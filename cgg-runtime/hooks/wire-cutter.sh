#!/usr/bin/env bash
# CGG Wire Cutter — emergency kill switch for hooks, loops, and emitters
#
# Usage in any hook:
#   source ~/.claude/wire-cutter.sh && wire_check [scope]
#
# Scopes:
#   all         — kill everything (global panic)
#   hooks       — kill all hooks
#   signals     — kill signal emission only
#   mandates    — kill mandate emission only
#   session     — kill session-restore hook only
#   gate        — kill cgg-gate hook only
#   microscan   — kill posttool-microscan only
#   sync        — kill post-commit-sync only
#   loops       — kill all /loop processes
#
# Arm:    touch ~/.claude/.wire-cut-{scope}
# Disarm: rm ~/.claude/.wire-cut-{scope}
# Status: wire_status (prints all armed scopes)
#
# Example:
#   touch ~/.claude/.wire-cut-signals    # stop all signal emission
#   touch ~/.claude/.wire-cut-all        # full panic stop
#   rm ~/.claude/.wire-cut-all           # resume

WIRE_CUT_DIR="${HOME}/.claude"

wire_check() {
  local scope="${1:-all}"

  # Global kill switch
  if [ -f "$WIRE_CUT_DIR/.wire-cut-all" ]; then
    exit 0
  fi

  # Hooks master switch
  if [ "$scope" != "loops" ] && [ -f "$WIRE_CUT_DIR/.wire-cut-hooks" ]; then
    exit 0
  fi

  # Scope-specific switch
  if [ -f "$WIRE_CUT_DIR/.wire-cut-${scope}" ]; then
    exit 0
  fi
}

wire_status() {
  local found=0
  for f in "$WIRE_CUT_DIR"/.wire-cut-*; do
    [ -e "$f" ] 2>/dev/null || continue
    scope="${f##*.wire-cut-}"
    echo "ARMED: $scope"
    found=1
  done
  [ "$found" -eq 0 ] && echo "All clear — no wire cuts armed."
}

# Signal-emission-specific guard (call from inbox-envelope.py wrapper or inline)
wire_check_signals() {
  if [ -f "$WIRE_CUT_DIR/.wire-cut-all" ] || \
     [ -f "$WIRE_CUT_DIR/.wire-cut-signals" ]; then
    return 1  # blocked
  fi
  return 0    # allowed
}
