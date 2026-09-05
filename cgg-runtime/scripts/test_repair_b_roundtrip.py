#!/usr/bin/env python3
"""test_repair_b_roundtrip.py — Repair Covenant B activation micro-gate C (/review 635).

Drives the REAL verdict writer (queue_event_writer.py -> lib/atomic-append.sh) against a
TEMPORARY COPY of the real queue.jsonl, across every verdict shape (PROMOTE/REFINEMENT_RAY,
SKIP_WITH_HOME, DEFER, HOLD, MODIFY_PROMOTE, MERGE, SUPERSEDE), then rematerializes (naive +
shadow) and asserts:
  - current formulation correct + nonblank
  - origin unchanged (immutable)
  - lifecycle state = latest
  - MODIFY predecessor/hash/version correct
  - naive compatibility reader remains non-lossy during transition
  - shadow materializer returns intended state
  - the REAL queue.jsonl is byte-unchanged
  - the physics guard refuses a blank-body compat row at the boundary
This is a real append->read round-trip, NOT a constructed-dict check.

B2 WAVE 10 AMENDMENT (/review 772 round 3 Q9, row
`bk-off-enum-drift-field-generic-writer-topology`). queue_event_writer now
carries the pending_class ENUM VOCABULARY GUARD, and this writer's OWN
hardcoded DEFER/HOLD defaults were OFF-TABLE against
contracts/pending-class-enum-v1.json — so a bare DEFER/HOLD was REFUSED rc=2
and every DEFER/HOLD row below passed the AUDITED `--waive-enum-guard
pending_class`.

B2 WAVE 11 AMENDMENT (/review 773 round 1 Q3 — NO-DEFAULT + ABSENCE, ratified
verbatim; signed artifact B2-wave-11-SIGNED-tic773.json, self-sha
3c46db86c0580d4e). The writer holds NO defaults now, so the two verdicts part
ways here and the rows below follow the ruling:

  HOLD rows — the waive is DROPPED. A bare HOLD writes the contract's lawful
    ABSENCE key (explicit null) and is not refused, so there is nothing left to
    admit. Asserting the stamp on these rows would now pin a hatch that no
    longer fires.
  DEFER rows — the waive STAYS, and the off-table value is now passed
    EXPLICITLY by this driver (`--pending-class`) instead of being resolved
    inside the writer. The rows are byte-unchanged; what moved is WHO chose the
    value. That is the whole ruling: the class is the caller's to supply, and
    an omission is refused rather than defaulted.

Why still the waive and NOT a ruled lawful value on the DEFER rows: this driver
exercises verdict SHAPE coverage, not vocabulary POLICY. Substituting a ratified
class here would assert an honest-class MAPPING for these CogPRs — and /review
773 took neither MAP nor ADMIT (proposal: audit-logs/governance/
backlog-gunslinger-hoist/om-w10-pending-class-default-map-vs-admit-fork-tic772.md,
§4). The audited hatch keeps the shape green, keeps the off-table value VISIBLE
and stamped, and adjudicates nothing. Checks below pin BOTH halves of the ruling
through the real CLI: a bare DEFER is refused rc=2 with the typed
`pending_class_required_for_DEFER` and appends nothing, a bare HOLD lands an
explicit null whose row and `patch` mirror agree, and every waived DEFER row
carries the audit stamp at `queue_event_writer.enum_guard_waived`.

DOES NOT SATISFY (rider carried verbatim from the wave-11 ruling,
B2-wave-11-SIGNED-tic773.json): "this increment does NOT author a HOLD
generator contract (future work, unruled); does NOT touch the office_map
(standing fence per /review 772 Q5); does NOT re-truth the contract JSON
(seat-owned data surface); does NOT claim the all-rows historical complement
cured"
"""
from __future__ import annotations
import json, hashlib, shutil, subprocess, sys, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import queue_event_materializer as M

