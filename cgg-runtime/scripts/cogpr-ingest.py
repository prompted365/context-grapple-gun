#!/usr/bin/env python3
"""
cogpr-ingest.py — Mogul-cycle CogPR candidate ingest (report → queue birth ledger).

The THIRD population lane into audit-logs/cprs/queue.jsonl, sibling to:
  - cpr-extract.py           (surface-scan lane: CLAUDE.md / MEMORY.md / plan-file
                              `<!-- --agnostic-candidate -->` blocks; the /cadence lane)
  - arena-pressure-ingest.py (arena lane: pressure-reports' candidate_cogprs)

This is the MOGUL lane (Architect-directed, tic 439). A mogul cycle report
(audit-logs/mogul/cycle-reports/reports/*.report.json) may carry a
`candidate_cogprs` array — durable CogPR candidates the META cycles surfaced
(memory_mining, pattern_mining, ladder_audit, deep_audit, review_close_check).
The mogul run is a META lane with TIME to do it right, so a candidate it
surfaces should land in the queue (the birth ledger) directly, not die as a
report-only finding a human must later re-author.

SOLE-WRITER FENCE (load-bearing): the backend (codex/gpt-5.5 or claude) only
*emits* candidate_cogprs into its report — an artifact. THIS script, run
canonical-side by mogul-runner.sh AFTER the report is validated, is the SOLE
writer that appends them to the queue. A backend may produce artifacts but may
never terminalize governance state; this honors that — and a birth-state row
(status=extracted) is NOT a terminal/doctrine write. Promotion (extracted →
promoted → ledger.md/CLAUDE.md) stays /review human-gated. bench-packet-prep
picks the row up from the queue (its get_pending_cprs accepts `extracted`), so
the candidate reaches /review the moment it is ingested — no prose round-trip.

candidate_cogprs are read from BOTH:
  - report["candidate_cogprs"]                       (top-level)
  - report["results"][<cycle>]["candidate_cogprs"]   (per-cycle)

Each candidate is a dict: {lesson (REQUIRED), band?, subsystem?,
confidence_tier?, lesson_type?, recommended_scopes?, note?, source_cycle?}.
A bare string is treated as {"lesson": <string>}.

Dedup is three-axis (defense in depth):
  1. deterministic id  cpr_mogul_<cycle>_<sha256(lesson)[:12]> — re-surfacing the
     same lesson yields the same id; dedup_queue_append skips it at the write
     boundary regardless of why the caller re-attempts.
  2. lesson-prefix (80 chars) already present in the queue → skip (cross-id
     content duplicate; mirrors arena-pressure-ingest).
  3. terminal-state valve — an id already terminal in the queue is never re-born.

Usage:
  python3 cogpr-ingest.py --zone-root /path --report /path/to/report.json
  python3 cogpr-ingest.py --zone-root /path --report ... --dry-run
  python3 cogpr-ingest.py --zone-root /path --report ... --json
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing the atomic-append physics + zone_root provenance helper from
# the same dir (same layout as arena-pressure-ingest / cpr-extract).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import birth_topology  # noqa: E402

# Terminal states: an id that has reached one of these is a SETTLED CPR — never
# re-birth it. Mirrors bench-packet-prep.TERMINAL_STATUSES + cpr-extract's set.
TERMINAL_STATUSES = frozenset({
    "promoted", "absorbed", "superseded", "rejected",
    "deferred", "dismissed", "resolved", "skipped",
})

# Maturity window auto-backfill (mirrors arena-pressure-ingest QR-T25-001):
# a born gets a 3-tic review window so it does not look instantly review-due.
DEFAULT_MATURITY_WINDOW_TICS = 3


def resolve_audit_logs(zone_root: Path) -> Path:
    """Resolve audit-logs path from .ticzone (fallback: audit-logs)."""
    ticzone = zone_root / ".ticzone"
    rel = "audit-logs"
    if ticzone.exists():
        try:
            cfg = json.loads(ticzone.read_text())
            rel = cfg.get("audit_logs_path", "audit-logs")
        except (json.JSONDecodeError, OSError):
            pass
    return zone_root / rel


def get_tic_count(audit_logs: Path) -> int:
    """Count physical tics from tic event JSONL (authoritative count)."""
    tic_dir = audit_logs / "tics"
    if not tic_dir.exists():
        return 0
    max_counter = 0
    for f in sorted(tic_dir.glob("*.jsonl")):
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if d.get("type") == "tic" and d.get("count_mode") != "ignored":
                gc = d.get("global_counter_after", 0)
                if isinstance(gc, int) and gc > max_counter:
                    max_counter = gc
    return max_counter


def load_queue_state(audit_logs: Path):
    """Load queue dedup state.

    Returns (terminal_ids, present_ids, lesson_prefixes):
      terminal_ids   — set of ids whose LATEST-per-id status is terminal
      present_ids    — set of all ids present (any status)
      lesson_prefixes— set of first-80-char lesson prefixes already in the queue
    """
    queue_file = audit_logs / "cprs" / "queue.jsonl"
    by_id_status = {}   # id -> latest status (append order)
    present_ids = set()
    lesson_prefixes = set()
    if not queue_file.exists():
        return set(), present_ids, lesson_prefixes
    for line in queue_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        eid = d.get("id", "")
        if eid:
            present_ids.add(eid)
            by_id_status[eid] = d.get("status", "")  # last wins
        lesson = d.get("lesson", "")
        if lesson:
            lesson_prefixes.add(lesson[:80])
    terminal_ids = {
        eid for eid, status in by_id_status.items()
        if status in TERMINAL_STATUSES
    }
    return terminal_ids, present_ids, lesson_prefixes


def extract_candidates(report: dict):
    """Collect candidate_cogprs from a cycle report (top-level + per-cycle).

    Yields (candidate_dict, source_cycle) tuples. A bare string candidate is
    normalized to {"lesson": <string>}. source_cycle is the results.<cycle> key
    the candidate came from (or "report" for the top-level array, or the
    candidate's own declared source_cycle when present).
    """
    def _normalize(c, default_cycle):
        if isinstance(c, str):
            return {"lesson": c}, default_cycle
        if isinstance(c, dict):
            return c, c.get("source_cycle", default_cycle)
        return None, default_cycle

    # Top-level array
    for c in report.get("candidate_cogprs", []) or []:
        cand, cyc = _normalize(c, "report")
        if cand is not None:
            yield cand, cyc

    # Per-cycle arrays under results.<cycle>.candidate_cogprs
    results = report.get("results", {})
    if isinstance(results, dict):
        for cycle, payload in results.items():
            if not isinstance(payload, dict):
                continue
            for c in payload.get("candidate_cogprs", []) or []:
                cand, cyc = _normalize(c, cycle)
                if cand is not None:
                    yield cand, cyc


def mint_entry(candidate: dict, source_cycle: str, report: dict, birth_tic: int, topo: dict):
    """Build a queue birth-state row from a candidate. Returns the entry dict
    or None when the candidate has no lesson (the one hard requirement).

    Provenance (UNIFIED ACROSS HARNESSES): the row carries the same birth
    provenance shape as a cpr-extract-authored born (birth_rung,
    birth_scope_path) PLUS the mogul-lane specifics (mogul_mandate_id,
    source_cycle, mogul_runtime). mogul_runtime records WHICH harness emitted
    the candidate (codex_gpt5_5 | claude_code) as EVIDENCE, never as control —
    the harness is evidence, not law (compute-admission-law-topology-agnostic);
    the ingest behaves identically regardless of which harness produced it.
    """
    lesson = (candidate.get("lesson") or "").strip()
    if not lesson:
        return None

    now = datetime.now(timezone.utc)
    cycle = source_cycle or "mogul"
    # Deterministic id: re-surfacing the same lesson in the same cycle yields the
    # same id, so dedup_queue_append idempotently skips re-births.
    digest = hashlib.sha256(f"{cycle}:{lesson}".encode()).hexdigest()[:12]
    entry_id = f"cpr_mogul_{cycle}_{digest}"

    scopes = candidate.get("recommended_scopes")
    if scopes is None and "recommended_scope" in candidate:
        scopes = [candidate["recommended_scope"]]
    if not isinstance(scopes, list):
        scopes = [scopes] if scopes else []

    actor = report.get("actor", {})
    runtime = actor.get("runtime", "") if isinstance(actor, dict) else ""

    entry = {
        "type": "cpr",
        "id": entry_id,
        "id_origin": "hash_derived",
        "status": "extracted",
        "tier": "tier1",
        "lesson": lesson,
        "source": f"mogul:{cycle}",
        "source_date": now.strftime("%Y-%m-%d"),
        "band": candidate.get("band", "COGNITIVE"),
        "motivation_layer": candidate.get("motivation_layer", "COGNITIVE"),
        "subsystem": candidate.get("subsystem", ""),
        "recommended_scopes": scopes,
        "note": candidate.get("note", ""),
        "confidence_tier": candidate.get("confidence_tier", "tentative"),
        "lesson_type": candidate.get("lesson_type", "unknown"),
        "birth_tic": candidate.get("birth_tic", birth_tic),
        "maturity_window_tics": candidate.get(
            "maturity_window_tics", DEFAULT_MATURITY_WINDOW_TICS
        ),
        "review_tic": birth_tic + DEFAULT_MATURITY_WINDOW_TICS,
        "origin_context": "mogul_cycle",
        "source_cycle": cycle,
        "mogul_mandate_id": report.get("mandate_id", ""),
        "mogul_runtime": runtime,
        # Birth provenance parity with cpr-extract-authored borns (UNIFIED across
        # lanes/harnesses): same rung/scope shape regardless of which lane authored.
        "birth_rung": topo.get("birth_rung"),
        "birth_scope_path": topo.get("birth_scope_path"),
        "extracted_at": now.isoformat(),
        "extracted_by": "cogpr-ingest",
    }
    return entry


def append_entry(queue_file: str, entry: dict) -> bool:
    """Append via the sanctioned dedup-at-write physics. Returns True if
    written, False if deduplicated by id at the write boundary."""
    try:
        from lib.atomic_append import dedup_queue_append
        return dedup_queue_append(queue_file, entry)
    except ImportError:
        # Fallback: id-checked append under lock (mirrors arena-pressure-ingest's
        # defensive fallback when the lib import is unavailable).
        import fcntl
        os.makedirs(os.path.dirname(queue_file), exist_ok=True)
        eid = entry.get("id", "")
        lockfile = queue_file + ".lock"
        with open(lockfile, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                existing = set()
                if os.path.isfile(queue_file):
                    for line in open(queue_file, encoding="utf-8"):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            existing.add(json.loads(line).get("id", ""))
                        except (json.JSONDecodeError, ValueError):
                            pass
                if eid and eid in existing:
                    return False
                with open(queue_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, separators=(",", ":")) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                return True
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def ingest(zone_root: Path, report_path: Path, dry_run: bool):
    """Ingest candidate_cogprs from a report into the queue. Returns a summary
    dict (always — even on no-op/skip), suitable for --json emission."""
    audit_logs = resolve_audit_logs(zone_root)
    summary = {
        "report": str(report_path),
        "candidates_seen": 0,
        "ingested": 0,
        "skipped_no_lesson": 0,
        "skipped_lesson_dup": 0,
        "skipped_terminal": 0,
        "skipped_present": 0,
        "skipped_write_dedup": 0,
        "dry_run": dry_run,
        "ingested_ids": [],
    }

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        summary["error"] = f"report unreadable: {e}"
        return summary
    if not isinstance(report, dict):
        summary["error"] = "report is not a JSON object"
        return summary

    terminal_ids, present_ids, lesson_prefixes = load_queue_state(audit_logs)
    birth_tic = get_tic_count(audit_logs)
    topo = birth_topology(str(zone_root))
    queue_file = str(audit_logs / "cprs" / "queue.jsonl")

    for candidate, source_cycle in extract_candidates(report):
        summary["candidates_seen"] += 1
        entry = mint_entry(candidate, source_cycle, report, birth_tic, topo)
        if entry is None:
            summary["skipped_no_lesson"] += 1
            continue

        eid = entry["id"]
        prefix = entry["lesson"][:80]

        # Axis 3: terminal valve — never re-birth a settled CPR.
        if eid in terminal_ids:
            summary["skipped_terminal"] += 1
            continue
        # Axis 1 (pre-write): id already present (non-terminal) — already ingested.
        if eid in present_ids:
            summary["skipped_present"] += 1
            continue
        # Axis 2: content duplicate by lesson prefix across any id.
        if prefix in lesson_prefixes:
            summary["skipped_lesson_dup"] += 1
            continue

        if dry_run:
            summary["ingested"] += 1
            summary["ingested_ids"].append(eid)
            # reserve so a second identical candidate in the same report dedups
            present_ids.add(eid)
            lesson_prefixes.add(prefix)
            continue

        if append_entry(queue_file, entry):
            summary["ingested"] += 1
            summary["ingested_ids"].append(eid)
            present_ids.add(eid)
            lesson_prefixes.add(prefix)
        else:
            # dedup_queue_append refused (id raced in concurrently)
            summary["skipped_write_dedup"] += 1

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Ingest candidate_cogprs from a mogul cycle report into queue.jsonl"
    )
    parser.add_argument("--zone-root", required=True, help="Project zone root")
    parser.add_argument("--report", required=True, help="Cycle report JSON to ingest")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Emit the summary as JSON to stdout")
    parser.add_argument("--quiet", action="store_true", help="Suppress human output")
    args = parser.parse_args()

    zone_root = Path(args.zone_root).resolve()
    report_path = Path(args.report)
    if not report_path.is_file():
        msg = {"error": f"report not found: {report_path}", "ingested": 0}
        if args.output_json:
            print(json.dumps(msg))
        elif not args.quiet:
            print(f"cogpr-ingest: report not found: {report_path}", file=sys.stderr)
        # Non-fatal: a missing report is a no-op (the runner calls fail-soft).
        return 0

    summary = ingest(zone_root, report_path, args.dry_run)

    if args.output_json:
        print(json.dumps(summary, indent=2))
    elif not args.quiet:
        prefix = "[DRY-RUN] " if args.dry_run else ""
        if "error" in summary:
            print(f"{prefix}cogpr-ingest: {summary['error']}", file=sys.stderr)
        else:
            print(
                f"{prefix}cogpr-ingest: {summary['ingested']} ingested / "
                f"{summary['candidates_seen']} seen "
                f"(dup:{summary['skipped_lesson_dup']} present:{summary['skipped_present']} "
                f"terminal:{summary['skipped_terminal']} no_lesson:{summary['skipped_no_lesson']})"
            )
            for eid in summary["ingested_ids"]:
                print(f"  + {eid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
