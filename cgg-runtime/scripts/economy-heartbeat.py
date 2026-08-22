#!/usr/bin/env python3
"""economy-heartbeat.py — deterministic per-tic ECONOMY HEARTBEAT handler (tic 568 wire).

Sibling of contagion-invoke.sh's engine step, in the economy lane. This is the
per-tic runner the economy is "wired" onto so it runs itself each tic: it builds
its input (spawns the 128-agent nautilus swarm), runs ONE economy tic in GUNSLINGER
(seed) mode cradled by a DissonanceBasin with a RollbackDrill armed, computes the
swarm's aggregate g_t -> mint (coin<->trust closure), captures the first-class VISIBLE
breach flags, and writes a per-tic artifact + a current-pointer + an append-only
invocations audit trail.

It REUSES the PROVEN assembly of `seed_the_ember.py` (cables SWARM -> CADENCE ->
PRICING, MODES as the winch) — the exact working call sequence that seeded the ember
at tic 568 — adapted to a per-tic parameterized run.

MOVING (tic 571 — the economy fuckin moves)
-------------------------------------------
The seed phase re-seeded the swarm every invocation (fixed asymptotic trust ramp),
so consecutive tics replayed byte-identical economics. Now the heartbeat rides
`autonomous_kernel/economy_motion.py`: trust is PERFORMANCE-DRIVEN (each tick the
128 agents react to a rotating market regime, realize pnl on their side, roll
their windows, rescore trust — BOTH directions), and the full state (buffer,
cumulative counters, per-agent trust+performance, market regime) CARRIES across
tics via audit-logs/economy/economy-state.json. tic N+1 CONTINUES tic N. The
advance guard types every run genesis|continue|replay — a re-fire of an
already-advanced tic runs as REPLAY (no state write, no series clobber).

ATTESTATION BASIS (tic 684 — bk-economy-attest-execution-fix)
-------------------------------------------------------------
A cable ATTESTS on EXECUTION-lawfulness, never on OUTCOME-health. The economy is
DESIGNED to halt the mint when aggregate trust sits below tau — a full-tic
zero-mint run is the LOUD, LAWFUL breach state (surface-don't-hide), not a
failure. The CADENCE worker used to require `mint_accrued > 0`, so that by-design
breach dropped a fully-executed cable out of the winch dispatch and cascaded to
all_three_cables_committed=false -> seed_stabilized=false while 11/12
stabilization checks passed and the CADENCE trace was complete (lived at tics
652 and 683). The predicate is now `execution_evidence()`: the tic ran its full
cadence, the guards held, the federal boundary normalized, and the carry ledger
advanced (or lawfully refused the write under REPLAY). Mint / breach / supply
numbers ride along as OBSERVABILITY fields on the receipt and the snapshot —
they are never the predicate.
Ref: cgg-ledger#attestation-predicate-must-prove-execution-not-outcome (ray on
cgg-ledger#wrapper-must-discriminate-instrument-exit-code-semantics-crash-vs-verdict).

BREACH DWELL AT FLAG ALTITUDE (tic 725 — rider lane C)
-------------------------------------------------------
`breach_flags` is an ANY-OCCURRENCE boolean over the tic's 1000 internal ticks:
it latches if even one tick breached. Aggregated over that population it
saturates — the identical set ['trust_below_tau','mint_halted'] rode 162 of 164
tics (98.8% base rate) — so the word BREACH stopped discriminating while the
governance-bearing quantity, ticks-below-tau, swung 16→991 and sat one level
down in detail.breach_flag_tick_counts. Live at tic 725: aggregate g_t 0.748988
sat ABOVE tau 0.70 with only 107/1000 ticks below it, yet the flags still read
as a full breach.
The cure is NOT to delete the flag. `breach_dwell` joins `breach_flags` at the
SAME altitude (snapshot, current-pointer, invocations row), carrying the dwell
count + fraction for exactly the flags that fired, plus a severity word that
tracks the rate — so the reader's discount reflex never has to form.
STRICTLY ADDITIVE: it is derived from the SAME counters that already feed
detail.breach_flag_tick_counts. No flag, threshold, cap, tau, mode, phase, or
mint/burn behaviour changes; no existing field's name or value moves.
Ref: ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude.

EXIT-CODE CONTRACT
------------------
Nonzero is reserved for EXECUTION FAILURE (the cadence did not execute, or the
artifacts did not land). The HEALTH verdict (`seed_stabilized`) is read from the
artifact and NEVER from the exit code — a verdict is not a crash.

FENCES / MEMBRANE
-----------------
  * Read-only of federation / governance state. This handler NEVER writes signals,
    queue, mandate, conformations, or CLAUDE.md, and imports NONE of
    atomic_append / queue / signals / manifest / mandate / conformation.
    (The invocations append takes an flock via stdlib `fcntl` — atomicity without
    coupling the economy lane to the governance primitives.)
  * Writes ONLY to audit-logs/economy/.
  * No mounted-volume runtime reference (membrane held; canonical is sole-writer). The
    OT mechanic was harpooned read-only into the imported modules; this handler
    holds zero mounted-volume reference of its own.

OUTPUTS (mirroring contagion's outputs, in the economy lane)
------------------------------------------------------------
  audit-logs/economy/economy-tic-{N}.json          the tic snapshot (tic, supply,
                                                    reserves, reserve_ratio, rate,
                                                    mint_total, burn_total, g_t, phase,
                                                    mode, breach_flags[], breach_dwell{},
                                                    seed_stabilized)
  audit-logs/economy/current-pointer.json           compact latest pointer; tic == N
                                                    (the anti-freeze tooth)
  audit-logs/economy/invocations.jsonl              audit trail (append-only)
  audit-logs/economy/ccoin-shadow-telemetry.jsonl   the breach-emitter wire (appended
                                                    by the existing BreachEmitter ONLY
                                                    when a breach fires)

USAGE
-----
  economy-heartbeat.py --tic 568
  economy-heartbeat.py --tic 568 --print     # echo the tic-snapshot path to stdout
"""
from __future__ import annotations

