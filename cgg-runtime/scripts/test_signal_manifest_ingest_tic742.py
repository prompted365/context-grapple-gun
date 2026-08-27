#!/usr/bin/env python3
"""Fixtures for `lib.atomic_append.dedup_signal_append`'s PRODUCER INGEST ARM
(`ingest_manifest=`) — wave 12c, tic 742, backlog row
bk-signal-manifest-producer-ingestion-path.

THE DEFECT (from the ruling's own evidence — the PRODUCER-half THIRD ray on
constitution-ledger#authoritative-set-readers-must-read-the-manifest-not-
aggregate-raw-emissions, promoted from cpr_mogul_memory_mining_012d4d5a42c0 at
/review 741): `dedup_signal_append(target, signal, manifest_path=...)` read
`manifest_path` ONLY to build its dedup set; its sole write was the daily
signals file. So NO ingestion path existed from a script-emitted signal into
`active-manifest.jsonl`. Emitters that TRUSTED the parameter's name
(visitor-economy-monitor.py, biome-engine.py) were structurally invisible to
the authoritative reader (Mogul signal_scan) forever — and because the only
cross-day dedup source is the surface those producers could never reach, every
new daily file started with an empty dedup set and the unlanded condition
re-emitted once per day indefinitely (measured live t738 and t741: 187 raw
emissions / 52 distinct ids / 0 manifest rows for `biome.health_degraded`).

THE RULED CURE (design fork (b)+(c), ruled at dispatch): the shared helper
gains an explicit, opt-in `ingest_manifest: bool = False` arm — the helper
becomes the ONE lawful append path for both surfaces. Default False keeps every
existing caller byte-identical.

RED-THEN-GREEN spine:
  RED   — `TestRedTodaysInvisibility` drives the REAL helper with
          `manifest_path=` and the DEFAULT arm and proves the exact shipped
          defect: the row lands in the daily file and NOT in the manifest.
          It is simultaneously the forward-only proof (every existing caller's
          behaviour is untouched) and the shape the cure is measured against.
  GREEN — `TestGreenIngestArmLandsBothSurfaces` runs the SAME signal with
          `ingest_manifest=True` and proves it lands in BOTH under
          dedup-by-identity: second call -> daily deduped AND manifest not
          duplicated; a manifest that ALREADY carries the id -> no duplicate.

NEGATIVE CONTROL (the load-bearing arm): `TestNegativeControlArmIsLoadBearing`
reverts the arm IN PLACE — it re-execs the real `lib/atomic_append.py` source
with the ingest predicate neutered — and proves the invisibility RETURNS on the
identical scenario, then proves the live module heals the same scenario. The
revert asserts its own sentinel matched first, so a future edit that deletes or
guts the arm fails this arm rather than silently passing it.

Per cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths
every documented conditional gets BOTH arms: ingest_manifest False/True,
manifest_path None/given, row-written/row-deduped, manifest-absent/
manifest-present, manifest_path == target, id-bearing/id-less signal, and each
derived row field present/absent. `TestRowIsReadableByTheAuthoritativeReaders`
closes the mounted-bear question directly: the landed row is projected by
manifest-prune.project_signal and counted by lib.signal_active.is_active_ray.
`TestRealCallSitesOptIn` drives the two REAL opted-in emitters end to end.

Isolation: every case builds its own signals tree under a TemporaryDirectory.
NOTHING in this file reads or writes the real `audit-logs/signals/` — no live
manifest row, no live daily row, is created by running it.

Run:  python3 -m unittest test_signal_manifest_ingest_tic742   (from cgg-runtime/scripts/)
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))          # so `from lib.atomic_append import ...` resolves
sys.path.insert(0, str(_HERE / "lib"))  # so `from signal_active import ...` resolves

from lib.atomic_append import dedup_signal_append, manifest_row_from_signal  # noqa: E402
import lib.atomic_append as aa  # noqa: E402
from signal_active import is_active_ray, latest_per_id  # noqa: E402

_ATOMIC_APPEND_PATH = _HERE / "lib" / "atomic_append.py"

# The exact predicate the cure hangs on. The negative control asserts this
# sentinel is PRESENT before neutering it — a deleted/renamed arm fails loudly
# instead of quietly turning the control into a no-op.
_ARM_SENTINEL = "if ingest_manifest and manifest_path and manifest_path != target:"

DATE = "2026-08-27"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rows(p: Path) -> list:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _ids(p: Path) -> list:
    return [r.get("signal_id") or r.get("id") for r in _rows(p)]


# ── the two real trusting-caller shapes, verbatim from their emitters ───────
# biome-engine.py:405-411 — carries `signal_id` and puts the SIGNAL TYPE in
# `type`; carries NO kind, NO status, NO volume.
BIOME_SIGNAL = {
    "signal_id": "biome.health_degraded_deadbeefdeadbeef",
    "band": "WATCH",
    "type": "health_degraded",
    "source": "biome_simulation",
    "payload": {"act_id": "act_2", "biome_cycle": 51, "summary": "trust floor breached"},
    "emitted_at": "2026-08-27T00:00:00+00:00",
}

# visitor-economy-monitor.py:65-76 — carries `id` (NOT signal_id) and puts the
# RECORD TYPE literal "signal" in `type`; carries kind/band/volume/status/
# subsystem/description.
VISITOR_SIGNAL = {
    "type": "signal",
    "id": "sig_trust_decay_0123456789ab",
    "kind": "WATCH",
    "band": "COGNITIVE",
    "volume": 30,
    "status": "active",
    "subsystem": "visitor_economy",
    "description": "3 visitors below trust floor",
    "emitted_at": "2026-08-27T00:00:00+00:00",
    "source": "visitor-economy-monitor.py",
}


class _SignalTree(unittest.TestCase):
    """Every case gets its own signals/ tree. Nothing touches the real one."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sig_dir = Path(self.tmp.name) / "audit-logs" / "signals"
        self.sig_dir.mkdir(parents=True)
        self.daily = self.sig_dir / f"{DATE}.jsonl"
        self.manifest = self.sig_dir / "active-manifest.jsonl"

    def _emit(self, signal, **kw):
        return dedup_signal_append(str(self.daily), dict(signal),
                                   manifest_path=str(self.manifest), **kw)


