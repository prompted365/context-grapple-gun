#!/usr/bin/env python3
"""Seed a governance workspace fixture for Mogul suborchestrator evaluation.

Creates realistic governance state (mandates, CPR queue, signals, ticzone)
derived from actual operationTorque patterns, sanitized for eval isolation.

Usage:
    python3 seed-workspace.py --scenario queue_refresh --output-dir files/workspace-queue-refresh
    python3 seed-workspace.py --scenario enrichment --output-dir files/workspace-enrichment
    python3 seed-workspace.py --scenario dual_cycle --output-dir files/workspace-dual-cycle
    python3 seed-workspace.py --help

Exit codes:
    0 - Success
    1 - Invalid arguments
    2 - Output directory creation failed
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone


def write_json(path: str, data: dict | list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def write_jsonl(path: str, entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def make_ticzone() -> dict:
    return {
        "name": "eval-fixture",
        "tz": "America/Toronto",
        "lat": 43.65,
        "lon": -79.38,
        "include": ["**"],
        "bands": {
            "PRIMITIVE": {"db_equiv": 0, "muffling_immune": True},
            "COGNITIVE": {"db_equiv": -6},
            "SOCIAL": {"db_equiv": -12},
            "PRESTIGE": {"db_equiv": -999, "auto_muted": True},
        },
        "muffling_per_hop": 5,
        "signal_governance": {
            "warrant_eligible_kinds": ["BEACON", "TENSION"],
            "decay_rate_per_tic": 2,
            "primitive_audibility_mode": "floor",
            "zombie_guard_mode": "clamp",
        },
    }


def make_mandate(
    scenario: str, tic: int = 203, cycles: list[str] | None = None
) -> dict:
    if cycles is None:
        cycles = ["queue_refresh"]
    return {
        "mandate_id": f"eval-{scenario}-tic-{tic}",
        "status": "pending",
        "supersedes": [],
        "merged_from": [],
        "actor": {"office": "mogul", "embodiment": "cgg_runtime"},
        "trigger": {"kind": "explicit", "source_ref": "evals/seed-workspace.py"},
        "tic_context": {
            "current_tic": tic,
            "review_due_tic": tic + 1,
            "memory_mining_due_tic": tic + 1,
            "ladder_audit_due_tic": tic + 2,
            "deep_audit_due_tic": tic + 5,
        },
        "cycle_request": {
            "run_now": cycles,
            "reason": f"Eval scenario: {scenario}",
        },
        "conformation_ref": None,
        "mode": {"blocking_to_homeskillet": False, "allow_subdelegation": True},
        "runtime_truth": {"canonical_vs_installed_verified": True},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "error": None,
    }


def make_cpr(
    cpr_id: str,
    dedup_hash: str,
    status: str,
    lesson: str,
    source: str,
    birth_tic: int,
    subsystem: str = "cgg",
    enrichment: list[dict] | None = None,
) -> dict:
    entry = {
        "type": "cpr",
        "id": cpr_id,
        "dedup_hash": dedup_hash,
        "status": status,
        "lesson": lesson,
        "source": source,
        "source_date": "2026-03-06",
        "band": "COGNITIVE",
        "motivation_layer": "COGNITIVE",
        "subsystem": subsystem,
        "recommended_scopes": ["CLAUDE.md"],
        "birth_tic": birth_tic,
        "posture": "ENG/META",
        "extracted_at": "2026-03-06T08:00:00+00:00",
        "extracted_by": "eval-fixture",
    }
    if enrichment:
        entry["enrichment"] = enrichment
    return entry


def make_signal(
    sig_id: str,
    kind: str,
    band: str,
    subsystem: str,
    volume: int,
    status: str = "active",
    summary: str = "",
) -> dict:
    return {
        "type": "signal",
        "id": sig_id,
        "kind": kind,
        "band": band,
        "motivation_layer": band,
        "source": f"eval-fixture/{subsystem}",
        "source_date": "2026-03-06",
        "subsystem": subsystem,
        "volume": volume,
        "volume_rate": 5,
        "max_volume": 100,
        "hearing_targets": [
            {"actor": "homeskillet", "threshold": 40},
            {"actor": "mogul", "threshold": 50},
        ],
        "escalation": {"warrant_threshold": 80, "warrant_id": ""},
        "payload": {"signature": f"eval_{subsystem}_{kind.lower()}", "summary": summary},
        "status": status,
        "last_tick_at": "2026-03-06T12:00:00+00:00",
        "tick_count": 3,
    }


def make_tic_entry(tic_num: int) -> dict:
    return {
        "type": "tic",
        "tic": f"2026-03-06T12:{tic_num:02d}:00-05:00",
        "tic_zone": "eval-fixture",
        "cadence_position": "downbeat",
        "scope": "project",
    }


def seed_queue_refresh(output_dir: str) -> dict:
    """Scenario 1: 3 CPRs — 1 pending, 1 enrichment_eligible (weak), 1 promotable."""
    cprs = [
        make_cpr(
            "cpr_eval_pending_01",
            "eval_pending_01",
            "extracted",
            "Extracted lesson awaiting initial review — should not be advanced by queue_refresh alone",
            "eval-fixture/test.py:42",
            birth_tic=200,
        ),
        make_cpr(
            "cpr_eval_enrich_01",
            "eval_enrich_01",
            "enrichment_eligible",
            "Governance scripts that share audit-store paths must resolve from a single zone-root primitive — the cwd-relative class of bugs is eliminated by making resolution the only authority",
            "eval-fixture/zone_root.py:1",
            birth_tic=184,
            enrichment=[
                {
                    "evidence_type": "source_stable",
                    "value": "Source file exists, lesson text present",
                    "gathered_at": "2026-03-05T12:00:00+00:00",
                    "gathered_by": "cpr-enrichment-scanner",
                }
            ],
        ),
        make_cpr(
            "cpr_eval_promotable_01",
            "eval_promotable_01",
            "enrichment_eligible",
            "Tutorial simulations work best as Claude-narrated demonstrations, not student-written exercises — when infrastructure can run code live, the student's job shifts from implementing to understanding",
            "eval-fixture/academy/SKILL.md:10",
            birth_tic=171,
            enrichment=[
                {
                    "evidence_type": "source_stable",
                    "value": "Source file exists, lesson text present",
                    "gathered_at": "2026-03-05T12:00:00+00:00",
                    "gathered_by": "cpr-enrichment-scanner",
                },
                {
                    "evidence_type": "commits_since_birth",
                    "value": "8 commits touching related paths",
                    "gathered_at": "2026-03-05T12:00:00+00:00",
                    "gathered_by": "cpr-enrichment-scanner",
                },
                {
                    "evidence_type": "cross_reference",
                    "value": "Referenced in 2 other files",
                    "detail": ["docs/meta-learning-matrix.md", "CLAUDE.md"],
                    "gathered_at": "2026-03-05T12:00:00+00:00",
                    "gathered_by": "cpr-enrichment-scanner",
                },
            ],
        ),
    ]

    signals = [
        make_signal(
            "sig_eval_drift_01",
            "TENSION",
            "COGNITIVE",
            "cgg",
            volume=43,
            summary="Detected runtime drift between canonical and installed copies",
        ),
    ]

    tics = [make_tic_entry(i) for i in range(1, 4)]
    mandate = make_mandate("queue_refresh", cycles=["queue_refresh"])

    write_jsonl(f"{output_dir}/audit-logs/cprs/queue.jsonl", cprs)
    write_jsonl(f"{output_dir}/audit-logs/signals/2026-03-06.jsonl", signals)
    write_jsonl(f"{output_dir}/audit-logs/tics/2026-03-06.jsonl", tics)
    write_json(f"{output_dir}/audit-logs/mogul/mandates/current.json", mandate)
    write_json(f"{output_dir}/.ticzone", make_ticzone())

    return {
        "scenario": "queue_refresh",
        "output_dir": output_dir,
        "cprs_seeded": len(cprs),
        "signals_seeded": len(signals),
        "tics_seeded": len(tics),
    }


def seed_enrichment(output_dir: str) -> dict:
    """Scenario 2: 2 enrichment_eligible CPRs with thin evidence."""
    cprs = [
        make_cpr(
            "cpr_eval_thin_01",
            "eval_thin_01",
            "enrichment_eligible",
            "PostToolUse hook on ExitPlanMode provides a deterministic, synchronous CPR extraction point that survives session boundaries",
            "eval-fixture/hooks/cpr-extract.sh:1",
            birth_tic=167,
            enrichment=[
                {
                    "evidence_type": "source_stable",
                    "value": "Source exists",
                    "gathered_at": "2026-03-04T12:00:00+00:00",
                    "gathered_by": "cpr-enrichment-scanner",
                }
            ],
        ),
        make_cpr(
            "cpr_eval_thin_02",
            "eval_thin_02",
            "enrichment_eligible",
            "A federated signal must carry birth provenance — hearing a signal locally does not make it locally born",
            "eval-fixture/signals.md:42",
            birth_tic=195,
            enrichment=[
                {
                    "evidence_type": "source_stable",
                    "value": "Source exists",
                    "gathered_at": "2026-03-05T12:00:00+00:00",
                    "gathered_by": "cpr-enrichment-scanner",
                }
            ],
        ),
    ]

    signals = [
        make_signal(
            "sig_eval_drift_02",
            "TENSION",
            "COGNITIVE",
            "cgg",
            volume=45,
            summary="Enrichment pipeline has thin evidence for eligible CPRs",
        ),
    ]

    tics = [make_tic_entry(i) for i in range(1, 4)]
    mandate = make_mandate("enrichment", cycles=["queue_refresh", "enrichment_scan"])

    write_jsonl(f"{output_dir}/audit-logs/cprs/queue.jsonl", cprs)
    write_jsonl(f"{output_dir}/audit-logs/signals/2026-03-06.jsonl", signals)
    write_jsonl(f"{output_dir}/audit-logs/tics/2026-03-06.jsonl", tics)
    write_json(f"{output_dir}/audit-logs/mogul/mandates/current.json", mandate)
    write_json(f"{output_dir}/.ticzone", make_ticzone())

    return {
        "scenario": "enrichment",
        "output_dir": output_dir,
        "cprs_seeded": len(cprs),
        "signals_seeded": len(signals),
        "tics_seeded": len(tics),
    }


def seed_dual_cycle(output_dir: str) -> dict:
    """Scenario 3: Dual-cycle mandate (signal_scan + queue_refresh) with mixed state."""
    cprs = [
        make_cpr(
            "cpr_eval_dual_01",
            "eval_dual_01",
            "enrichment_eligible",
            "Constraint stress testing inverts the test subject — adversarial scenarios test the governance infrastructure, not the agent",
            "eval-fixture/payne-harness.json:1",
            birth_tic=172,
            subsystem="harpoon",
            enrichment=[
                {
                    "evidence_type": "source_stable",
                    "value": "Source exists, harness validated (40/40 tests)",
                    "gathered_at": "2026-03-04T12:00:00+00:00",
                    "gathered_by": "cpr-enrichment-scanner",
                },
                {
                    "evidence_type": "test_files_modified",
                    "value": "10 test files modified since birth",
                    "gathered_at": "2026-03-04T12:00:00+00:00",
                    "gathered_by": "cpr-enrichment-scanner",
                },
            ],
        ),
        make_cpr(
            "cpr_eval_dual_02",
            "eval_dual_02",
            "enrichment_eligible",
            "Custom agents in .claude/agents/ load at session start only — files created mid-session require session restart",
            "eval-fixture/agents-loader.md:1",
            birth_tic=179,
            enrichment=[
                {
                    "evidence_type": "source_stable",
                    "value": "Source exists",
                    "gathered_at": "2026-03-05T12:00:00+00:00",
                    "gathered_by": "cpr-enrichment-scanner",
                },
            ],
        ),
    ]

    signals = [
        make_signal(
            "sig_eval_ecotone_01",
            "BEACON",
            "COGNITIVE",
            "ecotone",
            volume=65,
            summary="Ecotone integrity gate detected behavioral drift pattern",
        ),
        make_signal(
            "sig_eval_motivation_01",
            "BEACON",
            "COGNITIVE",
            "motivation_gate",
            volume=50,
            summary="Governance tag #PRESTIGE_PURSUIT active",
        ),
    ]

    tics = [make_tic_entry(i) for i in range(1, 4)]
    mandate = make_mandate("dual_cycle", cycles=["signal_scan", "queue_refresh"])

    write_jsonl(f"{output_dir}/audit-logs/cprs/queue.jsonl", cprs)
    write_jsonl(f"{output_dir}/audit-logs/signals/2026-03-06.jsonl", signals)
    write_jsonl(f"{output_dir}/audit-logs/tics/2026-03-06.jsonl", tics)
    write_json(f"{output_dir}/audit-logs/mogul/mandates/current.json", mandate)
    write_json(f"{output_dir}/.ticzone", make_ticzone())

    return {
        "scenario": "dual_cycle",
        "output_dir": output_dir,
        "cprs_seeded": len(cprs),
        "signals_seeded": len(signals),
        "tics_seeded": len(tics),
    }


SCENARIOS = {
    "queue_refresh": seed_queue_refresh,
    "enrichment": seed_enrichment,
    "dual_cycle": seed_dual_cycle,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed a governance workspace fixture for Mogul eval.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scenarios:
  queue_refresh   3 CPRs (pending, enrichment_eligible, promotable) + 1 signal
  enrichment      2 enrichment_eligible CPRs with thin evidence
  dual_cycle      Dual mandate (signal_scan + queue_refresh) with mixed state
        """,
    )
    parser.add_argument(
        "--scenario",
        required=True,
        choices=list(SCENARIOS.keys()),
        help="Which fixture scenario to seed",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write fixture files into",
    )
    args = parser.parse_args()

    try:
        result = SCENARIOS[args.scenario](args.output_dir)
    except OSError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
