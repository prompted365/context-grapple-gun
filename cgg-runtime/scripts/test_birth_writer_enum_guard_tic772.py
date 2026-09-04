#!/usr/bin/env python3
"""Negative-control fixtures for the pending_class ENUM VOCABULARY GUARD at the
TWO BIRTH WRITERS — cpr-extract.py and queue_event_writer.py (B2 wave 10).

RULED: /review 772 round 3 Q9 (Architect-signed, recommended option verbatim:
"SIGN"), basis /review 772 round 2 Q6. Backlog row
`bk-off-enum-drift-field-generic-writer-topology`. Staged artifact
audit-logs/governance/backlog-gunslinger-hoist/B2-wave-10-STAGED-tic772.json
(self-sha c5b574676304f5ab), signed B2-wave-10-SIGNED-tic772.json
(self-sha a94e377876ad8250).

WHY: /review 767 Q4 guarded pending_class at queue-lifecycle-writeback.py and
its own rider said so out loud — "guards at any writer other than
queue-lifecycle-writeback.py" was explicitly NOT satisfied. The contract's
`writer_topology` key names the open half: the drift axis for pending_class is
not free-hand coinage at a verdict site but MULTIPLE WRITERS WITH NO SHARED
CONTRACT. This file is the discriminating proof for the two birth writers.

THE TWO WRITERS ARE NOT SYMMETRIC, and the asymmetry is the finding:
  cpr-extract.py       — mints `evidence_scoped` (Tier-2) / `schema_incomplete`
                         (Tier-3) from its own closed tier vocabulary. BOTH are
                         ON-TABLE since /review 768 round 2. The risk the guard
                         closes here is DRIFT (a future tier-vocabulary edit
                         minting off-table), not present off-table minting.
  queue_event_writer.py — hardcodes `architect_ruling` (HOLD) and
                         `maturity_window` (DEFER) as pending_class defaults.
                         BOTH are OFF-TABLE. The guard therefore REFUSES this
                         writer's own defaults from the moment it lands.

WHAT THIS FILE DOES NOT DECIDE: what those two defaults SHOULD become. That is
the map-vs-admit fork, and it is /review 773's — proposed at
audit-logs/governance/backlog-gunslinger-hoist/
om-w10-pending-class-default-map-vs-admit-fork-tic772.md. The defaults in the
writer are left exactly as they were; the arms below pin the REFUSAL and the
audited hatch, never a substitute value.

THE ARMS (the revert control is what makes the rest mean anything):
  1. CONTRACT-IS-THE-CONTENT — both writers load the enum from
     contracts/pending-class-enum-v1.json; neither inlines the values.
  2. THE RATIFIED FIVE PASS — at both writers, named literally (never derived
     by iterating the enum, which a silent SHRINK would satisfy vacuously).
  3. TYPED REFUSAL — a never-in-corpus coinage and the two off-table defaults
     are refused with `pending_class_off_enum`, and the message names the
     contract file AND /review as the minting authority.
  4. THE AUDITED WAIVE — admits, discloses on stderr, and STAMPS the row.
  5. REVERTED-GUARD CONTROL — revert the cure and watch the exact predicted
     breakage: the same off-table value sails through and lands. If this arm
     ever starts refusing, the arms above are passing for some other reason.
  6. ISOLATION — every case builds its own zone/queue under a
     TemporaryDirectory; nothing reads or writes the federation queue.

ONE HONEST ASYMMETRY IN THE ARM-3 COVERAGE. At queue_event_writer the
novel-coinage refusal is proven END-TO-END through the real CLI path (the
writer accepts an arbitrary `--pending-class`, and the corpus proves it: the
off-table `evidence_pending_calibration` reached queue.jsonl that way at
/review 643). At cpr-extract NO input path can carry an author-supplied
pending_class — the value is chosen by the tier branch in code — so the
end-to-end arm there exercises the SAME comparison from the contract side
(shrink the ratified set; the real mint path must refuse). That is a faithful
simulation of the drift class, not a proof that an author can trip it; an
author cannot, which is precisely why the risk here is drift.

FIXTURE-GREEN, NOT LIVE-GREEN: every arm below runs against temporary fixtures.
No arm proves anything about the federation queue's contents.

DOES NOT SATISFY (rider carried verbatim from the wave-10 ruling): "this
increment does NOT adjudicate the map-vs-admit fork (that is /review 773's),
does NOT touch the office_map (standing fence per /review 772 Q5), and does NOT
claim the queue's historical off-table complement cured (retirement of the 3-id
latest-per-id residual landed at /review 772 Q3; the ~232-id all-rows
complement stays apophatically excluded)"

Run:  python3 -m unittest test_birth_writer_enum_guard_tic772
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(module_name, filename):
    """Load a (possibly hyphenated) script as a module."""
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ce = _load("cpr_extract_enum_guard_under_test", "cpr-extract.py")
qew = _load("queue_event_writer_enum_guard_under_test", "queue_event_writer.py")

# The CURRENT ruled table, named literally. If /review mints a sixth value this
# tuple is amended in the same pass as the contract file — that is the point.
# (The wave-9 currency scar: a stale THREE-value expectation reads a FALSE
# off-table population — 17 ids instead of 3.)
RULED_PENDING_CLASSES_AT_772 = (
    "evidence_insufficient", "evidence_scoped", "feedback_required",
    "schema_incomplete", "stability_window",
)
# The two BIRTH-minted classes accreted at /review 768 round 2 — exactly the
# members a stale-three reading drops on the floor.
ACCRETED_AT_768 = ("evidence_scoped", "schema_incomplete")
# queue_event_writer's OWN hardcoded defaults, both off-table. NOT fixtures —
# these are read off the writer's DEFER/HOLD branch.
QEW_HOLD_DEFAULT = "architect_ruling"
QEW_DEFER_DEFAULT = "maturity_window"
# A never-in-corpus coinage — the purest instance of the class the contract's
# minting_authority clause forbids ("never coined at a write boundary").
NOVEL_COINAGE = "probe_novel_value_tic772"


# ===========================================================================
# ARM 1 — engine-content separation: the CONTRACT is the content
# ===========================================================================

class TestContractIsTheContent(unittest.TestCase):
    def test_both_writers_load_the_same_contract_file(self):
        for mod in (ce, qew):
            self.assertEqual(mod.PENDING_CLASS_CONTRACT_FILE,
                             "pending-class-enum-v1.json")
            self.assertTrue((mod._CONTRACTS_DIR / mod.PENDING_CLASS_CONTRACT_FILE).is_file())
            self.assertTrue(mod.PENDING_CLASS_ENUM, "enum is empty")

    def test_both_writers_agree_with_the_lifecycle_writer_on_the_vocabulary(self):
        """One contract, three guarded writers — the whole point of the row."""
        qlw = _load("qlw_parity_probe", "queue-lifecycle-writeback.py")
        self.assertEqual(ce.PENDING_CLASS_ENUM, qew.PENDING_CLASS_ENUM)
        self.assertEqual(ce.PENDING_CLASS_ENUM, qlw.FIELD_ENUMS["pending_class"])

    def test_the_five_ruled_values_are_named_not_derived(self):
        """Named literally so a silent enum SHRINK cannot pass vacuously — the
        failure mode an iterate-the-enum assertion cannot see."""
        for mod in (ce, qew):
            self.assertEqual(sorted(mod.PENDING_CLASS_ENUM),
                             sorted(RULED_PENDING_CLASSES_AT_772))
            for value in ACCRETED_AT_768:
                self.assertIn(value, mod.PENDING_CLASS_ENUM)

    def test_no_writer_inlines_the_enum_values(self):
        """Engine-content separation, checked at the SOURCE: the ratified values
        may appear in prose/comments, but never as a literal frozenset/list the
        engine reads instead of the contract."""
        for filename in ("cpr-extract.py", "queue_event_writer.py"):
            src = Path(_HERE, filename).read_text(encoding="utf-8")
            self.assertIn('PENDING_CLASS_CONTRACT["enum"].keys()', src,
                          f"{filename} must derive the enum from the contract")

    def test_the_refusal_message_names_the_contract_and_the_authority(self):
        for mod in (ce, qew):
            msg = mod.pending_class_refusal_message(NOVEL_COINAGE, "loc")
            self.assertIn("contracts/pending-class-enum-v1.json", msg)
            self.assertIn("MINTING AUTHORITY", msg)
            self.assertIn("/review", msg)
            for value in RULED_PENDING_CLASSES_AT_772:
                self.assertIn(value, msg, "the refusal must name the ratified five")


# ===========================================================================
# ARM 2/3 — the predicate: five pass, off-table refuses, absence is lawful
# ===========================================================================

class TestPredicateAtBothWriters(unittest.TestCase):
    def test_the_ratified_five_are_lawful_at_both_writers(self):
        for mod in (ce, qew):
            for value in RULED_PENDING_CLASSES_AT_772:
                self.assertEqual(mod.classify_pending_class(value), "lawful", value)

    def test_absence_is_lawful_at_both_writers(self):
        """The contract's `absence` key: field absent (or null) = no pending
        class asserted — the lawful representation off the DEFER landing."""
        for mod in (ce, qew):
            self.assertEqual(mod.classify_pending_class(None), "lawful")
            self.assertEqual(mod.classify_pending_class(""), "lawful")

    def test_novel_coinage_and_non_strings_are_off_enum_at_both_writers(self):
        for mod in (ce, qew):
            self.assertEqual(mod.classify_pending_class(NOVEL_COINAGE), "off_enum")
            self.assertEqual(mod.classify_pending_class(7), "off_enum")
            self.assertEqual(mod.classify_pending_class(["feedback_required"]),
                             "off_enum")

    def test_the_qew_hardcoded_defaults_are_off_table(self):
        """The measured premise, re-pinned as a test: this writer's own DEFER
        and HOLD defaults are NOT ratified values. Curing that is /review 773's
        map-vs-admit fork; refusing them is this increment's."""
        for value in (QEW_HOLD_DEFAULT, QEW_DEFER_DEFAULT):
            self.assertEqual(qew.classify_pending_class(value), "off_enum")
            self.assertNotIn(value, RULED_PENDING_CLASSES_AT_772)


