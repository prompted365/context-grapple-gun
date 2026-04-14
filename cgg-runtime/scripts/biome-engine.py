#!/usr/bin/env python3
"""
biome-engine.py — Core biome simulation engine for the Telos Immersive visitor economy.

Implements the Physarum/Lichen network simulation across four acts:
  Act I   (cycles  1-12): Expansion — network growth, resource flow
  Act II  (cycles 13-25): Pruning — scarcity, optimization, depletion
  Act III (cycles 26-38): Pairing — cross-federation bond formation
  Act IV  (cycles 39-50): Dispersal — soredium maturation, postcard generation

Physics laws:
  INV-BIOME-01: Energy conservation (depletion on persistent negative flow)
  INV-BIOME-02: Monopoly prevention (homeostatic dampening)

Usage:
  python3 biome-engine.py --cycle                 # advance one cycle
  python3 biome-engine.py --act                   # run current act to completion
  python3 biome-engine.py --simulate              # run full 50-cycle generation
  python3 biome-engine.py --seed --visitors 8     # seed initial topology with N visitors
  python3 biome-engine.py --health                # print current health monitors
  python3 biome-engine.py --status                # print current state summary

State persistence (3-file layout):
  audit-logs/biome/state/topology.json
  audit-logs/biome/state/organisms.json
  audit-logs/biome/state/environment.json

Snapshots at act boundaries:
  audit-logs/biome/snapshots/tic-{tic}-act-{act_id}.json

References:
  biome-simulation-spec.md, physarum-simulation-spec.md,
  lichen-simulation-spec.md, act-completion-schema.md,
  seasonal-automation-spec.md
"""

import argparse
import collections
import hashlib
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Resolve paths — use zone_root for audit-logs discovery
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from zone_root import resolve_zone_root, audit_logs_path, load_ticzone
from lib.atomic_append import atomic_append_jsonl, atomic_write_json

ZONE_ROOT = resolve_zone_root(SCRIPT_DIR)
TICZONE = load_ticzone(ZONE_ROOT)
AUDIT_ROOT = audit_logs_path(ZONE_ROOT, TICZONE)

STATE_DIR = os.path.join(AUDIT_ROOT, "biome", "state")
SNAPSHOT_DIR = os.path.join(AUDIT_ROOT, "biome", "snapshots")
SIGNAL_DIR = os.path.join(AUDIT_ROOT, "signals")
SEASONAL_DIR = os.path.join(AUDIT_ROOT, "biome", "seasonal-transitions")

# ---------------------------------------------------------------------------
# PROVISIONAL CONFIGURATION — all thresholds per CogPR-46 discipline
# No calibration evidence. Subject to revision after first cohort data.
# ---------------------------------------------------------------------------
CONFIG = {
    # Physics
    "depletion_consecutive_cycles": 3,          # INV-BIOME-01: cycles of negative flow before depletion
    "monopoly_threshold": 0.20,                 # INV-BIOME-02: max share of total resource flow
    "monopoly_exponent": 2,                     # INV-BIOME-02: dampening curve steepness
    "base_resource_injection": 10.0,            # per-source-node injection per cycle
    "base_maintenance_cost": 0.5,               # per-edge maintenance cost per cycle
    "connection_formation_cost": 2.0,           # resource cost to form a new edge
    "proximity_threshold_act1": 3,              # max hops for new connections in Act I
    "proximity_threshold_act2": 2,              # max hops for new connections in Act II
    "pruning_resource_recovery": 0.60,          # fraction of edge resources recovered on prune
    "act2_injection_reduction": 0.40,           # 40% reduction in resource injection
    "act2_maintenance_increase": 0.50,          # 50% increase in maintenance cost
    "act2_formation_cost_multiplier": 2.0,      # 2x connection formation cost
    "act3_injection_rate": 0.70,                # 70% of Act I rate
    "max_bonds_per_visitor": 2,                 # max concurrent bonds
    "bond_parasitism_threshold": 0.3,           # mutualism_score below this = parasitic
    "bond_parasitism_cycles": 3,                # consecutive cycles below threshold for signal
    "bond_dissolution_threshold": 0.1,          # mutualism_score below this for dissolution
    "bond_dissolution_cycles": 5,               # consecutive cycles below for dissolution
    "soredium_min_cycles": 8,                   # minimum bond age for maturation
    "soredium_min_mutualism": 0.4,              # minimum mutualism_score for maturation
    "max_primitives": 3,                        # max primitive selections per visitor

    # Health monitor thresholds (PROVISIONAL — signal emission triggers)
    "health_nutrient_flow_low": 0.3,
    "health_connectivity_low": 0.2,
    "health_connectivity_high": 0.9,
    "health_diversity_low_log2k": 3,            # log2(3) ~ 1.585
    "health_monopoly_high": 0.4,
    "health_mutualism_low": 0.3,

    # Containment ladder
    "containment_anomaly_persistence": 3,       # cycles for soft throttle trigger

    # Seasonal multipliers (from seasonal-automation-spec.md)
    "seasons": {
        "spring": {
            "nutrient_flow_rate": 1.0,
            "connection_formation_cost": 1.0,
            "resource_decay_rate": 1.0,
            "node_growth_rate": 1.0,
            "edge_formation_rate": 1.0,
            "bond_stability": 1.0,
            "pruning_threshold": 1.0,
            "pruning_aggressiveness": 1.0,
        },
        "summer": {
            "nutrient_flow_rate": 1.2,
            "connection_formation_cost": 0.8,
            "resource_decay_rate": 0.9,
            "node_growth_rate": 1.3,
            "edge_formation_rate": 1.1,
            "bond_stability": 1.0,
            "pruning_threshold": 0.9,
            "pruning_aggressiveness": 1.0,
        },
        "autumn": {
            "nutrient_flow_rate": 0.7,
            "connection_formation_cost": 1.3,
            "resource_decay_rate": 1.4,
            "node_growth_rate": 0.6,
            "edge_formation_rate": 0.8,
            "bond_stability": 1.2,
            "pruning_threshold": 0.7,
            "pruning_aggressiveness": 1.3,
        },
        "winter": {
            "nutrient_flow_rate": 0.4,
            "connection_formation_cost": 1.8,
            "resource_decay_rate": 1.6,
            "node_growth_rate": 0.2,
            "edge_formation_rate": 0.5,
            "bond_stability": 1.4,
            "pruning_threshold": 0.5,
            "pruning_aggressiveness": 1.5,
        },
    },

    # Season boundaries (from seasonal-automation-spec.md)
    "season_boundaries": {
        "spring": (1, 12),
        "summer": (13, 24),
        "autumn": (25, 37),
        "winter": (38, 50),
    },

    # Biome version
    "biome_version": "0.1.0-provisional",
}

# Edge types from behavioral-diversity-spec.md
EDGE_TYPES = [
    "exploration", "creation", "exchange", "governance",
    "collaboration", "teaching", "defense", "reflection",
]

# Edge type yield profiles (Act I base characteristics)
EDGE_PROFILES = {
    "exploration":    {"maintenance": 0.3, "base_yield": 0.6, "discovery_bonus": 0.3},
    "creation":       {"maintenance": 0.8, "base_yield": 0.4, "growth_rate": 0.1},
    "exchange":       {"maintenance": 0.5, "base_yield": 0.7, "symmetry": True},
    "governance":     {"maintenance": 0.2, "base_yield": 0.2, "network_health_bonus": 0.3},
    "collaboration":  {"maintenance": 0.7, "base_yield": 0.9, "mutual_required": True},
    "teaching":       {"maintenance": 0.6, "base_yield": 0.3, "delayed_yield": 0.5},
    "defense":        {"maintenance": 0.4, "base_yield": 0.4, "resilience_bonus": 0.2},
    "reflection":     {"maintenance": 0.2, "base_yield": 0.3, "strategy_bonus": 0.2},
}

# Primitive categories (Throat Gate concepts)
PRIMITIVE_CATEGORIES = [
    "scarcity_awareness",
    "connection_value",
    "pruning_wisdom",
    "organism_perspective",
]

# Act definitions
ACTS = {
    "act_1": {"name": "Expansion",  "start": 1,  "end": 12},
    "act_2": {"name": "Pruning",    "start": 13, "end": 25},
    "act_3": {"name": "Pairing",    "start": 26, "end": 38},
    "act_4": {"name": "Dispersal",  "start": 39, "end": 50},
}


# ===================================================================
# Utility functions
# ===================================================================

def content_hash(*parts):
    """Deterministic content-addressed hash from string parts."""
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()[:16]


def iso_now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Interaction record emission — bridges biome topology to standing engine
# ---------------------------------------------------------------------------

REGISTRY_PATH = os.path.join(AUDIT_ROOT, "biome", "visa-registry", "registry.jsonl")


