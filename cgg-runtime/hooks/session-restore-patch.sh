#!/bin/bash
# CGG v2 — SessionStart hook PATCH
# Add this logic to your existing SessionStart hook (session-restore.sh).
# If you don't have one, use this as your complete SessionStart hook.
#
# This script discovers project-scoped plan files with CGG triggers,
# extracts them to flag files for the UserPromptSubmit gate, and
# counts pending CPR flags for the session banner.
cat > /dev/null

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PROJECT_KEY=$(echo "$PROJECT_DIR" | sed 's|/|-|g')

# --- CGG v2: Project-scoped plan discovery + trigger extraction ---
PROCESSED_IDS="$HOME/.claude/cgg-processed-handoff-ids.txt"
touch "$PROCESSED_IDS"
FLAG_DIR="${TMPDIR:-/tmp}/claude_cgg/$PROJECT_KEY"
CGG_MSG=""
HANDOFF_ID=""
LATEST_PLAN=""

# Search for plan files in the project's Claude directory
PLAN_DIR="$HOME/.claude/projects/$PROJECT_KEY"

if [ -d "$PLAN_DIR" ]; then
  for PLAN_FILE in $(find "$PLAN_DIR" -maxdepth 2 -name "*.md" -newer "$PROCESSED_IDS" 2>/dev/null | sort -r | head -10); do
    if grep -q "cgg-handoff" "$PLAN_FILE" 2>/dev/null; then
      PLAN_PROJECT=$(grep 'project_dir:' "$PLAN_FILE" 2>/dev/null | head -1 | sed 's/.*project_dir: *"\{0,1\}\([^"]*\)"\{0,1\}/\1/' | tr -d ' ')
      if [ "$PLAN_PROJECT" = "$PROJECT_DIR" ]; then
        if grep -q "cgg-evaluate" "$PLAN_FILE" 2>/dev/null; then
          HANDOFF_ID=$(grep 'handoff_id:' "$PLAN_FILE" 2>/dev/null | head -1 | sed 's/.*handoff_id: *"\{0,1\}\([^"]*\)"\{0,1\}/\1/' | tr -d ' ')
          if [ -n "$HANDOFF_ID" ] && ! grep -qF "$HANDOFF_ID" "$PROCESSED_IDS" 2>/dev/null; then
            LATEST_PLAN="$PLAN_FILE"
            break
          fi
        elif [ -z "$LATEST_PLAN" ]; then
          LATEST_PLAN="$PLAN_FILE"
        fi
      fi
    fi
  done
fi

# Extract trigger to flag files if unprocessed
TRIGGER_MSG=""
if [ -n "$LATEST_PLAN" ] && [ -n "$HANDOFF_ID" ]; then
  TRIGGER_BLOCK=$(awk '/<!-- cgg-evaluate/,/-->/' "$LATEST_PLAN" 2>/dev/null)
  if [ -n "$TRIGGER_BLOCK" ]; then
    EXPECTED=$(echo "$TRIGGER_BLOCK" | grep 'pending_cprs_expected:' | grep -o '[0-9]*')
    [ -z "$EXPECTED" ] && EXPECTED=0
    mkdir -p "$FLAG_DIR"
    echo "$TRIGGER_BLOCK" > "$FLAG_DIR/pending-trigger.txt"
    echo "$HANDOFF_ID" > "$FLAG_DIR/pending-handoff-id.txt"
    TRIGGER_MSG="[CGG EVALUATION PENDING: $EXPECTED CPR flags extracted from handoff $HANDOFF_ID]"
  fi
fi

# Count pending CPR flags
CPR_COUNT=0
if [ -d "$PROJECT_DIR" ]; then
  _count=$(grep -r "agnostic-candidate" "$PROJECT_DIR" --include="*.md" 2>/dev/null | grep -c "status.*pending" 2>/dev/null) || true
  CPR_COUNT=$(( ${_count:-0} ))
fi
MEMORY_FILE="$HOME/.claude/projects/$PROJECT_KEY/memory/MEMORY.md"
if [ -f "$MEMORY_FILE" ]; then
  _mem_count=$(grep -c "agnostic-candidate" "$MEMORY_FILE" 2>/dev/null) || true
  CPR_COUNT=$(( CPR_COUNT + ${_mem_count:-0} ))
fi

# Build CGG context message
if [ -n "$LATEST_PLAN" ]; then
  CGG_MSG="[CGG CHARTER: Read $LATEST_PLAN]"
fi
if [ -n "$TRIGGER_MSG" ]; then
  CGG_MSG="$CGG_MSG $TRIGGER_MSG"
fi
if [ "$CPR_COUNT" -gt 0 ]; then
  CGG_MSG="$CGG_MSG [CPR QUEUE: $CPR_COUNT pending flags. /grapple when ready.]"
fi

# Output (append to your existing SessionStart output)
if [ -n "$CGG_MSG" ]; then
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"$CGG_MSG\"}}"
fi

exit 0
