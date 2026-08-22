#!/usr/bin/env python3
"""Tests for economy-heartbeat BREACH DWELL AT FLAG ALTITUDE (tic 725, rider lane C).

Authorizing verdict: /review 725, Architect-ratified —
ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude.

The defect under guard: `breach_flags` is an ANY-OCCURRENCE boolean over the
tic's 1000 internal ticks, so aggregated over that population it SATURATES.
The identical set ['trust_below_tau','mint_halted'] rode 162 of 164 tics
(98.8% base rate) while the governance-bearing quantity — ticks-below-tau —
swung 16→991 and sat one level down in detail.breach_flag_tick_counts. Lived
at tic 725: aggregate g_t 0.748988 sat ABOVE tau 0.70 with only 107/1000 ticks
below it, yet the flags still read as a full breach and the reader could not
see the recovery without diving into `detail`.

The contract this file guards:

  1. PLACEMENT LAW (t724 lane A scar) — `breach_dwell` actually LANDS at top
     level in EVERY artifact `breach_flags` rides in (snapshot, current-pointer,
     invocations row), and survives the real downstream consumer projection.
     Verified by running the artifact-assembly function (write_outputs) in an
     isolated root — never by emitting a live economy tic.
  2. DISCRIMINATION — a 107/1000 recovery tic and a 1000/1000 saturated tic
     carry the SAME breach_flags but DIFFERENT dwell; the flag alone cannot
     tell them apart, the dwell can.
  3. ADDITIVE-ONLY — every pre-existing top-level field keeps its exact name
     and value; the flags, tau, caps, mode, phase, seed_stabilized, and the
     execution attestation are untouched. breach_dwell is the only new key.
  4. FAIL-SOFT — a missing counter or unusable denominator yields honest None
     and severity "undetermined", never an invented number.

ISOLATION: every arm pins ROOT / ECON_DIR / STATE_PATH into a tempdir via the
sibling suite's IsolatedRoot. The live audit-logs/economy/ lane is never read
or written (self-locating artifact test isolation).

Run:  python3 -m unittest test_economy_heartbeat_dwell_altitude_tic725 -v
"""
import importlib.util
import json
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Reuse the sibling suite's fixture builders AND its module instance. Loading
# economy-heartbeat.py a second time would give a second module object whose
# ROOT/ECON_DIR/STATE_PATH IsolatedRoot does not patch — one instance only.
_sib = _load("economy_heartbeat_attest_suite",
             "test_economy_heartbeat_attest_execution.py")
eh = _sib.eh
IsolatedRoot = _sib.IsolatedRoot
make_trace = _sib.make_trace
zero_mint_breach = _sib.zero_mint_breach
attest = _sib.attest
TIC = _sib.TIC
N_TICKS = _sib.N_TICKS

# The exact top-level key list the snapshot carried BEFORE this change, in
# order. Pinned so an accidental rename/drop/reorder of an existing field is a
# test failure, not a silent contract break.
PRE_CHANGE_SNAPSHOT_KEYS = [
    "type", "tic", "series_mode", "carried_from_tic", "supply", "reserves",
    "reserve_ratio", "rate", "mint_total", "burn_total", "g_t", "phase",
    "mode", "breach_flags", "seed_stabilized", "execution_attested",
    "detail", "membrane", "generated_at",
]
PRE_CHANGE_POINTER_KEYS = [
    "tic", "economy_tic_path", "generated_at", "breach_flags",
    "seed_stabilized", "execution_attested", "series_mode",
]
PRE_CHANGE_INVOCATION_KEYS = [
    "tic", "invoked_at", "mode", "series_mode", "g_t", "mint_total",
    "breach_flags", "seed_stabilized", "execution_attested",
    "execution_failed_checks",
]


def recovery_trace(below_tau_ticks=107, **kw):
    """The LIVE tic-725 shape: aggregate g_t ABOVE tau, mint flowing, yet the
    any-occurrence flags still latched off 107 breaching internal ticks."""
    kw.setdefault("ticks_with_mint", N_TICKS - below_tau_ticks)
    trace = make_trace(**kw)
    trace["CADENCE"]["swarm_final_aggregate_g_t"] = 0.748988      # ABOVE tau 0.70
    trace["CADENCE"]["breach_flag_tick_counts"] = {
        "trust_below_tau": below_tau_ticks, "reserve_breach": 0,
        "rate_band_breach": 0, "supply_cap_reached": 0,
        "mint_halted": below_tau_ticks,
    }
    trace["CADENCE"]["breach_emitter_records"] = 2
    return trace


def write(trace, tic=TIC):
    """Run the attestation chain then the ARTIFACT-ASSEMBLY function."""
    ev, fire, verdict = attest(trace, tic)
    return eh.write_outputs(tic, trace, fire, verdict, ev), ev, verdict


