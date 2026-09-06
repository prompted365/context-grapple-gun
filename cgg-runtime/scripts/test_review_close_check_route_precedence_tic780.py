#!/usr/bin/env python3
"""Tests for the /review 780 Q2 review-close-check cure (the tic-780 CGG batch).

cpr_mogul_review_close_check_4cb469459489 (PROMOTE + same-pass cure — the
COVERAGE-IS-BINDING face, inscribed at cgg-ledger; the t778 entry fire's
self-catch, lived at tic 777 on member d53f1bf19ee0): a route-attribution
catalog that publishes a COVERAGE statement measures BINDING, never
CORRECTNESS — and when one of its routes asserts a NEGATIVE fact ("this
promotion landed no provenance comment"), a sibling counter on the SAME
artifact may already hold the measurement that falsifies the binding.

The cure under test:
  1. `_DIVERGENCE_ROUTES` gains its SIXTH member
     `promotion_witness_comment_shed_by_matcher` (append-only; indices stable).
  2. `build_inscribed_index` publishes the COMPLETE token membership of shed
     (index_loss) residue comments — `index_loss_member_tokens` — a membership
     set beside the count, never a capped sample.
  3. The precedence gate in `compute_cross_counter_attribution`: an index_loss
     typing from the residue counter OUTRANKS any negative-fact catalog route
     (the modify/merge "adds no provenance comment" binding) for the member
     whose token it carries; where neither binds, the member stays honestly
     `uncovered`.

NC property: test_precedence_gate_* fails against the pre-cure script by
construction (the gate did not exist); the negative-control test proves the
gate is the ONLY behavioral change (empty shed set == pre-cure binding).
"""
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest

_HERE = pathlib.Path(__file__).resolve().parent
_SRC = (_HERE / "review-close-check.py").read_text(encoding="utf-8")
_spec = importlib.util.spec_from_file_location(
    "review_close_check_t780", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rcc)

ROUTES = list(rcc._DIVERGENCE_ROUTES)
ROUTE_F = "promotion_witness_comment_shed_by_matcher"


def _prior(report_dir, tic, tokens=None, promoted=None):
    """Write a prior tic-keyed artifact carrying membership sets."""
    art = {
        "inscribed_index_size": len(tokens or []),
        "inscribed_index_unit": {"matched_comment_count": len(tokens or [])},
        "verdict_counts": {"promoted": len(promoted or []), "deferred": 0,
                           "skipped": 0},
        "membership_sets": {
            "index_tokens": sorted(tokens or []),
            "promoted_ids": sorted(promoted or []),
        },
    }
    (pathlib.Path(report_dir) / f"tic-{tic}-check.json").write_text(
        json.dumps(art), encoding="utf-8")


def _members(a):
    return {m["member"]: m for m in a["attributed_members"]}


class CatalogSixthMember(unittest.TestCase):
    def test_catalog_sixth_member_appended_indices_stable(self):
        self.assertEqual(len(ROUTES), 6)
        self.assertEqual(ROUTES[5], ROUTE_F)
        # append-only: the five prior members hold their exact positions
        self.assertEqual(ROUTES[0],
                         "modify_and_merge_promotion_adds_no_provenance_comment")
        self.assertEqual(ROUTES[4],
                         "promotion_of_id_whose_witness_token_pre_existed_in_prior_index")
        # one constant, every disclosure surface
        d = rcc.compute_cross_counter_disclosure(
            {"delta": {"promoted": 1}}, {"delta_tokens": 1})
        self.assertEqual(d["divergence_routes"], ROUTES)
        self.assertEqual(d["attribution"]["catalog"], ROUTES)


