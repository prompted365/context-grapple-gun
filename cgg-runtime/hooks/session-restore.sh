#!/usr/bin/env bash
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

# Capture stdin payload. Claude Code 2.1.69+ ships agent_id/agent_type when
# SessionStart fires for a subagent context (Agent tool spawn). Empty when the
# harness fires for the primary orchestrator. Captured into mandate-history
# writes below for cross-agent provenance (federation KI: bounded-delegation
# default masking).
INPUT=$(cat)
AGENT_ID=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('agent_id') or '')
except Exception:
    print('')
" 2>/dev/null)
AGENT_TYPE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('agent_type') or '')
except Exception:
    print('')
" 2>/dev/null)

# Wire cutter — emergency kill switch
[ -f ~/.claude/wire-cutter.sh ] && source ~/.claude/wire-cutter.sh && wire_check session

# ============================================================================
# Phase 1: Root Anchoring
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
# Effective-record hydration gate (third-surface correction reconciler).
#
# A pair of agreeing projections is not current truth when an append-only
# correction landed on a third surface. Resolve corrections BEFORE any civic
# worldview is hydrated. An unresolved chain suppresses worldview rendering
# and leaves a loud hook badge. A resolved correction also suppresses the raw
# worldview compiler until that consumer can accept the row-scoped effective
# projection; projection-aware consumers such as RTCH use the effective view.
# Resolver absence is a capability blocker: the hook emits only that blocker
# and stops before every downstream governance reader.
# ============================================================================

EFFECTIVE_RECORD_SCRIPT="$CGG_SCRIPTS_DIR/effective-record.py"
[ -f "$EFFECTIVE_RECORD_SCRIPT" ] || EFFECTIVE_RECORD_SCRIPT="$HOME/.claude/cgg-runtime/scripts/effective-record.py"
EFFECTIVE_RECORD_MSG=""
EFFECTIVE_RECORD_HYDRATION_BLOCKED=0
EFFECTIVE_RECORD_CAPABILITY_BLOCKED=0
if [ -f "$EFFECTIVE_RECORD_SCRIPT" ]; then
  if command -v python3 >/dev/null 2>&1; then
    # --emit-view: the gate's ONE index build also serves the projection-aware
    # worldview render below (b3) — the renderer reuses this boot's view instead
    # of rebuilding (a full build reads every JSONL surface). Best-effort file;
    # the renderer falls back to the stored index if it is absent/unreadable.
    EFFECTIVE_VIEW_FILE="${TMPDIR:-/tmp}/cgg-effective-view-$$.json"
    EFFECTIVE_RECORD_MSG=$(python3 "$EFFECTIVE_RECORD_SCRIPT" --zone-root "$ZONE_ROOT" \
      hydration-gate --format hook --emit-view "$EFFECTIVE_VIEW_FILE" 2>/dev/null)
    EFFECTIVE_RECORD_RC=$?
    if [ "$EFFECTIVE_RECORD_RC" -eq 0 ]; then
      # The safe path is intentionally silent; SessionStart badges stay
      # signal-bearing instead of announcing the absence of corrections.
      EFFECTIVE_RECORD_MSG=""
    elif [ "$EFFECTIVE_RECORD_RC" -eq 2 ]; then
      EFFECTIVE_RECORD_HYDRATION_BLOCKED=1
    elif [ "$EFFECTIVE_RECORD_RC" -eq 3 ]; then
      # Corrections are resolved AND office-worldview.py is PROJECTION-AWARE
      # (b3, tic 683 — bk-worldview-projection-aware-b3): the renderer builds
      # the same effective view the resolver serves and consumes JSONL rows
      # through it (corrected rows overridden by effective_record, blocked rows
      # dropped row-scoped, the projection declared as a leading SUBSTRATE
      # fragment; a failed in-render projection build withholds JSONL-sourced
      # rays rather than reading raw). rc=3 is therefore no longer a
      # render-suppression state — the badge stays (loud, leads the context),
      # the render proceeds. rc=2 (genuine-unresolved) and resolver-crash
      # remain blocking; the capability blocker still stops the boot.
      EFFECTIVE_RECORD_HYDRATION_BLOCKED=0
    else
      EFFECTIVE_RECORD_MSG="[EFFECTIVE RECORD WARNING: resolver execution failed; no correction-derived claim is admitted by this hook]"
      EFFECTIVE_RECORD_HYDRATION_BLOCKED=1
    fi
  else
    EFFECTIVE_RECORD_MSG="[EFFECTIVE RECORD HOLD: python3 unavailable; SessionStart governance readers suppressed]"
    EFFECTIVE_RECORD_HYDRATION_BLOCKED=1
    EFFECTIVE_RECORD_CAPABILITY_BLOCKED=1
  fi
else
  EFFECTIVE_RECORD_MSG="[EFFECTIVE RECORD HOLD: resolver unavailable; SessionStart governance readers suppressed]"
  EFFECTIVE_RECORD_HYDRATION_BLOCKED=1
  EFFECTIVE_RECORD_CAPABILITY_BLOCKED=1
fi

# Stop-scope is DERIVED from the consumer set of the held truth (b2, tic 680;
# doctrine vehicle cpr_fail_closed_boot_hold_must_scope_stop_to_held_truth_
# consumers_tic679). A TRUTH hold (rc=2 genuine-unresolved, resolver crash)
# suppresses only the projection-dependent consumer — the raw worldview
# render, gated below on EFFECTIVE_RECORD_HYDRATION_BLOCKED — while the
# truth-independent mechanical lanes (handoff discovery, cpr-extract,
# enrichment scanner, mandate-fabric emission) RUN; the loud badge leads the
# injected context via CGG_MSG. Three consecutive dark boots (t677/t678/t679)
# were this early-exit answering a question those lanes never asked. Only a
# CAPABILITY blocker (resolver or python3 absent — the gate itself cannot run,
# so running ungated readers would be gate-bypass, not scoping) still stops
# the boot here fail-closed. rc=3 (corrected) no longer holds anything: the
# renderer is projection-aware (b3, tic 683) and consumes the row-scoped
# effective views itself — the badge stays, the render proceeds. (rc=3 is
# PERMANENT once any resolved correction differs from base — corrections are
# append-only — which is exactly why suppression-on-rc=3 was a blackout with
# no exit condition, and why the exit had to be renderer-side awareness.)
if [ "$EFFECTIVE_RECORD_CAPABILITY_BLOCKED" -eq 1 ]; then
  if command -v python3 >/dev/null 2>&1; then
    EFFECTIVE_RECORD_MSG="$EFFECTIVE_RECORD_MSG" python3 -c '
import json, os
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": os.environ["EFFECTIVE_RECORD_MSG"],
        "reloadSkills": True,
    }
}))
'
  else
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s","reloadSkills":true}}\n' "$EFFECTIVE_RECORD_MSG"
  fi
  exit 0
fi

# ============================================================================
# Handoff-seal reconcile + interstitial activation (tic 633 plan-lifecycle
# split; tic 634 recovery-seam repair — both Architect-directed). SessionStart
# delegates to cadence-handoff-seal.py --reconcile-at-start (ONE owner of the
# seal lifecycle): it consumes the sealed handoff EXACTLY ONCE (guard:
# consumed_at null), RECOVERS a matching staged seal when PostToolUse was
# skipped (approval/background adoption) — promoted only with matching
# emission_id + entry_tic AND plan-file approval evidence, never on an
# arbitrary SessionStart — flips the interstitial marker to active ONLY when
# that matching boundary's seal is consumed (a generic resume/background
# SessionStart never clears it; the statusline arrow renders from this STATE),
# and arms the pause-after-boot gate when activation.mode == pause_after_boot
# (cgg-gate.sh honors it: hydrate-only, no mandate/assessor/workflow dispatch,
# until a real explicit `continue` opens the gate). Fail-soft: never blocks boot.
# ============================================================================

SEAL_HOOK_SCRIPT=""
for _seal_candidate in \
  "$(cd "$(dirname "$0")" && pwd)/cadence-handoff-seal.py" \
  "$CGG_PLUGIN_ROOT/cgg-runtime/hooks/cadence-handoff-seal.py"; do
  [ -f "$_seal_candidate" ] && SEAL_HOOK_SCRIPT="$_seal_candidate" && break
