#!/usr/bin/env python3
"""Tests for `ladder-audit.py staleness-scan` — the M2 staleness DETECTION half
(S0 detector + S1 classifier; staleness-routing-spec.md §3–§4).

Guards the read-only DETECTION contract: the scan COMPOSES the existing staleness
signals (last_validated_tic freshness + held-dissonance-stale + coverage-stale) into a
candidate set + a PROPOSED re-examination route, WITHOUT mutating doctrine, persisting
a signal, opening an arena, or wiring into cadence. Every proposed route is a
re-examination (re-validate / re-test / re-audit), NEVER a demote — the demote-class
ACTION half (S2) is /review-gated AND precondition-gated AND RBD-gated, and is NOT in
this scan.

Each case isolates against a TemporaryDirectory — nothing touches the real canonical
zone (Self-Locating Artifact Test Isolation KI), and current_tic is always passed
explicitly (Temporal Scope Discipline). The held-dissonance and coverage signals reuse
already-tested readers (list_downaudit_findings / run_downlane_campaign); these tests
cover the NEW logic — the freshness loader, the classifier, and the read-only contract.

Run:  python3 -m unittest test_staleness_scan   (from cgg-runtime/scripts/)
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "ladder_audit", os.path.join(_HERE, "ladder-audit.py")
)
la = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(la)

_REEXAM_ACTIONS = {
    "revalidate", "revalidate_or_confirm_still_forward", "reconfirm_dormancy",
    "retest_dissonance", "reaudit",
}


def _write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _spec(status, last_validated):
    return f"---\nstatus: {status}\nlast_validated_tic: {last_validated}\n---\n# spec\n\nbody\n"


class TestFreshnessLoader(unittest.TestCase):
    """S0a — `_load_doctrine_freshness`: overdue detection, fresh exclusion,
    no-frontmatter skip, fail-soft on a missing root."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def test_overdue_detected_fresh_excluded(self):
        _write(self.root, "autonomous_kernel/old.md", _spec("active", 100))
        _write(self.root, "autonomous_kernel/recent.md", _spec("active", 505))
        overdue, scanned, skipped = la._load_doctrine_freshness(
            self.root, current_tic=509, freshness_stale_tics=50)
        targets = {o["surface"] for o in overdue}
        self.assertIn("autonomous_kernel/old.md", targets)
        self.assertNotIn("autonomous_kernel/recent.md", targets)  # 4t < 50
        self.assertEqual(scanned, 2)
        self.assertEqual(skipped, 0)
        old = next(o for o in overdue if o["surface"].endswith("old.md"))
        self.assertEqual(old["tics_since_validated"], 409)
        self.assertEqual(old["status"], "active")

    def test_surface_without_frontmatter_is_skipped_not_inferred_fresh(self):
        _write(self.root, "autonomous_kernel/no-fm.md", "# no frontmatter\n\nprose\n")
        overdue, scanned, skipped = la._load_doctrine_freshness(
            self.root, current_tic=509, freshness_stale_tics=50)
        self.assertEqual(overdue, [])
        self.assertEqual(scanned, 0)
        self.assertEqual(skipped, 1)  # out-of-signal-scope, declared — never inferred-fresh

    def test_yaml_meta_sidecar_scanned(self):
        _write(self.root, "autonomous_kernel/reg.json.meta.yaml",
               "status: active\nlast_validated_tic: 100\n")
        overdue, scanned, _ = la._load_doctrine_freshness(
            self.root, current_tic=509, freshness_stale_tics=50)
        self.assertEqual(scanned, 1)
        self.assertEqual(len(overdue), 1)

    def test_missing_root_fails_soft(self):
        overdue, scanned, skipped = la._load_doctrine_freshness(
            self.root, current_tic=509, freshness_stale_tics=50,
            freshness_root_rel="does-not-exist")
        self.assertEqual((overdue, scanned, skipped), ([], 0, 0))

    def test_threshold_is_a_knob_not_a_gate(self):
        _write(self.root, "autonomous_kernel/s.md", _spec("active", 480))  # 29t at 509
        hi, _, _ = la._load_doctrine_freshness(self.root, 509, freshness_stale_tics=50)
        lo, _, _ = la._load_doctrine_freshness(self.root, 509, freshness_stale_tics=20)
        self.assertEqual(len(hi), 0)   # 29 < 50
        self.assertEqual(len(lo), 1)   # 29 >= 20 — overridable window


