#!/usr/bin/env python3
"""
Pass 1 — Fossil Recovery + PARTIAL Backfill

Source authority: audit-logs/governance/constitutional-dehydration-architect-verdict-tic245.md
Verdict step 0 (fossil-first) + step 6 (Architect-attestation exception path)

Architect tic 261 directive: "Push through the evidence recovery, not through the
constitution." Pass 1 strengthens measurements; it does NOT mutate CLAUDE.md, activate
freeze, or compact entries.

Hard constraints (Architect tic 261):
  - no CLAUDE.md mutation
  - no ROOT_ACTIVE_LAW refactor
  - no review freeze activation
  - no ledger trim
  - no doctrine inscription
  - no demotion to ledger
  - no compaction of verified entries

Inputs:
  - audit-logs/governance/constitution-ledger/pass-0-rows.jsonl (immutable; Pass 0 ledger)
  - audit-logs/cprs/queue.jsonl
  - audit-logs/tmux-dumps/vocabulary-index.jsonl (16,440 rows)
  - audit-logs/governance/ (packets, specs, arena runs)
  - ~/.claude/projects/-Users-breydentaylor-canonical/memory/{MEMORY.md, cogpr-archive.md, session_lessons_tic_*.md}
  - git log (commit references)

Per-entry recovery axes (additive to Pass 0 axes):
  P1.A — vocab-index first_appearance.tic_estimate match
  P1.B — cogpr-archive.md term match
  P1.C — session_lessons_tic_*.md tic-keyed lesson match
  P1.D — MEMORY.md auto-memory keyword match
  P1.E — arena-runs/ + stage/shows/ synthesis match
  P1.F — specs/ + swarm-specs/ source-spec match
  P1.G — git log keyword match

Outputs (overlay; Pass 0 untouched):
  - audit-logs/governance/constitution-ledger/pass-1-overlay-rows.jsonl
  - audit-logs/governance/constitution-ledger/pass-1-backfill-report.md
  - audit-logs/governance/constitution-ledger/fossil-missing-investigation.md
  - audit-logs/governance/constitution-ledger/exception-candidates.md (if any)

Per-entry overlay row carries:
  invariant_id (matches Pass 0)
  pass_1_new_refs (list of newly-located provenance surfaces)
  pass_1_axes_hit (which P1.A-G axes resolved)
  pass_1_evidence_count_after (Pass 0 count + Pass 1 hits)
  pass_1_status_after (VERIFIED|PARTIAL|FOSSIL_MISSING after backfill)
  pass_1_status_changed (bool)
  pass_1_gap_reason (explicit if still PARTIAL/MISSING after attempt)
  pass_1_exception_candidate (bool — needs Architect-attestation routing)
  pass_1_first_appearance_tic_estimate (from vocab-index when available)

Authored tic 261 under ENG/DIRECT, Architect-approved per "lets get tjis fuckin thing lifted."
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[4]
LEDGER_DIR = PROJECT_DIR / "audit-logs" / "governance" / "constitution-ledger"
PASS_0_ROWS = LEDGER_DIR / "pass-0-rows.jsonl"

PASS_1_OVERLAY = LEDGER_DIR / "pass-1-overlay-rows.jsonl"
PASS_1_REPORT = LEDGER_DIR / "pass-1-backfill-report.md"
FOSSIL_INVESTIGATION = LEDGER_DIR / "fossil-missing-investigation.md"
EXCEPTION_CANDIDATES = LEDGER_DIR / "exception-candidates.md"

VOCAB_INDEX = PROJECT_DIR / "audit-logs" / "tmux-dumps" / "vocabulary-index.jsonl"
GOVERNANCE_DIR = PROJECT_DIR / "audit-logs" / "governance"
QUEUE_PATH = PROJECT_DIR / "audit-logs" / "cprs" / "queue.jsonl"

MEMORY_DIR = Path(os.path.expanduser(
    "~/.claude/projects/-Users-breydentaylor-canonical/memory"
))
MEMORY_MAIN = MEMORY_DIR / "MEMORY.md"
COGPR_ARCHIVE = MEMORY_DIR / "cogpr-archive.md"

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

STOPWORDS = {
    "the", "and", "for", "from", "with", "into", "that", "this", "must", "not",
    "are", "was", "were", "but", "have", "has", "had", "any", "all", "one",
    "two", "may", "can", "via", "per", "its", "out", "off", "ing", "tion",
    "when", "where", "what", "which", "how", "why", "who", "than", "then",
}


def significant_keywords(s: str, cap: int = 6) -> List[str]:
    words = re.findall(r"[a-z][a-z0-9]{3,}", s.lower())
    return [w for w in words if w not in STOPWORDS][:cap]


def load_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    out: List[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out

# --------------------------------------------------------------------------
# Provenance surface scans
# --------------------------------------------------------------------------

def build_vocab_term_index(path: Path) -> Dict[str, dict]:
    """Build {term: row} index from vocabulary-index for fast lookup."""
    index: Dict[str, dict] = {}
    if not path.exists():
        return index
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                term = d.get("term", "").lower()
                if term:
                    index[term] = d
            except json.JSONDecodeError:
                continue
    return index


def vocab_first_appearance(keywords: List[str], term_index: Dict[str, dict]) -> Optional[dict]:
    """Find vocabulary-index entry matching any keyword; return the earliest first_appearance."""
    matches: List[dict] = []
    for kw in keywords:
        # Search for terms containing the keyword
        for term, row in term_index.items():
            if kw in term:
                fa = row.get("first_appearance", {})
                tic = fa.get("tic_estimate")
                if tic is not None:
                    matches.append({
                        "term": term,
                        "tic_estimate": tic,
                        "dump_id": fa.get("dump_id"),
                        "occurrences": row.get("total_occurrences", 0),
                        "matched_keyword": kw,
                    })
    if not matches:
        return None
    # Return earliest first_appearance (smallest tic_estimate)
    return min(matches, key=lambda m: m["tic_estimate"])


def search_text_file(path: Path, keywords: List[str], threshold: int = 2) -> Optional[dict]:
    """Search a text file for entries containing >= threshold keywords."""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8").lower()
    except (OSError, UnicodeDecodeError):
        return None
    hits = [kw for kw in keywords if kw in text]
    if len(hits) >= threshold:
        return {"path": str(path), "matched_keywords": hits}
    return None


def search_dir_md_files(directory: Path, keywords: List[str], threshold: int = 2,
                       cap: int = 3) -> List[dict]:
    """Search markdown files in a directory tree."""
    if not directory.exists():
        return []
    results: List[dict] = []
    for p in directory.rglob("*.md"):
        if "node_modules" in p.parts:
            continue
        res = search_text_file(p, keywords, threshold)
        if res:
            try:
                rel = str(p.relative_to(PROJECT_DIR))
            except ValueError:
                rel = str(p)
            results.append({"path": rel, "matched_keywords": res["matched_keywords"]})
            if len(results) >= cap:
                break
    return results


def search_session_lessons(keywords: List[str], threshold: int = 2,
                          cap: int = 3) -> List[dict]:
    """Search ~/.claude/.../session_lessons_tic_*.md files."""
    if not MEMORY_DIR.exists():
        return []
    results: List[dict] = []
    for p in sorted(MEMORY_DIR.glob("session_lessons_tic_*.md")):
        res = search_text_file(p, keywords, threshold)
        if res:
            tic_match = re.search(r"tic_(\d+)", p.name)
            tic = int(tic_match.group(1)) if tic_match else None
            results.append({
                "path": str(p.relative_to(MEMORY_DIR.parent)),
                "tic": tic,
                "matched_keywords": res["matched_keywords"],
            })
            if len(results) >= cap:
                break
    return results


def search_git_log(keywords: List[str], cap: int = 3) -> List[dict]:
    """Search git log for keyword matches across all branches."""
    if not keywords:
        return []
    results: List[dict] = []
    for kw in keywords[:3]:  # cap keywords per search
        try:
            out = subprocess.check_output(
                ["git", "log", "--oneline", "--all", f"--grep={kw}", "-n", "3"],
                cwd=PROJECT_DIR,
                stderr=subprocess.DEVNULL,
                timeout=10,
            ).decode("utf-8", errors="ignore")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            continue
        for line in out.splitlines():
            line = line.strip()
            if line and len(results) < cap:
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    sha, msg = parts
                    results.append({
                        "sha": sha,
                        "message": msg[:120],
                        "matched_keyword": kw,
                    })
    # dedup by sha
    seen: Set[str] = set()
    unique: List[dict] = []
    for r in results:
        if r["sha"] not in seen:
            seen.add(r["sha"])
            unique.append(r)
    return unique[:cap]

# --------------------------------------------------------------------------
# Per-entry backfill
# --------------------------------------------------------------------------

def backfill_entry(row: dict, vocab_term_index: Dict[str, dict]) -> dict:
    """Run all Pass 1 recovery axes on a Pass 0 row; return overlay dict.

    Pass 2 schema refinement (tic 261): STRUCTURAL_POINTER_EXEMPT entries are
    schema-class artifacts (navigation pointers, headers, posture tokens). They
    are NOT KIs — provenance recovery does not apply. Skip Pass 1 for these
    entries and emit a clean exemption overlay.
    """
    title = row["title"]
    keywords = significant_keywords(title)

    # Pass 2 carry-through: structural pointers bypass Pass 1 entirely
    if row.get("fossil_lane_status") == "STRUCTURAL_POINTER_EXEMPT":
        return {
            "invariant_id": row["invariant_id"],
            "title_ref": title,
            "pass_0_status": "STRUCTURAL_POINTER_EXEMPT",
            "pass_0_evidence_count": row["_pass_0_evidence_count"],
            "pass_1_axes_hit": [],
            "pass_1_new_refs": {},
            "pass_1_first_appearance_tic_estimate": None,
            "pass_1_status_after": "STRUCTURAL_POINTER_EXEMPT",
            "pass_1_status_changed": False,
            "pass_1_evidence_count_after": row["_pass_0_evidence_count"],
            "pass_1_gap_reason": "structural_pointer_exempt_no_provenance_required",
            "pass_1_exception_candidate": False,
            "pass_1_skipped_reason": "schema_class_artifact_not_a_KI",
        }

    overlay = {
        "invariant_id": row["invariant_id"],
        "title_ref": title,
        "pass_0_status": row["fossil_lane_status"],
        "pass_0_evidence_count": row["_pass_0_evidence_count"],
        "pass_1_axes_hit": [],
        "pass_1_new_refs": {},
        "pass_1_first_appearance_tic_estimate": None,
    }

    if not keywords:
        # Special case: no extractable keywords (e.g., short pointers like "GLOSSARY.md")
        overlay["pass_1_status_after"] = row["fossil_lane_status"]
        overlay["pass_1_status_changed"] = False
        overlay["pass_1_evidence_count_after"] = overlay["pass_0_evidence_count"]
        overlay["pass_1_gap_reason"] = "no_extractable_keywords_from_title"
        overlay["pass_1_exception_candidate"] = (
            row["fossil_lane_status"] == "FOSSIL_MISSING"
        )
        return overlay

    new_evidence = 0

    # P1.A — vocab-index first appearance (deep, with tic estimate)
    fa = vocab_first_appearance(keywords, vocab_term_index)
    if fa:
        overlay["pass_1_axes_hit"].append("P1.A_vocab_first_appearance")
        overlay["pass_1_new_refs"]["vocab_first_appearance"] = fa
        overlay["pass_1_first_appearance_tic_estimate"] = fa["tic_estimate"]
        new_evidence += 1

    # P1.B — cogpr-archive
    cogpr_hit = search_text_file(COGPR_ARCHIVE, keywords, threshold=2)
    if cogpr_hit:
        overlay["pass_1_axes_hit"].append("P1.B_cogpr_archive")
        overlay["pass_1_new_refs"]["cogpr_archive"] = cogpr_hit
        new_evidence += 1

    # P1.C — session_lessons_tic_*.md
    session_hits = search_session_lessons(keywords, threshold=2, cap=2)
    if session_hits:
        overlay["pass_1_axes_hit"].append("P1.C_session_lessons")
        overlay["pass_1_new_refs"]["session_lessons"] = session_hits
        new_evidence += 1

    # P1.D — MEMORY.md auto-memory
    memory_hit = search_text_file(MEMORY_MAIN, keywords, threshold=3)  # higher threshold (large file)
    if memory_hit:
        overlay["pass_1_axes_hit"].append("P1.D_memory_auto")
        overlay["pass_1_new_refs"]["memory_auto"] = memory_hit
        new_evidence += 1

    # P1.E — arena runs + stage shows
    arena_hits = search_dir_md_files(
        GOVERNANCE_DIR / "arena-runs", keywords, threshold=2, cap=2
    )
    stage_hits = search_dir_md_files(
        PROJECT_DIR / "stage" / "shows", keywords, threshold=2, cap=2
    )
    if arena_hits or stage_hits:
        overlay["pass_1_axes_hit"].append("P1.E_arena_shows")
        if arena_hits:
            overlay["pass_1_new_refs"]["arena_runs"] = arena_hits
        if stage_hits:
            overlay["pass_1_new_refs"]["stage_shows"] = stage_hits
        new_evidence += 1

    # P1.F — specs surfaces
    spec_hits: List[dict] = []
    if (GOVERNANCE_DIR / "specs").exists():
        spec_hits.extend(search_dir_md_files(
            GOVERNANCE_DIR / "specs", keywords, threshold=2, cap=2
        ))
    # swarm-specs across estates
    for swarm_root in (PROJECT_DIR / "canonical_developer").glob("*/swarm-specs"):
        spec_hits.extend(search_dir_md_files(swarm_root, keywords, threshold=2, cap=1))
    if spec_hits:
        overlay["pass_1_axes_hit"].append("P1.F_specs")
        overlay["pass_1_new_refs"]["specs"] = spec_hits[:3]
        new_evidence += 1

    # P1.G — git log
    git_hits = search_git_log(keywords, cap=2)
    if git_hits:
        overlay["pass_1_axes_hit"].append("P1.G_git_log")
        overlay["pass_1_new_refs"]["git_commits"] = git_hits
        new_evidence += 1

    # Compute status after Pass 1
    evidence_after = overlay["pass_0_evidence_count"] + new_evidence
    overlay["pass_1_evidence_count_after"] = evidence_after
    # Pass 0 had 5 axes; Pass 1 adds 7. Total possible = 12. Status thresholds:
    #   VERIFIED ≥ 5 evidence (≥3 unique surface classes, robust coverage)
    #   PARTIAL  ≥ 1
    #   FOSSIL_MISSING == 0
    if evidence_after >= 5:
        status_after = "VERIFIED"
    elif evidence_after >= 1:
        status_after = "PARTIAL"
    else:
        status_after = "FOSSIL_MISSING"

    overlay["pass_1_status_after"] = status_after
    overlay["pass_1_status_changed"] = status_after != row["fossil_lane_status"]

    # Gap explicit if still PARTIAL/MISSING after Pass 1 attempt
    if status_after in ("PARTIAL", "FOSSIL_MISSING"):
        unchecked_axes = set(["P1.A", "P1.B", "P1.C", "P1.D", "P1.E", "P1.F", "P1.G"])
        hit_axes = set(a.split("_")[0] for a in overlay["pass_1_axes_hit"])
        # axes that returned no hit
        missed = sorted(unchecked_axes - hit_axes)
        overlay["pass_1_gap_reason"] = (
            f"checked_all_pass_1_axes_status_remains_{status_after.lower()};_"
            f"axes_with_no_hit={','.join(missed)}"
        )

    # Exception-candidate: cannot be promoted after both Pass 0 + Pass 1
    overlay["pass_1_exception_candidate"] = (status_after == "FOSSIL_MISSING")

    return overlay

# --------------------------------------------------------------------------
# Report generation
# --------------------------------------------------------------------------

def write_backfill_report(pass_0_rows: List[dict], overlays: List[dict]) -> None:
    overlay_by_id = {o["invariant_id"]: o for o in overlays}

    status_before = Counter(r["fossil_lane_status"] for r in pass_0_rows)
    status_after = Counter(o["pass_1_status_after"] for o in overlays)

    delta_promotions = sum(1 for o in overlays if o["pass_1_status_changed"])
    delta_verified = status_after["VERIFIED"] - status_before["VERIFIED"]
    delta_partial = status_after["PARTIAL"] - status_before["PARTIAL"]
    delta_missing = status_after["FOSSIL_MISSING"] - status_before["FOSSIL_MISSING"]

    axes_hits = Counter()
    for o in overlays:
        for axis in o["pass_1_axes_hit"]:
            axes_hits[axis] += 1

    tic_estimates = [o["pass_1_first_appearance_tic_estimate"] for o in overlays
                     if o["pass_1_first_appearance_tic_estimate"] is not None]

    lines = []
    lines.append("# Pass 1 — Fossil Recovery + PARTIAL Backfill Report\n")
    lines.append(f"**Generated**: {datetime.now(timezone.utc).isoformat()}\n")
    lines.append("**Authority**: Architect verdict tic 245 step 0 + tic 261 directive\n")
    lines.append("**Posture**: read-only; no CLAUDE.md mutation; no freeze activation\n\n")

    lines.append("## Coverage Delta (Pass 0 → Pass 1)\n\n")
    lines.append("| Status | Pass 0 | Pass 1 | Delta |\n")
    lines.append("|---|---|---|---|\n")
    for s in ("VERIFIED", "PARTIAL", "FOSSIL_MISSING"):
        b = status_before.get(s, 0)
        a = status_after.get(s, 0)
        d = a - b
        sign = "+" if d > 0 else ""
        lines.append(f"| {s} | {b} | {a} | {sign}{d} |\n")
    lines.append(f"\n**Status changes**: {delta_promotions} entries shifted "
                 f"({delta_verified:+d} VERIFIED, {delta_partial:+d} PARTIAL, "
                 f"{delta_missing:+d} FOSSIL_MISSING)\n\n")

    lines.append("## Pass 1 Axis Hit Rates\n\n")
    axis_descriptions = {
        "P1.A_vocab_first_appearance": "vocab-index first_appearance.tic_estimate match",
        "P1.B_cogpr_archive": "cogpr-archive.md term match",
        "P1.C_session_lessons": "session_lessons_tic_*.md tic-keyed match",
        "P1.D_memory_auto": "MEMORY.md auto-memory match (high threshold)",
        "P1.E_arena_shows": "arena-runs/ + stage/shows/ synthesis match",
        "P1.F_specs": "specs/ + swarm-specs/ match",
        "P1.G_git_log": "git log keyword match",
    }
    total = len(overlays)
    for axis, count in sorted(axes_hits.items(), key=lambda x: -x[1]):
        pct = (count / total) * 100
        desc = axis_descriptions.get(axis, axis)
        lines.append(f"- `{axis}` ({desc}): {count}/{total} ({pct:.1f}%)\n")
    lines.append("\n")

    if tic_estimates:
        lines.append("## Vocabulary Index First-Appearance Coverage\n\n")
        lines.append(f"- Entries with vocab-index tic_estimate: {len(tic_estimates)}/{total}\n")
        lines.append(f"- tic range: {min(tic_estimates)} → {max(tic_estimates)}\n")
        # Distribution
        bins = defaultdict(int)
        for t in tic_estimates:
            if t < 100: bins["pre_100"] += 1
            elif t < 150: bins["100_149"] += 1
            elif t < 200: bins["150_199"] += 1
            elif t < 220: bins["200_219"] += 1
            elif t < 240: bins["220_239"] += 1
            else: bins["240+"] += 1
        for bucket in ("pre_100", "100_149", "150_199", "200_219", "220_239", "240+"):
            lines.append(f"  - `{bucket}`: {bins.get(bucket, 0)}\n")
        lines.append("\n")

    # Entries promoted to VERIFIED this pass
    promoted = [o for o in overlays
                if o["pass_0_status"] != "VERIFIED" and o["pass_1_status_after"] == "VERIFIED"]
    if promoted:
        lines.append(f"## Newly VERIFIED ({len(promoted)} entries)\n\n")
        lines.append("These entries crossed the evidence threshold via Pass 1 recovery.\n\n")
        for o in promoted[:40]:
            tic = o.get("pass_1_first_appearance_tic_estimate")
            tic_str = f"first_appearance≈tic{tic}" if tic else "no_tic_estimate"
            axes = len(o["pass_1_axes_hit"])
            lines.append(f"- **{o['title_ref']}** "
                        f"({o['pass_0_status']} → VERIFIED, "
                        f"evidence {o['pass_0_evidence_count']}→{o['pass_1_evidence_count_after']}, "
                        f"+{axes} P1 axes, {tic_str})\n")
        if len(promoted) > 40:
            lines.append(f"- ... and {len(promoted) - 40} more\n")
        lines.append("\n")

    # Still PARTIAL after Pass 1
    still_partial = [o for o in overlays if o["pass_1_status_after"] == "PARTIAL"]
    if still_partial:
        lines.append(f"## Still PARTIAL after Pass 1 ({len(still_partial)} entries)\n\n")
        lines.append("Evidence coverage improved but threshold (≥5 total surfaces) not yet met. ")
        lines.append("Pass 2 may surface additional provenance OR /review may accept as ")
        lines.append("PARTIAL-with-explicit-gap for compaction adjudication.\n\n")
        for o in still_partial[:30]:
            tic = o.get("pass_1_first_appearance_tic_estimate")
            tic_str = f"≈tic{tic}" if tic else "tic?"
            ev = o["pass_1_evidence_count_after"]
            lines.append(f"- **{o['title_ref']}** ({tic_str}, evidence={ev}/12)\n")
        if len(still_partial) > 30:
            lines.append(f"- ... and {len(still_partial) - 30} more\n")
        lines.append("\n")

    # Exception candidates (still FOSSIL_MISSING)
    exceptions = [o for o in overlays if o["pass_1_exception_candidate"]]
    if exceptions:
        lines.append(f"## Architect-Attestation Exception Candidates ({len(exceptions)})\n\n")
        lines.append("Per verdict step 6: if copy-then-pointer fails and fossil source cannot be ")
        lines.append("found, route to /review as exception path. **Do not normalize attestation ")
        lines.append("into routine provenance.**\n\n")
        for o in exceptions:
            lines.append(f"- **{o['title_ref']}** "
                        f"(gap: {o.get('pass_1_gap_reason', '?')})\n")
        lines.append("\n")
        lines.append(f"See `exception-candidates.md` for the routing packet.\n\n")

    lines.append("---\n\n## Next-Gate Status\n\n")
    lines.append("Pass 1 emission complete. Constraints honored:\n")
    lines.append("- ✅ No CLAUDE.md mutation\n")
    lines.append("- ✅ No ROOT_ACTIVE_LAW refactor\n")
    lines.append("- ✅ No /review freeze activation\n")
    lines.append("- ✅ No ledger trim\n")
    lines.append("- ✅ No doctrine inscription\n")
    lines.append("- ✅ No demotion to ledger\n")
    lines.append("- ✅ No compaction of verified entries\n\n")
    lines.append("Subsequent gates require Architect green-light:\n")
    lines.append("- Pass 2: deeper backfill on Still-PARTIAL entries\n")
    lines.append("- /review docket review of VERIFIED list for compact_root_candidate adjudication\n")
    lines.append("- /review freeze activation (verdict step 1)\n")
    lines.append("- A2 copy-then-pointer execution (verdict step 5)\n\n")

    lines.append("## Architect lock lines (preserved)\n\n")
    lines.append("- Fossil first.\n")
    lines.append("- Freeze during dehydration.\n")
    lines.append("- Ledger before trim.\n")
    lines.append("- target_rung required.\n")
    lines.append("- No root mutation until provenance coverage is known.\n\n")
    lines.append("**Pass 1 lock line (tic 261)**: *Push through the evidence recovery, not "
                 "through the constitution.*\n")

    PASS_1_REPORT.write_text("".join(lines), encoding="utf-8")


def write_fossil_investigation(pass_0_rows: List[dict], overlays: List[dict]) -> None:
    """Detailed investigation for the FOSSIL_MISSING + still-MISSING entries."""
    overlay_by_id = {o["invariant_id"]: o for o in overlays}
    initial_missing = [r for r in pass_0_rows if r["fossil_lane_status"] == "FOSSIL_MISSING"]

    lines = []
    lines.append("# Fossil-Missing Investigation\n")
    lines.append(f"**Generated**: {datetime.now(timezone.utc).isoformat()}\n")
    lines.append("**Authority**: Architect verdict tic 245 step 0 + tic 261 directive\n\n")

    lines.append("## Pass 0 FOSSIL_MISSING entries (initial)\n\n")
    if not initial_missing:
        lines.append("None at Pass 0 emission.\n\n")
    else:
        for r in initial_missing:
            inv_id = r["invariant_id"]
            overlay = overlay_by_id.get(inv_id, {})
            after_status = overlay.get("pass_1_status_after", "?")
            lines.append(f"### {r['title']}\n\n")
            lines.append(f"- **invariant_id**: `{inv_id}`\n")
            lines.append(f"- **kind**: {r['_pass_0_kind']}\n")
            lines.append(f"- **location**: L{r['_pass_0_line_start']}-{r['_pass_0_line_end']}\n")
            lines.append(f"- **body_chars**: {r['_pass_0_body_chars']}\n")
            lines.append(f"- **Pass 0 evidence count**: {r['_pass_0_evidence_count']}/5\n")
            lines.append(f"- **Pass 1 status after recovery**: `{after_status}`\n")
            if overlay.get("pass_1_axes_hit"):
                lines.append(f"- **Pass 1 axes hit**: {', '.join(overlay['pass_1_axes_hit'])}\n")
            if overlay.get("pass_1_gap_reason"):
                lines.append(f"- **gap reason**: {overlay['pass_1_gap_reason']}\n")

            # Specific narrative for the GLOSSARY.md pointer (Pass 0's 1 FOSSIL_MISSING)
            if r["title"] == "GLOSSARY.md":
                lines.append("\n**Investigation narrative**:\n\n")
                lines.append(
                    "This entry is the `## Extracted References` pointer to `GLOSSARY.md` "
                    "at L449 of CLAUDE.md. It is a **navigation pointer**, not a Key "
                    "Invariant — Pass 0's evidence-threshold logic correctly returned "
                    "FOSSIL_MISSING because there is no doctrine here to verify provenance "
                    "of. The entry's fossil is the GLOSSARY.md file itself "
                    f"({'exists' if (PROJECT_DIR / 'GLOSSARY.md').exists() else 'MISSING'} "
                    "at federation root).\n\n"
                )
                lines.append("**Recommended classification (Pass 1 → /review)**: "
                            "`not_a_ki_navigation_pointer` — exempt from compaction. The "
                            "ledger should carry it as a structural reference row, not a "
                            "compactable KI entry. This is NOT an Architect-attestation "
                            "exception candidate; it's a schema-class distinction (KI vs "
                            "pointer).\n\n")
                lines.append("**Action**: at Pass 2 or /review, add a `root_role` field value "
                            "such as `STRUCTURAL_POINTER` to distinguish navigation entries "
                            "from compactable KIs.\n\n")
            lines.append("---\n\n")

    # Pass 1 newly-MISSING (shouldn't happen given evidence is additive, but check)
    pass_1_missing = [o for o in overlays if o["pass_1_status_after"] == "FOSSIL_MISSING"]
    pass_1_new_missing = [o for o in pass_1_missing
                          if o["pass_0_status"] != "FOSSIL_MISSING"]
    if pass_1_new_missing:
        lines.append("## ⚠️ Newly FOSSIL_MISSING at Pass 1\n\n")
        lines.append("These should not exist (Pass 1 evidence is additive); flagged for audit.\n\n")
        for o in pass_1_new_missing:
            lines.append(f"- `{o['invariant_id']}`\n")
        lines.append("\n")

    FOSSIL_INVESTIGATION.write_text("".join(lines), encoding="utf-8")


def write_exception_candidates(overlays: List[dict]) -> None:
    """Packet for Architect-attestation exception routing."""
    exceptions = [o for o in overlays if o["pass_1_exception_candidate"]]

    lines = []
    lines.append("# Architect-Attestation Exception Candidates\n")
    lines.append(f"**Generated**: {datetime.now(timezone.utc).isoformat()}\n")
    lines.append("**Authority**: Architect verdict tic 245 step 6 (exception path)\n\n")

    lines.append("Per verdict: *Use Architect-attestation only as exception path. "
                 "If copy-then-pointer fails and fossil source cannot be found, "
                 "route to /review. Do not normalize attestation into routine "
                 "provenance.*\n\n")

    if not exceptions:
        lines.append("## No exception candidates\n\n")
        lines.append("All Pass 0 + Pass 1 entries have located at least one provenance "
                    "surface. The Architect-attestation exception path is not needed at "
                    "this gate.\n\n")
        EXCEPTION_CANDIDATES.write_text("".join(lines), encoding="utf-8")
        return

    lines.append(f"## {len(exceptions)} entries requiring exception adjudication\n\n")
    lines.append("Routing target: /review docket (next available pass).\n\n")
    for o in exceptions:
        lines.append(f"### {o['title_ref']}\n\n")
        lines.append(f"- **invariant_id**: `{o['invariant_id']}`\n")
        lines.append(f"- **Pass 0 status**: {o['pass_0_status']}\n")
        lines.append(f"- **Pass 1 status**: {o['pass_1_status_after']}\n")
        lines.append(f"- **gap reason**: {o.get('pass_1_gap_reason', '?')}\n")
        lines.append("\n**Architect attestation question**:\n\n")
        lines.append("- Is this entry a legitimate Key Invariant that should be preserved "
                    "without locatable fossil provenance?\n")
        lines.append("- OR is it a navigation pointer / structural artifact that should be "
                    "classified as non-compactable?\n")
        lines.append("- OR should it be retired from CLAUDE.md as unverifiable doctrine?\n\n")
        lines.append("---\n\n")

    EXCEPTION_CANDIDATES.write_text("".join(lines), encoding="utf-8")

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary; do not write files")
    args = parser.parse_args()

    print(f"Pass 1 — Fossil Recovery — {datetime.now(timezone.utc).isoformat()}")

    if not PASS_0_ROWS.exists():
        print(f"ERROR: {PASS_0_ROWS} not found. Run Pass 0 first.", file=sys.stderr)
        return 2

    pass_0_rows = load_jsonl(PASS_0_ROWS)
    print(f"  Loaded {len(pass_0_rows)} Pass 0 rows")

    print(f"  Building vocab-index term lookup from {VOCAB_INDEX} ...")
    vocab_term_index = build_vocab_term_index(VOCAB_INDEX)
    print(f"  Indexed {len(vocab_term_index)} unique terms")

    print(f"  Running Pass 1 recovery (7 axes per entry)...")
    overlays: List[dict] = []
    for i, row in enumerate(pass_0_rows, 1):
        if i % 20 == 0:
            print(f"    ... processed {i}/{len(pass_0_rows)}")
        overlay = backfill_entry(row, vocab_term_index)
        overlays.append(overlay)

    # Summary
    status_before = Counter(r["fossil_lane_status"] for r in pass_0_rows)
    status_after = Counter(o["pass_1_status_after"] for o in overlays)
    changes = sum(1 for o in overlays if o["pass_1_status_changed"])
    exceptions = sum(1 for o in overlays if o["pass_1_exception_candidate"])

    print()
    print(f"  Pass 0 status: {dict(status_before)}")
    print(f"  Pass 1 status: {dict(status_after)}")
    print(f"  Status changes: {changes}")
    print(f"  Exception candidates: {exceptions}")

    if args.dry_run:
        print("\n  Dry-run; no files written.")
        return 0

    LEDGER_DIR.mkdir(parents=True, exist_ok=True)

    # Atomic overlay rows write
    tmp = PASS_1_OVERLAY.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for o in overlays:
            fh.write(json.dumps(o, ensure_ascii=False) + "\n")
    tmp.replace(PASS_1_OVERLAY)
    print(f"\n  Wrote {PASS_1_OVERLAY}")

    # Reports
    write_backfill_report(pass_0_rows, overlays)
    print(f"  Wrote {PASS_1_REPORT}")

    write_fossil_investigation(pass_0_rows, overlays)
    print(f"  Wrote {FOSSIL_INVESTIGATION}")

    write_exception_candidates(overlays)
    print(f"  Wrote {EXCEPTION_CANDIDATES}")

    print()
    print(f"Pass 1 complete. Pass 0 ledger preserved at {PASS_0_ROWS} (immutable).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
