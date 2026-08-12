#!/usr/bin/env python3
"""Write-side terminal-valve guard for cpr-gate-advance.append_transitions
(bk-cpr-stepper-docket-race-write-guard, tic 707).

The race shape: advance_gated composes its update_map from a read taken BEFORE the
append lock; a concurrent writer (review-execute landing a verdict) can terminalize
an id in that window. The guard re-projects each id's CURRENT status under the lock
and compare-and-swaps against the entry's recorded `prior_status` — a mismatched
entry is skipped loudly, never appended, so the stale transition cannot resurrect
a decided row under latest-per-id semantics.
"""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "cpr_gate_advance", os.path.join(_HERE, "cpr-gate-advance.py")
)
cga = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cga)


def row(cpr_id, status, **extra):
    base = {"id": cpr_id, "status": status, "lesson": "x", "source": "y",
            "birth_tic": 700}
    base.update(extra)
    return base


def write_queue(path, rows):
    path.write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows),
        encoding="utf-8")
    return path


class TestAppendTransitionsGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.q = Path(self.tmp.name) / "queue.jsonl"
        self.addCleanup(self.tmp.cleanup)

    def rows(self):
        return [json.loads(ln) for ln in
                self.q.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def test_matching_prior_status_appends(self):
        write_queue(self.q, [row("cpr_a", "tic_gated")])
        update = {"cpr_a": row("cpr_a", "enrichment_needed",
                               prior_status="tic_gated")}
        raced = cga.append_transitions(str(self.q), update)
        self.assertEqual(raced, [])
        self.assertEqual(self.rows()[-1]["status"], "enrichment_needed")

    def test_raced_terminalized_id_is_skipped_not_appended(self):
        # composed from a stale read: the id was tic_gated then, promoted now
        write_queue(self.q, [row("cpr_a", "tic_gated"),
                             row("cpr_a", "promoted")])
        update = {"cpr_a": row("cpr_a", "enrichment_needed",
                               prior_status="tic_gated")}
        raced = cga.append_transitions(str(self.q), update)
        self.assertEqual(raced, [("cpr_a", "tic_gated", "promoted")])
        self.assertEqual(self.rows()[-1]["status"], "promoted")  # untouched

    def test_mixed_batch_writes_only_unraced(self):
        write_queue(self.q, [row("cpr_a", "tic_gated"),
                             row("cpr_b", "tic_gated"),
                             row("cpr_b", "skipped")])
        update = {
            "cpr_a": row("cpr_a", "enrichment_needed", prior_status="tic_gated"),
            "cpr_b": row("cpr_b", "enrichment_needed", prior_status="tic_gated"),
        }
        raced = cga.append_transitions(str(self.q), update)
        self.assertEqual(raced, [("cpr_b", "tic_gated", "skipped")])
        latest = {}
        for r in self.rows():
            latest[r["id"]] = r["status"]
        self.assertEqual(latest["cpr_a"], "enrichment_needed")
        self.assertEqual(latest["cpr_b"], "skipped")

    def test_entry_without_prior_status_is_not_guarded(self):
        # prior_status is the compare-and-swap key; an entry that does not carry
        # it declares no expectation and passes through (legacy writer shape)
        write_queue(self.q, [row("cpr_a", "promoted")])
        update = {"cpr_a": row("cpr_a", "enrichment_needed")}
        raced = cga.append_transitions(str(self.q), update)
        self.assertEqual(raced, [])


if __name__ == "__main__":
    unittest.main()
