#!/usr/bin/env bash
# atomic-append.sh — JSONL-safe atomic append using flock
# Source this file, then call: atomic_append "$TARGET_FILE" "$JSON_LINE"
#
# Uses flock for mutual exclusion across concurrent processes.
# Falls back to direct append if flock is unavailable (with warning).
# Enforces single-line invariant: multi-line JSON is compacted before append.

# ── promote-writeback physics gate (bk-emitter-review-wiring, tic 481) ──────────
# When a PROMOTE-class CogPR row lands in queue.jsonl, fire the emit-side writeback
# (review-promote-writeback.py: inline status flip + auto-memory breadcrumb) AT THE
# APPEND BOUNDARY, so the writeback can no longer be silently skipped by an LLM applier
# — it is enforced as a side-effect of the promotion itself, the SAME boundary that
# writes the queue row (the way the queue is already written via atomic-append, not Edit).
# Moves the emit-side writeback from prompt-level "review-execute should call it" to
# enforced-at-the-execution-boundary (three-layer tool economics: physics layer).
#
# Safety contract: scoped to */cprs/queue.jsonl + promote-class status ONLY (every other
# JSONL append is byte-for-byte unchanged — the case in atomic_append never matches them);
# fires AFTER the row is durably appended (cannot corrupt the write); idempotent (re-fire
# is a no-op); fully fail-soft (always returns 0; never affects the append's result).
#
# ── REACHABILITY CURE (bk-reinforced-by-stamper-trigger-never-keyed, B2 wave 8 row B,
#    /review 770 round 2 Q5; cures F-769-B1 / OM-B1, filed HIGH by the wave-7 citizen) ──
# This gate ORIGINALLY required a TRUTHY `promoted_to` before it would invoke the
# writeback. That predicate is correct for a PROMOTE landing and WRONG as the sole
# admission test: an ABSORB-side `reinforce_existing` landing carries `absorbed_into`,
# never `promoted_to` (0 of 14 latest-per-id reinforce rows carry one — measured tic 769,
# RE-MEASURED 0/14 at tic 770). So the wave-7 landing_kind-keyed reinforce trigger inside
# review-promote-writeback.py — built, tested, and live — was UNREACHABLE from its ONLY
# automatic caller: this boundary. Mechanism present, dataflow dead ("can it eat?").
#
# THE CURE: `promoted_to` stops being an admission requirement and becomes a MODE
# SELECTOR.
#   • PROMOTE path (unchanged): id + promoted_to + review_tic -> argv carries --promoted-to.
#   • KEYED path (new): id + review_tic + NO promoted_to + a `landing_kind` on the row
#     -> argv OMITS --promoted-to, which is exactly the shape review-promote-writeback.py
#     already documents as KEYED reinforced-by mode (`--promoted-to` is `required=False`;
#     the missing value routes to `fire_reinforce_trigger` before any usage error).
#
# ENGINE-CONTENT SEPARATION (federation KI) — WHY THE PREDICATE HERE IS `landing_kind`
# PRESENT AND NOT `landing_kind == reinforce_existing`: the REINFORCE FAMILY is OPEN-BY-
# /review and lives in contracts/landing-kind-enum-v1.json, read by the consumer. If this
# bash boundary re-implemented family membership it would become a SECOND reader of that
# vocabulary and would silently re-open this very unreachability class the next time
# /review accretes a stamp-mandating value. So the boundary's test is STRUCTURAL ("this
# row took a landing, so a keyed trigger may apply") and the vocabulary decision stays
# with the one consumer that reads the contract. The consumer is FAIL-CLOSED: an
# off-family landing_kind, an unresolvable `absorbed_into`, or an unreadable contract all
# leave the stamper DISARMED with a typed reason and write nothing.
#
# NOT WIDENED: the */cprs/queue.jsonl scope containment and the promote-class `status`
# pre-filter are BOTH untouched — a non-queue append and a non-promote-class row are
# refused exactly as before. A row with neither `promoted_to` nor `landing_kind` is still
# declined here (nothing to promote to, nothing to key on).
#
# ⚠ DOES-NOT-SATISFY RIDER (verbatim, carried from the wave-7 receipt and the signed wave):
#   This cure does NOT retroactively stamp anything — the backfill population measured 0
#   twice, OM-B2 adjudicated already-discharged this fence.
#   It also does NOT prove a LIVE natural firing: reachability is proven end-to-end
#   hermetically (scripts/lib/test_promote_gate.sh arms E1-E6), and no naturally-occurring
#   reinforce landing has yet traversed this boundary in production.
_cgg_fire_promote_writeback() {
  local row="$1"
  # cheap bash pre-filter: only promote-class rows are candidates (no python spawn for
  # the frequent extracted/enrichment/deferred/skipped queue writes).
  case "$row" in
    *'"promoted"'*|*'"promoted_spec"'*|*'"absorbed"'*) : ;;
    *) return 0 ;;
  esac
  local rpw
  rpw="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)/review-promote-writeback.py"
  [ -f "$rpw" ] || return 0
  # precise check + dispatch: parse the row, fire ONLY for a promote-class `status`.
  python3 - "$rpw" "$row" <<'PY' 2>/dev/null || true