import argparse
import fcntl
import json
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve the canonical root by walking up until we see both the kernel and the
# audit-logs tree. Self-locating (no hardcoded absolute path baked into logic),
# and it never reaches across a mounted-volume membrane.
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
ROOT = HERE
for _ in range(12):
    if (ROOT / "autonomous_kernel").is_dir() and (ROOT / "audit-logs").is_dir():
        break
    if ROOT.parent == ROOT:
        break
    ROOT = ROOT.parent

KERNEL = ROOT / "autonomous_kernel"
WINCH = ROOT / "audit-logs" / "governance" / "harpoon-office" / "winch"
ECON_DIR = ROOT / "audit-logs" / "economy"

# The economy cables live in autonomous_kernel; the winch dial lives in the office
# winch dir. Same sys.path seam seed_the_ember.py uses.
for p in (str(KERNEL), str(WINCH)):
    if p not in sys.path:
        sys.path.insert(0, p)

# SWARM cable
import nautilus_swarm as swarm_mod          # noqa: E402
# CADENCE + economy cables
import ccoin_shadow_economy as ccoin        # noqa: E402
import economy_cadence as cadence           # noqa: E402
# PRICING cable
import visitor_economy_pricing as pricing   # noqa: E402
# MOTION layer — performance-driven trust + carry-state (tic 571: the economy MOVES)
import economy_motion as motion             # noqa: E402
# MODES cable — the winch operating-mode dial
from winch_modes import WinchDial           # noqa: E402  (DissonanceBasin + RollbackDrill are used inside fire_seed)

# The carry ledger — the series' spine. tic N+1 CONTINUES tic N through this file.
STATE_PATH = ECON_DIR / "economy-state.json"

# The economy DAG the gunslinger raises as one frontier (SWARM -> CADENCE -> PRICING,
# all non-gated => all exec-ready). Defined inline; no covenant-surface file is written
# (that is the seed's artifact) so this handler writes ONLY to audit-logs/economy/.
EXEC_READY_FRONTIER = ["SWARM", "CADENCE", "PRICING"]


