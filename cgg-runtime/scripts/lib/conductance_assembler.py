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


def _authored_fallback(reason: str) -> dict[str, Any]:
    return {
        "conductance": dict(_AUTHORED_BANDS),
        "conductanceProvenance": dict(_AUTHORED_PROVENANCE),
        "conductanceSource": "authored_literal_stub_no_producer",
        "measuredBandCount": 0,
        "fullyMeasured": False,
        "assemblerFallbackReason": reason,
    }


def assemble_conductance(
    manifold_stats: Optional[dict[str, Any]],
    repo_root: Path,
    *,
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
    if isinstance(manifold_stats, dict) and isinstance(
        manifold_stats.get("volume_mean"), (int, float)
    ):
        substrate["manifold"] = {
            "volume_mean": manifold_stats.get("volume_mean"),
            "active_signal_count": manifold_stats.get("active_signal_count", 0),
            "volume_entropy": manifold_stats.get("volume_entropy"),
        }
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
        "fullyMeasured": bool(readings.get("fullyMeasured", False)),
        "assemblerFallbackReason": None,
    }
