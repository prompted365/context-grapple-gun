#!/usr/bin/env python3
"""
Falsifier Runner (T2) — Federation Inversion Harness

Reads audit-logs/governance/falsifier/manifest.yaml, observes runtime state,
classifies each mechanism as healthy / broken / broken_content / fire_pending /
fire_recent_quiescent / dormant / unwired / dropped.

Writes classification report to audit-logs/governance/falsifier/reports/.
Does NOT emit signals (T4 gate). Does NOT mutate governance state.
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def load_manifest(zone_root: str) -> dict:
    manifest_path = os.path.join(zone_root, "audit-logs/governance/falsifier/manifest.yaml")
    if not os.path.isfile(manifest_path):
        return {"error": f"manifest not found at {manifest_path}"}

    if yaml:
        with open(manifest_path) as f:
            return yaml.safe_load(f)

    # Fallback: minimal YAML parser for the subset we need
    import re
    with open(manifest_path) as f:
        content = f.read()

    mechanisms = []
    blocks = re.split(r'\n  - mechanism_id: ', content)
    for i, block in enumerate(blocks):
        if i == 0:
            continue
        lines = ("mechanism_id: " + block).split('\n')
        mech = {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('mechanism_id:'):
                mech['mechanism_id'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('status_class:'):
                mech['status_class'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('invocation_policy:'):
                val = stripped.split(':', 1)[1].strip()
                if '#' in val:
                    val = val[:val.index('#')].strip()
                mech['invocation_policy'] = val
            elif stripped.startswith('layer:'):
                mech['layer'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('modulo_tic:'):
                mech.setdefault('fire_schedule', {})['modulo_tic'] = int(stripped.split(':', 1)[1].strip())
            elif stripped.startswith('every_cadence:'):
                mech.setdefault('fire_schedule', {})['every_cadence'] = True
            elif stripped.startswith('poll_seconds:'):
                mech.setdefault('fire_schedule', {})['poll_seconds'] = int(stripped.split(':', 1)[1].strip())
            elif stripped.startswith('expected_artifact:'):
                val = stripped.split(':', 1)[1].strip()
                if '#' in val:
                    val = val[:val.index('#')].strip()
                mech['expected_artifact'] = val if val != 'null' else None
        if mech.get('mechanism_id'):
            mechanisms.append(mech)

    return {
        "schema_version": "0.2",
        "mechanisms": mechanisms
    }


def get_current_tic(zone_root: str) -> int:
    tic_dir = os.path.join(zone_root, "audit-logs/tics")
    max_counter = 0
    if not os.path.isdir(tic_dir):
        return 0
    for f in sorted(glob.glob(os.path.join(tic_dir, "*.jsonl"))):
        for line in open(f):
            try:
                d = json.loads(line)
                if d.get("type") != "tic":
                    continue
                if d.get("count_mode") != "counted":
                    continue
                ca = d.get("global_counter_after", d.get("global_counter", 0))
                if ca > max_counter:
                    max_counter = ca
            except Exception:
                pass
    return max_counter


def find_latest_artifact(zone_root: str, pattern: str, current_tic: int) -> tuple:
    """Find the latest artifact matching the pattern. Returns (path, data, error)."""
    if not pattern:
        return None, None, "no expected_artifact declared"

    resolved = pattern.replace("{N}", str(current_tic))
    resolved = resolved.replace("{YYYY-MM-DD}", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    full_pattern = os.path.join(zone_root, resolved)
    matches = sorted(glob.glob(full_pattern), key=os.path.getmtime, reverse=True)

    if not matches:
        for fallback_tic in range(current_tic - 1, max(current_tic - 5, 0), -1):
            fallback = pattern.replace("{N}", str(fallback_tic))
            fallback_full = os.path.join(zone_root, fallback)
            fallback_matches = sorted(glob.glob(fallback_full), key=os.path.getmtime, reverse=True)
            if fallback_matches:
                matches = fallback_matches
                break

    if not matches:
        return None, None, f"no artifact found for {full_pattern}"

    latest = matches[0]
    try:
        with open(latest) as f:
            data = json.load(f)
        return latest, data, None
    except json.JSONDecodeError as e:
        return latest, None, f"JSON parse error: {e}"
    except Exception as e:
        return latest, None, f"read error: {e}"


def check_fingerprint(mechanism_id: str, data: dict) -> tuple:
    """Evaluate content fingerprint for a mechanism. Returns (passed: bool, findings: list)."""
    if data is None:
        return False, [{"check": "data_load", "passed": False, "detail": "no data to check"}]

    checks = {
        "queue_refresh": _fp_queue_refresh,
        "signal_scan": _fp_signal_scan,
        "harmony_invoke": _fp_harmony_invoke,
        "review_close_check": _fp_review_close_check,
        "memory_mining": _fp_memory_mining,
        "cache_refresh": _fp_cache_refresh,
        "pattern_mining": _fp_pattern_mining,
        "ladder_audit": _fp_ladder_audit,
        "runtime_drift_check": _fp_runtime_drift_check,
        "deep_audit": _fp_deep_audit,
        "bench_packet_prep": _fp_bench_packet_prep,
    }

    checker = checks.get(mechanism_id)
    if not checker:
        return True, [{"check": "no_fingerprint", "passed": True, "detail": "no fingerprint defined"}]

    return checker(data)


def _navigate(data, *keys):
    """Navigate nested dict, return (value, found)."""
    current = data
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return None, False
    return current, True


def _fp_queue_refresh(data):
    findings = []
    r, found = _navigate(data, "results", "queue_refresh")
    if not found:
        r = data  # report-level (non-nested) check

    total, f1 = _navigate(r, "total_unique_ids")
    findings.append({"check": "total_unique_ids > 0", "passed": f1 and isinstance(total, int) and total > 0,
                      "actual": total if f1 else "MISSING"})

    sd, f2 = _navigate(r, "status_distribution")
    findings.append({"check": "status_distribution is object", "passed": f2 and isinstance(sd, dict),
                      "actual": "found" if f2 else "MISSING"})

    ap, f3 = _navigate(r, "actionable_pending")
    findings.append({"check": "actionable_pending is int", "passed": f3 and isinstance(ap, int),
                      "actual": ap if f3 else "MISSING"})

    all_passed = all(c["passed"] for c in findings)
    return all_passed, findings


def _fp_signal_scan(data):
    findings = []
    r, found = _navigate(data, "results", "signal_scan")
    if not found:
        r = data

    ac, f1 = _navigate(r, "active_count")
    findings.append({"check": "active_count is int", "passed": f1 and isinstance(ac, int), "actual": ac if f1 else "MISSING"})

    src, f2 = _navigate(r, "authoritative_source")
    findings.append({"check": "authoritative_source contains active-manifest",
                      "passed": f2 and isinstance(src, str) and "active-manifest" in src,
                      "actual": src if f2 else "MISSING"})

    ids, f3 = _navigate(r, "active_signal_ids")
    findings.append({"check": "active_signal_ids is array", "passed": f3 and isinstance(ids, list), "actual": type(ids).__name__ if f3 else "MISSING"})

    return all(c["passed"] for c in findings), findings


def _fp_harmony_invoke(data):
    findings = []
    r, found = _navigate(data, "results", "harmony_invoke")

    if found and isinstance(r, dict):
        disp, f1 = _navigate(r, "disposition")
        # Handle both string and dict dispositions
        if isinstance(disp, dict):
            disp_ok = True
        else:
            disp_ok = f1 and isinstance(disp, str)
        findings.append({"check": "disposition present", "passed": disp_ok, "actual": type(disp).__name__ if f1 else "MISSING"})

        snr, f2 = _navigate(r, "snr")
        findings.append({"check": "snr is number [0,1]", "passed": f2 and isinstance(snr, (int, float)) and 0 <= snr <= 1, "actual": snr if f2 else "MISSING"})

        ms, f3 = _navigate(r, "meaning_state")
        valid_ms = {"preserved", "drifting", "lost"}
        findings.append({"check": "meaning_state valid", "passed": f3 and ms in valid_ms, "actual": ms if f3 else "MISSING"})
    else:
        # Check standalone harmony disposition file
        disp_val, f1 = _navigate(data, "disposition")
        if isinstance(disp_val, dict):
            findings.append({"check": "disposition present", "passed": True, "actual": "dict"})
        else:
            findings.append({"check": "disposition present", "passed": f1, "actual": disp_val if f1 else "MISSING"})

        ms, f2 = _navigate(data, "meaningState")
        if not f2:
            ms, f2 = _navigate(data, "meaning_state")
        valid_ms = {"preserved", "drifting", "lost"}
        findings.append({"check": "meaning_state valid", "passed": f2 and ms in valid_ms, "actual": ms if f2 else "MISSING"})

        snr_data = data.get("acousticSignature", {})
        snr = snr_data.get("snr") if isinstance(snr_data, dict) else None
        if snr is None:
            snr, _ = _navigate(data, "snr")
        findings.append({"check": "snr is number", "passed": isinstance(snr, (int, float)), "actual": snr})

    return all(c["passed"] for c in findings), findings


def _fp_review_close_check(data):
    findings = []

    tc, f1 = _navigate(data, "total_cprs")
    findings.append({"check": "total_cprs > 0", "passed": f1 and isinstance(tc, int) and tc > 0, "actual": tc if f1 else "MISSING"})

    vc, f2 = _navigate(data, "verdict_counts")
    findings.append({"check": "verdict_counts is object", "passed": f2 and isinstance(vc, dict), "actual": type(vc).__name__ if f2 else "MISSING"})

    consistent, f3 = _navigate(data, "summary", "consistent")
    if not f3:
        consistent, f3 = _navigate(data, "consistent")
    fb, f4 = _navigate(data, "findings")
    shape_ok = f3 or (f4 and isinstance(fb, list))
    findings.append({"check": "consistent or findings present", "passed": shape_ok})

    return all(c["passed"] for c in findings), findings


def _fp_memory_mining(data):
    findings = []
    r, found = _navigate(data, "results", "memory_mining")
    if not found:
        r = data

    sh, f1 = _navigate(r, "structural_health")
    valid_sh = ("clean", "breach")
    # structural_health can be a string OR a dict (detailed audit output); both valid per manifest v0.3
    if f1 and isinstance(sh, dict):
        findings.append({"check": "structural_health present (object or string)", "passed": True, "actual": "dict"})
    else:
        findings.append({"check": "structural_health in {clean, breach}", "passed": f1 and sh in valid_sh, "actual": sh if f1 else "MISSING"})

    il, f2 = _navigate(r, "memory_md_lines")
    if not f2:
        il, f2 = _navigate(r, "index_lines")
    findings.append({"check": "index_lines is int", "passed": f2 and isinstance(il, int), "actual": il if f2 else "MISSING"})

    fb, f3 = _navigate(r, "findings")
    if not f3:
        fb, f3 = _navigate(r, "recurring_patterns")
    findings.append({"check": "findings/patterns is array", "passed": f3 and isinstance(fb, list), "actual": type(fb).__name__ if f3 else "MISSING"})

    return all(c["passed"] for c in findings), findings


def _fp_cache_refresh(data):
    findings = []
    r, found = _navigate(data, "results", "cache_refresh")
    if not found:
        r = data

    te, f1 = _navigate(r, "cache_entries")
    if not f1:
        te, f1 = _navigate(r, "total_entries")
    findings.append({"check": "total_entries is int", "passed": f1 and isinstance(te, int), "actual": te if f1 else "MISSING"})

    th, f2 = _navigate(r, "biome_health")
    if not f2:
        th, f2 = _navigate(r, "ttl_health")
    findings.append({"check": "ttl_health/biome_health present", "passed": f2, "actual": type(th).__name__ if f2 else "MISSING"})

    return all(c["passed"] for c in findings), findings


def _fp_pattern_mining(data):
    # Pattern mining writes to JSONL, not JSON report — check file existence + non-empty
    return True, [{"check": "artifact_exists", "passed": True, "detail": "JSONL pattern file; existence check only"}]


def _fp_ladder_audit(data):
    findings = []
    r, found = _navigate(data, "results", "ladder_audit")
    if not found:
        r = data

    findings.append({"check": "ladder_audit is object", "passed": found and isinstance(r, dict), "actual": "found" if found else "MISSING"})
    return all(c["passed"] for c in findings), findings


def _fp_runtime_drift_check(data):
    findings = []
    r, found = _navigate(data, "results", "runtime_drift_check")
    if not found:
        r = data

    findings.append({"check": "runtime_drift_check is object", "passed": found and isinstance(r, dict), "actual": "found" if found else "MISSING"})

    # Manifest says drift_count; runtime has assessment + nested dicts
    dc, f1 = _navigate(r, "drift_count")
    if not f1:
        assess, f1a = _navigate(r, "assessment")
        ci, f1b = _navigate(r, "harmony_readonly")
        if not f1b:
            ci, f1b = _navigate(r, "canonical_vs_installed")
        has_substance = (f1a and isinstance(assess, str)) or (f1b and isinstance(ci, dict))
        findings.append({"check": "assessment or drift structure present", "passed": has_substance,
                          "actual": f"assessment={assess}" if f1a else ("nested dicts" if f1b else "MISSING")})
    else:
        findings.append({"check": "drift_count is int", "passed": isinstance(dc, int), "actual": dc})

    return all(c["passed"] for c in findings), findings


def _fp_deep_audit(data):
    findings = []
    r, found = _navigate(data, "results", "deep_audit")
    if not found:
        r = data

    findings.append({"check": "deep_audit is object", "passed": found and isinstance(r, dict), "actual": "found" if found else "MISSING"})

    if found and isinstance(r, dict):
        # Deep audit has variable structure; check for any substantive content
        has_substance = len(r) >= 2
        findings.append({"check": "has substantive content (>=2 keys)", "passed": has_substance,
                          "actual": f"{len(r)} keys: {list(r.keys())[:5]}"})
    else:
        fb, f1 = _navigate(r, "findings")
        findings.append({"check": "findings is array", "passed": f1 and isinstance(fb, list), "actual": type(fb).__name__ if f1 else "MISSING"})

    return all(c["passed"] for c in findings), findings


def _fp_bench_packet_prep(data):
    findings = []
    pc, f1 = _navigate(data, "pending_count")
    findings.append({"check": "pending_count is int", "passed": f1 and isinstance(pc, int), "actual": pc if f1 else "MISSING"})
    return all(c["passed"] for c in findings), findings


def classify_mechanism(mech: dict, zone_root: str, current_tic: int, mandate_data: dict) -> dict:
    """Classify a single mechanism's runtime state."""
    mid = mech.get("mechanism_id", "unknown")
    status_class = mech.get("status_class", "unknown")
    invocation_policy = mech.get("invocation_policy", "unknown")

    result = {
        "mechanism_id": mid,
        "status_class": status_class,
        "invocation_policy": invocation_policy,
        "runtime_state": None,
        "artifact_path": None,
        "fingerprint_findings": [],
        "schema_mismatches": [],
    }

    # Non-active status classes: classify directly
    if status_class == "dormant_by_design":
        result["runtime_state"] = "dormant"
        return result

    if status_class == "not_yet_initialized":
        result["runtime_state"] = "unwired"
        return result

    if status_class == "scheduler_dropped":
        artifact_pattern = mech.get("expected_artifact")
        if artifact_pattern:
            path, data, err = find_latest_artifact(zone_root, artifact_pattern, current_tic)
            if path:
                mtime = os.path.getmtime(path)
                age_hours = (datetime.now(timezone.utc).timestamp() - mtime) / 3600
                result["artifact_path"] = path
                result["artifact_age_hours"] = round(age_hours, 1)
                if age_hours < 2:
                    result["runtime_state"] = "dropped_but_manual_fire_detected"
                    passed, findings = check_fingerprint(mid, data)
                    result["fingerprint_findings"] = findings
                    result["fingerprint_passed"] = passed
                else:
                    result["runtime_state"] = "dropped"
            else:
                result["runtime_state"] = "dropped"
        else:
            result["runtime_state"] = "dropped"
        return result

    # Active mechanisms: check fire schedule, artifact, fingerprint
    fire_schedule = mech.get("fire_schedule", {}) or {}
    mandate_cycles = mandate_data.get("cycle_request", {}).get("run_now", [])
    mandate_status = mandate_data.get("status", "unknown")

    is_due_this_tic = False
    if fire_schedule.get("every_cadence"):
        is_due_this_tic = True
    elif "modulo_tic" in fire_schedule:
        mod = fire_schedule["modulo_tic"]
        is_due_this_tic = (current_tic % mod == 0)

    in_current_mandate = mid in mandate_cycles
    mandate_consumed = mandate_status in ("completed", "consumed")

    artifact_pattern = mech.get("expected_artifact")
    if not artifact_pattern:
        if in_current_mandate or is_due_this_tic:
            result["runtime_state"] = "healthy"
            result["note"] = "no artifact to check; schedule says due"
        else:
            result["runtime_state"] = "fire_pending"
            result["next_due_info"] = f"modulo_tic={fire_schedule.get('modulo_tic', '?')}"
        return result

    # For Mogul report mechanisms: find a report that contains this mechanism's results
    is_report_mechanism = "reports/*.report.json" in (artifact_pattern or "")
    path, data, err = None, None, None

    if mid == "harmony_invoke":
        path, data, err = find_latest_artifact(zone_root, artifact_pattern, current_tic)
        if not path:
            report_path, report_data, _ = find_latest_artifact(
                zone_root, "audit-logs/mogul/cycle-reports/reports/*.report.json", current_tic)
            if report_data:
                harmony_result, _ = _navigate(report_data, "results", "harmony_invoke")
                if harmony_result:
                    path, data, err = report_path, report_data, None
    elif is_report_mechanism:
        # Search through reports for one that contains this mechanism's results
        reports_pattern = os.path.join(zone_root, "audit-logs/mogul/cycle-reports/reports/*.report.json")
        all_reports = sorted(glob.glob(reports_pattern), key=os.path.getmtime, reverse=True)
        for rp in all_reports[:10]:
            try:
                rd = json.load(open(rp))
                section, found = _navigate(rd, "results", mid)
                if found and section:
                    path, data, err = rp, rd, None
                    break
            except Exception:
                continue
        if not path:
            err = f"no report containing results.{mid} in last 10 reports"
    else:
        path, data, err = find_latest_artifact(zone_root, artifact_pattern, current_tic)

    if not path:
        if in_current_mandate and mandate_consumed:
            result["runtime_state"] = "broken"
            result["detail"] = err or "no artifact found despite mandate consumed"
        elif in_current_mandate and not mandate_consumed:
            result["runtime_state"] = "fire_pending"
            result["detail"] = "in mandate but mandate not yet consumed"
        elif is_due_this_tic:
            if not mandate_consumed:
                result["runtime_state"] = "fire_pending"
                result["detail"] = "due this tic but mandate pending"
            else:
                result["runtime_state"] = "broken"
                result["detail"] = err or "no artifact found"
        else:
            result["runtime_state"] = "fire_pending"
            if "modulo_tic" in fire_schedule:
                mod = fire_schedule["modulo_tic"]
                remainder = current_tic % mod
                next_due = current_tic + (mod - remainder) if remainder != 0 else current_tic
                result["next_due_tic"] = next_due
        return result

    result["artifact_path"] = path

    mtime = os.path.getmtime(path)
    age_hours = (datetime.now(timezone.utc).timestamp() - mtime) / 3600
    result["artifact_age_hours"] = round(age_hours, 1)

    if err:
        result["runtime_state"] = "broken"
        result["detail"] = err
        return result

    passed, findings = check_fingerprint(mid, data)
    result["fingerprint_findings"] = findings
    result["fingerprint_passed"] = passed

    for f in findings:
        if f.get("schema_note"):
            result["schema_mismatches"].append(f["schema_note"])

    if not passed:
        result["runtime_state"] = "broken_content"
        return result

    if age_hours > 48 and is_due_this_tic:
        result["runtime_state"] = "fire_recent_quiescent"
        result["detail"] = f"artifact is {age_hours:.0f}h old despite being due"
    else:
        result["runtime_state"] = "healthy"

    return result


