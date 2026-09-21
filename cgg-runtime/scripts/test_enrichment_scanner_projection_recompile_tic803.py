#!/usr/bin/env python3
"""test_enrichment_scanner_projection_recompile_tic803.py — the enrichment
scanner's adoption of the ONE shared recompile helper.

FIX-SITE: /review 803 round 2 (Ruling A), Architect-ratified on the recommended
option verbatim ("One shared helper, all five writers, today"). Ruling receipt:
  audit-logs/governance/receipts/2026-09-19-tic803-projection-shared-recompile-helper-ruling.md

THE DEFECT UNDER CURE (F-802-B2, MEDIUM, handed up by the tic-802 build seat)
-----------------------------------------------------------------------------
cpr-enrichment-scanner.py MUTATES audit-logs/cprs/queue.jsonl on every scan that
gathers new evidence, and its single `queue_state_compile` mention was a comment
about clocks. The queue's sha256 moves, so `meta.queue_sha256` is invalidated and
the derived projection is stale until the next /review writeback.

STATE-LINE CORRECTION carried with this suite: both the /review 803 ruling and
F-802-B2 describe this script as one that "rewrites the WHOLE queue under flock"
at ~L1091. That was true until tic 765, when
bk-cpr-enrichment-scanner-whole-file-rewrite-of-queue (HIGH, ruled /review 750
Q7) replaced the whole-file rewrite with an append-only copy-forward path
(`append_queue_rows`). The MUTATION is real either way, so the ruled duty is
unchanged; only the mechanism the ruling names is stale. The recompile therefore
sits AFTER `append_queue_rows` RETURNS — that function owns the whole locked
write and RAISES on refusal, so returning normally IS the successful-write
signal, and the lock is already released (recompiling under the lock would hold
a whole-queue compile inside a write lock every other queue writer waits on).

DOES-NOT-SATISFY RIDER (travels verbatim, on ONE unbroken line so a byte-exact
grep resolves it):
this increment does NOT add a reader-side staleness detector, does NOT prove the compiled per-id states are correct, does NOT test two writers racing, and does NOT make the projection authoritative over the queue — `queue.jsonl` latest-per-id remains the only authority; the projection is a derived convenience that is now writer-fresh for five of six writers by construction and for the sixth by its own code.

ARMS
----
  1. a SUCCESSFUL scan moves `meta.queue_sha256` to the live queue's sha256 and
     the projection lands in the zone the rows were appended to
  2. a DRY-RUN appends nothing and writes no projection
  3. a FAILED MUTATION (the write boundary raises) fires NO recompile — this is
     the one arm here that is NOT merely an absence assertion under revert: it
     proves the recompile sits AFTER the write, not beside it
  4. FAIL-SOFT: a non-zero compiler still lands the rows, the counters say so,
     stderr says so, and the scan's return value is unchanged

VACUITY NOTE (declared, not discovered): arm 2 asserts the ABSENCE of a
recompile and is vacuous under the negative control. Arm 3 is also vacuous under
a full revert (no recompile exists to suppress) — declared in the NC prediction
file BEFORE the control runs. The teeth are in arms 1 and 4.

EVIDENCE CLASS: FIXTURE-GREEN. Every arm runs in a temp zone; the live
audit-logs/cprs/queue.jsonl is NEVER touched.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE / "cpr-enrichment-scanner.py"
FIXTURE_TIC = 803

FAILING_COMPILER = (
    "#!/usr/bin/env python3\n"
    "import sys\n"
    "print('fixture compiler: deliberate non-zero exit', file=sys.stderr)\n"
    "sys.exit(6)\n"
)


def _load(name="cpr_enrichment_scanner_tic803"):
    spec = importlib.util.spec_from_file_location(name, str(_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sc = _load()


# THE OPT-OUT (F-812-C3, ruled /review 813). When NEITHER the seam above NOR a
# walkable root resolves the compiler, this resolver now FAILS: a green count
# that has lost its stamp-equality arms is the silent-degrade class. The name
# below is the explicit opt-out that restores the skip, and it announces ITSELF
# in three places so a skipped proof is never silent -- a warning (visible under
# bare -q with NO reporting flag), the skip reason (visible under -rs), and
# stdout (visible under -s) -- each MEASURED on this runner, not argued. It
# follows the one existing CGG_ALLOW_MISSING_* precedent rather than inventing a
# second convention. EMPTY IS NOT SET: the value is stripped before it is
# believed, so an empty override falls back to the hard failure, never to the
# silent skip.
#
# DOES-NOT-SATISFY RIDER (travels verbatim, on ONE unbroken line so a byte-exact grep resolves it):
# this increment does NOT convert any skip outside the six named files, does NOT change what the stamp-equality arms assert, does NOT make the projection authoritative over the queue, and does NOT certify that the tic-812 writer-class closure has fired live.
ALLOW_MISSING_QUEUE_STATE_COMPILE_ENV = "CGG_ALLOW_MISSING_QUEUE_STATE_COMPILE"


def _real_compiler():
    env = os.environ.get("CGG_QUEUE_STATE_COMPILE", "")
    if env and Path(env).is_file():
        return Path(env)
    for d in [_HERE, *_HERE.parents]:
        cand = d / "audit-logs" / "cprs" / "queue_state_compile.py"
        if cand.is_file():
            return cand
    if os.environ.get(ALLOW_MISSING_QUEUE_STATE_COMPILE_ENV, "").strip():
        announcement = (
            f"{ALLOW_MISSING_QUEUE_STATE_COMPILE_ENV} is set: the fixture "
            f"compiler is unresolvable, so the projection proofs in this file "
            f"are SKIPPED, not satisfied."
        )
        print(announcement)
        warnings.warn(announcement, stacklevel=2)
        raise unittest.SkipTest(announcement)
    raise AssertionError(
        "QUEUE STATE COMPILER UNRESOLVABLE -- the stamp-equality and fail-soft "
        "proofs in this file cannot run, so they FAIL rather than skipping "
        "quietly.\n"
        "  wanted         : audit-logs/cprs/queue_state_compile.py\n"
        f"  seam checked   : CGG_QUEUE_STATE_COMPILE="
        f"{os.environ.get('CGG_QUEUE_STATE_COMPILE', '') or '(unset or empty)'}\n"
        f"  walked up from : {_HERE}\n"
        f"  roots walked   : {len([_HERE, *_HERE.parents])}, none carrying "
        f"audit-logs/cprs/queue_state_compile.py\n"
        "  supply it: point CGG_QUEUE_STATE_COMPILE at an existing "
        "queue_state_compile.py, or run this file inside a tree whose ancestry "
        "carries audit-logs/cprs/queue_state_compile.py, or set "
        f"{ALLOW_MISSING_QUEUE_STATE_COMPILE_ENV}=1 to skip these proofs "
        "deliberately and loudly."
    )


def build_zone(td, compiler="real"):
    """Fixture shape mirrors the committed scanner NC suite
    (test_scanner_append_only_nc._build_fixture): a holding CPR with a real
    source file so the evidence gatherers have something to read."""
    zone = Path(td)
    (zone / ".ticzone").write_text(json.dumps(
        {"name": "fixturezone803", "audit_logs_path": "audit-logs"}))
    al = zone / "audit-logs"
    (al / "cprs").mkdir(parents=True, exist_ok=True)
    (al / "tics").mkdir(parents=True, exist_ok=True)
    (al / "signals").mkdir(parents=True, exist_ok=True)
    (al / "tics" / "2026-09.jsonl").write_text(json.dumps({
        "type": "tic", "count_mode": "counted",
        "domain_counter_after": FIXTURE_TIC, "global_counter_after": FIXTURE_TIC,
    }) + "\n")
    (zone / "beta_source.md").write_text(
        "BETA LESSON BODY: a queue mutator owns its derived projection.\n",
        encoding="utf-8")
    rows = [
        {"id": "cpr_alpha", "status": "promoted", "lesson": "unrelated",
         "birth_tic": 700},
        {"id": "cpr_beta", "status": "enrichment_needed",
         "lesson": "BETA LESSON BODY: a queue mutator owns its derived projection.",
         "source": "beta_source.md", "source_file": "beta_source.md",
         "source_date": "2026-08-01", "subsystem": "cprs",
         "recommended_scopes": ["beta_source.md"], "birth_tic": 701},
    ]
    with open(al / "cprs" / "queue.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    if compiler == "real":
        shutil.copy2(_real_compiler(), al / "cprs" / "queue_state_compile.py")
    elif compiler == "failing":
        (al / "cprs" / "queue_state_compile.py").write_text(FAILING_COMPILER)
    return zone


def qp(zone):
    return Path(zone) / "audit-logs" / "cprs" / "queue.jsonl"


def qsha(zone):
    return hashlib.sha256(qp(zone).read_bytes()).hexdigest()


def proj(zone):
    return Path(zone) / "audit-logs" / "cprs" / "effective-state" / "effective_state.json"


class SuccessfulScanMovesTheProjection(unittest.TestCase):
    """ARM 1 — the duty: stamp equals the LIVE fixture queue's sha."""

    def test_scan_moves_queue_sha256_to_the_live_queue_sha(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            before = qp(zone).read_bytes()
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                sc.scan_and_enrich(str(zone), quiet=True)

            self.assertNotEqual(qp(zone).read_bytes(), before,
                                "the scan must have mutated the queue for this arm "
                                "to mean anything")
            self.assertEqual(sc.RUN_COUNTERS["effective_state_recompiled"], 1,
                             f"{sc.RUN_COUNTERS} / stderr={err.getvalue()}")
            self.assertEqual(sc.RUN_COUNTERS["effective_state_recompile_failed"], 0)
            self.assertEqual(sc.RUN_COUNTERS["effective_state_recompile_detail"],
                             f"recompiled_at_tic={FIXTURE_TIC}")

            es = json.loads(proj(zone).read_text())
            self.assertEqual(es["meta"]["queue_sha256"], qsha(zone),
                             "the projection's stamp must equal the LIVE queue's sha256")
            self.assertEqual(Path(es["meta"]["queue_path"]).resolve(), qp(zone).resolve())
            self.assertIn(zone.resolve(), proj(zone).resolve().parents)

    def test_history_rows_stay_byte_intact(self):
        """The tic-765 append-only cure is not regressed by this increment."""
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            before_lines = qp(zone).read_text().splitlines()
            with contextlib.redirect_stderr(io.StringIO()):
                sc.scan_and_enrich(str(zone), quiet=True)
            after_lines = qp(zone).read_text().splitlines()
            self.assertEqual(after_lines[:len(before_lines)], before_lines,
                             "every historical line must stay byte-intact")
            self.assertGreater(len(after_lines), len(before_lines))


class NoMutationFiresNoRecompile(unittest.TestCase):
    """ARMS 2-3."""

    def test_dry_run_appends_nothing_and_writes_no_projection(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            before = qp(zone).read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                sc.scan_and_enrich(str(zone), dry_run=True, quiet=True)
            self.assertEqual(qp(zone).read_bytes(), before)
            self.assertEqual(sc.RUN_COUNTERS["effective_state_recompiled"], 0)
            self.assertFalse(proj(zone).exists())

    def test_a_failed_write_fires_no_recompile(self):
        """ARM 3 — the recompile sits AFTER the write, not beside it. If the
        write boundary raises, no projection may be produced."""
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            before = qp(zone).read_bytes()
            real = sc.append_queue_rows

            def refuse(queue_path, rows):
                raise RuntimeError("atomic-append.sh refused/failed (rc=1): fixture")

            sc.append_queue_rows = refuse
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(RuntimeError):
                        sc.scan_and_enrich(str(zone), quiet=True)
            finally:
                sc.append_queue_rows = real

            self.assertEqual(qp(zone).read_bytes(), before, "nothing was written")
            self.assertEqual(sc.RUN_COUNTERS["effective_state_recompiled"], 0)
            self.assertEqual(sc.RUN_COUNTERS["effective_state_recompile_detail"], "")
            self.assertFalse(proj(zone).exists(),
                             "a failed mutation must not produce a projection")


class RecompileIsFailSoft(unittest.TestCase):
    """ARM 4 — a derived-cache miss NEVER fails the scan."""

    def test_nonzero_compiler_still_lands_the_rows(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, compiler="failing")
            before_lines = len(qp(zone).read_text().splitlines())
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                sc.scan_and_enrich(str(zone), quiet=True)
            self.assertGreater(len(qp(zone).read_text().splitlines()), before_lines,
                               "the appended rows must survive a compile failure")
            self.assertEqual(sc.RUN_COUNTERS["effective_state_recompile_failed"], 1)
            self.assertIn("recompile_failed_rc=6",
                          sc.RUN_COUNTERS["effective_state_recompile_detail"])
            self.assertIn("effective-state recompile FAILED", err.getvalue())

    def test_missing_compiler_is_typed_and_soft(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, compiler="missing")
            before_lines = len(qp(zone).read_text().splitlines())
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                sc.scan_and_enrich(str(zone), quiet=True)
            self.assertGreater(len(qp(zone).read_text().splitlines()), before_lines)
            self.assertTrue(
                sc.RUN_COUNTERS["effective_state_recompile_detail"].startswith(
                    "compiler_not_found:"),
                sc.RUN_COUNTERS["effective_state_recompile_detail"])
            self.assertIn("recompile skipped", err.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
