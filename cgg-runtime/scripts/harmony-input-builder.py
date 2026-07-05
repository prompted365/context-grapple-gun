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
import math
import os
import pathlib
import subprocess
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root  # noqa: E402
from lib.conductance_assembler import assemble_conductance  # noqa: E402


def _resolve_repo_root() -> pathlib.Path:
    """Resolve REPO_ROOT under federation marker-aware discipline.

    Priority chain (per /review tic 284 Verdict C refinement):
      1. CGG_REPO_ROOT env override — explicit fixture / test escape hatch
      2. Marker-aware zone resolution via zone_root.resolve_zone_root() —
         honors CLAUDE_PROJECT_DIR, walks up for .ticzone, falls back to
         git rev-parse, then cwd-with-warning
      3. Hardcoded canonical default — backward-compatible final fallback
         (reached only if zone_root resolution raises; should not normally fire
         since resolve_zone_root has its own cwd-fallback path)
    """
    env_override = os.environ.get("CGG_REPO_ROOT")
    if env_override:
        return pathlib.Path(env_override)
    try:
        return pathlib.Path(resolve_zone_root())
    except Exception:
        return pathlib.Path("/Users/breydentaylor/canonical")


REPO_ROOT = _resolve_repo_root()

CONFORMATION_DIR = REPO_ROOT / "audit-logs" / "conformations"
QUEUE_FILE = REPO_ROOT / "audit-logs" / "cprs" / "queue.jsonl"
BRAID_DIR = REPO_ROOT / "audit-logs" / "braid"
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
RTCH_PACKETS_DIR = REPO_ROOT / "audit-logs" / "rtch" / "packets"

CHUNK_TEXT_MAX = 600  # per-chunk text cap (preserves intent without flooding)
TOP_SUBSYSTEMS = 12   # match fixture cardinality
# RTCH packet ingestion — bounds (Ship 2 of three-layer terrain proposal tic 223)
RTCH_PACKET_LIMIT = 12         # cap of fresh packets ingested per build (prevents flood)
RTCH_STUB_LIMIT = 24           # cap of historical_packet_stub entries surfaced per build
RTCH_DEFAULT_TTL_TICS = 30     # fallback if packet lacks ttl_tics field


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