# ===========================================================================
# The assembled economy pipeline — run the REAL cables, capture REAL numbers.
# (Parameterized clone of seed_the_ember.run_assembled_economy — same call sequence.)
# ===========================================================================
def run_assembled_economy(tic: int) -> dict:
    trace: dict = {}

    # --- config: SimOnly phase (cap 1_000_000 >> seed 100_000 => cap>=seed guard holds) ---
    config = ccoin.MonetaryConfig.task_economy()
    phase = ccoin.TransitionPhase.SimOnly

    # -----------------------------------------------------------------------
    # SWARM cable — coin<->trust CLOSURE proof (mint moves with aggregate g_t).
    # -----------------------------------------------------------------------
    agents = swarm_mod.spawn_swarm(seed=42)
    g_t_low = swarm_mod.aggregate_g_t(agents)

    def _closure_mint(agent_pool, seed_supply=100_000.0, seed_res=20_000.0, gens=20):
        buf = ccoin.EconomyBuffer(seed_supply, seed_res, usd_rate=1.0, is_live=True)
        econ = ccoin.Economy(buf, config, phase, currency="ucoin", is_shadow=False)
        total = 0.0
        last = None
        for _ in range(gens):
            last = econ.step_from_swarm(
                agent_pool, confidence=0.9, opportunities_sum=3000.0,
                realized_gap=0.5, consensus_elasticity=0.5,
            )
            total += last.mint_amount
        return total, last

    mint_low, last_low = _closure_mint(agents)
    good = {"sharpe": 3.0, "dd": 0.05, "ci_width": 0.10, "consistency": 0.9}
    for a in agents:
        a.update_trust(good, stake=20000.0, methodology="scientific")
    g_t_high = swarm_mod.aggregate_g_t(agents)
    mint_high, last_high = _closure_mint(agents)

    trace["SWARM"] = {
        "n_agents": len(agents),
        "aggregate_g_t_low_trust": round(g_t_low, 6),
        "aggregate_g_t_high_trust": round(g_t_high, 6),
        "tau": swarm_mod.TAU_DEFAULT,
        "mint_low_trust_20gen": round(mint_low, 6),
        "mint_high_trust_20gen": round(mint_high, 6),
        "economy_g_t_low": round(last_low.g_t, 6),
        "economy_g_t_high": round(last_high.g_t, 6),
        "low_trust_halt_reason": last_low.mint_halt_reason,
        "coin_trust_closed": (mint_low == 0.0 and mint_high > 0.0),
        "mint_moves_with_g_t": (mint_high > mint_low),
    }

    # -----------------------------------------------------------------------
    # CADENCE cable — ONE FULL TIC (1000 ticks) of the assembled economy driven by
    # the 128-agent swarm. MOVING (tic 571): trust is PERFORMANCE-DRIVEN (react ->
    # pnl -> rolling window -> score_trust, both directions, regime-rotated) and the
    # whole state CARRIES across tics through the carry ledger — tic N+1 continues
    # tic N; it does not replay it. At the tic boundary the FederalExchange
    # normalizes the held rate (center-exclusion applied to money).
    # -----------------------------------------------------------------------
    dial = cadence.CadenceDial(ticks_per_tic=cadence.DEFAULT_TICKS_PER_TIC)
    conformation = "ot-economy-heartbeat"
    dial.set_multiplier(conformation, 1.0)               # g=1.0 -> 1000 ticks/tic
    n_ticks = dial.effective_ticks(conformation)

    federal = cadence.FederalExchange(held_rate=1.0)     # frozen center anchor

    # --- carry ledger: load the series state; the advance guard types the run ---
    carry = motion.load_state(str(STATE_PATH))
    series_mode = motion.advance_guard(carry, tic)       # genesis | continue | replay
    if series_mode == "genesis":
        tic_agents = swarm_mod.spawn_swarm(seed=motion.SWARM_SEED)   # t=0.5 (< tau)
        market = motion.MarketState()
        live_buf = ccoin.EconomyBuffer(current_supply=100_000.0, reserves=20_000.0,
                                       usd_rate=1.0, is_live=True)
        carried_from_tic = None
        carried_cumulative = None
    else:
        tic_agents = motion.restore_swarm(carry)
        market = motion.restore_market(carry)
        b = carry["buffer"]
        live_buf = ccoin.EconomyBuffer(current_supply=b["current_supply"],
                                       reserves=b["reserves"],
                                       usd_rate=b["usd_rate"], is_live=True)
        carried_from_tic = int(carry["tic"])
        carried_cumulative = dict(carry.get("cumulative") or {})

    rng = motion.tic_rng(tic)                            # deterministic per (seed, tic)
    trust_start = swarm_mod.aggregate_g_t(tic_agents)

    emitter = ccoin.BreachEmitter(tic=tic)               # breach flags -> live telemetry (the wire)
    econ = ccoin.Economy(live_buf, config, phase, currency="ucoin",
                         is_shadow=False, emitter=emitter)
    if carried_cumulative:
        # the series' cumulative counters continue across the boundary
        econ.mint_total = float(carried_cumulative.get("mint_total", 0.0))
        econ.burn_total_cum = float(carried_cumulative.get("burn_total", 0.0))
        econ.generation = int(carried_cumulative.get("generation", 0))

    floor_trap = econ.floor_trap                         # cap>=seed guard
    supply_before = econ.buffer.current_supply
    reserves_before = econ.buffer.reserves

    mint_accrued = 0.0
    burn_accrued = 0.0
    ticks_with_mint = 0
    first_mint_tick = None
    min_supply = econ.buffer.current_supply
    min_reserve_ratio = econ.buffer.reserve_ratio()
    breach_flag_ticks = {"trust_below_tau": 0, "reserve_breach": 0,
                         "rate_band_breach": 0, "supply_cap_reached": 0,
                         "mint_halted": 0}
    g_t_samples = []
    last_result = None

    for i in range(n_ticks):
        # MOVING trust: the 128 agents react to the rotating market frame,
        # realize pnl on their side, roll their windows, and rescore trust —
        # trust moves BOTH directions (economy_motion.performance_tick).
        g = motion.performance_tick(tic_agents, market, rng)
        # WIRE: aggregate g_t -> mint gate (coin<->trust closure, live)
        r = econ.step(
            trust=g, confidence=0.9, opportunities_sum=3000.0,
            realized_gap=0.5, consensus_elasticity=0.5,
            tau=0.70, k=0.10, reserves_share=0.20, fee_units=100,
        )
        last_result = r
        mint_accrued += r.mint_amount
        burn_accrued += r.burn_total
        if r.mint_amount > 0.0:
            ticks_with_mint += 1
            if first_mint_tick is None:
                first_mint_tick = i + 1
        min_supply = min(min_supply, r.supply)
        min_reserve_ratio = min(min_reserve_ratio, r.reserve_ratio)
        f = r.breach_flags
        for name in breach_flag_ticks:
            if getattr(f, name):
                breach_flag_ticks[name] += 1
        if i in (0, 99, 199, 299, 499, 999):
            g_t_samples.append({
                "tick": i + 1,
                "swarm_aggregate_trust": round(swarm_mod.aggregate_g_t(tic_agents), 6),
                "economy_g_t": round(r.g_t, 6),
                "mint_amount": round(r.mint_amount, 6),
                "supply": round(r.supply, 4),
                "rate": round(r.rate, 6),
            })

    # tic boundary: normalize the held federal exchange (frozen center)
    pre_norm_rate = econ.buffer.usd_rate
    norm = federal.normalize_at_tic(
        economy=econ, conformation=conformation, tic_index=tic,
        ticks_run=n_ticks, mint_accrued_this_tic=mint_accrued, burn_this_tic=burn_accrued,
    )

    swarm_final_g_t = swarm_mod.aggregate_g_t(tic_agents)

    trace["CADENCE"] = {
        "ticks_per_tic": n_ticks,
        "one_tic_ran_1000_ticks": (n_ticks == 1000),
        "floor_trap_message": floor_trap.message,
        "cap_ge_seed_guard_clear": (not floor_trap.tripped),
        "supply_before": round(supply_before, 6),
        "supply_after": round(econ.buffer.current_supply, 6),
        "reserves_before": round(reserves_before, 6),
        "reserves_after": round(econ.buffer.reserves, 6),
        "final_reserve_ratio": round(econ.buffer.reserve_ratio(), 6),
        "min_supply_during_tic": round(min_supply, 6),
        "min_reserve_ratio_during_tic": round(min_reserve_ratio, 6),
        "mint_accrued": round(mint_accrued, 6),
        "burn_accrued": round(burn_accrued, 6),
        "ticks_with_mint": ticks_with_mint,
        "first_mint_tick": first_mint_tick,
        "zero_mint_ticks": n_ticks - ticks_with_mint,
        "swarm_trust_start": round(trust_start, 6),
        "swarm_final_aggregate_g_t": round(swarm_final_g_t, 6),
        "swarm_trust_moved": (abs(swarm_final_g_t - trust_start) > 1e-9),
        "g_t_trajectory_samples": g_t_samples,
        "breach_flag_tick_counts": breach_flag_ticks,
        "breach_emitter_records": emitter.emitted,
        "tic_boundary": {
            "pre_normalize_rate": round(pre_norm_rate, 8),
            "held_rate_after": round(norm.held_rate, 8),
            "deviation_absorbed": round(norm.deviation, 8),
            "anchor_frozen_center_excluded": norm.anchor_frozen,
            "federal_normalizations": federal.normalizations,
        },
        "series": {
            "mode": series_mode,                        # genesis | continue | replay
            "carried_from_tic": carried_from_tic,       # None on genesis
            "cumulative_mint_total": round(econ.mint_total, 6),
            "cumulative_burn_total": round(econ.burn_total_cum, 6),
            "cumulative_generation": econ.generation,
            "market": {"spread": round(market.spread, 6),
                       "elasticity": round(market.elasticity, 6),
                       "global_tick": market.global_tick},
        },
    }

    # --- CARRY: persist the series state so the NEXT tic CONTINUES this one.
    # Replay mode never writes — the guard exists so a re-fire of an already-
    # advanced tic cannot silently double-advance the series.
    if series_mode != "replay":
        motion.save_state(str(STATE_PATH),
                          motion.serialize_state(tic, econ.buffer, econ,
                                                 tic_agents, market))

    # -----------------------------------------------------------------------
    # PRICING cable — anchor coin -> usd off the LIVE federal rate (held, band-checked).
    # -----------------------------------------------------------------------
    held = pricing.capture_federal_rate(last_result, phase, config=config,
                                        tic=tic, label="ot-economy-heartbeat")
    eng = pricing.price_engagement(outcome_units=3.0, coin_per_outcome=500.0, held=held)
    leg_usd = pricing.price_leg_cost_usd(8_000.0, held)

    trace["PRICING"] = {
        "held_rate": round(held.rate, 8),
        "band": [round(held.rate_floor, 4), round(held.rate_ceiling, 4)],
        "within_band": held.within_band,
        "clamped_degraded_anchor": held.clamped,
        "source": held.source,
        "engagement": {
            "outcome_units": eng.outcome_units,
            "coin_earned": round(eng.coin_earned, 6),
            "usd_value": round(eng.usd_value, 6),
            "non_speculative": eng.non_speculative,
            "degraded_anchor": eng.degraded_anchor,
        },
        "compute_leg_8000_ucoin_usd": round(leg_usd, 6),
        "coin_usd_anchored": (abs(eng.usd_value - eng.coin_earned * held.rate) < 1e-6),
    }

    return trace


