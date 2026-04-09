#!/usr/bin/env python3
"""
visitor-economy-monitor.py — Mogul-callable visitor economy governance monitor.

Wraps cache-ops.py, standing-engine.py, and biome-engine.py with governance
envelope production for mandate cycle integration.

Functions:
  cache_refresh_cycle(tic)   — wraps cache-ops refresh_cycle + governance envelope
  standing_decay_check()     — scan visitors for trust_score decay below thresholds
  biome_health_check()       — read biome state, emit signals on threshold violations
  visitor_census()           — count active visitors by standing tier

CLI:
  python3 visitor-economy-monitor.py --cache-refresh <tic>
  python3 visitor-economy-monitor.py --standing-decay
  python3 visitor-economy-monitor.py --biome-health
  python3 visitor-economy-monitor.py --census
  python3 visitor-economy-monitor.py --full-cycle <tic>

Exit codes: 0=success, 1=error.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow importing siblings from same directory
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from zone_root import resolve_zone_root, load_ticzone, audit_logs_path
from lib.atomic_append import atomic_append_jsonl, atomic_write_json


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
    """Produce a deterministic signal ID from condition + discriminator."""
    raw = f"{condition}:{discriminator}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"sig_{condition}_{h}"


def _emit_signal(al, signal_id, kind, band, description, subsystem="visitor_economy"):
    """Append a signal to today's signal JSONL."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    sig_dir = os.path.join(al, "signals")
    os.makedirs(sig_dir, exist_ok=True)

    signal = {
        "type": "signal",
        "id": signal_id,
        "kind": kind,
        "band": band,
        "volume": 30,
        "status": "active",
        "subsystem": subsystem,
        "description": description,
        "emitted_at": now.isoformat(),
        "source": "visitor-economy-monitor.py",
    }
    atomic_append_jsonl(os.path.join(sig_dir, f"{today}.jsonl"), signal)
    return signal


# ---------------------------------------------------------------------------
# 1. Cache Refresh Cycle
# ---------------------------------------------------------------------------

def cache_refresh_cycle(tic, zone_root=None):
    """Wrap cache-ops.py refresh_cycle() with governance envelope.

    Runs the 6-step cache refresh, produces cache-state artifact,
    and emits summary signals. Returns envelope dict.
    """
    now = datetime.now(timezone.utc)
    zr = zone_root or resolve_zone_root(SCRIPT_DIR)
    _, al = _resolve_zone()

    # Import cache-ops refresh_cycle
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cache_ops", os.path.join(SCRIPT_DIR, "cache-ops.py"))
        cache_ops = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cache_ops)
        artifact = cache_ops.refresh_cycle(tic=tic, project_dir=zr)
    except Exception as e:
        artifact = {
            "artifact_type": "cache_state",
            "error": str(e),
            "produced_at": now.isoformat(),
            "produced_by_tic": tic,
            "summary": {
                "total_entries": 0, "active": 0, "stale": 0,
                "quarantined": 0, "deprecated": 0,
                "archived_this_cycle": 0, "pending_queue_depth": 0,
            },
            "trust_distribution": {"mean": 0.0, "median": 0.0,
                                   "min": 0.0, "max": 0.0},
            "search_tier_in_use": "tier_1",
            "monopoly_check": {"top_contributor_entity": "",
                               "top_contributor_percentage": 0.0,
                               "dampening_active": False},
            "ttl_health": {"entries_approaching_expiry": 0,
                           "probes_dispatched": 0, "probes_responded": 0,
                           "entries_expired_this_cycle": 0},
            "standing_changes_processed": 0,
            "signals_emitted": [],
        }

    envelope = {
        "operation": "cache_refresh",
        "tic": tic,
        "timestamp": now.isoformat(),
        "source": "visitor-economy-monitor.py",
        "cache_state": artifact,
        "status": "error" if "error" in artifact else "complete",
    }

    return envelope


