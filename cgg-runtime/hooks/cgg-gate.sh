#!/usr/bin/env bash
# CGG v6 — UserPromptSubmit gate
# Two independent branches:
#   A) Mandate branch: checks for pending Mogul mandates independent of trigger state
#   B) Trigger branch: fires ONCE per handoff — routes ripple.assessment via trigger-router,
#      runs ripple-assessor, then self-disarms
#
# Assessment strategy (Phase 4 — trigger-router first, deterministic second, LLM fallback):
#   1. Route ripple.assessment trigger to ent_ripple_assessor inbox via trigger-router.py
#   2. If ripple-assessor.py exists → run it directly (fast, deterministic)
#   3. Otherwise → instruct Claude to spawn the ripple-assessor agent
#
# Script resolution order:
#   1. $ZONE_ROOT/scripts/<name>.py (project override)
#   2. $CGG_SCRIPTS_DIR/<name>.py (plugin-root-anchored bundled script)
#   3. $HOME/.claude/cgg-runtime/scripts/<name>.py (global install fallback)
#
# Mandate lifecycle:
#   pending → running → consumed | failed
cat > /dev/null

# Wire cutter — emergency kill switch
[ -f ~/.claude/wire-cutter.sh ] && source ~/.claude/wire-cutter.sh && wire_check gate

# ============================================================================
# Root Anchoring
# ============================================================================

# Plugin-root anchor: canonical for finding bundled runtime assets.
# CLAUDE_PLUGIN_ROOT is only set for plugin-registered hooks (hooks.json).
# User-registered hooks (~/.claude/hooks/) must resolve via fallback chain.
CGG_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
if [ -z "$CGG_PLUGIN_ROOT" ] || [ ! -d "$CGG_PLUGIN_ROOT/cgg-runtime" ]; then
  for _cpr_candidate in \
    "${CLAUDE_PROJECT_DIR:+$CLAUDE_PROJECT_DIR/vendor/context-grapple-gun}" \
    "${CLAUDE_PROJECT_DIR:+$CLAUDE_PROJECT_DIR/canonical_developer/context-grapple-gun}" \
    "$HOME/.claude"; do
    [ -n "$_cpr_candidate" ] && [ -d "$_cpr_candidate/cgg-runtime" ] && CGG_PLUGIN_ROOT="$_cpr_candidate" && break
  done
fi

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

PROJECT_DIR="$ZONE_ROOT"
PROJECT_KEY=$(echo "$PROJECT_DIR" | sed 's|/|-|g')
FLAG_DIR="${TMPDIR:-/tmp}/claude_cgg/$PROJECT_KEY"
TRIGGER_FILE="$FLAG_DIR/pending-trigger.txt"
HANDOFF_FILE="$FLAG_DIR/pending-handoff-id.txt"
PROCESSED_IDS="$HOME/.claude/cgg-processed-handoff-ids.txt"
META_LOG="$HOME/.claude/grapple-meta-log.jsonl"
TIMESTAMP=$(date -Iseconds)

