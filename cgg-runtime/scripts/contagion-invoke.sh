#!/usr/bin/env bash
# contagion-invoke.sh — Build federation-grounded input, run ContagionMatch v0,
# write disposition packet to audit-logs/contagion/.
#
# Sibling of harmony-invoke.sh. Clone of the proven cross-rung synchronous-data
# invocation seam: build input -> reach UPWARD to the kernel via `node -e` -> write
# the disposition packet. This is synchronous DATA invocation, NOT authority
# delegation (autonomous_kernel/CLAUDE.md "Cross-Rung Invocation Pattern").
#
# Read-only of federation state. Writes only to audit-logs/contagion/.
# Honors the contagion kernel authority clause: no governance mutation, no
# authority claim. The match retrieves by CONFORMATION-PROXIMITY (not text) and
# emits a NON-CITABLE shaping packet.
#
# Outputs:
#   audit-logs/contagion/input-tic-{N}.json
#   audit-logs/contagion/disposition-tic-{N}.json
#   audit-logs/contagion/current-pointer.json   (latest pointer; small JSON)
#   audit-logs/contagion/invocations.jsonl       (audit trail, append-only)
#
# Usage:
#   contagion-invoke.sh                # uses conformation posture
#   POSTURE=ENG/META contagion-invoke.sh

set -euo pipefail

REPO="/Users/breydentaylor/canonical"
ENGINE="$REPO/autonomous_kernel/contagion_match_v0/runtime/contagion-engine.mjs"
CONTAGION_DIR="$REPO/audit-logs/contagion"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_BUILDER="$SCRIPT_DIR/contagion-input-builder.py"

POSTURE="${POSTURE:-${CGG_POSTURE:-}}"

mkdir -p "$CONTAGION_DIR"

# 1. Build input from federation state (conformation + learned coordinates)
echo "→ contagion-input-builder.py posture=${POSTURE:-<conformation>}"
INPUT_PATH=$(CGG_POSTURE="${POSTURE:-}" python3 "$INPUT_BUILDER" --print)
[ -f "$INPUT_PATH" ] || { echo "ERR: input not written at $INPUT_PATH" >&2; exit 1; }

TIC=$(python3 -c "import json; print(json.load(open('$INPUT_PATH'))['tic'])")
DISPOSITION_PATH="$CONTAGION_DIR/disposition-tic-$TIC.json"

# 2. Invoke engine via node — read input, write disposition packet (kernel reach-up)
node --input-type=module -e "
  import { runContagionEngine } from '$ENGINE';
  import { readFileSync, writeFileSync } from 'node:fs';
  const input = JSON.parse(readFileSync('$INPUT_PATH', 'utf8'));
  const out = runContagionEngine(input);
  writeFileSync('$DISPOSITION_PATH', JSON.stringify(out, null, 2));
  console.log('contagion:', out.meaningState, '|', 'nearest:', out.nearest.length, '|', 'epitaph:', out.nearest_epitaph?.kind ?? 'none');
" || { echo "ERR: engine invocation failed" >&2; exit 1; }

# 3. Update current-pointer.json (compact latest pointer)
python3 <<PY
import json, time, pathlib
p = pathlib.Path("$DISPOSITION_PATH")
d = json.loads(p.read_text())
disp = d.get("disposition", {})
current = {
    "tic": $TIC,
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "meaning_state": d.get("meaningState", "unknown"),
    "stance": disp.get("stance", ""),
    "one_way_injection": disp.get("oneWayInjection", ""),
    "nearest_count": len(d.get("nearest", []) or []),
    "nearest_epitaph_kind": (d.get("nearest_epitaph", {}) or {}).get("kind"),
    "non_citable": d.get("non_citable", True),
    "is_disposition_not_verdict": d.get("is_disposition_not_verdict", True),
    "source_disposition": str(p.relative_to(pathlib.Path("$REPO"))),
    "posture": d.get("disposition", {}).get("posture", "${POSTURE:-}"),
}
out = pathlib.Path("$CONTAGION_DIR/current-pointer.json")
out.write_text(json.dumps(current, indent=2) + "\n")
print(f"current pointer: {out}")
PY

# 4. Append audit log entry
python3 <<PY
import json, time, pathlib
log = pathlib.Path("$CONTAGION_DIR/invocations.jsonl")
entry = {
    "tic": $TIC,
    "invoked_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "posture": "${POSTURE:-}",
    "input": str(pathlib.Path("$INPUT_PATH").relative_to(pathlib.Path("$REPO"))),
    "output": str(pathlib.Path("$DISPOSITION_PATH").relative_to(pathlib.Path("$REPO"))),
}
with log.open("a") as f:
    f.write(json.dumps(entry) + "\n")
print(f"audit logged: {log}")
PY

echo "✓ contagion match invocation complete (tic=$TIC)"
