#!/usr/bin/env python3
"""
visitor-economy-monitor.py — Mogul-callable visitor economy governance monitor.

Wraps cache-ops.py, standing-engine.py, and biome-engine.py with governance
envelope production for mandate cycle integration.

Functions:
  cache_refresh_cycle(tic)   — wraps cache-ops refresh_cycle + governance envelope
  standing_decay_check()     — scan visitors for trust_score decay below thresholds
  biome_health_check()       — read biome state, emit signals on threshold violations
  visitor_census()           — count active visitors by standing tier

CLI:
  python3 visitor-economy-monitor.py --cache-refresh <tic>
  python3 visitor-economy-monitor.py --standing-decay
  python3 visitor-economy-monitor.py --biome-health
  python3 visitor-economy-monitor.py --census
  python3 visitor-economy-monitor.py --full-cycle <tic>

Exit codes: 0=success, 1=error.

REPORT KEYS — WRITE VERDICT, NOT CONSTRUCTION (tic 765; /review 747 Q1 ray,
cgg-ledger/ledger.md:3775; backlog row bk-write-verb-keys-report-write-verdict):
  signals_written                  — ids whose row ACTUALLY LANDED this call
  signals_suppressed_as_duplicate  — ids dedup-by-identity refused (already present)
  signals_emitted                  — DEPRECATED ALIAS (one era, dated below):
                                     the CONSTRUCTED set, unchanged in value
  thresholds_violated              — follows the WRITTEN set, per the ruling
A past-tense write-verb key must report the write verdict; `signals_emitted`
read identically in the wrote case and the suppressed-by-dedup case, which is
the over-claim this cure removes.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow importing siblings from same directory
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from zone_root import resolve_zone_root, load_ticzone, audit_logs_path
from lib.atomic_append import atomic_append_jsonl, atomic_write_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_zone():
    """Resolve zone root and audit-logs path."""
    zr = resolve_zone_root(SCRIPT_DIR)
    tz = load_ticzone(zr)
    al = audit_logs_path(zr, tz)
    return zr, al


def _deterministic_signal_id(condition, discriminator=""):
    """Produce a deterministic signal ID from condition + discriminator."""
    raw = f"{condition}:{discriminator}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"sig_{condition}_{h}"


# ---------------------------------------------------------------------------
# Write-verdict vocabulary (tic 765 — /review 747 Q1 ray)
#
# `dedup_signal_append()` yields exactly one bit, and its own docstring pins the
# meaning: "The return value is unchanged (True iff the DAILY row was written)".
# These are the only two dispositions this producer can OBSERVE for its own
# writes. Anything else is declared, never guessed.
# ---------------------------------------------------------------------------
VERDICT_WRITTEN = "written"
VERDICT_SUPPRESSED = "suppressed_as_duplicate"

# DEPRECATED 2026-09-03 (tic 765). `signals_emitted` is retained as an ALIAS for
# ONE era so the closed consumer set (mogul-runner.sh:465 copies biome_health
# VERBATIM; cgg-runtime/skills/stage/SKILL.md:337 documents the key) keeps
# reading a byte-identical value while it migrates to the split keys. Removal is
# a separate ruled motion — dropping it silently would break consumers this
# increment's write fence may not edit.
#
# The string travels IN THE PAYLOAD on purpose. The ruled ray's own finding is
# that a copy-verbatim contract transmits a producer's mis-naming under the
# reporter's no-inference warrant; a deprecation that lives only in this source
# file would never reach the reporter that copies the key.
WRITE_VERB_KEY_DEPRECATION = (
    "signals_emitted: DEPRECATED 2026-09-03 (tic 765, /review 747 Q1 ray) — "
    "retained as an ALIAS for ONE era. It lists ids CONSTRUCTED, not rows "
    "WRITTEN, and reads identically in the wrote case and the suppressed-by-"
    "dedup case. Read signals_written / signals_suppressed_as_duplicate instead."
)

# DOES-NOT-SATISFY RIDER — the cache_refresh arm. This increment's fence is one
# file; the cache artifact's key is another module's construction.
CACHE_STATE_VERDICT_RIDER = (
    "DOES NOT SATISFY the write-verdict cure: cache_state.signals_emitted is "
    "constructed by cache-ops.py:747 and is NOT split into written/suppressed. "
    "Measured at tic 765: cache-ops.py has NO signal write path at all — it "
    "imports atomic_append_jsonl for the quarantine log (:260) and the "
    "retrieval log (:457) only — so its ids are neither written nor dedup-"
    "suppressed; they are NEVER-ATTEMPTED, a third disposition this two-value "
    "split cannot express. Read that key as CONSTRUCTED ids, never as landed "
    "rows. Curing it at source is an owed motion at cache-ops.py, OUT OF FENCE "
    "for backlog row bk-write-verb-keys-report-write-verdict."
)

# DOES-NOT-SATISFY RIDER — the biome arm's method. Measured-by-delta is a
# WEAKER instrument than a producer verdict and must never read as one.
BIOME_VERDICT_METHOD_RIDER = (
    "DOES NOT SATISFY the write-verdict cure at its source: biome-engine.py:387 "
    "emit_signal() READS its dedup verdict and DISCARDS it — `if not written: "
    "return sig_id` returns the SAME id as the written branch — so this "
    "producer cannot receive one. signals_written on this arm is MEASURED by a "
    "read-only before/after delta on biome-engine's own daily signal partition, "
    "NOT reported by the emitter. Strictly weaker than a producer verdict: a "
    "concurrent writer landing the same id inside the window would be credited "
    "here. Curing it at source is an owed motion at biome-engine.py, OUT OF "
    "FENCE for backlog row bk-write-verb-keys-report-write-verdict."
)


def _emit_signal(al, signal_id, kind, band, description, subsystem="visitor_economy"):
    """Append a signal to today's signal JSONL and RETURN THE WRITE VERDICT.

    Returns the signal dict enriched with a `write_verdict` key: VERDICT_WRITTEN
    when the daily row actually landed, VERDICT_SUPPRESSED when dedup-by-identity
    found the id already present in the daily partition or the active manifest.

    RETURN-SHAPE CONTRACT (tic 765): the return stays a SUBSCRIPTABLE SIGNAL
    DICT — `signal["id"]` keeps working — because a consumer outside this file
    reads it that way (test_signal_manifest_ingest_tic742.py:468-471). The
    verdict is therefore carried AS A KEY, not as a tuple; a tuple return would
    have been the tidier signature and a silent break of a consumer this
    increment's write fence may not edit.

    THE VERDICT NEVER REACHES THE LEDGER: the enriched dict is a COPY built
    AFTER dedup_signal_append() has already serialized the row, so neither the
    daily partition nor the manifest projection carries the key.
    """
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    sig_dir = os.path.join(al, "signals")
    os.makedirs(sig_dir, exist_ok=True)

    signal = {
        "type": "signal",
        "id": signal_id,
        "kind": kind,
        "band": band,
        "volume": 30,
        "status": "active",
        "subsystem": subsystem,
        "description": description,
        "emitted_at": now.isoformat(),
        "source": "visitor-economy-monitor.py",
    }
    target = os.path.join(sig_dir, f"{today}.jsonl")
    manifest = os.path.join(sig_dir, "active-manifest.jsonl")
    try:
        from lib.atomic_append import dedup_signal_append
        written = dedup_signal_append(target, signal, manifest_path=manifest,
                                      ingest_manifest=True)
    except ImportError:
        # No dedup gate on this path: the append is unconditional, so the row IS
        # written. Reporting it as written is measurement, not optimism.
        atomic_append_jsonl(target, signal)
        written = True
    return dict(signal,
                write_verdict=VERDICT_WRITTEN if written else VERDICT_SUPPRESSED)


def _daily_ledger_ids(signal_dir):
    """READ-ONLY: the signal ids present in TODAY's daily partition of `signal_dir`.

    Returns (partition_path, ids); a missing partition yields (path, empty set).
    This function NEVER writes. It exists because a FOREIGN emitter can swallow
    its own write verdict, and a before/after delta on the exact partition that
    `dedup_signal_append` gates is the only remaining way to OBSERVE the same
    bit without editing that emitter (out of fence).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(signal_dir, f"{today}.jsonl")
    ids = set()
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                sid = d.get("signal_id", d.get("id", ""))
                if sid:
                    ids.add(sid)
    return path, ids


