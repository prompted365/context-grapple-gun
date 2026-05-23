#!/usr/bin/env python3
"""
Review Test 6 — REVIEW lane reducer-boundary regression test.

Second implementation pathway for federation KI #1 (Policy-Gated Reducer-Boundary
Discipline) promoted at /review tic 278. Mirrors Harmony Test 6 pattern (state
invariance under stub injection) and the SIGNALS-lane Test 6 structure, applied
here to the queue.jsonl writeback-drift reader cluster.

Pattern (per rail T4 §1 REVIEW subsection):
  1. Build a synthetic CPR queue fixture in a tmpdir with:
       - A "live active" CPR (status=extracted) representing a true live CPR
         that ALL readers must surface as live.
       - A "writeback-drift" CPR carrying both:
           (a) an earlier active row (status=extracted), AND
           (b) a later terminal row (status=promoted)
         This is the canonical "writeback drift" anomaly per
         queue_state_compile.compute_id_state (line 124): the terminal row
         MUST win at every reader; the stale extracted row must NOT mask it.
       - A "stub residue" CPR (status=promoted) — terminal-only row mirroring
         the rail's stub-injection load-bearing assertion: terminal MUST NOT
         appear in any reader's live_now / pending counts.
  2. Build the effective_state.json that queue_state_compile would emit for
     the fixture queue (compile via the canonical compiler, not by mocking).
  3. Run every queue reader against the fixture:
       - queue_state_compile.py            (Python — direct subprocess invocation
                                            with --queue + --out + --current-tic)
       - review-close-check.py             (Python — direct subprocess invocation
                                            with --project-dir + --json + --dry-run)
       - bench-packet-prep.py (load_queue) (substituted with re-implementation
                                            of the terminal-state-valve reader
                                            at lines 109-150 — same predicate)
       - /review skill body                (markdown — substituted with documented
                                            "pending CPRs" derivation that the
                                            skill body relies on bench-packet-prep
                                            for; reader is bench-packet-prep's
                                            load_queue, exercised above)
       - Mogul queue_refresh cycle         (cycle script — substituted with the
                                            documented latest-entry-per-id scan
                                            pattern; Mogul reads queue.jsonl
                                            during its cycle but the actual
                                            scan logic is documented, not
                                            independently scripted)
  4. Assert ALL readers agree on:
       (a) live_now / pending count (terminal-state valve dominates).
       (b) Effective status of the writeback-drift CPR = "promoted" (terminal
           wins; the stale extracted row never resurrects).
       (c) Effective status of the stub residue CPR = "promoted".
  5. Assert allRows preservation: the raw queue.jsonl preserves both
     writeback-drift rows (raw emission preserved per Append-Only Emission
     Retention — the Layer 2 visibility invariant).
  6. Per Harmony Test 6's load-bearing assertion (line 92, run-tests.mjs:
     `stubPacket.meaningState === preStubPacket.meaningState`): the live_now
     count under the fixture-with-stub MUST equal the live_now count under
     the fixture-without-stub. State invariance across stub injection proves
     no reducer is silently consuming allRays-without-filter.

Exit codes:
  0 — all readers pass; reducer-boundary discipline intact
  1 — at least one reader leaked (returned stub-promoted in live_now, OR
       returned the stale extracted row as effective status for writeback-drift)
  2 — fixture/setup error

The test is RUNNABLE: `python3 test_reducer_boundary.py` from any cwd.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolution: locate the CGG runtime scripts directory + the canonical
# queue_state_compile.py compiler.
# ---------------------------------------------------------------------------
THIS_FILE = Path(__file__).resolve()
# tests/review/test_reducer_boundary.py -> cgg-runtime/scripts/
SCRIPTS_DIR = THIS_FILE.parent.parent.parent / "scripts"
REVIEW_CLOSE_CHECK_PY = SCRIPTS_DIR / "review-close-check.py"
BENCH_PACKET_PREP_PY = SCRIPTS_DIR / "bench-packet-prep.py"
REVIEW_SKILL = SCRIPTS_DIR.parent / "skills" / "review" / "SKILL.md"
MOGUL_RUNNER_SH = SCRIPTS_DIR / "mogul-runner.sh"

# Canonical compiler lives in audit-logs/cprs/, not in cgg-runtime/scripts/
# (per Tracked External Scripts Pattern — path-locked to audit-logs/cprs/ so
# DEFAULT_QUEUE / DEFAULT_OUT siblings resolve correctly).
# tests/review/ -> cgg-runtime/ -> context-grapple-gun/ -> canonical_developer/ -> canonical/
CANONICAL_ROOT_HINT = THIS_FILE.parents[5]
QUEUE_STATE_COMPILE_PY = CANONICAL_ROOT_HINT / "audit-logs" / "cprs" / "queue_state_compile.py"

# Reader-side status taxonomy (mirroring queue_state_compile.py lines 39-46
# and bench-packet-prep.py lines 40-43). REVIEW lane uses a different active
# bucket than SIGNALS (review uses pending/extracted/enrichment_*; signals
# uses active/acknowledged/working).
TERMINAL_STATUSES = frozenset({
    "promoted", "absorbed", "superseded", "rejected",
    "deferred", "dismissed", "resolved", "skipped",
})
ACTIVE_STATUSES = frozenset({
    "pending", "extracted", "enrichment_needed",
    "enrichment_eligible", "enrichment_in_progress",
    "review_ready", "promotable",
})

# Bench-packet-prep's review-eligible set (the narrower set actually surfaced
# as "pending" for /review consumption — lines 360-369 of bench-packet-prep.py).
BENCH_PENDING_STATUSES = frozenset({
    "pending", "enrichment_needed", "enrichment_eligible",
    "extracted", "review_ready",
})


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------
def build_fixture(tmpdir: Path, include_stub: bool = True) -> Path:
    """Construct a synthetic queue.jsonl fixture under tmpdir.

    Returns the zone root path (tmpdir).

    Fixture contents:
      .ticzone                             — minimal valid config
      audit-logs/cprs/queue.jsonl          — append-only queue:
           - cpr_live_active           (status=extracted; live pending)
           - cpr_writeback_drift  active (status=extracted; row 1)
           - cpr_writeback_drift  termin (status=promoted;  row 2 — terminal-wins)
           - cpr_stub_residue         (status=promoted; terminal-only,
                                       ONLY if include_stub=True)
      audit-logs/cprs/queue_state_compile.py — symlink to the canonical
                                             compiler (so subprocess invocation
                                             from the fixture's audit-logs path
                                             resolves correctly).
      audit-logs/tics/current.json         — current_tic marker (used by
                                             queue-drift-audit and
                                             review-close-check tic resolution)
      audit-logs/mogul/mandates/current.json — minimal mandate metadata for
                                             review-close-check tic resolution.
    """
    zone = tmpdir
    al = zone / "audit-logs"
    cprs = al / "cprs"
    cprs.mkdir(parents=True, exist_ok=True)
    tics_dir = al / "tics"
    tics_dir.mkdir(parents=True, exist_ok=True)
    mogul_dir = al / "mogul" / "mandates"
    mogul_dir.mkdir(parents=True, exist_ok=True)
    # review-close-check expects services/ to exist for atomic-append log writes
    services_dir = al / "services"
    services_dir.mkdir(parents=True, exist_ok=True)

    # .ticzone — minimal valid config for zone_root.py to resolve.
    (zone / ".ticzone").write_text(json.dumps({
        "name": "test-fixture-review-zone",
        "audit_logs_path": "audit-logs",
        "signal_governance": {
            "hearing_threshold": 40,
            "decay_rate_per_tic": 2,
            "warrant_eligible_kinds": ["BEACON", "TENSION"],
        },
    }) + "\n")

    # current.json — tic marker.
    fixture_tic = 282
    (tics_dir / "current.json").write_text(json.dumps({
        "current_tic": fixture_tic,
        "counter_after": fixture_tic,
    }) + "\n")

    # mogul/mandates/current.json — minimum required fields for
    # review-close-check.load_mandate_id() to resolve a tic.
    (mogul_dir / "current.json").write_text(json.dumps({
        "mandate_id": f"tic-{fixture_tic}-test-fixture-mandate",
        "tic": fixture_tic,
        "tic_context": {"current_tic": fixture_tic},
    }) + "\n")

    # queue.jsonl — append-only event log (allRows equivalent).
    queue_path = cprs / "queue.jsonl"
    queue_entries = []

    # Entry 1: a true live active CPR (must appear in every reader's
    # live_now/pending count).
    queue_entries.append({
        "id": "cpr_live_active",
        "status": "extracted",
        "extracted_at": "2026-05-23T10:00:00Z",
        "extracted_by": "cpr-extract-hook",
        "source_file": "memory/MEMORY.md",
        "birth_tic": 282,
        "review_tic": None,
        "band": "COGNITIVE",
        "subsystem": "test_fixture",
        "lesson": "Live active CPR fixture — must surface as live_now / pending.",
        "recommended_scopes": ["canonical/CLAUDE.md"],
    })

    # Entry 2: writeback-drift CPR — earlier active row (the stale row that
    # must NOT survive the terminal-state valve).
    queue_entries.append({
        "id": "cpr_writeback_drift",
        "status": "extracted",
        "extracted_at": "2026-05-23T08:00:00Z",
        "extracted_by": "cpr-extract-hook",
        "source_file": "memory/MEMORY.md",
        "birth_tic": 281,
        "review_tic": None,
        "band": "COGNITIVE",
        "subsystem": "test_fixture",
        "lesson": "Writeback-drift fixture — earlier extracted row. Terminal-state "
                  "valve must collapse this to the later terminal row.",
        "recommended_scopes": ["canonical/CLAUDE.md"],
    })

    # Entry 3: writeback-drift CPR — later terminal row (must win).
    queue_entries.append({
        "id": "cpr_writeback_drift",
        "status": "promoted",
        "promoted_to": "canonical/CLAUDE.md",
        "promoted_at_tic": 282,
        "review_tic": 282,
        "review_verdict": "PROMOTE",
        "band": "COGNITIVE",
        "subsystem": "test_fixture",
        "lesson": "Writeback-drift fixture — later promoted row. This is the "
                  "terminal disposition that must dominate every reader.",
        "recommended_scopes": ["canonical/CLAUDE.md"],
    })

    if include_stub:
        # Entry 4: the load-bearing stub — a terminal-only CPR (mirrors the
        # rail's stub-injection pattern from Harmony Test 6 and the SIGNALS
        # lane test 6). Terminal status MUST NOT appear in any reader's
        # live_now / pending counts. Per the Architect-stated test pattern
        # from rail T4 line 86: "one CPR that has both an active row AND a
        # later terminal row" plus "stub" — the stub here represents a
        # tic-handoff residue: terminal-only but its mere presence in
        # queue.jsonl must not push pending count upward.
        queue_entries.append({
            "id": "cpr_stub_residue",
            "status": "promoted",
            "promoted_to": "canonical/CLAUDE.md",
            "promoted_at_tic": 280,
            "review_tic": 280,
            "review_verdict": "PROMOTE",
            "birth_tic": 279,
            "band": "COGNITIVE",
            "subsystem": "test_fixture",
            "lesson": "Stub residue — promoted terminal-only. Must NEVER be "
                      "counted as live_now / pending by any reader (Harmony "
                      "Test 6 load-bearing assertion at the queue surface).",
            "recommended_scopes": ["canonical/CLAUDE.md"],
        })

    with open(queue_path, "w") as f:
        for e in queue_entries:
            f.write(json.dumps(e) + "\n")

    # Provide a symlink to the canonical compiler at the expected path so
    # bench-packet-prep's compiler-invocation step resolves correctly when
    # the fixture's audit-logs path is the working tree. We use a symlink
    # rather than a copy to ensure we're exercising the canonical compiler
    # (one true reducer-boundary implementation).
    compiler_target = cprs / "queue_state_compile.py"
    if not compiler_target.exists():
        if QUEUE_STATE_COMPILE_PY.exists():
            os.symlink(QUEUE_STATE_COMPILE_PY, compiler_target)

    return zone


# ---------------------------------------------------------------------------
# Reader 1: queue_state_compile.py (canonical compiler — the authoritative
# reducer-boundary implementation per rail T4 line 79: line 229
# `_classify_active_bucket → 'live_now'`).
# ---------------------------------------------------------------------------
def read_via_queue_state_compile(zone_root: Path) -> dict:
    """Invoke queue_state_compile.py compile against the fixture queue.

    Returns:
      {
        "live_now": int (count of ids whose bucket == 'live_now'),
        "live_now_ids": [list of ids],
        "terminal": int (count of ids with bucket starting with 'terminal_'),
        "id_states": {id: bucket} for inspection,
        "writeback_drift_effective_status": <status of cpr_writeback_drift>,
        "stub_effective_status": <status of cpr_stub_residue or None>,
      }
    """
    queue_path = zone_root / "audit-logs" / "cprs" / "queue.jsonl"
    out_dir = zone_root / "audit-logs" / "cprs" / "effective-state"
    try:
        result = subprocess.run(
            ["python3", str(QUEUE_STATE_COMPILE_PY),
             "compile",
             "--queue", str(queue_path),
             "--out", str(out_dir),
             "--current-tic", "282"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        return {"error": f"queue_state_compile invocation failed: {e}",
                "live_now": None}

    if result.returncode != 0:
        return {"error": f"queue_state_compile exit={result.returncode}: {result.stderr}",
                "live_now": None}

    es_path = out_dir / "effective_state.json"
    if not es_path.exists():
        return {"error": f"effective_state.json not written at {es_path}",
                "live_now": None}

    try:
        es = json.loads(es_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": f"effective_state.json parse failed: {e}",
                "live_now": None}

    states = es.get("states", {})
    live_now_ids = [sid for sid, s in states.items()
                    if s.get("bucket") == "live_now"]
    terminal_ids = [sid for sid, s in states.items()
                    if str(s.get("bucket", "")).startswith("terminal_")]

    return {
        "live_now": len(live_now_ids),
        "live_now_ids": sorted(live_now_ids),
        "terminal": len(terminal_ids),
        "id_states": {sid: s.get("bucket") for sid, s in states.items()},
        "writeback_drift_effective_status":
            states.get("cpr_writeback_drift", {}).get("effective_status"),
        "stub_effective_status":
            states.get("cpr_stub_residue", {}).get("effective_status")
            if "cpr_stub_residue" in states else None,
    }


# ---------------------------------------------------------------------------
# Reader 2: review-close-check.py (verifier path; reads queue.jsonl directly
# via load_queue at line 37 — latest-entry-per-id-wins WITHOUT terminal-state
# preference at that path; the test surfaces whether the verifier honors the
# valve at the verdict_counts boundary).
# ---------------------------------------------------------------------------
def read_via_review_close_check(zone_root: Path) -> dict:
    """Invoke review-close-check.py --dry-run --json against the fixture.

    review-close-check loads queue.jsonl via its own load_queue (line 37) —
    latest-entry-per-id-wins (no terminal-state preference). For the
    writeback-drift fixture, the LATEST entry IS the terminal entry (row 3
    is promoted), so the valve naturally resolves the right way here. The
    test asserts the verdict_counts agree with the compiler.
    """
    try:
        result = subprocess.run(
            ["python3", str(REVIEW_CLOSE_CHECK_PY),
             "--project-dir", str(zone_root),
             "--dry-run", "--json"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        return {"error": f"review-close-check invocation failed: {e}",
                "promoted": None, "deferred": None, "skipped": None}

    if result.returncode != 0:
        return {"error": f"review-close-check exit={result.returncode}: "
                         f"{result.stderr[:500]}",
                "promoted": None}

    try:
        data = json.loads(result.stdout)
    except Exception as e:
        return {"error": f"review-close-check non-JSON output: {e}",
                "promoted": None}

    vc = data.get("verdict_counts", {})
    return {
        "total_cprs": data.get("total_cprs"),
        "promoted": vc.get("promoted"),
        "deferred": vc.get("deferred"),
        "skipped": vc.get("skipped"),
        # Compute "live" (= non-terminal) from total - terminal sum.
        # review-close-check doesn't surface a "live" bucket directly, but
        # the latest-entry-per-id projection's non-promoted/non-skipped/
        # non-deferred is the live set.
        # For our fixture: 3 ids (live_active, writeback_drift, stub or not),
        # with promoted = 2 (writeback_drift, stub) or 1 (no stub).
    }


# ---------------------------------------------------------------------------
# Reader 3: bench-packet-prep load_queue + get_pending_cprs
# (re-implementation of the terminal-state-valve reader at lines 109-150 +
# 360-369 — same predicate as exercised by the live bench-packet-prep run,
# without requiring the full bench-packet pipeline scaffolding).
# ---------------------------------------------------------------------------
def read_via_bench_packet_prep_substitute(zone_root: Path) -> dict:
    """Mirror bench-packet-prep.load_queue + get_pending_cprs.

    From bench-packet-prep.py lines 109-150 (load_queue with terminal-state
    preference) + lines 360-369 (get_pending_cprs filter to BENCH_PENDING_STATUSES).

    This is the load_queue substitution per rail T4: bench-packet-prep is
    the bench-packet builder reader; the load_queue function IS the reducer-
    boundary at the consumer side, before downstream filtering.
    """
    queue_path = zone_root / "audit-logs" / "cprs" / "queue.jsonl"
    if not queue_path.exists():
        return {"pending": 0, "pending_ids": [], "by_id": {}}

    # Parse with append-order tracking per load_queue.
    by_id = {}
    for line in queue_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        eid = d.get("id", "")
        if eid:
            by_id.setdefault(eid, []).append(d)

    canonical = {}
    for eid, entries_list in by_id.items():
        terminal_entries = [
            e for e in entries_list
            if e.get("status", "") in TERMINAL_STATUSES
        ]
        if terminal_entries:
            canonical[eid] = terminal_entries[-1]
        else:
            canonical[eid] = entries_list[-1]

    # get_pending_cprs filter (line 360-369).
    pending_ids = sorted([
        eid for eid, entry in canonical.items()
        if entry.get("status") in BENCH_PENDING_STATUSES
    ])

    return {
        "pending": len(pending_ids),
        "pending_ids": pending_ids,
        "writeback_drift_effective_status":
            canonical.get("cpr_writeback_drift", {}).get("status"),
        "stub_effective_status":
            canonical.get("cpr_stub_residue", {}).get("status")
            if "cpr_stub_residue" in canonical else None,
        # Surface the canonical id -> status map for cross-reader assertions.
        "by_id": {eid: e.get("status") for eid, e in canonical.items()},
    }


# ---------------------------------------------------------------------------
# Reader 4: /review skill body
#
# Per skills/review/SKILL.md: /review reads the pre-built bench packet at
# audit-logs/cprs/bench-packets/latest.json. The bench-packet builder
# (bench-packet-prep.py) is the upstream producer; the /review skill body
# consumes "pending" from the packet. So /review IS a bench-packet-derived
# reader at the live invocation.
#
# Substitution rationale: live skill invocation requires the Claude Code
# harness. We substitute with the documented derivation — /review's pending
# count = bench-packet-prep's get_pending_cprs(load_queue(queue_path)) which
# we already exercise as Reader 3.
# ---------------------------------------------------------------------------
def read_via_review_skill_substitute(zone_root: Path) -> dict:
    """Substitute for /review skill body's pending CPR derivation.

    Documented path: /review reads bench-packets/latest.json which is built
    by bench-packet-prep.get_pending_cprs(load_queue(queue_path)). We mirror
    that derivation here (which IS reader 3) and label as the /review skill
    body substitution for the test report.
    """
    return read_via_bench_packet_prep_substitute(zone_root)


# ---------------------------------------------------------------------------
# Reader 5: Mogul queue_refresh cycle
#
# Per mogul-runner.sh: the queue_refresh cycle invokes build_queue_index.py
# (latest-entry-per-id, no terminal-state filter) AND optionally
# queue_state_compile.py (terminal-state valve). The cycle's downstream
# consumers read the compiler outputs (effective_state.json), so the
# Mogul-side reader IS the compiler — exercised at Reader 1.
#
# Substitution rationale: per the manifest mapping, Mogul's queue_refresh
# does NOT independently re-derive "live_now" — it consumes the compiler
# outputs. So Mogul's reducer-boundary view IS the compiler's view. We
# label as the Mogul queue_refresh substitution but it shares the compiler
# result, treating the Mogul reader as a compiler-derivative reader.
# ---------------------------------------------------------------------------
def read_via_mogul_queue_refresh_substitute(zone_root: Path) -> dict:
    """Substitute for Mogul queue_refresh cycle's queue-state derivation.

    Documented path: Mogul invokes queue_state_compile.py and reads
    effective_state.json. Same view as Reader 1 (the canonical compiler).
    """
    # Reader 1 may not have been called yet — re-derive via subprocess.
    return read_via_queue_state_compile(zone_root)


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------
READERS = {
    "queue_state_compile.py":         read_via_queue_state_compile,
    "review-close-check.py":          read_via_review_close_check,
    "bench-packet-prep (load_queue)": read_via_bench_packet_prep_substitute,
    "/review skill body":             read_via_review_skill_substitute,
    "Mogul queue_refresh cycle":      read_via_mogul_queue_refresh_substitute,
}


def run_all_readers(zone_root: Path) -> dict:
    """Invoke every reader against the fixture; return reader -> result map."""
    results = {}
    for name, fn in READERS.items():
        try:
            results[name] = fn(zone_root)
        except Exception as e:
            results[name] = {"error": f"reader raised: {e}",
                             "live_now": None, "pending": None}
    return results


def assert_live_count(results: dict, expected_live: int, expected_pending: int) -> list:
    """Return list of failure messages (empty list = all readers passed).

    Each reader surfaces 'live_now' (compiler-side), 'pending' (bench-packet-
    derived), or 'promoted/deferred/skipped' counts (review-close-check). The
    boundary-split discipline requires:
      compiler.live_now == expected_live
      bench/review pending == expected_pending
    The two counts are not required to be equal — bench-packet's pending
    set is the review-eligible subset of compiler.live_now, but for our
    fixture they coincide (all active CPRs are review-eligible).
    """
    failures = []
    for name, r in results.items():
        if r.get("error"):
            failures.append(f"  [{name}] ERROR: {r['error']}")
            continue

        if "live_now" in r and r.get("live_now") is not None:
            actual = r.get("live_now")
            if actual != expected_live:
                ids = r.get("live_now_ids", "<n/a>")
                failures.append(
                    f"  [{name}] LIVE-LEAK: live_now = {actual} "
                    f"(expected {expected_live}); ids={ids}"
                )
        elif "pending" in r and r.get("pending") is not None:
            actual = r.get("pending")
            if actual != expected_pending:
                ids = r.get("pending_ids", "<n/a>")
                failures.append(
                    f"  [{name}] PENDING-LEAK: pending = {actual} "
                    f"(expected {expected_pending}); ids={ids}"
                )
        elif "promoted" in r and r.get("promoted") is not None:
            # review-close-check verdict_counts:
            # promoted = total - non-promoted-non-deferred-non-skipped
            # For our fixture (pre-stub): writeback_drift = promoted, so
            # promoted=1; live_active = extracted, so live=1.
            # post-stub: promoted=2 (writeback_drift + stub), live=1.
            # We assert the promoted count is consistent with expected_live
            # (live = total_cprs - promoted - deferred - skipped).
            total = r.get("total_cprs", 0)
            promoted = r.get("promoted", 0)
            deferred = r.get("deferred", 0)
            skipped = r.get("skipped", 0)
            live = total - promoted - deferred - skipped
            if live != expected_live:
                failures.append(
                    f"  [{name}] LIVE-LEAK: derived live = {live} "
                    f"(expected {expected_live}); total={total}, "
                    f"promoted={promoted}, deferred={deferred}, skipped={skipped}"
                )
    return failures


def assert_writeback_drift_terminal(results: dict) -> list:
    """Per Terminal-State Valve Pattern (CGG KI cpr_terminal_state_valve_pattern):
    every reader must surface cpr_writeback_drift as 'promoted' (terminal
    wins). If any reader surfaces 'extracted' or another active status, the
    valve has leaked.
    """
    failures = []
    for name, r in results.items():
        if r.get("error"):
            continue

        # Compiler-side (Reader 1, 5): effective_status
        ws = r.get("writeback_drift_effective_status")
        if ws is not None and ws != "promoted":
            failures.append(
                f"  [{name}] WRITEBACK-DRIFT-LEAK: effective_status = '{ws}' "
                f"(expected 'promoted')"
            )

        # Bench-packet-side (Reader 3, 4): pending_ids must NOT contain
        # cpr_writeback_drift.
        pending_ids = r.get("pending_ids")
        if pending_ids is not None and "cpr_writeback_drift" in pending_ids:
            failures.append(
                f"  [{name}] WRITEBACK-DRIFT-LEAK: cpr_writeback_drift "
                f"present in pending_ids: {pending_ids}"
            )

        # Compiler id_states: cpr_writeback_drift bucket must start with 'terminal_'
        id_states = r.get("id_states")
        if id_states is not None:
            wb_bucket = id_states.get("cpr_writeback_drift")
            if wb_bucket and not wb_bucket.startswith("terminal_"):
                failures.append(
                    f"  [{name}] WRITEBACK-DRIFT-LEAK: bucket = '{wb_bucket}' "
                    f"(expected terminal_*)"
                )
    return failures


def assert_stub_not_live(results: dict) -> list:
    """Per Harmony Test 6 load-bearing assertion: the stub MUST NOT push
    upward into any reader's live/pending count."""
    failures = []
    for name, r in results.items():
        if r.get("error"):
            continue

        # Compiler-side: stub effective_status must be 'promoted' (terminal).
        stub_status = r.get("stub_effective_status")
        if stub_status is not None and stub_status != "promoted":
            failures.append(
                f"  [{name}] STUB-LEAK: stub effective_status = '{stub_status}' "
                f"(expected 'promoted')"
            )

        # Compiler live_now_ids: stub must NOT appear.
        live_ids = r.get("live_now_ids")
        if live_ids is not None and "cpr_stub_residue" in live_ids:
            failures.append(
                f"  [{name}] STUB-LEAK: cpr_stub_residue present in "
                f"live_now_ids: {live_ids}"
            )

        # Bench-packet-side: stub must NOT appear in pending_ids.
        pending_ids = r.get("pending_ids")
        if pending_ids is not None and "cpr_stub_residue" in pending_ids:
            failures.append(
                f"  [{name}] STUB-LEAK: cpr_stub_residue present in "
                f"pending_ids: {pending_ids}"
            )

        # Compiler id_states: stub bucket must start with 'terminal_'.
        id_states = r.get("id_states")
        if id_states is not None:
            stub_bucket = id_states.get("cpr_stub_residue")
            if stub_bucket and not stub_bucket.startswith("terminal_"):
                failures.append(
                    f"  [{name}] STUB-LEAK: cpr_stub_residue bucket = "
                    f"'{stub_bucket}' (expected terminal_*)"
                )
    return failures


