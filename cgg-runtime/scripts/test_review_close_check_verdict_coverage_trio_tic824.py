#!/usr/bin/env python3
"""Fixtures for the tic-824 review-close-check TRIO — three ruled increments,
one change, one producer-sha move.

  I1  RULED /review 822 Q2 (cpr_mogul_review_close_check_0c8fb7d7972f, ABSORBED
      onto cgg-ledger#named-footgun-guard-leaves-sibling-site-unfixed):
      retire the unconstructible `skip_status_mismatch` class, have the artifact
      declare the skipped arm CENSUS-ONLY, and persist `skipped_ids` as a
      membership arm.
  I2  RULED /review 823 Q2 (cpr_mogul_review_close_check_2b2f04a1e6bb, ABSORBED
      MODIFIED as the VERDICT-DISPATCH refinement on
      cgg-ledger#queue-index-status-coverage-discipline, WIDENED at adjudication
      to every verdict class that falls through the chain): the artifact
      declares per verdict class whether it VERIFIES / only COUNTS / does not
      READ it, and persists member ids for every class it does not verify; a
      supersede target's NAMESPACE is typed before anything calls it unresolved.
  I3  RULED /review 823 round 2 Q4 (F-822-G37-3): publish the PER-MEMBER map
      from each index-loss token to its sub-type.

DOES-NOT-SATISFY RIDER (/review 823 Q2, travels verbatim): this increment does
NOT make the checker a lifecycle auditor, does NOT assert that any past
supersede, rejection or absorb was wrong, does NOT change which findings are
genuine or known, and does NOT repair any row.

DOES-NOT-SATISFY (/review 822 Q2 backlog row, travels verbatim): Neither cure
creates a per-row SKIP check: that needs a machine-readable verdict source that
does not exist (/review 819 Q1).

EVIDENCE DISCIPLINE: every assertion reads the WRITTEN artifact or the returned
structure. Expected values are literals or are known BY CONSTRUCTION of each
fixture corpus — no expected value is computed with the same expression the
checker uses, because a test that matched whatever the code happened to produce
could not fail.

SCOPE HONESTY: fixture-green over synthetic zones and synthetic corpora.
FIXTURE-GREEN IS NOT LIVE-GREEN. Nothing here runs against the live zone, the
live queue, or the installed runtime. The real-population figures the strike
readers measured (129 skipped / 269 absorbed / 43 rejected / 23 superseded) are
NOT re-measured here.

Every documented conditional gets BOTH arms
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths): the
per-member map's threaded AND not-threaded arms at route (f); the collision arm
AND the single-subtype arm; a fall-through class WITH members and a class with
none.

Run:  python3 -m unittest test_review_close_check_verdict_coverage_trio_tic824
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
    "review_close_check_824", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check_824"] = rcc
_spec.loader.exec_module(rcc)

ROUTE_F = "promotion_witness_comment_shed_by_matcher"

# Riders, as literals, so the test fails if the shipped text drifts by a byte.
RIDER_823 = (
    "this increment does NOT make the checker a lifecycle auditor, does NOT "
    "assert that any past supersede, rejection or absorb was wrong, does NOT "
    "change which findings are genuine or known, and does NOT repair any row."
)
NOTE_822 = (
    "Neither cure creates a per-row SKIP check: that needs a machine-readable "
    "verdict source that does not exist (/review 819 Q1)."
)

# --- the fixture queue, member sets known BY CONSTRUCTION --------------------
SKIPPED_IDS = ["cpr_fix_skip_a", "cpr_fix_skip_b", "cpr_fix_skip_c"]
ABSORBED_IDS = ["cpr_fix_absorbed_a"]
REJECTED_IDS = ["cpr_fix_rejected_a"]
SUP_QUEUE_TARGET = "cpr_fix_sup_queue_target"
SUP_DOC_TARGET = "cpr_fix_sup_doc_target"
SUP_ORPHAN_TARGET = "cpr_fix_sup_absent_target"
SETTLED_ID = "cpr_fix_settled_a"


def _queue_rows():
    """A mixed queue covering every dispatch arm exactly once per class."""
    rows = [{"id": i, "status": "skipped"} for i in SKIPPED_IDS]
    rows += [{"id": i, "status": "absorbed"} for i in ABSORBED_IDS]
    rows += [{"id": i, "status": "rejected"} for i in REJECTED_IDS]
    rows += [
        # superseded_by resolves to a live queue id
        {"id": SUP_QUEUE_TARGET, "status": "superseded",
         "superseded_by": ABSORBED_IDS[0]},
        # superseded_by is a DOCUMENT-SECTION POINTER — the real shape carried
        # by CogPR-54 / CogPR-55, which a queue-id-only resolver misreads as
        # unresolved. This is the namespace clause's whole reason to exist.
        {"id": SUP_DOC_TARGET, "status": "superseded",
         "superseded_by": "substrate-performance-risk-map.md Hard Rule #6"},
        # id-SHAPED but absent from this queue projection
        {"id": SUP_ORPHAN_TARGET, "status": "superseded",
         "superseded_by": "cpr_not_in_this_queue_at_all"},
        # recognized by the lifecycle_state branch, not by status
        {"id": SETTLED_ID, "status": "implemented",
         "lifecycle_state": "terminal_positive"},
    ]
    return rows


class HermeticZoneCase(unittest.TestCase):
    """HOME sandboxed so real surfaces never leak into fixture counts
    (cgg-ledger#self-locating-artifact-test-isolation).

    THE POPULATION QUESTION, stated because it decides the proof: the checker
    WRITES through `project_dir` (every write lands under audit_logs_path of the
    zone) and READS part of its universe through ambient HOME
    (AUTO_MEMORY_DIR = Path.home()/'.claude'/'projects'/...). A fixture zone
    protects the writer; a sandboxed HOME shrinks the reader to the fixture,
    which is what makes these counts reproducible AND what guarantees no test
    here can touch the real auto-memory directory.
    """

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

    def zone(self, tic=930, rows=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        z = pathlib.Path(tmp.name)
        (z / ".ticzone").write_text("{}", encoding="utf-8")
        al = z / "audit-logs"
        (al / "cprs").mkdir(parents=True)
        (al / "mogul" / "mandates").mkdir(parents=True)
        (al / "cprs" / "queue.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in (rows or _queue_rows())),
            encoding="utf-8")
        (al / "mogul" / "mandates" / "current.json").write_text(
            json.dumps({"mandate_id": f"tic-{tic}-fixture", "tic": tic}),
            encoding="utf-8")
        return z

    def report(self, tic=930, rows=None):
        """Run the check and read the WRITTEN artifact back off disk."""
        z = self.zone(tic=tic, rows=rows)
        buf = io.StringIO()
        with redirect_stderr(buf):
            rcc.run_check(str(z))
        rd = z / "audit-logs" / "mogul" / "cycle-reports" / "review-close-checks"
        arts = sorted(rd.glob("tic-*-check.json"))
        self.assertEqual(len(arts), 1, f"expected exactly one artifact, got {arts}")
        return json.loads(arts[0].read_text(encoding="utf-8"))


# =========================== I1 — THE SKIPPED ARM ===========================
class SkippedArmRetiredAndDeclared(HermeticZoneCase):

    def test_skip_status_mismatch_class_is_unconstructible_on_any_input(self):
        """THE RETIREMENT, proved on the input the OLD class needed.

        The old finding fired only when status != 'skipped'. That input could
        never arrive through the dispatch guard, but it CAN be handed to the
        function directly — which is exactly how a revert control tells a
        retired class from a merely shadowed one. Under the cure the class is
        unconstructible on EVERY input, including this one.
        """
        self.assertEqual(rcc.check_skipped("cpr_x", {"status": "skipped"}), [])
        self.assertEqual(rcc.check_skipped("cpr_x", {"status": "promoted"}), [])
        self.assertEqual(rcc.check_skipped("cpr_x", {}), [])

    def test_no_construction_site_for_the_retired_type_remains(self):
        """Narration may name the retired class; no producer may WRITE it."""
        src = (_HERE / "review-close-check.py").read_text(encoding="utf-8")
        self.assertNotIn('"type": "skip_status_mismatch"', src)

    def test_skipped_ids_persisted_as_a_membership_arm(self):
        ms = self.report()["membership_sets"]
        self.assertEqual(ms["skipped_ids"], sorted(SKIPPED_IDS))
        self.assertEqual(ms["skipped_ids_count"], 3)

    def test_skipped_ids_count_agrees_with_the_verdict_counter(self):
        """The magnitude and the members are the same population."""
        r = self.report()
        self.assertEqual(r["verdict_counts"]["skipped"], 3)
        self.assertEqual(r["membership_sets"]["skipped_ids_count"], 3)

    def test_skipped_arm_carries_its_attribution_stability_entry(self):
        st = self.report()["membership_sets"]["attribution_stability"]
        self.assertIs(
            st["skipped_ids"]["member_identity_stable_under_upstream_insertion"],
            True)

    def test_artifact_declares_the_skipped_arm_census_only(self):
        """The disclosure gap strike822 found: across all 26 `skip` occurrences
        in the tic-819 artifact, nothing said the arm verifies nothing."""
        cov = self.report()["verdict_class_coverage"]
        self.assertEqual(cov["classes"]["skipped"]["coverage"], "counted_only")
        self.assertIn("CENSUS-ONLY", cov["skipped_arm_note"])
        self.assertIn(NOTE_822, cov["skipped_arm_note"])

    def test_pair_coverage_no_longer_calls_skipped_unpersisted(self):
        """The closed consumer set of the new arm: pairs[2] said skipped was
        NOT persisted. Leaving that sentence would have made the artifact lie
        about itself."""
        pairs = self.report()["pair_coverage"]["pairs"]
        vc = [p for p in pairs if p["pair"].startswith("verdict_counts_delta")]
        self.assertEqual(len(vc), 1)
        self.assertIn("skipped_ids", vc[0]["membership_sets"])
        self.assertNotIn("and skipped populations are NOT persisted as sets",
                         vc[0]["status"])
        # deferred is still honestly declared absent
        self.assertIn("deferred population is NOT persisted", vc[0]["status"])


# ================= I2 — VERDICT-CLASS COVERAGE AND MEMBERS ==================
class VerdictClassCoverage(HermeticZoneCase):

    def test_every_row_is_classified_exactly_once(self):
        """No row floats. classified == latest-per-id rows, unclassified == 0."""
        cov = self.report()["verdict_class_coverage"]
        t = cov["totals"]
        self.assertEqual(t["latest_per_id_rows"], len(_queue_rows()))
        self.assertEqual(t["classified"], t["latest_per_id_rows"])
        self.assertEqual(t["unclassified"], 0)

    def test_fall_through_classes_are_declared_not_read(self):
        cov = self.report()["verdict_class_coverage"]["classes"]
        for status in ("absorbed", "rejected", "superseded"):
            self.assertEqual(cov[status]["coverage"], "not_read", status)

    def test_fall_through_classes_persist_their_members_by_id(self):
        """The supersede at tic 820 occurred ZERO times in 466,619 bytes of
        artifact. Under the cure every unverified class carries its members."""
        cov = self.report()["verdict_class_coverage"]["classes"]
        self.assertEqual(cov["absorbed"]["members_not_verified"],
                         sorted(ABSORBED_IDS))
        self.assertEqual(cov["rejected"]["members_not_verified"],
                         sorted(REJECTED_IDS))
        self.assertEqual(
            cov["superseded"]["members_not_verified"],
            sorted([SUP_QUEUE_TARGET, SUP_DOC_TARGET, SUP_ORPHAN_TARGET]))

    def test_settled_lifecycle_rows_are_recognized_not_called_fallthrough(self):
        """Branch four is a DIFFERENT arm from no-branch-at-all; collapsing
        them would misreport a settled disposition as an unread class."""
        cov = self.report()["verdict_class_coverage"]["classes"]
        self.assertEqual(cov["implemented"]["coverage"], "recognized_settled")
        self.assertEqual(cov["implemented"]["members_not_verified"],
                         [SETTLED_ID])

    def test_members_persisted_at_is_an_address_not_a_bare_true(self):
        """A bare True here would be the same cannot-be-false shape this round
        retires."""
        cov = self.report()["verdict_class_coverage"]["classes"]
        addr = cov["superseded"]["members_persisted_at"]
        self.assertIsInstance(addr, str)
        self.assertIn("members_not_verified", addr)
        self.assertIn("membership_sets.skipped_ids",
                      cov["skipped"]["members_persisted_at"])

    def test_supersede_target_namespace_typed_before_anything_is_unresolved(self):
        """THE NAMESPACE CLAUSE. A queue-id-only resolver reads a document
        section pointer as unresolved; two of the 23 real superseded rows carry
        exactly that shape."""
        ns = self.report()["verdict_class_coverage"][
            "supersede_target_namespaces"]["by_member"]
        self.assertEqual(ns[SUP_QUEUE_TARGET], "queue_id")
        self.assertEqual(ns[SUP_DOC_TARGET], "document_section_pointer")
        self.assertEqual(ns[SUP_ORPHAN_TARGET],
                         "queue_id_absent_from_this_queue")
        # the word the clause exists to forbid appears in no typing
        self.assertNotIn("unresolved", set(ns.values()))

    def test_namespace_census_sums_to_the_superseded_population(self):
        cov = self.report()["verdict_class_coverage"]
        census = cov["supersede_target_namespaces"]["census"]
        self.assertEqual(sum(census.values()), 3)
        self.assertEqual(cov["classes"]["superseded"]["count"], 3)

    def test_rider_travels_verbatim_into_the_artifact(self):
        """A reader of verdict_class_coverage could mistake members-with-
        namespaces for lifecycle auditing. The rider rides in the artifact."""
        cov = self.report()["verdict_class_coverage"]
        self.assertIn(RIDER_823, cov["does_not_satisfy"])

    def test_the_increment_changes_no_finding(self):
        """The rider says it does not change which findings are genuine or
        known. On this fixture the unverified classes emit nothing at all."""
        r = self.report()
        self.assertEqual(r["summary"]["by_type"], {})
        self.assertEqual(r["summary"]["total_findings"], 0)
        self.assertEqual(r["summary"]["genuine_count"], 0)
        self.assertEqual(r["summary"]["known_count"], 0)
        self.assertIs(r["summary"]["universe_classified"], True)

    def test_a_queue_with_only_verified_rows_owes_no_unverified_members(self):
        """The other arm: a class whose every member took a verified arm."""
        cov = self.report(rows=[{"id": "cpr_only_promoted", "status": "promoted"}]
                          )["verdict_class_coverage"]
        self.assertEqual(cov["classes"]["promoted"]["coverage"], "verified")
        self.assertEqual(cov["classes"]["promoted"]["members_not_verified"], [])
        self.assertEqual(cov["classes"]["promoted"]["members_persisted_at"],
                         "membership_sets.promoted_ids")
        self.assertEqual(cov["totals"]["members_not_verified_total"], 0)


# ============ I3 — PER-MEMBER index_loss TOKEN -> SUB-TYPE MAP ==============
ADMITTED = ("<!-- PROMOTE-AS-REFINEMENT promoted from "
            "cpr_mogul_review_close_check_1d0125de5ee3 at /review 771 -->")
SHED_SAME_TOKEN = ("<!-- consumer-carry note from "
                   "cpr_mogul_review_close_check_1d0125de5ee3 (/review 772) -->")
SHED_ABSENT = ("<!-- consumer-carry note from "
               "cpr_mogul_review_close_check_feedbeef0000 (/review 772) -->")


class PerMemberTokenSubtypeMap(HermeticZoneCase):

    def index(self, body):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        (root / "CLAUDE.md").write_text(body, encoding="utf-8")
        diag = {}
        buf = io.StringIO()
        with redirect_stderr(buf):
            rcc.build_inscribed_index(str(root), queue_ids=None, diagnostics=diag)
        return diag["unmatched_disposition_split"]

    def test_map_keys_equal_the_published_union(self):
        """F-822-G37-3: the union said WHICH tokens; the map says which SUB-TYPE
        each one is. The two must describe the same membership."""
        split = self.index(
            ADMITTED + "\n\n" + SHED_SAME_TOKEN + "\n\n" + SHED_ABSENT + "\n")
        self.assertEqual(
            sorted(split["index_loss_member_token_subtypes"]),
            split["index_loss_member_tokens"])

    def test_each_member_carries_its_own_subtype(self):
        split = self.index(
            ADMITTED + "\n\n" + SHED_SAME_TOKEN + "\n\n" + SHED_ABSENT + "\n")
        m = split["index_loss_member_token_subtypes"]
        self.assertEqual(m["cpr_mogul_review_close_check_1d0125de5ee3"],
                         "index_loss_comment_only")
        self.assertEqual(m["cpr_mogul_review_close_check_feedbeef0000"],
                         "index_loss_id_absent")
        self.assertEqual(split["index_loss_member_token_subtype_collisions"], [])

    def test_per_member_map_and_parent_counts_agree(self):
        split = self.index(
            ADMITTED + "\n\n" + SHED_SAME_TOKEN + "\n\n" + SHED_ABSENT + "\n")
        self.assertEqual(split["index_loss_subtype_counts"],
                         {"index_loss_comment_only": 1,
                          "index_loss_id_absent": 1})

    def test_empty_population_publishes_an_empty_map_not_a_missing_key(self):
        """The other arm: no index_loss member at all."""
        split = self.index("<!-- --agnostic-candidate id: "
                           "cpr_mogul_review_close_check_cafebabe0001 -->\n")
        self.assertEqual(split["index_loss_member_tokens"], [])
        self.assertEqual(split["index_loss_member_token_subtypes"], {})
        self.assertEqual(split["index_loss_member_token_subtype_collisions"], [])


class RouteFNamesThisMembersSubtype(unittest.TestCase):
    """The consumer half: route (f) could name the POPULATION's sub-types
    (/review 812 Q2) but not THIS member's. Both arms of the new conditional."""

    def _attribution(self, token_subtypes):
        with tempfile.TemporaryDirectory() as td:
            art = {
                "inscribed_index_size": 0,
                "inscribed_index_unit": {"matched_comment_count": 0},
                "verdict_counts": {"promoted": 0, "deferred": 0, "skipped": 0},
                "membership_sets": {"index_tokens": [], "promoted_ids": []},
            }
            (pathlib.Path(td) / "tic-9-check.json").write_text(
                json.dumps(art), encoding="utf-8")
            return rcc.compute_cross_counter_attribution(
                td, "tic-10-check.json", 10,
                current_tokens=set(),
                current_promoted={"cpr_x_shedcase"},
                queue={"cpr_x_shedcase": {"status": "promoted",
                                          "landing_kind": "modify_and_merge"}},
                shed_witness_tokens={"cpr_x_shedcase"},
                index_loss_subtype_counts={"index_loss_id_absent": 1,
                                           "index_loss_comment_only": 0},
                index_loss_token_subtypes=token_subtypes,
            )

    def _member(self, a):
        return {m["member"]: m for m in a["attributed_members"]}["cpr_x_shedcase"]

    def test_threaded_arm_names_this_members_subtype(self):
        m = self._member(
            self._attribution({"cpr_x_shedcase": "index_loss_id_absent"}))
        self.assertEqual(m["catalog_route"], ROUTE_F)
        self.assertEqual(m["index_loss_subtype_of_this_member"],
                         "index_loss_id_absent")
        self.assertIn("THIS MEMBER's own token types as index_loss_id_absent",
                      m["note"])

    def test_not_threaded_arm_says_unmeasured_not_a_fabricated_subtype(self):
        m = self._member(self._attribution(None))
        self.assertEqual(m["catalog_route"], ROUTE_F)
        self.assertIsNone(m["index_loss_subtype_of_this_member"])
        self.assertIn("UNMEASURED here", m["note"])

    def test_the_binding_is_unchanged_by_this_cure(self):
        """No member enters or leaves route (f): the gate still fires on the
        PARENT membership set, exactly as /review 780 Q2 bound it."""
        for subtypes in ({"cpr_x_shedcase": "index_loss_comment_only"}, None):
            m = self._member(self._attribution(subtypes))
            self.assertEqual(m["catalog_route"], ROUTE_F)
            self.assertIs(m["catalog_covers"], True)
            self.assertIs(m["witness_comment_shed"], True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
