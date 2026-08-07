#!/usr/bin/env python3
"""
Review Test — resolution-order claim A (bk-review-close-check-resolution-order, tic 684).

Guards the Verifier-Split CHAPTER 4 claim-A runtime fix (cgg-ledger
#inscription-verification-reason-coded-dehydration-provenance-aware, MODIFY+PROMOTE
/review 683; runtime fix FILED not blind-authorized): the resolution layer sits
BENEATH every classification axis, so when target decomposition manufactures
fragments that resolve nowhere, no axis can fire and the finding falls through as
false GENUINE — and the GENUINE evidence says "genuinely missing" without ever
disclosing that content verification never ran.

Claim B ("no domain-root fallback") is STRUCK — falsified by corrector
cpr_mogul_review_close_check_6540e0503eaa (the bounded suffix-rglob exists and the
cross-axis hoist landed /review 680). This test targets ONLY the surviving claim A.

The live post-fix-A fracture shape: `_split_compound_targets` splits on ` + ` at
paren depth 0 — but this federation has REAL filenames containing ` + `
("cpr_mogul_harmony_invoke + deep_audit_f4de0ac773fb.consolidated.json"), so a
promoted_to naming such a file fractures into two components that resolve nowhere.

Pins, on isolated fixtures:
  1. REPRO (check_promoted): a promoted_to naming an existing ` + `-in-filename
     file that CONTAINS the cpr_id must produce NO finding — the raw unsplit
     string is a last-resort resolution candidate after its components fail.
  2. REPRO (classifier): the same fracture shape over an existing CODE file must
     classify behavioral_text_unverifiable, NOT genuine — the axis fires once the
     raw form resolves.
  3. DISCLOSURE: when NO target resolves anywhere, the finding STAYS genuine
     (hazard preserved — a broken pointer is never a known non-hazard) but its
     evidence must carry resolution_layer_miss=True + the unresolved targets, so
     the resolution-layer failure is loud instead of silently graded as a
     verified-missing inscription.
  4. NEGATIVE: a target that RESOLVES but lacks the inscription stays plain
     genuine with no resolution_layer_miss flag — no blanket reclassification.
  5. ORDER: components still precede the raw form in the candidate list (the raw
     form is last-resort, never the primary).

Run: python3 test_resolution_order_claim_a_tic684.py  (pytest-discoverable)
"""
import importlib.util
import os
import sys
import tempfile

_SCRIPT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "review-close-check.py"))


def _load():
    spec = importlib.util.spec_from_file_location("review_close_check", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _promoted_cpr(cpr_id, lesson, promoted_to):
    return {
        "id": cpr_id,
        "status": "promoted",
        "tier": "tier1",
        "lesson": lesson,
        "promoted_to": promoted_to,
    }


# ---------------------------------------------------------------------------
# 1. REPRO — ` + ` inside a real filename; content match must find the raw file
# ---------------------------------------------------------------------------

def test_plus_in_filename_target_resolves_via_raw_fallback():
    m = _load()
    m._RECEIPT_INDEX_CACHE.clear()
    with tempfile.TemporaryDirectory() as d:
        rel = "audit-logs/governance/enrichment/cpr_alpha + deep_audit_beta.consolidated.md"
        _write(os.path.join(d, rel),
               "# Consolidated\n\ncpr_alpha_plus_case_tic684 evidence body.\n")
        cpr = _promoted_cpr("cpr_alpha_plus_case_tic684", "some lesson text", rel)
        findings = m.check_promoted("cpr_alpha_plus_case_tic684", cpr, d)
        assert findings == [], (
            f"raw ` + `-in-filename target must content-match; got {findings}")


# ---------------------------------------------------------------------------
# 2. REPRO — same fracture over a code file; classifier must reach behavioral
# ---------------------------------------------------------------------------

def test_plus_in_filename_code_target_classifies_behavioral_not_genuine():
    m = _load()
    m._RECEIPT_INDEX_CACHE.clear()
    with tempfile.TemporaryDirectory() as d:
        rel = "scripts/econ + drift-guard.py"
        _write(os.path.join(d, rel), "# behavioral surface\n")
        cpr = _promoted_cpr("cpr_plus_code_case_tic684", "lesson", rel)
        reason, evidence = m.classify_known_reason(
            "cpr_plus_code_case_tic684", cpr, d)
        assert reason == m.REASON_BEHAVIORAL, (
            f"expected behavioral_text_unverifiable, got {reason} ({evidence})")


# ---------------------------------------------------------------------------
# 3. DISCLOSURE — nothing resolves: stays GENUINE but the miss is loud
# ---------------------------------------------------------------------------

def test_resolution_layer_miss_is_disclosed_and_stays_genuine():
    m = _load()
    m._RECEIPT_INDEX_CACHE.clear()
    with tempfile.TemporaryDirectory() as d:
        cpr = _promoted_cpr(
            "cpr_unresolvable_case_tic684", "lesson",
            "docs/never-written-file.md (scope hint) + also/not-there.md")
        reason, evidence = m.classify_known_reason(
            "cpr_unresolvable_case_tic684", cpr, d)
        assert reason is None, "unresolvable pointer must STAY a genuine hazard"
        assert evidence.get("resolution_layer_miss") is True, (
            f"resolution-layer failure must be disclosed; got {evidence}")
        assert evidence.get("targets_unresolved"), (
            "the unresolved targets must be named in evidence")


# ---------------------------------------------------------------------------
# 4. NEGATIVE — resolved-but-missing stays plain genuine (no miss flag)
# ---------------------------------------------------------------------------

def test_resolved_target_missing_text_stays_plain_genuine():
    m = _load()
    m._RECEIPT_INDEX_CACHE.clear()
    with tempfile.TemporaryDirectory() as d:
        rel = "docs/present.md"
        _write(os.path.join(d, rel), "# Doctrine\n\nUnrelated body text only.\n")
        cpr = _promoted_cpr("cpr_present_but_missing_tic684", "lesson", rel)
        reason, evidence = m.classify_known_reason(
            "cpr_present_but_missing_tic684", cpr, d)
        assert reason is None
        assert not evidence.get("resolution_layer_miss"), (
            "a resolved target must not be reported as a resolution-layer miss")


# ---------------------------------------------------------------------------
# 5. ORDER — components precede the raw form; raw only appended on real splits
# ---------------------------------------------------------------------------

def test_collect_targets_appends_raw_last_and_only_on_split():
    m = _load()
    split_cpr = {"promoted_to": "a.md + b.md"}
    targets = m._collect_targets(split_cpr)
    assert targets[:2] == ["a.md", "b.md"]
    assert targets[-1] == "a.md + b.md", (
        f"raw unsplit string must trail as last-resort; got {targets}")
    plain_cpr = {"promoted_to": "a.md"}
    assert m._collect_targets(plain_cpr) == ["a.md"], (
        "no raw duplicate when no split occurred")


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILED'}")
    sys.exit(1 if failures else 0)
