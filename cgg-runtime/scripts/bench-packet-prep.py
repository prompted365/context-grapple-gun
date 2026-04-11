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

def load_queue(queue_path):
    """Load CPR queue (latest-entry-per-ID-wins). Returns dict of id->entry."""
    entries = {}
    p = Path(queue_path)
    if not p.exists():
        return entries
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            eid = d.get("id", "")
            if eid:
                entries[eid] = d
        except json.JSONDecodeError:
            continue
    return entries


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

        dossier = {
            "id": cpr_id,
            "lesson": cpr.get("lesson", ""),
            "birth_tic": cpr.get("birth_tic", 0),
            "status": cpr.get("status", ""),
            "band": cpr.get("band", "COGNITIVE"),
            "subsystem": cpr.get("subsystem", ""),
            "recommended_scopes": cpr.get("recommended_scopes", []),
            "review_hints": cpr.get("review_hints", ""),
            "enrichment_confidence": cpr.get("enrichment_confidence"),
            "relations": {
                "sibling_cprs": related,
                "active_signals": related_signals,
                "already_in_doctrine": doctrine_ref,
            },
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

    # Recommended review order: enrichment confidence desc, then birth_tic asc
    review_order = sorted(
        pending_cogprs,
        key=lambda x: (-(x.get("enrichment_confidence") or 0), x.get("birth_tic", 0)),
    )

    packet = {
        "tic": tic,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "birth_rung": topo["birth_rung"],
        "pending_cogprs": pending_cogprs,
        "active_signals": active_signals,
        "promoted_since_last_review": promoted_since,
        "recommended_review_order": [c["id"] for c in review_order],
        "summary": {
            "total_pending": len(pending_cogprs),
            "total_active_signals": len(active_signals),
            "total_recently_promoted": len(promoted_since),
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
        print(f"Bench packet: {packet['summary']['total_pending']} pending, "
              f"{packet['summary']['total_active_signals']} signals, "
              f"{packet['summary']['total_recently_promoted']} recently promoted")
        if packet["recommended_review_order"]:
            print(f"Review order: {', '.join(packet['recommended_review_order'][:5])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
