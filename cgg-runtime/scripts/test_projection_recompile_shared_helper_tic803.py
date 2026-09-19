#!/usr/bin/env python3
"""test_projection_recompile_shared_helper_tic803.py — the ONE shared
recompile helper, and the proof that all FIVE writers call THAT ONE.

FIX-SITE: /review 803 round 2 (Ruling A), Architect-ratified on the recommended
option verbatim ("One shared helper, all five writers, today"). Ruling receipt:
  audit-logs/governance/receipts/2026-09-19-tic803-projection-shared-recompile-helper-ruling.md
It EXTENDS — does not reverse — the /review 801 round-2 ruling ("Key the writer
on mutation").

THE DEFECT UNDER CURE
---------------------
At tic 802 the recompile body existed in THREE copies held together by diligence
(queue-lifecycle-writeback's ratified original + faithful copies in
cogpr-ingest.py and cpr-extract.py) while THREE further queue MUTATORS —
pattern_miner.py, cpr-gate-advance.py, cpr-enrichment-scanner.py — carried no
copy at all and left the derived projection stale after every mutation. That is
F-802-B4 stacked on F-802-B1/B2, all handed up by the tic-802 build seat.

DOES-NOT-SATISFY RIDER (travels verbatim, on ONE unbroken line so a byte-exact
grep resolves it):
this increment does NOT add a reader-side staleness detector, does NOT prove the compiled per-id states are correct, does NOT test two writers racing, and does NOT make the projection authoritative over the queue — `queue.jsonl` latest-per-id remains the only authority; the projection is a derived convenience that is now writer-fresh for five of six writers by construction and for the sixth by its own code.

ARMS
----
  1. SINGLE OWNER — all five writers' `recompile_effective_state` is the SAME
     function object as lib.effective_state_recompile's. This is the increment's
     literal claim ("one contract and five call sites, not three copies and two
     gaps") and the only arm that can catch a silent re-divergence.
  2. ZONE LAW by EXECUTION — the helper compiles the zone that owns the QUEUE IT
     WAS HANDED, and does so identically from TWO different working directories.
     Nothing is derived from any script's __file__ (CLI shape 22).
  3..5. FAIL-SOFT, typed, never raising: missing compiler, non-zero compiler,
     unresolvable tic. Each returns (False, typed_detail) and says so on stderr.
  6. SUCCESS detail shape + the stamp equals the live queue's sha256.

EVIDENCE CLASS: FIXTURE-GREEN. Every arm runs in a temp zone under the test's
own tmpdir; the live audit-logs/cprs/queue.jsonl is NEVER touched and no writer
is ever run against it. Fixture-green is not live-green and not trainer-green.

Run:  python3 -m pytest -q scripts/test_projection_recompile_shared_helper_tic803.py
"""

import hashlib
import importlib.util
import io
import json
import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from lib.effective_state_recompile import (  # noqa: E402
    recompile_effective_state, resolve_recompile_tic)

FIXTURE_TIC = 803

FAILING_COMPILER = (
    "#!/usr/bin/env python3\n"
    "import sys\n"
    "print('fixture compiler: deliberate non-zero exit', file=sys.stderr)\n"
    "sys.exit(7)\n"
)


def _real_compiler():
    """The real compiler is a fixture INPUT (copied into each temp zone, never
    run against the live tree). CGG_QUEUE_STATE_COMPILE is the declared seam for
    the NEGATIVE CONTROL harness, which runs a reverted copy of this suite from
    OUTSIDE the measured tree and so cannot walk up to the federation root."""
    env = os.environ.get("CGG_QUEUE_STATE_COMPILE", "")
    if env and Path(env).is_file():
        return Path(env)
    for d in [_HERE, *_HERE.parents]:
        cand = d / "audit-logs" / "cprs" / "queue_state_compile.py"
        if cand.is_file():
            return cand
    raise unittest.SkipTest("queue_state_compile.py not locatable for fixtures")


def build_zone(td, compiler="real", with_tics=True, rows=()):
    """A minimal but REAL zone: .ticzone + a tic log + a queue (+ the compiler
    beside the queue, per the mode)."""
    zone = Path(td)
    (zone / ".ticzone").write_text(json.dumps(
        {"name": "fixturezone803", "audit_logs_path": "audit-logs"}))
    if with_tics:
        tics = zone / "audit-logs" / "tics"
        tics.mkdir(parents=True, exist_ok=True)
        (tics / "2026-09.jsonl").write_text(json.dumps({
            "type": "tic", "count_mode": "counted",
            "domain_counter_after": FIXTURE_TIC,
            "global_counter_after": FIXTURE_TIC,
        }) + "\n")
    cprs = zone / "audit-logs" / "cprs"
    cprs.mkdir(parents=True, exist_ok=True)
    (cprs / "queue.jsonl").write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
    if compiler == "real":
        shutil.copy2(_real_compiler(), cprs / "queue_state_compile.py")
    elif compiler == "failing":
        (cprs / "queue_state_compile.py").write_text(FAILING_COMPILER)
    return zone


def queue_path(zone):
    return Path(zone) / "audit-logs" / "cprs" / "queue.jsonl"


def queue_sha(zone):
    return hashlib.sha256(queue_path(zone).read_bytes()).hexdigest()


def projection(zone):
    return Path(zone) / "audit-logs" / "cprs" / "effective-state" / "effective_state.json"


