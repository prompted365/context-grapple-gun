#!/usr/bin/env python3
"""ARM (b) — the ADMISSION-AND-COVERAGE unsourced-rung ROLLUP.

RULED /review 808 (cpr_mogul_ladder_audit_1d3045c0e3ce -> ledger.md#admission-and-
coverage-are-separately-clocked-the-generator-behind-an-undelivered-owed-motion).
CONSUMER RULED, verbatim: "the instrument emits ONE condition-stable rollup signal while
its unsourced set is non-empty and resolves it on heal (emit/resolve symmetry; one ray
per owner, never one per rung)".

The four ruled fixtures:
  non-empty                      -> emits exactly ONE signal
  membership change (non-empty)  -> SAME id, no second row
  empty                          -> resolves it
  already-resolved + still empty -> no row

THE TWO PINNED LIMIT TESTS WERE INVERTED at /review 810 (ruling step 3). They were
written at tic 809 to fail loudly on the day F-809-B1 was cured; the cure landed as
manifest-keyed emit + remove-on-heal, so both now assert the CURED behaviour
(recurrence after heal RE-EMITS) on this function AND on the precedent it mirrors.

Plus the guards that keep the cure from damaging its neighbours:
  * the read-only selector still writes NOTHING (its fence is load-bearing — three
    read-only scans call it);
  * federation law: signal `kind` never leaks into `status`;
  * the rollup does NOT contaminate run_audit's ratified TWO-ALTITUDES sibling count.

Every case isolates against a TemporaryDirectory (Self-Locating Artifact Test Isolation).

Run:  python3 -m unittest test_ladder_audit_unsourced_rung_rollup_tic809
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "ladder_audit", os.path.join(_HERE, "ladder-audit.py"))
la = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(la)

_LEDGER = """### Test Invariant One

`invariant_id`: `ki_test_one`
`terrain_class`: `queue_and_state`

Body.

<!-- promoted from cpr_test_one -->
"""


def _write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


class _Fixture(unittest.TestCase):
    """A zone with THREE active rungs ('.', 'sub-a', 'sub-b') whose concern coverage
    can be varied, so the unsourced SET changes while the CONDITION stays present."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        _write(self.root, ".ticzone", json.dumps({"name": "fixture-zone"}))
        _write(self.root, "audit-logs/governance/constitution-ledger/ledger.md", _LEDGER)
        _write(self.root, "sub-a/.domain-root", "")
        _write(self.root, "sub-b/.domain-root", "")
        # run_audit needs a real chain member, or it short-circuits on the
        # "No CLAUDE.md files found" branch and the sibling-count guard below would
        # pass vacuously against an error dict.
        _write(self.root, "CLAUDE.md", "# Fixture root\n\n## Section\n")

    def _source(self, name, paths):
        """Write a concern source covering `paths`; return its absolute path."""
        rungs = {f"r{i}": {"path": p, "candidate_concerns": ["queue-and-state"],
                           "ranked": [{"lane": "queue-and-state", "score": 5}]}
                 for i, p in enumerate(paths)}
        p = _write(self.root, f"audit-logs/governance/{name}",
                   json.dumps({"_tic": 999, "rungs": rungs}))
        return str(p)

    def _select(self, covered):
        return la.select_kis_per_rung(
            self.root, concern_source=self._source("src.json", covered))

    def _rows(self):
        d = Path(self.root) / "audit-logs" / "signals"
        if not d.is_dir():
            return []
        rows = []
        for f in sorted(d.glob("*.jsonl")):
            # Both DERIVED surfaces are excluded, exactly as the cured production
            # readers do. This is not hygiene: under remove-on-heal the heal writes
            # the terminal row to resolved-archive.jsonl, which sorts LAST in this
            # glob, so a harness that folded it in would read the thin archived
            # copy as the newest row — the very file-sort-is-not-chronology defect
            # this increment cured at load_staleness_rollups / load_unsourced_rung_rollups.
            if f.name in ("active-manifest.jsonl", "resolved-archive.jsonl"):
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    if r.get("signal_type") == la.UNSOURCED_RUNG_SIGNAL_TYPE:
                        rows.append(r)
        return rows

    def _active(self):
        return [r for r in la.load_unsourced_rung_rollups(self.root)
                if la.is_active_ray(r)]


class TestActiveSetPrecondition(_Fixture):
    """Guard against a vacuous suite: the fixture must really produce unsourced rungs."""

    def test_three_rungs_active_and_two_unsourced(self):
        sel = self._select(["."])
        self.assertEqual(sel["reconciliation"]["active_but_unsourced"],
                         ["sub-a", "sub-b"])


class TestConditionStableId(_Fixture):
    """The id is keyed on the OWNER, never on the member set or its cardinality."""

    def test_id_is_stable_across_membership_and_cardinality(self):
        a = la.compute_unsourced_rung_rollup_signal_id()
        b = la.compute_unsourced_rung_rollup_signal_id("ladder_downlane")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("sig_ladder_rung_concern_unsourced_"))

    def test_distinct_owner_distinct_ray(self):
        self.assertNotEqual(la.compute_unsourced_rung_rollup_signal_id("owner_x"),
                            la.compute_unsourced_rung_rollup_signal_id("owner_y"))


