#!/usr/bin/env python3
"""slice-compile.py — Federation slice compiler (Ship 3)

Implements the Slice as Bounded World Preservation construct
(cpr_slice_as_bounded_world_preservation_tic223) with the Packet Slice Rule
(cpr_packet_slice_projection_rule_tic225) projection.

A federation slice is bounded preservation of world-state at a tic, NOT a
summary. The compiler walks tic-keyed verbatim feeds and produces a SLICE.json
manifest that indexes them by reference (path + size + sha256 + mtime).

Three-layer architecture (cpr_three_layer_terrain_architecture_tic223):
  Layer 1 — verbatim refs:    append-preserved emission paths + hashes
  Layer 2 — projection:       navigable handles (counts, status fields, refs)
  Layer 3 — hot-path stubs:   current active pressure (decision dumps, packets)

TTL governance (cpr_ttl_governs_heat_not_memory_tic223): TTL acts on Layer 3
hot-path stubs only. Layer 1 verbatim refs are invariant — never deleted.

Read-only on all source feeds. Writes only to audit-logs/slices/tic-N/SLICE.json
(creates parent directories as needed).

Usage:
  python3 slice-compile.py --tic 225
  python3 slice-compile.py --tic 225 --zone-root /path/to/canonical
  python3 slice-compile.py --tic 225 --output /tmp/slice-225.json
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


SLICE_VERSION = "1.0"
DEFAULT_PACKET_TTL_TICS = 30  # per RTCH binder Q.3 + ttl_governs_heat_not_memory


def find_zone_root(start: Path) -> Path:
    """Walk up looking for federation root markers."""
    p = start.resolve()
    while p != p.parent:
        if (p / ".federation-root").exists() or (p / ".ticzone").exists():
            return p
        # canonical/ is the federation; check for the audit-logs/ + autonomous_kernel/ pair
        if (p / "audit-logs").is_dir() and (p / "autonomous_kernel").is_dir():
            return p
        p = p.parent
    raise SystemExit(f"could not locate zone root from {start}")


def hash_file(path: Path, max_bytes: int = 50 * 1024 * 1024) -> str:
    """sha256 of file content, capped to avoid OOM on huge files."""
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                # large-file marker; not a real hash
                return f"sha256:partial-over-{max_bytes}"
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def file_ref(path: Path, zone: Path, kind: str, **extra) -> dict:
    """Build a Layer-1 verbatim ref entry."""
    if not path.exists():
        return None
    rel = str(path.relative_to(zone)) if path.is_absolute() else str(path)
    stat = path.stat()
    ref = {
        "kind": kind,
        "path": rel,
        "size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "sha256": hash_file(path),
    }
    ref.update(extra)
    return ref


def scan_tic_event(zone: Path, tic: int) -> tuple[list, dict]:
    """Find the counted tic event for this tic across all daily files."""
    refs = []
    projection = None
    tics_dir = zone / "audit-logs" / "tics"
    if not tics_dir.exists():
        return refs, projection
    for daily in sorted(tics_dir.glob("*.jsonl")):
        with daily.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "tic" and ev.get("domain_counter_after") == tic:
                    refs.append(file_ref(daily, zone, "tic_event_log"))
                    projection = {
                        "type": ev.get("type"),
                        "tic_zone": ev.get("tic_zone"),
                        "cadence_position": ev.get("cadence_position"),
                        "count_mode": ev.get("count_mode"),
                        "count_reason": ev.get("count_reason"),
                        "domain_counter_after": ev.get("domain_counter_after"),
                        "global_counter_after": ev.get("global_counter_after"),
                        "iso_timestamp": ev.get("tic"),
                    }
                    break
            if projection:
                break
    return refs, projection


def scan_conformation(zone: Path, tic: int) -> tuple[list, dict]:
    """audit-logs/conformations/tic-N.json — exact filename."""
    refs, projection = [], None
    p = zone / "audit-logs" / "conformations" / f"tic-{tic}.json"
    if p.exists():
        refs.append(file_ref(p, zone, "conformation"))
        try:
            data = json.loads(p.read_text())
            projection = {
                "active_signals": len(data.get("active_signals", [])),
                "active_warrants": len(data.get("active_warrants", [])),
                "pending_cprs": data.get("pending_cprs"),
                "tic": data.get("tic"),
                "generated_at": data.get("generated_at"),
            }
        except (json.JSONDecodeError, OSError):
            pass
    return refs, projection


def scan_harmony(zone: Path, tic: int) -> list:
    """harmony disposition + input (if produced this tic)."""
    refs = []
    h = zone / "audit-logs" / "harmony"
    for stem in ("disposition", "input"):
        p = h / f"{stem}-tic-{tic}.json"
        if p.exists():
            refs.append(file_ref(p, zone, f"harmony_{stem}"))
    return refs


def scan_mogul(zone: Path, tic: int) -> tuple[list, dict]:
    """Mogul cycle reports + transcripts + mandate history (filtered by tic)."""
    refs = []
    projection = {}
    reports_dir = zone / "audit-logs" / "mogul" / "cycle-reports" / "reports"
    transcripts_dir = zone / "audit-logs" / "mogul" / "cycle-reports" / "transcripts"
    if reports_dir.exists():
        for p in reports_dir.glob(f"*-tic-{tic}.report.json"):
            refs.append(file_ref(p, zone, "mogul_cycle_report"))
            try:
                data = json.loads(p.read_text())
                projection["cycle_report_summary"] = {
                    "mandate_id": data.get("mandate_id"),
                    "cycles_executed": data.get("cycles_executed", []),
                    "synthesis_posture": (data.get("synthesis") or {}).get("posture"),
                }
            except (json.JSONDecodeError, OSError):
                pass
    if transcripts_dir.exists():
        for p in transcripts_dir.glob(f"*-tic-{tic}.json"):
            refs.append(file_ref(p, zone, "mogul_transcript"))

    # Mandate history: filter by mandate_id containing tic-N-
    mandate_history = zone / "audit-logs" / "mogul" / "mandates" / "history"
    if mandate_history.exists():
        mandate_records = []
        for daily in sorted(mandate_history.glob("*.jsonl")):
            with daily.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    mid = rec.get("mandate_id", "")
                    if mid.startswith(f"tic-{tic}-"):
                        mandate_records.append({
                            "mandate_id": mid,
                            "status": rec.get("status"),
                            "cycles": rec.get("cycle_request", {}).get("run_now", []),
                            "source_daily": str(daily.relative_to(zone)),
                        })
        if mandate_records:
            projection["mandate_records"] = mandate_records

    # Current mandate (if it's for this tic)
    current = zone / "audit-logs" / "mogul" / "mandates" / "current.json"
    if current.exists():
        try:
            data = json.loads(current.read_text())
            mid = data.get("mandate_id", "")
            if mid.startswith(f"tic-{tic}-"):
                refs.append(file_ref(current, zone, "mogul_current_mandate"))
                projection["current_mandate"] = {
                    "mandate_id": mid,
                    "status": data.get("status"),
                    "cycles": data.get("cycle_request", {}).get("run_now", []),
                    "supersedes": data.get("supersedes", []),
                }
        except (json.JSONDecodeError, OSError):
            pass

    return refs, projection


def scan_routing_decisions(zone: Path, tic: int) -> tuple[list, list]:
    """Routing decisions emitted at this tic."""
    refs = []
    entries = []
    rd = zone / "audit-logs" / "routing" / "decisions.jsonl"
    if not rd.exists():
        return refs, entries
    refs.append(file_ref(rd, zone, "routing_decisions_ledger"))
    with rd.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("tic") == tic:
                entries.append({
                    "decision_id": rec.get("decision_id"),
                    "actor": rec.get("actor"),
                    "intake_class": (rec.get("input") or {}).get("intake_class"),
                    "weight": (rec.get("input") or {}).get("weight"),
                    "outcome_status": rec.get("outcome", {}).get("status") if isinstance(rec.get("outcome"), dict) else None,
                })
    return refs, entries


def scan_governance_packets(zone: Path, tic: int) -> list:
    """audit-logs/governance/*tic{N}*.md — packets emitted at or for this tic."""
    refs = []
    g = zone / "audit-logs" / "governance"
    if not g.exists():
        return refs
    # match tic-N or ticN suffix variants
    patterns = [f"*tic{tic}*", f"*tic-{tic}*"]
    seen = set()
    for pat in patterns:
        for p in g.glob(pat):
            if p in seen or not p.is_file():
                continue
            seen.add(p)
            refs.append(file_ref(p, zone, "governance_packet"))
    return refs


def scan_agent_mailboxes_at_tic(zone: Path, tic: int) -> list:
    """Mailbox envelopes whose lifecycle source_tic equals this tic, plus
    inbound dumps that name the tic in the filename."""
    refs = []
    mb = zone / "audit-logs" / "agent-mailboxes"
    if not mb.exists():
        return refs
    seen = set()
    # Envelope-bearing dirs
    for envelope in mb.glob("*/inbound/WAIT_*/envelope.json"):
        try:
            data = json.loads(envelope.read_text())
            src_tic = (data.get("lifecycle") or {}).get("source_tic")
            if src_tic == tic:
                if envelope not in seen:
                    seen.add(envelope)
                    refs.append(file_ref(envelope, zone, "mailbox_envelope",
                                         message_id=data.get("message_id"),
                                         category=(data.get("routing") or {}).get("category")))
        except (json.JSONDecodeError, OSError):
            continue
    # Loose-named WAIT envelopes (e.g., WAIT_normal_*_t223_*.json)
    for envelope in mb.glob(f"*/inbound/WAIT_*_t{tic}_*.json"):
        if envelope in seen:
            continue
        seen.add(envelope)
        refs.append(file_ref(envelope, zone, "mailbox_envelope_loose"))
    # Inbound dumps with tic in filename (e.g., decision dump).
    # /review dumps are commonly emitted AT tic N AND named FOR tic N+1
    # (e.g., "architect-routing-decisions-tic226-review-dump.md" emitted at
    # tic 225 for the tic 226 /review pass per Post-Cadence Clean-Close Ordering).
    # Capture both N and N+1 patterns; downstream tic slices will not double-count
    # because the per-tic dedup is by path.
    for variant in (tic, tic + 1):
        for pat in (f"*/inbound/*tic{variant}*", f"*/inbound/*tic-{variant}*"):
            for p in mb.glob(pat):
                if p in seen or not p.is_file():
                    continue
                seen.add(p)
                kind = "mailbox_inbound_dump_forward" if variant == tic + 1 else "mailbox_inbound_dump"
                refs.append(file_ref(p, zone, kind, names_tic=variant))
    return refs


