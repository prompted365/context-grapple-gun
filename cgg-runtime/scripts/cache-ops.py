#!/usr/bin/env python3
"""
cache-ops.py — Pen Pal Cache Operations (6th capability surface).

CRUD, trust-tier write gating, Tier 1 tag-intersection search,
cache refresh cycle, and poisoning detection for the pen pal cache.

Implements:
  - pen-pal-cache-spec.md (CacheEnvelope, trust-tier gating, 3-layer curation)
  - cache-poisoning-protocol.md (detection, quarantine, anomaly scanning)
  - cache-refresh-cycle-spec.md (6-step mandate cycle)
  - cache-search-tiers-spec.md (Tier 1 tag-intersection)

Usage:
    python cache-ops.py create --authors A,B --bond BOND --problem-shape PS \\
        --constraints C1,C2 --solution-pattern SP --content "..."
    python cache-ops.py read --entry-id ID
    python cache-ops.py quarantine --entry-id ID --reason "..." --by ENTITY
    python cache-ops.py deprecate --entry-id ID
    python cache-ops.py archive --entry-id ID
    python cache-ops.py search [--problem-shape PS] [--constraints C1,C2] \\
        [--solution-pattern SP]
    python cache-ops.py check-write --entity-id ENT --standing STANDING
    python cache-ops.py refresh-cycle [--tic N]
    python cache-ops.py detect-anomalies

Exit codes: 0=success, 1=validation error, 2=IO error, 3=data error.
"""

import argparse
import hashlib
import json
import os
import shutil
import statistics
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Allow importing from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path
from lib.atomic_append import atomic_append_jsonl, atomic_write_json

# ---------------------------------------------------------------------------
# PROVISIONAL CONFIG — all thresholds lack calibration evidence.
# ---------------------------------------------------------------------------
CONFIG = {
    # Trust scoring (PROVISIONAL)
    "initial_trust_score": 0.0,
    "trust_increment": 0.1,         # positive retrieval feedback
    "trust_decrement": 0.2,         # negative retrieval feedback
    "trust_decay_per_tic": 0.01,    # time-based decay
    "trust_floor": -1.0,            # below this -> quarantine review

    # TTL (PROVISIONAL)
    "default_ttl_days": 90,
    "ttl_warning_fraction": 0.20,   # 20% remaining -> flag for probe

    # Staleness archival (PROVISIONAL)
    "stale_archive_tics": 9,        # stale > N tics -> archive eligible

    # Search (PROVISIONAL)
    "match_threshold": 0.5,         # Tier 1 minimum match score

    # Retrieval log cap (PROVISIONAL)
    "retrieval_log_cap": 100,

    # Rate budgets per tic (PROVISIONAL — INV-CACHE-01)
    "rate_budget": {
        "student": 5,
        "resident": 20,
        "citizen": 50,
    },

    # Monopoly prevention (PROVISIONAL — INV-BIOME-02)
    "monopoly_threshold": 0.30,     # 30% of total entries
    "dampening_curve": {
        # contribution_pct_lower_bound -> write_rate_modifier
        0.0: 1.0,
        0.10: 0.75,
        0.20: 0.50,
        0.30: 0.10,
    },

    # Pending queue signal threshold (PROVISIONAL)
    "pending_queue_signal_depth": 50,

    # Search tier (Tier 1 only for now)
    "search_tier": "tier_1",
}

# Standing hierarchy — ordered from lowest to highest
STANDING_ORDER = ["guest", "tourist", "student", "resident", "citizen"]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _cache_root(project_dir=None):
    """Resolve pen-pal-cache audit directory."""
    zone_root = project_dir or resolve_zone_root()
    tz_config = load_ticzone(zone_root)
    al = audit_logs_path(zone_root, tz_config)
    return Path(al) / "biome" / "pen-pal-cache"


def _entries_dir(project_dir=None):
    d = _cache_root(project_dir) / "entries"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _archive_dir(project_dir=None):
    d = _cache_root(project_dir) / "archive"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_artifacts_dir(project_dir=None):
    d = _cache_root(project_dir) / "state-artifacts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _retrieval_log_path(project_dir=None):
    return _cache_root(project_dir) / "retrieval.jsonl"


