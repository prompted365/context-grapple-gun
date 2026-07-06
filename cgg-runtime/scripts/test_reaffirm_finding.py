#!/usr/bin/env python3
"""Tests for `ladder-audit.py reaffirm-finding` — the THIRD leg of emit/resolve
symmetry (re-affirm-on-retest; tic-570 gap, bk-downlane-retest-write-path).

Guards the third-leg contract:
  - a re-test whose conclusion is "the finding stands" lands on the EXISTING
    active finding (same signal_id, latest-per-id append — NO duplicate id, NO
    terminalization), refreshing last_retested_tic / retest_count so the D4
    held-band STALE flag clears;
  - the D4 center-hold survives: the staleness clock RE-ANCHORS (it does not
    immortalize — a re-affirmed hold goes stale again after the window),
    tics_held never resets, retest_count accumulates, receipt is mandatory;
  - a terminal finding REFUSES re-affirmation (a recurred condition is a fresh
    emit, not a re-affirm);
  - emit-finding's dedup-refusal is UNCHANGED (by design — the third leg goes
    AROUND it, not through it; tic-570 purpose-first assessment).

Each case isolates against a TemporaryDirectory — nothing touches the real
canonical zone (Self-Locating Artifact Test Isolation KI), and every tic is
passed explicitly (Temporal Scope Discipline).

Run:  python3 -m unittest test_reaffirm_finding   (from cgg-runtime/scripts/)
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "ladder_audit", os.path.join(_HERE, "ladder-audit.py")
)
la = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(la)

RUNG = "canonical_developer/context-grapple-gun/stage"
KI = "cpr_can_it_eat_dataflow_liveness_predicate_tic405"


def _daily_rows(root):
    """All raw signal rows from the daily files (manifest excluded)."""
    sig_dir = Path(root) / "audit-logs" / "signals"
    rows = []
    if not sig_dir.is_dir():
        return rows
    for f in sorted(sig_dir.glob("*.jsonl")):
        if f.name == "active-manifest.jsonl":
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _all_files(root):
    return sorted(str(p) for p in Path(root).rglob("*") if p.is_file())


class TestReaffirmFinding(unittest.TestCase):
    """Third-leg landing: refresh retest state, no duplicate, never terminal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        res = la.emit_downaudit_finding(
            self.root, RUNG, KI, "hold_in_dissonance", opened_tic=490,
            summary="held tension (test fixture)")
        self.assertTrue(res["written"])
        self.sid = res["signal_id"]

    def _proj(self, tic):
        return la.list_downaudit_findings(self.root, current_tic=tic)

    def test_reaffirm_refreshes_retest_state_without_duplicate(self):
        # Before: held 20 tics (>= DISSONANCE_STALE_TICS=8) → STALE for re-test.
        before = self._proj(510)
        self.assertEqual(len(before["held_band"]), 1)
        self.assertEqual(len(before["stale_held_for_retest"]), 1)

        res = la.reaffirm_downaudit_finding(
            self.root, self.sid,
            "re-test at tic 508 verified the tension byte-on-disk; hold stands",
            retest_tic=508,
            artifact="audit-logs/governance/downaudit-retest-tic570.md")
        self.assertTrue(res["ok"])
        self.assertEqual(res["retest_tic"], 508)
        self.assertEqual(res["retest_count"], 1)
        self.assertEqual(res["verdict"], "hold_in_dissonance")

        # No duplicate finding: latest-per-id still projects exactly ONE...
        latest = la.load_downaudit_findings(self.root)
        self.assertEqual(len(latest), 1)
        sig = latest[0]
        # ...via an APPENDED same-id row (2 raw rows, both this signal_id).
        rows = [r for r in _daily_rows(self.root)
                if (r.get("signal_id") or r.get("id")) == self.sid]
        self.assertEqual(len(rows), 2)

        # Never terminalized: still active, verdict unchanged, receipt carried.
        self.assertTrue(la.is_active_ray(sig))
        self.assertEqual(sig["payload"]["verdict"], "hold_in_dissonance")
        self.assertEqual(sig["payload"]["last_retested_tic"], 508)
        self.assertEqual(sig["payload"]["retest_count"], 1)
        self.assertEqual(sig["payload"]["last_retest"]["disposition"], "reaffirmed")
        self.assertIn("justification", sig["payload"]["last_retest"])

        # After: STALE flag cleared (anchor = re-test tic 508: 2t < 8), the hold
        # stays in the held band, and tics_held keeps the honest total age.
        after = self._proj(510)
        self.assertEqual(len(after["held_band"]), 1)
        h = after["held_band"][0]
        self.assertFalse(h["stale_for_retest"])
        self.assertEqual(after["stale_held_for_retest"], [])
        self.assertEqual(h["tics_since_retest"], 2)
        self.assertEqual(h["tics_held"], 20)          # never resets (D4 pressure)
        self.assertEqual(h["last_retested_tic"], 508)
        self.assertEqual(h["retest_count"], 1)
        self.assertEqual(after["active_findings"], 1)
        self.assertEqual(after["terminal_findings"], 0)

    def test_staleness_reanchors_it_does_not_immortalize(self):
        la.reaffirm_downaudit_finding(
            self.root, self.sid, "hold stands", retest_tic=508)
        # 12 tics after the re-test (>= 8) → stale AGAIN. The clock re-anchors;
        # a re-affirm is a snooze-until-window, never a permanent silence.
        later = self._proj(520)
        h = later["held_band"][0]
        self.assertTrue(h["stale_for_retest"])
        self.assertEqual(h["tics_since_retest"], 12)
        self.assertEqual(h["tics_held"], 30)

    def test_second_reaffirm_accumulates_visible_count(self):
        la.reaffirm_downaudit_finding(
            self.root, self.sid, "hold stands (first)", retest_tic=500)
        res = la.reaffirm_downaudit_finding(
            self.root, self.sid, "hold stands (second)", retest_tic=512)
        self.assertEqual(res["retest_count"], 2)
        latest = la.load_downaudit_findings(self.root)
        self.assertEqual(len(latest), 1)               # still exactly one finding
        self.assertEqual(latest[0]["payload"]["retest_count"], 2)
        self.assertEqual(latest[0]["payload"]["last_retested_tic"], 512)

    def test_reaffirm_on_terminal_finding_refuses(self):
        resolved = la.resolve_downaudit_finding(
            self.root, self.sid, review_tic=509, resolved_to="confirmed",
            justification="arena confirmed; tension dissolved")
        self.assertTrue(resolved["ok"])
        rows_before = len(_daily_rows(self.root))
        res = la.reaffirm_downaudit_finding(
            self.root, self.sid, "attempting to re-affirm a closed finding",
            retest_tic=511)
        self.assertFalse(res["ok"])
        self.assertIn("terminal", res["error"])
        self.assertIn("emit-finding", res["error"])    # recurrence → fresh emit
        self.assertEqual(len(_daily_rows(self.root)), rows_before)  # refusal writes nothing

    def test_reaffirm_unknown_signal_refuses(self):
        res = la.reaffirm_downaudit_finding(
            self.root, "sig_ladder_down_audit_finding_00000000", "n/a",
            retest_tic=510)
        self.assertFalse(res["ok"])
        self.assertIn("no finding signal", res["error"])

    def test_reaffirm_requires_justification_receipt(self):
        with self.assertRaises(ValueError):
            la.reaffirm_downaudit_finding(self.root, self.sid, "", retest_tic=510)

    def test_dry_run_writes_nothing(self):
        before = _all_files(self.root)
        res = la.reaffirm_downaudit_finding(
            self.root, self.sid, "hold stands (preview)", retest_tic=508,
            dry_run=True)
        self.assertTrue(res["ok"])
        self.assertTrue(res["dry_run"])
        self.assertEqual(_all_files(self.root), before)
        # projection unchanged: still stale, no retest state landed
        h = self._proj(510)["held_band"][0]
        self.assertTrue(h["stale_for_retest"])
        self.assertNotIn("last_retested_tic", h)

    def test_coverage_index_treats_reaffirm_as_fresh_audit(self):
        idx = la._downlane_coverage_index(self.root)
        self.assertEqual(idx[(RUNG, KI)]["opened_tic"], 490)
        la.reaffirm_downaudit_finding(
            self.root, self.sid, "hold stands", retest_tic=508)
        idx = la._downlane_coverage_index(self.root)
        # the re-test IS the latest audit event of the pair — coverage freshness
        # keys on it (same third-leg gap, coverage-side: no eternal re-dispatch).
        self.assertEqual(idx[(RUNG, KI)]["opened_tic"], 508)