done
SEAL_RECONCILE_MSG=""
if [ -n "$SEAL_HOOK_SCRIPT" ]; then
  SEAL_RECONCILE_MSG=$(python3 "$SEAL_HOOK_SCRIPT" --reconcile-at-start \
    --zone-root "$ZONE_ROOT" --agent-id "$AGENT_ID" 2>/dev/null || true)
fi

# ============================================================================
# Boot actor derivation (tic-799 born -> /review 802 Q5 -> /review 803 round 2
# Ruling B, "refuse one, declare three"). Derived ONCE, here, and read by the
# act-1 guard below.
#
# ONE RULE, TWO CALL SITES. The rule is NOT re-implemented here: it is the
# seal reconciler's own `derive_actor`, imported from cadence-handoff-seal.py
# (READ-only; that file is untouched by this increment). Call site A is
# cadence-handoff-seal.py `handle_reconcile_at_start` -> `derive_actor(agent_id)`;
# call site B is this block. A second bash-side re-derivation would be a SECOND
# RULE the moment either copy drifted -- the exact spec-runtime divergence the
# federation names as drift-by-accident.
#
# Three boot kinds reach THIS seam (SessionStart):
#   primary           -- empty payload agent_id AND no obligation environment
#   subagent          -- non-empty payload agent_id
#   headless_citizen  -- empty agent_id + the runner's CGG_OBLIGATION_MANDATE_ID
# A mogul-runner `claude -p` child is a TOP-LEVEL session: it boots through
# SessionStart -- the PRIMARY's seam, not SubagentStart -- so "this is
# SessionStart" never meant "this is the primary".
#
# FAIL-OPEN TO PRIMARY, deliberately. If the rule cannot be reached (seal hook
# absent, import failure, python3 missing) the actor degrades to primary, which
# is EXACTLY the pre-cure behaviour. A refusal is a RESTRICTION, and the only
# safe failure direction for a restriction on this seam is open: the primary
# must never be lockable out of its own mandate lane by a derivation fault.
# Every non-"false" value of BOOT_ACTOR_IS_PRIMARY is therefore treated as the
# primary by the guard below.
# ============================================================================

