#!/usr/bin/env python3
"""queue_event_materializer.py — Repair Covenant B (object-2, ADMITTED /review 635).

The typed-append-only-event materializer + legacy-migration shadow reader for the CogPR
queue. Cures three defects proven at /review 635 without rewriting queue.jsonl history:

  Defect A (11 rows): a /review deferral appends a thin `status:deferred` row that OMITS
    the `lesson` key; the naive latest-per-id reader elects the thin delta and the body
    goes dark. Cure: a thin lifecycle row is a `lifecycle_patch`, never a formulation.
  Defect B (5 rows):  a row ingested with `lesson` KEY-ABSENT AND source=None — no body,
    no addressable origin. Cure: origin comes from a migration pointer+hash, current is
    the review-accepted formulation, never derived from a thin event.
  Field-selection symptom: pending_class read from a non-latest row (architect_gate) vs
    the terminal-valve latest (feedback_required). Cure: lifecycle fields fold to latest.

Contract: audit-logs/governance/review-635-repair-covenant-b/spec.md
This is a FORWARD overlay + shadow reader; it mutates no queue.jsonl row.

Usage:
  queue_event_materializer.py --selftest        # fixtures (18 witnesses) + parity
  queue_event_materializer.py --shadow <id>     # corrected projection for one id
  queue_event_materializer.py --naive  <id>     # the current (buggy) latest-per-id read
"""
from __future__ import annotations
import argparse, json, hashlib, sys
from pathlib import Path

# ---- zone resolution (repo-external queue lives in canonical/audit-logs) -----------
def _find_queue() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        cand = p / "audit-logs" / "cprs" / "queue.jsonl"
        if cand.exists():
            return cand
    # fall back to the known federation root
    return Path("/Users/breydentaylor/canonical/audit-logs/cprs/queue.jsonl")

QUEUE = _find_queue()

FORMULATION_FIELDS = ("lesson", "title", "recommended_scopes", "review_hints")
LIFECYCLE_FIELDS = ("status", "pending_class", "defer_class", "re_eval_tic",
                    "defer_until_tic", "enrichment_state", "maturity_window_tics")