def read_all(paths):
    snap = json.loads(paths["snapshot"].read_text(encoding="utf-8"))
    ptr = (json.loads(paths["pointer"].read_text(encoding="utf-8"))
           if paths["pointer"].exists() else None)
    rows = [json.loads(x) for x in
            paths["invocations"].read_text(encoding="utf-8").splitlines() if x.strip()]
    return snap, ptr, rows


# ===========================================================================
# PLACEMENT LAW — the field must actually LAND, not be dropped by the writer
# ===========================================================================
class TestPlacementLaw(unittest.TestCase):
    """t724 lane A scar: a writer that assembles through a fixed schema can
    silently drop a new top-level field. Verified by RUNNING the assembly."""

    def test_dwell_lands_top_level_in_all_three_artifacts(self):
        with IsolatedRoot():
            paths, _ev, _v = write(recovery_trace())
            snap, ptr, rows = read_all(paths)
        for label, obj in (("snapshot", snap), ("pointer", ptr),
                           ("invocations row", rows[-1])):
            self.assertIn("breach_dwell", obj,
                          f"breach_dwell was DROPPED from the {label}")
            self.assertIsInstance(obj["breach_dwell"], dict)
            self.assertIn("breach_flags", obj)

    def test_dwell_sits_immediately_beside_the_flag_it_qualifies(self):
        """'At the flag's altitude' is structural: same nesting level, adjacent
        in the emitted key order — never one level down in `detail`."""
        with IsolatedRoot():
            paths, _ev, _v = write(recovery_trace())
            snap, ptr, rows = read_all(paths)
        for label, obj in (("snapshot", snap), ("pointer", ptr),
                           ("invocations row", rows[-1])):
            keys = list(obj)
            self.assertEqual(keys[keys.index("breach_flags") + 1], "breach_dwell",
                             f"{label}: dwell is not adjacent to its flag")
        # and it is NOT merely nested down in detail
        self.assertNotIn("breach_dwell", snap["detail"])
        self.assertIn("breach_flag_tick_counts", snap["detail"])   # basis still there

    def test_dwell_survives_the_real_downstream_consumer_projection(self):
        """braid-input-builder.py:143 projects the snapshot with a DENY-list
        (`{k: v for k, v in snap.items() if k != 'detail'}`) into the braid
        envelope's economy.latest. Replicated here: a top-level dwell reaches
        the consumer; a dwell buried in `detail` would not have."""
        with IsolatedRoot():
            paths, _ev, _v = write(recovery_trace())
            snap, _ptr, _rows = read_all(paths)
        latest = {k: v for k, v in snap.items() if k != "detail"}
        self.assertIn("breach_dwell", latest)
        self.assertIn("breach_flags", latest)
        self.assertEqual(latest["breach_dwell"]["ticks"]["trust_below_tau"], 107)

    def test_dwell_lands_on_the_replay_sidecar_too(self):
        with IsolatedRoot(state_tic=TIC):
            paths, _ev, _v = write(recovery_trace(series_mode="replay"))
            snap, ptr, rows = read_all(paths)
        self.assertTrue(paths["snapshot"].name.endswith("-replay.json"))
        self.assertIsNone(ptr)                       # pointer lawfully unmoved
        self.assertIn("breach_dwell", snap)
        self.assertIn("breach_dwell", rows[-1])


