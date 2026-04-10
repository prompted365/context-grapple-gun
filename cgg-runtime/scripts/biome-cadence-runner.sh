#!/usr/bin/env bash
# biome-cadence-runner.sh — Advance biome simulation and trigger dependent engines.
#
# Called per-tic by mogul cadence or standalone. Runs the biome engine,
# then triggers standing recalculation and economy bridge observation.
#
# Usage:
#   bash biome-cadence-runner.sh                    # advance 1 cycle
#   bash biome-cadence-runner.sh --cycles 5         # advance 5 cycles
#   bash biome-cadence-runner.sh --seed --visitors 8  # seed fresh biome
#
# Dependencies:
#   biome-engine.py, standing-engine.py, economy-bridge-adapter.py
#
# Trigger routing: This script is the cadence trigger for:
#   - biome.cycle (advance simulation)
#   - standing.recalculate (after act boundary)
#   - economy.observe (per-tic economy bridge)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

# ── Parse args ──
CYCLES=1
SEED=false
VISITORS=8

while [[ $# -gt 0 ]]; do
    case $1 in
        --cycles) CYCLES="$2"; shift 2 ;;
        --seed) SEED=true; shift ;;
        --visitors) VISITORS="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

# ── Seed if requested ──
if $SEED; then
    echo "[biome-cadence] Seeding biome with $VISITORS visitors..."
    $PYTHON "$SCRIPT_DIR/biome-engine.py" --seed --visitors "$VISITORS"
fi

# ── Advance biome cycles ──
echo "[biome-cadence] Advancing $CYCLES cycle(s)..."
BIOME_OUTPUT=$($PYTHON "$SCRIPT_DIR/biome-engine.py" --cycle 2>&1) || {
    echo "[biome-cadence] ERROR: biome-engine.py failed" >&2
    echo "$BIOME_OUTPUT" >&2
    exit 1
}
echo "$BIOME_OUTPUT"

# ── Check for act boundary ──
ACT_BOUNDARY=$(echo "$BIOME_OUTPUT" | grep -c "ACT_BOUNDARY" || true)

if [[ "$ACT_BOUNDARY" -gt 0 ]]; then
    echo "[biome-cadence] Act boundary detected — triggering standing recalculation..."

    # Get all active visitor entity IDs from organisms.json
    ZONE_ROOT=$($PYTHON -c "
import sys, os
sys.path.insert(0, '$SCRIPT_DIR')
from zone_root import resolve_zone_root
print(resolve_zone_root('$SCRIPT_DIR'))
")
    ORGANISMS="$ZONE_ROOT/audit-logs/biome/state/organisms.json"

    if [[ -f "$ORGANISMS" ]]; then
        # Extract entity IDs and recalculate trust_score for each
        $PYTHON -c "
import json, subprocess, sys
with open('$ORGANISMS') as f:
    data = json.load(f)
visitors = data.get('visitors', [])
for v in visitors:
    eid = v.get('entity_id', '')
    if eid.startswith('ent_visitor_'):
        result = subprocess.run(
            [sys.executable, '$SCRIPT_DIR/standing-engine.py', '--compute-trust', eid],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f'[standing] {eid}: {result.stdout.strip()}')
        else:
            print(f'[standing] {eid}: ERROR - {result.stderr.strip()}', file=sys.stderr)
"
    fi
fi

# ── Economy bridge observation (every cycle) ──
echo "[biome-cadence] Running economy bridge observation..."
$PYTHON "$SCRIPT_DIR/economy-bridge-adapter.py" --observe 2>&1 || {
    echo "[biome-cadence] WARN: economy-bridge-adapter.py --observe failed (non-fatal)" >&2
}

echo "[biome-cadence] Cycle complete."
