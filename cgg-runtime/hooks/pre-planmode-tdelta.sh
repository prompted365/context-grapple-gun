#!/usr/bin/env bash
# pre-planmode-tdelta.sh — Thin shell wrapper that pipes stdin to the real hook
# Fires on PreToolUse:EnterPlanMode
# invariant: do not rely on shell aliases inside hooks — call the real binary

set -euo pipefail

# Resolve the real binary relative to this wrapper — no hardcoded root.
# Works whether fired from canonical source or the installed ~/.claude copy
# (runtime-sync keeps the .py sibling to this wrapper in both layouts).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pass stdin through to the Python hook
exec python3 "$DIR/cadence-plan-submit.py"
