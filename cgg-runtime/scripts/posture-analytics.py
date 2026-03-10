#!/usr/bin/env python3
"""
Posture Analytics v0.2 — correlates posture declarations with session outcomes.

Three data layers:
  1. Claude Code native insights (session-meta + facets) — outcome layer
  2. CGG conformations (audit-logs/conformations/tic-*.json) — posture state layer
  3. CogPR queue (audit-logs/cprs/queue.jsonl) — learning outcome layer

Bridges session-meta to conformations via timestamp proximity.
Applies CGG-aware normalization to insights data.
Confidence-gated: main correlations use exact+high bridges only.

Output:
  audit-logs/posture/posture-analytics.raw.json  — full structured data
  audit-logs/posture/posture-analytics.summary.md — human-readable findings

Usage:
    python3 posture-analytics.py --project-dir /path/to/zone
    python3 posture-analytics.py --project-dir /path/to/zone --json
    python3 posture-analytics.py --help
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, audit_logs_path

# --- Constants ---

USAGE_DATA_DIR = os.path.expanduser("~/.claude/usage-data")
SESSION_META_DIR = os.path.join(USAGE_DATA_DIR, "session-meta")
FACETS_DIR = os.path.join(USAGE_DATA_DIR, "facets")

BRIDGE_TOLERANCE_MINUTES = 180  # max gap for any bridge

# Confidence band definitions (named, not just numeric)
CONFIDENCE_BANDS = {
    "exact": {"max_gap": 0, "label": "conformation inside session window"},
    "high": {"max_gap": 30, "label": "edge gap <= 30 min"},
    "medium": {"max_gap": 120, "label": "edge gap <= 120 min"},
    "low": {"max_gap": BRIDGE_TOLERANCE_MINUTES, "label": "edge gap > 120 min"},
}

# Bands eligible for main correlation tables
CORRELATION_ELIGIBLE_BANDS = {"exact", "high"}

# Minimum N for non-exploratory correlation claims
MIN_N_FOR_INFERENCE = 3

# Outcome ordering (higher = better)
OUTCOME_RANK = {
    "achieved": 3,
    "mostly_achieved": 2,
    "partially_achieved": 1,
    "not_achieved": 0,
}

# Helpfulness ordering
HELPFULNESS_RANK = {
    "essential": 3,
    "very_helpful": 2,
    "helpful": 1,
    "somewhat_helpful": 0,
    "not_helpful": -1,
}

# Posture verbs — used for verb-posture alignment check
DIRECT_VERBS = {"fix", "implement", "build", "generate", "run", "patch", "ship",
                "add", "create", "write", "deploy", "wire", "close", "push"}
META_VERBS = {"plan", "design", "analyze", "audit", "review", "explore",
              "investigate", "assess", "research", "map", "inspect", "check"}


def mean_safe(lst):
    """Mean of a list, returns 0 if empty."""
    return round(sum(lst) / len(lst), 2) if lst else 0


def load_json_safe(path):
    """Load JSON file, returning None on any error."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def load_jsonl_safe(path):
    """Load JSONL file, returning list of successfully parsed entries."""
    entries = []
    if not os.path.isfile(path):
        return entries
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def parse_iso(s):
    """Parse ISO timestamp string to datetime. Returns None on failure."""
    if not s or not isinstance(s, str):
        return None
    try:
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def classify_confidence_band(gap_minutes):
    """Classify a gap into a named confidence band."""
    if gap_minutes == 0:
        return "exact"
    elif gap_minutes <= 30:
        return "high"
    elif gap_minutes <= 120:
        return "medium"
    else:
        return "low"


# --- Data Loading ---

def load_session_data(project_path):
    """Load session-meta + facets for sessions matching project_path."""
    sessions = []
    if not os.path.isdir(SESSION_META_DIR):
        return sessions

    for fname in os.listdir(SESSION_META_DIR):
        if not fname.endswith(".json"):
            continue
        meta = load_json_safe(os.path.join(SESSION_META_DIR, fname))
        if meta is None:
            continue
        if not meta.get("project_path", "").rstrip("/").endswith(project_path.rstrip("/")):
            continue

        sid = meta.get("session_id", fname.replace(".json", ""))
        facets_path = os.path.join(FACETS_DIR, sid + ".json")
        facets = load_json_safe(facets_path) or {}

        session = {**meta, **facets, "session_id": sid}
        sessions.append(session)

    return sessions


def load_conformations(audit_dir):
    """Load all conformations from audit-logs/conformations/tic-*.json."""
    conf_dir = os.path.join(audit_dir, "conformations")
    conformations = []
    if not os.path.isdir(conf_dir):
        return conformations

    for fname in sorted(os.listdir(conf_dir)):
        if not fname.startswith("tic-") or not fname.endswith(".json"):
            continue
        data = load_json_safe(os.path.join(conf_dir, fname))
        if data is None:
            continue
        try:
            tic_num = int(fname.replace("tic-", "").replace(".json", ""))
        except ValueError:
            continue
        data["_tic_num"] = tic_num
        conformations.append(data)

    return sorted(conformations, key=lambda c: c["_tic_num"])