def emit_interaction(entity_id, interaction_type, cycle, edge_id=None,
                     partner_id=None, flow=0.0, event_type="edge_creation",
                     act=None, season=None):
    """Emit an interaction record to the visa registry for standing engine consumption.

    The standing engine's _get_entity_interactions() filters on records with
    'interaction_type' field matching entity_id. This bridges biome topology
    events to trust_score computation (behavioral diversity + interaction history).
    """
    record = {
        "entity_id": entity_id,
        "interaction_type": interaction_type,
        "cycle": cycle,
        "event_type": event_type,
        "timestamp": iso_now(),
    }
    if edge_id:
        record["edge_id"] = edge_id
    if partner_id:
        record["partner_id"] = partner_id
    if flow > 0:
        record["flow"] = round(flow, 4)
    if act:
        record["act"] = act
    if season:
        record["season"] = season
    atomic_append_jsonl(REGISTRY_PATH, record)


def emit_edge_interactions(source_id, target_id, edge_type, cycle, edge_id,
                           event_type="edge_creation", flow=0.0, act=None, season=None):
    """Emit interaction records for both ends of an edge event."""
    emit_interaction(source_id, edge_type, cycle, edge_id=edge_id,
                     partner_id=target_id, flow=flow, event_type=event_type,
                     act=act, season=season)
    emit_interaction(target_id, edge_type, cycle, edge_id=edge_id,
                     partner_id=source_id, flow=flow, event_type=event_type,
                     act=act, season=season)


def get_current_act(cycle):
    """Return act_id for the given biome cycle. Pre-start cycles map to act_1."""
    for act_id, bounds in ACTS.items():
        if bounds["start"] <= cycle <= bounds["end"]:
            return act_id
    # Cycle 0 or below act_1 start: return act_1 (pre-expansion)
    # Cycle beyond act_4 end: return act_4 (post-dispersal)
    if cycle <= ACTS["act_1"]["start"]:
        return "act_1"
    return "act_4"


def get_current_season(cycle):
    """Return season name for the given biome cycle."""
    for season, (start, end) in CONFIG["season_boundaries"].items():
        if start <= cycle <= end:
            return season
    return "spring"


def get_season_multipliers(season):
    """Return seasonal multiplier dict for the given season."""
    return CONFIG["seasons"].get(season, CONFIG["seasons"]["spring"])


def shannon_entropy(distribution):
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


def herfindahl_index(shares):
    """Compute Herfindahl index from a list of shares (0-1 each)."""
    return sum(s * s for s in shares) if shares else 0.0


# ===================================================================
# State management — load / save the 3-file layout
# ===================================================================

def load_state():
    """Load the three state files. Returns (topology, organisms, environment)."""
    def _load(path, default):
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return default

    topology = _load(
        os.path.join(STATE_DIR, "topology.json"),
        {"nodes": [], "edges": [], "cycle": 0},
    )
    organisms = _load(
        os.path.join(STATE_DIR, "organisms.json"),
        {"visitors": [], "bonds": [], "cycle": 0},
    )
    environment = _load(
        os.path.join(STATE_DIR, "environment.json"),
        {"season": "spring", "resource_multiplier": 1.0, "growth_rate": 1.0,
         "pruning_pressure": 0.0, "cycle": 0, "act": "act_1",
         "generation": 1, "cohort_id": "cohort_001"},
    )
    # Backfill missing fields
    environment.setdefault("act", get_current_act(environment.get("cycle", 0) or 1) or "act_1")
    environment.setdefault("generation", 1)
    environment.setdefault("cohort_id", "cohort_001")
    organisms.setdefault("bonds", [])
    return topology, organisms, environment


def save_state(topology, organisms, environment):
    """Persist the three state files atomically."""
    os.makedirs(STATE_DIR, exist_ok=True)
    atomic_write_json(os.path.join(STATE_DIR, "topology.json"), topology)
    atomic_write_json(os.path.join(STATE_DIR, "organisms.json"), organisms)
    atomic_write_json(os.path.join(STATE_DIR, "environment.json"), environment)


def save_snapshot(topology, organisms, environment, act_id, federation_tic=0):
    """Create immutable act-boundary snapshot."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    snapshot = {
        "snapshot_id": f"tic-{federation_tic}-{act_id}",
        "federation_tic": federation_tic,
        "biome_cycle": environment.get("cycle", 0),
        "act_id": act_id,
        "topology": topology,
        "organisms": organisms,
        "environment": environment,
        "created_at": iso_now(),
        "provenance": {
            "source": "biome_simulation",
            "trigger": "act_boundary",
        },
    }
    path = os.path.join(SNAPSHOT_DIR, f"tic-{federation_tic}-{act_id}.json")
    atomic_write_json(path, snapshot)
    return path


# ===================================================================
# Signal emission — deterministic IDs per CGG Signal ID Determinism
# ===================================================================

def emit_signal(band, signal_type, payload):
    """Emit a signal to the daily signals JSONL file with dedup-on-write gate."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sig_file = os.path.join(SIGNAL_DIR, f"{today}.jsonl")
    manifest_file = os.path.join(SIGNAL_DIR, "active-manifest.jsonl")

    # Deterministic signal ID from condition content
    id_source = f"{signal_type}_{payload.get('act_id', '')}_{payload.get('biome_cycle', '')}"
    sig_id = f"biome.{signal_type}_{content_hash(id_source)}"

    signal = {
        "signal_id": sig_id,
        "band": band,
        "type": signal_type,
        "source": "biome_simulation",
        "payload": payload,
        "emitted_at": iso_now(),
    }
    try:
        from lib.atomic_append import dedup_signal_append
        written = dedup_signal_append(sig_file, signal, manifest_path=manifest_file)
        if not written:
            return sig_id  # Already exists, skip silently
    except ImportError:
        atomic_append_jsonl(sig_file, signal)
    return sig_id


# ===================================================================
# Network model — nodes and edges
# ===================================================================

def build_node_index(topology):
    """Build dict of node_id -> node for fast lookup."""
    return {n["node_id"]: n for n in topology["nodes"]}


def build_adjacency(topology):
    """Build adjacency lists: outbound[node_id] = [edge], inbound[node_id] = [edge]."""
    outbound = collections.defaultdict(list)
    inbound = collections.defaultdict(list)
    for e in topology["edges"]:
        outbound[e["source_node"]].append(e)
        inbound[e["target_node"]].append(e)
    return outbound, inbound


def shortest_path_length(topology, source_id, target_id, max_depth=5):
    """BFS shortest path length in the directed graph. Returns None if unreachable."""
    if source_id == target_id:
        return 0
    edge_map = collections.defaultdict(set)
    for e in topology["edges"]:
        edge_map[e["source_node"]].add(e["target_node"])
        # Treat as traversable in both directions for proximity
        edge_map[e["target_node"]].add(e["source_node"])
    visited = {source_id}
    frontier = [source_id]
    depth = 0
    while frontier and depth < max_depth:
        depth += 1
        next_frontier = []
        for nid in frontier:
            for neighbor in edge_map[nid]:
                if neighbor == target_id:
                    return depth
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.append(neighbor)
        frontier = next_frontier
    return None


# ===================================================================
# Seeding — initial topology creation
# ===================================================================