# ══════════════════════════════════════════════════════════════════════════
# RED — today's invisibility, reproduced against the real helper
# ══════════════════════════════════════════════════════════════════════════

class TestRedTodaysInvisibility(_SignalTree):

    def test_manifest_path_alone_lands_daily_and_not_manifest(self):
        """The shipped defect: `manifest_path=` is READ-ONLY."""
        self.assertTrue(self._emit(BIOME_SIGNAL))
        self.assertEqual(_ids(self.daily), [BIOME_SIGNAL["signal_id"]])
        self.assertEqual(_rows(self.manifest), [],
                         "manifest_path= must remain read-only without the opt-in")

    def test_default_is_false_so_existing_callers_are_byte_identical(self):
        sig = inspect.signature(dedup_signal_append)
        self.assertIn("ingest_manifest", sig.parameters)
        self.assertIs(sig.parameters["ingest_manifest"].default, False)
        # ...and the positional order of the pre-existing parameters is unchanged.
        self.assertEqual(list(sig.parameters)[:3], ["target", "signal", "manifest_path"])

    def test_daily_row_is_written_verbatim_not_projected(self):
        """The ingest arm must not change what lands in the DAILY file."""
        self._emit(BIOME_SIGNAL, ingest_manifest=True)
        self.assertEqual(_rows(self.daily), [BIOME_SIGNAL])


# ══════════════════════════════════════════════════════════════════════════
# GREEN — the ingest arm lands both surfaces under dedup-by-identity
# ══════════════════════════════════════════════════════════════════════════