def load_cogprs(audit_dir):
    """Load CogPR queue entries."""
    queue_path = os.path.join(audit_dir, "cprs", "queue.jsonl")
    return load_jsonl_safe(queue_path)


# --- CGG Normalization ---

def classify_session(session):
    """Classify session as cadence_boundary or implementation."""
    first_prompt = session.get("first_prompt", "")
    is_cadence = "cgg-handoff" in first_prompt

    tags = set()
    if is_cadence:
        tags.add("cadence_boundary")
    else:
        tags.add("implementation")

    goal_cats = session.get("goal_categories", {})
    if goal_cats.get("implement_plan", 0) > 0 and is_cadence:
        tags.add("cadence_plan_pickup")

    return {
        "is_cadence": is_cadence,
        "tags": list(tags),
        "raw_session_type": session.get("session_type", "unknown"),
    }


def normalize_friction(session, classification):
    """Apply CGG-aware friction normalization."""
    raw_friction = session.get("friction_counts", {})
    normalized = dict(raw_friction)
    notes = []

    if classification["is_cadence"]:
        rejected = raw_friction.get("user_rejected_action", 0)
        if rejected > 0:
            normalized["user_rejected_action"] = 0
            normalized["collaborative_refinement"] = rejected
            notes.append(f"Reclassified {rejected} user_rejected_action -> collaborative_refinement (cadence)")

    return {"normalized": normalized, "raw": raw_friction, "notes": notes}


def normalize_tool_counts(session, classification):
    """Apply CGG-aware tool count normalization."""
    raw = session.get("tool_counts", {})
    governance_overhead = {}
    implementation_tools = dict(raw)

    if classification["is_cadence"]:
        exit_count = raw.get("ExitPlanMode", 0)
        if exit_count > 1:
            governance_overhead["ExitPlanMode_retries"] = exit_count - 1
            implementation_tools["ExitPlanMode"] = 1

        task_updates = raw.get("TaskUpdate", 0)
        if task_updates > 0:
            governance_overhead["TaskUpdate_governance"] = task_updates
            implementation_tools.pop("TaskUpdate", None)

        enter_count = raw.get("EnterPlanMode", 0)
        if enter_count > 0:
            governance_overhead["EnterPlanMode_cadence"] = enter_count
            implementation_tools.pop("EnterPlanMode", None)

    return {
        "implementation": implementation_tools,
        "governance_overhead": governance_overhead,
    }


# --- Bridge ---

def bridge_sessions_to_conformations(sessions, conformations):
    """Bridge sessions to conformations via timestamp proximity.

    Returns list of bridge entries with named confidence bands.
    """
    bridges = []

    for conf in conformations:
        conf_time = parse_iso(conf.get("snapshot_at") or conf.get("tic"))
        if conf_time is None:
            continue

        tic_num = conf["_tic_num"]
        best_match = None
        best_gap = None

        for sess in sessions:
            sess_start = parse_iso(sess.get("start_time"))
            if sess_start is None:
                continue

            duration = sess.get("duration_minutes", 0)
            sess_end = sess_start + timedelta(minutes=duration) if duration else sess_start

            gap_to_start = abs((conf_time - sess_start).total_seconds()) / 60
            gap_to_end = abs((conf_time - sess_end).total_seconds()) / 60
            gap = min(gap_to_start, gap_to_end)

            # Perfect containment
            if sess_start <= conf_time <= sess_end:
                gap = 0

            if gap <= BRIDGE_TOLERANCE_MINUTES:
                if best_gap is None or gap < best_gap:
                    best_gap = gap
                    best_match = sess

        if best_match is not None:
            band = classify_confidence_band(best_gap)
            bridges.append({
                "tic": tic_num,
                "session_id": best_match["session_id"],
                "posture": conf.get("posture"),
                "gap_minutes": round(best_gap, 1),
                "confidence_band": band,
                "conformation_time": conf.get("snapshot_at") or conf.get("tic"),
                "session_start": best_match.get("start_time"),
                "session_classification": best_match.get("_classification", {}).get("tags", []),
            })

    return bridges


def filter_bridges(bridges, eligible_bands=None):
    """Filter bridges to eligible confidence bands."""
    if eligible_bands is None:
        eligible_bands = CORRELATION_ELIGIBLE_BANDS
    return [b for b in bridges if b["confidence_band"] in eligible_bands]


# --- Analysis Functions ---

