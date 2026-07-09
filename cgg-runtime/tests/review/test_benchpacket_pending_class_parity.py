#!/usr/bin/env python3
"""
Review-lane test — bench-packet-prep pending-class taxonomy parity
(bk-bench-packet-drops-loadqueue-pending, tic 593).

Proves that `scripts/bench-packet-prep.py::get_pending_cprs` reads the FULL
authoritative pending-class vocabulary rather than a drifted narrow subset.

Root bug (fixed): get_pending_cprs carried a private 5-status allow-list
({pending, enrichment_needed, enrichment_eligible, extracted, review_ready})
that OMITTED `tic_gated`, `enrichment_in_progress`, `promotable`, and
`born_truth_captured`. The oracle
(`audit-logs/cpg/scripts/governance_query.py::PENDING_CLASS_STATUSES`, whose
`pending_total` is the task-declared authoritative count) recognizes all nine.
So any id whose latest non-terminal status was one of the four omitted values
was SILENTLY DROPPED by bench-packet while still counted by the oracle — a
silent-degrade reader violating the federation invariant "Authoritative-set
readers must read the manifest, not aggregate raw emissions."

Two behaviours under test (synthetic canonical queue, no live queue):
  1. FULL COVERAGE — every one of the 9 authoritative pending-class statuses is
     surfaced by get_pending_cprs; terminal-status rows are NOT.
  2. REGRESSION GUARD — the four previously-dropped statuses (tic_gated,
     enrichment_in_progress, promotable, born_truth_captured) are surfaced.
     This is the exact set the old narrow allow-list dropped.
  3. ORACLE PARITY — the module PENDING_CLASS_STATUSES equals the authoritative
     set governance_query.py publishes as its pending_class_definition.

Run: python3 tests/review/test_benchpacket_pending_class_parity.py
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

# The authoritative pending-class vocabulary, mirrored from
# audit-logs/cpg/scripts/governance_query.py::PENDING_CLASS_STATUSES
# (the oracle whose pending_total the task pins as authoritative). Kept here as
# a literal so this test fails loudly if bench-packet drifts away from the
# oracle again.
ORACLE_PENDING_CLASS = {
    "pending",
    "extracted",
    "tic_gated",
    "enrichment_needed",
    "enrichment_in_progress",
    "enrichment_eligible",
    "promotable",
    "review_ready",
    "born_truth_captured",
}

# The exact statuses the pre-fix narrow allow-list dropped.
PREVIOUSLY_DROPPED = {
    "tic_gated",
    "enrichment_in_progress",
    "promotable",
    "born_truth_captured",
}

TERMINAL_SAMPLE = {"promoted", "absorbed", "rejected", "deferred", "skipped"}


def _load_module():
    spec = importlib.util.spec_from_file_location("bench_packet_prep", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    mod = _load_module()

    failures = []

    # (3) ORACLE PARITY — module set must equal the oracle's published set.
    module_set = set(mod.PENDING_CLASS_STATUSES)
    if module_set != ORACLE_PENDING_CLASS:
        missing = ORACLE_PENDING_CLASS - module_set
        extra = module_set - ORACLE_PENDING_CLASS
        failures.append(
            f"FAIL(parity): PENDING_CLASS_STATUSES != oracle "
            f"(missing={sorted(missing)}, extra={sorted(extra)})"
        )

    # Build a synthetic canonical queue: one id per pending-class status +
    # one id per sampled terminal status. get_pending_cprs consumes the
    # terminal-valve latest-per-id map (exactly this shape).
    queue = {}
    for st in ORACLE_PENDING_CLASS:
        queue[f"cpr_pending_{st}"] = {"id": f"cpr_pending_{st}", "status": st}
    for st in TERMINAL_SAMPLE:
        queue[f"cpr_terminal_{st}"] = {"id": f"cpr_terminal_{st}", "status": st}

    surfaced = mod.get_pending_cprs(queue)
    surfaced_statuses = {e["status"] for e in surfaced.values()}

    # (1) FULL COVERAGE — every pending-class status surfaced, no terminal ones.
    if surfaced_statuses != ORACLE_PENDING_CLASS:
        missing = ORACLE_PENDING_CLASS - surfaced_statuses
        leaked_terminal = surfaced_statuses & TERMINAL_SAMPLE
        failures.append(
            f"FAIL(coverage): surfaced statuses {sorted(surfaced_statuses)} "
            f"(missing={sorted(missing)}, leaked_terminal={sorted(leaked_terminal)})"
        )

    # (2) REGRESSION GUARD — the four previously-dropped statuses are surfaced.
    for st in PREVIOUSLY_DROPPED:
        if f"cpr_pending_{st}" not in surfaced:
            failures.append(
                f"FAIL(regression): previously-dropped status '{st}' not surfaced"
            )

    if failures:
        print("BENCH-PACKET PENDING-CLASS PARITY TEST: FAIL")
        for f in failures:
            print("  " + f)
        return 1

    print("BENCH-PACKET PENDING-CLASS PARITY TEST: PASS")
    print(f"  pending-class surfaced ({len(surfaced_statuses)}): "
          f"{sorted(surfaced_statuses)}")
    print(f"  previously-dropped now surfaced: {sorted(PREVIOUSLY_DROPPED)}")
    print(f"  terminal rows correctly excluded: {sorted(TERMINAL_SAMPLE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
