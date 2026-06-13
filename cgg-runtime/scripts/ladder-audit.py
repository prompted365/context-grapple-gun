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

    args = parser.parse_args()

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
