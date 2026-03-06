#!/bin/bash
# CGG v4 — UserPromptSubmit one-shot trigger gate
# Fires ONCE per handoff: runs ripple-assessor evaluation, then self-disarms.
# Called by UserPromptSubmit hook. Reads stdin (prompt JSON) but ignores content.
#
# Assessment strategy (deterministic first, LLM fallback):
#   1. If ripple-assessor.py exists → run it directly (fast, deterministic)
#   2. Otherwise → instruct Claude to spawn the ripple-assessor agent (original behavior)
#
# Script resolution order:
#   1. $ZONE_ROOT/scripts/<name>.py (project override)
#   2. $CGG_SCRIPTS_DIR/<name>.py (plugin-root-anchored bundled script)
#   3. $HOME/.claude/cgg-runtime/scripts/<name>.py (global install fallback)
cat > /dev/null

# ============================================================================
# Root Anchoring
# ============================================================================

# Plugin-root anchor: canonical for finding bundled runtime assets
CGG_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
CGG_SCRIPTS_DIR="$CGG_PLUGIN_ROOT/cgg-runtime/scripts"

# Zone-root anchor: canonical for all governance data IO
resolve_zone_root() {
  local dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
  while [ "$dir" != "/" ]; do
    [ -f "$dir/.ticzone" ] && echo "$dir" && return 0
    dir=$(dirname "$dir")
  done
  git rev-parse --show-toplevel 2>/dev/null && return 0
  echo "$(pwd)" && echo "[CGG WARNING] No .ticzone found — falling back to cwd" >&2
}
ZONE_ROOT=$(resolve_zone_root)

PROJECT_DIR="$ZONE_ROOT"
PROJECT_KEY=$(echo "$PROJECT_DIR" | sed 's|/|-|g')
FLAG_DIR="${TMPDIR:-/tmp}/claude_cgg/$PROJECT_KEY"
TRIGGER_FILE="$FLAG_DIR/pending-trigger.txt"
HANDOFF_FILE="$FLAG_DIR/pending-handoff-id.txt"
PROCESSED_IDS="$HOME/.claude/cgg-processed-handoff-ids.txt"
META_LOG="$HOME/.claude/grapple-meta-log.jsonl"

# Fast exit: no pending trigger = no cost
[ ! -f "$TRIGGER_FILE" ] && exit 0

# Read trigger data
HANDOFF_ID=""
[ -f "$HANDOFF_FILE" ] && HANDOFF_ID=$(cat "$HANDOFF_FILE")
TRIGGER_DATA=$(cat "$TRIGGER_FILE")
EXPECTED_CPRS=$(echo "$TRIGGER_DATA" | grep -o 'pending_cprs_expected: *[0-9]*' | grep -o '[0-9]*')
[ -z "$EXPECTED_CPRS" ] && EXPECTED_CPRS=0

