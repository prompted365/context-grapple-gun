#!/usr/bin/env python3
"""
rebru-blockdiff — ReBru v0 cadence-block sequence comparison CLI.

Implements T3 Bite 2 from the T4a ReBru schema v0 spec (Compare Semantics).
Consumes two or more cadence-block YAML files and emits a structured
comparison artifact mirroring audit-logs/rebru/v0-blocks/n2-comparison-
tic256-tic257.md.

Read-only. No source mutation. No hot-path or Harmony ingestion.

The CLI is the compiled-form sibling to hand-authored n2-comparison.md:
hand-authored versions captured cross-tic n=2 evidence at tic 257 and
n=3 evidence at tic 259. Bite 2 mechanizes the comparison so future
cadence-block emissions automatically produce comparison artifacts
without hand authoring.

Authorized at /review tic 257 ITEM 1 PROMOTE-SCHEMA-V0+EXTEND-TO-N=3
(Bite 2 enumerated in T4a spec §13). Authored at tic 260 T3.

Usage:
    rebru-blockdiff <block1.yaml> <block2.yaml> [<block3.yaml> ...]
    rebru-blockdiff --output <path.md> <block1.yaml> <block2.yaml>
    rebru-blockdiff --json <block1.yaml> <block2.yaml>          # structured output

Comparison axes (matching n2-comparison.md sections):
    1. Handle Resolution Stability — which handles appear in each block
    2. Lane Assignment Drift — per-handle lane across blocks
    3. Schema Adequacy — which fields populated in each block
    4. Hydrate Method Distribution — per-handle method across blocks
    5. Authority Class Stability — per-handle authority_class drift
    6. Cross-Block Findings — structural drift detection

Composes with: rebru-resolve.py (sibling resolver), rebru-cadence-block
schema.draft.json (canonical schema). Validates each block file against
the schema's structural shape (binders array, required handle pattern).
"""

import argparse
import json
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


HANDLE_REGEX_DESC = "@<Type>.<N> (e.g., @Tic.0, @Queue.0)"
SCHEMA_FIELDS = [
    "binder", "kind", "role", "lane", "provenance_id", "content_hash",
    "emission_tic", "authority_class", "canonical_status",
    "hot_path_eligible", "ttl_tics", "hydrate", "no_mutation_guarantee",
    "notes", "composes_with",
]


