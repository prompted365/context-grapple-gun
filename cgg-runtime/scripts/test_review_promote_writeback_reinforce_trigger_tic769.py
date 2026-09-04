#!/usr/bin/env python3
"""Tests for the LANDING-KIND-KEYED reinforce trigger in review-promote-writeback.py.

Row: `bk-reinforced-by-stamper-trigger-never-keyed` (B2 wave 7 row B), in the RE-SCOPED
shape ruled at /review 768 (the original ">=23 unstamped" premise was same-day-falsified;
the row was re-scoped to the TYPING gap) and signed at /review 769
(B2-wave-7-STAGED-tic769.json fc6559c303cf5970 / B2-wave-7-SIGNED-tic769.json 2a01f061284849d4).

WHAT IS UNDER TEST: `stamp_reinforced_by` has been BUILT and LIVE since tic 377, but its
only trigger was a hand-typed `--reinforce-target-anchor` flag — nothing in the runtime
read `landing_kind` and armed it. These arms prove the keying: the REINFORCE FAMILY is
READ from `contracts/landing-kind-enum-v1.json` (never hardcoded, never minted here), the
trigger arms on a family member and fail-closes on every other shape, and the stamp fires
without a hand-typed anchor.

⚠ DOES-NOT-SATISFY RIDER (verbatim from the module under test; reproduced here so a reader
of a GREEN suite cannot mistake it for the live gap being closed):

  This keying does NOT by itself make a live reinforce landing fire the stamper
  end-to-end: the tic-481 physics boundary (`lib/atomic-append.sh:43-45`) requires a
  TRUTHY `promoted_to` before it invokes this script, and 0 of the 14 latest-per-id
  `reinforce_existing` rows carry one (all 14 carry `absorbed_into`; measured tic 769).
  Reaching that boundary is an OWED MOTION outside this increment's fence. Nor does
  this keying retro-stamp: NO backfill sweep ran (a separate later receipted motion).

EVIDENCE CLASS: every arm below is FIXTURE-GREEN (temp-dir ledgers, temp-dir queues, a
temp-dir contract). Fixture-green is not live-green and is not trainer-green; no arm here
touches the real ledgers, the real queue, or the real contract except to READ them in
TestFamilyIsReadFromTheShippedContract.

Run:  python3 -m pytest -q --continue-on-collection-errors -p no:cacheprovider \
        test_review_promote_writeback_reinforce_trigger_tic769.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "review-promote-writeback.py")
_SPEC = importlib.util.spec_from_file_location("review_promote_writeback", _SCRIPT)
rpw = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rpw)

# The rider text, pinned so a future edit that drops it fails LOUD (a green suite must not
# be able to outlive the honest limit it was shipped with).
_RIDER_PHRASES = (
    "This keying does NOT by itself make a live reinforce landing fire the stamper",
    "requires a\n#   TRUTHY `promoted_to` before it invokes this script",
    "NO backfill sweep ran",
)


def _ledger(anchor="demo-invariant-anchor", heading="Demo invariant"):
    """A ledger fixture in the REAL shape: `### heading`, then `<a id="anchor"></a>`,
    then the body, bounded by the next heading (mirrors constitution-ledger/ledger.md)."""
    return (
        "# Ledger\n\n"
        "### An earlier entry\n\n"
        '<a id="an-earlier-entry"></a>\n\n'
        "earlier body\n\n"
        f"### {heading}\n\n"
        f'<a id="{anchor}"></a>\n\n'
        "the entry body\n\n"
        "### A later entry\n\n"
        '<a id="a-later-entry"></a>\n\n'
        "later body\n"
    )


def _contract(values):
    """A landing-kind contract fixture. `values` maps landing_kind -> description; the
    REINFORCE FAMILY is whatever subset of those descriptions mandates the stamp."""
    return json.dumps({"schema_version": "landing-kind-enum-v1-fixture", "enum": values})


_MANDATE = ("ABSORB-side -> absorbed (already-present): the wisdom is already at the top; "
            "this born truth adds resilience/persistence, not a new item. Set "
            "absorbed_reason AND stamp a reinforced_by breadcrumb on the TARGET doctrine item.")
_NO_MANDATE = ("PROMOTE-side -> promoted: a ray on an existing ledger anchor; promoted_to "
               "names the anchor and the clause.")


class _Fixture(unittest.TestCase):
    """Shared temp-dir scaffolding: a queue, a contract, and a ledger — all disposable."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.ledger = self.dir / "ledger.md"
        self.ledger.write_text(_ledger(), encoding="utf-8")
        self.contract = self.dir / "landing-kind-enum-v1.json"
        self.contract.write_text(
            _contract({"reinforce_existing": _MANDATE, "refinement_ray": _NO_MANDATE}),
            encoding="utf-8")

    def _queue(self, rows):
        q = self.dir / "queue.jsonl"
        q.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return q

    def _row(self, cpr_id, landing_kind="reinforce_existing", status="absorbed",
             absorbed_into=None, **extra):
        r = {"id": cpr_id, "status": status, "landing_kind": landing_kind,
             "absorbed_into": (absorbed_into if absorbed_into is not None
                               else "ledger.md#demo-invariant-anchor")}
        r.update(extra)
        return r