# ---------------------------------------------------------------------------
# 1. Cache Refresh Cycle
# ---------------------------------------------------------------------------

def cache_refresh_cycle(tic, zone_root=None):
    """Wrap cache-ops.py refresh_cycle() with governance envelope.

    Runs the 6-step cache refresh, produces cache-state artifact,
    and emits summary signals. Returns envelope dict.
    """
    now = datetime.now(timezone.utc)
    zr = zone_root or resolve_zone_root(SCRIPT_DIR)
    _, al = _resolve_zone()

    # Import cache-ops refresh_cycle
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cache_ops", os.path.join(SCRIPT_DIR, "cache-ops.py"))
        cache_ops = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cache_ops)
        artifact = cache_ops.refresh_cycle(tic=tic, project_dir=zr)
    except Exception as e:
        artifact = {
            "artifact_type": "cache_state",
            "error": str(e),
            "produced_at": now.isoformat(),
            "produced_by_tic": tic,
            "summary": {
                "total_entries": 0, "active": 0, "stale": 0,
                "quarantined": 0, "deprecated": 0,
                "archived_this_cycle": 0, "pending_queue_depth": 0,
            },
            "trust_distribution": {"mean": 0.0, "median": 0.0,
                                   "min": 0.0, "max": 0.0},
            "search_tier_in_use": "tier_1",
            "monopoly_check": {"top_contributor_entity": "",
                               "top_contributor_percentage": 0.0,
                               "dampening_active": False},
            "ttl_health": {"entries_approaching_expiry": 0,
                           "probes_dispatched": 0, "probes_responded": 0,
                           "entries_expired_this_cycle": 0},
            "standing_changes_processed": 0,
            # This fallback artifact is THIS file's construction and carries no
            # signals at all; the split keys are empty because nothing was
            # constructed, written, or suppressed. The success-path artifact is
            # cache-ops.py's own construction — see the rider on the envelope.
            "signals_emitted": [],
            "signals_emitted_deprecation": WRITE_VERB_KEY_DEPRECATION,
            "signals_written": [],
            "signals_suppressed_as_duplicate": [],
        }

    envelope = {
        "operation": "cache_refresh",
        "tic": tic,
        "timestamp": now.isoformat(),
        "source": "visitor-economy-monitor.py",
        "cache_state": artifact,
        "status": "error" if "error" in artifact else "complete",
        # RIDER (verbatim, tic 765): a reader seeing the write-verdict cure land
        # in this file could mistake cache_state.signals_emitted for cured. It
        # is not. Reproduced here because this envelope is the surface that
        # carries that key to the mandate consumer.
        "cache_state_write_verdict_rider": CACHE_STATE_VERDICT_RIDER,
    }

    return envelope


