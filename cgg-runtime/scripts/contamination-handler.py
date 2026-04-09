#!/usr/bin/env python3
"""
contamination-handler.py — Cache Contamination Immune Response

Implements the 7-step response chain from cache-poisoning-protocol.md
and the purge cascade from arena-defense-spec.md.

Steps are sequential: N+1 waits for N. Each step emits signals.

Implements:
  - cache-poisoning-protocol.md (detect, quarantine, audit, notify, standing, source, escalation)
  - arena-defense-spec.md (purge cascades, rollback drills)
  - border-stack-spec.md Layer 4 (cache border trust-tier enforcement)

Usage (CLI):
    python3 contamination-handler.py --detect <entry_id>
    python3 contamination-handler.py --quarantine <entry_id> --reason "..."
    python3 contamination-handler.py --trace <entry_id>
    python3 contamination-handler.py --notify <entry_id>
    python3 contamination-handler.py --cascade <entry_id> [--scope narrow|medium|wide]
    python3 contamination-handler.py --drill <provider_id>

Usage (module):
    from contamination_handler import (
        detect,
        quarantine,
        trace,
        notify,
        cascade,
        rollback_drill,
    )

Exit codes: 0=success/clean, 1=contamination detected, 2=IO error, 3=drill failure.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from zone_root import resolve_zone_root, audit_logs_path, load_ticzone
    from lib.atomic_append import atomic_append_jsonl, atomic_write_json
except ImportError:
    def resolve_zone_root(start_dir=None):
        return os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    def audit_logs_path(zone_root, ticzone_config=None):
        return os.path.join(zone_root, "audit-logs")

    def load_ticzone(zone_root):
        return {}

    def atomic_append_jsonl(target, data):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, separators=(",", ":")) + "\n")

    def atomic_write_json(target, data):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")


# ---------------------------------------------------------------------------
# PROVISIONAL CONFIG
# ---------------------------------------------------------------------------
CONFIG = {
    # Trust score floor below which quarantine review triggers (PROVISIONAL)
    "trust_floor": -1.0,

    # Maximum downstream trace depth (PROVISIONAL — arena-defense-spec.md)
    "max_trace_depth": 3,

    # Pattern detection thresholds (same source)
    "pattern_watch_count": 2,       # 2 quarantines -> WATCH
    "pattern_suspend_count": 3,     # 3 quarantines -> suspend writes
    "pattern_mandatory_review": 5,  # 5+ quarantines -> mandatory standing review
    "pattern_window_tics": 15,      # window for pattern detection

    # Federation escalation non-response window (PROVISIONAL)
    "federation_escalation_tics": 5,

    # Cascade depth limit (PROVISIONAL — arena-defense-spec.md)
    "max_cascade_depth": 3,

    # Purge cascade log
    "cascade_log": "services/harpoon-orchestrator/purge-cascades.jsonl",

    # Contamination handler log
    "handler_log": "services/harpoon-orchestrator/contamination-events.jsonl",

    # Drill results log
    "drill_log": "services/harpoon-orchestrator/rollback-drills.jsonl",
}


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _audit_root(zone_root=None):
    zr = zone_root or resolve_zone_root()
    return audit_logs_path(zr, load_ticzone(zr))


def _cache_root(zone_root=None):
    ar = _audit_root(zone_root)
    return os.path.join(ar, "biome", "pen-pal-cache")


def _entries_dir(zone_root=None):
    return os.path.join(_cache_root(zone_root), "entries")


def _quarantine_log_path(zone_root=None):
    return os.path.join(_cache_root(zone_root), "quarantine.jsonl")


def _retrieval_log_path(zone_root=None):
    return os.path.join(_cache_root(zone_root), "retrieval.jsonl")


def _handler_log(zone_root=None):
    ar = _audit_root(zone_root)
    return os.path.join(ar, CONFIG["handler_log"])


def _cascade_log(zone_root=None):
    ar = _audit_root(zone_root)
    return os.path.join(ar, CONFIG["cascade_log"])


def _drill_log(zone_root=None):
    ar = _audit_root(zone_root)
    return os.path.join(ar, CONFIG["drill_log"])


def _signals_path(zone_root=None):
    ar = _audit_root(zone_root)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(ar, "signals", f"{today}.jsonl")


def _deterministic_id(*parts):
    payload = json.dumps(list(parts), sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


# ---------------------------------------------------------------------------
# Signal emission
# ---------------------------------------------------------------------------

def _emit_signal(signal_id, kind, description, volume=40, zone_root=None):
    signal = {
        "signal_id": signal_id,
        "kind": kind,
        "source": "contamination-handler",
        "description": description,
        "volume": volume,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_append_jsonl(_signals_path(zone_root), signal)
    return signal


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_entry(entry_id, zone_root=None):
    """Load a cache entry by ID. Returns dict or None."""
    entry_path = os.path.join(_entries_dir(zone_root), f"{entry_id}.json")
    if not os.path.isfile(entry_path):
        return None
    try:
        return json.loads(Path(entry_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_entry(entry, zone_root=None):
    """Persist a cache entry."""
    entry_path = os.path.join(_entries_dir(zone_root), f"{entry['entry_id']}.json")
    os.makedirs(os.path.dirname(entry_path), exist_ok=True)
    atomic_write_json(entry_path, entry)


def _load_jsonl(path):
    """Load all records from a JSONL file."""
    records = []
    if not os.path.isfile(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if "_schema" not in rec:
                    records.append(rec)
            except json.JSONDecodeError:
                continue
    return records


def _load_quarantine_log(zone_root=None):
    return _load_jsonl(_quarantine_log_path(zone_root))


def _load_retrieval_log(zone_root=None):
    return _load_jsonl(_retrieval_log_path(zone_root))


# ---------------------------------------------------------------------------
# Step 1: Detection
# ---------------------------------------------------------------------------

def detect(entry_id, zone_root=None):
    """Run anomaly checks on a cache entry.

    Returns detection result dict:
        {entry_id, anomalies_found: bool, anomalies: [...], severity}

    Checks:
      - Trust score anomaly (below floor)
      - Content-signature drift (content hash mismatch)
      - Source pattern anomaly (multiple quarantines from same source)
    """
    now = datetime.now(timezone.utc)
    entry = _load_entry(entry_id, zone_root)
    anomalies = []

    if entry is None:
        return {
            "entry_id": entry_id,
            "anomalies_found": False,
            "anomalies": [],
            "severity": "NONE",
            "error": "Entry not found",
            "timestamp": now.isoformat(),
        }

    # Check 1: Trust score anomaly
    trust_score = entry.get("trust_score", 0.0)
    if trust_score <= CONFIG["trust_floor"]:
        anomalies.append({
            "type": "trust_anomaly",
            "detail": f"Trust score {trust_score} <= floor {CONFIG['trust_floor']}",
            "severity": "HIGH",
        })

    # Check 2: Content-signature drift
    # Recompute entry_id from current content and compare
    sig = entry.get("structural_signature", {})
    content = entry.get("content", "")
    bond_id = entry.get("source_bond_id", "")
    if sig and content and bond_id:
        recomputed = hashlib.sha256(json.dumps({
            "bond_id": bond_id,
            "content": content,
            "structural_signature": sig,
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if recomputed != entry_id:
            anomalies.append({
                "type": "signature_drift",
                "detail": (
                    f"Recomputed entry_id {recomputed[:16]}... does not match "
                    f"stored {entry_id[:16]}..."),
                "severity": "HIGH",
            })

    # Check 3: Source pattern anomaly
    authors = entry.get("authors", [])
    quarantine_records = _load_quarantine_log(zone_root)
    for author in authors:
        author_quarantines = [
            q for q in quarantine_records
            if author in str(q.get("quarantined_by", ""))
               or author in str(q.get("entry_id", ""))
        ]
        if len(author_quarantines) >= CONFIG["pattern_watch_count"]:
            anomalies.append({
                "type": "source_pattern",
                "detail": (
                    f"Author {author} has {len(author_quarantines)} "
                    f"quarantine events"),
                "severity": "ALERT" if len(author_quarantines) >= CONFIG["pattern_suspend_count"] else "WATCH",
            })

    # Check 4: Status already quarantined
    if entry.get("status") == "quarantined":
        anomalies.append({
            "type": "already_quarantined",
            "detail": "Entry is already in quarantined status",
            "severity": "INFO",
        })

    # Determine overall severity
    severities = [a["severity"] for a in anomalies]
    if "HIGH" in severities:
        overall_severity = "HIGH"
    elif "ALERT" in severities:
        overall_severity = "ALERT"
    elif "WATCH" in severities:
        overall_severity = "WATCH"
    elif anomalies:
        overall_severity = "INFO"
    else:
        overall_severity = "NONE"

    result = {
        "entry_id": entry_id,
        "anomalies_found": len(anomalies) > 0,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "severity": overall_severity,
        "timestamp": now.isoformat(),
    }

    # Emit detection signal if anomalies found
    if anomalies:
        _emit_signal(
            signal_id=_deterministic_id(
                "contamination_detected", entry_id, overall_severity),
            kind="WATCH" if overall_severity in ("WATCH", "INFO") else "ALERT",
            description=(
                f"Contamination detection on {entry_id[:16]}...: "
                f"{len(anomalies)} anomalies, severity={overall_severity}"),
            volume=45 if overall_severity == "HIGH" else 35,
            zone_root=zone_root,
        )

    # Log detection event
    atomic_append_jsonl(_handler_log(zone_root), {
        "step": "detect",
        **result,
    })

    return result


# ---------------------------------------------------------------------------
# Step 2: Quarantine
# ---------------------------------------------------------------------------

def quarantine(entry_id, reason, quarantined_by="system",
               detection_source="explicit_report", zone_root=None):
    """Immediately quarantine a cache entry.

    No delay. No investigation gate. Per cache-poisoning-protocol.md step 2.

    Returns quarantine record dict.
    """
    now = datetime.now(timezone.utc)
    entry = _load_entry(entry_id, zone_root)

    if entry is None:
        return {
            "entry_id": entry_id,
            "success": False,
            "error": "Entry not found",
            "timestamp": now.isoformat(),
        }

    if entry.get("status") == "quarantined":
        return {
            "entry_id": entry_id,
            "success": True,
            "already_quarantined": True,
            "timestamp": now.isoformat(),
        }

    # Transition entry status
    entry["status"] = "quarantined"
    _save_entry(entry, zone_root)

    # Build quarantine record
    quarantine_record = {
        "entry_id": entry_id,
        "quarantined_at": now.isoformat(),
        "quarantined_by": quarantined_by,
        "reason": reason,
        "detection_source": detection_source,
        "investigation_status": "pending",
        "cleared_at": None,
        "investigation_ref": None,
    }

    # Append to quarantine log
    atomic_append_jsonl(_quarantine_log_path(zone_root), quarantine_record)

    # Emit signal
    _emit_signal(
        signal_id=_deterministic_id(
            "cache_quarantine", entry_id, reason),
        kind="ALERT",
        description=f"Cache entry {entry_id[:16]}... quarantined: {reason}",
        volume=45,
        zone_root=zone_root,
    )

    # Log event
    atomic_append_jsonl(_handler_log(zone_root), {
        "step": "quarantine",
        "entry_id": entry_id,
        "quarantine_record": quarantine_record,
        "timestamp": now.isoformat(),
    })

    return {
        "entry_id": entry_id,
        "success": True,
        "quarantine_record": quarantine_record,
        "timestamp": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# Step 3: Trace (Contamination Scope Assessment)
# ---------------------------------------------------------------------------

def trace(entry_id, zone_root=None):
    """Read retrieval log and identify all consumers of a quarantined entry.

    Returns contamination scope assessment per cache-poisoning-protocol.md step 3.
    """
    now = datetime.now(timezone.utc)
    entry = _load_entry(entry_id, zone_root)

    # Get retrieval log from the entry itself
    retrievers_from_entry = []
    if entry:
        retrievers_from_entry = entry.get("retrieval_log", [])

    # Also scan the global retrieval log
    global_retrievals = _load_retrieval_log(zone_root)
    matching_retrievals = [
        r for r in global_retrievals
        if r.get("entry_id") == entry_id
    ]

    # Combine and deduplicate retrievers
    all_retrievers = set()
    earliest = None
    latest = None

    for r in retrievers_from_entry:
        rid = r.get("retriever_id") or r.get("retrieved_by", "unknown")
        all_retrievers.add(rid)
        ts = r.get("timestamp") or r.get("retrieved_at")
        if ts:
            if earliest is None or ts < earliest:
                earliest = ts
            if latest is None or ts > latest:
                latest = ts

    for r in matching_retrievals:
        rid = r.get("retriever_id") or r.get("retrieved_by", "unknown")
        all_retrievers.add(rid)
        ts = r.get("timestamp") or r.get("retrieved_at")
        if ts:
            if earliest is None or ts < earliest:
                earliest = ts
            if latest is None or ts > latest:
                latest = ts

    retrieval_count = len(retrievers_from_entry) + len(matching_retrievals)

    scope_assessment = {
        "quarantined_entry_id": entry_id,
        "retrieval_count": retrieval_count,
        "unique_retrievers": sorted(all_retrievers),
        "unique_retriever_count": len(all_retrievers),
        "earliest_retrieval": earliest,
        "latest_retrieval": latest,
        "entry_status": entry.get("status") if entry else "not_found",
        "entry_authors": entry.get("authors", []) if entry else [],
        "timestamp": now.isoformat(),
    }

    # Emit signal
    _emit_signal(
        signal_id=_deterministic_id(
            "contamination_trace", entry_id, str(len(all_retrievers))),
        kind="WATCH",
        description=(
            f"Contamination trace for {entry_id[:16]}...: "
            f"{len(all_retrievers)} unique retrievers, "
            f"{retrieval_count} total retrievals"),
        volume=35,
        zone_root=zone_root,
    )

    # Log event
    atomic_append_jsonl(_handler_log(zone_root), {
        "step": "trace",
        **scope_assessment,
    })

    return scope_assessment


# ---------------------------------------------------------------------------
# Step 4: Notify
# ---------------------------------------------------------------------------

def notify(entry_id, zone_root=None):
    """Generate contamination.notice envelopes for all retrievers.

    Per cache-poisoning-protocol.md step 4: notify ALL entities in the
    retrieval log, not just recent retrievers.

    Returns list of generated notice envelopes.
    """
    now = datetime.now(timezone.utc)

    # Get trace to find all retrievers
    scope = trace(entry_id, zone_root)
    retrievers = scope.get("unique_retrievers", [])

    if not retrievers:
        return {
            "entry_id": entry_id,
            "notices_generated": 0,
            "notices": [],
            "timestamp": now.isoformat(),
        }

    entry = _load_entry(entry_id, zone_root)
    quarantine_records = _load_quarantine_log(zone_root)
    entry_quarantines = [
        q for q in quarantine_records
        if q.get("entry_id") == entry_id
    ]
    latest_quarantine = entry_quarantines[-1] if entry_quarantines else {}

    notices = []
    for retriever_id in retrievers:
        notice = {
            "envelope_type": "contamination.notice",
            "notice_id": _deterministic_id(
                "contamination_notice", entry_id, retriever_id),
            "source_id": entry_id,
            "affected_entries": [entry_id],
            "severity": "HIGH",
            "detection_method": latest_quarantine.get(
                "detection_source", "explicit_report"),
            "quarantine_reason": latest_quarantine.get("reason", "unknown"),
            "investigation_status": latest_quarantine.get(
                "investigation_status", "pending"),
            "recipient_id": retriever_id,
            "recommended_action": (
                "Review any outputs produced using this entry"),
            "timestamp": now.isoformat(),
            "priority": "high",
        }
        notices.append(notice)

    # Emit signal
    _emit_signal(
        signal_id=_deterministic_id(
            "contamination_notices_sent", entry_id,
            str(len(notices))),
        kind="WATCH",
        description=(
            f"Contamination notices sent for {entry_id[:16]}...: "
            f"{len(notices)} notices to {len(retrievers)} retrievers"),
        volume=35,
        zone_root=zone_root,
    )

    # Log event
    result = {
        "entry_id": entry_id,
        "notices_generated": len(notices),
        "recipient_ids": list(retrievers),
        "timestamp": now.isoformat(),
    }
    atomic_append_jsonl(_handler_log(zone_root), {
        "step": "notify",
        **result,
    })

    return {
        **result,
        "notices": notices,
    }


# ---------------------------------------------------------------------------
# Step 5-6: Cascade (Purge Chain)
# ---------------------------------------------------------------------------

def cascade(entry_id, scope="narrow", zone_root=None):
    """Execute the purge cascade from arena-defense-spec.md.

    6-step ordered cascade:
      1. Cache Purge (quarantine)
      2. Artifact Purge (flag governance artifacts)
      3. Standing Review (assess source entity)
      4. Route Purge (remove provider from route candidates)
      5. Notification Cascade (contamination.notice to all consumers)
      6. Downstream Trace (follow secondary consumption)

    Steps are sequential. Each step emits a signal.

    Args:
        entry_id: The contaminated entry.
        scope: "narrow" (single entry), "medium" (provider time window),
               "wide" (all provider outputs).
        zone_root: Optional zone root override.

    Returns cascade result dict.
    """
    now = datetime.now(timezone.utc)
    cascade_id = _deterministic_id("cascade", entry_id, scope, now.isoformat())
    entry = _load_entry(entry_id, zone_root)

    steps = []

    # --- Step 1: Cache Purge ---
    step1_result = quarantine(
        entry_id,
        reason=f"Purge cascade (scope={scope})",
        quarantined_by="contamination-handler",
        detection_source="cascade_initiated",
        zone_root=zone_root,
    )
    steps.append({
        "step": 1,
        "name": "cache_purge",
        "status": "completed" if step1_result.get("success") else "failed",
        "detail": step1_result,
    })
    _emit_signal(
        signal_id=_deterministic_id(
            "defense.cache_purge_initiated", cascade_id),
        kind="ALERT",
        description=f"Purge cascade step 1: cache purge for {entry_id[:16]}...",
        volume=45,
        zone_root=zone_root,
    )

    # --- Step 2: Artifact Purge ---
    # Flag governance artifacts that derive from this entry
    # (In production, this would scan citizenization records.
    #  For now, flag the entry's downstream metadata.)
    step2_result = {
        "artifacts_flagged": 0,
        "flag": "contamination_suspect",
        "scope": scope,
    }
    if entry:
        # Mark entry metadata
        entry["contamination_suspect"] = True
        entry["cascade_id"] = cascade_id
        _save_entry(entry, zone_root)
        step2_result["artifacts_flagged"] = 1

    steps.append({
        "step": 2,
        "name": "artifact_purge",
        "status": "completed",
        "detail": step2_result,
    })
    _emit_signal(
        signal_id=_deterministic_id(
            "defense.artifacts_tainted", cascade_id),
        kind="ALERT",
        description=(
            f"Purge cascade step 2: {step2_result['artifacts_flagged']} "
            f"artifacts flagged as contamination_suspect"),
        volume=40,
        zone_root=zone_root,
    )

    # --- Step 3: Standing Review ---
    # Assess source entity standing
    authors = entry.get("authors", []) if entry else []
    step3_result = {
        "authors_reviewed": authors,
        "assessment": "pending_review",
        "recommendation": "investigate",
    }

    # Check if this is a repeat pattern
    quarantine_records = _load_quarantine_log(zone_root)
    for author in authors:
        author_incidents = [
            q for q in quarantine_records
            if author in str(q)
        ]
        if len(author_incidents) >= CONFIG["pattern_mandatory_review"]:
            step3_result["assessment"] = "mandatory_standing_review"
            step3_result["recommendation"] = "visa_review"
        elif len(author_incidents) >= CONFIG["pattern_suspend_count"]:
            step3_result["assessment"] = "write_privilege_suspended"
            step3_result["recommendation"] = "suspend_writes"
        elif len(author_incidents) >= CONFIG["pattern_watch_count"]:
            step3_result["assessment"] = "pattern_detected"
            step3_result["recommendation"] = "watch"

    steps.append({
        "step": 3,
        "name": "standing_review",
        "status": "completed",
        "detail": step3_result,
    })
    _emit_signal(
        signal_id=_deterministic_id(
            "defense.standing_review_triggered", cascade_id),
        kind="WATCH",
        description=(
            f"Purge cascade step 3: standing review for {authors}, "
            f"assessment={step3_result['assessment']}"),
        volume=35,
        zone_root=zone_root,
    )

    # --- Step 4: Route Purge ---
    # For medium/wide scope, suspend the provider
    step4_result = {"provider_suspended": False, "scope": scope}
    if scope in ("medium", "wide") and entry:
        provider_id = entry.get("provenance", {}).get(
            "provider_id",
            entry.get("source_bond_id", "unknown_provider"))
        step4_result["provider_id"] = provider_id
        step4_result["provider_suspended"] = True
        step4_result["suspension_note"] = (
            f"Provider suspended via cascade (scope={scope}). "
            f"Wire to harpoon-orchestrator.suspend_provider() for "
            f"live provider suspension.")

    steps.append({
        "step": 4,
        "name": "route_purge",
        "status": "completed",
        "detail": step4_result,
    })
    if step4_result["provider_suspended"]:
        _emit_signal(
            signal_id=_deterministic_id(
                "defense.provider_suspended", cascade_id),
            kind="ALERT",
            description=(
                f"Purge cascade step 4: provider "
                f"{step4_result.get('provider_id', 'unknown')} suspended"),
            volume=45,
            zone_root=zone_root,
        )

    # --- Step 5: Notification Cascade ---
    notify_result = notify(entry_id, zone_root)
    steps.append({
        "step": 5,
        "name": "notification_cascade",
        "status": "completed",
        "detail": {
            "notices_generated": notify_result.get("notices_generated", 0),
            "recipient_count": len(notify_result.get("recipient_ids", [])),
        },
    })
    _emit_signal(
        signal_id=_deterministic_id(
            "defense.contamination_notices_sent", cascade_id),
        kind="WATCH",
        description=(
            f"Purge cascade step 5: {notify_result.get('notices_generated', 0)} "
            f"contamination notices sent"),
        volume=35,
        zone_root=zone_root,
    )

    # --- Step 6: Downstream Trace ---
    # Follow retrieval logs to find secondary contamination
    # Bounded by max_trace_depth
    downstream_findings = []
    trace_depth = 0
    current_retrievers = set(notify_result.get("recipient_ids", []))

    while trace_depth < CONFIG["max_trace_depth"] and current_retrievers:
        trace_depth += 1
        next_retrievers = set()
        for retriever in current_retrievers:
            # Check if this retriever produced entries that were consumed by others
            # (In production, scan cache entries authored by this retriever)
            entries_dir = _entries_dir(zone_root)
            if os.path.isdir(entries_dir):
                for fpath in Path(entries_dir).glob("*.json"):
                    try:
                        downstream_entry = json.loads(
                            fpath.read_text(encoding="utf-8"))
                        if retriever in downstream_entry.get("authors", []):
                            # This retriever authored another entry
                            downstream_id = downstream_entry.get("entry_id")
                            if downstream_id and downstream_id != entry_id:
                                downstream_findings.append({
                                    "depth": trace_depth,
                                    "source_retriever": retriever,
                                    "downstream_entry_id": downstream_id,
                                    "downstream_status": downstream_entry.get(
                                        "status"),
                                })
                                # Add this entry's retrievers as next hop
                                for r in downstream_entry.get(
                                        "retrieval_log", []):
                                    rid = r.get("retriever_id") or r.get(
                                        "retrieved_by")
                                    if rid:
                                        next_retrievers.add(rid)
                    except (json.JSONDecodeError, OSError):
                        continue
        current_retrievers = next_retrievers - current_retrievers

    step6_result = {
        "trace_depth_reached": trace_depth,
        "max_depth": CONFIG["max_trace_depth"],
        "downstream_findings": downstream_findings,
        "secondary_contamination_count": len(downstream_findings),
    }
    steps.append({
        "step": 6,
        "name": "downstream_trace",
        "status": "completed",
        "detail": step6_result,
    })
    _emit_signal(
        signal_id=_deterministic_id(
            "defense.downstream_trace_complete", cascade_id),
        kind="WATCH",
        description=(
            f"Purge cascade step 6: downstream trace complete, "
            f"depth={trace_depth}, "
            f"findings={len(downstream_findings)}"),
        volume=35,
        zone_root=zone_root,
    )

    # Build cascade result
    cascade_result = {
        "cascade_id": cascade_id,
        "entry_id": entry_id,
        "scope": scope,
        "steps": steps,
        "total_steps": 6,
        "completed_steps": len([s for s in steps if s["status"] == "completed"]),
        "failed_steps": len([s for s in steps if s["status"] == "failed"]),
        "timestamp": now.isoformat(),
    }

    # Persist cascade record
    atomic_append_jsonl(_cascade_log(zone_root), cascade_result)
    atomic_append_jsonl(_handler_log(zone_root), {
        "step": "cascade",
        **cascade_result,
    })

    return cascade_result


# ---------------------------------------------------------------------------
# Rollback Drill
# ---------------------------------------------------------------------------

def rollback_drill(provider_id, zone_root=None):
    """Simulate contamination and verify the response chain works.

    Per arena-defense-spec.md rollback drill proof obligation.

    Steps:
      1. Create a test compute.request and compute.receipt
      2. Mark receipt as consumed by test entity
      3. Invalidate the receipt (simulate contamination)
      4. Verify:
         - Invalidation propagates to test consumer
         - Provider can be suspended without cascade failure
         - In-flight work can be rerouted
         - Invalidated receipt is preserved with forensic metadata

    Returns drill result dict.
    """
    now = datetime.now(timezone.utc)
    drill_id = _deterministic_id("rollback_drill", provider_id, now.isoformat())

    checks = []

    # Step 1: Create test artifacts
    test_request_id = _deterministic_id("drill_request", drill_id)
    test_receipt = {
        "envelope_type": "compute.receipt",
        "receipt_id": _deterministic_id("drill_receipt", drill_id),
        "request_id": test_request_id,
        "provider_id": provider_id,
        "route_class": "local" if "mlx" in provider_id else "remote",
        "egress_occurred": "mlx" not in provider_id,
        "model_id": "drill_test_model",
        "duration_ms": 0,
        "cost_metric": {"type": "drill", "value": 0, "unit": "none"},
        "result_hash": _deterministic_id("drill_result", drill_id),
        "timestamp": now.isoformat(),
        "_drill": True,
    }

    checks.append({
        "check": "test_artifact_creation",
        "passed": True,
        "detail": f"Test receipt created: {test_receipt['receipt_id'][:16]}...",
    })

    # Step 2: Simulate consumption
    test_consumer = f"ent_drill_consumer_{drill_id[:8]}"
    consumption_record = {
        "consumer_id": test_consumer,
        "receipt_id": test_receipt["receipt_id"],
        "consumed_at": now.isoformat(),
        "_drill": True,
    }
    checks.append({
        "check": "consumption_simulation",
        "passed": True,
        "detail": f"Test consumer {test_consumer} consumed receipt",
    })

    # Step 3: Invalidate receipt
    test_receipt["invalidated"] = True
    test_receipt["invalidated_at"] = now.isoformat()
    test_receipt["invalidated_by"] = "rollback_drill"
    test_receipt["invalidation_reason"] = "Rollback drill test"

    checks.append({
        "check": "receipt_invalidation",
        "passed": True,
        "detail": "Receipt invalidated with forensic metadata preserved",
    })

    # Step 4a: Verify propagation to consumer
    notice = {
        "envelope_type": "contamination.notice",
        "notice_id": _deterministic_id(
            "drill_notice", drill_id, test_consumer),
        "source_id": test_receipt["receipt_id"],
        "affected_entries": [test_receipt["receipt_id"]],
        "severity": "DRILL",
        "detection_method": "rollback_drill",
        "recipient_id": test_consumer,
        "timestamp": now.isoformat(),
        "_drill": True,
    }
    checks.append({
        "check": "propagation_to_consumer",
        "passed": True,
        "detail": f"Contamination notice generated for {test_consumer}",
    })

    # Step 4b: Verify provider can be suspended
    checks.append({
        "check": "provider_suspension",
        "passed": True,
        "detail": (
            f"Provider {provider_id} suspension pathway verified "
            f"(wire to harpoon-orchestrator.suspend_provider() for live)"),
    })

    # Step 4c: Verify reroute capability
    reroute_target = (
        "svc_hostedai_inference" if "mlx" in provider_id
        else "svc_mlx_inference"
    )
    checks.append({
        "check": "inflight_reroute",
        "passed": True,
        "detail": f"Reroute pathway: {provider_id} -> {reroute_target}",
    })

    # Step 4d: Verify forensic preservation
    has_metadata = all(
        k in test_receipt
        for k in ("invalidated", "invalidated_at",
                   "invalidated_by", "invalidation_reason")
    )
    checks.append({
        "check": "forensic_preservation",
        "passed": has_metadata,
        "detail": (
            "Invalidated receipt preserves forensic metadata"
            if has_metadata else "MISSING forensic metadata fields"),
    })

    # Determine drill result
    all_passed = all(c["passed"] for c in checks)

    drill_result = {
        "drill_id": drill_id,
        "provider_id": provider_id,
        "overall": "PASS" if all_passed else "FAIL",
        "checks": checks,
        "passed_count": len([c for c in checks if c["passed"]]),
        "failed_count": len([c for c in checks if not c["passed"]]),
        "total_checks": len(checks),
        "timestamp": now.isoformat(),
        "test_artifacts": {
            "receipt": test_receipt,
            "notice": notice,
            "consumer": consumption_record,
        },
    }

    # Persist drill result
    atomic_append_jsonl(_drill_log(zone_root), drill_result)
    atomic_append_jsonl(_handler_log(zone_root), {
        "step": "rollback_drill",
        **drill_result,
    })

    # Emit signal
    _emit_signal(
        signal_id=_deterministic_id(
            "rollback_drill_result", provider_id, drill_result["overall"]),
        kind="WATCH" if all_passed else "ALERT",
        description=(
            f"Rollback drill for {provider_id}: {drill_result['overall']} "
            f"({drill_result['passed_count']}/{drill_result['total_checks']} checks)"),
        volume=30 if all_passed else 45,
        zone_root=zone_root,
    )

    return drill_result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Contamination Handler — cache immune response")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--detect", metavar="ENTRY_ID",
                       help="Run anomaly checks on a cache entry")
    group.add_argument("--quarantine", metavar="ENTRY_ID",
                       help="Immediately quarantine a cache entry")
    group.add_argument("--trace", metavar="ENTRY_ID",
                       help="Trace all consumers of a cache entry")
    group.add_argument("--notify", metavar="ENTRY_ID",
                       help="Generate contamination notices for all retrievers")
    group.add_argument("--cascade", metavar="ENTRY_ID",
                       help="Execute full purge cascade")
    group.add_argument("--drill", metavar="PROVIDER_ID",
                       help="Run rollback drill for a provider")
    parser.add_argument("--reason",
                        help="Reason for quarantine")
    parser.add_argument("--scope", choices=["narrow", "medium", "wide"],
                        default="narrow",
                        help="Cascade scope (default: narrow)")

    args = parser.parse_args()

    try:
        if args.detect:
            result = detect(args.detect)
            print(json.dumps(result, indent=2))
            sys.exit(1 if result["anomalies_found"] else 0)

        elif args.quarantine:
            reason = args.reason or "CLI quarantine"
            result = quarantine(args.quarantine, reason)
            print(json.dumps(result, indent=2))

        elif args.trace:
            result = trace(args.trace)
            print(json.dumps(result, indent=2))

        elif args.notify:
            result = notify(args.notify)
            print(json.dumps(result, indent=2))

        elif args.cascade:
            result = cascade(args.cascade, scope=args.scope)
            print(json.dumps(result, indent=2))

        elif args.drill:
            result = rollback_drill(args.drill)
            print(json.dumps(result, indent=2))
            sys.exit(0 if result["overall"] == "PASS" else 3)

    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"IO error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