ROW = {"id": "cpr_tic803_fixture", "status": "extracted", "birth_tic": 800,
       "lesson": "a fixture row so the compiler has something to project",
       "source": "fixture.md"}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# The closed call-site set the ruling names: five writers, one contract.
FIVE_WRITERS = ("pattern_miner.py", "cpr-gate-advance.py",
                "cpr-enrichment-scanner.py", "cogpr-ingest.py", "cpr-extract.py")


class AllFiveWritersShareTheOneOwner(unittest.TestCase):
    """ARM 1 — the increment's literal claim, mechanically checked."""

    def test_every_writer_binds_the_shared_helper_function_object(self):
        for i, name in enumerate(FIVE_WRITERS):
            with self.subTest(writer=name):
                mod = _load(f"writer_tic803_{i}", _HERE / name)
                self.assertTrue(
                    hasattr(mod, "recompile_effective_state"),
                    f"{name} does not bind recompile_effective_state at all")
                self.assertIs(
                    mod.recompile_effective_state, recompile_effective_state,
                    f"{name} binds a DIFFERENT recompile_effective_state — the "
                    f"three-copies-held-together-by-diligence shape (F-802-B4) "
                    f"has re-formed")

    def test_no_writer_keeps_a_private_copy_of_the_body(self):
        """A private `def recompile_effective_state` in a writer would shadow
        the import and silently re-open the drift."""
        for name in FIVE_WRITERS:
            with self.subTest(writer=name):
                text = (_HERE / name).read_text(encoding="utf-8")
                self.assertNotIn("def recompile_effective_state", text)
                self.assertNotIn("def _resolve_recompile_tic", text)
                self.assertIn(
                    "from lib.effective_state_recompile import "
                    "recompile_effective_state", text)


class ZoneLawByExecution(unittest.TestCase):
    """ARM 2 — CLI shape 22. The zone comes from the QUEUE PATH, never __file__."""

    def test_compiles_the_zone_of_the_queue_it_was_handed(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, rows=[ROW])
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                ok, detail = recompile_effective_state(queue_path(zone))
            self.assertTrue(ok, f"{detail} / stderr={err.getvalue()}")
            es = json.loads(projection(zone).read_text())
            self.assertEqual(Path(es["meta"]["queue_path"]).resolve(),
                             queue_path(zone).resolve())
            self.assertEqual(es["meta"]["queue_sha256"], queue_sha(zone))
            self.assertIn(zone.resolve(), projection(zone).resolve().parents)

    def test_same_answer_from_two_different_working_directories(self):
        """The source copy lives under cgg-runtime/scripts/lib/; the INSTALLED
        copy lives under ~/.claude/cgg-runtime/scripts/lib/, whose ancestry
        carries no .ticzone. If any zone path were __file__-derived or
        cwd-derived, these two runs would diverge."""
        answers = []
        for cwd in (Path(tempfile.gettempdir()), Path.home()):
            with tempfile.TemporaryDirectory() as td:
                zone = build_zone(td, rows=[ROW])
                prev = os.getcwd()
                os.chdir(cwd)
                try:
                    with contextlib.redirect_stderr(io.StringIO()):
                        ok, _ = recompile_effective_state(queue_path(zone))
                finally:
                    os.chdir(prev)
                self.assertTrue(ok)
                es = json.loads(projection(zone).read_text())
                answers.append((
                    Path(es["meta"]["queue_path"]).resolve() == queue_path(zone).resolve(),
                    es["meta"]["queue_sha256"] == queue_sha(zone),
                    zone.resolve() in projection(zone).resolve().parents,
                ))
        self.assertEqual(answers[0], (True, True, True))
        self.assertEqual(answers[0], answers[1],
                         "zone resolution must not depend on the working directory")

    def test_clock_reads_the_queues_own_zone(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, rows=[ROW])
            self.assertEqual(resolve_recompile_tic(queue_path(zone)), FIXTURE_TIC)


class FailSoftIsTypedAndNeverRaises(unittest.TestCase):
    """ARMS 3-5 — a derived-cache miss NEVER fails the constitutional write."""

    def test_missing_compiler(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, compiler="missing", rows=[ROW])
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                ok, detail = recompile_effective_state(queue_path(zone))
            self.assertFalse(ok)
            self.assertTrue(detail.startswith("compiler_not_found:"), detail)
            self.assertIn("recompile skipped", err.getvalue())
            self.assertFalse(projection(zone).exists())

    def test_nonzero_compiler(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, compiler="failing", rows=[ROW])
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                ok, detail = recompile_effective_state(queue_path(zone))
            self.assertFalse(ok)
            self.assertIn("recompile_failed_rc=7", detail)
            self.assertIn("effective-state recompile FAILED", err.getvalue())

    def test_unresolvable_tic(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, with_tics=False, rows=[ROW])
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                ok, detail = recompile_effective_state(queue_path(zone))
            self.assertFalse(ok)
            self.assertTrue(detail.startswith("no_tic_resolvable:"), detail)
            self.assertIn("recompile SKIPPED", err.getvalue())

    def test_explicit_tic_overrides_the_clock(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, with_tics=False, rows=[ROW])
            with contextlib.redirect_stderr(io.StringIO()):
                ok, detail = recompile_effective_state(queue_path(zone), current_tic=777)
            self.assertTrue(ok, detail)
            self.assertEqual(detail, "recompiled_at_tic=777")
            self.assertEqual(json.loads(projection(zone).read_text())["meta"]["current_tic"],
                             777)


if __name__ == "__main__":
    unittest.main(verbosity=2)
