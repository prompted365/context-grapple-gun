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

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)/scripts"
ZONE_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../../.." && pwd)}"
CGG_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Check if the commit touched cgg-runtime files
# We check the most recent commit in the CGG repo
CGG_GIT_DIR="$CGG_ROOT/.git"
if [ -d "$CGG_GIT_DIR" ]; then
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
    python3 "$SCRIPT_DIR/runtime-sync.py" auto-sync \
        --project-dir "$ZONE_ROOT" \
        --plugin-root "$CGG_ROOT" \
        --commit "$COMMIT_SHA" 2>/dev/null || true
fi
