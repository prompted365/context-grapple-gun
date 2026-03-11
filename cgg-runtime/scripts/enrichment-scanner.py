#!/usr/bin/env python3
"""
Enrichment Scanner — scans governance docs for ENRICHMENT_REQUESTED tags.

Reports count and locations of sections needing attention. Designed for
/loop-compatible periodic monitoring.

Usage:
  python3 enrichment-scanner.py                          # full report
  python3 enrichment-scanner.py check                    # exit code only (0=clean, 1=tags found)
  python3 enrichment-scanner.py --project-dir /path      # explicit project root
"""

import argparse
import os
import re
import sys
from pathlib import Path

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TAG_PATTERN = re.compile(
    r'<!--\s*ENRICHMENT_REQUESTED:\s*(.+?)\s*-->', re.IGNORECASE
)

# Governance docs to scan (relative to project root)
SCAN_TARGETS = [
    "ARCHITECTURE.md",
    "SYSTEM_MAP.md",
    "CLAUDE.md",
    "GLOSSARY.md",
    "autonomous_kernel/entity-ontology.md",
    "autonomous_kernel/archivist-envelope-schema.md",
    "autonomous_kernel/agent-inbox-schema.md",
    "ak_control_room/CLAUDE.md",
    "ak_control_room/mode-map.md",
]


def find_tags(project_dir: Path) -> list[dict]:
    """Scan governance docs for enrichment tags. Returns list of findings."""
    findings = []
    for rel_path in SCAN_TARGETS:
        fp = project_dir / rel_path
        if not fp.exists():
            continue
        lines = fp.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            m = TAG_PATTERN.search(line)
            if m:
                findings.append({
                    "file": rel_path,
                    "line": i,
                    "description": m.group(1).strip(),
                })
    return findings


def main():
    parser = argparse.ArgumentParser(description="Scan for ENRICHMENT_REQUESTED tags")
    parser.add_argument("mode", nargs="?", default="report", choices=["report", "check"])
    parser.add_argument("--project-dir", default=None)
    args = parser.parse_args()

    if args.project_dir:
        project_dir = Path(args.project_dir)
    else:
        # Walk up to find .federation-root
        cwd = Path.cwd()
        project_dir = cwd
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".federation-root").exists():
                project_dir = parent
                break

    findings = find_tags(project_dir)

    if args.mode == "check":
        if findings:
            print(f"ENRICHMENT: {len(findings)} tag(s) pending")
            sys.exit(1)
        else:
            print("ENRICHMENT: clean")
            sys.exit(0)

    # Full report
    if not findings:
        print("No enrichment tags found. All governance docs are current.")
        return

    print(f"=== Enrichment Scanner: {len(findings)} tag(s) found ===\n")
    for f in findings:
        print(f"  {f['file']}:{f['line']}")
        print(f"    → {f['description']}\n")


if __name__ == "__main__":
    main()
