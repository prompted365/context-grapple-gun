#!/usr/bin/env python3
"""
rebru-cadence-emit — ReBru v0 cadence-block auto-emitter.

Implements T3 Bite 3 from the T4a ReBru schema v0 spec (Cadence Auto-Emit).
Constructs a cadence-block YAML from current substrate state and writes
it to audit-logs/rebru/v0-blocks/cadence-block-tic<N>.yaml.

Mirrors the hand-authored n=1 (tic 256), n=2 (tic 257), and n=3 (tic 259)
blocks. The 10 binders constructed follow the stable pattern observed
across the n=3 stability proof (zero drift across all axes).

Read-only on substrate state; writes only to the rebru v0-blocks directory.
No hot-path, signal manifold, or Harmony ingestion.

Authorized at /review tic 257 ITEM 1 PROMOTE-SCHEMA-V0+EXTEND-TO-N=3
(Bite 3 enumerated in T4a spec §13). Authored at tic 260 T3.

Invocation surface:
    Standalone: rebru-cadence-emit.py [--zone <path>] [--dry-run]
    Hook integration: called by cadence-plan-submit.py at downbeat boundary

Composes with rebru-resolve.py (sibling resolver, CGG d2935c2) and
rebru-blockdiff.py (sibling diff CLI, CGG 7d73261) — together the
three scripts cover Bites 1+4, 2, and 3 of the T4a spec.

Idempotency: re-running for the same tic OVERWRITES the existing block
(latest-emit-wins). Use --dry-run to preview without writing.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


def resolve_zone() -> Path:
    """Resolve canonical zone root via env or fallback."""
    env_zone = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_zone and Path(env_zone).exists():
        return Path(env_zone)
    # Fallback: walk up from script location to find .ticzone
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".ticzone").exists():
            return parent
    return Path("/Users/breydentaylor/canonical")


def current_tic(zone: Path) -> int:
    """Read latest tic count from audit-logs/conformations/."""
    conf_dir = zone / "audit-logs" / "conformations"
    if not conf_dir.exists():
        return -1
    tics = []
    for f in conf_dir.glob("tic-*.json"):
        try:
            n = int(f.stem.split("-")[1])
            tics.append(n)
        except (ValueError, IndexError):
            continue
    return max(tics) if tics else -1


def git_head(repo: Path) -> str:
    """Get short HEAD sha; returns 'unknown' on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "unknown"


def latest_plan(plans_dir: Path) -> str:
    """Find most-recent ~/.claude/plans/*.md by mtime."""
    if not plans_dir.exists():
        return ""
    candidates = sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(candidates[0]) if candidates else ""