# ---------------------------------------------------------------------------
# A. THE FAMILY IS CONTENT, NOT ENGINE (engine-content separation).
# ---------------------------------------------------------------------------

class TestFamilyIsReadFromTheShippedContract(unittest.TestCase):
    """Reads the REAL shipped contract — the one arm here that touches a live surface,
    and read-only. `landing_kind` is OPEN-BY-/review, so the engine must never enumerate
    the family itself."""

    def test_shipped_contract_yields_reinforce_existing(self):
        fam, prov = rpw.resolve_reinforce_landing_kinds()
        self.assertTrue(prov["resolved"], prov)
        self.assertIn("reinforce_existing", fam)
        self.assertEqual(prov["schema_version"], "landing-kind-enum-v1")

    def test_promote_side_values_are_not_in_the_family(self):
        fam, _ = rpw.resolve_reinforce_landing_kinds()
        for promote_side in ("refinement_ray", "typed_guard", "new_anchor",
                             "resubmit_higher"):
            self.assertNotIn(promote_side, fam)

    def test_other_absorb_side_values_are_not_in_the_family(self):
        """concede_local / content_empty_stub_twin / refinement_tail are ABSORB-side but
        their contract text mandates NO stamp — family membership is the stamp mandate,
        not the ABSORB side."""
        fam, _ = rpw.resolve_reinforce_landing_kinds()
        for absorb_side in ("concede_local", "content_empty_stub_twin", "refinement_tail"):
            self.assertNotIn(absorb_side, fam)


class TestFamilyIsContractDerivedNotHardcoded(_Fixture):
    def test_a_ninth_value_mandating_the_stamp_joins_the_family(self):
        """The accretion proof: /review mints a value; the family grows with the CONTRACT
        and this engine is unchanged. If the family were hardcoded this arm would fail."""
        c = self.dir / "accreted.json"
        c.write_text(_contract({
            "reinforce_existing": _MANDATE,
            "refinement_ray": _NO_MANDATE,
            "reinforce_cross_rung": "ABSORB-side: a down-audit rediscovery — set "
                                    "absorbed_reason AND stamp a reinforced_by breadcrumb "
                                    "on the TARGET doctrine item.",
        }), encoding="utf-8")
        fam, prov = rpw.resolve_reinforce_landing_kinds(contract_path=c)
        self.assertEqual(fam, frozenset({"reinforce_existing", "reinforce_cross_rung"}))
        self.assertTrue(prov["resolved"])

    def test_trigger_arms_on_the_accreted_value_without_touching_the_engine(self):
        c = self.dir / "accreted.json"
        c.write_text(_contract({
            "reinforce_cross_rung": "stamp a reinforced_by breadcrumb on the TARGET item.",
        }), encoding="utf-8")
        q = self._queue([self._row("cpr_x_tic700", landing_kind="reinforce_cross_rung")])
        t = rpw.resolve_reinforce_trigger("cpr_x_tic700", queue_path=q, contract_path=c,
                                          ledger_override=str(self.ledger))
        self.assertTrue(t["armed"], t)
        self.assertEqual(t["landing_kind"], "reinforce_cross_rung")


