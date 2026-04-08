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
    python3 runtime-sync.py check      [--project-dir PATH] [--json]
    python3 runtime-sync.py diff       [--project-dir PATH] [--json]
    python3 runtime-sync.py sync       [--project-dir PATH]
    python3 runtime-sync.py auto-sync  [--project-dir PATH] [--commit SHA]
    python3 runtime-sync.py discover   [--project-dir PATH] [--json]
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, birth_topology


# ---------------------------------------------------------------------------
# Surface discovery — file-tree derived, not static
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Surface manifest — loaded from sync-manifest.json (single source of truth)
# Both runtime-sync.py and posttool-sync-weigh.sh consume this file.
# Edit sync-manifest.json, not these variables.
# ---------------------------------------------------------------------------

def _load_sync_manifest():
    """Load surface map from sync-manifest.json next to cgg-runtime/."""
    manifest_candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sync-manifest.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sync-manifest.json"),
    ]
    for path in manifest_candidates:
        path = os.path.normpath(path)
        if os.path.isfile(path):
            with open(path) as f:
                return json.load(f)
    # Fallback: if manifest is missing, fail loudly
    print("FATAL: sync-manifest.json not found. Looked in:", manifest_candidates, file=sys.stderr)
    sys.exit(3)

_MANIFEST = _load_sync_manifest()

INSTALL_TARGETS = _MANIFEST["install_targets"]

SYNC_EXCLUDE = set(_MANIFEST.get("sync_exclude", []))

# Overrides in manifest use relative paths (~/.claude/...); expand to absolute
INSTALL_PATH_OVERRIDES = {
    k: os.path.join(os.path.expanduser("~"), v)
    for k, v in _MANIFEST.get("install_path_overrides", {}).items()
}


