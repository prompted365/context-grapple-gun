#!/usr/bin/env python3
"""
Signals Test — manifold_summary single-owner predicate adoption
(bk-conformation-emitter-adopt-active-ray-predicate, tic 684).

Guards the /review-683 PROMOTE of 4b0fefebb476 (cgg-ledger
#predicate-retirement-needs-reader-consumer-sweep): the conformation emitter's
governance_query_enrichment.manifold_summary still computed `active` via the
RETIRED raw-status enum — governance_query's thin signals.status rows carry
`state` only (no heat projection), so the two acknowledged-with-heat rays
counted by the single-owner predicate (lib/signal_active.is_active_ray, owner
since t674) were invisible to the enrichment counter. The delta-2 divergence
(conformation 57 vs enrichment 55) recurred t680→t683 (stepper F5) — the
retired predicate over an authoritative source lies quietly.

Pins, on synthetic fixtures:
  1. ADOPTION — with manifest_records supplied, manifold_summary.active is the
     is_active_ray count (raw-enum-active + acknowledged-with-heat), the old
     thin-row count survives as active_raw_enum, and active_source declares the
     split (residual divergence carries a declared source split — acceptance).
  2. STATE — manifold_state derives from the ADOPTED count.
  3. COOLED — an acknowledged ray at heat 0 does NOT count (the precise
     retirement: acknowledged is no longer auto-active).
  4. BACK-COMPAT — without manifest_records the raw thin-row computation is
     unchanged (no silent behavior change for callers that lack the records).

Run: python3 test_manifold_summary_predicate_adoption_tic684.py  (pytest-discoverable)
"""
import importlib.util
import os
import sys

_SCRIPTS = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts"))
sys.path.insert(0, _SCRIPTS)
sys.path.insert(0, os.path.join(_SCRIPTS, "lib"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "cadence_ops", os.path.join(_SCRIPTS, "cadence-ops.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _gq_signals_response(n_active, n_resolved=1, n_dismissed=1):
    results = []
    for i in range(n_active):
        results.append({"signal_id": f"sig_a{i}", "state": "active"})
    for i in range(n_resolved):
        results.append({"signal_id": f"sig_r{i}", "state": "resolved"})
    for i in range(n_dismissed):
        results.append({"signal_id": f"sig_d{i}", "state": "dismissed"})
    return [{"query_type": "signals.status", "results": results}]


def _manifest_records(n_active, acked_hot=0, acked_cold=0):
    recs = []
    for i in range(n_active):
        recs.append({"signal_id": f"sig_a{i}", "status": "active", "volume": 10})
    for i in range(acked_hot):
        recs.append({"signal_id": f"sig_ack_hot{i}", "status": "acknowledged",
                     "volume": 25})
    for i in range(acked_cold):
        recs.append({"signal_id": f"sig_ack_cold{i}", "status": "acknowledged",
                     "volume": 0, "heat": 0.0})
    return recs


def test_adoption_counts_acknowledged_with_heat_and_declares_split():
    m = _load()
    gq = _gq_signals_response(n_active=55)
    records = _manifest_records(n_active=55, acked_hot=2)
    enr = m.extract_governance_enrichment(gq, manifest_records=records)
    ms = enr["manifold_summary"]
    assert ms["active"] == 57, f"adopted predicate count must be 57, got {ms['active']}"
    assert ms["active_raw_enum"] == 55, f"thin-row count must survive declared, got {ms}"
    assert "active_source" in ms, "residual divergence must carry a declared source split"
    assert ms["resolved"] == 1 and ms["dismissed"] == 1


def test_manifold_state_derives_from_adopted_count():
    m = _load()
    # thin rows say 0 active; manifest carries 3 hot acknowledged rays
    gq = _gq_signals_response(n_active=0)
    records = _manifest_records(n_active=0, acked_hot=3)
    enr = m.extract_governance_enrichment(gq, manifest_records=records)
    assert enr["manifold_summary"]["active"] == 3
    assert enr["manifold_state"] == "HAZARD", (
        f"state must key on the adopted count (3 > 2), got {enr['manifold_state']}")


def test_cooled_acknowledged_ray_does_not_count():
    m = _load()
    gq = _gq_signals_response(n_active=1)
    records = _manifest_records(n_active=1, acked_cold=2)
    enr = m.extract_governance_enrichment(gq, manifest_records=records)
    assert enr["manifold_summary"]["active"] == 1, (
        "a heat-0 acknowledged ray must not count — the precise retirement")


def test_backcompat_without_manifest_records_unchanged():
    m = _load()
    gq = _gq_signals_response(n_active=2)
    enr = m.extract_governance_enrichment(gq)
    ms = enr["manifold_summary"]
    assert ms["active"] == 2
    assert "active_raw_enum" not in ms and "active_source" not in ms, (
        "no manifest records -> raw computation unchanged, no phantom fields")
    assert enr["manifold_state"] == "ACTIVE"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILED'}")
    sys.exit(1 if failures else 0)
