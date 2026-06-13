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
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path
# Shared active-ray predicate (tic 403): heat-based, retires acknowledged-as-active.
from lib.signal_active import is_active_ray
# Shared dehydration-aware doctrine resolver (tic 335 consumer-set fix): a
# dehydrated rung's promoted bodies live in a sibling ledger.md under
# `<!-- promoted from cpr_... -->` provenance markers, NOT in the compact
# CLAUDE.md as `<!-- --agnostic-candidate ... status:"promoted" -->` blocks. A
# rule scan that reads CLAUDE.md alone extracts ZERO promoted rules from a
# dehydrated root — it audits the table of contents, not the law.
from doctrine_surfaces import resolve_doctrine_surfaces  # noqa: E402
# Stage-3 down-lane finding-emit reuses the EXISTING manifold writer (no new
# store): dedup-at-write keyed on the deterministic signal_id (Dedup-at-Write +
# JSONL Atomic Writes KIs). `lib/` is on sys.path via the insert above.
from atomic_append import dedup_signal_append  # noqa: E402


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
# Ledger provenance marker: a dehydrated rung's bodies carry
# `<!-- promoted from cpr_xxx ... -->` / `<!-- promoted-spec ... -->` /
# `<!-- refined from ... -->` etc. — the body-side equivalent of a compact
# root's `--agnostic-candidate status:"promoted"` block.
LEDGER_PROVENANCE_RE = re.compile(
    r"<!--\s*(?:promoted-spec|promoted|absorbed|refined|extended|merged|superseded)\b",
    re.IGNORECASE,
)


def _extract_compact_rules(content):
    """Extract rules from a compact CLAUDE.md surface (methylated tags,
    --agnostic-candidate promoted blocks, section headings)."""
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


def _extract_ledger_rules(content):
    """Extract rules from a dehydrated rung's ledger.md surface.

    The ledger holds the relocated doctrine BODIES: each invariant is a
    `##`/`###` heading whose body carries a `<!-- promoted from cpr_... -->`
    provenance marker. We surface each provenance-marked entry as a promoted_cpr
    rule (lesson = the nearest preceding heading, i.e. the invariant's name) so
    the audit counts the actual law, not an empty compact root. Section headings
    are surfaced too, for parity with the compact extractor.
    """
    rules = []

    # Index headings by position so each provenance marker maps to its name.
    headings = [
        (m.start(), len(m.group(1)), m.group(2).strip())
        for m in SECTION_RE.finditer(content)
    ]

    def _name_for(offset):
        name = ""
        for pos, _depth, text in headings:
            if pos <= offset:
                name = text
            else:
                break
        return name

    for m in LEDGER_PROVENANCE_RE.finditer(content):
        offset = m.start()
        line_num = content[:offset].count("\n") + 1
        lesson = _name_for(offset) or "(ledger entry)"
        rules.append({
            "type": "promoted_cpr",
            "lesson": lesson,
            "line": line_num,
            "text": lesson[:80],
        })

    for pos, depth, text in headings:
        if depth <= 3:
            line_num = content[:pos].count("\n") + 1
            rules.append({
                "type": "section",
                "depth": depth,
                "heading": text,
                "line": line_num,
                "text": text,
            })

    return rules


def extract_rules(md_path):
    """Extract governance rules from a rung's doctrine surfaces.

    Dehydration-aware (tic 335): resolves the CLAUDE.md to its body-bearing
    surfaces — for a dehydrated rung that adds the sibling ledger.md where the
    promoted bodies live. Reading the compact CLAUDE.md alone extracts ZERO
    promoted rules post-dehydration (the bodies relocated to the ledger), so the
    coherence audit would silently report `rule_count: 0` for federation/CGG —
    the silent-degrade profile the consumer-set obligation (federation KI
    tic 333) names.
    """
    surfaces = resolve_doctrine_surfaces(str(md_path))
    if not surfaces:
        # md_path may not resolve as a doctrine surface; read it directly.
        try:
            return _extract_compact_rules(
                Path(md_path).read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError):
            return []

    rules = []
    for i, surface in enumerate(surfaces):
        try:
            content = Path(surface).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # First surface is the compact CLAUDE.md; any subsequent surface is a
        # dehydrated-body ledger.
        if i == 0:
            rules.extend(_extract_compact_rules(content))
        else:
            rules.extend(_extract_ledger_rules(content))
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
        if is_active_ray(sig):
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


