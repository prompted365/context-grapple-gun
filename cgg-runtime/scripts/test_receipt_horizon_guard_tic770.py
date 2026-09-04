"""test_receipt_horizon_guard_tic770 — H2 of THE HORIZON QUIVER, the receipt-intake
horizon check.

RULED: /review 769 signed the HORIZON QUIVER build set H1-H4 staged-lock; the
Architect's word at tic 769 ruled "Dispatch H2 || H3 || H4 at 770". Staged
decomposition row H2 (staging/horizon-quiver-admission-and-dag-tic768.md section 3,
as adjudicated 12,923 B / sha256-16 ab69feb78ed4600d):

    "Receipt-intake horizon check: a receipt claim typed ABOVE its artifact's lawful
     horizon REFUSES with a typed error (same physics locus class as the off-enum +
     undeclared-field guards) | H1 | the receipt-intake boundary + tests (disjoint
     from H3/H4) | signed wave"

Gate evidence: H1's cable receipt 91cf9b14ba17b8e9 ("H2 || H3 || H4 tension only
after H1's cable receipt lands").

EVIDENCE CLASS: FIXTURE-GREEN. Every arm below runs against temporary ladders,
temporary sandboxes, and in-process fixtures. NOTHING here is live-green,
trainer-green, wave-green, or install-green. Arm 4 exercises the REAL hook module
with its HERE/MANIFEST rebound to a TemporaryDirectory — that is a fixture of the
live boundary, not a live fire. No wave-ledger in the federation is written by this
suite.

DOES NOT SATISFY (rider carried verbatim from the ruling, via H1's receipt): "H1
does NOT satisfy H2 (receipt-intake refusal), H3 (remote-parity close predicate),
or H4 (detached-reproduction twin); it types the ladder those consumers will read.
No intake boundary refuses anything as of this increment."

Run: python3 -m pytest -q -p no:cacheprovider scripts/test_receipt_horizon_guard_tic770.py
"""

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # cgg-runtime/scripts
_LIB = _HERE / "lib"

RIDER = ("H1 does NOT satisfy H2 (receipt-intake refusal), H3 (remote-parity "
         "close predicate), or H4 (detached-reproduction twin); it types the "
         "ladder those consumers will read. No intake boundary refuses anything "
         "as of this increment.")


def _zone_root() -> Path:
    for p in [_HERE, *_HERE.parents]:
        if (p / ".ticzone").is_file():
            return p
    raise AssertionError("no .ticzone root found above the test file")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import proof_horizon                     # noqa: E402  (H1's engine)
import receipt_horizon_guard as rhg      # noqa: E402  (H2's guard, under test)

ZONE = _zone_root()
HOOK_PATH = ZONE / "audit-logs" / "governance" / "harpoon-office" / "hoist-receipt-hook.py"
SHIPPED_LADDER = proof_horizon.default_ladder_path()
ORDER = proof_horizon.load_ladder()["order"]      # read, never hardcoded


def _write_ladder(path: Path, order) -> Path:
    """Write a syntactically valid ladder carrying `order`. Used to prove the guard's
    verdicts follow the CONTENT and not any ordering baked into H2."""
    path.write_text(json.dumps({
        "schema_version": proof_horizon.SCHEMA_VERSION,
        "ladder": [{"rank": i, "horizon": h} for i, h in enumerate(order)],
    }), encoding="utf-8")
    return path


def _receipt(claim=None, attested=None, block="default", **extra):
    """A receipt-shaped artifact. block=None omits the proof_horizon key entirely."""
    art = {"receipt_id": "fixture", "tic": 495, "run_id": "test"}
    art.update(extra)
    if block == "default":
        b = {}
        if claim is not None:
            b[rhg.CLAIM_KEY] = claim
        if attested is not None:
            b[rhg.ARTIFACT_KEY] = attested
        art[rhg.BLOCK_KEY] = b
    elif block is not None:
        art[rhg.BLOCK_KEY] = block
    return art


