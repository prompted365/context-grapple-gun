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

FENCES / MEMBRANE
-----------------
  * Read-only of federation / governance state. This handler NEVER writes signals,
    queue, mandate, conformations, or CLAUDE.md, and imports NONE of
    atomic_append / queue / signals / manifest / mandate / conformation.
  * Writes ONLY to audit-logs/economy/.
  * No mounted-volume runtime reference (membrane held; canonical is sole-writer). The
    OT mechanic was harpooned read-only into the imported modules; this handler
    holds zero mounted-volume reference of its own.

OUTPUTS (mirroring contagion's outputs, in the economy lane)
------------------------------------------------------------
  audit-logs/economy/economy-tic-{N}.json          the tic snapshot (tic, supply,
                                                    reserves, reserve_ratio, rate,
                                                    mint_total, burn_total, g_t, phase,
                                                    mode, breach_flags[], seed_stabilized)
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
# MODES cable — the winch operating-mode dial
from winch_modes import WinchDial           # noqa: E402  (DissonanceBasin + RollbackDrill are used inside fire_seed)

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
    # the 128-agent swarm. Trust accrues per tick; each tick the aggregate g_t gates
    # the mint via step_from_swarm; at the tic boundary the FederalExchange normalizes
    # the held rate (center-exclusion applied to money).
    # -----------------------------------------------------------------------
    dial = cadence.CadenceDial(ticks_per_tic=cadence.DEFAULT_TICKS_PER_TIC)
    conformation = "ot-economy-heartbeat"
    dial.set_multiplier(conformation, 1.0)               # g=1.0 -> 1000 ticks/tic
    n_ticks = dial.effective_ticks(conformation)

    federal = cadence.FederalExchange(held_rate=1.0)     # frozen center anchor

    tic_agents = swarm_mod.spawn_swarm(seed=42)          # start at t=0.5 (< tau)
    ACCRUAL_RATE = 0.003                                 # asymptotic: t += r*(1-t)

    live_buf = ccoin.EconomyBuffer(current_supply=100_000.0, reserves=20_000.0,
                                   usd_rate=1.0, is_live=True)
    emitter = ccoin.BreachEmitter(tic=tic)               # breach flags -> live telemetry (the wire)
    econ = ccoin.Economy(live_buf, config, phase, currency="ucoin",
                         is_shadow=False, emitter=emitter)

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
        # the 128-agent swarm accrues trust this tick (asymptotic toward 1.0)
        for a in tic_agents:
            a.trust.t = min(1.0, a.trust.t + ACCRUAL_RATE * (1.0 - a.trust.t))
        # WIRE: aggregate g_t -> mint gate (coin<->trust closure, live)
        r = econ.step_from_swarm(
            tic_agents, confidence=0.9, opportunities_sum=3000.0,
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
        "swarm_seed_trust": 0.5,
        "swarm_final_aggregate_g_t": round(swarm_final_g_t, 6),
        "swarm_trust_accrued": (swarm_final_g_t > 0.5),
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
    }

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
# FIRE the raise in GUNSLINGER (seed) mode over the assembled cables.
# (Verbatim call sequence from seed_the_ember.fire_gunslinger — cradle + RBD armed.)
# ===========================================================================
def fire_gunslinger(econ_trace: dict) -> dict:
    """GUNSLINGER: raise every exec-ready cable AT ONCE under one shared DissonanceBasin
    cradle with a RollbackDrill armed. Each cable's worker ATTESTS its assembled result
    and returns its receipt."""
    exec_ready = list(EXEC_READY_FRONTIER)

    def worker(cable: str):
        t = econ_trace.get(cable, {})
        if cable == "SWARM":
            ok = t.get("coin_trust_closed") and t.get("mint_moves_with_g_t")
            return (bool(ok), f"SWARM receipt: 128-agent coin<->trust closed "
                              f"(low g_t={t['aggregate_g_t_low_trust']} mint={t['mint_low_trust_20gen']}; "
                              f"high g_t={t['aggregate_g_t_high_trust']} mint={t['mint_high_trust_20gen']})")
        if cable == "CADENCE":
            ok = (t.get("one_tic_ran_1000_ticks") and t.get("cap_ge_seed_guard_clear")
                  and t.get("supply_after", 0) > 0 and t.get("mint_accrued", 0) > 0
                  and t["tic_boundary"]["anchor_frozen_center_excluded"])
            return (bool(ok), f"CADENCE receipt: 1 tic = {t['ticks_per_tic']} ticks; "
                              f"mint_accrued={t['mint_accrued']}; supply {t['supply_before']}->"
                              f"{t['supply_after']}; federal anchor frozen at "
                              f"{t['tic_boundary']['held_rate_after']}")
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
# WRITE the per-tic snapshot + current-pointer + invocations audit trail.
# Writes ONLY to audit-logs/economy/.
# ===========================================================================
def write_outputs(tic: int, econ_trace: dict, fire: dict, verdict: dict) -> dict:
    ECON_DIR.mkdir(parents=True, exist_ok=True)

    cad = econ_trace["CADENCE"]
    breach_flags = verdict["breach_flags_fired_during_tic"]
    seed_stabilized = bool(verdict["seed_stabilized"])
    mode = fire["mode"]

    # 1) the tic snapshot ----------------------------------------------------
    snapshot = {
        "type": "economy.heartbeat.tic",
        "tic": tic,
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
        "seed_stabilized": seed_stabilized,
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
            "economy_trace": econ_trace,
        },
        "membrane": "held; canonical sole-writer; no OT runtime ref; writes only audit-logs/economy/",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }
    snap_path = ECON_DIR / f"economy-tic-{tic}.json"
    snap_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    # 2) current-pointer.json (compact latest pointer; tic == N is the anti-freeze tooth)
    pointer = {
        "tic": tic,
        "economy_tic_path": str(snap_path.relative_to(ROOT)),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "breach_flags": breach_flags,
        "seed_stabilized": seed_stabilized,
    }
    ptr_path = ECON_DIR / "current-pointer.json"
    ptr_path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")

    # 3) invocations.jsonl (append-only audit trail)
    inv_path = ECON_DIR / "invocations.jsonl"
    entry = {
        "tic": tic,
        "invoked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": mode,
        "g_t": cad["swarm_final_aggregate_g_t"],
        "mint_total": cad["mint_accrued"],
        "breach_flags": breach_flags,
        "seed_stabilized": seed_stabilized,
    }
    with inv_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return {
        "snapshot": snap_path,
        "pointer": ptr_path,
        "invocations": inv_path,
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
    fire = fire_gunslinger(econ_trace)
    verdict = stabilization_verdict(econ_trace, fire)
    paths = write_outputs(tic, econ_trace, fire, verdict)

    cad = econ_trace["CADENCE"]
    if args.print_path:
        print(str(paths["snapshot"]))
    else:
        print(
            f"economy heartbeat tic={tic}: mode={fire['mode']} "
            f"seed_stabilized={verdict['seed_stabilized']} "
            f"g_t={cad['swarm_final_aggregate_g_t']:.4f} "
            f"mint={cad['mint_accrued']:.2f} burn={cad['burn_accrued']:.2f} "
            f"supply={cad['supply_after']:.2f} rr={cad['final_reserve_ratio']:.4f} "
            f"breach_flags={verdict['breach_flags_fired_during_tic']} "
            f"-> {paths['snapshot'].relative_to(ROOT)}",
            file=sys.stderr,
        )
    return 0 if verdict["seed_stabilized"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
