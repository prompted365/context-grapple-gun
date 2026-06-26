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
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path
# Shared active-ray predicate (tic 403): heat-based, retires acknowledged-as-active.
# TERMINAL_STATUSES / TERMINAL_STRUCTURAL are the canonical reader-side terminal
# sets — a finding in one of these has left the LIVE set (Terminal-State Valve).
from lib.signal_active import is_active_ray, TERMINAL_STATUSES, TERMINAL_STRUCTURAL
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
from atomic_append import dedup_signal_append, atomic_append_jsonl  # noqa: E402


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


# ---------------------------------------------------------------------------
# Stage-0 active-rung selector (ladder-downlane-spec.md §2 Stage 0 / §3 KIND)
#
# The down-lane's smallest next build after Stage-3 finding-emit: discover which
# rungs are ACTIVE — running with their own agent and/or their own tic-zone —
# so the (forward) down-audit spends friction-budget only where there is real
# friction to test against, never as a blanket all-rungs sweep.
#
# Boundary (per the KIND table — this piece is LOW gate):
#   - read-only discovery: reads rung markers, .ticzone presence/mtime, git
#     last-commit recency, and agent-mailbox entry recency. Writes nothing; no
#     authority; no doctrine mutation; no arena.
#   - NON-blanket guard: dormant rungs are reported-but-EXCLUDED (their
#     structural coherence stays with the bare `run_audit` chain scan). The
#     exclusion is made transparent (Presence/Observation Fallacy Guard —
#     declare what the watcher can and cannot see, and what it dropped).
#   - gitignored-rung-safe: a sovereign Pattern-B rung (e.g. global-environmental-
#     fusion) is gitignored, so git-recency is N/A for it — git-recency is
#     fail-soft, NEVER the sole disqualifier; an own .ticzone is itself an
#     own-clock activity signal.
# ---------------------------------------------------------------------------

RUNG_TOPOLOGY_MARKERS = (
    ".federation-root", ".estate-root", ".domain-root", ".site-root",
)

# Default recency window: a rung is ACTIVE if it carries a rung marker AND at
# least one activity signal landed within this many days. Calibratable via
# --window-days (down-lane residue D2: an own .ticzone with no recent activity
# could otherwise read as a false-active — the mtime window is the discriminator).
# 30d is the "touched within ~a month" threshold; the known dormancy forks
# (canonical_user ~91d, biome ~51-66d, CPG ~95d) all sit well past it.
ACTIVE_RUNG_WINDOW_DAYS = 30

# Discovery noise — directories whose nested markers/ticzones are NOT governance
# rungs (build artifacts, vendor internals, and eval/test FIXTURE .ticzones such
# as evals/mogul-suborchestrator/files/workspace-* which exist to exercise the
# tooling, not to be down-audited).
_RUNG_SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", "dist", "build", "target",
    "evals", "fixtures",
}

# Files whose mtime does NOT indicate rung activity: OS metadata, dir-placeholder
# stubs, and editor/compiler transients. A .DS_Store touched by Finder (or a
# .gitkeep created once) must not make a dormant rung read as active (down-lane
# residue D2 false-active). The disk-truth newest-file signal filters these.
_NOISE_FILE_BASENAMES = {".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep"}
_NOISE_FILE_SUFFIXES = (".pyc", ".pyo", ".swp", ".swo", ".tmp", ".lock")


