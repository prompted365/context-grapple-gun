#!/usr/bin/env python3
"""test_harmony_family_statistic_tic755.py — the family-statistic ray fixtures.

Fix-site: /review 755 Q1 (cpr_mogul_deep_audit_97339bfeeecb, PROMOTE-as-
refinement-ray on constitution-ledger#presence-observation-fallacy-guard —
the FAMILY-STATISTIC face): a family-split counter gives every family the
same statistic class, or each family's statistic class and its blind spot
ride beside the count — one family's history is never the lane's.

Lived shape (tic 752): admission_gate 4 occurrences (windowed count) fired
its watch and printed refusal tics topping out at 737, while infrastructure
sat at 9 occurrences in the SAME window with leading streak 0 — the lane's
true latest infrastructure event (749) invisible. The cure is ADDITIVE:
the windowed infrastructure pair + per-family statistic_class/blind_spot
stamps + sibling-family disclosure on both stderr watch lines. No flag,
threshold, band, or escalation change (the row's own fence).

Seven tests: windowed-pair collection · streak-blind-spot visibility ·
statistic_classes stamp · current-infra accounting · pre-755 schema
stability · QUALITY-WATCH sibling disclosure · DECORATIVE-notice sibling
disclosure.
"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("harmony_voice_t755", _HERE / "harmony-voice.py")
hv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hv)


def _disposition(tic, voice_source=None, fallback_reason=None):
    return {"tic": tic, "voice": {"voice_source": voice_source,
                                  "fallback_reason": fallback_reason}}


class FamilyStatisticRay(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="harmony-famstat-"))
        self._orig_dir = hv.HARMONY_DIR
        hv.HARMONY_DIR = self._tmp

    def tearDown(self):
        hv.HARMONY_DIR = self._orig_dir

    def _write(self, tic, **kw):
        (self._tmp / f"disposition-tic-{tic}.json").write_text(
            json.dumps(_disposition(tic, **kw)))

    def _healthy(self, tic):
        self._write(tic, voice_source="llm", fallback_reason=None)

    def _infra(self, tic):
        self._write(tic, voice_source="template_fallback",
                    fallback_reason="llm_timeout_45s")

    def _refusal(self, tic):
        self._write(tic, voice_source="template_fallback",
                    fallback_reason="validation_failed:imperative_vocabulary")

    def _apply(self, current_tic, voice_source="llm", fallback_reason=None):
        voice = {"voice_source": voice_source, "fallback_reason": fallback_reason}
        return hv.apply_fallback_counter(voice, current_tic)

    def test_windowed_infrastructure_pair_collected(self):
        # spaced infra occurrences accumulate in the windowed pair (descending
        # walk order, the refusal_tics convention)
        self._infra(700)
        self._healthy(701)
        self._infra(702)
        self._healthy(703)
        out = hv.scan_prior_fallback_families(704)
        self.assertEqual(out["infrastructure_count"], 2)
        self.assertEqual(out["infrastructure_tics"], [702, 700])

    def test_streak_blind_spot_now_visible_in_window(self):
        # THE RAY'S EXACT CLAIM: intermittent infra recurrence reads streak 0
        # (the blind spot) while the windowed count carries the history.
        self._infra(704)
        self._healthy(705)
        self._infra(706)
        self._healthy(707)
        out = hv.scan_prior_fallback_families(708)
        self.assertEqual(out["infrastructure_streak"], 0)
        self.assertEqual(out["infrastructure_count"], 2)

    def test_statistic_classes_stamped_with_blind_spots(self):
        self._infra(710)
        self._healthy(711)
        v = self._apply(712)
        fam = v["fallback_families"]
        sc = fam["statistic_classes"]
        self.assertEqual(sc["infrastructure"]["statistic_class"],
                         "leading_consecutive_streak")
        self.assertEqual(sc["admission_gate"]["statistic_class"],
                         "windowed_occurrence_count")
        self.assertIn("intermittent recurrence", sc["infrastructure"]["blind_spot"])
        self.assertIn("consecutivity", sc["admission_gate"]["blind_spot"])
        self.assertEqual(fam["infrastructure_window_count"], 1)
        self.assertEqual(fam["infrastructure_window_tics"], [710])
        self.assertEqual(fam["latest_infrastructure_tic"], 710)

    def test_current_infra_counts_and_latest_is_current(self):
        # count includes the current run (admission-watch convention); the
        # tics list stays prior-only (refusal_tics convention).
        self._infra(720)
        self._healthy(721)
        v = self._apply(722, voice_source="template_fallback",
                        fallback_reason="llm_timeout_45s")
        fam = v["fallback_families"]
        self.assertEqual(fam["infrastructure_window_count"], 2)
        self.assertEqual(fam["infrastructure_window_tics"], [720])
        self.assertEqual(fam["latest_infrastructure_tic"], 722)

    def test_pre755_keys_keep_shape_and_semantics(self):
        self._refusal(730)
        self._healthy(731)
        v = self._apply(732)
        fam = v["fallback_families"]
        self.assertIsNone(fam["current"])
        self.assertEqual(fam["infrastructure_streak"], 0)
        self.assertEqual(fam["admission_gate_window_count"], 1)
        self.assertEqual(fam["window_scanned"], 2)
        self.assertEqual(v["consecutive_fallbacks"], 0)
        self.assertEqual(v["fallback_escalation"]["family"], "infrastructure")

    def test_quality_watch_stderr_discloses_infrastructure_sibling(self):
        # two prior refusals fire the admission watch (threshold 2); the line
        # now names the infrastructure sibling's windowed history beside it.
        self._refusal(740)
        self._infra(741)
        self._refusal(742)
        self._healthy(743)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            v = self._apply(744)
        self.assertTrue(v["admission_gate_watch"]["fired"])
        err = buf.getvalue()
        self.assertIn("QUALITY-WATCH", err)
        self.assertIn("sibling family this window: infrastructure 1 occurrences", err)
        self.assertIn("latest tic 741", err)

    def test_decorative_notice_discloses_admission_sibling(self):
        # force the outage streak to fire at threshold 2 (function override,
        # restored) and assert the admission sibling clause rides the notice.
        self._refusal(750)
        self._infra(751)
        orig = hv._fallback_threshold
        hv._fallback_threshold = lambda: 2
        try:
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                v = self._apply(752, voice_source="template_fallback",
                                fallback_reason="llm_timeout_45s")
        finally:
            hv._fallback_threshold = orig
        self.assertTrue(v["fallback_escalation"]["fired"])
        err = buf.getvalue()
        self.assertIn("DECORATIVE-BAND-NOTICE", err)
        self.assertIn("sibling family this window: admission_gate 1 refusals", err)


if __name__ == "__main__":
    unittest.main()
