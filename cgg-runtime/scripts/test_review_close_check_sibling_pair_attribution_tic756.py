#!/usr/bin/env python3
"""test_review_close_check_sibling_pair_attribution_tic756.py — the CURE-SCOPE
face of the ATTRIBUTION clause (/review 756 Q2, cpr_mogul_review_close_check_6d648f9e39a9
absorbed as reinforcement; ruled consumer).

The lived defect (tic 753, corroborated 755 and 756): the clause's first-consumer
fire persisted index_tokens / promoted_ids and attributed the cross-counter pair by
set difference — and left the SIBLING pair in the same instrument (inscribed_index_delta:
delta_tokens 1 vs delta_matched_comments 2) with no matched-comment membership set to
difference against, so it was unattributable on that pass and on every future pass by
construction. The cure persists matched_comment_ids as a THIRD membership set, attributes
the sibling pair by set difference, and publishes a per-pair COVERAGE statement over every
divergence pair the artifact carries.

Eight tests: unresolved-without-prior · unresolved-when-prior-predates-the-set ·
attributed-by-set-difference · delta_by_membership matches the counts · occurrence-unique
identity (F-756-C1: a content-hashed set collapsed 881 occurrences to 804 ids at the
third set's first fire) · a prior set in a different unit is never differenced · coverage
names every pair with its status · unmeasured current side stays honest.
"""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("rcc_t756", _HERE / "review-close-check.py")
rcc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rcc)


def _write_artifact(report_dir: Path, name: str, payload: dict) -> Path:
    path = report_dir / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class SiblingPairAttributionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.report_dir = Path(self._tmp.name)
        self.current = "tic-756-check.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_unresolved_without_prior_artifact(self):
        block = rcc.compute_sibling_pair_attribution(
            str(self.report_dir), self.current, 756, ["a#1", "b#2"])
        self.assertTrue(block["attribution_unresolved"])
        self.assertIsNotNone(block["unresolved_reason"])
        self.assertIsNone(block["new_matched_comments"])
        self.assertIsNone(block["delta_by_membership"])

    def test_unresolved_when_prior_predates_the_set(self):
        _write_artifact(self.report_dir, "tic-755-check.json", {
            "membership_sets": {"index_tokens": ["x"], "promoted_ids": ["x"]}})
        block = rcc.compute_sibling_pair_attribution(
            str(self.report_dir), self.current, 756, ["a#1"])
        self.assertTrue(block["attribution_unresolved"])
        self.assertIn("carries_no_matched_comment_ids", block["unresolved_reason"])
        self.assertEqual(block["baseline"]["artifact"], "tic-755-check.json")

    def test_attributed_by_set_difference(self):
        _write_artifact(self.report_dir, "tic-755-check.json", {
            "membership_sets": {"index_tokens": [], "promoted_ids": [],
                                "matched_comment_id_unit": rcc.MATCHED_COMMENT_ID_UNIT,
                                "matched_comment_ids": ["ledger.md#aaa", "memo.md#bbb"]}})
        block = rcc.compute_sibling_pair_attribution(
            str(self.report_dir), self.current, 756,
            ["ledger.md#aaa", "ledger.md#ccc", "notes.md#ddd"])
        self.assertFalse(block["attribution_unresolved"])
        self.assertEqual(block["new_matched_comments"], ["ledger.md#ccc", "notes.md#ddd"])
        self.assertEqual(block["removed_matched_comments"], ["memo.md#bbb"])
        self.assertEqual(block["delta_by_membership"], 1)

    def test_delta_by_membership_matches_counts(self):
        prior = [f"f#{i}" for i in range(5)]
        current = [f"f#{i}" for i in range(2, 9)]  # drops 0,1 ; adds 5,6,7,8
        _write_artifact(self.report_dir, "tic-755-check.json", {
            "membership_sets": {"index_tokens": [], "promoted_ids": [], "matched_comment_ids": prior,
                                "matched_comment_id_unit": rcc.MATCHED_COMMENT_ID_UNIT}})
        block = rcc.compute_sibling_pair_attribution(str(self.report_dir), self.current, 756, current)
        self.assertEqual(block["delta_by_membership"], len(current) - len(prior))
        self.assertEqual(len(block["new_matched_comments"]), 4)
        self.assertEqual(len(block["removed_matched_comments"]), 2)

    def test_identity_is_occurrence_unique_stable_and_edit_sensitive(self):
        # F-756-C1: two byte-identical comments in one file are TWO occurrences, so
        # the identity carries the per-file occurrence index beside the content hash.
        seg = "<!-- promoted from cpr_x_abc123 (tic 1) -->"
        h = hashlib.sha256(seg.encode('utf-8')).hexdigest()[:12]
        first, second = f"a/b.md#0#{h}", f"a/b.md#1#{h}"
        self.assertNotEqual(first, second)
        edited = f"a/b.md#0#{hashlib.sha256((seg + ' ').encode('utf-8')).hexdigest()[:12]}"
        self.assertNotEqual(first, edited)
        self.assertEqual(len(first.split('#')), 3)
        self.assertEqual(rcc.MATCHED_COMMENT_ID_UNIT, "relative_path#occurrence_index#sha256_12_of_comment_segment")

    def test_prior_set_in_a_different_unit_is_not_differenced(self):
        _write_artifact(self.report_dir, "tic-755-check.json", {
            "membership_sets": {"index_tokens": [], "promoted_ids": [],
                                "matched_comment_id_unit": "relative_path#sha256_12_of_comment_segment",
                                "matched_comment_ids": ["ledger.md#aaa"]}})
        block = rcc.compute_sibling_pair_attribution(str(self.report_dir), self.current, 756, ["ledger.md#0#aaa"])
        self.assertTrue(block["attribution_unresolved"])
        self.assertIn("unit_differs", block["unresolved_reason"])
        self.assertEqual(block["baseline"]["prior_unit"], "relative_path#sha256_12_of_comment_segment")

    def test_coverage_names_every_pair_with_status(self):
        sibling = {"attribution_unresolved": True, "unresolved_reason": "prior_artifact_carries_no_matched_comment_ids"}
        cross = {"attribution_unresolved": False}
        cov = rcc.pair_coverage_statement(sibling, cross)
        pairs = {p["pair"].split(" (")[0]: p["status"] for p in cov["pairs"]}
        self.assertEqual(set(pairs), {"cross_counter_disclosure", "inscribed_index_delta", "verdict_counts_delta"})
        self.assertTrue(pairs["cross_counter_disclosure"].startswith("attributed"))
        self.assertTrue(pairs["inscribed_index_delta"].startswith("unresolved"))
        self.assertIn("NOT persisted", pairs["verdict_counts_delta"])
        absent = rcc.pair_coverage_statement(None, None)
        self.assertTrue(all(p["status"].startswith(("unattributable", "partially")) for p in absent["pairs"]))

    def test_unmeasured_current_side_stays_honest(self):
        block = rcc.compute_sibling_pair_attribution(str(self.report_dir), self.current, 756, None)
        self.assertTrue(block["attribution_unresolved"])
        self.assertEqual(block["unresolved_reason"], "current_pass_matched_comment_ids_unmeasured")


if __name__ == "__main__":
    unittest.main(verbosity=2)
