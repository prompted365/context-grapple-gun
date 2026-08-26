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
lineage of the cpr_id, ANCHORED to the id's birth commit + full pickaxe depth per
bk-review-close-provenance-evidence-anchor / /review 723 — never a newest-first
truncation window, which converges to a global churn cursor) for behavioral/code
targets, and a relocation-aware pointer-correction axis for Pass-4-moved archive
files.

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

# Additive lifecycle-state recognition (terminal-taxonomy APPLICATION tranche,
# verdict tic 555 PROMOTE-SPEC). A row settled by the SHARED additive
# `lifecycle_state` field (and not `promoted`) is a settled disposition carrying
# its own per-row receipt — it needs no promoted-text/orphan close-check. Making
# the recognition explicit discharges the closed consumer-set obligation without
# a behavior change (these ids already fell through the status dispatch).
# Spec: audit-logs/governance/terminal-taxonomy-strike-verdict-tic555.md
LIFECYCLE_SETTLED_STATES = frozenset({
    "terminal_positive", "terminal_negative", "obligated_waiting", "suspensive",
})


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
# (git lineage of the cpr_id — see _git_provenance_anchor for the anchored,
# churn-stable shape ratified at /review 723) rather than literal-content match.
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
# anchor_present_text_rephrased — a promoted_to names a heading anchor that EXISTS
# at the resolved doctrine surface (explicit `<a id>`/`<a name>` tag, or a heading
# whose GitHub-slug matches), but the verbatim-lesson-text match misses because the
# lesson (and often the heading prose) was REPHRASED on promotion. The inscription
# landed at the named anchor — content-match cannot see a rephrased refinement. The
# anchor is the landed-proof; the rephrase is why literal-text search fails.
# (bk-review-close-anchor-presence-check, /review 409 surfaced 2 such false positives.)
REASON_ANCHOR_PRESENT = "anchor_present_text_rephrased"
# affirmed_via_receipts — a promotion is FREQUENTLY operationalized as BEHAVIOR (a
# cable-receipt, an honesty-lock drive_mode note carried inside one, a conformation
# record) rather than as quotable doctrine prose at the named target. When the
# doctrine-target content-match misses, the born-id is nonetheless CITED in a bounded
# behavioral/receipt surface — the promotion landed as behavior, not text. This is
# the tic-593 widening of the sweep beyond the named doctrine target file.
# (bk-review-close-check-widen-sweep-tic593; proven case
# cpr_hoist_s6_close_anchor_must_track_proposal_head_tic590, affirmed across 6
# tic-591 S-cable receipts + conformation tic-591.)
REASON_AFFIRMED_VIA_RECEIPTS = "affirmed_via_receipts"
# prose_spec_suffix_normalized_present — a born is promoted INTO a prose/doctrine spec
# (hoist-wave-engine-spec, outbound-syntax-contagion-boundary-spec, …) rather than an
# auto-memory file or a ledger anchor. The spec references the born by its id with the
# extractor-appended `_tic<N>` suffix STRIPPED, and — until the emit-side breadcrumb
# stamping (review-promote-writeback.py) reaches prose-spec targets — carries no
# `<!-- promoted from … -->` breadcrumb. So the full-id content match in check_promoted
# misses (queue id `cpr_x_tic590` vs spec citation `cpr_x`) and the finding false-fires.
# This axis strips the suffix and matches the born-id (full OR `_tic<N>`-stripped) against
# the resolved prose-spec's breadcrumbs/body; a hit is VERIFIED-present (the born-id is a
# long unique slug — same positive-signal reasoning as the evidence-anchor axis), so the
# finding is KNOWN(reason), never blanket-suppressed. Distinct from anchor_present_text_
# rephrased, which requires a heading anchor OR a same-line Evidence marker; this axis is
# the broader fallback when the citation sits on a plain line.
# (bk-review-close-check-prose-spec-breadcrumb, tic 620.)
REASON_PROSE_SPEC_SUFFIX_NORMALIZED = "prose_spec_suffix_normalized_present"
# pipeline_advanced_never_reviewed — enrichment_eligible is reachable by TWO lifecycle
# paths: a /review DEFER writeback (carries review-writeback fields) and ordinary
# pipeline advancement (enrichment scanner / gate / stepper — carries enrichment-lineage
# fields and is legitimately provenance-free: it is AWAITING its first review). The
# checker must discriminate by in-row path evidence BEFORE demanding path-specific
# provenance — enrichment-lineage fields present + review-writeback fields absent means
# awaiting-first-review, a KNOWN non-hazard, never a provenance inconsistency.
# (Verifier-Split Chapter 3, cgg-ledger#reason-coded-genuine-vs-known-verifier-split;
# bk-review-close-check-reason-coverage-path-discrimination, admitted /review 621,
# built tic 628.)
REASON_PIPELINE_ADVANCED = "pipeline_advanced_never_reviewed"

# In-row path-evidence vocabularies for the enrichment_eligible discrimination.
# REVIEW-WRITEBACK fields: any of these present means a /review pass touched the row —
# path-specific provenance (review_tic/reviewed_tic) is then legitimately demanded.
_REVIEW_WRITEBACK_FIELDS = frozenset({
    "review_tic", "reviewed_tic", "review_pass", "review_verdict", "reviewed_at",
    "reviewed_by", "verdict_class", "defer_reason", "deferred_at", "deferred_by",
    "defer_until_tic", "docket", "reeval_tic", "review_confidence", "review_reasoning",
})
# ENRICHMENT-LINEAGE fields: written by the advancement path (scanner writeback, gate
# advance, stepper). Deliberately EXCLUDES the pure scanner stamps
# (enrichment_scan_count / enrichment_scanned_at) — the scanner stamps every row it
# scans, including review-deferred ones, so those two discriminate nothing.
_ENRICHMENT_LINEAGE_FIELDS = frozenset({
    "enriched_at_tic", "enriched_by", "enriched_at", "enriched_tic",
    "enrichment_artifact", "enrichment", "writeback_reason",
    "advanced_tic", "advanced_by", "advance_reason",
    "gate_advanced_at_tic", "gate_advanced_by", "gate_advance_reason",
    "stepper_advancement",
})

