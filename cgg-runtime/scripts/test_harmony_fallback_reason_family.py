#!/usr/bin/env python3
"""test_harmony_fallback_reason_family.py — reason-family counter fixtures.

Fix-site: bk-harmony-fallback-counter-reason-family (/review-689 ratified ray
on constitution-ledger#presence-observation-fallacy-guard, COUNTER-KEY axis;
struck tic 692). The reason-blind scalar converted a HEALTHY validator refusal
into outage-escalation input (t686 counterexample: scalar=1 on
validation_failed:imperative_vocabulary) and could never surface slow
admission-gate recurrence (t670+t686, 16 tics apart — prompt-drift signal).

Three ratified arms:
  (1) infrastructure-streak — consecutive infra fallbacks escalate LOUD at
      small N (outage semantics preserved, now correctly scoped);
  (2) admission-gate-recurrence — spaced validator refusals within the window
      fire the QUALITY-WATCH channel (explicitly NOT an outage) while the
      outage streak stays 0;                                     [RED pre-fix]
  (3) healthy-reset — an llm run resets the outage streak.
Plus: the t686 counterexample (a single validator refusal stamps
consecutive_fallbacks 0, not 1), kill-switch neutrality, family classifier,
and pre-voice-era honest stop.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("harmony_voice", _HERE / "harmony-voice.py")
hv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hv)


def _disposition(tic, voice_source=None, fallback_reason=None, no_voice=False):
    body = {"tic": tic}
    if not no_voice:
        body["voice"] = {"voice_source": voice_source, "fallback_reason": fallback_reason}
    return body


class ReasonFamilyCounter(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="harmony-fam-"))
        self._orig_dir = hv.HARMONY_DIR
        hv.HARMONY_DIR = self._tmp

    def tearDown(self):
        hv.HARMONY_DIR = self._orig_dir

    def _write(self, tic, **kw):
        (self._tmp / f"disposition-tic-{tic}.json").write_text(
            json.dumps(_disposition(tic, **kw)))

    def _apply(self, current_tic, voice_source, fallback_reason=None):
        voice = {"voice_source": voice_source, "fallback_reason": fallback_reason}
        return hv.apply_fallback_counter(voice, current_tic)

    def test_family_classifier(self):
        f = hv.fallback_reason_family
        self.assertEqual(f("validation_failed:imperative_vocabulary"), "admission_gate")
        self.assertEqual(f("llm_timeout_45s"), "infrastructure")
        self.assertEqual(f("claude_cli_not_found"), "infrastructure")
        self.assertEqual(f("llm_error:boom"), "infrastructure")
        self.assertEqual(f("kill_switch:HARMONY_VOICE=off"), "kill_switch")
        self.assertIsNone(f(None))

    def test_arm1_infrastructure_streak_escalates_loud(self):
        self._write(690, voice_source="template_fallback", fallback_reason="llm_timeout_45s")
        v = self._apply(691, "template_fallback", "llm_timeout_45s")
        self.assertEqual(v["consecutive_fallbacks"], 2)
        self.assertTrue(v["fallback_escalation"]["fired"])
        self.assertEqual(v["fallback_escalation"]["family"], "infrastructure")

    def test_arm2_admission_recurrence_fires_watch_not_outage(self):
        """THE t670+t686 shape: two validator refusals 16 tics apart with
        healthy runs between — the streak can never see it; the window must."""
        self._write(670, voice_source="template_fallback",
                    fallback_reason="validation_failed:multi_line")
        for t in range(671, 686):
            self._write(t, voice_source="llm")
        v = self._apply(686, "template_fallback", "validation_failed:imperative_vocabulary")
        self.assertEqual(v["consecutive_fallbacks"], 0)          # not outage input
        self.assertFalse(v["fallback_escalation"]["fired"])       # no outage escalation
        self.assertEqual(v["fallback_families"]["admission_gate_window_count"], 2)
        self.assertTrue(v["admission_gate_watch"]["fired"])       # recurrence surfaced

    def test_arm3_healthy_llm_run_resets_everything(self):
        self._write(690, voice_source="template_fallback", fallback_reason="llm_timeout_45s")
        v = self._apply(691, "llm")
        self.assertEqual(v["consecutive_fallbacks"], 0)
        self.assertFalse(v["fallback_escalation"]["fired"])
        self.assertIsNone(v["fallback_families"]["current"])

    def test_t686_counterexample_single_refusal_is_not_outage_input(self):
        """Pre-fix the scalar stamped 1 on a lone healthy refusal — the exact
        observed defect. Post-fix: 0 toward outage, 1 in the quality window."""
        v = self._apply(686, "template_fallback", "validation_failed:imperative_vocabulary")
        self.assertEqual(v["consecutive_fallbacks"], 0)
        self.assertEqual(v["fallback_families"]["admission_gate_window_count"], 1)
        self.assertFalse(v["admission_gate_watch"]["fired"])      # 1 < threshold 2

    def test_admission_refusal_breaks_the_infrastructure_streak(self):
        """A refusal between two timeouts is not outage continuity — the infra
        streak counts consecutive INFRA runs only."""
        self._write(689, voice_source="template_fallback", fallback_reason="llm_timeout_45s")
        self._write(690, voice_source="template_fallback",
                    fallback_reason="validation_failed:multi_line")
        v = self._apply(691, "template_fallback", "llm_timeout_45s")
        self.assertEqual(v["consecutive_fallbacks"], 1)           # prior timeout masked by refusal
        self.assertFalse(v["fallback_escalation"]["fired"])

    def test_kill_switch_counts_toward_nothing(self):
        self._write(690, voice_source="template_fallback", fallback_reason="llm_timeout_45s")
        v = self._apply(691, "template_fallback", "kill_switch:HARMONY_VOICE=off")
        self.assertEqual(v["consecutive_fallbacks"], 0)
        self.assertFalse(v["fallback_escalation"]["fired"])
        self.assertEqual(v["fallback_families"]["admission_gate_window_count"], 0)
        self.assertFalse(v["admission_gate_watch"]["fired"])

    def test_pre_voice_era_stops_the_walk(self):
        self._write(688, no_voice=True)
        self._write(689, voice_source="template_fallback",
                    fallback_reason="validation_failed:x")
        self._write(690, voice_source="template_fallback", fallback_reason="llm_timeout_45s")
        v = self._apply(691, "template_fallback", "llm_timeout_45s")
        self.assertEqual(v["consecutive_fallbacks"], 2)
        # the no-voice stop bounds the window: only 689+690 walked
        self.assertEqual(v["fallback_families"]["window_scanned"], 2)

    def test_backcompat_shim_returns_infrastructure_streak(self):
        self._write(689, voice_source="template_fallback", fallback_reason="llm_timeout_45s")
        self._write(690, voice_source="template_fallback", fallback_reason="llm_timeout_45s")
        self.assertEqual(hv.count_prior_fallback_streak(691), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
