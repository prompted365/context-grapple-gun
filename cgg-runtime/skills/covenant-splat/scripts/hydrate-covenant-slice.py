#!/usr/bin/env python3
"""hydrate-covenant-slice.py — CovenantSlice SCAFFOLD hydration (covenant-splat skill, v2 tic 622).

Gathers the COMPILER-VISIBLE current field for one backlog identity and emits a
CovenantSlice scaffold per autonomous_kernel/covenant-splat-fqoq-runtime-spec.md §6:
identity + reality-state inputs + typed-NULL facet slots + source-tense + input hashes
+ a per-source status envelope.

FAIL-CLOSED SOURCE CONTRACT (the zero-conflation law — absence ≠ malformed ≠ blindness):
  required source missing     -> nonzero exit, named path (COVENANT_SPLAT_SOURCE_MISSING)
  required source malformed   -> nonzero exit, path + parse error (COVENANT_SPLAT_SOURCE_MALFORMED)
  optional source absent      -> source_status[..].state = "unavailable" (typed, never a default)
  optional source malformed   -> source_status[..].state = "malformed" + reason (never empty default)
Outside a federation zone -> COVENANT_SPLAT_ZONE_UNAVAILABLE (typed, no covenant judgment attempted).

WHAT THIS IS NOT (bounded-morphism law, spec §9): it does NOT locate/invent the admitted
covenant (covenant_ref stays null — drain step 2 is judgment, not a script); it does NOT
fill the six facets (the agentic interpreter's work); it writes NO federation surface
(stdout / --out only). A null is a demand for real work, never a default.

Usage: hydrate-covenant-slice.py <backlog-id> [--out FILE] [--zone-root DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SPEC_REL = "autonomous_kernel/covenant-splat-fqoq-runtime-spec.md"


def find_root(start: Path) -> Path:
    p = start.resolve()
    while p != p.parent:
        if (p / "audit-logs" / "governance" / "backlog" / "backlog.jsonl").exists() \
                and (p / SPEC_REL).exists():
            return p
        p = p.parent
    raise SystemExit(
        "COVENANT_SPLAT_ZONE_UNAVAILABLE:\n"
        f"  expected {SPEC_REL} + audit-logs/governance/backlog/backlog.jsonl above cwd\n"
        f"  searched from: {start.resolve()}\n"
        "  this skill is project-coupled; no covenant judgment was attempted")


def load_required_jsonl_latest(p: Path) -> dict[str, dict]:
    """Required source: missing or malformed rows are LOUD, never apparent absence."""
    if not p.exists():
        raise SystemExit(f"COVENANT_SPLAT_SOURCE_MISSING: required source absent: {p}")
    out: dict[str, dict] = {}
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            raise SystemExit(f"COVENANT_SPLAT_SOURCE_MALFORMED: {p}:{i}: {e}") from e
        if "id" in rec:
            out[rec["id"]] = rec
    return out


def load_optional(p: Path, status: dict, key: str):
    """Optional source: typed unavailable / malformed states — never a silent default."""
    if not p.exists():
        status[key] = {"state": "unavailable", "reason": f"not found: {p.name}"}
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        status[key] = {"state": "loaded"}
        return data
    except Exception as e:
        status[key] = {"state": "malformed", "reason": f"{type(e).__name__}: {e}"}
        return None


def sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def build_slice(root: Path, bid: str) -> dict:
    gov = root / "audit-logs" / "governance"
    office = gov / "harpoon-office"
    backlog_p = gov / "backlog" / "backlog.jsonl"
    board_p = office / "board-state.json"
    rm_p = office / "route-metadata.json"
    gr_p = office / "gate-resolutions.json"
    xw_p = office / "crosswalk-tic621" / "legacy-to-current-crosswalk.json"
    spec_p = root / SPEC_REL

    backlog = load_required_jsonl_latest(backlog_p)
    row = backlog.get(bid)
    if row is None:
        raise SystemExit(f"COVENANT_SPLAT_IDENTITY_UNKNOWN: {bid!r} not in the backlog "
                         "latest-per-id set (identity precedes hydration)")

    source_status: dict[str, dict] = {"backlog": {"state": "loaded", "records": len(backlog)}}
    board = load_optional(board_p, source_status, "board")
    rm_raw = load_optional(rm_p, source_status, "route_metadata")
    gr_raw = load_optional(gr_p, source_status, "gate_resolutions")
    xw_raw = load_optional(xw_p, source_status, "crosswalk")

    node = ((board or {}).get("items") or {}).get(bid)
    rm = {k: v for k, v in (rm_raw or {}).items() if not k.startswith("_")} if rm_raw else {}
    gr = {k: v for k, v in (gr_raw or {}).items() if not k.startswith("_")} if gr_raw else {}
    xw = next((v for v in (xw_raw or {}).values()
               if isinstance(v, dict) and v.get("canonical_backlog_id") == bid), None)

    typed_null = None  # a slot the drain/interpreter must fill or return COVENANT_INSUFFICIENT

    return {
        "slice_type": "CovenantSlice-scaffold/v2-tic622",
        "_law": ("scaffold per covenant-splat-fqoq-runtime-spec.md §6; nulls are typed demands "
                 "for the drain/interpreter — never defaults; a backlog row is not a covenant; "
                 "source_status keeps absence, malformation, and blindness distinct"),
        "source_status": source_status,
        "identity": {"backlog_id": bid, "lane": row.get("lane"), "state": row.get("state"),
                     "title": row.get("title"), "depends_on": row.get("depends_on") or []},
        "covenant_ref": typed_null,          # admission locator — drain step 2 (judgment, not script)
        "admission_receipt": typed_null,
        "reality_state": {
            "_source_note": "compiler-visible field only; route_metadata is a DERIVED CACHE lens "
                            "(never semantic authority, spec §15); board_node carries the "
                            "five-status axes under the §14 axis fail-closed law",
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
        "center_exclusion": {
            "required": True,
            "source": f"{SPEC_REL}#4-fqoq-and-held-open-center-invariants",
            "verified_for_route": typed_null,   # a kernel invariant, NOT a route-level verification
        },
        "lawful_traversal_candidates": typed_null,
        "excluded": typed_null,
        "de_considered": typed_null,
        "suspended": typed_null,
        "live_under_conditions": typed_null,
        "renarrow_triggers": ["any input hash below changes", "operative tic advances",
                              "gate-resolutions or route-metadata edited",
                              "admitted covenant located (covenant_ref filled)",
                              "any source_status state changes"],
        "source_tense": "compiled-at-generation",
        "input_hashes": {
            str(p.relative_to(root)): sha(p)
            for p in (backlog_p, board_p, rm_p, gr_p, xw_p, spec_p)
        },
        "operative_tic": ((board or {}).get("conformation_envelope") or {}).get("operative_tic"),
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
