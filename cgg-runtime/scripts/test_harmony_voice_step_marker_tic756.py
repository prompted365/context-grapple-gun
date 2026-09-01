#!/usr/bin/env python3
"""test_harmony_voice_step_marker_tic756.py — the PRODUCER-LIVENESS face of the
presence-observation guard (/review 756 Q1, cpr_mogul_harmony_invoke_a5db1643a492
PROMOTED as a refinement ray; both consumers ruled — this is the producer half's
marker plus the reader's classifier).

The lived defect (tic 753): the mandate consumer read disposition-tic-753.json while
harmony-voice.py (PID 28910) was still running — a structurally valid packet with NO
voice block, indistinguishable from a failed voice step by shape alone; only a process
probe told the two absences apart. The cure: the invoker stamps voice_step {running}
before the amender and {done|failed, exit_code} after, and the reader types an absence
from the marker, never from shape.

Eight tests: running→amender_running · failed→amender_failed · done-without-voice is a
producer defect · voice present→none regardless of marker · no marker→probe liveness ·
the marker is additive (no other key touched) · started_at survives running→done ·
the CLI round-trips through a real file atomically.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("hvm_t756", _HERE / "harmony-voice-marker.py")
hvm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hvm)

_BASE = {"packetId": "pkt-1", "disposition": {"stance": "x"}, "meaningState": "strained", "rays": []}


class MarkerTests(unittest.TestCase):
    def test_running_reads_amender_running(self):
        d = hvm.stamp(dict(_BASE), "running", now="2026-08-31T00:00:00+00:00")
        c = hvm.classify(d)
        self.assertEqual(c["absence_type"], "amender_running")
        self.assertFalse(c["voice_present"])
        self.assertEqual(c["typed_from"], "marker")

    def test_failed_reads_amender_failed_with_exit_code(self):
        d = hvm.stamp(dict(_BASE), "running", now="t0")
        d = hvm.stamp(d, "failed", exit_code=1, now="t1")
        c = hvm.classify(d)
        self.assertEqual(c["absence_type"], "amender_failed")
        self.assertEqual(c["exit_code"], 1)

    def test_done_without_voice_is_a_producer_defect(self):
        d = hvm.stamp(dict(_BASE), "running", now="t0")
        d = hvm.stamp(d, "done", exit_code=0, now="t1")
        self.assertEqual(hvm.classify(d)["absence_type"], "amender_done_without_voice")

    def test_voice_present_reads_none_regardless_of_marker(self):
        d = hvm.stamp(dict(_BASE), "running", now="t0")
        d["voice"] = {"ambient_voice": "…", "validators_passed": True}
        c = hvm.classify(d)
        self.assertEqual(c["absence_type"], "none")
        self.assertTrue(c["voice_present"])

    def test_no_marker_means_probe_liveness(self):
        c = hvm.classify(dict(_BASE))
        self.assertEqual(c["absence_type"], "marker_absent_probe_liveness")
        self.assertFalse(c["marker_present"])
        self.assertIn("probe", c["guidance"])

    def test_marker_is_additive(self):
        d = hvm.stamp(dict(_BASE), "running", now="t0")
        for key, value in _BASE.items():
            self.assertEqual(d[key], value)
        self.assertEqual(set(d) - set(_BASE), {"voice_step"})

    def test_started_at_survives_running_to_done(self):
        d = hvm.stamp(dict(_BASE), "running", now="t0")
        d = hvm.stamp(d, "done", exit_code=0, now="t1")
        self.assertEqual(d["voice_step"]["started_at"], "t0")
        self.assertEqual(d["voice_step"]["finished_at"], "t1")
        self.assertEqual(d["voice_step"]["state"], "done")

    def test_cli_round_trips_through_a_real_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "disposition-tic-1.json"
            path.write_text(json.dumps(_BASE), encoding="utf-8")
            script = str(_HERE / "harmony-voice-marker.py")
            r = subprocess.run([sys.executable, script, "stamp", "--disposition", str(path), "--state", "running"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            r = subprocess.run([sys.executable, script, "classify", "--disposition", str(path)],
                               capture_output=True, text=True)
            self.assertEqual(json.loads(r.stdout)["absence_type"], "amender_running")
            r = subprocess.run([sys.executable, script, "stamp", "--disposition", str(path), "--state", "failed", "--exit-code", "2"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            on_disk = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["voice_step"]["state"], "failed")
            self.assertEqual(on_disk["voice_step"]["exit_code"], 2)
            self.assertEqual(on_disk["packetId"], "pkt-1")
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["disposition-tic-1.json"], "no temp residue")


if __name__ == "__main__":
    unittest.main(verbosity=2)
