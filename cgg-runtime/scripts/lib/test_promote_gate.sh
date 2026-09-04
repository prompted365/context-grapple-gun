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

# ═══════════════════════════════════════════════════════════════════════════════
# B2 WAVE 8 ROW B — THE REACHABILITY CURE (bk-reinforced-by-stamper-trigger-never-keyed)
# Cures F-769-B1 / OM-B1, filed HIGH by the wave-7 citizen: this gate required a TRUTHY
# `promoted_to`, which 0 of 14 latest-per-id `reinforce_existing` rows carry (all 14 carry
# `absorbed_into`; measured tic 769, RE-MEASURED 0/14 at tic 770) — so the wave-7
# landing_kind-keyed reinforce trigger was UNREACHABLE from its ONLY automatic caller.
#
# NC RUNS BOTH DIRECTIONS, member sets predicted BEFORE observation at
# audit-logs/governance/harpoon-office/staging/B2-wave8-rowB-NC-predicted-member-sets-tic770.json
#
# ⚠ DOES-NOT-SATISFY RIDER (verbatim): This cure does NOT retroactively stamp anything —
#   the backfill population measured 0 twice, OM-B2 adjudicated already-discharged this
#   fence. Nor does it prove a LIVE natural firing: no naturally-occurring reinforce
#   landing has yet traversed this boundary in production.
# ═══════════════════════════════════════════════════════════════════════════════

bad() { fail=$((fail+1)); echo "  FAIL: $1"; }

# ── DIRECTION 1: MUST FIRE on a reinforce-shaped landing carrying NO promoted_to ──
: > "$MARK"
bash "$TMP/scripts/lib/atomic-append.sh" --append "$QUEUE" \
  '{"id":"cpr_reinforce_demo_tic770","status":"absorbed","landing_kind":"reinforce_existing","absorbed_into":"ledger.md#demo-reachability-anchor","review_tic":770}'
chk "$(wc -l < "$MARK" | tr -d ' ')" "1" "R1 reinforce-shaped row (NO promoted_to) REACHES the writeback"
chk "$(grep -c -- '--cpr-id cpr_reinforce_demo_tic770' "$MARK")" "1" "R2 argv carries --cpr-id"
chk "$(grep -c -- '--status absorbed' "$MARK")" "1" "R3 argv carries --status absorbed"
chk "$(grep -c -- '--promoted-to' "$MARK")" "0" "R4 argv OMITS --promoted-to (keyed reinforced-by mode)"
chk "$(grep -c -- '--review-tic 770' "$MARK")" "1" "R5 argv carries --review-tic"

# ── DIRECTION 2: MUST NOT FIRE on non-matching landings; scope NOT widened ──
# R6 — nothing to promote to AND nothing to key on.
: > "$MARK"
bash "$TMP/scripts/lib/atomic-append.sh" --append "$QUEUE" \
  '{"id":"cpr_no_landing_tic770","status":"absorbed","absorbed_into":"ledger.md#demo-reachability-anchor","review_tic":770}'
chk "$(wc -l < "$MARK" | tr -d ' ')" "0" "R6 absorbed row with NO promoted_to and NO landing_kind does NOT fire"

# R7 — the promote-class STATUS pre-filter is untouched by the cure. The row deliberately
# carries the literal token "absorbed" (in superseded_status) so it PASSES the cheap bash
# pre-filter and is refused by the precise python status check — the discriminating shape.
: > "$MARK"
bash "$TMP/scripts/lib/atomic-append.sh" --append "$QUEUE" \
  '{"id":"cpr_extracted_lk_tic770","status":"extracted","superseded_status":"absorbed","landing_kind":"reinforce_existing","review_tic":770}'
chk "$(wc -l < "$MARK" | tr -d ' ')" "0" "R7 non-promote-class status carrying landing_kind does NOT fire (status check untouched)"

# R8 — queue scope containment is untouched by the cure.
: > "$MARK"
bash "$TMP/scripts/lib/atomic-append.sh" --append "$OTHER" \
  '{"id":"cpr_reinforce_offqueue_tic770","status":"absorbed","landing_kind":"reinforce_existing","absorbed_into":"ledger.md#demo-reachability-anchor","review_tic":770}'
chk "$(wc -l < "$MARK" | tr -d ' ')" "0" "R8 reinforce-shaped row on a NON-queue jsonl does NOT fire (scope containment)"

# R9 — the PROMOTE path is unregressed: promoted_to is now a MODE SELECTOR, not a gate.
: > "$MARK"
bash "$TMP/scripts/lib/atomic-append.sh" --append "$QUEUE" \
  '{"id":"cpr_promote_regress_tic770","status":"promoted","promoted_to":"feedback_y.md","landing_kind":"refinement_ray","review_tic":770}'
chk "$(grep -c -- '--promoted-to feedback_y.md' "$MARK")" "1" "R9 promote path unregressed (argv still carries --promoted-to)"

# ── E: END-TO-END REACHABILITY through the REAL review-promote-writeback.py ──────
# The stub above proves the boundary's ADMISSION (argv). These arms prove the STAMPER
# actually fires end-to-end — the thing "reachability" means. Fully hermetic: the real
# script resolves its queue / contract / ledger by walking UP from its own __file__, so a
# copy inside a tmp tree resolves tmp-side. E1 PROVES that resolution before any live
# stamp; if it fails, E2-E6 are refused rather than risking a federation-ledger write.
TMP2="$(mktemp -d)"
trap 'rm -rf "$TMP" "$TMP2"' EXIT
mkdir -p "$TMP2/scripts/lib" "$TMP2/audit-logs/cprs" \
         "$TMP2/audit-logs/governance/constitution-ledger" "$TMP2/contracts"