REAL_QUEUE = M.QUEUE
WRITER = HERE / "queue_event_writer.py"
ATOMIC = HERE / "lib" / "atomic-append.sh"
SCRATCH = Path(os.environ.get("REPAIR_B_SCRATCH",
    "/private/tmp/claude-501/-Users-breydentaylor-canonical/525f6ff4-230c-4084-a1a0-85e95e38cada/scratchpad"))
TMP_DIR = SCRATCH / "repair_b_test" / "cprs"        # must end in cprs/queue.jsonl (guard scope)
TMP_QUEUE = TMP_DIR / "queue.jsonl"

def sha_file(p: Path) -> str: return hashlib.sha256(p.read_bytes()).hexdigest()
def sha(s: str) -> str: return hashlib.sha256((s or "").encode()).hexdigest()

AUTH = "audit-logs/governance/review-635-verdict-authority-tic635.md"
MODIFY_14 = ("Every adjudication office must expose observable drift basins and an independently "
             "addressable audit/appeal surface. Dissent must not be silently reclassified as "
             "complicity by the office whose judgment is disputed.")
MODIFY_16 = ("Telos is an engineered prerequisite: governance must construct the prerequisites under "
             "which meaning is defended by the system's operation, not merely asserted after the fact.")

# B2 wave 10: the audited hatch. B2 wave 11: ridden by the DEFER rows ONLY, and
# now paired with an EXPLICIT caller-supplied value — the writer holds no
# default to admit. HOLD rows carry neither (they land the lawful null).
WAIVE = "pending_class"
# The historical off-table value these DEFER rows have always carried. Passed
# explicitly so the ROWS are byte-unchanged across the wave-11 cure while the
# CHOICE moves from the writer to the caller. Naming it here asserts nothing
# about the vocabulary — that is precisely what the audited hatch is for.
DEFER_OFF_TABLE = "maturity_window"

# (id, verdict, kwargs, note) — real verdict where Lane-A doctrine; SHAPE-coverage flagged otherwise
PLAN = [
    ("cpr_exact_token_inheritance_via_preamble_only_protection_tic232", "REFINEMENT_RAY", {}, "real"),
    ("cpr_lineage_note_is_a_relation_not_a_promotion_destination_tic421", "REFINEMENT_RAY", {}, "real"),
    ("cpr_two_axis_status_encoding_status_class_x_invocation_policy_tic293", "REFINEMENT_RAY", {}, "real"),
    ("cpr_runtime_pertinence_fidelity_is_the_meaning_fidelity_target_tic329", "REFINEMENT_RAY", {}, "real"),
    ("cpr_push_load_bearing_in_intelligent_commits_cadence_sweeps_exhaust_tic421", "REFINEMENT_RAY", {}, "real[11] override"),
    ("cpr_promotion_success_rate_after_floor_n_trust_mechanic_tic244", "DEFER", {"maturity_window": 8, "pending_class": DEFER_OFF_TABLE, "waive_enum_guard": WAIVE}, "real[9a]"),
    ("cpr_adjudication_office_drift_audit_basins_tic358", "MODIFY_PROMOTE", {"new_formulation": MODIFY_14}, "real[14]"),
    ("cpr_cockpit_intent_gate_latency_bounds_provisional_tic256", "DEFER", {"maturity_window": None, "pending_class": DEFER_OFF_TABLE, "waive_enum_guard": WAIVE}, "shape[3] object-2 lifecycle"),
    ("cpr_phase_beta1_rapier_admission_advance_tic285", "HOLD", {}, "shape[7] object-2 lifecycle"),
    ("cpr_plate_council_live_pressure_actuation_tic285", "HOLD", {}, "shape[10] object-2 lifecycle"),
    ("cpr_boot_receipt_fingerprint_excludes_boot_read_fields_tic422", "DEFER", {"pending_class": DEFER_OFF_TABLE, "waive_enum_guard": WAIVE}, "shape[15] object-2 lifecycle"),
    # migrated (Defect B)
    ("cpr_consumer_set_audit_yield_proportional_to_transform_unambiguity_tic333", "REFINEMENT_RAY", {}, "real[2] migrated"),
    ("cpr_1c547dc137974836", "REFINEMENT_RAY", {}, "real[4] migrated"),
    ("cpr_relational_meaning_pinning_fidelity_preserving_decoupling_tic327", "HOLD", {}, "real[6a] migrated"),
    ("cpr_00c5f4571317f11a", "SKIP_WITH_HOME", {"home": "harpoon-office/HT_cable-lattice (assessment lane)"}, "shape[8] migrated relation"),
    ("cpr_governance_as_gravity_well_telos_as_engineered_prerequisite_tic327", "MODIFY_PROMOTE", {"new_formulation": MODIFY_16}, "real[16] migrated apex"),
]
CONTROLS = [  # unaffected — NOT written; must stay byte-identical projection
    "cpr_changelog_fix_entry_impact_is_a_config_shape_probe_not_a_read_tic501",
    "cpr_generated_map_derived_signal_only_as_honest_as_its_nodeset_tic502",
    "cpr_consumer_that_reads_the_source_collapses_the_drift_leg_it_read_against_tic502",
    "cpr_dry_run_proof_cannot_prove_the_write_leg_verify_delivery_at_consumer_tic632",
]

