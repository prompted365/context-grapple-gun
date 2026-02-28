#!/bin/bash
# CGG v3 — SessionStart hook PATCH
# Add this logic to your existing SessionStart hook (session-restore.sh).
# If you don't have one, use this as your complete SessionStart hook.
#
# This script discovers project-scoped plan files with CGG triggers,
# extracts them to flag files for the UserPromptSubmit gate,
# counts pending CPR flags, and scans the signal store for active signals.
#
# Signal scanning uses single-pass Python for dedup (latest-entry-per-ID-wins)
# instead of line-by-line bash parsing. Much faster on large signal stores.
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

# --- CGG v3: Signal Scanning (single-pass Python dedup) ---
SIGNAL_DIR="$PROJECT_DIR/audit-logs/signals"
SIREN_MSG=""
if [ -d "$SIGNAL_DIR" ]; then
  SIREN_MSG=$(python3 -c "
import json, glob, sys
signals = {}
warrants = {}
for f in sorted(glob.glob('$SIGNAL_DIR/*.jsonl')):
    for line in open(f):
        try:
            d = json.loads(line)
            eid = d.get('id', '')
            if not eid: continue
            if d.get('type') == 'signal':
                signals[eid] = d
            elif d.get('type') == 'warrant':
                warrants[eid] = d
        except: pass
active_sigs = [s for s in signals.values() if s.get('status') in ('active','acknowledged','working')]
active_wrns = [w for w in warrants.values() if w.get('status') in ('active','acknowledged')]
if not active_sigs and not active_wrns:
    sys.exit(0)
loudest = max(active_sigs, key=lambda s: s.get('volume',0), default=None)
parts = ['[SIREN: %d active signals, %d active warrants.' % (len(active_sigs), len(active_wrns))]
if loudest:
    parts.append('Loudest: %s (volume=%s, band=%s).' % (loudest.get('id','?'), loudest.get('volume',0), loudest.get('band','?')))
parts.append('/siren when ready.]')
print(' '.join(parts))
" 2>/dev/null || true)
fi

# --- Parallel context awareness (project-filtered) ---
SESSION_META="$HOME/.claude/usage-data/session-meta"
PARALLEL_MSG=""
if [ -d "$SESSION_META" ]; then
  RECENT_COUNT=$(python3 -c "
import json, glob, time, sys
now = time.time()
count = 0
for f in sorted(glob.glob('$SESSION_META/*.json'), key=lambda x: -__import__('os').path.getmtime(x))[:30]:
    age = now - __import__('os').path.getmtime(f)
    if age > 7200: break
    try:
        d = json.load(open(f))
        if d.get('project_path','') == '$PROJECT_DIR':
            count += 1
    except: pass
print(count)
" 2>/dev/null || echo "0")
  if [ "$RECENT_COUNT" -gt 1 ]; then
    PARALLEL_MSG="[PARALLEL: $RECENT_COUNT recent sessions on this project in last 2h. Files may have shifted since last handoff.]"
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
