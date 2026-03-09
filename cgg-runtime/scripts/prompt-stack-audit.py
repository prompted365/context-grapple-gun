#!/usr/bin/env python3
"""
Prompt Stack Audit — CLAUDE.md chain coherence scanner.

Scans the CLAUDE.md governance chain (federation -> estate -> domain -> site)
for:
  - Contradictions between parent/child doctrine
  - Overlapping/redundant rules at different scopes
  - Rules that reference specific volatile surfaces (promotion gate violation)

Output: JSON audit packet with findings.

Usage:
    python3 prompt-stack-audit.py --project-dir /path/to/zone
    python3 prompt-stack-audit.py --project-dir /path/to/zone --dry-run
    python3 prompt-stack-audit.py --project-dir /path/to/zone --json
    python3 prompt-stack-audit.py --help
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, resolve_rung_position


# ---------------------------------------------------------------------------
# CLAUDE.md chain discovery
# ---------------------------------------------------------------------------

def discover_claude_md_chain(zone_root):
    """Walk the rung topology and collect CLAUDE.md files with their rung labels."""
    rp = resolve_rung_position(zone_root)
    chain = []

    # Add files from topology (site -> domain -> estate -> federation)
    rung_order = ["site", "domain", "estate", "federation"]
    for rung in rung_order:
        info = rp["topology"].get(rung)
        if info and info.get("path"):
            cmd = Path(info["path"]) / "CLAUDE.md"
            if cmd.exists():
                chain.append({
                    "rung": rung,
                    "path": str(cmd),
                    "name": info.get("name", os.path.basename(info["path"])),
                })

    # Global CLAUDE.md
    global_cmd = Path.home() / ".claude" / "CLAUDE.md"
    if global_cmd.exists():
        chain.append({
            "rung": "global",
            "path": str(global_cmd),
            "name": "global",
        })

    return chain


def load_claude_md(path):
    """Load and return CLAUDE.md content."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ---------------------------------------------------------------------------
# Audit checks
# ---------------------------------------------------------------------------

# Volatile surface indicators — references to specific third-party fields/models/endpoints
VOLATILE_PATTERNS = [
    (r"gemini-\d[\w.-]+", "Gemini model name"),
    (r"gpt-\d[\w.-]+", "GPT model name"),
    (r"claude-\d[\w.-]+", "Claude model name"),
    (r"veo-\d[\w.-]+", "Veo model name"),
    (r"v\d+beta\d*", "API version string"),
    (r"https?://[\w./]+(api|endpoint|webhook)", "API endpoint URL"),
]

# Contradiction detection — opposing keyword pairs
CONTRADICTION_PAIRS = [
    ({"never", "must not", "do not", "prohibited", "forbidden"},
     {"always", "must", "required", "mandatory"}),
]


def check_volatile_references(content, path, rung):
    """Find references to specific volatile surfaces in doctrine-level files."""
    findings = []
    lines = content.splitlines()

    for i, line in enumerate(lines, 1):
        # Skip HTML comments (they're metadata, not doctrine)
        if line.strip().startswith("<!--"):
            continue
        # Skip code blocks
        if line.strip().startswith("```"):
            continue

        for pattern, label in VOLATILE_PATTERNS:
            matches = re.findall(pattern, line, re.IGNORECASE)
            if matches:
                findings.append({
                    "type": "volatile_reference",
                    "severity": "warning",
                    "rung": rung,
                    "file": path,
                    "line": i,
                    "match": matches[0],
                    "label": label,
                    "message": f"Volatile surface reference ({label}) in {rung}-level doctrine",
                })

    return findings


def check_redundancies(chain_contents):
    """Find overlapping rules across different scope levels."""
    findings = []

    # Extract section headers from each file
    sections_by_rung = {}
    for entry in chain_contents:
        headers = re.findall(r"^#{1,3}\s+(.+)$", entry["content"], re.MULTILINE)
        sections_by_rung[entry["rung"]] = {
            "headers": [h.strip().lower() for h in headers],
            "path": entry["path"],
        }

    # Check for duplicate section headers across rungs
    seen_headers = {}
    for rung, data in sections_by_rung.items():
        for header in data["headers"]:
            if header in seen_headers:
                findings.append({
                    "type": "redundant_section",
                    "severity": "info",
                    "rung": rung,
                    "file": data["path"],
                    "other_rung": seen_headers[header]["rung"],
                    "other_file": seen_headers[header]["path"],
                    "header": header,
                    "message": f"Section '{header}' exists at both {seen_headers[header]['rung']} and {rung} level",
                })
            else:
                seen_headers[header] = {"rung": rung, "path": data["path"]}

    return findings


