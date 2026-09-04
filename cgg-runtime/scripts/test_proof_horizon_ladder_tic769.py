#!/usr/bin/env python3
"""Committed suite for the PROOF-HORIZON LADDER (the horizon axis) — H1.

RULED: /review 769 (in-tic Architect-ratified question set) signed the HORIZON
QUIVER build set H1-H4 staged-lock. Staged decomposition:
audit-logs/governance/harpoon-office/staging/horizon-quiver-admission-and-dag-tic768.md
section 3, row H1 (11,432 B, sha256-16 0fe23c722fe3233b) — "content = a horizon
ladder file ... values are CONTENT, ruled not hardcoded; engine = one comparator
in cgg-runtime lib + tests".

WHAT THIS SUITE HAS TO PROVE, in order of load-bearing weight:

  1. ENGINE-CONTENT SEPARATION IS REAL. Not "the engine has a contract file
     beside it" — that is presence, not dataflow. The discriminating proof is
     ARM 4: point the engine at a PERMUTED ladder and watch every rank permute
     with it. An engine carrying its own order passes every other arm in this
     file and fails only that one.
  2. FAIL-CLOSED. A missing or malformed ladder is a TYPED refusal, never a
     fallback order. A comparator that keeps answering without its content has
     silently become the author of the vocabulary it was supposed to read.
  3. OFF-LADDER IS TYPED AND ROUTED. An unruled horizon refuses with a message
     naming /review as the minting authority — the refusal is a routing
     instruction, not a vocabulary ceiling. Absence is NOT rank 0.

CURRENCY RIDER (the lesson the sibling enum suites carry): the ruled order is
asserted here against the RULING, not read back from the file, so that a silent
data edit is caught. That makes a STALE expectation in this file read as a FALSE
anomaly after a lawful /review amendment. When /review amends the ladder, this
expectation is amended in the same motion — the contract file leads, the suite
follows, and neither ships alone.

DOES NOT SATISFY (rider carried verbatim from the ruling): "H1 does NOT satisfy
H2 (receipt-intake refusal), H3 (remote-parity close predicate), or H4
(detached-reproduction twin); it types the ladder those consumers will read. No
intake boundary refuses anything as of this increment."

FIXTURE-GREEN. Every arm here is fixture-green: temp ladder files under
TemporaryDirectory plus read-only reads of the shipped contract. Nothing in this
suite exercises a live intake boundary, a receipt writer, a close instrument, or
a remote — there is nothing live to exercise, because H2/H3/H4 are unbuilt.

Run:  python3 -m pytest -q -p no:cacheprovider \\
          test_proof_horizon_ladder_tic769.py      (from cgg-runtime/scripts/)
  or: python3 -m unittest test_proof_horizon_ladder_tic769
"""
import contextlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

# --- Load the module under test by absolute path -----------------------------
# Mirrors the sibling-test convention in this directory (scripts/ is not an
# importable package and pytest runs with --import-mode=importlib).
_HERE = Path(os.path.abspath(__file__)).resolve().parent
_LIB = _HERE / "lib" / "proof_horizon.py"
_SPEC = importlib.util.spec_from_file_location("proof_horizon_under_test", _LIB)
ph = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ph)

_CONTRACTS_DIR = _HERE.parent / "contracts"
_SHIPPED = _CONTRACTS_DIR / "proof-horizon-ladder-v1.json"

# The RULED order, transcribed from the ruling (staged decomposition section 3,
# row H1) — deliberately NOT read back from the file under test.
RULED_ORDER = (
    "source_admitted",
    "pushed",
    "remote_readback",
    "detached_reproduced",
    "installed_verified",
    "deployed",
    "outcome_observed",
)

RIDER = ("H1 does NOT satisfy H2 (receipt-intake refusal), H3 (remote-parity "
         "close predicate), or H4 (detached-reproduction twin); it types the "
         "ladder those consumers will read. No intake boundary refuses anything "
         "as of this increment.")

