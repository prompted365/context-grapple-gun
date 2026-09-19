#!/usr/bin/env python3
"""test_pattern_miner_projection_recompile_tic803.py — the pattern miner's
adoption of the ONE shared recompile helper.

FIX-SITE: /review 803 round 2 (Ruling A), Architect-ratified on the recommended
option verbatim ("One shared helper, all five writers, today"). Ruling receipt:
  audit-logs/governance/receipts/2026-09-19-tic803-projection-shared-recompile-helper-ruling.md

THE DEFECT UNDER CURE (F-802-B1, HIGH, handed up by the tic-802 build seat)
--------------------------------------------------------------------------
pattern_miner.py is a MINT-SIDE queue appender — `atomic_append_jsonl(queue_path,
env)` at the envelope-emission boundary — and its only two mentions of
`queue_state_compile` were COMMENTS. Every mined mint therefore left
audit-logs/cprs/effective-state/ stale until the next /review writeback: the
exact window the /review 801 ruling closed for cogpr-ingest and cpr-extract.
The tic-804 `pattern_mining` fire is the expected first LIVE witness of this arm.

DOES-NOT-SATISFY RIDER (travels verbatim, on ONE unbroken line so a byte-exact
grep resolves it):
this increment does NOT add a reader-side staleness detector, does NOT prove the compiled per-id states are correct, does NOT test two writers racing, and does NOT make the projection authoritative over the queue — `queue.jsonl` latest-per-id remains the only authority; the projection is a derived convenience that is now writer-fresh for five of six writers by construction and for the sixth by its own code.

ARMS
----
  1. a SUCCESSFUL emission moves `meta.queue_sha256` to the live queue's sha256
     and the projection lands in the zone the append wrote to
  2. a ZERO-EMISSION run (every candidate refused by the id-dedup valve) mutates
     nothing and must move nothing — projection bytes AND mtime unmoved
  3. a DRY-RUN (the full CLI, --dry-run) writes no queue row and no projection
  4. FAIL-SOFT: a non-zero compiler still lands the envelopes, the counters say
     so, stderr says so, and the CLI exit status is unchanged

VACUITY NOTE (declared, not discovered): arms 2 and 3 assert the ABSENCE of a
recompile, so a fully reverted build also passes them. Their discriminating
power is zero under the negative control and that is stated in the NC prediction
file BEFORE the control runs. The teeth are in arms 1 and 4.

EVIDENCE CLASS: FIXTURE-GREEN. Every arm runs in a temp zone; the live
audit-logs/cprs/queue.jsonl is NEVER touched and the miner is never run against
it.
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
_SCRIPT = _HERE / "pattern_miner.py"
FIXTURE_TIC = 803

FAILING_COMPILER = (
    "#!/usr/bin/env python3\n"
    "import sys\n"
    "print('fixture compiler: deliberate non-zero exit', file=sys.stderr)\n"
    "sys.exit(5)\n"
)


def _load():
    spec = importlib.util.spec_from_file_location("pattern_miner_tic803", str(_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pattern_miner_tic803"] = mod
    spec.loader.exec_module(mod)
    return mod


pm = _load()


def _real_compiler():
    env = os.environ.get("CGG_QUEUE_STATE_COMPILE", "")
    if env and Path(env).is_file():
        return Path(env)
    for d in [_HERE, *_HERE.parents]:
        cand = d / "audit-logs" / "cprs" / "queue_state_compile.py"
        if cand.is_file():
            return cand
    raise unittest.SkipTest("queue_state_compile.py not locatable for fixtures")


def build_zone(td, compiler="real", queue_rows=()):
    zone = Path(td)
    (zone / ".ticzone").write_text(json.dumps(
        {"name": "fixturezone803", "audit_logs_path": "audit-logs"}))
    tics = zone / "audit-logs" / "tics"
    tics.mkdir(parents=True, exist_ok=True)
    (tics / "2026-09.jsonl").write_text(json.dumps({
        "type": "tic", "count_mode": "counted",
        "domain_counter_after": FIXTURE_TIC, "global_counter_after": FIXTURE_TIC,
    }) + "\n")
    cprs = zone / "audit-logs" / "cprs"
    cprs.mkdir(parents=True, exist_ok=True)
    (cprs / "queue.jsonl").write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in queue_rows))
    (zone / "audit-logs" / "signals").mkdir(parents=True, exist_ok=True)
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


def a_pattern(pid="pat_tic803fixture01"):
    """A pattern that clears all three write-boundary admission gates: it is not
    a carrier-pointer stub, its source is not terminal, and its id is fresh."""
    return {
        "id": pid,
        "pattern": ("Governance rule: a queue mutator must recompile the derived "
                    "projection for the zone that owns the queue it wrote."),
        "recurrence_kind": "cross_site_same_domain",
        "recurrence_scope": "domain",
        "observation_count": 4,
        "placement_target": "domain",
        "confidence_tier": "T2",
        "observed_in": [],
        "source_cpr": "",
        "subsystem": "cprs",
    }


def emit(zone, patterns):
    """Drive the miner's real emission boundary — the function carrying the
    ruled call site. mine_patterns only ever reaches it with
    `new_patterns and not dry_run`."""
    pm._reset_run_counters()
    topo = pm.birth_topology(str(zone))
    return pm.emit_pattern_envelopes(patterns, str(qp(zone)), topo, FIXTURE_TIC)


class SuccessfulEmissionMovesTheProjection(unittest.TestCase):
    """ARM 1 — the duty: stamp equals the LIVE fixture queue's sha."""

    def test_emission_moves_queue_sha256_to_the_live_queue_sha(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                envelopes = emit(zone, [a_pattern()])
            self.assertEqual(len(envelopes), 1,
                             f"{envelopes} / stderr={err.getvalue()}")
            self.assertEqual(pm.RUN_COUNTERS["effective_state_recompiled"], 1,
                             f"{dict(pm.RUN_COUNTERS)} / stderr={err.getvalue()}")
            self.assertEqual(pm.RUN_COUNTERS["effective_state_recompile_failed"], 0)
            self.assertEqual(pm.RUN_COUNTERS["effective_state_recompile_detail"],
                             f"recompiled_at_tic={FIXTURE_TIC}")

            es = json.loads(proj(zone).read_text())
            self.assertEqual(es["meta"]["queue_sha256"], qsha(zone),
                             "the projection's stamp must equal the LIVE queue's sha256")
            self.assertEqual(es["meta"]["current_tic"], FIXTURE_TIC)

    def test_recompile_targets_the_queue_the_append_wrote(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            with contextlib.redirect_stderr(io.StringIO()):
                emit(zone, [a_pattern()])
            es = json.loads(proj(zone).read_text())
            self.assertEqual(Path(es["meta"]["queue_path"]).resolve(), qp(zone).resolve())
            self.assertIn(zone.resolve(), proj(zone).resolve().parents)


class NoMutationFiresNoRecompile(unittest.TestCase):
    """ARM 2 — VACUOUS UNDER THE NEGATIVE CONTROL (declared in advance)."""

    def test_id_dedup_refusal_leaves_the_projection_byte_and_mtime_identical(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            pat = a_pattern()
            with contextlib.redirect_stderr(io.StringIO()):
                first = emit(zone, [pat])
            self.assertEqual(len(first), 1)
            before_bytes = proj(zone).read_bytes()
            before_mtime = proj(zone).stat().st_mtime_ns
            queue_before = qp(zone).read_bytes()

            # the SAME pattern re-mines to the SAME content-deterministic id, so
            # GATE 3 (the id-keyed re-flood valve) refuses it: zero mutation.
            with contextlib.redirect_stderr(io.StringIO()):
                second = emit(zone, [pat])

            self.assertEqual(second, [], "the dedup valve must refuse the re-mint")
            self.assertEqual(pm.RUN_COUNTERS["effective_state_recompiled"], 0)
            self.assertEqual(pm.RUN_COUNTERS["effective_state_recompile_detail"], "")
            self.assertEqual(proj(zone).read_bytes(), before_bytes,
                             "a zero-mutation run must not rewrite the projection")
            self.assertEqual(proj(zone).stat().st_mtime_ns, before_mtime,
                             "a zero-mutation run must not even touch the projection")
            self.assertEqual(qp(zone).read_bytes(), queue_before)

    def test_dry_run_cli_writes_no_queue_row_and_no_projection(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td)
            proc = subprocess.run(
                [sys.executable, str(_SCRIPT), "--project-dir", str(zone),
                 "--dry-run", "--json"],
                capture_output=True, text=True, timeout=180)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out["admission_counters"]["effective_state_recompiled"], 0)
            self.assertEqual(qp(zone).read_bytes(), b"")
            self.assertFalse(proj(zone).exists(),
                             "a dry-run must not produce a projection")


class RecompileIsFailSoft(unittest.TestCase):
    """ARM 4 — a derived-cache miss NEVER fails the mint."""

    def test_nonzero_compiler_still_lands_the_envelopes_and_counts_the_failure(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, compiler="failing")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                envelopes = emit(zone, [a_pattern()])

            self.assertEqual(len(envelopes), 1, "the mint must survive a compile failure")
            rows = [l for l in qp(zone).read_text().splitlines() if l.strip()]
            self.assertEqual(len(rows), 1, "the appended row must survive")

            self.assertEqual(pm.RUN_COUNTERS["effective_state_recompiled"], 0)
            self.assertEqual(pm.RUN_COUNTERS["effective_state_recompile_failed"], 1)
            self.assertIn("recompile_failed_rc=5",
                          pm.RUN_COUNTERS["effective_state_recompile_detail"])
            self.assertIn("effective-state recompile FAILED", err.getvalue())

    def test_missing_compiler_is_typed_and_soft(self):
        with tempfile.TemporaryDirectory() as td:
            zone = build_zone(td, compiler="missing")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                envelopes = emit(zone, [a_pattern()])
            self.assertEqual(len(envelopes), 1)
            self.assertEqual(pm.RUN_COUNTERS["effective_state_recompile_failed"], 1)
            self.assertTrue(
                pm.RUN_COUNTERS["effective_state_recompile_detail"].startswith(
                    "compiler_not_found:"),
                pm.RUN_COUNTERS["effective_state_recompile_detail"])
            self.assertIn("recompile skipped", err.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