class TestEmitDedupUnchanged(unittest.TestCase):
    """The emit-finding dedup-refusal is BY DESIGN (D4 pressure; tic-570
    purpose-first assessment) — the third leg goes AROUND it, not through it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        res = la.emit_downaudit_finding(
            self.root, RUNG, KI, "hold_in_dissonance", opened_tic=490)
        self.assertTrue(res["written"])
        self.sid = res["signal_id"]

    def test_emit_dedup_refusal_unchanged_before_and_after_reaffirm(self):
        # Re-emission of the same (rung, ki, verdict) dedup-refuses — unchanged.
        again = la.emit_downaudit_finding(
            self.root, RUNG, KI, "hold_in_dissonance", opened_tic=510)
        self.assertFalse(again["written"])
        self.assertTrue(again["deduplicated"])
        self.assertEqual(again["signal_id"], self.sid)

        # A reaffirm lands AROUND the dedup (same id, append leg)...
        res = la.reaffirm_downaudit_finding(
            self.root, self.sid, "hold stands", retest_tic=510)
        self.assertTrue(res["ok"])

        # ...and emit STILL dedup-refuses afterwards (nothing weakened).
        after = la.emit_downaudit_finding(
            self.root, RUNG, KI, "hold_in_dissonance", opened_tic=511)
        self.assertFalse(after["written"])
        self.assertTrue(after["deduplicated"])

    def test_verdict_flip_still_emits_as_new_condition(self):
        # A verdict flip on the same (rung, ki) is a genuinely NEW finding
        # (condition-stable id includes the verdict) — unchanged by the third leg.
        flip = la.emit_downaudit_finding(
            self.root, RUNG, KI, "damaging", opened_tic=512)
        self.assertTrue(flip["written"])
        self.assertNotEqual(flip["signal_id"], self.sid)


if __name__ == "__main__":
    unittest.main()
