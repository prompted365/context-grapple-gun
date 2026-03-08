#!/usr/bin/env python3
"""
Rung resolution CLI — topology bootstrap for CGG.

Walks upward from cwd (or --start), detects rung markers, prints topology.
Tolerates partial/missing topology — works even with NO markers present.

Marker convention (plain sentinel files):
  .ticzone         = site boundary (governance zone)
  .domain-root     = domain boundary
  .estate-root     = estate boundary
  .federation-root = federation boundary
  (none)           = global (external Claude scope ~/.claude/CLAUDE.md)

Usage:
  rung_resolver.py              # human-readable output
  rung_resolver.py --json       # machine-readable JSON
  rung_resolver.py --start /p   # resolve from specific directory
"""

import argparse
import json
import sys
from pathlib import Path

# Import from sibling module
sys.path.insert(0, str(Path(__file__).resolve().parent))
from zone_root import resolve_rung_position, RUNG_ORDER


def format_human(result):
    """Format topology result for human reading."""
    lines = []
    lines.append(f"current_rung: {result['current_rung']}")
    lines.append("")

    lines.append("topology:")
    for rung in reversed(RUNG_ORDER):
        entry = result["topology"][rung]
        if entry is not None:
            lines.append(f"  {rung:12s}  {entry['path']}  ({entry['name']})")
        else:
            lines.append(f"  {rung:12s}  (none)")

    if result["global"]:
        lines.append(f"\nglobal: {result['global']}")
    else:
        lines.append("\nglobal: (none)")

    if result["system_map"]:
        lines.append(f"system_map: {result['system_map']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="CGG rung resolution — detect topology markers"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )
    parser.add_argument(
        "--start", type=str, default=None,
        help="Directory to resolve from (default: cwd or $CLAUDE_PROJECT_DIR)"
    )
    args = parser.parse_args()

    result = resolve_rung_position(start_dir=args.start)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_human(result))


if __name__ == "__main__":
    main()