class TestClassifier(unittest.TestCase):
    """S1 — `_classify_staleness_candidate`: every route is a re-examination, never a
    demote; status drives the freshness route (needs_mechanization ≠ stale)."""

    def test_freshness_routes_by_status(self):
        a, _ = la._classify_staleness_candidate("freshness_overdue", {"status": "active"})
        f, _ = la._classify_staleness_candidate("freshness_overdue", {"status": "forward"})
        d, _ = la._classify_staleness_candidate("freshness_overdue", {"status": "dormant"})
        self.assertEqual(a, "revalidate")
        self.assertEqual(f, "revalidate_or_confirm_still_forward")  # not a demote
        self.assertEqual(d, "reconfirm_dormancy")

    def test_held_and_coverage_routes(self):
        h, _ = la._classify_staleness_candidate("held_dissonance_stale", {})
        c, _ = la._classify_staleness_candidate("coverage_stale", {})
        self.assertEqual(h, "retest_dissonance")
        self.assertEqual(c, "reaudit")

    def test_every_route_is_reexamination_never_demote(self):
        for sig in ("freshness_overdue", "held_dissonance_stale", "coverage_stale"):
            action, note = la._classify_staleness_candidate(sig, {"status": "active"})
            self.assertIn(action, _REEXAM_ACTIONS)
            self.assertNotIn("demote", action)


