#!/usr/bin/env python3
"""Fixtures for the /review-776 UNIT-RECOMPUTABILITY cure, ruled in one
Architect-ratified round (recommended verbatim, 2/2):

  cpr_mogul_review_close_check_57096af5a389 — ray on
  constitution-ledger#artifact-language-must-not-exceed-its-declared-
  confidence-classification (the UNIT-RECOMPUTABILITY clause): a disclosure
  block publishing a count beside a set it also persists owes a unit sentence
  recomputable FROM that persisted set. Lived t773: layout_churn's unit
  sentence licensed the per-positional-ENTRY population (514) while `members`
  published the per-distinct-CONTENT count (256) — both exact, different
  populations, 258 apart. The cure is a unit restatement plus a per-side
  collapse decomposition, never a value change.

Every documented conditional gets BOTH arms
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths).
The NC predicted-member sets were written to disk BEFORE this suite first ran
(scratchpad nc-predicted-members-tic776.json — prediction-before-observation).
SCOPE HONESTY: fixture-green over synthetic surfaces plus one historical
artifact pin; the live fire is the next review_close_check cycle.

Run:  python3 -m unittest test_review_close_check_unit_recomputability_tic776
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "review_close_check_776", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check_776"] = rcc
_spec.loader.exec_module(rcc)

# The canonical zone root, for the historical-artifact pin (scripts/ sits at
# canonical_developer/context-grapple-gun/cgg-runtime/scripts).
_ZONE_ROOT = _HERE.parents[3]
_T773_ARTIFACT = (_ZONE_ROOT / "audit-logs" / "mogul" / "cycle-reports"
                  / "review-close-checks" / "tic-773-check.json")


def _content(cid):
    parts = str(cid).rsplit("#", 2)
    return f"{parts[0]}#{parts[2]}" if len(parts) == 3 else str(cid)


def _run_attribution(prior_ids, current_ids, tic=776):
    """Drive compute_sibling_pair_attribution with a synthetic prior artifact."""
    with tempfile.TemporaryDirectory() as td:
        prior = {
            "membership_sets": {
                "matched_comment_ids": sorted(prior_ids),
                "matched_comment_id_unit": rcc.MATCHED_COMMENT_ID_UNIT,
            }
        }
        prior_name = f"tic-{tic - 1}-check.json"
        (Path(td) / prior_name).write_text(json.dumps(prior), encoding="utf-8")
        return rcc.compute_sibling_pair_attribution(
            td, f"tic-{tic}-check.json", tic, sorted(current_ids))


class UnitRecomputability(unittest.TestCase):
    """The churn arm: members recomputes from the persisted lists under the
    RESTATED unit, the OLD unit's licensed population disagrees, and the
    collapse names its side."""

    PRIOR = ["a#1#h1", "a#2#h2", "b#1#h3"]
    CURRENT = ["a#2#h1", "a#3#h2", "b#1#h3", "c#1#h4", "c#2#h4"]

    def setUp(self):
        self.block = _run_attribution(self.PRIOR, self.CURRENT)
        self.lc = self.block["layout_churn"]

    def test_unit_sentence_names_the_published_population(self):
        self.assertTrue(self.lc["unit"].startswith("distinct content components"),
                        self.lc["unit"])
        self.assertIn("BOTH sides of the positional difference", self.lc["unit"])

    def test_members_recomputes_from_persisted_lists_under_the_stated_unit(self):
        new = self.block["new_matched_comments"]
        removed = self.block["removed_matched_comments"]
        new_c = {_content(i) for i in new}
        removed_c = {_content(i) for i in removed}
        # The RESTATED unit's population: distinct content components on BOTH sides.
        self.assertEqual(self.lc["members"], len(new_c & removed_c))
        self.assertEqual(self.lc["members"], 2)

    def test_old_unit_licensed_a_different_integer(self):
        """The discriminating control: the prior unit sentence ('members of the
        positional difference whose content component appears on BOTH sides')
        licenses the per-ENTRY population — which must DIFFER here, proving the
        restatement discriminates rather than relabels."""
        new = self.block["new_matched_comments"]
        removed = self.block["removed_matched_comments"]
        new_c = {_content(i) for i in new}
        removed_c = {_content(i) for i in removed}
        per_entry = (sum(1 for i in new if _content(i) in removed_c)
                     + sum(1 for i in removed if _content(i) in new_c))
        self.assertEqual(per_entry, 4)
        self.assertNotEqual(per_entry, self.lc["members"])

    def test_collapse_decomposes_per_side_and_sums_to_the_scalar(self):
        by_side = self.lc["content_collapse_by_side"]
        self.assertEqual(by_side, {"added": 1, "removed": 0})
        self.assertEqual(self.lc["content_collapse"],
                         by_side["added"] + by_side["removed"])

    def test_added_only_content_is_not_the_collapse(self):
        """The mint's own coincidental-identity slip, pinned as law: the
        added-only content set (content_new) and the collapse are DIFFERENT
        quantities that can share a value by coincidence (both were 2 at
        t773). Pin the true DECOMPOSITIONS: members + added-only = added-side
        distinct, and members + removed-only = removed-side distinct — the
        identities the collapse scalar satisfies on neither side here."""
        new = self.block["new_matched_comments"]
        new_c = {_content(i) for i in new}
        content_new = self.block["content_new_matched_comments"]
        self.assertEqual(self.lc["members"] + len(content_new), len(new_c))
        # And the removed-side identity: members + content_removed = removed-side distinct.
        removed = self.block["removed_matched_comments"]
        removed_c = {_content(i) for i in removed}
        content_removed = self.block["content_removed_matched_comments"]
        self.assertEqual(self.lc["members"] + len(content_removed), len(removed_c))


class VacuousArm(unittest.TestCase):
    """The other documented arm: an EMPTY positional difference is a vacuous
    zero, and the by-side decomposition is present and zero on both sides."""

    def test_vacuous_antecedent_and_zero_by_side(self):
        block = _run_attribution(["a#1#h1"], ["a#1#h1"])
        lc = block["layout_churn"]
        self.assertTrue(lc["vacuous_antecedent"])
        self.assertEqual(lc["members"], 0)
        self.assertEqual(lc["content_collapse_by_side"], {"added": 0, "removed": 0})


class HistoricalArtifactPin(unittest.TestCase):
    """The lived t773 member: recompute every figure of the /review-776 ruling
    from the artifact's own persisted lists. The artifact predates the by-side
    field; the recomputation pins what the field would have published."""

    def test_tic773_recomputation(self):
        if not _T773_ARTIFACT.exists():
            self.skipTest(f"historical pin absent: {_T773_ARTIFACT}")
        art = json.loads(_T773_ARTIFACT.read_text(encoding="utf-8"))
        att = art["inscribed_index_delta"]["attribution"]
        new = att["new_matched_comments"]
        removed = att["removed_matched_comments"]
        self.assertEqual((len(new), len(removed)), (259, 257))
        new_c = {_content(i) for i in new}
        removed_c = {_content(i) for i in removed}
        self.assertEqual(att["layout_churn"]["members"], len(new_c & removed_c))
        self.assertEqual(len(new_c & removed_c), 256)
        per_entry = (sum(1 for i in new if _content(i) in removed_c)
                     + sum(1 for i in removed if _content(i) in new_c))
        self.assertEqual(per_entry, 514)
        self.assertEqual(att["layout_churn"]["content_collapse"], 2)
        self.assertEqual((len(new) - len(new_c), len(removed) - len(removed_c)),
                         (1, 1))


if __name__ == "__main__":
    unittest.main()
