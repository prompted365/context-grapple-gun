#!/bin/bash
# CGG v4 — SessionStart canonical governance runtime entrypoint
#
# Features:
# - Zone-root-anchored governance IO (all paths resolve from .ticzone, never cwd)
# - Plugin-root-anchored script resolution (bundled runtime assets)
# - Project-scoped plan discovery + trigger extraction
# - Block-aware CogPR counter (inline tags + queue.jsonl)
# - Signal store scanning (single-pass Python dedup, latest-entry-per-ID)
# - Parallel session awareness
# - CPR extract backfill + enrichment scanner (if scripts exist)
# - Physical tic count anchoring
#
# Constitutional principles:
# - Signals do not expire. Only resolved/dismissed are terminal.
# - Tic count is the time authority. Timestamps are observability only.
# - Warrant eligibility is kind-gated (configurable via .ticzone).
cat > /dev/null

# ============================================================================
# Phase 1: Root Anchoring
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

# Audit-logs path (read from .ticzone if available, default "audit-logs")
AUDIT_LOGS_REL=$(python3 -c "
import json
try:
    tz = json.load(open('$ZONE_ROOT/.ticzone'))
    print(tz.get('audit_logs_path', 'audit-logs'))
except: print('audit-logs')
" 2>/dev/null || echo "audit-logs")
AUDIT_LOGS="$ZONE_ROOT/$AUDIT_LOGS_REL"

PROJECT_DIR="$ZONE_ROOT"
PROJECT_KEY=$(echo "$PROJECT_DIR" | sed 's|/|-|g')

# ============================================================================
# Plan discovery + trigger extraction
# ============================================================================

PROCESSED_IDS="$HOME/.claude/cgg-processed-handoff-ids.txt"
touch "$PROCESSED_IDS"
FLAG_DIR="${TMPDIR:-/tmp}/claude_cgg/$PROJECT_KEY"
CGG_MSG=""
HANDOFF_ID=""
LATEST_PLAN=""

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
    TRIGGER_MSG="[CGG EVALUATION PENDING: $EXPECTED CogPR flags extracted from handoff $HANDOFF_ID]"
  fi
fi

# ============================================================================
# CogPR counting: inline blocks + queue.jsonl
# ============================================================================

# Block-aware CogPR counter for inline <!-- --agnostic-candidate --> blocks
count_pending_cprs() {
  awk '
    /<!-- --agnostic-candidate/ { in_block=1; pending=0; example=0 }
    in_block && /status:[[:space:]]*"pending"/ { pending=1 }
    in_block && /status:[[:space:]]*"enrichment_eligible"/ { pending=1 }
    in_block && /status:[[:space:]]*"example"/ { example=1 }
    in_block && /-->/ { if (pending && !example) c++; in_block=0 }
    END { print c+0 }
  ' "$1"
}

CPR_COUNT=0
if [ -d "$PROJECT_DIR" ]; then
  # Build find exclusions from .ticignore (always exclude .git)
  FIND_EXCLUDES=(-not -path "*/.git/*")
  TICIGNORE="$PROJECT_DIR/.ticignore"
  if [ -f "$TICIGNORE" ]; then
    while IFS= read -r pat; do
      pat=$(echo "$pat" | sed 's/#.*//;s/^[[:space:]]*//;s/[[:space:]]*$//;s|/$||')
      [ -z "$pat" ] && continue
      case "$pat" in *\**|*\?*) continue ;; esac
      FIND_EXCLUDES+=(-not -path "*/$pat/*")
    done < "$TICIGNORE"
  else
    FIND_EXCLUDES+=(-not -path "*/vendor/*" -not -path "*/node_modules/*" -not -path "*/.claude/skills/*")
  fi

  while IFS= read -r f; do
    _c=$(count_pending_cprs "$f")
    CPR_COUNT=$(( CPR_COUNT + _c ))
  done < <(find "$PROJECT_DIR" \( -name "CLAUDE.md" -o -name "MEMORY.md" \) "${FIND_EXCLUDES[@]}" 2>/dev/null)
fi

# Auto-memory (gitignored but governance-visible)
MEMORY_FILE="$HOME/.claude/projects/$PROJECT_KEY/memory/MEMORY.md"
if [ -f "$MEMORY_FILE" ]; then
  _mem_count=$(count_pending_cprs "$MEMORY_FILE")
  CPR_COUNT=$(( CPR_COUNT + _mem_count ))
fi

