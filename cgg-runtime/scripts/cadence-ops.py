#!/usr/bin/env python3
"""cadence-ops.py — Unified cadence operations: tic + conformation + mandate.

Called by /cadence skill. Returns structured JSON on stdout so the skill can
compose the narrative handoff from structured data.

Operations (in order):
  1. Emit tic — append tic event to audit-logs/tics/YYYY-MM-DD.jsonl
  2. Write conformation — snapshot system state at tic boundary
  3. Write mandate — compute due cycles, write mogul mandate

Usage:
    python3 cadence-ops.py --zone-root /path --mode downbeat
    python3 cadence-ops.py --zone-root /path --mode syncopate --skip-conformation --skip-mandate
    python3 cadence-ops.py --zone-root /path --mode downbeat --count-mode ignored --count-reason "experimental"
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing siblings from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, birth_topology
import importlib
_mandate_mod = importlib.import_module("mandate-write")
compute_due_markers = _mandate_mod.compute_due_markers
read_existing_mandate = _mandate_mod.read_existing_mandate
merge_or_supersede = _mandate_mod.merge_or_supersede
build_mandate = _mandate_mod.build_mandate
write_mandate = _mandate_mod.write_mandate


# ---------------------------------------------------------------------------
# Tic emission
# ---------------------------------------------------------------------------

def count_physical_tics(tic_dir: str) -> int:
    """Count physical tics from JSONL files (entries where count_mode == 'counted').

    This is the substrate invariant: canonical tic count is determined by
    JSON-parsing, never by grep or embedded counter fields.
    """
    total = 0
    for f in sorted(glob.glob(os.path.join(tic_dir, "*.jsonl"))):
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "tic" and obj.get("count_mode", "counted") == "counted":
                    total += 1
    return total


def emit_tic(zone_root: str, mode: str, count_mode: str, count_reason: str) -> dict:
    """Emit a tic event. Returns tic result dict."""
    al = audit_logs_path(zone_root)
    tic_dir = os.path.join(al, "tics")
    os.makedirs(tic_dir, exist_ok=True)

    tz_config = load_ticzone(zone_root)
    zone_name = tz_config.get("name", "canonical")

    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now_iso[:10]

    before = count_physical_tics(tic_dir)
    after = before + 1 if count_mode == "counted" else before

    cadence_position = "syncopate" if mode == "syncopate" else "downbeat"

    event = {
        "type": "tic",
        "tic": now_iso,
        "tic_zone": zone_name,
        "cadence_position": cadence_position,
        "count_mode": count_mode,
        "count_reason": count_reason,
        "domain_counter_before": before,
        "domain_counter_after": after,
        "global_counter_before": before,
        "global_counter_after": after,
    }

    # Atomic append (O_APPEND is atomic for small writes on POSIX)
    tic_file = os.path.join(tic_dir, f"{today}.jsonl")
    fd = os.open(tic_file, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(fd, (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
    finally:
        os.close(fd)

    # Update cached mirror
    counter_path = Path.home() / ".claude" / "cgg-tic-counter.json"
    counter_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = counter_path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"count": after, "last_tic": now_iso}) + "\n", encoding="utf-8")
    tmp.replace(counter_path)

    return {
        "emitted": True,
        "timestamp": now_iso,
        "cadence_position": cadence_position,
        "count_mode": count_mode,
        "count_reason": count_reason,
        "counter_before": before,
        "counter_after": after,
        "tic_file": tic_file,
    }


# ---------------------------------------------------------------------------
# Conformation snapshot
# ---------------------------------------------------------------------------

def load_latest_per_id(jsonl_dir: str, type_filter: str = None) -> dict:
    """Load latest-entry-per-ID from all JSONL files in a directory."""
    entries = {}
    d = Path(jsonl_dir)
    if not d.exists():
        return entries
    for f in sorted(d.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if type_filter and obj.get("type") != type_filter:
                continue
            eid = obj.get("id", "")
            if eid:
                entries[eid] = obj
    return entries


def load_queue_pending(queue_path: str) -> list:
    """Load pending CogPRs from queue.jsonl (latest-per-ID, pending status only)."""
    entries = {}
    p = Path(queue_path)
    if not p.exists():
        return []
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

    pending_statuses = {"pending", "enrichment_needed", "enrichment_eligible",
                        "extracted", "review_ready"}
    return [
        {
            "id": e.get("id"),
            "lesson": (e.get("lesson", "") or "")[:100],
            "band": e.get("band", "COGNITIVE"),
            "subsystem": e.get("subsystem", ""),
            "status": e.get("status", ""),
        }
        for e in entries.values()
        if e.get("status") in pending_statuses
    ]


def compute_rules_in_force(zone_root: str) -> dict:
    """Compute rule fingerprints for CLAUDE.md files in the governance chain."""
    rules = {}
    # Site/zone CLAUDE.md
    site_cmd = os.path.join(zone_root, "CLAUDE.md")
    if os.path.isfile(site_cmd):
        content = Path(site_cmd).read_text(encoding="utf-8")
        rules["site"] = {
            "file": site_cmd,
            "lines": content.count("\n") + 1,
            "bytes": len(content.encode("utf-8")),
        }
    # Global CLAUDE.md
    global_cmd = os.path.expanduser("~/.claude/CLAUDE.md")
    if os.path.isfile(global_cmd):
        content = Path(global_cmd).read_text(encoding="utf-8")
        rules["global"] = {
            "file": global_cmd,
            "lines": content.count("\n") + 1,
            "bytes": len(content.encode("utf-8")),
        }
    return rules


def query_governance_compound(zone_root: str) -> list:
    """Call governance.query compound for enriched conformation data.

    Uses subprocess to respect repo boundaries — governance_query.py lives
    in the federation audit-logs, cadence-ops.py lives in the CGG domain.
    """
    al = audit_logs_path(zone_root)
    gq_script = os.path.join(al, "cpg", "scripts", "governance_query.py")
    if not os.path.isfile(gq_script):
        return []

    queries = json.dumps([
        {"query_type": "queue.status"},
        {"query_type": "signals.status"},
        {"query_type": "conformations.status"},
        {"query_type": "estate.snapshot"},
    ])
    try:
        result = subprocess.run(
            [sys.executable, gq_script, "compound", "--queries", queries, "--format", "json"],
            capture_output=True, text=True, timeout=30, cwd=zone_root
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return []


def extract_governance_enrichment(gq_responses: list) -> dict:
    """Extract enrichment fields from governance.query compound responses."""
    enrichment = {}
    for resp in gq_responses:
        qt = resp.get("query_type")
        if qt == "queue.status":
            counts = resp.get("counts", {})
            enrichment["queue_terminal_counts"] = {
                k: counts.get(k, 0)
                for k in ("promoted", "skipped", "superseded", "total")
                if k in counts
            }
        elif qt == "signals.status":
            results = resp.get("results", [])
            active = len([r for r in results if r.get("state") == "active"])
            resolved = len([r for r in results if r.get("state") == "resolved"])
            dismissed = len([r for r in results if r.get("state") == "dismissed"])
            enrichment["manifold_summary"] = {
                "active": active,
                "resolved": resolved,
                "dismissed": dismissed,
            }
            enrichment["manifold_state"] = (
                "CLEAR" if active == 0
                else "HAZARD" if active > 2
                else "ACTIVE"
            )
        elif qt == "conformations.status":
            results = resp.get("results", {})
            enrichment["conformation_coverage"] = {
                "total": results.get("count", 0),
                "gaps": results.get("gap_count", 0),
                "gap_list": results.get("gaps", []),
            }
        elif qt == "estate.snapshot":
            results = resp.get("results", {})
            sel = results.get("profile_selection", {})
            enrichment["estate_profile"] = sel.get("profile", "unknown")
            enrichment["estate_cycles"] = sel.get("cycles", [])
    return enrichment


def write_conformation(zone_root: str, tic_count: int, tic_timestamp: str,
                       posture: str = None) -> dict:
    """Write a conformation snapshot at the current tic boundary."""
    al = audit_logs_path(zone_root)
    tz_config = load_ticzone(zone_root)
    zone_name = tz_config.get("name", "canonical")

    now = datetime.now(timezone.utc)

    # Load signal state
    signal_dir = os.path.join(al, "signals")
    all_signals = load_latest_per_id(signal_dir, type_filter="signal")
    all_warrants = load_latest_per_id(signal_dir, type_filter="warrant")

    active_signal_statuses = {"active", "acknowledged", "working"}
    active_signals = [
        {
            "id": s.get("id"),
            "kind": s.get("kind", ""),
            "band": s.get("band", ""),
            "volume": s.get("volume", 0),
            "status": s.get("status", ""),
            "subsystem": s.get("subsystem", ""),
        }
        for s in all_signals.values()
        if s.get("status") in active_signal_statuses
    ]
    active_warrants = [
        {
            "id": w.get("id"),
            "band": w.get("band", ""),
            "priority": w.get("priority", 0),
            "minting_condition": w.get("minting_condition", ""),
            "status": w.get("status", ""),
        }
        for w in all_warrants.values()
        if w.get("status") in active_signal_statuses
    ]

    # Load pending CogPRs from queue
    queue_path = os.path.join(al, "cprs", "queue.jsonl")
    pending_cogprs = load_queue_pending(queue_path)

    # Zone config for conformation
    zone_block = {
        "name": zone_name,
        "bands": tz_config.get("bands", ["PRIMITIVE", "COGNITIVE", "SOCIAL"]),
        "muffling_per_hop": tz_config.get("muffling_per_hop", 5),
    }
    sg = tz_config.get("signal_governance", {})
    if sg:
        zone_block["signal_governance"] = {
            "warrant_eligible_kinds": sg.get("warrant_eligible_kinds", ["BEACON", "TENSION"]),
            "decay_rate_per_tic": sg.get("decay_rate_per_tic", 2),
            "primitive_audibility_mode": sg.get("primitive_audibility_mode", "threshold_floor"),
        }

    rules = compute_rules_in_force(zone_root)

    conformation = {
        "type": "conformation",
        "tic_count_physical": tic_count,
        "tic": tic_timestamp,
        "tic_zone": zone_name,
        "snapshot_at": now.isoformat(),
        "active_signals": active_signals,
        "active_warrants": active_warrants,
        "pending_cogprs": pending_cogprs,
        "zone": zone_block,
        "rules_in_force": rules,
        "counts": {
            "active_signals": len(active_signals),
            "active_warrants": len(active_warrants),
            "pending_cogprs": len(pending_cogprs),
        },
    }
    if posture:
        conformation["posture"] = posture

    # Enrichment from governance.query compound (cross-repo subprocess call)
    gq_responses = query_governance_compound(zone_root)
    if gq_responses:
        enrichment = extract_governance_enrichment(gq_responses)
        if enrichment:
            conformation["governance_query_enrichment"] = enrichment

    # Write conformation file
    conf_dir = os.path.join(al, "conformations")
    os.makedirs(conf_dir, exist_ok=True)
    conf_path = os.path.join(conf_dir, f"tic-{tic_count}.json")
    Path(conf_path).write_text(json.dumps(conformation, indent=2) + "\n", encoding="utf-8")

    return {
        "written": True,
        "path": conf_path,
        "tic_count": tic_count,
        "summary": conformation["counts"],
    }


# ---------------------------------------------------------------------------
# Mandate cascade
# ---------------------------------------------------------------------------

def compute_due_cycles(tic: int) -> list:
    """Compute which governance cycles are due at this tic."""
    cycles = ["queue_refresh", "signal_scan"]  # always due

    if tic % 3 == 0:
        cycles.append("memory_mining")
    if tic % 4 == 0:
        cycles.append("pattern_mining")
    if tic % 5 == 0:
        cycles.extend(["ladder_audit", "runtime_drift_check"])
    if tic % 8 == 0:
        cycles.append("deep_audit")

    return cycles


def write_cadence_mandate(zone_root: str, tic: int, trigger_source: str,
                          conformation_ref: str = None) -> dict:
    """Write a Mogul mandate for the next tic's due cycles.

    Delegates to mandate-write.py's functions for merge-before-write semantics.
    """
    next_tic = tic + 1
    due_cycles = compute_due_cycles(next_tic)
    due_markers = compute_due_markers(tic)

    # Read existing mandate for merge-before-write
    al = audit_logs_path(zone_root)
    mandate_path = Path(al) / "mogul" / "mandates" / "current.json"
    existing = read_existing_mandate(mandate_path)

    # Determine merge/supersede
    final_cycles, merged_from, supersedes = merge_or_supersede(existing, due_cycles)

    # Build mandate
    mandate = build_mandate(
        trigger_kind="cadence",
        trigger_source=trigger_source,
        tic=tic,
        cycles=final_cycles,
        merged_from=merged_from,
        supersedes=supersedes,
        conformation_ref=conformation_ref,
        runtime_verified=False,
        zone_root_path=zone_root,
    )

    # Write
    written_path = write_mandate(mandate, Path(zone_root))

    return {
        "written": True,
        "mandate_id": mandate.get("mandate_id"),
        "cycles": final_cycles,
        "merged_from": merged_from,
        "supersedes": supersedes,
        "path": str(written_path),
        "due_markers": due_markers,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="cadence-ops: unified tic + conformation + mandate"
    )
    parser.add_argument("--zone-root", default=None,
                        help="Zone root path (auto-resolved if omitted)")
    parser.add_argument("--mode", choices=["downbeat", "syncopate"], default="downbeat",
                        help="Cadence mode (default: downbeat)")
    parser.add_argument("--count-mode", choices=["counted", "ignored"], default="counted",
                        help="Tic count mode (default: counted)")
    parser.add_argument("--count-reason", default=None,
                        help="Reason for count mode (default: derived from mode)")
    parser.add_argument("--posture", default=None,
                        help="Current session posture (e.g., ENG/DIRECT)")
    parser.add_argument("--trigger-source", default="cgg-runtime/skills/cadence/SKILL.md",
                        help="Trigger source ref for mandate")
    parser.add_argument("--skip-conformation", action="store_true",
                        help="Skip conformation snapshot (syncopate default)")
    parser.add_argument("--skip-mandate", action="store_true",
                        help="Skip mandate write")

    args = parser.parse_args()

    zone_root = args.zone_root or resolve_zone_root()

    # Default count_reason from mode
    count_reason = args.count_reason
    if not count_reason:
        count_reason = "cadence" if args.mode == "downbeat" else "emergency_syncopate"

    result = {"mode": args.mode}

    # 1. Emit tic
    tic_result = emit_tic(zone_root, args.mode, args.count_mode, count_reason)
    result["tic"] = tic_result

    tic_count = tic_result["counter_after"]
    tic_timestamp = tic_result["timestamp"]

    # 2. Conformation (skip for syncopate by default)
    skip_conf = args.skip_conformation
    if args.mode == "syncopate" and not args.skip_conformation:
        # Syncopate skips conformation by default unless explicitly kept
        # (the flag --skip-conformation is still respected for downbeat)
        skip_conf = True

    if not skip_conf:
        conf_result = write_conformation(zone_root, tic_count, tic_timestamp, args.posture)
        result["conformation"] = conf_result
    else:
        result["conformation"] = {"written": False, "reason": "skipped"}

    # 3. Mandate (skip for syncopate by default)
    skip_mand = args.skip_mandate
    if args.mode == "syncopate" and not args.skip_mandate:
        skip_mand = True

    if not skip_mand:
        conf_ref = result.get("conformation", {}).get("path")
        mandate_result = write_cadence_mandate(zone_root, tic_count, args.trigger_source, conf_ref)
        result["mandate"] = mandate_result
    else:
        result["mandate"] = {"written": False, "reason": "skipped"}

    # Output
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