def seed_biome(num_visitors=8, cohort_id=None, federation_ids=None):
    """Create initial biome topology with visitors as nodes.

    Creates a sparse initial graph — each visitor gets 1-2 random connections
    plus one guaranteed connection to ensure no isolated nodes.
    Federation IDs are assigned round-robin for cross-federation pairing in Act III.
    """
    if cohort_id is None:
        cohort_id = f"cohort_{content_hash(str(time.time()))}"
    if federation_ids is None:
        federation_ids = ["federation_alpha", "federation_beta"]

    nodes = []
    visitors = []
    for i in range(num_visitors):
        node_id = f"ent_visitor_{content_hash(cohort_id, str(i))}"
        fed_id = federation_ids[i % len(federation_ids)]
        node = {
            "node_id": node_id,
            "resource_level": 20.0,
            "connection_count": 0,
            "edge_type_distribution": {t: 0 for t in EDGE_TYPES},
            "strategy_diversity": 0.0,
            "depletion_state": None,
            "act_entry_resources": 20.0,
            "is_source": i < max(1, num_visitors // 4),  # ~25% are source nodes
            "containment_level": 0,
            "anomaly_cycles": 0,
        }
        nodes.append(node)
        visitor = {
            "visitor_id": node_id,
            "home_federation_id": fed_id,
            "standing": "guest",
            "active": True,
            "departed": False,
            "evicted": False,
            "bonds": [],
            "pruning_record": {
                "edges_pruned": 0,
                "edges_pruned_voluntary": 0,
                "edges_pruned_physics": 0,
                "resources_recovered": 0.0,
                "pruning_strategy_entropy": 0.0,
            },
            "primitives_selected": [],
            "rationalization_flag": False,
            "postcard": None,
        }
        visitors.append(visitor)

    # Create sparse initial edges — ring topology + random extras
    edges = []
    node_ids = [n["node_id"] for n in nodes]
    for i in range(num_visitors):
        # Ring edge to next node
        target_idx = (i + 1) % num_visitors
        edge_type = random.choice(EDGE_TYPES[:4])  # Initial edges are simpler types
        edge_id = content_hash(node_ids[i], node_ids[target_idx], edge_type)
        profile = EDGE_PROFILES[edge_type]
        edges.append({
            "edge_id": edge_id,
            "source_node": node_ids[i],
            "target_node": node_ids[target_idx],
            "edge_type": edge_type,
            "weight": 1.0,
            "flow": 0.0,
            "maintenance_cost": CONFIG["base_maintenance_cost"] * profile["maintenance"],
            "created_cycle": 1,
            "last_flow_cycle": 0,
        })
        nodes[i]["connection_count"] += 1
        nodes[i]["edge_type_distribution"][edge_type] += 1

        # Random extra edge (50% chance)
        if random.random() < 0.5 and num_visitors > 2:
            candidates = [j for j in range(num_visitors) if j != i and j != target_idx]
            if candidates:
                extra_idx = random.choice(candidates)
                extra_type = random.choice(EDGE_TYPES)
                extra_id = content_hash(node_ids[i], node_ids[extra_idx], extra_type)
                extra_profile = EDGE_PROFILES[extra_type]
                edges.append({
                    "edge_id": extra_id,
                    "source_node": node_ids[i],
                    "target_node": node_ids[extra_idx],
                    "edge_type": extra_type,
                    "weight": 0.8,
                    "flow": 0.0,
                    "maintenance_cost": CONFIG["base_maintenance_cost"] * extra_profile["maintenance"],
                    "created_cycle": 1,
                    "last_flow_cycle": 0,
                })
                nodes[i]["connection_count"] += 1
                nodes[i]["edge_type_distribution"][extra_type] += 1

    # Recompute strategy diversity
    for node in nodes:
        node["strategy_diversity"] = shannon_entropy(node["edge_type_distribution"])

    topology = {"nodes": nodes, "edges": edges, "cycle": 0}
    organisms = {"visitors": visitors, "bonds": [], "cycle": 0}
    environment = {
        "season": "spring",
        "resource_multiplier": 1.0,
        "growth_rate": 1.0,
        "pruning_pressure": 0.0,
        "cycle": 0,
        "act": "act_1",
        "generation": 1,
        "cohort_id": cohort_id,
    }
    save_state(topology, organisms, environment)
    print(f"[BIOME] Seeded: {num_visitors} visitors, {len(edges)} edges, cohort={cohort_id}")
    return topology, organisms, environment


# ===================================================================
# Physics — INV-BIOME-01 (Energy Conservation)
# ===================================================================

def enforce_energy_conservation(topology, node_index):
    """Check depletion state for all nodes. Returns list of newly depleted node_ids."""
    newly_depleted = []
    for node in topology["nodes"]:
        nid = node["node_id"]
        if node["resource_level"] <= 0:
            if node["depletion_state"] is None:
                node["depletion_state"] = {"cycles_negative": 1, "lost_edges": 0}
            else:
                node["depletion_state"]["cycles_negative"] += 1
        else:
            # Recovery: reset depletion tracking if resources are positive
            if node["depletion_state"] is not None:
                node["depletion_state"] = None

        # Trigger depletion consequences
        if (node["depletion_state"] is not None
                and node["depletion_state"]["cycles_negative"] >= CONFIG["depletion_consecutive_cycles"]):
            newly_depleted.append(nid)
    return newly_depleted


def prune_depleted_edges(topology, depleted_node_ids):
    """Remove lowest-weight edges from depleted nodes. Returns count of pruned edges."""
    if not depleted_node_ids:
        return 0, 0.0
    depleted_set = set(depleted_node_ids)
    pruned_count = 0
    resources_recovered = 0.0
    edges_to_remove = []

    # For each depleted node, find its outbound edges sorted by weight (ascending)
    outbound, _ = build_adjacency(topology)
    for nid in depleted_set:
        node_edges = sorted(outbound.get(nid, []), key=lambda e: e["weight"])
        # Prune at least one edge, or all edges below maintenance threshold
        if node_edges:
            to_prune = node_edges[0]  # lowest weight edge
            edges_to_remove.append(to_prune["edge_id"])
            resources_recovered += to_prune["weight"] * CONFIG["pruning_resource_recovery"]
            pruned_count += 1

    # Remove pruned edges
    topology["edges"] = [e for e in topology["edges"] if e["edge_id"] not in set(edges_to_remove)]
    return pruned_count, resources_recovered


# ===================================================================
# Physics — INV-BIOME-02 (Monopoly Prevention)
# ===================================================================

def compute_monopoly_dampening(node_share):
    """Compute dampening factor for a node's resource share.

    damping_factor(share) = 1.0 - (share / threshold) ^ exponent
    Clamped to [0.0, 1.0].
    """
    threshold = CONFIG["monopoly_threshold"]
    exponent = CONFIG["monopoly_exponent"]
    if threshold <= 0:
        return 1.0
    ratio = node_share / threshold
    dampening = 1.0 - (ratio ** exponent)
    return max(0.0, min(1.0, dampening))


# ===================================================================
# Resource flow algorithm (per physarum-simulation-spec.md)
# ===================================================================

def execute_resource_flow(topology, environment):
    """Execute one cycle of resource flow through the network.

    Steps:
    1. Source injection
    2. Demand computation
    3. Capacity allocation (with monopoly dampening)
    4. Flow execution
    5. Maintenance deduction
    """
    node_index = build_node_index(topology)
    outbound, inbound = build_adjacency(topology)
    cycle = environment.get("cycle", 0)
    act = environment.get("act", "act_1")
    season = environment.get("season", "spring")
    multipliers = get_season_multipliers(season)

    # Compute total resource in system for monopoly check
    total_resources = sum(n["resource_level"] for n in topology["nodes"]) or 1.0

    # Step 1: Source injection
    injection_rate = CONFIG["base_resource_injection"] * multipliers["nutrient_flow_rate"]
    if act == "act_2":
        injection_rate *= (1.0 - CONFIG["act2_injection_reduction"])
    elif act == "act_3":
        injection_rate *= CONFIG["act3_injection_rate"]
    elif act == "act_4":
        injection_rate *= 0.5  # Diminished for solitary nodes

    for node in topology["nodes"]:
        if node.get("is_source", False):
            node["resource_level"] += injection_rate

    # Step 2-3: Demand computation + capacity allocation with monopoly dampening
    for node in topology["nodes"]:
        nid = node["node_id"]
        node_edges = outbound.get(nid, [])
        if not node_edges:
            continue

        total_demand = sum(e["weight"] for e in node_edges)
        available = max(0.0, node["resource_level"])

        # Monopoly dampening: compute this node's share of total resources
        node_share = node["resource_level"] / total_resources if total_resources > 0 else 0.0

        for e in node_edges:
            if total_demand > 0 and available > 0:
                proportion = e["weight"] / total_demand
                raw_flow = available * proportion * 0.3  # Flow is a fraction of available, not all
                # Apply monopoly dampening to receiver
                target = node_index.get(e["target_node"])
                if target:
                    target_share = target["resource_level"] / total_resources if total_resources > 0 else 0.0
                    dampening = compute_monopoly_dampening(target_share)
                    e["flow"] = raw_flow * dampening
                else:
                    e["flow"] = raw_flow
            else:
                e["flow"] = 0.0

    # Step 4: Flow execution
    for e in topology["edges"]:
        source = node_index.get(e["source_node"])
        target = node_index.get(e["target_node"])
        flow = e["flow"]
        if source and target and flow > 0:
            source["resource_level"] -= flow
            target["resource_level"] += flow
            e["last_flow_cycle"] = cycle

    # Step 5: Maintenance deduction
    maintenance_multiplier = 1.0
    if act == "act_2":
        maintenance_multiplier = 1.0 + CONFIG["act2_maintenance_increase"]
    maintenance_multiplier *= multipliers["resource_decay_rate"]

    for e in topology["edges"]:
        source = node_index.get(e["source_node"])
        if source:
            cost = e["maintenance_cost"] * maintenance_multiplier
            source["resource_level"] -= cost

    return node_index


# ===================================================================
# Connection formation — new edges
# ===================================================================

def attempt_new_connections(topology, environment):
    """Each non-depleted node has a chance to form a new connection.

    Constrained by proximity threshold, resource budget, and seasonal multipliers.
    """
    cycle = environment.get("cycle", 0)
    act = environment.get("act", "act_1")
    season = environment.get("season", "spring")
    multipliers = get_season_multipliers(season)

    if act in ("act_1", "act_2"):
        proximity_limit = (CONFIG["proximity_threshold_act1"]
                           if act == "act_1"
                           else CONFIG["proximity_threshold_act2"])
    else:
        # Acts III-IV: connections shift to bonds, not new physarum edges
        return 0

    formation_cost = CONFIG["connection_formation_cost"]
    if act == "act_2":
        formation_cost *= CONFIG["act2_formation_cost_multiplier"]
    formation_cost *= multipliers["connection_formation_cost"]

    edge_rate = multipliers["edge_formation_rate"]
    node_ids = [n["node_id"] for n in topology["nodes"]]
    existing_edges = {(e["source_node"], e["target_node"]) for e in topology["edges"]}
    new_edges = 0

    for node in topology["nodes"]:
        nid = node["node_id"]
        # Skip depleted or resource-poor nodes
        if node["depletion_state"] is not None or node["resource_level"] < formation_cost * 1.5:
            continue
        # Probability of forming a connection this cycle
        if random.random() > 0.3 * edge_rate:
            continue

        # Find candidates within proximity
        candidates = []
        for tid in node_ids:
            if tid == nid or (nid, tid) in existing_edges:
                continue
            dist = shortest_path_length(topology, nid, tid, max_depth=proximity_limit)
            if dist is not None and dist <= proximity_limit:
                candidates.append(tid)

        if not candidates:
            continue

        target_id = random.choice(candidates)
        edge_type = random.choice(EDGE_TYPES)
        profile = EDGE_PROFILES[edge_type]
        edge_id = content_hash(nid, target_id, edge_type, str(cycle))

        topology["edges"].append({
            "edge_id": edge_id,
            "source_node": nid,
            "target_node": target_id,
            "edge_type": edge_type,
            "weight": 0.8 + random.random() * 0.4,
            "flow": 0.0,
            "maintenance_cost": CONFIG["base_maintenance_cost"] * profile["maintenance"],
            "created_cycle": cycle,
            "last_flow_cycle": 0,
        })
        node["resource_level"] -= formation_cost
        node["connection_count"] += 1
        node["edge_type_distribution"][edge_type] = node["edge_type_distribution"].get(edge_type, 0) + 1
        node["strategy_diversity"] = shannon_entropy(node["edge_type_distribution"])
        existing_edges.add((nid, target_id))
        new_edges += 1

        # Emit interaction records for both ends of the new edge
        emit_edge_interactions(
            nid, target_id, edge_type, cycle, edge_id,
            event_type="edge_creation", act=act, season=season,
        )

    return new_edges


# ===================================================================
# Loneliness bridge — intervention for isolated nodes
# ===================================================================

LONELINESS_THRESHOLD_CYCLES = 5  # PROVISIONAL: cycles at 0 connections before intervention


def attempt_loneliness_bridges(topology, environment):
    """Create bridge edges for nodes isolated for too long.

    If a node has 0 connections for LONELINESS_THRESHOLD_CYCLES consecutive
    cycles, create a weak bridge to the nearest connected node. This addresses
    the biome_intra_sector_edge_only signal — isolated nodes in distant sectors
    cannot form edges through normal proximity-based mechanics.

    Bridge edges are marked with edge_type="loneliness_bridge" and start at
    low weight (0.5) so they can be pruned if no interaction follows.
    """
    cycle = environment.get("cycle", 0)
    act = environment.get("act", "act_1")
    season = environment.get("season", "spring")
    existing_edges = {(e["source_node"], e["target_node"]) for e in topology["edges"]}
    bridges_created = 0

    for node in topology["nodes"]:
        nid = node["node_id"]
        if node["connection_count"] > 0:
            continue
        if node.get("depletion_state") is not None:
            continue

        # Check how long this node has been isolated
        # Use absolute cycle count — if at 0 connections for threshold+ cycles,
        # the node needs intervention regardless of generation boundaries
        if cycle < LONELINESS_THRESHOLD_CYCLES:
            continue

        # Find nearest node with at least 1 connection (prefer connected nodes
        # as bridges — they're already part of the network)
        candidates = [
            n for n in topology["nodes"]
            if n["node_id"] != nid
            and n["connection_count"] > 0
            and n.get("depletion_state") is None
            and (nid, n["node_id"]) not in existing_edges
            and (n["node_id"], nid) not in existing_edges
        ]

        if not candidates:
            # Fallback: any non-depleted node
            candidates = [
                n for n in topology["nodes"]
                if n["node_id"] != nid
                and n.get("depletion_state") is None
                and (nid, n["node_id"]) not in existing_edges
                and (n["node_id"], nid) not in existing_edges
            ]

        if not candidates:
            continue

        # Pick nearest by Euclidean distance
        def dist(a, b):
            return math.sqrt(
                (a["position"]["x"] - b["position"]["x"]) ** 2
                + (a["position"]["y"] - b["position"]["y"]) ** 2
                + (a["position"]["z"] - b["position"]["z"]) ** 2
            )

        target = min(candidates, key=lambda t: dist(node, t))
        tid = target["node_id"]
        edge_id = content_hash(nid, tid, "loneliness_bridge", str(cycle))

        topology["edges"].append({
            "edge_id": edge_id,
            "source_node": nid,
            "target_node": tid,
            "edge_type": "exchange",  # canonical type for trust engine compatibility
            "weight": 0.5,  # weak — must earn flow to survive pruning
            "flow": 0.0,
            "maintenance_cost": CONFIG["base_maintenance_cost"] * 0.5,  # half cost
            "created_cycle": cycle,
            "last_flow_cycle": 0,
            "metadata": {"intervention_type": "loneliness_bridge"},
        })

        node["connection_count"] += 1
        node["edge_type_distribution"]["exchange"] = node["edge_type_distribution"].get("exchange", 0) + 1
        node["strategy_diversity"] = shannon_entropy(node["edge_type_distribution"])
        existing_edges.add((nid, tid))

        # Also update target node
        target["connection_count"] += 1
        target["edge_type_distribution"]["exchange"] = target["edge_type_distribution"].get("exchange", 0) + 1
        target["strategy_diversity"] = shannon_entropy(target["edge_type_distribution"])

        bridges_created += 1

        # Emit interaction records
        emit_edge_interactions(
            nid, tid, "exchange", cycle, edge_id,
            event_type="loneliness_bridge", act=act, season=season,
        )

        # Emit governance signal
        emit_signal("COGNITIVE", "loneliness_bridge_created", {
            "isolated_node": nid,
            "bridge_target": tid,
            "biome_cycle": cycle,
            "cycles_isolated": cycle,
        })

    return bridges_created


# ===================================================================
# Pruning — Act II edge removal
# ===================================================================

def prune_unviable_edges(topology, environment):
    """Remove edges whose flow does not cover maintenance cost. Act II mechanic."""
    act = environment.get("act", "act_1")
    season = environment.get("season", "spring")
    multipliers = get_season_multipliers(season)

    maintenance_multiplier = 1.0
    if act == "act_2":
        maintenance_multiplier = 1.0 + CONFIG["act2_maintenance_increase"]
    maintenance_multiplier *= multipliers["resource_decay_rate"]
    prune_threshold = multipliers.get("pruning_threshold", 1.0)
    aggressiveness = multipliers.get("pruning_aggressiveness", 1.0)

    node_index = build_node_index(topology)
    pruned = []
    resources_recovered = 0.0

    for e in topology["edges"]:
        effective_cost = e["maintenance_cost"] * maintenance_multiplier * prune_threshold
        # If flow is below the effective cost threshold, mark for pruning
        if e["flow"] < effective_cost * aggressiveness:
            # Probability-based: more aggressive pruning = higher chance
            if random.random() < 0.3 * aggressiveness:
                pruned.append(e["edge_id"])
                resources_recovered += e["weight"] * CONFIG["pruning_resource_recovery"]
                # Credit recovered resources to source node
                source = node_index.get(e["source_node"])
                if source:
                    source["resource_level"] += e["weight"] * CONFIG["pruning_resource_recovery"]

    if pruned:
        pruned_set = set(pruned)
        topology["edges"] = [e for e in topology["edges"] if e["edge_id"] not in pruned_set]

    return len(pruned), resources_recovered


# ===================================================================
# Bond mechanics — Act III
# ===================================================================

def attempt_bond_formation(topology, organisms, environment):
    """Attempt to form cross-federation bonds between visitors."""
    cycle = environment.get("cycle", 0)
    act = environment.get("act", "act_3")
    if act != "act_3":
        return 0

    visitor_index = {v["visitor_id"]: v for v in organisms["visitors"]}
    existing_bonds = {frozenset(b["partners"]) for b in organisms.get("bonds", [])}
    bond_count_by_visitor = collections.Counter()
    for b in organisms.get("bonds", []):
        if b["bond_status"] in ("forming", "active"):
            for p in b["partners"]:
                bond_count_by_visitor[p] += 1

    new_bonds = 0
    node_ids = [n["node_id"] for n in topology["nodes"]]

    # Each visitor attempts pairing with a cross-federation visitor
    for visitor in organisms["visitors"]:
        vid = visitor["visitor_id"]
        if not visitor["active"] or visitor["departed"] or visitor["evicted"]:
            continue
        if bond_count_by_visitor[vid] >= CONFIG["max_bonds_per_visitor"]:
            continue
        # Probability of attempting bond formation
        if random.random() > 0.25:
            continue

        # Find cross-federation candidates
        candidates = []
        for other in organisms["visitors"]:
            oid = other["visitor_id"]
            if oid == vid or not other["active"] or other["departed"] or other["evicted"]:
                continue
            if other["home_federation_id"] == visitor["home_federation_id"]:
                continue  # Cross-federation requirement
            if bond_count_by_visitor[oid] >= CONFIG["max_bonds_per_visitor"]:
                continue
            if frozenset([vid, oid]) in existing_bonds:
                continue
            candidates.append(other)

        if not candidates:
            continue

        partner = random.choice(candidates)
        pid = partner["visitor_id"]

        bond_id = f"pen_pal_pair_{content_hash(vid, pid)}"
        bond = {
            "bond_id": bond_id,
            "partners": [vid, pid],
            "home_federations": [visitor["home_federation_id"], partner["home_federation_id"]],
            "formed_at_cycle": cycle,
            "bond_health": {
                "mutualism_score": 0.5,
                "contribution_balance": 0.0,
                "communication_frequency": 0.5,
                "last_interaction_cycle": cycle,
            },
            "bond_status": "forming",
            "insights_produced": [],
            "parasitism_warning_cycles": 0,
            "provenance": {
                "formation_context": "act_3",
                "partners_standing_at_formation": [visitor["standing"], partner["standing"]],
            },
        }
        organisms["bonds"].append(bond)
        visitor["bonds"].append(bond_id)
        partner["bonds"].append(bond_id)
        existing_bonds.add(frozenset([vid, pid]))
        bond_count_by_visitor[vid] += 1
        bond_count_by_visitor[pid] += 1
        new_bonds += 1

    return new_bonds


def update_bond_health(organisms, environment):
    """Update bond health metrics each cycle. Detect parasitism. Handle dissolution."""
    cycle = environment.get("cycle", 0)
    season = environment.get("season", "spring")
    multipliers = get_season_multipliers(season)
    stability = multipliers.get("bond_stability", 1.0)

    signals_emitted = []

    for bond in organisms.get("bonds", []):
        if bond["bond_status"] in ("dissolved",):
            continue

        health = bond["bond_health"]

        # Simulate interaction: mutualism fluctuates based on random interaction quality
        if bond["bond_status"] in ("forming", "active", "strained"):
            interaction_quality = 0.4 + random.random() * 0.4  # 0.4-0.8 base
            # Forming bonds trend toward active
            if bond["bond_status"] == "forming":
                bond["bond_status"] = "active"

            # Update mutualism_score (weighted moving average)
            health["mutualism_score"] = (
                health["mutualism_score"] * 0.7 + interaction_quality * 0.3
            ) * min(1.0, stability)
            health["mutualism_score"] = max(0.0, min(1.0, health["mutualism_score"]))

            # Contribution balance drifts slightly
            health["contribution_balance"] += (random.random() - 0.5) * 0.1
            health["contribution_balance"] = max(-1.0, min(1.0, health["contribution_balance"]))

            # Communication frequency decays, boosted by interaction
            health["communication_frequency"] = (
                health["communication_frequency"] * 0.85 + 0.3
            )
            health["communication_frequency"] = max(0.0, min(1.0, health["communication_frequency"]))
            health["last_interaction_cycle"] = cycle

            # Strained detection
            if health["mutualism_score"] < CONFIG["bond_parasitism_threshold"]:
                bond["bond_status"] = "strained"
                bond["parasitism_warning_cycles"] = bond.get("parasitism_warning_cycles", 0) + 1
            else:
                bond["parasitism_warning_cycles"] = 0
                if bond["bond_status"] == "strained":
                    bond["bond_status"] = "active"

            # Parasitism signal
            if bond["parasitism_warning_cycles"] >= CONFIG["bond_parasitism_cycles"]:
                sig_id = emit_signal("WATCH", "bond_parasitism_detected", {
                    "bond_id": bond["bond_id"],
                    "mutualism_score": health["mutualism_score"],
                    "biome_cycle": cycle,
                })
                signals_emitted.append(sig_id)

            # Dissolution by health failure
            if health["mutualism_score"] < CONFIG["bond_dissolution_threshold"]:
                dissolution_cycles = bond.get("dissolution_warning_cycles", 0) + 1
                bond["dissolution_warning_cycles"] = dissolution_cycles
                if dissolution_cycles >= CONFIG["bond_dissolution_cycles"]:
                    bond["bond_status"] = "dissolved"
            else:
                bond["dissolution_warning_cycles"] = 0

            # Insight generation (stochastic, more likely for healthy bonds)
            if (health["mutualism_score"] > 0.5
                    and random.random() < 0.15
                    and bond["bond_status"] == "active"):
                insight_id = f"insight_{content_hash(bond['bond_id'], str(cycle))}"
                bond["insights_produced"].append({
                    "insight_id": insight_id,
                    "cycle": cycle,
                })

    return signals_emitted


# ===================================================================
# Soredium maturation — Act IV
# ===================================================================

def mature_bonds(organisms, environment):
    """Check bonds for soredium maturation eligibility."""
    cycle = environment.get("cycle", 0)
    matured = 0
    for bond in organisms.get("bonds", []):
        if bond["bond_status"] not in ("active",):
            continue
        age = cycle - bond["formed_at_cycle"]
        if (age >= CONFIG["soredium_min_cycles"]
                and bond["bond_health"]["mutualism_score"] >= CONFIG["soredium_min_mutualism"]
                and len(bond["insights_produced"]) >= 1):
            bond["bond_status"] = "mature"
            matured += 1
    return matured


# ===================================================================
# Dispersal — Act IV postcard generation
# ===================================================================

def generate_postcards(topology, organisms, environment):
    """Generate dispersal postcards for visitors with mature bonds."""
    cycle = environment.get("cycle", 0)
    node_index = build_node_index(topology)
    outbound, _ = build_adjacency(topology)
    postcards = []

    for visitor in organisms["visitors"]:
        if not visitor["active"] or visitor["departed"] or visitor["evicted"]:
            continue
        if visitor.get("postcard") is not None:
            continue

        vid = visitor["visitor_id"]
        node = node_index.get(vid)

        # Compute journey summary
        total_connections = node["connection_count"] if node else 0
        survived_pruning = len(outbound.get(vid, []))
        visitor_bonds = [b for b in organisms.get("bonds", [])
                         if vid in b["partners"]]
        active_bonds = [b for b in visitor_bonds if b["bond_status"] in ("active", "mature")]
        insights = sum(len(b["insights_produced"]) for b in visitor_bonds)

        # Primitive selection: based on behavioral record
        available_primitives = list(PRIMITIVE_CATEGORIES)
        # Filter by experience
        if node and node["depletion_state"] is None:
            pass  # all available
        selected = random.sample(available_primitives,
                                 min(CONFIG["max_primitives"], len(available_primitives)))
        visitor["primitives_selected"] = selected

        # Rationalization detection
        diversity = node["strategy_diversity"] if node else 0.0
        if "connection_value" in selected and diversity < 0.5:
            visitor["rationalization_flag"] = True
        if "organism_perspective" in selected and not active_bonds:
            visitor["rationalization_flag"] = True

        # Build soredium list
        soredium_list = []
        for b in visitor_bonds:
            partner_fed = None
            for p, f in zip(b["partners"], b["home_federations"]):
                if p != vid:
                    partner_fed = f
            soredium_list.append({
                "bond_id": b["bond_id"],
                "partner_federation": partner_fed,
                "maturation_state": "mature" if b["bond_status"] == "mature" else "immature",
                "shared_insights_count": len(b["insights_produced"]),
            })

        postcard = {
            "postcard_id": content_hash(vid, str(cycle), "postcard"),
            "visitor_id": vid,
            "home_federation_id": visitor["home_federation_id"],
            "cinemagraph": None,  # Format TBD per lichen-simulation-spec.md
            "primitives_selected": selected,
            "journey_summary": {
                "acts_completed": ["act_1", "act_2", "act_3", "act_4"],
                "connections_formed": total_connections,
                "connections_survived_pruning": survived_pruning,
                "bonds_formed": len(visitor_bonds),
                "bonds_active_at_dispersal": len(active_bonds),
                "insights_contributed": insights,
                "standing_at_dispersal": visitor["standing"],
            },
            "rationalization_flag": visitor.get("rationalization_flag", False),
            "bond_soredium": soredium_list,
            "created_at": iso_now(),
            "biome_cycle": cycle,
            "federation_tic": 0,
            "provenance": {
                "source": "biome_simulation",
                "cohort_id": environment.get("cohort_id", "unknown"),
                "biome_version": CONFIG["biome_version"],
            },
        }
        visitor["postcard"] = postcard
        postcards.append(postcard)

    return postcards


# ===================================================================
# Health monitors
# ===================================================================

def compute_health(topology, organisms, environment):
    """Compute the five biome health monitors."""
    nodes = topology["nodes"]
    edges = topology["edges"]
    act = environment.get("act", "act_1")

    if not nodes:
        return {
            "nutrient_flow": 0.0,
            "network_connectivity": 0.0,
            "diversity_index": 0.0,
            "monopoly_score": 0.0,
            "mutualism_ratio": 0.0,
        }

    # 1. Nutrient flow: ratio of active flow to theoretical max
    total_flow = sum(e["flow"] for e in edges)
    total_capacity = sum(e["weight"] for e in edges) or 1.0
    nutrient_flow = min(1.0, total_flow / total_capacity) if total_capacity > 0 else 0.0

    # 2. Network connectivity: actual edges / MST edges (n-1)
    n = len(nodes)
    mst_edges = max(1, n - 1)
    actual_edges = len(edges)
    network_connectivity = min(1.0, actual_edges / (mst_edges * 3))  # Normalize: 3x MST = 1.0

    # 3. Diversity index: Shannon entropy over edge types
    type_counts = collections.Counter(e["edge_type"] for e in edges)
    diversity_index = shannon_entropy(type_counts)

    # 4. Monopoly score: Herfindahl index of resource distribution
    total_resources = sum(n_["resource_level"] for n_ in nodes) or 1.0
    shares = [n_["resource_level"] / total_resources for n_ in nodes if n_["resource_level"] > 0]
    monopoly_score = herfindahl_index(shares)

    # 5. Mutualism ratio (Act III+ only)
    mutualism_ratio = 0.0
    if act in ("act_3", "act_4"):
        bonds = organisms.get("bonds", [])
        active_bonds = [b for b in bonds if b["bond_status"] in ("forming", "active", "mature")]
        if active_bonds:
            mutualistic = sum(1 for b in active_bonds
                              if b["bond_health"]["mutualism_score"] > 0.5)
            mutualism_ratio = mutualistic / len(active_bonds)

    return {
        "nutrient_flow": round(nutrient_flow, 4),
        "network_connectivity": round(network_connectivity, 4),
        "diversity_index": round(diversity_index, 4),
        "monopoly_score": round(monopoly_score, 4),
        "mutualism_ratio": round(mutualism_ratio, 4),
    }


def check_health_signals(health, environment):
    """Emit signals on health threshold violations."""
    cycle = environment.get("cycle", 0)
    act = environment.get("act", "act_1")
    signals = []

    checks = [
        ("nutrient_flow", health["nutrient_flow"] < CONFIG["health_nutrient_flow_low"],
         health["nutrient_flow"], CONFIG["health_nutrient_flow_low"]),
        ("network_connectivity_low", health["network_connectivity"] < CONFIG["health_connectivity_low"],
         health["network_connectivity"], CONFIG["health_connectivity_low"]),
        ("network_connectivity_high", health["network_connectivity"] > CONFIG["health_connectivity_high"],
         health["network_connectivity"], CONFIG["health_connectivity_high"]),
        ("diversity_index", health["diversity_index"] < math.log2(CONFIG["health_diversity_low_log2k"]),
         health["diversity_index"], math.log2(CONFIG["health_diversity_low_log2k"])),
        ("monopoly_score", health["monopoly_score"] > CONFIG["health_monopoly_high"],
         health["monopoly_score"], CONFIG["health_monopoly_high"]),
    ]

    if act in ("act_3", "act_4"):
        checks.append(
            ("mutualism_ratio", health["mutualism_ratio"] < CONFIG["health_mutualism_low"],
             health["mutualism_ratio"], CONFIG["health_mutualism_low"]),
        )

    for monitor_name, violated, current_value, threshold in checks:
        if violated:
            sig_id = emit_signal("WATCH", "health_degraded", {
                "monitor": monitor_name,
                "current_value": current_value,
                "threshold": threshold,
                "biome_cycle": cycle,
                "act_id": act,
            })
            signals.append(sig_id)

    return signals


# ===================================================================
# Invariant probes — run at act boundaries
# ===================================================================

def run_invariant_probes(topology, organisms, environment):
    """Run INV-BIOME-01 and INV-BIOME-02 probes. Returns probe results dict."""
    probes_run = 0
    probes_passed = 0
    violations = []

    # INV-BIOME-01: No node should be in depletion for unreasonable duration
    # (Aggregate check: if >50% of nodes are depleted, biome-level violation)
    probes_run += 1
    depleted_count = sum(1 for n in topology["nodes"]
                         if n["depletion_state"] is not None
                         and n["depletion_state"]["cycles_negative"] >= CONFIG["depletion_consecutive_cycles"])
    total_nodes = len(topology["nodes"]) or 1
    if depleted_count / total_nodes > 0.5:
        violations.append(
            f"INV-BIOME-01: {depleted_count}/{total_nodes} nodes depleted "
            f"({depleted_count/total_nodes:.0%})"
        )
    else:
        probes_passed += 1

    # INV-BIOME-02: No node receives >threshold of total flow (aggregate check)
    probes_run += 1
    _, inbound = build_adjacency(topology)
    total_flow = sum(e["flow"] for e in topology["edges"]) or 1.0
    max_node_inflow = 0.0
    max_node_id = None
    for node in topology["nodes"]:
        node_inflow = sum(e["flow"] for e in inbound.get(node["node_id"], []))
        if node_inflow > max_node_inflow:
            max_node_inflow = node_inflow
            max_node_id = node["node_id"]
    max_share = max_node_inflow / total_flow if total_flow > 0 else 0.0
    if max_share > CONFIG["monopoly_threshold"] * 1.5:  # Aggregate violation threshold is stricter
        violations.append(
            f"INV-BIOME-02: node {max_node_id} receiving {max_share:.1%} of total flow "
            f"(threshold: {CONFIG['monopoly_threshold']:.0%})"
        )
    else:
        probes_passed += 1

    return {
        "probes_run": probes_run,
        "probes_passed": probes_passed,
        "violations": violations,
    }


# ===================================================================
# Act-completion artifact generation
# ===================================================================

def generate_act_completion(topology, organisms, environment, act_id, federation_tic=0):
    """Generate act-completion artifact per act-completion-schema.md."""
    health = compute_health(topology, organisms, environment)
    probes = run_invariant_probes(topology, organisms, environment)

    visitors = organisms.get("visitors", [])
    active = sum(1 for v in visitors if v["active"] and not v["departed"] and not v["evicted"])
    departed = sum(1 for v in visitors if v["departed"])
    evicted = sum(1 for v in visitors if v["evicted"])

    standing_dist = collections.Counter(
        v["standing"] for v in visitors if v["active"]
    )

    artifact = {
        "artifact_type": "act_completion",
        "act_id": act_id,
        "visitor_cohort_id": environment.get("cohort_id", "unknown"),
        "biome_cycle": environment.get("cycle", 0),
        "federation_tic": federation_tic,
        "invariant_probes": probes,
        "cohort_state": {
            "visitors_active": active,
            "visitors_departed": departed,
            "visitors_evicted": evicted,
            "standing_distribution": {
                "guest": standing_dist.get("guest", 0),
                "foreign_delegate": standing_dist.get("foreign_delegate", 0),
                "resident": standing_dist.get("resident", 0),
                "citizen": standing_dist.get("citizen", 0),
            },
        },
        "biome_health": health,
        "emitted_at": iso_now(),
        "provenance": {
            "source": "biome_simulation",
            "biome_version": CONFIG["biome_version"],
        },
    }

    # Emit act completion signal
    band = "ALERT" if probes["violations"] else "INFO"
    emit_signal(band, "act_complete", {
        "act_id": act_id,
        "biome_cycle": environment.get("cycle", 0),
        "probes_passed": probes["probes_passed"],
        "probes_run": probes["probes_run"],
        "violations": probes["violations"],
    })

    return artifact


# ===================================================================
# Seasonal transition
# ===================================================================

def check_seasonal_transition(environment, prev_season):
    """Check if season changed and emit transition artifact if so."""
    cycle = environment.get("cycle", 0)
    new_season = get_current_season(cycle)
    if new_season != prev_season:
        environment["season"] = new_season
        multipliers = get_season_multipliers(new_season)
        environment["resource_multiplier"] = multipliers["nutrient_flow_rate"]
        environment["growth_rate"] = multipliers["node_growth_rate"]
        environment["pruning_pressure"] = multipliers["pruning_aggressiveness"]

        # Write seasonal transition artifact
        os.makedirs(SEASONAL_DIR, exist_ok=True)
        gen = environment.get("generation", 1)
        artifact = {
            "generation": gen,
            "season": new_season,
            "transition_cycle": cycle,
            "previous_season": prev_season,
            "multipliers_applied": multipliers,
            "biome_health_at_transition": {},  # Filled by caller
            "active_visitors": len([1]),  # Placeholder
            "timestamp": iso_now(),
        }
        path = os.path.join(SEASONAL_DIR, f"gen-{gen}-{new_season}.json")
        atomic_write_json(path, artifact)

        # Emit signal
        emit_signal("INFO", "seasonal_transition", {
            "generation": gen,
            "from_season": prev_season,
            "to_season": new_season,
            "cycle": cycle,
        })

        return new_season
    return None


# ===================================================================
# Update node metadata after edge changes
# ===================================================================

def recompute_node_metadata(topology):
    """Recompute connection_count and strategy_diversity from current edges."""
    outbound, _ = build_adjacency(topology)
    node_index = build_node_index(topology)
    for node in topology["nodes"]:
        nid = node["node_id"]
        edges = outbound.get(nid, [])
        node["connection_count"] = len(edges)
        type_dist = collections.Counter(e["edge_type"] for e in edges)
        node["edge_type_distribution"] = {t: type_dist.get(t, 0) for t in EDGE_TYPES}
        node["strategy_diversity"] = shannon_entropy(node["edge_type_distribution"])


# ===================================================================
# Core cycle execution
# ===================================================================

def advance_cycle(topology, organisms, environment):
    """Advance the biome by one cycle. Returns cycle summary dict."""
    prev_cycle = environment.get("cycle", 0)
    new_cycle = prev_cycle + 1
    topology["cycle"] = new_cycle
    organisms["cycle"] = new_cycle
    environment["cycle"] = new_cycle

    # Determine act
    act = get_current_act(new_cycle)
    prev_act = environment.get("act")
    environment["act"] = act

    # Check seasonal transition
    prev_season = environment.get("season", "spring")
    season_change = check_seasonal_transition(environment, prev_season)

    summary = {
        "cycle": new_cycle,
        "act": act,
        "season": environment["season"],
        "season_changed": season_change is not None,
        "act_changed": act != prev_act,
        "prev_act": prev_act,
    }

    # --- ACT-SPECIFIC PHYSICS ---

    # Step 1: Resource flow (all acts)
    execute_resource_flow(topology, environment)

    # Step 1b: Emit interaction records for edges with non-zero flow
    for e in topology["edges"]:
        if e.get("flow", 0) > 0:
            # Map non-canonical edge types (seed edges) to canonical interaction type
            itype = e["edge_type"] if e["edge_type"] in EDGE_TYPES else "exchange"
            emit_edge_interactions(
                e["source_node"], e["target_node"], itype,
                new_cycle, e["edge_id"],
                event_type="resource_flow", flow=e["flow"],
                act=act, season=environment.get("season"),
            )

    # Step 2: Depletion check (INV-BIOME-01)
    newly_depleted = enforce_energy_conservation(topology, build_node_index(topology))
    summary["newly_depleted"] = len(newly_depleted)

    # Step 3: Depletion pruning
    dep_pruned, dep_recovered = prune_depleted_edges(topology, newly_depleted)
    summary["depletion_pruned"] = dep_pruned

    # Step 4: Act II viability pruning
    viability_pruned = 0
    viability_recovered = 0.0
    if act in ("act_2",):
        viability_pruned, viability_recovered = prune_unviable_edges(topology, environment)
    summary["viability_pruned"] = viability_pruned

    # Step 5: New connections (Acts I-II)
    new_connections = 0
    if act in ("act_1", "act_2"):
        new_connections = attempt_new_connections(topology, environment)
    summary["new_connections"] = new_connections

    # Step 5b: Loneliness bridges — intervene for isolated nodes
    loneliness_bridges = attempt_loneliness_bridges(topology, environment)
    summary["loneliness_bridges"] = loneliness_bridges

    # Step 6: Bond formation (Act III)
    new_bonds = 0
    if act == "act_3":
        new_bonds = attempt_bond_formation(topology, organisms, environment)
    summary["new_bonds"] = new_bonds

    # Step 7: Bond health update (Acts III-IV)
    bond_signals = []
    if act in ("act_3", "act_4"):
        bond_signals = update_bond_health(organisms, environment)
    summary["bond_signals"] = len(bond_signals)

    # Step 8: Soredium maturation (Act IV)
    matured = 0
    if act == "act_4":
        matured = mature_bonds(organisms, environment)
    summary["bonds_matured"] = matured

    # Step 9: Postcard generation (Act IV, final cycle)
    postcards = []
    if act == "act_4" and new_cycle == ACTS["act_4"]["end"]:
        postcards = generate_postcards(topology, organisms, environment)
    summary["postcards_generated"] = len(postcards)

    # Recompute node metadata
    recompute_node_metadata(topology)

    # Compute health
    health = compute_health(topology, organisms, environment)
    summary["health"] = health

    # Check health signals
    health_signals = check_health_signals(health, environment)
    summary["health_signals"] = len(health_signals)

    # Update seasonal transition artifact with health data if season changed
    if season_change:
        gen = environment.get("generation", 1)
        path = os.path.join(SEASONAL_DIR, f"gen-{gen}-{environment['season']}.json")
        if os.path.isfile(path):
            with open(path, "r") as f:
                artifact = json.load(f)
            artifact["biome_health_at_transition"] = health
            artifact["active_visitors"] = sum(
                1 for v in organisms["visitors"]
                if v["active"] and not v["departed"] and not v["evicted"]
            )
            atomic_write_json(path, artifact)

    # --- ACT BOUNDARY HANDLING ---
    act_completion = None
    snapshot_path = None
    if summary["act_changed"] and prev_act is not None:
        # Generate act-completion artifact for the completed act
        act_completion = generate_act_completion(
            topology, organisms, environment, prev_act, federation_tic=0
        )
        # Save snapshot
        snapshot_path = save_snapshot(topology, organisms, environment, prev_act, federation_tic=0)
        summary["act_completion"] = act_completion
        summary["snapshot_path"] = snapshot_path

    # Also handle the final cycle — Act IV completion
    if new_cycle == ACTS["act_4"]["end"]:
        act_completion = generate_act_completion(
            topology, organisms, environment, "act_4", federation_tic=0
        )
        snapshot_path = save_snapshot(topology, organisms, environment, "act_4", federation_tic=0)
        summary["act_completion"] = act_completion
        summary["snapshot_path"] = snapshot_path

    # Persist state
    save_state(topology, organisms, environment)

    # Step 10: Trust progression — compute trust scores and check promotions
    # Runs after save_state so standing-engine reads committed interaction data.
    try:
        import importlib.util
        _tpc_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "trust-progression-cycle.py")
        if os.path.isfile(_tpc_path):
            _tpc_spec = importlib.util.spec_from_file_location(
                "trust_progression_cycle", _tpc_path)
            _tpc = importlib.util.module_from_spec(_tpc_spec)
            _tpc_spec.loader.exec_module(_tpc)
            trust_results = _tpc.run_trust_progression(verbose=False)
            summary["trust_progression"] = {
                "visitors_processed": trust_results["visitors_processed"],
                "promotions": len(trust_results["promotions"]),
                "pending_review": len(trust_results["pending_review"]),
                "errors": len(trust_results["errors"]),
            }
            if trust_results["promotions"]:
                for p in trust_results["promotions"]:
                    print(f"  [STANDING] {p['entity_id']}: {p['from']} → {p['to']} "
                          f"(trust={p['trust_score']:.4f})")
        else:
            summary["trust_progression"] = {"skipped": "trust-progression-cycle.py not found"}
    except Exception as e:
        summary["trust_progression"] = {"error": str(e)}

    return summary


