#!/usr/bin/env python3
"""
CPR queue extractor — scans governance files for pending --agnostic-candidate
blocks and appends new entries to audit-logs/cprs/queue.jsonl.

Block-aware parsing (not line grep). Dedup by sha256(source:lesson)[:16].

Usage:
  python3 scripts/cpr-extract.py --project-dir /path/to/project
  python3 scripts/cpr-extract.py --project-dir /path/to/project --dry-run
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, birth_topology


BLOCK_RE = re.compile(
    r"<!-- --agnostic-candidate\s*\n(.*?)\n\s*-->",
    re.DOTALL,
)


def parse_cpr_block(block_text):
    """Parse YAML-ish CPR block into dict."""
    result = {}
    lines = block_text.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if val == "":
            # List value — collect indented items
            items = []
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line.startswith("- "):
                    item = next_line[2:].strip()
                    if len(item) >= 2 and item[0] == item[-1] and item[0] in ('"', "'"):
                        item = item[1:-1]
                    items.append(item)
                    i += 1
                elif not next_line:
                    i += 1
                else:
                    break
            result[key] = items
            continue
        # Strip quotes
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        result[key] = val
        i += 1
    return result


def load_ticignore(project_dir):
    """Load .ticignore exclusions. Returns set of directory names."""
    excludes = {".git"}
    ticignore = os.path.join(project_dir, ".ticignore")
    if os.path.isfile(ticignore):
        for line in open(ticignore, encoding="utf-8"):
            line = line.split("#")[0].strip().rstrip("/")
            if not line:
                continue
            # Skip glob patterns — only directory names for governance scan
            if "*" in line or "?" in line:
                continue
            excludes.add(line)
    else:
        excludes.update(["vendor", "node_modules", ".claude/skills"])
    return excludes


def should_exclude(rel_path, excludes):
    """Check if a path should be excluded based on .ticignore.

    Patterns are treated as path prefixes from the project root.
    'vendor' matches vendor/* but not nested some_module/vendor/*.
    'vendor/ruvector' matches vendor/ruvector/* only.
    '.git' is special-cased (always matches as a component anywhere).
    """
    rel_str = str(Path(rel_path))
    for exc in excludes:
        # .git is always excluded wherever it appears
        if exc == ".git" and ".git" in Path(rel_path).parts:
            return True
        # Prefix match from project root
        if rel_str == exc or rel_str.startswith(exc + "/"):
            return True
    return False


# Terminal status set — once a CPR id has reached one of these, the extractor
# must NOT append a new "extracted" row for it. Doing so re-surfaces an already
# settled CPR into the bench packet (CogPR-162 schema-implicit territory).
TERMINAL_STATUSES = frozenset({
    "promoted", "absorbed", "superseded", "rejected",
    "deferred", "dismissed", "resolved", "skipped",
})


def load_existing_state(queue_file):
    """Load dedup hashes AND terminal ids from existing queue.jsonl.

    Returns (hashes, terminal_ids):
      hashes       — set of all dedup_hash values seen (for source:lesson dedup)
      terminal_ids — set of ids whose latest entry is in a terminal status

    JSONL is append-only; latest entry per id wins. A CPR may appear with
    status=extracted, then later status=promoted; the second row is the
    canonical state. Re-extracting after terminal would inject a stale
    "extracted" row that bench-packet-prep would prefer over the terminal.
    """
    hashes = set()
    latest_status_by_id = {}
    if not os.path.isfile(queue_file):
        return hashes, set()
    for line in open(queue_file, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        h = d.get("dedup_hash", "")
        if h:
            hashes.add(h)
        eid = d.get("id", "")
        if eid:
            # JSONL append-only: each subsequent occurrence overwrites
            latest_status_by_id[eid] = d.get("status", "")
    terminal_ids = {
        eid for eid, status in latest_status_by_id.items()
        if status in TERMINAL_STATUSES
    }
    return hashes, terminal_ids


def find_governance_files(project_dir, excludes, plan_file=None):
    """Find CLAUDE.md and MEMORY.md files, respecting .ticignore.

    If plan_file is given, append that single plan file to the scan set —
    scope is the ACTIVE plan only (caller is responsible for selecting it).
    """
    gov_files = []
    for name in ["CLAUDE.md", "MEMORY.md"]:
        for f in Path(project_dir).rglob(name):
            try:
                rel = f.relative_to(project_dir)
            except ValueError:
                continue
            if not should_exclude(rel, excludes):
                gov_files.append(f)

    # Also check auto-memory (gitignored but governance-visible)
    project_key = project_dir.replace("/", "-")
    auto_memory = (
        Path.home() / ".claude" / "projects" / project_key / "memory" / "MEMORY.md"
    )
    if auto_memory.is_file():
        # Avoid double-counting if auto_memory is somehow also in project_dir
        if auto_memory not in gov_files:
            gov_files.append(auto_memory)

    # Active plan file (optional) — caller-selected via session-restore.sh's
    # LATEST_PLAN discovery. Never scans the whole plans directory.
    if plan_file:
        p = Path(plan_file)
        if p.is_file() and p not in gov_files:
            gov_files.append(p)

    return gov_files


def get_tic_count(project_dir):
    """Get current project tic count from audit-logs/tics/*.jsonl."""
    tic_count = 0
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)
    tic_dir = os.path.join(al_path, "tics")
    if not os.path.isdir(tic_dir):
        return tic_count
    for f in sorted(Path(tic_dir).glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if d.get("type") == "tic":
                    tic_count += 1
            except (json.JSONDecodeError, TypeError):
                continue
    return tic_count


def extract_cprs(project_dir, dry_run=False, plan_file=None, anomaly_threshold=0.5):
    """Main extraction: scan governance files, dedup, append to queue.

    Schema gate is intentionally narrow — status=="pending" AND source AND
    lesson must all be present. Widening the accepted schema (title/evidence
    or lesson-only) is a doctrine question that must route through /review,
    not be silently expanded here. (See architect's Patch E direction.)

    Dedup is two-axis:
      1. dedup_hash (sha256(source:lesson)[:16]) — same content, same row
      2. explicit/derived id in TERMINAL_STATUSES — already-settled CPR
    Either match skips extraction.

    Anomaly report fires to stderr when extracted < blocks_found * threshold.
    """
    project_dir = os.path.abspath(project_dir)
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)
    queue_file = os.path.join(al_path, "cprs", "queue.jsonl")
    excludes = load_ticignore(project_dir)
    existing_hashes, terminal_ids = load_existing_state(queue_file)
    gov_files = find_governance_files(project_dir, excludes, plan_file=plan_file)
    tic_count = get_tic_count(project_dir)
    topo = birth_topology(project_dir)
    now = datetime.now(timezone.utc).isoformat()

    new_entries = []
    counters = {
        "blocks_found": 0,
        "blocks_extracted": 0,
        "skipped_status_not_pending": 0,
        "skipped_missing_source_or_lesson": 0,
        "skipped_dedup_hash_match": 0,
        "skipped_terminal_id_match": 0,
    }

    for gov_file in gov_files:
        try:
            text = gov_file.read_text(encoding="utf-8")
        except Exception:
            continue

        for match in BLOCK_RE.finditer(text):
            counters["blocks_found"] += 1
            block = parse_cpr_block(match.group(1))
            status = block.get("status", "")
            if status != "pending":
                counters["skipped_status_not_pending"] += 1
                continue

            source = block.get("source", "")
            lesson = block.get("lesson", "")
            if not source or not lesson:
                counters["skipped_missing_source_or_lesson"] += 1
                continue

            dedup_hash = hashlib.sha256(
                f"{source}:{lesson}".encode()
            ).hexdigest()[:16]
            if dedup_hash in existing_hashes:
                counters["skipped_dedup_hash_match"] += 1
                continue

            # Preserve explicit author-supplied id when present; otherwise
            # derive from dedup hash. Explicit ids carry author intent
            # (e.g., "CogPR-186") and were previously silently overwritten.
            explicit_id = str(block.get("id", "")).strip()
            entry_id = explicit_id if explicit_id else f"cpr_{dedup_hash}"

            # Terminal-state valve: if this id has already reached a terminal
            # status in the queue, do not append a new extracted row. Doing so
            # would re-surface a settled CPR into bench-packet (the bug minted
            # as cpr_bench_packet_must_filter_by_latest_non_extracted_status_tic183).
            if entry_id in terminal_ids:
                counters["skipped_terminal_id_match"] += 1
                continue

            entry = {
                "type": "cpr",
                "id": entry_id,
                "id_origin": "explicit" if explicit_id else "hash_derived",
                "dedup_hash": dedup_hash,
                "status": "extracted",
                "lesson": lesson,
                "source": source,
                "source_date": block.get("source_date", ""),
                "band": block.get("band", "COGNITIVE"),
                "motivation_layer": block.get("motivation_layer", "COGNITIVE"),
                "subsystem": block.get("subsystem", ""),
                "recommended_scopes": block.get("recommended_scopes", []),
                "rationale": block.get("rationale", ""),
                "review_hints": block.get("review_hints", ""),
                "birth_tic": block.get("birth_tic", tic_count),
                "posture": block.get("posture", ""),
                "extracted_at": now,
                "extracted_by": "cpr-extract-hook",
                "source_file": str(gov_file),
                "birth_rung": topo["birth_rung"],
                "birth_scope_path": topo["birth_scope_path"],
            }

            # Parse birth_tic as int if it came from block as string
            try:
                entry["birth_tic"] = int(entry["birth_tic"])
            except (ValueError, TypeError):
                entry["birth_tic"] = tic_count

            new_entries.append(entry)
            existing_hashes.add(dedup_hash)
            counters["blocks_extracted"] += 1

    if new_entries and not dry_run:
        os.makedirs(os.path.dirname(queue_file), exist_ok=True)
        try:
            from lib.atomic_append import atomic_append_jsonl
            for entry in new_entries:
                atomic_append_jsonl(queue_file, entry)
        except ImportError:
            import fcntl
            lockfile = queue_file + ".lock"
            with open(lockfile, "w") as lf:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
                try:
                    with open(queue_file, "a", encoding="utf-8") as f:
                        for entry in new_entries:
                            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
                finally:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    # Anomaly self-reporting (CogPR-150). Fires to stderr when blocks_found
    # is materially greater than blocks_extracted. The default 0.5 threshold
    # is intentionally permissive — most non-extractions are legitimate
    # (status not pending, missing schema, dedup match). The signal exists
    # so silent zero-extraction at scale becomes visible.
    bf = counters["blocks_found"]
    bx = counters["blocks_extracted"]
    if bf > 0 and bx < bf * (1.0 - anomaly_threshold):
        print(
            f"cpr-extract anomaly: blocks_found={bf} blocks_extracted={bx} "
            f"counters={json.dumps(counters)}",
            file=sys.stderr,
        )

    return new_entries, counters


def main():
    parser = argparse.ArgumentParser(
        description="Extract pending CPR tags from governance files to queue.jsonl"
    )
    parser.add_argument(
        "--project-dir",
        default=None,
    )
    parser.add_argument(
        "--plan-file",
        default=None,
        help="Optional absolute path to the active plan file (single file). "
             "Session-restore.sh selects this via LATEST_PLAN discovery.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    project_dir = args.project_dir or resolve_zone_root()
    new_entries, counters = extract_cprs(
        project_dir,
        dry_run=args.dry_run,
        plan_file=args.plan_file,
    )

    if args.verbose:
        for e in new_entries:
            origin = e.get("id_origin", "?")
            print(f"  {e['id']} [{origin}]: {e['lesson'][:60]}...")
        print(f"  counters: {json.dumps(counters)}", file=sys.stderr)

    # Print count (consumed by hook wrapper)
    print(len(new_entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