# An off-ladder value that is a plausible coinage at a call site — exactly the
# shape the refusal exists to route to /review rather than admit quietly.
OFF_LADDER = "merged"


def ladder_file(path, order, schema_version=ph.SCHEMA_VERSION, ranks=None):
    """Write a ladder contract carrying `order`. `ranks` overrides the rank
    values for the malformed-shape arms."""
    entries = []
    for position, name in enumerate(order):
        rank = position if ranks is None else ranks[position]
        entries.append({"rank": rank, "horizon": name,
                        "earliest_lawful_observation": "fixture"})
    path.write_text(json.dumps({"schema_version": schema_version,
                                "ladder": entries}), encoding="utf-8")
    return path


class _TmpLadder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "proof-horizon-ladder-v1.json"
        self.addCleanup(self.tmp.cleanup)


# ===========================================================================
# ARM 1 — the shipped CONTENT: the ruled ladder, in the ruled order
# ===========================================================================

class TestArm1ShippedContract(unittest.TestCase):
    def test_the_contract_file_exists_where_the_engine_looks_for_it(self):
        self.assertTrue(_SHIPPED.is_file(), f"missing content file: {_SHIPPED}")
        self.assertEqual(ph.default_ladder_path(), _SHIPPED.resolve())

    def test_the_shipped_ladder_carries_exactly_the_ruled_order(self):
        """The ordering assert. Seven horizons, earliest-lawful-observation
        first, exactly as ruled — no extras, no drops, no re-sort."""
        self.assertEqual(ph.load_ladder()["order"], RULED_ORDER)

    def test_ranks_are_contiguous_from_zero_and_strictly_increasing(self):
        ladder = ph.load_ladder()
        self.assertEqual([ladder["ranks"][n] for n in RULED_ORDER],
                         list(range(len(RULED_ORDER))))

    def test_each_rung_declares_its_earliest_lawful_observation_instant(self):
        """The ladder orders INSTANTS, not workflow stages — every rung has to
        say what instant it names, or the axis is a label."""
        for rung in ph.load_ladder()["contract"]["ladder"]:
            self.assertTrue(rung.get("earliest_lawful_observation"),
                            f"{rung.get('horizon')!r} names no instant")

    def test_the_contract_declares_open_by_review_and_names_the_authority(self):
        contract = ph.load_ladder()["contract"]
        self.assertIn("OPEN-BY-/REVIEW", contract["accretion"])
        self.assertIn("NOT A CLOSURE", contract["accretion"].upper())
        self.assertIn("/review", contract["minting_authority"])

    def test_the_contract_forbids_a_fallback_order_in_the_engine(self):
        engine = ph.load_ladder()["contract"]["engine"]
        prohibition = engine["hardcoded_order_prohibition"].lower()
        self.assertIn("carries no ordering of its own", prohibition)
        self.assertIn("not as a fallback", prohibition)
        self.assertEqual(
            sorted(engine["typed_refusal_codes"]),
            ["ladder_file_malformed_json", "ladder_file_missing",
             "ladder_schema_invalid", "off_ladder_horizon"])

    def test_absence_is_not_rank_zero_in_the_ruled_content(self):
        self.assertIn("NOT rank 0", ph.load_ladder()["contract"]["absence"])

    def test_the_contract_declares_zero_consumers_at_this_increment(self):
        contract = ph.load_ladder()["contract"]
        self.assertEqual(contract["write_surfaces"], [])
        self.assertIn("NONE at tic 769", contract["consumers"])

    def test_the_rider_travels_verbatim_in_the_contract_and_the_engine(self):
        """A does-not-satisfy rider is only doing its job where a reader could
        mistake the artifact for satisfying the withheld thing — so it rides the
        contract's does_not_satisfy, the contract's brief, and the module
        docstring, verbatim in all three."""
        contract = ph.load_ladder()["contract"]
        self.assertEqual(contract["does_not_satisfy"], RIDER)
        self.assertIn(RIDER, contract["brief"])
        self.assertEqual(ph.DOES_NOT_SATISFY, RIDER)
        collapsed = " ".join(ph.__doc__.split())
        self.assertIn(" ".join(RIDER.split()), collapsed)