class TestGreenIngestArmLandsBothSurfaces(_SignalTree):

    def test_opt_in_lands_daily_and_manifest(self):
        self.assertTrue(self._emit(BIOME_SIGNAL, ingest_manifest=True))
        self.assertEqual(_ids(self.daily), [BIOME_SIGNAL["signal_id"]])
        self.assertEqual(_ids(self.manifest), [BIOME_SIGNAL["signal_id"]])

    def test_second_call_dedups_daily_and_does_not_duplicate_manifest(self):
        self.assertTrue(self._emit(BIOME_SIGNAL, ingest_manifest=True))
        self.assertFalse(self._emit(BIOME_SIGNAL, ingest_manifest=True),
                         "second identical emit must dedup away")
        self.assertEqual(len(_rows(self.daily)), 1)
        self.assertEqual(len(_rows(self.manifest)), 1)

    def test_manifest_already_carrying_the_id_is_not_duplicated(self):
        """The cross-day path: the manifest IS the dedup source once it lands."""
        self.manifest.write_text(
            json.dumps({"signal_id": BIOME_SIGNAL["signal_id"], "status": "active"}) + "\n",
            encoding="utf-8")
        self.assertFalse(self._emit(BIOME_SIGNAL, ingest_manifest=True),
                         "an id already in the manifest must dedup the DAILY write away")
        self.assertEqual(_rows(self.daily), [])
        self.assertEqual(len(_rows(self.manifest)), 1)

    def test_new_day_with_manifest_row_stops_the_daily_re_emission(self):
        """The second-order cure: the 187-raw/52-id storm ends after one ingest."""
        self.assertTrue(self._emit(BIOME_SIGNAL, ingest_manifest=True))
        tomorrow = self.sig_dir / "2026-08-28.jsonl"
        written = dedup_signal_append(str(tomorrow), dict(BIOME_SIGNAL),
                                      manifest_path=str(self.manifest),
                                      ingest_manifest=True)
        self.assertFalse(written, "the manifest row must dedup the next day's emission")
        self.assertEqual(_rows(tomorrow), [])
        self.assertEqual(len(_rows(self.manifest)), 1)

    def test_deduped_row_never_mints_a_manifest_row(self):
        """Row-written vs row-deduped — the ruled precondition, both arms."""
        self.daily.write_text(json.dumps(BIOME_SIGNAL) + "\n", encoding="utf-8")
        self.assertFalse(self._emit(BIOME_SIGNAL, ingest_manifest=True))
        self.assertEqual(_rows(self.manifest), [],
                         "a deduped-away row must not ingest")

    def test_manifest_absent_is_created(self):
        self.assertFalse(self.manifest.exists())
        self._emit(BIOME_SIGNAL, ingest_manifest=True)
        self.assertTrue(self.manifest.exists())
        self.assertEqual(len(_rows(self.manifest)), 1)

    def test_manifest_present_with_other_rows_is_appended_not_clobbered(self):
        other = {"signal_id": "sig_unrelated_aaaa", "status": "active", "volume": 10}
        self.manifest.write_text(json.dumps(other) + "\n", encoding="utf-8")
        self._emit(BIOME_SIGNAL, ingest_manifest=True)
        rows = _rows(self.manifest)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], other)
        self.assertEqual(rows[1]["signal_id"], BIOME_SIGNAL["signal_id"])

    def test_manifest_path_none_with_opt_in_is_a_safe_no_op(self):
        written = dedup_signal_append(str(self.daily), dict(BIOME_SIGNAL),
                                      ingest_manifest=True)
        self.assertTrue(written)
        self.assertEqual(len(_rows(self.daily)), 1)
        self.assertEqual(_rows(self.manifest), [])

    def test_manifest_path_equal_to_target_does_not_double_write(self):
        written = dedup_signal_append(str(self.manifest), dict(BIOME_SIGNAL),
                                      manifest_path=str(self.manifest),
                                      ingest_manifest=True)
        self.assertTrue(written)
        self.assertEqual(len(_rows(self.manifest)), 1,
                         "manifest_path == target must not mint a second row")

    def test_id_less_signal_appends_daily_and_never_mints_a_manifest_row(self):
        """Documented no-op: a manifest row without signal_id is unreadable."""
        idless = {"band": "COGNITIVE", "summary": "no identity"}
        self.assertTrue(self._emit(idless, ingest_manifest=True))
        self.assertEqual(len(_rows(self.daily)), 1)
        self.assertEqual(_rows(self.manifest), [],
                         "an id-less signal must not mint an uncollapsible manifest row")


# ══════════════════════════════════════════════════════════════════════════
# NEGATIVE CONTROL — revert the arm in place; the invisibility must return
# ══════════════════════════════════════════════════════════════════════════

