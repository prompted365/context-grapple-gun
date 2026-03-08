#!/usr/bin/env python3
"""
Pattern Miner — topology-aware recurrence detection for governance artifacts.

Reads CPR queue, signals, and participation data. Detects recurring patterns
across sessions, subsystems, and rungs. Writes pattern recurrence events to
audit-logs/patterns/YYYY-MM-DD.jsonl.

Classifies recurrence with rung context:
  - site_local: repeated within one site
  - cross_site_same_domain: repeated across sibling sites in same domain
  - cross_domain_same_estate: repeated across domains in same estate
  - cross_estate: repeated across estates

This script is the canonical authority for recurrence detection. The enrichment
scanner imports from it rather than maintaining its own inline logic.

Usage:
    python3 pattern-miner.py --project-dir /path/to/zone
    python3 pattern-miner.py --project-dir /path/to/zone --dry-run
    python3 pattern-miner.py --project-dir /path/to/zone --json
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, birth_topology


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_queue(queue_path):
    """Load CPR queue (latest-entry-per-ID-wins). Returns dict of id->entry."""
    entries = {}
    p = Path(queue_path)
    if not p.exists():
        return entries
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            eid = d.get("id", "")
            if eid:
                entries[eid] = d
        except json.JSONDecodeError:
            continue
    return entries


def load_signal_store(signal_dir):
    """Load latest-per-ID signal state from all JSONL files."""
    entries = {}
    sd = Path(signal_dir)
    if not sd.exists():
        return entries
    for f in sorted(sd.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                sid = d.get("id", "")
                if sid:
                    entries[sid] = d
            except json.JSONDecodeError:
                continue
    return entries


def load_existing_patterns(patterns_dir):
    """Load existing pattern records (latest-per-ID-wins)."""
    entries = {}
    pd = Path(patterns_dir)
    if not pd.exists():
        return entries
    for f in sorted(pd.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                pid = d.get("id", "")
                if pid:
                    entries[pid] = d
            except json.JSONDecodeError:
                continue
    return entries


# ---------------------------------------------------------------------------
# Recurrence detection
# ---------------------------------------------------------------------------

def compute_word_overlap(text_a, text_b):
    """Compute Jaccard word overlap between two texts. Returns float in [0, 1]."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if len(words_a) < 3 or len(words_b) < 3:
        return 0.0
    total = len(words_a | words_b)
    if total == 0:
        return 0.0
    return len(words_a & words_b) / total


def classify_recurrence_scope(observations):
    """Classify recurrence scope from observation rung set.

    Returns (recurrence_kind, recurrence_scope, placement_target).
    """
    rungs = {obs.get("rung", "unknown") for obs in observations}
    subsystems = {obs.get("subsystem", "") for obs in observations}
    scope_paths = {obs.get("scope_path") for obs in observations if obs.get("scope_path")}

    if len(scope_paths) > 1:
        # Different paths — check if rungs differ
        if "estate" in rungs or "federation" in rungs:
            return "cross_domain_same_estate", "estate", "estate"
        if "domain" in rungs:
            return "cross_site_same_domain", "domain", "domain"

    if len(subsystems) > 1:
        return "cross_subsystem", "site", "site"

    return "site_local", "site", "site"


def gather_recurrence(cpr_id, cpr, queue_entries):
    """Find CPRs with similar lessons (canonical recurrence detection).

    Returns list of observation dicts for matching CPRs.
    """
    lesson = cpr.get("lesson", "")
    if not lesson:
        return []

    observations = []
    for eid, entry in queue_entries.items():
        if eid == cpr_id:
            continue
        other_lesson = entry.get("lesson", "")
        if not other_lesson:
            continue
        overlap = compute_word_overlap(lesson, other_lesson)
        if overlap >= 0.3:
            observations.append({
                "id": eid,
                "rung": entry.get("birth_rung", "unknown"),
                "scope_path": entry.get("birth_scope_path"),
                "subsystem": entry.get("subsystem", ""),
                "overlap": round(overlap, 3),
            })

    return observations


def gather_signal_recurrence(cpr, signals):
    """Find signals related to this CPR's subsystem."""
    subsystem = cpr.get("subsystem", "")
    if not subsystem:
        return []

    observations = []
    for sid, sig in signals.items():
        if sig.get("subsystem") != subsystem:
            continue
        if sig.get("status") not in ("active", "working", "acknowledged"):
            continue
        observations.append({
            "id": sid,
            "rung": sig.get("birth_rung", "unknown"),
            "scope_path": None,
            "subsystem": subsystem,
            "kind": sig.get("kind", ""),
        })

    return observations


# ---------------------------------------------------------------------------
# Pattern mining pipeline
# ---------------------------------------------------------------------------