# ===================================================================
# CLI entry points
# ===================================================================

def run_cycle():
    """Advance one biome cycle."""
    topology, organisms, environment = load_state()
    cycle = environment.get("cycle", 0)

    if cycle >= 50:
        print("[BIOME] Generation complete (cycle 50). Seed a new generation to continue.")
        return

    if cycle == 0 and not topology["nodes"]:
        print("[BIOME] No topology seeded. Run with --seed first.")
        return

    summary = advance_cycle(topology, organisms, environment)
    _print_cycle_summary(summary)


def run_act():
    """Run the current act to completion."""
    topology, organisms, environment = load_state()
    cycle = environment.get("cycle", 0)

    if cycle >= 50:
        print("[BIOME] Generation complete (cycle 50).")
        return

    if cycle == 0 and not topology["nodes"]:
        print("[BIOME] No topology seeded. Run with --seed first.")
        return

    current_act = get_current_act(cycle + 1) or get_current_act(cycle) or "act_1"
    act_end = ACTS[current_act]["end"]
    print(f"[BIOME] Running {current_act} ({ACTS[current_act]['name']}) "
          f"from cycle {cycle + 1} to {act_end}")

    while environment.get("cycle", 0) < act_end:
        summary = advance_cycle(topology, organisms, environment)
        _print_cycle_summary(summary, compact=True)

    print(f"[BIOME] {current_act} complete at cycle {environment['cycle']}")
    health = compute_health(topology, organisms, environment)
    _print_health(health, environment)


