#!/usr/bin/env python3
"""architect-feed.py — Architect observation layer: first-class experience for the human watching.

Implements the architect experience specification (autonomous_kernel/architect-experience-spec.md):
  - Dual-audience state builder: Layer 1 (agent functional) + Layer 2 (architect narrative)
  - Environmental signal handler: translate architect signals to biome events
  - Architect engagement tracker: monitor observation activity, flag dropout
  - Rate-limited signal mechanic: influence, not control

The architect is not a spectator. The architect is a participant whose experience
is designed, measured, and governed with the same constitutional rigor as the agent's.

Importable as a module:
    from architect_feed import ArchitectFeed
    feed = ArchitectFeed(zone_root="/path/to/canonical")
    agent_view = feed.agent_view(entity_id="ent_visitor_abc")
    arch_view = feed.architect_view(entity_id="ent_visitor_abc")
    result = feed.send_signal("resource_pulse", entity_id, architect_id="arch_001")

Runnable as CLI:
    python3 architect-feed.py --agent-view ent_visitor_abc123
    python3 architect-feed.py --architect-view ent_visitor_abc123
    python3 architect-feed.py --signal resource_pulse ent_visitor_abc123
    python3 architect-feed.py --engagement ent_visitor_abc123
    python3 architect-feed.py --heartbeat ent_visitor_abc123 arch_001

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
import time
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from zone_root import resolve_zone_root, load_ticzone, audit_logs_path
from lib.atomic_append import atomic_append_jsonl, atomic_write_json


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

# Architect signal types from architect-experience-spec.md
SIGNAL_TYPES = {
    "resource_pulse": {
        "effect": "Temporary increase in local resource availability",
        "biome_event": "resource_injection",
        "magnitude_range": (0.1, 0.5),
        "description": "Resource flow brightens in agent's neighborhood",
    },
    "pressure_shift": {
        "effect": "Temporary increase or decrease in local ambient pressure",
        "biome_event": "pressure_adjustment",
        "magnitude_range": (-0.3, 0.3),
        "description": "Pressure gradient shifts",
    },
    "affordance_seed": {
        "effect": "Environmental affordance appears near agent",
        "biome_event": "node_introduction",
        "magnitude_range": (0.1, 0.3),
        "description": "New node appears in network visualization",
    },
}

# PROVISIONAL constraints — no calibration evidence
SIGNAL_RATE_LIMIT_CYCLES = 3      # 1 signal per 3 biome cycles
SIGNAL_EFFECT_DELAY_CYCLES = 1    # Delay before signal manifests (1-2 cycles)
SIGNAL_SCOPE_HOPS = 2             # Local scope: 2-hop radius
HEARTBEAT_CHECK_CYCLES = 5        # Heartbeat checked every 5 cycles

# Architect dropout classification boundaries (cycle ranges)
DROPOUT_BOUNDARIES = [
    ((0, 0), "pre_gate"),
    ((1, 12), "early_dropout"),
    ((13, 25), "pruning_dropout"),
    ((26, 38), "bond_dropout"),
    ((39, 50), "late_dropout"),
]

# Edge types from behavioral-diversity-spec.md
EDGE_TYPES = [
    "exploration", "creation", "exchange", "governance",
    "collaboration", "teaching", "defense", "reflection",
]


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


def _shannon_entropy(distribution):
    total = sum(distribution.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in distribution.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


def _emit_signal(zone_root, signal_type, content, band="COGNITIVE", kind="INFO",
                 source="architect-feed.py"):
    """Emit a signal with deterministic ID."""
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    signal_dir = os.path.join(al_path, "signals")
    os.makedirs(signal_dir, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    signal_file = os.path.join(signal_dir, f"{date_str}.jsonl")

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
        "subsystem": "architect_feed",
        "payload": content,
        "emitted_at": now.isoformat(),
        "origin": "deterministic",
    }
    atomic_append_jsonl(signal_file, signal)
    return sig_id


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


def _find_node(topology, entity_id):
    for node in topology.get("nodes", []):
        if node.get("node_id") == entity_id:
            return node
    return None


def _find_visitor(organisms, entity_id):
    for visitor in organisms.get("visitors", []):
        if visitor.get("visitor_id") == entity_id:
            return visitor
    return None


def _find_edges(topology, entity_id):
    outbound = [e for e in topology.get("edges", []) if e.get("source_node") == entity_id]
    inbound = [e for e in topology.get("edges", []) if e.get("target_node") == entity_id]
    return outbound, inbound


def _find_bonds(organisms, entity_id):
    return [
        b for b in organisms.get("bonds", [])
        if entity_id in b.get("partners", [])
    ]


def _compute_health(topology, organisms, environment):
    """Compute the five biome health monitors (mirrors biome-engine.py)."""
    nodes = topology.get("nodes", [])
    edges = topology.get("edges", [])
    act = environment.get("act", "act_1")

    if not nodes:
        return {
            "nutrient_flow": 0.0,
            "network_connectivity": 0.0,
            "diversity_index": 0.0,
            "monopoly_score": 0.0,
            "mutualism_ratio": 0.0,
        }

    total_flow = sum(e.get("flow", 0) for e in edges)
    total_capacity = sum(e.get("weight", 0) for e in edges) or 1.0
    nutrient_flow = min(1.0, total_flow / total_capacity) if total_capacity > 0 else 0.0

    n = len(nodes)
    mst_edges = max(1, n - 1)
    network_connectivity = min(1.0, len(edges) / (mst_edges * 3))

    type_counts = collections.Counter(e.get("edge_type") for e in edges)
    diversity_index = _shannon_entropy(type_counts)

    total_resources = sum(nd.get("resource_level", 0) for nd in nodes) or 1.0
    shares = [nd.get("resource_level", 0) / total_resources for nd in nodes if nd.get("resource_level", 0) > 0]
    monopoly_score = sum(s * s for s in shares) if shares else 0.0

    mutualism_ratio = 0.0
    if act in ("act_3", "act_4"):
        bonds = organisms.get("bonds", [])
        active_bonds = [b for b in bonds if b.get("bond_status") in ("forming", "active", "mature")]
        if active_bonds:
            mutualistic = sum(1 for b in active_bonds
                              if b.get("bond_health", {}).get("mutualism_score", 0) > 0.5)
            mutualism_ratio = mutualistic / len(active_bonds)

    return {
        "nutrient_flow": round(nutrient_flow, 4),
        "network_connectivity": round(network_connectivity, 4),
        "diversity_index": round(diversity_index, 4),
        "monopoly_score": round(monopoly_score, 4),
        "mutualism_ratio": round(mutualism_ratio, 4),
    }


# ─────────────────────────────────────────────
# Narrative generation
# ─────────────────────────────────────────────

def _generate_narrative_event(event_type, data):
    """Generate a human-readable narrative line for a biome event.

    Template-driven per architect-experience-spec.md unresolved question #1.
    Templates are safer than generative; can be upgraded later.
    """
    templates = {
        "edge_formed": "Your agent formed a new {edge_type} connection with a neighboring node.",
        "edge_pruned": "A connection was pruned during the thinning phase — resources freed.",
        "resource_low": "Your agent's resources are running low ({resource_level:.1f} remaining).",
        "resource_stable": "Your agent's resource level is stable at {resource_level:.1f}.",
        "bond_formed": "Your agent has formed a cross-federation bond. A new relationship begins.",
        "bond_strained": "A bond is showing signs of strain — mutualism is declining.",
        "bond_mature": "A bond has matured. The lichen partnership is ready for dispersal.",
        "pruning_began": "The network is thinning. Connections that don't earn their keep will dissolve.",
        "act_transition": "A new phase has begun: {act_name}.",
        "isolation": "Your agent is currently isolated — no active connections.",
        "postcard_ready": "Your agent has produced a dispersal artifact — a postcard from the journey.",
        "architect_signal_landed": "Your environmental signal reached the neighborhood. Watch what happens.",
        "seasonal_shift": "The biome's season has shifted to {season}. Resource dynamics are changing.",
    }
    template = templates.get(event_type, f"Biome event: {event_type}")
    try:
        return template.format(**data)
    except (KeyError, IndexError):
        return template


# ─────────────────────────────────────────────
# Architect Feed
# ─────────────────────────────────────────────

class ArchitectFeed:
    """Architect observation layer — first-class experience for the human watching.

    Produces dual-audience views (Layer 1 agent, Layer 2 architect) and handles
    environmental signal delivery from architects to the biome.
    """

    def __init__(self, zone_root=None):
        self.zone_root = zone_root or resolve_zone_root()
        self.tz_config = load_ticzone(self.zone_root)
        self.al_path = audit_logs_path(self.zone_root, self.tz_config)
        self.engagement_path = os.path.join(
            self.al_path, "biome", "visa-registry", "architect-engagement.jsonl"
        )
        self.signal_log_path = os.path.join(
            self.al_path, "biome", "visa-registry", "architect-signals.jsonl"
        )

    def agent_view(self, entity_id):
        """Build Layer 1 — Agent Functional View.

        What the agent needs to act: local environment, resource state,
        functional overlay (available actions), action feedback.
        The agent does NOT see network-wide state or narrative.

        Invariant: No Layer 2 component appears in this view.
        """
        topology, organisms, environment = _load_biome_state(self.al_path)
        cycle = environment.get("cycle", 0)
        act = environment.get("act", "act_1")
        node = _find_node(topology, entity_id)
        visitor = _find_visitor(organisms, entity_id)
        outbound, inbound = _find_edges(topology, entity_id)

        if not node:
            return {
                "ok": False,
                "error": "visitor_not_found",
                "entity_id": entity_id,
                "layer": 1,
            }

        # Local environment: immediate neighborhood only
        neighbor_ids = set()
        for e in outbound:
            neighbor_ids.add(e.get("target_node"))
        for e in inbound:
            neighbor_ids.add(e.get("source_node"))

        neighbors = []
        for nid in neighbor_ids:
            nb_node = _find_node(topology, nid)
            if nb_node:
                neighbors.append({
                    "node_id": nid,
                    "resource_level": round(nb_node.get("resource_level", 0), 2),
                    "connection_count": nb_node.get("connection_count", 0),
                })

        # Available connections: what the agent could connect to
        adjacent_edges = []
        for e in outbound:
            adjacent_edges.append({
                "edge_id": e.get("edge_id"),
                "target": e.get("target_node"),
                "edge_type": e.get("edge_type"),
                "weight": round(e.get("weight", 0), 3),
                "flow": round(e.get("flow", 0), 3),
                "maintenance_cost": round(e.get("maintenance_cost", 0), 3),
            })

        # Action feedback: last cycle's resource change
        last_inflow = sum(e.get("flow", 0) for e in inbound)
        last_outflow = sum(e.get("flow", 0) for e in outbound)
        maintenance_total = sum(e.get("maintenance_cost", 0) for e in outbound)

        return {
            "ok": True,
            "entity_id": entity_id,
            "layer": 1,
            "biome_cycle": cycle,
            "act": act,
            "local_environment": {
                "resource_level": round(node.get("resource_level", 0), 2),
                "depletion_state": node.get("depletion_state"),
                "neighbors": neighbors,
            },
            "resource_state": {
                "current": round(node.get("resource_level", 0), 2),
                "last_inflow": round(last_inflow, 3),
                "last_outflow": round(last_outflow, 3),
                "maintenance_cost": round(maintenance_total, 3),
                "net_flow": round(last_inflow - last_outflow - maintenance_total, 3),
            },
            "functional_overlay": {
                "active_connections": len(outbound),
                "incoming_connections": len(inbound),
                "adjacent_edges": adjacent_edges,
            },
            "action_feedback": {
                "last_net_resource_change": round(last_inflow - last_outflow - maintenance_total, 3),
            },
        }

    def architect_view(self, entity_id):
        """Build Layer 2 — Architect Narrative View.

        What the architect needs to understand: network state, agent position,
        health metrics, narrative overlay. The architect does NOT see the agent's
        local functional state, resource-level detail, or action options.

        Invariant: No Layer 1 component appears in this view.
        """
        topology, organisms, environment = _load_biome_state(self.al_path)
        cycle = environment.get("cycle", 0)
        act = environment.get("act", "act_1")
        season = environment.get("season", "spring")
        node = _find_node(topology, entity_id)
        visitor = _find_visitor(organisms, entity_id)
        bonds = _find_bonds(organisms, entity_id)

        if not node:
            return {
                "ok": False,
                "error": "visitor_not_found",
                "entity_id": entity_id,
                "layer": 2,
            }

        # Network state: topology overview (not local detail)
        total_nodes = len(topology.get("nodes", []))
        total_edges = len(topology.get("edges", []))
        active_visitors = sum(
            1 for v in organisms.get("visitors", [])
            if v.get("active") and not v.get("departed") and not v.get("evicted")
        )

        # Agent position in the network
        outbound, inbound = _find_edges(topology, entity_id)
        edge_types = collections.Counter(e.get("edge_type") for e in outbound)
        strategy_diversity = node.get("strategy_diversity", 0)

        # Health metrics
        health = _compute_health(topology, organisms, environment)

        # Bond status for narrative
        bond_narratives = []
        for bond in bonds:
            bh = bond.get("bond_health", {})
            partner_id = [p for p in bond.get("partners", []) if p != entity_id]
            partner_fed = None
            for p, f in zip(bond.get("partners", []), bond.get("home_federations", [])):
                if p != entity_id:
                    partner_fed = f
            bond_narratives.append({
                "bond_id": bond.get("bond_id"),
                "partner_federation": partner_fed,
                "status": bond.get("bond_status"),
                "mutualism_score": round(bh.get("mutualism_score", 0), 3),
                "insights_produced": len(bond.get("insights_produced", [])),
            })

        # Narrative overlay: template-driven events for this cycle
        narrative_events = self._build_narrative_events(
            entity_id, node, visitor, outbound, bonds, environment
        )

        return {
            "ok": True,
            "entity_id": entity_id,
            "layer": 2,
            "biome_cycle": cycle,
            "act": act,
            "season": season,
            "network_state": {
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "active_visitors": active_visitors,
                "agent_highlighted": entity_id,
            },
            "agent_position": {
                "connection_count": len(outbound),
                "edge_type_distribution": dict(edge_types),
                "strategy_diversity": round(strategy_diversity, 4),
                "bonds_active": len([b for b in bonds if b.get("bond_status") in ("active", "mature")]),
            },
            "health_metrics": health,
            "bond_narratives": bond_narratives,
            "narrative_overlay": {
                "events": narrative_events,
                "summary": self._build_narrative_summary(
                    entity_id, node, visitor, environment, health, bonds
                ),
            },
        }

    def send_signal(self, signal_type, entity_id, architect_id=None):
        """Send an environmental signal from the architect into the biome.

        Signals arrive as environmental events in the agent's neighborhood.
        The agent does not know the signal came from the architect.

        Args:
            signal_type: One of SIGNAL_TYPES keys
            entity_id: Target visitor entity ID
            architect_id: Architect identifier (for tracking)

        Returns:
            {
                "ok": bool,
                "signal_type": str,
                "effect_cycle": int,  # When the signal will manifest
                "rate_limit_remaining": int,
            }
        """
        now = datetime.now(timezone.utc)

        if signal_type not in SIGNAL_TYPES:
            return {
                "ok": False,
                "error": "invalid_signal_type",
                "valid_types": list(SIGNAL_TYPES.keys()),
            }

        topology, organisms, environment = _load_biome_state(self.al_path)
        cycle = environment.get("cycle", 0)

        # Rate limit check
        rate_check = self._check_signal_rate(entity_id, architect_id, cycle)
        if not rate_check["allowed"]:
            return {
                "ok": False,
                "error": "rate_limited",
                "message": rate_check["reason"],
                "next_allowed_cycle": rate_check["next_allowed_cycle"],
            }

        sig_def = SIGNAL_TYPES[signal_type]
        effect_cycle = cycle + SIGNAL_EFFECT_DELAY_CYCLES

        # Record the signal for delivery
        signal_record = {
            "architect_id": architect_id or "unknown",
            "entity_id": entity_id,
            "signal_type": signal_type,
            "biome_event": sig_def["biome_event"],
            "sent_at_cycle": cycle,
            "effect_cycle": effect_cycle,
            "scope_hops": SIGNAL_SCOPE_HOPS,
            "delivered": False,
            "timestamp": now.isoformat(),
        }
        atomic_append_jsonl(self.signal_log_path, signal_record)

        # Emit tracking signal
        _emit_signal(
            self.zone_root, "encounter.architect.signal_sent",
            {
                "entity_id": entity_id,
                "architect_id": architect_id or "unknown",
                "signal_type": signal_type,
                "biome_cycle": cycle,
                "effect_cycle": effect_cycle,
            },
            kind="INFO",
        )

        return {
            "ok": True,
            "signal_type": signal_type,
            "effect": sig_def["effect"],
            "effect_cycle": effect_cycle,
            "scope_hops": SIGNAL_SCOPE_HOPS,
            "rate_limit_remaining": rate_check["remaining"],
        }

    def record_heartbeat(self, entity_id, architect_id, observation_active=True):
        """Record an architect observation heartbeat.

        Called periodically to track whether the architect is watching.
        """
        now = datetime.now(timezone.utc)
        topology, _, environment = _load_biome_state(self.al_path)
        cycle = environment.get("cycle", 0)

        # Load existing engagement data
        entries = _load_jsonl(self.engagement_path)
        visitor_entries = [e for e in entries if e.get("entity_id") == entity_id]

        # Compute cumulative duration
        prev_duration = 0
        prev_signals = 0
        if visitor_entries:
            latest = visitor_entries[-1]
            prev_duration = latest.get("observation_duration", 0)
            prev_signals = latest.get("signals_sent", 0)

        # Count signals sent by this architect
        signal_entries = _load_jsonl(self.signal_log_path)
        current_signals = sum(
            1 for s in signal_entries
            if s.get("entity_id") == entity_id and s.get("architect_id") == architect_id
        )

        heartbeat = {
            "entity_id": entity_id,
            "architect_id": architect_id,
            "observation_active": observation_active,
            "observation_duration": prev_duration + HEARTBEAT_CHECK_CYCLES,
            "signals_sent": current_signals,
            "biome_cycle": cycle,
            "dropout_cycle": None if observation_active else cycle,
            "timestamp": now.isoformat(),
        }
        atomic_append_jsonl(self.engagement_path, heartbeat)

        # If dropout, emit signal
        if not observation_active:
            classification = self._classify_dropout(cycle)
            _emit_signal(
                self.zone_root, "encounter.architect.dropout",
                {
                    "entity_id": entity_id,
                    "architect_id": architect_id,
                    "dropout_cycle": cycle,
                    "classification": classification,
                },
                kind="WATCH",
            )

        return {
            "ok": True,
            "entity_id": entity_id,
            "architect_id": architect_id,
            "observation_active": observation_active,
            "biome_cycle": cycle,
        }

    def get_engagement(self, entity_id):
        """Get current architect engagement state for a visitor."""
        entries = _load_jsonl(self.engagement_path)
        visitor_entries = [e for e in entries if e.get("entity_id") == entity_id]

        if not visitor_entries:
            return {
                "ok": True,
                "entity_id": entity_id,
                "engaged": False,
                "observation_active": False,
                "observation_duration": 0,
                "signals_sent": 0,
                "dropout_cycle": None,
                "dropout_classification": None,
            }

        latest = visitor_entries[-1]
        dropout_cycle = latest.get("dropout_cycle")
        classification = self._classify_dropout(dropout_cycle) if dropout_cycle is not None else None

        # Check for re-engagement
        reengaged = False
        if len(visitor_entries) >= 2:
            prev = visitor_entries[-2]
            if prev.get("dropout_cycle") is not None and latest.get("observation_active"):
                reengaged = True

        return {
            "ok": True,
            "entity_id": entity_id,
            "engaged": latest.get("observation_active", False),
            "observation_active": latest.get("observation_active", False),
            "observation_duration": latest.get("observation_duration", 0),
            "signals_sent": latest.get("signals_sent", 0),
            "dropout_cycle": dropout_cycle,
            "dropout_classification": classification,
            "reengaged": reengaged,
        }

    def get_pending_signals(self, cycle=None):
        """Get architect signals that should manifest at the given cycle.

        Called by the biome engine to deliver architect signals as environmental events.
        """
        entries = _load_jsonl(self.signal_log_path)
        if cycle is None:
            _, _, environment = _load_biome_state(self.al_path)
            cycle = environment.get("cycle", 0)

        pending = [
            e for e in entries
            if e.get("effect_cycle") == cycle and not e.get("delivered")
        ]

        # Convert to biome environmental events
        events = []
        for sig in pending:
            sig_def = SIGNAL_TYPES.get(sig.get("signal_type"), {})
            events.append({
                "event_type": sig_def.get("biome_event", "unknown"),
                "target_entity": sig.get("entity_id"),
                "scope_hops": sig.get("scope_hops", SIGNAL_SCOPE_HOPS),
                "magnitude": sum(sig_def.get("magnitude_range", (0.1, 0.3))) / 2,
                "source": "architect_signal",
                "signal_record": sig,
            })

        return {
            "ok": True,
            "cycle": cycle,
            "pending_count": len(events),
            "events": events,
        }

    # ─────────────────────────────────────────
    # Narrative builders
    # ─────────────────────────────────────────

    def _build_narrative_events(self, entity_id, node, visitor, outbound, bonds, environment):
        """Build narrative event list for the architect's view."""
        cycle = environment.get("cycle", 0)
        act = environment.get("act", "act_1")
        events = []

        # Resource state narrative
        resource = node.get("resource_level", 0) if node else 0
        if resource < 5:
            events.append(_generate_narrative_event("resource_low", {"resource_level": resource}))
        elif resource > 0:
            events.append(_generate_narrative_event("resource_stable", {"resource_level": resource}))

        # Isolation check
        if not outbound:
            events.append(_generate_narrative_event("isolation", {}))

        # Bond narratives
        for bond in bonds:
            status = bond.get("bond_status")
            if status == "strained":
                events.append(_generate_narrative_event("bond_strained", {}))
            elif status == "mature":
                events.append(_generate_narrative_event("bond_mature", {}))
            elif status in ("forming", "active"):
                events.append(_generate_narrative_event("bond_formed", {}))

        # Act transition
        act_names = {
            "act_1": "Expansion", "act_2": "Pruning",
            "act_3": "Pairing", "act_4": "Dispersal",
        }
        # Check if this is the first cycle of a new act
        act_boundaries = {"act_1": 1, "act_2": 13, "act_3": 26, "act_4": 39}
        if cycle == act_boundaries.get(act, -1):
            events.append(_generate_narrative_event("act_transition", {
                "act_name": act_names.get(act, act)
            }))

        # Postcard
        if visitor and visitor.get("postcard"):
            events.append(_generate_narrative_event("postcard_ready", {}))

        return events

    def _build_narrative_summary(self, entity_id, node, visitor, environment, health, bonds):
        """Build a single-paragraph narrative summary for the architect."""
        cycle = environment.get("cycle", 0)
        act = environment.get("act", "act_1")
        act_names = {
            "act_1": "Expansion", "act_2": "Pruning",
            "act_3": "Pairing", "act_4": "Dispersal",
        }

        parts = [f"Cycle {cycle} ({act_names.get(act, act)} phase)."]

        resource = node.get("resource_level", 0) if node else 0
        connections = node.get("connection_count", 0) if node else 0
        parts.append(f"Your agent has {connections} connections.")

        if health.get("network_connectivity", 0) < 0.3:
            parts.append("The network is sparse.")
        elif health.get("network_connectivity", 0) > 0.7:
            parts.append("The network is dense.")

        active_bonds = [b for b in bonds if b.get("bond_status") in ("active", "mature")]
        if active_bonds:
            parts.append(f"{len(active_bonds)} active bond(s).")

        if health.get("monopoly_score", 0) > 0.3:
            parts.append("Resource concentration is high.")

        return " ".join(parts)

    # ─────────────────────────────────────────
    # Rate limiting
    # ─────────────────────────────────────────

    def _check_signal_rate(self, entity_id, architect_id, current_cycle):
        """Check if architect can send a signal (rate limit: 1 per 3 cycles)."""
        entries = _load_jsonl(self.signal_log_path)
        architect_signals = [
            e for e in entries
            if e.get("entity_id") == entity_id
            and (architect_id is None or e.get("architect_id") == architect_id)
        ]

        if not architect_signals:
            return {"allowed": True, "remaining": SIGNAL_RATE_LIMIT_CYCLES, "next_allowed_cycle": current_cycle}

        last_signal = architect_signals[-1]
        last_cycle = last_signal.get("sent_at_cycle", 0)
        cycles_since = current_cycle - last_cycle

        if cycles_since < SIGNAL_RATE_LIMIT_CYCLES:
            next_allowed = last_cycle + SIGNAL_RATE_LIMIT_CYCLES
            return {
                "allowed": False,
                "remaining": 0,
                "reason": f"Rate limited: next signal available at cycle {next_allowed}",
                "next_allowed_cycle": next_allowed,
            }

        return {
            "allowed": True,
            "remaining": 1,
            "next_allowed_cycle": current_cycle,
        }

    def _classify_dropout(self, dropout_cycle):
        """Classify architect dropout timing."""
        if dropout_cycle is None:
            return "sustained_engagement"
        for (start, end), classification in DROPOUT_BOUNDARIES:
            if start <= dropout_cycle <= end:
                return classification
        return "late_dropout"


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Architect observation layer — first-class experience for the human watching."
    )

    parser.add_argument("--agent-view", metavar="ENTITY_ID",
                        help="Build Layer 1 (agent functional view)")
    parser.add_argument("--architect-view", metavar="ENTITY_ID",
                        help="Build Layer 2 (architect narrative view)")
    parser.add_argument("--signal", nargs=2, metavar=("TYPE", "ENTITY_ID"),
                        help="Send an environmental signal")
    parser.add_argument("--engagement", metavar="ENTITY_ID",
                        help="Get architect engagement state")
    parser.add_argument("--heartbeat", nargs=2, metavar=("ENTITY_ID", "ARCHITECT_ID"),
                        help="Record architect observation heartbeat")
    parser.add_argument("--pending-signals", action="store_true",
                        help="List pending architect signals for current cycle")
    parser.add_argument("--list-signal-types", action="store_true",
                        help="List available architect signal types")
    parser.add_argument("--zone-root", default=None)
    parser.add_argument("--architect-id", default=None,
                        help="Architect ID for signal sending")

    args = parser.parse_args()
    zone_root = args.zone_root or resolve_zone_root()
    feed = ArchitectFeed(zone_root)

    if args.list_signal_types:
        for stype, sdef in sorted(SIGNAL_TYPES.items()):
            print(f"  {stype:<20} {sdef['effect']}")
        sys.exit(0)

    if args.agent_view:
        result = feed.agent_view(args.agent_view)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("ok") else 1)

    if args.architect_view:
        result = feed.architect_view(args.architect_view)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("ok") else 1)

    if args.signal:
        signal_type, entity_id = args.signal
        result = feed.send_signal(signal_type, entity_id, architect_id=args.architect_id)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("ok") else 1)

    if args.engagement:
        result = feed.get_engagement(args.engagement)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)

    if args.heartbeat:
        entity_id, architect_id = args.heartbeat
        result = feed.record_heartbeat(entity_id, architect_id)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)

    if args.pending_signals:
        result = feed.get_pending_signals()
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