# Safe JSONL append wrapper
log_meta() {
  if type atomic_append &>/dev/null; then
    atomic_append "$META_LOG" "$1"
  else
    echo "$1" >> "$META_LOG"
  fi
}

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
        log_meta "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"mogul_mandate_activated\",\"mandate_id\":\"$MANDATE_ID\",\"cycles\":\"$HEAVY_CYCLES\",\"status\":\"pending\"}"

        MOGUL_LOG_DIR="$ZONE_ROOT/$AUDIT_LOGS_REL/mogul/cycle-reports"
        mkdir -p "$MOGUL_LOG_DIR"
        "$MOGUL_RUNNER" > "$MOGUL_LOG_DIR/$(date +%Y-%m-%dT%H%M%S)-runner-log.txt" 2>&1 &
        log_meta "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"mogul_runner_spawned\",\"mandate_id\":\"$MANDATE_ID\",\"cycles\":\"$HEAVY_CYCLES\",\"pid\":$!}"
        MANDATE_OUTPUT="[MOGUL MANDATE: runner spawn] mogul-runner.sh executing governance cycles ($HEAVY_CYCLES) in background (PID $!). Non-blocking."
      else
        # No runner — leave status pending, surface for LLM/manual execution
        log_meta "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"mogul_mandate_surfaced\",\"mandate_id\":\"$MANDATE_ID\",\"cycles\":\"$HEAVY_CYCLES\",\"status\":\"pending\"}"
        MANDATE_OUTPUT="[MOGUL MANDATE PENDING] Heavy governance cycles due: $HEAVY_CYCLES. Spawn Mogul agent (Task tool, subagent_type: mogul, run_in_background: true) to execute mandated cycles. Mandate at: $MANDATE_FILE. Mandate ID: $MANDATE_ID. Non-blocking."
      fi
    elif [ -n "$ALL_CYCLES" ]; then
      # Lightweight cycles — execute inline and consume
      LIGHTWEIGHT_RESULTS=""
      LIGHTWEIGHT_FAILED=""

      # Re-validate status before consumption (race guard: mogul-runner may have
      # picked up the mandate between our initial read and now — CogPR-57 fix #1)
      RECHECK_STATUS=$(python3 -c "
import json
try:
    m = json.load(open('$MANDATE_FILE'))
    print(m.get('status', 'pending'))
except: print('error')
" 2>/dev/null)
      if [ "$RECHECK_STATUS" != "pending" ]; then
        log_meta "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"lightweight_mandate_race_avoided\",\"mandate_id\":\"$MANDATE_ID\",\"recheck_status\":\"$RECHECK_STATUS\"}"
        MANDATE_OUTPUT="[MOGUL MANDATE: $RECHECK_STATUS] Mandate $MANDATE_ID already picked up (status: $RECHECK_STATUS)."
      else

      # Execute each lightweight cycle
      IFS=',' read -ra LW_CYCLES <<< "$ALL_CYCLES"
      for cycle in "${LW_CYCLES[@]}"; do
        case "$cycle" in
          queue_refresh)
            # Re-index CPR queue
            QUEUE_FILE="$ZONE_ROOT/$AUDIT_LOGS_REL/cprs/queue.jsonl"
            if [ -f "$QUEUE_FILE" ]; then
              PENDING=$(python3 -c "
import json
seen = {}
for line in open('$QUEUE_FILE'):
    line = line.strip()
    if not line: continue
    try:
        e = json.loads(line)
        seen[e.get('id','')] = e
    except: pass
pending = [v for v in seen.values() if v.get('review_verdict','') == '' and v.get('status','') not in ('promoted','skipped','absorbed','rejected')]
print(len(pending))
" 2>/dev/null)
              LIGHTWEIGHT_RESULTS="${LIGHTWEIGHT_RESULTS}queue_refresh=${PENDING:-0}_pending,"
            else
              LIGHTWEIGHT_RESULTS="${LIGHTWEIGHT_RESULTS}queue_refresh=no_queue,"
            fi
            ;;
          signal_scan)
            # Count active signals
            SIGNAL_DIR="$ZONE_ROOT/$AUDIT_LOGS_REL/signals"
            if [ -d "$SIGNAL_DIR" ]; then
              ACTIVE_SIGS=$(python3 -c "
import json, glob, os
seen = {}
for f in sorted(glob.glob(os.path.join('$SIGNAL_DIR', '*.jsonl'))):
    for line in open(f):
        line = line.strip()
        if not line: continue
        try:
            e = json.loads(line)
            seen[e.get('id','')] = e
        except: pass
active = [v for v in seen.values() if v.get('status','active') == 'active' and v.get('type','') == 'signal']
print(len(active))
" 2>/dev/null)
              LIGHTWEIGHT_RESULTS="${LIGHTWEIGHT_RESULTS}signal_scan=${ACTIVE_SIGS:-0}_active,"
            else
              LIGHTWEIGHT_RESULTS="${LIGHTWEIGHT_RESULTS}signal_scan=no_signals,"
            fi
            ;;
          *)
            LIGHTWEIGHT_RESULTS="${LIGHTWEIGHT_RESULTS}${cycle}=skipped,"
            ;;
        esac
      done

      # Consume the mandate
      python3 -c "
