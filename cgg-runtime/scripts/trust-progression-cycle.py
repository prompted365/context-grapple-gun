#!/usr/bin/env python3
"""
trust-progression-cycle.py — Biome→Trust→Standing integration loop.

Called after each biome cycle to:
  1. Compute trust_score for all active visitors
  2. Check standing transition eligibility
  3. Auto-promote visitors through automated gates
  4. Emit signals for gates requiring review (steward/constitutional)
  5. Update agent-index.json with standing changes

This closes the dry-run loop: biome emits interactions → this script
reads them → standing engine computes trust → eligible visitors promote.

Usage:
  python3 trust-progression-cycle.py                    # run for all active visitors
  python3 trust-progression-cycle.py --entity <id>      # run for one visitor
  python3 trust-progression-cycle.py --dry-run           # compute but don't promote
  python3 trust-progression-cycle.py --verbose           # detailed output

Integration:
  Called from biome-engine.py advance_cycle() after save_state().
  Can also be called standalone for manual trust assessment.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Path resolution — same pattern as biome-engine.py and standing-engine.py
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def resolve_zone_root():
    """Walk up from cwd to find .ticzone."""
    d = os.getcwd()
    while d != "/":
        if os.path.isfile(os.path.join(d, ".ticzone")):
            return d
        d = os.path.dirname(d)
    # Fallback: two levels up from scripts/
    return os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))


def audit_logs_path(zone_root):
    """Resolve audit-logs directory."""
    ticzone_path = os.path.join(zone_root, ".ticzone")
    if os.path.isfile(ticzone_path):
        try:
            tz = json.loads(open(ticzone_path).read())
            al = tz.get("audit_logs_path")
            if al:
                return os.path.join(zone_root, al) if not os.path.isabs(al) else al
        except (json.JSONDecodeError, OSError):
            pass
    return os.path.join(zone_root, "audit-logs")


ZONE_ROOT = resolve_zone_root()
AUDIT_ROOT = audit_logs_path(ZONE_ROOT)
BIOME_STATE_DIR = os.path.join(AUDIT_ROOT, "biome", "state")
REGISTRY_PATH = os.path.join(AUDIT_ROOT, "biome", "visa-registry", "registry.jsonl")
AGENT_INDEX_PATH = os.path.join(AUDIT_ROOT, "biome", "visa-registry", "agent-index.json")
DEMOTION_WATCH_PATH = os.path.join(AUDIT_ROOT, "biome", "visa-registry", "demotion-watch.json")
SIGNALS_DIR = os.path.join(AUDIT_ROOT, "signals")


# ---------------------------------------------------------------------------
# Import standing engine functions
# ---------------------------------------------------------------------------

# standing-engine.py uses hyphens — import via importlib
import importlib.util
_se_path = os.path.join(SCRIPT_DIR, "standing-engine.py")
_spec = importlib.util.spec_from_file_location("standing_engine", _se_path)
_se = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_se)

compute_trust_score = _se.compute_trust_score
check_transition_eligibility = _se.check_transition_eligibility
compute_behavioral_diversity = _se.compute_behavioral_diversity
compute_endorser_penalty = _se.compute_endorser_penalty
SE_CONFIG = _se.CONFIG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def iso_now():
    return datetime.now(timezone.utc).isoformat()


def load_organisms():
    path = os.path.join(BIOME_STATE_DIR, "organisms.json")
    if not os.path.isfile(path):
        return {"visitors": []}
    with open(path) as f:
        return json.load(f)


def load_agent_index():
    if not os.path.isfile(AGENT_INDEX_PATH):
        return {"visitors_by_standing": {}, "active_count": 0, "total_registered": 0}
    with open(AGENT_INDEX_PATH) as f:
        return json.load(f)


def save_agent_index(idx):
    idx["last_rebuilt"] = iso_now()
    tmp = AGENT_INDEX_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(idx, f, indent=2)
        f.write("\n")
    os.replace(tmp, AGENT_INDEX_PATH)


def atomic_append_jsonl(path, record):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def emit_signal(signal_type, data):
    """Emit a signal to today's signal log."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(SIGNALS_DIR, f"{today}.jsonl")
    record = {
        "signal_type": signal_type,
        "timestamp": iso_now(),
        **data,
    }
    atomic_append_jsonl(path, record)