# ===========================================================================
# DISCRIMINATION — the dwell separates what the saturated flag cannot
# ===========================================================================
class TestDwellDiscriminates(unittest.TestCase):

    def test_live_tic_725_recovery_is_visible_without_opening_detail(self):
        """g_t 0.748988 sits ABOVE tau 0.70; only 107/1000 internal ticks
        breached. The flag still latches — the dwell shows the recovery."""
        with IsolatedRoot():
            paths, _ev, _v = write(recovery_trace(below_tau_ticks=107))
            snap, _ptr, _rows = read_all(paths)
        self.assertEqual(sorted(snap["breach_flags"]),
                         ["mint_halted", "trust_below_tau"])       # flag unchanged
        d = snap["breach_dwell"]
        self.assertEqual(d["ticks"]["trust_below_tau"], 107)
        self.assertEqual(d["fraction"]["trust_below_tau"], 0.107)
        self.assertEqual(d["ticks_per_tic"], N_TICKS)
        self.assertEqual(d["max_fraction"], 0.107)
        self.assertEqual(d["severity"], "intermittent")
        self.assertGreater(snap["g_t"], 0.70)                      # above tau

    def test_saturated_tic_reads_saturated(self):
        with IsolatedRoot():
            paths, _ev, _v = write(zero_mint_breach())             # 1000/1000
            snap, _ptr, _rows = read_all(paths)
        d = snap["breach_dwell"]
        self.assertEqual(d["ticks"]["trust_below_tau"], N_TICKS)
        self.assertEqual(d["fraction"]["trust_below_tau"], 1.0)
        self.assertEqual(d["severity"], "saturated")

    def test_same_flags_different_dwell_is_the_whole_point(self):
        """Both tics emit the IDENTICAL breach set. Only the dwell separates
        the 10.7%-recovery tic from the 100%-halt tic."""
        with IsolatedRoot():
            recovered, _e, _v = write(recovery_trace(below_tau_ticks=107))
            # read BEFORE the second write — both land on the same tic path
            r = json.loads(recovered["snapshot"].read_text(encoding="utf-8"))
            saturated, _e2, _v2 = write(zero_mint_breach(), tic=TIC)
            s = json.loads(saturated["snapshot"].read_text(encoding="utf-8"))
        self.assertNotEqual(r["breach_dwell"]["ticks"],
                            s["breach_dwell"]["ticks"])
        self.assertEqual(sorted(r["breach_flags"]), sorted(s["breach_flags"]))
        self.assertNotEqual(r["breach_dwell"]["max_fraction"],
                            s["breach_dwell"]["max_fraction"])
        self.assertNotEqual(r["breach_dwell"]["severity"],
                            s["breach_dwell"]["severity"])

    def test_severity_word_tracks_the_rate_across_the_bands(self):
        for below, word in ((16, "intermittent"), (249, "intermittent"),
                            (250, "sustained"), (749, "sustained"),
                            (750, "saturated"), (991, "saturated")):
            d = eh.breach_dwell(["trust_below_tau"],
                                {"trust_below_tau": below}, N_TICKS)
            self.assertEqual(d["severity"], word,
                             f"{below}/{N_TICKS} classified {d['severity']}")

    def test_keys_are_set_equal_to_the_fired_flags(self):
        """The flag says WHETHER, the dwell says HOW MUCH — one pair, one key set."""
        with IsolatedRoot():
            paths, _ev, _v = write(recovery_trace())
            snap, ptr, rows = read_all(paths)
        for obj in (snap, ptr, rows[-1]):
            d = obj["breach_dwell"]
            self.assertEqual(set(d["ticks"]), set(obj["breach_flags"]))
            self.assertEqual(set(d["fraction"]), set(obj["breach_flags"]))

    def test_clean_tic_reports_none_not_a_fake_zero_breach(self):
        with IsolatedRoot():
            paths, _ev, _v = write(make_trace())                   # no flags fired
            snap, _ptr, _rows = read_all(paths)
        self.assertEqual(snap["breach_flags"], [])
        d = snap["breach_dwell"]
        self.assertEqual(d["ticks"], {})
        self.assertEqual(d["fraction"], {})
        self.assertEqual(d["max_fraction"], 0.0)
        self.assertEqual(d["severity"], "none")