# Behavioral / receipt surface roots swept before a promotion is graded genuinely
# missing (tic 593). SCOPED — never all of audit-logs — so pipeline-bookkeeping
# surfaces (queue.jsonl, bench-packets, civil-reports, corpus-harvest, cycle
# reports) that name EVERY id can NEVER trivially "affirm" a promotion; only a
# genuine behavioral receipt naming the born counts. Paths are project-dir-relative.
_RECEIPT_SURFACE_ROOTS = (
    "audit-logs/governance/harpoon-office/cable-receipts",
    "audit-logs/conformations",
)


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

    The split is PAREN-AWARE (fix A, authorized /review 680 — the t679/t680
    false-GENUINE sole live cause): a ` + ` occurring INSIDE a parenthetical
    scope hint is hint text, not a component boundary. Splitting the raw
    string before hint-stripping fractured
    "cgg-gate.sh (… step 2.5 at both sites + in-flight mirror-integrity clause)"
    mid-paren into two unbalanced components that fell through every
    classification axis to GENUINE. Normalization precedes decomposition.
    """
    if " + " not in s:
        return [s]
    parts = []
    current = []
    depth = 0
    i = 0
    while i < len(s):
        if depth == 0 and s.startswith(" + ", i):
            parts.append("".join(current).strip())
            current = []
            i += 3
            continue
        ch = s[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        current.append(ch)
        i += 1
    parts.append("".join(current).strip())
    return [part for part in parts if part]


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
        components = _split_compound_targets(raw)
        targets.extend(components)
        # Resolution-order repair (Verifier-Split Ch.4 claim A,
        # bk-review-close-check-resolution-order, tic 684): when decomposition
        # actually split, keep the RAW unsplit string as a LAST-RESORT candidate.
        # A ` + ` at paren depth 0 inside a real filename (this federation has
        # such files — "cpr_x + deep_audit_y.consolidated.json") fractures into
        # components that resolve nowhere; every downstream classification axis
        # is resolution-gated, so the finding fell through as false GENUINE.
        # Components stay first (more specific); the raw form is only reached
        # when they all fail. Shared source: heals finding-production
        # (check_promoted) and classification (classify_known_reason) together.
        if len(components) > 1:
            targets.append(raw)
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

    # Cross-axis consistency hoist (authorized /review 680): the bounded
    # suffix-rglob lived only in _resolve_target_path, so resolution was
    # INCONSISTENT ACROSS AXES — domain-relative targets resolved on the
    # path axis but not the read axis (the true residue of the disproven
    # claim B: mechanism present but not reached, never absent).
    resolved = _resolve_target_path(target_str, project_dir, project_basename)
    if resolved:
        return _read_with_ledger(resolved)

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

    # Cross-axis consistency hoist (authorized /review 680): reach the same
    # bounded suffix-rglob _resolve_target_path already applies, so the
    # existence axis and the path axis can never disagree on a
    # domain-relative target.
    return _resolve_target_path(target_str, project_dir, project_basename) is not None


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
# search-path family; extended again tic 515 — verifier-split chapter 2). Catches all
# governance-style provenance verbs (promoted, promoted-spec, absorbed, refinement[ edge],
# refined, extended, merged, superseded) regardless of the verb→ref-keyword shape
# ("from", "by", "at tic N /review from"). Compound references with multiple cpr_xxx refs
# in one comment are captured as a set (refined-from-A+B pattern observed in ledger.md).
#
# tic-515 fix (cgg-ledger#inscription-verification-reason-coded-dehydration-provenance-aware):
# a REFINEMENT-EDGE promotion lands as `**Refinement — …**` prose + a
# `<!-- refinement edge from cpr_X -->` provenance comment appended to a PARENT entry's
# anchor. The verb "refinement" was NOT in the alternation, so build_inscribed_index never
# saw those cpr_ids, so check_promoted's provenance-index axis (the strongest signal) never
# fired and they false-orphaned as GENUINE. "refinement" precedes "refined" so the
# alternation matches the longer form first. The provenance comment is the strongest
# inscription witness — the verb-set must recognize every governed inscription verb.
_PROVENANCE_VERB_RE = re.compile(
    r"<!--\s*(?:"
    # tic-716 fix, n=2 of the tic-515 verb-alternation-gap class: ray
    # inscriptions authored since tic 597 open with "PROMOTE-AS-REFINEMENT"
    # — a governed inscription verb the anchored alternation never matched,
    # so their cpr tokens were invisible to the index (measured: 3 comments,
    # constitution ledger; caught by the /review-716 FLAT-720 watch reading
    # against the just-declared unit). Longer form precedes "promoted"
    # by the same longest-first discipline as refinement/refined.
    # SKIP-WITH-HOME openings stay EXCLUDED BY DESIGN (a skip pointer is
    # not an inscription witness).
    # /review-719 adjudication (cpr_mogul_review_close_check_3a40ab346adb,
    # PROMOTE-as-refinement-ray + first-consumer patch, Architect-ratified):
    # the census-residue heads "inscribed"/"review-executed" are ADMITTED
    # (the adjudication the tic-716 note reserved them for), together with
    # the row's measured unmatched inscription-witness heads
    # "CONDITIONAL-PROMOTED" (1), "MERGE" (list carried only `merged`) and
    # "REINFORCED" (1). The closed-list sin is not re-committed silently:
    # the unmatched-provenance-shaped loud counter below surfaces every
    # FUTURE head that fails this alternation instead of letting it drop
    # out of the index (cgg-ledger#emitter-rows-must-match-a-reader-
    # predicate, reciprocal direction — reader predicate over an OPEN
    # authoring vocabulary).
    r"(?:conditional-promoted|promote-as-refinement|promoted-spec|promoted|absorbed|refinement|refined|reinforced|review-executed|inscribed|conformation|conformed|extended|merged|merge|superseded)"
    r"|CPR-ID:"
    r").*?-->",
    re.IGNORECASE | re.DOTALL,
)

# Unmatched-provenance-shape loud counter (/review 719, 3a40ab346adb).
# Any HTML comment carrying a cpr-shaped token that FAILS the verb alternation
# is counted + sampled in diagnostics and announced on stderr — never gating,
# never silently dropped. SKIP-* heads are excluded by design (a skip pointer
# is deliberately not an inscription witness, so its non-match is correct).
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_SKIP_HEAD_RE = re.compile(r"<!--\s*skip", re.IGNORECASE)

# Remedy-class typing of the unmatched population (/review 736,
# cpr_mogul_review_close_check_955e9009a2da PROMOTE-TO-PROCEDURAL-HOME): one
# disclosure frame over structurally opposite classes prescribes the wrong
# cure for part of its own population, and the counter cannot converge.
# Three classes, three REACHABLE cures — disclosed per class, never gating:
#   wrong_object_class -> cure EXCLUSION: a birth record (--agnostic-candidate
#     block), a ledger-tags metadata comment, or a home-pointer is not a
#     failed inscription witness at all; admitting it would be a category
#     error, and no verb registration can ever be the fix.
#   head_anchor_gap -> cure HEAD-ANCHOR RELAXATION: an admitted verb IS
#     present but subject-prefixed off the head ("tic-733 refinement appendix
#     promoted from ...", "scope-fence ray promoted from ..."); no vocabulary
#     addition can EVER admit these. The relaxation itself is a ratified
#     build increment riding the build lane (direction ruled /review 736).
#   vocabulary_gap -> cure VERB REGISTRATION: no admitted verb anywhere in
#     the comment — the only class the original single-frame sentence
#     ("a new verdict head must enter the matcher") was ever true for.
_WRONG_OBJECT_HEAD_RE = re.compile(
    r"<!--\s*(?:--agnostic-candidate|ledger-tags:|home-pointer)",
    re.IGNORECASE)
_MIDCOMMENT_VERB_RE = re.compile(
    r"\b(?:conditional-promoted|promote-as-refinement|promoted-spec|promoted"
    r"|absorbed|refinement|refined|reinforced|review-executed|inscribed"
    r"|conformation|conformed|extended|merged|merge|superseded)\b",
    re.IGNORECASE)

_UNMATCHED_REMEDY_TEXT = {
    "wrong_object_class": ("EXCLUSION — not an inscription witness "
                           "(born block / metadata tag / pointer); verb "
                           "registration can never be the fix"),
    "head_anchor_gap": ("HEAD-ANCHOR RELAXATION — admitted verb present but "
                        "subject-prefixed off the head; build-lane increment "
                        "(ruled /review 736), not a vocabulary addition"),
    "vocabulary_gap": ("VERB REGISTRATION — no admitted verb anywhere; the "
                       "one class where a new head entering the matcher is "
                       "the true cure"),
}


def _classify_unmatched_remedy(seg):
    """Remedy class of one unmatched cpr-token-bearing comment (see above)."""
    if _WRONG_OBJECT_HEAD_RE.match(seg):
        return "wrong_object_class"
    if _MIDCOMMENT_VERB_RE.search(seg):
        return "head_anchor_gap"
    return "vocabulary_gap"
_CPR_REF_RE = re.compile(r"(cpr_[A-Za-z0-9_]+|CogPR-\d+)")
# Reserved sibling namespaces under the cpr_ prefix that are NOT CogPR ids.
# A namespace-prefix match is not identifier membership (/review 709,
# cpr_mogul_review_close_check_f94b63ce931d): at tic 706 the era metadata label
# `cpr_era_tic_700_749` entered the inscribed index and moved the counter
# without an inscription event, making the mandate's exactly-one prediction
# read +2. Reserved tokens are excluded at every _CPR_REF_RE consumer and
# REPORTED as unresolved, never silently admitted.
_RESERVED_REF_PREFIXES = ("cpr_era_",)


def _is_reserved_ref(token):
    """True for tokens in reserved sibling namespaces (metadata labels, not ids)."""
    return any(token.startswith(p) for p in _RESERVED_REF_PREFIXES)


# --- Admission-route DISCLOSURE PARITY (/review 724 RIDER 1;
# cgg-ledger#instance-keyed-cures-cannot-see-sibling-routes-disclosure-parity) ---
#
# The pre-724 boundary_rule justified this index's over-admission by exactly ONE
# route — "a sibling id NARRATED in another entry's provenance prose". At tic 721
# a token entered the index by a route that rationale does not cover: a
# CPR-SHAPED SUBSTRING OF A FILENAME cited in a provenance comment's `Source:`
# clause (`Source: DONE_cpr_stepper_advance_tic718.json` admits the token
# `cpr_stepper_advance_tic718`). An instance-keyed rationale cannot see its
# sibling routes — so the declaration below is derived from the MECHANISM, not
# from the two known instances.
#
# THE MECHANISM, read directly:
#   * _PROVENANCE_VERB_RE anchors an inscription verb at the comment HEAD, then
#     spans `.*?-->` under DOTALL. ONE head verb therefore licenses EVERY token
#     up to the first `-->`, at any distance, in any grammatical role.
#   * _CPR_REF_RE is `(cpr_[A-Za-z0-9_]+|CogPR-\\d+)` — NO left word boundary, no
#     right boundary beyond the character class, no path/quote/fence exclusion,
#     no polarity reading, and no queue-membership predicate at match time.
# Every consequence of those two facts is an admission route the boundary cannot
# discriminate. They are enumerated here in full.
#
# SCOPE (ratified): the cure is DISCLOSURE PARITY, NOT GATING. Nothing below
# changes what is admitted — the class test over-excludes, and that was
# adjudicated. `machine_countable` marks the routes whose occurrences are
# COUNTED AT RUNTIME (never a frozen number) into route_occurrence_counts; the
# rest are NOT countable BY CONSTRUCTION — a boundary able to count them would
# be able to discriminate them, and it cannot. That asymmetry is itself the
# disclosure.
_ADMISSION_ROUTES_NOT_DISCRIMINABLE = [
    {
        "route": "head_subject_token",
        "intended_witness": True,
        "mechanism": "the first token in the matched comment — normally the id the "
                     "head verb is actually about. This is the ONLY route where a "
                     "token approximates an inscription EVENT.",
        "machine_countable": True,
        "counter": "head_subject_token",
    },
    {
        "route": "sibling_id_narrated_in_provenance_prose",
        "mechanism": "the head verb's `.*?-->` span licenses every later token, so a "
                     "sibling id merely NARRATED in the body ('extended by CogPR-87', "
                     "'refined from A + B', 'Source: cpr_other') is admitted with the "
                     "same weight as the head subject.",
        "machine_countable": "partially — every non-first occurrence is counted as "
                             "body_scope_token, but body-scope is a superset: the "
                             "narrating/naming distinction is semantic, not structural",
        "counter": "body_scope_token",
    },
    {
        "route": "cpr_shaped_substring_of_a_cited_FILENAME_or_PATH",
        "mechanism": "_CPR_REF_RE has no left word boundary and no path/quote "
                     "exclusion, so a mailbox-envelope filename or artifact path cited "
                     "in the comment donates its embedded cpr-shaped run to the index "
                     "(`Source: DONE_cpr_stepper_advance_tic718.json`). THE TIC-721 "
                     "ROUTE — the one the pre-724 rationale did not cover.",
        "machine_countable": True,
        "counter": "substring_of_cited_filename_or_path",
    },
    {
        "route": "cpr_shaped_substring_of_ANY_longer_identifier",
        "mechanism": "the same missing left boundary admits an embedded run from any "
                     "longer identifier, not only paths — an entity/actor name "
                     "(`ent_cpr_stepper` admits `cpr_stepper`), a prefixed slug, a "
                     "concatenated token. The admitted string need not be any real "
                     "CogPR id. Generalization of the filename route.",
        "machine_countable": True,
        "counter": "substring_of_longer_identifier",
    },
    {
        "route": "greedy_right_extension_past_the_real_id",
        "mechanism": "`[A-Za-z0-9_]+` is greedy and stops only at a character outside "
                     "the class, so an id embedded in an underscore-joined compound is "
                     "admitted AS THE COMPOUND — a token that exists nowhere as an id. "
                     "Counted only for tokens outside the queue namespace that strictly "
                     "extend a queue id at an underscore.",
        "machine_countable": True,
        "counter": "greedy_right_extension",
    },
    {
        "route": "bare_CogPR_N_numeric_form",
        "mechanism": "`CogPR-\\d+` matches anywhere in the comment, including pure "
                     "cross-references ('Refinement of … (CogPR-118)', "
                     "'Non-derivability vs CogPR-100 adjudicated'). It also truncates a "
                     "slash-compound to its first element (`CogPR-170/171/172/173` "
                     "admits only CogPR-170) — the same boundary that over-admits here "
                     "UNDER-admits there.",
        "machine_countable": True,
        "counter": "cogpr_numeric_form",
    },
    {
        "route": "contrastive_negated_or_superseding_mention",
        "mechanism": "the boundary reads no POLARITY. An id named in order to be "
                     "excluded, superseded, contrasted, or ruled non-duplicative "
                     "('Supersedes CogPR-14', 'Sibling cited, not re-opened: cpr_X', "
                     "'theme-adjacent (NOT duplicate) to cpr_Y') is admitted identically "
                     "to one named as inscribed.",
        "machine_countable": False,
        "counter": None,
    },
    {
        "route": "illustrative_or_documentary_occurrence",
        "mechanism": "the scan has no fence/quote/example awareness anywhere, and the "
                     "scanned set includes SKILL.md / AUTHORING_CONVENTION.md / "
                     "CLAUDE.md / ledger.md / auto-memory *.md — surfaces that DOCUMENT "
                     "the breadcrumb format. A provenance-shaped comment inside an "
                     "example, template, fenced block, or quoted snippet is "
                     "structurally identical to a real breadcrumb.",
        "machine_countable": False,
        "counter": None,
    },
    {
        "route": "token_outside_the_queue_id_namespace",
        "mechanism": "queue membership is NOT an admission predicate — an id-shaped "
                     "token that resolves to no queue id is admitted by design (legacy "
                     "inscriptions predate full queue coverage; dropping them would flip "
                     "historical checks) and disclosed via unresolved_against_queue_*. "
                     "Named here because it is an admission route, not a discrimination.",
        "machine_countable": True,
        "counter": "unresolved_against_queue (see inscribed_index_unresolved)",
    },
    {
        "route": "population_is_not_content_deduplicated",
        "mechanism": "the token SET dedups, the declared POPULATION does not: a "
                     "breadcrumb repeated within or across scanned surfaces increments "
                     "matched_comment_count once per occurrence while contributing its "
                     "tokens once. The two declared numbers are therefore NOT in a fixed "
                     "ratio, and a delta in one does not entail a delta in the other.",
        "machine_countable": False,
        "counter": None,
    },
]

# Enumerated prose form of the same disclosure, carried in boundary_rule so a
# consumer reading only the string still sees every route.
_BOUNDARY_RULE = (
    "ADMIT: any cpr_/CogPR-shaped token ANYWHERE inside a comment whose HEAD matches "
    "_PROVENANCE_VERB_RE, up to that comment's first `-->`. EXCLUDE: reserved "
    "sibling-namespace prefixes (disclosed separately). The boundary CANNOT "
    "discriminate these admission routes — enumerated from the mechanism "
    "(_PROVENANCE_VERB_RE head-anchored + `.*?-->` DOTALL span; _CPR_REF_RE with no "
    "left word boundary, no path/quote/fence exclusion, no polarity, no queue "
    "predicate), NOT from the known instances: "
    "(a) head-subject token — the only route where token ~ inscription event; "
    "(b) sibling id NARRATED in the body prose, licensed by the head verb; "
    "(c) cpr-shaped SUBSTRING OF A CITED FILENAME/PATH — the tic-721 route "
    "(`Source: DONE_cpr_stepper_advance_tic718.json` admits "
    "`cpr_stepper_advance_tic718`), which the pre-724 sibling-narration rationale "
    "did not cover; "
    "(d) cpr-shaped substring of ANY longer identifier (entity/actor names such as "
    "`ent_cpr_stepper` -> `cpr_stepper`) — the admitted string need not be a real id; "
    "(e) greedy RIGHT extension past the real id into an underscore-joined compound; "
    "(f) bare `CogPR-N` numeric form, including pure cross-references, and its mirror "
    "defect of truncating slash-compounds to the first element; "
    "(g) contrastive / negated / superseding mentions — no polarity is read, so an id "
    "named to be EXCLUDED is admitted as a witness; "
    "(h) illustrative / documentary occurrences — no fence, quote, or example "
    "awareness on surfaces that document the breadcrumb format; "
    "(i) tokens outside the queue id namespace — admitted by design, disclosed; "
    "(j) the population (matched comments) is not content-deduplicated while the unit "
    "(distinct tokens) is, so the two are not in a fixed ratio. "
    "SCOPE: this is DISCLOSURE PARITY, not gating — the admission mechanism is "
    "unchanged (the class test over-excludes; adjudicated /review 724)."
)


def _enclosing_pathish_run(text, start, end):
    """Return the maximal filename/path-shaped run containing [start, end), else None.

    Route-census helper (/review 724 RIDER 1). Expands left and right over the
    path character class and reports the run only when it is STRICTLY LARGER than
    the token and looks like a path (contains `/`) or a filename (ends in a dotted
    extension). This is what separates the tic-721 filename route
    (`DONE_cpr_stepper_advance_tic718.json`) from the plain longer-identifier
    route (`ent_cpr_stepper`). Disclosure only — never gates admission.
    """
    i = start
    while i > 0 and (text[i - 1].isalnum() or text[i - 1] in "_./~-"):
        i -= 1
    j = end
    while j < len(text) and (text[j].isalnum() or text[j] in "_./~-"):
        j += 1
    run = text[i:j]
    if run == text[start:end]:
        return None
    trimmed = run.rstrip(".,;:")
    if "/" in run or re.search(r"\.[A-Za-z0-9]+$", trimmed):
        return run
    return None


# Backwards-compat alias retained for downstream callers; not used internally.
_PROVENANCE_RE = _PROVENANCE_VERB_RE


def build_inscribed_index(project_dir, queue_ids=None, diagnostics=None):
    """Scan governance files for `<!-- promoted from <id>` markers.

    Returns set of CPR ids that have provenance comments anywhere in the
    federation governance surface. Used by check_promoted as the strongest
    verification axis — surviving the comment is sufficient evidence of
    inscription, regardless of whether the queue entry's `promoted_to` field
    points at the correct file.

    Membership resolution (/review 709, f94b63ce931d): a candidate ref is
    admitted only by resolving against the id namespace this index claims to
    measure. Reserved sibling-prefix tokens (_RESERVED_REF_PREFIXES) are
    EXCLUDED and reported via `diagnostics`; when `queue_ids` is provided,
    id-shaped tokens that fail queue membership are still admitted (legacy
    inscriptions predate the queue's full coverage — dropping them would flip
    historical checks) but DISCLOSED as unresolved-against-queue, so the
    counter's referent is measured rather than assumed.

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

    reserved_excluded = {}
    unresolved_against_queue = set()
    matched_comment_count = 0
    multi_token_comment_count = 0
    unmatched_shaped_count = 0
    unmatched_shaped_samples = []
    unmatched_remedy_counts = {}
    # Route census (/review 724 RIDER 1 — disclosure parity). Counts TOKEN
    # OCCURRENCES inside matched comments, not distinct tokens (the index unit),
    # and is computed at runtime so the disclosure can never rot into a frozen
    # claim. head_subject_token + body_scope_token PARTITION the occurrence
    # total; the remaining counters are OVERLAPPING attributes of the same
    # occurrences. Purely observational — no counter gates admission.
    route_counts = {
        "head_subject_token": 0,
        "body_scope_token": 0,
        "substring_of_longer_identifier": 0,
        "substring_of_cited_filename_or_path": 0,
        "greedy_right_extension": 0,
        "cogpr_numeric_form": 0,
    }
    substring_route_samples = []
    for path in candidate_paths:
        content = read_file_safe(path)
        if not content:
            continue
        rel_path = (os.path.relpath(path, project_dir)
                    if path.startswith(project_dir) else path)
        # Two-pass: find each provenance HTML-comment block, then extract every
        # cpr_xxx / CogPR-N ref inside it. The compound case ("refined from A + B")
        # surfaces both refs from a single comment.
        for m in _PROVENANCE_VERB_RE.finditer(content):
            matched_comment_count += 1
            seg = m.group(0)
            distinct_in_comment = set()
            seen_any_in_comment = False
            for ref_match in _CPR_REF_RE.finditer(seg):
                token = ref_match.group(1)
                if _is_reserved_ref(token):
                    reserved_excluded.setdefault(token, set()).add(rel_path)
                    continue
                if queue_ids is not None and token not in queue_ids:
                    unresolved_against_queue.add(token)
                inscribed.add(token)
                distinct_in_comment.add(token)
                # --- route census for this occurrence (disclosure only) ---
                if seen_any_in_comment:
                    route_counts["body_scope_token"] += 1
                else:
                    route_counts["head_subject_token"] += 1
                    seen_any_in_comment = True
                if token.startswith("CogPR-"):
                    route_counts["cogpr_numeric_form"] += 1
                t_start, t_end = ref_match.span(1)
                left = seg[t_start - 1] if t_start > 0 else ""
                if left and (left.isalnum() or left == "_"):
                    route_counts["substring_of_longer_identifier"] += 1
                    enclosing = _enclosing_pathish_run(seg, t_start, t_end)
                    if enclosing:
                        route_counts["substring_of_cited_filename_or_path"] += 1
                    if len(substring_route_samples) < 10:
                        substring_route_samples.append({
                            "path": rel_path,
                            "admitted_token": token,
                            "enclosing_identifier": enclosing,
                            "route": ("cpr_shaped_substring_of_a_cited_FILENAME_or_PATH"
                                      if enclosing else
                                      "cpr_shaped_substring_of_ANY_longer_identifier"),
                            "context": " ".join(
                                seg[max(0, t_start - 70):t_end + 30].split())[:180],
                        })
                if queue_ids and token not in queue_ids and any(
                        token.startswith(q + "_") for q in queue_ids):
                    route_counts["greedy_right_extension"] += 1
            if len(distinct_in_comment) > 1:
                multi_token_comment_count += 1
        # Unmatched-provenance-shape loud counter (/review 719, 3a40ab346adb):
        # a cpr-token-bearing comment that fails the verb alternation is exactly
        # the shape that silently dropped out of the index while the inscription
        # stayed valid (measured live at tic 716: PROMOTE-AS-REFINEMENT, delta
        # read 0 against a landed inscription). Counted + sampled, never gating;
        # SKIP-* heads excluded by design; reserved-only comments not counted.
        for cm in _HTML_COMMENT_RE.finditer(content):
            seg = cm.group(0)
            if _PROVENANCE_VERB_RE.match(seg) or _SKIP_HEAD_RE.match(seg):
                continue
            tokens = [t.group(1) for t in _CPR_REF_RE.finditer(seg)
                      if not _is_reserved_ref(t.group(1))]
            if not tokens:
                continue
            unmatched_shaped_count += 1
            remedy_class = _classify_unmatched_remedy(seg)
            unmatched_remedy_counts[remedy_class] = (
                unmatched_remedy_counts.get(remedy_class, 0) + 1)
            if len(unmatched_shaped_samples) < 10:
                unmatched_shaped_samples.append({
                    "path": (os.path.relpath(path, project_dir)
                             if path.startswith(project_dir) else path),
                    "head": " ".join(seg[:120].split()),
                    "tokens": sorted(set(tokens))[:5],
                    "remedy_class": remedy_class,
                })
    if unmatched_shaped_count:
        per_class = ", ".join(
            f"{cls}={n}" for cls, n in sorted(unmatched_remedy_counts.items()))
        print(
            f"UNMATCHED-PROVENANCE-SHAPE: {unmatched_shaped_count} cpr-token-"
            f"bearing comment(s) fail the inscription-verb alternation and are "
            f"NOT indexed (skip-heads excluded by design). Typed per remedy "
            f"class ({per_class}) — each class has a DIFFERENT reachable cure "
            f"(wrong_object_class: exclusion; head_anchor_gap: head-anchor "
            f"relaxation, build lane; vocabulary_gap: verb registration). See "
            f"inscribed_index_unresolved.unmatched_remedy_class_counts.",
            file=sys.stderr,
        )
    if diagnostics is not None:
        diagnostics["reserved_tokens_excluded"] = {
            tok: sorted(paths) for tok, paths in sorted(reserved_excluded.items())
        }
        diagnostics["reserved_excluded_count"] = len(reserved_excluded)
        diagnostics["unresolved_against_queue_count"] = len(unresolved_against_queue)
        diagnostics["unresolved_against_queue_sample"] = sorted(unresolved_against_queue)[:25]
        # /review-719 loud counter (3a40ab346adb): the residue an anchored
        # closed alternation sheds from an open authoring vocabulary, made
        # visible beside the index it was invisible to. Non-gating.
        diagnostics["unmatched_provenance_shaped_count"] = unmatched_shaped_count
        diagnostics["unmatched_provenance_shaped_samples"] = unmatched_shaped_samples
        # /review-736 remedy-class typing (955e9009a2da): per-class counts +
        # the per-class REACHABLE remedy beside the integer, so the disclosure
        # frame can never again prescribe one cure over opposite classes.
        diagnostics["unmatched_remedy_class_counts"] = dict(
            sorted(unmatched_remedy_counts.items()))
        diagnostics["unmatched_remedy_class_remedies"] = _UNMATCHED_REMEDY_TEXT
        # Class-cure (/review 716, 502236e96cf1 SKIP-with-routing, executed
        # same tic): the counter's POPULATION and UNIT are declared as fields
        # BESIDE the integer, so a consumer predicting against it must predict
        # in the counter's own unit. The tic-706 reserved-prefix exclusion was
        # an instance-cure (one token family removed from a counter whose unit
        # stayed undeclared); this is the class-cure the guard-11 refinement
        # ray (/review 712) entails: every multi-unit disclosure publishes a
        # declared population per named unit and a declared boundary rule.
        # RIDER 1 (/review 724, cgg-ledger#instance-keyed-cures-cannot-see-
        # sibling-routes-disclosure-parity): boundary_rule now enumerates EVERY
        # admission route the boundary cannot discriminate — derived from the
        # mechanism, not from the two known instances — and the structurally
        # countable ones are MEASURED at runtime beside it. Disclosure parity,
        # not gating: admission is byte-for-byte unchanged.
        diagnostics["unit_declaration"] = {
            "unit": "distinct_cpr_shaped_tokens_inside_matched_provenance_comments",
            "population": "provenance HTML-comments matched by _PROVENANCE_VERB_RE across the scanned surfaces declared in build_inscribed_index's docstring",
            "boundary_rule": _BOUNDARY_RULE,
            "admission_routes_not_discriminable": _ADMISSION_ROUTES_NOT_DISCRIMINABLE,
            "route_occurrence_counts": route_counts,
            "route_counting_unit": (
                "TOKEN OCCURRENCES inside matched provenance comments — NOT the "
                "index unit (distinct tokens). head_subject_token + "
                "body_scope_token partition the occurrence total; the remaining "
                "counters are overlapping attributes of the same occurrences and "
                "do not sum to it. Routes marked machine_countable:false in "
                "admission_routes_not_discriminable are absent here BY "
                "CONSTRUCTION — a boundary that could count them could "
                "discriminate them."
            ),
            "substring_route_samples": substring_route_samples,
            "not_the_unit": "inscription EVENTS — the strictly-narrower referent an observer may assume; predictions against this counter are lawful only in the token unit",
            "matched_comment_count": matched_comment_count,
            "multi_token_comment_count": multi_token_comment_count,
        }
    return inscribed