def _days_since_mtime(path, now=None):
    """Whole/fractional days since a path's mtime; None if it does not exist."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    return round((now - mtime) / 86400.0, 1)


def _git_last_commit_days(zone_root, rel_dir, now=None):
    """Days since the last commit touching rel_dir. None if gitignored / no git /
    not a repo (fail-soft — a gitignored sovereign rung legitimately has no git
    recency; that is N/A, never a disqualifier)."""
    try:
        out = subprocess.run(
            ["git", "-C", zone_root, "log", "-1", "--format=%ct", "--", rel_dir],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    ts = out.stdout.strip()
    if out.returncode != 0 or not ts:
        return None
    try:
        commit_ts = int(ts)
    except ValueError:
        return None
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    return round((now - commit_ts) / 86400.0, 1)


def _resolve_agent_mailbox(zone_root, rung_dir, ticzone):
    """Best-effort, NON-inventing rung→agent-mailbox resolution.

    Resolution order (each step explicit, never a fuzzy guess):
      1. an explicit `agent_mailbox` key in the rung's own .ticzone (forward-
         compatible; a structured declaration wins)
      2. a convention mailbox `ent_<basename_with_underscores>` IF that directory
         actually exists under audit-logs/agent-mailboxes/
    Returns the mailbox dir name or None. A None is HONEST: the holder of a
    sovereign office may not be derivable from the directory name (e.g.
    global-environmental-fusion is held by ent_homeskillet_gk, which no
    convention recovers) — the caller then relies on the own .ticzone as the
    activity signal instead of guessing a mailbox.
    """
    mbox_root = os.path.join(zone_root, "audit-logs", "agent-mailboxes")
    declared = (ticzone or {}).get("agent_mailbox")
    if declared:
        return declared if os.path.isdir(os.path.join(mbox_root, declared)) else None
    basename = os.path.basename(rung_dir.rstrip(os.sep))
    candidate = "ent_" + basename.replace("-", "_")
    if os.path.isdir(os.path.join(mbox_root, candidate)):
        return candidate
    return None


def _mailbox_recent_days(zone_root, mailbox, now=None):
    """Days since the newest entry in an agent mailbox; None if unresolved."""
    if not mailbox:
        return None
    mbox = os.path.join(zone_root, "audit-logs", "agent-mailboxes", mailbox)
    if not os.path.isdir(mbox):
        return None
    newest = None
    for root, _dirs, files in os.walk(mbox):
        for fn in files:
            d = _days_since_mtime(os.path.join(root, fn), now=now)
            if d is not None and (newest is None or d < newest):
                newest = d
    return newest


def _newest_file_days(dir_path, now=None, file_cap=50000):
    """Days since the newest file under dir_path — the DISK-TRUTH recency signal
    that survives .gitignore.

    The git-recency signal is blind to a gitignored rung that is nonetheless
    actively edited on disk (e.g. the CGG forge source: gitignored in canonical/
    yet the most-edited domain). Walking the tree for the newest mtime recovers
    that activity. Noise dirs (node_modules/.git/build/eval-fixtures) are pruned,
    so real rungs scan only a few hundred files. Returns (days, capped); capped
    is surfaced rather than silently truncating (no-silent-caps discipline).
    """
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    newest = None
    scanned = 0
    capped = False
    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [
            d for d in dirs
            if d not in _RUNG_SKIP_DIRS and not (d.startswith(".") and d != ".claude")
        ]
        for fn in files:
            # Skip dotfiles (markers, .ticzone, .gitignore, .DS_Store — config
            # already covered by the marker/own_ticzone signals) + OS-noise
            # basenames + editor/compiler transients. The newest-file signal is
            # CONTENT activity, not config churn.
            if (fn.startswith(".") or fn in _NOISE_FILE_BASENAMES
                    or fn.endswith(_NOISE_FILE_SUFFIXES)):
                continue
            try:
                mtime = os.path.getmtime(os.path.join(root, fn))
            except OSError:
                continue
            d = round((now - mtime) / 86400.0, 1)
            if newest is None or d < newest:
                newest = d
            scanned += 1
            if scanned >= file_cap:
                capped = True
                return newest, capped
    return newest, capped


def discover_active_rungs(zone_root, window_days=ACTIVE_RUNG_WINDOW_DAYS):
    """Stage-0: rank ACTIVE rungs (marker + >=1 recent activity signal) and
    transparently list the DORMANT ones that are excluded.

    Returns a dict {window_days, active:[...], dormant:[...], scope_declaration}.
    Each rung entry carries its evidence (the activity signals + why it is
    active/dormant) so the selector's judgment is auditable, not opaque.
    """
    zone_root = os.path.abspath(zone_root)
    now = datetime.now(timezone.utc).timestamp()
    root = Path(zone_root)

    # Collect candidate rung dirs: any dir carrying a topology marker OR its own
    # .ticzone (the site-rung marker / own clock).
    candidates = {}  # rel_dir -> {markers:set, abs}
    marker_names = sorted(set(RUNG_TOPOLOGY_MARKERS) | {".ticzone"})
    for marker in marker_names:
        for mp in sorted(root.rglob(marker)):
            parts = mp.relative_to(root).parts
            if any(p in _RUNG_SKIP_DIRS for p in parts):
                continue
            # Skip hidden ancestor dirs (except .claude); the marker itself is
            # a dotfile so only the ancestors (parts[:-1]) are checked.
            if any(p.startswith(".") and p != ".claude" for p in parts[:-1]):
                continue
            rung_dir = mp.parent
            rel = str(rung_dir.relative_to(root)) if rung_dir != root else "."
            entry = candidates.setdefault(rel, {"markers": set(), "abs": str(rung_dir)})
            entry["markers"].add(marker)

    active, dormant = [], []
    for rel, info in sorted(candidates.items()):
        abs_dir = info["abs"]
        markers = sorted(info["markers"])
        own_ticzone = ".ticzone" in info["markers"]

        ticzone_cfg = {}
        if own_ticzone:
            try:
                ticzone_cfg = json.loads(
                    Path(os.path.join(abs_dir, ".ticzone")).read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                ticzone_cfg = {}

        rung_name = ticzone_cfg.get("name") or (
            "canonical" if rel == "." else os.path.basename(abs_dir)
        )

        # Activity signals — each None if unavailable, else days-since-event.
        ticzone_days = (
            _days_since_mtime(os.path.join(abs_dir, ".ticzone"), now=now)
            if own_ticzone else None
        )
        marker_days = None
        for m in info["markers"]:
            if m == ".ticzone":
                continue
            d = _days_since_mtime(os.path.join(abs_dir, m), now=now)
            if d is not None and (marker_days is None or d < marker_days):
                marker_days = d
        git_days = _git_last_commit_days(zone_root, rel, now=now)
        mailbox = _resolve_agent_mailbox(zone_root, abs_dir, ticzone_cfg)
        mailbox_days = _mailbox_recent_days(zone_root, mailbox, now=now)
        files_days, files_capped = _newest_file_days(abs_dir, now=now)

        recent = {}
        for label, d in (("own_ticzone", ticzone_days), ("git", git_days),
                         ("mailbox", mailbox_days), ("marker", marker_days),
                         ("files", files_days)):
            if d is not None and d <= window_days:
                recent[label] = d

        has_rung_marker = bool(set(markers) & set(RUNG_TOPOLOGY_MARKERS)) or own_ticzone
        entry = {
            "rung": rung_name,
            "dir": rel,
            "markers": markers,
            "own_clock": own_ticzone,
            "agent_mailbox": mailbox,
            "signals": {
                "own_ticzone_days": ticzone_days,
                "git_last_commit_days": git_days,
                "mailbox_recent_days": mailbox_days,
                "marker_mtime_days": marker_days,
                "newest_file_days": files_days,
                "newest_file_scan_capped": files_capped,
            },
            "recent_signals": recent,
        }

        if has_rung_marker and recent:
            entry["selected"] = True
            entry["best_recency_days"] = min(recent.values())
            active.append(entry)
        else:
            entry["selected"] = False
            entry["excluded_reason"] = (
                "no rung marker" if not has_rung_marker
                else f"no activity signal within {window_days}d "
                     "(dormant — structural coverage stays with run_audit)"
            )
            dormant.append(entry)

    active.sort(key=lambda e: e["best_recency_days"])
    return {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "zone_root": zone_root,
        "window_days": window_days,
        "scope_declaration": (
            "Reads rung markers + .ticzone presence/mtime + git last-commit recency "
            "+ agent-mailbox entry recency + newest-file mtime (disk-truth, prunes "
            "noise dirs), from zone root downward (vendor/build/hidden/eval-fixture "
            "dirs skipped). git-recency is N/A for gitignored sovereign rungs "
            "(fail-soft, never a sole disqualifier) — the newest-file signal "
            "recovers their on-disk activity. CANNOT see: tic-counter advancement "
            "inside .ticzone (no counter field), nor a mailbox holder that is "
            "neither name-derivable nor declared via an agent_mailbox key; a capped "
            "newest-file scan is flagged (newest_file_scan_capped), never silent. "
            "ACTIVE = rung marker + >=1 activity signal within the window; DORMANT "
            "rungs are listed-but-excluded, NOT judged."
        ),
        "active_count": len(active),
        "dormant_count": len(dormant),
        "active": active,
        "dormant": dormant,
    }


def format_active_rungs(result):
    """Human-readable Stage-0 active-rung report."""
    lines = []
    lines.append("=" * 64)
    lines.append("LADDER DOWN-LANE · Stage-0 active-rung selector (read-only)")
    lines.append("=" * 64)
    lines.append(f"  Zone root:  {result.get('zone_root', '?')}")
    lines.append(f"  Window:     {result.get('window_days')}d")
    lines.append(
        f"  Active:     {result.get('active_count', 0)}    "
        f"Dormant: {result.get('dormant_count', 0)}"
    )
    lines.append("")
    lines.append("  scope: " + result.get("scope_declaration", ""))
    lines.append("")
    lines.append("ACTIVE RUNGS (marker + >=1 activity signal in window) → down-audit sites:")
    lines.append("-" * 64)
    if not result.get("active"):
        lines.append("  (none)")
    for e in result.get("active", []):
        sig = ", ".join(f"{k}={v}d" for k, v in sorted(e["recent_signals"].items()))
        mbox = e.get("agent_mailbox") or "—"
        clock = "own-clock" if e["own_clock"] else "no-own-clock"
        lines.append(f"  ▸ {e['rung']}  [{e['dir']}]")
        lines.append(f"      {clock} · mailbox:{mbox} · recent: {sig}  → SELECTED")
    lines.append("")
    lines.append("DORMANT / EXCLUDED (structural coverage stays with run_audit):")
    lines.append("-" * 64)
    if not result.get("dormant"):
        lines.append("  (none)")
    for e in result.get("dormant", []):
        lines.append(f"  · {e['rung']}  [{e['dir']}] — {e.get('excluded_reason', '')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage-1 KI-selection-by-applicability (ladder-downlane-spec.md §2 Stage 1 / §3 KIND)
#
# The down-lane's keystone read-only stage (C9_EXEC_GO, tic 470): for each ACTIVE
# rung (Stage 0), select which federation KIs plausibly REACH that rung — matched by
# the KI's ledger lane/terrain_class tags against the rung's declared concerns. The
# output is a ranked KI-per-rung CANDIDATE list that the (forward) Stage-2 down-audit
# consumes; it is NOT a down-audit verdict and NOT a mutation.
#
# Boundary (per the KIND table — this piece is LOW gate, "read-only matching"):
#   - read-only: reads the ledger tags + the Stage-0 active set + a rung-concern
#     source. Writes nothing; no authority; no doctrine mutation; no signal; no arena.
#   - CANDIDATE (center-hold): the rung-concern source is the tic-467 fork-B DERIVE —
#     heuristic, coherence-is-not-admission. A selection is a hypothesis about REACH,
#     never a verdict about FIT (Arena Velocity Guard; the fit test is the Stage-2
#     rehydration-in-spirit down-audit, which stays forward).
#   - NON-bias guard: selection must NOT pre-bias toward demotion. `needs_mechanization`
#     != defective (spec §2 S2 / readiness-map guardrail). Stage 1 answers only "does
#     this KI plausibly reach here?", never "should it be demoted?".
#   - honest reconciliation: the concern source is a tic-467 snapshot; the active set
#     is live. Rungs active-but-unsourced and sourced-but-now-dormant are surfaced
#     (Disagreement-as-evidence), never silently dropped or invented.
# ---------------------------------------------------------------------------

DEFAULT_CONCERN_SOURCE_REL = os.path.join(
    "governance", "c9-rung-concerns-derived-tic490.json")
LEDGER_REL = os.path.join("governance", "constitution-ledger", "ledger.md")

_LEDGER_INVARIANT_RE = re.compile(r"`invariant_id`:\s*`([a-z0-9_]+)`")
_LEDGER_TERRAIN_RE = re.compile(r"`terrain_class`:\s*`([a-z0-9_]+)`")
_LEDGER_TARGET_RUNG_RE = re.compile(r"`target_rung`:\s*`?([a-z0-9_]+)`?")
# Captures BOTH lane forms: the structured `\`lanes\`: [...]` tag (quoted,
# underscored) AND the inline `lanes: [...]` provenance-comment form (unquoted,
# hyphenated). The leading backtick of the structured form sits outside the match.
_LEDGER_LANES_RE = re.compile(r"lanes`?\s*:\s*\[([^\]]*)\]")
_LEDGER_HEADING_RE = re.compile(r"^#{2,4}\s+(.+)$", re.MULTILINE)


def _norm_tag(s):
    """Canonicalize a lane/terrain tag for cross-vocabulary matching: the ledger
    uses underscores (queue_and_state), the rung-concern derive uses hyphens
    (queue-and-state). Lowercase, strip quotes/space, fold `_` → `-`."""
    return s.strip().strip('"').strip("'").strip().lower().replace("_", "-")


def _parse_ledger_kis(ledger_path, include_body=False):
    """Parse the constitution-ledger into KI tag records (read-only).

    Returns [{invariant_id, name, terrain_class, lanes, target_rung, tags}]. `tags`
    is the normalized union of terrain_class + lanes — the match surface. Each KI is
    anchored on its `invariant_id` tag; its name is the nearest preceding heading; its
    terrain_class / lanes / target_rung are read from the span up to the next
    invariant. Both lane forms are captured (structured tag + inline provenance).

    With include_body=True each KI also carries `body` (the doctrine TEXT the Stage-2
    down-audit judges against, not just the tag name) + `body_truncated`. The body
    runs heading → the entry's OWN `<!-- promoted from … -->` provenance close — NOT
    the next `### ` (which would over-collect the trailing bullet-form KIs, the
    body-side of the same span-attribution discipline the tag scan applies).
    """
    try:
        content = Path(ledger_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    inv_matches = list(_LEDGER_INVARIANT_RE.finditer(content))
    headings = [(m.start(), m.group(1).strip())
                for m in _LEDGER_HEADING_RE.finditer(content)]

    def _heading_pos_before(offset):
        pos_out = None
        for pos, _text in headings:
            if pos <= offset:
                pos_out = pos
            else:
                break
        return pos_out

    # Entry boundary = the next `### ` heading (each KI is `### Name` → tag block →
    # verbatim → provenance → next `### `). Bounding the tag/lane collection at the
    # next h3 heading keeps each entry's `lanes:` attributed to ITS OWN KI — without
    # this, the LAST invariant_id's span ran to EOF and swallowed every provenance
    # `lanes:` in the trailing verbatim "Compact-Root Source Bodies" section (the
    # observed ki_session_memory_pickup 13-lane over-match).
    h3_starts = sorted(mm.start()
                       for mm in re.finditer(r"^### ", content, re.MULTILINE))

    def _entry_end(start):
        nxt_h3 = next((p for p in h3_starts if p > start), len(content))
        return nxt_h3

    def _name_before(offset):
        name = ""
        for pos, text in headings:
            if pos <= offset:
                name = text
            else:
                break
        return name

    kis = []
    for i, m in enumerate(inv_matches):
        start = m.start()
        # Bound at the next h3 heading OR the next invariant_id, whichever is nearer
        # (defensive: an entry with two invariant tags should not bleed into the next).
        next_inv = inv_matches[i + 1].start() if i + 1 < len(inv_matches) else len(content)
        end = min(_entry_end(start), next_inv)
        span = content[start:end]

        inv_id = m.group(1)
        terrain_m = _LEDGER_TERRAIN_RE.search(span)
        terrain = terrain_m.group(1) if terrain_m else ""
        target_m = _LEDGER_TARGET_RUNG_RE.search(span)
        target_rung = target_m.group(1) if target_m else ""

        lanes = set()
        for lm in _LEDGER_LANES_RE.finditer(span):
            for tok in lm.group(1).split(","):
                tok = tok.strip()
                if tok:
                    lanes.add(_norm_tag(tok))

        tags = set(lanes)
        if terrain:
            tags.add(_norm_tag(terrain))

        rec = {
            "invariant_id": inv_id,
            "name": _name_before(start) or inv_id.replace("ki_", "").replace("_", " "),
            "terrain_class": _norm_tag(terrain) if terrain else "",
            "lanes": sorted(lanes),
            "target_rung": target_rung,
            "tags": tags,
        }
        if include_body:
            body_start = _heading_pos_before(start)
            body_start = body_start if body_start is not None else start
            prov = content.find("<!-- promoted", start)
            body_end = end
            if prov != -1 and prov < end:
                close = content.find("-->", prov)
                body_end = (close + 3) if close != -1 else end
            body = content[body_start:body_end].strip()
            truncated = len(body) > DOWNAUDIT_MAX_BODY_CHARS
            if truncated:
                body = (body[:DOWNAUDIT_MAX_BODY_CHARS].rstrip() +
                        f"\n… [body truncated at {DOWNAUDIT_MAX_BODY_CHARS} chars — "
                        f"full at ledger entry `{inv_id}`]")
            rec["body"] = body
            rec["body_truncated"] = truncated
        kis.append(rec)
    return kis


def _load_rung_concerns(concern_source_path):
    """Load the rung-concern source (default: the tic-467 fork-B derive).

    Returns (concern_map, meta) where concern_map is {rung_path: {concerns,
    scores, recommend_fork_A_declare, raw_concerns}} keyed on the source's per-rung
    `path` so it joins to the Stage-0 active set `dir`. meta carries the source's
    `_`-prefixed provenance/fence fields (CANDIDATE marker, tic, status)."""
    try:
        data = json.loads(Path(concern_source_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    out = {}
    for _name, rec in (data.get("rungs") or {}).items():
        path = rec.get("path")
        if path is None:
            continue
        concerns = set(_norm_tag(c) for c in rec.get("candidate_concerns", []))
        scores = {}
        for r in rec.get("ranked", []):
            scores[_norm_tag(r.get("lane", ""))] = r.get("score", 1)
        out[path] = {
            "concerns": concerns,
            "scores": scores,
            "recommend_fork_A_declare": bool(rec.get("recommend_fork_A_declare")),
            "raw_concerns": rec.get("candidate_concerns", []),
        }
    meta = {k: v for k, v in data.items() if k.startswith("_")}
    return out, meta


def _match_kis_for_rung(kis, concerns, scores):
    """Rank the KIs that plausibly reach one rung (read-only).

    A KI reaches a rung if its terrain_class is in the rung's concerns OR its lanes
    intersect them. Score = sum of the rung's concern-score over each matched tag
    (concern-weighted reach); a terrain_class hit is flagged as the primary axis and
    breaks ties. Selection ≠ verdict — this is reach, not fit (Stage 2 tests fit)."""
    out = []
    for ki in kis:
        matched = sorted(ki["tags"] & concerns)
        if not matched:
            continue
        terrain_hit = bool(ki["terrain_class"]) and ki["terrain_class"] in concerns
        basis = []
        if terrain_hit:
            basis.append("terrain_class")
        if set(ki["lanes"]) & concerns:
            basis.append("lanes")
        score = sum(scores.get(t, 1) for t in matched)
        out.append({
            "invariant_id": ki["invariant_id"],
            "name": ki["name"],
            "terrain_class": ki["terrain_class"],
            "target_rung": ki["target_rung"],
            "matched_tags": matched,
            "match_basis": basis,
            "score": score,
        })
    out.sort(key=lambda c: (-c["score"],
                            0 if "terrain_class" in c["match_basis"] else 1,
                            c["invariant_id"]))
    return out


def select_kis_per_rung(zone_root, concern_source=None,
                        window_days=ACTIVE_RUNG_WINDOW_DAYS):
    """Stage-1: select the federation KIs that plausibly reach each ACTIVE rung.

    Read-only. Returns a CANDIDATE ranked KI-per-rung list plus an honest
    reconciliation of the live active set against the (snapshot) concern source.
    NOT a down-audit verdict (Stage 2) and NOT a mutation (Stage 4, /review-gated).
    """
    zone_root = os.path.abspath(zone_root)
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)

    ledger_path = os.path.join(al_path, LEDGER_REL)
    concern_source = concern_source or os.path.join(al_path, DEFAULT_CONCERN_SOURCE_REL)

    kis = _parse_ledger_kis(ledger_path)
    concern_map, concern_meta = _load_rung_concerns(concern_source)
    # Label follows the source file (never drift again): "derived-tic<N>" from the
    # source's own _tic, falling back to "derived" if the source carries no tic.
    _cs_label = (f"derived-tic{concern_meta.get('_tic')}"
                 if concern_meta.get("_tic") is not None else "derived")
    stage0 = discover_active_rungs(zone_root, window_days=window_days)

    active_dirs = {e["dir"] for e in stage0["active"]}
    sourced_paths = set(concern_map.keys())

    rungs_out = []
    for e in stage0["active"]:
        d = e["dir"]
        rec = concern_map.get(d)
        if rec is None:
            rungs_out.append({
                "rung": e["rung"], "dir": d,
                "concern_source": "missing",
                "note": "active in Stage-0 but absent from the concern source "
                        "(the tic-467 derive predates this rung's activation or did "
                        "not cover it) — a fork-A declaration or a re-derive is owed "
                        "before Stage-2 can down-audit it",
                "ki_candidates": [], "candidate_count": 0,
            })
            continue
        if not rec["concerns"]:
            rungs_out.append({
                "rung": e["rung"], "dir": d,
                "concern_source": _cs_label,
                "recommend_fork_A_declare": rec["recommend_fork_A_declare"],
                "concerns": sorted(rec["concerns"]),
                "note": "no concerns derived for this rung (fork-A declaration "
                        "advised) — no KI candidates until concerns exist",
                "ki_candidates": [], "candidate_count": 0,
            })
            continue
        cands = _match_kis_for_rung(kis, rec["concerns"], rec["scores"])
        rungs_out.append({
            "rung": e["rung"], "dir": d,
            "concern_source": _cs_label,
            "recommend_fork_A_declare": rec["recommend_fork_A_declare"],
            "concerns": sorted(rec["concerns"]),
            "ki_candidates": cands,
            "candidate_count": len(cands),
        })

    sourced_but_dormant = sorted(p for p in sourced_paths if p not in active_dirs)

    return {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "zone_root": zone_root,
        "_status": "Stage-1 KI-selection CANDIDATE — read-only; NOT a down-audit "
                   "verdict (Stage 2) and NOT a mutation (Stage 4, /review-gated)",
        "_fence": "center-hold: runs no down-audit, demotes nothing, emits no signal; "
                  "selection only. A candidate is a hypothesis about reach, not a "
                  "verdict about fit (Arena Velocity Guard).",
        "concern_source": os.path.relpath(concern_source, zone_root),
        "concern_source_meta": concern_meta,
        "scope_declaration": (
            "Reads the constitution-ledger KI tags (terrain_class + structured and "
            "inline `lanes`), the live Stage-0 active-rung set, and the rung-concern "
            "source (the tic-467 fork-B DERIVE — heuristic CANDIDATE, coherence-is-"
            "not-admission). MATCHES KI.tags ∩ rung.concerns with hyphen/underscore "
            "normalization. CANNOT see: whether a selected KI actually rehydrates in "
            "spirit at the rung (that is the Stage-2 down-audit, forward), nor fork-A "
            "declared concerns (not authored). The concern source is a tic-467 "
            "snapshot reconciled against the live active set: active-but-unsourced "
            "and sourced-but-now-dormant rungs are surfaced, never silently dropped "
            "or invented (Disagreement-as-evidence)."
        ),
        "ki_total_parsed": len(kis),
        "active_rung_count": len(stage0["active"]),
        "reconciliation": {
            "matched": sorted(d for d in active_dirs if d in sourced_paths),
            "active_but_unsourced": sorted(d for d in active_dirs
                                           if d not in sourced_paths),
            "sourced_but_now_dormant": sourced_but_dormant,
        },
        "rungs": rungs_out,
    }


def format_select_kis(result, top=15):
    """Human-readable Stage-1 KI-selection report."""
    lines = []
    lines.append("=" * 68)
    lines.append("LADDER DOWN-LANE · Stage-1 KI-selection-by-applicability (read-only)")
    lines.append("=" * 68)
    lines.append(f"  Zone root:       {result.get('zone_root', '?')}")
    lines.append(f"  Concern source:  {result.get('concern_source', '?')}")
    lines.append(f"  KIs parsed:      {result.get('ki_total_parsed', 0)}")
    lines.append(f"  Active rungs:    {result.get('active_rung_count', 0)}")
    lines.append("")
    lines.append("  " + result.get("_status", ""))
    lines.append("  " + result.get("_fence", ""))
    lines.append("")
    lines.append("  scope: " + result.get("scope_declaration", ""))
    rec = result.get("reconciliation", {})
    lines.append("")
    lines.append("RECONCILIATION (live active set vs tic-467 concern snapshot):")
    lines.append("-" * 68)
    lines.append(f"  matched:                 {', '.join(rec.get('matched', [])) or '(none)'}")
    lines.append(f"  active-but-unsourced:    {', '.join(rec.get('active_but_unsourced', [])) or '(none)'}")
    lines.append(f"  sourced-but-now-dormant: {', '.join(rec.get('sourced_but_now_dormant', [])) or '(none)'}")
    lines.append("")
    lines.append("KI CANDIDATES PER RUNG (ranked; selection ≠ verdict):")
    lines.append("-" * 68)
    for r in result.get("rungs", []):
        lines.append(f"  ▸ {r['rung']}  [{r['dir']}]  ({r.get('candidate_count', 0)} candidates)")
        if r.get("concern_source") == "missing":
            lines.append(f"      ⚠ {r.get('note', '')}")
            continue
        if r.get("candidate_count", 0) == 0:
            lines.append(f"      · {r.get('note', 'no candidates')}")
            if r.get("recommend_fork_A_declare"):
                lines.append("      · fork-A declaration advised")
            continue
        if r.get("recommend_fork_A_declare"):
            lines.append("      · fork-A declaration advised (derivation ambiguous)")
        lines.append(f"      concerns: {', '.join(r.get('concerns', []))}")
        shown = r["ki_candidates"][:top]
        for c in shown:
            basis = "+".join(c["match_basis"])
            lines.append(f"      [{c['score']:>3}] {c['name'][:54]}")
            lines.append(f"            ↳ {c['invariant_id']}  ({basis}: {', '.join(c['matched_tags'])})")
        extra = r["candidate_count"] - len(shown)
        if extra > 0:
            lines.append(f"      … + {extra} more (use --json for the full ranked list)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage-2 down-audit packet-assembler (ladder-downlane-spec.md §2 Stage 2 / §3 KIND)
#
# The down-lane's first JUDGMENT stage: the rehydration-in-spirit fit-test. For an
# ACTIVE rung, assemble the read-only PACKET a (read-only) ladder-auditor consumes
# to judge, per (rung, KI), whether the KI rehydrates IN SPIRIT here — clean | N/A |
# damaging — against the rung's real friction. The VERDICT is the auditor's act
# (returned as text); this assembler only PREPARES the judgment, and the orchestrator
# lands the verdict via `emit-finding` (Stage 3, already wired). A deterministic
# script cannot judge "rehydrates in spirit" — that is the whole point: Stage 2 is
# JUDGMENT, not the Stage-1 tag-match — so the buildable read-only piece is the
# packet + the mandatory scope-declaration envelope, NOT a verdict.
#
# Boundary (per the KIND table — this is the read-only HALF of the MEDIUM Stage-2
# gate; the judgment half extends the ladder-auditor agent, which is also read-only:
# tools Read/Grep/Glob, no Write/Edit/Bash):
#   - read-only: reads the Stage-1 selection, the ledger KI bodies, and the rung's
#     Stage-0 activity/friction signals. Writes nothing; no signal; no arena; no
#     doctrine mutation.
#   - CANDIDATE / center-hold: a selected KI is a hypothesis about REACH (Stage 1);
#     the packet does NOT pre-decide FIT. A `damaging` verdict (when the auditor
#     returns one) is a HYPOTHESIS routed to /stage (Stage 4, /review-gated), NEVER
#     an auto-demotion (Arena Velocity Guard); `needs_mechanization` != defective.
#   - scope-declared-before-judgment: the packet carries a MANDATORY scope envelope
#     (Presence/Observation Fallacy Guard) — structural facts pre-filled, judgment-
#     time slots left for the auditor. A down-audit without a declared fire-shape is
#     "hallucination dressed as judgment" (spec §2 S2).
#   - dual-mode + honest disagreement: default targets the rung's top-N Stage-1
#     candidates (pipeline-honest, in_selection:true); an explicit --ki-id may target
#     a KI OUTSIDE the selection (the spec's manual/from-root down-audit, e.g.
#     frame-protocol × fusion-outpost) — flagged in_selection:false so the
#     selection-vs-narrative disagreement is surfaced, never silently honored
#     (Disagreement-as-evidence).
# ---------------------------------------------------------------------------

DOWNAUDIT_MAX_BODY_CHARS = 4000

# The Stage-2 verdict taxonomy + the routing rule each verdict triggers. Carried IN
# the packet so the auditor judges against the same contract the orchestrator emits
# under (emit-finding) — no drift between what is asked and what is recorded.
DOWNAUDIT_VERDICT_CONTRACT = {
    "clean": "the KI rehydrates in spirit at this rung; cross-ray centroid-routed "
             "understanding holds here → record (Stage 3). If the rung re-derived "
             "this KI from its OWN recent friction, set reinforce:true (independent "
             "rediscovery → resilience evidence).",
    "N/A": "the KI does not reach this rung — correctly scoped away. This is a WIN, "
           "not a gap (the `concede_local` mirror) → record.",
    "needs_mechanization": "the KI is right and forward, but no enforcement substrate "
                           "exists here yet. NOT defective — do not route to demote. "
                           "→ record; aggregation across rungs decides if system-wide.",
    "damaging": "the KI rehydrates as foreign, N/A-but-load-bearing, or actively "
                "harmful here. This is a HYPOTHESIS, not a verdict (Arena Velocity "
                "Guard) → record + route to a /stage re-eval arena (Stage 4, "
                "/review-gated). NEVER an auto-demotion.",
    "hold_in_dissonance": "a genuine unresolved tension between the KI and this rung's "
                          "lived reality; hold the contradiction rather than force a "
                          "premature collapse (§4) → record as the held band.",
}


def _resolve_rung_in_selection(sel, rung):
    """Find a rung record in the Stage-1 selection by dir, name, or basename."""
    for r in sel["rungs"]:
        if rung in (r["dir"], r["rung"], os.path.basename(r["dir"])):
            return r
    return None


def _downaudit_target(ki, cand):
    """Build the per-KI target entry for the down-audit packet (read-only).

    `ki` is the parsed ledger record (with body); `cand` is the Stage-1 candidate
    record for this rung if the KI is in-selection, else None (explicit/outside-
    selection target — the disagreement is surfaced via in_selection:false)."""
    if ki is None:
        return None
    entry = {
        "invariant_id": ki["invariant_id"],
        "name": ki["name"],
        "terrain_class": ki["terrain_class"],
        "lanes": ki["lanes"],
        "target_rung": ki["target_rung"],
        "in_selection": cand is not None,
        "body": ki.get("body", ""),
        "body_truncated": ki.get("body_truncated", False),
    }
    if cand is not None:
        entry["selection"] = {
            "score": cand["score"],
            "match_basis": cand["match_basis"],
            "matched_tags": cand["matched_tags"],
        }
    else:
        entry["selection_note"] = (
            "OUTSIDE the rung's Stage-1 selection — explicit/manual down-audit "
            "(the tic-467 concern derive does not connect this KI to this rung). "
            "Surfaced as Disagreement-as-evidence, not silently honored; the "
            "down-audit verdict is still valid but the SELECTION gap is itself a "
            "signal (fork-A concern declaration may be owed for this rung)."
        )
    return entry


def build_downaudit_packet(zone_root, rung, ki_ids=None, top=3,
                           opened_tic=None, window_days=ACTIVE_RUNG_WINDOW_DAYS):
    """Stage-2: assemble the read-only down-audit packet for one ACTIVE rung.

    Read-only. Returns the packet a (read-only) ladder-auditor consumes to judge
    rehydration-in-spirit per (rung, KI). NOT a verdict (the auditor judges) and NOT
    a mutation (Stage 4, /review-gated). The orchestrator lands the auditor's returned
    verdict via `emit-finding` (Stage 3).
    """
    zone_root = os.path.abspath(zone_root)
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    ledger_path = os.path.join(al_path, LEDGER_REL)

    sel = select_kis_per_rung(zone_root, window_days=window_days)
    rung_rec = _resolve_rung_in_selection(sel, rung)

    base = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "zone_root": zone_root,
        "stage": "C9 Stage-2 down-audit packet (read-only PREP — NOT a verdict)",
        "_status": "Stage-2 down-audit PACKET — read-only; the verdict is the "
                   "(read-only) ladder-auditor's act, landed by the orchestrator via "
                   "emit-finding (Stage 3). NOT a mutation (Stage 4, /review-gated).",
        "_fence": "center-hold: the packet runs no down-audit itself, demotes nothing, "
                  "emits no signal, opens no arena. A selected KI is a hypothesis about "
                  "reach (Stage 1); this packet does not pre-decide fit. A `damaging` "
                  "verdict is a hypothesis → /stage (Stage 4), NEVER auto-demote.",
        "requested_rung": rung,
        "opened_tic": opened_tic,
    }

    if rung_rec is None:
        # Honest: the down-lane is active-rung-only. Surface whether the rung is
        # dormant/unknown vs active-but-unsourced — never invent a packet.
        recon = sel.get("reconciliation", {})
        base["ok"] = False
        base["error"] = (
            f"rung '{rung}' is not in the live Stage-1 active selection — the "
            "down-lane is active-rung-only (dormant/unknown rungs stay with the "
            "structural run_audit chain scan). Active rungs this tic: "
            + ", ".join(sorted(r["dir"] for r in sel["rungs"]))
        )
        base["reconciliation"] = recon
        return base

    kis = _parse_ledger_kis(ledger_path, include_body=True)
    ki_by_id = {k["invariant_id"]: k for k in kis}
    in_sel = {c["invariant_id"]: c for c in (rung_rec.get("ki_candidates") or [])}

    targets, unresolved = [], []
    if ki_ids:
        for kid in ki_ids:
            ki = ki_by_id.get(kid)
            if ki is None:
                unresolved.append({"invariant_id": kid,
                                   "error": "not found in the constitution-ledger"})
                continue
            targets.append(_downaudit_target(ki, in_sel.get(kid)))
    else:
        for cand in (rung_rec.get("ki_candidates") or [])[:top]:
            ki = ki_by_id.get(cand["invariant_id"])
            t = _downaudit_target(ki, cand)
            if t is not None:
                targets.append(t)

    # Rung friction (read-only): Stage-0 activity signals for this rung + active
    # signal subsystems with a name-overlap flag. The auditor reads the rung's own
    # CLAUDE.md chain + recent friction itself (it has Read/Grep/Glob) — the packet
    # gives it the hard-to-locate ledger KI bodies + the pointers, never pre-judges.
    stage0 = discover_active_rungs(zone_root, window_days=window_days)
    rung_dir = rung_rec["dir"]
    stage0_entry = next((e for e in stage0["active"] if e["dir"] == rung_dir), None)
    signals_by_sub = load_active_signals(zone_root)
    rung_basename = os.path.basename(rung_dir)
    overlapping = {sub: ids for sub, ids in signals_by_sub.items()
                   if rung_basename in sub or sub in rung_dir or sub in rung_rec["rung"]}

    base.update({
        "ok": True,
        "rung": rung_rec["rung"],
        "rung_dir": rung_dir,
        "concern_source": rung_rec.get("concern_source"),
        "rung_concerns": rung_rec.get("concerns", []),
        "recommend_fork_A_declare": rung_rec.get("recommend_fork_A_declare", False),
        "target_mode": "explicit_ki_ids" if ki_ids else f"top_{top}_stage1_candidates",
        "targets": targets,
        "unresolved_ki_ids": unresolved,
        "friction": {
            "rung_activity_signals": (stage0_entry or {}).get("recent_signals", {}),
            "rung_doctrine_chain_cmd":
                f"python3 cgg-runtime/scripts/lib/load_doctrine_chain.py "
                f"{rung_dir}  # the auditor reads the rung's CLAUDE.md chain here",
            "active_signal_subsystems": sorted(signals_by_sub.keys()),
            "subsystems_name_overlapping_rung": overlapping,
            "friction_scope_note": (
                "Signal subsystems are federation-wide; a rung-name overlap is a "
                "weak heuristic. The auditor must read the rung's OWN recent friction "
                "(its CLAUDE.md chain, recent born/arena/signal surfaces) and declare "
                "what it could and could NOT access — do not infer friction from this "
                "list alone."
            ),
        },
        "verdict_contract": DOWNAUDIT_VERDICT_CONTRACT,
        "scope_declaration_envelope": {
            "prefilled_by_assembler": {
                "loaded": "the rung's Stage-1 selection (live), each target KI's BODY "
                          "from the constitution-ledger (read-only), the rung's Stage-0 "
                          "activity signals, the active-signal subsystem list",
                "concern_source": rung_rec.get("concern_source"),
                "concern_source_caveat": "the rung-concern derive is the tic-467 fork-B "
                                         "CANDIDATE (coherence-is-not-admission); a thin "
                                         "or fork-A-flagged concern set is itself signal",
                "cannot_see_from_assembler": "whether each KI actually rehydrates in "
                          "spirit (THAT is the auditor's judgment), the rung's live "
                          "operational friction beyond mtime recency, any non-name-"
                          "matched signal relevance",
            },
            "auditor_must_declare_at_judgment": [
                "which rung surfaces it actually read (CLAUDE.md chain, which friction)",
                "which friction it could NOT access (the fire-shape envelope)",
                "the reflexive caveat where it judges a KI in its own operating set "
                "(D3: a dulling auditor cannot fully audit the doctrine that dulled it)",
            ],
        },
        "emit_contract": {
            "note": "Return one verdict block per target KI (verdict + scope + "
                    "reasoning + reinforce flag). The ORCHESTRATOR lands each via: "
                    "ladder-audit.py emit-finding --rung <dir> --ki-id <id> "
                    "--verdict <v> --opened-tic <N> [--reinforce-signal] [--summary]. "
                    "The auditor does NOT write (no Bash/Write/Edit).",
            "valid_verdicts": sorted(DOWNAUDIT_VERDICTS),
        },
        "scope_declaration": (
            "Read-only Stage-2 PACKET assembler. Reads: the live Stage-1 selection, "
            "each target KI's ledger BODY (heading→own provenance close, bounded so it "
            "does not over-collect trailing bullet KIs), the rung's Stage-0 activity "
            "signals, the active-signal subsystem list. Writes nothing, emits no "
            "signal, opens no arena. CANNOT judge fit (the auditor does) and does not "
            "pre-bias toward demotion. Dual-mode: default = top-N in-selection "
            "candidates (pipeline-honest); explicit --ki-id = may be outside-selection "
            "(flagged in_selection:false, the disagreement surfaced)."
        ),
    })
    return base


def format_downaudit_packet(packet):
    """Human-readable Stage-2 down-audit packet."""
    lines = []
    lines.append("=" * 70)
    lines.append("LADDER DOWN-LANE · Stage-2 down-audit PACKET (read-only prep; NOT a verdict)")
    lines.append("=" * 70)
    if not packet.get("ok"):
        lines.append(f"  ✗ {packet.get('error', 'could not assemble packet')}")
        return "\n".join(lines)
    lines.append(f"  Rung:            {packet['rung']}  [{packet['rung_dir']}]")
    lines.append(f"  Opened tic:      {packet.get('opened_tic')}")
    lines.append(f"  Concern source:  {packet.get('concern_source')}  "
                 f"(fork-A advised: {packet.get('recommend_fork_A_declare')})")
    lines.append(f"  Rung concerns:   {', '.join(packet.get('rung_concerns', [])) or '(none)'}")
    lines.append(f"  Target mode:     {packet.get('target_mode')}")
    lines.append("")
    lines.append("  " + packet.get("_status", ""))
    lines.append("  " + packet.get("_fence", ""))
    lines.append("")
    lines.append("  scope: " + packet.get("scope_declaration", ""))
    lines.append("")
    lines.append(f"TARGET KIs ({len(packet.get('targets', []))}) — judge rehydration-in-spirit per KI:")
    lines.append("-" * 70)
    for t in packet.get("targets", []):
        flag = "IN-SELECTION" if t["in_selection"] else "⚠ OUTSIDE-SELECTION (explicit)"
        lines.append(f"  ▸ {t['name'][:60]}")
        lines.append(f"      {t['invariant_id']}  [{flag}]  terrain={t['terrain_class']} "
                     f"target_rung={t['target_rung']}")
        if t.get("selection"):
            s = t["selection"]
            lines.append(f"      reach: score={s['score']} "
                         f"basis={'+'.join(s['match_basis'])} tags={s['matched_tags']}")
        elif t.get("selection_note"):
            lines.append(f"      {t['selection_note'][:120]}")
        body = (t.get("body") or "").strip().replace("\n", " ")
        lines.append(f"      body: {body[:200]}{'…' if len(body) > 200 else ''}")
    for u in packet.get("unresolved_ki_ids", []):
        lines.append(f"  ✗ {u['invariant_id']} — {u['error']}")
    lines.append("")
    lines.append("VERDICT CONTRACT (the auditor returns one block per KI):")
    lines.append("-" * 70)
    for v in sorted(packet.get("verdict_contract", {})):
        lines.append(f"  · {v}: {packet['verdict_contract'][v][:88]}")
    lines.append("")
    lines.append("FRICTION + SCOPE: the auditor reads the rung's own CLAUDE.md chain "
                 "(load_doctrine_chain) + recent friction and DECLARES its fire-shape "
                 "envelope before judging.")
    lines.append("EMIT: orchestrator lands each verdict via `ladder-audit.py emit-finding` "
                 "(Stage 3). The auditor does not write.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage-4 finding routing + held-state durability + arena-brief
#   (ladder-downlane-spec.md §2 Stage 4, §4 hold_in_dissonance, §3 KIND table)
#
# Stage 4 is the down-lane's ONLY mutation locus — and even here the buildable
# pieces are read-only or signal-state, NEVER doctrine. The HIGH-gate doctrine
# inscription (demote/reword/reinforce) is /review-only (Review-Execution-
# Delegation); these surfaces only PREPARE and OBSERVE it:
#
#   - `list-findings`  : read-only projection of the down-audit finding set,
#                        grouped by Stage-3/4 routing, with held-band staleness
#                        (§4 + D4). The /review-surfaced down-lane view.
#   - `stage-brief`    : read-only — assembles the `/stage` arena brief for a
#                        `damaging` (or re-tested held) finding. Does NOT open the
#                        arena (the orchestrator runs /stage) and does NOT inscribe.
#                        Mirrors the Stage-2 packet-assembler discipline.
#   - `resolve-finding`: signal-state transition (NOT doctrine) — closes a held/
#                        damaging finding signal AFTER /review rules, carrying a
#                        mandatory receipt (terminal-state-change-requires-receipt).
#                        /review-gated; does not touch the ledger.
#
# Center-hold (do not violate): a `damaging` finding is a HYPOTHESIS routed to an
# arena, never an auto-demotion (Arena Velocity Guard). A held dissonance is
# preserved, re-tested at /review, never auto-resolved (§4). `needs_mechanization`
# is NOT defective. The arena's verdict routes to /review; only /review inscribes.
# ---------------------------------------------------------------------------

# How a recorded Stage-2/3 verdict routes at Stage 4 (the §2 Stage-3 routing rule
# + the Stage-4 mutation locus). Read-only classification — nothing here mutates
# doctrine; `damaging` opens a /stage arena (stage-brief), the rest record.
DOWNAUDIT_ROUTING = {
    "clean":               "record (healthy; reinforce-signal if independent rediscovery → Stage 5)",
    "N/A":                 "record (correctly scoped away — a concede_local win)",
    "needs_mechanization": "record + aggregate (forward, NOT defective; breadth decides system-wide)",
    "damaging":            "→ /stage re-eval arena (stage-brief) — HYPOTHESIS, never auto-demote",
    "hold_in_dissonance":  "held band (§4) — preserve tension; re-test at /review, never auto-resolve",
}

# A held dissonance carried this many tics without re-test is flagged for re-test
# at /review (down-lane residue D4 — held dissonances must not be silently immortal).
DISSONANCE_STALE_TICS = 8

# Campaign coverage heuristic (down-lane-run driver): a (rung, KI) pair last
# down-audited this many tics ago is flagged "stale" (a re-audit candidate). Longer
# than DISSONANCE_STALE_TICS — a held-tension re-test is more urgent than a clean/N/A
# coverage refresh. Heuristic + overridable (--coverage-stale-tics); NEVER a gate.
DOWNAUDIT_COVERAGE_STALE_TICS = 12

# M2 staleness-scan heuristic (staleness-routing-spec.md §2/§3 S0): a doctrine
# surface whose `last_validated_tic` frontmatter is this many tics behind the current
# federation tic is flagged freshness-OVERDUE — overdue for a re-validation CHECK
# against current substrate (the Volatility Handling Law's L4-probe), NOT a verdict
# that it is stale. Longer than the coverage window — a spec's claims drift slower
# than audit-coverage of a (rung,KI) pair. Heuristic + overridable
# (--freshness-stale-tics); NEVER a gate. SR1 (per-terrain/per-rung calibration) is a
# forward residue — a founding KI goes stale slower than a fast-churning estate spec;
# this global default is the `DOWNAUDIT_COVERAGE_STALE_TICS` precedent (a real,
# overridable window, never a gate), refined per-terrain later.
FRESHNESS_STALE_TICS = 50

# The doctrine surfaces the freshness scan reads (declared scope, not the whole repo):
# the kernel-rung specs carry the `status` + `last_validated_tic` frontmatter
# convention (autonomous_kernel/CLAUDE.md "Status Convention for Specs"). The scan is
# bounded to this surface; surfaces WITHOUT the frontmatter are out-of-signal-scope
# (declared), never inferred-fresh. Overridable via --freshness-root.
FRESHNESS_SCAN_ROOT_REL = "autonomous_kernel"

# The Stage-4 arena's legal outcomes (the 8-outcome taxonomy from
# doctrine-lifecycle-spec.md §6 + `reinforce` + the net-new `hold_in_dissonance`).
# Each routes to /review as a VERDICT — never self-inscribed by this script.
DOWNAUDIT_ARENA_OUTCOMES = {
    "confirmed": "hydrates cleanly under arena pressure; the `damaging` first-read "
                 "was local — no change to the KI.",
    "needs_clarification": "spirit right, local interpretation unstable → reword the "
                           "expression so the spirit carries (no scope change).",
    "needs_mechanization": "doctrine right, no enforcement surface exists here yet → "
                           "forward, NOT a demote.",
    "overbroad_demote": "the KI over-claimed scope → lower its target_rung or scope "
                        "it locally.",
    "localized": "true only at a narrower rung → relocate; prevent false "
                 "universalization.",
    "stale": "no longer matches current operating reality → staleness route "
             "(clarify/demote/retire/supersede).",
    "conflict_found": "collides with a sibling principle or local constraint → "
                      "reconcile; do not silently overwrite.",
    "exception_needed": "the KI survives but a bounded exception must be recorded.",
    "recenter_required": "right region, wrong/incomplete centroid → recenter, not "
                         "reword.",
    "reinforce": "the RUNG is wrong, not the KI; the friction is a local error and the "
                 "KI holds (often → a born truth at the rung; Stage 5 reinforced_by).",
    "hold_in_dissonance": "genuine unresolved tension → hold the contradiction rather "
                          "than force a premature collapse (§4 held band).",
}

# ─── M1 piece 3: RBD demote-admission predicate (build-and-gate) ─────────────────
# The federation KI `rollback-velocity-must-exceed-attachment-velocity` is made an
# ADMISSION PREDICATE on a Stage-4 DEMOTE-class outcome: a demote whose rollback is
# slower than attachment (velocity_ratio < 1), or whose reversion is not clean, is
# INADMISSIBLE until reversion is made clean. The doctrine rollback-drill lane
# (audit-logs/rollback-drills/RBD-*.json) ALREADY COMPUTES the verdict over doctrine
# surfaces (tic-494 memo §1 Half B) — stage-brief WIRES it as the reversibility-proof
# INPUT; it does NOT rebuild the measurement (the double-make NAVIGATION prevents).
#
# Build-and-gate (cgg-ledger#build-and-gate-ratified-flag-gated-consumer): ships DORMANT —
# RBD_DEMOTE_ADMISSION_RATIFIED defaults False. While dormant the RBD verdict is surfaced
# as ADVISORY evidence (rbd_would_gate_outcomes) and blocks nothing. /review 505 flips the
# flag (ratification IS the flip; no further code change) → the predicate becomes a HARD
# gate (rbd_gated_outcomes) /review must honor. Dual-proven: dormancy (advisory, blocks
# nothing) + activation (--force-rbd-ratified → the hard-gate surface). Center-hold:
# read-only — stage-brief inscribes nothing; the demote DOCTRINE inscription stays
# /review-only (Review-Execution-Delegation), unchanged.
RBD_DEMOTE_ADMISSION_RATIFIED = True  # build-and-gate RATIFIED at /review 505 (tic 505, Architect-gated) — now a HARD admission predicate on demote-class outcomes

# The scope-reducing / scope-removing Stage-4 outcomes the RBD reversibility predicate
# guards. `overbroad_demote` is the canonical demote; `localized` (relocate to a narrower
# rung) and `stale` (clarify/demote/retire/supersede) are demote-adjacent — each
# accumulates the irreversible dependency the KI forbids until rollback is proven.
RBD_DEMOTE_CLASS_OUTCOMES = ("overbroad_demote", "localized", "stale")

# ─── M1 complement: the RBD drill AUTO-INVOCATION flag (build-and-gate; tic 507) ───
# RBD_DEMOTE_ADMISSION_RATIFIED (above) made the RBD verdict a HARD gate on demote-class
# outcomes (/review 505). The RBD re-runner `rbd-drill-run` (tic 506) made the `admissible`
# path lifecycle-reachable. The residual the tic-506 build receipt named honestly: the
# /review-flow wiring that AUTO-invokes the re-runner on a demote-class verdict is
# "documented-not-yet-mechanized" — today the /review operator HAND-runs
# `rbd-drill-run --target-commit … --cprs …` for a demote-class target. This flag gates
# that auto-invocation.
#
# It is ORTHOGONAL to RBD_DEMOTE_ADMISSION_RATIFIED (do not conflate): that flag decides
# whether the RBD verdict BLOCKS a demote (ratified True); THIS flag decides whether a
# missing fresh drill is AUTO-PRODUCED on a demote-class verdict vs hand-run by the
# operator. Auto-producing the reversibility evidence is itself a (small, regenerable)
# governance write, so it ships human-gated.
#
# Build-and-gate (cgg-ledger#build-and-gate-ratified-flag-gated-consumer): ships DORMANT —
# default False. While dormant `rbd_autodrill_for_demote` surfaces the exact `rbd-drill-run`
# PLAN it WOULD fire (writes nothing, fires nothing); /review 507 flips it True → the
# `rbd-autodrill` subcommand FIRES the re-runner (regenerable drill record only). The
# cadence stays EVENT-DRIVEN (fires on the consuming demote-class verdict, never periodic —
# the tic-506 born; a periodic drill with no demote pending is the mounted-bear). Dual-
# proven: dormancy (plan-only, lane unchanged) + activation (--force-autodrill → fires +
# the consumer reads the fresh `admissible`, proven in isolated test repos). Center-hold:
# read-only on DOCTRINE — the demote DECISION stays HIGH-gate /review-only; the read-only
# Stage-4 stage-brief surfaces the PLAN only and never fires regardless of the flag.
RBD_AUTODRILL_RATIFIED = False  # build-and-gate: DORMANT — /review 507 flips False→True (ratification IS the flip; no further code change)

# Doctrine rollback-drill lane (tic-130-era records; tic-494 memo §1 Half B).
ROLLBACK_DRILLS_REL = os.path.join("audit-logs", "rollback-drills")

# Recommended justification_class vocabulary for a resolve-finding receipt
# (terminal-state-change-requires-receipt KI). Free-form is accepted, but a
# resolution should name WHY the held/damaging signal may now go terminal.
DOWNAUDIT_RESOLUTION_CLASSES = (
    "arena_adjudicated",     # a /stage arena → /review verdict resolved it
    "rung_matured",          # the rung grew the missing enforcement/context
    "sibling_ki_landed",     # a sibling KI landed and dissolved the tension
    "architect_ruled",       # the Architect ruled on the dissonance
    "local_error_confirmed", # the friction was a local error; the KI holds (reinforce)
    "superseded_by_redown",  # a fresh down-audit produced a different verdict
)


def _resolve_federation_tic(zone_root):
    """Best-effort read of the current federation tic (domain_counter_after) from
    the canonical tic log (Temporal Scope Discipline). None if unavailable."""
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    tic_dir = Path(al_path) / "tics"
    if not tic_dir.is_dir():
        return None
    latest = None
    for f in sorted(tic_dir.glob("*.jsonl")):
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            val = d.get("domain_counter_after")
            if isinstance(val, int):
                latest = val
    return latest


def load_downaudit_findings(zone_root):
    """Read every down-audit finding from the signal manifold, projected
    terminal-per-id (latest entry wins — the Terminal-State Valve discipline).

    Returns a list of the latest signal dict per signal_id. Read-only. The
    active-manifest is skipped (thin entries without payload); the full signal
    rows in the daily files carry the (rung, ki_id, verdict, opened_tic) payload.
    """
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    signal_dir = Path(al_path) / "signals"
    if not signal_dir.is_dir():
        return []
    latest = {}
    for f in sorted(signal_dir.glob("*.jsonl")):
        if f.name == "active-manifest.jsonl":
            continue
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("signal_type") != DOWNAUDIT_FINDING_SIGNAL_TYPE:
                continue
            eid = d.get("signal_id") or d.get("id")
            if eid:
                latest[eid] = d
    return list(latest.values())


def _finding_entry(sig, current_tic=None):
    """Normalize a finding signal into a flat entry (read-only)."""
    payload = sig.get("payload", {})
    verdict = payload.get("verdict", "?")
    entry = {
        "signal_id": sig.get("signal_id") or sig.get("id"),
        "verdict": verdict,
        "rung": payload.get("rung"),
        "ki_id": payload.get("ki_id"),
        "opened_tic": payload.get("opened_tic"),
        "reinforce_signal": payload.get("reinforce_signal", False),
        "status": sig.get("status", "active"),
        "active": is_active_ray(sig),
        "summary": payload.get("summary") or sig.get("summary", ""),
        "artifact": payload.get("finding_artifact"),
        "routing": DOWNAUDIT_ROUTING.get(verdict, "record"),
    }
    resolution = payload.get("resolution")
    if resolution:
        entry["resolution"] = resolution
    if (verdict == "hold_in_dissonance" and entry["active"]
            and current_tic is not None and isinstance(entry["opened_tic"], int)):
        held = current_tic - entry["opened_tic"]
        entry["tics_held"] = held
        entry["stale_for_retest"] = held >= DISSONANCE_STALE_TICS
    return entry


def _finding_is_terminal(sig):
    """Terminal-State Valve on the down-lane READ surface: a finding whose latest
    signal row is terminal (resolved / dismissed / superseded — by `status` or v2
    `structural_status`) has left the LIVE finding set. The read projection
    excludes it from the active verdict grouping/counts /review consults for live
    attention, but surfaces it in a separate receipt-bearing bucket so the
    resolution never goes dark. Scoped to TERMINAL statuses only — a cooled-but-
    unresolved (carried/dimmed) finding stays in the live set, since it is quiet,
    not closed. The data loader (load_downaudit_findings) stays full terminal-per-
    id; this valve lives in the projection, where resolve-finding idempotency and
    stage-brief lookup still need to see terminal rows."""
    return (sig.get("status") in TERMINAL_STATUSES
            or sig.get("structural_status") in TERMINAL_STRUCTURAL)


def _finding_aggregation(findings, ki_id, active_rung_count=None):
    """Breadth of a KI's down-audit findings across active rungs (the fault-locator,
    spec §2 Stage 2 / Disagreement-as-evidence). single | multi | all-rung."""
    rungs = sorted({(f.get("payload", {}).get("rung") or "")
                    for f in findings
                    if f.get("payload", {}).get("ki_id") == ki_id
                    and f.get("payload", {}).get("rung")})
    # A backfilled FORK finding may carry a comma-joined multi-rung string; split it.
    expanded = set()
    for r in rungs:
        for part in str(r).split(","):
            part = part.strip()
            if part:
                expanded.add(part)
    n = len(expanded)
    if n <= 1:
        breadth = "single-rung"
        interp = ("local machinery / context / understanding — record; no doctrine "
                  "action by default (the arena tests local-vs-doctrine for THIS rung)")
    elif active_rung_count and n >= active_rung_count:
        breadth = "all-rung"
        interp = ("SPLIT required: record-defective (illegible/over-broad/no-gate → "
                  "clarify/demote/localize) vs needs-mechanization (doctrine fine, no "
                  "system-wide enforcement substrate yet — do NOT demote good forward-"
                  "doctrine for being early)")
    else:
        breadth = "multi-rung"
        interp = ("DOCTRINE clarity / scope / legibility defect until proven otherwise "
                  "→ Stage-4 arena")
    return {"breadth": breadth, "rungs_with_finding": sorted(expanded),
            "rung_count": n, "default_interpretation": interp}


def list_downaudit_findings(zone_root, current_tic=None):
    """Stage-4 read-only projection of the down-audit finding set, grouped by
    routing, with held-band staleness (D4). The /review-surfaced down-lane view."""
    if current_tic is None:
        current_tic = _resolve_federation_tic(zone_root)
    raw = load_downaudit_findings(zone_root)
    grouped = defaultdict(list)
    held, damaging, resolved = [], [], []
    for sig in raw:
        entry = _finding_entry(sig, current_tic=current_tic)
        if _finding_is_terminal(sig):
            # Terminal-State Valve: partition the resolved/dismissed finding into
            # its own receipt-bearing bucket (audit trail preserved) and EXCLUDE
            # it from the active verdict grouping/counts. Fixes the read-surface
            # gap where a resolve-finding left the closed N/A still projected
            # (bk-list-findings-excludes-resolved, surfaced tic 474).
            resolved.append(entry)
            continue
        grouped[entry["verdict"]].append(entry)
        if entry["verdict"] == "hold_in_dissonance" and entry["active"]:
            held.append(entry)
        if entry["verdict"] == "damaging" and entry["active"]:
            damaging.append(entry)
    counts = {v: len(items) for v, items in grouped.items()}
    active_total = sum(counts.values())
    return {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "zone_root": os.path.abspath(zone_root),
        "current_tic": current_tic,
        "_status": "Stage-4 finding projection — READ-ONLY; surfaces the down-lane "
                   "finding set for /review. Mutates nothing.",
        "_fence": "center-hold: read-only; opens no arena, resolves nothing, demotes "
                  "nothing. `damaging` → stage-brief (a hypothesis, /review-gated); the "
                  "held band is preserved + staleness-flagged, never auto-resolved.",
        "scope_declaration": (
            "Reads the signal manifold daily files (terminal-per-id, latest wins; "
            "active-manifest skipped — it lacks payload), filtered to "
            f"signal_type={DOWNAUDIT_FINDING_SIGNAL_TYPE}. current_tic resolved from "
            "the canonical tic log (domain_counter_after) if not supplied. CANNOT see "
            "whether a held tension has since dissolved at its rung — that is a fresh "
            "down-audit (re-test), surfaced by the staleness flag, not inferred here. "
            "Terminal-State Valve: resolved/dismissed/superseded findings are "
            "partitioned into resolved_findings (receipt-bearing) and EXCLUDED from "
            "the active counts_by_verdict / findings_by_verdict that /review reads."
        ),
        "total_findings": len(raw),
        "active_findings": active_total,
        "terminal_findings": len(resolved),
        "counts_by_verdict": counts,
        "routing": DOWNAUDIT_ROUTING,
        "resolved_findings": resolved,
        "damaging_awaiting_arena": damaging,
        "held_band": held,
        "stale_held_for_retest": [h for h in held if h.get("stale_for_retest")],
        "findings_by_verdict": dict(grouped),
    }


def format_findings_list(result):
    """Human-readable Stage-4 finding projection."""
    lines = []
    lines.append("=" * 70)
    lines.append("LADDER DOWN-LANE · Stage-4 finding projection (read-only; /review view)")
    lines.append("=" * 70)
    lines.append(f"  Zone root:    {result.get('zone_root', '?')}")
    lines.append(f"  Current tic:  {result.get('current_tic')}")
    _term = result.get("terminal_findings", 0)
    _term_note = f" (+{_term} resolved/terminal — see below)" if _term else ""
    lines.append(f"  Findings:     {result.get('active_findings', result.get('total_findings', 0))} active"
                 f"{_term_note}  counts: {result.get('counts_by_verdict', {})}")
    lines.append("")
    lines.append("  " + result.get("_status", ""))
    lines.append("  " + result.get("_fence", ""))
    lines.append("")
    lines.append("  scope: " + result.get("scope_declaration", ""))
    lines.append("")
    dmg = result.get("damaging_awaiting_arena", [])
    lines.append(f"DAMAGING → /stage ARENA (Stage 4; HYPOTHESIS, never auto-demote): {len(dmg)}")
    lines.append("-" * 70)
    if not dmg:
        lines.append("  (none — no damaging finding awaiting an arena this tic)")
    for d in dmg:
        lines.append(f"  ⚠ {d['ki_id']} @ {d['rung']}  [{d['signal_id']}]")
        lines.append(f"      → ladder-audit.py stage-brief --signal-id {d['signal_id']}")
        if d.get("summary"):
            lines.append(f"      {d['summary'][:96]}")
    lines.append("")
    held = result.get("held_band", [])
    lines.append(f"HELD BAND — hold_in_dissonance (§4; preserve tension, re-test): {len(held)}")
    lines.append("-" * 70)
    if not held:
        lines.append("  (none held)")
    for h in held:
        th = h.get("tics_held")
        stale = " ⏳ STALE — re-test at /review" if h.get("stale_for_retest") else ""
        held_str = f"held {th} tics" if th is not None else "held"
        lines.append(f"  · {h['ki_id']} @ {h['rung']}  [{h['signal_id']}]  ({held_str}){stale}")
        if h.get("summary"):
            lines.append(f"      {h['summary'][:96]}")
    lines.append("")
    lines.append("RECORDED (clean / N/A / needs_mechanization — no arena):")
    lines.append("-" * 70)
    for v in ("clean", "N/A", "needs_mechanization"):
        items = result.get("findings_by_verdict", {}).get(v, [])
        for it in items:
            rf = " [reinforce]" if it.get("reinforce_signal") else ""
            lines.append(f"  {v:<20} {it['ki_id']} @ {it['rung']}{rf}")
    resolved = result.get("resolved_findings", [])
    if resolved:
        lines.append("")
        lines.append(f"RESOLVED / TERMINAL (Terminal-State Valve — off the live set; receipt-bearing): {len(resolved)}")
        lines.append("-" * 70)
        for it in resolved:
            res = it.get("resolution") or {}
            to = res.get("resolved_to", "?")
            jc = res.get("justification_class", "?")
            rtic = res.get("review_tic", "?")
            lines.append(f"  ✓ {it['verdict']:<18} {it['ki_id']} @ {it['rung']}  "
                         f"[{it['signal_id']}]  → {it.get('status')}/{to} ({jc}, /review {rtic})")
    return "\n".join(lines)


def _extract_cpr_provenance_refs(text):
    """Pull CogPR-NNN and cpr_<slug|hash> references from a KI ledger body's provenance
    (the `promoted from` breadcrumbs / inline lineage). Read-only; returns a set."""
    if not text:
        return set()
    refs = set()
    refs.update(re.findall(r"CogPR-\d+", text))
    refs.update(re.findall(r"cpr_[a-z0-9_]+", text))
    return refs


def load_rbd_demote_evidence(zone_root, target_ki, ki_body=None):
    """Read-only: resolve the RBD (doctrine rollback-drill) reversibility verdict that
    gates a Stage-4 DEMOTE-class outcome for `target_ki`, and compute a
    `demote_admissibility` verdict from it. WIRES the existing RBD lane
    (audit-logs/rollback-drills/RBD-*.json — already computes velocity_ratio +
    reversion_patch_clean + orphaned_references over doctrine surfaces, tic-494 memo
    §1 Half B) as the reversibility-proof INPUT; does NOT rebuild the measurement.
    Never raises (fail-soft — an absent/unreadable lane yields the absent verdict).

    demote_admissibility:
      - `admissible`                     matched drill ∧ velocity_ratio>=1 ∧ reversion_patch_clean ∧ orphaned_references==0
      - `inadmissible_pending_reversion` matched drill but the predicate fails (rollback slower than attachment / unclean reversion / orphans)
      - `inadmissible_rbd_absent`        no drill resolves this KI's provenance — no reversibility proof exists yet
    """
    drills_dir = Path(zone_root) / ROLLBACK_DRILLS_REL
    records = []
    try:
        for p in sorted(drills_dir.glob("RBD-*.json")):
            try:
                records.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001 — skip an unreadable drill, never raise
                continue
    except Exception:  # noqa: BLE001 — lane absent → records stays empty
        pass
    # latest-first (the lane is small + append-style; newest drill per target wins)
    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)

    ki_refs = _extract_cpr_provenance_refs(ki_body)
    matched, match_basis = None, None
    for rec in records:
        overlap = ki_refs & set(rec.get("cprs_in_scope", []))
        if overlap:
            matched = rec
            match_basis = f"cprs_in_scope ∩ KI provenance: {sorted(overlap)}"
            break

    if records:
        latest = records[0]
        lane_note = (
            f"RBD doctrine rollback-drill lane: {len(records)} record(s); latest "
            f"target_tic {latest.get('target_tic')} ({(latest.get('timestamp') or '')[:10]}). "
            "Lane is DORMANT — no live re-runner (composite_rollback_gap / ESC-T155-001); "
            "tic-494 memo recommendation #2 (drill cadence) is a separate, unbuilt piece. "
            "A demote-class outcome needs a FRESH drill for the target KI."
        )
    else:
        lane_note = (
            "RBD doctrine rollback-drill lane: EMPTY. No reversibility proof can be "
            "sourced; every demote-class outcome is inadmissible until a drill is run."
        )

    predicate = "velocity_ratio>=1 AND reversion_patch_clean AND orphaned_references==0"
    if matched is None:
        return {
            "matched": False,
            "match_basis": None,
            "demote_admissibility": "inadmissible_rbd_absent",
            "predicate": predicate,
            "reason": ("no RBD reversibility drill resolves this KI's provenance — a "
                       "demote cannot be admitted without a reversibility proof "
                       "(rollback-velocity-must-exceed-attachment-velocity)."),
            "ki_provenance_refs": sorted(ki_refs),
            "rbd_lane_note": lane_note,
        }

    vr = matched.get("velocity_ratio")
    clean = bool(matched.get("reversion_patch_clean"))
    orphans = matched.get("orphaned_references")
    predicate_pass = (isinstance(vr, (int, float)) and vr >= 1 and clean and orphans == 0)
    return {
        "matched": True,
        "match_basis": match_basis,
        "drill_id": matched.get("drill_id"),
        "target_tic": matched.get("target_tic"),
        "velocity_ratio": vr,
        "attachment_velocity": matched.get("attachment_velocity"),
        "rollback_velocity": matched.get("rollback_velocity"),
        "reversion_patch_clean": clean,
        "orphaned_references": orphans,
        "drill_verdict": matched.get("verdict"),
        "demote_admissibility": ("admissible" if predicate_pass
                                 else "inadmissible_pending_reversion"),
        "predicate": predicate,
        "reason": ("reversibility proven (velocity_ratio>=1, reversion clean, 0 orphans) "
                   "— a demote outcome is admissible if the arena rules it"
                   if predicate_pass else
                   f"reversibility NOT proven (velocity_ratio={vr}, "
                   f"reversion_patch_clean={clean}, orphaned_references={orphans}) — "
                   "demote inadmissible until reversion is made clean"),
        "ki_provenance_refs": sorted(ki_refs),
        "rbd_lane_note": lane_note,
    }


# ─── M1 piece 3 complement: the RBD doctrine rollback-drill RE-RUNNER ─────────
# load_rbd_demote_evidence (above) CONSUMES RBD-*.json records. Until tic 506 the
# lane held only 3 tic-130-era records and had NO live re-runner
# (composite_rollback_gap / ESC-T155-001), so the `admissible` demote-admissibility
# path was lifecycle-UNREACHABLE — every KI read `inadmissible_rbd_absent`. This
# subcommand is that re-runner (tic-494 memo recommendation #2): it computes a
# FRESH doctrine rollback-drill for a target promotion (tic/commit → cprs_in_scope
# → doctrine files mutated → reversibility + velocity) and writes a schema-faithful
# record to the EXISTING lane the consumer reads. It does NOT rebuild the
# velocity-ratio measurement under a new name — that would be the double-make the
# memo §4 "What NOT to do" forbids; the record schema and write target are the
# existing ones (Inter-Engine Integration Emission: producer emits the consumer's
# format).
#
# CENTER-HOLD — read-only on DOCTRINE. It runs `git diff` / `git apply --check -R`
# (which only VERIFY — --check never writes, -R only tests reverse-apply, the
# worktree is never mutated), scans the corpus read-only, and writes only a
# regenerable drill record (like down-lane-run's --output report). It inscribes NO
# doctrine and demotes NOTHING: the demote DECISION stays HIGH-gate /review-only.
# The record is EVIDENCE the /review-gated demote consumes, never an action — so
# there is no new ungated effect to flag-gate (the human gate is /review itself).
#
# CADENCE DECISION (tic-494 memo recommendation #2, the explicit half): the
# re-runner fires EVENT-DRIVEN — manually for a reachability proof, and at /review
# when a demote-class verdict needs a fresh reversibility proof for its target KI.
# It is explicitly NOT periodic: the demote queue is event-sparse (0 damaging
# findings at tic 506), so a periodic RBD cadence would re-run drills with no
# demote pending — the exact "mounted bear" (can-it-eat) the federation warns
# against. The memo says EITHER a live re-runner OR an explicit event-driven-only
# decision closes the WATCH honestly; this build does BOTH.
#
# THE VELOCITY MODEL IS LOAD-BEARING LOCAL SEMANTICS — it stays home. The JUDGMENT
# that travels up the ladder is the federation KI
# rollback-velocity-must-exceed-attachment-velocity; the FORMULA below is this
# rung's transparent local instantiation, NOT a reconstruction of the lost
# tic-130 producer (reconstructing an exact formula from a principle is the
# magic-rehydration failure the ladder forbids).

# Doctrine-plane pathspecs the cross-reference scan searches. References that
# matter for reversion dependency are DOCTRINE references (other specs, ledgers,
# CLAUDE.mds) — NOT append-only audit-log history (commentary, not live dependency).
RBD_DOCTRINE_REF_PATHSPECS = (
    "autonomous_kernel",
    os.path.join("audit-logs", "governance", "constitution-ledger"),
    os.path.join("canonical_developer", "context-grapple-gun", "cgg-ledger"),
    ":(glob)**/CLAUDE.md",
    "CLAUDE.md",
)


def _is_doctrine_surface(path):
    """A changed path counts as a DOCTRINE surface for RBD reversion purposes
    (read-only). The same plane the cross-reference scan covers."""
    p = path.replace("\\", "/")
    base = p.rsplit("/", 1)[-1]
    if base == "CLAUDE.md":
        return True
    if base == "ledger.md" and ("constitution-ledger" in p or "cgg-ledger" in p):
        return True
    if p.startswith("autonomous_kernel/") and p.endswith(".md"):
        return True
    return False


def _git_capture(zone_root, git_args, input_text=None, timeout=20):
    """Run a git subcommand; return (returncode, stdout, stderr). Fail-soft —
    never raises (mirrors _git_last_commit_days). Read-only/verify callers only;
    nothing here mutates the worktree."""
    try:
        out = subprocess.run(
            ["git", "-C", zone_root, *git_args],
            capture_output=True, text=True, timeout=timeout, input=input_text,
        )
        return out.returncode, out.stdout, out.stderr
    except (OSError, subprocess.SubprocessError):
        return 1, "", "git-unavailable"


def _resolve_target_commit(zone_root, target_tic=None, target_commit=None):
    """Resolve the promotion commit to drill. Prefer an explicit --target-commit;
    else the newest commit whose subject names the target tic (`Tic <N>`). Returns
    a dict (short/full/parent/subject) or None if unresolved. Read-only."""
    sha = None
    if target_commit:
        rc, out, _ = _git_capture(
            zone_root, ["rev-parse", "--verify", f"{target_commit}^{{commit}}"])
        if rc == 0 and out.strip():
            sha = out.strip()
    elif target_tic is not None:
        rc, out, _ = _git_capture(
            zone_root, ["log", "-E", "--format=%H",
                        "--grep", rf"[Tt]ic {target_tic}( |:|$|\b)", "-n", "1"])
        if rc == 0 and out.strip():
            sha = out.strip().splitlines()[0]
    if not sha:
        return None
    rc, full, _ = _git_capture(zone_root, ["rev-parse", sha])
    full = full.strip() or sha
    _, short, _ = _git_capture(zone_root, ["rev-parse", "--short", sha])
    _, pfull, _ = _git_capture(zone_root, ["rev-parse", f"{sha}^"])
    _, pshort, _ = _git_capture(zone_root, ["rev-parse", "--short", f"{sha}^"])
    _, subj, _ = _git_capture(zone_root, ["log", "-1", "--format=%s", sha])
    return {
        "short": short.strip() or full[:7],
        "full": full,
        "parent_short": pshort.strip() or (pfull.strip()[:7] if pfull.strip() else None),
        "parent_full": pfull.strip() or None,
        "subject": subj.strip(),
    }


def run_rbd_drill(zone_root, target_tic=None, target_commit=None, cprs=None,
                  current_tic=None, dry_run=False):
    """Compute a FRESH doctrine rollback-drill (RBD) record for a target promotion
    and (unless dry_run) write it to the EXISTING audit-logs/rollback-drills/ lane.
    Read-only on doctrine; never mutates the worktree. See the section header for
    the center-hold + the local velocity model. Returns a result dict."""
    zone_root = os.path.abspath(zone_root)
    if current_tic is None:
        current_tic = _resolve_federation_tic(zone_root)
    commit = _resolve_target_commit(
        zone_root, target_tic=target_tic, target_commit=target_commit)
    if commit is None:
        return {
            "ok": False,
            "error": (f"no promotion commit resolved for target_tic={target_tic} / "
                      f"target_commit={target_commit} — pass --target-commit explicitly"),
            "wrote": None,
        }
    parent = commit["parent_full"]
    target = commit["full"]
    diff_range = f"{parent}..{target}" if parent else target

    # Files changed by the promotion, filtered to DOCTRINE surfaces.
    _, names_out, _ = _git_capture(zone_root, ["diff", "--name-only", diff_range])
    all_files = [f for f in names_out.splitlines() if f.strip()]
    doctrine_files = [f for f in all_files if _is_doctrine_surface(f)]

    # Patch size over the doctrine files (added+deleted lines, numstat).
    patch_lines = 0
    if doctrine_files:
        _, ns, _ = _git_capture(
            zone_root, ["diff", "--numstat", diff_range, "--", *doctrine_files])
        for line in ns.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                for n in parts[:2]:
                    try:
                        patch_lines += int(n)
                    except ValueError:
                        pass

    # cprs_in_scope: explicit, else extracted from the commit message.
    if cprs:
        cprs_in_scope = sorted(set(cprs))
    else:
        _, body, _ = _git_capture(zone_root, ["log", "-1", "--format=%B", target])
        cprs_in_scope = sorted(_extract_cpr_provenance_refs(body))

    # reversion_patch_clean: can the promotion be reverse-applied to the CURRENT
    # tree without conflict? `git apply --check -R` VERIFIES only (never writes).
    # An empty doctrine diff → nothing to revert on the doctrine plane → clean.
    reversion_patch_clean = True
    if doctrine_files:
        _, patch, _ = _git_capture(
            zone_root, ["diff", diff_range, "--", *doctrine_files])
        if patch.strip():
            rc_check, _, _ = _git_capture(
                zone_root, ["apply", "--check", "-R", "--recount", "-"],
                input_text=patch)
            reversion_patch_clean = (rc_check == 0)

    # cross_references / orphaned_references: references to this promotion's cprs
    # across the DOCTRINE plane. Orphans = refs living OUTSIDE the files the revert
    # would touch (they would dangle if the promotion were reverted).
    ref_files = set()
    for cid in cprs_in_scope:
        rc, hits, _ = _git_capture(
            zone_root, ["grep", "-l", "-F", "-e", cid, "--", *RBD_DOCTRINE_REF_PATHSPECS])
        if rc == 0:
            for hf in hits.splitlines():
                hf = hf.strip()
                if hf:
                    ref_files.add(hf)
    doctrine_set = set(doctrine_files)
    cross_references_found = len(ref_files)
    orphaned_references = len([f for f in ref_files if f not in doctrine_set])

    # ── the local velocity model (load-bearing local semantics; stays home) ──
    # attachment_velocity: downstream doctrine references accreted, per tic since
    #   promotion.  rollback_velocity: dependency mass a single clean revert can
    #   shed, per tic — a clean revert with no surviving orphans sheds everything
    #   it touches (+1 for the revert op itself); orphans throttle it; an unclean
    #   reversion cannot apply atomically (capacity 0).  velocity_ratio >= 1 ⟺ the
    #   undo can keep pace with what has attached = the federation KI satisfied.
    if current_tic is not None and target_tic is not None:
        tics_since_raw = current_tic - target_tic
    else:
        tics_since_raw = None
    tics_since = max(tics_since_raw, 1) if isinstance(tics_since_raw, int) else 1
    attachment_velocity = round(cross_references_found / tics_since, 3)
    if reversion_patch_clean and orphaned_references == 0:
        rollback_capacity = float(cross_references_found) + 1.0
    elif reversion_patch_clean:
        rollback_capacity = float(max(cross_references_found - orphaned_references, 0))
    else:
        rollback_capacity = 0.0
    rollback_velocity = round(rollback_capacity / tics_since, 3)
    if attachment_velocity > 0:
        velocity_ratio = round(rollback_velocity / attachment_velocity, 3)
    else:
        velocity_ratio = 1.0 if (reversion_patch_clean and orphaned_references == 0) else 0.0

    if velocity_ratio >= 1 and reversion_patch_clean and orphaned_references == 0:
        verdict = "ok"
    elif velocity_ratio >= 0.5 and reversion_patch_clean:
        verdict = "warning"
    else:
        verdict = "critical"

    now = datetime.now(timezone.utc)
    epoch = int(now.timestamp())
    tic_label = target_tic if target_tic is not None else commit["short"]
    drill_id = f"RBD-{tic_label}-{epoch}"
    record = {
        "drill_id": drill_id,
        "target_commit": commit["short"],
        "target_commit_full": commit["full"],
        "parent_commit": commit["parent_short"],
        "target_tic": target_tic,
        "cprs_in_scope": cprs_in_scope,
        "files_mutated": doctrine_files,
        "file_count": len(doctrine_files),
        "patch_lines": patch_lines,
        "reversion_patch_clean": reversion_patch_clean,
        "cross_references_found": cross_references_found,
        "orphaned_references": orphaned_references,
        "attachment_velocity": attachment_velocity,
        "rollback_velocity": rollback_velocity,
        "velocity_ratio": velocity_ratio,
        "tics_since_promotion": tics_since_raw,
        "verdict": verdict,
        "timestamp": now.isoformat(),
        "produced_by": "ladder-audit.py rbd-drill-run",
        "drill_model": "re-runner v0 (tic 506); local Half-B velocity semantics",
    }
    demote_admissible = (velocity_ratio >= 1 and reversion_patch_clean
                         and orphaned_references == 0)
    result = {
        "ok": True,
        "dry_run": dry_run,
        "record": record,
        "would_demote_admissibility": ("admissible" if demote_admissible
                                       else "inadmissible_pending_reversion"),
        "commit_subject": commit["subject"],
        "all_files_changed": len(all_files),
        "doctrine_files_changed": len(doctrine_files),
        "note": ("not a doctrine-promotion commit (no doctrine surface changed) — "
                 "degenerate drill" if not doctrine_files else None),
        "wrote": None,
    }
    if not dry_run:
        drills_dir = Path(zone_root) / ROLLBACK_DRILLS_REL
        drills_dir.mkdir(parents=True, exist_ok=True)
        out_path = drills_dir / f"{drill_id}.json"
        out_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        result["wrote"] = str(out_path)
    return result


def format_rbd_drill(result):
    """Human-readable RBD re-runner output (read-only producer)."""
    lines = []
    lines.append("=" * 74)
    lines.append("RBD DOCTRINE ROLLBACK-DRILL · re-runner (M1 complement; tic-494 memo rec #2)")
    lines.append("=" * 74)
    if not result.get("ok"):
        lines.append(f"  ✗ {result.get('error', 'unresolved')}")
        return "\n".join(lines)
    rec = result["record"]
    lines.append(f"  drill_id:        {rec['drill_id']}    {'(DRY-RUN — not written)' if result['dry_run'] else 'WRITTEN: ' + str(result.get('wrote'))}")
    lines.append(f"  target:          tic {rec['target_tic']}  commit {rec['target_commit']} (parent {rec['parent_commit']})")
    lines.append(f"  subject:         {result.get('commit_subject', '')[:64]}")
    lines.append(f"  cprs_in_scope:   {', '.join(rec['cprs_in_scope']) or '(none found)'}")
    lines.append(f"  doctrine files:  {rec['file_count']} of {result.get('all_files_changed')} changed  ({rec['patch_lines']} patch lines)")
    if result.get("note"):
        lines.append(f"  ⚠ {result['note']}")
    for f in rec["files_mutated"]:
        lines.append(f"      - {f}")
    lines.append("")
    lines.append("  REVERSIBILITY:")
    lines.append(f"    reversion_patch_clean: {rec['reversion_patch_clean']}   "
                 f"orphaned_references: {rec['orphaned_references']}   "
                 f"cross_references_found: {rec['cross_references_found']}")
    lines.append(f"    attachment_velocity:   {rec['attachment_velocity']}   "
                 f"rollback_velocity: {rec['rollback_velocity']}   "
                 f"tics_since_promotion: {rec['tics_since_promotion']}")
    lines.append(f"    velocity_ratio:        {rec['velocity_ratio']}   →  verdict: {rec['verdict'].upper()}")
    lines.append("")
    lines.append(f"  ⇒ would_demote_admissibility: {result['would_demote_admissibility']}")
    lines.append("    (predicate: velocity_ratio>=1 AND reversion_patch_clean AND orphaned_references==0)")
    lines.append("    The demote DECISION stays /review-only — this record is reversibility EVIDENCE, not an action.")
    return "\n".join(lines)


# ─── M1 complement: the /review-flow AUTO-INVOCATION of the re-runner (tic 507) ──────
# When a demote-class verdict needs a fresh reversibility proof and none exists
# (`inadmissible_rbd_absent`), today the operator HAND-runs `rbd-drill-run`. This
# resolver + the autodrill function mechanize that hand-step (build-and-gate, dormant).

def _resolve_ki_promotion_target(ki_body):
    """Resolve, from a KI's ledger BODY, the promotion the RBD drill should measure.
    The promotion COMMIT is the /review-execute commit at the KI's promote/review tic;
    the cprs are the KI's provenance refs. Read-only; returns a dict (never raises).

    Preference for the tic that names the promotion commit subject (`Tic <N>`):
      promoted_tic: tag  >  `(tic B->R)` breadcrumb review-tic R  >  first_appearance_tic.
    """
    cprs = sorted(_extract_cpr_provenance_refs(ki_body))
    promoted_tic = None
    if ki_body:
        # Ledger tags are backtick-wrapped: `promoted_tic`: `406`. Tolerate the
        # backticks/colon/whitespace between the key and the digit.
        m = re.search(r"promoted_tic[`:\s]*(\d+)", ki_body)
        if m:
            promoted_tic = int(m.group(1))
        if promoted_tic is None:
            # `promoted from CogPR-N (tic B->R)` — R is the /review (promotion) tic.
            # Provenance uses an ASCII (`->`) or unicode (`→`) arrow.
            m = re.search(r"\(tic\s+\d+\s*(?:-+>|→)\s*(\d+)", ki_body)
            if m:
                promoted_tic = int(m.group(1))
        if promoted_tic is None:
            m = re.search(r"first_appearance_tic[`:\s]*(\d+)", ki_body)
            if m:
                promoted_tic = int(m.group(1))
    return {"promoted_tic": promoted_tic, "cprs": cprs}


def rbd_autodrill_for_demote(zone_root, target_ki, ki_body=None, current_tic=None,
                             target_tic=None, cprs=None, ratified=False):
    """The /review-flow AUTO-INVOCATION of the RBD re-runner for a demote-class verdict.
    Build-and-gate, DORMANT by default (ratified=False → plan-only, writes nothing).

    Flow: read the current demote-admissibility for `target_ki`; if it is already
    `admissible` a fresh proof exists → no autodrill needed. Else resolve the KI's
    promotion target (tic + cprs) from its ledger provenance (or explicit overrides) and:
      - DORMANT  → surface the exact `rbd-drill-run` PLAN it WOULD fire (no write).
      - RATIFIED → fire `run_rbd_drill` (regenerable drill record), then re-read the
        evidence and return the now-fresh admissibility (the consumer reads it back).

    Center-hold: read-only on DOCTRINE; the only write is run_rbd_drill's regenerable
    drill record (gated on `ratified`); the demote DECISION stays /review-only.
    Never raises (fail-soft). Returns a result dict.
    """
    zone_root = os.path.abspath(zone_root)
    if current_tic is None:
        current_tic = _resolve_federation_tic(zone_root)

    before = load_rbd_demote_evidence(zone_root, target_ki, ki_body=ki_body)
    base = {
        "ok": True,
        "target_ki": target_ki,
        "ratified": bool(ratified),
        "ratified_source": ("RBD_AUTODRILL_RATIFIED/--force-autodrill"
                            if ratified else "DORMANT (RBD_AUTODRILL_RATIFIED=False)"),
        "evidence_before": before,
        "demote_class_outcomes": list(RBD_DEMOTE_CLASS_OUTCOMES),
        "_fence": ("read-only on DOCTRINE; the demote DECISION stays /review-only. "
                   "While dormant this surfaces the PLAN only and writes nothing."),
        "wrote": None,
    }
    if before["demote_admissibility"] == "admissible":
        base["action"] = "none_needed"
        base["note"] = ("a fresh reversibility proof already resolves this KI "
                        f"({before.get('drill_id')}) — no autodrill needed.")
        return base

    # Resolve the promotion target (explicit overrides win, else ledger provenance).
    resolved = _resolve_ki_promotion_target(ki_body)
    eff_tic = target_tic if target_tic is not None else resolved["promoted_tic"]
    eff_cprs = cprs if cprs else (resolved["cprs"] or None)
    plan = {
        "subcommand": "rbd-drill-run",
        "target_tic": eff_tic,
        "cprs": eff_cprs,
        "invocation": (
            "python3 ladder-audit.py rbd-drill-run "
            f"--zone-root {zone_root} "
            + (f"--target-tic {eff_tic} " if eff_tic is not None else "--target-commit <SHA> ")
            + (f"--cprs {','.join(eff_cprs)}" if eff_cprs else "").strip()
        ).strip(),
    }
    base["plan"] = plan

    if eff_tic is None and not (target_tic or cprs):
        # Degenerate: provenance gave no promotion tic — the operator must supply a target.
        base["action"] = "unresolved_target"
        base["note"] = ("could not resolve the KI's promotion commit from its ledger "
                        "provenance — supply --target-tic or --target-commit explicitly.")
        return base

    if not ratified:
        base["action"] = "would_autodrill"
        base["note"] = ("DORMANT (build-and-gate) — the re-runner is NOT auto-fired. "
                        "Run the planned invocation by hand, or /review 507 flips "
                        "RBD_AUTODRILL_RATIFIED True to auto-fire it on a demote-class "
                        "verdict.")
        return base

    # RATIFIED — fire the re-runner (regenerable drill record), then re-read evidence.
    drill = run_rbd_drill(zone_root, target_tic=eff_tic, cprs=eff_cprs,
                          current_tic=current_tic, dry_run=False)
    base["drill_result"] = drill
    base["wrote"] = drill.get("wrote")
    if not drill.get("ok"):
        base["action"] = "autodrill_failed"
        base["note"] = drill.get("error", "re-runner could not resolve the target commit")
        return base
    after = load_rbd_demote_evidence(zone_root, target_ki, ki_body=ki_body)
    base["action"] = "autodrilled"
    base["evidence_after"] = after
    base["demote_admissibility"] = after["demote_admissibility"]
    base["note"] = (
        f"auto-fired the re-runner ({drill['record']['drill_id']}); the consumer now "
        f"reads `{after['demote_admissibility']}` for this KI."
    )
    return base


def format_rbd_autodrill(result):
    """Human-readable RBD autodrill output (the /review-flow auto-invocation)."""
    lines = []
    lines.append("=" * 74)
    lines.append("RBD AUTODRILL · /review-flow auto-invocation of the re-runner (tic 507)")
    lines.append("=" * 74)
    if not result.get("ok"):
        lines.append(f"  ✗ {result.get('error', 'failed')}")
        return "\n".join(lines)
    before = result.get("evidence_before", {})
    lines.append(f"  target KI:         {result['target_ki']}")
    lines.append(f"  ratified:          {result['ratified']}   ({result['ratified_source']})")
    lines.append(f"  admissibility now: {before.get('demote_admissibility')}")
    lines.append(f"  action:            {result['action'].upper()}")
    plan = result.get("plan")
    if plan:
        lines.append("")
        lines.append("  WOULD-FIRE PLAN:")
        lines.append(f"    target_tic: {plan.get('target_tic')}   cprs: {', '.join(plan.get('cprs') or []) or '(none)'}")
        lines.append(f"    $ {plan.get('invocation')}")
    if result.get("action") == "autodrilled":
        after = result.get("evidence_after", {})
        lines.append("")
        lines.append(f"  FIRED — wrote: {result.get('wrote')}")
        lines.append(f"  admissibility after: {after.get('demote_admissibility')}")
    lines.append("")
    lines.append(f"  → {result.get('note', '')}")
    lines.append(f"  ⓘ {result.get('_fence', '')}")
    return "\n".join(lines)


def build_stage_brief(zone_root, signal_id=None, rung=None, ki_id=None,
                      current_tic=None, window_days=ACTIVE_RUNG_WINDOW_DAYS,
                      force_rbd_ratified=False):
    """Stage-4 read-only: assemble the `/stage` arena brief for a `damaging` (or
    re-tested held) down-audit finding. Does NOT open the arena and does NOT
    inscribe — the orchestrator runs /stage; the arena verdict routes to /review.
    """
    if current_tic is None:
        current_tic = _resolve_federation_tic(zone_root)
    zone_root = os.path.abspath(zone_root)
    raw = load_downaudit_findings(zone_root)

    # Resolve the target finding by signal_id, or by (rung, ki_id).
    sig = None
    if signal_id:
        sig = next((s for s in raw
                    if (s.get("signal_id") or s.get("id")) == signal_id), None)
    elif rung and ki_id:
        for s in raw:
            p = s.get("payload", {})
            if p.get("ki_id") == ki_id and (
                    p.get("rung") == rung or rung in str(p.get("rung", ""))):
                sig = s
                break

    base = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "zone_root": zone_root,
        "current_tic": current_tic,
        "stage": "C9 Stage-4 arena BRIEF (read-only PREP — NOT a verdict, NOT inscription)",
        "_status": "Stage-4 /stage arena BRIEF — read-only. The orchestrator runs "
                   "/stage with this brief; the arena VERDICT routes to /review "
                   "(review-execute inscribes). This script opens no arena, inscribes "
                   "nothing, demotes nothing.",
        "_fence": "center-hold: a `damaging` finding is a HYPOTHESIS (Arena Velocity "
                  "Guard), never an auto-demotion. The arena contests the KI's FIT at "
                  "the rung; only /review may demote/reword/reinforce. NEVER inscribe "
                  "from this brief.",
    }
    if sig is None:
        base["ok"] = False
        base["error"] = (
            "no down-audit finding resolves the request "
            f"(signal_id={signal_id!r}, rung={rung!r}, ki_id={ki_id!r}). "
            "Run `ladder-audit.py list-findings` to see the finding set."
        )
        return base

    entry = _finding_entry(sig, current_tic=current_tic)
    verdict = entry["verdict"]
    if verdict not in ("damaging", "hold_in_dissonance"):
        base["ok"] = False
        base["error"] = (
            f"finding {entry['signal_id']} is `{verdict}` — Stage-4 arenas open only "
            "for `damaging` (route-to-arena) or `hold_in_dissonance` (re-test). A "
            f"`{verdict}` finding records; it does not open an arena (spec §2 Stage 3)."
        )
        base["finding"] = entry
        return base

    target_ki = entry["ki_id"]
    ledger_path = os.path.join(audit_logs_path(zone_root, load_ticzone(zone_root)),
                               LEDGER_REL)
    kis = _parse_ledger_kis(ledger_path, include_body=True)
    ki = next((k for k in kis if k["invariant_id"] == target_ki), None)

    stage0 = discover_active_rungs(zone_root, window_days=window_days)
    active_rung_count = stage0.get("active_count")
    agg = _finding_aggregation(raw, target_ki, active_rung_count=active_rung_count)

    rung_name = entry["rung"]
    contested = (
        f"Does the federation KI `{target_ki}` rehydrate IN SPIRIT at the `{rung_name}` "
        f"rung — or is its applicability-claim here foreign / over-scoped / "
        f"load-bearing-but-N/A (the `{verdict}` finding)?"
    )
    base.update({
        "ok": True,
        "finding": entry,
        "target_ki": target_ki,
        "rung": rung_name,
        "ki_body": (ki or {}).get("body", ""),
        "ki_body_resolved": ki is not None,
        "aggregation": agg,
        "contested_question": contested,
        "arena_geometry": (
            "opposing-values (the KI's scope/fit is the contested question) — per "
            "Opposing-Values Geometry for Constitutional Questions; OA-VPL-T if "
            "multi-office breadth is wanted. Advocates hold genuinely different values "
            "(KI-holds-here vs KI-is-damaging-here vs KI-needs-local-mechanization)."
        ),
        "suggested_positions": [
            "KI HOLDS at this rung — the `damaging` first-read was local "
            "(→ confirmed / reinforce: the rung erred, not the KI)",
            "KI is DAMAGING/over-scoped here — its applicability-claim does not carry "
            "(→ overbroad_demote / localized / needs_clarification / recenter_required)",
            "KI is RIGHT but UNENFORCED here — forward, not defective "
            "(→ needs_mechanization)",
            "GENUINE unresolved tension — neither collapse is honest "
            "(→ hold_in_dissonance)",
        ],
        "legal_outcomes": DOWNAUDIT_ARENA_OUTCOMES,
        "routing_rule": (
            "The arena produces ONE outcome as GOVERNANCE INPUT, not a verdict. It "
            "routes to /review (a CogPR / docket entry); review-execute inscribes any "
            "demote/reword/reinforce (HIGH gate, /review-only). NEVER auto-demote "
            "(Arena Velocity Guard). On `hold_in_dissonance`, leave the held band open "
            "(resolve-finding only after /review rules)."
        ),
        "stage_invocation_hint": (
            f"/stage opposing-values  \"{contested}\"  "
            "(feed this brief as the arena context: the KI body, the rung friction, "
            "the finding, the aggregation breadth, the legal outcomes)"
        ),
        "friction_pointer": (
            f"python3 cgg-runtime/scripts/lib/load_doctrine_chain.py {rung_name}  "
            "# the rung's CLAUDE.md chain; arena advocates read the rung's real friction"
        ),
        "scope_declaration": (
            "Read-only Stage-4 arena-brief assembler. Reads: the target finding from "
            "the manifold, the KI's ledger BODY, the Stage-0 active-rung breadth for "
            "this KI. Writes nothing, opens no arena, inscribes nothing. CANNOT decide "
            "the outcome (the arena does) and does not pre-bias toward demotion "
            "(`needs_mechanization`/`reinforce` are first-class non-demote outcomes)."
        ),
    })
    # M1 piece 3 — RBD demote-admission evidence (build-and-gate; read-only).
    # The reversibility-proof INPUT a `damaging`→demote consumes: surfaced as ADVISORY
    # while dormant (gates nothing), as a HARD gate once /review 505 flips the flag.
    rbd_ratified = RBD_DEMOTE_ADMISSION_RATIFIED or force_rbd_ratified
    rbd = load_rbd_demote_evidence(zone_root, target_ki, ki_body=base["ki_body"])
    admissible = rbd["demote_admissibility"] == "admissible"
    base.update({
        "rbd_evidence": rbd,
        "demote_admissibility": rbd["demote_admissibility"],
        "rbd_admission_ratified": rbd_ratified,
        "rbd_demote_class_outcomes": list(RBD_DEMOTE_CLASS_OUTCOMES),
        # dual-proof surface: dormancy gates NOTHING (rbd_gated_outcomes empty),
        # ratification gates the demote-class outcomes the predicate fails.
        "rbd_gated_outcomes": (
            list(RBD_DEMOTE_CLASS_OUTCOMES) if (rbd_ratified and not admissible) else []
        ),
        "rbd_would_gate_outcomes": (
            list(RBD_DEMOTE_CLASS_OUTCOMES) if (not rbd_ratified and not admissible) else []
        ),
        "rbd_admission_enforcement": (
            ("RATIFIED — HARD GATE: /review must NOT inscribe a demote-class outcome "
             "(overbroad_demote / localized / stale) while demote_admissibility != "
             "'admissible'. A reversibility proof (RBD velocity_ratio>=1 ∧ clean reversion "
             "∧ 0 orphans) is the admission predicate.")
            if rbd_ratified else
            ("ADVISORY — build-and-gate (RBD_DEMOTE_ADMISSION_RATIFIED=False; /review 505 "
             "flips it). The RBD verdict is surfaced as evidence and does NOT yet block a "
             "demote; the arena / /review MAY weigh it. (Inscription stays /review-only "
             "regardless — this gate only constrains WHICH outcome /review may inscribe.)")
        ),
    })
    # M1 complement (tic 507): surface the RBD AUTODRILL PLAN — the `rbd-drill-run`
    # invocation the /review flow would auto-fire on a demote-class verdict to make a
    # currently-absent reversibility proof exist. stage-brief is READ-ONLY PREP: it
    # passes ratified=False so this NEVER fires (plan-only); the firing surface is the
    # `rbd-autodrill` subcommand, gated on RBD_AUTODRILL_RATIFIED (/review 507).
    base["rbd_autodrill"] = rbd_autodrill_for_demote(
        zone_root, target_ki, ki_body=base["ki_body"], current_tic=current_tic,
        ratified=False)
    if entry.get("artifact"):
        base["finding_artifact"] = entry["artifact"]
    if ki is None:
        base["ki_body_note"] = (
            f"KI `{target_ki}` not found in the constitution-ledger as an "
            "`invariant_id` — the arena must source the doctrine body manually "
            "(it may be a CGG-ledger or compact-root entry, not federation-ledger)."
        )
    return base


def format_stage_brief(brief):
    """Human-readable Stage-4 arena brief."""
    lines = []
    lines.append("=" * 70)
    lines.append("LADDER DOWN-LANE · Stage-4 /stage ARENA BRIEF (read-only; NOT a verdict)")
    lines.append("=" * 70)
    if not brief.get("ok"):
        lines.append(f"  ✗ {brief.get('error', 'could not assemble brief')}")
        return "\n".join(lines)
    lines.append(f"  Target KI:   {brief['target_ki']}")
    lines.append(f"  Rung:        {brief['rung']}")
    lines.append(f"  Finding:     {brief['finding']['verdict']}  "
                 f"[{brief['finding']['signal_id']}]")
    agg = brief.get("aggregation", {})
    lines.append(f"  Breadth:     {agg.get('breadth')}  "
                 f"(rungs: {', '.join(agg.get('rungs_with_finding', [])) or '—'})")
    lines.append("")
    lines.append("  " + brief.get("_status", ""))
    lines.append("  " + brief.get("_fence", ""))
    lines.append("")
    lines.append("  scope: " + brief.get("scope_declaration", ""))
    lines.append("")
    lines.append("CONTESTED QUESTION:")
    lines.append("-" * 70)
    lines.append("  " + brief.get("contested_question", ""))
    lines.append("")
    lines.append(f"  default interpretation ({agg.get('breadth')}): {agg.get('default_interpretation', '')}")
    lines.append("")
    lines.append("ARENA GEOMETRY:")
    lines.append("-" * 70)
    lines.append("  " + brief.get("arena_geometry", ""))
    lines.append("")
    lines.append("SUGGESTED POSITIONS (genuinely different values):")
    for p in brief.get("suggested_positions", []):
        lines.append(f"  • {p}")
    lines.append("")
    lines.append("LEGAL OUTCOMES (route to /review as a verdict — NEVER self-inscribed):")
    lines.append("-" * 70)
    for o in sorted(brief.get("legal_outcomes", {})):
        lines.append(f"  · {o}: {brief['legal_outcomes'][o][:84]}")
    rbd = brief.get("rbd_evidence")
    if rbd:
        lines.append("")
        lines.append("RBD DEMOTE-ADMISSION (rollback-velocity-must-exceed-attachment-velocity):")
        lines.append("-" * 70)
        lines.append("  enforcement:   " + brief.get("rbd_admission_enforcement", ""))
        lines.append(f"  admissibility: {rbd.get('demote_admissibility')}   "
                     f"[predicate: {rbd.get('predicate')}]")
        if rbd.get("matched"):
            lines.append(f"  drill {rbd.get('drill_id')}: velocity_ratio={rbd.get('velocity_ratio')}  "
                         f"reversion_clean={rbd.get('reversion_patch_clean')}  "
                         f"orphans={rbd.get('orphaned_references')}  verdict={rbd.get('drill_verdict')}")
        lines.append("  " + rbd.get("reason", ""))
        gated = brief.get("rbd_gated_outcomes") or []
        would = brief.get("rbd_would_gate_outcomes") or []
        if gated:
            lines.append("  ⛔ GATED (ENFORCED — /review may not inscribe): " + ", ".join(gated))
        if would:
            lines.append("  ⚠ would-gate (ADVISORY preview, not yet enforced): " + ", ".join(would))
        if not gated and not would:
            lines.append("  ✓ demote-class outcomes ADMISSIBLE (reversibility proven)")
        lines.append("  lane: " + rbd.get("rbd_lane_note", ""))
    lines.append("")
    lines.append("ROUTING: " + brief.get("routing_rule", ""))
    lines.append("")
    lines.append("INVOKE: " + brief.get("stage_invocation_hint", ""))
    lines.append("FRICTION: " + brief.get("friction_pointer", ""))
    body = (brief.get("ki_body") or "").strip()
    if body:
        lines.append("")
        lines.append("KI BODY (the spirit the arena judges against):")
        lines.append("-" * 70)
        lines.append(body[:1200] + ("…" if len(body) > 1200 else ""))
    if brief.get("ki_body_note"):
        lines.append("")
        lines.append("  ⚠ " + brief["ki_body_note"])
    return "\n".join(lines)


def resolve_downaudit_finding(zone_root, signal_id, review_tic, resolved_to,
                              justification, *, justification_class=None,
                              reversible=None, made_known=None, resolved_tic=None,
                              dry_run=False):
    """Receipted terminal transition of a held/damaging finding SIGNAL (signal-state,
    NOT doctrine). /review-gated. Appends a `resolved` row (Terminal-State Valve)
    carrying the receipt per `terminal-state-change-requires-receipt`. Does NOT
    mutate the ledger — any demote/reword the resolution implies is /review's act.
    """
    if resolved_to not in DOWNAUDIT_ARENA_OUTCOMES:
        raise ValueError(
            f"Unknown resolved_to '{resolved_to}'. Valid: "
            f"{', '.join(sorted(DOWNAUDIT_ARENA_OUTCOMES))}"
        )
    if not justification:
        raise ValueError("a resolve-finding receipt requires --justification "
                          "(terminal-state-change-requires-receipt).")

    raw = load_downaudit_findings(zone_root)
    sig = next((s for s in raw
                if (s.get("signal_id") or s.get("id")) == signal_id), None)
    if sig is None:
        return {"ok": False, "error": f"no finding signal '{signal_id}' on the manifold"}
    if not is_active_ray(sig):
        return {"ok": False, "error": f"finding '{signal_id}' is already terminal "
                f"(status={sig.get('status')}); resolve is idempotent — no re-close.",
                "current": _finding_entry(sig)}

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    resolved_tic = resolved_tic if resolved_tic is not None else _resolve_federation_tic(zone_root)

    receipt = {
        "resolved_to": resolved_to,
        "review_tic": review_tic,
        "resolved_tic": resolved_tic,
        "justification": justification,
        "justification_class": justification_class or "arena_adjudicated",
        "reversible": reversible if reversible is not None else True,
        "made_known": made_known or f"resolve-finding @ /review {review_tic}",
        "resolved_at": now.isoformat(),
    }

    resolved_signal = dict(sig)  # carry the original shape; flip terminal + receipt
    resolved_signal["status"] = "resolved"
    resolved_signal["structural_status"] = "resolved"
    resolved_signal["resolved_at"] = now.isoformat()
    payload = dict(resolved_signal.get("payload", {}))
    payload["resolution"] = receipt
    resolved_signal["payload"] = payload

    manifest_entry = {
        "signal_id": signal_id,
        "signal_type": DOWNAUDIT_FINDING_SIGNAL_TYPE,
        "status": "resolved",
        "structural_status": "resolved",
        "resolved_to": resolved_to,
        "review_tic": review_tic,
        "summary": (f"down-audit finding resolved → {resolved_to} "
                    f"(/review {review_tic}): {justification[:80]}"),
    }

    if dry_run:
        return {"ok": True, "dry_run": True, "signal_id": signal_id,
                "receipt": receipt, "resolved_signal": resolved_signal}

    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    signal_dir = os.path.join(al_path, "signals")
    os.makedirs(signal_dir, exist_ok=True)
    signal_file = os.path.join(signal_dir, f"{date_str}.jsonl")
    manifest_path = os.path.join(signal_dir, "active-manifest.jsonl")

    # Terminal transition = append a new row with the SAME signal_id (latest-per-id
    # wins). NOT dedup_signal_append (which would refuse the duplicate id).
    atomic_append_jsonl(signal_file, resolved_signal)
    atomic_append_jsonl(manifest_path, manifest_entry)

    return {"ok": True, "dry_run": False, "signal_id": signal_id,
            "resolved_to": resolved_to, "receipt": receipt,
            "summary": manifest_entry["summary"]}


# ---------------------------------------------------------------------------
# down-lane-run — the C9 down-audit RUNTIME driver (M1, ladder-downlane-spec.md)
#
# The §1 Sovereign Boot Authority spec (ratified tic 502) names M1 as "C9 down-lane
# WIRED — the missing down-audit RUNTIME". Stages 0–5 were each built as atomic
# subcommands (tic 380→473) but had to be HAND-CHAINED every tic (the tic-490 inline
# pass, the tic-493 4-seat medley): list-active-rungs → select-kis → down-audit (per
# rung) → ladder-auditor judgment → emit-finding. There was no runtime that RAN the
# audit — only parts an orchestrator assembled by hand. This driver is that runtime:
# it runs Stage 0→1→2 across the active rung set in ONE read-only pass and computes
# coverage/due-ness against the EXISTING finding manifold, so the down-lane becomes
# self-pacing (it knows which (rung,KI) pairs are never-audited or stale) instead of
# depending on a human to remember to chain the subcommands.
#
# Boundary (this piece is read-only / no-new-authority — spec §gated_by: "Read-only
# pieces (selector, down-audit, finding-emit) extend ladder-audit.py without new
# authority"):
#   - composes only the wired READ-ONLY stages (discover_active_rungs +
#     select_kis_per_rung + build_downaudit_packet) + reads load_downaudit_findings.
#   - emits NO finding (the ladder-auditor judges; the orchestrator lands via
#     emit-finding — Stage 3), opens NO arena, mutates NO doctrine (Stage 4 is
#     /review-only), creates NO new state-store (coverage is read from the manifold;
#     output is a regenerable read-only report — self-conditioning thin-terminal-
#     residue boundary).
#   - stays ACTIVE-RUNG + SELECTION-scoped (never a blanket sweep — that is the bare
#     run_audit structural pass). A rung that cannot be down-audited (unsourced / no
#     candidates) is SURFACED, never invented (Disagreement-as-evidence).
#   - a "due" pair is a campaign HYPOTHESIS about what to re-audit, never a verdict
#     about fit and never a demotion pressure (Arena Velocity Guard).
# ---------------------------------------------------------------------------

def _downlane_coverage_index(zone_root):
    """Map (rung-identity, ki_id) -> latest-by-opened_tic finding summary.

    Read-only, from the EXISTING down-audit finding manifold (terminal-per-id). A
    backfilled finding may carry a comma-joined multi-rung string; each part is keyed
    separately. The latest opened_tic wins (the most recent audit of that pair)."""
    idx = {}
    for sig in load_downaudit_findings(zone_root):
        p = sig.get("payload", {})
        ki_id = p.get("ki_id")
        rung = p.get("rung")
        ot = p.get("opened_tic")
        if not ki_id or not rung:
            continue
        terminal = _finding_is_terminal(sig)
        for part in str(rung).split(","):
            part = part.strip()
            if not part:
                continue
            key = (part, ki_id)
            cur = idx.get(key)
            cur_ot = (cur or {}).get("opened_tic")
            if cur is None or (isinstance(ot, int)
                               and (not isinstance(cur_ot, int) or ot >= cur_ot)):
                idx[key] = {
                    "opened_tic": ot,
                    "verdict": p.get("verdict"),
                    "signal_id": sig.get("signal_id") or sig.get("id"),
                    "terminal": terminal,
                }
    return idx


def _downlane_coverage_for_pair(idx, rung_idents, ki_id, current_tic, stale_tics):
    """Coverage of one (rung, KI) campaign pair against the finding index.

    rung_idents = the identities the rung can be keyed by (dir / name / basename),
    mirroring _resolve_rung_in_selection so a finding emitted under any of them is
    matched. Returns never_audited | stale | fresh + the last audit's tic/verdict."""
    hit = None
    for ident in rung_idents:
        h = idx.get((ident, ki_id))
        if h is None:
            continue
        if hit is None or (isinstance(h.get("opened_tic"), int)
                           and (not isinstance(hit.get("opened_tic"), int)
                                or h["opened_tic"] >= hit["opened_tic"])):
            hit = h
    if hit is None:
        return {"coverage": "never_audited", "last_audited_tic": None,
                "last_verdict": None, "tics_since": None, "last_signal_id": None}
    ot = hit.get("opened_tic")
    tics_since = (current_tic - ot) if (isinstance(current_tic, int)
                                        and isinstance(ot, int)) else None
    coverage = "stale" if (tics_since is not None and tics_since >= stale_tics) else "fresh"
    return {"coverage": coverage, "last_audited_tic": ot,
            "last_verdict": hit.get("verdict"), "tics_since": tics_since,
            "last_signal_id": hit.get("signal_id"),
            "last_finding_terminal": hit.get("terminal")}


