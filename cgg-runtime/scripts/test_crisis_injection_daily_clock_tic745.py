#!/usr/bin/env python3
"""F-745 — two date clocks on one lane. Every signal EMITTER names the daily file by the
UTC calendar date; crisis-injection.py READ it by the local date (date.today()), so for
every hour between UTC midnight and local midnight Check 1 and raw_emissions_today read
a stale file. Live instance at the tic-745 boot (02:46Z = 22:46 EDT, 2026-08-27 local /
2026-08-28 UTC): 61 rows in the local-dated file vs the 10 fresh rows — the four tic-745
rows among them — in the UTC-dated file. The mandate-history file stays LOCAL by design
(both of its writers are local); the split is disclosed, not unified.

RED-THEN-GREEN + NEGATIVE CONTROL spine. Every case in its own TemporaryDirectory.
"""
import importlib.util, json, os, tempfile, unittest, pathlib, datetime

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("crisis_injection", HERE / "crisis-injection.py")
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)

EDT = datetime.timezone(datetime.timedelta(hours=-4))
# 22:00 EDT on 2026-08-27 == 02:00Z on 2026-08-28: the two calendars DISAGREE at this instant.
SPLIT = datetime.datetime(2026, 8, 27, 22, 0, tzinfo=EDT)
# 12:00 EDT == 16:00Z, same calendar date on both clocks.
SAME = datetime.datetime(2026, 8, 27, 12, 0, tzinfo=EDT)


def _mk(tmp, ids):
    sig = os.path.join(tmp, "signals"); os.makedirs(sig, exist_ok=True)
    with open(os.path.join(sig, "active-manifest.jsonl"), "w") as f:
        for i in ids:
            f.write(json.dumps({"signal_id": i, "status": "active"}) + "\n")
    os.makedirs(os.path.join(tmp, "sentinel"), exist_ok=True)
    with open(os.path.join(tmp, "sentinel", "crisis-injection-shadow.jsonl"), "w") as f:
        f.write(json.dumps({"type": "crisis_injection_shadow", "check": "active_signal_count",
                            "tic": 744, "active_count": len(ids), "active_ids": sorted(ids),
                            "mode": "live"}) + "\n")
    return sig


def _daily(sig, day, rows):
    with open(os.path.join(sig, f"{day}.jsonl"), "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")


class TestUtcToday(unittest.TestCase):
    def test_split_instant_utc_date_differs_from_local_calendar(self):
        self.assertEqual(ci._utc_today(SPLIT), "2026-08-28")
        self.assertEqual(SPLIT.date().isoformat(), "2026-08-27")  # the pre-745 read at this instant
    def test_same_instant_agrees(self):
        self.assertEqual(ci._utc_today(SAME), "2026-08-27")
    def test_naive_input_is_treated_as_utc(self):
        self.assertEqual(ci._utc_today(datetime.datetime(2026, 8, 28, 2, 0)), "2026-08-28")
    def test_default_is_now_utc(self):
        self.assertEqual(ci._utc_today(), datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    def test_history_file_stays_local_by_design(self):
        self.assertEqual(ci._local_today(), datetime.date.today().isoformat())


class TestRawEmissionsFollowTheWritersClock(unittest.TestCase):
    def test_reads_the_utc_dated_file_at_the_split_instant(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, ["x"])
            _daily(sig, "2026-08-27", [{"type": "signal", "signal_id": "old"}] * 3)   # local-dated (stale)
            _daily(sig, "2026-08-28", [{"type": "signal", "signal_id": "new"}] * 1)   # UTC-dated (live)
            self.assertEqual(ci._raw_emissions_today(sig, SPLIT), 1)
    def test_negative_control_reverting_to_the_local_read_counts_the_stale_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, ["x"])
            _daily(sig, "2026-08-27", [{"type": "signal", "signal_id": "old"}] * 3)
            _daily(sig, "2026-08-28", [{"type": "signal", "signal_id": "new"}] * 1)
            orig = ci._utc_today
            ci._utc_today = lambda now=None: (now or SPLIT).date().isoformat()   # the pre-745 read
            try:
                self.assertEqual(ci._raw_emissions_today(sig, SPLIT), 3)
            finally:
                ci._utc_today = orig
            self.assertEqual(ci._raw_emissions_today(sig, SPLIT), 1)


class TestCheck1BlindWindow(unittest.TestCase):
    def test_runaway_in_the_utc_dated_file_is_seen_at_the_split_instant(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, ["x"])
            _daily(sig, "2026-08-28", [{"type": "signal", "signal_id": "sig_runaway"}] * 51)
            out = ci.check_signal_storm(sig, 745, audit_logs=tmp, live_active_threshold=True, now=SPLIT)
            self.assertIsNotNone(out); self.assertIn("sig_runaway", out)
    def test_the_same_runaway_written_only_to_the_local_dated_file_is_the_stale_file(self):
        # The emitters never write there at this instant; a reader that DID see it would be
        # reading yesterday's file — the tic-745 shape (raw_emissions_today=61 from 08-27).
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, ["x"])
            _daily(sig, "2026-08-27", [{"type": "signal", "signal_id": "sig_runaway"}] * 51)
            self.assertIsNone(ci.check_signal_storm(sig, 745, audit_logs=tmp, live_active_threshold=True, now=SPLIT))
    def test_shadow_row_raw_emissions_is_the_utc_file_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, ["x"])
            _daily(sig, "2026-08-27", [{"type": "signal", "signal_id": "old"}] * 61)
            _daily(sig, "2026-08-28", [{"type": "signal", "signal_id": "new"}] * 10)
            ci.check_signal_storm(sig, 745, audit_logs=tmp, live_active_threshold=True, now=SPLIT)
            rows = [json.loads(l) for l in open(os.path.join(tmp, "sentinel", "crisis-injection-shadow.jsonl"))]
            self.assertEqual(rows[-1]["raw_emissions_today"], 10)


if __name__ == "__main__":
    unittest.main()
