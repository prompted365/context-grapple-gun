#!/usr/bin/env python3
"""Fixtures for crisis-injection.py — the tic-744 ARRIVAL predicate (Check 2) and the
Check-1 field cure (F-744-CS1/CS2). Ruled by the crisis-steward seat at tic 744
(audit-logs/sentinel/crisis-threshold-ruling-tic744.json; /review 744 Q4).

THE RULING: ACTIVE_THRESHOLD=10 (an absolute test on a monotonically growing set —
9/9 shadow rows would_inject against a bit-identical active set) is retired for an
arrival predicate: A1 >=5 new NON-campaign active ids since the prior-tic shadow
observation, OR A2 >=12 new ids any lane in one tic, OR A3 standing active > 90.
No base => delta arms SKIPPED, never default-fire. The shadow lane records EVERY
evaluation (trip or no trip) — it is the predicate's state store and its negative
control (ruling falsifier F4).

THE CHECK-1 CURE: Check 1 keyed d['id'] and required d['tic']==current_tic; today's
daily rows carry signal_id (40/50) and almost never a tic (4/50) — Check 1 saw ZERO
rows at tics 743/744. Cure: signal_id-or-id, tic-carrying rows counted at the
current tic, tic-less rows counted as today/tic-unresolved and DISCLOSED as such.

RED-THEN-GREEN + NEGATIVE CONTROL spine (house convention). Every case in its own
TemporaryDirectory; nothing touches any real audit-logs surface.
"""
import importlib.util, json, os, tempfile, unittest, pathlib, datetime

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("crisis_injection", HERE / "crisis-injection.py")
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)

CAMP = "sig_ladder_down_audit_finding_"


def _mk(tmp, ids, prior=None, prior_tic=743):
    sig = os.path.join(tmp, "signals"); os.makedirs(sig, exist_ok=True)
    with open(os.path.join(sig, "active-manifest.jsonl"), "w") as f:
        for i in ids:
            f.write(json.dumps({"signal_id": i, "status": "active"}) + "\n")
    if prior is not None:
        os.makedirs(os.path.join(tmp, "sentinel"), exist_ok=True)
        with open(os.path.join(tmp, "sentinel", "crisis-injection-shadow.jsonl"), "w") as f:
            # a row of the PRE-744 schema (threshold:10) — the base must read across vintages
            f.write(json.dumps({"type": "crisis_injection_shadow", "check": "active_signal_count",
                                "tic": prior_tic, "active_count": len(prior), "threshold": 10,
                                "would_inject": True, "active_ids": sorted(prior),
                                "mode": "shadow"}) + "\n")
    return sig


def _rows(tmp):
    p = os.path.join(tmp, "sentinel", "crisis-injection-shadow.jsonl")
    return [json.loads(l) for l in open(p).read().strip().splitlines()]


class TestRedRetiredAbsoluteThresholdCriedWolf(unittest.TestCase):
    def test_old_predicate_fires_on_a_bit_identical_set(self):
        # RED (the retired shape): 58 > 10 is True on a set that has not moved.
        ids = [f"s{i}" for i in range(58)]
        self.assertTrue(len(ids) > 10)
        self.assertEqual(sorted(ids), sorted(ids))   # no arrival, yet "would_inject"
    def test_constant_is_retired(self):
        self.assertFalse(hasattr(ci, "ACTIVE_THRESHOLD"))
        self.assertEqual((ci.ARRIVAL_NON_CAMPAIGN, ci.ARRIVAL_ANY_LANE, ci.ACTIVE_ABSOLUTE_CEILING), (5, 12, 90))


