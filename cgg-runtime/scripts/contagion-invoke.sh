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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${CGG_REPO_ROOT:-$(cd "$SCRIPT_DIR/../../../.." && pwd)}"
ENGINE="$REPO/autonomous_kernel/contagion_match_v0/runtime/contagion-engine.mjs"
CONTAGION_DIR="$REPO/audit-logs/contagion"
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

# 2.5 Discrimination-receipt step (bk-harmony-discrimination-receipt, ratified
#     /review 733 as the discrimination-axis ray on
#     ledger.md#can-it-eat-dataflow-liveness-predicate; fail-soft). Stamps the
#     emitted packet with last_change_tic + consecutive_identical_count over the
#     FULL retained history + the declared discriminating condition, so a
#     per-tic-consumed output can no longer read as a per-tic READING without
#     disclosing whether it has ever moved.
#
#     ⟜ RIDER — reproduced verbatim, /review 733 + the A3-732 standing rule ⟜
#     (carried on unbroken lines so the verbatim rider survives grep, unwrapped)
# RIDER (RULED /review 736): the discrimination receipt is READABLE as constancy observability — the read half RULED LIVE at /review 736 (Architect-ratified in-tic question set, recommended option verbatim). UNCHANGED by that ruling: the harmony/contagion disposition VALUES remain NON-CITABLE shaping (may_quote=false), and this receipt does not diagnose the constancy — the A3-732 cause stays deliberately unruled
# PRE-RULING RIDER (banked for lineage): no harmony/contagion disposition may be READ as discriminating until built AND ruled — your build is the first half; the ruling comes later at /review
# STANDING RULE: Standing rule since /review 736: the receipt FIELDS are readable and may be consumed as constancy observability; the disposition VALUES stay non-citable; the constancy CAUSE is not ruled — A3-732 rides separately.
#     The block therefore carries ratified:false and NO consumer reads it. This
#     step REPORTS constancy; it never diagnoses the cause (t589-frozen
#     coordinates / no TTL is the A3-732 investigation, deliberately unruled).
#     The write lives in the outer ring by kernel contract — the engine stays a
#     pure function (meta.pure:true / meta.writes:false).
echo "→ discrimination-receipt.py (receipt step, fail-soft; read half RULED LIVE /review 736; values stay non-citable)"
python3 "$SCRIPT_DIR/discrimination-receipt.py" --lane contagion --disposition "$DISPOSITION_PATH" || \
  echo "WARN contagion: discrimination receipt step failed — disposition stands without a receipt block (fail-soft)" >&2

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
# Discrimination summary on the glance-speed pointer (/review 736 — the read
# half RULED LIVE). Fail-soft: "not computed", never silence.
dsc = d.get("discrimination_receipt")
if isinstance(dsc, dict):
    current["discrimination"] = {
        "ratified": dsc.get("ratified"),
        "last_change_tic": dsc.get("last_change_tic"),
        "consecutive_identical_count": dsc.get("consecutive_identical_count"),
        "never_changed_in_retained_history": dsc.get("never_changed_in_retained_history"),
        "ruling": "/review 736 read-half LIVE; disposition values stay non-citable; A3-732 cause unruled",
    }
else:
    current["discrimination"] = {
        "status": "not computed",
        "note": "receipt step did not land on this emission (fail-soft) — absence of the block, not absence of constancy",
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
