#!/usr/bin/env bash
# test_atomic_append_arg_guard.sh — argument-shape guard fixtures for lib/atomic-append.sh
# (bk-atomic-append-positional-silent-noop, filed HIGH tic 691, struck tic 692).
#
# The defect: EXECUTED positionally without the --append sentinel, the lib fell
# through its trailing arg-check — exit 0, ZERO bytes written. A write primitive
# whose misuse-shape no-ops green is the 'bare invocation is an action, not a
# probe' inversion: misuse must FAIL LOUD. Caught live by the tic-691
# cpr-stepper reading its own receipt back (reviews/2026-08-10.jsonl rows 2-3).
#
# Contract asserted here (post-fix):
#   A1  positional execution (no sentinel)  -> exit 2, usage on stderr, nothing written  [RED pre-fix]
#   A2  zero-arg execution                  -> exit 2, usage on stderr                   [RED pre-fix]
#   A3  sentinel form --append <t> <line>   -> exit 0, line durably appended             [green both]
#   A4  sourcing with unrelated positionals -> inert: no error, no write, fn available   [green both]
#   A5  sourced atomic_append call          -> line durably appended                     [green both]
#
# Follows the test_promote_gate.sh convention: copy the lib into a tmp tree and
# drive the COPY (self-locating-artifact test isolation — never the real zone).
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/atomic-append.sh"
TMP="$(mktemp -d /tmp/atomic-arg-guard.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/scripts/lib"
cp "$SRC" "$TMP/scripts/lib/atomic-append.sh"
LIB="$TMP/scripts/lib/atomic-append.sh"
TARGET="$TMP/out.jsonl"

pass=0; fail=0
ok()   { pass=$((pass+1)); echo "  PASS: $1"; }
bad()  { fail=$((fail+1)); echo "  FAIL: $1"; }

echo "=== A1: positional execution without sentinel fails loud, writes nothing ==="
rm -f "$TARGET"
err="$(bash "$LIB" "$TARGET" '{"a":1}' 2>&1 >/dev/null)"; rc=$?
[ "$rc" -eq 2 ] && ok "exit 2 (got $rc)" || bad "expected exit 2, got $rc (silent no-op pre-fix)"
[ ! -s "$TARGET" ] && ok "nothing written" || bad "bytes were written on misuse"
case "$err" in *usage*|*USAGE*|*--append*) ok "usage names the sentinel on stderr" ;; *) bad "no usage on stderr (got: ${err:-<empty>})" ;; esac

echo "=== A2: zero-arg execution fails loud ==="
err="$(bash "$LIB" 2>&1 >/dev/null)"; rc=$?
[ "$rc" -eq 2 ] && ok "exit 2 (got $rc)" || bad "expected exit 2, got $rc"

echo "=== A3: sentinel form appends durably ==="
rm -f "$TARGET"
bash "$LIB" --append "$TARGET" '{"a":1}'; rc=$?
[ "$rc" -eq 0 ] && ok "exit 0" || bad "sentinel form exited $rc"
[ "$(cat "$TARGET" 2>/dev/null)" = '{"a":1}' ] && ok "line appended" || bad "line not appended"

echo "=== A4: sourcing with unrelated positional args is inert ==="
rm -f "$TARGET.src"
# probe script sources the lib while carrying its own positional args
cat > "$TMP/probe-source.sh" <<PROBE
#!/usr/bin/env bash
source "$LIB"
type atomic_append >/dev/null 2>&1 && echo fn-present
echo probe-rc=0
PROBE
out="$(bash "$TMP/probe-source.sh" not-append junk1 junk2 2>&1)"; rc=$?
[ "$rc" -eq 0 ] && ok "sourcing script with positionals exits 0" || bad "sourcing path exited $rc: $out"
case "$out" in *fn-present*) ok "atomic_append function available after source" ;; *) bad "function missing after source" ;; esac
[ ! -f "$TARGET.src" ] && ok "no stray write from sourcing" || bad "sourcing wrote a file"

echo "=== A5: sourced function call still appends ==="
rm -f "$TARGET"
cat > "$TMP/probe-call.sh" <<PROBE
#!/usr/bin/env bash
source "$LIB"
atomic_append "$TARGET" '{"b":2}'
PROBE
bash "$TMP/probe-call.sh"; rc=$?
[ "$rc" -eq 0 ] && ok "sourced call exit 0" || bad "sourced call exited $rc"
[ "$(cat "$TARGET" 2>/dev/null)" = '{"b":2}' ] && ok "line appended via sourced fn" || bad "sourced fn did not append"

echo
echo "RESULT: $pass passed, $fail failed"
[ "$fail" -eq 0 ] || exit 1
