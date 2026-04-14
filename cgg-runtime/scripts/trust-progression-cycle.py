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
# Core: trust progression cycle
# ---------------------------------------------------------------------------

def run_trust_progression(entity_filter=None, dry_run=False, verbose=False):
    """Run trust computation and promotion checks for all active visitors.

    Returns:
        dict with keys:
            visitors_processed: int
            trust_scores: dict[entity_id, float]
            promotions: list[dict] — visitors that were promoted
            pending_review: list[dict] — visitors needing steward/constitutional review
            errors: list[str]
    """
    organisms = load_organisms()
    idx = load_agent_index()
    results = {
        "visitors_processed": 0,
        "trust_scores": {},
        "promotions": [],
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

    # Save updated agent-index
    if not dry_run and results["promotions"]:
        save_agent_index(idx)

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
        if results["pending_review"]:
            print(f"\nPending review: {len(results['pending_review'])}")
            for p in results["pending_review"]:
                print(f"  {p['entity_id']}: {p['from']} → {p['to']} (gate={p['gate']})")
        if results["errors"]:
            print(f"\nErrors: {len(results['errors'])}")
            for e in results["errors"]:
                print(f"  {e}")


if __name__ == "__main__":
    main()
