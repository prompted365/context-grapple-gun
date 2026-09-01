#!/usr/bin/env python3
"""test_review_close_check_equality_constructor_and_coverage_tic757.py — the FORWARD-DECAY
face (/review 757 Q1, cpr_mogul_review_close_check_7db791b7707a PROMOTED on the
presence-observation family: a cure applied by enumeration binds only the sites that existed
at ruling time; at the second site the enumeration becomes a CONSTRUCTOR) and the COVERAGE
face (/review 757 Q2, cpr_mogul_review_close_check_a75f34bef299 absorbed into the ATTRIBUTION
clause: a coverage flag must not read TRUE for a member the catalog was never asked about).

The lived defect: review-close-check.py's third equality discriminator
(attribution.agree_by_membership + magnitude_agreement_is_coincidence, minted /review 753)
fired UNTYPED at tic 754 — agree_by_membership:true over two EMPTY sets beside a parent flag
correctly typed vacuous on the same pass; and the paired_promotion_and_witness_token member
(catalog_route null) read catalog_covers:true in the 754/755/756 artifacts, so a reader
aggregating the flag counted clean inscription events as coverage evidence.

Ten tests: the constructor's four weights · not-comparable is all-None · stem + predicate
forms · the audit names an untyped flag · the tic-754 empty-delta shape is now typed vacuous
· a PROMOTE+ABSORB pass is typed disagreement with the paired member not_applicable and the
denominator over divergent members only · coverage is undefined (never 100%) when only clean
inscriptions landed · the emitted artifact audits itself clean.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("rcc_t757", _HERE / "review-close-check.py")
rcc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rcc)


def _write_artifact(report_dir: Path, name: str, payload: dict) -> Path:
    path = report_dir / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class EqualityConstructorTests(unittest.TestCase):
    def test_vacuous_flag_leaves_with_its_weight(self):
        out = rcc.emit_equality_discriminator("x", 0, 0, observation_empty=True)
        self.assertEqual(set(out), {"x", "x_vacuous", "x_evidential_weight"})
        self.assertTrue(out["x"])
        self.assertTrue(out["x_vacuous"])
        self.assertTrue(out["x_evidential_weight"].startswith("none"))

    def test_disagreement_weight(self):
        out = rcc.emit_equality_discriminator("x", 1, 2, observation_empty=False)
        self.assertFalse(out["x"])
        self.assertFalse(out["x_vacuous"])
        self.assertTrue(out["x_evidential_weight"].startswith("disagreement"))

    def test_coincident_arms_and_evidence_bearing(self):
        coincident = rcc.emit_equality_discriminator("x", 3, 3, observation_empty=False, coincident=True)
        self.assertTrue(coincident["x"])
        self.assertTrue(coincident["x_evidential_weight"].startswith("coincident-arms"))
        clean = rcc.emit_equality_discriminator("x", 3, 3, observation_empty=False)
        self.assertTrue(clean["x_evidential_weight"].startswith("evidence-bearing"))

    def test_not_comparable_is_all_none(self):
        out = rcc.emit_equality_discriminator("x", None, 3, observation_empty=False, comparable=False)
        self.assertEqual(out, {"x": None, "x_vacuous": None, "x_evidential_weight": None})

    def test_stem_and_predicate_forms(self):
        agree = rcc.emit_equality_discriminator("agree", 0, 0, observation_empty=True, stem="")
        self.assertEqual(set(agree), {"agree", "vacuous", "evidential_weight"})
        units = rcc.emit_equality_discriminator("units_collapsed_this_pass", 2, 2,
                                                observation_empty=False, stem="units_collapsed")
        self.assertIn("units_collapsed_vacuous", units)
        self.assertIn("units_collapsed_evidential_weight", units)
        coinc = rcc.emit_equality_discriminator(
            "m", {"a", "b"}, {"c", "d"}, observation_empty=False,
            predicate=lambda l, r: len(l) == len(r) and l != r)
        self.assertTrue(coinc["m"])

    def test_audit_names_an_untyped_flag(self):
        bad = {"cross_counter_disclosure": {"attribution": {"agree_by_membership": True}}}
        out = rcc.audit_equality_flags(bad)
        self.assertEqual(out["untyped"], ["cross_counter_disclosure.attribution.agree_by_membership"])
        good = {"attribution": rcc.emit_equality_discriminator("agree_by_membership", set(), set(),
                                                               observation_empty=True)}
        out = rcc.audit_equality_flags(good)
        self.assertEqual(out["untyped"], [])
        self.assertEqual(out["checked"], ["attribution.agree_by_membership"])
        # the persisted stem forms audit too
        stems = {"x": rcc.emit_equality_discriminator("agree", 1, 1, observation_empty=False, stem=""),
                 "y": rcc.emit_equality_discriminator("units_collapsed_this_pass", 1, 1,
                                                       observation_empty=False, stem="units_collapsed")}
        self.assertEqual(rcc.audit_equality_flags(stems)["untyped"], [])


class AttributionTypingAndCoverageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.report_dir = Path(self._tmp.name)
        self.current = "tic-757-check.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _prior(self, tokens, promoted):
        _write_artifact(self.report_dir, "tic-756-check.json", {
            "membership_sets": {"index_tokens": sorted(tokens), "promoted_ids": sorted(promoted)}})

    def test_empty_delta_is_typed_vacuous_the_tic_754_shape(self):
        self._prior({"a"}, {"a"})
        block = rcc.compute_cross_counter_attribution(
            str(self.report_dir), self.current, 757, {"a"}, {"a"}, queue={})
        self.assertFalse(block["attribution_unresolved"])
        self.assertTrue(block["agree_by_membership"])
        self.assertTrue(block["agree_by_membership_vacuous"])
        self.assertTrue(block["agree_by_membership_evidential_weight"].startswith("none"))
        self.assertFalse(block["magnitude_agreement_is_coincidence"])
        self.assertTrue(block["magnitude_agreement_is_coincidence_vacuous"])
        self.assertEqual(rcc.audit_equality_flags(block)["untyped"], [])

    def test_promote_plus_absorb_is_typed_disagreement_and_the_paired_member_is_not_applicable(self):
        self._prior({"a"}, {"a"})
        queue = {"x": {"status": "promoted"}, "y": {"status": "absorbed"}}
        block = rcc.compute_cross_counter_attribution(
            str(self.report_dir), self.current, 757, {"a", "x", "y"}, {"a", "x"}, queue=queue)
        self.assertFalse(block["agree_by_membership"])
        self.assertFalse(block["agree_by_membership_vacuous"])
        self.assertTrue(block["agree_by_membership_evidential_weight"].startswith("disagreement"))
        self.assertFalse(block["magnitude_agreement_is_coincidence"])
        members = {m["member"]: m for m in block["attributed_members"]}
        self.assertEqual(members["x"]["class"], "paired_promotion_and_witness_token")
        self.assertEqual(members["x"]["catalog_covers"], "not_applicable")
        self.assertFalse(members["x"]["divergence_occurred"])
        self.assertEqual(members["y"]["class"], "token_without_promotion")
        self.assertIs(members["y"]["catalog_covers"], True)
        self.assertTrue(members["y"]["divergence_occurred"])
        cov = block["coverage_over_divergent_members"]
        self.assertEqual((cov["denominator"], cov["covered"], cov["not_applicable_excluded"]), (1, 1, 1))
        self.assertIn("1/1", cov["statement"])

    def test_coverage_is_undefined_when_only_clean_inscriptions_landed(self):
        self._prior({"a"}, {"a"})
        block = rcc.compute_cross_counter_attribution(
            str(self.report_dir), self.current, 757, {"a", "x"}, {"a", "x"}, queue={"x": {"status": "promoted"}})
        cov = block["coverage_over_divergent_members"]
        self.assertEqual(cov["denominator"], 0)
        self.assertIn("undefined", cov["statement"])
        self.assertTrue(block["agree_by_membership"])
        self.assertFalse(block["agree_by_membership_vacuous"])

    def test_audit_declares_its_observation_window(self):
        # bfb2ebf77d70 (the close-fire citizen, tic 757): the audit gates on a NAME registry —
        # it must say so, and name what it does NOT observe, beside its verdict.
        out = rcc.audit_equality_flags_with_window({"a": {"agree": True, "vacuous": False,
                                                          "evidential_weight": "x"}})
        self.assertEqual(out["untyped"], [])
        w = out["observation_window"]
        self.assertEqual(w["registry"], list(rcc.EQUALITY_FLAG_NAMES))
        self.assertIn("NOT OBSERVED", w["not_observed"])
        self.assertIn("membership_sets.matched_comment_ids_unit_parity", w["known_unregistered_equality_shaped_flags"])
        # an unregistered equality-shaped boolean is invisible to the audit — by declaration, not by omission
        out2 = rcc.audit_equality_flags_with_window({"queue_state_tuple": {"matches_total_cprs": True}})
        self.assertEqual(out2["checked"], [])
        self.assertEqual(out2["untyped"], [])

    def test_unresolved_shape_carries_the_siblings(self):
        block = rcc._attribution_not_computed("no_prior_artifact")
        for k in ("agree_by_membership_vacuous", "agree_by_membership_evidential_weight",
                  "magnitude_agreement_is_coincidence_vacuous",
                  "magnitude_agreement_is_coincidence_evidential_weight"):
            self.assertIn(k, block)
            self.assertIsNone(block[k])
        self.assertEqual(rcc.audit_equality_flags(block)["untyped"], [])


if __name__ == "__main__":
    unittest.main()
