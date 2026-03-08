#!/bin/bash
# CGG v5 — UserPromptSubmit gate
# Two independent branches:
#   A) Trigger branch: fires ONCE per handoff — runs ripple-assessor, then self-disarms
#   B) Mandate branch: checks for pending Mogul mandates independent of trigger state
#
# Assessment strategy (deterministic first, LLM fallback):
#   1. If ripple-assessor.py exists → run it directly (fast, deterministic)
#   2. Otherwise → instruct Claude to spawn the ripple-assessor agent (original behavior)
#
# Script resolution order:
#   1. $ZONE_ROOT/scripts/<name>.py (project override)
#   2. $CGG_SCRIPTS_DIR/<name>.py (plugin-root-anchored bundled script)
#   3. $HOME/.claude/cgg-runtime/scripts/<name>.py (global install fallback)
#
# Mandate lifecycle:
#   pending → running → consumed | failed
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
TIMESTAMP=$(date -Iseconds)

# ============================================================================
# Resolve audit-logs path from .ticzone BEFORE any path construction
# ============================================================================

AUDIT_LOGS_REL=$(python3 -c "
import json
try:
    tz = json.load(open('$ZONE_ROOT/.ticzone'))
    print(tz.get('audit_logs_path', 'audit-logs'))
except: print('audit-logs')
" 2>/dev/null || echo "audit-logs")

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
# Branch A: Mandate check — independent of trigger-file state
# ============================================================================

MANDATE_FILE="$ZONE_ROOT/$AUDIT_LOGS_REL/mogul/mandates/current.json"
MANDATE_OUTPUT=""

if [ -f "$MANDATE_FILE" ]; then
  # Read mandate status and cycles in a single Python call
  MANDATE_INFO=$(python3 -c "
import json, sys
try:
    m = json.load(open('$MANDATE_FILE'))
    status = m.get('status', 'pending')
    mandate_id = m.get('mandate_id', 'unknown')
    cycles = m.get('cycle_request', {}).get('run_now', [])
    heavy = [c for c in cycles if c not in ('queue_refresh', 'signal_scan')]
    all_cycles = ','.join(cycles) if cycles else ''
    heavy_str = ','.join(heavy) if heavy else ''
    print(f'{status}|{mandate_id}|{all_cycles}|{heavy_str}')
except: print('error|||')
" 2>/dev/null)

  MANDATE_STATUS=$(echo "$MANDATE_INFO" | cut -d'|' -f1)
  MANDATE_ID=$(echo "$MANDATE_INFO" | cut -d'|' -f2)
  ALL_CYCLES=$(echo "$MANDATE_INFO" | cut -d'|' -f3)
  HEAVY_CYCLES=$(echo "$MANDATE_INFO" | cut -d'|' -f4)

  if [ "$MANDATE_STATUS" = "pending" ]; then
    if [ -n "$HEAVY_CYCLES" ]; then
      # Look for estate-local runner; fallback to LLM instruction
      MOGUL_RUNNER=$(resolve_script "mogul-runner.sh")
      if [ -n "$MOGUL_RUNNER" ] && [ -x "$MOGUL_RUNNER" ]; then
        # Runner exists — spawn it. Runner owns the full pending→running→consumed lifecycle.
        # Gate does NOT touch mandate status (race condition fix: runner is sole state owner).
        echo "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"mogul_mandate_activated\",\"mandate_id\":\"$MANDATE_ID\",\"cycles\":\"$HEAVY_CYCLES\",\"status\":\"pending\"}" >> "$META_LOG"

        MOGUL_LOG_DIR="$ZONE_ROOT/$AUDIT_LOGS_REL/mogul/cycle-reports"
        mkdir -p "$MOGUL_LOG_DIR"
        "$MOGUL_RUNNER" > "$MOGUL_LOG_DIR/$(date +%Y-%m-%dT%H%M%S)-runner-log.txt" 2>&1 &
        echo "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"mogul_runner_spawned\",\"mandate_id\":\"$MANDATE_ID\",\"cycles\":\"$HEAVY_CYCLES\",\"pid\":$!}" >> "$META_LOG"
        MANDATE_OUTPUT="[MOGUL MANDATE: runner spawn] mogul-runner.sh executing governance cycles ($HEAVY_CYCLES) in background (PID $!). Non-blocking."
      else
        # No runner — leave status pending, surface for LLM/manual execution
        echo "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"mogul_mandate_surfaced\",\"mandate_id\":\"$MANDATE_ID\",\"cycles\":\"$HEAVY_CYCLES\",\"status\":\"pending\"}" >> "$META_LOG"
        MANDATE_OUTPUT="[MOGUL MANDATE PENDING] Heavy governance cycles due: $HEAVY_CYCLES. Spawn Mogul agent (Task tool, subagent_type: mogul, run_in_background: true) to execute mandated cycles. Mandate at: $MANDATE_FILE. Mandate ID: $MANDATE_ID. Non-blocking."
      fi
    elif [ -n "$ALL_CYCLES" ]; then
      # Lightweight cycles only — surface but don't spawn
      MANDATE_OUTPUT="[MOGUL MANDATE: lightweight] Pending cycles: $ALL_CYCLES (no heavy work — no spawn needed)."
    fi
  elif [ "$MANDATE_STATUS" = "running" ]; then
    MANDATE_OUTPUT="[MOGUL MANDATE: in-flight] Mandate $MANDATE_ID still running (cycles: $ALL_CYCLES)."
  elif [ "$MANDATE_STATUS" = "failed" ]; then
    MANDATE_OUTPUT="[MOGUL MANDATE: FAILED] Mandate $MANDATE_ID failed (cycles: $ALL_CYCLES). Needs investigation."
    echo "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"mogul_mandate_failed_surfaced\",\"mandate_id\":\"$MANDATE_ID\",\"cycles\":\"$ALL_CYCLES\"}" >> "$META_LOG"
  else
    # consumed or unknown — no output needed
    :
  fi
fi

# ============================================================================
# Branch B: Trigger-based assessor spawn — independent of mandate
# ============================================================================

HAS_TRIGGER=false
ASSESSOR_OUTPUT=""

if [ -f "$TRIGGER_FILE" ]; then
  HAS_TRIGGER=true

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
  echo "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"trigger_fired\",\"handoff_id\":\"$HANDOFF_ID\",\"expected_cprs\":$EXPECTED_CPRS,\"plan_path\":\"$PLAN_PATH\",\"project\":\"$PROJECT_DIR\"}" >> "$META_LOG"

  # Try deterministic assessor first
  DETERMINISTIC_ASSESSOR=$(resolve_script "ripple-assessor.py")
  if [ -n "$DETERMINISTIC_ASSESSOR" ]; then
    python3 "$DETERMINISTIC_ASSESSOR" \
      --plan "$PLAN_PATH" \
      --project "$PROJECT_DIR" \
      --output "$HOME/.claude/grapple-proposals/latest.md" \
      2>/dev/null &

    echo "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"deterministic_assessor_spawned\",\"handoff_id\":\"$HANDOFF_ID\",\"assessor\":\"$DETERMINISTIC_ASSESSOR\"}" >> "$META_LOG"
    ASSESSOR_OUTPUT="[CGG TRIGGER FIRED] Deterministic ripple-assessor running in background. Proposals will appear at ~/.claude/grapple-proposals/latest.md. /review when ready."
  else
    # Fall back to LLM agent spawn
    PLAN_REF=""
    if [ -n "$PLAN_PATH" ]; then
      PLAN_REF="Plan file: $PLAN_PATH"
    else
      PLAN_REF="Plan file: not located (assessor should search for handoff_id: $HANDOFF_ID)"
    fi
    ASSESSOR_OUTPUT="[CGG TRIGGER FIRED] Spawn ripple-assessor agent (Task tool, subagent_type: ripple-assessor) BEFORE starting user work. $PLAN_REF. Expected CogPR count: $EXPECTED_CPRS. Handoff ID: $HANDOFF_ID. The assessor will read the plan, evaluate pending CogPR flags and active signals, and write proposals to ~/.claude/grapple-proposals/latest.md. Run it in the background so you can proceed with the user's request."
  fi
fi

# ============================================================================
# Output — combine both branches into a single hook response
# ============================================================================

# If neither branch produced output, fast exit
if [ -z "$MANDATE_OUTPUT" ] && [ -z "$ASSESSOR_OUTPUT" ]; then
  exit 0
fi

# Combine outputs
COMBINED=""
if [ -n "$ASSESSOR_OUTPUT" ]; then
  COMBINED="$ASSESSOR_OUTPUT"
fi
if [ -n "$MANDATE_OUTPUT" ]; then
  if [ -n "$COMBINED" ]; then
    COMBINED="$COMBINED $MANDATE_OUTPUT"
  else
    COMBINED="$MANDATE_OUTPUT"
  fi
fi

echo "{\"hookSpecificOutput\":{\"hookEventName\":\"UserPromptSubmit\",\"additionalContext\":\"$COMBINED\"}}"
exit 0
