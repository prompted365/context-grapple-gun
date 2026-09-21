#!/usr/bin/env python3
"""test_cogpr_ingest_maturity_alignment.py — maturity field-name alignment fixtures.

Fix-site: bk-cpr-maturity-field-name-mismatch (surfaced by the cpr-stepper
tic-693 pass, filed at /review 693 close, struck tic 694). The defect: every
pending queue row carried `maturity_window_tics: 3` and NO `maturity_tics`,
while the extracted-gate readers (lib/cpr_steppable.py, ripple-assessor.py,
mandate-write.py _derive_review_due_tic) read `maturity_tics` default-3 — so
every gate decision to date was correct by VALUE-COINCIDENCE, not field
agreement. Worse than single-reader drift: the compile layer
(audit-logs/cprs/queue_state_compile.py _resolve_target_tic) parks extracted
rows on birth + maturity_window_tics (birth-anchored per the t665/t691 fence),
so a divergent-value row splits the two reader FAMILIES — the bench packet
parks it to birth+window while the stepper/mandate clock it at birth+3.

The cure (writer-side, per the filing's "align writer field naming"): ONE
resolved maturity clock feeds BOTH fields at mint. Gate readers need no
change — they already honor a per-row `maturity_tics` override; the field
just never existed. SCOPE FENCE: historical rows are not retro-edited
(append-only; the honest "maturity_tics ABSENT — gate default" consumed_fields
line stays true for them); the legacy divergent shape is DOCUMENTED here, not
repaired.
"""

import importlib.util
import os
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ci = _load("cogpr_ingest", _HERE / "cogpr-ingest.py")
mw = _load("mandate_write", _HERE / "mandate-write.py")
sys.path.insert(0, str(_HERE / "lib"))
import cpr_steppable  # noqa: E402

# The compile layer lives canonical-side (tracked-external-scripts pattern).
# CGG_QUEUE_STATE_COMPILE is the declared seam -- already the supply contract
# of the six sibling projection suites cured at /review 813 -- and it is read
# FIRST so a runner outside any walkable tree can still supply the compiler;
# otherwise walk up to the zone root the same way the runtime scripts do.
_QSC = None
_seam = os.environ.get("CGG_QUEUE_STATE_COMPILE", "")
if _seam and Path(_seam).is_file():
    _QSC = _load("queue_state_compile", Path(_seam))
else:
    for _p in _HERE.parents:
        _cand = _p / "audit-logs" / "cprs" / "queue_state_compile.py"
        if _cand.exists():
            _QSC = _load("queue_state_compile", _cand)
            break

# THE OPT-OUT (F-814-A1, ruled /review 814 Q3). When NEITHER the seam above
# NOR a walkable root resolves the compile layer, the proof that needs it now
# FAILS: a green count that has lost an arm is the silent-degrade class. The
# name below is the explicit opt-out that restores the skip, and it announces
# ITSELF so a skipped proof is never silent -- a warning (visible under bare
# -q with NO reporting flag), the skip reason (visible under -rs), and stdout
# (visible under -s) -- each MEASURED on this runner, not argued. It is the
# one name the six sibling suites already carry, not a second convention.
# EMPTY IS NOT SET: the value is stripped before it is believed, so an empty
# override falls back to the hard failure, never to the silent skip.
#
# DOES-NOT-SATISFY RIDER (travels verbatim, on ONE unbroken line so a byte-exact grep resolves it):
# this increment does NOT convert any skip outside the one named file, does NOT type or census the other skip sites under cgg-runtime, does NOT change what the file's arms assert, and does NOT certify that the tic-812 writer-class closure has fired live.
ALLOW_MISSING_QUEUE_STATE_COMPILE_ENV = "CGG_ALLOW_MISSING_QUEUE_STATE_COMPILE"


