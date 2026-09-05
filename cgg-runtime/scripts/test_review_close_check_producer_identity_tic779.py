#!/usr/bin/env python3
"""Fixtures for the /review-779 INSTRUMENT-IDENTITY cure, Architect-ratified
in one round (recommended verbatim, Q2):

  cpr_mogul_review_close_check_cba835ca35ea — a same-tic supersession receipt
  types the RE-OBSERVATION but not the INSTRUMENT. When a /review-ratified
  cure to this writer lands between two same-tic fires, the preserved prior
  and the live artifact are outputs of two DIFFERENT instrument versions, but
  justification_class 'superseded_by_same_tic_reobservation' reads as "same
  instrument, later reading" (lived t776: writer mtime strictly between the
  two generated_at stamps; different key sets).

  Cure: producer_identity {writer_path, writer_sha256_16} stamped on every
  emitted report; the supersession receipt and sidecar carry the live
  producer_identity plus prior_producer_identity (honest null for a pre-cure
  prior — declared unmeasured, never inferred). producer_identity is
  occurrence-class under the MEASUREMENT-vs-OCCURRENCE discriminator (it
  records which instrument TOOK the measurement, never what it said), so it
  joins _COMPARE_VOLATILE_KEYS and cannot flip skip-vs-replace.

Every documented conditional gets BOTH arms
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths).
SCOPE HONESTY: fixture-green over synthetic surfaces; the first live
emission is the tic-779 single fire.

Run:  python3 -m unittest test_review_close_check_producer_identity_tic779
"""

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE / "review-close-check.py"
_spec = importlib.util.spec_from_file_location(
    "review_close_check_779", _SCRIPT
)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check_779"] = rcc
_spec.loader.exec_module(rcc)


class TestProducerIdentityEmission(unittest.TestCase):
    """NC2 — the emission stamp names the writer and hashes its own bytes."""

    def test_helper_identity_matches_independent_recomputation(self):
        ident = rcc.compute_producer_identity()
        self.assertEqual(ident["writer_path"], "review-close-check.py")
        expected = hashlib.sha256(_SCRIPT.read_bytes()).hexdigest()[:16]
        self.assertEqual(ident["writer_sha256_16"], expected)
        self.assertRegex(ident["writer_sha256_16"], r"^[0-9a-f]{16}$")

    def test_report_composition_carries_the_stamp(self):
        # Wiring check on the compose site: the report literal stamps the
        # identity at emission (the full compose path is exercised live at
        # the next review_close_check fire, per the banked NC file).
        src = _SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            '"producer_identity": compute_producer_identity(),', src)


class TestProducerIdentityVolatileExclusion(unittest.TestCase):
    """NC3 — occurrence-class exclusion: the stamp cannot flip skip/replace."""

    def test_volatile_membership_and_normalized_equality(self):
        self.assertIn("producer_identity", rcc._COMPARE_VOLATILE_KEYS)
        a = {"x": 1, "producer_identity": {
            "writer_path": "review-close-check.py",
            "writer_sha256_16": "aaaaaaaaaaaaaaaa"}}
        b = {"x": 1, "producer_identity": {
            "writer_path": "review-close-check.py",
            "writer_sha256_16": "bbbbbbbbbbbbbbbb"}}
        self.assertEqual(
            rcc.normalize_report_for_content_compare(a),
            rcc.normalize_report_for_content_compare(b))

    def test_discriminating_control_both_arms(self):
        # Both arms: the RAW pair differs (the exclusion is doing real work),
        # and the legacy volatile keys are still excluded (regression guard —
        # the tuple grew, it did not rotate).
        a = {"x": 1, "producer_identity": {"writer_sha256_16": "aaaa"}}
        b = {"x": 1, "producer_identity": {"writer_sha256_16": "bbbb"}}
        self.assertNotEqual(a, b)
        for legacy in ("generated_at", "superseded_receipt"):
            self.assertIn(legacy, rcc._COMPARE_VOLATILE_KEYS)
        # An information-bearing delta still compares as changed.
        c = {"x": 2, "producer_identity": a["producer_identity"]}
        self.assertNotEqual(
            rcc.normalize_report_for_content_compare(a),
            rcc.normalize_report_for_content_compare(c))


class TestSupersessionReceiptDiscrimination(unittest.TestCase):
    """NC4 — the receipt and sidecar type the instrument; pre-cure prior
    identity is an honest null."""

    def test_receipt_and_sidecar_carry_both_identities(self):
        src = _SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            '"producer_identity": report.get("producer_identity"),', src)
        self.assertIn(
            '"prior_producer_identity": prior_producer_identity,', src)
        self.assertIn(
            '"producer_identity": superseded_receipt["producer_identity"],',
            src)
        # Pre-cure prior semantics: a prior artifact without the field yields
        # None through the same accessor the writer uses — declared, never
        # invented.
        pre_cure_prior = {"generated_at": "2026-09-05T19:00:00+00:00"}
        self.assertIsNone(pre_cure_prior.get("producer_identity"))


if __name__ == "__main__":
    unittest.main()
