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
# Strip vendor-appended " (1M context)" — redundant once ctx% is visible
MODEL="${MODEL% (1M context)}"
PROJECT_DIR=$(printf '%s' "$INPUT" | jq -r '.workspace.project_dir // empty' 2>/dev/null)
COST=$(printf '%s' "$INPUT" | jq -r '.cost.total_cost_usd // empty' 2>/dev/null)
DURATION_MS=$(printf '%s' "$INPUT" | jq -r '.cost.total_duration_ms // empty' 2>/dev/null)
CTX_PCT=$(printf '%s' "$INPUT" | jq -r '.context_window.used_percentage // empty' 2>/dev/null)

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

# --- ANSI color palette (Persian fire) ---
C_RESET='\033[0m'
C_AMBER='\033[38;5;214m'    # amber/gold — model, tic
C_FLAME='\033[38;5;202m'    # orange-red — project name
C_EMBER='\033[38;5;167m'    # warm red — branch
C_ASH='\033[38;5;245m'      # dim gray — separators, duration
C_GREEN='\033[32m'           # green — clean/zero counts
C_RED='\033[31m'             # red — active/nonzero warnings
C_YELLOW='\033[33m'          # yellow — nonzero cprs, cost
# Background colors for conformation status badge
C_BG_GREEN='\033[42;30m'    # green bg, black text
C_BG_RED='\033[41;97m'      # red bg, bright white text

# --- LITE mode output ---
# Context percentage — color-coded by used: green <50, yellow 50-80, red >80
CTX_PART=""
if [ -n "$CTX_PCT" ] && [ "$CTX_PCT" != "null" ]; then
  CTX_INT=${CTX_PCT%.*}
  if [ "${CTX_INT:-0}" -ge 80 ] 2>/dev/null; then
    CTX_COLOR="$C_RED"
  elif [ "${CTX_INT:-0}" -ge 50 ] 2>/dev/null; then
    CTX_COLOR="$C_YELLOW"
  else
    CTX_COLOR="$C_GREEN"
  fi
  CTX_PART=" ${C_ASH}·${C_RESET} ${CTX_COLOR}ctx ${CTX_INT}%${C_RESET}"
fi

LITE_LINE="${C_AMBER}[${MODEL}]${C_RESET} ${C_FLAME}${PROJ_NAME}${C_RESET} ${C_EMBER}${GIT_INFO:+$GIT_INFO }${C_RESET}${C_ASH}|${C_RESET} ${C_AMBER}tic ${TIC_COUNT}${C_RESET}${CTX_PART}"

if [ "$MODE" = "LITE" ]; then
  printf '%b' "$LITE_LINE"
  exit 0
fi

# --- FULL mode: telos radar (30s cache) ---
# Sources (read-only):
#   - latest conformation snapshot (signals, warrants, CPR pipeline distribution)
#   - audit-logs/harmony/disposition-current.json (theory-of-mind injection)
# Never scan raw ledgers. If a source is missing, degrade gracefully.
CONF_CACHE="${CACHE_PREFIX}-conf"
CONF_LINE=""
if cache_fresh "$CONF_CACHE" 30; then
  CONF_LINE=$(cat "$CONF_CACHE")