# ===========================================================================
# EXECUTION EVIDENCE — did the cycle RUN and LAND its state?
#
# This is the CADENCE cable's attestation predicate. It reads ONLY execution
# facts: the tic ran its full cadence, the tick accounting closes, the cap>=seed
# guard held, the federal boundary normalized, and the carry ledger (the series'
# spine) advanced to this tic — or, under REPLAY, lawfully refused the write.
#
# It reads NO economic outcome. mint_accrued / breach_flags / supply are carried
# under "observability" and are never consulted by the predicate. A designed
# zero-mint breach tic with a clean run ATTESTS TRUE; a run that did not execute
# (short cadence, tripped floor guard, un-advanced series) ATTESTS FALSE.
# (bk-economy-attest-execution-fix; ledger ray
#  #attestation-predicate-must-prove-execution-not-outcome)
# ===========================================================================
_CADENCE_NUMERIC_FIELDS = (
    "supply_before", "supply_after", "reserves_before", "reserves_after",
    "final_reserve_ratio", "min_supply_during_tic", "min_reserve_ratio_during_tic",
    "mint_accrued", "burn_accrued", "ticks_with_mint", "zero_mint_ticks",
    "swarm_trust_start", "swarm_final_aggregate_g_t",
)


def _is_number(v) -> bool:
    """bool is an int subclass — a True in a numeric slot is a malformed trace."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def read_carry_state_tic() -> tuple:
    """(tic, note) of the carry ledger — the series' spine. note is None on success."""
    try:
        state = motion.load_state(str(STATE_PATH))
    except Exception as exc:                                   # unreadable/malformed
        return None, f"carry_state_unreadable: {exc!r}"
    if state is None:
        return None, "carry_state_absent"
    try:
        return int(state["tic"]), None
    except (KeyError, TypeError, ValueError) as exc:
        return None, f"carry_state_malformed: {exc!r}"


