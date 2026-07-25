#!/usr/bin/env python3
"""
Review-lane test — bench-packet-prep load_queue PAYLOAD valve (M1 cure, tic 645).

The tic-523 C-3 cure fixed WHICH IDS surface (reconcile_surfaced_ids); its test
asserts only on the id set. This test proves WHICH ROW is read for an id —
the payload half. Bug M1 (conformance audit tic 645): `deferred` sat in
TERMINAL_STATUSES, so `terminal_entries[-1]` preferred a stale deferred row
over a chronologically later active row, handing /review predicate inputs
hundreds of tics stale (t256: 323 tics).

The cure keeps the HELD terminal enum intact (6+ readers share it) and corrects
the VALVE: `deferred` is SUSPENSIVE — canonical only while it is the id's
latest row. Any later row re-activates the id; a hard-terminal entry still
outranks everything.

Behaviours under test:
  1. RE-ACTIVATED: [extracted, deferred, enrichment_eligible] -> latest row wins
     (the M1 core; the live-queue shape of t256/t327/cpr_00c5...).
  2. PARKED: [extracted, deferred] (deferred latest) -> deferred row stands.
  3. HARD TERMINAL OUTRANKS: [deferred, extracted, promoted] -> promoted;
     [promoted, deferred, extracted] -> promoted (tic-183 masking cure holds).
  4. LIFECYCLE-SETTLED deferred row (lifecycle_state settled) followed by a
     later row -> the settled row stands (suspensive exception does not apply).
  5. STRAY RE-EXTRACTION after promoted -> promoted (original valve preserved).

Run: python3 tests/review/test_benchpacket_payload_valve.py
Exit 0 = PASS, 1 = FAIL.
"""

import importlib.util
import json
import sys
import tempfile
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


def _queue_file(rows):
    f = tempfile.NamedTemporaryFile(
        "w", suffix=".jsonl", delete=False, encoding="utf-8")
    for r in rows:
        f.write(json.dumps(r) + "\n")
    f.close()
    return f.name


def main():
    mod = _load_module()
    failures = []

    def check(name, rows, expect_status, expect_marker):
        path = _queue_file(rows)
        canonical = mod.load_queue(path)
        row = canonical.get("x")
        if row is None:
            failures.append(f"FAIL({name}): id missing from canonical view")
            return
        if row.get("status") != expect_status or row.get("m") != expect_marker:
            failures.append(
                f"FAIL({name}): got status={row.get('status')} m={row.get('m')} "
                f"expected status={expect_status} m={expect_marker}")

    # (1) RE-ACTIVATED — the M1 core: later active row must not be masked.
    check("reactivated", [
        {"id": "x", "status": "extracted", "m": 1},
        {"id": "x", "status": "deferred", "m": 2},
        {"id": "x", "status": "enrichment_eligible", "m": 3},
    ], "enrichment_eligible", 3)

    # (2) PARKED — deferred as latest row stands canonical.
    check("parked", [
        {"id": "x", "status": "extracted", "m": 1},
        {"id": "x", "status": "deferred", "m": 2},
    ], "deferred", 2)

    # (3) HARD TERMINAL OUTRANKS — both orderings.
    check("hard-terminal-late", [
        {"id": "x", "status": "deferred", "m": 1},
        {"id": "x", "status": "extracted", "m": 2},
        {"id": "x", "status": "promoted", "m": 3},
    ], "promoted", 3)
    check("hard-terminal-early", [
        {"id": "x", "status": "promoted", "m": 1},
        {"id": "x", "status": "deferred", "m": 2},
        {"id": "x", "status": "extracted", "m": 3},
    ], "promoted", 1)

    # (4) LIFECYCLE-SETTLED deferred — settled by lifecycle_state, not resumable.
    check("lifecycle-settled", [
        {"id": "x", "status": "deferred", "lifecycle_state": "suspensive", "m": 1},
        {"id": "x", "status": "extracted", "m": 2},
    ], "deferred", 1)

    # (5) STRAY RE-EXTRACTION after promoted — the original tic-183 cure holds.
    check("stray-reextraction", [
        {"id": "x", "status": "promoted", "m": 1},
        {"id": "x", "status": "extracted", "m": 2},
    ], "promoted", 1)

    if failures:
        print("BENCH-PACKET PAYLOAD-VALVE TEST: FAIL")
        for f in failures:
            print("  " + f)
        return 1

    print("BENCH-PACKET PAYLOAD-VALVE TEST: PASS")
    print("  (1) re-activated defer reads the later live row")
    print("  (2) parked defer stands while latest")
    print("  (3) hard terminal outranks in both orderings")
    print("  (4) lifecycle-settled suspensive row stands")
    print("  (5) stray re-extraction still masked by promoted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