# ===========================================================================
# ARM 2 — the predicate: ordering and the over-claim case
# ===========================================================================

class TestArm2Predicate(unittest.TestCase):
    def test_horizon_rank_returns_the_ruled_rank(self):
        for expected, name in enumerate(RULED_ORDER):
            self.assertEqual(ph.horizon_rank(name), expected)

    def test_a_claim_at_its_own_horizon_is_within(self):
        for name in RULED_ORDER:
            self.assertTrue(ph.claim_within_horizon(name, name))

    def test_an_earlier_claim_on_a_later_artifact_is_within(self):
        self.assertTrue(ph.claim_within_horizon("source_admitted", "deployed"))
        self.assertTrue(ph.claim_within_horizon("pushed", "remote_readback"))

    def test_the_over_claim_case_is_reported_false(self):
        """The whole point of the axis: a push is emission, a readback is
        retrieval. An artifact whose observation stopped at `pushed` cannot
        truthfully carry a `remote_readback` claim.

        Each pair below is written CLAIM-first, ARTIFACT-second, and each names
        a scar this federation has paid for: a push read as retrieval; an
        installed-bytes parity read as an independent reproduction; a delivery
        read as an outcome. The direction matters — the mirrored pairs (an
        EARLIER claim on a LATER artifact) are lawful and are asserted True in
        the sibling test above."""
        self.assertFalse(ph.claim_within_horizon("remote_readback", "pushed"))
        self.assertFalse(
            ph.claim_within_horizon("installed_verified", "detached_reproduced"))
        self.assertFalse(ph.claim_within_horizon("outcome_observed", "deployed"))

    def test_the_full_matrix_agrees_with_the_ruled_order(self):
        for i, claim in enumerate(RULED_ORDER):
            for j, artifact in enumerate(RULED_ORDER):
                self.assertEqual(ph.claim_within_horizon(claim, artifact), i <= j,
                                 f"{claim} on {artifact}")

    def test_the_predicate_refuses_nothing_and_returns_a_bool(self):
        """H1 REPORTS the over-claim; it does not refuse it. The boundary that
        turns False into a typed refusal is H2, and H2 is unbuilt."""
        verdict = ph.claim_within_horizon("deployed", "source_admitted")
        self.assertIsInstance(verdict, bool)
        self.assertFalse(verdict)


# ===========================================================================
# ARM 3 — off-ladder values are TYPED refusals, never silent defaults
# ===========================================================================

class TestArm3OffLadderIsTyped(unittest.TestCase):
    def test_an_unruled_horizon_refuses_with_the_typed_code(self):
        with self.assertRaises(ph.OffLadderHorizon) as ctx:
            ph.horizon_rank(OFF_LADDER)
        self.assertEqual(ctx.exception.code, "off_ladder_horizon")

    def test_the_refusal_names_review_as_the_minting_authority(self):
        with self.assertRaises(ph.OffLadderHorizon) as ctx:
            ph.horizon_rank(OFF_LADDER)
        msg = str(ctx.exception)
        self.assertIn("MINTING AUTHORITY: /review", msg)
        self.assertIn("do not coin it at the call site", msg)
        self.assertIn("contracts/proof-horizon-ladder-v1.json", msg)
        for name in RULED_ORDER:
            self.assertIn(name, msg)

    def test_absence_is_refused_not_defaulted_to_rank_zero(self):
        """Absence asserts nothing. Defaulting it to the earliest rung would
        quietly certify every unlabelled claim as lawful at rank 0."""
        for value in (None, "", 0, False, ["pushed"]):
            with self.assertRaises(ph.OffLadderHorizon):
                ph.horizon_rank(value)

    def test_case_and_whitespace_variants_are_off_ladder(self):
        for value in ("Pushed", "PUSHED", " pushed", "pushed "):
            with self.assertRaises(ph.OffLadderHorizon):
                ph.horizon_rank(value)

    def test_either_argument_off_ladder_refuses_and_names_which(self):
        with self.assertRaises(ph.OffLadderHorizon) as ctx:
            ph.claim_within_horizon(OFF_LADDER, "pushed")
        self.assertIn("claim_horizon=", str(ctx.exception))
        with self.assertRaises(ph.OffLadderHorizon) as ctx:
            ph.claim_within_horizon("pushed", OFF_LADDER)
        self.assertIn("artifact_horizon=", str(ctx.exception))

    def test_off_ladder_refusals_are_proof_horizon_refusals(self):
        self.assertTrue(issubclass(ph.OffLadderHorizon, ph.ProofHorizonRefusal))
        self.assertTrue(issubclass(ph.LadderUnavailable, ph.ProofHorizonRefusal))


