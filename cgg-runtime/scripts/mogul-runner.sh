#!/usr/bin/env bash
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

# ============================================================================
# Snapshot $MANDATE_FILE mtime at run start (CogPR-3 fix-family, tic 280)
#
# Mandate Lifecycle Defect #4: cross-mandate write race. If /cadence emits a
# new mandate to current.json mid-execution, the file's mtime advances under
# the runner's feet. Verifier clauses using `find -newer "$MANDATE_FILE"`
# would then false-negative legitimately-produced artifacts whose mtime is
# older than the cadence-written new mandate. Pin the mtime here so verifiers
# read the snapshot, not the live (possibly cadence-overwritten) file.
# ============================================================================

MANDATE_FILE_SNAPSHOT_REF="/tmp/cgg-mandate-snapshot-$$.ref"
touch -r "$MANDATE_FILE" "$MANDATE_FILE_SNAPSHOT_REF"
trap 'rm -f "$MANDATE_FILE_SNAPSHOT_REF"' EXIT

echo "Mandate: $MANDATE_ID"
echo "Cycles:  $CYCLES"
echo "Tic:     $CURRENT_TIC"
echo "Status:  $MANDATE_STATUS"
echo "Snapshot ref: $MANDATE_FILE_SNAPSHOT_REF"

# ============================================================================
# Guarded terminal write-back — WRITE-side complement to the tic-280 snapshot
# pin above. The snapshot pin protects the READ side (artifact counting via
# find -newer); this guards the WRITE side. If /cadence overwrote current.json
# with a SUCCESSOR mandate mid-run (Mandate Lifecycle Defect #4, write-back
# half), the runner must NOT clobber the successor's pending status — doing so
# stamps an un-run mandate 'consumed' and strands its cycles (observed silently
# at tics 284 / 326 / 348 / 350). Per CogPR-57 the runner is the sole mandate
# state owner; this keeps that ownership honest under the cross-mandate race.
# The coexisting layer cadence-side (wait_for_runner_quiescence, 30s) and this
# runner-side guard compose: cadence still writes after timeout (load-bearing),
# the runner now detects the successor and detaches instead of clobbering.
#
# Args:    $1 target_status   $2 completed_at   $3 extra-fields JSON (default {})
# Returns: 0 written to current.json · 3 detached (successor present; left alone)
# On detach, prints the successor mandate_id to stdout.
# ============================================================================
write_current_mandate_status() {
  # NB: do NOT inline a brace default like ${3:-{}} — bash leaks the default
  # word's literal '}' into the value when $3 is set (e.g. JSON '{...}' becomes
  # '{...}}'), corrupting WB_EXTRA with trailing "Extra data". Build it safely.
  local wb_extra="${3:-}"
  [ -n "$wb_extra" ] || wb_extra='{}'
  WB_EXPECT_ID="$MANDATE_ID" WB_STATUS="$1" WB_COMPLETED="$2" WB_EXTRA="$wb_extra" \
  WB_MF="$MANDATE_FILE" python3 - <<'PYEOF'
import json, os, sys
mf = os.environ['WB_MF']
try:
    with open(mf) as f:
        m = json.load(f)
except Exception as e:
    sys.stderr.write(f"WARN: write-back could not read {mf}: {e}; skipping current.json update.\n")
    sys.exit(3)
live = m.get('mandate_id', '')
if live != os.environ['WB_EXPECT_ID']:
    sys.stderr.write(
        "WARN: cross-mandate write-back averted — current.json now holds "
        f"'{live}', not '{os.environ['WB_EXPECT_ID']}' (cadence wrote a successor "
        "mid-run). Not clobbering the successor's pending status.\n")
    print(live)
    sys.exit(3)
m['status'] = os.environ['WB_STATUS']
m['completed_at'] = os.environ['WB_COMPLETED']
for k, v in json.loads(os.environ['WB_EXTRA']).items():
    m[k] = v
with open(mf, 'w') as f:
    json.dump(m, f, indent=2)
sys.exit(0)
PYEOF
}

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
# Pre-spawn: prune active-manifest of resolved entries
#
# Mechanizes "Signal Resolution Writeback Atomicity (Dual-Surface)" — keeps
# Mogul's signal_scan reading curated truth instead of stale resolved entries.
# Idempotent and cheap; safe to run before every mandate.
# ============================================================================

