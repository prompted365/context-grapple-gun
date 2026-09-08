#!/usr/bin/env python3
"""Fixtures for the /review-784 PRODUCER-IDENTITY BASELINE cure, Architect-ratified
in one round (recommended verbatim, Q2):

  cpr_mogul_review_close_check_0feb4176272e — a producer-identity EQUALITY
  banked across a /review boundary is unsound at composition whenever the
  docket names the instrument as a same-pass cure surface, and the instrument
  cannot warn the banker because producer_identity was the one cross-pass
  quantity published WITHOUT a baseline block.

  Cure: compute_producer_identity_delta reuses the SAME tic-keyed baseline
  selector the measured arms resolve (_find_prior_check_artifact) and
  publishes {baseline{artifact, selector, reason_absent}, prior_writer_
  sha256_16, current_writer_sha256_16, producer_identity_changed} — so the
  instrument self-discloses its own mutation in the pass series, exactly as
  it already does in the supersession lane. Occurrence-class: the block
  rides _COMPARE_VOLATILE_KEYS and cannot flip skip-vs-replace; the flag
  stays OUTSIDE EQUALITY_FLAG_NAMES (registry four, /review-760 ruling) and
  is disclosed in the audit window's known-unregistered list.

Every documented conditional gets BOTH arms
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths).
SCOPE HONESTY: fixture-green over synthetic surfaces; the first live
emission is the tic-784 CLOSE fire (banked: changed=true with prior
c55dca32db418468 — the cure disclosing its own landing).

Run:  python3 -m unittest test_review_close_check_producer_identity_delta_tic784
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE / "review-close-check.py"
_spec = importlib.util.spec_from_file_location(
    "review_close_check_784", _SCRIPT
)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check_784"] = rcc
_spec.loader.exec_module(rcc)

_CURRENT = {"writer_path": "review-close-check.py",
            "writer_sha256_16": "aaaaaaaaaaaaaaaa"}


def _write_prior(report_dir, tic, body):
    p = Path(report_dir) / f"tic-{tic}-check.json"
    p.write_text(json.dumps(body), encoding="utf-8")
    return p


class TestProducerIdentityDeltaBaselineAbsent(unittest.TestCase):
    """Arm 1 — no prior pass artifact: nulls with the reason, never zeros."""

    def test_no_prior_artifact_yields_honest_nulls(self):
        with tempfile.TemporaryDirectory() as d:
            block = rcc.compute_producer_identity_delta(
                d, "tic-784-check.json", 784, _CURRENT)
        self.assertTrue(block["delta_baseline_absent"])
        self.assertIsNone(block["producer_identity_changed"])
        self.assertIsNone(block["prior_writer_sha256_16"])
        self.assertEqual(block["baseline"]["reason_absent"],
                         "no_prior_pass_artifact")
        self.assertEqual(block["current_writer_sha256_16"], "aaaaaaaaaaaaaaaa")


class TestProducerIdentityDeltaEqualArm(unittest.TestCase):
    """Arm 2 — prior stamped the SAME sha: changed=False, selector named."""

    def test_equal_sha_reads_changed_false_via_shared_selector(self):
        with tempfile.TemporaryDirectory() as d:
            _write_prior(d, 783, {"producer_identity": {
                "writer_path": "review-close-check.py",
                "writer_sha256_16": "aaaaaaaaaaaaaaaa"}})
            block = rcc.compute_producer_identity_delta(
                d, "tic-784-check.json", 784, _CURRENT)
        self.assertFalse(block["delta_baseline_absent"])
        self.assertIs(block["producer_identity_changed"], False)
        self.assertEqual(block["prior_writer_sha256_16"], "aaaaaaaaaaaaaaaa")
        self.assertEqual(block["baseline"]["artifact"], "tic-783-check.json")
        # The SAME selector the measured arms resolve — the cure's whole point.
        self.assertEqual(block["baseline"]["selector"],
                         "tic_keyed_prior_tic_783")


class TestProducerIdentityDeltaChangedArm(unittest.TestCase):
    """Arm 3 — prior stamped a DIFFERENT sha: changed=True, a typed boundary."""

    def test_differing_sha_reads_changed_true(self):
        with tempfile.TemporaryDirectory() as d:
            _write_prior(d, 783, {"producer_identity": {
                "writer_path": "review-close-check.py",
                "writer_sha256_16": "bbbbbbbbbbbbbbbb"}})
            block = rcc.compute_producer_identity_delta(
                d, "tic-784-check.json", 784, _CURRENT)
        self.assertIs(block["producer_identity_changed"], True)
        self.assertEqual(block["prior_writer_sha256_16"], "bbbbbbbbbbbbbbbb")
        self.assertFalse(block["delta_baseline_absent"])


class TestProducerIdentityDeltaPreCurePriorAndVolatility(unittest.TestCase):
    """Arm 4 — a pre-cure prior (no stamp) is UNMEASURED never inferred; and
    the block is occurrence-class (volatile, cannot flip skip-vs-replace)."""

    def test_pre_cure_prior_honest_null_and_volatile_exclusion(self):
        with tempfile.TemporaryDirectory() as d:
            _write_prior(d, 783, {"inscribed_index_size": 1})
            block = rcc.compute_producer_identity_delta(
                d, "tic-784-check.json", 784, _CURRENT)
        self.assertTrue(block["delta_baseline_absent"])
        self.assertIsNone(block["producer_identity_changed"])
        self.assertEqual(block["baseline"]["reason_absent"],
                         "prior_artifact_predates_producer_identity")
        # Occurrence-class: rides the volatile set, stripped from the
        # skip-vs-replace comparison view — a writer change alone must never
        # manufacture a supersession (the /review-775 discriminator).
        self.assertIn("producer_identity_delta", rcc._COMPARE_VOLATILE_KEYS)
        view = rcc.normalize_report_for_content_compare(
            {"x": 1, "producer_identity_delta": block})
        self.assertNotIn("producer_identity_delta", view)
        # Disclosed in the audit's observation window, registry held at four
        # (the /review-760 ruling not widened at build altitude).
        window = rcc.audit_equality_flags_with_window({})["observation_window"]
        self.assertIn("producer_identity_delta.producer_identity_changed",
                      window["known_unregistered_equality_shaped_flags"])
        self.assertEqual(window["registry_size"], 4)


if __name__ == "__main__":
    unittest.main()