cp "$SRC" "$TMP2/scripts/lib/atomic-append.sh"
cp "$HERE/../review-promote-writeback.py" "$TMP2/scripts/review-promote-writeback.py"
cp "$HERE/../../contracts/landing-kind-enum-v1.json" "$TMP2/contracts/landing-kind-enum-v1.json"

QUEUE2="$TMP2/audit-logs/cprs/queue.jsonl"
LEDGER2="$TMP2/audit-logs/governance/constitution-ledger/ledger.md"
cat > "$LEDGER2" <<'LEDGER'
# Demo Constitution Ledger (hermetic fixture — NOT the federation ledger)

### Demo Reachability Anchor
<a id="demo-reachability-anchor"></a>
Body of the entry a reinforce landing should stamp.

### Demo Concede Anchor
<a id="demo-concede-anchor"></a>
Body of the entry a NON-family landing must leave untouched.
LEDGER

E_ID="cpr_e2e_reinforce_tic770"
E_ROW="{\"id\":\"$E_ID\",\"status\":\"absorbed\",\"landing_kind\":\"reinforce_existing\",\"absorbed_into\":\"ledger.md#demo-reachability-anchor\",\"review_tic\":770}"

# Seed the row directly (NOT through the gate — a plain append fires nothing) so the
# dry-run pre-flight can resolve it.
printf '%s\n' "$E_ROW" >> "$QUEUE2"

# E1 — PRE-FLIGHT SAFETY GUARD: the real script, invoked with the EXACT argv shape the
# cured boundary emits, must resolve the HERMETIC tmp ledger. Never the federation one.
probe="$(python3 "$TMP2/scripts/review-promote-writeback.py" \
           --cpr-id "$E_ID" --review-tic 770 --status absorbed --dry-run --json 2>&1)"
# Two-sided predicate, NOT an occurrence count: the tmp ledger must appear at least once
# AND the real federation ledger must appear ZERO times. (Round 1 of this arm asserted
# `count == 1` and FAILED CLOSED at count 2 — the resolved path is reported TWICE in the
# JSON, once under trigger.ledger and once under stamp.ledger. The guard refusing to
# proceed on a shape it did not model is the correct direction; the arithmetic was the
# arm's defect, disclosed rather than relaxed away.)
_tmp_hits="$(printf '%s' "$probe" | grep -c "\"ledger\": \"$LEDGER2\"")"
_fed_hits="$(printf '%s' "$probe" | grep -c 'canonical/audit-logs/governance/constitution-ledger/ledger.md')"
if [ "$_tmp_hits" -ge 1 ] && [ "$_fed_hits" -eq 0 ]; then e1=1; else e1=0; fi
chk "$e1" "1" "E1 pre-flight: real writeback resolves the HERMETIC tmp ledger and NEVER the federation ledger (tmp_hits=$_tmp_hits fed_hits=$_fed_hits)"

if [ "$e1" = "1" ]; then
  # E2-E4 — the live end-to-end fire THROUGH the cured boundary.
  bash "$TMP2/scripts/lib/atomic-append.sh" --append "$QUEUE2" "$E_ROW"
  chk "$(grep -c 'reinforced_by:' "$LEDGER2")" "1" "E2 reinforced_by breadcrumb LANDED via the boundary (REACHABILITY PROVEN)"
  chk "$(grep -c "$E_ID" "$LEDGER2")" "1" "E3 breadcrumb names the reinforcing cpr_id"
  chk "$(grep -c 'up-lane landing_kind=reinforce_existing' "$LEDGER2")" "1" "E4 breadcrumb names the up-lane KEYED source"

  # E5-E6 — direction 2, end-to-end: a NON-family landing traverses the same cured
  # boundary and the fail-closed consumer writes ZERO bytes.
  before="$(shasum -a 256 < "$LEDGER2" | awk '{print $1}')"
  bash "$TMP2/scripts/lib/atomic-append.sh" --append "$QUEUE2" \
    '{"id":"cpr_e2e_concede_tic770","status":"absorbed","landing_kind":"concede_local","absorbed_into":"ledger.md#demo-concede-anchor","review_tic":770}'
  after="$(shasum -a 256 < "$LEDGER2" | awk '{print $1}')"
  chk "$(grep -c 'cpr_e2e_concede_tic770' "$LEDGER2")" "0" "E5 NON-family landing (concede_local) stamps NOTHING"
  chk "$after" "$before" "E6 ledger BYTE-IDENTICAL across the non-family landing (fail-closed wrote zero bytes)"
else
  bad "E2 SKIPPED — E1 pre-flight failed; refusing to stamp an unverified ledger path"
  bad "E3 SKIPPED — E1 pre-flight failed"
  bad "E4 SKIPPED — E1 pre-flight failed"
  bad "E5 SKIPPED — E1 pre-flight failed"
  bad "E6 SKIPPED — E1 pre-flight failed"
  echo "  probe output was: $probe"
fi

echo "--------------------------------------------------"
echo "promote-gate test: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
