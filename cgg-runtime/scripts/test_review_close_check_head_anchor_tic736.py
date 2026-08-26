#!/usr/bin/env python3
"""Fixtures for the /review-736 HEAD-ANCHOR RELAXATION (bk-close-check-head-anchor-relaxation).

Ruling: /review 736, cpr_mogul_review_close_check_955e9009a2da
PROMOTE-TO-PROCEDURAL-HOME, Architect-ratified in-tic (receipt
audit-logs/governance/receipts/2026-08-25-tic736-review-docket-and-wave5-residue-ratification.json).
The remedy-class TYPING landed at the ruling; THIS suite covers the RELAXATION
half only — admit Class-B heads (an admitted inscription verb present but
subject-prefixed off the head) WITHOUT admitting Class-A objects (born blocks,
ledger-tags metadata, home-pointers) and WITHOUT weakening the skip-head
exclusion.

Every documented conditional gets BOTH arms
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths). The
Class-A fixtures are deliberately ADVERSARIAL as well as realistic: in the live
corpus every wrong-object head carries its verb at word 4+, so the live run can
never exercise that guard (declined_by_exclusion.excluded_wrong_object_head
reads an honest 0). A guard the population does not exercise is proven HERE or
it is not proven at all.
"""

import importlib.util
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "review_close_check", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check"] = rcc
_spec.loader.exec_module(rcc)


# --- The four measured Class-B shapes, verbatim heads from the live corpus at
# build tic 736 (constitution-ledger, cgg-ledger). Kept verbatim so a future
# authoring-style change that breaks them breaks a test, not a counter.
CLASS_B_HEADS = {
    "subject_two_words_promoted":
        "<!-- Non-derivability criterion promoted from CogPR-110 (tic 118). -->",
    "subject_one_word_refinement":
        "<!-- tic-733 refinement appendix promoted from "
        "cpr_mogul_economy_heartbeat_51aaf3773488 (birth_tic 730). -->",
    "subject_two_words_hyphenated":
        "<!-- scope-fence ray promoted from "
        "cpr_maturity_keys_to_uncertainty_both_triggers_nonoperative_tic676 (t676). -->",
    "subject_label_colon_absorbed":
        "<!-- C5 REINFORCE: absorbed narrow residual from "
        "cpr_situational_dehydration_biases_retrieval_origin_to_situation_tic377. -->",
}


