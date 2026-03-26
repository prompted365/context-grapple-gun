#!/usr/bin/env bash
# CGG v4 — PostToolUse micro-scan hook
# Lightweight governance notice between cadence boundaries.
# Fires after Write/Edit tool completions. Must complete in < 2 seconds.
#
# Bounded actions only:
#   - Record signal seed if governance file was modified
#   - Stage tiny finding for Mogul's next cycle
#   - Silent unless warranted
#
# Hard limits:
#   - No promotion, no law inscription, no full assessor
#   - No ladder audit, no review logic
#   - Writes to file only (no stdout bloat)
#   - Must not exceed 2 second runtime

# Read stdin (tool result JSON) — we need the file path
INPUT=$(cat)

# Wire cutter — emergency kill switch
[ -f ~/.claude/wire-cutter.sh ] && source ~/.claude/wire-cutter.sh && wire_check microscan

# Plugin-root anchor: CLAUDE_PLUGIN_ROOT is only set for plugin-registered hooks.
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

# ============================================================================
# Root Anchoring
# ============================================================================

resolve_zone_root() {
  local dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
  while [ "$dir" != "/" ]; do
    [ -f "$dir/.ticzone" ] && echo "$dir" && return 0
    dir=$(dirname "$dir")
  done
  git rev-parse --show-toplevel 2>/dev/null && return 0
  echo "$(pwd)"
}
ZONE_ROOT=$(resolve_zone_root)

# ============================================================================
# Extract modified file path from tool input
# ============================================================================

# Try to extract file_path from the JSON input
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # PostToolUse provides tool_input with file_path
    ti = d.get('tool_input', {})
    if isinstance(ti, str):
        ti = json.loads(ti)
    print(ti.get('file_path', ''))
except:
    print('')
" 2>/dev/null)

# Fast exit: no file path or not a governance-relevant file
[ -z "$FILE_PATH" ] && exit 0

# ============================================================================
# Governance file detection
# ============================================================================

BASENAME=$(basename "$FILE_PATH")
DIRNAME=$(dirname "$FILE_PATH")

IS_GOVERNANCE=0

# CLAUDE.md or MEMORY.md modifications
case "$BASENAME" in
  CLAUDE.md|MEMORY.md)
    IS_GOVERNANCE=1
    FINDING_TYPE="governance_file_modified"
    ;;
  SKILL.md)
    IS_GOVERNANCE=1
    FINDING_TYPE="skill_surface_modified"
    ;;
  *.jsonl)
    # Check if it's in audit-logs
    case "$FILE_PATH" in
      *audit-logs/signals*|*audit-logs/cprs*|*audit-logs/tics*)
        IS_GOVERNANCE=1
        FINDING_TYPE="audit_surface_modified"
        ;;
    esac
    ;;
esac