# ===========================================================================
# ARM 4 — THE NEGATIVE CONTROL: does the engine actually READ the content?
#
# This is the load-bearing arm. Every other arm in this file passes just as
# green against an engine that carries a hardcoded order, because the hardcoded
# order and the shipped file agree. Only a PERMUTED ladder can tell them apart.
# ===========================================================================

class TestArm4RevertedCureControl(_TmpLadder):
    """Revert the cure and watch the exact predicted breakage.

    THE CURE: `horizon_rank` reads its ordering from the ladder FILE at call
    time. THE REVERTED CURE: `_read_ladder_file` is monkeypatched to return a
    HARDCODED ladder regardless of the path — the shape the engine would have if
    engine-content separation had never been built.

    PREDICTED BREAKAGE when the cure is reverted, named in advance:
      `horizon_rank("source_admitted", path=<permuted file>)` returns 0 (the
      hardcoded rank) instead of 6 (the file's rank), so the cure's own
      assertion fails with AssertionError "0 != 6".
    """

    PERMUTED = tuple(reversed(RULED_ORDER))

    @contextlib.contextmanager
    def _cure_reverted(self, hardcoded_order=RULED_ORDER):
        saved = ph._read_ladder_file

        def _hardcoded(path):
            return {"schema_version": ph.SCHEMA_VERSION,
                    "ladder": [{"rank": i, "horizon": n}
                               for i, n in enumerate(hardcoded_order)]}

        ph._read_ladder_file = _hardcoded
        try:
            yield
        finally:
            ph._read_ladder_file = saved

    def test_cure_live_the_ranks_follow_the_file(self):
        """A permuted ladder permutes every rank. This is the positive control
        for Arm 4 and the only assert in this file that a hardcoded engine
        cannot pass."""
        ladder_file(self.path, self.PERMUTED)
        self.assertEqual(ph.load_ladder(path=self.path)["order"], self.PERMUTED)
        self.assertEqual(ph.horizon_rank("source_admitted", path=self.path), 6)
        self.assertEqual(ph.horizon_rank("outcome_observed", path=self.path), 0)
        # The predicate inverts with the content, because the content IS the order.
        self.assertTrue(
            ph.claim_within_horizon("outcome_observed", "source_admitted",
                                    path=self.path))
        self.assertFalse(
            ph.claim_within_horizon("source_admitted", "outcome_observed",
                                    path=self.path))

    def test_cure_reverted_the_file_is_ignored_and_the_assert_fails_by_name(self):
        """The discriminating half: with the cure reverted, the SAME permuted
        file yields the hardcoded ranks, and the cure's assertion fails with the
        predicted message. Discriminated by exception NAME and MESSAGE."""
        ladder_file(self.path, self.PERMUTED)
        with self._cure_reverted():
            self.assertEqual(ph.horizon_rank("source_admitted", path=self.path), 0)
            with self.assertRaises(AssertionError) as ctx:
                self.assertEqual(
                    ph.horizon_rank("source_admitted", path=self.path), 6,
                    "PREDICTED BREAKAGE: the engine no longer reads the ladder file")
            message = str(ctx.exception)
            self.assertIn("0 != 6", message)
            self.assertIn("PREDICTED BREAKAGE", message)

    def test_cure_reverted_survives_content_loss_which_is_the_defect_itself(self):
        """Second face of the control: fail-closed is what content-dependence
        FEELS like. With the cure live, a deleted ladder refuses. With the cure
        reverted, the engine answers cheerfully with no content at all — that
        silent survival is exactly the defect."""
        missing = self.dir / "no-such-ladder.json"
        with self.assertRaises(ph.LadderUnavailable) as ctx:
            ph.horizon_rank("pushed", path=missing)
        self.assertEqual(ctx.exception.code, "ladder_file_missing")
        with self._cure_reverted():
            self.assertEqual(ph.horizon_rank("pushed", path=missing), 1)

    def test_the_control_does_not_leak(self):
        """If the revert leaked, every arm after it would be testing a hardcoded
        engine and this suite would be green for the wrong reason."""
        ladder_file(self.path, self.PERMUTED)
        with self._cure_reverted():
            pass
        self.assertEqual(ph.horizon_rank("source_admitted", path=self.path), 6)
        self.assertEqual(ph.load_ladder()["order"], RULED_ORDER)