def posture_distribution(conformations, cogprs):
    """Compute posture distribution across conformations and CogPRs."""
    conf_postures = Counter()
    conf_missing = 0
    for c in conformations:
        p = c.get("posture")
        if p:
            conf_postures[p] += 1
        else:
            conf_missing += 1

    cpr_postures = Counter()
    cpr_missing = 0
    for cpr in cogprs:
        p = cpr.get("posture")
        if p:
            cpr_postures[p] += 1
        else:
            cpr_missing += 1

    return {
        "conformations": {
            "distribution": dict(conf_postures),
            "total": len(conformations),
            "with_posture": sum(conf_postures.values()),
            "missing": conf_missing,
            "coverage_pct": round(sum(conf_postures.values()) / max(len(conformations), 1) * 100, 1),
        },
        "cogprs": {
            "distribution": dict(cpr_postures),
            "total": len(cogprs),
            "with_posture": sum(cpr_postures.values()),
            "missing": cpr_missing,
            "coverage_pct": round(sum(cpr_postures.values()) / max(len(cogprs), 1) * 100, 1),
        },
    }


def posture_outcome_correlation(bridges, sessions_by_id):
    """Correlate posture with session outcomes using NORMALIZED friction.

    Only uses exact+high confidence bridges.
    """
    eligible = filter_bridges(bridges)

    posture_outcomes = defaultdict(list)
    posture_helpfulness = defaultdict(list)
    posture_friction_totals = defaultdict(list)

    for bridge in eligible:
        posture = bridge.get("posture")
        if not posture:
            continue
        sess = sessions_by_id.get(bridge["session_id"])
        if not sess:
            continue

        outcome = sess.get("outcome", "")
        if outcome in OUTCOME_RANK:
            posture_outcomes[posture].append(OUTCOME_RANK[outcome])

        helpfulness = sess.get("claude_helpfulness", "")
        if helpfulness in HELPFULNESS_RANK:
            posture_helpfulness[posture].append(HELPFULNESS_RANK[helpfulness])

        # Use NORMALIZED friction, not raw
        norm = sess.get("_normalized_friction", {})
        friction = norm.get("normalized", sess.get("friction_counts", {}))
        total_friction = sum(v for v in friction.values() if isinstance(v, (int, float)))
        posture_friction_totals[posture].append(total_friction)

    result = {}
    all_postures = set(list(posture_outcomes.keys()) + list(posture_helpfulness.keys()))
    for posture in all_postures:
        outcomes = posture_outcomes.get(posture, [])
        helps = posture_helpfulness.get(posture, [])
        frictions = posture_friction_totals.get(posture, [])
        n = len(outcomes)

        result[posture] = {
            "n": n,
            "exploratory": n < MIN_N_FOR_INFERENCE,
            "outcome_mean": mean_safe(outcomes),
            "helpfulness_mean": mean_safe(helps),
            "friction_mean_normalized": mean_safe(frictions),
            "outcomes_raw": [
                {v: k for k, v in OUTCOME_RANK.items()}.get(o, "unknown")
                for o in outcomes
            ],
            "bridge_bands_used": "exact+high",
        }

    return result


def posture_productivity_proxy(bridges, sessions_by_id):
    """Correlate posture with productivity proxies. Exact+high bridges only."""
    eligible = filter_bridges(bridges)

    posture_data = defaultdict(lambda: {
        "lines_added": [], "lines_removed": [], "commits": [],
        "duration": [], "tool_errors": [], "files_modified": [],
    })

    for bridge in eligible:
        posture = bridge.get("posture")
        if not posture:
            continue
        sess = sessions_by_id.get(bridge["session_id"])
        if not sess:
            continue

        posture_data[posture]["lines_added"].append(sess.get("lines_added", 0))
        posture_data[posture]["lines_removed"].append(sess.get("lines_removed", 0))
        posture_data[posture]["commits"].append(sess.get("git_commits", 0))
        posture_data[posture]["duration"].append(sess.get("duration_minutes", 0))
        posture_data[posture]["tool_errors"].append(sess.get("tool_errors", 0))
        posture_data[posture]["files_modified"].append(sess.get("files_modified", 0))

    result = {}
    for posture, data in posture_data.items():
        n = len(data["lines_added"])
        result[posture] = {
            "n": n,
            "exploratory": n < MIN_N_FOR_INFERENCE,
            "lines_added_mean": mean_safe(data["lines_added"]),
            "lines_removed_mean": mean_safe(data["lines_removed"]),
            "commits_mean": mean_safe(data["commits"]),
            "duration_mean": mean_safe(data["duration"]),
            "tool_errors_mean": mean_safe(data["tool_errors"]),
            "files_modified_mean": mean_safe(data["files_modified"]),
            "bridge_bands_used": "exact+high",
        }

    return result


