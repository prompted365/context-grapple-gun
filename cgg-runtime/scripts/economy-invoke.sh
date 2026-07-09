#!/usr/bin/env bash
# economy-invoke.sh — deterministic per-tic ECONOMY HEARTBEAT invocation.
#
# Sibling of contagion-invoke.sh. Thin wrapper over the proven per-tic seam: resolve
# the current tic (the same way contagion does — the latest conformation's
# tic_count_physical), then invoke economy-heartbeat.py which spawns the 128-agent
# swarm, runs ONE economy tic in GUNSLINGER (seed) mode cradled by a DissonanceBasin
# with rollback armed, and writes the tic artifact + current-pointer + invocations.
#
# Read-only of federation state (only READS the conformation to resolve the tic).
# All writes are the handler's, and they land ONLY in audit-logs/economy/.
#
# Outputs (written by economy-heartbeat.py):
#   audit-logs/economy/economy-tic-{N}.json
#   audit-logs/economy/current-pointer.json          (latest pointer; tic == N)
#   audit-logs/economy/invocations.jsonl              (audit trail, append-only)
#   audit-logs/economy/ccoin-shadow-telemetry.jsonl   (breach-emitter wire; on breach only)
#
# Usage:
#   economy-invoke.sh                 # resolves the current tic from the conformation
#   economy-invoke.sh 570             # explicit tic as a positional arg
#   economy-invoke.sh --tic 570       # explicit tic as a flag
#   CURRENT_TIC=570 economy-invoke.sh # explicit tic via env

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${CGG_REPO_ROOT:-$(cd "$SCRIPT_DIR/../../../.." && pwd)}"
HANDLER="$SCRIPT_DIR/economy-heartbeat.py"
ECON_DIR="$REPO/audit-logs/economy"
CONFORMATION_DIR="$REPO/audit-logs/conformations"

[ -f "$HANDLER" ] || { echo "ERR: handler not found at $HANDLER" >&2; exit 1; }

# 1. Resolve the current tic: --tic / positional arg > CURRENT_TIC env > conformation.
TIC=""
if [ "${1:-}" = "--tic" ] && [ -n "${2:-}" ]; then
  TIC="$2"
elif [ -n "${1:-}" ]; then
  TIC="$1"
elif [ -n "${CURRENT_TIC:-}" ]; then
  TIC="$CURRENT_TIC"
else
  # Same resolution contagion uses: the latest conformation's tic_count_physical.
  TIC=$(python3 - "$CONFORMATION_DIR" <<'PY'
import glob, json, os, sys
conf_dir = sys.argv[1]
files = glob.glob(os.path.join(conf_dir, "tic-*.json"))
def tic_of(p):
    b = os.path.basename(p)
    try:
        return int(b.replace("tic-", "").replace(".json", ""))
    except ValueError:
        return -1
if not files:
    print("ERR: no conformation tic-*.json found", file=sys.stderr); sys.exit(1)
latest = max(files, key=tic_of)
d = json.load(open(latest))
print(int(d.get("tic_count_physical", tic_of(latest))))
PY
)
fi

case "$TIC" in
  ''|*[!0-9]*) echo "ERR: could not resolve a numeric tic (got '${TIC}')" >&2; exit 1 ;;
esac

echo "→ economy-heartbeat.py --tic $TIC"

# 2. Invoke the handler — spawn swarm, run one GUNSLINGER economy tic, write artifacts.
SNAP_PATH=$(python3 "$HANDLER" --tic "$TIC" --print) \
  || { echo "ERR: economy-heartbeat.py failed (tic=$TIC)" >&2; exit 1; }
[ -f "$SNAP_PATH" ] || { echo "ERR: snapshot not written at $SNAP_PATH" >&2; exit 1; }

# 3. One-line summary read back off the artifacts the handler just wrote.
python3 - "$SNAP_PATH" "$ECON_DIR/current-pointer.json" <<'PY'
import json, sys
snap = json.load(open(sys.argv[1]))
ptr = json.load(open(sys.argv[2]))
assert ptr["tic"] == snap["tic"], \
    f"anti-freeze: pointer tic {ptr['tic']} != snapshot tic {snap['tic']}"
print(
    f"✓ economy heartbeat complete (tic={snap['tic']}) "
    f"mode={snap['mode']} seed_stabilized={snap['seed_stabilized']} "
    f"g_t={snap['g_t']} mint_total={snap['mint_total']} burn_total={snap['burn_total']} "
    f"supply={snap['supply']} reserve_ratio={snap['reserve_ratio']} "
    f"breach_flags={snap['breach_flags']}"
)
PY