class TestNegativeControlArmIsLoadBearing(_SignalTree):

    def _reverted_module(self):
        src = _ATOMIC_APPEND_PATH.read_text(encoding="utf-8")
        self.assertIn(_ARM_SENTINEL, src,
                      "the ingest arm's predicate is gone — the cure was removed "
                      "or renamed; this control cannot revert what is not there")
        reverted = src.replace(_ARM_SENTINEL, "if False and " + _ARM_SENTINEL[3:])
        self.assertNotEqual(reverted, src, "revert did not change the source")
        mod = types.ModuleType("atomic_append_reverted_tic742")
        mod.__file__ = str(_ATOMIC_APPEND_PATH)
        exec(compile(reverted, str(_ATOMIC_APPEND_PATH), "exec"), mod.__dict__)
        return mod

    def test_reverting_the_arm_restores_the_structural_invisibility(self):
        reverted = self._reverted_module()

        # ── REVERT: the pre-cure behaviour, on the identical scenario ──
        written = reverted.dedup_signal_append(
            str(self.daily), dict(BIOME_SIGNAL),
            manifest_path=str(self.manifest), ingest_manifest=True)
        self.assertTrue(written)
        self.assertEqual(_ids(self.daily), [BIOME_SIGNAL["signal_id"]],
                         "the daily write must still land under the revert")
        self.assertEqual(_rows(self.manifest), [],
                         "revert did not reproduce the defect — the manifest "
                         "must stay empty when the arm is neutered")

        # ── RESTORE: the live module heals the same scenario ──
        fresh = Path(self.tmp.name) / "fresh" / "signals"
        fresh.mkdir(parents=True)
        daily2, manifest2 = fresh / f"{DATE}.jsonl", fresh / "active-manifest.jsonl"
        self.assertTrue(dedup_signal_append(
            str(daily2), dict(BIOME_SIGNAL),
            manifest_path=str(manifest2), ingest_manifest=True))
        self.assertEqual(_ids(manifest2), [BIOME_SIGNAL["signal_id"]])

    def test_revert_and_live_differ_only_on_the_manifest_surface(self):
        """The cure changes the manifest and NOTHING about the daily file."""
        reverted = self._reverted_module()
        a = Path(self.tmp.name) / "a" / "signals"
        b = Path(self.tmp.name) / "b" / "signals"
        a.mkdir(parents=True)
        b.mkdir(parents=True)
        reverted.dedup_signal_append(str(a / f"{DATE}.jsonl"), dict(VISITOR_SIGNAL),
                                     manifest_path=str(a / "active-manifest.jsonl"),
                                     ingest_manifest=True)
        dedup_signal_append(str(b / f"{DATE}.jsonl"), dict(VISITOR_SIGNAL),
                            manifest_path=str(b / "active-manifest.jsonl"),
                            ingest_manifest=True)
        self.assertEqual(_rows(a / f"{DATE}.jsonl"), _rows(b / f"{DATE}.jsonl"),
                         "the daily surface must be byte-equal across the revert")
        self.assertEqual(_rows(a / "active-manifest.jsonl"), [])
        self.assertEqual(len(_rows(b / "active-manifest.jsonl")), 1)


# ══════════════════════════════════════════════════════════════════════════
# The DERIVED row shape — every field, both arms (present / absent)
# ══════════════════════════════════════════════════════════════════════════