def mine_patterns(project_dir, dry_run=False):
    """Main mining pipeline: detect recurrence, classify, write patterns."""
    project_dir = os.path.abspath(project_dir)
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)
    topo = birth_topology(project_dir)

    queue_path = os.path.join(al_path, "cprs", "queue.jsonl")
    signal_dir = os.path.join(al_path, "signals")
    patterns_dir = os.path.join(al_path, "patterns")

    queue = load_queue(queue_path)
    signals = load_signal_store(signal_dir)
    existing_patterns = load_existing_patterns(patterns_dir)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    patterns_file = os.path.join(patterns_dir, f"{date_str}.jsonl")

    new_patterns = []

    # For each CPR, check for recurrence across the queue
    for cpr_id, cpr in queue.items():
        lesson = cpr.get("lesson", "")
        if not lesson:
            continue

        # Gather observations from queue + signals
        queue_obs = gather_recurrence(cpr_id, cpr, queue)
        signal_obs = gather_signal_recurrence(cpr, signals)

        all_obs = queue_obs + signal_obs
        if not all_obs:
            continue

        # Include the source CPR itself as an observation
        all_obs_with_self = [{
            "id": cpr_id,
            "rung": cpr.get("birth_rung", "unknown"),
            "scope_path": cpr.get("birth_scope_path"),
            "subsystem": cpr.get("subsystem", ""),
        }] + all_obs

        # Classify recurrence scope
        rec_kind, rec_scope, placement = classify_recurrence_scope(all_obs_with_self)

        # Compute stable pattern ID from lesson hash
        pattern_hash = hashlib.sha256(
            f"pattern:{cpr.get('subsystem', '')}:{lesson[:100]}".encode()
        ).hexdigest()[:16]
        pattern_id = f"pat_{pattern_hash}"

        # Check if this pattern already exists
        existing = existing_patterns.get(pattern_id)
        prev_count = existing.get("observation_count", 0) if existing else 0
        new_count = len(all_obs) + 1  # +1 for source CPR

        # Only emit if count increased or pattern is new
        if existing and new_count <= prev_count:
            continue

        # Determine confidence tier from observation count
        if new_count >= 5:
            confidence = "convergent"
        elif new_count >= 3:
            confidence = "reinforced"
        else:
            confidence = "tentative"

        # Get tic context
        first_tic = cpr.get("birth_tic", 0)
        if existing:
            first_tic = existing.get("first_observed_tic", first_tic)
        last_tic = max(
            (obs_entry.get("birth_tic", 0)
             for obs_entry in [queue.get(o["id"], {}) for o in queue_obs] + [cpr]
             if obs_entry),
            default=0,
        )

        pattern = {
            "type": "pattern_recurrence",
            "id": pattern_id,
            "pattern": lesson[:200],
            "subsystem": cpr.get("subsystem", ""),
            "recurrence_kind": rec_kind,
            "recurrence_scope": rec_scope,
            "observed_in": [
                {"id": o["id"], "rung": o["rung"], "subsystem": o.get("subsystem", "")}
                for o in all_obs_with_self[:10]
            ],
            "observation_count": new_count,
            "first_observed_tic": first_tic,
            "last_observed_tic": last_tic,
            "placement_target": placement,
            "confidence_tier": confidence,
            "status": "observed",
            "birth_rung": topo["birth_rung"],
            "created_at": now.isoformat(),
            "source_cpr": cpr_id,
        }

        new_patterns.append(pattern)
        existing_patterns[pattern_id] = pattern

    # Write patterns
    if new_patterns and not dry_run:
        os.makedirs(patterns_dir, exist_ok=True)
        with open(patterns_file, "a", encoding="utf-8") as f:
            for pat in new_patterns:
                f.write(json.dumps(pat, separators=(",", ":")) + "\n")

    # Emit proposal envelopes for patterns crossing the threshold
    envelopes = []
    if new_patterns and not dry_run:
        envelopes = emit_pattern_envelopes(new_patterns, queue_path, topo)

    return new_patterns, envelopes


# ---------------------------------------------------------------------------
# Proposal envelope emission
# ---------------------------------------------------------------------------

ENVELOPE_THRESHOLD_COUNT = 3
ENVELOPE_THRESHOLD_SCOPES = {"domain", "estate", "federation"}


