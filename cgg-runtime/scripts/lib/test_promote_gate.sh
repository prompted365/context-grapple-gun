#!/usr/bin/env bash
# test_promote_gate.sh — hermetic test for the atomic-append promote-writeback physics
# gate (bk-emitter-review-wiring, tic 481). Copies atomic-append.sh + a STUB writeback
# into a temp tree (mirroring scripts/lib + scripts/) and asserts the gate:
#   1. FIRES on a promote-class row appended to */cprs/queue.jsonl (correct argv)
#   2. SKIPS a non-promote row (status=extracted) on the same queue
#   3. SKIPS a promote-class row on a NON-queue jsonl (scope containment)
#   4. SKIPS promoted_spec/absorbed handled as promote-class too (fires)
# No production surface is touched. Run: bash test_promote_gate.sh
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/atomic-append.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/scripts/lib" "$TMP/audit-logs/cprs"
cp "$SRC" "$TMP/scripts/lib/atomic-append.sh"
MARK="$TMP/rpw_invocations.log"

# STUB review-promote-writeback.py — records its argv, mutates nothing.
cat > "$TMP/scripts/review-promote-writeback.py" <<'PYSTUB'
#!/usr/bin/env python3
import sys, os
mark = os.environ["RPW_MARK"]
with open(mark, "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\n")
PYSTUB

export RPW_MARK="$MARK"
QUEUE="$TMP/audit-logs/cprs/queue.jsonl"
OTHER="$TMP/audit-logs/signals/2026-06-21.jsonl"
mkdir -p "$(dirname "$OTHER")"

pass=0; fail=0
chk() { if [ "$1" = "$2" ]; then pass=$((pass+1)); echo "  PASS: $3"; else fail=$((fail+1)); echo "  FAIL: $3 (got '$1' want '$2')"; fi; }

# 1. promote row on queue → gate fires
: > "$MARK"
bash "$TMP/scripts/lib/atomic-append.sh" --append "$QUEUE" \
  '{"id":"cpr_demo_tic500","status":"promoted","promoted_to":"feedback_x.md","review_tic":481}'
chk "$(grep -c 'cpr_demo_tic500' "$MARK")" "1" "promote row FIRES the writeback"
chk "$(grep -c -- '--status promoted' "$MARK")" "1" "argv carries --status promoted"
chk "$(grep -c -- '--promoted-to feedback_x.md' "$MARK")" "1" "argv carries --promoted-to"

# 2. non-promote row on queue → gate skips
: > "$MARK"
bash "$TMP/scripts/lib/atomic-append.sh" --append "$QUEUE" \
  '{"id":"cpr_demo_tic501","status":"extracted"}'
chk "$(wc -l < "$MARK" | tr -d ' ')" "0" "extracted row does NOT fire (pre-filter)"

# 3. deferred row that happens to mention promoted_to-ish text but status!=promote → skip
: > "$MARK"
bash "$TMP/scripts/lib/atomic-append.sh" --append "$QUEUE" \
  '{"id":"cpr_demo_tic502","status":"deferred","review_reasoning":"not promoted yet"}'
chk "$(wc -l < "$MARK" | tr -d ' ')" "0" "deferred row does NOT fire (precise status check)"

# 4. promote row on a NON-queue jsonl → gate skips (scope containment)
: > "$MARK"
bash "$TMP/scripts/lib/atomic-append.sh" --append "$OTHER" \
  '{"id":"sig_x","status":"promoted","promoted_to":"x","review_tic":1}'
chk "$(wc -l < "$MARK" | tr -d ' ')" "0" "promote row on signals jsonl does NOT fire (scoped to queue)"

# 5. promoted_spec + absorbed are promote-class too
: > "$MARK"
bash "$TMP/scripts/lib/atomic-append.sh" --append "$QUEUE" \
  '{"id":"cpr_demo_tic503","status":"promoted_spec","promoted_to":"spec.md","review_tic":481}'
bash "$TMP/scripts/lib/atomic-append.sh" --append "$QUEUE" \
  '{"id":"cpr_demo_tic504","status":"absorbed","promoted_to":"x.md","review_tic":481}'
chk "$(wc -l < "$MARK" | tr -d ' ')" "2" "promoted_spec + absorbed both fire"

# 6. queue rows still durably appended (gate never blocks the write)
chk "$(grep -c 'cpr_demo_tic500' "$QUEUE")" "1" "queue row durably appended (gate non-blocking)"

echo "--------------------------------------------------"
echo "promote-gate test: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