else
  CONF_STATUS=""
  SIG_DOTS=""           # one ● per active signal, colored by volume tier
  WRN_COUNT=""          # warrants stay numeric; boundaries are not "ambient"
  PIPE_E=""; PIPE_N=""; PIPE_R=""  # extracted ▸ enrichment_needed ▸ enrichment_eligible
  HARMONY_PART=""

  # Find latest conformation snapshot by tic number
  CONF_DIR="$ZONE_ROOT/audit-logs/conformations"
  if [ -d "$CONF_DIR" ]; then
    LATEST_CONF=$(ls -1 "$CONF_DIR"/tic-*.json 2>/dev/null | awk -F'tic-' '{n=$2; sub(/\.json$/,"",n); print n"\t"$0}' | sort -n | tail -1 | cut -f2)
    if [ -n "$LATEST_CONF" ] && [ -f "$LATEST_CONF" ]; then
      # Severity dots — one per active signal, colored by volume tier
      # vol >= 40: red, 20-39: yellow, < 20: green
      SIG_DOTS=$(jq -r '
        ([.active_signals // .signals.active // [] | .[] | select(.status != "dismissed" and .status != "resolved") | (.volume // 0)] // [])
        | map(if . >= 40 then "R" elif . >= 20 then "Y" else "G" end)
        | join("")
      ' "$LATEST_CONF" 2>/dev/null || echo "")

      WRN_COUNT=$(jq -r '(.active_warrants // .warrants.active // []) | length' "$LATEST_CONF" 2>/dev/null || echo "0")

      # Pipeline distribution from pending_cogprs list
      PIPE_E=$(jq -r '[.pending_cogprs // [] | .[] | select(.status == "extracted")] | length' "$LATEST_CONF" 2>/dev/null || echo "0")
      PIPE_N=$(jq -r '[.pending_cogprs // [] | .[] | select(.status == "enrichment_needed")] | length' "$LATEST_CONF" 2>/dev/null || echo "0")
      PIPE_R=$(jq -r '[.pending_cogprs // [] | .[] | select(.status == "enrichment_eligible")] | length' "$LATEST_CONF" 2>/dev/null || echo "0")

      # Conformation health: clean if no signals AND no warrants
      SIG_LEN=${#SIG_DOTS}
      if [ "${SIG_LEN}" = "0" ] && [ "${WRN_COUNT:-0}" = "0" ]; then
        CONF_STATUS="clean"
      else
        CONF_STATUS="active"
      fi
    fi
  fi

  # Harmony disposition (theory-of-mind injection)
  HARMONY_FILE="$ZONE_ROOT/audit-logs/harmony/disposition-current.json"
  if [ -f "$HARMONY_FILE" ]; then
    H_TIC=$(jq -r '.tic // 0' "$HARMONY_FILE" 2>/dev/null)
    H_STATE=$(jq -r '.meaning_state // "unknown"' "$HARMONY_FILE" 2>/dev/null)
    H_SNR=$(jq -r '.snr // 0' "$HARMONY_FILE" 2>/dev/null)
    H_STANCE=$(jq -r '.stance // "idle"' "$HARMONY_FILE" 2>/dev/null)
    # Compress stance: "hold-open-with-boundary" → "hold-open"
    H_STANCE_SHORT=$(printf '%s' "$H_STANCE" | sed 's/-with-boundary//' | cut -c1-12)
    # SNR as .NN (drop leading 0, two decimals)
    H_SNR_SHORT=$(printf '%s' "$H_SNR" | awk '{printf ".%02d", int(($1 + 0.005) * 100)}' 2>/dev/null || printf ".??")
    # Freshness: current tic vs disposition tic
    H_AGE=$(( ${TIC_COUNT:-0} - ${H_TIC:-0} ))
    [ "$H_AGE" -lt 0 ] && H_AGE=0
    # Color by meaning_state
    case "$H_STATE" in
      held|clear|coherent) H_COLOR="$C_GREEN" ;;
      strained|tense)      H_COLOR="$C_YELLOW" ;;
      dissonant|broken)    H_COLOR="$C_RED" ;;
      *)                   H_COLOR="$C_ASH" ;;
    esac
    if [ "$H_AGE" -le 0 ]; then
      H_GLYPH="⊙"; H_FRESH=""
    elif [ "$H_AGE" -le 3 ]; then
      H_GLYPH="◐"; H_FRESH=" t-${H_AGE}"
    else
      H_GLYPH="·"; H_FRESH=" stale"
    fi
    HARMONY_PART="${H_COLOR}${H_GLYPH} ${H_STATE} ${H_SNR_SHORT} ${H_STANCE_SHORT}${H_FRESH}${C_RESET}"
  fi

  # Build conformation radar line with colors
  # Fallback ladder: conformation summary > tic-only > model+project+branch
  if [ -n "$CONF_STATUS" ]; then
    # Background-color badge for conformation status
    if [ "$CONF_STATUS" = "clean" ]; then
      C_BADGE="$C_BG_GREEN"
    else
      C_BADGE="$C_BG_RED"
    fi
    # Render severity dots with per-tier color
    DOTS_RENDERED=""
    i=0
    while [ $i -lt ${#SIG_DOTS} ]; do
      ch="${SIG_DOTS:$i:1}"
      case "$ch" in
        R) DOTS_RENDERED="${DOTS_RENDERED}${C_RED}●${C_RESET}" ;;
        Y) DOTS_RENDERED="${DOTS_RENDERED}${C_YELLOW}●${C_RESET}" ;;
        G) DOTS_RENDERED="${DOTS_RENDERED}${C_GREEN}●${C_RESET}" ;;
      esac
      i=$((i+1))
    done
    [ -z "$DOTS_RENDERED" ] && DOTS_RENDERED="${C_GREEN}○${C_RESET}"

    # Pipeline gauge: extracted ▸ enrichment_needed ▸ enrichment_eligible
    # Right-most (eligible) is docket-ready — color it green
    PIPE_GAUGE="${C_ASH}pipe ${PIPE_E}▸${PIPE_N}▸${C_RESET}${C_GREEN}${PIPE_R}${C_RESET}"

    # Warrant indicator: only show if nonzero (otherwise omit — boundary, not ambient)
    WRN_PART=""
    if [ "${WRN_COUNT:-0}" != "0" ]; then
      WRN_PART=" ${C_ASH}|${C_RESET} ${C_RED}wrn ${WRN_COUNT}${C_RESET}"
    fi

    CONF_LINE="${C_BADGE} ${CONF_STATUS} ${C_RESET} ${PIPE_GAUGE} ${C_ASH}|${C_RESET} sig ${DOTS_RENDERED}${WRN_PART}"
  fi

  # Append harmony disposition (theory-of-mind injection)
  if [ -n "$HARMONY_PART" ]; then
    CONF_LINE="${CONF_LINE:+$CONF_LINE ${C_ASH}|${C_RESET} }${HARMONY_PART}"
  fi

  printf '%s' "$CONF_LINE" > "$CONF_CACHE"
fi

# --- FULL mode output ---
if [ -n "$CONF_LINE" ]; then
  printf '%b\n%b' "$LITE_LINE" "$CONF_LINE"
else
  # No conformation data available — degrade to LITE
  printf '%b' "$LITE_LINE"
fi
