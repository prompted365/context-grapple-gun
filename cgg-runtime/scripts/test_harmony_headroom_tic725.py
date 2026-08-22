#!/usr/bin/env python3
"""test_harmony_headroom_tic725.py — the voice-lane headroom observable.

Fix-site: constitution-ledger #threshold-raise-relocates-the-wall-ship-a-
headroom-observable (/review 725, Architect-ratified).

The counters in harmony-voice.py (infrastructure streak, admission-gate window
— t692 reason-family design) are CROSSING-observers: they key on fallback and
timeout EVENTS, so they can only speak after the wall has been hit. The voice
lane timed out 8x at a 45 s budget; the budget was raised to 120 s; it timed
out 8 more times at 120 s within ~17 tics. Raising a threshold RELOCATES the
wall, it does not govern the APPROACH.

The leading indicator was on disk the whole time and unread: every disposition
receipt has carried `voice.duration_ms` since tic 570. These fixtures pin the
reader that turns it into an approach observable.

Arms:
  (1) RED — the entire pre-change receipt corpus (tics <= 725) carries NO
      top-level `voice_headroom`. The observable did not exist.  [RED evidence]
  (2) PLACEMENT LAW — an end-to-end run writes `voice_headroom` at TOP LEVEL of
      the written artifact and the field SURVIVES the writeback (no schema
      contract drops it, and it is not buried inside `voice`).
  (3) ARITHMETIC — the >=90 %-of-budget share, recent max, and approach max are
      computed correctly from synthetic duration history.
  (4) CROSSING vs APPROACH — a timed-out run sits at 100 % of budget BY
      CONSTRUCTION; it counts toward the ceiling but must not pollute the
      approach statistics, which are the actual leading indicator.
  (5) HONESTY — a budget change inside the window is DECLARED; an unusable
      window yields nulls, never fabricated zeros; the pre-voice era stops the
      walk exactly as the sibling counter walk does.
  (6) VERDICT REPRODUCTION — over the REAL on-disk corpus at the window the
      ratifying verdict cited (12 receipts ending tic 721) the observable
      reproduces its arithmetic: 5/12 runs >= 90 % of budget, and the slowest
      COMPLETED call at 97.7 % of the 120 s budget.
  (7) CONSUMER SET — the glance-speed pointer writer (harmony-invoke.sh step 3)
      projects the observable, so it is read, not written-never-read.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VOICE_PY = _HERE / "harmony-voice.py"
_INVOKE_SH = _HERE / "harmony-invoke.sh"
_SPEC = importlib.util.spec_from_file_location("harmony_voice_headroom", _VOICE_PY)
hv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hv)

# The live federation receipt corpus (the surface the observable derives from).
_REAL_HARMONY_DIR = Path("/Users/breydentaylor/canonical/audit-logs/harmony")
# Last tic written BEFORE this change landed — the pre-change corpus boundary.
_PRE_CHANGE_MAX_TIC = 725
_BUDGET = 120_000


def _voice(duration_ms, voice_source="llm", fallback_reason=None):
    return {"voice_source": voice_source, "fallback_reason": fallback_reason,
            "duration_ms": duration_ms}


class HeadroomRedEvidence(unittest.TestCase):
    """Arm 1 — the observable did not exist before this change."""

    @unittest.skipUnless(_REAL_HARMONY_DIR.is_dir(), "live harmony corpus absent")
    def test_red_pre_change_receipts_carry_no_headroom(self):
        checked = 0
        for p in _REAL_HARMONY_DIR.glob("disposition-tic-*.json"):
            m = re.search(r"disposition-tic-(\d+)\.json$", p.name)
            if not m or int(m.group(1)) > _PRE_CHANGE_MAX_TIC:
                continue
            body = json.loads(p.read_text())
            self.assertNotIn(
                "voice_headroom", body,
                f"{p.name}: pre-change receipt unexpectedly carries voice_headroom")
            checked += 1
        self.assertGreater(checked, 100, "expected a substantial pre-change corpus")

    @unittest.skipUnless(_REAL_HARMONY_DIR.is_dir(), "live harmony corpus absent")
    def test_red_the_leading_indicator_was_already_written_and_unread(self):
        """duration_ms existed on every receipt — only the READER was missing."""
        with_duration = 0
        for p in _REAL_HARMONY_DIR.glob("disposition-tic-*.json"):
            m = re.search(r"disposition-tic-(\d+)\.json$", p.name)
            if not m or int(m.group(1)) > _PRE_CHANGE_MAX_TIC:
                continue
            v = json.loads(p.read_text()).get("voice")
            if isinstance(v, dict) and isinstance(v.get("duration_ms"), int):
                with_duration += 1
        self.assertGreater(with_duration, 100)


class HeadroomPlacementLaw(unittest.TestCase):
    """Arm 2 — the field survives to the WRITTEN artifact, at TOP level."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="harmony-headroom-e2e-"))
        self._dir = self._tmp / "audit-logs" / "harmony"
        self._dir.mkdir(parents=True)

    def _write_receipt(self, tic, duration_ms, voice_source="llm", reason=None):
        (self._dir / f"disposition-tic-{tic}.json").write_text(json.dumps({
            "type": "harmony.disposition", "meaningState": "preserved",
            "acousticSignature": {"snr": 0.58},
            "disposition": {"stance": "carry", "caution": "c",
                            "oneWayInjection": "STANCE=carry"},
            "voice": _voice(duration_ms, voice_source, reason),
        }))

    def test_end_to_end_run_writes_headroom_at_top_level(self):
        for tic, ms in zip(range(710, 721), [117196, 120024, 120029, 88382, 78412,
                                             101832, 82000, 96074, 90901, 112725,
                                             109686]):
            reason = "llm_timeout_120s" if tic in (711, 712) else None
            src = "template_fallback" if reason else "llm"
            self._write_receipt(tic, ms, src, reason)

        target = self._dir / "disposition-tic-721.json"
        target.write_text(json.dumps({
            "type": "harmony.disposition", "meaningState": "preserved",
            "acousticSignature": {"snr": 0.58},
            "disposition": {"stance": "carry", "caution": "c",
                            "oneWayInjection": "STANCE=carry"},
        }))

        env = dict(os.environ)
        env.update({"CGG_REPO_ROOT": str(self._tmp), "HARMONY_VOICE": "off"})
        proc = subprocess.run(
            [sys.executable, str(_VOICE_PY), "--disposition", str(target)],
            capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)

        written = json.loads(target.read_text())
        # TOP level, sibling of `voice` — not buried inside the receipt of the
        # thing that failed.
        self.assertIn("voice_headroom", written,
                      "voice_headroom did not survive the writeback")
        self.assertNotIn("voice_headroom", written["voice"],
                         "observable must not be buried inside the voice object")
        h = written["voice_headroom"]
        self.assertEqual(h["budget_ms"], _BUDGET)
        self.assertEqual(h["window_observed"], 12)
        self.assertEqual(h["window_tics"][0], 721)
        # 12 runs: current (kill-switch fallback, fast) + the 11 seeded priors.
        # Of the priors, 5 are >= 90 % of budget -> 5/12.
        self.assertAlmostEqual(h["share_of_recent_runs_ge_90pct"], 5 / 12, places=4)
        self.assertAlmostEqual(h["recent_max_pct"], 120029 / _BUDGET, places=5)
        self.assertAlmostEqual(h["approach_max_pct"], 117196 / _BUDGET, places=5)
        self.assertEqual(h["crossings_in_window"], 2)
        self.assertEqual(h["approaches_in_window"], 10)