BOOT_ACTOR="orchestrator_session_start"
BOOT_ACTOR_CLASS="primary"
BOOT_ACTOR_IS_PRIMARY="true"
BOOT_ACTOR_OBLIGATION_ID=""
BOOT_ACTOR_OBLIGATION_TIC=""
if [ -n "$SEAL_HOOK_SCRIPT" ]; then
  BOOT_ACTOR_FIELDS=$(CGG_SEAL_RULE="$SEAL_HOOK_SCRIPT" CGG_PAYLOAD_AGENT_ID="$AGENT_ID" python3 -c '
import importlib.util, os
spec = importlib.util.spec_from_file_location("cgg_seal_rule", os.environ["CGG_SEAL_RULE"])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
a = mod.derive_actor(os.environ.get("CGG_PAYLOAD_AGENT_ID", ""))
print(str(a["actor"]).replace("\n", " "))
print(str(a["actor_class"]).replace("\n", " "))
print("true" if a["is_primary"] else "false")
print(str(a.get("obligation_mandate_id") or "").replace("\n", " "))
print(str(a.get("obligation_tic") or "").replace("\n", " "))
' 2>/dev/null || true)
  if [ -n "$BOOT_ACTOR_FIELDS" ]; then
    BOOT_ACTOR=$(printf '%s\n' "$BOOT_ACTOR_FIELDS" | sed -n '1p')
    BOOT_ACTOR_CLASS=$(printf '%s\n' "$BOOT_ACTOR_FIELDS" | sed -n '2p')
    BOOT_ACTOR_IS_PRIMARY=$(printf '%s\n' "$BOOT_ACTOR_FIELDS" | sed -n '3p')
    BOOT_ACTOR_OBLIGATION_ID=$(printf '%s\n' "$BOOT_ACTOR_FIELDS" | sed -n '4p')
    BOOT_ACTOR_OBLIGATION_TIC=$(printf '%s\n' "$BOOT_ACTOR_FIELDS" | sed -n '5p')
  fi
fi

# ============================================================================
# Plan discovery + trigger extraction
# ============================================================================

PROCESSED_IDS="$HOME/.claude/cgg-processed-handoff-ids.txt"
# THE MARKER IS CREATED-IF-MISSING WITHOUT BUMPING ITS MTIME (ruled /review 805
# round 3, Architect-ratified, recommended option verbatim "Rule the cure for 806
# entry; slip the drill one boundary"). A `touch` here advanced the marker to NOW
# at every boot, while the plan-discovery gate below reads
# `find ... -newer "$PROCESSED_IDS"` -- so nothing that already existed could be
# newer than a file touched a moment earlier, in EITHER plan directory, and every
# handoff-consuming locus went dark without one error. The mtime now advances only
# when an id is RECORDED (cgg-gate.sh's append is the marker's only content
# writer). The id check further down is and remains the real dedup; `-newer` stays
# an optimization that no longer defeats itself. Creation is KEPT so the reference
# file always EXISTS at that gate -- `find -newer <missing>` errors and matches
# nothing, and the stderr that would say so is discarded there. The two sites are
# NAMED here, never numbered: this comment's own arrival moved every line below it.
# DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT flip the payload switch, does NOT establish how long the loci have been dark or when the touch was introduced, does NOT change what a processed id means, and does NOT serve the successor session (manifest row B13).
[ -e "$PROCESSED_IDS" ] || : > "$PROCESSED_IDS"
FLAG_DIR="${TMPDIR:-/tmp}/claude_cgg/$PROJECT_KEY"
CGG_MSG="$EFFECTIVE_RECORD_MSG"
HANDOFF_ID=""
LATEST_PLAN=""

# ============================================================================
# ONE RULE, THREE CALL SITES (ruled /review 804 round 3, Architect-ratified,
# recommended option verbatim "Cure at 805, BEFORE the first pointer boundary").
#
# The plan-discovery DIRECTORY SET is NOT re-derived here: it is the seal
# reconciler's own `candidate_plan_dirs()`, imported from cadence-handoff-seal.py
# (READ-only; that file is untouched by this increment). Call site A is
# cadence-handoff-seal.py `find_boundary_plan_file` -> `candidate_plan_dirs()`;
# call site B is this block; call site C is cgg-gate.sh's Branch-B plan
# resolution. A second bash-side derivation -- hardcoding the two directories
# here -- would be a SECOND RULE the moment either copy drifted, which is exactly
# how this seam broke: the seal globbed ~/.claude/plans/ all along while this
# hook read only ~/.claude/projects/<key>/, so every handoff-consuming locus
# below went dark without one error.
#
# THE ZONE ROOT IS BOUND EXPLICITLY before the rule is called. The module binds
# itself at import to whatever zone it can resolve from its OWN file location,
# and candidate_plan_dirs() derives the project key FROM that binding -- so an
# unbound call would answer for the wrong zone.
#
# FAIL-OPEN TO THE PRE-CURE DIRECTORY, deliberately. If the rule cannot be
# reached (seal hook absent, import failure, python3 missing) the set degrades to
# $HOME/.claude/projects/$PROJECT_KEY -- EXACTLY the pre-cure behaviour. That
# fallback is not a second derivation of the rule; it is the ABSENCE of the rule,
# named as such, and it never silently invents the second directory.
#
# DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT flip the payload switch, does NOT establish how long the loci have been dark, does NOT change the seal journal's vocabulary, and does NOT serve the successor session (manifest row B13), which has no call site and is served only by the pointer payload's own text.
# ============================================================================

PLAN_DIRS=()
if [ -n "$SEAL_HOOK_SCRIPT" ]; then
  while IFS= read -r _plan_dir; do
    [ -n "$_plan_dir" ] && PLAN_DIRS+=("$_plan_dir")
  done < <(CGG_SEAL_RULE="$SEAL_HOOK_SCRIPT" CGG_ZONE_ROOT="$ZONE_ROOT" python3 -c '
import importlib.util, os
from pathlib import Path
spec = importlib.util.spec_from_file_location("cgg_seal_rule", os.environ["CGG_SEAL_RULE"])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.bind_zone(Path(os.environ["CGG_ZONE_ROOT"]))
for d in mod.candidate_plan_dirs():
    print(d)
' 2>/dev/null || true)
fi
if [ ${#PLAN_DIRS[@]} -eq 0 ]; then
  PLAN_DIR="$HOME/.claude/projects/$PROJECT_KEY"
  [ -d "$PLAN_DIR" ] && PLAN_DIRS=("$PLAN_DIR")
fi

if [ ${#PLAN_DIRS[@]} -gt 0 ]; then
  for PLAN_FILE in $(find "${PLAN_DIRS[@]}" -maxdepth 2 -name "*.md" -newer "$PROCESSED_IDS" 2>/dev/null | sort -r | head -10); do
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
# THE BODY-CONSUMING PATH, UNDER THE ONE SWITCH (manifest rows B3..B6, the
# re-points Deliverable 2 EXCLUDED; they land in THIS change, under the SAME
# switch -- cgg-runtime/config/handoff-payload-mode.json, `body` today).
#
# Four readers below consume the handoff BODY, not a marker: the inline-CogPR
# awk scan (B3), the cpr-extract --plan-file delegation (B4), and the two
# section-bounded awk ranges that build the boot briefing (B5 `## Next Actions`,
# B6 `### Not Started`). Under `pointer` mode $LATEST_PLAN is an ENVELOPE, not
# the plan, and all four would read a body that never had their content -- an
# empty extraction that reads as a LAWFUL ZERO and a strictly thinner briefing
# emitted with no error. They therefore read HANDOFF_BODY_PATH, resolved here.
#
# The mode rule and the pointer/durable-home rule are NOT re-derived either:
# resolve_payload_mode(), parse_pointer_block() and resolve_durable_home() are
# the seal's own, imported the same READ-only way.
#
# UNDER `body` (today) HANDOFF_BODY_PATH IS $LATEST_PLAN -- the executed path and
# every emitted byte are unchanged, which is the property the drill's byte-clean
# comparison measures.
#
# A DANGLING durable home is REFUSED fail-closed and LOUD, mirroring the seal's
# own pointer discipline: the body-consumers are left unfed rather than fed the
# envelope, because a silent thinner briefing is the exact failure this re-point
# exists to prevent.
#
# DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT flip the payload switch, does NOT establish how long the loci have been dark, does NOT change the seal journal's vocabulary, and does NOT serve the successor session (manifest row B13), which has no call site and is served only by the pointer payload's own text.
# ============================================================================

HANDOFF_BODY_PATH="$LATEST_PLAN"
HANDOFF_POINTER_MSG=""
if [ -n "$LATEST_PLAN" ] && [ -n "$SEAL_HOOK_SCRIPT" ]; then
  HANDOFF_BODY_FIELDS=$(CGG_SEAL_RULE="$SEAL_HOOK_SCRIPT" CGG_ZONE_ROOT="$ZONE_ROOT" \
    CGG_PLAN_FILE="$LATEST_PLAN" python3 -c '
import importlib.util, os
from pathlib import Path
spec = importlib.util.spec_from_file_location("cgg_seal_rule", os.environ["CGG_SEAL_RULE"])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.bind_zone(Path(os.environ["CGG_ZONE_ROOT"]))
mode, _reason = mod.resolve_payload_mode()
plan = Path(os.environ["CGG_PLAN_FILE"])
if mode != mod.PAYLOAD_MODE_POINTER:
    print("body")
    print(str(plan))
else:
    try:
        text = plan.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    block = mod.parse_pointer_block(text)
    home, why = mod.resolve_durable_home(block.get("durable_home"))
    if home is None:
        print("pointer_unresolved")
        print(why)
    else:
        print("pointer")
        print(str(home))
' 2>/dev/null || true)
  HANDOFF_BODY_KIND=$(printf '%s\n' "$HANDOFF_BODY_FIELDS" | sed -n '1p')
  HANDOFF_BODY_VALUE=$(printf '%s\n' "$HANDOFF_BODY_FIELDS" | sed -n '2p')
  case "$HANDOFF_BODY_KIND" in
    pointer)
      [ -n "$HANDOFF_BODY_VALUE" ] && HANDOFF_BODY_PATH="$HANDOFF_BODY_VALUE"
      ;;
    pointer_unresolved)
      HANDOFF_BODY_PATH=""
      HANDOFF_POINTER_MSG="[CGG HANDOFF POINTER UNRESOLVED: payload mode is pointer but the durable home named by $LATEST_PLAN did not resolve ($HANDOFF_BODY_VALUE). The body-consuming readers are HELD rather than fed the envelope. Do NOT proceed from the pointer summary; open the durable home or report a broken handoff pointer.]"
      ;;
  esac
fi

# ============================================================================
# CogPR counting: inline blocks + queue.jsonl
# ============================================================================

# Block-aware CogPR id emitter for inline <!-- --agnostic-candidate --> blocks.
# Emits the id of each pending/enrichment_eligible (non-example) block, one per
# line. Tolerates quoted and unquoted status values — authoring variance is real
# and a silent undercount blinds the gate that triggers cpr-extract.py.
# Emitting ids (rather than a raw count) lets the caller reconcile each inline
# marker against queue.jsonl terminal-per-id: an inline block whose id is already
# terminal in the queue (promoted/absorbed/...) is a STALE marker, not a live
# pending CogPR, and must not inflate the boot banner's pending count.
emit_pending_cpr_ids() {
  awk '
    function field_val(s, key,   v) {
      v = s
      sub("^[[:space:]]*" key ":[[:space:]]*", "", v)
      gsub(/["'\''[:space:]]/, "", v)
      return v
    }
    /<!-- --agnostic-candidate/ { in_block=1; pending=0; example=0; id="" }
    in_block && /^[[:space:]]*id:[[:space:]]/ { id = field_val($0, "id") }
    in_block && /^[[:space:]]*status:/ {
      sv = field_val($0, "status")
      if (sv == "pending" || sv == "enrichment_eligible") pending=1
      if (sv == "example") example=1
    }
    in_block && /-->/ { if (pending && !example && id != "") print id; in_block=0 }
  ' "$1"
}

# Collect inline CogPR ids (not a raw count) so they can be reconciled against
# queue.jsonl terminal-per-id below. A temp file keeps the find-loop subshell
# from swallowing the accumulation.
INLINE_CPR_IDS_FILE=$(mktemp 2>/dev/null || echo "${TMPDIR:-/tmp}/cgg-inline-cpr-ids.$$")
: > "$INLINE_CPR_IDS_FILE"
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
    emit_pending_cpr_ids "$f" >> "$INLINE_CPR_IDS_FILE"
  done < <(find "$PROJECT_DIR" \( -name "CLAUDE.md" -o -name "MEMORY.md" \) "${FIND_EXCLUDES[@]}" 2>/dev/null)
fi

# Auto-memory DECOUPLED (tic 570 — memory is not governance): the inline
# count no longer scans ~/.claude auto-memory. Counting memory-side blocks
# here would inflate TOTAL_CPRS and fire the cpr-extract gate for blocks the
# extractor (correctly) can no longer reach — a permanent phantom count.
# Repo-side CLAUDE.md/MEMORY.md (above) + the active plan (below) remain.

# Active plan file (caller-selected by LATEST_PLAN discovery above).
# Active plan only — never scans the whole plans directory.
# Row B3 re-point (under the one switch): scan the durable home, not the
# approval artifact. Under `body` this is byte-for-byte the previous read.
if [ -n "$HANDOFF_BODY_PATH" ] && [ -f "$HANDOFF_BODY_PATH" ]; then
  emit_pending_cpr_ids "$HANDOFF_BODY_PATH" >> "$INLINE_CPR_IDS_FILE"
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

# Reconcile inline CogPR markers against queue.jsonl terminal-per-id. An inline
# <!-- --agnostic-candidate --> block whose id resolves to a TERMINAL queue
# state (promoted, promoted_spec, absorbed, rejected, superseded, skipped,
# dismissed, resolved, withdrawn*, merged, closed, terminal-audit) has already
# been adjudicated — it is a STALE marker, not a live pending CogPR. Count only
# inline ids absent from the queue or still in a non-terminal state. Without this
# the banner reads its own stale write-surface as live (self-operation signal
# discipline / disagreement-as-evidence). NOTE: `deferred` is NOT terminal — a
# deferred inline candidate is genuinely carried and still counts.
CPR_COUNT=$(python3 -c "
import json
ids_path = '$INLINE_CPR_IDS_FILE'
queue = '$QUEUE_FILE'
TERMINAL = {'promoted','promoted_spec','absorbed','rejected','superseded',
            'skipped','dismissed','resolved','merged','closed','terminal-audit',
            'withdrawn','withdrawn_inline_tracked'}
latest = {}
try:
    with open(queue) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: d = json.loads(line)
            except: continue
            i = d.get('id') or d.get('cogpr_id') or d.get('lesson_id')
            if i: latest[i] = d.get('status','')
except FileNotFoundError:
    pass
n = 0
try:
    for raw in open(ids_path):
        i = raw.strip()
        if not i: continue
        if latest.get(i, '') in TERMINAL: continue
        n += 1
except FileNotFoundError:
    pass
print(n)
" 2>/dev/null || echo 0)
rm -f "$INLINE_CPR_IDS_FILE" 2>/dev/null || true

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

# ----------------------------------------------------------------------------
# ACT 4 of 4 on this seam -- cpr-extract backfill.
# ACTOR-AGNOSTIC BY DESIGN (/review 803 round 2, Ruling B). REASON: DEDUP AT
# WRITE. The extractor keys on canonical CogPR identity at the write boundary,
# so a second actor running it re-derives the same rows rather than minting
# duplicates. The absence of an actor axis here is a RECORDED DECISION, not an
# oversight: queue row 3,208 (the tic-802 born) was extracted at 09:23:53Z by
# THIS act running inside the close-fire runner child's boot -- benign and
# useful. Refusing it for a non-primary actor would make queue hygiene depend
# on a human-led boot. Only ACT 1 (mandate auto-write + route) is refused.
# ----------------------------------------------------------------------------
CPR_EXTRACT=$(resolve_script "cpr-extract.py")
if [ -n "$CPR_EXTRACT" ] && [ "$TOTAL_CPRS" -gt 0 ]; then
  # Row B4 re-point (under the one switch): pass the durable home to --plan-file.
  if [ -n "$HANDOFF_BODY_PATH" ] && [ -f "$HANDOFF_BODY_PATH" ]; then
    python3 "$CPR_EXTRACT" --project-dir "$PROJECT_DIR" --plan-file "$HANDOFF_BODY_PATH" 2>/dev/null || true
  else
    python3 "$CPR_EXTRACT" --project-dir "$PROJECT_DIR" 2>/dev/null || true
  fi
fi

# ============================================================================
# Enrichment scanner (background, nonblocking)
# ============================================================================

# ----------------------------------------------------------------------------
# CPR gate-advance reconciler (tic 470) — deterministic tic_gated -> enrichment_needed.
# Runs SYNCHRONOUSLY, BEFORE the HOLDING_CPRS count below, so any row it advances is
# counted as holding and gets its evidence gathered by the scanner THIS same boot.
# Closes the enrichment chicken-and-egg deadlock: the model-only cpr-stepper owns
# extracted->tic_gated (needs DEDUP), but tic_gated->enrichment_needed is mechanical
# and had no deterministic on-disk owner — so mature tic_gated rows starved forever
# with an empty enrichment[] even when their tic-427 baseline consolidated.json existed.
# This reconciler is that owner. Deterministic (no model), idempotent, never promotes.
# ----------------------------------------------------------------------------
# ACT 2 of 4 on this seam -- the CPR gate-advance reconciler.
# ACTOR-AGNOSTIC BY DESIGN (/review 803 round 2, Ruling B). REASON:
# DETERMINISTIC (and idempotent). The tic_gated -> enrichment_needed edge is a
# pure function of on-disk queue state and the tic authority -- no model, no
# authority minted, same input same output for every actor. Re-running it from
# a second boot advances nothing that was not already due. The absence of an
# actor axis here is a RECORDED DECISION, not an oversight; only ACT 1
# (mandate auto-write + trigger-router route) carries an actor axis.
GATE_ADVANCE=$(resolve_script "cpr-gate-advance.py")
if [ -n "$GATE_ADVANCE" ] && [ -f "$QUEUE_FILE" ]; then
  python3 "$GATE_ADVANCE" --project-dir "$PROJECT_DIR" --quiet > /dev/null 2>&1 || true
fi

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
  # Banner must not assert an unowned status transition as automatic: the scanner
  # consolidates evidence artifacts; it does not rename queue status
  # (cgg-ledger#need-asserting-status-name-needs-rename-owner-count-field-not-label).
  ENRICHMENT_MSG="[ENRICHMENT: gathering evidence for $HOLDING_CPRS CogPRs (enrichment_needed/enrichment_eligible FIELD state, queue.jsonl latest-per-id) in background. The scanner consolidates evidence artifacts only — it does NOT rename queue status; status transitions are owned by cpr-gate-advance (deterministic), the cpr-stepper (model lane), and /review verdicts. Results visible in next /review.]"
fi

# ============================================================================
# CPR step lane (async decoupled intelligent run — NOT a compute_due_cycles cycle)
# ============================================================================
# The extracted/tic_gated tiers need intelligent state advancement + DEDUP
# (verify-twin-before-absorb) that the DETERMINISTIC enrichment scanner does not
# perform. cpr-stepper is an AGENT — the assessment needs the model — so unlike the
# enrichment script it cannot be a `scanner.py &` from a hook; it is surfaced as a
# background-agent-spawn instruction, the agent-tier sibling of the enrichment lane
# (same pattern as the MOGUL / RIPPLE protocols). SessionStart-seam-only, which is
# NOT the same as primary-only (corrected /review 803 round 2, Ruling B; the claim
# below read "Primary-only: ... never the citizen boot path" and was FALSE for one
# of the three boot kinds). THREE boot kinds exist: (1) the PRIMARY orchestrator,
# SessionStart -- fires; (2) a SubagentStart CITIZEN, which boots through
# subagent-citizen-boot.py and never reaches this file -- does not fire, so spawned
# citizens do not each launch a stepper; (3) a HEADLESS `claude -p` child (a
# mogul-runner child), which is a TOP-LEVEL session and boots through THIS
# SessionStart seam carrying an empty payload agent_id -- so it DOES fire here.
# Kind (3) is the third-boot-kind blind spot; this lane is surfacing-only (it emits
# a banner instruction, mints nothing), so it is left actor-agnostic. This is the CONSUMER half of the tic-369
# producer-without-reconciler fix (the producer half is pattern_miner
# dedup-at-write). Kept OFF compute_due_cycles deliberately: the stepper is robust
# and slower than the sync cycles, so it belongs in the decoupled lane, not the
# blocking inline scheduler.
# STEPPABLE_CPRS is computed BELOW, after the physical tic count — the honest
# per-id maturity predicate needs the tic authority, which does not exist yet
# at this point in the boot (covenant cpr_step_lane_marker_per_id_maturity_tic655).

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

# ----------------------------------------------------------------------------
# CPR-STEP steppable count — PER-ID TIC-MATURITY (covenant
# cpr_step_lane_marker_per_id_maturity_tic655, admitted /review 655).
# A row is counted steppable only when its OWN maturity gate passes at
# marker-write time: extracted → tic_delta >= maturity_tics (default 3;
# construction_authoritative waived); tic_gated → in-transit (maturity was
# enforced at the prior gate). The t620 scar: the old aggregate said 2
# steppable when the honest per-id set was 1 (one row matured only at 621),
# and the boot injection eats this count to shape stepper dispatch.
# Single-owner predicate: cgg-runtime/scripts/lib/cpr_steppable.py — import
# when path-reachable, else run the faithful embedded replica (keep it in
# lockstep; same pattern as signal_active.py). Fail-visible arms: extracted
# rows without a derivable birth_tic count as steppable; a clock fault
# (TIC_COUNT unresolved) falls back to the legacy aggregate rather than
# silently starving the lane.
# ----------------------------------------------------------------------------
STEPPABLE_CPRS=0
if [ -f "$QUEUE_FILE" ]; then
  STEPPABLE_CPRS=$(python3 -c "
import json, os, sys
entries = {}
for line in open('$QUEUE_FILE'):
    try:
        d = json.loads(line.strip())
        eid = d.get('id','')
        if eid: entries[eid] = d
    except: pass
count_steppable = None
for _libdir in ['$CGG_SCRIPTS_DIR/lib', os.path.expanduser('~/.claude/cgg-runtime/scripts/lib')]:
    if _libdir and os.path.isdir(_libdir):
        sys.path.insert(0, _libdir)
        try:
            from cpr_steppable import count_steppable
            break
        except Exception:
            sys.path.pop(0)
if count_steppable is None:
    _DEFAULT_MATURITY = 3
    _STEPPABLE = ('extracted','tic_gated')
    def _is_steppable(e, tic):
        s = e.get('status','')
        if s == 'tic_gated': return True
        if s != 'extracted': return False
        if e.get('provenance_class') == 'construction_authoritative': return True
        b = e.get('birth_tic')
        if not isinstance(b, int): return True
        try: m = int(e.get('maturity_tics', _DEFAULT_MATURITY))
        except (TypeError, ValueError): m = _DEFAULT_MATURITY
        return (tic - b) >= m
    def count_steppable(entries, tic):
        if not isinstance(tic, int) or tic <= 0:
            return sum(1 for e in entries.values() if e.get('status','') in _STEPPABLE)
        return sum(1 for e in entries.values() if _is_steppable(e, tic))
try:
    _tic = int('${TIC_COUNT:-0}')
except ValueError:
    _tic = 0
print(count_steppable(entries, _tic))
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

# ----------------------------------------------------------------------------
# ACT 1 of 4 on this seam -- mandate auto-write + trigger-router route.
# THE ONE ACT OF THE FOUR THAT CARRIES AN ACTOR AXIS (/review 803 round 2,
# Ruling B, Architect-ratified, recommended option verbatim "Refuse one,
# declare three").
#
# WHY THIS ONE AND NOT THE OTHER THREE: this act is NON-IDEMPOTENT and
# AUTHORITY-BEARING. A mogul-runner `claude -p` child boots through THIS seam
# as a top-level session, so without this guard it could MINT and ROUTE a fresh
# mandate while it was itself executing one -- a runner child manufacturing its
# own successor's obligation. Acts 2, 3 and 4 are declared actor-agnostic by
# design at their own call sites (deterministic; idempotent; dedup at write).
#
# A non-primary actor is REFUSED here: no mandate is written, none is routed, a
# typed line is journaled naming the actor and the refusal, and THE BOOT
# CONTINUES -- acts 2, 3 and 4 still run for that actor.
#
# DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT rule or cure which promoter is the seal seam's ordinary path (that is the tic-801 born, adjudicated at /review 804), does NOT add coverage for the seal hook's PreToolUse stage path, its PostToolUse promoter or its plan-capture identity validator (F-802-B1's residue), and does NOT prove that the obligation variable reaches the SessionStart hook process — that leg remains reasoned from shared parentage until a live refusal row witnesses it.
# ----------------------------------------------------------------------------
ACT1_REFUSED=false
if [ "$TIC_COUNT" -gt 0 ] && [ "$MANDATE_ALREADY_EXISTS" = "false" ] && [ "$BOOT_ACTOR_IS_PRIMARY" = "false" ]; then
  ACT1_REFUSED=true
  BOOT_ACTS_LOG="$AUDIT_LOGS/hooks/boot-act-refusals.jsonl"
  mkdir -p "$(dirname "$BOOT_ACTS_LOG")" 2>/dev/null || true
  # Typed refusal row, MIRRORING the seal reconciler's consume_refused /
  # non_primary_actor shape. Deliberately a SIBLING journal, never the seal's
  # own handoff-seals.jsonl: two different lifecycles must not share one
  # journal, and the seal journal's event distribution is a measured surface.
  ACT1_REFUSAL_ROW=$(CGG_R_ACTOR="$BOOT_ACTOR" CGG_R_CLASS="$BOOT_ACTOR_CLASS" \
    CGG_R_AGENT_ID="$AGENT_ID" CGG_R_OBL_ID="$BOOT_ACTOR_OBLIGATION_ID" \
    CGG_R_OBL_TIC="$BOOT_ACTOR_OBLIGATION_TIC" CGG_R_TIC="$TIC_COUNT" python3 -c '
import json, os
from datetime import datetime, timezone
print(json.dumps({
    "journal_event": "mandate_write_refused",
    "reason": "non_primary_actor",
    "act": "mandate_auto_write_and_trigger_router_route",
    "actor": os.environ.get("CGG_R_ACTOR", ""),
    "actor_class": os.environ.get("CGG_R_CLASS", ""),
    "agent_id": os.environ.get("CGG_R_AGENT_ID", ""),
    "obligation_mandate_id": os.environ.get("CGG_R_OBL_ID") or None,
    "obligation_tic": os.environ.get("CGG_R_OBL_TIC") or None,
    "tic": int(os.environ.get("CGG_R_TIC") or 0),
    "acts_continued": ["cpr_extract_backfill", "cpr_gate_advance", "inbox_sweeps"],
    "at": datetime.now(timezone.utc).isoformat(),
}, separators=(",", ":")))
' 2>/dev/null || true)
  if [ -n "$ACT1_REFUSAL_ROW" ]; then
    if type atomic_append &>/dev/null; then
      atomic_append "$BOOT_ACTS_LOG" "$ACT1_REFUSAL_ROW"
    else
      printf '%s\n' "$ACT1_REFUSAL_ROW" >> "$BOOT_ACTS_LOG"
    fi
  fi

  # ACT 3 ON THE REFUSAL PATH. The sweeps' ordinary call site is NESTED inside
  # the routed branch of ACT 1 below, so refusing ACT 1 would otherwise take
  # ACT 3 down with it -- and ACT 3 is ruled actor-agnostic BY DESIGN. The two
  # invocations are duplicated here rather than hoisted into a shared lane
  # precisely so the PRIMARY's executed path stays byte-for-byte unchanged by
  # this cure. Keep the two sites in lockstep. (Finding F-804-B1.)
  REFUSED_INBOX_SCANNER=$(resolve_script "inbox-envelope.py")
  if [ -n "$REFUSED_INBOX_SCANNER" ]; then
    python3 "$REFUSED_INBOX_SCANNER" \
      --zone-root "$ZONE_ROOT" \
      sweep \
      --entity ent_homeskillet \
      --current-tic "$TIC_COUNT" \
      > /dev/null 2>&1 || true
    python3 "$REFUSED_INBOX_SCANNER" \
      --zone-root "$ZONE_ROOT" \
      sweep \
      --entity ent_mogul \
      --current-tic "$TIC_COUNT" \
      > /dev/null 2>&1 || true
  fi
fi

if [ "$TIC_COUNT" -gt 0 ] && [ "$MANDATE_ALREADY_EXISTS" = "false" ] && [ "$BOOT_ACTOR_IS_PRIMARY" != "false" ]; then
  # ── Reconcile-first cycle computation (CogPR-57 fix #3) ──
  # Primary: read previous mandate's tic_context for scheduled due_tic values.
  # Secondary: estate_snapshot or modulo fallback only when no previous context.
  # This prevents recomputation drift where modulo math disagrees with the
  # schedule that cadence/review explicitly set in tic_context.
  DUE_CYCLES_CSV=$(python3 -c "
import json, os, sys

tic = $TIC_COUNT
prev = '$MANDATE_FILE'
# NOTE (legibility, tic 597): base_cycles schedules ONLY the lightweight always-due
# cycles (run inline via cgg-gate.sh). The self-waking HEAVY cycles --
# harmony_invoke / contagion_heartbeat / economy_heartbeat / review_close_check /
# civil_status_check -- are intentionally NOT scheduled here: they are produced on the
# /cadence -> mandate loop (cadence-ops.py compute_due_cycles) and dispatched to Mogul
# via cgg-gate.sh heavy-routing. Their absence here is lane separation, not omission.
base_cycles = ['queue_refresh', 'signal_scan']  # always due

# ── Primary: reconcile from previous mandate tic_context ──
tc = {}
has_prev_context = False
if os.path.isfile(prev):
    try:
        p = json.load(open(prev))
        tc = p.get('tic_context', {})
        # Previous context is valid if it has any due_tic fields
        if any(k.endswith('_due_tic') for k in tc):
            has_prev_context = True
    except: pass

if has_prev_context:
    # Schedule-driven: use due_tic values from previous mandate
    due_map = {
        'memory_mining': 'memory_mining_due_tic',
        'cache_refresh': 'cache_refresh_due_tic',
        'pattern_mining': 'pattern_mining_due_tic',
        'ladder_audit': 'ladder_audit_due_tic',
        'deep_audit': 'deep_audit_due_tic',
    }
    for cycle, key in due_map.items():
        due_at = tc.get(key)
        if due_at and tic >= due_at:
            base_cycles.append(cycle)
else:
    # ── Fallback: modulo-based defaults (no previous context) ──
    if tic % 3 == 0: base_cycles.append('memory_mining'); base_cycles.append('cache_refresh')
    if tic % 4 == 0: base_cycles.append('pattern_mining')
    if tic % 5 == 0: base_cycles.extend(['ladder_audit', 'runtime_drift_check'])
    if tic % 8 == 0: base_cycles.append('deep_audit')

# ── Optional: estate_snapshot can ADD cycles but not replace schedule ──
estate_py = '$ZONE_ROOT/$AUDIT_LOGS_REL/cpg/scripts/estate_snapshot.py'
if os.path.isfile(estate_py):
    try:
        import subprocess
        env = os.environ.copy()
        env['ZONE_ROOT'] = '$ZONE_ROOT'
        r = subprocess.run(['python3', estate_py, '--json'],
                          capture_output=True, text=True, env=env, timeout=10)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            estate_cycles = data.get('profile_selection', {}).get('cycles', [])
            for c in estate_cycles:
                if c not in base_cycles:
                    base_cycles.append(c)
    except: pass

print(','.join(sorted(set(base_cycles))))
" 2>/dev/null || echo "queue_refresh,signal_scan")

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
        'cache_refresh_due_tic': tic+(3-tic%3) if tic%3!=0 else tic+3,
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
          # ACT 3 of 4 on this seam -- the inbox sweeps.
          # ACTOR-AGNOSTIC BY DESIGN (/review 803 round 2, Ruling B). REASON:
          # IDEMPOTENT. A DEFER->WAIT resurfacing re-derives the same due set
          # from the same tic; sweeping twice resurfaces nothing twice. The
          # absence of an actor axis here is a RECORDED DECISION, not an
          # oversight. NOTE (structural, F-804-B1): this call site is NESTED
          # inside ACT 1's guard and its routed branch, so it is reachable on
          # the PRIMARY's path only. A non-primary actor, whose ACT 1 is
          # refused, runs the same two sweeps from the refusal branch above --
          # duplicated deliberately rather than hoisted, so that the primary's
          # EXECUTED path stays byte-for-byte what it was before this cure.
          # Best-effort reminder/missed-fire sweep + manual-drop reconcile at boot
          # (mailbox lane consolidation, tic 384). Resurfaces due deferred reminders
          # (DEFER->WAIT) and reconciles hand-dropped + directory envelopes so the
          # scan below reflects filesystem truth. Authoritative catch is /cadence;
          # this just reduces latency when a session starts past a due tic.
          python3 "$INBOX_SCANNER" \
            --zone-root "$ZONE_ROOT" \
            sweep \
            --entity ent_homeskillet \
            --current-tic "$TIC_COUNT" \
            > /dev/null 2>&1 || true
          python3 "$INBOX_SCANNER" \
            --zone-root "$ZONE_ROOT" \
            sweep \
            --entity ent_mogul \
            --current-tic "$TIC_COUNT" \
            > /dev/null 2>&1 || true

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
        'cache_refresh_due_tic': tic+(3-tic%3) if tic%3!=0 else tic+3,
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
        # Inject agent identity into the mandate-history compact write
        # (preserves which agent context spawned the session if present).
        MANDATE_COMPACT=$(echo "$MANDATE_JSON" | AGENT_ID="$AGENT_ID" AGENT_TYPE="$AGENT_TYPE" python3 -c "
import json, sys, os
m = json.load(sys.stdin)
m['agent_id'] = os.environ.get('AGENT_ID') or ''
m['agent_type'] = os.environ.get('AGENT_TYPE') or ''
print(json.dumps(m, separators=(',',':')))
" 2>/dev/null)
        # Daily partition key on the ONE declared clock (UTC) — writer #3 of THREE
        # into mandates/history/<date>.jsonl, moved atomically with
        # mandate-write.py:416 (via lib/partition_key.py) and mogul-runner.sh:317.
        # A partition key is a JOIN key: half-landing this atom would put the
        # mandate-compact row and the mandate row in DIFFERENTLY-named files for the
        # SAME mandate during the 20:00-24:00 EDT window.
        # Historical locally-named files are NEVER renamed; forward-only.
        TODAY=$(date -u +%Y-%m-%d)
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

# Rows B5 and B6 re-point (under the one switch): awk the durable home. Under
# `body` HANDOFF_BODY_PATH IS $LATEST_PLAN, so every emitted byte is unchanged.
HANDOFF_MSG=""
if [ -n "$HANDOFF_BODY_PATH" ]; then
  NEXT_ACTIONS=$(awk '/^## Next Actions/,/^## [^N]/' "$HANDOFF_BODY_PATH" 2>/dev/null | head -20 | sed 's/"/\\"/g' | tr '\n' ' ')
  if [ -n "$NEXT_ACTIONS" ] && [ ${#NEXT_ACTIONS} -gt 20 ]; then
    HANDOFF_MSG="[CGG HANDOFF NEXT ACTIONS: $NEXT_ACTIONS] [Full plan if needed: $HANDOFF_BODY_PATH]"
  else
    WORKING=$(awk '/^### Not Started/,/^### [^N]/' "$HANDOFF_BODY_PATH" 2>/dev/null | head -15 | sed 's/"/\\"/g' | tr '\n' ' ')
    if [ -n "$WORKING" ] && [ ${#WORKING} -gt 20 ]; then
      HANDOFF_MSG="[CGG HANDOFF REMAINING: $WORKING] [Full plan if needed: $HANDOFF_BODY_PATH]"
    else
      HANDOFF_MSG="[CGG CHARTER: Read $HANDOFF_BODY_PATH]"
    fi
  fi
fi
[ -n "$HANDOFF_POINTER_MSG" ] && HANDOFF_MSG="${HANDOFF_MSG:+$HANDOFF_MSG }$HANDOFF_POINTER_MSG"
[ -n "$HANDOFF_MSG" ] && CGG_MSG="${CGG_MSG:+$CGG_MSG }$HANDOFF_MSG"
if [ -n "$TRIGGER_MSG" ]; then
  CGG_MSG="$CGG_MSG $TRIGGER_MSG"
fi
if [ "$TOTAL_CPRS" -gt 0 ]; then
  # Lifecycle banner names OWNED transitions, not a linear label chain: 13/13 of the
  # birth-650..658 cohort reached terminal without traversing enrichment_eligible —
  # asserting the unwalked chain as the path misleads every booting reader
  # (cgg-ledger#need-asserting-status-name-needs-rename-owner-count-field-not-label).
  CGG_MSG="$CGG_MSG [CPR QUEUE: $TOTAL_CPRS pending ($CPR_COUNT inline + $QUEUE_COUNT in queue.jsonl). /review when ready.] [CPR LIFECYCLE v1: status values are LABELS over queue.jsonl latest-per-id FIELD state; every transition has an OWNER — cpr-stepper (extracted -> tic_gated maturity-gated; enrichment_eligible -> promotable), cpr-gate-advance (tic_gated -> enrichment_needed, deterministic), /review verdicts (terminal states + DEFER). No unowned edge advances by itself. Run /review to triage and promote.]"
fi
if [ -n "$ENRICHMENT_MSG" ]; then
  CGG_MSG="$CGG_MSG $ENRICHMENT_MSG"
fi
# CPR step lane: surface a background cpr-stepper spawn when extracted/tic_gated
# entries await advancement. Per-tic dedup guard (seen marker keyed on TIC_COUNT)
# prevents re-spawning on repeated session clears within the same tic.
if [ "$STEPPABLE_CPRS" -gt 0 ]; then
  CPR_STEP_SEEN="$AUDIT_LOGS/hooks/cpr-step-lane-seen.json"
  CPR_STEP_LAST_TIC=""
  [ -f "$CPR_STEP_SEEN" ] && CPR_STEP_LAST_TIC=$(python3 -c "import json;print(json.load(open('$CPR_STEP_SEEN')).get('tic',''))" 2>/dev/null || echo "")
  if [ "$CPR_STEP_LAST_TIC" != "$TIC_COUNT" ]; then
    CGG_MSG="$CGG_MSG [CPR STEP: $STEPPABLE_CPRS CogPR(s) in extracted/tic_gated awaiting intelligent state advancement + DEDUP. Async-decoupled lane (NOT a cadence cycle). Dispatch the cpr-stepper office steward in background — an entity at the appropriate state, via the lead harness's active dispatch surface (subagent / workflow / agent-team; stewards of each office are installed to that end) — NON-BLOCKING, proceed with user work. The stepper advances each entry one step, runs verify-twin DEDUP, writes state changes to queue.jsonl; promotion stays gated at /review. Results visible in next /review.] [CPR STEP PROTOCOL v1: (1) Dispatch cpr-stepper in background via the active harness dispatch surface. (2) NON-BLOCKING — do not wait. (3) Stepper mutates queue.jsonl state only (extracted->...->absorbed/promotable); it never promotes. (4) Re-surfaces next tic if entries remain (one step per session per entry).]"
    mkdir -p "$(dirname "$CPR_STEP_SEEN")" 2>/dev/null
    printf '{"tic": %s, "steppable": %s, "predicate": "per_id_maturity_v1"}\n' "${TIC_COUNT:-0}" "$STEPPABLE_CPRS" > "$CPR_STEP_SEEN" 2>/dev/null || true
  fi
fi

# ============================================================================
# Signal store scanning (constitutional: no expired status, acoustic decay)
# ============================================================================

SIGNAL_DIR="$AUDIT_LOGS/signals"
SIREN_MSG=""
if [ -d "$SIGNAL_DIR" ]; then
  SIREN_MSG=$(python3 -c "
import json, os, glob, sys
# Source signals from active-manifest.jsonl (authoritative curated truth).
# Daily logs contain raw emissions with mixed schemas; the manifest is deduplicated.
manifest = os.path.join('$SIGNAL_DIR', 'active-manifest.jsonl')
signals = []
if os.path.isfile(manifest):
    for line in open(manifest):
        try:
            d = json.loads(line)
            signals.append(d)
        except: pass
# Terminal-valve latest-per-id projection (bk-boot-banner-latest-per-id-reader,
# tic 686) — SOURCE OF TRUTH: signal_active.latest_per_id (imported below with
# is_active_ray when reachable; embedded replica kept in lockstep otherwise).
# The manifest is append-only BETWEEN prune sweeps: an update/resolve appends a
# NEW row for the same signal, so counting every row counts stale predecessors
# (the 65/62-vs-57 banner divergence, t681/t682/t685) and can crown a resolved
# row loudest. 'Latest' = file-append order within this ONE file (chronological
# provenance); key = signal_id then id; id-less rows pass through unprojected
# (never silently dropped).
def _latest_per_id_replica(records):
    latest = {}
    unkeyed = []
    for rec in records:
        if not isinstance(rec, dict): continue
        sid = rec.get('signal_id') or rec.get('id')
        if sid: latest[sid] = rec
        else: unkeyed.append(rec)
    return list(latest.values()) + unkeyed
latest_per_id = None
# Warrants: still scan daily logs (no manifest yet)
warrants = {}
for f in sorted(glob.glob('$SIGNAL_DIR/*.jsonl')):
    if os.path.basename(f) == 'active-manifest.jsonl': continue
    for line in open(f):
        try:
            d = json.loads(line)
            eid = d.get('id', '')
            if not eid: continue
            if d.get('type') == 'warrant':
                warrants[eid] = d
        except: pass
# Active-ray predicate — SOURCE OF TRUTH: cgg-runtime/scripts/lib/signal_active.py
# (single-owner v2-projection retirement of the raw status-enum, tic 403; reader
# sweep tic 571). Import from the lib when path-reachable; else run the faithful
# embedded replica below (keep it in lockstep with signal_active.py).
is_active_ray = None
for _libdir in ['$CGG_SCRIPTS_DIR/lib', os.path.expanduser('~/.claude/cgg-runtime/scripts/lib')]:
    if _libdir and os.path.isdir(_libdir):
        sys.path.insert(0, _libdir)
        try:
            from signal_active import is_active_ray
            try:
                from signal_active import latest_per_id
            except ImportError:
                pass  # older installed lib — replica below covers it
            break
        except Exception:
            sys.path.pop(0)
if latest_per_id is None:
    latest_per_id = _latest_per_id_replica
signals = latest_per_id(signals)
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
active_sigs = [s for s in signals if is_active_ray(s)]
active_wrns = [w for w in warrants.values() if w.get('status') in ('active','acknowledged')]
if not active_sigs and not active_wrns:
    sys.exit(0)
loudest = max(active_sigs, key=lambda s: s.get('volume',0), default=None)
parts = ['[SIREN: %d active signals, %d active warrants.' % (len(active_sigs), len(active_wrns))]
if loudest:
    sid = loudest.get('signal_id', loudest.get('id','?'))
    parts.append('Loudest: %s (volume=%s, band=%s).' % (sid, loudest.get('volume',0), loudest.get('band','?')))
parts.append('/siren when ready.]')
parts.append('[SIREN PROTOCOL v1: (1) High-volume signals (>30) may warrant triage before other work. (2) Run /siren to view, triage, and resolve signals. (3) Warrants indicate governance obligations requiring action. (4) Band context: PRIMITIVE=safety/data integrity, COGNITIVE=learning/process, SOCIAL=collaboration.]')
print(' '.join(parts))
" 2>/dev/null || true)
fi

# ============================================================================
# Crisis injection condition checks (crisis-response/README.md)
# ============================================================================
# Lightweight post-scan pass: checks signal storm, mandate pileup, inbox
# backlog. Runtime divergence check is deferred (slower) and only runs if
# other conditions are clean.

CRISIS_MSG=""
CRISIS_CHECKER=$(resolve_script "crisis-injection.py")
if [ -n "$CRISIS_CHECKER" ] && [ "$TIC_COUNT" -gt 0 ]; then
  CRISIS_RAW=$(python3 "$CRISIS_CHECKER" \
    --zone-root "$ZONE_ROOT" \
    --audit-logs "$AUDIT_LOGS" \
    --current-tic "$TIC_COUNT" \
    --live-active-threshold \
    2>/dev/null || true)
  if [ -n "$CRISIS_RAW" ]; then
    CRISIS_MSG="$CRISIS_RAW [CRISIS PROTOCOL v1: (1) Pause non-critical work. (2) Triage via /siren. (3) If mandate-related, check audit-logs/mogul/mandates/. (4) If signal-related, check audit-logs/signals/active-manifest.jsonl.]"
  fi
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
    PARALLEL_MSG="[PARALLEL: $RECENT_COUNT recent sessions on this project in last 2h. (1) ADVISORY — files may have changed since your handoff. (2) Re-read target files before editing. (3) git pull if working on shared branch. (4) Coordinate via /cadence to avoid duplicate work.]"
  fi
fi

# ============================================================================
# Inbox injection (inbox-query.py inject)
# ============================================================================

INBOX_MSG=""
INBOX_QUERY=$(resolve_script "inbox-query.py")
if [ -n "$INBOX_QUERY" ] && [ "$TIC_COUNT" -gt 0 ]; then
  INBOX_RAW=$(python3 "$INBOX_QUERY" --format text inject \
    --entity ent_homeskillet \
    --current-tic "$TIC_COUNT" \
    2>/dev/null || true)
  if [ -n "$INBOX_RAW" ]; then
    # Flatten multi-line output for JSON embedding
    INBOX_MSG=$(echo "$INBOX_RAW" | tr '\n' ' ' | sed 's/  */ /g')
  fi
fi

# ============================================================================
# Boot-injection lane (shared registry with subagent-citizen-boot.py)
# Tic-gated broadcast pointers (e.g. GLOSSARY doctrine-surface navigation).
# Read-only renderer — mints no signals, fail-soft to empty.
# ============================================================================

BOOT_INJECTION_MSG=""
BOOT_INJECTION_SCRIPT=$(resolve_script "boot-injection.py")
if [ -n "$BOOT_INJECTION_SCRIPT" ] && [ "$TIC_COUNT" -gt 0 ]; then
  BOOT_INJECTION_RAW=$(python3 "$BOOT_INJECTION_SCRIPT" render \
    --tic "$TIC_COUNT" --audience orchestrator --zone-root "$PROJECT_DIR" --max-chars 20000 2>/dev/null || true)
  if [ -n "$BOOT_INJECTION_RAW" ]; then
    BOOT_INJECTION_MSG=$(echo "$BOOT_INJECTION_RAW" | tr '\n' ' ' | sed 's/  */ /g')
  fi
fi

# ============================================================================
# Pertinence worldview (office-worldview.py) — the PRIMARY orchestrator's seam.
# SubagentStart boots spawned citizens; the primary (ent_homeskillet) boots HERE,
# so the compiled civic orientation rides in alongside the handoff. Read-only,
# mints no signals, fail-soft. Line structure is preserved (JSON \n-escaped, not
# space-flattened) so the per-line authority badges stay legible. The budget-exempt
# boot-receipt request frame is appended by the compiler. (Architect, tic-332 gate.)
# ============================================================================

WORLDVIEW_MSG=""
WORLDVIEW_SCRIPT=$(resolve_script "office-worldview.py")
if [ -n "$WORLDVIEW_SCRIPT" ] && [ "$TIC_COUNT" -gt 0 ] && [ "$EFFECTIVE_RECORD_HYDRATION_BLOCKED" -eq 0 ]; then
  # b3: hand the renderer this boot's hydration view (built once at the gate above)
  # so its row-scoped effective projection reuses that build; absent/unreadable file
  # falls back to the stored index inside the renderer.
  WORLDVIEW_EFF_ARGS=""
  [ -n "${EFFECTIVE_VIEW_FILE:-}" ] && [ -f "$EFFECTIVE_VIEW_FILE" ] && \
    WORLDVIEW_EFF_ARGS="--effective-view $EFFECTIVE_VIEW_FILE"
  WORLDVIEW_RAW=$(python3 "$WORLDVIEW_SCRIPT" render \
    --office ent_homeskillet --tic "$TIC_COUNT" --format human \
    --zone-root "$PROJECT_DIR" --max-chars 20000 $WORLDVIEW_EFF_ARGS 2>/dev/null || true)
  [ -n "${EFFECTIVE_VIEW_FILE:-}" ] && rm -f "$EFFECTIVE_VIEW_FILE" 2>/dev/null
  if [ -n "$WORLDVIEW_RAW" ]; then
    # JSON-escape preserving newlines as \n (NOT flattened) for safe additionalContext
    # embedding — keeps the badge-per-line worldview readable in the injected context.
    WORLDVIEW_MSG=$(printf '%s' "$WORLDVIEW_RAW" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read())[1:-1])" 2>/dev/null || true)
  fi
fi

# ============================================================================
# Mid-tic resumption note (bk-sovereign-midtic-pause-receipt, tic 683): if a
# durable hold-note exists for the ACTIVE emission, inject it — resumption
# never leans on harness-transcript fidelity. Fail-soft; the note lane is
# audit-logs/tics/interstitial-notes.jsonl (midtic-note.py, sibling of the
# interstitial marker — this hook is the lane's live consumer).
# ============================================================================
MIDTIC_MSG=""
MIDTIC_SCRIPT=$(resolve_script "midtic-note.py")
if [ -n "$MIDTIC_SCRIPT" ]; then
  ACTIVE_EMISSION=$(python3 -c "
import json
try:
    print(json.load(open('$AUDIT_LOGS/tics/.interstitial-marker.json')).get('emission_id') or '')
except Exception:
    print('')
" 2>/dev/null)
  if [ -n "$ACTIVE_EMISSION" ]; then
    MIDTIC_MSG=$(python3 "$MIDTIC_SCRIPT" --zone-root "$ZONE_ROOT" latest \
      --emission-id "$ACTIVE_EMISSION" --format line 2>/dev/null || true)
    [ "$MIDTIC_MSG" = "no note" ] && MIDTIC_MSG=""
  fi
fi

# ============================================================================
# Combine all context
# ============================================================================

FULL_MSG=""
# Worldview leads — the civic orientation prepends the handoff (Architect, tic 332).
# The BOOT READ INVARIANT (pseudo_temperature, tic 406) rides INSIDE the worldview as
# its leading SUBSTRATE fragment (office-worldview.py) — universal across both boot
# seams + every entity-state — NOT a session-restore-only prepend (that was the wrong
# lane; the worldview is the single source, rendered here and in subagent-citizen-boot).
[ -n "$WORLDVIEW_MSG" ] && FULL_MSG="$WORLDVIEW_MSG"
[ -n "$CGG_MSG" ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }$CGG_MSG"
[ -n "$SIREN_MSG" ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }$SIREN_MSG"
[ -n "$INBOX_MSG" ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }$INBOX_MSG"
[ -n "$BOOT_INJECTION_MSG" ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }$BOOT_INJECTION_MSG"
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
[ -n "$MIDTIC_MSG" ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }$MIDTIC_MSG"
[ -n "$PARALLEL_MSG" ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }$PARALLEL_MSG"
[ -n "$CRISIS_MSG" ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }$CRISIS_MSG"
[ -n "$SEAL_RECONCILE_MSG" ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }$SEAL_RECONCILE_MSG"
[ "$TIC_COUNT" -gt 0 ] && FULL_MSG="${FULL_MSG:+$FULL_MSG }[TIC: #$TIC_COUNT]"

# ── Handoff consumption protocol hint (versioned, structural) ──
# Appended when a cadence handoff is detected. Tells the consuming session
# how to treat the Next Actions — not memory-dependent, injected with the data.
if [ -n "$LATEST_PLAN" ]; then
  FULL_MSG="$FULL_MSG [CGG CONSUMPTION PROTOCOL v1: Next Actions from the prior handoff are your primary work queue. (1) Consume the Mogul mandate first as governance overhead — report compactly. (2) Surface the Next Actions as a numbered TODO in your first substantive response. (3) Verify each item against current state before executing — items may already be completed. (4) Incomplete items carry forward to the next handoff. The mandate is not the session's purpose — the Next Actions are.]"
fi

SESSION_TITLE=""
if [ "$TIC_COUNT" -gt 0 ]; then
  SESSION_TITLE="canonical tic-$TIC_COUNT"
fi

if [ -n "$FULL_MSG" ]; then
  HOOK_OUTPUT="{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"$FULL_MSG\",\"reloadSkills\":true"
  if [ -n "$SESSION_TITLE" ]; then
    HOOK_OUTPUT="$HOOK_OUTPUT,\"sessionTitle\":\"$SESSION_TITLE\""
  fi
  HOOK_OUTPUT="$HOOK_OUTPUT}}"
  echo "$HOOK_OUTPUT"
fi

exit 0