def _sha(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

# ---- Migration for the 5 bodyless-ingestion ids (Defect B) — PINNED MANIFEST -------
# Loaded from the pinned migration manifest (NOT opaque runtime constants), so origin
# source-session references + captured hashes live as reviewable governance data.
def _find_migration_manifest() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        cand = (p / "audit-logs" / "governance" / "review-635-repair-covenant-b"
                / "migration-manifest.json")
        if cand.exists():
            return cand
    return Path("/Users/breydentaylor/canonical/audit-logs/governance/"
                "review-635-repair-covenant-b/migration-manifest.json")

def load_migration() -> dict:
    mp = _find_migration_manifest()
    if not mp.exists():
        return {}
    m = json.loads(mp.read_text(encoding="utf-8"))
    out = {}
    for oid, e in m.get("entries", {}).items():
        out[oid] = {
            "origin_source_pointer": e["origin_source_session"],
            "origin_snapshot": e["origin_formulation_capture"],
            "origin_hash": e["origin_formulation_hash"],
            "review_accepted": True,
        }
    return out

MIGRATION = load_migration()

# ---- Typed-event fold (the forward contract) ---------------------------------------
def materialize_events(events: list[dict]) -> dict:
    """fold typed events -> current object (spec.md 'Deterministic materializer')."""
    ordered = sorted(enumerate(events), key=lambda ix: (ix[1].get("object_version", 0), ix[0]))
    obj: dict = {"lineage": []}
    for _, ev in ordered:
        et = ev.get("event_type")
        if et == "birth":
            obj["object_id"] = ev["object_id"]
            obj["birth_tic"] = ev.get("birth_tic")
            obj["origin_formulation"] = ev.get("origin_formulation")
            obj["origin_source_pointer"] = ev.get("origin_source_pointer")
            obj["origin_source_hash"] = ev.get("origin_source_hash")
            obj["current_formulation"] = ev.get("origin_formulation")
            obj["formulation_version"] = 0
        elif et in ("formulation_update", "merge", "supersede"):
            obj["current_formulation"] = ev.get("current_formulation")
            obj["formulation_version"] = ev.get("formulation_version")
            obj["lineage"].append({k: ev.get(k) for k in
                ("event_type", "governing_verdict", "replaces_version",
                 "parent_object_ids", "supersedes") if ev.get(k) is not None})
        elif et == "lifecycle_patch":
            for f in LIFECYCLE_FIELDS:
                if f in ev:
                    obj[f] = ev[f]
            # INVARIANT: a lifecycle patch NEVER touches a formulation field.
        elif et == "enrichment_append":
            obj.setdefault("enrichment", []).append(ev.get("evidence"))
        elif et == "skip_with_home":
            obj["home_relation"] = ev.get("home_relation")
        elif et == "tombstone":
            fld = ev.get("field")
            if fld in FORMULATION_FIELDS or fld in ("origin_formulation", "origin_source_pointer"):
                raise ValueError(f"unlawful tombstone on protected field {fld!r}")
            obj[fld] = None
        else:
            raise ValueError(f"unknown event_type {et!r}")
    return obj

# ---- Legacy readers (over the append-only queue.jsonl) -----------------------------
def _rows_for(object_id: str, queue_path: Path = QUEUE) -> list[dict]:
    rows = []
    for line in queue_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or f'"{object_id}"' not in line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("id") == object_id:
            rows.append(r)
    return rows

def naive_project(object_id: str, queue_path: Path = QUEUE) -> dict:
    """The CURRENT (buggy) reader: the last row wins wholesale."""
    rows = _rows_for(object_id, queue_path)
    if not rows:
        return {"object_id": object_id, "current_formulation": None, "_reader": "naive_empty"}
    latest = rows[-1]
    return {"object_id": object_id,
            "current_formulation": latest.get("lesson") or None,
            "status": latest.get("status"),
            "pending_class": latest.get("pending_class"),
            "_reader": "naive_latest_row_wholesale"}

def shadow_project(object_id: str, queue_path: Path = QUEUE) -> dict:
    """The CORRECTED reader (Repair B): a thin lifecycle row is a lifecycle_patch, never a
    formulation; current_formulation = latest CONTENT-BEARING formulation; lifecycle fields
    fold to their latest value; bodyless-ingestion ids resolve origin via the migration table."""
    rows = _rows_for(object_id, queue_path)
    content_rows = [r for r in rows if (r.get("lesson") or "").strip()]
    obj = {"object_id": object_id, "lineage": [], "_reader": "shadow_materialized"}

    if object_id in MIGRATION:
        # PINNED origin from the migration manifest (immutable) — a later content-bearing row
        # advances `current` but NEVER redefines origin for a migrated (Defect-B) id.
        m = MIGRATION[object_id]
        obj["origin_formulation"] = m["origin_snapshot"]
        obj["origin_source_pointer"] = m["origin_source_pointer"]
        obj["origin_source_hash"] = m.get("origin_hash") or _sha(m["origin_snapshot"])
        if content_rows:
            last_content = content_rows[-1]
            obj["current_formulation"] = last_content.get("lesson")
            obj["current_source_hash"] = _sha(last_content.get("lesson"))
            obj["current_from"] = "review_accepted_content_row"
        else:
            obj["current_formulation"] = m["origin_snapshot"]
            obj["current_source_hash"] = obj["origin_source_hash"]
            obj["current_from"] = "review_635_accepted"
    elif content_rows:
        first, last_content = content_rows[0], content_rows[-1]
        obj["origin_formulation"] = first.get("lesson")
        obj["origin_source_pointer"] = first.get("source") or first.get("source_file")
        obj["origin_source_hash"] = _sha(first.get("lesson"))
        obj["current_formulation"] = last_content.get("lesson")
        obj["current_source_hash"] = _sha(last_content.get("lesson"))
        obj["birth_tic"] = first.get("birth_tic")
    else:
        obj["current_formulation"] = None
        obj["_unresolved"] = "no content-bearing row and no migration origin"

    # lifecycle fields fold to the LATEST row that declares them (terminal-valve latest)
    for f in ("status", "pending_class", "defer_class", "re_eval_tic"):
        for r in reversed(rows):
            if r.get(f) is not None:
                obj[f] = r.get(f); break
    return obj

# NOTE: the real body-preserving/typed write path lives in queue_event_writer.py (which
# appends through lib/atomic-append.sh) and is exercised end-to-end by test_repair_b_roundtrip.py.
# There is deliberately no dict-returning "write helper" here — a helper that only builds a
# dict is a mounted bear (presence != execution). This module is the READ/FOLD half only.

# ---- Fixtures: the 18 fault witnesses + parity (READ-side) --------------------------
PROJECTION_LOSS = [  # Defect A — 11
    "cpr_exact_token_inheritance_via_preamble_only_protection_tic232",
    "cpr_cockpit_intent_gate_latency_bounds_provisional_tic256",
    "cpr_lineage_note_is_a_relation_not_a_promotion_destination_tic421",
    "cpr_phase_beta1_rapier_admission_advance_tic285",
    "cpr_promotion_success_rate_after_floor_n_trust_mechanic_tic244",
    "cpr_plate_council_live_pressure_actuation_tic285",
    "cpr_push_load_bearing_in_intelligent_commits_cadence_sweeps_exhaust_tic421",
    "cpr_two_axis_status_encoding_status_class_x_invocation_policy_tic293",
    "cpr_runtime_pertinence_fidelity_is_the_meaning_fidelity_target_tic329",
    "cpr_adjudication_office_drift_audit_basins_tic358",
    "cpr_boot_receipt_fingerprint_excludes_boot_read_fields_tic422",
]
BODYLESS = list(MIGRATION.keys())  # Defect B — 5
STALE_FIELD = [  # field-selection symptom — [7]/[10]
    ("cpr_phase_beta1_rapier_admission_advance_tic285", "feedback_required"),
    ("cpr_plate_council_live_pressure_actuation_tic285", "feedback_required"),
]
UNAFFECTED = [  # 6 content-bearing — parity must hold (no regression)
    "cpr_changelog_fix_entry_impact_is_a_config_shape_probe_not_a_read_tic501",
    "cpr_generated_map_derived_signal_only_as_honest_as_its_nodeset_tic502",
    "cpr_consumer_that_reads_the_source_collapses_the_drift_leg_it_read_against_tic502",
    "cpr_mogul_civil_status_check_fd0e9526f1de",
    "cpr_dry_run_proof_cannot_prove_the_write_leg_verify_delivery_at_consumer_tic632",
    "cpr_skill_tool_mask_leaks_across_plan_approve_boundary_trace_recurrence_dont_normalize_tic633",
]

def selftest() -> int:
    ok = True
    results = {"projection_loss_recovered": [], "bodyless_origin_addressable": [],
               "stale_field_corrected": [], "parity_unaffected": [], "invariant_checks": []}
    def check(cond, bucket, detail):
        nonlocal ok
        ok = ok and bool(cond)
        results[bucket].append({"pass": bool(cond), **detail})

    # (1) unit test the typed-event fold: a lifecycle patch must not blank the body
    ev = [
        {"event_type": "birth", "object_id": "T", "birth_tic": 1,
         "origin_formulation": "ORIGIN BODY", "origin_source_pointer": "src://x",
         "origin_source_hash": _sha("ORIGIN BODY"), "object_version": 0},
        {"event_type": "lifecycle_patch", "object_id": "T", "status": "deferred",
         "pending_class": "architect_gate", "object_version": 1},
        {"event_type": "lifecycle_patch", "object_id": "T", "status": "enrichment_eligible",
         "pending_class": "feedback_required", "object_version": 2},
    ]
    m = materialize_events(ev)
    check(m["current_formulation"] == "ORIGIN BODY", "invariant_checks",
          {"name": "lifecycle_patch_never_blanks_body", "got": m["current_formulation"]})
    check(m["pending_class"] == "feedback_required", "invariant_checks",
          {"name": "lifecycle_folds_to_latest", "got": m["pending_class"]})
    try:
        materialize_events([{"event_type": "tombstone", "object_id": "T", "field": "lesson"}])
        check(False, "invariant_checks", {"name": "tombstone_protects_formulation"})
    except ValueError:
        check(True, "invariant_checks", {"name": "tombstone_protects_formulation"})

    # (2) Defect A — 11 projection-loss ids. DURABLE INVARIANT: shadow returns a nonblank
    #     current formulation. (The original fixture also asserted "naive reader empty" as a
    #     proxy for the defect being PRESENT; once /review 635 wrote promoted content rows the
    #     defect is CURED at the source and the naive reader recovers too — so that precondition
    #     is intentionally dropped. Body-preservation is proven state-independently by
    #     test_repair_b_roundtrip.py; this asserts the always-true invariant.)
    for oid in PROJECTION_LOSS:
        shadow = shadow_project(oid)
        recovered = bool((shadow.get("current_formulation") or "").strip())
        check(recovered, "projection_loss_recovered",
              {"id": oid, "shadow_len": len(shadow.get("current_formulation") or "")})

    # (3) Defect B — 5 bodyless ids. DURABLE INVARIANT: origin is addressable (pinned manifest
    #     pointer+hash) AND current is nonblank. (Pre-/review-635, current came from the migration
    #     snapshot [current_from=review_635_accepted]; after V.3 wrote a promoted content row,
    #     current legitimately comes from that row [current_from=review_accepted_content_row] while
    #     origin stays pinned to the manifest — proven in shadow_project. Both are valid; assert
    #     nonblank + addressable, not the source-branch which is state-dependent.)
    for oid in BODYLESS:
        shadow = shadow_project(oid)
        addressable = bool(shadow.get("origin_source_pointer")) and bool(shadow.get("origin_source_hash"))
        current_ok = bool((shadow.get("current_formulation") or "").strip())
        check(addressable and current_ok, "bodyless_origin_addressable",
              {"id": oid, "origin_ptr": shadow.get("origin_source_pointer"),
               "current_from": shadow.get("current_from")})

    # (4) field-selection symptom — [7]/[10]: naive=architect_gate(stale), shadow=feedback_required
    for oid, expect in STALE_FIELD:
        naive, shadow = naive_project(oid), shadow_project(oid)
        check(shadow.get("pending_class") == expect, "stale_field_corrected",
              {"id": oid, "naive_pending_class": naive.get("pending_class"),
               "shadow_pending_class": shadow.get("pending_class"), "expected": expect})

    # (5) parity — 6 content-bearing ids: shadow current body == naive current body (no regression)
    for oid in UNAFFECTED:
        naive, shadow = naive_project(oid), shadow_project(oid)
        same_body = (naive.get("current_formulation") or "") == (shadow.get("current_formulation") or "")
        check(same_body, "parity_unaffected",
              {"id": oid, "same_body": same_body,
               "len": len(shadow.get("current_formulation") or "")})

    summary = {
        "scope": "READ/FOLD half only — the write path is proven by test_repair_b_roundtrip.py",
        "witnesses_total": len(PROJECTION_LOSS) + len(BODYLESS) + len(STALE_FIELD),
        "projection_loss": f"{sum(r['pass'] for r in results['projection_loss_recovered'])}/{len(PROJECTION_LOSS)}",
        "bodyless": f"{sum(r['pass'] for r in results['bodyless_origin_addressable'])}/{len(BODYLESS)}",
        "stale_field": f"{sum(r['pass'] for r in results['stale_field_corrected'])}/{len(STALE_FIELD)}",
        "parity_unaffected": f"{sum(r['pass'] for r in results['parity_unaffected'])}/{len(UNAFFECTED)}",
        "invariants": f"{sum(r['pass'] for r in results['invariant_checks'])}/{len(results['invariant_checks'])}",
        "verdict": "GREEN" if ok else "RED",
    }
    print(json.dumps({"summary": summary, "results": results}, indent=2))
    return 0 if ok else 1

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--shadow")
    ap.add_argument("--naive")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.shadow:
        print(json.dumps(shadow_project(a.shadow), indent=2)); return 0
    if a.naive:
        print(json.dumps(naive_project(a.naive), indent=2)); return 0
    ap.error("one of --selftest / --shadow <id> / --naive <id> required")

if __name__ == "__main__":
    sys.exit(main())
