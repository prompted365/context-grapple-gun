#!/usr/bin/env python3
"""
economy-bridge-adapter.py — L5 adapter: OT economic state → dual-path output.

Reads Foreman HTTP API snapshots and produces two output paths:
  1. Governance signals — sharp, immediate, full-fidelity (→ signal manifold)
  2. Rendering whispers — smoothed, atmospheric (→ encounter surfaces)

"Render smoothly, signal sharply" — arena:2026-04-09_ot-economic-integration-oavplt.

Spec sources:
  - autonomous_kernel/foreman-api-contract.md (L3 contract snapshot)
  - ak_control_room/envelopes.yaml (economy.snapshot, economy.signal, economy.whisper)
  - ak_control_room/services.yaml (svc_economy_bridge)

Invariants enforced:
  - INV-ECON-01: economic balance never determines standing
  - INV-ECON-02: burn cannot destroy standing
  - INV-ECON-03: mint gates require review

Usage (CLI):
    python3 economy-bridge-adapter.py --snapshot              # fetch + store snapshot
    python3 economy-bridge-adapter.py --observe               # fetch + emit signals + whispers
    python3 economy-bridge-adapter.py --gate-entropy <id>     # compute gate-entropy for entity
    python3 economy-bridge-adapter.py --probe                 # L4 drift probe only

Usage (module):
    from economy_bridge_adapter import (
        fetch_snapshot, emit_governance_signals, emit_rendering_whispers,
        compute_gate_entropy, probe_schema,
    )

Exit codes: 0=success, 1=error, 2=drift detected.
"""

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    from zone_root import resolve_zone_root, load_ticzone, audit_logs_path
    from lib.atomic_append import atomic_append_jsonl, atomic_write_json
except ImportError:
    def resolve_zone_root(start_dir=None):
        return os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    def audit_logs_path(zone_root, ticzone_config=None):
        return os.path.join(zone_root, "audit-logs")

    def load_ticzone(zone_root):
        return {}

    def atomic_append_jsonl(target, data):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, separators=(",", ":")) + "\n")

    def atomic_write_json(target, data):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, target)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Foreman endpoint — env override or default to tailnet-local
FOREMAN_ENDPOINT = os.environ.get(
    "OT_FOREMAN_ENDPOINT", "http://localhost:8420/api/v1"
)

# Snapshot required fields (from economy.snapshot envelope schema)
SNAPSHOT_REQUIRED_FIELDS = [
    "foreman_version", "barometer", "mint_gates", "supply"
]

# Hard state transitions — bypass smoothing, emit directly to governance
HARD_TRANSITIONS = {
    "circuit_breaker": {
        "path": ["barometer", "circuit_breaker_active"],
        "trigger_value": True,
        "signal_type": "economy_circuit_breaker",
        "severity": "HIGH",
        "volume": 60,
    },
    "reserve_breach": {
        "path_numerator": ["barometer", "reserve_level"],
        "path_denominator": ["barometer", "reserve_threshold"],
        "trigger": "below_threshold",
        "signal_type": "economy_reserve_breach",
        "severity": "HIGH",
        "volume": 60,
    },
    "crisis_state": {
        "path": ["barometer", "state"],
        "trigger_value": "crisis",
        "signal_type": "economy_crisis_state",
        "severity": "HIGH",
        "volume": 60,
    },
}

# Smoothing window for rendering whispers (in snapshots, not tics)
WHISPER_SMOOTHING_WINDOW = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_zone():
    """Resolve zone root and audit-logs path."""
    zr = resolve_zone_root(SCRIPT_DIR)
    tz = load_ticzone(zr)
    al = audit_logs_path(zr, tz)
    return zr, al


def _deterministic_signal_id(condition, discriminator=""):
    """Signal ID determinism per CGG CLAUDE.md."""
    raw = f"economy:{condition}:{discriminator}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"sig_economy_{condition}_{h}"


def _deep_get(obj, path):
    """Navigate nested dict by path list."""
    for key in path:
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return None
    return obj


def _snapshot_dir(al):
    """Path to economy bridge snapshot storage."""
    d = os.path.join(al, "services", "economy-bridge", "snapshots")
    os.makedirs(d, exist_ok=True)
    return d


def _whisper_dir(al):
    """Path to economy whisper state."""
    d = os.path.join(al, "services", "economy-bridge", "whispers")
    os.makedirs(d, exist_ok=True)
    return d


