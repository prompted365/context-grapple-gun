#!/usr/bin/env python3
"""MANIFEST-KEYED EMIT / REMOVE-ON-HEAL — the cure ruled at /review 810.

RULED /review 810 round 1 Q4 ("Manifest-keyed + remove-on-heal", the recommended
option verbatim), answering F-809-B1 (HIGH). The three EXPOSED emitters in
ladder-audit.py adopt the already-shipped shape carried by the arena-index and
maps-freshness canaries:

  * the DAILY row is plain append-only LINEAGE — never the dedup key;
  * the DEDUP KEY is the curated manifest's ACTIVE set;
  * the HEAL REMOVES the manifest line and writes the terminal row to the daily
    file AND resolved-archive.jsonl.

THE DEFECT BEING RETIRED: dedup keyed on today's daily file *and* the manifest,
while every heal APPENDED a terminal row instead of removing it — so both dedup
sources still carried the condition-stable id after a heal and a RECURRENCE was
refused. The re-detected condition went dark at the exact moment it re-fired.

This module proves the cure on ALL THREE exposed emitters, in both recurrence
windows the tic-810 trace distinguished (same UTC day; next UTC day with NO
manifest-prune sweep — the window that was previously dark either way), plus the
reader half (resolved-archive.jsonl excluded at the two newly cured sites) and
the properties the cure must NOT break (idempotence, condition-stable ids,
observability-field parity, manifest permission bits).

Every case isolates against a TemporaryDirectory (Self-Locating Artifact Test
Isolation). No test reads or writes the real zone.

DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT change the
shared dedup gate, does NOT cure the three unexposed emitters (none heals), does
NOT wire the staleness precedent's `--persist` into cadence, and does NOT make
the rollup's first live row a series.

Run:  python3 -m pytest -q -p no:cacheprovider \
          test_ladder_audit_manifest_keyed_emit_remove_on_heal_tic811.py
"""
import contextlib
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "ladder_audit", os.path.join(_HERE, "ladder-audit.py"))
la = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(la)

DAY1 = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
DAY2 = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)


@contextlib.contextmanager
def frozen_day(when):
    """Pin the emitters' UTC day so the NEXT-DAY recurrence window is exercised
    for real (a new daily FILE) rather than assumed."""
    real = la.datetime

    class _DT(real):
        @classmethod
        def now(cls, tz=None):
            return when

    la.datetime = _DT
    try:
        yield
    finally:
        la.datetime = real


