#!/usr/bin/env python3
"""
Expression Tracker — persist survival-backed lesson participation.

Consumes the session tracker (written by the expression verifier hook)
and persists tiered participation data to the zone audit surface.

Three tiers of evidence:
  1. retrieved    — lesson was pulled into candidate set
  2. survived     — lesson remained in active lineup through generation
  3. direct_hits  — verifier found lexical evidence in output

This script does NOT model mature methylation. It records what we
actually know: survival-backed participation.

Output: append-only JSONL at $ZONE_ROOT/audit-logs/lesson-expression/participation.jsonl
Latest-entry-per-ID-wins semantics (same as signal store).

Usage:
    python3 expression-tracker.py --update           # consume tracker, update store
    python3 expression-tracker.py --status            # print current participation state
    python3 expression-tracker.py --status --json     # structured output
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, birth_topology


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PARTICIPATION_DIR = "lesson-expression"
PARTICIPATION_FILE = "participation.jsonl"


def participation_store_path(al_path: str) -> Path:
    """Resolve the participation JSONL store path."""
    return Path(al_path) / PARTICIPATION_DIR / PARTICIPATION_FILE


def resolve_tracker_path(zone_root: str) -> Path:
    """Resolve the session tracker written by the expression verifier hook.

    Uses CLAUDE_PROJECT_DIR-derived key for the tmp path, matching
    the verifier hook's own resolution. Zone-agnostic: the project key
    is derived from the zone root, not hardcoded.
    """
    uid = os.getuid()
    # Derive project key the same way Claude Code does:
    # replace / with - in the project dir path
    project_key = zone_root.replace("/", "-").lstrip("-")
    return Path(f"/private/tmp/claude-{uid}/{project_key}/lessons/tracker.json")


def resolve_manifest_path(zone_root: str) -> Path:
    """Resolve the lesson manifest written by the retriever at SessionStart."""
    uid = os.getuid()
    project_key = zone_root.replace("/", "-").lstrip("-")
    return Path(f"/private/tmp/claude-{uid}/{project_key}/lessons/active.json")


# ---------------------------------------------------------------------------
# Store operations (append-only JSONL, latest-entry-per-ID-wins)
# ---------------------------------------------------------------------------

def load_participation_store(store_path: Path) -> dict:
    """Load current participation state. Returns {lesson_id: entry}."""
    entries: dict = {}
    if not store_path.is_file():
        return entries
    try:
        for line in store_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                lid = d.get("lesson_id", "")
                if lid:
                    entries[lid] = d
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return entries


def append_participation(store_path: Path, entries: list[dict]) -> None:
    """Append participation entries to the JSONL store."""
    store_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from lib.atomic_append import atomic_append_jsonl
        for entry in entries:
            atomic_append_jsonl(str(store_path), entry)
    except ImportError:
        import fcntl
        lockfile = str(store_path) + ".lock"
        with open(lockfile, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                with open(store_path, "a", encoding="utf-8") as f:
                    for entry in entries:
                        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Update: consume session tracker + manifest
# ---------------------------------------------------------------------------

def update_from_session(zone_root: str, tic_count: int | None = None) -> dict:
    """Consume the session tracker and manifest, update participation store.

    Returns summary of what was updated.
    """
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    store_path = participation_store_path(al_path)
    tracker_path = resolve_tracker_path(zone_root)
    manifest_path = resolve_manifest_path(zone_root)

    current_tic = tic_count or 0
    topo = birth_topology(zone_root)
    now = datetime.now(timezone.utc).isoformat()

    # Load existing state
    store = load_participation_store(store_path)

    # Load manifest (tells us what was retrieved this session)
    manifest_lessons = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for lesson in manifest.get("lessons", []):
                title = lesson.get("title", "")
                if title:
                    manifest_lessons[title] = lesson
        except (json.JSONDecodeError, OSError):
            pass

    # Load tracker (tells us what was expressed this session)
    tracker = {}
    if tracker_path.is_file():
        try:
            tracker = json.loads(tracker_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    expressed_lessons = tracker.get("expressed_lessons", {})
    write_count = tracker.get("write_count", 0)

    if not manifest_lessons and not expressed_lessons:
        return {"updated": 0, "reason": "no session data to consume"}

    # Build participation updates
    new_entries = []

    # Every lesson in the manifest was retrieved AND survived into the lineup
    # (the manifest only contains lessons that made the final cut)
    for title, lesson_info in manifest_lessons.items():
        # Use title as ID since we don't have doc IDs at this layer
        lid = title

        prev = store.get(lid, {})
        retrieval_count = prev.get("retrieval_count", 0) + 1

        # If writes happened while this lesson was in the lineup,
        # it survived through generation — that's participation
        survival_count = prev.get("survival_count", 0)
        if write_count > 0:
            survival_count += 1

        # Direct expression hits from the verifier
        direct_hits = prev.get("direct_expression_hits", 0)
        session_hits = expressed_lessons.get(title, 0)
        direct_hits += session_hits

        entry = {
            "lesson_id": lid,
            "subsystem": lesson_info.get("subsystem", ""),
            "band": lesson_info.get("band", "COGNITIVE"),
            "retrieval_count": retrieval_count,
            "survival_count": survival_count,
            "direct_expression_hits": direct_hits,
            "last_survived_tic": current_tic if write_count > 0 else prev.get("last_survived_tic", 0),
            "last_retrieved_tic": current_tic,
            "retrieved_rung": topo["birth_rung"],
            "updated_at": now,
        }
        new_entries.append(entry)

    # Append to store
    if new_entries:
        append_participation(store_path, new_entries)

    # Clean up consumed tracker (prevents double-counting)
    if tracker_path.is_file():
        try:
            tracker_path.unlink()
        except OSError:
            pass

    return {
        "updated": len(new_entries),
        "retrieved": len(manifest_lessons),
        "expressed": len(expressed_lessons),
        "tic": current_tic,
        "store_path": str(store_path),
    }


# ---------------------------------------------------------------------------
# Status: read current participation state
# ---------------------------------------------------------------------------

def format_status(store: dict) -> str:
    """Format participation state as human-readable text."""
    if not store:
        return "No participation data recorded."

    lines = ["LESSON PARTICIPATION", "=" * 50]
    # Sort by survival_count descending
    sorted_entries = sorted(store.values(),
                            key=lambda e: e.get("survival_count", 0),
                            reverse=True)
    for entry in sorted_entries:
        lid = entry.get("lesson_id", "?")[:60]
        r = entry.get("retrieval_count", 0)
        s = entry.get("survival_count", 0)
        d = entry.get("direct_expression_hits", 0)
        last = entry.get("last_survived_tic", 0)
        lines.append(f"  {lid}")
        lines.append(f"    retrieved={r}  survived={s}  direct_hits={d}  last_tic={last}")

    lines.append("")
    lines.append(f"Total lessons tracked: {len(store)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Expression Tracker — persist survival-backed lesson participation"
    )
    parser.add_argument("--update", action="store_true",
                        help="Consume session tracker and update participation store")
    parser.add_argument("--status", action="store_true",
                        help="Print current participation state")
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--tic-count", type=int, default=None,
                        help="Current tic count for anchoring")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Output structured JSON")
    args = parser.parse_args()

    zone_root = args.project_dir or resolve_zone_root()
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)

    if args.update:
        result = update_from_session(zone_root, tic_count=args.tic_count)
        if args.output_json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("updated", 0) > 0:
                print(f"Updated {result['updated']} lesson participation records.")
                print(f"  Retrieved: {result.get('retrieved', 0)}")
                print(f"  Expressed: {result.get('expressed', 0)}")
                print(f"  Tic: {result.get('tic', '?')}")
            else:
                print(f"No updates: {result.get('reason', 'no data')}")

    elif args.status:
        store_path = participation_store_path(al_path)
        store = load_participation_store(store_path)
        if args.output_json:
            print(json.dumps({"lessons": list(store.values()),
                              "count": len(store)}, indent=2))
        else:
            print(format_status(store))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
