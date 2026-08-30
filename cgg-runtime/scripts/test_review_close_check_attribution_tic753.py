#!/usr/bin/env python3
"""Tests for the /review 753 review-close-check cure (the tic-753 CGG batch).

Q1 (cpr_mogul_review_close_check_e193ae8e2af1, PROMOTE-as-refinement-ray + first-consumer
patch — the ATTRIBUTION clause, fifth ray on constitution-ledger#artifact-language-must-not-
exceed-its-declared-confidence-classification): a divergence disclosure that enumerates
candidate routes owes the FIRED member when the delta is enumerable. The cross-counter
disclosure's `agree` is a MAGNITUDE claim; the new `attribution` block binds the moved
MEMBERS by set difference over membership sets the artifact now PERSISTS
(`membership_sets`: index tokens + promoted ids). The lived instance pinned below: the
tic-752 close fire read +3/+3 `agree=True, evidence-bearing` over sets intersecting in
2 of 3 — a promoted id whose witness token pre-existed, paired against a phantom token.

Q2 (F-743-M1; bk-close-check-unresolved-membership-persisted): the FULL
unresolved-against-queue membership is persisted beside the 25-item sample.

Honest-limit arms are first-class fixtures: no prior artifact, a pre-753 prior without
membership sets, and a delta past the enumeration cap all yield attribution_unresolved
with a reason — never a fabricated binding.
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

ROUTES = list(rcc._DIVERGENCE_ROUTES)


def _prior(report_dir, tic, tokens=None, promoted=None, with_sets=True):
    """Write a prior tic-keyed artifact; with_sets=False emits the pre-753 schema."""
    art = {
        "inscribed_index_size": len(tokens or []),
        "inscribed_index_unit": {"matched_comment_count": len(tokens or [])},
        "verdict_counts": {"promoted": len(promoted or []), "deferred": 0, "skipped": 0},
    }
    if with_sets:
        art["membership_sets"] = {
            "index_tokens": sorted(tokens or []),
            "promoted_ids": sorted(promoted or []),
        }
    (pathlib.Path(report_dir) / f"tic-{tic}-check.json").write_text(
        json.dumps(art), encoding="utf-8")


class DisclosureBackCompat(unittest.TestCase):
    def test_two_arg_form_carries_unresolved_attribution_and_the_same_catalog(self):
        d = rcc.compute_cross_counter_disclosure(
            {"delta": {"promoted": 1}}, {"delta_tokens": 1})
        self.assertTrue(d["agree"])
        a = d["attribution"]
        self.assertTrue(a["attribution_unresolved"])
        self.assertTrue(a["unresolved_reason"].startswith("not_computed_by_caller"))
        self.assertIsNone(a["attributed_members"])
        # The catalog is unchanged: four members, order pinned, printed from ONE constant.
        self.assertEqual(d["divergence_routes"], ROUTES)
        self.assertEqual(len(ROUTES), 4)
        self.assertEqual(ROUTES[3],
                         "absorbed_reinforcement_breadcrumb_adds_token_without_promotion")
        self.assertIn('"divergence_routes": list(_DIVERGENCE_ROUTES)', _SRC)


class AttributionHonestLimits(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_prior_artifact_is_unresolved(self):
        a = rcc.compute_cross_counter_attribution(
            self.rd, "tic-753-check.json", 753, {"cpr_a"}, {"cpr_a"}, {})
        self.assertTrue(a["attribution_unresolved"])
        self.assertEqual(a["unresolved_reason"], "no_prior_pass_artifact")
        self.assertIsNone(a["attributed_members"])
        self.assertIsNone(a["agree_by_membership"])

    def test_prior_without_membership_sets_is_unresolved_with_reason(self):
        # The pre-753 schema (every artifact through tic 752): counts only, no sets.
        _prior(self.rd, 752, with_sets=False)
        a = rcc.compute_cross_counter_attribution(
            self.rd, "tic-753-check.json", 753, {"cpr_a"}, {"cpr_a"}, {})
        self.assertTrue(a["attribution_unresolved"])
        self.assertTrue(a["unresolved_reason"].startswith(
            "prior_artifact_carries_no_membership_sets"))
        self.assertEqual(a["baseline"]["artifact"], "tic-752-check.json")
        self.assertEqual(a["baseline"]["selector"], "tic_keyed_prior_tic_752")

    def test_delta_past_cap_is_unresolved_with_sizes_not_members(self):
        _prior(self.rd, 752, tokens=[], promoted=[])
        many = {f"cpr_flood_{i}" for i in range(rcc._ATTRIBUTION_ENUMERATION_CAP + 1)}
        a = rcc.compute_cross_counter_attribution(
            self.rd, "tic-753-check.json", 753, many, set(), {})
        self.assertTrue(a["attribution_unresolved"])
        self.assertTrue(a["unresolved_reason"].startswith("delta_too_large_to_attribute"))
        self.assertEqual(a["delta_sizes"]["new_index_tokens"],
                         rcc._ATTRIBUTION_ENUMERATION_CAP + 1)
        self.assertIsNone(a["attributed_members"])


class AttributionByMembership(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _members(self, a):
        return {m["member"]: m for m in a["attributed_members"]}

    def test_paired_member_is_the_inscription_event(self):
        _prior(self.rd, 752, tokens=["cpr_a"], promoted=["cpr_a"])
        a = rcc.compute_cross_counter_attribution(
            self.rd, "tic-753-check.json", 753, {"cpr_a", "cpr_b"}, {"cpr_a", "cpr_b"},
            {"cpr_b": {"status": "promoted", "landing_kind": "refinement_ray"}})
        self.assertFalse(a["attribution_unresolved"])
        self.assertEqual(a["new_index_tokens"], ["cpr_b"])
        self.assertEqual(a["new_promoted_ids"], ["cpr_b"])
        self.assertTrue(a["agree_by_membership"])
        self.assertFalse(a["magnitude_agreement_is_coincidence"])
        m = self._members(a)["cpr_b"]
        self.assertEqual(m["class"], "paired_promotion_and_witness_token")
        self.assertTrue(m["catalog_covers"])

    def test_tic752_coincidence_shape_magnitude_agrees_membership_does_not(self):
        # Prior: cpr_x's token ALREADY narrated (a breadcrumb at the prior close); not promoted.
        _prior(self.rd, 752, tokens=["cpr_a", "cpr_x"], promoted=["cpr_a"])
        queue = {
            "cpr_a": {"status": "promoted"},
            "cpr_x": {"status": "promoted", "landing_kind": "refinement_ray"},
            "cpr_b": {"status": "promoted", "landing_kind": "refinement_ray"},
            "cpr_c": {"status": "promoted", "landing_kind": "typed_guard"},
        }
        # This pass: b and c promoted with their tokens; x promoted (token pre-existed);
        # cpr_phantom_run donated by a cited filename — a token with no queue row.
        cur_tokens = {"cpr_a", "cpr_x", "cpr_b", "cpr_c", "cpr_phantom_run"}
        cur_promoted = {"cpr_a", "cpr_x", "cpr_b", "cpr_c"}
        a = rcc.compute_cross_counter_attribution(
            self.rd, "tic-753-check.json", 753, cur_tokens, cur_promoted, queue)
        self.assertEqual(len(a["new_index_tokens"]), 3)
        self.assertEqual(len(a["new_promoted_ids"]), 3)
        # The counts agree (3 == 3); the sets intersect in 2 of 3 — the tic-752 reading.
        self.assertFalse(a["agree_by_membership"])
        self.assertTrue(a["magnitude_agreement_is_coincidence"])
        self.assertEqual(a["intersection_new_tokens_new_promoted"], ["cpr_b", "cpr_c"])
        m = self._members(a)
        self.assertEqual(m["cpr_x"]["class"], "promoted_without_new_token")
        self.assertTrue(m["cpr_x"]["token_pre_existed_in_prior_index"])
        self.assertIs(m["cpr_x"]["catalog_covers"], False)
        self.assertIsNone(m["cpr_x"]["catalog_route"])
        self.assertEqual(m["cpr_phantom_run"]["class"], "token_without_promotion")
        self.assertFalse(m["cpr_phantom_run"]["in_queue"])
        self.assertIsNone(m["cpr_phantom_run"]["catalog_covers"])
        self.assertIn(ROUTES[2], m["cpr_phantom_run"]["candidate_routes"])

    def test_modify_merge_promotion_binds_to_route_a(self):
        _prior(self.rd, 752, tokens=["cpr_a"], promoted=["cpr_a"])
        a = rcc.compute_cross_counter_attribution(
            self.rd, "tic-753-check.json", 753, {"cpr_a"}, {"cpr_a", "cpr_m"},
            {"cpr_m": {"status": "promoted", "review_verdict": "MODIFY-and-merge"}})
        m = self._members(a)["cpr_m"]
        self.assertEqual(m["class"], "promoted_without_new_token")
        self.assertEqual(m["catalog_route"], ROUTES[0])
        self.assertTrue(m["catalog_covers"])
        self.assertFalse(a["agree_by_membership"])

    def test_absorbed_breadcrumb_binds_to_route_d(self):
        _prior(self.rd, 752, tokens=["cpr_a"], promoted=["cpr_a"])
        a = rcc.compute_cross_counter_attribution(
            self.rd, "tic-753-check.json", 753, {"cpr_a", "cpr_abs"}, {"cpr_a"},
            {"cpr_abs": {"status": "absorbed"}})
        m = self._members(a)["cpr_abs"]
        self.assertEqual(m["class"], "token_without_promotion")
        self.assertEqual(m["catalog_route"], ROUTES[3])
        self.assertTrue(m["catalog_covers"])

    def test_narrated_sibling_queue_id_binds_to_route_b(self):
        _prior(self.rd, 752, tokens=["cpr_a"], promoted=["cpr_a", "cpr_old"])
        a = rcc.compute_cross_counter_attribution(
            self.rd, "tic-753-check.json", 753, {"cpr_a", "cpr_old"}, {"cpr_a", "cpr_old"},
            {"cpr_old": {"status": "promoted"}})
        m = self._members(a)["cpr_old"]
        self.assertEqual(m["class"], "token_without_promotion")
        self.assertEqual(m["catalog_route"], ROUTES[1])
        self.assertEqual(a["new_promoted_ids"], [])

    def test_removed_members_are_disclosed_not_routed(self):
        # The tic-752 cure shape: a phantom token stripped from a comment shrinks the index.
        _prior(self.rd, 752, tokens=["cpr_a", "cpr_phantom_run"], promoted=["cpr_a"])
        a = rcc.compute_cross_counter_attribution(
            self.rd, "tic-753-check.json", 753, {"cpr_a"}, {"cpr_a"}, {})
        self.assertEqual(a["removed_index_tokens"], ["cpr_phantom_run"])
        m = self._members(a)["cpr_phantom_run"]
        self.assertEqual(m["class"], "index_token_removed")
        self.assertIsNone(m["catalog_covers"])
        self.assertTrue(a["agree_by_membership"])  # nothing NEW moved on either side


class PersistenceHalf(unittest.TestCase):
    def test_report_persists_membership_sets_between_disclosure_and_findings(self):
        i_disc = _SRC.index('"cross_counter_disclosure": cross_disclosure,')
        i_sets = _SRC.index('"membership_sets": {', i_disc)
        i_find = _SRC.index('"findings": all_findings,', i_sets)
        self.assertLess(i_disc, i_sets)
        self.assertLess(i_sets, i_find)
        self.assertIn('"index_tokens": sorted(inscribed_ids),', _SRC[i_sets:i_find])
        self.assertIn('"promoted_ids": promoted_ids,', _SRC[i_sets:i_find])

    def test_run_check_computes_attribution_after_the_unit_delta_and_passes_it(self):
        i_delta = _SRC.index("index_delta = compute_unit_deltas(")
        i_attr = _SRC.index("attribution = compute_cross_counter_attribution(", i_delta)
        i_disc = _SRC.index("cross_disclosure = compute_cross_counter_disclosure(", i_attr)
        self.assertIn("verdict_delta, index_delta, attribution)", _SRC[i_disc:i_disc + 200])

    def test_full_unresolved_membership_persisted_beside_the_sample(self):
        i_sample = _SRC.index('diagnostics["unresolved_against_queue_sample"]')
        i_members = _SRC.index('diagnostics["unresolved_against_queue_members"]', i_sample)
        self.assertLess(i_sample, i_members)
        # Live: 30 id-shaped tokens that fail queue membership. The scan ALSO reads the
        # real global surfaces (~/.claude/CLAUDE.md, auto-memory) by design, so the
        # assertions hold on the fixture SUBSET and on the members/sample/count
        # relations — never on an absolute total the machine's globals would move.
        with tempfile.TemporaryDirectory() as tmp:
            fixture = {f"cpr_unres_{i:02d}" for i in range(30)}
            body = "".join(f"<!-- promoted from {t} -->\n" for t in sorted(fixture))
            pathlib.Path(tmp, "CLAUDE.md").write_text(body, encoding="utf-8")
            diag = {}
            ids = rcc.build_inscribed_index(tmp, queue_ids=set(), diagnostics=diag)
            members = diag["unresolved_against_queue_members"]
            self.assertTrue(fixture <= ids)
            self.assertTrue(fixture <= set(members))
            self.assertGreaterEqual(len(members), 30)
            # the FULL set: count == len(members), sorted, and the sample is its head
            self.assertEqual(diag["unresolved_against_queue_count"], len(members))
            self.assertEqual(members, sorted(members))
            self.assertEqual(len(diag["unresolved_against_queue_sample"]), 25)
            self.assertEqual(diag["unresolved_against_queue_sample"], members[:25])


if __name__ == "__main__":
    unittest.main()
