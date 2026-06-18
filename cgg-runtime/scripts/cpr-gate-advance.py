#!/usr/bin/env python3
"""
CPR Gate Advance — deterministic reconciler for the tic_gated → enrichment_needed step.

WHY THIS EXISTS (the chicken-and-egg deadlock, tic 470):
  The CPR lifecycle is `extracted → tic_gated → enrichment_needed → … → promotable`.
  - `extracted → tic_gated` is owned by the cpr-stepper AGENT because it needs the
    model (verify-twin DEDUP). Correct — leave it with the agent.
  - `tic_gated → enrichment_needed` is purely MECHANICAL, but it had NO deterministic
    on-disk owner: the only writer was that same unscheduled, model-only agent, and
    its documented gate was "enrichment[] ≥1 entry" — an artifact the enrichment
    scanner only produces for HOLDING statuses (enrichment_needed/enrichment_eligible),
    i.e. AFTER the very transition the gate guards. A row could sit at `tic_gated`
    forever with an empty `enrichment[]` even though its tic-427 baseline
    `consolidated.json` already existed on disk.

  This reconciler is the deterministic owner of that mechanical step. The tic-427
  decoupling made the `<id>.consolidated.json` baseline the "evaluable PRE-enrichment"
  evidence; this script treats that baseline as the gate condition (not the full
  `enrichment[]` array, which is gathered downstream by cpr-enrichment-scanner.py once
  the row reaches `enrichment_needed`). It NEVER promotes and NEVER gathers evidence —
  it only advances the one mechanical status step, then the existing boot scanner
  (session-restore.sh, fired for holding states) does the evidence gather.

GATE (deterministic, no model):
  advance `tic_gated` → `enrichment_needed` IFF
    audit-logs/governance/enrichment/<id>.consolidated.json EXISTS
  (maturity was already enforced at the prior extracted→tic_gated gate by the stepper;
   this step does NOT re-check it.)

SAFETY:
  - Append/replace-in-place under flock (mirrors cpr-enrichment-scanner.py writeback).
  - Only ever touches rows whose CURRENT status is exactly `tic_gated`.
  - Stamps a transition breadcrumb (prior_status, gate_advanced_at_tic, gate_advanced_by).
  - Idempotent: a second run finds no `tic_gated`-with-baseline rows and writes nothing.
  - Never writes CLAUDE.md / MEMORY.md / ledger. Never promotes.

Usage:
  python3 cpr-gate-advance.py --project-dir /path/to/zone
  python3 cpr-gate-advance.py --dry-run
  python3 cpr-gate-advance.py --quiet      # print only the count advanced
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path


def load_queue(queue_path):
    """Latest-entry-per-id-wins projection of the append-only queue."""
    entries = {}
    p = Path(queue_path)
    if not p.exists():
        return entries
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            eid = d.get("id", "")
            if eid:
                entries[eid] = d
        except json.JSONDecodeError:
            continue
    return entries


def resolve_current_tic(al_path):
    """Count counted tic events to resolve current tic (mirrors cadence-ops/scanner)."""
    tic_dir = Path(al_path) / "tics"
    if not tic_dir.is_dir():
        return -1
    total = 0
    for f in sorted(tic_dir.glob("*.jsonl")):
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if o.get("type") == "tic" and o.get("count_mode", "counted") == "counted":
                    total += 1
        except OSError:
            return -1
    return total


def find_advanceable(queue_entries, enrichment_dir):
    """tic_gated rows whose tic-427 baseline consolidated.json exists on disk."""
    advanceable = []
    for eid, entry in queue_entries.items():
        if entry.get("status") != "tic_gated":
            continue
        baseline = Path(enrichment_dir) / f"{eid}.consolidated.json"
        if baseline.exists():
            advanceable.append((eid, entry, str(baseline)))
    return advanceable


def writeback_in_place(queue_path, update_map):
    """Replace matching id rows in queue.jsonl under flock (no duplicate append)."""
    import fcntl
    p = Path(queue_path)
    os.makedirs(os.path.dirname(queue_path), exist_ok=True)
    lockfile = queue_path + ".lock"
    with open(lockfile, "w") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
            new_lines = []
            replaced = set()
            for line in lines:
                s = line.strip()
                if not s:
                    new_lines.append(line)
                    continue
                try:
                    d = json.loads(s)
                    eid = d.get("id", "")
                    if eid in update_map:
                        new_lines.append(json.dumps(update_map[eid], separators=(",", ":"), default=str))
                        replaced.add(eid)
                    else:
                        new_lines.append(line)
                except json.JSONDecodeError:
                    new_lines.append(line)
            for eid, entry in update_map.items():
                if eid not in replaced:
                    new_lines.append(json.dumps(entry, separators=(",", ":"), default=str))
            p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def advance_gated(project_dir, dry_run=False, quiet=False):
    project_dir = os.path.abspath(project_dir)
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)
    queue_path = os.path.join(al_path, "cprs", "queue.jsonl")
    enrichment_dir = Path(al_path) / "governance" / "enrichment"

    queue = load_queue(queue_path)
    advanceable = find_advanceable(queue, enrichment_dir)

    if not advanceable:
        if not quiet:
            print("0")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    current_tic = resolve_current_tic(al_path)
    update_map = {}
    for eid, entry, baseline in advanceable:
        updated = {**entry}
        updated["status"] = "enrichment_needed"
        updated["prior_status"] = "tic_gated"
        updated["gate_advanced_at_tic"] = current_tic
        updated["gate_advanced_by"] = "cpr-gate-advance"
        updated["gate_advance_reason"] = "tic-427 baseline consolidated present (pre-enrichment evidence); deterministic tic_gated->enrichment_needed reconcile"
        updated["updated_at"] = now
        update_map[eid] = updated
        if not quiet:
            print(f"  {eid}: tic_gated -> enrichment_needed (baseline: {os.path.basename(baseline)})")

    if not dry_run:
        writeback_in_place(queue_path, update_map)

    if not quiet:
        verb = "would advance" if dry_run else "advanced"
        print(f"{len(update_map)}")
        sys.stderr.write(f"[cpr-gate-advance] {verb} {len(update_map)} tic_gated -> enrichment_needed\n")
    return len(update_map)


def main():
    ap = argparse.ArgumentParser(description="CPR Gate Advance — deterministic tic_gated->enrichment_needed reconciler")
    ap.add_argument("--project-dir", default=None, help="Zone root (auto-resolved if omitted)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="print only the count advanced")
    args = ap.parse_args()
    project_dir = args.project_dir or resolve_zone_root()
    advance_gated(project_dir, dry_run=args.dry_run, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