def posture_outcome_correlation_low_confidence(bridges, sessions_by_id):
    """Same correlation but for medium+low confidence bridges only. Reported separately."""
    low_bridges = [b for b in bridges if b["confidence_band"] in {"medium", "low"}]

    posture_outcomes = defaultdict(list)
    posture_friction = defaultdict(list)

    for bridge in low_bridges:
        posture = bridge.get("posture")
        if not posture:
            continue
        sess = sessions_by_id.get(bridge["session_id"])
        if not sess:
            continue

        outcome = sess.get("outcome", "")
        if outcome in OUTCOME_RANK:
            posture_outcomes[posture].append(OUTCOME_RANK[outcome])

        norm = sess.get("_normalized_friction", {})
        friction = norm.get("normalized", sess.get("friction_counts", {}))
        total = sum(v for v in friction.values() if isinstance(v, (int, float)))
        posture_friction[posture].append(total)

    result = {}
    for posture in set(list(posture_outcomes.keys()) + list(posture_friction.keys())):
        outcomes = posture_outcomes.get(posture, [])
        frictions = posture_friction.get(posture, [])
        result[posture] = {
            "n": len(outcomes),
            "exploratory": True,  # Always exploratory — low confidence
            "outcome_mean": mean_safe(outcomes),
            "friction_mean_normalized": mean_safe(frictions),
            "bridge_bands_used": "medium+low",
        }

    return result


def toggle_frequency_analysis(conformations):
    """Analyze posture toggle frequency across conformations.

    A toggle is detected when a posture string contains '→' (e.g. "ENG/DIRECT → ENG/META").
    """
    total_with_posture = 0
    toggles = 0
    toggle_patterns = Counter()

    for conf in conformations:
        posture = conf.get("posture")
        if not posture:
            continue
        total_with_posture += 1
        if "→" in posture or "->" in posture:
            toggles += 1
            toggle_patterns[posture] += 1

    return {
        "total_with_posture": total_with_posture,
        "toggle_count": toggles,
        "toggle_rate_pct": round(toggles / max(total_with_posture, 1) * 100, 1),
        "toggle_patterns": dict(toggle_patterns),
        "note": "Toggles detected by presence of '→' in posture string. "
                "Actual mid-session toggles may be higher if not captured in conformation.",
    }


def verb_posture_alignment(bridges, sessions_by_id):
    """Check if the verbs in first_prompt align with declared posture.

    DIRECT posture should correlate with DIRECT_VERBS.
    META posture should correlate with META_VERBS.
    """
    results = []

    for bridge in bridges:
        posture = bridge.get("posture")
        if not posture:
            continue
        sess = sessions_by_id.get(bridge["session_id"])
        if not sess:
            continue

        first_prompt = sess.get("first_prompt", "")
        # Extract first ~200 chars for verb detection
        prompt_start = first_prompt[:200].lower()
        words = set(re.findall(r'\b[a-z]+\b', prompt_start))

        direct_hits = words & DIRECT_VERBS
        meta_hits = words & META_VERBS

        # Determine declared axis
        declared_axis = None
        if "DIRECT" in posture:
            declared_axis = "DIRECT"
        elif "META" in posture:
            declared_axis = "META"

        # Check alignment
        if declared_axis == "DIRECT":
            aligned = len(direct_hits) >= len(meta_hits)
        elif declared_axis == "META":
            aligned = len(meta_hits) >= len(direct_hits)
        else:
            aligned = None  # Can't assess

        results.append({
            "tic": bridge["tic"],
            "posture": posture,
            "declared_axis": declared_axis,
            "direct_verbs_found": sorted(direct_hits),
            "meta_verbs_found": sorted(meta_hits),
            "aligned": aligned,
            "confidence_band": bridge["confidence_band"],
        })

    aligned_count = sum(1 for r in results if r["aligned"] is True)
    misaligned_count = sum(1 for r in results if r["aligned"] is False)
    unassessable = sum(1 for r in results if r["aligned"] is None)

    return {
        "total_assessed": len(results),
        "aligned": aligned_count,
        "misaligned": misaligned_count,
        "unassessable": unassessable,
        "alignment_rate_pct": round(aligned_count / max(aligned_count + misaligned_count, 1) * 100, 1),
        "details": results,
        "note": "Verb extraction from first ~200 chars of first_prompt. "
                "Rough heuristic — 'implement the plan' in a cadence handoff is a false positive for DIRECT.",
    }


def cogpr_posture_analysis(cogprs):
    """Analyze CogPR posture distribution and downstream status."""
    posture_status = defaultdict(lambda: Counter())
    posture_band = defaultdict(lambda: Counter())

    for cpr in cogprs:
        posture = cpr.get("posture", "untagged")
        status = cpr.get("status", "unknown")
        band = cpr.get("band", "unknown")

        posture_status[posture][status] += 1
        posture_band[posture][band] += 1

    return {
        posture: {
            "status_distribution": dict(posture_status[posture]),
            "band_distribution": dict(posture_band[posture]),
            "total": sum(posture_status[posture].values()),
        }
        for posture in set(list(posture_status.keys()))
    }


