#!/usr/bin/env bash
# post-commit-sync.sh — CGG PostToolUse hook
#
# Fires after Bash tool invocations. Checks if the command was a git commit
# touching CGG runtime files. If so, runs auto-sync to keep installed
# runtime in sync with canonical source.
#
# Registered as: PostToolUse hook with matcher "Bash"
# Input: JSON on stdin with tool_input.command
# Output: stdout message (shown to user if non-empty)

set -euo pipefail

# Read tool input from stdin
INPUT=$(cat)

# Wire cutter — emergency kill switch
[ -f ~/.claude/wire-cutter.sh ] && source ~/.claude/wire-cutter.sh && wire_check sync

# Extract the command that was run
COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    cmd = data.get('tool_input', {}).get('command', '')
    print(cmd)
except:
    print('')
" 2>/dev/null)

# Fast exit: only care about git commit commands
if ! echo "$COMMAND" | grep -q 'git commit'; then
    exit 0
fi

# ============================================================================
# Path resolution — use environment variables, not dirname "$0" relative paths.
# This hook is installed at ~/.claude/hooks/ which is OUTSIDE the plugin tree.
# dirname-relative navigation only works inside the plugin directory.
# ============================================================================

# Zone root: use CLAUDE_PROJECT_DIR, fall back to .ticzone walk
resolve_zone_root() {
    local dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
    while [ "$dir" != "/" ]; do
        [ -f "$dir/.ticzone" ] && echo "$dir" && return 0
        dir=$(dirname "$dir")
    done
    echo "${CLAUDE_PROJECT_DIR:-$(pwd)}"
}
ZONE_ROOT=$(resolve_zone_root)

# Plugin root: use CLAUDE_PLUGIN_ROOT, fall back to known locations
CGG_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
if [ -z "$CGG_ROOT" ] || [ ! -d "$CGG_ROOT" ]; then
    for candidate in \
        "$ZONE_ROOT/vendor/context-grapple-gun" \
        "$ZONE_ROOT/canonical_developer/context-grapple-gun" \
        "$HOME/.claude/cgg"; do
        [ -d "$candidate" ] && CGG_ROOT="$candidate" && break
    done
fi

# Scripts directory: plugin-root-anchored, then global install fallback
SCRIPT_DIR=""
for candidate in \
    "${CGG_ROOT:+$CGG_ROOT/cgg-runtime/scripts}" \
    "$HOME/.claude/cgg-runtime/scripts"; do
    [ -n "$candidate" ] && [ -d "$candidate" ] && SCRIPT_DIR="$candidate" && break
done

# Fast exit: no scripts directory found
[ -z "$SCRIPT_DIR" ] && exit 0

# Check if the commit touched cgg-runtime files
CGG_GIT_DIR="${CGG_ROOT:+$CGG_ROOT/.git}"
if [ -n "$CGG_GIT_DIR" ] && [ -d "$CGG_GIT_DIR" ]; then
    # CGG has its own git — check if the commit was in this repo
    CHANGED_FILES=$(cd "$CGG_ROOT" && git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null || true)
    if ! echo "$CHANGED_FILES" | grep -q 'cgg-runtime/'; then
        exit 0
    fi
    COMMIT_SHA=$(cd "$CGG_ROOT" && git rev-parse HEAD 2>/dev/null || echo "unknown")
else
    # Federation repo — check if commit touched canonical_developer/context-grapple-gun/cgg-runtime/
    CHANGED_FILES=$(cd "$ZONE_ROOT" && git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null || true)
    if ! echo "$CHANGED_FILES" | grep -q 'canonical_developer/context-grapple-gun/cgg-runtime/'; then
        exit 0
    fi
    COMMIT_SHA=$(cd "$ZONE_ROOT" && git rev-parse HEAD 2>/dev/null || echo "unknown")
fi

# Run auto-sync
if [ -f "$SCRIPT_DIR/runtime-sync.py" ]; then
    RESULT=$(python3 "$SCRIPT_DIR/runtime-sync.py" auto-sync \
        --project-dir "$ZONE_ROOT" \
        --plugin-root "${CGG_ROOT:-$ZONE_ROOT}" \
        --commit "$COMMIT_SHA" 2>&1) || true
    if [ -n "$RESULT" ]; then
        echo "$RESULT"
    fi
fi