# ---------------------------------------------------------------------------
# Stage-3 down-lane finding-emit (ladder-downlane-spec.md §2 Stage 3 / §3 KIND)
#
# The down-lane's smallest honest next build: give operational down-audits
# (FORK-2 N/A tic 378, FORK-3 needs_mechanization tic 379, ...) a home on the
# EXISTING signal manifold instead of leaving them as prose-only artifacts.
#
# Boundary (per the KIND table — this piece is LOW gate):
#   - read-only at the audited rung; the auditor judged, this only records
#   - append-only on the EXISTING manifold (COGNITIVE band); NO new store
#     (self-conditioning-discipline thin-terminal-residue boundary)
#   - dedup-at-write on the deterministic signal_id (Dedup-at-Write KI)
#   - does NOT open an arena, does NOT mutate doctrine — even a `damaging`
#     verdict only RECORDS here; routing to a /stage re-eval is Stage 4
#     (MEDIUM/HIGH gate, /review). An originator may produce artifacts; it may
#     never terminalize governance state (shared admission-gate, §1b).
# ---------------------------------------------------------------------------

DOWNAUDIT_FINDING_SIGNAL_TYPE = "ladder.down_audit_finding"

# Verdict vocabulary: the Stage-2 triad (clean | N/A | damaging) plus the two
# aggregation/lifecycle outcomes a recorded finding can carry —
# `needs_mechanization` (the all-rung-split forward carve-out: doctrine is fine,
# the enforcement substrate doesn't exist yet) and `hold_in_dissonance` (the
# first-class held state, §4). kind/volume are observability weights only; none
# of these auto-open an arena. `damaging`/`hold_in_dissonance` are WATCH so
# /review sees them; the forward/healthy verdicts stay quiet (INFO).
DOWNAUDIT_VERDICTS = {
    "clean":               {"kind": "INFO",  "volume": 10},
    "N/A":                 {"kind": "INFO",  "volume": 10},
    "needs_mechanization": {"kind": "WATCH", "volume": 25},
    "damaging":            {"kind": "WATCH", "volume": 40},
    "hold_in_dissonance":  {"kind": "WATCH", "volume": 35},
}


def compute_finding_signal_id(rung, ki_id, verdict):
    """Deterministic, condition-stable signal ID (Signal ID Determinism KI).

    Hashed from (signal_type, rung, ki_id, verdict) — NOT tic/timestamp — so a
    re-audit of the same (rung, ki, verdict) dedups idempotently, while a
    verdict-flip on the same (rung, ki) is a genuinely new finding (the rung's
    lived reality changed).
    """
    parts = [DOWNAUDIT_FINDING_SIGNAL_TYPE,
             f"ki_id={ki_id}", f"rung={rung}", f"verdict={verdict}"]
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:8]
    return f"sig_ladder_down_audit_finding_{h}"


