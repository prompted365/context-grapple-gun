#!/usr/bin/env bash
# mogul-runner.sh — Mogul mandate consumer
#
# Reads authoritative mandate from audit-logs/mogul/mandates/current.json,
# validates status, binds Mogul office identity, invokes claude -p, and
# records lifecycle transitions.
#
# Usage:
#   scripts/mogul-runner.sh            Consume the pending mandate (default action — MUTATES governance state)
#   scripts/mogul-runner.sh --status   Read-only probe: print current mandate state, exit 0, mutate nothing
#   scripts/mogul-runner.sh --dry-run  Validate the pending mandate without executing (exit 2 = would execute)
#   scripts/mogul-runner.sh --help     Print usage
#
# A bare invocation is an ACTION, not a probe (cgg-ledger#bare-invocation-is-an-action-not-a-probe,
# /review 605→608): the mutating default (mandate consumption) requires NO flag, so this runner
# supplies a real read-only probe verb (--status) AND fails CLOSED on any unrecognized flag
# (usage + non-zero, runs nothing) rather than silently ignoring the flag and falling through to
# consumption. Live-hit at tic 619: `--status` was silently ignored and the runner consumed the
# pending mandate.
#
# Exit codes:
#   0 — mandate consumed successfully, OR --status probe printed state, OR --help
#   1 — error (no mandate, already consumed, runner failure)
#   2 — dry-run (mandate valid, would execute)
#  64 — usage error (unrecognized argument; NOTHING executed)

set -euo pipefail

print_usage() {
  cat <<'USAGE'
Usage:
  mogul-runner.sh            Consume the pending mandate (default — MUTATES governance state)
  mogul-runner.sh --status   Read-only probe: print current mandate state and exit 0 (no execution, no writes)
  mogul-runner.sh --dry-run  Validate the pending mandate without executing (exit 2 = would execute)
  mogul-runner.sh --help     Print this usage
USAGE
}

# ── Argument parse (fail-closed) ─────────────────────────────────────────────
# Only the bare invocation runs the mutating default. --dry-run and --status are
# explicit verbs; every other token is a usage error that executes NOTHING (it must
# never silently fall through to consumption). Only $1 is inspected — no call site
# passes positional args beyond a single leading flag (closed-consumer-set verified
# tic 620: cgg-gate.sh invokes bare; the smoke test invokes --dry-run).
DRY_RUN=false
STATUS_PROBE=false
case "${1:-}" in
  "")          : ;;                        # bare — legitimate consumption path (cgg-gate.sh spawn)
  --dry-run)   DRY_RUN=true ;;             # unchanged (smoke test relies on rc=2 / rc=1)
  --status)    STATUS_PROBE=true ;;        # read-only probe (added tic 620)
  -h|--help)   print_usage; exit 0 ;;
  *)           echo "ERROR: unrecognized argument '$1' — refusing to run. A bare invocation CONSUMES the pending mandate; use --status to probe read-only." >&2
               print_usage >&2
               exit 64 ;;
esac

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

# ============================================================================
# --status: read-only probe. Print the current mandate's identity + lifecycle
# timestamps (+ report path if present) and exit 0 WITHOUT invoking the mogul
# agent, running any cycle, or writing any file. This is the real read-only verb
# the bare-invocation-is-an-action doctrine requires. It short-circuits HERE —
# before the rung resolver runs, before the snapshot-dir mkdir/touch, and before
# the pending-status gate — so no side effect (subprocess spawn, file write, dir
# creation) can occur on the probe path. Reading current.json with python3 is a
# pure read, identical to how the consumption path reads status below.
# ============================================================================
if [ "$STATUS_PROBE" = true ]; then
  MF="$ZONE_ROOT/audit-logs/mogul/mandates/current.json" python3 - <<'PYEOF'
import json, os, sys
mf = os.environ['MF']
if not os.path.isfile(mf):
    print(f"mandate_file:  {mf}")
    print("status:        (no mandate file present)")
    sys.exit(0)
try:
    with open(mf) as f:
        m = json.load(f)
except Exception as e:
    print(f"mandate_file:  {mf}")
    print(f"status:        (unreadable: {e})")
    sys.exit(0)
def g(k):
    v = m.get(k)
    return v if (v is not None and v != '') else '—'
print(f"mandate_file:  {mf}")
print(f"mandate_id:    {g('mandate_id')}")
print(f"status:        {g('status')}")
print(f"created_at:    {g('created_at')}")
print(f"started_at:    {g('started_at')}")
print(f"completed_at:  {g('completed_at')}")
sr = m.get('structured_report')
if sr:
    print(f"report:        {sr}")
err = m.get('error')
if err:
    print(f"error:         {err}")
PYEOF
  exit 0
fi

# Resolve the CGG runtime scripts root (generator-surface fix, tic 552 — the
# mandate prompt previously hardcoded a vendor/ layout that does not exist in
# this federation; the drift fired 4 cross-tic times, 545→552, before landing
# here at the generator). Probe known layouts in order; first hit wins.
CGG_SCRIPTS=""
for cgg_cand in \
  "$ZONE_ROOT/vendor/context-grapple-gun/cgg-runtime/scripts" \
  "$ZONE_ROOT/canonical_developer/context-grapple-gun/cgg-runtime/scripts" \
  "$HOME/.claude/cgg-runtime/scripts"; do
  [ -d "$cgg_cand" ] && CGG_SCRIPTS="$cgg_cand" && break
done

# Resolve rung topology for provenance embedding
RUNG_RESOLVER="$CGG_SCRIPTS/rung_resolver.py"
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

