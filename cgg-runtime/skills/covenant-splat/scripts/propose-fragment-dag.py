#!/usr/bin/env python3
"""propose-fragment-dag.py — deterministic CovenantExpr → FragmentDAG lowering (covenant-splat skill).

Mirrors the homeskillet-csl lowering contract (references/lowering-interface.md):
  Sequential ⊳  creates dependency edges (all sinks of A → all sources of B)
  Parallel  ∥  creates NO cross-edges
  Choice    ⊕  stays honest branch metadata until selected — NEVER flattened into edges
Waves derive by Kahn dependency-grouping. Cycles are refused loudly.

Input JSON: a CovenantExpr — either a string leaf (fragment id) or
  {"op": "seq"|"parallel"|"choice", "operands": [expr, ...]}
Output JSON: {"fragments", "edges", "waves", "choices", "validation"}

This is a PROPOSAL artifact (bounded morphism, spec §9): it carries no authority and
writes no federation surface. Ordering must be constructed here (upstream) — the
crates execute topology; they do not infer it.

Usage: propose-fragment-dag.py <expr.json> | --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class Lowered:
    def __init__(self):
        self.fragments: list[str] = []
        self.edges: list[tuple[str, str]] = []
        self.choices: list[dict] = []


def lower(expr, acc: Lowered) -> tuple[list[str], list[str]]:
    """Returns (sources, sinks) of the lowered subgraph."""
    if isinstance(expr, str):
        if expr not in acc.fragments:
            acc.fragments.append(expr)
        return [expr], [expr]
    if not isinstance(expr, dict) or "op" not in expr or "operands" not in expr:
        raise ValueError(f"malformed CovenantExpr node: {expr!r}")
    op, operands = expr["op"], expr["operands"]
    if not operands:
        raise ValueError(f"empty operands under op={op!r}")
    if op == "seq":
        srcs, sinks = None, None
        for operand in operands:
            s2, k2 = lower(operand, acc)
            if sinks is not None:
                for a in sinks:
                    for b in s2:
                        if (a, b) not in acc.edges:
                            acc.edges.append((a, b))
            if srcs is None:
                srcs = s2
            sinks = k2
        return srcs, sinks
    if op == "parallel":
        srcs, sinks = [], []
        for operand in operands:
            s2, k2 = lower(operand, acc)
            srcs += s2
            sinks += k2
        return srcs, sinks
    if op == "choice":
        branches = []
        srcs, sinks = [], []
        for operand in operands:
            s2, k2 = lower(operand, acc)
            branches.append({"sources": s2, "sinks": k2})
            srcs += s2
            sinks += k2
        acc.choices.append({"branches": branches,
                            "note": "honest branch metadata — unselected; no edges minted"})
        return srcs, sinks
    raise ValueError(f"unknown op {op!r} (expected seq|parallel|choice)")


def kahn_waves(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    succ = {n: set() for n in nodes}
    indeg = {n: 0 for n in nodes}
    for a, b in edges:
        if b not in succ[a]:
            succ[a].add(b)
            indeg[b] += 1
    frontier = sorted(n for n in nodes if indeg[n] == 0)
    waves, placed = [], 0
    while frontier:
        nxt = set()
        for n in frontier:
            for s in succ[n]:
                indeg[s] -= 1
                if indeg[s] == 0:
                    nxt.add(s)
        placed += len(frontier)
        waves.append(sorted(frontier))
        frontier = sorted(nxt)
    if placed != len(nodes):
        raise ValueError(f"cycle detected — not a DAG (unresolved: "
                         f"{sorted(n for n, d in indeg.items() if d > 0)})")
    return waves


def propose(expr) -> dict:
    acc = Lowered()
    lower(expr, acc)
    waves = kahn_waves(acc.fragments, acc.edges)
    return {
        "_law": "proposal only — no authority, no write; the covenant authorizes, "
                "the receipt proves (covenant-splat-fqoq-runtime-spec.md §9/§13)",
        "fragments": acc.fragments,
        "edges": [list(e) for e in acc.edges],
        "waves": waves,
        "choices": acc.choices,
        "validation": {"acyclic": True, "fragment_count": len(acc.fragments),
                       "edge_count": len(acc.edges), "choice_count": len(acc.choices)},
    }


def selftest() -> int:
    ok = True

    def t(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    r = propose({"op": "seq", "operands": ["build", "test", "deploy"]})
    t("seq_creates_dependency_edges_and_ordered_waves",
      r["edges"] == [["build", "test"], ["test", "deploy"]] and
      r["waves"] == [["build"], ["test"], ["deploy"]])
    r = propose({"op": "parallel", "operands": ["a", "b", "c"]})
    t("parallel_creates_no_edges_single_wave", r["edges"] == [] and r["waves"] == [["a", "b", "c"]])
    r = propose({"op": "choice", "operands": ["x", "y"]})
    t("choice_stays_branch_metadata_no_edges",
      r["edges"] == [] and len(r["choices"]) == 1 and len(r["choices"][0]["branches"]) == 2)
    r = propose({"op": "seq", "operands": [
        {"op": "parallel", "operands": ["a1", "a2"]}, "join"]})
    t("seq_over_parallel_fans_into_join",
      sorted(map(tuple, r["edges"])) == [("a1", "join"), ("a2", "join")] and
      r["waves"] == [["a1", "a2"], ["join"]])
    try:
        kahn_waves(["a", "b"], [("a", "b"), ("b", "a")])
        t("cycles_refused", False)
    except ValueError:
        t("cycles_refused", True)
    try:
        propose({"op": "warp", "operands": ["a"]})
        t("unknown_op_refused", False)
    except ValueError:
        t("unknown_op_refused", True)
    print("selftest:", "GREEN" if ok else "RED")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expr_file", nargs="?")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.expr_file:
        ap.error("expr_file required (or --selftest)")
    expr = json.loads(Path(args.expr_file).read_text(encoding="utf-8"))
    print(json.dumps(propose(expr), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
