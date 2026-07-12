#!/usr/bin/env python3
"""lower-covenant-expr.py — deterministic CovenantExpr → FragmentDAG lowering (covenant-splat skill).

PARITY-FAITHFUL mirror of the homeskillet-csl lowering contract
(crates/harpoon_bridge/src/covenant_composition.rs + fragment_dag.rs):

  fragment ids   occurrence-namespaced: `{id}#{occ}::obj-{i}` (per objective) or
                 `{id}#{occ}::covenant` (leaf without objectives); occ = pre-order
                 leaf counter — the SAME covenant may appear twice without collision
  Sequential ⊳   dependency edges: EVERY left-sink × EVERY right-source
  Parallel  ∥    NO cross-edges
  Choice    ⊕    group `g{n}` allocated OUTER-FIRST; each fragment carries its FULL
                 choice ancestry as tags {group, branch∈L|R}; n-ary choice folds
                 left-associative (A⊕B⊕C = Choice(Choice(A,B),C): outer=g0, inner=g1)
  resolution     a fragment survives iff, for EVERY resolved group in its ancestry,
                 it sits on the chosen branch; unresolved groups are kept; an edge
                 survives iff both endpoints survive
  waves          Kahn dependency-grouping, sorted within a wave (deterministic)

This id scheme is the acceptance-point-10 parity hazard: any Rust↔Python
executable-set hash equality must hash the SAME identities this scheme produces.

This is a LOWERER, not a proposer (bounded morphism law, kernel spec §9): the
CovenantExpr it consumes was already proposed upstream; this script carries no
authority and writes no federation surface.

Input JSON: a CovenantExpr — a leaf (string id, or {"id", "objectives":[...],
"title"?}) or {"op": "seq"|"parallel"|"choice", "operands": [expr, ...]}.

Usage: lower-covenant-expr.py <expr.json> [--pick g0=L --pick g1=R ...] | --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class LowerCtx:
    def __init__(self):
        self.node_seq = 0
        self.choice_seq = 0
        self.fragments: list[dict] = []   # {id, label, choices:[{group,branch}]}
        self.edges: list[tuple[str, str]] = []


def _fold_nary(expr):
    """Normalize n-ary op nodes to the binary tree the Rust builders produce
    (left-associative: A.op(B).op(C) = Op(Op(A,B),C))."""
    if not isinstance(expr, dict) or "op" not in expr:
        return expr
    op, operands = expr["op"], expr.get("operands", [])
    if op not in ("seq", "parallel", "choice"):
        raise ValueError(f"unknown op {op!r} (expected seq|parallel|choice)")
    if not operands:
        raise ValueError(f"empty operands under op={op!r}")
    operands = [_fold_nary(o) for o in operands]
    node = operands[0]
    for nxt in operands[1:]:
        node = {"op": op, "operands": [node, nxt]}
    return node


def _lower(expr, ctx: LowerCtx, choices: list[dict]) -> tuple[list[str], list[str]]:
    """Returns (sources, sinks) of the lowered subgraph. `choices` = ambient ancestry."""
    if isinstance(expr, str) or (isinstance(expr, dict) and "op" not in expr):
        # leaf — occurrence-namespaced
        if isinstance(expr, str):
            leaf_id, objectives, label_base = expr, [], expr
        else:
            leaf_id = expr.get("id")
            if not leaf_id:
                raise ValueError(f"leaf object missing 'id': {expr!r}")
            objectives = expr.get("objectives") or []
            label_base = expr.get("title") or leaf_id
        occ = ctx.node_seq
        ctx.node_seq += 1
        ids: list[str] = []
        if objectives:
            for i, obj in enumerate(objectives):
                fid = f"{leaf_id}#{occ}::obj-{i}"
                ctx.fragments.append({"id": fid, "label": obj, "choices": list(choices)})
                ids.append(fid)
        else:
            fid = f"{leaf_id}#{occ}::covenant"
            ctx.fragments.append({"id": fid, "label": label_base, "choices": list(choices)})
            ids.append(fid)
        return ids, ids  # independent objectives: sources == sinks == all ids

    op, (left, right) = expr["op"], expr["operands"]
    if op == "seq":
        l_src, l_snk = _lower(left, ctx, choices)
        r_src, r_snk = _lower(right, ctx, choices)
        for a in l_snk:
            for b in r_src:
                if (a, b) not in ctx.edges:
                    ctx.edges.append((a, b))
        return l_src, r_snk
    if op == "parallel":
        l_src, l_snk = _lower(left, ctx, choices)
        r_src, r_snk = _lower(right, ctx, choices)
        return l_src + r_src, l_snk + r_snk
    if op == "choice":
        group = f"g{ctx.choice_seq}"          # allocated OUTER-FIRST, before branches lower
        ctx.choice_seq += 1
        l_src, l_snk = _lower(left, ctx, choices + [{"group": group, "branch": "L"}])
        r_src, r_snk = _lower(right, ctx, choices + [{"group": group, "branch": "R"}])
        return l_src + r_src, l_snk + r_snk
    raise ValueError(f"unknown op {op!r}")


def resolve_choices(fragments: list[dict], edges: list[tuple[str, str]],
                    picks: dict[str, str]) -> tuple[list[dict], list[tuple[str, str]]]:
    """Mirror of fragment_dag::resolve_choices: survive iff on the chosen branch of
    EVERY resolved group carried; unresolved groups kept; edges need both endpoints."""
    def survives(frag: dict) -> bool:
        return all(t["branch"] == picks[t["group"]]
                   for t in frag["choices"] if t["group"] in picks)
    kept = [f for f in fragments if survives(f)]
    kept_ids = {f["id"] for f in kept}
    kept_edges = [(a, b) for a, b in edges if a in kept_ids and b in kept_ids]
    return kept, kept_edges


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


def lower_expr(expr, picks: dict[str, str] | None = None) -> dict:
    ctx = LowerCtx()
    _lower(_fold_nary(expr), ctx, [])
    fragments, edges = ctx.fragments, ctx.edges
    resolved = None
    if picks:
        fragments, edges = resolve_choices(fragments, edges, picks)
        resolved = dict(picks)
    ids = [f["id"] for f in fragments]
    waves = kahn_waves(ids, edges)
    groups: dict[str, dict] = {}
    for f in fragments:
        for t in f["choices"]:
            groups.setdefault(t["group"], {"L": [], "R": []})[t["branch"]].append(f["id"])
    return {
        "_law": "lowering only — no authority, no write; ids are the point-10 parity "
                "identities (occurrence-namespaced per the csl contract); the covenant "
                "authorizes, the receipt proves (kernel spec §9/§13)",
        "fragments": fragments,
        "edges": [list(e) for e in edges],
        "waves": waves,
        "choice_groups": [{"group": g, "branches": b} for g, b in sorted(groups.items())],
        "resolved_picks": resolved,
        "validation": {"acyclic": True, "fragment_count": len(fragments),
                       "edge_count": len(edges), "choice_group_count": len(groups)},
    }


def selftest() -> int:
    ok = True

    def t(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    r = lower_expr({"op": "seq", "operands": ["build", "test", "deploy"]})
    t("1_seq_edges_and_ordered_waves_namespaced",
      r["edges"] == [["build#0::covenant", "test#1::covenant"],
                     ["test#1::covenant", "deploy#2::covenant"]] and
      r["waves"] == [["build#0::covenant"], ["test#1::covenant"], ["deploy#2::covenant"]])
    r = lower_expr({"op": "seq", "operands": ["inspect", "inspect"]})
    t("2_duplicate_leaf_two_lawful_occurrences_no_collapse",
      [f["id"] for f in r["fragments"]] == ["inspect#0::covenant", "inspect#1::covenant"] and
      r["edges"] == [["inspect#0::covenant", "inspect#1::covenant"]] and
      len(r["waves"]) == 2)
    r = lower_expr({"op": "parallel", "operands": ["a", "b", "c"]})
    t("3_parallel_no_edges_single_wave", r["edges"] == [] and len(r["waves"]) == 1 and
      len(r["fragments"]) == 3)
    r = lower_expr({"op": "choice", "operands": ["x", "y"]})
    t("4_choice_branch_tags_no_edges",
      r["edges"] == [] and
      r["fragments"][0]["choices"] == [{"group": "g0", "branch": "L"}] and
      r["fragments"][1]["choices"] == [{"group": "g0", "branch": "R"}])
    r = lower_expr({"op": "choice", "operands": [
        {"op": "seq", "operands": ["shared", "a"]},
        {"op": "seq", "operands": ["shared", "b"]}]})
    shared_tags = {f["id"]: f["choices"] for f in r["fragments"] if f["id"].startswith("shared")}
    t("5_shared_leaf_across_branches_distinct_occurrences_and_ancestry",
      len(shared_tags) == 2 and
      shared_tags["shared#0::covenant"] == [{"group": "g0", "branch": "L"}] and
      shared_tags["shared#2::covenant"] == [{"group": "g0", "branch": "R"}])
    # nested: Choice(Choice(A,B),C) — outer g0, inner g1; picks {g0:L, g1:R} -> B only
    nested = {"op": "choice", "operands": [{"op": "choice", "operands": ["A", "B"]}, "C"]}
    r = lower_expr(nested, picks={"g0": "L", "g1": "R"})
    t("6_nested_choice_outer_g0_inner_g1_resolution_prunes",
      [f["id"] for f in r["fragments"]] == ["B#1::covenant"])
    r = lower_expr({"op": "seq", "operands": [{"op": "choice", "operands": ["a", "b"]}, "join"]})
    t("7_choice_inside_sequence_both_branches_edge_to_join",
      sorted(map(tuple, r["edges"])) == [("a#0::covenant", "join#2::covenant"),
                                          ("b#1::covenant", "join#2::covenant")])
    r2 = lower_expr({"op": "seq", "operands": [{"op": "choice", "operands": ["a", "b"]}, "join"]},
                    picks={"g0": "L"})
    t("8_resolution_inside_sequence_keeps_chosen_edge_only",
      r2["edges"] == [["a#0::covenant", "join#2::covenant"]])
    r = lower_expr({"op": "choice", "operands": [{"op": "seq", "operands": ["x", "y"]}, "z"]})
    t("9_sequence_inside_choice_edge_carries_branch_tags",
      r["edges"] == [["x#0::covenant", "y#1::covenant"]] and
      all(f["choices"] == [{"group": "g0", "branch": "L"}]
          for f in r["fragments"] if f["id"][0] in "xy"))
    r = lower_expr({"op": "choice", "operands": ["a", "b", "c"]})
    by_id = {f["id"]: f["choices"] for f in r["fragments"]}
    t("10_three_way_choice_left_assoc_ancestry",
      by_id["c#2::covenant"] == [{"group": "g0", "branch": "R"}] and
      by_id["a#0::covenant"] == [{"group": "g0", "branch": "L"}, {"group": "g1", "branch": "L"}] and
      by_id["b#1::covenant"] == [{"group": "g0", "branch": "L"}, {"group": "g1", "branch": "R"}])
    r = lower_expr({"op": "seq", "operands": [
        {"id": "cov1", "objectives": ["o1", "o2"]}, {"id": "cov2", "objectives": ["p1"]}]})
    t("11_objective_leaves_obj_ids_and_full_fanin",
      [f["id"] for f in r["fragments"]] == ["cov1#0::obj-0", "cov1#0::obj-1", "cov2#1::obj-0"] and
      sorted(map(tuple, r["edges"])) == [("cov1#0::obj-0", "cov2#1::obj-0"),
                                          ("cov1#0::obj-1", "cov2#1::obj-0")])
    try:
        lower_expr({"op": "warp", "operands": ["a"]})
        t("12_unknown_op_refused", False)
    except ValueError:
        t("12_unknown_op_refused", True)
    try:
        kahn_waves(["a", "b"], [("a", "b"), ("b", "a")])
        t("13_cycle_guard_refuses", False)
    except ValueError:
        t("13_cycle_guard_refuses", True)
    print("selftest:", "GREEN" if ok else "RED")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expr_file", nargs="?")
    ap.add_argument("--pick", action="append", default=[],
                    help="resolve a choice group, e.g. --pick g0=L (repeatable)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.expr_file:
        ap.error("expr_file required (or --selftest)")
    picks = {}
    for p in args.pick:
        if "=" not in p:
            ap.error(f"--pick expects group=branch, got {p!r}")
        g, b = p.split("=", 1)
        if b not in ("L", "R"):
            ap.error(f"branch must be L or R, got {b!r}")
        picks[g] = b
    expr = json.loads(Path(args.expr_file).read_text(encoding="utf-8"))
    print(json.dumps(lower_expr(expr, picks=picks or None), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