def _require_queue_state_compile():
    """Return the compile layer, or make its absence LOUD -- never silent."""
    if _QSC is not None:
        return _QSC
    if os.environ.get(ALLOW_MISSING_QUEUE_STATE_COMPILE_ENV, "").strip():
        announcement = (
            f"{ALLOW_MISSING_QUEUE_STATE_COMPILE_ENV} is set: the compile "
            f"layer is unresolvable, so the family-unification proof in this "
            f"file is SKIPPED, not satisfied."
        )
        print(announcement)
        warnings.warn(announcement, stacklevel=2)
        raise unittest.SkipTest(announcement)
    raise AssertionError(
        "QUEUE STATE COMPILER UNRESOLVABLE -- the family-unification proof in "
        "this file cannot run, so it FAILS rather than skipping quietly.\n"
        "  wanted         : audit-logs/cprs/queue_state_compile.py\n"
        f"  seam checked   : CGG_QUEUE_STATE_COMPILE="
        f"{os.environ.get('CGG_QUEUE_STATE_COMPILE', '') or '(unset or empty)'}\n"
        f"  walked up from : {_HERE}\n"
        f"  roots walked   : {len(_HERE.parents)}, none carrying "
        f"audit-logs/cprs/queue_state_compile.py\n"
        "  supply it: point CGG_QUEUE_STATE_COMPILE at an existing "
        "queue_state_compile.py, or run this file inside a tree whose "
        "ancestry carries audit-logs/cprs/queue_state_compile.py, or set "
        f"{ALLOW_MISSING_QUEUE_STATE_COMPILE_ENV}=1 to skip this proof "
        "deliberately and loudly."
    )


TOPO = {"birth_rung": "site", "birth_scope_path": "/tmp/zone"}
REPORT = {"mandate_id": "tic-694-test", "actor": {"runtime": "claude_code"}}
BIRTH = 100


def _mint(candidate, cycle="pattern_mining"):
    return ci.mint_entry(candidate, cycle, REPORT, BIRTH, TOPO)


class MintStampsMaturityTics(unittest.TestCase):
    def test_minted_entry_carries_explicit_maturity_tics(self):
        """THE defect: pre-fix the gate-reader field was absent entirely."""
        e = _mint({"lesson": "A lesson about clocks."})
        self.assertIn("maturity_tics", e)
        self.assertEqual(e["maturity_tics"], 3)

    def test_dual_stamp_equal_from_one_resolved_source(self):
        """Family A (maturity_tics gate readers) and Family B
        (queue_state_compile window parking) must read the SAME clock."""
        e = _mint({"lesson": "Another lesson."})
        self.assertEqual(e["maturity_tics"], e["maturity_window_tics"])
        self.assertEqual(e["review_tic"], BIRTH + e["maturity_tics"])

    def test_candidate_maturity_tics_override_honored(self):
        e = _mint({"lesson": "Slow-maturing lesson.", "maturity_tics": 5})
        self.assertEqual(e["maturity_tics"], 5)
        self.assertEqual(e["maturity_window_tics"], 5)
        self.assertEqual(e["review_tic"], BIRTH + 5)

    def test_legacy_candidate_window_only_shape_resolves_as_clock(self):
        """A candidate authored in the pre-fix vocabulary (window-only) still
        means the maturity clock on this lane; both fields ride it."""
        e = _mint({"lesson": "Window-vocab lesson.", "maturity_window_tics": 7})
        self.assertEqual(e["maturity_tics"], 7)
        self.assertEqual(e["maturity_window_tics"], 7)

    def test_non_numeric_override_falls_to_default(self):
        e = _mint({"lesson": "Garbled clock.", "maturity_tics": "soon"})
        self.assertEqual(e["maturity_tics"], 3)


