#!/usr/bin/env python3
"""
arena-pressure-ingest.py — Standalone arena pressure report ingestion.

Parses pressure reports from audit-logs/arenas/pressure-reports/,
emits signals, generates CogPRs, and enforces arena mode constraints.

Usage:
    python3 arena-pressure-ingest.py --zone-root /path/to/project
    python3 arena-pressure-ingest.py --zone-root /path/to/project --dry-run
    python3 arena-pressure-ingest.py --zone-root /path/to/project --report /path/to/specific-report.json
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def resolve_audit_logs(zone_root: Path) -> Path:
    """Resolve audit-logs path from .ticzone."""
    ticzone = zone_root / ".ticzone"
    rel = "audit-logs"
    if ticzone.exists():
        try:
            cfg = json.loads(ticzone.read_text())
            rel = cfg.get("audit_logs_path", "audit-logs")
        except (json.JSONDecodeError, OSError):
            pass
    return zone_root / rel


def load_processed_reports(audit_logs: Path) -> set:
    """Load set of already-processed report IDs."""
    tracker = audit_logs / "arenas" / ".processed-reports.jsonl"
    processed = set()
    if tracker.exists():
        for line in tracker.read_text().splitlines():
            try:
                entry = json.loads(line.strip())
                rid = entry.get("report_id", "")
                if rid:
                    processed.add(rid)
            except (json.JSONDecodeError, ValueError):
                continue
    return processed


def discover_reports(audit_logs: Path, specific_report: str = None) -> list:
    """Find unprocessed pressure reports."""
    if specific_report:
        p = Path(specific_report)
        if p.exists():
            return [p]
        return []

    reports_dir = audit_logs / "arenas" / "pressure-reports"
    if not reports_dir.exists():
        return []

    return sorted(reports_dir.glob("*.json"), key=lambda f: f.stat().st_mtime)


def parse_pressure_report(path: Path) -> dict | None:
    """Parse a pressure report JSON file."""
    try:
        data = json.loads(path.read_text())
        # Validate minimal structure
        if not isinstance(data, dict):
            return None
        if "arena_id" not in data and "session_id" not in data:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def report_id(report: dict, path: Path) -> str:
    """Generate a stable ID for a pressure report."""
    content = json.dumps(report, sort_keys=True)
    h = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"pr_{path.stem}_{h}"


def emit_signal(report: dict, rid: str, audit_logs: Path, dry_run: bool) -> dict:
    """Emit a signal from a pressure report finding."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    arena_id = report.get("arena_id", report.get("session_id", "unknown"))
    pressure_type = report.get("pressure_type", "arena_finding")
    summary = report.get("summary", report.get("finding", "Arena pressure report"))
    band = report.get("band", "COGNITIVE")
    volume = report.get("volume", 40)
    subsystem = report.get("subsystem", "arena")

    signal = {
        "type": "signal",
        "id": f"sig_{date_str}_{rid}",
        "kind": "TENSION",
        "band": band,
        "status": "active",
        "volume": min(volume, 100),
        "max_volume": 100,
        "tick_count": 0,
        "subsystem": subsystem,
        "source": "arena-pressure-ingest.py",
        "source_date": date_str,
        "created_at": now.isoformat(),
        "birth_rung": "site",
        "payload": {
            "summary": summary[:500],
            "arena_id": arena_id,
            "pressure_type": pressure_type,
            "report_id": rid,
        },
        "escalation": {"warrant_threshold": 70},
        "origin": "deterministic",
    }

    if not dry_run:
        signal_file = audit_logs / "signals" / f"{date_str}.jsonl"
        signal_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            from lib.atomic_append import atomic_append_jsonl
            atomic_append_jsonl(str(signal_file), signal)
        except ImportError:
            import fcntl
            lockfile = str(signal_file) + ".lock"
            with open(lockfile, "w") as lf:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
                try:
                    with open(signal_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(signal, separators=(",", ":")) + "\n")
                finally:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    return signal