def _quarantine_log_path(project_dir=None):
    return _cache_root(project_dir) / "quarantine.jsonl"


# ---------------------------------------------------------------------------
# Content-addressed entry ID
# ---------------------------------------------------------------------------

def compute_entry_id(bond_id, content, structural_signature):
    """SHA-256 of (bond_id + content + structural_signature).

    Content-addressed: identical inputs = identical entry_id.
    Spec says SHA-256 of structural_signature + content; we include bond_id
    per the task requirement for stronger dedup.
    """
    payload = json.dumps({
        "bond_id": bond_id,
        "content": content,
        "structural_signature": structural_signature,
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# CacheEnvelope CRUD
# ---------------------------------------------------------------------------

def create_entry(authors, structural_signature, content, bond_id,
                 creation_context="", contributing_federations=None,
                 project_dir=None):
    """Create a content-addressed CacheEnvelope entry.

    Returns the CacheEnvelope dict. Persists to entries/ directory.
    Raises ValueError on validation failure.
    """
    # INV-CACHE-03: provenance chain completeness
    if not authors or len(authors) < 2:
        raise ValueError("INV-CACHE-03: exactly 2 authors required")
    if not bond_id:
        raise ValueError("INV-CACHE-03: bond_id required")

    if not structural_signature or not structural_signature.get("problem_shape"):
        raise ValueError("structural_signature.problem_shape required")

    entry_id = compute_entry_id(bond_id, content, structural_signature)

    # Dedup: if entry already exists, return it
    entry_path = _entries_dir(project_dir) / f"{entry_id}.json"
    if entry_path.exists():
        return json.loads(entry_path.read_text(encoding="utf-8"))

    now = datetime.now(timezone.utc).isoformat()
    ttl = (datetime.now(timezone.utc) +
           timedelta(days=CONFIG["default_ttl_days"])).isoformat()

    envelope = {
        "entry_id": entry_id,
        "source_bond_id": bond_id,
        "authors": list(authors),
        "structural_signature": {
            "problem_shape": structural_signature.get("problem_shape", ""),
            "constraint_dimensions": structural_signature.get(
                "constraint_dimensions", []),
            "solution_pattern": structural_signature.get(
                "solution_pattern", ""),
        },
        "content": content,
        "trust_score": CONFIG["initial_trust_score"],
        "created_at": now,
        "ttl": ttl,
        "last_verified": now,
        "retrieval_count": 0,
        "retrieval_log": [],
        "provenance": {
            "origin": "collaborative",
            "contributing_federations": contributing_federations or [],
            "creation_context": creation_context,
        },
        "status": "active",
    }

    atomic_write_json(str(entry_path), envelope)
    return envelope


def read_entry(entry_id, project_dir=None):
    """Read a CacheEnvelope by entry_id. Returns dict or None."""
    entry_path = _entries_dir(project_dir) / f"{entry_id}.json"
    if not entry_path.exists():
        # Check archive
        archive_path = _archive_dir(project_dir) / f"{entry_id}.json"
        if archive_path.exists():
            return json.loads(archive_path.read_text(encoding="utf-8"))
        return None
    return json.loads(entry_path.read_text(encoding="utf-8"))


def _write_entry(entry, project_dir=None):
    """Write an entry back to disk (internal helper)."""
    entry_path = _entries_dir(project_dir) / f"{entry['entry_id']}.json"
    atomic_write_json(str(entry_path), entry)


def quarantine_entry(entry_id, reason, quarantined_by,
                     detection_source="explicit_report", project_dir=None):
    """Quarantine an entry. Returns updated entry or None if not found.

    Immediate action per cache-poisoning-protocol.md step 2.
    """
    entry = read_entry(entry_id, project_dir)
    if entry is None:
        return None

    now = datetime.now(timezone.utc).isoformat()
    entry["status"] = "quarantined"

    _write_entry(entry, project_dir)

    # Append to quarantine log
    quarantine_record = {
        "entry_id": entry_id,
        "quarantined_at": now,
        "quarantined_by": quarantined_by,
        "reason": reason,
        "detection_source": detection_source,
        "investigation_status": "pending",
        "cleared_at": None,
        "investigation_ref": None,
    }
    atomic_append_jsonl(str(_quarantine_log_path(project_dir)),
                        quarantine_record)

    return entry


def deprecate_entry(entry_id, project_dir=None):
    """Deprecate an entry. Returns updated entry or None."""
    entry = read_entry(entry_id, project_dir)
    if entry is None:
        return None
    if entry["status"] == "quarantined":
        # Quarantined entries cannot be deprecated — they must resolve first
        raise ValueError(
            "Cannot deprecate quarantined entry — resolve investigation first")
    entry["status"] = "deprecated"
    _write_entry(entry, project_dir)
    return entry


def archive_entry(entry_id, project_dir=None):
    """Archive an entry — move from entries/ to archive/.

    Returns updated entry or None. Quarantined entries cannot be archived.
    """
    entry_path = _entries_dir(project_dir) / f"{entry_id}.json"
    if not entry_path.exists():
        return None

    entry = json.loads(entry_path.read_text(encoding="utf-8"))
    if entry["status"] == "quarantined":
        raise ValueError(
            "Cannot archive quarantined entry — resolve investigation first")

    entry["status"] = "archived"
    archive_path = _archive_dir(project_dir) / f"{entry_id}.json"
    atomic_write_json(str(archive_path), entry)

    # Remove from active entries
    entry_path.unlink()
    return entry


# ---------------------------------------------------------------------------
# Trust-tier write gating
# ---------------------------------------------------------------------------

def check_write_permission(entity_id, standing):
    """Check write permission based on visitor standing.

    Returns dict with:
      allowed: bool
      mode: "denied" | "pending" | "direct"
      reason: str
    """
    standing_lower = standing.lower()

    if standing_lower in ("guest", "tourist"):
        return {
            "allowed": False,
            "mode": "denied",
            "reason": f"{standing} standing: no write access to pen pal cache",
        }

    if standing_lower == "student":
        return {
            "allowed": True,
            "mode": "pending",
            "reason": "Student standing: writes enter pending queue for review",
        }

    if standing_lower in ("resident", "citizen"):
        return {
            "allowed": True,
            "mode": "direct",
            "reason": f"{standing} standing: direct write access",
        }

    return {
        "allowed": False,
        "mode": "denied",
        "reason": f"Unknown standing '{standing}': denied by default",
    }


def check_curate_permission(entity_id, standing, entry):
    """Check curation permission.

    Resident: can curate own pair's entries only.
    Citizen: can curate any entry.
    """
    standing_lower = standing.lower()

    if standing_lower in ("guest", "tourist", "student"):
        return False, f"{standing} standing: no curation rights"

    if standing_lower == "resident":
        if entity_id in entry.get("authors", []):
            return True, "Resident: curating own pair's entry"
        return False, "Resident: can only curate own pair's entries"

    if standing_lower == "citizen":
        return True, "Citizen: can curate any entry"

    return False, f"Unknown standing '{standing}'"


# ---------------------------------------------------------------------------
# Tier 1 Search — tag-intersection on structural_signature
# ---------------------------------------------------------------------------

def _load_active_entries(project_dir=None):
    """Load all active (non-quarantined, non-archived) entries."""
    entries_dir = _entries_dir(project_dir)
    results = []
    for fpath in entries_dir.glob("*.json"):
        try:
            entry = json.loads(fpath.read_text(encoding="utf-8"))
            if entry.get("status") == "active":
                results.append(entry)
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _load_all_entries(project_dir=None):
    """Load ALL entries from entries/ regardless of status."""
    entries_dir = _entries_dir(project_dir)
    results = []
    for fpath in entries_dir.glob("*.json"):
        try:
            entry = json.loads(fpath.read_text(encoding="utf-8"))
            results.append(entry)
        except (json.JSONDecodeError, OSError):
            continue
    return results


def search(problem_shape=None, constraint_dimensions=None,
           solution_pattern=None, project_dir=None):
    """Tier 1 tag-intersection search on structural_signature.

    Returns matching entries sorted by (match_score DESC, trust_score DESC).
    Logs retrieval events to retrieval.jsonl.
    Quarantined entries are excluded.
    """
    if not problem_shape and not constraint_dimensions and not solution_pattern:
        return []

    entries = _load_active_entries(project_dir)
    scored = []

    for entry in entries:
        sig = entry.get("structural_signature", {})
        match_score = 0.0

        # Problem shape match: exact string match
        if problem_shape and sig.get("problem_shape") == problem_shape:
            match_score += 1.0

        # Constraint dimensions: intersection ratio
        if constraint_dimensions:
            entry_constraints = set(sig.get("constraint_dimensions", []))
            query_constraints = set(constraint_dimensions)
            if query_constraints:
                overlap = len(entry_constraints & query_constraints)
                match_score += overlap / len(query_constraints)

        # Solution pattern match: exact string match, +0.5
        if solution_pattern and sig.get("solution_pattern") == solution_pattern:
            match_score += 0.5

        if match_score >= CONFIG["match_threshold"]:
            scored.append((match_score, entry))

    # Sort by match_score DESC, then trust_score DESC
    scored.sort(key=lambda x: (x[0], x[1].get("trust_score", 0.0)),
                reverse=True)

    return [entry for _, entry in scored]


def log_retrieval(entry_id, retriever_id, context="", feedback=None,
                  project_dir=None):
    """Log a retrieval event to retrieval.jsonl.

    Also updates the entry's retrieval_count and inline retrieval_log
    (capped at retrieval_log_cap).
    """
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "entry_id": entry_id,
        "retriever_id": retriever_id,
        "timestamp": now,
        "context": context,
        "feedback": feedback,
    }
    atomic_append_jsonl(str(_retrieval_log_path(project_dir)), record)

    # Update entry inline retrieval log
    entry = read_entry(entry_id, project_dir)
    if entry and entry.get("status") != "archived":
        entry["retrieval_count"] = entry.get("retrieval_count", 0) + 1
        log = entry.get("retrieval_log", [])
        log.append(record)
        # Cap at configured depth
        if len(log) > CONFIG["retrieval_log_cap"]:
            log = log[-CONFIG["retrieval_log_cap"]:]
        entry["retrieval_log"] = log
        _write_entry(entry, project_dir)


# ---------------------------------------------------------------------------
# Cache refresh cycle (6-step mandate integration)
# ---------------------------------------------------------------------------

def refresh_cycle(tic=None, project_dir=None):
    """Execute the full 6-step cache refresh cycle.

    Returns the cache-state artifact dict. Persists to state-artifacts/.
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    signals_emitted = []

    all_entries = _load_all_entries(project_dir)

    # -----------------------------------------------------------------------
    # Step 1: TTL Scan
    # -----------------------------------------------------------------------
    entries_approaching_expiry = []
    entries_expired = []

    for entry in all_entries:
        if entry.get("status") != "active":
            continue
        ttl_str = entry.get("ttl")
        if not ttl_str:
            continue
        try:
            ttl_dt = datetime.fromisoformat(ttl_str)
        except (ValueError, TypeError):
            continue

        remaining = ttl_dt - now
        if remaining.total_seconds() <= 0:
            # Past TTL -> stale
            entry["status"] = "stale"
            _write_entry(entry, project_dir)
            entries_expired.append(entry["entry_id"])
        else:
            # Check warning window: 20% of original TTL remaining
            created_str = entry.get("created_at", "")
            try:
                created_dt = datetime.fromisoformat(created_str)
                original_ttl = ttl_dt - created_dt
                warning_window = original_ttl * CONFIG["ttl_warning_fraction"]
                if remaining <= warning_window:
                    entries_approaching_expiry.append(entry["entry_id"])
            except (ValueError, TypeError):
                pass

    if entries_expired:
        signals_emitted.append({
            "signal_id": _deterministic_signal_id(
                "cache.stale_entries_found", str(tic or 0)),
            "kind": "WATCH",
            "description": (f"TTL scan found {len(entries_expired)} "
                            f"expired entries"),
            "entry_ids": entries_expired,
        })

    # -----------------------------------------------------------------------
    # Step 2: Probe Dispatch (produces probe list — actual inbox delivery
    # is handled by the trigger router, not this script)
    # -----------------------------------------------------------------------
    probes_dispatched = len(entries_approaching_expiry)

    # -----------------------------------------------------------------------
    # Step 3: Trust Score Maintenance
    # -----------------------------------------------------------------------
    retrieval_path = _retrieval_log_path(project_dir)
    retrieval_events = []
    if retrieval_path.exists():
        for line in retrieval_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    retrieval_events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # Build feedback map: entry_id -> list of feedback events
    feedback_map = {}
    for evt in retrieval_events:
        eid = evt.get("entry_id")
        if eid:
            feedback_map.setdefault(eid, []).append(evt)

    quarantine_candidates = []
    for entry in all_entries:
        if entry.get("status") != "active":
            continue
        eid = entry["entry_id"]
        authors = set(entry.get("authors", []))

        # Apply retrieval feedback
        for evt in feedback_map.get(eid, []):
            retriever = evt.get("retriever_id", "")
            # Self-retrieval excluded from scoring
            if retriever in authors:
                continue
            fb = evt.get("feedback")
            if fb == "positive":
                entry["trust_score"] = entry.get("trust_score", 0.0) + \
                    CONFIG["trust_increment"]
            elif fb == "negative":
                entry["trust_score"] = entry.get("trust_score", 0.0) - \
                    CONFIG["trust_decrement"]

        # Time-based decay
        last_verified_str = entry.get("last_verified", "")
        try:
            last_verified = datetime.fromisoformat(last_verified_str)
            # Approximate tics as days for decay calculation
            days_since = (now - last_verified).total_seconds() / 86400
            decay = days_since * CONFIG["trust_decay_per_tic"]
            entry["trust_score"] = entry.get("trust_score", 0.0) - decay
        except (ValueError, TypeError):
            pass

        # Check trust floor
        if entry.get("trust_score", 0.0) < CONFIG["trust_floor"]:
            quarantine_candidates.append(entry)

        entry["last_verified"] = now_iso
        _write_entry(entry, project_dir)

    # Quarantine entries below trust floor
    for entry in quarantine_candidates:
        quarantine_entry(
            entry["entry_id"],
            reason=f"Trust score {entry['trust_score']:.2f} below floor "
                   f"{CONFIG['trust_floor']}",
            quarantined_by="system",
            detection_source="trust_anomaly",
            project_dir=project_dir,
        )
        signals_emitted.append({
            "signal_id": _deterministic_signal_id(
                "cache.quarantine_triggered", entry["entry_id"]),
            "kind": "ALERT",
            "description": (f"Entry {entry['entry_id'][:12]}... quarantined: "
                            f"trust below floor"),
        })

    # -----------------------------------------------------------------------
    # Step 4: Standing-Change Propagation
    # -----------------------------------------------------------------------
    standing_changes_processed = 0
    visa_registry_path = (_cache_root(project_dir).parent /
                          "visa-registry" / "registry.jsonl")
    if visa_registry_path.exists():
        # Load standing changes and check affected entries
        # (actual visa registry scanning is a stub — the registry format
        # is defined by the biome, not this script. We scan for entries
        # with authors whose standing may have changed.)
        pass

    # -----------------------------------------------------------------------
    # Step 5: Archive Pruning
    # -----------------------------------------------------------------------
    archived_this_cycle = 0
    # Reload entries after trust maintenance
    all_entries = _load_all_entries(project_dir)
    for entry in all_entries:
        status = entry.get("status")
        if status in ("deprecated", "stale"):
            # For stale: check if stale long enough
            # (approximation: use last_verified as staleness timestamp)
            if status == "stale":
                try:
                    lv = datetime.fromisoformat(
                        entry.get("last_verified", ""))
                    stale_days = (now - lv).total_seconds() / 86400
                    if stale_days < CONFIG["stale_archive_tics"]:
                        continue  # Not stale long enough
                except (ValueError, TypeError):
                    continue
            try:
                archive_entry(entry["entry_id"], project_dir)
                archived_this_cycle += 1
            except ValueError:
                pass  # Quarantined, skip

    # -----------------------------------------------------------------------
    # Step 6: Cache-State Artifact Production
    # -----------------------------------------------------------------------
    # Reload final state
    final_entries = _load_all_entries(project_dir)
    archived_entries = list(_archive_dir(project_dir).glob("*.json"))

    status_counts = {"active": 0, "stale": 0, "quarantined": 0,
                     "deprecated": 0}
    trust_scores = []
    author_counts = {}

    for entry in final_entries:
        s = entry.get("status", "active")
        if s in status_counts:
            status_counts[s] += 1
        ts = entry.get("trust_score", 0.0)
        trust_scores.append(ts)
        for author in entry.get("authors", []):
            author_counts[author] = author_counts.get(author, 0) + 1

    total = len(final_entries)

    # Monopoly check
    top_contributor = ""
    top_pct = 0.0
    if total > 0 and author_counts:
        top_contributor = max(author_counts, key=author_counts.get)
        top_pct = author_counts[top_contributor] / total

    dampening_active = top_pct >= 0.10  # Any dampening tier active

    if top_pct >= CONFIG["monopoly_threshold"]:
        signals_emitted.append({
            "signal_id": _deterministic_signal_id(
                "cache.monopoly_approaching", top_contributor),
            "kind": "WATCH",
            "description": (f"Entity {top_contributor} at "
                            f"{top_pct:.0%} of cache entries"),
        })

    # Pending queue depth (count entries in pending state if any)
    pending_count = sum(1 for e in final_entries
                        if e.get("status") == "pending")

    # Trust distribution
    trust_dist = {
        "mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0
    }
    if trust_scores:
        trust_dist = {
            "mean": round(statistics.mean(trust_scores), 4),
            "median": round(statistics.median(trust_scores), 4),
            "min": round(min(trust_scores), 4),
            "max": round(max(trust_scores), 4),
        }

    # Completion signal
    signals_emitted.append({
        "signal_id": _deterministic_signal_id(
            "cache.refresh_complete", str(tic or 0)),
        "kind": "INFO",
        "description": "Cache refresh cycle complete",
    })

    artifact = {
        "artifact_type": "cache_state",
        "produced_at": now_iso,
        "produced_by_tic": tic,
        "summary": {
            "total_entries": total,
            "active": status_counts["active"],
            "stale": status_counts["stale"],
            "quarantined": status_counts["quarantined"],
            "deprecated": status_counts["deprecated"],
            "archived_this_cycle": archived_this_cycle,
            "pending_queue_depth": pending_count,
        },
        "trust_distribution": trust_dist,
        "search_tier_in_use": CONFIG["search_tier"],
        "monopoly_check": {
            "top_contributor_entity": top_contributor,
            "top_contributor_percentage": round(top_pct, 4),
            "dampening_active": dampening_active,
        },
        "ttl_health": {
            "entries_approaching_expiry": len(entries_approaching_expiry),
            "probes_dispatched": probes_dispatched,
            "probes_responded": 0,  # Probes are async — response tracked later
            "entries_expired_this_cycle": len(entries_expired),
        },
        "standing_changes_processed": standing_changes_processed,
        "signals_emitted": [s["signal_id"] for s in signals_emitted],
    }

    # Persist artifact
    tic_label = tic if tic is not None else now.strftime("%Y%m%dT%H%M%S")
    artifact_path = (_state_artifacts_dir(project_dir) /
                     f"{tic_label}-cache-state.json")
    atomic_write_json(str(artifact_path), artifact)

    return artifact


# ---------------------------------------------------------------------------
# Poisoning detection
# ---------------------------------------------------------------------------

def detect_anomalies(project_dir=None):
    """Scan for cache poisoning indicators.

    Checks:
    1. Trust score anomalies (entries with score below floor)
    2. Content-signature drift (placeholder — requires semantic check)
    3. Retrieval pattern anomalies (single source with many quarantines)

    Returns list of anomaly dicts. On detection: quarantine + signal.
    """
    anomalies = []
    all_entries = _load_all_entries(project_dir)

    # 1. Trust score anomalies — active entries below floor
    for entry in all_entries:
        if entry.get("status") != "active":
            continue
        ts = entry.get("trust_score", 0.0)
        if ts < CONFIG["trust_floor"]:
            anomalies.append({
                "type": "trust_anomaly",
                "entry_id": entry["entry_id"],
                "trust_score": ts,
                "floor": CONFIG["trust_floor"],
            })
            quarantine_entry(
                entry["entry_id"],
                reason=f"Anomaly detection: trust {ts:.2f} < {CONFIG['trust_floor']}",
                quarantined_by="system",
                detection_source="trust_anomaly",
                project_dir=project_dir,
            )

    # 2. Content-signature drift — check if problem_shape appears in content
    #    (structural check per INV-CACHE-02, not deep semantic)
    for entry in all_entries:
        if entry.get("status") != "active":
            continue
        sig = entry.get("structural_signature", {})
        content = entry.get("content", "").lower()
        ps = sig.get("problem_shape", "").lower()
        if ps and ps not in content:
            anomalies.append({
                "type": "signature_drift",
                "entry_id": entry["entry_id"],
                "problem_shape": sig.get("problem_shape"),
                "detail": "problem_shape not found in content",
            })

    # 3. Source pattern anomalies — check quarantine log for repeated sources
    quarantine_path = _quarantine_log_path(project_dir)
    source_quarantine_counts = {}
    if quarantine_path.exists():
        for line in quarantine_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                eid = record.get("entry_id")
                # Look up the entry to find authors
                entry = read_entry(eid, project_dir)
                if entry:
                    for author in entry.get("authors", []):
                        source_quarantine_counts[author] = \
                            source_quarantine_counts.get(author, 0) + 1
            except json.JSONDecodeError:
                continue

    for source, count in source_quarantine_counts.items():
        if count >= 2:
            anomalies.append({
                "type": "source_pattern",
                "entity_id": source,
                "quarantine_count": count,
                "action": ("write_suspended" if count >= 3
                           else "watch_emitted"),
            })

    return anomalies


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deterministic_signal_id(condition, discriminator):
    """Produce a deterministic signal ID per CGG Signal ID Determinism.

    Content-hash based: same condition + discriminator = same ID.
    """
    payload = f"{condition}:{discriminator}"
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"sig_{condition}_{h}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser():
    # Shared args inherited by every subcommand
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--project-dir", default=None,
                        help="Override zone root discovery")
    shared.add_argument("--json", action="store_true",
                        help="Output as JSON")

    p = argparse.ArgumentParser(
        prog="cache-ops",
        description="Pen Pal Cache Operations — 6th capability surface",
        parents=[shared],
    )
    sub = p.add_subparsers(dest="command", required=True)

    # create
    c = sub.add_parser("create", help="Create a cache entry",
                       parents=[shared])
    c.add_argument("--authors", required=True,
                   help="Comma-separated author entity IDs")
    c.add_argument("--bond", required=True, help="Bond ID")
    c.add_argument("--problem-shape", required=True)
    c.add_argument("--constraints", default="",
                   help="Comma-separated constraint dimensions")
    c.add_argument("--solution-pattern", default="")
    c.add_argument("--content", required=True)
    c.add_argument("--context", default="",
                   help="Creation context (biome act/cycle)")
    c.add_argument("--federations", default="",
                   help="Comma-separated contributing federation IDs")

    # read
    r = sub.add_parser("read", help="Read a cache entry",
                       parents=[shared])
    r.add_argument("--entry-id", required=True)

    # quarantine
    q = sub.add_parser("quarantine", help="Quarantine an entry",
                       parents=[shared])
    q.add_argument("--entry-id", required=True)
    q.add_argument("--reason", required=True)
    q.add_argument("--by", required=True, help="Entity performing quarantine")
    q.add_argument("--detection-source", default="explicit_report",
                   choices=["trust_anomaly", "signature_drift",
                            "explicit_report", "source_pattern",
                            "downstream_failure"])

    # deprecate
    d = sub.add_parser("deprecate", help="Deprecate an entry",
                       parents=[shared])
    d.add_argument("--entry-id", required=True)

    # archive
    a = sub.add_parser("archive", help="Archive an entry",
                       parents=[shared])
    a.add_argument("--entry-id", required=True)

    # search
    s = sub.add_parser("search", help="Tier 1 tag-intersection search",
                       parents=[shared])
    s.add_argument("--problem-shape", default=None)
    s.add_argument("--constraints", default="",
                   help="Comma-separated constraint dimensions")
    s.add_argument("--solution-pattern", default=None)

    # check-write
    cw = sub.add_parser("check-write",
                        help="Check write permission for entity",
                        parents=[shared])
    cw.add_argument("--entity-id", required=True)
    cw.add_argument("--standing", required=True,
                    choices=["guest", "tourist", "student",
                             "resident", "citizen"])

    # refresh-cycle
    rc = sub.add_parser("refresh-cycle",
                        help="Run cache refresh mandate cycle",
                        parents=[shared])
    rc.add_argument("--tic", type=int, default=None)

    # detect-anomalies
    sub.add_parser("detect-anomalies",
                   help="Scan for poisoning anomalies",
                   parents=[shared])

    return p


def main():
    parser = _build_parser()
    args = parser.parse_args()
    project_dir = args.project_dir

    try:
        if args.command == "create":
            authors = [a.strip() for a in args.authors.split(",")
                       if a.strip()]
            constraints = [c.strip() for c in args.constraints.split(",")
                           if c.strip()]
            federations = [f.strip() for f in args.federations.split(",")
                           if f.strip()]
            sig = {
                "problem_shape": args.problem_shape,
                "constraint_dimensions": constraints,
                "solution_pattern": args.solution_pattern,
            }
            result = create_entry(
                authors=authors,
                structural_signature=sig,
                content=args.content,
                bond_id=args.bond,
                creation_context=args.context,
                contributing_federations=federations,
                project_dir=project_dir,
            )
            _output(result, args.json)

        elif args.command == "read":
            result = read_entry(args.entry_id, project_dir)
            if result is None:
                print(f"Entry not found: {args.entry_id}", file=sys.stderr)
                sys.exit(1)
            _output(result, args.json)

        elif args.command == "quarantine":
            result = quarantine_entry(
                args.entry_id, args.reason, args.by,
                detection_source=args.detection_source,
                project_dir=project_dir,
            )
            if result is None:
                print(f"Entry not found: {args.entry_id}", file=sys.stderr)
                sys.exit(1)
            _output(result, args.json)

        elif args.command == "deprecate":
            result = deprecate_entry(args.entry_id, project_dir)
            if result is None:
                print(f"Entry not found: {args.entry_id}", file=sys.stderr)
                sys.exit(1)
            _output(result, args.json)

        elif args.command == "archive":
            result = archive_entry(args.entry_id, project_dir)
            if result is None:
                print(f"Entry not found: {args.entry_id}", file=sys.stderr)
                sys.exit(1)
            _output(result, args.json)

        elif args.command == "search":
            constraints = [c.strip() for c in args.constraints.split(",")
                           if c.strip()] if args.constraints else None
            results = search(
                problem_shape=args.problem_shape,
                constraint_dimensions=constraints,
                solution_pattern=args.solution_pattern,
                project_dir=project_dir,
            )
            _output({"count": len(results), "entries": results}, args.json)

        elif args.command == "check-write":
            result = check_write_permission(args.entity_id, args.standing)
            _output(result, args.json)

        elif args.command == "refresh-cycle":
            result = refresh_cycle(tic=args.tic, project_dir=project_dir)
            _output(result, args.json)

        elif args.command == "detect-anomalies":
            results = detect_anomalies(project_dir)
            _output({"anomalies": results, "count": len(results)}, args.json)

    except ValueError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"IO error: {e}", file=sys.stderr)
        sys.exit(2)


def _output(data, as_json=False):
    """Print result to stdout."""
    if as_json or not sys.stdout.isatty():
        print(json.dumps(data, indent=2))
    else:
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