def run_downlane_campaign(zone_root, rung=None, top=3, opened_tic=None,
                          current_tic=None,
                          coverage_stale_tics=DOWNAUDIT_COVERAGE_STALE_TICS,
                          window_days=ACTIVE_RUNG_WINDOW_DAYS, include_packets=True):
    """C9 down-lane RUNTIME driver (M1): run Stage 0→1→2 across the active rung set in
    ONE read-only pass + compute coverage/due-ness from the EXISTING finding manifold.

    Read-only / no-new-authority. Assembles the full Stage-2 packet-set + a coverage
    manifest; emits NO finding (the ladder-auditor judges, the orchestrator lands via
    emit-finding), opens NO arena, mutates NO doctrine, creates NO new state-store. The
    down-lane stays active-rung + selection-scoped; unsourced rungs are surfaced, not
    invented."""
    zone_root = os.path.abspath(zone_root)
    if current_tic is None:
        current_tic = _resolve_federation_tic(zone_root)
    if opened_tic is None:
        opened_tic = current_tic

    sel = select_kis_per_rung(zone_root, window_days=window_days)
    cov_idx = _downlane_coverage_index(zone_root)

    rung_records = sel.get("rungs", [])
    if rung is not None:
        rr = _resolve_rung_in_selection(sel, rung)
        rung_records = [rr] if rr is not None else []

    rungs_out, due_now = [], []
    campaign_pairs = never = stale = fresh = 0

    for rr in rung_records:
        rung_dir = rr["dir"]
        rung_name = rr["rung"]
        idents = {rung_dir, rung_name, os.path.basename(rung_dir)}
        cands = rr.get("ki_candidates") or []
        auditable = bool(cands)

        rec = {
            "rung": rung_name, "dir": rung_dir,
            "concern_source": rr.get("concern_source"),
            "recommend_fork_A_declare": rr.get("recommend_fork_A_declare", False),
            "auditable": auditable,
        }
        if not auditable:
            rec["skip_reason"] = rr.get("note") or (
                "no Stage-1 KI candidates — cannot down-audit this rung until its "
                "concerns are sourced (fork-A declaration / re-derive owed). Surfaced, "
                "not invented (Disagreement-as-evidence).")
            rec["pairs"] = []
            rungs_out.append(rec)
            continue

        targets = cands[:top]
        pairs = []
        for c in targets:
            ki_id = c["invariant_id"]
            cov = _downlane_coverage_for_pair(
                cov_idx, idents, ki_id, current_tic, coverage_stale_tics)
            pair = {"ki_id": ki_id, "name": c.get("name", ""),
                    "selection_score": c.get("score")}
            pair.update(cov)
            pairs.append(pair)
            campaign_pairs += 1
            if cov["coverage"] == "never_audited":
                never += 1
                due_now.append({"rung": rung_name, "dir": rung_dir, "ki_id": ki_id,
                                "name": c.get("name", ""), "reason": "never_audited",
                                "last_audited_tic": None, "tics_since": None})
            elif cov["coverage"] == "stale":
                stale += 1
                due_now.append({"rung": rung_name, "dir": rung_dir, "ki_id": ki_id,
                                "name": c.get("name", ""), "reason": "stale",
                                "last_audited_tic": cov["last_audited_tic"],
                                "tics_since": cov["tics_since"]})
            else:
                fresh += 1
        rec["pairs"] = pairs
        rec["due_count"] = sum(1 for p in pairs
                               if p["coverage"] in ("never_audited", "stale"))

        if include_packets:
            packet = build_downaudit_packet(
                zone_root, rung_dir, ki_ids=None, top=top,
                opened_tic=opened_tic, window_days=window_days)
            rec["packet"] = packet
            rec["packet_ok"] = bool(packet.get("ok"))
        rungs_out.append(rec)

    # never_audited first, then stale oldest-first (largest tics_since first)
    due_now.sort(key=lambda d: (0 if d["reason"] == "never_audited" else 1,
                                -(d.get("tics_since") or 0)))

    return {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "zone_root": zone_root,
        "stage": "C9 down-lane campaign (read-only RUNTIME driver — Stage 0→1→2 + coverage)",
        "_status": "Down-lane campaign PLAN — read-only RUNTIME driver (M1). Assembles "
                   "the full Stage-2 down-audit packet-set across the active rung set in "
                   "one pass + a coverage/due manifest from the EXISTING finding "
                   "manifold. NOT verdicts (the ladder-auditor judges), NOT a mutation "
                   "(Stage 4 /review-gated).",
        "_fence": "center-hold: runs no down-audit itself, emits no finding, opens no "
                  "arena, demotes nothing, creates no new state-store. Coverage is read "
                  "from the signal manifold; a 'due' pair is a campaign HYPOTHESIS, "
                  "never a verdict about fit (Arena Velocity Guard).",
        "current_tic": current_tic,
        "opened_tic": opened_tic,
        "coverage_stale_tics": coverage_stale_tics,
        "top_per_rung": top,
        "rung_filter": rung,
        "include_packets": include_packets,
        "concern_source": sel.get("concern_source"),
        "scope_declaration": (
            "Composes the wired read-only stages: Stage-0 discover_active_rungs (rung "
            "marker + recency), Stage-1 select_kis_per_rung (KI.tags ∩ rung.concerns, "
            "CANDIDATE), Stage-2 build_downaudit_packet (the ladder-auditor's read-only "
            "judgment packet) — for every ACTIVE, SOURCED rung. Coverage is read from "
            "the down-audit finding manifold (load_downaudit_findings, terminal-per-id), "
            "keyed (rung-identity, ki_id) → latest opened_tic. CANNOT judge fit (the "
            "auditor does), CANNOT down-audit an unsourced rung (surfaced, not invented), "
            "does not pre-bias toward demotion. coverage_stale_tics (default "
            f"{coverage_stale_tics}) is a heuristic re-audit window, overridable, never "
            "a gate."
        ),
        "active_rung_count": sel.get("active_rung_count"),
        "campaigned_rung_count": len(rungs_out),
        "reconciliation": sel.get("reconciliation", {}),
        "coverage_summary": {
            "campaign_pairs": campaign_pairs,
            "never_audited": never,
            "stale": stale,
            "fresh": fresh,
            "due_now": never + stale,
        },
        "rungs": rungs_out,
        "due_now": due_now,
        "dispatch_hint": (
            "Spawn one read-only ladder-auditor seat per packet (or a parallel 4-seat "
            "medley, as the tic-493 campaign did). The seat declares its fire-shape "
            "envelope + the D3 reflexive caveat, judges each (rung, KI), and returns "
            "verdicts as text. The ORCHESTRATOR (sole writer) lands each via "
            "`ladder-audit.py emit-finding`. This driver assembles + tracks coverage; it "
            "never judges, emits, or inscribes. Prioritize due_now (never_audited first)."
        ),
    }


