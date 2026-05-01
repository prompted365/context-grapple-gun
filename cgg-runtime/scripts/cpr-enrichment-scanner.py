#!/usr/bin/env python3
"""
CPR Enrichment Scanner — deterministic evidence gatherer for holding CPRs.

Scans queue.jsonl for CPRs at enrichment_needed or enrichment_eligible,
gathers evidence (git commits, test files, signal correlation, source stability,
cross-references), updates enrichment entries in-place in queue.jsonl.

No LLM. Background-safe. Designed to run at SessionStart from session-restore.sh.

Subsystem-to-path mappings are loaded from .cgg/subsystems.json (zone root).
Falls back to empty mappings if the config file doesn't exist.

Usage:
  python3 cpr-enrichment-scanner.py --project-dir /path/to/project
  python3 cpr-enrichment-scanner.py --project-dir /path/to/project --quiet
  python3 cpr-enrichment-scanner.py --project-dir /path/to/project --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, load_subsystems_config, audit_logs_path, birth_topology
from pattern_miner import gather_recurrence_count


HOLDING_STATUSES = {"enrichment_needed", "enrichment_eligible"}


# ---------------------------------------------------------------------------
# Queue I/O
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


def get_holding_cprs(queue_entries):
    """Filter to CPRs in enrichment holding states."""
    return {
        eid: entry for eid, entry in queue_entries.items()
        if entry.get("status") in HOLDING_STATUSES
    }


# ---------------------------------------------------------------------------
# Evidence Gatherers
# ---------------------------------------------------------------------------

def gather_git_evidence(cpr, project_dir, subsystem_config):
    """Find commits since CPR birth that touch related files/subsystem."""
    evidence = []
    source = cpr.get("source", "")
    source_date = cpr.get("source_date", "")
    subsystem = cpr.get("subsystem", "")

    if not source_date:
        return evidence

    paths_to_check = []
    if ":" in source:
        source_file = source.split(":")[0]
        if os.path.exists(os.path.join(project_dir, source_file)):
            paths_to_check.append(source_file)

    subsystem_dirs = subsystem_config.get("subsystems", {}).get(subsystem, [])
    for d in subsystem_dirs:
        if os.path.exists(os.path.join(project_dir, d.rstrip("/"))):
            paths_to_check.append(d)

    for scope in cpr.get("recommended_scopes", []):
        if not scope.startswith("~") and os.path.exists(os.path.join(project_dir, scope)):
            paths_to_check.append(scope)

    if not paths_to_check:
        return evidence

    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"--since={source_date}",
             "--", *paths_to_check],
            capture_output=True, text=True, timeout=10,
            cwd=project_dir,
        )
        if result.returncode == 0 and result.stdout.strip():
            commits = result.stdout.strip().splitlines()
            evidence.append({
                "evidence_type": "commits_since_birth",
                "value": f"{len(commits)} commits touching related paths since {source_date}",
                "detail": [c.strip() for c in commits[:5]],
                "paths_checked": paths_to_check[:5],
            })
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return evidence


def gather_test_evidence(cpr, project_dir, subsystem_config):
    """Check if tests exist and have been modified for the subsystem."""
    evidence = []
    subsystem = cpr.get("subsystem", "")
    if not subsystem:
        return evidence

    test_patterns = subsystem_config.get("test_paths", {}).get(subsystem, [])
    found_tests = []

    for pattern in test_patterns:
        matches = list(Path(project_dir).glob(pattern))
        found_tests.extend(matches)

    if found_tests:
        source_date = cpr.get("source_date", "")
        recent = []
        for test_file in found_tests[:10]:
            try:
                mtime = datetime.fromtimestamp(
                    test_file.stat().st_mtime, tz=timezone.utc
                )
                if source_date:
                    birth = datetime.fromisoformat(source_date + "T00:00:00+00:00")
                    if mtime > birth:
                        recent.append(str(test_file.relative_to(project_dir)))
            except (ValueError, OSError):
                continue

        if recent:
            evidence.append({
                "evidence_type": "test_files_modified",
                "value": f"{len(recent)} test files modified since birth",
                "detail": recent[:5],
            })
        elif found_tests:
            evidence.append({
                "evidence_type": "test_files_exist",
                "value": f"{len(found_tests)} test files exist for {subsystem}",
                "detail": [str(f.relative_to(project_dir)) for f in found_tests[:5]],
            })

    return evidence


def gather_signal_evidence(cpr, signal_dir):
    """Check for active signals related to this CPR's subsystem."""
    evidence = []
    subsystem = cpr.get("subsystem", "")
    if not subsystem:
        return evidence

    if not signal_dir.exists():
        return evidence

    related_signals = []
    for f in sorted(signal_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if (d.get("subsystem") == subsystem
                        and d.get("status") in ("active", "working", "acknowledged")
                        and d.get("type") == "signal"):
                    related_signals = [
                        s for s in related_signals if s.get("id") != d.get("id")
                    ]
                    related_signals.append(d)
            except json.JSONDecodeError:
                continue

    if related_signals:
        evidence.append({
            "evidence_type": "signal_correlation",
            "value": f"{len(related_signals)} active signals for subsystem {subsystem}",
            "detail": [
                f"{s['id']} (vol={s.get('volume', 0)}, {s.get('kind', '?')})"
                for s in related_signals[:5]
            ],
        })

    return evidence


def gather_source_stability(cpr, project_dir):
    """Check if the source file still exists and CPR content is present."""
    evidence = []
    source = cpr.get("source", "")
    lesson = cpr.get("lesson", "")

    if not source:
        return evidence

    source_file = source.split(":")[0] if ":" in source else source
    source_path = Path(project_dir) / source_file

    if not source_path.exists():
        # Memory files live in ~/.claude/projects/<project_key>/memory/
        project_key = project_dir.replace("/", "-")
        memory_dir = Path.home() / ".claude" / "projects" / project_key / "memory"
        memory_candidate = memory_dir / source_file
        if memory_candidate.exists():
            source_path = memory_candidate

    if source_path.exists():
        try:
            content = source_path.read_text(encoding="utf-8")
            if lesson and lesson[:60] in content:
                evidence.append({
                    "evidence_type": "source_stable",
                    "value": "Source file exists, lesson text still present",
                })
            else:
                evidence.append({
                    "evidence_type": "source_diverged",
                    "value": "Source file exists but lesson text may have changed",
                })
        except Exception:
            pass
    else:
        evidence.append({
            "evidence_type": "source_missing",
            "value": f"Source file {source_file} not found",
        })

    return evidence


def gather_cross_references(cpr, project_dir):
    """Grep for the lesson's key terms in governance files (organic adoption)."""
    evidence = []
    lesson = cpr.get("lesson", "")
    source = cpr.get("source", "")
    if not lesson:
        return evidence

    words = lesson.split()
    if len(words) < 3:
        return evidence

    mid = len(words) // 2
    search_phrase = " ".join(words[max(0, mid - 1):mid + 2])

    try:
        result = subprocess.run(
            ["grep", "-rl", "--include=*.md", search_phrase, project_dir],
            capture_output=True, text=True, timeout=10,
            cwd=project_dir,
        )
        if result.returncode == 0 and result.stdout.strip():
            files = result.stdout.strip().splitlines()
            source_file = source.split(":")[0] if ":" in source else ""
            cross_refs = [
                f for f in files
                if source_file not in f and ".git" not in f
            ]
            if cross_refs:
                evidence.append({
                    "evidence_type": "cross_reference",
                    "value": f"Lesson referenced in {len(cross_refs)} other files",
                    "detail": [
                        str(Path(f).relative_to(project_dir))
                        for f in cross_refs[:5]
                        if f.startswith(project_dir)
                    ],
                })
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return evidence


def gather_target_absence(cpr, project_dir):
    """Check if recommended_scopes targets lack the lesson content.

    Confirms the promotion target actually needs the lesson — prevents
    promoting content that's already been absorbed.
    """
    evidence = []
    lesson = cpr.get("lesson", "")
    scopes = cpr.get("recommended_scopes", [])

    if not lesson or not scopes:
        return evidence

    snippet = lesson[:50]
    absent_targets = []
    present_targets = []

    for scope in scopes:
        # Strip parenthetical description from scope before path resolution.
        # Convention: recommended_scopes uses "path (description)" — the
        # parenthetical is human-facing context, not part of the path.
        # (Patched tic 207: prior version passed full string to Path() which
        # produced false target_absence_confirmed reports — surfaced by Tier 1
        # swarm across many records.)
        scope_path_str = scope.split(" (")[0].strip() if " (" in scope else scope.strip()

        # Federation-prefix tolerance: operators write "canonical/X" meaning
        # the federation root file, but project_dir IS canonical. Try literal
        # first, then federation-prefix-stripped.
        scope_path = None
        if scope_path_str.startswith("~"):
            candidate = Path(os.path.expanduser(scope_path_str))
            if candidate.exists():
                scope_path = candidate
        else:
            candidates = [scope_path_str]
            fed_name = Path(project_dir).name
            if scope_path_str.startswith(fed_name + "/"):
                candidates.append(scope_path_str[len(fed_name) + 1:])
            for cand in candidates:
                cand_path = Path(project_dir) / cand
                if cand_path.exists():
                    scope_path = cand_path
                    break
            if scope_path is None:
                # Use literal candidate for "missing" reporting
                scope_path = Path(project_dir) / scope_path_str

        if not scope_path.exists():
            absent_targets.append(f"{scope} (file missing)")
            continue

        try:
            content = scope_path.read_text(encoding="utf-8")
            if snippet in content:
                present_targets.append(scope)
            else:
                absent_targets.append(scope)
        except (OSError, UnicodeDecodeError):
            absent_targets.append(f"{scope} (unreadable)")

    if absent_targets:
        evidence.append({
            "evidence_type": "target_absence_confirmed",
            "value": f"{len(absent_targets)}/{len(scopes)} targets lack lesson content",
            "detail": absent_targets[:5],
        })
    elif present_targets:
        evidence.append({
            "evidence_type": "target_already_present",
            "value": f"Lesson already present in all {len(present_targets)} targets",
            "detail": present_targets[:5],
        })

    return evidence


def compute_enrichment_confidence(enrichment_list):
    """Compute composite confidence score from gathered evidence.

    Weights by evidence type reliability. Returns float in [0.0, 1.0].
    """
    weights = {
        "source_stable": 0.20,
        "commits_since_birth": 0.15,
        "test_files_modified": 0.15,
        "test_files_exist": 0.05,
        "signal_correlation": 0.10,
        "cross_reference": 0.15,
        "recurrence_count": 0.10,
        "target_absence_confirmed": 0.15,
    }
    penalties = {
        "source_missing": -0.30,
        "source_diverged": -0.15,
        "target_already_present": -0.20,
    }

    score = 0.0
    for ev in enrichment_list:
        et = ev.get("evidence_type", "")
        if et in weights:
            score += weights[et]
        elif et in penalties:
            score += penalties[et]

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def scan_and_enrich(project_dir, dry_run=False, quiet=False):
    """Main enrichment pipeline: scan holding CPRs, gather evidence, append."""
    project_dir = os.path.abspath(project_dir)
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)
    subsystem_config = load_subsystems_config(project_dir)

    queue_path = os.path.join(al_path, "cprs", "queue.jsonl")
    signal_dir = Path(al_path) / "signals"

    queue = load_queue(queue_path)
    holding = get_holding_cprs(queue)

    if not holding:
        if not quiet:
            print("0")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    topo = birth_topology(project_dir)
    updated_count = 0
    entries_to_append = []

    for cpr_id, cpr in holding.items():
        all_evidence = []
        all_evidence.extend(gather_git_evidence(cpr, project_dir, subsystem_config))
        all_evidence.extend(gather_test_evidence(cpr, project_dir, subsystem_config))
        all_evidence.extend(gather_signal_evidence(cpr, signal_dir))
        all_evidence.extend(gather_source_stability(cpr, project_dir))
        all_evidence.extend(gather_cross_references(cpr, project_dir))
        all_evidence.extend(gather_recurrence_count(cpr, queue))
        all_evidence.extend(gather_target_absence(cpr, project_dir))

        if not all_evidence:
            # Record scan metadata even with zero evidence — the prior silent
            # skip hid genuine zero-evidence state (missing source_date,
            # subsystem config absent) as indistinguishable from "not scanned."
            # Confidence scoring remains unchanged; only audit trail is added.
            missing = [
                f for f in ("source", "source_date", "subsystem",
                            "recommended_scopes", "lesson")
                if not cpr.get(f)
            ]
            reason = (
                f"no gatherer produced evidence (missing: {', '.join(missing)})"
                if missing else "no gatherer produced evidence"
            )
            updated_entry = {**cpr}
            updated_entry["enrichment_scanned_at"] = now
            updated_entry["enrichment_scan_count"] = cpr.get("enrichment_scan_count", 0) + 1
            updated_entry["no_evidence_reason"] = reason
            entries_to_append.append(updated_entry)
            updated_count += 1
            if not quiet:
                print(f"  {cpr_id}: 0 evidence ({reason})")
            continue

        existing_enrichment = cpr.get("enrichment", [])
        existing_types = {e.get("evidence_type") for e in existing_enrichment}
        new_evidence = [
            e for e in all_evidence
            if e["evidence_type"] not in existing_types
        ]

        if not new_evidence:
            continue

        merged_enrichment = existing_enrichment + [
            {**e, "gathered_at": now, "gathered_by": "cpr-enrichment-scanner"}
            for e in new_evidence
        ]

        updated_entry = {**cpr, "enrichment": merged_enrichment}
        updated_entry["enrichment_scanned_at"] = now
        updated_entry["enrichment_rung"] = topo["birth_rung"]
        updated_entry["enrichment_scan_count"] = cpr.get("enrichment_scan_count", 0) + 1
        updated_entry["enrichment_confidence"] = round(
            compute_enrichment_confidence(merged_enrichment), 4
        )
        updated_entry.pop("no_evidence_reason", None)

        entries_to_append.append(updated_entry)
        updated_count += 1

        if not quiet:
            print(
                f"  {cpr_id}: +{len(new_evidence)} evidence "
                f"({', '.join(e['evidence_type'] for e in new_evidence)})"
            )

    if entries_to_append and not dry_run:
        # Update-in-place: replace existing entries by ID instead of appending
        # duplicates. Read all lines, substitute matching IDs, write back.
        update_map = {e["id"]: e for e in entries_to_append}
        p = Path(queue_path)
        os.makedirs(os.path.dirname(queue_path), exist_ok=True)

        import fcntl
        lockfile = queue_path + ".lock"
        with open(lockfile, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
                new_lines = []
                replaced_ids = set()
                for line in lines:
                    line_s = line.strip()
                    if not line_s:
                        new_lines.append(line)
                        continue
                    try:
                        d = json.loads(line_s)
                        eid = d.get("id", "")
                        if eid in update_map:
                            new_lines.append(json.dumps(update_map[eid], separators=(",", ":"), default=str))
                            replaced_ids.add(eid)
                        else:
                            new_lines.append(line)
                    except json.JSONDecodeError:
                        new_lines.append(line)
                # Append any entries whose IDs were not found in existing lines
                for eid, entry in update_map.items():
                    if eid not in replaced_ids:
                        new_lines.append(json.dumps(entry, separators=(",", ":"), default=str))
                p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    if not quiet:
        print(f"{updated_count}")

    return updated_count


def main():
    parser = argparse.ArgumentParser(
        description="CPR Enrichment Scanner — deterministic evidence gatherer"
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="Project/zone root directory (auto-resolved if omitted)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true",
                        help="Print only the count of enriched CPRs")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    project_dir = args.project_dir or resolve_zone_root()
    count = scan_and_enrich(
        project_dir,
        dry_run=args.dry_run,
        quiet=args.quiet and not args.verbose,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
