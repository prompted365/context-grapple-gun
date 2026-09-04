#!/usr/bin/env python3
"""test_review_close_check_prior_same_tic_tic769.py — the SAME-TIC RE-OBSERVATION
face made executable (/review 747 round 1 Q4, cpr_mogul_review_close_check_9646fae378af,
PROMOTE-as-refinement-ray; built at /review 769 WAVE 7 ROW A, backlog row
bk-close-check-same-tic-reobservation-delta-decomposition, Architect-signed
B2-wave-7-SIGNED-tic769.json 2a01f061284849d4).

THE LIVED DEFECT the ruling re-derived EXACT from the artifacts: `review-close-check.py`
excludes its own canonical artifact from baseline selection, so on a tic that fires
twice the close artifact re-measures against the PRIOR TIC, not against the earlier
fire. Baseline tic-737 promoted 754 / index 786; the 738 ENTRY fire 757 (+3) / 789 (+3);
the 738 CLOSE fire 759 (+5) / 792 (+6). A reader reconciling the /review 738 docket row
count against `delta.promoted = 5` over-attributes by 3, and the two counters split
differently (+3/+3 on +6) so the decomposition is NOT derivable from one counter's
totals. `verdict_counts_delta.note` bucketed that residual as "any out-of-band queue
state change" — framing a KNOWN, typed, same-artifact-lineage prior observation as
unattributable drift.

THE CURE UNDER TEST, exactly as ruled and no wider: an ADDITIVE
`prior_same_tic_observation` field on BOTH delta blocks naming the same-tic artifact and
its delta, and the vc note amended off the blanket phrase onto the reason-coded
genuine-vs-known split. No counter semantics move; no baseline is re-selected.

ELEVEN arms. Nine DISCRIMINATE the cure (they fail when the additive field or the
amended note is reverted). Two are declared NON-DISCRIMINATING CONTROLS and say so in
their own names — `test_control_*` — because a control that passes in both states is
evidence about the cure's ADDITIVITY, and an arm that cannot fail must never be counted
as proof that the cure landed.

Arm 11 is a MEASUREMENT, not a cure claim: it measures this field's interaction with the
write block's skip-vs-replace content comparison (F-769-A1), including the arm where the
pre-existing `genuine_zero_streak` divergence does NOT cover it. The measurement is the
finding; the cure for it is OUT OF THIS ROW'S FENCE and handed up.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("rcc_t769", _HERE / "review-close-check.py")
rcc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rcc)

# The /review-747 re-derived numbers, used verbatim as the fixture so the suite pins the
# ruling's own instance rather than an invented one.
T737_PROMOTED, T737_TOKENS, T737_COMMENTS = 754, 786, 700
T738_ENTRY_PROMOTED, T738_ENTRY_TOKENS, T738_ENTRY_COMMENTS = 757, 789, 702
T738_CLOSE_PROMOTED, T738_CLOSE_TOKENS, T738_CLOSE_COMMENTS = 759, 792, 705


def _artifact(promoted, tokens, comments, generated_at="2026-08-21T00:00:00+00:00"):
    return {
        "generated_at": generated_at,
        "inscribed_index_size": tokens,
        "inscribed_index_unit": {"matched_comment_count": comments},
        "verdict_counts": {"promoted": promoted, "deferred": 10, "skipped": 4},
    }


def _write(report_dir: Path, name: str, payload: dict) -> Path:
    path = report_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class PriorSameTicObservationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.report_dir = Path(self._tmp.name)
        self.current = "tic-738-check.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _seed_prior_tic(self):
        _write(self.report_dir, "tic-737-check.json",
               _artifact(T737_PROMOTED, T737_TOKENS, T737_COMMENTS))

    def _seed_same_tic_entry_fire(self):
        _write(self.report_dir, self.current,
               _artifact(T738_ENTRY_PROMOTED, T738_ENTRY_TOKENS, T738_ENTRY_COMMENTS,
                         generated_at="2026-08-21T04:00:00+00:00"))

    def _vc(self):
        return rcc.compute_verdict_count_deltas(
            str(self.report_dir), self.current, 738,
            {"promoted": T738_CLOSE_PROMOTED, "deferred": 10, "skipped": 4})

    def _idx(self):
        return rcc.compute_unit_deltas(
            str(self.report_dir), self.current, 738,
            T738_CLOSE_TOKENS, T738_CLOSE_COMMENTS)

    # ---------------------------------------------------------------- arm 1
    def test_first_fire_of_a_tic_is_absent_with_a_reason_never_a_fabricated_zero(self):
        """A tic's FIRST fire has no earlier fire. Absent is disclosed with its reason;
        a zero delta would assert measured no-movement from no measurement."""
        self._seed_prior_tic()
        for name, block in (("verdict_counts_delta", self._vc()),
                            ("inscribed_index_delta", self._idx())):
            with self.subTest(block=name):
                st = block["prior_same_tic_observation"]
                self.assertFalse(st["present"])
                self.assertTrue(st["decomposition_absent"])
                self.assertEqual(st["reason_absent"], "no_same_tic_prior_observation")
                self.assertIsNone(st["artifact"])
                self.assertIsNone(st["selector"])
        self.assertIsNone(self._vc()["prior_same_tic_observation"]["prior_counts"])
        self.assertEqual(
            self._vc()["prior_same_tic_observation"]["delta_since_prior_same_tic"],
            {"promoted": None, "deferred": None, "skipped": None})
        idx_st = self._idx()["prior_same_tic_observation"]
        self.assertIsNone(idx_st["delta_tokens_since_prior_same_tic"])
        self.assertIsNone(idx_st["delta_matched_comments_since_prior_same_tic"])

    # ---------------------------------------------------------------- arm 2
    def test_second_fire_decomposes_the_verdict_delta_at_the_ruled_instance(self):
        """The /review-747 instance: delta.promoted stays 5 against its declared
        baseline (the ruling's APO — the delta is not wrong, the defect is
        attributional), and THIS fire's movement is now named as 2."""
        self._seed_prior_tic()
        self._seed_same_tic_entry_fire()
        block = self._vc()
        self.assertEqual(block["baseline"]["artifact"], "tic-737-check.json")
        self.assertEqual(block["baseline"]["selector"], "tic_keyed_prior_tic_737")
        self.assertEqual(block["delta"]["promoted"],
                         T738_CLOSE_PROMOTED - T737_PROMOTED)
        self.assertEqual(block["delta"]["promoted"], 5)
        st = block["prior_same_tic_observation"]
        self.assertTrue(st["present"])
        self.assertFalse(st["decomposition_absent"])
        self.assertIsNone(st["reason_absent"])
        self.assertEqual(st["artifact"], self.current)
        self.assertEqual(st["selector"], "same_tic_live_artifact_pre_overwrite")
        self.assertEqual(st["prior_generated_at"], "2026-08-21T04:00:00+00:00")
        self.assertEqual(st["prior_counts"]["promoted"], T738_ENTRY_PROMOTED)
        self.assertEqual(st["delta_since_prior_same_tic"]["promoted"], 2)
        # The decomposition closes: earlier fire's movement + this fire's movement.
        self.assertEqual(
            (st["prior_counts"]["promoted"] - block["baseline"]["counts"]["promoted"])
            + st["delta_since_prior_same_tic"]["promoted"],
            block["delta"]["promoted"])

    # ---------------------------------------------------------------- arm 3
    def test_second_fire_decomposes_the_index_delta_and_the_counters_split_differently(self):
        """+3/+3 on +6: the ruling's point that the decomposition is NOT derivable
        from one counter's totals."""
        self._seed_prior_tic()
        self._seed_same_tic_entry_fire()
        block = self._idx()
        self.assertEqual(block["delta_tokens"], T738_CLOSE_TOKENS - T737_TOKENS)
        self.assertEqual(block["delta_tokens"], 6)
        st = block["prior_same_tic_observation"]
        self.assertTrue(st["present"])
        self.assertFalse(st["decomposition_absent"])
        self.assertEqual(st["prior_tokens"], T738_ENTRY_TOKENS)
        self.assertEqual(st["delta_tokens_since_prior_same_tic"], 3)
        self.assertEqual(st["prior_matched_comments"], T738_ENTRY_COMMENTS)
        self.assertEqual(st["delta_matched_comments_since_prior_same_tic"],
                         T738_CLOSE_COMMENTS - T738_ENTRY_COMMENTS)
        # The verdict side moved 3 then 2; the index side moved 3 then 3. One
        # counter's totals cannot yield the other's split.
        self.assertNotEqual(
            self._vc()["prior_same_tic_observation"]["delta_since_prior_same_tic"]["promoted"],
            st["delta_tokens_since_prior_same_tic"])

    # ---------------------------------------------------------------- arm 4
    def test_same_tic_artifact_predating_the_fields_is_disclosed_not_differenced(self):
        self._seed_prior_tic()
        _write(self.report_dir, self.current, {"generated_at": "x", "findings": []})
        for name, block in (("verdict_counts_delta", self._vc()),
                            ("inscribed_index_delta", self._idx())):
            with self.subTest(block=name):
                st = block["prior_same_tic_observation"]
                self.assertTrue(st["present"])
                self.assertTrue(st["decomposition_absent"])
                self.assertEqual(st["reason_absent"],
                                 "same_tic_artifact_predates_these_fields")
        # OUTSIDE the subTest loop on purpose: a subtest-only failure leaves the PARENT
        # test reporting PASSED, so an arm whose every assertion sits inside subTest
        # reads green in the FAILED list while its subtests failed — the masked-verdict
        # shape (F-768-S2 family). Measured on this suite's own first NC run at tic 769.
        self.assertIn("prior_same_tic_observation", self._vc())
        self.assertIn("prior_same_tic_observation", self._idx())

    # ---------------------------------------------------------------- arm 5
    def test_unreadable_same_tic_artifact_is_disclosed_by_reason(self):
        self._seed_prior_tic()
        (self.report_dir / self.current).write_text("{not json", encoding="utf-8")
        for name, block in (("verdict_counts_delta", self._vc()),
                            ("inscribed_index_delta", self._idx())):
            with self.subTest(block=name):
                st = block["prior_same_tic_observation"]
                self.assertFalse(st["present"])
                self.assertEqual(st["reason_absent"], "same_tic_artifact_unreadable")
                self.assertEqual(st["artifact"], self.current)
        # OUTSIDE the subTest loop — same anti-masked-verdict reason as the arm above.
        self.assertIn("prior_same_tic_observation", self._vc())
        self.assertIn("prior_same_tic_observation", self._idx())

    # ---------------------------------------------------------------- arm 6
    def test_earlier_preserved_fires_are_named_and_the_back_stamp_sidecar_excluded(self):
        """Named from what is ON DISK now — never a predicted preserved_path for the
        live artifact, whose preservation has not happened at compute time."""
        self._seed_prior_tic()
        self._seed_same_tic_entry_fire()
        sup = self.report_dir / "superseded"
        _write(sup, "tic-738-check.superseded-1.json", _artifact(755, 787, 701))
        _write(sup, "tic-738-check.superseded-2.json", _artifact(756, 788, 701))
        _write(sup, "tic-738-check.superseded-1.json.superseded-by.json", {"x": 1})
        _write(sup, "tic-737-check.superseded-1.json", _artifact(1, 1, 1))
        st = self._vc()["prior_same_tic_observation"]
        self.assertEqual(st["earlier_preserved_same_tic_artifacts"],
                         ["tic-738-check.superseded-1.json",
                          "tic-738-check.superseded-2.json"])
        self.assertNotIn("preserved_path", st)

    # ---------------------------------------------------------------- arm 7
    def test_unmeasured_current_side_stays_honest_on_both_blocks(self):
        self._seed_prior_tic()
        self._seed_same_tic_entry_fire()
        vc = rcc.compute_verdict_count_deltas(
            str(self.report_dir), self.current, 738,
            {"promoted": None, "deferred": 10, "skipped": 4})
        st = vc["prior_same_tic_observation"]
        self.assertTrue(st["present"])
        self.assertTrue(st["decomposition_absent"])
        self.assertEqual(st["reason_absent"], "current_pass_counts_unmeasured")
        self.assertEqual(st["prior_counts"]["promoted"], T738_ENTRY_PROMOTED)
        idx = rcc.compute_unit_deltas(str(self.report_dir), self.current, 738,
                                      T738_CLOSE_TOKENS, None)
        st_i = idx["prior_same_tic_observation"]
        self.assertTrue(st_i["decomposition_absent"])
        self.assertEqual(st_i["reason_absent"], "current_pass_units_unmeasured")

    # ---------------------------------------------------------------- arm 8
    def test_vc_note_names_the_reason_coded_split_and_retires_the_blanket_phrase(self):
        """/review 747 round 1 Q4: the note must name the reason-coded genuine-vs-known
        split. The old blanket phrase survives ONLY as declared superseded lineage —
        never as the live characterization of the residual."""
        note = self._vc()["note"]
        for token in ("REASON-CODED", "reason-coded-genuine-vs-known-verifier-split",
                      "same_tic_prior_observation", "prior_same_tic_observation",
                      "delta_since_prior_same_tic", "GENUINE", "KNOWN reason"):
            with self.subTest(token=token):
                self.assertIn(token, note)
        blanket = "any out-of-band queue state change"
        self.assertIn(blanket, note)
        head = note.split("SUPERSEDED WORDING")[0]
        self.assertNotIn(blanket, head)
        self.assertIn("SUPERSEDED WORDING, kept for lineage", note)

    # ---------------------------------------------------------------- arm 9
    def test_no_equality_flag_escapes_the_constructor_through_the_new_field(self):
        """The constructor law (/review 757 FORWARD-DECAY face) still holds with the
        new booleans on the artifact: present / decomposition_absent are NOT
        equality-of-deltas flags and must not be minted as untyped ones."""
        self._seed_prior_tic()
        self._seed_same_tic_entry_fire()
        for name, block in (("verdict_counts_delta", self._vc()),
                            ("inscribed_index_delta", self._idx())):
            with self.subTest(block=name):
                audit = rcc.audit_equality_flags(block)
                self.assertEqual(audit["untyped"], [])
        st = self._vc()["prior_same_tic_observation"]
        for key in ("present", "decomposition_absent"):
            self.assertNotIn(key, rcc.EQUALITY_FLAG_NAMES)
            self.assertIsInstance(st[key], bool)

    # ------------------------------------------------- arm 10 (NON-DISCRIMINATING)
    def test_control_additive_only_baseline_and_published_deltas_never_move(self):
        """DECLARED NON-DISCRIMINATING: this arm passes with the cure reverted, by
        construction — it asserts what the cure must NOT change. It is evidence of
        ADDITIVITY, never evidence that the field landed."""
        self._seed_prior_tic()
        without_vc, without_idx = self._vc(), self._idx()
        self._seed_same_tic_entry_fire()
        with_vc, with_idx = self._vc(), self._idx()
        self.assertEqual(without_vc["delta"], with_vc["delta"])
        self.assertEqual(without_vc["baseline"], with_vc["baseline"])
        self.assertFalse(without_vc["delta_baseline_absent"])
        self.assertFalse(with_vc["delta_baseline_absent"])
        for key in ("delta_tokens", "delta_matched_comments", "baseline",
                    "units_collapsed_this_pass", "units_collapsed_vacuous",
                    "units_collapsed_evidential_weight", "delta_baseline_absent"):
            with self.subTest(key=key):
                self.assertEqual(without_idx[key], with_idx[key])

    # ------------------------------------------------- arm 11 (MEASUREMENT / F-769-A1)
    def test_measures_the_write_block_content_comparison_interaction(self):
        """MEASUREMENT (F-769-A1), not a cure claim. Its two streak sections are
        NON-DISCRIMINATING (they exercise pre-existing behaviour and pass with the cure
        reverted); its final section DISCRIMINATES because it reads the new field. It
        carries no `test_control_` prefix for exactly that reason — an arm that can fail
        when the cure is reverted is not a control, whatever else it also measures.

        The write block's skip-vs-replace predicate compares WHOLE REPORT CONTENT minus
        (`generated_at`, `superseded_receipt`). `prior_same_tic_observation` is by
        design different on a tic's second fire than on its first, so it is content
        that moves across a same-tic re-run.

        The script's own docstring (:_git_provenance_anchor, the tic-723 scope-honest
        residue) states the skip branch is "effectively unreachable for a same-tic
        re-run" because `genuine_zero_streak` already moves. This arm MEASURES that
        claim's scope: it holds when the streak is ACTIVE (genuine_count == 0) and does
        NOT hold when the streak is BROKEN (genuine_count > 0), where the streak block
        returns byte-identical across both fires. On that arm the new field is the first
        content to differ. The cure — if one is owed — is a `_volatile` decision in the
        write block, OUTSIDE this row's declared fence; handed up, not taken."""
        log = self.report_dir / "log.jsonl"

        # Streak ACTIVE: the pre-existing divergence covers the same-tic re-run.
        log.write_text(json.dumps({"tic": 738, "genuine_count": 0}) + "\n",
                       encoding="utf-8")
        first = rcc.compute_genuine_zero_streak(str(log), 738, 0)
        log.write_text("".join(json.dumps({"tic": 738, "genuine_count": 0}) + "\n"
                               for _ in range(2)), encoding="utf-8")
        second = rcc.compute_genuine_zero_streak(str(log), 738, 0)
        self.assertNotEqual(first, second)
        self.assertEqual(first["row_count_within_streak"], 2)
        self.assertEqual(second["row_count_within_streak"], 3)

        # Streak BROKEN: the pre-existing divergence does NOT cover it.
        log.write_text(json.dumps({"tic": 738, "genuine_count": 3}) + "\n",
                       encoding="utf-8")
        first_b = rcc.compute_genuine_zero_streak(str(log), 738, 3)
        log.write_text("".join(json.dumps({"tic": 738, "genuine_count": 3}) + "\n"
                               for _ in range(2)), encoding="utf-8")
        second_b = rcc.compute_genuine_zero_streak(str(log), 738, 3)
        self.assertEqual(first_b, second_b)
        self.assertEqual(first_b["broken_at_tic"], 738)
        self.assertEqual(first_b["row_count_within_streak"], 0)

        # And on that same arm this field DOES differ across the two fires.
        self._seed_prior_tic()
        before = self._vc()["prior_same_tic_observation"]
        self._seed_same_tic_entry_fire()
        after = self._vc()["prior_same_tic_observation"]
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
