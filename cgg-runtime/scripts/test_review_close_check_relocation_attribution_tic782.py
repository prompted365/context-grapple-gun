#!/usr/bin/env python3
"""THE RELOCATION face fixtures (/review 782, cpr_mogul_review_close_check_e1365f4a14b3,
ratified same-pass cure).

Pins the two halves of the cure, both arms of each documented conditional:
  (1) compute_sibling_pair_attribution's SUCCESS path publishes attribution_basis
      (content projection = IDENTITY, occurrence_index = ADDRESS) and
      attribution_fields routing — strictly ADDITIVE beside the /review-761
      KEEP-BOTH-COMPONENTS fields, whose pinned semantics are untouched.
  (2) the UNRESOLVED path does NOT carry the basis (nothing fabricated from an
      absent measurement — the skeleton's honest shape is unchanged).
  (3) pair_coverage_statement's sibling-pair ATTRIBUTED status names the stable
      (path, content_hash) projection while keeping the "attributed" prefix the
      t756 pins require.
  (4) the sibling-pair UNRESOLVED status is untouched by the restatement (the
      restatement fires only on the attributed arm).

Run: python3 -m pytest -q cgg-runtime/scripts/test_review_close_check_relocation_attribution_tic782.py
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "review_close_check", _HERE / "review-close-check.py")
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check"] = rcc
_spec.loader.exec_module(rcc)


def _write_prior(report_dir, comment_ids):
    (report_dir / "tic-700-check.json").write_text(json.dumps({
        "inscribed_index_size": 0,
        "inscribed_index_unit": {"matched_comment_count": len(comment_ids)},
        "membership_sets": {
            "index_tokens": [], "promoted_ids": [],
            "matched_comment_id_unit": rcc.MATCHED_COMMENT_ID_UNIT,
            "matched_comment_ids": comment_ids,
        },
    }), encoding="utf-8")


class RelocationAttributionBasis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.report_dir = Path(self.tmp.name)
        self.current = "tic-782-check.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_success_path_publishes_basis_and_routing(self):
        _write_prior(self.report_dir, ["a.md#0#111111111111"])
        block = rcc.compute_sibling_pair_attribution(
            str(self.report_dir), self.current, 782,
            ["a.md#0#111111111111", "a.md#1#222222222222"])
        self.assertFalse(block["attribution_unresolved"])
        basis = block["attribution_basis"]
        self.assertEqual(basis["attribution_runs_on"], "content_projection")
        self.assertIn("occurrence_index", basis["address_components"])
        routing = block["attribution_fields"]
        self.assertIn("delta_by_content_membership", routing["attribution"])
        self.assertIn("delta_by_membership", routing["addressing"])
        # /review-761 KEEP-BOTH-COMPONENTS: the pinned positional semantics stand.
        self.assertEqual(block["new_matched_comments"], ["a.md#1#222222222222"])
        self.assertEqual(block["delta_by_membership"], 1)
        self.assertEqual(block["content_new_matched_comments"], ["a.md#222222222222"])

    def test_unresolved_path_carries_no_basis(self):
        # No prior artifact — the honest UNRESOLVED arm: nothing fabricated.
        block = rcc.compute_sibling_pair_attribution(
            str(self.report_dir), self.current, 782, ["a.md#0#111111111111"])
        self.assertTrue(block["attribution_unresolved"])
        self.assertNotIn("attribution_basis", block)
        self.assertNotIn("attribution_fields", block)

    def test_pair_coverage_attributed_status_names_stable_projection(self):
        sibling = {"attribution_unresolved": False}
        cross = {"attribution_unresolved": False}
        cov = rcc.pair_coverage_statement(sibling, cross)
        pairs = {p["pair"].split(" (")[0]: p["status"] for p in cov["pairs"]}
        sib = pairs["inscribed_index_delta"]
        self.assertTrue(sib.startswith("attributed"))
        self.assertIn("content_hash", sib)
        self.assertIn("ADDRESSING", sib)
        # The cross pair's populations use naturally-stable cpr ids (the row's
        # PLE facet) — its status text is NOT restated.
        self.assertEqual(
            pairs["cross_counter_disclosure"],
            "attributed — by set difference over persisted membership sets")

    def test_pair_coverage_unresolved_arm_untouched(self):
        sibling = {"attribution_unresolved": True,
                   "unresolved_reason": "prior_artifact_carries_no_matched_comment_ids"}
        cov = rcc.pair_coverage_statement(sibling, None)
        pairs = {p["pair"].split(" (")[0]: p["status"] for p in cov["pairs"]}
        self.assertTrue(pairs["inscribed_index_delta"].startswith("unresolved"))
        self.assertNotIn("content_hash", pairs["inscribed_index_delta"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