def update_organisms_standing(visitor_id, new_standing):
    """Update a visitor's standing in organisms.json."""
    path = os.path.join(BIOME_STATE_DIR, "organisms.json")
    with open(path) as f:
        organisms = json.load(f)
    for v in organisms["visitors"]:
        if v["visitor_id"] == visitor_id:
            v["standing"] = new_standing
            break
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(organisms, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def promote_in_agent_index(idx, visitor_id, old_standing, new_standing):
    """Move visitor from old_standing to new_standing in agent-index."""
    vbs = idx.setdefault("visitors_by_standing", {})
    # Remove from old
    if old_standing in vbs and visitor_id in vbs[old_standing]:
        vbs[old_standing].remove(visitor_id)
    # Add to new
    vbs.setdefault(new_standing, [])
    if visitor_id not in vbs[new_standing]:
        vbs[new_standing].append(visitor_id)


# ---------------------------------------------------------------------------
# Demotion watch state — tracks grace periods for trust decay
# ---------------------------------------------------------------------------

def load_demotion_watch():
    """Load active demotion watch records."""
    if not os.path.isfile(DEMOTION_WATCH_PATH):
        return {}
    with open(DEMOTION_WATCH_PATH) as f:
        return json.load(f)


def save_demotion_watch(watch):
    """Atomically save demotion watch state."""
    os.makedirs(os.path.dirname(DEMOTION_WATCH_PATH), exist_ok=True)
    tmp = DEMOTION_WATCH_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(watch, f, indent=2)
        f.write("\n")
    os.replace(tmp, DEMOTION_WATCH_PATH)


def get_current_tic():
    """Resolve current federation tic from tic log files."""
    tic_dir = os.path.join(AUDIT_ROOT, "tics")
    if not os.path.isdir(tic_dir):
        return 0
    tic_files = sorted(f for f in os.listdir(tic_dir) if f.endswith(".jsonl"))
    if not tic_files:
        return 0
    last_file = os.path.join(tic_dir, tic_files[-1])
    try:
        last_line = None
        with open(last_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line
        if last_line:
            rec = json.loads(last_line)
            return rec.get("domain_counter_after",
                           rec.get("global_counter_after",
                                   rec.get("tic", 0)))
    except (json.JSONDecodeError, OSError):
        pass
    return 0


def get_standing_threshold(standing):
    """Get the trust_score threshold for a standing level.

    Returns the threshold that was required to ENTER this standing.
    If trust drops below this, the visitor is in decay territory.
    """
    thresholds = SE_CONFIG["trust_thresholds"]
    return thresholds.get(standing, 0.0)


def get_demotion_target(standing):
    """Get the standing level to demote to."""
    return SE_CONFIG.get("demotion_map", {}).get(standing)


def get_demotion_gate(standing):
    """Get the governance gate type for demotion at this standing level.

    Per spec: demotion review is triggered at the governance authority
    appropriate to the visitor's current standing.
    """
    due_process = SE_CONFIG.get("due_process", {})
    dp = due_process.get(standing, {})
    return dp.get("review_type", "automated")


def demote_in_agent_index(idx, visitor_id, old_standing, new_standing):
    """Move visitor from old_standing to new_standing in agent-index (demotion)."""
    vbs = idx.setdefault("visitors_by_standing", {})
    if old_standing in vbs and visitor_id in vbs[old_standing]:
        vbs[old_standing].remove(visitor_id)
    vbs.setdefault(new_standing, [])
    if visitor_id not in vbs[new_standing]:
        vbs[new_standing].append(visitor_id)


def execute_departure(visitor_id, reason="voluntary"):
    """Mark a visitor as departed in organisms.json."""
    path = os.path.join(BIOME_STATE_DIR, "organisms.json")
    with open(path) as f:
        organisms = json.load(f)
    for v in organisms["visitors"]:
        if v["visitor_id"] == visitor_id:
            v["departed"] = True
            v["active"] = False
            v["departure_reason"] = reason
            v["departure_timestamp"] = iso_now()
            break
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(organisms, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def execute_eviction(visitor_id, evidence, zone_root=None):
    """Mark a visitor as evicted, trigger endorser penalty cascade.

    Returns endorser penalties applied.
    """
    path = os.path.join(BIOME_STATE_DIR, "organisms.json")
    with open(path) as f:
        organisms = json.load(f)
    for v in organisms["visitors"]:
        if v["visitor_id"] == visitor_id:
            v["evicted"] = True
            v["active"] = False
            v["eviction_evidence"] = evidence
            v["eviction_timestamp"] = iso_now()
            break
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(organisms, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)

    # Trigger endorser penalty cascade
    penalties = compute_endorser_penalty(visitor_id, zone_root=zone_root or ZONE_ROOT)

    # Log eviction to registry
    atomic_append_jsonl(REGISTRY_PATH, {
        "entity_id": visitor_id,
        "event_type": "eviction",
        "evidence": evidence,
        "endorser_penalties": len(penalties),
        "timestamp": iso_now(),
    })

    # Emit eviction signal
    emit_signal("standing.eviction", {
        "entity_id": visitor_id,
        "evidence_summary": evidence[:200] if isinstance(evidence, str) else str(evidence)[:200],
        "endorser_penalties_count": len(penalties),
        "band": "ALERT",
    })

    return penalties


# ---------------------------------------------------------------------------
# Core: trust progression cycle
# ---------------------------------------------------------------------------

def run_trust_progression(entity_filter=None, dry_run=False, verbose=False):
    """Run trust computation, promotion checks, and demotion monitoring.

    Returns:
        dict with keys:
            visitors_processed: int
            trust_scores: dict[entity_id, float]
            promotions: list[dict] — visitors that were promoted
            demotions: list[dict] — visitors that were demoted
            demotion_watches: list[dict] — visitors entering grace period
            pending_review: list[dict] — visitors needing steward/constitutional review
            errors: list[str]
    """
    organisms = load_organisms()
    idx = load_agent_index()
    results = {
        "visitors_processed": 0,
        "trust_scores": {},
        "promotions": [],
        "demotions": [],
        "demotion_watches": [],
        "watch_cleared": [],
        "pending_review": [],
        "errors": [],
        "timestamp": iso_now(),
    }

    active_visitors = [
        v for v in organisms.get("visitors", [])
        if v.get("active") and not v.get("departed") and not v.get("evicted")
    ]

    if entity_filter:
        active_visitors = [v for v in active_visitors if v["visitor_id"] == entity_filter]

    for visitor in active_visitors:
        vid = visitor["visitor_id"]
        results["visitors_processed"] += 1

        try:
            # Step 1: Compute trust score
            trust_result = compute_trust_score(vid, zone_root=ZONE_ROOT)
            ts = trust_result["trust_score"]
            results["trust_scores"][vid] = ts

            if verbose:
                div = trust_result.get("diversity", {})
                print(f"  {vid}: trust={ts:.4f}, diversity={div.get('entropy', 0):.3f} "
                      f"({div.get('types_observed', 0)} types), "
                      f"decay={'yes' if trust_result['decay_applied'] else 'no'}")
                for comp, val in trust_result["components"].items():
                    print(f"    {comp}: {val}")

            # Step 2: Check eligibility
            elig = check_transition_eligibility(vid, zone_root=ZONE_ROOT)

            if elig["eligible"]:
                gate = elig["governance_gate"]
                old = elig["current_standing"]
                new = elig["target_standing"]

                if gate == "automated" and not dry_run:
                    # Auto-promote
                    update_organisms_standing(vid, new)
                    promote_in_agent_index(idx, vid, old, new)

                    # Log promotion to registry
                    atomic_append_jsonl(REGISTRY_PATH, {
                        "entity_id": vid,
                        "event_type": "standing_promotion",
                        "from_standing": old,
                        "to_standing": new,
                        "trust_score": ts,
                        "gate": gate,
                        "timestamp": iso_now(),
                    })

                    results["promotions"].append({
                        "entity_id": vid,
                        "from": old,
                        "to": new,
                        "trust_score": ts,
                        "gate": gate,
                    })

                    if verbose:
                        print(f"  ** PROMOTED {vid}: {old} → {new} (trust={ts:.4f}, gate={gate})")

                elif gate in ("steward_review", "constitutional_review"):
                    # Emit signal for manual review
                    results["pending_review"].append({
                        "entity_id": vid,
                        "from": old,
                        "to": new,
                        "trust_score": ts,
                        "gate": gate,
                    })

                    if not dry_run:
                        emit_signal("standing.promotion_eligible", {
                            "entity_id": vid,
                            "current_standing": old,
                            "target_standing": new,
                            "trust_score": ts,
                            "governance_gate": gate,
                        })

                    if verbose:
                        print(f"  ** ELIGIBLE {vid}: {old} → {new} (trust={ts:.4f}, gate={gate}, needs review)")

                elif dry_run:
                    results["promotions"].append({
                        "entity_id": vid,
                        "from": old,
                        "to": new,
                        "trust_score": ts,
                        "gate": gate,
                        "dry_run": True,
                    })
                    if verbose:
                        print(f"  ** [DRY RUN] WOULD PROMOTE {vid}: {old} → {new} (trust={ts:.4f})")

            else:
                if verbose and elig["reasons"]:
                    print(f"  {vid}: not eligible — {'; '.join(elig['reasons'][:2])}")

        except Exception as e:
            results["errors"].append(f"{vid}: {e}")
            if verbose:
                print(f"  ERROR {vid}: {e}")

    # ----- Step 3: Demotion monitoring -----
    # Per standing-progression-spec §Reverse Transitions:
    # If trust_score drops below threshold for current standing:
    #   1. Emit standing.trust_decay WATCH signal
    #   2. Grace period (5 tics PROVISIONAL)
    #   3. After grace: trigger demotion review
    #   4. Auto-demote for automated gates, signal for review gates

    current_tic = get_current_tic()
    grace_period = SE_CONFIG.get("trust_decay_grace_period_tics", 5)
    watch = load_demotion_watch()
    watch_dirty = False

    for visitor in active_visitors:
        vid = visitor["visitor_id"]
        standing = visitor.get("standing", "guest")
        ts = results["trust_scores"].get(vid)

        if ts is None:
            continue  # trust not computed (error case)

        # Skip guests — can't demote below guest
        if standing == "guest":
            if vid in watch:
                del watch[vid]
                watch_dirty = True
            continue

        # Check if visitor was just promoted — skip demotion check this cycle
        if any(p["entity_id"] == vid for p in results["promotions"]):
            if vid in watch:
                del watch[vid]
                watch_dirty = True
            continue

        threshold = get_standing_threshold(standing)

        if ts >= threshold:
            # Trust recovered — clear watch if active
            if vid in watch:
                if verbose:
                    print(f"  [DEMOTION] {vid}: trust recovered ({ts:.4f} >= {threshold}), "
                          f"clearing watch")
                results["watch_cleared"].append({
                    "entity_id": vid,
                    "standing": standing,
                    "trust_score": ts,
                    "threshold": threshold,
                })
                del watch[vid]
                watch_dirty = True
            continue

        # Trust below threshold
        demotion_target = get_demotion_target(standing)
        if not demotion_target:
            continue  # shouldn't happen, but safety

        if vid not in watch:
            # Start grace period — emit WATCH signal
            watch[vid] = {
                "standing": standing,
                "trust_score_at_watch": ts,
                "threshold": threshold,
                "watch_start_tic": current_tic,
                "grace_expires_tic": current_tic + grace_period,
                "timestamp": iso_now(),
            }
            watch_dirty = True

            results["demotion_watches"].append({
                "entity_id": vid,
                "standing": standing,
                "trust_score": ts,
                "threshold": threshold,
                "grace_expires_tic": current_tic + grace_period,
            })

            if not dry_run:
                emit_signal("standing.trust_decay", {
                    "entity_id": vid,
                    "current_standing": standing,
                    "trust_score": ts,
                    "threshold": threshold,
                    "grace_period_tics": grace_period,
                    "grace_expires_tic": current_tic + grace_period,
                    "band": "WATCH",
                })

            if verbose:
                print(f"  [DEMOTION] {vid}: trust decay ({ts:.4f} < {threshold}), "
                      f"grace period started (expires tic {current_tic + grace_period})")

        else:
            # Already on watch — check if grace period expired
            w = watch[vid]
            if current_tic >= w["grace_expires_tic"]:
                # Grace period expired — trigger demotion
                gate = get_demotion_gate(standing)

                if gate == "automated" and not dry_run:
                    # Auto-demote
                    update_organisms_standing(vid, demotion_target)
                    demote_in_agent_index(idx, vid, standing, demotion_target)

                    atomic_append_jsonl(REGISTRY_PATH, {
                        "entity_id": vid,
                        "event_type": "standing_demotion",
                        "from_standing": standing,
                        "to_standing": demotion_target,
                        "trust_score": ts,
                        "gate": gate,
                        "reason": "trust_decay_grace_expired",
                        "watch_start_tic": w["watch_start_tic"],
                        "timestamp": iso_now(),
                    })

                    results["demotions"].append({
                        "entity_id": vid,
                        "from": standing,
                        "to": demotion_target,
                        "trust_score": ts,
                        "gate": gate,
                    })

                    if not dry_run:
                        emit_signal("standing.demotion", {
                            "entity_id": vid,
                            "from_standing": standing,
                            "to_standing": demotion_target,
                            "trust_score": ts,
                            "reason": "trust_decay_grace_expired",
                            "band": "ALERT",
                        })

                    if verbose:
                        print(f"  ** DEMOTED {vid}: {standing} → {demotion_target} "
                              f"(trust={ts:.4f}, gate={gate})")

                    # Clear from watch
                    del watch[vid]
                    watch_dirty = True

                elif gate in ("steward_review", "constitutional_review"):
                    # Emit demotion review signal
                    results["pending_review"].append({
                        "entity_id": vid,
                        "from": standing,
                        "to": demotion_target,
                        "trust_score": ts,
                        "gate": gate,
                        "action": "demotion_review",
                    })

                    if not dry_run:
                        emit_signal("standing.demotion_review", {
                            "entity_id": vid,
                            "current_standing": standing,
                            "target_standing": demotion_target,
                            "trust_score": ts,
                            "governance_gate": gate,
                            "watch_start_tic": w["watch_start_tic"],
                            "band": "WATCH",
                        })

                    if verbose:
                        print(f"  ** DEMOTION REVIEW {vid}: {standing} → {demotion_target} "
                              f"(trust={ts:.4f}, gate={gate}, needs review)")

                elif dry_run:
                    results["demotions"].append({
                        "entity_id": vid,
                        "from": standing,
                        "to": demotion_target,
                        "trust_score": ts,
                        "gate": gate,
                        "dry_run": True,
                    })
                    if verbose:
                        print(f"  ** [DRY RUN] WOULD DEMOTE {vid}: {standing} → {demotion_target}")

            else:
                # Grace period still active
                remaining = w["grace_expires_tic"] - current_tic
                if verbose:
                    print(f"  [DEMOTION] {vid}: grace period active "
                          f"({remaining} tics remaining, trust={ts:.4f})")

    # Save updated state
    if not dry_run and (results["promotions"] or results["demotions"]):
        save_agent_index(idx)
    if watch_dirty and not dry_run:
        save_demotion_watch(watch)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Trust progression cycle — biome→trust→standing integration")
    parser.add_argument("--entity", help="Run for a single entity ID")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't promote")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detailed output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.verbose:
        print(f"[TRUST-PROGRESSION] Running at {iso_now()}")
        print(f"  Zone root: {ZONE_ROOT}")
        print(f"  Registry: {REGISTRY_PATH}")
        if args.dry_run:
            print("  Mode: DRY RUN (no promotions)")
        print()

    results = run_trust_progression(
        entity_filter=args.entity,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        # Human summary
        print(f"\n[TRUST-PROGRESSION] {results['visitors_processed']} visitors processed")
        if results["trust_scores"]:
            for vid, ts in sorted(results["trust_scores"].items()):
                print(f"  {vid}: {ts:.4f}")
        if results["promotions"]:
            print(f"\nPromotions: {len(results['promotions'])}")
            for p in results["promotions"]:
                dr = " [DRY RUN]" if p.get("dry_run") else ""
                print(f"  {p['entity_id']}: {p['from']} → {p['to']} (trust={p['trust_score']:.4f}){dr}")
        if results["demotions"]:
            print(f"\nDemotions: {len(results['demotions'])}")
            for d in results["demotions"]:
                dr = " [DRY RUN]" if d.get("dry_run") else ""
                print(f"  {d['entity_id']}: {d['from']} → {d['to']} (trust={d['trust_score']:.4f}){dr}")
        if results["demotion_watches"]:
            print(f"\nDemotion watches started: {len(results['demotion_watches'])}")
            for w in results["demotion_watches"]:
                print(f"  {w['entity_id']}: {w['standing']} (trust={w['trust_score']:.4f} < "
                      f"{w['threshold']}, grace expires tic {w['grace_expires_tic']})")
        if results["watch_cleared"]:
            print(f"\nDemotion watches cleared: {len(results['watch_cleared'])}")
            for w in results["watch_cleared"]:
                print(f"  {w['entity_id']}: trust recovered ({w['trust_score']:.4f} >= {w['threshold']})")
        if results["pending_review"]:
            print(f"\nPending review: {len(results['pending_review'])}")
            for p in results["pending_review"]:
                action = p.get("action", "promotion")
                print(f"  {p['entity_id']}: {p['from']} → {p['to']} (gate={p['gate']}, {action})")
        if results["errors"]:
            print(f"\nErrors: {len(results['errors'])}")
            for e in results["errors"]:
                print(f"  {e}")


if __name__ == "__main__":
    main()