def load_rtch_packets(current_tic_value: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read RTCH packets from audit-logs/rtch/packets/, partition into
    (fresh, expired) per packet's ttl_tics + expires_at_tic.

    Fresh packets carry decay_weight in (0.0, 1.0]. Expired packets carry
    decay_weight = 0.0 and become historical_packet_stub chunks per
    three-layer terrain doctrine (Ship 2 of tic-223 proposal):
      - Layer 1 verbatim retention (the file stays at audit-logs/rtch/packets/)
      - Layer 3 hot-path force = 0
      - Layer 2 stub pointer with current_claim_force=none

    Per binder §12.7: skipped/truncated surfaces must surface, not hide.
    """
    fresh: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    if not RTCH_PACKETS_DIR.is_dir():
        return fresh, expired
    for p in sorted(RTCH_PACKETS_DIR.glob("rtch_packet_*.json")):
        try:
            with open(p) as f:
                pkt = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        generated = int(pkt.get("generated_at_tic") or 0)
        ttl = int(pkt.get("ttl_tics") or RTCH_DEFAULT_TTL_TICS)
        expires = int(pkt.get("expires_at_tic") or (generated + ttl))
        remaining = expires - current_tic_value
        if remaining <= 0:
            pkt["_decay_weight"] = 0.0
            pkt["_age_tics"] = max(0, current_tic_value - generated)
            pkt["_packet_path"] = str(p)
            expired.append(pkt)
        else:
            decay_weight = max(0.0, min(1.0, remaining / ttl)) if ttl > 0 else 0.0
            pkt["_decay_weight"] = decay_weight
            pkt["_age_tics"] = max(0, current_tic_value - generated)
            pkt["_packet_path"] = str(p)
            fresh.append(pkt)
    # Order fresh by decay_weight desc (freshest first); expired by age asc (most recent first)
    fresh.sort(key=lambda x: x.get("_decay_weight", 0.0), reverse=True)
    expired.sort(key=lambda x: x.get("_age_tics", 0))
    return fresh, expired


def build_chunk_from_rtch_packet(pkt: dict[str, Any]) -> dict[str, Any]:
    """A fresh RTCH packet becomes a returnedChunk anchored at the
    rtch.discovery centroid. Pressure scales with TTL decay_weight.

    Per three-layer terrain doctrine: Layer 3 hot-path eligibility is
    decay_weight in (0, 1]; Layer 1 verbatim packet at packet_path is
    untouched.
    """
    pid = pkt.get("packet_id") or "rtch_unknown"
    decay = float(pkt.get("_decay_weight", 1.0))
    age = int(pkt.get("_age_tics", 0))
    intake = pkt.get("intake", {}) or {}
    goal = (intake.get("goal") or "")[:140]
    profile = intake.get("target_profile", "?")
    fanout = intake.get("fanout_level", "?")
    selected = pkt.get("selected_surfaces", []) or []
    halting = pkt.get("halting_reason", "?")
    unresolved_n = len(pkt.get("unresolved_questions", []) or [])
    chunks_n = len(pkt.get("hydrated_chunks", []) or [])
    text = (
        f"RTCH packet {pid} (age {age}t, decay_weight {decay:.2f}). "
        f"Intake goal: {goal} (profile={profile}, fanout={fanout}). "
        f"Selected {len(selected)} surfaces; {chunks_n} hydrated chunks; "
        f"{unresolved_n} unresolved questions; halted on {halting}. "
        f"Layer-3 hot-path force scales with decay_weight."
    )[:CHUNK_TEXT_MAX]
    # Signal-kind heuristic: discovery freshness reads as LESSON when high,
    # REPAIR when faded (still useful but acknowledging staleness)
    kind = "LESSON" if decay > 0.5 else "REPAIR"
    return {
        "chunkId": f"rtch.{pid}",
        "source": "council",
        "text": text,
        "sourceCentroid": {
            "centroidId": "centroid.rtch.discovery",
            "rung": "federation",
            "label": "Tactical Hydration Discovery",
            "embedding": embed_band_kind("COGNITIVE", kind, int(decay * 100)),
            "collapseZones": [
                "discovery vs packaging confusion",
                "stale evidence read as current",
                "doctrine claim from grep alone",
            ],
            "siblingOverlaps": ["signal", "CPR pipeline", "/consolidate handoff"],
        },
        "provenance": {
            "sourceId": pkt.get("_packet_path", f"audit-logs/rtch/packets/{pid}.json"),
            "tic": int(pkt.get("generated_at_tic") or 0),
        },
        "signalKindHint": kind,
        "bandHint": "ACOUSTIC",
        "relayDepth": 2,
        # Three-layer terrain extension fields (Ship 2 of tic-223 proposal):
        "chunkType": "tactical_hydration_packet",
        "decayWeight": decay,
        "ttlState": "active" if decay >= 0.66 else "aging" if decay > 0.0 else "expired",
        "currentClaimForce": "allowed_if_source_bearing",
        "expiresAtTic": int(pkt.get("expires_at_tic") or 0),
        "selectedSurfaceCount": len(selected),
    }


def build_chunk_from_expired_rtch_packet(pkt: dict[str, Any]) -> dict[str, Any]:
    """An expired RTCH packet becomes a historical_packet_stub chunk.

    Per three-layer terrain doctrine: Layer 1 verbatim retention is
    invariant (packet file stays at packet_path); Layer 3 hot-path force
    = 0 (pressure 0, no claim weight); Layer 2 stub pointer with
    current_claim_force=none. Harmony sees the stub but cannot weigh it
    as current evidence. Rehydration (Ship 4) is the bridge back.
    """
    pid = pkt.get("packet_id") or "rtch_unknown"
    age = int(pkt.get("_age_tics", 0))
    expires = int(pkt.get("expires_at_tic") or 0)
    generated = int(pkt.get("generated_at_tic") or 0)
    text = (
        f"Historical packet stub {pid} (generated tic {generated}, expired tic {expires}, "
        f"age {age}t). Layer 1 verbatim preserved at {pkt.get('_packet_path','?')}. "
        f"Layer 3 hot-path force = 0 (current_claim_force=none). Allowed uses: lineage, "
        f"route memory, drift comparison, rehydration candidate. NOT a current claim."
    )[:CHUNK_TEXT_MAX]
    return {
        "chunkId": f"rtch_stub.{pid}",
        "source": "council",
        "text": text,
        "sourceCentroid": {
            "centroidId": "centroid.rtch.historical",
            "rung": "federation",
            "label": "Historical Packet Stub",
            "embedding": embed_band_kind("COGNITIVE", "REPAIR", 0),
            "collapseZones": [
                "expired packet read as current",
                "stub treated as claim",
                "Layer 1 deletion on Layer 3 expiry",
            ],
            "siblingOverlaps": ["past slice", "route memory", "drift comparison"],
        },
        "provenance": {
            "sourceId": pkt.get("_packet_path", f"audit-logs/rtch/packets/{pid}.json"),
            "tic": generated,
        },
        "signalKindHint": "REPAIR",
        "bandHint": "ACOUSTIC",
        "relayDepth": 3,
        # Three-layer terrain extension fields (Ship 2 of tic-223 proposal):
        "chunkType": "historical_packet_stub",
        "decayWeight": 0.0,
        "ttlState": "expired_requires_rehydration",
        "currentClaimForce": "none",
        "expiresAtTic": expires,
        "allowedUses": ["lineage", "route_memory", "drift_comparison", "rehydration_candidate"],
        "blockedUses": ["current_truth", "doctrine_claim", "harmony_hot_path_weight"],
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


def load_braid_packet(braid_dir: pathlib.Path | None = None) -> dict[str, Any] | None:
    """Load the current braid packet via audit-logs/braid/current-pointer.json.

    Cable BR5 (braid covenant tic 569). FAIL-SOFT: any absent/corrupt surface
    returns None and the builder behaves EXACTLY as it did before the braid
    existed (content survives expression failure — Volatility Handling KI).
    Read-only; never writes the braid surface.
    """
    d = braid_dir if braid_dir is not None else BRAID_DIR
    try:
        pointer = read_json(d / "current-pointer.json")
        rel = pointer.get("braid_packet_path")
        if not rel:
            return None
        pkt_path = REPO_ROOT / rel if not str(rel).startswith("/") else pathlib.Path(rel)
        if braid_dir is not None and not str(rel).startswith("/"):
            # fixture dirs resolve relative to themselves when the pointer names
            # a bare filename (selftest hermeticity); repo-relative paths keep
            # the live behavior.
            candidate = d / pathlib.Path(rel).name
            if candidate.exists():
                pkt_path = candidate
        pkt = read_json(pkt_path)
        if not isinstance(pkt, dict) or pkt.get("type") != "lattice.braid.tic":
            return None
        return pkt
    except Exception:
        return None


# Shared collapse zones for all braid-derived chunks (SPEC §BR5.1): the three
# ways a braid ray dies — quoted as command (non-citable pressure only),
# read as warnings alone (wisdom overall, the covenant's founding directive),
# collapsed to argmax (mixture-of-models, never classification).
BRAID_COLLAPSE_ZONES = ["quoted-as-command", "warning-only-read", "argmax collapse"]


def build_chunks_from_braid(braid_packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Braid packet → up to 3 returnedChunks (SPEC §BR5.1).

    (a) wisdom-pressure chunk — ACOUSTIC; LESSON when wisdom-dominant,
        TENSION when caution-dominant.
    (b) traversal chunk — GRAVITY; BOUNDARY only at route_advisory=="near_ponr",
        else TENSION.
    (c) trajectory chunk — LIGHT; BEACON on steady trajectory, TENSION when
        jerk flags fire or trust velocity turns negative.

    All texts are OBSERVATIONAL (non-imperative — same guard family as
    aesop_archetype_field._IMPERATIVE_RE): the braid shapes, it never
    instructs. Chunks carry provenance to the braid packet file.
    """
    chunks: list[dict[str, Any]] = []
    tic = int(braid_packet.get("tic") or 0)
    provenance_id = f"audit-logs/braid/braid-tic-{tic}.json"

    af = braid_packet.get("archetype_field") or {}
    wp = braid_packet.get("wisdom_pressure") or {}
    tp = braid_packet.get("traversal_physics") or {}
    traj = braid_packet.get("trajectory") or {}

    wisdom_mass = float(af.get("wisdom_mass") or 0.0)
    caution_mass = float(af.get("caution_mass") or 0.0)
    dominant = af.get("dominant") or {}
    route = str(tp.get("route_advisory") or "unknown")

    # (a) wisdom-pressure chunk
    wisdom_dominant = wisdom_mass > caution_mass
    kind_a = "LESSON" if wisdom_dominant else "TENSION"
    hint = wp.get("wisdom_hydration_hint") or wp.get("failure_mode_inverse")
    if not hint:
        hint = (
            "No archetype prior carries meaningful weight at this conformation; "
            "the field reads as unfamiliar terrain."
        )
    moral = dominant.get("moral") or ""
    fable = dominant.get("fable") or ""
    text_a = (
        f"Braid wisdom-pressure at tic {tic}: {hint} "
        + (f"Nearest working centroid: '{fable}' — {moral} " if moral else "")
        + f"The grade ahead reads {route}. Wisdom mass {wisdom_mass:.4f}, "
        f"caution mass {caution_mass:.4f} — a mixture reading, not a verdict."
    )[:CHUNK_TEXT_MAX]
    chunks.append({
        "chunkId": f"braid.wisdom.{tic}",
        "source": "council",
        "text": text_a,
        "sourceCentroid": {
            "centroidId": "centroid.braid.wisdom_pressure",
            "rung": "council",
            "label": "Braid Wisdom Pressure",
            "embedding": embed_band_kind("BRAID", kind_a, int(caution_mass * 100)),
            "collapseZones": list(BRAID_COLLAPSE_ZONES),
            "siblingOverlaps": ["signal manifold", "harmony disposition", "economy heartbeat"],
        },
        "provenance": {"sourceId": provenance_id, "tic": tic},
        "signalKindHint": kind_a,
        "bandHint": "ACOUSTIC",
        "relayDepth": 2,
    })

    # (b) traversal chunk
    kind_b = "BOUNDARY" if route == "near_ponr" else "TENSION"
    barrier = (tp.get("barrier_cost") or {})
    nearest = barrier.get("nearest_ponr") or {}
    text_b = (
        f"Braid traversal physics at tic {tic}: route advisory {route}; "
        f"barrier cost {barrier.get('value', 'n/a')} "
        f"(elevation {tp.get('elevation', 'n/a')}). Nearest point of no return: "
        f"'{nearest.get('id', 'none')}' on axis {nearest.get('axis', 'n/a')} at "
        f"distance {nearest.get('distance_to_ponr', 'n/a')}. Traversal grows "
        f"costlier as that distance closes — the terrain is speaking, not a rule."
    )[:CHUNK_TEXT_MAX]
    chunks.append({
        "chunkId": f"braid.traversal.{tic}",
        "source": "council",
        "text": text_b,
        "sourceCentroid": {
            "centroidId": "centroid.braid.traversal",
            "rung": "council",
            "label": "Braid Traversal Physics",
            "embedding": embed_band_kind("BRAID", kind_b, int(float(barrier.get("value") or 0.0))),
            "collapseZones": list(BRAID_COLLAPSE_ZONES),
            "siblingOverlaps": ["gravity wells", "economy breach flags", "substrate projection"],
        },
        "provenance": {"sourceId": provenance_id, "tic": tic},
        "signalKindHint": kind_b,
        "bandHint": "GRAVITY",
        "relayDepth": 2,
    })

    # (c) trajectory chunk
    jerk_flags = list(traj.get("jerk_flags") or [])
    tick = traj.get("tick_scale") or {}
    trust_d1 = ((tick.get("trust") or {}).get("d1"))
    trust_sign = (
        "rising" if isinstance(trust_d1, (int, float)) and trust_d1 > 0
        else "falling" if isinstance(trust_d1, (int, float)) and trust_d1 < 0
        else "flat-or-unread"
    )
    kind_c = "TENSION" if (jerk_flags or trust_sign == "falling") else "BEACON"
    text_c = (
        f"Braid trajectory at tic {tic}: trust velocity reads {trust_sign}"
        + (f" (d1={trust_d1})" if isinstance(trust_d1, (int, float)) else "")
        + (
            f"; jerk flags fired: {', '.join(jerk_flags[:4])}."
            if jerk_flags
            else "; no jerk flags — the derivatives sit inside their calibrated bands."
        )
        + " Scalars here are projections; the trajectory object is the record."
    )[:CHUNK_TEXT_MAX]
    chunks.append({
        "chunkId": f"braid.trajectory.{tic}",
        "source": "council",
        "text": text_c,
        "sourceCentroid": {
            "centroidId": "centroid.braid.trajectory",
            "rung": "council",
            "label": "Braid Trajectory Field",
            "embedding": embed_band_kind("BRAID", kind_c, len(jerk_flags)),
            "collapseZones": list(BRAID_COLLAPSE_ZONES),
            "siblingOverlaps": ["economy cadence", "tick/tic dial", "conformation history"],
        },
        "provenance": {"sourceId": provenance_id, "tic": tic},
        "signalKindHint": kind_c,
        "bandHint": "LIGHT",
        "relayDepth": 2,
    })

    return chunks


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


def build_terrain_slice(census: dict[str, Any], tic: int, posture: str, mode: str,
                        conductance_result: dict[str, Any] | None = None) -> dict[str, Any]:
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
    # conductance: assembled by the conductance ASSEMBLER (β, /review 401) from
    # the cartography terrain-physics producer (γ, deriveConductance). Per-band
    # provenance is honest (measured varies with real substrate state; authored =
    # no producer yet). When the producer is unreachable it degrades to the
    # authored literals and the authored-not-measured canary fires (/review 401 KI).
    if conductance_result and isinstance(conductance_result.get("conductance"), dict):
        conductance = conductance_result["conductance"]
        conductance_provenance = conductance_result.get("conductanceProvenance") or {}
        conductance_source = conductance_result.get("conductanceSource", "cartography_conductance_v0")
        measured = int(conductance_result.get("measuredBandCount", 0) or 0)
    else:
        # No assembler result supplied (e.g. direct call) — honest authored fallback.
        conductance = {"acoustic": 0.72, "light": 0.58, "gravity": 1, "social": 0.46}
        conductance_provenance = {b: "authored" for b in conductance}
        conductance_source = "authored_literal_stub_no_producer"
        measured = 0
    # authored-not-measured canary (/review 401 KI): fires for genuinely-`authored`
    # CONSUMED bands (a `?? const` over a field doctrine treats as measured must
    # confess). `authored_unconsumed` (gravity — engine short-circuits it) is a
    # dead field, expected, NOT an alarm. Per-band provenance rides terrainSlice.
    if conductance_result:
        measured_consumed = int(conductance_result.get("measuredConsumedCount", measured) or 0)
        consumed_total = int(conductance_result.get("consumedBandCount", 3) or 3)
    else:
        measured_consumed, consumed_total = 0, 3
    pending_bands = [b for b, p in conductance_provenance.items() if p == "authored"]
    if pending_bands:
        print(
            "⚠ harmony canary: terrain.conductance has UNMEASURED consumed bands "
            f"{pending_bands} — no producer yet; engine ?? 0.5 masks absence. "
            f"source={conductance_source}, measured={measured_consumed}/{consumed_total} consumed. "
            "(KI authored-not-measured-canary, /review 401)",
            file=sys.stderr,
        )
    else:
        print(
            f"✓ harmony: all {consumed_total} consumed conductance bands measured "
            f"({measured_consumed}/{consumed_total}; gravity is a dead field, authored). "
            f"source={conductance_source}",
            file=sys.stderr,
        )
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
        "conductanceProvenance": conductance_provenance,
        "conductanceSource": conductance_source,
        "pressureHints": pressure_hints,
    }