# ---------------------------------------------------------------------------
# 2. Standing Decay Check
# ---------------------------------------------------------------------------

def standing_decay_check(zone_root=None):
    """Scan all active visitors for trust_score decay below standing thresholds.

    Identifies entities approaching demotion and emits WATCH signals.
    Returns a summary dict.
    """
    now = datetime.now(timezone.utc)
    zr = zone_root or resolve_zone_root(SCRIPT_DIR)
    _, al = _resolve_zone()

    # Load agent index for visitor enumeration
    biome_dir = os.path.join(al, "biome")
    idx_path = os.path.join(biome_dir, "visa-registry", "agent-index.json")
    if not os.path.isfile(idx_path):
        return {
            "operation": "standing_decay_check",
            "timestamp": now.isoformat(),
            "visitors_scanned": 0,
            "at_risk": [],
            "signals_emitted": [],
        }

    with open(idx_path, "r", encoding="utf-8") as f:
        idx = json.load(f)

    visitors_by_standing = idx.get("visitors_by_standing", {})

    # Import standing engine
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "standing_engine", os.path.join(SCRIPT_DIR, "standing-engine.py"))
        se = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(se)
    except Exception as e:
        return {
            "operation": "standing_decay_check",
            "timestamp": now.isoformat(),
            "error": str(e),
            "visitors_scanned": 0,
            "at_risk": [],
            "signals_emitted": [],
        }

    # Standing thresholds from standing-engine CONFIG
    trust_thresholds = se.CONFIG.get("trust_thresholds", {})

    at_risk = []
    signals_emitted = []
    visitors_scanned = 0

    for standing, entity_ids in visitors_by_standing.items():
        threshold = trust_thresholds.get(standing, 0.0)
        for eid in entity_ids:
            visitors_scanned += 1
            try:
                result = se.compute_trust_score(eid, zone_root=zr)
                ts = result["trust_score"]
                # At risk: within 20% above threshold or below it
                warning_band = threshold * 0.20
                if ts < threshold + warning_band:
                    risk_entry = {
                        "entity_id": eid,
                        "current_standing": standing,
                        "trust_score": round(ts, 4),
                        "threshold": threshold,
                        "below_threshold": ts < threshold,
                    }
                    at_risk.append(risk_entry)

                    if ts < threshold:
                        sig_id = _deterministic_signal_id(
                            "standing.decay_below_threshold", eid)
                        sig = _emit_signal(
                            al, sig_id, "WATCH", "COGNITIVE",
                            f"Entity {eid} trust_score {ts:.3f} below "
                            f"{standing} threshold {threshold}")
                        signals_emitted.append(sig_id)
            except Exception:
                # Entity computation failed — skip, don't block cycle
                continue

    return {
        "operation": "standing_decay_check",
        "timestamp": now.isoformat(),
        "visitors_scanned": visitors_scanned,
        "at_risk": at_risk,
        "signals_emitted": signals_emitted,
    }


# ---------------------------------------------------------------------------
# 3. Biome Health Check
# ---------------------------------------------------------------------------

def biome_health_check(zone_root=None):
    """Read current biome state, compute health monitors, emit signals.

    Returns health summary dict.
    """
    now = datetime.now(timezone.utc)
    zr = zone_root or resolve_zone_root(SCRIPT_DIR)
    _, al = _resolve_zone()

    # Import biome engine
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "biome_engine", os.path.join(SCRIPT_DIR, "biome-engine.py"))
        be = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(be)
    except Exception as e:
        return {
            "operation": "biome_health_check",
            "timestamp": now.isoformat(),
            "error": str(e),
            "health": {},
            "signals_emitted": [],
        }

    # Load biome state
    try:
        topology, organisms, environment = be.load_state()
        health = be.compute_health(topology, organisms, environment)
        health_signals = be.check_health_signals(health, environment)
    except Exception as e:
        return {
            "operation": "biome_health_check",
            "timestamp": now.isoformat(),
            "error": str(e),
            "health": {},
            "signals_emitted": [],
        }

    # health_signals is a list of signal ID strings already emitted by
    # biome-engine's check_health_signals (which calls emit_signal internally).
    # We just collect them for the envelope — no need to re-emit.
    signals_emitted = health_signals if health_signals else []

    cycle = environment.get("cycle", 0)
    act = environment.get("act", "unknown")

    return {
        "operation": "biome_health_check",
        "timestamp": now.isoformat(),
        "biome_cycle": cycle,
        "biome_act": act,
        "health": health,
        "thresholds_violated": len(signals_emitted),
        "signals_emitted": signals_emitted,
    }