# ===========================================================================
# ARM 5 — FAIL-CLOSED: missing / malformed content is a typed refusal
# ===========================================================================

class TestArm5FailClosed(_TmpLadder):
    def _refusal(self, callable_, *args, **kwargs):
        with self.assertRaises(ph.LadderUnavailable) as ctx:
            callable_(*args, **kwargs)
        return ctx.exception

    def test_missing_file_is_typed_and_offers_no_ordering(self):
        missing = self.dir / "absent.json"
        exc = self._refusal(ph.load_ladder, path=missing)
        self.assertEqual(exc.code, "ladder_file_missing")
        self.assertIn("FAIL-CLOSED", str(exc))
        self.assertIn("no fallback ordering", str(exc))
        # Every entry point fails closed, not just the loader.
        self.assertEqual(
            self._refusal(ph.horizon_rank, "pushed", path=missing).code,
            "ladder_file_missing")
        self.assertEqual(
            self._refusal(ph.claim_within_horizon, "pushed", "deployed",
                          path=missing).code,
            "ladder_file_missing")

    def test_a_directory_in_the_ladder_slot_is_typed_missing_not_a_crash(self):
        d = self.dir / "not-a-file"
        d.mkdir()
        self.assertEqual(self._refusal(ph.load_ladder, path=d).code,
                         "ladder_file_missing")

    def test_malformed_json_is_typed(self):
        self.path.write_text("{ this is not json", encoding="utf-8")
        exc = self._refusal(ph.load_ladder, path=self.path)
        self.assertEqual(exc.code, "ladder_file_malformed_json")

    def test_empty_file_is_typed(self):
        self.path.write_text("", encoding="utf-8")
        self.assertEqual(self._refusal(ph.load_ladder, path=self.path).code,
                         "ladder_file_malformed_json")

    def test_a_json_array_at_the_top_level_is_schema_invalid(self):
        self.path.write_text("[]", encoding="utf-8")
        self.assertEqual(self._refusal(ph.load_ladder, path=self.path).code,
                         "ladder_schema_invalid")

    def test_a_foreign_schema_version_is_refused_not_guessed(self):
        ladder_file(self.path, RULED_ORDER, schema_version="some-other-enum-v1")
        exc = self._refusal(ph.load_ladder, path=self.path)
        self.assertEqual(exc.code, "ladder_schema_invalid")
        self.assertIn("schema_version", str(exc))

    def test_an_empty_ladder_is_refused(self):
        ladder_file(self.path, ())
        self.assertEqual(self._refusal(ph.load_ladder, path=self.path).code,
                         "ladder_schema_invalid")

    def test_a_missing_ladder_key_is_refused(self):
        self.path.write_text(json.dumps({"schema_version": ph.SCHEMA_VERSION}),
                             encoding="utf-8")
        self.assertEqual(self._refusal(ph.load_ladder, path=self.path).code,
                         "ladder_schema_invalid")

    def test_a_rung_missing_its_horizon_name_is_refused(self):
        self.path.write_text(json.dumps(
            {"schema_version": ph.SCHEMA_VERSION,
             "ladder": [{"rank": 0}]}), encoding="utf-8")
        self.assertEqual(self._refusal(ph.load_ladder, path=self.path).code,
                         "ladder_schema_invalid")

    def test_a_non_integer_rank_is_refused(self):
        ladder_file(self.path, ("a", "b"), ranks=[0, "1"])
        self.assertEqual(self._refusal(ph.load_ladder, path=self.path).code,
                         "ladder_schema_invalid")

    def test_a_boolean_rank_is_refused_despite_being_an_int_subclass(self):
        ladder_file(self.path, ("a", "b"), ranks=[False, True])
        self.assertEqual(self._refusal(ph.load_ladder, path=self.path).code,
                         "ladder_schema_invalid")

    def test_a_rank_gap_is_refused_because_it_silently_changes_the_order(self):
        ladder_file(self.path, ("a", "b", "c"), ranks=[0, 2, 3])
        exc = self._refusal(ph.load_ladder, path=self.path)
        self.assertEqual(exc.code, "ladder_schema_invalid")
        self.assertIn("contiguous", str(exc))

    def test_ranks_disagreeing_with_list_order_are_refused(self):
        ladder_file(self.path, ("a", "b"), ranks=[1, 0])
        self.assertEqual(self._refusal(ph.load_ladder, path=self.path).code,
                         "ladder_schema_invalid")

    def test_a_duplicate_horizon_name_is_refused(self):
        ladder_file(self.path, ("pushed", "pushed"))
        exc = self._refusal(ph.load_ladder, path=self.path)
        self.assertEqual(exc.code, "ladder_schema_invalid")
        self.assertIn("more than once", str(exc))

    def test_a_lawful_custom_ladder_still_loads(self):
        """Fail-closed must not mean fail-always: the amendment path stays open,
        which is what makes the refusals above meaningful."""
        ladder_file(self.path, ("a", "b", "c"))
        self.assertEqual(ph.load_ladder(path=self.path)["order"], ("a", "b", "c"))
        self.assertEqual(ph.horizon_rank("c", path=self.path), 2)


