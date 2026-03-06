#!/usr/bin/env python3
"""
Deterministic ripple-assessor — structured-data-only proposal compiler.

Replaces the LLM-based ripple-assessor agent. No heuristics beyond treaty rules.

Inputs:  plan file (with cgg-evaluate block), signal JSONLs, tic counter.
Output:  ~/.claude/grapple-proposals/latest.md with truthiness checksum.

All paths resolve from zone root (via .ticzone walk-up), never cwd.

Usage:
  python3 ripple-assessor.py --plan PATH [--signals-dir PATH] [--output PATH]
  python3 ripple-assessor.py --plan PATH --quiet   # for hook integration
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path


# ---------------------------------------------------------------------------
# cgg-evaluate block parsing
# ---------------------------------------------------------------------------

def _unquote(s):
    """Remove surrounding quotes, coerce ints."""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    try:
        return int(s)
    except ValueError:
        return s


def parse_evaluate_block(plan_path):
    """Extract cgg-evaluate block from plan file, return (dict | None, plan_text)."""
    text = Path(plan_path).read_text(encoding="utf-8")

    start = text.find("<!-- cgg-evaluate")
    if start == -1:
        return None, text
    content_start = start + len("<!-- cgg-evaluate")
    end = text.find("-->", content_start)
    if end == -1:
        return None, text

    block = text[content_start:end]

    try:
        import yaml
        parsed = yaml.safe_load(block)
        if isinstance(parsed, dict):
            return parsed, text
    except Exception:
        pass

    return _parse_evaluate_lines(block), text


def _parse_evaluate_lines(block):
    """Minimal parser for the cgg-evaluate block's fixed schema."""
    result = {}
    lines = [l for l in block.split("\n") if l.strip()]
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        base_indent = len(line) - len(line.lstrip())

        if ":" not in stripped or stripped.startswith("-"):
            i += 1
            continue

        key, val = stripped.split(":", 1)
        key, val = key.strip(), val.strip()

        if key == "pending_cprs" and not val:
            cprs = []
            i += 1
            current_cpr = None

            while i < len(lines):
                cline = lines[i]
                cs = cline.strip()
                ci = len(cline) - len(cline.lstrip())

                if ci <= base_indent and not cs.startswith("-"):
                    break

                if cs.startswith("- "):
                    rest = cs[2:].strip()
                    if ":" in rest and not (rest.startswith('"') or rest.startswith("'")):
                        if current_cpr is not None:
                            cprs.append(current_cpr)
                        k, v = rest.split(":", 1)
                        current_cpr = {k.strip(): _unquote(v.strip())}
                    else:
                        if current_cpr and "recommended" in current_cpr:
                            current_cpr["recommended"].append(_unquote(rest))
                elif ":" in cs and current_cpr is not None:
                    k, v = cs.split(":", 1)
                    k, v = k.strip(), v.strip()
                    if v:
                        current_cpr[k] = _unquote(v)
                    else:
                        current_cpr[k] = []

                i += 1

            if current_cpr is not None:
                cprs.append(current_cpr)
            result["pending_cprs"] = cprs
            continue
        else:
            result[key] = _unquote(val) if val else None
        i += 1

    return result


# ---------------------------------------------------------------------------
# Signal store
# ---------------------------------------------------------------------------

