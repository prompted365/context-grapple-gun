#!/usr/bin/env python3
"""effective_state_recompile — the ONE owner of "after a successful queue
mutation, recompile the projection for the zone that owns that queue".

FIX-SITE: /review 803 round 2 (Ruling A), Architect-ratified on the recommended
option verbatim ("One shared helper, all five writers, today"). Ruling receipt:
  audit-logs/governance/receipts/2026-09-19-tic803-projection-shared-recompile-helper-ruling.md
It EXTENDS — does not reverse — the /review 801 round-2 ruling ("Key the writer
on mutation", receipts/2026-09-19-tic801-projection-writer-locus-ruling.md).

THE CONTRACT (one sentence, one owner)
--------------------------------------
After a SUCCESSFUL queue mutation, recompile the derived effective-state
projection for the zone that owns THAT queue; FAIL-SOFT (a compile error never
fails the mutation and never raises into the caller), and SAY SO on stderr.

WHY ONE MODULE. At tic 802 this body existed in THREE copies held together by
diligence — queue-lifecycle-writeback.recompile_effective_state (the ratified
original) plus two faithful copies in cogpr-ingest.py and cpr-extract.py — while
three further queue MUTATORS (pattern_miner.py, cpr-gate-advance.py,
cpr-enrichment-scanner.py) had no copy at all and left the projection stale after
every mutation. That is F-802-B4 (drift-by-copy) stacked on F-802-B1/B2 (the
uncovered writers). The ruled cure is one contract with five call sites, not
three copies and two gaps.

DOES-NOT-SATISFY RIDER (travels verbatim with this increment, on ONE unbroken
line so a byte-exact grep resolves it):
this increment does NOT add a reader-side staleness detector, does NOT prove the compiled per-id states are correct, does NOT test two writers racing, and does NOT make the projection authoritative over the queue — `queue.jsonl` latest-per-id remains the only authority; the projection is a derived convenience that is now writer-fresh for five of six writers by construction and for the sixth by its own code.

ZONE LAW (CLI shape 22 — the defect this family keeps re-meeting)
-----------------------------------------------------------------
Two path KINDS live here and they resolve from DIFFERENT anchors. Conflating
them is the whole defect:

  * ZONE paths (the compiler to run, the --out directory, the tic log) are
    derived from THE QUEUE PATH THIS HELPER WAS HANDED — the queue the caller's
    mutation ACTUALLY wrote — and NEVER from this module's own __file__. The
    INSTALLED copy of this module lives under ~/.claude/cgg-runtime/scripts/lib/,
    whose ancestry carries no `.ticzone` and no audit-logs/cprs/queue.jsonl, so
    any __file__-anchored zone resolution would miss the canonical zone
    entirely (or silently pick another one). Deriving from the queue is what
    makes the source copy and the installed copy behave identically.
        compiler := <queue>.parent / "queue_state_compile.py"
        --out    := <queue>.parent / "effective-state"
        tic log  := <queue>.parent.parent / "tics"
    The compiler's own DEFAULT_OUT is Path(__file__)-relative, which is exactly
    why --out is pinned explicitly on every invocation.

  * CODE paths (the sibling module this helper REUSES for the clock) are
    __file__-relative, and correctly so: code travels with the installation, so
    the installed copy must load the installed sibling. This is NOT a zone
    resolution and does not read the tree under test.

THE CLOCK is cpr-gate-advance.resolve_current_tic (`domain_counter_after` on the
LATEST tic event), read from the QUEUE's own audit-logs root. A second tic reader
minted here would be the exact counter-disagreement shape `Disagreement-as-
evidence` names. Deliberately NOT cogpr-ingest.get_tic_count(), which aggregates
raw `type=tic` rows on `global_counter_after` — a second, divergent clock.

FAIL-SOFT, ABSOLUTELY. The queue write is the constitutional write; the
projection is a derived cache. No path in this module raises into the caller:
every failure returns (False, typed_detail) and prints to stderr, so a landed
mutation stays landed.

CONSUMERS (the closed call-site set as of tic 803 — five writers):
  scripts/pattern_miner.py · scripts/cpr-gate-advance.py ·
  scripts/cpr-enrichment-scanner.py · scripts/cogpr-ingest.py ·
  scripts/cpr-extract.py
A SIXTH mutator, scripts/queue-lifecycle-writeback.py, carries its own ratified
copy of this contract and is deliberately NOT refactored onto this module: it is
the live /review verdict path and was named OUT of the tic-803 fence by the
ruling itself.
"""

