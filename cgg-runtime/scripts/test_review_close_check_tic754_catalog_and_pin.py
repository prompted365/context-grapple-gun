#!/usr/bin/env python3
"""Tests for the /review 754 review-close-check batch (the tic-754 CGG batch).

Q1 (cpr_mogul_review_close_check_a8fc12928fe2, ABSORB-as-reinforcement into the UNIT
clause of the re-derivability axis — the catalog-unit face): a divergence catalog can
only carry the attribution its counters are UNIT-COMPATIBLE with. The consumer ruled:
`_DIVERGENCE_ROUTES` gains its FIFTH member — a promotion whose witness token already
sat in the prior index (the tic-752 shape, disclosed catalog_covers=False until now) —
bound by MEMBERSHIP, never prose; and the attribution block counts attributed members
per bound route (`attributed_members_by_route`) — the per-route delta in the HEADLINE's
unit (distinct members), never the occurrence census.

Q2 (cpr_mogul_review_close_check_da948d00591d, PROMOTE-as-refinement-ray — the PIN
clause, sixth ray on constitution-ledger#internal-memory-entries-and-governance-
snapshots-must-carry-explicit-timestamps-): a state tuple carrying a content hash of its
whole surface makes every other member falsifiable AT that instant; a self-minting fire
is blind to its own mint. The consumer: `compute_queue_state_tuple` — every member from
ONE byte read — persisted on the artifact as `queue_state_tuple` beside `total_cprs`.

Honest-limit arms are first-class fixtures: an absent queue is UNPINNED with a reason;
the unresolved attribution shape carries `attributed_members_by_route: None`, nothing
fabricated.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest

_HERE = pathlib.Path(__file__).resolve().parent
_SRC = (_HERE / "review-close-check.py").read_text(encoding="utf-8")
_spec = importlib.util.spec_from_file_location(
    "review_close_check_t754", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rcc)

ROUTES = list(rcc._DIVERGENCE_ROUTES)
ROUTE_E = "promotion_of_id_whose_witness_token_pre_existed_in_prior_index"


def _prior(report_dir, tic, tokens=None, promoted=None):
    art = {
        "inscribed_index_size": len(tokens or []),
        "inscribed_index_unit": {"matched_comment_count": len(tokens or [])},
        "verdict_counts": {"promoted": len(promoted or []), "deferred": 0, "skipped": 0},
        "membership_sets": {
            "index_tokens": sorted(tokens or []),
            "promoted_ids": sorted(promoted or []),
        },
    }
    (pathlib.Path(report_dir) / f"tic-{tic}-check.json").write_text(
        json.dumps(art), encoding="utf-8")


def _members(a):
    return {m["member"]: m for m in a["attributed_members"]}


class CatalogFifthMember(unittest.TestCase):
    def test_catalog_has_five_members_order_pinned_from_one_constant(self):
        self.assertEqual(len(ROUTES), 5)
        self.assertEqual(ROUTES[3],
                         "absorbed_reinforcement_breadcrumb_adds_token_without_promotion")
        self.assertEqual(ROUTES[4], ROUTE_E)
        # printed from ONE constant everywhere the catalog is disclosed
        self.assertIn('"divergence_routes": list(_DIVERGENCE_ROUTES)', _SRC)
        self.assertIn('"catalog": list(_DIVERGENCE_ROUTES)', _SRC)
        d = rcc.compute_cross_counter_disclosure({"delta": {"promoted": 1}}, {"delta_tokens": 1})
        self.assertEqual(d["divergence_routes"], ROUTES)
        self.assertEqual(d["attribution"]["catalog"], ROUTES)

    def test_pre_existing_token_promotion_binds_to_route_e_by_membership(self):
        with tempfile.TemporaryDirectory() as rd:
            # The tic-752 shape: cpr_x's token narrated at the prior close, promoted now.
            _prior(rd, 753, tokens=["cpr_a", "cpr_x"], promoted=["cpr_a"])
            a = rcc.compute_cross_counter_attribution(
                rd, "tic-754-check.json", 754, {"cpr_a", "cpr_x"}, {"cpr_a", "cpr_x"},
                {"cpr_x": {"status": "promoted", "landing_kind": "refinement_ray"}})
            self.assertFalse(a["attribution_unresolved"])
            self.assertEqual(a["new_index_tokens"], [])
            self.assertEqual(a["new_promoted_ids"], ["cpr_x"])
            m = _members(a)["cpr_x"]
            self.assertEqual(m["class"], "promoted_without_new_token")
            self.assertTrue(m["token_pre_existed_in_prior_index"])
            self.assertEqual(m["catalog_route"], ROUTE_E)
            self.assertIs(m["catalog_covers"], True)
            # bound by MEMBERSHIP: no verdict prose was consulted for the binding
            self.assertFalse(a["agree_by_membership"])
            self.assertFalse(a["magnitude_agreement_is_coincidence"])

    def test_route_e_and_route_a_do_not_collide(self):
        # A MODIFY/MERGE promotion whose token also pre-existed is route (e): the
        # membership test is evaluated first and is decisive.
        with tempfile.TemporaryDirectory() as rd:
            _prior(rd, 753, tokens=["cpr_m"], promoted=[])
            a = rcc.compute_cross_counter_attribution(
                rd, "tic-754-check.json", 754, {"cpr_m"}, {"cpr_m"},
                {"cpr_m": {"status": "promoted", "review_verdict": "MODIFY-and-merge"}})
            m = _members(a)["cpr_m"]
            self.assertEqual(m["catalog_route"], ROUTE_E)
            self.assertTrue(m["catalog_covers"])


class AttributedMembersByRoute(unittest.TestCase):
    def test_counts_in_the_headline_unit_per_bound_route(self):
        # The tic-754 close bank: one PROMOTE with its witness token (paired) + one
        # ABSORB whose reinforced_by breadcrumb landed a token with no promotion (route d)
        # + one promotion whose token pre-existed (route e).
        with tempfile.TemporaryDirectory() as rd:
            _prior(rd, 753, tokens=["cpr_a", "cpr_x"], promoted=["cpr_a"])
            queue = {
                "cpr_da94": {"status": "promoted", "landing_kind": "refinement_ray"},
                "cpr_a8fc": {"status": "absorbed", "landing_kind": "reinforce_existing"},
                "cpr_x": {"status": "promoted"},
            }
            a = rcc.compute_cross_counter_attribution(
                rd, "tic-754-check.json", 754,
                {"cpr_a", "cpr_x", "cpr_da94", "cpr_a8fc"},
                {"cpr_a", "cpr_x", "cpr_da94"}, queue)
            self.assertEqual(sorted(a["new_index_tokens"]), ["cpr_a8fc", "cpr_da94"])
            self.assertEqual(sorted(a["new_promoted_ids"]), ["cpr_da94", "cpr_x"])
            by = a["attributed_members_by_route"]
            self.assertEqual(by, {
                ROUTES[3]: 1,
                ROUTE_E: 1,
                "paired_promotion_and_witness_token": 1,
            })
            # the unit is declared beside the counts and names the headline's unit
            self.assertIn("headline", a["attributed_members_by_route_unit"])
            self.assertNotIn("occurrence", a["attributed_members_by_route"])
            # the counts sum to the attributed members — a re-derivable census
            self.assertEqual(sum(by.values()), len(a["attributed_members"]))

    def test_unbound_members_count_under_their_class(self):
        with tempfile.TemporaryDirectory() as rd:
            _prior(rd, 753, tokens=["cpr_a"], promoted=["cpr_a"])
            a = rcc.compute_cross_counter_attribution(
                rd, "tic-754-check.json", 754, {"cpr_a", "cpr_phantom_run"}, {"cpr_a"}, {})
            by = a["attributed_members_by_route"]
            self.assertEqual(by, {"token_without_promotion": 1})

    def test_empty_delta_counts_nothing_and_unresolved_carries_none(self):
        with tempfile.TemporaryDirectory() as rd:
            _prior(rd, 753, tokens=["cpr_a"], promoted=["cpr_a"])
            a = rcc.compute_cross_counter_attribution(
                rd, "tic-754-check.json", 754, {"cpr_a"}, {"cpr_a"}, {})
            self.assertEqual(a["attributed_members_by_route"], {})
        with tempfile.TemporaryDirectory() as empty:
            # no prior pass artifact at all -> unresolved, and the new field is None
            u = rcc.compute_cross_counter_attribution(
                empty, "tic-755-check.json", 755, {"cpr_a"}, {"cpr_a"}, {})
            self.assertTrue(u["attribution_unresolved"])
            self.assertIsNone(u["attributed_members_by_route"])


class QueueStateTuple(unittest.TestCase):
    def _write(self, path, rows):
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(r if isinstance(r, str) else json.dumps(r))
                f.write("\n")

    def test_every_member_from_one_byte_read_at_the_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = os.path.join(tmp, "queue.jsonl")
            self._write(q, [
                {"id": "cpr_a", "status": "extracted"},
                {"id": "cpr_b", "status": "promoted"},
                "{not json",
                {"id": "cpr_a", "status": "promoted"},   # latest-per-id wins
                {"id": "cpr_c", "status": "absorbed"},
            ])
            t = rcc.compute_queue_state_tuple(q, total_cprs=3)
            self.assertTrue(t["pinned"])
            self.assertEqual(t["raw_rows"], 5)
            self.assertEqual(t["parse_errors"], 1)
            self.assertEqual(t["unique_ids"], 3)
            self.assertEqual(t["status_census"], {"absorbed": 1, "promoted": 2})
            self.assertEqual(t["promoted"], 2)
            self.assertEqual(t["absorbed"], 1)
            self.assertEqual(t["extracted"], 0)
            self.assertTrue(t["matches_total_cprs"])
            sha = hashlib.sha256(open(q, "rb").read()).hexdigest()
            self.assertEqual(t["sha256"], sha)
            self.assertEqual(t["sha256_16"], sha[:16])
            self.assertEqual(t["sha256_8"], sha[:8])
            self.assertIn("one pass", t["unit"])

    def test_self_mint_blind_spot_the_tuple_is_pinned_not_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = os.path.join(tmp, "queue.jsonl")
            self._write(q, [{"id": "cpr_a", "status": "promoted"}])
            t = rcc.compute_queue_state_tuple(q)
            # the fire's own mint lands AFTER the read
            with open(q, "a", encoding="utf-8") as f:
                f.write(json.dumps({"id": "cpr_mint", "status": "extracted"}) + "\n")
            live = hashlib.sha256(open(q, "rb").read()).hexdigest()
            self.assertNotEqual(t["sha256"], live)      # the tuple is pinned to its read
            self.assertEqual(t["unique_ids"], 1)         # the mint is not in it
            self.assertIn("NEXT fire", t["self_mint_blind_spot"])
            nxt = rcc.compute_queue_state_tuple(q)       # the next fire sees it
            self.assertEqual(nxt["sha256"], live)
            self.assertEqual(nxt["unique_ids"], 2)

    def test_matches_total_cprs_discloses_disagreement_never_hides_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = os.path.join(tmp, "queue.jsonl")
            self._write(q, [{"id": "cpr_a", "status": "promoted"}])
            self.assertFalse(rcc.compute_queue_state_tuple(q, total_cprs=2)["matches_total_cprs"])
            self.assertIsNone(rcc.compute_queue_state_tuple(q)["matches_total_cprs"])

    def test_absent_queue_is_unpinned_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = rcc.compute_queue_state_tuple(os.path.join(tmp, "missing.jsonl"))
            self.assertFalse(t["pinned"])
            self.assertEqual(t["reason"], "queue_absent")
            self.assertIsNone(t["sha256_16"])
            self.assertIsNone(t["unique_ids"])


class PersistenceHalf(unittest.TestCase):
    def test_tuple_is_measured_at_the_read_and_persisted_beside_total_cprs(self):
        i_load = _SRC.index("queue = load_queue(queue_path)")
        i_tuple = _SRC.index(
            "queue_state_tuple = compute_queue_state_tuple(queue_path, total_cprs=len(queue))",
            i_load)
        i_total = _SRC.index('"total_cprs": len(queue),', i_tuple)
        i_field = _SRC.index('"queue_state_tuple": queue_state_tuple,', i_total)
        i_size = _SRC.index('"inscribed_index_size": len(inscribed_ids),', i_field)
        self.assertLess(i_load, i_tuple)
        self.assertLess(i_total, i_field)
        self.assertLess(i_field, i_size)


if __name__ == "__main__":
    unittest.main()
