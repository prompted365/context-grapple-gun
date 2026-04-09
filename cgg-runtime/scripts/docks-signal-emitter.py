#!/usr/bin/env python3
"""docks-signal-emitter.py — Emit Docks-specific signals with deterministic IDs.

Signal types (from docks-ingress-spec.md):
  docks.registration         — WATCH  — every new visitor registration
  docks.registration_flood   — ALERT  — registration rate exceeds threshold
  docks.probe_failure        — WATCH  — probe handshake failure (any probe)
  docks.admission            — INFO   — successful admission to biome
  docks.rejection            — WATCH  — registration rejected (probe 1 failure)
  docks.standing_change      — INFO   — any visa state transition

Signal ID determinism (per CGG CLAUDE.md Signal ID Determinism rule):
  sig_{signal_type}_{content_hash_hex8}
  Content hash = SHA-256 of deterministic content fields (excluding timestamps).

Usage as module:
    from docks_signal_emitter import emit_docks_signal
    signal_id = emit_docks_signal(zone_root, "docks.registration", content_fields, band="WATCH")

Usage as CLI:
    python3 docks-signal-emitter.py emit --type docks.registration --content '{"entity_id":"..."}' [--zone-root PATH]
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, birth_topology

# ─────────────────────────────────────────────
# Signal type definitions from docks-ingress-spec.md
# ─────────────────────────────────────────────

DOCKS_SIGNAL_TYPES = {
    "docks.registration": {
        "band": "COGNITIVE",
        "kind": "WATCH",
        "volume": 20,
        "deterministic_fields": ["entity_id", "ingress_lane", "tvi_tier_claim"],
    },
    "docks.registration_flood": {
        "band": "COGNITIVE",
        "kind": "ALERT",
        "volume": 70,
        "deterministic_fields": ["rate", "threshold", "window"],
    },
    "docks.probe_failure": {
        "band": "COGNITIVE",
        "kind": "WATCH",
        "volume": 30,
        "deterministic_fields": ["entity_id", "failed_probe", "probe_index"],
    },
    "docks.admission": {
        "band": "COGNITIVE",
        "kind": "INFO",
        "volume": 15,
        "deterministic_fields": ["entity_id", "standing", "tvi_tier"],
    },
    "docks.rejection": {
        "band": "COGNITIVE",
        "kind": "WATCH",
        "volume": 35,
        "deterministic_fields": ["source_ip", "rejection_reason"],
    },
    "docks.standing_change": {
        "band": "COGNITIVE",
        "kind": "INFO",
        "volume": 20,
        "deterministic_fields": ["entity_id", "from_state", "to_state"],
    },
}


def compute_signal_id(signal_type: str, content: dict, type_def: dict) -> str:
    """Compute deterministic signal ID from content hash.

    ID format: sig_{signal_type}_{content_hash_hex8}
    Hash input: signal_type + sorted deterministic field values.
    """
    det_fields = type_def.get("deterministic_fields", [])
    hash_parts = [signal_type]
    for field in sorted(det_fields):
        val = content.get(field, "")
        hash_parts.append(f"{field}={val}")
    hash_input = "|".join(hash_parts)
    content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:8]
    return f"sig_{signal_type}_{content_hash}"


def emit_docks_signal(
    zone_root: str,
    signal_type: str,
    content: dict,
    *,
    band: str | None = None,
    kind: str | None = None,
    volume: int | None = None,
    source: str = "docks-handler.py",
) -> str:
    """Emit a Docks signal to the signal store.

    Args:
        zone_root: Federation zone root path.
        signal_type: One of DOCKS_SIGNAL_TYPES keys.
        content: Signal content fields (must include deterministic fields).
        band: Override default band for this signal type.
        kind: Override default kind for this signal type.
        volume: Override default volume for this signal type.
        source: Source script name for provenance.

    Returns:
        signal_id: The deterministic signal ID that was emitted.

    Raises:
        ValueError: If signal_type is unknown.
    """
    if signal_type not in DOCKS_SIGNAL_TYPES:
        raise ValueError(
            f"Unknown docks signal type '{signal_type}'. "
            f"Valid types: {', '.join(sorted(DOCKS_SIGNAL_TYPES))}"
        )

    type_def = DOCKS_SIGNAL_TYPES[signal_type]
    resolved_band = band or type_def["band"]
    resolved_kind = kind or type_def["kind"]
    resolved_volume = volume if volume is not None else type_def["volume"]

    signal_id = compute_signal_id(signal_type, content, type_def)

    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    signal_dir = os.path.join(al_path, "signals")
    os.makedirs(signal_dir, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    signal_file = os.path.join(signal_dir, f"{date_str}.jsonl")

    topo = birth_topology(zone_root)

    signal = {
        "type": "signal",
        "id": signal_id,
        "signal_type": signal_type,
        "kind": resolved_kind,
        "band": resolved_band,
        "status": "active",
        "volume": resolved_volume,
        "max_volume": 100,
        "tick_count": 0,
        "subsystem": "docks",
        "source": source,
        "source_date": date_str,
        "created_at": now.isoformat(),
        "birth_rung": topo["birth_rung"],
        "payload": content,
        "origin": "deterministic",
    }

    # Write signal to daily JSONL
    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(signal_file, signal)
    except ImportError:
        import fcntl
        lockfile = signal_file + ".lock"
        line = json.dumps(signal, separators=(",", ":")) + "\n"
        with open(lockfile, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                with open(signal_file, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    # Auto-append to active-manifest.jsonl for Mogul signal scan visibility
    manifest_path = os.path.join(signal_dir, "active-manifest.jsonl")
    manifest_entry = {
        "signal_id": signal_id,
        "signal_type": signal_type,
        "kind": resolved_kind,
        "band": resolved_band,
        "status": "active",
        "volume": resolved_volume,
        "source_file": f"signals/{date_str}.jsonl",
        "summary": _build_summary(signal_type, content),
    }
    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(manifest_path, manifest_entry)
    except ImportError:
        with open(manifest_path, "a", encoding="utf-8") as mf:
            mf.write(json.dumps(manifest_entry, separators=(",", ":")) + "\n")

    return signal_id


def _build_summary(signal_type: str, content: dict) -> str:
    """Build a human-readable summary for manifest entry."""
    if signal_type == "docks.registration":
        return f"Visitor registration: {content.get('entity_id', 'unknown')}"
    elif signal_type == "docks.registration_flood":
        return f"Registration flood: {content.get('rate', '?')}/{content.get('window', '?')}s (threshold {content.get('threshold', '?')})"
    elif signal_type == "docks.probe_failure":
        return f"Probe failure: {content.get('entity_id', 'unknown')} failed {content.get('failed_probe', 'unknown')} (probe {content.get('probe_index', '?')})"
    elif signal_type == "docks.admission":
        return f"Visitor admitted: {content.get('entity_id', 'unknown')} as {content.get('standing', 'unknown')} (TVI {content.get('tvi_tier', '?')})"
    elif signal_type == "docks.rejection":
        return f"Visitor rejected: {content.get('rejection_reason', 'unknown')} from {content.get('source_ip', 'unknown')}"
    elif signal_type == "docks.standing_change":
        return f"Standing change: {content.get('entity_id', 'unknown')} {content.get('from_state', '?')} -> {content.get('to_state', '?')}"
    return f"Docks signal: {signal_type}"


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Emit Docks-specific signals with deterministic IDs."
    )
    sub = parser.add_subparsers(dest="command")

    emit_p = sub.add_parser("emit", help="Emit a docks signal")
    emit_p.add_argument("--type", required=True, dest="signal_type",
                        choices=sorted(DOCKS_SIGNAL_TYPES.keys()),
                        help="Signal type to emit")
    emit_p.add_argument("--content", required=True,
                        help="JSON object with signal content fields")
    emit_p.add_argument("--zone-root", default=None,
                        help="Zone root path (auto-detected if omitted)")
    emit_p.add_argument("--source", default="docks-signal-emitter.py",
                        help="Source script name for provenance")

    list_p = sub.add_parser("list-types", help="List available signal types")

    args = parser.parse_args()

    if args.command == "list-types":
        for stype, sdef in sorted(DOCKS_SIGNAL_TYPES.items()):
            print(f"  {stype:<30} {sdef['kind']:<8} vol={sdef['volume']}")
        return

    if args.command == "emit":
        zone_root = args.zone_root or resolve_zone_root()
        try:
            content = json.loads(args.content)
        except json.JSONDecodeError as e:
            print(json.dumps({"ok": False, "error": f"Invalid JSON: {e}"}))
            sys.exit(1)

        signal_id = emit_docks_signal(
            zone_root, args.signal_type, content, source=args.source
        )
        print(json.dumps({"ok": True, "signal_id": signal_id}))
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