class TestRuledFixtures(_Fixture):
    """The four ruled fixtures, in order."""

    def test_1_non_empty_emits_exactly_one_signal(self):
        res = la.persist_unsourced_rung_rollup(self.root, self._select(["."]),
                                               opened_tic=809)
        self.assertTrue(res["condition_present"])
        self.assertEqual(len(res["emitted"]), 1)
        self.assertEqual(len(self._rows()), 1)          # ONE row, not one per rung
        self.assertEqual(len(self._active()), 1)
        row = self._rows()[0]
        self.assertEqual(row["payload"]["unsourced_count"], 2)   # 2 rungs, 1 ray
        self.assertEqual(row["payload"]["unsourced_rungs"], ["sub-a", "sub-b"])

    def test_2_membership_change_while_non_empty_same_id_no_second_row(self):
        first = la.persist_unsourced_rung_rollup(self.root, self._select(["."]),
                                                 opened_tic=809)
        # coverage grows: sub-a is now sourced -> the SET changes, the CONDITION stands
        sel2 = self._select([".", "sub-a"])
        self.assertEqual(sel2["reconciliation"]["active_but_unsourced"], ["sub-b"])
        second = la.persist_unsourced_rung_rollup(self.root, sel2, opened_tic=810)
        self.assertEqual(second["signal_id"], first["signal_id"])   # SAME id
        self.assertEqual(second["emitted"], [])                     # no second row
        self.assertEqual(second["deduplicated"], [first["signal_id"]])
        self.assertEqual(len(self._rows()), 1)
        self.assertEqual(len(self._active()), 1)

    def test_3_empty_resolves_it(self):
        la.persist_unsourced_rung_rollup(self.root, self._select(["."]), opened_tic=809)
        healed = la.persist_unsourced_rung_rollup(
            self.root, self._select([".", "sub-a", "sub-b"]), opened_tic=811)
        self.assertFalse(healed["condition_present"])
        self.assertEqual(len(healed["resolved"]), 1)
        self.assertEqual(self._active(), [])        # no write-only TENSION debt
        term = self._rows()[-1]
        self.assertEqual(term["status"], "resolved")
        self.assertEqual(term["payload"]["resolution"]["resolved_to"], "healed")
        # the heal row carries the observability quartet forward (never acoustically dark)
        for field in ("kind", "band", "volume", "max_volume"):
            self.assertIn(field, term)

    def test_4_already_resolved_and_still_empty_writes_no_row(self):
        la.persist_unsourced_rung_rollup(self.root, self._select(["."]), opened_tic=809)
        la.persist_unsourced_rung_rollup(
            self.root, self._select([".", "sub-a", "sub-b"]), opened_tic=811)
        before = len(self._rows())
        again = la.persist_unsourced_rung_rollup(
            self.root, self._select([".", "sub-a", "sub-b"]), opened_tic=812)
        self.assertEqual(again["resolved"], [])
        self.assertEqual(again["emitted"], [])
        self.assertEqual(len(self._rows()), before)     # idempotent: NO row
        self.assertEqual(self._active(), [])

    def test_recurrence_after_heal_RE_EMITS(self):
        """INVERTED at /review 810 (ruling step 3) — this was
        `test_LIMIT_recurrence_after_heal_does_NOT_re_emit`.

        The tic-809 version PINNED the inherited F-809-B1 limit: after a heal, a
        RECURRENCE of the same condition was REFUSED, because dedup keyed on the daily
        file (and the manifest, which the heal only appended to) still carried the
        condition-stable id — so the re-detected condition went dark at the exact
        moment it re-fired. It was written to fail loudly on the day of the cure.

        This is that day. The ruled cure (manifest-keyed emit + remove-on-heal) makes
        the manifest's ACTIVE set the sole dedup key and makes the heal REMOVE the
        manifest line, so a recurrence finds no active id and re-emits — on the SAME
        UTC day, and on any later day, with or without a manifest-prune sweep.

        The id is unchanged across the cycle: condition-stability is preserved, which
        is what distinguishes this cure from the rejected mint-a-new-id option.
        """
        first = la.persist_unsourced_rung_rollup(self.root, self._select(["."]),
                                                 opened_tic=809)
        la.persist_unsourced_rung_rollup(
            self.root, self._select([".", "sub-a", "sub-b"]), opened_tic=811)
        again = la.persist_unsourced_rung_rollup(self.root, self._select(["."]),
                                                 opened_tic=812)
        self.assertEqual(again["emitted"], [again["signal_id"]])   # RE-EMITS (cured)
        self.assertEqual(again["deduplicated"], [])
        self.assertEqual(again["signal_id"], first["signal_id"])   # id still stable
        self.assertEqual(len(self._active()), 1)        # the ray is live again

    def test_the_precedent_IS_CURED_in_the_same_motion(self):
        """INVERTED at /review 810 (ruling step 3) — this was
        `test_LIMIT_is_inherited_from_the_mirrored_precedent`.

        Its tic-809 job was to prove F-809-B1 was INHERITED from the ratified precedent
        (`persist_staleness_candidates`) rather than introduced here — which is exactly
        why the cure could not land on one caller alone without half-fixing a shared
        shape (the named-footgun-leaves-sibling-site-unfixed defect class). Both were
        cured in ONE motion, so the same sequence now proves the precedent re-emits
        too."""
        _write(self.root, "autonomous_kernel/a.md",
               "---\nstatus: active\nlast_validated_tic: 100\n---\n# s\n")
        present = la.staleness_scan(self.root, current_tic=509)
        empty = {"current_tic": 510, "candidates": []}
        self.assertEqual(len(la.persist_staleness_candidates(
            self.root, present, opened_tic=509, force=True)["emitted"]), 1)
        self.assertEqual(len(la.persist_staleness_candidates(
            self.root, empty, opened_tic=510, force=True)["resolved"]), 1)
        recur = la.persist_staleness_candidates(
            self.root, present, opened_tic=511, force=True)
        self.assertEqual(len(recur["emitted"]), 1)      # precedent RE-EMITS (cured)
        self.assertEqual(recur["deduplicated"], [])
        self.assertEqual(len([s for s in la.load_staleness_rollups(self.root)
                              if la.is_active_ray(s)]), 1)