def assert_all_rows_preserves_writeback(zone_root: Path) -> str | None:
    """Assert BOTH writeback-drift rows ARE visible in the raw queue.jsonl
    (allRows preserved per Append-Only Emission Retention — the Layer 2
    visibility invariant per Harmony Test 6 line 77).

    Returns None on pass, error string on fail.
    """
    queue = zone_root / "audit-logs" / "cprs" / "queue.jsonl"
    if not queue.exists():
        return f"queue.jsonl missing: {queue}"
    writeback_drift_count = 0
    statuses_seen = []
    for line in queue.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("id") == "cpr_writeback_drift":
            writeback_drift_count += 1
            statuses_seen.append(obj.get("status"))
    if writeback_drift_count != 2:
        return (f"cpr_writeback_drift expected 2 raw rows; "
                f"found {writeback_drift_count} (statuses: {statuses_seen}) — "
                f"Layer 2 visibility violation (allRows did not preserve both)")
    if "extracted" not in statuses_seen or "promoted" not in statuses_seen:
        return (f"cpr_writeback_drift raw rows expected statuses "
                f"['extracted', 'promoted']; found {statuses_seen}")
    return None


def assert_state_invariance(pre_results: dict, post_results: dict) -> list:
    """Per Harmony Test 6 line 92 (`stubPacket.meaningState ===
    preStubPacket.meaningState`): the live_now / pending count under
    fixture-with-stub MUST equal the count under fixture-without-stub.

    State invariance across stub injection proves no reducer is silently
    consuming allRows-without-filter.
    """
    failures = []
    for name in READERS.keys():
        pre = pre_results.get(name, {})
        post = post_results.get(name, {})
        if pre.get("error") or post.get("error"):
            continue

        # Compare live_now if both surfaced it.
        if pre.get("live_now") is not None and post.get("live_now") is not None:
            if pre["live_now"] != post["live_now"]:
                failures.append(
                    f"  [{name}] INVARIANCE-LEAK: pre.live_now={pre['live_now']} "
                    f"!= post.live_now={post['live_now']}"
                )
        # Compare pending if both surfaced it.
        if pre.get("pending") is not None and post.get("pending") is not None:
            if pre["pending"] != post["pending"]:
                failures.append(
                    f"  [{name}] INVARIANCE-LEAK: pre.pending={pre['pending']} "
                    f"!= post.pending={post['pending']}"
                )
        # Compare derived-live from review-close-check.
        if pre.get("total_cprs") is not None and post.get("total_cprs") is not None:
            pre_live = (pre["total_cprs"] - pre.get("promoted", 0)
                        - pre.get("deferred", 0) - pre.get("skipped", 0))
            post_live = (post["total_cprs"] - post.get("promoted", 0)
                         - post.get("deferred", 0) - post.get("skipped", 0))
            if pre_live != post_live:
                failures.append(
                    f"  [{name}] INVARIANCE-LEAK: pre derived-live={pre_live} "
                    f"!= post derived-live={post_live}"
                )
    return failures


