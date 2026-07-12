#!/usr/bin/env python3
"""validate-covenant-projection.py — board-projection contract check (covenant-splat skill).

Enforces the kernel contract's acceptance assertions (covenant-splat-fqoq-runtime-spec.md §17)
against the LIVE board-state.json. Read-only; exit 0 = contract held, 1 = violation(s).

Checks:
  1. the retired pre-v3 label never appears in any node classification field
  2. every node carries the five-status covenant_projection block (all five keys)
  3. nulls-never-invented: covenant_status / evidence_status are null unless the node
     carries a drain receipt (drain_receipt field) — the compiler must not claim admission
  4. exec_ready ⇒ projection_status == complete AND execution_status == ready
  5. covenant_decomposition_unmaterialized ⇒ NOT exec_ready AND projection_status == partial
  6. contradiction present ⇒ conformation_status == contradicted AND not exec_ready
  7. executable_identity_set == the set of nodes with exec_ready true
  8. conformation envelope carries mode=live + the three identity/edge/executable hashes

Usage: validate-covenant-projection.py [--board FILE] [--zone-root DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RETIRED = "blocked_by_evidence"
AXES = ("covenant_status", "projection_status", "conformation_status",
        "execution_status", "evidence_status")


def find_root(start: Path) -> Path:
    p = start.resolve()
    while p != p.parent:
        if (p / "audit-logs" / "governance" / "harpoon-office").exists():
            return p
        p = p.parent
    raise SystemExit("federation root not found")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board")
    ap.add_argument("--zone-root")
    args = ap.parse_args()
    if args.board:
        board_p = Path(args.board)
    else:
        root = find_root(Path(args.zone_root) if args.zone_root else Path.cwd())
        board_p = root / "audit-logs" / "governance" / "harpoon-office" / "board-state.json"
    board = json.loads(board_p.read_text(encoding="utf-8"))
    items = board.get("items") or {}
    violations: list[str] = []

    for bid, n in items.items():
        cls_fields = json.dumps({k: n.get(k) for k in
                                 ("readiness_class", "effective_classification", "identity_class")})
        if RETIRED in cls_fields:
            violations.append(f"{bid}: retired label in classification fields")
        cp = n.get("covenant_projection")
        if not isinstance(cp, dict) or any(k not in cp for k in AXES):
            violations.append(f"{bid}: covenant_projection block missing/incomplete")
            continue
        if n.get("drain_receipt") is None:
            if cp["covenant_status"] is not None:
                violations.append(f"{bid}: covenant_status invented without drain receipt")
            if cp["evidence_status"] is not None:
                violations.append(f"{bid}: evidence_status invented without drain receipt")
        if n.get("exec_ready"):
            if cp["projection_status"] != "complete" or cp["execution_status"] != "ready":
                violations.append(f"{bid}: exec_ready without complete projection / ready execution axis")
        if n.get("readiness_class") == "covenant_decomposition_unmaterialized":
            if n.get("exec_ready") or cp["projection_status"] != "partial":
                violations.append(f"{bid}: unmaterialized decomposition axis inconsistency")
        if n.get("contradiction"):
            if cp["conformation_status"] != "contradicted" or n.get("exec_ready"):
                violations.append(f"{bid}: contradiction not carried on conformation axis / executable")

    declared = set(board.get("executable_identity_set") or [])
    actual = {bid for bid, n in items.items() if n.get("exec_ready")}
    if declared != actual:
        violations.append(f"executable_identity_set mismatch: declared {sorted(declared)} "
                          f"vs actual {sorted(actual)}")

    env = board.get("conformation_envelope") or {}
    if (env.get("source") or {}).get("mode") != "live":
        violations.append("envelope source.mode != live")
    for h in ("identity_set_hash", "edge_set_hash", "executable_identity_set_hash"):
        if not env.get(h):
            violations.append(f"envelope missing {h}")

    n_unmat = sum(1 for n in items.values()
                  if n.get("readiness_class") == "covenant_decomposition_unmaterialized")
    print(f"validate-covenant-projection: {len(items)} nodes · "
          f"{len(actual)} exec_ready · {n_unmat} covenant_decomposition_unmaterialized")
    if violations:
        for v in violations:
            print(f"  [VIOLATION] {v}")
        print(f"CONTRACT BROKEN — {len(violations)} violation(s)")
        return 1
    print("CONTRACT HELD — all §17 assertions pass on this projection")
    return 0


if __name__ == "__main__":
    sys.exit(main())
