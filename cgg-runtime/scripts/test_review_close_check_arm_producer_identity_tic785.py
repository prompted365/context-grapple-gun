"""THE PER-ARM BASELINE-STABILITY face (/review 785,
cpr_mogul_review_close_check_9c38ebdd0b9c, ratified same-pass cure).

Lived shape (t782): a two-fire tic crossed a /review same-pass writer-cure
boundary and BOTH of the close fire's baselines — the cross-tic artifact AND
the same-tic prior — were written by the OLD writer; verdict_counts_delta and
prior_same_tic_observation published attributed movement with zero
producer-identity declaration on those arms. The t784 producer_identity_delta
block discloses the checker's own identity boundary at top level; this face
lands the SAME disclosure per-arm, at the delta block's own altitude.

Cure: _arm_producer_identity(arm_report, current_identity) attaches
{arm_writer_sha256_16, current_writer_sha256_16,
arm_producer_identity_changed, reason_absent} to the cross-tic baseline arm
(block.baseline.producer_identity) and the same-tic prior arm
(prior_same_tic_observation.producer_identity) on BOTH delta blocks. A
declaration, never a verified cross-run state check. Honest nulls for
pre-identity arm artifacts. Occurrence-class: nested producer_identity keys
are stripped recursively from the skip-vs-replace comparison view;
arm_producer_identity_changed stays OUTSIDE EQUALITY_FLAG_NAMES (registry
four, /review-760 ruling) and is disclosed in the audit window's
known-unregistered list.

Run:  python3 -m unittest test_review_close_check_arm_producer_identity_tic785
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent / "review-close-check.py"
_spec = importlib.util.spec_from_file_location("rcc_arm_pid_t785", _SCRIPT)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["rcc_arm_pid_t785"] = rcc
_spec.loader.exec_module(rcc)

_CUR = {"writer_path": "review-close-check.py",
        "writer_sha256_16": "cccccccccccccccc"}


def _write_prior(d, tic, extra):
    body = {"generated_at": "2026-09-08T19:00:00+00:00",
            "inscribed_index_size": 900,
            "inscribed_index_unit": {"matched_comment_count": 940},
            "verdict_counts": {"promoted": 840, "deferred": 3, "skipped": 126}}
    body.update(extra)
    p = os.path.join(d, f"tic-{tic}-check.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(body, fh)
    return p


class TestArmHelperHonestNulls(unittest.TestCase):
    """NC1 — a pre-identity arm artifact yields declared-unmeasured, never
    inferred."""

    def test_pre_identity_arm_yields_reason_absent(self):
        arm = rcc._arm_producer_identity(
            {"generated_at": "2026-09-05T19:00:00+00:00"}, _CUR)
        self.assertIsNone(arm["arm_writer_sha256_16"])
        self.assertIsNone(arm["arm_producer_identity_changed"])
        self.assertEqual(arm["reason_absent"],
                         "arm_artifact_predates_producer_identity")
        self.assertEqual(arm["current_writer_sha256_16"], "cccccccccccccccc")


class TestCrossTicArmDeclaration(unittest.TestCase):
    """NC2 — the cross-tic baseline arm carries its declaration on both
    delta blocks, changed typed by sha comparison."""

    def test_verdict_delta_cross_tic_arm_changed_true(self):
        with tempfile.TemporaryDirectory() as d:
            _write_prior(d, 784, {"producer_identity": {
                "writer_path": "review-close-check.py",
                "writer_sha256_16": "aaaaaaaaaaaaaaaa"}})
            block = rcc.compute_verdict_count_deltas(
                d, "tic-785-check.json", 785,
                {"promoted": 842, "deferred": 3, "skipped": 126},
                current_identity=_CUR)
        arm = block["baseline"]["producer_identity"]
        self.assertEqual(arm["arm_writer_sha256_16"], "aaaaaaaaaaaaaaaa")
        self.assertIs(arm["arm_producer_identity_changed"], True)
        self.assertIsNone(arm["reason_absent"])

    def test_unit_delta_cross_tic_arm_stable_false_changed(self):
        with tempfile.TemporaryDirectory() as d:
            _write_prior(d, 784, {"producer_identity": {
                "writer_path": "review-close-check.py",
                "writer_sha256_16": "cccccccccccccccc"}})
            block = rcc.compute_unit_deltas(
                d, "tic-785-check.json", 785, 902, 942,
                current_identity=_CUR)
        arm = block["baseline"]["producer_identity"]
        self.assertEqual(arm["arm_writer_sha256_16"], "cccccccccccccccc")
        self.assertIs(arm["arm_producer_identity_changed"], False)


class TestSameTicArmDeclaration(unittest.TestCase):
    """NC3 — the same-tic prior arm carries its own declaration; a first-fire
    tic (arm absent) keeps the key shape-stable at None."""

    def test_same_tic_arm_present_and_declared(self):
        with tempfile.TemporaryDirectory() as d:
            # the tic's earlier fire — the same-tic arm — with OLD identity
            with open(os.path.join(d, "tic-785-check.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"generated_at": "2026-09-11T00:00:00+00:00",
                           "producer_identity": {
                               "writer_path": "review-close-check.py",
                               "writer_sha256_16": "bbbbbbbbbbbbbbbb"},
                           "inscribed_index_size": 901,
                           "inscribed_index_unit": {
                               "matched_comment_count": 941},
                           "verdict_counts": {"promoted": 841, "deferred": 3,
                                              "skipped": 126}}, fh)
            block = rcc.compute_verdict_count_deltas(
                d, "tic-785-check.json", 785,
                {"promoted": 842, "deferred": 3, "skipped": 126},
                current_identity=_CUR)
        st = block["prior_same_tic_observation"]
        self.assertTrue(st["present"])
        arm = st["producer_identity"]
        self.assertEqual(arm["arm_writer_sha256_16"], "bbbbbbbbbbbbbbbb")
        self.assertIs(arm["arm_producer_identity_changed"], True)

    def test_first_fire_same_tic_arm_shape_stable_none(self):
        with tempfile.TemporaryDirectory() as d:
            block = rcc.compute_unit_deltas(
                d, "tic-785-check.json", 785, 902, 942,
                current_identity=_CUR)
        st = block["prior_same_tic_observation"]
        self.assertFalse(st["present"])
        self.assertIn("producer_identity", st)
        self.assertIsNone(st["producer_identity"])


class TestOccurrenceClassAndDisclosure(unittest.TestCase):
    """NC4 — the arm declarations cannot flip skip-vs-replace (recursive
    occurrence strip) and the equality-shaped flag is disclosed in the audit
    window with the registry held at four."""

    def test_nested_producer_identity_stripped_from_comparison(self):
        a = {"x": 1, "verdict_counts_delta": {"baseline": {
            "artifact": "tic-784-check.json",
            "producer_identity": {"arm_writer_sha256_16": "aaaaaaaaaaaaaaaa",
                                  "arm_producer_identity_changed": True}}}}
        b = {"x": 1, "verdict_counts_delta": {"baseline": {
            "artifact": "tic-784-check.json",
            "producer_identity": {"arm_writer_sha256_16": "bbbbbbbbbbbbbbbb",
                                  "arm_producer_identity_changed": False}}}}
        self.assertEqual(rcc.normalize_report_for_content_compare(a),
                         rcc.normalize_report_for_content_compare(b))

    def test_registry_four_and_known_unregistered_disclosure(self):
        self.assertEqual(len(rcc.EQUALITY_FLAG_NAMES), 4)
        self.assertNotIn("arm_producer_identity_changed",
                         rcc.EQUALITY_FLAG_NAMES)
        window = rcc.audit_equality_flags_with_window({})["observation_window"]
        self.assertIn("*.producer_identity.arm_producer_identity_changed",
                      window["known_unregistered_equality_shaped_flags"])
        self.assertEqual(window["registry_size"], 4)


if __name__ == "__main__":
    unittest.main()