def discover_surfaces(plugin_root, zone_root):
    """Auto-discover all installable surfaces by scanning the cgg-runtime file tree.

    Returns a list of surface dicts (same shape as the old static build_surface_map).
    Install targets always resolve to ~/.claude/ (the user's global runtime),
    not zone_root/.claude/ (which is project-local settings).
    """
    surfaces = []
    runtime_dir = os.path.join(plugin_root, "cgg-runtime")
    home_dir = os.path.expanduser("~")

    for category, spec in INSTALL_TARGETS.items():
        canonical_dir = os.path.join(runtime_dir, spec["canonical_subdir"])
        if not os.path.isdir(canonical_dir):
            continue

        if category == "skills":
            # Skills: each subdirectory with a SKILL.md
            for entry in sorted(os.listdir(canonical_dir)):
                skill_file = os.path.join(canonical_dir, entry, "SKILL.md")
                if os.path.isfile(skill_file):
                    installed = os.path.join(
                        home_dir, spec["installed_subdir"], entry, "SKILL.md"
                    )
                    surfaces.append({
                        "name": f"skill:{entry}",
                        "canonical": skill_file,
                        "installed": installed,
                        "type": spec["type"],
                        "category": category,
                    })
        elif category == "agents":
            # Agents: each .md file in agents/
            for entry in sorted(os.listdir(canonical_dir)):
                if entry.endswith(".md"):
                    canonical_path = os.path.join(canonical_dir, entry)
                    rel_key = f"{spec['canonical_subdir']}/{entry}"
                    if rel_key in SYNC_EXCLUDE:
                        continue
                    installed = os.path.join(
                        home_dir, spec["installed_subdir"], entry
                    )
                    name = entry.replace(".md", "")
                    surfaces.append({
                        "name": f"agent:{name}",
                        "canonical": canonical_path,
                        "installed": installed,
                        "type": spec["type"],
                        "category": category,
                    })
        elif category == "hooks":
            # Hooks: each .sh file in hooks/
            for entry in sorted(os.listdir(canonical_dir)):
                if entry.endswith(".sh"):
                    canonical_path = os.path.join(canonical_dir, entry)
                    rel_key = f"{spec['canonical_subdir']}/{entry}"
                    if rel_key in SYNC_EXCLUDE:
                        continue
                    # Check for non-standard install path override
                    if rel_key in INSTALL_PATH_OVERRIDES:
                        installed = INSTALL_PATH_OVERRIDES[rel_key]
                    else:
                        installed = os.path.join(
                            home_dir, spec["installed_subdir"], entry
                        )
                    name = entry.replace(".sh", "")
                    surfaces.append({
                        "name": f"hook:{name}",
                        "canonical": canonical_path,
                        "installed": installed,
                        "type": spec["type"],
                        "category": category,
                    })
        elif category == "scripts":
            # Scripts: each .py file in scripts/ (flat, not nested)
            for entry in sorted(os.listdir(canonical_dir)):
                if entry.endswith(".py"):
                    canonical_path = os.path.join(canonical_dir, entry)
                    rel_key = f"{spec['canonical_subdir']}/{entry}"
                    if rel_key in SYNC_EXCLUDE:
                        continue
                    installed = os.path.join(
                        home_dir, spec["installed_subdir"], entry
                    )
                    name = entry.replace(".py", "")
                    surfaces.append({
                        "name": f"script:{name}",
                        "canonical": canonical_path,
                        "installed": installed,
                        "type": spec["type"],
                        "category": category,
                    })
            # Also sync .sh scripts (mogul-runner.sh, etc.)
            for entry in sorted(os.listdir(canonical_dir)):
                if entry.endswith(".sh"):
                    canonical_path = os.path.join(canonical_dir, entry)
                    rel_key = f"{spec['canonical_subdir']}/{entry}"
                    if rel_key in SYNC_EXCLUDE:
                        continue
                    installed = os.path.join(
                        home_dir, spec["installed_subdir"], entry
                    )
                    name = entry.replace(".sh", "")
                    surfaces.append({
                        "name": f"script:{name}",
                        "canonical": canonical_path,
                        "installed": installed,
                        "type": spec["type"],
                        "category": category,
                    })
            # Sync lib/ subdirectory contents
            lib_dir = os.path.join(canonical_dir, "lib")
            if os.path.isdir(lib_dir):
                for entry in sorted(os.listdir(lib_dir)):
                    if entry.startswith("__"):
                        continue  # skip __pycache__
                    canonical_path = os.path.join(lib_dir, entry)
                    if not os.path.isfile(canonical_path):
                        continue
                    installed = os.path.join(
                        home_dir, spec["installed_subdir"], "lib", entry
                    )
                    surfaces.append({
                        "name": f"script:lib/{entry}",
                        "canonical": canonical_path,
                        "installed": installed,
                        "type": spec["type"],
                        "category": category,
                    })

    return surfaces


def build_surface_map(plugin_root, zone_root):
    """Build mapping of canonical -> installed paths for all tracked surfaces.

    Now delegates to discover_surfaces() for file-tree derived discovery.
    """
    return discover_surfaces(plugin_root, zone_root)