def session_classification_summary(sessions):
    """Summarize session classifications."""
    cadence = 0
    implementation = 0
    for sess in sessions:
        cls = classify_session(sess)
        if cls["is_cadence"]:
            cadence += 1
        else:
            implementation += 1

    return {
        "total_sessions": len(sessions),
        "cadence_sessions": cadence,
        "implementation_sessions": implementation,
        "cadence_pct": round(cadence / max(len(sessions), 1) * 100, 1),
    }


def missingness_report(conformations, cogprs, sessions, bridges):
    """Report on data completeness across all three layers."""
    conf_with_posture = sum(1 for c in conformations if c.get("posture"))
    cpr_with_posture = sum(1 for c in cogprs if c.get("posture"))
    sessions_bridged = len(set(b["session_id"] for b in bridges))

    # Stratified missingness
    conf_missing_tics = [c["_tic_num"] for c in conformations if not c.get("posture")]
    conf_present_tics = [c["_tic_num"] for c in conformations if c.get("posture")]

    # By session classification
    bridged_by_class = defaultdict(int)
    for b in bridges:
        for tag in b.get("session_classification", []):
            bridged_by_class[tag] += 1

    # By confidence band
    band_counts = Counter(b["confidence_band"] for b in bridges)

    return {
        "conformations": {
            "total": len(conformations),
            "with_posture": conf_with_posture,
            "without_posture": len(conformations) - conf_with_posture,
            "coverage_pct": round(conf_with_posture / max(len(conformations), 1) * 100, 1),
            "missing_at_tics": conf_missing_tics,
            "present_at_tics": conf_present_tics,
        },
        "cogprs": {
            "total": len(cogprs),
            "with_posture": cpr_with_posture,
            "without_posture": len(cogprs) - cpr_with_posture,
            "coverage_pct": round(cpr_with_posture / max(len(cogprs), 1) * 100, 1),
        },
        "session_bridge": {
            "total_sessions": len(sessions),
            "bridged": sessions_bridged,
            "unbridged": len(sessions) - sessions_bridged,
            "bridge_rate_pct": round(sessions_bridged / max(len(sessions), 1) * 100, 1),
            "bridged_by_classification": dict(bridged_by_class),
        },
        "bridges_by_band": {
            "exact": band_counts.get("exact", 0),
            "high": band_counts.get("high", 0),
            "medium": band_counts.get("medium", 0),
            "low": band_counts.get("low", 0),
            "total": len(bridges),
            "correlation_eligible": band_counts.get("exact", 0) + band_counts.get("high", 0),
        },
    }


# --- Output ---

def _exploratory_label(data):
    """Return ' [EXPLORATORY]' if n < MIN_N_FOR_INFERENCE."""
    if data.get("exploratory", False):
        return " **[EXPLORATORY n<3]**"
    return ""