def format_downlane_campaign(result):
    """Human-readable down-lane campaign plan (read-only RUNTIME driver)."""
    lines = []
    lines.append("=" * 74)
    lines.append("LADDER DOWN-LANE · campaign RUNTIME driver (read-only; M1 — Stage 0→1→2 + coverage)")
    lines.append("=" * 74)
    lines.append(f"  Zone root:      {result.get('zone_root', '?')}")
    lines.append(f"  Current tic:    {result.get('current_tic')}    opened_tic: {result.get('opened_tic')}")
    lines.append(f"  Concern source: {result.get('concern_source', '?')}")
    lines.append(f"  Coverage-stale: ≥{result.get('coverage_stale_tics')} tics    top/rung: {result.get('top_per_rung')}")
    lines.append(f"  Active rungs:   {result.get('active_rung_count')}    campaigned: {result.get('campaigned_rung_count')}")
    lines.append("")
    lines.append("  " + result.get("_status", ""))
    lines.append("  " + result.get("_fence", ""))
    lines.append("")
    cs = result.get("coverage_summary", {})
    lines.append("COVERAGE SUMMARY (campaign pairs across active rungs):")
    lines.append("-" * 74)
    lines.append(f"  pairs: {cs.get('campaign_pairs', 0)}    "
                 f"never-audited: {cs.get('never_audited', 0)}    "
                 f"stale: {cs.get('stale', 0)}    fresh: {cs.get('fresh', 0)}    "
                 f"→ DUE NOW: {cs.get('due_now', 0)}")
    rec = result.get("reconciliation", {})
    if rec.get("active_but_unsourced"):
        lines.append("  ⚠ active-but-unsourced (cannot down-audit until sourced): "
                     + ", ".join(rec["active_but_unsourced"]))
    lines.append("")
    lines.append("PER-RUNG COVERAGE (selection ≠ verdict; a 'due' pair is a campaign hypothesis):")
    lines.append("-" * 74)
    for r in result.get("rungs", []):
        if not r.get("auditable"):
            lines.append(f"  · {r['rung']}  [{r['dir']}] — SKIP: {(r.get('skip_reason', '') or '')[:62]}")
            continue
        pk = ""
        if result.get("include_packets"):
            pk = " · packet:OK" if r.get("packet_ok") else " · packet:ERR"
        lines.append(f"  ▸ {r['rung']}  [{r['dir']}]  "
                     f"({r.get('due_count', 0)} due / {len(r.get('pairs', []))} pairs){pk}")
        for p in r.get("pairs", []):
            cov = p["coverage"]
            mark = {"never_audited": "○ NEVER", "stale": "◐ STALE",
                    "fresh": "● fresh "}.get(cov, cov)
            if cov == "stale":
                extra = f"  (last tic {p['last_audited_tic']}, {p['tics_since']}t ago, was {p['last_verdict']})"
            elif cov == "fresh":
                extra = f"  (tic {p['last_audited_tic']}, {p['last_verdict']})"
            else:
                extra = ""
            lines.append(f"      {mark}  {p['ki_id']}{extra}")
    due = result.get("due_now", [])
    lines.append("")
    lines.append(f"DUE-NOW CAMPAIGN ({len(due)} pairs — recommended next ladder-auditor dispatch, never_audited first):")
    lines.append("-" * 74)
    if not due:
        lines.append("  (none — every campaign pair is fresh within the coverage window)")
    for d in due[:40]:
        if d["reason"] == "never_audited":
            lines.append(f"  ○ {d['rung'][:26]:<26} {d['ki_id']}  [never audited]")
        else:
            lines.append(f"  ◐ {d['rung'][:26]:<26} {d['ki_id']}  [stale {d.get('tics_since')}t]")
    if len(due) > 40:
        lines.append(f"  … + {len(due) - 40} more (use --json for the full list)")
    lines.append("")
    lines.append("  dispatch: " + result.get("dispatch_hint", ""))
    return "\n".join(lines)