import json
from datetime import datetime, timezone
m = json.load(open('$MANDATE_FILE'))
m['status'] = 'consumed'
m['completed_at'] = datetime.now(timezone.utc).isoformat()
m['lightweight_results'] = '${LIGHTWEIGHT_RESULTS}'.rstrip(',')
json.dump(m, open('$MANDATE_FILE', 'w'), indent=2)
" 2>/dev/null

      if [ $? -eq 0 ]; then
        log_meta "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"lightweight_mandate_consumed\",\"mandate_id\":\"$MANDATE_ID\",\"cycles\":\"$ALL_CYCLES\",\"results\":\"${LIGHTWEIGHT_RESULTS}\"}"
        MANDATE_OUTPUT="[MOGUL MANDATE: consumed] Lightweight cycles completed inline: ${LIGHTWEIGHT_RESULTS%,}."
      else
        log_meta "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"lightweight_mandate_consumption_failed\",\"mandate_id\":\"$MANDATE_ID\",\"cycles\":\"$ALL_CYCLES\"}"
        MANDATE_OUTPUT="[MOGUL MANDATE: lightweight] Pending cycles: $ALL_CYCLES (inline consumption failed — needs investigation)."
      fi

      fi  # end race guard (CogPR-57 fix #1)
    fi
  elif [ "$MANDATE_STATUS" = "running" ]; then
    MANDATE_OUTPUT="[MOGUL MANDATE: in-flight] Mandate $MANDATE_ID still running (cycles: $ALL_CYCLES)."
  elif [ "$MANDATE_STATUS" = "failed" ]; then
    MANDATE_OUTPUT="[MOGUL MANDATE: FAILED] Mandate $MANDATE_ID failed (cycles: $ALL_CYCLES). Needs investigation."
    log_meta "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"mogul_mandate_failed_surfaced\",\"mandate_id\":\"$MANDATE_ID\",\"cycles\":\"$ALL_CYCLES\"}"
  else
    # consumed or unknown — no output needed
    :
  fi
fi