# tic 596 (durable-lane discipline): moved the mtime anchor off /tmp into a canonical
# gitignored ephemeral lane. It stores NO mandate content — it is a 0-byte `touch -r`
# mtime source for the `find -newer` verifier clauses below; canonical-fs mtimes behave
# identically to /tmp (same APFS boot volume). Even a non-state marker in /tmp reads as a
# leak to a log-grepper. `.run/` is physics-layer gitignored (audit-logs/mogul/.run/) so
# the per-PID ref can never be swept into a commit.
MANDATE_SNAPSHOT_DIR="$AUDIT_LOGS/mogul/.run"
mkdir -p "$MANDATE_SNAPSHOT_DIR"
MANDATE_FILE_SNAPSHOT_REF="$MANDATE_SNAPSHOT_DIR/mandate-snapshot-$$.ref"
touch -r "$MANDATE_FILE" "$MANDATE_FILE_SNAPSHOT_REF"
trap 'rm -f "$MANDATE_FILE_SNAPSHOT_REF"' EXIT

# Obligation-clock pin (bk-review-close-check-obligation-clock-naming, /review-687
# ratified ray): export the DISPATCHED mandate's identity so child invocations —
# the agent's review-close-check.py runs — name their evidence artifact under the
# OBLIGATION's tic even when /cadence supersedes current.json mid-run (the executor
# clock, which files tic-N evidence under tic-N+1 across a boundary crossing).
# Composes with the tic-280 mtime snapshot above: that pins the READ side
# (find -newer verification); this pins the artifact-NAMING side.
export CGG_OBLIGATION_TIC="$CURRENT_TIC"
export CGG_OBLIGATION_MANDATE_ID="$MANDATE_ID"

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
import json, os, sys
# Active-ray predicate — SOURCE OF TRUTH: lib/signal_active.py (single-owner
# v2-projection retirement of the raw status-enum, tic 403; reader sweep tic
# 571). Import from the lib when path-reachable; else run the faithful
# embedded replica below (keep it in lockstep with signal_active.py).
is_active_ray = None
for _libdir in ['$SCRIPT_DIR/lib', os.path.expanduser('~/.claude/cgg-runtime/scripts/lib')]:
    if _libdir and os.path.isdir(_libdir):
        sys.path.insert(0, _libdir)
        try:
            from signal_active import is_active_ray
            break
        except Exception:
            sys.path.pop(0)
