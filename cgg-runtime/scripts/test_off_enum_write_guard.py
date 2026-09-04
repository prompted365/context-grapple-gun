#!/usr/bin/env python3
"""Negative-control fixtures for the ENUM VOCABULARY GUARD on `pending_class` and
`landing_kind` at queue-lifecycle-writeback.py (guarantee 7).

RULED: /review 767 Q4, B2 wave 5, backlog row
`bk-off-enum-drift-field-generic-writer-topology`. Admission receipt:
audit-logs/governance/backlog-gunslinger-hoist/B2-wave-5-tic767.json.

WHY: A4-709 measured the off-enum drift adjudicated at /review 708 as FIELD-GENERIC
while the physics shipped at 708 was AXIS-SPECIFIC — confidence_tier guarded,
`pending_class` (17 ids / 4 off-table values, latest-per-id) and `landing_kind`
UNGUARDED, `lifecycle_state` the zero-drift single-governed-writer control. This file
is the discriminating proof for the two newly-guarded fields.

THE THREE ARMS (the third is what makes the first two mean anything):
  1. REFUSED — a fixture off-table value on a NEW write is refused with a typed
     code (`pending_class_off_enum` / `landing_kind_off_enum`) naming the contract
     file and /review as the minting authority; nothing is appended.
  2. WAIVED  — `--waive-enum-guard <field>` admits the same value and the row
     carries an AUDIT STAMP at `lifecycle_writeback.enum_guard_waived`.
  3. REVERTED-GUARD CONTROL — the guard is monkeypatched OFF (the field's contract
     binding removed from `ENUM_GUARDED_FIELDS`) and the SAME bad value sails
     through and lands in the queue. This proves the tests discriminate: they fail
     because of the guard, not because of the fixture.

Plus the carry-forward arm, which is the ruling's other half: HISTORICAL ROWS ARE
NEVER RE-TYPED — an unchanged off-table value carried forward is LAWFUL and merely
disclosed on stderr.

DOES NOT SATISFY (rider carried verbatim from the ruling): "per-field rulings on the
17 historical off-table ids (that is /review's 768+ docket); guards at any writer
other than queue-lifecycle-writeback.py"

Isolation: every case builds its own queue.jsonl under a TemporaryDirectory and passes
it via the `queue_path` hook — nothing reads or writes the real federation queue.
Promote/absorb-class rows are exercised with `emit_only=True` so the tic-481
promote-writeback physics gate at the atomic-append boundary is never fired.

Run:  python3 -m unittest test_off_enum_write_guard   (from cgg-runtime/scripts/)
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
    "queue_lifecycle_writeback_enum_guard",
    os.path.join(_HERE, "queue-lifecycle-writeback.py"),
)
qlw = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(qlw)

CPR_ID = "cpr_off_enum_guard_fixture_tic767"

# Off-table fixtures drawn from the MEASURED corpus, never invented:
# `architect_ruling` is measured x7 in the reviews-lane decision rows (the t767 E4
# census) and RULED at /review 768 round 2 to be a DIFFERENT QUANTITY sharing the
# pending_class token (rename owed at that writer) — it therefore NEVER enters this
# enum, making it the stable off-table exemplar after schema_incomplete was ACCRETED
# lawful at the same round. `rejected_scope` is the landing_kind value RETIRED by
# /review 751 Q5 after measuring ZERO instances in the whole queue.
OFF_TABLE_PENDING_CLASS = "architect_ruling"
OFF_TABLE_LANDING_KIND = "rejected_scope"


def envelope_row(cpr_id=CPR_ID, status="enrichment_eligible", **extra):
    """A full envelope in the shape queue.jsonl carries. Deliberately WITHOUT
    pending_class / landing_kind so each case declares its own prior state."""
    row = {
        "id": cpr_id, "status": status, "type": "cogpr",
        "lesson": "A vocabulary that depends on producer restraint is not a "
                  "vocabulary; it is a habit.",
        "source": "harpoon build citizen, B2 wave 5",
        "source_date": "2026-09-03", "subsystem": "governance/queue",
        "recommended_scopes": ["cgg-ledger"],
        "birth_tic": 760, "birth_rung": "federation",
        "confidence_tier": "tentative", "lesson_type": "mechanism",
        "dedup_hash": "0f7e11aa22bb33cc", "extracted_at": "2026-09-03T00:00:00Z",
        "extracted_by": "cpr-extract", "id_origin": "hash",
        "maturity_window_tics": 3, "advanced_tic": 764,
    }
    row.update(extra)
    return row


def write_queue(path, rows):
    path.write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows),
        encoding="utf-8")


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
# The contract files are the CONTENT half (engine-content separation)
# ===========================================================================

class TestContractsAreTheContent(unittest.TestCase):
    def test_both_fields_bind_to_a_contract_file_that_loads(self):
        self.assertEqual(set(qlw.ENUM_GUARDED_FIELDS),
                         {"pending_class", "landing_kind"})
        for field, filename in qlw.ENUM_GUARDED_FIELDS.items():
            path = qlw._CONTRACTS_DIR / filename
            self.assertTrue(path.is_file(), f"{field} contract missing: {path}")
            self.assertTrue(qlw.FIELD_ENUMS[field], f"{field} enum is empty")

    def test_pending_class_carries_exactly_the_five_ruled_values(self):
        """RULED /review 663 at three (the DEFER generators); ACCRETED to five at
        /review 768 round 2 (evidence_scoped + schema_incomplete — the BIRTH-minted
        classes, 'Admit + rename'). A stale three-value expectation reads a FALSE
        off-table anomaly — the same currency rider the landing_kind arm carries."""
        self.assertEqual(
            qlw.FIELD_ENUMS["pending_class"],
            frozenset({"feedback_required", "stability_window",
                       "evidence_insufficient", "evidence_scoped",
                       "schema_incomplete"}))
        self.assertNotIn(OFF_TABLE_PENDING_CLASS, qlw.FIELD_ENUMS["pending_class"])

    def test_landing_kind_carries_the_eight_accreted_values(self):
        """RULED /review 751 Q5 at six; ACCRETED to eight at /review 767 Q3
        (new_anchor + refinement_tail). A stale six-value expectation reads a FALSE
        off-table anomaly — the currency rider this increment was dispatched with."""
        self.assertEqual(
            qlw.FIELD_ENUMS["landing_kind"],
            frozenset({"concede_local", "reinforce_existing",
                       "content_empty_stub_twin", "refinement_ray", "typed_guard",
                       "resubmit_higher", "new_anchor", "refinement_tail"}))
        self.assertNotIn(OFF_TABLE_LANDING_KIND, qlw.FIELD_ENUMS["landing_kind"])

    def test_landing_kind_contract_encodes_open_by_review(self):
        """Load-bearing: the schema must NOT close the vocabulary. The contract
        carries the accretion rule and the guard's refusal quotes it."""
        contract = qlw.ENUM_CONTRACTS["landing_kind"]
        self.assertIn("OPEN-BY-/REVIEW", contract["accretion"])
        self.assertIn("never closed by schema", contract["accretion"].lower())
        self.assertIn("/review", contract["minting_authority"])
        self.assertIn("NEVER CLOSED BY SCHEMA", contract["minting_authority"])

    def test_pending_class_contract_carries_no_stale_three_claim(self):
        """/review 771 Q15a (F-771-W9A-4 second half): the guard's most-read surface
        — its typed refusal, interpolated verbatim from this contract — must not
        assert 'CLOSED at the ruled three' while listing five lawful values. The
        stale-three prose generated the falsified wave-9 rowA premise; this arm
        pins the cure so the contradiction cannot silently return."""
        contract = qlw.ENUM_CONTRACTS["pending_class"]
        blob = json.dumps(contract)
        self.assertNotIn("the ruled three", blob)
        self.assertIn("FIVE", blob)

    def test_pending_class_contract_declares_its_closed_posture_and_authority(self):
        contract = qlw.ENUM_CONTRACTS["pending_class"]
        self.assertIn("CLOSED", contract["accretion"])
        self.assertIn("/review is the minting authority",
                      contract["accretion"])

    def test_refusal_message_names_contract_file_and_review(self):
        msg = qlw.enum_refusal_message("landing_kind", OFF_TABLE_LANDING_KIND)
        self.assertIn("contracts/landing-kind-enum-v1.json", msg)
        self.assertIn("MINTING AUTHORITY", msg)
        self.assertIn("/review", msg)
        msg = qlw.enum_refusal_message("pending_class", OFF_TABLE_PENDING_CLASS)
        self.assertIn("contracts/pending-class-enum-v1.json", msg)
        self.assertIn("/review", msg)

    def test_both_contracts_carry_the_ruling_rider_verbatim(self):
        rider = ("per-field rulings on the 17 historical off-table ids (that is "
                 "/review's 768+ docket); guards at any writer other than "
                 "queue-lifecycle-writeback.py")
        for field in qlw.ENUM_GUARDED_FIELDS:
            self.assertEqual(qlw.ENUM_CONTRACTS[field]["does_not_satisfy"], rider)