class HermeticIndexCase(unittest.TestCase):
    """build_inscribed_index also sweeps ~/.claude/CLAUDE.md and the auto-memory
    dir; point HOME into a sandbox so real surfaces never leak into fixture counts
    (cgg-ledger#self-locating-artifact-test-isolation)."""

    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self._orig_expanduser = os.path.expanduser
        self._orig_home = Path.home
        home = self._home.name
        os.path.expanduser = (
            lambda p: p.replace("~", home, 1) if p.startswith("~") else p)
        Path.home = classmethod(lambda cls: Path(home))
        rcc.os.path.expanduser = os.path.expanduser

    def tearDown(self):
        os.path.expanduser = self._orig_expanduser
        rcc.os.path.expanduser = self._orig_expanduser
        Path.home = self._orig_home
        self._home.cleanup()

    def index(self, body, queue_ids=None):
        """Write ONE governance surface carrying `body`; return (inscribed, diag)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(body, encoding="utf-8")
        diag = {}
        inscribed = rcc.build_inscribed_index(
            str(root), queue_ids=queue_ids, diagnostics=diag)
        return inscribed, diag


# ---------------------------------------------------------------------------
# 1. Class B is ADMITTED
# ---------------------------------------------------------------------------

class TestClassBAdmitted(HermeticIndexCase):

    def test_each_measured_class_b_head_enters_the_index(self):
        for name, head in CLASS_B_HEADS.items():
            with self.subTest(shape=name):
                inscribed, diag = self.index(head + "\n")
                self.assertTrue(
                    inscribed,
                    f"{name}: Class-B head donated no tokens to the index")
                self.assertEqual(
                    diag["unmatched_provenance_shaped_count"], 0,
                    f"{name}: admitted comment must NOT also count as residue")
                self.assertEqual(
                    diag["head_anchor_relaxation"]["comments_admitted"], 1)

    def test_named_ids_become_index_visible(self):
        """The build dispatch's index-visibility demand, at fixture scale."""
        body = "\n".join(CLASS_B_HEADS.values()) + "\n"
        inscribed, _ = self.index(body)
        for cid in (
            "cpr_mogul_economy_heartbeat_51aaf3773488",
            "cpr_maturity_keys_to_uncertainty_both_triggers_nonoperative_tic676",
            "cpr_situational_dehydration_biases_retrieval_origin_to_situation_tic377",
            "CogPR-110",
        ):
            self.assertIn(cid, inscribed)

    def test_relaxed_admission_is_disclosed_per_side(self):
        inscribed, diag = self.index(
            CLASS_B_HEADS["subject_one_word_refinement"] + "\n")
        block = diag["head_anchor_relaxation"]
        self.assertEqual(block["max_subject_prefix_words"], 3)
        self.assertEqual(block["comments_admitted"], 1)
        self.assertEqual(block["token_occurrences_admitted"], 1)
        self.assertEqual(
            block["declined_by_exclusion"],
            {"excluded_inline_status_marker": 0,
             "excluded_skip_head": 0,
             "excluded_wrong_object_head": 0})
        self.assertEqual(len(block["samples"]), 1)

    def test_head_anchored_path_is_unchanged(self):
        """The pre-existing admission path still admits, and is not double-counted."""
        inscribed, diag = self.index(
            "<!-- promoted from cpr_plain_head_anchored_tic100 -->\n")
        self.assertIn("cpr_plain_head_anchored_tic100", inscribed)
        self.assertEqual(diag["unit_declaration"]["matched_comment_count"], 1)
        # a head-anchored comment is NOT re-processed by the relaxed branch
        self.assertEqual(diag["head_anchor_relaxation"]["comments_admitted"], 0)


# ---------------------------------------------------------------------------
# 2. Class A stays EXCLUDED — realistic AND adversarial
# ---------------------------------------------------------------------------

class TestClassAExcluded(HermeticIndexCase):

    def _assert_excluded(self, comment, expect_decline=None):
        inscribed, diag = self.index(comment + "\n")
        self.assertEqual(
            inscribed, set(),
            f"Class-A object leaked into the index: {comment[:80]}")
        self.assertEqual(diag["head_anchor_relaxation"]["comments_admitted"], 0)
        if expect_decline:
            self.assertEqual(
                diag["head_anchor_relaxation"]["declined_by_exclusion"][expect_decline],
                1,
                "the refusal must be COUNTED, not silent")
        return diag

    # --- born block (--agnostic-candidate) ---

    def test_born_block_realistic_excluded(self):
        diag = self._assert_excluded(
            "<!-- --agnostic-candidate\n"
            "id: cpr_pipeline_audio_drift_tic149\n"
            "status: promoted\n"
            "lesson: \"a birth record is not an inscription witness\"\n"
            "-->")
        # still typed as residue by the (untouched) remedy classifier
        self.assertEqual(
            diag["unmatched_remedy_class_counts"],
        {"wrong_object_class": 1, "head_anchor_gap": 0, "vocabulary_gap": 0})

    def test_born_block_ADVERSARIAL_head_adjacent_verb_excluded(self):
        """The guard's real job: a born block whose verb sits INSIDE the bound.

        The live corpus cannot exercise this (every born head carries its verb at
        word 4+), so without this fixture the exclusion is asserted, not proven.
        """
        self._assert_excluded(
            "<!-- --agnostic-candidate promoted from cpr_born_adversarial_tic999 -->",
            expect_decline="excluded_wrong_object_head")

    # --- ledger-tags metadata ---

    def test_ledger_tags_realistic_excluded(self):
        self._assert_excluded(
            "<!-- ledger-tags: authority_class=signal_and_queue_manifold | "
            "rung=domain | born_tic=653 | promoted_tic=680 | "
            "merged_from=cpr_supply_window_consumed_by_route_completion_tic657 -->")

    def test_ledger_tags_ADVERSARIAL_head_adjacent_verb_excluded(self):
        self._assert_excluded(
            "<!-- ledger-tags: promoted from cpr_tags_adversarial_tic999 -->",
            expect_decline="excluded_wrong_object_head")

    def test_promoted_tic_tag_key_is_not_the_verb(self):
        """`promoted_tic=680` must never read as the verb `promoted`.

        The trailing \\b in the relaxed pattern is what holds this: `_` is a word
        character, so there is no boundary after `promoted` in `promoted_tic`.
        """
        self.assertIsNone(
            rcc._HEAD_SUBJECT_PREFIX_VERB_RE.match(
                "<!-- tags: promoted_tic=680 cpr_x_tic1 -->"))

    # --- home-pointer ---

    def test_home_pointer_realistic_excluded(self):
        self._assert_excluded(
            "<!-- home-pointer from "
            "cpr_changelog_fix_entry_impact_is_a_config_shape_probe_not_a_read_tic501 "
            "at /review 635 (SKIP-with-home; loading home, not a new body) -->")

    def test_home_pointer_ADVERSARIAL_head_adjacent_verb_excluded(self):
        self._assert_excluded(
            "<!-- home-pointer promoted from cpr_pointer_adversarial_tic999 -->",
            expect_decline="excluded_wrong_object_head")

    # --- inline status marker (measured at this build) ---

    def test_inline_status_marker_excluded(self):
        """`<!-- status: promoted | promoted_to: … -->` is a writeback mirror.

        Measured at build tic 736 as the ONE token-less comment the relaxed
        predicate would otherwise newly admit — it would have moved the declared
        POPULATION (matched_comment_count) for a metadata object.
        """
        self._assert_excluded(
            "<!-- status: promoted | promoted_to: "
            "audit-logs/governance/constitution-ledger/ledger.md#anchor -->",
            expect_decline="excluded_inline_status_marker")