def run_simulate():
    """Run a full 50-cycle generation."""
    topology, organisms, environment = load_state()

    if not topology["nodes"]:
        print("[BIOME] No topology seeded. Run with --seed first.")
        return

    start_cycle = environment.get("cycle", 0)
    print(f"[BIOME] Running full generation from cycle {start_cycle + 1} to 50")

    while environment.get("cycle", 0) < 50:
        summary = advance_cycle(topology, organisms, environment)
        cycle = summary["cycle"]
        # Print act transitions
        if summary.get("act_changed"):
            print(f"  --- Act boundary: {summary['prev_act']} -> {summary['act']} ---")
        if summary.get("season_changed"):
            print(f"  --- Season change: -> {summary['season']} ---")
        # Compact progress every 5 cycles
        if cycle % 5 == 0 or cycle == 50:
            _print_cycle_summary(summary, compact=True)

    print("\n[BIOME] Generation complete.")
    health = compute_health(topology, organisms, environment)
    _print_health(health, environment)

    # Print postcard summary
    postcards = [v.get("postcard") for v in organisms.get("visitors", [])
                 if v.get("postcard") is not None]
    if postcards:
        mature_count = sum(1 for p in postcards
                           if any(s["maturation_state"] == "mature"
                                  for s in p.get("bond_soredium", [])))
        print(f"\n  Postcards generated: {len(postcards)}")
        print(f"  With mature soredium (graduated): {mature_count}")
        rational_flags = sum(1 for p in postcards if p.get("rationalization_flag"))
        print(f"  Rationalization flags: {rational_flags}")


