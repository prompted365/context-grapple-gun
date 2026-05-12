#!/usr/bin/env python3
"""
Pass 0 — Fossil Lane Verification for canonical/CLAUDE.md

Source authority: audit-logs/governance/constitutional-dehydration-architect-verdict-tic245.md
Verdict step 0: "Every pre-Compact-KI root entry must get a verified fossil lane."

Read-only. Walks canonical/CLAUDE.md, enumerates KI entries (## sections + bulleted
KIs under ## Key Invariants), attempts to locate fossil sources from:
  - inline cpr_*_tic* references in entry body
  - audit-logs/cprs/queue.jsonl (CogPR provenance)
  - audit-logs/governance/*.md (packet surfaces)
  - audit-logs/tmux-dumps/vocabulary-index.jsonl (16,440-row provenance trail)
  - MEMORY.md cross-references
  - "Validated:" / "Validated at tic N" clauses (inline evidence anchors)

Emits:
  - audit-logs/governance/constitution-ledger/pass-0-rows.jsonl (one row per entry)
  - audit-logs/governance/constitution-ledger/pass-0-report.md (summary)

DOES NOT mutate canonical/CLAUDE.md (Architect verdict step 1: no root mutation until
provenance coverage is known + freeze during dehydration).

Authored tic 261 under ENG/DIRECT, Architect-approved Pass 0 scaffold (no freeze flag).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[4]  # canonical/
CLAUDE_MD = PROJECT_DIR / "CLAUDE.md"
QUEUE_PATH = PROJECT_DIR / "audit-logs" / "cprs" / "queue.jsonl"
GOVERNANCE_DIR = PROJECT_DIR / "audit-logs" / "governance"
VOCAB_INDEX = PROJECT_DIR / "audit-logs" / "tmux-dumps" / "vocabulary-index.jsonl"
LEDGER_DIR = PROJECT_DIR / "audit-logs" / "governance" / "constitution-ledger"

ROWS_OUT = LEDGER_DIR / "pass-0-rows.jsonl"
REPORT_OUT = LEDGER_DIR / "pass-0-report.md"

# --------------------------------------------------------------------------
# Parsing — extract KI entries from CLAUDE.md
# --------------------------------------------------------------------------

CPR_REF_RE = re.compile(r"(cpr_[a-z0-9_]+_tic\d+|CogPR-\d+)")
TIC_REF_RE = re.compile(r"tic[\s-]*(\d{1,4})", re.IGNORECASE)
VALIDATED_RE = re.compile(r"\(?\s*[Vv]alidated[:\s][^)]*?(?:tic\s*\d+|n[\s=]*\d+|cross-tic|same-tic)[^)]*\)?")
LOCK_LINE_RE = re.compile(r"\*?Lock\s*line\*?:\s*\*?(.+?)\*?\.?\s*$", re.MULTILINE | re.IGNORECASE)
BOLD_LEAD_RE = re.compile(r"^-\s+\*\*([^*]+)\*\*\s*(?:—|--|-)?\s*(.*)$")


def slugify(s: str, maxlen: int = 80) -> str:
    """Slugify a title for invariant_id when no CPR id is present."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return f"ki_{s[:maxlen]}"


def parse_claude_md(path: Path) -> List[dict]:
    """Extract KI entries.

    Two entry shapes:
      1. ## Section Heading — entire section body
      2. - **Bold Lead Phrase** — under ## Key Invariants or similar lists
    """
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(2)

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    entries: List[dict] = []

    current_section = None
    current_section_start = None
    current_section_lines: List[str] = []
    inside_ki_listing = False

    def flush_section():
        nonlocal current_section, current_section_start, current_section_lines
        if current_section and current_section_start is not None:
            body = "\n".join(current_section_lines).strip()
            # If the section contains bulleted KIs (under ## Key Invariants etc),
            # emit them individually; otherwise emit the section as one entry.
            bullet_kis = extract_bullet_kis(
                current_section_lines, current_section_start, current_section
            )
            if bullet_kis:
                # The section itself becomes a synthesis-only entry IF it has narrative
                # before bullets; otherwise we skip the section-level entry.
                pre_bullet_text = []
                for ln in current_section_lines:
                    if BOLD_LEAD_RE.match(ln):
                        break
                    pre_bullet_text.append(ln)
                pre_body = "\n".join(pre_bullet_text).strip()
                if pre_body and len(pre_body) > 80:
                    entries.append({
                        "kind": "section",
                        "title": current_section,
                        "parent_section": None,
                        "line_start": current_section_start,
                        "line_end": current_section_start + len(pre_bullet_text),
                        "body": pre_body,
                    })
                entries.extend(bullet_kis)
            else:
                entries.append({
                    "kind": "section",
                    "title": current_section,
                    "parent_section": None,
                    "line_start": current_section_start,
                    "line_end": current_section_start + len(current_section_lines),
                    "body": body,
                })
        current_section = None
        current_section_start = None
        current_section_lines = []

    for i, line in enumerate(lines, 1):
        if line.startswith("## "):
            flush_section()
            current_section = line[3:].strip()
            current_section_start = i
            current_section_lines = []
        elif current_section is not None:
            current_section_lines.append(line)

    flush_section()
    return entries


