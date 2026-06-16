#!/usr/bin/env python3
"""contagion-input-builder.py — federation-state -> contagion.match input envelope.

CGG-rung wrapper (clone of harmony-input-builder.py). READ-ONLY of federation
state. Writes ONLY audit-logs/contagion/input-tic-N.json.

Sibling kernel to harmony. This builder's job is the load-bearing FENCE #2 work:
turn BOTH the live conformation AND each learned coordinate into vectors in ONE
SHARED STRUCTURAL DIMENSION SPACE, so the engine's cosine match is
CONFORMATION-PROXIMITY (shape against shape), NEVER text similarity.

Inputs (read-only):
  - audit-logs/conformations/tic-N.json   (the CURRENT SHAPE — the retrieval key)
  - audit-logs/patterns/f2-learned-coordinates.json  (Lane B learned coordinates)
  - audit-logs/signals/resolved-archive.jsonl + NACK_* (epitaph failure shapes,
    via the SAME structural projection)

Output (write-only, its own surface):
  - audit-logs/contagion/input-tic-N.json

The SHARED STRUCTURAL DIMENSION SCHEMA (STRUCT_DIMS) — every vector, current and
learned, is projected into these axes. No text token ever enters a vector.
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# walk up to canonical root
ROOT = "/Users/breydentaylor/canonical"
for _ in range(8):
    if os.path.isdir(os.path.join(ROOT, "audit-logs", "conformations")):
        break

CONTAGION_DIR = os.path.join(ROOT, "audit-logs", "contagion")
CONFORMATION_DIR = os.path.join(ROOT, "audit-logs", "conformations")
LEARNED_COORDS = os.path.join(ROOT, "audit-logs", "patterns", "f2-learned-coordinates.json")
RESOLVED_ARCHIVE = os.path.join(ROOT, "audit-logs", "signals", "resolved-archive.jsonl")

# ---------------------------------------------------------------------------
# THE SHARED STRUCTURAL DIMENSION SCHEMA (fence #2 — shape, never text)
# ---------------------------------------------------------------------------
# Each axis is a structural property a conformation AND a learned coordinate
# both express. The match is cosine over these axes. Order is load-bearing.
STRUCT_DIMS = [
    "failure_pressure",     # 0: how failure-shaped is this state?
    "signal_density",       # 1: how much active-signal load?
    "drift_band",           # 2: doctrine-byte drift proxy / shape volatility
    "manifold_tension",     # 3: unresolved manifold pressure
    "pending_pressure",     # 4: pending-cogpr / pending-work load
    "well_worn",            # 5: familiarity / on-the-office's-actual-work
    "estate_hazard",        # 6: estate_profile hazard level
    "epitaph_proximity",    # 7: closeness to a remembered failure
]
N_DIMS = len(STRUCT_DIMS)


def clamp01(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------------------
# Project the LIVE conformation into the shared structural shape.
# ---------------------------------------------------------------------------
def latest_conformation():
    files = glob.glob(os.path.join(CONFORMATION_DIR, "tic-*.json"))
    if not files:
        raise FileNotFoundError("no conformation tic-*.json found")

    def tic_of(p):
        b = os.path.basename(p)
        try:
            return int(b.replace("tic-", "").replace(".json", ""))
        except ValueError:
            return -1

    files.sort(key=tic_of)
    return files[-1]


def conformation_shape(conf):
    sigs = conf.get("active_signals", []) or []
    counts = conf.get("counts", {}) or {}
    gqe = conf.get("governance_query_enrichment", {}) or {}

    # failure_pressure: fraction of active signals whose id carries a failure shape
    fail_terms = ("drift", "fail", "rollback", "gap", "storm", "leak", "stale", "down_audit")
    fail_sigs = sum(
        1 for s in sigs
        if any(t in (s.get("id", "") or "").lower() for t in fail_terms)
    )
    failure_pressure = clamp01(fail_sigs / max(1, len(sigs))) if sigs else 0.0

    # signal_density: normalized count of active signals (cap at 8 = saturated)
    signal_density = clamp01(counts.get("active_signals", len(sigs)) / 8.0)

    # drift_band: doctrine-surface byte volatility proxy. Baseline ~36KB site +
    # 13KB global ~= 49.5KB. Deviation reads as drift pressure. Bounded.
    rif = conf.get("rules_in_force", {}) or {}
    site_b = (rif.get("site", {}) or {}).get("bytes", 36493)
    glob_b = (rif.get("global", {}) or {}).get("bytes", 13017)
    baseline = 36493 + 13017
    drift_band = clamp01(abs((site_b + glob_b) - baseline) / baseline)

    # manifold_tension: active manifold entries (CLEAR -> 0)
    ms = (gqe.get("manifold_summary", {}) or {})
    manifold_active = ms.get("active", 0)
    manifold_state = gqe.get("manifold_state", "CLEAR")
    manifold_tension = 0.0 if manifold_state == "CLEAR" else clamp01(
        manifold_active / 8.0 if manifold_active else 0.3
    )

    # pending_pressure: pending cogprs / warrants
    pending_pressure = clamp01(
        (counts.get("pending_cogprs", 0) + counts.get("active_warrants", 0)) / 6.0
    )

    # well_worn: inverse of failure pressure when the field is quiet — the field
    # is "on the office's work" when it is not failure-shaped and not hazardous.
    estate_profile = gqe.get("estate_profile", "")
    estate_hazard = 1.0 if estate_profile == "hazard" else (
        0.5 if estate_profile in ("caution", "warn") else 0.0
    )
    well_worn = clamp01((1.0 - failure_pressure) * (1.0 - 0.5 * estate_hazard))

    # epitaph_proximity for the CURRENT conformation = its own failure pressure
    # echoed into the failure axis (so a failure-shaped present sits near
    # failure-shaped learned terrain). Kept distinct from failure_pressure so the
    # two axes can diverge for learned coordinates.
    epitaph_proximity = failure_pressure

    vec = [
        round(failure_pressure, 4),
        round(signal_density, 4),
        round(drift_band, 4),
        round(manifold_tension, 4),
        round(pending_pressure, 4),
        round(well_worn, 4),
        round(estate_hazard, 4),
        round(epitaph_proximity, 4),
    ]
    provenance = {
        "dims": N_DIMS,
        "schema": STRUCT_DIMS,
        "values": dict(zip(STRUCT_DIMS, vec)),
        "derived_from": {
            "active_signals": len(sigs),
            "failure_shaped_signals": fail_sigs,
            "manifold_state": manifold_state,
            "estate_profile": estate_profile,
            "pending_cogprs": counts.get("pending_cogprs", 0),
            "site_bytes": site_b,
            "global_bytes": glob_b,
        },
        "note": "STRUCTURAL shape only — no text tokens enter this vector (fence #2)",
    }
    return vec, provenance


# ---------------------------------------------------------------------------
# Project each LEARNED COORDINATE into the SAME shared structural shape.
# ---------------------------------------------------------------------------
def learned_coordinate_shape(p):
    """Map a Lane B learned-coordinate row to STRUCT_DIMS.

    The coordinate's OWN learned fields ARE its structural shape: affinity =
    well_worn, epitaph distance -> epitaph_proximity, route_kind -> failure
    pressure, observation_count -> a familiarity prior. No pattern TEXT is read
    into the vector (fence #2); pattern text is carried separately for human
    legibility only.
    """
    aff = clamp01(p.get("f2_office_affinity", 0.0) * 8.0)  # affinity is small (0-0.1); scale to 0-1 band
    epi = p.get("f2_nearest_epitaph", {}) or {}
    epi_dist = clamp01(epi.get("distance", 1.0))
    epitaph_proximity = clamp01(1.0 - epi_dist)
    route = (p.get("f2_route_kind") or "neutral").lower()

    # route_kind encodes the learned failure/familiarity contour structurally
    if route == "epitaph":
        failure_pressure, well_worn = 0.9, 0.1
    elif route == "tricky":
        failure_pressure, well_worn = 0.55, 0.3
    elif route == "well_worn":
        failure_pressure, well_worn = 0.15, max(0.6, aff)
    else:  # neutral
        failure_pressure, well_worn = 0.3, aff

    # observation tier -> a familiarity/signal-density prior (well-observed
    # patterns describe denser terrain)
    obs = p.get("observation_count", 0) or 0
    signal_density = clamp01(obs / 16.0)

    # confidence tier -> drift-band inverse (reinforced patterns are stable)
    tier = (p.get("confidence_tier") or "").lower()
    drift_band = {"reinforced": 0.1, "convergent": 0.25, "tentative": 0.5}.get(tier, 0.4)

    # manifold/pending/hazard are conformation-runtime axes the learned
    # coordinate does not directly carry; project them from the failure contour
    # so a failure-shaped coordinate reads as tensioned terrain.
    manifold_tension = clamp01(failure_pressure * 0.5)
    pending_pressure = clamp01(epitaph_proximity * 0.5)
    estate_hazard = clamp01(failure_pressure * 0.6)

    vec = [
        round(failure_pressure, 4),
        round(signal_density, 4),
        round(drift_band, 4),
        round(manifold_tension, 4),
        round(pending_pressure, 4),
        round(well_worn, 4),
        round(estate_hazard, 4),
        round(epitaph_proximity, 4),
    ]
    return vec


def load_learned_coordinates():
    if not os.path.exists(LEARNED_COORDS):
        return [], None
    d = json.load(open(LEARNED_COORDS))
    coords = []
    for p in d.get("patterns", []) or []:
        coords.append({
            "coordinate_id": p.get("pattern", "")[:48] or "unnamed",
            "shapeVector": learned_coordinate_shape(p),
            "source_lane": "token",
            "route_kind": p.get("f2_route_kind"),
            "confidence_tier": p.get("confidence_tier"),
            # human-legible only — NEVER enters the proximity match
            "pattern_excerpt": p.get("pattern", ""),
        })
    return coords, d.get("tic")


# ---------------------------------------------------------------------------
# Epitaph failure-shape profiles (the failure axis of conformation-proximity).
# Each epitaph is a synthetic failure-shaped vector (high failure_pressure +
# epitaph_proximity), so a failure-shaped present conformation sits near it.
# ---------------------------------------------------------------------------
def load_epitaph_shapes():
    epis = []
    fail_terms = ("drift", "fail", "rollback", "gap", "storm", "leak", "stale")
    if os.path.exists(RESOLVED_ARCHIVE):
        seen = set()
        for line in open(RESOLVED_ARCHIVE):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = r.get("signal_id") or r.get("id") or ""
            low = sid.lower()
            if not any(t in low for t in fail_terms) or sid in seen:
                continue
            seen.add(sid)
            # intensity = how many failure terms the id carries (denser = sharper)
            intensity = clamp01(sum(low.count(t) for t in fail_terms) / 3.0) or 0.4
            epis.append({
                "id": sid,
                "kind": "resolved_failure_signal",
                # a sharp failure shape: high failure_pressure, manifold tension,
                # estate hazard, epitaph proximity; low well_worn.
                "shapeVector": [
                    round(0.7 + 0.3 * intensity, 4),  # failure_pressure
                    round(0.4 * intensity, 4),         # signal_density
                    0.4,                                # drift_band
                    round(0.5 + 0.3 * intensity, 4),   # manifold_tension
                    round(0.4 * intensity, 4),         # pending_pressure
                    round(0.15 * (1 - intensity), 4),  # well_worn (low)
                    round(0.6 + 0.3 * intensity, 4),   # estate_hazard
                    round(0.85 + 0.15 * intensity, 4), # epitaph_proximity (high)
                ],
            })
    for nf in glob.glob(os.path.join(ROOT, "audit-logs", "agent-mailboxes", "*", "archive", "NACK_*")):
        base = os.path.basename(nf)
        epis.append({
            "id": base,
            "kind": "nack_obligation",
            "shapeVector": [0.65, 0.3, 0.4, 0.5, 0.5, 0.2, 0.55, 0.8],
        })
    return epis


# ---------------------------------------------------------------------------
def build(posture=None, geometry="conformation"):
    conf_path = latest_conformation()
    conf = json.load(open(conf_path))
    tic = conf.get("tic_count_physical", 0)
    posture = posture or conf.get("posture", "unknown")

    cur_vec, provenance = conformation_shape(conf)
    coords, coords_tic = load_learned_coordinates()
    epis = load_epitaph_shapes()

    envelope = {
        "type": "contagion.match.input",
        "tic": tic,
        "office": "ent_homeskillet",
        "posture": posture,
        "geometry": geometry,
        "currentShape": cur_vec,
        "shapeProvenance": provenance,
        "learnedCoordinates": coords,
        "epitaphProfiles": epis,
        "receiverRegister": {
            "posture": posture,
            "toleranceForDissonance": 0.5 if "DIRECT" in (posture or "") else 0.7,
        },
        "packetSeed": f"{tic}:{conf_path}",
        "_sources": {
            "conformation": os.path.relpath(conf_path, ROOT),
            "learned_coordinates": os.path.relpath(LEARNED_COORDS, ROOT),
            "learned_coordinates_tic": coords_tic,
            "n_learned": len(coords),
            "n_epitaphs": len(epis),
        },
    }

    os.makedirs(CONTAGION_DIR, exist_ok=True)
    out_path = os.path.join(CONTAGION_DIR, f"input-tic-{tic}.json")
    with open(out_path, "w") as f:
        json.dump(envelope, f, indent=2)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="print the written input path")
    ap.add_argument("--posture", default=os.environ.get("CGG_POSTURE"))
    args = ap.parse_args()
    out_path = build(posture=args.posture)
    if args.print:
        print(out_path)
    else:
        print(f"contagion input written: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
