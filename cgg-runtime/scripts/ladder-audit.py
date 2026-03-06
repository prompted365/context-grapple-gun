#!/usr/bin/env python3
"""
Ladder Coherence Audit — deterministic scan of CLAUDE.md governance chain.

Discovers all CLAUDE.md files from zone root downward, extracts rules
(methylated lessons, promoted CPRs, section headers), cross-references
parent/child relationships, detects orphans, duplicates, and contradictions.

Outputs a JSON audit packet.

Usage:
    python3 ladder-audit.py [--project-dir PATH] [--json] [--verbose]
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_claude_mds(zone_root):
    """Walk from zone root downward, find all CLAUDE.md files.

    Aggressively skips vendor submodule internals and nested repos to avoid
    polluting the governance chain with files outside the zone's authority.
    """
    found = []
    root = Path(zone_root)

    # Directories to skip entirely — nested repos, vendor internals, build artifacts
    skip_dirs = {
        "node_modules", "__pycache__", ".git", "dist", "build", "target",
    }

    for md in sorted(root.rglob("CLAUDE.md")):
        rel = str(md.relative_to(root))
        parts = rel.split(os.sep)

        # Skip hidden directories (except .claude)
        if any(p.startswith(".") and p != ".claude" for p in parts):
            continue

        # Skip known noise directories
        if any(p in skip_dirs for p in parts):
            continue

        # Skip deep vendor nesting (vendor/X/Y/CLAUDE.md is fine,
        # vendor/X/Y/Z/W/CLAUDE.md is probably a nested repo's own governance)
        vendor_idx = next((i for i, p in enumerate(parts) if p == "vendor"), -1)
        if vendor_idx >= 0:
            depth_in_vendor = len(parts) - vendor_idx - 1  # depth below vendor/
            if depth_in_vendor > 3:
                continue

        # Skip if the directory contains its own .git (nested repo)
        if (md.parent / ".git").exists() and md.parent != root:
            continue

        found.append(md)
    return found


# ---------------------------------------------------------------------------
# Rule extraction
# ---------------------------------------------------------------------------

METHYLATED_RE = re.compile(r"<!--\s*methylated:\s*(\S+)\s*-->")
CPR_STATUS_RE = re.compile(r'status:\s*"(promoted|absorbed|pending|rejected\w*)"')
CPR_LESSON_RE = re.compile(r'lesson:\s*"([^"]+)"')
SECTION_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


def extract_rules(md_path):
    """Extract governance rules from a CLAUDE.md file."""
    try:
        content = md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    rules = []

    # Methylated lessons
    for match in METHYLATED_RE.finditer(content):
        tag = match.group(1)
        line_num = content[:match.start()].count("\n") + 1
        rules.append({
            "type": "methylated",
            "tag": tag,
            "line": line_num,
            "text": tag,
        })

    # Promoted CPR blocks
    blocks = content.split("<!-- --agnostic-candidate")
    for i, block in enumerate(blocks[1:], 1):
        end = block.find("-->")
        if end == -1:
            continue
        block_text = block[:end]
        status_m = CPR_STATUS_RE.search(block_text)
        lesson_m = CPR_LESSON_RE.search(block_text)
        if status_m and status_m.group(1) == "promoted" and lesson_m:
            offset = content.find("<!-- --agnostic-candidate" + block)
            line_num = content[:offset].count("\n") + 1 if offset >= 0 else 0
            rules.append({
                "type": "promoted_cpr",
                "lesson": lesson_m.group(1),
                "line": line_num,
                "text": lesson_m.group(1)[:80],
            })

    # Major sections (h2, h3)
    for match in SECTION_RE.finditer(content):
        depth = len(match.group(1))
        if depth <= 3:
            line_num = content[:match.start()].count("\n") + 1
            rules.append({
                "type": "section",
                "depth": depth,
                "heading": match.group(2).strip(),
                "line": line_num,
                "text": match.group(2).strip(),
            })

    return rules


# ---------------------------------------------------------------------------
# Chain building
# ---------------------------------------------------------------------------

def build_chain(zone_root, md_paths):
    """Build parent/child tree from discovered CLAUDE.md files."""
    root = Path(zone_root)
    nodes = {}

    for md in md_paths:
        rel = str(md.relative_to(root))
        rel_dir = str(md.parent.relative_to(root)) if md.parent != root else "."
        rules = extract_rules(md)
        nodes[rel] = {
            "path": str(md),
            "rel": rel,
            "dir": rel_dir,
            "depth": rel.count(os.sep),
            "rules": rules,
            "children": [],
            "parent": None,
        }

    # Assign parent/child relationships by directory nesting
    sorted_paths = sorted(nodes.keys(), key=lambda k: nodes[k]["depth"])
    for i, rel in enumerate(sorted_paths):
        node = nodes[rel]
        # Find nearest ancestor
        for j in range(i - 1, -1, -1):
            candidate = sorted_paths[j]
            cand_dir = nodes[candidate]["dir"]
            if cand_dir == "." or node["dir"].startswith(cand_dir + os.sep) or node["dir"].startswith(cand_dir):
                if nodes[candidate]["depth"] < node["depth"]:
                    node["parent"] = candidate
                    nodes[candidate]["children"].append(rel)
                    break

    return nodes


# ---------------------------------------------------------------------------
# Cross-reference analysis
# ---------------------------------------------------------------------------

def cross_reference(nodes):
    """Detect orphans, duplicates, missing references."""
    findings = []

    # Orphan detection: nodes with no parent and not root
    for rel, node in nodes.items():
        if node["parent"] is None and node["depth"] > 0:
            findings.append({
                "type": "orphan",
                "file": rel,
                "detail": "CLAUDE.md has no parent in the chain",
                "severity": "medium",
            })

    # Duplicate rule detection across siblings
    parent_groups = defaultdict(list)
    for rel, node in nodes.items():
        parent = node["parent"] or "__root__"
        parent_groups[parent].append(rel)

    for parent, siblings in parent_groups.items():
        if len(siblings) < 2:
            continue
        # Compare methylated tags and promoted lessons across siblings
        sibling_rules = {}
        for sib in siblings:
            for rule in nodes[sib]["rules"]:
                if rule["type"] in ("methylated", "promoted_cpr"):
                    key = rule["text"].lower()[:60]
                    if key not in sibling_rules:
                        sibling_rules[key] = []
                    sibling_rules[key].append(sib)

        for key, locations in sibling_rules.items():
            if len(locations) > 1:
                findings.append({
                    "type": "sibling_duplicate",
                    "rule_key": key,
                    "files": locations,
                    "detail": f"Same rule appears in {len(locations)} siblings under {parent}",
                    "severity": "medium",
                    "state": "under_abstracted",
                })

    # Parent/child reference check
    for rel, node in nodes.items():
        if not node["parent"]:
            continue
        parent_node = nodes[node["parent"]]
        try:
            parent_content = Path(parent_node["path"]).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Does parent reference child directory?
        child_dir = node["dir"]
        child_basename = os.path.basename(child_dir)
        if child_basename not in parent_content and child_dir not in parent_content:
            findings.append({
                "type": "missing_reference",
                "parent": node["parent"],
                "child": rel,
                "detail": f"Parent does not reference child directory '{child_dir}'",
                "severity": "low",
            })

    return findings


# ---------------------------------------------------------------------------
# Signal correlation
# ---------------------------------------------------------------------------

def load_active_signals(zone_root):
    """Load active signals grouped by subsystem."""
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    signal_dir = Path(al_path) / "signals"
    if not signal_dir.is_dir():
        return {}

    latest = {}
    for f in sorted(signal_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                eid = d.get("id") or d.get("signal_id")
                if eid:
                    latest[eid] = d
            except json.JSONDecodeError:
                continue

    by_subsystem = defaultdict(list)
    for eid, sig in latest.items():
        if sig.get("status") in ("active", "working", "acknowledged"):
            by_subsystem[sig.get("subsystem", "unknown")].append(eid)

    return by_subsystem


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_audit(zone_root, verbose=False):
    """Execute the full ladder audit and return structured results."""
    zone_root = os.path.abspath(zone_root)
    md_paths = discover_claude_mds(zone_root)

    if not md_paths:
        return {"error": "No CLAUDE.md files found", "zone_root": zone_root}

    nodes = build_chain(zone_root, md_paths)
    findings = cross_reference(nodes)
    signals_by_sub = load_active_signals(zone_root)

    # Build chain map
    chain_map = {}
    for rel, node in sorted(nodes.items(), key=lambda x: x[1]["depth"]):
        chain_map[rel] = {
            "depth": node["depth"],
            "rule_count": len(node["rules"]),
            "parent": node["parent"],
            "children": node["children"],
        }

    # Classify rules
    rule_classifications = []
    for rel, node in nodes.items():
        for rule in node["rules"]:
            if rule["type"] == "section":
                continue

            classification = {
                "file": rel,
                "rule": rule["text"][:80],
                "type": rule["type"],
                "line": rule["line"],
                "state": "coherent",
                "signal_correlation": [],
            }

            # Check for signal correlation based on rule tag
            tag = rule.get("tag", "")
            if tag:
                parts = tag.split(":")
                if len(parts) >= 2:
                    subsystem = parts[1]
                    if subsystem in signals_by_sub:
                        classification["signal_correlation"] = signals_by_sub[subsystem]

            rule_classifications.append(classification)

    # Apply finding states to rules
    for finding in findings:
        if finding.get("state"):
            for rc in rule_classifications:
                if finding["type"] == "sibling_duplicate":
                    if rc["file"] in finding.get("files", []):
                        key = finding["rule_key"]
                        if rc["rule"].lower()[:60].startswith(key[:30]):
                            rc["state"] = finding["state"]

    # Summary counts
    state_counts = defaultdict(int)
    for rc in rule_classifications:
        state_counts[rc["state"]] += 1

    result = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "zone_root": zone_root,
        "confidence": "preliminary",
        "confidence_note": (
            "This is a heuristic scan based on path nesting and lexical "
            "matching. Parent/child relationships are inferred from directory "
            "structure, not explicit governance linkage. Findings are suitable "
            "for surfacing potential issues, not for authoritative constitutional "
            "judgment. False positives are expected in vendor/nested-repo areas."
        ),
        "claude_md_count": len(md_paths),
        "rules_audited": len(rule_classifications),
        "chain_map": chain_map,
        "rule_classifications": rule_classifications,
        "findings": findings,
        "summary": dict(state_counts),
        "signal_subsystems_active": list(signals_by_sub.keys()),
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Ladder Coherence Audit — scan CLAUDE.md governance chain"
    )
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON (default: human-readable)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--output", default=None,
                        help="Write output to file instead of stdout")
    args = parser.parse_args()

    zone_root = args.project_dir or resolve_zone_root()
    result = run_audit(zone_root, verbose=args.verbose)

    output_text = ""
    if args.json:
        output_text = json.dumps(result, indent=2)
    else:
        output_text = format_human_readable(result)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output_text + "\n", encoding="utf-8")
        print(f"Audit written to {args.output}")
    else:
        print(output_text)


def format_human_readable(result):
    """Format audit result as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("LADDER COHERENCE AUDIT (preliminary / heuristic)")
    lines.append("=" * 60)
    lines.append(f"  Audited at:      {result.get('audited_at', '?')}")
    lines.append(f"  Zone root:       {result.get('zone_root', '?')}")
    lines.append(f"  Confidence:      {result.get('confidence', 'preliminary')}")
    lines.append(f"  CLAUDE.md files: {result.get('claude_md_count', 0)}")
    lines.append(f"  Rules audited:   {result.get('rules_audited', 0)}")
    lines.append("")
    lines.append("  NOTE: Parent/child inferred from path nesting, not explicit")
    lines.append("  governance linkage. Not authoritative constitutional judgment.")
    lines.append("")

    # Chain map
    lines.append("CHAIN MAP:")
    lines.append("-" * 60)
    for rel, info in sorted(result.get("chain_map", {}).items(),
                            key=lambda x: x[1]["depth"]):
        indent = "  " * info["depth"]
        parent_note = f" (parent: {info['parent']})" if info["parent"] else ""
        lines.append(f"  {indent}{rel} ({info['rule_count']} rules){parent_note}")
    lines.append("")

    # Summary
    summary = result.get("summary", {})
    lines.append("SUMMARY:")
    lines.append("-" * 60)
    for state, count in sorted(summary.items()):
        lines.append(f"  {state:<20} {count}")
    lines.append("")

    # Findings
    findings = result.get("findings", [])
    if findings:
        lines.append(f"FINDINGS ({len(findings)}):")
        lines.append("-" * 60)
        for f in findings:
            lines.append(f"  [{f['severity'].upper()}] {f['type']}: {f['detail']}")
            if "files" in f:
                for fpath in f["files"]:
                    lines.append(f"    - {fpath}")
    else:
        lines.append("No structural findings.")

    # Active signal subsystems
    subs = result.get("signal_subsystems_active", [])
    if subs:
        lines.append("")
        lines.append(f"ACTIVE SIGNAL SUBSYSTEMS: {', '.join(subs)}")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
