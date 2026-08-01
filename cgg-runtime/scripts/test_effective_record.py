#!/usr/bin/env python3
"""Regression floor for the third-surface effective-record contract.

The eight named arms mirror the publication gate in issue #16.  Migration and
consumer arms exercise the real tic 657→658 correction plus safe RTCH/export
behavior at the append-only row boundary.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from lib import effective_record as effective_record_lib  # noqa: E402
from lib.effective_record import (  # noqa: E402
    BACKREFS_RELATIVE,
    INDEX_RELATIVE,
    RECEIPTS_RELATIVE,
    build_effective_index,
    digest_value,
    hydration_view,
    projection_status,
    reconcile,
    review_gate,
)


TARGET = "audit-logs/cprs/queue.jsonl"


class EffectiveRecordFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="effective-record-"))
        self.managed_tmp = Path(tempfile.mkdtemp(prefix="effective-record-runtime-"))
        self.trusted_migrations = self.managed_tmp / "migrations"
        shutil.copytree(
            REPO_ROOT / "cgg-runtime" / "migrations",
            self.trusted_migrations,
        )
        self.trusted_migrations_patch = patch.object(
            effective_record_lib,
            "TRUSTED_MIGRATIONS_DIR",
            self.trusted_migrations,
        )
        self.trusted_migrations_patch.start()
        (self.tmp / ".ticzone").write_text(
            json.dumps({"audit_logs_path": "audit-logs"}) + "\n",
            encoding="utf-8",
        )
        self.git("init", "-q")
        self.git("config", "user.name", "CGG effective-record test")
        self.git("config", "user.email", "effective-record@example.invalid")
        self.git(
            "remote",
            "add",
            "origin",
            "https://github.com/prompted365/canonical_federation.git",
        )
        self.commit_zone("Initialize governed zone")

    def tearDown(self):
        self.trusted_migrations_patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.managed_tmp, ignore_errors=True)

    def git(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.tmp), *arguments],
            capture_output=True,
            text=True,
            check=check,
            timeout=10,
        )

    def commit_zone(self, message="Record correction fixture") -> str:
        self.git("add", "-A")
        if self.git("diff", "--cached", "--quiet", check=False).returncode != 0:
            self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").stdout.strip()

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

    def receipt_relative_for(self, row: dict) -> str:
        correction_id = row["correction_id"]
        safe_id = "".join(
            character if character.isalnum() or character in "-_" else "-"
            for character in correction_id
        )
        return f"cgg-runtime/migrations/test-{safe_id}.json"

    def trust_correction_for_fixture(
        self,
        row: dict,
        append_commit: str,
        append_surface: str | None = None,
    ) -> None:
        correction_id = row["correction_id"]
        receipt_relative = row["receipt_path"]
        receipt_name = Path(receipt_relative).name
        correction_digest = digest_value(row)
        source = row["source"]
        surface = append_surface or source["surface"]
        migration = {
            "provenance": {
                "repository": source["repository"],
                "surface": surface,
                "canonical_append_commit": append_commit,
            },
            "canonical_correction": copy.deepcopy(row),
            "canonical_authorization_receipt": {
                "schema_version": 1,
                "type": "record_correction_authorization_receipt",
                "correction_id": correction_id,
                "correction_digest": correction_digest,
                "authority": row["authority"],
                "lifecycle_state": row["lifecycle_state"],
                "receipt_path": receipt_relative,
                "canonical_append_repository": source["repository"],
                "canonical_append_commit": append_commit,
                "canonical_append_surface": surface,
            },
        }
        (self.trusted_migrations / receipt_name).write_text(
            json.dumps(migration, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def trust_real_migration_for_fixture(self, migration: dict, append_commit: str) -> None:
        trusted = copy.deepcopy(migration)
        surface = trusted["provenance"]["surface"]
        trusted["provenance"]["canonical_append_commit"] = append_commit
        receipt = trusted["canonical_authorization_receipt"]
        receipt["canonical_append_commit"] = append_commit
        receipt["canonical_append_surface"] = surface
        trusted["migration_receipt"]["canonical_append_commit"] = append_commit
        (self.trusted_migrations / "record-correction-tic658.json").write_text(
            json.dumps(trusted, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def append_trusted_correction(self, located_surface: str, row: dict) -> str:
        row["receipt_path"] = self.receipt_relative_for(row)
        self.append(located_surface, row)
        append_commit = self.commit_zone()
        self.trust_correction_for_fixture(row, append_commit)
        return append_commit

    def run_consolidate(self, *targets: str) -> subprocess.CompletedProcess[str]:
        wrapper = """
import runpy
import sys
from pathlib import Path