class TestFencesAndFederationLaw(_Fixture):
    """The cure must not damage its neighbours."""

    def test_selector_itself_still_writes_nothing(self):
        # The gauge is a site too: the fixture's own concern-source write must land
        # BEFORE the snapshot, or the harness's write is charged to the selector.
        src = self._source("src.json", ["."])
        before = sorted(str(p) for p in Path(self.root).rglob("*") if p.is_file())
        la.select_kis_per_rung(self.root, concern_source=src)
        after = sorted(str(p) for p in Path(self.root).rglob("*") if p.is_file())
        self.assertEqual(before, after)

    def test_dry_run_writes_nothing_but_plans(self):
        res = la.persist_unsourced_rung_rollup(self.root, self._select(["."]),
                                               opened_tic=809, dry_run=True)
        self.assertEqual(self._rows(), [])
        self.assertIsNotNone(res["would_emit"])
        self.assertEqual(res["would_emit"]["unsourced_count"], 2)

    def test_kind_never_leaks_into_status(self):
        la.persist_unsourced_rung_rollup(self.root, self._select(["."]), opened_tic=809)
        row = self._rows()[0]
        self.assertEqual(row["kind"], "WATCH")
        self.assertEqual(row["status"], "active")
        self.assertNotEqual(row["status"], row["kind"])
        manifest = (Path(self.root) / "audit-logs" / "signals"
                    / "active-manifest.jsonl").read_text(encoding="utf-8")
        for line in manifest.splitlines():
            if line.strip():
                m = json.loads(line)
                self.assertIn(m.get("status"), ("active", "resolved"))

    def test_rollup_does_not_contaminate_the_downlane_sibling_count(self):
        """run_audit's ratified TWO-ALTITUDES disclosure (/review 758 Q1) counts a
        sibling finding as subsystem=='ladder_downlane' OR id prefix
        'sig_ladder_down_audit_finding_'. This rollup is NEITHER — emitting it must not
        inflate a count another ruling fixed."""
        la.persist_unsourced_rung_rollup(self.root, self._select(["."]), opened_tic=809)
        row = self._rows()[0]
        self.assertEqual(row["subsystem"], "ladder_admission")
        self.assertNotEqual(row["subsystem"], "ladder_downlane")
        self.assertFalse(row["signal_id"].startswith("sig_ladder_down_audit_finding_"))
        audit = la.run_audit(self.root)
        sib = audit["sibling_instruments"]["ladder_down_audit"]
        self.assertNotIn(row["signal_id"], sib["ids"])
        self.assertEqual(sib["open_findings_on_manifold"], 0)

    def test_rider_travels_verbatim_in_the_emitted_payload(self):
        la.persist_unsourced_rung_rollup(self.root, self._select(["."]), opened_tic=809)
        row = self._rows()[0]
        self.assertEqual(row["payload"]["does_not_satisfy"],
                         la.UNSOURCED_RUNG_DOES_NOT_SATISFY)
        for phrase in ("does NOT source or deliver the two unsourced rungs",
                       "does NOT perform the ladder-audit re-derive",
                       "does NOT change which rungs count as active",
                       "does NOT cure the rung-ident canonicalization defect"):
            self.assertIn(phrase, row["payload"]["does_not_satisfy"])

    def test_fail_soft_on_a_selection_with_no_reconciliation(self):
        res = la.persist_unsourced_rung_rollup(self.root, {}, opened_tic=809,
                                               dry_run=True)
        self.assertFalse(res["condition_present"])
        self.assertEqual(res["unsourced_rungs"], [])


if __name__ == "__main__":
    unittest.main()