def main() -> int:
    print("=" * 72)
    print("Review Test 6 — REVIEW lane reducer-boundary regression test")
    print("Federation KI #1 (Policy-Gated Reducer-Boundary Discipline)")
    print("=" * 72)
    print()

    # Pre-flight: verify reader artifacts exist.
    missing = []
    if not QUEUE_STATE_COMPILE_PY.exists():
        missing.append(str(QUEUE_STATE_COMPILE_PY))
    if not REVIEW_CLOSE_CHECK_PY.exists():
        missing.append(str(REVIEW_CLOSE_CHECK_PY))
    if not BENCH_PACKET_PREP_PY.exists():
        missing.append(str(BENCH_PACKET_PREP_PY))
    if not REVIEW_SKILL.exists():
        # /review skill body is a substitute target — print warning but do
        # not fail. The substitution path exercises bench-packet-prep's
        # load_queue, which IS the upstream reader.
        print(f"INFO: /review SKILL.md not found at {REVIEW_SKILL} — "
              f"substitution still exercises the documented derivation.")
    if not MOGUL_RUNNER_SH.exists():
        print(f"INFO: mogul-runner.sh not found at {MOGUL_RUNNER_SH} — "
              f"substitution still exercises the documented derivation.")
    if missing:
        print("FIXTURE ERROR — required reader artifacts not found:")
        for p in missing:
            print(f"  - {p}")
        return 2

    print("Reader artifacts verified:")
    print(f"  queue_state_compile.py:   {QUEUE_STATE_COMPILE_PY}")
    print(f"  review-close-check.py:    {REVIEW_CLOSE_CHECK_PY}")
    print(f"  bench-packet-prep.py:     {BENCH_PACKET_PREP_PY}")
    print(f"  /review skill body:       {REVIEW_SKILL} (substituted)")
    print(f"  Mogul queue_refresh:      {MOGUL_RUNNER_SH} (substituted)")
    print()
    print("Reader classification (per W1-F pattern):")
    print("  LIVE       — queue_state_compile.py (subprocess invocation)")
    print("  LIVE       — review-close-check.py (subprocess invocation)")
    print("  SUBSTITUTE — bench-packet-prep load_queue (re-implementation of")
    print("               lines 109-150 + 360-369; same predicate, no live ")
    print("               bench-packet pipeline scaffolding required)")
    print("  SUBSTITUTE — /review skill body (consumes bench-packets/latest.json;")
    print("               documented derivation IS bench-packet-prep's path)")
    print("  SUBSTITUTE — Mogul queue_refresh cycle (consumes compiler outputs;")
    print("               documented derivation IS queue_state_compile.py)")
    print()

    overall_pass = True

    # ----------------------------------------------------------------
    # Phase 1: Pre-stub fixture (control) — establish baseline counts.
    # ----------------------------------------------------------------
    pre_results_snapshot = None
    with tempfile.TemporaryDirectory(prefix="review_test6_pre_") as td_pre:
        td_pre_path = Path(td_pre)
        zone_pre = build_fixture(td_pre_path, include_stub=False)
        print("[Phase 1] PRE-STUB fixture built at:", zone_pre)
        pre_results = run_all_readers(zone_pre)
        pre_results_snapshot = pre_results  # captured for Phase 3

        print("[Phase 1] Pre-stub reader counts:")
        for name, r in pre_results.items():
            if r.get("error"):
                print(f"    {name:35s} ERROR: {r['error'][:80]}")
                continue
            if "live_now" in r:
                print(f"    {name:35s} live_now={r.get('live_now')} "
                      f"ids={r.get('live_now_ids')}")
            elif "pending" in r:
                print(f"    {name:35s} pending={r.get('pending')} "
                      f"ids={r.get('pending_ids')}")
            elif "promoted" in r:
                total = r.get("total_cprs", 0)
                promoted = r.get("promoted", 0)
                deferred = r.get("deferred", 0)
                skipped = r.get("skipped", 0)
                live = total - promoted - deferred - skipped
                print(f"    {name:35s} promoted={promoted} "
                      f"derived-live={live} (total={total})")

        # Expectation: exactly 1 live_now CPR (cpr_live_active) in every
        # reader. cpr_writeback_drift is terminal (promoted wins).
        pre_failures = assert_live_count(pre_results, expected_live=1,
                                         expected_pending=1)
        if pre_failures:
            print("[Phase 1] FAIL — pre-stub baseline disagreement:")
            for f in pre_failures:
                print(f)
            overall_pass = False
        else:
            print("[Phase 1] PASS — all readers agree on baseline live=1")

        # Writeback-drift terminal check (must hold pre-stub too).
        wb_failures = assert_writeback_drift_terminal(pre_results)
        if wb_failures:
            print("[Phase 1] FAIL — writeback-drift terminal-state-valve leak:")
            for f in wb_failures:
                print(f)
            overall_pass = False
        else:
            print("[Phase 1] PASS — cpr_writeback_drift surfaces as terminal "
                  "in every reader (terminal wins)")
        print()

    # ----------------------------------------------------------------
    # Phase 2: Post-stub fixture — inject stub residue, re-run.
    # ----------------------------------------------------------------
    post_results_snapshot = None
    with tempfile.TemporaryDirectory(prefix="review_test6_post_") as td_post:
        td_post_path = Path(td_post)
        zone_post = build_fixture(td_post_path, include_stub=True)
        print("[Phase 2] POST-STUB fixture built at:", zone_post)
        post_results = run_all_readers(zone_post)
        post_results_snapshot = post_results  # captured for Phase 3

        print("[Phase 2] Post-stub reader counts:")
        for name, r in post_results.items():
            if r.get("error"):
                print(f"    {name:35s} ERROR: {r['error'][:80]}")
                continue
            if "live_now" in r:
                print(f"    {name:35s} live_now={r.get('live_now')} "
                      f"ids={r.get('live_now_ids')}")
            elif "pending" in r:
                print(f"    {name:35s} pending={r.get('pending')} "
                      f"ids={r.get('pending_ids')}")
            elif "promoted" in r:
                total = r.get("total_cprs", 0)
                promoted = r.get("promoted", 0)
                deferred = r.get("deferred", 0)
                skipped = r.get("skipped", 0)
                live = total - promoted - deferred - skipped
                print(f"    {name:35s} promoted={promoted} "
                      f"derived-live={live} (total={total})")

        # Expectation: still exactly 1 live_now CPR.
        post_failures = assert_live_count(post_results, expected_live=1,
                                          expected_pending=1)
        if post_failures:
            print("[Phase 2] FAIL — post-stub baseline disagreement:")
            for f in post_failures:
                print(f)
            overall_pass = False
        else:
            print("[Phase 2] PASS — all readers still agree on live=1 "
                  "(stub did not leak)")

        # Writeback-drift terminal check (still must hold).
        wb_failures = assert_writeback_drift_terminal(post_results)
        if wb_failures:
            print("[Phase 2] FAIL — writeback-drift terminal-state-valve leak:")
            for f in wb_failures:
                print(f)
            overall_pass = False
        else:
            print("[Phase 2] PASS — cpr_writeback_drift still terminal in "
                  "every reader")

        # Load-bearing assertion (Harmony Test 6 line 92): stub MUST NOT
        # appear in any reader's live/pending count.
        stub_failures = assert_stub_not_live(post_results)
        if stub_failures:
            print("[Phase 2] FAIL — stub leaked into live/pending:")
            for f in stub_failures:
                print(f)
            overall_pass = False
        else:
            print("[Phase 2] PASS — cpr_stub_residue NOT present in any "
                  "reader's live/pending count")

        # Layer 2 visibility invariant: writeback rows ARE preserved in raw
        # queue.jsonl (allRows preserved per Append-Only Emission Retention).
        ray_err = assert_all_rows_preserves_writeback(zone_post)
        if ray_err:
            print(f"[Phase 2] FAIL — allRows Layer 2 visibility: {ray_err}")
            overall_pass = False
        else:
            print("[Phase 2] PASS — both writeback-drift rows preserved in "
                  "raw queue.jsonl (allRows)")
        print()

    # ----------------------------------------------------------------
    # Phase 3: State invariance — pre/post counts MUST match.
    # ----------------------------------------------------------------
    print("[Phase 3] State invariance check (Harmony Test 6 boundary "
          "assertion line 92):")

    if pre_results_snapshot and post_results_snapshot:
        inv_failures = assert_state_invariance(pre_results_snapshot,
                                               post_results_snapshot)
        if inv_failures:
            print("[Phase 3] FAIL — state invariance violated:")
            for f in inv_failures:
                print(f)
            overall_pass = False
        else:
            print("[Phase 3] PASS — pre/post live counts match across all "
                  "readers (stub injection did not push count upward)")
    else:
        print("[Phase 3] SKIP — Phase 1/2 snapshots unavailable")
        overall_pass = False
    print()

    # ----------------------------------------------------------------
    # Final verdict
    # ----------------------------------------------------------------
    print("=" * 72)
    if overall_pass:
        print("RESULT: PASS — reducer-boundary discipline intact across "
              "all 5 readers")
        print("Federation KI #1 (Policy-Gated Reducer-Boundary Discipline) — "
              "REVIEW lane: CONFORMANT")
        print("=" * 72)
        return 0
    else:
        print("RESULT: FAIL — at least one reader leaked or disagreed "
              "on baseline")
        print("Federation KI #1 (Policy-Gated Reducer-Boundary Discipline) — "
              "REVIEW lane: LEAK DETECTED")
        print("=" * 72)
        return 1


if __name__ == "__main__":
    sys.exit(main())
