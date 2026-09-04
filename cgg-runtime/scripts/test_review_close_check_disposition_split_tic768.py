#!/usr/bin/env python3
"""Fixtures for the /review-768 DISPOSITION SPLIT (bk-close-check-counter-disposition-split).

Ruling: the /review-726 refinement ray
cgg-ledger#loud-counter-mirror-overadmission-split-by-disposition
(cpr_mogul_review_close_check_8698d4d1b9bc, Architect-ratified in-tic, 4/4 as
recommended), executed at /review 768 under admission
audit-logs/governance/backlog-gunslinger-hoist/B2-wave-6-tic768.json
(self-sha fde2800d7566382a, "SIGN both" round 1).

THE RULED CURE, three teeth — each pinned below:
  1. DESIGN-EXCLUDE the two non-witness head classes the ruling names
     (born-CANDIDATE declaration blocks, ledger-tags metadata blocks) from the
     loud counter.
  2. PUBLISH the population SPLIT BY DISPOSITION (index_loss vs
     design_excludable vs unclassified).
  3. The REMEDIATION STRING must name EVERY disposition its population
     contains.

Every documented conditional gets BOTH arms
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths).

SCOPE HONESTY, stated up front: these are FIXTURE-GREEN proofs over synthetic
governance surfaces. The split's LIVE fire is the next review_close_check
mandate cycle; nothing here is live-green. The live read taken at build tic 768
(read-only, no artifact written) is recorded in
test_live_population_shape_at_build_tic768 as a documentation fixture that
asserts only the structure it can own.
"""

import importlib.util
import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "review_close_check", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check"] = rcc
_spec.loader.exec_module(rcc)


# --- Verbatim head shapes. The two RULED design-exclusion classes are quoted
# from the live corpus at build tic 768 so an authoring-style change breaks a
# test rather than silently re-opening the counter.
BORN_BLOCK = (
    "<!-- --agnostic-candidate\n"
    "id: cpr_pipeline_audio_drift_tic149\n"
    "band: COGNITIVE\n"
    "status: pending\n"
    "birth_tic: 149\n"
    "-->")
LEDGER_TAGS_BLOCK = (
    "<!-- ledger-tags: authority_class=measurement_integrity | rung=domain | "
    "domain=context-grapple-gun | born_tic=723 | promoted_tic=726 | "
    "relations=refines:emitter-rows-must-match-a-reader-predicate,"
    "sibling:cpr_mogul_review_close_check_8698d4d1b9bc | "
    "confidence_tier=tentative -->")
HOME_POINTER = (
    "<!-- home-pointer from "
    "cpr_changelog_fix_entry_impact_is_a_config_shape_probe_not_a_read_tic501 "
    "at /review 635 (SKIP-with-home; loading home, not a new body) -->")
VOCABULARY_GAP_HEAD = (
    "<!-- routed-from cpr_still_unregistered_tic999 (/review 999). -->")
# The ONE live producer of head_anchor_gap residue post-M1-736-HAR: an
# inline status marker carrying an admitted verb inside the head window. The
# relaxation declines it by exclusion, so it reaches the remedy classifier
# with a head-window verb present.
HEAD_ANCHOR_GAP_HEAD = (
    "<!-- status: promoted from cpr_status_marker_head_tic999 -->")