# ===========================================================================
# NO-REGRESSION TRIPWIRE — adding a file to contracts/ disturbs nothing
# ===========================================================================

class TestNoRegressionOnTheContractsDirectory(unittest.TestCase):
    """The only shared surface this increment touches is the contracts/
    directory, and it touches it by ADDING a file. The hazard would be a
    consumer that globs contracts/*.json and now sees a shape it does not
    expect; the sibling enum guard binds contracts by explicit FILENAME, and
    this arm holds that boundary."""

    def test_every_contract_in_the_directory_still_parses(self):
        found = sorted(p.name for p in _CONTRACTS_DIR.glob("*.json"))
        self.assertIn("proof-horizon-ladder-v1.json", found)
        for name in found:
            with open(_CONTRACTS_DIR / name, encoding="utf-8") as fh:
                json.load(fh)

    def test_the_enum_guard_binding_is_unchanged_by_this_increment(self):
        spec = importlib.util.spec_from_file_location(
            "qlw_no_regression_tic769",
            str(_HERE / "queue-lifecycle-writeback.py"))
        qlw = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(qlw)
        self.assertEqual(set(qlw.ENUM_GUARDED_FIELDS),
                         {"pending_class", "landing_kind"})
        self.assertNotIn("proof_horizon", qlw.ENUM_GUARDED_FIELDS)

    def test_the_sibling_tier_contract_engine_still_loads(self):
        spec = importlib.util.spec_from_file_location(
            "confidence_tier_no_regression_tic769",
            str(_HERE / "lib" / "confidence_tier.py"))
        ct = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ct)
        self.assertTrue(ct.TIER_ENUM)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