class _Zone(unittest.TestCase):
    """A bare fixture zone. Signals land under audit-logs/signals/."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        (Path(self.root) / "audit-logs" / "signals").mkdir(parents=True)

    # ---- surfaces -------------------------------------------------------
    @property
    def sig_dir(self):
        return Path(self.root) / "audit-logs" / "signals"

    @property
    def manifest(self):
        return self.sig_dir / "active-manifest.jsonl"

    @property
    def archive(self):
        return self.sig_dir / "resolved-archive.jsonl"

    def daily_rows(self, signal_type=None):
        """Every DAILY row (the dated files only — both derived surfaces
        excluded, the cured reader discipline)."""
        out = []
        for f in sorted(self.sig_dir.glob("*.jsonl")):
            if f.name in ("active-manifest.jsonl", "resolved-archive.jsonl"):
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    if signal_type is None or r.get("signal_type") == signal_type:
                        out.append(r)
        return out

    def jsonl(self, path):
        if not path.is_file():
            return []
        return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()
                if x.strip()]

    def manifest_ids(self):
        return [r.get("signal_id") or r.get("id") for r in self.jsonl(self.manifest)]

    def manifest_active_ids(self):
        return sorted(la._manifest_active_ids(str(self.manifest)))

    # ---- the three exposed emitters, as (emit, heal) pairs ---------------
    def emit_finding(self, tic=811, verdict="damaging"):
        return la.emit_downaudit_finding(
            self.root, "sub-a", "ki_test_one", verdict, tic)

    def heal_finding(self, signal_id, tic=811):
        return la.resolve_downaudit_finding(
            self.root, signal_id, tic, "confirmed",
            "fixture heal — the condition cleared")

    _SCAN_PRESENT = {
        "current_tic": 811,
        "candidates": [{"signal": "freshness_overdue", "target": "a.md",
                        "proposed_next_action": "revalidate"}],
    }
    _SCAN_EMPTY = {"current_tic": 811, "candidates": []}

    def emit_staleness(self, tic=811):
        return la.persist_staleness_candidates(
            self.root, self._SCAN_PRESENT, opened_tic=tic, force=True)

    def heal_staleness(self, tic=811):
        return la.persist_staleness_candidates(
            self.root, self._SCAN_EMPTY, opened_tic=tic, force=True)

    _SEL_PRESENT = {"reconciliation": {"active_but_unsourced": ["sub-a", "sub-b"]}}
    _SEL_EMPTY = {"reconciliation": {"active_but_unsourced": []}}

    def emit_unsourced(self, tic=811):
        return la.persist_unsourced_rung_rollup(
            self.root, self._SEL_PRESENT, opened_tic=tic)

    def heal_unsourced(self, tic=811):
        return la.persist_unsourced_rung_rollup(
            self.root, self._SEL_EMPTY, opened_tic=tic)


# =====================================================================
# HARD PROPERTY 1 — RECURRENCE RE-EMITS (both windows, all three emitters)
# =====================================================================
class TestRecurrenceReEmitsSameUtcDay(_Zone):
    """emit -> heal -> recur on the SAME UTC day re-emits. This was the window
    F-809-B1 named: previously REFUSED because the id sat in today's daily file."""

    def test_emit_downaudit_finding(self):
        with frozen_day(DAY1):
            first = self.emit_finding()
            self.assertTrue(first["written"])
            self.heal_finding(first["signal_id"])
            self.assertEqual(self.manifest_active_ids(), [])
            again = self.emit_finding()
        self.assertTrue(again["written"], "same-day recurrence must RE-EMIT")
        self.assertFalse(again["deduplicated"])
        self.assertEqual(again["signal_id"], first["signal_id"])  # id stays stable
        self.assertEqual(self.manifest_active_ids(), [first["signal_id"]])

    def test_persist_staleness_candidates(self):
        with frozen_day(DAY1):
            first = self.emit_staleness()
            self.assertEqual(len(first["emitted"]), 1)
            self.assertEqual(len(self.heal_staleness()["resolved"]), 1)
            self.assertEqual(self.manifest_active_ids(), [])
            again = self.emit_staleness()
        self.assertEqual(len(again["emitted"]), 1, "same-day recurrence must RE-EMIT")
        self.assertEqual(again["deduplicated"], [])
        self.assertEqual(again["emitted"], first["emitted"])      # id stays stable

    def test_persist_unsourced_rung_rollup(self):
        with frozen_day(DAY1):
            first = self.emit_unsourced()
            self.assertEqual(len(first["emitted"]), 1)
            self.assertEqual(len(self.heal_unsourced()["resolved"]), 1)
            self.assertEqual(self.manifest_active_ids(), [])
            again = self.emit_unsourced()
        self.assertEqual(len(again["emitted"]), 1, "same-day recurrence must RE-EMIT")
        self.assertEqual(again["deduplicated"], [])
        self.assertEqual(again["signal_id"], first["signal_id"])  # id stays stable