class HermeticIndexCase(unittest.TestCase):
    """build_inscribed_index also sweeps ~/.claude/CLAUDE.md and the auto-memory
    dir; point HOME into a sandbox so real surfaces never leak into fixture
    counts (cgg-ledger#self-locating-artifact-test-isolation)."""

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

    def index(self, body, queue_ids=None, capture_stderr=False):
        """Write ONE governance surface carrying `body`; return (inscribed, diag).

        With capture_stderr=True returns (inscribed, diag, stderr_text).
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(body, encoding="utf-8")
        diag = {}
        buf = io.StringIO()
        with redirect_stderr(buf):
            inscribed = rcc.build_inscribed_index(
                str(root), queue_ids=queue_ids, diagnostics=diag)
        if capture_stderr:
            return inscribed, diag, buf.getvalue()
        return inscribed, diag


# ---------------------------------------------------------------------------
# 1. TOOTH ONE — the two RULED classes are design-excluded from the counter
# ---------------------------------------------------------------------------

class TestDesignExclusion(HermeticIndexCase):

    def test_born_candidate_block_leaves_the_headline_counter(self):
        """15 of the 18 t723 non-witnesses. A candidate is not an inscription."""
        inscribed, diag = self.index(BORN_BLOCK + "\n")
        self.assertEqual(inscribed, set(), "a born block must never reach the index")
        self.assertEqual(
            diag["unmatched_provenance_shaped_count"], 0,
            "born-CANDIDATE block must be DESIGN-EXCLUDED from the loud counter")
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["counts"]["design_excludable"], 1)
        self.assertEqual(split["token_bearing_residue_total"], 1)
        self.assertEqual(
            split["design_excluded_by_class"]["born_candidate_declaration_block"], 1)

    def test_ledger_tags_block_leaves_the_headline_counter(self):
        """3 of the 18 t723 non-witnesses. A metadata mirror is not a witness."""
        inscribed, diag = self.index(LEDGER_TAGS_BLOCK + "\n")
        self.assertEqual(inscribed, set())
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["counts"]["design_excludable"], 1)
        self.assertEqual(
            split["design_excluded_by_class"]["ledger_tags_metadata_block"], 1)

    def test_design_excluded_members_are_MEASURED_not_dark(self):
        """The exclusion is auditable: excluded members keep a published home.

        This is what separates this exclusion from the SKIP-head exclusion,
        which drops its population entirely — 'no signal goes dark'.
        """
        _, diag = self.index(BORN_BLOCK + "\n" + LEDGER_TAGS_BLOCK + "\n")
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["counts"]["design_excludable"], 2)
        samples = split["samples_by_disposition"]["design_excludable"]
        self.assertEqual(len(samples), 2)
        classes = sorted(s["design_exclusion_class"] for s in samples)
        self.assertEqual(
            classes,
            ["born_candidate_declaration_block", "ledger_tags_metadata_block"])
        for s in samples:
            self.assertEqual(s["disposition"], "design_excludable")
            self.assertTrue(s["tokens"], "an excluded sample still carries its tokens")

    def test_design_excluded_members_are_NOT_in_the_headline_sample_list(self):
        """unmatched_provenance_shaped_samples is scoped to the counter's own
        population — a reader paging the headline sample must not meet objects
        the headline does not count."""
        _, diag = self.index(
            BORN_BLOCK + "\n" + LEDGER_TAGS_BLOCK + "\n" + VOCABULARY_GAP_HEAD + "\n")
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)
        heads = [s["head"] for s in diag["unmatched_provenance_shaped_samples"]]
        self.assertEqual(len(heads), 1)
        self.assertTrue(heads[0].startswith("<!-- routed-from"))

    def test_exclusion_set_is_EXACTLY_the_three_ruled_classes(self):
        """No UNRULED class was added at build altitude — the third class
        (home_pointer_block) was widened by the /review-769 ruling itself
        (F-768-A1, LATER-GOVERNS), never by a build increment."""
        self.assertEqual(
            sorted(rcc._DESIGN_EXCLUDED_HEAD_CLASSES),
            ["born_candidate_declaration_block", "home_pointer_block",
             "ledger_tags_metadata_block"])

    def test_exclusion_patterns_are_a_SUBSET_of_the_wrong_object_guard(self):
        """PARITY INVARIANT — the sharpest boundary claim of this increment.

        A head this counter design-excludes MUST also be one the head-anchor
        relaxation refuses. Otherwise a comment could be dropped from the
        residue report AND admitted to the index — the exclusion would become
        the back door /review 719 refused to open. Both arms: realistic heads
        (verb far from the head) and ADVERSARIAL heads (verb inside the 1..3
        word bound, which is the only shape that can reach the relaxation).
        """
        adversarial = [
            "<!-- --agnostic-candidate promoted from cpr_born_adversarial_tic999 -->",
            "<!-- ledger-tags: promoted from cpr_tags_adversarial_tic999 -->",
        ]
        for seg in [BORN_BLOCK, LEDGER_TAGS_BLOCK] + adversarial:
            with self.subTest(head=seg[:48]):
                fired = [n for n, p in rcc._DESIGN_EXCLUDED_HEAD_CLASSES.items()
                         if p.match(seg)]
                self.assertEqual(len(fired), 1, "exactly one exclusion class fires")
                self.assertTrue(
                    rcc._WRONG_OBJECT_HEAD_RE.match(seg),
                    "design-excluded head must also be refused by the relaxation")
                inscribed, diag = self.index(seg + "\n")
                self.assertEqual(
                    inscribed, set(),
                    "design-excluded head leaked into the INDEX")
                self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)


# ---------------------------------------------------------------------------
# 2. TOOTH ONE, other arm — what design-exclusion must NOT swallow
# ---------------------------------------------------------------------------

class TestExclusionDoesNotOverreach(HermeticIndexCase):

    def test_vocabulary_gap_head_stays_LOUD_as_index_loss(self):
        """The /review-719 contract survives: a real lost witness still fires."""
        inscribed, diag = self.index(VOCABULARY_GAP_HEAD + "\n")
        self.assertEqual(inscribed, set())
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["counts"]["index_loss"], 1)
        self.assertEqual(split["counts"]["design_excludable"], 0)
        self.assertEqual(
            split["samples_by_disposition"]["index_loss"][0]["remedy_class"],
            "vocabulary_gap")

    def test_head_anchor_gap_head_stays_LOUD_as_index_loss(self):
        """The other index_loss producer, reachable post-M1-736-HAR only via an
        inline status marker carrying a head-window verb."""
        inscribed, diag = self.index(HEAD_ANCHOR_GAP_HEAD + "\n")
        self.assertEqual(inscribed, set())
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["counts"]["index_loss"], 1)
        self.assertEqual(
            split["samples_by_disposition"]["index_loss"][0]["remedy_class"],
            "head_anchor_gap")

    def test_home_pointer_is_DESIGN_EXCLUDED_by_the_review_769_ruling(self):
        """The cross-ruling question — RULED at /review 769 (F-768-A1).

        /review 723 counted `home-pointer from` x1 among the REAL index-loss
        witnesses; /review 736 typed a home-pointer "not a failed inscription
        witness at all". The fence settled it LATER-GOVERNS: the /review-736
        typing rules the member (the /review-723 typing on it is superseded-
        with-lineage), so a home-pointer head is design-excluded under its own
        named class — widened by the fence itself, never by a build increment.
        """
        inscribed, diag = self.index(HOME_POINTER + "\n")
        self.assertEqual(inscribed, set())
        self.assertEqual(
            diag["unmatched_provenance_shaped_count"], 0,
            "home-pointer leaves the LOUD counter under the /review-769 ruling")
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["counts"]["unclassified"], 0)
        self.assertEqual(split["counts"]["design_excludable"], 1)
        sample = split["samples_by_disposition"]["design_excludable"][0]
        self.assertEqual(sample["design_exclusion_class"], "home_pointer_block")

    def test_unknown_remedy_class_falls_to_unclassified_never_to_silence(self):
        """ANTI-ROT, at the predicate. A class the mapping does not know is
        LOUD, never absorbed."""
        self.assertEqual(
            rcc._classify_unmatched_disposition(
                "<!-- some-future-head from cpr_x_tic1 -->", "a_class_from_2027"),
            ("unclassified", None))

    def test_skip_head_exclusion_is_UNWEAKENED(self):
        """The upstream /review-719 exclusion is untouched: neither indexed, nor
        counted, nor present in any disposition bucket."""
        inscribed, diag = self.index(
            "<!-- SKIP at /review 700: cpr_skipped_lesson_tic690 not net-new -->\n")
        self.assertEqual(inscribed, set())
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["token_bearing_residue_total"], 0)

    def test_admitted_witness_is_in_no_bucket_at_all(self):
        """A comment the matcher ADMITS is not residue under any disposition."""
        inscribed, diag = self.index(
            "<!-- promoted from cpr_plain_head_anchored_tic100 -->\n")
        self.assertIn("cpr_plain_head_anchored_tic100", inscribed)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)
        self.assertEqual(
            diag["unmatched_disposition_split"]["token_bearing_residue_total"], 0)


# ---------------------------------------------------------------------------
# 3. TOOTH TWO — the population is PUBLISHED split by disposition
# ---------------------------------------------------------------------------

class TestPopulationSplitPublished(HermeticIndexCase):

    def mixed(self):
        body = "\n".join([
            BORN_BLOCK, BORN_BLOCK.replace("tic149", "tic150"),
            LEDGER_TAGS_BLOCK, VOCABULARY_GAP_HEAD, HOME_POINTER]) + "\n"
        return self.index(body)

    def test_counts_sum_to_the_residue_total_and_gate_the_headline(self):
        _, diag = self.mixed()
        split = diag["unmatched_disposition_split"]
        self.assertEqual(
            split["counts"],
            {"design_excludable": 4, "index_loss": 1, "unclassified": 0})
        self.assertEqual(split["token_bearing_residue_total"], 5)
        self.assertEqual(
            sum(split["counts"].values()), split["token_bearing_residue_total"])
        self.assertEqual(
            split["headline_counter_value"],
            split["counts"]["index_loss"] + split["counts"]["unclassified"])
        self.assertEqual(
            diag["unmatched_provenance_shaped_count"],
            split["headline_counter_value"])

    def test_all_three_dispositions_are_DECLARED_keys_even_at_zero(self):
        """A zero must mean 'the classifier ran and found none', never a missing
        key a consumer has to distinguish from 'not evaluated' (M1-736-HAR
        discipline, carried onto the new axis)."""
        _, diag = self.index("<!-- an ordinary prose comment, no ids -->\n")
        split = diag["unmatched_disposition_split"]
        self.assertEqual(
            split["counts"],
            {"design_excludable": 0, "index_loss": 0, "unclassified": 0})
        self.assertEqual(
            sorted(split["samples_by_disposition"]),
            ["design_excludable", "index_loss", "unclassified"])
        self.assertEqual(
            sorted(split["design_excluded_by_class"]),
            ["born_candidate_declaration_block", "home_pointer_block",
             "ledger_tags_metadata_block"])

    def test_samples_are_STRATIFIED_not_head_of_list(self):
        """The ray's second tooth: a capped UNSTRATIFIED sample hid the t723
        population's structure (read as 'mostly a vocabulary problem' while it
        was 64% category error). Twelve born blocks ahead of one real witness
        must not starve the witness out of the published samples.
        """
        body = "\n".join(
            [BORN_BLOCK.replace("tic149", f"tic{200 + i}") for i in range(12)]
            + [VOCABULARY_GAP_HEAD]) + "\n"
        _, diag = self.index(body)
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["counts"]["design_excludable"], 12)
        self.assertEqual(split["counts"]["index_loss"], 1)
        self.assertEqual(
            len(split["samples_by_disposition"]["design_excludable"]), 5,
            "per-disposition cap holds")
        self.assertEqual(
            len(split["samples_by_disposition"]["index_loss"]), 1,
            "the lone real witness survives 12 excluded objects ahead of it")

    def test_every_sample_carries_its_disposition(self):
        _, diag = self.mixed()
        split = diag["unmatched_disposition_split"]
        for disposition, samples in split["samples_by_disposition"].items():
            for s in samples:
                self.assertEqual(s["disposition"], disposition)
                self.assertIn("remedy_class", s)

    def test_headline_publishes_its_CHANGED_population_beside_the_integer(self):
        """The ray's own cost_of_action: the counter's value changed, so a
        consumer predicting against the bare integer must re-baseline. That
        must be readable at the mint site, not inferred."""
        _, diag = self.mixed()
        pop = diag["unmatched_provenance_shaped_population"]
        self.assertIn("index_loss", pop)
        self.assertIn("unclassified", pop)
        self.assertIn("design_excludable", pop)
        self.assertIn("PRE-768 READERS", pop)

    def test_disposition_texts_name_the_route_for_each_disposition(self):
        _, diag = self.mixed()
        texts = diag["unmatched_disposition_split"]["dispositions"]
        self.assertEqual(
            sorted(texts), ["design_excludable", "index_loss", "unclassified"])
        self.assertIn("verb registration", texts["index_loss"])
        self.assertIn("head-anchor", texts["index_loss"])
        self.assertIn("no matcher change", texts["design_excludable"])
        self.assertIn("/review", texts["unclassified"])

    def test_axis_relation_and_rot_disclosures_are_published(self):
        """Both of the ray's teeth are disclosed as DATA, not left to prose."""
        _, diag = self.mixed()
        split = diag["unmatched_disposition_split"]
        self.assertIn("ORTHOGONAL", split["axis_relation"])
        self.assertIn("CLOSED negative list", split["exclusion_set_rot_disclosure"])
        self.assertIn("unclassified", split["exclusion_set_rot_disclosure"])
        self.assertIn("home-pointer", split["unclassified_open_question"])
        self.assertIn("B2-wave-6-tic768", split["design_exclusion_authority"])