def check_deferred(cpr_id, cpr):
    """Verify deferred CPR has updated review_tic.

    Accepts either key variant: review_tic (script writers) or reviewed_tic
    (hand-authored /review writebacks, e.g. tic500-pass1) — both carry the
    same review provenance (schema key signature drift, conductor-score-runtime
    parity mechanism class 3).

    Path discrimination (tic 628, Verifier-Split Chapter 3): enrichment_eligible
    is reachable by TWO lifecycle paths. Before demanding review provenance, the
    row's own fields are read as path evidence — enrichment-lineage fields present
    + review-writeback fields absent means the row was advanced by the pipeline
    and is AWAITING its first review (legitimately provenance-free). Such a
    finding is emitted (surface-don't-hide) but classified KNOWN with reason
    pipeline_advanced_never_reviewed, severity info — never a hazard. A row with
    review-writeback fields present but review_tic/reviewed_tic missing is a
    GENUINE provenance inconsistency (a review touched it and left no tic).
    """
    findings = []

    review_tic = cpr.get("review_tic", cpr.get("reviewed_tic"))
    if review_tic is None:
        review_fields = sorted(set(cpr) & _REVIEW_WRITEBACK_FIELDS)
        lineage_fields = sorted(set(cpr) & _ENRICHMENT_LINEAGE_FIELDS)
        finding = {
            "type": "deferred_no_review_tic",
            "severity": "warning",
            "cpr_id": cpr_id,
            "message": f"{cpr_id} deferred but review_tic/reviewed_tic not set",
        }
        if lineage_fields and not review_fields:
            finding["finding_class"] = "known"
            finding["reason"] = REASON_PIPELINE_ADVANCED
            finding["severity"] = "info"
            finding["evidence"] = {
                "enrichment_lineage_fields": lineage_fields,
                "review_writeback_fields": [],
                "note": "row reached enrichment_eligible via ordinary pipeline "
                        "advancement (in-row path evidence: enrichment-lineage "
                        "fields present, review-writeback fields absent) — "
                        "awaiting-first-review, legitimately provenance-free",
            }
        else:
            finding["finding_class"] = "genuine"
            finding["evidence"] = {
                "enrichment_lineage_fields": lineage_fields,
                "review_writeback_fields": review_fields,
                "note": "review-writeback fields present without review_tic/"
                        "reviewed_tic (a review touched the row and left no tic), "
                        "or no path evidence at all — genuine provenance gap",
            }
        findings.append(finding)

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
    """True if a resolved path is a code/behavioral surface — a source file, a
    SKILL.md, or an agent-definition spec (`agents/*.md`) whose promotion lands as
    behavior, not quotable text.

    An agent spec under an `agents/` directory is the same behavioral class as
    SKILL.md: a promotion to it inscribes routing/behavior metadata (e.g. a
    `landing_kind` field on cpr-stepper.md), not quotable doctrine prose — so a
    content-matching verifier can never confirm it by literal-text search. Verified
    instead via target existence + cpr_id git lineage (the behavioral axis).
    (bk-review-close-anchor-presence-check case 2, /review 409.)
    """
    base = os.path.basename(path)
    if base == "SKILL.md":
        return True
    norm = path.replace("\\", "/")
    if base.endswith(".md") and "/agents/" in norm:
        return True
    return os.path.splitext(base)[1].lower() in _CODE_SUFFIXES