class TestRecurrenceReEmitsNextUtcDayWithoutPrune(_Zone):
    """emit+heal on day 1, recur on day 2 with NO manifest-prune sweep.

    The tic-810 trace measured this window as ALSO dark under the old shape: the
    new day's daily file was clean, but the manifest still carried the id because
    the heal appended rather than removed. Remove-on-heal closes it WITHOUT
    depending on the prune cadence — no prune runs anywhere in these cases."""

    def test_emit_downaudit_finding(self):
        with frozen_day(DAY1):
            first = self.emit_finding()
            self.heal_finding(first["signal_id"])
        with frozen_day(DAY2):
            again = self.emit_finding()
        self.assertTrue(again["written"], "next-day recurrence must RE-EMIT (no prune)")
        self.assertEqual(again["signal_id"], first["signal_id"])
        self.assertIn("2026-09-21.jsonl", [p.name for p in self.sig_dir.glob("*.jsonl")])

    def test_persist_staleness_candidates(self):
        with frozen_day(DAY1):
            self.emit_staleness()
            self.heal_staleness()
        with frozen_day(DAY2):
            again = self.emit_staleness()
        self.assertEqual(len(again["emitted"]), 1,
                         "next-day recurrence must RE-EMIT (no prune)")

    def test_persist_unsourced_rung_rollup(self):
        with frozen_day(DAY1):
            self.emit_unsourced()
            self.heal_unsourced()
        with frozen_day(DAY2):
            again = self.emit_unsourced()
        self.assertEqual(len(again["emitted"]), 1,
                         "next-day recurrence must RE-EMIT (no prune)")

    def test_no_prune_ran_in_any_of_these_cases(self):
        """Scope honesty: the cure must not silently depend on manifest-prune.
        resolved-archive.jsonl here is written by the HEAL, never by a sweep."""
        with frozen_day(DAY1):
            r = self.emit_unsourced()
            self.heal_unsourced()
        rows = self.jsonl(self.archive)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["signal_id"], r["signal_id"])
        self.assertEqual(rows[0]["status"], "resolved")


# =====================================================================
# HARD PROPERTY 2 — IDEMPOTENCE PRESERVED (and the DAILY accrual, measured)
# =====================================================================
class TestIdempotencePreserved(_Zone):
    """A STANDING, un-healed condition emits ONE manifest ray, never one per run.

    The daily accrual is MEASURED here rather than assumed: the manifest-active
    PRE-CHECK returns before any write, so a standing condition accrues ZERO
    additional daily rows per run — exactly ONE daily row per emit EDGE."""

    def test_downaudit_three_runs_one_ray_one_daily_row(self):
        with frozen_day(DAY1):
            for _ in range(3):
                self.emit_finding()
        self.assertEqual(len(self.manifest_active_ids()), 1)
        self.assertEqual(len(self.daily_rows(la.DOWNAUDIT_FINDING_SIGNAL_TYPE)), 1)

    def test_staleness_three_runs_one_ray_one_daily_row(self):
        with frozen_day(DAY1):
            results = [self.emit_staleness() for _ in range(3)]
        self.assertEqual(len(results[0]["emitted"]), 1)
        self.assertEqual(results[1]["emitted"], [])
        self.assertEqual(len(results[1]["deduplicated"]), 1)
        self.assertEqual(len(self.manifest_active_ids()), 1)
        self.assertEqual(len(self.daily_rows(la.STALENESS_CANDIDATE_SIGNAL_TYPE)), 1)

    def test_unsourced_three_runs_one_ray_one_daily_row(self):
        with frozen_day(DAY1):
            results = [self.emit_unsourced() for _ in range(3)]
        self.assertEqual(len(results[0]["emitted"]), 1)
        self.assertEqual(results[2]["emitted"], [])
        self.assertEqual(len(self.manifest_active_ids()), 1)
        self.assertEqual(len(self.daily_rows(la.UNSOURCED_RUNG_SIGNAL_TYPE)), 1)

    def test_membership_change_while_standing_writes_no_second_row(self):
        """One ray per OWNER, never one per rung — the emission-granularity law."""
        with frozen_day(DAY1):
            first = self.emit_unsourced()
            second = la.persist_unsourced_rung_rollup(
                self.root, {"reconciliation": {"active_but_unsourced": ["sub-b"]}},
                opened_tic=812)
        self.assertEqual(second["signal_id"], first["signal_id"])
        self.assertEqual(second["emitted"], [])
        self.assertEqual(len(self.daily_rows(la.UNSOURCED_RUNG_SIGNAL_TYPE)), 1)

    def test_daily_accrual_over_a_full_emit_heal_recur_cycle(self):
        """The whole cycle's daily accrual, stated as a number: 3 rows —
        emit(active) + heal(resolved) + re-emit(active). Never one per RUN."""
        with frozen_day(DAY1):
            r = self.emit_unsourced()
            self.emit_unsourced()              # standing: no row
            self.heal_unsourced()
            self.heal_unsourced()              # already healed: no row
            self.emit_unsourced()              # recurrence: a row
            self.emit_unsourced()              # standing again: no row
        rows = self.daily_rows(la.UNSOURCED_RUNG_SIGNAL_TYPE)
        self.assertEqual(len(rows), 3)
        self.assertEqual([x["status"] for x in rows],
                         ["active", "resolved", "active"])
        self.assertEqual({x["signal_id"] for x in rows}, {r["signal_id"]})


