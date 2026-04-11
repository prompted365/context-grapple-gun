#!/usr/bin/env python3
"""
standing-engine.py — Standing Progression Engine

Implements trust_score computation, behavioral diversity scoring, standing
transition checking, endorsement handling, and due process initiation.

Spec sources:
  - autonomous_kernel/standing-progression-spec.md
  - autonomous_kernel/behavioral-diversity-spec.md
  - autonomous_kernel/endorsement-chain-spec.md
  - autonomous_kernel/due-process-protocol.md
  - autonomous_kernel/standing-mapping-spec.md

Usage (CLI):
  python3 standing-engine.py --check-eligibility <entity_id>
  python3 standing-engine.py --compute-trust <entity_id>
  python3 standing-engine.py --diversity <entity_id>
  python3 standing-engine.py --endorse <endorser_id> <endorsed_id> <target_standing> <rationale>
  python3 standing-engine.py --due-process <entity_id> <trigger_type> <evidence>

Usage (module):
  from standing_engine import (
      compute_trust_score,
      compute_behavioral_diversity,
      check_transition_eligibility,
      process_endorsement,
      initiate_due_process,
  )
"""

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# PROVISIONAL CONFIGURATION — all thresholds subject to calibration
# Per CogPR-46: fabricated thresholds create false confidence. These are
# starting points, not validated boundaries.
# ---------------------------------------------------------------------------

CONFIG = {
    # trust_score thresholds per transition (PROVISIONAL)
    "trust_thresholds": {
        "tourist": 0.2,       # Guest -> Tourist
        "foreign_delegate": 0.4,  # Tourist -> Student
        "resident": 0.6,     # Student -> Resident
        "citizen": 0.8,      # Resident -> Citizen
    },

    # Behavioral diversity entropy thresholds per tier (PROVISIONAL)
    "diversity_thresholds": {
        "tourist": 0.0,       # No diversity requirement for Guest -> Tourist
        "foreign_delegate": 1.585,  # log2(3) — min 3 types
        "resident": 1.585,   # log2(3) — sustained
        "citizen": 2.0,      # log2(4) — min 4 types
    },

    # Time-lock minimums (in sessions/tics) per tier (PROVISIONAL)
    "time_locks": {
        "tourist": 1,         # 1 session at guest
        "foreign_delegate": 3,  # 3 sessions at tourist
        "resident": 10,       # sustained participation (PROVISIONAL)
        "citizen": 20,        # extended participation (PROVISIONAL)
    },

    # Sliding window for diversity calculation (in cycles)
    "diversity_window_cycles": 20,

    # trust_score decay half-life in tics (PROVISIONAL)
    "decay_half_life_tics": 10,

    # trust_score input weights (base weights before non-linear interaction)
    "input_weights": {
        "behavioral_diversity": 0.30,
        "endorsement_strength": 0.20,
        "interaction_history": 0.30,
        "pressure_response": 0.20,
    },

    # Endorsement mechanics (PROVISIONAL)
    "endorsement_cap": 3,        # Max active endorsements per endorser
    "endorsement_ttl_tics": 20,  # TTL before expiry
    "endorsement_penalty_direct": 0.1,   # trust_score penalty on eviction
    "endorsement_penalty_dampening": 0.5,  # 50% per hop
    "endorsement_penalty_floor": 0.01,     # cease below this

    # Demotion review (PROVISIONAL)
    "trust_decay_grace_period_tics": 5,
    "trust_collapse_threshold": 0.2,  # triggers endorser WATCH
    "demotion_penalty_factor": 0.5,   # half eviction penalty

    # Due process scaled parameters (PROVISIONAL)
    "due_process": {
        "guest": {
            "authority": "automated",
            "min_evidence": 2,
            "notice_period_tics": 0,
            "appeal_window_tics": 1,
            "review_type": "automated",
        },
        "tourist": {
            "authority": "automated",
            "min_evidence": 2,
            "notice_period_tics": 1,
            "appeal_window_tics": 2,
            "review_type": "automated",
        },
        "foreign_delegate": {
            "authority": "steward",
            "min_evidence": 3,
            "notice_period_tics": 2,
            "appeal_window_tics": 3,
            "review_type": "steward_review",
        },
        "resident": {
            "authority": "constitutional",
            "min_evidence": 5,
            "notice_period_tics": 3,
            "appeal_window_tics": 5,
            "review_type": "constitutional_review",
        },
        "citizen": {
            "authority": "constitutional_panel",
            "min_evidence": 7,
            "notice_period_tics": 5,
            "appeal_window_tics": -1,  # open-ended
            "review_type": "full_constitutional_review",
        },
    },

    # Interaction type taxonomy (8 canonical types)
    "interaction_types": [
        "exploration",
        "creation",
        "exchange",
        "governance",
        "collaboration",
        "teaching",
        "defense",
        "reflection",
    ],

    # Standing hierarchy (ordered low to high)
    "standing_order": ["guest", "tourist", "foreign_delegate", "resident", "citizen"],

    # Promotion targets: current_standing -> next_standing
    "promotion_map": {
        "guest": "tourist",
        "tourist": "foreign_delegate",
        "foreign_delegate": "resident",
        "resident": "citizen",
    },

    # Governance gate types per transition
    "governance_gates": {
        "tourist": "automated",
        "foreign_delegate": "automated",
        "resident": "steward_review",
        "citizen": "constitutional_review",
    },

    # Tiers requiring endorsement (INV-STANDING-03)
    "endorsement_required_tiers": {"resident", "citizen"},

    # Minimum endorser standing
    "min_endorser_standing": "resident",
}

# ---------------------------------------------------------------------------
# Interaction type enum for type-safe references
# ---------------------------------------------------------------------------

INTERACTION_TYPES = set(CONFIG["interaction_types"])
STANDING_ORDER = CONFIG["standing_order"]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _scripts_dir():
    """Return the directory containing this script."""
    return os.path.dirname(os.path.abspath(__file__))


def _setup_lib_path():
    """Add scripts dir to sys.path so lib imports work."""
    sd = _scripts_dir()
    if sd not in sys.path:
        sys.path.insert(0, sd)


_setup_lib_path()

try:
    from zone_root import resolve_zone_root, audit_logs_path, load_ticzone
    from lib.atomic_append import atomic_append_jsonl
except ImportError:
    # Fallback for standalone testing
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


def _biome_path(zone_root=None):
    """Resolve the biome audit-logs path."""
    zr = zone_root or resolve_zone_root()
    al = audit_logs_path(zr, load_ticzone(zr))
    return os.path.join(al, "biome")


def _registry_path(zone_root=None):
    return os.path.join(_biome_path(zone_root), "visa-registry", "registry.jsonl")


def _agent_index_path(zone_root=None):
    return os.path.join(_biome_path(zone_root), "visa-registry", "agent-index.json")


def _endorsements_path(zone_root=None):
    return os.path.join(_biome_path(zone_root), "endorsements", "endorsements.jsonl")


def _due_process_path(zone_root=None):
    return os.path.join(_biome_path(zone_root), "due-process", "actions.jsonl")


def _signals_path(zone_root=None):
    zr = zone_root or resolve_zone_root()
    al = audit_logs_path(zr, load_ticzone(zr))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(al, "signals", f"{today}.jsonl")


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_jsonl(path):
    """Load all records from a JSONL file, skipping schema headers."""
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
                # Skip schema header lines
                if "_schema" in rec:
                    continue
                records.append(rec)
            except json.JSONDecodeError:
                continue
    return records


