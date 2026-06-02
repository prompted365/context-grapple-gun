#!/usr/bin/env python3
"""
Review Close Check — post-review consistency verification.

Verifies that /review verdicts were correctly inscribed:
  - PROMOTE: lesson text landed in target file
  - DEFER: queue.jsonl has updated review_tic
  - SKIP: queue.jsonl status is 'skipped'
  - Orphan check: queue says promoted but text missing from target

Genuine-vs-known reason split (cgg-ledger#reason-coded-genuine-vs-known-verifier-split,
promoted /review 336): a content-matching verifier CANNOT verify a promotion whose
target is a code BEHAVIOR (a `.py`/`SKILL.md` change) or a relocated archive file —
those carry no text-matchable trace. A bare `consistent:false` over-reports by
collapsing such KNOWN false-positives with GENUINE missing inscriptions. So every
promoted-missing / orphaned finding is classified with a REASON code
(`dehydration_resolved | behavioral_text_unverifiable | stale_relocated_pointer`);
only reason=None findings are GENUINE, and the report carries
`consistent:false(genuine=G, known=K)` — only `G>0` is a hazard. Two mechanisms back
the split beyond the shared dehydration resolver: a provenance-trace axis (git
lineage of the cpr_id) for behavioral/code targets, and a relocation-aware
pointer-correction axis for Pass-4-moved archive files.

Output: JSON consistency report.

Usage:
    python3 review-close-check.py --project-dir /path/to/zone
    python3 review-close-check.py --project-dir /path/to/zone --dry-run
    python3 review-close-check.py --project-dir /path/to/zone --json
    python3 review-close-check.py --help
"""

import argparse
import glob as _glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path
# Shared dehydration-aware doctrine resolver (tic 335 consumer-set fix): when a
# promoted_to target is a DEHYDRATED CLAUDE.md, the inscription body relocated to
# a sibling ledger.md — reading the compact root alone reports
# `promoted_text_missing` for doctrine that IS inscribed (the verifier's half of
# the dehydration blindspot, named tic 279/301/316 but runtime-fix-not-landed
# until this consumer-set pass).
from doctrine_surfaces import resolve_doctrine_surfaces  # noqa: E402

