#!/usr/bin/env python3
"""Fixtures for the /review 812 Q2 review-close-check cure (built tic 822).

cpr_mogul_review_close_check_86165cdd977a, promoted MODIFIED at /review 812 as
the MEANING-ONLY-SPLIT face on the CGG ledger's loud-counter block:

  The stderr banner and the dormant attribution route note each NAME the
  `index_loss` sub-types WITH THEIR COUNTS and route each to ITS cure —
  `index_loss_id_absent` -> a real index hole, cure it;
  `index_loss_comment_only` -> zero index consequence, a vocabulary
  registration at most. The counter stays LOUD in both sub-types. The two
  membership formulas and `_DISPOSITION_TEXT` are byte-unchanged.

WHAT THE CURE ANSWERS: at every check-bearing fire from tic 804 through 812 the
banner told its reader "index_loss = a real witness lost from the index, cure
it" while the artifact's own `index_loss_subtype_counts` read
`index_loss_id_absent` 0 / `index_loss_comment_only` 2 — zero index holes, and
comments whose every token was already indexed by another witness. The
sub-type counts were computed a few lines above the banner and referenced
nowhere in the print. A loud counter that mis-types its own residue spends the
attention it exists to command.

DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT register the
unregistered head verb that sheds the two comments, does NOT quiet the counter,
does NOT re-audit any other sub-typed counter in the federation, and does NOT
assign the raising row a tier.

EVIDENCE DISCIPLINE: every behavioural assertion below reads the checker's
CAPTURED STDERR and its WRITTEN diagnostics. No expected value is computed with
the same expression the checker uses — the expected substrings are literals, and
their counts are known BY CONSTRUCTION of each fixture corpus. A test that
matched whatever the f-string happened to produce could not fail.

SCOPE HONESTY: fixture-green over synthetic corpora. Fixture-green is not
live-green; the first live banner read is the next review_close_check fire.

Every documented conditional gets BOTH arms
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths): the
banner's sub-typed arm AND its no-index-loss arm; the route note's threaded arm
AND its not-threaded arm.

Run:  python3 -m unittest test_review_close_check_banner_subtypes_tic822
"""

import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

_HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "review_close_check_822", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check_822"] = rcc
_spec.loader.exec_module(rcc)

ROUTE_F = "promotion_witness_comment_shed_by_matcher"

# --- corpus pieces, reused from the /review-775 sub-typing fixtures ----------
# An ADMITTED head-anchored inscription witness donating its token to the index.
ADMITTED = ("<!-- PROMOTE-AS-REFINEMENT promoted from "
            "cpr_mogul_review_close_check_1d0125de5ee3 at /review 771 -->")
# A shed comment carrying the SAME token -> comment_only (zero index consequence).
SHED_SAME_TOKEN = ("<!-- consumer-carry note from "
                   "cpr_mogul_review_close_check_1d0125de5ee3 (/review 772) -->")
# A shed comment whose token nothing admits -> id_absent (a real hole).
SHED_ABSENT = ("<!-- consumer-carry note from "
               "cpr_mogul_review_close_check_feedbeef0000 (/review 772) -->")
# A DESIGN-EXCLUDED residue comment: token-bearing residue with NO index_loss
# member at all — the NEITHER population.
DESIGN_EXCLUDED = ("<!-- --agnostic-candidate id: "
                   "cpr_mogul_review_close_check_cafebabe0001 -->")