class TestFamilyFailsClosed(_Fixture):
    def test_missing_contract_yields_empty_family_and_disarms(self):
        q = self._queue([self._row("cpr_x_tic700")])
        missing = self.dir / "nope.json"
        fam, prov = rpw.resolve_reinforce_landing_kinds(contract_path=missing)
        self.assertEqual(fam, frozenset())
        self.assertEqual(prov["reason"], "landing_kind_contract_not_found")
        t = rpw.resolve_reinforce_trigger("cpr_x_tic700", queue_path=q,
                                          contract_path=missing)
        self.assertFalse(t["armed"])
        self.assertIn("reinforce_family_unresolved_fail_closed", t["reason"])

    def test_malformed_contract_yields_empty_family(self):
        bad = self.dir / "bad.json"
        bad.write_text("{not json at all", encoding="utf-8")
        fam, prov = rpw.resolve_reinforce_landing_kinds(contract_path=bad)
        self.assertEqual(fam, frozenset())
        self.assertIn("landing_kind_contract_unreadable", prov["reason"])

    def test_contract_without_enum_map_yields_empty_family(self):
        noenum = self.dir / "noenum.json"
        noenum.write_text(json.dumps({"schema_version": "x"}), encoding="utf-8")
        fam, prov = rpw.resolve_reinforce_landing_kinds(contract_path=noenum)
        self.assertEqual(fam, frozenset())
        self.assertEqual(prov["reason"], "landing_kind_contract_has_no_enum_map")

    def test_contract_whose_values_mandate_nothing_yields_empty_family(self):
        none = self.dir / "none.json"
        none.write_text(_contract({"refinement_ray": _NO_MANDATE}), encoding="utf-8")
        fam, prov = rpw.resolve_reinforce_landing_kinds(contract_path=none)
        self.assertEqual(fam, frozenset())
        self.assertEqual(prov["reason"], "no_enum_value_mandates_a_reinforced_by_stamp")


# ---------------------------------------------------------------------------
# B. THE KEYING ITSELF — arms on the family, fail-closes everywhere else.
# ---------------------------------------------------------------------------

class TestTriggerArming(_Fixture):
    def _trigger(self, rows, cpr_id="cpr_x_tic700", **kw):
        q = self._queue(rows)
        return rpw.resolve_reinforce_trigger(
            cpr_id, queue_path=q, contract_path=self.contract,
            ledger_override=str(self.ledger), **kw)

    def test_arms_on_reinforce_existing(self):
        t = self._trigger([self._row("cpr_x_tic700")])
        self.assertTrue(t["armed"], t)
        self.assertEqual(t["landing_kind"], "reinforce_existing")
        self.assertEqual(t["target_anchor"], "demo-invariant-anchor")
        self.assertEqual(t["reinforce_family"], ["reinforce_existing"])

    def test_does_not_arm_on_a_promote_side_landing(self):
        t = self._trigger([self._row("cpr_x_tic700", landing_kind="refinement_ray")])
        self.assertFalse(t["armed"])
        self.assertEqual(t["reason"], "landing_kind_not_in_reinforce_family")

    def test_does_not_arm_when_the_row_carries_no_landing_kind(self):
        """The pre-field corpus: rows landed before landing_kind existed must NOT be
        auto-stamped by a guess — absence asserts no landing kind."""
        row = self._row("cpr_x_tic700")
        row.pop("landing_kind")
        t = self._trigger([row])
        self.assertFalse(t["armed"])
        self.assertEqual(t["reason"], "no_landing_kind_on_row")

    def test_does_not_arm_when_absorbed_into_names_another_cogpr(self):
        """4 of the 14 live reinforce rows absorb into ANOTHER CogPR, not a doctrine
        anchor (measured tic 769). Those must fail closed, never guess a ledger entry."""
        t = self._trigger([self._row("cpr_x_tic700",
                                     absorbed_into="cpr_mogul_review_close_check_0150ad7b7a2c")])
        self.assertFalse(t["armed"])
        self.assertEqual(t["reason"], "absorbed_into_names_cogpr_not_doctrine_anchor")

    def test_does_not_arm_when_absorbed_into_has_no_anchor(self):
        t = self._trigger([self._row("cpr_x_tic700", absorbed_into="ledger.md#")])
        self.assertFalse(t["armed"])
        self.assertEqual(t["reason"], "absorbed_into_names_no_anchor")

    def test_does_not_arm_when_absorbed_into_is_missing(self):
        t = self._trigger([self._row("cpr_x_tic700", absorbed_into="")])
        self.assertFalse(t["armed"])
        self.assertEqual(t["reason"], "absorbed_into_missing")

    def test_does_not_arm_when_the_row_is_absent_from_the_queue(self):
        t = self._trigger([self._row("cpr_other_tic1")], cpr_id="cpr_x_tic700")
        self.assertFalse(t["armed"])
        self.assertEqual(t["reason"], "queue_row_not_resolved")

    def test_latest_per_id_governs_a_retype_OUT_of_the_family(self):
        """The A1-767 precedent (496b8fe3085b was re-typed reinforce_existing ->
        refinement_tail): the LATEST row rules, so a re-typed row must NOT arm."""
        t = self._trigger([
            self._row("cpr_x_tic700", landing_kind="reinforce_existing"),
            self._row("cpr_x_tic700", landing_kind="refinement_ray"),
        ])
        self.assertFalse(t["armed"])
        self.assertEqual(t["landing_kind"], "refinement_ray")
        self.assertEqual(t["reason"], "landing_kind_not_in_reinforce_family")

    def test_latest_per_id_governs_a_retype_INTO_the_family(self):
        t = self._trigger([
            self._row("cpr_x_tic700", landing_kind="refinement_ray"),
            self._row("cpr_x_tic700", landing_kind="reinforce_existing"),
        ])
        self.assertTrue(t["armed"], t)
        self.assertEqual(t["landing_kind"], "reinforce_existing")