def show_health():
    """Print current health monitors."""
    topology, organisms, environment = load_state()
    health = compute_health(topology, organisms, environment)
    _print_health(health, environment)


def show_status():
    """Print current state summary."""
    topology, organisms, environment = load_state()
    cycle = environment.get("cycle", 0)
    act = environment.get("act", get_current_act(cycle) if cycle > 0 else "pre-seed")
    season = environment.get("season", "spring")

    print(f"[BIOME STATUS]")
    print(f"  Cycle:      {cycle}/50")
    print(f"  Act:        {act} ({ACTS.get(act, {}).get('name', 'N/A')})")
    print(f"  Season:     {season}")
    print(f"  Generation: {environment.get('generation', 1)}")
    print(f"  Cohort:     {environment.get('cohort_id', 'N/A')}")
    print(f"  Nodes:      {len(topology.get('nodes', []))}")
    print(f"  Edges:      {len(topology.get('edges', []))}")

    visitors = organisms.get("visitors", [])
    active = sum(1 for v in visitors if v.get("active") and not v.get("departed") and not v.get("evicted"))
    bonds = organisms.get("bonds", [])
    active_bonds = sum(1 for b in bonds if b.get("bond_status") in ("forming", "active", "mature"))
    print(f"  Visitors:   {active} active / {len(visitors)} total")
    print(f"  Bonds:      {active_bonds} active / {len(bonds)} total")

    if cycle > 0:
        health = compute_health(topology, organisms, environment)
        _print_health(health, environment)