# ─── M2 staleness routing — S0 detector + S1 classifier (read-only) ──────────────
# staleness-routing-spec.md §3–§4. The buildable-now DETECTION half of M2: compose
# the staleness signals the federation ALREADY produces (§2) into a per-surface
# staleness-candidate set + a PROPOSED re-examination route — read-only, no doctrine
# mutation, no signal persistence, no cadence wiring. The ACTION half (S2 routing
# inscription) is NOT here — it is /review-gated AND precondition-gated on a real
# Stage-4 `stale`/`damaging` finding (can-it-eat); the demote-class subset of that
# action is RBD-gated (RBD_DEMOTE_CLASS_OUTCOMES). The scan is a COMPOSER, not a new
# freshness metric (tic-503 born: the missing runtime of a multi-stage lane is the
# absent composer, not a missing stage).

_FM_LAST_VALIDATED_RE = re.compile(r"^\s*last_validated_tic:\s*(\d+)", re.MULTILINE)
_FM_STATUS_RE = re.compile(r"^\s*status:\s*([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
_FM_FIRST_AUTHORED_RE = re.compile(r"^\s*first_authored_tic:\s*(\d+)", re.MULTILINE)
# Frontmatter-bearing doctrine surfaces: kernel specs (.md) + typed registries /
# meta sidecars (.yaml / .meta.yaml) that carry the convention.
_FRESHNESS_SUFFIXES = (".md", ".yaml", ".meta.yaml")


def _load_doctrine_freshness(zone_root, current_tic, freshness_stale_tics,
                             freshness_root_rel=FRESHNESS_SCAN_ROOT_REL):
    """Read-only S0a freshness signal: scan the declared doctrine-surface root for
    `last_validated_tic` frontmatter and flag surfaces whose validation is OVERDUE
    (current_tic - last_validated_tic >= freshness_stale_tics).

    A surface WITHOUT a `last_validated_tic` is out-of-signal-scope (declared) — it is
    skipped, never inferred-fresh. Never raises (fail-soft per surface). Returns
    (overdue_list, scanned_count, skipped_no_frontmatter). `overdue` carries status +
    first_authored_tic so the classifier can apply the `needs_mechanization ≠ stale`
    discriminator (a `forward` spec overdue for validation is not stale for being early)."""
    root = Path(zone_root) / freshness_root_rel
    overdue, scanned, skipped = [], 0, 0
    if not root.is_dir():
        return overdue, scanned, skipped
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if not any(p.name.endswith(sfx) for sfx in _FRESHNESS_SUFFIXES):
            continue
        try:
            head = p.read_text(encoding="utf-8")[:4000]
        except (OSError, UnicodeDecodeError):
            continue
        m = _FM_LAST_VALIDATED_RE.search(head)
        if not m:
            skipped += 1
            continue
        scanned += 1
        lv = int(m.group(1))
        if not isinstance(current_tic, int):
            continue
        tics_since = current_tic - lv
        if tics_since < freshness_stale_tics:
            continue
        sm = _FM_STATUS_RE.search(head)
        fm = _FM_FIRST_AUTHORED_RE.search(head)
        overdue.append({
            "surface": os.path.relpath(str(p), zone_root),
            "last_validated_tic": lv,
            "tics_since_validated": tics_since,
            "status": (sm.group(1) if sm else None),
            "first_authored_tic": (int(fm.group(1)) if fm else None),
        })
    overdue.sort(key=lambda d: -(d.get("tics_since_validated") or 0))
    return overdue, scanned, skipped


def _classify_staleness_candidate(signal, payload):
    """S1 classifier (read-only judgment): map a staleness candidate to a PROPOSED
    RE-EXAMINATION route — never a demote. Detection-only: with no confirmed Stage-4
    `stale` verdict in hand, the only honest route is to re-examine (re-validate /
    re-test / re-audit) so a /stage arena can CONFIRM or dismiss the hypothesis. The
    §3 routes (clarify/localize/supersede/retire) are post-arena and live in the
    /review-gated + RBD-gated ACTION half — surfaced here as the gated downstream, not
    proposed. Returns (proposed_next_action, route_note)."""
    if signal == "freshness_overdue":
        status = payload.get("status")
        if status == "forward":
            return ("revalidate_or_confirm_still_forward",
                    "forward spec overdue for a freshness check — re-validate against "
                    "current substrate OR confirm still-forward; NOT a demote "
                    "(needs_mechanization ≠ stale — do not demote forward-doctrine "
                    "for being early).")
        if status == "dormant":
            return ("reconfirm_dormancy",
                    "dormant spec overdue — re-confirm dormancy still holds or its "
                    "trigger conditions changed; NOT a demote.")
        return ("revalidate",
                "active spec overdue for the Volatility-Handling L4-probe — re-validate "
                "claims against current substrate; overdue ≠ confirmed-stale.")
    if signal == "held_dissonance_stale":
        return ("retest_dissonance",
                "held dissonance carried past its re-test window (D4) — fire a fresh "
                "down-audit so it is not silently immortal; re-test, never auto-resolve.")
    if signal == "coverage_stale":
        return ("reaudit",
                "(rung,KI) coverage stale — re-run the C9 down-lane (down-lane-run) for "
                "this pair; coverage-staleness is an INPUT, not the doctrine verdict.")
    return ("review", "unclassified staleness candidate — route to /review.")


def staleness_scan(zone_root, current_tic=None,
                   freshness_stale_tics=FRESHNESS_STALE_TICS,
                   coverage_stale_tics=DOWNAUDIT_COVERAGE_STALE_TICS,
                   window_days=ACTIVE_RUNG_WINDOW_DAYS,
                   freshness_root_rel=FRESHNESS_SCAN_ROOT_REL):
    """M2 staleness DETECTION (S0 detector + S1 classifier) — read-only.

    Composes the staleness signals the federation already produces (staleness-routing-
    spec.md §2) into ONE staleness-candidate set per surface/finding, each with a
    PROPOSED re-examination route (S1). Read-only / no-new-authority: reads frontmatter
    + the EXISTING finding manifold + the C9 coverage manifold; persists NOTHING, emits
    NO signal, opens NO arena, mutates NO doctrine, wires into NO cadence. A candidate
    is a staleness HYPOTHESIS, never a verdict — convergence routes to a /stage arena →
    /review (Arena Velocity Guard). The ACTION half (S2 routing inscription) is NOT
    here: it is /review-gated AND precondition-gated on a real Stage-4 `stale`/`damaging`
    finding (can-it-eat); demote-class routes are additionally RBD-gated."""
    zone_root = os.path.abspath(zone_root)
    if current_tic is None:
        current_tic = _resolve_federation_tic(zone_root)

    candidates = []

    # S0a — freshness: doctrine surfaces overdue for re-validation (last_validated_tic).
    overdue, fresh_scanned, fresh_skipped = _load_doctrine_freshness(
        zone_root, current_tic, freshness_stale_tics, freshness_root_rel)
    for o in overdue:
        action, note = _classify_staleness_candidate("freshness_overdue", o)
        candidates.append({
            "signal": "freshness_overdue",
            "target": o["surface"],
            "detail": (f"last_validated_tic={o['last_validated_tic']} "
                       f"({o['tics_since_validated']}t ago), status={o['status']}"),
            "tics_since": o["tics_since_validated"],
            "status": o.get("status"),
            "proposed_next_action": action,
            "route_note": note,
            "confirmed_stale": False,
            "demote_class_route": False,
        })

    # S0b — held-dissonance staleness: reuse the Stage-4 finding projection (D4).
    findings = list_downaudit_findings(zone_root, current_tic=current_tic)
    held_stale = findings.get("stale_held_for_retest", [])
    for h in held_stale:
        action, note = _classify_staleness_candidate("held_dissonance_stale", h)
        candidates.append({
            "signal": "held_dissonance_stale",
            "target": f"{h.get('ki_id')} @ {h.get('rung')}",
            "detail": (f"held {h.get('tics_held')}t (≥{DISSONANCE_STALE_TICS}) "
                       f"[{h.get('signal_id')}]"),
            "tics_since": h.get("tics_held"),
            "signal_id": h.get("signal_id"),
            "proposed_next_action": action,
            "route_note": note,
            "confirmed_stale": False,
            "demote_class_route": False,
        })

    # S0c — coverage staleness: reuse the C9 down-lane coverage manifold (fast path).
    camp = run_downlane_campaign(
        zone_root, current_tic=current_tic, coverage_stale_tics=coverage_stale_tics,
        window_days=window_days, include_packets=False)
    cov_stale = [d for d in camp.get("due_now", []) if d.get("reason") == "stale"]
    for c in cov_stale:
        action, note = _classify_staleness_candidate("coverage_stale", c)
        candidates.append({
            "signal": "coverage_stale",
            "target": f"{c.get('ki_id')} @ {c.get('rung')}",
            "detail": (f"last audited tic {c.get('last_audited_tic')} "
                       f"({c.get('tics_since')}t ago, ≥{coverage_stale_tics})"),
            "tics_since": c.get("tics_since"),
            "proposed_next_action": action,
            "route_note": note,
            "confirmed_stale": False,
            "demote_class_route": False,
        })

    by_signal = defaultdict(int)
    for c in candidates:
        by_signal[c["signal"]] += 1

    return {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "zone_root": zone_root,
        "stage": "M2 staleness DETECTION (read-only S0 detector + S1 classifier)",
        "_status": "Staleness candidate set — read-only DETECTION half of M2 "
                   "(staleness-routing-spec.md §3–§4). Composes the EXISTING staleness "
                   "signals (§2) into candidates + PROPOSED re-examination routes. NOT "
                   "verdicts (a /stage arena → /review confirms), NOT a mutation.",
        "_fence": "center-hold: read-only — persists nothing, emits no signal, opens no "
                  "arena, demotes nothing, mutates no doctrine, wires into no cadence. A "
                  "candidate is a staleness HYPOTHESIS (Arena Velocity Guard). Every "
                  "proposed route is a RE-EXAMINATION (re-validate/re-test/re-audit), "
                  "never a demote — the demote-class ACTION (S2) is /review-gated AND "
                  "precondition-gated on a real Stage-4 `stale` finding AND RBD-gated.",
        "current_tic": current_tic,
        "freshness_stale_tics": freshness_stale_tics,
        "coverage_stale_tics": coverage_stale_tics,
        "scope_declaration": (
            "S0a freshness: scans frontmatter `last_validated_tic` under "
            f"{freshness_root_rel}/ (the declared `status`+`last_validated_tic` "
            "convention surface; surfaces without it are out-of-signal-scope, never "
            "inferred-fresh). S0b held-dissonance: reuses list-findings "
            "stale_held_for_retest (DISSONANCE_STALE_TICS, D4). S0c coverage: reuses "
            "down-lane-run due_now[reason=stale] (DOWNAUDIT_COVERAGE_STALE_TICS). "
            "CANNOT confirm staleness (a /stage arena does); freshness-overdue means "
            "overdue for a re-validation CHECK (Volatility Handling L4-probe), NOT "
            "confirmed-stale. Thresholds are heuristic re-examination windows, "
            "overridable, NEVER gates."
        ),
        "freshness_surfaces_scanned": fresh_scanned,
        "freshness_surfaces_skipped_no_frontmatter": fresh_skipped,
        "candidate_count": len(candidates),
        "candidates_by_signal": dict(by_signal),
        "candidates": candidates,
        "forward_residues": {
            "supersession_orphan_detection": (
                "FORWARD (SR2) — a superseded-but-not-transitioned entry looks stale "
                "but its route is already known (supersede); needs disambiguation "
                "before detection, not built here."),
            "persistence_residue": (
                "BUILT DORMANT (build-and-gate, tic 510) — `persist_staleness_candidates` "
                "emits a per-class `ladder.staleness_candidate` rollup residue (NOT this "
                "read-only scan); gated on M2_STALENESS_PERSISTENCE_RATIFIED (default False). "
                "`--persist` surfaces the plan; /review flips the flag to make it write."),
            "cadence_wiring": (
                "BUILT DORMANT (build-and-gate, tic 510) — cadence-ops.py "
                "`run_m2_staleness_cadence_step` auto-fires this read-only scan on the "
                "ladder_audit cadence (mod 5); gated on M2_STALENESS_CADENCE_RATIFIED "
                "(default False). /review flips the flag (mirrors the C9 cadence auto-fire)."),
            "action_half_S2": (
                "FORWARD (precondition-gated) — staleness ROUTING inscription "
                "(clarify/localize/supersede/retire/demote) waits on a real Stage-4 "
                "`stale`/`damaging` finding; demote-class is RBD-gated "
                f"({', '.join(RBD_DEMOTE_CLASS_OUTCOMES)})."),
        },
    }


def format_staleness_scan(result):
    """Human-readable M2 staleness DETECTION (read-only S0+S1)."""
    lines = []
    lines.append("=" * 74)
    lines.append("LADDER STALENESS-SCAN · M2 DETECTION (read-only; S0 detector + S1 classifier)")
    lines.append("=" * 74)
    lines.append(f"  Zone root:      {result.get('zone_root', '?')}")
    lines.append(f"  Current tic:    {result.get('current_tic')}")
    lines.append(f"  Freshness-stale: ≥{result.get('freshness_stale_tics')}t    "
                 f"coverage-stale: ≥{result.get('coverage_stale_tics')}t")
    lines.append(f"  Freshness surfaces: {result.get('freshness_surfaces_scanned')} scanned, "
                 f"{result.get('freshness_surfaces_skipped_no_frontmatter')} skipped (no frontmatter)")
    lines.append("")
    lines.append("  " + result.get("_status", ""))
    lines.append("  " + result.get("_fence", ""))
    lines.append("")
    lines.append("  scope: " + result.get("scope_declaration", ""))
    lines.append("")
    by = result.get("candidates_by_signal", {})
    lines.append(f"CANDIDATE SUMMARY ({result.get('candidate_count', 0)} total — "
                 "each a HYPOTHESIS, route = re-examination, never a demote):")
    lines.append("-" * 74)
    lines.append(f"  freshness_overdue: {by.get('freshness_overdue', 0)}    "
                 f"held_dissonance_stale: {by.get('held_dissonance_stale', 0)}    "
                 f"coverage_stale: {by.get('coverage_stale', 0)}")
    lines.append("")
    for sig in ("freshness_overdue", "held_dissonance_stale", "coverage_stale"):
        items = [c for c in result.get("candidates", []) if c["signal"] == sig]
        if not items:
            continue
        lines.append(f"{sig.upper()} ({len(items)}):")
        lines.append("-" * 74)
        for c in items[:40]:
            lines.append(f"  · {c['target']}")
            lines.append(f"      {c['detail']}  → {c['proposed_next_action']}")
        if len(items) > 40:
            lines.append(f"  … + {len(items) - 40} more (use --json for the full list)")
        lines.append("")
    fr = result.get("forward_residues", {})
    lines.append("FORWARD / GATED (not in this read-only scan):")
    lines.append("-" * 74)
    for k in ("persistence_residue", "cadence_wiring", "action_half_S2",
              "supersession_orphan_detection"):
        if k in fr:
            lines.append(f"  · {k}: {fr[k]}")
    return "\n".join(lines)


# ─── M2 ACTIVATION piece 1: staleness-candidate persistence residue (build-and-gate; tic 510) ───
# The read-only DETECTION half (staleness_scan, S0+S1, tic 509) produces a candidate set but
# persists NOTHING — the federation can SEE stale doctrine only WITHIN one scan, never ACROSS
# tics. This piece persists the candidate set as a thin terminal residue on the EXISTING signal
# manifold so /review has a durable marker (the observability half of M2; staleness-routing-
# spec.md §3 last row + §4).
#
# Build-and-gate (cgg-ledger#build-and-gate-ratified-flag-gated-consumer): ships DORMANT —
# M2_STALENESS_PERSISTENCE_RATIFIED defaults False. While dormant `--persist` surfaces the
# would-be emit/resolve PLAN and writes NOTHING; /review flips the flag (ratification IS the
# flip; no further code change). Dual-proven: dormancy (plan-only, writes nothing) + activation
# (--force-persist → the rollup signals land + heal).
#
# Emission GRANULARITY (cgg-ledger#emission-granularity-is-the-leak): NOT one signal per
# candidate (the 89 freshness-overdue would FLOOD the manifold) — ONE rollup ray PER staleness-
# signal CLASS (the per-owner rollup the KI prescribes; ≤3 active). The CURRENT count + the full
# candidate list live in the regenerable scan artifact (overwrite-latest); the signal is the
# durable condition-present PING (STABLE id per class), so it never carries a stale count.
# EMIT/RESOLVE symmetry (cgg-ledger#machine-emitter-emit-resolve-symmetry-and-chronological-
# status-truth): a class that heals to 0 candidates resolves its prior rollup — no write-only
# TENSION debt. SR4 (per-candidate decay/re-test discipline) stays a FORWARD residue; the rollup
# is a condition present/absent marker, not a per-candidate accumulation surface.
#
# Center-hold: staleness_scan() itself stays READ-ONLY (unchanged; persists nothing — the
# tic-509 contract). This residue is a SEPARATE gated function. A rollup is a HYPOTHESIS ping
# (kind WATCH), opens no arena, mutates no doctrine, proposes only re-examination; NO new store.
M2_STALENESS_PERSISTENCE_RATIFIED = False  # build-and-gate: DORMANT — /review flips False→True (ratification IS the flip; no further code change)
STALENESS_CANDIDATE_SIGNAL_TYPE = "ladder.staleness_candidate"
# Rollup observability weight: WATCH so /review sees it; modest volume — a re-examination
# HYPOTHESIS is softer pressure than a down-audit `damaging` (40) / `hold_in_dissonance` (35).
STALENESS_CANDIDATE_VOLUME = 20


def compute_staleness_rollup_signal_id(staleness_signal):
    """Deterministic, condition-stable signal ID for a staleness-candidate ROLLUP.

    Keyed on (signal_type, staleness_signal class) — STABLE per class, NOT tic/count — so a
    re-scan dedups idempotently (the COUNT lives in the regenerable artifact, never frozen in
    the signal) and there is exactly ONE active rollup per staleness-signal class
    (Emission-Granularity-Is-the-Leak: the per-owner rollup ray; Signal ID Determinism KI).
    """
    parts = [STALENESS_CANDIDATE_SIGNAL_TYPE, f"class={staleness_signal}"]
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:8]
    return f"sig_ladder_staleness_candidate_{h}"


