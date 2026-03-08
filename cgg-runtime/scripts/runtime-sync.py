#!/usr/bin/env python3
"""
Runtime Sync — compare installed vs canonical CGG surfaces, report/sync.

Detects drift between canonical sources in the CGG submodule and installed
runtime copies in .claude/skills/, .claude/agents/, and hook locations.

On drift detection: emits TENSION signal (warrant-eligible) to signal store.

Invariant: loaded runtime wins — this tool reports drift, does not silently
pretend canonical is active.

Exit codes: 0=success, 1=validation error, 2=IO error, 3=data error.

Usage:
    python3 runtime-sync.py check  [--project-dir PATH] [--json]
    python3 runtime-sync.py diff   [--project-dir PATH] [--json]
    python3 runtime-sync.py sync   [--project-dir PATH]
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, birth_topology


# ---------------------------------------------------------------------------
# Surface registry — canonical source -> installed location
# ---------------------------------------------------------------------------

def build_surface_map(plugin_root, zone_root):
    """Build mapping of canonical -> installed paths for all tracked surfaces."""
    surfaces = []

    # Skills
    skills = [
        ("cadence/SKILL.md", "skills/cadence/SKILL.md"),
        ("review/SKILL.md", "skills/review/SKILL.md"),
        ("siren/SKILL.md", "skills/siren/SKILL.md"),
        ("init-governance/SKILL.md", "skills/init-governance/SKILL.md"),
        ("statusline/SKILL.md", "skills/statusline/SKILL.md"),
    ]
    for canonical_rel, installed_rel in skills:
        surfaces.append({
            "name": f"skill:{canonical_rel.split('/')[0]}",
            "canonical": os.path.join(plugin_root, "cgg-runtime", "skills", canonical_rel),
            "installed": os.path.join(zone_root, ".claude", installed_rel),
            "type": "PROMPT_CODE",
        })

    # Agents
    agents = [
        "mogul.md",
        "ripple-assessor.md",
        "pattern-curator.md",
        "ladder-auditor.md",
    ]
    for agent_file in agents:
        surfaces.append({
            "name": f"agent:{agent_file.replace('.md', '')}",
            "canonical": os.path.join(plugin_root, "cgg-runtime", "agents", agent_file),
            "installed": os.path.join(zone_root, ".claude", "agents", agent_file),
            "type": "PROMPT_CODE",
        })

    # Scripts (zone-root-resolved runtime scripts)
    scripts = [
        "expression-tracker.py",
    ]
    for script_file in scripts:
        surfaces.append({
            "name": f"script:{script_file.replace('.py', '')}",
            "canonical": os.path.join(plugin_root, "cgg-runtime", "scripts", script_file),
            "installed": os.path.join(zone_root, "scripts", script_file),
            "type": "SCRIPT_CODE",
        })

    # Hooks
    hooks = [
        "session-restore-patch.sh",
        "cgg-gate.sh",
    ]
    for hook_file in hooks:
        surfaces.append({
            "name": f"hook:{hook_file.replace('.sh', '')}",
            "canonical": os.path.join(plugin_root, "cgg-runtime", "hooks", hook_file),
            "installed": os.path.join(zone_root, ".claude", "hooks", hook_file),
            "type": "SCRIPT_CODE",
        })

    return surfaces


def find_plugin_root(zone_root):
    """Locate the CGG plugin root directory."""
    candidates = [
        os.path.join(zone_root, "vendor", "context-grapple-gun"),
        os.path.join(zone_root, ".claude", "cgg"),
        os.path.join(os.path.expanduser("~"), ".claude", "cgg"),
    ]
    for c in candidates:
        if os.path.isdir(os.path.join(c, "cgg-runtime")):
            return c
    return None


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def file_hash(path):
    """SHA-256 content hash of a file. Returns None if file doesn't exist."""
    if not os.path.isfile(path):
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare_surface(surface):
    """Compare a single surface. Returns status + hashes."""
    canonical_hash = file_hash(surface["canonical"])
    installed_hash = file_hash(surface["installed"])

    if canonical_hash is None and installed_hash is None:
        status = "both_missing"
    elif canonical_hash is None:
        status = "missing_canonical"
    elif installed_hash is None:
        status = "missing_installed"
    elif canonical_hash == installed_hash:
        status = "synced"
    else:
        status = "drifted"

    return {
        **surface,
        "status": status,
        "canonical_hash": canonical_hash,
        "installed_hash": installed_hash,
    }


