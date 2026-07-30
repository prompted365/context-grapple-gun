#!/usr/bin/env python3
"""Tests for observability-FIELD parity on the down-lane manifest writers
(bk-downaudit-observability-field-parity; ratified ray /review 668 —
cgg-ledger#machine-emitter-emit-resolve-symmetry-and-chronological-status-truth
section 3).

The contract under guard: a reaffirm/resolve manifest row must carry
kind / band / volume / max_volume FORWARD FROM THE ORIGINAL SIGNAL. A thin row
becomes the latest-per-id manifest truth on the next collapse, silently dropping
the fields every manifest reader keys on (band counts, volume projection,
/siren loudest, worldview banner) — the reaffirmed WATCH finding goes
acoustically dark at the exact moment it is re-affirmed as standing.

Both arms per conditional:
  - fields PRESENT on the original  → carried forward verbatim;
  - fields ABSENT on the original   → stay absent (carry, never invent);
  - sibling site (named-footgun-sibling discipline): the staleness-rollup HEAL
    write is a resolve-class manifest row with the same thinness — fixed and
    guarded together with the two named sites;
  - end-to-end symptom: after reaffirm + manifest-prune collapse, the projected
    manifest row keeps band + a non-zero visible_volume (the tic-668 defect).

Each case isolates against a TemporaryDirectory (Self-Locating Artifact Test
Isolation KI); every tic is explicit (Temporal Scope Discipline).

Run:  python3 -m unittest test_downaudit_manifest_field_parity
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
    "ladder_audit", os.path.join(_HERE, "ladder-audit.py")
)
la = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(la)

RUNG = "canonical_developer/context-grapple-gun/stage"
KI = "cpr_can_it_eat_dataflow_liveness_predicate_tic405"

PARITY_FIELDS = ("kind", "band", "volume", "max_volume")


def _manifest_rows(root, signal_id=None):
    """Raw manifest rows, in file order (the append surface under test)."""
    p = Path(root) / "audit-logs" / "signals" / "active-manifest.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    if signal_id is not None:
        rows = [r for r in rows if r.get("signal_id") == signal_id]
    return rows


def _seed_tic_ledger(root, counter):
    """Give the zone a tic ledger so count_physical_tics resolves `counter`."""
    tic_dir = Path(root) / "audit-logs" / "tics"
    tic_dir.mkdir(parents=True, exist_ok=True)
    (tic_dir / "2026-07-30.jsonl").write_text(
        json.dumps({"type": "tic", "global_counter_after": counter}) + "\n",
        encoding="utf-8")


class TestEmitManifestRowParity(unittest.TestCase):
    """The emit-side manifest row is the parity REFERENCE — it must itself carry
    the full field set (max_volume was the one gap on the emit row)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def test_emit_manifest_row_carries_all_parity_fields(self):
        res = la.emit_downaudit_finding(
            self.root, RUNG, KI, "hold_in_dissonance", opened_tic=490,
            summary="held tension (test fixture)")
        self.assertTrue(res["written"])
        rows = _manifest_rows(self.root, res["signal_id"])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        for f in PARITY_FIELDS:
            self.assertIn(f, row, f"emit manifest row missing {f}")
        self.assertEqual(row["kind"], "WATCH")
        self.assertEqual(row["band"], "COGNITIVE")
        self.assertEqual(row["volume"], 35)
        self.assertEqual(row["max_volume"], 100)