def _signal_path(al):
    """Path to today's signal JSONL."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    sig_dir = os.path.join(al, "signals")
    os.makedirs(sig_dir, exist_ok=True)
    return os.path.join(sig_dir, f"{today}.jsonl")


# ---------------------------------------------------------------------------
# L4 Probe — schema drift detection
# ---------------------------------------------------------------------------

def probe_schema(snapshot):
    """Verify snapshot conforms to expected schema. Returns (ok, issues)."""
    issues = []

    # Required top-level fields
    for field in SNAPSHOT_REQUIRED_FIELDS:
        if field not in snapshot:
            issues.append(f"missing required field: {field}")

    # Barometer shape
    baro = snapshot.get("barometer", {})
    if isinstance(baro, dict):
        if "state" not in baro:
            issues.append("barometer missing 'state'")
        if "circuit_breaker_active" not in baro:
            issues.append("barometer missing 'circuit_breaker_active'")
        rl = baro.get("reserve_level")
        if rl is not None and not (0 <= rl <= 1):
            issues.append(f"reserve_level out of range [0,1]: {rl}")
    else:
        issues.append("barometer is not a dict")

    # Mint gates shape
    gates = snapshot.get("mint_gates", {})
    if isinstance(gates, dict):
        for gate_name, gate in gates.items():
            if isinstance(gate, dict):
                if "active" not in gate:
                    issues.append(f"mint_gate '{gate_name}' missing 'active'")
            else:
                issues.append(f"mint_gate '{gate_name}' is not a dict")

    return len(issues) == 0, issues


# ---------------------------------------------------------------------------
# Fetch — HTTP snapshot from Foreman
# ---------------------------------------------------------------------------

def fetch_snapshot(endpoint=None):
    """Fetch economic state from Foreman HTTP API. Returns (snapshot, error)."""
    ep = endpoint or FOREMAN_ENDPOINT
    url = f"{ep}/state"
    now = datetime.now(timezone.utc)

    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (URLError, HTTPError, json.JSONDecodeError, OSError) as e:
        return None, str(e)

    # Wrap in economy.snapshot envelope
    snapshot = {
        "snapshot_id": f"snap_{now.strftime('%Y%m%dT%H%M%SZ')}",
        "captured_at": now.isoformat(),
        "source": "economy-bridge-adapter.py",
        "foreman_version": raw.get("foreman_version", "unknown"),
        "barometer_state": raw.get("barometer", {}).get("state", "unknown"),
        "circuit_breaker_active": raw.get("barometer", {}).get(
            "circuit_breaker_active", False),
        "reserve_level": raw.get("barometer", {}).get("reserve_level"),
        "reserve_threshold": raw.get("barometer", {}).get("reserve_threshold"),
        "mint_gates": raw.get("mint_gates", {}),
        "supply": raw.get("supply", {}),
        "burn_channels": raw.get("burn_channels", {}),
        # Preserve raw for probe
        "_raw": raw,
    }

    # L4 probe
    ok, issues = probe_schema(raw)
    if not ok:
        snapshot["_probe_issues"] = issues
        snapshot["_probe_status"] = "drift_detected"
    else:
        snapshot["_probe_status"] = "clean"

    return snapshot, None


def store_snapshot(snapshot, al):
    """Persist snapshot to audit-logs."""
    snap_dir = _snapshot_dir(al)
    fname = f"{snapshot['snapshot_id']}.json"
    atomic_write_json(os.path.join(snap_dir, fname), {
        k: v for k, v in snapshot.items() if not k.startswith("_")
    })

    # Also append to rolling JSONL for time-series
    atomic_append_jsonl(
        os.path.join(snap_dir, "snapshots.jsonl"),
        {k: v for k, v in snapshot.items() if not k.startswith("_")}
    )
    return fname


# ---------------------------------------------------------------------------
# Governance Signals — sharp, immediate, full-fidelity
# ---------------------------------------------------------------------------

def check_hard_transitions(snapshot):
    """Check for hard state transitions that bypass smoothing."""
    signals = []
    raw = snapshot.get("_raw", snapshot)

    # Circuit breaker
    cb = _deep_get(raw, ["barometer", "circuit_breaker_active"])
    if cb is True:
        signals.append({
            "signal_type": "economy_circuit_breaker",
            "severity": "HIGH",
            "condition": "circuit_breaker_active",
            "raw_value": True,
            "volume": 60,
        })

    # Reserve breach
    rl = _deep_get(raw, ["barometer", "reserve_level"])
    rt = _deep_get(raw, ["barometer", "reserve_threshold"])
    if rl is not None and rt is not None and rl < rt:
        signals.append({
            "signal_type": "economy_reserve_breach",
            "severity": "HIGH",
            "condition": f"reserve_level ({rl}) < threshold ({rt})",
            "raw_value": rl,
            "threshold_reference": rt,
            "volume": 60,
        })

    # Crisis state
    state = _deep_get(raw, ["barometer", "state"])
    if state == "crisis":
        signals.append({
            "signal_type": "economy_crisis_state",
            "severity": "HIGH",
            "condition": "barometer_state=crisis",
            "raw_value": state,
            "volume": 60,
        })

    # Mint gate halted
    gates = raw.get("mint_gates", {})
    for gate_name, gate in gates.items():
        if isinstance(gate, dict) and gate.get("active") is False:
            signals.append({
                "signal_type": "economy_mint_halted",
                "severity": "MEDIUM",
                "condition": f"mint_gate_{gate_name}_halted",
                "raw_value": gate,
                "volume": 40,
            })

    return signals


def emit_governance_signals(snapshot, al):
    """Check hard transitions and emit governance signals to manifold."""
    hard_signals = check_hard_transitions(snapshot)
    emitted = []

    for sig in hard_signals:
        signal_id = _deterministic_signal_id(
            sig["signal_type"], sig["condition"]
        )
        signal_record = {
            "type": "signal",
            "id": signal_id,
            "kind": "TENSION" if sig["severity"] == "HIGH" else "WATCH",
            "band": "COGNITIVE",
            "volume": sig["volume"],
            "status": "active",
            "subsystem": "economy_bridge",
            "description": f"Economy bridge: {sig['condition']}",
            "signal_type": sig["signal_type"],
            "severity": sig["severity"],
            "raw_value": sig["raw_value"],
            "source_snapshot_id": snapshot.get("snapshot_id"),
            "emitted_at": datetime.now(timezone.utc).isoformat(),
            "source": "economy-bridge-adapter.py",
        }
        if "threshold_reference" in sig:
            signal_record["threshold_reference"] = sig["threshold_reference"]

        atomic_append_jsonl(_signal_path(al), signal_record)
        emitted.append(signal_id)

    # Emit stale signal if probe detected drift
    if snapshot.get("_probe_status") == "drift_detected":
        drift_id = _deterministic_signal_id(
            "economy_schema_drift", snapshot.get("foreman_version", "")
        )
        atomic_append_jsonl(_signal_path(al), {
            "type": "signal",
            "id": drift_id,
            "kind": "WATCH",
            "band": "COGNITIVE",
            "volume": 35,
            "status": "active",
            "subsystem": "economy_bridge",
            "description": f"Foreman schema drift: {snapshot.get('_probe_issues', [])}",
            "emitted_at": datetime.now(timezone.utc).isoformat(),
            "source": "economy-bridge-adapter.py",
        })
        emitted.append(drift_id)

    return emitted


# ---------------------------------------------------------------------------
# Rendering Whispers — smoothed, atmospheric
# ---------------------------------------------------------------------------

def _load_whisper_history(al):
    """Load recent whisper state for smoothing."""
    history_path = os.path.join(_whisper_dir(al), "history.json")
    if os.path.exists(history_path):
        with open(history_path, "r") as f:
            return json.load(f)
    return {"states": []}


def _save_whisper_history(al, history):
    """Save whisper history (bounded to smoothing window)."""
    history["states"] = history["states"][-WHISPER_SMOOTHING_WINDOW:]
    atomic_write_json(
        os.path.join(_whisper_dir(al), "history.json"), history
    )


def compute_smoothed_state(snapshot, history):
    """Compute smoothed atmospheric values from snapshot history."""
    # Extract numeric state
    raw = snapshot.get("_raw", snapshot)
    current = {
        "reserve_level": _deep_get(raw, ["barometer", "reserve_level"]) or 0,
        "barometer_state": _deep_get(raw, ["barometer", "state"]) or "unknown",
        "total_supply": _deep_get(raw, ["supply", "total_ucoin"]) or 0,
        "circulating": _deep_get(raw, ["supply", "circulating"]) or 0,
        "staked_ratio": 0,
    }

    total = current["total_supply"]
    staked = _deep_get(raw, ["supply", "staked"]) or 0
    if total > 0:
        current["staked_ratio"] = staked / total

    # Add to history
    history["states"].append(current)
    states = history["states"][-WHISPER_SMOOTHING_WINDOW:]

    # Compute smoothed values (simple moving average for numerics)
    smoothed = {
        "reserve_level": sum(
            s.get("reserve_level", 0) for s in states
        ) / len(states),
        "staked_ratio": sum(
            s.get("staked_ratio", 0) for s in states
        ) / len(states),
        "circulating": sum(
            s.get("circulating", 0) for s in states
        ) / len(states),
    }

    # Trend direction (last 3 vs first 3 if enough data)
    if len(states) >= 3:
        recent = sum(s.get("reserve_level", 0) for s in states[-3:]) / 3
        earlier = sum(s.get("reserve_level", 0) for s in states[:3]) / 3
        if recent > earlier * 1.05:
            smoothed["trend_direction"] = "improving"
        elif recent < earlier * 0.95:
            smoothed["trend_direction"] = "declining"
        else:
            smoothed["trend_direction"] = "stable"
    else:
        smoothed["trend_direction"] = "insufficient_data"

    # Map to atmospheric state for encounter surfaces
    rl = smoothed["reserve_level"]
    if rl > 0.7:
        smoothed["ambient_state"] = "prosperous"
    elif rl > 0.4:
        smoothed["ambient_state"] = "stable"
    elif rl > 0.2:
        smoothed["ambient_state"] = "cautious"
    else:
        smoothed["ambient_state"] = "austere"

    return smoothed


def emit_rendering_whispers(snapshot, al):
    """Produce smoothed atmospheric whisper for encounter surfaces."""
    # Hard transitions do NOT produce whispers
    hard = check_hard_transitions(snapshot)
    if hard:
        # Still update history but mark whisper as suppressed
        history = _load_whisper_history(al)
        compute_smoothed_state(snapshot, history)
        _save_whisper_history(al, history)
        return {"suppressed": True, "reason": "hard_transition_active",
                "hard_signals": len(hard)}

    history = _load_whisper_history(al)
    smoothed = compute_smoothed_state(snapshot, history)
    _save_whisper_history(al, history)

    whisper = {
        "type": "economy_whisper",
        "whisper_type": "ambient_economy",
        "source_snapshot_id": snapshot.get("snapshot_id"),
        "ambient_state": smoothed["ambient_state"],
        "smoothing_window": WHISPER_SMOOTHING_WINDOW,
        "atmospheric_values": {
            "reserve_level": round(smoothed["reserve_level"], 4),
            "staked_ratio": round(smoothed["staked_ratio"], 4),
            "circulating": round(smoothed["circulating"], 2),
        },
        "trend_direction": smoothed["trend_direction"],
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "source": "economy-bridge-adapter.py",
    }

    # Persist whisper to whisper log
    atomic_append_jsonl(
        os.path.join(_whisper_dir(al), "whispers.jsonl"), whisper
    )

    # Write current whisper state for encounter surfaces to read
    atomic_write_json(
        os.path.join(_whisper_dir(al), "current.json"), whisper
    )

    return whisper


# ---------------------------------------------------------------------------
# Gate-Entropy computation
# ---------------------------------------------------------------------------

def compute_gate_entropy(entity_activity):
    """Compute Shannon entropy over gate distribution.

    Args:
        entity_activity: dict with gate_history counts
            {"contribution": N, "governance": N, "exchange": N, "endorsement": N}

    Returns:
        float: entropy in bits. Max = log2(4) ≈ 2.0 for uniform distribution.
    """
    gate_hist = entity_activity.get("gate_history", {})
    counts = [
        gate_hist.get("contribution", 0),
        gate_hist.get("governance", 0),
        gate_hist.get("exchange", 0),
        gate_hist.get("endorsement", 0),
    ]

    total = sum(counts)
    if total == 0:
        return 0.0

    entropy = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            entropy -= p * math.log2(p)

    return round(entropy, 4)


def fetch_entity_gate_entropy(entity_id, endpoint=None):
    """Fetch entity summary from Foreman and compute gate-entropy."""
    ep = endpoint or FOREMAN_ENDPOINT
    url = f"{ep}/entity/{entity_id}/summary"

    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (URLError, HTTPError, json.JSONDecodeError, OSError) as e:
        return None, str(e)

    entropy = compute_gate_entropy(data)
    return {
        "entity_id": entity_id,
        "gate_entropy": entropy,
        "max_entropy": round(math.log2(4), 4),
        "gate_distribution": data.get("gate_history", {}),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }, None


# ---------------------------------------------------------------------------
# Full observation cycle
# ---------------------------------------------------------------------------

def observe(endpoint=None):
    """Full observation cycle: fetch → probe → signals → whispers.

    Returns observation envelope with all outputs.
    """
    zr, al = _resolve_zone()
    now = datetime.now(timezone.utc)

    # Fetch
    snapshot, err = fetch_snapshot(endpoint)
    if err:
        # Emit stale signal and return error envelope
        stale_id = _deterministic_signal_id("economy_fetch_failed", "")
        atomic_append_jsonl(_signal_path(al), {
            "type": "signal",
            "id": stale_id,
            "kind": "WATCH",
            "band": "COGNITIVE",
            "volume": 30,
            "status": "active",
            "subsystem": "economy_bridge",
            "description": f"Foreman fetch failed: {err}",
            "emitted_at": now.isoformat(),
            "source": "economy-bridge-adapter.py",
        })
        return {
            "status": "error",
            "error": err,
            "signal_emitted": stale_id,
            "timestamp": now.isoformat(),
        }

    # Store snapshot
    snap_file = store_snapshot(snapshot, al)

    # Governance signals (sharp path)
    emitted_signals = emit_governance_signals(snapshot, al)

    # Rendering whispers (smooth path)
    whisper = emit_rendering_whispers(snapshot, al)

    envelope = {
        "status": "complete",
        "timestamp": now.isoformat(),
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot_file": snap_file,
        "probe_status": snapshot.get("_probe_status", "unknown"),
        "governance_signals_emitted": emitted_signals,
        "whisper": whisper if not isinstance(whisper, dict)
                          or not whisper.get("suppressed")
                          else {"suppressed": True},
        "hard_transitions_detected": len(
            check_hard_transitions(snapshot)
        ),
    }

    return envelope


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="OT Economy Bridge Adapter (L5)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--snapshot", action="store_true",
                       help="Fetch and store snapshot only")
    group.add_argument("--observe", action="store_true",
                       help="Full observation cycle (fetch + signals + whispers)")
    group.add_argument("--gate-entropy", metavar="ENTITY_ID",
                       help="Compute gate-entropy for entity")
    group.add_argument("--probe", action="store_true",
                       help="L4 drift probe only")
    parser.add_argument("--endpoint", default=None,
                        help="Override Foreman endpoint URL")

    args = parser.parse_args()

    if args.snapshot:
        snapshot, err = fetch_snapshot(args.endpoint)
        if err:
            print(json.dumps({"error": err}), file=sys.stderr)
            sys.exit(1)
        _, al = _resolve_zone()
        fname = store_snapshot(snapshot, al)
        print(json.dumps({
            "snapshot_id": snapshot["snapshot_id"],
            "file": fname,
            "probe_status": snapshot.get("_probe_status"),
        }, indent=2))

    elif args.observe:
        result = observe(args.endpoint)
        print(json.dumps(result, indent=2))
        if result["status"] == "error":
            sys.exit(1)
        if result.get("probe_status") == "drift_detected":
            sys.exit(2)

    elif args.gate_entropy:
        result, err = fetch_entity_gate_entropy(
            args.gate_entropy, args.endpoint)
        if err:
            print(json.dumps({"error": err}), file=sys.stderr)
            sys.exit(1)
        print(json.dumps(result, indent=2))

    elif args.probe:
        snapshot, err = fetch_snapshot(args.endpoint)
        if err:
            print(json.dumps({"error": err, "probe": "fetch_failed"}),
                  file=sys.stderr)
            sys.exit(1)
        ok, issues = probe_schema(snapshot.get("_raw", snapshot))
        result = {"probe_status": "clean" if ok else "drift_detected",
                  "issues": issues}
        print(json.dumps(result, indent=2))
        sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