def find_plugin_root(zone_root):
    """Locate the CGG plugin root directory."""
    candidates = [
        os.path.join(zone_root, "vendor", "context-grapple-gun"),
        os.path.join(zone_root, ".claude", "cgg"),
        os.path.join(os.path.expanduser("~"), ".claude", "cgg"),
        # Federation layout: canonical_developer/context-grapple-gun/
        os.path.join(zone_root, "canonical_developer", "context-grapple-gun"),
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
# Commit context enrichment
# ---------------------------------------------------------------------------

def get_commit_context(plugin_root, canonical_path, installed_hash):
    """Get git commit history for a canonical file to explain drift.

    Returns a dict with:
    - last_commit: the most recent commit that touched this file
    - commits_since_installed: commits that changed this file since the
      installed version's content was current
    - drift_window: human-readable summary of the drift timeline
    """
    if not os.path.isfile(canonical_path):
        return None

    try:
        # Get recent commit history for this file (last 10 commits)
        result = subprocess.run(
            ["git", "log", "--format=%H|%ai|%s", "-n", "10", "--", canonical_path],
            capture_output=True, text=True, timeout=10,
            cwd=plugin_root,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        commits = []
        for line in result.stdout.strip().split("\n"):
            parts = line.split("|", 2)
            if len(parts) == 3:
                commits.append({
                    "sha": parts[0][:12],
                    "sha_full": parts[0],
                    "date": parts[1].strip(),
                    "message": parts[2].strip(),
                })

        if not commits:
            return None

        # If we have the installed hash, find which commits introduced the drift
        # by checking file content at each commit
        drift_commits = []
        if installed_hash:
            for commit in commits:
                try:
                    blob_result = subprocess.run(
                        ["git", "show", f"{commit['sha_full']}:{os.path.relpath(canonical_path, plugin_root)}"],
                        capture_output=True, timeout=5,
                        cwd=plugin_root,
                    )
                    if blob_result.returncode == 0:
                        commit_hash = hashlib.sha256(blob_result.stdout).hexdigest()
                        if commit_hash == installed_hash:
                            # Found the commit where installed version was current
                            break
                        drift_commits.append(commit)
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    break

        context = {
            "last_commit": commits[0] if commits else None,
            "commits_since_installed": drift_commits if drift_commits else commits[:5],
            "drift_depth": len(drift_commits) if drift_commits else "unknown",
        }

        if drift_commits:
            context["drift_window"] = f"{len(drift_commits)} commits, " \
                f"from {drift_commits[-1]['date'].split()[0]} to {drift_commits[0]['date'].split()[0]}"
        else:
            context["drift_window"] = "unknown (installed hash not found in recent history)"

        return context

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def get_current_commit(repo_dir):
    """Get the current HEAD commit SHA and message for a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=repo_dir,
        )
        if result.returncode != 0:
            return None, None

        sha = result.stdout.strip()

        msg_result = subprocess.run(
            ["git", "log", "--format=%s", "-n", "1"],
            capture_output=True, text=True, timeout=5,
            cwd=repo_dir,
        )
        msg = msg_result.stdout.strip() if msg_result.returncode == 0 else ""
        return sha, msg
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None


# ---------------------------------------------------------------------------
# Sync log
# ---------------------------------------------------------------------------

def write_sync_log(zone_root, plugin_root, synced_surfaces, commit_sha, commit_msg):
    """Append a sync event to the sync log with commit pointer."""
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    log_dir = os.path.join(al_path, "services")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "cgg-sync-log.jsonl")

    now = datetime.now(timezone.utc)
    entry = {
        "event": "sync",
        "timestamp": now.isoformat(),
        "commit_sha": commit_sha[:12] if commit_sha else None,
        "commit_sha_full": commit_sha,
        "commit_message": commit_msg,
        "surfaces_synced": [
            {
                "name": s["name"],
                "canonical_hash": s.get("canonical_hash"),
                "previous_installed_hash": s.get("installed_hash"),
                "status_before": s.get("status"),
            }
            for s in synced_surfaces
        ],
        "surface_count": len(synced_surfaces),
        "source": "runtime-sync.py",
    }

    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(str(log_file), entry)
    except ImportError:
        import fcntl
        lockfile = str(log_file) + ".lock"
        with open(lockfile, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    return log_file


def read_last_sync(zone_root):
    """Read the most recent sync log entry. Returns dict or None."""
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    log_file = os.path.join(al_path, "services", "cgg-sync-log.jsonl")

    if not os.path.isfile(log_file):
        return None

    last_line = None
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line
        if last_line:
            return json.loads(last_line)
    except (OSError, json.JSONDecodeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Signal emission
# ---------------------------------------------------------------------------

def emit_drift_signal(zone_root, drifted_surfaces, severity="detected_drift",
                      commit_context=None):
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

    payload = {
        "summary": f"Runtime {severity.replace('_', ' ')}: {len(drifted_surfaces)} surfaces",
        "severity": severity,
        "surfaces": surface_names,
    }

    # Enrich with commit context if available
    if commit_context:
        payload["commit_context"] = commit_context

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
        "payload": payload,
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

def cmd_check(surfaces, zone_root, plugin_root, output_json=False, enrich=False):
    """Report sync status for all surfaces. Emits drift hazard on detection."""
    results = [compare_surface(s) for s in surfaces]
    drifted = [r for r in results if r["status"] == "drifted"]
    missing = [r for r in results if r["status"] == "missing_installed"]
    new_canonical = [r for r in results if r["status"] == "missing_installed"
                     and r["canonical_hash"] is not None]
    synced = [r for r in results if r["status"] == "synced"]

    # Enrich drifted surfaces with commit context
    enrichments = {}
    if enrich and plugin_root:
        for r in drifted:
            ctx = get_commit_context(plugin_root, r["canonical"], r["installed_hash"])
            if ctx:
                enrichments[r["name"]] = ctx

    # Drift detection itself is a governance hazard — emit on detection
    signal_id = None
    commit_ctx_summary = None
    if drifted:
        if enrichments:
            commit_ctx_summary = {
                name: {
                    "drift_depth": ctx["drift_depth"],
                    "drift_window": ctx["drift_window"],
                    "last_commit": ctx["last_commit"]["sha"] if ctx.get("last_commit") else None,
                }
                for name, ctx in enrichments.items()
            }
        signal_id = emit_drift_signal(zone_root, drifted, severity="detected_drift",
                                      commit_context=commit_ctx_summary)

    last_sync = read_last_sync(zone_root)

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
                    "commit_context": enrichments.get(r["name"]),
                }
                for r in results
            ],
            "summary": {
                "synced": len(synced),
                "drifted": len(drifted),
                "missing_installed": len(missing),
                "new_canonical": len(new_canonical),
                "total": len(results),
            },
            "last_sync": {
                "timestamp": last_sync["timestamp"] if last_sync else None,
                "commit_sha": last_sync.get("commit_sha") if last_sync else None,
            } if last_sync else None,
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
            "missing_installed": " NEW  ",
            "missing_canonical": "NO SRC",
            "both_missing": "ABSENT",
        }.get(r["status"], r["status"])
        print(f"  [{status_tag}] {r['name']:<30} ({r['type']})")

        # Show enrichment if available
        if r["name"] in enrichments:
            ctx = enrichments[r["name"]]
            print(f"           drift: {ctx['drift_window']}")
            if ctx.get("last_commit"):
                print(f"           last:  {ctx['last_commit']['sha']} {ctx['last_commit']['message'][:60]}")

    print()
    print(f"  Synced: {len(synced)}  |  Drifted: {len(drifted)}  |  New: {len(new_canonical)}  |  Total: {len(results)}")

    if last_sync:
        print(f"  Last sync: {last_sync['timestamp'][:19]}  commit: {last_sync.get('commit_sha', 'unknown')}")

    if signal_id:
        print(f"  TENSION signal emitted (detected_drift): {signal_id}")

    return results


def cmd_diff(surfaces, plugin_root, output_json=False):
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
            ctx = get_commit_context(plugin_root, r["canonical"], r["installed_hash"])
            diffs.append({
                "name": r["name"],
                "type": r["type"],
                "canonical": r["canonical"],
                "installed": r["installed"],
                "canonical_hash": r["canonical_hash"],
                "installed_hash": r["installed_hash"],
                "commit_context": ctx,
                **diff_info,
            })
        print(json.dumps({"command": "diff", "drifted": diffs}, indent=2))
        return results

    print("=" * 60)
    print("RUNTIME DRIFT DIFFS")
    print("=" * 60)

    for r in drifted:
        diff_info = file_diff(r["canonical"], r["installed"])
        ctx = get_commit_context(plugin_root, r["canonical"], r["installed_hash"])
        print(f"\n--- {r['name']} ({r['type']}) ---")
        print(f"  Canonical: {r['canonical']}")
        print(f"  Installed: {r['installed']}")
        print(f"  Canonical lines: {diff_info['canonical_lines']}")
        print(f"  Installed lines: {diff_info['installed_lines']}")
        print(f"  Lines only in canonical: {diff_info['removed_lines']}")
        print(f"  Lines only in installed: {diff_info['added_lines']}")
        if ctx:
            print(f"  Drift window: {ctx['drift_window']}")
            for c in ctx.get("commits_since_installed", [])[:5]:
                print(f"    {c['sha']} {c['date'].split()[0]} {c['message'][:60]}")

    return results


def cmd_sync(surfaces, zone_root, plugin_root, commit_sha=None, commit_msg=None):
    """Copy canonical to installed for drifted/missing surfaces, verify, log."""
    results = [compare_surface(s) for s in surfaces]
    needs_sync = [r for r in results if r["status"] in ("drifted", "missing_installed")]

    if not needs_sync:
        print("All surfaces are in sync. Nothing to do.")
        return results

    # Get commit pointer if not provided
    if not commit_sha and plugin_root:
        commit_sha, commit_msg = get_current_commit(plugin_root)

    # Record that drift was detected BEFORE sync
    emit_drift_signal(zone_root, needs_sync, severity="detected_drift")

    print("=" * 60)
    print("RUNTIME SYNC")
    print("=" * 60)

    synced_items = []
    for r in needs_sync:
        if not os.path.isfile(r["canonical"]):
            print(f"  [SKIP] {r['name']} — canonical source missing")
            continue

        # Ensure target directory exists
        os.makedirs(os.path.dirname(r["installed"]), exist_ok=True)

        # Copy
        shutil.copy2(r["canonical"], r["installed"])

        # Make scripts executable
        if r.get("type") == "SCRIPT_CODE":
            os.chmod(r["installed"], 0o755)

        # Verify
        new_hash = file_hash(r["installed"])
        if new_hash == r["canonical_hash"]:
            label = "SYNCED" if r["status"] == "drifted" else "INSTALLED"
            print(f"  [{label}] {r['name']}")
            synced_items.append(r)
        else:
            print(f"  [ERROR] {r['name']} — hash mismatch after copy")

    print()
    print(f"  Synced {len(synced_items)}/{len(needs_sync)} surfaces")

    # Write sync log with commit pointer
    if synced_items:
        log_file = write_sync_log(zone_root, plugin_root, synced_items,
                                  commit_sha, commit_msg)
        print(f"  Sync log: {log_file}")

    # Re-check for any remaining drift — escalated severity
    post_results = [compare_surface(s) for s in surfaces]
    still_drifted = [r for r in post_results if r["status"] == "drifted"]
    if still_drifted:
        signal_id = emit_drift_signal(zone_root, still_drifted, severity="unresolved_drift")
        print(f"  WARNING: {len(still_drifted)} surfaces still drifted after sync")
        print(f"  TENSION signal emitted (unresolved_drift): {signal_id}")

    return post_results


def cmd_auto_sync(surfaces, zone_root, plugin_root, commit_sha=None):
    """Post-commit auto-sync: discover, compare, selectively sync, log.

    This is the hook-triggered entry point. It:
    1. Discovers all surfaces from the file tree
    2. Compares canonical vs installed
    3. Syncs only changed/new surfaces
    4. Logs the sync event with commit pointer
    5. Prints a compact summary for hook output
    """
    if not commit_sha and plugin_root:
        commit_sha, commit_msg = get_current_commit(plugin_root)
    else:
        commit_msg = None

    results = [compare_surface(s) for s in surfaces]
    needs_sync = [r for r in results if r["status"] in ("drifted", "missing_installed")]
    synced_count = sum(1 for r in results if r["status"] == "synced")

    if not needs_sync:
        print(f"[CGG-SYNC] All {synced_count} surfaces in sync @ {commit_sha[:8] if commit_sha else 'HEAD'}")
        return results

    # Sync and log
    synced_items = []
    for r in needs_sync:
        if not os.path.isfile(r["canonical"]):
            continue
        os.makedirs(os.path.dirname(r["installed"]), exist_ok=True)
        shutil.copy2(r["canonical"], r["installed"])
        if r.get("type") == "SCRIPT_CODE":
            os.chmod(r["installed"], 0o755)
        new_hash = file_hash(r["installed"])
        if new_hash == r["canonical_hash"]:
            synced_items.append(r)

    # Log
    if synced_items:
        write_sync_log(zone_root, plugin_root, synced_items, commit_sha, commit_msg)

    # Compact summary for hook output
    new_surfaces = [r for r in needs_sync if r["status"] == "missing_installed"]
    updated_surfaces = [r for r in needs_sync if r["status"] == "drifted"]
    parts = []
    if updated_surfaces:
        parts.append(f"{len(updated_surfaces)} updated")
    if new_surfaces:
        parts.append(f"{len(new_surfaces)} new")
    summary = ", ".join(parts)
    names = [r["name"] for r in synced_items]
    print(f"[CGG-SYNC] {summary}: {', '.join(names)} @ {commit_sha[:8] if commit_sha else 'HEAD'}")

    return results


def cmd_discover(surfaces, plugin_root, zone_root, output_json=False):
    """List all discovered surfaces and their sync status."""
    results = [compare_surface(s) for s in surfaces]
    last_sync = read_last_sync(zone_root)

    if output_json:
        output = {
            "command": "discover",
            "surfaces": [
                {
                    "name": r["name"],
                    "category": r.get("category"),
                    "type": r["type"],
                    "status": r["status"],
                    "canonical": r["canonical"],
                    "installed": r["installed"],
                }
                for r in results
            ],
            "total": len(results),
            "last_sync": last_sync,
        }
        print(json.dumps(output, indent=2))
        return

    print("=" * 60)
    print("CGG SURFACE DISCOVERY")
    print("=" * 60)

    current_category = None
    for r in results:
        cat = r.get("category", "unknown")
        if cat != current_category:
            print(f"\n  {cat.upper()}")
            current_category = cat
        status_tag = {
            "synced": "  OK  ",
            "drifted": "DRIFTED",
            "missing_installed": " NEW  ",
            "missing_canonical": "NO SRC",
            "both_missing": "ABSENT",
        }.get(r["status"], r["status"])
        print(f"    [{status_tag}] {r['name']}")

    print(f"\n  Total: {len(results)} surfaces")
    if last_sync:
        print(f"  Last sync: {last_sync['timestamp'][:19]}  commit: {last_sync.get('commit_sha', 'unknown')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Runtime Sync — compare installed vs canonical CGG surfaces"
    )
    parser.add_argument("command", choices=["check", "diff", "sync", "auto-sync", "discover"],
                        help="Operation: check, diff, sync, auto-sync (hook-triggered), discover (list surfaces)")
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--plugin-root", default=None,
                        help="Explicit CGG plugin root (bypasses auto-detection)")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Output structured JSON (check/diff/discover)")
    parser.add_argument("--commit", default=None, dest="commit_sha",
                        help="Git commit SHA to record in sync log (auto-sync)")
    parser.add_argument("--enrich", action="store_true",
                        help="Enrich drift detection with commit history context (check)")
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
        msg = (f"CGG plugin root not found. Checked: {zone_root}/vendor/context-grapple-gun/, "
               f"{zone_root}/.claude/cgg/, ~/.claude/cgg/, "
               f"{zone_root}/canonical_developer/context-grapple-gun/")
        if args.output_json:
            print(json.dumps({"error": msg, "exit_code": 2}))
        else:
            print(f"ERROR: {msg}", file=sys.stderr)
        sys.exit(2)

    surfaces = build_surface_map(plugin_root, zone_root)

    if args.command == "check":
        results = cmd_check(surfaces, zone_root, plugin_root,
                            output_json=args.output_json, enrich=args.enrich)
        drifted = [r for r in results if r["status"] in ("drifted", "missing_installed")]
        sys.exit(1 if drifted else 0)
    elif args.command == "diff":
        cmd_diff(surfaces, plugin_root, output_json=args.output_json)
    elif args.command == "sync":
        cmd_sync(surfaces, zone_root, plugin_root)
    elif args.command == "auto-sync":
        cmd_auto_sync(surfaces, zone_root, plugin_root, commit_sha=args.commit_sha)
    elif args.command == "discover":
        cmd_discover(surfaces, plugin_root, zone_root, output_json=args.output_json)


if __name__ == "__main__":
    main()