# ===========================================================================
# queue_event_writer — end-to-end at the write boundary
# ===========================================================================

class _TmpQueue(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="w10-enum-guard-")
        self.dir = Path(self._td.name)
        self.q = self.dir / "queue.jsonl"
        self.q.write_text(json.dumps({
            "id": "cpr_w10_fixture", "status": "extracted", "type": "cogpr",
            "lesson": "A vocabulary that depends on producer restraint is not a "
                      "vocabulary; it is a habit.",
            "current_formulation": "A vocabulary that depends on producer "
                                   "restraint is not a vocabulary; it is a habit.",
        }) + "\n", encoding="utf-8")
        self.addCleanup(self._td.cleanup)

    def rows(self):
        return [json.loads(ln) for ln in
                self.q.read_text(encoding="utf-8").splitlines() if ln.strip()]


class TestQueueEventWriterGuard(_TmpQueue):
    def _build(self, verdict, **kw):
        return qew.build_event("cpr_w10_fixture", verdict, 772,
                               "audit-logs/governance/backlog-gunslinger-hoist/"
                               "B2-wave-10-SIGNED-tic772.json", self.q, **kw)

    def test_bare_hold_is_refused_typed(self):
        with self.assertRaises(qew.PendingClassOffEnum) as ctx:
            self._build("HOLD")
        self.assertEqual(ctx.exception.code, "pending_class_off_enum")
        self.assertEqual(ctx.exception.value, QEW_HOLD_DEFAULT)

    def test_bare_defer_is_refused_typed(self):
        with self.assertRaises(qew.PendingClassOffEnum) as ctx:
            self._build("DEFER")
        self.assertEqual(ctx.exception.value, QEW_DEFER_DEFAULT)

    def test_an_explicit_novel_coinage_is_refused(self):
        """The corpus proves this path is real: `evidence_pending_calibration`
        reached queue.jsonl through an explicit --pending-class at /review 643."""
        with self.assertRaises(qew.PendingClassOffEnum) as ctx:
            self._build("DEFER", pending_class=NOVEL_COINAGE)
        self.assertEqual(ctx.exception.value, NOVEL_COINAGE)

    def test_all_five_ruled_values_write_through(self):
        for value in RULED_PENDING_CLASSES_AT_772:
            ev = self._build("DEFER", pending_class=value)
            self.assertEqual(ev["pending_class"], value)
            self.assertEqual(ev["patch"]["pending_class"], value,
                             "row and patch mirror must agree")
            self.assertNotIn("queue_event_writer", ev,
                             "a lawful write carries NO waive stamp")

    def test_the_waive_admits_and_stamps_and_discloses(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            ev = self._build("HOLD", waive_enum_guard=("pending_class",))
        self.assertEqual(ev["pending_class"], QEW_HOLD_DEFAULT)
        self.assertEqual(ev["queue_event_writer"]["enum_guard_waived"],
                         {"pending_class": QEW_HOLD_DEFAULT})
        self.assertIn("ENUM-GUARD-WAIVE-NOTICE", buf.getvalue())

    def test_a_refusal_appends_nothing(self):
        before = self.q.read_bytes()
        with self.assertRaises(qew.PendingClassOffEnum):
            self._build("DEFER")
        self.assertEqual(self.q.read_bytes(), before)

    def test_non_defer_verdicts_are_untouched_by_this_increment(self):
        """No-regression tripwire: pending_class lives only on the DEFER/HOLD
        branch, so PROMOTE/SKIP_WITH_HOME must be unmoved."""
        ev = self._build("PROMOTE", promoted_to="ledger.md#anchor")
        self.assertNotIn("pending_class", ev)
        self.assertEqual(ev["status"], "promoted")
        ev = self._build("SKIP_WITH_HOME", home="harpoon-office/lane")
        self.assertNotIn("pending_class", ev)

    def test_the_blank_body_refusal_still_fires_first(self):
        """No-regression tripwire: hard invariant #4 (unconditional blank
        refusal) must not be shadowed by the new guard."""
        (self.dir / "empty.jsonl").write_text("", encoding="utf-8")
        with self.assertRaises(SystemExit):
            qew.build_event("cpr_never_seen", "DEFER", 772, "auth",
                            self.dir / "empty.jsonl")


class TestQueueEventWriterCLI(_TmpQueue):
    def _cli(self, argv):
        import subprocess
        import sys as _sys
        return subprocess.run(
            [_sys.executable, os.path.join(_HERE, "queue_event_writer.py"),
             "--queue", str(self.q), "--id", "cpr_w10_fixture",
             "--review-tic", "772", "--authority", "B2-wave-10-SIGNED-tic772.json"]
            + argv, capture_output=True, text=True)

    def test_cli_refusal_exits_2_and_appends_nothing(self):
        before = self.q.read_bytes()
        r = self._cli(["--verdict", "DEFER"])
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("pending_class_off_enum", r.stderr)
        self.assertIn("contracts/pending-class-enum-v1.json", r.stderr)
        self.assertIn("MINTING AUTHORITY", r.stderr)
        self.assertEqual(self.q.read_bytes(), before)

    def test_cli_dry_run_is_refused_too(self):
        """A --dry-run that PRINTED an off-table row would be a lawful-looking
        preview of an unlawful write."""
        r = self._cli(["--verdict", "HOLD", "--dry-run"])
        self.assertEqual(r.returncode, 2, r.stderr)

    def test_cli_waive_flag_admits(self):
        r = self._cli(["--verdict", "HOLD", "--dry-run",
                       "--waive-enum-guard", "pending_class"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ENUM-GUARD-WAIVE-NOTICE", r.stderr)
        ev = json.loads(r.stdout)
        self.assertEqual(ev["pending_class"], QEW_HOLD_DEFAULT)
        self.assertEqual(ev["queue_event_writer"]["enum_guard_waived"],
                         {"pending_class": QEW_HOLD_DEFAULT})


# ===========================================================================
# cpr-extract — end-to-end at the birth boundary
# ===========================================================================

def _block(cpr_id, body):
    return f"<!-- --agnostic-candidate\nid: {cpr_id}\nstatus: pending\n{body}-->\n"


TIER3_BLOCK = _block("cpr_w10_tier3", "lesson: a lesson with no source at all\n")
TIER2_BLOCK = _block("cpr_w10_tier2",
                     "title: a title\nevidence: some evidence line\n")


class _TmpZone(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="w10-extract-guard-")
        self.zone = Path(self._td.name)
        (self.zone / ".ticzone").write_text(json.dumps({"name": "fixture-zone"}),
                                            encoding="utf-8")
        (self.zone / "audit-logs" / "tics").mkdir(parents=True)
        (self.zone / "audit-logs" / "tics" / "f.jsonl").write_text(
            json.dumps({"type": "tic", "domain_counter_after": 772}) + "\n",
            encoding="utf-8")
        (self.zone / "CLAUDE.md").write_text(
            "# fixture doctrine\n" + TIER3_BLOCK + TIER2_BLOCK, encoding="utf-8")
        self.addCleanup(self._td.cleanup)

    def extract(self, **kw):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            entries, counters = ce.extract_cprs(str(self.zone), dry_run=True, **kw)
        return entries, counters, err.getvalue()


class TestCprExtractGuard(_TmpZone):
    def test_the_live_tier_mints_are_ON_TABLE_today(self):
        """THE STAGED PREMISE, re-measured as a test: cpr-extract's two mints
        are lawful right now, so this guard closes DRIFT, not a live defect. If
        this arm ever fails, the premise moved and the row needs re-scoping."""
        entries, _, _ = self.extract()
        minted = {e["id"]: e.get("pending_class") for e in entries}
        self.assertEqual(minted["cpr_w10_tier3"], "schema_incomplete")
        self.assertEqual(minted["cpr_w10_tier2"], "evidence_scoped")
        for value in minted.values():
            self.assertEqual(ce.classify_pending_class(value), "lawful")

    def test_a_tier1_row_carries_no_pending_class_and_is_untouched(self):
        """Absence is the lawful form; the guard fires on writes, not presence."""
        (self.zone / "CLAUDE.md").write_text(
            "# fixture\n" + _block("cpr_w10_tier1",
                                   "lesson: a full lesson\nsource: fixture.md:1\n"),
            encoding="utf-8")
        entries, _, _ = self.extract()
        self.assertEqual(len(entries), 1)
        self.assertNotIn("pending_class", entries[0])

    def test_a_drifted_tier_vocabulary_is_REFUSED_at_the_birth_boundary(self):
        """THE DRIFT ARM. No author input can reach this field — the value is
        chosen in code — so the drift is simulated from the contract side of the
        same comparison: shrink the ratified set and the real mint path must
        refuse with the typed code, appending nothing."""
        saved = ce.PENDING_CLASS_ENUM
        ce.PENDING_CLASS_ENUM = frozenset({NOVEL_COINAGE})
        try:
            with self.assertRaises(ce.PendingClassOffEnum) as ctx:
                self.extract()
            self.assertEqual(ctx.exception.code, "pending_class_off_enum")
            self.assertIn(ctx.exception.value, ACCRETED_AT_768)
        finally:
            ce.PENDING_CLASS_ENUM = saved

    def test_the_stale_three_revert_flips_exactly_the_two_accreted_members(self):
        """The wave-9 currency scar, re-armed at the BIRTH writer. Revert the
        table to the stale THREE and watch the exact predicted breakage:
        precisely the two /review-768 accretions flip lawful -> off_enum, and
        cpr-extract — whose ONLY two mints are those very members — stops
        extracting entirely. Restore and it extracts again."""
        saved = ce.PENDING_CLASS_ENUM
        stale_three = frozenset({"feedback_required", "stability_window",
                                 "evidence_insufficient"})
        ce.PENDING_CLASS_ENUM = stale_three
        try:
            flipped = sorted(v for v in RULED_PENDING_CLASSES_AT_772
                             if ce.classify_pending_class(v) != "lawful")
            self.assertEqual(flipped, sorted(ACCRETED_AT_768))
            with self.assertRaises(ce.PendingClassOffEnum):
                self.extract()
        finally:
            ce.PENDING_CLASS_ENUM = saved
        entries, _, _ = self.extract()
        self.assertEqual(len(entries), 2, "restored: both mints extract again")

    def test_the_waive_admits_and_stamps_and_discloses(self):
        saved = ce.PENDING_CLASS_ENUM
        ce.PENDING_CLASS_ENUM = frozenset({NOVEL_COINAGE})
        try:
            entries, _, err = self.extract(waive_enum_guard=["pending_class"])
        finally:
            ce.PENDING_CLASS_ENUM = saved
        self.assertEqual(len(entries), 2)
        for e in entries:
            self.assertEqual(e["cpr_extract"]["enum_guard_waived"],
                             {"pending_class": e["pending_class"]})
        self.assertIn("ENUM-GUARD-WAIVE-NOTICE", err)

    def test_a_lawful_extraction_carries_no_waive_stamp(self):
        """The stamp is evidence the hatch FIRED — absent otherwise."""
        entries, _, _ = self.extract()
        for e in entries:
            self.assertNotIn("cpr_extract", e)

    def test_cli_refusal_exits_2(self):
        import subprocess
        import sys as _sys
        env = dict(os.environ)
        r = subprocess.run(
            [_sys.executable, "-c",
             "import importlib.util,sys;"
             f"spec=importlib.util.spec_from_file_location('m',{os.path.join(_HERE, 'cpr-extract.py')!r});"
             "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
             "m.PENDING_CLASS_ENUM=frozenset({'nothing_matches'});"
             f"sys.argv=['cpr-extract','--project-dir',{str(self.zone)!r},'--dry-run'];"
             "sys.exit(m.main())"],
            capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("pending_class_off_enum", r.stderr)
        self.assertIn("NOTHING was appended", r.stderr)


# ===========================================================================
# ARM 5 — the REVERTED-GUARD control: does any of this discriminate?
# ===========================================================================

class TestRevertedGuardControl(_TmpQueue):
    """Revert the cure and watch the exact predicted breakage.

    With `classify_pending_class` reverted to the pre-increment behaviour
    (everything lawful — which is exactly what these writers did before this
    increment), the SAME off-table value that every arm above refuses sails
    through and lands on the row. If this arm ever starts refusing, the arms
    above are passing for a reason other than the guard.
    """

    @contextlib.contextmanager
    def _guard_reverted(self, mod):
        saved = mod.classify_pending_class
        mod.classify_pending_class = lambda value: "lawful"
        try:
            yield
        finally:
            mod.classify_pending_class = saved

    def test_reverted_guard_lets_the_qew_default_through(self):
        with self._guard_reverted(qew):
            ev = qew.build_event("cpr_w10_fixture", "HOLD", 772, "auth", self.q)
        self.assertEqual(ev["pending_class"], QEW_HOLD_DEFAULT)
        self.assertNotIn("queue_event_writer", ev,
                         "unguarded minting is SILENT — no stamp, no notice; "
                         "that is the defect this increment closes")

    def test_reverted_guard_lets_a_novel_coinage_through(self):
        with self._guard_reverted(qew):
            ev = qew.build_event("cpr_w10_fixture", "DEFER", 772, "auth", self.q,
                                 pending_class=NOVEL_COINAGE)
        self.assertEqual(ev["pending_class"], NOVEL_COINAGE)

    def test_the_guard_is_restored_after_the_control(self):
        """The control must not leak — the refusal has to still fire after."""
        with self._guard_reverted(qew):
            pass
        with self.assertRaises(qew.PendingClassOffEnum):
            qew.build_event("cpr_w10_fixture", "HOLD", 772, "auth", self.q)


class TestRevertedGuardControlAtExtract(_TmpZone):
    def test_reverted_guard_lets_a_drifted_mint_through(self):
        saved_classify = ce.classify_pending_class
        saved_enum = ce.PENDING_CLASS_ENUM
        ce.PENDING_CLASS_ENUM = frozenset({NOVEL_COINAGE})   # everything drifts
        ce.classify_pending_class = lambda value: "lawful"   # ...and nothing guards
        try:
            entries, _, err = self.extract()
        finally:
            ce.classify_pending_class = saved_classify
            ce.PENDING_CLASS_ENUM = saved_enum
        self.assertEqual(len(entries), 2, "unguarded: the drifted mints land")
        self.assertNotIn("ENUM-GUARD-WAIVE-NOTICE", err)
        # restored: the same extraction refuses again
        ce.PENDING_CLASS_ENUM = frozenset({NOVEL_COINAGE})
        try:
            with self.assertRaises(ce.PendingClassOffEnum):
                self.extract()
        finally:
            ce.PENDING_CLASS_ENUM = saved_enum


# ===========================================================================
# ARM 6 — isolation: no fixture in this file can reach the federation queue
# ===========================================================================

class TestIsolation(_TmpQueue, _TmpZone):
    def setUp(self):
        _TmpQueue.setUp(self)
        _TmpZone.setUp(self)

    def test_the_fixture_queue_is_not_the_federation_queue(self):
        federation = qew.M.QUEUE
        self.assertNotEqual(Path(federation).resolve(), self.q.resolve())

    def test_extraction_writes_into_the_fixture_zone_only(self):
        """dry_run=True everywhere above; this arm proves the resolved queue
        path for the fixture zone is inside the TemporaryDirectory."""
        from zone_root import audit_logs_path, load_ticzone
        resolved = Path(audit_logs_path(str(self.zone),
                                        load_ticzone(str(self.zone)))) / "cprs" / "queue.jsonl"
        self.assertIn(str(self.zone), str(resolved))
        self.assertFalse(resolved.exists(), "dry-run arms create no queue file")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