class TestReinforceTargetResolution(_Fixture):
    def test_bare_ledger_md_resolves_to_the_default_federation_ledger(self):
        """2 of the 14 live rows carry a bare `ledger.md#anchor` (measured tic 769)."""
        led, anchor, why = rpw.resolve_reinforce_target("ledger.md#some-anchor")
        self.assertEqual(anchor, "some-anchor")
        self.assertEqual(why, "resolved_to_default_federation_ledger")
        self.assertTrue(str(led).endswith("constitution-ledger/ledger.md"))

    def test_unresolvable_surface_fails_closed(self):
        led, anchor, why = rpw.resolve_reinforce_target(
            "audit-logs/governance/no-such-dir/nothing.md#anchor")
        self.assertIsNone(led)
        self.assertEqual(why, "reinforce_target_surface_unresolved")


# ---------------------------------------------------------------------------
# C. FIRING — the stamp lands, idempotently, and fails LOUD on a bad anchor.
# ---------------------------------------------------------------------------

class TestFiring(_Fixture):
    def _fire(self, **kw):
        q = self._queue([self._row("cpr_x_tic700")])
        return rpw.fire_reinforce_trigger(
            "cpr_x_tic700", 769, queue_path=q, contract_path=self.contract,
            ledger_override=str(self.ledger), **kw)

    def test_keyed_fire_stamps_the_target_entry(self):
        out = self._fire()
        self.assertTrue(out["trigger"]["armed"])
        self.assertEqual(out["stamp"]["action"], "stamp")
        text = self.ledger.read_text(encoding="utf-8")
        self.assertIn("reinforced_by: cpr_x_tic700", text)
        self.assertIn("landing_kind=reinforce_existing", text)
        # the stamp landed INSIDE its own entry, not in a sibling
        body = text.split("### Demo invariant")[1].split("### A later entry")[0]
        self.assertIn("reinforced_by: cpr_x_tic700", body)

    def test_second_fire_is_idempotent_noop(self):
        self._fire()
        second = self._fire()
        self.assertEqual(second["stamp"]["action"], "noop")
        self.assertEqual(
            self.ledger.read_text(encoding="utf-8").count("reinforced_by: cpr_x_tic700"), 1)

    def test_dry_run_writes_nothing(self):
        before = self.ledger.read_text(encoding="utf-8")
        out = self._fire(dry_run=True)
        self.assertEqual(out["stamp"]["action"], "stamp")
        self.assertEqual(self.ledger.read_text(encoding="utf-8"), before)

    def test_unresolvable_anchor_fails_loud_and_leaves_the_ledger_byte_identical(self):
        q = self._queue([self._row("cpr_x_tic700",
                                   absorbed_into="ledger.md#no-such-entry-anywhere")])
        before = self.ledger.read_text(encoding="utf-8")
        out = rpw.fire_reinforce_trigger(
            "cpr_x_tic700", 769, queue_path=q, contract_path=self.contract,
            ledger_override=str(self.ledger))
        self.assertTrue(out["trigger"]["armed"])
        self.assertEqual(out["stamp"]["action"], "error")
        self.assertIn("entry not found", out["stamp"]["reason"])
        self.assertEqual(self.ledger.read_text(encoding="utf-8"), before)

    def test_not_armed_means_no_stamp_and_no_write(self):
        q = self._queue([self._row("cpr_x_tic700", landing_kind="refinement_ray")])
        before = self.ledger.read_text(encoding="utf-8")
        out = rpw.fire_reinforce_trigger(
            "cpr_x_tic700", 769, queue_path=q, contract_path=self.contract,
            ledger_override=str(self.ledger))
        self.assertFalse(out["trigger"]["armed"])
        self.assertIsNone(out["stamp"])
        self.assertEqual(self.ledger.read_text(encoding="utf-8"), before)