class HermeticBannerCase(unittest.TestCase):
    """HOME sandboxed so real surfaces never leak into fixture counts
    (cgg-ledger#self-locating-artifact-test-isolation)."""

    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self.addCleanup(self._home.cleanup)
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

    def banner(self, body):
        """Run the index pass over a one-file corpus and return
        (captured stderr, published diagnostics). The banner is read from the
        CAPTURED STREAM, never re-rendered by the test."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        (root / "CLAUDE.md").write_text(body, encoding="utf-8")
        diag = {}
        buf = io.StringIO()
        with redirect_stderr(buf):
            rcc.build_inscribed_index(str(root), queue_ids=None, diagnostics=diag)
        return buf.getvalue(), diag


class TestBannerNamesSubtypesWithCounts(HermeticBannerCase):

    def test_comment_only_population_routes_to_zero_index_consequence(self):
        """THE LIVED 804-812 SHAPE. One shed comment whose token is already in
        the index via another admitted comment: comment_only=1, id_absent=0.
        The banner must say so, and must route it to a vocabulary registration
        — not to 'cure it'."""
        err, diag = self.banner(ADMITTED + "\n\n" + SHED_SAME_TOKEN + "\n")
        # the written artifact agrees, read independently of the banner text
        self.assertEqual(
            diag["unmatched_disposition_split"]["index_loss_subtype_counts"],
            {"index_loss_comment_only": 1, "index_loss_id_absent": 0})
        self.assertIn("index_loss_comment_only=1 -> zero index consequence", err)
        self.assertIn("a vocabulary registration at most", err)
        self.assertIn("index_loss_id_absent=0", err)
        # the pre-cure parent-semantics sentence is GONE for this population:
        # its residue had zero index consequence and no hole to cure.
        self.assertNotIn("index_loss = a real witness lost from the index", err)

    def test_id_absent_population_routes_to_a_real_index_hole(self):
        """The other sub-type: nothing admits the token — a real hole, and the
        banner keeps the imperative for exactly this population."""
        err, diag = self.banner(SHED_ABSENT + "\n")
        self.assertEqual(
            diag["unmatched_disposition_split"]["index_loss_subtype_counts"],
            {"index_loss_comment_only": 0, "index_loss_id_absent": 1})
        self.assertIn("index_loss_id_absent=1 -> a real index hole, cure it", err)
        self.assertIn("index_loss_comment_only=0", err)

    def test_both_subtypes_print_both_counts_and_both_routes(self):
        """BOTH non-zero: both counts AND both routes appear. Naming the
        sub-types must not read as quieting either one."""
        err, diag = self.banner(
            ADMITTED + "\n\n" + SHED_SAME_TOKEN + "\n\n" + SHED_ABSENT + "\n")
        self.assertEqual(
            diag["unmatched_disposition_split"]["index_loss_subtype_counts"],
            {"index_loss_comment_only": 1, "index_loss_id_absent": 1})
        self.assertIn("index_loss_id_absent=1 -> a real index hole, cure it", err)
        self.assertIn("index_loss_comment_only=1 -> zero index consequence", err)
        # both routes present means neither sub-type went dark
        self.assertIn("a vocabulary registration at most", err)

    def test_neither_subtype_prints_no_loss_implying_sentence(self):
        """NEITHER sub-type: a token-bearing residue population with zero
        index_loss members (a design-excluded block). The banner still fires —
        the population is disclosed rather than going dark — but it must NOT
        print a sentence implying a witness was lost."""
        err, diag = self.banner(DESIGN_EXCLUDED + "\n")
        split = diag["unmatched_disposition_split"]
        # by construction: residue exists, but no index_loss member
        self.assertGreater(split["token_bearing_residue_total"], 0)
        self.assertEqual(split["counts"].get("index_loss", 0), 0)
        self.assertEqual(split["index_loss_subtype_counts"],
                         {"index_loss_comment_only": 0, "index_loss_id_absent": 0})
        self.assertIn("UNMATCHED-PROVENANCE-SHAPE:", err)   # still fires
        self.assertNotIn("a real witness lost from the index", err)
        self.assertNotIn("a real index hole, cure it", err)
        self.assertIn("index_loss = 0 members this pass", err)

    def test_counter_stays_loud_in_both_subtypes(self):
        """The ruling changes what the number MEANS, never whether it sounds:
        both sub-types remain inside the loud headline count."""
        err, diag = self.banner(
            ADMITTED + "\n\n" + SHED_SAME_TOKEN + "\n\n" + SHED_ABSENT + "\n")
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 2)
        self.assertEqual(
            diag["unmatched_disposition_split"]["counts"]["index_loss"], 2)
        self.assertIn("UNMATCHED-PROVENANCE-SHAPE: 2 of 2", err)

    def test_membership_formulas_and_disposition_text_still_carry_parent_text(self):
        """The three strings the ruling holds byte-unchanged still read as they
        did: _DISPOSITION_TEXT already carried the sub-types, and the two
        membership formulas stay correct at PARENT granularity."""
        self.assertIn("index_loss_id_absent", rcc._DISPOSITION_TEXT["index_loss"])
        self.assertIn("index_loss_comment_only", rcc._DISPOSITION_TEXT["index_loss"])
        _, diag = self.banner(ADMITTED + "\n\n" + SHED_SAME_TOKEN + "\n")
        self.assertIn("disposition index_loss OR ",
                      diag["unmatched_provenance_shaped_population"])
        self.assertIn("index_loss + unclassified",
                      diag["unmatched_disposition_split"]["headline_counter_population"])


def _prior(report_dir, tic, tokens=None, promoted=None):
    """Write a prior tic-keyed artifact carrying membership sets (the tic-780
    fixture shape) so the attribution pass has a baseline to diff against."""
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


class TestDormantRouteNoteCarriesSubtypes(unittest.TestCase):
    """HOW THIS DORMANT NOTE IS MADE TO FIRE (it has fired ZERO times in the
    804/809/812 live artifacts): route (f) binds only for a member that is in
    this pass's promoted set, NOT in the prior pass's promoted set, donates NO
    new index token, was NOT in the prior index, and IS carried by the residue
    counter's shed-witness token membership. The fixture builds a prior
    artifact with empty membership sets, then presents exactly one promoted
    member with no token and shed_witness_tokens={that member} — the lived
    tic-777 shape from the /review-780 precedence-gate fixture."""

    def _attribution(self, shed, subtype_counts=None):
        with tempfile.TemporaryDirectory() as td:
            _prior(td, 9, tokens=[], promoted=[])
            queue = {"cpr_x_shedcase": {"status": "promoted",
                                        "landing_kind": "modify_and_merge"}}
            kwargs = {}
            if subtype_counts is not None:
                kwargs["index_loss_subtype_counts"] = subtype_counts
            return rcc.compute_cross_counter_attribution(
                td, "tic-10-check.json", 10,
                current_tokens=set(),
                current_promoted={"cpr_x_shedcase"},
                queue=queue,
                shed_witness_tokens=shed,
                **kwargs)

    def _member(self, a):
        return {m["member"]: m for m in a["attributed_members"]}["cpr_x_shedcase"]

    def test_route_note_carries_the_subtypes_when_it_fires(self):
        """The note FIRES (route f bound) and names both sub-types with their
        counts, routing each to its own cure."""
        a = self._attribution(shed={"cpr_x_shedcase"},
                              subtype_counts={"index_loss_id_absent": 3,
                                              "index_loss_comment_only": 5})
        m = self._member(a)
        self.assertEqual(m["catalog_route"], ROUTE_F)      # it really fired
        self.assertIs(m["catalog_covers"], True)
        self.assertIs(m.get("witness_comment_shed"), True)
        self.assertIn("index_loss_id_absent=3 -> a real index hole, cure it",
                      m["note"])
        self.assertIn("index_loss_comment_only=5 -> zero index consequence, "
                      "a vocabulary registration at most", m["note"])
        # the pre-cure sentence is preserved, not replaced — nothing else moves
        self.assertIn("its witness comment WAS written and was SHED by the "
                      "matcher", m["note"])

    def test_route_note_declares_unmeasured_when_split_not_threaded(self):
        """THE OTHER ARM of the documented conditional: a caller that does not
        thread the split gets an explicit UNMEASURED declaration, never a
        fabricated zero that would read as 'no holes'."""
        a = self._attribution(shed={"cpr_x_shedcase"})
        m = self._member(a)
        self.assertEqual(m["catalog_route"], ROUTE_F)
        self.assertIn("sub-type split was NOT threaded", m["note"])
        self.assertNotIn("index_loss_id_absent=0", m["note"])

    def test_route_f_membership_is_unchanged_by_this_cure(self):
        """NEGATIVE CONTROL on the binding: the precedence gate still fires on
        the PARENT-level shed membership. With an empty shed set the pre-cure
        binding is preserved (route a), and no sub-type text appears — this
        cure moved the note TEXT, never who reaches route (f)."""
        a = self._attribution(shed=set(),
                              subtype_counts={"index_loss_id_absent": 3,
                                              "index_loss_comment_only": 5})
        m = self._member(a)
        self.assertEqual(m["catalog_route"],
                         "modify_and_merge_promotion_adds_no_provenance_comment")
        self.assertNotIn("witness_comment_shed", m)
        self.assertNotIn("INDEX CONSEQUENCE", m["note"])


if __name__ == "__main__":
    unittest.main()
