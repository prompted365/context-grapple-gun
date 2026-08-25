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

# 0-pre. Chain clock resolution (bk-braid-tic-clock-inheritance, /review 684
#    ratified fix-site): resolve THIS chain's tic ONCE, from the same authority
#    harmony-input-builder uses (current_tic: counter file, conformation
#    fallback), and INHERIT it down to the braid sub-step. The braid's tic
#    identity was order-dependent on the economy pointer — the lag direction
#    was set by scheduling, not content — so inheritance replaces the race and
#    the builder declares any pointer divergence FIRST-CLASS (never a constant
#    offset). Fail-soft: an unresolved chain clock leaves CHAIN_TIC empty and
#    the braid runs uninherited (legacy pointer-primary path, divergence still
#    declared builder-side).
CHAIN_TIC=$(python3 - "$INPUT_BUILDER" <<'PY' 2>/dev/null || true
import importlib.util, sys
spec = importlib.util.spec_from_file_location("hib", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
t = m.current_tic()
print(t if t else "")
PY
)

# 0. Braid step (cable BR5, fail-soft): refresh the braid packet BEFORE input
#    assembly so the builder can ingest a current-tic braid. Any failure here
#    leaves the legacy harmony lane fully intact (braid-invoke is itself
#    fail-soft and exits 0; the guard below is belt-and-suspenders).
echo "→ braid-invoke.sh (braid step, fail-soft; inherited chain tic=${CHAIN_TIC:-unresolved})"
BRAID_INHERIT_TIC="${CHAIN_TIC:-}" bash "$SCRIPT_DIR/braid-invoke.sh" || \
  echo "WARN harmony: braid step failed — continuing without braid (fail-soft)" >&2

# 1. Build input from federation state
echo "→ harmony-input-builder.py posture=$POSTURE mode=$MODE"
INPUT_PATH=$(CGG_POSTURE="$POSTURE" CGG_STATUSLINE_MODE="$MODE" \
  python3 "$INPUT_BUILDER" --print)
[ -f "$INPUT_PATH" ] || { echo "ERR: input not written at $INPUT_PATH" >&2; exit 1; }

TIC=$(python3 -c "import json,sys; print(json.load(open('$INPUT_PATH'))['terrainSlice']['tic'])")
DISPOSITION_PATH="$HARMONY_DIR/disposition-tic-$TIC.json"

# stderr capture (canary-docket t673 (b)): the engine + voice steps' stderr was
# UNCAPTURED — callers commonly discard it (2>/dev/null), so a degraded path's
# diagnostics (e.g. WHY the voice LLM times out, seven consecutive fallback tics
# 677-683) left no residue. Captured per-tic; caller-visible WARN lines below
# name the file. Empty logs are removed at the end (no zero-byte litter).
STDERR_LOG="$HARMONY_DIR/stderr-tic-$TIC.log"

# 2. Invoke engine via node — read input from stdin, write disposition packet
node --input-type=module -e "
  import { runHarmonyEngine } from '$ENGINE';
  import { readFileSync, writeFileSync } from 'node:fs';
  const input = JSON.parse(readFileSync('$INPUT_PATH', 'utf8'));
  const out = runHarmonyEngine(input);
  writeFileSync('$DISPOSITION_PATH', JSON.stringify(out, null, 2));
  console.log('disposition:', out.disposition?.stance, '|', 'meaning:', out.acousticSignature?.meaningState ?? 'n/a');
" 2>>"$STDERR_LOG" || { echo "ERR: engine invocation failed (stderr at $STDERR_LOG)" >&2; exit 1; }

# 2.5 Voice step (cable BR5, fail-soft): bounded-morphism ambient voice
#     proposer — constrained LLM line, validator-gated, honest template
#     fallback. Writes the voice object INTO the disposition file (additive).
#     HARMONY_VOICE=off skips the LLM inside the script. Any failure leaves
#     the disposition standing without a voice object (legacy-equivalent).
echo "→ harmony-voice.py (voice step, fail-soft; stderr → $STDERR_LOG)"
python3 "$SCRIPT_DIR/harmony-voice.py" --disposition "$DISPOSITION_PATH" 2>>"$STDERR_LOG" || \
  echo "WARN harmony: voice step failed — disposition stands without voice (fail-soft; stderr at $STDERR_LOG)" >&2

# 2.75 Discrimination-receipt step (bk-harmony-discrimination-receipt, ratified
#     /review 733 as the discrimination-axis ray on
#     ledger.md#can-it-eat-dataflow-liveness-predicate; fail-soft). Stamps the
#     emitted packet with last_change_tic + consecutive_identical_count over the
#     FULL retained history + the declared discriminating condition, so a
#     per-tic-consumed output can no longer read as a per-tic READING without
#     disclosing whether it has ever moved.
#
#     ⟜ RIDER — reproduced verbatim, /review 733 + the A3-732 standing rule ⟜
#     (carried on unbroken lines so the verbatim rider survives grep, unwrapped)
# RIDER: no harmony/contagion disposition may be READ as discriminating until built AND ruled — your build is the first half; the ruling comes later at /review
# STANDING RULE: Standing rule carried forward: do not read harmony/contagion dispositions as discriminating until the receipt fields exist and the A3-732 cause is ruled.
#     The block therefore carries ratified:false and NO consumer reads it. This
#     step REPORTS constancy; it never diagnoses the cause (t589-frozen
#     coordinates / no TTL is the A3-732 investigation, deliberately unruled).
echo "→ discrimination-receipt.py (receipt step, fail-soft; ratified:false, emit-side only)"
python3 "$SCRIPT_DIR/discrimination-receipt.py" --lane harmony --disposition "$DISPOSITION_PATH" 2>>"$STDERR_LOG" || \
  echo "WARN harmony: discrimination receipt step failed — disposition stands without a receipt block (fail-soft; stderr at $STDERR_LOG)" >&2

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
# /review 725 (#threshold-raise-relocates-the-wall-ship-a-headroom-observable):
# the counters key on CROSSING events, so they can only speak after the wall is
# hit. The approach observable rides the pointer the same way the streak does
# (/review 685) so glance-speed consumers (statusline, federation telemetry
# spine) can eat it — honest nulls when the voice step didn't run.
headroom = d.get("voice_headroom") or {}
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
    # bk-harmony-fallback-consecutive-counter (/review 685): the streak +
    # escalation ride the pointer so glance-speed consumers (statusline)
    # can eat them — honest nulls when the voice step didn't run.
    "consecutive_fallbacks": voice.get("consecutive_fallbacks"),
    "fallback_escalation_fired": (voice.get("fallback_escalation") or {}).get("fired"),
    "voice_budget_ms": headroom.get("budget_ms"),
    "voice_pct_of_budget": headroom.get("pct_of_budget"),
    "voice_recent_max_pct": headroom.get("recent_max_pct"),
    "voice_approach_max_pct": headroom.get("approach_max_pct"),
    "voice_share_recent_ge_90pct": headroom.get("share_of_recent_runs_ge_90pct"),
    "voice_headroom_window": headroom.get("window_observed"),
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

# drop an empty stderr capture (a clean run leaves no zero-byte litter);
# a non-empty one is the tic's diagnostic residue — announce it.
if [ -s "$STDERR_LOG" ]; then
  echo "⚠ stderr residue captured: $STDERR_LOG" >&2
else
  rm -f "$STDERR_LOG" 2>/dev/null || true
fi

echo "✓ harmony invocation complete (tic=$TIC posture=$POSTURE mode=$MODE)"
