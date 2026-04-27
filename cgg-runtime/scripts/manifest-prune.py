#!/usr/bin/env python3
"""manifest-prune.py — sweep resolved entries out of active-manifest.jsonl.

Reads audit-logs/signals/active-manifest.jsonl, partitions by status:
  - keep: status in {active, acknowledged, working}
  - archive: everything else (resolved, dismissed, etc.)

Resolved entries are appended to audit-logs/signals/resolved-archive.jsonl
(no data loss — the resolution metadata is preserved in the archive).
The active-manifest is rewritten with only the kept entries.

Mechanizes the "Signal Resolution Writeback Atomicity (Dual-Surface)"
invariant from CLAUDE.md: cadence-driven sweep reconciliation. Designed
to be invoked from mogul-runner.sh before signal_scan, but safe to run
standalone at any time (idempotent — re-running on an already-pruned
manifest is a no-op).

Usage:
  python3 manifest-prune.py [--zone-root <path>] [--dry-run] [--quiet]

Exit codes:
  0 — pruned (or already clean — no-op)
  1 — error reading or writing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ACTIVE_STATUSES = {"active", "acknowledged", "working"}


def resolve_zone_root(start: str | None = None) -> Path:
    if start is None:
        start = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    cur = Path(start).resolve()
    while cur != cur.parent:
        if (cur / ".ticzone").exists():
            return cur
        cur = cur.parent
    return Path(start).resolve()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone-root", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    zone_root = resolve_zone_root(args.zone_root)
    manifest = zone_root / "audit-logs" / "signals" / "active-manifest.jsonl"
    archive = zone_root / "audit-logs" / "signals" / "resolved-archive.jsonl"

    if not manifest.exists():
        if not args.quiet:
            print(f"manifest-prune: no manifest at {manifest} — nothing to prune")
        return 0

    keep: list[dict] = []
    archived: list[dict] = []
    malformed = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if rec.get("status") in ACTIVE_STATUSES:
            keep.append(rec)
        else:
            archived.append(rec)

    if not archived:
        if not args.quiet:
            print(
                f"manifest-prune: clean — {len(keep)} active, 0 to prune"
                f"{f', {malformed} malformed lines preserved-as-empty' if malformed else ''}"
            )
        return 0

    if args.dry_run:
        print(
            f"manifest-prune: [DRY RUN] would prune {len(archived)} resolved entries; "
            f"{len(keep)} would remain active"
        )
        return 0

    # Append archived entries (atomic append).
    try:
        from lib.atomic_append import atomic_append_jsonl  # type: ignore

        for rec in archived:
            atomic_append_jsonl(str(archive), rec)
    except ImportError:
        with archive.open("a", encoding="utf-8") as f:
            for rec in archived:
                f.write(json.dumps(rec) + "\n")

    # Atomic replace of active-manifest with kept entries only.
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=".manifest-prune-", suffix=".jsonl", dir=str(manifest.parent)
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            for rec in keep:
                f.write(json.dumps(rec) + "\n")
        os.replace(tmp_path, manifest)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    if not args.quiet:
        print(
            f"manifest-prune: pruned {len(archived)} resolved entries to {archive.name}; "
            f"{len(keep)} remain active in manifest"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