def emit_cogpr(report: dict, rid: str, audit_logs: Path, tic: int, dry_run: bool) -> dict | None:
    """Generate a CogPR from a pressure report if it contains a lesson."""
    lessons = report.get("lessons", [])
    if not lessons and not report.get("lesson"):
        return None

    lesson_text = report.get("lesson", lessons[0] if lessons else "")
    if not lesson_text:
        return None

    now = datetime.now(timezone.utc)
    arena_id = report.get("arena_id", report.get("session_id", "unknown"))
    band = report.get("band", "COGNITIVE")
    subsystem = report.get("subsystem", "arena")

    cpr = {
        "id": f"cpr_{rid}",
        "lesson": lesson_text[:500],
        "band": band,
        "status": "extracted",
        "source_date": now.strftime("%Y-%m-%d"),
        "source": f"arena:{arena_id}",
        "subsystem": subsystem,
        "birth_tic": tic,
        "arena_origin": True,
        "pressure_type": report.get("pressure_type", "arena_finding"),
        "created_at": now.isoformat(),
    }

    if not dry_run:
        append_to_queue(cpr, audit_logs)

    return cpr


def load_existing_queue(audit_logs: Path) -> dict:
    """Load existing queue entries for dedup. Returns dict of id -> entry."""
    queue_file = audit_logs / "cprs" / "queue.jsonl"
    entries = {}
    if not queue_file.exists():
        return entries
    for line in queue_file.read_text(encoding="utf-8").splitlines():
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


def lesson_already_queued(lesson: str, existing_queue: dict) -> bool:
    """Check if a lesson (by prefix match) already exists in the queue."""
    prefix = lesson[:80]
    for entry in existing_queue.values():
        existing_lesson = entry.get("lesson", "")
        existing_prefix = existing_lesson[:80]
        if existing_prefix == prefix:
            return True
    return False


