#!/usr/bin/env python3
"""mandate-write.py — Centralized Mogul mandate writer with merge-before-write.

Single implementation of non-lossy mandate lifecycle for all trigger surfaces
(SessionStart, /cadence, /review, explicit). Called by hooks and skills.

Merge semantics:
  - If existing mandate status is pending|running: MERGE new cycles into existing,
    record old mandate_id in merged_from
  - If existing mandate status is consumed|failed|superseded: write fresh,
    record old mandate_id in supersedes
  - If no existing mandate: write fresh

Usage:
    python3 mandate-write.py \
        --zone-root /path/to/zone \
        --trigger-kind session_start \
        --trigger-source "cgg-runtime/hooks/session-restore.sh" \
        --tic 201 \
        --cycles queue_refresh,signal_scan,memory_mining \
        [--conformation-ref path/to/conformation.json] \
        [--runtime-verified]

Output: JSON mandate written to stdout + file. Exit 0 on success.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def compute_due_markers(tic: int) -> dict:
    """Compute due marker tics from current tic count."""
    return {
        "current_tic": tic,
        "review_due_tic": tic + 1,
        "memory_mining_due_tic": tic + (3 - tic % 3) if tic % 3 != 0 else tic + 3,
        "ladder_audit_due_tic": tic + (5 - tic % 5) if tic % 5 != 0 else tic + 5,
        "deep_audit_due_tic": tic + (8 - tic % 8) if tic % 8 != 0 else tic + 8,
    }


def read_existing_mandate(mandate_path: Path) -> dict | None:
    """Read existing mandate if present and valid JSON."""
    if not mandate_path.exists():
        return None
    try:
        return json.loads(mandate_path.read_text())
    except Exception:
        return None


def merge_or_supersede(existing: dict | None, new_cycles: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Determine merge/supersede behavior.

    Returns: (final_cycles, merged_from, supersedes)
    """
    if existing is None:
        return new_cycles, [], []

    existing_status = existing.get("status", "pending")  # backwards compat: no status = pending
    existing_id = existing.get("mandate_id", "")

    if existing_status in ("pending", "running"):
        # MERGE: absorb existing cycles
        existing_cycles = existing.get("cycle_request", {}).get("run_now", [])
        merged = list(new_cycles)
        for c in existing_cycles:
            if c not in merged:
                merged.append(c)

        # Also check existing due markers for overdue cycles
        tc = existing.get("tic_context", {})
        # (caller should handle due marker absorption via --cycles arg)

        merged_from = [existing_id] if existing_id else []
        return merged, merged_from, []

    elif existing_status in ("consumed", "failed", "superseded"):
        # Fresh write, record supersession
        supersedes = [existing_id] if existing_id else []
        return new_cycles, [], supersedes

    else:
        # Unknown status — treat as fresh write
        return new_cycles, [], []


def build_mandate(
    trigger_kind: str,
    trigger_source: str,
    tic: int,
    cycles: list[str],
    merged_from: list[str],
    supersedes: list[str],
    conformation_ref: str | None,
    runtime_verified: bool,
) -> dict:
    """Build a complete mandate object."""
    now = datetime.now(timezone.utc)
    mandate_id = f"tic-{tic}-{now.strftime('%Y%m%dT%H%M%S')}"

    return {
        "mandate_id": mandate_id,
        "status": "pending",
        "supersedes": supersedes,
        "merged_from": merged_from,
        "actor": {"office": "mogul", "embodiment": "cgg_runtime"},
        "trigger": {"kind": trigger_kind, "source_ref": trigger_source},
        "tic_context": compute_due_markers(tic),
        "cycle_request": {
            "run_now": list(set(cycles)),
            "reason": _build_reason(tic, trigger_kind, cycles, merged_from),
        },
        "conformation_ref": conformation_ref,
        "mode": {"blocking_to_homeskillet": False, "allow_subdelegation": True},
        "runtime_truth": {"canonical_vs_installed_verified": runtime_verified},
        "created_at": now.isoformat(),
        "started_at": None,
        "completed_at": None,
        "error": None,
    }


def _build_reason(tic: int, trigger_kind: str, cycles: list[str], merged_from: list[str]) -> str:
    reason = f"Tic {tic} — {trigger_kind}"
    if merged_from:
        reason += f" (merged from {merged_from[0]})"
    return reason


def write_mandate(mandate: dict, zone_root: Path, audit_logs_rel: str = "audit-logs") -> Path:
    """Write mandate to current.json and append to history."""
    audit_logs = zone_root / audit_logs_rel
    mandate_dir = audit_logs / "mogul" / "mandates"
    history_dir = mandate_dir / "history"
    mandate_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)

    mandate_file = mandate_dir / "current.json"
    mandate_file.write_text(json.dumps(mandate, indent=2))

    today = datetime.now().strftime("%Y-%m-%d")
    history_file = history_dir / f"{today}.jsonl"
    with open(history_file, "a") as f:
        f.write(json.dumps(mandate) + "\n")

    return mandate_file


def main():
    parser = argparse.ArgumentParser(description="Centralized Mogul mandate writer")
    parser.add_argument("--zone-root", required=True, help="Zone root path")
    parser.add_argument("--trigger-kind", required=True,
                        choices=["session_start", "first_prompt", "cadence", "review", "siren", "init_governance", "explicit"])
    parser.add_argument("--trigger-source", required=True, help="Source ref of the trigger")
    parser.add_argument("--tic", type=int, required=True, help="Current tic count")
    parser.add_argument("--cycles", required=True, help="Comma-separated cycle names")
    parser.add_argument("--conformation-ref", default=None, help="Path to conformation snapshot")
    parser.add_argument("--runtime-verified", action="store_true", help="Whether canonical vs installed is verified")
    parser.add_argument("--audit-logs-rel", default="audit-logs", help="Relative path to audit-logs dir")
    args = parser.parse_args()

    zone_root = Path(args.zone_root)
    cycles = [c.strip() for c in args.cycles.split(",") if c.strip()]

    # Read existing mandate for merge-before-write
    mandate_path = zone_root / args.audit_logs_rel / "mogul" / "mandates" / "current.json"
    existing = read_existing_mandate(mandate_path)

    # Determine merge/supersede
    final_cycles, merged_from, supersedes = merge_or_supersede(existing, cycles)

    # Build and write
    mandate = build_mandate(
        trigger_kind=args.trigger_kind,
        trigger_source=args.trigger_source,
        tic=args.tic,
        cycles=final_cycles,
        merged_from=merged_from,
        supersedes=supersedes,
        conformation_ref=args.conformation_ref,
        runtime_verified=args.runtime_verified,
    )

    written_path = write_mandate(mandate, zone_root, args.audit_logs_rel)

    # Output for caller
    print(json.dumps(mandate, indent=2))
    print(f"\nMandate written: {written_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
