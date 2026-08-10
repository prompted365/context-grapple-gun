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

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import birth_topology


# Queue-truth review_due derivation (bk-cadence-ops-review-due-formula-off-by-one,
# filed tic 690 after four consecutive off-by-one observations t687-690: the
# unconditional tic+1 stamp contradicted the queue maturity law, which matures
# rows AT entry). review_due_tic is a PROJECTION for readers of tic_context —
# the bench/docket lane derives the real docket independently and has never
# been wrong; derivation here is therefore fail-soft (any read failure falls
# back to tic + 1) so a mandate write can never block on the stamp.
# LOCKSTEP MIRRORS (no import to avoid a cadence-ops circular import):
#   _DEFAULT_MATURITY_TICS mirrors ripple-assessor.py DEFAULT_MATURITY_TICS;
#   _REVIEW_PENDING_STATUSES mirrors cadence-ops.py pending_statuses.
_DEFAULT_MATURITY_TICS = 3
_REVIEW_PENDING_STATUSES = {
    "pending", "extracted", "tic_gated", "enrichment_needed",
    "enrichment_in_progress", "enrichment_eligible", "promotable", "review_ready",
}


def _derive_review_due_tic(tic: int, queue_path: Path | None) -> int:
    """min over pending birth-carrying rows of (birth_tic + maturity_tics),
    clamped to >= tic; tic + 1 when no row carries a maturity clock.

    Latest-entry-per-id read discipline; birthless rows (birth_tic null/0 —
    evidence-gated classes like C3) contribute no clock. Fail-soft throughout.
    """
    default = tic + 1
    if queue_path is None or not queue_path.exists():
        return default
    try:
        entries: dict[str, dict] = {}
        with open(queue_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rid = row.get("id")
                if rid:
                    entries[rid] = row
        clocks = []
        for row in entries.values():
            if row.get("status") not in _REVIEW_PENDING_STATUSES:
                continue
            # `or 0` coalesces explicit birth_tic: null (tic-646 mirror).
            birth = row.get("birth_tic") or 0
            if not isinstance(birth, int) or birth <= 0:
                continue
            mt = row.get("maturity_tics")
            mt = _DEFAULT_MATURITY_TICS if mt is None else mt
            clocks.append(birth + mt)
        if not clocks:
            return default
        return max(tic, min(clocks))
    except Exception:
        return default


def compute_due_markers(tic: int, zone_root_path: str | None = None) -> dict:
    """Compute due marker tics from current tic count.

    With zone_root_path, review_due_tic derives from queue truth (see
    _derive_review_due_tic); without it, the legacy tic + 1 projection holds.
    """
    queue_path = None
    if zone_root_path:
        queue_path = Path(zone_root_path) / "audit-logs" / "cprs" / "queue.jsonl"
    return {
        "current_tic": tic,
        "review_due_tic": _derive_review_due_tic(tic, queue_path),
        "memory_mining_due_tic": tic + (3 - tic % 3) if tic % 3 != 0 else tic + 3,
        "pattern_mining_due_tic": tic + (4 - tic % 4) if tic % 4 != 0 else tic + 4,
        "ladder_audit_due_tic": tic + (5 - tic % 5) if tic % 5 != 0 else tic + 5,
        "civil_check_due_tic": tic + (10 - tic % 10) if tic % 10 != 0 else tic + 10,
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


# Terminal mandate statuses — the ONLY statuses that license a supersede. A terminal
# mandate is already consumed or dead, so its run_now cycles are done and recording a
# supersession (rather than merging) is truthful. mogul-runner writes the lifecycle:
# pending (build_mandate) -> running (mogul-runner.sh ~L200, on start) -> consumed
# (mogul-runner.sh ~L882, on complete); "failed"/"superseded" are the other terminal exits.
_TERMINAL_MANDATE_STATUSES = ("consumed", "failed", "superseded")


def merge_or_supersede(existing: dict | None, new_cycles: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Determine merge/supersede behavior for the mandate about to be written.

    INVARIANT (/review Step 8.5 + cgg-ledger *Even-Tic Review-Close Routing*):
    **MERGE a live mandate; SUPERSEDE only a terminal one.** Superseding a live mandate
    silently drops its unconsumed run_now cycles (harmony_invoke / signal_scan /
    queue_refresh / review_close_check / …) — the exact cycles the next session requires
    Mogul to run. "No cycle overlap" is NOT a license to supersede.

    The discriminator is **status (lifecycle liveness), NOT trigger.kind.** A live
    review-close mandate (trigger.kind == "review", written by /review Step 8.5) is merged
    exactly like a live cadence mandate (kind == "cadence") — both carry cycles the next
    session owes. Keying supersede on trigger.kind == "review" would REINTRODUCE the
    tic-530 drop (cpr_cadence_ops_supersedes_review_close_mandate_dropping_unconsumed_cycle
    _tic530). Do not add a trigger.kind discriminator here.

    DEFAULT IS THE NON-DESTRUCTIVE MOVE: any status that is not *explicitly terminal* is
    treated as live and MERGED. This closes the status-vocabulary-drift gap — an
    unrecognized live status (older runner, hand-authored mandate, new lifecycle state)
    can no longer fall through to a fresh-write that silently drops a live obligation.

    Returns: (final_cycles, merged_from, supersedes)
    """
    if existing is None:
        return new_cycles, [], []

    existing_status = existing.get("status", "pending")  # no status = pending (live)
    existing_id = existing.get("mandate_id", "")

    if existing_status in _TERMINAL_MANDATE_STATUSES:
        # SUPERSEDE — the existing mandate is terminal; its cycles are already done.
        supersedes = [existing_id] if existing_id else []
        return new_cycles, [], supersedes

    # MERGE — the existing mandate is live (pending / running) OR carries a status we do
    # not recognize as terminal and must therefore not assume is dead. Absorb its
    # unconsumed run_now cycles so none are dropped (dedup-preserving; the caller handles
    # overdue due-marker absorption via its --cycles arg).
    existing_cycles = existing.get("cycle_request", {}).get("run_now", [])
    merged = list(new_cycles)
    for c in existing_cycles:
        if c not in merged:
            merged.append(c)
    merged_from = [existing_id] if existing_id else []
    return merged, merged_from, []


def build_mandate(
    trigger_kind: str,
    trigger_source: str,
    tic: int,
    cycles: list[str],
    merged_from: list[str],
    supersedes: list[str],
    conformation_ref: str | None,
    runtime_verified: bool,
    zone_root_path: str | None = None,
) -> dict:
    """Build a complete mandate object."""
    now = datetime.now(timezone.utc)
    mandate_id = f"tic-{tic}-{now.strftime('%Y%m%dT%H%M%S')}"
    topo = birth_topology(zone_root_path)

    return {
        "mandate_id": mandate_id,
        "status": "pending",
        "supersedes": supersedes,
        "merged_from": merged_from,
        "actor": {"office": "mogul", "embodiment": "cgg_runtime"},
        "trigger": {"kind": trigger_kind, "source_ref": trigger_source},
        "tic_context": compute_due_markers(tic, zone_root_path),
        "cycle_request": {
            "run_now": list(set(cycles)),
            "reason": _build_reason(tic, trigger_kind, cycles, merged_from),
        },
        "conformation_ref": conformation_ref,
        "mode": {"blocking_to_orchestrator": False, "allow_subdelegation": True},
        "runtime_truth": {"canonical_vs_installed_verified": runtime_verified},
        "rung": topo["birth_rung"],
        "topology_chain": topo["topology_chain"],
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


def _schema_path() -> Path:
    """Path to the mandate contract schema (sibling config/ dir; parity-synced install + canonical)."""
    return Path(__file__).resolve().parent.parent / "config" / "mogul-mandate.schema.json"


def _die_invalid(errors: list[str]) -> None:
    """Fail-closed exit — the malformed mandate is NOT written."""
    print("[mandate-write] SCHEMA VALIDATION FAILED (fail-closed, /review 598) — mandate NOT written:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    print("  Fix: reconcile the producer (compute_due_markers / build_mandate) with "
          "config/mogul-mandate.schema.json, or add the value to the schema enum.", file=sys.stderr)
    raise SystemExit(2)


def validate_mandate_or_die(mandate: dict) -> None:
    """Fail-closed schema validation at the write boundary — physics-layer enforcement.

    Ratified /review 598 (Architect: fail-closed raise). The schema calls itself
    "machine-checkable"; this makes that TRUE instead of decorative — born tic-597
    (slice-only-audit legibility probe): a decorative contract is a legibility gap, and
    "nothing validates it" is exactly how the producer silently drifted to emit
    schema-forbidden fields. A malformed mandate must NOT land.

    Prefers `jsonschema` (full validation) when installed; otherwise a hand-rolled
    fallback that reads the ENUMS + property sets FROM the schema (engine/content
    separation — the schema stays the single source of truth) and enforces the
    load-bearing constraints: required keys, enum membership (status / embodiment /
    trigger.kind / run_now cycles), and additionalProperties:false on the surfaces that
    have historically drifted (top-level, cycle_request, tic_context). A missing schema
    FILE degrades to a LOUD skip (a different failure the raise cannot fix); an actual
    VIOLATION raises (SystemExit 2).
    """
    schema_path = _schema_path()
    if not schema_path.exists():
        print(f"[mandate-write] WARNING: schema not found at {schema_path} — "
              "validation SKIPPED (contract file missing).", file=sys.stderr)
        return
    schema = json.loads(schema_path.read_text())

    # Preferred: full JSON-Schema validation when the library is installed.
    try:
        import jsonschema  # type: ignore
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        try:
            jsonschema.validate(instance=mandate, schema=schema)
            return
        except jsonschema.ValidationError as e:
            loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
            _die_invalid([f"{loc}: {e.message}"])

    # Hand-rolled fallback — enums + property sets are READ from the schema (content-separated).
    errors: list[str] = []
    props = schema.get("properties", {})

    for req in schema.get("required", []):
        if req not in mandate:
            errors.append(f"missing required top-level key: {req}")
    if schema.get("additionalProperties") is False:
        for k in mandate:
            if k not in props:
                errors.append(f"unexpected top-level key (additionalProperties:false): {k}")

    status_enum = props.get("status", {}).get("enum")
    if status_enum and mandate.get("status") not in status_enum:
        errors.append(f"status {mandate.get('status')!r} not in {status_enum}")

    actor = mandate.get("actor", {})
    emb_enum = props.get("actor", {}).get("properties", {}).get("embodiment", {}).get("enum")
    if emb_enum and actor.get("embodiment") not in emb_enum:
        errors.append(f"actor.embodiment {actor.get('embodiment')!r} not in {emb_enum}")

    kind_enum = props.get("trigger", {}).get("properties", {}).get("kind", {}).get("enum")
    if kind_enum and mandate.get("trigger", {}).get("kind") not in kind_enum:
        errors.append(f"trigger.kind {mandate.get('trigger', {}).get('kind')!r} not in {kind_enum}")

    cr_schema = props.get("cycle_request", {})
    cr_props = cr_schema.get("properties", {})
    cr = mandate.get("cycle_request", {})
    run_now_enum = cr_props.get("run_now", {}).get("items", {}).get("enum", [])
    for c in cr.get("run_now", []):
        if run_now_enum and c not in run_now_enum:
            errors.append(f"cycle_request.run_now cycle {c!r} not in the {len(run_now_enum)}-cycle enum")
    if cr_schema.get("additionalProperties") is False:
        for k in cr:
            if k not in cr_props:
                errors.append(f"unexpected cycle_request key (additionalProperties:false): {k}")

    tc_schema = props.get("tic_context", {})
    tc_props = tc_schema.get("properties", {})
    tc = mandate.get("tic_context", {})
    if "current_tic" not in tc:
        errors.append("tic_context missing required current_tic")
    if tc_schema.get("additionalProperties") is False:
        for k in tc:
            if k not in tc_props:
                errors.append(f"unexpected tic_context key (additionalProperties:false): {k}")

    if errors:
        _die_invalid(errors)


def _append_history_jsonl(history_file: Path, row: dict) -> None:
    """Append one row to the mandate history ledger (atomic-append discipline)."""
    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(str(history_file), row)
    except ImportError:
        import fcntl
        lockfile = str(history_file) + ".lock"
        with open(lockfile, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                with open(history_file, "a") as f:
                    f.write(json.dumps(row) + "\n")
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def _terminalize_absorbed_pending(mandate: dict, absorbed: dict | None, history_file: Path) -> None:
    """Close the absorbed lane at the merge site (bk-mandate-merge-terminalize-absorbed,
    /review-691 ratified: A MERGE MUST TERMINALIZE WHAT IT CONSUMES).

    A merge that absorbs a NEVER-DISPATCHED (pending) predecessor is the only
    absorption with no other terminal writer: a running predecessor's own runner
    still lands running_to_consumed[_detached] through the write-back guard, and
    the supersede branch fires only on already-terminal records. Recording the
    absorption only on the absorber (merged_from) left the absorbed record's
    ledger lane permanently non-terminal — inverting the declared tiebreaker
    authority ("on disagreement the LEDGER is truth", cgg-gate.sh protocol 2.5).

    Emission keys on BOUNDARY TRUTH — the record current.json held at the
    clobber, not the merge-time snapshot: it must be named in this mandate's
    merged_from AND still be status "pending" (an unrecognized live status is
    merged for safety but never mislabeled pending_to_merged; a predecessor that
    started running in between keeps its own terminal writer). Fail-soft: a
    ledger emission failure warns and never blocks the mandate write.
    """
    if absorbed is None:
        return
    absorbed_id = absorbed.get("mandate_id", "")
    if not absorbed_id or absorbed_id == mandate.get("mandate_id"):
        return
    if absorbed_id not in mandate.get("merged_from", []):
        return
    if absorbed.get("status", "pending") != "pending":
        return
    try:
        _append_history_jsonl(history_file, {
            "transition": "pending_to_merged",
            "mandate_id": absorbed_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "merged_into": mandate["mandate_id"],
            "emitted_by": "mandate-write",
        })
    except Exception as e:
        print(f"[mandate-write] WARN: pending_to_merged emission failed for "
              f"{absorbed_id} ({e}); the absorbed lane stays open in the ledger.",
              file=sys.stderr)


def write_mandate(mandate: dict, zone_root: Path, audit_logs_rel: str = "audit-logs") -> Path:
    """Write mandate to current.json and append to history.

    Fail-closed validation fires HERE — the true write boundary — so EVERY caller is
    covered: the CLI main() path (session-restore.sh) AND direct-import callers
    (cadence-ops.py builds+writes via the imported functions, bypassing main()). A
    malformed mandate raises SystemExit(2) before any disk write. (/review 598.)
    The merge-terminalize emission lives at the same boundary for the same reason:
    the current.json overwrite IS the absorption.
    """
    validate_mandate_or_die(mandate)
    audit_logs = zone_root / audit_logs_rel
    mandate_dir = audit_logs / "mogul" / "mandates"
    history_dir = mandate_dir / "history"
    mandate_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)

    mandate_file = mandate_dir / "current.json"
    # Read the record being clobbered BEFORE the overwrite — the terminalize
    # decision keys on what the file holds at the boundary.
    absorbed = read_existing_mandate(mandate_file)
    mandate_file.write_text(json.dumps(mandate, indent=2))

    today = datetime.now().strftime("%Y-%m-%d")
    history_file = history_dir / f"{today}.jsonl"
    # Ledger order: close the absorbed lane first, then the successor's row.
    _terminalize_absorbed_pending(mandate, absorbed, history_file)
    _append_history_jsonl(history_file, mandate)

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
        zone_root_path=str(zone_root),
    )

    # Validation fires inside write_mandate() (the true write boundary — covers this
    # CLI path AND direct-import callers like cadence-ops.py). /review 598.
    written_path = write_mandate(mandate, zone_root, args.audit_logs_rel)

    # Output for caller
    print(json.dumps(mandate, indent=2))
    print(f"\nMandate written: {written_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
