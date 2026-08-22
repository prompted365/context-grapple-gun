#!/usr/bin/env python3
"""
queue.jsonl drift audit — durable, idempotent observability script.

Born tic 280 from CogPR `cpr_queue_jsonl_drift_audit_primitive_tic278`
(promoted at /review tic 279). Purpose: continuous detection of two
queue-health failure modes that mislead RTCH harvest readers and
falsely surface overdue work:

  1. Genuinely-overdue active entries (status in {pending, extracted,
     enrichment_eligible, enrichment_in_progress, promotable} aged
     beyond a configurable threshold in tics since birth_tic)
  2. Terminal-state ids carrying raw-emission duplicates (pre-promotion
     rows that survived the latest-entry-per-id projection only because
     a peer reader aggregates raw lines)

The script is the queue-side complement to
`audit-logs/governance/memory-md-audit.py` — same structural shape
(project state -> classify -> emit structured findings), different
substrate (queue.jsonl rather than MEMORY.md).

Outputs JSON to
`audit-logs/governance/queue-drift-audit/<timestamp>[-tic-N].json` and
prints a compact summary to stdout. Per-finding structure:

    {
      "breach_class": "overdue_active" | "terminal_with_duplicates",
      "id": "<cogpr id>",
      "status": "<latest-entry status>",
      "birth_tic": <int|null>,
      "age_tics": <int|null>,
      "duplicate_count": <int>,
      "duplicate_statuses": [...],
      "note": "..."
    }

Composes with federation KI `Authoritative-set readers must read the
manifest, not aggregate raw emissions` (the projection IS the manifest
for queue.jsonl) and CGG KI `Terminal-State Valve Pattern` (read-side
projection complement). Read-only; never mutates queue.jsonl.

Census-rate discrimination (added /review 725, ledger anchor
`#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude`):
`terminal_with_duplicates` fires on EVERY run by construction — it is
entailed by the federation's own mandated copy-forward writeback
discipline, and its count grew monotonically 280 -> 803 across the report
history. A flag at ~100% base rate is a census wearing the word BREACH.
Per the ratified cure the flag is NOT deleted; instead the governance-
bearing quantity — the RATE — is raised to the flag's own altitude
(top-level keys, never one level down in a detail object) and a severity
word tracks that rate:

    "terminal_with_duplicates_count":       <int>
    "terminal_with_duplicates_delta":       <int|null>    # vs previous report
    "terminal_with_duplicates_rate_per_tic":<float|null>
    "terminal_with_duplicates_severity":    "expected_census"
                                          | "anomalous_jump"
                                          | "census_regression"
                                          | "untimed_baseline"
                                          | "no_baseline"
    "census_baseline":       {...}   # provenance of the comparison
    "breach_classification": {...}   # per-class census-vs-discriminating label

Backward compatibility is preserved deliberately: the `breaches` list
strings and the exit-code contract below are UNCHANGED, and the entailed
class stays loudly visible — it gains a discriminating axis, it is never
silently suppressed.

Exit codes:
  0 — healthy (no breaches)
  1 — discipline breach (overdue_active > 0 OR terminal_with_duplicates > 0)
  2 — fatal error reading queue.jsonl
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Script lives at <federation_root>/canonical_developer/context-grapple-gun/
#   cgg-runtime/scripts/queue-drift-audit.py
# .parent.parent.parent.parent.parent resolves the federation root path.
SCRIPT_PATH = Path(__file__).resolve()
FEDERATION_ROOT = SCRIPT_PATH.parent.parent.parent.parent.parent
QUEUE_FILE = FEDERATION_ROOT / "audit-logs" / "cprs" / "queue.jsonl"
OUT_DIR = FEDERATION_ROOT / "audit-logs" / "governance" / "queue-drift-audit"
TIC_LOG_DIR = FEDERATION_ROOT / "audit-logs" / "tics"

# Terminal statuses per CGG `Terminal-State Valve Pattern` doctrine.
TERMINAL_STATUSES = {
    "promoted",
    "deferred",
    "skipped",
    "absorbed",
    "rejected",
    "dismissed",
    "resolved",
    "superseded",
}

# Additive lifecycle-state valve (terminal-taxonomy APPLICATION tranche, verdict
# tic 555 PROMOTE-SPEC). The 5 orphan statuses used to land in the "other"
# bucket (settled but unrecognized), and each peer reader corrected differently
# — the Disagreement-as-evidence shape. Reading the SHARED additive
# `lifecycle_state` field settles them here too: an id is terminal for this
# audit when its status is terminal OR its lifecycle_state is settled.
# `obligated_waiting` is settled (not overdue-active, not "other") even though
# it carries a live build/falsification obligation surfaced elsewhere.
# Spec: audit-logs/governance/terminal-taxonomy-strike-verdict-tic555.md
LIFECYCLE_SETTLED_STATES = {
    "terminal_positive",
    "terminal_negative",
    "obligated_waiting",
    "suspensive",
}


def _is_terminal(row):
    """Settled = terminal status OR settled additive lifecycle_state."""
    return (
        row.get("status", "") in TERMINAL_STATUSES
        or row.get("lifecycle_state", "") in LIFECYCLE_SETTLED_STATES
    )

ACTIVE_STATUSES = {
    "pending",
    "extracted",
    "enrichment_eligible",
    "enrichment_in_progress",
    "promotable",
}

DEFAULT_OVERDUE_THRESHOLD_TICS = 20

# --- Census-rate discrimination (ledger anchor
# `#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude`,
# PROMOTE /review 725) -------------------------------------------------------
#
# Breach classes whose firing is ENTAILED by federation discipline rather than
# discovered by observation. These saturate to always-true and stop
# discriminating; they stay loud (never suppressed) but are labelled as census
# so a reader's discount reflex never has to form.
ENTAILED_CENSUS_CLASSES = {
    "terminal_with_duplicates": (
        "Entailed by the federation's mandated copy-forward writeback "
        "discipline: review-execute appends a full-envelope row per verdict, "
        "so every terminalized id necessarily acquires >=1 pre-projection row. "
        "Base rate ~100% on every run since tic 280; count grew monotonically "
        "280 -> 803 across the report history. The flag is a census — the "
        "governance-bearing quantity is its RATE, not its truth value."
    ),
}

# Observed per-tic growth band for `terminal_with_duplicates`, derived from the
# civil-engineer cycle record (tic 490=446, 540=559, 550=563, 570=624,
# ~722=803) => 0.40 to 3.05 ids/tic. The ceiling carries headroom over the
# measured maximum; a rate above it is a genuine anomaly, not census drift.
DEFAULT_CENSUS_RATE_BAND_PER_TIC = 5.0

# Severity vocabulary — one word, and it tracks the RATE (not the flag).
SEVERITY_NO_BASELINE = "no_baseline"           # nothing to compare against
SEVERITY_UNTIMED_BASELINE = "untimed_baseline"  # baseline carries no usable tic
SEVERITY_EXPECTED_CENSUS = "expected_census"    # in-band entailed growth
SEVERITY_ANOMALOUS_JUMP = "anomalous_jump"      # rate above the band
SEVERITY_CENSUS_REGRESSION = "census_regression"  # count fell (append-only says it shouldn't)


def load_current_tic():
    """Return the current federation tic from the canonical tic log, or None.

    Resolves from `audit-logs/tics/*.jsonl` latest event, field
    `domain_counter_after` (Temporal Scope Discipline — the tic emission
    lane is the time authority). The prior source, `audit-logs/tics/
    current.json`, never existed, so `age_tics` stayed None and the
    `overdue_active` detector could never fire while the duplicate-class
    banner printed every run (F4-723, verified; repaired /review 723).
    """
    try:
        files = sorted(TIC_LOG_DIR.glob("*.jsonl"))
    except OSError:
        return None
    for path in reversed(files):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            for key in ("domain_counter_after", "counter_after", "current_tic", "tic"):
                val = event.get(key)
                if isinstance(val, int):
                    return val
    return None


def load_queue_rows(queue_path):
    """Return list of parsed dicts (preserving append order). Empty on missing."""
    rows = []
    p = Path(queue_path)
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict):
            rows.append(d)
    return rows


def project_terminal_state(rows):
    """Apply latest-entry-per-id-wins projection over the raw rows.

    Returns:
      latest: dict id -> latest row (last-write-wins)
      per_id_rows: dict id -> list of all rows for that id, in append order
    """
    latest = {}
    per_id_rows = {}
    for row in rows:
        rid = row.get("id")
        if not rid:
            continue
        per_id_rows.setdefault(rid, []).append(row)
        latest[rid] = row
    return latest, per_id_rows


def breach_class_count(report, breach_class):
    """Read a breach class's count out of a report of EITHER schema generation.

    Reports written before /review 725 carry no top-level count key, so fall
    back to the `breaches` strings (`"<class>:<n>"`, present since tic 280) and
    finally to counting `findings`. Returns None when the class is absent
    entirely, which is distinct from a genuine zero.
    """
    if not isinstance(report, dict):
        return None

    val = report.get(f"{breach_class}_count")
    if isinstance(val, int) and not isinstance(val, bool):
        return val

    for entry in report.get("breaches") or []:
        if not isinstance(entry, str) or not entry.startswith(f"{breach_class}:"):
            continue
        try:
            return int(entry.split(":", 1)[1])
        except (ValueError, IndexError):
            continue

    findings = report.get("findings")
    if isinstance(findings, list):
        return sum(
            1
            for f in findings
            if isinstance(f, dict) and f.get("breach_class") == breach_class
        )
    return None


def load_previous_report(out_dir=None):
    """Return (report_dict, filename) for the newest prior report, or (None, None).

    Report filenames are `<iso-ish-timestamp>[-tic-N].json`, so lexicographic
    order over the directory IS chronological order (the optional tic suffix
    sorts after the timestamp it belongs to and cannot reorder distinct
    timestamps).
    """
    directory = Path(out_dir) if out_dir is not None else OUT_DIR
    try:
        files = sorted(directory.glob("*.json"))
    except OSError:
        return None, None
    for path in reversed(files):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return data, path.name
    return None, None


def classify_census_rate(
    count,
    previous_count,
    tic_delta,
    band_per_tic=DEFAULT_CENSUS_RATE_BAND_PER_TIC,
):
    """Classify an entailed-census class by its RATE of change.

    Returns (severity, delta, rate_per_tic). The severity word tracks the rate,
    never the flag's truth value — the flag is always true for these classes.
    Refuses to invent a rate when the baseline carries no usable tic delta
    (`untimed_baseline`) rather than dividing by an assumed cadence.
    """
    if not isinstance(previous_count, int) or isinstance(previous_count, bool):
        return SEVERITY_NO_BASELINE, None, None

    delta = count - previous_count
    if delta < 0:
        # Entailed by an append-only substrate to be monotonic; a fall means the
        # queue was rewritten, pruned, or re-projected. Worth a human look.
        return SEVERITY_CENSUS_REGRESSION, delta, None
    if delta == 0:
        # Zero growth is in-band under any cadence; no tic delta needed.
        return SEVERITY_EXPECTED_CENSUS, delta, 0.0
    if not isinstance(tic_delta, int) or isinstance(tic_delta, bool) or tic_delta <= 0:
        # Growth is real but its rate is not derivable from this baseline.
        return SEVERITY_UNTIMED_BASELINE, delta, None

    rate = delta / tic_delta
    severity = (
        SEVERITY_EXPECTED_CENSUS if rate <= band_per_tic else SEVERITY_ANOMALOUS_JUMP
    )
    return severity, delta, rate


def audit(overdue_threshold=DEFAULT_OVERDUE_THRESHOLD_TICS, current_tic=None):
    if not QUEUE_FILE.exists():
        print(f"ERROR: {QUEUE_FILE} does not exist", file=sys.stderr)
        return None, 2

    if current_tic is None:
        current_tic = load_current_tic()

    rows = load_queue_rows(QUEUE_FILE)
    raw_row_count = len(rows)
    latest, per_id_rows = project_terminal_state(rows)

    findings = []
    overdue_active = []
    terminal_with_duplicates = []
    terminal_count = 0
    active_count = 0
    other_count = 0

    for rid, row in latest.items():
        status = row.get("status", "")
        birth_tic = row.get("birth_tic")
        all_rows = per_id_rows.get(rid, [])
        duplicate_count = max(0, len(all_rows) - 1)
        duplicate_statuses = (
            [r.get("status", "") for r in all_rows[:-1]] if duplicate_count > 0 else []
        )

        if _is_terminal(row):
            terminal_count += 1
            # Only flag terminal entries with duplicate rows whose presence
            # could mislead a raw-line reader (any duplicate count > 0).
            if duplicate_count > 0:
                f = {
                    "breach_class": "terminal_with_duplicates",
                    "id": rid,
                    "status": status,
                    "birth_tic": birth_tic,
                    "age_tics": None,
                    "duplicate_count": duplicate_count,
                    "duplicate_statuses": duplicate_statuses,
                    "note": (
                        "Terminal entry preceded by raw-emission row(s); "
                        "raw-line readers without terminal-state-valve "
                        "projection may surface stale pre-promotion state."
                    ),
                }
                findings.append(f)
                terminal_with_duplicates.append(f)
        elif status in ACTIVE_STATUSES:
            active_count += 1
            age_tics = None
            if isinstance(birth_tic, int) and isinstance(current_tic, int):
                age_tics = current_tic - birth_tic
            if age_tics is not None and age_tics >= overdue_threshold:
                f = {
                    "breach_class": "overdue_active",
                    "id": rid,
                    "status": status,
                    "birth_tic": birth_tic,
                    "age_tics": age_tics,
                    "duplicate_count": duplicate_count,
                    "duplicate_statuses": duplicate_statuses,
                    "note": (
                        f"Active entry aged {age_tics} tics since birth "
                        f"(threshold={overdue_threshold})."
                    ),
                }
                findings.append(f)
                overdue_active.append(f)
        else:
            other_count += 1

    breaches = []
    if overdue_active:
        breaches.append(f"overdue_active:{len(overdue_active)}")
    if terminal_with_duplicates:
        breaches.append(f"terminal_with_duplicates:{len(terminal_with_duplicates)}")

    # --- Census-rate discrimination -----------------------------------------
    # The flag stays exactly as-is above (backward compatible). What follows
    # RAISES THE RATE TO THE FLAG'S ALTITUDE: top-level keys, not a detail
    # object. Ledger: `#breach-flag-at-saturation-is-a-census-rate-rides-at-
    # flag-altitude` (/review 725).
    twd_count = len(terminal_with_duplicates)
    prev_report, prev_name = load_previous_report()
    prev_count = breach_class_count(prev_report, "terminal_with_duplicates")
    prev_tic = prev_report.get("tic_at_audit") if isinstance(prev_report, dict) else None
    if not isinstance(prev_tic, int) or isinstance(prev_tic, bool):
        prev_tic = None
    tic_delta = (
        current_tic - prev_tic
        if isinstance(current_tic, int)
        and not isinstance(current_tic, bool)
        and prev_tic is not None
        else None
    )
    twd_severity, twd_delta, twd_rate = classify_census_rate(
        twd_count, prev_count, tic_delta
    )

    census_baseline = None
    if prev_report is not None:
        census_baseline = {
            "report": prev_name,
            "tic_at_audit": prev_tic,
            "terminal_with_duplicates_count": prev_count,
            "timestamp_utc": prev_report.get("timestamp_utc"),
            "tic_delta": tic_delta,
            "rate_band_per_tic": DEFAULT_CENSUS_RATE_BAND_PER_TIC,
        }

    breach_classification = {}
    for entry in breaches:
        cls = entry.split(":", 1)[0]
        if cls in ENTAILED_CENSUS_CLASSES:
            breach_classification[cls] = {
                "kind": "census",
                "entailed": True,
                "discriminating": False,
                "rationale": ENTAILED_CENSUS_CLASSES[cls],
            }
        else:
            breach_classification[cls] = {
                "kind": "discriminating",
                "entailed": False,
                "discriminating": True,
                "rationale": "Observed condition; not entailed by federation discipline.",
            }

    report = {
        "tic_at_audit": current_tic,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "queue_path": str(QUEUE_FILE),
        "overdue_threshold_tics": overdue_threshold,
        "raw_row_count": raw_row_count,
        "unique_id_count": len(latest),
        "status_breakdown": {
            "terminal": terminal_count,
            "active": active_count,
            "other": other_count,
        },
        "duplicate_summary": {
            "ids_with_duplicates": sum(
                1 for r in per_id_rows.values() if len(r) > 1
            ),
            "total_duplicate_rows": sum(
                max(0, len(r) - 1) for r in per_id_rows.values()
            ),
        },
        # Rate at flag altitude — these four keys are deliberately TOP-LEVEL.
        "terminal_with_duplicates_count": twd_count,
        "terminal_with_duplicates_delta": twd_delta,
        "terminal_with_duplicates_rate_per_tic": twd_rate,
        "terminal_with_duplicates_severity": twd_severity,
        "census_baseline": census_baseline,
        "breach_classification": breach_classification,
        "findings": findings,
        "breaches": breaches,
        "healthy": len(breaches) == 0,
    }

    exit_code = 0 if report["healthy"] else 1
    return report, exit_code


def main():
    parser = argparse.ArgumentParser(
        description="queue.jsonl drift audit — terminal-valve projection + overdue detection"
    )
    parser.add_argument(
        "--overdue-threshold",
        type=int,
        default=DEFAULT_OVERDUE_THRESHOLD_TICS,
        help=(
            f"Age threshold in tics for overdue_active classification "
            f"(default: {DEFAULT_OVERDUE_THRESHOLD_TICS})"
        ),
    )
    parser.add_argument(
        "--tic",
        type=int,
        default=None,
        help="Override current tic resolution (default: latest event in audit-logs/tics/*.jsonl)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Print full JSON report to stdout (no file write)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout summary",
    )
    args = parser.parse_args()

    report, exit_code = audit(
        overdue_threshold=args.overdue_threshold,
        current_tic=args.tic,
    )
    if report is None:
        sys.exit(exit_code)

    if args.output_json:
        print(json.dumps(report, indent=2))
        sys.exit(exit_code)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = report["timestamp_utc"].replace(":", "").split(".")[0]
    tic_part = f"-tic-{report['tic_at_audit']}" if report.get("tic_at_audit") else ""
    out_file = OUT_DIR / f"{ts}{tic_part}.json"
    out_file.write_text(json.dumps(report, indent=2) + "\n")

    if not args.quiet:
        status = "HEALTHY" if report["healthy"] else "BREACH"
        print(
            f"[{status}] queue.jsonl: {report['raw_row_count']} raw rows "
            f"/ {report['unique_id_count']} unique ids"
        )
        sb = report["status_breakdown"]
        print(
            f"  status: terminal={sb['terminal']} active={sb['active']} other={sb['other']}"
        )
        ds = report["duplicate_summary"]
        print(
            f"  duplicates: {ds['ids_with_duplicates']} ids carry "
            f"{ds['total_duplicate_rows']} pre-projection rows"
        )
        print(
            f"  overdue threshold: {report['overdue_threshold_tics']} tics "
            f"(current_tic={report['tic_at_audit']})"
        )
        if report["breaches"]:
            print(f"  BREACHES: {', '.join(report['breaches'])}")
            for cls, meta in report["breach_classification"].items():
                if meta["kind"] == "census":
                    print(f"    - {cls}: CENSUS (entailed, ~100% base rate)")
        # Rate at flag altitude — printed beside the flag, never buried.
        delta = report["terminal_with_duplicates_delta"]
        rate = report["terminal_with_duplicates_rate_per_tic"]
        delta_s = "n/a" if delta is None else f"{delta:+d}"
        rate_s = "n/a" if rate is None else f"{rate:.2f}/tic"
        base = report["census_baseline"]
        base_s = "no baseline" if not base else f"vs {base['report']}"
        print(
            f"  census terminal_with_duplicates: "
            f"{report['terminal_with_duplicates_count']} "
            f"(delta {delta_s}, rate {rate_s}, {base_s}) "
            f"-> {report['terminal_with_duplicates_severity']}"
        )
        print(f"  report written: {out_file}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