def load_staleness_rollups(zone_root):
    """Read staleness-candidate rollup signals from the manifold, terminal-per-id projected
    (latest entry wins — the Terminal-State Valve discipline). Read-only; the active-manifest
    file is skipped (thin entries). Returns the latest signal dict per signal_id."""
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    signal_dir = Path(al_path) / "signals"
    if not signal_dir.is_dir():
        return []
    latest = {}
    for f in sorted(signal_dir.glob("*.jsonl")):
        if f.name == "active-manifest.jsonl":
            continue
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("signal_type") != STALENESS_CANDIDATE_SIGNAL_TYPE:
                continue
            eid = d.get("signal_id") or d.get("id")
            if eid:
                latest[eid] = d
    return list(latest.values())


def persist_staleness_candidates(zone_root, scan_result, opened_tic=None, *,
                                 force=False, dry_run=False,
                                 source="ladder-audit.py", artifact_rel=None):
    """M2 ACTIVATION piece 1 (build-and-gate): persist the read-only scan's candidate set as a
    thin terminal rollup residue on the EXISTING signal manifold — ONE rollup ray per staleness-
    signal CLASS (Emission-Granularity-Is-the-Leak), with emit-on-present / resolve-on-heal
    symmetry (Machine-Emitter Emit/Resolve Symmetry). Dedup-at-write on the STABLE per-class id
    (re-scan is idempotent); the CURRENT count lives in the regenerable artifact, never frozen
    in the signal.

    DORMANT unless M2_STALENESS_PERSISTENCE_RATIFIED or `force`: dormant returns the would-be
    emit/resolve PLAN and writes NOTHING (the build-and-gate dormancy surface; /review flips the
    flag — ratification IS the flip). Center-hold: a rollup is a HYPOTHESIS ping (WATCH) — opens
    no arena, mutates no doctrine, proposes only re-examination; no new store. Fail-soft on a
    bare/absent manifold."""
    ratified = M2_STALENESS_PERSISTENCE_RATIFIED or force
    if opened_tic is None:
        opened_tic = scan_result.get("current_tic")

    by_class = defaultdict(list)
    for c in scan_result.get("candidates", []):
        by_class[c["signal"]].append(c)
    present_classes = set(by_class.keys())

    plan_emit = []
    for cls in sorted(present_classes):
        items = by_class[cls]
        plan_emit.append({
            "signal_id": compute_staleness_rollup_signal_id(cls),
            "staleness_signal": cls,
            "candidate_count": len(items),
            "top_targets": [c["target"] for c in items[:5]],
            "proposed_routes": sorted({c["proposed_next_action"] for c in items}),
        })

    # Heal: an active rollup whose class is no longer present this scan → resolve it
    # (emit/resolve symmetry — a healed condition must not leave write-only TENSION debt).
    active_rollups = load_staleness_rollups(zone_root)
    plan_resolve = []
    for sig in active_rollups:
        if not is_active_ray(sig):
            continue
        cls = (sig.get("payload") or {}).get("staleness_signal")
        if cls and cls not in present_classes:
            plan_resolve.append({
                "signal_id": sig.get("signal_id") or sig.get("id"),
                "staleness_signal": cls,
                "reason": "healed — 0 candidates this scan",
            })

    if not ratified:
        return {
            "ran": False, "ratified": False,
            "reason": "DORMANT (build-and-gate: M2_STALENESS_PERSISTENCE_RATIFIED=False; "
                      "/review flips it). The read-only staleness-scan is built + live; only "
                      "the candidate-residue PERSISTENCE is flag-gated. Plan-only — writes nothing.",
            "would_emit": plan_emit,
            "would_resolve": plan_resolve,
            "_fence": "center-hold: dormant = NO write. A rollup is a HYPOTHESIS ping (WATCH); "
                      "opens no arena, mutates no doctrine; no new store.",
        }

    if dry_run:
        return {"ran": False, "ratified": True, "dry_run": True,
                "would_emit": plan_emit, "would_resolve": plan_resolve}

    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    signal_dir = os.path.join(al_path, "signals")
    os.makedirs(signal_dir, exist_ok=True)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    signal_file = os.path.join(signal_dir, f"{date_str}.jsonl")
    manifest_path = os.path.join(signal_dir, "active-manifest.jsonl")

    emitted, deduped = [], []
    for p in plan_emit:
        cls, sig_id = p["staleness_signal"], p["signal_id"]
        summary_text = (f"staleness candidates [{cls}]: {p['candidate_count']} "
                        f"re-examination hypotheses → {', '.join(p['proposed_routes'])} "
                        f"(see artifact; a HYPOTHESIS set, not a verdict)")
        payload = {
            "staleness_signal": cls,
            "candidate_count": p["candidate_count"],
            "top_targets": p["top_targets"],
            "proposed_routes": p["proposed_routes"],
            "opened_tic": opened_tic,
            "scan_artifact": artifact_rel,
            "note": ("read-only DETECTION rollup; the CURRENT count + full set live in the "
                     "regenerable scan artifact (this signal is the durable condition-present "
                     "ping). Every route is a RE-EXAMINATION, never a demote — the S2 ACTION "
                     "half is /review-gated + precondition-gated + RBD-gated."),
        }
        signal = {
            "type": "signal", "id": sig_id, "signal_id": sig_id,
            "signal_type": STALENESS_CANDIDATE_SIGNAL_TYPE,
            "kind": "WATCH", "band": "COGNITIVE", "status": "active",
            "volume": STALENESS_CANDIDATE_VOLUME, "max_volume": 100, "tick_count": 0,
            "subsystem": "ladder_staleness", "source": source,
            "source_date": date_str, "created_at": now.isoformat(),
            "payload": payload, "origin": "deterministic",
        }
        written = dedup_signal_append(signal_file, signal, manifest_path=manifest_path)
        if written:
            dedup_signal_append(manifest_path, {
                "signal_id": sig_id, "signal_type": STALENESS_CANDIDATE_SIGNAL_TYPE,
                "kind": "WATCH", "band": "COGNITIVE", "status": "active",
                "volume": STALENESS_CANDIDATE_VOLUME,
                "source_file": f"signals/{date_str}.jsonl", "summary": summary_text,
            })
            emitted.append(sig_id)
        else:
            deduped.append(sig_id)

    resolved = []
    for r in plan_resolve:
        sig = next((s for s in active_rollups
                    if (s.get("signal_id") or s.get("id")) == r["signal_id"]), None)
        if sig is None:
            continue
        healed = dict(sig)
        healed["status"] = "resolved"
        healed["structural_status"] = "resolved"
        healed["resolved_at"] = now.isoformat()
        hp = dict(healed.get("payload", {}))
        hp["resolution"] = {
            "resolved_to": "healed", "resolved_tic": opened_tic,
            "justification": "0 candidates of this class this scan (emit/resolve symmetry)",
            "made_known": "staleness rollup heal (machine)",
        }
        healed["payload"] = hp
        # Terminal transition = append same signal_id (latest-per-id wins); NOT dedup
        # (which would refuse the duplicate id) — mirrors resolve_downaudit_finding.
        atomic_append_jsonl(signal_file, healed)
        atomic_append_jsonl(manifest_path, {
            "signal_id": r["signal_id"], "signal_type": STALENESS_CANDIDATE_SIGNAL_TYPE,
            "status": "resolved", "structural_status": "resolved",
            "summary": f"staleness rollup [{r['staleness_signal']}] healed (0 candidates)",
        })
        resolved.append(r["signal_id"])

    return {
        "ran": True, "ratified": True,
        "emitted": emitted, "deduplicated": deduped, "resolved": resolved,
        "summary": (f"persisted {len(emitted)} new + {len(deduped)} dedup rollup(s); "
                    f"healed {len(resolved)} (per-class rollup, emit/resolve symmetric)"),
    }


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

    lar = sub.add_parser(
        "list-active-rungs",
        help="Stage-0 down-lane active-rung selector: rank ACTIVE rungs (rung "
             "marker + >=1 recent activity signal) as down-audit sites and list "
             "dormant rungs as excluded. Read-only discovery — no mutation.")
    lar.add_argument("--window-days", type=float, default=ACTIVE_RUNG_WINDOW_DAYS,
                     dest="window_days",
                     help=f"Recency window in days (default {ACTIVE_RUNG_WINDOW_DAYS})")
    lar.add_argument("--zone-root", default=None, dest="zone_root")

    sk = sub.add_parser(
        "select-kis",
        help="Stage-1 down-lane KI-selection-by-applicability: for each ACTIVE "
             "rung, rank the federation KIs that plausibly reach it "
             "(KI.tags ∩ rung.concerns). Read-only CANDIDATE list; no down-audit, "
             "no mutation.")
    sk.add_argument("--concern-source", default=None, dest="concern_source",
                    help="Rung-concern source JSON (default: the tic-467 fork-B "
                         "derive under governance/)")
    sk.add_argument("--window-days", type=float, default=ACTIVE_RUNG_WINDOW_DAYS,
                    dest="window_days",
                    help=f"Stage-0 recency window in days (default {ACTIVE_RUNG_WINDOW_DAYS})")
    sk.add_argument("--top", type=int, default=15,
                    help="Max KI candidates shown per rung in human output "
                         "(JSON always carries the full ranked list)")
    sk.add_argument("--zone-root", default=None, dest="zone_root")

    da = sub.add_parser(
        "down-audit",
        help="Stage-2 down-lane down-audit PACKET: for an ACTIVE rung, assemble the "
             "read-only packet a ladder-auditor consumes to judge rehydration-in-"
             "spirit (clean|N/A|damaging) per KI. Read-only prep — NOT a verdict, "
             "NOT a mutation; the verdict is the auditor's act, landed via emit-finding.")
    da.add_argument("--rung", required=True,
                    help="Active rung to down-audit (dir, name, or basename)")
    da.add_argument("--ki-id", action="append", dest="ki_ids", default=None,
                    help="Specific KI invariant_id to target (repeatable). If omitted, "
                         "defaults to the rung's top-N Stage-1 candidates. An explicit "
                         "id may be OUTSIDE the selection (flagged in_selection:false).")
    da.add_argument("--top", type=int, default=3,
                    help="When --ki-id omitted, how many top Stage-1 candidates to target")
    da.add_argument("--opened-tic", type=int, default=None, dest="opened_tic",
                    help="Tic the down-audit fires (stamped into the packet)")
    da.add_argument("--window-days", type=float, default=ACTIVE_RUNG_WINDOW_DAYS,
                    dest="window_days",
                    help=f"Stage-0 recency window in days (default {ACTIVE_RUNG_WINDOW_DAYS})")
    da.add_argument("--zone-root", default=None, dest="zone_root")

    lf = sub.add_parser(
        "list-findings",
        help="Stage-4 down-lane finding projection: read-only view of the down-audit "
             "finding set (terminal-per-id), grouped by routing, with held-band "
             "(hold_in_dissonance §4) staleness. The /review-surfaced down-lane view. "
             "Read-only — opens no arena, resolves nothing.")
    lf.add_argument("--current-tic", type=int, default=None, dest="current_tic",
                    help="Current federation tic (auto-resolved from the tic log if omitted)")
    lf.add_argument("--zone-root", default=None, dest="zone_root")

    sb = sub.add_parser(
        "stage-brief",
        help="Stage-4 down-lane arena brief: for a `damaging` (or re-tested held) "
             "finding, assemble the read-only `/stage` arena brief (contested "
             "question, opposing-values geometry, KI body, aggregation breadth, legal "
             "outcomes). Read-only prep — does NOT open the arena, does NOT inscribe.")
    sb.add_argument("--signal-id", default=None, dest="signal_id",
                    help="Finding signal_id to brief (e.g. sig_ladder_down_audit_finding_xxxx)")
    sb.add_argument("--rung", default=None,
                    help="Alternative to --signal-id: the rung (with --ki-id)")
    sb.add_argument("--ki-id", default=None, dest="ki_id",
                    help="Alternative to --signal-id: the KI invariant_id (with --rung)")
    sb.add_argument("--current-tic", type=int, default=None, dest="current_tic",
                    help="Current federation tic (auto-resolved if omitted)")
    sb.add_argument("--window-days", type=float, default=ACTIVE_RUNG_WINDOW_DAYS,
                    dest="window_days")
    sb.add_argument("--force-rbd-ratified", action="store_true",
                    dest="force_rbd_ratified",
                    help="Build-and-gate dual-proof: exercise the RATIFIED hard-gate "
                         "surface (demote-class outcomes blocked when inadmissible) "
                         "WITHOUT flipping RBD_DEMOTE_ADMISSION_RATIFIED. /review 505 "
                         "flips the module flag to make it live.")
    sb.add_argument("--zone-root", default=None, dest="zone_root")

    rf = sub.add_parser(
        "resolve-finding",
        help="Stage-4 down-lane finding resolution: receipted terminal transition of "
             "a held/damaging finding SIGNAL (signal-state, NOT doctrine) AFTER /review "
             "rules. /review-gated — requires --review-tic + --resolved-to + "
             "--justification. Does not touch the ledger (demote/reword is /review's act).")
    rf.add_argument("--signal-id", required=True, dest="signal_id",
                    help="Finding signal_id to resolve")
    rf.add_argument("--review-tic", required=True, type=int, dest="review_tic",
                    help="The /review tic that ruled on this finding")
    rf.add_argument("--resolved-to", required=True, dest="resolved_to",
                    choices=sorted(DOWNAUDIT_ARENA_OUTCOMES),
                    help="The arena/review outcome the finding resolved to")
    rf.add_argument("--justification", required=True,
                    help="Why this finding may now go terminal (receipt-required)")
    rf.add_argument("--justification-class", default=None, dest="justification_class",
                    help="Recommended: " + ", ".join(DOWNAUDIT_RESOLUTION_CLASSES))
    rf.add_argument("--irreversible", action="store_true",
                    help="Mark the resolution NOT reversible (default: reversible)")
    rf.add_argument("--made-known", default=None, dest="made_known",
                    help="Where the resolution was surfaced (default: /review tic)")
    rf.add_argument("--resolved-tic", type=int, default=None, dest="resolved_tic",
                    help="Tic of resolution (auto-resolved if omitted)")
    rf.add_argument("--dry-run", action="store_true", dest="dry_run",
                    help="Preview the receipt + resolved row without writing")
    rf.add_argument("--zone-root", default=None, dest="zone_root")

    dlr = sub.add_parser(
        "down-lane-run",
        help="C9 down-lane RUNTIME driver (M1): run Stage 0→1→2 across the active rung "
             "set in ONE read-only pass + compute coverage/due-ness from the EXISTING "
             "finding manifold. The 'missing down-audit runtime' the §1 Sovereign Boot "
             "Authority spec names — turns the hand-chained subcommands into a self-"
             "pacing campaign. Read-only: assembles packets + coverage, emits no "
             "finding, opens no arena, mutates no doctrine, creates no new state-store.")
    dlr.add_argument("--rung", default=None,
                     help="Scope the campaign to one active rung (dir/name/basename). "
                          "Default: all active, sourced rungs.")
    dlr.add_argument("--top", type=int, default=3,
                     help="Top-N Stage-1 candidates per rung to campaign (default 3, "
                          "matching the down-audit packet default)")
    dlr.add_argument("--opened-tic", type=int, default=None, dest="opened_tic",
                     help="Tic stamped into the assembled packets (default: current tic)")
    dlr.add_argument("--current-tic", type=int, default=None, dest="current_tic",
                     help="Current federation tic for coverage staleness "
                          "(auto-resolved from the tic log if omitted)")
    dlr.add_argument("--coverage-stale-tics", type=int,
                     default=DOWNAUDIT_COVERAGE_STALE_TICS, dest="coverage_stale_tics",
                     help="A (rung,KI) pair last audited >= this many tics ago is "
                          f"flagged stale/re-audit (heuristic, default "
                          f"{DOWNAUDIT_COVERAGE_STALE_TICS}; never a gate)")
    dlr.add_argument("--window-days", type=float, default=ACTIVE_RUNG_WINDOW_DAYS,
                     dest="window_days",
                     help=f"Stage-0 recency window in days (default {ACTIVE_RUNG_WINDOW_DAYS})")
    dlr.add_argument("--no-packets", action="store_true", dest="no_packets",
                     help="Skip Stage-2 packet assembly — emit only the coverage/due "
                          "manifest (fast path for cadence display)")
    dlr.add_argument("--zone-root", default=None, dest="zone_root")

    rdr = sub.add_parser(
        "rbd-drill-run",
        help="M1 complement: the RBD doctrine rollback-drill RE-RUNNER (tic-494 memo "
             "rec #2). Compute a FRESH reversibility drill for a target promotion "
             "(tic/commit → cprs_in_scope → doctrine files → reversibility + velocity) "
             "and write a schema-faithful record to the EXISTING rollback-drills lane "
             "the demote-admissibility consumer reads — making the `admissible` path "
             "lifecycle-reachable. Read-only on doctrine; never mutates the worktree "
             "(git apply --check -R verifies only). The demote DECISION stays /review-only.")
    rdr.add_argument("--target-tic", type=int, default=None, dest="target_tic",
                     help="Tic whose promotion the drill measures (resolves the commit "
                          "whose subject names this tic; or pass --target-commit)")
    rdr.add_argument("--target-commit", default=None, dest="target_commit",
                     help="Explicit promotion commit to drill (preferred over --target-tic)")
    rdr.add_argument("--cprs", default=None,
                     help="Comma-separated cprs_in_scope override (CogPR-NNN / cpr_slug); "
                          "default: extracted from the commit message")
    rdr.add_argument("--current-tic", type=int, default=None, dest="current_tic",
                     help="Current federation tic for tics_since_promotion "
                          "(auto-resolved from the tic log if omitted)")
    rdr.add_argument("--dry-run", action="store_true", dest="dry_run",
                     help="Compute the drill record WITHOUT writing (dormancy proof; "
                          "lane unchanged)")
    rdr.add_argument("--zone-root", default=None, dest="zone_root")

    rad = sub.add_parser(
        "rbd-autodrill",
        help="M1 complement: the /review-flow AUTO-INVOCATION of the RBD re-runner on a "
             "demote-class verdict (tic 507). For a target KI, resolve its promotion from "
             "ledger provenance and — DORMANT (build-and-gate) — surface the exact "
             "rbd-drill-run PLAN it would fire; RATIFIED (/review 507 flips "
             "RBD_AUTODRILL_RATIFIED) — auto-fire the re-runner so the consumer reads a "
             "fresh reversibility proof. Read-only on doctrine; the demote DECISION stays "
             "/review-only.")
    rad.add_argument("--target-ki", required=True, dest="target_ki",
                     help="The invariant_id of the demote-class target KI (its ledger "
                          "BODY supplies the promotion provenance)")
    rad.add_argument("--target-tic", type=int, default=None, dest="target_tic",
                     help="Override the promotion tic (else resolved from KI provenance)")
    rad.add_argument("--cprs", default=None,
                     help="Override cprs_in_scope (comma-separated; else from provenance)")
    rad.add_argument("--current-tic", type=int, default=None, dest="current_tic",
                     help="Current federation tic (auto-resolved from the tic log if omitted)")
    rad.add_argument("--force-autodrill", action="store_true", dest="force_autodrill",
                     help="Exercise the RATIFIED firing path WITHOUT flipping the module "
                          "flag (activation proof; fires run_rbd_drill)")
    rad.add_argument("--zone-root", default=None, dest="zone_root")

    ss = sub.add_parser(
        "staleness-scan",
        help="M2 staleness DETECTION (read-only S0 detector + S1 classifier; "
             "staleness-routing-spec.md §3–§4). Composes the EXISTING staleness signals "
             "(last_validated_tic freshness + held-dissonance-stale + coverage-stale) "
             "into a staleness-candidate set + a PROPOSED re-examination route per "
             "candidate. Read-only: persists nothing, emits no signal, opens no arena, "
             "mutates no doctrine, wires into no cadence. A candidate is a HYPOTHESIS; "
             "the demote-class ACTION half (S2) is /review-gated AND precondition-gated "
             "on a real Stage-4 `stale` finding AND RBD-gated.")
    ss.add_argument("--current-tic", type=int, default=None, dest="current_tic",
                    help="Current federation tic (auto-resolved from the tic log if omitted)")
    ss.add_argument("--freshness-stale-tics", type=int, default=FRESHNESS_STALE_TICS,
                    dest="freshness_stale_tics",
                    help="A doctrine surface whose last_validated_tic is >= this many "
                         f"tics behind current is flagged freshness-overdue (heuristic, "
                         f"default {FRESHNESS_STALE_TICS}; never a gate). SR1: per-terrain "
                         "calibration is forward.")
    ss.add_argument("--coverage-stale-tics", type=int,
                    default=DOWNAUDIT_COVERAGE_STALE_TICS, dest="coverage_stale_tics",
                    help=f"Coverage-staleness window (default {DOWNAUDIT_COVERAGE_STALE_TICS}; "
                         "never a gate)")
    ss.add_argument("--freshness-root", default=FRESHNESS_SCAN_ROOT_REL,
                    dest="freshness_root_rel",
                    help="Doctrine-surface root (relative to zone) the freshness scan "
                         f"reads (default {FRESHNESS_SCAN_ROOT_REL})")
    ss.add_argument("--window-days", type=float, default=ACTIVE_RUNG_WINDOW_DAYS,
                    dest="window_days",
                    help=f"Stage-0 recency window in days (default {ACTIVE_RUNG_WINDOW_DAYS})")
    ss.add_argument("--persist", action="store_true",
                    help="M2 ACTIVATION piece 1 (build-and-gate, DORMANT): persist the "
                         "candidate set as a per-class rollup residue on the signal manifold "
                         "(emit-on-present / resolve-on-heal). Gated on "
                         "M2_STALENESS_PERSISTENCE_RATIFIED — dormant surfaces the emit/resolve "
                         "PLAN and writes NOTHING; /review flips the flag to make it persist.")
    ss.add_argument("--force-persist", action="store_true", dest="force_persist",
                    help="Force the persistence ACTIVATION surface (dual-proof: bypasses the "
                         "dormant gate to exercise the full emit/resolve surface before "
                         "ratification; the scan itself stays read-only).")
    ss.add_argument("--zone-root", default=None, dest="zone_root")

    args = parser.parse_args()

    if args.command == "list-findings":
        zone_root = args.zone_root or args.project_dir or resolve_zone_root()
        result = list_downaudit_findings(zone_root, current_tic=args.current_tic)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(format_findings_list(result))
        return

    if args.command == "stage-brief":
        zone_root = args.zone_root or args.project_dir or resolve_zone_root()
        brief = build_stage_brief(
            zone_root, signal_id=args.signal_id, rung=args.rung, ki_id=args.ki_id,
            current_tic=args.current_tic, window_days=args.window_days,
            force_rbd_ratified=args.force_rbd_ratified)
        if args.json:
            print(json.dumps(brief, indent=2))
        else:
            print(format_stage_brief(brief))
        return

    if args.command == "resolve-finding":
        zone_root = args.zone_root or args.project_dir or resolve_zone_root()
        result = resolve_downaudit_finding(
            zone_root, args.signal_id, args.review_tic, args.resolved_to,
            args.justification, justification_class=args.justification_class,
            reversible=(not args.irreversible), made_known=args.made_known,
            resolved_tic=args.resolved_tic, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
        return

    if args.command == "staleness-scan":
        zone_root = args.zone_root or args.project_dir or resolve_zone_root()
        result = staleness_scan(
            zone_root, current_tic=args.current_tic,
            freshness_stale_tics=args.freshness_stale_tics,
            coverage_stale_tics=args.coverage_stale_tics,
            window_days=args.window_days,
            freshness_root_rel=args.freshness_root_rel)
        # M2 ACTIVATION piece 1 (build-and-gate): persist the candidate set as a per-class
        # rollup residue. The scan above stays READ-ONLY; persistence is the SEPARATE gated
        # function. Dormant (default) → plan-only, writes nothing. /review flips the flag.
        if args.persist or args.force_persist:
            result["persistence"] = persist_staleness_candidates(
                zone_root, result, opened_tic=result.get("current_tic"),
                force=args.force_persist, artifact_rel=args.output)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(f"Staleness scan written to {args.output}")
            if "persistence" in result:
                print(f"Persistence: {result['persistence'].get('reason') or result['persistence'].get('summary')}")
        elif args.json:
            print(json.dumps(result, indent=2))
        else:
            print(format_staleness_scan(result))
            if "persistence" in result:
                pz = result["persistence"]
                print("")
                print("PERSISTENCE (M2 ACTIVATION piece 1, build-and-gate):")
                print("-" * 74)
                print(f"  {pz.get('reason') or pz.get('summary')}")
                if not pz.get("ratified"):
                    we, wr = pz.get("would_emit", []), pz.get("would_resolve", [])
                    print(f"  would emit {len(we)} rollup(s), resolve {len(wr)} (DORMANT — wrote nothing)")
        return

    if args.command == "down-lane-run":
        zone_root = args.zone_root or args.project_dir or resolve_zone_root()
        result = run_downlane_campaign(
            zone_root, rung=args.rung, top=args.top, opened_tic=args.opened_tic,
            current_tic=args.current_tic,
            coverage_stale_tics=args.coverage_stale_tics,
            window_days=args.window_days, include_packets=(not args.no_packets))
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(f"Down-lane campaign written to {args.output}")
        elif args.json:
            print(json.dumps(result, indent=2))
        else:
            print(format_downlane_campaign(result))
        return

    if args.command == "rbd-drill-run":
        zone_root = args.zone_root or args.project_dir or resolve_zone_root()
        cprs = None
        if args.cprs:
            cprs = [c.strip() for c in args.cprs.split(",") if c.strip()]
        result = run_rbd_drill(
            zone_root, target_tic=args.target_tic, target_commit=args.target_commit,
            cprs=cprs, current_tic=args.current_tic, dry_run=args.dry_run)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(f"RBD drill result written to {args.output}")
        elif args.json:
            print(json.dumps(result, indent=2))
        else:
            print(format_rbd_drill(result))
        return

    if args.command == "rbd-autodrill":
        zone_root = args.zone_root or args.project_dir or resolve_zone_root()
        # Resolve the KI body from the federation ledger (its provenance drives resolution).
        ki_body = ""
        try:
            ledger_path = os.path.join(
                audit_logs_path(zone_root, load_ticzone(zone_root)), LEDGER_REL)
            kis = _parse_ledger_kis(ledger_path, include_body=True)
            ki = next((k for k in kis if k["invariant_id"] == args.target_ki), None)
            if ki:
                ki_body = ki.get("body", "")
        except Exception:  # noqa: BLE001 — fail-soft; explicit overrides can still resolve
            ki_body = ""
        cprs = None
        if args.cprs:
            cprs = [c.strip() for c in args.cprs.split(",") if c.strip()]
        ratified = RBD_AUTODRILL_RATIFIED or args.force_autodrill
        result = rbd_autodrill_for_demote(
            zone_root, args.target_ki, ki_body=ki_body, current_tic=args.current_tic,
            target_tic=args.target_tic, cprs=cprs, ratified=ratified)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(f"RBD autodrill result written to {args.output}")
        elif args.json:
            print(json.dumps(result, indent=2))
        else:
            print(format_rbd_autodrill(result))
        return

    if args.command == "down-audit":
        zone_root = args.zone_root or args.project_dir or resolve_zone_root()
        packet = build_downaudit_packet(
            zone_root, args.rung, ki_ids=args.ki_ids, top=args.top,
            opened_tic=args.opened_tic, window_days=args.window_days)
        if args.json:
            print(json.dumps(packet, indent=2))
        else:
            print(format_downaudit_packet(packet))
        return

    if args.command == "select-kis":
        zone_root = args.zone_root or args.project_dir or resolve_zone_root()
        result = select_kis_per_rung(zone_root, concern_source=args.concern_source,
                                     window_days=args.window_days)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(format_select_kis(result, top=args.top))
        return

    if args.command == "list-active-rungs":
        zone_root = args.zone_root or args.project_dir or resolve_zone_root()
        result = discover_active_rungs(zone_root, window_days=args.window_days)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(format_active_rungs(result))
        return

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
