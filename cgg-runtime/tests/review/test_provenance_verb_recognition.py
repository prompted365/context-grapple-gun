#!/usr/bin/env python3
"""
Review Test — provenance-verb recognition regression (verifier-split chapter 2, tic 515).

Guards cgg-ledger#inscription-verification-reason-coded-dehydration-provenance-aware
(promoted /review 515): the provenance-comment cpr_id recognizer is review-close-check's
STRONGEST verification axis (check_promoted line ~467 early-returns when a cpr_id is in
build_inscribed_index). Before this fix, `_PROVENANCE_VERB_RE` recognized
promoted/absorbed/refined/... but NOT the verb forms "refinement edge from" and
"conformation + refinement", so REFINEMENT-EDGE and CONFORMATION inscriptions
false-orphaned as GENUINE (13 false-positives at /review 515; tic-371/491/500/508/514
cohort). The fix completes the verb-set. This test pins:

  1. the regex recognizes every governed inscription verb form (incl. refinement edge,
     conformation), case-insensitively;
  2. the regex does NOT over-broaden — a non-provenance HTML comment with no governance
     verb must NOT match (re-introducing blindness from the other side is the failure
     this verifier exists to prevent);
  3. build_inscribed_index extracts the cpr_id from a refinement-edge AND a conformation
     comment landed in a doctrine surface (the end-to-end path check_promoted relies on).

Run: python3 test_provenance_verb_recognition.py   (also pytest-discoverable)
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


def test_regex_recognizes_all_inscription_verb_forms():
    m = _load()
    RE = m._PROVENANCE_VERB_RE
    must_match = [
        "<!-- promoted from cpr_x_tic1 -->",                       # existing baseline
        "<!-- promoted-spec from cpr_x_tic1 -->",
        "<!-- refinement edge from cpr_can_it_eat_tic508 -->",     # tic-515 fix #1
        "<!-- REFINEMENT EDGE from cpr_crossmodel_tic500 -->",     # case-insensitive
        "<!-- conformation + refinement (tic 491 ...) cpr_fidelity_tic491 -->",  # tic-515 fix #2
        "<!-- absorbed into cpr_merge_tic9 -->",
        "<!-- superseded by cpr_new_tic2 -->",
        "<!-- refined from cpr_a_tic3 + cpr_b_tic4 -->",
    ]
    for s in must_match:
        assert RE.search(s), f"provenance regex must match: {s}"


def test_regex_does_not_overbroaden():
    m = _load()
    RE = m._PROVENANCE_VERB_RE
    must_not_match = [
        "<!-- TODO: wire cpr_x_tic1 later -->",        # no governance verb at the anchor
        "<!-- this is a plain note about cpr_y -->",   # mentions a cpr but no verb
        "<!-- cpr_z_tic9 not yet promoted -->",        # negation; verb not at anchor
    ]
    for s in must_not_match:
        assert not RE.search(s), f"provenance regex must NOT match (over-broad): {s}"


def test_build_inscribed_index_picks_up_refinement_edge_and_conformation():
    m = _load()
    with tempfile.TemporaryDirectory() as d:
        led_dir = os.path.join(d, "audit-logs", "governance", "constitution-ledger")
        os.makedirs(led_dir)
        with open(os.path.join(led_dir, "ledger.md"), "w") as f:
            f.write(
                "### Parent KI\n\n"
                "**Refinement — scope-time gate.** body...\n\n"
                "<!-- refinement edge from cpr_can_it_eat_predicate_runs_at_scope_time_tic508 "
                "(tic 508 -> /review 515). Band: COGNITIVE. -->\n\n"
                "<!-- conformation + refinement (tic 491 -> /review 492). "
                "cpr_rehydration_and_ledger_fidelity_test_tic491. -->\n\n"
                "<!-- promoted from cpr_completion_metric_corruption_tic498 (tic 498 -> 515). -->\n"
            )
        # Minimal CLAUDE.md so the candidate-path sweep has its root anchor.
        with open(os.path.join(d, "CLAUDE.md"), "w") as f:
            f.write("# root\n")
        inscribed = m.build_inscribed_index(d)
        for cid in (
            "cpr_can_it_eat_predicate_runs_at_scope_time_tic508",
            "cpr_rehydration_and_ledger_fidelity_test_tic491",
            "cpr_completion_metric_corruption_tic498",
        ):
            assert cid in inscribed, f"build_inscribed_index missed {cid}: {sorted(inscribed)}"


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
