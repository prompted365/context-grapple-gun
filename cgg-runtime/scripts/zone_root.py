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