def build_manifold_active(sigs: list[dict[str, Any]], cur_tic: int) -> dict[str, Any]:
    """Shape-bearing manifold_active object (P2 spec, tic 228 closeout).

    Replaces input-boundary collapse where pressure = max(volumes)/100 was
    Harmony's only reading of the active signal manifold. Emits the 12
    required minimum fields. pressure_scalar_compat is preserved for
    back-compat consumers but MUST NOT be the only field downstream reads.

    Spec: audit-logs/governance/p2-harmony-manifold-input-patch-handoff-tic228.md
    """
    if not sigs:
        return {
            "active_signal_count": 0,
            "unique_signal_count": 0,
            "volume_max": 0,
            "volume_sum": 0,
            "volume_mean": 0.0,
            "volume_entropy": 0.0,
            "volume_gini": 0.0,
            "cluster_count": 0,
            "oldest_active_age_tics": 0,
            "newest_active_age_tics": 0,
            "recurrence_count": 0,
            "pressure_scalar_compat": 0.0,
        }

    volumes = [int(s.get("volume", 0) or 0) for s in sigs]
    ids = [s.get("id") for s in sigs if s.get("id")]
    clusters = {(s.get("band") or "?", s.get("kind") or "?") for s in sigs}

    vol_sum = sum(volumes)
    vol_max = max(volumes)
    vol_mean = vol_sum / len(volumes)

    # Shannon entropy over normalized volume distribution (nats).
    entropy = 0.0
    if vol_sum > 0:
        for v in volumes:
            if v > 0:
                p = v / vol_sum
                entropy -= p * math.log(p)

    # Gini coefficient over volumes (0 = perfect equality).
    gini = 0.0
    if vol_sum > 0:
        sorted_vols = sorted(volumes)
        n = len(sorted_vols)
        cumulative = sum((i + 1) * v for i, v in enumerate(sorted_vols))
        gini = (2 * cumulative) / (n * vol_sum) - (n + 1) / n

    # Age: signals carry a 'tic' field on emit; conformation copies may omit it.
    # Skip rather than fabricate when the source is silent.
    ages = [
        max(0, cur_tic - int(s.get("tic", 0) or 0))
        for s in sigs
        if int(s.get("tic", 0) or 0) > 0 and cur_tic > 0
    ]
    oldest = max(ages) if ages else 0
    newest = min(ages) if ages else 0

    # Recurrence: prefer per-signal recurrence_count; fall back to id collisions.
    recurrence = sum(int(s.get("recurrence_count", 0) or 0) for s in sigs)
    if recurrence == 0 and ids:
        recurrence = len(ids) - len(set(ids))

    pressure_scalar_compat = round((vol_max or 1) / 100.0, 2)

    return {
        "active_signal_count": len(sigs),
        "unique_signal_count": len(set(ids)) if ids else 0,
        "volume_max": vol_max,
        "volume_sum": vol_sum,
        "volume_mean": round(vol_mean, 3),
        "volume_entropy": round(entropy, 4),
        "volume_gini": round(gini, 4),
        "cluster_count": len(clusters),
        "oldest_active_age_tics": oldest,
        "newest_active_age_tics": newest,
        "recurrence_count": recurrence,
        "pressure_scalar_compat": pressure_scalar_compat,
    }


