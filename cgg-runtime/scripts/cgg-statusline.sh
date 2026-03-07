#!/usr/bin/env bash
# CGG Acoustic Statusline — read-only conformation radar for Claude Code.
#
# Pure observability surface. Reads canonical summaries only.
# Never reconstructs governance truth from raw event ledgers.
# Never writes to governance surfaces, emits signals, or participates in cadence.
#
# Receives JSON on stdin from Claude Code's statusLine runner.
# Outputs: nothing (OFF), one line (LITE), or two lines (FULL).
#
# Mode toggle: /tmp/cgg-sl-<project_hash>-mode (OFF|LITE|FULL, default LITE)
# Cache files: /tmp/cgg-sl-<project_hash>-{git,tic,conf}
#
# Data sources (allowed):
#   - Claude Code stdin JSON (model, cost, duration)
#   - ~/.claude/cgg-tic-counter.json (canonical tic scalar)
#   - audit-logs/conformations/tic-N.json (canonical conformation summary)
#   - git status (branch, dirty flag)
#
# Data sources (disallowed — never scan these):
#   - audit-logs/signals/*.jsonl
#   - audit-logs/cprs/queue.jsonl
#   - inline <!-- --> blocks in any file

set -euo pipefail

# --- Read stdin JSON ---
INPUT=$(cat)

CWD=$(printf '%s' "$INPUT" | jq -r '.workspace.current_dir // empty' 2>/dev/null)
MODEL=$(printf '%s' "$INPUT" | jq -r '.model.display_name // empty' 2>/dev/null)
PROJECT_DIR=$(printf '%s' "$INPUT" | jq -r '.workspace.project_dir // empty' 2>/dev/null)
COST=$(printf '%s' "$INPUT" | jq -r '.cost.total_cost_usd // empty' 2>/dev/null)
DURATION_MS=$(printf '%s' "$INPUT" | jq -r '.cost.total_duration_ms // empty' 2>/dev/null)

# Use project_dir for resolution; fall back to cwd
RESOLVE_DIR="${PROJECT_DIR:-$CWD}"
[ -z "$RESOLVE_DIR" ] && exit 0

# --- Project hash for namespacing ---
PROJ_HASH=$(printf '%s' "$RESOLVE_DIR" | md5 -q 2>/dev/null || printf '%s' "$RESOLVE_DIR" | md5sum 2>/dev/null | cut -c1-8)
PROJ_HASH="${PROJ_HASH:0:8}"
PROJ_NAME=$(basename "$RESOLVE_DIR")

CACHE_PREFIX="/tmp/cgg-sl-${PROJ_HASH}"
MODE_FILE="${CACHE_PREFIX}-mode"

# --- Mode resolution ---
MODE="LITE"
if [ -f "$MODE_FILE" ]; then
  MODE_RAW=$(cat "$MODE_FILE" 2>/dev/null || true)
  case "$MODE_RAW" in
    OFF|LITE|FULL) MODE="$MODE_RAW" ;;
  esac
fi

[ "$MODE" = "OFF" ] && exit 0

# --- Zone root resolution ---
# Walk up from RESOLVE_DIR to find .ticzone
ZONE_ROOT=""
d="$RESOLVE_DIR"
while [ "$d" != "/" ]; do
  if [ -f "$d/.ticzone" ]; then
    ZONE_ROOT="$d"
    break
  fi
  d=$(dirname "$d")
done
# Fallback: git root
if [ -z "$ZONE_ROOT" ]; then
  ZONE_ROOT=$(git -C "$RESOLVE_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$RESOLVE_DIR")
fi

# --- Cache helper ---
cache_fresh() {
  local cache_file="$1" max_age="$2"
  [ -f "$cache_file" ] || return 1
  local now file_mod age
  now=$(date +%s)
  file_mod=$(stat -f%m "$cache_file" 2>/dev/null || stat -c%Y "$cache_file" 2>/dev/null || echo 0)
  age=$((now - file_mod))
  [ "$age" -lt "$max_age" ]
}

# --- Git info (5s cache) ---
GIT_CACHE="${CACHE_PREFIX}-git"
if cache_fresh "$GIT_CACHE" 5; then
  GIT_INFO=$(cat "$GIT_CACHE")
else
  BRANCH=""
  DIRTY=""
  if git -C "$RESOLVE_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    BRANCH=$(git -C "$RESOLVE_DIR" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
      || git -C "$RESOLVE_DIR" --no-optional-locks rev-parse --short HEAD 2>/dev/null || true)
    if ! git -C "$RESOLVE_DIR" --no-optional-locks diff --quiet HEAD 2>/dev/null; then
      DIRTY="*"
    fi
  fi
  GIT_INFO="${BRANCH:+($BRANCH$DIRTY)}"
  printf '%s' "$GIT_INFO" > "$GIT_CACHE"
fi

# --- Tic count (30s cache) ---
# Source: canonical tic counter scalar. No JSONL scanning.
TIC_CACHE="${CACHE_PREFIX}-tic"
if cache_fresh "$TIC_CACHE" 30; then
  TIC_COUNT=$(cat "$TIC_CACHE")