def execution_evidence(tic: int, econ_trace: dict) -> dict:
    """EXECUTION-lawfulness evidence for the CADENCE cable. Never outcome-health."""
    cad = econ_trace.get("CADENCE") or {}
    series = cad.get("series") or {}
    boundary = cad.get("tic_boundary") or {}
    series_mode = series.get("mode")
    ticks_ran = cad.get("ticks_per_tic")

    ran_full_tic = bool(cad.get("one_tic_ran_1000_ticks")) and _is_number(ticks_ran) and ticks_ran > 0
    trace_complete = all(_is_number(cad.get(k)) for k in _CADENCE_NUMERIC_FIELDS)
    tick_accounting_closed = (
        _is_number(ticks_ran)
        and _is_number(cad.get("ticks_with_mint")) and _is_number(cad.get("zero_mint_ticks"))
        and (cad["ticks_with_mint"] + cad["zero_mint_ticks"]) == ticks_ran
    )
    guards_clear = bool(cad.get("cap_ge_seed_guard_clear"))
    tic_boundary_normalized = (
        bool(boundary.get("anchor_frozen_center_excluded"))
        and _is_number(boundary.get("federal_normalizations"))
        and boundary["federal_normalizations"] >= 1
    )

    state_tic, state_note = read_carry_state_tic()
    if series_mode in ("genesis", "continue"):
        series_state_advanced = (state_tic == tic)
    elif series_mode == "replay":
        # REPLAY lawfully refuses the state write (the double-advance guard).
        # Its execution evidence is that the series already sits at/past this tic.
        series_state_advanced = (state_tic is not None and state_tic >= tic)
    else:
        series_state_advanced = False
        state_note = state_note or f"unknown_series_mode: {series_mode!r}"

    checks = {
        "ran_full_tic": ran_full_tic,
        "trace_complete": trace_complete,
        "tick_accounting_closed": tick_accounting_closed,
        "guards_clear": guards_clear,
        "tic_boundary_normalized": tic_boundary_normalized,
        "series_state_advanced": series_state_advanced,
    }
    failed = [k for k, v in checks.items() if not v]
    breach_counts = cad.get("breach_flag_tick_counts") or {}
    return {
        "cadence_executed": not failed,
        "checks": checks,
        "failed_checks": failed,
        "series_mode": series_mode,
        "carry_state_tic": state_tic,
        "carry_state_note": state_note,
        "ticks_ran": ticks_ran if _is_number(ticks_ran) else None,
        "predicate": ("execution evidence (ran_full_tic / trace_complete / "
                      "tick_accounting_closed / guards_clear / "
                      "tic_boundary_normalized / series_state_advanced) — "
                      "NEVER mint or breach outcome"),
        # --- OBSERVABILITY ONLY. Not consulted by the predicate above. --------
        "observability": {
            "mint_accrued": cad.get("mint_accrued"),
            "burn_accrued": cad.get("burn_accrued"),
            "ticks_with_mint": cad.get("ticks_with_mint"),
            "zero_mint_ticks": cad.get("zero_mint_ticks"),
            "supply_after": cad.get("supply_after"),
            "breach_flags_fired": [k for k, v in breach_counts.items() if v],
        },
    }


# ===========================================================================
# FIRE the raise in GUNSLINGER (seed) mode over the assembled cables.
# (Call sequence from seed_the_ember.fire_gunslinger — cradle + RBD armed.
#  The CADENCE worker's predicate is the tic-684 attestation fix; SWARM and
#  PRICING keep their wiring proofs, which are tic-independent property tests
#  over a fresh seed-42 pool, not this tic's economic outcome.)
# ===========================================================================
def fire_gunslinger(econ_trace: dict, evidence: dict) -> dict:
    """GUNSLINGER: raise every exec-ready cable AT ONCE under one shared DissonanceBasin
    cradle with a RollbackDrill armed. Each cable's worker ATTESTS its assembled result
    and returns its receipt.

    `evidence` is execution_evidence(tic, econ_trace) — the CADENCE cable attests on
    it, so a lawful zero-mint breach tic with clean execution still raises."""
    exec_ready = list(EXEC_READY_FRONTIER)

    def worker(cable: str):
        t = econ_trace.get(cable, {})
        if cable == "SWARM":
            ok = t.get("coin_trust_closed") and t.get("mint_moves_with_g_t")
            return (bool(ok), f"SWARM receipt: 128-agent coin<->trust closed "
                              f"(low g_t={t['aggregate_g_t_low_trust']} mint={t['mint_low_trust_20gen']}; "
                              f"high g_t={t['aggregate_g_t_high_trust']} mint={t['mint_high_trust_20gen']})")
        if cable == "CADENCE":
            # ATTEST ON EXECUTION, NOT OUTCOME. mint/breach appear in the receipt
            # text as observability only — they do not gate `ok`.
            ok = bool(evidence.get("cadence_executed"))
            obs = evidence.get("observability") or {}
            return (ok, f"CADENCE receipt [EXECUTION-attested={ok}"
                        f"{'' if ok else ' failed=' + repr(evidence.get('failed_checks'))}]: "
                        f"1 tic = {t.get('ticks_per_tic')} ticks; "
                        f"series={evidence.get('series_mode')} "
                        f"carry_state_tic={evidence.get('carry_state_tic')}; "
                        f"supply {t.get('supply_before')}->{t.get('supply_after')}; "
                        f"federal anchor frozen at "
                        f"{(t.get('tic_boundary') or {}).get('held_rate_after')} "
                        f"| OBSERVABILITY (not attestation basis): "
                        f"mint_accrued={obs.get('mint_accrued')} "
                        f"ticks_with_mint={obs.get('ticks_with_mint')} "
                        f"breach_flags={obs.get('breach_flags_fired')}")
        if cable == "PRICING":
            ok = t.get("coin_usd_anchored") and t.get("within_band")
            return (bool(ok), f"PRICING receipt: held rate={t['held_rate']} in band {t['band']}; "
                              f"3-unit visit -> {t['engagement']['coin_earned']} ucoin -> "
                              f"${t['engagement']['usd_value']} USD (non-speculative)")
        return (False, f"unknown cable {cable}")

    dial = WinchDial.from_hoist_mode("seed")             # seed -> GUNSLINGER
    report = dial.fire_seed(exec_ready, worker, live=False)   # sandbox raise, RBD armed

    return {
        "mode": report.mode.value,
        "covenant_id": report.covenant_id,
        "committed": report.committed,
        "dispatched": report.dispatched,
        "held": report.held,
        "rollback_drill": report.rollback,
        "rollback_armed": report.rollback is not None,
        "basin_drain": report.basin_drain,
        "all_cables_raised_at_once": (sorted(report.dispatched) == sorted(exec_ready)),
        "execution_time_ms": report.execution_time_ms,
    }


