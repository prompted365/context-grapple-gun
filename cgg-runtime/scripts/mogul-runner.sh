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
# Daily partition key on the ONE declared clock (UTC) — the shell expression of
# scripts/lib/partition_key.py. Writer #2 of THREE into mandates/history/<date>.jsonl
# (mandate-write.py:416 writes the mandate row; hooks/session-restore.sh:831 writes the
# mandate-compact row). $TODAY is consumed by FIVE append sites in this file
# (:324/:1026/:1096/:1159/:1181 pre-edit) — one derivation, five rows, one file.
# A partition key is a JOIN key: all three writers moved in the SAME motion, because a
# one-writer cure splits the lane during the 20:00-24:00 EDT window.
# Historical locally-named files are NEVER renamed; forward-only.
TODAY=$(date -u +%Y-%m-%d)
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

# Artifact-naming timestamp on the ONE declared clock (UTC) — the shared
# partition-key law, admitted /review 767 Q4 as row
# bk-daily-partition-key-shared-clock-primitive (clock RULED /review 745 Q2);
# the python expression of the same law is scripts/lib/partition_key.py.
# WAS: date +%Y-%m-%dT%H%M%S — the LOCAL clock, which named a 05:54:11Z run
# "T015411" (t750) while every lane artifact around it was UTC-dated. The
# transcript/report pair is named ONCE here and nowhere else (sole writer),
# and no consumer parses this prefix (slice-compile.py globs *-tic-N,
# rollup.py reads d["tic"] or the tic-N regex, falsifier-run.py sorts by
# mtime) — so the rename is forward-only and consumer-safe. Historical
# locally-named artifacts are NEVER renamed.
TIMESTAMP=$(date -u +%Y-%m-%dT%H%M%S)
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
   FLAG SHAPES ARE PER-SCRIPT, stated ONCE for every instrument named below (/review 815): this list spells out the full invocation of SOME of the instruments it names and names the others by bare path — the shape shown for one instrument is NEVER evidence of the shape of another, and no zone-root flag, subcommand or default carries across them. Before you call any instrument named below, read that script's ARGUMENT HANDLING in its own source and call it by what you read there. NEVER run a help flag to find out: a help flag is not a probe here — measured at /review 815, on four of the thirteen instruments this list then named a help flag was a FULL RUN, and on two of those four that run WROTE tic-keyed artifacts.
   - queue_refresh: scan audit-logs/cprs/queue.jsonl, report state. First run: python3 $CGG_SCRIPTS/arena-pressure-ingest.py --zone-root \$ZONE_ROOT --quiet to discover arena candidates before scanning. MATURITY PREDICATE (the AGENT-CONSUMER axis, ratified /review 743 Q2 on cpr_mogul_queue_refresh_d9e2a59ba0c6 — you are a consumer with no call site, so this contract text IS your cure): resolve every row at latest-per-id and compute its fence as review_tic when present, else birth_tic + maturity_window_tics (both shapes are lawful at their own mint site; NEVER back-stamp review_tic; treat a prose-string maturity_window_tics as UNRESOLVABLE and disclose it, A4-743). A row is docket-eligible iff status == 'extracted' AND fence <= CURRENT_TIC, and you assert clock-currency (CURRENT_TIC read from the tic ledger THIS run, never from a cached projection's meta.current_tic — the CLOCK-INPUT face) before labelling any row mature or parked. Report pending_count over that predicate, and disclose the count of rows resolved through EACH shape. DISAGREEMENT SET (the COINCIDENT-ARMS face of guard 19 on ledger.md#presence-observation-fallacy-guard, ratified /review 752 C2 on cpr_mogul_queue_refresh_04fdfd8962fe): beside the per-shape count report shapes_disagreed_on_rows — the SET of live extracted row ids whose review_tic != birth_tic + maturity_window_tics (write the literal string 'empty' when the set is empty; never omit the key) — because where the two shapes agree row-for-row the per-shape split is a PROVENANCE NOTE (which field was read), never evidence the second shape was exercised, and the report must say so in one sentence; state once that at MINT the two shapes disagreed on 48 of 265 rows born 126-467 and on none born after 467 (measured tic 752), so an empty set is read as a property of the post-467 mint site, not of the predicate. EVALUABLE COUNT (the EMPTY-SET-CAUSE face, guard 19's third face, ratified /review 762 Q1 on cpr_mogul_queue_refresh_df535e0b7d15): beside shapes_disagreed_on_rows report evaluable_comparisons — the count of live extracted rows on which BOTH shapes could actually evaluate (both review_tic and birth_tic + maturity_window_tics resolvable) — because the literal 'empty' has two disjoint causes: (A) compared on every evaluable row and agreed, or (B) inputs absent so the inequality never evaluated; the licensed post-467-mint-site reading holds ONLY under cause (A), and an empty set with evaluable_comparisons=0 must be reported as 'nothing was compared', never as agreement. PRECEDENCE-TWIN (guard 19's fourth face, ratified /review 771 round 1 Q1 - the ray beside the EMPTY-SET-CAUSE face on ledger.md#presence-observation-fallacy-guard): the split's zeros are typed by the SAME evaluable count - in this precedence-ordered resolver a per-shape count of ZERO reports NON-SELECTION, never non-availability, so when you publish the per-shape split, say WHICH cause produced any zero in it: reached-and-zero, or never-reached-because-a-higher-precedence-shape-resolved-the-row (evaluable_comparisons discriminates: a shape reporting 0 while evaluable_comparisons shows it resolvable on N of those rows is precedence shadow, not vestigiality - never retire or call vestigial a shape on a zero that never measured it).
   - signal_scan: AUTHORITATIVE COUNT IS PRE-COMPUTED. The runner has already read audit-logs/signals/active-manifest.jsonl (curated truth, post-prune) and counted ACTIVE RAYS per the shared is_active_ray predicate (lib/signal_active.py — structurally live, or carried/dimmed with heat above floor; the raw status enum is retired). Authoritative count: $AUTH_SIGNAL_COUNT. Authoritative signal_ids: $AUTH_SIGNAL_IDS. Your report MUST use these values verbatim — do NOT re-derive from daily files, do NOT count raw emissions. Daily files audit-logs/signals/*.jsonl are raw emissions, not authoritative state. Your results.signal_scan object MUST include: {\"active_count\": $AUTH_SIGNAL_COUNT, \"active_signal_ids\": $AUTH_SIGNAL_IDS, \"authoritative_source\": \"active-manifest.jsonl (pre-computed by mogul-runner.sh)\"}.
   - memory_mining: scan MEMORY.md chain for recurring patterns, write findings. MEASURE-VALIDITY CLAUSE (the AGENT-CONSUMER axis, ratified /review 747 Q3 on cpr_mogul_memory_mining_fefd6a73fa3b — you are a consumer with no call site, so this contract text IS the guard that pattern_miner.py carries in code under cgg-ledger#recurrence-measure-invalid-over-shared-generator-corpus): the memory root's feedback_*.md corpus is a SHARED-GENERATOR corpus (one lead, one authoring convention, one voice), so any lexical or thematic recurrence measured over it measures the authoring convention, not recurrence in the world. Declare the corpus's authorship status in results.memory_mining, report any recurrence pass over it as MEASURE-INVALID, WITHHOLD hit rates and cluster sizes as findings (a 63/96 top cluster is broad-term over-matching, not a signal — t744), and promote a recurrence to a candidate ONLY when an instrument independent of the corpus corroborates it in the same run (name the instrument and its artifact; t747 lived: the lane reported a recurrence without the disclosure once the hand-fired guard lapsed). The structural audit is unaffected (it measures the index's shape, not recurrence): invoke memory-md-audit.py — ADDRESS DECLARED (/review 777, cpr 672e1bb251ce: the addressing-axis ray on the closed-consumer-set obligation): this is the ONE instrument in this contract that does NOT live beside its path-qualified siblings in cgg-runtime/scripts/; it resolves at <zone_root>/audit-logs/governance/memory-md-audit.py (a lawful governance-side home — the divergence is declared HERE at the naming site rather than discovered by ENOENT; if a bare name ever misses, resolve by filesystem-wide search and DISCLOSE the divergence — never silently substitute a same-named neighbor, never report the cycle un-runnable on the first ENOENT) — as a BARE CALLER (no --tic) so tic_source resolves in-emitter to tic_ledger, and report tic_source (the t747 test, paid non-vacuously, now standing). READ-FIRST AT THIS SITE (/review 816, the eighth rider; the general re-read-not-re-execute order in the cache_refresh paragraph binds here too and is not restated): before you invoke the audit, read the artifact already present for this tic AND the path field the producer itself publishes on it — here tic_source — and match that published path against the bare-caller form this contract demands; a same-tic artifact whose identity field parses exactly still does not discharge this cycle when its published path is not the demanded one, and a re-invoke on that ground is value-empty and governance-NON-empty at the same time, lawful, and justified in writing by naming BOTH paths. Where a producer publishes no such field the present artifact licenses nothing: the discriminator is never an inference from mtime and never a guess. The order is held by conduct, so hold it — at t813 this cycle read the prior artifact first and wrote both paths down; at t816, same contract text and same instrument, it re-invoked first and read afterwards, and disclosed that as its own miss.
   - pattern_mining: run $CGG_SCRIPTS/pattern_miner.py, output to audit-logs/patterns/
   - harmony_invoke: run $CGG_SCRIPTS/harmony-invoke.sh (kernel-class autonomous_kernel.meaning.disposition; produces disposition packet to audit-logs/harmony/disposition-tic-N.json + appends invocations.jsonl audit trail). Read-only kernel; does not mutate governance state. WINDOW-vs-POINT (the THIRD ray on ledger.md#disagreement-as-evidence, ratified /review 752 C1 on cpr_mogul_harmony_invoke_6689bad2ad26): the packet carries a WINDOWED aggregate (voice.admission_gate_watch: fired / count / prior_refusal_tics over window_runs_including_current (key renamed from bare refusal_tics at /review 763 Q1 — the NAME-BOUNDARY ray: the list is PRIOR-ONLY while count is inclusive-of-current; packets before t763 carry the old bare key)) beside THIS tic's POINT event — read voice.fallback_reason and voice.fallback_families.current BEFORE validators_passed or admission_gate_watch.fired, and never let a fired watch stand as this tic's own event: report the window as a window (name its prior_refusal_tics and its denominator) and the point as a point (name its cause and family; validators_passed=false is VACUOUS when no output reached the validators, e.g. a CLI timeout). PRODUCER-LIVENESS (the ruled reader half of /review 756 Q1, ledger.md#two-phase-fail-soft-artifact-absence-is-typed-by-producer-liveness-not-shape): the disposition is written in TWO phases (engine, then the fail-soft voice amender); if the voice block is ABSENT, type the absence from the packet's own voice_step marker — run $CGG_SCRIPTS/harmony-voice-marker.py classify --disposition <path> — never from the packet's shape or a sibling-tic diff: amender_running is NOT a fault (re-read after it finishes), amender_failed is a typed failure, marker_absent_probe_liveness means probe the process table / exit status / invocations.jsonl row BEFORE typing anything. Record the absence_type you typed and what you typed it from. VACUITY-CARRIES-INTO-THE-AGGREGATE CLAUSE (t790 mint, /review 793 Q2, cpr_mogul_harmony_invoke_bd14f93c401d — the FIFTH ray on ledger.md#disagreement-as-evidence): the point-scoped vacuity typing above is carried INTO every window statistic derived from validators_passed — a two-phase fail-soft field whose falsy value is vacuous at the point (no output reached the validators) silently merges two disjoint causes when counted over a window, so any aggregate of validators_passed==false is published SPLIT BY CAUSE via fallback_reason (real validation failures vs vacuous infrastructure timeouts), never as the bare count (measured over [741..790] and replayed member-exact at adjudication: 8 false = 7 vacuous llm_timeout_120s at 749/765/769/783/786/788/790 + exactly 1 real at 760 validation_failed:multi_line — the naive 16 percent 'validation failure rate' is truly 2 percent real, an 8x overstatement pointing the cure at the validator when the condition is infrastructure; 760 is also the admission_gate_watch's only prior_refusal_tics member, so the instrument already discriminates at the point and only the aggregate loses it).
   - contagion_heartbeat: run $CGG_SCRIPTS/contagion-invoke.sh (kernel-class ContagionMatch v0, harmony_invoke's sibling seam; conformation-proximity match over learned coordinates — NOT LLM-backed, NOT coupled to the 27B; produces disposition packet to audit-logs/contagion/disposition-tic-N.json + refreshes current-pointer.json + appends invocations.jsonl). Read-only kernel; emits a NON-CITABLE shaping packet; does not mutate governance state. The office-worldview boot render consumes current-pointer.json (staleness-canaried) — this cycle is the producer half of that heartbeat (GO ratified /review 545). DISCRIMINATOR-BEFORE-MAGNITUDE CLAUSE (t789 mint, /review 792 Q1, cpr_mogul_contagion_heartbeat_64f84c2c53b1 — the RUN-LENGTH-DEGENERACY reading-order face on ledger#presence-observation-fallacy-guard): any consumer quoting the discrimination block's consecutive_identical_count reads the change-event discriminator FIRST (last_change_tic · never_changed_in_retained_history · the basis string) — with never-changed true the run-length is NUMERICALLY IDENTICAL to the retained-artifact population (244=244 at mint over tics 443..789; 246=246 re-verified live at adjudication, the +2 accretion demonstrating the degeneracy) and MUST be reported as a POPULATION CENSUS, never a stability streak (it accretes +1 per tic with zero information gain); an integer last_change_tic (harmony's 591) marks the genuine-streak case where the count IS a sub-population streak inside a varying series. The producer is exemplary — the duty is entirely the reader's; no producer change.
   - economy_heartbeat: run $CGG_SCRIPTS/economy-invoke.sh (the c-coin shadow economy, H-2.5 seed; runs ONE economy tic in gunslinger seed mode — the 128-agent nautilus swarm accrues trust -> aggregate g_t -> gates the mint (coin<->trust closed), the federal exchange is held/normalized at the tic boundary, EconomyBreachFlags stay first-class visible; deterministic/local, NOT LLM-backed; produces audit-logs/economy/economy-tic-N.json + refreshes current-pointer.json + appends invocations.jsonl). Read-only of governance state; writes ONLY to audit-logs/economy/; does not mutate signals/queue/mandate/conformations. Producer half of the economy heartbeat (Architect \"wire\" GO tic 568). Your results.economy_heartbeat object MUST include {\"tic\": N, \"mode\": \"gunslinger\", \"series_mode\": \"genesis|continue|replay\", \"g_t\": ..., \"mint_total\": ..., \"seed_stabilized\": bool, \"execution_attested\": bool, \"breach_flags\": [...], \"breach_dwell\": {...}} — execution_attested is the attest-on-execution bit (t684 cure): seed_stabilized alone reads breach-visibility as instability; a breach-showing tic with a completed run is attested TRUE. breach_dwell is the CENSUS (t732 cure, /review 732 consumer-contract ray on the t725 dwell-altitude lesson): copy the emitter's top-level breach_dwell object verbatim — g_t is the end-of-tic point-sample, NOT a mean, and on saturated tics the two invert (t729: g_t 0.734 'recovered' while dwell.fraction 0.932 saturated); a report demanding only the terminal sample can tell the tic's story backwards. FIELD QUALIFICATION (t733 cure, /review 733 sem-identity data-field ray; path REPINNED /review 737 per cpr_mogul_economy_heartbeat_5caab586f38c — the shallow path never resolved, value-identity through the top-level alias had masked the address rot): the demanded g_t key IS detail.economy_trace.CADENCE.swarm_final_aggregate_g_t — swarm aggregate TRUST at the last internal tick; it is NOT the artifact's inner economy_g_t (g_t_trajectory_samples — a different quantity ~10x smaller sharing the token). Any report/prose quoting this key names the qualified referent (swarm trust, terminal sample), never the bare colliding token as if it were the economy's own g_t. RESOLUTION-FAILURE CLAUSE (t740 cure, /review 740 substitution face on the same ray): if the demanded path does not resolve against the artifact, the report DECLARES resolution_failure for that key — it NEVER substitutes a same-named neighbor at another altitude (the top-level g_t alias included); the right number from the wrong place is the failure mode, not a fallback. TYPED-RUN PROPAGATION (t734 cure, /review 734 conductor-score-runtime-parity ray on the t731 replay-report lesson): series_mode copies the advance_guard's own run typing verbatim — genesis|continue|replay. The guard already refuses to clobber the three WRITE surfaces on replay; this key carries that same typing across the REPORT membrane, so a replay tic (deliberately non-authoritative economy values) is schema-distinguishable from canonical instead of presenting AS the tic's economy (t731 lived: replay g_t 0.756 vs canonical 0.451 under one tic label). A report whose series_mode is replay quotes economy values only WITH that qualifier. PHASE CLAUSE (t742 cure, /review 742 phase-half ray on the t725 dwell-altitude lesson, cpr_mogul_economy_heartbeat_a57aee1fda06 — FOURTH ray on ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude): the terminal point-sample is PERIODIC — it occupies two disjoint bands (LO ~0.45-0.55 / HI ~0.70-0.76) and alternates between them on a phase-locked slip clock (21/26 consecutive pairs 716-742; slips every ~6 tics, gaps in [5,7]) — so a consecutive-tic g_t delta reports the PHASE, not the economy. NEVER narrate a one-tic g_t movement as trust recovered / degraded / flat; a g_t delta is reportable ONLY against a multi-tic aggregate, or against a same-parity tic whose parity is READ OFF THE OBSERVED BAND SERIES — never computed from tic arithmetic (the mod-6 residue class was tested and falsified). The dwell census remains the within-tic story (t742 lived: dsample -0.0015 'flat' beside ddwell 0.885->0.075 in one tic). When quoting g_t, name its band and, for any comparison, the parity source; the clock ray cpr_mogul_economy_heartbeat_64367ac313d3 was ABSORBED at /review 745 as the CLOCK-EVIDENCE face on the phase ray (pointer re-dated /review 763 per the SELF-INVALIDATING-POINTER face — a disclosure naming a forum by id expires at that forum's ruling). OUT-OF-BAND CLAUSE (t763 cure, /review 763 Q3, cpr_mogul_economy_heartbeat_7a6c0df654dd — the SIXTH ray on ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude): the band pair is a classifier with a DECLARED THIRD OUTCOME — a g_t sample inside NEITHER band (t760 lived: 0.61437) is typed out_of_band with parity_source=unresolvable; it is NEVER rounded to the nearer band, in prose or in any observed_band_series render (the t763 report labeled 0.61437 \"LO\" — the exact silent absorption this clause forbids); an out-of-band sample makes any band-parity comparison against it unresolvable, and its cause (excursion / slip-transition / regime change) is not determinable from one point — record it typed, never narrate it. REPEAT-READING CLAUSE (t764 cure, /review 764 Q1, cpr_mogul_economy_heartbeat_83e2019a2029 — the SEVENTH ray on ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude, the BAND-CARDINALITY face): the two bands differ in KIND — HI (~0.70-0.76) is a low-cardinality ATTRACTOR set (measured t761 on the emitter's own corpus: 86 samples / 74 distinct / 6 values recurring exactly; e.g. 0.749012 at tics 617/653/749/761 with distinct provenance on all four), LO (~0.45-0.55) is INJECTIVE (75/75, zero exact repeats) — so before treating a repeated g_t value as evidence of staleness, replay, or a wedged producer, measure and STATE the value-cardinality of the region the sample falls in: an exact repeat inside the HI attractor set is the instrument working (never a staleness/replay finding on that evidence alone), while an exact repeat inside the injective LO region is the alarm worth escalating. The rule is two-sided; attractor-membership is never a blanket license to ignore repeats, and the per-region cardinality is stated whenever either call is made. WINDOW-INDEXED-RATE CLAUSE (t777 cure, /review 780 Q1, cpr_mogul_economy_heartbeat_379ba4c96c9d — the NINTH ray on ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude, the window duty on the declared third outcome): an out_of_band RATE is window-indexed, never a population constant — measured at mint 33/209 = 15.8 percent over the full corpus vs 3/62 = 4.8 percent over tics >= 716 (a 3.3x spread across NESTED windows of ONE population; the full-corpus figure is inflated by the extinct 568-570 regime), so whenever you state the third outcome's frequency, NAME THE WINDOW IN THE SAME SENTENCE, and report a rate that spans a known regime change per-regime or not at all — a bare rate silently re-bases how often a same-parity comparison is even available, and the same honest sentence can understate or overstate parity-availability by more than 3x depending on the reader's implicit window. WINDOW-AGES SENTENCE (t808 mint, /review 811 Q1, PROMOTE MODIFIED — a refinement ray on the NINTH clause; the mint's own midpoint-split probe was STRUCK as the instrument: it read 1.35x on the known 568-570 regime change, a failed positive control, and its member-spacing arm fired at the window's own mint): a window designated regime-local is a fact about the data when its boundary was drawn, and it AGES — so whenever you quote the regime-local rate, quote its TWO-HALF MEMBER SPLIT beside it (each half's event count over its size, WITH the event tics as members), never the pooled rate alone; do NOT re-cut the boundary at report altitude and do NOT declare the window aged from a factor threshold — no calibrated probe exists yet (one must fire on a KNOWN regime change and stay silent at the window's own mint before it is relied on); a re-draw is a /review motion. NAMED-CUT READ (/review 817, the tenth rider): that two-half member split NAMES its cut beside it — the cut is FIXED at the window's own designation tic and is STATED as a tic, never a function of the window's current extent, because a cut that moves as the window accretes tics (a midpoint moves) makes each half a new population at every report and can migrate a member with no new event arriving; a factor between the halves is a ratio of RATES and says so; and a reader comparing two reports checks FIRST that both name the same cut, because two splits on different cuts are two instruments. This stays a DISCLOSURE and adds nothing that re-draws: it sets no threshold, declares no window aged, and leaves the re-draw the /review motion it already is above. MOVING-DENOMINATOR CLAUSE (t783 cure, /review 786 Q1, cpr_mogul_economy_heartbeat_09776dea2ffc — the TENTH ray on ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude, the cross-INSTANT duty on the window duty): a window-indexed rate quoted for comparison ACROSS TICS publishes the NUMERATOR AND DENOMINATOR SEPARATELY, never the percentage alone — an open-ended window (fixed start, floating end) accretes denominator every tic while the numerator moves only when an event fires, so a rate that FALLS across tics is not evidence the phenomenon became rarer (measured t783 against the ninth ray's own mint literals: out_of_band 33/209 -> 33/215 and 3/62 -> 3/68 with ZERO events between — both denominators grew by exactly the 6 elapsed tics); a frozen numerator is reported visibly as zero-events-since, never laundered into a declining rate, and a denominator-only movement is a statement about elapsed time, not about the phenomenon (fixed-window last-N-tics rates are exempt — their denominator is constant by construction). DERIVED-STATISTIC CLAUSE (t788 cure, /review 788 Q1, cpr_mogul_economy_heartbeat_88e63895485b — the ELEVENTH ray on ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude, the window duty on every DERIVED statistic of the third outcome): the window-naming duty extends beyond the RATE to run-length, maximum, gap, and recurrence — any statistic derived over the out_of_band series — and an EXISTENCE or FIRST-EVER claim states its verdict under BOTH the regime-local window and the full corpus, because the two can disagree in KIND, not degree (a mis-windowed rate is a magnitude error; a mis-windowed run-length flips 'first ever', which reads as regime-change evidence the full corpus refutes — measured at adjudication: [784,785] is the FIRST consecutive out-of-band run post-716 AND merely the SEVENTH multi-tic run of the full corpus, six prior precedents: five length-2 at 578-579/639-640/663-664/706-707/711-712 plus one length-3 at 568-570; the t785 report itself counted the current run among its own precedents, the exact derived-statistic mis-statement this clause forbids). State every derived statistic of the third outcome with its window in the same sentence; a first-ever claim answers under both windows or not at all. ORDINAL-CARRIER face (t790, /review 790 Q1, cpr_mogul_economy_heartbeat_50e00cbb03b4 MERGE-ABSORBED into this clause — the no-numerator grammar): an ordinal/first-occurrence/streak-record claim carries NO numerator, so it slips the letter of the rate duties while re-basing inference exactly as a bare rate does — a \"first\" asserted over a sub-window is reported as first-in-window WITH the full-population ordinal beside it in the same sentence (lived t787: \"first adjacent pair\" post-716 = the SEVENTH multi-tic run of the full corpus; the probe fired BEFORE minting and no bare novelty language reached the report), never as a bare first. RESIDUAL-SUBSTRUCTURE CLAUSE (t789 cure, /review 789 Q1, cpr_mogul_economy_heartbeat_a96f6ac79157 — the TWELFTH ray on ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude, the population-structure axis on the declared third outcome): the third outcome is a RESIDUAL, not a class — when a report types a sample out_of_band it names the SUB-POPULATION beside the bare token (shoulder_low: within ~0.005 of the LO floor / gap: genuinely between the bands / shoulder_high: within ~0.014 of the HI ceiling / extinct_regime), and any statement of the residual's RATE discloses the sub-population split, because an edge-adjacency rate and an excursion rate answer different questions and only one of them is about the economy (measured on the strict per-tic corpus [568..786], 218 artifacts: out_of_band 35 = sub-LO 9 [0.445295,0.449622] + gap 19 [0.561095,0.696014] + supra 7 [four shoulder members at tics 601/607/715/572 + three extinct at 0.975218]; a shoulder member misses its band edge by as little as 0.0004 — an artifact of WHERE THE EDGES WERE DRAWN — yet forces the same parity_source=unresolvable as a genuine excursion, so ~a quarter of the residual makes parity unavailable for a reason about the classifier's own geometry). CENSUS-POPULATION DISCIPLINE (the mint's own recorded miss, self-evidencing): the residual census population is the strict per-tic series economy-tic-N.json — replay variants (economy-tic-N-replay.json) are EXCLUDED or counted under their own typed population, never silently merged (the t786 mint's 229/36 figures swept 11 -replay files; the phantom shoulder member was economy-tic-605-replay.json). NEVER move, widen, or re-fit the band edges to swallow shoulders — re-fitting destroys the evidence that shoulders are edge artifacts; the cure is disclosure at report, never re-fit at the classifier. EPISODE-vs-SAMPLE CLAUSE (t788 mint, /review 791 Q2, cpr_mogul_economy_heartbeat_d346a7e37fdb — the THIRTEENTH ray on ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude, the NUMERATOR-SEMANTICS duty on every rate of the third outcome): a clustered phenomenon's rate has TWO disjoint numerators — SAMPLES and EPISODES — and a bare sample-rate quoted as an occurrence-rate over-counts by exactly the clustering factor (measured on the strict per-tic corpus and re-derived EXACT at adjudication: out_of_band 35 samples / 27 contiguous episodes over tics 568-788, run-length histogram 20 singletons + 6 pairs + 1 triple, factors 1.30x full-corpus and 1.25x window>=716 where 5 samples occupy 4 episodes and [784,785] is ONE two-tic episode, never two excursions); when a phenomenon can persist across consecutive observations, STATE whether the numerator counts samples or episodes IN THE SAME SENTENCE as the rate, and note that the clustering factor is itself window-indexed (7 of 27 episodes multi-tic full-corpus vs 1 of 4 in-window) — the ninth/tenth rays govern the denominator and the window; this clause governs what the numerator COUNTS, and neither substitutes for the other. IN-BAND WINDOW-DUTY CLAUSE (t790 mint, /review 793 Q1, cpr_mogul_economy_heartbeat_fcd7212bfd55 — the FOURTEENTH ray on ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude, the LICENSING-STATISTIC face): the window-naming duty extends beyond the third outcome's statistics to the IN-BAND value-cardinality statistic whenever it licenses the attractor-vs-staleness verdict (the REPEAT-READING clause's own evidence base) — that statistic is window-sensitive in exactly the residual's way (measured t790, replayed member-exact at adjudication: the current sample's recurrence count is 7 over the full corpus [568..790] at tics 629/665/677/701/725/773/790 but 3 over the regime-local window [716..790] at 725/773/790, a 2.3x spread across nested windows of one population); NAME THE WINDOW IN THE SAME SENTENCE as the cardinality, and when the two windows disagree in KIND (attractor under one, injective under the other), answer the staleness/attractor call under BOTH windows or not at all — a KIND flip licenses 'instrument working' and 'escalate the alarm' from the same honest sentence, and the window choice must never silently pick between them. EVALUABILITY CLAUSE (t804 mint, /review 807 Q1, cpr_mogul_economy_heartbeat_5bc284aa1521 — an ABSORBED refinement tail on the clause above, its agreeing-case precondition; guard 19's EMPTY-SET-CAUSE face rehydrated on this lane): a nested-window comparison CANNOT disagree on a singleton — a value whose full-corpus recurrence is 1 is a singleton in every nested sub-window, so 'both windows agree in KIND' is then STRUCTURALLY GUARANTEED, never measured. Whenever you publish the in-band cardinality under both windows, publish beside windows_agree_in_kind whether the comparison was EVALUABLE (the current value's full-corpus recurrence is 2 or more) or GUARANTEED by nested containment, and never let a guaranteed agreement read as a measured cross-window check. AGREEMENT IS ARITHMETIC, ONLY A FLIP IS A MEASUREMENT (the first duty promoted at /review 812, routed to this contract at /review 817 as the eleventh rider): inside the EVALUABLE domain the two windows can agree only when agreement is FORCED — a value whose inner-window recurrence is already 2 or more forces the outer reading by nested containment exactly as a singleton does — so treat an agreement as ARITHMETIC and only a FLIP as a measurement, the sharp domain being the evaluable values whose inner recurrence is thin, and say so beside the two-window line you publish. Measured at mint and re-derived member-exact at adjudication on the strict per-tic HI band over tics 568-804: 85 of 91 distinct values are singletons on which the check is mute, 6 can exercise it, and 4 of those 6 flip KIND — the check is sharp on its small evaluable domain and vacuous elsewhere. The cure is a disclosed flag, never suppression of the two-window report. KIND THRESHOLD, DECLARED HERE (the second duty promoted at /review 812 — before that it was declared nowhere): a value is typed an ATTRACTOR within a window when its recurrence inside that window is 2 or more, and INJECTIVE otherwise; that threshold is what every KIND in this clause and in the window-duty clause above it means. No emitting code computes it — the two-window check lives only as this contract prose — and the nested-window subset relation is likewise unenforced, so state the threshold beside any KIND you publish, or your agreements and your flips alike rest on a reading the next reader may not share. SHOULDER-MARGIN CLAUSE (t794 mint, /review 797 Q2, cpr_mogul_economy_heartbeat_24d37bea1e3f — the FIFTEENTH ray on ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude, the MARGIN duty on the RESIDUAL-SUBSTRUCTURE clause's sub-population typing): a shoulder token (shoulder_low / shoulder_high) is MARGIN-BLIND — within the shoulder tolerance it types a member at +0.000173 and a member at +0.013092 identically, and the margin is the entire evidence for the edge-artifact claim the token makes (measured on the strict per-tic corpus [568..794], 226 artifacts, replayed member-exact at adjudication: shoulder_high margins above the 0.76 ceiling +0.000173 at t794, +0.001708 at t601, +0.010663 at t715, +0.010717 at t607, +0.013092 at t572 — a 75x spread; the HI band's highest in-band member is 0.759938 at t775, so the round-number ceiling sits 0.000062 above the population's empirical max and the classifier manufactures shoulders out of the in-band tail); whenever you type a sample into a shoulder sub-population, publish TWO numbers beside the token in the same sentence — the member's own margin past the declared edge (COMPUTE it yourself from the strict per-tic series economy-tic-N.json, replay variants excluded — no producer emits it; PUBLISH-AS band_classification.margin_above_HI_ceiling or band_classification.margin_below_LO_floor — an OUTPUT name you write at exactly that path, never an address you read) and that edge's distance to the in-band population's empirical extreme (COMPUTE it from the same series; PUBLISH-AS band_classification.HI_population_max_in_band or band_classification.LO_population_min_in_band — an OUTPUT name, never an address; DIRECTION-MARKING, /review 801: every dotted name in this clause is PUBLISH-AS, none is a READ address, so a name absent from the producer artifact is never a resolution_failure — the duty is computable and you compute it) — and in residual_census list each shoulder member as (tic, g_t, margin) beside the sub-population count, never the bare count alone; the reader compares, the report never pre-decides which shoulder is thin. The parent's prohibition is carried forward verbatim: NEVER re-fit, widen, or move the band edges to swallow a shoulder — the margin is DISCLOSED, never absorbed.
   - enrichment_scan: run $CGG_SCRIPTS/cpr-enrichment-scanner.py, assess enrichment-eligible CPRs
   - ladder_audit: audit CLAUDE.md chain coherence. ALSO run python3 $CGG_SCRIPTS/ladder-audit.py select-kis --zone-root $ZONE_ROOT --persist-unsourced (the flag belongs to the select-kis SUBCOMMAND and follows it) — the ADMISSION-AND-COVERAGE consumer RULED at /review 808, given its invoker at /review 810: ONE condition-stable rollup ray per owner while active_but_unsourced is non-empty, resolved on heal. The selection scan itself stays read-only; the rollup is the separate obliged-consumer write, and this contract line is the ONLY runtime path that reaches it — no code call site passes the flag (census /review 810, re-confirmed by the build seat at tic 811). Report results.ladder_audit.unsourced_rung_rollup as the emitted / deduplicated / resolved result the command returns; a deduplicated result means the ray already stands, NOT that the cycle failed. Does NOT satisfy: this does not make the rollup's first live row a series, and it does not audit the UNSOURCED rungs themselves.
   - runtime_drift_check: compare installed vs canonical runtime surfaces. ALSO run $CGG_SCRIPTS/check-harmony-readonly.py --json AND $CGG_SCRIPTS/check-contagion-readonly.py --json — each verifies its engine's modules contain no forbidden imports (atomic_append/queue/signals/manifest-prune/mandate/conformation) or write patterns (writeFileSync/appendFileSync/.write()). Surface any violations as drift findings (treat as TENSION/COGNITIVE per existing drift severity classification).
   - prompt_stack_audit: run $CGG_SCRIPTS/prompt-stack-audit.py, scan CLAUDE.md chain for conflicts
   - cache_refresh: run $CGG_SCRIPTS/visitor-economy-monitor.py --full-cycle \$TIC (NOT --cache-refresh: that flag's producer measures cache_state ONLY, and the two other demanded keys would be filled by your inference reading as measurement — the t687/t692 defect, bk-mandate-cache-refresh-contract-producer-split). The full-cycle output MEASURES every demanded key: build results.cache_refresh from it as {\"cache_state\": <full_cycle.cache_refresh.cache_state>, \"standing_decay\": <full_cycle.standing_decay>, \"biome_health\": <full_cycle.biome_health>} — all three measured, never derived — EVEN WHEN THE CACHE IS EMPTY (e.g. cache_state {\"summary\": {\"total_entries\": 0}}). The extra full-cycle keys (census, economy_observation) are benign byproducts; do not promote them into results.cache_refresh. Do NOT report cache_refresh only in the prose summary; the structured results.cache_refresh key is the verified artifact. DURABLE ARTIFACT (t714 cure, the a4c8 no-path ray): the producer persists its full output to audit-logs/visitor-economy/full-cycle-tic-\$TIC.json — if your read of the stdout is clipped, RE-READ that artifact; never re-execute the signal-emitting cycle to recover a measurement. Verify the artifact landed (results.artifact_path non-null) and cite it in results.cache_refresh as {\"artifact_path\": <full_cycle.artifact_path>}; a null artifact_path with artifact_write_error is a finding to surface, not to absorb. RENDERING-RERUN (generalized /review 771 round 1 Q2, the ray on ledger.md#terminal-state-change-requires-receipt-and-no-signal-goes-dark): this re-read-not-re-execute discipline is GENERAL to every tic-keyed artifact writer in every cycle, on a second justification - a second same-tic run of ANY tic-keyed artifact writer supersedes its first observation, and a re-run whose only purpose is a different output format mints a content-empty supersession receipt (real justification_class, zero governance information); before re-invoking ANY tic-keyed artifact writer, READ the artifact the prior invocation already wrote; re-invoke only when the MEASUREMENT is stale, never when only its RENDERING is inconvenient.
   - deep_audit: comprehensive multi-rung scan
   - review_close_check: run $CGG_SCRIPTS/review-close-check.py, verify post-review inscription consistency. THREE-CAUSE NONE CLAUSE (t788 cure, /review 788 Q2, cpr_mogul_review_close_check_36e8046380e9 — guard 19's NINTH face, the ad-hoc-prober face): a falsy value returned by an ad-hoc .get() probe over a typed governance row has THREE disjoint causes — present-and-null (a measured absence), absent-by-design (a lawful conditional emission), or THE PROBER NAMED THE WRONG KEY — and the third cause is a property of the MEASURER that no amount of additional row-reading can distinguish (more rows return the same undifferentiated None, and an agreeing window of nothings reads as a stable finding). Before typing ANY all-falsy probe window as a finding (a mounted-bear / inert-divergence-lane verdict included), read the emitting code's write condition for that key; a probe output line can mix real measurements and instrument artifacts with nothing marking which is which, so type each key by its producer, never by the window's internal agreement (t785 lived: five guessed keys printed five false Nones beside two true readings, and executor_clock_tic read None across 8 rows because the producer emits it only on divergence — the lane was healthy, the near-finding false). KEY-SETS FIRST (/review 816, the ninth rider): on ANY append-only log — heterogeneity is the norm and not the exception, and even a formally single-kind table reads many shapes — partition the rows by their KEY-SET and dump those sets before you open a producer that may have several write sites, then read the dump for exactly what it is: a key-set partition is NOT a row-kind partition (shapes and action kinds are two reads, never one), and the partition LOCATES the population that carries the key without settling which of the three causes above produced the falsy read on it. ARTIFACT-DISCOVERY CLAUSE (t795 home, /review 795 Q2 ABSORB reinforce_existing, cpr_mogul_review_close_check_b33a62b2aa6a — the cause-C1 instance at the filesystem-discovery prober class): an empty find/glob/mtime window for a producer's artifact has THREE disjoint causes — nothing written, not landed yet, or THE PROBER'S OWN PREDICATE NEVER REACHED THE ARTIFACT — and repeating the probe cannot distinguish the third (every repetition returns the same undifferentiated empty set). Before typing an artifact ABSENT, read the producer's OWN PUBLISHED INDEX — the review-close-check log row's report_path (audit-logs/services/review-close-check-log.jsonl) — never a guessed directory, name pattern, or mtime window; and NEVER re-invoke a tic-keyed artifact writer on a mis-typed absence (t792 lived: three agreeing empties, a redundant second same-tic invocation stopped mid-flight, the first run had completed exit 0 and written its artifact; a wrong-shaped grep over the same log returned 0 while the parsed count was 1). FALSE-PRESENCE CLAUSE (t808 home, /review 808 Q3 MODIFY-and-PROMOTE, cpr_mogul_review_close_check_95d4b020a396 — the FALSE-PRESENCE face of guard 19, the polarity the clause above did not cover): a NON-EMPTY window has the same third cause as an empty one — THE PROBERS OWN PREDICATE NEVER ADDRESSED THE ARTIFACT — but it presents as CONFIRMATION, which is exactly when a prober stops probing. Reading the published index is NOT enough: the cure is the MATCH PREDICATE. Type an artifact or a cycle PRESENT (already run, already written) only from a PARSED row of the published index whose identity FIELD equals the target (for this instrument: the top-level tic field of a review-close-check-log.jsonl row), never from a substring, a count or a glob hit over that same file, and STATE the field you matched on. A tic number also occurs inside mandate ids, timestamps and microsecond fragments of unrelated rows (t805 lived: a substring count of the tic over this log returned 11 while the parsed count of rows with that tic was 0; re-read at /review 808: 11 lines against 1 parsed row, ten of eleven false). The two errors are not symmetric: a false ABSENT licenses the forbidden re-invoke; a false PRESENT licenses a SKIP — the cycle never runs, no artifact is written, and this report would claim a cycle it did not execute, with nothing left on disk to contradict it. A false PRESENT is cured by RUNNING the cycle, which is lawful first-run behaviour, never by re-running a writer that already fired. OBLIGATION-MATCH SENTENCE (t808 mint, /review 811 Q2, PROMOTE MODIFIED — the SUPERSEDED-PRESENT typing, a refinement ray on guard 19): on an instrument that can lawfully fire more than once per tic, a parsed tic match is NECESSARY BUT NOT SUFFICIENT — before typing PRESENT, compare the parsed row's mandate_id with the mandate you are consuming AND its timestamp with the event this cycle exists to verify (for review_close_check: the /review inscription commit); if EITHER diverges, type the row SUPERSEDED-PRESENT — an honest measurement of a prior surface — and RUN the cycle. BOTH arms are bound: mandate_id is caller-supplied identity and carried no operand on any same-mandate multi-fire tic before 739, so the timestamp arm may NEVER be dropped; a matching mandate_id with an unchanged measured surface remains a SKIP. PINNED-SHA OPERAND, a second operand for arm 2 (an independent rediscovery of arm 2 recorded as confirmation, /review 813): where a row pins the sha of the input it read, that pinned sha against the same input's sha after the event is an ordering test that needs no clock. It is CORROBORATION for arm 2, never a replacement for it, and it licenses dropping neither arm. UNREACHED-BRANCH DUTY (the mute-branch locus of this face, /review 814): on a run where NO parsed tic-match row exists, both arms above are structurally UNREACHED, not satisfied. Publish beside the obligation-match result whether the arms were REACHED (naming both compared values) or UNREACHED with its cause, and never let an unreached arm read as verified — a refinement that did not run is reported UNREACHED with its cause, never as coverage this run did not have. READ-ORDER CLAUSE (t806 home, /review 806 Q1, an ABSORBED refinement tail on the clause above — its ordering precondition): the published index answers only WHAT WAS WRITTEN, never whether writing is still happening. This producer writes its log row at COMPLETION, so for its whole run the index returns the SAME empty as a run that never started. LIVENESS FIRST, INDEX SECOND: before reading the index to type an absence, read the process table by argv at the executable position (or the task exit status); a live producer makes the index read premature by construction, and no amount of re-reading resolves it. SIZE THE CALL TO THE INSTRUMENT: review-close-check.py runs for MINUTES from its pinned queue read to its artifact, and EVERY fire of it on record has EXCEEDED the 120 second default foreground ceiling — so a default-ceiling foreground call ALWAYS returns with no terminal status, and the three-empty window (no exit status, no stdout summary, no index row) is this instrument's ORDINARY case. READ THE CURRENT WALL-CLOCK FROM THE RECORD, never from this contract: this instrument's own recent cycle reports carry the measured figure in their wall-clock field. An inscribed range here has already rotted TWICE — once when its fire count aged, and again when a later fire ran past its upper bound, which is why /review 813 routed the literal out of this sentence. A wall-clock literal in a contract is a maintenance debt; the ceiling conclusion above is what binds. Invoke it with the foreground ceiling raised (timeout 600000 ms), or launch it in one call and block on its process exit in a separate call. A severed return is the observer's ceiling until the process table says otherwise; a dead producer with an empty index is a real absence and the no-re-invoke duty still binds until the cause is typed. PRESERVATION IS THE PRODUCER'S, NOT YOURS (/review 815): before you copy a check file aside to save it from a second same-tic fire, read this producer's replacement branch — it already preserves the prior itself. On the replace branch, and only when the prior bytes are readable, it writes those raw bytes into the superseded subdirectory of its own report directory, audit-logs/mogul/cycle-reports/review-close-checks/superseded/, named tic-N-check.superseded-SEQ.json at the first free sequence number and never itself overwritten; it writes a back-pointer sidecar beside it, tic-N-check.superseded-SEQ.json.superseded-by.json, whose superseded_by_live_path key names the replacing artifact; and it stamps the same receipt into the live report as superseded_receipt.preserved_path. Its order is preserve, then back-pointer, then overwrite, then announce on standard error — so the announcement you would read arrives AFTER any hand-copy you already made. A hand-copy outside that directory under a name of your own invention is a preservation no enumerator of the producer's pattern can find. The skip branch preserves nothing and needs nothing: read the branch, never the announcement.
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
# Standing fence (comment RE-TAUGHT at t765, F-765-W4R1 — the prose below had
# kept teaching the pre-Q8 codex-only world): civil_status_check is CARVED OUT
# for EVERY backend (/review 750 Q8, landed 2e14067) — the runner dispatches it
# on its own `claude -p --agent civil-engineer` lane and merges
# results.civil_status_check into the main report. It NEVER routes to an
# external compute backend, and the MAIN agent never dispatches it (its prompt
# says so at the civil_status_check clause). (Per Architect tic 438: per-lane
# selector; civil stays on Claude Code.)
#
# Agent grant history (tic 404, civil-cadence wiring tranche): the claude lane
# was granted the Agent tool FOR the old spawn-civil route. That route is now
# FORBIDDEN (/review 750 Q8 — civil is the runner's own carve-out; the main
# agent's prompt says "NOT YOURS TO DISPATCH"). The grant itself is retained
# UNMEASURED pending F-765-W4R2/R3 (/review candidate: does any live cycle need
# Agent? cure the affordance and the sibling seat's grant together or neither).
# Do NOT read this comment as authority for --allowedTools including Agent
# "for civil_status_check" — that teaching was stale and is retired.

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
  # nesting by default; headless -p is safe). Agent REMOVED from --allowedTools
  # (F-765-W4R2/R3 cure, /review 766 signed: zero live cycles need it — civil
  # runs out-of-band via the runner's own carve-out; the seat prompt forbids
  # subagent spawning under print mode).
  env -u CLAUDECODE "$CLAUDE_BIN" -p "$MOGUL_PROMPT" \
    --model "$MOGUL_RUNNER_MODEL" \
    --allowedTools "Read,Grep,Glob,Bash,Write" \
    --dangerously-skip-permissions \
    --output-format json \
    > "$TRANSCRIPT_FILE" 2>&1
  CLAUDE_EXIT=$?
fi
set -e

# ---- Civil carve-out merge (EVERY backend + civil requested — /review 750 Q8) ---
# The MAIN agent (any backend) ran every cycle EXCEPT civil. Dispatch civil-engineer on Claude
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
    --allowedTools "Read,Grep,Glob,Bash,Write" \
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
        # OM-2 (/review 767 round 3, signed): this VERIFIER reads the patterns daily
        # file whose WRITER (pattern_miner.py:417-419) already names it by the UTC
        # date. A reader follows its WRITER's clock — on the local clock this probed
        # a file the miner never wrote during the 20:00-24:00 EDT window. ALIGNS the
        # pair (writer already UTC); it does not split a lane.
        TODAY_PATTERNS="$AUDIT_LOGS/patterns/$(date -u +%Y-%m-%d).jsonl"
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