def emit_pattern_envelopes(patterns, queue_path, topo):
    """Emit proposal envelopes for patterns crossing review threshold.

    Threshold: observation_count >= 3 OR recurrence_scope is domain+.
    Writes to the CPR queue as extracted entries with artifact_kind: pattern_recurrence.
    """
    now = datetime.now(timezone.utc).isoformat()
    envelopes = []

    for pat in patterns:
        count = pat.get("observation_count", 0)
        scope = pat.get("recurrence_scope", "site")

        if count < ENVELOPE_THRESHOLD_COUNT and scope not in ENVELOPE_THRESHOLD_SCOPES:
            continue

        # Determine lesson type from pattern characteristics
        pattern_text = pat.get("pattern", "")
        if any(kw in pattern_text.lower() for kw in ["governance", "protocol", "invariant", "rule"]):
            lesson_type = "meta"
        elif any(kw in pattern_text.lower() for kw in ["workflow", "process", "pipeline", "step"]):
            lesson_type = "process"
        else:
            lesson_type = "subject"

        envelope = {
            "type": "cpr",
            "id": f"cpr_{pat['id'][4:]}",  # pat_xxx -> cpr_xxx
            "dedup_hash": pat["id"][4:],
            "status": "extracted",
            "lesson": pat["pattern"],
            "source": f"pattern_miner:{pat['id']}",
            "source_date": now[:10],
            "band": "COGNITIVE",
            "motivation_layer": "COGNITIVE",
            "subsystem": pat.get("subsystem", ""),
            "recommended_scopes": [],
            "birth_tic": pat.get("last_observed_tic", 0),
            "birth_rung": topo["birth_rung"],
            "birth_scope_path": topo["birth_scope_path"],
            "extracted_at": now,
            "extracted_by": "pattern-miner",
            "source_file": "pattern_miner.py",
            "proposal_envelope": {
                "artifact_kind": "pattern_recurrence",
                "lesson_type": lesson_type,
                "confidence_tier": pat.get("confidence_tier", "tentative"),
                "relations": {
                    "supports": [],
                    "contradicts": [],
                    "refines": [],
                    "supersedes": [],
                    "depends_on": [],
                },
                "capture_policy": {
                    "persist_locally": True,
                    "route_to_review": True,
                    "route_to_governance": False,
                    "allow_signal_emission": pat.get("confidence_tier") in ("reinforced", "convergent"),
                    "allow_warrant_generation": False,
                },
                "evidence": {
                    "sources": [pat["id"]],
                    "supporting_artifacts": [o["id"] for o in pat.get("observed_in", [])[:5]],
                    "independent_confirmations": pat.get("observation_count", 0),
                },
                "routing": {
                    "review_required": True,
                    "promotion_target": pat.get("placement_target", "site"),
                    "promotion_blockers": [],
                },
                "placement": {
                    "suggested_rung": pat.get("placement_target", "site"),
                    "suggested_target": "CLAUDE.md",
                    "reason": f"Recurs across {count} observations ({pat.get('recurrence_kind', 'unknown')})",
                },
                "payload": {
                    "pattern_id": pat["id"],
                    "recurrence_kind": pat.get("recurrence_kind", ""),
                    "recurrence_scope": scope,
                    "observation_count": count,
                    "summary": pat["pattern"][:200],
                },
            },
        }

        envelopes.append(envelope)

    # Write envelopes to CPR queue
    if envelopes:
        os.makedirs(os.path.dirname(queue_path), exist_ok=True)
        with open(queue_path, "a", encoding="utf-8") as f:
            for env in envelopes:
                f.write(json.dumps(env, separators=(",", ":")) + "\n")

    return envelopes


# ---------------------------------------------------------------------------
# Public API for enrichment scanner import
# ---------------------------------------------------------------------------

def gather_recurrence_count(cpr, queue_entries):
    """Count recurrence for a single CPR against the queue.

    Drop-in replacement for the inline implementation formerly in
    cpr-enrichment-scanner.py. Returns list of evidence dicts.
    """
    cpr_id = cpr.get("id", "")
    observations = gather_recurrence(cpr_id, cpr, queue_entries)

    if not observations:
        return []

    return [{
        "evidence_type": "recurrence_count",
        "value": f"{len(observations)} similar CPRs detected",
        "detail": [o["id"] for o in observations[:5]],
    }]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Pattern Miner — topology-aware recurrence detection"
    )
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect patterns without writing")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Output structured JSON")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    project_dir = args.project_dir or resolve_zone_root()
    patterns, envelopes = mine_patterns(project_dir, dry_run=args.dry_run)

    if args.output_json:
        print(json.dumps({
            "patterns": patterns,
            "count": len(patterns),
            "envelopes_emitted": len(envelopes),
        }, indent=2))
    elif not args.quiet:
        if patterns:
            for p in patterns:
                print(f"  {p['id']}: {p['pattern'][:60]}... "
                      f"({p['recurrence_kind']}, {p['observation_count']} obs, "
                      f"{p['confidence_tier']})")
        if envelopes:
            print(f"  → {len(envelopes)} proposal envelope(s) emitted to queue")
        print(len(patterns))

    return 0


if __name__ == "__main__":
    sys.exit(main())