# Queue.jsonl counting (latest-entry-per-ID, non-terminal statuses)
QUEUE_FILE="$AUDIT_LOGS/cprs/queue.jsonl"
QUEUE_COUNT=0
if [ -f "$QUEUE_FILE" ]; then
  QUEUE_COUNT=$(python3 -c "
import json
entries = {}
for line in open('$QUEUE_FILE'):
    try:
        d = json.loads(line.strip())
        eid = d.get('id','')
        if eid: entries[eid] = d
    except: pass
pending = [e for e in entries.values()
           if e.get('status','') in ('extracted','tic_gated','enrichment_needed',
                                      'enrichment_in_progress','enrichment_eligible','promotable')]
print(len(pending))
" 2>/dev/null || echo "0")
fi

TOTAL_CPRS=$(( CPR_COUNT + QUEUE_COUNT ))

# ============================================================================
# CPR extract backfill — script resolution order:
#   1. $ZONE_ROOT/scripts/<name>.py (project override)
#   2. $CGG_SCRIPTS_DIR/<name>.py (plugin-root-anchored bundled script)
#   3. $HOME/.claude/cgg-runtime/scripts/<name>.py (global install fallback)
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

CPR_EXTRACT=$(resolve_script "cpr-extract.py")
if [ -n "$CPR_EXTRACT" ] && [ "$TOTAL_CPRS" -gt 0 ]; then
  python3 "$CPR_EXTRACT" --project-dir "$PROJECT_DIR" 2>/dev/null || true
fi

# ============================================================================
# Enrichment scanner (background, nonblocking)
# ============================================================================

HOLDING_CPRS=0
if [ -f "$QUEUE_FILE" ]; then
  HOLDING_CPRS=$(python3 -c "
import json
entries = {}
for line in open('$QUEUE_FILE'):
    try:
        d = json.loads(line.strip())
        eid = d.get('id','')
        if eid: entries[eid] = d
    except: pass
holding = [e for e in entries.values()
           if e.get('status','') in ('enrichment_needed','enrichment_eligible')]
print(len(holding))
" 2>/dev/null || echo "0")
fi

ENRICHMENT_MSG=""
ENRICHMENT_SCANNER=$(resolve_script "cpr-enrichment-scanner.py")
if [ -n "$ENRICHMENT_SCANNER" ] && [ "$HOLDING_CPRS" -gt 0 ]; then
  python3 "$ENRICHMENT_SCANNER" --project-dir "$PROJECT_DIR" > /dev/null 2>&1 &
  ENRICHMENT_MSG="[ENRICHMENT: scanning $HOLDING_CPRS holding CogPRs in background]"
fi

# ============================================================================
# Physical tic count (zone-root-anchored)
# ============================================================================

TIC_DIR="$AUDIT_LOGS/tics"
TIC_COUNT=0
if [ -d "$TIC_DIR" ]; then
  TIC_COUNT=$(python3 -c "
import json, glob
count = 0
for f in sorted(glob.glob('$TIC_DIR/*.jsonl')):
    for line in open(f):
        try:
            if json.loads(line).get('type') == 'tic': count += 1
        except: pass
print(count)
" 2>/dev/null || echo "0")
fi

# ============================================================================
# Build handoff context
# ============================================================================

if [ -n "$LATEST_PLAN" ]; then
  NEXT_ACTIONS=$(awk '/^## Next Actions/,/^## [^N]/' "$LATEST_PLAN" 2>/dev/null | head -20 | sed 's/"/\\"/g' | tr '\n' ' ')
  if [ -n "$NEXT_ACTIONS" ] && [ ${#NEXT_ACTIONS} -gt 20 ]; then
    CGG_MSG="[CGG HANDOFF NEXT ACTIONS: $NEXT_ACTIONS] [Full plan if needed: $LATEST_PLAN]"
  else
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
if [ "$TOTAL_CPRS" -gt 0 ]; then
  CGG_MSG="$CGG_MSG [CPR QUEUE: $TOTAL_CPRS pending ($CPR_COUNT inline + $QUEUE_COUNT in queue.jsonl). /review when ready.]"
fi
if [ -n "$ENRICHMENT_MSG" ]; then
  CGG_MSG="$CGG_MSG $ENRICHMENT_MSG"
fi

# ============================================================================
# Signal store scanning (constitutional: no expired status, acoustic decay)
# ============================================================================

SIGNAL_DIR="$AUDIT_LOGS/signals"
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
# Signals never expire — only count active/acknowledged/working
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

# ============================================================================
# Parallel session awareness
# ============================================================================

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

# ============================================================================
# Combine all context
# ============================================================================

FULL_MSG=""
[ -n "$CGG_MSG" ] && FULL_MSG="$CGG_MSG"
[ -n "$SIREN_MSG" ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }$SIREN_MSG"
[ -n "$PARALLEL_MSG" ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }$PARALLEL_MSG"
[ "$TIC_COUNT" -gt 0 ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }[TIC: #$TIC_COUNT]"

if [ -n "$FULL_MSG" ]; then
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"$FULL_MSG\"}}"
fi

exit 0
