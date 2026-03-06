#!/usr/bin/env python3
"""
CGG Uninstall — reverse install side effects cleanly.

Removes CGG-installed runtime surfaces (skills, agents, hooks) from the
project's .claude/ directory. Does NOT remove user-authored governance
surfaces unless explicitly flagged.

Usage:
    python3 cgg-uninstall.py full        [--project-dir PATH] [--dry-run]
    python3 cgg-uninstall.py runtime-only [--project-dir PATH] [--dry-run]
    python3 cgg-uninstall.py full --include-governance --include-history [--dry-run]
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root


# ---------------------------------------------------------------------------
# Surface definitions
# ---------------------------------------------------------------------------

def get_runtime_surfaces(zone_root):
    """Surfaces installed by CGG runtime (skills, agents, hooks)."""
    claude_dir = os.path.join(zone_root, ".claude")
    surfaces = []

    # Skills
    for skill_dir in ["cadence", "review", "siren", "init-governance"]:
        skill_path = os.path.join(claude_dir, "skills", skill_dir)
        if os.path.isdir(skill_path):
            surfaces.append({
                "path": skill_path,
                "type": "skill_dir",
                "name": f"skills/{skill_dir}/",
            })

    # Agents
    for agent_file in ["mogul.md", "ripple-assessor.md", "pattern-curator.md", "ladder-auditor.md"]:
        agent_path = os.path.join(claude_dir, "agents", agent_file)
        if os.path.isfile(agent_path):
            surfaces.append({
                "path": agent_path,
                "type": "agent_file",
                "name": f"agents/{agent_file}",
            })

    # Hooks
    for hook_file in ["session-restore-patch.sh", "cgg-gate.sh", "posttool-microscan.sh"]:
        hook_path = os.path.join(claude_dir, "hooks", hook_file)
        if os.path.isfile(hook_path):
            surfaces.append({
                "path": hook_path,
                "type": "hook_file",
                "name": f"hooks/{hook_file}",
            })

    # Microscan staging
    staging = os.path.join(zone_root, "audit-logs", ".microscan-staging.jsonl")
    if os.path.isfile(staging):
        surfaces.append({
            "path": staging,
            "type": "staging_file",
            "name": "audit-logs/.microscan-staging.jsonl",
        })

    return surfaces


def get_governance_surfaces(zone_root):
    """User-authored governance surfaces (only removed with --include-governance)."""
    surfaces = []
    for gov_file in ["CLAUDE.md", "MEMORY.md"]:
        path = os.path.join(zone_root, gov_file)
        if os.path.isfile(path):
            surfaces.append({
                "path": path,
                "type": "governance_file",
                "name": gov_file,
            })

    # Auto-memory
    project_key = zone_root.replace("/", "-")
    auto_memory = os.path.join(
        os.path.expanduser("~"), ".claude", "projects", project_key, "memory"
    )
    if os.path.isdir(auto_memory):
        surfaces.append({
            "path": auto_memory,
            "type": "auto_memory_dir",
            "name": f"~/.claude/projects/{project_key}/memory/",
        })

    return surfaces


def get_history_surfaces(zone_root):
    """Audit logs (only removed with --include-history)."""
    al_path = os.path.join(zone_root, "audit-logs")
    surfaces = []
    if os.path.isdir(al_path):
        surfaces.append({
            "path": al_path,
            "type": "audit_logs_dir",
            "name": "audit-logs/",
        })
    return surfaces


def get_zone_surfaces(zone_root):
    """Zone config (only removed with --include-zone)."""
    surfaces = []
    for zone_file in [".ticzone", ".ticignore"]:
        path = os.path.join(zone_root, zone_file)
        if os.path.isfile(path):
            surfaces.append({
                "path": path,
                "type": "zone_config",
                "name": zone_file,
            })
    return surfaces


# ---------------------------------------------------------------------------
# Removal
# ---------------------------------------------------------------------------

def remove_surface(surface, dry_run=False):
    """Remove a single surface. Returns True if removed."""
    path = surface["path"]

    if dry_run:
        return True

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.isfile(path):
            os.remove(path)
        return True
    except OSError as e:
        print(f"  [ERROR] Could not remove {path}: {e}")
        return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_uninstall(zone_root, mode, include_governance=False,
                  include_history=False, include_zone=False, dry_run=False):
    """Execute uninstall."""
    surfaces_to_remove = []

    # Always include runtime surfaces
    surfaces_to_remove.extend(get_runtime_surfaces(zone_root))

    # Full mode includes governance/history/zone only with flags
    if mode == "full":
        if include_governance:
            surfaces_to_remove.extend(get_governance_surfaces(zone_root))
        if include_history:
            surfaces_to_remove.extend(get_history_surfaces(zone_root))
        if include_zone:
            surfaces_to_remove.extend(get_zone_surfaces(zone_root))

    if not surfaces_to_remove:
        print("No CGG-installed surfaces found to remove.")
        return

    # Report
    print("=" * 60)
    print(f"CGG UNINSTALL — {'DRY RUN' if dry_run else mode.upper()}")
    print("=" * 60)
    print(f"  Zone root: {zone_root}")
    print(f"  Mode:      {mode}")
    print(f"  Dry run:   {dry_run}")
    print()

    removed_count = 0
    for surface in surfaces_to_remove:
        action = "[would remove]" if dry_run else "[removing]"
        print(f"  {action} {surface['name']} ({surface['type']})")
        if remove_surface(surface, dry_run=dry_run):
            removed_count += 1

    print()
    verb = "would remove" if dry_run else "removed"
    print(f"  {removed_count} surfaces {verb}")

    # Report what was preserved
    if mode == "runtime-only" or (mode == "full" and not all([include_governance, include_history, include_zone])):
        print()
        print("  PRESERVED (use flags to include):")
        if not include_governance:
            gov = get_governance_surfaces(zone_root)
            if gov:
                for s in gov:
                    print(f"    {s['name']} (--include-governance)")
        if not include_history:
            hist = get_history_surfaces(zone_root)
            if hist:
                for s in hist:
                    print(f"    {s['name']} (--include-history)")
        if not include_zone:
            zone = get_zone_surfaces(zone_root)
            if zone:
                for s in zone:
                    print(f"    {s['name']} (--include-zone)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CGG Uninstall — reverse install side effects"
    )
    parser.add_argument("mode", choices=["full", "runtime-only", "dry-run"],
                        help="full: all CGG surfaces. runtime-only: skills/agents/hooks only. dry-run: report only.")
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be removed without removing")
    parser.add_argument("--include-governance", action="store_true",
                        help="Also remove CLAUDE.md, MEMORY.md, auto-memory")
    parser.add_argument("--include-history", action="store_true",
                        help="Also remove audit-logs/")
    parser.add_argument("--include-zone", action="store_true",
                        help="Also remove .ticzone, .ticignore")
    args = parser.parse_args()

    zone_root = args.project_dir or resolve_zone_root()

    # "dry-run" as positional mode is equivalent to full --dry-run
    dry_run = args.dry_run or args.mode == "dry-run"
    mode = "full" if args.mode == "dry-run" else args.mode

    cmd_uninstall(
        zone_root,
        mode=mode,
        include_governance=args.include_governance,
        include_history=args.include_history,
        include_zone=args.include_zone,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    main()