# ---------------------------------------------------------------------------
# 2. Standing Decay Check
# ---------------------------------------------------------------------------

def standing_decay_check(zone_root=None):
    """Scan all active visitors for trust_score decay below standing thresholds.

    Identifies entities approaching demotion and emits WATCH signals.
    Returns a summary dict.
    """
    now = datetime.now(timezone.utc)
    zr = zone_root or resolve_zone_root(SCRIPT_DIR)
    _, al = _resolve_zone()

    # Load agent index for visitor enumeration
    biome_dir = os.path.join(al, "biome")
    idx_path = os.path.join(biome_dir, "visa-registry", "agent-index.json")
    if not os.path.isfile(idx_path):
        return {
            "operation": "standing_decay_check",
            "timestamp": now.isoformat(),
            "visitors_scanned": 0,
            "at_risk": [],
            "signals_emitted": [],
            "signals_emitted_deprecation": WRITE_VERB_KEY_DEPRECATION,
            "signals_written": [],
            "signals_suppressed_as_duplicate": [],
            "signals_disposition_method": "producer_verdict",
        }

    with open(idx_path, "r", encoding="utf-8") as f:
        idx = json.load(f)

    visitors_by_standing = idx.get("visitors_by_standing", {})

    # Import standing engine
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "standing_engine", os.path.join(SCRIPT_DIR, "standing-engine.py"))
        se = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(se)
    except Exception as e:
        return {
            "operation": "standing_decay_check",
            "timestamp": now.isoformat(),
            "error": str(e),
            "visitors_scanned": 0,
            "at_risk": [],
            "signals_emitted": [],
            "signals_emitted_deprecation": WRITE_VERB_KEY_DEPRECATION,
            "signals_written": [],
            "signals_suppressed_as_duplicate": [],
            "signals_disposition_method": "producer_verdict",
        }

    # Standing thresholds from standing-engine CONFIG
    trust_thresholds = se.CONFIG.get("trust_thresholds", {})

    at_risk = []
    # DEPRECATED alias — built EXACTLY as before (every constructed id, in
    # construction order) so consumers reading the old key see a byte-identical
    # value during the alias era. See WRITE_VERB_KEY_DEPRECATION.
    signals_emitted = []
    signals_written = []
    signals_suppressed_as_duplicate = []
    visitors_scanned = 0

    for standing, entity_ids in visitors_by_standing.items():
        threshold = trust_thresholds.get(standing, 0.0)
        for eid in entity_ids:
            visitors_scanned += 1
            try:
                result = se.compute_trust_score(eid, zone_root=zr)
                ts = result["trust_score"]
                # At risk: within 20% above threshold or below it
                warning_band = threshold * 0.20
                if ts < threshold + warning_band:
                    risk_entry = {
                        "entity_id": eid,
                        "current_standing": standing,
                        "trust_score": round(ts, 4),
                        "threshold": threshold,
                        "below_threshold": ts < threshold,
                    }
                    at_risk.append(risk_entry)

                    if ts < threshold:
                        sig_id = _deterministic_signal_id(
                            "standing.decay_below_threshold", eid)
                        emitted = _emit_signal(
                            al, sig_id, "WATCH", "COGNITIVE",
                            f"Entity {eid} trust_score {ts:.3f} below "
                            f"{standing} threshold {threshold}")
                        signals_emitted.append(sig_id)
                        # The verdict is this producer's OWN — directly observed
                        # from the write path, not inferred from presence.
                        if emitted["write_verdict"] == VERDICT_WRITTEN:
                            signals_written.append(sig_id)
                        else:
                            signals_suppressed_as_duplicate.append(sig_id)
            except Exception:
                # Entity computation failed — skip, don't block cycle
                continue

    return {
        "operation": "standing_decay_check",
        "timestamp": now.isoformat(),
        "visitors_scanned": visitors_scanned,
        "at_risk": at_risk,
        "signals_written": signals_written,
        "signals_suppressed_as_duplicate": signals_suppressed_as_duplicate,
        "signals_disposition_method": "producer_verdict",
        "signals_emitted": signals_emitted,
        "signals_emitted_deprecation": WRITE_VERB_KEY_DEPRECATION,
    }


