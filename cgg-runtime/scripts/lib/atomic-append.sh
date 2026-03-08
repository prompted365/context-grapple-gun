#!/usr/bin/env bash
# atomic-append.sh — JSONL-safe atomic append using flock
# Source this file, then call: atomic_append "$TARGET_FILE" "$JSON_LINE"
#
# Uses flock for mutual exclusion across concurrent processes.
# Falls back to direct append if flock is unavailable (with warning).
# Enforces single-line invariant: multi-line JSON is compacted before append.

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
}

# Python-callable version for subprocess invocation
if [ "${1:-}" = "--append" ] && [ -n "${2:-}" ] && [ -n "${3:-}" ]; then
  atomic_append "$2" "$3"
fi
