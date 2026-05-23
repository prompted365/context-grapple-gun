#!/usr/bin/env python3
"""
queue.jsonl drift audit — durable, idempotent observability script.

Born tic 280 from CogPR `cpr_queue_jsonl_drift_audit_primitive_tic278`
(promoted at /review tic 279). Purpose: continuous detection of two
queue-health failure modes that mislead RTCH harvest readers and
falsely surface overdue work:

  1. Genuinely-overdue active entries (status in {pending, extracted,
     enrichment_eligible, enrichment_in_progress, promotable} aged
     beyond a configurable threshold in tics since birth_tic)
  2. Terminal-state ids carrying raw-emission duplicates (pre-promotion
     rows that survived the latest-entry-per-id projection only because
     a peer reader aggregates raw lines)

The script is the queue-side complement to
`audit-logs/governance/memory-md-audit.py` — same structural shape
(project state -> classify -> emit structured findings), different
substrate (queue.jsonl rather than MEMORY.md).

Outputs JSON to
`audit-logs/governance/queue-drift-audit/<timestamp>[-tic-N].json` and
prints a compact summary to stdout. Per-finding structure:

    {
      "breach_class": "overdue_active" | "terminal_with_duplicates",
      "id": "<cogpr id>",
      "status": "<latest-entry status>",
      "birth_tic": <int|null>,
      "age_tics": <int|null>,
      "duplicate_count": <int>,
      "duplicate_statuses": [...],
      "note": "..."
    }

Composes with federation KI `Authoritative-set readers must read the
manifest, not aggregate raw emissions` (the projection IS the manifest
for queue.jsonl) and CGG KI `Terminal-State Valve Pattern` (read-side
projection complement). Read-only; never mutates queue.jsonl.

Exit codes:
  0 — healthy (no breaches)
  1 — discipline breach (overdue_active > 0 OR terminal_with_duplicates > 0)
  2 — fatal error reading queue.jsonl
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Script lives at <federation_root>/canonical_developer/context-grapple-gun/
#   cgg-runtime/scripts/queue-drift-audit.py
# .parent.parent.parent.parent.parent resolves the federation root path.
SCRIPT_PATH = Path(__file__).resolve()
FEDERATION_ROOT = SCRIPT_PATH.parent.parent.parent.parent.parent
QUEUE_FILE = FEDERATION_ROOT / "audit-logs" / "cprs" / "queue.jsonl"
OUT_DIR = FEDERATION_ROOT / "audit-logs" / "governance" / "queue-drift-audit"
TIC_FILE = FEDERATION_ROOT / "audit-logs" / "tics" / "current.json"

# Terminal statuses per CGG `Terminal-State Valve Pattern` doctrine.
TERMINAL_STATUSES = {
    "promoted",
    "deferred",
    "skipped",
    "absorbed",
    "rejected",
    "dismissed",
    "resolved",
    "superseded",
}

ACTIVE_STATUSES = {
    "pending",
    "extracted",
    "enrichment_eligible",
    "enrichment_in_progress",
    "promotable",
}

DEFAULT_OVERDUE_THRESHOLD_TICS = 20


def load_current_tic():
    """Return the current federation tic, or None if unresolvable."""
    try:
        data = json.loads(TIC_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    # Common shapes: {"current_tic": N} or {"counter_after": N} or {"tic": N}
    for key in ("current_tic", "counter_after", "tic", "global_counter"):
        val = data.get(key)
        if isinstance(val, int):
            return val
    return None


def load_queue_rows(queue_path):
    """Return list of parsed dicts (preserving append order). Empty on missing."""
    rows = []
    p = Path(queue_path)
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict):
            rows.append(d)
    return rows


def project_terminal_state(rows):
    """Apply latest-entry-per-id-wins projection over the raw rows.

    Returns:
      latest: dict id -> latest row (last-write-wins)
      per_id_rows: dict id -> list of all rows for that id, in append order
    """
    latest = {}
    per_id_rows = {}
    for row in rows:
        rid = row.get("id")
        if not rid:
            continue
        per_id_rows.setdefault(rid, []).append(row)
        latest[rid] = row
    return latest, per_id_rows


def audit(overdue_threshold=DEFAULT_OVERDUE_THRESHOLD_TICS, current_tic=None):
    if not QUEUE_FILE.exists():
        print(f"ERROR: {QUEUE_FILE} does not exist", file=sys.stderr)
        return None, 2

    if current_tic is None:
        current_tic = load_current_tic()

    rows = load_queue_rows(QUEUE_FILE)
    raw_row_count = len(rows)
    latest, per_id_rows = project_terminal_state(rows)

    findings = []
    overdue_active = []
    terminal_with_duplicates = []
    terminal_count = 0
    active_count = 0
    other_count = 0

    for rid, row in latest.items():
        status = row.get("status", "")
        birth_tic = row.get("birth_tic")
        all_rows = per_id_rows.get(rid, [])
        duplicate_count = max(0, len(all_rows) - 1)
        duplicate_statuses = (
            [r.get("status", "") for r in all_rows[:-1]] if duplicate_count > 0 else []
        )

        if status in TERMINAL_STATUSES:
            terminal_count += 1
            # Only flag terminal entries with duplicate rows whose presence
            # could mislead a raw-line reader (any duplicate count > 0).
            if duplicate_count > 0:
                f = {
                    "breach_class": "terminal_with_duplicates",
                    "id": rid,
                    "status": status,
                    "birth_tic": birth_tic,
                    "age_tics": None,
                    "duplicate_count": duplicate_count,
                    "duplicate_statuses": duplicate_statuses,
                    "note": (
                        "Terminal entry preceded by raw-emission row(s); "
                        "raw-line readers without terminal-state-valve "
                        "projection may surface stale pre-promotion state."
                    ),
                }
                findings.append(f)
                terminal_with_duplicates.append(f)
        elif status in ACTIVE_STATUSES:
            active_count += 1
            age_tics = None
            if isinstance(birth_tic, int) and isinstance(current_tic, int):
                age_tics = current_tic - birth_tic
            if age_tics is not None and age_tics >= overdue_threshold:
                f = {
                    "breach_class": "overdue_active",
                    "id": rid,
                    "status": status,
                    "birth_tic": birth_tic,
                    "age_tics": age_tics,
                    "duplicate_count": duplicate_count,
                    "duplicate_statuses": duplicate_statuses,
                    "note": (
                        f"Active entry aged {age_tics} tics since birth "
                        f"(threshold={overdue_threshold})."
                    ),
                }
                findings.append(f)
                overdue_active.append(f)
        else:
            other_count += 1

    breaches = []
    if overdue_active:
        breaches.append(f"overdue_active:{len(overdue_active)}")
    if terminal_with_duplicates:
        breaches.append(f"terminal_with_duplicates:{len(terminal_with_duplicates)}")

    report = {
        "tic_at_audit": current_tic,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "queue_path": str(QUEUE_FILE),
        "overdue_threshold_tics": overdue_threshold,
        "raw_row_count": raw_row_count,
        "unique_id_count": len(latest),
        "status_breakdown": {
            "terminal": terminal_count,
            "active": active_count,
            "other": other_count,
        },
        "duplicate_summary": {
            "ids_with_duplicates": sum(
                1 for r in per_id_rows.values() if len(r) > 1
            ),
            "total_duplicate_rows": sum(
                max(0, len(r) - 1) for r in per_id_rows.values()
            ),
        },
        "findings": findings,
        "breaches": breaches,
        "healthy": len(breaches) == 0,
    }

    exit_code = 0 if report["healthy"] else 1
    return report, exit_code


def main():
    parser = argparse.ArgumentParser(
        description="queue.jsonl drift audit — terminal-valve projection + overdue detection"
    )
    parser.add_argument(
        "--overdue-threshold",
        type=int,
        default=DEFAULT_OVERDUE_THRESHOLD_TICS,
        help=(
            f"Age threshold in tics for overdue_active classification "
            f"(default: {DEFAULT_OVERDUE_THRESHOLD_TICS})"
        ),
    )
    parser.add_argument(
        "--tic",
        type=int,
        default=None,
        help="Override current tic resolution (default: read from tics/current.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Print full JSON report to stdout (no file write)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout summary",
    )
    args = parser.parse_args()

    report, exit_code = audit(
        overdue_threshold=args.overdue_threshold,
        current_tic=args.tic,
    )
    if report is None:
        sys.exit(exit_code)

    if args.output_json:
        print(json.dumps(report, indent=2))
        sys.exit(exit_code)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = report["timestamp_utc"].replace(":", "").split(".")[0]
    tic_part = f"-tic-{report['tic_at_audit']}" if report.get("tic_at_audit") else ""
    out_file = OUT_DIR / f"{ts}{tic_part}.json"
    out_file.write_text(json.dumps(report, indent=2) + "\n")

    if not args.quiet:
        status = "HEALTHY" if report["healthy"] else "BREACH"
        print(
            f"[{status}] queue.jsonl: {report['raw_row_count']} raw rows "
            f"/ {report['unique_id_count']} unique ids"
        )
        sb = report["status_breakdown"]
        print(
            f"  status: terminal={sb['terminal']} active={sb['active']} other={sb['other']}"
        )
        ds = report["duplicate_summary"]
        print(
            f"  duplicates: {ds['ids_with_duplicates']} ids carry "
            f"{ds['total_duplicate_rows']} pre-projection rows"
        )
        print(
            f"  overdue threshold: {report['overdue_threshold_tics']} tics "
            f"(current_tic={report['tic_at_audit']})"
        )
        if report["breaches"]:
            print(f"  BREACHES: {', '.join(report['breaches'])}")
        print(f"  report written: {out_file}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
