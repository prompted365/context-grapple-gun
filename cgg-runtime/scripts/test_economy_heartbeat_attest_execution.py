#!/usr/bin/env python3
"""Tests for economy-heartbeat attest-on-EXECUTION, not on OUTCOME
(bk-economy-attest-execution-fix; ratified ray
 cgg-ledger#attestation-predicate-must-prove-execution-not-outcome).

The contract under guard: the CADENCE cable's winch attestation keys on
EXECUTION evidence — the tic ran its full cadence, the tick accounting closes,
the cap>=seed guard held, the federal boundary normalized, and the carry ledger
advanced (or lawfully refused the write under REPLAY). It must NOT key on the
economic OUTCOME.

The economy is DESIGNED to halt the mint when aggregate trust sits below tau; a
full-tic zero-mint run is the loud, lawful breach state (surface-don't-hide).
Pre-fix the worker required `mint_accrued > 0`, so that by-design breach dropped
a fully-executed CADENCE cable out of the winch dispatch and cascaded to
all_three_cables_committed=false -> seed_stabilized=false while 11/12
stabilization checks passed (lived at tics 652 and 683 — both reproduced below
as the zero_mint_breach fixture).

Arms:
  a) zero-mint breach tic + clean execution     -> ATTEST TRUE   (the RED arm)
  c) normal mint tic                            -> ATTEST TRUE   (regression)
  b) artifacts missing / not landed             -> ATTEST FALSE
     short cadence / tripped guard / stale carry-> ATTEST FALSE
     unclosed tick accounting / no normalization-> ATTEST FALSE
  + outcome-independence: predicate is byte-identical across mint outcomes
  + REPLAY lawfully attests (state write refused by the double-advance guard)
  + exit-code contract: nonzero reserved for execution failure, never health

ISOLATION: every arm pins ROOT / ECON_DIR / STATE_PATH into a tempdir. The live
audit-logs/economy/ lane is never read or written (self-locating artifact test
isolation).

Run:  python3 -m unittest test_economy_heartbeat_attest_execution -v
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "economy_heartbeat", os.path.join(_HERE, "economy-heartbeat.py")
)
eh = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(eh)

TIC = 9683
N_TICKS = 1000


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------
def carry_state(tic: int) -> dict:
    """What motion.save_state leaves behind once the series advanced to `tic`."""
    return {
        "type": "economy.carry_state", "version": 1, "tic": tic,
        "buffer": {"current_supply": 4251.7, "reserves": 850.3, "usd_rate": 1.0},
        "cumulative": {"mint_total": 0.0, "burn_total": 0.0, "generation": 113000},
        "market": {"spread": 0.5, "elasticity": 0.5, "global_tick": 113000},
        "swarm": {"seed": 42, "agents": []},
    }


def make_trace(*, mint_accrued=37459.99, ticks_with_mint=814, breach=False,
               ticks_per_tic=N_TICKS, ran_full_tic=True, guard_clear=True,
               anchor_frozen=True, normalizations=1, series_mode="continue"):
    """A complete economy trace, shaped exactly like a real economy-tic-N.json."""
    counts = {"trust_below_tau": ticks_per_tic if breach else 0,
              "reserve_breach": 0, "rate_band_breach": 0,
              "supply_cap_reached": 0,
              "mint_halted": ticks_per_tic if breach else 0}
    return {
        "SWARM": {
            "n_agents": 128, "aggregate_g_t_low_trust": 0.5,
            "aggregate_g_t_high_trust": 0.9, "tau": 0.7,
            "mint_low_trust_20gen": 0.0, "mint_high_trust_20gen": 500.0,
            "economy_g_t_low": 0.5, "economy_g_t_high": 0.9,
            "low_trust_halt_reason": "trust_below_tau",
            "coin_trust_closed": True, "mint_moves_with_g_t": True,
        },
        "CADENCE": {
            "ticks_per_tic": ticks_per_tic,
            "one_tic_ran_1000_ticks": ran_full_tic,
            "floor_trap_message": "cap>=seed ok" if guard_clear else "floor trap tripped",
            "cap_ge_seed_guard_clear": guard_clear,
            "supply_before": 4200.0, "supply_after": 4251.719253,
            "reserves_before": 840.0, "reserves_after": 850.34,
            "final_reserve_ratio": 0.2,
            "min_supply_during_tic": 4251.719253,
            "min_reserve_ratio_during_tic": 0.2,
            "mint_accrued": mint_accrued, "burn_accrued": 12.5,
            "ticks_with_mint": ticks_with_mint,
            "first_mint_tick": 1 if ticks_with_mint else None,
            "zero_mint_ticks": ticks_per_tic - ticks_with_mint,
            "swarm_trust_start": 0.61, "swarm_final_aggregate_g_t": 0.59,
            "swarm_trust_moved": True, "g_t_trajectory_samples": [],
            "breach_flag_tick_counts": counts,
            "breach_emitter_records": 2 if breach else 0,
            "tic_boundary": {
                "pre_normalize_rate": 1.0, "held_rate_after": 1.0,
                "deviation_absorbed": 0.0,
                "anchor_frozen_center_excluded": anchor_frozen,
                "federal_normalizations": normalizations,
            },
            "series": {
                "mode": series_mode, "carried_from_tic": TIC - 1,
                "cumulative_mint_total": 0.0, "cumulative_burn_total": 0.0,
                "cumulative_generation": 113000,
                "market": {"spread": 0.5, "elasticity": 0.5,
                           "global_tick": 113000},
            },
        },
        "PRICING": {
            "held_rate": 1.0, "band": [0.5, 2.0], "within_band": True,
            "clamped_degraded_anchor": False, "source": "federal",
            "engagement": {"outcome_units": 3.0, "coin_earned": 1500.0,
                           "usd_value": 1500.0, "non_speculative": True,
                           "degraded_anchor": False},
            "compute_leg_8000_ucoin_usd": 8000.0, "coin_usd_anchored": True,
        },
    }


def zero_mint_breach(**kw):
    """The lived tic-652 / tic-683 shape: 1000/1000 zero-mint ticks under a
    standing trust_below_tau + mint_halted breach — designed, lawful, loud."""
    kw.setdefault("mint_accrued", 0.0)
    kw.setdefault("ticks_with_mint", 0)
    kw.setdefault("breach", True)
    return make_trace(**kw)


class IsolatedRoot:
    """Pin the module's self-located surfaces into a fixture root."""

    def __init__(self, state_tic=TIC):
        self._tmp = tempfile.TemporaryDirectory()
        self._state_tic = state_tic
        self._saved = None

    def __enter__(self):
        root = Path(self._tmp.name)
        econ = root / "audit-logs" / "economy"
        econ.mkdir(parents=True, exist_ok=True)
        self._saved = (eh.ROOT, eh.ECON_DIR, eh.STATE_PATH)
        eh.ROOT, eh.ECON_DIR = root, econ
        eh.STATE_PATH = econ / "economy-state.json"
        if self._state_tic is not None:
            eh.STATE_PATH.write_text(
                json.dumps(carry_state(self._state_tic)) + "\n", encoding="utf-8")
        self.root, self.econ = root, econ
        return self

    def __exit__(self, *exc):
        eh.ROOT, eh.ECON_DIR, eh.STATE_PATH = self._saved
        self._tmp.cleanup()
        return False