import json, subprocess, sys
rpw, row = sys.argv[1], sys.argv[2]
try:
    d = json.loads(row)
except Exception:
    sys.exit(0)
if d.get("status") not in ("promoted", "promoted_spec", "absorbed"):
    sys.exit(0)
cpr_id, promoted_to, review_tic = d.get("id"), d.get("promoted_to"), d.get("review_tic")
if not (cpr_id and review_tic is not None):
    sys.exit(0)  # incomplete row — the explicit review-execute call covers it
argv = ["python3", rpw, "--cpr-id", str(cpr_id),
        "--review-tic", str(review_tic), "--status", str(d["status"])]
if promoted_to:
    argv += ["--promoted-to", str(promoted_to)]           # PROMOTE path (unchanged)
elif not d.get("landing_kind"):
    # No promotion target AND no landing to key on -> nothing this boundary can dispatch.
    sys.exit(0)
# else: KEYED path — omit --promoted-to so review-promote-writeback.py resolves the
# reinforce trigger from the row's landing_kind against the landing-kind contract.
# Family membership is NEVER decided here (engine-content separation); the consumer is
# fail-closed and writes nothing when it does not arm.
subprocess.run(argv, check=False)
PY
  return 0
}

# ── body-preservation physics gate (Repair Covenant B, /review 635) ─────────────
# A Repair-B compat-snapshot typed event (`"compat_snapshot":true`) carries the current
# formulation forward so BOTH the naive latest-per-id reader and the shadow materializer
# stay non-lossy. If such a row reaches the boundary with a BLANK body, it would re-open
# the exact erasure Defect A. Refuse it BEFORE the write (physics layer — the perception
# layer warns too late; footgun-guard-at-perception-layer). Scoped to */cprs/queue.jsonl +
# compat_snapshot rows ONLY: legacy writers and future pure-Option-B events are untouched.
# Returns 3 to signal "refuse the append".
_cgg_guard_body_preservation() {
  local row="$1"
  # Forward-contract discriminator: only Repair-B typed events carry `schema_version`.
  # Legacy-compatible bodyless extractions (no schema_version) remain temporarily permitted
  # and pass UNTOUCHED — the global producer/consumer migration (STRIKE_READY_UNEXECUTED) is
  # what makes Defects A/B fleet-wide impossible; this gate enforces only the typed path.
  case "$row" in *'"schema_version"'*|*'"compat_snapshot"'*) : ;; *) return 0 ;; esac
  python3 - "$row" <<'PY'
import json, sys
try:
    d = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)
et = d.get("event_type")
# (a) forward-contract typed BIRTH must carry formulation + hashed source provenance,
#     else it is PREP_NOT_READY (Defect-B guard on the typed path) — reject/quarantine.
if et == "birth":
    body = (d.get("origin_formulation") or d.get("current_formulation") or d.get("lesson") or "").strip()
    prov = d.get("origin_source_hash") or d.get("origin_source_pointer")
    if not body or not prov:
        sys.stderr.write("[atomic-append] REFUSED PREP_NOT_READY: forward-contract typed birth lacking "
                         f"formulation+hashed provenance (id={d.get('id')!r})\n")
        sys.exit(4)