def extract_bullet_kis(section_lines: List[str], section_start: int,
                      parent_section: Optional[str] = None) -> List[dict]:
    """Extract bulleted KIs from a section. Multi-line bullets (continuation indents) merge.

    parent_section is threaded through so downstream classifiers can detect
    STRUCTURAL_POINTER entries by section context (e.g., bullets under
    ## Extracted References are navigation pointers, not KIs).
    """
    kis: List[dict] = []
    current_ki: Optional[dict] = None
    for offset, line in enumerate(section_lines):
        m = BOLD_LEAD_RE.match(line)
        if m:
            if current_ki is not None:
                kis.append(current_ki)
            title = m.group(1).strip()
            first_body = m.group(2).strip()
            current_ki = {
                "kind": "bullet",
                "title": title,
                "parent_section": parent_section,
                "line_start": section_start + offset + 1,
                "line_end": section_start + offset + 1,
                "body": first_body,
                "_continuation": [],
            }
        elif current_ki is not None:
            # Continuation: indented line or non-blank non-list line
            stripped = line.strip()
            if not stripped:
                # blank line — bullet body may continue or end; we accept the next
                # non-blank line as either continuation or new bullet
                current_ki["_continuation"].append(line)
            elif line.startswith("  ") or line.startswith("\t"):
                current_ki["_continuation"].append(line)
                current_ki["line_end"] = section_start + offset + 1
            elif line.startswith("- ") and not BOLD_LEAD_RE.match(line):
                # sub-bullet inside the KI body
                current_ki["_continuation"].append(line)
                current_ki["line_end"] = section_start + offset + 1
            else:
                # non-bullet, non-indent line ends the bullet
                kis.append(current_ki)
                current_ki = None
    if current_ki is not None:
        kis.append(current_ki)

    # Merge continuation
    for ki in kis:
        cont = ki.pop("_continuation", [])
        if cont:
            ki["body"] = ki["body"] + "\n" + "\n".join(cont).strip()
    return kis

# --------------------------------------------------------------------------
# Fossil source lookups
# --------------------------------------------------------------------------

def load_queue_index(path: Path) -> Dict[str, dict]:
    """Build {cpr_id: latest_entry} index from queue.jsonl."""
    if not path.exists():
        return {}
    out: Dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            cid = d.get("id", "")
            if cid:
                out[cid] = d
        except json.JSONDecodeError:
            continue
    return out


def find_inline_cpr_refs(body: str) -> List[str]:
    """Find cpr_*_tic* and CogPR-N references in entry body."""
    found = CPR_REF_RE.findall(body)
    return list(dict.fromkeys(found))  # dedup, preserve order


def find_validated_clauses(body: str) -> List[str]:
    """Extract '(Validated: ...)' clauses as evidence anchors."""
    return [m.group(0) for m in VALIDATED_RE.finditer(body)]


def find_promoted_tics(body: str, cpr_index: Dict[str, dict], cpr_refs: List[str]) -> List[int]:
    """Find tic markers in body + queue entries."""
    tics: List[int] = []
    # Inline tics
    for m in TIC_REF_RE.finditer(body):
        try:
            tics.append(int(m.group(1)))
        except ValueError:
            continue
    # Queue entries
    for ref in cpr_refs:
        entry = cpr_index.get(ref)
        if entry:
            for k in ("promoted_by_tic", "review_tic", "tic"):
                v = entry.get(k)
                if isinstance(v, int):
                    tics.append(v)
    return sorted(set(tics))


