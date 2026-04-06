#!/usr/bin/env python3
"""
arena-report-generator.py — Post-arena report generation pipeline.

Ingests arena pressure reports and show directories via the archivist envelope
pattern, generates a unified HTML governance report as a knowledge.summary
artifact.

This is the post-processing protocol for /stage and arena swarm outcomes.
After any arena (or set of arenas) completes, this script:

1. Reads pressure reports from audit-logs/arenas/pressure-reports/
2. Reads show directories for synthesis documents
3. Collates CogPRs, signals, conformation data
4. Generates an archivist-envelope-compliant HTML report
5. Writes report to the show directory

Usage:
    # Generate report for a specific arena
    python3 arena-report-generator.py --zone-root /path/to/project --arena-id <id>

    # Generate multi-arena synthesis report (all arenas sharing a source_tic)
    python3 arena-report-generator.py --zone-root /path/to/project --tic <N>

    # Generate report for specific arena IDs
    python3 arena-report-generator.py --zone-root /path/to/project --arenas id1,id2,id3

    # Dry run (print envelope, don't write)
    python3 arena-report-generator.py --zone-root /path/to/project --tic <N> --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def resolve_paths(zone_root: Path) -> dict:
    """Resolve all governance paths from zone root."""
    audit = zone_root / "audit-logs"
    cgg = None

    # Find CGG stage directory
    for candidate in [
        zone_root / "canonical_developer" / "context-grapple-gun" / "stage",
        zone_root / "stage",
    ]:
        if candidate.exists():
            cgg = candidate
            break

    return {
        "zone_root": zone_root,
        "audit_logs": audit,
        "pressure_reports": audit / "arenas" / "pressure-reports",
        "signals": audit / "signals",
        "cprs": audit / "cprs",
        "conformations": audit / "conformations",
        "stage": cgg,
        "shows": cgg / "shows" if cgg else None,
    }


def load_pressure_report(path: Path) -> dict | None:
    """Load a single pressure report JSON."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"  WARN: failed to load {path}: {e}", file=sys.stderr)
        return None


def find_arenas_by_tic(paths: dict, tic: int) -> list[dict]:
    """Find all pressure reports for a given source tic."""
    reports = []
    pr_dir = paths["pressure_reports"]
    if not pr_dir.exists():
        return reports
    for f in sorted(pr_dir.glob("*.json")):
        data = load_pressure_report(f)
        if data and data.get("source_tic") == tic:
            reports.append(data)
    return reports


def find_arenas_by_ids(paths: dict, arena_ids: list[str]) -> list[dict]:
    """Find pressure reports matching specific arena IDs."""
    reports = []
    pr_dir = paths["pressure_reports"]
    if not pr_dir.exists():
        return reports
    for arena_id in arena_ids:
        candidates = list(pr_dir.glob(f"*{arena_id}*.json"))
        if not candidates:
            # Try exact filename match
            exact = pr_dir / f"{arena_id}.json"
            if exact.exists():
                candidates = [exact]
        for f in candidates:
            data = load_pressure_report(f)
            if data:
                reports.append(data)
    return reports


def load_synthesis(paths: dict, arena_id: str) -> str | None:
    """Load synthesis document from show directory."""
    if not paths["shows"]:
        return None

    # Try common show directory naming patterns
    for pattern in [arena_id, arena_id.replace("2026-04-05_", "")]:
        show_dir = paths["shows"] / pattern
        synth = show_dir / "synthesis.md"
        if synth.exists():
            return synth.read_text()
    return None


