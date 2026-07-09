#!/usr/bin/env bash
# braid-invoke.sh — Build the lattice.braid.input envelope, run the kernel
# braid engine (autonomous_kernel/lattice_braid.py), write the braid packet.
#
# Cable BR4 outer ring (braid covenant tic 569, Office of the Harpoonv2).
# Mirrors harmony-invoke.sh's seam pattern: builder -> engine (python3 -c
# import seam, the python analog of harmony's node seam) -> packet + pointer
# + invocations line.
#
# READ-ONLY of federation state. Writes ONLY to audit-logs/braid/:
#   audit-logs/braid/input-tic-{N}.json      (builder)
#   audit-logs/braid/braid-tic-{N}.json      (the braid packet)
#   audit-logs/braid/current-pointer.json    (compact latest pointer)
#   audit-logs/braid/invocations.jsonl       (audit trail, append-only)
#
# FAIL-SOFT EVERYWHERE: absent surfaces -> nulls + honest flags inside the
# packet; any step failure logs a warning and exits 0 (the braid is advisory
# — a missing braid never breaks a caller's lane). The economic writeback in
# the packet is BUILD-AND-GATE: ratified:false, dormant; /review flips it.
#
# Usage:
#   braid-invoke.sh          # full run
#   braid-invoke.sh --print  # also echo the packet path to stdout

set -uo pipefail   # no -e: every step is individually fail-soft

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${CGG_REPO_ROOT:-$(cd "$SCRIPT_DIR/../../../.." && pwd)}"
BRAID_DIR="$REPO/audit-logs/braid"
INPUT_BUILDER="$SCRIPT_DIR/braid-input-builder.py"
KERNEL_DIR="$REPO/autonomous_kernel"

mkdir -p "$BRAID_DIR" || { echo "WARN braid: cannot mkdir $BRAID_DIR" >&2; exit 0; }

# 1. Build the input envelope from federation state (fail-soft inside).
echo "→ braid-input-builder.py" >&2
INPUT_PATH=$(python3 "$INPUT_BUILDER" --print) || INPUT_PATH=""
if [ -z "$INPUT_PATH" ] || [ ! -f "$INPUT_PATH" ]; then
  echo "WARN braid: input envelope not written — braid skipped (fail-soft)" >&2
  exit 0
fi

TIC=$(python3 -c "import json;print(json.load(open('$INPUT_PATH')).get('tic'))") || TIC=""
if [ -z "$TIC" ] || [ "$TIC" = "None" ]; then
  echo "WARN braid: tic unresolved in envelope — braid skipped (fail-soft)" >&2
  exit 0
fi
PACKET_PATH="$BRAID_DIR/braid-tic-$TIC.json"

# 2. Run the kernel engine via the python3 import seam (harmony's node-seam
#    analog). Pure transform; the WRITE happens here in the outer ring.
if ! python3 - "$INPUT_PATH" "$PACKET_PATH" "$REPO" <<'PY'
import json, os, sys
input_path, packet_path, repo = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.join(repo, "autonomous_kernel"))
from lattice_braid import braid
env = json.load(open(input_path))
packet = braid(env)
with open(packet_path, "w") as f:
    json.dump(packet, f, indent=2)
print(f"braid packet: {packet_path}", file=sys.stderr)
print("route:", packet["traversal_physics"]["route_advisory"],
      "| tension:", packet["tension"]["cable_tension"],
      "| regime:", packet["tension"]["regime"],
      "| wisdom/caution:",
      round(packet["archetype_field"]["wisdom_mass"], 4), "/",
      round(packet["archetype_field"]["caution_mass"], 4),
      "| ratified:", packet["economic_writeback"]["ratified"], file=sys.stderr)
PY
then
  echo "WARN braid: engine invocation failed — braid skipped (fail-soft)" >&2
  exit 0
fi

# 3. Compact current pointer (small JSON, latest wins).
python3 - "$PACKET_PATH" "$REPO" <<'PY' || echo "WARN braid: pointer write failed (fail-soft)" >&2
import json, pathlib, sys, time
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text())
repo = pathlib.Path(sys.argv[2])
current = {
    "tic": d.get("tic"),
    "braid_packet_path": str(p.relative_to(repo)),
    "generated_at": d.get("generated_at")
        or time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "route_advisory": d.get("traversal_physics", {}).get("route_advisory"),
    "cable_tension": d.get("tension", {}).get("cable_tension"),
    "regime": d.get("tension", {}).get("regime"),
    "wisdom_mass": d.get("archetype_field", {}).get("wisdom_mass"),
    "caution_mass": d.get("archetype_field", {}).get("caution_mass"),
    "epsilon_gate_fired": d.get("wisdom_pressure", {})
        .get("epsilon_gate", {}).get("fired"),
    "writeback_ratified": d.get("economic_writeback", {}).get("ratified"),
    "engine_version": d.get("engine_version"),
}
out = repo / "audit-logs" / "braid" / "current-pointer.json"
out.write_text(json.dumps(current, indent=2) + "\n")
print(f"current pointer: {out}", file=sys.stderr)
PY

# 4. Append the invocations audit line.
python3 - "$INPUT_PATH" "$PACKET_PATH" "$REPO" <<'PY' || echo "WARN braid: invocations append failed (fail-soft)" >&2
import json, pathlib, sys, time
repo = pathlib.Path(sys.argv[3])
inp, pkt = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
d = json.loads(pkt.read_text())
entry = {
    "tic": d.get("tic"),
    "invoked_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "input": str(inp.relative_to(repo)),
    "output": str(pkt.relative_to(repo)),
    "route_advisory": d.get("traversal_physics", {}).get("route_advisory"),
    "jerk_flags": d.get("trajectory", {}).get("jerk_flags"),
    "honest_flags": d.get("honest_flags"),
    "writeback_ratified": d.get("economic_writeback", {}).get("ratified"),
}
log = repo / "audit-logs" / "braid" / "invocations.jsonl"
with log.open("a") as f:
    f.write(json.dumps(entry) + "\n")
print(f"audit logged: {log}", file=sys.stderr)
PY

if [ "${1:-}" = "--print" ]; then
  echo "$PACKET_PATH"
fi
echo "✓ braid invocation complete (tic=$TIC)" >&2
exit 0
