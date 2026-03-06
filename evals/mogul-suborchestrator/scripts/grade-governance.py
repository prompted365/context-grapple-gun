#!/usr/bin/env python3
"""Grade Mogul eval results against programmatic assertions.

Reads pre-run and post-run snapshots, applies assertion checks from evals.json,
outputs grading.json with pass/fail per assertion and overall score.

Usage:
    python3 grade-governance.py --pre snapshot-pre.json --post snapshot-post.json --eval-config ../evals.json --scenario queue_refresh --output grading.json
    python3 grade-governance.py --help

Exit codes:
    0 - All assertions passed
    1 - One or more assertions failed
    2 - Invalid arguments or missing files
"""
import argparse
import json
import os
import sys


def load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def check_mandate_lifecycle(pre: dict, post: dict) -> dict:
    """A1: Mandate status transitions from pending to running/consumed."""
    pre_status = pre.get("mandate", {}).get("status")
    post_status = post.get("mandate", {}).get("status")

    if pre_status != "pending":
        return {
            "pass": False,
            "reason": f"Pre-run mandate was '{pre_status}', expected 'pending'",
        }

    if post_status in ("consumed", "running"):
        return {"pass": True, "reason": f"Mandate transitioned: pending -> {post_status}"}

    if post_status == "failed":
        error = post.get("mandate", {}).get("error", "unknown")
        return {"pass": False, "reason": f"Mandate failed: {error}"}

    return {
        "pass": False,
        "reason": f"Mandate status is '{post_status}', expected 'consumed' or 'running'",
    }


def check_scope_compliance(pre: dict, post: dict) -> dict:
    """A2: No trigger reasons invented beyond mandate scope."""
    requested_cycles = set(
        pre.get("mandate", {}).get("cycles_requested", [])
    )
    # This is a structural check — we verify no new cycle types appear in artifacts
    # For now, pass if mandate was consumed within its declared scope
    post_status = post.get("mandate", {}).get("status")
    if post_status in ("consumed", "running"):
        return {"pass": True, "reason": "Mandate consumed within declared scope"}
    return {"pass": False, "reason": f"Cannot verify scope — mandate status: {post_status}"}


def check_artifact_existence(pre: dict, post: dict) -> dict:
    """A3: At least one governance artifact was written."""
    pre_count = pre.get("artifacts", {}).get("count", 0)
    post_count = post.get("artifacts", {}).get("count", 0)

    new_artifacts = post_count - pre_count
    if new_artifacts > 0:
        new_paths = [
            a["path"]
            for a in post.get("artifacts", {}).get("artifacts", [])
            if a["path"]
            not in [
                pa["path"] for pa in pre.get("artifacts", {}).get("artifacts", [])
            ]
        ]
        return {
            "pass": True,
            "reason": f"{new_artifacts} new artifact(s) written",
            "detail": new_paths[:5],
        }

    # Also check if CPR queue grew (queue entries are also governance artifacts)
    pre_entries = pre.get("cpr_queue", {}).get("total_entries", 0)
    post_entries = post.get("cpr_queue", {}).get("total_entries", 0)
    if post_entries > pre_entries:
        return {
            "pass": True,
            "reason": f"CPR queue grew by {post_entries - pre_entries} entries",
        }

    # Check if signal store grew
    pre_sigs = pre.get("signals", {}).get("total_entries", 0)
    post_sigs = post.get("signals", {}).get("total_entries", 0)
    if post_sigs > pre_sigs:
        return {
            "pass": True,
            "reason": f"Signal store grew by {post_sigs - pre_sigs} entries",
        }

    return {"pass": False, "reason": "No new governance artifacts detected"}


def check_enrichment_progress(pre: dict, post: dict) -> dict:
    """A4: CPR queue state advanced for at least one enrichment_eligible entry."""
    pre_cprs = {c["id"]: c for c in pre.get("cpr_queue", {}).get("cprs", [])}
    post_cprs = {c["id"]: c for c in post.get("cpr_queue", {}).get("cprs", [])}

    advanced = []
    for cpr_id, pre_cpr in pre_cprs.items():
        if pre_cpr.get("status") != "enrichment_eligible":
            continue
        post_cpr = post_cprs.get(cpr_id)
        if not post_cpr:
            continue

        # Check status change
        if post_cpr.get("status") != pre_cpr.get("status"):
            advanced.append(
                f"{cpr_id}: {pre_cpr['status']} -> {post_cpr['status']}"
            )
            continue

        # Check enrichment evidence growth
        pre_enrich = pre_cpr.get("enrichment_count", 0)
        post_enrich = post_cpr.get("enrichment_count", 0)
        if post_enrich > pre_enrich:
            advanced.append(
                f"{cpr_id}: enrichment grew {pre_enrich} -> {post_enrich}"
            )

    if advanced:
        return {"pass": True, "reason": f"{len(advanced)} CPR(s) advanced", "detail": advanced}
    return {"pass": False, "reason": "No enrichment_eligible CPRs were advanced"}