def attest(trace, tic=TIC):
    """Run the attestation chain and return (evidence, fire, verdict)."""
    ev = eh.execution_evidence(tic, trace)
    fire = eh.fire_gunslinger(trace, ev)
    return ev, fire, eh.stabilization_verdict(trace, fire)


# ===========================================================================
# ARM (a) — the RED arm: a designed zero-mint breach tic ATTESTS TRUE
# ===========================================================================
class TestZeroMintBreachAttestsTrue(unittest.TestCase):

    def test_zero_mint_breach_with_clean_execution_attests_true(self):
        with IsolatedRoot():
            ev, fire, verdict = attest(zero_mint_breach())
        self.assertTrue(ev["cadence_executed"], ev["failed_checks"])
        self.assertEqual(ev["failed_checks"], [])
        self.assertIn("CADENCE", fire["dispatched"])
        self.assertTrue(fire["all_cables_raised_at_once"])
        self.assertTrue(verdict["checks"]["all_three_cables_committed"])
        self.assertTrue(verdict["seed_stabilized"])

    def test_breach_flags_stay_visible_while_attestation_holds(self):
        """Surface-don't-hide: attesting true must not suppress the breach."""
        with IsolatedRoot():
            ev, _fire, verdict = attest(zero_mint_breach())
        self.assertEqual(sorted(verdict["breach_flags_fired_during_tic"]),
                         ["mint_halted", "trust_below_tau"])
        self.assertEqual(sorted(ev["observability"]["breach_flags_fired"]),
                         ["mint_halted", "trust_below_tau"])
        self.assertEqual(ev["observability"]["mint_accrued"], 0.0)
        self.assertEqual(ev["observability"]["zero_mint_ticks"], N_TICKS)

    def test_receipt_labels_mint_as_observability_not_basis(self):
        with IsolatedRoot():
            ev = eh.execution_evidence(TIC, zero_mint_breach())
        self.assertIn("NEVER mint or breach outcome", ev["predicate"])