class TestClassifyPredicate(unittest.TestCase):
    def test_absence_is_lawful_on_both_fields(self):
        for field in qlw.ENUM_GUARDED_FIELDS:
            self.assertEqual(qlw.classify_enum_value(field, None), "lawful")

    def test_members_are_lawful(self):
        self.assertEqual(
            qlw.classify_enum_value("pending_class", "feedback_required"), "lawful")
        self.assertEqual(
            qlw.classify_enum_value("landing_kind", "new_anchor"), "lawful")

    def test_off_table_and_non_strings_are_off_enum(self):
        self.assertEqual(
            qlw.classify_enum_value("pending_class", OFF_TABLE_PENDING_CLASS),
            "off_enum")
        self.assertEqual(qlw.classify_enum_value("landing_kind", 7), "off_enum")

    def test_an_unbound_field_is_unguarded_not_refused(self):
        """lifecycle_state is the A4-709 zero-drift control and carries no contract
        at tic 767 — the predicate must say so, not silently refuse it."""
        self.assertEqual(
            qlw.classify_enum_value("lifecycle_state", "obligated_waiting"),
            "unguarded")


# ===========================================================================
# ARM 1 — the off-table INTRODUCTION is REFUSED
# ===========================================================================

class TestArm1OffTableIntroductionRefused(_TmpQueue):
    def test_pending_class_off_table_is_refused_and_nothing_is_appended(self):
        write_queue(self.q, [envelope_row()])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "enrichment_eligible",
                         "pending_class": OFF_TABLE_PENDING_CLASS},
                queue_path=self.q, writer="test")
        codes = [r["code"] for r in ctx.exception.reasons]
        self.assertIn("pending_class_off_enum", codes)
        self.assertEqual(len(self.rows()), 1)  # nothing appended

    def test_landing_kind_off_table_is_refused(self):
        write_queue(self.q, [envelope_row(status="promotable")])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "promoted", "review_verdict": "PROMOTE",
                         "adjudicated_at_tic": 767,
                         "landing_kind": OFF_TABLE_LANDING_KIND},
                queue_path=self.q, writer="test", emit_only=True)
        codes = [r["code"] for r in ctx.exception.reasons]
        self.assertIn("landing_kind_off_enum", codes)

    def test_the_refusal_names_the_contract_and_the_minting_authority(self):
        write_queue(self.q, [envelope_row()])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"pending_class": OFF_TABLE_PENDING_CLASS},
                queue_path=self.q, writer="test")
        msg = "; ".join(r["message"] for r in ctx.exception.reasons)
        self.assertIn("contracts/pending-class-enum-v1.json", msg)
        self.assertIn("MINTING AUTHORITY", msg)
        self.assertIn("--waive-enum-guard pending_class", msg)

    def test_both_fields_report_their_violations_at_once(self):
        """An applier fixing one field per run is the recovery loop the generator
        fix exists to end — both refusals arrive in the same raise."""
        write_queue(self.q, [envelope_row(status="promotable")])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "promoted",
                         "pending_class": OFF_TABLE_PENDING_CLASS,
                         "landing_kind": OFF_TABLE_LANDING_KIND},
                queue_path=self.q, writer="test", emit_only=True)
        codes = sorted(r["code"] for r in ctx.exception.reasons)
        self.assertEqual(codes, ["landing_kind_off_enum", "pending_class_off_enum"])

    def test_a_non_string_value_is_refused(self):
        write_queue(self.q, [envelope_row()])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"pending_class": ["feedback_required"]},
                queue_path=self.q, writer="test")
        self.assertIn("pending_class_off_enum",
                      [r["code"] for r in ctx.exception.reasons])

    def test_lawful_members_pass_through_untouched(self):
        for value in sorted(qlw.FIELD_ENUMS["pending_class"]):
            write_queue(self.q, [envelope_row()])
            report = qlw.lifecycle_writeback(
                CPR_ID, {"status": "enrichment_eligible", "pending_class": value},
                queue_path=self.q, writer="test")
            self.assertEqual(report["row"]["pending_class"], value)

    def test_every_ruled_landing_kind_is_admitted(self):
        for value in sorted(qlw.FIELD_ENUMS["landing_kind"]):
            write_queue(self.q, [envelope_row(status="promotable")])
            report = qlw.lifecycle_writeback(
                CPR_ID, {"status": "promoted", "review_verdict": "PROMOTE",
                         "adjudicated_at_tic": 767, "landing_kind": value},
                queue_path=self.q, writer="test", emit_only=True)
            self.assertEqual(report["row"]["landing_kind"], value)

    def test_cli_refusal_exits_2_and_writes_nothing(self):
        write_queue(self.q, [envelope_row()])
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = qlw.main(["--cpr-id", CPR_ID, "--queue-path", str(self.q),
                           "--set", f"pending_class={OFF_TABLE_PENDING_CLASS}"])
        self.assertEqual(rc, 2)
        self.assertIn("pending_class_off_enum", buf.getvalue())
        self.assertEqual(len(self.rows()), 1)


