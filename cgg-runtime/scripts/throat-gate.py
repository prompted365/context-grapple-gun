#!/usr/bin/env python3
"""throat-gate.py — Throat Gate handler: transition between Docks admission and biome entry.

Implements the Throat Gate specification (autonomous_kernel/throat-gate-spec.md):
  1. Accept admitted visitor entity_id + session envelope from Docks
  2. Run visitor through 4 minimum viable concepts (environmental, not instructional)
  3. Dynamic modulation: adjust traversal pacing based on probe results
  4. Tier-gated visibility: filter biome information by standing
  5. Exit observation: emit encounter quality checkpoints #3 and #4
  6. Output: visitor ready for biome entry with concept comprehension signals

The Gate teaches exactly four concepts:
  1. Resources exist and are scarce
  2. Network connections have cost and yield
  3. Pruning is mandatory
  4. You are one tendril of a larger organism

Importable as a module:
    from throat_gate import ThroatGate
    gate = ThroatGate(zone_root="/path/to/canonical")
    result = gate.traverse(session_envelope)

Runnable as CLI:
    python3 throat-gate.py traverse --entity-id ent_visitor_abc123
    python3 throat-gate.py traverse --session-json '{"entity_id":"...","probe_results":{...}}'
    python3 throat-gate.py status --entity-id ent_visitor_abc123

Depends on:
    - scripts/lib/atomic_append.py (JSONL writes)
    - scripts/zone_root.py (zone root discovery)
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from zone_root import resolve_zone_root, load_ticzone, audit_logs_path
from lib.atomic_append import atomic_append_jsonl, atomic_write_json


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

# The four minimum viable concepts — the Gate teaches exactly these, no more
CONCEPTS = [
    {
        "id": 1,
        "name": "scarcity",
        "physics_ref": "INV-BIOME-01",
        "expression": "invariant_sculpture",
        "description": "Resources exist and are scarce — you must choose",
    },
    {
        "id": 2,
        "name": "cost_yield",
        "physics_ref": "physarum_edge_weight",
        "expression": "entity_monument",
        "description": "Network connections have cost and yield — building is not free",
    },
    {
        "id": 3,
        "name": "pruning",
        "physics_ref": "act_2_pruning",
        "expression": "invariant_sculpture",
        "description": "Pruning is mandatory — you cannot keep everything",
    },
    {
        "id": 4,
        "name": "organism",
        "physics_ref": "aggregate_biome_health",
        "expression": "entity_monument",
        "description": "You are one tendril of a larger organism",
    },
]

# Standing-to-tier mapping for Gate modulation
# From throat-gate-spec.md: tier determines traversal pacing
STANDING_TIERS = {
    "guest": "tourist",       # Default for new visitors
    "foreign_delegate": "student",
    "resident": "resident",
    "citizen": "citizen",
}

# Modulation profiles: how the Gate adjusts per tier
# All values are multipliers on base traversal parameters
MODULATION_PROFILES = {
    "tourist": {
        "traversal_pace": 1.5,     # Slower — more observation time
        "sculpture_persistence": 2.0,  # Sculptures linger longer
        "concept_repetition": True,    # Concepts 1-2 repeated near exit
        "monument_detail": 1.0,
        "abbreviated": False,
    },
    "student": {
        "traversal_pace": 1.0,     # Standard cadence
        "sculpture_persistence": 1.0,
        "concept_repetition": False,
        "monument_detail": 1.0,
        "abbreviated": False,
    },
    "resident": {
        "traversal_pace": 0.5,     # Abbreviated — returning visitor
        "sculpture_persistence": 0.5,
        "concept_repetition": False,
        "monument_detail": 0.5,      # Reduced monuments
        "abbreviated": True,
    },
    "citizen": {
        "traversal_pace": 0.3,     # Highly abbreviated
        "sculpture_persistence": 0.3,
        "concept_repetition": False,
        "monument_detail": 0.3,
        "abbreviated": True,
    },
}

# Tier-gated visibility: what each tier sees within and beyond the Gate
# From throat-gate-spec.md Table
VISIBILITY_GATES = {
    "public": {
        "gate": ["concept_names"],
        "biome": [],
    },
    "tourist": {
        "gate": ["concept_names", "concept_demonstrations"],
        "biome": ["resource_state", "local_connections", "immediate_neighborhood"],
    },
    "student": {
        "gate": ["concept_names", "concept_demonstrations", "full_interaction"],
        "biome": ["resource_state", "local_connections", "immediate_neighborhood",
                   "network_visualization", "resource_flow_paths", "edge_weights"],
    },
    "resident": {
        "gate": ["concept_names", "concept_demonstrations", "full_interaction"],
        "biome": ["resource_state", "local_connections", "immediate_neighborhood",
                   "network_visualization", "resource_flow_paths", "edge_weights",
                   "health_metrics", "aggregate_network_state", "governance_signals"],
    },
    "citizen": {
        "gate": ["concept_names", "concept_demonstrations", "full_interaction"],
        "biome": ["resource_state", "local_connections", "immediate_neighborhood",
                   "network_visualization", "resource_flow_paths", "edge_weights",
                   "health_metrics", "aggregate_network_state", "governance_signals",
                   "full_constitutional_visibility"],
    },
}

# PROVISIONAL thresholds — no calibration evidence
DISORIENTATION_THRESHOLD_CYCLES = 2.0  # time-to-first-action > 2x median = disorientation
COHORT_DISORIENTATION_RATE = 0.30       # >30% disorientation = Gate overload

# Base traversal time per concept (arbitrary units — cycle-equivalents)
BASE_CONCEPT_DURATION = 1.0


# ─────────────────────────────────────────────
# Signal helpers — deterministic IDs
# ─────────────────────────────────────────────

def _content_hash(*parts):
    """Deterministic content-addressed hash from string parts."""
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()[:8]


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def _emit_signal(zone_root, signal_type, content, source="throat-gate.py"):
    """Emit a signal to the daily signals JSONL file."""
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    signal_dir = os.path.join(al_path, "signals")
    os.makedirs(signal_dir, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    signal_file = os.path.join(signal_dir, f"{date_str}.jsonl")

    # Deterministic signal ID from content hash
    det_parts = [signal_type]
    for k in sorted(content.keys()):
        det_parts.append(f"{k}={content[k]}")
    sig_id = f"sig_{signal_type}_{_content_hash(*det_parts)}"

    signal = {
        "signal_id": sig_id,
        "band": "COGNITIVE",
        "kind": "WATCH" if "quality" in signal_type else "INFO",
        "type": signal_type,
        "source": source,
        "subsystem": "throat_gate",
        "payload": content,
        "emitted_at": now.isoformat(),
        "origin": "deterministic",
    }
    atomic_append_jsonl(signal_file, signal)
    return sig_id


# ─────────────────────────────────────────────
# Visitor session loading
# ─────────────────────────────────────────────

def _load_visitor_session(zone_root, entity_id):
    """Load a visitor's session from the visitor registry."""
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    registry_path = os.path.join(al_path, "visitors", "registry.jsonl")

    if not os.path.isfile(registry_path):
        return None

    with open(registry_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("entity_id") == entity_id:
                    return entry
            except json.JSONDecodeError:
                continue
    return None


# ─────────────────────────────────────────────
# Throat Gate Handler
# ─────────────────────────────────────────────

class ThroatGate:
    """Throat Gate handler — environmental onboarding through four minimum viable concepts.

    The Gate teaches through invariant sculptures and entity monuments,
    not through text, instruction, or tutorial. Modulation adjusts
    traversal pacing based on probe results. The visitor does not know
    they are being modulated.
    """

    def __init__(self, zone_root=None):
        self.zone_root = zone_root or resolve_zone_root()
        self.tz_config = load_ticzone(self.zone_root)
        self.al_path = audit_logs_path(self.zone_root, self.tz_config)
        self.visa_registry_path = os.path.join(
            self.al_path, "biome", "visa-registry", "registry.jsonl"
        )

    def traverse(self, session_envelope):
        """Run a visitor through the Throat Gate.

        Args:
            session_envelope: Dict from Docks admission containing:
                - entity_id (required)
                - probe_results (required) — dict of probe_name: pass/fail/skipped
                - standing (required)
                - probes_passed (required) — int 0-4
                - visa_state (required) — should be "admitted"

        Returns:
            {
                "ok": bool,
                "entity_id": str,
                "gate_traversal": {...},  # Full traversal record
                "visibility": {...},      # Tier-gated visibility grants
                "signals_emitted": [...], # Signal IDs emitted
                "ready_for_biome": bool,
            }
        """
        now = datetime.now(timezone.utc)
        start_time = time.monotonic()
        signals = []

        # ── 1. Validate session envelope ──
        entity_id = session_envelope.get("entity_id")
        probe_results = session_envelope.get("probe_results", {})
        standing = session_envelope.get("standing", "guest")
        probes_passed = session_envelope.get("probes_passed", 0)
        visa_state = session_envelope.get("visa_state")

        if not entity_id:
            return {"ok": False, "error": "missing_entity_id"}
        if visa_state not in ("admitted", "verified"):
            return {
                "ok": False,
                "error": "visitor_not_admitted",
                "visa_state": visa_state,
                "message": "Visitor must be admitted before Gate traversal.",
            }

        # ── 2. Determine modulation tier ──
        tier = self._determine_tier(standing, probes_passed)
        profile = MODULATION_PROFILES.get(tier, MODULATION_PROFILES["student"])

        # ── 3. Traverse the four concepts ──
        concept_observations = []
        traversal_start = time.monotonic()

        for concept in CONCEPTS:
            observation = self._traverse_concept(
                entity_id, concept, profile, probe_results
            )
            concept_observations.append(observation)

        # Concept repetition for Tourist tier (concepts 1-2 near exit)
        repeated = []
        if profile["concept_repetition"]:
            for concept in CONCEPTS[:2]:
                rep = self._traverse_concept(
                    entity_id, concept, profile, probe_results,
                    is_repetition=True,
                )
                repeated.append(rep)

        traversal_duration_ms = int((time.monotonic() - traversal_start) * 1000)

        # ── 4. Compute tier-gated visibility ──
        visibility = self._compute_visibility(tier)

        # ── 5. Emit checkpoint #3: First invariant encounter ──
        first_concept = concept_observations[0] if concept_observations else {}
        sig_3 = _emit_signal(self.zone_root, "encounter.quality.first_invariant_frame", {
            "entity_id": entity_id,
            "tier": tier,
            "first_concept_id": first_concept.get("concept_id", 1),
            "first_concept_response_ms": first_concept.get("observation_duration_ms", 0),
            "probes_passed": probes_passed,
        })
        signals.append(sig_3)

        # ── 6. Emit checkpoint #4: Throat Gate exit state ──
        concept_engagement = self._assess_concept_engagement(concept_observations)
        sig_4 = _emit_signal(self.zone_root, "encounter.quality.gate_exit_state", {
            "entity_id": entity_id,
            "tier": tier,
            "traversal_duration_ms": traversal_duration_ms,
            "concepts_encountered": len(concept_observations),
            "concept_engagement_score": concept_engagement["score"],
            "modulation_applied": tier,
            "abbreviated": profile["abbreviated"],
        })
        signals.append(sig_4)

        # ── 7. Write visa state transition: admitted -> gate_traversed ──
        self._write_visa_transition(
            entity_id=entity_id,
            transition="admitted->gate_traversed",
            from_visa_state="admitted",
            to_visa_state="gate_traversed",
            evidence=f"Gate traversal complete: {len(concept_observations)} concepts, tier={tier}",
            timestamp=now,
        )

        total_duration_ms = int((time.monotonic() - start_time) * 1000)

        gate_traversal = {
            "entity_id": entity_id,
            "tier": tier,
            "standing": standing,
            "probes_passed": probes_passed,
            "modulation_profile": tier,
            "concepts_encountered": [c["concept_id"] for c in concept_observations],
            "concept_observations": concept_observations,
            "concept_repetitions": repeated,
            "concept_engagement": concept_engagement,
            "traversal_duration_ms": traversal_duration_ms,
            "total_duration_ms": total_duration_ms,
            "abbreviated": profile["abbreviated"],
            "traversed_at": now.isoformat(),
        }

        return {
            "ok": True,
            "entity_id": entity_id,
            "gate_traversal": gate_traversal,
            "visibility": visibility,
            "signals_emitted": signals,
            "ready_for_biome": True,
        }

    def _determine_tier(self, standing, probes_passed):
        """Determine Gate modulation tier from standing and probe results.

        Priority:
          1. Standing-based tier (Resident+)
          2. Probe-based tier (Tourist vs Student)
        """
        # Resident+ get abbreviated regardless of probe results
        tier_from_standing = STANDING_TIERS.get(standing)
        if tier_from_standing in ("resident", "citizen"):
            return tier_from_standing

        # Probe-based: all 4 probes = Student, otherwise Tourist
        if probes_passed >= 4:
            return "student"
        return "tourist"

    def _traverse_concept(self, entity_id, concept, profile, probe_results,
                          is_repetition=False):
        """Simulate traversal of a single concept.

        The Gate communicates through environmental features:
          - Invariant sculptures (concepts 1, 3): static, observable
          - Entity monuments (concepts 2, 4): dynamic, living behavior

        Returns observation record for the concept.
        """
        concept_id = concept["id"]
        expression = concept["expression"]

        # Compute observation duration based on modulation profile
        base_duration = BASE_CONCEPT_DURATION
        if expression == "invariant_sculpture":
            duration = base_duration * profile["sculpture_persistence"]
        else:
            duration = base_duration * profile["monument_detail"]

        # Scale by overall traversal pace
        duration *= profile["traversal_pace"]

        # Repetitions are shorter
        if is_repetition:
            duration *= 0.5

        # Convert to milliseconds for record-keeping
        duration_ms = int(duration * 1000)

        return {
            "concept_id": concept_id,
            "concept_name": concept["name"],
            "expression_type": expression,
            "physics_ref": concept["physics_ref"],
            "observation_duration_ms": duration_ms,
            "is_repetition": is_repetition,
            "modulation_pace": profile["traversal_pace"],
        }

    def _assess_concept_engagement(self, observations):
        """Assess overall concept engagement from traversal observations.

        This is an observation about the Gate's effectiveness, not the visitor's aptitude.
        The score represents how much observation time the Gate provided relative to baseline.
        """
        if not observations:
            return {"score": 0.0, "total_observation_ms": 0, "concept_count": 0}

        total_ms = sum(o["observation_duration_ms"] for o in observations)
        avg_ms = total_ms / len(observations)

        # Engagement score: normalized against baseline (1000ms per concept)
        baseline_total = len(observations) * 1000
        score = min(1.0, total_ms / baseline_total) if baseline_total > 0 else 0.0

        return {
            "score": round(score, 4),
            "total_observation_ms": total_ms,
            "concept_count": len(observations),
            "avg_observation_ms": int(avg_ms),
        }

    def _compute_visibility(self, tier):
        """Compute tier-gated visibility grants.

        Visibility is additive: each tier sees everything the previous tier sees,
        plus additional layers.
        """
        grants = VISIBILITY_GATES.get(tier, VISIBILITY_GATES["tourist"])
        return {
            "tier": tier,
            "gate_visibility": grants["gate"],
            "biome_visibility": grants["biome"],
        }

    def _write_visa_transition(self, entity_id, transition, from_visa_state,
                               to_visa_state, evidence, timestamp):
        """Write a visa state transition to the visa registry."""
        record = {
            "entity_id": entity_id,
            "transition": transition,
            "from_visa_state": from_visa_state,
            "to_visa_state": to_visa_state,
            "timestamp": timestamp.isoformat(),
            "evidence": evidence,
            "authority": "throat_gate",
        }
        atomic_append_jsonl(self.visa_registry_path, record)

    def get_traversal_status(self, entity_id):
        """Check if a visitor has traversed the Gate by reading visa registry."""
        if not os.path.isfile(self.visa_registry_path):
            return {"traversed": False, "entity_id": entity_id}

        with open(self.visa_registry_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if (entry.get("entity_id") == entity_id
                            and entry.get("to_visa_state") == "gate_traversed"):
                        return {
                            "traversed": True,
                            "entity_id": entity_id,
                            "traversed_at": entry.get("timestamp"),
                            "evidence": entry.get("evidence"),
                        }
                except json.JSONDecodeError:
                    continue

        return {"traversed": False, "entity_id": entity_id}


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Throat Gate handler — environmental onboarding through four minimum viable concepts."
    )
    sub = parser.add_subparsers(dest="command")

    # ── traverse ──
    trav_p = sub.add_parser("traverse", help="Run a visitor through the Throat Gate")
    trav_p.add_argument("--entity-id",
                        help="Visitor entity ID (loads session from registry)")
    trav_p.add_argument("--session-json",
                        help="Full session envelope as JSON string")
    trav_p.add_argument("--zone-root", default=None)

    # ── status ──
    stat_p = sub.add_parser("status", help="Check Gate traversal status for a visitor")
    stat_p.add_argument("--entity-id", required=True)
    stat_p.add_argument("--zone-root", default=None)

    # ── concepts ──
    sub.add_parser("concepts", help="List the four minimum viable concepts")

    args = parser.parse_args()

    if args.command == "traverse":
        zone_root = args.zone_root or resolve_zone_root()
        gate = ThroatGate(zone_root)

        if args.session_json:
            session = json.loads(args.session_json)
        elif args.entity_id:
            # Load session from visitor registry
            visitor = _load_visitor_session(zone_root, args.entity_id)
            if not visitor:
                print(json.dumps({
                    "ok": False,
                    "error": "visitor_not_found",
                    "entity_id": args.entity_id,
                }))
                sys.exit(1)
            # Build session envelope from registry entry
            session = {
                "entity_id": visitor["entity_id"],
                "probe_results": visitor.get("probe_results", {}),
                "standing": visitor.get("standing", "guest"),
                "probes_passed": sum(
                    1 for v in visitor.get("probe_results", {}).values()
                    if v == "pass"
                ),
                "visa_state": visitor.get("visa_state", "admitted"),
            }
        else:
            print(json.dumps({
                "ok": False,
                "error": "missing_args",
                "message": "--entity-id or --session-json required",
            }))
            sys.exit(1)

        result = gate.traverse(session)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("ok") else 1)

    elif args.command == "status":
        zone_root = args.zone_root or resolve_zone_root()
        gate = ThroatGate(zone_root)
        status = gate.get_traversal_status(args.entity_id)
        print(json.dumps(status, indent=2))
        sys.exit(0)

    elif args.command == "concepts":
        for c in CONCEPTS:
            print(f"  [{c['id']}] {c['name']:<20} ({c['expression']}) — {c['description']}")
        sys.exit(0)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
