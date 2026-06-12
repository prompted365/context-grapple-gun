"""conductance_assembler.py — the conductance ASSEMBLER (β, /review 401).

The missing seam the harmony-wiring arena named: between the (cartography-rung)
terrain-physics conductance PRODUCER and harmony-input-builder's `terrainSlice`
contract. Replaces the 4 hand-painted conductance literals (masked by the
engine's `?? 0.5`) with real, provenance-tagged readings assembled from
cartography.

Architecture (honors the /review 401 orphanhood law — wire to the TRUE producer,
not a fake socket):

    real substrate signals (manifold stats, physics flag)
        → cartography deriveConductance()  [γ, the producer — terrain physics]
        → THIS assembler maps to the {acoustic, light, gravity, social} contract
        → harmony-input-builder.terrainSlice.conductance

Cross-rung invocation mirrors harmony-invoke.sh → harmony-engine.mjs: a
synchronous `node` subprocess call to the cartography runner, NOT authority
delegation. Fail-soft: if node/cartography is unavailable, fall back to the
authored literals with provenance `authored_literal_stub_no_producer` so the
/review 401 authored-not-measured canary still fires honestly.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

# The authored fallback — identical to the prior inline stub. Used only when the
# cartography producer cannot be reached; provenance makes the fallback honest.
_AUTHORED_BANDS = {"acoustic": 0.72, "light": 0.58, "gravity": 1, "social": 0.46}
_AUTHORED_PROVENANCE = {b: "authored" for b in _AUTHORED_BANDS}

_CARTOGRAPHY_RUNNER_REL = "autonomous_kernel/cartography/runtime/cartography-emit.mjs"
_ACTOR_REGISTRY_REL = "autonomous_kernel/actor-registry.json"

# Lifecycle/standing values that count an actor as part of the LIVE economy.
_ACTIVE_LIFECYCLES = {"active", "mature", "operational", "live", "promoted"}
_MATURE_LIFECYCLES = {"mature", "operational", "promoted"}


def _read_entity_economy(repo_root: Path) -> Optional[dict[str, Any]]:
    """Real entity-economy signal for the SOCIAL band — actor-registry census.

    Returns {actorCount, activeCount, matureCount} or None if unreadable. A
    livelier, more-mature citizen registry carries social rays further; this
    grows with the federation (genuinely tic-varying over time).
    """
    reg = Path(repo_root) / _ACTOR_REGISTRY_REL
    if not reg.exists():
        return None
    try:
        actors = (json.loads(reg.read_text()).get("actors")) or []
    except Exception:
        return None
    if not isinstance(actors, list) or not actors:
        return None
    active = mature = 0
    for a in actors:
        if not isinstance(a, dict):
            continue
        lc = str(a.get("lifecycle", "")).lower()
        st = str(a.get("status", "")).lower()
        standing = str(a.get("standing", "")).lower()
        if lc in _ACTIVE_LIFECYCLES or st in _ACTIVE_LIFECYCLES or standing in {"citizen", "primary", "resident"}:
            active += 1
        if lc in _MATURE_LIFECYCLES or standing in {"citizen", "primary"}:
            mature += 1
    return {"actorCount": len(actors), "activeCount": active, "matureCount": mature}


def _authored_fallback(reason: str) -> dict[str, Any]:
    return {
        "conductance": dict(_AUTHORED_BANDS),
        "conductanceProvenance": dict(_AUTHORED_PROVENANCE),
        "conductanceSource": "authored_literal_stub_no_producer",
        "measuredBandCount": 0,
        "consumedBandCount": 3,
        "measuredConsumedCount": 0,
        "fullyMeasured": False,
        "assemblerFallbackReason": reason,
    }


def assemble_conductance(
    manifold_stats: Optional[dict[str, Any]],
    repo_root: Path,
    *,
    observability: Optional[dict[str, Any]] = None,
    physics_runtime_active: Optional[bool] = None,
    timeout_s: float = 8.0,
) -> dict[str, Any]:
    """Assemble terrain.conductance from the cartography producer.

    Returns a dict with `conductance` (the {acoustic,light,gravity,social} band
    map), `conductanceProvenance` (per-band measured|authored), `conductanceSource`,
    and `measuredBandCount`/`fullyMeasured`. Never raises — degrades to the
    authored fallback (canary stays honest).
    """
    node = shutil.which("node")
    if not node:
        return _authored_fallback("node_not_on_path")

    runner = Path(repo_root) / _CARTOGRAPHY_RUNNER_REL
    if not runner.exists():
        return _authored_fallback(f"cartography_runner_absent:{runner}")

    # Build the cartography input.substrate from REAL signals. Only include a
    # band's source when it genuinely exists — absent sources stay authored,
    # per-band, inside cartography (no invented proxies).
    substrate: dict[str, Any] = {}
    # acoustic — signal-manifold liveness.
    if isinstance(manifold_stats, dict) and isinstance(
        manifold_stats.get("volume_mean"), (int, float)
    ):
        substrate["manifold"] = {
            "volume_mean": manifold_stats.get("volume_mean"),
            "active_signal_count": manifold_stats.get("active_signal_count", 0),
            "volume_entropy": manifold_stats.get("volume_entropy"),
        }
    # light — observability-surface liveness (conformation recency), supplied by
    # the caller which holds the conformation + current tic.
    if (
        isinstance(observability, dict)
        and isinstance(observability.get("latestConformationTic"), int)
        and isinstance(observability.get("currentTic"), int)
    ):
        substrate["observability"] = {
            "latestConformationTic": observability["latestConformationTic"],
            "currentTic": observability["currentTic"],
        }
    # social — entity-economy maturity (actor-registry census), read here.
    econ = _read_entity_economy(repo_root)
    if econ:
        substrate["entityEconomy"] = econ
    # gravity — intentionally NOT supplied: dead field (engine short-circuits it).
    if isinstance(physics_runtime_active, bool):
        substrate["physicsRuntimeActive"] = physics_runtime_active

    payload = json.dumps({"source": "conductance_assembler", "substrate": substrate})

    try:
        proc = subprocess.run(
            [node, str(runner)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return _authored_fallback("cartography_timeout")
    except Exception as exc:  # pragma: no cover - defensive
        return _authored_fallback(f"cartography_invoke_error:{type(exc).__name__}")

    if proc.returncode != 0:
        return _authored_fallback(f"cartography_nonzero_exit:{proc.returncode}")

    try:
        out = json.loads(proc.stdout)
        readings = out.get("conductanceReadings") or {}
        bands = readings.get("bands")
        provenance = readings.get("provenance")
        if not isinstance(bands, dict) or not isinstance(provenance, dict):
            return _authored_fallback("cartography_missing_conductanceReadings")
    except Exception:
        return _authored_fallback("cartography_unparseable_output")

    measured = int(readings.get("measuredBandCount", 0) or 0)
    return {
        "conductance": bands,
        "conductanceProvenance": provenance,
        "conductanceSource": readings.get("source", "cartography_conductance_v0"),
        "measuredBandCount": measured,
        "consumedBandCount": int(readings.get("consumedBandCount", 3) or 3),
        "measuredConsumedCount": int(readings.get("measuredConsumedCount", 0) or 0),
        "fullyMeasured": bool(readings.get("fullyMeasured", False)),
        "assemblerFallbackReason": None,
    }
