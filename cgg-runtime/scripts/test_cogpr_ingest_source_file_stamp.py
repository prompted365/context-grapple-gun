#!/usr/bin/env python3
"""test_cogpr_ingest_source_file_stamp.py — cycle-report provenance stamp fixtures.

Fix-site: bk-cogpr-ingest-source-file-unstamped (classified tic 693 while
verifying docket evidence truthfulness, struck tic 694). The defect: mogul
cogpr-ingest mint_entry never stamped `source_file`, and its `source` field is
the provenance TAG `mogul:<cycle>` — not a path — so the scanner's Gate-1
A1-665 resolution (stamped source_file FIRST, colon-heuristic over `source`
as fallback) fell through BOTH attempts and minted an honest-but-discounting
`source_missing` ray (-0.30) on EVERY mogul-ingested row, even when the real
cycle report sat on disk (confirmed live for the tic-690 reports at /review
693). Scanner behavior is correct per A1-665 — the cure is input-side: stamp
`source_file` with the producing cycle-report path, zone-relative (relative
paths anchor at zone root, never cwd). Sibling of the t692 dedup_hash stamp
fix on the same mint_entry surface; historical rows are not retro-edited.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ci = _load("cogpr_ingest", _HERE / "cogpr-ingest.py")
scanner = _load("cpr_enrichment_scanner", _HERE / "cpr-enrichment-scanner.py")

TOPO = {"birth_rung": "site", "birth_scope_path": "/tmp/zone"}
REPORT = {"mandate_id": "tic-694-test", "actor": {"runtime": "claude_code"}}
REL_REPORT = "audit-logs/mogul/cycle-reports/reports/tic-694-test.report.json"


class MintStampsSourceFile(unittest.TestCase):
    def test_mint_entry_stamps_source_file_when_supplied(self):
        """THE defect: pre-fix mint_entry had no source_file at all, so the
        scanner's stamped-first resolution had nothing to resolve."""
        e = ci.mint_entry({"lesson": "A provenance lesson."}, "pattern_mining",
                          REPORT, 100, TOPO, source_file=REL_REPORT)
        self.assertEqual(e.get("source_file"), REL_REPORT)

    def test_source_tag_untouched_by_the_stamp(self):
        """`source` stays the mogul:<cycle> provenance TAG (id/dedup formula
        input) — the stamp adds a path, it never rewrites the tag."""
        e = ci.mint_entry({"lesson": "Tag-stability lesson."}, "deep_audit",
                          REPORT, 100, TOPO, source_file=REL_REPORT)
        self.assertEqual(e["source"], "mogul:deep_audit")

    def test_omitted_source_file_leaves_field_absent(self):
        """Back-compat: callers that cannot name the report omit the kwarg;
        the row carries NO empty-string noise field."""
        e = ci.mint_entry({"lesson": "No-path lesson."}, "pattern_mining",
                          REPORT, 100, TOPO)
        self.assertNotIn("source_file", e)


class IngestStampsZoneRelativePath(unittest.TestCase):
    def test_ingest_end_to_end_stamps_zone_relative_and_scanner_resolves(self):
        """Round-trip: a report ingested from a temp zone lands a queue row
        whose source_file is ZONE-RELATIVE, and the scanner's
        resolve_source_path finds it against that zone root — the exact
        resolution that pre-fix fell through both attempts."""
        with tempfile.TemporaryDirectory() as td:
            zone = Path(td)
            rep_dir = zone / "audit-logs" / "mogul" / "cycle-reports" / "reports"
            rep_dir.mkdir(parents=True)
            rep_path = rep_dir / "tic-694-test.report.json"
            rep_path.write_text(json.dumps({
                "mandate_id": "tic-694-test",
                "actor": {"runtime": "claude_code"},
                "candidate_cogprs": [
                    {"lesson": "Round-trip provenance lesson."}
                ],
            }))
            summary = ci.ingest(zone, rep_path, dry_run=False)
            self.assertEqual(summary["ingested"], 1)

            queue = zone / "audit-logs" / "cprs" / "queue.jsonl"
            row = json.loads(queue.read_text().strip().splitlines()[-1])
            want_rel = str(rep_path.relative_to(zone))
            self.assertEqual(row.get("source_file"), want_rel)

            resolved = scanner.resolve_source_path(row["source_file"], str(zone))
            self.assertIsNotNone(resolved)
            self.assertTrue(str(resolved).endswith("tic-694-test.report.json"))

    def test_report_outside_zone_falls_back_to_absolute_string(self):
        """A report not under the zone root cannot be zone-relativized; the
        stamp degrades to the absolute path rather than lying or dropping."""
        with tempfile.TemporaryDirectory() as td_zone, \
                tempfile.TemporaryDirectory() as td_out:
            zone = Path(td_zone)
            rep_path = Path(td_out) / "outside.report.json"
            rep_path.write_text(json.dumps({
                "candidate_cogprs": [{"lesson": "Outside-zone lesson."}],
            }))
            summary = ci.ingest(zone, rep_path, dry_run=False)
            self.assertEqual(summary["ingested"], 1)
            queue = zone / "audit-logs" / "cprs" / "queue.jsonl"
            row = json.loads(queue.read_text().strip().splitlines()[-1])
            self.assertEqual(row.get("source_file"), str(rep_path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
