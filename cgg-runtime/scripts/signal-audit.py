#!/usr/bin/env python3
"""
Signal Audit — Dedup, Metrics, Zombie Detection, Store Diagnostics.

Operates on audit-logs/signals/*.jsonl with non-destructive semantics:
- compact: keep latest entry per (date, id), archive raw to signals/raw/
- metrics: unique_signal_count, collision_pressure per (date, id)
- audit: identify zombie signals (warrant-eligible but can't reach threshold)
- view: latest-per-id active signal summary

Signals do NOT expire. This utility never sets status=expired.
Compaction is limited to duplicate transport emissions — never lesson/covenant compression.

Exit codes: 0=success, 1=validation error, 2=IO error, 3=data error.

Usage:
    python signal-audit.py metrics [--project-dir PATH] [--json]
    python signal-audit.py view [--project-dir PATH] [--json]
    python signal-audit.py compact [--project-dir PATH] [--dry-run]
    python signal-audit.py audit [--project-dir PATH] [--json]
"""

import argparse
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, signal_governance


def resolve_signal_dir(project_dir=None):
    """Resolve the signal directory from zone root, never cwd."""
    zone_root = project_dir or resolve_zone_root()
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    return Path(al_path) / "signals", tz_config


def load_all_entries(signal_dir):
    """Load all JSONL entries from the signal store, preserving file origin."""
    entries = []
    if not signal_dir.is_dir():
        return entries
    for fpath in sorted(signal_dir.glob("*.jsonl")):
        with open(fpath) as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    obj["_source_file"] = fpath.name
                    obj["_source_lineno"] = lineno
                    entries.append(obj)
                except json.JSONDecodeError:
                    continue
    return entries


def latest_per_id(entries):
    """Apply latest-entry-per-ID-wins. Returns dict {id: entry}."""
    latest = {}
    for e in entries:
        eid = e.get("id") or e.get("signal_id")
        if eid:
            latest[eid] = e
    return latest


def cmd_metrics(entries, output_json=False):
    """Show unique_signal_count, collision_pressure, and per-file stats."""
    file_counts = Counter()
    id_counts = Counter()
    id_date_counts = defaultdict(Counter)

    for e in entries:
        eid = e.get("id") or e.get("signal_id") or "NO_ID"
        source_file = e.get("_source_file", "unknown")
        source_date = e.get("source_date", "unknown")
        file_counts[source_file] += 1
        id_counts[eid] += 1
        id_date_counts[eid][source_date] += 1

    latest = latest_per_id(entries)
    active = {k: v for k, v in latest.items() if v.get("status") == "active"}

    if output_json:
        collisions = []
        for eid, count in id_counts.most_common():
            if count <= 1:
                continue
            collisions.append({
                "id": eid,
                "count": count,
                "subsystem": latest.get(eid, {}).get("subsystem"),
                "status": latest.get(eid, {}).get("status"),
                "by_date": dict(sorted(id_date_counts[eid].items())),
            })
        per_file = []
        for fname, count in sorted(file_counts.items()):
            unique_in_file = len({
                e.get("id") or e.get("signal_id")
                for e in entries
                if e.get("_source_file") == fname
            })
            per_file.append({"file": fname, "entries": count, "unique": unique_in_file})
        result = {
            "command": "metrics",
            "total_entries": len(entries),
            "unique_signal_ids": len(id_counts),
            "active_signals": len(active),
            "duplicate_entries": len(entries) - len(id_counts),
            "compression_ratio": round(len(id_counts) / max(len(entries), 1), 4),
            "collision_pressure": collisions,
            "per_file": per_file,
        }
        print(json.dumps(result, indent=2))
        return

    print("=" * 60)
    print("SIGNAL STORE METRICS")
    print("=" * 60)
    print(f"  Total JSONL entries:    {len(entries)}")
    print(f"  Unique signal IDs:      {len(id_counts)}")
    print(f"  Active (latest state):  {len(active)}")
    print(f"  Duplicate entries:      {len(entries) - len(id_counts)}")
    print(f"  Compression ratio:      {len(id_counts)}/{len(entries)} "
          f"({len(id_counts)/max(len(entries),1)*100:.1f}%)")
    print()

    print("COLLISION PRESSURE (duplicates per signal ID):")
    print("-" * 60)
    for eid, count in id_counts.most_common():
        if count <= 1:
            continue
        subsystem = latest.get(eid, {}).get("subsystem", "?")
        status = latest.get(eid, {}).get("status", "?")
        dates = ", ".join(f"{d}:{n}" for d, n in sorted(id_date_counts[eid].items()))
        print(f"  {count:>5}x  {eid}")
        print(f"         subsystem={subsystem}  status={status}")
        print(f"         by date: {dates}")
    print()

    print("PER-FILE ENTRY COUNTS:")
    print("-" * 60)
    for fname, count in sorted(file_counts.items()):
        unique_in_file = len({
            e.get("id") or e.get("signal_id")
            for e in entries
            if e.get("_source_file") == fname
        })
        print(f"  {count:>5} entries  ({unique_in_file} unique)  {fname}")


