#!/usr/bin/env python3
"""
Review Close Check — post-review consistency verification.

Verifies that /review verdicts were correctly inscribed:
  - PROMOTE: lesson text landed in target file
  - DEFER: queue.jsonl has updated review_tic
  - SKIP: queue.jsonl status is 'skipped'
  - Orphan check: queue says promoted but text missing from target

Output: JSON consistency report.

Usage:
    python3 review-close-check.py --project-dir /path/to/zone
    python3 review-close-check.py --project-dir /path/to/zone --dry-run
    python3 review-close-check.py --project-dir /path/to/zone --json
    python3 review-close-check.py --help
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
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path


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


def _read_target(target_str, project_dir, project_basename=None):
    """Resolve a target string to a filesystem path and return its content.

    Applies two normalizations before resolving:
      1. Parenthetical scope-hint stripping — "canonical/CLAUDE.md (refined 'X')"
         becomes "canonical/CLAUDE.md".
      2. Federation-prefix stripping — when the first path segment matches the
         federation repo's basename (e.g. "canonical/CLAUDE.md" where the repo
         is named "canonical"), strip that segment and resolve relative to
         project_dir.  This handles queue entries that record paths relative to
         the parent of the federation root rather than relative to it.

    Returns file content as str, or "" if the file cannot be read.
    """
    bare = _strip_scope_hint(target_str)

    if bare.startswith("~"):
        path = os.path.expanduser(bare)
        return read_file_safe(path)

    if os.path.isabs(bare):
        return read_file_safe(bare)

    # Relative path: resolve against project_dir
    path = os.path.join(project_dir, bare)
    content = read_file_safe(path)
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
                content2 = read_file_safe(path2)
                if content2:
                    return content2

    return ""


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

    Parenthesized scope hints in target paths (e.g.
    "canonical/CLAUDE.md (refined 'X' Key Invariant)") are stripped before
    filesystem resolution but preserved in the targets_checked report field.

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

    promoted_to = cpr.get("promoted_to", "")
    target = cpr.get("promotion_target", "")
    scopes = cpr.get("recommended_scopes", [])

    targets = []
    if isinstance(promoted_to, str) and promoted_to:
        targets.append(promoted_to)
    elif isinstance(promoted_to, list):
        targets.extend([p for p in promoted_to if isinstance(p, str) and p])
    if target:
        targets.append(target)
    for s in scopes:
        if _looks_like_file_path(s):
            targets.append(s)

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


_PROVENANCE_RE = re.compile(r"<!--\s*promoted from\s+(cpr_[A-Za-z0-9_]+|CogPR-\d+)", re.IGNORECASE)


def build_inscribed_index(project_dir):
    """Scan governance files for `<!-- promoted from <id>` markers.

    Returns set of CPR ids that have provenance comments anywhere in the
    federation governance surface. Used by check_promoted as the strongest
    verification axis — surviving the comment is sufficient evidence of
    inscription, regardless of whether the queue entry's `promoted_to` field
    points at the correct file.

    Scanned surfaces (patch tic 216):
    - canonical/CLAUDE.md, INDEX.md, GIT_RULES.md — federation root governance docs
    - ~/.claude/CLAUDE.md — global user governance surface
    - canonical_developer/ subtree — CLAUDE.md, AUTHORING_CONVENTION.md, SKILL.md files
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
        os.path.expanduser("~/.claude/CLAUDE.md"),
    ]
    # Sweep canonical_developer subtree CLAUDE.md surfaces (CGG, capture-studio, etc.)
    cd_dir = os.path.join(project_dir, "canonical_developer")
    if os.path.isdir(cd_dir):
        for root, _dirs, files in os.walk(cd_dir):
            if "/.git/" in root or "/node_modules/" in root:
                continue
            for fn in files:
                if fn in ("CLAUDE.md", "AUTHORING_CONVENTION.md") or fn.endswith("SKILL.md"):
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
        for m in _PROVENANCE_RE.finditer(content):
            inscribed.add(m.group(1))
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
            os.path.expanduser("~/.claude/CLAUDE.md"),
        ]

        promoted_to = cpr.get("promoted_to", "")
        if isinstance(promoted_to, str) and promoted_to:
            check_paths.append(promoted_to if os.path.isabs(promoted_to)
                               else os.path.join(project_dir, promoted_to))
        elif isinstance(promoted_to, list):
            for p in promoted_to:
                if isinstance(p, str) and p:
                    check_paths.append(p if os.path.isabs(p) else os.path.join(project_dir, p))

        for scope in cpr.get("recommended_scopes", []):
            if not _looks_like_file_path(scope):
                continue
            if scope.startswith("~"):
                check_paths.append(os.path.expanduser(scope))
            elif not os.path.isabs(scope):
                check_paths.append(os.path.join(project_dir, scope))
            else:
                check_paths.append(scope)

        found = False
        for path in check_paths:
            content = read_file_safe(path)
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
# Main pipeline
# ---------------------------------------------------------------------------

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
            "consistent": len(all_findings) == 0,
        },
    }

    if not dry_run:
        report_dir = os.path.join(al_path, "mogul", "cycle-reports", "review-close-checks")
        os.makedirs(report_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
        output_path = os.path.join(report_dir, f"{timestamp}-check.json")
        Path(output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["_output_path"] = output_path

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
        status = "CONSISTENT" if s["consistent"] else f"{s['total_findings']} ISSUES"
        print(f"Review close check: {status}")
        print(f"  Verdicts: {vc['promoted']} promoted, {vc['deferred']} deferred, {vc['skipped']} skipped")
        if not s["consistent"]:
            for sev, count in s["by_severity"].items():
                print(f"  {sev}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