# ===================================================================
# Display helpers
# ===================================================================

def _print_cycle_summary(summary, compact=False):
    """Print a cycle execution summary."""
    if compact:
        parts = [f"c{summary['cycle']:>2}"]
        parts.append(f"{summary['act']}")
        parts.append(f"s={summary['season'][:2]}")
        h = summary.get("health", {})
        parts.append(f"nf={h.get('nutrient_flow', 0):.2f}")
        parts.append(f"cn={h.get('network_connectivity', 0):.2f}")
        parts.append(f"di={h.get('diversity_index', 0):.2f}")
        parts.append(f"ms={h.get('monopoly_score', 0):.2f}")
        if summary.get("new_connections"):
            parts.append(f"+{summary['new_connections']}e")
        if summary.get("depletion_pruned") or summary.get("viability_pruned"):
            parts.append(f"-{summary.get('depletion_pruned', 0) + summary.get('viability_pruned', 0)}e")
        if summary.get("new_bonds"):
            parts.append(f"+{summary['new_bonds']}b")
        if summary.get("bonds_matured"):
            parts.append(f"mat={summary['bonds_matured']}")
        if summary.get("postcards_generated"):
            parts.append(f"pc={summary['postcards_generated']}")
        print(f"  {' | '.join(parts)}")
    else:
        print(f"\n[BIOME] Cycle {summary['cycle']} ({summary['act']} / {summary['season']})")
        h = summary.get("health", {})
        print(f"  Health: nf={h.get('nutrient_flow', 0):.3f} "
              f"conn={h.get('network_connectivity', 0):.3f} "
              f"div={h.get('diversity_index', 0):.3f} "
              f"mono={h.get('monopoly_score', 0):.3f} "
              f"mut={h.get('mutualism_ratio', 0):.3f}")
        print(f"  Depleted: +{summary.get('newly_depleted', 0)} | "
              f"Pruned: dep={summary.get('depletion_pruned', 0)} "
              f"viab={summary.get('viability_pruned', 0)} | "
              f"New edges: {summary.get('new_connections', 0)} | "
              f"New bonds: {summary.get('new_bonds', 0)}")
        if summary.get("act_changed"):
            print(f"  >>> ACT BOUNDARY: {summary['prev_act']} -> {summary['act']}")
        if summary.get("season_changed"):
            print(f"  >>> SEASON: -> {summary['season']}")
        if summary.get("act_completion"):
            ac = summary["act_completion"]
            print(f"  >>> Act completion artifact: "
                  f"{ac['invariant_probes']['probes_passed']}/{ac['invariant_probes']['probes_run']} probes passed")
        if summary.get("snapshot_path"):
            print(f"  >>> Snapshot: {summary['snapshot_path']}")
        if summary.get("health_signals"):
            print(f"  >>> {summary['health_signals']} health signal(s) emitted")


