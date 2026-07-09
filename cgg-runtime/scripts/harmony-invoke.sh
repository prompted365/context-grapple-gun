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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${CGG_REPO_ROOT:-$(cd "$SCRIPT_DIR/../../../.." && pwd)}"
ENGINE="$REPO/autonomous_kernel/harmony_engine_v0/runtime/harmony-engine.mjs"
HARMONY_DIR="$REPO/audit-logs/harmony"
INPUT_BUILDER="$SCRIPT_DIR/harmony-input-builder.py"

POSTURE="${POSTURE:-${CGG_POSTURE:-OPS/DIRECT}}"
MODE="${MODE:-${CGG_STATUSLINE_MODE:-FULL}}"

mkdir -p "$HARMONY_DIR"

# 0. Braid step (cable BR5, fail-soft): refresh the braid packet BEFORE input
#    assembly so the builder can ingest a current-tic braid. Any failure here
#    leaves the legacy harmony lane fully intact (braid-invoke is itself
#    fail-soft and exits 0; the guard below is belt-and-suspenders).
echo "→ braid-invoke.sh (braid step, fail-soft)"
bash "$SCRIPT_DIR/braid-invoke.sh" || \
  echo "WARN harmony: braid step failed — continuing without braid (fail-soft)" >&2

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

# 2.5 Voice step (cable BR5, fail-soft): bounded-morphism ambient voice
#     proposer — constrained LLM line, validator-gated, honest template
#     fallback. Writes the voice object INTO the disposition file (additive).
#     HARMONY_VOICE=off skips the LLM inside the script. Any failure leaves
#     the disposition standing without a voice object (legacy-equivalent).
echo "→ harmony-voice.py (voice step, fail-soft)"
python3 "$SCRIPT_DIR/harmony-voice.py" --disposition "$DISPOSITION_PATH" || \
  echo "WARN harmony: voice step failed — disposition stands without voice (fail-soft)" >&2

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
# Cable BR5 additions (fail-soft): ambient voice from the disposition's
# additive voice object; braid_tic from the braid current-pointer (null if
# either surface is absent — honest nulls, never fabricated).
voice = d.get("voice") or {}
braid_tic = None
try:
    braid_ptr = pathlib.Path("$REPO") / "audit-logs" / "braid" / "current-pointer.json"
    braid_tic = json.loads(braid_ptr.read_text()).get("tic")
except Exception:
    braid_tic = None
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
    "ambient_voice": voice.get("ambient_voice"),
    "voice_source": voice.get("voice_source"),
    "braid_tic": braid_tic,
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