def _load_agent_index(zone_root=None):
    """Load the agent-index.json."""
    path = _agent_index_path(zone_root)
    if not os.path.isfile(path):
        return {"visitors_by_standing": {}, "active_count": 0}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"visitors_by_standing": {}, "active_count": 0}


def _get_entity_standing(entity_id, zone_root=None):
    """Look up an entity's current standing from the agent-index or registry."""
    idx = _load_agent_index(zone_root)
    vbs = idx.get("visitors_by_standing", {})
    for standing, entities in vbs.items():
        if entity_id in entities:
            return standing
    # Fallback: scan registry for most recent transition
    records = _load_jsonl(_registry_path(zone_root))
    last_standing = None
    for rec in records:
        if rec.get("entity_id") == entity_id:
            last_standing = rec.get("to_standing")
    return last_standing


def _get_entity_interactions(entity_id, window_cycles=None, zone_root=None):
    """Load interaction history for an entity from the visa registry.

    Returns a list of interaction records within the sliding window.
    Each record should have at minimum: {"type": "<interaction_type>", "cycle": N}
    """
    if window_cycles is None:
        window_cycles = CONFIG["diversity_window_cycles"]

    # Interactions are logged in the registry as state transitions and
    # interaction events. We scan for records with matching entity_id.
    records = _load_jsonl(_registry_path(zone_root))
    interactions = []
    for rec in records:
        if rec.get("entity_id") == entity_id and rec.get("interaction_type"):
            interactions.append(rec)

    # Apply sliding window — keep only the last N cycles
    if interactions and window_cycles > 0:
        # Sort by cycle/timestamp, keep last window
        interactions.sort(key=lambda r: r.get("cycle", r.get("timestamp", "")))
        if len(interactions) > window_cycles:
            interactions = interactions[-window_cycles:]

    return interactions


def _get_entity_endorsements(entity_id, active_only=True, zone_root=None):
    """Get endorsements where entity_id is the endorsed entity."""
    records = _load_jsonl(_endorsements_path(zone_root))
    endorsements = []
    for rec in records:
        if rec.get("endorsed_id") != entity_id:
            continue
        if active_only and rec.get("state") not in (None, "active", "validated"):
            continue
        endorsements.append(rec)
    return endorsements


def _get_endorser_active_count(endorser_id, zone_root=None):
    """Count active endorsements made by an endorser."""
    records = _load_jsonl(_endorsements_path(zone_root))
    count = 0
    for rec in records:
        if rec.get("endorser_id") != endorser_id:
            continue
        if rec.get("state") in (None, "active", "validated"):
            count += 1
    return count


def _get_endorsers_for_entity(entity_id, zone_root=None):
    """Get list of endorser_ids who have active endorsements for entity_id."""
    records = _load_jsonl(_endorsements_path(zone_root))
    endorsers = []
    for rec in records:
        if rec.get("endorsed_id") == entity_id:
            if rec.get("state") in (None, "active", "validated"):
                endorsers.append(rec.get("endorser_id"))
    return endorsers


def _get_entity_time_at_standing(entity_id, zone_root=None):
    """Get how many tics/sessions the entity has been at current standing.

    Returns int (count of tics at current standing).
    """
    records = _load_jsonl(_registry_path(zone_root))
    last_transition_tic = None
    current_standing = None
    for rec in records:
        if rec.get("entity_id") == entity_id:
            if rec.get("to_standing"):
                current_standing = rec.get("to_standing")
                last_transition_tic = rec.get("tic", rec.get("federation_tic", 0))

    if last_transition_tic is None:
        return 0

    # Estimate current tic from the ticzone or latest registry entry
    latest_tic = last_transition_tic
    for rec in records:
        t = rec.get("tic", rec.get("federation_tic", 0))
        if isinstance(t, (int, float)) and t > latest_tic:
            latest_tic = t

    return max(0, int(latest_tic - last_transition_tic))


def _get_pressure_response_score(entity_id, zone_root=None):
    """Assess pressure response from biome stress event records.

    Returns float [0.0, 1.0] or None if no stress events observed.
    Pressure response is episodic and high-signal — assessed only when
    stress conditions occur naturally (INV: system does NOT manufacture
    adversarial conditions).
    """
    # Pressure response events would be logged in the registry or a
    # dedicated stress-events log. For now, scan registry for defense
    # interaction types and stress-event markers.
    records = _load_jsonl(_registry_path(zone_root))
    stress_events = []
    for rec in records:
        if rec.get("entity_id") == entity_id:
            if rec.get("stress_event") or rec.get("interaction_type") == "defense":
                stress_events.append(rec)

    if not stress_events:
        return None  # No pressure data — not penalized, just absent

    # Score based on coherence during stress events
    coherent = sum(1 for e in stress_events if e.get("coherent", True))
    return coherent / len(stress_events) if stress_events else None


# ---------------------------------------------------------------------------
# 1. BEHAVIORAL DIVERSITY SCORING
#    Shannon entropy over interaction type distribution in sliding window
# ---------------------------------------------------------------------------

def compute_behavioral_diversity(entity_id, window_cycles=None, zone_root=None):
    """Compute behavioral diversity as Shannon entropy.

    Returns:
        dict with keys:
            entropy: float — Shannon entropy in bits [0.0, 3.0]
            distribution: dict — proportion per interaction type
            interaction_count: int — total interactions in window
            types_active: int — number of distinct types observed
            thresholds_met: dict — {tier: bool} for each tier threshold
    """
    if window_cycles is None:
        window_cycles = CONFIG["diversity_window_cycles"]

    interactions = _get_entity_interactions(entity_id, window_cycles, zone_root)

    # Count interactions per type
    type_counts = {t: 0 for t in CONFIG["interaction_types"]}
    for rec in interactions:
        itype = rec.get("interaction_type", rec.get("type"))
        if itype in type_counts:
            type_counts[itype] += 1

    total = sum(type_counts.values())

    if total == 0:
        return {
            "entropy": 0.0,
            "distribution": {t: 0.0 for t in CONFIG["interaction_types"]},
            "interaction_count": 0,
            "types_active": 0,
            "thresholds_met": {
                tier: (threshold == 0.0)
                for tier, threshold in CONFIG["diversity_thresholds"].items()
            },
        }

    # Compute proportions
    distribution = {t: count / total for t, count in type_counts.items()}

    # Shannon entropy: H = -sum(p_i * log2(p_i)) for p_i > 0
    entropy = 0.0
    for p in distribution.values():
        if p > 0:
            entropy -= p * math.log2(p)

    types_active = sum(1 for c in type_counts.values() if c > 0)

    # Check which tier thresholds are met
    thresholds_met = {}
    for tier, threshold in CONFIG["diversity_thresholds"].items():
        thresholds_met[tier] = entropy >= threshold

    return {
        "entropy": round(entropy, 4),
        "distribution": {t: round(p, 4) for t, p in distribution.items()},
        "interaction_count": total,
        "types_active": types_active,
        "thresholds_met": thresholds_met,
    }


# ---------------------------------------------------------------------------
# 1b. GATE-ENTROPY (CogPR-139 wiring: economy-bridge → standing-engine)
# ---------------------------------------------------------------------------

