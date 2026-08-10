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
if not (cpr_id and promoted_to and review_tic is not None):
    sys.exit(0)  # incomplete promote row — the explicit review-execute call covers it
subprocess.run(
    ["python3", rpw, "--cpr-id", str(cpr_id), "--promoted-to", str(promoted_to),
     "--review-tic", str(review_tic), "--status", str(d["status"])],
    check=False,
)
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
