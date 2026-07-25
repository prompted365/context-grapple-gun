#!/usr/bin/env python3
"""
Review-lane test — null-birth_tic reader safety in the mirror pair (tic 646).

The M1 payload-valve cure (tic 645) correctly surfaces re-activated live rows
— and some live rows carry `birth_tic: null` EXPLICITLY (t327/C3's live
`enrichment_eligible` row does). A `dict.get(key, default)` only covers ABSENT
keys; an explicit null sails through as None and poisons numeric sorts and
comparisons. First fired live at tic 646: bench-packet-prep's dossier sort
(`sorted(..., key=lambda x: x[1].get("birth_tic", 0))`) crashed with
`TypeError: '<' not supported between instances of 'NoneType' and 'int'`
on the first post-cure lane regeneration. ripple-assessor carried the same
footgun at its maturity gate (`birth_tic > 0` with a `.get(..., 0)` read) —
the named-footgun-sibling law applied per the declared mirror contract.

The cure coalesces explicit null to the established absent-sentinel 0
(`.get("birth_tic") or 0`) at every birth_tic read in both readers;
maturity_tics keeps an is-None check because 0 would be meaningful there.

Behaviours under test:
  1. BENCH END-TO-END: build_bench_packet over a minimal zone (DEGRADED
     compiler fallback) whose queue mixes int / explicit-null / absent
     birth_tic rows — must not crash; null and absent both read as 0 and
     sort before the int row.
  2. RIPPLE MATURITY GATE: classify_cpr_readiness with birth_tic=None must
     not crash and must NOT tic-gate (null provenance == no maturity gate,
     same as the 0-sentinel).
  3. RIPPLE 0-SENTINEL PARITY: birth_tic=0 and birth_tic=None classify
     identically (null is the 0-sentinel, not a distinct state).

Run: python3 tests/review/test_benchpacket_null_birth_tic.py
Exit 0 = PASS, 1 = FAIL.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    failures = []

    # --- (1) bench-packet end-to-end over a mixed-birth_tic zone ---
    bpp = _load("bench_packet_prep", SCRIPTS / "bench-packet-prep.py")
    zone = tempfile.mkdtemp(prefix="bpp-nulltic-")
    al = Path(zone) / "audit-logs"
    (al / "cprs").mkdir(parents=True)
    (al / "signals").mkdir()
    (al / "tics").mkdir()
    rows = [
        {"id": "a", "status": "extracted", "lesson": "int birth",
         "birth_tic": 100, "source": "t"},
        {"id": "b", "status": "extracted", "lesson": "null birth",
         "birth_tic": None, "source": "t"},
        {"id": "c", "status": "extracted", "lesson": "absent birth",
         "source": "t"},
    ]
    with open(al / "cprs" / "queue.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    try:
        packet = bpp.build_bench_packet(zone, dry_run=True)
    except TypeError as e:
        failures.append(f"FAIL(bench-e2e): build_bench_packet crashed: {e}")
        packet = None
    if packet is not None:
        dossiers = {d["id"]: d for d in packet["pending_cogprs"]}
        if set(dossiers) != {"a", "b", "c"}:
            failures.append(
                f"FAIL(bench-e2e): surfaced ids {sorted(dossiers)} != a,b,c")
        elif dossiers["b"]["birth_tic"] != 0 or dossiers["c"]["birth_tic"] != 0:
            failures.append(
                "FAIL(bench-e2e): null/absent birth_tic did not coalesce to 0 "
                f"(b={dossiers['b']['birth_tic']} c={dossiers['c']['birth_tic']})")
        else:
            order = [d["id"] for d in packet["pending_cogprs"]]
            if order.index("a") < order.index("b"):
                failures.append(
                    f"FAIL(bench-e2e): 0-sentinel rows must sort before "
                    f"birth_tic=100 (got {order})")

    # --- (2)+(3) ripple-assessor maturity gate under null birth_tic ---
    ra = _load("ripple_assessor", SCRIPTS / "ripple-assessor.py")
    base = {"queue_status": "enrichment_eligible",
            "enrichment": [{"kind": "e"}]}
    try:
        state_null, _ = ra.classify_cpr_readiness(
            dict(base, birth_tic=None), current_tic_count=646)
    except TypeError as e:
        failures.append(f"FAIL(ripple-null): classify crashed: {e}")
        state_null = None
    if state_null == "tic_gated":
        failures.append(
            "FAIL(ripple-null): null birth_tic must not tic-gate")
    state_zero, _ = ra.classify_cpr_readiness(
        dict(base, birth_tic=0), current_tic_count=646)
    if state_null is not None and state_null != state_zero:
        failures.append(
            f"FAIL(ripple-parity): null ({state_null}) != zero ({state_zero})")

    if failures:
        print("NULL-BIRTH-TIC READER TEST: FAIL")
        for f in failures:
            print("  " + f)
        return 1

    print("NULL-BIRTH-TIC READER TEST: PASS")
    print("  (1) bench e2e: null/absent coalesce to 0, sort stable, no crash")
    print("  (2) ripple maturity gate survives null birth_tic, no tic-gate")
    print("  (3) null and 0-sentinel classify identically")
    return 0


if __name__ == "__main__":
    sys.exit(main())
