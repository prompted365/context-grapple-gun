#!/usr/bin/env python3
"""Fixtures for crisis-injection.py — the manifest key read + SHADOW mode
(F-742-C3 HIGH, ruled /review 742 Q5, Architect-ratified, recommended verbatim).

THE DEFECT: `_active_manifest_count` keyed `d.get("id")` while every manifest row
carries `signal_id` (0/56 rows carried `id` at tic 742) — the authoritative ACTIVE
count read 0 over 54 rows since the manifold was born: a dead detector whose >10
threshold was never exercised.

THE RULING: fix the read (`signal_id` primary, `id` fallback) AND gate the
injection behind detect+audit SHADOW mode — record what WOULD be injected, inject
nothing — until the crisis-steward seat re-baselines the threshold.

RED-THEN-GREEN + NEGATIVE CONTROL spine (house convention,
test_inbox_reconcile_none_overwrite.py): RED reproduces the old read inline and
proves it counts 0; GREEN proves the cured read counts the rows; SHADOW proves no
stdout injection + a shadow row; LIVE-FLAG proves the injection text returns only
under --live-active-threshold; NC reverts the read in place and proves the zero
returns. Every case in its own TemporaryDirectory; nothing touches any real
audit-logs surface.
"""
import importlib.util, io, json, os, sys, tempfile, unittest, contextlib, pathlib

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("crisis_injection", HERE / "crisis-injection.py")
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)

ROWS = [
    {"signal_id": "sig_a", "status": "active", "kind": "TENSION"},
    {"signal_id": "sig_b", "status": "acknowledged"},
    {"signal_id": "sig_c", "status": "resolved"},
    {"signal_id": "sig_a", "status": "active"},          # latest-per-id dup
    {"id": "legacy_d", "status": "active"},               # legacy id-keyed row
]

def _mk(tmp, rows=ROWS):
    sig = os.path.join(tmp, "signals"); os.makedirs(sig, exist_ok=True)
    with open(os.path.join(sig, "active-manifest.jsonl"), "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    return sig

def _old_read(manifest):
    latest = {}
    for line in open(manifest):
        d = json.loads(line); sid = d.get("id", "")
        if sid: latest[sid] = d
    return sum(1 for d in latest.values() if d.get("status") in {"active", "acknowledged", "working"})


class TestRedOldReadCountsZero(unittest.TestCase):
    def test_old_id_read_sees_only_legacy_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp)
            self.assertEqual(_old_read(os.path.join(sig, "active-manifest.jsonl")), 1)
    def test_old_id_read_is_zero_on_signal_id_only_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, [r for r in ROWS if "signal_id" in r])
            self.assertEqual(_old_read(os.path.join(sig, "active-manifest.jsonl")), 0)


class TestGreenCuredRead(unittest.TestCase):
    def test_counts_signal_id_and_legacy_rows_latest_per_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp)
            self.assertEqual(ci._active_manifest_count(sig), 3)   # a, b, legacy_d
            self.assertEqual(ci._active_manifest_ids(sig), ["legacy_d", "sig_a", "sig_b"])
    def test_none_when_manifest_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "signals"))
            self.assertIsNone(ci._active_manifest_count(os.path.join(tmp, "signals")))


class TestShadowMode(unittest.TestCase):
    """Rewritten at tic 744 under the crisis-steward's arrival predicate (/review 744 Q4):
    ACTIVE_THRESHOLD=10 is retired, so the size-based expectations here were replaced
    by the same INTENT under the ruled shape — shadow records, live injects, fail-soft."""
    def _many(self, tmp, n=12, prior=None):
        sig = _mk(tmp, [{"signal_id": f"s{i}", "status": "active"} for i in range(n)])
        if prior is not None:
            os.makedirs(os.path.join(tmp, "sentinel"), exist_ok=True)
            with open(os.path.join(tmp, "sentinel", "crisis-injection-shadow.jsonl"), "w") as f:
                f.write(json.dumps({"type": "crisis_injection_shadow", "check": "active_signal_count",
                                    "tic": 741, "active_count": len(prior), "threshold": 10,
                                    "active_ids": sorted(prior), "mode": "shadow"}) + "\n")
        return sig
    def test_default_is_shadow_no_injection_but_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = self._many(tmp, prior=[])            # 12 new non-campaign arrivals => A1 would trip
            out = ci.check_signal_storm(sig, 742, audit_logs=tmp)
            self.assertIsNone(out)
            sink = os.path.join(tmp, "sentinel", "crisis-injection-shadow.jsonl")
            self.assertTrue(os.path.isfile(sink))
            rec = json.loads(open(sink).read().strip().splitlines()[-1])
            self.assertEqual(rec["active_count"], 12)
            self.assertEqual(rec["thresholds"]["A1_non_campaign_arrival"], ci.ARRIVAL_NON_CAMPAIGN)
            self.assertTrue(rec["would_inject"]); self.assertFalse(rec["injected"])
            self.assertEqual(rec["mode"], "shadow"); self.assertEqual(rec["arm"], "A1_non_campaign_arrival")
            self.assertEqual(len(rec["active_ids"]), 12)
    def test_no_trip_still_writes_a_row(self):
        # tic 744: the lane records EVERY evaluation (it is the predicate's state store);
        # the pre-744 expectation "below threshold writes nothing" is retired with the constant.
        with tempfile.TemporaryDirectory() as tmp:
            sig = self._many(tmp, n=5)                 # no base => delta arms skipped; 5 < 90
            self.assertIsNone(ci.check_signal_storm(sig, 742, audit_logs=tmp))
            sink = os.path.join(tmp, "sentinel", "crisis-injection-shadow.jsonl")
            rec = json.loads(open(sink).read().strip().splitlines()[-1])
            self.assertFalse(rec["tripped"]); self.assertFalse(rec["would_inject"])
            self.assertIsNone(rec["prior_observation_tic"])
    def test_live_flag_injects(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = self._many(tmp, prior=[])
            out = ci.check_signal_storm(sig, 742, audit_logs=tmp, live_active_threshold=True)
            self.assertIsNotNone(out); self.assertIn("A1_non_campaign_arrival", out)
            self.assertIn("12 new active ids since tic 741", out)
            sink = os.path.join(tmp, "sentinel", "crisis-injection-shadow.jsonl")
            rec = json.loads(open(sink).read().strip().splitlines()[-1])
            self.assertTrue(rec["injected"]); self.assertEqual(rec["mode"], "live")   # the lane keeps recording after the flip
    def test_shadow_is_fail_soft_without_audit_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = self._many(tmp)
            self.assertIsNone(ci.check_signal_storm(sig, 742, audit_logs=None))


class TestNegativeControlCureIsLoadBearing(unittest.TestCase):
    def test_reverting_the_read_restores_the_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            sig = _mk(tmp, [r for r in ROWS if "signal_id" in r])
            self.assertEqual(ci._active_manifest_count(sig), 2)
            orig = ci._active_manifest_count
            def reverted(signal_dir):
                return _old_read(os.path.join(signal_dir, "active-manifest.jsonl"))
            ci._active_manifest_count = reverted
            try:
                self.assertEqual(ci._active_manifest_count(sig), 0)  # the dead detector returns
            finally:
                ci._active_manifest_count = orig
            self.assertEqual(ci._active_manifest_count(sig), 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