# ---------------------------------------------------------------------------
# 4. TOOTH THREE — the remediation string names EVERY disposition
# ---------------------------------------------------------------------------

class TestRemediationStringNamesEveryDisposition(HermeticIndexCase):

    def test_every_disposition_and_all_exclusion_classes_are_named(self):
        body = "\n".join(
            [BORN_BLOCK, LEDGER_TAGS_BLOCK, VOCABULARY_GAP_HEAD, HOME_POINTER]) + "\n"
        _, _, err = self.index(body, capture_stderr=True)
        for token in ("index_loss", "design_excludable", "unclassified",
                      "born_candidate_declaration_block",
                      "ledger_tags_metadata_block",
                      "home_pointer_block",
                      "POPULATION SPLIT BY DISPOSITION",
                      "verb registration", "head-anchor",
                      "no matcher change can ever be the fix",
                      "orthogonal"):
            with self.subTest(names=token):
                self.assertIn(token, err)

    def test_string_carries_the_headline_AND_the_total(self):
        body = "\n".join(
            [BORN_BLOCK, LEDGER_TAGS_BLOCK, VOCABULARY_GAP_HEAD, HOME_POINTER]) + "\n"
        _, diag, err = self.index(body, capture_stderr=True)
        self.assertIn("UNMATCHED-PROVENANCE-SHAPE: 1 of 4", err)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)
        self.assertIn("design_excludable=3, index_loss=1, unclassified=0", err)

    def test_a_fully_design_excluded_population_still_DISCLOSES(self):
        """Both arms of the print gate. If the line fired only on a non-zero
        headline, an all-excluded population would go dark on stderr and the
        exclusion would stop being auditable."""
        _, diag, err = self.index(BORN_BLOCK + "\n", capture_stderr=True)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)
        self.assertIn("UNMATCHED-PROVENANCE-SHAPE: 0 of 1", err)
        self.assertIn("design_excludable=1", err)

    def test_an_empty_residue_population_prints_NOTHING(self):
        """The other arm: no residue, no line — the counter stays quiet when
        there is nothing to route."""
        _, diag, err = self.index(
            "<!-- promoted from cpr_clean_head_tic100 -->\n", capture_stderr=True)
        self.assertEqual(
            diag["unmatched_disposition_split"]["token_bearing_residue_total"], 0)
        self.assertNotIn("UNMATCHED-PROVENANCE-SHAPE", err)