# ===========================================================================
# ARM 2 — the audited waive ADMITS, and the row carries the stamp
# ===========================================================================

class TestArm2WaiveAdmitsWithAuditStamp(_TmpQueue):
    def test_waive_admits_and_stamps_the_row(self):
        write_queue(self.q, [envelope_row()])
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            report = qlw.lifecycle_writeback(
                CPR_ID, {"status": "enrichment_eligible",
                         "pending_class": OFF_TABLE_PENDING_CLASS},
                queue_path=self.q, writer="test",
                waive_enum_guard=("pending_class",))
        landed = self.rows()[-1]
        self.assertEqual(landed["pending_class"], OFF_TABLE_PENDING_CLASS)
        self.assertEqual(
            landed["lifecycle_writeback"]["enum_guard_waived"],
            {"pending_class": OFF_TABLE_PENDING_CLASS})
        self.assertIn("ENUM-GUARD-WAIVE-NOTICE", buf.getvalue())
        self.assertEqual(report["row"]["pending_class"], OFF_TABLE_PENDING_CLASS)

    def test_waive_is_per_field_and_does_not_leak_to_the_sibling(self):
        write_queue(self.q, [envelope_row(status="promotable")])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "promoted",
                         "pending_class": OFF_TABLE_PENDING_CLASS,
                         "landing_kind": OFF_TABLE_LANDING_KIND},
                queue_path=self.q, writer="test", emit_only=True,
                waive_enum_guard=("pending_class",))
        codes = [r["code"] for r in ctx.exception.reasons]
        self.assertEqual(codes, ["landing_kind_off_enum"])

    def test_an_unwaived_write_carries_no_stamp(self):
        """The stamp is evidence the hatch FIRED — it must be absent otherwise."""
        write_queue(self.q, [envelope_row()])
        qlw.lifecycle_writeback(
            CPR_ID, {"status": "enrichment_eligible",
                     "pending_class": "feedback_required"},
            queue_path=self.q, writer="test")
        self.assertNotIn("enum_guard_waived",
                         self.rows()[-1]["lifecycle_writeback"])

    def test_cli_waive_flag_admits(self):
        write_queue(self.q, [envelope_row()])
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = qlw.main(["--cpr-id", CPR_ID, "--queue-path", str(self.q),
                           "--set", f"pending_class={OFF_TABLE_PENDING_CLASS}",
                           "--waive-enum-guard", "pending_class",
                           "--emit-only"])
        self.assertEqual(rc, 0)
        self.assertIn("ENUM-GUARD-WAIVE-NOTICE", buf.getvalue())