class TestGreenArrivalPredicate(unittest.TestCase):
    def test_no_base_skips_delta_arms_and_stays_silent_but_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, [f"s{i}" for i in range(12)])           # no prior row
            self.assertIsNone(ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True))
            r = _rows(tmp)[-1]
            self.assertFalse(r["tripped"]); self.assertIsNone(r["prior_observation_tic"])
            self.assertFalse(r["delta_arms_evaluated"]); self.assertEqual(r["predicate_version"], "tic744")
    def test_A1_non_campaign_arrival_trips_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, [f"s{i}" for i in range(5)], prior=[])
            out = ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True)
            self.assertIsNotNone(out); self.assertIn("A1_non_campaign_arrival", out)
            r = _rows(tmp)[-1]
            self.assertEqual(r["arm"], "A1_non_campaign_arrival"); self.assertTrue(r["injected"])
            self.assertEqual(r["new_since_prior_tic"], 5); self.assertEqual(r["prior_observation_tic"], 743)
    def test_four_non_campaign_arrivals_stay_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, [f"n{i}" for i in range(4)] + [f"{CAMP}{i}" for i in range(7)], prior=[])
            self.assertIsNone(ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True))
            r = _rows(tmp)[-1]; self.assertIsNone(r["arm"]); self.assertEqual(r["new_since_prior_tic"], 11)
    def test_A2_campaign_dump_trips_as_A2_not_A1(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, [f"{CAMP}{i}" for i in range(12)], prior=[])
            out = ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True)
            self.assertIn("A2_any_lane_burst", out)
            r = _rows(tmp)[-1]; self.assertEqual(r["non_campaign_new"], [])
    def test_A3_ceiling_trips_with_zero_arrivals(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids = [f"s{i}" for i in range(91)]
            sig = _mk(tmp, ids, prior=ids)
            out = ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True)
            self.assertIn("A3_absolute_ceiling", out)
            r = _rows(tmp)[-1]; self.assertEqual(r["new_since_prior_tic"], 0)
    def test_ninety_standing_with_no_arrivals_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids = [f"s{i}" for i in range(90)]
            sig = _mk(tmp, ids, prior=ids)
            self.assertIsNone(ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True))
    def test_base_ignores_rows_of_the_current_tic(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, [f"s{i}" for i in range(6)], prior=[], prior_tic=744)   # same-tic row: not a base
            self.assertIsNone(ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True))
            self.assertIsNone(_rows(tmp)[-1]["prior_observation_tic"])


class TestShadowLaneIsMechanism(unittest.TestCase):
    def test_shadow_mode_records_would_inject_and_injects_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, [f"s{i}" for i in range(12)], prior=[])
            self.assertIsNone(ci.check_signal_storm(sig, 744, audit_logs=tmp))
            r = _rows(tmp)[-1]
            self.assertTrue(r["would_inject"]); self.assertFalse(r["injected"]); self.assertEqual(r["mode"], "shadow")
    def test_no_trip_evaluation_still_writes_a_row_F4(self):
        # ruling falsifier F4: a post-flip tic with zero shadow rows = the detector is dead again
        with tempfile.TemporaryDirectory() as tmp:
            ids = [f"s{i}" for i in range(3)]
            sig = _mk(tmp, ids, prior=ids)
            self.assertIsNone(ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True))
            r = _rows(tmp)[-1]
            self.assertEqual(r["tic"], 744); self.assertFalse(r["tripped"]); self.assertEqual(r["mode"], "live")
    def test_fail_soft_without_audit_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, [f"s{i}" for i in range(12)])
            self.assertIsNone(ci.check_signal_storm(sig, 744, audit_logs=None, live_active_threshold=True))


class TestCheck1FieldCure(unittest.TestCase):
    def _daily(self, sig, rows):
        # F-745: the daily file is named by the WRITER's clock (UTC, every emitter in the
        # corpus) — the fixture keyed date.today() (local) and went RED at the 745 patch
        # between UTC and local midnight (4/4 Check-1 cases returned None at 22:5x EDT).
        today = ci._utc_today()
        with open(os.path.join(sig, f"{today}.jsonl"), "w") as f:
            for r in rows: f.write(json.dumps(r) + "\n")
    def test_signal_id_rows_without_tic_fire_as_tic_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, ["x"], prior=["x"])
            self._daily(sig, [{"type": "signal", "signal_id": "sig_runaway"}] * 51)
            out = ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True)
            self.assertIn("sig_runaway", out); self.assertIn("rows_today_tic_unresolved", out)
    def test_tic_carrying_rows_count_at_current_tic_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, ["x"], prior=["x"])
            self._daily(sig, [{"type": "signal", "signal_id": "sig_old", "tic": 743}] * 51)
            self.assertIsNone(ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True))
            self._daily(sig, [{"type": "signal", "id": "sig_legacy", "tic": 744}] * 51)
            self.assertIn("rows_at_current_tic", ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True))
    def test_check1_no_longer_suppresses_check2_CS2(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, [f"s{i}" for i in range(5)], prior=[])
            self._daily(sig, [{"type": "signal", "signal_id": "sig_runaway"}] * 51)
            out = ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True)
            self.assertIn("sig_runaway", out); self.assertIn("A1_non_campaign_arrival", out)
    def test_negative_control_reverting_the_key_read_blinds_check1(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, ["x"], prior=["x"])
            self._daily(sig, [{"type": "signal", "signal_id": "sig_runaway"}] * 51)
            self.assertIsNotNone(ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True))
            orig = ci._row_signal_id
            ci._row_signal_id = lambda d: d.get("id", "")      # the pre-744 read
            try:
                self.assertIsNone(ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True))
            finally:
                ci._row_signal_id = orig
            self.assertIsNotNone(ci.check_signal_storm(sig, 744, audit_logs=tmp, live_active_threshold=True))


if __name__ == "__main__":
    unittest.main()