# ---------------------------------------------------------------------------
# 3. Skip-head exclusion NOT weakened
# ---------------------------------------------------------------------------

class TestSkipHeadUnweakened(HermeticIndexCase):

    def test_skip_head_realistic_still_excluded(self):
        inscribed, diag = self.index(
            "<!-- SKIP at /review 700: cpr_skipped_lesson_tic690 not net-new -->\n")
        self.assertEqual(inscribed, set())
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0,
                         "a skip pointer is neither indexed NOR counted as residue")

    def test_skip_head_ADVERSARIAL_with_head_adjacent_verb_still_excluded(self):
        """The relaxation must not become the back door for what /review 719
        deliberately refuses."""
        inscribed, diag = self.index(
            "<!-- SKIP-with-home: promoted from cpr_skip_backdoor_tic999 -->\n")
        self.assertEqual(inscribed, set())
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)
        self.assertEqual(
            diag["head_anchor_relaxation"]["declined_by_exclusion"]["excluded_skip_head"],
            1, "the skip refusal must be COUNTED, so the guard is not an assurance")

    def test_predicate_level_skip_refusal(self):
        admitted, reason = rcc._relaxation_verdict(
            "<!-- skip: promoted from cpr_x_tic1 -->")
        self.assertFalse(admitted)
        self.assertEqual(reason, "excluded_skip_head")


# ---------------------------------------------------------------------------
# 4. NEGATIVE CONTROL — a novel unadmitted head still fires the counter
# ---------------------------------------------------------------------------