def _get_gate_entropy_score(entity_id, zone_root=None):
    """Retrieve gate-entropy score from economy bridge adapter output.

    Gate-entropy measures distributional breadth across economic channels
    (contribution, governance, exchange, endorsement). It is a stronger
    trust signal than balance per CogPR-139.

    Returns:
        float or None — entropy in bits (max ~2.0), None if no data available.
    """
    if zone_root is None:
        zone_root = _resolve_zone_root()

    # Look for economy bridge gate-entropy output
    gate_entropy_dir = os.path.join(
        zone_root, "audit-logs", "services", "economy-bridge", "gate-entropy"
    )
    entity_file = os.path.join(gate_entropy_dir, f"{entity_id}.json")

    if not os.path.isfile(entity_file):
        return None

    try:
        with open(entity_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        entropy = data.get("gate_entropy")
        if entropy is not None:
            return float(entropy)
    except (json.JSONDecodeError, ValueError, OSError):
        pass

    return None


# ---------------------------------------------------------------------------
# 2. TRUST_SCORE COMPUTATION
#    Non-linear derivation from 5 input signals (4 original + gate-entropy)
# ---------------------------------------------------------------------------

def compute_trust_score(entity_id, zone_root=None):
    """Compute trust_score for an entity.

    trust_score is a continuous value in [0.0, 1.0]. Inputs interact
    non-linearly: high volume with low diversity does not compensate.
    Endorsement amplifies but does not substitute for behavioral evidence.
    Pressure response is high-signal but rare.

    Returns:
        dict with keys:
            trust_score: float [0.0, 1.0]
            components: dict — individual input scores
            decay_applied: bool
            raw_score: float — score before clamping
    """
    # --- Component 1: Behavioral diversity entropy ---
    diversity = compute_behavioral_diversity(entity_id, zone_root=zone_root)
    # Normalize entropy to [0, 1]: max entropy is log2(8) = 3.0
    max_entropy = math.log2(len(CONFIG["interaction_types"]))
    diversity_score = min(diversity["entropy"] / max_entropy, 1.0) if max_entropy > 0 else 0.0

    # --- Component 2: Endorsement chain strength ---
    endorsements = _get_entity_endorsements(entity_id, active_only=True, zone_root=zone_root)
    endorsement_score = _compute_endorsement_strength(endorsements)

    # --- Component 3: Time-weighted interaction history ---
    interactions = _get_entity_interactions(entity_id, zone_root=zone_root)
    history_score = _compute_interaction_history_score(interactions, entity_id, zone_root)

    # --- Component 4: Pressure response ---
    pressure_raw = _get_pressure_response_score(entity_id, zone_root)
    # None means no data — treat as neutral (0.5) rather than penalizing
    pressure_score = pressure_raw if pressure_raw is not None else 0.5

    # --- Component 5: Gate-entropy (CogPR-139) ---
    # Gate-entropy (distributional breadth across economic channels) is a
    # stronger trust signal than balance. Trailing-window measurement with
    # environmental normalization. If economy bridge data is unavailable,
    # gate-entropy is neutral (does not penalize or boost).
    gate_entropy_score = _get_gate_entropy_score(entity_id, zone_root)

    # --- Non-linear derivation ---
    # Property 1: High volume + low diversity does NOT compensate.
    # Apply diversity as a gate on history: if diversity is low, history
    # contribution is attenuated.
    diversity_gate = _sigmoid(diversity_score, center=0.3, steepness=8.0)
    gated_history = history_score * diversity_gate

    # Property 2: Endorsement as multiplier — amplifies when other signals
    # are healthy, but does not substitute for behavioral evidence.
    base_behavioral = (
        CONFIG["input_weights"]["behavioral_diversity"] * diversity_score
        + CONFIG["input_weights"]["interaction_history"] * gated_history
    )

    # Property 2b: Gate-entropy enriches behavioral diversity signal.
    # When gate-entropy data exists, blend it with behavioral diversity
    # (stronger signal per CogPR-139). Max gate entropy = log2(4) ≈ 2.0.
    if gate_entropy_score is not None:
        gate_entropy_normalized = min(gate_entropy_score / 2.0, 1.0)
        # Blend: 60% behavioral diversity + 40% gate entropy
        blended_diversity = 0.6 * diversity_score + 0.4 * gate_entropy_normalized
        base_behavioral = (
            CONFIG["input_weights"]["behavioral_diversity"] * blended_diversity
            + CONFIG["input_weights"]["interaction_history"] * gated_history
        )

    endorsement_multiplier = 1.0 + (endorsement_score * 0.5)  # Up to 1.5x
    behavioral_with_endorsement = min(base_behavioral * endorsement_multiplier, 1.0)

    # Property 3: Pressure response as discriminator — disproportionate
    # benefit when present and positive.
    pressure_weight = CONFIG["input_weights"]["pressure_response"]
    if pressure_raw is not None:
        # Pressure data exists — high-signal: can boost or drag
        pressure_contribution = pressure_score * pressure_weight * 1.5
    else:
        # No pressure data — neutral contribution
        pressure_contribution = 0.5 * pressure_weight

    # Combine
    raw_score = behavioral_with_endorsement + pressure_contribution

    # Property 4: Decay — without continued participation, trust_score
    # decays toward zero. Check time since last interaction.
    decay_factor, decay_applied = _compute_decay_factor(entity_id, zone_root)
    raw_score *= decay_factor

    # Clamp to [0.0, 1.0]
    trust_score = max(0.0, min(1.0, raw_score))

    return {
        "trust_score": round(trust_score, 4),
        "components": {
            "behavioral_diversity": round(diversity_score, 4),
            "endorsement_strength": round(endorsement_score, 4),
            "interaction_history": round(history_score, 4),
            "interaction_history_gated": round(gated_history, 4),
            "pressure_response": round(pressure_score, 4),
            "pressure_data_present": pressure_raw is not None,
            "gate_entropy": round(gate_entropy_score, 4) if gate_entropy_score is not None else None,
            "gate_entropy_present": gate_entropy_score is not None,
            "diversity_gate": round(diversity_gate, 4),
            "endorsement_multiplier": round(endorsement_multiplier, 4),
            "decay_factor": round(decay_factor, 4),
        },
        "decay_applied": decay_applied,
        "raw_score": round(raw_score, 4),
        "diversity": diversity,
    }


def _sigmoid(x, center=0.5, steepness=10.0):
    """Sigmoid function for smooth gating. Returns [0, 1]."""
    exp_arg = -steepness * (x - center)
    # Clamp to avoid overflow
    exp_arg = max(-500, min(500, exp_arg))
    return 1.0 / (1.0 + math.exp(exp_arg))


def _compute_endorsement_strength(endorsements):
    """Compute endorsement chain strength from active endorsements.

    Weighted by endorser standing and trust_score at time of endorsement.
    Returns float [0.0, 1.0].
    """
    if not endorsements:
        return 0.0

    standing_weights = {
        "resident": 0.6,
        "citizen": 1.0,
    }

    total_weight = 0.0
    for e in endorsements:
        sw = standing_weights.get(e.get("endorser_standing"), 0.3)
        endorser_trust = e.get("endorser_trust_score_at_time", 0.5)
        total_weight += sw * endorser_trust

    # Normalize: diminishing returns after first few endorsements
    # Using log scaling to prevent endorsement stacking
    if total_weight <= 0:
        return 0.0
    return min(1.0, math.log1p(total_weight) / math.log1p(3.0))


def _compute_interaction_history_score(interactions, entity_id, zone_root=None):
    """Compute time-weighted interaction history score.

    Exponential decay weighting: recent activity counts more.
    Returns float [0.0, 1.0].
    """
    if not interactions:
        return 0.0

    # Weight by recency — most recent interactions count more
    n = len(interactions)
    half_life = CONFIG["decay_half_life_tics"]

    weighted_sum = 0.0
    for i, rec in enumerate(interactions):
        # Position-based decay: item at end of list is most recent
        age = n - 1 - i
        weight = math.pow(0.5, age / max(half_life, 1))
        weighted_sum += weight

    # Normalize to [0, 1] based on expected activity
    # A fully active entity in a 20-cycle window with ~5 interactions/cycle
    # would have ~100 interactions
    expected_max = CONFIG["diversity_window_cycles"] * 5
    return min(1.0, weighted_sum / max(expected_max * 0.3, 1))


def _compute_decay_factor(entity_id, zone_root=None):
    """Compute trust_score decay factor based on inactivity.

    Returns (factor: float [0, 1], decay_applied: bool).
    Decay is exponential with configurable half-life.
    """
    interactions = _get_entity_interactions(entity_id, zone_root=zone_root)

    if not interactions:
        # No interactions at all — full decay
        return (0.1, True)  # Floor at 0.1, not zero

    # Find most recent interaction timestamp/cycle
    last_cycle = 0
    for rec in interactions:
        c = rec.get("cycle", 0)
        if isinstance(c, (int, float)) and c > last_cycle:
            last_cycle = c

    # Estimate current cycle (use latest from any entity in registry)
    records = _load_jsonl(_registry_path(zone_root))
    current_cycle = last_cycle
    for rec in records:
        c = rec.get("cycle", 0)
        if isinstance(c, (int, float)) and c > current_cycle:
            current_cycle = c

    inactivity = current_cycle - last_cycle
    if inactivity <= 0:
        return (1.0, False)

    half_life = CONFIG["decay_half_life_tics"]
    factor = math.pow(0.5, inactivity / max(half_life, 1))
    # Floor at 0.1 — complete erasure requires explicit action
    factor = max(0.1, factor)

    return (factor, inactivity > 0)


# ---------------------------------------------------------------------------
# 3. STANDING TRANSITION CHECKER
#    Checks all four conditions: trust_score, time-lock, entry reqs, gate
# ---------------------------------------------------------------------------

def check_transition_eligibility(entity_id, zone_root=None):
    """Check if an entity is eligible for promotion to the next standing tier.

    All four conditions must be true simultaneously:
      1. trust_score >= threshold for target standing
      2. Time-lock satisfied (min duration at current standing)
      3. Entry requirements met (diversity, endorsement, etc.)
      4. Governance gate identified (automated, steward, constitutional)

    Meeting threshold creates eligibility, not promotion.

    Returns:
        dict with keys:
            eligible: bool
            current_standing: str
            target_standing: str or None
            trust_score: float
            requirements: dict — each requirement with met/unmet status
            reasons: list[str] — human-readable reasons for ineligibility
            governance_gate: str — type of gate required
    """
    current_standing = _get_entity_standing(entity_id, zone_root)
    if current_standing is None:
        return {
            "eligible": False,
            "current_standing": None,
            "target_standing": None,
            "trust_score": 0.0,
            "requirements": {},
            "reasons": ["Entity not found in visa registry"],
            "governance_gate": None,
        }

    target_standing = CONFIG["promotion_map"].get(current_standing)
    if target_standing is None:
        return {
            "eligible": False,
            "current_standing": current_standing,
            "target_standing": None,
            "trust_score": 0.0,
            "requirements": {},
            "reasons": [f"No promotion path from {current_standing} (already at max or unmapped)"],
            "governance_gate": None,
        }

    reasons = []
    requirements = {}

    # --- Condition 1: trust_score threshold ---
    trust_result = compute_trust_score(entity_id, zone_root)
    ts = trust_result["trust_score"]
    threshold = CONFIG["trust_thresholds"].get(target_standing, 1.0)
    trust_met = ts >= threshold
    requirements["trust_score"] = {
        "met": trust_met,
        "value": ts,
        "threshold": threshold,
    }
    if not trust_met:
        reasons.append(
            f"trust_score {ts:.4f} below threshold {threshold} for {target_standing}"
        )

    # --- Condition 2: Time-lock ---
    time_at_standing = _get_entity_time_at_standing(entity_id, zone_root)
    time_lock = CONFIG["time_locks"].get(target_standing, 1)
    time_met = time_at_standing >= time_lock
    requirements["time_lock"] = {
        "met": time_met,
        "value": time_at_standing,
        "threshold": time_lock,
    }
    if not time_met:
        reasons.append(
            f"Time at {current_standing}: {time_at_standing} tics, need {time_lock}"
        )

    # --- Condition 3: Entry requirements ---

    # 3a. Behavioral diversity (Tourist+ transitions)
    diversity = trust_result.get("diversity", compute_behavioral_diversity(entity_id, zone_root=zone_root))
    div_threshold = CONFIG["diversity_thresholds"].get(target_standing, 0.0)
    div_met = diversity["entropy"] >= div_threshold
    requirements["behavioral_diversity"] = {
        "met": div_met,
        "entropy": diversity["entropy"],
        "threshold": div_threshold,
        "types_active": diversity["types_active"],
    }
    if not div_met and div_threshold > 0:
        reasons.append(
            f"Behavioral diversity H={diversity['entropy']:.4f} below {div_threshold:.3f} for {target_standing}"
        )

    # 3b. Endorsement (Resident+ transitions — INV-STANDING-03)
    endorsement_met = True
    if target_standing in CONFIG["endorsement_required_tiers"]:
        endorsements = _get_entity_endorsements(entity_id, active_only=True, zone_root=zone_root)
        valid_endorsements = [
            e for e in endorsements
            if e.get("target_standing") == target_standing
        ]
        endorsement_met = len(valid_endorsements) > 0

        # Also check anti-Sybil: no duplicate home_federation_id
        fed_ids = set()
        sybil_clean = True
        for e in valid_endorsements:
            fid = e.get("home_federation_id")
            if fid and fid in fed_ids:
                sybil_clean = False
            if fid:
                fed_ids.add(fid)

        requirements["endorsement"] = {
            "met": endorsement_met and sybil_clean,
            "count": len(valid_endorsements),
            "required": True,
            "anti_sybil_clean": sybil_clean,
        }
        if not endorsement_met:
            reasons.append(
                f"No active endorsement for {target_standing} transition "
                f"(INV-STANDING-03: endorsement required for Resident+)"
            )
        if not sybil_clean:
            reasons.append("Anti-Sybil violation: multiple endorsers from same federation")
            endorsement_met = False
    else:
        requirements["endorsement"] = {
            "met": True,
            "count": 0,
            "required": False,
            "anti_sybil_clean": True,
        }

    # --- Condition 4: Governance gate ---
    gate = CONFIG["governance_gates"].get(target_standing, "constitutional_review")

    # INV-STANDING-04: No automated path to Citizen
    if target_standing == "citizen" and gate == "automated":
        gate = "constitutional_review"  # Hard override

    requirements["governance_gate"] = {
        "type": gate,
        "note": "Meeting threshold creates eligibility, not promotion. "
                "Governance gate approval required.",
    }

    # --- Eligibility determination ---
    eligible = all([
        trust_met,
        time_met,
        div_met or div_threshold == 0.0,
        endorsement_met,
    ])

    return {
        "eligible": eligible,
        "current_standing": current_standing,
        "target_standing": target_standing,
        "trust_score": ts,
        "requirements": requirements,
        "reasons": reasons if not eligible else [],
        "governance_gate": gate,
    }


# ---------------------------------------------------------------------------
# 4. ENDORSEMENT HANDLER
#    Process, validate, and record endorsements
# ---------------------------------------------------------------------------

def _deterministic_signal_id(condition_key, *parts):
    """Generate a deterministic signal ID from condition content.

    Per CGG Signal ID Determinism: IDs derived from the condition, not
    from timestamp or session.
    """
    content = "|".join(str(p) for p in [condition_key] + list(parts))
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    return f"sig_{condition_key}_{h}"


def process_endorsement(endorser_id, endorsed_id, target_standing, rationale,
                        zone_root=None):
    """Process an endorsement envelope.

    Validates:
      1. Endorser holds resident or citizen standing
      2. Endorsed entity is below target standing
      3. Endorser has not exceeded active endorsement cap (max 3)
      4. No same-federation duplicate (anti-Sybil)
      5. Rationale is substantive

    On success, appends to endorsements.jsonl via atomic append.

    Returns:
        dict with keys:
            accepted: bool
            endorsement_id: str or None
            rejection_reasons: list[str]
            endorser_active_count: int
    """
    rejection_reasons = []

    # --- Validation 1: Endorser standing ---
    endorser_standing = _get_entity_standing(endorser_id, zone_root)
    min_standing_idx = STANDING_ORDER.index(CONFIG["min_endorser_standing"])
    endorser_idx = STANDING_ORDER.index(endorser_standing) if endorser_standing in STANDING_ORDER else -1

    if endorser_idx < min_standing_idx:
        rejection_reasons.append(
            f"Endorser standing '{endorser_standing}' below minimum "
            f"'{CONFIG['min_endorser_standing']}'"
        )

    # --- Validation 2: Endorsed entity below target ---
    endorsed_standing = _get_entity_standing(endorsed_id, zone_root)
    if target_standing not in STANDING_ORDER:
        rejection_reasons.append(f"Invalid target standing: {target_standing}")
    elif endorsed_standing and target_standing in STANDING_ORDER:
        endorsed_idx = STANDING_ORDER.index(endorsed_standing) if endorsed_standing in STANDING_ORDER else -1
        target_idx = STANDING_ORDER.index(target_standing)
        if endorsed_idx >= target_idx:
            rejection_reasons.append(
                f"Endorsed entity already at or above target standing "
                f"(current: {endorsed_standing}, target: {target_standing})"
            )

    # --- Validation 3: Active endorsement cap ---
    active_count = _get_endorser_active_count(endorser_id, zone_root)
    cap = CONFIG["endorsement_cap"]
    if active_count >= cap:
        rejection_reasons.append(
            f"Endorser has {active_count}/{cap} active endorsements (cap reached)"
        )

    # --- Validation 4: Anti-Sybil (same-federation limit) ---
    existing_endorsements = _get_entity_endorsements(endorsed_id, active_only=True, zone_root=zone_root)
    endorser_fed_id = _get_entity_federation_id(endorser_id, zone_root)
    if endorser_fed_id:
        for e in existing_endorsements:
            if (e.get("target_standing") == target_standing
                    and e.get("home_federation_id") == endorser_fed_id):
                rejection_reasons.append(
                    f"Anti-Sybil: another endorser from federation "
                    f"'{endorser_fed_id}' already endorsed for this transition"
                )
                break

    # --- Validation 5: Rationale substantive ---
    if not rationale or len(rationale.strip()) < 10:
        rejection_reasons.append("Rationale must be substantive (min 10 characters)")

    # --- Decision ---
    if rejection_reasons:
        # Emit rejection signal
        _emit_signal(
            "endorsement.rejected",
            "WATCH",
            {
                "endorser_id": endorser_id,
                "endorsed_id": endorsed_id,
                "reasons": rejection_reasons,
            },
            zone_root,
        )
        return {
            "accepted": False,
            "endorsement_id": None,
            "rejection_reasons": rejection_reasons,
            "endorser_active_count": active_count,
        }

    # --- Compute trust_score for endorser at time of endorsement ---
    endorser_trust = compute_trust_score(endorser_id, zone_root)

    # --- Build endorsement record ---
    now = datetime.now(timezone.utc).isoformat()
    endorsement_id = _deterministic_signal_id(
        "endorsement", endorser_id, endorsed_id, target_standing
    )
    record = {
        "endorsement_id": endorsement_id,
        "envelope_type": "standing.endorsement",
        "endorser_id": endorser_id,
        "endorsed_id": endorsed_id,
        "endorser_standing": endorser_standing,
        "endorsed_current_standing": endorsed_standing,
        "target_standing": target_standing,
        "rationale": rationale.strip(),
        "endorser_trust_score_at_time": endorser_trust["trust_score"],
        "home_federation_id": endorser_fed_id,
        "state": "active",
        "timestamp": now,
    }

    # --- Atomic append ---
    atomic_append_jsonl(_endorsements_path(zone_root), record)

    # --- Emit signal ---
    _emit_signal(
        "endorsement.validated",
        "INFO",
        {
            "endorsement_id": endorsement_id,
            "endorser_id": endorser_id,
            "endorsed_id": endorsed_id,
            "target_standing": target_standing,
        },
        zone_root,
    )

    return {
        "accepted": True,
        "endorsement_id": endorsement_id,
        "rejection_reasons": [],
        "endorser_active_count": active_count + 1,
    }


def compute_endorser_penalty(evicted_entity_id, zone_root=None):
    """Compute endorser reputation cost on eviction.

    Direct endorser: -0.1 trust_score (PROVISIONAL)
    Chain dampening: 50% per hop, floor at 0.01.

    Returns list of penalty records.
    """
    penalties = []
    _compute_penalty_chain(evicted_entity_id, 0, penalties, set(), zone_root)
    return penalties


def _compute_penalty_chain(entity_id, depth, penalties, visited, zone_root):
    """Recursive penalty cascade with dampening."""
    if entity_id in visited:
        return
    visited.add(entity_id)

    direct_penalty = CONFIG["endorsement_penalty_direct"]
    dampening = CONFIG["endorsement_penalty_dampening"]
    floor = CONFIG["endorsement_penalty_floor"]

    penalty_amount = direct_penalty * (dampening ** depth)
    if penalty_amount < floor:
        return  # Cease cascade

    endorsers = _get_endorsers_for_entity(entity_id, zone_root)
    for endorser_id in endorsers:
        penalties.append({
            "endorser_id": endorser_id,
            "evicted_entity_id": entity_id if depth == 0 else penalties[0].get("evicted_entity_id"),
            "penalty_amount": round(penalty_amount, 4),
            "chain_depth": depth,
            "reason": "eviction" if depth == 0 else "chain_cascade",
        })
        # Recurse up the endorsement chain
        _compute_penalty_chain(endorser_id, depth + 1, penalties, visited, zone_root)


def _get_entity_federation_id(entity_id, zone_root=None):
    """Look up home_federation_id for an entity. Returns None if not set."""
    records = _load_jsonl(_registry_path(zone_root))
    for rec in records:
        if rec.get("entity_id") == entity_id:
            fid = rec.get("home_federation_id")
            if fid:
                return fid
    return None


# ---------------------------------------------------------------------------
# 5. DUE PROCESS INITIATOR
#    Scaled due process for involuntary standing actions
# ---------------------------------------------------------------------------

def initiate_due_process(entity_id, trigger_type, evidence, zone_root=None):
    """Initiate due process for an entity.

    Trigger types: trust_decay, specific_cause, biome_health
    Due process is scaled to the entity's current standing.

    Creates a due process record in actions.jsonl and emits signals
    for notice delivery.

    Hard constraints enforced:
      - No automated eviction above Tourist (INV)
      - Evidence must be specific, not general suspicion
      - One active proceeding per entity

    Returns:
        dict with keys:
            initiated: bool
            proceeding_id: str or None
            standing: str
            due_process_params: dict
            reasons: list[str] — reasons for rejection if not initiated
    """
    reasons = []

    # --- Look up entity standing ---
    standing = _get_entity_standing(entity_id, zone_root)
    if standing is None:
        return {
            "initiated": False,
            "proceeding_id": None,
            "standing": None,
            "due_process_params": {},
            "reasons": ["Entity not found in visa registry"],
        }

    # --- Validate trigger type ---
    valid_triggers = {"trust_decay", "specific_cause", "biome_health"}
    if trigger_type not in valid_triggers:
        reasons.append(f"Invalid trigger type: {trigger_type}. Must be one of {valid_triggers}")

    # --- Validate evidence ---
    if not evidence or len(str(evidence).strip()) < 10:
        reasons.append("Evidence must be specific, not general suspicion (min 10 chars)")

    # --- Check for existing active proceeding (no pile-up) ---
    existing = _load_jsonl(_due_process_path(zone_root))
    for rec in existing:
        if (rec.get("entity_id") == entity_id
                and rec.get("phase") in ("notice", "appeal", "review")):
            reasons.append(
                f"Active proceeding already exists for {entity_id} "
                f"(phase: {rec.get('phase')}). Consolidate, do not pile up."
            )
            break

    if reasons:
        return {
            "initiated": False,
            "proceeding_id": None,
            "standing": standing,
            "due_process_params": {},
            "reasons": reasons,
        }

    # --- Get scaled due process parameters ---
    dp_config = CONFIG["due_process"].get(standing, CONFIG["due_process"]["citizen"])

    # --- Hard constraint: no automated eviction above Tourist ---
    standing_idx = STANDING_ORDER.index(standing) if standing in STANDING_ORDER else 0
    tourist_idx = STANDING_ORDER.index("tourist")
    if standing_idx > tourist_idx and dp_config["authority"] == "automated":
        dp_config = dict(dp_config)
        dp_config["authority"] = "steward"
        dp_config["review_type"] = "steward_review"

    # --- Build due process notice envelope ---
    now = datetime.now(timezone.utc).isoformat()
    proceeding_id = _deterministic_signal_id(
        "due_process", entity_id, trigger_type, now[:10]
    )

    notice_record = {
        "proceeding_id": proceeding_id,
        "entity_id": entity_id,
        "current_standing": standing,
        "trigger_type": trigger_type,
        "trigger_evidence": evidence,
        "proposed_action": "reduce_standing",
        "appeal_window_tics": dp_config["appeal_window_tics"],
        "notice_period_tics": dp_config["notice_period_tics"],
        "review_authority": dp_config["authority"],
        "review_type": dp_config["review_type"],
        "phase": "notice",
        "timestamp": now,
    }

    # --- Atomic append to actions.jsonl ---
    atomic_append_jsonl(_due_process_path(zone_root), notice_record)

    # --- Emit signals ---
    _emit_signal(
        "due_process.initiated",
        "WATCH",
        {
            "proceeding_id": proceeding_id,
            "entity_id": entity_id,
            "standing": standing,
            "trigger_type": trigger_type,
        },
        zone_root,
    )

    _emit_signal(
        "due_process.notice_delivered",
        "INFO",
        {
            "proceeding_id": proceeding_id,
            "entity_id": entity_id,
            "appeal_window_tics": dp_config["appeal_window_tics"],
        },
        zone_root,
    )

    return {
        "initiated": True,
        "proceeding_id": proceeding_id,
        "standing": standing,
        "due_process_params": dp_config,
        "reasons": [],
    }


# ---------------------------------------------------------------------------
# University Admission (Student/foreign_delegate → Resident)
# Spec: autonomous_kernel/university-admission-spec.md
# ---------------------------------------------------------------------------

UNIVERSITY_CONFIG = {
    "trust_threshold": 0.6,
    "diversity_threshold": 2.0,   # log2(4)
    "min_acts_completed": 2,
    "review_authority": ["ent_crisis_steward", "ent_resolution_analyst"],
    "appeal_window_tics": 3,
    "queue_path_suffix": "biome/university-queue.jsonl",
}


def university_precheck(entity_id, zone_root=None):
    """Run automated pre-check for University admission eligibility.

    Returns dict with 'eligible' bool, 'reasons' list, and 'scores' snapshot.
    """
    trust_result = compute_trust_score(entity_id, zone_root=zone_root) or {}
    diversity_result = compute_behavioral_diversity(entity_id, zone_root=zone_root) or {}
    standing = _get_entity_standing(entity_id, zone_root=zone_root) or {}
    time_at = _get_entity_time_at_standing(entity_id, zone_root=zone_root) or {}
    endorsements = _get_entity_endorsements(entity_id, active_only=True, zone_root=zone_root) or []

    reasons = []
    trust_score = trust_result.get("trust_score", 0)
    diversity_entropy = diversity_result.get("entropy", 0)
    current_standing = standing.get("standing", "guest")
    tics_at_standing = time_at.get("tics_at_standing", 0)

    # Must be foreign_delegate (student equivalent) to apply
    if current_standing != "foreign_delegate":
        reasons.append(f"Standing is '{current_standing}', must be 'foreign_delegate'")

    if trust_score < UNIVERSITY_CONFIG["trust_threshold"]:
        reasons.append(f"Trust score {trust_score:.3f} < {UNIVERSITY_CONFIG['trust_threshold']}")

    if diversity_entropy < UNIVERSITY_CONFIG["diversity_threshold"]:
        reasons.append(f"Diversity entropy {diversity_entropy:.3f} < {UNIVERSITY_CONFIG['diversity_threshold']}")

    # Time-lock: min acts completed (proxy via tics)
    min_tics = CONFIG["time_locks"].get("resident", 10)
    if tics_at_standing < min_tics:
        reasons.append(f"Time at standing {tics_at_standing} < {min_tics} required")

    # Endorsement required per INV-STANDING-03
    active_endorsements = [e for e in endorsements if e.get("target_standing") == "resident"]
    if not active_endorsements:
        reasons.append("No active endorsement targeting 'resident' standing")

    eligible = len(reasons) == 0

    return {
        "entity_id": entity_id,
        "eligible": eligible,
        "reasons": reasons,
        "scores": {
            "trust_score": trust_score,
            "diversity_entropy": diversity_entropy,
            "current_standing": current_standing,
            "tics_at_standing": tics_at_standing,
            "active_endorsements": len(active_endorsements),
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def university_queue_entry(entity_id, zone_root=None):
    """Queue entity for University admission review (after passing pre-check).

    Returns the queue entry or error if pre-check fails.
    """
    precheck = university_precheck(entity_id, zone_root=zone_root)
    if not precheck["eligible"]:
        return {"error": "Pre-check failed", "reasons": precheck["reasons"]}

    zr = zone_root or str(_biome_path())
    queue_path = os.path.join(_resolve_zone_root(zone_root), "audit-logs",
                              UNIVERSITY_CONFIG["queue_path_suffix"])

    entry = {
        "type": "university_admission",
        "entity_id": entity_id,
        "status": "queued",
        "scores_at_queue": precheck["scores"],
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "review_authority": UNIVERSITY_CONFIG["review_authority"],
        "decision": None,
        "decision_at": None,
        "appeal_window_until": None,
    }

    _setup_lib_path()
    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(queue_path, entry)
    except ImportError:
        os.makedirs(os.path.dirname(queue_path), exist_ok=True)
        with open(queue_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # Emit signal for review queue
    _emit_signal("university.admission_queued", "COGNITIVE", {
        "entity_id": entity_id,
        "trust_score": precheck["scores"]["trust_score"],
    }, zone_root=zone_root)

    return entry


# ---------------------------------------------------------------------------
# Ambassador Graduation (Citizen → Ambassador lateral role)
# Spec: autonomous_kernel/ambassador-graduation-spec.md
# ---------------------------------------------------------------------------

AMBASSADOR_CONFIG = {
    "min_cross_federation_bonds": 2,
    "min_cross_federation_endorsements": 1,
    "min_bridge_behaviors": 5,
    "inactivity_threshold_tics": 15,
    "review_authority": ["ent_crisis_steward", "ent_homeskillet"],
    "nomination_path_suffix": "biome/ambassador-nominations.jsonl",
}


def ambassador_precheck(entity_id, zone_root=None):
    """Run automated pre-check for Ambassador graduation eligibility.

    Ambassador is lateral from Citizen — adds diplomatic capabilities,
    not higher internal standing.
    """
    standing = _get_entity_standing(entity_id, zone_root=zone_root) or {}
    current_standing = standing.get("standing", "guest")
    federation_id = _get_entity_federation_id(entity_id, zone_root=zone_root)

    reasons = []

    if current_standing != "citizen":
        reasons.append(f"Standing is '{current_standing}', must be 'citizen'")

    if not federation_id:
        reasons.append("No home_federation_id — required for Ambassador role")

    # Check cross-federation bonds (from biome bond data)
    zr = _resolve_zone_root(zone_root)
    bond_data_path = os.path.join(zr, "audit-logs", "biome", "bonds.jsonl")
    cross_fed_bonds = 0
    if os.path.isfile(bond_data_path):
        for line in open(bond_data_path):
            try:
                b = json.loads(line)
                if entity_id in b.get("partners", []):
                    partner_feds = b.get("home_federations", [])
                    if any(f != federation_id for f in partner_feds if f):
                        cross_fed_bonds += 1
            except (json.JSONDecodeError, ValueError):
                pass

    if cross_fed_bonds < AMBASSADOR_CONFIG["min_cross_federation_bonds"]:
        reasons.append(f"Cross-federation bonds {cross_fed_bonds} < "
                       f"{AMBASSADOR_CONFIG['min_cross_federation_bonds']} required")

    # Check cross-federation endorsements
    endorsements = _get_entity_endorsements(entity_id, active_only=True, zone_root=zone_root)
    cross_fed_endorsements = [e for e in endorsements
                              if e.get("endorser_federation") and
                              e.get("endorser_federation") != federation_id]
    if len(cross_fed_endorsements) < AMBASSADOR_CONFIG["min_cross_federation_endorsements"]:
        reasons.append(f"Cross-federation endorsements {len(cross_fed_endorsements)} < "
                       f"{AMBASSADOR_CONFIG['min_cross_federation_endorsements']} required")

    eligible = len(reasons) == 0

    return {
        "entity_id": entity_id,
        "eligible": eligible,
        "reasons": reasons,
        "profile": {
            "current_standing": current_standing,
            "home_federation_id": federation_id,
            "cross_federation_bonds": cross_fed_bonds,
            "cross_federation_endorsements": len(cross_fed_endorsements),
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def ambassador_nominate(entity_id, nominator_id, zone_root=None):
    """Submit Ambassador graduation nomination (after pre-check passes).

    Nominations route to constitutional review via inbox.
    """
    precheck = ambassador_precheck(entity_id, zone_root=zone_root)
    if not precheck["eligible"]:
        return {"error": "Pre-check failed", "reasons": precheck["reasons"]}

    zr = _resolve_zone_root(zone_root)
    nom_path = os.path.join(zr, "audit-logs",
                            AMBASSADOR_CONFIG["nomination_path_suffix"])

    nomination = {
        "type": "ambassador_nomination",
        "entity_id": entity_id,
        "nominator_id": nominator_id,
        "status": "pending_review",
        "profile_at_nomination": precheck["profile"],
        "nominated_at": datetime.now(timezone.utc).isoformat(),
        "review_authority": AMBASSADOR_CONFIG["review_authority"],
        "decision": None,
    }

    _setup_lib_path()
    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(nom_path, nomination)
    except ImportError:
        os.makedirs(os.path.dirname(nom_path), exist_ok=True)
        with open(nom_path, "a") as f:
            f.write(json.dumps(nomination) + "\n")

    _emit_signal("ambassador.nomination_submitted", "COGNITIVE", {
        "entity_id": entity_id,
        "nominator_id": nominator_id,
    }, zone_root=zone_root)

    return nomination


def ambassador_inactivity_check(entity_id, current_tic, zone_root=None):
    """Check if an Ambassador is inactive (> threshold tics since last bridge activity).

    Returns inactivity status and recommendation.
    """
    zr = _resolve_zone_root(zone_root)
    # Check last bridge activity from interactions
    interactions = _get_entity_interactions(entity_id, zone_root=zone_root)
    bridge_interactions = [i for i in interactions
                          if i.get("type") in ("collaboration", "teaching", "exchange")
                          and i.get("cross_federation", False)]

    if bridge_interactions:
        last_activity_tic = max(i.get("tic", 0) for i in bridge_interactions)
    else:
        last_activity_tic = 0

    tics_inactive = current_tic - last_activity_tic if current_tic and last_activity_tic else 999
    is_inactive = tics_inactive > AMBASSADOR_CONFIG["inactivity_threshold_tics"]

    return {
        "entity_id": entity_id,
        "is_inactive": is_inactive,
        "tics_since_last_bridge_activity": tics_inactive,
        "threshold_tics": AMBASSADOR_CONFIG["inactivity_threshold_tics"],
        "recommendation": "inactivity_review" if is_inactive else "active",
    }


# ---------------------------------------------------------------------------
# Ecotone Visa (cross-biome movement)
# Spec: autonomous_kernel/cross-biome-visa-spec.md
# ---------------------------------------------------------------------------

ECOTONE_CONFIG = {
    "default_visa_ttl_tics": 10,
    "min_standing_for_visa": "tourist",
    "visa_registry_suffix": "biome/visa-registry.jsonl",
}


def ecotone_request_visa(entity_id, source_biome, target_biome, zone_root=None):
    """Request a cross-biome visa at an ecotone post.

    Evaluates standing and issues TTL-bound visa.
    """
    standing = _get_entity_standing(entity_id, zone_root=zone_root) or {}
    current_standing = standing.get("standing", "guest")
    standing_order = CONFIG["standing_order"]

    min_idx = standing_order.index(ECOTONE_CONFIG["min_standing_for_visa"])
    current_idx = standing_order.index(current_standing) if current_standing in standing_order else -1

    if current_idx < min_idx:
        return {
            "entity_id": entity_id,
            "visa_status": "denied",
            "reason": f"Standing '{current_standing}' below minimum '{ECOTONE_CONFIG['min_standing_for_visa']}'",
        }

    now = datetime.now(timezone.utc)
    visa_id = _deterministic_signal_id("visa", entity_id, source_biome, target_biome)

    visa = {
        "type": "ecotone_visa",
        "visa_id": visa_id,
        "entity_id": entity_id,
        "source_biome": source_biome,
        "target_biome": target_biome,
        "standing_snapshot": current_standing,
        "issued_at": now.isoformat(),
        "ttl_tics": ECOTONE_CONFIG["default_visa_ttl_tics"],
        "status": "issued",
        "revocation_reason": None,
    }

    zr = _resolve_zone_root(zone_root)
    registry_path = os.path.join(zr, "audit-logs",
                                 ECOTONE_CONFIG["visa_registry_suffix"])

    _setup_lib_path()
    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(registry_path, visa)
    except ImportError:
        os.makedirs(os.path.dirname(registry_path), exist_ok=True)
        with open(registry_path, "a") as f:
            f.write(json.dumps(visa) + "\n")

    return visa


def ecotone_revoke_visa(visa_id, reason, zone_root=None):
    """Revoke an active visa. Appends revocation entry to registry."""
    revocation = {
        "type": "ecotone_visa_revocation",
        "visa_id": visa_id,
        "status": "revoked",
        "revocation_reason": reason,
        "revoked_at": datetime.now(timezone.utc).isoformat(),
    }

    zr = _resolve_zone_root(zone_root)
    registry_path = os.path.join(zr, "audit-logs",
                                 ECOTONE_CONFIG["visa_registry_suffix"])

    _setup_lib_path()
    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(registry_path, revocation)
    except ImportError:
        with open(registry_path, "a") as f:
            f.write(json.dumps(revocation) + "\n")

    return revocation


def _resolve_zone_root(zone_root=None):
    """Resolve zone root from argument or auto-detect."""
    if zone_root:
        return str(zone_root)
    # Walk up from script location
    p = Path(__file__).resolve().parent
    for _ in range(10):
        if (p / ".ticzone").exists() or (p / "audit-logs").is_dir():
            return str(p)
        if p.parent == p:
            break
        p = p.parent
    return os.getcwd()


# ---------------------------------------------------------------------------
# Signal emission helper
# ---------------------------------------------------------------------------

def _emit_signal(signal_pattern, band, payload, zone_root=None):
    """Emit a signal to the signals JSONL log.

    Signal IDs are deterministic per CGG Signal ID Determinism.
    """
    sig_id = _deterministic_signal_id(
        signal_pattern,
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )
    record = {
        "signal_id": sig_id,
        "pattern": signal_pattern,
        "band": band,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "standing-engine",
    }
    try:
        atomic_append_jsonl(_signals_path(zone_root), record)
    except Exception as e:
        print(f"[standing-engine] Signal emission failed: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def _json_serializer(obj):
    """Handle non-standard types for JSON serialization."""
    if isinstance(obj, set):
        return sorted(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _format_json(data):
    """Pretty-print JSON for CLI output."""
    return json.dumps(data, indent=2, default=_json_serializer)


def main():
    parser = argparse.ArgumentParser(
        description="Standing Progression Engine — trust_score, diversity, transitions, endorsements, due process",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --compute-trust ent_visitor_abc123
  %(prog)s --diversity ent_visitor_abc123
  %(prog)s --check-eligibility ent_visitor_abc123
  %(prog)s --endorse ent_res_001 ent_visitor_abc123 resident "Demonstrated sustained diverse participation"
  %(prog)s --due-process ent_visitor_abc123 trust_decay "trust_score below 0.4 for 6 tics"
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--compute-trust",
        metavar="ENTITY_ID",
        help="Compute trust_score for an entity",
    )
    group.add_argument(
        "--diversity",
        metavar="ENTITY_ID",
        help="Compute behavioral diversity entropy for an entity",
    )
    group.add_argument(
        "--check-eligibility",
        metavar="ENTITY_ID",
        help="Check standing promotion eligibility for an entity",
    )
    group.add_argument(
        "--endorse",
        nargs=4,
        metavar=("ENDORSER_ID", "ENDORSED_ID", "TARGET_STANDING", "RATIONALE"),
        help="Process an endorsement",
    )
    group.add_argument(
        "--due-process",
        nargs=3,
        metavar=("ENTITY_ID", "TRIGGER_TYPE", "EVIDENCE"),
        help="Initiate due process for an entity",
    )
    group.add_argument(
        "--penalty-cascade",
        metavar="EVICTED_ENTITY_ID",
        help="Compute endorser penalty cascade for an evicted entity",
    )
    group.add_argument(
        "--university-precheck",
        metavar="ENTITY_ID",
        help="Check University admission eligibility",
    )
    group.add_argument(
        "--university-queue",
        metavar="ENTITY_ID",
        help="Queue entity for University admission review",
    )
    group.add_argument(
        "--ambassador-precheck",
        metavar="ENTITY_ID",
        help="Check Ambassador graduation eligibility",
    )
    group.add_argument(
        "--ambassador-nominate",
        nargs=2,
        metavar=("ENTITY_ID", "NOMINATOR_ID"),
        help="Nominate entity for Ambassador graduation",
    )
    group.add_argument(
        "--visa-request",
        nargs=3,
        metavar=("ENTITY_ID", "SOURCE_BIOME", "TARGET_BIOME"),
        help="Request ecotone visa for cross-biome movement",
    )
    group.add_argument(
        "--config",
        action="store_true",
        help="Print current PROVISIONAL configuration",
    )

    parser.add_argument(
        "--zone-root",
        default=None,
        help="Override zone root (default: auto-detect)",
    )

    args = parser.parse_args()
    zr = args.zone_root

    if args.compute_trust:
        result = compute_trust_score(args.compute_trust, zone_root=zr)
        print(_format_json(result))

    elif args.diversity:
        result = compute_behavioral_diversity(args.diversity, zone_root=zr)
        print(_format_json(result))

    elif args.check_eligibility:
        result = check_transition_eligibility(args.check_eligibility, zone_root=zr)
        print(_format_json(result))

    elif args.endorse:
        endorser_id, endorsed_id, target, rationale = args.endorse
        result = process_endorsement(endorser_id, endorsed_id, target, rationale, zone_root=zr)
        print(_format_json(result))

    elif args.due_process:
        entity_id, trigger, evidence = args.due_process
        result = initiate_due_process(entity_id, trigger, evidence, zone_root=zr)
        print(_format_json(result))

    elif args.penalty_cascade:
        result = compute_endorser_penalty(args.penalty_cascade, zone_root=zr)
        print(_format_json(result))

    elif args.university_precheck:
        result = university_precheck(args.university_precheck, zone_root=zr)
        print(_format_json(result))

    elif args.university_queue:
        result = university_queue_entry(args.university_queue, zone_root=zr)
        print(_format_json(result))

    elif args.ambassador_precheck:
        result = ambassador_precheck(args.ambassador_precheck, zone_root=zr)
        print(_format_json(result))

    elif args.ambassador_nominate:
        entity_id, nominator_id = args.ambassador_nominate
        result = ambassador_nominate(entity_id, nominator_id, zone_root=zr)
        print(_format_json(result))

    elif args.visa_request:
        entity_id, source, target = args.visa_request
        result = ecotone_request_visa(entity_id, source, target, zone_root=zr)
        print(_format_json(result))

    elif args.config:
        print(_format_json(CONFIG))

    return 0


if __name__ == "__main__":
    sys.exit(main())