def find_governance_packets(title: str, body: str, governance_dir: Path) -> List[str]:
    """Heuristic match — files in governance/ whose name shares 2+ significant words with title."""
    if not governance_dir.exists():
        return []
    title_keywords = significant_keywords(title)
    if not title_keywords:
        return []
    matches: List[str] = []
    for p in governance_dir.rglob("*.md"):
        name = p.stem.lower()
        hits = sum(1 for k in title_keywords if k in name)
        if hits >= 2:
            matches.append(str(p.relative_to(PROJECT_DIR)))
    return matches[:5]  # cap


def significant_keywords(s: str) -> List[str]:
    """Extract significant keywords (>3 chars, not stopwords)."""
    stopwords = {
        "the", "and", "for", "from", "with", "into", "that", "this", "must", "not",
        "are", "was", "were", "but", "have", "has", "had", "any", "all", "one",
        "two", "may", "can", "via", "per", "its", "out", "off", "ing", "tion",
    }
    words = re.findall(r"[a-z][a-z0-9]{3,}", s.lower())
    return [w for w in words if w not in stopwords][:6]


def search_vocab_index(title: str, vocab_path: Path, cap: int = 5) -> List[dict]:
    """Find vocabulary-index entries matching title keywords (lightweight scan)."""
    if not vocab_path.exists():
        return []
    keywords = significant_keywords(title)[:3]
    if not keywords:
        return []
    matches: List[dict] = []
    with vocab_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            # Cheap pre-filter: any keyword present?
            if not any(k in line for k in keywords):
                continue
            try:
                d = json.loads(line)
                term = d.get("term", "")
                if any(k in term for k in keywords):
                    matches.append({
                        "term": term,
                        "occurrences": d.get("total_occurrences", 0),
                        "first_tic_estimate": d.get("first_appearance", {}).get("tic_estimate"),
                    })
                    if len(matches) >= cap:
                        break
            except json.JSONDecodeError:
                continue
    return matches

# --------------------------------------------------------------------------
# Classification heuristics
# --------------------------------------------------------------------------

TERRAIN_KEYWORDS = {
    "constitutional_procedure": ["procedure", "inscription", "promotion", "demote", "amend"],
    "capability_surface_contract": ["envelope", "capability", "contract", "schema", "router"],
    "cognitive_economy": ["budget", "context", "cognitive", "token", "model"],
    "identity_and_capability": ["identity", "boundary", "standing", "role", "jurisdiction"],
    "signal_and_manifold": ["signal", "manifold", "siren", "warrant", "dedup"],
    "queue_and_state": ["queue", "state", "stack", "terminal", "valve"],
    "arena_geometry": ["arena", "advocate", "wildcard", "bracket", "vpl", "oavplt", "crx"],
    "inscription_discipline": ["promot", "verify", "fossil", "ledger", "doctrine", "review"],
    "volatility_handling": ["volatil", "vendor", "ttl", "probe", "adapter", "drift"],
    "sentinel_integrity": ["sentinel", "fingerprint", "chain", "ledger", "tamper"],
    "terrain_projection": ["projection", "terrain", "slice", "layer", "rtch"],
    "estate_relations": ["estate", "federation", "rung", "domain", "telos"],
    "publication_governance": ["publication", "citizens", "edition", "broadcast"],
    "persona_and_runtime": ["persona", "runtime", "agent", "harmony", "homeskillet"],
}


def classify_terrain(title: str, body: str) -> str:
    """Heuristic terrain classification. /review will refine."""
    text = (title + " " + body).lower()
    best = ("unclassified", 0)
    for cls, kws in TERRAIN_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in text)
        if score > best[1]:
            best = (cls, score)
    return best[0] if best[1] > 0 else "unclassified"


def classify_era(tics: List[int]) -> str:
    """Group tics into era buckets."""
    if not tics:
        return "pre_cpr_discipline"
    earliest = min(tics)
    if earliest < 100:
        return "pre_cpr_discipline"
    elif earliest < 150:
        return "cpr_era_tic_100_149"
    elif earliest < 200:
        return "cpr_era_tic_150_199"
    elif earliest < 220:
        return "cpr_era_tic_200_219"
    elif earliest < 240:
        return "cpr_era_tic_220_239"
    else:
        return "cpr_era_tic_240_current"


