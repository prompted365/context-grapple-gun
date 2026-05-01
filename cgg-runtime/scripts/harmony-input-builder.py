#!/usr/bin/env python3
"""
harmony-input-builder.py — Federation-state → Harmony input envelope.

Assembles a HarmonyEngine v0 input packet from live federation state without
truncating salient rays nor flooding her context window. The envelope honors
the engine's documented input schema and grounds the disposition in the
terrain Harmony actually hears against:

  - scene census          (terrain witness — what is counted)
  - conformation snapshot (signals + warrants + CPR pipeline at this tic)
  - tic counter           (federation clock)
  - posture + mode        (Primary's current stance, theory-of-mind aware)
  - enrichment_eligible CPRs (decision-ready rays — not the full 77 pending)

The bound is principled: rays = active signals + active warrants +
enrichment_eligible CPRs (the federation's live, salient state). All other
classes are upstream of the docket gate and would flood Harmony's hearing
without sharpening her disposition.

Output: audit-logs/harmony/input-tic-{N}.json

Read-only of federation state; never writes governance surfaces.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = pathlib.Path("/Users/breydentaylor/canonical")

CONFORMATION_DIR = REPO_ROOT / "audit-logs" / "conformations"
QUEUE_FILE = REPO_ROOT / "audit-logs" / "cprs" / "queue.jsonl"
SCENE_CENSUS = (
    REPO_ROOT
    / "audit-logs"
    / "agent-mailboxes"
    / "ent_homeskillet"
    / "inbound"
    / "scene-census-tic-197.json"
)
TIC_COUNTER = pathlib.Path.home() / ".claude" / "cgg-tic-counter.json"
HARMONY_DIR = REPO_ROOT / "audit-logs" / "harmony"

CHUNK_TEXT_MAX = 600  # per-chunk text cap (preserves intent without flooding)
TOP_SUBSYSTEMS = 12   # match fixture cardinality


def read_json(path: pathlib.Path) -> Any:
    with open(path) as f:
        return json.load(f)


def latest_conformation() -> dict[str, Any]:
    files = sorted(CONFORMATION_DIR.glob("tic-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit("no conformation snapshots in audit-logs/conformations/")
    return read_json(files[0])


def current_tic() -> int:
    if TIC_COUNTER.exists():
        try:
            data = read_json(TIC_COUNTER)
            # canonical counter file uses "count"; legacy variant used "counter"
            return int(data.get("count") or data.get("counter") or 0)
        except Exception:
            pass
    # fall back to latest conformation
    conf = latest_conformation()
    return int(conf.get("tic_count_physical") or 0)


def latest_status_per_id(queue_path: pathlib.Path) -> dict[str, dict[str, Any]]:
    """Return {id: latest_record} from the JSONL queue (latest-wins per id)."""
    seen: dict[str, dict[str, Any]] = {}
    if not queue_path.exists():
        return seen
    with open(queue_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            cid = rec.get("id") or rec.get("cogpr_id")
            if cid:
                seen[cid] = rec
    return seen


def build_chunk_from_signal(sig: dict[str, Any]) -> dict[str, Any]:
    """A signal becomes a returnedChunk anchored at a council-pole centroid."""
    band = (sig.get("band") or "COGNITIVE").upper()
    kind = (sig.get("kind") or "WATCH").upper()
    sid = sig.get("id") or "sig_unknown"
    vol = int(sig.get("volume") or 0)
    status = sig.get("status") or "active"
    # Map COGNITIVE→ACOUSTIC band (closest in engine band policy)
    band_hint = {
        "COGNITIVE": "ACOUSTIC",
        "PRIMITIVE": "GRAVITY",
        "SOCIAL": "SOCIAL",
    }.get(band, "ACOUSTIC")
    text = (
        f"Signal {sid} carries band={band} kind={kind} volume={vol} status={status}. "
        f"This is a federation-active signal in the manifold; Harmony must hear it as a "
        f"live ray against its source-band centroid without flattening it into a count."
    )[:CHUNK_TEXT_MAX]
    return {
        "chunkId": f"signal.{sid}",
        "source": "council",
        "text": text,
        "sourceCentroid": {
            "centroidId": f"centroid.signal.{band.lower()}",
            "rung": "council",
            "label": f"Signal Manifold ({band})",
            "embedding": embed_band_kind(band, kind, vol),
            "collapseZones": ["count flatten", "premature dismissal", "severity drift"],
            "siblingOverlaps": ["warrant", "CPR pipeline", "manifold posture"],
        },
        "provenance": {"sourceId": "audit-logs/conformations", "tic": int(sig.get("tic", 0) or 0)},
        "signalKindHint": kind if kind in {"BEACON", "LESSON", "TENSION", "OPPORTUNITY", "BOUNDARY", "REPAIR", "REFUSAL"} else "TENSION",
        "bandHint": band_hint,
        "relayDepth": 1,
    }


def build_chunk_from_warrant(wrn: dict[str, Any]) -> dict[str, Any]:
    wid = wrn.get("id") or "wrn_unknown"
    band = (wrn.get("band") or "COGNITIVE").upper()
    text = (
        f"Warrant {wid} (band={band}) is active and demands governance action. "
        f"Harmony must preserve its boundary character; it is not a lesson, it is an obligation."
    )[:CHUNK_TEXT_MAX]
    return {
        "chunkId": f"warrant.{wid}",
        "source": "council",
        "text": text,
        "sourceCentroid": {
            "centroidId": f"centroid.warrant.{band.lower()}",
            "rung": "federation",
            "label": f"Active Warrant ({band})",
            "embedding": embed_band_kind(band, "BOUNDARY", 100),
            "collapseZones": ["lesson absorption", "delay drift"],
            "siblingOverlaps": ["signal", "review docket"],
        },
        "provenance": {"sourceId": "audit-logs/conformations", "tic": 0},
        "signalKindHint": "BOUNDARY",
        "bandHint": "GRAVITY",
        "relayDepth": 1,
    }


def build_chunk_from_cpr(c: dict[str, Any], queue_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cid = c.get("id") or "cpr_unknown"
    lesson = (c.get("lesson") or "").strip()
    rec = queue_lookup.get(cid, {})
    if not lesson:
        lesson = (rec.get("lesson") or "").strip()
    band = (c.get("band") or rec.get("band") or "COGNITIVE").upper()
    subsystem = c.get("subsystem") or rec.get("subsystem") or ""
    text = (
        lesson if lesson else f"Pending CPR {cid} (band={band}) awaiting /review judgment."
    )[:CHUNK_TEXT_MAX]
    return {
        "chunkId": f"cpr.{cid}",
        "source": "council",
        "text": text,
        "sourceCentroid": {
            "centroidId": f"centroid.cpr.{band.lower()}",
            "rung": "federation",
            "label": f"Decision-Ready CPR ({band})" + (f" — {subsystem}" if subsystem else ""),
            "embedding": embed_band_kind(band, "LESSON", 50),
            "collapseZones": ["batch flatten", "premature promotion", "convergence smoothing"],
            "siblingOverlaps": ["doctrine", "MEMORY.md", "promoted lessons"],
        },
        "provenance": {"sourceId": "audit-logs/cprs/queue.jsonl", "tic": 0},
        "signalKindHint": "LESSON",
        "bandHint": "ACOUSTIC",
        "relayDepth": 2,
    }


def embed_band_kind(band: str, kind: str, weight: int) -> list[float]:
    """8-dim deterministic embedding seeded by band/kind/weight."""
    seed = f"{band}:{kind}:{weight}"
    h = hashlib.sha256(seed.encode()).digest()
    out = []
    for i in range(8):
        # signed normalized [-1, 1]
        b = h[i]
        out.append(((b / 255.0) * 2 - 1))
    # normalize
    mag = (sum(x * x for x in out)) ** 0.5 or 1.0
    return [round(x / mag, 4) for x in out]


def build_terrain_slice(census: dict[str, Any], tic: int, posture: str, mode: str) -> dict[str, Any]:
    totals = census.get("totals", {})
    subsystems = census.get("subsystems") or []
    # subsystems may be a list of dicts or a dict; normalize
    if isinstance(subsystems, dict):
        subs_list = [{"name": k, **(v if isinstance(v, dict) else {"objectCount": int(v or 0)})} for k, v in subsystems.items()]
    else:
        subs_list = subsystems
    # rank by objectCount desc
    subs_list = sorted(subs_list, key=lambda s: int(s.get("objectCount", 0) or 0), reverse=True)
    top = subs_list[:TOP_SUBSYSTEMS]
    # carry whatever fields exist
    top_subsystems = [
        {
            "name": s.get("name", "(unnamed)"),
            "objectCount": int(s.get("objectCount", 0) or 0),
            "meshCount": int(s.get("meshCount", 0) or 0),
            "instanceCount": int(s.get("instanceCount", 0) or 0),
            "lightCount": int(s.get("lightCount", 0) or 0),
            "triangleEstimate": int(s.get("triangleEstimate", 0) or 0),
            "lineSegmentCount": int(s.get("lineSegmentCount", 0) or 0),
        }
        for s in top
    ]
    # conductance: derived (substrate has physics_runtime since tic 202)
    conductance = {
        "acoustic": 0.72,  # signal manifold breathing
        "light": 0.58,     # observability surfaces
        "gravity": 1,      # physics runtime active
        "social": 0.46,    # visitor economy mature
    }
    # pressureHints: subsystem names (Harmony searches for these substrings in chunks)
    pressure_hints = [s["name"] for s in top_subsystems if s.get("name")]
    # digest: stable hash over census + tic
    digest_src = json.dumps({"totals": totals, "tic": tic}, sort_keys=True).encode()
    digest = "sha256:" + hashlib.sha256(digest_src).hexdigest()
    return {
        "terrainDigest": digest,
        "tic": tic,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "mode": f"{posture}/{mode}",
        "totals": totals,
        "topSubsystems": top_subsystems,
        "conductance": conductance,
        "pressureHints": pressure_hints,
    }


def build_council_pressure(conf: dict[str, Any]) -> list[dict[str, Any]]:
    sigs = conf.get("active_signals", []) or []
    wrns = conf.get("active_warrants", []) or []
    poles: list[dict[str, Any]] = []
    if sigs:
        max_vol = max(int(s.get("volume", 0) or 0) for s in sigs) or 1
        poles.append({
            "poleId": "council.manifold_active",
            "poleName": "Active Manifold",
            "pressure": round(max_vol / 100.0, 2),
            "direction": "strains" if max_vol > 30 else "holds",
        })
    if wrns:
        poles.append({
            "poleId": "council.warrants_open",
            "poleName": "Open Warrants",
            "pressure": min(1.0, len(wrns) * 0.25),
            "direction": "demands",
        })
    # decision-ready CPR pressure
    cprs = conf.get("pending_cogprs", []) or []
    eligible = [c for c in cprs if c.get("status") == "enrichment_eligible"]
    if eligible:
        poles.append({
            "poleId": "council.cpr_docket",
            "poleName": "Decision-Ready CPRs",
            "pressure": min(1.0, len(eligible) / 30.0),
            "direction": "awaits",
        })
    if not poles:
        poles.append({
            "poleId": "council.federation_quiet",
            "poleName": "Federation Quiet",
            "pressure": 0.1,
            "direction": "holds",
        })
    return poles


def build_returned_chunks(conf: dict[str, Any], queue_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for sig in conf.get("active_signals", []) or []:
        chunks.append(build_chunk_from_signal(sig))
    for wrn in conf.get("active_warrants", []) or []:
        chunks.append(build_chunk_from_warrant(wrn))
    for c in conf.get("pending_cogprs", []) or []:
        if c.get("status") == "enrichment_eligible":
            chunks.append(build_chunk_from_cpr(c, queue_lookup))
    return chunks


def build_envelope(posture: str, mode: str) -> dict[str, Any]:
    conf = latest_conformation()
    tic = current_tic()
    queue_lookup = latest_status_per_id(QUEUE_FILE)
    census = read_json(SCENE_CENSUS)

    primary_centroid_embedding = embed_band_kind("COGNITIVE", "BEACON", 100)
    primary_context = {
        "contextId": f"ctx.harmony.tic{tic}.{posture.replace('/', '_')}.{mode}",
        "question": (
            f"At tic {tic} under posture {posture} and mode {mode}, what is the "
            f"federation's disposition? Harmony must sign the meaning the terrain "
            f"carries — preserve rays, do not adjudicate."
        ),
        "currentGoal": (
            f"Surface a Primary-facing disposition that orients without verdict; "
            f"theory-of-mind injection rather than count rollup."
        ),
        "primaryCentroid": {
            "centroidId": f"centroid.primary.tic{tic}",
            "rung": "federation",
            "label": "Federation Primary at Tic " + str(tic),
            "embedding": primary_centroid_embedding,
            "collapseZones": ["count rollup", "premature verdict", "operator preference smoothing", "metric flatten"],
            "siblingOverlaps": ["arena synthesis", "review docket", "cadence handoff", "MEMORY tail"],
        },
        "activeCouncilPoles": [
            "meaning_integrity",
            "rollback_velocity",
            "telos_beauty",
            "encounter_quality",
        ],
        "receiverWorld": "operator-architect Breyden building Telos/Ubiquity federation under physics runtime",
    }

    receiver_register = {
        "registerId": f"receiver.primary.{posture.replace('/', '_').lower()}",
        "preferredBands": _bands_for_posture(posture),
        "toleranceForDissonance": _tolerance_for_mode(mode),
        "trustSensitivity": 0.88,
        "boundarySensitivity": 0.91,
        "semanticVocabulary": [
            "Harmony", "disposition", "ray", "centroid", "rung",
            "telos", "substrate", "terrain", "ecotone", "boundary",
            "rollback", "physics", "heritage", "meaning", "manifold",
            "federation", "tic",
        ],
    }

    envelope = {
        "primaryContext": primary_context,
        "terrainSlice": build_terrain_slice(census, tic, posture, mode),
        "councilPressureHints": build_council_pressure(conf),
        "receiverRegister": receiver_register,
        "returnedChunks": build_returned_chunks(conf, queue_lookup),
    }
    return envelope


def _bands_for_posture(posture: str) -> list[str]:
    p = posture.upper()
    if p.startswith("OPS/DIRECT"):
        return ["GRAVITY", "ACOUSTIC", "LIGHT"]
    if p.startswith("OPS/META"):
        return ["LIGHT", "ACOUSTIC"]
    if p.startswith("ENG/DIRECT"):
        return ["ACOUSTIC", "GRAVITY"]
    if p.startswith("ENG/META"):
        return ["LIGHT", "ACOUSTIC", "SOCIAL"]
    return ["ACOUSTIC", "LIGHT"]


def _tolerance_for_mode(mode: str) -> float:
    return {"OFF": 0.5, "LITE": 0.65, "FULL": 0.80}.get(mode.upper(), 0.72)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--posture", default=os.environ.get("CGG_POSTURE", "OPS/DIRECT"))
    ap.add_argument("--mode", default=os.environ.get("CGG_STATUSLINE_MODE", "FULL"))
    ap.add_argument("--output-dir", default=str(HARMONY_DIR))
    ap.add_argument("--print", action="store_true", help="print path of written input on success")
    args = ap.parse_args()

    HARMONY_DIR.mkdir(parents=True, exist_ok=True)

    envelope = build_envelope(args.posture, args.mode)
    tic = envelope["terrainSlice"]["tic"]
    out_path = pathlib.Path(args.output_dir) / f"input-tic-{tic}.json"
    with open(out_path, "w") as f:
        json.dump(envelope, f, indent=2)
    if args.print:
        print(out_path)
    else:
        print(
            f"input written: {out_path}\n"
            f"  tic={tic} posture={args.posture} mode={args.mode}\n"
            f"  rays={len(envelope['returnedChunks'])} council_poles={len(envelope['councilPressureHints'])}\n"
            f"  terrain_subsystems={len(envelope['terrainSlice']['topSubsystems'])}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
