#!/bin/bash
# CGG v5 — SessionStart canonical governance runtime entrypoint
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
# - Trigger-router integration (Phase 4): mandate routing via inbox delivery
#
# Constitutional principles:
# - Signals do not expire. Only resolved/dismissed are terminal.
# - Tic count is the time authority. Timestamps are observability only.
# - Warrant eligibility is kind-gated (configurable via .ticzone).
cat > /dev/null

# Wire cutter — emergency kill switch
[ -f ~/.claude/wire-cutter.sh ] && source ~/.claude/wire-cutter.sh && wire_check session

# ============================================================================
# Phase 1: Root Anchoring
# ============================================================================

# Plugin-root anchor: canonical for finding bundled runtime assets
CGG_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"

# Load atomic append library for JSONL-safe writes
ATOMIC_LIB="$CGG_PLUGIN_ROOT/cgg-runtime/scripts/lib/atomic-append.sh"
[ -f "$ATOMIC_LIB" ] && source "$ATOMIC_LIB"
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
max_counter = 0
for f in sorted(glob.glob('$TIC_DIR/*.jsonl')):
    for line in open(f):
        try:
            d = json.loads(line)
            if d.get('type') != 'tic': continue
            mode = d.get('count_mode', 'counted')
            if mode != 'counted': continue
            # Handle both old format (global_counter) and new format (global_counter_after)
            ca = d.get('global_counter_after', d.get('global_counter', 0))
            if ca > max_counter:
                max_counter = ca
        except: pass
print(max_counter)
" 2>/dev/null || echo "0")
fi

# ============================================================================
# Overdue cycle detection + Mogul mandate routing (Phase 4: trigger-router)
# ============================================================================
# SessionStart computes due cycles and routes a mogul.mandate trigger to
# Mogul's inbox via trigger-router.py. The trigger-router handles envelope
# creation, idempotency, dedup, and audit logging.
#
# Backward compatibility: current.json is still written as a fallback until
# inbox routing is validated (remove after 5 clean tics).

MANDATE_DIR="$AUDIT_LOGS/mogul/mandates"
MANDATE_HISTORY_DIR="$MANDATE_DIR/history"
MANDATE_FILE="$MANDATE_DIR/current.json"
MOGUL_MANDATE_MSG=""
INBOX_INJECTION=""

