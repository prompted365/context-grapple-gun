#!/usr/bin/env python3
"""Fixture replay for cpr_steppable.py — the CPR-STEP lane marker predicate.

Covenant success-check 1 (cpr_step_lane_marker_per_id_maturity_tic655):
replay the t620 case — a queue projection where one row matures at N+1 must
yield a marker count EXCLUDING it at N and INCLUDING it at N+1 (the lived
2-vs-honest-1 over-count flips to honest).

Per selftest discipline (cgg-ledger#selftest-fixtures-must-exercise-
documented-conditional-paths): every documented conditional gets BOTH arms.
"""

import sys

import cpr_steppable as cs


FAILURES = []


def check(name, actual, expected):
    ok = actual == expected
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: got {actual!r}, expected {expected!r}")
    if not ok:
        FAILURES.append(name)


def main():
    N = 620  # the lived defect tic

    # ── t620 replay: 2-vs-honest-1 ──────────────────────────────────────
    # Row A: extracted, born N-3 → delta 3 >= 3, mature at N.
    # Row B: extracted, born N-2 → delta 2 < 3, matures only at N+1.
    # The old aggregate marker said 2; the honest per-id set at N is 1.
    queue = {
        "cpr_a": {"status": "extracted", "birth_tic": N - 3},
        "cpr_b": {"status": "extracted", "birth_tic": N - 2},
    }
    check("t620 replay: count at N excludes the immature row (honest 1)",
          cs.count_steppable(queue, N), 1)
    check("t620 replay: count at N+1 includes it (flips to 2)",
          cs.count_steppable(queue, N + 1), 2)

    # ── status arms ─────────────────────────────────────────────────────
    check("tic_gated is steppable regardless of birth (in-transit)",
          cs.is_steppable({"status": "tic_gated", "birth_tic": N}, N), True)
    check("terminal/holding statuses are never steppable",
          cs.count_steppable({
              "p": {"status": "promoted", "birth_tic": N - 10},
              "e": {"status": "enrichment_needed", "birth_tic": N - 10},
              "x": {"status": "absorbed", "birth_tic": N - 10},
          }, N), 0)

    # ── provenance-class arms ───────────────────────────────────────────
    check("construction_authoritative waives the temporal hold (delta 0)",
          cs.is_steppable({"status": "extracted", "birth_tic": N,
                           "provenance_class": "construction_authoritative"}, N),
          True)
    check("friction_born at delta 0 is held",
          cs.is_steppable({"status": "extracted", "birth_tic": N,
                           "provenance_class": "friction_born"}, N), False)
    check("absent provenance_class defaults to friction_born (held at delta 2)",
          cs.is_steppable({"status": "extracted", "birth_tic": N - 2}, N), False)

    # ── per-row maturity_tics override arms ─────────────────────────────
    row = {"status": "extracted", "birth_tic": N - 5, "maturity_tics": 10}
    check("per-row maturity_tics override holds at delta 5 < 10",
          cs.is_steppable(row, N), False)
    check("per-row maturity_tics override releases at delta 10",
          cs.is_steppable(row, N + 5), True)
    check("malformed maturity_tics falls back to default 3",
          cs.is_steppable({"status": "extracted", "birth_tic": N - 3,
                           "maturity_tics": "not-a-number"}, N), True)

    # ── fail-visible arms ───────────────────────────────────────────────
    check("extracted with no derivable birth_tic is counted (fail-visible)",
          cs.is_steppable({"status": "extracted"}, N), True)
    check("clock fault (tic 0) falls back to legacy aggregate",
          cs.count_steppable({
              "a": {"status": "extracted", "birth_tic": N - 1},
              "b": {"status": "tic_gated", "birth_tic": N},
              "p": {"status": "promoted", "birth_tic": N - 10},
          }, 0), 2)
    check("clock fault (tic None) falls back to legacy aggregate",
          cs.count_steppable({"a": {"status": "extracted", "birth_tic": 1}}, None), 1)

    print()
    total = 13
    if FAILURES:
        print(f"FAIL {len(FAILURES)}/{total}: {FAILURES}")
        return 1
    print(f"ALL PASS ({total}/{total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
