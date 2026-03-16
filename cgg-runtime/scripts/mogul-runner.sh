#!/bin/bash
# mogul-runner.sh — Mogul mandate consumer
#
# Reads authoritative mandate from audit-logs/mogul/mandates/current.json,
# validates status, binds Mogul office identity, invokes claude -p, and
# records lifecycle transitions.
#
# Usage: scripts/mogul-runner.sh [--dry-run]
#
# Exit codes:
#   0 — mandate consumed successfully
#   1 — error (no mandate, already consumed, runner failure)
#   2 — dry-run (mandate valid, would execute)

set -euo pipefail

DRY_RUN=false
[ "${1:-}" = "--dry-run" ] && DRY_RUN=true

# Load atomic append library for JSONL-safe writes.
# SCRIPT_DIR is reliable for sibling-file lookups (lib/, etc.) since
# mogul-runner.sh lives alongside its dependencies at install time.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ATOMIC_LIB="$SCRIPT_DIR/lib/atomic-append.sh"
[ -f "$ATOMIC_LIB" ] && source "$ATOMIC_LIB"

# Safe JSONL append wrapper
safe_jsonl_append() {
  local target="$1" content="$2"
  if type atomic_append &>/dev/null; then
    atomic_append "$target" "$content"
  else
    echo "$content" >> "$target"
  fi
}

# ============================================================================
# Zone root resolution — use CLAUDE_PROJECT_DIR, walk to .ticzone.
# Never use dirname "$0" for zone root — this script may be installed
# at ~/.claude/cgg-runtime/scripts/ which is outside the project tree.
# ============================================================================

resolve_zone_root() {
  local dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
  while [ "$dir" != "/" ]; do
    [ -f "$dir/.ticzone" ] && echo "$dir" && return 0
    dir=$(dirname "$dir")
  done
  git rev-parse --show-toplevel 2>/dev/null && return 0
  echo "${CLAUDE_PROJECT_DIR:-$(pwd)}"
}

ZONE_ROOT=$(resolve_zone_root)

