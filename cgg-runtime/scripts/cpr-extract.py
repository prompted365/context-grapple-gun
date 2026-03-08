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


def load_existing_hashes(queue_file):
    """Load dedup hashes from existing queue.jsonl."""
    hashes = set()
    if not os.path.isfile(queue_file):
        return hashes
    for line in open(queue_file, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            h = d.get("dedup_hash", "")
            if h:
                hashes.add(h)
        except json.JSONDecodeError:
            continue
    return hashes


def find_governance_files(project_dir, excludes):
    """Find CLAUDE.md and MEMORY.md files, respecting .ticignore."""
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


def extract_cprs(project_dir, dry_run=False):
    """Main extraction: scan governance files, dedup, append to queue."""
    project_dir = os.path.abspath(project_dir)
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)
    queue_file = os.path.join(al_path, "cprs", "queue.jsonl")
    excludes = load_ticignore(project_dir)
    existing_hashes = load_existing_hashes(queue_file)
    gov_files = find_governance_files(project_dir, excludes)
    tic_count = get_tic_count(project_dir)
    topo = birth_topology(project_dir)
    now = datetime.now(timezone.utc).isoformat()

    new_entries = []

    for gov_file in gov_files:
        try:
            text = gov_file.read_text(encoding="utf-8")
        except Exception:
            continue

        for match in BLOCK_RE.finditer(text):
            block = parse_cpr_block(match.group(1))
            status = block.get("status", "")
            if status != "pending":
                continue

            source = block.get("source", "")
            lesson = block.get("lesson", "")
            if not source or not lesson:
                continue

            dedup_hash = hashlib.sha256(
                f"{source}:{lesson}".encode()
            ).hexdigest()[:16]
            if dedup_hash in existing_hashes:
                continue

            entry = {
                "type": "cpr",
                "id": f"cpr_{dedup_hash}",
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

    return new_entries


def main():
    parser = argparse.ArgumentParser(
        description="Extract pending CPR tags from governance files to queue.jsonl"
    )
    parser.add_argument(
        "--project-dir",
        default=None,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    project_dir = args.project_dir or resolve_zone_root()
    new_entries = extract_cprs(project_dir, dry_run=args.dry_run)

    if args.verbose:
        for e in new_entries:
            print(f"  {e['id']}: {e['lesson'][:60]}...")

    # Print count (consumed by hook wrapper)
    print(len(new_entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