# ===========================================================================
# ARM 3 — the REVERTED-GUARD control: does the test discriminate?
# ===========================================================================

class TestArm3RevertedGuardControl(_TmpQueue):
    """Revert the cure and watch the exact predicted breakage.

    With the field's contract binding removed from ENUM_GUARDED_FIELDS the guard
    loop never reaches the field, `classify_enum_value` reports it "unguarded", and
    the SAME off-table value that Arm 1 refuses lands in the queue. If this arm ever
    starts refusing, the tests above are passing for a reason other than the guard.
    """

    @contextlib.contextmanager
    def _guard_reverted(self, field):
        saved_fields = dict(qlw.ENUM_GUARDED_FIELDS)
        saved_enums = dict(qlw.FIELD_ENUMS)
        qlw.ENUM_GUARDED_FIELDS.pop(field)
        qlw.FIELD_ENUMS.pop(field)
        try:
            yield
        finally:
            qlw.ENUM_GUARDED_FIELDS.clear()
            qlw.ENUM_GUARDED_FIELDS.update(saved_fields)
            qlw.FIELD_ENUMS.clear()
            qlw.FIELD_ENUMS.update(saved_enums)

    def test_reverted_guard_lets_the_bad_pending_class_through(self):
        write_queue(self.q, [envelope_row()])
        with self._guard_reverted("pending_class"):
            self.assertEqual(
                qlw.classify_enum_value("pending_class", OFF_TABLE_PENDING_CLASS),
                "unguarded")
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "enrichment_eligible",
                         "pending_class": OFF_TABLE_PENDING_CLASS},
                queue_path=self.q, writer="test")
        landed = self.rows()[-1]
        self.assertEqual(landed["pending_class"], OFF_TABLE_PENDING_CLASS)
        self.assertNotIn("enum_guard_waived", landed["lifecycle_writeback"])

    def test_reverted_guard_lets_the_bad_landing_kind_through(self):
        write_queue(self.q, [envelope_row(status="promotable")])
        with self._guard_reverted("landing_kind"):
            report = qlw.lifecycle_writeback(
                CPR_ID, {"status": "promoted", "review_verdict": "PROMOTE",
                         "adjudicated_at_tic": 767,
                         "landing_kind": OFF_TABLE_LANDING_KIND},
                queue_path=self.q, writer="test", emit_only=True)
        self.assertEqual(report["row"]["landing_kind"], OFF_TABLE_LANDING_KIND)

    def test_the_guard_is_restored_after_the_control(self):
        """The control must not leak — Arm 1 has to still refuse afterwards."""
        write_queue(self.q, [envelope_row()])
        with self._guard_reverted("pending_class"):
            pass
        with self.assertRaises(qlw.LifecycleWritebackRefused):
            qlw.lifecycle_writeback(
                CPR_ID, {"pending_class": OFF_TABLE_PENDING_CLASS},
                queue_path=self.q, writer="test")