# ============================================================================
# Branch B: Trigger-based assessor spawn — independent of mandate
# Phase 4: Routes ripple.assessment via trigger-router, falls back to
#           flag-file polling for backward compatibility.
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
  log_meta "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"trigger_fired\",\"handoff_id\":\"$HANDOFF_ID\",\"expected_cprs\":$EXPECTED_CPRS,\"plan_path\":\"$PLAN_PATH\",\"project\":\"$PROJECT_DIR\"}"

  # ── Route ripple.assessment via trigger-router (primary path) ──
  TRIGGER_ROUTER=$(resolve_script "trigger-router.py")
  INBOX_SCANNER=$(resolve_script "inbox-envelope.py")
  RIPPLE_ROUTED=false

  # Read current tic count for routing
  TIC_DIR="$ZONE_ROOT/$AUDIT_LOGS_REL/tics"
  CURRENT_TIC=0
  if [ -d "$TIC_DIR" ]; then
    CURRENT_TIC=$(python3 -c "
import json, glob
max_counter = 0
for f in sorted(glob.glob('$TIC_DIR/*.jsonl')):
    for line in open(f):
        try:
            d = json.loads(line)
            if d.get('type') != 'tic': continue
            if d.get('count_mode', 'counted') != 'counted': continue
            ca = d.get('global_counter_after', d.get('global_counter', 0))
            if ca > max_counter: max_counter = ca
        except: pass
print(max_counter)
" 2>/dev/null || echo "0")
  fi

  # Build signal snapshot for the trigger body
  SIGNAL_SNAPSHOT=$(python3 -c "
import json, glob
signals = {}
for f in sorted(glob.glob('$ZONE_ROOT/$AUDIT_LOGS_REL/signals/*.jsonl')):
    for line in open(f):
        try:
            d = json.loads(line)
            eid = d.get('id', '')
            if eid and d.get('type') == 'signal':
                signals[eid] = d
        except: pass
active = [{'id': s['id'], 'volume': s.get('volume',0), 'band': s.get('band','?')}
          for s in signals.values() if s.get('status') in ('active','acknowledged','working')]
print(json.dumps(active))
" 2>/dev/null || echo "[]")

  RIPPLE_BODY_JSON=$(python3 -c "
import json
body = {
    'plan_id': '$PLAN_PATH' if '$PLAN_PATH' else None,
    'handoff_id': '$HANDOFF_ID' if '$HANDOFF_ID' else None,
    'active_signals_snapshot': json.loads('$SIGNAL_SNAPSHOT'),
    'trigger_data': '''$TRIGGER_DATA''',
    'expected_cprs': $EXPECTED_CPRS,
}
print(json.dumps(body))
" 2>/dev/null)

  if [ -n "$TRIGGER_ROUTER" ] && [ -n "$RIPPLE_BODY_JSON" ]; then
    ROUTE_RESULT=$(python3 "$TRIGGER_ROUTER" \
      --zone-root "$ZONE_ROOT" \
      route \
      --trigger-type ripple.assessment \
      --source-event UserPromptSubmit \
      --producer "cgg-gate.sh" \
      --source-tic "$CURRENT_TIC" \
      --subject "Ripple assessment — handoff $HANDOFF_ID" \
      --body "$RIPPLE_BODY_JSON" \
      --session-id "$(python3 -c "import uuid; print(uuid.uuid4().hex[:12])" 2>/dev/null)" \
      2>/dev/null)

    ROUTE_STATUS=$(echo "$ROUTE_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
    if [ "$ROUTE_STATUS" = "routed" ]; then
      RIPPLE_ROUTED=true
      log_meta "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"ripple_routed_via_trigger_router\",\"handoff_id\":\"$HANDOFF_ID\"}"

      # Read ripple-assessor inbox for injection
      if [ -n "$INBOX_SCANNER" ]; then
        RIPPLE_INBOX=$(python3 "$INBOX_SCANNER" \
          --zone-root "$ZONE_ROOT" \
          scan \
          --entity ent_ripple_assessor \
          --format injection \
          --current-tic "$CURRENT_TIC" \
          2>/dev/null)

        # Phase 5: Emit attention-debt signals for stale inbox items
        python3 "$INBOX_SCANNER" \
          --zone-root "$ZONE_ROOT" \
          stale-check \
          --current-tic "$CURRENT_TIC" \
          --emit-signals \
          > /dev/null 2>&1 || true
      fi
    fi
  fi

  # ── Deterministic assessor spawn (runs regardless of routing) ──
  DETERMINISTIC_ASSESSOR=$(resolve_script "ripple-assessor.py")
  if [ -n "$DETERMINISTIC_ASSESSOR" ]; then
    python3 "$DETERMINISTIC_ASSESSOR" \
      --plan "$PLAN_PATH" \
      --project "$PROJECT_DIR" \
      --output "$HOME/.claude/grapple-proposals/latest.md" \
      2>/dev/null &

    log_meta "{\"timestamp\":\"$TIMESTAMP\",\"action\":\"deterministic_assessor_spawned\",\"handoff_id\":\"$HANDOFF_ID\",\"assessor\":\"$DETERMINISTIC_ASSESSOR\"}"

    if [ "$RIPPLE_ROUTED" = "true" ] && [ -n "$RIPPLE_INBOX" ]; then
      ASSESSOR_OUTPUT="[CGG TRIGGER FIRED] $RIPPLE_INBOX Deterministic ripple-assessor running in background. Proposals at ~/.claude/grapple-proposals/latest.md. /review when ready."
    else
      ASSESSOR_OUTPUT="[CGG TRIGGER FIRED] Deterministic ripple-assessor running in background. Proposals will appear at ~/.claude/grapple-proposals/latest.md. /review when ready."
    fi
  else
    # Fall back to LLM agent spawn
    PLAN_REF=""
    if [ -n "$PLAN_PATH" ]; then
      PLAN_REF="Plan file: $PLAN_PATH"
    else
      PLAN_REF="Plan file: not located (assessor should search for handoff_id: $HANDOFF_ID)"
    fi

    if [ "$RIPPLE_ROUTED" = "true" ] && [ -n "$RIPPLE_INBOX" ]; then
      ASSESSOR_OUTPUT="[CGG TRIGGER FIRED] $RIPPLE_INBOX Spawn ripple-assessor agent (Agent tool, subagent_type: ripple-assessor) BEFORE starting user work. $PLAN_REF. Expected CogPR count: $EXPECTED_CPRS. Handoff ID: $HANDOFF_ID. Run it in background."
    else
      ASSESSOR_OUTPUT="[CGG TRIGGER FIRED] Spawn ripple-assessor agent (Agent tool, subagent_type: ripple-assessor) BEFORE starting user work. $PLAN_REF. Expected CogPR count: $EXPECTED_CPRS. Handoff ID: $HANDOFF_ID. The assessor will read the plan, evaluate pending CogPR flags and active signals, and write proposals to ~/.claude/grapple-proposals/latest.md. Run it in the background so you can proceed with the user's request."
    fi
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