# =====================================================================
# HARD PROPERTY 3 — MANIFEST ACCRUAL FIELDS across a heal/recur
# =====================================================================
class TestManifestAccrualAcrossHealAndRecurrence(_Zone):
    """What the MANIFEST carries before/after a heal and a recurrence — read from
    the fixture manifest, not assumed."""

    def test_manifest_row_fields_and_lifecycle(self):
        with frozen_day(DAY1):
            emitted = self.emit_unsourced()
            after_emit = self.jsonl(self.manifest)
            self.heal_unsourced()
            after_heal = self.jsonl(self.manifest)
            self.emit_unsourced()
            after_recur = self.jsonl(self.manifest)

        # AFTER EMIT: exactly one row, carrying the observability quartet.
        self.assertEqual(len(after_emit), 1)
        row = after_emit[0]
        self.assertEqual(row["signal_id"], emitted["signal_id"])
        self.assertEqual(row["status"], "active")
        for field in ("kind", "band", "volume", "max_volume"):
            self.assertIn(field, row, f"manifest row lost {field} (acoustically dark)")
        self.assertEqual(row["signal_type"], la.UNSOURCED_RUNG_SIGNAL_TYPE)
        self.assertIn("source_file", row)
        self.assertIn("summary", row)

        # AFTER HEAL: the line is REMOVED — the manifest is EMPTY, not shadowed
        # by an appended terminal row. This is the whole cure.
        self.assertEqual(after_heal, [],
                         "remove-on-heal must REMOVE the line, not append a terminal row")

        # AFTER RECURRENCE: one row again, same id, active, quartet intact.
        self.assertEqual(len(after_recur), 1)
        self.assertEqual(after_recur[0]["signal_id"], emitted["signal_id"])
        self.assertEqual(after_recur[0]["status"], "active")
        for field in ("kind", "band", "volume", "max_volume"):
            self.assertIn(field, after_recur[0])

    def test_no_terminal_row_accumulates_on_the_manifest(self):
        """Under the old shape the manifest accrued emit+heal rows per cycle and
        never shed them. After two full cycles it must hold exactly one row."""
        with frozen_day(DAY1):
            for _ in range(2):
                self.emit_unsourced()
                self.heal_unsourced()
            self.emit_unsourced()
        self.assertEqual(len(self.jsonl(self.manifest)), 1)
        self.assertEqual(len(self.jsonl(self.archive)), 2)  # both heals archived

    def test_heal_archives_so_no_signal_goes_dark(self):
        """manifest-prune used to sweep the appended terminal row to the archive.
        Removal means prune never sees it, so the HEAL must archive it itself."""
        with frozen_day(DAY1):
            r = self.emit_finding()
            self.heal_finding(r["signal_id"])
        arch = self.jsonl(self.archive)
        self.assertEqual(len(arch), 1)
        self.assertEqual(arch[0]["signal_id"], r["signal_id"])
        self.assertEqual(arch[0]["status"], "resolved")
        self.assertEqual(arch[0]["structural_status"], "resolved")
        for field in ("kind", "band", "volume", "max_volume"):
            self.assertIn(field, arch[0], "archived row must carry the quartet")

    def test_manifest_keeps_its_permission_bits_across_removal(self):
        """The remove rewrites the manifest. Through the shared umask-honoring
        writer it KEEPS its mode — a mkstemp+replace pair would re-clamp the
        curated manifest to owner-only."""
        with frozen_day(DAY1):
            self.emit_unsourced()
            os.chmod(self.manifest, 0o644)
            before = stat.S_IMODE(os.stat(self.manifest).st_mode)
            self.heal_unsourced()
            after = stat.S_IMODE(os.stat(self.manifest).st_mode)
        self.assertEqual(before, 0o644)
        self.assertEqual(after, before, "remove-on-heal must preserve the mode")