class HeadroomArithmetic(unittest.TestCase):
    """Arms 3-5 — computed correctly, and honest where it cannot compute."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="harmony-headroom-"))
        self._orig = hv.HARMONY_DIR
        hv.HARMONY_DIR = self._tmp

    def tearDown(self):
        hv.HARMONY_DIR = self._orig

    def _write(self, tic, duration_ms=None, voice_source="llm", reason=None,
               no_voice=False):
        body = {"tic": tic}
        if not no_voice:
            body["voice"] = _voice(duration_ms, voice_source, reason)
        (self._tmp / f"disposition-tic-{tic}.json").write_text(json.dumps(body))

    def test_share_ge_90pct_from_synthetic_history(self):
        """5 of 12 runs at or above the near-wall threshold -> 5/12."""
        # 11 priors: 4 at/above 108000 ms (90 %), 7 below.
        priors = [110_000, 60_000, 108_000, 61_000, 62_000, 119_000,
                  63_000, 64_000, 65_000, 66_000, 117_000]
        for tic, ms in zip(range(700, 711), priors):
            self._write(tic, ms)
        cur = _voice(115_000)  # 5th run at/above threshold
        h = hv.compute_voice_headroom(cur, 711, window=12, budget_ms=_BUDGET)
        self.assertEqual(h["window_observed"], 12)
        self.assertAlmostEqual(h["share_of_recent_runs_ge_90pct"], 5 / 12, places=4)
        self.assertAlmostEqual(h["recent_max_pct"], 119_000 / _BUDGET, places=5)
        self.assertAlmostEqual(h["pct_of_budget"], 115_000 / _BUDGET, places=5)
        self.assertEqual(h["headroom_ms"], _BUDGET - 115_000)
        self.assertEqual(h["near_wall_threshold_pct"], 0.90)

    def test_window_bounds_at_n_and_reports_the_tics_it_used(self):
        for tic in range(600, 640):
            self._write(tic, 50_000)
        h = hv.compute_voice_headroom(_voice(51_000), 640, window=12,
                                      budget_ms=_BUDGET)
        self.assertEqual(h["window_requested"], 12)
        self.assertEqual(h["window_observed"], 12)
        self.assertEqual(h["window_tics"], [640] + list(range(639, 628, -1)))

    def test_crossings_count_toward_ceiling_but_not_the_approach_signal(self):
        """A timeout is 100 % of budget BY CONSTRUCTION — a crossing, not an
        approach. It must not inflate the leading indicator it precedes."""
        self._write(700, 120_030, "template_fallback", "llm_timeout_120s")
        self._write(701, 120_020, "template_fallback", "llm_timeout_120s")
        self._write(702, 60_000)
        h = hv.compute_voice_headroom(_voice(70_000), 703, window=4,
                                      budget_ms=_BUDGET)
        self.assertEqual(h["crossings_in_window"], 2)
        self.assertEqual(h["approaches_in_window"], 2)
        # ceiling sees the crossings...
        self.assertAlmostEqual(h["recent_max_pct"], 120_030 / _BUDGET, places=5)
        # ...the approach signal does not.
        self.assertAlmostEqual(h["approach_max_pct"], 70_000 / _BUDGET, places=5)
        self.assertAlmostEqual(h["approach_mean_pct"], 65_000 / _BUDGET, places=5)

    def test_all_crossings_window_yields_null_approach_not_zero(self):
        """No completed call in the window means the approach is UNMEASURED,
        never 0 % — an unmeasured approach and a fast one are different claims."""
        self._write(700, 120_030, "template_fallback", "llm_timeout_120s")
        h = hv.compute_voice_headroom(
            _voice(120_020, "template_fallback", "llm_timeout_120s"), 701,
            window=2, budget_ms=_BUDGET)
        self.assertIsNone(h["approach_max_pct"])
        self.assertIsNone(h["approach_mean_pct"])
        self.assertEqual(h["approaches_in_window"], 0)

    def test_budget_change_inside_the_window_is_declared(self):
        """The exact 45s -> 120s shape. A prior run's own timeout reason names
        the budget it ran under; the pct math mixes eras and SAYS so."""
        self._write(683, 45_017, "template_fallback", "llm_timeout_45s")
        self._write(684, 45_018, "template_fallback", "llm_timeout_45s")
        h = hv.compute_voice_headroom(_voice(73_114), 685, window=3,
                                      budget_ms=_BUDGET)
        self.assertTrue(h["budget_change_in_window"])
        self.assertEqual(h["budget_eras_ms"], [45_000, 120_000])

    def test_single_era_window_declares_no_budget_change(self):
        self._write(700, 60_000)
        h = hv.compute_voice_headroom(_voice(61_000), 701, window=2,
                                      budget_ms=_BUDGET)
        self.assertFalse(h["budget_change_in_window"])
        self.assertEqual(h["budget_eras_ms"], [120_000])

    def test_pre_voice_era_stops_the_walk(self):
        """Same honest stop as the sibling fallback-family walk."""
        self._write(698, no_voice=True)
        self._write(699, 60_000)
        self._write(700, 61_000)
        h = hv.compute_voice_headroom(_voice(62_000), 701, window=12,
                                      budget_ms=_BUDGET)
        self.assertEqual(h["window_observed"], 3)
        self.assertEqual(h["window_tics"], [701, 700, 699])

    def test_no_prior_history_is_honest_not_fabricated(self):
        h = hv.compute_voice_headroom(_voice(60_000), 701, window=12,
                                      budget_ms=_BUDGET)
        self.assertEqual(h["window_observed"], 1)
        self.assertAlmostEqual(h["share_of_recent_runs_ge_90pct"], 0.0, places=4)
        self.assertAlmostEqual(h["pct_of_budget"], 0.5, places=5)

    def test_missing_duration_yields_nulls_never_zeros(self):
        h = hv.compute_voice_headroom({"voice_source": "llm"}, None,
                                      window=12, budget_ms=_BUDGET)
        self.assertEqual(h["window_observed"], 0)
        self.assertIsNone(h["pct_of_budget"])
        self.assertIsNone(h["recent_max_pct"])
        self.assertIsNone(h["share_of_recent_runs_ge_90pct"])
        self.assertIsNone(h["headroom_ms"])

    def test_unparsable_tic_still_reports_the_current_run_honestly(self):
        h = hv.compute_voice_headroom(_voice(96_000), None, window=12,
                                      budget_ms=_BUDGET)
        self.assertEqual(h["window_observed"], 1)
        self.assertEqual(h["window_tics"], [None])
        self.assertAlmostEqual(h["pct_of_budget"], 0.8, places=5)

    def test_receipt_declares_its_own_provenance_and_confidence(self):
        h = hv.compute_voice_headroom(_voice(60_000), None, budget_ms=_BUDGET)
        self.assertEqual(h["confidence_class"], "exact")
        self.assertIn("duration_ms", h["derived_from"])
        self.assertEqual(h["budget_source"], "HARMONY_VOICE_TIMEOUT_S")
        self.assertEqual(h["window_source"], "HARMONY_HEADROOM_WINDOW")

    def test_window_is_env_tunable_like_the_budget_it_watches(self):
        for tic in range(690, 701):
            self._write(tic, 60_000)
        os.environ["HARMONY_HEADROOM_WINDOW"] = "4"
        try:
            h = hv.compute_voice_headroom(_voice(60_000), 701, budget_ms=_BUDGET)
        finally:
            del os.environ["HARMONY_HEADROOM_WINDOW"]
        self.assertEqual(h["window_requested"], 4)
        self.assertEqual(h["window_observed"], 4)


class HeadroomReproducesRatifiedVerdict(unittest.TestCase):
    """Arm 6 — the observable's numbers ARE the verdict's numbers."""

    @unittest.skipUnless(_REAL_HARMONY_DIR.is_dir(), "live harmony corpus absent")
    def test_real_corpus_window_ending_721_matches_the_verdict(self):
        orig = hv.HARMONY_DIR
        hv.HARMONY_DIR = _REAL_HARMONY_DIR
        try:
            v721 = json.loads(
                (_REAL_HARMONY_DIR / "disposition-tic-721.json").read_text())["voice"]
            h = hv.compute_voice_headroom(v721, 721, window=12, budget_ms=_BUDGET)
        finally:
            hv.HARMONY_DIR = orig
        self.assertEqual(h["window_observed"], 12)
        self.assertEqual(h["window_tics"], list(range(721, 709, -1)))
        # "5 of the last 12 runs >= 90 %" — the ratified verdict's own figure.
        self.assertAlmostEqual(h["share_of_recent_runs_ge_90pct"], 5 / 12, places=4)
        # "max 117.2 s = 97.7 % of budget" — the slowest COMPLETED call.
        self.assertEqual(h["approach_max_pct"], round(117196 / _BUDGET, 5))
        self.assertAlmostEqual(h["approach_max_pct"], 0.977, places=3)
        # The two 120 s timeouts in the window are crossings, already counted by
        # the crossing-observers; they sit at/over the ceiling.
        self.assertEqual(h["crossings_in_window"], 2)
        self.assertGreaterEqual(h["recent_max_pct"], 1.0)


class HeadroomConsumerSet(unittest.TestCase):
    """Arm 7 — the observable is read, not written-never-read."""

    def test_glance_speed_pointer_writer_projects_the_observable(self):
        body = _INVOKE_SH.read_text()
        self.assertIn('d.get("voice_headroom")', body,
                      "pointer writer does not read the observable")
        for key in ("voice_budget_ms", "voice_pct_of_budget",
                    "voice_recent_max_pct", "voice_approach_max_pct",
                    "voice_share_recent_ge_90pct", "voice_headroom_window"):
            self.assertIn(f'"{key}"', body, f"pointer writer omits {key}")


class HeadroomLeavesCrossingObserversAlone(unittest.TestCase):
    """The t692 reason-family counters are correct and must not be perturbed."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="harmony-headroom-counters-"))
        self._orig = hv.HARMONY_DIR
        hv.HARMONY_DIR = self._tmp

    def tearDown(self):
        hv.HARMONY_DIR = self._orig

    def test_family_classifier_and_streak_semantics_unchanged(self):
        self.assertEqual(hv.fallback_reason_family("llm_timeout_120s"),
                         "infrastructure")
        self.assertEqual(hv.fallback_reason_family("validation_failed:multi_line"),
                         "admission_gate")
        (self._tmp / "disposition-tic-690.json").write_text(json.dumps(
            {"voice": {"voice_source": "template_fallback",
                       "fallback_reason": "llm_timeout_120s"}}))
        v = hv.apply_fallback_counter(
            {"voice_source": "template_fallback",
             "fallback_reason": "llm_timeout_120s"}, 691)
        self.assertEqual(v["consecutive_fallbacks"], 2)
        self.assertTrue(v["fallback_escalation"]["fired"])
        self.assertNotIn("voice_headroom", v,
                         "headroom must not be stamped inside the voice object")


if __name__ == "__main__":
    unittest.main(verbosity=2)