def declared_posture_from_plan(plan_path: str) -> str:
    """Extract POSTURE: line from plan file if present."""
    if not plan_path or not Path(plan_path).exists():
        return "ENG/DIRECT"  # safe default
    try:
        text = Path(plan_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "ENG/DIRECT"
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("POSTURE:"):
            return line.split(":", 1)[1].strip()
    return "ENG/DIRECT"


def build_block(zone: Path, tic: int) -> dict:
    """Construct a cadence-block dict from current substrate state.

    The 10 binders mirror the stable pattern from n=1/n=2/n=3 hand-authored
    blocks (zero drift confirmed by rebru-blockdiff over those three).
    """
    audit_logs = zone / "audit-logs"
    plans_dir = Path.home() / ".claude" / "plans"
    plan_path = latest_plan(plans_dir)
    posture = declared_posture_from_plan(plan_path)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    emit_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    head = git_head(zone)

    binders = [
        {
            "binder": "@Tic.0",
            "kind": "tic",
            "role": "current_operational_tic_counter",
            "lane": "hot_path",
            "provenance_id": f"audit-logs/tics/{today}.jsonl",
            "content_hash": f"sha256:tic-event-stream-tail-tic-{tic}-cadence-emission",
            "emission_tic": tic,
            "authority_class": "runtime_observed",
            "canonical_status": "probe_not_doctrine",
            "hot_path_eligible": True,
            "ttl_tics": None,
            "hydrate": {
                "method": "jsonl_tail",
                "source": f"audit-logs/tics/{today}.jsonl",
                "query": f"domain_counter_after:{tic}",
                "line_window": 5,
                "max_bytes": 4096,
            },
            "no_mutation_guarantee": True,
            "notes": f"Cadence advanced counter to {tic}. Block auto-emitted by rebru-cadence-emit (T3 Bite 3).",
            "composes_with": [
                "Three-Layer Terrain Architecture",
                "TTL Tic-Indexed Not Tic-Uniform",
            ],
        },
        {
            "binder": "@Posture.0",
            "kind": "posture",
            "role": "declared_operational_posture_session_scope",
            "lane": "hot_path",
            "provenance_id": f"session-start-banner-tic{tic + 1}-entry",
            "content_hash": f"sha256:posture-{posture.lower().replace('/', '-')}-tic-{tic}",
            "emission_tic": tic,
            "authority_class": "operator_observed",
            "canonical_status": "probe_not_doctrine",
            "hot_path_eligible": True,
            "ttl_tics": 1,
            "hydrate": {
                "method": "rg_window",
                "source": plan_path or "~/.claude/plans/latest.md",
                "query": "POSTURE:",
                "line_window": 5,
                "max_bytes": 1024,
            },
            "no_mutation_guarantee": True,
            "notes": f"{posture} declared at session entry. Auto-extracted from {plan_path or 'plan file (path unresolved)'}.",
            "composes_with": [
                "Declared operational state must persist to a governed audit surface",
            ],
        },
        {
            "binder": "@Mode.0",
            "kind": "mode",
            "role": "declared_operational_mode_session_scope",
            "lane": "hot_path",
            "provenance_id": "inferred-from-cadence-context",
            "content_hash": f"sha256:mode-full-inferred-tic-{tic}",
            "emission_tic": tic,
            "authority_class": "operator_observed",
            "canonical_status": "probe_not_doctrine",
            "hot_path_eligible": True,
            "ttl_tics": 1,
            "hydrate": {
                "method": "rg_window",
                "source": plan_path or "~/.claude/plans/latest.md",
                "query": "Mode:|mode:",
                "line_window": 3,
                "max_bytes": 512,
            },
            "no_mutation_guarantee": True,
            "notes": "FULL inferred (default for substantive cadence handoffs).",
        },
        {
            "binder": "@Plan.0",
            "kind": "plan",
            "role": "active_session_handoff_plan",
            "lane": "hot_path",
            "provenance_id": plan_path or "~/.claude/plans/latest.md",
            "content_hash": f"sha256:plan-file-tic-{tic}-emit-time-mtime",
            "emission_tic": tic,
            "authority_class": "runtime_observed",
            "canonical_status": "probe_not_doctrine",
            "hot_path_eligible": True,
            "ttl_tics": None,
            "hydrate": {
                "method": "read_full",
                "source": plan_path or "~/.claude/plans/latest.md",
                "query": None,
                "line_window": None,
                "max_bytes": 65536,
            },
            "no_mutation_guarantee": True,
            "notes": "Most-recent plan file by mtime; consumed as substantive handoff source.",
        },
        {
            "binder": "@Mandate.0",
            "kind": "mandate",
            "role": "current_mogul_mandate",
            "lane": "hot_path",
            "provenance_id": "audit-logs/mogul/mandates/current.json",
            "content_hash": f"sha256:mandate-current-tic-{tic}",
            "emission_tic": tic,
            "authority_class": "runtime_observed",
            "canonical_status": "probe_not_doctrine",
            "hot_path_eligible": True,
            "ttl_tics": None,
            "hydrate": {
                "method": "read_full",
                "source": "audit-logs/mogul/mandates/current.json",
                "query": None,
                "line_window": None,
                "max_bytes": 8192,
            },
            "no_mutation_guarantee": True,
            "notes": "Current Mogul mandate (single-record file); status field carries lifecycle.",
        },
        {
            "binder": "@Queue.0",
            "kind": "queue",
            "role": "cogpr_queue_append_only_log",
            "lane": "hot_path",
            "provenance_id": "audit-logs/cprs/queue.jsonl",
            "content_hash": f"sha256:queue-jsonl-tic-{tic}-tail",
            "emission_tic": tic,
            "authority_class": "runtime_observed",
            "canonical_status": "probe_not_doctrine",
            "hot_path_eligible": True,
            "ttl_tics": None,
            "hydrate": {
                "method": "jsonl_tail",
                "source": "audit-logs/cprs/queue.jsonl",
                "query": None,
                "line_window": 30,
                "max_bytes": 32768,
            },
            "no_mutation_guarantee": True,
            "notes": "Append-only CogPR queue; latest-entry-per-id-wins read semantics.",
        },
        {
            "binder": "@ReviewDocket.0",
            "kind": "review_docket",
            "role": "current_or_latest_bench_packet",
            "lane": "receipt_landmark",
            "provenance_id": "audit-logs/mogul/bench-packets/latest.json",
            "content_hash": f"sha256:bench-packet-latest-tic-{tic}",
            "emission_tic": tic,
            "authority_class": "bench_evidence",
            "canonical_status": "probe_not_doctrine",
            "hot_path_eligible": False,
            "ttl_tics": 2,
            "hydrate": {
                "method": "read_full",
                "source": "audit-logs/mogul/bench-packets/latest.json",
                "query": None,
                "line_window": None,
                "max_bytes": 131072,
            },
            "no_mutation_guarantee": True,
            "notes": "Bench packet — staged or just-consumed; receipt-landmark per ReBru investigation §4.",
            "composes_with": ["Authoritative-set readers must read the manifest"],
        },
        {
            "binder": "@Receipt.0",
            "kind": "receipt",
            "role": "latest_settled_mutation_proof",
            "lane": "receipt_landmark",
            "provenance_id": f"git:{head}",
            "content_hash": f"sha256:git-head-{head}",
            "emission_tic": tic,
            "authority_class": "doctrine_inscribed",
            "canonical_status": "probe_not_doctrine",
            "hot_path_eligible": False,
            "ttl_tics": None,
            "hydrate": {
                "method": "git_show",
                "source": str(zone),
                "query": head,
                "line_window": None,
                "max_bytes": 16384,
            },
            "no_mutation_guarantee": True,
            "notes": f"Latest canonical commit at emit time: {head}.",
        },
        {
            "binder": "@Disposition.0",
            "kind": "disposition",
            "role": "current_harmony_disposition",
            "lane": "hot_path",
            "provenance_id": "audit-logs/harmony/disposition-current.json",
            "content_hash": f"sha256:disposition-current-tic-{tic}",
            "emission_tic": tic,
            "authority_class": "runtime_observed",
            "canonical_status": "probe_not_doctrine",
            "hot_path_eligible": True,
            "ttl_tics": None,
            "hydrate": {
                "method": "read_full",
                "source": "audit-logs/harmony/disposition-current.json",
                "query": None,
                "line_window": None,
                "max_bytes": 8192,
            },
            "no_mutation_guarantee": True,
            "notes": "Harmony disposition snapshot; per Conductor-Score-Runtime Parity decode at radar.",
            "composes_with": ["Conductor-Score-Runtime Parity"],
        },
        {
            "binder": "@OpenRay.0",
            "kind": "open_ray",
            "role": "current_highest_pressure_unresolved_node",
            "lane": "hot_path",
            "provenance_id": "composite-synthetic-from-plan-state",
            "content_hash": f"sha256:open-ray-tic-{tic}-composite",
            "emission_tic": tic,
            "authority_class": "operator_observed",
            "canonical_status": "probe_not_doctrine",
            "hot_path_eligible": True,
            "ttl_tics": 1,
            "hydrate": {
                "method": "rg_window",
                "source": plan_path or "~/.claude/plans/latest.md",
                "query": "Active Goals|Next Actions|Production Next Actions",
                "line_window": 20,
                "max_bytes": 8192,
            },
            "no_mutation_guarantee": True,
            "notes": "Composite synthetic — points at the active-goal / next-action section of the current plan as the highest-pressure unresolved area.",
        },
    ]

    return {
        "type": "rebru.cadence_block",
        "version": "v0_probe",
        "canonical_status": "probe_not_doctrine",
        "session_id": f"tic{tic}-auto-emit-{today}",
        "tic": tic,
        "emission_at": emit_iso,
        "source_handoff_id": f"auto-emit-tic-{tic}-rebru-cadence-emit",
        "binders": binders,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ReBru v0 cadence-block auto-emitter (T3 Bite 3)",
    )
    parser.add_argument("--zone", help="Canonical zone root (default: env CLAUDE_PROJECT_DIR or fallback)")
    parser.add_argument("--tic", type=int, help="Override tic counter (default: read from conformations)")
    parser.add_argument("--dry-run", action="store_true", help="Print block to stdout instead of writing")
    parser.add_argument("--quiet", action="store_true", help="Suppress stderr success message")
    args = parser.parse_args()

    zone = Path(args.zone) if args.zone else resolve_zone()
    if not zone.exists():
        print(f"ERROR: zone not found: {zone}", file=sys.stderr)
        return 2

    tic = args.tic if args.tic is not None else current_tic(zone)
    if tic < 0:
        print(f"ERROR: cannot resolve current tic from {zone}/audit-logs/conformations/", file=sys.stderr)
        return 2

    block = build_block(zone, tic)
    out_yaml = yaml.dump(block, sort_keys=False, default_flow_style=False, width=120)

    if args.dry_run:
        print(out_yaml)
        return 0

    out_dir = zone / "audit-logs" / "rebru" / "v0-blocks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"cadence-block-tic{tic}.yaml"
    out_path.write_text(out_yaml, encoding="utf-8")

    if not args.quiet:
        print(f"Wrote cadence-block: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
