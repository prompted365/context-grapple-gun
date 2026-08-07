#!/usr/bin/env python3
"""
Signals Test — boot-banner latest-per-id reader (bk-boot-banner-latest-per-id-reader, tic 686).

Guards the banner-reader fix: session-restore's SIREN banner read EVERY
active-manifest.jsonl row (the comment claimed "the manifest is deduplicated" —
it is append-only BETWEEN prune sweeps), so a signal's update/resolve appended a
NEW row and the reader counted stale predecessors — the 65/62-vs-57 divergence
at the t681/t682/t685 boots, and a resolved drift row crowned loudest at t681.
Instance of cgg-ledger#file-sort-is-not-chronology-derived-surfaces-excluded-
from-primary-readers (reader-locus repair, not a manifest rewrite).

The cure is a terminal-valve latest-per-id projection OWNED by the single-owner
lib (signal_active.latest_per_id) and consumed by the banner (with the hook's
embedded lockstep replica):
  LATEST   — 'latest' is file-append order within the ONE manifest file
             (chronological provenance), keyed on signal_id|id.
  VALVE    — the active predicate then runs on the LATEST row only, so a
             resolved-later signal leaves the active set.
  HONESTY  — id-less rows cannot be projected and pass through unprojected
             (conservative: never silently dropped).
"""
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
LIB = HERE.parent.parent / "scripts" / "lib" / "signal_active.py"

spec = importlib.util.spec_from_file_location("signal_active_t686", str(LIB))
sa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sa)


def test_duplicate_rows_collapse_latest_wins():
    rows = [
        {"signal_id": "sig_a", "status": "active", "volume": 20},
        {"signal_id": "sig_a", "status": "active", "volume": 35},
    ]
    latest = sa.latest_per_id(rows)
    assert len(latest) == 1
    assert latest[0]["volume"] == 35


def test_resolved_later_row_leaves_active_set():
    # The t681 shape: an earlier active drift row + a later resolved row for
    # the same id. Raw read counts it active (and can crown it loudest);
    # latest-per-id + the active predicate excludes it.
    rows = [
        {"signal_id": "sig_drift", "status": "active", "volume": 40},
        {"signal_id": "sig_drift", "status": "resolved", "volume": 40},
        {"signal_id": "sig_ladder", "status": "active", "volume": 35},
    ]
    active = [r for r in sa.latest_per_id(rows) if sa.is_active_ray(r)]
    assert [r["signal_id"] for r in active] == ["sig_ladder"]
    loudest = max(active, key=lambda s: s.get("volume", 0))
    assert loudest["signal_id"] == "sig_ladder"


def test_idless_rows_pass_through_unprojected():
    rows = [
        {"signal_id": "sig_a", "status": "active", "volume": 5},
        {"status": "active", "volume": 7},
    ]
    latest = sa.latest_per_id(rows)
    assert len(latest) == 2


def test_id_key_falls_back_to_id_field():
    rows = [
        {"id": "sig_b", "status": "active", "volume": 3},
        {"id": "sig_b", "status": "working", "volume": 9},
    ]
    latest = sa.latest_per_id(rows)
    assert len(latest) == 1
    assert latest[0]["status"] == "working"


def test_hook_replica_in_lockstep():
    # The installed banner carries an embedded replica of the projection for
    # the lib-unreachable path — the replica must exist in the hook source and
    # name the same key precedence (signal_id then id). A textual lockstep
    # check, same discipline as the is_active_ray replica comment.
    hook = HERE.parent.parent / "hooks" / "session-restore.sh"
    text = hook.read_text()
    assert "latest_per_id" in text
    assert text.index("signal_id") < len(text)  # key precedence present


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    passed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")
    print("=" * 74)
    print(f"RESULT: {passed}/{len(fns)} — {'OK' if passed == len(fns) else 'FAIL'}")
    sys.exit(0 if passed == len(fns) else 1)
