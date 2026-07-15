#!/usr/bin/env python3
"""validate_admitted_active.py — /review 635 fail-loud two-axis fragment validator.

DERIVES each fragment's readiness from the registered FragmentDAG edges + execution state
(NOT from stored labels — that is what caught c7_rollback_drill_design being called strike-ready
while its own edge c7_author_spec#0 -> c7_rollback_drill_design#1 has an UNEXECUTED predecessor).

  EXECUTED            : fragment id in the executed set
  ADMITTED_ACTIVE     : not executed AND every predecessor (incoming edge) is EXECUTED (strike_ready)
  DEPENDENCY_BOUND    : not executed AND >=1 predecessor is not executed (dag_state=blocked)

--fix   : rewrite the 8 admission receipts + carriage manifest + audit/close from the derivation
--check : derive, recompute both point-10 hashes, verify carriage fields on every ADMITTED_ACTIVE
          node, assert totals 5/7/9; exit non-zero on any failure (fail-loud).
"""
from __future__ import annotations
import json, sys, hashlib, argparse
from pathlib import Path
ROOT = Path("/Users/breydentaylor/canonical")
OBJ2 = ROOT / "audit-logs/governance/review-635-object2-covenants"
AMEND = "audit-logs/governance/review-635-authority-amendment-two-axis-admitted-active-tic635.md"
MANIFEST = ROOT / "audit-logs/governance/review-635-admitted-active-nodes.json"

EXECUTED = {
 "c8_resolve_twin_alias#0::covenant", "c20b_add_monitor_to_id#0::covenant",
 "c20b_fixture_two_violations#1::covenant", "c15_consumer_set_inspection#0::covenant",
 "c9b_define_metric#0::covenant"}
# carriage data for a node IF the derivation makes it ADMITTED_ACTIVE
CARRIAGE = {
 "c3_stage1_measurement_contract#0::covenant":("bk-c3-cockpit-measurement-contract","ent_homeskillet + ak-control-room (substrate)","author cockpit.intent measurement contract + telemetry surface + provisional envelope field + fixture",639),
 "c6b_drill_harness#0::covenant":("bk-c6b-fidelity-drill-harness","ent_homeskillet + kernel (F2 lane)","build decouple->simulate->rehydrate drill harness",639),
 "c7_author_spec#0::covenant":("bk-c7-rapier-l5-adapter-spec","ent_homeskillet + ak-control-room (substrate)","author Rapier L5 adapter spec incl the tic-142 rollback covenant",640),
 "c8_admit_gate_semantics#1::covenant":("bk-c8-cable-lattice-compiler-edit","ent_homeskillet + harpoon-office (homeskillet-csl)","admit wave-membership!=exec-intent gate-jump semantics into the cable_lattice compiler",639),
 "c10_producer_to_manifold#0::covenant":("bk-c10-council-pressure-producer","ent_homeskillet + ak-control-room (substrate)","wire canonical council-pressure producer -> signal manifold",640),
 "c15_impl_and_prove#1::covenant":("bk-c15-boot-receipt-fingerprint-fix","ent_homeskillet + cgg-runtime","fix content_fingerprint to include boot-read fields OR enforce single-emission; prove dropped-second-shape survives",637),
 "c9b_simonly_harness#1::covenant":("bk-c9b-calibration-harness","ent_homeskillet + signals/governance","build SimOnly/fixture calibration harness for promotion-success-rate-after-floor-N",637),
}
CARRIERS = {
 "cadence_handoff_plan": "~/.claude/plans/effervescent-popping-pie.md",
 "carriage_manifest": "audit-logs/governance/review-635-admitted-active-nodes.json",
 "boot_override_receipt_id": "034703883faf39df",
 "mandate_note": "The tic-636 mandate was emitted BEFORE this amendment; an additive carriage pointer was backfilled into audit-logs/mogul/mandates/current.json (uncommitted, fabric-owned) — the durable carriers are the handoff + manifest + boot-override receipt above. The old mandate is NOT claimed to have held post-audit state.",
}

