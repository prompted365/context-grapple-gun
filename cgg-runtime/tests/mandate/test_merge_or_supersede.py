#!/usr/bin/env python3
"""
Mandate Test — merge-vs-supersede parity check (bk-cadence-ops-merge-not-supersede).

The doctrine-runtime PARITY residue for /review Step 8.5 + cgg-ledger *Even-Tic
Review-Close Routing*: a live (pending/running) mandate must be MERGED, never
superseded — superseding silently drops its unconsumed run_now cycles
(harmony_invoke / signal_scan / queue_refresh / review_close_check / …), the exact
cycles the next session requires Mogul to run.

Named CogPR the fix discharges:
  cpr_cadence_ops_supersedes_review_close_mandate_dropping_unconsumed_cycle_tic530
  (/review 532 SKIP-as-derivable — Case-2: doctrine already exists; residue = code fix
   + THIS parity check.)

The invariant this test pins (so a future edit cannot silently re-narrow the
merge-set — the ENA ray of the tic-534 splat):
  1. MERGE-not-supersede for every live status (pending / running).
  2. SUPERSEDE only on an EXPLICITLY terminal status (consumed / failed / superseded).
  3. The discriminator is STATUS, NOT trigger.kind — a live review-close mandate
     (kind==review) merges exactly like a live cadence mandate (kind==cadence).
  4. Non-destructive default: an UNRECOGNIZED / absent status is treated as live and
     MERGED (closes the status-vocabulary-drift drop the tic-530 incident exposed).

Self-contained; std-only; offline. Loads the hyphenated mandate-write.py via importlib
(matches tests/review/test_provenance_verb_recognition.py). Run directly:
  python3 tests/mandate/test_merge_or_supersede.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1].parent / "scripts" / "mandate-write.py"


def _load():
    spec = importlib.util.spec_from_file_location("mandate_write", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mandate(status, run_now, mid="m-existing"):
    """Minimal existing-mandate fixture carrying a status + run_now cycles."""
    m = {"mandate_id": mid, "cycle_request": {"run_now": list(run_now)}}
    if status is not None:
        m["status"] = status
    return m


def main() -> int:
    m = _load()
    mos = m.merge_or_supersede
    new_cycles = ["harmony_invoke", "signal_scan"]
    failures = []

    def check(name, existing, expect_verb, expect_preserved=None):
        final, merged_from, supersedes = mos(existing, list(new_cycles))
        verb = "supersede" if supersedes else ("merge" if merged_from else "fresh")
        if verb != expect_verb:
            failures.append(f"[{name}] expected {expect_verb}, got {verb} "
                            f"(merged_from={merged_from} supersedes={supersedes})")
            return
        # For merges, assert the existing cycle survived (no live obligation dropped).
        if expect_preserved is not None and expect_preserved not in final:
            failures.append(f"[{name}] live obligation dropped: {expect_preserved!r} "
                            f"not in final cycles {final}")

    # 1. First write — nothing to merge/supersede.
    check("none-first-write", None, "fresh")

    # 2. LIVE statuses MERGE and preserve the existing cycle.
    check("pending-review-close", _mandate("pending", ["review_close_check"]),
          "merge", expect_preserved="review_close_check")
    check("running-cadence", _mandate("running", ["queue_refresh"]),
          "merge", expect_preserved="queue_refresh")

    # 3. TERMINAL statuses SUPERSEDE (their cycles are already done).
    check("consumed-terminal", _mandate("consumed", ["old_cycle"]), "supersede")
    check("failed-terminal", _mandate("failed", ["old_cycle"]), "supersede")
    check("superseded-terminal", _mandate("superseded", ["old_cycle"]), "supersede")

    # 4. NON-DESTRUCTIVE DEFAULT — unrecognized / absent status is treated as live
    #    and MERGED (the status-vocabulary-drift guard; the tic-530 drop class).
    check("unknown-started-drift", _mandate("started", ["review_close_check"]),
          "merge", expect_preserved="review_close_check")
    check("no-status-field", _mandate(None, ["review_close_check"]),
          "merge", expect_preserved="review_close_check")

    # 5. DISCRIMINATOR IS STATUS, NOT trigger.kind — merge_or_supersede takes no
    #    trigger.kind argument, so a review-close mandate cannot be superseded as a
    #    CLASS. Assert the signature carries no kind discriminator (structural guard
    #    against re-introducing "supersede kind==review").
    import inspect
    params = list(inspect.signature(mos).parameters)
    if params != ["existing", "new_cycles"]:
        failures.append(f"[signature] merge_or_supersede must key on (existing, "
                        f"new_cycles) only — no trigger.kind discriminator; got {params}")

    if failures:
        print("FAIL — merge-vs-supersede parity:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — merge-vs-supersede parity (8 cases + signature guard): "
          "live=MERGE, terminal=SUPERSEDE, discriminator=status-not-kind.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
