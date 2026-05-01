#!/usr/bin/env python3
"""
Bench Packet Prep — pre-review dossier builder for /review sessions.

Cross-references pending CogPRs against promoted doctrine, sibling CogPRs,
active signals, and recent promotions. Outputs a structured bench packet
that gives the reviewer context for each pending item.

Output: audit-logs/mogul/bench-packets/latest.json

Usage:
    python3 bench-packet-prep.py --project-dir /path/to/zone
    python3 bench-packet-prep.py --project-dir /path/to/zone --dry-run
    python3 bench-packet-prep.py --project-dir /path/to/zone --json
    python3 bench-packet-prep.py --help
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, birth_topology


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

# Terminal-state set: once an id has reached one of these, the canonical
# state IS that terminal entry — even if a later "extracted" row appears
# (e.g., from re-extraction after schema change). The terminal-state valve
# protects bench-packet from surfacing settled CPRs as live candidates.
TERMINAL_STATUSES = frozenset({
    "promoted", "absorbed", "superseded", "rejected",
    "deferred", "dismissed", "resolved", "skipped",
})


def load_queue(queue_path):
    """Load CPR queue with terminal-state preference.

    For each id, returns:
      - the LATEST entry whose status is in TERMINAL_STATUSES, if any exist
      - otherwise the latest entry overall (preserves the prior
        latest-entry-per-id-wins behaviour for non-terminal ids)

    This prevents a later duplicate-extracted row from masking an already-
    settled disposition. Born from the bug minted as
    cpr_bench_packet_must_filter_by_latest_non_extracted_status_tic183.
    """
    p = Path(queue_path)
    if not p.exists():
        return {}

    by_id = {}  # id -> list of entries in append order
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        eid = d.get("id", "")
        if eid:
            by_id.setdefault(eid, []).append(d)

    canonical = {}
    for eid, entries_list in by_id.items():
        terminal_entries = [
            e for e in entries_list
            if e.get("status", "") in TERMINAL_STATUSES
        ]
        if terminal_entries:
            # Latest terminal entry is the canonical disposition
            canonical[eid] = terminal_entries[-1]
        else:
            # No terminal yet — fall back to latest overall
            canonical[eid] = entries_list[-1]
    return canonical


def load_signal_store(signal_dir):
    """Load signal state from active-manifest.jsonl (authoritative curated truth).
    Falls back to scanning all JSONL files if manifest doesn't exist."""
    entries = {}
    sd = Path(signal_dir)
    if not sd.exists():
        return entries
    manifest = sd / "active-manifest.jsonl"
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                sid = d.get("signal_id", d.get("id", ""))
                if sid:
                    entries[sid] = d
            except json.JSONDecodeError:
                continue
        return entries
    # Fallback: scan daily logs (less reliable, may include resolved signals)
    for f in sorted(sd.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                sid = d.get("id", "")
                if sid:
                    entries[sid] = d
            except json.JSONDecodeError:
                continue
    return entries


def count_physical_tics(audit_logs_path):
    """Count physical tics from tic event JSONL files (authoritative count)."""
    tic_dir = Path(audit_logs_path) / "tics"
    if not tic_dir.exists():
        return 0
    max_counter = 0
    for f in sorted(tic_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if d.get("type") == "tic" and d.get("count_mode") != "ignored":
                    gc = d.get("global_counter_after", 0)
                    if gc > max_counter:
                        max_counter = gc
            except json.JSONDecodeError:
                continue
    return max_counter


def find_claude_md_chain(zone_root):
    """Walk the CLAUDE.md chain from zone root upward through rung topology."""
    chain = []
    # Zone root CLAUDE.md
    root_cmd = Path(zone_root) / "CLAUDE.md"
    if root_cmd.exists():
        chain.append(str(root_cmd))

    # Walk upward for estate/federation CLAUDE.md
    d = Path(zone_root).parent
    while d != d.parent:
        cmd = d / "CLAUDE.md"
        if cmd.exists():
            chain.append(str(cmd))
        d = d.parent

    # Global CLAUDE.md
    global_cmd = Path.home() / ".claude" / "CLAUDE.md"
    if global_cmd.exists():
        chain.append(str(global_cmd))

    return chain


def extract_promoted_ids(claude_md_paths):
    """Scan CLAUDE.md files for CogPR references to find what's been promoted."""
    promoted = set()
    pattern = re.compile(r"CogPR-(\d+)")
    for path in claude_md_paths:
        try:
            content = Path(path).read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                promoted.add(f"CogPR-{match.group(1)}")
        except (OSError, UnicodeDecodeError):
            continue
    return promoted


# ---------------------------------------------------------------------------
# Enrichment artifact loading (Tier 1 metadata-enrichment swarm output, tic 207)
# ---------------------------------------------------------------------------

# Key axes from schema v2 to surface in dossiers as decision-support evidence.
# These are the axes that, when present in agreements, materially inform a
# /review verdict (lesson_class drives doctrine routing; certainty_axis drives
# confidence; scope_axis drives applicability).
KEY_ENRICHMENT_AXES = (
    "lesson_class",
    "speculative_applicability.scope_axis",
    "speculative_applicability.certainty_axis",
    "birth_slice.harmony_disposition_at_birth.stance",
    "birth_slice.harmony_disposition_at_birth.meaning_state",
    "birth_slice.mode",
    "birth_slice.posture",
    "birth_slice.birth_evidence_anchor",
)


def load_enrichment_artifacts(audit_logs_path):
    """Load consolidated enrichment atoms keyed by record_id.

    Source: audit-logs/governance/enrichment/<record_id>.consolidated.json
    Authored by the Tier 1 metadata-enrichment swarm at tic 207 under
    SCHEMA-tic208-v2.md.
    """
    enrichment_dir = Path(audit_logs_path) / "governance" / "enrichment"
    if not enrichment_dir.exists():
        return {}

    artifacts = {}
    for f in sorted(enrichment_dir.glob("*.consolidated.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rid = data.get("record_id")
        if not rid:
            continue
        key_agreements = {}
        for agreement in data.get("agreements", []):
            axis = agreement.get("axis", "")
            if axis in KEY_ENRICHMENT_AXES:
                key_agreements[axis] = agreement.get("value")
        artifacts[rid] = {
            "consolidated_path": str(f.relative_to(audit_logs_path)),
            "consolidated_at_tic": data.get("consolidated_at_tic"),
            "agreements_count": data.get("agreements_count", 0),
            "divergences_count": data.get("divergences_count", 0),
            "lens_a_path": data.get("lens_a_path", ""),
            "lens_b_path": data.get("lens_b_path", ""),
            "key_agreements": key_agreements,
        }
    return artifacts


def load_enrichment_hotspots(audit_logs_path):
    """Load conflict hotspots grouped by record_id.

    Each entry is a per-axis disagreement between lens-A (Harmony-disposition
    emphasis) and lens-B (temporal-pressure emphasis). Hotspots ARE the
    "patterns in processing" — surfacing them per pending CPR gives the
    reviewer the conflict surfaces the swarm found.
    """
    enrichment_dir = Path(audit_logs_path) / "governance" / "enrichment"
    if not enrichment_dir.exists():
        return {}

    by_record = {}
    for f in sorted(enrichment_dir.glob("conflict-hotspots-*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = d.get("record_id")
            if not rid:
                continue
            by_record.setdefault(rid, []).append({
                "axis": d.get("axis", ""),
                "lens_a_value": d.get("lens_a_value"),
                "lens_b_value": d.get("lens_b_value"),
                "kind": d.get("kind", ""),
                "magnitude": d.get("magnitude"),
                "tier": d.get("tier", ""),
            })
    return by_record


def discover_synthesis_refs(audit_logs_path):
    """List enrichment-swarm synthesis documents available to the reviewer."""
    enrichment_dir = Path(audit_logs_path) / "governance" / "enrichment"
    if not enrichment_dir.exists():
        return []
    refs = []
    for pattern in ("SCHEMA-*.md", "TIER*-SYNTHESIS-*.md", "SCHEMA-FRICTION-*.md",
                    "source-fidelity-correction-*.md"):
        for f in sorted(enrichment_dir.glob(pattern)):
            refs.append(str(f.relative_to(audit_logs_path)))
    return refs


# ---------------------------------------------------------------------------
# Bench packet assembly
# ---------------------------------------------------------------------------

def get_pending_cprs(queue):
    """Filter to CPRs eligible for review."""
    review_statuses = {
        "pending", "enrichment_needed", "enrichment_eligible",
        "extracted", "review_ready",
    }
    return {
        eid: entry for eid, entry in queue.items()
        if entry.get("status") in review_statuses
    }


def get_recently_promoted(queue):
    """Find CPRs that were recently promoted (for context)."""
    return {
        eid: entry for eid, entry in queue.items()
        if entry.get("status") == "promoted"
    }


def find_related_cprs(cpr, all_cprs):
    """Find CPRs with overlapping subsystem or lesson similarity."""
    related = []
    subsystem = cpr.get("subsystem", "")
    lesson = cpr.get("lesson", "")
    cpr_id = cpr.get("id", "")
    lesson_words = set(lesson.lower().split()) if lesson else set()

    for eid, entry in all_cprs.items():
        if eid == cpr_id:
            continue
        # Same subsystem
        if subsystem and entry.get("subsystem") == subsystem:
            related.append({"id": eid, "relation": "same_subsystem"})
            continue
        # Word overlap
        other_words = set(entry.get("lesson", "").lower().split())
        if lesson_words and other_words:
            overlap = len(lesson_words & other_words) / max(len(lesson_words | other_words), 1)
            if overlap >= 0.3:
                related.append({"id": eid, "relation": "lesson_overlap", "overlap": round(overlap, 3)})

    return related[:10]


def find_related_signals(cpr, signals):
    """Find active signals related to this CPR."""
    related = []
    subsystem = cpr.get("subsystem", "")
    if not subsystem:
        return related

    for sid, sig in signals.items():
        if sig.get("subsystem") == subsystem and sig.get("status") in ("active", "working", "acknowledged"):
            related.append({
                "id": sid,
                "kind": sig.get("kind", ""),
                "volume": sig.get("volume", 0),
            })

    return related[:5]


def build_bench_packet(project_dir, dry_run=False):
    """Build the full bench packet."""
    project_dir = os.path.abspath(project_dir)
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)
    topo = birth_topology(project_dir)

    queue_path = os.path.join(al_path, "cprs", "queue.jsonl")
    signal_dir = os.path.join(al_path, "signals")

    queue = load_queue(queue_path)
    signals = load_signal_store(signal_dir)
    claude_md_chain = find_claude_md_chain(project_dir)
    already_promoted_refs = extract_promoted_ids(claude_md_chain)

    # Tier 1 enrichment swarm artifacts (tic 207). Loading is best-effort —
    # absence is normal in zones that haven't run the swarm.
    enrichment_artifacts = load_enrichment_artifacts(al_path)
    enrichment_hotspots = load_enrichment_hotspots(al_path)
    synthesis_refs = discover_synthesis_refs(al_path)

    pending = get_pending_cprs(queue)
    recently_promoted = get_recently_promoted(queue)

    # Get current tic from physical tic event count (authoritative)
    tic = count_physical_tics(al_path)

    # Build per-CPR dossier
    pending_cogprs = []
    for cpr_id, cpr in sorted(pending.items(), key=lambda x: x[1].get("birth_tic", 0)):
        related = find_related_cprs(cpr, queue)
        related_signals = find_related_signals(cpr, signals)

        # Check if a CogPR reference already exists in doctrine
        cpr_num = re.search(r"CogPR-(\d+)", cpr_id)
        doctrine_ref = cpr_id in already_promoted_refs if cpr_num else False

        # Tier 1 enrichment evidence — surface the swarm's per-record findings
        # so reviewers get lesson_class, scope_axis, certainty_axis as decision
        # support rather than re-deriving them. Absent for CPRs not in the
        # tic 207 swarm corpus (which is normal — only 77 of N pending were
        # processed).
        enrichment_evidence = enrichment_artifacts.get(cpr_id, {})
        cpr_hotspots = enrichment_hotspots.get(cpr_id, [])

        dossier = {
            "id": cpr_id,
            "lesson": cpr.get("lesson", ""),
            "birth_tic": cpr.get("birth_tic", 0),
            "status": cpr.get("status", ""),
            "band": cpr.get("band", "COGNITIVE"),
            "subsystem": cpr.get("subsystem", ""),
            "recommended_scopes": cpr.get("recommended_scopes", []),
            "review_hints": cpr.get("review_hints", ""),
            # Enrichment fields — preserved end-to-end so reviewers see
            # the evidence cpr-enrichment-scanner gathered, not just the
            # confidence score. The full set is the same as ripple-assessor's
            # passthrough (conductor-score-runtime parity, single source).
            "enrichment": cpr.get("enrichment", []),
            "enrichment_confidence": cpr.get("enrichment_confidence"),
            "enrichment_scanned_at": cpr.get("enrichment_scanned_at"),
            "enrichment_scan_count": cpr.get("enrichment_scan_count", 0),
            "enrichment_rung": cpr.get("enrichment_rung"),
            "no_evidence_reason": cpr.get("no_evidence_reason"),
            "pending_class": cpr.get("pending_class"),
            "maturity_window_tics": cpr.get("maturity_window_tics"),
            "regression_count": cpr.get("regression_count", 0),
            "lesson_type": cpr.get("lesson_type"),
            "confidence_tier": cpr.get("confidence_tier"),
            "origin_context": cpr.get("origin_context"),
            "relations": {
                "sibling_cprs": related,
                "active_signals": related_signals,
                "already_in_doctrine": doctrine_ref,
                "queue_relations": cpr.get("relations", {}),
            },
            "enrichment_evidence": enrichment_evidence if enrichment_evidence else None,
            "enrichment_hotspots": cpr_hotspots,
        }
        pending_cogprs.append(dossier)

    # Active signals summary
    active_signals = [
        {
            "id": sid,
            "kind": sig.get("kind", ""),
            "subsystem": sig.get("subsystem", ""),
            "volume": sig.get("volume", 0),
            "status": sig.get("status", ""),
        }
        for sid, sig in signals.items()
        if sig.get("status") in ("active", "working", "acknowledged")
    ]

    # Recently promoted (for reviewer awareness)
    promoted_since = [
        {
            "id": eid,
            "lesson": entry.get("lesson", "")[:100],
            "promoted_at_tic": entry.get("review_tic", entry.get("birth_tic", 0)),
        }
        for eid, entry in recently_promoted.items()
    ]

    # Recommended review order: enrichment confidence desc, then birth_tic asc.
    # Tiebreak: prefer pending CPRs that have schema-v2 enrichment evidence
    # (Tier 1 swarm coverage) over those without — the swarm-covered ones have
    # decision-support data the reviewer can lean on.
    def review_sort_key(c):
        conf = -(c.get("enrichment_confidence") or 0)
        has_swarm = 0 if c.get("enrichment_evidence") else 1  # 0 sorts first
        return (conf, has_swarm, c.get("birth_tic", 0))

    review_order = sorted(pending_cogprs, key=review_sort_key)

    # Cluster pending CPRs by lesson_class (from enrichment evidence) to give
    # the reviewer recommended cluster geometries for batch processing. CPRs
    # without enrichment evidence land in the "uncovered" bucket — these need
    # foreground judgment without swarm decision support.
    clusters = {
        "doctrinal": [],
        "engineering": [],
        "capacity_demonstration": [],
        "paradigm_locked": [],
        "uncovered": [],
        "other": [],
    }
    for c in pending_cogprs:
        ev = c.get("enrichment_evidence")
        if not ev:
            clusters["uncovered"].append(c["id"])
            continue
        lesson_class = ev.get("key_agreements", {}).get("lesson_class")
        bucket = lesson_class if lesson_class in clusters else "other"
        clusters[bucket].append(c["id"])

    # Enrichment coverage stats
    pending_with_enrichment = sum(1 for c in pending_cogprs if c.get("enrichment_evidence"))
    enrichment_coverage_pct = (
        round(100 * pending_with_enrichment / len(pending_cogprs), 1)
        if pending_cogprs else 0.0
    )

    packet = {
        "tic": tic,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "birth_rung": topo["birth_rung"],
        "pending_cogprs": pending_cogprs,
        "active_signals": active_signals,
        "promoted_since_last_review": promoted_since,
        "recommended_review_order": [c["id"] for c in review_order],
        # Enrichment-aware metadata (Tier 1 swarm output, tic 207).
        # Synthesis refs point reviewers to ground material when a verdict
        # benefits from broader context than the per-CPR dossier carries.
        "enrichment_metadata": {
            "synthesis_refs": synthesis_refs,
            "coverage_pct": enrichment_coverage_pct,
            "pending_with_enrichment": pending_with_enrichment,
            "pending_without_enrichment": len(pending_cogprs) - pending_with_enrichment,
            "total_hotspots": sum(len(v) for v in enrichment_hotspots.values()),
            "schema_version": "SCHEMA-tic208-v2 (LOCKED at tic 207)",
        },
        "review_clusters": {
            "doctrinal": clusters["doctrinal"],
            "engineering": clusters["engineering"],
            "capacity_demonstration": clusters["capacity_demonstration"],
            "paradigm_locked": clusters["paradigm_locked"],
            "uncovered": clusters["uncovered"],
            "other": clusters["other"],
        },
        "summary": {
            "total_pending": len(pending_cogprs),
            "total_active_signals": len(active_signals),
            "total_recently_promoted": len(promoted_since),
            "enrichment_covered": pending_with_enrichment,
            "enrichment_coverage_pct": enrichment_coverage_pct,
        },
    }

    if not dry_run:
        bench_dir = os.path.join(al_path, "mogul", "bench-packets")
        os.makedirs(bench_dir, exist_ok=True)
        output_path = os.path.join(bench_dir, "latest.json")
        Path(output_path).write_text(json.dumps(packet, indent=2), encoding="utf-8")

    return packet


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Bench Packet Prep — pre-review dossier builder"
    )
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build packet without writing to disk")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Output structured JSON to stdout")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    project_dir = args.project_dir or resolve_zone_root()
    packet = build_bench_packet(project_dir, dry_run=args.dry_run)

    if args.output_json:
        print(json.dumps(packet, indent=2))
    elif not args.quiet:
        s = packet["summary"]
        print(f"Bench packet: {s['total_pending']} pending, "
              f"{s['total_active_signals']} signals, "
              f"{s['total_recently_promoted']} recently promoted")
        print(f"Enrichment coverage: {s['enrichment_covered']}/{s['total_pending']} "
              f"({s['enrichment_coverage_pct']}%)")
        clusters = packet.get("review_clusters", {})
        cluster_summary = ", ".join(
            f"{k}={len(v)}" for k, v in clusters.items() if v
        )
        if cluster_summary:
            print(f"Review clusters: {cluster_summary}")
        if packet["recommended_review_order"]:
            print(f"Review order (top 5): {', '.join(packet['recommended_review_order'][:5])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