class TestStalenessScan(unittest.TestCase):
    """Full read-only scan on an isolated repo: composes freshness candidates,
    holds the center (hypothesis not verdict, no demote), writes nothing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        _write(self.root, "autonomous_kernel/old-a.md", _spec("active", 100))
        _write(self.root, "autonomous_kernel/old-b.md", _spec("forward", 120))
        _write(self.root, "autonomous_kernel/recent.md", _spec("active", 505))
        _write(self.root, "autonomous_kernel/no-fm.md", "# no fm\n\nprose\n")

    def test_freshness_candidates_present_and_classified(self):
        res = la.staleness_scan(self.root, current_tic=509)
        fresh = [c for c in res["candidates"] if c["signal"] == "freshness_overdue"]
        targets = {c["target"] for c in fresh}
        self.assertEqual(targets, {"autonomous_kernel/old-a.md",
                                   "autonomous_kernel/old-b.md"})
        by_target = {c["target"]: c["proposed_next_action"] for c in fresh}
        self.assertEqual(by_target["autonomous_kernel/old-a.md"], "revalidate")
        self.assertEqual(by_target["autonomous_kernel/old-b.md"],
                         "revalidate_or_confirm_still_forward")

    def test_center_hold_contract(self):
        res = la.staleness_scan(self.root, current_tic=509)
        # every candidate is a hypothesis, never a confirmed-stale demote
        self.assertTrue(all(c["confirmed_stale"] is False for c in res["candidates"]))
        self.assertTrue(all(c["demote_class_route"] is False for c in res["candidates"]))
        self.assertTrue(all(c["proposed_next_action"] in _REEXAM_ACTIONS
                            for c in res["candidates"]))
        # the read-only fence + the gated forward residues are declared
        self.assertIn("read-only", res["_fence"])
        for k in ("persistence_residue", "cadence_wiring", "action_half_S2",
                  "supersession_orphan_detection"):
            self.assertIn(k, res["forward_residues"])

    def test_scan_writes_nothing(self):
        before = sorted(str(p) for p in Path(self.root).rglob("*") if p.is_file())
        la.staleness_scan(self.root, current_tic=509)
        after = sorted(str(p) for p in Path(self.root).rglob("*") if p.is_file())
        self.assertEqual(before, after)  # read-only: no file created/removed

    def test_counts_and_skip_accounting(self):
        res = la.staleness_scan(self.root, current_tic=509)
        self.assertEqual(res["freshness_surfaces_scanned"], 3)  # old-a, old-b, recent
        self.assertEqual(res["freshness_surfaces_skipped_no_frontmatter"], 1)  # no-fm
        self.assertEqual(res["candidates_by_signal"].get("freshness_overdue"), 2)

    def test_held_and_coverage_fail_soft_on_bare_repo(self):
        """No signal manifold / ledger in the bare repo → held + coverage compose to
        0 candidates without raising (fail-soft); freshness still eats."""
        res = la.staleness_scan(self.root, current_tic=509)
        self.assertEqual(res["candidates_by_signal"].get("held_dissonance_stale", 0), 0)
        self.assertEqual(res["candidates_by_signal"].get("coverage_stale", 0), 0)
        self.assertGreaterEqual(res["candidate_count"], 2)


class TestPersistenceResidue(unittest.TestCase):
    """M2 ACTIVATION piece 1 (build-and-gate): `persist_staleness_candidates`. Dual-proof —
    dormancy (writes nothing) + activation (per-class rollup, dedup, emit/resolve symmetry).
    Honors Emission-Granularity-Is-the-Leak (one rollup per CLASS, never per candidate)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        # 4 freshness-overdue specs (one class) → proves rollup, not per-candidate flood.
        _write(self.root, "autonomous_kernel/a.md", _spec("active", 100))
        _write(self.root, "autonomous_kernel/b.md", _spec("active", 110))
        _write(self.root, "autonomous_kernel/c.md", _spec("forward", 120))
        _write(self.root, "autonomous_kernel/d.md", _spec("dormant", 130))

    def _scan(self):
        return la.staleness_scan(self.root, current_tic=509)

    def _signal_files(self):
        return sorted(str(p) for p in Path(self.root).rglob("*.jsonl"))

    def test_dormant_writes_nothing_and_plans(self):
        before = self._signal_files()
        res = la.persist_staleness_candidates(self.root, self._scan(), opened_tic=509)
        self.assertFalse(res["ratified"])
        self.assertFalse(res["ran"])
        self.assertEqual(self._signal_files(), before)  # build-and-gate dormancy: no write
        # the would-emit PLAN is surfaced: one rollup for the single present class
        self.assertEqual(len(res["would_emit"]), 1)
        self.assertEqual(res["would_emit"][0]["staleness_signal"], "freshness_overdue")
        self.assertEqual(res["would_emit"][0]["candidate_count"], 4)

    def test_activation_emits_one_rollup_per_class_not_per_candidate(self):
        res = la.persist_staleness_candidates(
            self.root, self._scan(), opened_tic=509, force=True)
        self.assertTrue(res["ran"])
        self.assertEqual(len(res["emitted"]), 1)  # 4 candidates → ONE rollup (not a flood)
        rollups = [r for r in la.load_staleness_rollups(self.root)
                   if la.is_active_ray(r)]
        self.assertEqual(len(rollups), 1)
        r = rollups[0]
        self.assertEqual(r["signal_type"], la.STALENESS_CANDIDATE_SIGNAL_TYPE)
        self.assertEqual(r["kind"], "WATCH")
        self.assertEqual(r["band"], "COGNITIVE")
        self.assertEqual(r["payload"]["staleness_signal"], "freshness_overdue")
        self.assertEqual(r["payload"]["candidate_count"], 4)

    def test_activation_is_idempotent_dedup_at_write(self):
        scan = self._scan()
        first = la.persist_staleness_candidates(self.root, scan, opened_tic=509, force=True)
        second = la.persist_staleness_candidates(self.root, scan, opened_tic=509, force=True)
        self.assertEqual(len(first["emitted"]), 1)
        self.assertEqual(len(second["emitted"]), 0)       # re-scan dedups
        self.assertEqual(len(second["deduplicated"]), 1)
        rollups = [r for r in la.load_staleness_rollups(self.root) if la.is_active_ray(r)]
        self.assertEqual(len(rollups), 1)                  # still exactly one active

    def test_emit_resolve_symmetry_heals_on_zero(self):
        # emit (class present), then re-persist a scan with NO candidates → heal it.
        la.persist_staleness_candidates(self.root, self._scan(), opened_tic=509, force=True)
        empty_scan = {"current_tic": 510, "candidates": []}
        healed = la.persist_staleness_candidates(
            self.root, empty_scan, opened_tic=510, force=True)
        self.assertEqual(len(healed["resolved"]), 1)       # emit/resolve symmetry
        active = [r for r in la.load_staleness_rollups(self.root) if la.is_active_ray(r)]
        self.assertEqual(active, [])                       # no write-only TENSION debt

    def test_stable_id_per_class(self):
        a = la.compute_staleness_rollup_signal_id("freshness_overdue")
        b = la.compute_staleness_rollup_signal_id("freshness_overdue")
        c = la.compute_staleness_rollup_signal_id("coverage_stale")
        self.assertEqual(a, b)        # condition-stable
        self.assertNotEqual(a, c)     # distinct per class
        self.assertTrue(a.startswith("sig_ladder_staleness_candidate_"))