# Check if it's an agent prompt
case "$FILE_PATH" in
  *.claude/agents/*.md|*cgg-runtime/agents/*.md)
    IS_GOVERNANCE=1
    FINDING_TYPE="agent_prompt_modified"
    ;;
esac

# Check if it's a hook
case "$FILE_PATH" in
  *.claude/hooks/*.sh|*cgg-runtime/hooks/*.sh)
    IS_GOVERNANCE=1
    FINDING_TYPE="hook_modified"
    ;;
esac

# Fast exit: not a governance file
[ "$IS_GOVERNANCE" -eq 0 ] && exit 0

# ============================================================================
# Stage finding (append to micro-scan staging file)
# ============================================================================

STAGING_DIR="$ZONE_ROOT/audit-logs"
STAGING_FILE="$STAGING_DIR/.microscan-staging.jsonl"

# Ensure directory exists
mkdir -p "$STAGING_DIR" 2>/dev/null

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Resolve rung for topology context (best-effort, must not block on failure)
SCRIPTS_DIR=""
for candidate in \
  "$ZONE_ROOT/vendor/context-grapple-gun/cgg-runtime/scripts" \
  "${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/cgg-runtime/scripts}" \
  "$HOME/.claude/cgg/cgg-runtime/scripts"; do
  [ -n "$candidate" ] && [ -f "$candidate/rung_resolver.py" ] && SCRIPTS_DIR="$candidate" && break
done

BIRTH_RUNG="unknown"
if [ -n "$SCRIPTS_DIR" ]; then
  BIRTH_RUNG=$(python3 "$SCRIPTS_DIR/rung_resolver.py" --json --start "$ZONE_ROOT" 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('current_rung','unknown'))" 2>/dev/null) || BIRTH_RUNG="unknown"
fi

# Append finding — lightweight JSON, no signal emission
MICROSCAN_JSON=$(printf '{"type":"microscan","finding":"%s","file":"%s","birth_rung":"%s","timestamp":"%s"}' \
  "$FINDING_TYPE" "$FILE_PATH" "$BIRTH_RUNG" "$TIMESTAMP")
if type atomic_append &>/dev/null; then
  atomic_append "$STAGING_FILE" "$MICROSCAN_JSON"
else
  printf '%s\n' "$MICROSCAN_JSON" >> "$STAGING_FILE" 2>/dev/null
fi

# ============================================================================
# Emit signal seed ONLY for prompt-stack hazards
# ============================================================================

# If a governance file was modified outside of a /cadence or /review context,
# it may indicate prompt-stack drift. Check if the modification is to an
# installed runtime surface that has a canonical source.

EMIT_SIGNAL=0

case "$FINDING_TYPE" in
  skill_surface_modified|agent_prompt_modified|hook_modified)
    # Check if this is an installed copy (not canonical)
    case "$FILE_PATH" in
      */.claude/skills/*|*/.claude/agents/*|*/.claude/hooks/*)
        # Only emit if canonical counterpart exists AND content now differs.
        # This prevents noise from intentional syncs or repairs.
        CANONICAL=""
        CGG_RT=""
        # Plugin root first (works for marketplace + submodule installs),
        # then submodule fallback, then global fallback
        CGG_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
        for candidate in \
          "${CGG_PLUGIN_ROOT:+$CGG_PLUGIN_ROOT/cgg-runtime}" \
          "$ZONE_ROOT/vendor/context-grapple-gun/cgg-runtime" \
          "$HOME/.claude/cgg/cgg-runtime"; do
          [ -n "$candidate" ] && [ -d "$candidate" ] && CGG_RT="$candidate" && break
        done

        if [ -n "$CGG_RT" ]; then
          # Map installed path back to canonical
          case "$FILE_PATH" in
            */.claude/skills/*)
              REL_SKILL=$(echo "$FILE_PATH" | sed 's|.*/.claude/skills/||')
              CANONICAL="$CGG_RT/skills/$REL_SKILL"
              ;;
            */.claude/agents/*)
              REL_AGENT=$(basename "$FILE_PATH")
              CANONICAL="$CGG_RT/agents/$REL_AGENT"
              ;;
            */.claude/hooks/*)
              REL_HOOK=$(basename "$FILE_PATH")
              CANONICAL="$CGG_RT/hooks/$REL_HOOK"
              ;;
          esac

          if [ -n "$CANONICAL" ] && [ -f "$CANONICAL" ]; then
            # Compare content hashes — only emit if they actually differ
            HASH_INSTALLED=$(shasum -a 256 "$FILE_PATH" 2>/dev/null | cut -d' ' -f1)
            HASH_CANONICAL=$(shasum -a 256 "$CANONICAL" 2>/dev/null | cut -d' ' -f1)
            if [ "$HASH_INSTALLED" != "$HASH_CANONICAL" ]; then
              EMIT_SIGNAL=1
            fi
          fi
        fi
        ;;
    esac
    ;;
esac

if [ "$EMIT_SIGNAL" -eq 1 ]; then
  SIGNAL_DIR="$ZONE_ROOT/audit-logs/signals"
  mkdir -p "$SIGNAL_DIR" 2>/dev/null
  DATE_STR=$(date -u +"%Y-%m-%d")
  SIGNAL_FILE="$SIGNAL_DIR/$DATE_STR.jsonl"

  SIGNAL_ID="sig_${TIMESTAMP}_microscan_drift_${BASENAME}"

  SIGNAL_JSON=$(printf '{"type":"signal","id":"%s","kind":"TENSION","band":"COGNITIVE","status":"active","volume":30,"max_volume":100,"tick_count":0,"subsystem":"cgg","source":"posttool-microscan.sh","source_date":"%s","created_at":"%s","birth_rung":"%s","payload":{"summary":"Installed runtime surface drifted from canonical: %s","file":"%s"},"escalation":{"warrant_threshold":70},"origin":"deterministic"}' \
    "$SIGNAL_ID" "$DATE_STR" "$TIMESTAMP" "$BIRTH_RUNG" "$BASENAME" "$FILE_PATH")
  if type atomic_append &>/dev/null; then
    atomic_append "$SIGNAL_FILE" "$SIGNAL_JSON"
  else
    printf '%s\n' "$SIGNAL_JSON" >> "$SIGNAL_FILE" 2>/dev/null
  fi
fi

exit 0