def _extract_path_anchor(target_str):
    """Return the heading-anchor component of a `.md` target (the text after '#'),
    or None.

    Only markdown heading anchors qualify — line-range suffixes (`:N-M`) and YAML
    key-path anchors (`file.yaml#a.b.c`) are NOT heading anchors and return None.
    The bare path must end in `.md` for the anchor-presence axis to apply.
    """
    bare = _strip_scope_hint(target_str).strip()
    m = re.match(r"^([^#:\s]+\.md)#([^\s]+)$", bare, re.IGNORECASE)
    if m:
        return m.group(2)
    return None


def _slugify_heading(text):
    """GitHub-style heading slug: lowercase, drop non-word/space/hyphen chars,
    collapse whitespace to single hyphens. Used as the FALLBACK anchor-match when a
    file carries no explicit `<a id>` tag."""
    s = text.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s.strip("-")


def _anchor_present_in_markdown(path, anchor):
    """True if `anchor` resolves to a real location in the markdown file at `path`.

    Two signals, exact-first:
      1. Explicit anchor tag — `<a id="ANCHOR">` / `<a name="ANCHOR">`. The doctrine
         ledger emits these under each (rephrasable) heading, so this is the strong
         exact match that survives heading-prose rephrasing.
      2. Heading GitHub-slug — a `#…` heading whose slug equals ANCHOR (fallback for
         markdown surfaces without explicit anchor tags).
    """
    content = read_file_safe(path)
    if not content:
        return False
    target = anchor.strip()
    # 1. explicit <a id="..."> / <a name="..."> tag (exact)
    if re.search(
        r'<a\s+(?:id|name)\s*=\s*["\']' + re.escape(target) + r'["\']',
        content, re.IGNORECASE,
    ):
        return True
    # 2. heading slug fallback
    tl = target.lower()
    for line in content.splitlines():
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if m and _slugify_heading(m.group(1)) == tl:
            return True
    return False


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


# Provenance-anchor memo — classify_known_reason is reachable TWICE for the same
# id (a promoted_text_missing and an orphaned_promotion finding both classify), and
# the full-history pickaxe is the most expensive call in this file. Cleared per
# run_check beside _RECEIPT_INDEX_CACHE.
_PICKAXE_CACHE = {}