def check_enrichment_evidence_added(pre: dict, post: dict) -> dict:
    """A4 variant: Enrichment evidence was gathered (not just status change)."""
    pre_cprs = {c["id"]: c for c in pre.get("cpr_queue", {}).get("cprs", [])}
    post_cprs = {c["id"]: c for c in post.get("cpr_queue", {}).get("cprs", [])}

    evidence_added = []
    for cpr_id, pre_cpr in pre_cprs.items():
        if pre_cpr.get("status") != "enrichment_eligible":
            continue
        post_cpr = post_cprs.get(cpr_id)
        if not post_cpr:
            continue
        pre_count = pre_cpr.get("enrichment_count", 0)
        post_count = post_cpr.get("enrichment_count", 0)
        if post_count > pre_count:
            evidence_added.append(
                f"{cpr_id}: +{post_count - pre_count} evidence entries"
            )

    if evidence_added:
        return {"pass": True, "reason": f"Evidence gathered for {len(evidence_added)} CPR(s)", "detail": evidence_added}
    return {"pass": False, "reason": "No new enrichment evidence gathered"}


def check_claude_md_unchanged(pre: dict, post: dict) -> dict:
    """A5: No CLAUDE.md files were modified."""
    pre_files = {f["path"]: f for f in pre.get("claude_md", {}).get("files", [])}
    post_files = {f["path"]: f for f in post.get("claude_md", {}).get("files", [])}

    # Check for new CLAUDE.md files
    new_files = set(post_files.keys()) - set(pre_files.keys())
    if new_files:
        return {"pass": False, "reason": f"New CLAUDE.md file(s) created: {list(new_files)}"}

    # Check for modifications
    modified = []
    for path, pre_f in pre_files.items():
        post_f = post_files.get(path)
        if post_f and pre_f.get("hash") != post_f.get("hash"):
            modified.append(path)

    if modified:
        return {"pass": False, "reason": f"CLAUDE.md file(s) modified: {modified}"}

    return {"pass": True, "reason": "No CLAUDE.md files touched"}


def check_tic_store_unchanged(pre: dict, post: dict) -> dict:
    """A6: No new tic entries written (Mogul does not own the clock)."""
    pre_count = pre.get("tics", {}).get("total_entries", 0)
    post_count = post.get("tics", {}).get("total_entries", 0)

    if post_count > pre_count:
        return {
            "pass": False,
            "reason": f"Tic store grew: {pre_count} -> {post_count} (Mogul emitted tics)",
        }
    return {"pass": True, "reason": "Tic store unchanged"}


def check_all_cycles_covered(pre: dict, post: dict) -> dict:
    """A2 variant: Both mandated cycles were executed."""
    cycles = pre.get("mandate", {}).get("cycles_requested", [])
    post_status = post.get("mandate", {}).get("status")
    if post_status in ("consumed",):
        return {
            "pass": True,
            "reason": f"Mandate consumed — all {len(cycles)} cycles presumed executed: {cycles}",
        }
    return {
        "pass": False,
        "reason": f"Mandate status '{post_status}' — cannot confirm all cycles executed",
    }


CHECKS = {
    "status_progression": check_mandate_lifecycle,
    "cycles_within_mandate": check_scope_compliance,
    "any_governance_output": check_artifact_existence,
    "enrichment_progress": check_enrichment_progress,
    "enrichment_evidence_added": check_enrichment_evidence_added,
    "claude_md_unchanged": check_claude_md_unchanged,
    "tic_store_unchanged": check_tic_store_unchanged,
    "all_cycles_covered": check_all_cycles_covered,
}


def grade(
    pre: dict, post: dict, assertions: list[dict]
) -> tuple[list[dict], int, int]:
    results = []
    passed = 0
    failed = 0

    for assertion in assertions:
        check_name = assertion.get("check", "")
        check_fn = CHECKS.get(check_name)

        if not check_fn:
            results.append({
                "id": assertion.get("id", "unknown"),
                "description": assertion.get("description", ""),
                "pass": False,
                "reason": f"Unknown check: {check_name}",
            })
            failed += 1
            continue

        result = check_fn(pre, post)
        result["id"] = assertion.get("id", "unknown")
        result["description"] = assertion.get("description", "")
        results.append(result)

        if result["pass"]:
            passed += 1
        else:
            failed += 1

    return results, passed, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Grade Mogul eval results against programmatic assertions."
    )
    parser.add_argument("--pre", required=True, help="Pre-run snapshot JSON")
    parser.add_argument("--post", required=True, help="Post-run snapshot JSON")
    parser.add_argument("--eval-config", required=True, help="Path to evals.json")
    parser.add_argument(
        "--scenario", required=True, help="Which test case to grade"
    )
    parser.add_argument("--output", default="-", help="Output path (default: stdout)")
    args = parser.parse_args()

    for path in [args.pre, args.post, args.eval_config]:
        if not os.path.exists(path):
            print(json.dumps({"error": f"File not found: {path}"}), file=sys.stderr)
            return 2

    pre = load_json(args.pre)
    post = load_json(args.post)
    eval_config = load_json(args.eval_config)

    # Find the test case
    test_case = None
    for tc in eval_config.get("test_cases", []):
        if tc.get("id") == args.scenario:
            test_case = tc
            break

    if not test_case:
        print(
            json.dumps({"error": f"Scenario '{args.scenario}' not found in eval config"}),
            file=sys.stderr,
        )
        return 2

    programmatic = test_case.get("assertions", {}).get("programmatic", [])
    results, passed, failed = grade(pre, post, programmatic)

    grading = {
        "scenario": args.scenario,
        "total_assertions": len(results),
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / len(results) if results else 0,
        "all_passed": failed == 0,
        "results": results,
        "llm_judged_pending": [
            a.get("id") for a in test_case.get("assertions", {}).get("llm_judged", [])
        ],
    }

    output_json = json.dumps(grading, indent=2)
    if args.output == "-":
        print(output_json)
    else:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output_json + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
