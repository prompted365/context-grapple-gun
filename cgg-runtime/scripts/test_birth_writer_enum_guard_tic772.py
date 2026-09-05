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
  queue_event_writer.py — hardcoded two OFF-TABLE pending_class defaults (one
                         for HOLD, one for DEFER), so the guard REFUSED this
                         writer's own defaults from the moment it landed.

B2 WAVE 11 AMENDMENT (/review 773 round 1 Q3 — "NO-DEFAULT + ABSENCE",
Architect-ratified verbatim; signed artifact
audit-logs/governance/backlog-gunslinger-hoist/B2-wave-11-SIGNED-tic773.json,
self-sha 3c46db86c0580d4e over STAGED c456ba46492885c5). The fork this file
declined to decide was RULED, and NEITHER of its two branches was taken — not
MAP (lossy for HOLD) and not ADMIT (a /review 768 reversal). Both defaults are
REMOVED:
  bare DEFER -> typed-refused `pending_class_required_for_DEFER` (rc=2). The
    class is a DEFER generator product; the omission is never laundered.
  bare HOLD  -> writes the contract's lawful ABSENCE key, an explicit null.
    HOLD has no generator contract, so no class was ever this writer's to mint.
The enum stays CLOSED-at-five and /review 768 round 2 is HELD (the HOLD
default's token NEVER enters the vocabulary). The arms below now pin the RULED
shape — and the arm-5 control reverts THAT cure, not the wave-10 one.

WHAT THIS FILE STILL DOES NOT DECIDE: the honest pending_class for any specific
DEFER. The arms pass explicit values or ride the audited hatch; none asserts a
mapping.

DOES NOT SATISFY (rider carried verbatim from the wave-11 ruling,
B2-wave-11-SIGNED-tic773.json): "this increment does NOT author a HOLD
generator contract (future work, unruled); does NOT touch the office_map
(standing fence per /review 772 Q5); does NOT re-truth the contract JSON
(seat-owned data surface); does NOT claim the all-rows historical complement
cured"

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
# queue_event_writer's two REMOVED defaults (B2 wave 11 / /review 773 Q3). They
# were off-table then and are off-table now; what changed is that the writer no
# longer holds them — these literals live HERE, in the fixtures, and nowhere in
# the writer's source. TestTheDefaultsAreGone pins that structurally.
QEW_REMOVED_HOLD_DEFAULT = "architect_ruling"
QEW_REMOVED_DEFER_DEFAULT = "maturity_window"
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

    def test_all_three_writers_consume_THE_SAME_guard_lib(self):
        """B2 wave 11 (OM-W10-4) — the STRUCTURAL half of "one contract, N
        writers".

        The vocabulary agreement above is a CONVENTIONAL check: three writers
        that happen to read the same file. It stays green even when the guard
        itself is three faithful copies drifting apart edit by edit. This arm
        asserts the ENGINE is one object — same module identity at all three
        call sites, resolved from cgg-runtime/scripts/lib/ — so a change to the
        predicate cannot reach two writers and miss the third.
        """
        qlw = _load("qlw_lib_probe", "queue-lifecycle-writeback.py")
        libs = {"cpr-extract.py": ce.enum_vocabulary_guard,
                "queue_event_writer.py": qew.enum_vocabulary_guard,
                "queue-lifecycle-writeback.py": qlw.enum_vocabulary_guard}
        first = libs["cpr-extract.py"]
        for name, mod in libs.items():
            self.assertIs(mod, first,
                          f"{name} consumes a DIFFERENT guard module object")
        self.assertEqual(
            Path(first.__file__).resolve(),
            Path(_HERE, "lib", "enum_vocabulary_guard.py").resolve())
        for fn in ("load_contract", "classify", "refusal_message"):
            self.assertTrue(callable(getattr(first, fn)),
                            f"the shared triple is missing {fn}")

    def test_each_writer_names_the_lib_in_its_source(self):
        """Identity alone could be satisfied by an attribute a future edit
        leaves behind after re-inlining the predicate. The import is the
        structural fact; both are asserted."""
        for filename in ("cpr-extract.py", "queue_event_writer.py",
                         "queue-lifecycle-writeback.py"):
            src = Path(_HERE, filename).read_text(encoding="utf-8")
            self.assertIn("import enum_vocabulary_guard", src,
                          f"{filename} must consume the shared guard lib")

    def test_the_empty_string_per_boundary_semantics_are_ruled_law(self):
        """F-773-W11-1 → OM-W11-2, RULED /review 774 round 1 Q4 (PER-BOUNDARY).

        The divergence is no longer a preserved asymmetry awaiting unification —
        it is ruled law: `""` NORMALIZES to absence at the birth boundaries
        (inbound from sources that never chose a value) and is REFUSED off_enum
        at the lifecycle boundary (an explicit-only composer writes null or
        omits, never ""; the /review 773 NO-DEFAULT + ABSENCE ruling's edge).
        The assertions below are unchanged from the pre-ruling pin — they assert
        exactly the ruled semantics; a DRY pass that unifies them now breaks LAW,
        not merely a carried divergence. Contract: pending-class-enum-v1.json
        `absence` key, EMPTY-STRING clause."""
        qlw = _load("qlw_empty_probe", "queue-lifecycle-writeback.py")
        self.assertEqual(ce.classify_pending_class(""), "lawful")
        self.assertEqual(qew.classify_pending_class(""), "lawful")
        self.assertEqual(qlw.classify_enum_value("pending_class", ""), "off_enum")
        # ...and the shared engine carries the difference as a declared flag,
        # never as an inlined assumption.
        lib = ce.enum_vocabulary_guard
        self.assertEqual(lib.classify("", frozenset(), empty_string_is_absence=True),
                         "lawful")
        self.assertEqual(lib.classify("", frozenset(), empty_string_is_absence=False),
                         "off_enum")

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

    def test_the_two_removed_defaults_are_still_off_table_values(self):
        """The wave-10 premise, still true and still load-bearing: both removed
        values remain OFF-TABLE, so a caller who names one explicitly is refused
        unless they ride the audited hatch. Removing a default did not admit it."""
        for value in (QEW_REMOVED_HOLD_DEFAULT, QEW_REMOVED_DEFER_DEFAULT):
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

    def test_bare_hold_asserts_the_lawful_absence_key(self):
        """THE ABSENCE HALF (/review 773 Q3). A bare HOLD is NOT refused: it
        writes the contract's `absence` form — the field PRESENT and null, never
        omitted and never a substituted class — and the patch mirror agrees."""
        ev = self._build("HOLD")
        self.assertIn("pending_class", ev, "absence is EXPLICIT null, not omission")
        self.assertIsNone(ev["pending_class"])
        self.assertIn("pending_class", ev["patch"])
        self.assertIsNone(ev["patch"]["pending_class"])
        self.assertEqual(ev["status"], "enrichment_eligible")
        self.assertNotIn("queue_event_writer", ev, "no hatch fired; none was needed")

    def test_bare_hold_with_an_empty_string_normalizes_to_null(self):
        """"" is a lawful absence form at this boundary; the row must carry the
        contract's canonical null rather than an empty coinage."""
        ev = self._build("HOLD", pending_class="")
        self.assertIsNone(ev["pending_class"])
        self.assertIsNone(ev["patch"]["pending_class"])

    def test_bare_defer_is_refused_typed_as_a_MISSING_INPUT(self):
        """THE NO-DEFAULT HALF. The refusal names the missing input, not a bad
        value — a distinct typed code, because it is a distinct failure."""
        with self.assertRaises(qew.PendingClassRequired) as ctx:
            self._build("DEFER")
        self.assertEqual(ctx.exception.code, "pending_class_required_for_DEFER")

    def test_an_empty_string_defer_is_refused_as_a_missing_input_too(self):
        """The lawful-absence form is still an OMISSION for a DEFER — the
        laundering route a `not value` check would have left open."""
        with self.assertRaises(qew.PendingClassRequired):
            self._build("DEFER", pending_class="")

    def test_the_defer_refusal_hands_back_both_lawful_routes(self):
        """A missing-input refusal owes what a bad-value refusal does not: the
        two doors back, plus the contract and the minting authority."""
        msg = qew.pending_class_required_message("LOC")
        self.assertIn("--pending-class", msg)
        self.assertIn("--waive-enum-guard", msg)
        self.assertIn("contracts/pending-class-enum-v1.json", msg)
        self.assertIn("MINTING AUTHORITY", msg)
        for value in RULED_PENDING_CLASSES_AT_772:
            self.assertIn(value, msg, "the refusal must name the ratified five")

    def test_the_two_refusal_codes_are_distinct(self):
        """Collapsing them would hide WHICH failure occurred at exactly the
        boundary the ruling exists to keep honest."""
        self.assertNotEqual(qew.PendingClassRequired.code,
                            qew.PendingClassOffEnum.code)
        with self.assertRaises(qew.PendingClassOffEnum):
            self._build("DEFER", pending_class=QEW_REMOVED_DEFER_DEFAULT)

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
        """Post-wave-11 the hatch admits a value the CALLER named — there is no
        default left for it to admit. Route (2) of the refusal's own message."""
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            ev = self._build("DEFER", pending_class=QEW_REMOVED_DEFER_DEFAULT,
                             waive_enum_guard=("pending_class",))
        self.assertEqual(ev["pending_class"], QEW_REMOVED_DEFER_DEFAULT)
        self.assertEqual(ev["queue_event_writer"]["enum_guard_waived"],
                         {"pending_class": QEW_REMOVED_DEFER_DEFAULT})
        self.assertIn("ENUM-GUARD-WAIVE-NOTICE", buf.getvalue())

    def test_the_waive_cannot_manufacture_a_missing_value(self):
        """The hatch admits a VALUE; it is not an omission-laundering route. A
        bare DEFER carrying the waive and nothing else is still refused — this
        is the arm that keeps route (2) from becoming a silent default."""
        with self.assertRaises(qew.PendingClassRequired):
            self._build("DEFER", waive_enum_guard=("pending_class",))

    def test_a_refusal_appends_nothing(self):
        before = self.q.read_bytes()
        with self.assertRaises(qew.PendingClassRequired):
            self._build("DEFER")
        with self.assertRaises(qew.PendingClassOffEnum):
            self._build("DEFER", pending_class=NOVEL_COINAGE)
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

    def test_cli_bare_defer_exits_2_and_appends_nothing(self):
        before = self.q.read_bytes()
        r = self._cli(["--verdict", "DEFER"])
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("pending_class_required_for_DEFER", r.stderr)
        self.assertIn("contracts/pending-class-enum-v1.json", r.stderr)
        self.assertIn("MINTING AUTHORITY", r.stderr)
        self.assertEqual(self.q.read_bytes(), before)

    def test_cli_explicit_off_table_exits_2_with_the_OTHER_code(self):
        before = self.q.read_bytes()
        r = self._cli(["--verdict", "DEFER", "--pending-class", NOVEL_COINAGE])
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("pending_class_off_enum", r.stderr)
        self.assertNotIn("pending_class_required_for_DEFER", r.stderr)
        self.assertEqual(self.q.read_bytes(), before)

    def test_cli_dry_run_is_refused_too(self):
        """A --dry-run that PRINTED a defaulted row would be a lawful-looking
        preview of a write nobody authorized."""
        r = self._cli(["--verdict", "DEFER", "--dry-run"])
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("pending_class_required_for_DEFER", r.stderr)

    def test_cli_bare_hold_dry_run_previews_the_explicit_null(self):
        """The ABSENCE half through the real CLI — accepted, not refused."""
        r = self._cli(["--verdict", "HOLD", "--dry-run"])
        self.assertEqual(r.returncode, 0, r.stderr)
        ev = json.loads(r.stdout)
        self.assertIn("pending_class", ev)
        self.assertIsNone(ev["pending_class"])
        self.assertIsNone(ev["patch"]["pending_class"])
        self.assertNotIn("ENUM-GUARD-WAIVE-NOTICE", r.stderr)

    def test_cli_waive_flag_admits_an_explicit_value(self):
        r = self._cli(["--verdict", "HOLD", "--dry-run",
                       "--pending-class", QEW_REMOVED_HOLD_DEFAULT,
                       "--waive-enum-guard", "pending_class"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ENUM-GUARD-WAIVE-NOTICE", r.stderr)
        ev = json.loads(r.stdout)
        self.assertEqual(ev["pending_class"], QEW_REMOVED_HOLD_DEFAULT)
        self.assertEqual(ev["queue_event_writer"]["enum_guard_waived"],
                         {"pending_class": QEW_REMOVED_HOLD_DEFAULT})


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

    def test_reverted_guard_lets_an_explicit_off_table_value_through(self):
        with self._guard_reverted(qew):
            ev = qew.build_event("cpr_w10_fixture", "HOLD", 772, "auth", self.q,
                                 pending_class=QEW_REMOVED_HOLD_DEFAULT)
        self.assertEqual(ev["pending_class"], QEW_REMOVED_HOLD_DEFAULT)
        self.assertNotIn("queue_event_writer", ev,
                         "unguarded minting is SILENT — no stamp, no notice; "
                         "that is the defect the wave-10 increment closes")

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
            qew.build_event("cpr_w10_fixture", "HOLD", 772, "auth", self.q,
                            pending_class=QEW_REMOVED_HOLD_DEFAULT)


class TestWave11DefaultRestoredControl(_TmpQueue):
    """THE WAVE-11 NEGATIVE CONTROL — revert THIS cure, watch the exact
    predicted breakage, restore.

    The cure is a REMOVAL, so the control restores what was removed: a shim that
    supplies the pre-773 default whenever the caller named no class. With it in
    place BOTH ruled behaviours regress, and they regress DIFFERENTLY — which is
    what makes the arms above discriminating rather than merely green:

      bare HOLD  — stops asserting the lawful null and mints the off-table value
                   again (then refused by the wave-10 guard: exactly the tic-772
                   state this increment was dispatched to move).
      bare DEFER — stops being a MISSING-INPUT refusal and becomes a BAD-VALUE
                   refusal. The omission is laundered into a default FIRST and
                   only then rejected — the precise laundering the ruling names.

    If either arm below ever stops breaking, the ruled shapes above are passing
    for some reason other than this cure.
    """

    @contextlib.contextmanager
    def _pre_773_defaults_restored(self):
        original = qew.build_event

        def shim(object_id, verdict, *a, **kw):
            if verdict.upper() in ("DEFER", "HOLD") and not kw.get("pending_class"):
                kw["pending_class"] = (QEW_REMOVED_HOLD_DEFAULT
                                       if verdict.upper() == "HOLD"
                                       else QEW_REMOVED_DEFER_DEFAULT)
            return original(object_id, verdict, *a, **kw)

        qew.build_event = shim
        try:
            yield
        finally:
            qew.build_event = original

    def test_reverted_bare_hold_mints_the_off_table_default_again(self):
        with self._pre_773_defaults_restored():
            with self.assertRaises(qew.PendingClassOffEnum) as ctx:
                qew.build_event("cpr_w10_fixture", "HOLD", 773, "auth", self.q)
        self.assertEqual(ctx.exception.value, QEW_REMOVED_HOLD_DEFAULT)

    def test_reverted_bare_defer_flips_from_missing_input_to_bad_value(self):
        with self._pre_773_defaults_restored():
            with self.assertRaises(qew.PendingClassOffEnum) as ctx:
                qew.build_event("cpr_w10_fixture", "DEFER", 773, "auth", self.q)
        self.assertEqual(ctx.exception.value, QEW_REMOVED_DEFER_DEFAULT)
        self.assertEqual(ctx.exception.code, "pending_class_off_enum")

    def test_the_ruled_shapes_return_after_the_control(self):
        """Restore: the null comes back, and so does the missing-input code."""
        with self._pre_773_defaults_restored():
            pass
        ev = qew.build_event("cpr_w10_fixture", "HOLD", 773, "auth", self.q)
        self.assertIsNone(ev["pending_class"])
        with self.assertRaises(qew.PendingClassRequired):
            qew.build_event("cpr_w10_fixture", "DEFER", 773, "auth", self.q)


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