# ===========================================================================
# ADDITIVE ONLY — the Architect's dials and every existing field are untouched
# ===========================================================================
class TestAdditiveOnly(unittest.TestCase):

    def test_breach_dwell_is_the_only_new_top_level_key(self):
        with IsolatedRoot():
            paths, _ev, _v = write(recovery_trace())
            snap, ptr, rows = read_all(paths)
        for label, obj, pre in (("snapshot", snap, PRE_CHANGE_SNAPSHOT_KEYS),
                                ("pointer", ptr, PRE_CHANGE_POINTER_KEYS),
                                ("invocations row", rows[-1],
                                 PRE_CHANGE_INVOCATION_KEYS)):
            self.assertEqual(set(obj) - {"breach_dwell"}, set(pre),
                             f"{label}: an existing field was added/renamed/dropped")
            self.assertEqual([k for k in obj if k != "breach_dwell"], pre,
                             f"{label}: existing field ORDER moved")

    def test_existing_field_values_are_byte_identical_to_a_dwell_free_read(self):
        """Every pre-existing field must carry exactly the value it carried
        before — the dwell rides alongside, it never rewrites."""
        trace = recovery_trace()
        with IsolatedRoot():
            paths, _ev, verdict = write(trace)
            snap, ptr, rows = read_all(paths)
        cad = trace["CADENCE"]
        self.assertEqual(snap["phase"], "SimOnly")                 # phase untouched
        self.assertEqual(snap["supply"], cad["supply_after"])
        self.assertEqual(snap["reserves"], cad["reserves_after"])
        self.assertEqual(snap["reserve_ratio"], cad["final_reserve_ratio"])
        self.assertEqual(snap["mint_total"], cad["mint_accrued"])
        self.assertEqual(snap["burn_total"], cad["burn_accrued"])
        self.assertEqual(snap["g_t"], cad["swarm_final_aggregate_g_t"])
        self.assertEqual(snap["breach_flags"],
                         verdict["breach_flags_fired_during_tic"])
        self.assertEqual(snap["seed_stabilized"], verdict["seed_stabilized"])
        self.assertEqual(snap["detail"]["breach_flag_tick_counts"],
                         cad["breach_flag_tick_counts"])           # basis unmoved
        self.assertEqual(ptr["breach_flags"], snap["breach_flags"])
        self.assertEqual(rows[-1]["g_t"], snap["g_t"])

    def test_dwell_does_not_touch_the_flag_computation(self):
        """breach_dwell READS the counters; the fired set stays derived solely
        from `count > 0` in stabilization_verdict."""
        trace = recovery_trace(below_tau_ticks=1)                  # one single tick
        with IsolatedRoot():
            _paths, _ev, verdict = write(trace)
        self.assertEqual(sorted(verdict["breach_flags_fired_during_tic"]),
                         ["mint_halted", "trust_below_tau"])       # still latched
        d = eh.breach_dwell(verdict["breach_flags_fired_during_tic"],
                            verdict["breach_flag_tick_counts"], N_TICKS)
        self.assertEqual(d["ticks"]["trust_below_tau"], 1)
        self.assertEqual(d["severity"], "intermittent")            # honestly tiny

    def test_attestation_and_health_verdict_are_unaffected(self):
        """Execution evidence and seed_stabilized must be blind to the dwell —
        the exit code still speaks only for execution."""
        with IsolatedRoot():
            recov = eh.execution_evidence(TIC, recovery_trace())
            sat = eh.execution_evidence(TIC, zero_mint_breach())
            paths, ev, verdict = write(recovery_trace())
            av = paths["artifact_verification"]
        self.assertEqual(recov["checks"], sat["checks"])
        self.assertNotIn("breach_dwell", recov)                    # not on the predicate
        self.assertIn("NEVER mint or breach outcome", recov["predicate"])
        self.assertTrue(ev["cadence_executed"], ev["failed_checks"])
        self.assertTrue(verdict["seed_stabilized"])
        self.assertTrue(av["ok"], av["failures"])                  # artifacts still verify

    def test_dwell_declares_its_own_basis_and_bands(self):
        """Self-describing: the reader can re-derive the severity word without
        this source file (artifact-language-must-not-exceed-confidence)."""
        d = eh.breach_dwell(["trust_below_tau"], {"trust_below_tau": 107}, N_TICKS)
        self.assertEqual(d["basis"], "detail.breach_flag_tick_counts")
        self.assertEqual(d["severity_bands"], eh.DWELL_SEVERITY_EDGES)
        self.assertIn("ADDITIVE", d["note"])


# ===========================================================================
# FAIL-SOFT — honest None, never an invented number
# ===========================================================================
class TestFailSoft(unittest.TestCase):

    def test_missing_counter_yields_none_not_zero(self):
        d = eh.breach_dwell(["trust_below_tau", "mint_halted"],
                            {"trust_below_tau": 107}, N_TICKS)
        self.assertEqual(d["ticks"]["trust_below_tau"], 107)
        self.assertIsNone(d["ticks"]["mint_halted"])
        self.assertIsNone(d["fraction"]["mint_halted"])
        self.assertEqual(d["max_fraction"], 0.107)      # from the known leg only
        self.assertEqual(d["severity"], "intermittent")

    def test_unusable_denominator_is_undetermined(self):
        for denom in (0, None, -5, True, "1000"):
            d = eh.breach_dwell(["trust_below_tau"],
                                {"trust_below_tau": 107}, denom)
            self.assertIsNone(d["ticks_per_tic"], denom)
            self.assertIsNone(d["fraction"]["trust_below_tau"], denom)
            self.assertEqual(d["severity"], "undetermined", denom)
            self.assertEqual(d["ticks"]["trust_below_tau"], 107)   # count still honest

    def test_absent_counters_dict_is_undetermined_not_clean(self):
        d = eh.breach_dwell(["trust_below_tau"], None, N_TICKS)
        self.assertIsNone(d["ticks"]["trust_below_tau"])
        self.assertEqual(d["severity"], "undetermined")

    def test_no_flags_and_no_counters_is_none(self):
        d = eh.breach_dwell(None, None, None)
        self.assertEqual(d["severity"], "none")
        self.assertEqual(d["ticks"], {})
        self.assertEqual(d["max_fraction"], 0.0)

    def test_boolean_counter_is_rejected_as_malformed(self):
        """bool is an int subclass — a True in a numeric slot is malformed."""
        d = eh.breach_dwell(["trust_below_tau"],
                            {"trust_below_tau": True}, N_TICKS)
        self.assertIsNone(d["ticks"]["trust_below_tau"])
        self.assertEqual(d["severity"], "undetermined")


if __name__ == "__main__":
    unittest.main(verbosity=2)