def load_conformation(paths: dict, tic: int) -> dict | None:
    """Load conformation snapshot for a tic."""
    conf_file = paths["conformations"] / f"tic-{tic}.json"
    if conf_file.exists():
        try:
            return json.loads(conf_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


def collate_cogprs(reports: list[dict]) -> list[dict]:
    """Extract all candidate CogPRs across reports."""
    cogprs = []
    seen_ids = set()
    for report in reports:
        for cpr in report.get("candidate_cogprs", []):
            cpr_id = cpr.get("id_suggestion", cpr.get("id", ""))
            if cpr_id not in seen_ids:
                seen_ids.add(cpr_id)
                cogprs.append({
                    "id": cpr_id,
                    "lesson": cpr.get("lesson", ""),
                    "confidence": cpr.get("confidence_tier", "tentative"),
                    "scope": cpr.get("recommended_scope", cpr.get("target", "")),
                    "arena": report.get("arena_id", "unknown"),
                })
    return cogprs


def collate_signals(reports: list[dict]) -> list[dict]:
    """Extract all candidate signals across reports."""
    signals = []
    for report in reports:
        for sig in report.get("candidate_signals", []):
            signals.append({
                "kind": sig.get("kind", sig.get("type", "WATCH")),
                "id": sig.get("id", sig.get("summary", "")[:40]),
                "summary": sig.get("summary", sig.get("reason", sig.get("description", ""))),
                "arena": report.get("arena_id", "unknown"),
            })
    return signals


def collate_convergent_discoveries(reports: list[dict]) -> list[dict]:
    """Extract convergent discoveries across reports."""
    discoveries = []
    for report in reports:
        for disc in report.get("convergent_discoveries", []):
            discoveries.append({
                "finding": disc.get("finding", disc.get("claim", "")),
                "confidence": disc.get("confidence", "convergent"),
                "arena": report.get("arena_id", "unknown"),
            })
    return discoveries


def build_archivist_envelope(reports: list[dict], tic: int) -> dict:
    """Build the archivist envelope metadata for the report."""
    arena_ids = [r.get("arena_id", "unknown") for r in reports]
    total_advocates = sum(
        r.get("geometry", {}).get("advocates", 3) for r in reports
    )
    total_docs = sum(
        r.get("geometry", {}).get("documents", 11) for r in reports
    )
    cogprs = collate_cogprs(reports)
    signals = collate_signals(reports)

    return {
        "@context": "canonical://archivist-envelope/v1",
        "@type": "FederationArenaReport",
        "envelope": {
            "capability": "knowledge.extract",
            "envelope_type": "knowledge.summary",
            "callback_mode": "artifact",
        },
        "provenance": {
            "report_type": "multi-arena-synthesis" if len(reports) > 1 else "single-arena",
            "source_tic": tic,
            "arenas": arena_ids,
            "total_advocates": total_advocates,
            "total_documents": total_docs,
            "cogprs_minted": len(cogprs),
            "signals_emitted": len(signals),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def generate_report_data(
    paths: dict,
    reports: list[dict],
    tic: int,
) -> dict:
    """Assemble all data needed for report generation."""
    cogprs = collate_cogprs(reports)
    signals = collate_signals(reports)
    discoveries = collate_convergent_discoveries(reports)
    conformation = load_conformation(paths, tic)

    # Load synthesis for each arena
    syntheses = {}
    for report in reports:
        arena_id = report.get("arena_id", "")
        synth = load_synthesis(paths, arena_id)
        if synth:
            syntheses[arena_id] = synth[:500]  # First 500 chars as summary

    # Extract conformation data if available
    conformation_summary = None
    if any("conformation_summary" in r for r in reports):
        for r in reports:
            if "conformation_summary" in r:
                conformation_summary = r["conformation_summary"]
                break

    return {
        "envelope": build_archivist_envelope(reports, tic),
        "reports": reports,
        "cogprs": cogprs,
        "signals": signals,
        "discoveries": discoveries,
        "syntheses": syntheses,
        "conformation": conformation,
        "conformation_summary": conformation_summary,
        "tic": tic,
    }


def determine_output_path(paths: dict, reports: list[dict], tic: int) -> Path:
    """Determine where to write the report."""
    if len(reports) == 1:
        arena_id = reports[0].get("arena_id", "arena")
        # Strip date prefix for directory name
        dir_name = arena_id.replace(f"{arena_id[:11]}", "").lstrip("_") or arena_id
        show_dir = paths["shows"] / dir_name if paths["shows"] else paths["zone_root"]
    else:
        show_dir = paths["shows"] / f"tic-{tic}-synthesis" if paths["shows"] else paths["zone_root"]

    show_dir.mkdir(parents=True, exist_ok=True)
    return show_dir / "federation-arena-report.html"


def main():
    parser = argparse.ArgumentParser(
        description="Generate archivist-envelope HTML reports from arena outcomes"
    )
    parser.add_argument("--zone-root", required=True, help="Project zone root")
    parser.add_argument("--arena-id", help="Single arena ID to report on")
    parser.add_argument("--arenas", help="Comma-separated arena IDs")
    parser.add_argument("--tic", type=int, help="Source tic (finds all arenas)")
    parser.add_argument("--dry-run", action="store_true", help="Print data, don't write")
    parser.add_argument("--output", help="Override output path")

    args = parser.parse_args()
    zone_root = Path(args.zone_root).resolve()
    paths = resolve_paths(zone_root)

    # Find reports
    reports = []
    tic = args.tic or 0

    if args.arena_id:
        reports = find_arenas_by_ids(paths, [args.arena_id])
    elif args.arenas:
        arena_ids = [a.strip() for a in args.arenas.split(",")]
        reports = find_arenas_by_ids(paths, arena_ids)
    elif args.tic:
        reports = find_arenas_by_tic(paths, args.tic)

    if not reports:
        print("ERROR: No pressure reports found for the given criteria.", file=sys.stderr)
        sys.exit(1)

    # Use first report's tic if not specified
    if not tic:
        tic = reports[0].get("source_tic", 0)

    print(f"Found {len(reports)} arena report(s) for tic {tic}")
    for r in reports:
        print(f"  - {r.get('arena_id', 'unknown')} ({r.get('template', 'unknown')})")

    # Assemble data
    data = generate_report_data(paths, reports, tic)

    if args.dry_run:
        print("\n--- Archivist Envelope ---")
        print(json.dumps(data["envelope"], indent=2))
        print(f"\nCogPRs: {len(data['cogprs'])}")
        for c in data["cogprs"]:
            print(f"  {c['id']}: [{c['confidence']}] {c['lesson'][:80]}")
        print(f"\nSignals: {len(data['signals'])}")
        for s in data["signals"]:
            print(f"  [{s['kind']}] {s['summary'][:80]}")
        print(f"\nConvergent discoveries: {len(data['discoveries'])}")
        for d in data["discoveries"]:
            print(f"  [{d['confidence']}] {d['finding'][:80]}")
        return

    # Determine output path
    if args.output:
        output = Path(args.output)
    else:
        output = determine_output_path(paths, reports, tic)

    # Write the data manifest (the agent uses this to generate the HTML)
    manifest_path = output.parent / "report-manifest.json"
    manifest_path.write_text(json.dumps(data, indent=2, default=str))
    print(f"\nReport manifest written: {manifest_path}")
    print(f"Report HTML target: {output}")
    print(f"\nTo generate the HTML report, dispatch the report-generator agent:")
    print(f"  Agent(subagent_type='videographer', prompt='Generate HTML arena report from {manifest_path}')")
    print(f"\nOr use /stage --report to invoke the full pipeline.")


if __name__ == "__main__":
    main()
