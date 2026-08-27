#!/usr/bin/env python3
"""Fixtures for lib/atomic_append.manifest_row_from_signal — the DATE ANCHOR
(F-742-C5, ruled /review 742 Q7, Architect-ratified, recommended verbatim).

THE DEFECT: an ingested manifest row with no tic anchor projects as age_unknown ->
structural_status live and NEVER decays under manifest-prune; the two trusting
emitters carry no tic (biome-engine's federation_tic is 0 by design), so
`source_tic` is absent and 61 rows would land permanently live.

THE CURE: stamp `added_to_manifest_tic` from the canonical tic ledger beside the
signals dir (manifest-prune's priority-2 anchor) — ABSENT when the ledger is
unreadable, never manufactured.

Spine: RED (no ledger -> no anchor, and manifest-prune._infer_last_reinforced_tic
returns None on the row), GREEN (ledger present -> anchor == max counted tic and the
projector's inference reads it), IGNORED-ROWS arm (count_mode ignored rows do not
count), NEGATIVE CONTROL (revert the stamp in place -> the anchor disappears and the
projector reads None again). Every case in its own TemporaryDirectory.
"""
import importlib.util, json, os, pathlib, tempfile, unittest, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lib import atomic_append as aa  # noqa: E402
spec = importlib.util.spec_from_file_location("manifest_prune", HERE / "manifest-prune.py")
mp = importlib.util.module_from_spec(spec); spec.loader.exec_module(mp)

SIG = {"signal_id": "biome.health_degraded_deadbeef", "band": "COGNITIVE", "type": "health_degraded",
       "source": "biome_simulation", "payload": {"summary": "x"}}

def _audit(tmp, tics=None):
    al = os.path.join(tmp, "audit-logs"); sig = os.path.join(al, "signals"); os.makedirs(sig)
    if tics is not None:
        td = os.path.join(al, "tics"); os.makedirs(td)
        with open(os.path.join(td, "2026-08-27.jsonl"), "w") as f:
            for row in tics: f.write(json.dumps(row) + "\n")
    return os.path.join(sig, "2026-08-27.jsonl")

class TestRedNoLedgerNoAnchor(unittest.TestCase):
    def test_absent_when_no_tics_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _audit(tmp)
            row = aa.manifest_row_from_signal(SIG, target, SIG["signal_id"])
            self.assertNotIn("added_to_manifest_tic", row)
            self.assertIsNone(mp._infer_last_reinforced_tic(row))

class TestGreenLedgerAnchors(unittest.TestCase):
    def test_anchor_is_max_counted_tic_and_projector_reads_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _audit(tmp, [{"type": "tic", "global_counter_after": 741},
                                  {"type": "tic", "global_counter_after": 742},
                                  {"type": "note", "global_counter_after": 999}])
            row = aa.manifest_row_from_signal(SIG, target, SIG["signal_id"])
            self.assertEqual(row["added_to_manifest_tic"], 742)
            self.assertEqual(mp._infer_last_reinforced_tic(row), 742)
    def test_ignored_count_mode_rows_do_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _audit(tmp, [{"type": "tic", "global_counter_after": 700},
                                  {"type": "tic", "global_counter_after": 900, "count_mode": "ignored"}])
            row = aa.manifest_row_from_signal(SIG, target, SIG["signal_id"])
            self.assertEqual(row["added_to_manifest_tic"], 700)
    def test_source_tic_outranked_by_volume_history_but_added_tic_outranks_source_tic(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _audit(tmp, [{"type": "tic", "global_counter_after": 742}])
            row = aa.manifest_row_from_signal({**SIG, "source_tic": 700}, target, SIG["signal_id"])
            self.assertEqual(row["source_tic"], 700)
            self.assertEqual(mp._infer_last_reinforced_tic(row), 742)   # added_to_manifest_tic wins
    def test_end_to_end_ingest_lands_dated_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _audit(tmp, [{"type": "tic", "global_counter_after": 742}])
            manifest = os.path.join(os.path.dirname(target), "active-manifest.jsonl")
            self.assertTrue(aa.dedup_signal_append(target, dict(SIG), manifest_path=manifest, ingest_manifest=True))
            rows = [json.loads(l) for l in open(manifest)]
            self.assertEqual(len(rows), 1); self.assertEqual(rows[0]["added_to_manifest_tic"], 742)

class TestNegativeControlStampIsLoadBearing(unittest.TestCase):
    def test_reverting_the_ledger_read_removes_the_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _audit(tmp, [{"type": "tic", "global_counter_after": 742}])
            self.assertEqual(aa.manifest_row_from_signal(SIG, target, SIG["signal_id"])["added_to_manifest_tic"], 742)
            orig = aa._current_canonical_tic
            aa._current_canonical_tic = lambda signals_dir: None   # the pre-cure world: no anchor
            try:
                row = aa.manifest_row_from_signal(SIG, target, SIG["signal_id"])
                self.assertNotIn("added_to_manifest_tic", row)
                self.assertIsNone(mp._infer_last_reinforced_tic(row))
            finally:
                aa._current_canonical_tic = orig
            self.assertEqual(aa.manifest_row_from_signal(SIG, target, SIG["signal_id"])["added_to_manifest_tic"], 742)

if __name__ == "__main__":
    unittest.main(verbosity=1)