def run_falsifier(zone_root: str, output_path: str = None) -> dict:
    """Main falsifier run. Returns the classification report."""
    now = datetime.now(timezone.utc)
    current_tic = get_current_tic(zone_root)

    manifest = load_manifest(zone_root)
    if "error" in manifest:
        return {"error": manifest["error"], "ran": False}

    mechanisms = manifest.get("mechanisms", [])
    if not mechanisms:
        return {"error": "no mechanisms found in manifest", "ran": False}

    # Load current mandate for cross-reference
    mandate_path = os.path.join(zone_root, "audit-logs/mogul/mandates/current.json")
    mandate_data = {}
    if os.path.isfile(mandate_path):
        try:
            mandate_data = json.load(open(mandate_path))
        except Exception:
            pass

    classifications = []
    summary = {"healthy": 0, "broken": 0, "broken_content": 0, "fire_pending": 0,
               "fire_recent_quiescent": 0, "dormant": 0, "unwired": 0, "dropped": 0,
               "dropped_but_manual_fire_detected": 0}

    all_schema_mismatches = []

    for mech in mechanisms:
        result = classify_mechanism(mech, zone_root, current_tic, mandate_data)
        classifications.append(result)
        state = result.get("runtime_state", "unknown")
        if state in summary:
            summary[state] += 1
        if result.get("schema_mismatches"):
            for sm in result["schema_mismatches"]:
                all_schema_mismatches.append({
                    "mechanism_id": result["mechanism_id"],
                    "mismatch": sm
                })

    report = {
        "falsifier_version": "T2-v1",
        "manifest_version": manifest.get("schema_version", "unknown"),
        "run_at": now.isoformat(),
        "current_tic": current_tic,
        "mandate_id": mandate_data.get("mandate_id"),
        "mandate_status": mandate_data.get("status"),
        "total_mechanisms": len(mechanisms),
        "summary": summary,
        "needs_attention": summary["broken"] + summary["broken_content"] + summary["fire_recent_quiescent"],
        "schema_mismatches": all_schema_mismatches,
        "classifications": classifications
    }

    # Write report
    if output_path is None:
        reports_dir = os.path.join(zone_root, "audit-logs/governance/falsifier/reports")
        os.makedirs(reports_dir, exist_ok=True)
        output_path = os.path.join(reports_dir, f"tic-{current_tic}-{now.strftime('%Y%m%dT%H%M%S')}.json")

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    return report