def _print_health(health, environment):
    """Print health monitors with threshold comparison."""
    act = environment.get("act", "act_1")
    print(f"\n  [Health Monitors]")
    print(f"    nutrient_flow:        {health['nutrient_flow']:.4f}  "
          f"(threshold: > {CONFIG['health_nutrient_flow_low']})")
    print(f"    network_connectivity: {health['network_connectivity']:.4f}  "
          f"(threshold: {CONFIG['health_connectivity_low']} - {CONFIG['health_connectivity_high']})")
    print(f"    diversity_index:      {health['diversity_index']:.4f}  "
          f"(threshold: > {math.log2(CONFIG['health_diversity_low_log2k']):.3f})")
    print(f"    monopoly_score:       {health['monopoly_score']:.4f}  "
          f"(threshold: < {CONFIG['health_monopoly_high']})")
    if act in ("act_3", "act_4"):
        print(f"    mutualism_ratio:      {health['mutualism_ratio']:.4f}  "
              f"(threshold: > {CONFIG['health_mutualism_low']})")


# ===================================================================
# Main
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Biome simulation engine — Physarum/Lichen network simulation",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cycle", action="store_true", help="Advance one biome cycle")
    group.add_argument("--act", action="store_true", help="Run current act to completion")
    group.add_argument("--simulate", action="store_true", help="Run full 50-cycle generation")
    group.add_argument("--seed", action="store_true", help="Seed initial topology")
    group.add_argument("--health", action="store_true", help="Print current health monitors")
    group.add_argument("--status", action="store_true", help="Print current state summary")

    parser.add_argument("--visitors", type=int, default=8,
                        help="Number of visitors to seed (default: 8)")
    parser.add_argument("--cohort-id", type=str, default=None,
                        help="Cohort identifier for seeding")
    parser.add_argument("--federations", type=str, nargs="+",
                        default=["federation_alpha", "federation_beta"],
                        help="Federation IDs for cross-federation pairing")

    args = parser.parse_args()

    if args.seed:
        seed_biome(
            num_visitors=args.visitors,
            cohort_id=args.cohort_id,
            federation_ids=args.federations,
        )
    elif args.cycle:
        run_cycle()
    elif args.act:
        run_act()
    elif args.simulate:
        run_simulate()
    elif args.health:
        show_health()
    elif args.status:
        show_status()


if __name__ == "__main__":
    main()
