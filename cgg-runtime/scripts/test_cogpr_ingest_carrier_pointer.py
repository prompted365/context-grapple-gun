#!/usr/bin/env python3
"""test_cogpr_ingest_carrier_pointer.py — carrier-pointer refusal fixtures.

Fix-site: A1-716 (cpr-stepper ninth post-fence run) + A2-716 (Mogul
pattern_mining, same tic, same root-cause file — two instruments convergent).
A BARE-STRING candidate in a candidate_cogprs array whose text names the
carrier field itself ("See top-level candidate_cogprs[0] …") is an
intra-document cross-reference, not a self-contained lesson; minted, it
births a queue row whose entire payload dangles once read divorced from the
report, and downstream miners inherit the pointer text verbatim (both
observed at tic 716; cohort doubled 2→4 in one tic).

The guard is STRUCTURAL (payload names its own envelope's field) and scoped
to the bare-string form only — the class-cure discipline per 502236e96cf1
(an instance-cure never cures the class) with an explicit over-blocking
guard: dict candidates may legitimately discuss the mechanism by name.

Every documented conditional gets both arms (selftest-fixtures-must-
exercise-documented-conditional-paths):
  arm 1 — bare-string pointer → refused, counted, loud, never minted
  arm 2 — bare-string real lesson → minted exactly as before
  arm 3 — dict candidate naming candidate_cogprs in its lesson → minted
          (over-block guard)
  arm 4 — per-cycle array pointer → refused via the same normalize path

SCOPE FENCE: historical pointer rows are not retro-edited (append-only;
their adjudication is /review's). This guards NEW births only.
"""

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "cogpr_ingest", _HERE / "cogpr-ingest.py")
ingest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ingest)

POINTER = "See top-level candidate_cogprs[0] — full lesson inscribed there."
REAL_BARE = ("A watcher that emits one ray per underlying item floods the "
             "manifold; aggregate to a per-owner rollup ray.")
DICT_NAMING_CARRIER = {
    "lesson": ("cogpr-ingest walks candidate_cogprs arrays at two levels; a "
               "producer emitting pointer strings there mints dangling rows — "
               "the ingest must refuse carrier-self-references at birth."),
    "band": "COGNITIVE",
    "subsystem": "cogpr-ingest",
}


def run_ingest(report_obj):
    """Run the full ingest against a throwaway zone; return (summary, stderr,
    queue_rows)."""
    with tempfile.TemporaryDirectory() as td:
        zone = Path(td)
        (zone / "audit-logs" / "cprs").mkdir(parents=True)
        report_path = zone / "report.json"
        report_path.write_text(json.dumps(report_obj))
        err = io.StringIO()
        with redirect_stderr(err):
            summary = ingest.ingest(zone, report_path, dry_run=False)
        queue_file = zone / "audit-logs" / "cprs" / "queue.jsonl"
        rows = []
        if queue_file.exists():
            rows = [json.loads(l) for l in
                    queue_file.read_text().splitlines() if l.strip()]
        return summary, err.getvalue(), rows


class TestCarrierPointerRefusal(unittest.TestCase):
    def test_arm1_bare_string_pointer_refused(self):
        summary, err, rows = run_ingest({
            "mandate_id": "tic-716-test",
            "candidate_cogprs": [POINTER],
        })
        self.assertEqual(summary["skipped_carrier_pointer"], 1)
        self.assertEqual(summary["ingested"], 0)
        self.assertIn("CARRIER-POINTER REFUSAL", err)
        self.assertEqual(rows, [])

    def test_arm2_bare_string_real_lesson_minted(self):
        summary, err, rows = run_ingest({
            "mandate_id": "tic-716-test",
            "candidate_cogprs": [REAL_BARE],
        })
        self.assertEqual(summary["skipped_carrier_pointer"], 0)
        self.assertEqual(summary["ingested"], 1)
        self.assertNotIn("CARRIER-POINTER REFUSAL", err)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["lesson"], REAL_BARE)

    def test_arm3_dict_naming_carrier_minted_overblock_guard(self):
        summary, err, rows = run_ingest({
            "mandate_id": "tic-716-test",
            "candidate_cogprs": [DICT_NAMING_CARRIER],
        })
        self.assertEqual(summary["skipped_carrier_pointer"], 0)
        self.assertEqual(summary["ingested"], 1)
        self.assertEqual(len(rows), 1)
        self.assertIn("candidate_cogprs", rows[0]["lesson"])

    def test_arm4_per_cycle_pointer_refused_real_top_level_minted(self):
        summary, err, rows = run_ingest({
            "mandate_id": "tic-716-test",
            "candidate_cogprs": [DICT_NAMING_CARRIER],
            "results": {
                "pattern_mining": {
                    "candidate_cogprs": [
                        "See top-level candidate_cogprs — 2 candidates, "
                        "both sourced from this cycle."],
                },
            },
        })
        self.assertEqual(summary["candidates_seen"], 2)
        self.assertEqual(summary["skipped_carrier_pointer"], 1)
        self.assertEqual(summary["ingested"], 1)
        self.assertIn("pattern_mining", err)
        self.assertEqual(len(rows), 1)

    def test_counter_present_in_fresh_summary(self):
        summary, _, _ = run_ingest({"mandate_id": "t", "candidate_cogprs": []})
        self.assertIn("skipped_carrier_pointer", summary)
        self.assertEqual(summary["skipped_carrier_pointer"], 0)


if __name__ == "__main__":
    unittest.main()
