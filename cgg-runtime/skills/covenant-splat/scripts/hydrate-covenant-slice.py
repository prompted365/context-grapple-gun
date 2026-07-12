#!/usr/bin/env python3
"""hydrate-covenant-slice.py — CovenantSlice SCAFFOLD hydration (covenant-splat skill, tic 622).

Gathers the COMPILER-VISIBLE current field for one backlog identity and emits a
CovenantSlice scaffold per autonomous_kernel/covenant-splat-fqoq-runtime-spec.md §6:
identity + reality-state inputs + typed-NULL facet slots + source-tense + input hashes.

WHAT THIS IS NOT (the bounded-morphism law, spec §9):
  - It does NOT locate or invent the admitted covenant (covenant_ref stays null — the
    drain's step 2 is a judgment-bearing search, not a script).
  - It does NOT fill the six facets (that is the agentic interpreter's work).
  - It does NOT write any federation surface (stdout / --out only).
A null in the scaffold is a demand for real work, never a default to be papered over.

Usage: hydrate-covenant-slice.py <backlog-id> [--out FILE] [--zone-root DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def find_root(start: Path) -> Path:
    p = start.resolve()
    while p != p.parent:
        if (p / "audit-logs" / "governance" / "backlog" / "backlog.jsonl").exists():
            return p
        p = p.parent
    raise SystemExit("federation root not found (no audit-logs/governance/backlog above cwd)")


def latest_per_id(jsonl: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" in rec:
            out[rec["id"]] = rec
    return out


def sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def build_slice(root: Path, bid: str) -> dict:
    gov = root / "audit-logs" / "governance"
    office = gov / "harpoon-office"
    backlog_p = gov / "backlog" / "backlog.jsonl"
    board_p = office / "board-state.json"
    rm_p = office / "route-metadata.json"
    gr_p = office / "gate-resolutions.json"
    xw_p = office / "crosswalk-tic621" / "legacy-to-current-crosswalk.json"
    spec_p = root / "autonomous_kernel" / "covenant-splat-fqoq-runtime-spec.md"

    backlog = latest_per_id(backlog_p)
    row = backlog.get(bid)
    if row is None:
        raise SystemExit(f"identity {bid!r} not found in backlog latest-per-id set")

    board = load(board_p, {}) or {}
    node = (board.get("items") or {}).get(bid)
    rm = {k: v for k, v in (load(rm_p, {}) or {}).items() if not k.startswith("_")}
    gr = {k: v for k, v in (load(gr_p, {}) or {}).items() if not k.startswith("_")}
    xw_all = load(xw_p, {}) or {}
    xw = next((v for v in xw_all.values()
               if isinstance(v, dict) and v.get("canonical_backlog_id") == bid), None)

    typed_null = None  # explicit: a slot the agentic interpreter must fill or return COVENANT_INSUFFICIENT

    return {
        "slice_type": "CovenantSlice-scaffold/v1-tic622",
        "_law": ("scaffold per covenant-splat-fqoq-runtime-spec.md §6; nulls are typed demands "
                 "for the drain/interpreter — never defaults; a backlog row is not a covenant"),
        "identity": {"backlog_id": bid, "lane": row.get("lane"), "state": row.get("state"),
                     "title": row.get("title"), "depends_on": row.get("depends_on") or []},
        "covenant_ref": typed_null,          # admission locator — drain step 2 (judgment, not script)
        "admission_receipt": typed_null,
        "reality_state": {
            "_source_note": "compiler-visible field only; route_metadata is a DERIVED CACHE lens "
                            "(never semantic authority, spec §15); board_node carries the five-status axes",
            "backlog_row": row,
            "board_node": node,
            "route_metadata_lens": rm.get(bid),
            "gate_resolution": gr.get(bid),
            "crosswalk": xw,
        },
        "target_state": {
            "declared_title": row.get("title"),
            "_warning": "title/notes are NOT the covenant target — locate the admitted covenant; "
                        "if none exists the route is covenant_absent",
            "target": typed_null,
        },
        "six_facet": {"KAT": typed_null, "APO": typed_null, "PAR": typed_null,
                      "PLE": typed_null, "ENA": typed_null, "TEL": typed_null,
                      "_note": "cross-bound ONE record when filled (spec §7)"},
        "working_centroid_refs": [],
        "center_exclusion": True,
        "lawful_traversal_candidates": typed_null,
        "excluded": typed_null,
        "de_considered": typed_null,
        "suspended": typed_null,
        "live_under_conditions": typed_null,
        "renarrow_triggers": ["any input hash below changes", "operative tic advances",
                              "gate-resolutions or route-metadata edited",
                              "admitted covenant located (covenant_ref filled)"],
        "source_tense": "compiled-at-generation",
        "input_hashes": {
            str(p.relative_to(root)): sha(p)
            for p in (backlog_p, board_p, rm_p, gr_p, xw_p, spec_p)
        },
        "operative_tic": (board.get("conformation_envelope") or {}).get("operative_tic"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("backlog_id")
    ap.add_argument("--out")
    ap.add_argument("--zone-root")
    args = ap.parse_args()
    root = find_root(Path(args.zone_root) if args.zone_root else Path.cwd())
    s = build_slice(root, args.backlog_id)
    text = json.dumps(s, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
