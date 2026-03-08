#!/usr/bin/env bash
# cgg-doctor.sh — Human-facing CGG topology diagnostic
#
# Works BEFORE governance is initialized. Adaptive output:
#   Minimal: no markers at all
#   Site only: .ticzone exists, no audit logs
#   Full: .ticzone + audit logs + governance initialized
#
# Pure read-only — no mutations.
# NOT registered in plugin.json (runtime utility, not plugin component).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Resolve topology via rung_resolver.py ---
TOPO_JSON=""
if command -v python3 &>/dev/null; then
    TOPO_JSON=$(python3 "$SCRIPT_DIR/rung_resolver.py" --json 2>/dev/null || true)
fi

if [ -z "$TOPO_JSON" ]; then
    echo "CGG Doctor"
    echo "──────────"
    echo "ERROR: python3 or rung_resolver.py unavailable"
    exit 1
fi

CURRENT_RUNG=$(echo "$TOPO_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['current_rung'])" 2>/dev/null)

# Extract topology entries
get_topo_entry() {
    local rung="$1"
    echo "$TOPO_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)['topology'].get('$rung')
if d: print(d['path'] + '|' + d['name'])
else: print('(none)|')
" 2>/dev/null
}

# --- Header ---
echo "CGG Doctor"
echo "──────────"
echo "CURRENT_RUNG:  $CURRENT_RUNG"

# --- Minimal output (no markers) ---
if [ "$CURRENT_RUNG" = "global" ]; then
    echo "ZONE_ROOT:     (none)"
    echo "TOPOLOGY:      (none)"
    exit 0
fi

# --- Site+ output ---
SITE_ENTRY=$(get_topo_entry "site")
SITE_PATH="${SITE_ENTRY%%|*}"
SITE_NAME="${SITE_ENTRY##*|}"

ZONE_ROOT=""
if [ "$SITE_PATH" != "(none)" ]; then
    ZONE_ROOT="$SITE_PATH"
else
    # current_rung might be domain/estate/federation without a site
    for rung in domain estate federation; do
        entry=$(get_topo_entry "$rung")
        path="${entry%%|*}"
        if [ "$path" != "(none)" ]; then
            ZONE_ROOT="$path"
            break
        fi
    done
fi

echo "ZONE_ROOT:     ${ZONE_ROOT:-(none)}"
echo ""

# Topology chain (highest to lowest)
echo "Topology:"
for rung in federation estate domain site; do
    entry=$(get_topo_entry "$rung")
    path="${entry%%|*}"
    name="${entry##*|}"
    if [ "$path" = "(none)" ]; then
        printf "  %-13s (none)\n" "$rung:"
    else
        printf "  %-13s %s (%s)\n" "$rung:" "$path" "$name"
    fi
done

# --- Zone details (if .ticzone exists) ---
if [ -n "$ZONE_ROOT" ] && [ -f "$ZONE_ROOT/.ticzone" ]; then
    ZONE_NAME=$(python3 -c "
import json, sys
try:
    d = json.load(open('$ZONE_ROOT/.ticzone'))
    tz = d.get('tz', '(unknown)')
    name = d.get('name', '(unnamed)')
    print(name + '|' + tz)
except: print('(error)|(error)')
" 2>/dev/null)
    ZN="${ZONE_NAME%%|*}"
    ZTZ="${ZONE_NAME##*|}"
    echo ""
    echo "Zone:          $ZN ($ZTZ)"
fi

# --- Extended details (only if governance is initialized) ---
if [ -n "$ZONE_ROOT" ] && [ -d "$ZONE_ROOT/audit-logs" ]; then
    # Tic counter (from cached counter, not raw ledger scanning)
    TIC_COUNTER_FILE="$HOME/.claude/cgg-tic-counter.json"
    if [ -f "$TIC_COUNTER_FILE" ]; then
        TIC_COUNT=$(python3 -c "
import json
try:
    d = json.load(open('$TIC_COUNTER_FILE'))
    print(d.get('project_tic', d.get('tic_count', '?')))
except: print('?')
" 2>/dev/null)
        echo "Tic counter:   $TIC_COUNT"
    fi

    # Latest conformation for signal/CPR/mandate counts
    LATEST_CONF=""
    if [ -d "$ZONE_ROOT/audit-logs/conformations" ]; then
        LATEST_CONF=$(ls -1 "$ZONE_ROOT/audit-logs/conformations/"tic-*.json 2>/dev/null | sort -V | tail -1)
    fi

    if [ -n "$LATEST_CONF" ] && [ -f "$LATEST_CONF" ]; then
        CONF_DATA=$(python3 -c "
import json
try:
    d = json.load(open('$LATEST_CONF'))
    sigs = d.get('signals', {})
    active = sigs.get('active_count', sigs.get('active', '?'))
    cprs = d.get('cprs', {})
    pending = cprs.get('pending_count', cprs.get('pending', '?'))
    mandate = d.get('mandate', {})
    mstatus = mandate.get('status', '?')
    mtic = mandate.get('tic', '')
    if mtic: mstatus = mstatus + ' (tic-' + str(mtic) + ')'
    print(f'{active}|{pending}|{mstatus}')
except: print('?|?|?')
" 2>/dev/null)
        SIG_COUNT="${CONF_DATA%%|*}"
        REST="${CONF_DATA#*|}"
        CPR_COUNT="${REST%%|*}"
        MANDATE_STATUS="${REST##*|}"
        echo "Signals:       $SIG_COUNT active"
        echo "CPR queue:     $CPR_COUNT pending"
        echo "Mandate:       $MANDATE_STATUS"
    fi
fi