if is_active_ray is None:
    _TERM = frozenset({'resolved','dismissed','superseded'})
    _TERM_SS = frozenset({'resolved','superseded'})
    _CARRY = frozenset({'carried','dimmed'})
    _HEAT_FLOOR = 0.01
    def _heat(rec):
        h = rec.get('heat')
        if h is not None:
            try: return float(h)
            except (TypeError, ValueError): pass
        if rec.get('status','active') in _TERM: return 0.0
        vv = rec.get('visible_volume')
        if vv is None: vv = rec.get('volume', 0) or 0
        try: return min(1.0, max(0.0, float(vv)/100.0))
        except (TypeError, ValueError): return 0.0
    def is_active_ray(rec):
        status = rec.get('status','active'); ss = rec.get('structural_status')
        if status in _TERM or ss in _TERM_SS: return False
        if ss == 'live' or (ss is None and status in ('active','working')): return True
        if ss in _CARRY: return _heat(rec) > _HEAT_FLOOR
        return _heat(rec) > _HEAT_FLOOR
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
            if is_active_ray(obj):
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
   - queue_refresh: scan audit-logs/cprs/queue.jsonl, report state. First run: python3 $CGG_SCRIPTS/arena-pressure-ingest.py --zone-root \$ZONE_ROOT --quiet to discover arena candidates before scanning. MATURITY PREDICATE (the AGENT-CONSUMER axis, ratified /review 743 Q2 on cpr_mogul_queue_refresh_d9e2a59ba0c6 — you are a consumer with no call site, so this contract text IS your cure): resolve every row at latest-per-id and compute its fence as review_tic when present, else birth_tic + maturity_window_tics (both shapes are lawful at their own mint site; NEVER back-stamp review_tic; treat a prose-string maturity_window_tics as UNRESOLVABLE and disclose it, A4-743). A row is docket-eligible iff status == 'extracted' AND fence <= CURRENT_TIC, and you assert clock-currency (CURRENT_TIC read from the tic ledger THIS run, never from a cached projection's meta.current_tic — the CLOCK-INPUT face) before labelling any row mature or parked. Report pending_count over that predicate, and disclose the count of rows resolved through EACH shape. DISAGREEMENT SET (the COINCIDENT-ARMS face of guard 19 on ledger.md#presence-observation-fallacy-guard, ratified /review 752 C2 on cpr_mogul_queue_refresh_04fdfd8962fe): beside the per-shape count report shapes_disagreed_on_rows — the SET of live extracted row ids whose review_tic != birth_tic + maturity_window_tics (write the literal string 'empty' when the set is empty; never omit the key) — because where the two shapes agree row-for-row the per-shape split is a PROVENANCE NOTE (which field was read), never evidence the second shape was exercised, and the report must say so in one sentence; state once that at MINT the two shapes disagreed on 48 of 265 rows born 126-467 and on none born after 467 (measured tic 752), so an empty set is read as a property of the post-467 mint site, not of the predicate. EVALUABLE COUNT (the EMPTY-SET-CAUSE face, guard 19's third face, ratified /review 762 Q1 on cpr_mogul_queue_refresh_df535e0b7d15): beside shapes_disagreed_on_rows report evaluable_comparisons — the count of live extracted rows on which BOTH shapes could actually evaluate (both review_tic and birth_tic + maturity_window_tics resolvable) — because the literal 'empty' has two disjoint causes: (A) compared on every evaluable row and agreed, or (B) inputs absent so the inequality never evaluated; the licensed post-467-mint-site reading holds ONLY under cause (A), and an empty set with evaluable_comparisons=0 must be reported as 'nothing was compared', never as agreement.
   - signal_scan: AUTHORITATIVE COUNT IS PRE-COMPUTED. The runner has already read audit-logs/signals/active-manifest.jsonl (curated truth, post-prune) and counted ACTIVE RAYS per the shared is_active_ray predicate (lib/signal_active.py — structurally live, or carried/dimmed with heat above floor; the raw status enum is retired). Authoritative count: $AUTH_SIGNAL_COUNT. Authoritative signal_ids: $AUTH_SIGNAL_IDS. Your report MUST use these values verbatim — do NOT re-derive from daily files, do NOT count raw emissions. Daily files audit-logs/signals/*.jsonl are raw emissions, not authoritative state. Your results.signal_scan object MUST include: {\"active_count\": $AUTH_SIGNAL_COUNT, \"active_signal_ids\": $AUTH_SIGNAL_IDS, \"authoritative_source\": \"active-manifest.jsonl (pre-computed by mogul-runner.sh)\"}.
   - memory_mining: scan MEMORY.md chain for recurring patterns, write findings. MEASURE-VALIDITY CLAUSE (the AGENT-CONSUMER axis, ratified /review 747 Q3 on cpr_mogul_memory_mining_fefd6a73fa3b — you are a consumer with no call site, so this contract text IS the guard that pattern_miner.py carries in code under cgg-ledger#recurrence-measure-invalid-over-shared-generator-corpus): the memory root's feedback_*.md corpus is a SHARED-GENERATOR corpus (one lead, one authoring convention, one voice), so any lexical or thematic recurrence measured over it measures the authoring convention, not recurrence in the world. Declare the corpus's authorship status in results.memory_mining, report any recurrence pass over it as MEASURE-INVALID, WITHHOLD hit rates and cluster sizes as findings (a 63/96 top cluster is broad-term over-matching, not a signal — t744), and promote a recurrence to a candidate ONLY when an instrument independent of the corpus corroborates it in the same run (name the instrument and its artifact; t747 lived: the lane reported a recurrence without the disclosure once the hand-fired guard lapsed). The structural audit is unaffected (it measures the index's shape, not recurrence): invoke memory-md-audit.py as a BARE CALLER (no --tic) so tic_source resolves in-emitter to tic_ledger, and report tic_source (the t747 test, paid non-vacuously, now standing).
   - pattern_mining: run $CGG_SCRIPTS/pattern_miner.py, output to audit-logs/patterns/
   - harmony_invoke: run $CGG_SCRIPTS/harmony-invoke.sh (kernel-class autonomous_kernel.meaning.disposition; produces disposition packet to audit-logs/harmony/disposition-tic-N.json + appends invocations.jsonl audit trail). Read-only kernel; does not mutate governance state. WINDOW-vs-POINT (the THIRD ray on ledger.md#disagreement-as-evidence, ratified /review 752 C1 on cpr_mogul_harmony_invoke_6689bad2ad26): the packet carries a WINDOWED aggregate (voice.admission_gate_watch: fired / count / refusal_tics over window_runs_including_current) beside THIS tic's POINT event — read voice.fallback_reason and voice.fallback_families.current BEFORE validators_passed or admission_gate_watch.fired, and never let a fired watch stand as this tic's own event: report the window as a window (name its refusal_tics and its denominator) and the point as a point (name its cause and family; validators_passed=false is VACUOUS when no output reached the validators, e.g. a CLI timeout). PRODUCER-LIVENESS (the ruled reader half of /review 756 Q1, ledger.md#two-phase-fail-soft-artifact-absence-is-typed-by-producer-liveness-not-shape): the disposition is written in TWO phases (engine, then the fail-soft voice amender); if the voice block is ABSENT, type the absence from the packet's own voice_step marker — run $CGG_SCRIPTS/harmony-voice-marker.py classify --disposition <path> — never from the packet's shape or a sibling-tic diff: amender_running is NOT a fault (re-read after it finishes), amender_failed is a typed failure, marker_absent_probe_liveness means probe the process table / exit status / invocations.jsonl row BEFORE typing anything. Record the absence_type you typed and what you typed it from.
   - contagion_heartbeat: run $CGG_SCRIPTS/contagion-invoke.sh (kernel-class ContagionMatch v0, harmony_invoke's sibling seam; conformation-proximity match over learned coordinates — NOT LLM-backed, NOT coupled to the 27B; produces disposition packet to audit-logs/contagion/disposition-tic-N.json + refreshes current-pointer.json + appends invocations.jsonl). Read-only kernel; emits a NON-CITABLE shaping packet; does not mutate governance state. The office-worldview boot render consumes current-pointer.json (staleness-canaried) — this cycle is the producer half of that heartbeat (GO ratified /review 545).
   - economy_heartbeat: run $CGG_SCRIPTS/economy-invoke.sh (the c-coin shadow economy, H-2.5 seed; runs ONE economy tic in gunslinger seed mode — the 128-agent nautilus swarm accrues trust -> aggregate g_t -> gates the mint (coin<->trust closed), the federal exchange is held/normalized at the tic boundary, EconomyBreachFlags stay first-class visible; deterministic/local, NOT LLM-backed; produces audit-logs/economy/economy-tic-N.json + refreshes current-pointer.json + appends invocations.jsonl). Read-only of governance state; writes ONLY to audit-logs/economy/; does not mutate signals/queue/mandate/conformations. Producer half of the economy heartbeat (Architect "wire" GO tic 568). Your results.economy_heartbeat object MUST include {\"tic\": N, \"mode\": \"gunslinger\", \"series_mode\": \"genesis|continue|replay\", \"g_t\": ..., \"mint_total\": ..., \"seed_stabilized\": bool, \"execution_attested\": bool, \"breach_flags\": [...], \"breach_dwell\": {...}} — execution_attested is the attest-on-execution bit (t684 cure): seed_stabilized alone reads breach-visibility as instability; a breach-showing tic with a completed run is attested TRUE. breach_dwell is the CENSUS (t732 cure, /review 732 consumer-contract ray on the t725 dwell-altitude lesson): copy the emitter's top-level breach_dwell object verbatim — g_t is the end-of-tic point-sample, NOT a mean, and on saturated tics the two invert (t729: g_t 0.734 'recovered' while dwell.fraction 0.932 saturated); a report demanding only the terminal sample can tell the tic's story backwards. FIELD QUALIFICATION (t733 cure, /review 733 sem-identity data-field ray; path REPINNED /review 737 per cpr_mogul_economy_heartbeat_5caab586f38c — the shallow path never resolved, value-identity through the top-level alias had masked the address rot): the demanded g_t key IS detail.economy_trace.CADENCE.swarm_final_aggregate_g_t — swarm aggregate TRUST at the last internal tick; it is NOT the artifact's inner economy_g_t (g_t_trajectory_samples — a different quantity ~10x smaller sharing the token). Any report/prose quoting this key names the qualified referent (swarm trust, terminal sample), never the bare colliding token as if it were the economy's own g_t. RESOLUTION-FAILURE CLAUSE (t740 cure, /review 740 substitution face on the same ray): if the demanded path does not resolve against the artifact, the report DECLARES resolution_failure for that key — it NEVER substitutes a same-named neighbor at another altitude (the top-level g_t alias included); the right number from the wrong place is the failure mode, not a fallback. TYPED-RUN PROPAGATION (t734 cure, /review 734 conductor-score-runtime-parity ray on the t731 replay-report lesson): series_mode copies the advance_guard's own run typing verbatim — genesis|continue|replay. The guard already refuses to clobber the three WRITE surfaces on replay; this key carries that same typing across the REPORT membrane, so a replay tic (deliberately non-authoritative economy values) is schema-distinguishable from canonical instead of presenting AS the tic's economy (t731 lived: replay g_t 0.756 vs canonical 0.451 under one tic label). A report whose series_mode is replay quotes economy values only WITH that qualifier. PHASE CLAUSE (t742 cure, /review 742 phase-half ray on the t725 dwell-altitude lesson, cpr_mogul_economy_heartbeat_a57aee1fda06 — FOURTH ray on ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude): the terminal point-sample is PERIODIC — it occupies two disjoint bands (LO ~0.45-0.55 / HI ~0.70-0.76) and alternates between them on a phase-locked slip clock (21/26 consecutive pairs 716-742; slips every ~6 tics, gaps in [5,7]) — so a consecutive-tic g_t delta reports the PHASE, not the economy. NEVER narrate a one-tic g_t movement as trust recovered / degraded / flat; a g_t delta is reportable ONLY against a multi-tic aggregate, or against a same-parity tic whose parity is READ OFF THE OBSERVED BAND SERIES — never computed from tic arithmetic (the mod-6 residue class was tested and falsified). The dwell census remains the within-tic story (t742 lived: dsample -0.0015 'flat' beside ddwell 0.885->0.075 in one tic). When quoting g_t, name its band and, for any comparison, the parity source; the pending clock ray is cpr_mogul_economy_heartbeat_64367ac313d3 (fence 745).
   - enrichment_scan: run $CGG_SCRIPTS/cpr-enrichment-scanner.py, assess enrichment-eligible CPRs
   - ladder_audit: audit CLAUDE.md chain coherence
   - runtime_drift_check: compare installed vs canonical runtime surfaces. ALSO run $CGG_SCRIPTS/check-harmony-readonly.py --json AND $CGG_SCRIPTS/check-contagion-readonly.py --json — each verifies its engine's modules contain no forbidden imports (atomic_append/queue/signals/manifest-prune/mandate/conformation) or write patterns (writeFileSync/appendFileSync/.write()). Surface any violations as drift findings (treat as TENSION/COGNITIVE per existing drift severity classification).
   - prompt_stack_audit: run $CGG_SCRIPTS/prompt-stack-audit.py, scan CLAUDE.md chain for conflicts
   - cache_refresh: run $CGG_SCRIPTS/visitor-economy-monitor.py --full-cycle \$TIC (NOT --cache-refresh: that flag's producer measures cache_state ONLY, and the two other demanded keys would be filled by your inference reading as measurement — the t687/t692 defect, bk-mandate-cache-refresh-contract-producer-split). The full-cycle output MEASURES every demanded key: build results.cache_refresh from it as {\"cache_state\": <full_cycle.cache_refresh.cache_state>, \"standing_decay\": <full_cycle.standing_decay>, \"biome_health\": <full_cycle.biome_health>} — all three measured, never derived — EVEN WHEN THE CACHE IS EMPTY (e.g. cache_state {\"summary\": {\"total_entries\": 0}}). The extra full-cycle keys (census, economy_observation) are benign byproducts; do not promote them into results.cache_refresh. Do NOT report cache_refresh only in the prose summary; the structured results.cache_refresh key is the verified artifact. DURABLE ARTIFACT (t714 cure, the a4c8 no-path ray): the producer persists its full output to audit-logs/visitor-economy/full-cycle-tic-\$TIC.json — if your read of the stdout is clipped, RE-READ that artifact; never re-execute the signal-emitting cycle to recover a measurement. Verify the artifact landed (results.artifact_path non-null) and cite it in results.cache_refresh as {\"artifact_path\": <full_cycle.artifact_path>}; a null artifact_path with artifact_write_error is a finding to surface, not to absorb.
   - deep_audit: comprehensive multi-rung scan
   - review_close_check: run $CGG_SCRIPTS/review-close-check.py, verify post-review inscription consistency
   - civil_status_check: NOT YOURS TO DISPATCH (every backend — /review 750 Q8, F-750-M1). civil_status_check is handled OUT-OF-BAND by this runner's own carve-out AFTER you finish: a separate \`claude -p --agent civil-engineer\` invocation runs the civil-engineer office steward as its own session agent and the runner merges results.civil_status_check into your report before verification. Do NOT dispatch civil-engineer, do NOT spawn any subagent for it, do NOT add a results.civil_status_check key, and NEVER hold, wait, or end your turn expecting a callback — under print mode there is no next turn, and a held background subagent is killed at the harness ceiling (tic 750: the report was never written and the mandate failed with 10/11 cycles' artifacts real on disk). Run every OTHER cycle in cycle_request.run_now normally and list only those in cycles_executed.
3. Write a DEDICATED structured JSON cycle report using Write tool to EXACTLY this path — and write it BEFORE any hold, wait, or dispatch of any kind (a report that exists is verifiable; a promise to write one after a callback is not, because in print mode the callback never comes):
   $STRUCTURED_REPORT
   This file is your governance evidence artifact. It MUST follow the schema below exactly.
4. Do NOT modify CLAUDE.md, MEMORY.md, or any constitutional surface
5. Do NOT invent cycles beyond what the mandate specifies
6. Working directory is: $ZONE_ROOT

## CogPR candidates — emit durable lessons (the runner ingests them canonical-side)

If a META cycle (memory_mining, pattern_mining, ladder_audit, deep_audit,
review_close_check) surfaces a DURABLE CogPR candidate — a new rule, pattern, or
correction worth /review — emit it as a structured object in a top-level
\`candidate_cogprs\` array (and/or under results.<cycle>.candidate_cogprs). Each:
{\"lesson\": \"<the full lesson — REQUIRED>\", \"band\": \"COGNITIVE|STRUCTURAL|PRIMITIVE|SOCIAL\", \"subsystem\": \"...\", \"confidence_tier\": \"tentative|...\", \"lesson_type\": \"...\", \"recommended_scopes\": [\"...\"], \"note\": \"...\", \"source_cycle\": \"<cycle>\"}.
RECOMMENDED (never required) expression for any minted candidate/finding — the six-facet strike: KAT (IS, the centroid) / APO (IS-NOT, the heaviest facet: the nearest excluded neighbors) / PAR (HOLDS, the tension held) / PLE (COMPLEMENT) / ENA (COUNTER, the failure it answers) / TEL (TELOS, what it serves).
Optional fields alongside the shape above: \`relations\` (sibling:/refines:/composes:/distinct_from: edges) · \`apophatic_exclusions\` (what it is NOT; nearest excluded neighbors) · \`slice_scope\` (centroid claims are slice-scoped and observer-indexed, never global) · \`cost_of_action\` · \`cost_of_inaction\` (a short assessed clause each, neither primary) · \`deferred_facets\` (a facet you cannot fill is DECLARED ABSENT, never fabricated).
These are OPTIONAL forever — omitting any of them is never a defect, and nothing here refuses a candidate for their absence. Full explainer: the EXPRESSION ray in the boot worldview (office-worldview.py).
Do NOT write queue.jsonl yourself — the runner ingests candidate_cogprs into the
queue (the birth ledger) canonical-side AFTER this report is validated (the
sole-writer gate: you produce the artifact, the canonical runner is the sole
writer of governance state; a birth-state row is non-terminal — promotion stays
/review-gated). Omit the array or leave it empty if nothing durable surfaced — do
NOT invent candidates to fill it.

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
  \"candidate_cogprs\": [],
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
# Invoke the mogul agent — backend-selectable (claude default | codex/gpt-5.5)
# ============================================================================
#
# Backend selection (tic 438, Architect-directed): the runner's headless agent
# lane is per-lane selectable between the Codex / GPT-5.5 backend and Claude Code.
# Selector: MOGUL_RUNNER_BACKEND env (values: codex | claude).
#
# DEFAULT = claude (Architect direction tic 456: "switch mogul back to claude code
# for now" — in the canonical mount). Codex/GPT-5.5 is now a per-spawn opt-in
# (set MOGUL_RUNNER_BACKEND=codex). History: the default was codex from tic 438
# (Architect: "set the 5.5 model to default for mogul"); flipped back to claude at
# tic 456 — only the default VALUE moved, the per-lane selector is unchanged.
# Claude Code is also the civil-carve-out lane (always, regardless of default — see
# fence below).
#
# Compute-admission framing (ledger#compute-admission-law-topology-agnostic,
# promoted /review 324): codex is an EXTERNAL EGRESS backend (OpenAI). With the
# default flipped back to claude (tic 456) the mogul GOVERNANCE lane is
# Claude-Code-mediated by default again; codex egress is an explicit per-spawn
# opt-in (MOGUL_RUNNER_BACKEND=codex), distinct from the compute INFERENCE lane
# where mlx_local/no-egress stays primary. If codex is requested but its binary is
# absent the runner auto-falls-back to claude; a codex RUNTIME error (auth/API)
# fails the mandate — drop the override to recover. Registered in
# ak_control_room/providers.yaml.
#
# Standing fence (carried verbatim from the prior single-backend comment + the
# MOGUL_PROMPT civil_status_check instruction): civil_status_check spawns the
# civil-engineer SUBAGENT, which is Claude-Code-mediated. It NEVER routes to an
# external compute backend. When backend=codex AND civil_status_check is in the
# cycle set, the runner CARVES civil out of the codex prompt and dispatches it
# separately on Claude Code, then merges results.civil_status_check into the
# codex-written report. (Per Architect tic 438: per-lane selector; civil stays
# on Claude Code.)
#
# Agent added tic 404 (civil-cadence wiring tranche): the claude lane grants the
# Agent tool so mogul can spawn the civil-engineer subagent (mogul.md declares
# `Read, Grep, Glob, Agent, Bash, Write, Edit`; --allowedTools must include Agent
# for civil_status_check). Edit kept out of mogul.md (already correct).

MOGUL_RUNNER_BACKEND="${MOGUL_RUNNER_BACKEND:-claude}"

# Model floor for the claude lane (tic 677, bk-mogul-runner-model-floor): the
# nested `claude -p` previously inherited the CLI default model with no floor —
# a credit-wall HTTP 429 on that default (fable-5, tic-676 live hit: 0/7 cycles,
# 0 tokens, transcript 2026-07-30T170834-tic-676.json) failed the whole mandate.
# Default = opus per feedback_workflow-engines-opus-not-fable (workflow/fleet
# dispatches run on opus; the lead's seat model is never inherited by fleets).
# Per-spawn override: MOGUL_RUNNER_MODEL=<model> — applies to BOTH claude spawn
# sites (main lane + civil carve-out; sibling-site closure per
# cgg-ledger#named-footgun-guard-leaves-sibling-site-unfixed).
MOGUL_RUNNER_MODEL="${MOGUL_RUNNER_MODEL:-opus}"

# Resolve Claude (always needed: the default backend AND the civil carve-out lane)
CLAUDE_BIN=$(command -v claude 2>/dev/null || true)

# Resolve Codex (app-bundle binary preferred — the Volta shim's native binary is
# absent on this host; /Applications/Codex.app ships a working arm64 codex CLI)
CODEX_BIN=""
for _cx in "/Applications/Codex.app/Contents/Resources/codex" "$(command -v codex 2>/dev/null || true)"; do
  if [ -n "$_cx" ] && [ -x "$_cx" ]; then CODEX_BIN="$_cx"; break; fi
done

# Does this mandate include the Claude-pinned civil cycle?
CIVIL_IN_CYCLES=false
case ",$CYCLES," in *,civil_status_check,*) CIVIL_IN_CYCLES=true;; esac

# Validate the selected backend's binary; fall back to claude if codex is missing.
if [ "$MOGUL_RUNNER_BACKEND" = "codex" ] && [ -z "$CODEX_BIN" ]; then
  echo "WARN: backend=codex requested but no codex binary found; falling back to claude" >&2
  MOGUL_RUNNER_BACKEND="claude"
fi
# Claude is required for the default lane AND for the codex+civil carve-out.
NEED_CLAUDE=false
[ "$MOGUL_RUNNER_BACKEND" = "claude" ] && NEED_CLAUDE=true
{ [ "$MOGUL_RUNNER_BACKEND" = "codex" ] && [ "$CIVIL_IN_CYCLES" = true ]; } && NEED_CLAUDE=true
if [ "$NEED_CLAUDE" = true ] && [ -z "$CLAUDE_BIN" ]; then
  echo "ERROR: claude CLI not found in PATH (required for backend=$MOGUL_RUNNER_BACKEND${CIVIL_IN_CYCLES:+ + civil carve-out})" >&2
  WB_EXTRA=$(python3 -c "import json;print(json.dumps({'error':'claude CLI not found in PATH'}))")
  set +e; write_current_mandate_status "failed" "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)" "$WB_EXTRA"; set -e
  exit 1
fi

echo "Backend: $MOGUL_RUNNER_BACKEND | model_floor: $MOGUL_RUNNER_MODEL | civil_in_cycles: $CIVIL_IN_CYCLES"
echo "Spawning $MOGUL_RUNNER_BACKEND agent for mandate $MANDATE_ID..."

set +e
if [ "$MOGUL_RUNNER_BACKEND" = "codex" ]; then
  # ---- Codex / GPT-5.5 lane -------------------------------------------------
  # Hook isolation: --ignore-user-config drops ~/.codex/config.toml, where the
  # [hooks.state] enablements live -> NO codex hooks fire (cgg-gate would re-enter
  # the mandate dispatcher; session-restore would inject the ORCHESTRATOR
  # worldview, the wrong identity for Mogul). Auth still resolves from CODEX_HOME.
  # sandbox=danger-full-access + approval=never == the --dangerously-skip-permissions
  # analog. -c model_reasoning_effort=high restores reasoning (config drop zeroes it).
  CODEX_PROMPT="$MOGUL_PROMPT"
  if [ "$CIVIL_IN_CYCLES" = true ]; then
    CODEX_PROMPT="$CODEX_PROMPT

## RUNTIME CARVE-OUT (codex lane — Architect tic 438)
civil_status_check is handled OUT-OF-BAND by the runner on Claude Code (the
civil-engineer subagent is Claude-Code-mediated and NEVER routes to an external
compute backend). Do NOT attempt civil_status_check. Do NOT add a
results.civil_status_check key — the runner merges it after you finish. Run every
OTHER cycle in cycle_request.run_now normally, and list only those in
cycles_executed."
  fi
  # stdin from /dev/null is REQUIRED: `codex exec` with a prompt arg still tries
  # to read stdin, and when spawned headless (stdin is a non-TTY pipe from the
  # orchestrator) it BLOCKS forever at "Reading additional input from stdin..."
  # until EOF. /dev/null forces immediate EOF so only the prompt arg is used.
  # (Verified tic 438: without it, a real round-trip hung 15+ min, zero output.)
  CODEX_HOME="${CODEX_HOME:-$HOME/.codex}" "$CODEX_BIN" exec \
    -m gpt-5.5 \
    -c model_reasoning_effort=high \
    -s danger-full-access \
    --skip-git-repo-check \
    --ignore-user-config \
    -C "$ZONE_ROOT" \
    -o "${TRANSCRIPT_FILE%.json}.last-message.txt" \
    "$CODEX_PROMPT" \
    < /dev/null \
    > "$TRANSCRIPT_FILE" 2>&1
  CLAUDE_EXIT=$?
else
  # ---- Claude Code lane (default) ------------------------------------------
  # Unset CLAUDECODE to allow nested headless invocation (Claude Code blocks
  # nesting by default; headless -p is safe). --allowedTools includes Agent so
  # mogul can spawn the civil-engineer subagent for civil_status_check.
  env -u CLAUDECODE "$CLAUDE_BIN" -p "$MOGUL_PROMPT" \
    --model "$MOGUL_RUNNER_MODEL" \
    --allowedTools "Read,Grep,Glob,Bash,Write,Agent" \
    --dangerously-skip-permissions \
    --output-format json \
    > "$TRANSCRIPT_FILE" 2>&1
  CLAUDE_EXIT=$?
fi
set -e

# ---- Civil carve-out merge (EVERY backend + civil requested — /review 750 Q8) ---
# The codex agent ran every cycle EXCEPT civil. Dispatch civil-engineer on Claude
# Code, capture its summary, and merge results.civil_status_check into the
# codex-written report BEFORE the per-cycle verification below (which iterates the
# full $CYCLES and would otherwise flag civil as a missing results key). The fence
# holds: civil-engineer never touches the external backend.
if [ "$CIVIL_IN_CYCLES" = true ] && [ $CLAUDE_EXIT -eq 0 ]; then
  echo "Civil carve-out: running civil-engineer as its own session agent (claude -p --agent civil-engineer; every backend — /review 750 Q8; fence: civil stays sovereign)..."
  CIVIL_FRAGMENT="$CYCLE_REPORTS_DIR/.${TIMESTAMP}-tic-${CURRENT_TIC}.civil-fragment.json"
  CIVIL_PROMPT="You ARE the civil-engineer office steward — booted as the SESSION AGENT by the mogul-runner civil carve-out for tic $CURRENT_TIC (mandate $MANDATE_ID). Working directory: $ZONE_ROOT.
Run your routine infrastructure-maintenance audit per your own spec (cgg-runtime/agents/civil-engineer.md: index/registry/sync/health checks) and write your civil-report to audit-logs/mogul/civil-reports/<YYYY-MM-DD>-tic-$CURRENT_TIC.json (the prior report for lineage: the most recent file in that directory).
You are the seat: do NOT spawn any subagent and do NOT hold for any background task — print mode has no next turn.
Then write EXACTLY this JSON file using the Write tool to: $CIVIL_FRAGMENT
{\"findings_count\": <int>, \"drift_detected\": <int>, \"report_path\": \"audit-logs/mogul/civil-reports/...\", \"runtime\": \"claude_code\"}
Do nothing else. Do NOT modify CLAUDE.md, MEMORY.md, queue.jsonl, or any governance surface."
  set +e
  env -u CLAUDECODE "$CLAUDE_BIN" -p "$CIVIL_PROMPT" \
    --agent civil-engineer \
    --model "$MOGUL_RUNNER_MODEL" \
    --allowedTools "Read,Grep,Glob,Bash,Write,Agent" \
    --dangerously-skip-permissions \
    --output-format json \
    >> "$TRANSCRIPT_FILE" 2>&1
  CIVIL_EXIT=$?
  set -e
  # Merge the civil fragment into the codex report (additive; never overwrites
  # existing results). Failure to produce the fragment fails the mandate — civil
  # signal must not silently go dark.
  if [ $CIVIL_EXIT -eq 0 ] && [ -s "$CIVIL_FRAGMENT" ] && [ -f "$STRUCTURED_REPORT" ]; then
    MERGE_OK=$(SR="$STRUCTURED_REPORT" CF="$CIVIL_FRAGMENT" python3 -c "
import json, os
try:
    r = json.load(open(os.environ['SR']))
    civ = json.load(open(os.environ['CF']))
except Exception as e:
    print('merge_failed: '+str(e)); raise SystemExit
r.setdefault('results', {})
r['results']['civil_status_check'] = civ
ce = r.get('cycles_executed', [])
if 'civil_status_check' not in ce:
    ce.append('civil_status_check'); r['cycles_executed'] = ce
json.dump(r, open(os.environ['SR'], 'w'), indent=2)
print('OK')
" 2>&1)
    echo "Civil merge: $MERGE_OK"
    [ "$MERGE_OK" != "OK" ] && CLAUDE_EXIT=1
  else
    echo "ERROR: civil carve-out failed (exit=$CIVIL_EXIT, fragment missing or report absent) — failing mandate to avoid dropping civil signal" >&2
    CLAUDE_EXIT=1
  fi
fi

# ---- Backend self-identification stamp --------------------------------------
# Every cycle report says which engine ran it: actor.runtime = the backend.
# Additive only (never clobbers actor.office/embodiment or an agent-set runtime).
if [ -f "$STRUCTURED_REPORT" ]; then
  SR="$STRUCTURED_REPORT" BK="$MOGUL_RUNNER_BACKEND" python3 -c "
import json, os
try:
    r = json.load(open(os.environ['SR']))
except Exception:
    raise SystemExit
a = r.get('actor')
if isinstance(a, dict) and 'runtime' not in a:
    a['runtime'] = ('codex_gpt5_5' if os.environ['BK'] == 'codex' else 'claude_code')
    json.dump(r, open(os.environ['SR'], 'w'), indent=2)
" 2>/dev/null || true
fi

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
      contagion_heartbeat)
        # Verify disposition exists for this tic AND current-pointer.json was
        # re-aimed at this tic. The pointer-tic check is the anti-freeze tooth:
        # the pointer sat frozen at tic 453 for 93 tics while dispositions went
        # written-never-read (GO ratified /review 545, bk-contagion-heartbeat-
        # cycle). Kernel is read-only; contagion-invoke.sh produces the audit
        # artifacts; the office-worldview boot render is the demand-side consumer.
        CONTAGION_DISPOSITION="$AUDIT_LOGS/contagion/disposition-tic-$CURRENT_TIC.json"
        CONTAGION_POINTER="$AUDIT_LOGS/contagion/current-pointer.json"
        if [ ! -f "$CONTAGION_DISPOSITION" ]; then
          ARTIFACT_ERRORS="${ARTIFACT_ERRORS}contagion_heartbeat: disposition-tic-$CURRENT_TIC.json missing. "
        fi
        if [ -f "$CONTAGION_POINTER" ]; then
          CONTAGION_POINTER_TIC=$(python3 -c "import json;print(json.load(open('$CONTAGION_POINTER')).get('tic',''))" 2>/dev/null)
          if [ "$CONTAGION_POINTER_TIC" != "$CURRENT_TIC" ]; then
            ARTIFACT_ERRORS="${ARTIFACT_ERRORS}contagion_heartbeat: current-pointer.json tic=$CONTAGION_POINTER_TIC, expected $CURRENT_TIC (frozen pointer). "
          fi
        else
          ARTIFACT_ERRORS="${ARTIFACT_ERRORS}contagion_heartbeat: current-pointer.json missing. "
        fi
        ;;
      economy_heartbeat)
        # Verify the economy tick snapshot exists for this tic AND
        # current-pointer.json was re-aimed at this tic (anti-freeze tooth,
        # mirroring contagion_heartbeat). The seed now runs itself each tic
        # (Architect "wire" GO tic 568); economy-invoke.sh is the producer half.
        ECONOMY_SNAPSHOT="$AUDIT_LOGS/economy/economy-tic-$CURRENT_TIC.json"
        ECONOMY_POINTER="$AUDIT_LOGS/economy/current-pointer.json"
        if [ ! -f "$ECONOMY_SNAPSHOT" ]; then
          ARTIFACT_ERRORS="${ARTIFACT_ERRORS}economy_heartbeat: economy-tic-$CURRENT_TIC.json missing. "
        fi
        if [ -f "$ECONOMY_POINTER" ]; then
          ECONOMY_POINTER_TIC=$(python3 -c "import json;print(json.load(open('$ECONOMY_POINTER')).get('tic',''))" 2>/dev/null)
          if [ "$ECONOMY_POINTER_TIC" != "$CURRENT_TIC" ]; then
            ARTIFACT_ERRORS="${ARTIFACT_ERRORS}economy_heartbeat: current-pointer.json tic=$ECONOMY_POINTER_TIC, expected $CURRENT_TIC (frozen pointer). "
          fi
        else
          ARTIFACT_ERRORS="${ARTIFACT_ERRORS}economy_heartbeat: current-pointer.json missing. "
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

  # ── Canonical-side CogPR candidate ingest (Architect-directed tic 439) ───────
  # The backend EMITTED any durable candidates into the report's candidate_cogprs
  # array (an artifact). THIS is the canonical-side sole-writer that appends them
  # to the queue (the birth ledger) as NON-terminal birth-state rows — bench-
  # packet-prep picks them up for /review; promotion stays /review-gated. The
  # ingest is HARNESS-AGNOSTIC (same write whether codex or claude emitted them;
  # the harness is recorded as provenance, never as control — compute-admission-
  # law-topology-agnostic). Fail-soft: the mandate is ALREADY consumed here, so an
  # ingest hiccup must never un-consume verified governance work — it is additive.
  COGPR_INGEST="$SCRIPT_DIR/cogpr-ingest.py"
  if [ -f "$COGPR_INGEST" ] && [ -f "$STRUCTURED_REPORT" ]; then
    set +e
    INGEST_OUT=$(python3 "$COGPR_INGEST" --zone-root "$ZONE_ROOT" --report "$STRUCTURED_REPORT" 2>&1)
    INGEST_RC=$?
    set -e
    if [ "$INGEST_RC" -eq 0 ]; then
      echo "CogPR ingest: $INGEST_OUT"
    else
      echo "WARN: cogpr-ingest failed (non-fatal; mandate already consumed): $INGEST_OUT" >&2
    fi
  fi

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
  WB_EXTRA=$(WB_EC="$CLAUDE_EXIT" WB_BK="$MOGUL_RUNNER_BACKEND" python3 -c "import json,os;print(json.dumps({'error':os.environ['WB_BK']+' backend exited with code '+str(os.environ['WB_EC'])}))")
  set +e; write_current_mandate_status "failed" "$COMPLETED_AT" "$WB_EXTRA"; set -e

  echo "ERROR: $MOGUL_RUNNER_BACKEND backend exited with code $CLAUDE_EXIT" >&2
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