# ---------------------------------------------------------------------------
# 5. NON-REGRESSION — the axes this patch must NOT move
# ---------------------------------------------------------------------------

class TestOrthogonalAxesUnmoved(HermeticIndexCase):

    def test_remedy_class_counts_still_span_the_FULL_residue(self):
        """The /review-736 typing is computed over the full residue INCLUDING
        design-excluded members, so its published counts stay comparable across
        the patch boundary (and the t736/t738 fixtures stay green)."""
        body = "\n".join(
            [BORN_BLOCK, LEDGER_TAGS_BLOCK, HOME_POINTER, VOCABULARY_GAP_HEAD]) + "\n"
        _, diag = self.index(body)
        self.assertEqual(
            diag["unmatched_remedy_class_counts"],
            {"wrong_object_class": 3, "head_anchor_gap": 0, "vocabulary_gap": 1})
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)

    def test_index_admission_is_byte_for_byte_unchanged(self):
        """This increment touches WHICH RESIDUE IS COUNTED, never WHICH TOKENS
        ARE ADMITTED. Both admission paths still admit exactly as before."""
        body = ("<!-- promoted from cpr_head_anchored_tic100 -->\n"
                "<!-- tic-733 refinement appendix promoted from cpr_relaxed_tic101 -->\n"
                + BORN_BLOCK + "\n" + LEDGER_TAGS_BLOCK + "\n")
        inscribed, diag = self.index(body)
        self.assertEqual(
            inscribed, {"cpr_head_anchored_tic100", "cpr_relaxed_tic101"})
        self.assertEqual(diag["unit_declaration"]["matched_comment_count"], 2)
        self.assertEqual(diag["head_anchor_relaxation"]["comments_admitted"], 1)

    def test_PRIOR_SET_CONDITION_docstring_block_is_INTACT(self):
        """BINDING CONSTRAINT of this increment (amended procedural clause
        /review 734, n=2): token_delta's unit is DISTINCT-MEMBERS-OF-A-SET and
        the PRIOR-SET CONDITION block is LAW. The patch may not regress it or
        its docstring. Pinned by content, so a future edit that dissolves the
        discipline breaks a test rather than a close-fire prediction."""
        doc = rcc.compute_cross_counter_disclosure.__doc__
        for clause in (
            "PRIOR-SET CONDITION (amended /review 734 from",
            "cpr_mogul_review_close_check_f6483a805358",
            "token_delta's unit is DISTINCT-MEMBERS-OF-A-SET",
            "planned content tokens INTERSECT complement of the",
            "PRIOR index set",
            "contributes +0 no matter how",
            "The failure this cures is MODAL",
            "index-set diff verified 368 -> 369",
        ):
            with self.subTest(clause=clause[:40]):
                self.assertIn(clause, doc)

    def test_the_DOES_NOT_SATISFY_rider_travels_with_the_patch(self):
        """The t724 filename over-admission route is NOT cured by this
        increment. The pre-768 docstring promised it would be ("until the
        disposition-split patch lands"), so the landed patch must carry the
        rider that says otherwise, verbatim and in place."""
        doc = rcc.compute_cross_counter_disclosure.__doc__
        self.assertIn("DOES-NOT-SATISFY RIDER", doc)
        self.assertIn("does NOT cure this", doc)
        self.assertIn("Index ADMISSION is byte-for-byte unchanged", doc)
        self.assertIn("this route remains OPEN", doc)
        # The PROMISSORY form is gone…
        self.assertNotIn(
            "inflates delta_tokens until the disposition-split patch lands", doc)
        # …and the phrase survives ONLY inside the rider that corrects it.
        # (This assertion pair replaced a bare assertNotIn that the rider's own
        # verbatim quotation falsified at first run — F-768-B1, self-caught.)
        self.assertIn(
            '"until the disposition-split patch lands" was a mis-routed forward',
            doc)
        self.assertEqual(
            doc.count("until the disposition-split patch lands"), 1)


