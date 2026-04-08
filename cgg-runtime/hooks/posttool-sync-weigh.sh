#!/usr/bin/env bash
# posttool-sync-weigh.sh — PostToolUse hook (Edit|Write)
#
# "Weighing" hook: checks if an edited canonical file has an installed
# counterpart that is now out of sync. Reports drift + versioning state.
#
# Surface map loaded from sync-manifest.json (single source of truth).
# runtime-sync.py reads the same file — edit sync-manifest.json to add
# or remove weighed surfaces, and BOTH consumers see the change.
#
# Three-form boundary awareness:
#   Form 1 (forge):   canonical_developer/context-grapple-gun/cgg-runtime/
#   Form 2 (proving): canonical_user/ (observation only — no sync target)
#   Form 3 (live):    ~/.claude/ (the installed runtime)
#
# Registered as: PostToolUse hook with matcher "Edit|Write"
# Input: JSON on stdin with tool_input.file_path
# Output: stdout drift warning (shown to user if non-empty)

set -euo pipefail

# Wire cutter — emergency kill switch
[ -f ~/.claude/wire-cutter.sh ] && source ~/.claude/wire-cutter.sh && wire_check sync_weigh

# Resolve the check script: installed location first, then canonical fallback
CHECK_SCRIPT=""
for candidate in \
    "$HOME/.claude/hooks/sync-weigh-check.py" \
    "${CLAUDE_PROJECT_DIR:-$(pwd)}/canonical_developer/context-grapple-gun/cgg-runtime/hooks/sync-weigh-check.py"; do
    [ -f "$candidate" ] && CHECK_SCRIPT="$candidate" && break
done

# Fast exit if check script not found
[ -z "$CHECK_SCRIPT" ] && exit 0

# Pipe stdin through to the python check script
python3 "$CHECK_SCRIPT"
