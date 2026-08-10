#!/usr/bin/env python3
"""Tests for the early-suppression-gate self-report in pattern_miner.py
(bk-pattern-miner-suppression-zero-unreported, tic 695 — filed from the
/review-695 MERGE verdict on cpr_mogul_pattern_mining_cb95782a31ca; doctrine
landed the same tic as a refinement ray on
cgg-ledger#extractor-anomaly-self-reporting).

The defect under cure: mine_patterns() carries TWO suppression gates but only
the late one self-reports. The late gate (emit_pattern_envelopes ~501) prints
its dedup-at-write skipped_duplicate count to stderr; the early gate
(`if existing and new_count <= prev_count: continue`, ~257) drops DETECTED
recurrences silently — so a SUPPRESSION-zero is indistinguishable from a
DETECTION-zero at the reader (measured live t692: 57 detected / 57 suppressed
/ reader saw nothing, consistent with ~6 weeks of empty daily emissions).

Contract teeth, each with a fixture arm (both arms per documented conditional):

  1. suppression fires   -> stderr carries an explicit early-gate suppression
                            self-report naming the count and the axis (the
                            zero is suppression-aware, not pattern absence)
  2. fresh pattern       -> NO suppression line (honest-empty arm: nothing
                            suppressed, nothing reported)
  3. detection-zero      -> NO suppression line (a genuine nothing-found run
                            stays unlabeled — the report must never blur
                            detection-zero into suppression-zero)

Run:  python3 -m unittest test_pattern_miner_suppression_reporting
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_MINER = os.path.join(_HERE, "pattern_miner.py")

_spec = importlib.util.spec_from_file_location("pattern_miner_under_test", _MINER)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Two CPRs whose lessons share >0.3 Jaccard word overlap (recurrence pair).
_LESSON_A = (
    "the widget frobnicator must always validate its input schema before "
    "emitting downstream envelope records to the queue surface"
)
_LESSON_B = (
    "the widget frobnicator must always validate its input schema before "
    "writing downstream envelope entries to the ledger surface"
)


def _seed_zone(zone: Path, queue_rows, pattern_rows=()):
    (zone / "audit-logs" / "cprs").mkdir(parents=True)
    (zone / "audit-logs" / "signals").mkdir(parents=True)
    pdir = zone / "audit-logs" / "patterns"
    pdir.mkdir(parents=True)
    qp = zone / "audit-logs" / "cprs" / "queue.jsonl"
    qp.write_text(
        "".join(json.dumps(r) + "\n" for r in queue_rows), encoding="utf-8"
    )
    if pattern_rows:
        (pdir / "2026-01-01.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in pattern_rows),
            encoding="utf-8",
        )


def _cpr(cid, lesson, subsystem="widgets"):
    return {"type": "cpr", "id": cid, "lesson": lesson, "subsystem": subsystem,
            "birth_tic": 690, "status": "extracted"}


def _run_miner(zone: Path):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        patterns, envelopes = _mod.mine_patterns(str(zone), dry_run=True)
    return patterns, envelopes, err.getvalue()


def _existing_pattern_for(cpr, count):
    """A pre-existing pattern record matching the miner's deterministic id."""
    import hashlib
    h = hashlib.sha256(
        f"pattern:{cpr['subsystem']}:{cpr['lesson'][:100]}".encode()
    ).hexdigest()[:16]
    return {"type": "pattern_recurrence", "id": f"pat_{h}",
            "observation_count": count, "first_observed_tic": 600,
            "status": "observed"}


class EarlyGateSuppressionReport(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.zone = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    # 1 — suppression fires: existing pattern already at the recomputed count
    def test_suppression_self_reports_on_stderr(self):
        a, b = _cpr("cpr_aaa", _LESSON_A), _cpr("cpr_bbb", _LESSON_B)
        # Recomputed count per source CPR = 1 similar + 1 self = 2; existing
        # records already at 2 -> early gate suppresses BOTH detections.
        _seed_zone(
            self.zone, [a, b],
            [_existing_pattern_for(a, 2), _existing_pattern_for(b, 2)],
        )
        patterns, _, err = _run_miner(self.zone)
        self.assertEqual(patterns, [])          # the zero the reader sees
        self.assertIn("suppress", err.lower())  # ...is now labeled
        self.assertIn("2", err)                 # with its magnitude
        self.assertNotIn("detection-zero", err.lower().replace(
            "not detection-zero", ""))          # and named as NOT absence

    # 2 — fresh pattern: nothing suppressed, nothing reported (honest-empty)
    def test_fresh_pattern_no_suppression_line(self):
        _seed_zone(self.zone, [_cpr("cpr_aaa", _LESSON_A),
                               _cpr("cpr_bbb", _LESSON_B)])
        patterns, _, err = _run_miner(self.zone)
        self.assertTrue(patterns)               # both mint fresh
        self.assertNotIn("suppress", err.lower())

    # 3 — detection-zero: dissimilar lessons, no recurrence detected at all
    def test_detection_zero_stays_unlabeled(self):
        _seed_zone(self.zone, [
            _cpr("cpr_aaa", "alpha bravo charlie delta echo foxtrot golf"),
            _cpr("cpr_bbb", "hotel india juliet kilo lima mike november"),
        ])
        patterns, _, err = _run_miner(self.zone)
        self.assertEqual(patterns, [])
        self.assertNotIn("suppress", err.lower())


if __name__ == "__main__":
    unittest.main()