class TestNegativeControl(HermeticIndexCase):

    def test_novel_head_fires_the_counter_never_the_index(self):
        """A genuinely NEW verdict head must still surface as residue.

        This is the /review-719 contract the relaxation must not dissolve: a new
        shape enters the matcher OR enters the residue report — never neither.
        """
        inscribed, diag = self.index(
            "<!-- TRANSMUTED-AT-TIC-999 from cpr_novel_head_tic999 -->\n")
        self.assertEqual(inscribed, set(), "novel head must NOT reach the index")
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)
        self.assertEqual(diag["head_anchor_relaxation"]["comments_admitted"], 0)

    def test_vocabulary_gap_no_admitted_verb_anywhere_stays_in_the_counter(self):
        """`landed-from` with NO admitted verb anywhere: still vocabulary_gap."""
        inscribed, diag = self.index(
            "<!-- landed-from cpr_priority_is_calibrated_at_cadence_not_boot_tic421 "
            "(/review 421 -> cgg-ledger#priority-is-calibrated-at-cadence-not-boot; "
            "impl gate tic 422). Band: COGNITIVE. -->\n")
        self.assertEqual(inscribed, set())
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)
        self.assertEqual(
            diag["unmatched_remedy_class_counts"],
        {"vocabulary_gap": 1, "wrong_object_class": 0, "head_anchor_gap": 0})

    def test_body_prose_verb_far_from_head_is_NOT_admitted(self):
        """The bound's discriminating case, measured live at 8 subject words.

        `landed-from` is a VOCABULARY gap whose cure is verb registration in a
        different lane. Admitting it here on the strength of `doctrine inscribed
        at …` deep in body prose would collapse two remedy classes with opposite
        cures into one — the exact failure the /review-735 disclosure-parity ray
        names.
        """
        inscribed, diag = self.index(
            "<!-- landed-from cpr_c47_generation_suffix_convention_tic274 "
            "(PROMOTE-SPEC at /review tic 278; doctrine inscribed at "
            "canonical_developer/context-grapple-gun/x.md). -->\n")
        self.assertEqual(inscribed, set())
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)
        self.assertEqual(diag["head_anchor_relaxation"]["comments_admitted"], 0)


# ---------------------------------------------------------------------------
# 5. The bound itself
# ---------------------------------------------------------------------------

class TestPrefixBound(unittest.TestCase):

    def test_bound_is_three_and_both_arms_are_exercised(self):
        self.assertEqual(rcc._HEAD_SUBJECT_PREFIX_MAX_WORDS, 3)
        inside = "<!-- one two three promoted from cpr_x_tic1 -->"
        outside = "<!-- one two three four promoted from cpr_x_tic1 -->"
        self.assertTrue(rcc._is_head_anchor_relaxed_witness(inside))
        self.assertFalse(rcc._is_head_anchor_relaxed_witness(outside))

    def test_zero_subject_words_is_the_head_anchored_path_not_this_one(self):
        """Caller contract: head-anchored membership is decided elsewhere."""
        admitted, reason = rcc._relaxation_verdict("<!-- promoted from cpr_x_tic1 -->")
        self.assertFalse(admitted)
        self.assertEqual(reason, rcc.RELAXED_NO_VERB)

    def test_prefix_cannot_cross_a_newline(self):
        """A multi-line YAML body may never reach up and donate a verb to the head."""
        self.assertIsNone(
            rcc._HEAD_SUBJECT_PREFIX_VERB_RE.match(
                "<!-- subject\npromoted from cpr_x_tic1 -->"))

    def test_prefix_cannot_swallow_a_comment_terminator(self):
        self.assertIsNone(
            rcc._HEAD_SUBJECT_PREFIX_VERB_RE.match("<!-- x --> promoted from cpr_y "))


# ---------------------------------------------------------------------------
# 6. /review-724 RIDER-1 over-admission routes must NOT widen
# ---------------------------------------------------------------------------

