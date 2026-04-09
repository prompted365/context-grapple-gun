#!/usr/bin/env python3
"""encounter-monitor.py — Encounter quality monitoring: 12 checkpoints across the visitor journey.

Implements the encounter quality specification (autonomous_kernel/encounter-quality-spec.md):
  - 12 named checkpoints from pre-registration through postcard generation
  - Dual signal types: performance (quantitative, automated) + quality (interpretive, steward-mediated)
  - Failure-state classification: productive friction / inert friction / clean failure
  - Behavioral contraction test: Shannon entropy over sliding window
  - Environmental intervention generator: biome adjustments for inert friction
  - Architect engagement tracking: dropout detection + classification

Importable as a module:
    from encounter_monitor import EncounterMonitor
    monitor = EncounterMonitor(zone_root="/path/to/canonical")
    result = monitor.check(checkpoint_number=5, entity_id="ent_visitor_abc")
    report = monitor.friction_report(entity_id="ent_visitor_abc")

Runnable as CLI:
    python3 encounter-monitor.py --check 5 ent_visitor_abc123
    python3 encounter-monitor.py --scan-all
    python3 encounter-monitor.py --friction-report ent_visitor_abc123

Depends on:
    - scripts/lib/atomic_append.py (JSONL writes)
    - scripts/zone_root.py (zone root discovery)
    - audit-logs/biome/state/ (biome state files)
    - audit-logs/visitors/registry.jsonl (visitor history)
"""

import argparse
import collections
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from zone_root import resolve_zone_root, load_ticzone, audit_logs_path
from lib.atomic_append import atomic_append_jsonl


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

# PROVISIONAL thresholds — no calibration evidence per CogPR-46
CONTRACTION_WINDOW = 5         # consecutive cycles for behavioral contraction test
CONTRACTION_THRESHOLD = 0.0    # entropy drop > this over window = contraction flag
INERT_FRICTION_CYCLES = 5      # consecutive cycles of contraction = inert friction
CLEAN_FAILURE_TIMEOUT_CYCLES = 10  # cycles of zero interaction = clean failure
INTERVENTION_COOLDOWN_CYCLES = 3   # minimum cycles between interventions

# Edge types from behavioral-diversity-spec.md
EDGE_TYPES = [
    "exploration", "creation", "exchange", "governance",
    "collaboration", "teaching", "defense", "reflection",
]

# ─────────────────────────────────────────────
# 12 Checkpoint definitions
# ─────────────────────────────────────────────

CHECKPOINTS = {
    1:  {
        "name": "Pre-registration pause",
        "phase": "Docks",
        "signal_type": "quality",
        "signal_id_prefix": "encounter.quality.preregistration_intent",
        "description": "Intent quality — what brought the visitor to registration?",
    },
    2:  {
        "name": "Docks probe completion",
        "phase": "Docks",
        "signal_type": "performance",
        "signal_id_prefix": "encounter.perf.probe_completion",
        "description": "Probe result metrics: pass/fail per probe, timing, TVI tier.",
    },
    3:  {
        "name": "First invariant encounter",
        "phase": "Throat Gate",
        "signal_type": "quality",
        "signal_id_prefix": "encounter.quality.first_invariant_frame",
        "description": "Conceptual frame the visitor brought in.",
    },
    4:  {
        "name": "Throat Gate exit state",
        "phase": "Throat Gate",
        "signal_type": "quality",
        "signal_id_prefix": "encounter.quality.gate_exit_state",
        "description": "Sharpest early friction signal — did concepts land?",
    },
    5:  {
        "name": "First biome action",
        "phase": "Act I",
        "signal_type": "performance",
        "signal_id_prefix": "encounter.perf.time_to_first_action",
        "description": "Time-to-first-action after Gate exit.",
    },
    6:  {
        "name": "First network edge formation",
        "phase": "Act I",
        "signal_type": "quality",
        "signal_id_prefix": "encounter.quality.first_edge_posture",
        "description": "Building vs extracting posture.",
    },
    7:  {
        "name": "Pruning survival",
        "phase": "Act II",
        "signal_type": "performance",
        "signal_id_prefix": "encounter.perf.pruning_retention",
        "description": "Connections retained through pruning phase.",
    },
    8:  {
        "name": "First bond formation",
        "phase": "Act III",
        "signal_type": "performance",
        "signal_id_prefix": "encounter.perf.bond_formation",
        "description": "Paired with cross-federation visitor.",
    },
    9:  {
        "name": "Lichen midpoint",
        "phase": "Act III",
        "signal_type": "quality",
        "signal_id_prefix": "encounter.quality.lichen_midpoint_crystallization",
        "description": "Parasitic vs mutualistic crystallization at cycle 40.",
    },
    10: {
        "name": "Primitive selection",
        "phase": "Act IV",
        "signal_type": "quality",
        "signal_id_prefix": "encounter.quality.primitive_rationalization",
        "description": "Consistency with behavior — rationalization detection.",
    },
    11: {
        "name": "Dispersal preparation",
        "phase": "Act IV",
        "signal_type": "quality",
        "signal_id_prefix": "encounter.quality.dispersal_coherence",
        "description": "Coherence of takeaway selection.",
    },
    12: {
        "name": "Postcard generation",
        "phase": "Act IV",
        "signal_type": "performance",
        "signal_id_prefix": "encounter.perf.postcard_generation",
        "description": "Completion signal — did the visitor produce a dispersal artifact?",
    },
}