class TestReaffirmResolveManifestRowParity(unittest.TestCase):
    """The two named sites: reaffirm + resolve manifest rows carry
    kind/band/volume/max_volume forward from the original signal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        res = la.emit_downaudit_finding(
            self.root, RUNG, KI, "hold_in_dissonance", opened_tic=490,
            summary="held tension (test fixture)")
        self.assertTrue(res["written"])
        self.sid = res["signal_id"]

    def test_reaffirm_manifest_row_carries_fields_forward(self):
        res = la.reaffirm_downaudit_finding(
            self.root, self.sid, "hold stands (parity fixture)", retest_tic=508)
        self.assertTrue(res["ok"])
        row = _manifest_rows(self.root, self.sid)[-1]
        self.assertTrue(row.get("reaffirmed"))
        # Carried forward from the ORIGINAL signal (kind WATCH / band COGNITIVE /
        # volume 35 / max_volume 100 — the hold_in_dissonance emit shape).
        self.assertEqual(row.get("kind"), "WATCH")
        self.assertEqual(row.get("band"), "COGNITIVE")
        self.assertEqual(row.get("volume"), 35)
        self.assertEqual(row.get("max_volume"), 100)
        # Lifecycle fields untouched by the carry.
        self.assertEqual(row.get("status"), "active")
        self.assertEqual(row.get("retest_tic"), 508)

    def test_resolve_manifest_row_carries_fields_forward(self):
        res = la.resolve_downaudit_finding(
            self.root, self.sid, review_tic=509, resolved_to="confirmed",
            justification="arena confirmed; tension dissolved (parity fixture)")
        self.assertTrue(res["ok"])
        row = _manifest_rows(self.root, self.sid)[-1]
        self.assertEqual(row.get("status"), "resolved")
        self.assertEqual(row.get("structural_status"), "resolved")
        for f, want in (("kind", "WATCH"), ("band", "COGNITIVE"),
                        ("volume", 35), ("max_volume", 100)):
            self.assertEqual(row.get(f), want,
                             f"resolve manifest row lost {f} (thin-row defect)")

    def test_absent_fields_stay_absent_never_invented(self):
        """Arm B: an original signal missing band/max_volume yields a manifest
        row that carries what exists and invents NOTHING (carry ≠ fabricate)."""
        sid = "sig_ladder_down_audit_finding_ffffffff"
        now_sig = {
            "type": "signal", "id": sid, "signal_id": sid,
            "signal_type": la.DOWNAUDIT_FINDING_SIGNAL_TYPE,
            "kind": "WATCH", "status": "active", "volume": 25,
            # band + max_volume deliberately ABSENT
            "payload": {"rung": RUNG, "ki_id": KI,
                        "verdict": "hold_in_dissonance", "opened_tic": 480},
        }
        sig_dir = Path(self.root) / "audit-logs" / "signals"
        sig_dir.mkdir(parents=True, exist_ok=True)
        with (sig_dir / "2026-07-29.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(now_sig) + "\n")

        res = la.reaffirm_downaudit_finding(
            self.root, sid, "hold stands (thin-original fixture)",
            retest_tic=508)
        self.assertTrue(res["ok"])
        row = _manifest_rows(self.root, sid)[-1]
        self.assertEqual(row.get("kind"), "WATCH")
        self.assertEqual(row.get("volume"), 25)
        self.assertNotIn("band", row)        # absent stays absent
        self.assertNotIn("max_volume", row)  # never invented


class TestStalenessHealSiblingSiteParity(unittest.TestCase):
    """Sibling site (named-footgun-sibling discipline): the staleness-rollup
    HEAL manifest write is a resolve-class row — same parity contract."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        _seed_tic_ledger(self.root, 500)

    def test_heal_manifest_row_carries_fields_forward(self):
        # Emit one rollup (force past the build-and-gate for the fixture),
        # then heal it with a scan bearing zero candidates.
        scan_present = {"current_tic": 500, "candidates": [
            {"signal": "coverage_stale", "target": f"{KI} @ {RUNG}",
             "proposed_next_action": "reaudit"}]}
        first = la.persist_staleness_candidates(
            self.root, scan_present, opened_tic=500, force=True)
        self.assertTrue(first["ran"])
        self.assertEqual(len(first["emitted"]), 1)
        sid = first["emitted"][0]

        scan_healed = {"current_tic": 501, "candidates": []}
        second = la.persist_staleness_candidates(
            self.root, scan_healed, opened_tic=501, force=True)
        self.assertTrue(second["ran"])
        self.assertEqual(second["resolved"], [sid])

        row = _manifest_rows(self.root, sid)[-1]
        self.assertEqual(row.get("status"), "resolved")
        for f, want in (("kind", "WATCH"), ("band", "COGNITIVE"),
                        ("volume", la.STALENESS_CANDIDATE_VOLUME),
                        ("max_volume", 100)):
            self.assertEqual(row.get(f), want,
                             f"heal manifest row lost {f} (sibling-site defect)")


class TestEndToEndManifestCollapseKeepsObservability(unittest.TestCase):
    """The tic-668 symptom, end-to-end: after a reaffirm, the manifest-prune
    latest-per-id collapse must NOT project the finding band-less/volume-less
    (acoustically dark). Runs the real manifest-prune file flow."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        (Path(self.root) / ".ticzone").write_text("{}\n", encoding="utf-8")
        _seed_tic_ledger(self.root, 500)

    def test_reaffirmed_finding_stays_loud_after_prune(self):
        res = la.emit_downaudit_finding(
            self.root, RUNG, KI, "hold_in_dissonance", opened_tic=490)
        sid = res["signal_id"]
        self.assertTrue(la.reaffirm_downaudit_finding(
            self.root, sid, "hold stands", retest_tic=498)["ok"])

        out = subprocess.run(
            [sys.executable, os.path.join(_HERE, "manifest-prune.py"),
             "--zone-root", self.root, "--quiet"],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)

        rows = _manifest_rows(self.root, sid)
        self.assertEqual(len(rows), 1)  # latest-per-id collapsed
        row = rows[0]
        self.assertEqual(row.get("band"), "COGNITIVE")
        self.assertEqual(row.get("kind"), "WATCH")
        self.assertGreater(float(row.get("visible_volume") or 0), 0,
                           "reaffirmed finding went acoustically dark")
        self.assertTrue(la.is_active_ray(row))


if __name__ == "__main__":
    unittest.main()
