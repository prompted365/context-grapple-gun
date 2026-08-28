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
history gap present/absent, validate-row PASS/REFUSE, dry-run vs write, and — for the
post-write effective-state recompile — clock explicit / clock from --review-tic / clock
resolved from the tic log / clock unresolvable (A2-724).

Isolation: every case builds its own queue.jsonl under a TemporaryDirectory and passes
it via the `queue_path` hook — nothing reads or writes the real federation queue.
Promote-class rows are exercised with `emit_only=True` so the tic-481 promote-writeback
physics gate at the atomic-append boundary is never fired against real auto-memory.

Run:  python3 -m unittest test_queue_lifecycle_writeback   (from cgg-runtime/scripts/)
"""
import contextlib
import importlib.util
import io
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


def stepper_envelope_row(cpr_id=CPR_ID, status="extracted"):
    """The shape a cpr-stepper advance actually copies forward: the envelope WITHOUT
    `review_tic`. The stepper must never stamp that field (it would falsely assert
    /review docket ownership and self-fence the row under the docket-race write
    guard), which is exactly why it cannot supply `--review-tic` (A2-724)."""
    row = envelope_row(cpr_id=cpr_id, status=status)
    row.pop("review_tic")
    return row


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

    def test_absorb_landing_family_is_declared(self):
        """The ABSORB family (MERGE/SUPERSEDE/absorb-as-stub Step-7 shape) writes
        without the escape hatch — its first live use (t689 stub absorb) refused
        fail-closed because the family was absent from the declared set."""
        write_queue(self.q, [envelope_row()])
        report = qlw.lifecycle_writeback(
            CPR_ID,
            {"status": "absorbed",
             "absorbed_reason": "malformed duplicate stub of cpr_twin (verify-twin)",
             "absorbed_tic": 689, "absorbed_date": "2026-08-09",
             "absorbed_by": "ent_homeskillet/review-689-pass-1"},
            queue_path=self.q, emit_only=True)
        self.assertEqual(report["row"]["status"], "absorbed")
        self.assertEqual(report["row"]["absorbed_tic"], 689)
        # copy-forward still holds: the envelope survives the absorb
        self.assertEqual(report["row"]["lesson"], envelope_row()["lesson"])

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


# ===========================================================================
# WRITE-SIDE TERMINAL VALVE (bk-cpr-stepper-docket-race-write-guard, tic 707)
# — the stepper-vs-verdict race lands as a REFUSAL, never a resurrection
# ===========================================================================

class TestTerminalValveGuard(_TmpQueue):
    def test_resurrection_over_promoted_is_refused(self):
        # the measured race shape: a stale stepper advance (extracted->tic_gated)
        # appended AFTER a concurrent /review PROMOTE landed
        write_queue(self.q, [envelope_row(status="promoted")])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "tic_gated", "advance_reason": "stale race"},
                queue_path=self.q, writer="cpr-stepper")
        codes = [r["code"] for r in ctx.exception.reasons]
        self.assertIn("terminal_state_resurrection", codes)
        self.assertEqual(len(self.rows()), 1)  # nothing appended

    def test_every_hard_terminal_status_is_guarded(self):
        for status in sorted(qlw.HARD_TERMINAL_STATUSES):
            write_queue(self.q, [envelope_row(status=status)])
            with self.assertRaises(qlw.LifecycleWritebackRefused):
                qlw.lifecycle_writeback(
                    CPR_ID, {"status": "extracted"}, queue_path=self.q)

    def test_deferred_is_suspensive_not_guarded(self):
        # `deferred` re-activates lawfully by design (SUSPENSIVE_STATUSES) —
        # the valve must NOT block a later row over it
        write_queue(self.q, [envelope_row(status="deferred")])
        report = qlw.lifecycle_writeback(
            CPR_ID, {"status": "enrichment_eligible",
                     "pending_class": "stability_window"},
            queue_path=self.q, writer="review-execute")
        self.assertEqual(report["summary"]["new_status"], "enrichment_eligible")
        self.assertEqual(len(self.rows()), 2)

    def test_terminal_to_terminal_stays_lawful(self):
        # reviewed reshaping (e.g. a down-lane SUPERSEDE over a promoted row)
        write_queue(self.q, [envelope_row(status="promoted")])
        report = qlw.lifecycle_writeback(
            CPR_ID, {"status": "superseded",
                     "absorbed_reason": "superseded by cpr_newer"},
            queue_path=self.q, writer="review-execute")
        self.assertEqual(report["summary"]["new_status"], "superseded")

    def test_metadata_annotation_on_terminal_row_passes(self):
        # no status change — annotating a terminal row is not a resurrection
        write_queue(self.q, [envelope_row(status="promoted")])
        report = qlw.lifecycle_writeback(
            CPR_ID, {"relations": {"refined_by": "cpr_child"}},
            queue_path=self.q, writer="review-execute")
        self.assertEqual(report["summary"]["new_status"], "promoted")

    def test_escape_hatch_allows_and_audits(self):
        write_queue(self.q, [envelope_row(status="promoted")])
        report = qlw.lifecycle_writeback(
            CPR_ID, {"status": "enrichment_eligible",
                     "pending_class": "feedback_required"},
            queue_path=self.q, writer="review-execute",
            allow_terminal_transition=True)
        self.assertEqual(report["summary"]["new_status"], "enrichment_eligible")
        landed = self.rows()[-1]
        self.assertTrue(landed["lifecycle_writeback"]["terminal_transition_allowed"])

    def test_validate_row_refuses_resurrection(self):
        write_queue(self.q, [envelope_row(status="promoted")])
        candidate = dict(envelope_row(status="promoted"))
        candidate["status"] = "tic_gated"
        res = qlw.validate_row(candidate, queue_path=self.q)
        self.assertEqual(res["verdict"], "REFUSE")
        self.assertTrue(res["terminal_state_resurrection"])
        self.assertIn("terminal_state_resurrection", res["reason"])

    def test_validate_row_passes_lawful_advance(self):
        write_queue(self.q, [envelope_row(status="extracted")])
        candidate = dict(envelope_row(status="extracted"))
        candidate["status"] = "tic_gated"
        res = qlw.validate_row(candidate, queue_path=self.q)
        self.assertEqual(res["verdict"], "PASS")
        self.assertFalse(res["terminal_state_resurrection"])

    def test_hard_terminal_set_excludes_suspensive(self):
        self.assertNotIn("deferred", qlw.HARD_TERMINAL_STATUSES)
        for s in ("promoted", "absorbed", "superseded", "rejected",
                  "dismissed", "resolved", "skipped"):
            self.assertIn(s, qlw.HARD_TERMINAL_STATUSES)


class TestTierVocabularyGuard(_TmpQueue):
    """Guarantee 6 — /review 708 off-enum rulings 1-4 (tic 708).

    Introduction of an off-enum confidence_tier is refused; unchanged
    carry-forward of a historical off-enum value stays lawful and disclosed
    (ruling 2); the admitted measured family is lawful (ruling 3); the same
    predicate runs in validate_row, including on birth rows.
    """

    def _prior(self, tier="tentative", status="extracted"):
        row = envelope_row(status=status)
        row["confidence_tier"] = tier
        write_queue(self.q, [row])
        return row

    def test_introduction_of_off_enum_is_refused(self):
        self._prior(tier="tentative")
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"stepper_annotation": "x", "confidence_tier": "observed"},
                queue_path=self.q, writer="test",
                allow_fields=["confidence_tier"])
        codes = [r["code"] for r in ctx.exception.reasons]
        self.assertIn("confidence_tier_off_enum", codes)
        self.assertEqual(len(self.rows()), 1)  # nothing appended

    def test_class_bleed_is_refused_and_named(self):
        self._prior(tier="tentative")
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"stepper_annotation": "x", "confidence_tier": "exact"},
                queue_path=self.q, writer="test",
                allow_fields=["confidence_tier"])
        msg = "; ".join(r["message"] for r in ctx.exception.reasons)
        self.assertIn("class_bleed", msg)

    def test_non_tier_marker_is_refused_and_named(self):
        self._prior(tier="tentative")
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"stepper_annotation": "x", "confidence_tier": "unknown"},
                queue_path=self.q, writer="test",
                allow_fields=["confidence_tier"])
        msg = "; ".join(r["message"] for r in ctx.exception.reasons)
        self.assertIn("non_tier_marker", msg)

    def test_admitted_measured_family_is_lawful(self):
        for value in ("measured", "measured_single_locus"):
            self._prior(tier="tentative")
            report = qlw.lifecycle_writeback(
                CPR_ID, {"stepper_annotation": "x", "confidence_tier": value},
                queue_path=self.q, writer="test",
                allow_fields=["confidence_tier"])
            self.assertEqual(self.rows()[-1]["confidence_tier"], value)
            self.assertTrue(report)

    def test_unchanged_carry_forward_is_lawful(self):
        self._prior(tier="observed")
        qlw.lifecycle_writeback(
            CPR_ID, {"stepper_annotation": "x", "confidence_tier": "observed"},
            queue_path=self.q, writer="test",
            allow_fields=["confidence_tier"])
        self.assertEqual(self.rows()[-1]["confidence_tier"], "observed")

    def test_clearing_to_none_is_lawful(self):
        self._prior(tier="observed")
        qlw.lifecycle_writeback(
            CPR_ID, {"stepper_annotation": "x", "confidence_tier": None},
            queue_path=self.q, writer="test",
            allow_fields=["confidence_tier"])
        self.assertIsNone(self.rows()[-1]["confidence_tier"])

    def test_validate_row_refuses_birth_off_enum(self):
        write_queue(self.q, [])
        candidate = envelope_row(cpr_id="cpr_fresh_birth_row_000000000000")
        candidate["confidence_tier"] = "observed"
        res = qlw.validate_row(candidate, queue_path=self.q)
        self.assertEqual(res["verdict"], "REFUSE")
        self.assertIn("confidence_tier_off_enum", res["reason"])

    def test_validate_row_passes_birth_lawful(self):
        write_queue(self.q, [])
        candidate = envelope_row(cpr_id="cpr_fresh_birth_row_000000000000")
        candidate["confidence_tier"] = "measured"
        res = qlw.validate_row(candidate, queue_path=self.q)
        self.assertEqual(res["verdict"], "PASS")

    def test_validate_row_refuses_introduction(self):
        self._prior(tier="tentative")
        candidate = envelope_row(status="extracted")
        candidate["confidence_tier"] = "high"
        res = qlw.validate_row(candidate, queue_path=self.q)
        self.assertEqual(res["verdict"], "REFUSE")
        self.assertTrue(res["confidence_tier_off_enum"])

    def test_validate_row_allows_carry_forward_with_disclosure(self):
        self._prior(tier="observed")
        candidate = envelope_row(status="extracted")
        candidate["confidence_tier"] = "observed"
        res = qlw.validate_row(candidate, queue_path=self.q)
        self.assertEqual(res["verdict"], "PASS")
        self.assertIn("carried forward unchanged", res["reason"])


class _RecompileZone(unittest.TestCase):
    """A fixture ZONE, not just a queue file.

    The recompile hook resolves both its compiler (`queue.parent/queue_state_compile.py`)
    and its fallback clock (`<audit-logs>/tics/*.jsonl`) RELATIVE TO THE QUEUE, so the
    fixture must carry the real `<audit-logs>/{cprs,tics}/` shape. A STUB compiler that
    records its argv stands in for the real one: it proves WHICH CLOCK reached the
    compiler without running a real compile against a fixture, and keeps the live
    projection untouched.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.al = Path(self.tmp.name) / "audit-logs"
        (self.al / "cprs").mkdir(parents=True)
        self.q = self.al / "cprs" / "queue.jsonl"
        self.argv_log = self.al / "cprs" / "compile-argv.json"
        (self.al / "cprs" / "queue_state_compile.py").write_text(
            "import json, sys\n"
            "from pathlib import Path\n"
            "Path(__file__).with_name('compile-argv.json').write_text(\n"
            "    json.dumps(sys.argv[1:]))\n",
            encoding="utf-8")

    def write_tic_log(self, *counters, name="2026-08-21.jsonl"):
        """Canonical tic events carrying `domain_counter_after` (the time authority)."""
        tic_dir = self.al / "tics"
        tic_dir.mkdir(parents=True, exist_ok=True)
        (tic_dir / name).write_text(
            "".join(json.dumps({"type": "tic", "count_mode": "counted",
                                "domain_counter_after": c}) + "\n" for c in counters),
            encoding="utf-8")

    def run_cli(self, *argv):
        """main() with both streams captured — the recompile speaks on stderr when it
        skips and on stdout when it lands."""
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            rc = qlw.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def compile_clock(self):
        """The `--current-tic` the stub compiler received, or None if it never ran."""
        if not self.argv_log.is_file():
            return None
        argv = json.loads(self.argv_log.read_text(encoding="utf-8"))
        return int(argv[argv.index("--current-tic") + 1])

    def rows(self):
        return [json.loads(ln) for ln in
                self.q.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ===========================================================================
# RECOMPILE CLOCK vs VERDICT FIELD (A2-724, cpr-stepper tics 723 + 724)
# — the hook keyed its clock on --review-tic, a field the stepper lane must
#   never pass, so it skipped on EVERY stepper write by construction
# ===========================================================================

class TestRecompileClockDecoupledFromVerdict(_RecompileZone):

    ADVANCE = ["--set", "status=tic_gated", "--set", "advance_reason=maturity discharged"]

    def test_current_tic_drives_the_recompile_without_stamping_the_row(self):
        """(a) The explicit clock reaches the compiler and touches NOTHING on the row —
        neither `review_tic` (the verdict field) nor `current_tic` (the same-named row
        field). A wrong tic log is seeded to prove the explicit flag outranks it."""
        write_queue(self.q, [stepper_envelope_row()])
        self.write_tic_log(999)
        rc, _, err = self.run_cli(
            "--cpr-id", CPR_ID, "--queue-path", str(self.q), "--writer", "cpr-stepper",
            "--current-tic", "724", *self.ADVANCE)

        self.assertEqual(rc, 0)
        self.assertEqual(self.compile_clock(), 724, "explicit clock must win")
        self.assertNotIn("SKIPPED", err)

        landed = self.rows()[-1]
        self.assertEqual(landed["status"], "tic_gated")
        self.assertNotIn("review_tic", landed,
                         "--current-tic must NOT stamp the verdict field")
        self.assertEqual(landed["current_tic"], stepper_envelope_row()["current_tic"],
                         "--current-tic is a clock, not a row write")

    def test_legacy_review_tic_only_call_recompiles_identically(self):
        """(b) Every existing review-execute call site is byte-for-byte unchanged: the
        verdict tic is still the clock AND still merges onto the row as `review_tic`."""
        write_queue(self.q, [envelope_row(status="promotable")])
        self.write_tic_log(999)
        rc, out, err = self.run_cli(
            "--cpr-id", CPR_ID, "--queue-path", str(self.q),
            "--writer", "review-execute", "--review-tic", "683",
            "--set", "status=skipped", "--set", "review_verdict=SKIP")

        self.assertEqual(rc, 0)
        self.assertEqual(self.compile_clock(), 683)
        self.assertNotIn("SKIPPED", err)
        self.assertIn("recompiled at tic 683", out)

        landed = self.rows()[-1]
        self.assertEqual(landed["review_tic"], 683, "verdict semantics must not change")
        self.assertEqual(landed["review_verdict"], "SKIP")

    def test_explicit_clock_outranks_review_tic_without_disturbing_the_verdict(self):
        """Both surfaces present and distinct: --current-tic sets the clock, --review-tic
        still lands as the verdict field."""
        write_queue(self.q, [envelope_row(status="extracted")])
        rc, _, _ = self.run_cli(
            "--cpr-id", CPR_ID, "--queue-path", str(self.q), "--review-tic", "683",
            "--current-tic", "724", "--set", "status=tic_gated")
        self.assertEqual(rc, 0)
        self.assertEqual(self.compile_clock(), 724)
        self.assertEqual(self.rows()[-1]["review_tic"], 683)

    def test_neither_flag_falls_back_to_the_resolved_canonical_tic(self):
        """(c) THE DEFECT ARM: a stepper advance carries no verdict tic at all. This
        used to SKIP the recompile every single pass; it now resolves the clock."""
        write_queue(self.q, [stepper_envelope_row()])
        self.write_tic_log(724)
        rc, out, err = self.run_cli(
            "--cpr-id", CPR_ID, "--queue-path", str(self.q), "--writer", "cpr-stepper",
            *self.ADVANCE)

        self.assertEqual(rc, 0)
        self.assertEqual(self.compile_clock(), 724, "the recompile must no longer skip")
        self.assertNotIn("SKIPPED", err)
        self.assertIn("resolved-from-tic-log", out)
        self.assertNotIn("review_tic", self.rows()[-1])

    def test_unresolvable_clock_skips_LOUDLY_and_still_lands_the_write(self):
        """The fail-soft arm: no flags AND no tic log. The recompile skips exactly as
        before — but says so loudly and names the cure — and the constitutional write
        still lands (a derived-cache miss must never block it)."""
        write_queue(self.q, [stepper_envelope_row()])
        rc, _, err = self.run_cli(
            "--cpr-id", CPR_ID, "--queue-path", str(self.q), "--writer", "cpr-stepper",
            *self.ADVANCE)

        self.assertEqual(rc, 0, "fail-soft: a clock miss does not fail the writeback")
        self.assertIsNone(self.compile_clock(), "the compiler must not run clockless")
        self.assertIn("effective-state recompile SKIPPED", err)
        self.assertIn("queue_state_compile.py compile --current-tic", err)
        self.assertEqual(len(self.rows()), 2, "the queue row still landed")

    def test_dry_run_and_emit_only_never_recompile(self):
        """Unchanged: no write, no derived-cache rebuild."""
        write_queue(self.q, [stepper_envelope_row()])
        self.write_tic_log(724)
        for flag in ("--dry-run", "--emit-only"):
            rc, _, _ = self.run_cli("--cpr-id", CPR_ID, "--queue-path", str(self.q),
                                    "--current-tic", "724", flag, *self.ADVANCE)
            self.assertEqual(rc, 0)
            self.assertIsNone(self.compile_clock(), f"{flag} must not recompile")

    # --- the resolver itself (reused, not reimplemented) ---------------------

    def test_resolver_reads_domain_counter_after_not_the_raw_row_count(self):
        """bk-cpr-extract-tic-count-drift discipline: the authority is the LATEST
        `domain_counter_after`, never a count of `type=tic` rows (which would stamp a
        tic in the past here, and in the future on the live log)."""
        write_queue(self.q, [stepper_envelope_row()])
        self.write_tic_log(721, 722, 723, name="2026-08-20.jsonl")
        self.write_tic_log(724, name="2026-08-21.jsonl")
        self.assertEqual(qlw.resolve_recompile_tic(self.q), 724)

    def test_resolver_returns_none_when_the_tic_log_is_absent(self):
        write_queue(self.q, [stepper_envelope_row()])
        self.assertIsNone(qlw.resolve_recompile_tic(self.q))

    def test_resolver_returns_none_on_an_empty_tic_log(self):
        write_queue(self.q, [stepper_envelope_row()])
        self.write_tic_log()
        self.assertIsNone(qlw.resolve_recompile_tic(self.q),
                          "a zero clock is not a clock")



class RuledTerminalFieldSetDeclaredTic741(unittest.TestCase):
    """/review 741 Q4 (Architect-ratified, recommended verbatim): the RULED terminal
    field set (A1-739 minimal writeback set, forward-only) is DECLARED in
    LIFECYCLE_MUTABLE_FIELDS — a mandatory set must not need the --allow-field
    valve on every pass (t739->740->741 = two passes through the escape)."""

    RULED = ("review_ratified_by", "adjudicated_at_tic", "absorbed_into",
             "absorbed_reason", "landing_kind")

    def test_ruled_set_classifies_ok_without_allow_field(self):
        lifecycle = {k: "x" for k in self.RULED}
        lifecycle["status"] = "promoted"
        ok, protected, unknown = qlw.classify_lifecycle_fields(lifecycle)
        self.assertEqual(unknown, [], "ruled field(s) still undeclared: %r" % unknown)
        self.assertEqual(protected, [])
        for field in self.RULED:
            self.assertIn(field, qlw.LIFECYCLE_MUTABLE_FIELDS)

    def test_unruled_field_still_refuses_without_allow_field(self):
        ok, protected, unknown = qlw.classify_lifecycle_fields(
            {"status": "promoted", "not_a_ruled_field_tic741": 1})
        self.assertEqual(unknown, ["not_a_ruled_field_tic741"])

    def test_envelope_identity_stays_protected(self):
        ok, protected, unknown = qlw.classify_lifecycle_fields(
            {"status": "promoted", "lesson": "retcon attempt"})
        self.assertEqual(protected, ["lesson"])

if __name__ == "__main__":
    unittest.main()


# ── tic 744 (/review 744 Q2, A1-744 HIGH / F-742-L1 n=2): mutated_fields is a VALUE diff ──
def test_restated_field_is_not_a_mutation_tic744():
    """RED (the retired shape): mutated_fields = sorted(lifecycle) listed review_tic as
    mutated when the caller passed the same value the row already carried (743->743 on
    four t743 promotes), forcing a value-read at the stepper's Check B. GREEN: only
    fields whose VALUE moved are mutated; the unchanged-but-passed field is RESTATED,
    kept visible beside it. PAID at first live fire: the /review 744 Q1 writeback
    stamped restated_fields=['review_tic'] with review_tic absent from mutated_fields."""
    import importlib.util, pathlib
    here = pathlib.Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("qlw744", here / "queue-lifecycle-writeback.py")
    qlw = importlib.util.module_from_spec(spec); spec.loader.exec_module(qlw)
    prior = {"id": "cpr_x", "status": "extracted", "lesson": "L", "source": "s", "birth_tic": 741,
             "review_tic": 744, "subsystem": "t"}
    row, report = qlw.build_lifecycle_row(
        prior, {"status": "promoted", "review_tic": 744, "adjudicated_at_tic": 744},
        writer="test", now="2026-08-27T00:00:00+00:00")
    lw = row["lifecycle_writeback"]
    assert "review_tic" not in lw["mutated_fields"], lw
    assert lw["restated_fields"] == ["review_tic"], lw
    # amended /review 746 (A3-746): the ROW stamp now splits ADDED from MUTATED too
    assert lw["mutated_fields"] == ["status"], lw
    assert lw["added_fields"] == ["adjudicated_at_tic"], lw
    assert report["restated_fields"] == ["review_tic"]
    assert report["mutated_fields"] == ["status"]              # among pre-existing keys
    assert "adjudicated_at_tic" in report["added_fields"]
    # RED reproduced inline: the retired stamp would have listed all three as mutated
    assert sorted({"status", "review_tic", "adjudicated_at_tic"}) != lw["mutated_fields"]



def test_row_stamp_splits_added_from_mutated_tic746():
    """RED (the retired shape, A1-745 -> A3-746 at n=2): the ROW stamp listed every
    value-changed field under mutated_fields, so a verdict writeback that ADDED 15
    fields and CHANGED one read as 16 mutations (93.8% added) — while the writer's
    SUMMARY already split them (mutated ∩ before_keys / added). GREEN: the row stamp
    carries the same split — mutated_fields = value-changed AND pre-existing;
    added_fields = value-changed AND new; restated beside both."""
    import importlib.util, pathlib
    here = pathlib.Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("qlw746", here / "queue-lifecycle-writeback.py")
    qlw = importlib.util.module_from_spec(spec); spec.loader.exec_module(qlw)
    prior = {"id": "cpr_y", "status": "extracted", "lesson": "L", "source": "s", "birth_tic": 743,
             "review_tic": 746, "subsystem": "t"}
    lifecycle = {"status": "promoted", "review_tic": 746, "adjudicated_at_tic": 746,
                 "review_verdict": "PROMOTE", "promoted_to": "ledger.md#x", "landing_kind": "refinement_ray"}
    row, report = qlw.build_lifecycle_row(prior, lifecycle, writer="test", now="2026-08-28T00:00:00+00:00")
    lw = row["lifecycle_writeback"]
    assert lw["mutated_fields"] == ["status"], lw                       # the ONE genuine value change
    assert lw["added_fields"] == sorted(["adjudicated_at_tic", "review_verdict", "promoted_to", "landing_kind"]), lw
    assert lw["restated_fields"] == ["review_tic"], lw
    # row stamp == summary split (the two names now compute one thing one way)
    assert lw["mutated_fields"] == report["mutated_fields"]
    # the SUMMARY's added_fields also counts the writer's OWN stamps — name them exactly
    assert set(report["added_fields"]) - set(lw["added_fields"]) == {"lifecycle_writeback", "updated_at", "prior_status"}
    assert set(lw["added_fields"]) <= set(report["added_fields"])
    # NEGATIVE CONTROL — the retired conflation is NOT what the row carries
    assert set(lw["mutated_fields"]) != {"status", "adjudicated_at_tic", "review_verdict", "promoted_to", "landing_kind"}