def scan_signals_emitted(zone: Path, tic: int) -> list:
    """Daily signal files containing emissions for this tic."""
    refs = []
    sd = zone / "audit-logs" / "signals"
    if not sd.exists():
        return refs
    matches = set()
    for daily in sd.glob("*.jsonl"):
        with daily.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("tic") == tic:
                    matches.add(daily)
                    break
    for daily in sorted(matches):
        refs.append(file_ref(daily, zone, "signals_daily_emit_includes_tic"))
    return refs


def scan_rtch_packets(zone: Path) -> list:
    """RTCH packets — track all in case any are referenced as past-slice material."""
    refs = []
    rd = zone / "audit-logs" / "rtch" / "packets"
    if not rd.exists():
        return refs
    for p in sorted(rd.glob("*.json")):
        refs.append(file_ref(p, zone, "rtch_packet"))
    return refs


def scan_cprs_birthed(zone: Path, tic: int) -> tuple[list, list]:
    """Queue entries with birth_tic == tic."""
    refs = []
    entries = []
    q = zone / "audit-logs" / "cprs" / "queue.jsonl"
    if not q.exists():
        return refs, entries
    refs.append(file_ref(q, zone, "cprs_queue"))
    seen_ids = set()
    with q.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("birth_tic") == tic and rec.get("type") == "cpr":
                cid = rec.get("id")
                if cid in seen_ids:
                    continue
                seen_ids.add(cid)
                entries.append({
                    "id": cid,
                    "status": rec.get("status"),
                    "tier": rec.get("tier"),
                    "recommended_scopes": rec.get("recommended_scopes", []),
                    "source": rec.get("source"),
                })
    return refs, entries