# ===========================================================================
# ARM (c) — a normal mint tic still ATTESTS TRUE (regression guard)
# ===========================================================================
class TestNormalMintTicAttestsTrue(unittest.TestCase):

    def test_normal_mint_tic_attests_true(self):
        with IsolatedRoot():
            ev, fire, verdict = attest(make_trace())
        self.assertTrue(ev["cadence_executed"])
        self.assertIn("CADENCE", fire["dispatched"])
        self.assertTrue(fire["all_cables_raised_at_once"])
        self.assertTrue(verdict["seed_stabilized"])

    def test_predicate_is_outcome_independent(self):
        """The attestation checks must be IDENTICAL across mint outcomes —
        that identity IS the invariant."""
        with IsolatedRoot():
            minted = eh.execution_evidence(TIC, make_trace())
            halted = eh.execution_evidence(TIC, zero_mint_breach())
        self.assertEqual(minted["checks"], halted["checks"])
        self.assertTrue(minted["cadence_executed"])
        self.assertTrue(halted["cadence_executed"])
        # ...while the observability legs genuinely differ
        self.assertNotEqual(minted["observability"]["mint_accrued"],
                            halted["observability"]["mint_accrued"])


# ===========================================================================
# ARM (b) — genuine EXECUTION failures ATTEST FALSE
# ===========================================================================
class TestExecutionFailureAttestsFalse(unittest.TestCase):

    def _assert_fails(self, trace, check, *, state_tic=TIC):
        with IsolatedRoot(state_tic=state_tic):
            ev, fire, verdict = attest(trace)
        self.assertFalse(ev["cadence_executed"])
        self.assertIn(check, ev["failed_checks"])
        self.assertNotIn("CADENCE", fire["dispatched"])
        self.assertFalse(verdict["checks"]["all_three_cables_committed"])
        return ev

    def test_short_cadence_fails(self):
        self._assert_fails(make_trace(ticks_per_tic=12, ran_full_tic=False,
                                      ticks_with_mint=0), "ran_full_tic")

    def test_tripped_floor_guard_fails(self):
        self._assert_fails(make_trace(guard_clear=False), "guards_clear")

    def test_unnormalized_tic_boundary_fails(self):
        self._assert_fails(make_trace(normalizations=0),
                           "tic_boundary_normalized")
        self._assert_fails(make_trace(anchor_frozen=False),
                           "tic_boundary_normalized")

    def test_series_state_not_advanced_fails(self):
        """The carry ledger is the series' spine — a missing series write is an
        execution failure even when every number in the trace looks healthy."""
        self._assert_fails(make_trace(), "series_state_advanced",
                           state_tic=TIC - 1)
        ev = self._assert_fails(make_trace(), "series_state_advanced",
                                state_tic=None)
        self.assertEqual(ev["carry_state_note"], "carry_state_absent")

    def test_incomplete_trace_fails(self):
        trace = make_trace()
        del trace["CADENCE"]["supply_after"]
        self._assert_fails(trace, "trace_complete")

    def test_unclosed_tick_accounting_fails(self):
        trace = make_trace()
        trace["CADENCE"]["zero_mint_ticks"] = 3      # 814 + 3 != 1000
        self._assert_fails(trace, "tick_accounting_closed")

    def test_unknown_series_mode_fails(self):
        self._assert_fails(make_trace(series_mode="wat"),
                           "series_state_advanced")