def emit_downaudit_finding(zone_root, rung, ki_id, verdict, opened_tic, *,
                           reinforce_signal=False, summary=None, artifact=None,
                           source="ladder-audit.py", dry_run=False):
    """Append a thin terminal down-audit-finding residue to the signal manifold.

    Returns a result dict (ok, signal_id, written/deduplicated, summary). With
    dry_run=True nothing is written — the would-be signal is returned for
    preview (read-only-first: see the residue before persisting it).
    """
    if verdict not in DOWNAUDIT_VERDICTS:
        raise ValueError(
            f"Unknown down-audit verdict '{verdict}'. "
            f"Valid: {', '.join(sorted(DOWNAUDIT_VERDICTS))}"
        )

    vdef = DOWNAUDIT_VERDICTS[verdict]
    signal_id = compute_finding_signal_id(rung, ki_id, verdict)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    payload = {
        "rung": rung,
        "ki_id": ki_id,
        "verdict": verdict,
        "opened_tic": opened_tic,
        "reinforce_signal": bool(reinforce_signal),
    }
    if summary:
        payload["summary"] = summary
    if artifact:
        payload["finding_artifact"] = artifact

    signal = {
        "type": "signal",
        "id": signal_id,
        "signal_id": signal_id,
        "signal_type": DOWNAUDIT_FINDING_SIGNAL_TYPE,
        "kind": vdef["kind"],
        "band": "COGNITIVE",
        "status": "active",
        "volume": vdef["volume"],
        "max_volume": 100,
        "tick_count": 0,
        "subsystem": "ladder_downlane",
        "source": source,
        "source_date": date_str,
        "created_at": now.isoformat(),
        "payload": payload,
        "origin": "deterministic",
    }

    summary_text = summary or (
        f"down-audit {verdict}: {ki_id} @ {rung} (opened tic {opened_tic})"
    )
    if reinforce_signal:
        summary_text += " [reinforce: independent rediscovery]"

    if dry_run:
        return {"ok": True, "dry_run": True, "signal_id": signal_id,
                "summary": summary_text, "signal": signal}

    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    signal_dir = os.path.join(al_path, "signals")
    os.makedirs(signal_dir, exist_ok=True)
    signal_file = os.path.join(signal_dir, f"{date_str}.jsonl")
    manifest_path = os.path.join(signal_dir, "active-manifest.jsonl")

    written = dedup_signal_append(signal_file, signal, manifest_path=manifest_path)

    if written:
        manifest_entry = {
            "signal_id": signal_id,
            "signal_type": DOWNAUDIT_FINDING_SIGNAL_TYPE,
            "kind": vdef["kind"],
            "band": "COGNITIVE",
            "status": "active",
            "volume": vdef["volume"],
            "source_file": f"signals/{date_str}.jsonl",
            "summary": summary_text,
        }
        dedup_signal_append(manifest_path, manifest_entry)

    return {"ok": True, "dry_run": False, "written": written,
            "deduplicated": (not written), "signal_id": signal_id,
            "summary": summary_text}


def main():
    parser = argparse.ArgumentParser(
        description="Ladder Coherence Audit — scan CLAUDE.md governance chain; "
                    "Stage-3 down-lane finding-emit via the `emit-finding` subcommand"
    )
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON (default: human-readable)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--output", default=None,
                        help="Write output to file instead of stdout")

    # Optional subcommand. Bare invocation (no subcommand) preserves the legacy
    # structural-audit behavior so existing callers are unaffected.
    sub = parser.add_subparsers(dest="command")
    ef = sub.add_parser(
        "emit-finding",
        help="Stage-3 down-lane finding-emit: append a thin terminal residue "
             "(rung, ki_id, verdict, opened_tic) to the EXISTING signal "
             "manifold. Read-only/append-only; no doctrine mutation, no arena.")
    ef.add_argument("--rung", required=True,
                    help="Active rung the down-audit fired at "
                         "(e.g. context-grapple-gun, autonomous_kernel)")
    ef.add_argument("--ki-id", required=True, dest="ki_id",
                    help="Identifier of the federation KI under down-audit")
    ef.add_argument("--verdict", required=True, choices=sorted(DOWNAUDIT_VERDICTS),
                    help="Down-audit verdict")
    ef.add_argument("--opened-tic", required=True, type=int, dest="opened_tic",
                    help="Tic the finding was opened")
    ef.add_argument("--reinforce-signal", action="store_true", dest="reinforce_signal",
                    help="Independent-rediscovery reinforce flag (Stage 3)")
    ef.add_argument("--summary", default=None,
                    help="One-line human-readable tension/finding summary")
    ef.add_argument("--artifact", default=None,
                    help="Path to the prose down-audit artifact (provenance)")
    ef.add_argument("--source", default="ladder-audit.py")
    ef.add_argument("--dry-run", action="store_true", dest="dry_run",
                    help="Preview the residue without writing")
    ef.add_argument("--zone-root", default=None, dest="zone_root")

    args = parser.parse_args()

    if args.command == "emit-finding":
        zone_root = args.zone_root or args.project_dir or resolve_zone_root()
        result = emit_downaudit_finding(
            zone_root, args.rung, args.ki_id, args.verdict, args.opened_tic,
            reinforce_signal=args.reinforce_signal, summary=args.summary,
            artifact=args.artifact, source=args.source, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
        return

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