# ===========================================================================
# The ruling's other half — HISTORICAL ROWS ARE NEVER RE-TYPED
# ===========================================================================

class TestHistoricalCarryForwardStaysLawful(_TmpQueue):
    def test_unchanged_off_table_carry_forward_is_lawful_and_disclosed(self):
        """The shape of all 17 measured off-table pending_class ids: they advance
        without friction, and the notice is the disclosure."""
        write_queue(self.q, [envelope_row(
            pending_class=OFF_TABLE_PENDING_CLASS)])
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "tic_gated",
                         "pending_class": OFF_TABLE_PENDING_CLASS},
                queue_path=self.q, writer="test")
        self.assertEqual(self.rows()[-1]["pending_class"],
                         OFF_TABLE_PENDING_CLASS)
        self.assertIn("ENUM-CARRY-NOTICE", buf.getvalue())
        self.assertIn("never re-typed", buf.getvalue())

    def test_a_row_that_does_not_touch_the_field_is_untouched(self):
        """A historical off-table carrier advanced WITHOUT naming the field is
        copied forward silently — the guard fires on writes, not on presence."""
        write_queue(self.q, [envelope_row(
            pending_class=OFF_TABLE_PENDING_CLASS)])
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "tic_gated"},
                queue_path=self.q, writer="test")
        self.assertEqual(self.rows()[-1]["pending_class"],
                         OFF_TABLE_PENDING_CLASS)
        self.assertNotIn("ENUM-CARRY-NOTICE", buf.getvalue())

    def test_moving_a_historical_off_table_value_to_ANOTHER_off_table_value_refuses(self):
        """Carry-forward is exemption for the SAME value, never a licence to
        re-coin. Re-typing a historical id is /review's 768+ docket, not a write."""
        write_queue(self.q, [envelope_row(pending_class="design_required")])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"pending_class": OFF_TABLE_PENDING_CLASS},
                queue_path=self.q, writer="test")
        self.assertIn("pending_class_off_enum",
                      [r["code"] for r in ctx.exception.reasons])

    def test_repairing_a_historical_off_table_value_to_a_ruled_one_is_lawful(self):
        """The forward path stays open: an off-table carrier CAN be moved onto the
        ruled vocabulary without a waive."""
        write_queue(self.q, [envelope_row(pending_class=OFF_TABLE_PENDING_CLASS)])
        qlw.lifecycle_writeback(
            CPR_ID, {"pending_class": "evidence_insufficient"},
            queue_path=self.q, writer="test")
        self.assertEqual(self.rows()[-1]["pending_class"], "evidence_insufficient")


# ===========================================================================
# --validate-row parity (the preflight face of the SAME boundary;
# cpr-stepper.md:261 instructs the stepper to use it)
# ===========================================================================