# (b) compat_snapshot events must carry a nonblank body, else they re-open Defect A.
if d.get("compat_snapshot") is True:
    body = (d.get("lesson") or d.get("current_formulation") or "").strip()
    if not body:
        sys.stderr.write("[atomic-append] REFUSED: Repair-B compat_snapshot row with BLANK body "
                         f"(id={d.get('id')!r}, event_type={et!r}) — would re-open Defect A\n")
        sys.exit(3)
sys.exit(0)
PY
}

atomic_append() {
  local target="$1"
  local content="$2"
  local lockfile="${target}.lock"

  # body-preservation physics gate — refuse a blank-body compat row (rc=3) or a
  # provenance-less forward-contract birth (rc=4) BEFORE writing.
  case "$target" in
    */cprs/queue.jsonl)
      _cgg_guard_body_preservation "$content"; local _grc=$?
      if [ "$_grc" -ne 0 ]; then
        echo "[atomic-append] append ABORTED by body-preservation gate (rc=$_grc) for $target" >&2
        return "$_grc"
      fi
      ;;
  esac

  # Ensure parent directory exists
  mkdir -p "$(dirname "$target")" 2>/dev/null

  # JSONL safety: compact multi-line JSON to single line before appending.
  # If content contains newlines and target is .jsonl, compact it.
  case "$target" in
    *.jsonl)
      if printf '%s' "$content" | grep -q $'\n'; then
        local compacted
        compacted=$(printf '%s' "$content" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin), separators=(',',':')))" 2>/dev/null)
        if [ -n "$compacted" ]; then
          content="$compacted"
        else
          echo "[atomic-append] WARN: failed to compact multi-line JSON for $target" >&2
        fi
      fi
      ;;
  esac

  if command -v flock >/dev/null 2>&1; then
    # flock available — use exclusive lock
    {
      flock -x 9
      printf '%s\n' "$content" >> "$target"
    } 9>"$lockfile"
  else
    # macOS fallback: use mkdir-based lock
    local lock_dir="${target}.lockdir"
    local max_wait=10
    local waited=0

    while ! mkdir "$lock_dir" 2>/dev/null; do
      waited=$((waited + 1))
      if [ "$waited" -ge "$max_wait" ]; then
        echo "[atomic-append] WARN: lock timeout on $target, appending without lock" >&2
        printf '%s\n' "$content" >> "$target"
        return 1
      fi
      sleep 0.1
    done

    printf '%s\n' "$content" >> "$target"
    rmdir "$lock_dir" 2>/dev/null
  fi

  # promote-writeback physics gate — fire AFTER the row is durably appended, scoped to
  # the CogPR queue + promote-class rows only. Fail-soft; never alters the append result.
  case "$target" in
    */cprs/queue.jsonl) _cgg_fire_promote_writeback "$content" || true ;;
  esac
}

# Python-callable version for subprocess invocation.
#
# Argument-shape guard (bk-atomic-append-positional-silent-noop, struck tic 692):
# EXECUTED without the --append sentinel this file used to fall through — exit 0,
# ZERO bytes written — a silent no-op that read as success at every call site
# (caught live by the tic-691 cpr-stepper reading its receipt back). Misuse now
# fails LOUD: exit 2 + usage naming the sentinel. Scoped to EXECUTION only
# (BASH_SOURCE test): sourcing consumers (cgg-gate / session-restore /
# posttool-microscan / mogul-runner) carry their own positional args, which must
# stay inert — a sourced library must never act on, or object to, its caller's argv.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  if [ "${1:-}" = "--append" ] && [ -n "${2:-}" ] && [ -n "${3:-}" ]; then
    atomic_append "$2" "$3"
  else
    echo "usage: atomic-append.sh --append <target-file> <json-line>" >&2
    echo "[atomic-append] REFUSED (exit 2): executed without the --append sentinel (got: ${*:-<no args>}) — this misuse-shape used to no-op silently with exit 0; it now fails loud (bk-atomic-append-positional-silent-noop)." >&2
    exit 2
  fi
fi
