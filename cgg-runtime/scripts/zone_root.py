#!/usr/bin/env python3
"""
Zone root resolution — shared utility for all CGG governance scripts.

Resolution chain:
  1. CLAUDE_PROJECT_DIR env var (if set)
  2. Walk upward from cwd to find .ticzone
  3. git rev-parse --show-toplevel (repo fallback)
  4. cwd (last resort, with warning)

Also provides .ticzone config loading, .cgg/subsystems.json loading,
and audit-logs path resolution.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def resolve_zone_root(start_dir=None):
    """Find the governance root by walking up to find .ticzone.

    Returns absolute path to the zone root directory.
    """
    start = start_dir or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    start = os.path.abspath(start)

    # Walk up from start to find .ticzone
    d = start
    while d != os.path.dirname(d):  # stop at filesystem root
        if os.path.isfile(os.path.join(d, ".ticzone")):
            return d
        d = os.path.dirname(d)

    # Fallback: git repo root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
            cwd=start,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Last resort
    print("[CGG WARNING] No .ticzone found — falling back to cwd", file=sys.stderr)
    return start


def load_ticzone(zone_root):
    """Load .ticzone config from zone root. Returns dict (empty on failure)."""
    ticzone_path = os.path.join(zone_root, ".ticzone")
    if not os.path.isfile(ticzone_path):
        return {}
    try:
        return json.loads(Path(ticzone_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_subsystems_config(zone_root):
    """Load .cgg/subsystems.json from zone root. Returns dict with defaults."""
    config_path = os.path.join(zone_root, ".cgg", "subsystems.json")
    default = {"subsystems": {}, "test_paths": {}}
    if not os.path.isfile(config_path):
        return default
    try:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        return {
            "subsystems": data.get("subsystems", {}),
            "test_paths": data.get("test_paths", {}),
        }
    except (json.JSONDecodeError, OSError):
        return default


def audit_logs_path(zone_root, ticzone_config=None):
    """Resolve the audit-logs directory path from zone root + .ticzone config.

    Always resolved relative to zone root, never cwd.
    """
    if ticzone_config is None:
        ticzone_config = load_ticzone(zone_root)
    rel = ticzone_config.get("audit_logs_path", "audit-logs")
    return os.path.join(zone_root, rel)


def signal_governance(ticzone_config):
    """Extract signal governance params with defaults."""
    sg = ticzone_config.get("signal_governance", {})
    return {
        "hearing_threshold": sg.get("hearing_threshold", 40),
        "decay_rate_per_tic": sg.get("decay_rate_per_tic", 2),
        "warrant_eligible_kinds": set(sg.get("warrant_eligible_kinds", ["BEACON", "TENSION"])),
        "primitive_audibility_mode": sg.get("primitive_audibility_mode", "threshold_floor"),
        "zombie_guard_mode": sg.get("zombie_guard_mode", "clamp_and_warn"),
    }


# Rung topology markers — ordered from lowest (nearest) to highest.
#
# LEGACY SEMANTICS NOTE (tic 211, see audit-logs/governance/zone-marker-utilization-audit-tic211.md
# and audit-logs/governance/rung-layering-audit-tic211.md F4): `.ticzone` is mapped to "site"
# rung here for historical reasons, but `.ticzone` is operationally a zone *configuration* file
# (timezone, bands, muffling-per-hop) that lives at multiple rungs — it can appear at federation
# root (canonical/.ticzone) as well as site sub-zones (e.g., stage/.ticzone). When a single
# directory carries both `.ticzone` and a higher-rung marker (e.g., canonical/ has both
# `.ticzone` and `.federation-root`), `resolve_rung_position()` returns it under both labels
# in the topology dict. The canonical resolution lives at the consumer side: load_doctrine_chain.py
# applies "highest-rung-wins on path collision" so federation isn't shadowed by site at the
# federation root. Future cleanup (deferred per "lucky alignment is structural drift" CogPR-205)
# would either rename `.ticzone` to a non-rung-marker config file or split the rung-tagging
# concern from the zone-config concern. Until then, consumers must apply collision-aware reads.
RUNG_MARKERS = {
    ".ticzone": "site",
    ".domain-root": "domain",
    ".estate-root": "estate",
    ".federation-root": "federation",
}

# Canonical rung ordering (lowest to highest)
RUNG_ORDER = ["site", "domain", "estate", "federation"]


def resolve_rung_position(start_dir=None):
    """Walk upward from start_dir, detect rung markers, return topology dict.

    Returns dict with current_rung (nearest/lowest marker found relative to
    start_dir) and full topology chain. Never errors — partial/missing
    topology is normal.
    """
    start = start_dir or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    start = os.path.abspath(start)

    topology = {rung: None for rung in RUNG_ORDER}
    nearest_rung = None

    d = start
    while True:
        for marker, rung in RUNG_MARKERS.items():
            marker_path = os.path.join(d, marker)
            if os.path.exists(marker_path):
                # Read marker content for name (falls back to directory name)
                name = os.path.basename(d)
                if os.path.isfile(marker_path):
                    try:
                        content = Path(marker_path).read_text(encoding="utf-8").strip()
                        if content:
                            # If it's JSON (.ticzone), extract name field
                            if marker == ".ticzone":
                                try:
                                    data = json.loads(content)
                                    name = data.get("name", name)
                                except json.JSONDecodeError:
                                    pass
                            else:
                                # Plain sentinel — content is the name if non-empty
                                name = content
                    except OSError:
                        pass

                if topology[rung] is None:
                    topology[rung] = {"path": d, "name": name}
                    if nearest_rung is None:
                        nearest_rung = rung

        # Stop at filesystem root
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent

    # Check for SYSTEM_MAP.md at federation root
    system_map = None
    if topology["federation"] is not None:
        sm_path = os.path.join(topology["federation"]["path"], "SYSTEM_MAP.md")
        if os.path.isfile(sm_path):
            system_map = sm_path

    # Global CLAUDE.md
    global_claude = os.path.expanduser("~/.claude/CLAUDE.md")
    if not os.path.isfile(global_claude):
        global_claude = None

    return {
        "current_rung": nearest_rung or "global",
        "topology": topology,
        "global": global_claude,
        "system_map": system_map,
    }


def birth_topology(start_dir=None):
    """Return compact topology metadata for embedding in JSONL artifacts.

    Calls resolve_rung_position() and distills the result into a flat dict
    suitable for inclusion in CPR entries, signals, mandates, etc.
    """
    rp = resolve_rung_position(start_dir)
    return {
        "birth_rung": rp["current_rung"],
        "birth_scope_path": (rp["topology"].get(rp["current_rung"]) or {}).get("path"),
        "topology_chain": {
            k: v["path"] if v else None for k, v in rp["topology"].items()
        },
    }
