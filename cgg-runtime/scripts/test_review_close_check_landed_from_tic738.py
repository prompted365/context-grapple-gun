#!/usr/bin/env python3
"""Fixtures for the /review-737 LANDED-FROM VERB REGISTRATION.

Ruling: /review 737 round-2 verdict n=5, id M3-736-HAR — "register 'landed-from'
next build wave"; backlog row bk-landed-from-verb-registration; ratification
receipt audit-logs/governance/receipts/
2026-08-26-tic737-review-docket-and-16d-adoption-ratification.json.

WHAT THIS INCREMENT IS: the vocabulary_gap cure, landing in the lane the
/review-736 remedy typing named. At tics 736-737 the checker measured exactly
5 unmatched cpr-token-bearing comments typed `vocabulary_gap` — no admitted
inscription verb anywhere in the head window — and typed their ONE reachable
cure as VERB REGISTRATION. All 5 are `landed-from` heads in
cgg-runtime/skills/cadence/SKILL.md. Registering the verb makes those comments
inscription witnesses WITHOUT EDITING THEM: the comments already carried the
verb; only the reader's vocabulary lacked it.

WHAT THIS INCREMENT IS NOT (the apophatic perimeter, load-bearing):
  * NOT the head-anchor relaxation (/review 736). All 5 live heads are
    HEAD-ANCHORED — the verb sits at offset 0 of the head window — so they are
    admitted by _PROVENANCE_VERB_RE and never touch the relaxed branch. The
    relaxation's bound stays 3 and its live admission count is unmoved.
  * NOT a widening of WHICH TOKENS a read comment donates. _CPR_REF_RE, the
    reserved-prefix exclusion and the /review-724 RIDER-1 route census are
    byte-identical; only the head vocabulary grew.
  * NOT an exclusion repeal. A `landed-from` head that is ALSO a skip pointer,
    a wrong-object head, or an inline status marker must still be refused —
    registration must not become a back door into the three standing guards.

Every documented conditional gets BOTH arms
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths), and
the guards that the live corpus cannot exercise (no live `landed-from` carries a
skip/wrong-object/status head) are proven HERE adversarially or not at all —
the same discipline the tic-736 suite established.

Run: python3 test_review_close_check_landed_from_tic738.py
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


# --- The five measured live heads, VERBATIM from
# canonical_developer/context-grapple-gun/cgg-runtime/skills/cadence/SKILL.md at
# build tic 738 (the entire vocabulary_gap population, not a sample). Kept
# verbatim so a future authoring-style change breaks a TEST, not a counter.
LIVE_LANDED_FROM = {
    "born_authoring_dryrun": (
        '<!-- landed-from cpr_born_authoring_requires_dryrun_reachability_verify_tic554 '
        '(PROMOTE at /review tic 584, Architect-ratified "approve as recommended"; '
        'n=5 cross-tic recurrence; cure already shipped in cpr-extract --dry-run; '
        'Case-2 wire-the-rehydration-at-the-locus). Band: COGNITIVE. '
        'Domain rung: CGG cadence skill. -->'),
    "tic_framing_convention": (
        '<!-- landed-from cpr_tic_framing_convention_off_kilter_work_tic_vs_emission_tic_tic262 '
        '(tic 263 birth, /review at next-session pending). Architect-locked verbatim '
        'convention quoted at handoff body; cross-tic n≥3 framing drift evidence across '
        'tics 261-263. Runtime parity patch landed under Governance Tool Urgency Triage '
        '(code/template-wrong, doctrine incomplete) per handoff Production Next Actions #6. '
        'Band: COGNITIVE. Domain rung: CGG. Promotion adjudication: pending /review. -->'),
    "c47_generation_suffix": (
        '<!-- landed-from cpr_c47_generation_suffix_convention_for_orchestrator_state_entries_tic274 '
        '(PROMOTE-SPEC at /review tic 278; doctrine inscribed at '
        'canonical_developer/context-grapple-gun/CLAUDE.md; skill body extension owed at '
        'tic 280 per Verdict-Shape KI). Band: COGNITIVE. Domain rung: CGG. -->'),
    "parallel_rtch_rails": (
        '<!-- landed-from cpr_parallel_rtch_consolidate_rails_for_next_swarm_with_inbox_marker_dependency_signaling_tic277 '
        '(PROMOTE-SPEC at /review tic 278; doctrine inscribed at '
        'canonical_developer/context-grapple-gun/CLAUDE.md; skill body extension owed at '
        'tic 280 per Verdict-Shape KI; cross-tic n=2 validated tic 277 authoring → '
        'tic 278 execution). Band: COGNITIVE. Domain rung: CGG. -->'),
    "priority_calibrated_at_cadence": (
        '<!-- landed-from cpr_priority_is_calibrated_at_cadence_not_boot_tic421 '
        '(/review 421 PROMOTE -> cgg-ledger#priority-is-calibrated-at-cadence-not-boot; '
        'impl gate tic 422). Band: COGNITIVE. Domain rung: CGG. -->'),
}

# The token each live comment donates (one apiece — measured, not assumed).
LIVE_TOKENS = {
    "born_authoring_dryrun":
        "cpr_born_authoring_requires_dryrun_reachability_verify_tic554",
    "tic_framing_convention":
        "cpr_tic_framing_convention_off_kilter_work_tic_vs_emission_tic_tic262",
    "c47_generation_suffix":
        "cpr_c47_generation_suffix_convention_for_orchestrator_state_entries_tic274",
    "parallel_rtch_rails":
        "cpr_parallel_rtch_consolidate_rails_for_next_swarm_with_inbox_marker"
        "_dependency_signaling_tic277",
    "priority_calibrated_at_cadence":
        "cpr_priority_is_calibrated_at_cadence_not_boot_tic421",
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
# 1. The registration ADMITS — and admits at the HEAD-ANCHORED path
# ---------------------------------------------------------------------------

class TestLandedFromAdmitted(HermeticIndexCase):

    def test_each_live_head_enters_the_index(self):
        for name, comment in LIVE_LANDED_FROM.items():
            with self.subTest(shape=name):
                inscribed, diag = self.index(comment + "\n")
                self.assertIn(
                    LIVE_TOKENS[name], inscribed,
                    f"{name}: registered landed-from head donated no token")
                self.assertEqual(
                    diag["unmatched_provenance_shaped_count"], 0,
                    f"{name}: an admitted comment must NOT also count as residue")

    def test_admission_is_head_anchored_NOT_the_relaxation(self):
        """The increment's sharpest boundary claim, per shape.

        All five live heads carry the verb at offset 0 of the head window, so
        _PROVENANCE_VERB_RE matches and the relaxed branch is never reached.
        If this ever flips, the two increments' cures have been conflated.
        """
        for name, comment in LIVE_LANDED_FROM.items():
            with self.subTest(shape=name):
                self.assertTrue(
                    rcc._PROVENANCE_VERB_RE.match(comment),
                    f"{name}: must match the HEAD-ANCHORED predicate")
                _, diag = self.index(comment + "\n")
                self.assertEqual(
                    diag["head_anchor_relaxation"]["comments_admitted"], 0,
                    f"{name}: must NOT be admitted via the head-anchor relaxation")

    def test_whole_live_population_zeroes_the_vocabulary_gap_class(self):
        """All five together: vocabulary_gap 5 -> 0, other classes untouched."""
        body = "\n".join(LIVE_LANDED_FROM.values()) + "\n"
        inscribed, diag = self.index(body)
        for tok in LIVE_TOKENS.values():
            self.assertIn(tok, inscribed)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)
        # Declared zeros stay DECLARED keys, never missing keys (M1-736-HAR).
        self.assertEqual(
            diag["unmatched_remedy_class_counts"],
            {"wrong_object_class": 0, "head_anchor_gap": 0, "vocabulary_gap": 0})
        self.assertEqual(diag["unit_declaration"]["matched_comment_count"], 5)

    def test_case_insensitive(self):
        inscribed, _ = self.index("<!-- LANDED-FROM cpr_upper_tic1 -->\n")
        self.assertIn("cpr_upper_tic1", inscribed)

    def test_reachable_subject_prefixed_too(self):
        """Parity with every other admitted verb: reachable one word in."""
        self.assertTrue(
            rcc._is_head_anchor_relaxed_witness(
                "<!-- subject landed-from cpr_x_tic1 -->"))


# ---------------------------------------------------------------------------
# 2. The registration does NOT WIDEN — the three standing guards hold
# ---------------------------------------------------------------------------

class TestRegistrationIsNotABackDoor(HermeticIndexCase):
    """No live `landed-from` carries a skip / wrong-object / status head, so the
    live run can never exercise these. Adversarial fixtures or nothing."""

    def _assert_excluded(self, comment):
        inscribed, diag = self.index(comment + "\n")
        self.assertEqual(
            inscribed, set(),
            f"registration leaked a guarded object into the index: {comment[:80]}")
        return diag

    def test_skip_head_with_landed_from_still_excluded(self):
        diag = self._assert_excluded(
            "<!-- SKIP-with-home: landed-from cpr_skip_backdoor_tic999 -->")
        self.assertEqual(
            diag["unmatched_provenance_shaped_count"], 0,
            "a skip pointer is neither indexed NOR counted as residue")
        self.assertEqual(
            diag["head_anchor_relaxation"]["declined_by_exclusion"]["excluded_skip_head"],
            1, "the skip refusal must be COUNTED, so the guard is not an assurance")

    def test_wrong_object_head_with_landed_from_still_excluded(self):
        diag = self._assert_excluded(
            "<!-- home-pointer landed-from cpr_pointer_backdoor_tic999 -->")
        self.assertEqual(
            diag["head_anchor_relaxation"]["declined_by_exclusion"][
                "excluded_wrong_object_head"], 1)
        self.assertEqual(
            diag["unmatched_remedy_class_counts"],
            {"wrong_object_class": 1, "head_anchor_gap": 0, "vocabulary_gap": 0})

    def test_born_block_with_landed_from_still_excluded(self):
        self._assert_excluded(
            "<!-- --agnostic-candidate landed-from cpr_born_backdoor_tic999 -->")

    def test_inline_status_marker_with_landed_from_still_excluded(self):
        diag = self._assert_excluded(
            "<!-- status: landed-from | promoted_to: ledger.md#anchor "
            "cpr_status_backdoor_tic999 -->")
        self.assertEqual(
            diag["head_anchor_relaxation"]["declined_by_exclusion"][
                "excluded_inline_status_marker"], 1)

    def test_a_still_unregistered_head_remains_a_vocabulary_gap(self):
        """The /review-719 contract survives: a NEW head enters the matcher OR
        the residue report — never neither. Registration cured one instance of
        the class, not the class."""
        inscribed, diag = self.index(
            "<!-- routed-from cpr_still_unregistered_tic999 -->\n")
        self.assertEqual(inscribed, set())
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)
        self.assertEqual(
            diag["unmatched_remedy_class_counts"],
            {"wrong_object_class": 0, "head_anchor_gap": 0, "vocabulary_gap": 1})

    def test_documentary_prose_within_the_head_window_admits_AT_PARITY(self):
        """HONEST PROPERTY, corrected at build tic 738 after this fixture caught
        the author's wishful first assertion.

        A documentary/illustrative mention of an admitted verb INSIDE the 1..3
        subject-word head window IS admitted — that is the /review-736
        relaxation's ratified bound, and the /review-724 RIDER-1 disclosure
        already names it as non-discriminable route (h)
        `illustrative_or_documentary_occurrence`. Registration grants
        `landed-from` PARITY with its siblings, including this route; it does
        NOT grant it immunity no other verb has.

        MEASURED, so the parity claim is evidence and not assertion: with
        `landed-from` de-registered the same shape is refused, while
        promoted / absorbed / refined are admitted either way. Live impact of
        this route for `landed-from` at build tic 738 is ZERO — the corpus
        census found 5 landed-from comments, all HEAD-ANCHORED, none
        subject-prefixed.
        """
        shape = "<!-- TODO: this was %s cpr_prose_only_tic999 once -->"
        for verb in ("landed-from", "promoted", "absorbed", "refined"):
            with self.subTest(verb=verb):
                self.assertTrue(
                    rcc._is_head_anchor_relaxed_witness(shape % verb),
                    f"{verb}: head-window documentary mention must admit at parity")
        inscribed, _ = self.index((shape % "landed-from") + "\n")
        self.assertIn("cpr_prose_only_tic999", inscribed)

    def test_documentary_prose_OUTSIDE_the_head_window_is_still_refused(self):
        """The other arm: past the 3-word bound, the verb never reaches the head
        — identically for `landed-from` and for every sibling verb."""
        shape = "<!-- TODO: note that this one was %s cpr_far_prose_tic999 once -->"
        for verb in ("landed-from", "promoted", "absorbed", "refined"):
            with self.subTest(verb=verb):
                self.assertFalse(
                    rcc._is_head_anchor_relaxed_witness(shape % verb),
                    f"{verb}: verb past the bound must NOT reach the head")
        inscribed, diag = self.index((shape % "landed-from") + "\n")
        self.assertEqual(inscribed, set())
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)


# ---------------------------------------------------------------------------
# 3. Token admission is BYTE-IDENTICAL — only comment RECOGNITION widened
# ---------------------------------------------------------------------------

class TestTokenAdmissionUnchanged(HermeticIndexCase):

    def test_cpr_ref_regex_is_untouched(self):
        self.assertEqual(rcc._CPR_REF_RE.pattern, r"(cpr_[A-Za-z0-9_]+|CogPR-\d+)")

    def test_reserved_prefix_exclusion_applies_inside_a_landed_from_comment(self):
        inscribed, diag = self.index(
            "<!-- landed-from cpr_real_tic700. era: cpr_era_tic_700_749 -->\n")
        self.assertIn("cpr_real_tic700", inscribed)
        self.assertNotIn("cpr_era_tic_700_749", inscribed)
        self.assertIn("cpr_era_tic_700_749", diag["reserved_tokens_excluded"])

    def test_route_census_identical_across_landed_from_and_promoted(self):
        """The RIDER-1 disclosure must not go dark on the newly-admitted head."""
        landed = ("<!-- landed-from cpr_head_tic1. "
                  "Source: DONE_cpr_stepper_advance_tic718.json -->\n")
        promoted = ("<!-- promoted from cpr_head_tic1. "
                    "Source: DONE_cpr_stepper_advance_tic718.json -->\n")
        _, diag_l = self.index(landed)
        _, diag_p = self.index(promoted)
        self.assertEqual(
            diag_l["unit_declaration"]["route_occurrence_counts"],
            diag_p["unit_declaration"]["route_occurrence_counts"],
            "route census must be identical across head vocabularies")

    def test_queue_unresolved_disclosure_applies(self):
        inscribed, diag = self.index(
            "<!-- landed-from cpr_not_in_queue_tic1 -->\n",
            queue_ids={"cpr_something_else_tic2"})
        self.assertIn("cpr_not_in_queue_tic1", inscribed)
        self.assertEqual(diag["unresolved_against_queue_count"], 1)


# ---------------------------------------------------------------------------
# 4. NEGATIVE CONTROL — de-register the verb, the exact predicted breakage
#    returns; restore, and the cure returns. Both directions, hermetic.
# ---------------------------------------------------------------------------

class TestNegativeControl(HermeticIndexCase):

    def test_deregistering_the_verb_restores_the_vocabulary_gap_exactly(self):
        """Fixture-scale mirror of the build's on-disk negative control.

        Removes `landed-from` from all three matchers, re-fires the whole live
        population, and asserts the pre-registration shape returns EXACTLY:
        5 residue comments, all typed vocabulary_gap, index empty. Then restores
        and asserts the cure returns. A cure that cannot be un-done on demand
        was never isolated.
        """
        body = "\n".join(LIVE_LANDED_FROM.values()) + "\n"

        # cured state
        inscribed, diag = self.index(body)
        self.assertEqual(len(inscribed), 5)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)

        originals = {}
        try:
            for name in ("_PROVENANCE_VERB_RE", "_MIDCOMMENT_VERB_RE",
                         "_HEAD_SUBJECT_PREFIX_VERB_RE"):
                rx = getattr(rcc, name)
                originals[name] = rx
                setattr(rcc, name, re.compile(
                    rx.pattern.replace("landed-from|", "").replace("|landed-from", ""),
                    rx.flags))
            reverted, diag_rev = self.index(body)
            self.assertEqual(
                reverted, set(),
                "de-registered: no landed-from token may reach the index")
            self.assertEqual(diag_rev["unmatched_provenance_shaped_count"], 5)
            self.assertEqual(
                diag_rev["unmatched_remedy_class_counts"],
                {"wrong_object_class": 0, "head_anchor_gap": 0,
                 "vocabulary_gap": 5},
                "de-registered: the population must retype to vocabulary_gap")
        finally:
            for name, rx in originals.items():
                setattr(rcc, name, rx)

        # restored state — byte-identical to the cured state above
        restored, diag_res = self.index(body)
        self.assertEqual(restored, inscribed)
        self.assertEqual(diag_res["unmatched_provenance_shaped_count"], 0)
        self.assertEqual(
            diag_res["unmatched_remedy_class_counts"],
            {"wrong_object_class": 0, "head_anchor_gap": 0, "vocabulary_gap": 0})


if __name__ == "__main__":
    unittest.main(verbosity=2)
