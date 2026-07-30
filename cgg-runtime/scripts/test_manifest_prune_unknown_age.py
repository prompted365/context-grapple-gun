#!/usr/bin/env python3
"""Tests for manifest-prune unknown-age honesty
(bk-downaudit-observability-field-parity leg 2; ratified ray /review 668).

The contract under guard: a manifest record whose reinforcement tic is NOT
derivable (no volume_history / added_to_manifest_tic / source_tic) must render
`last_reinforced_tic` as UNKNOWN (null + age_unknown marker) — NEVER
fallback=current_tic, which manufactures raw_age_tics=0: fake freshness on the
audit metadata AND a permanently-zero anti-silencing quiet clock (the unowned
silent ray can never re-escalate — silenced forever by absence of evidence).

Escalation-reader semantics for unknown age (decided in-item): on an unowned,
silent, carried/dimmed ray with NO decision anchor, an unmeasurable quiet
window is escalation-ELIGIBLE — anti-silencing wins; absence of age evidence
must never keep a ray dark. Decay under unknown age claims nothing (factor 1.0
— over-surface, never silently dim; the same visible volume the old fallback
produced, so no volume regression, only honest metadata).

Both arms per documented conditional:
  - age DERIVABLE (each priority source) → unchanged decay/quiet behavior;
  - age UNKNOWN → null age + age_unknown, no decay claim;
  - unknown + silent + unowned      → RE-ESCALATES (the defect arm);
  - unknown + silent + OWNED        → no re-escalation (owned carry is a decision);
  - unknown + LOUD                  → no re-escalation (not silent);
  - known-age quiet clock           → both arms unchanged (regression guard);
  - resolved rows still archive through the real file flow.

Run:  python3 -m unittest test_manifest_prune_unknown_age
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "manifest_prune", os.path.join(_HERE, "manifest-prune.py")
)
mp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mp)

TIC = 500


class TestAgeDerivation(unittest.TestCase):
    """_infer_last_reinforced_tic: each priority source, and honest None."""

    def test_volume_history_wins(self):
        rec = {"volume_history": [{"tic": 480}, {"tic": 495}],
               "added_to_manifest_tic": 470, "source_tic": 460}
        self.assertEqual(mp._infer_last_reinforced_tic(rec), 495)

    def test_added_to_manifest_then_source_tic(self):
        self.assertEqual(
            mp._infer_last_reinforced_tic({"added_to_manifest_tic": 470}), 470)
        self.assertEqual(
            mp._infer_last_reinforced_tic({"source_tic": 460}), 460)

    def test_underivable_is_none_never_current_tic(self):
        self.assertIsNone(mp._infer_last_reinforced_tic({}))
        self.assertIsNone(mp._infer_last_reinforced_tic(
            {"volume_history": [], "status": "active", "volume": 35}))


class TestProjectionAgeHonesty(unittest.TestCase):
    """project_signal renders unknown age as null + marker; known age unchanged."""

    def test_known_age_unchanged(self):
        rec = {"signal_id": "s1", "status": "active", "volume": 40,
               "source_tic": TIC - 2}
        proj = mp.project_signal(rec, TIC)
        inputs = proj["_v2_projection_inputs"]
        self.assertEqual(inputs["last_reinforced_tic"], TIC - 2)
        self.assertEqual(inputs["raw_age_tics"], 2)
        self.assertFalse(inputs["age_unknown"])
        # decay 0.9 at age 2 — the measured-quiet claim stands.
        self.assertAlmostEqual(proj["visible_volume"], 40 * 0.9, places=2)

    def test_unknown_age_is_null_with_marker_and_no_decay_claim(self):
        rec = {"signal_id": "s2", "status": "active", "volume": 35}
        proj = mp.project_signal(rec, TIC)
        inputs = proj["_v2_projection_inputs"]
        self.assertIsNone(inputs["last_reinforced_tic"])
        self.assertIsNone(inputs["raw_age_tics"])
        self.assertTrue(inputs["age_unknown"])
        # No decay claim (factor 1.0): same visible volume the old fallback
        # produced — the fix is honest metadata, not a volume change.
        self.assertAlmostEqual(proj["visible_volume"], 35.0, places=2)
        self.assertEqual(proj["structural_status"], "live")


class TestUnknownAgeEscalationSemantics(unittest.TestCase):
    """The escalation reader under unknown age — all three arms."""

    def test_unknown_silent_unowned_reescalates(self):
        # THE DEFECT ARM: old fallback zeroed the quiet clock → silenced forever.
        rec = {"signal_id": "s3", "status": "acknowledged", "volume": 0}
        proj = mp.project_signal(rec, TIC)
        self.assertTrue(proj.get("re_escalation_reminder"),
                        "unknown-age unowned silent ray failed to re-escalate "
                        "(silenced forever by absence of age evidence)")
        self.assertEqual(proj["volume"], mp.REESC_VOLUME)
        self.assertEqual(proj["re_escalated_at_tic"], TIC)
        self.assertEqual(proj["structural_status"], "carried")
        self.assertGreater(proj["heat"], mp.HEAT_FLOOR)

    def test_unknown_silent_owned_does_not_reescalate(self):
        rec = {"signal_id": "s4", "status": "acknowledged", "volume": 0,
               "resolution_action": "drill scheduled"}
        proj = mp.project_signal(rec, TIC)
        self.assertFalse(proj.get("re_escalation_reminder", False))
        self.assertNotIn("volume", proj)  # no re-heat write-through

    def test_unknown_loud_does_not_reescalate(self):
        rec = {"signal_id": "s5", "status": "acknowledged", "volume": 35}
        proj = mp.project_signal(rec, TIC)
        self.assertFalse(proj.get("re_escalation_reminder", False))
        self.assertGreater(proj["heat"], mp.HEAT_FLOOR)

    def test_known_age_quiet_clock_unchanged_both_arms(self):
        # Recent decision anchor → quiet window not met → no re-escalation.
        recent = {"signal_id": "s6", "status": "acknowledged", "volume": 0,
                  "acknowledged_tic": TIC - 2, "source_tic": TIC - 10}
        self.assertFalse(mp.project_signal(recent, TIC)
                         .get("re_escalation_reminder", False))
        # Old decision anchor → quiet window met → re-escalates (sawtooth).
        old = {"signal_id": "s7", "status": "acknowledged", "volume": 0,
               "acknowledged_tic": TIC - 5, "source_tic": TIC - 10}
        proj = mp.project_signal(old, TIC)
        self.assertTrue(proj.get("re_escalation_reminder"))
        self.assertEqual(proj["re_escalated_at_tic"], TIC)


class TestFileFlowPartition(unittest.TestCase):
    """The real file flow still partitions keep/archive with unknown-age rows."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        (Path(self.root) / ".ticzone").write_text("{}\n", encoding="utf-8")
        tic_dir = Path(self.root) / "audit-logs" / "tics"
        tic_dir.mkdir(parents=True)
        (tic_dir / "d.jsonl").write_text(
            json.dumps({"type": "tic", "global_counter_after": TIC}) + "\n",
            encoding="utf-8")
        self.sig_dir = Path(self.root) / "audit-logs" / "signals"
        self.sig_dir.mkdir(parents=True)

    def _write_manifest(self, rows):
        (self.sig_dir / "active-manifest.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def _read(self, name):
        p = self.sig_dir / name
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
                if l.strip()]

    def test_prune_partitions_and_stamps_age_honestly(self):
        self._write_manifest([
            {"signal_id": "keep_known", "status": "active", "volume": 30,
             "source_tic": TIC - 3},
            {"signal_id": "keep_unknown", "status": "active", "volume": 30},
            {"signal_id": "gone", "status": "resolved", "volume": 0,
             "source_tic": TIC - 6},
        ])
        out = subprocess.run(
            [sys.executable, os.path.join(_HERE, "manifest-prune.py"),
             "--zone-root", self.root, "--quiet"],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)

        kept = {r["signal_id"]: r for r in self._read("active-manifest.jsonl")}
        self.assertEqual(set(kept), {"keep_known", "keep_unknown"})
        known = kept["keep_known"]["_v2_projection_inputs"]
        self.assertEqual(known["raw_age_tics"], 3)
        self.assertFalse(known["age_unknown"])
        unknown = kept["keep_unknown"]["_v2_projection_inputs"]
        self.assertIsNone(unknown["raw_age_tics"])
        self.assertTrue(unknown["age_unknown"])

        archived = {r["signal_id"] for r in self._read("resolved-archive.jsonl")}
        self.assertEqual(archived, {"gone"})


if __name__ == "__main__":
    unittest.main()