def _git_provenance_anchor(project_dir, cpr_id, sample_limit=3):
    """Provenance-trace axis: anchor the cpr_id's committed lineage to its BIRTH
    commit and its full pickaxe depth, with a small newest-first sample.

    Returns {"birth_commit", "total_commits", "recent_sample", "trace_available"}.

    A behavioral inscription leaves NO content-matchable trace in its code target,
    but the cpr_id itself has committed lineage (queue.jsonl writeback, spec files)
    — pickaxe -S confirms the CogPR is a real, committed governance artifact, not a
    phantom id. Combined with an existing code/behavioral target, that is sufficient
    positive evidence the promotion is behavioral-and-landed.

    WHY THIS SHAPE (bk-review-close-provenance-evidence-anchor, authorized /review
    723; cgg-ledger#churn-window-evidence-field-is-a-global-cursor-not-per-subject-
    provenance): the prior implementation emitted `git log --all -S<id>
    --max-count=5` — a NEWEST-FIRST window, so the OLDEST hit (the CogPR's birth /
    inscription commit — the one thing the field's name promises) is the FIRST to
    be evicted. Every /review batch rewrites queue.jsonl rows bearing every cpr_id,
    so under that churn the window converges to a CONSTANT across unrelated
    subjects: measured at tic 719, three findings at pickaxe depths 230 / 277 / 48
    all displayed the byte-identical 5-commit window (the five most recent
    queue.jsonl-touching batch commits) while each subject's real birth commit sat
    evicted and invisible. It rendered as per-subject provenance while carrying zero
    discriminating information — a global churn cursor wearing a per-subject name.
    Raising N only delays eviction; the cure is anchoring. birth_commit and
    total_commits are per-subject and move only on real change.

    SECOND-ORDER, AND INTENTIONAL: unrelated queue.jsonl churn no longer shifts this
    field, so a semantically-identical re-observation no longer differs HERE. That is
    deliberate against run_check's dedup comparison: the /review-685 preservation law
    stops spending durable superseded byte-copies on a pure cursor shift (measured at
    tic 719: the run flipped to decision=replace and minted
    tic-719-check.superseded-1.json whose ONLY real delta across 5 changed findings
    was that cursor). The law is NOT weakened — it still fires on every REAL content
    change; it just stops paying for the cursor.

    SCOPE-HONEST RESIDUE (measured at tic 723 while landing this cure, NOT cured
    here, DIFFERENT owner): the dedup comparison also covers `genuine_zero_streak`,
    which by /review-715 design discloses same-tic re-observations
    (row_count_within_streak / same_tic_reobservation_tics), and the log row it reads
    is appended on EVERY run — including `skip`. So a same-tic re-run still computes
    a content delta from the streak alone and still routes to `replace`; the `skip`
    branch is effectively unreachable for a same-tic re-run. Evidence that this is
    pre-existing and independent of this change:
    tests/review/test_close_check_superseded_receipt_tic686.py::
    test_skip_path_preserves_nothing fails identically (4/5) on the pre-patch HEAD
    script and on this one. Reported upward, never silently absorbed.

    CLAIM SEMANTICS PRESERVED: the verifier claims only that a non-empty trace
    proves the id is a real committed artifact, not a phantom. `total_commits > 0`
    is exactly the old `trace != []` predicate, so the behavioral axis's positive
    evidence is unchanged in strength.

    Fail-soft (trace_available=False) when git is unavailable or the dir is not a
    repo — a git failure must never crash the cycle.
    """
    key = (os.path.abspath(project_dir), cpr_id)
    cached = _PICKAXE_CACHE.get(key)
    if cached is not None:
        return cached
    anchor = {
        "birth_commit": None,
        "total_commits": 0,
        "recent_sample": [],
        "trace_available": False,
    }
    try:
        # ONE full-history pickaxe in CHRONOLOGICAL order — no --max-count, because
        # the truncation window IS the defect. hits[0] is the birth commit,
        # len(hits) the true depth, and the newest-first sample is the tail
        # re-reversed (so the old window's content is still available as context,
        # just demoted from "the evidence" to "a sample").
        out = subprocess.run(
            ["git", "-C", project_dir, "log", "--all", "--reverse",
             "--format=%h", f"-S{cpr_id}"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        _PICKAXE_CACHE[key] = anchor
        return anchor
    if out.returncode != 0:
        _PICKAXE_CACHE[key] = anchor
        return anchor
    hits = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    anchor["trace_available"] = True
    if hits:
        anchor["birth_commit"] = hits[0]
        anchor["total_commits"] = len(hits)
        sample = hits[-sample_limit:] if sample_limit > 0 else []
        anchor["recent_sample"] = list(reversed(sample))
    _PICKAXE_CACHE[key] = anchor
    return anchor


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


# ---------------------------------------------------------------------------
# Widened sweep (tic 593, bk-review-close-check-widen-sweep-tic593)
# Two additive false-positive guards on the genuine-vs-known classifier:
#   (a) receipt/behavioral surface sweep — a promotion operationalized as behavior
#       (cable-receipt / honesty-lock drive_mode note / conformation record) is
#       affirmed even when its lesson prose is absent from the named doctrine target.
#   (b) Evidence-anchor citation — a doctrine/spec target that CITES the born-id on
#       an Evidence/provenance line (often with the extractor-appended `_tic<N>`
#       suffix dropped) has the inscription LANDED; the verbatim-lesson-text match
#       misses a rephrased-on-promotion refinement. Classified anchor_present_text_rephrased.
# ---------------------------------------------------------------------------

_TIC_SUFFIX_RE = re.compile(r"_tic\d+$")


def _strip_tic_suffix(cpr_id):
    """Strip a trailing `_tic<N>` suffix from a cpr id.

    Evidence / receipt surfaces frequently cite the BORN name without the
    extractor-appended tic suffix — the queue id `cpr_x_tic590` appears in a spec's
    Evidence line as `cpr_x`. A full-id substring search misses that citation, so
    both forms must be tried.
    """
    return _TIC_SUFFIX_RE.sub("", cpr_id)


def _born_id_variants(cpr_id):
    """Return the distinct born-id forms to match: the full queue id first (more
    specific) then its tic-suffix-stripped born form."""
    stripped = _strip_tic_suffix(cpr_id)
    variants = [cpr_id]
    if stripped and stripped != cpr_id:
        variants.append(stripped)
    return variants


# An Evidence-anchor citation line: an evidence/provenance marker on the SAME line
# as the born-id, so a bare co-incidental mention elsewhere in the file does not
# qualify. `born` + a long unique cpr slug is itself a strong provenance signal.
_EVIDENCE_MARKER_RE = re.compile(
    r"(?:\bevidence\b|\bborn\b|\bprovenance\b|<!--)", re.IGNORECASE
)


def _evidence_anchor_cites_born(path, cpr_id):
    """Return the matching Evidence-anchor line (stripped) if the markdown file at
    `path` carries an evidence/provenance line citing the born-id (full or
    tic-stripped), else None.

    The inscription landed as a REFINEMENT whose Evidence line names the born rather
    than quoting the lesson verbatim — content-match misses it, but the citation IS
    the landed-proof. Scoped to `.md` doctrine/spec surfaces (the shape that carries
    Evidence-anchor lines).
    """
    if not path.lower().endswith(".md"):
        return None
    content = read_file_safe(path)
    if not content:
        return None
    variants = _born_id_variants(cpr_id)
    for line in content.splitlines():
        if not _EVIDENCE_MARKER_RE.search(line):
            continue
        if any(v in line for v in variants):
            return line.strip()
    return None


def _prose_spec_suffix_normalized_hit(path, cpr_id):
    """Return match evidence if a resolved prose/doctrine spec `.md` cites the born-id in
    suffix-normalized form (full OR `_tic<N>`-stripped), else None.

    Two loci, breadcrumb-first (the stronger provenance signal):
      1. a `<!-- promoted from … -->` / provenance-verb comment carrying the born-id;
      2. the born-id appearing on any body line.

    The born-id is a long unique slug, so its presence — even suffix-stripped — is strong
    positive evidence the inscription landed at this prose spec (identical reasoning to the
    evidence-anchor axis, which already trusts a born-slug citation). This axis is the
    fallback the evidence-anchor axis does NOT cover: a citation on a PLAIN line (no
    Evidence/born/provenance marker) that a full-id content match still misses because the
    spec dropped the `_tic<N>` suffix. Scoped to `.md`; the caller has already excluded
    code/behavioral targets and tried the heading/evidence-anchor forms.
    """
    if not path.lower().endswith(".md"):
        return None
    content = read_file_safe(path)
    if not content:
        return None
    variants = _born_id_variants(cpr_id)
    # 1. provenance-comment / breadcrumb locus (strongest — an intentional stamp)
    for m in _PROVENANCE_VERB_RE.finditer(content):
        seg = m.group(0)
        for v in variants:
            if v in seg:
                return {"locus": "breadcrumb", "matched_form": v,
                        "line": " ".join(seg.split())[:200]}
    # 2. body-line locus (the born-slug cited in prose without a marker)
    for line in content.splitlines():
        for v in variants:
            if v in line:
                return {"locus": "body", "matched_form": v, "line": line.strip()[:200]}
    return None


# Memoized per project_dir — the receipt-surface walk runs once per run_check.
_RECEIPT_INDEX_CACHE = {}


def _receipt_surface_ids(project_dir):
    """Return the set of cpr-id tokens cited anywhere in the bounded behavioral /
    receipt surfaces (_RECEIPT_SURFACE_ROOTS). Tokens are stored AS FOUND (organic),
    never synthetically tic-stripped, so a same-slug born at a different tic cannot
    collide: a match requires either the exact full id or a receipt that organically
    wrote the born form.

    SCOPE DISCIPLINE: only _RECEIPT_SURFACE_ROOTS are swept — never pipeline
    bookkeeping (queue.jsonl, bench-packets, civil/cycle reports, corpus-harvest),
    which name every id and would trivially affirm every promotion.
    """
    key = os.path.abspath(project_dir)
    cached = _RECEIPT_INDEX_CACHE.get(key)
    if cached is not None:
        return cached
    ids = set()
    for root in _RECEIPT_SURFACE_ROOTS:
        root_abs = os.path.join(project_dir, root)
        if not os.path.isdir(root_abs):
            continue
        for dirpath, _dirs, files in os.walk(root_abs):
            for fn in files:
                content = read_file_safe(os.path.join(dirpath, fn))
                if not content:
                    continue
                for match in _CPR_REF_RE.finditer(content):
                    # Membership resolution (/review 709, f94b63ce931d): reserved
                    # sibling-prefix tokens are metadata labels, not ids — the
                    # A5-707 second call site, cured with the first.
                    if _is_reserved_ref(match.group(1)):
                        continue
                    ids.add(match.group(1))
    _RECEIPT_INDEX_CACHE[key] = ids
    return ids


def _affirmed_via_receipts(cpr_id, project_dir):
    """True if the born-id is cited (full id, or its born form written organically)
    in a bounded behavioral/receipt surface."""
    ids = _receipt_surface_ids(project_dir)
    if cpr_id in ids:
        return True
    stripped = _strip_tic_suffix(cpr_id)
    return stripped != cpr_id and stripped in ids


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
         BEHAVIOR not text, strengthened by the git provenance-trace ANCHOR
         ({birth_commit, total_commits, recent_sample} — per-subject and
         churn-stable; /review 723, bk-review-close-provenance-evidence-anchor).
      3. anchor_present_text_rephrased — the resolved doctrine/spec target either
         (i) names a heading anchor that EXISTS (explicit <a id>/<a name> or a
         matching heading slug), or (ii) CITES the born-id on an Evidence/provenance
         line (tic suffix often dropped). The inscription landed as a rephrased
         refinement content-match cannot see. (tic 593 added the evidence-anchor half.)
      4. prose_spec_suffix_normalized_present — a born promoted INTO a prose/doctrine
         spec (not auto-memory, not a ledger anchor) that cites the born-id with the
         `_tic<N>` suffix STRIPPED, in a breadcrumb or on a plain body line the
         evidence-anchor axis (3-ii) does not cover. Verified present under suffix
         normalization. The read-side complement to the emit-side prose-spec breadcrumb
         stamp (review-promote-writeback). (bk-review-close-check-prose-spec-breadcrumb, tic 620.)
      5. affirmed_via_receipts — the born-id is cited in a bounded behavioral/receipt
         surface (cable-receipt / honesty-lock drive_mode note / conformation record);
         the promotion is operationalized as behavior, not doctrine prose. (tic 593.)
      6. (none) GENUINE — no code/behavioral target, no relocation, no present anchor,
         no prose-spec citation, and no affirming receipt surface; genuinely missing.
    """
    targets = _collect_targets(cpr)
    lesson = cpr.get("lesson", "")
    if not lesson and lesson_fallbacks:
        lesson = lesson_fallbacks.get(cpr_id, "")
    snippet = lesson[:50] if lesson else ""

    relocated = None
    behavioral = None
    anchor_present = None
    prose_spec = None
    resolved_any = False
    targets_unresolved = []
    for t in targets:
        existing = _resolve_target_path(t, project_dir, project_basename)
        if existing is not None:
            resolved_any = True
        if existing is None:
            targets_unresolved.append(t)
            if relocated is None:
                hit = _find_relocated(t, project_dir, cpr_id, snippet)
                if hit:
                    relocated = (t, hit)
        elif behavioral is None and _is_codeish_path(existing):
            behavioral = (t, existing)
        elif anchor_present is None:
            # (b-i) heading-anchor form: promoted_to names a `#anchor` present in the md
            anchor = _extract_path_anchor(t)
            if anchor and _anchor_present_in_markdown(existing, anchor):
                anchor_present = (t, existing, anchor, None)
            else:
                # (b-ii) evidence-anchor form: the resolved doctrine/spec target CITES
                # the born-id on an Evidence/provenance line (tic suffix often dropped).
                ev_line = _evidence_anchor_cites_born(existing, cpr_id)
                if ev_line:
                    anchor_present = (t, existing, None, ev_line)
                elif prose_spec is None:
                    # (c) prose-spec suffix-normalized form: the born-id (full OR
                    # `_tic<N>`-stripped) is present in a resolved prose/doctrine spec .md —
                    # in a `<!-- promoted from … -->` breadcrumb or on a plain body line —
                    # WITHOUT a same-line Evidence marker. The inscription landed in a prose
                    # spec that references the born rather than quoting the rephrased lesson.
                    ps_hit = _prose_spec_suffix_normalized_hit(existing, cpr_id)
                    if ps_hit:
                        prose_spec = (t, existing, ps_hit)

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
        # ANCHORED provenance evidence (bk-review-close-provenance-evidence-anchor,
        # /review 723): {birth_commit, total_commits, recent_sample} — per-subject
        # and churn-stable, never a bare newest-first --max-count window (which was
        # a global churn cursor: byte-identical across depths 230/277/48 at tic 719).
        trace = _git_provenance_anchor(project_dir, cpr_id)
        return REASON_BEHAVIORAL, {
            "behavioral_target": orig,
            "resolved_path": resolved,
            "provenance_trace_commits": trace,
            "note": "inscription is a code behavior, not quotable text; verified "
                    "via target existence + cpr_id git lineage (pickaxe -S). The "
                    "trace is ANCHORED to the id's BIRTH commit plus its full "
                    "pickaxe depth — total_commits > 0 is the non-phantom proof "
                    "(the same predicate the pre-723 non-empty list carried); "
                    "recent_sample is context only, never the evidence.",
        }

    if anchor_present is not None:
        orig, resolved, heading_anchor, evidence_line = anchor_present
        try:
            resolved_rel = os.path.relpath(resolved, project_dir)
        except ValueError:
            resolved_rel = resolved
        evidence = {
            "anchored_target": orig,
            "resolved_path": resolved_rel,
        }
        if heading_anchor is not None:
            evidence["anchor"] = heading_anchor
            evidence["note"] = (
                "promoted_to names a heading anchor that EXISTS at the resolved "
                "doctrine surface (explicit <a id>/<a name> tag or matching heading "
                "slug); the inscription landed at the named anchor — the verbatim-"
                "lesson-text match misses a rephrased-on-promotion refinement"
            )
        else:
            evidence["evidence_anchor_line"] = evidence_line
            evidence["note"] = (
                "resolved doctrine/spec surface carries an Evidence-anchor line that "
                "CITES the born-id (tic suffix often dropped); the inscription landed "
                "as a refinement whose provenance line names the born rather than "
                "quoting the lesson verbatim — the citation is the landed-proof"
            )
        return REASON_ANCHOR_PRESENT, evidence

    if prose_spec is not None:
        orig, resolved, ps_hit = prose_spec
        try:
            resolved_rel = os.path.relpath(resolved, project_dir)
        except ValueError:
            resolved_rel = resolved
        return REASON_PROSE_SPEC_SUFFIX_NORMALIZED, {
            "prose_spec_target": orig,
            "resolved_path": resolved_rel,
            "match_locus": ps_hit["locus"],
            "matched_born_form": ps_hit["matched_form"],
            "matched_line": ps_hit["line"],
            "note": "born is promoted INTO a prose/doctrine spec (not auto-memory / not a "
                    "ledger anchor); the spec cites the born-id with the extractor `_tic<N>` "
                    "suffix dropped, so the full-id content match misses. Verified present "
                    "under suffix normalization (born-id is a long unique slug) — KNOWN, not "
                    "blanket-suppressed. The emit-side fix (review-promote-writeback prose-spec "
                    "breadcrumb) makes FUTURE promotions resolve by direct content match.",
        }

    # (a) behavioral/receipt-surface sweep — last positive axis before GENUINE: the
    # promotion is operationalized as behavior (cable-receipt / honesty-lock drive_mode
    # note / conformation record) even though the doctrine-target content-match missed.
    if _affirmed_via_receipts(cpr_id, project_dir):
        return REASON_AFFIRMED_VIA_RECEIPTS, {
            "affirming_surfaces": list(_RECEIPT_SURFACE_ROOTS),
            "note": "born-id is cited in a bounded behavioral/receipt surface "
                    "(cable-receipt / honesty-lock drive_mode note / conformation "
                    "record); the promotion is operationalized as behavior, not as "
                    "quotable doctrine prose at the named target",
        }

    # Resolution-layer disclosure (Verifier-Split Ch.4 claim A, tic 684): the
    # resolution layer sits BENEATH every classification axis, so when NO target
    # resolves, content verification never ran — grading that "genuinely missing"
    # asserted positive knowledge from an absent input. The finding STAYS genuine
    # (a broken pointer is never a known non-hazard; surface-don't-hide), but the
    # evidence discloses the resolution-layer miss loudly instead of silently.
    if targets and not resolved_any:
        return None, {
            "resolution_layer_miss": True,
            "targets_unresolved": targets_unresolved[:5],
            "note": "NO target resolved to any filesystem surface — content "
                    "verification never ran. This is a resolution-layer failure "
                    "(broken/malformed pointer), surfaced loudly as its own "
                    "shape; it is NOT a verified-missing inscription. Still "
                    "GENUINE: either the pointer is broken or the inscription "
                    "is missing — both need attention.",
        }
    return None, {
        "note": "no code/behavioral target, no relocation, no present anchor, and no "
                "affirming receipt surface found; inscription appears genuinely missing",
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


def resolve_obligation_clock(al_path, obligation_tic=None, obligation_mandate_id=None):
    """Resolve the artifact-naming clock — the OBLIGATION's tic, not the executor's
    (bk-review-close-check-obligation-clock-naming, /review-687 ratified ray on
    cgg-ledger#even-tic-review-close-routing-review-step-8-5-discipline).

    The consistency artifact must file under the tic of the mandate that DISPATCHED
    this review_close_check cycle. Reading current.json at write time is the
    EXECUTOR clock: when a run crosses a tic boundary (cadence supersedes
    current.json mid-flight), it files tic-N evidence under tic-{N+1}-check.json
    and tic-N reads never-checked at count=1. NEVER per-mandate filenames (that
    re-opens the N!=1 artifact-cardinality family); the N=1-per-tic canonical
    identity stands — this only fixes WHICH tic names the artifact.

    Precedence:
      1. explicit CLI (--obligation-tic / --obligation-mandate-id) — invocation authority
      2. CGG_OBLIGATION_TIC / CGG_OBLIGATION_MANDATE_ID env — pinned by
         mogul-runner.sh at mandate-snapshot time and inherited by the agent's
         subprocesses; immune to a mid-run supersede of current.json
      3. current.json (executor clock) — correct only while no boundary was crossed

    A malformed env tic fails soft (channel treated absent — the cycle must never
    crash on a bad pin). Returns (mandate_id, tic, source) with source in
    {"cli", "env", "executor_clock"}.
    """
    if obligation_tic is not None or obligation_mandate_id:
        return (obligation_mandate_id, obligation_tic, "cli")
    env_tic_raw = os.environ.get("CGG_OBLIGATION_TIC")
    env_mid = os.environ.get("CGG_OBLIGATION_MANDATE_ID") or None
    env_tic = None
    if env_tic_raw:
        try:
            env_tic = int(env_tic_raw)
        except ValueError:
            env_tic = None
    if env_tic is not None or env_mid:
        if env_tic is not None:
            return (env_mid, env_tic, "env")
        # mandate-id-only pin: still the obligation channel (mandate-keyed naming)
        return (env_mid, None, "env")
    mid, tic = load_mandate_id(al_path)
    return (mid, tic, "executor_clock")


def compute_genuine_zero_streak(log_path, current_tic, current_genuine_count):
    """Mechanized genuine-zero streak (/review 709, ad00d4c652c8).

    UNIT — declared AND counted: DISTINCT CHECK-BEARING TICS whose every log
    row has genuine_count == 0, walking backward from the current entry's tic
    to the nearest tic bearing a row with genuine_count > 0. The cure the
    lesson names: the streak is computed by the script that writes the log
    row (no hand-carried number), in exactly its declared unit, with gaps and
    same-tic re-observations DISCLOSED rather than absorbed — an unobserved
    tic is not a passed tic, and a re-observation of an already-passing tic is
    not new evidence about a new boundary.

    Returns a dict embedded in the log row; both arms are first-class: a
    current row with genuine_count > 0 yields streak 0 with the breaking tic
    disclosed.
    """
    by_tic = {}
    p = Path(log_path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = row.get("tic")
            g = row.get("genuine_count")
            if t is None or g is None:
                continue
            by_tic.setdefault(t, []).append(g)
    if current_tic is not None:
        by_tic.setdefault(current_tic, []).append(current_genuine_count)

    result = {
        "unit": "distinct_check_bearing_tics",
        "computed_by": "review-close-check.py:compute_genuine_zero_streak",
        "distinct_check_bearing_tics": 0,
        "row_count_within_streak": 0,
        "span": None,
        "gap_tics_no_check_row": [],
        "same_tic_reobservation_tics": {},
        "broken_at_tic": None,
    }
    if current_tic is None or not by_tic:
        return result
    if current_genuine_count and current_genuine_count > 0:
        result["broken_at_tic"] = current_tic
        return result

    streak_tics = []
    rows_in_streak = 0
    for t in sorted((t for t in by_tic if t <= current_tic), reverse=True):
        counts = by_tic[t]
        if any(g > 0 for g in counts):
            result["broken_at_tic"] = t
            break
        streak_tics.append(t)
        rows_in_streak += len(counts)
    if streak_tics:
        first, last = min(streak_tics), max(streak_tics)
        result["distinct_check_bearing_tics"] = len(streak_tics)
        result["row_count_within_streak"] = rows_in_streak
        result["span"] = [first, last]
        result["gap_tics_no_check_row"] = [
            t for t in range(first, last + 1) if t not in by_tic
        ]
        result["same_tic_reobservation_tics"] = {
            str(t): len(by_tic[t]) for t in streak_tics if len(by_tic[t]) > 1
        }
    return result


# ---------------------------------------------------------------------------
# Per-unit delta (/review 724 RIDER 2 — constitution-ledger streak-claims ray)
# ---------------------------------------------------------------------------

_CHECK_ARTIFACT_TIC_RE = re.compile(r"^tic-(\d+)-check\.json$")


def _canonical_output_filename(mandate_tic, mandate_id, now=None):
    """Compute the canonical check-artifact filename ONCE for the whole run.

    Returns (filename, identity_kind) with identity_kind in {"tic","mandate",
    "timestamp"} so the write path can still emit its identity-degradation
    warnings without recomputing the name. Hoisted out of the write block at
    tic 724 so the per-unit delta can EXCLUDE this run's own artifact from its
    baseline search using the same name the writer will use — one computation,
    two consumers (the /review 715 discipline). Ordering is unchanged:
    tic-keyed > mandate-keyed > timestamp-keyed (T4c ladder).
    """
    if mandate_tic is not None:
        return f"tic-{mandate_tic}-check.json", "tic"
    if mandate_id:
        return f"{mandate_id}-check.json", "mandate"
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H%M%S")
    return f"{ts}-check.json", "timestamp"


def _find_prior_check_artifact(report_dir, current_filename, current_tic):
    """Locate the most recent PRIOR check artifact, or (None, reason).

    Returns (path, selector) where selector names HOW it was chosen — the
    baseline is disclosed, never assumed.

    A same-tic re-observation is the SAME pass re-run, not a new pass, so this
    run's own canonical artifact (current_filename) is EXCLUDED from the search.
    That is what keeps the delta stable across a same-tic re-run: if the run's
    own prior bytes could serve as the baseline, an unchanged re-run would
    compute delta 0/0 where the first run computed +N, manufacture a content
    delta, and break the dedup skip branch the /review-685 preservation law
    depends on. The superseded/ subdirectory is likewise out of scope (it is a
    preservation lane, not a pass series) — the listing is non-recursive.

    Selection: prefer the highest tic-keyed artifact strictly BELOW the current
    tic (the previous pass in the canonical tic series); fall back to newest by
    mtime when no tic-keyed candidate qualifies (mandate-keyed / timestamp-keyed
    identity, or an unresolvable current tic).

    "no baseline" is reported as ONE selector regardless of whether the lane
    directory is absent or merely holds nothing but this run's own artifact.
    Splitting those two states flipped the emitted reason between a first write
    (lane absent) and its same-tic re-run (lane now exists, still no prior pass)
    — a spurious content delta that would route an otherwise-identical re-run to
    `replace` and mint a superseded copy. Same meaning, same string.
    """
    if not os.path.isdir(report_dir):
        return None, "no_prior_pass_artifact"
    try:
        entries = [
            fn for fn in os.listdir(report_dir)
            if fn.endswith("-check.json")
            and fn != current_filename
            and os.path.isfile(os.path.join(report_dir, fn))
        ]
    except OSError:
        return None, "report_dir_unreadable"
    if not entries:
        return None, "no_prior_pass_artifact"

    tic_keyed = []
    for fn in entries:
        m = _CHECK_ARTIFACT_TIC_RE.match(fn)
        if m:
            tic_keyed.append((int(m.group(1)), fn))
    if tic_keyed:
        if current_tic is not None:
            below = [(t, fn) for t, fn in tic_keyed if t < current_tic]
            if below:
                t, fn = max(below)
                return os.path.join(report_dir, fn), f"tic_keyed_prior_tic_{t}"
        else:
            t, fn = max(tic_keyed)
            return os.path.join(report_dir, fn), f"tic_keyed_max_tic_{t}_no_current_tic"
    newest = max(entries, key=lambda fn: os.path.getmtime(os.path.join(report_dir, fn)))
    return os.path.join(report_dir, newest), "newest_by_mtime"


def compute_unit_deltas(report_dir, current_filename, current_tic,
                        current_tokens, current_matched_comments):
    """Per-pass PER-UNIT DELTA for the inscribed-index counter (/review 724 RIDER 2).

    The /review-716 class-cure declared the counter's UNIT beside the integer.
    A declared unit still leaves the consumer hand-projecting movement: the
    counter owes a per-pass DELTA in each of its declared units. This emits:

      delta_tokens             — change in `inscribed_index_size` (DISTINCT
                                 cpr-shaped tokens) vs the previous pass artifact
      delta_matched_comments   — change in the declared POPULATION
                                 (unit_declaration.matched_comment_count)
      units_collapsed_this_pass— True iff the two deltas are EQUAL

    WHY THE COLLAPSE FLAG: when both units move by the same amount, every new
    matched comment carried exactly one new token — the token unit and the
    comment unit are indistinguishable FOR THIS PASS, and an observer reading
    agreement between them would be reading a collapse, not a corroboration.
    Marking it makes agreement-under-collapse legible AS collapse. (Its own
    honest limit: equal deltas are necessary, not sufficient — offsetting
    additions and removals can produce equal deltas without lockstep. The flag
    names a collapse CANDIDATE, and says so.)

    NO FABRICATED ZEROS: with no prior artifact — or a prior artifact that
    predates these fields — the deltas are None and `delta_baseline_absent` is
    True with the reason disclosed. A zero would assert measured no-change from
    an absent measurement.
    """
    block = {
        "unit_tokens": "distinct_cpr_shaped_tokens_inside_matched_provenance_comments",
        "unit_matched_comments": "provenance_comments_matched_by_PROVENANCE_VERB_RE",
        "current_tokens": current_tokens,
        "current_matched_comments": current_matched_comments,
        "delta_tokens": None,
        "delta_matched_comments": None,
        "units_collapsed_this_pass": None,
        "delta_baseline_absent": True,
        "baseline": {
            "artifact": None,
            "selector": None,
            "tokens": None,
            "matched_comments": None,
            "reason_absent": None,
        },
        "note": (
            "per-pass delta in the counter's OWN declared units; the baseline is "
            "the previous PASS artifact — this run's own canonical artifact is "
            "excluded, so a same-tic re-observation re-measures against the same "
            "baseline rather than against itself. units_collapsed_this_pass is a "
            "collapse CANDIDATE (equal deltas are necessary, not sufficient)."
        ),
    }

    if not isinstance(current_tokens, int) or not isinstance(current_matched_comments, int):
        # Nothing measured on this side either — an absent minuend cannot yield
        # a delta. Absent, never zero.
        block["baseline"]["reason_absent"] = "current_pass_units_unmeasured"
        return block

    prior_path, selector = _find_prior_check_artifact(
        report_dir, current_filename, current_tic)
    block["baseline"]["selector"] = selector
    if prior_path is None:
        block["baseline"]["reason_absent"] = selector
        return block

    try:
        prior = json.loads(Path(prior_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        block["baseline"]["reason_absent"] = "prior_artifact_unreadable"
        return block

    # Basename only: the artifact lane is fixed and already named by
    # report_path in the log row; an absolute path here would make the report
    # machine-dependent and would churn the dedup comparison across zones.
    block["baseline"]["artifact"] = os.path.basename(prior_path)

    prior_tokens = prior.get("inscribed_index_size")
    prior_unit = prior.get("inscribed_index_unit") or {}
    prior_comments = prior_unit.get("matched_comment_count")

    if not isinstance(prior_tokens, int) or not isinstance(prior_comments, int):
        # An older-schema artifact carries no baseline for these units. Absent,
        # not zero — the distinction the rider makes load-bearing.
        block["baseline"]["reason_absent"] = "prior_artifact_predates_these_fields"
        block["baseline"]["tokens"] = prior_tokens if isinstance(prior_tokens, int) else None
        block["baseline"]["matched_comments"] = (
            prior_comments if isinstance(prior_comments, int) else None)
        return block

    block["baseline"]["tokens"] = prior_tokens
    block["baseline"]["matched_comments"] = prior_comments
    block["delta_tokens"] = current_tokens - prior_tokens
    block["delta_matched_comments"] = current_matched_comments - prior_comments
    block["units_collapsed_this_pass"] = (
        block["delta_tokens"] == block["delta_matched_comments"])
    block["delta_baseline_absent"] = False
    return block


_VERDICT_COUNT_UNITS = {
    "promoted": "queue_latest_per_id_rows_with_status_promoted",
    "deferred": "queue_latest_per_id_rows_status_deferred_or_enrichment_eligible_with_review_tic",
    "skipped": "queue_latest_per_id_rows_with_status_skipped",
}


def compute_verdict_count_deltas(report_dir, current_filename, current_tic,
                                 current_counts):
    """Per-pass PER-KEY DELTA for the verdict counters (/review 728, c209995ad848).

    The obligation-scope ray: a per-pass delta obligation landed on one counter
    (inscribed_index_size, /review 724 RIDER 2) attaches to EVERY counter on the
    same artifact surface. verdict_counts sat in the same report as bare scalars
    — no unit declaration, no delta — leaving the consumer hand-diffing prior
    artifacts for exactly the movement this report exists to disclose.

    Same discipline as compute_unit_deltas: baseline is the previous PASS
    artifact (this run's own artifact excluded via current_filename); absent or
    older-schema baselines yield None deltas with delta_baseline_absent and the
    reason disclosed — NO FABRICATED ZEROS.
    """
    block = {
        "units": dict(_VERDICT_COUNT_UNITS),
        "current": dict(current_counts),
        "delta": {k: None for k in _VERDICT_COUNT_UNITS},
        "delta_baseline_absent": True,
        "baseline": {
            "artifact": None,
            "selector": None,
            "counts": None,
            "reason_absent": None,
        },
        "note": (
            "per-pass delta for each verdict counter; baseline is the previous "
            "PASS artifact, this run's own canonical artifact excluded. The "
            "counters are whole-universe cumulative totals over queue "
            "latest-per-id state, so a per-pass delta reads as this pass's "
            "verdict movement plus any out-of-band queue state change."
        ),
    }

    if not all(isinstance(current_counts.get(k), int) for k in _VERDICT_COUNT_UNITS):
        block["baseline"]["reason_absent"] = "current_pass_counts_unmeasured"
        return block

    prior_path, selector = _find_prior_check_artifact(
        report_dir, current_filename, current_tic)
    block["baseline"]["selector"] = selector
    if prior_path is None:
        block["baseline"]["reason_absent"] = selector
        return block

    try:
        prior = json.loads(Path(prior_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        block["baseline"]["reason_absent"] = "prior_artifact_unreadable"
        return block

    block["baseline"]["artifact"] = os.path.basename(prior_path)

    prior_counts = prior.get("verdict_counts")
    if not isinstance(prior_counts, dict) or not all(
            isinstance(prior_counts.get(k), int) for k in _VERDICT_COUNT_UNITS):
        block["baseline"]["reason_absent"] = "prior_artifact_predates_these_fields"
        block["baseline"]["counts"] = prior_counts if isinstance(prior_counts, dict) else None
        return block

    block["baseline"]["counts"] = {k: prior_counts[k] for k in _VERDICT_COUNT_UNITS}
    block["delta"] = {
        k: current_counts[k] - prior_counts[k] for k in _VERDICT_COUNT_UNITS}
    block["delta_baseline_absent"] = False
    return block


def compute_cross_counter_disclosure(verdict_delta_block, index_delta_block):
    """Derived cross-counter DISCLOSURE (/review 728, c209995ad848) — a typed
    question, NEVER an asserted invariant.

    Two independently derived counters can agree on a /review pass's PROMOTE
    count: verdict_counts.promoted delta (queue-side) and inscribed_index_size
    delta_tokens (doctrine-surface-side). Nothing in the artifact compared
    them; each /review recomputed the agreement by hand. This field emits the
    comparison with its known divergence routes named — divergence is a
    DISCLOSED question for the reader, not a finding and not a failure:
      - a MODIFY-and-merge promotion into an existing anchor adds no new
        provenance comment (promoted moves, tokens do not);
      - a doctrine-surface edit narrating a sibling id adds a token with no
        promotion behind it (tokens move, promoted does not);
      - the t724 over-admission route (receipt filenames carrying cpr-shaped
        tokens) inflates delta_tokens until the disposition-split patch lands
        (bk-close-check-counter-disposition-split).

    AUTHORING-SIDE RULE (the reading-side note above governs how this field is
    READ; this governs how a prediction about it is BANKED — promoted here from
    cpr_cross_counter_prediction_computed_in_target_units_not_sibling_delta_b730,
    /review 733, Architect-ratified): a falsifiable prediction banked against
    one counter must be COMPUTED in that counter's own declared units over the
    content that will actually be written — never DERIVED from the sibling
    counter's expected delta. Before banking a cross-counter prediction at a
    /review close, COUNT the cpr-shaped tokens in the planned inscription
    content (promotion ids + evidence citations + receipt filenames quoted in
    doctrine prose) and bank the token-side number from that count. The t729
    close banked "+1/+1" by deriving tokens from verdicts; the planned
    inscription carried TWO cpr-shaped tokens (the id AND a receipt filename)
    and the t730 fire read +1/+2. Evidence-citation discipline makes this MORE
    likely to recur: the richer an inscription's same-tic evidence, the more
    sibling tokens it carries. Practice-validated t732 (banked "tokens +1,
    COUNT AT AUTHORING") -> t733 first fire read promoted +0 / tokens +1 EXACT.

    PRIOR-SET CONDITION (amended /review 734 from
    cpr_mogul_review_close_check_f6483a805358, Architect-ratified): counting
    the cpr-shaped tokens in the planned inscription content is NECESSARY but
    NOT sufficient — token_delta's unit is DISTINCT-MEMBERS-OF-A-SET, so the
    delta is a function of (planned content tokens INTERSECT complement of the
    PRIOR index set), never of content alone. Before banking, DIFF each planned
    token against the prior index: a token already inside a provenance comment
    on any scanned surface (grep the build_inscribed_index surfaces, or read
    the prior tic's persisted check artifact) contributes +0 no matter how
    many times the new inscription cites it. The failure this cures is MODAL,
    not edge-case: a refinement ray routinely narrates the sibling guard it
    sits beside, and a narrated already-indexed sibling moves the counter by
    exactly zero (t731 lived: the GUARD-15 provenance comment carried two
    cpr-shaped tokens yet moved the counter +1 — the narrated sibling was
    already a member; index-set diff verified 368 -> 369, new set exactly one
    id). Content-count without the prior-set diff would have banked +2 and
    been confidently wrong on the commonest inscription shape.
    """
    promoted_delta = (verdict_delta_block.get("delta") or {}).get("promoted")
    token_delta = index_delta_block.get("delta_tokens")
    comparable = isinstance(promoted_delta, int) and isinstance(token_delta, int)
    return {
        "promoted_delta": promoted_delta,
        "token_delta": token_delta,
        "comparable": comparable,
        "agree": (promoted_delta == token_delta) if comparable else None,
        "divergence_routes": [
            "modify_and_merge_promotion_adds_no_provenance_comment",
            "doctrine_edit_narrating_sibling_id_adds_token_without_promotion",
            "t724_over_admission_receipt_filename_tokens",
        ],
        "note": (
            "typed disclosure, never an invariant: agree=False is a question "
            "with named routes, not a finding. Baselines absent on either side "
            "=> comparable=False, agree=None — never fabricated agreement."
        ),
    }


def run_check(project_dir, dry_run=False, obligation_tic=None, obligation_mandate_id=None):
    """Run the full review-close consistency check.

    obligation_tic / obligation_mandate_id: explicit obligation-clock identity for
    the written artifact (see resolve_obligation_clock) — the tic of the mandate
    that dispatched this cycle, outranking the executor clock (current.json)."""
    project_dir = os.path.abspath(project_dir)
    # Rebuild the receipt-surface index fresh each run (tic 593 widened sweep).
    _RECEIPT_INDEX_CACHE.clear()
    # Same freshness discipline for the provenance anchors (tic 723): memoized
    # WITHIN a run (an id can be classified twice), never ACROSS runs — a stale
    # birth_commit would be exactly the kind of frozen evidence this cure removes.
    _PICKAXE_CACHE.clear()
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)

    queue_path = os.path.join(al_path, "cprs", "queue.jsonl")
    queue = load_queue(queue_path)
    # Lesson fallbacks: recover lesson text from earlier (pre-writeback) queue rows
    # when the latest (promoted) entry is a minimal writeback with no lesson field.
    lesson_fallbacks = load_lesson_fallbacks(queue_path)

    inscribed_diagnostics = {}
    inscribed_ids = build_inscribed_index(
        project_dir, queue_ids=set(queue.keys()), diagnostics=inscribed_diagnostics
    )

    all_findings = []

    # Check each CPR based on its status
    for cpr_id, cpr in queue.items():
        status = cpr.get("status", "")

        if status == "promoted":
            all_findings.extend(check_promoted(cpr_id, cpr, project_dir, inscribed_ids, lesson_fallbacks))

        elif status in ("deferred", "enrichment_eligible"):
            # Deferred CPRs should have review provenance. Call unconditionally:
            # a call-site guard on the same predicate the check tests made the
            # deferred_no_review_tic finding-class unreachable (dead check,
            # found tic 554 via a 35-vs-36 counter delta).
            all_findings.extend(check_deferred(cpr_id, cpr))

        elif status == "skipped":
            all_findings.extend(check_skipped(cpr_id, cpr))

        elif cpr.get("lifecycle_state", "") in LIFECYCLE_SETTLED_STATES:
            # Settled by additive lifecycle_state (terminal_positive/negative,
            # obligated_waiting, suspensive) and not one of the checked statuses
            # above — a settled disposition carrying its own per-row receipt; no
            # promoted-text/orphan close-check applies. Explicit recognition of
            # the shared field; no behavior change (these ids already fell
            # through the status dispatch before tic 555).
            continue

    # Orphan check across all promoted
    all_findings.extend(check_orphans(queue, project_dir, inscribed_ids))

    # Genuine-vs-known reason split (cgg-ledger#reason-coded-genuine-vs-known-verifier-split,
    # promoted /review 336): annotate each promoted-missing / orphaned finding with a
    # REASON code so only reason=None (genuinely missing) findings count as hazards.
    # KNOWN findings are downgraded to severity=info — they are expected noise, not
    # inconsistencies — so by_severity.error reflects ONLY genuine hazards. Done before
    # the severity aggregation below so the downgrade is reflected in the counts.
    #
    # tic 628 (Verifier-Split Chapter 3): the classification pass covers EVERY emitted
    # finding type — no type floats unclassified while consistent:false. The two
    # promoted classes go through classify_known_reason (unchanged); check_deferred
    # classifies in-row (it holds the path evidence); anything else that arrives
    # unclassified is stamped genuine explicitly. genuine + known therefore equals the
    # full finding universe, so the human-facing all-known sentence and the artifact
    # can no longer disagree.
    project_basename = os.path.basename(project_dir)
    genuine_count = 0
    known_count = 0
    known_by_reason = {}
    for f in all_findings:
        if f.get("type") in ("promoted_text_missing", "orphaned_promotion"):
            cpr = queue.get(f.get("cpr_id"), {})
            reason, evidence = classify_known_reason(
                f["cpr_id"], cpr, project_dir, project_basename, lesson_fallbacks
            )
            f["evidence"] = evidence
            if reason is None:
                f["finding_class"] = "genuine"
            else:
                f["finding_class"] = "known"
                f["reason"] = reason
                f["severity"] = "info"  # known false-positive — not a hazard
        elif "finding_class" not in f:
            # A finding type with no dedicated classifier (promoted_no_target,
            # skip_status_mismatch, …) is a real data-quality gap until a
            # discriminating axis exists — classified genuine, never left floating.
            f["finding_class"] = "genuine"
            f.setdefault("evidence", {
                "note": "no dedicated known-false-positive axis for this finding "
                        "type; classified genuine (unclassified-floating is the "
                        "defect this pass closes)",
            })
        if f["finding_class"] == "genuine":
            genuine_count += 1
        else:
            known_count += 1
            reason = f.get("reason", "unspecified")
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
    deferred_count = sum(1 for c in queue.values() if c.get("status") in ("deferred", "enrichment_eligible") and (c.get("review_tic") or c.get("reviewed_tic")))
    skipped_count = sum(1 for c in queue.values() if c.get("status") == "skipped")

    historical_count = sum(1 for c in queue.values() if c.get("historical_artifact"))

    # Artifact-identity resolution HOISTED out of the write block (/review 724
    # RIDER 2): the per-unit delta must exclude this run's OWN artifact from its
    # baseline search, and it must do so using the exact name the writer will
    # use — so the name is computed ONCE here and reused below (single
    # computation, two consumers). Both calls are pure reads (env / CLI /
    # current.json); the identity-degradation WARNINGS stay in the write path,
    # where they are true. dry-run therefore gets the delta too, and prints it
    # under --json without touching disk.
    report_dir = os.path.join(al_path, "mogul", "cycle-reports", "review-close-checks")
    mandate_id, mandate_tic, clock_source = resolve_obligation_clock(
        al_path, obligation_tic, obligation_mandate_id)
    executor_clock_tic = None
    if clock_source != "executor_clock":
        _exec_mid, _exec_tic = load_mandate_id(al_path)
        if _exec_tic is not None and _exec_tic != mandate_tic:
            executor_clock_tic = _exec_tic
        if mandate_id is None:
            mandate_id = _exec_mid  # audit-trail fallback; naming stays obligation-clocked
    output_filename, identity_kind = _canonical_output_filename(mandate_tic, mandate_id)

    inscribed_unit = inscribed_diagnostics.get("unit_declaration") or {}
    index_delta = compute_unit_deltas(
        report_dir,
        output_filename,
        mandate_tic,
        len(inscribed_ids),
        inscribed_unit.get("matched_comment_count"),
    )
    verdict_delta = compute_verdict_count_deltas(
        report_dir,
        output_filename,
        mandate_tic,
        {"promoted": promoted_count, "deferred": deferred_count,
         "skipped": skipped_count},
    )
    cross_disclosure = compute_cross_counter_disclosure(verdict_delta, index_delta)

    report = {
        "check_type": "review_close_check",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queue_path": queue_path,
        "total_cprs": len(queue),
        "inscribed_index_size": len(inscribed_ids),
        # Unit declaration BESIDE the integer (/review 716 class-cure,
        # 502236e96cf1): what was scanned, what unit the integer counts, and
        # how many comments yield >1 distinct id — the fields a consumer needs
        # to predict in the counter's own unit.
        "inscribed_index_unit": inscribed_diagnostics.get("unit_declaration"),
        # Per-unit DELTA beside the integer and its unit (/review 724 RIDER 2,
        # constitution-ledger streak-claims ray): the counter owes a per-pass
        # delta in EACH of its declared units, plus the collapse flag that makes
        # agreement-under-collapse legible as collapse. Baseline absent =>
        # nulls + delta_baseline_absent, never fabricated zeros.
        "inscribed_index_delta": index_delta,
        # Membership-resolution diagnostics (/review 709, f94b63ce931d): the
        # counter's referent is measured — reserved tokens excluded, id-shaped
        # refs that fail queue membership admitted-but-disclosed.
        "inscribed_index_unresolved": inscribed_diagnostics,
        "historical_artifacts": historical_count,
        "verdict_counts": {
            "promoted": promoted_count,
            "deferred": deferred_count,
            "skipped": skipped_count,
        },
        # Per-key DELTA beside the verdict counters (/review 728 obligation-scope
        # ray, c209995ad848): a delta obligation landed on one counter attaches
        # to every counter on the same artifact surface. Same baseline discipline
        # as inscribed_index_delta — absent => nulls, never fabricated zeros.
        "verdict_counts_delta": verdict_delta,
        # Derived cross-counter DISCLOSURE (same ray): promoted-verdict delta vs
        # provenance-token delta, with divergence routes named — a typed question
        # for the reader, never an asserted invariant.
        "cross_counter_disclosure": cross_disclosure,
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
            # tic 628 (Verifier-Split Chapter 3): the classification pass covers the
            # FULL finding universe, so genuine + known == total by construction.
            # This field makes the summary↔universe agreement machine-checkable —
            # False here means a finding type regressed to floating-unclassified.
            "universe_classified": (genuine_count + known_count) == len(all_findings),
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

        os.makedirs(report_dir, exist_ok=True)

        # Obligation-clock naming (bk-review-close-check-obligation-clock-naming):
        # the artifact files under the OBLIGATION's tic. When an obligation channel
        # is present and the executor clock (current.json) disagrees, the divergence
        # is disclosed first-class in the log row — the boundary crossing made
        # visible, never silently absorbed (surface-don't-hide).
        #
        # mandate_id / mandate_tic / clock_source / executor_clock_tic /
        # output_filename were resolved ONCE above (hoisted at tic 724 so the
        # per-unit delta excludes this run's own artifact by the writer's exact
        # name). The T4c identity ladder is unchanged; only the WARNINGS live
        # here, because only a write can degrade an artifact's identity.
        if identity_kind == "mandate":
            print(
                "WARNING: review_close_check write without mandate tic; "
                "falling back to mandate-keyed identity (per-tic dedup degraded).",
                file=sys.stderr,
            )
        elif identity_kind == "timestamp":
            print(
                "WARNING: review_close_check write without mandate_id; "
                "falling back to timestamp identity (canonical artifact identity unstable).",
                file=sys.stderr,
            )
        output_path = os.path.join(report_dir, output_filename)

        # Designated-evidence-surface cure (/review 715, 6372e7b37b73): the
        # streak the machine computes belongs in the artifact the cycle names
        # as its evidence, not only in the service-log audit trail — a durable
        # birth in the wrong lane still forces consumers to hand-project.
        # Computed ONCE here (before the dedup comparison, so a same-tic
        # re-observation that changes the streak is a REAL content change and
        # routes through the superseded-receipt branch), reused for the log row.
        report["genuine_zero_streak"] = compute_genuine_zero_streak(
            os.path.join(al_path, "services", "review-close-check-log.jsonl"),
            mandate_tic,
            report["summary"]["genuine_count"],
        )

        decision = "write"
        prior_raw = None
        prior_generated_at = None
        if (mandate_tic is not None or mandate_id) and os.path.exists(output_path):
            try:
                prior_raw = Path(output_path).read_bytes()
                prior = json.loads(prior_raw.decode("utf-8"))
                prior_generated_at = prior.get("generated_at")
                # Compare full report content minus the volatile timestamp —
                # findings-only comparison let a stale verdict_counts survive a
                # counter repair (tic 554: on-disk deferred=35 vs runtime 36).
                # superseded_receipt is comparison-volatile too (/review 716
                # AUDIENCE/HANDLE cure): the live artifact now carries the
                # supersession receipt for its OWN prior; a fresh in-memory
                # report never has one, so comparing it would force decision=
                # replace on every run after a supersession even when findings
                # are identical — the exact skip-branch the receipt must not
                # break.
                _volatile = ("generated_at", "superseded_receipt")
                prior_norm = {k: v for k, v in prior.items() if k not in _volatile}
                report_norm = {k: v for k, v in report.items() if k not in _volatile}
                if prior_norm == report_norm:
                    decision = "skip"
                else:
                    decision = "replace"
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                # Corrupt or unreadable prior — overwrite under latest-wins semantics
                # (the raw bytes, if readable, are still preserved below).
                decision = "replace"

        identity_label = (
            f"tic {mandate_tic}" if mandate_tic is not None
            else f"mandate {mandate_id}"
        )

        superseded_receipt = None
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
            # Preserve-prior-under-superseded-receipt (bk-review-close-check-
            # observation-key, /review 685 ratified — ray on cgg-ledger#artifact-
            # count-1-fix-family): the N=1-per-tic canonical identity STANDS, but
            # two distinct mandates within one tic are two distinct OBSERVATIONS
            # (pre-/review baseline vs post-/review state) — the replace branch
            # destroyed the earlier one with only a stderr INFO line. Before the
            # overwrite, the prior artifact's RAW BYTES are preserved (sequence-
            # numbered, never themselves overwritten) and the log row carries a
            # first-class receipt: a terminal-essence state change requires a
            # justified receipt and may not let signal go dark. NEVER per-mandate
            # filenames (re-opens the N!=1 family); NEVER a review-phase detector
            # (inference, not evidence — preservation invents nothing).
            if decision == "replace" and prior_raw is not None:
                superseded_dir = os.path.join(report_dir, "superseded")
                os.makedirs(superseded_dir, exist_ok=True)
                stem = os.path.splitext(output_filename)[0]
                seq = 1
                while os.path.exists(os.path.join(
                        superseded_dir, f"{stem}.superseded-{seq}.json")):
                    seq += 1
                preserved_abs = os.path.join(
                    superseded_dir, f"{stem}.superseded-{seq}.json")
                Path(preserved_abs).write_bytes(prior_raw)
                try:
                    preserved_rel = os.path.relpath(preserved_abs, project_dir)
                except ValueError:
                    preserved_rel = preserved_abs
                superseded_receipt = {
                    "preserved_path": preserved_rel,
                    "justification_class": (
                        "superseded_by_same_tic_reobservation"
                        if prior_generated_at is not None
                        else "corrupt_prior_replaced"),
                    "prior_generated_at": prior_generated_at,
                }
                # AUDIENCE/HANDLE ray cure (/review 716, 07c597566b16 PROMOTE-
                # as-refinement-ray): made_known discharges at the CONSUMER'S
                # HANDLE, not only in the producer's lane. The receipt below is
                # ALSO written into the live replacing artifact — a consumer
                # holding this stable path (an immutable past cycle report
                # citing report_path) discovers the supersession HERE without
                # ever reading review-close-check-log.jsonl. Same block, second
                # audience; single computation, two sinks (the /review 715
                # discipline). Excluded from the dedup comparison via
                # _volatile above so identical-CONTENT runs still skip.
                # UNIT, stated exactly (bf492de6b23a, /review 735 PROMOTE-TO-
                # PROCEDURAL-HOME): the skip-vs-replace predicate compares the
                # WHOLE REPORT CONTENT minus the two volatile keys
                # (`generated_at`, `superseded_receipt`) — NOT the findings set.
                # A run whose findings are byte-stable still REPLACES when any
                # other content moves (measured t732: verdict_counts.promoted
                # 733 -> 734 drove the replace across two same-tic observations
                # with an identical 14-finding set). Narrate the measured unit;
                # a findings-only claim here would be falsifiable-and-false.
                report["superseded_receipt"] = superseded_receipt
                # Back-stamp beside the preserved copy as a SIDECAR — the
                # preserved artifact's RAW BYTES stay byte-exact (the /review
                # 685 preservation law); the stamp rides NEXT TO it, never
                # inside it.
                Path(preserved_abs + ".superseded-by.json").write_text(
                    json.dumps({
                        "superseded_by_live_path": output_path,
                        "superseded_at": datetime.now(timezone.utc).isoformat(),
                        "justification_class": superseded_receipt["justification_class"],
                    }, indent=2), encoding="utf-8")
            Path(output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
            if decision == "replace":
                preserved_note = (
                    f" prior observation preserved at {superseded_receipt['preserved_path']}"
                    if superseded_receipt else " prior unreadable — nothing to preserve"
                )
                print(
                    f"INFO: review_close_check replaced existing report for {identity_label} (report content changed);{preserved_note}.",
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
            "obligation_clock_source": clock_source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "report_path": output_path,
            "findings_count": len(report["findings"]),
            "consistent": report["summary"]["consistent"],
            "genuine_count": report["summary"]["genuine_count"],
            "known_count": report["summary"]["known_count"],
            "genuine_consistent": report["summary"]["genuine_consistent"],
        }
        # Mechanized streak (/review 709, ad00d4c652c8): computed by the writer
        # of the log row, in its declared unit, gaps + re-observations disclosed.
        # Single computation, two sinks (/review 715): the value embedded in the
        # designated report artifact above IS the value logged here — one
        # measurement, never two divergent computations.
        log_entry["genuine_zero_streak"] = report["genuine_zero_streak"]
        if executor_clock_tic is not None:
            # The cured defect, observed live: the run crossed a tic boundary and
            # the executor clock would have mis-filed this evidence.
            log_entry["executor_clock_tic"] = executor_clock_tic
        if superseded_receipt is not None:
            log_entry["superseded_receipt"] = superseded_receipt
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
    parser.add_argument("--obligation-tic", type=int, default=None,
                        help="Obligation-clock tic for artifact naming (the tic of "
                             "the mandate that dispatched this cycle); outranks the "
                             "CGG_OBLIGATION_TIC env pin and the executor clock")
    parser.add_argument("--obligation-mandate-id", default=None,
                        help="Obligation mandate id (audit trail; pairs with "
                             "--obligation-tic)")
    args = parser.parse_args()

    project_dir = args.project_dir or resolve_zone_root()
    report = run_check(project_dir, dry_run=args.dry_run,
                       obligation_tic=args.obligation_tic,
                       obligation_mandate_id=args.obligation_mandate_id)

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
                # tic 628: with the classification pass covering every emitted
                # finding type, known_count == total_findings whenever genuine == 0
                # — the all-known sentence now states the full finding universe.
                print(f"  genuine=0 — no hazard (all {s['known_count']} of {s['total_findings']} findings are known false-positives)")
            if not s.get("universe_classified", True):
                print("  WARNING: finding universe not fully classified — a finding type regressed to floating-unclassified")

    return 0


if __name__ == "__main__":
    sys.exit(main())