# ---------------------------------------------------------------------------
# 3. Biome Health Check
# ---------------------------------------------------------------------------

def biome_health_check(zone_root=None):
    """Read current biome state, compute health monitors, emit signals.

    Returns health summary dict.
    """
    now = datetime.now(timezone.utc)
    zr = zone_root or resolve_zone_root(SCRIPT_DIR)
    _, al = _resolve_zone()

    # Import biome engine
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "biome_engine", os.path.join(SCRIPT_DIR, "biome-engine.py"))
        be = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(be)
    except Exception as e:
        return {
            "operation": "biome_health_check",
            "timestamp": now.isoformat(),
            "error": str(e),
            "health": {},
            "thresholds_violated": 0,
            "signals_written": [],
            "signals_suppressed_as_duplicate": [],
            "signals_disposition_unknown": [],
            "signals_disposition_method": "unavailable",
            "signals_disposition_rider": BIOME_VERDICT_METHOD_RIDER,
            "signals_emitted": [],
            "signals_emitted_deprecation": WRITE_VERB_KEY_DEPRECATION,
        }

    # Load biome state
    #
    # THE FOREIGN-PRODUCER ARM (tic 765). biome-engine.py:387 emit_signal()
    # READS its write verdict (`written = dedup_signal_append(...)`) and then
    # DISCARDS it: `if not written: return sig_id  # Already exists, skip
    # silently` returns the SAME id as the written branch. The list
    # check_health_signals() hands back is therefore the CONSTRUCTED set, and no
    # edit inside this file can make that return value carry a verdict.
    #
    # What this file CAN do without touching biome-engine.py (out of fence) is
    # MEASURE the same bit the verdict reports: dedup_signal_append returns True
    # iff the DAILY row was written, so a read-only before/after snapshot of that
    # exact partition, taken around the call, separates written from suppressed.
    # This is a measurement, NOT a presence inference — an id already in the
    # partition before the call is not credited to this call.
    try:
        topology, organisms, environment = be.load_state()
        health = be.compute_health(topology, organisms, environment)
        be_signal_dir = getattr(be, "SIGNAL_DIR", None)
        pre_path, pre_ids = (_daily_ledger_ids(be_signal_dir)
                             if be_signal_dir else (None, set()))
        health_signals = be.check_health_signals(health, environment)
        post_path, post_ids = (_daily_ledger_ids(be_signal_dir)
                               if be_signal_dir else (None, set()))
    except Exception as e:
        return {
            "operation": "biome_health_check",
            "timestamp": now.isoformat(),
            "error": str(e),
            "health": {},
            "thresholds_violated": 0,
            "signals_written": [],
            "signals_suppressed_as_duplicate": [],
            "signals_disposition_unknown": [],
            "signals_disposition_method": "unavailable",
            "signals_disposition_rider": BIOME_VERDICT_METHOD_RIDER,
            "signals_emitted": [],
            "signals_emitted_deprecation": WRITE_VERB_KEY_DEPRECATION,
        }

    # health_signals is a list of signal ID strings already emitted by
    # biome-engine's check_health_signals (which calls emit_signal internally).
    # We just collect them for the envelope — no need to re-emit.
    # DEPRECATED alias — value UNCHANGED (the constructed set, in order).
    signals_emitted = health_signals if health_signals else []

    signals_written = []
    signals_suppressed_as_duplicate = []
    signals_disposition_unknown = []
    if pre_path is not None and post_path is not None and pre_path == post_path:
        disposition_method = "ledger_delta_measured"
        newly_present = post_ids - pre_ids
        for sid in signals_emitted:
            if sid in newly_present:
                signals_written.append(sid)
            else:
                signals_suppressed_as_duplicate.append(sid)
    else:
        # Either biome-engine exposed no SIGNAL_DIR, or the UTC day rolled over
        # mid-call so the two snapshots name different partitions. DECLARED
        # NEGATIVE SPACE: the ids are reported with NO disposition claim rather
        # than defaulted into either arm. An unknown defaulted to "written" is
        # the original over-claim; defaulted to "suppressed" is a new one.
        disposition_method = "unavailable"
        signals_disposition_unknown = list(signals_emitted)

    cycle = environment.get("cycle", 0)
    act = environment.get("act", "unknown")

    return {
        "operation": "biome_health_check",
        "timestamp": now.isoformat(),
        "biome_cycle": cycle,
        "biome_act": act,
        "health": health,
        # RULED (/review 747 Q1): thresholds_violated follows the WRITTEN set,
        # not the constructed set. NOTE FOR THE ALIAS'S RETIREMENT: the
        # constructed count is currently recoverable ONLY as
        # len(signals_emitted); retiring the alias without giving that quantity
        # its own key would let it go dark. Flagged as an owed motion at tic 765.
        "thresholds_violated": len(signals_written),
        "signals_written": signals_written,
        "signals_suppressed_as_duplicate": signals_suppressed_as_duplicate,
        "signals_disposition_unknown": signals_disposition_unknown,
        "signals_disposition_method": disposition_method,
        "signals_disposition_rider": BIOME_VERDICT_METHOD_RIDER,
        "signals_emitted": signals_emitted,
        "signals_emitted_deprecation": WRITE_VERB_KEY_DEPRECATION,
    }