# ---------------------------------------------------------------------------
# D. writeback() INTEGRATION — the third half, and the pre-existing halves intact.
# ---------------------------------------------------------------------------

class TestWritebackIntegration(_Fixture):
    def setUp(self):
        super().setUp()
        self.am = self.dir / "memory"
        self.am.mkdir()

    def test_writeback_fires_the_keyed_trigger_as_a_third_half(self):
        q = self._queue([self._row("cpr_x_tic700")])
        report = rpw.writeback(
            "cpr_x_tic700", "ledger.md#demo-invariant-anchor", 769, status="absorbed",
            search_dir=self.am, queue_path=q, contract_path=self.contract,
            reinforce_ledger=str(self.ledger))
        self.assertTrue(report["summary"]["reinforce_trigger_armed"])
        self.assertEqual(report["summary"]["reinforce_stamp_action"], "stamp")
        self.assertIn("reinforced_by: cpr_x_tic700",
                      self.ledger.read_text(encoding="utf-8"))

    def test_reinforce_trigger_false_disarms_and_writes_nothing(self):
        q = self._queue([self._row("cpr_x_tic700")])
        before = self.ledger.read_text(encoding="utf-8")
        report = rpw.writeback(
            "cpr_x_tic700", "ledger.md#demo-invariant-anchor", 769, status="absorbed",
            search_dir=self.am, queue_path=q, contract_path=self.contract,
            reinforce_ledger=str(self.ledger), reinforce_trigger=False)
        self.assertFalse(report["summary"]["reinforce_trigger_armed"])
        self.assertEqual(report["summary"]["reinforce_trigger_reason"],
                         "reinforce_trigger_disabled_by_caller")
        self.assertEqual(self.ledger.read_text(encoding="utf-8"), before)

    def test_hermetic_default_without_a_queue_fails_closed(self):
        """The pre-existing hermetic contract (search_dir set, no queue_path) skips queue
        resolution — with no queue there is no landing_kind, so the trigger must NOT arm.
        This is what keeps every pre-existing caller and test byte-unchanged."""
        report = rpw.writeback("cpr_x_tic700", "feedback_x.md", 769,
                               status="promoted", search_dir=self.am)
        self.assertFalse(report["summary"]["reinforce_trigger_armed"])
        self.assertEqual(report["summary"]["reinforce_trigger_reason"],
                         "queue_not_resolved_trigger_fail_closed")

    def test_promote_side_row_leaves_both_pre_existing_halves_working(self):
        (self.am / "MEMORY.md").write_text(
            "<!-- --agnostic-candidate\n  id: cpr_x_tic700\n  status: pending\n"
            '  lesson: "l"\n  source: "s"\n-->\n', encoding="utf-8")
        (self.am / "feedback_x.md").write_text("# fb\n\nbody\n", encoding="utf-8")
        q = self._queue([self._row("cpr_x_tic700", landing_kind="refinement_ray",
                                   status="promoted")])
        report = rpw.writeback(
            "cpr_x_tic700", "feedback_x.md", 769, status="promoted",
            search_dir=self.am, queue_path=q, contract_path=self.contract,
            reinforce_ledger=str(self.ledger))
        self.assertEqual(report["summary"]["inline_blocks_flipped"], 1)
        self.assertEqual(report["summary"]["breadcrumb_action"], "stamp")
        self.assertFalse(report["summary"]["reinforce_trigger_armed"])