def extract_lock_line(body: str) -> str:
    """Extract explicit 'Lock line:' clause or fall back to last sentence."""
    m = LOCK_LINE_RE.search(body)
    if m:
        return m.group(1).strip()
    return ""


# Sections whose bullets are by-design navigation pointers, not KIs.
STRUCTURAL_POINTER_SECTIONS = {
    "Extracted References",
    "Structure",  # the federation root structure declaration
    "Workspace Default Posture",  # posture tokens (ENG/META, ENG/DIRECT, etc.)
}


def is_structural_pointer(entry: dict) -> Tuple[bool, str]:
    """Detect if entry is a navigation pointer / schema-class artifact rather than a KI.

    Returns (is_pointer, reason). Pass 2 schema refinement (tic 261) per Architect-approved
    disciplined version of Pass 1 counsel framing: stop counting navigation/heading bullets
    as KI candidates.

    Detection criteria (any single criterion suffices):
      1. Bullet under a known structural-pointer section (## Extracted References, etc.)
      2. Bullet body very short (< 80 chars total) — navigation entries lack substantive body
      3. Title is a filename pointer (*.md, *.py, *.json, *.yaml)
      4. Title is a posture/path token (contains `/` with short total length, e.g., ENG/META)
    """
    title = entry["title"]
    kind = entry.get("kind", "")
    body = entry.get("body", "")
    parent = entry.get("parent_section") or ""

    # Criterion 1: section-level structural designation
    if parent in STRUCTURAL_POINTER_SECTIONS:
        return True, f"bullet_under_structural_pointer_section_'{parent}'"

    # Criterion 2: short-body bullets (navigation entries lack substantive doctrine)
    if kind == "bullet" and len(body) < 80:
        return True, f"bullet_body_<80_chars_(actual={len(body)})"

    # Criterion 3: filename pointer titles
    for ext in (".md", ".py", ".json", ".yaml", ".jsonl", ".sh"):
        if title.endswith(ext):
            return True, f"title_filename_pointer_ext={ext}"

    # Criterion 4: posture/path token titles (slash-separated, short)
    if "/" in title and len(title) < 25 and " " not in title.strip():
        return True, "title_posture_or_path_token"

    return False, ""

# --------------------------------------------------------------------------
# Pass 0 row composition
# --------------------------------------------------------------------------