class TestRider1RoutesDoNotWiden(HermeticIndexCase):

    def test_cpr_ref_regex_is_untouched(self):
        """Token admission is byte-identical; only comment RECOGNITION widened."""
        self.assertEqual(rcc._CPR_REF_RE.pattern, r"(cpr_[A-Za-z0-9_]+|CogPR-\d+)")

    def test_reserved_prefix_exclusion_applies_inside_a_relaxed_comment(self):
        inscribed, diag = self.index(
            "<!-- scope-fence ray promoted from cpr_real_tic700. "
            "era: cpr_era_tic_700_749 -->\n")
        self.assertIn("cpr_real_tic700", inscribed)
        self.assertNotIn("cpr_era_tic_700_749", inscribed)
        self.assertIn("cpr_era_tic_700_749", diag["reserved_tokens_excluded"])

    def test_route_census_is_not_blind_on_the_relaxed_path(self):
        """A substring occurrence inside a RELAXED comment is disclosed exactly as
        it would be inside a head-anchored one — the RIDER-1 disclosure must not
        go dark on the new admission path."""
        relaxed = ("<!-- scope-fence ray promoted from cpr_head_tic1. "
                   "Source: DONE_cpr_stepper_advance_tic718.json -->\n")
        anchored = ("<!-- promoted from cpr_head_tic1. "
                    "Source: DONE_cpr_stepper_advance_tic718.json -->\n")
        _, diag_r = self.index(relaxed)
        _, diag_a = self.index(anchored)
        routes_r = diag_r["unit_declaration"]["route_occurrence_counts"]
        routes_a = diag_a["unit_declaration"]["route_occurrence_counts"]
        self.assertEqual(routes_r, routes_a,
                         "route census must be identical across admission paths")
        self.assertEqual(routes_r["substring_of_cited_filename_or_path"], 1)
        self.assertEqual(routes_r["substring_of_longer_identifier"], 1)
        self.assertEqual(routes_r["head_subject_token"], 1)
        self.assertEqual(routes_r["body_scope_token"], 1)

    def test_queue_unresolved_disclosure_applies_on_the_relaxed_path(self):
        inscribed, diag = self.index(
            "<!-- scope-fence ray promoted from cpr_not_in_queue_tic1 -->\n",
            queue_ids={"cpr_something_else_tic2"})
        self.assertIn("cpr_not_in_queue_tic1", inscribed)
        self.assertEqual(diag["unresolved_against_queue_count"], 1)

    def test_boundary_rule_and_population_declare_the_relaxation(self):
        """A declared field that my change falsifies is a defect, not a detail."""
        _, diag = self.index("<!-- promoted from cpr_x_tic1 -->\n")
        unit = diag["unit_declaration"]
        self.assertIn("HEAD-ANCHOR RELAXATION", unit["boundary_rule"])
        self.assertIn("HEAD-ANCHOR RELAXATION", unit["population"])


# ---------------------------------------------------------------------------
# 7. Verb-vocabulary drift tripwire
# ---------------------------------------------------------------------------

class TestVerbAlternationParity(unittest.TestCase):
    """Three regexes now carry the inscription-verb alternation
    (_PROVENANCE_VERB_RE, _MIDCOMMENT_VERB_RE, _HEAD_SUBJECT_PREFIX_VERB_RE). A
    third copy is a sibling-site footgun
    (cgg-ledger#named-footgun-guard-leaves-sibling-site-unfixed) — this pins them
    to ONE verb set so a future verb registration cannot land in two of three."""

    VERBS = {
        "conditional-promoted", "promote-as-refinement", "promoted-spec",
        "promoted", "absorbed", "refinement", "refined", "reinforced",
        "review-executed", "inscribed", "conformation", "conformed", "extended",
        "merged", "merge", "superseded",
    }

    @staticmethod
    def _verbs_in(pattern):
        found = set()
        for alt in re.findall(r"[a-z][a-z-]+", pattern):
            if alt in TestVerbAlternationParity.VERBS:
                found.add(alt)
        return found

    def test_all_three_matchers_carry_the_same_verb_set(self):
        a = self._verbs_in(rcc._PROVENANCE_VERB_RE.pattern)
        b = self._verbs_in(rcc._MIDCOMMENT_VERB_RE.pattern)
        c = self._verbs_in(rcc._HEAD_SUBJECT_PREFIX_VERB_RE.pattern)
        self.assertEqual(a, self.VERBS)
        self.assertEqual(b, self.VERBS)
        self.assertEqual(c, self.VERBS)

    def test_every_admitted_verb_is_reachable_subject_prefixed(self):
        for verb in sorted(self.VERBS):
            with self.subTest(verb=verb):
                self.assertTrue(
                    rcc._is_head_anchor_relaxed_witness(
                        f"<!-- subject {verb} from cpr_x_tic1 -->"),
                    f"{verb} admitted at the head but not one word in")


if __name__ == "__main__":
    unittest.main(verbosity=2)