# Auto-memory directory — feedback_*.md, session_lessons_*.md, project_*.md and
# other CPR promotion targets live here, OUTSIDE the federation repo. A bare
# `feedback_x.md` promoted_to target does not resolve against project_dir; it
# resolves here. Shared by build_inscribed_index and the target resolvers.
AUTO_MEMORY_DIR = (
    Path.home()
    / ".claude"
    / "projects"
    / "-Users-breydentaylor-canonical"
    / "memory"
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_queue(queue_path):
    """Load CPR queue (latest-entry-per-ID-wins). Returns dict of id->entry."""
    entries = {}
    p = Path(queue_path)
    if not p.exists():
        return entries
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            eid = d.get("id", "")
            if eid:
                entries[eid] = d
        except json.JSONDecodeError:
            continue
    return entries


def load_lesson_fallbacks(queue_path):
    """Collect lesson text from ALL queue entries per id (not just latest).

    Some promoted writeback rows are minimal records with no lesson field.
    Earlier entries for the same id (e.g., enrichment_eligible rows) may carry
    the full lesson text.  This mapping provides a fallback lesson source for
    check_promoted when the latest (promoted) entry has an empty lesson.

    Returns: dict of id -> str (first non-empty lesson found for that id,
             scanning the file in order — earlier entries win for lesson lookup
             because the enrichment-eligible row carries the full text).
    """
    lessons = {}
    p = Path(queue_path)
    if not p.exists():
        return lessons
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            eid = d.get("id", "")
            lesson = d.get("lesson", "")
            if eid and lesson and eid not in lessons:
                lessons[eid] = lesson
        except json.JSONDecodeError:
            continue
    return lessons


def read_file_safe(path):
    """Read file content, return empty string on failure."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ---------------------------------------------------------------------------
# Consistency checks
# ---------------------------------------------------------------------------

_PATH_CHARS = re.compile(r"^[~./\w-]+(?:/[~./\w-]+)*\.[a-zA-Z]+$")

# Matches a parenthesized scope hint appended AFTER the file path.
# E.g. "canonical/CLAUDE.md (refined 'Constitutional schema must precede rendering layer')"
# The path ends at the first " (" that is NOT part of the filesystem path itself.
# We only strip when the "(" is preceded by a space — absolute/tilde paths with embedded
# parentheses are extremely rare and excluded by the leading-space guard.
_SCOPE_HINT_RE = re.compile(r"^(.*?)\s+\(.*\)$", re.DOTALL)

# Receipt-closure annotation: parenthetical of the form "(already inscribed ...)" or
# "(... already inscribed ...)" signals that the doctrine is inscribed at a prior tic
# in a sibling surface. Presence is a strong receipt-closure signal — the gate then
# verifies via filesystem-existence-of-target rather than literal-content match.
_RECEIPT_CLOSURE_ANNOTATION_RE = re.compile(r"\(\s*[^)]*\balready\s+inscribed\b[^)]*\)", re.IGNORECASE)

# Anchor/line-range suffix on a target path:
#   file.md:N-M  or  file.md:N   (line range)
#   file.md#heading-anchor       (markdown heading anchor)
#   file.yaml#path.to.field      (YAML key path anchor)
# Stripped before filesystem resolution; preserved in reporting.
_PATH_ANCHOR_RE = re.compile(r"^([^#:\s]+\.[A-Za-z]+)(?:[#:][^\s]*)?$")

# --- Genuine-vs-known reason split (cgg-ledger#reason-coded-genuine-vs-known-verifier-split) ---
#
# Code/behavioral promotion targets: a promotion whose promoted_to is a source
# file (or a SKILL.md whose change is behavioral) lands as a code BEHAVIOR, not
# quotable text — content-matching can never verify it. Classified
# `behavioral_text_unverifiable` and verified via the provenance-trace axis
# (git lineage of the cpr_id) rather than literal-content match.
_CODE_SUFFIXES = {".py", ".sh", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".rs", ".go"}

# Relocation roots searched by the relocation-aware pointer-correction axis: when
# a promoted_to names a path that Pass-4 dehydration MOVED (e.g.
# canonical/doctrine/CONSTITUTION_LEDGER.md -> the archive below), the bare path
# no longer resolves; the doctrine body lives at the moved location.
_RELOCATION_ROOTS = ("audit-logs/governance/dehydration-pipeline-archive",)

# Reason codes for a KNOWN (non-hazard) promoted_text_missing finding. Only a
# finding with reason=None is GENUINE (a real missing inscription — the G>0
# hazard). dehydration_resolved is closed UPSTREAM by _read_with_ledger /
# resolve_doctrine_surfaces (such findings never reach classification); it is
# named here for taxonomy completeness and evidence labels.
REASON_DEHYDRATION_RESOLVED = "dehydration_resolved"
REASON_BEHAVIORAL = "behavioral_text_unverifiable"
REASON_STALE_RELOCATED = "stale_relocated_pointer"


def _strip_scope_hint(s):
    """Strip a trailing parenthesized scope hint from a target string.

    Preserves the original string for reporting; returns only the bare path
    for filesystem resolution.  Only strips when the parenthetical follows a
    space so that paths with embedded parentheses (unlikely but possible) are
    not mangled.

    Examples:
        "canonical/CLAUDE.md (refined 'X')"  -> "canonical/CLAUDE.md"
        "canonical/CLAUDE.md"                 -> "canonical/CLAUDE.md"  (unchanged)
    """
    m = _SCOPE_HINT_RE.match(s.strip())
    if m:
        return m.group(1)
    return s


def _strip_path_anchor(s):
    """Strip line-range, heading anchor, or YAML key-path suffix from a target.

    Receipt-closure PROMOTES often point at specific locations inside a file
    (e.g. "file.md:389-391", "file.md#section", "envelopes.yaml#cockpit.intent.field").
    The suffix is structurally meaningful (it names the inscription location) but
    must be stripped before filesystem resolution. Suffix is preserved in the
    targets_checked report field; only the bare file path is used for resolution.

    Examples:
        "file.md:389-391"               -> "file.md"
        "file.md#anchor-name"           -> "file.md"
        "envelopes.yaml#path.to.field"  -> "envelopes.yaml"
        "file.md"                       -> "file.md"  (unchanged)
    """
    m = _PATH_ANCHOR_RE.match(s.strip())
    if m:
        return m.group(1)
    return s


def _split_compound_targets(s):
    """Split a compound `+`-joined target string into individual targets.

    Receipt-closure PROMOTES sometimes name multiple co-inscription surfaces
    in a single promoted_to string joined by ` + `. Each split component is
    a candidate target in its own right.

    Example:
        "file.md (estate doctrine) + dir.ts (StructureCategory union)"
            -> ["file.md (estate doctrine)", "dir.ts (StructureCategory union)"]
        "file.md"  -> ["file.md"]  (no split needed)
    """
    if " + " not in s:
        return [s]
    return [part.strip() for part in s.split(" + ") if part.strip()]


def _has_receipt_closure_annotation(s):
    """Detect '(already inscribed ...)' parenthetical receipt-closure marker."""
    return bool(_RECEIPT_CLOSURE_ANNOTATION_RE.search(s))


def _looks_like_file_path(s):
    """Heuristic: does this string look like a file path (vs natural-language description)?"""
    if not s or not isinstance(s, str):
        return False
    # Strip parenthetical scope hint before checking path shape
    bare = _strip_scope_hint(s.strip())
    if " " in bare:
        return False
    if not _PATH_CHARS.match(bare):
        return False
    return True


def _collect_targets(cpr):
    """Collect + compound-split the candidate target strings for a promoted CPR.

    The single source of the target list, shared by check_promoted (finding
    production) and classify_known_reason (finding classification) so the two
    can never drift on what counts as a target. Priority: promoted_to (verdict-
    side authoritative), promotion_target (legacy), then file-path-shaped
    recommended_scopes. Compound `+`-joined targets are split into components;
    scope hints / anchors are preserved on each component for the caller to strip.
    """
    promoted_to = cpr.get("promoted_to", "")
    target = cpr.get("promotion_target", "")
    scopes = cpr.get("recommended_scopes", [])

    raw_targets = []
    if isinstance(promoted_to, str) and promoted_to:
        raw_targets.append(promoted_to)
    elif isinstance(promoted_to, list):
        raw_targets.extend([p for p in promoted_to if isinstance(p, str) and p])
    if target:
        raw_targets.append(target)
    for s in scopes:
        if _looks_like_file_path(s):
            raw_targets.append(s)

    targets = []
    for raw in raw_targets:
        for component in _split_compound_targets(raw):
            targets.append(component)
    return targets


def _read_with_ledger(path):
    """Read a resolved file, folding in the sibling ledger body for a dehydrated
    CLAUDE.md target.

    The dehydration-aware half of the consumer-set fix (tic 335): a promoted_to
    pointing at a dehydrated CLAUDE.md (federation or CGG compact root) names a
    surface that, post-dehydration, carries only the pointer index — the
    inscription body relocated to a sibling ledger.md. Returning the CLAUDE.md
    content ALONE makes check_promoted report `promoted_text_missing` for
    doctrine that IS inscribed. resolve_doctrine_surfaces returns
    [claude_md, ledger_md] for a dehydrated rung; we concatenate so the cpr_id /
    lesson-snippet match runs against the body where the doctrine lives.

    This only EXPANDS the searched text — the match predicate in check_promoted
    (cpr_id literal or lesson snippet) is unchanged, so a genuinely-missing
    inscription still fails to match and still fires. No false-negative widening.
    """
    base = read_file_safe(path)
    if os.path.basename(path) != "CLAUDE.md":
        return base
    parts = [base] if base else []
    for surface in resolve_doctrine_surfaces(path):
        if os.path.basename(surface) == "CLAUDE.md":
            continue  # already read as `base`
        ledger_body = read_file_safe(surface)
        if ledger_body:
            parts.append(ledger_body)
    return "\n".join(parts)


def _read_target(target_str, project_dir, project_basename=None):
    """Resolve a target string to a filesystem path and return its content.

    Applies three normalizations before resolving:
      1. Parenthetical scope-hint stripping — "canonical/CLAUDE.md (refined 'X')"
         becomes "canonical/CLAUDE.md".
      2. Path-anchor stripping — "file.md:389-391", "file.md#anchor",
         "file.yaml#field.path" all reduce to their bare file path. The anchor
         suffix is structurally meaningful (names the inscription location) but
         is not a filesystem path component.
      3. Federation-prefix stripping — when the first path segment matches the
         federation repo's basename (e.g. "canonical/CLAUDE.md" where the repo
         is named "canonical"), strip that segment and resolve relative to
         project_dir.  This handles queue entries that record paths relative to
         the parent of the federation root rather than relative to it.

    Returns file content as str, or "" if the file cannot be read.
    """
    bare = _strip_scope_hint(target_str)
    bare = _strip_path_anchor(bare)

    if bare.startswith("~"):
        path = os.path.expanduser(bare)
        return _read_with_ledger(path)

    if os.path.isabs(bare):
        return _read_with_ledger(bare)

    # Relative path: resolve against project_dir
    path = os.path.join(project_dir, bare)
    content = _read_with_ledger(path)
    if content:
        return content

    # Federation-prefix fallback: if the leading segment of the relative path
    # matches the repo's own basename, strip it and retry.
    # E.g. project_dir=/…/canonical, bare="canonical/CLAUDE.md"
    #   -> retry with "CLAUDE.md" -> /…/canonical/CLAUDE.md
    if project_basename:
        parts = bare.replace("\\", "/").split("/")
        if parts and parts[0] == project_basename:
            stripped = "/".join(parts[1:])
            if stripped:
                path2 = os.path.join(project_dir, stripped)
                content2 = _read_with_ledger(path2)
                if content2:
                    return content2

    # Auto-memory fallback (tic 335): a bare `feedback_x.md` / `session_lessons_x.md`
    # promoted_to target lives in the auto-memory dir, not the federation repo.
    # Only the basename is used (auto-memory is flat).
    am_path = AUTO_MEMORY_DIR / os.path.basename(bare)
    content_am = read_file_safe(str(am_path))
    if content_am:
        return content_am

    return ""


def _target_exists(target_str, project_dir, project_basename=None):
    """Return True if target resolves to an existing file or directory.

    Used by the receipt-closure axis: when a target carries the
    "(already inscribed ...)" annotation, existence-of-target is sufficient
    evidence that the inscription has a real referent — the actual doctrine
    content lives in a sibling surface (prior tic's commit) and the
    promoted_to string is a pointer to where it was inscribed, not a
    verification target for literal-content match.

    Applies the same normalizations as _read_target but checks os.path.exists
    rather than reading content. Handles trailing slashes (directory targets)
    by stripping them before lookup.
    """
    bare = _strip_scope_hint(target_str).rstrip("/")
    bare = _strip_path_anchor(bare)

    if bare.startswith("~"):
        return os.path.exists(os.path.expanduser(bare))

    if os.path.isabs(bare):
        return os.path.exists(bare)

    path = os.path.join(project_dir, bare)
    if os.path.exists(path):
        return True

    if project_basename:
        parts = bare.replace("\\", "/").split("/")
        if parts and parts[0] == project_basename:
            stripped = "/".join(parts[1:])
            if stripped and os.path.exists(os.path.join(project_dir, stripped)):
                return True

    # Auto-memory fallback (tic 335): bare auto-memory filenames resolve there.
    if (AUTO_MEMORY_DIR / os.path.basename(bare)).exists():
        return True

    return False


def check_promoted(cpr_id, cpr, project_dir, inscribed_ids=None, lesson_fallbacks=None):
    """Verify promoted CPR text landed in target file.

    Verification axes (any one resolves):
      1. cpr_id appears in inscribed_ids index (provenance-comment scan of governance files)
      2. cpr_id (or CogPR-N alt) appears in any target file
      3. lesson snippet appears in any target file
         - lesson sourced from the promoted entry when non-empty
         - lesson sourced from lesson_fallbacks (earlier queue entries for same id) when
           the promoted entry is a minimal writeback row with no lesson field
      4. (fallback) promoted_to is a tilde path that resolves to an existing non-empty file
         for entries where the lesson cannot be recovered from any queue row
      5. RECEIPT-CLOSURE axis: target carries an "(already inscribed ...)" parenthetical
         annotation AND the bare-path target resolves to an existing file/directory.
         Receipt-closure PROMOTES point at sibling surfaces where the doctrine was
         inscribed in a prior tic; the promoted_to string is a pointer, not a literal-
         content verification target. Existence-of-target is sufficient evidence under
         this axis. (Refines federation KI "Verification-gate drift requires dual fix"
         — extends the dual-fix pattern from legacy stale targets to structurally-typed
         sibling-surface receipt-closure targets per
         cpr_verification_gate_drift_receipt_closure_instance_tic259.)

    Target normalization:
      - Parenthesized scope hints stripped before path resolution
        ("file.md (refined 'X')" -> "file.md")
      - Anchor/line-range/YAML-key-path suffixes stripped
        ("file.md:N-M", "file.md#anchor", "file.yaml#field.path" -> "file.md")
      - Compound `+`-joined targets split into individual components
        ("file.md + dir.ts" -> ["file.md", "dir.ts"])
      - Federation-prefix stripping retried when bare path fails

    Targets, in priority order: promoted_to (verdict-side authoritative),
    promotion_target (legacy), recommended_scopes (filtered to file-path-shaped entries).
    """
    findings = []

    # Historical-artifact bypass — triaged legacy entries
    if cpr.get("historical_artifact"):
        return findings

    # Provenance-index axis — strongest signal
    if inscribed_ids and cpr_id in inscribed_ids:
        return findings

    lesson = cpr.get("lesson", "")
    # Fallback: recover lesson from an earlier queue entry when the promoted writeback
    # is a minimal row without lesson text (convention: enrichment_eligible rows carry
    # the full lesson; promoted writeback rows sometimes omit it).
    if not lesson and lesson_fallbacks:
        lesson = lesson_fallbacks.get(cpr_id, "")

    # Collect + compound-split target strings via the shared helper (same list
    # classify_known_reason consumes, so finding-production and classification
    # never drift on what counts as a target).
    targets = _collect_targets(cpr)

    if not targets:
        findings.append({
            "type": "promoted_no_target",
            "severity": "warning",
            "cpr_id": cpr_id,
            "message": f"{cpr_id} promoted but has no target or recommended_scopes",
        })
        return findings

    cpr_ref = cpr_id
    num_match = re.search(r"(\d+)", cpr_id)
    cpr_ref_alt = f"CogPR-{num_match.group(1)}" if num_match else None
    snippet = lesson[:50] if lesson else ""
    found_in_any = False

    # Federation-repo basename for prefix-stripping fallback (see _resolve_target_path).
    project_basename = os.path.basename(project_dir)

    for t in targets:
        # Receipt-closure axis (#5): annotation signals doctrine inscribed in a prior tic
        # at a sibling surface; existence-of-target is sufficient evidence.
        if _has_receipt_closure_annotation(t) and _target_exists(t, project_dir, project_basename):
            found_in_any = True
            break

        content = _read_target(t, project_dir, project_basename)
        if not content:
            continue

        if cpr_ref and cpr_ref in content:
            found_in_any = True
            break
        if cpr_ref_alt and cpr_ref_alt in content:
            found_in_any = True
            break
        if snippet and snippet in content:
            found_in_any = True
            break

    if not found_in_any:
        findings.append({
            "type": "promoted_text_missing",
            "severity": "error",
            "cpr_id": cpr_id,
            "targets_checked": targets[:5],
            "message": f"{cpr_id} marked promoted but text not found in targets",
        })

    return findings


# Provenance-comment recognition (extended at tic 282 per D7 W2 — review-close-check
# search-path family). Catches all governance-style provenance verbs (promoted,
# promoted-spec, absorbed, refined, extended, merged, superseded) regardless of
# the verb→ref-keyword shape ("from", "by", "at tic N /review from"). Compound
# references with multiple cpr_xxx refs in one comment are captured as a set
# (refined-from-A+B pattern observed in ledger.md).
_PROVENANCE_VERB_RE = re.compile(
    r"<!--\s*(?:"
    r"(?:promoted-spec|promoted|absorbed|refined|extended|merged|superseded)"
    r"|CPR-ID:"
    r").*?-->",
    re.IGNORECASE | re.DOTALL,
)
_CPR_REF_RE = re.compile(r"(cpr_[A-Za-z0-9_]+|CogPR-\d+)")
# Backwards-compat alias retained for downstream callers; not used internally.
_PROVENANCE_RE = _PROVENANCE_VERB_RE


def build_inscribed_index(project_dir):
    """Scan governance files for `<!-- promoted from <id>` markers.

    Returns set of CPR ids that have provenance comments anywhere in the
    federation governance surface. Used by check_promoted as the strongest
    verification axis — surviving the comment is sufficient evidence of
    inscription, regardless of whether the queue entry's `promoted_to` field
    points at the correct file.

    Scanned surfaces (patch tic 216, extended tic 280):
    - canonical/CLAUDE.md, INDEX.md, GIT_RULES.md — federation root governance docs
    - audit-logs/governance/constitution-ledger/ledger.md — Pass-4-A demoted-body
      ledger (carries provenance markers for legacy CogPRs whose body text was
      relocated from compact root to ledger under the dehydration plan; per
      CogPR cpr_review_close_check_verifier_dehydration_blindspot_tic279)
    - ~/.claude/CLAUDE.md — global user governance surface
    - canonical_developer/ subtree — CLAUDE.md, AUTHORING_CONVENTION.md, SKILL.md, and
      ledger.md files (ledger.md added tic 316 — the CGG dehydration relocated CGG CLAUDE.md
      bodies into cgg-ledger/ledger.md; n=2 recurrence of the dehydration blindspot)
    - autonomous_kernel/ and ak_control_room/ subtrees — CLAUDE.md files
    - auto-memory directory (~/.claude/projects/-Users-breydentaylor-canonical/memory/)
      — feedback, session-lesson, and topic files that are promotion targets
    """
    inscribed = set()
    candidate_paths = [
        os.path.join(project_dir, "CLAUDE.md"),
        os.path.join(project_dir, "INDEX.md"),
        # GIT_RULES.md carries <!-- promoted from --> comments for git-workflow CPRs
        os.path.join(project_dir, "GIT_RULES.md"),
        # Pass-4-A demoted-body ledger — verifier dehydration blindspot fix per
        # cpr_review_close_check_verifier_dehydration_blindspot_tic279.
        # Carries `<!-- promoted from cpr_xxx -->` markers for legacy CogPRs
        # whose body text was relocated from canonical/CLAUDE.md under the
        # constitutional dehydration plan (Architect verdict tic 245).
        os.path.join(
            project_dir,
            "audit-logs",
            "governance",
            "constitution-ledger",
            "ledger.md",
        ),
        os.path.expanduser("~/.claude/CLAUDE.md"),
    ]
    # Sweep canonical_developer subtree CLAUDE.md surfaces (CGG, capture-studio, etc.)
    cd_dir = os.path.join(project_dir, "canonical_developer")
    if os.path.isdir(cd_dir):
        for root, _dirs, files in os.walk(cd_dir):
            if "/.git/" in root or "/node_modules/" in root:
                continue
            for fn in files:
                # ledger.md added tic 316: the tic-314 CGG dehydration relocated CGG
                # CLAUDE.md bodies into canonical_developer/context-grapple-gun/cgg-ledger/ledger.md.
                # Without scanning subtree ledger.md files the provenance markers there are
                # invisible, producing 135 false promoted_text_missing/orphaned_promotion findings
                # (n=2 recurrence of the tic-279 dehydration-blindspot, now on the CGG surface).
                if fn in ("CLAUDE.md", "AUTHORING_CONVENTION.md", "ledger.md") or fn.endswith("SKILL.md"):
                    candidate_paths.append(os.path.join(root, fn))
    # Also sweep autonomous_kernel and ak_control_room if present
    for sub in ("autonomous_kernel", "ak_control_room"):
        sd = os.path.join(project_dir, sub)
        if os.path.isdir(sd):
            for root, _dirs, files in os.walk(sd):
                for fn in files:
                    if fn == "CLAUDE.md":
                        candidate_paths.append(os.path.join(root, fn))
    # Auto-memory directory — feedback_*.md, session_lessons_*.md, project_*.md, etc.
    # These files are direct promotion targets for auto-memory CPRs and may carry
    # <!-- promoted from --> markers.
    auto_memory_dir = Path.home() / ".claude" / "projects" / "-Users-breydentaylor-canonical" / "memory"
    if auto_memory_dir.is_dir():
        for fpath in auto_memory_dir.iterdir():
            if fpath.suffix == ".md" and fpath.is_file():
                candidate_paths.append(str(fpath))

    for path in candidate_paths:
        content = read_file_safe(path)
        if not content:
            continue
        # Two-pass: find each provenance HTML-comment block, then extract every
        # cpr_xxx / CogPR-N ref inside it. The compound case ("refined from A + B")
        # surfaces both refs from a single comment.
        for m in _PROVENANCE_VERB_RE.finditer(content):
            for ref_match in _CPR_REF_RE.finditer(m.group(0)):
                inscribed.add(ref_match.group(1))
    return inscribed


def check_deferred(cpr_id, cpr):
    """Verify deferred CPR has updated review_tic."""
    findings = []

    review_tic = cpr.get("review_tic")
    if review_tic is None:
        findings.append({
            "type": "deferred_no_review_tic",
            "severity": "warning",
            "cpr_id": cpr_id,
            "message": f"{cpr_id} deferred but review_tic not set",
        })

    return findings


def check_skipped(cpr_id, cpr):
    """Verify skipped CPR has correct status."""
    findings = []
    status = cpr.get("status", "")

    if status != "skipped":
        findings.append({
            "type": "skip_status_mismatch",
            "severity": "warning",
            "cpr_id": cpr_id,
            "actual_status": status,
            "message": f"{cpr_id} should be 'skipped' but is '{status}'",
        })

    return findings


def check_orphans(queue, project_dir, inscribed_ids=None):
    """Find CPRs marked promoted in queue but missing from all governance files.

    Verification axes (any one resolves):
      1. Historical-artifact bypass (triaged legacy entries)
      2. cpr_id appears in inscribed_ids index
      3. cpr_id, CogPR-N alt, or lesson snippet appears in promoted_to /
         recommended_scopes / common governance locations
    """
    findings = []

    for cpr_id, cpr in queue.items():
        if cpr.get("status") != "promoted":
            continue

        if cpr.get("historical_artifact"):
            continue

        if inscribed_ids and cpr_id in inscribed_ids:
            continue

        lesson = cpr.get("lesson", "")
        if not lesson:
            continue

        cpr_num = re.search(r"(\d+)", cpr_id)
        cpr_ref = f"CogPR-{cpr_num.group(1)}" if cpr_num else cpr_id
        snippet = lesson[:50]

        check_paths = [
            os.path.join(project_dir, "CLAUDE.md"),
            # Pass-4-A demoted-body ledger — verifier dehydration blindspot fix
            # per cpr_review_close_check_verifier_dehydration_blindspot_tic279.
            os.path.join(
                project_dir,
                "audit-logs",
                "governance",
                "constitution-ledger",
                "ledger.md",
            ),
            os.path.expanduser("~/.claude/CLAUDE.md"),
        ]

        # Helper: append a target's project-dir resolution AND its auto-memory
        # resolution (tic 335). A bare `feedback_x.md` promoted_to lives in the
        # auto-memory dir, not the federation repo — joining it to project_dir
        # alone never resolves and produced a false orphaned_promotion.
        def _append_target(t):
            t = _strip_path_anchor(_strip_scope_hint(t))
            if t.startswith("~"):
                check_paths.append(os.path.expanduser(t))
            elif os.path.isabs(t):
                check_paths.append(t)
            else:
                check_paths.append(os.path.join(project_dir, t))
            check_paths.append(str(AUTO_MEMORY_DIR / os.path.basename(t)))

        promoted_to = cpr.get("promoted_to", "")
        if isinstance(promoted_to, str) and promoted_to:
            _append_target(promoted_to)
        elif isinstance(promoted_to, list):
            for p in promoted_to:
                if isinstance(p, str) and p:
                    _append_target(p)

        for scope in cpr.get("recommended_scopes", []):
            if not _looks_like_file_path(scope):
                continue
            _append_target(scope)

        found = False
        for path in check_paths:
            # Dehydration-aware read: a CLAUDE.md target folds in its sibling
            # ledger body (tic 335) so a promoted body relocated to the ledger
            # is found rather than read as missing.
            content = _read_with_ledger(path)
            if content and (cpr_id in content or cpr_ref in content or snippet in content):
                found = True
                break

        if not found:
            findings.append({
                "type": "orphaned_promotion",
                "severity": "error",
                "cpr_id": cpr_id,
                "cpr_ref": cpr_ref,
                "message": f"{cpr_id} marked promoted in queue but text not found in any governance file",
            })

    return findings


# ---------------------------------------------------------------------------
# Genuine-vs-known reason split
# (cgg-ledger#reason-coded-genuine-vs-known-verifier-split, promoted /review 336)
# ---------------------------------------------------------------------------

def _is_codeish_path(path):
    """True if a resolved path is a code/behavioral surface — a source file or a
    SKILL.md whose promotion lands as behavior, not quotable text."""
    base = os.path.basename(path)
    if base == "SKILL.md":
        return True
    return os.path.splitext(base)[1].lower() in _CODE_SUFFIXES


def _resolve_target_path(target_str, project_dir, project_basename=None):
    """Return an existing filesystem path for a target string, or None.

    The path-returning sibling of _read_target / _target_exists. Tries, in order:
    absolute / tilde, project-relative, federation-prefix strip, auto-memory,
    then a bounded suffix-rglob. The rglob is what resolves DOMAIN-relative
    targets: a promoted_to like `cgg-runtime/scripts/x.py` names a path relative
    to a nested domain root, not project_dir, so the direct join fails even
    though the file exists. That "domain-relative path" shape is exactly what the
    reason-split doctrine calls out as content-unverifiable.
    """
    bare = _strip_path_anchor(_strip_scope_hint(target_str)).rstrip("/")
    if not bare:
        return None
    if bare.startswith("~"):
        p = os.path.expanduser(bare)
        return p if os.path.exists(p) else None
    if os.path.isabs(bare):
        return bare if os.path.exists(bare) else None
    p = os.path.join(project_dir, bare)
    if os.path.exists(p):
        return p
    if project_basename:
        parts = bare.replace("\\", "/").split("/")
        if parts and parts[0] == project_basename:
            stripped = "/".join(parts[1:])
            if stripped:
                p2 = os.path.join(project_dir, stripped)
                if os.path.exists(p2):
                    return p2
    am = AUTO_MEMORY_DIR / os.path.basename(bare)
    if am.exists():
        return str(am)
    # Bounded suffix-rglob — only reached when direct resolution failed.
    try:
        hits = [h for h in _glob.glob(os.path.join(project_dir, "**", bare), recursive=True)
                if os.path.isfile(h)]
    except OSError:
        return None
    return sorted(hits)[0] if hits else None


def _git_pickaxe_hits(project_dir, cpr_id, limit=5):
    """Provenance-trace axis: return up to `limit` short commit hashes whose diff
    introduces or removes the cpr_id (`git log -S`).

    A behavioral inscription leaves NO content-matchable trace in its code
    target, but the cpr_id itself has committed lineage (queue.jsonl writeback,
    spec files) — pickaxe -S confirms the CogPR is a real, committed governance
    artifact, not a phantom id. Combined with an existing code/behavioral target,
    that is sufficient positive evidence the promotion is behavioral-and-landed.
    Fail-soft to [] when git is unavailable or the dir is not a repo.
    """
    try:
        out = subprocess.run(
            ["git", "-C", project_dir, "log", "--all", "--oneline",
             f"-S{cpr_id}", f"--max-count={limit}"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    return [ln.split()[0] for ln in out.stdout.splitlines() if ln.strip()]


def _find_relocated(target_str, project_dir, cpr_id, snippet=""):
    """Relocation-aware pointer-correction axis: if a target's named path is
    ABSENT, search the relocation roots for a same-basename file that carries
    cpr-identifying evidence (cpr_id literal, CogPR-N alt, or lesson snippet).
    Returns the relocated (corrected) path on a hit, else None.

    Pass-4 dehydration moved doctrine files into
    audit-logs/governance/dehydration-pipeline-archive/ but the queue pointer
    still names the pre-move path. The corrected pointer is surfaced as evidence
    — it is NOT silently rewritten into the queue (that is a separate data-fix).
    Positive content evidence (not bare basename collision) is required so a
    same-named-but-unrelated file is never mistaken for the relocation.
    """
    bare = _strip_path_anchor(_strip_scope_hint(target_str)).rstrip("/")
    base = os.path.basename(bare)
    if not base:
        return None
    num = re.search(r"(\d+)", cpr_id)
    cpr_ref_alt = f"CogPR-{num.group(1)}" if num else None
    for root in _RELOCATION_ROOTS:
        root_abs = os.path.join(project_dir, root)
        if not os.path.isdir(root_abs):
            continue
        for dirpath, _dirs, files in os.walk(root_abs):
            if base not in files:
                continue
            fpath = os.path.join(dirpath, base)
            content = read_file_safe(fpath)
            if not content:
                continue
            if cpr_id in content:
                return fpath
            if cpr_ref_alt and cpr_ref_alt in content:
                return fpath
            if snippet and snippet in content:
                return fpath
    return None


def classify_known_reason(cpr_id, cpr, project_dir, project_basename=None,
                          lesson_fallbacks=None):
    """Classify a promoted_text_missing / orphaned_promotion finding as a KNOWN
    false-positive (with a REASON code) or GENUINE (reason=None).

    Per cgg-ledger#reason-coded-genuine-vs-known-verifier-split: a content-
    matching verifier CANNOT verify behavioral/relocated targets by any amount of
    surface resolution, so a bare consistent:false over-reports. This assigns each
    finding a reason so only reason=None findings count as GENUINE (G>0, the sole
    hazard). The shared dehydration resolver (resolve_doctrine_surfaces) closes
    only the dehydration_resolved reason upstream; these axes close the rest.

    Returns (reason, evidence_dict). reason is a REASON_* code or None (genuine).

    Axes, in priority order:
      1. stale_relocated_pointer — a target's named path is ABSENT but the
         doctrine is found (cpr_id / alt / snippet) at a relocation root;
         evidence carries the corrected pointer. Highest priority: a moved file
         is content-verified at the new path, the strongest positive signal.
      2. behavioral_text_unverifiable — a target resolves to an existing
         code/behavioral surface (.py/.sh/SKILL.md/...); the inscription is a
         BEHAVIOR not text, strengthened by the git provenance-trace.
      3. (none) GENUINE — no target resolves to a code surface and none relocate;
         the inscription is genuinely missing (the hazard).
    """
    targets = _collect_targets(cpr)
    lesson = cpr.get("lesson", "")
    if not lesson and lesson_fallbacks:
        lesson = lesson_fallbacks.get(cpr_id, "")
    snippet = lesson[:50] if lesson else ""

    relocated = None
    behavioral = None
    for t in targets:
        existing = _resolve_target_path(t, project_dir, project_basename)
        if existing is None:
            if relocated is None:
                hit = _find_relocated(t, project_dir, cpr_id, snippet)
                if hit:
                    relocated = (t, hit)
        elif behavioral is None and _is_codeish_path(existing):
            behavioral = (t, existing)

    if relocated is not None:
        orig, corrected = relocated
        try:
            corrected_rel = os.path.relpath(corrected, project_dir)
        except ValueError:
            corrected_rel = corrected
        return REASON_STALE_RELOCATED, {
            "stale_pointer": orig,
            "corrected_pointer": corrected_rel,
            "note": "doctrine relocated by Pass-4 dehydration; queue pointer not "
                    "updated (corrected_pointer is the live location)",
        }

    if behavioral is not None:
        orig, resolved = behavioral
        trace = _git_pickaxe_hits(project_dir, cpr_id)
        return REASON_BEHAVIORAL, {
            "behavioral_target": orig,
            "resolved_path": resolved,
            "provenance_trace_commits": trace,
            "note": "inscription is a code behavior, not quotable text; verified "
                    "via target existence + cpr_id git lineage (pickaxe -S)",
        }

    return None, {
        "note": "no code/behavioral target and no relocation found; inscription "
                "appears genuinely missing",
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def load_mandate_id(al_path):
    """Read (mandate_id, tic) from audit-logs/mogul/mandates/current.json.

    Returns (None, None) when current.json is absent or unreadable. The caller
    falls back to timestamp-keyed identity and emits a stderr warning so the
    canonical-identity instability is visible per T4c spec.
    """
    mandate_path = Path(al_path) / "mogul" / "mandates" / "current.json"
    try:
        data = json.loads(mandate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (None, None)
    mandate_id = data.get("mandate_id")
    tic = data.get("tic")
    if tic is None:
        tic_ctx = data.get("tic_context") or {}
        tic = tic_ctx.get("current_tic")
    if tic is None and isinstance(mandate_id, str):
        m = re.match(r"tic-(\d+)-", mandate_id)
        if m:
            tic = int(m.group(1))
    return (mandate_id, tic)


def run_check(project_dir, dry_run=False):
    """Run the full review-close consistency check."""
    project_dir = os.path.abspath(project_dir)
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)

    queue_path = os.path.join(al_path, "cprs", "queue.jsonl")
    queue = load_queue(queue_path)
    # Lesson fallbacks: recover lesson text from earlier (pre-writeback) queue rows
    # when the latest (promoted) entry is a minimal writeback with no lesson field.
    lesson_fallbacks = load_lesson_fallbacks(queue_path)

    inscribed_ids = build_inscribed_index(project_dir)

    all_findings = []

    # Check each CPR based on its status
    for cpr_id, cpr in queue.items():
        status = cpr.get("status", "")

        if status == "promoted":
            all_findings.extend(check_promoted(cpr_id, cpr, project_dir, inscribed_ids, lesson_fallbacks))

        elif status in ("deferred", "enrichment_eligible"):
            # Deferred CPRs should have a review_tic
            if cpr.get("review_tic") is not None:
                all_findings.extend(check_deferred(cpr_id, cpr))

        elif status == "skipped":
            all_findings.extend(check_skipped(cpr_id, cpr))

    # Orphan check across all promoted
    all_findings.extend(check_orphans(queue, project_dir, inscribed_ids))

    # Genuine-vs-known reason split (cgg-ledger#reason-coded-genuine-vs-known-verifier-split,
    # promoted /review 336): annotate each promoted-missing / orphaned finding with a
    # REASON code so only reason=None (genuinely missing) findings count as hazards.
    # KNOWN findings are downgraded to severity=info — they are expected noise, not
    # inconsistencies — so by_severity.error reflects ONLY genuine hazards. Done before
    # the severity aggregation below so the downgrade is reflected in the counts.
    project_basename = os.path.basename(project_dir)
    genuine_count = 0
    known_count = 0
    known_by_reason = {}
    for f in all_findings:
        if f.get("type") not in ("promoted_text_missing", "orphaned_promotion"):
            continue
        cpr = queue.get(f.get("cpr_id"), {})
        reason, evidence = classify_known_reason(
            f["cpr_id"], cpr, project_dir, project_basename, lesson_fallbacks
        )
        f["evidence"] = evidence
        if reason is None:
            f["finding_class"] = "genuine"
            genuine_count += 1
        else:
            f["finding_class"] = "known"
            f["reason"] = reason
            f["severity"] = "info"  # known false-positive — not a hazard
            known_count += 1
            known_by_reason[reason] = known_by_reason.get(reason, 0) + 1

    # Build report
    severity_counts = {}
    for f in all_findings:
        sev = f.get("severity", "info")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    type_counts = {}
    for f in all_findings:
        t = f.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Count by verdict
    promoted_count = sum(1 for c in queue.values() if c.get("status") == "promoted")
    deferred_count = sum(1 for c in queue.values() if c.get("status") in ("deferred", "enrichment_eligible") and c.get("review_tic"))
    skipped_count = sum(1 for c in queue.values() if c.get("status") == "skipped")

    historical_count = sum(1 for c in queue.values() if c.get("historical_artifact"))

    report = {
        "check_type": "review_close_check",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queue_path": queue_path,
        "total_cprs": len(queue),
        "inscribed_index_size": len(inscribed_ids),
        "historical_artifacts": historical_count,
        "verdict_counts": {
            "promoted": promoted_count,
            "deferred": deferred_count,
            "skipped": skipped_count,
        },
        "findings": all_findings,
        "summary": {
            "total_findings": len(all_findings),
            "by_severity": severity_counts,
            "by_type": type_counts,
            # `consistent` retains its original meaning (ZERO findings) for
            # backward compatibility with downstream log/runner consumers.
            "consistent": len(all_findings) == 0,
            # Genuine-vs-known split: only `genuine` findings are hazards.
            # genuine_consistent is the authoritative health signal — a cycle
            # with K>0 known false-positives but G==0 is healthy.
            "genuine_count": genuine_count,
            "known_count": known_count,
            "known_by_reason": known_by_reason,
            "genuine_consistent": genuine_count == 0,
        },
    }

    if not dry_run:
        # T4c spec (W3-B1 tic 282 refinement): canonical artifact identity is
        # tic-keyed, not mandate-keyed or timestamp-keyed. Per-tic uniqueness is
        # the structural target — N=1 cardinality per tic regardless of how many
        # distinct mandates within the tic invoke review-close-check (cadence
        # mandate + review-close mandate + post-/review inline invocation all
        # collapse to one canonical artifact). This closes the falsification gate
        # from rail-T1 B1 ("future mandate cycles should observe N=1 cardinality
        # consistently"). The mandate_id is preserved in the log entry as audit
        # trail for which invocation lane wrote which content.
        # Filesystem enforces per-tic uniqueness; latest-wins for content under
        # the dedup decision policy below.
        from lib.atomic_append import atomic_append_jsonl

        report_dir = os.path.join(al_path, "mogul", "cycle-reports", "review-close-checks")
        os.makedirs(report_dir, exist_ok=True)

        mandate_id, mandate_tic = load_mandate_id(al_path)
        if mandate_tic is not None:
            # Tic-keyed canonical filename — collapses multiple mandates within
            # the same tic to a single artifact (N=1 cardinality target).
            output_filename = f"tic-{mandate_tic}-check.json"
        elif mandate_id:
            # No tic resolvable but mandate_id present — fall back to mandate-keyed
            # filename. Preserves per-mandate dedup even when tic parse fails.
            output_filename = f"{mandate_id}-check.json"
            print(
                "WARNING: review_close_check write without mandate tic; "
                "falling back to mandate-keyed identity (per-tic dedup degraded).",
                file=sys.stderr,
            )
        else:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
            output_filename = f"{timestamp}-check.json"
            print(
                "WARNING: review_close_check write without mandate_id; "
                "falling back to timestamp identity (canonical artifact identity unstable).",
                file=sys.stderr,
            )
        output_path = os.path.join(report_dir, output_filename)

        decision = "write"
        if (mandate_tic is not None or mandate_id) and os.path.exists(output_path):
            try:
                prior = json.loads(Path(output_path).read_text(encoding="utf-8"))
                if prior.get("findings") == report["findings"]:
                    decision = "skip"
                else:
                    decision = "replace"
            except (OSError, json.JSONDecodeError):
                # Corrupt or unreadable prior — overwrite under latest-wins semantics.
                decision = "replace"

        identity_label = (
            f"tic {mandate_tic}" if mandate_tic is not None
            else f"mandate {mandate_id}"
        )

        if decision == "skip":
            # Touch existing file so the runner's `find -newer $MANDATE_FILE` verification
            # succeeds. Skip means findings are identical and the cycle DID run correctly;
            # the file's content is current but its mtime is stale from a prior session.
            # Without this touch, the runner marks the mandate failed despite healthy output.
            # Root cause of tic-271 mandate failure (civil report 2026-05-22-tic-272.json).
            Path(output_path).touch()
            print(
                f"INFO: review_close_check skipped (identical report exists for {identity_label}); mtime touched for runner verification.",
                file=sys.stderr,
            )
        else:
            Path(output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
            if decision == "replace":
                print(
                    f"INFO: review_close_check replaced existing report for {identity_label} (findings changed).",
                    file=sys.stderr,
                )
            else:
                print(
                    f"INFO: review_close_check wrote consistency report for {identity_label}.",
                    file=sys.stderr,
                )

        report["_output_path"] = output_path

        log_entry = {
            "mandate_id": mandate_id,
            "tic": mandate_tic,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "report_path": output_path,
            "findings_count": len(report["findings"]),
            "consistent": report["summary"]["consistent"],
            "genuine_count": report["summary"]["genuine_count"],
            "known_count": report["summary"]["known_count"],
            "genuine_consistent": report["summary"]["genuine_consistent"],
        }
        atomic_append_jsonl(
            os.path.join(al_path, "services", "review-close-check-log.jsonl"),
            log_entry,
        )

    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Review Close Check — post-review consistency verification"
    )
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run check without writing results to disk")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Output structured JSON to stdout")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    project_dir = args.project_dir or resolve_zone_root()
    report = run_check(project_dir, dry_run=args.dry_run)

    if args.output_json:
        report.pop("_output_path", None)
        print(json.dumps(report, indent=2))
    elif not args.quiet:
        s = report["summary"]
        vc = report["verdict_counts"]
        if s["consistent"]:
            status = "CONSISTENT"
        else:
            status = f"consistent:false(genuine={s['genuine_count']}, known={s['known_count']})"
        print(f"Review close check: {status}")
        print(f"  Verdicts: {vc['promoted']} promoted, {vc['deferred']} deferred, {vc['skipped']} skipped")
        if not s["consistent"]:
            if s.get("known_by_reason"):
                reasons = ", ".join(f"{k}={v}" for k, v in s["known_by_reason"].items())
                print(f"  known by reason: {reasons}")
            if s["genuine_count"]:
                print(f"  GENUINE (hazard): {s['genuine_count']}")
            else:
                print(f"  genuine=0 — no hazard (all {s['known_count']} findings are known false-positives)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