class TestCadenceAutoFire(unittest.TestCase):
    """M2 ACTIVATION piece 2 (build-and-gate): cadence-ops.run_m2_staleness_cadence_step.
    Dual-proof — dormancy (no-op, no artifact) + not-due + activation (artifact at a
    ladder_audit-due tic). Read-only: refreshes the artifact, emits no signal."""

    @classmethod
    def setUpClass(cls):
        _co_spec = importlib.util.spec_from_file_location(
            "cadence_ops", os.path.join(_HERE, "cadence-ops.py"))
        cls.co = importlib.util.module_from_spec(_co_spec)
        _co_spec.loader.exec_module(cls.co)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        _write(self.root, "autonomous_kernel/a.md", _spec("active", 100))
        self.artifact = (Path(self.root) / "audit-logs" / "governance"
                         / "m2-staleness-candidates-latest.json")

    def test_dormant_no_op_writes_no_artifact(self):
        res = self.co.run_m2_staleness_cadence_step(self.root, 510)  # 510 % 5 == 0, due
        self.assertFalse(res["ratified"])
        self.assertFalse(res["ran"])
        self.assertTrue(res["due"])  # due but dormant — proves the gate, not the schedule
        self.assertFalse(self.artifact.exists())

    def test_not_due_when_ratified_but_off_cadence(self):
        res = self.co.run_m2_staleness_cadence_step(self.root, 511, force_ratified=True)
        self.assertTrue(res["ratified"])
        self.assertFalse(res["due"])   # 511 % 5 != 0
        self.assertFalse(res["ran"])
        self.assertFalse(self.artifact.exists())

    def test_activation_fires_read_only_scan_to_artifact(self):
        res = self.co.run_m2_staleness_cadence_step(self.root, 510, force_ratified=True)
        self.assertTrue(res["ran"])
        self.assertTrue(res["ok"])
        self.assertTrue(self.artifact.exists())
        self.assertGreaterEqual(res["candidate_count"], 1)  # found the overdue spec
        # read-only: the scan artifact is detection output, NOT a persisted signal
        sigs = list((Path(self.root) / "audit-logs" / "signals").glob("*.jsonl")) \
            if (Path(self.root) / "audit-logs" / "signals").is_dir() else []
        self.assertEqual(sigs, [])  # cadence step emits NO signal (orthogonal flag)


if __name__ == "__main__":
    unittest.main()