def generate_summary_md(report):
    """Generate human-readable markdown summary from report."""
    L = []  # lines accumulator
    L.append("# Posture Analytics Report (v0.2)")
    L.append("")
    L.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    L.append(f"Zone: {report['metadata']['zone_root']}")
    L.append(f"Correlation gate: **exact+high confidence bridges only**")
    L.append(f"Friction source: **normalized** (CGG-aware)")
    L.append("")

    # =========================================================
    # SECTION A: STRUCTURAL FINDINGS
    # =========================================================
    L.append("---")
    L.append("")
    L.append("# A. Structural Findings")
    L.append("")
    L.append("*Coverage, bridgeability, cadence distortion — measured properties of the data itself.*")
    L.append("")

    # --- Session Classification ---
    sc = report["session_classification"]
    L.append("## A1. Session Classification (CGG Normalization)")
    L.append("")
    L.append(f"- **Total canonical sessions**: {sc['total_sessions']}")
    L.append(f"- **Cadence boundary sessions**: {sc['cadence_sessions']} ({sc['cadence_pct']}%)")
    L.append(f"- **Implementation sessions**: {sc['implementation_sessions']}")
    L.append("")
    L.append("> Cadence sessions use plan mode for handoff, not implementation planning.")
    L.append("> `user_rejected_action` in cadence sessions reclassified as `collaborative_refinement`.")
    L.append("")

    # --- Posture Distribution ---
    pd = report["posture_distribution"]
    L.append("## A2. Posture Distribution")
    L.append("")
    L.append("### Conformations")
    L.append(f"Coverage: {pd['conformations']['with_posture']}/{pd['conformations']['total']} ({pd['conformations']['coverage_pct']}%)")
    L.append("")
    if pd["conformations"]["distribution"]:
        L.append("| Posture | Count |")
        L.append("|---------|-------|")
        for p, c in sorted(pd["conformations"]["distribution"].items(), key=lambda x: -x[1]):
            L.append(f"| {p} | {c} |")
    else:
        L.append("*No posture data in conformations*")
    L.append("")

    L.append("### CogPRs")
    L.append(f"Coverage: {pd['cogprs']['with_posture']}/{pd['cogprs']['total']} ({pd['cogprs']['coverage_pct']}%)")
    L.append("")
    if pd["cogprs"]["distribution"]:
        L.append("| Posture | Count |")
        L.append("|---------|-------|")
        for p, c in sorted(pd["cogprs"]["distribution"].items(), key=lambda x: -x[1]):
            L.append(f"| {p} | {c} |")
    else:
        L.append("*No posture data in CogPRs*")
    L.append("")

    # --- Missingness ---
    mr = report["missingness"]
    L.append("## A3. Missingness Report")
    L.append("")
    L.append(f"- Conformations with posture: {mr['conformations']['with_posture']}/{mr['conformations']['total']} ({mr['conformations']['coverage_pct']}%)")
    if mr["conformations"]["missing_at_tics"]:
        L.append(f"  - Missing at tics: {', '.join(str(t) for t in sorted(mr['conformations']['missing_at_tics']))}")
    if mr["conformations"]["present_at_tics"]:
        L.append(f"  - Present at tics: {', '.join(str(t) for t in sorted(mr['conformations']['present_at_tics']))}")
    L.append(f"- CogPRs with posture: {mr['cogprs']['with_posture']}/{mr['cogprs']['total']} ({mr['cogprs']['coverage_pct']}%)")
    L.append(f"- Sessions bridged: {mr['session_bridge']['bridged']}/{mr['session_bridge']['total_sessions']} ({mr['session_bridge']['bridge_rate_pct']}%)")
    if mr["session_bridge"]["bridged_by_classification"]:
        for cls, n in sorted(mr["session_bridge"]["bridged_by_classification"].items()):
            L.append(f"  - {cls}: {n} bridged")
    L.append("")

    # --- Bridge Confidence ---
    bb = mr["bridges_by_band"]
    L.append("## A4. Bridge Confidence Report")
    L.append("")
    L.append(f"| Band | Count | Eligible for correlation |")
    L.append(f"|------|-------|------------------------|")
    L.append(f"| exact | {bb['exact']} | YES |")
    L.append(f"| high | {bb['high']} | YES |")
    L.append(f"| medium | {bb['medium']} | no (reported separately) |")
    L.append(f"| low | {bb['low']} | no (reported separately) |")
    L.append(f"| **total** | **{bb['total']}** | **{bb['correlation_eligible']} eligible** |")
    L.append("")

    if report.get("bridge_details"):
        L.append("### Bridge Detail")
        L.append("")
        L.append("| Tic | Session | Posture | Gap(min) | Band |")
        L.append("|-----|---------|---------|----------|------|")
        for b in report["bridge_details"]:
            sid_short = b["session_id"][:8]
            L.append(f"| {b['tic']} | {sid_short}... | {b.get('posture') or 'none'} | {b['gap_minutes']} | {b['confidence_band']} |")
    L.append("")

    # --- Toggle Frequency ---
    tf = report["toggle_frequency"]
    L.append("## A5. Toggle Frequency Analysis")
    L.append("")
    L.append(f"- Conformations with posture: {tf['total_with_posture']}")
    L.append(f"- Toggles detected: {tf['toggle_count']} ({tf['toggle_rate_pct']}%)")
    if tf["toggle_patterns"]:
        L.append(f"- Patterns: {', '.join(f'{k} ({v}x)' for k, v in tf['toggle_patterns'].items())}")
    L.append(f"- {tf['note']}")
    L.append("")

    # =========================================================
    # SECTION B: BEHAVIORAL FINDINGS
    # =========================================================
    L.append("---")
    L.append("")
    L.append("# B. Behavioral Findings")
    L.append("")
    L.append("*Posture/outcome, posture/friction, posture/productivity — requires bridge joins.*")
    L.append(f"*Using exact+high bridges only ({bb['correlation_eligible']} eligible). Normalized friction.*")
    L.append("")

    # --- Posture/Outcome ---
    poc = report["posture_outcome_correlation"]
    L.append("## B1. Posture / Outcome Correlation (exact+high only)")
    L.append("")
    if poc:
        L.append("| Posture | N | Outcome | Helpfulness | Friction (norm) | Status |")
        L.append("|---------|---|---------|-------------|-----------------|--------|")
        for p, data in sorted(poc.items()):
            status = _exploratory_label(data)
            L.append(
                f"| {p} | {data['n']} | {data['outcome_mean']}/3 "
                f"| {data['helpfulness_mean']}/3 | {data['friction_mean_normalized']}"
                f" | {status or 'sufficient'} |"
            )
        L.append("")
        L.append("*Outcome: 0=not_achieved, 1=partial, 2=mostly, 3=achieved*")
        L.append("*Helpfulness: -1=not, 0=somewhat, 1=helpful, 2=very, 3=essential*")
        L.append("*Friction: CGG-normalized (cadence rejections reclassified)*")
    else:
        L.append("*No exact+high bridges with posture — cannot compute behavioral correlation*")
    L.append("")

    # --- Posture/Productivity ---
    pp = report["posture_productivity"]
    L.append("## B2. Posture / Productivity Proxy (exact+high only)")
    L.append("")
    if pp:
        L.append("| Posture | N | Lines+/- | Commits | Duration | Errors | Files | Status |")
        L.append("|---------|---|----------|---------|----------|--------|-------|--------|")
        for p, data in sorted(pp.items()):
            status = _exploratory_label(data)
            L.append(
                f"| {p} | {data['n']} | +{data['lines_added_mean']}/-{data['lines_removed_mean']} "
                f"| {data['commits_mean']} | {data['duration_mean']}m "
                f"| {data['tool_errors_mean']} | {data['files_modified_mean']}"
                f" | {status or 'sufficient'} |"
            )
    else:
        L.append("*No exact+high bridges with posture — cannot compute productivity proxy*")
    L.append("")

    # --- Verb-Posture Alignment ---
    vpa = report["verb_posture_alignment"]
    L.append("## B3. Verb-Posture Alignment")
    L.append("")
    L.append(f"- Assessed: {vpa['total_assessed']}")
    L.append(f"- Aligned: {vpa['aligned']} ({vpa['alignment_rate_pct']}%)")
    L.append(f"- Misaligned: {vpa['misaligned']}")
    L.append(f"- Unassessable: {vpa['unassessable']}")
    L.append(f"- {vpa['note']}")
    L.append("")

    # --- Low-confidence correlation (separate) ---
    lc = report.get("low_confidence_correlation", {})
    if lc:
        L.append("## B4. Low-Confidence Correlation (medium+low bridges, exploratory only)")
        L.append("")
        L.append("| Posture | N | Outcome | Friction (norm) | Bands |")
        L.append("|---------|---|---------|-----------------|-------|")
        for p, data in sorted(lc.items()):
            L.append(
                f"| {p} | {data['n']} | {data['outcome_mean']}/3 "
                f"| {data['friction_mean_normalized']} | {data['bridge_bands_used']} |"
            )
        L.append("")
        L.append("*All entries are exploratory — low-confidence bridge joins.*")
        L.append("")

    # --- CogPR Posture Analysis ---
    cpa = report["cogpr_posture_analysis"]
    L.append("## B5. CogPR Posture Analysis")
    L.append("")
    if cpa:
        for posture, data in sorted(cpa.items()):
            L.append(f"### {posture} (n={data['total']})")
            L.append(f"- Status: {', '.join(f'{k}={v}' for k, v in sorted(data['status_distribution'].items()))}")
            L.append(f"- Band: {', '.join(f'{k}={v}' for k, v in sorted(data['band_distribution'].items()))}")
            L.append("")
    else:
        L.append("*No CogPR posture data*")
    L.append("")

    # =========================================================
    # SECTION C: PROTOCOL TWEAK CANDIDATES
    # =========================================================
    L.append("---")
    L.append("")
    L.append("# C. Protocol Tweak Candidates")
    L.append("")
    L.append("*Recommendations separated from measured findings above.*")
    L.append("")

    tweaks = report.get("protocol_tweaks", [])
    if tweaks:
        for i, tweak in enumerate(tweaks, 1):
            L.append(f"{i}. **{tweak['title']}** — {tweak['rationale']}")
            L.append(f"   - Type: {tweak.get('finding_type', 'unknown')}")
            if tweak.get("confidence"):
                L.append(f"   - Confidence: {tweak['confidence']}")
            L.append("")
    else:
        L.append("*No protocol tweaks recommended at current data volume.*")
    L.append("")

    return "\n".join(L)