# =====================================================================
# HARD PROPERTY 4 — THE TWO READERS exclude resolved-archive.jsonl
# =====================================================================
class TestReadersExcludeResolvedArchive(_Zone):
    """A row present ONLY in resolved-archive.jsonl is invisible to the two newly
    cured readers — and to the two siblings that were already cured.

    resolved-archive.jsonl sorts LAST in the directory glob ('r' > any date), so
    an un-excluded reader lets a thin archived terminal copy out-vote a
    chronologically newer active row."""

    def _plant_archive_only(self, signal_type, sig_id):
        self.archive.write_text(json.dumps({
            "signal_id": sig_id, "id": sig_id, "signal_type": signal_type,
            "status": "resolved", "structural_status": "resolved",
        }) + "\n", encoding="utf-8")

    def test_load_staleness_rollups_excludes_archive_only_row(self):
        self._plant_archive_only(la.STALENESS_CANDIDATE_SIGNAL_TYPE, "sig_archive_only_a")
        self.assertEqual(la.load_staleness_rollups(self.root), [])

    def test_load_unsourced_rung_rollups_excludes_archive_only_row(self):
        self._plant_archive_only(la.UNSOURCED_RUNG_SIGNAL_TYPE, "sig_archive_only_b")
        self.assertEqual(la.load_unsourced_rung_rollups(self.root), [])

    def test_archived_terminal_echo_cannot_out_vote_a_live_re_emit(self):
        """The end-to-end shape of the defect: heal (archives) then recur. The
        readers must report the ray ACTIVE, reading the daily file, not the
        archive's terminal copy."""
        with frozen_day(DAY1):
            self.emit_unsourced()
            self.heal_unsourced()
            self.emit_unsourced()
        active = [s for s in la.load_unsourced_rung_rollups(self.root)
                  if la.is_active_ray(s)]
        self.assertEqual(len(active), 1,
                         "the re-emitted ray must be visible, not swallowed by the archive")

    def test_previously_cured_siblings_still_exclude_both(self):
        """load_downaudit_findings and load_active_signals were cured earlier;
        this increment must leave their behaviour intact."""
        self._plant_archive_only(la.DOWNAUDIT_FINDING_SIGNAL_TYPE, "sig_archive_only_c")
        self.assertEqual(la.load_downaudit_findings(self.root), [])
        by_sub = la.load_active_signals(self.root)
        flat = {i for ids in by_sub.values() for i in ids}
        self.assertNotIn("sig_archive_only_c", flat)

    def test_healed_then_recurred_finding_is_visible_to_its_reader(self):
        with frozen_day(DAY1):
            r = self.emit_finding()
            self.heal_finding(r["signal_id"])
            self.emit_finding()
        live = [s for s in la.load_downaudit_findings(self.root)
                if la.is_active_ray(s)]
        self.assertEqual([s.get("signal_id") for s in live], [r["signal_id"]])