# ---------------------------------------------------------------------------
# 4. Visitor Census
# ---------------------------------------------------------------------------

def visitor_census(zone_root=None):
    """Count active visitors by standing tier, compute aggregate stats.

    Produces census artifact for governance_query.py (MVOS L3).
    Returns census dict.
    """
    now = datetime.now(timezone.utc)
    zr = zone_root or resolve_zone_root(SCRIPT_DIR)
    _, al = _resolve_zone()

    biome_dir = os.path.join(al, "biome")
    idx_path = os.path.join(biome_dir, "visa-registry", "agent-index.json")

    if not os.path.isfile(idx_path):
        census = {
            "artifact_type": "visitor_census",
            "timestamp": now.isoformat(),
            "total_active": 0,
            "by_standing": {},
            "standing_order": ["guest", "tourist", "student",
                               "resident", "citizen"],
        }
    else:
        with open(idx_path, "r", encoding="utf-8") as f:
            idx = json.load(f)

        vbs = idx.get("visitors_by_standing", {})
        by_standing = {}
        total_active = 0
        for standing, entities in vbs.items():
            count = len(entities)
            by_standing[standing] = count
            total_active += count

        census = {
            "artifact_type": "visitor_census",
            "timestamp": now.isoformat(),
            "total_active": total_active,
            "by_standing": by_standing,
            "standing_order": ["guest", "tourist", "student",
                               "resident", "citizen"],
        }

    # Persist census artifact
    census_dir = os.path.join(biome_dir, "census")
    os.makedirs(census_dir, exist_ok=True)
    artifact_path = os.path.join(
        census_dir,
        f"{now.strftime('%Y-%m-%dT%H%M%S')}-census.json")
    atomic_write_json(artifact_path, census)

    return census


