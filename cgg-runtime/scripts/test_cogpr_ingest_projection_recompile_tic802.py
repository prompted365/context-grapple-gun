#!/usr/bin/env python3
"""test_cogpr_ingest_projection_recompile_tic802.py — the mint-side projection
recompile, keyed on MUTATION.

FIX-SITE: the /review 801 round-2 ruling, Architect-ratified on the recommended
option verbatim ("Key the writer on mutation"). Ruling receipt:
  audit-logs/governance/receipts/2026-09-19-tic801-projection-writer-locus-ruling.md

THE DEFECT UNDER CURE
---------------------
audit-logs/cprs/effective-state/ is a DERIVED cache (queue.jsonl stays the sole
authority), but its only invokers were queue-lifecycle-writeback.py (fires at a
/review writeback) and bench-packet-prep.py (fires at a bench prep). This
script is a MINT-SIDE queue appender that named the compiler only in comments
and never invoked it — so every mint left the projection stale until the next
/review pass. Lived at the tic-800 walk: live-extracted 12 vs projection 5,
i.e. 7 invisible ids; at the tic-801 walk the projection's `queue_sha256`
reproduced the queue's first 3,195 rows while the queue stood at 3,198.

DOES-NOT-SATISFY RIDER (travels verbatim with this increment, on ONE unbroken
line so a byte-exact grep resolves it):
this increment does NOT add a reader-side staleness detector; a reader that trusts the projection is protected only while every queue writer recompiles. A writer added later without the call re-opens the window.

THE CONTRACT UNDER TEST (one arm per tooth)
-------------------------------------------
  1. a SUCCESSFUL mint moves `meta.queue_sha256` to the live queue's sha256
  2. the recompile targets the ZONE THE APPEND WROTE TO (meta.queue_path is the
     fixture queue; the projection lands beside that queue), which is what makes
     the source copy and the installed copy under ~/.claude/cgg-runtime/ behave
     identically — the installed tree carries no .ticzone in its ancestry
  3. a NO-APPEND run (dedup hit) fires NO recompile — the projection's bytes
     AND mtime are unmoved
  4. a DRY-RUN fires no recompile (nothing was written, so nothing may move)
  5. FAIL-SOFT on a non-zero compiler: the append still lands, the process exit
     status is unchanged, the failure is on stderr AND in the counters
  6. FAIL-SOFT on a missing compiler: same contract, typed `compiler_not_found`

EVIDENCE CLASS: FIXTURE-GREEN. Every arm runs in a temp zone under the test's
own tmpdir; the live audit-logs/cprs/queue.jsonl is NEVER touched (a real
cogpr-ingest run MINTS queue rows). Fixture-green is not live-green — the first
LIVE proof is the seat's next real mint after commit + sync.

Self-Locating Artifact Test Isolation: `ingest()` takes an explicit zone_root,
so no arm can reach the real zone.

Run:  python3 -m unittest test_cogpr_ingest_projection_recompile_tic802
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE / "cogpr-ingest.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ci = _load("cogpr_ingest_projection_under_test", _SCRIPT)

FIXTURE_TIC = 802

# The real compiler is a fixture INPUT (copied into each temp zone, never run
# against the live tree). CGG_QUEUE_STATE_COMPILE is the declared seam for the
# NEGATIVE CONTROL harness, which runs a reverted copy of this suite from
# outside the measured tree and so cannot walk up to the federation root.
def _real_compiler():
    env = os.environ.get("CGG_QUEUE_STATE_COMPILE", "")
    if env and Path(env).is_file():
        return Path(env)
    for d in [_HERE, *_HERE.parents]:
        cand = d / "audit-logs" / "cprs" / "queue_state_compile.py"
        if cand.is_file():
            return cand
    raise unittest.SkipTest("queue_state_compile.py not locatable for fixtures")


FAILING_COMPILER = (
    "#!/usr/bin/env python3\n"
    "import sys\n"
    "print('fixture compiler: deliberate non-zero exit', file=sys.stderr)\n"
    "sys.exit(3)\n"
)


def _build_zone(td, compiler="real"):
    """A minimal but REAL zone: .ticzone + a tic log + an empty queue (+ the
    compiler beside the queue, per the mode)."""
    zone = Path(td)
    (zone / ".ticzone").write_text(json.dumps(
        {"name": "fixturezone", "audit_logs_path": "audit-logs"}))
    tics = zone / "audit-logs" / "tics"
    tics.mkdir(parents=True, exist_ok=True)
    (tics / "2026-09.jsonl").write_text(json.dumps({
        "type": "tic", "count_mode": "counted",
        "domain_counter_after": FIXTURE_TIC,
        "global_counter_after": FIXTURE_TIC,
    }) + "\n")
    cprs = zone / "audit-logs" / "cprs"
    cprs.mkdir(parents=True, exist_ok=True)
    (cprs / "queue.jsonl").write_text("")
    if compiler == "real":
        shutil.copy2(_real_compiler(), cprs / "queue_state_compile.py")
    elif compiler == "failing":
        (cprs / "queue_state_compile.py").write_text(FAILING_COMPILER)
    # compiler == "missing": nothing is placed beside the queue
    return zone


def _write_report(zone, lesson, name="tic-802-fixture.report.json"):
    rep_dir = zone / "audit-logs" / "mogul" / "cycle-reports" / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)
    rep = rep_dir / name
    rep.write_text(json.dumps({
        "mandate_id": "tic-802-fixture",
        "actor": {"runtime": "claude_code"},
        "candidate_cogprs": [{"lesson": lesson}],
    }))
    return rep


def _queue_sha(zone):
    return hashlib.sha256(
        (zone / "audit-logs" / "cprs" / "queue.jsonl").read_bytes()).hexdigest()


def _projection(zone):
    return zone / "audit-logs" / "cprs" / "effective-state" / "effective_state.json"


class SuccessfulMintMovesTheProjection(unittest.TestCase):
    """DUTY 2 + the zone-resolution proof."""

    def test_mint_moves_queue_sha256_to_the_live_queue_sha(self):
        with tempfile.TemporaryDirectory() as td:
            zone = _build_zone(td)
            rep = _write_report(zone, "A mint that must move the projection.")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                summary = ci.ingest(zone, rep, dry_run=False)

            self.assertEqual(summary["ingested"], 1, summary)
            self.assertEqual(summary["effective_state_recompiled"], 1,
                             f"{summary} / stderr={err.getvalue()}")
            self.assertEqual(summary["effective_state_recompile_failed"], 0)

            es = json.loads(_projection(zone).read_text())
            self.assertEqual(es["meta"]["queue_sha256"], _queue_sha(zone),
                             "the projection's stamp must equal the LIVE queue's sha256")
            self.assertEqual(es["meta"]["current_tic"], FIXTURE_TIC)

    def test_recompile_targets_the_queue_the_append_wrote(self):
        """Every path is derived from the queue, never from __file__ — this is
        what makes the installed copy (no .ticzone in its ancestry) behave the
        same as the source copy."""
        with tempfile.TemporaryDirectory() as td:
            zone = _build_zone(td)
            rep = _write_report(zone, "A mint whose projection must land in-zone.")
            with contextlib.redirect_stderr(io.StringIO()):
                summary = ci.ingest(zone, rep, dry_run=False)
            self.assertEqual(summary["effective_state_recompiled"], 1)

            es = json.loads(_projection(zone).read_text())
            wrote = (zone / "audit-logs" / "cprs" / "queue.jsonl").resolve()
            self.assertEqual(Path(es["meta"]["queue_path"]).resolve(), wrote)
            self.assertTrue(
                zone.resolve() in _projection(zone).resolve().parents,
                "the projection must land inside the zone the append wrote to")


class NoAppendFiresNoRecompile(unittest.TestCase):
    """DUTY 3 — a run that mutates nothing must move nothing."""

    def test_dedup_hit_leaves_the_projection_byte_and_mtime_identical(self):
        with tempfile.TemporaryDirectory() as td:
            zone = _build_zone(td)
            rep = _write_report(zone, "A lesson ingested exactly once.")
            with contextlib.redirect_stderr(io.StringIO()):
                first = ci.ingest(zone, rep, dry_run=False)
            self.assertEqual(first["ingested"], 1)
            proj = _projection(zone)
            before_bytes = proj.read_bytes()
            before_mtime = proj.stat().st_mtime_ns
            queue_before = (zone / "audit-logs" / "cprs" / "queue.jsonl").read_bytes()

            with contextlib.redirect_stderr(io.StringIO()):
                second = ci.ingest(zone, rep, dry_run=False)

            self.assertEqual(second["ingested"], 0, second)
            self.assertEqual(second["effective_state_recompiled"], 0)
            self.assertEqual(second["effective_state_recompile_failed"], 0)
            self.assertEqual(second["effective_state_recompile_detail"], "")
            self.assertEqual(proj.read_bytes(), before_bytes,
                             "no-append run must not rewrite the projection")
            self.assertEqual(proj.stat().st_mtime_ns, before_mtime,
                             "no-append run must not even touch the projection")
            self.assertEqual(
                (zone / "audit-logs" / "cprs" / "queue.jsonl").read_bytes(),
                queue_before)

    def test_dry_run_fires_no_recompile(self):
        with tempfile.TemporaryDirectory() as td:
            zone = _build_zone(td)
            rep = _write_report(zone, "A dry-run lesson that must write nothing.")
            with contextlib.redirect_stderr(io.StringIO()):
                summary = ci.ingest(zone, rep, dry_run=True)
            self.assertEqual(summary["ingested"], 1)
            self.assertEqual(summary["effective_state_recompiled"], 0)
            self.assertFalse(_projection(zone).exists(),
                             "a dry-run must not produce a projection")


class RecompileIsFailSoft(unittest.TestCase):
    """DUTY 4 — a derived-cache miss NEVER fails the constitutional write."""

    def test_nonzero_compiler_still_lands_the_append_and_counts_the_failure(self):
        with tempfile.TemporaryDirectory() as td:
            zone = _build_zone(td, compiler="failing")
            rep = _write_report(zone, "A mint whose recompile must fail softly.")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                summary = ci.ingest(zone, rep, dry_run=False)

            # the append LANDED
            self.assertEqual(summary["ingested"], 1, summary)
            self.assertNotIn("error", summary)
            rows = [l for l in (zone / "audit-logs" / "cprs" / "queue.jsonl")
                    .read_text().splitlines() if l.strip()]
            self.assertEqual(len(rows), 1, "the row must survive a compile failure")

            # the failure is COUNTED and LOUD
            self.assertEqual(summary["effective_state_recompiled"], 0)
            self.assertEqual(summary["effective_state_recompile_failed"], 1)
            self.assertIn("recompile_failed_rc=3",
                          summary["effective_state_recompile_detail"])
            self.assertIn("effective-state recompile FAILED", err.getvalue())

    def test_missing_compiler_is_typed_and_soft(self):
        with tempfile.TemporaryDirectory() as td:
            zone = _build_zone(td, compiler="missing")
            rep = _write_report(zone, "A mint with no compiler beside the queue.")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                summary = ci.ingest(zone, rep, dry_run=False)

            self.assertEqual(summary["ingested"], 1, summary)
            self.assertEqual(summary["effective_state_recompile_failed"], 1)
            self.assertTrue(
                summary["effective_state_recompile_detail"].startswith(
                    "compiler_not_found:"),
                summary["effective_state_recompile_detail"])
            self.assertIn("recompile skipped", err.getvalue())

    def test_process_exit_status_is_unchanged_when_the_compiler_fails(self):
        """The strongest fail-soft arm: the CLI's exit status, measured."""
        with tempfile.TemporaryDirectory() as td:
            zone = _build_zone(td, compiler="failing")
            rep = _write_report(zone, "An exit-status lesson.")
            proc = subprocess.run(
                [sys.executable, str(_SCRIPT), "--zone-root", str(zone),
                 "--report", str(rep), "--json"],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out["ingested"], 1)
            self.assertEqual(out["effective_state_recompile_failed"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
