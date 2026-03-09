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


def read_file_safe(path):
    """Read file content, return empty string on failure."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ---------------------------------------------------------------------------
# Consistency checks
# ---------------------------------------------------------------------------

def check_promoted(cpr_id, cpr, project_dir):
    """Verify promoted CPR text landed in target file."""
    findings = []
    lesson = cpr.get("lesson", "")
    scopes = cpr.get("recommended_scopes", [])
    target = cpr.get("promotion_target", "")

    # Determine target files to check
    targets = []
    if target:
        targets.append(target)
    targets.extend(scopes)

    if not targets:
        findings.append({
            "type": "promoted_no_target",
            "severity": "warning",
            "cpr_id": cpr_id,
            "message": f"{cpr_id} promoted but has no target or recommended_scopes",
        })
        return findings

    # Check if the CogPR reference or lesson snippet exists in any target
    cpr_ref = cpr_id
    # Also try CogPR-N format
    num_match = re.search(r"(\d+)", cpr_id)
    if num_match:
        cpr_ref_alt = f"CogPR-{num_match.group(1)}"
    else:
        cpr_ref_alt = None

    snippet = lesson[:50] if lesson else ""
    found_in_any = False

    for t in targets:
        path = t
        if t.startswith("~"):
            path = os.path.expanduser(t)
        elif not os.path.isabs(t):
            path = os.path.join(project_dir, t)

        content = read_file_safe(path)
        if not content:
            continue

        # Check for CogPR reference or lesson snippet
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


def check_orphans(queue, project_dir):
    """Find CPRs marked promoted in queue but missing from all target files."""
    findings = []

    for cpr_id, cpr in queue.items():
        if cpr.get("status") != "promoted":
            continue

        lesson = cpr.get("lesson", "")
        if not lesson:
            continue

        # Check if the CPR reference exists anywhere in governance files
        cpr_num = re.search(r"(\d+)", cpr_id)
        if not cpr_num:
            continue

        cpr_ref = f"CogPR-{cpr_num.group(1)}"
        snippet = lesson[:50]

        # Check common governance locations
        check_paths = [
            os.path.join(project_dir, "CLAUDE.md"),
            os.path.expanduser("~/.claude/CLAUDE.md"),
        ]

        # Also check recommended_scopes
        for scope in cpr.get("recommended_scopes", []):
            if scope.startswith("~"):
                check_paths.append(os.path.expanduser(scope))
            elif not os.path.isabs(scope):
                check_paths.append(os.path.join(project_dir, scope))
            else:
                check_paths.append(scope)

        found = False
        for path in check_paths:
            content = read_file_safe(path)
            if content and (cpr_ref in content or snippet in content):
                found = True
                break

        if not found:
            findings.append({
                "type": "orphaned_promotion",
                "severity": "error",
                "cpr_id": cpr_id,
                "cpr_ref": cpr_ref,
                "message": f"{cpr_ref} marked promoted in queue but text not found in any governance file",
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

    all_findings = []

    # Check each CPR based on its status
    for cpr_id, cpr in queue.items():
        status = cpr.get("status", "")

        if status == "promoted":
            all_findings.extend(check_promoted(cpr_id, cpr, project_dir))

        elif status in ("deferred", "enrichment_eligible"):
            # Deferred CPRs should have a review_tic
            if cpr.get("review_tic") is not None:
                all_findings.extend(check_deferred(cpr_id, cpr))

        elif status == "skipped":
            all_findings.extend(check_skipped(cpr_id, cpr))

    # Orphan check across all promoted
    all_findings.extend(check_orphans(queue, project_dir))

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

    report = {
        "check_type": "review_close_check",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queue_path": queue_path,
        "total_cprs": len(queue),
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