def file_diff(path_a, path_b):
    """Simple line-by-line diff summary."""
    try:
        lines_a = Path(path_a).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        lines_a = []
    try:
        lines_b = Path(path_b).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        lines_b = []

    added = 0
    removed = 0
    set_a = set(lines_a)
    set_b = set(lines_b)
    added = len(set_b - set_a)
    removed = len(set_a - set_b)
    return {"added_lines": added, "removed_lines": removed,
            "canonical_lines": len(lines_a), "installed_lines": len(lines_b)}


# ---------------------------------------------------------------------------
# Signal emission
# ---------------------------------------------------------------------------

def emit_drift_signal(zone_root, drifted_surfaces, severity="detected_drift"):
    """Emit a TENSION signal for runtime drift.

    Severity levels:
      detected_drift — drift was found (check mode or pre-sync)
      unresolved_drift — drift remains after sync attempt (escalated)
    """
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    signal_dir = os.path.join(al_path, "signals")
    os.makedirs(signal_dir, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    signal_file = os.path.join(signal_dir, f"{date_str}.jsonl")

    surface_names = [s["name"] for s in drifted_surfaces]
    signal_id = f"sig_{now.strftime('%Y-%m-%dT%H:%MZ')}_{severity}_{len(drifted_surfaces)}"

    # Unresolved drift after sync is more severe
    volume = 60 if severity == "unresolved_drift" else 45

    topo = birth_topology(zone_root)

    signal = {
        "type": "signal",
        "id": signal_id,
        "kind": "TENSION",
        "band": "COGNITIVE",
        "status": "active",
        "volume": volume,
        "max_volume": 100,
        "tick_count": 0,
        "subsystem": "cgg",
        "source": "runtime-sync.py",
        "source_date": date_str,
        "created_at": now.isoformat(),
        "birth_rung": topo["birth_rung"],
        "payload": {
            "summary": f"Runtime {severity.replace('_', ' ')}: {len(drifted_surfaces)} surfaces",
            "severity": severity,
            "surfaces": surface_names,
        },
        "escalation": {
            "warrant_threshold": 70,
        },
        "origin": "deterministic",
    }

    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(str(signal_file), signal)
    except ImportError:
        import fcntl
        lockfile = str(signal_file) + ".lock"
        with open(lockfile, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                with open(signal_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(signal, separators=(",", ":")) + "\n")
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    return signal_id


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_check(surfaces, zone_root, output_json=False):
    """Report sync status for all surfaces. Emits drift hazard on detection."""
    results = [compare_surface(s) for s in surfaces]
    drifted = [r for r in results if r["status"] == "drifted"]
    missing = [r for r in results if r["status"] == "missing_installed"]
    synced = [r for r in results if r["status"] == "synced"]

    # Drift detection itself is a governance hazard — emit on detection,
    # not only on failed sync. The Trip Hazard Invariant requires it.
    signal_id = None
    if drifted:
        signal_id = emit_drift_signal(zone_root, drifted, severity="detected_drift")

    if output_json:
        result = {
            "command": "check",
            "surfaces": [
                {
                    "name": r["name"],
                    "type": r["type"],
                    "status": r["status"],
                    "canonical_hash": r["canonical_hash"],
                    "installed_hash": r["installed_hash"],
                }
                for r in results
            ],
            "summary": {
                "synced": len(synced),
                "drifted": len(drifted),
                "missing": len(missing),
            },
            "signal_emitted": signal_id,
        }
        print(json.dumps(result, indent=2))
        return results

    print("=" * 60)
    print("RUNTIME SYNC CHECK")
    print("=" * 60)

    for r in results:
        status_tag = {
            "synced": "  OK  ",
            "drifted": "DRIFTED",
            "missing_installed": "MISSING",
            "missing_canonical": "NO SRC",
            "both_missing": "ABSENT",
        }.get(r["status"], r["status"])
        print(f"  [{status_tag}] {r['name']:<30} ({r['type']})")

    print()
    print(f"  Synced: {len(synced)}  |  Drifted: {len(drifted)}  |  Missing: {len(missing)}")

    if signal_id:
        print(f"  TENSION signal emitted (detected_drift): {signal_id}")

    return results


def cmd_diff(surfaces, output_json=False):
    """Show diffs for drifted surfaces."""
    results = [compare_surface(s) for s in surfaces]
    drifted = [r for r in results if r["status"] == "drifted"]

    if not drifted:
        if output_json:
            print(json.dumps({"command": "diff", "drifted": []}))
        else:
            print("All surfaces are in sync. No diffs to show.")
        return results

    if output_json:
        diffs = []
        for r in drifted:
            diff_info = file_diff(r["canonical"], r["installed"])
            diffs.append({
                "name": r["name"],
                "type": r["type"],
                "canonical": r["canonical"],
                "installed": r["installed"],
                "canonical_hash": r["canonical_hash"],
                "installed_hash": r["installed_hash"],
                **diff_info,
            })
        print(json.dumps({"command": "diff", "drifted": diffs}, indent=2))
        return results

    print("=" * 60)
    print("RUNTIME DRIFT DIFFS")
    print("=" * 60)

    for r in drifted:
        diff_info = file_diff(r["canonical"], r["installed"])
        print(f"\n--- {r['name']} ({r['type']}) ---")
        print(f"  Canonical: {r['canonical']}")
        print(f"  Installed: {r['installed']}")
        print(f"  Canonical lines: {diff_info['canonical_lines']}")
        print(f"  Installed lines: {diff_info['installed_lines']}")
        print(f"  Lines only in canonical: {diff_info['removed_lines']}")
        print(f"  Lines only in installed: {diff_info['added_lines']}")

    return results


def cmd_sync(surfaces, zone_root):
    """Copy canonical to installed for drifted/missing surfaces, verify."""
    results = [compare_surface(s) for s in surfaces]
    needs_sync = [r for r in results if r["status"] in ("drifted", "missing_installed")]

    if not needs_sync:
        print("All surfaces are in sync. Nothing to do.")
        return results

    # Record that drift was detected BEFORE sync — the detection event
    # itself is a governance hazard per Trip Hazard Invariant
    emit_drift_signal(zone_root, needs_sync, severity="detected_drift")

    print("=" * 60)
    print("RUNTIME SYNC")
    print("=" * 60)

    synced_count = 0
    for r in needs_sync:
        if not os.path.isfile(r["canonical"]):
            print(f"  [SKIP] {r['name']} — canonical source missing")
            continue

        # Ensure target directory exists
        os.makedirs(os.path.dirname(r["installed"]), exist_ok=True)

        # Copy
        shutil.copy2(r["canonical"], r["installed"])

        # Verify
        new_hash = file_hash(r["installed"])
        if new_hash == r["canonical_hash"]:
            print(f"  [SYNCED] {r['name']}")
            synced_count += 1
        else:
            print(f"  [ERROR] {r['name']} — hash mismatch after copy")

    print()
    print(f"  Synced {synced_count}/{len(needs_sync)} surfaces")

    # Re-check for any remaining drift — escalated severity
    post_results = [compare_surface(s) for s in surfaces]
    still_drifted = [r for r in post_results if r["status"] == "drifted"]
    if still_drifted:
        signal_id = emit_drift_signal(zone_root, still_drifted, severity="unresolved_drift")
        print(f"  WARNING: {len(still_drifted)} surfaces still drifted after sync")
        print(f"  TENSION signal emitted (unresolved_drift): {signal_id}")

    return post_results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Runtime Sync — compare installed vs canonical CGG surfaces"
    )
    parser.add_argument("command", choices=["check", "diff", "sync"],
                        help="Operation: check (report), diff (show diffs), sync (copy canonical to installed)")
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--plugin-root", default=None,
                        help="Explicit CGG plugin root (bypasses auto-detection)")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Output structured JSON drift report (check/diff)")
    args = parser.parse_args()

    try:
        zone_root = args.project_dir or resolve_zone_root()
    except Exception as e:
        if args.output_json:
            print(json.dumps({"error": str(e), "exit_code": 2}))
        else:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    plugin_root = args.plugin_root if args.plugin_root else find_plugin_root(zone_root)

    if not plugin_root:
        msg = f"CGG plugin root not found. Checked: {zone_root}/vendor/context-grapple-gun/, {zone_root}/.claude/cgg/, ~/.claude/cgg/"
        if args.output_json:
            print(json.dumps({"error": msg, "exit_code": 2}))
        else:
            print("ERROR: CGG plugin root not found. Checked:")
            print(f"  {zone_root}/vendor/context-grapple-gun/")
            print(f"  {zone_root}/.claude/cgg/")
            print(f"  ~/.claude/cgg/")
        sys.exit(2)

    surfaces = build_surface_map(plugin_root, zone_root)

    if args.command == "check":
        results = cmd_check(surfaces, zone_root, output_json=args.output_json)
        drifted = [r for r in results if r["status"] in ("drifted", "missing_installed")]
        sys.exit(1 if drifted else 0)
    elif args.command == "diff":
        cmd_diff(surfaces, output_json=args.output_json)
    elif args.command == "sync":
        cmd_sync(surfaces, zone_root)


if __name__ == "__main__":
    main()