def cmd_view(entries, output_json=False):
    """Show latest state per unique signal ID."""
    latest = latest_per_id(entries)
    if not latest:
        if output_json:
            print(json.dumps({"command": "view", "signals": []}))
        else:
            print("No signals found.")
        return

    if output_json:
        signals = []
        for eid, e in sorted(latest.items(), key=lambda x: x[1].get("created_at", "")):
            signals.append({
                "id": eid,
                "kind": e.get("kind"),
                "band": e.get("band"),
                "volume": e.get("volume", 0),
                "tick_count": e.get("tick_count", 0),
                "status": e.get("status"),
                "subsystem": e.get("subsystem"),
                "origin": e.get("origin"),
                "created_at": e.get("created_at"),
            })
        print(json.dumps({"command": "view", "signals": signals}, indent=2))
        return

    print(f"{'ID':<55} {'Kind':<8} {'Band':<10} {'Vol':>4} {'Ticks':>5} {'Status':<10} {'Subsystem':<18} {'Origin':<4}")
    print("-" * 160)
    for eid, e in sorted(latest.items(), key=lambda x: x[1].get("created_at", "")):
        print(f"{eid:<55} {e.get('kind','?'):<8} {e.get('band','?'):<10} "
              f"{e.get('volume',0):>4} {e.get('tick_count',0):>5} "
              f"{e.get('status','?'):<10} {e.get('subsystem','?'):<18} "
              f"{e.get('origin',''):<4}")


def cmd_compact(entries, signal_dir, dry_run=False):
    """Deduplicate JSONL files: keep latest per ID, archive originals."""
    if not entries:
        print("No entries to compact.")
        return

    raw_archive_dir = signal_dir / "raw"
    by_file = defaultdict(list)
    for e in entries:
        by_file[e["_source_file"]].append(e)

    total_before = 0
    total_after = 0

    for fname, file_entries in sorted(by_file.items()):
        with_id = [e for e in file_entries if e.get("id") or e.get("signal_id")]
        without_id = [e for e in file_entries if not (e.get("id") or e.get("signal_id"))]
        file_latest = latest_per_id(with_id)
        before = len(file_entries)
        after = len(file_latest) + len(without_id)
        total_before += before
        total_after += after

        if before == after:
            print(f"  {fname}: {before} entries — no duplicates, skip")
            continue

        suffix = f" (+{len(without_id)} non-signal preserved)" if without_id else ""
        print(f"  {fname}: {before} -> {after} entries ({before - after} duplicates removed){suffix}")

        if dry_run:
            continue

        fpath = signal_dir / fname

        raw_archive_dir.mkdir(parents=True, exist_ok=True)
        archive_name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{fname}"
        shutil.copy2(fpath, raw_archive_dir / archive_name)

        compacted = sorted(file_latest.values(), key=lambda x: x.get("created_at", ""))
        with open(fpath, "w") as f:
            for entry in without_id:
                clean = {k: v for k, v in entry.items() if not k.startswith("_")}
                f.write(json.dumps(clean) + "\n")
            for entry in compacted:
                clean = {k: v for k, v in entry.items() if not k.startswith("_")}
                f.write(json.dumps(clean) + "\n")

    print()
    print(f"  Total: {total_before} -> {total_after} entries")
    if dry_run:
        print("  (dry run — no files modified)")
    else:
        print(f"  Raw originals archived to: {raw_archive_dir}/")


