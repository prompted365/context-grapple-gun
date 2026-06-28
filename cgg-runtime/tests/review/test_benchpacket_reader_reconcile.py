#!/usr/bin/env python3
"""
Review-lane test — bench-packet-prep C-3 reader cure (tic 523).

Proves the tic-222 contract reader cure in
`scripts/bench-packet-prep.py::reconcile_surfaced_ids`:
bench-packet's surfaced pending set is reconciled to the compiler's
`live_now` classification, resolving
cgg-ledger#status-value-reader-disagreement-sticky-masks-reactivated-item
(C-3, promoted /review 522).

The cure is a UNION with park-aware subtraction, NOT a wholesale flip:

    surfaced = compiler_live_now
             ∪ (load_queue_pending MINUS items the compiler PARKS/TERMINALIZES)

Four behaviours under test (one synthetic effective_state, no live queue):
  1. RE-ACTIVATED DEFER added — a 'deferred' id the compiler buckets live_now
     (re_eval_tic reached) is surfaced even though load_queue's sticky-deferred
     terminal-valve masked it. (the core C-3 bug)
  2. COMPILER-PARKED excluded — a load_queue-pending id the compiler buckets
     parked_to_<tic> (re_eval_tic > current_tic) is NOT surfaced.
  3. COMPILER-BLIND kept — a load_queue-pending id the compiler does NOT
     recognize ('pending'/'review_ready' compile to 'unknown'/'metadata') is
     KEPT, never dropped. (the apophatic guard against a naive flip)
  4. DEGRADED fallback — with no effective_state, surfaced == load_queue_pending
     and reconciliation is None.

Run: python3 tests/review/test_benchpacket_reader_reconcile.py
Exit 0 = PASS, 1 = FAIL.
"""

import importlib.util
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "bench-packet-prep.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("bench_packet_prep", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _state(eid, bucket, status):
    return {"id": eid, "bucket": bucket, "effective_status": status}


def main():
    mod = _load_module()
    reconcile = mod.reconcile_surfaced_ids

    # --- Synthetic effective_state (the compiler's view) ---
    # current_tic is implicit in the compiler's bucket assignment; we encode the
    # outcomes directly as buckets, which is exactly what reconcile reads.
    effective_state = {
        "states": {
            # genuinely live per compiler (active, not parked)
            "id_live_active": _state("id_live_active", "live_now", "enrichment_eligible"),
            # re-activated DEFER: compiler says live_now, load_queue masks it
            "id_reactivated_defer": _state("id_reactivated_defer", "live_now", "deferred"),
            # compiler PARKS this load_queue-pending id (re_eval in future)
            "id_parked": _state("id_parked", "parked_to_999", "deferred"),
            # compiler TERMINALIZES this load_queue-pending id
            "id_terminal": _state("id_terminal", "terminal_promoted", "promoted"),
            # compiler-active id load_queue never recognized (tic_gated)
            "id_tic_gated": _state("id_tic_gated", "live_now", "tic_gated"),
        }
    }

    # load_queue's pre-cure pending set (bench-packet terminal-valve view).
    # Note: 'id_reactivated_defer' and 'id_tic_gated' are NOT here — load_queue
    # masks them (sticky-deferred / unrecognized status). 'id_blind' is a
    # 'pending'-status row the compiler doesn't recognize at all (no state).
    load_queue_pending_ids = {
        "id_live_active",   # both readers agree
        "id_parked",        # compiler parks -> must be excluded
        "id_terminal",      # compiler terminalizes -> must be excluded
        "id_blind",         # compiler-blind ('pending'/'review_ready') -> must be kept
    }

    surfaced, live_now_ids, recon = reconcile(load_queue_pending_ids, effective_state)

    failures = []

    # (1) re-activated DEFER added
    if "id_reactivated_defer" not in surfaced:
        failures.append("FAIL(1): re-activated DEFER not surfaced")
    # tic_gated (compiler-active, load_queue-blind) also surfaced
    if "id_tic_gated" not in surfaced:
        failures.append("FAIL(1b): compiler-live tic_gated not surfaced")

    # (2) compiler-parked / terminalized excluded
    if "id_parked" in surfaced:
        failures.append("FAIL(2): compiler-parked id wrongly surfaced")
    if "id_terminal" in surfaced:
        failures.append("FAIL(2b): compiler-terminal id wrongly surfaced")

    # (3) compiler-blind kept (the apophatic guard — never dropped)
    if "id_blind" not in surfaced:
        failures.append("FAIL(3): compiler-blind 'pending' id wrongly DROPPED")

    # agreement item present
    if "id_live_active" not in surfaced:
        failures.append("FAIL(0): agreed-live id missing")

    # reconciliation record correctness
    if recon is None:
        failures.append("FAIL(recon): reconciliation is None under PRODUCTIZED")
    else:
        if set(recon["parked_by_compiler"]) != {"id_parked", "id_terminal"}:
            failures.append(
                f"FAIL(recon.parked): {recon['parked_by_compiler']}"
            )
        if "id_blind" not in recon["kept_compiler_blind"]:
            failures.append(
                f"FAIL(recon.blind): {recon['kept_compiler_blind']}"
            )
        added = set(recon["added_from_compiler_live_now"])
        if not {"id_reactivated_defer", "id_tic_gated"} <= added:
            failures.append(f"FAIL(recon.added): {recon['added_from_compiler_live_now']}")

    # exact surfaced set
    expected = {"id_live_active", "id_reactivated_defer", "id_tic_gated", "id_blind"}
    if surfaced != expected:
        failures.append(f"FAIL(surfaced): got {sorted(surfaced)} expected {sorted(expected)}")

    # (4) DEGRADED fallback
    d_surfaced, d_live, d_recon = reconcile(load_queue_pending_ids, None)
    if d_surfaced != load_queue_pending_ids:
        failures.append("FAIL(4): DEGRADED surfaced != load_queue_pending")
    if d_recon is not None:
        failures.append("FAIL(4b): DEGRADED reconciliation should be None")
    if d_live != set():
        failures.append("FAIL(4c): DEGRADED live_now_ids should be empty")

    if failures:
        print("BENCH-PACKET READER-CURE TEST: FAIL")
        for f in failures:
            print("  " + f)
        return 1

    print("BENCH-PACKET READER-CURE TEST: PASS")
    print(f"  surfaced = {sorted(surfaced)}")
    print(f"  parked_by_compiler = {sorted(recon['parked_by_compiler'])}")
    print(f"  kept_compiler_blind = {sorted(recon['kept_compiler_blind'])}")
    print(f"  added_from_compiler_live_now = {sorted(recon['added_from_compiler_live_now'])}")
    print("  DEGRADED fallback: surfaced==load_queue_pending, recon=None — OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
