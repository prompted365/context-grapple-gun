#!/usr/bin/env python3
"""
rebru-resolve — ReBru v0 binder resolver CLI.

Implements Tranche Set #5 Bites 1 + 4 from the T4a ReBru schema v0 spec
(audit-logs/governance/specs/rebru-schema-v0-spec.md, Section 13):

  - Bite 1 (Resolver CLI): accepts a binder handle (e.g., @Queue.0) and a
    cadence block YAML path; emits the hydration output per the binder's
    hydrate recipe.
  - Bite 4 (Single-Binder Hydrate): dispatches the hydrate recipe method to
    the appropriate read tool with max_bytes cap enforcement.

Read-only. No source mutation. No hot-path or Harmony ingestion. No
runtime-exhaust binding. Scope: cadence-handoff binding only (per narrow
bounds §2 of T4a spec).

The 9 method enum values from rebru-cadence-block.schema.draft.json:
  rg_window, read_lines, read_full, jsonl_tail, jsonl_grep, json_path,
  rtch_packet_chunk, git_show, raw_jsonl_filter

v0 implements all 9 methods. Methods exercised in n=1+n=2 production blocks
(rg_window, read_full, jsonl_tail) are validated; the remaining 6 are
implemented but flagged with a NOT_VALIDATED_IN_V0 stderr note on first
use until cross-tic exercise accumulates.

Authorized at /review tic 257 ITEM 1 PROMOTE-SCHEMA-V0+EXTEND-TO-N=3.
Authored at tic 258 T5c.

Usage:
    rebru-resolve --block <path-to-cadence-block.yaml> --handle <@Lane.N>
    rebru-resolve --block <path> --list           # enumerate all binders
    rebru-resolve --block <path> --handle <@Lane.N> --json   # structured output

Lock line (from T4a spec, Architect-given verbatim):
    Variables are allowed to point. Variables are not allowed to decide.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


HANDLE_REGEX = re.compile(r"^@[A-Z][A-Za-z]+\.[0-9]+$")
VALIDATED_METHODS = {"rg_window", "read_full", "jsonl_tail"}
ALL_METHODS = {
    "rg_window", "read_lines", "read_full", "jsonl_tail",
    "jsonl_grep", "json_path", "rtch_packet_chunk", "git_show",
    "raw_jsonl_filter",
}


def expand_path(p: str) -> str:
    """Expand ~ and resolve env vars in a source path."""
    return os.path.expanduser(os.path.expandvars(p))


def cap_bytes(content: str, max_bytes: int) -> str:
    """Cap content to max_bytes (UTF-8 bytes). Truncates at byte boundary."""
    if max_bytes <= 0:
        return content
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated + f"\n... [truncated at {max_bytes} bytes]"


def hydrate_rg_window(source: str, query: str, line_window: int, max_bytes: int) -> str:
    """rg-style search with line context window. Returns matches + neighbors."""
    src = expand_path(source)
    if not Path(src).exists():
        return f"ERROR: source not found: {src}"
    try:
        result = subprocess.run(
            ["rg", "-n", "-C", str(line_window), query, src],
            capture_output=True, text=True, timeout=10,
        )
        return cap_bytes(result.stdout or "(no matches)", max_bytes)
    except FileNotFoundError:
        # rg not installed — fall back to grep
        try:
            result = subprocess.run(
                ["grep", "-n", "-C", str(line_window), query, src],
                capture_output=True, text=True, timeout=10,
            )
            return cap_bytes(result.stdout or "(no matches)", max_bytes)
        except subprocess.TimeoutExpired:
            return "ERROR: hydrate timeout"
    except subprocess.TimeoutExpired:
        return "ERROR: hydrate timeout"


def hydrate_read_lines(source: str, line_window: int, max_bytes: int, start_line: int = 1) -> str:
    """Read line_window lines starting at start_line."""
    src = expand_path(source)
    if not Path(src).exists():
        return f"ERROR: source not found: {src}"
    try:
        with open(src, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f, start=1):
                if i < start_line:
                    continue
                if i >= start_line + line_window:
                    break
                lines.append(f"{i}: {line.rstrip()}")
        return cap_bytes("\n".join(lines), max_bytes)
    except OSError as e:
        return f"ERROR: read failed: {e}"


def hydrate_read_full(source: str, max_bytes: int) -> str:
    """Read full file up to max_bytes cap."""
    src = expand_path(source)
    if not Path(src).exists():
        return f"ERROR: source not found: {src}"
    try:
        content = Path(src).read_text(encoding="utf-8", errors="replace")
        return cap_bytes(content, max_bytes)
    except OSError as e:
        return f"ERROR: read failed: {e}"


def hydrate_jsonl_tail(source: str, query: str, line_window: int, max_bytes: int) -> str:
    """Tail JSONL with optional query filter. query format: 'field:value' filters latest matching."""
    src = expand_path(source)
    if not Path(src).exists():
        return f"ERROR: source not found: {src}"
    try:
        with open(src, "r", encoding="utf-8", errors="replace") as f:
            lines = [ln for ln in f if ln.strip()]
        if query and ":" in query:
            field, value = query.split(":", 1)
            filtered = []
            for ln in lines:
                try:
                    rec = json.loads(ln)
                    if str(rec.get(field, "")) == value:
                        filtered.append(ln)
                except json.JSONDecodeError:
                    continue
            tail = filtered[-line_window:] if filtered else lines[-line_window:]
        else:
            tail = lines[-line_window:]
        return cap_bytes("".join(tail), max_bytes)
    except OSError as e:
        return f"ERROR: read failed: {e}"


def hydrate_jsonl_grep(source: str, query: str, line_window: int, max_bytes: int) -> str:
    """Filter JSONL by 'field:value' predicate; return up to line_window matches."""
    src = expand_path(source)
    if not Path(src).exists():
        return f"ERROR: source not found: {src}"
    if not query or ":" not in query:
        return "ERROR: jsonl_grep requires 'field:value' query"
    field, value = query.split(":", 1)
    matches = []
    try:
        with open(src, "r", encoding="utf-8", errors="replace") as f:
            for ln in f:
                if not ln.strip():
                    continue
                try:
                    rec = json.loads(ln)
                    if str(rec.get(field, "")) == value:
                        matches.append(ln)
                        if len(matches) >= line_window:
                            break
                except json.JSONDecodeError:
                    continue
        return cap_bytes("".join(matches) if matches else "(no matches)", max_bytes)
    except OSError as e:
        return f"ERROR: read failed: {e}"


def hydrate_json_path(source: str, query: str, max_bytes: int) -> str:
    """Extract a JSON field via dot notation. query: 'a.b.c' or 'a.b[0].c'."""
    src = expand_path(source)
    if not Path(src).exists():
        return f"ERROR: source not found: {src}"
    try:
        doc = json.loads(Path(src).read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as e:
        return f"ERROR: load failed: {e}"
    if not query:
        return cap_bytes(json.dumps(doc, indent=2), max_bytes)
    # Simple dot-and-index parser
    cur = doc
    for part in query.split("."):
        m = re.match(r"^(.+?)\[(\d+)\]$", part)
        if m:
            key, idx = m.group(1), int(m.group(2))
            if not isinstance(cur, dict) or key not in cur:
                return f"ERROR: path segment '{key}' not found"
            cur = cur[key]
            if not isinstance(cur, list) or idx >= len(cur):
                return f"ERROR: index [{idx}] out of bounds"
            cur = cur[idx]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return f"ERROR: path segment '{part}' not found"
    out = json.dumps(cur, indent=2) if isinstance(cur, (dict, list)) else str(cur)
    return cap_bytes(out, max_bytes)


def hydrate_rtch_packet_chunk(source: str, query: str, max_bytes: int) -> str:
    """Read a chunk from an RTCH packet by query. Falls back to read_full."""
    # v0: RTCH packet structure not yet machine-typed; read full + cap
    return hydrate_read_full(source, max_bytes)


def hydrate_git_show(source: str, max_bytes: int) -> str:
    """git show <ref> — source is a git ref or commit SHA."""
    try:
        result = subprocess.run(
            ["git", "show", source],
            capture_output=True, text=True, timeout=15,
        )
        return cap_bytes(result.stdout or "(no output)", max_bytes)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f"ERROR: git show failed: {e}"


def hydrate_raw_jsonl_filter(source: str, query: str, line_window: int, max_bytes: int) -> str:
    """raw_jsonl_filter — alias to jsonl_grep for v0 (same semantics)."""
    return hydrate_jsonl_grep(source, query, line_window, max_bytes)


def dispatch_hydrate(recipe: dict) -> str:
    """Dispatch the hydrate recipe to the appropriate handler.

    The dispatch enforces:
      - max_bytes cap (default 8192 if absent)
      - method enum validation
      - source presence
      - method-specific argument validation
    """
    method = recipe.get("method")
    source = recipe.get("source", "")
    query = recipe.get("query", "")
    line_window = int(recipe.get("line_window", 10))
    max_bytes = int(recipe.get("max_bytes", 8192))

    if method not in ALL_METHODS:
        return f"ERROR: unknown hydrate method '{method}'; valid: {sorted(ALL_METHODS)}"
    if not source:
        return "ERROR: hydrate recipe missing 'source'"
    if method not in VALIDATED_METHODS:
        print(
            f"NOTE: method '{method}' is implemented but NOT_VALIDATED_IN_V0 "
            f"(no cross-tic production exercise yet — per T4a spec §10).",
            file=sys.stderr,
        )

    if method == "rg_window":
        return hydrate_rg_window(source, query, line_window, max_bytes)
    if method == "read_lines":
        start_line = int(recipe.get("start_line", 1))
        return hydrate_read_lines(source, line_window, max_bytes, start_line)
    if method == "read_full":
        return hydrate_read_full(source, max_bytes)
    if method == "jsonl_tail":
        return hydrate_jsonl_tail(source, query, line_window, max_bytes)
    if method == "jsonl_grep":
        return hydrate_jsonl_grep(source, query, line_window, max_bytes)
    if method == "json_path":
        return hydrate_json_path(source, query, max_bytes)
    if method == "rtch_packet_chunk":
        return hydrate_rtch_packet_chunk(source, query, max_bytes)
    if method == "git_show":
        return hydrate_git_show(source, max_bytes)
    if method == "raw_jsonl_filter":
        return hydrate_raw_jsonl_filter(source, query, line_window, max_bytes)

    # Unreachable due to method enum check above
    return f"ERROR: dispatch failure for method '{method}'"


def load_block(block_path: str) -> dict:
    """Load a cadence block YAML."""
    p = Path(expand_path(block_path))
    if not p.exists():
        print(f"ERROR: block not found: {p}", file=sys.stderr)
        sys.exit(2)
    try:
        with open(p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        print(f"ERROR: failed to parse block: {e}", file=sys.stderr)
        sys.exit(2)


def find_binder(block: dict, handle: str) -> dict | None:
    """Locate the binder matching the given handle (e.g., @Queue.0)."""
    binders = block.get("binders") or []
    for b in binders:
        if b.get("binder") == handle:
            return b
    return None


def list_binders(block: dict) -> str:
    """Enumerate all binders in the block as a table."""
    binders = block.get("binders") or []
    lines = [
        f"Block: tic={block.get('tic')} session={block.get('session_id', '?')}",
        f"Binders: {len(binders)}",
        "",
        f"{'HANDLE':<24} {'LANE':<18} {'METHOD':<20} {'TTL':<6} AUTH",
        "-" * 90,
    ]
    for b in binders:
        handle = b.get("binder", "?")
        lane = b.get("lane", "?")
        method = (b.get("hydrate") or {}).get("method", "?")
        ttl = b.get("ttl_tics")
        ttl_s = str(ttl) if ttl is not None else "∞"
        auth = b.get("authority_class", "?")
        lines.append(f"{handle:<24} {lane:<18} {method:<20} {ttl_s:<6} {auth}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Resolve a ReBru v0 binder handle to its hydrated source window.",
    )
    parser.add_argument("--block", required=True,
                        help="Path to cadence block YAML")
    parser.add_argument("--handle", default=None,
                        help="Binder handle (e.g., @Queue.0). Required unless --list.")
    parser.add_argument("--list", action="store_true",
                        help="List all binders in the block")
    parser.add_argument("--json", action="store_true",
                        help="Emit structured JSON output (handle metadata + hydrated content)")
    args = parser.parse_args()

    block = load_block(args.block)

    if args.list:
        print(list_binders(block))
        return 0

    if not args.handle:
        print("ERROR: --handle required unless --list specified", file=sys.stderr)
        return 2

    if not HANDLE_REGEX.match(args.handle):
        print(
            f"ERROR: handle '{args.handle}' does not match @<Lane>.<index> pattern "
            f"per T4a spec §3 (regex ^@[A-Z][A-Za-z]+\\.[0-9]+$)",
            file=sys.stderr,
        )
        return 2

    binder = find_binder(block, args.handle)
    if binder is None:
        print(f"ERROR: handle '{args.handle}' not found in block", file=sys.stderr)
        return 1

    recipe = binder.get("hydrate") or {}
    if not recipe:
        print(f"ERROR: binder '{args.handle}' has no hydrate recipe", file=sys.stderr)
        return 1

    content = dispatch_hydrate(recipe)

    if args.json:
        out = {
            "block_path": args.block,
            "handle": args.handle,
            "binder_metadata": {
                "kind": binder.get("kind"),
                "lane": binder.get("lane"),
                "authority_class": binder.get("authority_class"),
                "ttl_tics": binder.get("ttl_tics"),
                "emission_tic": binder.get("emission_tic"),
                "content_hash": binder.get("content_hash"),
            },
            "hydrate_recipe": recipe,
            "hydrated_content": content,
        }
        print(json.dumps(out, indent=2))
    else:
        print(content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