# ---------------------------------------------------------------------------
# ARM 1 — the predicate: absence, lawful, and THE ruled refusal
# ---------------------------------------------------------------------------

class TestArm1Predicate(unittest.TestCase):

    def test_no_block_at_all_is_unguarded_not_rank_zero(self):
        """H1 contract `absence`: a claim with NO horizon asserted is lawful and is
        NOT rank 0. The guard must not invent a default rung."""
        v = rhg.classify_receipt_horizon(_receipt(block=None))
        self.assertEqual(v["verdict"], "unguarded")
        self.assertIsNone(v["code"])
        self.assertIsNone(v["claim"])

    def test_block_present_but_no_claim_is_unguarded(self):
        v = rhg.classify_receipt_horizon(_receipt(attested="pushed"))
        self.assertEqual(v["verdict"], "unguarded")
        self.assertIsNone(v["code"])

    def test_equal_horizons_are_lawful(self):
        for h in ORDER:
            with self.subTest(horizon=h):
                v = rhg.classify_receipt_horizon(_receipt(claim=h, attested=h))
                self.assertEqual(v["verdict"], "lawful", v)

    def test_claim_below_attested_is_lawful(self):
        v = rhg.classify_receipt_horizon(
            _receipt(claim=ORDER[0], attested=ORDER[-1]))
        self.assertEqual(v["verdict"], "lawful", v)

    def test_THE_ruled_refusal_claim_above_attested(self):
        """The ruled target, in its canonical instance: a receipt whose bytes only
        exist locally (source_admitted) claiming the delivery surface serves them."""
        v = rhg.classify_receipt_horizon(
            _receipt(claim="deployed", attested="source_admitted"))
        self.assertEqual(v["verdict"], "refused")
        self.assertEqual(v["code"], "receipt_horizon_over_claim")
        self.assertEqual(v["claim"], "deployed")
        self.assertEqual(v["attested"], "source_admitted")

    def test_full_matrix_every_ordered_pair(self):
        """All 7x7 ordered pairs: refused iff rank(claim) > rank(attested)."""
        refused = lawful = 0
        for i, claim in enumerate(ORDER):
            for j, attested in enumerate(ORDER):
                v = rhg.classify_receipt_horizon(
                    _receipt(claim=claim, attested=attested))
                if i > j:
                    self.assertEqual(v["verdict"], "refused", (claim, attested))
                    self.assertEqual(v["code"], "receipt_horizon_over_claim")
                    refused += 1
                else:
                    self.assertEqual(v["verdict"], "lawful", (claim, attested))
                    lawful += 1
        n = len(ORDER)
        self.assertEqual(refused, n * (n - 1) // 2)
        self.assertEqual(lawful, n * (n + 1) // 2)

    def test_the_scar_this_guard_answers(self):
        """The t767 over-claimed-verify scar and its siblings, named in the ruling's
        ENA facet — each is an over-claim by exactly one rung or more."""
        for claim, attested in (("remote_readback", "pushed"),        # push read as retrieval
                                ("installed_verified", "pushed"),     # emission read as parity
                                ("outcome_observed", "deployed"),     # delivery read as effect
                                ("detached_reproduced", "remote_readback")):
            with self.subTest(claim=claim, attested=attested):
                v = rhg.classify_receipt_horizon(
                    _receipt(claim=claim, attested=attested))
                self.assertEqual(v["verdict"], "refused")
                self.assertEqual(v["code"], "receipt_horizon_over_claim")


# ---------------------------------------------------------------------------
# ARM 2 — the typed refusal codes (the guard-family reason-dict shape)
# ---------------------------------------------------------------------------

class TestArm2TypedRefusals(unittest.TestCase):

    def test_claim_with_no_attestation_is_refused_not_admitted(self):
        v = rhg.classify_receipt_horizon(_receipt(claim="deployed"))
        self.assertEqual(v["verdict"], "refused")
        self.assertEqual(v["code"], "receipt_horizon_unattested")

    def test_off_ladder_claim_routes_to_review(self):
        v = rhg.classify_receipt_horizon(
            _receipt(claim="shipped_probably", attested="source_admitted"))
        self.assertEqual(v["code"], "receipt_horizon_off_ladder")
        self.assertIn("/review", v["reason"]["message"])

    def test_off_ladder_attested_is_also_refused(self):
        v = rhg.classify_receipt_horizon(
            _receipt(claim="source_admitted", attested="vibes"))
        self.assertEqual(v["code"], "receipt_horizon_off_ladder")

    def test_a_non_string_horizon_is_refused_never_coerced(self):
        for bad in (0, True, ["pushed"], {"h": "pushed"}):
            with self.subTest(bad=bad):
                v = rhg.classify_receipt_horizon(
                    _receipt(claim=bad, attested="pushed"))
                self.assertEqual(v["verdict"], "refused", bad)
                self.assertEqual(v["code"], "receipt_horizon_off_ladder")

    def test_a_malformed_block_is_refused_not_ignored(self):
        for bad in ("source_admitted", ["source_admitted"], 7):
            with self.subTest(bad=bad):
                v = rhg.classify_receipt_horizon(_receipt(block=bad))
                self.assertEqual(v["code"], "receipt_horizon_malformed_block")

    def test_ladder_unavailable_refuses_an_asserted_claim(self):
        """FAIL-CLOSED, scoped: a claim that cannot be judged is refused."""
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "not-there.json"
            v = rhg.classify_receipt_horizon(
                _receipt(claim="deployed", attested="source_admitted"),
                ladder_path=missing)
            self.assertEqual(v["verdict"], "refused")
            self.assertEqual(v["code"], "receipt_horizon_ladder_unavailable")

    def test_ladder_unavailable_does_NOT_refuse_a_receipt_asserting_nothing(self):
        """The scoping half — and the reason this guard adds zero coupling for the
        corpus that never opted in. An unguarded receipt never consults the ladder."""
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "not-there.json"
            v = rhg.classify_receipt_horizon(_receipt(block=None),
                                             ladder_path=missing)
            self.assertEqual(v["verdict"], "unguarded")

    def test_every_refusal_carries_the_family_reason_shape(self):
        for art in (_receipt(claim="deployed"),
                    _receipt(claim="nope", attested="pushed"),
                    _receipt(block=7),
                    _receipt(claim="deployed", attested="source_admitted")):
            v = rhg.classify_receipt_horizon(art)
            self.assertEqual(v["verdict"], "refused", art)
            r = v["reason"]
            self.assertEqual(set(r), {"code", "fields", "value", "message"})
            self.assertEqual(r["fields"], ["proof_horizon"])
            self.assertEqual(r["code"], v["code"])
            self.assertTrue(r["message"].strip())


# ---------------------------------------------------------------------------
# ARM 3 — engine-content separation is INHERITED, not re-implemented
# ---------------------------------------------------------------------------

class TestArm3ContentSeparation(unittest.TestCase):
    """H2 must carry no ordering of its own. Point it at a PERMUTED ladder and the
    verdicts must permute with the FILE — the H1 discriminator, re-run one layer up."""

    def test_verdicts_follow_the_file_not_the_code(self):
        with tempfile.TemporaryDirectory() as td:
            permuted = _write_ladder(Path(td) / "ladder.json", tuple(reversed(ORDER)))
            # Under the SHIPPED ladder this is the canonical over-claim...
            self.assertEqual(
                rhg.classify_receipt_horizon(
                    _receipt(claim="deployed", attested="source_admitted"))["verdict"],
                "refused")
            # ...and under the REVERSED ladder the very same receipt is lawful.
            self.assertEqual(
                rhg.classify_receipt_horizon(
                    _receipt(claim="deployed", attested="source_admitted"),
                    ladder_path=permuted)["verdict"],
                "lawful")

    def test_a_custom_lawful_ladder_is_honored(self):
        with tempfile.TemporaryDirectory() as td:
            custom = _write_ladder(Path(td) / "ladder.json", ("alpha", "beta", "gamma"))
            self.assertEqual(rhg.classify_receipt_horizon(
                _receipt(claim="gamma", attested="alpha"), ladder_path=custom)["code"],
                "receipt_horizon_over_claim")
            self.assertEqual(rhg.classify_receipt_horizon(
                _receipt(claim="alpha", attested="gamma"), ladder_path=custom)["verdict"],
                "lawful")
            # a SHIPPED horizon is off-ladder against this custom content
            self.assertEqual(rhg.classify_receipt_horizon(
                _receipt(claim="deployed", attested="alpha"), ladder_path=custom)["code"],
                "receipt_horizon_off_ladder")

    def test_h2_source_carries_no_hardcoded_ladder_vocabulary(self):
        """Structural: no ruled horizon name may appear as a literal in the guard."""
        src = Path(rhg.__file__).read_text(encoding="utf-8")
        body = src.split('"""', 2)[2]          # exclude the module docstring
        for horizon in ORDER:
            self.assertNotIn(f'"{horizon}"', body,
                             f"{horizon!r} is hardcoded in the guard body")
            self.assertNotIn(f"'{horizon}'", body,
                             f"{horizon!r} is hardcoded in the guard body")


# ---------------------------------------------------------------------------
# ARM 4 — THE INTAKE BOUNDARY: the real hook, sandboxed
# ---------------------------------------------------------------------------

class _Boundary:
    """Sandbox harness for the REAL hoist-receipt-hook module, mirroring the
    conventions of audit-logs/governance/harpoon-office/hoist-wave-engine-selftest.py
    (HERE/MANIFEST rebound to a TemporaryDirectory; probe_selfcheck payloads so the
    step-0 capture rows this fires are self-marked and never read as runtime evidence)."""

    CABLE = "S1_corpus_harvest"
    OFFICE = "ent_archivist"
    TIC = 495
    PAYLOAD = {"session_id": "h2-selftest-sid", "hook_event_name": "SubagentStop",
               "agent_id": "a0000000000000000", "agent_type": "archivist",
               "probe_selfcheck": True}

    def __init__(self, td, artifact):
        self.sb = Path(td)
        office_dir = HOOK_PATH.parent
        self.hook = _load("hoist_receipt_hook_h2", HOOK_PATH)
        manifest = json.loads((office_dir / "hoist-wave-engine-manifest.json").read_text())
        surface = json.loads((office_dir / "systems-layers-hoist-covenant-surface.json").read_text())
        (self.sb / "systems-layers-hoist-covenant-surface.json").write_text(json.dumps(surface))
        (self.sb / "hoist-wave-engine-manifest.json").write_text(json.dumps(dict(
            manifest, ratified=True, wave_ledger="hoist-wave-ledger.jsonl",
            covenant_surface="systems-layers-hoist-covenant-surface.json")))
        (self.sb / "hoist-wave-ledger.jsonl").write_text(json.dumps({
            "tic": self.TIC, "mode": "fire", "wave": 0, "cable": self.CABLE,
            "office": self.OFFICE, "event": "dispatched", "run_id": "test"}) + "\n")
        (self.sb / "cable-receipts").mkdir(exist_ok=True)
        (self.sb / f"cable-receipts/{self.CABLE}-{self.OFFICE}-tic{self.TIC}.json"
         ).write_text(json.dumps(artifact))
        self.hook.HERE = self.sb
        self.hook.MANIFEST = self.sb / "hoist-wave-engine-manifest.json"

    def fire(self):
        old_in, old_err = sys.stdin, sys.stderr
        sys.stdin, sys.stderr = io.StringIO(json.dumps(self.PAYLOAD)), io.StringIO()
        try:
            rc = self.hook.main()
            return rc, sys.stderr.getvalue()
        finally:
            sys.stdin, sys.stderr = old_in, old_err

    def receipt_rows(self):
        return [json.loads(l) for l in
                (self.sb / "hoist-wave-ledger.jsonl").read_text().splitlines()
                if l.strip() and json.loads(l).get("event") == "receipt"]


class TestArm4IntakeBoundary(unittest.TestCase):

    def test_an_over_claiming_receipt_is_REFUSED_admission(self):
        """THE increment, at its boundary: the receipt exists, belongs to this close,
        and passes every pre-existing LOCK-5 check — and is still refused, because it
        claims a horizon its own evidence does not reach."""
        art = _receipt(claim="installed_verified", attested="source_admitted")
        with tempfile.TemporaryDirectory(prefix="h2-overclaim-") as td:
            b = _Boundary(td, art)
            rc, err = b.fire()
            self.assertEqual(rc, 0, "fail-soft contract: never blocks a stop")
            self.assertEqual(b.receipt_rows(), [], "no receipt row may be written")
            self.assertIn("RECEIPT-HORIZON REFUSAL", err)
            self.assertIn("receipt_horizon_over_claim", err)

    def test_a_lawful_receipt_is_admitted_and_STAMPED(self):
        art = _receipt(claim="source_admitted", attested="pushed")
        with tempfile.TemporaryDirectory(prefix="h2-lawful-") as td:
            b = _Boundary(td, art)
            rc, _ = b.fire()
            rows = b.receipt_rows()
            self.assertEqual(rc, 0)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["proof_horizon"]["claim_horizon"], "source_admitted")
            self.assertEqual(rows[0]["proof_horizon"]["artifact_lawful_horizon"], "pushed")

    def test_an_unguarded_receipt_admits_EXACTLY_as_before(self):
        """The no-regression shape at the boundary: today's whole corpus asserts no
        horizon, so today's whole corpus must be untouched — row written, and NO
        proof_horizon key invented on it (absence stays absence on the ledger too)."""
        with tempfile.TemporaryDirectory(prefix="h2-unguarded-") as td:
            b = _Boundary(td, _receipt(block=None))
            rc, _ = b.fire()
            rows = b.receipt_rows()
            self.assertEqual(rc, 0)
            self.assertEqual(len(rows), 1)
            self.assertNotIn("proof_horizon", rows[0])

    def test_an_unattested_claim_is_refused_at_the_boundary(self):
        with tempfile.TemporaryDirectory(prefix="h2-unattested-") as td:
            b = _Boundary(td, _receipt(claim="deployed"))
            rc, err = b.fire()
            self.assertEqual(rc, 0)
            self.assertEqual(b.receipt_rows(), [])
            self.assertIn("receipt_horizon_unattested", err)

    def test_an_off_ladder_claim_is_refused_at_the_boundary(self):
        with tempfile.TemporaryDirectory(prefix="h2-offladder-") as td:
            b = _Boundary(td, _receipt(claim="totally_shipped", attested="pushed"))
            rc, err = b.fire()
            self.assertEqual(rc, 0)
            self.assertEqual(b.receipt_rows(), [])
            self.assertIn("receipt_horizon_off_ladder", err)

    def test_the_pre_existing_LOCK5_refusals_still_fire_first(self):
        """Disjointness from what was already there: a run_id mismatch must still be
        refused by LOCK-5, not by H2 — H2 did not displace the checks above it."""
        art = _receipt(claim="source_admitted", attested="source_admitted",
                       run_id="someone-else")
        with tempfile.TemporaryDirectory(prefix="h2-lock5-") as td:
            b = _Boundary(td, art)
            rc, err = b.fire()
            self.assertEqual(rc, 0)
            self.assertEqual(b.receipt_rows(), [])
            self.assertIn("mismatching the dispatched row", err)
            self.assertNotIn("RECEIPT-HORIZON REFUSAL", err)


# ---------------------------------------------------------------------------
# ARM 5 — THE REVERTED-CURE CONTROL
# ---------------------------------------------------------------------------

class TestArm5RevertedCureControl(unittest.TestCase):
    """The control that makes this suite discriminating rather than decorative.

    THE CURE: the intake boundary consults the guard and refuses an over-claim.
    THE REVERT: the boundary's verdict function is neutered to always return
    "unguarded" — the pre-H2 state, where a receipt could claim anything.
    PREDICTED BREAKAGE: the over-claiming receipt is ADMITTED (a receipt row
    appears) and the typed refusal vanishes from stderr.
    """

    def test_cure_live_the_over_claim_is_refused(self):
        art = _receipt(claim="outcome_observed", attested="source_admitted")
        with tempfile.TemporaryDirectory(prefix="h2-cure-live-") as td:
            b = _Boundary(td, art)
            b.fire()
            self.assertEqual(b.receipt_rows(), [],
                             "PREDICTED BREAKAGE marker: with the cure LIVE the "
                             "over-claiming receipt must be refused admission")

    def test_cure_reverted_the_over_claim_is_admitted(self):
        art = _receipt(claim="outcome_observed", attested="source_admitted")
        with tempfile.TemporaryDirectory(prefix="h2-cure-reverted-") as td:
            b = _Boundary(td, art)
            b.hook._horizon_verdict = lambda artifact: {
                "verdict": "unguarded", "code": None, "claim": None,
                "attested": None, "reason": None}
            rc, err = b.fire()
            rows = b.receipt_rows()
            self.assertEqual(rc, 0)
            self.assertEqual(len(rows), 1,
                             "with the cure REVERTED the over-claim must sail through "
                             "— if it does not, this control proves nothing")
            self.assertNotIn("RECEIPT-HORIZON REFUSAL", err)

    def test_the_control_does_not_leak(self):
        """A freshly loaded boundary must be cured again — the revert above must not
        persist into any sibling arm."""
        art = _receipt(claim="outcome_observed", attested="source_admitted")
        with tempfile.TemporaryDirectory(prefix="h2-noleak-") as td:
            b = _Boundary(td, art)
            b.fire()
            self.assertEqual(len(b.receipt_rows()), 0)


# ---------------------------------------------------------------------------
# ARM 6 — the rider travels verbatim
# ---------------------------------------------------------------------------

class TestArm6Riders(unittest.TestCase):

    def test_the_h1_rider_is_carried_verbatim_in_the_guard(self):
        self.assertEqual(rhg.DOES_NOT_SATISFY, RIDER)
        self.assertIn(RIDER, " ".join(
            Path(rhg.__file__).read_text(encoding="utf-8").split()).replace("  ", " "))

    def test_h2_declares_what_IT_does_not_satisfy(self):
        for phrase in ("does NOT independently measure", "H3", "H4"):
            self.assertIn(phrase, rhg.H2_DOES_NOT_SATISFY)

    def test_the_boundary_declares_the_refusal_is_admission_refusal_not_exit_code(self):
        """The honest bound must live in the hook's own text, not only in a receipt."""
        src = HOOK_PATH.read_text(encoding="utf-8")
        self.assertIn("REFUSES ADMISSION", src)
        self.assertIn("FAIL-SOFT", src)

    def test_h1_artifacts_are_untouched_by_h2(self):
        """H2 is a CONSUMER. It must not have edited H1's engine or content."""
        contract = json.loads(SHIPPED_LADDER.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema_version"], "proof-horizon-ladder-v1")
        self.assertEqual(contract["does_not_satisfy"], RIDER)
        self.assertEqual(proof_horizon.DOES_NOT_SATISFY, RIDER)


if __name__ == "__main__":
    unittest.main(verbosity=2)