# ---------------------------------------------------------------------------
# E. THE CLI TRIGGER REGISTRATION — the argparse guard that kept absorb-side landings
#    from ever reaching the stamper.
# ---------------------------------------------------------------------------

class TestCliKeyedMode(_Fixture):
    def _run(self, *extra):
        q = self._queue([self._row("cpr_x_tic700")])
        return subprocess.run(
            [sys.executable, _SCRIPT, "--cpr-id", "cpr_x_tic700", "--review-tic", "769",
             "--queue-path", str(q), "--landing-kind-contract", str(self.contract),
             "--reinforce-ledger", str(self.ledger), *extra],
            capture_output=True, text=True)

    def test_cli_stamps_without_promoted_to_when_the_landing_is_reinforce(self):
        """An ABSORBED reinforce row carries no `promoted_to`. Before the keying, argparse
        refused the invocation outright — the absorb-side landing could never reach the
        stamper. Now the keying is consulted first."""
        p = self._run()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("KEYED on landing_kind=reinforce_existing", p.stdout)
        self.assertIn("reinforced_by: cpr_x_tic700",
                      self.ledger.read_text(encoding="utf-8"))

    def test_cli_usage_error_carries_the_typed_reason_for_a_non_reinforce_row(self):
        q = self._queue([self._row("cpr_x_tic700", landing_kind="refinement_ray")])
        p = subprocess.run(
            [sys.executable, _SCRIPT, "--cpr-id", "cpr_x_tic700", "--review-tic", "769",
             "--queue-path", str(q), "--landing-kind-contract", str(self.contract)],
            capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("landing_kind_not_in_reinforce_family", p.stderr)
        self.assertIn("--promoted-to is required", p.stderr)

    def test_cli_no_reinforce_trigger_flag_disarms_and_errors_bare(self):
        p = self._run("--no-reinforce-trigger")
        self.assertEqual(p.returncode, 2)
        self.assertIn("--promoted-to is required in promote mode", p.stderr)
        self.assertNotIn("reinforced_by: cpr_x_tic700",
                         self.ledger.read_text(encoding="utf-8"))

    def test_cli_dry_run_reports_the_stamp_without_writing(self):
        before = self.ledger.read_text(encoding="utf-8")
        p = self._run("--dry-run")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("(dry-run)", p.stdout)
        self.assertEqual(self.ledger.read_text(encoding="utf-8"), before)

    def test_manual_anchor_mode_still_works_unchanged(self):
        """The keying ADDS an automatic path; it does not remove the hand-typed one."""
        p = subprocess.run(
            [sys.executable, _SCRIPT, "--cpr-id", "cpr_manual_tic700", "--review-tic", "769",
             "--reinforce-target-anchor", "demo-invariant-anchor",
             "--reinforce-source", "down-audit@some-rung",
             "--reinforce-ledger", str(self.ledger)],
            capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("reinforced_by: cpr_manual_tic700",
                      self.ledger.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# F. HONEST-LIMIT PIN — the rider must outlive this suite.
# ---------------------------------------------------------------------------

class TestRiderIsPinnedInSource(unittest.TestCase):
    def test_does_not_satisfy_rider_present_verbatim_in_the_module(self):
        src = Path(_SCRIPT).read_text(encoding="utf-8")
        for phrase in _RIDER_PHRASES:
            self.assertIn(phrase, src,
                          "the does-not-satisfy rider was dropped from the module — a "
                          "green suite may not outlive the honest limit it shipped with")

    def test_rider_names_the_unreached_boundary_and_the_unperformed_backfill(self):
        src = Path(_SCRIPT).read_text(encoding="utf-8")
        self.assertIn("lib/atomic-append.sh:43-45", src)
        self.assertIn("OWED MOTION outside this increment's fence", src)


if __name__ == "__main__":
    unittest.main()
