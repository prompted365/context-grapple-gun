#!/usr/bin/env python3
"""Tests for `ladder-audit.py rbd-drill-run` — the RBD doctrine rollback-drill
RE-RUNNER (M1 piece-3 complement; tic-494 memo recommendation #2).

Guards the producer↔consumer contract: run_rbd_drill emits a record into the
EXISTING rollback-drills lane, and load_rbd_demote_evidence (the consumer wired
at tic 504, ratified /review 505) reads it back and computes demote_admissibility.

Every case isolates against a TemporaryDirectory git repo and passes current_tic
explicitly — nothing touches the real canonical zone (Self-Locating Artifact Test
Isolation KI). The producer is read-only on doctrine: git apply --check -R only
verifies; the worktree is never mutated.

Run:  python3 -m unittest test_rbd_drill_run   (from cgg-runtime/scripts/)
"""
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "ladder_audit", os.path.join(_HERE, "ladder-audit.py")
)
la = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(la)


def _git(repo, *args, **kw):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True,
                          text=True, check=True, **kw)


def _init_repo(repo):
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _write(repo, rel, text):
    p = Path(repo) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _commit(repo, msg):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


class TestRbdDrillRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        _init_repo(self.repo)
        # parent commit: a doctrine spec exists
        _write(self.repo, "autonomous_kernel/demo-spec.md",
               "# Demo spec\n\nbaseline body line\n")
        _commit(self.repo, "Tic 900: baseline doctrine")

    def _promote(self, extra=""):
        """The promotion commit (tic 901, CogPR-901) mutates a doctrine surface."""
        _write(self.repo, "autonomous_kernel/demo-spec.md",
               "# Demo spec\n\nbaseline body line\nPROMOTED addition for CogPR-901\n" + extra)
        return _commit(self.repo, "Tic 901: promote CogPR-901 into demo-spec")

    def test_admissible_path_is_reachable(self):
        """A cleanly-revertible promotion with 0 surviving orphan refs computes
        velocity_ratio>=1 / clean / 0-orphans → admissible (the path the dormant
        lane could never reach)."""
        self._promote()
        res = la.run_rbd_drill(self.repo, target_tic=901, current_tic=902,
                               dry_run=True)
        self.assertTrue(res["ok"], res)
        rec = res["record"]
        self.assertIn("CogPR-901", rec["cprs_in_scope"])
        self.assertEqual(rec["files_mutated"], ["autonomous_kernel/demo-spec.md"])
        self.assertTrue(rec["reversion_patch_clean"])
        self.assertEqual(rec["orphaned_references"], 0)
        self.assertGreaterEqual(rec["velocity_ratio"], 1)
        self.assertEqual(rec["verdict"], "ok")
        self.assertEqual(res["would_demote_admissibility"], "admissible")

    def test_unclean_reversion_is_inadmissible(self):
        """A further edit to the promoted lines makes the reverse-apply conflict →
        reversion_patch_clean False → inadmissible_pending_reversion (the honest
        center-hold: no clean undo → no admissible demote)."""
        self._promote()
        # a later commit rewrites the promoted region → reverse-apply conflicts
        _write(self.repo, "autonomous_kernel/demo-spec.md",
               "# Demo spec\n\nTOTALLY rewritten body, conflicts with the revert\n")
        _commit(self.repo, "Tic 902: rewrite demo-spec body")
        res = la.run_rbd_drill(self.repo, target_tic=901, current_tic=903,
                               dry_run=True)
        self.assertTrue(res["ok"], res)
        self.assertFalse(res["record"]["reversion_patch_clean"])
        self.assertEqual(res["would_demote_admissibility"],
                         "inadmissible_pending_reversion")

    def test_orphaned_reference_throttles_admissibility(self):
        """A reference to the promotion's cpr living in a DIFFERENT doctrine file
        (not touched by the revert) is an orphan — it would dangle on reversion →
        inadmissible even when the patch reverts clean."""
        self._promote()
        # a sibling doctrine surface references CogPR-901 and is NOT in the revert set
        _write(self.repo, "autonomous_kernel/sibling-spec.md",
               "# Sibling\n\nsee CogPR-901 for the rule\n")
        _commit(self.repo, "Tic 902: sibling references CogPR-901")
        res = la.run_rbd_drill(self.repo, target_tic=901, current_tic=903,
                               dry_run=True)
        self.assertTrue(res["ok"], res)
        self.assertGreaterEqual(res["record"]["orphaned_references"], 1)
        self.assertEqual(res["would_demote_admissibility"],
                         "inadmissible_pending_reversion")

    def test_dry_run_writes_nothing(self):
        """Dormancy: --dry-run computes the record but the lane is unchanged."""
        self._promote()
        lane = Path(self.repo) / la.ROLLBACK_DRILLS_REL
        before = list(lane.glob("RBD-*.json")) if lane.is_dir() else []
        res = la.run_rbd_drill(self.repo, target_tic=901, current_tic=902,
                               dry_run=True)
        self.assertIsNone(res["wrote"])
        after = list(lane.glob("RBD-*.json")) if lane.is_dir() else []
        self.assertEqual(len(before), len(after))

    def test_activation_writes_and_consumer_reads_it_back(self):
        """The producer↔consumer contract: a real run writes a schema-faithful
        record, and load_rbd_demote_evidence (the consumer) matches it by
        cprs_in_scope ∩ KI-provenance and reads back the SAME drill + verdict."""
        self._promote()
        lane = Path(self.repo) / la.ROLLBACK_DRILLS_REL
        res = la.run_rbd_drill(self.repo, target_tic=901, current_tic=902,
                               dry_run=False)
        self.assertIsNotNone(res["wrote"])
        written = Path(res["wrote"])
        self.assertTrue(written.exists())
        on_disk = json.loads(written.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["drill_id"], res["record"]["drill_id"])

        # consumer reads it back — KI body carries the matching provenance ref
        ki_body = "Some KI body. promoted from CogPR-901. body."
        ev = la.load_rbd_demote_evidence(self.repo, "demo-ki", ki_body=ki_body)
        self.assertTrue(ev["matched"], ev)
        self.assertEqual(ev["drill_id"], res["record"]["drill_id"])
        self.assertEqual(ev["demote_admissibility"], "admissible")

    def test_unresolved_target_fails_soft(self):
        """An unresolvable target returns ok:False, never raises."""
        res = la.run_rbd_drill(self.repo, target_tic=None, target_commit="deadbeef",
                               current_tic=902, dry_run=True)
        self.assertFalse(res["ok"])
        self.assertIsNone(res["wrote"])