def compose_ledger_row(entry: dict, cpr_index: Dict[str, dict]) -> dict:
    """Build a ledger row for a single CLAUDE.md entry.

    Pass 2 schema refinement (tic 261): detect STRUCTURAL_POINTER entries first.
    These are navigation/header objects, not KIs — they bypass fossil_lane_status
    semantics and route to KEEP_AS_STRUCTURAL_POINTER directly.
    """
    title = entry["title"]
    body = entry["body"]
    kind = entry["kind"]

    # Pass 2: structural-pointer detection (schema-class distinction, not fossil_lane work)
    is_ptr, ptr_reason = is_structural_pointer(entry)
    if is_ptr:
        return {
            "invariant_id": slugify(title),
            "title": title,
            "compact_lock_line": "",
            "terrain_class": "structural_pointer",
            "lane_tags": ["structural_pointer"],
            "era": "n/a_structural",
            "target_rung": "federation",
            "root_role": "STRUCTURAL_POINTER",
            "source_cpr": [],
            "promoted_tic": None,
            "source_surface": [],
            "review_surface": None,
            "evidence_anchor": "",
            "fossil_lane_status": "STRUCTURAL_POINTER_EXEMPT",
            "compact_root_candidate": False,
            "action_recommendation": "KEEP_AS_STRUCTURAL_POINTER",
            "_pass_0_kind": kind,
            "_pass_0_line_start": entry["line_start"],
            "_pass_0_line_end": entry["line_end"],
            "_pass_0_body_chars": len(body),
            "_pass_0_evidence_count": 0,  # N/A for structural pointers
            "_pass_0_tic_refs_found": [],
            "_pass_0_structural_pointer_reason": ptr_reason,
            "_pass_0_parent_section": entry.get("parent_section"),
        }

    cpr_refs = find_inline_cpr_refs(body)
    validated = find_validated_clauses(body)
    tics = find_promoted_tics(body, cpr_index, cpr_refs)
    governance_packets = find_governance_packets(title, body, GOVERNANCE_DIR)
    vocab_hits = search_vocab_index(title, VOCAB_INDEX)

    # invariant_id: prefer first cpr_ref, else slugified title
    if cpr_refs:
        invariant_id = cpr_refs[0] if cpr_refs[0].startswith("cpr_") else slugify(title)
    else:
        invariant_id = slugify(title)

    lock_line = extract_lock_line(body)
    terrain_class = classify_terrain(title, body)
    era = classify_era(tics)
    promoted_tic = min(tics) if tics else None

    # Source surfaces
    source_surface: List[str] = []
    if governance_packets:
        source_surface.extend(governance_packets)
    if vocab_hits:
        source_surface.append(f"vocabulary-index:{len(vocab_hits)}_term_matches")

    # Evidence anchor
    evidence_anchor = validated[0][:240] if validated else ""

    # Fossil status determination
    has_cpr_ref = bool(cpr_refs)
    has_validated_clause = bool(validated)
    has_governance_packet = bool(governance_packets)
    has_queue_match = any(ref in cpr_index for ref in cpr_refs)
    has_vocab_match = bool(vocab_hits)

    evidence_count = sum([
        has_cpr_ref, has_validated_clause, has_governance_packet,
        has_queue_match, has_vocab_match,
    ])

    if evidence_count >= 3:
        fossil_lane_status = "VERIFIED"
    elif evidence_count >= 1:
        fossil_lane_status = "PARTIAL"
    else:
        fossil_lane_status = "FOSSIL_MISSING"

    # Action recommendation (Pass 0 heuristic; /review adjudicates)
    if fossil_lane_status == "FOSSIL_MISSING":
        action = "FOSSIL_INVESTIGATE"
    elif kind == "section" and len(body) > 800:
        # Long sections likely candidates for DEMOTE_TO_LEDGER per A2 copy-then-pointer
        action = "DEMOTE_TO_LEDGER"
    else:
        action = "NEEDS_REVIEW"

    return {
        "invariant_id": invariant_id,
        "title": title,
        "compact_lock_line": lock_line,
        "terrain_class": terrain_class,
        "lane_tags": [],  # Pass 0 default; /review fills
        "era": era,
        "target_rung": "federation",
        "root_role": "ROOT_CANDIDATE",  # Pass 0 default
        "source_cpr": cpr_refs,
        "promoted_tic": promoted_tic,
        "source_surface": source_surface,
        "review_surface": None,  # Pass 0 doesn't locate /review packets per-KI
        "evidence_anchor": evidence_anchor,
        "fossil_lane_status": fossil_lane_status,
        "compact_root_candidate": False,  # Pass 0 default
        "action_recommendation": action,
        # Pass 0 audit metadata
        "_pass_0_kind": kind,
        "_pass_0_line_start": entry["line_start"],
        "_pass_0_line_end": entry["line_end"],
        "_pass_0_body_chars": len(body),
        "_pass_0_evidence_count": evidence_count,
        "_pass_0_tic_refs_found": tics,
    }

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print summary only; do not write files")
    args = parser.parse_args()

    print(f"Pass 0 Fossil Verification — {datetime.now(timezone.utc).isoformat()}")
    print(f"  CLAUDE.md: {CLAUDE_MD}")
    print(f"  Queue: {QUEUE_PATH}")
    print(f"  Governance dir: {GOVERNANCE_DIR}")
    print(f"  Vocab index: {VOCAB_INDEX}")

    entries = parse_claude_md(CLAUDE_MD)
    print(f"  Extracted {len(entries)} entries")

    cpr_index = load_queue_index(QUEUE_PATH)
    print(f"  Loaded {len(cpr_index)} unique CPR ids from queue")

    rows = [compose_ledger_row(e, cpr_index) for e in entries]

    # Summary stats
    status_counts = Counter(r["fossil_lane_status"] for r in rows)
    action_counts = Counter(r["action_recommendation"] for r in rows)
    terrain_counts = Counter(r["terrain_class"] for r in rows)
    era_counts = Counter(r["era"] for r in rows)
    kind_counts = Counter(r["_pass_0_kind"] for r in rows)

    print()
    print(f"  Entry kind: {dict(kind_counts)}")
    print(f"  Fossil status: {dict(status_counts)}")
    print(f"  Action recommendation: {dict(action_counts)}")
    print(f"  Terrain class distribution: {dict(terrain_counts.most_common(10))}")
    print(f"  Era distribution: {dict(era_counts)}")

    if args.dry_run:
        print("\nDry-run; no files written.")
        return 0

    LEDGER_DIR.mkdir(parents=True, exist_ok=True)

    # Atomic write of rows
    tmp_rows = ROWS_OUT.with_suffix(".jsonl.tmp")
    with tmp_rows.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp_rows.replace(ROWS_OUT)
    print(f"\n  Wrote {ROWS_OUT}")

    # Report
    report_lines = []
    report_lines.append("# Pass 0 — Fossil Lane Verification Report\n")
    report_lines.append(f"**Generated**: {datetime.now(timezone.utc).isoformat()}\n")
    report_lines.append(f"**Source corpus**: `CLAUDE.md` ({CLAUDE_MD.stat().st_size:,} bytes)\n")
    report_lines.append(f"**Authority**: Architect verdict tic 245 step 0\n")
    report_lines.append(f"**Posture**: read-only emission; no mutation to CLAUDE.md\n\n")
    report_lines.append("> **Calibration warning (persistent)**: `fossil_lane_status` values\n")
    report_lines.append("> reflect **lexical surface evidence**, not semantic verification.\n")
    report_lines.append("> An entry classified VERIFIED has provenance keywords located across\n")
    report_lines.append("> N surfaces; this does NOT guarantee that each surface semantically\n")
    report_lines.append("> attests to the KI's authoring lineage. Semantic adjudication\n")
    report_lines.append("> (which VERIFIED entries are true ROOT_ACTIVE_LAW vs which are\n")
    report_lines.append("> high-keyword-frequency lexical noise) is `/review` territory at\n")
    report_lines.append("> the next available adjudication boundary (currently /review tic 264).\n\n")

    report_lines.append("---\n\n## Summary\n\n")
    report_lines.append(f"- **Total entries enumerated**: {len(rows)}\n")
    report_lines.append(f"- **By kind**: {dict(kind_counts)}\n")
    report_lines.append(f"- **By fossil status**: {dict(status_counts)}\n")
    report_lines.append(f"- **By action recommendation**: {dict(action_counts)}\n\n")

    report_lines.append("## Fossil Lane Status Distribution\n\n")
    for status, count in status_counts.most_common():
        pct = (count / len(rows)) * 100
        report_lines.append(f"- `{status}`: {count} ({pct:.1f}%)\n")
    report_lines.append("\n")

    report_lines.append("## Action Recommendation Distribution\n\n")
    for action, count in action_counts.most_common():
        pct = (count / len(rows)) * 100
        report_lines.append(f"- `{action}`: {count} ({pct:.1f}%)\n")
    report_lines.append("\n")

    report_lines.append("## Terrain Class Distribution\n\n")
    for cls, count in terrain_counts.most_common():
        report_lines.append(f"- `{cls}`: {count}\n")
    report_lines.append("\n")

    report_lines.append("## Era Distribution\n\n")
    for era, count in sorted(era_counts.items()):
        report_lines.append(f"- `{era}`: {count}\n")
    report_lines.append("\n")

    # FOSSIL_MISSING list (these block compaction per verdict step 0)
    missing = [r for r in rows if r["fossil_lane_status"] == "FOSSIL_MISSING"]
    if missing:
        report_lines.append(f"## FOSSIL_MISSING entries ({len(missing)})\n\n")
        report_lines.append("Per Architect verdict step 0: entries without verified provenance ")
        report_lines.append("**do not compact**. These require investigation or architect-attestation ")
        report_lines.append("exception path (verdict step 6) before subsequent passes.\n\n")
        for r in missing:
            report_lines.append(f"- **{r['title']}** (L{r['_pass_0_line_start']}-{r['_pass_0_line_end']}, ")
            report_lines.append(f"{r['_pass_0_kind']}, evidence_count={r['_pass_0_evidence_count']})\n")
        report_lines.append("\n")

    # PARTIAL list (need more provenance before compaction)
    partial = [r for r in rows if r["fossil_lane_status"] == "PARTIAL"]
    if partial:
        report_lines.append(f"## PARTIAL entries ({len(partial)})\n\n")
        report_lines.append("Some fossil evidence located but coverage incomplete. ")
        report_lines.append("Pass 1+ should backfill before compaction.\n\n")
        for r in partial[:25]:  # cap display
            tic_str = f"tic={r['promoted_tic']}" if r['promoted_tic'] else "tic=?"
            report_lines.append(f"- **{r['title']}** ({tic_str}, evidence={r['_pass_0_evidence_count']}/5, ")
            report_lines.append(f"surfaces={len(r['source_surface'])})\n")
        if len(partial) > 25:
            report_lines.append(f"- ... and {len(partial) - 25} more\n")
        report_lines.append("\n")

    # VERIFIED list (compact-eligible per Pass 0)
    verified = [r for r in rows if r["fossil_lane_status"] == "VERIFIED"]
    if verified:
        report_lines.append(f"## VERIFIED entries ({len(verified)})\n\n")
        report_lines.append("Fossil lane confirmed across 3+ provenance surfaces. ")
        report_lines.append("Eligible for compaction adjudication at Pass 1+.\n\n")
        for r in verified[:25]:
            tic_str = f"tic={r['promoted_tic']}" if r['promoted_tic'] else "tic=?"
            report_lines.append(f"- **{r['title']}** ({tic_str}, evidence={r['_pass_0_evidence_count']}/5)\n")
        if len(verified) > 25:
            report_lines.append(f"- ... and {len(verified) - 25} more\n")
        report_lines.append("\n")

    # STRUCTURAL_POINTER list (Pass 2 schema refinement, tic 261)
    structural = [r for r in rows if r["fossil_lane_status"] == "STRUCTURAL_POINTER_EXEMPT"]
    if structural:
        report_lines.append(f"## STRUCTURAL_POINTER entries ({len(structural)})\n\n")
        report_lines.append("Navigation/header/sub-bullet/formatting objects — NOT KIs. ")
        report_lines.append("`fossil_lane_status` does not apply. These entries stay in ")
        report_lines.append("CLAUDE.md as structural references; no compaction or demotion.\n\n")
        for r in structural[:25]:
            reason = r.get("_pass_0_structural_pointer_reason", "")
            parent = r.get("_pass_0_parent_section") or "(top-level)"
            report_lines.append(f"- **{r['title']}** "
                               f"(parent=`{parent}`, reason=`{reason}`)\n")
        if len(structural) > 25:
            report_lines.append(f"- ... and {len(structural) - 25} more\n")
        report_lines.append("\n")

    report_lines.append("---\n\n## Next Steps (Architect verdict referenced)\n\n")
    report_lines.append("Pass 0 emission is complete. Subsequent passes (under Architect green-light):\n\n")
    report_lines.append("1. **Pass 1**: Investigate FOSSIL_MISSING entries — locate sources or route to ")
    report_lines.append("/review for Architect-attestation exception path.\n")
    report_lines.append("2. **Pass 2**: Backfill PARTIAL entries — surface additional provenance ")
    report_lines.append("evidence; promote PARTIAL → VERIFIED where supportable.\n")
    report_lines.append("3. **Pass 3**: /review docket adjudicates `compact_root_candidate` and ")
    report_lines.append("`root_role` per VERIFIED entry. Target ROOT_ACTIVE_LAW count: 15-25.\n")
    report_lines.append("4. **Pass 4**: A2 copy-then-pointer execution — full bodies move to ledger; ")
    report_lines.append("root carries lock-line + pointer.\n\n")
    report_lines.append("**Freeze flag**: not activated by this Pass 0 emission. Activation routes ")
    report_lines.append("separately under Architect authorization per verdict step 1.\n\n")

    report_lines.append("## Lock lines (Architect verdict)\n\n")
    report_lines.append("- Fossil first.\n")
    report_lines.append("- Freeze during dehydration.\n")
    report_lines.append("- Ledger before trim.\n")
    report_lines.append("- target_rung required.\n")
    report_lines.append("- No root mutation until provenance coverage is known.\n")

    REPORT_OUT.write_text("".join(report_lines), encoding="utf-8")
    print(f"  Wrote {REPORT_OUT}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
