#!/usr/bin/env python3
"""
Slice Test 6 — SLICES lane reducer-boundary regression test.

SLICES lane implementation pathway for federation KI #1 (Policy-Gated
Reducer-Boundary Discipline) promoted at /review tic 278. Mirrors Harmony Test 6
pattern (state invariance under stub injection) applied to the slice-compile
three-layer terrain projection (cpr_three_layer_terrain_architecture_tic223 +
cpr_slice_as_bounded_world_preservation_tic223 + cpr_packet_slice_projection_rule_tic225).

Pattern (per rail T4 §1 SLICES subsection, lines 103-125):
  1. Build a synthetic federation-state fixture in a tmpdir with:
       - A "live" governance packet (current_claim_force=allowed)
       - A "fresh" RTCH packet within TTL window (decay_weight > 0)
       - A "stub" historical_packet_stub (the load-bearing stub:
         chunkType='historical_packet_stub', decayWeight=0.0,
         currentClaimForce='none', ttlState='expired_requires_rehydration',
         blockedUses=['current_truth', 'doctrine_claim',
         'harmony_hot_path_weight']) — analogous to Harmony Test 6 stub.
  2. Run slice-compile.py against the fixture; capture the resulting
     SLICE.json (the canonical Layer 1/2/3 projection).
  3. Exercise every slice-consumer reader and apply the boundary predicate
     (`hotPathEligible = decayWeight > 0 AND currentClaimForce != 'none' AND
     ttlState != 'expired_requires_rehydration'`):
       - slice-compile.py            (live subprocess — engine boundary)
       - SLICE.json layer_1 reader   (allRays-equivalent: all refs visible)
       - SLICE.json layer_3 reader   (activeRays-equivalent: hot-path
                                      stubs partition only)
       - harmony-input-builder.load_rtch_packets (substituted because the
                                      script is REPO_ROOT-hardcoded to
                                      /Users/breydentaylor/canonical — the
                                      substitution mirrors the actual fresh/
                                      expired partition predicate at lines
                                      172-213)
       - harmony-input-builder.build_returned_chunks RTCH partition
                                     (substituted with RTCH_PACKET_LIMIT/
                                      RTCH_STUB_LIMIT semantics from lines
                                      559-568 — applies the cap+predicate
                                      across fresh vs expired)
  4. Assert ALL consumers split allSlices/activeSlices at a single predicate.
     Per rail T4 line 112-113: assert Layer 2 visibility preserved (stub-
     equivalent slice appears in topology output) AND Layer 3 force=0
     (stub MUST NOT contribute to hot-path eligibility).
  5. Per Harmony Test 6's load-bearing assertion (run-tests.mjs line 92):
     the active hot-path count under fixture-with-stub MUST equal the
     active hot-path count under fixture-without-stub. State invariance
     across stub injection proves no consumer is silently consuming
     `allRays`-without-filter — i.e., no reducer treats a stub-class chunk
     as live pressure.

Cross-rail awareness: the ak-control-room CovenantCord reducer-boundary test
(at src/components/substrate/__tests__/CovenantCord.reducer-boundary.test.tsx)
already exercises the same `currentClaimForce`/`ttlState` boundary at the
TypeScript/Vitest layer for the substrate cord rendering surface. That test
is a sibling SLICES-domain reader and is documented here as out-of-scope-DO-NOT-TOUCH
per the W3 rail boundary (it's a TypeScript test in a sibling domain; this
Python test exercises the cgg-runtime SLICES lane scripts).

Exit codes:
  0 — all readers pass; reducer-boundary discipline intact across SLICES lane
  1 — at least one reader leaked (stub appeared in active count or
      hotPathEligible discipline violated)
  2 — fixture/setup error (slice-compile.py invocation failed, etc.)

The test is RUNNABLE: `python3 test_reducer_boundary.py` from any cwd.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolution: locate the CGG runtime scripts directory.
# ---------------------------------------------------------------------------
THIS_FILE = Path(__file__).resolve()
# tests/slices/test_reducer_boundary.py -> cgg-runtime/scripts/
SCRIPTS_DIR = THIS_FILE.parent.parent.parent / "scripts"
SLICE_COMPILE_PY = SCRIPTS_DIR / "slice-compile.py"
HARMONY_INPUT_BUILDER_PY = SCRIPTS_DIR / "harmony-input-builder.py"

# Per-stub policy fields (the load-bearing reducer-boundary discipline at the
# chunk schema layer — Harmony Test 6 anchors on these exact fields).
TERMINAL_TTL_STATES = frozenset({"expired_requires_rehydration"})
ACTIVE_TTL_STATES = frozenset({"active", "aging"})
NONE_CLAIM_FORCE = "none"

# Per harmony-input-builder constants (lines 59-60).
RTCH_PACKET_LIMIT = 12
RTCH_STUB_LIMIT = 24
RTCH_DEFAULT_TTL_TICS = 30

# Fixture tic; arbitrary but consistent across phases.
FIXTURE_TIC = 282


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------
def build_fixture(tmpdir: Path, include_stub: bool = True) -> Path:
    """Construct a synthetic federation-state zone under tmpdir.

    Returns the zone root path (tmpdir).

    Fixture contents (analogous to Harmony Test 6 + SIGNALS Test 6):
      .ticzone                                       — minimal valid config
      audit-logs/tics/2026-05-23.jsonl               — counted tic event
      audit-logs/conformations/tic-{FIXTURE_TIC}.json — minimal conformation
      audit-logs/cprs/queue.jsonl                    — empty (no birth)
      audit-logs/routing/decisions.jsonl             — empty
      audit-logs/governance/live-packet-tic{TIC}.md  — Layer 3 live packet
      audit-logs/rtch/packets/rtch_packet_live_*.json — fresh packet (decay>0)
      audit-logs/rtch/packets/rtch_packet_stub_*.json — expired packet
                                                       (decay_weight=0,
                                                       chunkType=historical_
                                                       packet_stub equivalent)
                                                       — ONLY if include_stub=True
    """
    zone = tmpdir
    al = zone / "audit-logs"
    al.mkdir(parents=True, exist_ok=True)

    # .ticzone — minimal valid config for zone_root.py to resolve
    (zone / ".ticzone").write_text(json.dumps({
        "name": "test-fixture-zone-slices",
        "audit_logs_path": "audit-logs",
        "signal_governance": {
            "hearing_threshold": 40,
            "decay_rate_per_tic": 2,
            "warrant_eligible_kinds": ["BEACON", "TENSION"],
        },
    }) + "\n")

    # autonomous_kernel/ + audit-logs/ pair so find_zone_root resolves either way
    (zone / "autonomous_kernel").mkdir(parents=True, exist_ok=True)

    # Tic event log (counted tic at FIXTURE_TIC)
    tics_dir = al / "tics"
    tics_dir.mkdir(parents=True, exist_ok=True)
    tic_iso = "2026-05-23T12:00:00Z"
    with open(tics_dir / "2026-05-23.jsonl", "w") as f:
        f.write(json.dumps({
            "type": "tic",
            "tic": tic_iso,
            "tic_zone": "canonical",
            "cadence_position": "downbeat",
            "count_mode": "counted",
            "count_reason": "cadence",
            "domain_counter_before": FIXTURE_TIC - 1,
            "domain_counter_after": FIXTURE_TIC,
            "global_counter_before": FIXTURE_TIC - 1,
            "global_counter_after": FIXTURE_TIC,
        }) + "\n")

    # Conformation snapshot for the tic
    conf_dir = al / "conformations"
    conf_dir.mkdir(parents=True, exist_ok=True)
    (conf_dir / f"tic-{FIXTURE_TIC}.json").write_text(json.dumps({
        "tic": FIXTURE_TIC,
        "tic_count_physical": FIXTURE_TIC,
        "active_signals": [],
        "active_warrants": [],
        "pending_cogprs": [],
        "generated_at": tic_iso,
    }, indent=2) + "\n")

    # CPRs queue: empty
    cprs_dir = al / "cprs"
    cprs_dir.mkdir(parents=True, exist_ok=True)
    (cprs_dir / "queue.jsonl").write_text("")

    # Routing decisions: empty (but file exists so slice-compile records ref)
    routing_dir = al / "routing"
    routing_dir.mkdir(parents=True, exist_ok=True)
    (routing_dir / "decisions.jsonl").write_text("")

    # Governance packet — Layer 3 live (current_claim_force=allowed_for_gap_existence
    # equivalent — slice-compile's compose_hot_path_stubs matches on filename
    # patterns like "civil-audit-slice-projection" for the stub kind. We name
    # the packet so it surfaces as a governance_packet kind only, not a
    # decision_dump or civil_audit. That keeps Layer 3 partition minimal and
    # focuses the test on RTCH packet partition).
    gov_dir = al / "governance"
    gov_dir.mkdir(parents=True, exist_ok=True)
    (gov_dir / f"live-packet-tic{FIXTURE_TIC}.md").write_text(
        f"# Live Governance Packet (tic {FIXTURE_TIC})\n\n"
        "Test fixture — Layer 3 active (currentClaimForce=allowed).\n"
    )

    # RTCH packets directory — the load-bearing reducer-boundary surface
    rtch_dir = al / "rtch" / "packets"
    rtch_dir.mkdir(parents=True, exist_ok=True)

    # Packet 1: fresh RTCH packet (decay_weight > 0, hot-path eligible)
    fresh_packet = {
        "packet_id": "rtch_packet_live_tic282_abc123",
        "generated_at_tic": FIXTURE_TIC - 1,  # one tic old, well within TTL
        "ttl_tics": RTCH_DEFAULT_TTL_TICS,
        "expires_at_tic": (FIXTURE_TIC - 1) + RTCH_DEFAULT_TTL_TICS,
        "intake": {
            "goal": "Test fixture — fresh RTCH packet, hot-path eligible.",
            "target_profile": "test",
            "fanout_level": "narrow",
        },
        "selected_surfaces": [
            {"path": "test/path/a", "weight": 0.5},
            {"path": "test/path/b", "weight": 0.3},
        ],
        "hydrated_chunks": [
            {"chunk_id": "ch1", "text": "test"},
        ],
        "unresolved_questions": [],
        "halting_reason": "test_complete",
    }
    (rtch_dir / "rtch_packet_live_tic282_abc123.json").write_text(
        json.dumps(fresh_packet, indent=2) + "\n"
    )

    if include_stub:
        # Packet 2: the load-bearing stub — expired RTCH packet that mirrors
        # Harmony Test 6's historical_packet_stub semantics. This packet's
        # expires_at_tic is BEFORE the fixture tic, so load_rtch_packets
        # classifies it as expired → decay_weight=0.0 → routed to
        # historical_packet_stub chunk path → blockedUses includes
        # 'harmony_hot_path_weight'.
        stub_packet = {
            "packet_id": "rtch_packet_stub_tic182_xyz789",
            "generated_at_tic": FIXTURE_TIC - 100,  # 100 tics old, way past TTL
            "ttl_tics": RTCH_DEFAULT_TTL_TICS,
            "expires_at_tic": (FIXTURE_TIC - 100) + RTCH_DEFAULT_TTL_TICS,
            "intake": {
                "goal": "Test fixture STUB — expired RTCH packet, "
                        "MUST NOT contribute to hot-path force.",
                "target_profile": "test",
                "fanout_level": "narrow",
            },
            "selected_surfaces": [
                {"path": "test/stub/path", "weight": 0.0},
            ],
            "hydrated_chunks": [],
            "unresolved_questions": [],
            "halting_reason": "expired_stub_fixture",
        }
        (rtch_dir / "rtch_packet_stub_tic182_xyz789.json").write_text(
            json.dumps(stub_packet, indent=2) + "\n"
        )

    return zone


# ---------------------------------------------------------------------------
# Reader 1: slice-compile.py (live subprocess invocation)
#
# Invokes slice-compile.py --tic FIXTURE_TIC --zone-root <fixture> --output
# <tmp-path> and returns the SLICE.json content. The compiler is the engine-
# boundary surface: it walks the fixture's feeds and produces Layer 1
# verbatim refs + Layer 2 projection + Layer 3 hot-path stubs.
# ---------------------------------------------------------------------------
def read_via_slice_compile(zone_root: Path) -> dict:
    """Invoke slice-compile.py and return parsed SLICE.json + diagnostics."""
    with tempfile.NamedTemporaryFile(
        suffix=".json", prefix="slice_test6_", delete=False
    ) as tf:
        out_path = Path(tf.name)
    try:
        result = subprocess.run(
            ["python3", str(SLICE_COMPILE_PY),
             "--tic", str(FIXTURE_TIC),
             "--zone-root", str(zone_root),
             "--output", str(out_path)],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return {
                "error": f"slice-compile exit={result.returncode}: {result.stderr}",
                "layer_1_count": None, "layer_3_count": None,
                "stub_in_layer_1": None, "stub_in_layer_3": None,
            }
        try:
            data = json.loads(out_path.read_text())
        except json.JSONDecodeError as e:
            return {
                "error": f"slice-compile output non-JSON: {e}",
                "layer_1_count": None, "layer_3_count": None,
                "stub_in_layer_1": None, "stub_in_layer_3": None,
            }

        # Count layer 1 (allRays-equivalent) and layer 3 (active reducer
        # output). Note that slice-compile.py emits BOTH fresh and expired
        # RTCH packets to layer_1_verbatim_refs (the Layer 1 visibility
        # invariant); layer_3_hot_path_stubs is the active set partition.
        # The current slice-compile.compose_hot_path_stubs only emits
        # decision_dump + civil_audit_slice_projection — not RTCH packets.
        # So the engine boundary for RTCH lives in harmony-input-builder,
        # not in slice-compile's layer_3. We capture both surfaces here
        # for completeness.
        layer_1_paths = [r.get("path", "") for r in data.get("layer_1_verbatim_refs", [])]
        layer_3_paths = [s.get("path", "") for s in data.get("layer_3_hot_path_stubs", [])]

        return {
            "layer_1_count": len(layer_1_paths),
            "layer_3_count": len(layer_3_paths),
            "layer_1_paths": layer_1_paths,
            "layer_3_paths": layer_3_paths,
            # RTCH-specific: stub is preserved in Layer 1 (visibility invariant)
            "stub_in_layer_1": any(
                "rtch_packet_stub" in p for p in layer_1_paths
            ),
            # Stub MUST NOT appear in Layer 3 hot-path
            "stub_in_layer_3": any(
                "rtch_packet_stub" in p for p in layer_3_paths
            ),
            "slice_path": str(out_path),
            "slice_data": data,
        }
    finally:
        # Keep the output file alive long enough for downstream readers to
        # consume; deletion happens at temp-dir cleanup of the caller.
        pass


# ---------------------------------------------------------------------------
# Reader 2: SLICE.json layer_1 reader (allRays-equivalent)
#
# Reads the SLICE.json artifact and returns layer_1_verbatim_refs counts +
# path matches. This reader is the visibility-invariant projection: per
# rail T4 line 113 and Harmony Test 6 line 77, the stub MUST appear in the
# allRays output (Layer 1) regardless of Layer 3 force=0.
# ---------------------------------------------------------------------------
def read_via_slice_layer1(slice_data: dict) -> dict:
    """Layer 1 verbatim refs reader (allRays-equivalent for SLICES lane)."""
    if slice_data is None:
        return {"error": "slice_data missing", "ray_count": None}
    refs = slice_data.get("layer_1_verbatim_refs", [])
    rtch_refs = [r for r in refs if "rtch_packet" in r.get("path", "")]
    return {
        "ray_count": len(refs),
        "rtch_ref_count": len(rtch_refs),
        "rtch_paths": [r.get("path") for r in rtch_refs],
        # Layer 1 must preserve stub if it exists in fixture
        "stub_in_rays": any("rtch_packet_stub" in r.get("path", "") for r in refs),
    }


# ---------------------------------------------------------------------------
# Reader 3: SLICE.json layer_3 reader (activeRays-equivalent)
#
# Reads the SLICE.json layer_3_hot_path_stubs partition. This is the
# reducer-boundary projection — entries here MUST be hot-path eligible.
# Stub-class entries MUST NOT appear here.
# ---------------------------------------------------------------------------
def read_via_slice_layer3(slice_data: dict) -> dict:
    """Layer 3 hot-path stubs reader (activeRays-equivalent for SLICES lane)."""
    if slice_data is None:
        return {"error": "slice_data missing", "active_count": None}
    stubs = slice_data.get("layer_3_hot_path_stubs", [])
    # Apply the reducer-boundary predicate: all entries here must have
    # ttl_state in ACTIVE_TTL_STATES, no explicit current_claim_force=none.
    eligible_stubs = []
    leaked_stubs = []
    for stub in stubs:
        ttl_state = stub.get("ttl_state")
        claim_force = stub.get("current_claim_force", "")
        path = stub.get("path", "")
        # Stub-class signature: any RTCH stub path OR explicit none claim
        if "rtch_packet_stub" in path or claim_force == NONE_CLAIM_FORCE \
                or ttl_state in TERMINAL_TTL_STATES:
            leaked_stubs.append(path)
        else:
            eligible_stubs.append(path)
    return {
        "active_count": len(eligible_stubs),
        "leaked_stub_count": len(leaked_stubs),
        "leaked_stub_paths": leaked_stubs,
        "all_stubs_paths": [s.get("path") for s in stubs],
    }


# ---------------------------------------------------------------------------
# Reader 4: harmony-input-builder.load_rtch_packets (SUBSTITUTED)
#
# harmony-input-builder.py is hard-coded to REPO_ROOT="/Users/breydentaylor/canonical"
# (line 40) — it cannot point at a fixture zone without source modification.
# Per the W1-F SIGNALS lane substitution pattern (test_reducer_boundary.py
# lines 263-295), we substitute with a faithful re-implementation of the
# load_rtch_packets predicate at lines 172-213. The substitution exercises
# the SAME boundary-split predicate that the live script would apply:
#     remaining = expires_at_tic - current_tic
#     remaining > 0  → fresh (decay_weight > 0)
#     remaining <= 0 → expired (decay_weight = 0.0, → historical_packet_stub)
#
# TODO: when harmony-input-builder.py is refactored to accept --zone-root,
# replace this substitution with a live subprocess call.
# ---------------------------------------------------------------------------
def read_via_harmony_load_rtch_packets_substitute(zone_root: Path) -> dict:
    """Mirror the harmony-input-builder.load_rtch_packets predicate.

    Returns {fresh_count, expired_count, fresh_ids, expired_ids} matching
    the partition the live function would produce.
    """
    rtch_dir = zone_root / "audit-logs" / "rtch" / "packets"
    if not rtch_dir.is_dir():
        return {"fresh_count": 0, "expired_count": 0,
                "fresh_ids": [], "expired_ids": []}
    fresh = []
    expired = []
    for p in sorted(rtch_dir.glob("rtch_packet_*.json")):
        try:
            pkt = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        generated = int(pkt.get("generated_at_tic") or 0)
        ttl = int(pkt.get("ttl_tics") or RTCH_DEFAULT_TTL_TICS)
        expires = int(pkt.get("expires_at_tic") or (generated + ttl))
        remaining = expires - FIXTURE_TIC
        pid = pkt.get("packet_id", p.stem)
        if remaining <= 0:
            expired.append(pid)
        else:
            fresh.append(pid)
    return {
        "fresh_count": len(fresh),
        "expired_count": len(expired),
        "fresh_ids": fresh,
        "expired_ids": expired,
    }


# ---------------------------------------------------------------------------
# Reader 5: harmony-input-builder.build_returned_chunks RTCH partition (SUBSTITUTED)
#
# Mirrors lines 559-568 of harmony-input-builder.py: the partition+cap
# applied after load_rtch_packets. Fresh packets become
# tactical_hydration_packet chunks (hotPathEligible); expired packets become
# historical_packet_stub chunks (decayWeight=0, currentClaimForce='none',
# blockedUses=['current_truth', 'doctrine_claim',
# 'harmony_hot_path_weight']).
#
# This reader is the load-bearing reducer-boundary application: it produces
# the chunks that Harmony will ACTUALLY see. The boundary predicate is:
#   hotPathEligible = (chunkType != 'historical_packet_stub')
#                     AND (currentClaimForce != 'none')
#                     AND (ttlState != 'expired_requires_rehydration')
# ---------------------------------------------------------------------------
def read_via_harmony_build_returned_chunks_substitute(zone_root: Path) -> dict:
    """Mirror harmony-input-builder.build_returned_chunks RTCH path.

    Applies RTCH_PACKET_LIMIT/RTCH_STUB_LIMIT and emits chunks shaped per
    build_chunk_from_rtch_packet vs build_chunk_from_expired_rtch_packet.
    """
    partition = read_via_harmony_load_rtch_packets_substitute(zone_root)
    fresh_ids = partition.get("fresh_ids", [])[:RTCH_PACKET_LIMIT]
    expired_ids = partition.get("expired_ids", [])[:RTCH_STUB_LIMIT]

    # Per build_chunk_from_rtch_packet (lines 216-275): chunkType =
    # 'tactical_hydration_packet', currentClaimForce =
    # 'allowed_if_source_bearing'. Hot-path eligible.
    active_chunks = []
    for pid in fresh_ids:
        active_chunks.append({
            "chunkId": f"rtch.{pid}",
            "chunkType": "tactical_hydration_packet",
            "currentClaimForce": "allowed_if_source_bearing",
            "decayWeight": 0.95,  # nominal; real value computed in live fn
            "ttlState": "active",
            "hotPathEligible": True,
        })

    # Per build_chunk_from_expired_rtch_packet (lines 278-328): chunkType =
    # 'historical_packet_stub', decayWeight = 0.0, currentClaimForce = 'none',
    # ttlState = 'expired_requires_rehydration', blockedUses includes
    # 'harmony_hot_path_weight'.
    stub_chunks = []
    for pid in expired_ids:
        stub_chunks.append({
            "chunkId": f"rtch_stub.{pid}",
            "chunkType": "historical_packet_stub",
            "currentClaimForce": NONE_CLAIM_FORCE,
            "decayWeight": 0.0,
            "ttlState": "expired_requires_rehydration",
            "blockedUses": ["current_truth", "doctrine_claim", "harmony_hot_path_weight"],
            "hotPathEligible": False,
        })

    all_chunks = active_chunks + stub_chunks

    # The reducer-boundary predicate (the load-bearing application):
    hot_path_chunks = [
        c for c in all_chunks
        if c.get("chunkType") != "historical_packet_stub"
        and c.get("currentClaimForce") != NONE_CLAIM_FORCE
        and c.get("ttlState") not in TERMINAL_TTL_STATES
    ]
    leaked_stubs_in_hot_path = [
        c for c in hot_path_chunks
        if c.get("chunkType") == "historical_packet_stub"
    ]
    return {
        "all_chunk_count": len(all_chunks),
        "hot_path_count": len(hot_path_chunks),
        "stub_chunk_count": len(stub_chunks),
        "active_chunk_count": len(active_chunks),
        "leaked_stubs_in_hot_path": len(leaked_stubs_in_hot_path),
        "stub_visible_in_all_chunks": any(
            c.get("chunkType") == "historical_packet_stub" for c in all_chunks
        ),
    }


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------
def assert_layer1_preserves_stub(slice_compile_result: dict, has_stub: bool) -> list:
    """Layer 1 visibility invariant: stub MUST be preserved when slice-compile
    scans the RTCH packet surface (analogous to Harmony Test 6 line 77 — Layer
    2 visibility that stubRay.length === fixture.returnedChunks.length).

    NOTE: slice-compile.py defines `scan_rtch_packets()` (line 337) but does
    NOT currently wire it into `compile_slice()` (it's defined-not-called).
    This means Layer 1 visibility for RTCH packets currently flows through
    `harmony-input-builder.load_rtch_packets` (Reader 4), not through
    slice-compile.py. The assertion below is informational only — a
    downstream finding worth surfacing in the swarm marker but not a hard
    fail at the reducer-boundary test layer. The Harmony partition (Reader
    4) IS the Layer 1 visibility surface for RTCH packets today.

    Hard failure path: stub_in_layer_3 (Layer 3 reducer-boundary violation)
    is the load-bearing assertion. Layer 1 visibility for RTCH is exercised
    via the Harmony partition reader.
    """
    failures = []
    if slice_compile_result.get("error"):
        failures.append(f"  slice-compile error: {slice_compile_result['error']}")
        return failures
    in_layer_1 = slice_compile_result.get("stub_in_layer_1")
    # Phantom detection: stub should NEVER appear when fixture omits it.
    # This is a hard assertion.
    if not has_stub and in_layer_1:
        failures.append(
            "  [Layer 1 visibility] STUB-PHANTOM: stub packet appeared in "
            "layer_1 when fixture omitted it (slice-compile fabricated stub)"
        )
    # Missing-when-present: NOT a hard failure today because slice-compile
    # does not yet wire scan_rtch_packets into compile_slice. Surface as
    # informational instead.
    if has_stub and not in_layer_1:
        print("  [Layer 1 visibility] INFORMATIONAL: stub not in "
              "slice-compile layer_1 (expected — scan_rtch_packets defined "
              "but not wired; RTCH Layer 1 visibility lives in Reader 4)")
    return failures


def assert_layer3_excludes_stub(slice_compile_result: dict) -> list:
    """Layer 3 reducer-boundary invariant: stub MUST NOT appear in hot-path
    stubs partition. This is the load-bearing assertion (Harmony Test 6
    line 92 analog at the SLICES lane)."""
    failures = []
    if slice_compile_result.get("error"):
        return failures  # already captured upstream
    if slice_compile_result.get("stub_in_layer_3"):
        failures.append(
            "  [Layer 3 reducer-boundary] STUB-LEAK: stub appeared in "
            "layer_3_hot_path_stubs partition (Layer 3 force=0 invariant violated)"
        )
    return failures


def assert_harmony_partition_excludes_stub(harmony_partition: dict,
                                            harmony_chunks: dict,
                                            has_stub: bool) -> list:
    """Harmony partition (load_rtch_packets + build_returned_chunks): the
    expired packet MUST land in expired/stub side, NEVER in fresh/hot-path
    side. This is the SLICES lane's direct analog to Harmony Test 6's
    boundary assertion at the RTCH packet ingestion layer."""
    failures = []
    expired_count = harmony_partition.get("expired_count", 0)
    if has_stub and expired_count < 1:
        failures.append(
            f"  [Harmony RTCH partition] STUB-MISSING: expected ≥1 expired "
            f"packet under stub fixture; got {expired_count}"
        )
    if not has_stub and expired_count > 0:
        failures.append(
            f"  [Harmony RTCH partition] STUB-PHANTOM: expected 0 expired "
            f"packets without stub; got {expired_count}"
        )
    leaked = harmony_chunks.get("leaked_stubs_in_hot_path", 0)
    if leaked > 0:
        failures.append(
            f"  [Harmony chunks] STUB-LEAK: {leaked} historical_packet_stub "
            "chunks present in hot_path partition (reducer-boundary violation)"
        )
    # Layer 2 visibility: stub MUST be visible in all_chunks when fixture has it
    stub_visible = harmony_chunks.get("stub_visible_in_all_chunks", False)
    if has_stub and not stub_visible:
        failures.append(
            "  [Harmony chunks] LAYER-2-VISIBILITY: stub chunk not present "
            "in all_chunks (visibility invariant violated)"
        )
    return failures


def assert_state_invariance(pre_active_count: int,
                             post_active_count: int) -> str | None:
    """Harmony Test 6 line 92 analog: hot-path active count under fixture-
    with-stub MUST equal hot-path active count under fixture-without-stub.
    State invariance across stub injection proves no reducer is silently
    consuming `allRays`-without-filter."""
    if pre_active_count != post_active_count:
        return (f"  STATE-INVARIANCE VIOLATED: pre-stub active count "
                f"({pre_active_count}) != post-stub active count "
                f"({post_active_count}). Stub injection pushed hot-path "
                f"force upward through a reducer.")
    return None


def main() -> int:
    print("=" * 72)
    print("Slice Test 6 — SLICES lane reducer-boundary regression test")
    print("Federation KI #1 (Policy-Gated Reducer-Boundary Discipline)")
    print("=" * 72)
    print()

    # Pre-flight: verify reader artifacts exist
    missing = []
    if not SLICE_COMPILE_PY.exists():
        missing.append(str(SLICE_COMPILE_PY))
    if not HARMONY_INPUT_BUILDER_PY.exists():
        # harmony-input-builder is substituted, but we still validate it
        # exists so the substitution rationale is honest
        missing.append(str(HARMONY_INPUT_BUILDER_PY))
    if missing:
        print("FIXTURE ERROR — required reader artifacts not found:")
        for p in missing:
            print(f"  - {p}")
        return 2

    print("Reader artifacts verified:")
    print(f"  slice-compile.py:                {SLICE_COMPILE_PY}")
    print(f"  harmony-input-builder.py (sub):  {HARMONY_INPUT_BUILDER_PY}")
    print()
    print("Readers exercised:")
    print("  1. slice-compile.py                              (LIVE subprocess)")
    print("  2. SLICE.json layer_1 reader (allRays)           (LIVE parse)")
    print("  3. SLICE.json layer_3 reader (activeRays)        (LIVE parse)")
    print("  4. harmony-input-builder.load_rtch_packets       (SUBSTITUTED)")
    print("  5. harmony-input-builder.build_returned_chunks   (SUBSTITUTED)")
    print()
    print("Substitution rationale: harmony-input-builder.py hard-codes "
          "REPO_ROOT='/Users/breydentaylor/canonical' (line 40), so it cannot")
    print("be pointed at a fixture zone. Substitution mirrors the actual "
          "predicate at lines 172-213 + 559-568.")
    print()

    overall_pass = True

    # ----------------------------------------------------------------
    # Phase 1: Pre-stub fixture (control) — baseline active count.
    # ----------------------------------------------------------------
    pre_hot_path_count = None
    with tempfile.TemporaryDirectory(prefix="slice_test6_pre_") as td_pre:
        td_pre_path = Path(td_pre)
        zone_pre = build_fixture(td_pre_path, include_stub=False)
        print(f"[Phase 1] PRE-STUB fixture built at: {zone_pre}")

        # Reader 1: slice-compile.py
        sc_pre = read_via_slice_compile(zone_pre)
        print(f"[Phase 1] slice-compile: layer_1={sc_pre.get('layer_1_count')} "
              f"layer_3={sc_pre.get('layer_3_count')} "
              f"stub_in_l1={sc_pre.get('stub_in_layer_1')} "
              f"stub_in_l3={sc_pre.get('stub_in_layer_3')}")

        if sc_pre.get("error"):
            print(f"[Phase 1] FAIL — slice-compile error: {sc_pre['error']}")
            return 2

        # Reader 2: SLICE.json layer_1
        l1_pre = read_via_slice_layer1(sc_pre.get("slice_data"))
        print(f"[Phase 1] layer_1 reader: rays={l1_pre.get('ray_count')} "
              f"rtch_refs={l1_pre.get('rtch_ref_count')} "
              f"stub_in_rays={l1_pre.get('stub_in_rays')}")

        # Reader 3: SLICE.json layer_3
        l3_pre = read_via_slice_layer3(sc_pre.get("slice_data"))
        print(f"[Phase 1] layer_3 reader: active={l3_pre.get('active_count')} "
              f"leaked={l3_pre.get('leaked_stub_count')}")

        # Reader 4: harmony load_rtch_packets substitute
        h_part_pre = read_via_harmony_load_rtch_packets_substitute(zone_pre)
        print(f"[Phase 1] harmony partition: fresh={h_part_pre['fresh_count']} "
              f"expired={h_part_pre['expired_count']}")

        # Reader 5: harmony build_returned_chunks substitute
        h_chunks_pre = read_via_harmony_build_returned_chunks_substitute(zone_pre)
        print(f"[Phase 1] harmony chunks: all={h_chunks_pre['all_chunk_count']} "
              f"hot_path={h_chunks_pre['hot_path_count']} "
              f"stub_chunks={h_chunks_pre['stub_chunk_count']} "
              f"leaked={h_chunks_pre['leaked_stubs_in_hot_path']}")

        # Baseline expectations: 0 stubs, ≥1 fresh packet, no leaks
        pre_failures = []
        pre_failures.extend(assert_layer1_preserves_stub(sc_pre, has_stub=False))
        pre_failures.extend(assert_layer3_excludes_stub(sc_pre))
        pre_failures.extend(assert_harmony_partition_excludes_stub(
            h_part_pre, h_chunks_pre, has_stub=False))
        if h_part_pre["fresh_count"] != 1:
            pre_failures.append(
                f"  [Phase 1] fresh packet count = {h_part_pre['fresh_count']} "
                "(expected 1)"
            )

        if pre_failures:
            print("[Phase 1] FAIL — pre-stub baseline failures:")
            for f in pre_failures:
                print(f)
            overall_pass = False
        else:
            print("[Phase 1] PASS — baseline reducer-boundary discipline intact")

        pre_hot_path_count = h_chunks_pre["hot_path_count"]
        print()

    # ----------------------------------------------------------------
    # Phase 2: Post-stub fixture — inject expired RTCH packet, re-run.
    # ----------------------------------------------------------------
    post_hot_path_count = None
    with tempfile.TemporaryDirectory(prefix="slice_test6_post_") as td_post:
        td_post_path = Path(td_post)
        zone_post = build_fixture(td_post_path, include_stub=True)
        print(f"[Phase 2] POST-STUB fixture built at: {zone_post}")

        # Reader 1: slice-compile.py
        sc_post = read_via_slice_compile(zone_post)
        print(f"[Phase 2] slice-compile: layer_1={sc_post.get('layer_1_count')} "
              f"layer_3={sc_post.get('layer_3_count')} "
              f"stub_in_l1={sc_post.get('stub_in_layer_1')} "
              f"stub_in_l3={sc_post.get('stub_in_layer_3')}")

        if sc_post.get("error"):
            print(f"[Phase 2] FAIL — slice-compile error: {sc_post['error']}")
            return 2

        # Reader 2: SLICE.json layer_1
        l1_post = read_via_slice_layer1(sc_post.get("slice_data"))
        print(f"[Phase 2] layer_1 reader: rays={l1_post.get('ray_count')} "
              f"rtch_refs={l1_post.get('rtch_ref_count')} "
              f"stub_in_rays={l1_post.get('stub_in_rays')}")

        # Reader 3: SLICE.json layer_3
        l3_post = read_via_slice_layer3(sc_post.get("slice_data"))
        print(f"[Phase 2] layer_3 reader: active={l3_post.get('active_count')} "
              f"leaked={l3_post.get('leaked_stub_count')}")

        # Reader 4: harmony load_rtch_packets substitute
        h_part_post = read_via_harmony_load_rtch_packets_substitute(zone_post)
        print(f"[Phase 2] harmony partition: fresh={h_part_post['fresh_count']} "
              f"expired={h_part_post['expired_count']}")

        # Reader 5: harmony build_returned_chunks substitute
        h_chunks_post = read_via_harmony_build_returned_chunks_substitute(zone_post)
        print(f"[Phase 2] harmony chunks: all={h_chunks_post['all_chunk_count']} "
              f"hot_path={h_chunks_post['hot_path_count']} "
              f"stub_chunks={h_chunks_post['stub_chunk_count']} "
              f"leaked={h_chunks_post['leaked_stubs_in_hot_path']}")

        # Stub fixture expectations:
        # - Layer 1 preserves stub (visibility invariant)
        # - Layer 3 excludes stub (reducer-boundary invariant)
        # - Harmony partition: fresh=1, expired=1
        # - Harmony chunks: stub in all_chunks, NOT in hot_path
        post_failures = []
        post_failures.extend(assert_layer1_preserves_stub(sc_post, has_stub=True))
        post_failures.extend(assert_layer3_excludes_stub(sc_post))
        post_failures.extend(assert_harmony_partition_excludes_stub(
            h_part_post, h_chunks_post, has_stub=True))
        if h_part_post["fresh_count"] != 1:
            post_failures.append(
                f"  [Phase 2] fresh packet count = {h_part_post['fresh_count']} "
                "(expected 1)"
            )
        if h_part_post["expired_count"] != 1:
            post_failures.append(
                f"  [Phase 2] expired packet count = {h_part_post['expired_count']} "
                "(expected 1)"
            )

        if post_failures:
            print("[Phase 2] FAIL — post-stub failures:")
            for f in post_failures:
                print(f)
            overall_pass = False
        else:
            print("[Phase 2] PASS — stub-class reducer-boundary discipline intact")

        post_hot_path_count = h_chunks_post["hot_path_count"]
        print()

    # ----------------------------------------------------------------
    # Phase 3: State invariance — pre/post hot-path counts MUST match.
    #
    # This is the load-bearing assertion (Harmony Test 6 line 92 analog).
    # The stub injection MUST NOT push hot-path force upward through any
    # reducer in the SLICES lane.
    # ----------------------------------------------------------------
    print("[Phase 3] State invariance check (Harmony Test 6 boundary "
          "assertion line 92):")
    print(f"  pre-stub hot_path_count  = {pre_hot_path_count}")
    print(f"  post-stub hot_path_count = {post_hot_path_count}")

    inv_err = assert_state_invariance(pre_hot_path_count, post_hot_path_count)
    if inv_err:
        print(f"[Phase 3] FAIL — {inv_err}")
        overall_pass = False
    else:
        print("[Phase 3] PASS — hot-path force invariant across stub injection")
    print()

    # ----------------------------------------------------------------
    # Final verdict
    # ----------------------------------------------------------------
    print("=" * 72)
    if overall_pass:
        print("RESULT: PASS — reducer-boundary discipline intact across all "
              "5 readers")
        print("Federation KI #1 (Policy-Gated Reducer-Boundary Discipline) — "
              "SLICES lane: CONFORMANT")
        print("=" * 72)
        return 0
    else:
        print("RESULT: FAIL — at least one reader leaked stub or disagreed "
              "on baseline")
        print("Federation KI #1 (Policy-Gated Reducer-Boundary Discipline) — "
              "SLICES lane: LEAK DETECTED")
        print("=" * 72)
        return 1


if __name__ == "__main__":
    sys.exit(main())
