#!/usr/bin/env python3
"""validate-covenant-projection.py — board-projection contract check (covenant-splat skill, v2 tic 622).

Enforces the IMPLEMENTED subset of the kernel contract's acceptance assertions
(autonomous_kernel/covenant-splat-fqoq-runtime-spec.md §17) against the LIVE
board-state.json + route-metadata.json. Read-only; exit 0 = shape held, 1 = violation(s).

IMPLEMENTED (checked here):
  §17.1-adjacent  retired pre-v3 label absent from every classification field
  §17.4           every route-metadata entry carries a typed `derivation` object
                  (source pointers+hashes, or a declared human_override_seed with
                  disclosure) — prose-string derivations are violations
  §17.5           both classification axes present on every node (identity_class,
                  readiness_class) + five-axis covenant_projection block
  §17.6 (partial) exec_ready ⇒ projection_status == complete; the axis fail-closed
                  law holds: covenant/evidence axes null without drain receipt,
                  conformation ∈ {unknown, contradicted} without currency receipt,
                  execution ∈ {null, blocked_by_dependency, blocked_by_physics, parked}
                  without a runtime probe ('ready'/'current' are never invented)
  §17.5/§14       contradiction ⇒ conformation_status == contradicted AND not exec_ready
  set integrity   executable_identity_set == exec_ready nodes; identity/edge/executable
                  hashes RECOMPUTED and compared to the envelope; declared input hashes
                  + compiler hash recomputed (a mismatch = the slice's own invalidation
                  condition has fired — stale slice, regenerate)

NOT YET IMPLEMENTED (disclosed, never claimed): §17.2 (re-route-never-re-author —
behavioral), §17.3 (COVENANT_INSUFFICIENT — behavioral), §17.6 full readiness
conjunction (needs drain receipts + a runtime capability probe), §17.8 search-record
on evidence claims (needs drain receipts). The success line says SHAPE HELD, not
CONTRACT HELD, until these close.

Usage: validate-covenant-projection.py [--board FILE] [--zone-root DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

RETIRED = "blocked_by_evidence"
AXES = ("covenant_status", "projection_status", "conformation_status",
        "execution_status", "evidence_status")
CONFORMATION_PRE_DRAIN = {None, "unknown", "contradicted"}
EXECUTION_OBSERVED = {None, "blocked_by_dependency", "blocked_by_physics", "parked"}
UNIMPLEMENTED = ("§17.2 re-route-never-re-author (behavioral)",
                 "§17.3 COVENANT_INSUFFICIENT (behavioral)",
                 "§17.6 full readiness conjunction (needs drain receipts + runtime probe)",
                 "§17.8 evidence search-record (needs drain receipts)")


def find_root(start: Path) -> Path:
    p = start.resolve()
    while p != p.parent:
        if (p / "audit-logs" / "governance" / "harpoon-office").exists():
            return p
        p = p.parent
    raise SystemExit(
        "COVENANT_SPLAT_ZONE_UNAVAILABLE:\n"
        "  expected audit-logs/governance/harpoon-office above cwd\n"
        f"  searched from: {start.resolve()}\n"
        "  this skill is project-coupled; no validation was attempted")


def sha_ids(ids) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


# K1 (tic 624, ADDENDUM 6 pin 1): the point-10 comparison hash is domain-separated —
# ONE formula both sides; byte-identical mirrors in harpoon-sequencer.py and
# homeskillet-csl strict_boundary.rs. identity/edge hashes remain legacy.
ROUTE_SET_HASH_DOMAIN = "harpoon.route-set.v1"


def domain_hash(domain: str, ids) -> str:
    return hashlib.sha256((domain + "\n" + "\n".join(sorted(ids))).encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board")
    ap.add_argument("--zone-root")
    args = ap.parse_args()
    root = find_root(Path(args.zone_root) if args.zone_root else Path.cwd())
    office = root / "audit-logs" / "governance" / "harpoon-office"
    board_p = Path(args.board) if args.board else office / "board-state.json"
    board = json.loads(board_p.read_text(encoding="utf-8"))
    items = board.get("items") or {}
    violations: list[str] = []

    # ── per-node checks ──
    for bid, n in items.items():
        cls_fields = json.dumps({k: n.get(k) for k in
                                 ("readiness_class", "effective_classification", "identity_class")})
        if RETIRED in cls_fields:
            violations.append(f"{bid}: retired label in classification fields")
        if not n.get("identity_class") or not n.get("readiness_class"):
            violations.append(f"{bid}: a classification axis is missing (§17.5)")
        cp = n.get("covenant_projection")
        if not isinstance(cp, dict) or any(k not in cp for k in AXES):
            violations.append(f"{bid}: covenant_projection block missing/incomplete")
            continue
        has_receipt = n.get("drain_receipt") is not None
        # K1 single-writer law (tic 623 ruling, landed tic 624): covenant_status lifts
        # via the RESOLVED admission_resolution block — never via drain receipt alone,
        # never invented. The remaining drain-lifted axes still require the receipt.
        adm = n.get("admission_resolution") or {}
        if cp["covenant_status"] is not None and not adm.get("resolved"):
            violations.append(f"{bid}: covenant_status lifted without a RESOLVED "
                              "admission_resolution (single-writer breach)")
        if not has_receipt:
            if cp["evidence_status"] is not None:
                violations.append(f"{bid}: evidence_status invented without drain receipt")
            if cp["conformation_status"] not in CONFORMATION_PRE_DRAIN:
                violations.append(f"{bid}: conformation_status {cp['conformation_status']!r} "
                                  "invented without currency receipt (a stale thing can be "
                                  "freshly rendered)")
            if cp["execution_status"] not in EXECUTION_OBSERVED:
                violations.append(f"{bid}: execution_status {cp['execution_status']!r} invented "
                                  "without runtime probe")
        if n.get("exec_ready") and cp["projection_status"] != "complete":
            violations.append(f"{bid}: exec_ready without complete projection")
        if n.get("readiness_class") == "covenant_decomposition_unmaterialized":
            if n.get("exec_ready") or cp["projection_status"] != "partial":
                violations.append(f"{bid}: unmaterialized decomposition axis inconsistency")
        if n.get("contradiction"):
            if cp["conformation_status"] != "contradicted" or n.get("exec_ready"):
                violations.append(f"{bid}: contradiction not carried on conformation axis / executable")

    # ── set integrity + hash recomputation ──
    declared = set(board.get("executable_identity_set") or [])
    actual = {bid for bid, n in items.items() if n.get("exec_ready")}
    if declared != actual:
        violations.append(f"executable_identity_set mismatch: declared {sorted(declared)} "
                          f"vs actual {sorted(actual)}")
    env = board.get("conformation_envelope") or {}
    if (env.get("source") or {}).get("mode") != "live":
        violations.append("envelope source.mode != live")
    recomputed = {
        "identity_set_hash": sha_ids(items.keys()),
        "edge_set_hash": sha_ids(f"{d}->{bid}" for bid, n in items.items()
                                 for d in (n.get("unmet_deps") or [])),
        # domain-separated since tic 624 (hash-domain MIGRATION, not identity drift);
        # the envelope declares its formula — refuse an undeclared/legacy formula
        "executable_identity_set_hash": domain_hash(ROUTE_SET_HASH_DOMAIN, declared),
    }
    if (env.get("hash_formulas") or {}).get("executable_identity_set_hash") != ROUTE_SET_HASH_DOMAIN:
        violations.append("envelope hash_formulas does not declare "
                          f"executable_identity_set_hash under {ROUTE_SET_HASH_DOMAIN} "
                          "(legacy/undeclared formula — regenerate the slice)")
    for h, val in recomputed.items():
        if not env.get(h):
            violations.append(f"envelope missing {h}")
        elif env[h] != val:
            violations.append(f"{h} RECOMPUTATION MISMATCH: envelope {env[h][:16]}… vs "
                              f"recomputed {val[:16]}…")
    # declared input hashes + compiler hash — a mismatch means the slice's own
    # invalidation condition fired (stale slice), which is a failure to act on
    for rel, declared_sha in (env.get("inputs") or {}).items():
        f = root / rel
        if not f.exists():
            violations.append(f"declared input vanished: {rel}")
        elif hashlib.sha256(f.read_bytes()).hexdigest() != declared_sha:
            violations.append(f"slice invalidated: input hash changed since generation: {rel}")
    comp = env.get("compiler") or {}
    if comp.get("path") and comp.get("sha256"):
        cf = root / comp["path"]
        if cf.exists() and hashlib.sha256(cf.read_bytes()).hexdigest() != comp["sha256"]:
            violations.append("slice invalidated: compiler hash changed since generation")

    # ── §17.4: route-metadata provenance ──
    rm_p = office / "route-metadata.json"
    if rm_p.exists():
        try:
            rm = json.loads(rm_p.read_text(encoding="utf-8"))
        except Exception as e:
            violations.append(f"route-metadata.json malformed: {e}")
            rm = {}
        for bid, entry in rm.items():
            if bid.startswith("_") or not isinstance(entry, dict):
                continue
            der = entry.get("derivation")
            if der is None or isinstance(der, str):
                violations.append(f"route-metadata[{bid}]: derivation missing or prose-string "
                                  "(§17.4 — needs typed object w/ source pointers or declared "
                                  "human_override_seed)")
            elif isinstance(der, dict):
                seed = der.get("kind") == "human_override_seed"
                if not seed and not der.get("source_pointers_sha16"):
                    violations.append(f"route-metadata[{bid}]: derived entry lacks "
                                      "source_pointers_sha16 (§17.4)")

    n_unmat = sum(1 for n in items.values()
                  if n.get("readiness_class") == "covenant_decomposition_unmaterialized")
    print(f"validate-covenant-projection v2: {len(items)} nodes · "
          f"{len(actual)} exec_ready · {n_unmat} covenant_decomposition_unmaterialized · "
          f"hashes recomputed 3/3 + {len(env.get('inputs') or {})} inputs + compiler")
    if violations:
        for v in violations:
            print(f"  [VIOLATION] {v}")
        print(f"PROJECTION SHAPE BROKEN — {len(violations)} violation(s)")
        return 1
    print("PROJECTION SHAPE HELD — implemented §17 projection assertions pass")
    print("  unimplemented (disclosed, not claimed): " + " · ".join(UNIMPLEMENTED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