def load_signal_store(signals_dir):
    """Load all signals, dedup by ID (latest entry wins)."""
    entries = {}
    p = Path(signals_dir)
    if not p.exists():
        return entries
    for f in sorted(p.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
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


def classify_entries(entries):
    """Separate into active signals, working signals, warrants, etc."""
    active_signals = {}
    working_signals = {}
    warranted_signals = {}
    active_warrants = {}
    acknowledged_warrants = {}
    resolved = {}

    for eid, e in entries.items():
        status = e.get("status", "")
        etype = e.get("type", "")

        if status in ("resolved", "dismissed", "warranted"):
            resolved[eid] = e
        elif etype == "warrant":
            if status == "active":
                active_warrants[eid] = e
            elif status == "acknowledged":
                acknowledged_warrants[eid] = e
        elif etype == "signal":
            if status == "active":
                active_signals[eid] = e
            elif status == "working":
                working_signals[eid] = e
            elif status == "warranted":
                warranted_signals[eid] = e

    return {
        "active_signals": active_signals,
        "working_signals": working_signals,
        "warranted_signals": warranted_signals,
        "active_warrants": active_warrants,
        "acknowledged_warrants": acknowledged_warrants,
        "resolved": resolved,
    }


def detect_harmonic_triads(active_signals, window_hours=24):
    """PRIMITIVE BEACON + COGNITIVE LESSON + TENSION within window -> triad."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    primitive_beacons = []
    cognitive_lessons = []
    tensions = []

    for eid, sig in active_signals.items():
        band = sig.get("band", "")
        kind = sig.get("kind", "")

        created = sig.get("created_at", "")
        if created:
            try:
                ts = created.replace("Z", "+00:00") if created.endswith("Z") else created
                if datetime.fromisoformat(ts) < cutoff:
                    continue
            except (ValueError, TypeError):
                pass

        if band == "PRIMITIVE" and kind == "BEACON":
            primitive_beacons.append(eid)
        if band == "COGNITIVE" and kind == "LESSON":
            cognitive_lessons.append(eid)
        if kind == "TENSION":
            tensions.append(eid)

    triads = []
    if primitive_beacons and cognitive_lessons and tensions:
        triads.append({
            "primitive_beacon": primitive_beacons[0],
            "cognitive_lesson": cognitive_lessons[0],
            "tension": tensions[0],
        })
    return triads


# ---------------------------------------------------------------------------
# CPR inline scan
# ---------------------------------------------------------------------------

def count_pending_cprs_inline(project_dir):
    """Count pending CPR flags in CLAUDE.md files. Returns int."""
    count = 0
    skip = {"vendor", "node_modules", ".git", "audit-logs"}
    for md in Path(project_dir).rglob("CLAUDE.md"):
        if skip & set(md.parts):
            continue
        try:
            for line in md.read_text(encoding="utf-8").splitlines():
                if "agnostic-candidate" in line and "pending" in line:
                    count += 1
        except Exception:
            continue
    return count


# ---------------------------------------------------------------------------
# Queue-based CPR loading
# ---------------------------------------------------------------------------

QUEUE_ACTIVE_STATUSES = {
    "extracted", "tic_gated", "enrichment_needed",
    "enrichment_in_progress", "enrichment_eligible", "promotable",
}


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


def queue_to_cprs(queue_entries):
    """Convert queue entries to the CPR format expected by compile_proposals."""
    cprs = []
    for eid, entry in queue_entries.items():
        status = entry.get("status", "")
        if status not in QUEUE_ACTIVE_STATUSES:
            continue
        cprs.append({
            "source": entry.get("source", "unknown"),
            "lesson": entry.get("lesson", "unknown"),
            "recommended": entry.get("recommended_scopes", []),
            "queue_id": eid,
            "queue_status": status,
            "birth_tic": entry.get("birth_tic", 0),
            "band": entry.get("band", "COGNITIVE"),
            "subsystem": entry.get("subsystem", ""),
        })
    return cprs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_tic_counter(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {"count": 0, "last_tic": "unknown"}


# ---------------------------------------------------------------------------
# Maturity gates
# ---------------------------------------------------------------------------

DEFAULT_MATURITY_TICS = 3


def classify_cpr_readiness(cpr, current_tic_count):
    """Apply temporal maturity gate then epistemic enrichment gate.

    Returns (state, reason) where state is one of:
      tic_gated, enrichment_needed, enrichment_eligible, promotable
    """
    birth_tic = cpr.get("birth_tic", 0)
    maturity_tics = cpr.get("maturity_tics", DEFAULT_MATURITY_TICS)

    # --- Gate 1: Temporal maturity ---
    if birth_tic > 0 and (current_tic_count - birth_tic) < maturity_tics:
        remaining = maturity_tics - (current_tic_count - birth_tic)
        return "tic_gated", f"temporal maturity insufficient ({remaining} tics remaining)"

    # --- Gate 2: Epistemic enrichment ---
    queue_status = cpr.get("queue_status", "")
    enrichment = cpr.get("enrichment", [])
    has_evidence = len(enrichment) > 0 if isinstance(enrichment, list) else bool(enrichment)

    # If queue already marked as needing enrichment and no evidence yet
    if queue_status in ("enrichment_needed",) and not has_evidence:
        return "enrichment_needed", "enrichment evidence insufficient"

    # If queue marked as enrichment_eligible, evidence gathering is in progress
    if queue_status == "enrichment_eligible" and not has_evidence:
        return "enrichment_eligible", "enrichment gathering in progress, no evidence yet"

    # Both gates clear
    return "promotable", "both gates cleared"


def _band_counts(signals):
    c = {}
    for s in signals.values():
        b = s.get("band", "UNKNOWN")
        c[b] = c.get(b, 0) + 1
    return c


def _priority_counts(warrants):
    c = {}
    for w in warrants.values():
        p = f"P{w.get('priority', 0)}"
        c[p] = c.get(p, 0) + 1
    return c


def _loudest(signals):
    lid, lvol, lband, lkind = "none", 0, "", ""
    for eid, s in signals.items():
        v = s.get("volume", 0)
        if v > lvol:
            lid, lvol = eid, v
            lband, lkind = s.get("band", ""), s.get("kind", "")
    return lid, lvol, lband, lkind


def _fmt_counts(c):
    return ", ".join(f"{k}={v}" for k, v in sorted(c.items())) or "none"


# ---------------------------------------------------------------------------
# Proposal compilation
# ---------------------------------------------------------------------------

def compile_proposals(evaluate_data, classified, triads, tic_counter,
                      plan_path, inline_cpr_count):
    now = datetime.now(timezone.utc).isoformat()
    current_tic = tic_counter.get("count", 0)

    handoff_id = ""
    expected_cprs = 0
    cprs = []
    if evaluate_data:
        handoff_id = evaluate_data.get("handoff_id", "")
        expected_cprs = evaluate_data.get("pending_cprs_expected", 0)
        cprs = evaluate_data.get("pending_cprs") or []
    found_cprs = len(cprs)

    # Classify each CPR through maturity gates
    gated = []      # tic_gated
    enriching = []   # enrichment_needed or enrichment_eligible
    reviewable = []  # promotable

    for cpr in cprs:
        state, reason = classify_cpr_readiness(cpr, current_tic)
        cpr["_gate_state"] = state
        cpr["_gate_reason"] = reason
        if state == "tic_gated":
            gated.append(cpr)
        elif state in ("enrichment_needed", "enrichment_eligible"):
            enriching.append(cpr)
        else:
            reviewable.append(cpr)

    asig = classified["active_signals"]
    wsig = classified["working_signals"]
    aw = classified["active_warrants"]
    ackw = classified["acknowledged_warrants"]
    all_warrants = {**aw, **ackw}

    L = []

    L.append("# CGG Ripple Assessment")
    L.append("")
    L.append(f"- **Handoff ID**: {handoff_id or 'none'}")
    L.append(f"- **Assessed at**: {now}")
    L.append(f"- **Plan file**: {plan_path or 'none'}")
    L.append(f"- **Tic counter**: {current_tic} (last: {tic_counter.get('last_tic', 'unknown')})")
    L.append(f"- **Expected CPRs**: {expected_cprs}")
    L.append(f"- **Found CPRs**: {found_cprs}")
    L.append(f"- **Inline pending CPRs**: {inline_cpr_count}")
    L.append(f"- **Active signals**: {len(asig)} (+ {len(wsig)} working)")
    L.append(f"- **Active warrants**: {len(all_warrants)}")
    L.append(f"- **Harmonic triads**: {len(triads)}")
    L.append(f"- **Gate summary**: {len(reviewable)} reviewable, {len(gated)} tic-gated, {len(enriching)} enriching")

    if evaluate_data and expected_cprs != found_cprs:
        L.append("")
        L.append(f"**WARNING: INTEGRITY MISMATCH**: Expected {expected_cprs} CPRs, found {found_cprs}.")

    L.append("")
    L.append("---")
    L.append("")

    L.append("## Signal Assessment")
    L.append("")
    L.append("### Signal Health Overview")

    bc = _band_counts(asig)
    L.append(f"- Active signals: {len(asig)} (by band: {_fmt_counts(bc)})")
    wbc = _band_counts(wsig)
    L.append(f"- Working signals: {len(wsig)} (by band: {_fmt_counts(wbc)})")
    pc = _priority_counts(all_warrants)
    L.append(f"- Active warrants: {len(all_warrants)} (by priority: {_fmt_counts(pc)})")
    L.append(f"- Harmonic triads detected: {len(triads)}")

    lid, lvol, lband, lkind = _loudest(asig)
    L.append(f"- Loudest signal: {lid} (volume={lvol}, band={lband}, kind={lkind})")
    L.append("")

    if all_warrants:
        L.append("### Warrant Status")
        L.append("")
        for wid, w in all_warrants.items():
            p = w.get("payload", {})
            L.append(f"- **{wid}**: {p.get('summary', 'No summary')}")
            L.append(f"  - Band: {w.get('band','')} | Priority: P{w.get('priority',0)} | Scope: {w.get('scope','')} | Status: {w.get('status','')}")
            L.append(f"  - Minting condition: {w.get('minting_condition','')}")
            L.append(f"  - Source signals: {', '.join(w.get('source_signal_ids', []))}")
            L.append(f"  - Action required: {p.get('action_required', 'none')}")
            L.append("")

    if triads:
        L.append("### Harmonic Triad Alerts")
        L.append("")
        for i, t in enumerate(triads, 1):
            L.append(f"- **Triad {i}**: {t['primitive_beacon']} (PRIMITIVE/BEACON) + {t['cognitive_lesson']} (COGNITIVE/LESSON) + {t['tension']} (TENSION)")
            L.append("  - Recommendation: Immediate warrant minting + investigation")
        L.append("")

    L.append("---")
    L.append("")

    # --- Tic-gated CPRs (not ready: too young) ---
    if gated:
        L.append("## Tic-Gated CPRs (not ready — too young)")
        L.append("")
        for cpr in gated:
            lesson = cpr.get("lesson", "unknown")
            birth = cpr.get("birth_tic", 0)
            L.append(f"- **{lesson[:80]}**")
            L.append(f"  - Source: {cpr.get('source', 'unknown')}")
            L.append(f"  - Birth tic: {birth} | Current tic: {current_tic} | Required delta: {cpr.get('maturity_tics', DEFAULT_MATURITY_TICS)}")
            L.append(f"  - Reason: {cpr.get('_gate_reason', '')}")
            L.append("")
        L.append("---")
        L.append("")

    # --- Enrichment-pending CPRs (not ready: under-enriched) ---
    if enriching:
        L.append("## Enrichment-Pending CPRs (not ready — under-enriched)")
        L.append("")
        for cpr in enriching:
            lesson = cpr.get("lesson", "unknown")
            state = cpr.get("_gate_state", "")
            L.append(f"- **{lesson[:80]}**")
            L.append(f"  - Source: {cpr.get('source', 'unknown')}")
            L.append(f"  - State: {state}")
            L.append(f"  - Reason: {cpr.get('_gate_reason', '')}")
            enrichment = cpr.get("enrichment", [])
            if enrichment:
                L.append(f"  - Evidence gathered: {len(enrichment)} entries")
            L.append("")
        L.append("---")
        L.append("")

    # --- Reviewable CPRs (both gates cleared) ---
    if reviewable:
        for i, cpr in enumerate(reviewable, 1):
            source = cpr.get("source", "unknown")
            lesson = cpr.get("lesson", "unknown")
            recommended = cpr.get("recommended", [])

            L.append(f"## CPR {i}: {lesson}")
            L.append("")
            L.append(f"- **Source**: {source}")
            L.append(f"- **Lesson**: {lesson}")
            L.append(f"- **Recommended targets**: {', '.join(recommended) if recommended else 'none'}")
            L.append(f"- **Gate state**: promotable (both gates cleared)")
            L.append("")

            L.append("### Treaty Verdict")
            L.append("")
            for target in recommended:
                is_global = "~/.claude/CLAUDE.md" in target
                if is_global:
                    L.append(f"- **{target}** — GLOBAL scope")
                    L.append(f"  - **Verdict**: SKIP (confidence: 0.5)")
                    L.append(f"  - **Reasoning**: Global scope requires governance invariant: >=2 validation cycles + cross-actor validation. Cannot verify mechanically. Recommend site-level adoption first.")
                else:
                    L.append(f"- **{target}** — SITE scope")
                    L.append(f"  - **Verdict**: PROMOTE (confidence: 0.8)")
                    L.append(f"  - **Reasoning**: Site scope — standard promotion. Human review recommended.")
            L.append("")
            L.append("---")
            L.append("")
    elif not gated and not enriching:
        L.append("## CPR Review")
        L.append("")
        L.append("No pending CPRs in evaluate block.")
        L.append("")
        L.append("---")
        L.append("")

    L.append("## Summary")
    L.append("")
    L.append(f"- **Total CPRs**: {found_cprs} ({len(reviewable)} reviewable, {len(gated)} tic-gated, {len(enriching)} enriching)")
    L.append(f"- **Signals**: {len(asig)} active, {len(wsig)} working, {len(all_warrants)} warrants, {len(triads)} triads")

    if triads:
        focus = "Harmonic triad alert — immediate attention"
    elif all_warrants:
        focus = "Warrant triage first"
    elif reviewable:
        focus = "CPR review"
    elif gated or enriching:
        focus = "No reviewable CPRs — all holding (tic-gated or enriching)"
    else:
        focus = "Signal review only"
    L.append(f"- **Docket priority**: {focus}")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Deterministic ripple-assessor — structured-data-only proposal compiler"
    )
    parser.add_argument("--plan", help="Plan file path (with cgg-evaluate block)")
    parser.add_argument("--queue", help="CPR queue JSONL path (preferred over plan CPRs)")
    parser.add_argument("--signals-dir", default=None)
    parser.add_argument("--project-dir", "--project", default=None)
    parser.add_argument("--tic-counter", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    project_dir = args.project_dir or resolve_zone_root()
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)

    signals_dir = args.signals_dir or os.path.join(al_path, "signals")
    tic_path = args.tic_counter or os.path.expanduser("~/.claude/cgg-tic-counter.json")
    output_path = args.output or os.path.expanduser("~/.claude/grapple-proposals/latest.md")
    queue_path = args.queue or os.path.join(al_path, "cprs", "queue.jsonl")

    evaluate_data = None
    plan_path = args.plan
    if plan_path and os.path.isfile(plan_path):
        evaluate_data, _ = parse_evaluate_block(plan_path)

    queue_entries = load_queue(queue_path) if os.path.isfile(queue_path) else {}
    queue_cprs = queue_to_cprs(queue_entries) if queue_entries else []

    if queue_cprs:
        if evaluate_data is None:
            evaluate_data = {}
        evaluate_data["pending_cprs"] = queue_cprs
        evaluate_data["pending_cprs_expected"] = len(queue_cprs)
        evaluate_data.setdefault("handoff_id", "queue-driven")

    entries = load_signal_store(signals_dir)
    classified = classify_entries(entries)
    triads = detect_harmonic_triads(classified["active_signals"])
    tic_counter = load_tic_counter(tic_path)
    inline_cpr_count = count_pending_cprs_inline(project_dir)

    proposals = compile_proposals(
        evaluate_data, classified, triads, tic_counter,
        plan_path, inline_cpr_count,
    )

    checksum = hashlib.sha256(proposals.encode()).hexdigest()[:16]
    proposals += (
        f"\n\n---\n\n"
        f"_Truthiness checksum: `{checksum}`_\n"
        f"_Compiled by: cgg-runtime/scripts/ripple-assessor.py (deterministic, no LLM)_\n"
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    Path(output_path).write_text(proposals, encoding="utf-8")

    if not args.quiet:
        a = len(classified["active_signals"])
        w = len(classified["working_signals"])
        wr = len(classified["active_warrants"]) + len(classified["acknowledged_warrants"])
        c = len(evaluate_data.get("pending_cprs", [])) if evaluate_data else 0
        print(f"Proposals written to {output_path}")
        print(f"Checksum: {checksum}")
        print(f"Active: {a} signals, {w} working, {wr} warrants, {c} CPRs, {len(triads)} triads")

    return 0


if __name__ == "__main__":
    sys.exit(main())