else
  TIC_COUNT=""
  COUNTER_FILE="$HOME/.claude/cgg-tic-counter.json"
  if [ -f "$COUNTER_FILE" ]; then
    TIC_COUNT=$(jq -r '.count // empty' "$COUNTER_FILE" 2>/dev/null || true)
  fi
  [ -z "$TIC_COUNT" ] && TIC_COUNT="?"
  printf '%s' "$TIC_COUNT" > "$TIC_CACHE"
fi

# --- LITE mode output ---
LITE_LINE="[$MODEL] $PROJ_NAME ${GIT_INFO:+$GIT_INFO }| tic ${TIC_COUNT}"

if [ "$MODE" = "LITE" ]; then
  printf '%s' "$LITE_LINE"
  exit 0
fi

# --- FULL mode: conformation radar (30s cache) ---
# Source: latest canonical conformation snapshot only.
# Never scan raw ledgers. If no snapshot exists, degrade gracefully.
CONF_CACHE="${CACHE_PREFIX}-conf"
CONF_LINE=""
if cache_fresh "$CONF_CACHE" 30; then
  CONF_LINE=$(cat "$CONF_CACHE")
else
  CONF_STATUS=""
  SIG_COUNT=""
  WRN_COUNT=""
  CPR_COUNT=""

  # Find latest conformation snapshot by tic number
  CONF_DIR="$ZONE_ROOT/audit-logs/conformations"
  if [ -d "$CONF_DIR" ]; then
    LATEST_CONF=$(ls -1 "$CONF_DIR"/tic-*.json 2>/dev/null | awk -F'tic-' '{n=$2; sub(/\.json$/,"",n); print n"\t"$0}' | sort -n | tail -1 | cut -f2)
    if [ -n "$LATEST_CONF" ] && [ -f "$LATEST_CONF" ]; then
      # Support two conformation schemas:
      #   v1 (tic-209 style): .counts.active_signals / .counts.active_warrants / .counts.pending_cogprs
      #   v2 (tic-210 style): .signals.active[] / .warrants.active[] / .cprs.enrichment_eligible
      SIG_COUNT=$(jq -r '.counts.active_signals // empty' "$LATEST_CONF" 2>/dev/null || true)
      if [ -z "$SIG_COUNT" ]; then
        # v2: count non-dismissed/non-resolved signals
        SIG_COUNT=$(jq -r '[.signals.active // [] | .[] | select(.status != "dismissed" and .status != "resolved")] | length' "$LATEST_CONF" 2>/dev/null || echo "0")
      fi
      WRN_COUNT=$(jq -r '.counts.active_warrants // empty' "$LATEST_CONF" 2>/dev/null || true)
      if [ -z "$WRN_COUNT" ]; then
        WRN_COUNT=$(jq -r '.warrants.active // [] | length' "$LATEST_CONF" 2>/dev/null || echo "0")
      fi
      CPR_COUNT=$(jq -r '.counts.pending_cogprs // empty' "$LATEST_CONF" 2>/dev/null || true)
      if [ -z "$CPR_COUNT" ]; then
        CPR_COUNT=$(jq -r '.cprs.enrichment_eligible // 0' "$LATEST_CONF" 2>/dev/null || echo "0")
      fi
      # Conformation health: clean if no active signals/warrants
      if [ "${SIG_COUNT:-0}" = "0" ] && [ "${WRN_COUNT:-0}" = "0" ]; then
        CONF_STATUS="clean"
      else
        CONF_STATUS="active"
      fi
    fi
  fi

  # Cost + duration formatting
  COST_STR=""
  if [ -n "$COST" ] && [ "$COST" != "null" ]; then
    COST_STR=$(printf '$%.2f' "$COST" 2>/dev/null || true)
  fi
  DUR_STR=""
  if [ -n "$DURATION_MS" ] && [ "$DURATION_MS" != "null" ]; then
    DUR_TOTAL_SECS=${DURATION_MS%.*}
    DUR_TOTAL_SECS=$((DUR_TOTAL_SECS / 1000))
    if [ "${DUR_TOTAL_SECS:-0}" -ge 3600 ] 2>/dev/null; then
      DUR_STR="$((DUR_TOTAL_SECS / 3600))h$((DUR_TOTAL_SECS % 3600 / 60))m"
    elif [ "${DUR_TOTAL_SECS:-0}" -ge 60 ] 2>/dev/null; then
      DUR_STR="$((DUR_TOTAL_SECS / 60))m"
    else
      DUR_STR="${DUR_TOTAL_SECS}s"
    fi
  fi

  # Build conformation radar line
  # Fallback ladder: conformation summary > tic-only > model+project+branch
  if [ -n "$CONF_STATUS" ]; then
    CONF_LINE="conformation: ${CONF_STATUS} | sig ${SIG_COUNT} | wrn ${WRN_COUNT} | cpr ${CPR_COUNT}"
  fi
  [ -n "$COST_STR" ] && CONF_LINE="${CONF_LINE:+$CONF_LINE | }${COST_STR}"
  [ -n "$DUR_STR" ] && CONF_LINE="${CONF_LINE:+$CONF_LINE | }${DUR_STR}"

  printf '%s' "$CONF_LINE" > "$CONF_CACHE"
fi

# --- FULL mode output ---
if [ -n "$CONF_LINE" ]; then
  printf '%s\n%s' "$LITE_LINE" "$CONF_LINE"
else
  # No conformation data available — degrade to LITE
  printf '%s' "$LITE_LINE"
fi
