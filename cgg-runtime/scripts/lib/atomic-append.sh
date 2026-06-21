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

atomic_append() {
  local target="$1"
  local content="$2"
  local lockfile="${target}.lock"

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

# Python-callable version for subprocess invocation
if [ "${1:-}" = "--append" ] && [ -n "${2:-}" ] && [ -n "${3:-}" ]; then
  atomic_append "$2" "$3"
fi