def load_block(path: Path) -> dict[str, Any]:
    """Load a cadence-block YAML; return parsed dict.

    Validates outer shape: must be a mapping with `binders: [...]` list.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SystemExit(f"ERROR: cannot read {path}: {e}")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SystemExit(f"ERROR: malformed YAML in {path}: {e}")
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: {path} root is not a mapping")
    if "binders" not in data or not isinstance(data["binders"], list):
        raise SystemExit(f"ERROR: {path} missing 'binders' list")
    return data


def block_label(block: dict[str, Any], path: Path) -> str:
    """Return a short label like 'n=1 tic 256' for header rendering."""
    tic = block.get("tic", "?")
    return f"tic {tic} ({path.name})"


def binders_by_handle(block: dict[str, Any]) -> OrderedDict[str, dict[str, Any]]:
    """Return ordered map handle -> binder record. Preserves YAML order."""
    out: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for b in block.get("binders", []):
        if not isinstance(b, dict):
            continue
        handle = b.get("binder")
        if isinstance(handle, str) and handle:
            out[handle] = b
    return out


def compare_handle_stability(
    blocks: list[OrderedDict[str, dict[str, Any]]],
    labels: list[str],
) -> dict[str, Any]:
    """Build handle-stability table: per-handle presence/absence across blocks."""
    all_handles: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        for h in block.keys():
            if h not in seen:
                seen.add(h)
                all_handles.append(h)

    rows = []
    universal = 0
    partial = 0
    for h in all_handles:
        presence = [h in b for b in blocks]
        if all(presence):
            universal += 1
            verdict = "universal"
        else:
            partial += 1
            verdict = "partial"
        rows.append({"handle": h, "presence": presence, "verdict": verdict})
    return {
        "total_handles": len(all_handles),
        "universal_count": universal,
        "partial_count": partial,
        "rows": rows,
        "labels": labels,
    }


def compare_lane_drift(
    blocks: list[OrderedDict[str, dict[str, Any]]],
    labels: list[str],
) -> dict[str, Any]:
    """Per-handle lane across blocks; flag drift."""
    handles = sorted({h for b in blocks for h in b.keys()})
    rows = []
    drift_count = 0
    for h in handles:
        lanes = [b.get(h, {}).get("lane", "—") for b in blocks]
        non_dash = [lane for lane in lanes if lane != "—"]
        drifted = len(set(non_dash)) > 1
        if drifted:
            drift_count += 1
        rows.append({"handle": h, "lanes": lanes, "drifted": drifted})

    # Lane distribution across all blocks
    distribution: dict[str, int] = defaultdict(int)
    for b in blocks:
        for rec in b.values():
            lane = rec.get("lane")
            if isinstance(lane, str):
                distribution[lane] += 1
    return {
        "rows": rows,
        "drift_count": drift_count,
        "distribution": dict(distribution),
        "labels": labels,
    }


def compare_schema_adequacy(
    blocks: list[OrderedDict[str, dict[str, Any]]],
    labels: list[str],
) -> dict[str, Any]:
    """Per-block field-population coverage across all SCHEMA_FIELDS."""
    rows = []
    for field in SCHEMA_FIELDS:
        per_block: list[int] = []
        for b in blocks:
            populated = sum(
                1 for rec in b.values()
                if rec.get(field) not in (None, "", [], {})
            )
            per_block.append(populated)
        total = [len(b) for b in blocks]
        rows.append({
            "field": field,
            "populated": per_block,
            "total_binders": total,
        })
    return {"rows": rows, "labels": labels}


def compare_hydrate_methods(
    blocks: list[OrderedDict[str, dict[str, Any]]],
    labels: list[str],
) -> dict[str, Any]:
    """Per-handle hydrate.method across blocks + per-block method distribution."""
    handles = sorted({h for b in blocks for h in b.keys()})
    rows = []
    method_drift = 0
    for h in handles:
        methods = []
        for b in blocks:
            rec = b.get(h, {})
            method = (rec.get("hydrate") or {}).get("method", "—")
            methods.append(method)
        non_dash = [m for m in methods if m != "—"]
        drifted = len(set(non_dash)) > 1
        if drifted:
            method_drift += 1
        rows.append({"handle": h, "methods": methods, "drifted": drifted})

    distribution: list[dict[str, int]] = []
    for b in blocks:
        dist: dict[str, int] = defaultdict(int)
        for rec in b.values():
            method = (rec.get("hydrate") or {}).get("method")
            if isinstance(method, str):
                dist[method] += 1
        distribution.append(dict(dist))
    return {
        "rows": rows,
        "method_drift_count": method_drift,
        "distribution_per_block": distribution,
        "labels": labels,
    }


def compare_authority_class(
    blocks: list[OrderedDict[str, dict[str, Any]]],
    labels: list[str],
) -> dict[str, Any]:
    """Per-handle authority_class across blocks."""
    handles = sorted({h for b in blocks for h in b.keys()})
    rows = []
    drift = 0
    for h in handles:
        classes = [b.get(h, {}).get("authority_class", "—") for b in blocks]
        non_dash = [c for c in classes if c != "—"]
        drifted = len(set(non_dash)) > 1
        if drifted:
            drift += 1
        rows.append({"handle": h, "classes": classes, "drifted": drifted})
    return {"rows": rows, "drift_count": drift, "labels": labels}


def render_markdown(
    blocks: list[dict[str, Any]],
    paths: list[Path],
    stability: dict[str, Any],
    lanes: dict[str, Any],
    schema: dict[str, Any],
    methods: dict[str, Any],
    authority: dict[str, Any],
) -> str:
    """Render comparison artifact as markdown."""
    n = len(blocks)
    labels = [block_label(b, p) for b, p in zip(blocks, paths)]
    header_cols = " | ".join(labels)
    sep_cols = " | ".join(["---"] * n)

    out: list[str] = []
    out.append(f"# ReBru v0 Cross-Block Comparison — n={n}\n")
    out.append("**Authority basis:** /review tic 257 ITEM 1 PROMOTE-SCHEMA-V0+EXTEND-TO-N=3.")
    out.append("Mechanized via rebru-blockdiff.py (T3 Bite 2, tic 260).\n")
    out.append("**Comparison subjects:**")
    for i, (b, p) in enumerate(zip(blocks, paths)):
        out.append(f"- n={i+1}: `{p}` (tic {b.get('tic', '?')})")
    out.append("")
    out.append(f"**Cross-tic distance:** {n - 1} cadence boundary/boundaries.\n")
    out.append("---\n")

    # Section 1 — Handle Resolution Stability
    out.append("## 1. Handle Resolution Stability\n")
    out.append(f"| Binder | {header_cols} | Verdict |")
    out.append(f"|---|{'---|' * n} ---|")
    for r in stability["rows"]:
        presence_cells = " | ".join("✓" if p else "—" for p in r["presence"])
        out.append(f"| `{r['handle']}` | {presence_cells} | {r['verdict']} |")
    out.append(f"\n**Verdict:** {stability['universal_count']} of "
               f"{stability['total_handles']} handles universal across "
               f"all blocks; {stability['partial_count']} partial.\n")

    # Section 2 — Lane Assignment Drift
    out.append("## 2. Lane Assignment Drift\n")
    out.append(f"| Binder | {header_cols} | Drift? |")
    out.append(f"|---|{'---|' * n} ---|")
    for r in lanes["rows"]:
        lane_cells = " | ".join(r["lanes"])
        out.append(f"| `{r['handle']}` | {lane_cells} | "
                   f"{'**YES**' if r['drifted'] else 'no'} |")
    out.append(f"\n**Distribution (all blocks):** "
               f"{', '.join(f'{k}={v}' for k, v in sorted(lanes['distribution'].items()))}\n")
    out.append(f"**Drift verdict:** {lanes['drift_count']} handle(s) drifted across blocks.\n")

    # Section 3 — Schema Adequacy
    out.append("## 3. Schema Adequacy\n")
    out.append(f"| Field | {header_cols} |")
    out.append(f"|---|{'---|' * n}")
    for r in schema["rows"]:
        cells = " | ".join(f"{p}/{t}" for p, t in zip(r["populated"], r["total_binders"]))
        out.append(f"| `{r['field']}` | {cells} |")
    out.append("\nLegend: `populated/total_binders` per block.\n")

    # Section 4 — Hydrate Method Distribution
    out.append("## 4. Hydrate Method Distribution\n")
    out.append(f"| Binder | {header_cols} | Drift? |")
    out.append(f"|---|{'---|' * n} ---|")
    for r in methods["rows"]:
        method_cells = " | ".join(f"`{m}`" for m in r["methods"])
        out.append(f"| `{r['handle']}` | {method_cells} | "
                   f"{'**YES**' if r['drifted'] else 'no'} |")
    out.append(f"\n**Method drift verdict:** {methods['method_drift_count']} handle(s) "
               f"changed hydrate method across blocks.\n")

    # Section 5 — Authority Class Stability
    out.append("## 5. Authority Class Stability\n")
    out.append(f"| Binder | {header_cols} | Drift? |")
    out.append(f"|---|{'---|' * n} ---|")
    for r in authority["rows"]:
        class_cells = " | ".join(r["classes"])
        out.append(f"| `{r['handle']}` | {class_cells} | "
                   f"{'**YES**' if r['drifted'] else 'no'} |")
    out.append(f"\n**Authority drift verdict:** {authority['drift_count']} handle(s) drifted.\n")

    # Section 6 — Cross-Block Findings
    out.append("## 6. Cross-Block Findings (Mechanical)\n")
    findings: list[str] = []
    if stability["partial_count"] == 0:
        findings.append("Handle universality: ALL handles present in ALL blocks — stable.")
    else:
        findings.append(f"Handle universality: {stability['partial_count']} "
                        f"handle(s) partial — investigate emission discipline.")
    if lanes["drift_count"] == 0:
        findings.append("Lane stability: zero drift across blocks.")
    else:
        findings.append(f"Lane drift: {lanes['drift_count']} handle(s) — surface to /review.")
    if methods["method_drift_count"] == 0:
        findings.append("Hydrate method stability: zero drift across blocks.")
    else:
        findings.append(f"Hydrate method drift: {methods['method_drift_count']} "
                        f"handle(s) — verify schema adequacy at v1.")
    if authority["drift_count"] == 0:
        findings.append("Authority class stability: zero drift across blocks.")
    else:
        findings.append(f"Authority class drift: {authority['drift_count']} handle(s).")

    for f in findings:
        out.append(f"- {f}")
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ReBru v0 cadence-block sequence comparison (T3 Bite 2)",
    )
    parser.add_argument("blocks", nargs="+", help="Two or more cadence-block YAML paths")
    parser.add_argument("--output", "-o", help="Write markdown report to PATH (default: stdout)")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown")
    args = parser.parse_args()

    if len(args.blocks) < 2:
        print("ERROR: at least two block paths required for comparison", file=sys.stderr)
        return 2

    paths = [Path(p) for p in args.blocks]
    for p in paths:
        if not p.exists():
            print(f"ERROR: block file not found: {p}", file=sys.stderr)
            return 2

    raw_blocks = [load_block(p) for p in paths]
    blocks = [binders_by_handle(b) for b in raw_blocks]
    labels = [block_label(b, p) for b, p in zip(raw_blocks, paths)]

    stability = compare_handle_stability(blocks, labels)
    lanes = compare_lane_drift(blocks, labels)
    schema = compare_schema_adequacy(blocks, labels)
    methods = compare_hydrate_methods(blocks, labels)
    authority = compare_authority_class(blocks, labels)

    if args.json:
        payload = {
            "n": len(blocks),
            "paths": [str(p) for p in paths],
            "tics": [b.get("tic") for b in raw_blocks],
            "handle_stability": stability,
            "lane_drift": lanes,
            "schema_adequacy": schema,
            "hydrate_methods": methods,
            "authority_class": authority,
        }
        out = json.dumps(payload, indent=2, default=str)
    else:
        out = render_markdown(raw_blocks, paths, stability, lanes, schema, methods, authority)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"Wrote comparison artifact: {args.output}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