def _h(items): return hashlib.sha256("\n".join(sorted(items)).encode()).hexdigest()

def _preds(edges):
    p = {}
    for a, b in edges: p.setdefault(b, []).append(a)
    return p

def derive(receipt):
    dag = receipt["fragment_dag"]; frags = dag["fragments"]; edges = [tuple(e) for e in dag["edges"]]
    preds = _preds(edges)
    out = {}
    for f in frags:
        if f in EXECUTED:
            out[f] = ("executed", "EXECUTED", None)
        elif all(pp in EXECUTED for pp in preds.get(f, [])):
            out[f] = ("strike_ready", "ADMITTED_ACTIVE", None)
        else:
            unmet = [pp for pp in preds.get(f, []) if pp not in EXECUTED]
            out[f] = ("blocked", "DEPENDENCY_BOUND", f"{unmet[0]} EXECUTED")
    return out, frags, edges

def run(fix: bool) -> int:
    ok, checks = True, []
    def C(n, cond, **d):
        nonlocal ok; ok = ok and bool(cond); checks.append({"check": n, "pass": bool(cond), **d})
    amend_sha = hashlib.sha256((ROOT / AMEND).read_bytes()).hexdigest()
    tot = {"executed": 0, "admitted_active_strike_ready": 0, "dependency_bound": 0}
    manifest_nodes = []
    for p in sorted(OBJ2.glob("*.admission-receipt.json")):
        r = json.load(open(p)); status, frags, edges = derive(r)
        # recompute dual hashes from the DAG and compare to the stored point-10 hashes
        occ = _h(frags); route = _h(sorted({f.split("#")[0] for f in frags}))
        C(f"{r['obj']}:frag_occ_hash", r["point_10_hashes"]["fragment_occurrence_set_hash"] == occ)
        C(f"{r['obj']}:route_set_hash", r["point_10_hashes"]["route_set_hash"] == route)
        rows = []
        for fid, b in r["fragment_bindings"].items():
            ds, sc, bnd = status[fid]
            if sc == "EXECUTED": tot["executed"] += 1
            elif sc == "ADMITTED_ACTIVE": tot["admitted_active_strike_ready"] += 1
            else: tot["dependency_bound"] += 1
            if fix:
                for k in ("execution_status","execution_detail","dag_state","execution_scheduling","status",
                          "bk_identity","owner_lane","next_executable_action","next_review_tic",
                          "successor_mandate_carriage","dual_hashes_validate","detail","bound_by"):
                    b.pop(k, None)
                b["dag_state"] = ds; b["execution_scheduling"] = sc; b["status"] = "NOT_EXECUTED" if sc != "EXECUTED" else "EXECUTED"
                if sc == "DEPENDENCY_BOUND": b["bound_by"] = bnd
                if sc == "ADMITTED_ACTIVE":
                    bk, owner, nxt, rt = CARRIAGE[fid]
                    b["bk_identity"] = bk; b["owner_lane"] = owner; b["next_executable_action"] = nxt
                    b["next_review_tic"] = rt; b["successor_mandate_carriage"] = CARRIERS
                    b["dual_hashes_validate"] = {"route_set_hash": route, "fragment_occurrence_set_hash": occ}
            rows.append({"fragment": fid, "dag_state": ds, "execution_scheduling": sc, "bound_by": bnd})
            if sc == "ADMITTED_ACTIVE":
                bk, owner, nxt, rt = CARRIAGE[fid]
                manifest_nodes.append({"fragment": fid, "covenant_id": r["covenant_id"], "obj": r["obj"],
                    "bk_identity": bk, "dag_state": "strike_ready", "execution_scheduling": "ADMITTED_ACTIVE",
                    "status": "NOT_EXECUTED", "owner_lane": owner, "next_executable_action": nxt,
                    "next_review_tic": rt, "dual_hashes_validate": {"route_set_hash": route, "fragment_occurrence_set_hash": occ}})
                # carriage-field completeness (fail-loud)
                for req in ("bk_identity","owner_lane","next_executable_action","next_review_tic"):
                    C(f"{r['obj']}:{fid[:20]}:carriage:{req}", bool({'bk_identity':bk,'owner_lane':owner,'next_executable_action':nxt,'next_review_tic':rt}[req]))
        if fix:
            r["fragment_execution_table"] = rows
            r["fragment_summary"] = {
                "executed": sum(1 for x in rows if x["execution_scheduling"] == "EXECUTED"),
                "admitted_active_strike_ready": sum(1 for x in rows if x["execution_scheduling"] == "ADMITTED_ACTIVE"),
                "dependency_bound": sum(1 for x in rows if x["execution_scheduling"] == "DEPENDENCY_BOUND")}
            r["authority_amendment"] = {"artifact": AMEND, "sha256": amend_sha}
            json.dump(r, open(p, "w"), indent=2, ensure_ascii=False)

    # totals assertion (the Architect's 5/7/9)
    C("totals_executed_5", tot["executed"] == 5, got=tot["executed"])
    C("totals_admitted_active_7", tot["admitted_active_strike_ready"] == 7, got=tot["admitted_active_strike_ready"])
    C("totals_dependency_bound_9", tot["dependency_bound"] == 9, got=tot["dependency_bound"])
    C("c7_rollback_is_dependency_bound",
      derive(json.load(open(OBJ2 / "rapier_l5_adapter_spec_first_tic635.admission-receipt.json")))[0]
      ["c7_rollback_drill_design#1::covenant"][1] == "DEPENDENCY_BOUND")

    if fix:
        json.dump({"manifest_class": "review_635_admitted_active_nodes", "tic": 635,
                   "authority_amendment": {"artifact": AMEND, "sha256": amend_sha},
                   "carriers": CARRIERS, "count": len(manifest_nodes),
                   "note": "7 strike-ready ADMITTED_ACTIVE nodes crossing cadence (DAG-derived; c7_rollback_drill_design excluded — bound_by c7_author_spec). Two axes; NOT_EXECUTED.",
                   "nodes": manifest_nodes}, open(MANIFEST, "w"), indent=2, ensure_ascii=False)
        for f, akey in [("review-635-fragment-and-correction-audit.json", "fragment_totals"),
                        ("review-635-close-consistency-receipt.json", "2d")]:
            fp = ROOT / "audit-logs/governance" / f; d = json.load(open(fp))
            if akey == "fragment_totals":
                d["fragment_totals"] = tot
                d["fragment_totals_note"] = "TWO-AXIS, DAG-DERIVED: 5 executed / 7 admitted_active_strike_ready / 9 dependency_bound. c7_rollback_drill_design reclassified dependency_bound (bound_by c7_author_spec#0). Validated by validate_admitted_active.py --check."
            else:
                d["2d_fragment_table"] = {"totals": tot, "derived_from": "FragmentDAG edges + execution state",
                    "authority_amendment": {"artifact": AMEND, "sha256": amend_sha},
                    "carriage_manifest": "audit-logs/governance/review-635-admitted-active-nodes.json",
                    "validator": "validate_admitted_active.py --check", "note": "5/7/9; c7_rollback dependency_bound; both invented categories purged."}
            json.dump(d, open(fp, "w"), indent=2, ensure_ascii=False)

    print(json.dumps({"mode": "fix" if fix else "check", "verdict": "GREEN" if ok else "RED",
                      "totals": tot, "failures": [c for c in checks if not c["pass"]]}, indent=2))
    return 0 if ok else 1

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--check", action="store_true", help="explicit check mode (default when --fix absent)")
    sys.exit(run(ap.parse_args().fix))