class TestRbdAutodrill(unittest.TestCase):
    """The /review-flow AUTO-INVOCATION of the re-runner (tic 507; build-and-gate).

    Guards the dormancy (plan-only, no write) and activation (fires → consumer reads
    fresh admissible) halves, the none-needed short-circuit, the unresolved-target
    degenerate, and the backtick/unicode-arrow provenance resolver. Isolated tmp git
    repos; the real zone is never touched (Self-Locating Artifact Test Isolation)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        _init_repo(self.repo)
        _write(self.repo, "autonomous_kernel/demo-spec.md",
               "# Demo spec\n\nbaseline body line\n")
        _commit(self.repo, "Tic 900: baseline doctrine")
        _write(self.repo, "autonomous_kernel/demo-spec.md",
               "# Demo spec\n\nbaseline body line\nPROMOTED addition for CogPR-901\n")
        _commit(self.repo, "Tic 901: promote CogPR-901 into demo-spec")
        # a KI body whose provenance resolves to the tic-901 promotion
        self.ki_body = "Demo KI body. `promoted_tic`: `901`. promoted from CogPR-901."

    def test_resolve_ki_promotion_target_parses_backtick_and_arrow(self):
        """The resolver reads backtick-wrapped `promoted_tic` tags and falls back to a
        unicode-arrow `(tic B->R)` provenance breadcrumb."""
        r1 = la._resolve_ki_promotion_target(self.ki_body)
        self.assertEqual(r1["promoted_tic"], 901)
        self.assertIn("CogPR-901", r1["cprs"])
        r2 = la._resolve_ki_promotion_target(
            "no tag here, but promoted from CogPR-7 (tic 504 → 505 PROMOTE).")
        self.assertEqual(r2["promoted_tic"], 505)

    def test_dormant_plans_but_writes_nothing(self):
        """DORMANT (ratified=False): surfaces the would-fire plan, writes no drill."""
        lane = Path(self.repo) / la.ROLLBACK_DRILLS_REL
        before = list(lane.glob("RBD-*.json")) if lane.is_dir() else []
        res = la.rbd_autodrill_for_demote(
            self.repo, "demo-ki", ki_body=self.ki_body, current_tic=902,
            ratified=False)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["action"], "would_autodrill")
        self.assertFalse(res["ratified"])
        self.assertEqual(res["plan"]["target_tic"], 901)
        self.assertIn("CogPR-901", res["plan"]["cprs"])
        self.assertIsNone(res["wrote"])
        after = list(lane.glob("RBD-*.json")) if lane.is_dir() else []
        self.assertEqual(len(before), len(after))

    def test_ratified_fires_and_consumer_reads_admissible(self):
        """RATIFIED (ratified=True): fires the re-runner (writes a drill), and the
        consumer reads back a FRESH `admissible` — the activation proof."""
        res = la.rbd_autodrill_for_demote(
            self.repo, "demo-ki", ki_body=self.ki_body, current_tic=902,
            ratified=True)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["action"], "autodrilled")
        self.assertTrue(res["ratified"])
        self.assertIsNotNone(res["wrote"])
        self.assertTrue(Path(res["wrote"]).exists())
        # before was absent, after is admissible — the gate's admissible path reached
        self.assertEqual(res["evidence_before"]["demote_admissibility"],
                         "inadmissible_rbd_absent")
        self.assertEqual(res["demote_admissibility"], "admissible")

    def test_none_needed_when_fresh_proof_exists(self):
        """If a fresh drill already resolves the KI (admissible), autodrill is a
        no-op (action none_needed) and writes nothing further."""
        # pre-seed a fresh admissible drill for CogPR-901
        la.run_rbd_drill(self.repo, target_tic=901, current_tic=902, dry_run=False)
        lane = Path(self.repo) / la.ROLLBACK_DRILLS_REL
        before = list(lane.glob("RBD-*.json"))
        res = la.rbd_autodrill_for_demote(
            self.repo, "demo-ki", ki_body=self.ki_body, current_tic=902,
            ratified=True)
        self.assertEqual(res["action"], "none_needed")
        self.assertIsNone(res["wrote"])
        after = list(lane.glob("RBD-*.json"))
        self.assertEqual(len(before), len(after))

    def test_unresolved_target_when_no_provenance(self):
        """A KI body with no resolvable promotion tic/cprs returns unresolved_target
        and writes nothing, even when ratified."""
        res = la.rbd_autodrill_for_demote(
            self.repo, "mystery-ki", ki_body="a body with no provenance markers",
            current_tic=902, ratified=True)
        self.assertEqual(res["action"], "unresolved_target")
        self.assertIsNone(res["wrote"])


if __name__ == "__main__":
    unittest.main()