# ---------------------------------------------------------------------------
# 6. NEGATIVE CONTROL — the cure can be un-done on demand
# ---------------------------------------------------------------------------

class TestNegativeControl(HermeticIndexCase):

    def test_emptying_the_exclusion_set_restores_the_UNSPLIT_counter_exactly(self):
        """Fixture-scale mirror of the build's on-disk negative control.

        Empties the ruled design-exclusion set, re-fires the same population,
        and asserts the pre-768 shape returns EXACTLY: every token-bearing
        residue comment back in the headline, design_excludable at 0, the 64%
        category error back under a single integer. Then restores and asserts
        the cure returns. A cure that cannot be un-done on demand was never
        isolated.
        """
        body = "\n".join(
            [BORN_BLOCK, LEDGER_TAGS_BLOCK, HOME_POINTER, VOCABULARY_GAP_HEAD]) + "\n"

        # cured state (post-/review-769: home-pointer design-excluded)
        _, diag = self.index(body)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)
        self.assertEqual(
            diag["unmatched_disposition_split"]["counts"],
            {"design_excludable": 3, "index_loss": 1, "unclassified": 0})

        original = rcc._DESIGN_EXCLUDED_HEAD_CLASSES
        try:
            rcc._DESIGN_EXCLUDED_HEAD_CLASSES = {}
            _, diag_rev = self.index(body)
            self.assertEqual(
                diag_rev["unmatched_provenance_shaped_count"], 4,
                "reverted: the counter must re-admit the design-excluded 64%")
            self.assertEqual(
                diag_rev["unmatched_disposition_split"]["counts"],
                {"design_excludable": 0, "index_loss": 1, "unclassified": 3},
                "reverted: the excluded classes retype as undisposed residue")
        finally:
            rcc._DESIGN_EXCLUDED_HEAD_CLASSES = original

        # restored state — identical to the cured state above
        _, diag_res = self.index(body)
        self.assertEqual(diag_res["unmatched_provenance_shaped_count"], 1)
        self.assertEqual(
            diag_res["unmatched_disposition_split"]["counts"],
            diag["unmatched_disposition_split"]["counts"])