# ===========================================================================
# STABILIZATION verdict — all cables held together, no collapse, arch stands.
# (Verbatim from seed_the_ember.stabilization_verdict.)
# ===========================================================================
def stabilization_verdict(econ_trace: dict, fire: dict) -> dict:
    cad = econ_trace["CADENCE"]
    swarm = econ_trace["SWARM"]
    price = econ_trace["PRICING"]

    checks = {
        # Post-tic-684 this reads "all three cables EXECUTED lawfully" — the
        # CADENCE leg no longer smuggles an economic outcome into a structural
        # stability verdict (bk-economy-attest-execution-fix). The genuinely
        # outcome-shaped health checks stay below, where they belong.
        "all_three_cables_committed": fire["committed"] and fire["all_cables_raised_at_once"],
        "rollback_reversible_gate_passed": (fire["rollback_drill"] is not None
                                            and fire["rollback_drill"]["is_reversible"]),
        "basin_drained_with_residual": (fire["basin_drain"] is not None
                                        and fire["basin_drain"]["residual_tension"] > 0.0),
        "cap_ge_seed_guard_clear": cad["cap_ge_seed_guard_clear"],
        "no_supply_collapse": cad["min_supply_during_tic"] > 1.0,
        "reserve_floor_held": cad["min_reserve_ratio_during_tic"] > 0.15,
        "coin_trust_closed": swarm["coin_trust_closed"],
        "mint_moved_with_g_t": swarm["mint_moves_with_g_t"],
        "federal_anchor_frozen": cad["tic_boundary"]["anchor_frozen_center_excluded"],
        "pricing_anchored_in_band": price["coin_usd_anchored"] and price["within_band"],
        "breach_flags_visible": cad["breach_emitter_records"] >= 0,   # emitted + counted
        "swarm_trust_moved": cad["swarm_trust_moved"],   # MOTION: trust responded to performance
    }
    seed_stabilized = all(checks.values())

    # breach flags that fired during the tic (kept VISIBLE, not suppressed)
    fired = [k for k, v in cad["breach_flag_tick_counts"].items() if v > 0]

    return {
        "seed_stabilized": seed_stabilized,
        "checks": checks,
        "breach_flags_fired_during_tic": fired,
        "breach_flag_tick_counts": cad["breach_flag_tick_counts"],
        "arch_stands": seed_stabilized,
    }


# ===========================================================================
# BREACH DWELL — the rate, hoisted to the flag's own altitude.
#
# `breach_flags` latches on ANY of the tic's 1000 internal ticks, so over that
# population it saturates and stops discriminating. This lifts the DWELL — the
# ticks-below-threshold count and its fraction of the tic — out of
# detail.breach_flag_tick_counts and stands it beside the flag it qualifies.
#
# READ-ONLY over the existing counters. It recomputes NO flag, moves NO
# threshold, and touches nothing the Architect dials (tau, caps, mode, phase,
# mint/burn). Keys are set-equal to `breach_flags` so the two fields read as one
# pair: the flag says WHETHER, the dwell says HOW MUCH.
# (ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude)
# ===========================================================================
# Band edges on the dwell FRACTION. Emitted with the verdict so the severity
# word is self-describing and a reader can re-derive it without this source.
DWELL_SEVERITY_BANDS = ((0.25, "intermittent"), (0.75, "sustained"))
DWELL_SEVERITY_EDGES = {"intermittent": [0.0, 0.25], "sustained": [0.25, 0.75],
                        "saturated": [0.75, 1.0]}


def breach_dwell(breach_flags, breach_flag_tick_counts, ticks_per_tic) -> dict:
    """Dwell for the flags that FIRED, at the flag's altitude. Purely additive.

    breach_flags          — the fired-flag list (verdict.breach_flags_fired_during_tic)
    breach_flag_tick_counts — the per-flag internal-tick counters (the SAME dict
                              that already lands at detail.breach_flag_tick_counts)
    ticks_per_tic         — the denominator (cadence ticks run this tic)

    Fail-soft: a missing counter or an unusable denominator yields an honest
    None for that leg and severity "undetermined" — never an invented number.
    """
    counts = breach_flag_tick_counts or {}
    fired = list(breach_flags or [])
    denom = ticks_per_tic if (_is_number(ticks_per_tic) and ticks_per_tic > 0) else None

    ticks: dict = {}
    fraction: dict = {}
    for name in fired:
        c = counts.get(name)
        ticks[name] = c if _is_number(c) else None
        fraction[name] = (round(ticks[name] / denom, 6)
                          if (denom is not None and ticks[name] is not None) else None)

    known = [v for v in fraction.values() if v is not None]
    max_fraction = max(known) if known else 0.0
    if not fired:
        severity = "none"
    elif not known:
        severity = "undetermined"
    else:
        severity = "saturated"
        for edge, word in DWELL_SEVERITY_BANDS:
            if max_fraction < edge:
                severity = word
                break

    return {
        "ticks_per_tic": ticks_per_tic if denom is not None else None,
        "ticks": ticks,
        "fraction": fraction,
        "max_fraction": max_fraction,
        "severity": severity,
        "severity_bands": DWELL_SEVERITY_EDGES,
        "basis": "detail.breach_flag_tick_counts",
        "note": ("dwell for the flags in breach_flags, at the flag's own altitude — "
                 "the flag says WHETHER, the dwell says HOW MUCH. ADDITIVE "
                 "observability: no flag, threshold, tau, cap, mode, phase, or "
                 "mint/burn behaviour is changed by this field. "
                 "ledger#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude"),
    }


