#!/usr/bin/env bash
# harmony-invoke.sh — Build federation-grounded input, run HarmonyEngine v0,
# write disposition packet to audit-logs/harmony/.
#
# Read-only of federation state. Writes only to audit-logs/harmony/.
# Honors v0 listening discipline: no governance mutation, no authority claim.
#
# Outputs:
#   audit-logs/harmony/input-tic-{N}.json
#   audit-logs/harmony/disposition-tic-{N}.json
#   audit-logs/harmony/disposition-current.json   (latest pointer; small JSON)
#   audit-logs/harmony/invocations.jsonl          (audit trail, append-only)
#
# Usage:
#   harmony-invoke.sh                # uses default posture/mode
#   POSTURE=ENG/META MODE=LITE harmony-invoke.sh

set -euo pipefail

REPO="/Users/breydentaylor/canonical"
ENGINE="$REPO/autonomous_kernel/harmony_engine_v0/runtime/harmony-engine.mjs"
HARMONY_DIR="$REPO/audit-logs/harmony"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_BUILDER="$SCRIPT_DIR/harmony-input-builder.py"

POSTURE="${POSTURE:-${CGG_POSTURE:-OPS/DIRECT}}"
MODE="${MODE:-${CGG_STATUSLINE_MODE:-FULL}}"

mkdir -p "$HARMONY_DIR"

# 1. Build input from federation state
echo "→ harmony-input-builder.py posture=$POSTURE mode=$MODE"
INPUT_PATH=$(CGG_POSTURE="$POSTURE" CGG_STATUSLINE_MODE="$MODE" \
  python3 "$INPUT_BUILDER" --print)
[ -f "$INPUT_PATH" ] || { echo "ERR: input not written at $INPUT_PATH" >&2; exit 1; }

TIC=$(python3 -c "import json,sys; print(json.load(open('$INPUT_PATH'))['terrainSlice']['tic'])")
DISPOSITION_PATH="$HARMONY_DIR/disposition-tic-$TIC.json"

# 2. Invoke engine via node — read input from stdin, write disposition packet
node --input-type=module -e "
  import { runHarmonyEngine } from '$ENGINE';
  import { readFileSync, writeFileSync } from 'node:fs';
  const input = JSON.parse(readFileSync('$INPUT_PATH', 'utf8'));
  const out = runHarmonyEngine(input);
  writeFileSync('$DISPOSITION_PATH', JSON.stringify(out, null, 2));
  console.log('disposition:', out.disposition?.stance, '|', 'meaning:', out.acousticSignature?.meaningState ?? 'n/a');
" || { echo "ERR: engine invocation failed" >&2; exit 1; }

# 3. Update disposition-current.json (compact pointer for statusline)
python3 <<PY
import json, time, pathlib
p = pathlib.Path("$DISPOSITION_PATH")
d = json.loads(p.read_text())
disp = d.get("disposition", {})
acoustic = d.get("acousticSignature", {}) or d.get("ecotone", {})
meaning = (acoustic.get("meaningState")
           or d.get("ecotone", {}).get("meaningState")
           or d.get("meaningState")
           or "unknown")
snr = (acoustic.get("snr")
       or d.get("acousticSignature", {}).get("snr")
       or d.get("snr"))
current = {
    "tic": $TIC,
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "stance": disp.get("stance", "idle"),
    "meaning_state": meaning,
    "snr": round(float(snr or 0.0), 3),
    "one_way_injection": disp.get("oneWayInjection", ""),
    "unresolved_count": len(disp.get("unresolvedDissonance", []) or []),
    "source_disposition": str(p.relative_to(pathlib.Path("$REPO"))),
    "posture": "$POSTURE",
    "mode": "$MODE",
}
out = pathlib.Path("$HARMONY_DIR/disposition-current.json")
out.write_text(json.dumps(current, indent=2) + "\n")
print(f"current pointer: {out}")
PY

# 4. Append audit log entry
python3 <<PY
import json, time, pathlib
log = pathlib.Path("$HARMONY_DIR/invocations.jsonl")
entry = {
    "tic": $TIC,
    "invoked_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "posture": "$POSTURE",
    "mode": "$MODE",
    "input": str(pathlib.Path("$INPUT_PATH").relative_to(pathlib.Path("$REPO"))),
    "output": str(pathlib.Path("$DISPOSITION_PATH").relative_to(pathlib.Path("$REPO"))),
}
with log.open("a") as f:
    f.write(json.dumps(entry) + "\n")
print(f"audit logged: {log}")
PY

echo "✓ harmony invocation complete (tic=$TIC posture=$POSTURE mode=$MODE)"