def scan_biome_cache_state(zone: Path, tic: int) -> list:
    """biome cache-state artifacts named with the tic."""
    refs = []
    base = zone / "audit-logs" / "biome" / "pen-pal-cache" / "state-artifacts"
    if not base.exists():
        return refs
    # files named <N>-cache-state.json where N is the tic context
    for n in (tic, tic - 1):  # cache-state typically writes for prior tic
        p = base / f"{n}-cache-state.json"
        if p.exists():
            refs.append(file_ref(p, zone, f"biome_cache_state_tic_{n}"))
    return refs


def compute_ttl_state(layer1_refs: list, current_tic: int, ttl: int) -> dict:
    """Compute TTL state for packet-class refs (governance_packet, mailbox_*).

    Layer 1 refs are NEVER deleted — TTL only annotates hot-path eligibility.
    """
    expired_at_tic = current_tic + ttl
    packet_kinds = {"governance_packet", "mailbox_envelope", "mailbox_envelope_loose",
                    "mailbox_inbound_dump", "rtch_packet"}
    active = []
    expired = []
    for ref in layer1_refs:
        if ref["kind"] in packet_kinds:
            # Default: assume packet emitted at current tic; expires at +ttl
            # (a richer impl would parse source_tic from the file itself)
            active.append(ref["path"])
    return {
        "default_packet_ttl_tics": ttl,
        "expired_at_tic": expired_at_tic,
        "active_packet_count": len(active),
        "expired_packet_count": len(expired),
        "rule": "TTL acts on Layer 3 hot-path eligibility only; Layer 1 refs invariant",
    }