# Find the plan file that contains this handoff_id
PLAN_PATH=""
if [ -n "$HANDOFF_ID" ]; then
  PLAN_DIR="$HOME/.claude/projects/$PROJECT_KEY"
  if [ -d "$PLAN_DIR" ]; then
    PLAN_PATH=$(grep -rl "handoff_id.*$HANDOFF_ID" "$PLAN_DIR"/*.md 2>/dev/null | head -1)
  fi
  if [ -z "$PLAN_PATH" ]; then
    PLAN_PATH=$(grep -rl "handoff_id.*$HANDOFF_ID" "${TMPDIR:-/tmp}/claude_cgg/$PROJECT_KEY"/*.md 2>/dev/null | head -1)
  fi
fi

# One-shot: delete flag files immediately
rm -f "$TRIGGER_FILE" "$HANDOFF_FILE"

# Idempotency: record this handoff_id as processed
if [ -n "$HANDOFF_ID" ]; then
  echo "$HANDOFF_ID" >> "$PROCESSED_IDS"
fi

# Audit trail
TIMESTAMP=$(date -Iseconds)
echo "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"trigger_fired\",\"handoff_id\":\"$HANDOFF_ID\",\"expected_cprs\":$EXPECTED_CPRS,\"plan_path\":\"$PLAN_PATH\",\"project\":\"$PROJECT_DIR\"}" >> "$META_LOG"

# ============================================================================
# Script resolution
# ============================================================================

resolve_script() {
  local name="$1"
  for candidate in \
    "$ZONE_ROOT/scripts/$name" \
    "$CGG_SCRIPTS_DIR/$name" \
    "$HOME/.claude/cgg-runtime/scripts/$name"; do
    if [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# ============================================================================
# Assessment strategy — deterministic assessor first
# ============================================================================

DETERMINISTIC_ASSESSOR=$(resolve_script "ripple-assessor.py")
if [ -n "$DETERMINISTIC_ASSESSOR" ]; then
  python3 "$DETERMINISTIC_ASSESSOR" \
    --plan "$PLAN_PATH" \
    --project "$PROJECT_DIR" \
    --output "$HOME/.claude/grapple-proposals/latest.md" \
    2>/dev/null &

  echo "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"deterministic_assessor_spawned\",\"handoff_id\":\"$HANDOFF_ID\",\"assessor\":\"$DETERMINISTIC_ASSESSOR\"}" >> "$META_LOG"
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"UserPromptSubmit\",\"additionalContext\":\"[CGG TRIGGER FIRED] Deterministic ripple-assessor running in background. Proposals will appear at ~/.claude/grapple-proposals/latest.md. /review when ready.\"}}"
  exit 0
fi

# ============================================================================
# Mogul mandate spawn path — if mandate present and due, spawn non-blocking
# ============================================================================

MANDATE_FILE="$ZONE_ROOT/${AUDIT_LOGS_REL:-audit-logs}/mogul/mandates/current.json"
if [ -f "$MANDATE_FILE" ]; then
  MOGUL_CYCLES=$(python3 -c "
import json, sys
try:
    m = json.load(open('$MANDATE_FILE'))
    cycles = m.get('cycle_request', {}).get('run_now', [])
    # Filter out queue_refresh and signal_scan — those are lightweight, not spawn-worthy
    heavy = [c for c in cycles if c not in ('queue_refresh', 'signal_scan')]
    if heavy:
        print(','.join(heavy))
except: pass
" 2>/dev/null)

  if [ -n "$MOGUL_CYCLES" ]; then
    # Check mandate status — only spawn if pending (lifecycle-aware)
    MANDATE_STATUS=$(python3 -c "
import json
try:
    m = json.load(open('$MANDATE_FILE'))
    print(m.get('status', 'pending'))
except: print('pending')
" 2>/dev/null)

    if [ "$MANDATE_STATUS" = "pending" ]; then
      echo "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"mogul_mandate_detected\",\"cycles\":\"$MOGUL_CYCLES\",\"status\":\"$MANDATE_STATUS\"}" >> "$META_LOG"

      # Look for estate-local runner (operationTorque override); fallback to LLM instruction
      MOGUL_RUNNER="$ZONE_ROOT/scripts/mogul-runner.sh"
      if [ -x "$MOGUL_RUNNER" ]; then
        MOGUL_LOG_DIR="$ZONE_ROOT/${AUDIT_LOGS_REL:-audit-logs}/mogul/cycle-reports"
        mkdir -p "$MOGUL_LOG_DIR"
        "$MOGUL_RUNNER" > "$MOGUL_LOG_DIR/$(date +%Y-%m-%dT%H%M%S)-runner-log.txt" 2>&1 &
        echo "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"mogul_runner_spawned\",\"cycles\":\"$MOGUL_CYCLES\",\"pid\":$!}" >> "$META_LOG"
        echo "{\"hookSpecificOutput\":{\"hookEventName\":\"UserPromptSubmit\",\"additionalContext\":\"[MOGUL MANDATE: runner spawn] mogul-runner.sh executing governance cycles ($MOGUL_CYCLES) in background (PID $!). Non-blocking — proceed with user work.\"}}"
      else
        # Canonical portable fallback: instruct LLM to spawn agent
        echo "{\"hookSpecificOutput\":{\"hookEventName\":\"UserPromptSubmit\",\"additionalContext\":\"[MOGUL MANDATE PENDING] Heavy governance cycles due: $MOGUL_CYCLES. Spawn Mogul agent (Task tool, subagent_type: mogul, run_in_background: true) to execute mandated cycles. Mandate at: $MANDATE_FILE. Non-blocking — proceed with user work.\"}}"
      fi
    else
      echo "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"mogul_mandate_skipped\",\"status\":\"$MANDATE_STATUS\",\"cycles\":\"$MOGUL_CYCLES\"}" >> "$META_LOG"
    fi
    # Do NOT exit — still check for ripple-assessor trigger below
  fi
fi

# Audit-logs relative path for mandate (need to resolve before assessor section)
if [ -z "${AUDIT_LOGS_REL:-}" ]; then
  AUDIT_LOGS_REL=$(python3 -c "
import json
try:
    tz = json.load(open('$ZONE_ROOT/.ticzone'))
    print(tz.get('audit_logs_path', 'audit-logs'))
except: print('audit-logs')
" 2>/dev/null || echo "audit-logs")
fi

# Fall back to LLM agent spawn (original behavior)
PLAN_REF=""
if [ -n "$PLAN_PATH" ]; then
  PLAN_REF="Plan file: $PLAN_PATH"
else
  PLAN_REF="Plan file: not located (assessor should search for handoff_id: $HANDOFF_ID)"
fi

echo "{\"hookSpecificOutput\":{\"hookEventName\":\"UserPromptSubmit\",\"additionalContext\":\"[CGG TRIGGER FIRED] Spawn ripple-assessor agent (Task tool, subagent_type: ripple-assessor) BEFORE starting user work. $PLAN_REF. Expected CogPR count: $EXPECTED_CPRS. Handoff ID: $HANDOFF_ID. The assessor will read the plan, evaluate pending CogPR flags and active signals, and write proposals to ~/.claude/grapple-proposals/latest.md. Run it in the background so you can proceed with the user's request.\"}}"
exit 0