import os
import subprocess
import sys
from pathlib import Path

__all__ = ["recompile_effective_state", "resolve_recompile_tic"]

# CODE path, not a zone path (see ZONE LAW above): the sibling clock reader lives
# beside this package in the scripts/ directory of the SAME installation.
_SIBLING_CLOCK_CANDIDATES = ("cpr-gate-advance.py",)


def _sibling_clock_module():
    """Load cpr-gate-advance as a module, or return None. NEVER raises.

    Probes this module's parent (scripts/, the normal layout: this file is
    scripts/lib/effective_state_recompile.py) and then its own directory (a flat
    vendoring). Both are CODE lookups anchored on __file__ by design.
    """
    here = Path(__file__).resolve().parent
    for base in (here.parent, here):
        for name in _SIBLING_CLOCK_CANDIDATES:
            cand = base / name
            if not cand.is_file():
                continue
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "cpr_gate_advance_for_recompile", str(cand))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
            except Exception:
                continue
    return None


def resolve_recompile_tic(queue_path):
    """Canonical current tic for the recompile, read from the QUEUE's own zone.

    REUSED, not reimplemented: cpr-gate-advance.resolve_current_tic is the cured
    sibling in this same queue lane. Returns a positive int, or None when the tic
    log is absent/unreadable or the helper cannot be loaded. NEVER raises — a
    derived-cache clock must not fail a constitutional write.
    """
    mod = _sibling_clock_module()
    if mod is None:
        return None
    try:
        tic = mod.resolve_current_tic(Path(queue_path).parent.parent)
    except Exception:
        return None
    return tic if isinstance(tic, int) and tic > 0 else None


def recompile_effective_state(queue_file, current_tic=None):
    """Recompile the derived effective-state projection for THIS queue.

    Args:
        queue_file:  the queue the caller's mutation ACTUALLY wrote. Every zone
                     path below is derived from it and from nothing else.
        current_tic: optional explicit tic; resolved from the queue's own zone
                     when omitted.

    Returns:
        (ok: bool, detail: str). BEST-EFFORT BY CONTRACT: every failure path
        returns False with a typed reason and prints to stderr; nothing here
        raises into the caller, so a landed mutation stays landed.

    Typed failure details: `no_tic_resolvable:` · `compiler_not_found:` ·
    `recompile_error:` · `recompile_failed_rc=N:`. Success detail is
    `recompiled_at_tic=<N>`.
    """
    qp = Path(queue_file)
    if current_tic is None:
        current_tic = resolve_recompile_tic(qp)
    if current_tic is None:
        detail = (f"no_tic_resolvable: {qp.parent.parent / 'tics'} yielded no "
                  f"canonical tic (queue_state_compile requires --current-tic)")
        print(f"  ⚠ effective-state recompile SKIPPED — {detail}; the projection "
              f"is STALE until a tic-bearing rebuild (backstop: civil).",
              file=sys.stderr)
        return False, detail
    compile_script = qp.parent / "queue_state_compile.py"
    if not compile_script.is_file():
        detail = f"compiler_not_found: {compile_script}"
        print(f"  ⚠ effective-state recompile skipped — {detail}; projection "
              f"stale until the next rebuild (backstop: civil).", file=sys.stderr)
        return False, detail
    try:
        res = subprocess.run(
            [sys.executable, str(compile_script), "compile",
             "--queue", str(qp), "--out", str(qp.parent / "effective-state"),
             "--current-tic", str(current_tic)],
            capture_output=True, text=True, timeout=120)
    except Exception as exc:
        detail = f"recompile_error: {exc}"
        print(f"  ⚠ effective-state recompile error — {exc}; projection stale "
              f"until the next rebuild (backstop: civil).", file=sys.stderr)
        return False, detail
    if res.returncode != 0:
        tail = (res.stderr or res.stdout or "").strip()[:300]
        detail = f"recompile_failed_rc={res.returncode}: {tail}"
        print(f"  ⚠ effective-state recompile FAILED rc={res.returncode} — "
              f"projection stale until the next rebuild (backstop: civil): {tail}",
              file=sys.stderr)
        return False, detail
    return True, f"recompiled_at_tic={current_tic}"
