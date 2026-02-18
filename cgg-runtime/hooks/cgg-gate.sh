#!/bin/bash
# CGG v3 — UserPromptSubmit one-shot trigger gate
# Fires ONCE per handoff: spawns ripple-assessor evaluation, then self-disarms.
# Called by UserPromptSubmit hook. Reads stdin (prompt JSON) but ignores content.
cat > /dev/null

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
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

# Inject additionalContext instructing Claude to spawn the ripple-assessor
PLAN_REF=""
if [ -n "$PLAN_PATH" ]; then
  PLAN_REF="Plan file: $PLAN_PATH"
else
  PLAN_REF="Plan file: not located (assessor should search for handoff_id: $HANDOFF_ID)"
fi

echo "{\"hookSpecificOutput\":{\"hookEventName\":\"UserPromptSubmit\",\"additionalContext\":\"[CGG TRIGGER FIRED] Spawn ripple-assessor agent (Task tool, subagent_type: ripple-assessor) BEFORE starting user work. $PLAN_REF. Expected CPR count: $EXPECTED_CPRS. Handoff ID: $HANDOFF_ID. The assessor will read the plan, evaluate pending CPR flags and active signals, and write proposals to ~/.claude/grapple-proposals/latest.md. Run it in the background so you can proceed with the user's request.\"}}"
exit 0