# ===========================================================================
# ARM (b) — artifacts missing / not landed ATTESTS FALSE (post-write half)
# ===========================================================================
class TestArtifactVerification(unittest.TestCase):

    def _write(self, trace, tic=TIC):
        ev, fire, verdict = attest(trace, tic)
        return ev, eh.write_outputs(tic, trace, fire, verdict, ev)

    def test_clean_zero_mint_run_lands_and_verifies(self):
        with IsolatedRoot():
            ev, paths = self._write(zero_mint_breach())
            av = paths["artifact_verification"]
            snap = json.loads(paths["snapshot"].read_text(encoding="utf-8"))
            ptr = json.loads(paths["pointer"].read_text(encoding="utf-8"))
            rows = [json.loads(x) for x in
                    paths["invocations"].read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertTrue(av["ok"], av["failures"])
        self.assertTrue(av["snapshot_verified"])
        self.assertTrue(av["pointer_verified"])
        self.assertTrue(av["invocation_appended"])
        # execution and health are now SEPARATE fields on the artifact
        self.assertTrue(snap["execution_attested"])
        self.assertTrue(snap["seed_stabilized"])
        self.assertEqual(snap["mint_total"], 0.0)
        self.assertEqual(sorted(snap["breach_flags"]),
                         ["mint_halted", "trust_below_tau"])
        self.assertEqual(snap["detail"]["execution_attestation"]["failed_checks"], [])
        self.assertTrue(ptr["execution_attested"])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["execution_attested"])
        self.assertEqual(rows[0]["execution_failed_checks"], [])
        self.assertEqual(ev["failed_checks"], [])

    def test_missing_snapshot_fails_verification(self):
        with IsolatedRoot():
            _ev, paths = self._write(make_trace())
            paths["snapshot"].unlink()
            av = eh.verify_artifacts(TIC, paths["snapshot"], paths["pointer"],
                                     paths["invocations"], "continue")
        self.assertFalse(av["ok"])
        self.assertFalse(av["snapshot_verified"])
        self.assertTrue(any("snapshot unreadable" in f for f in av["failures"]))

    def test_frozen_pointer_fails_verification(self):
        """The anti-freeze tooth: a pointer left on an older tic is a failure."""
        with IsolatedRoot():
            _ev, paths = self._write(make_trace())
            paths["pointer"].write_text(json.dumps({"tic": TIC - 5}) + "\n",
                                        encoding="utf-8")
            av = eh.verify_artifacts(TIC, paths["snapshot"], paths["pointer"],
                                     paths["invocations"], "continue")
        self.assertFalse(av["ok"])
        self.assertTrue(any("anti-freeze" in f for f in av["failures"]))

    def test_missing_invocation_row_fails_verification(self):
        with IsolatedRoot():
            _ev, paths = self._write(make_trace())
            paths["invocations"].unlink()
            av = eh.verify_artifacts(TIC, paths["snapshot"], paths["pointer"],
                                     paths["invocations"], "continue")
        self.assertFalse(av["ok"])
        self.assertFalse(av["invocation_appended"])

    def test_invocations_append_is_flocked_and_accretes(self):
        with IsolatedRoot():
            self._write(make_trace())
            _ev, paths = self._write(zero_mint_breach())
            rows = [json.loads(x) for x in
                    paths["invocations"].read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["execution_attested"] for r in rows))


