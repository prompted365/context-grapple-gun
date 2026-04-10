#!/usr/bin/env python3
"""
seed-first-cohort.py — Seed the first controlled visitor cohort.

Asymmetric 6-visitor shape for observability:
  - 3 federations (alpha, beta, gamma) for cross-fed pairing diversity
  - Cluster distribution: 3 in sector 0, 2 in sector 2, 1 in sector 4
  - Named test entities for traceability
  - All enter at guest standing via Docks handler

This is a controlled activation, not demand estimation.
The asymmetric shape ensures all visual treatments and progression
mechanics are observable from cycle 1.

Usage:
    python3 seed-first-cohort.py              # seed + register all 6
    python3 seed-first-cohort.py --dry-run    # print plan without executing
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from zone_root import resolve_zone_root, audit_logs_path, load_ticzone
from lib.atomic_append import atomic_append_jsonl, atomic_write_json

# ---------------------------------------------------------------------------
# Cohort definition — the deliberate shape
# ---------------------------------------------------------------------------

COHORT_ID = "cohort_first_controlled_tic130"

# 6 visitors, 3 federations, asymmetric sector placement
VISITORS = [
    # Sector 0 cluster (3 visitors — dense interaction zone)
    {
        "name": "Artemis",
        "federation": "federation_alpha",
        "sector": 0,
        "role": "explorer",       # high behavioral diversity potential
        "notes": "Dense cluster member. Should form early connections in Act I.",
    },
    {
        "name": "Basalt",
        "federation": "federation_beta",
        "sector": 0,
        "role": "builder",        # creation-focused
        "notes": "Dense cluster, different federation. Cross-fed pairing candidate in Act III.",
    },
    {
        "name": "Cinder",
        "federation": "federation_gamma",
        "sector": 0,
        "role": "observer",       # governance-focused
        "notes": "Dense cluster, third federation. Tests 3-federation dynamics.",
    },

    # Sector 2 pair (2 visitors — moderate density)
    {
        "name": "Dune",
        "federation": "federation_alpha",
        "sector": 2,
        "role": "collaborator",   # exchange + teaching
        "notes": "Paired with Echo. Same federation as Artemis — tests intra-fed dynamics.",
    },
    {
        "name": "Echo",
        "federation": "federation_beta",
        "sector": 2,
        "role": "defender",       # defense + reflection
        "notes": "Paired with Dune. Cross-fed pair. Tests pressure response in Act II.",
    },

    # Sector 4 isolate (1 visitor — sparse, tests isolation dynamics)
    {
        "name": "Flint",
        "federation": "federation_gamma",
        "sector": 4,
        "role": "pioneer",        # must reach toward other sectors
        "notes": "Alone in sector. Must form long-range connections or face pruning.",
    },
]

# Sector angular positions (5 sectors, biome annulus r=23-35)
import math
SECTOR_ANGLE = 2 * math.pi / 5
BIOME_R_MID = 29  # midpoint of annulus

def visitor_position(sector, index_in_sector, total_in_sector):
    """Compute world-space position within a biome sector."""
    base_angle = sector * SECTOR_ANGLE + SECTOR_ANGLE / 2
    # Spread within sector
    spread = SECTOR_ANGLE * 0.3
    if total_in_sector > 1:
        offset = (index_in_sector / (total_in_sector - 1) - 0.5) * spread
    else:
        offset = 0
    angle = base_angle + offset
    r = BIOME_R_MID + (index_in_sector % 2) * 3 - 1.5  # stagger radially
    x = r * math.cos(angle)
    z = r * math.sin(angle)
    y = 2.5  # just above biome floor
    return round(x, 2), round(y, 2), round(z, 2)


def build_cohort():
    """Build the full cohort data structures."""
    # Count visitors per sector for position calculation
    sector_counts = {}
    sector_indices = {}
    for v in VISITORS:
        s = v["sector"]
        sector_counts[s] = sector_counts.get(s, 0) + 1
        sector_indices[s] = 0

    cohort = []
    for v in VISITORS:
        s = v["sector"]
        idx = sector_indices[s]
        sector_indices[s] += 1
        pos = visitor_position(s, idx, sector_counts[s])

        entity_id = f"ent_visitor_{v['name'].lower()}"
        cohort.append({
            "entity_id": entity_id,
            "visitor_display_name": v["name"],
            "home_federation_id": v["federation"],
            "sector": s,
            "position": {"x": pos[0], "y": pos[1], "z": pos[2]},
            "standing": "guest",
            "role_archetype": v["role"],
            "notes": v["notes"],
            "cohort_id": COHORT_ID,
        })

    return cohort


def seed_biome_state(cohort, zone_root):
    """Write fresh biome state files for Act I with the cohort."""
    al = audit_logs_path(zone_root, load_ticzone(zone_root))
    state_dir = os.path.join(al, "biome", "state")
    os.makedirs(state_dir, exist_ok=True)

    # Archive previous generation
    prev_env_path = os.path.join(state_dir, "environment.json")
    if os.path.exists(prev_env_path):
        snapshot_dir = os.path.join(al, "biome", "snapshots")
        os.makedirs(snapshot_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        for fname in ["environment.json", "topology.json", "organisms.json"]:
            src = os.path.join(state_dir, fname)
            if os.path.exists(src):
                dst = os.path.join(snapshot_dir, f"gen1-archive-{ts}-{fname}")
                os.rename(src, dst)
                print(f"  Archived: {fname} → {os.path.basename(dst)}")

    # Environment: fresh Act I
    environment = {
        "season": "spring",
        "resource_multiplier": 1.0,
        "growth_rate": 1.0,
        "pruning_pressure": 1.0,
        "cycle": 0,
        "act": "act_1",
        "generation": 2,
        "cohort_id": COHORT_ID,
        "seed_timestamp": datetime.now(timezone.utc).isoformat(),
        "seed_visitor_count": len(cohort),
        "seed_shape": "asymmetric_6",
    }
    atomic_write_json(os.path.join(state_dir, "environment.json"), environment)

    # Topology: initial sparse graph
    edge_types = ["resource_flow", "information_exchange", "trust_signal"]
    nodes = []
    edges = []
    for c in cohort:
        nodes.append({
            "node_id": c["entity_id"],
            "resource_level": 20.0,
            "connection_count": 0,
            "edge_type_distribution": {t: 0 for t in edge_types},
            "strategy_diversity": 0.0,
            "depletion_state": None,
            "act_entry_resources": 20.0,
            "is_source": c["sector"] == 0,  # sector 0 cluster are source nodes
            "containment_level": 0,
            "anomaly_cycles": 0,
            "position": c["position"],
            "sector": c["sector"],
        })

    # Initial edges: within-sector connections only (sparse start)
    sector_nodes = {}
    for n in nodes:
        s = n["sector"]
        sector_nodes.setdefault(s, []).append(n["node_id"])

    for s, nids in sector_nodes.items():
        for i in range(len(nids)):
            for j in range(i + 1, len(nids)):
                edges.append({
                    "source": nids[i],
                    "target": nids[j],
                    "weight": 1.0,
                    "edge_type": edge_types[0],
                    "age": 0,
                    "resource_flow": 0.0,
                })

    topology = {
        "nodes": nodes,
        "edges": edges,
        "generation": 2,
        "cohort_id": COHORT_ID,
    }
    atomic_write_json(os.path.join(state_dir, "topology.json"), topology)

    # Organisms: visitor records
    visitors_data = []
    for c in cohort:
        visitors_data.append({
            "visitor_id": c["entity_id"],
            "home_federation_id": c["home_federation_id"],
            "standing": "guest",
            "active": True,
            "departed": False,
            "evicted": False,
            "bonds": [],
            "pruning_record": {
                "edges_pruned": 0,
                "edges_pruned_voluntary": 0,
            },
            "soredium_state": None,
            "postcard_generated": False,
            "position": c["position"],
            "sector": c["sector"],
            "role_archetype": c["role_archetype"],
            "display_name": c["visitor_display_name"],
            "cohort_id": COHORT_ID,
        })

    organisms = {
        "visitors": visitors_data,
        "generation": 2,
        "cohort_id": COHORT_ID,
    }
    atomic_write_json(os.path.join(state_dir, "organisms.json"), organisms)

    return environment, topology, organisms


def register_in_visitor_registry(cohort, zone_root):
    """Append visitor records to the visitor registry."""
    al = audit_logs_path(zone_root, load_ticzone(zone_root))
    registry_path = os.path.join(al, "visitors", "registry.jsonl")

    for c in cohort:
        entry = {
            "entity_id": c["entity_id"],
            "visitor_display_name": c["visitor_display_name"],
            "home_federation_id": c["home_federation_id"],
            "standing": "guest",
            "admission_timestamp": datetime.now(timezone.utc).isoformat(),
            "probes_passed": 4,  # controlled admission — all probes pass
            "ingress_lane": "tailscale_serve",
            "tvi_tier": "native",
            "cohort_id": COHORT_ID,
            "admission_type": "controlled_seed",
            "role_archetype": c["role_archetype"],
        }
        atomic_append_jsonl(registry_path, entry)

    return len(cohort)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Seed first controlled cohort")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    args = parser.parse_args()

    zone_root = resolve_zone_root(SCRIPT_DIR)
    cohort = build_cohort()

    print(f"=== First Controlled Cohort — {COHORT_ID} ===")
    print(f"Shape: asymmetric 6 (3-2-1 across sectors 0/2/4)")
    print(f"Federations: alpha, beta, gamma")
    print()

    for c in cohort:
        pos = c["position"]
        print(f"  {c['visitor_display_name']:10s}  {c['entity_id']:35s}  "
              f"fed={c['home_federation_id'].split('_')[1]:5s}  "
              f"sector={c['sector']}  "
              f"pos=({pos['x']:6.1f}, {pos['y']:4.1f}, {pos['z']:6.1f})  "
              f"role={c['role_archetype']}")

    print()

    if args.dry_run:
        print("[DRY RUN] No state changes made.")
        return

    print("Seeding biome state (fresh Act I, generation 2)...")
    env, topo, org = seed_biome_state(cohort, zone_root)
    print(f"  Environment: cycle=0, act=act_1, season=spring")
    print(f"  Topology: {len(topo['nodes'])} nodes, {len(topo['edges'])} edges")
    print(f"  Organisms: {len(org['visitors'])} visitors")
    print()

    print("Registering in visitor registry...")
    count = register_in_visitor_registry(cohort, zone_root)
    print(f"  {count} visitors registered.")
    print()

    print("=== Cohort seeded. Ready for biome-cadence-runner.sh --cycles 1 ===")


if __name__ == "__main__":
    main()