PRUNE_SCRIPT="$SCRIPT_DIR/manifest-prune.py"
if [ -f "$PRUNE_SCRIPT" ]; then
  python3 "$PRUNE_SCRIPT" --zone-root "$ZONE_ROOT" --quiet || \
    echo "WARN: manifest-prune failed (non-fatal); continuing" >&2
fi

# ============================================================================
# Pre-compute authoritative active signal count from active-manifest.jsonl
#
# Closes the runtime-parity gap from Disagreement-as-Evidence (CogPR-183):
# the cycle prompt instructs Mogul to read active-manifest.jsonl, but LLM
# agents historically re-derive counts from raw daily files (e.g., 294 vs 3
# at tic 205). Pre-computing here in bash and injecting the count as a
# mandatory fact in the prompt forecloses re-derivation.
# ============================================================================

ACTIVE_MANIFEST="$AUDIT_LOGS/signals/active-manifest.jsonl"
AUTH_SIGNAL_COUNT=0
AUTH_SIGNAL_IDS="[]"
if [ -f "$ACTIVE_MANIFEST" ]; then
  AUTH_SIGNAL_DATA=$(python3 -c "
import json
ids = []
try:
    with open('$ACTIVE_MANIFEST') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get('status') in ('active', 'acknowledged', 'working'):
                sid = obj.get('signal_id')
                if sid and sid not in ids:
                    ids.append(sid)
except Exception:
    pass
print(f'{len(ids)}|{json.dumps(ids)}')
" 2>/dev/null) || AUTH_SIGNAL_DATA="0|[]"
  AUTH_SIGNAL_COUNT=$(echo "$AUTH_SIGNAL_DATA" | cut -d'|' -f1)
  AUTH_SIGNAL_IDS=$(echo "$AUTH_SIGNAL_DATA" | cut -d'|' -f2-)
fi

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
   - signal_scan: AUTHORITATIVE COUNT IS PRE-COMPUTED. The runner has already read audit-logs/signals/active-manifest.jsonl (curated truth, post-prune) and counted signals with status in {active, acknowledged, working}. Authoritative count: $AUTH_SIGNAL_COUNT. Authoritative signal_ids: $AUTH_SIGNAL_IDS. Your report MUST use these values verbatim — do NOT re-derive from daily files, do NOT count raw emissions. Daily files audit-logs/signals/*.jsonl are raw emissions, not authoritative state. Your results.signal_scan object MUST include: {\"active_count\": $AUTH_SIGNAL_COUNT, \"active_signal_ids\": $AUTH_SIGNAL_IDS, \"authoritative_source\": \"active-manifest.jsonl (pre-computed by mogul-runner.sh)\"}.
   - memory_mining: scan MEMORY.md chain for recurring patterns, write findings
   - pattern_mining: run scripts/pattern_miner.py, output to audit-logs/patterns/
   - harmony_invoke: run scripts/harmony-invoke.sh (kernel-class autonomous_kernel.meaning.disposition; produces disposition packet to audit-logs/harmony/disposition-tic-N.json + appends invocations.jsonl audit trail). Read-only kernel; does not mutate governance state.
   - enrichment_scan: run scripts/cpr-enrichment-scanner.py, assess enrichment-eligible CPRs
   - ladder_audit: audit CLAUDE.md chain coherence
   - runtime_drift_check: compare installed vs canonical runtime surfaces. ALSO run scripts/check-harmony-readonly.py --json — verifies harmony engine src/harmony/*.ts modules contain no forbidden imports (atomic_append/queue/signals/manifest-prune/mandate/conformation) or write patterns (writeFileSync/appendFileSync/.write()). Surface any violations as drift findings (treat as TENSION/COGNITIVE per existing drift severity classification).
   - prompt_stack_audit: run scripts/prompt-stack-audit.py, scan CLAUDE.md chain for conflicts
   - cache_refresh: run \$ZONE_ROOT/vendor/context-grapple-gun/cgg-runtime/scripts/visitor-economy-monitor.py --cache-refresh \$TIC, report cache state + standing decay + biome health. Your results.cache_refresh object MUST include: {\"cache_state\": ..., \"standing_decay\": ..., \"biome_health\": ...} — EVEN WHEN THE CACHE IS EMPTY (e.g. {\"cache_state\": \"empty\", \"healthy\": true}). Do NOT report cache_refresh only in the prose summary; the structured results.cache_refresh key is the verified artifact.
   - deep_audit: comprehensive multi-rung scan
   - review_close_check: run scripts/review-close-check.py, verify post-review inscription consistency
   - civil_status_check: SPAWN the existing civil-engineer subagent via the STANDARD Agent tool (subagent_type: civil-engineer) — harness- and sovereign-contract-mediated, Claude Code default runtime; do NOT route it to any external compute backend. It runs the routine infrastructure-maintenance audit (index/registry/sync/health checks per cgg-runtime/agents/civil-engineer.md) and writes its civil-report to audit-logs/mogul/civil-reports/<YYYY-MM-DD>-tic-\$CURRENT_TIC.json. Do NOT reimplement civil logic inline — civil-engineer already exists; you only dispatch it (find-before-create). Your results.civil_status_check object MUST summarize {\"findings_count\": N, \"drift_detected\": N, \"report_path\": \"audit-logs/mogul/civil-reports/...\"}.
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
  \"artifacts\": {},
  \"results\": {
    \"signal_scan\": {},
    \"queue_refresh\": {}
  },
  \"civic_receipt\": {
    \"understood_scope\": \"what this mandate is + your lane, 1-2 sentences\",
    \"accepted_constraints\": [\"constraints you operated under, e.g. do-not-double-spawn, OT read-only\"],
    \"abstentions\": [\"what you deliberately did NOT do this run\"],
    \"first_action_or_escalation\": \"your first concrete action or escalation\",
    \"model\": \"your model id if known, e.g. claude-opus-4-8 (optional)\"
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
- You MUST populate a results.<cycle> key for EVERY cycle in cycle_request.run_now that you executed — INCLUDING trivial/empty-output cycles (e.g. cache_refresh on an empty cache). Describing an executed cycle only in the prose summary is NOT sufficient: the structured results object is the verified artifact and the runner FAILS the mandate if any executed cycle is missing its results key. (Conversely: do NOT invent results keys for cycles you did NOT execute.)
- civic_receipt is REQUIRED — your civic-orientation proof at the terminal boundary: understood_scope + first_action_or_escalation MUST be non-empty strings; accepted_constraints + abstentions MUST be non-empty lists. The runner REFUSES to mark the mandate consumed without a complete civic_receipt block (and refuses if the boot-receipt sink emission fails).
- The runner will REFUSE to mark mandate consumed if this file is missing or malformed"

# ============================================================================
# Invoke claude -p with Mogul identity
# ============================================================================

CLAUDE_BIN=$(command -v claude 2>/dev/null || true)
if [ -z "$CLAUDE_BIN" ]; then
  echo "ERROR: claude CLI not found in PATH" >&2
  # Transition: running -> failed (guarded write-back)
  WB_EXTRA=$(python3 -c "import json;print(json.dumps({'error':'claude CLI not found in PATH'}))")
  set +e; write_current_mandate_status "failed" "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)" "$WB_EXTRA"; set -e
  exit 1
fi

echo "Spawning claude -p for mandate $MANDATE_ID..."

# Unset CLAUDECODE to allow nested headless invocation
# (Claude Code blocks nesting by default; headless -p is safe)
# --dangerously-skip-permissions: no interactive user for tool approval
# --allowedTools: bounded tool set for governance work
#
# Agent added tic 404 (civil-cadence wiring tranche): the runner previously
# UNDER-granted mogul's declared toolset — mogul.md frontmatter declares
# `Read, Grep, Glob, Agent, Bash, Write, Edit`, and the MOGUL_PROMPT instructs
# mogul to "decompose, delegate, advance" — yet --allowedTools omitted Agent, so
# mogul could never spawn a subagent (a Conductor-Score-Runtime Parity gap in
# mogul's own tool surface). civil_status_check requires it: civil-engineer is an
# agent (no civil script exists; find-before-create), so the civil cycle spawns
# the existing civil-engineer subagent via the STANDARD Agent tool — harness- and
# sovereign-contract-mediated, Claude Code as the default runtime (no external
# compute backend routing). Edit kept out of mogul.md (already correct); the fix
# is the runner aligning to the declared toolset.
set +e
env -u CLAUDECODE "$CLAUDE_BIN" -p "$MOGUL_PROMPT" \
  --allowedTools "Read,Grep,Glob,Bash,Write,Agent" \
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
      harmony_invoke)
        # Verify disposition file exists for this tic + entry appended to
        # invocations.jsonl. The kernel itself is read-only; the runner
        # invokes harmony-invoke.sh which produces the audit artifact.
        HARMONY_DISPOSITION="$AUDIT_LOGS/harmony/disposition-tic-$CURRENT_TIC.json"
        HARMONY_INVOCATIONS="$AUDIT_LOGS/harmony/invocations.jsonl"
        if [ ! -f "$HARMONY_DISPOSITION" ]; then
          ARTIFACT_ERRORS="${ARTIFACT_ERRORS}harmony_invoke: disposition-tic-$CURRENT_TIC.json missing. "
        fi
        if [ ! -f "$HARMONY_INVOCATIONS" ]; then
          ARTIFACT_ERRORS="${ARTIFACT_ERRORS}harmony_invoke: invocations.jsonl missing. "
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
          PSA_COUNT=$(find "$PSA_DIR" -name "*-audit.json" -newer "$MANDATE_FILE_SNAPSHOT_REF" 2>/dev/null | wc -l | tr -d ' ')
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
          RCC_COUNT=$(find "$RCC_DIR" -name "*-check.json" -newer "$MANDATE_FILE_SNAPSHOT_REF" 2>/dev/null | wc -l | tr -d ' ')
        else
          RCC_COUNT=0
        fi
        if [ "$RCC_COUNT" -eq 0 ]; then
          ARTIFACT_ERRORS="${ARTIFACT_ERRORS}review_close_check: no consistency report produced. "
        fi
        ;;
      cache_refresh)
        # Verify cache_refresh produced a cache-state artifact
        CACHE_STATE_DIR="$AUDIT_LOGS/biome/pen-pal-cache/state-artifacts"
        if [ -d "$CACHE_STATE_DIR" ]; then
          CACHE_ARTIFACT_COUNT=$(find "$CACHE_STATE_DIR" -name "*-cache-state.json" -newer "$MANDATE_FILE_SNAPSHOT_REF" 2>/dev/null | wc -l | tr -d ' ')
        else
          CACHE_ARTIFACT_COUNT=0
        fi
        # Cache may be empty (valid) — check structured report has cache_refresh in results
        if [ -f "$STRUCTURED_REPORT" ]; then
          HAS_CACHE_RESULT=$(python3 -c "
import json
r = json.load(open('$STRUCTURED_REPORT'))
print('yes' if 'cache_refresh' in r.get('results', {}) else 'no')
" 2>/dev/null)
          if [ "$HAS_CACHE_RESULT" != "yes" ]; then
            ARTIFACT_ERRORS="${ARTIFACT_ERRORS}cache_refresh: not in structured report results. "
          fi
        fi
        ;;
      civil_status_check)
        # civil_status_check (WIRED tic 404) — verify the civil-engineer subagent
        # produced a fresh civil-report for this tic. Mirrors the review_close_check
        # artifact-file pattern (the -newer timing bug was fixed per civil F1, tic404).
        CIVIL_DIR="$AUDIT_LOGS/mogul/civil-reports"
        if [ -d "$CIVIL_DIR" ]; then
          CIVIL_COUNT=$(find "$CIVIL_DIR" -name "*tic-${CURRENT_TIC}*.json" -newer "$MANDATE_FILE_SNAPSHOT_REF" 2>/dev/null | wc -l | tr -d ' ')
        else
          CIVIL_COUNT=0
        fi
        # Accept either a fresh civil-report file OR the structured results key
        # (lenient like cache_refresh — a clean civil pass still self-reports).
        if [ "$CIVIL_COUNT" -eq 0 ] && [ -f "$STRUCTURED_REPORT" ]; then
          HAS_CIVIL_RESULT=$(python3 -c "
import json
r = json.load(open('$STRUCTURED_REPORT'))
print('yes' if 'civil_status_check' in r.get('results', {}) else 'no')
" 2>/dev/null)
          if [ "$HAS_CIVIL_RESULT" != "yes" ]; then
            ARTIFACT_ERRORS="${ARTIFACT_ERRORS}civil_status_check: no civil report produced and not in structured report results. "
          fi
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

  # Civic-receipt verification (Mogul runner receipt gate) — the report MUST carry a
  # complete civic_receipt block: the headless governance mutator's civic-orientation
  # proof surface at the terminal boundary. Reuses the ARTIFACT_ERRORS valve so a
  # missing/incomplete block fails-not-consumes through the existing gate below.
  if [ -f "$STRUCTURED_REPORT" ]; then
    CIVIC_CHECK=$(python3 -c "
import json
try:
    r = json.load(open('$STRUCTURED_REPORT'))
except Exception:
    print('civic_receipt: report unparseable'); raise SystemExit
cr = r.get('civic_receipt')
if not isinstance(cr, dict):
    print('civic_receipt block missing'); raise SystemExit
miss = []
if not (isinstance(cr.get('understood_scope'), str) and cr.get('understood_scope').strip()): miss.append('understood_scope')
if not (isinstance(cr.get('accepted_constraints'), list) and cr.get('accepted_constraints')): miss.append('accepted_constraints')
if not (isinstance(cr.get('abstentions'), list) and cr.get('abstentions')): miss.append('abstentions')
if not (isinstance(cr.get('first_action_or_escalation'), str) and cr.get('first_action_or_escalation').strip()): miss.append('first_action_or_escalation')
print('ok' if not miss else 'civic_receipt incomplete: '+','.join(miss))
" 2>/dev/null)
    if [ "$CIVIC_CHECK" != "ok" ]; then
      ARTIFACT_ERRORS="${ARTIFACT_ERRORS}${CIVIC_CHECK:-civic_receipt check failed}. "
    fi
  fi

  if [ -n "$ARTIFACT_ERRORS" ]; then
    echo "WARNING: Artifact verification failed: $ARTIFACT_ERRORS" >&2
    echo "Marking mandate as failed despite exit code 0."

    WB_EXTRA=$(WB_ERR="Artifact verification failed: $ARTIFACT_ERRORS" python3 -c "import json,os;print(json.dumps({'error':os.environ['WB_ERR']}))")
    set +e; write_current_mandate_status "failed" "$COMPLETED_AT" "$WB_EXTRA"; set -e

    python3 -c "
import json
t = {'transition': 'running_to_failed', 'mandate_id': '$MANDATE_ID', 'timestamp': '$COMPLETED_AT', 'reason': 'artifact_verification', 'errors': '$(echo "$ARTIFACT_ERRORS" | sed "s/'/\\\\'/g")'}
print(json.dumps(t))
" | while IFS= read -r _line; do safe_jsonl_append "$MANDATE_HISTORY_DIR/$TODAY.jsonl" "$_line"; done 2>/dev/null

    exit 1
  fi

  # ── Mogul runner receipt gate: emit the civic-orientation receipt BEFORE terminalizing.
  # Proof precedes close — a headless governance mutator must leave a civic proof surface
  # at the SAME boundary where it terminalizes work. Emit-failure is a HARD fail (this gate
  # exists to make the proof MANDATORY at the physics boundary), logged distinctly as
  # receipt_emit_failed (not artifact-verification ambiguity). civic_receipt presence is
  # already guaranteed by the verification gate above.
  RECEIPT_PAYLOAD="$CYCLE_REPORTS_DIR/.${TIMESTAMP}-tic-${CURRENT_TIC}.receipt-payload.json"
  # advisory detach flag: does current.json still hold our mandate? (the write-back is authoritative)
  LIVE_MID=$(python3 -c "import json;print(json.load(open('$MANDATE_FILE')).get('mandate_id',''))" 2>/dev/null)
  if [ "$LIVE_MID" = "$MANDATE_ID" ]; then RECEIPT_DETACHED=false; else RECEIPT_DETACHED=true; fi
  RECEIPT_BUILD=$(R_SR="$STRUCTURED_REPORT" R_TR="$TRANSCRIPT_FILE" R_MID="$MANDATE_ID" \
    R_DET="$RECEIPT_DETACHED" R_OUT="$RECEIPT_PAYLOAD" python3 -c "
import json, os
try:
    r = json.load(open(os.environ['R_SR']))
except Exception as e:
    print('BUILD_ERR:'+str(e)); raise SystemExit
cr = r.get('civic_receipt') or {}
payload = {
    'understood_scope': cr.get('understood_scope',''),
    'accepted_constraints': cr.get('accepted_constraints',[]),
    'abstentions': cr.get('abstentions',[]),
    'first_action_or_escalation': cr.get('first_action_or_escalation',''),
    'receipt_route': 'mogul-runner',
    'mandate_id': os.environ['R_MID'],
    'cycles_executed': r.get('cycles_executed',[]),
    'structured_report': os.environ['R_SR'],
    'transcript': os.environ['R_TR'],
    'detached': os.environ['R_DET']=='true',
    'model_of_record': cr.get('model') or 'unknown',
}
open(os.environ['R_OUT'],'w').write(json.dumps(payload))
print('ok')
" 2>&1)
  if [ "$RECEIPT_BUILD" != "ok" ]; then
    echo "ERROR: receipt_emit_failed (payload build): $RECEIPT_BUILD" >&2
    WB_EXTRA=$(WB_ERR="receipt_emit_failed: payload build: $RECEIPT_BUILD" python3 -c "import json,os;print(json.dumps({'error':os.environ['WB_ERR']}))")
    set +e; write_current_mandate_status "failed" "$COMPLETED_AT" "$WB_EXTRA"; set -e
    rm -f "$RECEIPT_PAYLOAD"
    exit 1
  fi
  BOOT_RECEIPT_SCRIPT="$SCRIPT_DIR/boot-receipt.py"
  [ -f "$BOOT_RECEIPT_SCRIPT" ] || BOOT_RECEIPT_SCRIPT="$HOME/.claude/cgg-runtime/scripts/boot-receipt.py"
  set +e
  RECEIPT_OUT=$(python3 "$BOOT_RECEIPT_SCRIPT" emit --entity ent_mogul --tic "$CURRENT_TIC" \
    --payload "$RECEIPT_PAYLOAD" --booted-from mandate-runner 2>/dev/null)
  RECEIPT_RC=$?
  set -e
  rm -f "$RECEIPT_PAYLOAD"
  RECEIPT_OK=$(RO="$RECEIPT_OUT" python3 -c "
import json,os
try:
    d=json.loads(os.environ['RO'])
except Exception:
    print('no'); raise SystemExit
print('yes' if d.get('status') in ('recorded','deduped') and not d.get('missing_fields') else 'no')
" 2>/dev/null)
  if [ "$RECEIPT_RC" -ne 0 ] || [ "$RECEIPT_OK" != "yes" ]; then
    echo "ERROR: receipt_emit_failed (sink emit rc=$RECEIPT_RC): $RECEIPT_OUT" >&2
    WB_EXTRA=$(WB_ERR="receipt_emit_failed: sink emit rc=$RECEIPT_RC" python3 -c "import json,os;print(json.dumps({'error':os.environ['WB_ERR']}))")
    set +e; write_current_mandate_status "failed" "$COMPLETED_AT" "$WB_EXTRA"; set -e
    python3 -c "
import json
t = {'transition': 'running_to_failed', 'mandate_id': '$MANDATE_ID', 'timestamp': '$COMPLETED_AT', 'reason': 'receipt_emit_failed'}
print(json.dumps(t))
" | while IFS= read -r _line; do safe_jsonl_append "$MANDATE_HISTORY_DIR/$TODAY.jsonl" "$_line"; done 2>/dev/null
    exit 1
  fi
  echo "Civic receipt emitted for ent_mogul tic $CURRENT_TIC (route=mogul-runner, detached=$RECEIPT_DETACHED)"

  # All artifacts verified — mark consumed (guarded write-back)
  WB_EXTRA=$(WB_SR="$STRUCTURED_REPORT" WB_TR="$TRANSCRIPT_FILE" python3 -c "import json,os;print(json.dumps({'structured_report':os.environ['WB_SR'],'transcript':os.environ['WB_TR']}))")
  set +e
  SUPERSEDED_BY=$(write_current_mandate_status "consumed" "$COMPLETED_AT" "$WB_EXTRA")
  WB_RC=$?
  set -e

  if [ "$WB_RC" -eq 0 ]; then
    echo "Mandate $MANDATE_ID consumed at $COMPLETED_AT"
    TRANSITION="running_to_consumed"
  else
    echo "Mandate $MANDATE_ID work completed at $COMPLETED_AT, but current.json holds successor '$SUPERSEDED_BY' — recording DETACHED (cycles ran + artifacts verified; successor left pending for normal consumption)."
    TRANSITION="running_to_consumed_detached"
  fi
  echo "Transcript: $TRANSCRIPT_FILE"
  echo "Report:     $STRUCTURED_REPORT"

  # Record transition with provenance (terminal record for THIS mandate's run;
  # appended to history regardless of detach — history is keyed by $MANDATE_ID,
  # not current.json, so it never clobbers).
  python3 -c "
import json
t = {
    'transition': '$TRANSITION',
    'mandate_id': '$MANDATE_ID',
    'timestamp': '$COMPLETED_AT',
    'transcript': '$TRANSCRIPT_FILE',
    'structured_report': '$STRUCTURED_REPORT',
    'actor': {'office': 'mogul', 'embodiment': 'cgg_runtime'},
    'orchestrated_by': 'homeskillet',
    'cycles_executed': '$CYCLES'.split(','),
    'artifacts_verified': True,
    'superseded_by': '$SUPERSEDED_BY',
    'birth_rung': '$BIRTH_RUNG'
}
print(json.dumps(t))
" | while IFS= read -r _line; do safe_jsonl_append "$MANDATE_HISTORY_DIR/$TODAY.jsonl" "$_line"; done 2>/dev/null
else
  WB_EXTRA=$(WB_EC="$CLAUDE_EXIT" python3 -c "import json,os;print(json.dumps({'error':'claude -p exited with code '+str(os.environ['WB_EC'])}))")
  set +e; write_current_mandate_status "failed" "$COMPLETED_AT" "$WB_EXTRA"; set -e

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