class TestValidateRowParity(_TmpQueue):
    def test_validate_row_refuses_an_off_table_introduction(self):
        write_queue(self.q, [envelope_row()])
        candidate = envelope_row(pending_class=OFF_TABLE_PENDING_CLASS)
        res = qlw.validate_row(candidate, queue_path=self.q)
        self.assertEqual(res["verdict"], "REFUSE")
        self.assertEqual(res["enum_off_table"],
                         {"pending_class": OFF_TABLE_PENDING_CLASS})
        self.assertIn("pending_class_off_enum", res["reason"])

    def test_validate_row_passes_unchanged_carry_forward(self):
        write_queue(self.q, [envelope_row(pending_class=OFF_TABLE_PENDING_CLASS)])
        candidate = envelope_row(pending_class=OFF_TABLE_PENDING_CLASS)
        res = qlw.validate_row(candidate, queue_path=self.q)
        self.assertEqual(res["verdict"], "PASS")

    def test_validate_row_refuses_a_birth_row_off_table_value(self):
        write_queue(self.q, [])
        candidate = envelope_row(cpr_id="cpr_fresh_birth_row_tic767",
                                 landing_kind=OFF_TABLE_LANDING_KIND)
        res = qlw.validate_row(candidate, queue_path=self.q)
        self.assertEqual(res["verdict"], "REFUSE")
        self.assertIn("landing_kind_off_enum", res["reason"])

    def test_validate_row_passes_a_lawful_birth_row(self):
        write_queue(self.q, [])
        candidate = envelope_row(cpr_id="cpr_fresh_birth_row_tic767",
                                 landing_kind="refinement_ray")
        res = qlw.validate_row(candidate, queue_path=self.q)
        self.assertEqual(res["verdict"], "PASS")

    def test_validate_row_cli_exits_3(self):
        write_queue(self.q, [envelope_row()])
        candidate = envelope_row(pending_class=OFF_TABLE_PENDING_CLASS)
        rc = qlw.main(["--validate-row", json.dumps(candidate),
                       "--queue-path", str(self.q)])
        self.assertEqual(rc, 3)


# ===========================================================================
# Coexistence with the guards already at this boundary
# ===========================================================================

class TestCoexistenceWithExistingPhysics(_TmpQueue):
    def test_presence_check_still_fires_first_on_an_absent_landing_kind(self):
        """VERDICT_REQUIRED_FIELDS (presence, /review 765 Q2) and this guard
        (VALUE, /review 767 Q4) are complements, not rivals — A16-764's gap. An
        ABSENT landing_kind refuses as mandatory_terminal_field_missing; an
        OFF-TABLE one refuses as landing_kind_off_enum."""
        write_queue(self.q, [envelope_row(status="promotable")])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "promoted", "review_verdict": "PROMOTE",
                         "adjudicated_at_tic": 767},
                queue_path=self.q, emit_only=True)
        self.assertIn("mandatory_terminal_field_missing",
                      [r["code"] for r in ctx.exception.reasons])

    def test_landing_kind_is_still_a_declared_lifecycle_mutable_field(self):
        self.assertIn("landing_kind", qlw.LIFECYCLE_MUTABLE_FIELDS)
        self.assertIn("pending_class", qlw.LIFECYCLE_MUTABLE_FIELDS)

    def test_the_tier_guard_is_untouched_by_this_increment(self):
        """No-regression tripwire: guarantee 6 still refuses its own class."""
        row = envelope_row()
        write_queue(self.q, [row])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"stepper_annotation": "x", "confidence_tier": "observed"},
                queue_path=self.q, allow_fields=["confidence_tier"])
        self.assertIn("confidence_tier_off_enum",
                      [r["code"] for r in ctx.exception.reasons])


# ===========================================================================
# WAVE 9 rowA (/review 771 round 4 Q12, B2-wave-9-SIGNED-tic771.json) — the
# CURRENCY arm. The wave-9 dispatch arrived carrying the pending_class table as
# the RULED THREE {feedback_required, stability_window, evidence_insufficient}.
# That is a STALE reading: /review 768 round 2 ('Admit + rename', Architect-
# ratified) RE-RULED the table to CLOSED-AT-FIVE by admitting the birth-minted
# evidence_scoped + schema_incomplete, and /review 769 A1 struck those two from
# the contract's refused-census list precisely BECAUSE they had been admitted.
#
# The measured cost of the stale reading, latest-per-id at tic 771: the
# off-table population reads 17 ids against the three, and 3 ids against the
# ratified five — the 14 schema_incomplete carriers are ON-table since 768. The
# arms below pin the CURRENT ruled table by NAME (never by iterating
# FIELD_ENUMS, which a silent enum shrink would satisfy vacuously) and pin the
# stale-three revert as the discriminating negative control.
#
# DOES NOT SATISFY (rider carried verbatim from the ruling): "per-field rulings
# on the 17 historical off-table ids (that is /review's 768+ docket); guards at
# any writer other than queue-lifecycle-writeback.py"
# ===========================================================================