# ---------------------------------------------------------------------------
# 4. Visitor Census
# ---------------------------------------------------------------------------

def visitor_census(zone_root=None):
    """Count active visitors by standing tier, compute aggregate stats.

    Produces census artifact for governance_query.py (MVOS L3).
    Returns census dict.
    """
    now = datetime.now(timezone.utc)
    zr = zone_root or resolve_zone_root(SCRIPT_DIR)
    _, al = _resolve_zone()

    biome_dir = os.path.join(al, "biome")
    idx_path = os.path.join(biome_dir, "visa-registry", "agent-index.json")

    if not os.path.isfile(idx_path):
        census = {
            "artifact_type": "visitor_census",
            "timestamp": now.isoformat(),
            "total_active": 0,
            "by_standing": {},
            "standing_order": ["guest", "tourist", "student",
                               "resident", "citizen"],
        }
    else:
        with open(idx_path, "r", encoding="utf-8") as f:
            idx = json.load(f)

        vbs = idx.get("visitors_by_standing", {})
        by_standing = {}
        total_active = 0
        for standing, entities in vbs.items():
            count = len(entities)
            by_standing[standing] = count
            total_active += count

        census = {
            "artifact_type": "visitor_census",
            "timestamp": now.isoformat(),
            "total_active": total_active,
            "by_standing": by_standing,
            "standing_order": ["guest", "tourist", "student",
                               "resident", "citizen"],
        }

    # Persist census artifact
    census_dir = os.path.join(biome_dir, "census")
    os.makedirs(census_dir, exist_ok=True)
    artifact_path = os.path.join(
        census_dir,
        f"{now.strftime('%Y-%m-%dT%H%M%S')}-census.json")
    atomic_write_json(artifact_path, census)

    return census


# ---------------------------------------------------------------------------
# 5. Full Cycle (all operations)
# ---------------------------------------------------------------------------

def full_cycle(tic, zone_root=None):
    """Run all visitor economy monitoring operations.

    Returns combined results dict.
    """
    results = {}
    results["cache_refresh"] = cache_refresh_cycle(tic, zone_root)
    results["standing_decay"] = standing_decay_check(zone_root)
    results["biome_health"] = biome_health_check(zone_root)
    results["census"] = visitor_census(zone_root)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Visitor economy governance monitor — Mogul mandate callable",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cache-refresh", type=int, metavar="TIC",
                       help="Run cache refresh cycle for given tic")
    group.add_argument("--standing-decay", action="store_true",
                       help="Run standing decay check")
    group.add_argument("--biome-health", action="store_true",
                       help="Run biome health check")
    group.add_argument("--census", action="store_true",
                       help="Run visitor census")
    group.add_argument("--full-cycle", type=int, metavar="TIC",
                       help="Run all operations for given tic")

    parser.add_argument("--zone-root", default=None,
                        help="Zone root override")

    args = parser.parse_args()

    zr = args.zone_root

    if args.cache_refresh is not None:
        result = cache_refresh_cycle(args.cache_refresh, zr)
    elif args.standing_decay:
        result = standing_decay_check(zr)
    elif args.biome_health:
        result = biome_health_check(zr)
    elif args.census:
        result = visitor_census(zr)
    elif args.full_cycle is not None:
        result = full_cycle(args.full_cycle, zr)
    else:
        parser.print_help()
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
