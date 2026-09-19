#!/usr/bin/env python3
"""test_cpr_gate_advance_projection_recompile_tic803.py — the gate reconciler's
adoption of the ONE shared recompile helper.

FIX-SITE: /review 803 round 2 (Ruling A), Architect-ratified on the recommended
option verbatim ("One shared helper, all five writers, today"). Ruling receipt:
  audit-logs/governance/receipts/2026-09-19-tic803-projection-shared-recompile-helper-ruling.md

THE DEFECT UNDER CURE (F-802-B2, MEDIUM, handed up by the tic-802 build seat)
-----------------------------------------------------------------------------
cpr-gate-advance.py APPENDS `tic_gated -> enrichment_needed` transition rows
under flock and had ZERO occurrences of `queue_state_compile`. It is a lifecycle
writer rather than a mint writer, but it MUTATES the queue all the same — the
queue's sha256 moves, so `meta.queue_sha256` is invalidated and the projection is
stale. "Key the writer on mutation" is a principle whose consumer set is larger
than the two scripts the /review 801 ruling named.

DOES-NOT-SATISFY RIDER (travels verbatim, on ONE unbroken line so a byte-exact
grep resolves it):
this increment does NOT add a reader-side staleness detector, does NOT prove the compiled per-id states are correct, does NOT test two writers racing, and does NOT make the projection authoritative over the queue — `queue.jsonl` latest-per-id remains the only authority; the projection is a derived convenience that is now writer-fresh for five of six writers by construction and for the sixth by its own code.

ARMS
----
  1. a SUCCESSFUL advance moves `meta.queue_sha256` to the live queue's sha256,
     and the projection lands in the zone the transition row was appended to
  2. a DRY-RUN advances nothing and writes no projection
  3. an ALL-RACED run (the write-side terminal-valve guard skips every
     candidate, so ZERO rows land) writes no projection — the "failed mutation"
     arm for this writer, and the one that discriminates a naive
     `if not dry_run:` placement from the ruled `advanced > 0` gate
  4. FAIL-SOFT: a non-zero compiler still lands the transition row, the counters
     say so, stderr says so, and the CLI exit status is unchanged

VACUITY NOTE (declared, not discovered): arm 2 asserts the ABSENCE of a
recompile and is therefore vacuous under the negative control. Arm 3 is NOT
vacuous in the same way — under a reverted build no recompile exists at all, so
it too passes; it is declared vacuous in the NC prediction file BEFORE the
control runs. The teeth are in arms 1 and 4.

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
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE / "cpr-gate-advance.py"
FIXTURE_TIC = 803

FAILING_COMPILER = (
    "#!/usr/bin/env python3\n"
    "import sys\n"
    "print('fixture compiler: deliberate non-zero exit', file=sys.stderr)\n"
    "sys.exit(4)\n"
)


def _load(name="cpr_gate_advance_tic803"):
    spec = importlib.util.spec_from_file_location(name, str(_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ga = _load()


def _real_compiler():
    env = os.environ.get("CGG_QUEUE_STATE_COMPILE", "")
    if env and Path(env).is_file():
        return Path(env)
    for d in [_HERE, *_HERE.parents]:
        cand = d / "audit-logs" / "cprs" / "queue_state_compile.py"
        if cand.is_file():
            return cand
    raise unittest.SkipTest("queue_state_compile.py not locatable for fixtures")


GATED = {"id": "cpr_tic803_gated", "status": "tic_gated", "birth_tic": 795,
         "lesson": "a gated row whose baseline exists on disk",
         "source": "fixture.md", "maturity_tics": 2}


def build_zone(td, compiler="real"):
    zone = Path(td)
    (zone / ".ticzone").write_text(json.dumps(
        {"name": "fixturezone803", "audit_logs_path": "audit-logs"}))
    al = zone / "audit-logs"
    (al / "tics").mkdir(parents=True, exist_ok=True)
    (al / "tics" / "2026-09.jsonl").write_text(json.dumps({
        "type": "tic", "count_mode": "counted",
        "domain_counter_after": FIXTURE_TIC, "global_counter_after": FIXTURE_TIC,
    }) + "\n")
    cprs = al / "cprs"
    cprs.mkdir(parents=True, exist_ok=True)
    (cprs / "queue.jsonl").write_text(
        json.dumps(GATED, separators=(",", ":")) + "\n")
    enr = al / "governance" / "enrichment"
    enr.mkdir(parents=True, exist_ok=True)
    (enr / f"{GATED['id']}.consolidated.json").write_text(json.dumps(
        {"id": GATED["id"], "agreements": [{"value": "operational"}]}))
    if compiler == "real":
        shutil.copy2(_real_compiler(), cprs / "queue_state_compile.py")
    elif compiler == "failing":
        (cprs / "queue_state_compile.py").write_text(FAILING_COMPILER)
    return zone


def qp(zone):
    return Path(zone) / "audit-logs" / "cprs" / "queue.jsonl"


def qsha(zone):
    return hashlib.sha256(qp(zone).read_bytes()).hexdigest()


def proj(zone):
    return Path(zone) / "audit-logs" / "cprs" / "effective-state" / "effective_state.json"


class SuccessfulAdvanceMovesTheProjection(unittest.TestCase):
    """ARM 1 — the duty: stamp equals the LIVE fixture queue's sha."""

    def test_advance_moves_queue_sha256_to_the_live_queue_sha(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                advanced = ga.advance_gated(str(zone), quiet=True)
            self.assertEqual(advanced, 1, err.getvalue())
            self.assertEqual(ga.RUN_COUNTERS["effective_state_recompiled"], 1,
                             f"{ga.RUN_COUNTERS} / stderr={err.getvalue()}")
            self.assertEqual(ga.RUN_COUNTERS["effective_state_recompile_failed"], 0)
            self.assertEqual(ga.RUN_COUNTERS["effective_state_recompile_detail"],
                             f"recompiled_at_tic={FIXTURE_TIC}")

            es = json.loads(proj(zone).read_text())
            self.assertEqual(es["meta"]["queue_sha256"], qsha(zone),
                             "the projection's stamp must equal the LIVE queue's sha256")
            self.assertEqual(Path(es["meta"]["queue_path"]).resolve(), qp(zone).resolve())
            self.assertIn(zone.resolve(), proj(zone).resolve().parents)

    def test_the_transition_row_landed_and_is_the_latest_per_id(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            with contextlib.redirect_stderr(io.StringIO()):
                ga.advance_gated(str(zone), quiet=True)
            rows = [json.loads(l) for l in qp(zone).read_text().splitlines() if l.strip()]
            self.assertEqual(len(rows), 2, "append-only: history row + transition row")
            self.assertEqual(rows[0]["status"], "tic_gated")
            self.assertEqual(rows[-1]["status"], "enrichment_needed")


class NoMutationFiresNoRecompile(unittest.TestCase):
    """ARMS 2-3 — VACUOUS UNDER THE NEGATIVE CONTROL (declared in advance)."""

    def test_dry_run_writes_no_row_and_no_projection(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            before = qp(zone).read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                advanced = ga.advance_gated(str(zone), dry_run=True, quiet=True)
            self.assertEqual(advanced, 1, "dry-run still REPORTS what it would do")
            self.assertEqual(qp(zone).read_bytes(), before, "a dry-run must write nothing")
            self.assertEqual(ga.RUN_COUNTERS["effective_state_recompiled"], 0)
            self.assertFalse(proj(zone).exists(),
                             "a dry-run must not produce a projection")

    def test_all_raced_skip_is_a_zero_row_mutation_and_moves_nothing(self):
        """The write-side terminal-valve guard skips every candidate, so
        `advanced` falls to 0 and NOTHING landed. A placement gated only on
        `not dry_run` would recompile here against an unchanged queue."""
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            real_append = ga.append_transitions

            def race_everything(queue_path, update_map):
                # simulate a concurrent writer having moved every id after our
                # read: the guard returns them all as raced, writes nothing.
                return [(eid, e.get("prior_status"), "promoted")
                        for eid, e in update_map.items()]

            ga.append_transitions = race_everything
            try:
                before = qp(zone).read_bytes()
                with contextlib.redirect_stderr(io.StringIO()):
                    advanced = ga.advance_gated(str(zone), quiet=True)
            finally:
                ga.append_transitions = real_append

            self.assertEqual(advanced, 0, "every candidate raced; zero rows landed")
            self.assertEqual(qp(zone).read_bytes(), before)
            self.assertEqual(ga.RUN_COUNTERS["effective_state_recompiled"], 0)
            self.assertEqual(ga.RUN_COUNTERS["effective_state_recompile_detail"], "")
            self.assertFalse(proj(zone).exists(),
                             "a zero-row mutation must not produce a projection")


class RecompileIsFailSoft(unittest.TestCase):
    """ARM 4 — a derived-cache miss NEVER fails the transition write."""

    def test_nonzero_compiler_still_lands_the_transition(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, compiler="failing")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                advanced = ga.advance_gated(str(zone), quiet=True)
            self.assertEqual(advanced, 1)
            rows = [l for l in qp(zone).read_text().splitlines() if l.strip()]
            self.assertEqual(len(rows), 2, "the transition row must survive")
            self.assertEqual(ga.RUN_COUNTERS["effective_state_recompile_failed"], 1)
            self.assertIn("recompile_failed_rc=4",
                          ga.RUN_COUNTERS["effective_state_recompile_detail"])
            self.assertIn("effective-state recompile FAILED", err.getvalue())

    def test_cli_exit_status_is_unchanged_when_the_compiler_fails(self):
        """The strongest fail-soft arm: the CLI's exit status, measured."""
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, compiler="failing")
            proc = subprocess.run(
                [sys.executable, str(_SCRIPT), "--project-dir", str(zone), "--quiet"],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("effective-state recompile FAILED", proc.stderr)
            rows = [l for l in qp(zone).read_text().splitlines() if l.strip()]
            self.assertEqual(len(rows), 2)

    def test_missing_compiler_is_typed_and_soft(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, compiler="missing")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                advanced = ga.advance_gated(str(zone), quiet=True)
            self.assertEqual(advanced, 1)
            self.assertTrue(
                ga.RUN_COUNTERS["effective_state_recompile_detail"].startswith(
                    "compiler_not_found:"),
                ga.RUN_COUNTERS["effective_state_recompile_detail"])
            self.assertIn("recompile skipped", err.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