# The dispatch's own probe value — a NEVER-IN-CORPUS coinage, distinct from
# OFF_TABLE_PENDING_CLASS (`architect_ruling`, which IS measured in the corpus).
# The distinction is load-bearing: the contract's minting_authority clause says a
# value is "never coined at a write boundary", and a fresh coinage is the purest
# instance of that class.
NOVEL_COINAGE = "probe_novel_value"

# The CURRENT ruled table, named literally. If /review mints a sixth value, this
# tuple is amended in the same pass as the contract file — that is the point.
RULED_PENDING_CLASSES_AT_771 = (
    "evidence_insufficient", "evidence_scoped", "feedback_required",
    "schema_incomplete", "stability_window",
)
# The two admitted at /review 768 round 2 — the exact members a stale-three
# reading drops on the floor.
ACCRETED_AT_768 = ("evidence_scoped", "schema_incomplete")
# The values still off-table against the RATIFIED five, measured latest-per-id
# at tic 771 (1 id each). Fixture data, not a live-queue read.
RESIDUAL_OFF_TABLE_AT_771 = ("design_required", "maturity", "needs_evidence_repair")


class TestWave9CurrencyOfTheRuledPendingClassTable(_TmpQueue):
    def test_the_five_ruled_values_are_named_not_derived(self):
        """Named literally so a silent enum SHRINK cannot pass vacuously — the
        failure mode an iterate-FIELD_ENUMS assertion cannot see."""
        self.assertEqual(sorted(qlw.FIELD_ENUMS["pending_class"]),
                         sorted(RULED_PENDING_CLASSES_AT_771))
        for value in ACCRETED_AT_768:
            self.assertIn(value, qlw.FIELD_ENUMS["pending_class"])
            self.assertEqual(qlw.classify_enum_value("pending_class", value),
                             "lawful")

    def test_all_five_ruled_values_write_through(self):
        """NC arm (b), against the RATIFIED table rather than the stale three."""
        for value in RULED_PENDING_CLASSES_AT_771:
            write_queue(self.q, [envelope_row()])
            report = qlw.lifecycle_writeback(
                CPR_ID, {"status": "enrichment_eligible", "pending_class": value},
                queue_path=self.q, writer="test")
            self.assertEqual(report["row"]["pending_class"], value)

    def test_a_never_in_corpus_coinage_is_refused_typed(self):
        """NC arm (a), writeback face: a fresh coinage the corpus has never
        carried is refused with the typed code, and nothing is appended."""
        write_queue(self.q, [envelope_row()])
        with self.assertRaises(qlw.LifecycleWritebackRefused) as ctx:
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "enrichment_eligible",
                         "pending_class": NOVEL_COINAGE},
                queue_path=self.q, writer="test")
        reason = next(r for r in ctx.exception.reasons
                      if r["code"] == "pending_class_off_enum")
        self.assertEqual(reason["value"], NOVEL_COINAGE)
        self.assertIn("contracts/pending-class-enum-v1.json", reason["message"])
        self.assertIn("MINTING AUTHORITY", reason["message"])
        self.assertEqual(len(self.rows()), 1)

    def test_a_never_in_corpus_coinage_is_refused_at_validate_row(self):
        """NC arm (a), preflight face — the same predicate, rc=3 surface."""
        write_queue(self.q, [envelope_row()])
        res = qlw.validate_row(envelope_row(pending_class=NOVEL_COINAGE),
                               queue_path=self.q)
        self.assertEqual(res["verdict"], "REFUSE")
        self.assertEqual(res["enum_off_table"], {"pending_class": NOVEL_COINAGE})

    def test_a_never_in_corpus_coinage_cli_exits_2_and_appends_nothing(self):
        """NC arm (a), CLI face."""
        write_queue(self.q, [envelope_row()])
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = qlw.main(["--cpr-id", CPR_ID, "--queue-path", str(self.q),
                           "--set", f"pending_class={NOVEL_COINAGE}"])
        self.assertEqual(rc, 2)
        self.assertIn("pending_class_off_enum", buf.getvalue())
        self.assertEqual(len(self.rows()), 1)

    def test_the_audited_valve_still_admits_the_novel_coinage(self):
        """NC arm (d): the escape hatch is UNTOUCHED by this increment — it still
        admits, still stamps, still discloses. A guard whose valve broke would be
        a regression dressed as rigour."""
        write_queue(self.q, [envelope_row()])
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            qlw.lifecycle_writeback(
                CPR_ID, {"status": "enrichment_eligible",
                         "pending_class": NOVEL_COINAGE},
                queue_path=self.q, writer="test",
                waive_enum_guard=("pending_class",))
        landed = self.rows()[-1]
        self.assertEqual(landed["pending_class"], NOVEL_COINAGE)
        self.assertEqual(landed["lifecycle_writeback"]["enum_guard_waived"],
                         {"pending_class": NOVEL_COINAGE})
        self.assertIn("ENUM-GUARD-WAIVE-NOTICE", buf.getvalue())

    def test_stale_three_revert_flips_exactly_the_two_accreted_members(self):
        """THE NEGATIVE CONTROL, member-exact and declared before observation.

        Revert the ruled table to the dispatch's stale THREE and watch the exact
        predicted breakage: precisely the two /review-768 accretions flip
        lawful -> off_enum, the other three are unmoved, and a write carrying
        schema_incomplete — the 14-id majority carrier — starts REFUSING. Restore
        and the refusal disappears. This is what makes the currency arm mean
        something: it fails for the table's content, not for the fixture.
        """
        saved = qlw.FIELD_ENUMS["pending_class"]
        stale_three = frozenset({"feedback_required", "stability_window",
                                 "evidence_insufficient"})
        qlw.FIELD_ENUMS["pending_class"] = stale_three
        try:
            flipped = sorted(v for v in RULED_PENDING_CLASSES_AT_771
                             if qlw.classify_enum_value("pending_class", v)
                             != "lawful")
            self.assertEqual(flipped, sorted(ACCRETED_AT_768))
            write_queue(self.q, [envelope_row()])
            with self.assertRaises(qlw.LifecycleWritebackRefused):
                qlw.lifecycle_writeback(
                    CPR_ID, {"status": "enrichment_eligible",
                             "pending_class": "schema_incomplete"},
                    queue_path=self.q, writer="test")
        finally:
            qlw.FIELD_ENUMS["pending_class"] = saved
        # restored: the same write is lawful again
        write_queue(self.q, [envelope_row()])
        report = qlw.lifecycle_writeback(
            CPR_ID, {"status": "enrichment_eligible",
                     "pending_class": "schema_incomplete"},
            queue_path=self.q, writer="test")
        self.assertEqual(report["row"]["pending_class"], "schema_incomplete")

    def test_off_table_population_partitions_at_three_not_seventeen(self):
        """The population discriminator, on a FIXTURE (never the live queue).

        Four ids carry the four values the wave-9 staging called 'off-table'.
        Against the RATIFIED five only three of them are off-table; the
        schema_incomplete carrier is ON-table. This is the 17-vs-3 arithmetic in
        miniature — the reason a stale table reports a false anomaly.
        """
        carriers = {
            "cpr_fixture_schema_incomplete": "schema_incomplete",
            "cpr_fixture_design_required": "design_required",
            "cpr_fixture_needs_evidence_repair": "needs_evidence_repair",
            "cpr_fixture_maturity": "maturity",
        }
        write_queue(self.q, [envelope_row(cpr_id=i, pending_class=v)
                             for i, v in carriers.items()])
        off_table = sorted(
            v for v in carriers.values()
            if qlw.classify_enum_value("pending_class", v) == "off_enum")
        self.assertEqual(off_table, sorted(RESIDUAL_OFF_TABLE_AT_771))
        self.assertEqual(
            qlw.classify_enum_value("pending_class", "schema_incomplete"),
            "lawful")

    def test_the_fixture_lane_never_resolves_to_the_federation_queue(self):
        """Isolation pin (NC arm (c) at the unit rung): the explicit queue_path
        hook wins, so no fixture in this file can reach audit-logs/cprs/queue.jsonl.
        The byte-identity of the live queue is proven at the receipt rung by a
        before/after sha256; this is the structural half."""
        federation = qlw.default_queue_path()
        self.assertIsNotNone(federation)
        self.assertNotEqual(Path(federation).resolve(), self.q.resolve())
        write_queue(self.q, [envelope_row()])
        report = qlw.lifecycle_writeback(
            CPR_ID, {"status": "enrichment_eligible",
                     "pending_class": "feedback_required"},
            queue_path=self.q, writer="test")
        self.assertEqual(Path(report["queue_path"]).resolve(), self.q.resolve())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
