#!/usr/bin/env python3
"""Fixtures for queue-lifecycle-writeback.py — the copy-forward writer for
lifecycle-class queue.jsonl rows (bk-review-execute-lifecycle-writeback-envelope-
stripping, cpr-step-683 finding F3).

RED-THEN-GREEN spine:
  RED  — `TestRedThinRowRefused` reconstructs the ACTUAL tic-682 shapes (a 37-field
         `tic_gated` envelope + the 24-field lifecycle-only DEFER row that landed over
         it) and proves the guard REFUSES the thin row, naming every dropped field.
         This is the arm that did not exist when the defect shipped.
  GREEN — `TestDeferWritebackPreservesEnvelope` runs the same DEFER through the
         mechanized path and proves all 8 named fields (+ the rest of the envelope)
         survive while ONLY the lifecycle fields change.

Per `cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths`, every
documented conditional gets BOTH arms: prior-row present/absent, payload empty/non-empty,
field declared/protected/unknown(+allowed), prior_status auto-stamp fires/suppressed,
review_tic merged/caller-wins, append via atomic-append.sh / in-process fallback,
history gap present/absent, validate-row PASS/REFUSE, dry-run vs write.

Isolation: every case builds its own queue.jsonl under a TemporaryDirectory and passes
it via the `queue_path` hook — nothing reads or writes the real federation queue.
Promote-class rows are exercised with `emit_only=True` so the tic-481 promote-writeback
physics gate at the atomic-append boundary is never fired against real auto-memory.

Run:  python3 -m unittest test_queue_lifecycle_writeback   (from cgg-runtime/scripts/)
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "queue_lifecycle_writeback", os.path.join(_HERE, "queue-lifecycle-writeback.py")
)
qlw = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(qlw)


# --- the tic-682 shapes, reconstructed ---------------------------------------------
# The 8 fields the live incident dropped, named explicitly so a regression names itself.
DROPPED_AT_682 = [
    "lesson", "source", "source_date", "subsystem", "recommended_scopes",
    "birth_tic", "confidence_tier", "lesson_type",
]

CPR_ID = "cpr_mogul_review_close_check_79ae89ca3a0a"


def envelope_row(cpr_id=CPR_ID, status="tic_gated"):
    """A full lifecycle envelope in the shape queue.jsonl actually carries (37 fields,
    matching the tic-682 `tic_gated` row that the thin DEFER row landed over)."""
    return {
        "id": cpr_id, "status": status, "type": "cogpr",
        "lesson": "A verifier that cannot distinguish absence-of-evidence from "
                  "evidence-of-absence reports the wrong hazard class.",
        "source": "mogul review_close_check cycle",
        "source_date": "2026-08-03", "source_cycle": "review_close_check",
        "subsystem": "governance/review",
        "recommended_scopes": ["cgg-ledger", "canonical/CLAUDE.md"],
        "birth_tic": 679, "birth_rung": "federation",
        "birth_scope_path": "audit-logs/governance",
        "confidence_tier": "medium", "lesson_type": "mechanism",
        "band": "COGNITIVE", "tier": 2, "motivation_layer": "governance",
        "note": "born from the repaired checker's third clean read",
        "origin_context": "mogul cycle report",
        "mogul_mandate_id": "tic-679-031408", "mogul_runtime": "opus",
        "dedup_hash": "79ae89ca3a0a0000", "dedup_verification": {"method": "verify_twin"},
        "extracted_at": "2026-08-03T19:12:00Z", "extracted_by": "cpr-extract",
        "id_origin": "hash", "maturity_window_tics": 3, "review_tic": 682,
        "relations": {"corrector": "cpr_6540e0503eaa"},
        "staleness": "fresh", "stepper_annotation": "birth 679+3<=682",
        "advance_reason": "maturity discharged", "advanced_at": "2026-08-05T19:00:00Z",
        "advanced_by": "cpr-stepper", "advanced_tic": 682, "current_tic": 682,
        "prior_status": "extracted",
    }


def thin_defer_row_682(cpr_id=CPR_ID):
    """The ACTUAL defect shape: a from-scratch lifecycle-only DEFER row that carries the
    verdict fields and nothing else. Under latest-per-id semantics this REPLACES the
    envelope — the 8 DROPPED_AT_682 fields are deleted, not merged."""
    return {
        "id": cpr_id, "status": "enrichment_eligible", "type": "cogpr",
        "pending_class": "evidence_insufficient", "maturity_window_tics": 1,
        "re_eval_condition": "joint adjudication with corrector at 683",
        "window_anchor_tic": 682, "review_tic": 682, "review_verdict": "DEFER",
        "review_confidence": 0.9, "review_reasoning": "corrector matures at 683",
        "review_pass": 1, "review_confidence_basis": "ratified question set",
        "review_confidence_tier": "medium", "ratified_by": "architect",
        "prior_status": "tic_gated", "advanced_by": "review-execute",
        "advanced_tic": 682, "current_tic": 682, "boot_receipt": "a0006c4eff5b",
        "inscription_form": "queue_only", "enrichment_scan_count": 1,
        "enrichment_scanned_at": "2026-08-06T19:00:00Z",
        "no_evidence_reason": "no gatherer produced evidence (missing: source, "
                              "source_date, subsystem, recommended_scopes, lesson)",
    }


def write_queue(path, rows):
    path.write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows),
        encoding="utf-8")
    return path


class _TmpQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.q = self.dir / "queue.jsonl"
        self.addCleanup(self.tmp.cleanup)

    def rows(self):
        return [json.loads(ln) for ln in
                self.q.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ===========================================================================
# RED — the thin row the defect actually wrote must be REFUSED
# ===========================================================================

class TestRedThinRowRefused(_TmpQueue):
    def test_thin_row_drops_the_eight_named_fields(self):
        """Bare predicate: the tic-682 thin row drops exactly the fields the incident
        lost. This is the assertion that was missing at write time."""
        drops = qlw.envelope_drops(envelope_row(), thin_defer_row_682())
        for field in DROPPED_AT_682:
            self.assertIn(field, drops, f"{field} should be detected as dropped")
        self.assertGreaterEqual(len(drops), 8)

    def test_validate_row_refuses_the_thin_row(self):
        """The live guard: appending the tic-682 row against the real prior envelope
        is REFUSED, and every dropped field is named."""
        write_queue(self.q, [envelope_row()])
        res = qlw.validate_row(thin_defer_row_682(), queue_path=self.q)
        self.assertEqual(res["verdict"], "REFUSE")
        for field in DROPPED_AT_682:
            self.assertIn(field, res["envelope_drops"])

    def test_validate_row_cli_exits_3_on_thin_row(self):
        write_queue(self.q, [envelope_row()])
        rc = qlw.main(["--validate-row", json.dumps(thin_defer_row_682()),
                       "--queue-path", str(self.q)])
        self.assertEqual(rc, 3)

    def test_validate_row_passes_a_copy_forward_row(self):
        """The other arm — a row that preserves the envelope is admitted."""
        write_queue(self.q, [envelope_row()])
        good = {**envelope_row(), "status": "enrichment_eligible",
                "review_verdict": "DEFER"}
        res = qlw.validate_row(good, queue_path=self.q)
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(res["envelope_drops"], [])

    def test_validate_row_birth_row_has_nothing_to_preserve(self):
        write_queue(self.q, [envelope_row(cpr_id="cpr_other")])
        res = qlw.validate_row({"id": "cpr_brand_new", "status": "extracted"},
                               queue_path=self.q)
        self.assertEqual(res["verdict"], "PASS")
        self.assertIn("birth row", res["reason"])

    def test_validate_row_without_id_is_refused(self):
        write_queue(self.q, [envelope_row()])
        res = qlw.validate_row({"status": "skipped"}, queue_path=self.q)
        self.assertEqual(res["verdict"], "REFUSE")
        self.assertIn("no id", res["reason"])


# ===========================================================================
# GREEN — the mechanized DEFER preserves the envelope
# ===========================================================================

class TestDeferWritebackPreservesEnvelope(_TmpQueue):
    DEFER = {
        "status": "enrichment_eligible", "pending_class": "evidence_insufficient",
        "maturity_window_tics": 1,
        "re_eval_condition": "joint adjudication with corrector at 683",
        "window_anchor_tic": 682, "review_verdict": "DEFER",
        "review_confidence": 0.9, "review_reasoning": "corrector matures at 683",
    }

    def test_full_envelope_survives_and_only_lifecycle_fields_change(self):
        prior = envelope_row()
        write_queue(self.q, [prior])
        report = qlw.lifecycle_writeback(
            CPR_ID, dict(self.DEFER), queue_path=self.q, review_tic=682,
            writer="review-execute")

        rows = self.rows()
        self.assertEqual(len(rows), 2, "append-only: the prior row is untouched")
        self.assertEqual(rows[0], prior, "history row must never be rewritten")
        new = rows[1]

        # (a) every envelope field survives with its EXACT prior value
        for field in DROPPED_AT_682:
            self.assertIn(field, new, f"{field} must survive the writeback")
            self.assertEqual(new[field], prior[field])
        self.assertEqual(qlw.envelope_drops(prior, new), [])

        # (b) only lifecycle fields changed
        changed = {k for k in prior if new.get(k) != prior.get(k)}
        allowed = set(self.DEFER) | {"prior_status", "review_tic"}
        self.assertTrue(changed <= allowed, f"unexpected mutations: {changed - allowed}")

        # (c) the verdict actually landed
        self.assertEqual(new["status"], "enrichment_eligible")
        self.assertEqual(new["pending_class"], "evidence_insufficient")
        self.assertEqual(new["review_verdict"], "DEFER")
        self.assertEqual(new["review_tic"], 682)

        # (d) the report is honest about what it did
        s = report["summary"]
        self.assertTrue(s["post_assert_no_envelope_drop"])
        self.assertEqual(s["envelope_drops"], [])
        self.assertEqual(s["copied_forward_fields"], len(prior))
        self.assertGreaterEqual(s["field_count_after"], len(prior))
        self.assertEqual(s["append_via"], "atomic-append.sh")

    def test_writeback_stamps_provenance(self):
        write_queue(self.q, [envelope_row()])
        qlw.lifecycle_writeback(CPR_ID, dict(self.DEFER), queue_path=self.q,
                                review_tic=682, writer="review-execute")
        stamp = self.rows()[1]["lifecycle_writeback"]
        self.assertEqual(stamp["by"], "queue-lifecycle-writeback")
        self.assertEqual(stamp["writer"], "review-execute")
        self.assertEqual(stamp["prior_status"], "tic_gated")

    def test_promote_class_row_also_copies_forward(self):
        """Same mechanism, PROMOTE shape. emit_only so the tic-481 promote-writeback
        physics gate at the append boundary is not fired from a fixture."""
        prior = envelope_row(status="promotable")
        write_queue(self.q, [prior])
        report = qlw.lifecycle_writeback(
            CPR_ID, {"status": "promoted", "promoted_to": "cgg-ledger/ledger.md#slug",
                     "promoted_date": "2026-08-06", "review_verdict": "PROMOTE",
                     "review_confidence": 0.85},
            queue_path=self.q, review_tic=683, writer="review-execute", emit_only=True)
        row = report["row"]
        self.assertEqual(qlw.envelope_drops(prior, row), [])
        self.assertEqual(row["lesson"], prior["lesson"])
        self.assertEqual(row["status"], "promoted")
        self.assertFalse(report["summary"]["appended"])
        self.assertEqual(len(self.rows()), 1, "emit_only must not write")


# ===========================================================================
# Contract refusals — both arms of every documented conditional
# ===========================================================================

class TestRefusals(_TmpQueue):
    def test_no_prior_row_is_refused(self):
        write_queue(self.q, [envelope_row(cpr_id="cpr_someone_else")])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback("cpr_absent", {"status": "skipped"},
                                    queue_path=self.q)
        self.assertEqual(ctx.exception.reasons[0]["code"], "no_prior_row")

    def test_prior_row_present_is_accepted(self):
        write_queue(self.q, [envelope_row()])
        report = qlw.lifecycle_writeback(CPR_ID, {"status": "skipped"},
                                         queue_path=self.q, emit_only=True)
        self.assertEqual(report["row"]["status"], "skipped")

    def test_empty_payload_is_refused(self):
        write_queue(self.q, [envelope_row()])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(CPR_ID, {}, queue_path=self.q)
        self.assertEqual(ctx.exception.reasons[0]["code"], "empty_lifecycle_payload")

    def test_envelope_protected_field_is_refused(self):
        """A lifecycle writeback may not rewrite the lesson — that is a reviewed data
        repair, not a status flip."""
        write_queue(self.q, [envelope_row()])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "skipped", "lesson": "rewritten"}, queue_path=self.q)
        codes = {r["code"] for r in ctx.exception.reasons}
        self.assertIn("envelope_protected_field", codes)
        self.assertEqual(len(self.rows()), 1, "refusal must not write")

    def test_undeclared_field_is_refused_then_allowed_with_flag(self):
        write_queue(self.q, [envelope_row()])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(CPR_ID, {"status": "skipped", "wat": 1},
                                    queue_path=self.q)
        self.assertIn("undeclared_lifecycle_field",
                      {r["code"] for r in ctx.exception.reasons})
        # other arm: the audited escape hatch admits it
        report = qlw.lifecycle_writeback(
            CPR_ID, {"status": "skipped", "wat": 1}, queue_path=self.q,
            allow_fields=["wat"], emit_only=True)
        self.assertEqual(report["row"]["wat"], 1)

    def test_all_violations_reported_at_once(self):
        write_queue(self.q, [envelope_row()])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "skipped", "lesson": "x", "wat": 1},
                queue_path=self.q)
        self.assertEqual(len(ctx.exception.reasons), 2)

    def test_unresolvable_queue_is_refused(self):
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(CPR_ID, {"status": "skipped"},
                                    queue_path=self.dir / "absent.jsonl")
        self.assertEqual(ctx.exception.reasons[0]["code"], "queue_unresolved")

    def test_cli_refusal_exits_2_and_writes_nothing(self):
        write_queue(self.q, [envelope_row()])
        rc = qlw.main(["--cpr-id", CPR_ID, "--queue-path", str(self.q),
                       "--set", "lesson=rewritten"])
        self.assertEqual(rc, 2)
        self.assertEqual(len(self.rows()), 1)


# ===========================================================================
# Merge semantics — auto-stamps fire and are suppressed
# ===========================================================================

class TestMergeSemantics(_TmpQueue):
    def test_prior_status_autostamped_on_status_change(self):
        write_queue(self.q, [envelope_row(status="tic_gated")])
        r = qlw.lifecycle_writeback(CPR_ID, {"status": "enrichment_eligible"},
                                    queue_path=self.q, emit_only=True)
        self.assertEqual(r["row"]["prior_status"], "tic_gated")

    def test_prior_status_not_autostamped_when_status_unchanged(self):
        write_queue(self.q, [envelope_row(status="tic_gated")])
        r = qlw.lifecycle_writeback(CPR_ID, {"review_reasoning": "annotation only"},
                                    queue_path=self.q, emit_only=True)
        # carried forward from the envelope, NOT re-stamped to the current status
        self.assertEqual(r["row"]["prior_status"], "extracted")

    def test_caller_prior_status_wins(self):
        write_queue(self.q, [envelope_row(status="tic_gated")])
        r = qlw.lifecycle_writeback(
            CPR_ID, {"status": "skipped", "prior_status": "explicit"},
            queue_path=self.q, emit_only=True)
        self.assertEqual(r["row"]["prior_status"], "explicit")

    def test_review_tic_merged_when_absent(self):
        write_queue(self.q, [envelope_row()])
        r = qlw.lifecycle_writeback(CPR_ID, {"status": "skipped"}, queue_path=self.q,
                                    review_tic=683, emit_only=True)
        self.assertEqual(r["row"]["review_tic"], 683)

    def test_caller_review_tic_in_payload_wins(self):
        write_queue(self.q, [envelope_row()])
        r = qlw.lifecycle_writeback(CPR_ID, {"status": "skipped", "review_tic": 999},
                                    queue_path=self.q, review_tic=683, emit_only=True)
        self.assertEqual(r["row"]["review_tic"], 999)

    def test_dry_run_writes_nothing(self):
        write_queue(self.q, [envelope_row()])
        before = self.q.read_text(encoding="utf-8")
        qlw.lifecycle_writeback(CPR_ID, {"status": "skipped"}, queue_path=self.q,
                                dry_run=True)
        self.assertEqual(self.q.read_text(encoding="utf-8"), before)


# ===========================================================================
# Queue reading — latest-per-id, history gap, append paths
# ===========================================================================

class TestQueueReading(_TmpQueue):
    def test_latest_per_id_takes_the_last_matching_row(self):
        write_queue(self.q, [
            envelope_row(status="extracted"),
            envelope_row(cpr_id="cpr_noise"),
            envelope_row(status="tic_gated"),
        ])
        row, line, _ = qlw.latest_row_for_id(self.q, CPR_ID)
        self.assertEqual(row["status"], "tic_gated")
        self.assertEqual(line, 3)

    def test_unparseable_lines_are_skipped_and_counted(self):
        self.q.write_text(
            json.dumps(envelope_row(), separators=(",", ":")) + "\n"
            + '{"id": "' + CPR_ID + '", broken\n',
            encoding="utf-8")
        row, _, unparseable = qlw.latest_row_for_id(self.q, CPR_ID)
        self.assertEqual(row["status"], "tic_gated")
        self.assertEqual(unparseable, 1)

    def test_history_gap_empty_when_envelope_intact(self):
        write_queue(self.q, [envelope_row(status="extracted"), envelope_row()])
        self.assertEqual(qlw.history_field_gap(self.q, CPR_ID), [])

    def test_history_gap_surfaces_an_earlier_stripping(self):
        """The tic-682 aftermath shape: the authoritative row is already thin, so the
        writeback preserves it faithfully AND reports the pre-existing gap."""
        write_queue(self.q, [envelope_row(), thin_defer_row_682()])
        gap = qlw.history_field_gap(self.q, CPR_ID)
        for field in DROPPED_AT_682:
            self.assertIn(field, gap)
        report = qlw.lifecycle_writeback(CPR_ID, {"status": "skipped"},
                                         queue_path=self.q, emit_only=True)
        self.assertTrue(report["summary"]["history_field_gap"])

    def test_append_uses_atomic_append_script(self):
        write_queue(self.q, [envelope_row()])
        r = qlw.lifecycle_writeback(CPR_ID, {"status": "skipped"}, queue_path=self.q)
        self.assertEqual(r["summary"]["append_via"], "atomic-append.sh")
        self.assertEqual(len(self.rows()), 2)

    def test_append_falls_back_when_file_lacks_trailing_newline(self):
        """atomic-append.sh does not repair a truncated last line; the in-process path
        does. Both arms must produce a parseable JSONL file."""
        self.q.write_text(json.dumps(envelope_row(), separators=(",", ":")),
                          encoding="utf-8")  # NO trailing newline
        r = qlw.lifecycle_writeback(CPR_ID, {"status": "skipped"}, queue_path=self.q)
        self.assertEqual(r["summary"]["append_via"], "flock-inprocess")
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["status"], "skipped")
        self.assertEqual(qlw.envelope_drops(rows[0], rows[1]), [])


# ===========================================================================
# Field classification table (content, not engine)
# ===========================================================================

class TestFieldClasses(unittest.TestCase):
    def test_classification_splits_three_ways(self):
        ok, protected, unknown = qlw.classify_lifecycle_fields(
            {"status": 1, "lesson": 2, "wat": 3})
        self.assertEqual(ok, ["status"])
        self.assertEqual(protected, ["lesson"])
        self.assertEqual(unknown, ["wat"])

    def test_allow_field_moves_a_key_into_ok(self):
        ok, protected, unknown = qlw.classify_lifecycle_fields(
            {"lesson": 2}, allow_fields=["lesson"])
        self.assertEqual(ok, ["lesson"])
        self.assertEqual((protected, unknown), ([], []))

    def test_the_eight_dropped_fields_are_all_envelope_protected(self):
        for field in DROPPED_AT_682:
            self.assertIn(field, qlw.ENVELOPE_PROTECTED_FIELDS)
            self.assertNotIn(field, qlw.LIFECYCLE_MUTABLE_FIELDS)

    def test_verdict_fields_are_all_lifecycle_mutable(self):
        for field in ("status", "pending_class", "maturity_window_tics",
                      "review_verdict", "review_confidence", "review_reasoning",
                      "promoted_to", "re_eval_condition", "window_anchor_tic"):
            self.assertIn(field, qlw.LIFECYCLE_MUTABLE_FIELDS)


if __name__ == "__main__":
    unittest.main()