def derive_protocol_tweaks(report):
    """Derive protocol tweak candidates from measured data."""
    tweaks = []

    # Structural: posture coverage
    conf_coverage = report["posture_distribution"]["conformations"]["coverage_pct"]
    if conf_coverage < 50:
        tweaks.append({
            "title": "Make posture mandatory in conformations",
            "rationale": f"Only {conf_coverage}% of conformations have posture. Analytics blocked by missingness.",
            "confidence": "HIGH — structural gap, not statistical inference",
            "finding_type": "structural",
        })

    # Structural: cadence proportion
    sc = report["session_classification"]
    if sc["cadence_pct"] > 60:
        tweaks.append({
            "title": "Normalize cadence sessions in insights pipeline",
            "rationale": f"{sc['cadence_pct']}% of canonical sessions are cadence boundaries. "
                         "Native analytics distorted by governance mechanics.",
            "confidence": "HIGH — measured, not inferred",
            "finding_type": "structural",
        })

    # Structural: bridge rate
    bridge_rate = report["missingness"]["session_bridge"]["bridge_rate_pct"]
    if bridge_rate < 80:
        tweaks.append({
            "title": "Embed session_id in conformations",
            "rationale": f"Bridge rate is {bridge_rate}% using timestamp proximity. "
                         "Direct session_id linkage would make correlation exact.",
            "confidence": "MEDIUM — depends on cadence hook having access to session_id",
            "finding_type": "structural",
        })

    # Behavioral: posture-outcome variance (only if sufficient N)
    poc = report["posture_outcome_correlation"]
    sufficient = {p: d for p, d in poc.items() if not d.get("exploratory", True)}
    if len(sufficient) >= 2:
        means = [d["outcome_mean"] for d in sufficient.values()]
        if max(means) - min(means) > 0.5:
            best = max(sufficient.items(), key=lambda x: x[1]["outcome_mean"])
            tweaks.append({
                "title": f"Investigate {best[0]} posture advantage",
                "rationale": f"{best[0]} shows outcome mean {best[1]['outcome_mean']}/3 "
                             f"vs range [{min(means)}, {max(means)}]. Sufficient N.",
                "confidence": "MEDIUM — sample still small but meets minimum threshold",
                "finding_type": "behavioral",
            })

    return tweaks