class TestManifestRowShape(unittest.TestCase):

    def _row(self, signal, target=f"/z/audit-logs/signals/{DATE}.jsonl"):
        sid = signal.get("signal_id", signal.get("id", ""))
        return manifest_row_from_signal(signal, target, sid)

    def test_identity_is_written_as_signal_id_even_when_source_used_id(self):
        row = self._row(VISITOR_SIGNAL)
        self.assertEqual(row["signal_id"], VISITOR_SIGNAL["id"])
        self.assertNotIn("id", row,
                         "manifest-prune.py:365 and mogul-runner.sh:403 key on "
                         "signal_id ONLY; 0/56 live rows carry `id`")

    def test_status_is_always_active(self):
        self.assertEqual(self._row(BIOME_SIGNAL)["status"], "active")
        self.assertEqual(self._row(VISITOR_SIGNAL)["status"], "active")

    def test_source_file_is_dir_plus_basename(self):
        self.assertEqual(self._row(BIOME_SIGNAL)["source_file"], f"signals/{DATE}.jsonl")

    def test_parity_quartet_carried_when_present(self):
        row = self._row(VISITOR_SIGNAL)
        self.assertEqual(row["kind"], "WATCH")
        self.assertEqual(row["band"], "COGNITIVE")
        self.assertEqual(row["volume"], 30)
        self.assertEqual(row["subsystem"], "visitor_economy")

    def test_parity_fields_absent_stay_absent_never_invented(self):
        """The ratified /review 668 law: carry, never invent."""
        row = self._row(BIOME_SIGNAL)
        for f in ("kind", "volume", "max_volume", "subsystem"):
            self.assertNotIn(f, row, f"{f} was invented on a signal that lacks it")
        self.assertEqual(row["band"], "WATCH")  # ...but what IS present is carried

    def test_max_volume_carried_when_present(self):
        row = self._row({**VISITOR_SIGNAL, "max_volume": 100})
        self.assertEqual(row["max_volume"], 100)

    def test_signal_type_from_explicit_key(self):
        row = self._row({**BIOME_SIGNAL, "signal_type": "explicit.type"})
        self.assertEqual(row["signal_type"], "explicit.type")

    def test_signal_type_derived_from_type_when_not_the_record_literal(self):
        self.assertEqual(self._row(BIOME_SIGNAL)["signal_type"], "health_degraded")

    def test_signal_type_omitted_when_type_is_the_record_literal(self):
        self.assertNotIn("signal_type", self._row(VISITOR_SIGNAL),
                         "`type: signal` is the RECORD type, not the signal type")

    def test_summary_chain_summary_then_description_then_payload(self):
        self.assertEqual(self._row({**BIOME_SIGNAL, "summary": "S"})["summary"], "S")
        self.assertEqual(self._row(VISITOR_SIGNAL)["summary"],
                         "3 visitors below trust floor")          # description
        self.assertEqual(self._row(BIOME_SIGNAL)["summary"],
                         "trust floor breached")                  # payload.summary

    def test_summary_omitted_when_no_slot_is_filled(self):
        self.assertNotIn("summary", self._row({"signal_id": "s1", "band": "COGNITIVE"}))

    def test_source_tic_carried_only_when_an_int(self):
        self.assertEqual(self._row({**BIOME_SIGNAL, "source_tic": 742})["source_tic"], 742)
        self.assertNotIn("source_tic", self._row({**BIOME_SIGNAL, "source_tic": "742"}))
        self.assertNotIn("source_tic", self._row(BIOME_SIGNAL))

    def test_payload_and_projection_fields_are_never_written(self):
        row = self._row(BIOME_SIGNAL)
        for f in ("payload", "structural_status", "visible_volume", "heat",
                  "_v2_projection_inputs"):
            self.assertNotIn(f, row)


# ══════════════════════════════════════════════════════════════════════════
# The mounted-bear question: can the projector project it, can the scan count it?
# ══════════════════════════════════════════════════════════════════════════

class TestRowIsReadableByTheAuthoritativeReaders(_SignalTree):

    def test_landed_row_is_counted_by_the_shared_active_ray_predicate(self):
        self._emit(BIOME_SIGNAL, ingest_manifest=True)
        rows = _rows(self.manifest)
        self.assertTrue(is_active_ray(rows[0]),
                        "signal_scan's shared predicate must count the landed row")

    def test_landed_row_is_keyed_by_the_latest_per_id_projection(self):
        self._emit(BIOME_SIGNAL, ingest_manifest=True)
        projected = latest_per_id(_rows(self.manifest))
        self.assertEqual([r.get("signal_id") for r in projected],
                         [BIOME_SIGNAL["signal_id"]])

    def test_landed_row_is_projected_by_manifest_prune(self):
        mp = _load_module(_HERE / "manifest-prune.py", "manifest_prune_t742")
        self._emit(VISITOR_SIGNAL, ingest_manifest=True)
        rec = _rows(self.manifest)[0]
        proj = mp.project_signal(rec, current_tic=742)
        self.assertEqual(proj["structural_status"], "live")
        self.assertGreater(proj["visible_volume"], 0)
        self.assertTrue(is_active_ray({**rec, **proj}))

    def test_manifest_prune_collapse_key_resolves(self):
        """manifest-prune.py:365 keys on rec['signal_id']; a None key would be
        bucketed under a synthetic __no_id__ and never collapsed."""
        self._emit(VISITOR_SIGNAL, ingest_manifest=True)
        self.assertIsNotNone(_rows(self.manifest)[0].get("signal_id"))

    def test_mogul_runner_signal_id_read_resolves(self):
        """mogul-runner.sh:403 reads obj.get('signal_id') and nothing else."""
        self._emit(BIOME_SIGNAL, ingest_manifest=True)
        self.assertEqual(_rows(self.manifest)[0].get("signal_id"),
                         BIOME_SIGNAL["signal_id"])