def build_council_pressure(conf: dict[str, Any]) -> list[dict[str, Any]]:
    sigs = conf.get("active_signals", []) or []
    wrns = conf.get("active_warrants", []) or []
    cur_tic = int(conf.get("tic_count_physical") or 0)
    poles: list[dict[str, Any]] = []
    if sigs:
        manifold_shape = build_manifold_active(sigs, cur_tic)
        max_vol = manifold_shape["volume_max"] or 1
        poles.append({
            "poleId": "council.manifold_active",
            "poleName": "Active Manifold",
            # pressure preserved as derived/compat for unaudited downstream consumers.
            # Authoritative shape lives in manifold_active below.
            "pressure": manifold_shape["pressure_scalar_compat"],
            "direction": "strains" if max_vol > 30 else "holds",
            "manifold_active": manifold_shape,
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
    # RTCH packet ingestion (Ship 2 of tic-223 three-layer terrain proposal).
    # Fresh packets contribute Layer 3 hot-path pressure scaled by TTL decay_weight.
    # Expired packets surface as historical_packet_stub (Layer 2 pointer, Layer 3 force=0).
    # Layer 1 verbatim packet file at audit-logs/rtch/packets/ is invariant.
    cur_tic = int(conf.get("tic_count_physical") or 0)
    fresh_packets, expired_packets = load_rtch_packets(cur_tic)
    for pkt in fresh_packets[:RTCH_PACKET_LIMIT]:
        chunks.append(build_chunk_from_rtch_packet(pkt))
    for pkt in expired_packets[:RTCH_STUB_LIMIT]:
        chunks.append(build_chunk_from_expired_rtch_packet(pkt))
    return chunks


def build_envelope(posture: str, mode: str) -> dict[str, Any]:
    conf = latest_conformation()
    tic = current_tic()
    queue_lookup = latest_status_per_id(QUEUE_FILE)
    census = read_json(SCENE_CENSUS)

    # Assemble terrain.conductance from the cartography producer (β→γ, /review 401):
    # real substrate signals feed cartography's deriveConductance; the assembler
    # maps to the band contract. Fail-soft to authored literals (canary fires).
    #   acoustic ← signal-manifold liveness; light ← conformation recency
    #   (observability); social ← actor-registry (read inside the assembler).
    #   gravity stays authored (dead field — engine short-circuits it).
    _sigs = conf.get("active_signals", []) or []
    _conf_tic = int(conf.get("tic_count_physical") or 0)
    _manifold_stats = build_manifold_active(_sigs, _conf_tic) if _sigs else None
    _observability = {"latestConformationTic": _conf_tic, "currentTic": int(tic)}
    conductance_result = assemble_conductance(
        _manifold_stats, REPO_ROOT, observability=_observability
    )

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
        "terrainSlice": build_terrain_slice(census, tic, posture, mode, conductance_result),
        "councilPressureHints": build_council_pressure(conf),
        "receiverRegister": receiver_register,
        "returnedChunks": build_returned_chunks(conf, queue_lookup),
    }

    # Braid ingestion (cable BR5, braid covenant tic 569). GUARDED: when no
    # braid packet is loadable the envelope is byte-identical to the pre-braid
    # builder (fail-soft — content survives expression failure). When present:
    # up to 3 braid chunks join returnedChunks and the envelope gains top-level
    # traversalPhysics verbatim (engine ignores unknown fields — verified:
    # runHarmonyEngine reads named fields only).
    braid_packet = load_braid_packet()
    if braid_packet is not None:
        try:
            envelope["returnedChunks"].extend(build_chunks_from_braid(braid_packet))
            envelope["traversalPhysics"] = braid_packet.get("traversal_physics")
            print(
                f"✓ harmony: braid packet ingested (tic={braid_packet.get('tic')}, "
                f"route={((braid_packet.get('traversal_physics') or {}).get('route_advisory'))})",
                file=sys.stderr,
            )
        except Exception as exc:  # fail-soft: braid failure never breaks the lane
            print(f"⚠ harmony: braid ingestion failed fail-soft ({exc})", file=sys.stderr)
    else:
        print("⚠ harmony: no braid packet available — legacy envelope (fail-soft)", file=sys.stderr)
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


def _selftest_braid() -> int:
    """Hermetic selftest for the BR5 braid-ingestion lane (no live surfaces).

    House style: numbered checks, [PASS]/[FAIL] lines, final N/N RESULT.
    Deterministic — fixture packets only; never touches audit-logs/.
    """
    import re as _re
    import tempfile

    # Same imperative-guard family as aesop_archetype_field._IMPERATIVE_RE:
    # braid chunk text is observational pressure, never command.
    imperative_re = _re.compile(r"\b(must|never|always|shall|do\s+not|don'?t)\b", _re.IGNORECASE)

    def fixture_packet(route: str, wisdom: float, caution: float,
                       jerks: list[str], trust_d1: float) -> dict[str, Any]:
        return {
            "type": "lattice.braid.tic",
            "tic": 570,
            "archetype_field": {
                "wisdom_mass": wisdom,
                "caution_mass": caution,
                "dominant": {"id": "cried_wolf", "fable": "The Boy Who Cried Wolf",
                             "moral": "Repeated false alarms spend the trust a true alarm will later need."},
            },
            "wisdom_pressure": {
                "wisdom_hydration_hint": ("A steady pace arrives while bursts and naps are still trading places."
                                          if wisdom > caution else None),
                "failure_mode_inverse": (None if wisdom > caution else
                                         "'The Boy Who Cried Wolf' names the nearest failure shape."),
            },
            "traversal_physics": {
                "route_advisory": route,
                "elevation": 0.81,
                "barrier_cost": {"value": 12.0, "nearest_ponr": {
                    "id": "cried_wolf", "axis": "epitaph_proximity", "distance_to_ponr": 0.0}},
            },
            "trajectory": {"jerk_flags": jerks,
                           "tick_scale": {"trust": {"d1": trust_d1}}},
        }

    checks: list[tuple[str, bool]] = []

    # [1] caution/near_ponr fixture: 3 chunks, kinds TENSION/BOUNDARY, bands right
    pkt = fixture_packet("near_ponr", 0.0, 1.0, [], 0.0002)
    chunks = build_chunks_from_braid(pkt)
    checks.append(("three_chunks_emitted", len(chunks) == 3))
    checks.append(("wisdom_chunk_tension_when_caution_dominant",
                   chunks[0]["signalKindHint"] == "TENSION" and chunks[0]["bandHint"] == "ACOUSTIC"))
    checks.append(("traversal_chunk_boundary_only_at_near_ponr",
                   chunks[1]["signalKindHint"] == "BOUNDARY" and chunks[1]["bandHint"] == "GRAVITY"))
    checks.append(("trajectory_chunk_beacon_when_steady",
                   chunks[2]["signalKindHint"] == "BEACON" and chunks[2]["bandHint"] == "LIGHT"))

    # [2] wisdom/cheap fixture: LESSON + TENSION (not BOUNDARY) kinds
    pkt2 = fixture_packet("cheap", 0.9, 0.1, [], 0.0001)
    chunks2 = build_chunks_from_braid(pkt2)
    checks.append(("wisdom_chunk_lesson_when_wisdom_dominant", chunks2[0]["signalKindHint"] == "LESSON"))
    checks.append(("traversal_chunk_tension_off_ponr", chunks2[1]["signalKindHint"] == "TENSION"))

    # [3] jerk flags / falling trust flip trajectory chunk to TENSION
    pkt3 = fixture_packet("rising", 0.5, 0.5, ["tick_scale.g_t.jerk_high"], -0.001)
    chunks3 = build_chunks_from_braid(pkt3)
    checks.append(("trajectory_chunk_tension_on_jerk_or_falling_trust",
                   chunks3[2]["signalKindHint"] == "TENSION"))

    # [4] non-imperative texts across all fixtures (observational guard)
    all_texts = [c["text"] for c in chunks + chunks2 + chunks3]
    checks.append(("chunk_texts_non_imperative",
                   all(imperative_re.search(t) is None for t in all_texts)))

    # [5] schema completeness per chunk (engine-required fields)
    def complete(c: dict[str, Any]) -> bool:
        sc = c.get("sourceCentroid", {})
        return all(k in c for k in ("chunkId", "source", "text", "provenance",
                                    "signalKindHint", "bandHint", "relayDepth")) and \
            all(k in sc for k in ("centroidId", "rung", "label", "embedding",
                                  "collapseZones", "siblingOverlaps")) and \
            sc["collapseZones"] == BRAID_COLLAPSE_ZONES and \
            c["provenance"]["sourceId"] == "audit-logs/braid/braid-tic-570.json"
    checks.append(("chunk_schema_complete", all(complete(c) for c in chunks)))

    # [6] fail-soft loader: absent dir → None; corrupt pointer → None
    with tempfile.TemporaryDirectory() as td:
        tdp = pathlib.Path(td)
        checks.append(("loader_none_on_absent_surface", load_braid_packet(tdp / "nope") is None))
        (tdp / "current-pointer.json").write_text("{not json")
        checks.append(("loader_none_on_corrupt_pointer", load_braid_packet(tdp) is None))
        # wrong-type packet rejected
        (tdp / "current-pointer.json").write_text(json.dumps({"braid_packet_path": "pkt.json"}))
        (tdp / "pkt.json").write_text(json.dumps({"type": "not.a.braid"}))
        checks.append(("loader_none_on_wrong_packet_type", load_braid_packet(tdp) is None))
        # valid fixture loads
        (tdp / "pkt.json").write_text(json.dumps(pkt))
        loaded = load_braid_packet(tdp)
        checks.append(("loader_loads_valid_fixture", isinstance(loaded, dict) and loaded.get("tic") == 570))

    passed = sum(1 for _, ok in checks if ok)
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 74)
    print(f"RESULT: {passed}/{len(checks)} checks passed — {'OK' if passed == len(checks) else 'FAIL'}")
    return 0 if passed == len(checks) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--posture", default=os.environ.get("CGG_POSTURE", "OPS/DIRECT"))
    ap.add_argument("--mode", default=os.environ.get("CGG_STATUSLINE_MODE", "FULL"))
    ap.add_argument("--output-dir", default=str(HARMONY_DIR))
    ap.add_argument("--print", action="store_true", help="print path of written input on success")
    ap.add_argument("--selftest", action="store_true",
                    help="run the hermetic BR5 braid-lane selftest and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest_braid()

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
