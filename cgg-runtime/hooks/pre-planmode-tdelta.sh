#!/usr/bin/env bash
# pre-planmode-tdelta.sh — Thin shell wrapper that pipes stdin to the real hook
# Fires on PreToolUse:EnterPlanMode
# invariant: do not rely on shell aliases inside hooks — call the real binary

set -euo pipefail

# Pass stdin through to the Python hook
exec python3 /Users/breydentaylor/canonical/canonical_developer/context-grapple-gun/cgg-runtime/hooks/cadence-plan-submit.py