scripts_dir, migrations_dir, *arguments = sys.argv[1:]
sys.path.insert(0, scripts_dir)
from lib import effective_record
effective_record.TRUSTED_MIGRATIONS_DIR = Path(migrations_dir)
sys.argv = [str(Path(scripts_dir) / "consolidate.py"), *arguments]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
        return subprocess.run(
            [
                sys.executable,
                "-c",
                wrapper,
                str(HERE),
                str(self.trusted_migrations),
                "--base-dir",
                str(self.tmp),
                "--targets",
                *targets,
                "--scan",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

    def correction(
        self,
        correction_id="rc-1",
        *,
        trusted=True,
        located_surface="audit-logs/reviews/2026-07-26.jsonl",
        **overrides,
    ):
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
        if trusted and row.get("lifecycle_state") in {"authorized", "ratified"}:
            self.append_trusted_correction(located_surface, row)
        else:
            self.append(located_surface, row)
            self.commit_zone()
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

    def test_revoked_correction_preserves_a_revoked_lineage_disposition(self):
        self.base()
        self.correction(lifecycle_state="revoked")
        index, record = self.one_record()
        self.assertEqual(index["counts"]["unresolved"], 0)
        self.assertEqual(record["effective_record"], record["base_record"])
        self.assertEqual(record["lineage"][0]["disposition"], "revoked")

    def test_duplicate_correction_id_is_unresolved(self):
        self.base()
        self.correction("rc-duplicate", effective_tic=3)
        self.correction("rc-duplicate", effective_tic=4)
        index, record = self.one_record()
        self.assertIn("duplicate_correction_id", {issue["code"] for issue in index["unresolved"]})
        self.assertTrue(all(row["disposition"] == "discarded_invalid" for row in record["lineage"]))

    def test_supersession_cycle_is_unresolved(self):
        self.base()
        self.correction("rc-cycle-a", effective_tic=3, supersedes=["rc-cycle-b"])
        self.correction("rc-cycle-b", effective_tic=4, supersedes=["rc-cycle-a"])
        index, _ = self.one_record()
        self.assertIn("supersession_cycle", {issue["code"] for issue in index["unresolved"]})

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

    def test_self_asserted_ratification_and_forged_zone_receipt_never_apply(self):
        self.base()
        correction = self.correction(trusted=False)
        fake_receipt = self.tmp / correction["receipt_path"]
        fake_receipt.parent.mkdir(parents=True, exist_ok=True)
        fake_receipt.write_text(
            json.dumps({
                "type": "record_correction_authorization_receipt",
                "correction_id": correction["correction_id"],
                "correction_digest": digest_value(correction),
                "authority": correction["authority"],
            }) + "\n",
            encoding="utf-8",
        )

        index, record = self.one_record()
        self.assertIn(
            "unverified_authorization_receipt",
            {issue["code"] for issue in index["unresolved"]},
        )
        self.assertEqual(record["effective_record"], record["base_record"])
        self.assertEqual(record["lineage"][0]["disposition"], "discarded_invalid")
        self.assertFalse(record["lineage"][0]["authority_receipt_verified"])
        self.assertEqual(review_gate(index)["status"], "hold")
        self.assertEqual(hydration_view(index)["status"], "blocked")

    def test_trusted_correction_replayed_off_its_source_surface_never_applies(self):
        self.base()
        self.correction(located_surface="audit-logs/reviews/copied.jsonl")

        index, record = self.one_record()
        self.assertIn(
            "source_surface_mismatch",
            {issue["code"] for issue in index["unresolved"]},
        )
        self.assertEqual(record["effective_record"], record["base_record"])
        self.assertEqual(record["lineage"][0]["disposition"], "discarded_invalid")

    def test_trusted_correction_copied_into_an_unrelated_repository_never_applies(self):
        self.base()
        self.correction()
        self.git(
            "remote",
            "set-url",
            "origin",
            "https://github.com/prompted365/unrelated-zone.git",
        )

        index, record = self.one_record()
        issue = next(
            issue
            for issue in index["unresolved"]
            if issue["code"] == "unverified_repository_binding"
        )
        self.assertEqual(issue["failure"], "origin_repository_mismatch")
        self.assertEqual(record["effective_record"], record["base_record"])
        self.assertEqual(record["lineage"][0]["disposition"], "discarded_invalid")
        self.assertFalse(record["lineage"][0]["authority_receipt_verified"])

    def test_github_origin_normalization_is_narrow_and_format_independent(self):
        normalize = effective_record_lib._normalize_github_repository
        expected = "prompted365/canonical_federation"
        self.assertEqual(normalize(expected), expected)
        self.assertEqual(
            normalize("https://github.com/prompted365/canonical_federation.git"),
            expected,
        )
        self.assertEqual(
            normalize("git@github.com:prompted365/canonical_federation.git"),
            expected,
        )
        self.assertEqual(
            normalize("ssh://git@github.com/prompted365/canonical_federation.git"),
            expected,
        )
        self.assertIsNone(normalize("https://example.com/prompted365/canonical_federation"))
        self.assertIsNone(normalize("https://github.com/prompted365/canonical_federation/tree/main"))

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

        backrefs_path.write_text("torn-write\n", encoding="utf-8")
        torn = projection_status(self.tmp)
        self.assertTrue(torn["stale"])
        self.assertEqual(torn["reason"], "backrefs_digest_changed")
        repaired = reconcile(
            self.tmp,
            authority="ent_homeskillet",
            timestamp="2026-07-26T00:03:00Z",
        )
        self.assertTrue(repaired["changed"])
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
        append_commit = self.commit_zone("Append canonical tic 658 correction")
        self.trust_real_migration_for_fixture(migration, append_commit)

        index, record = self.one_record()
        self.assertEqual(index["counts"]["unresolved"], 0)
        self.assertEqual(index["counts"]["legacy_correction_rows"], 1)
        self.assertEqual(index["counts"]["mapped_legacy_corrections"], 1)
        self.assertEqual(
            index["legacy_migrations"][0]["canonical_correction_id"],
            "rc_review_657_human_gate_and_supply_tic658",
        )
        self.assertEqual(
            index["legacy_migrations"][0]["disposition"],
            "preserved_legacy_mapped_to_canonical",
        )
        self.assertTrue(migration["migration_receipt"]["canonical_correction_appended"])
        self.assertEqual(
            migration["legacy_binding"]["legacy_row_digest"],
            digest_value(migration["legacy_correction_snapshot"]),
        )
        self.assertEqual(
            migration["canonical_authorization_receipt"]["correction_digest"],
            digest_value(migration["canonical_correction"]),
        )
        self.assertEqual(
            migration["canonical_authorization_receipt"]["authority"],
            migration["canonical_correction"]["authority"],
        )
        self.assertEqual(
            migration["migration_receipt"]["canonical_append_commit"],
            "9c8c386091f281b494621a4b52276096aeefea8d",
        )
        self.assertIn("not resident", record["base_record"]["human_gate"])
        self.assertIn("was resident", record["effective_record"]["human_gate"])
        self.assertEqual(
            record["applied_correction_ids"],
            ["rc_review_657_human_gate_and_supply_tic658"],
        )
        self.assertEqual(record["lineage"][0]["disposition"], "applied_ratified")
        self.assertTrue(record["lineage"][0]["authority_receipt_verified"])

    def test_legacy_binding_stays_stable_after_a_later_correction(self):
        migration = json.loads(
            (REPO_ROOT / "cgg-runtime/migrations/record-correction-tic658.json").read_text(
                encoding="utf-8"
            )
        )
        surface = migration["canonical_correction"]["target_surface"]
        self.append(surface, migration["base_record_snapshot"])
        self.append(surface, migration["legacy_correction_snapshot"])
        self.append(surface, migration["canonical_correction"])
        append_commit = self.commit_zone("Append canonical tic 658 correction")
        self.trust_real_migration_for_fixture(migration, append_commit)
        later = copy.deepcopy(migration["canonical_correction"])
        later.update({
            "correction_id": "rc_review_657_later_clarification_tic659",
            "patch": {"human_gate": "later ratified clarification"},
            "literal_correction": "A later correction must not steal the legacy binding.",
            "reason": "Exercise stable migration identity after another correction lands.",
            "effective_tic": 659,
            "effective_at": "2026-07-27T00:00:00Z",
            "receipt_path": "audit-logs/reviews/later-correction-receipt.json",
        })
        self.append_trusted_correction(surface, later)

        index, record = self.one_record()
        self.assertEqual(index["counts"]["unresolved"], 0)
        self.assertEqual(
            index["legacy_migrations"][0]["canonical_correction_id"],
            "rc_review_657_human_gate_and_supply_tic658",
        )
        self.assertEqual(
            record["applied_correction_ids"],
            [
                "rc_review_657_human_gate_and_supply_tic658",
                "rc_review_657_later_clarification_tic659",
            ],
        )

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
        self.assertEqual(
            index["legacy_migrations"][0]["disposition"],
            "preserved_legacy_unmigrated",
        )
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

    def test_rtch_keeps_projection_hold_when_the_source_reread_fails(self):
        self.base(claim="disproven current claim")
        self.correction(patch={"claim": "correct current claim"})
        projection = hydration_view(build_effective_index(self.tmp))

        spec = importlib.util.spec_from_file_location("rtch_effective_read_hold_test", HERE / "rtch.py")
        rtch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rtch)
        target = str((self.tmp / TARGET).resolve())
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
        }]

        with patch.object(rtch.Path, "open", side_effect=OSError("fixture read failure")):
            rtch.apply_effective_record_projection(
                [], chunks, {"zone_root": str(self.tmp)}, projection
            )

        self.assertEqual(chunks[0]["confidence_class"], "effective_record_projection_hold")
        self.assertEqual(
            chunks[0]["body_preview"],
            "[effective-record projection unavailable; raw bounded chunk withheld]",
        )
        self.assertNotIn("disproven current claim", chunks[0]["body_preview"])

    def test_rtch_preserves_unrelated_hits_on_a_corrected_jsonl_surface(self):
        self.base(claim="disproven current claim")
        self.append(TARGET, {"id": "unrelated", "claim": "independent evidence"})
        self.append(TARGET, {"id": "claim-2", "claim": "second disproven claim"})
        self.correction(patch={"claim": "correct current claim"})
        self.correction(
            "rc-2",
            target_record_id="claim-2",
            patch={"claim": "second corrected claim"},
        )
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
            "line_range": "L1-L3",
            "start_line": 1,
            "end_line": 3,
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
        commands = chunks[0]["effective_record_re_entry_commands"]
        self.assertEqual(len(commands), 2)
        self.assertTrue(any("--record-id claim-1 " in command for command in commands))
        self.assertTrue(any("--record-id claim-2 " in command for command in commands))

    def test_consolidate_blocks_raw_corrected_surface_export(self):
        self.base(claim="disproven current claim")
        self.correction(patch={"claim": "correct current claim"})
        result = self.run_consolidate(str(self.tmp / TARGET))
        self.assertEqual(result.returncode, 3)
        self.assertIn("effective_record_export_hold", result.stderr)
        self.assertNotIn("disproven current claim", result.stdout)

    def test_consolidate_blocks_a_selected_legacy_only_unresolved_surface(self):
        migration = json.loads(
            (REPO_ROOT / "cgg-runtime/migrations/record-correction-tic658.json").read_text(
                encoding="utf-8"
            )
        )
        surface = migration["canonical_correction"]["target_surface"]
        self.append(surface, migration["base_record_snapshot"])
        self.append(surface, migration["legacy_correction_snapshot"])
        result = self.run_consolidate(str(self.tmp / surface))
        self.assertEqual(result.returncode, 3)
        self.assertIn("legacy_correction_unmigrated", result.stderr)
        self.assertNotIn("Architect not resident", result.stdout)

    def test_consolidate_blocks_duplicate_corrections_on_their_source_surface(self):
        self.base()
        correction = self.correction("rc-source-duplicate")
        source_surface = correction["source"]["surface"]
        self.append(source_surface, correction)
        self.commit_zone("Duplicate a correction row")

        index = build_effective_index(self.tmp)
        duplicate = next(
            issue
            for issue in index["unresolved"]
            if issue["code"] == "duplicate_correction_id"
        )
        self.assertEqual(
            duplicate["source_locations"],
            [
                {"surface": source_surface, "line": 1},
                {"surface": source_surface, "line": 2},
            ],
        )

        result = self.run_consolidate(str(self.tmp / source_surface))
        self.assertEqual(result.returncode, 3)
        self.assertIn("duplicate_correction_id", result.stderr)
        self.assertEqual(result.stdout, "")

        unrelated = self.tmp / "notes.md"
        unrelated.write_text("independent export\n", encoding="utf-8")
        mixed = self.run_consolidate(str(self.tmp / source_surface), str(unrelated))
        self.assertEqual(mixed.returncode, 0)
        self.assertEqual(json.loads(mixed.stdout)["file_list"], ["notes.md"])
        self.assertIn("Raw corrected surfaces were excluded", mixed.stderr)

    def test_consolidate_excludes_corrected_surface_but_keeps_unrelated_export(self):
        migration = json.loads(
            (REPO_ROOT / "cgg-runtime/migrations/record-correction-tic658.json").read_text(
                encoding="utf-8"
            )
        )
        surface = migration["canonical_correction"]["target_surface"]
        self.append(surface, migration["base_record_snapshot"])
        self.append(surface, migration["legacy_correction_snapshot"])
        self.append(surface, migration["canonical_correction"])
        append_commit = self.commit_zone("Append canonical tic 658 correction")
        self.trust_real_migration_for_fixture(migration, append_commit)
        unrelated = self.tmp / "notes.md"
        unrelated.write_text("independent export\n", encoding="utf-8")
        result = self.run_consolidate(str(self.tmp / surface), str(unrelated))
        self.assertEqual(result.returncode, 0)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["file_list"], ["notes.md"])
        self.assertIn("Raw corrected surfaces were excluded", result.stderr)


if __name__ == "__main__":
    unittest.main()