def append_to_queue(entry: dict, audit_logs: Path):
    """Append a single entry to queue.jsonl with atomic write."""
    queue_file = str(audit_logs / "cprs" / "queue.jsonl")
    os.makedirs(os.path.dirname(queue_file), exist_ok=True)
    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(queue_file, entry)
    except ImportError:
        import fcntl
        lockfile = queue_file + ".lock"
        with open(lockfile, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                with open(queue_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def ingest_candidate_cogprs(
    report: dict,
    report_path: Path,
    audit_logs: Path,
    tic: int,
    existing_queue: dict,
    dry_run: bool,
) -> list:
    """Ingest candidate_cogprs from a pressure report into queue.jsonl.

    Deduplicates against existing queue entries by lesson prefix.
    Returns list of minted CogPR entries.
    """
    candidates = report.get("candidate_cogprs", [])
    if not candidates:
        return []

    now = datetime.now(timezone.utc)
    arena_id = report.get("arena_id", report.get("session_id", "unknown"))
    arena_mode = report.get("arena_mode", "experimental")
    source_tic = report.get("source_tic", tic)

    minted = []
    for i, candidate in enumerate(candidates):
        lesson = candidate.get("lesson", "")
        if not lesson:
            continue

        # Dedup: skip if lesson already in queue
        if lesson_already_queued(lesson, existing_queue):
            continue

        # Generate stable ID from arena + candidate index
        arena_short = arena_id[:40]
        candidate_id = f"arena-{arena_short}-{i}"

        # Skip if this exact candidate_id already exists
        if candidate_id in existing_queue:
            continue

        # Normalize recommended_scopes
        scopes = []
        if "recommended_scope" in candidate:
            scopes = [candidate["recommended_scope"]]
        elif "recommended_scopes" in candidate:
            scopes = candidate["recommended_scopes"]

        cpr = {
            "type": "cpr",
            "id": candidate_id,
            "status": "pending",
            "lesson": lesson,
            "band": candidate.get("band", "COGNITIVE"),
            "source": f"arena:{arena_id}",
            "source_date": now.strftime("%Y-%m-%d"),
            "subsystem": candidate.get("subsystem", report.get("subsystem", "arena")),
            "birth_tic": source_tic,
            "arena_source": arena_id,
            "arena_mode": arena_mode,
            "confidence_tier": candidate.get("confidence_tier", "unknown"),
            "lesson_type": candidate.get("lesson_type", "unknown"),
            "recommended_scopes": scopes,
            "note": candidate.get("note", ""),
            "extracted_at": now.isoformat(),
            "extracted_by": "arena-pressure-ingest",
        }

        # QR-T25-001: Auto-assign maturity window when absent
        if "maturity_window_tics" not in cpr and "maturity_window_tics" not in candidate:
            cpr["maturity_window_tics"] = 3
            cpr["review_tic"] = source_tic + 3
            cpr["assigned_by"] = "arena-pressure-ingest"
            cpr["assignment_reason"] = "auto-window backfill"

        if not dry_run:
            append_to_queue(cpr, audit_logs)

        # Add to existing_queue for subsequent dedup within same run
        existing_queue[candidate_id] = cpr
        minted.append(cpr)

    return minted


def enforce_arena_mode(report: dict) -> list[str]:
    """Check arena mode constraints. Returns list of violations."""
    violations = []
    mode = report.get("arena_mode", "experimental")

    if mode == "operational":
        # Operational arenas must not produce experimental-band findings
        if report.get("band") == "EXPERIMENTAL":
            violations.append(
                f"Operational arena produced EXPERIMENTAL band finding (arena: {report.get('arena_id', '?')})"
            )
    elif mode == "experimental":
        # Experimental arenas must not claim operational authority
        if report.get("claims_operational", False):
            violations.append(
                f"Experimental arena claims operational authority (arena: {report.get('arena_id', '?')})"
            )

    return violations


def get_tic_count(audit_logs: Path) -> int:
    """Read current tic count from audit-logs."""
    tic_dir = audit_logs / "tics"
    if not tic_dir.exists():
        return 0
    count = 0
    for f in sorted(tic_dir.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            try:
                if json.loads(line.strip()).get("type") == "tic":
                    count += 1
            except (json.JSONDecodeError, ValueError):
                continue
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Ingest arena pressure reports into governance pipeline"
    )
    parser.add_argument("--zone-root", required=True, help="Project zone root")
    parser.add_argument("--report", help="Specific report file to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    args = parser.parse_args()

    zone_root = Path(args.zone_root).resolve()
    audit_logs = resolve_audit_logs(zone_root)

    # Discover reports
    reports = discover_reports(audit_logs, args.report)
    if not reports:
        if not args.quiet:
            print("No pressure reports found.")
        return

    # Load processed set and existing queue for dedup
    processed = load_processed_reports(audit_logs)
    existing_queue = load_existing_queue(audit_logs)

    tic = get_tic_count(audit_logs)
    signals_emitted = 0
    cprs_generated = 0
    candidates_minted = 0
    violations_found = []

    for report_path in reports:
        report = parse_pressure_report(report_path)
        if report is None:
            if not args.quiet:
                print(f"  SKIP {report_path.name} (invalid format)")
            continue

        rid = report_id(report, report_path)
        if rid in processed:
            if not args.quiet:
                print(f"  SKIP {report_path.name} (already processed)")
            continue

        # Enforce arena mode
        mode_violations = enforce_arena_mode(report)
        violations_found.extend(mode_violations)

        # Emit signal
        signal = emit_signal(report, rid, audit_logs, args.dry_run)
        signals_emitted += 1

        # Generate CogPR if report-level lesson present
        cpr = emit_cogpr(report, rid, audit_logs, tic, args.dry_run)
        if cpr:
            cprs_generated += 1

        # Ingest candidate_cogprs array (the main pipeline fix for SIG-T22-001)
        minted = ingest_candidate_cogprs(
            report, report_path, audit_logs, tic, existing_queue, args.dry_run
        )
        candidates_minted += len(minted)

        # Record as processed
        if not args.dry_run:
            tracker = audit_logs / "arenas" / ".processed-reports.jsonl"
            tracker.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "report_id": rid,
                "file": str(report_path),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "signal_emitted": True,
                "cpr_generated": cpr is not None,
                "candidates_minted": len(minted),
                "violations": mode_violations,
            }
            try:
                from lib.atomic_append import atomic_append_jsonl
                atomic_append_jsonl(str(tracker), entry)
            except ImportError:
                with open(tracker, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, separators=(",", ":")) + "\n")

        if not args.quiet:
            status = "DRY-RUN" if args.dry_run else "OK"
            cpr_msg = f" +CPR" if cpr else ""
            cand_msg = f" +{len(minted)} candidates" if minted else ""
            violation_msg = f" VIOLATIONS:{len(mode_violations)}" if mode_violations else ""
            print(f"  [{status}] {report_path.name} → signal{cpr_msg}{cand_msg}{violation_msg}")

    if not args.quiet:
        prefix = "[DRY-RUN] " if args.dry_run else ""
        print(f"\n{prefix}Processed: {signals_emitted} reports, {signals_emitted} signals, {cprs_generated} report-level CogPRs, {candidates_minted} arena candidates")
        if violations_found:
            print(f"{prefix}Mode violations: {len(violations_found)}")
            for v in violations_found:
                print(f"  ! {v}")


if __name__ == "__main__":
    main()