# =====================================================================
# The cure must not damage its neighbours
# =====================================================================
class TestNeighboursUndamaged(_Zone):
    """Guards on properties the ruling did NOT authorise changing."""

    def test_ids_remain_condition_stable(self):
        """The rejected option was minting a new id per occurrence. Ids must be
        byte-identical across emit/heal/recur."""
        with frozen_day(DAY1):
            a = self.emit_unsourced()["signal_id"]
            self.heal_unsourced()
            b = self.emit_unsourced()["signal_id"]
        self.assertEqual(a, b)
        self.assertEqual(a, la.compute_unsourced_rung_rollup_signal_id())

    def test_reaffirm_keeps_the_ray_active_and_is_not_a_heal(self):
        """reaffirm-finding is the THIRD symmetry leg, not a heal: it must NOT
        remove the manifest line, and the ray stays ACTIVE."""
        with frozen_day(DAY1):
            r = self.emit_finding()
            out = la.reaffirm_downaudit_finding(
                self.root, r["signal_id"], "fixture re-test: the finding stands")
        self.assertTrue(out["ok"])
        self.assertEqual(self.manifest_active_ids(), [r["signal_id"]])

    def test_a_standing_condition_is_not_re_emitted_after_a_reaffirm(self):
        with frozen_day(DAY1):
            r = self.emit_finding()
            la.reaffirm_downaudit_finding(self.root, r["signal_id"], "stands")
            again = self.emit_finding()
        self.assertFalse(again["written"])
        self.assertTrue(again["deduplicated"])

    def test_resolve_is_idempotent_and_refuses_a_terminal_finding(self):
        with frozen_day(DAY1):
            r = self.emit_finding()
            self.heal_finding(r["signal_id"])
            second = self.heal_finding(r["signal_id"])
        self.assertFalse(second["ok"])
        self.assertIn("already terminal", second["error"])

    def test_empty_condition_with_nothing_active_writes_nothing(self):
        with frozen_day(DAY1):
            out = self.heal_unsourced()
        self.assertEqual(out["resolved"], [])
        self.assertEqual(out["emitted"], [])
        self.assertEqual(self.daily_rows(), [])

    def test_dry_run_still_writes_nothing(self):
        with frozen_day(DAY1):
            out = la.persist_unsourced_rung_rollup(
                self.root, self._SEL_PRESENT, opened_tic=811, dry_run=True)
        self.assertEqual(self.daily_rows(), [])
        self.assertEqual(self.jsonl(self.manifest), [])
        self.assertIsNotNone(out["would_emit"])

    def test_manifest_active_ids_is_fail_soft_on_a_bare_manifold(self):
        self.assertEqual(la._manifest_active_ids(str(self.manifest)), set())
        self.assertEqual(la._manifest_remove(str(self.manifest), "sig_absent"), 0)

    def test_manifest_remove_drops_every_row_for_the_id_only(self):
        self.manifest.write_text(
            json.dumps({"signal_id": "keep_me", "status": "active"}) + "\n"
            + json.dumps({"signal_id": "drop_me", "status": "active"}) + "\n"
            + json.dumps({"signal_id": "drop_me", "status": "resolved"}) + "\n",
            encoding="utf-8")
        removed = la._manifest_remove(str(self.manifest), "drop_me")
        self.assertEqual(removed, 2)
        self.assertEqual(self.manifest_ids(), ["keep_me"])

    def test_rider_constant_is_present_and_verbatim(self):
        self.assertEqual(
            la.MANIFEST_KEYED_EMIT_DOES_NOT_SATISFY,
            "this increment does NOT change the shared dedup gate, does NOT cure "
            "the three unexposed emitters (none heals), does NOT wire the "
            "staleness precedent's `--persist` into cadence, and does NOT make "
            "the rollup's first live row a series.")


if __name__ == "__main__":
    unittest.main()
