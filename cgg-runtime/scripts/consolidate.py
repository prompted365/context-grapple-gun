#!/usr/bin/env python3
"""
consolidate.py — Context Consolidation Pipeline

Concatenates any file surface into a single LLM-consumable indexed markdown
dump with smart delimiters, file index, and grep patterns.

Works with: local dirs, glob patterns, git repos, git diff ranges.

Usage:
    python3 consolidate.py --targets ./dir1 ./dir2/*.md --output dump.md
    python3 consolidate.py --git-repo https://github.com/org/repo --output dump.md
    python3 consolidate.py --git-diff main..HEAD --output dump.md
    python3 consolidate.py --targets ./specs/ --harpoon --output dump.md
    python3 consolidate.py --targets ./specs/ --arena arena-spec.yaml --output dump.md
    python3 consolidate.py --scan  (dry run — show what would be included)

Exit codes: 0=success, 1=error, 2=no files found.
"""

import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

DEFAULT_INCLUDE = {
    ".md", ".py", ".yaml", ".yml", ".json", ".jsonl", ".txt", ".sh",
    ".ts", ".js", ".tsx", ".jsx", ".toml", ".cfg", ".html", ".css",
    ".sql", ".rs", ".go", ".java", ".rb", ".php", ".swift", ".kt",
    ".c", ".cpp", ".h", ".hpp", ".r", ".jl", ".lua", ".zig",
    ".env.example", ".gitignore", ".dockerignore", "Dockerfile",
    "Makefile", "Cargo.toml", "package.json", "pyproject.toml",
    "tsconfig.json", "go.mod", "go.sum", "Gemfile", "requirements.txt",
}

DEFAULT_EXCLUDE_DIRS = {
    "__pycache__", "node_modules", ".git", ".svn", ".hg",
    "dist", "build", ".next", ".nuxt", "target", "out",
    ".tox", ".mypy_cache", ".pytest_cache", "venv", ".venv",
    "egg-info", ".eggs",
}

DEFAULT_EXCLUDE_FILES = {
    "*.pyc", "*.pyo", "*.lock", "*.min.js", "*.min.css",
    "*.map", "*.wasm", "*.o", "*.so", "*.dylib", "*.dll",
    "*.exe", "*.bin", "*.dat", "*.db", "*.sqlite",
    "*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.ico",
    "*.svg", "*.webp", "*.mp3", "*.mp4", "*.wav", "*.avi",
    "*.mov", "*.mkv", "*.webm", "*.pdf", "*.zip", "*.tar",
    "*.gz", "*.bz2", "*.xz", "*.rar", "*.7z",
}

# Truncation mode defaults (overridden by --mode flag)
# Modes: full (default, no truncation), efficient (chunked/sparse), head, tail, split
TRUNCATION_MODE = "full"      # default: include entire file
MAX_FILE_SIZE = 0             # 0 = no limit in full mode
MAX_JSONL_LINES = 0           # 0 = no limit in full mode
MAX_TOTAL_LINES = 0           # 0 = no limit in full mode

# Per-mode limits (applied when mode != "full")
MODE_LIMITS = {
    "efficient": {"max_file_size": 500_000, "max_lines": 300, "jsonl_lines": 50},
    "head":      {"max_file_size": 500_000, "max_lines": 200, "jsonl_lines": 50},
    "tail":      {"max_file_size": 500_000, "max_lines": 200, "jsonl_lines": 50},
    "split":     {"max_file_size": 500_000, "max_lines": 200, "jsonl_lines": 50},  # 100 head + 100 tail
}

BINARY_MAGIC = {
    b'\x89PNG', b'\xff\xd8\xff', b'GIF8', b'PK\x03\x04',
    b'\x7fELF', b'\xfe\xed\xfa', b'\xca\xfe\xba\xbe',
    b'\x1f\x8b', b'BZ', b'\xfd7zXZ', b'Rar!',
    b'\x00\x00\x01\x00',  # ICO
    b'ID3',  # MP3
    b'\x00\x00\x00',  # MP4/MOV
}


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------

def is_binary(path: str) -> bool:
    """Check if file is binary using magic bytes + null byte heuristic."""
    try:
        with open(path, "rb") as f:
            header = f.read(16)
        if not header:
            return False
        for magic in BINARY_MAGIC:
            if header.startswith(magic):
                return True
        # Null byte heuristic
        with open(path, "rb") as f:
            chunk = f.read(8192)
        if b'\x00' in chunk:
            return True
        return False
    except (OSError, PermissionError):
        return True