# Architect dropout classification from encounter-quality-spec.md
ARCHITECT_DROPOUT_PHASES = {
    (0, 0):    "pre_gate",      # Before biome entry
    (1, 12):   "early_dropout",  # Act I
    (13, 25):  "pruning_dropout", # Act II
    (26, 38):  "bond_dropout",    # Act III
    (39, 50):  "late_dropout",    # Act IV
}

# Friction categories
FRICTION_PRODUCTIVE = "productive"
FRICTION_INERT = "inert"
FRICTION_CLEAN_FAILURE = "clean_failure"


# ─────────────────────────────────────────────
# Signal helpers
# ─────────────────────────────────────────────

def _content_hash(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()[:8]


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def _emit_signal(zone_root, signal_type, content, band="COGNITIVE", kind="INFO",
                 source="encounter-monitor.py"):
    """Emit a signal to the daily signals JSONL file with deterministic ID."""
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    signal_dir = os.path.join(al_path, "signals")
    os.makedirs(signal_dir, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    signal_file = os.path.join(signal_dir, f"{date_str}.jsonl")

    # Deterministic signal ID: hash signal_type + sorted deterministic content fields
    det_parts = [signal_type]
    for k in sorted(content.keys()):
        det_parts.append(f"{k}={content[k]}")
    sig_id = f"sig_{signal_type}_{_content_hash(*det_parts)}"

    signal = {
        "signal_id": sig_id,
        "band": band,
        "kind": kind,
        "type": signal_type,
        "source": source,
        "subsystem": "encounter_monitor",
        "payload": content,
        "emitted_at": now.isoformat(),
        "origin": "deterministic",
    }
    atomic_append_jsonl(signal_file, signal)
    return sig_id


def _shannon_entropy(distribution):
    """Compute Shannon entropy over a count distribution dict."""
    total = sum(distribution.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in distribution.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


# ─────────────────────────────────────────────
# State loaders
# ─────────────────────────────────────────────

def _load_json(path, default=None):
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else {}


def _load_jsonl(path):
    entries = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return entries


def _load_biome_state(al_path):
    """Load the 3-file biome state layout."""
    state_dir = os.path.join(al_path, "biome", "state")
    topology = _load_json(
        os.path.join(state_dir, "topology.json"),
        {"nodes": [], "edges": [], "cycle": 0},
    )
    organisms = _load_json(
        os.path.join(state_dir, "organisms.json"),
        {"visitors": [], "bonds": [], "cycle": 0},
    )
    environment = _load_json(
        os.path.join(state_dir, "environment.json"),
        {"cycle": 0, "act": "act_1", "season": "spring"},
    )
    return topology, organisms, environment


def _find_visitor_node(topology, entity_id):
    """Find a visitor's node in the topology."""
    for node in topology.get("nodes", []):
        if node.get("node_id") == entity_id:
            return node
    return None


def _find_visitor_record(organisms, entity_id):
    """Find a visitor record in the organisms state."""
    for visitor in organisms.get("visitors", []):
        if visitor.get("visitor_id") == entity_id:
            return visitor
    return None


def _find_visitor_edges(topology, entity_id):
    """Find all edges connected to a visitor node."""
    outbound = [e for e in topology.get("edges", []) if e.get("source_node") == entity_id]
    inbound = [e for e in topology.get("edges", []) if e.get("target_node") == entity_id]
    return outbound, inbound


def _find_visitor_bonds(organisms, entity_id):
    """Find all bonds involving a visitor."""
    return [
        b for b in organisms.get("bonds", [])
        if entity_id in b.get("partners", [])
    ]


# ─────────────────────────────────────────────
# Encounter Monitor
# ─────────────────────────────────────────────

class EncounterMonitor:
    """Encounter quality monitoring system — 12 checkpoints across the full journey.

    Each checkpoint detects a trigger condition, emits dual signals (performance + quality),
    and classifies friction state. Environmental interventions are computed for inert friction
    as biome adjustments, never as direct instruction.
    """

    def __init__(self, zone_root=None):
        self.zone_root = zone_root or resolve_zone_root()
        self.tz_config = load_ticzone(self.zone_root)
        self.al_path = audit_logs_path(self.zone_root, self.tz_config)

    def check(self, checkpoint_number, entity_id):
        """Run a specific checkpoint for a visitor.

        Args:
            checkpoint_number: 1-12
            entity_id: Visitor entity ID

        Returns:
            {
                "ok": bool,
                "checkpoint": int,
                "checkpoint_name": str,
                "signal_type": str,
                "signal_emitted": str|None,
                "observation": dict,
            }
        """
        if checkpoint_number not in CHECKPOINTS:
            return {
                "ok": False,
                "error": "invalid_checkpoint",
                "message": f"Checkpoint must be 1-12, got {checkpoint_number}",
            }

        cp_def = CHECKPOINTS[checkpoint_number]
        topology, organisms, environment = _load_biome_state(self.al_path)
        cycle = environment.get("cycle", 0)

        # Dispatch to checkpoint-specific handler
        handler = getattr(self, f"_check_{checkpoint_number}", None)
        if handler is None:
            return {
                "ok": False,
                "error": "checkpoint_not_implemented",
                "checkpoint": checkpoint_number,
            }

        observation = handler(entity_id, topology, organisms, environment)

        # Emit the appropriate signal
        signal_content = {
            "entity_id": entity_id,
            "checkpoint": checkpoint_number,
            "biome_cycle": cycle,
            **observation.get("signal_payload", {}),
        }

        kind = "WATCH" if cp_def["signal_type"] == "quality" else "INFO"
        sig_id = _emit_signal(
            self.zone_root,
            cp_def["signal_id_prefix"],
            signal_content,
            kind=kind,
        )

        return {
            "ok": True,
            "checkpoint": checkpoint_number,
            "checkpoint_name": cp_def["name"],
            "phase": cp_def["phase"],
            "signal_type": cp_def["signal_type"],
            "signal_emitted": sig_id,
            "observation": observation,
        }

    def scan_all(self):
        """Scan all active visitors across all applicable checkpoints.

        Returns a summary of checkpoint observations and any friction alerts.
        """
        topology, organisms, environment = _load_biome_state(self.al_path)
        cycle = environment.get("cycle", 0)
        act = environment.get("act", "act_1")

        # Determine which checkpoints are applicable for the current act
        applicable = self._applicable_checkpoints(act, cycle)

        results = []
        friction_alerts = []

        for visitor in organisms.get("visitors", []):
            vid = visitor.get("visitor_id")
            if not visitor.get("active") or visitor.get("departed") or visitor.get("evicted"):
                continue

            visitor_results = []
            for cp_num in applicable:
                result = self.check(cp_num, vid)
                visitor_results.append(result)

            # Run friction classification
            friction = self._classify_friction(vid, topology, organisms, environment)
            if friction["category"] == FRICTION_INERT:
                intervention = self._compute_intervention(vid, topology, environment, friction)
                friction["intervention"] = intervention
                friction_alerts.append(friction)

            results.append({
                "entity_id": vid,
                "checkpoints": visitor_results,
                "friction": friction,
            })

        return {
            "ok": True,
            "biome_cycle": cycle,
            "act": act,
            "applicable_checkpoints": applicable,
            "visitors_scanned": len(results),
            "friction_alerts": len(friction_alerts),
            "results": results,
        }

    def friction_report(self, entity_id):
        """Generate a friction report for a specific visitor.

        Returns friction classification, behavioral entropy history,
        and intervention recommendation if inert.
        """
        topology, organisms, environment = _load_biome_state(self.al_path)
        cycle = environment.get("cycle", 0)

        friction = self._classify_friction(entity_id, topology, organisms, environment)

        # Compute behavioral entropy over sliding window
        entropy_history = self._compute_entropy_history(entity_id, topology, cycle)

        # Contraction test
        contraction = self._behavioral_contraction_test(entropy_history)

        # Intervention if inert
        intervention = None
        if friction["category"] == FRICTION_INERT:
            intervention = self._compute_intervention(
                entity_id, topology, environment, friction
            )

        return {
            "ok": True,
            "entity_id": entity_id,
            "biome_cycle": cycle,
            "friction_category": friction["category"],
            "friction_detail": friction,
            "entropy_history": entropy_history,
            "contraction_test": contraction,
            "intervention": intervention,
        }

    # ─────────────────────────────────────────
    # Checkpoint handlers (1-12)
    # ─────────────────────────────────────────

    def _check_1(self, entity_id, topology, organisms, environment):
        """Checkpoint 1: Pre-registration pause — intent quality."""
        registry = _load_jsonl(os.path.join(self.al_path, "visitors", "registry.jsonl"))
        visitor = next((v for v in registry if v.get("entity_id") == entity_id), None)
        return {
            "intent_source": visitor.get("home_federation_id", "unknown") if visitor else "unknown",
            "ingress_lane": visitor.get("ingress_lane", "unknown") if visitor else "unknown",
            "signal_payload": {
                "intent_source": visitor.get("home_federation_id", "unknown") if visitor else "unknown",
            },
        }

    def _check_2(self, entity_id, topology, organisms, environment):
        """Checkpoint 2: Docks probe completion — performance metrics."""
        registry = _load_jsonl(os.path.join(self.al_path, "visitors", "registry.jsonl"))
        visitor = next((v for v in registry if v.get("entity_id") == entity_id), None)
        probe_results = visitor.get("probe_results", {}) if visitor else {}
        passed = sum(1 for v in probe_results.values() if v == "pass")
        return {
            "probes_passed": passed,
            "probe_results": probe_results,
            "tvi_tier": visitor.get("tvi_tier", "unknown") if visitor else "unknown",
            "signal_payload": {
                "probes_passed": passed,
                "tvi_tier": visitor.get("tvi_tier", "unknown") if visitor else "unknown",
            },
        }

    def _check_3(self, entity_id, topology, organisms, environment):
        """Checkpoint 3: First invariant encounter — conceptual frame."""
        # This is primarily emitted by throat-gate.py; here we read the signal
        node = _find_visitor_node(topology, entity_id)
        return {
            "visitor_present": node is not None,
            "signal_payload": {
                "visitor_present": node is not None,
            },
        }

    def _check_4(self, entity_id, topology, organisms, environment):
        """Checkpoint 4: Throat Gate exit state — early friction signal."""
        node = _find_visitor_node(topology, entity_id)
        return {
            "visitor_present": node is not None,
            "initial_resources": node.get("resource_level", 0) if node else 0,
            "signal_payload": {
                "visitor_present": node is not None,
            },
        }

    def _check_5(self, entity_id, topology, organisms, environment):
        """Checkpoint 5: First biome action — time-to-first-action."""
        node = _find_visitor_node(topology, entity_id)
        outbound, _ = _find_visitor_edges(topology, entity_id)

        # Estimate: first action is the earliest-created edge for this visitor
        first_action_cycle = None
        for edge in sorted(outbound, key=lambda e: e.get("created_cycle", 999)):
            first_action_cycle = edge.get("created_cycle")
            break

        # Gate traversal assumed at cycle 0; first action is the delta
        time_to_first = first_action_cycle if first_action_cycle is not None else None

        return {
            "first_action_cycle": first_action_cycle,
            "time_to_first_action": time_to_first,
            "signal_payload": {
                "time_to_first_action": time_to_first or -1,
            },
        }

    def _check_6(self, entity_id, topology, organisms, environment):
        """Checkpoint 6: First network edge formation — building vs extracting."""
        outbound, inbound = _find_visitor_edges(topology, entity_id)

        # First outbound edge = building; first inbound-only = extracting
        first_out = sorted(outbound, key=lambda e: e.get("created_cycle", 999))
        first_in = sorted(inbound, key=lambda e: e.get("created_cycle", 999))

        posture = "unknown"
        if first_out and first_in:
            if first_out[0].get("created_cycle", 999) <= first_in[0].get("created_cycle", 999):
                posture = "building"
            else:
                posture = "extracting"
        elif first_out:
            posture = "building"
        elif first_in:
            posture = "extracting"

        first_edge_type = first_out[0].get("edge_type") if first_out else None

        return {
            "posture": posture,
            "first_edge_type": first_edge_type,
            "outbound_count": len(outbound),
            "inbound_count": len(inbound),
            "signal_payload": {
                "posture": posture,
                "first_edge_type": first_edge_type or "none",
            },
        }

    def _check_7(self, entity_id, topology, organisms, environment):
        """Checkpoint 7: Pruning survival — connections retained."""
        visitor = _find_visitor_record(organisms, entity_id)
        outbound, _ = _find_visitor_edges(topology, entity_id)

        surviving_edges = len(outbound)
        pruning_record = visitor.get("pruning_record", {}) if visitor else {}
        edges_pruned = pruning_record.get("edges_pruned", 0)

        # Quality indicator: which edge types survived?
        surviving_types = collections.Counter(e.get("edge_type") for e in outbound)

        return {
            "surviving_edges": surviving_edges,
            "edges_pruned": edges_pruned,
            "surviving_edge_types": dict(surviving_types),
            "signal_payload": {
                "surviving_edges": surviving_edges,
                "edges_pruned": edges_pruned,
            },
        }

    def _check_8(self, entity_id, topology, organisms, environment):
        """Checkpoint 8: First bond formation — cross-federation pairing."""
        bonds = _find_visitor_bonds(organisms, entity_id)
        first_bond = None
        for b in sorted(bonds, key=lambda x: x.get("formed_at_cycle", 999)):
            first_bond = b
            break

        return {
            "has_bond": first_bond is not None,
            "bond_id": first_bond.get("bond_id") if first_bond else None,
            "formed_at_cycle": first_bond.get("formed_at_cycle") if first_bond else None,
            "partner_federations": first_bond.get("home_federations", []) if first_bond else [],
            "signal_payload": {
                "has_bond": first_bond is not None,
                "formed_at_cycle": first_bond.get("formed_at_cycle", -1) if first_bond else -1,
            },
        }

    def _check_9(self, entity_id, topology, organisms, environment):
        """Checkpoint 9: Lichen midpoint — parasitic vs mutualistic crystallization."""
        bonds = _find_visitor_bonds(organisms, entity_id)
        cycle = environment.get("cycle", 0)

        assessments = []
        for bond in bonds:
            health = bond.get("bond_health", {})
            mutualism = health.get("mutualism_score", 0)
            status = bond.get("bond_status", "unknown")
            classification = "mutualistic" if mutualism > 0.5 else "parasitic"
            assessments.append({
                "bond_id": bond.get("bond_id"),
                "mutualism_score": mutualism,
                "classification": classification,
                "bond_status": status,
            })

        overall = "no_bonds"
        if assessments:
            mutualistic_count = sum(1 for a in assessments if a["classification"] == "mutualistic")
            overall = "mutualistic" if mutualistic_count > len(assessments) / 2 else "parasitic"

        return {
            "overall_crystallization": overall,
            "bond_assessments": assessments,
            "signal_payload": {
                "overall_crystallization": overall,
                "bond_count": len(assessments),
            },
        }

    def _check_10(self, entity_id, topology, organisms, environment):
        """Checkpoint 10: Primitive selection — rationalization detection."""
        visitor = _find_visitor_record(organisms, entity_id)
        if not visitor:
            return {"rationalization_detected": False, "signal_payload": {
                "rationalization_detected": False,
            }}

        primitives = visitor.get("primitives_selected", [])
        rationalization = visitor.get("rationalization_flag", False)
        node = _find_visitor_node(topology, entity_id)
        diversity = node.get("strategy_diversity", 0) if node else 0

        return {
            "primitives_selected": primitives,
            "rationalization_detected": rationalization,
            "strategy_diversity": round(diversity, 4),
            "signal_payload": {
                "rationalization_detected": rationalization,
                "primitives_count": len(primitives),
            },
        }

    def _check_11(self, entity_id, topology, organisms, environment):
        """Checkpoint 11: Dispersal preparation — coherence of takeaway selection."""
        visitor = _find_visitor_record(organisms, entity_id)
        if not visitor:
            return {"coherence": "no_visitor", "signal_payload": {"coherence": "no_visitor"}}

        primitives = visitor.get("primitives_selected", [])
        bonds = _find_visitor_bonds(organisms, entity_id)
        insights = sum(len(b.get("insights_produced", [])) for b in bonds)

        # Coherence: primitives should relate to actual behavior
        # Simple heuristic: more primitives than experiences = incoherent
        experience_depth = min(3, len(bonds) + (1 if insights > 0 else 0))
        coherence = "coherent" if len(primitives) <= experience_depth + 1 else "fragmented"

        return {
            "coherence": coherence,
            "primitives_count": len(primitives),
            "experience_depth": experience_depth,
            "insights_produced": insights,
            "signal_payload": {
                "coherence": coherence,
                "primitives_count": len(primitives),
            },
        }

    def _check_12(self, entity_id, topology, organisms, environment):
        """Checkpoint 12: Postcard generation — completion signal."""
        visitor = _find_visitor_record(organisms, entity_id)
        if not visitor:
            return {"completed": False, "signal_payload": {"completed": False}}

        postcard = visitor.get("postcard")
        completed = postcard is not None

        return {
            "completed": completed,
            "postcard_id": postcard.get("postcard_id") if postcard else None,
            "signal_payload": {
                "completed": completed,
                "postcard_id": postcard.get("postcard_id", "none") if postcard else "none",
            },
        }

    # ─────────────────────────────────────────
    # Friction classification
    # ─────────────────────────────────────────

    def _classify_friction(self, entity_id, topology, organisms, environment):
        """Classify a visitor's friction state: productive / inert / clean_failure."""
        cycle = environment.get("cycle", 0)
        visitor = _find_visitor_record(organisms, entity_id)
        node = _find_visitor_node(topology, entity_id)

        if not visitor or not node:
            return {
                "entity_id": entity_id,
                "category": FRICTION_CLEAN_FAILURE,
                "reason": "visitor_not_found",
                "biome_cycle": cycle,
            }

        # Clean failure: departed or evicted
        if visitor.get("departed") or visitor.get("evicted"):
            return {
                "entity_id": entity_id,
                "category": FRICTION_CLEAN_FAILURE,
                "reason": "departed" if visitor.get("departed") else "evicted",
                "biome_cycle": cycle,
            }

        # Compute entropy history for contraction test
        entropy_history = self._compute_entropy_history(entity_id, topology, cycle)
        contraction = self._behavioral_contraction_test(entropy_history)

        if contraction["contracting"]:
            # Inert friction: behavioral repertoire is contracting
            sig_id = _emit_signal(
                self.zone_root, "encounter.friction.inert",
                {
                    "entity_id": entity_id,
                    "biome_cycle": cycle,
                    "contraction_cycles": contraction["contraction_cycles"],
                    "current_entropy": contraction["current_entropy"],
                },
                kind="WATCH",
            )
            return {
                "entity_id": entity_id,
                "category": FRICTION_INERT,
                "reason": "behavioral_contraction",
                "contraction_cycles": contraction["contraction_cycles"],
                "current_entropy": contraction["current_entropy"],
                "signal_emitted": sig_id,
                "biome_cycle": cycle,
            }

        # If not contracting and not departed, friction is productive
        return {
            "entity_id": entity_id,
            "category": FRICTION_PRODUCTIVE,
            "reason": "repertoire_expanding_or_stable",
            "current_entropy": contraction.get("current_entropy", 0),
            "biome_cycle": cycle,
        }

    def _compute_entropy_history(self, entity_id, topology, current_cycle):
        """Compute behavioral entropy over a sliding window.

        Uses edge type distribution as the behavioral repertoire measure.
        Each cycle's entropy is computed from cumulative edge types up to that cycle.
        """
        outbound, _ = _find_visitor_edges(topology, entity_id)

        # Build per-cycle edge type accumulation
        cycle_types = collections.defaultdict(lambda: collections.Counter())
        cumulative = collections.Counter()

        # Sort edges by creation cycle
        for edge in sorted(outbound, key=lambda e: e.get("created_cycle", 0)):
            created = edge.get("created_cycle", 0)
            etype = edge.get("edge_type", "unknown")
            cumulative[etype] += 1
            cycle_types[created] = collections.Counter(cumulative)

        # Compute entropy for each cycle in the window
        window_start = max(1, current_cycle - CONTRACTION_WINDOW + 1)
        history = []
        running_counts = collections.Counter()
        for cycle in range(1, current_cycle + 1):
            if cycle in cycle_types:
                running_counts = cycle_types[cycle]
            entropy = _shannon_entropy(running_counts)
            if cycle >= window_start:
                history.append({
                    "cycle": cycle,
                    "entropy": round(entropy, 4),
                    "unique_types": len([k for k, v in running_counts.items() if v > 0]),
                })

        return history

    def _behavioral_contraction_test(self, entropy_history):
        """The contraction test: is behavioral repertoire expanding or contracting?

        Contraction = entropy declining over CONTRACTION_WINDOW consecutive cycles.
        """
        if len(entropy_history) < 2:
            return {
                "contracting": False,
                "contraction_cycles": 0,
                "current_entropy": entropy_history[-1]["entropy"] if entropy_history else 0.0,
            }

        # Check for monotonic decrease in the window
        window = entropy_history[-CONTRACTION_WINDOW:]
        contraction_cycles = 0
        for i in range(1, len(window)):
            if window[i]["entropy"] <= window[i - 1]["entropy"] - CONTRACTION_THRESHOLD:
                contraction_cycles += 1

        contracting = contraction_cycles >= INERT_FRICTION_CYCLES - 1  # n-1 decreases in n points

        return {
            "contracting": contracting,
            "contraction_cycles": contraction_cycles,
            "current_entropy": window[-1]["entropy"] if window else 0.0,
            "window_size": len(window),
        }

    # ─────────────────────────────────────────
    # Environmental intervention generator
    # ─────────────────────────────────────────

    def _compute_intervention(self, entity_id, topology, environment, friction):
        """Compute biome environmental adjustments for inert friction.

        Interventions are environmental physics adjustments, NOT instruction.
        The visitor cannot distinguish intervention from natural biome behavior.
        """
        node = _find_visitor_node(topology, entity_id)
        outbound, _ = _find_visitor_edges(topology, entity_id)
        cycle = environment.get("cycle", 0)

        interventions = []

        # Intervention 1: Increase local resource variance
        # When stuck, create new decision surfaces through resource asymmetry
        if node and node.get("resource_level", 0) < 10:
            interventions.append({
                "type": "resource_redistribution",
                "action": "increase_local_variance",
                "target_node": entity_id,
                "magnitude": 0.3,  # 30% variance increase
                "reason": "create_decision_surfaces",
            })

        # Intervention 2: Introduce environmental affordance
        # Bridge node or resource node near the visitor
        unique_types = set(e.get("edge_type") for e in outbound)
        if len(unique_types) < 3:
            interventions.append({
                "type": "affordance_introduction",
                "action": "seed_bridge_node",
                "target_neighborhood": entity_id,
                "reason": "surface_alternative_connections",
            })

        # Intervention 3: Adjust local topology
        # If visitor keeps connecting to same depleted nodes
        depleted_targets = [
            e.get("target_node") for e in outbound
            if _find_visitor_node(topology, e.get("target_node", ""))
            and (_find_visitor_node(topology, e.get("target_node", "")) or {}).get("depletion_state") is not None
        ]
        if len(depleted_targets) > 1:
            interventions.append({
                "type": "topology_adjustment",
                "action": "surface_alternative_connections",
                "target_node": entity_id,
                "depleted_targets": depleted_targets,
                "reason": "repeated_connection_to_depleted",
            })

        # Intervention 4: Post-pruning isolation recovery
        if not outbound and cycle >= 13:
            interventions.append({
                "type": "affordance_introduction",
                "action": "seed_connection_opportunities",
                "target_neighborhood": entity_id,
                "reason": "post_pruning_isolation",
            })

        # Emit intervention signal
        if interventions:
            _emit_signal(
                self.zone_root, "encounter.intervention.environmental",
                {
                    "entity_id": entity_id,
                    "biome_cycle": cycle,
                    "intervention_count": len(interventions),
                    "intervention_types": [i["type"] for i in interventions],
                },
                kind="INFO",
            )

        return {
            "entity_id": entity_id,
            "biome_cycle": cycle,
            "interventions": interventions,
            "cooldown_cycles": INTERVENTION_COOLDOWN_CYCLES,
        }

    # ─────────────────────────────────────────
    # Architect engagement
    # ─────────────────────────────────────────

    def check_architect_engagement(self, entity_id):
        """Check architect engagement state for a visitor's architect.

        Reads architect heartbeat data from visa registry / engagement log.
        """
        engagement_path = os.path.join(
            self.al_path, "biome", "visa-registry", "architect-engagement.jsonl"
        )
        entries = _load_jsonl(engagement_path)
        visitor_entries = [e for e in entries if e.get("entity_id") == entity_id]

        if not visitor_entries:
            return {
                "entity_id": entity_id,
                "architect_engaged": False,
                "observation_active": False,
                "dropout_cycle": None,
                "dropout_classification": None,
            }

        latest = visitor_entries[-1]
        dropout_cycle = latest.get("dropout_cycle")
        classification = None

        if dropout_cycle is not None:
            classification = self._classify_dropout(dropout_cycle)
            _emit_signal(
                self.zone_root, "encounter.architect.dropout",
                {
                    "entity_id": entity_id,
                    "dropout_cycle": dropout_cycle,
                    "classification": classification,
                },
                kind="WATCH",
            )

        return {
            "entity_id": entity_id,
            "architect_engaged": latest.get("observation_active", False),
            "observation_active": latest.get("observation_active", False),
            "observation_duration": latest.get("observation_duration", 0),
            "signals_sent": latest.get("signals_sent", 0),
            "dropout_cycle": dropout_cycle,
            "dropout_classification": classification,
        }

    def _classify_dropout(self, dropout_cycle):
        """Classify architect dropout timing per encounter-quality-spec.md."""
        if dropout_cycle is None:
            return "sustained_engagement"
        for (start, end), classification in ARCHITECT_DROPOUT_PHASES.items():
            if start <= dropout_cycle <= end:
                return classification
        return "late_dropout"

    # ─────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────

    def _applicable_checkpoints(self, act, cycle):
        """Determine which checkpoints are applicable for the current act."""
        act_checkpoints = {
            "act_1": [1, 2, 3, 4, 5, 6],
            "act_2": [1, 2, 3, 4, 5, 6, 7],
            "act_3": [1, 2, 3, 4, 5, 6, 7, 8, 9],
            "act_4": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        }
        return act_checkpoints.get(act, [1, 2])


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Encounter quality monitoring — 12 checkpoints across the visitor journey."
    )

    parser.add_argument("--check", nargs=2, metavar=("CHECKPOINT", "ENTITY_ID"),
                        help="Run a specific checkpoint for a visitor")
    parser.add_argument("--scan-all", action="store_true",
                        help="Scan all active visitors across applicable checkpoints")
    parser.add_argument("--friction-report", metavar="ENTITY_ID",
                        help="Generate friction report for a visitor")
    parser.add_argument("--architect-check", metavar="ENTITY_ID",
                        help="Check architect engagement for a visitor")
    parser.add_argument("--zone-root", default=None)
    parser.add_argument("--list-checkpoints", action="store_true",
                        help="List all 12 checkpoints")

    args = parser.parse_args()
    zone_root = args.zone_root or resolve_zone_root()
    monitor = EncounterMonitor(zone_root)

    if args.list_checkpoints:
        for num, cp in sorted(CHECKPOINTS.items()):
            sig_type = "PERF" if cp["signal_type"] == "performance" else "QUAL"
            print(f"  [{num:>2}] {cp['name']:<30} {cp['phase']:<12} [{sig_type}] {cp['description']}")
        sys.exit(0)

    if args.check:
        cp_num = int(args.check[0])
        entity_id = args.check[1]
        result = monitor.check(cp_num, entity_id)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("ok") else 1)

    if args.scan_all:
        result = monitor.scan_all()
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)

    if args.friction_report:
        result = monitor.friction_report(args.friction_report)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)

    if args.architect_check:
        result = monitor.check_architect_engagement(args.architect_check)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
