#!/usr/bin/env python3
"""Fixtures for obligation-clocked artifact naming in review-close-check.py
(bk-review-close-check-obligation-clock-naming, tic 688).

Ratified cure (/review 687, PROMOTE-as-ray on cgg-ledger#even-tic-review-close-
routing-review-step-8-5-discipline): the consistency artifact must file under the
OBLIGATION's tic — the tic of the mandate that dispatched this review_close_check
cycle — not the executor clock (current.json read at write time). When a run
crosses a tic boundary (cadence supersedes current.json mid-flight), the executor
clock files tic-N evidence under tic-{N+1}-check.json and tic-N reads
never-checked at count=1. Do NOT revert to per-mandate filenames (re-opens the
N!=1 family); the t686 preserve-prior-under-superseded-receipt cure composes
untouched (it keys off the filename stem, whichever clock names it).

Precedence: CLI --obligation-tic/--obligation-mandate-id > CGG_OBLIGATION_* env
(pinned by mogul-runner.sh at snapshot time, inherited by the agent's
subprocesses) > current.json (executor clock — correct only while no boundary
was crossed). The clock source is disclosed in the log row; when an obligation
channel is present and the executor clock differs, the divergence is recorded
first-class (surface-don't-hide), never silently absorbed.

Arms (every documented conditional, both sides):
  1. env obligation clock wins    — CGG_OBLIGATION_TIC=687 with current.json at
                                    688 files tic-687-check.json (the boundary
                                    crossing, cured)
  2. executor-clock fallback      — no obligation channel: current.json names
                                    the artifact (same-tic runs unchanged)
  3. CLI beats env                — --obligation-tic 686 over env 687
  4. divergence disclosed         — log row carries obligation_clock_source and
                                    executor_clock_tic when the clocks differ
  5. superseded-receipt composes  — a changed re-run under the obligation name
                                    still preserves prior bytes (t686 cure)
  6. malformed env fails soft     — non-int CGG_OBLIGATION_TIC falls through to
                                    the executor clock, never crashes the cycle
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

import importlib.util

_spec = importlib.util.spec_from_file_location("review_close_check", HERE / "review-close-check.py")
rcc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rcc)

ENV_TIC = "CGG_OBLIGATION_TIC"
ENV_MID = "CGG_OBLIGATION_MANDATE_ID"


class ObligationClockBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.zone = Path(self.tmp.name)
        (self.zone / "audit-logs" / "cprs").mkdir(parents=True)
        (self.zone / "audit-logs" / "cprs" / "queue.jsonl").write_text("", encoding="utf-8")
        self._saved_env = {k: os.environ.pop(k, None) for k in (ENV_TIC, ENV_MID)}

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def _executor_mandate(self, tic: int):
        p = self.zone / "audit-logs" / "mogul" / "mandates" / "current.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "mandate_id": f"tic-{tic}-executor", "status": "running",
            "tic_context": {"current_tic": tic},
        }), encoding="utf-8")

    def _report_dir(self):
        return self.zone / "audit-logs" / "mogul" / "cycle-reports" / "review-close-checks"

    def _log_rows(self):
        p = self.zone / "audit-logs" / "services" / "review-close-check-log.jsonl"
        if not p.exists():
            return []
        return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


class ObligationClockNaming(ObligationClockBase):
    def test_env_obligation_clock_wins_over_executor_clock(self):
        """Arm 1: the boundary crossing — obligation tic 687 pinned by the runner,
        executor clock already superseded to 688. Evidence files under 687."""
        self._executor_mandate(688)
        os.environ[ENV_TIC] = "687"
        os.environ[ENV_MID] = "tic-687-obligation"
        rcc.run_check(str(self.zone), dry_run=False)
        self.assertTrue((self._report_dir() / "tic-687-check.json").exists(),
                        "artifact must file under the OBLIGATION's tic")
        self.assertFalse((self._report_dir() / "tic-688-check.json").exists(),
                         "executor-clock filing is the cured defect")

    def test_executor_clock_fallback_unchanged(self):
        """Arm 2: no obligation channel — current.json names the artifact
        (same-tic runs keep their existing behavior)."""
        self._executor_mandate(688)
        rcc.run_check(str(self.zone), dry_run=False)
        self.assertTrue((self._report_dir() / "tic-688-check.json").exists())

    def test_cli_beats_env(self):
        """Arm 3: explicit invocation authority outranks the inherited env pin."""
        self._executor_mandate(688)
        os.environ[ENV_TIC] = "687"
        rcc.run_check(str(self.zone), dry_run=False,
                      obligation_tic=686, obligation_mandate_id="tic-686-cli")
        self.assertTrue((self._report_dir() / "tic-686-check.json").exists())
        self.assertFalse((self._report_dir() / "tic-687-check.json").exists())

    def test_divergence_disclosed_in_log_row(self):
        """Arm 4: when the clocks differ, the log row names the source and the
        executor tic — the crossing is surfaced, never silently absorbed."""
        self._executor_mandate(688)
        os.environ[ENV_TIC] = "687"
        rcc.run_check(str(self.zone), dry_run=False)
        rows = self._log_rows()
        self.assertTrue(rows)
        row = rows[-1]
        self.assertEqual(row.get("obligation_clock_source"), "env")
        self.assertEqual(row.get("tic"), 687)
        self.assertEqual(row.get("executor_clock_tic"), 688,
                         "the divergent executor clock must be disclosed")

    def test_no_divergence_field_when_clocks_agree(self):
        """Arm 4 complement: same-tic run — no divergence field emitted."""
        self._executor_mandate(688)
        os.environ[ENV_TIC] = "688"
        rcc.run_check(str(self.zone), dry_run=False)
        row = self._log_rows()[-1]
        self.assertNotIn("executor_clock_tic", row)

    def test_superseded_receipt_composes(self):
        """Arm 5: a changed re-run under the obligation-named stem still
        preserves the prior observation (the t686 cure, undisturbed)."""
        self._executor_mandate(688)
        os.environ[ENV_TIC] = "687"
        rcc.run_check(str(self.zone), dry_run=False)
        # change the queue so the second report differs (a real re-observation)
        (self.zone / "audit-logs" / "cprs" / "queue.jsonl").write_text(
            json.dumps({"id": "cpr_fixture_row", "status": "skipped"}) + "\n",
            encoding="utf-8")
        rcc.run_check(str(self.zone), dry_run=False)
        preserved = self._report_dir() / "superseded" / "tic-687-check.superseded-1.json"
        self.assertTrue(preserved.exists(),
                        "prior observation must be preserved under the obligation stem")
        row = self._log_rows()[-1]
        self.assertIn("superseded_receipt", row)

    def test_malformed_env_tic_fails_soft_to_executor_clock(self):
        """Arm 6: a non-int env tic never crashes the cycle — the channel is
        treated absent and the executor clock names the artifact."""
        self._executor_mandate(688)
        os.environ[ENV_TIC] = "not-a-tic"
        rcc.run_check(str(self.zone), dry_run=False)
        self.assertTrue((self._report_dir() / "tic-688-check.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
