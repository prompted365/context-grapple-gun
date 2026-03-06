#!/usr/bin/env python3
"""
Manifestation Tracker — scan promoted CPRs for downstream evidence.

Tracks post-promotion outcomes: did the promoted rule produce useful downstream
behavior, or is it accumulating strain?

Reads queue.jsonl for promoted entries, then searches for manifestation evidence:
- Signal activity referencing the promoted lesson's subsystem
- Ladder audit findings about the rule
- Observed specialization (child CLAUDE.md entries referencing the rule)
- Review-close follow-on checks that flagged strain

Outputs a JSONL manifestation report.

Usage:
    python3 manifestation-tracker.py [--project-dir PATH] [--json] [--output FILE]
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path


# ---------------------------------------------------------------------------
# Queue loading
# ---------------------------------------------------------------------------

def load_promoted_cprs(queue_path):
    """Load all promoted CPRs from queue (latest-entry-per-ID-wins)."""
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
    return {k: v for k, v in entries.items() if v.get("status") == "promoted"}


# ---------------------------------------------------------------------------
# Evidence gatherers
# ---------------------------------------------------------------------------

def gather_signal_evidence(cpr, signal_dir):
    """Check for active signals referencing the promoted lesson's subsystem."""
    evidence = []
    subsystem = cpr.get("subsystem", "")
    if not subsystem or not signal_dir.is_dir():
        return evidence

    related = []
    latest = {}
    for f in sorted(signal_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                eid = d.get("id") or d.get("signal_id")
                if eid:
                    latest[eid] = d
            except json.JSONDecodeError:
                continue

    for eid, sig in latest.items():
        if sig.get("subsystem") == subsystem and sig.get("type") == "signal":
            status = sig.get("status", "")
            if status in ("active", "working", "acknowledged"):
                related.append({
                    "signal_id": eid,
                    "kind": sig.get("kind", "?"),
                    "band": sig.get("band", "?"),
                    "volume": sig.get("volume", 0),
                    "status": status,
                })

    if related:
        # Distinguish positive vs strain signals
        tensions = [s for s in related if s["kind"] == "TENSION"]
        beacons = [s for s in related if s["kind"] == "BEACON"]

        if tensions:
            evidence.append({
                "evidence_type": "tension_signals",
                "value": f"{len(tensions)} TENSION signals in subsystem {subsystem}",
                "detail": [f"{s['signal_id']} (vol={s['volume']})" for s in tensions[:5]],
                "polarity": "strain",
            })
        if beacons:
            evidence.append({
                "evidence_type": "beacon_signals",
                "value": f"{len(beacons)} BEACON signals in subsystem {subsystem}",
                "detail": [f"{s['signal_id']} (vol={s['volume']})" for s in beacons[:5]],
                "polarity": "neutral",
            })

    return evidence


def gather_specialization_evidence(cpr, zone_root):
    """Search child CLAUDE.md files for references to the promoted rule."""
    evidence = []
    lesson = cpr.get("lesson", "")
    if not lesson:
        return evidence

    root = Path(zone_root)
    # Find distinctive phrase from the lesson
    words = lesson.split()
    if len(words) < 4:
        search_phrase = lesson
    else:
        mid = len(words) // 2
        search_phrase = " ".join(words[max(0, mid - 2):mid + 2])

    referencing_files = []
    promoted_to = cpr.get("promoted_to", "")

    for md in sorted(root.rglob("CLAUDE.md")):
        rel = str(md.relative_to(root))
        # Skip .git
        if any(p.startswith(".") and p != ".claude" for p in rel.split(os.sep)):
            continue
        # Skip the file it was promoted to (that's the source, not downstream)
        if promoted_to and rel == promoted_to:
            continue
        try:
            content = md.read_text(encoding="utf-8")
            if search_phrase in content:
                referencing_files.append(rel)
        except (OSError, UnicodeDecodeError):
            continue

    if referencing_files:
        evidence.append({
            "evidence_type": "downstream_specialization",
            "value": f"Rule referenced in {len(referencing_files)} child/sibling CLAUDE.md files",
            "detail": referencing_files[:5],
            "polarity": "useful",
        })

    return evidence


def gather_review_evidence(cpr, al_path):
    """Check conformations and provenance for review-close findings about this rule."""
    evidence = []
    cpr_id = cpr.get("id", "")
    lesson_fragment = (cpr.get("lesson", "") or "")[:40]

    # Check provenance logs for review-close references
    provenance_dir = Path(al_path) / "provenance"
    if provenance_dir.is_dir():
        mentions = 0
        for f in sorted(provenance_dir.glob("*.jsonl")):
            try:
                content = f.read_text(encoding="utf-8")
                if cpr_id in content or (lesson_fragment and lesson_fragment in content):
                    mentions += 1
            except (OSError, UnicodeDecodeError):
                continue

        if mentions > 0:
            evidence.append({
                "evidence_type": "provenance_mentions",
                "value": f"Referenced in {mentions} provenance log files",
                "polarity": "neutral",
            })

    return evidence


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_manifestation(cpr, all_evidence):
    """Classify the promoted rule's manifestation state."""
    has_strain = any(e.get("polarity") == "strain" for e in all_evidence)
    has_useful = any(e.get("polarity") == "useful" for e in all_evidence)
    has_any = len(all_evidence) > 0

    if has_useful and not has_strain:
        return "useful"
    if has_strain and has_useful:
        return "strained"
    if has_strain and not has_useful:
        return "demotion_candidate"
    if not has_any:
        return "preserved"
    return "preserved"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_tracker(zone_root, verbose=False):
    """Execute the full manifestation tracking scan."""
    zone_root = os.path.abspath(zone_root)
    tz_config = load_ticzone(zone_root)
    al_path = audit_logs_path(zone_root, tz_config)
    queue_path = os.path.join(al_path, "cprs", "queue.jsonl")
    signal_dir = Path(al_path) / "signals"

    promoted = load_promoted_cprs(queue_path)
    if not promoted:
        return {"promoted_count": 0, "manifestations": [], "summary": {}}

    now = datetime.now(timezone.utc).isoformat()
    manifestations = []

    for cpr_id, cpr in promoted.items():
        all_evidence = []
        all_evidence.extend(gather_signal_evidence(cpr, signal_dir))
        all_evidence.extend(gather_specialization_evidence(cpr, zone_root))
        all_evidence.extend(gather_review_evidence(cpr, al_path))

        state = classify_manifestation(cpr, all_evidence)

        manifestations.append({
            "cpr_id": cpr_id,
            "lesson": (cpr.get("lesson", "") or "")[:100],
            "subsystem": cpr.get("subsystem", ""),
            "promoted_to": cpr.get("promoted_to", ""),
            "promoted_date": cpr.get("promoted_date", ""),
            "state": state,
            "evidence": all_evidence,
            "tracked_at": now,
        })

    # Summary
    state_counts = defaultdict(int)
    for m in manifestations:
        state_counts[m["state"]] += 1

    return {
        "tracked_at": now,
        "zone_root": zone_root,
        "promoted_count": len(promoted),
        "manifestations": manifestations,
        "summary": dict(state_counts),
    }


def format_human_readable(result):
    """Format tracker result as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("MANIFESTATION TRACKER")
    lines.append("=" * 60)
    lines.append(f"  Tracked at:     {result.get('tracked_at', '?')}")
    lines.append(f"  Zone root:      {result.get('zone_root', '?')}")
    lines.append(f"  Promoted CPRs:  {result.get('promoted_count', 0)}")
    lines.append("")

    # Summary
    summary = result.get("summary", {})
    lines.append("SUMMARY:")
    lines.append("-" * 60)
    for state, count in sorted(summary.items()):
        lines.append(f"  {state:<22} {count}")
    lines.append("")

    # Per-manifestation
    for m in result.get("manifestations", []):
        lines.append(f"  {m['cpr_id']}")
        lines.append(f"    Lesson:    {m['lesson']}")
        lines.append(f"    State:     {m['state']}")
        lines.append(f"    Subsystem: {m['subsystem']}")
        lines.append(f"    Promoted:  {m['promoted_date']} -> {m['promoted_to']}")
        if m["evidence"]:
            for e in m["evidence"]:
                lines.append(f"    [{e.get('polarity','?')}] {e['evidence_type']}: {e['value']}")
        else:
            lines.append("    (no evidence found)")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Manifestation Tracker — scan promoted CPRs for downstream evidence"
    )
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON")
    parser.add_argument("--output", default=None,
                        help="Write output to file instead of stdout")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    zone_root = args.project_dir or resolve_zone_root()
    result = run_tracker(zone_root, verbose=args.verbose)

    if args.json:
        output_text = json.dumps(result, indent=2)
    else:
        output_text = format_human_readable(result)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output_text + "\n", encoding="utf-8")
        print(f"Manifestation report written to {args.output}")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