# ── Idempotency guard: skip mandate emission if one already exists for this tic ──
# Prevents mandate emission runaway when multiple sessions open at the same tic.
# Evidence: tic-87 produced 269 inbox messages from unguarded re-emission.
MANDATE_ALREADY_EXISTS=false
if [ -f "$MANDATE_FILE" ] && [ "$TIC_COUNT" -gt 0 ]; then
  EXISTING_TIC=$(python3 -c "
import json
try:
    m = json.load(open('$MANDATE_FILE'))
    t = m.get('tic_context', {}).get('current_tic', m.get('tic', 0))
    print(t)
except: print(0)
" 2>/dev/null || echo "0")
  if [ "$EXISTING_TIC" = "$TIC_COUNT" ]; then
    MANDATE_ALREADY_EXISTS=true
  fi
fi

if [ "$TIC_COUNT" -gt 0 ] && [ "$MANDATE_ALREADY_EXISTS" = "false" ]; then
  # Compute due cycles via estate_snapshot (MVOS L2) with inline fallback
  ESTATE_SNAPSHOT_PY="$ZONE_ROOT/$AUDIT_LOGS_REL/cpg/scripts/estate_snapshot.py"
  if [ -f "$ESTATE_SNAPSHOT_PY" ]; then
    DUE_CYCLES_CSV=$(ZONE_ROOT="$ZONE_ROOT" python3 "$ESTATE_SNAPSHOT_PY" --json 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    cycles = data.get('profile_selection', {}).get('cycles', ['queue_refresh', 'signal_scan'])
    # Also check mandate due-tic overrides
    import os
    prev = '$MANDATE_FILE'
    tic = $TIC_COUNT
    if os.path.isfile(prev):
        p = json.load(open(prev))
        tc = p.get('tic_context', {})
        if tc.get('memory_mining_due_tic') and tic >= tc['memory_mining_due_tic'] and 'memory_mining' not in cycles: cycles.append('memory_mining')
        if tc.get('pattern_mining_due_tic') and tic >= tc['pattern_mining_due_tic'] and 'pattern_mining' not in cycles: cycles.append('pattern_mining')
        if tc.get('ladder_audit_due_tic') and tic >= tc['ladder_audit_due_tic']:
            if 'ladder_audit' not in cycles: cycles.append('ladder_audit')
        if tc.get('deep_audit_due_tic') and tic >= tc['deep_audit_due_tic'] and 'deep_audit' not in cycles: cycles.append('deep_audit')
    print(','.join(set(cycles)))
except:
    print('queue_refresh,signal_scan')
" 2>/dev/null || echo "queue_refresh,signal_scan")
  else
    # Inline fallback when estate_snapshot.py not available
    DUE_CYCLES_CSV=$(python3 -c "
tic = $TIC_COUNT
cycles = ['queue_refresh', 'signal_scan']
if tic % 3 == 0: cycles.append('memory_mining')
if tic % 4 == 0: cycles.append('pattern_mining')
if tic % 5 == 0: cycles.extend(['ladder_audit', 'runtime_drift_check'])
if tic % 8 == 0: cycles.append('deep_audit')
import json, os
prev = '$MANDATE_FILE'
if os.path.isfile(prev):
    try:
        p = json.load(open(prev))
        tc = p.get('tic_context', {})
        if tc.get('memory_mining_due_tic') and tic >= tc['memory_mining_due_tic'] and 'memory_mining' not in cycles: cycles.append('memory_mining')
        if tc.get('pattern_mining_due_tic') and tic >= tc['pattern_mining_due_tic'] and 'pattern_mining' not in cycles: cycles.append('pattern_mining')
        if tc.get('ladder_audit_due_tic') and tic >= tc['ladder_audit_due_tic']:
            if 'ladder_audit' not in cycles: cycles.append('ladder_audit')
            if 'runtime_drift_check' not in cycles: cycles.append('runtime_drift_check')
        if tc.get('deep_audit_due_tic') and tic >= tc['deep_audit_due_tic'] and 'deep_audit' not in cycles: cycles.append('deep_audit')
    except: pass
print(','.join(set(cycles)))
" 2>/dev/null)
  fi

  if [ -n "$DUE_CYCLES_CSV" ]; then
    # ── Build mandate body JSON ──
    MANDATE_BODY_JSON=$(python3 -c "
import json
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
tic = $TIC_COUNT
cycles = '$DUE_CYCLES_CSV'.split(',')
body = {
    'mandate_id': f'tic-{tic}-{now.strftime(\"%Y%m%dT%H%M%S\")}',
    'tic': tic,
    'cycle_request': {'run_now': list(set(cycles)), 'reason': f'SessionStart at tic {tic}'},
    'tic_context': {'current_tic': tic, 'review_due_tic': tic+1,
        'memory_mining_due_tic': tic+(3-tic%3) if tic%3!=0 else tic+3,
        'pattern_mining_due_tic': tic+(4-tic%4) if tic%4!=0 else tic+4,
        'ladder_audit_due_tic': tic+(5-tic%5) if tic%5!=0 else tic+5,
        'deep_audit_due_tic': tic+(8-tic%8) if tic%8!=0 else tic+8},
    'estate_profile': 'standard',
}
print(json.dumps(body))
" 2>/dev/null)

    # ── Route via trigger-router (primary path) ──
    TRIGGER_ROUTER=$(resolve_script "trigger-router.py")
    SESSION_ID=$(python3 -c "import uuid; print(uuid.uuid4().hex[:12])" 2>/dev/null || echo "unknown")

    ROUTED=false
    if [ -n "$TRIGGER_ROUTER" ] && [ -n "$MANDATE_BODY_JSON" ]; then
      ROUTE_RESULT=$(python3 "$TRIGGER_ROUTER" \
        --zone-root "$ZONE_ROOT" \
        route \
        --trigger-type mogul.mandate \
        --source-event SessionStart \
        --producer "session-restore.sh" \
        --source-tic "$TIC_COUNT" \
        --subject "Mogul mandate — tic $TIC_COUNT" \
        --body "$MANDATE_BODY_JSON" \
        --session-id "$SESSION_ID" \
        2>/dev/null)

      ROUTE_STATUS=$(echo "$ROUTE_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
      if [ "$ROUTE_STATUS" = "routed" ]; then
        ROUTED=true
        DUE_CYCLES=$(echo "$MANDATE_BODY_JSON" | python3 -c "import json,sys; m=json.load(sys.stdin); print(', '.join(m['cycle_request']['run_now']))" 2>/dev/null)

        # ── Inbox scan for prompt injection + attention-debt (Phase 5) ──
        INBOX_SCANNER=$(resolve_script "inbox-envelope.py")
        if [ -n "$INBOX_SCANNER" ]; then
          INBOX_INJECTION=$(python3 "$INBOX_SCANNER" \
            --zone-root "$ZONE_ROOT" \
            scan \
            --entity ent_mogul \
            --format injection \
            --current-tic "$TIC_COUNT" \
            2>/dev/null)

          # Phase 5: Emit attention-debt signals for all stale inbox items
          python3 "$INBOX_SCANNER" \
            --zone-root "$ZONE_ROOT" \
            stale-check \
            --current-tic "$TIC_COUNT" \
            --emit-signals \
            > /dev/null 2>&1 || true
        fi

        # Use inbox injection as mandate message if available, else fallback format
        if [ -n "$INBOX_INJECTION" ]; then
          MOGUL_MANDATE_MSG="$INBOX_INJECTION"
        else
          MOGUL_MANDATE_MSG="[MOGUL MANDATE: due cycles=$DUE_CYCLES]"
        fi
      fi
    fi

    # ── Backward-compatible fallback: current.json + history JSONL ──
    # Always write current.json (consumed by cgg-gate.sh Branch A mandate check).
    # Remove this fallback block after 5 clean tics of inbox routing.
    MANDATE_WRITER=$(resolve_script "mandate-write.py")
    if [ -n "$MANDATE_WRITER" ]; then
      MANDATE_JSON=$(python3 "$MANDATE_WRITER" \
        --zone-root "$ZONE_ROOT" \
        --trigger-kind session_start \
        --trigger-source "cgg-runtime/hooks/session-restore.sh" \
        --tic "$TIC_COUNT" \
        --cycles "$DUE_CYCLES_CSV" \
        --audit-logs-rel "$AUDIT_LOGS_REL" \
        2>/dev/null)

      if [ -n "$MANDATE_JSON" ] && [ "$ROUTED" = "false" ]; then
        DUE_CYCLES=$(echo "$MANDATE_JSON" | python3 -c "import json,sys; m=json.load(sys.stdin); print(', '.join(m['cycle_request']['run_now']))" 2>/dev/null)
        MOGUL_MANDATE_MSG="[MOGUL MANDATE: due cycles=$DUE_CYCLES]"
      fi
    else
      # Inline fallback: build mandate JSON and write current.json + history
      MANDATE_JSON=$(python3 -c "
import json
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
tic = $TIC_COUNT
cycles = '$DUE_CYCLES_CSV'.split(',')
mandate = {
    'mandate_id': f'tic-{tic}-{now.strftime(\"%Y%m%dT%H%M%S\")}',
    'status': 'pending',
    'supersedes': [], 'merged_from': [],
    'actor': {'office': 'mogul', 'embodiment': 'cgg_runtime'},
    'trigger': {'kind': 'session_start', 'source_ref': 'cgg-runtime/hooks/session-restore.sh'},
    'tic_context': {'current_tic': tic, 'review_due_tic': tic+1,
        'memory_mining_due_tic': tic+(3-tic%3) if tic%3!=0 else tic+3,
        'pattern_mining_due_tic': tic+(4-tic%4) if tic%4!=0 else tic+4,
        'ladder_audit_due_tic': tic+(5-tic%5) if tic%5!=0 else tic+5,
        'deep_audit_due_tic': tic+(8-tic%8) if tic%8!=0 else tic+8},
    'cycle_request': {'run_now': list(set(cycles)), 'reason': f'SessionStart at tic {tic}'},
    'conformation_ref': None,
    'mode': {'blocking_to_orchestrator': False, 'allow_subdelegation': True},
    'runtime_truth': {'canonical_vs_installed_verified': False},
    'created_at': now.isoformat(), 'started_at': None, 'completed_at': None, 'error': None
}
print(json.dumps(mandate, indent=2))
" 2>/dev/null)

      if [ -n "$MANDATE_JSON" ]; then
        mkdir -p "$MANDATE_DIR" "$MANDATE_HISTORY_DIR"
        echo "$MANDATE_JSON" > "$MANDATE_FILE"
        MANDATE_COMPACT=$(echo "$MANDATE_JSON" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin), separators=(',',':')))" 2>/dev/null)
        TODAY=$(date +%Y-%m-%d)
        if [ -n "$MANDATE_COMPACT" ] && type atomic_append &>/dev/null; then
          atomic_append "$MANDATE_HISTORY_DIR/$TODAY.jsonl" "$MANDATE_COMPACT"
        elif [ -n "$MANDATE_COMPACT" ]; then
          printf '%s\n' "$MANDATE_COMPACT" >> "$MANDATE_HISTORY_DIR/$TODAY.jsonl"
        fi
        if [ "$ROUTED" = "false" ]; then
          DUE_CYCLES=$(echo "$MANDATE_JSON" | python3 -c "import json,sys; m=json.load(sys.stdin); print(', '.join(m['cycle_request']['run_now']))" 2>/dev/null)
          MOGUL_MANDATE_MSG="[MOGUL MANDATE: due cycles=$DUE_CYCLES]"
        fi
      fi
    fi
  fi
fi

# ── Mandate already exists: still inject inbox context for orchestrator ──
if [ "$MANDATE_ALREADY_EXISTS" = "true" ] && [ "$TIC_COUNT" -gt 0 ]; then
  INBOX_SCANNER=$(resolve_script "inbox-envelope.py")
  if [ -n "$INBOX_SCANNER" ]; then
    INBOX_INJECTION=$(python3 "$INBOX_SCANNER" \
      --zone-root "$ZONE_ROOT" \
      scan \
      --entity ent_mogul \
      --format injection \
      --current-tic "$TIC_COUNT" \
      2>/dev/null)

    python3 "$INBOX_SCANNER" \
      --zone-root "$ZONE_ROOT" \
      stale-check \
      --current-tic "$TIC_COUNT" \
      --emit-signals \
      > /dev/null 2>&1 || true
  fi

  if [ -n "$INBOX_INJECTION" ]; then
    MOGUL_MANDATE_MSG="$INBOX_INJECTION"
  else
    DUE_CYCLES=$(python3 -c "
import json
try:
    m = json.load(open('$MANDATE_FILE'))
    print(', '.join(m.get('cycle_request',{}).get('run_now',[])))
except: print('unknown')
" 2>/dev/null)
    MOGUL_MANDATE_MSG="[MOGUL MANDATE: due cycles=$DUE_CYCLES (existing mandate for tic $TIC_COUNT)]"
  fi
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
if [ -n "$MOGUL_MANDATE_MSG" ]; then
  # Inbox injection may be multi-line — flatten for JSON embedding
  MANDATE_FLAT=$(echo "$MOGUL_MANDATE_MSG" | tr '\n' ' ' | sed 's/  */ /g')
  FULL_MSG="${FULL_MSG:+$FULL_MSG }$MANDATE_FLAT"
  # Tell the orchestrator HOW to consume the mandate
  MOGUL_RUNNER=$(resolve_script "mogul-runner.sh")
  if [ -n "$MOGUL_RUNNER" ]; then
    FULL_MSG="$FULL_MSG [MOGUL CONSUMPTION: Mogul consumes mandates via: bash $MOGUL_RUNNER]"
  fi
fi
[ -n "$PARALLEL_MSG" ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }$PARALLEL_MSG"
[ "$TIC_COUNT" -gt 0 ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }[TIC: #$TIC_COUNT]"

if [ -n "$FULL_MSG" ]; then
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"$FULL_MSG\"}}"
fi

exit 0