# Resolve rung topology for provenance embedding
RUNG_RESOLVER="$ZONE_ROOT/vendor/context-grapple-gun/cgg-runtime/scripts/rung_resolver.py"
BIRTH_RUNG="unknown"
TOPOLOGY_JSON="{}"
if [ -f "$RUNG_RESOLVER" ]; then
  RUNG_JSON=$(python3 "$RUNG_RESOLVER" --json --start "$ZONE_ROOT" 2>/dev/null) || RUNG_JSON="{}"
  BIRTH_RUNG=$(echo "$RUNG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('current_rung','unknown'))" 2>/dev/null) || BIRTH_RUNG="unknown"
  TOPOLOGY_JSON=$(echo "$RUNG_JSON" | python3 -c "
import sys,json
d = json.load(sys.stdin).get('topology',{})
print(json.dumps({k: v['path'] if v else None for k,v in d.items()}))
" 2>/dev/null) || TOPOLOGY_JSON="{}"
fi

AUDIT_LOGS="$ZONE_ROOT/audit-logs"
MANDATE_FILE="$AUDIT_LOGS/mogul/mandates/current.json"
MANDATE_HISTORY_DIR="$AUDIT_LOGS/mogul/mandates/history"
CYCLE_REPORTS_DIR="$AUDIT_LOGS/mogul/cycle-reports"
MOGUL_AGENT="$ZONE_ROOT/.claude/agents/mogul.md"

# ============================================================================
# Validate mandate exists and is pending
# ============================================================================

if [ ! -f "$MANDATE_FILE" ]; then
  echo "ERROR: No mandate at $MANDATE_FILE" >&2
  exit 1
fi

MANDATE_STATUS=$(python3 -c "
import json, sys
m = json.load(open('$MANDATE_FILE'))
print(m.get('status', 'pending'))
" 2>/dev/null)

# Backwards compat: mandates without status field are treated as pending
if [ -z "$MANDATE_STATUS" ]; then
  MANDATE_STATUS="pending"
fi

if [ "$MANDATE_STATUS" != "pending" ]; then
  echo "ERROR: Mandate status is '$MANDATE_STATUS', not 'pending'. Refusing to execute." >&2
  exit 1
fi

# Read mandate details
MANDATE_INFO=$(python3 -c "
import json
m = json.load(open('$MANDATE_FILE'))
mid = m.get('mandate_id', 'legacy-no-id')
cycles = m.get('cycle_request', {}).get('run_now', [])
tic = m.get('tic_context', {}).get('current_tic', '?')
print(f'{mid}|{\",\".join(cycles)}|{tic}')
" 2>/dev/null)

MANDATE_ID=$(echo "$MANDATE_INFO" | cut -d'|' -f1)
CYCLES=$(echo "$MANDATE_INFO" | cut -d'|' -f2)
CURRENT_TIC=$(echo "$MANDATE_INFO" | cut -d'|' -f3)

echo "Mandate: $MANDATE_ID"
echo "Cycles:  $CYCLES"
echo "Tic:     $CURRENT_TIC"
echo "Status:  $MANDATE_STATUS"

if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN] Would execute mandate $MANDATE_ID with cycles: $CYCLES"
  exit 2
fi

# ============================================================================
# Transition: pending -> running
# ============================================================================

NOW=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)

python3 -c "
import json
m = json.load(open('$MANDATE_FILE'))
m['status'] = 'running'
m['started_at'] = '$NOW'
json.dump(m, open('$MANDATE_FILE', 'w'), indent=2)
" 2>/dev/null

# Record transition in history
TODAY=$(date +%Y-%m-%d)
mkdir -p "$MANDATE_HISTORY_DIR"
python3 -c "
import json
m = json.load(open('$MANDATE_FILE'))
t = {'transition': 'pending_to_running', 'mandate_id': m.get('mandate_id',''), 'timestamp': '$NOW'}
print(json.dumps(t))
" | while IFS= read -r _line; do safe_jsonl_append "$MANDATE_HISTORY_DIR/$TODAY.jsonl" "$_line"; done 2>/dev/null

echo "Status -> running at $NOW"

# ============================================================================
# Compute artifact paths (needed by prompt and verification)
# ============================================================================

TRANSCRIPT_DIR="$CYCLE_REPORTS_DIR/transcripts"
REPORT_DIR="$CYCLE_REPORTS_DIR/reports"
mkdir -p "$TRANSCRIPT_DIR" "$REPORT_DIR"

TIMESTAMP=$(date +%Y-%m-%dT%H%M%S)
TRANSCRIPT_FILE="$TRANSCRIPT_DIR/${TIMESTAMP}-tic-${CURRENT_TIC}.json"
STRUCTURED_REPORT="$REPORT_DIR/${TIMESTAMP}-tic-${CURRENT_TIC}.report.json"

# ============================================================================
# Compose Mogul prompt from agent identity + mandate
# ============================================================================

MANDATE_CONTENT=$(cat "$MANDATE_FILE")

MOGUL_PROMPT="You are Mogul — the estate governance suborchestrator, activated by mandate.

You are NOT Homeskillet. You are Mogul. Homeskillet orchestrated this invocation but you own the governance office.

You are a suborchestrator, not a passive reporter. When cycles reveal actionable state (enrichment-eligible CPRs, signal pressure, drift findings), you should assess, decompose, delegate, advance, and synthesize — not merely describe what you see. The pipeline should be materially further along when you finish.

## Your mandate (authoritative — execute exactly these cycles)

\`\`\`json
$MANDATE_CONTENT
\`\`\`

## Topology context

- Birth rung: $BIRTH_RUNG
- Topology chain: $TOPOLOGY_JSON

## Instructions

1. Read and execute ONLY the cycles in cycle_request.run_now: $CYCLES
2. For each cycle, produce evidence artifacts:
   - queue_refresh: scan audit-logs/cprs/queue.jsonl, report state. First run: python3 \$ZONE_ROOT/vendor/context-grapple-gun/cgg-runtime/scripts/arena-pressure-ingest.py --zone-root \$ZONE_ROOT --quiet to discover arena candidates before scanning.
   - signal_scan: scan audit-logs/signals/*.jsonl, report active/decayed
   - memory_mining: scan MEMORY.md chain for recurring patterns, write findings
   - pattern_mining: run scripts/pattern_miner.py, output to audit-logs/patterns/
   - enrichment_scan: run scripts/cpr-enrichment-scanner.py, assess enrichment-eligible CPRs
   - ladder_audit: audit CLAUDE.md chain coherence
   - runtime_drift_check: compare installed vs canonical runtime surfaces
   - prompt_stack_audit: run scripts/prompt-stack-audit.py, scan CLAUDE.md chain for conflicts
   - deep_audit: comprehensive multi-rung scan
   - bench_packet_prep: run scripts/bench-packet-prep.py, output to audit-logs/mogul/bench-packets/
   - review_close_check: run scripts/review-close-check.py, verify post-review inscription consistency
3. Write a DEDICATED structured JSON cycle report using Write tool to EXACTLY this path:
   $STRUCTURED_REPORT
   This file is your governance evidence artifact. It MUST follow the schema below exactly.
4. Do NOT modify CLAUDE.md, MEMORY.md, or any constitutional surface
5. Do NOT invent cycles beyond what the mandate specifies
6. Working directory is: $ZONE_ROOT

## Cycle report schema (MANDATORY — runner validates this before marking mandate consumed)

Write this EXACT file: $STRUCTURED_REPORT

Your cycle report MUST be a JSON object with exactly this shape:

\`\`\`json
{
  \"mandate_id\": \"$MANDATE_ID\",
  \"actor\": {\"office\": \"mogul\", \"embodiment\": \"cgg_runtime\"},
  \"orchestrated_by\": \"homeskillet\",
  \"tic\": $CURRENT_TIC,
  \"timestamp\": \"ISO-8601 now\",
  \"cycles_executed\": [\"list of cycles you ran\"],
  \"artifacts\": {
    \"bench_packet\": \"audit-logs/mogul/bench-packets/latest.json\"
  },
  \"results\": {
    \"signal_scan\": {},
    \"queue_refresh\": {},
    \"bench_packet_prep\": {}
  }
}
\`\`\`

CRITICAL RULES:
- actor MUST be an object, never a string
- actor.office MUST be \"mogul\"
- actor.embodiment MUST be \"cgg_runtime\"
- Do NOT write actor as 'homeskillet_as_mogul'
- mandate_id MUST exactly equal \"$MANDATE_ID\"
- The file MUST be valid JSON parseable by python json.load()
- Only populate results keys for cycles you actually executed
- The runner will REFUSE to mark mandate consumed if this file is missing or malformed"

# ============================================================================
# Invoke claude -p with Mogul identity
# ============================================================================

CLAUDE_BIN=$(command -v claude 2>/dev/null || true)
if [ -z "$CLAUDE_BIN" ]; then
  echo "ERROR: claude CLI not found in PATH" >&2
  # Transition: running -> failed
  python3 -c "
import json
m = json.load(open('$MANDATE_FILE'))
m['status'] = 'failed'
m['completed_at'] = '$(date -u +%Y-%m-%dT%H:%M:%S+00:00)'
m['error'] = 'claude CLI not found in PATH'
json.dump(m, open('$MANDATE_FILE', 'w'), indent=2)
" 2>/dev/null
  exit 1
fi

echo "Spawning claude -p for mandate $MANDATE_ID..."

# Unset CLAUDECODE to allow nested headless invocation
# (Claude Code blocks nesting by default; headless -p is safe)
# --dangerously-skip-permissions: no interactive user for tool approval
# --allowedTools: bounded tool set for governance work
set +e
env -u CLAUDECODE "$CLAUDE_BIN" -p "$MOGUL_PROMPT" \
  --allowedTools "Read,Grep,Glob,Bash,Write" \
  --dangerously-skip-permissions \
  --output-format json \
  > "$TRANSCRIPT_FILE" 2>&1
CLAUDE_EXIT=$?
set -e

# ============================================================================
# Record completion
# ============================================================================

COMPLETED_AT=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)

if [ $CLAUDE_EXIT -eq 0 ]; then
  # ============================================================================
  # Artifact verification — two-layer: transcript + structured report
  # ============================================================================

  ARTIFACT_ERRORS=""

  # Layer 1: Transcript (execution evidence)
  if [ ! -s "$TRANSCRIPT_FILE" ]; then
    ARTIFACT_ERRORS="${ARTIFACT_ERRORS}Transcript file empty or missing. "
  fi

  # Layer 2: Structured report (governance evidence)
  if [ ! -f "$STRUCTURED_REPORT" ]; then
    ARTIFACT_ERRORS="${ARTIFACT_ERRORS}Structured report missing at $STRUCTURED_REPORT. "
  elif [ ! -s "$STRUCTURED_REPORT" ]; then
    ARTIFACT_ERRORS="${ARTIFACT_ERRORS}Structured report exists but is empty. "
  else
    # Validate structured report contents
    REPORT_VALIDATION=$(python3 -c "
import json, sys
try:
    r = json.load(open('$STRUCTURED_REPORT'))
except Exception as e:
    print(f'JSON parse failed: {e}')
    sys.exit(0)

errors = []
# actor must be an object with office=mogul
actor = r.get('actor')
if not isinstance(actor, dict):
    errors.append(f'actor is {type(actor).__name__}, must be object')
elif actor.get('office') != 'mogul':
    errors.append(f'actor.office={actor.get(\"office\")}, must be mogul')
elif actor.get('embodiment') != 'cgg_runtime':
    errors.append(f'actor.embodiment={actor.get(\"embodiment\")}, must be cgg_runtime')

# mandate_id must exactly match
mid = r.get('mandate_id')
if mid != '$MANDATE_ID':
    errors.append(f'mandate_id={mid}, expected=$MANDATE_ID')

# cycles_executed must be a list
if not isinstance(r.get('cycles_executed'), list):
    errors.append('cycles_executed missing or not a list')

if errors:
    print('; '.join(errors))
else:
    print('OK')
" 2>&1)

    if [ "$REPORT_VALIDATION" != "OK" ]; then
      ARTIFACT_ERRORS="${ARTIFACT_ERRORS}Structured report validation: $REPORT_VALIDATION. "
    fi
  fi

  # Verify cycle-specific artifacts
  IFS=',' read -ra CYCLE_ARRAY <<< "$CYCLES"
  for cycle in "${CYCLE_ARRAY[@]}"; do
    case "$cycle" in
      bench_packet_prep)
        BENCH_PACKET="$AUDIT_LOGS/mogul/bench-packets/latest.json"
        if [ ! -f "$BENCH_PACKET" ]; then
          ARTIFACT_ERRORS="${ARTIFACT_ERRORS}bench_packet_prep: latest.json missing. "
        fi
        ;;
      pattern_mining)
        TODAY_PATTERNS="$AUDIT_LOGS/patterns/$(date +%Y-%m-%d).jsonl"
        # Pattern file is optional (no new patterns is valid), but check
        # that the structured report mentions pattern_mining in results
        if [ -f "$STRUCTURED_REPORT" ]; then
          HAS_PATTERN_RESULT=$(python3 -c "
import json
r = json.load(open('$STRUCTURED_REPORT'))
print('yes' if 'pattern_mining' in r.get('results', {}) else 'no')
" 2>/dev/null)
          if [ "$HAS_PATTERN_RESULT" != "yes" ]; then
            ARTIFACT_ERRORS="${ARTIFACT_ERRORS}pattern_mining: not in structured report results. "
          fi
        fi
        ;;
      enrichment_scan)
        if [ -f "$STRUCTURED_REPORT" ]; then
          HAS_ENRICHMENT_RESULT=$(python3 -c "
import json
r = json.load(open('$STRUCTURED_REPORT'))
print('yes' if 'enrichment_scan' in r.get('results', {}) else 'no')
" 2>/dev/null)
          if [ "$HAS_ENRICHMENT_RESULT" != "yes" ]; then
            ARTIFACT_ERRORS="${ARTIFACT_ERRORS}enrichment_scan: not in structured report results. "
          fi
        fi
        ;;
      prompt_stack_audit)
        # Check that an audit file was written
        PSA_DIR="$AUDIT_LOGS/mogul/cycle-reports/prompt-stack-audits"
        if [ -d "$PSA_DIR" ]; then
          PSA_COUNT=$(find "$PSA_DIR" -name "*-audit.json" -newer "$MANDATE_FILE" 2>/dev/null | wc -l | tr -d ' ')
        else
          PSA_COUNT=0
        fi
        if [ "$PSA_COUNT" -eq 0 ]; then
          ARTIFACT_ERRORS="${ARTIFACT_ERRORS}prompt_stack_audit: no audit file produced. "
        fi
        ;;
      review_close_check)
        # Check that a consistency report was written
        RCC_DIR="$AUDIT_LOGS/mogul/cycle-reports/review-close-checks"
        if [ -d "$RCC_DIR" ]; then
          RCC_COUNT=$(find "$RCC_DIR" -name "*-check.json" -newer "$MANDATE_FILE" 2>/dev/null | wc -l | tr -d ' ')
        else
          RCC_COUNT=0
        fi
        if [ "$RCC_COUNT" -eq 0 ]; then
          ARTIFACT_ERRORS="${ARTIFACT_ERRORS}review_close_check: no consistency report produced. "
        fi
        ;;
      queue_refresh|signal_scan|memory_mining|ladder_audit|runtime_drift_check|deep_audit)
        # Lightweight cycles — verify they appear in structured report results
        if [ -f "$STRUCTURED_REPORT" ]; then
          HAS_CYCLE_RESULT=$(python3 -c "
import json
r = json.load(open('$STRUCTURED_REPORT'))
print('yes' if '$cycle' in r.get('results', {}) else 'no')
" 2>/dev/null)
          if [ "$HAS_CYCLE_RESULT" != "yes" ]; then
            ARTIFACT_ERRORS="${ARTIFACT_ERRORS}${cycle}: not in structured report results. "
          fi
        fi
        ;;
    esac
  done

  if [ -n "$ARTIFACT_ERRORS" ]; then
    echo "WARNING: Artifact verification failed: $ARTIFACT_ERRORS" >&2
    echo "Marking mandate as failed despite exit code 0."

    python3 -c "
import json
m = json.load(open('$MANDATE_FILE'))
m['status'] = 'failed'
m['completed_at'] = '$COMPLETED_AT'
m['error'] = 'Artifact verification failed: $(echo "$ARTIFACT_ERRORS" | sed "s/'/\\\\'/g")'
json.dump(m, open('$MANDATE_FILE', 'w'), indent=2)
" 2>/dev/null

    python3 -c "
import json
t = {'transition': 'running_to_failed', 'mandate_id': '$MANDATE_ID', 'timestamp': '$COMPLETED_AT', 'reason': 'artifact_verification', 'errors': '$(echo "$ARTIFACT_ERRORS" | sed "s/'/\\\\'/g")'}
print(json.dumps(t))
" | while IFS= read -r _line; do safe_jsonl_append "$MANDATE_HISTORY_DIR/$TODAY.jsonl" "$_line"; done 2>/dev/null

    exit 1
  fi

  # All artifacts verified — mark consumed
  python3 -c "
import json
m = json.load(open('$MANDATE_FILE'))
m['status'] = 'consumed'
m['completed_at'] = '$COMPLETED_AT'
m['structured_report'] = '$STRUCTURED_REPORT'
m['transcript'] = '$TRANSCRIPT_FILE'
json.dump(m, open('$MANDATE_FILE', 'w'), indent=2)
" 2>/dev/null

  echo "Mandate $MANDATE_ID consumed at $COMPLETED_AT"
  echo "Transcript: $TRANSCRIPT_FILE"
  echo "Report:     $STRUCTURED_REPORT"

  # Record transition with provenance
  python3 -c "
import json
t = {
    'transition': 'running_to_consumed',
    'mandate_id': '$MANDATE_ID',
    'timestamp': '$COMPLETED_AT',
    'transcript': '$TRANSCRIPT_FILE',
    'structured_report': '$STRUCTURED_REPORT',
    'actor': {'office': 'mogul', 'embodiment': 'cgg_runtime'},
    'orchestrated_by': 'homeskillet',
    'cycles_executed': '$CYCLES'.split(','),
    'artifacts_verified': True,
    'birth_rung': '$BIRTH_RUNG'
}
print(json.dumps(t))
" | while IFS= read -r _line; do safe_jsonl_append "$MANDATE_HISTORY_DIR/$TODAY.jsonl" "$_line"; done 2>/dev/null
else
  python3 -c "
import json
m = json.load(open('$MANDATE_FILE'))
m['status'] = 'failed'
m['completed_at'] = '$COMPLETED_AT'
m['error'] = 'claude -p exited with code $CLAUDE_EXIT'
json.dump(m, open('$MANDATE_FILE', 'w'), indent=2)
" 2>/dev/null

  echo "ERROR: claude -p exited with code $CLAUDE_EXIT" >&2
  echo "Mandate $MANDATE_ID failed at $COMPLETED_AT"
  echo "Transcript: $TRANSCRIPT_FILE"

  # Record transition
  python3 -c "
import json
t = {
    'transition': 'running_to_failed',
    'mandate_id': '$MANDATE_ID',
    'timestamp': '$COMPLETED_AT',
    'exit_code': $CLAUDE_EXIT,
    'actor': {'office': 'mogul', 'embodiment': 'cgg_runtime'},
    'orchestrated_by': 'homeskillet',
    'birth_rung': '$BIRTH_RUNG'
}
print(json.dumps(t))
" | while IFS= read -r _line; do safe_jsonl_append "$MANDATE_HISTORY_DIR/$TODAY.jsonl" "$_line"; done 2>/dev/null

  exit 1
fi