def check_contradictions(chain_contents):
    """Find potential contradictions between parent and child doctrine."""
    findings = []

    for i, child in enumerate(chain_contents):
        for parent in chain_contents[i + 1:]:
            child_lines = child["content"].lower().splitlines()
            parent_lines = parent["content"].lower().splitlines()

            for pos_set, neg_set in CONTRADICTION_PAIRS:
                # Find assertions in parent
                for pi, pline in enumerate(parent_lines, 1):
                    pline_clean = pline.strip()
                    if not pline_clean or pline_clean.startswith("#") or pline_clean.startswith("<!--"):
                        continue

                    parent_has_pos = any(kw in pline_clean for kw in pos_set)
                    parent_has_neg = any(kw in pline_clean for kw in neg_set)

                    if not (parent_has_pos or parent_has_neg):
                        continue

                    # Look for opposing assertions in child about same topic
                    # Extract key nouns from parent line
                    parent_nouns = set(re.findall(r"\b[a-z]{4,}\b", pline_clean)) - pos_set - neg_set
                    if len(parent_nouns) < 2:
                        continue

                    for ci, cline in enumerate(child_lines, 1):
                        cline_clean = cline.strip()
                        if not cline_clean or cline_clean.startswith("#") or cline_clean.startswith("<!--"):
                            continue

                        child_nouns = set(re.findall(r"\b[a-z]{4,}\b", cline_clean))
                        noun_overlap = len(parent_nouns & child_nouns) / max(len(parent_nouns), 1)

                        if noun_overlap < 0.4:
                            continue

                        child_has_pos = any(kw in cline_clean for kw in pos_set)
                        child_has_neg = any(kw in cline_clean for kw in neg_set)

                        if (parent_has_pos and child_has_neg) or (parent_has_neg and child_has_pos):
                            findings.append({
                                "type": "potential_contradiction",
                                "severity": "warning",
                                "parent_rung": parent["rung"],
                                "parent_file": parent["path"],
                                "parent_line": pi,
                                "child_rung": child["rung"],
                                "child_file": child["path"],
                                "child_line": ci,
                                "message": f"Potential contradiction between {parent['rung']}:{pi} and {child['rung']}:{ci}",
                            })

    return findings


def check_upward_references(chain_contents):
    """Check for child files referencing parent-scope concepts they shouldn't own."""
    findings = []
    rung_order = ["site", "domain", "estate", "federation", "global"]

    for entry in chain_contents:
        rung_idx = rung_order.index(entry["rung"]) if entry["rung"] in rung_order else 0
        content = entry["content"]

        # Check for references to higher-scope operations
        if rung_idx < 3:  # site, domain, estate
            if re.search(r"\bfederation\s+(law|rule|doctrine|invariant)\b", content, re.IGNORECASE):
                findings.append({
                    "type": "upward_reference",
                    "severity": "info",
                    "rung": entry["rung"],
                    "file": entry["path"],
                    "message": f"{entry['rung']}-level file references federation-level doctrine",
                })

    return findings


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_audit(project_dir, dry_run=False):
    """Run the full prompt stack audit."""
    project_dir = os.path.abspath(project_dir)
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)

    chain = discover_claude_md_chain(project_dir)

    # Load all contents
    chain_contents = []
    for entry in chain:
        content = load_claude_md(entry["path"])
        chain_contents.append({**entry, "content": content})

    # Run all checks
    all_findings = []

    for entry in chain_contents:
        all_findings.extend(check_volatile_references(entry["content"], entry["path"], entry["rung"]))

    all_findings.extend(check_redundancies(chain_contents))
    all_findings.extend(check_contradictions(chain_contents))
    all_findings.extend(check_upward_references(chain_contents))

    # Build audit packet
    severity_counts = {}
    for f in all_findings:
        sev = f.get("severity", "info")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    type_counts = {}
    for f in all_findings:
        t = f.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    packet = {
        "audit_type": "prompt_stack_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chain": [{"rung": e["rung"], "path": e["path"], "name": e["name"]} for e in chain],
        "chain_depth": len(chain),
        "findings": all_findings,
        "summary": {
            "total_findings": len(all_findings),
            "by_severity": severity_counts,
            "by_type": type_counts,
        },
    }

    if not dry_run:
        report_dir = os.path.join(al_path, "mogul", "cycle-reports", "prompt-stack-audits")
        os.makedirs(report_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
        output_path = os.path.join(report_dir, f"{timestamp}-audit.json")
        Path(output_path).write_text(json.dumps(packet, indent=2), encoding="utf-8")
        packet["_output_path"] = output_path

    return packet


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Prompt Stack Audit — CLAUDE.md chain coherence scanner"
    )
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run audit without writing results to disk")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Output structured JSON to stdout")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    project_dir = args.project_dir or resolve_zone_root()
    packet = run_audit(project_dir, dry_run=args.dry_run)

    if args.output_json:
        # Don't include internal _output_path in JSON output
        packet.pop("_output_path", None)
        print(json.dumps(packet, indent=2))
    elif not args.quiet:
        s = packet["summary"]
        print(f"Prompt stack audit: {s['total_findings']} findings across {packet['chain_depth']} files")
        if s["by_severity"]:
            parts = [f"{count} {sev}" for sev, count in s["by_severity"].items()]
            print(f"  Severity: {', '.join(parts)}")
        if s["by_type"]:
            parts = [f"{count} {t}" for t, count in s["by_type"].items()]
            print(f"  Types: {', '.join(parts)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
