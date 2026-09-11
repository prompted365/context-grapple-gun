#!/usr/bin/env python3
"""THE BASELINE-COINCIDENCE face — fixtures (/review 787,
cpr_mogul_review_close_check_7d3ae95bceeb, ratified same-pass cure).

Guards compute_baseline_coincidence: the collapse-candidate typing between the
two instrument-identity lanes (within-tic supersession prior vs cross-tic
pass-series prior). Every documented conditional gets a fixture, BOTH arms
(the selftest-fixtures law, cgg-ledger#selftest-fixtures-must-exercise-
documented-conditional-paths): non-vacuous coincidence w/ timing condition,
vacuous coincidence, honest divergence, and the four honest-null lane-absent
shapes. Also guards the registry discipline: both new booleans stay OUTSIDE
EQUALITY_FLAG_NAMES (registry stays FOUR per /review-760, re-ruled /review
787) while being disclosed in the audit window's known-unregistered list.
"""
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE / "review-close-check.py"

_load_seq = 0


def _load_module():
    global _load_seq
    _load_seq += 1
    spec = importlib.util.spec_from_file_location(
        f"review_close_check_bc_fixture_{_load_seq}", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sup(prior_sha):
    return {"prior_producer_identity": {"writer_path": "review-close-check.py",
                                        "writer_sha256_16": prior_sha}}


def _pid(prior_sha, current_sha):
    return {"prior_writer_sha256_16": prior_sha,
            "current_writer_sha256_16": current_sha}


def test_non_vacuous_coincidence_names_timing_condition():
    # The lived t784 shape: both priors equal, current differs — a writer
    # change landed between the within-tic prior fire and this fire.
    mod = _load_module()
    block = mod.compute_baseline_coincidence(
        _sup("c55dca32db418468"), _pid("c55dca32db418468", "91d99d4337b48792"))
    assert block["baseline_coincidence_this_pass"] is True
    assert block["baseline_coincidence_vacuous"] is False
    assert block["timing_condition"] is not None
    assert "BETWEEN" in block["timing_condition"]
    assert block["lanes_absent"] == []


def test_vacuous_coincidence_when_no_boundary_in_either_lane():
    # Agreement with prior == current everywhere: one instrument throughout —
    # the equality types nothing (GUARD-19 vacuity arm).
    mod = _load_module()
    block = mod.compute_baseline_coincidence(
        _sup("aaaa000011112222"), _pid("aaaa000011112222", "aaaa000011112222"))
    assert block["baseline_coincidence_this_pass"] is True
    assert block["baseline_coincidence_vacuous"] is True
    assert block["timing_condition"] is None


def test_divergence_is_measured_false_not_null():
    # The two lanes answering their two different questions — measured
    # disagreement, never an error and never an unmeasured null.
    mod = _load_module()
    block = mod.compute_baseline_coincidence(
        _sup("c55dca32db418468"), _pid("91d99d4337b48792", "8e98f1cc7122879d"))
    assert block["baseline_coincidence_this_pass"] is False
    assert block["baseline_coincidence_vacuous"] is False
    assert block["timing_condition"] is None
    assert block["lanes_absent"] == []


def test_no_supersession_lane_honest_absent():
    # The common single-fire pass: no within-tic supersession — the block
    # still emits, the absent lane NAMED, coincidence unmeasured.
    mod = _load_module()
    block = mod.compute_baseline_coincidence(
        None, _pid("91d99d4337b48792", "8e98f1cc7122879d"))
    assert block["baseline_coincidence_this_pass"] is None
    assert block["baseline_coincidence_vacuous"] is None
    assert "no_within_tic_supersession_this_pass" in block["lanes_absent"]
    assert block["pass_series_prior_writer_sha256_16"] == "91d99d4337b48792"


def test_pre_cure_supersession_prior_unmeasured_never_inferred():
    # A supersession over a pre-cure prior that never stamped its identity —
    # unmeasured, never inferred.
    mod = _load_module()
    block = mod.compute_baseline_coincidence(
        {"prior_producer_identity": None},
        _pid("91d99d4337b48792", "8e98f1cc7122879d"))
    assert block["baseline_coincidence_this_pass"] is None
    assert ("supersession_prior_unmeasured_pre_cure_prior"
            in block["lanes_absent"])


def test_pass_series_baseline_unmeasured_lane_named():
    # First-pass / unreadable-prior shapes upstream leave the pass-series
    # prior None — the lane is named, coincidence unmeasured.
    mod = _load_module()
    block = mod.compute_baseline_coincidence(
        _sup("c55dca32db418468"), _pid(None, "8e98f1cc7122879d"))
    assert block["baseline_coincidence_this_pass"] is None
    assert "pass_series_baseline_unmeasured" in block["lanes_absent"]
    assert block["supersession_prior_writer_sha256_16"] == "c55dca32db418468"


def test_registry_stays_four_and_flags_disclosed_and_volatile():
    # The /review-787 registry ruling, mechanically held: EQUALITY_FLAG_NAMES
    # stays FOUR; both new booleans appear in the audit window's
    # known-unregistered disclosure; the block rides the volatile set so it
    # cannot flip skip-vs-replace.
    mod = _load_module()
    assert len(mod.EQUALITY_FLAG_NAMES) == 4
    assert "baseline_coincidence_this_pass" not in mod.EQUALITY_FLAG_NAMES
    audit = mod.audit_equality_flags_with_window({})
    disclosed = audit["observation_window"][
        "known_unregistered_equality_shaped_flags"]
    assert "baseline_coincidence.baseline_coincidence_this_pass" in disclosed
    assert "baseline_coincidence.baseline_coincidence_vacuous" in disclosed
    assert "baseline_coincidence" in mod._COMPARE_VOLATILE_KEYS
