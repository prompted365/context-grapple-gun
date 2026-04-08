#!/usr/bin/env python3
"""
sync-weigh-check.py — Weighing check for posttool-sync-weigh.sh

Reads PostToolUse JSON from stdin, checks if the edited file is in a
weighed surface (per sync-manifest.json), compares canonical vs installed,
and reports drift + sub-repo versioning state.

Called by posttool-sync-weigh.sh — not intended for direct invocation.
"""

import sys
import json
import os
import hashlib
import subprocess


def main():
    # --- Parse stdin ---
    try:
        data = json.load(sys.stdin)
        file_path = data.get('tool_input', {}).get('file_path', '')
    except Exception as e:
        print(f'[sync-weigh] stdin parse error: {e}', file=sys.stderr)
        return

    if not file_path:
        return

    # --- Resolve zone root ---
    # Walk up from the EDITED FILE (not cwd) to find .federation-root or .ticzone.
    zone_root = None
    for start in [os.path.dirname(file_path), os.environ.get('CLAUDE_PROJECT_DIR', ''), os.getcwd()]:
        if not start:
            continue
        d = start
        while d != '/':
            if os.path.isfile(os.path.join(d, '.federation-root')) or os.path.isfile(os.path.join(d, '.ticzone')):
                zone_root = d
                break
            d = os.path.dirname(d)
        if zone_root:
            break

    if not zone_root:
        return  # Not in a federation — nothing to weigh

    # --- Load manifest ---
    cgg_runtime = os.path.join(zone_root, 'canonical_developer', 'context-grapple-gun', 'cgg-runtime')
    manifest_path = os.path.join(cgg_runtime, 'sync-manifest.json')

    # Also check installed copy as fallback
    if not os.path.isfile(manifest_path):
        manifest_path = os.path.join(os.path.expanduser('~'), '.claude', 'cgg-runtime', 'sync-manifest.json')
    if not os.path.isfile(manifest_path):
        return  # No manifest = can't weigh = silent exit

    with open(manifest_path) as f:
        manifest = json.load(f)

    targets = manifest.get('install_targets', {})
    excludes = manifest.get('exclude_patterns', [])
    sync_exclude = set(manifest.get('sync_exclude', []))
    overrides = manifest.get('install_path_overrides', {})
    home = os.path.expanduser('~')

    # --- Match file against weighed surfaces ---
    matched_canonical_dir = None
    matched_installed_dir = None
    relative_path = None

    for cat, spec in targets.items():
        canonical_dir = os.path.join(cgg_runtime, spec['canonical_subdir'])
        if file_path.startswith(canonical_dir + '/'):
            relative_path = file_path[len(canonical_dir) + 1:]
            rel_key = spec['canonical_subdir'] + '/' + relative_path
            if rel_key in sync_exclude:
                return
            matched_canonical_dir = canonical_dir
            matched_installed_dir = os.path.join(home, spec['installed_subdir'])
            if rel_key in overrides:
                matched_installed_dir = os.path.dirname(os.path.join(home, overrides[rel_key]))
                relative_path = os.path.basename(overrides[rel_key])
            break

    # Fast exit: not in any weighed surface
    if matched_canonical_dir is None:
        # Self-awareness: warn if someone edits the manifest itself
        manifest_abs = os.path.normpath(os.path.join(cgg_runtime, 'sync-manifest.json'))
        if os.path.normpath(file_path) == manifest_abs:
            installed_manifest = os.path.join(home, '.claude', 'cgg-runtime', 'sync-manifest.json')
            if os.path.isfile(installed_manifest):
                with open(manifest_abs, 'rb') as a, open(installed_manifest, 'rb') as b:
                    if a.read() != b.read():
                        print('[sync-weigh] DRIFT: sync-manifest.json changed — installed copy is stale')
                        print(f'  canonical: {manifest_abs}')
                        print(f'  installed: {installed_manifest}')
                        print('  action: cp canonical → installed (both runtime-sync.py and this hook read from it)')
            else:
                print('[sync-weigh] NEW: sync-manifest.json not yet installed')
                print(f'  canonical: {manifest_abs}')
                print(f'  expected:  {os.path.join(home, ".claude", "cgg-runtime", "sync-manifest.json")}')
        return

    # Check exclude patterns
    for pat in excludes:
        if pat.startswith('*'):
            if relative_path.endswith(pat[1:]):
                return
        elif pat in relative_path:
            return

    # --- Compare canonical vs installed ---
    installed_file = os.path.join(matched_installed_dir, relative_path)

    if not os.path.isfile(installed_file):
        print(f'[sync-weigh] NEW canonical file not yet installed: {relative_path}')
        print(f'  canonical: {file_path}')
        print(f'  expected:  {installed_file}')
        print(f'  action: run runtime-sync.py sync to install')
        _check_versioning(file_path, zone_root)
        return

    drifted = _md5(file_path) != _md5(installed_file)

    if drifted:
        print(f'[sync-weigh] DRIFT: canonical ≠ installed for {relative_path}')
        print(f'  canonical: {file_path}')
        print(f'  installed: {installed_file}')
        print(f'  action: cp canonical → installed, or run runtime-sync.py sync')

    # Always check versioning state — even for in-sync files, the sub-repo
    # may have uncommitted changes that need attention
    _check_versioning(file_path, zone_root)


def _md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def _git_dirty_count(repo_dir, subpath=None):
    """Count uncommitted changes in a git repo, optionally scoped to subpath."""
    try:
        cmd = ['git', '-C', repo_dir, 'status', '--porcelain']
        if subpath:
            cmd.append(subpath)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        return [l for l in result.stdout.strip().splitlines() if l.strip()]
    except Exception:
        return []


def _find_owning_git(path):
    """Walk up from path to find the nearest .git directory."""
    d = os.path.dirname(path)
    while d != '/':
        if os.path.isdir(os.path.join(d, '.git')) or os.path.isfile(os.path.join(d, '.git')):
            return d
        d = os.path.dirname(d)
    return None


def _check_versioning(file_path, zone_root):
    """Check sub-repo and parent repo versioning state."""
    owning_repo = _find_owning_git(file_path)

    if owning_repo and owning_repo != zone_root:
        # File lives in a sub-repo (e.g., canonical_developer/context-grapple-gun/)
        # Check the sub-repo's dirty state — changes here are invisible to parent git
        dirty = _git_dirty_count(owning_repo)
        if dirty:
            repo_name = os.path.relpath(owning_repo, zone_root)
            print(f'[sync-weigh] {repo_name} has {len(dirty)} uncommitted change(s)')

    elif os.path.isfile(os.path.join(zone_root, '.federation-root')):
        # File is directly in the federation repo — check estate-level dirty state
        rel_to_zone = os.path.relpath(file_path, zone_root)
        parts = rel_to_zone.split(os.sep)
        estate = parts[0] if len(parts) > 1 else None
        if estate in ('canonical_developer', 'canonical_user'):
            dirty = _git_dirty_count(zone_root, estate + '/')
            if dirty:
                print(f'[sync-weigh] {estate}/ has {len(dirty)} uncommitted change(s) in federation repo')


if __name__ == '__main__':
    main()