# ===========================================================================
# REPLAY — the double-advance guard's lawful state refusal still attests
# ===========================================================================
class TestReplayAttestsLawfully(unittest.TestCase):

    def test_replay_attests_without_a_state_write(self):
        with IsolatedRoot(state_tic=TIC):     # series already AT this tic
            ev, fire, _verdict = attest(zero_mint_breach(series_mode="replay"))
        self.assertTrue(ev["cadence_executed"], ev["failed_checks"])
        self.assertIn("CADENCE", fire["dispatched"])

    def test_replay_sidecar_verifies_without_repointing(self):
        with IsolatedRoot(state_tic=TIC):
            trace = zero_mint_breach(series_mode="replay")
            ev, fire, verdict = attest(trace)
            paths = eh.write_outputs(TIC, trace, fire, verdict, ev)
            av = paths["artifact_verification"]
        self.assertTrue(paths["snapshot"].name.endswith("-replay.json"))
        self.assertFalse(paths["pointer"].exists())   # pointer stays on the series
        self.assertFalse(av["pointer_checked"])
        self.assertTrue(av["ok"], av["failures"])

    def test_replay_behind_the_series_fails(self):
        with IsolatedRoot(state_tic=TIC - 4):   # cannot be a replay of a future tic
            ev, _fire, _v = attest(make_trace(series_mode="replay"))
        self.assertFalse(ev["cadence_executed"])
        self.assertIn("series_state_advanced", ev["failed_checks"])


# ===========================================================================
# EXIT-CODE CONTRACT — nonzero reserved for execution failure, never health
# ===========================================================================
class TestExitCodeContract(unittest.TestCase):
    """main() computes rc from (cadence_executed AND artifact_verification.ok).
    Re-derived here at the seam so the heavy 128-agent run is not required."""

    @staticmethod
    def _rc(evidence, av):
        return 0 if (bool(evidence["cadence_executed"]) and bool(av["ok"])) else 1

    def test_zero_mint_breach_tic_exits_zero(self):
        with IsolatedRoot():
            trace = zero_mint_breach()
            ev, fire, verdict = attest(trace)
            paths = eh.write_outputs(TIC, trace, fire, verdict, ev)
            rc = self._rc(ev, paths["artifact_verification"])
        self.assertEqual(rc, 0)

    def test_unhealthy_but_executed_tic_exits_zero(self):
        """A collapsing-supply HEALTH failure is a verdict, not a crash."""
        trace = zero_mint_breach()
        trace["CADENCE"]["min_supply_during_tic"] = 0.0    # health check trips
        with IsolatedRoot():
            ev, fire, verdict = attest(trace)
            paths = eh.write_outputs(TIC, trace, fire, verdict, ev)
            rc = self._rc(ev, paths["artifact_verification"])
        self.assertFalse(verdict["seed_stabilized"])       # health says NO
        self.assertFalse(verdict["checks"]["no_supply_collapse"])
        self.assertTrue(ev["cadence_executed"])            # execution says YES
        self.assertEqual(rc, 0)                            # exit follows execution

    def test_execution_failure_exits_nonzero(self):
        with IsolatedRoot(state_tic=TIC - 1):              # series never advanced
            trace = make_trace()
            ev, fire, verdict = attest(trace)
            paths = eh.write_outputs(TIC, trace, fire, verdict, ev)
            rc = self._rc(ev, paths["artifact_verification"])
        self.assertEqual(rc, 1)

    def test_missing_artifact_exits_nonzero(self):
        with IsolatedRoot():
            trace = make_trace()
            ev, fire, verdict = attest(trace)
            paths = eh.write_outputs(TIC, trace, fire, verdict, ev)
            paths["snapshot"].unlink()
            av = eh.verify_artifacts(TIC, paths["snapshot"], paths["pointer"],
                                     paths["invocations"], "continue")
            rc = self._rc(ev, av)
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
