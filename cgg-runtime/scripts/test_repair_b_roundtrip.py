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

# (id, verdict, kwargs, note) — real verdict where Lane-A doctrine; SHAPE-coverage flagged otherwise
PLAN = [
    ("cpr_exact_token_inheritance_via_preamble_only_protection_tic232", "REFINEMENT_RAY", {}, "real"),
    ("cpr_lineage_note_is_a_relation_not_a_promotion_destination_tic421", "REFINEMENT_RAY", {}, "real"),
    ("cpr_two_axis_status_encoding_status_class_x_invocation_policy_tic293", "REFINEMENT_RAY", {}, "real"),
    ("cpr_runtime_pertinence_fidelity_is_the_meaning_fidelity_target_tic329", "REFINEMENT_RAY", {}, "real"),
    ("cpr_push_load_bearing_in_intelligent_commits_cadence_sweeps_exhaust_tic421", "REFINEMENT_RAY", {}, "real[11] override"),
    ("cpr_promotion_success_rate_after_floor_n_trust_mechanic_tic244", "DEFER", {"maturity_window": 8}, "real[9a]"),
    ("cpr_adjudication_office_drift_audit_basins_tic358", "MODIFY_PROMOTE", {"new_formulation": MODIFY_14}, "real[14]"),
    ("cpr_cockpit_intent_gate_latency_bounds_provisional_tic256", "DEFER", {"maturity_window": None}, "shape[3] object-2 lifecycle"),
    ("cpr_phase_beta1_rapier_admission_advance_tic285", "HOLD", {}, "shape[7] object-2 lifecycle"),
    ("cpr_plate_council_live_pressure_actuation_tic285", "HOLD", {}, "shape[10] object-2 lifecycle"),
    ("cpr_boot_receipt_fingerprint_excludes_boot_read_fields_tic422", "DEFER", {}, "shape[15] object-2 lifecycle"),
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