# ---------------------------------------------------------------------------
# 7. The live population, as READ at build tic 768 — documentation fixture
# ---------------------------------------------------------------------------

class TestLivePopulationShapeAtBuild(unittest.TestCase):

    def test_live_population_shape_at_build_tic768(self):
        """FIXTURE-GREEN IS NOT LIVE-GREEN. This asserts only what it owns.

        Read-only measurement at build tic 768 (build_inscribed_index over the
        real scanned-surface set; NO artifact written, the live mandate cycle
        had already consumed and exited):
            residue total 20 · design_excludable 19 (born 15 + ledger-tags 4) ·
            unclassified 1 (the home-pointer in cgg-ledger/ledger.md) ·
            index_loss 0 · headline 20 -> 1 · index tokens 862 UNCHANGED.
        The t723 figure the ruling cites (18 of 28 = 64% non-witness) is
        HISTORY and was correct as taken; the live population has since moved
        (the /review-736 relaxation and the /review-737 landed-from
        registration cured the index_loss classes to 0). Both figures are
        named from their own instrument and are NOT comparable — the POPULATION
        clause.

        Nothing here asserts the live numbers: a test that pinned them would
        fail on the next inscription. It pins the SHAPES the split must satisfy
        for any population.
        """
        for name in ("_DISPOSITION_INDEX_LOSS", "_DISPOSITION_DESIGN_EXCLUDABLE",
                     "_DISPOSITION_UNCLASSIFIED"):
            self.assertTrue(hasattr(rcc, name))
        self.assertEqual(
            sorted(rcc._DISPOSITION_TEXT),
            ["design_excludable", "index_loss", "unclassified"])
        self.assertEqual(
            sorted(rcc._REMEDY_CLASS_DISPOSITION),
            ["head_anchor_gap", "vocabulary_gap", "wrong_object_class"])
        self.assertEqual(
            rcc._REMEDY_CLASS_DISPOSITION["wrong_object_class"], "unclassified",
            "a wrong-object head outside the two RULED classes stays LOUD")


if __name__ == "__main__":
    unittest.main(verbosity=2)