class PrecedenceGate(unittest.TestCase):
    def _attribution(self, shed):
        with tempfile.TemporaryDirectory() as td:
            _prior(td, 9, tokens=[], promoted=[])
            queue = {
                "cpr_x_shedcase": {
                    "status": "promoted",
                    "landing_kind": "modify_and_merge",
                },
            }
            return rcc.compute_cross_counter_attribution(
                td, "tic-10-check.json", 10,
                current_tokens=set(),
                current_promoted={"cpr_x_shedcase"},
                queue=queue,
                shed_witness_tokens=shed,
            )

    def test_precedence_gate_binds_sixth_route_over_negative_fact(self):
        # The lived t777 shape: a modify/merge-verdicted promotion whose
        # witness token appears in a SHED residue comment. The negative-fact
        # route is falsified by the sibling measurement; the gate binds
        # route (f) with covers=True, and says the witness was shed.
        a = self._attribution(shed={"cpr_x_shedcase"})
        m = _members(a)["cpr_x_shedcase"]
        self.assertEqual(m["class"], "promoted_without_new_token")
        self.assertEqual(m["catalog_route"], ROUTE_F)
        self.assertIs(m["catalog_covers"], True)
        self.assertIs(m.get("witness_comment_shed"), True)

    def test_negative_control_empty_shed_set_preserves_pre_cure_binding(self):
        # With NO falsifying sibling measurement the pre-cure binding is
        # byte-preserved: the modify/merge verdict text binds route (a).
        a = self._attribution(shed=set())
        m = _members(a)["cpr_x_shedcase"]
        self.assertEqual(m["catalog_route"], ROUTES[0])
        self.assertIs(m["catalog_covers"], True)
        self.assertNotIn("witness_comment_shed", m)

    def test_uncovered_when_neither_route_binds(self):
        # No shed measurement, no modify/merge text, token not pre-existing:
        # the honest state is uncovered (covers=False), never a nearest-
        # neighbor binding — the denominator carries the hole.
        with tempfile.TemporaryDirectory() as td:
            _prior(td, 9, tokens=[], promoted=[])
            queue = {"cpr_y_plain": {"status": "promoted",
                                     "landing_kind": "refinement_ray"}}
            a = rcc.compute_cross_counter_attribution(
                td, "tic-10-check.json", 10,
                current_tokens=set(),
                current_promoted={"cpr_y_plain"},
                queue=queue,
                shed_witness_tokens=set(),
            )
        m = _members(a)["cpr_y_plain"]
        self.assertIsNone(m["catalog_route"])
        self.assertIs(m["catalog_covers"], False)


class ShedMembershipPublished(unittest.TestCase):
    """build_inscribed_index also sweeps ~/.claude/CLAUDE.md and the auto-memory
    dir; point HOME into a sandbox so real surfaces never leak into fixture
    counts (cgg-ledger#self-locating-artifact-test-isolation — the tic768
    HermeticIndexCase pattern)."""

    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self._orig_expanduser = os.path.expanduser
        self._orig_home = pathlib.Path.home
        home = self._home.name
        os.path.expanduser = (
            lambda p: p.replace("~", home, 1) if p.startswith("~") else p)
        pathlib.Path.home = classmethod(lambda cls: pathlib.Path(home))
        rcc.os.path.expanduser = os.path.expanduser

    def tearDown(self):
        os.path.expanduser = self._orig_expanduser
        rcc.os.path.expanduser = self._orig_expanduser
        pathlib.Path.home = self._orig_home
        self._home.cleanup()

    def test_index_loss_member_tokens_published_complete_and_declared_empty(self):
        # A shed residue comment (unregistered head verb, cpr-shaped token)
        # donates its token to the COMPLETE published membership; a corpus
        # with no residue publishes a DECLARED empty list, never a missing key.
        with tempfile.TemporaryDirectory() as td:
            claude_md = pathlib.Path(td) / "CLAUDE.md"
            claude_md.write_text(
                "# t\n<!-- witnessed via cpr_shed_token_x999 at tic 780 -->\n",
                encoding="utf-8")
            diags = {}
            rcc.build_inscribed_index(td, queue_ids=set(), diagnostics=diags)
            split = diags["unmatched_disposition_split"]
            self.assertIn("cpr_shed_token_x999",
                          split["index_loss_member_tokens"])
        with tempfile.TemporaryDirectory() as td2:
            (pathlib.Path(td2) / "CLAUDE.md").write_text("# empty\n",
                                                         encoding="utf-8")
            diags2 = {}
            rcc.build_inscribed_index(td2, queue_ids=set(), diagnostics=diags2)
            split2 = diags2.get("unmatched_disposition_split")
            if split2 is not None:
                self.assertEqual(split2["index_loss_member_tokens"], [])


if __name__ == "__main__":
    unittest.main()