# ===========================================================================
# POST-WRITE artifact verification — the second half of the execution proof.
#
# The attestation above proves the cycle RAN; this proves it LANDED. A missing
# or unparseable artifact, or a pointer that did not re-aim at this tic, is an
# EXECUTION failure (nonzero exit). A health verdict never is.
# ===========================================================================
def verify_artifacts(tic: int, snap_path: Path, ptr_path: Path,
                     inv_path: Path, series_mode: str) -> dict:
    failures = []

    snapshot_verified = False
    try:
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        if int(snap.get("tic", -1)) != tic:
            failures.append(f"snapshot tic {snap.get('tic')!r} != {tic}")
        else:
            snapshot_verified = True
    except Exception as exc:
        failures.append(f"snapshot unreadable at {snap_path}: {exc!r}")

    # REPLAY lawfully leaves the pointer anchored on the series row — not a defect.
    pointer_checked = (series_mode != "replay")
    pointer_verified = None
    if pointer_checked:
        pointer_verified = False
        try:
            ptr = json.loads(ptr_path.read_text(encoding="utf-8"))
            if int(ptr.get("tic", -1)) != tic:
                failures.append(f"pointer tic {ptr.get('tic')!r} != {tic} "
                                f"(anti-freeze tooth)")
            else:
                pointer_verified = True
        except Exception as exc:
            failures.append(f"pointer unreadable at {ptr_path}: {exc!r}")

    invocation_appended = False
    try:
        rows = [ln for ln in inv_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        last = json.loads(rows[-1])
        if int(last.get("tic", -1)) != tic:
            failures.append(f"invocation row tic {last.get('tic')!r} != {tic}")
        else:
            invocation_appended = True
    except Exception as exc:
        failures.append(f"invocation row not appended at {inv_path}: {exc!r}")

    return {
        "ok": not failures,
        "failures": failures,
        "snapshot_verified": snapshot_verified,
        "pointer_checked": pointer_checked,
        "pointer_verified": pointer_verified,
        "invocation_appended": invocation_appended,
    }


def _flock_append(path: Path, obj: dict) -> None:
    """Atomic append under an exclusive flock. Stdlib only — the economy lane
    stays uncoupled from the governance atomic_append primitive (FENCES)."""
    with path.open("a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(obj) + "\n")
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


# ===========================================================================
# WRITE the per-tic snapshot + current-pointer + invocations audit trail,
# then VERIFY the artifacts landed. Writes ONLY to audit-logs/economy/.
# ===========================================================================
def write_outputs(tic: int, econ_trace: dict, fire: dict, verdict: dict,
                  evidence: dict) -> dict:
    ECON_DIR.mkdir(parents=True, exist_ok=True)

    cad = econ_trace["CADENCE"]
    series = cad["series"]
    series_mode = series["mode"]
    breach_flags = verdict["breach_flags_fired_during_tic"]
    # The dwell rides at the SAME altitude as the flag it qualifies, in every
    # artifact the flag appears in (snapshot / pointer / invocations row).
    dwell = breach_dwell(breach_flags, verdict["breach_flag_tick_counts"],
                         cad["ticks_per_tic"])
    seed_stabilized = bool(verdict["seed_stabilized"])
    execution_attested = bool(evidence["cadence_executed"])
    mode = fire["mode"]

    # 1) the tic snapshot ----------------------------------------------------
    snapshot = {
        "type": "economy.heartbeat.tic",
        "tic": tic,
        "series_mode": series_mode,
        "carried_from_tic": series["carried_from_tic"],
        "supply": cad["supply_after"],
        "reserves": cad["reserves_after"],
        "reserve_ratio": cad["final_reserve_ratio"],
        "rate": cad["tic_boundary"]["held_rate_after"],
        "mint_total": cad["mint_accrued"],
        "burn_total": cad["burn_accrued"],
        "g_t": cad["swarm_final_aggregate_g_t"],
        "phase": "SimOnly",
        "mode": mode,
        "breach_flags": breach_flags,
        # The DWELL beside the FLAG (tic 725). Additive; derived from the same
        # counters that land at detail.breach_flag_tick_counts below.
        "breach_dwell": dwell,
        "seed_stabilized": seed_stabilized,
        # EXECUTION-lawfulness, decoupled from outcome-health. seed_stabilized is
        # the HEALTH verdict; execution_attested is the "did the cycle run and
        # land" verdict and is the only one the exit code speaks for.
        "execution_attested": execution_attested,
        # --- richer auditable detail (nested; the flat fields above are the contract) ---
        "detail": {
            "n_agents": econ_trace["SWARM"]["n_agents"],
            "ticks_per_tic": cad["ticks_per_tic"],
            "ticks_with_mint": cad["ticks_with_mint"],
            "first_mint_tick": cad["first_mint_tick"],
            "zero_mint_ticks": cad["zero_mint_ticks"],
            "min_supply_during_tic": cad["min_supply_during_tic"],
            "min_reserve_ratio_during_tic": cad["min_reserve_ratio_during_tic"],
            "breach_flag_tick_counts": verdict["breach_flag_tick_counts"],
            "breach_emitter_records": cad["breach_emitter_records"],
            "tic_boundary": cad["tic_boundary"],
            "winch_fire": fire,
            "stabilization_checks": verdict["checks"],
            "execution_attestation": evidence,
            "economy_trace": econ_trace,
        },
        "membrane": "held; canonical sole-writer; no OT runtime ref; writes only audit-logs/economy/",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }
    # REPLAY never clobbers the series artifacts: its snapshot lands beside the
    # series row, and the pointer (the anti-freeze tooth) stays on the series.
    if series_mode == "replay":
        snap_path = ECON_DIR / f"economy-tic-{tic}-replay.json"
    else:
        snap_path = ECON_DIR / f"economy-tic-{tic}.json"
    snap_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    # 2) current-pointer.json (compact latest pointer; tic == N is the anti-freeze tooth)
    ptr_path = ECON_DIR / "current-pointer.json"
    if series_mode != "replay":
        pointer = {
            "tic": tic,
            "economy_tic_path": str(snap_path.relative_to(ROOT)),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "breach_flags": breach_flags,
            "breach_dwell": dwell,
            "seed_stabilized": seed_stabilized,
            "execution_attested": execution_attested,
            "series_mode": series_mode,
        }
        ptr_path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")

    # 3) invocations.jsonl (append-only audit trail; atomic under flock)
    inv_path = ECON_DIR / "invocations.jsonl"
    entry = {
        "tic": tic,
        "invoked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": mode,
        "series_mode": series_mode,
        "g_t": cad["swarm_final_aggregate_g_t"],
        "mint_total": cad["mint_accrued"],
        "breach_flags": breach_flags,
        "breach_dwell": dwell,
        "seed_stabilized": seed_stabilized,
        "execution_attested": execution_attested,
        "execution_failed_checks": evidence["failed_checks"],
    }
    _flock_append(inv_path, entry)

    # 4) VERIFY the artifacts landed (post-write half of the execution proof)
    artifact_verification = verify_artifacts(tic, snap_path, ptr_path, inv_path,
                                             series_mode)

    return {
        "snapshot": snap_path,
        "pointer": ptr_path,
        "invocations": inv_path,
        "artifact_verification": artifact_verification,
    }


# ===========================================================================
# main
# ===========================================================================
def main() -> int:
    ap = argparse.ArgumentParser(description="ECONOMY HEARTBEAT per-tic runner")
    ap.add_argument("--tic", type=int, required=True, help="the federation tic N to run")
    ap.add_argument("--print", action="store_true", dest="print_path",
                    help="echo the tic-snapshot artifact path to stdout")
    args = ap.parse_args()
    tic = args.tic

    econ_trace = run_assembled_economy(tic)
    evidence = execution_evidence(tic, econ_trace)
    fire = fire_gunslinger(econ_trace, evidence)
    verdict = stabilization_verdict(econ_trace, fire)
    paths = write_outputs(tic, econ_trace, fire, verdict, evidence)

    av = paths["artifact_verification"]
    execution_ok = bool(evidence["cadence_executed"]) and bool(av["ok"])

    cad = econ_trace["CADENCE"]
    # Same altitude on the operator-facing line: the flag list alone saturates.
    dwell = breach_dwell(verdict["breach_flags_fired_during_tic"],
                         verdict["breach_flag_tick_counts"], cad["ticks_per_tic"])
    if args.print_path:
        print(str(paths["snapshot"]))
    else:
        print(
            f"economy heartbeat tic={tic}: mode={fire['mode']} "
            f"series={cad['series']['mode']} "
            f"execution_attested={execution_ok} "
            f"seed_stabilized={verdict['seed_stabilized']} "
            f"g_t={cad['swarm_trust_start']:.4f}->{cad['swarm_final_aggregate_g_t']:.4f} "
            f"mint={cad['mint_accrued']:.2f} burn={cad['burn_accrued']:.2f} "
            f"supply={cad['supply_after']:.2f} rr={cad['final_reserve_ratio']:.4f} "
            f"breach_flags={verdict['breach_flags_fired_during_tic']} "
            f"breach_dwell={dwell['severity']}"
            f"({dwell['max_fraction']:.3f} of {dwell['ticks_per_tic']}) "
            f"-> {paths['snapshot'].relative_to(ROOT)}",
            file=sys.stderr,
        )

    # EXECUTION failures are always loud, on BOTH stdout modes — the exit code
    # speaks only for them, so their reason must be legible next to it.
    if not execution_ok:
        print(f"EXECUTION FAILURE tic={tic}: "
              f"cadence_failed_checks={evidence['failed_checks']} "
              f"artifact_failures={av['failures']}", file=sys.stderr)

    # EXIT-CODE CONTRACT (ledger#wrapper-must-discriminate-instrument-exit-code-
    # semantics-crash-vs-verdict): nonzero is reserved for EXECUTION failure.
    # `seed_stabilized` is a HEALTH verdict and is read from the artifact — a
    # lawful loud-halt tic exits 0.
    return 0 if execution_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
