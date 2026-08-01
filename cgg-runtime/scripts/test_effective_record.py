#!/usr/bin/env python3
"""Regression floor for the third-surface effective-record contract.

The eight named arms mirror the publication gate in issue #16.  Migration and
consumer arms exercise the real tic 657→658 correction plus safe RTCH/export
behavior at the append-only row boundary.
"""

from __future__ import annotations

import json
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from lib.effective_record import (  # noqa: E402
    BACKREFS_RELATIVE,
    INDEX_RELATIVE,
    RECEIPTS_RELATIVE,
    build_effective_index,
    hydration_view,
    projection_status,
    reconcile,
    review_gate,
)


TARGET = "audit-logs/cprs/queue.jsonl"


class EffectiveRecordFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="effective-record-"))
        (self.tmp / ".ticzone").write_text(
            json.dumps({"audit_logs_path": "audit-logs"}) + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def append(self, relative: str, row: dict) -> None:
        path = self.tmp / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    def base(self, record_id="claim-1", **fields):
        row = {"id": record_id, "status": "promotable", "claim": "old claim"}
        row.update(fields)
        self.append(TARGET, row)
        return row

    def correction(self, correction_id="rc-1", **overrides):
        row = {
            "schema_version": 1,
            "type": "record_correction",
            "correction_id": correction_id,
            "target_record_id": "claim-1",
            "target_surface": TARGET,
            "source": {
                "repository": "prompted365/canonical_federation",
                "commit": "a" * 40,
                "surface": "audit-logs/reviews/2026-07-26.jsonl",
            },
            "patch": {"claim": "corrected claim"},
            "literal_correction": "The prior claim is disproven.",
            "authority": {
                "author_id": "ent_homeskillet",
                "authority_class": "ratified_review",
                "authorization_ref": "/review:test",
            },
            "reason": "Regression fixture",
            "effective_tic": 2,
            "effective_at": "2026-07-26T00:00:00Z",
            "supersedes": [],
            "consequence_class": "operational",
            "reversible": False,
            "lifecycle_state": "ratified",
            "receipt_path": "audit-logs/corrections/test.json",
        }
        row.update(overrides)
        self.append("audit-logs/reviews/2026-07-26.jsonl", row)
        return row

    def one_record(self):
        index = build_effective_index(self.tmp)
        self.assertEqual(len(index["records"]), 1)
        return index, index["records"][0]


class TestIssue16RegressionArms(EffectiveRecordFixture):
    def test_pair_agreement_third_surface_correction_holds_review(self):
        self.base(claim="Architect not resident")
        self.append(
            "audit-logs/governance/source-projection.jsonl",
            {"id": "source-claim-1", "claim": "Architect not resident"},
        )
        self.correction(
            patch={"claim": "Architect was resident"},
            lifecycle_state="authorized",
        )

        index, record = self.one_record()
        self.assertEqual(record["base_record"]["claim"], "Architect not resident")
        self.assertEqual(record["effective_record"]["claim"], "Architect was resident")
        self.assertEqual(review_gate(index)["status"], "hold")

    def test_authorized_backref_updates_effective_view(self):
        self.base()
        self.correction()
        result = reconcile(
            self.tmp,
            authority="ent_homeskillet",
            timestamp="2026-07-26T00:01:00Z",
        )
        backrefs = self.tmp / "audit-logs" / BACKREFS_RELATIVE
        row = json.loads(backrefs.read_text(encoding="utf-8").strip())
        self.assertEqual(row["correction_ids"], ["rc-1"])
        self.assertEqual(result["index"]["records"][0]["effective_record"]["claim"], "corrected claim")

    def test_multiple_corrections_order_deterministically(self):
        self.base()
        self.correction("rc-late", patch={"claim": "late"}, effective_tic=9)
        self.correction("rc-early", patch={"claim": "early"}, effective_tic=3)
        index, record = self.one_record()
        self.assertEqual(record["effective_record"]["claim"], "late")
        self.assertEqual(record["applied_correction_ids"], ["rc-early", "rc-late"])
        self.assertEqual(index, build_effective_index(self.tmp))

    def test_supersession_preserves_both_lineage_branches(self):
        self.base()
        self.correction("rc-first", patch={"claim": "first"}, effective_tic=3)
        self.correction(
            "rc-second",
            patch={"claim": "second"},
            effective_tic=4,
            supersedes=["rc-first"],
        )
        _, record = self.one_record()
        self.assertEqual(record["effective_record"]["claim"], "second")
        dispositions = {row["correction_id"]: row["disposition"] for row in record["lineage"]}
        self.assertEqual(dispositions["rc-first"], "superseded")
        self.assertEqual(dispositions["rc-second"], "applied_ratified")
        self.assertEqual(len(record["lineage"]), 2)

    def test_orphan_is_visible_and_blocks_promotion(self):
        self.correction(target_record_id="missing")
        index, record = self.one_record()
        self.assertEqual(index["counts"]["unresolved"], 1)
        self.assertEqual(record["unresolved"][0]["code"], "orphan_correction")
        self.assertEqual(review_gate(index)["status"], "hold")
        self.assertEqual(hydration_view(index)["status"], "blocked")

    def test_unauthorized_correction_never_rewrites_effective_view(self):
        self.base()
        self.correction(lifecycle_state="proposed")
        index, record = self.one_record()
        self.assertEqual(record["effective_record"], record["base_record"])
        self.assertEqual(record["lineage"][0]["disposition"], "proposed_not_applied")
        self.assertEqual(review_gate(index)["status"], "hold")

    def test_hydration_never_emits_disproven_claim_as_current_truth(self):
        wrong = "Architect not resident"
        self.base(claim=wrong)
        self.correction(patch={"claim": "Architect was resident"})
        hydration = hydration_view(build_effective_index(self.tmp))
        rendered = json.dumps(hydration, sort_keys=True)
        self.assertEqual(hydration["status"], "corrected")
        self.assertNotIn(wrong, rendered)
        self.assertIn("Architect was resident", rendered)

    def test_reconciliation_is_idempotent_and_projection_staleness_is_typed(self):
        self.base()
        self.correction()
        first = reconcile(
            self.tmp,
            authority="ent_homeskillet",
            timestamp="2026-07-26T00:01:00Z",
        )
        index_path = self.tmp / "audit-logs" / INDEX_RELATIVE
        backrefs_path = self.tmp / "audit-logs" / BACKREFS_RELATIVE
        receipts_path = self.tmp / "audit-logs" / RECEIPTS_RELATIVE
        snapshot = (index_path.read_bytes(), backrefs_path.read_bytes(), receipts_path.read_bytes())

        second = reconcile(
            self.tmp,
            authority="ent_homeskillet",
            timestamp="2026-07-26T00:02:00Z",
        )
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertFalse(second["receipt_written"])
        self.assertEqual(
            snapshot,
            (index_path.read_bytes(), backrefs_path.read_bytes(), receipts_path.read_bytes()),
        )
        self.assertFalse(projection_status(self.tmp)["stale"])

        self.append(TARGET, {"id": "unrelated", "claim": "new source state"})
        stale = projection_status(self.tmp)
        self.assertTrue(stale["stale"])
        self.assertEqual(stale["reason"], "source_digest_changed")


class TestRealMigration(EffectiveRecordFixture):
    def test_tic_657_to_658_history_resolves_without_retcon(self):
        migration = json.loads(
            (REPO_ROOT / "cgg-runtime/migrations/record-correction-tic658.json").read_text(
                encoding="utf-8"
            )
        )
        surface = migration["canonical_correction"]["target_surface"]
        self.append(surface, migration["base_record_snapshot"])
        self.append(surface, migration["legacy_correction_snapshot"])
        self.append(surface, migration["canonical_correction"])

        index, record = self.one_record()
        self.assertEqual(index["counts"]["unresolved"], 0)
        self.assertEqual(index["counts"]["legacy_correction_rows"], 1)
        self.assertEqual(index["counts"]["mapped_legacy_corrections"], 1)
        self.assertEqual(
            index["legacy_migrations"][0]["canonical_correction_id"],
            "rc_review_657_human_gate_and_supply_tic658",
        )
        self.assertIn("not resident", record["base_record"]["human_gate"])
        self.assertIn("was resident", record["effective_record"]["human_gate"])
        self.assertEqual(
            record["applied_correction_ids"],
            ["rc_review_657_human_gate_and_supply_tic658"],
        )
        self.assertEqual(record["lineage"][0]["disposition"], "applied_ratified")

    def test_unmigrated_legacy_correction_blocks_consumers(self):
        migration = json.loads(
            (REPO_ROOT / "cgg-runtime/migrations/record-correction-tic658.json").read_text(
                encoding="utf-8"
            )
        )
        surface = migration["canonical_correction"]["target_surface"]
        self.append(surface, migration["base_record_snapshot"])
        self.append(surface, migration["legacy_correction_snapshot"])

        index = build_effective_index(self.tmp)
        self.assertEqual(index["counts"]["correction_rows"], 0)
        self.assertEqual(index["counts"]["legacy_correction_rows"], 1)
        self.assertEqual(index["unresolved"][0]["code"], "legacy_correction_unmigrated")
        self.assertEqual(review_gate(index)["status"], "hold")
        self.assertEqual(hydration_view(index)["status"], "blocked")


class TestHydrationAndExportConsumers(EffectiveRecordFixture):
    def test_rtch_replaces_raw_preview_with_effective_record(self):
        self.base(claim="disproven current claim")
        self.correction(patch={"claim": "correct current claim"})
        projection = hydration_view(build_effective_index(self.tmp))

        spec = importlib.util.spec_from_file_location("rtch_effective_test", HERE / "rtch.py")
        rtch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rtch)
        target = str((self.tmp / TARGET).resolve())
        executed = [{"hits": [{"path": target, "line": 1, "preview": "disproven current claim"}]}]
        chunks = [{
            "path": target,
            "line_range": "L1-L1",
            "start_line": 1,
            "end_line": 1,
            "target_line": 1,
            "body_preview": "disproven current claim",
            "body_full_chars": 23,
            "confidence_class": "source_bearing_hit",
            "limitation": "",
            "why_included": "raw",
            "next_re_entry_command": "Read raw",
        }]
        rtch.apply_effective_record_projection(
            executed, chunks, {"zone_root": str(self.tmp)}, projection
        )
        rendered = json.dumps({"executed": executed, "chunks": chunks}, sort_keys=True)
        self.assertNotIn("disproven current claim", rendered)
        self.assertIn("correct current claim", rendered)
        self.assertEqual(chunks[0]["confidence_class"], "effective_record_view")

    def test_rtch_preserves_unrelated_hits_on_a_corrected_jsonl_surface(self):
        self.base(claim="disproven current claim")
        self.append(TARGET, {"id": "unrelated", "claim": "independent evidence"})
        self.correction(patch={"claim": "correct current claim"})
        projection = hydration_view(build_effective_index(self.tmp))

        spec = importlib.util.spec_from_file_location("rtch_effective_scope_test", HERE / "rtch.py")
        rtch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rtch)
        target = str((self.tmp / TARGET).resolve())
        executed = [{"hits": [{
            "path": target,
            "line": 2,
            "preview": "independent evidence",
        }]}]
        chunks = [{
            "path": target,
            "line_range": "L1-L2",
            "start_line": 1,
            "end_line": 2,
            "target_line": 2,
            "body_preview": "disproven current claim\nindependent evidence",
            "body_full_chars": 44,
            "confidence_class": "claim_supporting",
            "limitation": "bounded hit",
            "why_included": "unrelated row matched",
            "next_re_entry_command": "Read unrelated row",
        }]
        rtch.apply_effective_record_projection(
            executed, chunks, {"zone_root": str(self.tmp)}, projection
        )

        self.assertEqual(executed[0]["hits"][0]["preview"], "independent evidence")
        self.assertEqual(chunks[0]["confidence_class"], "claim_supporting")
        self.assertEqual(chunks[0]["why_included"], "unrelated row matched")
        self.assertIn("independent evidence", chunks[0]["body_preview"])
        self.assertIn("correct current claim", chunks[0]["body_preview"])
        self.assertNotIn("disproven current claim", chunks[0]["body_preview"])

    def test_consolidate_blocks_raw_corrected_surface_export(self):
        self.base(claim="disproven current claim")
        self.correction(patch={"claim": "correct current claim"})
        result = subprocess.run(
            [
                sys.executable,
                str(HERE / "consolidate.py"),
                "--base-dir",
                str(self.tmp),
                "--targets",
                str(self.tmp / TARGET),
                "--scan",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("effective_record_export_hold", result.stderr)
        self.assertNotIn("disproven current claim", result.stdout)


if __name__ == "__main__":
    unittest.main()