# ══════════════════════════════════════════════════════════════════════════
# The two REAL opted-in call sites, driven end to end
# ══════════════════════════════════════════════════════════════════════════

class TestRealCallSitesOptIn(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_biome_engine_emit_signal_reaches_the_manifest(self):
        be = _load_module(_HERE / "biome-engine.py", "biome_engine_t742")
        sig_dir = Path(self.tmp.name) / "biome" / "signals"
        sig_dir.mkdir(parents=True)
        be.SIGNAL_DIR = str(sig_dir)      # redirect the REAL emitter (t635 harness)
        sid = be.emit_signal("WATCH", "health_degraded",
                             {"act_id": "act_2", "biome_cycle": 51})
        manifest = sig_dir / "active-manifest.jsonl"
        self.assertIn(sid, _ids(manifest),
                      "the opted-in biome emitter must reach the authoritative set")
        row = _rows(manifest)[0]
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["signal_type"], "health_degraded")
        self.assertTrue(is_active_ray(row))
        # ...and the documented "already exists, skip silently" branch is intact.
        self.assertEqual(be.emit_signal("WATCH", "health_degraded",
                                        {"act_id": "act_2", "biome_cycle": 51}), sid)
        self.assertEqual(len(_rows(manifest)), 1)

    def test_visitor_economy_monitor_emit_signal_reaches_the_manifest(self):
        vm = _load_module(_HERE / "visitor-economy-monitor.py", "visitor_economy_t742")
        al = Path(self.tmp.name) / "visitor" / "audit-logs"
        (al / "signals").mkdir(parents=True)
        signal = vm._emit_signal(str(al), "sig_trust_decay_0123456789ab",
                                 "WATCH", "COGNITIVE", "3 visitors below trust floor")
        manifest = al / "signals" / "active-manifest.jsonl"
        self.assertIn(signal["id"], _ids(manifest),
                      "the opted-in visitor-economy emitter must reach the "
                      "authoritative set")
        row = _rows(manifest)[0]
        self.assertEqual(row["signal_id"], signal["id"])
        self.assertNotIn("id", row)
        self.assertEqual(row["kind"], "WATCH")
        self.assertEqual(row["volume"], 30)
        self.assertEqual(row["subsystem"], "visitor_economy")
        self.assertTrue(is_active_ray(row))


class TestNoLiveSurfaceIsTouched(unittest.TestCase):
    """Fixture-green is fixture-green, and this arm proves the 'fixture' half:
    running the ingest arm leaves the REAL federation manifest byte-untouched.
    If a future edit lets a default path leak into the helper, this fails."""

    def test_module_under_test_is_the_repo_copy(self):
        self.assertEqual(Path(aa.__file__).resolve(), _ATOMIC_APPEND_PATH.resolve())

    def test_live_manifest_is_byte_identical_across_a_full_ingest(self):
        live = _HERE.parents[3] / "audit-logs" / "signals" / "active-manifest.jsonl"
        if not live.exists():
            self.skipTest(f"no live manifest at {live} — nothing to protect")
        before = (live.stat().st_size, live.stat().st_mtime_ns,
                  live.read_bytes().__hash__())
        with tempfile.TemporaryDirectory() as td:
            sig = Path(td) / "signals"
            sig.mkdir(parents=True)
            dedup_signal_append(str(sig / f"{DATE}.jsonl"), dict(BIOME_SIGNAL),
                                manifest_path=str(sig / "active-manifest.jsonl"),
                                ingest_manifest=True)
            self.assertEqual(len(_rows(sig / "active-manifest.jsonl")), 1)
        after = (live.stat().st_size, live.stat().st_mtime_ns,
                 live.read_bytes().__hash__())
        self.assertEqual(before, after,
                         "the live active-manifest.jsonl was mutated by a fixture run")


if __name__ == "__main__":
    unittest.main(verbosity=2)