def compose_hot_path_stubs(zone: Path, tic: int, layer1_refs: list) -> list:
    """Layer 3 — current active pressure (decision dumps, slice projections, etc.)."""
    stubs = []
    # Decision dump for upcoming /review
    for ref in layer1_refs:
        path = ref["path"]
        if "architect-routing-decisions-tic" in path:
            stubs.append({
                "kind": "decision_dump",
                "path": path,
                "ttl_state": "active",
                "scope": "11 Architect-routing decisions for /review tic 226+",
                "hot_path_action": "consume_at_review_or_per_decision_routing",
            })
        elif "civil-audit-slice-projection" in path:
            stubs.append({
                "kind": "civil_audit_slice_projection",
                "path": path,
                "ttl_state": "active",
                "decision_needed": ["C-1", "C-2", "C-3"],
                "architect_preference": "C-3",
                "current_claim_force": "allowed_for_gap_existence",
                "mutation_authority": "none",
                "hot_path_action": "route_decision_not_patch",
            })
    return stubs


def compile_slice(zone: Path, tic: int) -> dict:
    """Walk all feeds and compose the slice manifest."""
    layer1_refs = []
    layer2_projection = {}
    discovery_log = {"feeds_scanned": [], "feeds_with_artifacts": [], "feeds_empty_for_tic": []}

    feeds = [
        ("tic_event", lambda: scan_tic_event(zone, tic)),
        ("conformation", lambda: scan_conformation(zone, tic)),
        ("mogul", lambda: scan_mogul(zone, tic)),
        ("routing_decisions", lambda: scan_routing_decisions(zone, tic)),
    ]
    for name, fn in feeds:
        discovery_log["feeds_scanned"].append(name)
        refs, projection = fn()
        layer1_refs.extend(r for r in refs if r)
        if projection:
            layer2_projection[name] = projection
            discovery_log["feeds_with_artifacts"].append(name)
        elif refs:
            discovery_log["feeds_with_artifacts"].append(name)
        else:
            discovery_log["feeds_empty_for_tic"].append(name)

    # Single-output feeds
    for name, fn in [
        ("harmony", lambda: scan_harmony(zone, tic)),
        ("governance_packets", lambda: scan_governance_packets(zone, tic)),
        ("mailbox_envelopes", lambda: scan_agent_mailboxes_at_tic(zone, tic)),
        ("signals_emitted", lambda: scan_signals_emitted(zone, tic)),
        ("biome_cache_state", lambda: scan_biome_cache_state(zone, tic)),
        ("rtch_packets", lambda: scan_rtch_packets(zone)),
    ]:
        discovery_log["feeds_scanned"].append(name)
        refs = fn()
        layer1_refs.extend(r for r in refs if r)
        if refs:
            discovery_log["feeds_with_artifacts"].append(name)
        else:
            discovery_log["feeds_empty_for_tic"].append(name)

    # CPR queue (birthed at this tic)
    discovery_log["feeds_scanned"].append("cprs_birthed")
    cpr_refs, cpr_entries = scan_cprs_birthed(zone, tic)
    layer1_refs.extend(r for r in cpr_refs if r)
    if cpr_entries:
        layer2_projection["cprs_birthed_at_tic"] = cpr_entries
        discovery_log["feeds_with_artifacts"].append("cprs_birthed")
    else:
        discovery_log["feeds_empty_for_tic"].append("cprs_birthed")

    # Routing decision entries (already refs added; pull entries from feed[2])
    rd_refs, rd_entries = scan_routing_decisions(zone, tic)
    if rd_entries:
        layer2_projection["routing_decision_entries"] = rd_entries

    # Compose pointers (Layer 2 — short-cut handles)
    pointers = {}
    for ref in layer1_refs:
        kind = ref["kind"]
        if kind not in pointers:
            pointers[kind] = ref["path"]

    # Layer 3 — hot-path stubs
    layer3_stubs = compose_hot_path_stubs(zone, tic, layer1_refs)

    # TTL state
    ttl_state = compute_ttl_state(layer1_refs, tic, DEFAULT_PACKET_TTL_TICS)

    return {
        "slice_version": SLICE_VERSION,
        "tic": tic,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "compiler": "slice-compile.py",
        "compiler_lineage": [
            "cpr_three_layer_terrain_architecture_tic223",
            "cpr_ttl_governs_heat_not_memory_tic223",
            "cpr_slice_as_bounded_world_preservation_tic223",
            "cpr_packet_slice_projection_rule_tic225",
        ],
        "zone_root": str(zone),
        "layer_1_verbatim_refs": layer1_refs,
        "layer_2_projection": layer2_projection,
        "layer_3_hot_path_stubs": layer3_stubs,
        "pointers": pointers,
        "ttl_state": ttl_state,
        "discovery_log": discovery_log,
        "rule_summary": {
            "layer_1": "verbatim refs — append-preserved emission paths + hashes; INVARIANT under TTL",
            "layer_2": "projection — counts, status, navigable handles",
            "layer_3": "hot-path stubs — current active pressure; subject to TTL",
            "ttl_governs": "Layer 3 only; Layer 1 retains regardless",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Federation slice compiler (Ship 3)")
    parser.add_argument("--tic", type=int, required=True, help="Tic to compile slice for")
    parser.add_argument("--zone-root", type=str, default=None,
                        help="Federation zone root (default: discover from cwd)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output path (default: <zone>/audit-logs/slices/tic-<N>/SLICE.json)")
    parser.add_argument("--print", action="store_true",
                        help="Print summary to stdout after writing")
    args = parser.parse_args()

    if args.zone_root:
        zone = Path(args.zone_root).resolve()
    else:
        zone = find_zone_root(Path.cwd())

    slice_manifest = compile_slice(zone, args.tic)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = zone / "audit-logs" / "slices" / f"tic-{args.tic}" / "SLICE.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(slice_manifest, indent=2) + "\n")

    if args.print:
        l1 = len(slice_manifest["layer_1_verbatim_refs"])
        l2 = len(slice_manifest["layer_2_projection"])
        l3 = len(slice_manifest["layer_3_hot_path_stubs"])
        feeds_with = slice_manifest["discovery_log"]["feeds_with_artifacts"]
        print(f"slice tic={args.tic} layer1_refs={l1} layer2_keys={l2} layer3_stubs={l3} "
              f"feeds_with_artifacts={len(feeds_with)} → {out_path}")
    else:
        print(out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