# ---------------------------------------------------------------------------
# File classification
# ---------------------------------------------------------------------------

CATEGORY_MAP = {
    # By directory name
    "autonomous_kernel": "SPEC",
    "ak_control_room": "AKCR",
    "scripts": "RUNTIME",
    "hooks": "HOOK",
    "skills": "SKILL",
    "agents": "AGENT",
    "publications": "PUBLICATION",
    "audit-logs": "AUDIT",
    "agent-mailboxes": "MEMO",
    "tests": "TEST",
    "docs": "DOC",
    "src": "SOURCE",
    "lib": "LIB",
    "config": "CONFIG",
}

EXT_CATEGORY = {
    ".py": "SCRIPT", ".sh": "SCRIPT", ".js": "SCRIPT", ".ts": "SCRIPT",
    ".md": "DOC", ".txt": "DOC", ".rst": "DOC",
    ".yaml": "CONFIG", ".yml": "CONFIG", ".toml": "CONFIG",
    ".json": "DATA", ".jsonl": "DATA",
    ".html": "WEB", ".css": "WEB",
    ".sql": "SCHEMA",
}


def classify_file(rel_path: str) -> str:
    """Classify a file into a category based on path and extension."""
    parts = rel_path.split(os.sep)
    # Check directory-based classification first
    for part in parts:
        if part in CATEGORY_MAP:
            return CATEGORY_MAP[part]
    # Fall back to extension
    ext = os.path.splitext(rel_path)[1].lower()
    return EXT_CATEGORY.get(ext, "OTHER")


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

def should_exclude_dir(dirname: str) -> bool:
    return dirname in DEFAULT_EXCLUDE_DIRS


def should_exclude_file(filename: str) -> bool:
    for pattern in DEFAULT_EXCLUDE_FILES:
        if pattern.startswith("*"):
            if filename.endswith(pattern[1:]):
                return True
        elif filename == pattern:
            return True
    return False


def should_include_ext(filename: str) -> bool:
    """Check if file extension is in include list. Also include extensionless known files."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in DEFAULT_INCLUDE:
        return True
    # Known extensionless files
    if filename in ("Dockerfile", "Makefile", "Gemfile", "Procfile", "Rakefile",
                     ".gitignore", ".dockerignore", ".env.example"):
        return True
    return False


def collect_from_directory(dirpath: str, base_dir: str = None) -> list:
    """Walk a directory and collect non-binary files."""
    if base_dir is None:
        base_dir = dirpath
    files = []
    for root, dirs, filenames in os.walk(dirpath):
        # Filter excluded directories in-place
        dirs[:] = [d for d in dirs if not should_exclude_dir(d)]
        dirs.sort()
        for fn in sorted(filenames):
            if should_exclude_file(fn):
                continue
            if not should_include_ext(fn):
                continue
            full = os.path.join(root, fn)
            if is_binary(full):
                continue
            rel = os.path.relpath(full, base_dir)
            files.append((rel, full))
    return files


def collect_from_glob(pattern: str, base_dir: str = None) -> list:
    """Expand a glob pattern and collect matching non-binary files."""
    if base_dir is None:
        base_dir = os.getcwd()
    files = []
    for full in sorted(glob.glob(pattern, recursive=True)):
        if os.path.isdir(full):
            files.extend(collect_from_directory(full, base_dir))
            continue
        if not os.path.isfile(full):
            continue
        fn = os.path.basename(full)
        if should_exclude_file(fn):
            continue
        if is_binary(full):
            continue
        rel = os.path.relpath(full, base_dir)
        files.append((rel, full))
    return files


def collect_from_git_repo(url: str) -> tuple:
    """Clone a git repo to temp dir, collect files, return (files, tmpdir, commit_hash)."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    tmpdir = os.path.join(tempfile.gettempdir(), f"consolidate-{url_hash}")
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    subprocess.run(["git", "clone", "--depth", "1", url, tmpdir],
                   capture_output=True, check=True, timeout=120)
    # Get commit hash
    result = subprocess.run(["git", "-C", tmpdir, "rev-parse", "HEAD"],
                            capture_output=True, text=True)
    commit = result.stdout.strip()[:12] if result.returncode == 0 else "unknown"
    files = collect_from_directory(tmpdir, tmpdir)
    return files, tmpdir, commit