def cmd_audit(entries, tz_config, output_json=False):
    """Identify zombie signals and structural issues."""
    latest = latest_per_id(entries)
    sg = signal_governance(tz_config)
    warrant_eligible = sg["warrant_eligible_kinds"]
    hearing_threshold = sg["hearing_threshold"]

    zombies = []
    ineligible_with_threshold = []
    decayed_below_hearing = []

    for eid, e in latest.items():
        if e.get("type") != "signal":
            continue
        status = e.get("status", "")
        if status in ("resolved", "dismissed", "warranted"):
            continue

        kind = e.get("kind", "")
        max_vol = e.get("max_volume", 100)
        threshold = (e.get("escalation") or {}).get("warrant_threshold")
        volume = e.get("volume", 0)

        if kind in warrant_eligible and threshold is not None and max_vol < threshold:
            zombies.append((eid, e, max_vol, threshold))

        if kind not in warrant_eligible and threshold is not None:
            ineligible_with_threshold.append((eid, e, kind, threshold))

        if status == "active" and volume < hearing_threshold:
            decayed_below_hearing.append((eid, e, volume))

    if output_json:
        result = {
            "command": "audit",
            "hearing_threshold": hearing_threshold,
            "warrant_eligible_kinds": list(warrant_eligible),
            "zombies": [
                {"id": eid, "max_volume": mv, "warrant_threshold": wt, "kind": e.get("kind")}
                for eid, e, mv, wt in zombies
            ],
            "ineligible_with_threshold": [
                {"id": eid, "kind": kind, "threshold": wt}
                for eid, e, kind, wt in ineligible_with_threshold
            ],
            "below_hearing": [
                {"id": eid, "volume": vol, "band": e.get("band"), "kind": e.get("kind")}
                for eid, e, vol in decayed_below_hearing
            ],
        }
        print(json.dumps(result, indent=2))
        return

    print("=" * 60)
    print("SIGNAL AUDIT")
    print("=" * 60)

    if zombies:
        print(f"\nZOMBIE SIGNALS ({len(zombies)}) — warrant-eligible but can never reach threshold:")
        for eid, e, mv, wt in zombies:
            print(f"  {eid}  max_volume={mv} < warrant_threshold={wt}  kind={e.get('kind')}")
    else:
        print("\nNo zombie signals found.")

    if ineligible_with_threshold:
        print(f"\nNON-ELIGIBLE WITH THRESHOLD ({len(ineligible_with_threshold)}) — kind not in warrant_eligible_kinds but threshold set:")
        for eid, e, kind, wt in ineligible_with_threshold:
            print(f"  {eid}  kind={kind}  threshold={wt}  (should be null)")
    else:
        print("\nNo structural threshold issues.")

    if decayed_below_hearing:
        print(f"\nBELOW HEARING THRESHOLD ({len(decayed_below_hearing)}) — active but inaudible (threshold={hearing_threshold}):")
        for eid, e, vol in decayed_below_hearing:
            print(f"  {eid}  volume={vol}  band={e.get('band')}  kind={e.get('kind')}")
    else:
        print("\nNo signals below hearing threshold.")


def main():
    parser = argparse.ArgumentParser(description="Signal store audit, metrics, and safe deduplication")
    parser.add_argument("command", choices=["metrics", "view", "compact", "audit"],
                        help="Operation to perform")
    parser.add_argument("--project-dir", default=None,
                        help="Project/zone root directory (auto-resolved if omitted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without modifying files")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Output structured JSON instead of human-readable text (metrics/view/audit)")
    args = parser.parse_args()

    try:
        zone_root = args.project_dir or resolve_zone_root()
    except Exception as e:
        if args.output_json:
            print(json.dumps({"error": str(e), "exit_code": 2}))
        else:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        signal_dir, tz_config = resolve_signal_dir(zone_root)
    except Exception as e:
        if args.output_json:
            print(json.dumps({"error": str(e), "exit_code": 2}))
        else:
            print(f"IO ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        entries = load_all_entries(signal_dir)
    except Exception as e:
        if args.output_json:
            print(json.dumps({"error": str(e), "exit_code": 3}))
        else:
            print(f"DATA ERROR: {e}", file=sys.stderr)
        sys.exit(3)

    if not entries and args.command != "metrics":
        if args.output_json:
            print(json.dumps({"error": f"No signal entries found in {signal_dir}", "exit_code": 1}))
        else:
            print(f"No signal entries found in {signal_dir}")
        sys.exit(1)

    if args.command == "metrics":
        cmd_metrics(entries, output_json=args.output_json)
    elif args.command == "view":
        cmd_view(entries, output_json=args.output_json)
    elif args.command == "compact":
        cmd_compact(entries, signal_dir, dry_run=args.dry_run)
    elif args.command == "audit":
        cmd_audit(entries, tz_config, output_json=args.output_json)


if __name__ == "__main__":
    main()