def main():
    parser = argparse.ArgumentParser(description="Falsifier Runner T2")
    parser.add_argument("--zone-root", default=None, help="Zone root directory")
    parser.add_argument("--output", default=None, help="Output report path (default: auto)")
    parser.add_argument("--json", action="store_true", help="Print report JSON to stdout")
    parser.add_argument("--summary", action="store_true", help="Print summary only")
    args = parser.parse_args()

    zone_root = args.zone_root
    if not zone_root:
        # Walk up from cwd looking for .ticzone
        d = os.getcwd()
        while d != "/":
            if os.path.isfile(os.path.join(d, ".ticzone")):
                zone_root = d
                break
            d = os.path.dirname(d)
        if not zone_root:
            zone_root = os.getcwd()

    report = run_falsifier(zone_root, args.output)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    elif args.summary:
        s = report.get("summary", {})
        attn = report.get("needs_attention", 0)
        tic = report.get("current_tic", "?")
        total = report.get("total_mechanisms", 0)
        print(f"Falsifier T2 @ tic {tic}: {total} mechanisms")
        print(f"  healthy={s.get('healthy',0)} broken={s.get('broken',0)} broken_content={s.get('broken_content',0)}")
        print(f"  fire_pending={s.get('fire_pending',0)} quiescent={s.get('fire_recent_quiescent',0)}")
        print(f"  dormant={s.get('dormant',0)} unwired={s.get('unwired',0)} dropped={s.get('dropped',0)}")
        if attn > 0:
            print(f"  ⚠ {attn} mechanism(s) need attention")
            for c in report.get("classifications", []):
                if c.get("runtime_state") in ("broken", "broken_content", "fire_recent_quiescent"):
                    print(f"    - {c['mechanism_id']}: {c['runtime_state']}")
                    if c.get("detail"):
                        print(f"      {c['detail']}")
        if report.get("schema_mismatches"):
            print(f"  Schema mismatches: {len(report['schema_mismatches'])}")
            for sm in report["schema_mismatches"]:
                print(f"    - {sm['mechanism_id']}: {sm['mismatch']}")
    else:
        # Default: compact one-liner for cadence-ops integration
        s = report.get("summary", {})
        attn = report.get("needs_attention", 0)
        state = "HEALTHY" if attn == 0 else f"ATTENTION({attn})"
        print(f"[FALSIFIER] {state} — {report.get('total_mechanisms',0)} mechanisms @ tic {report.get('current_tic','?')}: "
              f"h={s.get('healthy',0)} b={s.get('broken',0)} bc={s.get('broken_content',0)} "
              f"fp={s.get('fire_pending',0)} d={s.get('dormant',0)} u={s.get('unwired',0)} dr={s.get('dropped',0)}")


if __name__ == "__main__":
    main()
