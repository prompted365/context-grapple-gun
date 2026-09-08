#!/usr/bin/env python3
"""test_harmony_expiry_forecast_tic783.py — THE EXPIRY-FORECAST face fixtures.

Fix-site: /review 783 Q1 ratified same-pass cure (cpr id ending d6d1809cc61d —
guard 19's eighth face, the TEMPORAL sibling of the SATURATED-DETECTOR face on
constitution-ledger#presence-observation-fallacy-guard). A trailing-window
watch's transition to quiet reports EXPIRY, not remediation; the cure emits an
expiry forecast BESIDE the flag, strictly additive.

Four arms:
  (1) the LIVED shape — refusals (733,737,760) at current tic 780, threshold 2,
      window 50: next expiry = 733 at tic 784 (count 3->2), fired flips false at
      tic 788 when 737 exits (count 2->1 < 2) — the t788 flip the born forecast;
  (2) EMPTY members — honest nulls, already_below_threshold True, no fabricated
      forecast (the no-members arm of the members conditional);
  (3) CURRENT-RUN refusal joins the members (the current_is_refusal arm) and
      moves the flip later;
  (4) ALREADY-BELOW-THRESHOLD with members present — next_expiry still published,
      fired_flips_false_at_tic stays None (the flip guard's other arm: a watch
      already quiet has no flip to forecast).
Plus the wiring assertion: apply_fallback_counter publishes the block inside
admission_gate_watch without moving fired/count/prior_refusal_tics semantics.
"""

import importlib.util
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("harmony_voice", _HERE / "harmony-voice.py")
hv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hv)


class TestExpiryForecast(unittest.TestCase):
    def test_lived_shape_t780_flip_forecast_at_788(self):
        # The born's own measured instance: (760,737,733) at t780, threshold 2.
        f = hv.compute_admission_expiry_forecast(
            [760, 737, 733], False, 780, 2, window_files=50)
        self.assertEqual(f["members"], [733, 737, 760])
        self.assertEqual(f["count_projected_from"], 3)
        self.assertFalse(f["already_below_threshold"])
        self.assertEqual(f["next_expiry"]["member_tic"], 733)
        self.assertEqual(f["next_expiry"]["expires_at_tic"], 784)
        self.assertEqual(f["next_expiry"]["count_after"], 2)
        # 733 exits -> 2 remaining (still fired); 737 exits at 788 -> 1 < 2.
        self.assertEqual(f["fired_flips_false_at_tic"], 788)
        self.assertEqual(f["projection_invariant"], "absent_further_refusals")
        self.assertIn("one_disposition_per_tic_forward", f["assumption"])

    def test_empty_members_honest_nulls(self):
        f = hv.compute_admission_expiry_forecast([], False, 780, 2, window_files=50)
        self.assertEqual(f["members"], [])
        self.assertIsNone(f["next_expiry"])
        self.assertIsNone(f["fired_flips_false_at_tic"])
        self.assertTrue(f["already_below_threshold"])

    def test_current_refusal_joins_members_and_moves_flip(self):
        # Same priors, but the CURRENT run is itself a refusal at tic 780:
        # members (733,737,760,780); flip now needs the count to fall below 2 —
        # 733 exits (3 left), 737 exits (2 left), 760 exits at 811 (1 left < 2).
        f = hv.compute_admission_expiry_forecast(
            [760, 737, 733], True, 780, 2, window_files=50)
        self.assertEqual(f["members"], [733, 737, 760, 780])
        self.assertEqual(f["fired_flips_false_at_tic"], 811)

    def test_already_below_threshold_publishes_expiry_but_no_flip(self):
        # One member under threshold 2: the watch is already quiet — the member's
        # own expiry is still forecast, but there is no fired flip to project.
        f = hv.compute_admission_expiry_forecast([760], False, 780, 2, window_files=50)
        self.assertTrue(f["already_below_threshold"])
        self.assertEqual(f["next_expiry"]["member_tic"], 760)
        self.assertEqual(f["next_expiry"]["expires_at_tic"], 811)
        self.assertIsNone(f["fired_flips_false_at_tic"])
        # Wiring: the block rides INSIDE admission_gate_watch, additive only.
        voice = {"voice_source": "llm"}
        stamped = hv.apply_fallback_counter(dict(voice), 10 ** 9)
        watch = stamped["admission_gate_watch"]
        self.assertIn("expiry_forecast", watch)
        self.assertIn("fired", watch)          # pre-existing semantics untouched
        self.assertIn("count", watch)
        self.assertIn("prior_refusal_tics", watch)


if __name__ == "__main__":
    unittest.main()