# --- Main ---

def run(project_dir, json_only=False):
    zone_root = resolve_zone_root(project_dir)
    audit_dir = audit_logs_path(zone_root)
    project_name = os.path.basename(zone_root)

    # Load data
    sessions = load_session_data(zone_root)
    conformations = load_conformations(audit_dir)
    cogprs = load_cogprs(audit_dir)

    # Index sessions by ID
    sessions_by_id = {s["session_id"]: s for s in sessions}

    # Classify and normalize all sessions
    for sess in sessions:
        sess["_classification"] = classify_session(sess)
        sess["_normalized_friction"] = normalize_friction(sess, sess["_classification"])
        sess["_normalized_tools"] = normalize_tool_counts(sess, sess["_classification"])

    # Bridge
    bridges = bridge_sessions_to_conformations(sessions, conformations)

    # Analysis — main correlations use exact+high only (via filter inside each fn)
    report = {
        "metadata": {
            "zone_root": zone_root,
            "project_name": project_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": "0.2",
            "correlation_gate": "exact+high confidence bridges only",
            "friction_source": "CGG-normalized",
            "min_n_for_inference": MIN_N_FOR_INFERENCE,
            "data_sources": {
                "sessions": len(sessions),
                "conformations": len(conformations),
                "cogprs": len(cogprs),
                "bridges_total": len(bridges),
                "bridges_correlation_eligible": len(filter_bridges(bridges)),
            },
        },
        "session_classification": session_classification_summary(sessions),
        "posture_distribution": posture_distribution(conformations, cogprs),
        "posture_outcome_correlation": posture_outcome_correlation(bridges, sessions_by_id),
        "posture_productivity": posture_productivity_proxy(bridges, sessions_by_id),
        "low_confidence_correlation": posture_outcome_correlation_low_confidence(bridges, sessions_by_id),
        "toggle_frequency": toggle_frequency_analysis(conformations),
        "verb_posture_alignment": verb_posture_alignment(bridges, sessions_by_id),
        "cogpr_posture_analysis": cogpr_posture_analysis(cogprs),
        "missingness": missingness_report(conformations, cogprs, sessions, bridges),
        "bridge_details": bridges,
        "session_details": [
            {
                "session_id": s["session_id"],
                "start_time": s.get("start_time"),
                "duration_minutes": s.get("duration_minutes"),
                "outcome": s.get("outcome"),
                "helpfulness": s.get("claude_helpfulness"),
                "friction_raw": s.get("friction_counts", {}),
                "friction_normalized": s["_normalized_friction"]["normalized"],
                "normalization_notes": s["_normalized_friction"]["notes"],
                "classification": s["_classification"],
                "tool_errors": s.get("tool_errors", 0),
                "lines_added": s.get("lines_added", 0),
                "lines_removed": s.get("lines_removed", 0),
                "git_commits": s.get("git_commits", 0),
                "files_modified": s.get("files_modified", 0),
            }
            for s in sessions
        ],
    }

    # Derive protocol tweaks
    report["protocol_tweaks"] = derive_protocol_tweaks(report)

    # Write outputs
    output_dir = os.path.join(audit_dir, "posture")
    os.makedirs(output_dir, exist_ok=True)

    raw_path = os.path.join(output_dir, "posture-analytics.raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    summary_md = generate_summary_md(report)
    summary_path = os.path.join(output_dir, "posture-analytics.summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_md)

    if json_only:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(summary_md)
        print(f"\n--- Written to ---")
        print(f"  Raw:     {raw_path}")
        print(f"  Summary: {summary_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Posture Analytics v0.2 — correlate posture with session outcomes")
    parser.add_argument("--project-dir", default=None, help="Path to project/zone root")
    parser.add_argument("--json", action="store_true", help="Output raw JSON only")
    args = parser.parse_args()

    run(args.project_dir, json_only=args.json)


if __name__ == "__main__":
    main()
