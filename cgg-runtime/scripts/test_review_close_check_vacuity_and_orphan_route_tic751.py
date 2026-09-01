#!/usr/bin/env python3
"""Tests for the /review 751 review-close-check cures (the tic-751 CGG batch).

Q1 (cpr_mogul_review_close_check_45c12f41fc1e, ABSORB-as-reinforcement into GUARD-19 —
the SIBLING-FIELD face): an equality-of-deltas discriminator fires TRUE vacuously at
0==0. Both discriminators on the artifact surface — cross_counter_disclosure.agree
(promoted_delta == token_delta) and units_collapsed_this_pass (delta_tokens ==
delta_matched_comments) — now carry a typed `vacuous` boolean and an evidential-weight
string, so an entry-fire agreement over an empty observation set is never read back as
equal evidence to a close-fire agreement.

Q4 (cpr_mogul_review_close_check_7fb07b4e6323, PROMOTE-as-refinement-ray — the
MIRROR-FACE corollary on cgg-ledger#emitter-rows-must-match-a-reader-predicate):
check_orphans (the row named it find_orphaned_promotions) clears on a MENTION anywhere in a bounded scanned set while its
message claimed "ANY governance file". The predicate is unchanged; the message names the
scanned set; each axis-3 clear is typed by ROUTE (declared_target_text |
scope_target_text | third_party_mention) and disclosed in
summary.orphan_route_disclosure, so a mention-cleared orphan is reported as
reclassified-by-sibling-narration, never as verification progress.

The units block's vacuity wiring is generator-enforced against source (the lane's
6372-cure style): compute_unit_deltas needs a report directory with two artifacts, so the
source asserts pin the wiring and the cross-counter function is exercised directly.
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
    "review_close_check", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rcc)


class CrossCounterVacuity(unittest.TestCase):
    def _cc(self, promoted, tokens):
        return rcc.compute_cross_counter_disclosure(
            {"delta": {"promoted": promoted}}, {"delta_tokens": tokens})

    def test_entry_fire_shape_is_vacuous(self):
        d = self._cc(0, 0)
        self.assertTrue(d["agree"])
        self.assertTrue(d["vacuous"])
        self.assertIn("GUARD-19", d["evidential_weight"])
        self.assertTrue(d["evidential_weight"].startswith("none"))

    def test_close_fire_agreement_is_evidence_bearing(self):
        d = self._cc(5, 5)
        self.assertTrue(d["agree"])
        self.assertFalse(d["vacuous"])
        self.assertTrue(d["evidential_weight"].startswith("evidence-bearing"))

    def test_disagreement_is_a_question_not_vacuous(self):
        d = self._cc(2, 3)
        self.assertFalse(d["agree"])
        self.assertFalse(d["vacuous"])
        self.assertTrue(d["evidential_weight"].startswith("disagreement"))

    def test_non_comparable_never_fabricates(self):
        d = self._cc(None, 3)
        self.assertFalse(d["comparable"])
        self.assertIsNone(d["agree"])
        self.assertIsNone(d["vacuous"])
        self.assertIsNone(d["evidential_weight"])

    def test_units_block_vacuity_wired_in_source(self):
        # /review 757 Q1 (the FORWARD-DECAY face, cpr_mogul_review_close_check_7db791b7707a):
        # the site now wires vacuity THROUGH the constructor — the flag, its vacuity sibling
        # and its weight leave as ONE unit; the persisted key names and texts are unchanged.
        i = _SRC.index('"units_collapsed_this_pass", block["delta_tokens"], block["delta_matched_comments"]')
        seg = _SRC[max(0, i - 200):i + 900]
        self.assertIn("emit_equality_discriminator(", seg)
        self.assertIn('observation_empty=(block["delta_tokens"] == 0 and block["delta_matched_comments"] == 0)', seg)
        self.assertIn('stem="units_collapsed"', seg)
        self.assertIn("GUARD-19", seg)


class OrphanRouteTyping(unittest.TestCase):
    """A promoted row whose id is mentioned ONLY by a sibling in ledger.md must clear
    (predicate unchanged) AND be disclosed under third_party_mention; a row whose text
    lives in its promoted_to target clears under declared_target_text; a row found
    nowhere in the scanned set is an orphan whose message names the scanned set."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        led = pathlib.Path(self.root) / "audit-logs" / "governance" / "constitution-ledger"
        led.mkdir(parents=True)
        (pathlib.Path(self.root) / "CLAUDE.md").write_text("# root\n", encoding="utf-8")
        # a sibling ray narrating cpr_alpha_1 in a distinct_from edge — a MENTION, not a landing
        (led / "ledger.md").write_text(
            "## Some anchor\n<!-- relations: distinct_from: cpr_alpha_1 (that one governs X) -->\n",
            encoding="utf-8")
        # cpr_beta_2's body genuinely lives in its promoted_to target
        (pathlib.Path(self.root) / "docs").mkdir()
        (pathlib.Path(self.root) / "docs" / "beta.md").write_text(
            "cpr_beta_2 landed here with its full lesson text.\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _queue(self):
        return {
            "cpr_alpha_1": {"status": "promoted", "lesson": "alpha lesson body never inscribed",
                            "promoted_to": "docs/alpha-missing.md", "recommended_scopes": []},
            "cpr_beta_2": {"status": "promoted", "lesson": "beta lesson body",
                           "promoted_to": "docs/beta.md", "recommended_scopes": []},
            "cpr_gamma_3": {"status": "promoted", "lesson": "gamma lesson body nowhere at all",
                            "promoted_to": "docs/gamma-missing.md", "recommended_scopes": []},
        }

    def test_routes_and_message(self):
        findings = rcc.check_orphans(self._queue(), self.root, inscribed_ids=set())
        disc = dict(rcc.ORPHAN_ROUTE_DISCLOSURE)
        # alpha: cleared by a sibling's mention in the fixed ledger path -> third_party_mention
        self.assertIn("third_party_mention", disc)
        self.assertEqual([i["cpr_id"] for i in disc["third_party_mention"]], ["cpr_alpha_1"])
        # beta: cleared inside its own promoted_to target -> declared_target_text
        self.assertIn("declared_target_text", disc)
        self.assertEqual([i["cpr_id"] for i in disc["declared_target_text"]], ["cpr_beta_2"])
        # gamma: an orphan whose message names the SCANNED set, not "any governance file"
        orphans = [f for f in findings if f["type"] == "orphaned_promotion"]
        self.assertEqual([f["cpr_id"] for f in orphans], ["cpr_gamma_3"])
        self.assertIn("SCANNED governance set", orphans[0]["message"])
        self.assertIn("not a claim about ANY governance file", orphans[0]["message"])
        self.assertIn("scanned_set", orphans[0])
        self.assertNotIn("not found in any governance file", orphans[0]["message"])

    def test_cure_revert_control_mention_would_read_as_verified(self):
        # With the route typing absent (the pre-751 predicate), a mention clear is
        # indistinguishable from a landing: assert the disclosure is what distinguishes it.
        rcc.check_orphans(self._queue(), self.root, inscribed_ids=set())
        routes = set(rcc.ORPHAN_ROUTE_DISCLOSURE)
        self.assertEqual(routes, {"third_party_mention", "declared_target_text"})
        # the legacy universe claim must be gone from the source
        self.assertNotIn('but text not found in any governance file"', _SRC)

    def test_summary_carries_the_disclosure_shape(self):
        i = _SRC.index('"orphan_route_disclosure": {')
        self.assertIn('for route, items in sorted(ORPHAN_ROUTE_DISCLOSURE.items())', _SRC[i:i + 400])


if __name__ == "__main__":
    unittest.main()