def writer(oid, verdict, queue, **kw):
    cmd = [sys.executable, str(WRITER), "--queue", str(queue), "--id", oid,
           "--verdict", verdict, "--review-tic", "635", "--authority", AUTH]
    for k, v in kw.items():
        if v is not None:
            cmd += [f"--{k.replace('_','-')}", str(v)]
    return subprocess.run(cmd, capture_output=True, text=True)

def last_row_for(oid, queue: Path):
    rows = M._rows_for(oid, queue)
    return rows[-1] if rows else None

def main() -> int:
    ok, checks = True, []
    def C(name, cond, **d):
        nonlocal ok; ok = ok and bool(cond)
        checks.append({"check": name, "pass": bool(cond), **d})

    real_sha_before = sha_file(REAL_QUEUE)
    if TMP_DIR.exists(): shutil.rmtree(TMP_DIR.parent)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REAL_QUEUE, TMP_QUEUE)

    control_before = {c: M.shadow_project(c, TMP_QUEUE).get("current_formulation") for c in CONTROLS}

    for oid, verdict, kw, note in PLAN:
        pre = M.shadow_project(oid, TMP_QUEUE)
        pre_origin, pre_current = pre.get("origin_formulation"), pre.get("current_formulation")
        r = writer(oid, verdict, TMP_QUEUE, **kw)
        if r.returncode != 0:
            C(f"{note}:{verdict}:{oid[:32]}", False, error=r.stderr.strip()[:160]); continue
        post = M.shadow_project(oid, TMP_QUEUE)
        naive = M.naive_project(oid, TMP_QUEUE)
        row = last_row_for(oid, TMP_QUEUE)
        cur = (post.get("current_formulation") or "").strip()

        # expected current: MODIFY advances to new wording; else prior body carried forward
        if verdict in ("MODIFY_PROMOTE", "MERGE"):
            expect = (kw.get("new_formulation") or "").strip()
        else:
            expect = (pre_current or "").strip()
        expected_status = {"REFINEMENT_RAY": "promoted", "PROMOTE": "promoted",
                           "SKIP_WITH_HOME": "skipped", "DEFER": "enrichment_eligible",
                           "HOLD": "enrichment_eligible", "MODIFY_PROMOTE": "promoted",
                           "SUPERSEDE": "superseded"}[verdict]

        C(f"{note}:current_nonblank", bool(cur), id=oid[:36], verdict=verdict)
        C(f"{note}:current_correct", cur == expect, id=oid[:36])
        C(f"{note}:origin_immutable", (post.get("origin_formulation") or "") == (pre_origin or ""), id=oid[:36])
        C(f"{note}:naive_non_lossy", bool((naive.get("current_formulation") or "").strip()), id=oid[:36])
        C(f"{note}:lifecycle_latest", post.get("status") == expected_status, id=oid[:36],
          got=post.get("status"), want=expected_status)
        if verdict == "DEFER":
            C(f"{note}:defer_not_status_deferred", row.get("status") == "enrichment_eligible", id=oid[:36])
        if verdict == "DEFER":
            # B2 wave 10/11: the waived row carries the AUDIT STAMP — the hatch
            # fired visibly, and the caller-supplied off-table value stays legible.
            C(f"{note}:enum_guard_waive_stamped",
              row.get("queue_event_writer", {}).get("enum_guard_waived", {}).get("pending_class")
              == row.get("pending_class"),
              id=oid[:36], pending_class=row.get("pending_class"))
        if verdict == "HOLD":
            # B2 wave 11 (/review 773 Q3, the ABSENCE half): a bare HOLD asserts
            # the contract's lawful absence key — the field is PRESENT and null
            # (never omitted, never a substituted class), the `patch` mirror
            # agrees, and no hatch fired because none was needed.
            C(f"{note}:hold_asserts_explicit_null",
              "pending_class" in row and row.get("pending_class") is None,
              id=oid[:36], pending_class=row.get("pending_class"),
              key_present="pending_class" in row)
            C(f"{note}:hold_row_patch_mirror_agrees",
              row.get("patch", {}).get("pending_class") is None
              and "pending_class" in row.get("patch", {}), id=oid[:36])
            C(f"{note}:hold_carries_no_waive_stamp",
              "queue_event_writer" not in row, id=oid[:36])
        if verdict == "MODIFY_PROMOTE":
            C(f"{note}:predecessor_hash", row.get("predecessor_hash") == sha(pre_current or ""), id=oid[:36])
            C(f"{note}:version_monotonic", isinstance(row.get("formulation_version"), int), id=oid[:36])
        # every appended event carries a full Option-B envelope (#5)
        for f in ("schema_version", "event_id", "object_version", "event_type", "governing_authority"):
            C(f"{note}:envelope:{f}", f in row, id=oid[:36])

    # relation shape-coverage: MERGE + SUPERSEDE (no review-635 verdict uses these; prove the writer handles them)
    rm = writer("cpr_synthetic_merge_shape", "MERGE", TMP_QUEUE,
                new_formulation="merged shape-coverage formulation", merge_parents="cpr_a,cpr_b")
    C("shape:MERGE_refused_blank_guarded", rm.returncode == 0, note="merge with body succeeds")
    if rm.returncode == 0:
        mrow = last_row_for("cpr_synthetic_merge_shape", TMP_QUEUE)
        C("shape:MERGE_carries_parents", mrow.get("parent_object_ids") == ["cpr_a", "cpr_b"])
    rs = writer("cpr_synthetic_supersede_shape", "SUPERSEDE", TMP_QUEUE,
                supersedes="cpr_old@2", new_formulation="x")  # supersede carries prior; needs body
    # supersede on a fresh id has no prior body -> must REFUSE (unconditional blank refusal #4)
    C("shape:SUPERSEDE_refuses_blank_body", rs.returncode != 0,
      note="fresh id has no formulation -> unconditional blank refusal", rc=rs.returncode)

    # B2 wave 11 ruling, through the REAL CLI — BOTH halves.
    #
    # HALF 1 (NO-DEFAULT): a bare DEFER names no class, and the writer holds no
    # default to fall back on, so it is REFUSED rc=2 with the typed code and
    # appends NOTHING. The refusal must hand the caller BOTH routes back.
    rows_before = len(TMP_QUEUE.read_text(encoding="utf-8").splitlines())
    rg = writer("cpr_boot_receipt_fingerprint_excludes_boot_read_fields_tic422",
                "DEFER", TMP_QUEUE)
    rows_after = len(TMP_QUEUE.read_text(encoding="utf-8").splitlines())
    C("enum_guard:bare_defer_refused_rc2", rg.returncode == 2, rc=rg.returncode)
    C("enum_guard:refusal_is_typed",
      "pending_class_required_for_DEFER" in rg.stderr, stderr=rg.stderr.strip()[:200])
    C("enum_guard:refusal_names_contract_and_authority",
      "contracts/pending-class-enum-v1.json" in rg.stderr
      and "MINTING AUTHORITY" in rg.stderr)
    C("enum_guard:refusal_names_both_routes",
      "--pending-class" in rg.stderr and "--waive-enum-guard" in rg.stderr,
      note="a missing-input refusal owes the caller both doors back")
    C("enum_guard:refusal_appended_nothing", rows_after == rows_before,
      before=rows_before, after=rows_after)
    # An explicitly-named OFF-TABLE value with no waive is still the wave-10
    # refusal — a DIFFERENT typed code, because it is a different failure (a
    # value the caller chose vs a value the caller never chose).
    rgv = writer("cpr_boot_receipt_fingerprint_excludes_boot_read_fields_tic422",
                 "DEFER", TMP_QUEUE, pending_class=DEFER_OFF_TABLE)
    C("enum_guard:explicit_off_table_without_waive_refused_rc2",
      rgv.returncode == 2, rc=rgv.returncode)
    C("enum_guard:off_enum_and_required_are_distinct_codes",
      "pending_class_off_enum" in rgv.stderr
      and "pending_class_required_for_DEFER" not in rgv.stderr,
      stderr=rgv.stderr.strip()[:160])
    #
    # HALF 2 (ABSENCE): a bare HOLD is NOT refused — it lands the contract's
    # lawful absence key as an explicit null, and the row grows by exactly one.
    rows_before = len(TMP_QUEUE.read_text(encoding="utf-8").splitlines())
    rh = writer("cpr_phase_beta1_rapier_admission_advance_tic285", "HOLD", TMP_QUEUE)
    rows_after = len(TMP_QUEUE.read_text(encoding="utf-8").splitlines())
    C("absence:bare_hold_accepted_rc0", rh.returncode == 0,
      rc=rh.returncode, stderr=rh.stderr.strip()[:200])
    C("absence:bare_hold_appended_exactly_one", rows_after == rows_before + 1,
      before=rows_before, after=rows_after)
    hrow = last_row_for("cpr_phase_beta1_rapier_admission_advance_tic285", TMP_QUEUE)
    C("absence:bare_hold_row_carries_explicit_null",
      "pending_class" in hrow and hrow.get("pending_class") is None,
      pending_class=hrow.get("pending_class"))
    C("absence:bare_hold_status_is_enrichment_eligible",
      hrow.get("status") == "enrichment_eligible", got=hrow.get("status"))
    C("absence:bare_hold_no_waive_notice",
      "ENUM-GUARD-WAIVE-NOTICE" not in rh.stderr,
      note="nothing was admitted, so no hatch may have fired")

    # physics guard: a blank-body compat row is refused at the boundary
    blank = json.dumps({"id": "cpr_x", "event_type": "lifecycle_patch", "status": "promoted",
                        "compat_snapshot": True, "lesson": ""})
    g = subprocess.run(["bash", str(ATOMIC), "--append", str(TMP_QUEUE), blank],
                       capture_output=True, text=True)
    C("physics_guard:blank_compat_refused", g.returncode == 3, rc=g.returncode)

    # unaffected controls unchanged
    for c in CONTROLS:
        after = M.shadow_project(c, TMP_QUEUE).get("current_formulation")
        C(f"control_unchanged:{c[:36]}", after == control_before[c])

    # THE REAL QUEUE IS BYTE-UNCHANGED
    real_sha_after = sha_file(REAL_QUEUE)
    C("real_queue_byte_unchanged", real_sha_after == real_sha_before,
      before=real_sha_before[:16], after=real_sha_after[:16])

    passed = sum(c["pass"] for c in checks)
    verdict = "GREEN" if ok else "RED"
    out = {"verdict": verdict, "checks_passed": f"{passed}/{len(checks)}",
           "temp_queue": str(TMP_QUEUE), "real_queue_sha": real_sha_after,
           "failures": [c for c in checks if not c["pass"]], "all_checks": checks}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
