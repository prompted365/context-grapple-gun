#!/bin/bash
# CGG v3 — SessionStart hook PATCH
# Add this logic to your existing SessionStart hook (session-restore.sh).
# If you don't have one, use this as your complete SessionStart hook.
#
# This script discovers project-scoped plan files with CGG triggers,
# extracts them to flag files for the UserPromptSubmit gate,
# counts pending CPR flags, and scans the signal store for active signals.
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

# Build CGG context message — extract Next Actions inline instead of forcing full plan re-read
if [ -n "$LATEST_PLAN" ]; then
  # Extract ## Next Actions section (lighter than full plan read)
  NEXT_ACTIONS=$(awk '/^## Next Actions/,/^## [^N]/' "$LATEST_PLAN" 2>/dev/null | head -20 | sed 's/"/\\"/g' | tr '\n' ' ')
  if [ -n "$NEXT_ACTIONS" ] && [ ${#NEXT_ACTIONS} -gt 20 ]; then
    CGG_MSG="[CGG HANDOFF NEXT ACTIONS: $NEXT_ACTIONS] [Full plan if needed: $LATEST_PLAN]"
  else
    # Fallback: try ## Not Started or ## Working State for compact context
    WORKING=$(awk '/^### Not Started/,/^### [^N]/' "$LATEST_PLAN" 2>/dev/null | head -15 | sed 's/"/\\"/g' | tr '\n' ' ')
    if [ -n "$WORKING" ] && [ ${#WORKING} -gt 20 ]; then
      CGG_MSG="[CGG HANDOFF REMAINING: $WORKING] [Full plan if needed: $LATEST_PLAN]"
    else
      CGG_MSG="[CGG CHARTER: Read $LATEST_PLAN]"
    fi
  fi
fi
if [ -n "$TRIGGER_MSG" ]; then
  CGG_MSG="$CGG_MSG $TRIGGER_MSG"
fi
if [ "$CPR_COUNT" -gt 0 ]; then
  CGG_MSG="$CGG_MSG [CPR QUEUE: $CPR_COUNT pending flags. /grapple when ready.]"
fi

# --- CGG v3: Signal Scanning ---
SIGNAL_DIR="$PROJECT_DIR/audit-logs/signals"
SIREN_MSG=""
if [ -d "$SIGNAL_DIR" ]; then
  ACTIVE_SIGNALS=0
  ACTIVE_WARRANTS=0
  LOUDEST_ID="none"
  LOUDEST_VOL=0
  LOUDEST_BAND=""

  for JSONL_FILE in "$SIGNAL_DIR"/*.jsonl; do
    [ -f "$JSONL_FILE" ] || continue
    while IFS= read -r LINE; do
      STATUS=$(echo "$LINE" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('status',''))" 2>/dev/null)
      TYPE=$(echo "$LINE" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('type',''))" 2>/dev/null)
      if [ "$STATUS" = "active" ]; then
        if [ "$TYPE" = "signal" ]; then
          ACTIVE_SIGNALS=$(( ACTIVE_SIGNALS + 1 ))
          VOL=$(echo "$LINE" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('volume',0))" 2>/dev/null)
          if [ "$VOL" -gt "$LOUDEST_VOL" ] 2>/dev/null; then
            LOUDEST_VOL="$VOL"
            LOUDEST_ID=$(echo "$LINE" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('id','?'))" 2>/dev/null)
            LOUDEST_BAND=$(echo "$LINE" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('band','?'))" 2>/dev/null)
          fi
        elif [ "$TYPE" = "warrant" ]; then
          ACTIVE_WARRANTS=$(( ACTIVE_WARRANTS + 1 ))
        fi
      fi
    done < "$JSONL_FILE"
  done

  if [ "$ACTIVE_SIGNALS" -gt 0 ] || [ "$ACTIVE_WARRANTS" -gt 0 ]; then
    SIREN_MSG="[SIREN: $ACTIVE_SIGNALS active signals, $ACTIVE_WARRANTS active warrants."
    if [ "$LOUDEST_VOL" -gt 0 ]; then
      SIREN_MSG="$SIREN_MSG Loudest: $LOUDEST_ID (volume=$LOUDEST_VOL, band=$LOUDEST_BAND)."
    fi
    SIREN_MSG="$SIREN_MSG /siren when ready.]"
  fi
fi

# --- Parallel context awareness ---
SESSION_META="$HOME/.claude/usage-data/session-meta"
PARALLEL_MSG=""
if [ -d "$SESSION_META" ]; then
  NOW=$(date +%s)
  RECENT_COUNT=0
  for META_FILE in $(ls -t "$SESSION_META"/*.json 2>/dev/null | head -20); do
    META_AGE=$(( NOW - $(stat -f%m "$META_FILE" 2>/dev/null || echo 0) ))
    [ "$META_AGE" -gt 7200 ] && break
    RECENT_COUNT=$(( RECENT_COUNT + 1 ))
  done
  if [ "$RECENT_COUNT" -gt 1 ]; then
    PARALLEL_MSG="[PARALLEL: $RECENT_COUNT recent sessions touched this project in last 2h. Files may have shifted since last handoff.]"
  fi
fi

# Combine all context messages
FULL_MSG=""
if [ -n "$CGG_MSG" ]; then
  FULL_MSG="$CGG_MSG"
fi
if [ -n "$SIREN_MSG" ]; then
  if [ -n "$FULL_MSG" ]; then
    FULL_MSG="$FULL_MSG $SIREN_MSG"
  else
    FULL_MSG="$SIREN_MSG"
  fi
fi
if [ -n "$PARALLEL_MSG" ]; then
  if [ -n "$FULL_MSG" ]; then
    FULL_MSG="$FULL_MSG $PARALLEL_MSG"
  else
    FULL_MSG="$PARALLEL_MSG"
  fi
fi

# Output (append to your existing SessionStart output)
if [ -n "$FULL_MSG" ]; then
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"$FULL_MSG\"}}"
fi

exit 0