class GateReadersHonorMintedField(unittest.TestCase):
    def test_steppable_gate_reads_minted_override(self):
        e = _mint({"lesson": "Gate-read lesson.", "maturity_tics": 5})
        self.assertFalse(cpr_steppable.is_steppable(e, BIRTH + 4))
        self.assertTrue(cpr_steppable.is_steppable(e, BIRTH + 5))

    def test_review_due_derivation_reads_minted_override(self):
        e = _mint({"lesson": "Due-clock lesson.", "maturity_tics": 5})
        import json
        with tempfile.NamedTemporaryFile(
            "w", suffix=".jsonl", delete=False
        ) as f:
            f.write(json.dumps(e) + "\n")
            qpath = Path(f.name)
        try:
            due = mw._derive_review_due_tic(BIRTH + 1, qpath)
            self.assertEqual(due, BIRTH + 5)
        finally:
            qpath.unlink()

    def test_compile_layer_agrees_with_gate_on_minted_row(self):
        """Family unification: the bench-packet parking clock and the
        steppable gate fire at the SAME tic on a post-fix row."""
        _require_queue_state_compile()
        e = _mint({"lesson": "Unified-clock lesson.", "maturity_tics": 5})
        target = _QSC._resolve_target_tic(e)
        self.assertEqual(target, BIRTH + 5)
        self.assertFalse(cpr_steppable.is_steppable(e, target - 1))
        self.assertTrue(cpr_steppable.is_steppable(e, target))


class ArenaLaneSiblingSite(unittest.TestCase):
    """QR-T25-001 in arena-pressure-ingest — the sibling mint site
    (named-footgun-guard-leaves-sibling-site-unfixed: fix-site and
    bug-sibling-site are a closed consumer set)."""

    def _mint_arena(self, candidate):
        api = _load("arena_pressure_ingest",
                    _HERE / "arena-pressure-ingest.py")
        report = {
            "arena_id": "maturity-align-fixture",
            "arena_mode": "experimental",
            "source_tic": BIRTH,
            "candidate_cogprs": [candidate],
        }
        minted = api.ingest_candidate_cogprs(
            report, Path("/dev/null"), Path("/nonexistent-audit-logs"),
            BIRTH, {}, dry_run=True,
        )
        self.assertEqual(len(minted), 1)
        return minted[0]

    def test_arena_mint_dual_stamps_default_clock(self):
        e = self._mint_arena({"lesson": "Arena lesson, default clock."})
        self.assertEqual(e["maturity_tics"], 3)
        self.assertEqual(e["maturity_window_tics"], 3)
        self.assertEqual(e["review_tic"], BIRTH + 3)
        self.assertEqual(e["assignment_reason"], "auto-window backfill")

    def test_arena_candidate_window_no_longer_dropped(self):
        """Pre-fix hole: a candidate-supplied window skipped the backfill
        branch AND was never copied into the row — the row shipped with
        neither field."""
        e = self._mint_arena({"lesson": "Arena lesson, candidate clock.",
                              "maturity_window_tics": 6})
        self.assertEqual(e["maturity_tics"], 6)
        self.assertEqual(e["maturity_window_tics"], 6)
        self.assertEqual(e["review_tic"], BIRTH + 6)
        self.assertEqual(e["assignment_reason"], "candidate clock resolved")


class LegacyDivergenceDocumented(unittest.TestCase):
    def test_legacy_window_only_row_splits_the_reader_families(self):
        """The divergence class the mint fix closes — DOCUMENTED, not
        repaired: a pre-fix row stamped window:10 (no maturity_tics) gates
        steppable at birth+3 while the compile layer parks it to birth+10.
        Historical rows keep this shape (append-only; no silent backfill);
        adjudications keep recording the honest 'maturity_tics ABSENT — gate
        default' line for them."""
        legacy = {
            "status": "extracted",
            "birth_tic": BIRTH,
            "maturity_window_tics": 10,
        }
        self.assertTrue(cpr_steppable.is_steppable(legacy, BIRTH + 3))
        if _QSC is not None:
            self.assertEqual(_QSC._resolve_target_tic(legacy), BIRTH + 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