def collect_from_git_diff(diff_range: str, repo_dir: str = None) -> list:
    """Collect files changed in a git diff range."""
    if repo_dir is None:
        repo_dir = os.getcwd()
    result = subprocess.run(
        ["git", "-C", repo_dir, "diff", "--name-only", diff_range],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print(f"Error: git diff failed: {result.stderr}", file=sys.stderr)
        return []
    files = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        full = os.path.join(repo_dir, line)
        if not os.path.isfile(full):
            continue
        if is_binary(full):
            continue
        files.append((line, full))
    return files


# ---------------------------------------------------------------------------
# Dump generation
# ---------------------------------------------------------------------------

def read_file_content(full_path: str, rel_path: str, mode: str = "full") -> tuple:
    """Read file content with mode-aware truncation. Returns (content, total_lines, truncated).

    Modes:
        full      — entire file, no truncation (default)
        efficient — chunked: first N lines + "..." + last 20 lines for large files
        head      — first N lines only
        tail      — last N lines only
        split     — first N/2 lines + "..." + last N/2 lines
    """
    try:
        size = os.path.getsize(full_path)
    except OSError:
        return "(error reading file)", 0, False

    is_jsonl = rel_path.endswith(".jsonl")
    limits = MODE_LIMITS.get(mode, {})
    max_size = limits.get("max_file_size", 0)
    max_lines = limits.get("jsonl_lines", 0) if is_jsonl else limits.get("max_lines", 0)

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            # Full mode or file within limits: read everything
            if mode == "full" or (max_size > 0 and size <= max_size):
                content = f.read()
                total = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
                if not content:
                    return "(empty file)", 0, False
                return content, total, False

            # File exceeds limits — apply truncation mode
            all_lines = f.readlines()
            total = len(all_lines)

            if mode == "head":
                kept = all_lines[:max_lines]
                content = "".join(kept)
                content += f"\n(HEAD TRUNCATED — showing first {len(kept)} of {total:,} lines, {size:,} bytes.)\n"

            elif mode == "tail":
                kept = all_lines[-max_lines:]
                content = f"(TAIL TRUNCATED — showing last {len(kept)} of {total:,} lines, {size:,} bytes.)\n\n"
                content += "".join(kept)

            elif mode == "split":
                half = max_lines // 2
                head = all_lines[:half]
                tail = all_lines[-half:]
                content = "".join(head)
                content += f"\n(SPLIT — {total:,} total lines. Showing first {len(head)} + last {len(tail)}, {total - len(head) - len(tail):,} lines omitted.)\n\n"
                content += "".join(tail)

            elif mode == "efficient":
                # Chunked: first N lines, then last 20 for context
                tail_n = min(20, max_lines // 5)
                head_n = max_lines - tail_n
                head = all_lines[:head_n]
                tail = all_lines[-tail_n:] if total > head_n + tail_n else []
                content = "".join(head)
                if tail:
                    omitted = total - len(head) - len(tail)
                    content += f"\n(... {omitted:,} lines omitted ...)\n\n"
                    content += "".join(tail)
                content += f"\n(EFFICIENT — {total:,} total lines, {size:,} bytes.)\n"

            else:
                # Unknown mode, fall back to full
                content = "".join(all_lines)
                return content, total, False

            return content, total, True

    except Exception as e:
        return f"(error reading file: {e})", 0, False


def generate_grep_patterns(files: list, has_harpoon: bool = False) -> str:
    """Generate context-aware grep patterns based on file contents."""
    patterns = []
    patterns.append("```bash")
    patterns.append("# List all files:")
    patterns.append("grep '^\\[FILE:' dump.md")
    patterns.append("")
    patterns.append("# Find files by category:")
    patterns.append("grep '^\\[FILE:.*category=SPEC' dump.md")
    patterns.append("grep '^\\[FILE:.*category=RUNTIME' dump.md")
    patterns.append("grep '^\\[FILE:.*category=DOC' dump.md")
    patterns.append("")
    patterns.append("# Content searches:")
    patterns.append("grep -n 'PROVISIONAL' dump.md           # uncalibrated thresholds")
    patterns.append("grep -n 'TODO\\|FIXME\\|HACK' dump.md     # action items")
    patterns.append("grep -n '^class \\|^def ' dump.md        # Python definitions")
    patterns.append("grep -n 'import ' dump.md                # dependency map")
    patterns.append("grep -n 'INV-' dump.md                   # invariant references")
    patterns.append("grep -n 'envelope_type' dump.md          # envelope schemas")
    patterns.append("grep -n 'signal_id' dump.md              # signal definitions")

    if has_harpoon:
        patterns.append("")
        patterns.append("# Harpoon assessment:")
        patterns.append("grep -n 'invariant\\|constraint\\|law\\|rule' dump.md  # anchor candidates")
        patterns.append("grep -n 'interface\\|adapter\\|hook\\|plugin' dump.md  # winch points")
        patterns.append("grep -n 'config\\|settings\\|env\\|threshold' dump.md  # tuning surfaces")

    patterns.append("```")
    return "\n".join(patterns)


def write_dump(files: list, output_path: str, title: str = "Context Consolidation",
               description: str = "", harpoon: bool = False, arena: str = None,
               git_commit: str = None, mode: str = "full",
               rtch_packet_id: str = None):
    """Write the consolidated dump file."""
    # Classify files
    classified = []
    total_lines = 0
    for rel, full in files:
        cat = classify_file(rel)
        content, lines, truncated = read_file_content(full, rel, mode=mode)
        classified.append({
            "rel": rel, "full": full, "category": cat,
            "content": content, "lines": lines, "truncated": truncated,
        })
        total_lines += lines

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cat_counts = Counter(f["category"] for f in classified)

    with open(output_path, "w", encoding="utf-8") as out:
        # Header
        out.write(f"# {title} — Context Consolidation Dump\n\n")
        out.write(f"> **Agent-consumable. {len(classified)} files, ~{total_lines:,} lines. Generated {now}.**\n")
        if description:
            out.write(f"> Source: {description}\n")
        if git_commit:
            out.write(f"> Git commit: {git_commit}\n")
        if rtch_packet_id:
            out.write(f"> **RTCH source selection**: rtch_packet_id={rtch_packet_id}\n")
        out.write("\n")

        # Harpoon preamble
        if harpoon:
            out.write("## Harpoon Analysis Preamble\n\n")
            out.write("This dump is prepared for harpoon assessment. When analyzing:\n\n")
            out.write("- **Anchor spots**: Constitutional primitives, invariants, patterns that align with federation doctrine\n")
            out.write("- **Winch points**: Integration surfaces where target patterns could mount into federation infrastructure\n")
            out.write("- **Rejection zones**: Patterns that contradict federation invariants or require governance exceptions\n")
            out.write("- **Adaptation candidates**: Patterns needing transformation before federation compatibility\n")
            out.write("- **tier_2_adapt signals**: Human-execution-dependent patterns ('Open Chrome...') that need agent-executable wrapping\n\n")

        # Arena preamble
        if arena:
            out.write(f"## Arena Context: {arena}\n\n")
            out.write("This dump consolidates all files relevant to the arena specification.\n\n")

        # Grep patterns
        out.write("## Grep Patterns\n\n")
        out.write(generate_grep_patterns(classified, harpoon))
        out.write("\n\n")

        # Category summary
        out.write("## Categories\n\n")
        out.write("| Category | Count |\n|---|---|\n")
        for cat, count in sorted(cat_counts.items()):
            out.write(f"| {cat} | {count} |\n")
        out.write(f"| **TOTAL** | **{len(classified)}** |\n\n")

        # File index
        out.write("## File Index\n\n")
        out.write("| # | Path | Category | Lines | Notes |\n")
        out.write("|---|---|---|---|---|\n")
        for idx, f in enumerate(classified, 1):
            notes = "TRUNCATED" if f["truncated"] else ""
            out.write(f"| {idx} | `{f['rel']}` | {f['category']} | {f['lines']:,} | {notes} |\n")
        out.write("\n---\n\n")

        # File contents
        for f in classified:
            out.write(f"[FILE: {f['rel']} | category={f['category']} | lines={f['lines']}]\n\n")
            out.write(f["content"])
            if not f["content"].endswith("\n"):
                out.write("\n")
            out.write("\n[/FILE]\n\n")

    return len(classified), total_lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Context consolidation pipeline — concatenate files into LLM-consumable dump"
    )
    parser.add_argument("--targets", nargs="+", help="Paths, globs, or directories to consolidate")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--title", default="Context Consolidation", help="Dump title")
    parser.add_argument("--description", default="", help="Source description")
    parser.add_argument("--git-repo", help="Git repo URL to clone and consolidate")
    parser.add_argument("--git-diff", help="Git diff range (e.g., main..HEAD)")
    parser.add_argument("--harpoon", action="store_true", help="Harpoon assessment mode")
    parser.add_argument("--arena", help="Arena spec YAML path for context mode")
    parser.add_argument("--scan", action="store_true", help="Dry run — show what would be included")
    parser.add_argument("--include", help="Comma-separated additional extensions to include")
    parser.add_argument("--exclude", help="Comma-separated additional patterns to exclude")
    parser.add_argument("--mode", choices=["full", "efficient", "head", "tail", "split"],
                        default="full",
                        help="Truncation mode: full (default, no truncation), efficient (chunked+sparse), "
                             "head (front only), tail (back only), split (front+back)")
    parser.add_argument("--max-file-size", type=int, default=500000, help="Max file size threshold for non-full modes (bytes)")
    parser.add_argument("--base-dir", help="Base directory for relative paths (default: cwd)")
    parser.add_argument("--rtch-packet-id", default=None,
                        help="RTCH packet ID for provenance (set when invoked via /tactical-hydration handoff)")
    args = parser.parse_args()

    MAX_FILE_SIZE = args.max_file_size

    if args.include:
        for ext in args.include.split(","):
            ext = ext.strip()
            if not ext.startswith("."):
                ext = "." + ext
            DEFAULT_INCLUDE.add(ext)

    if args.exclude:
        for pat in args.exclude.split(","):
            DEFAULT_EXCLUDE_FILES.add(pat.strip())

    base_dir = args.base_dir or os.getcwd()
    tmpdir = None
    git_commit = None
    all_files = []

    # Collect from git repo
    if args.git_repo:
        print(f"Cloning {args.git_repo}...", file=sys.stderr)
        try:
            files, tmpdir, git_commit = collect_from_git_repo(args.git_repo)
            all_files.extend(files)
            print(f"  Collected {len(files)} files (commit {git_commit})", file=sys.stderr)
        except Exception as e:
            print(f"Error cloning repo: {e}", file=sys.stderr)
            sys.exit(1)

    # Collect from git diff
    if args.git_diff:
        files = collect_from_git_diff(args.git_diff, base_dir)
        all_files.extend(files)
        print(f"  Collected {len(files)} files from diff {args.git_diff}", file=sys.stderr)

    # Collect from targets
    if args.targets:
        for target in args.targets:
            expanded = os.path.expanduser(target)
            if os.path.isdir(expanded):
                files = collect_from_directory(expanded, base_dir)
                all_files.extend(files)
                print(f"  {target}: {len(files)} files", file=sys.stderr)
            elif "*" in target or "?" in target:
                files = collect_from_glob(expanded, base_dir)
                all_files.extend(files)
                print(f"  {target}: {len(files)} files", file=sys.stderr)
            elif os.path.isfile(expanded):
                rel = os.path.relpath(expanded, base_dir)
                all_files.append((rel, expanded))
                print(f"  {target}: 1 file", file=sys.stderr)
            else:
                print(f"  Warning: {target} not found, skipping", file=sys.stderr)

    # Deduplicate by full path
    seen = set()
    deduped = []
    for rel, full in all_files:
        real = os.path.realpath(full)
        if real not in seen:
            seen.add(real)
            deduped.append((rel, full))
    all_files = deduped

    if not all_files:
        print("No files found to consolidate.", file=sys.stderr)
        sys.exit(2)

    # Scan mode — dry run
    if args.scan:
        print(json.dumps({
            "files": len(all_files),
            "file_list": [r for r, _ in all_files],
            "categories": dict(Counter(classify_file(r) for r, _ in all_files)),
        }, indent=2))
        sys.exit(0)

    # Determine output path
    output = args.output
    if not output:
        output = f"consolidation-dump-{datetime.now().strftime('%Y%m%dT%H%M%S')}.md"

    # Write
    title = args.title
    if args.harpoon:
        title = f"Harpoon Assessment: {title}"
    if args.arena:
        title = f"Arena Context: {args.arena}"

    count, lines = write_dump(
        all_files, output,
        title=title,
        description=args.description or f"{len(all_files)} files from {len(args.targets or [])} targets",
        harpoon=args.harpoon,
        arena=args.arena,
        git_commit=git_commit,
        mode=args.mode,
        rtch_packet_id=args.rtch_packet_id,
    )

    size = os.path.getsize(output)
    print(json.dumps({
        "output": output,
        "files": count,
        "lines": lines,
        "size_bytes": size,
        "size_human": f"{size // 1024}KB",
        "git_commit": git_commit,
    }, indent=2))

    # Cleanup temp dir
    if tmpdir and os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    main()