# ---------------------------------------------------------------------------
# 5. Full Cycle (all operations)
# ---------------------------------------------------------------------------

def economy_observation(zone_root=None):
    """Run economy bridge observation cycle.

    Fetches OT economic state via Foreman API, emits governance signals
    and rendering whispers. Returns observation envelope.
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "economy_bridge_adapter",
            os.path.join(SCRIPT_DIR, "economy-bridge-adapter.py"))
        eba = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(eba)
        return eba.observe()
    except Exception as e:
        return {
            "operation": "economy_observation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error": str(e),
        }


def full_cycle(tic, zone_root=None):
    """Run all visitor economy monitoring operations.

    Returns combined results dict. The mandate contract demands MEASURED keys
    from this cycle, so the measurement must outlive the caller's transcript:
    the full result persists to audit-logs/visitor-economy/full-cycle-tic-<N>.json
    (re-readable without re-executing a signal-emitting cycle).
    """
    results = {}
    results["cache_refresh"] = cache_refresh_cycle(tic, zone_root)
    results["standing_decay"] = standing_decay_check(zone_root)
    results["biome_health"] = biome_health_check(zone_root)
    results["census"] = visitor_census(zone_root)
    results["economy_observation"] = economy_observation(zone_root)

    _, al = _resolve_zone()
    artifact_dir = os.path.join(al, "visitor-economy")
    artifact_path = os.path.join(artifact_dir, f"full-cycle-tic-{tic}.json")
    # stamp-then-write: the attestation must be serialized INSIDE the durable
    # copy — a stamp applied after the write exists only on the in-memory copy,
    # i.e. on the channel this recovery artifact exists to outlive. The failure
    # path reports on the in-memory copy because a failed write has no other
    # carrier.
    results["artifact_path"] = artifact_path
    try:
        os.makedirs(artifact_dir, exist_ok=True)
        atomic_write_json(artifact_path, results)
    except Exception as e:
        results["artifact_path"] = None
        results["artifact_write_error"] = str(e)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Visitor economy governance monitor — Mogul mandate callable",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cache-refresh", type=int, metavar="TIC",
                       help="Run cache refresh cycle for given tic")
    group.add_argument("--standing-decay", action="store_true",
                       help="Run standing decay check")
    group.add_argument("--biome-health", action="store_true",
                       help="Run biome health check")
    group.add_argument("--census", action="store_true",
                       help="Run visitor census")
    group.add_argument("--economy", action="store_true",
                       help="Run economy bridge observation cycle")
    group.add_argument("--full-cycle", type=int, metavar="TIC",
                       help="Run all operations for given tic")

    parser.add_argument("--zone-root", default=None,
                        help="Zone root override")

    args = parser.parse_args()

    zr = args.zone_root

    if args.cache_refresh is not None:
        result = cache_refresh_cycle(args.cache_refresh, zr)
    elif args.standing_decay:
        result = standing_decay_check(zr)
    elif args.biome_health:
        result = biome_health_check(zr)
    elif args.census:
        result = visitor_census(zr)
    elif args.economy:
        result = economy_observation(zr)
    elif args.full_cycle is not None:
        result = full_cycle(args.full_cycle, zr)
    else:
        parser.print_help()
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
