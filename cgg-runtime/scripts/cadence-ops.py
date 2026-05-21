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

# Cockpit intent emitter (T2b I-B, tic 267). Import via lib/ subdir.
# Soft-fail import: if cockpit_intent_emit is unavailable (older install), the
# emit step short-circuits below. The cadence pipeline never blocks on it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
try:
    from cockpit_intent_emit import emit_intent as _emit_cockpit_intent
except ImportError:
    _emit_cockpit_intent = None


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
    tmp.write_text(json.dumps({"count": after, "previous_count": before, "last_tic": now_iso}) + "\n", encoding="utf-8")
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
    result = []
    for e in entries.values():
        if e.get("status") not in pending_statuses:
            continue
        item = {
            "id": e.get("id"),
            "lesson": (e.get("lesson", "") or "")[:100],
            "band": e.get("band", "COGNITIVE"),
            "subsystem": e.get("subsystem", ""),
            "status": e.get("status", ""),
        }
        if e.get("status") == "deferred" and e.get("deferred_to_tic"):
            item["deferred_to_tic"] = e["deferred_to_tic"]
        result.append(item)
    return result


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
            # manifold_state is a pure count threshold:
            #   active == 0    -> CLEAR
            #   active in 1..2 -> ACTIVE
            #   active > 2     -> HAZARD
            #
            # Caveat (cpr_hazard_label_under_discriminates_tic173,
            # tic 173 -> tic 188 review): the label has NO severity / band /
            # kind weighting. A federation with 7 WATCH-band hygiene signals
            # gets the same HAZARD label as one with 7 PRIMITIVE BEACONs. The
            # label reads as danger but mechanically means "more than two
            # signals are being tracked." Under-discriminates between
            # `unattended-emergency` and `tracked-hygiene` regimes. Refining
            # this is open work (weight by band/kind, subtract held-class
            # signals, or split into orthogonal axes count + severity).
            # Band: COGNITIVE.
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

    # Load signal state from active-manifest.jsonl (authoritative source).
    # Daily signal logs contain raw emissions with mixed schemas; the manifest
    # is the curated, deduplicated truth for active/resolved state.
    signal_dir = os.path.join(al, "signals")
    manifest_path = os.path.join(signal_dir, "active-manifest.jsonl")
    manifest_entries = []
    if os.path.isfile(manifest_path):
        for line in Path(manifest_path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                manifest_entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    active_signal_statuses = {"active", "acknowledged", "working"}

    # Latest-entry-per-signal_id collapse. active-manifest.jsonl is append-only
    # under Terminal-State Valve discipline; multiple rows for the same signal
    # accumulate as state transitions land (active -> acknowledged -> working
    # -> resolved). Without dedup, the conformation reports stale rows
    # alongside their successors — observed as the recurring 6 raw / 3 unique
    # gap across tic 222-224 conformations. Mirrors the latest-entry-per-id
    # discipline already applied to warrants via load_latest_per_id().
    latest_by_signal_id = {}
    for s in manifest_entries:
        sid = s.get("signal_id") or s.get("id", "")
        if not sid:
            continue
        latest_by_signal_id[sid] = s

    active_signals = [
        {
            "id": s.get("signal_id", s.get("id", "")),
            "kind": s.get("kind", ""),
            "band": s.get("band", ""),
            "volume": s.get("volume", 0),
            "status": s.get("status", ""),
            "subsystem": s.get("subsystem", ""),
        }
        for s in latest_by_signal_id.values()
        if s.get("status") in active_signal_statuses
    ]

    # Warrants: still scan daily logs (no manifest yet for warrants)
    all_warrants = load_latest_per_id(signal_dir, type_filter="warrant")
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
    # harmony_invoke joins the always-due lane alongside queue_refresh +
    # signal_scan. Slice doctrine (Slice as Bounded World Preservation,
    # federation CLAUDE.md tic 226) names harmony as a Layer-1 slice
    # contributor; mod-4 cadence left ~75% of slices with stale or absent
    # harmony refs. Tic-226 probe confirmed cost: 0.42s wall-clock + ~207KB
    # artifact per fire — cheap enough for per-tic cadence. Pairs with
    # queue_refresh as the lightest existing per-tic cycle rather than
    # opening a standalone harmony lane. pattern_mining stays decoupled
    # at mod 4 (the original tic-213 piggyback rationale was cycle
    # proliferation avoidance, not pattern_mining coupling per se).
    cycles = ["queue_refresh", "signal_scan", "harmony_invoke"]  # always due

    if tic % 2 == 0:
        # T6a (tic 259 close, landed at tic 260 entry): re-include review_close_check
        # in mandate cycles. T5a (CGG commit 47a916f) landed the runtime emit-side
        # dedup gate, making the Artifact-Count-≠-1 N=2 case structurally impossible
        # (one canonical {mandate_id}-check.json per mandate). The cycle-7+ inhibition
        # pattern (tics 252-257 omission + tic 258 failed mandate) is mechanically
        # resolved; this re-include closes the operational source per the
        # Conductor-Score-Runtime Parity invariant. Modulo chosen as `tic % 2 == 0`:
        # dense enough to track /review-close drift (which fires every 2-3 tics in
        # active periods) without padding every mandate.
        cycles.append("review_close_check")
    if tic % 3 == 0:
        cycles.append("memory_mining")
        cycles.append("cache_refresh")
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

    # 2. Conformation — always generated for both downbeat and syncopate.
    # CogPR-43: the tic-conformation invariant requires every counted tic
    # to have a corresponding conformation. --skip-conformation is only
    # honored for syncopate (emergency override); downbeat never skips.
    if args.mode == "downbeat":
        skip_conf = False  # CogPR-43: downbeat NEVER skips
    else:
        skip_conf = args.skip_conformation  # syncopate: only if explicitly requested

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

    # 4. Cockpit-intent emission (T2b I-B, tic 267) — per spec
    # audit-logs/governance/cockpit-intent-t2b-invocation-discipline-spec-tic264.md.
    # Every /cadence emission produces an explicit declared state boundary that
    # downstream consumers should be able to read from the cockpit.intent stream.
    # intent_class is always 'observe' for I-B (the cadence emission itself is a
    # governance observation, not an interface mutation).
    # Fail-soft: errors log to result["cockpit_intent"] but never block cadence output.
    if _emit_cockpit_intent is not None and args.posture:
        try:
            intent_result = _emit_cockpit_intent(
                zone_root=zone_root,
                intent_class="observe",
                source_object_ref=f"cadence.session.tic{tic_count}",
                source_path=args.trigger_source,
                required_gate="G0_auto_audit",
                posture=args.posture,
                mode="LITE",  # cadence emissions are non-interactive; LITE is the safe default
                operator_ref="ent_breyden",
                actor="cadence-ops.emit_cadence",
                source_ref="cgg-runtime/scripts/cadence-ops.py:main",
            )
            result["cockpit_intent"] = {
                "emitted": intent_result.get("emitted", False),
                "intent_id": intent_result.get("intent_id"),
                "reason": intent_result.get("reason"),
            }
        except Exception as err:  # noqa: BLE001 — fail-soft
            result["cockpit_intent"] = {"emitted": False, "error": str(err)}
    else:
        result["cockpit_intent"] = {
            "emitted": False,
            "reason": (
                "skipped: emitter unavailable" if _emit_cockpit_intent is None
                else "skipped: --posture not provided"
            ),
        }

    # 5. Memory.md health audit (tic 268) — structural observability sweep.
    # Born tic 268 from the post-Pass-4 dehydration arc, after MEMORY.md was
    # trimmed from 4,105 → 205 lines (95% reduction). Detects the structural
    # failure modes that produced the bloat: orphan topic files, dead refs,
    # inline extraction candidates. Line count is reported but informational
    # only — real breaches are structural per the spirit-over-letter discipline.
    # Fail-soft: never blocks cadence output. Audit script lives in canonical
    # at audit-logs/governance/memory-md-audit.py; resolved from zone_root.
    audit_script = Path(zone_root) / "audit-logs" / "governance" / "memory-md-audit.py"
    if audit_script.exists():
        try:
            audit_proc = subprocess.run(
                ["python3", str(audit_script), "--tic", str(tic_count)],
                capture_output=True, text=True, timeout=15,
            )
            # Exit 0 = HEALTHY; exit 1 = structural breach (orphans/dead refs/
            # inline candidates). Both are valid execution outcomes from
            # cadence's perspective — we surface the status, not block on it.
            first_line = audit_proc.stdout.split("\n")[0] if audit_proc.stdout else None
            result["memory_md_audit"] = {
                "ran": True,
                "exit_code": audit_proc.returncode,
                "healthy": audit_proc.returncode == 0,
                "summary": first_line,
            }
        except Exception as err:  # noqa: BLE001 — fail-soft
            result["memory_md_audit"] = {"ran": False, "error": str(err)}
    else:
        result["memory_md_audit"] = {
            "ran": False,
            "reason": "audit script not found at expected path",
        }

    # 6. Claude agents snapshot (tic 270) — read-only observability sensor.
    # Born tic 270 under Architect Path C adoption. Captures native Claude
    # Code `claude agents --json` output as sensor data ONLY — never used
    # to mint warrants, never written to queue.jsonl, never replaces
    # inbox-registry / mandate-current / conformation / Mogul reports /
    # review receipts. Fail-soft on missing command, timeout, malformed
    # JSON, or non-zero exit; the cadence pipeline never raises on the
    # integration. Output schema is stable and boring: count + kind
    # summary + status summary, no per-session detail (no pid, no
    # sessionId, no cwd — privacy + noise).
    try:
        agents_proc = subprocess.run(
            ["claude", "agents", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if agents_proc.returncode != 0:
            result["claude_agents_snapshot"] = {
                "ran": True,
                "command_available": True,
                "exit_code": agents_proc.returncode,
                "captured_at": tic_timestamp,
                "count": None,
                "kinds": None,
                "statuses": None,
                "error": (agents_proc.stderr or "")[:200] or "exit_nonzero",
            }
        else:
            try:
                agents_list = json.loads(agents_proc.stdout or "[]")
                if not isinstance(agents_list, list):
                    raise ValueError("expected JSON array")
                kinds: dict = {}
                statuses: dict = {}
                for entry in agents_list:
                    if not isinstance(entry, dict):
                        continue
                    k = entry.get("kind") or "unknown"
                    s = entry.get("status") or "unknown"
                    kinds[k] = kinds.get(k, 0) + 1
                    statuses[s] = statuses.get(s, 0) + 1
                result["claude_agents_snapshot"] = {
                    "ran": True,
                    "command_available": True,
                    "exit_code": 0,
                    "captured_at": tic_timestamp,
                    "count": len(agents_list),
                    "kinds": kinds,
                    "statuses": statuses,
                    "error": None,
                }
            except (json.JSONDecodeError, ValueError) as parse_err:
                result["claude_agents_snapshot"] = {
                    "ran": True,
                    "command_available": True,
                    "exit_code": 0,
                    "captured_at": tic_timestamp,
                    "count": None,
                    "kinds": None,
                    "statuses": None,
                    "error": f"json_parse_failed: {str(parse_err)[:160]}",
                }
    except FileNotFoundError:
        result["claude_agents_snapshot"] = {
            "ran": False,
            "command_available": False,
            "exit_code": None,
            "captured_at": tic_timestamp,
            "count": None,
            "kinds": None,
            "statuses": None,
            "error": "claude binary not found in PATH",
        }
    except subprocess.TimeoutExpired:
        result["claude_agents_snapshot"] = {
            "ran": False,
            "command_available": True,
            "exit_code": None,
            "captured_at": tic_timestamp,
            "count": None,
            "kinds": None,
            "statuses": None,
            "error": "timeout after 5s",
        }
    except Exception as err:  # noqa: BLE001 — fail-soft
        result["claude_agents_snapshot"] = {
            "ran": False,
            "command_available": None,
            "exit_code": None,
            "captured_at": tic_timestamp,
            "count": None,
            "kinds": None,
            "statuses": None,
            "error": str(err)[:200],
        }

    # Output
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
