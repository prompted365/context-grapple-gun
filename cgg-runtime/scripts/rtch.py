#!/usr/bin/env python3
"""
rtch.py — Runtime Tactical Context Hydration (RTCH) runner.

Productizes the eight-stage discovery-and-bounded-hydration discipline that the
/tactical-hydration skill body specifies. Phase 2-7 deliverable per
audit-logs/governance/runtime-tactical-context-hydration-binder.md.

Stages:
  1. Intake               (CLI args + optional --intake JSON file)
  2. Zone orientation     (zone_root walk-up, rung chain, obvious truth files)
  3. Shape scout          (low-cost filesystem-shape scans)
  4. Candidate basket     (origin/use taxonomy + pairing-rule enforcement)
  5. Probe plan           (typed probe records, fanout-bounded)
  6. Hydration            (bounded chunk reads with line-range provenance)
  7. Evidence packet      (typed YAML emission; mandatory unresolved_questions)
  8. Packaging handoff    (optional --handoff-to-consolidate)

CLI:
  rtch.py --goal "<sentence>" --profile <p> --fanout <level> --risk <level> \\
          --output-kind <kind> --enough "<halting condition>" \\
          [--seed <term>]... [--known-target <path>] [--persist] \\
          [--handoff-to-consolidate]
  rtch.py --intake <intake.json>
  rtch.py --validate-example <10.1|10.2|10.3|10.4|10.5>

Exit codes: 0=success, 1=intake error, 2=zone error, 3=probe error, 4=packet error.

Hard holds (per binder §12 — enforced at runtime):
  - read-only by default (no source mutation)
  - no full-file reads on growing files (>200 lines requires bounded chunks)
  - skipped/truncated surfaces appear in skipped_surfaces (no silent omission)
  - confidence class enforced per chunk (no claim-supporting claims from generic-alone hits)
  - vector-DB assumptions prohibited (federation KI)
  - 30-tic TTL on persisted packets (per Architect routing Q.3 default)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Allow importing from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

try:
    from zone_root import resolve_zone_root, load_ticzone, audit_logs_path
except ImportError:
    resolve_zone_root = None
    load_ticzone = None
    audit_logs_path = None

try:
    # Shared dehydration-aware doctrine resolver (tic 335 consumer-set fix): the
    # durable-id scout reads the CLAUDE.md chain, but post-dehydration the
    # federation + CGG cpr_ids live in sibling ledger.md surfaces — invisible if
    # only the compact roots are scanned.
    from doctrine_surfaces import resolve_doctrine_surfaces
except ImportError:
    resolve_doctrine_surfaces = None


# ─────────────────────────────────────────────────────────────────────────────
# Configuration constants
# ─────────────────────────────────────────────────────────────────────────────

PACKET_TTL_TICS = 30  # per Architect Q.3 default

VALID_TARGET_PROFILES = {
    "doctrine_chain", "audit_history", "code_path",
    "manifest_registry", "vague_intent", "mixed",
}
VALID_FANOUT_LEVELS = {"conservative", "normal", "wide"}
VALID_MUTATION_RISK = {"read_only", "low_mutation", "high_mutation"}
VALID_OUTPUT_KINDS = {
    "hydration_packet", "target_set_for_consolidate",
    "single_chunk", "claim_evidence",
}

# Generic terms — weak alone per binder §4.4 pairing rule
GENERIC_TERMS = frozenset({
    "domain", "estate", "site", "runtime", "state", "handler",
    "router", "agent", "surface", "principal",
})

# Probe budgets per fanout level
FANOUT_BUDGETS = {
    "conservative": {"max_probes": 5, "max_files_per_probe": 20, "exploratory_allowed": False},
    "normal": {"max_probes": 12, "max_files_per_probe": 50, "exploratory_allowed": True},
    "wide": {"max_probes": 25, "max_files_per_probe": 200, "exploratory_allowed": True},
}

# Cost-discovery thresholds (per binder §6.10)
COST_FILE_THRESHOLD = 100
COST_LINES_THRESHOLD = 50000

# Bounded chunk window (per file-access-discipline + binder §6.9)
DEFAULT_CHUNK_WINDOW = 40  # 20 before + 20 after target line
SMALL_FILE_LIMIT = 200     # files at or below this limit may be read in full

# Confidence classes
CONFIDENCE_CLASSES = (
    "hit",
    "weak_hit",
    "source_bearing_hit",
    "hydrated_evidence",
    "claim_supporting",
    "neighbor_only",
    "caution_only",
)

# Origin trust ranking (high → low)
HIGH_TRUST_ORIGINS = frozenset({
    "durable_handle", "manifest_key", "explicit_seed",
    "local_shape", "file_path",
})
MEDIUM_TRUST_ORIGINS = frozenset({
    "heading", "code_symbol", "json_key", "yaml_key", "ref_neighborhood",
})
LOW_TRUST_ORIGINS = frozenset({
    "caution", "exploratory", "noise",
})


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Intake
# ─────────────────────────────────────────────────────────────────────────────

def parse_intake(args: argparse.Namespace) -> dict[str, Any]:
    """Parse CLI args or --intake JSON into a structured intake form.

    Required fields per binder §4.1:
      goal, target_profile, fanout_level, mutation_risk, expected_output,
      enough_evidence_definition.
    Optional: known_target, explicit_seeds, forbidden_assumptions,
              known_neighbor_surfaces.
    """
    if args.intake:
        intake_path = Path(args.intake).resolve()
        if not intake_path.is_file():
            raise SystemExit(f"[rtch] intake file not found: {intake_path}")
        intake = json.loads(intake_path.read_text(encoding="utf-8"))
    elif args.validate_example:
        intake = _load_validation_example(args.validate_example)
    else:
        intake = {
            "goal": args.goal,
            "target_profile": args.profile,
            "fanout_level": args.fanout,
            "mutation_risk": args.risk,
            "expected_output": args.output_kind,
            "enough_evidence_definition": args.enough,
            "known_target": args.known_target,
            "explicit_seeds": list(args.seed or []),
            "forbidden_assumptions": list(args.forbid or []),
            "known_neighbor_surfaces": list(args.neighbor or []),
        }

    _validate_intake(intake)

    # Hash for packet_id stability
    canonical = json.dumps(
        {k: intake.get(k) for k in sorted(intake.keys())},
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    intake["intake_hash"] = hashlib.sha256(canonical).hexdigest()[:12]
    return intake


def _validate_intake(intake: dict[str, Any]) -> None:
    """Reject incomplete intakes. Per binder §4.1: enough_evidence_definition
    is load-bearing — without it, the lane has no halting condition."""
    required = (
        "goal", "target_profile", "fanout_level", "mutation_risk",
        "expected_output", "enough_evidence_definition",
    )
    missing = [k for k in required if not intake.get(k)]
    if missing:
        raise SystemExit(f"[rtch] intake missing required fields: {missing}")

    if intake["target_profile"] not in VALID_TARGET_PROFILES:
        raise SystemExit(f"[rtch] invalid target_profile: {intake['target_profile']}")
    if intake["fanout_level"] not in VALID_FANOUT_LEVELS:
        raise SystemExit(f"[rtch] invalid fanout_level: {intake['fanout_level']}")
    if intake["mutation_risk"] not in VALID_MUTATION_RISK:
        raise SystemExit(f"[rtch] invalid mutation_risk: {intake['mutation_risk']}")
    if intake["expected_output"] not in VALID_OUTPUT_KINDS:
        raise SystemExit(f"[rtch] invalid expected_output: {intake['expected_output']}")


def _load_validation_example(name: str) -> dict[str, Any]:
    """Built-in validation example intakes per binder §10."""
    examples = {
        "10.1": {
            "goal": "Locate the canonical topology document(s) describing federation domain/estate structure.",
            "target_profile": "doctrine_chain",
            "fanout_level": "normal",
            "mutation_risk": "read_only",
            "expected_output": "hydration_packet",
            "enough_evidence_definition": "I have at least one source-bearing hit naming the topology document and one chunk showing its structure section.",
            "explicit_seeds": ["topology", "SYSTEM_MAP"],
            "known_target": None,
            "forbidden_assumptions": [],
            "known_neighbor_surfaces": ["CLAUDE.md", "SYSTEM_MAP.md"],
        },
        "10.2": {
            "goal": "Find every CogPR candidate inscribed at tic 223 in MEMORY.md.",
            "target_profile": "audit_history",
            "fanout_level": "normal",
            "mutation_risk": "read_only",
            "expected_output": "target_set_for_consolidate",
            "enough_evidence_definition": "I have line-range chunks for every cpr_*_tic223 inscription block.",
            "explicit_seeds": ["cpr_", "tic223", "agnostic-candidate"],
            "known_target": str(Path.home() / ".claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md"),
            "forbidden_assumptions": [],
            "known_neighbor_surfaces": [],
        },
        "10.3": {
            "goal": "Show evidence that bench-packet-prep.py invokes queue_state_compile.py.",
            "target_profile": "code_path",
            "fanout_level": "conservative",
            "mutation_risk": "read_only",
            "expected_output": "claim_evidence",
            "enough_evidence_definition": "I have a hydrated chunk from bench-packet-prep.py showing the invocation site.",
            "explicit_seeds": ["queue_state_compile", "compile_lane_status", "DEGRADED_"],
            "known_target": "canonical_developer/context-grapple-gun/cgg-runtime/scripts/bench-packet-prep.py",
            "forbidden_assumptions": [],
            "known_neighbor_surfaces": ["audit-logs/cprs/queue_state_compile.py"],
        },
        "10.4": {
            "goal": "Enumerate manifest/registry files acting as authoritative for any federation runtime decision.",
            "target_profile": "manifest_registry",
            "fanout_level": "wide",
            "mutation_risk": "read_only",
            "expected_output": "hydration_packet",
            "enough_evidence_definition": "Map of (manifest path, what it authoritates over, what consumes it) covering at least 5 manifests.",
            "explicit_seeds": ["sync-manifest", "inbox-registry", "actor-registry", "active-manifest"],
            "known_target": None,
            "forbidden_assumptions": [],
            "known_neighbor_surfaces": [],
        },
        "10.5": {
            "goal": "Find anything related to the harmony engine.",
            "target_profile": "vague_intent",
            "fanout_level": "wide",
            "mutation_risk": "read_only",
            "expected_output": "hydration_packet",
            "enough_evidence_definition": "At least 3 source-bearing hits naming distinct harmony surfaces (engine, doctrine, runtime artifact).",
            "explicit_seeds": ["harmony", "HarmonyEngine"],
            "known_target": None,
            "forbidden_assumptions": [],
            "known_neighbor_surfaces": ["audit-logs/harmony/", "harmony-invoke.sh"],
        },
    }
    if name not in examples:
        raise SystemExit(f"[rtch] unknown validation example: {name}; valid: {list(examples)}")
    return examples[name]


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Zone orientation
# ─────────────────────────────────────────────────────────────────────────────

def orient_zone(intake: dict[str, Any]) -> dict[str, Any]:
    """Resolve cwd, repo_root, zone_root, rung_chain, obvious truth files.

    Read-only. Walks upward from intake.known_target if set, else cwd.
    """
    cwd = os.path.abspath(os.getcwd())
    start = intake.get("known_target") or cwd
    start = os.path.abspath(start)

    repo_root = _git_toplevel(start)
    zone_root = resolve_zone_root(start) if resolve_zone_root else _fallback_zone_root(start)

    rung_chain = _walk_rung_markers(start, zone_root)
    truth_files = _enumerate_truth_files(zone_root)
    manifests = _enumerate_manifests(zone_root)
    git_status = _git_status_short(repo_root or zone_root)

    return {
        "cwd": cwd,
        "start_dir": start,
        "repo_root": repo_root,
        "zone_root": zone_root,
        "rung_chain": rung_chain,
        "obvious_truth_files": truth_files,
        "obvious_manifests_indexes": manifests,
        "git_status_summary": git_status,
        "oriented_at": datetime.now(timezone.utc).isoformat(),
    }


def _git_toplevel(start: str) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, cwd=start if os.path.isdir(start) else os.path.dirname(start),
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _fallback_zone_root(start: str) -> str:
    d = start if os.path.isdir(start) else os.path.dirname(start)
    while d != os.path.dirname(d):
        if os.path.isfile(os.path.join(d, ".ticzone")):
            return d
        d = os.path.dirname(d)
    return os.path.abspath(os.getcwd())


def _walk_rung_markers(start: str, zone_root: str) -> list[dict[str, str]]:
    """List rung markers (.federation-root, .estate-root, .domain-root, .site-root)
    between start and zone_root, lowest to highest."""
    markers = []
    d = start if os.path.isdir(start) else os.path.dirname(start)
    seen = set()
    while True:
        if d in seen:
            break
        seen.add(d)
        for marker_name in (".site-root", ".domain-root", ".estate-root", ".federation-root", ".ticzone"):
            mpath = os.path.join(d, marker_name)
            if os.path.isfile(mpath):
                claude_md = os.path.join(d, "CLAUDE.md")
                markers.append({
                    "rung_dir": d,
                    "marker": marker_name,
                    "claude_md": claude_md if os.path.isfile(claude_md) else None,
                })
        if d == zone_root or d == os.path.dirname(d):
            break
        d = os.path.dirname(d)
    return markers


def _enumerate_truth_files(zone_root: str) -> list[str]:
    candidates = [
        "CLAUDE.md", "SYSTEM_MAP.md", "GLOSSARY.md", "GIT_RULES.md",
        "ARCHITECTURE.md", "AGENTS.md",
    ]
    found = []
    for c in candidates:
        p = os.path.join(zone_root, c)
        if os.path.isfile(p):
            found.append(p)
    return found


def _enumerate_manifests(zone_root: str) -> list[str]:
    candidates = [
        "audit-logs/cprs/effective-state/effective_state.json",
        "audit-logs/cprs/effective-state/effective_state.md",
        "audit-logs/agent-mailboxes/inbox-registry.json",
        "actor-registry.json",
        "autonomous_kernel/sub_telos.yaml",
        "audit-logs/signals/active-manifest.jsonl",
        "canonical_developer/context-grapple-gun/cgg-runtime/sync-manifest.json",
    ]
    found = []
    for c in candidates:
        p = os.path.join(zone_root, c)
        if os.path.isfile(p):
            found.append(p)
    # Also check nested actor-registry locations
    for nested in ["autonomous_kernel/actor-registry.json"]:
        p = os.path.join(zone_root, nested)
        if os.path.isfile(p) and p not in found:
            found.append(p)
    return found


def _git_status_short(repo_dir: Optional[str]) -> dict[str, Any]:
    if not repo_dir:
        return {"available": False}
    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, timeout=5, cwd=repo_dir,
        )
        if r.returncode != 0:
            return {"available": False}
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        return {"available": True, "dirty_files": len(lines), "sample": lines[:5]}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"available": False}


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — Shape scout
# ─────────────────────────────────────────────────────────────────────────────

def shape_scout(intake: dict[str, Any], zone: dict[str, Any]) -> dict[str, Any]:
    """Run low-cost filesystem-shape scans. No semantic content here — just
    structural signals (paths, names, headings, durable-id patterns)."""
    zone_root = zone["zone_root"]
    profile = intake["target_profile"]

    inventory = {
        "directory_map": _scan_directory_map(zone_root, depth=3, limit=50),
        "candidate_filenames": _scan_filenames(zone_root, intake, limit=50),
        "headings": _scan_headings(zone["obvious_truth_files"]),
        "durable_id_patterns": _scan_durable_ids(zone_root, intake),
        "json_yaml_keys": _scan_structured_keys(zone["obvious_manifests_indexes"]),
        "audit_tic_markers": _scan_audit_markers(zone_root),
        "source_of_truth_phrases": _scan_truth_phrases(zone["obvious_truth_files"]),
        "deprecation_markers": _scan_deprecation(zone["obvious_truth_files"]),
    }

    if profile == "code_path":
        inventory["code_symbols"] = _scan_code_symbols(zone_root, intake)

    inventory["scout_finished_at"] = datetime.now(timezone.utc).isoformat()
    return inventory


def _safe_run(argv: list[str], cwd: Optional[str] = None, timeout: int = 5) -> tuple[int, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.returncode, r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return -1, ""


def _scan_directory_map(zone_root: str, depth: int = 3, limit: int = 50) -> list[str]:
    rc, out = _safe_run(["find", zone_root, "-maxdepth", str(depth), "-type", "d"])
    if rc != 0:
        return []
    return [p for p in out.splitlines() if p and not _excluded_dir(p)][:limit]


_EXCLUDE_DIR_TOKENS = ("/.git", "/node_modules", "/__pycache__", "/.venv", "/dist", "/build", "/.next")


def _excluded_dir(p: str) -> bool:
    return any(tok in p for tok in _EXCLUDE_DIR_TOKENS)


def _scan_filenames(zone_root: str, intake: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
    """Inventory candidate files near the target. Prefer known_target's parent
    if set; otherwise scan zone_root with seed filtering."""
    target_dir = zone_root
    if intake.get("known_target"):
        kt = intake["known_target"]
        if not os.path.isabs(kt):
            kt = os.path.join(zone_root, kt)
        target_dir = os.path.dirname(kt) if os.path.isfile(kt) else kt

    seeds = [s.lower() for s in intake.get("explicit_seeds", [])]
    candidates: list[dict[str, Any]] = []
    rc, out = _safe_run(["find", target_dir, "-type", "f"])
    if rc != 0:
        return candidates
    for line in out.splitlines():
        if not line or _excluded_dir(line):
            continue
        bn = os.path.basename(line).lower()
        if seeds and not any(s in bn for s in seeds):
            continue
        try:
            sz = os.path.getsize(line)
        except OSError:
            continue
        candidates.append({"path": line, "size_bytes": sz})
        if len(candidates) >= limit:
            break
    return candidates


def _scan_headings(files: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in files:
        if not f.endswith(".md"):
            continue
        try:
            text = Path(f).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            m = re.match(r"^(#{1,3})\s+(.+)$", line)
            if m:
                out.append({
                    "path": f, "line": i, "level": len(m.group(1)),
                    "heading": m.group(2).strip()[:120],
                })
            if len(out) > 200:
                return out
    return out


def _scan_durable_ids(zone_root: str, intake: dict[str, Any]) -> dict[str, list[str]]:
    """Locate durable-id patterns. Bounded scope (zone_root CLAUDE.md chain
    + audit-logs/governance + audit-logs/cprs)."""
    patterns = {
        "cpr_id": r"cpr_[a-z][a-z_0-9]+",
        "tic_marker": r"tic[ -]?[0-9]{1,3}",
        "sig_id": r"sig_[a-z_]+_[a-f0-9]{4,}",
        "oavplt_id": r"OAVPLT-[0-9]+",
    }
    bounded_paths = []
    for cand in (
        os.path.join(zone_root, "CLAUDE.md"),
        os.path.join(zone_root, "canonical_developer", "CLAUDE.md"),
        os.path.join(zone_root, "canonical_developer", "context-grapple-gun", "CLAUDE.md"),
    ):
        if not os.path.isfile(cand):
            continue
        # Dehydration-aware (tic 335): fold in the sibling ledger.md for a
        # dehydrated rung so federation/CGG cpr_ids in the relocated bodies are
        # in scope, not just the compact-root pointers.
        if resolve_doctrine_surfaces is not None:
            bounded_paths.extend(resolve_doctrine_surfaces(cand))
        else:
            bounded_paths.append(cand)
    # De-dup while preserving order (resolve may return overlapping surfaces
    # across the three candidate roots in unusual layouts).
    bounded_paths = list(dict.fromkeys(bounded_paths))

    seeds = [s for s in intake.get("explicit_seeds", []) if s]
    found: dict[str, set[str]] = {k: set() for k in patterns}
    for p in bounded_paths:
        try:
            text = Path(p).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for kind, pat in patterns.items():
            for m in re.finditer(pat, text, re.IGNORECASE):
                found[kind].add(m.group(0).lower())
                if len(found[kind]) >= 30:
                    break
        for s in seeds:
            if s.lower() in text.lower():
                found.setdefault("explicit_seed_hit", set()).add(s)
    return {k: sorted(v) for k, v in found.items()}


def _scan_structured_keys(manifests: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for m in manifests:
        try:
            if m.endswith(".json"):
                data = json.loads(Path(m).read_text(encoding="utf-8", errors="ignore"))
                if isinstance(data, dict):
                    out[m] = sorted(data.keys())[:30]
                elif isinstance(data, list) and data and isinstance(data[0], dict):
                    out[m] = sorted(data[0].keys())[:30]
            elif m.endswith(".jsonl"):
                first = ""
                with open(m, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            first = line
                            break
                if first:
                    try:
                        d = json.loads(first)
                        if isinstance(d, dict):
                            out[m] = sorted(d.keys())[:30]
                    except json.JSONDecodeError:
                        pass
            elif m.endswith((".yaml", ".yml")):
                # YAML key extraction without yaml dep — simple top-level scan
                keys = []
                try:
                    text = Path(m).read_text(encoding="utf-8", errors="ignore")
                    for line in text.splitlines():
                        m2 = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", line)
                        if m2:
                            keys.append(m2.group(1))
                            if len(keys) >= 30:
                                break
                    out[m] = keys
                except OSError:
                    pass
        except (OSError, json.JSONDecodeError):
            continue
    return out


def _scan_audit_markers(zone_root: str) -> dict[str, Any]:
    audit_dir = os.path.join(zone_root, "audit-logs")
    if not os.path.isdir(audit_dir):
        return {"available": False}

    out: dict[str, Any] = {"available": True}
    tics_dir = os.path.join(audit_dir, "tics")
    if os.path.isdir(tics_dir):
        recent = sorted(os.listdir(tics_dir))[-5:]
        out["recent_tic_files"] = recent

    conf_dir = os.path.join(audit_dir, "conformations")
    if os.path.isdir(conf_dir):
        recent = sorted(os.listdir(conf_dir))[-5:]
        out["recent_conformations"] = recent

    return out


def _scan_truth_phrases(files: list[str]) -> list[dict[str, Any]]:
    pattern = re.compile(r"(authoritative|source of truth|canonical|single source)", re.IGNORECASE)
    hits: list[dict[str, Any]] = []
    for f in files:
        try:
            text = Path(f).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                hits.append({"path": f, "line": i, "preview": line.strip()[:120]})
            if len(hits) > 30:
                return hits
    return hits


def _scan_deprecation(files: list[str]) -> list[dict[str, Any]]:
    pattern = re.compile(r"(deprecated|superseded|TERMINAL|status:\s*pending|status:\s*deferred)")
    hits: list[dict[str, Any]] = []
    for f in files:
        try:
            text = Path(f).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                hits.append({"path": f, "line": i, "preview": line.strip()[:120]})
            if len(hits) > 30:
                return hits
    return hits


def _scan_code_symbols(zone_root: str, intake: dict[str, Any]) -> list[dict[str, Any]]:
    """Locate code symbol definitions in candidate code dirs."""
    seeds = [s for s in intake.get("explicit_seeds", []) if s]
    if not seeds:
        return []
    code_dirs = []
    for cand in (
        os.path.join(zone_root, "canonical_developer", "context-grapple-gun", "cgg-runtime", "scripts"),
        os.path.join(zone_root, "audit-logs", "cprs"),
    ):
        if os.path.isdir(cand):
            code_dirs.append(cand)
    out: list[dict[str, Any]] = []
    for d in code_dirs:
        for s in seeds:
            rc, sout = _safe_run(
                ["grep", "-rn", "-E", f"(^def {s}|^class {s}|^def .*{s}|^function {s})", d],
                timeout=10,
            )
            if rc == 0:
                for line in sout.splitlines()[:10]:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        out.append({"path": parts[0], "line": int(parts[1]) if parts[1].isdigit() else None, "preview": parts[2].strip()[:120], "seed": s})
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — Candidate basket
# ─────────────────────────────────────────────────────────────────────────────

def build_basket(intake: dict[str, Any], zone: dict[str, Any], scout: dict[str, Any]) -> dict[str, Any]:
    """Produce typed candidate basket per binder §4.4. Each term carries
    origin and use; pairing rule enforced; generic-alone warnings emitted."""
    terms: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(term: str, origin: str, use: str, paired_with: list[str], expected: str, notes: str = ""):
        key = (term.lower(), origin)
        if key in seen:
            return
        seen.add(key)
        terms.append({
            "term": term,
            "origin": origin,
            "use": use,
            "paired_with": paired_with,
            "expected_signal": expected,
            "notes": notes,
        })

    # Explicit seeds
    for s in intake.get("explicit_seeds", []):
        if s.lower() in GENERIC_TERMS:
            paired = [t for t in intake.get("explicit_seeds", []) if t != s and t.lower() not in GENERIC_TERMS]
            if paired:
                add(s, "explicit_seed", "locate", paired, "useful only when paired", "generic seed; pairing-rule enforced")
            else:
                add(s, "exploratory", "exploratory", [], "noisy alone; never claim-supporting", "generic seed without pairing")
        else:
            add(s, "explicit_seed", "locate", [], "exact-match locator", "")

    # Durable handles surfaced by scout
    for kind, vals in scout.get("durable_id_patterns", {}).items():
        for v in vals[:10]:
            add(v, "durable_handle", "locate", [], f"{kind} hit at federation CLAUDE chain", "")

    # File paths from manifests + truth files
    for f in zone.get("obvious_truth_files", [])[:10]:
        add(os.path.basename(f), "file_path", "locate", [], f"truth file at {f}", "")
    for f in zone.get("obvious_manifests_indexes", [])[:10]:
        add(os.path.basename(f), "manifest_key", "locate", [], f"manifest at {f}", "")

    # Headings as pressure terms
    for h in scout.get("headings", [])[:15]:
        head = h.get("heading", "")
        if head and len(head) > 3 and head.lower() not in GENERIC_TERMS:
            add(head, "heading", "pressure", [], f"heading at {h.get('path','?')}:{h.get('line','?')}", "")

    # JSON/YAML/manifest keys from structured surfaces
    for path, keys in scout.get("json_yaml_keys", {}).items():
        for k in keys[:5]:
            add(k, "json_key" if path.endswith(".json") else "yaml_key", "locate", [], f"key in {os.path.basename(path)}", "")

    # Source-of-truth phrases as caution markers (claim-grade language requires per-hit verify)
    for p in scout.get("source_of_truth_phrases", [])[:5]:
        add(p.get("preview", "")[:50], "ref_neighborhood", "pressure", [], f"truth phrase at {p.get('path','?')}", "")

    # Code symbols if surfaced
    for c in scout.get("code_symbols", []):
        add(c.get("seed", ""), "code_symbol", "locate", [], f"definition at {c.get('path','?')}:{c.get('line','?')}", "")

    # Filter: drop terms with empty term string
    terms = [t for t in terms if t.get("term", "").strip()]

    # Generic-alone warnings (pairing-rule enforcement)
    warnings = _detect_generic_alone_warnings(terms)

    return {
        "basket_id": f"rtch_basket_{intake['intake_hash']}",
        "intake_ref": intake["intake_hash"],
        "terms": terms,
        "term_count": len(terms),
        "generic_alone_warnings": warnings,
    }


def _detect_generic_alone_warnings(terms: list[dict[str, Any]]) -> list[str]:
    """Per binder §4.4: generic terms are weak alone. Surface warnings when
    generic terms appear without stronger pairing."""
    warnings = []
    for t in terms:
        term_lower = t.get("term", "").lower()
        if term_lower in GENERIC_TERMS:
            paired = t.get("paired_with") or []
            origin = t.get("origin", "")
            # If origin is exploratory or no strong pairing exists, warn
            if origin == "exploratory" or not paired:
                warnings.append(
                    f"Generic term '{t['term']}' surfaced as {origin} without strong pairing — never claim-supporting alone."
                )
    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5 — Probe plan
# ─────────────────────────────────────────────────────────────────────────────

def build_probe_plan(intake: dict[str, Any], zone: dict[str, Any], basket: dict[str, Any]) -> dict[str, Any]:
    """Generate typed probe records per binder §4.5. Bounded by fanout level."""
    fanout = intake["fanout_level"]
    budget = FANOUT_BUDGETS[fanout]
    profile = intake["target_profile"]

    probes: list[dict[str, Any]] = []
    pid = 0

    def add_probe(family: str, purpose: str, terms: list[str], target_set: list[str], cmd_class: str, expected: str, limitation: str, claim_authority: str):
        nonlocal pid
        if len(probes) >= budget["max_probes"]:
            return
        pid += 1
        probes.append({
            "probe_id": f"rtch_probe_{basket['basket_id']}_{pid:02d}",
            "family": family,
            "purpose": purpose,
            "input_terms": terms,
            "target_set": target_set[:budget["max_files_per_probe"]],
            "command_class": cmd_class,
            "expected_signal": expected,
            "limitation": limitation,
            "claim_authority": claim_authority,
        })

    # File inventory probes for known_target
    if intake.get("known_target"):
        kt = intake["known_target"]
        add_probe(
            "file_inventory",
            f"Confirm known_target exists and bound size for {kt}",
            [kt], [kt],
            "wc -l <path> + stat <path>",
            "file size + line count",
            "size doesn't imply content match",
            "source-bearing if path exists",
        )

    # Explicit seed probes (high authority)
    for t in basket["terms"]:
        if t["origin"] == "explicit_seed" and t["use"] == "locate":
            target = []
            if intake.get("known_target"):
                target = [intake["known_target"]]
            else:
                target = zone.get("obvious_truth_files", [])[:5]
            add_probe(
                "explicit_seed",
                f"Exact-match grep for explicit_seed '{t['term']}'",
                [t["term"]], target,
                "rg -nF '<term>' <files>",
                f"hits anchored at term locations",
                "case-sensitive; misses spaced variants",
                "source_bearing if origin remains explicit_seed",
            )

    # Durable handle probes
    for t in basket["terms"]:
        if t["origin"] == "durable_handle" and len(probes) < budget["max_probes"]:
            target = zone.get("obvious_truth_files", [])[:3]
            add_probe(
                "durable_handle",
                f"Locate durable handle '{t['term']}' in CLAUDE chain",
                [t["term"]], target,
                "rg -nF '<handle>' <chain>",
                "1-3 inscription hits",
                "id matches do not certify content",
                "claim_supporting if origin = durable_handle on source-of-truth file",
            )

    # Heading probe (pressure)
    if profile in ("doctrine_chain", "vague_intent", "audit_history"):
        heading_terms = [t["term"] for t in basket["terms"] if t["origin"] == "heading"][:5]
        if heading_terms:
            add_probe(
                "heading",
                "Locate heading hits across truth files",
                heading_terms[:5],
                zone.get("obvious_truth_files", [])[:3],
                "rg --no-heading -n '^#+.*<term>' <files>",
                "0-3 heading hits",
                "headings prove anchor presence, not doctrine status",
                "source_bearing on heading hit",
            )

    # Code symbol probes (code_path profile only)
    if profile == "code_path":
        code_terms = [t["term"] for t in basket["terms"] if t["origin"] == "code_symbol"][:5]
        for ct in code_terms:
            zone_root = zone["zone_root"]
            target = [
                os.path.join(zone_root, "canonical_developer", "context-grapple-gun", "cgg-runtime", "scripts"),
                os.path.join(zone_root, "audit-logs", "cprs"),
            ]
            add_probe(
                "code_symbol",
                f"Locate definitions/import sites for code symbol '{ct}'",
                [ct], [t for t in target if os.path.isdir(t)][:2],
                "git grep -n 'def <symbol>\\|class <symbol>'",
                "definition + import sites",
                "naming-convention drift can produce zero hits",
                "claim_supporting on definition match",
            )

    # Manifest/registry probes (manifest_registry profile)
    if profile in ("manifest_registry", "vague_intent"):
        manifest_files = zone.get("obvious_manifests_indexes", [])[:5]
        if manifest_files:
            add_probe(
                "manifest_registry",
                "Enumerate manifest top-level keys + identify authoritative claims",
                [t["term"] for t in basket["terms"] if t["origin"] == "manifest_key"][:3],
                manifest_files,
                "jq 'keys' + rg 'authoritative|source of truth'",
                "key inventory + authority phrase hits",
                "key existence ≠ semantic authority",
                "source_bearing per manifest",
            )

    # Reference/backlink probes (where available)
    if budget["exploratory_allowed"] and profile != "conservative":
        durable = [t["term"] for t in basket["terms"] if t["origin"] == "durable_handle"][:3]
        for dt in durable:
            zone_root = zone["zone_root"]
            target = [os.path.join(zone_root, "audit-logs", "governance")]
            target = [t for t in target if os.path.isdir(t)]
            if target:
                add_probe(
                    "reference_backlink",
                    f"Find references to durable handle '{dt}' in governance",
                    [dt], target,
                    "rg -F '<handle>' <governance>",
                    "0-N backlinks",
                    "backlinks ≠ semantic agreement",
                    "neighbor_only",
                )

    # Source-of-truth phrase probe (caution-grade)
    if budget["exploratory_allowed"]:
        add_probe(
            "source_of_truth_phrase",
            "Locate authoritative-claim language",
            ["authoritative", "source of truth", "canonical"],
            zone.get("obvious_truth_files", [])[:3],
            "rg -i 'authoritative|source of truth|canonical' <files>",
            "claim-language hits",
            "phrase presence ≠ correct claim",
            "caution_only — per-hit verify",
        )

    # Audit/tic temporal probes (audit_history profile)
    if profile == "audit_history":
        zone_root = zone["zone_root"]
        audit_dir = os.path.join(zone_root, "audit-logs")
        if os.path.isdir(audit_dir):
            add_probe(
                "temporal_provenance",
                "Locate tic/timestamp markers in audit history",
                [t["term"] for t in basket["terms"] if t["origin"] == "explicit_seed" and "tic" in t["term"].lower()][:3] or ["tic"],
                [audit_dir],
                "rg 'tic[ -]?<N>' <audit_dir>",
                "tic markers in events/conformations/governance",
                "tic presence ≠ semantic event match",
                "source_bearing per hit",
            )

    return {
        "plan_id": f"rtch_plan_{basket['basket_id']}",
        "basket_ref": basket["basket_id"],
        "fanout_level": fanout,
        "probe_count": len(probes),
        "probe_budget_remaining": budget["max_probes"] - len(probes),
        "probes": probes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5b/6 — Probe execution + chunk hydration
# ─────────────────────────────────────────────────────────────────────────────

def execute_probes_and_hydrate(intake: dict[str, Any], zone: dict[str, Any], plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Execute each probe, hydrate bounded chunks for source-bearing hits.

    Returns (executed_probes, hydrated_chunks).
    """
    executed: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []

    for probe in plan["probes"]:
        outcome = _execute_probe(probe, zone)
        executed.append(outcome)
        if outcome.get("hits"):
            new_chunks = _hydrate_hits(outcome, zone, intake)
            chunks.extend(new_chunks)
    return executed, chunks


def _execute_probe(probe: dict[str, Any], zone: dict[str, Any]) -> dict[str, Any]:
    family = probe["family"]
    terms = probe["input_terms"]
    target_set = probe["target_set"]
    hits: list[dict[str, Any]] = []

    if family == "file_inventory":
        for path in target_set:
            full = path if os.path.isabs(path) else os.path.join(zone["zone_root"], path)
            if os.path.isfile(full):
                rc, out = _safe_run(["wc", "-l", full])
                size = os.path.getsize(full) if os.path.isfile(full) else 0
                lc = int(out.strip().split()[0]) if rc == 0 and out.strip() else 0
                hits.append({"path": full, "size_bytes": size, "line_count": lc, "preview": "(file_inventory)"})

    elif family in ("explicit_seed", "durable_handle", "heading", "reference_backlink", "source_of_truth_phrase", "temporal_provenance"):
        # Use grep -n -F for fixed strings, -E for regex
        flags = "-nF"
        for term in terms:
            for tgt in target_set:
                full = tgt if os.path.isabs(tgt) else os.path.join(zone["zone_root"], tgt)
                if not (os.path.isfile(full) or os.path.isdir(full)):
                    continue
                argv = ["grep", "-r", flags, term, full] if os.path.isdir(full) else ["grep", flags, term, full]
                rc, out = _safe_run(argv, timeout=10)
                if rc == 0:
                    for line in out.splitlines()[:10]:
                        parsed = _parse_grep_line(line, full, isdir=os.path.isdir(full))
                        if parsed:
                            parsed["matched_term"] = term
                            hits.append(parsed)

    elif family == "code_symbol":
        for term in terms:
            for tgt in target_set:
                full = tgt if os.path.isabs(tgt) else os.path.join(zone["zone_root"], tgt)
                if not os.path.isdir(full):
                    continue
                rc, out = _safe_run(
                    ["grep", "-rn", "-E", f"(^def {term}|^class {term}|^def .*{term}|^function {term})", full],
                    timeout=10,
                )
                if rc == 0:
                    for line in out.splitlines()[:5]:
                        parsed = _parse_grep_line(line, full, isdir=True)
                        if parsed:
                            parsed["matched_term"] = term
                            hits.append(parsed)

    elif family == "manifest_registry":
        for path in target_set:
            full = path if os.path.isabs(path) else os.path.join(zone["zone_root"], path)
            if not os.path.isfile(full):
                continue
            try:
                if full.endswith(".json"):
                    data = json.loads(Path(full).read_text(encoding="utf-8", errors="ignore"))
                    keys = sorted(data.keys()) if isinstance(data, dict) else []
                    hits.append({"path": full, "preview": f"keys: {keys[:10]}", "matched_term": "(manifest_keys)", "line": 1, "size_bytes": os.path.getsize(full), "line_count": -1})
            except (OSError, json.JSONDecodeError):
                continue

    return {**probe, "hits": hits, "hit_count": len(hits), "executed_at": datetime.now(timezone.utc).isoformat()}


def _parse_grep_line(line: str, full_path: str, isdir: bool) -> Optional[dict[str, Any]]:
    if isdir:
        # path:line:content
        parts = line.split(":", 2)
        if len(parts) >= 3 and parts[1].isdigit():
            return {"path": parts[0], "line": int(parts[1]), "preview": parts[2].strip()[:120]}
    else:
        # line:content
        parts = line.split(":", 1)
        if len(parts) >= 2 and parts[0].isdigit():
            return {"path": full_path, "line": int(parts[0]), "preview": parts[1].strip()[:120]}
    return None


def _hydrate_hits(probe_outcome: dict[str, Any], zone: dict[str, Any], intake: dict[str, Any]) -> list[dict[str, Any]]:
    """Read bounded chunks around hit lines. Per file-access-discipline."""
    chunks: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    family = probe_outcome["family"]

    for hit in probe_outcome.get("hits", []):
        path = hit.get("path")
        line = hit.get("line", 0)
        if not path or not os.path.isfile(path):
            continue
        # Dedupe by (path, target_line_window_start)
        key = (path, max(1, line - DEFAULT_CHUNK_WINDOW // 2))
        if key in seen:
            continue
        seen.add(key)

        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
        except OSError:
            continue

        if not all_lines:
            continue

        if line and line > 0 and line <= len(all_lines):
            start = max(1, line - DEFAULT_CHUNK_WINDOW // 2)
            end = min(len(all_lines), line + DEFAULT_CHUNK_WINDOW // 2)
        elif len(all_lines) <= SMALL_FILE_LIMIT and probe_outcome.get("family") == "file_inventory":
            # Small file with no hit line — read first SMALL_FILE_LIMIT lines
            start, end = 1, min(SMALL_FILE_LIMIT, len(all_lines))
        else:
            start, end = 1, min(DEFAULT_CHUNK_WINDOW, len(all_lines))

        body = "".join(all_lines[start - 1:end])
        confidence = _classify_confidence(family, hit, probe_outcome)

        chunks.append({
            "chunk_id": f"rtch_chunk_{probe_outcome['probe_id']}_{len(chunks)+1:02d}",
            "path": path,
            "line_range": f"L{start}-L{end}",
            "why_included": f"{family} hit on '{hit.get('matched_term','?')}' at L{line}",
            "term_or_shape": hit.get("matched_term", "?"),
            "confidence_class": confidence,
            "limitation": _confidence_limitation(confidence),
            "next_re_entry_command": f"Read {path} with offset={start} limit={end - start + 1}",
            "body_preview": body[:600],
            "body_full_chars": len(body),
        })

        # Cap chunks per probe to prevent flood
        if len(chunks) >= 8:
            break
    return chunks


def _classify_confidence(family: str, hit: dict[str, Any], probe_outcome: dict[str, Any]) -> str:
    """Map probe family + claim_authority to a confidence class per binder §8."""
    declared = probe_outcome.get("claim_authority", "")
    matched_term = hit.get("matched_term", "")
    if matched_term.lower() in GENERIC_TERMS:
        return "weak_hit"
    if family == "file_inventory":
        return "source_bearing_hit"
    if family in ("explicit_seed", "durable_handle"):
        return "claim_supporting" if "claim_supporting" in declared else "source_bearing_hit"
    if family == "heading":
        return "source_bearing_hit"
    if family == "code_symbol":
        return "claim_supporting" if "claim_supporting" in declared else "source_bearing_hit"
    if family == "manifest_registry":
        return "source_bearing_hit"
    if family == "reference_backlink":
        return "neighbor_only"
    if family == "source_of_truth_phrase":
        return "caution_only"
    if family == "temporal_provenance":
        return "source_bearing_hit"
    return "hit"


def _confidence_limitation(c: str) -> str:
    return {
        "hit": "Locates a candidate; supports nothing further.",
        "weak_hit": "Generic-term hit without stronger pairing — surfaces in generic_alone_warnings.",
        "source_bearing_hit": "Hit at structurally significant location; does not certify content.",
        "hydrated_evidence": "Content claims bounded by chunk's line range only.",
        "claim_supporting": "Supports content claims as authored; does not certify currency or staleness.",
        "neighbor_only": "Adjacency claim only; not target claim.",
        "caution_only": "Per-hit verification required; supports nothing without consumer judgment.",
    }.get(c, "")


# ─────────────────────────────────────────────────────────────────────────────
# Stage 7 — Evidence packet
# ─────────────────────────────────────────────────────────────────────────────

def build_packet(intake: dict[str, Any], zone: dict[str, Any], scout: dict[str, Any], basket: dict[str, Any], plan: dict[str, Any], executed: list[dict[str, Any]], chunks: list[dict[str, Any]], current_tic: int) -> dict[str, Any]:
    """Assemble the typed evidence packet per binder §4.7."""
    # Selected surfaces — paths with at least one source_bearing_hit chunk
    selected: list[str] = []
    seen_paths: set[str] = set()
    for c in chunks:
        if c["confidence_class"] in ("source_bearing_hit", "hydrated_evidence", "claim_supporting"):
            p = c["path"]
            if p not in seen_paths:
                selected.append(p)
                seen_paths.add(p)

    # Skipped surfaces — paths exceeded SMALL_FILE_LIMIT but were not hydrated
    skipped: list[dict[str, Any]] = []
    for f in scout.get("candidate_filenames", []):
        if f["path"] not in seen_paths:
            try:
                with open(f["path"], encoding="utf-8", errors="ignore") as fh:
                    lc = sum(1 for _ in fh)
            except OSError:
                continue
            if lc > SMALL_FILE_LIMIT:
                skipped.append({
                    "path": f["path"],
                    "reason": f"file >{SMALL_FILE_LIMIT} lines AND no hit produced bounded chunk",
                    "size_bytes": f["size_bytes"],
                    "line_count": lc,
                })

    # Unresolved questions — federation KI mandatory (cardinality > 0)
    unresolved = _enumerate_unresolved(intake, zone, basket, executed)

    # Halting reason
    enough = intake.get("enough_evidence_definition", "")
    enough_lower = enough.lower()
    have_source_bearing = any(c["confidence_class"] in ("source_bearing_hit", "hydrated_evidence", "claim_supporting") for c in chunks)
    have_chunks = len(chunks) > 0
    if have_source_bearing and have_chunks:
        halting = "enough_evidence_definition_satisfied"
    elif plan["probe_budget_remaining"] == 0:
        halting = "budget_exhausted"
    elif not have_chunks:
        halting = "no_signal_at_normal_fanout"
    else:
        halting = "partial_evidence_only"

    # Caution map — caution_only chunks
    caution_map = [
        {"path": c["path"], "flag": "caution-grade hit", "note": c["limitation"]}
        for c in chunks if c["confidence_class"] == "caution_only"
    ]

    # Next legal probes — probes still in budget that the consumer could escalate to
    next_legal: list[dict[str, Any]] = []
    if plan["probe_budget_remaining"] > 0 and halting != "enough_evidence_definition_satisfied":
        next_legal.append({
            "family": "wider_fanout",
            "purpose": f"escalate from {intake['fanout_level']} to next level (manual)",
            "limitation": "wide fanout cannot certify truth alone (binder §7.3)",
        })

    return {
        "packet_id": f"rtch_packet_{intake['intake_hash']}",
        "schema_version": "rtch.packet.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_at_tic": current_tic,
        "ttl_tics": PACKET_TTL_TICS,
        "expires_at_tic": current_tic + PACKET_TTL_TICS,
        "intake": intake,
        "zone_descriptor": zone,
        "candidate_basket": basket,
        "probe_plan": {
            "plan_id": plan["plan_id"],
            "fanout_level": plan["fanout_level"],
            "probe_count": plan["probe_count"],
            "probe_budget_remaining": plan["probe_budget_remaining"],
            "probes_executed": executed,
        },
        "hydrated_chunks": chunks,
        "selected_surfaces": selected,
        "skipped_surfaces": skipped,
        "unresolved_questions": unresolved,
        "caution_map": caution_map,
        "next_legal_probes": next_legal,
        "generic_alone_warnings": basket.get("generic_alone_warnings", []),
        "fanout_level_used": intake["fanout_level"],
        "halting_reason": halting,
    }


def _enumerate_unresolved(intake: dict[str, Any], zone: dict[str, Any], basket: dict[str, Any], executed: list[dict[str, Any]]) -> list[str]:
    """Federation KI: complexity preservation requires schema-level enforcement.
    Cardinality MUST be > 0 — produce honest unresolved questions."""
    unresolved = []

    # Probes that returned zero hits
    zero_hit_probes = [p for p in executed if p.get("hit_count", 0) == 0]
    for p in zero_hit_probes[:3]:
        unresolved.append(
            f"Probe '{p.get('purpose','?')[:80]}' returned 0 hits — term naming may have drifted or scope was wrong."
        )

    # Was scope wide enough?
    if intake["fanout_level"] == "conservative":
        unresolved.append(
            "Conservative fanout used — wider discovery (refs, neighbor probes) was deferred. "
            "If primary evidence is thin, escalate to fanout=normal."
        )

    # Currency check — RTCH does not verify whether selected surfaces are current
    unresolved.append(
        "RTCH does not verify whether surfaces are CURRENT (not stale or superseded). "
        "Currency check is an L4 probe responsibility per Volatility Handling Law."
    )

    # Generic-alone surfaces if any
    if basket.get("generic_alone_warnings"):
        unresolved.append(
            f"Basket contained {len(basket['generic_alone_warnings'])} generic-alone term(s); "
            "claims cannot rest on these."
        )

    if not unresolved:
        unresolved.append(
            "No probe produced surprising or contradictory output — but absence of surprise is not validation. "
            "Consider invoking surprise_assessment per federation KI."
        )

    return unresolved


# ─────────────────────────────────────────────────────────────────────────────
# Stage 8 — Persistence + handoff
# ─────────────────────────────────────────────────────────────────────────────

def persist_packet(packet: dict[str, Any], zone: dict[str, Any]) -> str:
    """Write packet to audit-logs/rtch/packets/<packet_id>.json with atomic
    write hygiene."""
    zone_root = zone["zone_root"]
    out_dir = os.path.join(zone_root, "audit-logs", "rtch", "packets")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{packet['packet_id']}.json")
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(packet, f, indent=2, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp_path, out_path)
    return out_path


def handoff_to_consolidate(packet: dict[str, Any], zone: dict[str, Any]) -> dict[str, Any]:
    """Hand selected_surfaces to /consolidate as --targets. Returns invocation
    metadata; actual /consolidate dispatch is the skill body's responsibility."""
    selected = packet.get("selected_surfaces", [])
    if not selected:
        return {"status": "skipped", "reason": "no selected_surfaces to hand off"}

    return {
        "status": "ready",
        "consolidate_argv": ["python3", "canonical_developer/context-grapple-gun/cgg-runtime/scripts/consolidate.py", "--targets"] + selected[:50],
        "rtch_packet_id": packet["packet_id"],
        "selected_surface_count": len(selected),
        "note": "Skill body or Architect invokes /consolidate with these targets; dump header should carry rtch_packet_id for provenance.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _current_tic(zone: dict[str, Any]) -> int:
    counter_path = os.path.expanduser("~/.claude/cgg-tic-counter.json")
    if os.path.isfile(counter_path):
        try:
            d = json.loads(Path(counter_path).read_text(encoding="utf-8"))
            return int(d.get("count") or d.get("counter") or 0)
        except (json.JSONDecodeError, OSError, ValueError):
            return 0
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Rehydrate subcommand (D4 — Ship 4)
# ─────────────────────────────────────────────────────────────────────────────
#
# Per cpr_ttl_governs_heat_not_memory_tic223: TTL governs Layer 3 hot-path
# eligibility, never Layer 1 verbatim retention. Rehydration is the explicit
# bridge from Layer 1 historical entry back into Layer 3 hot-path eligibility
# — invocation-driven, probe-based, with explicit diff outcomes.
#
# Outcomes:
#   refreshed             — selected_surfaces verified present + content sha256
#                           matches archive; packet returns to hot-path
#   drift_detected        — surfaces present but content sha256 changed; packet
#                           returns CAUTION, not truth — Architect must reconcile
#   superseded            — newer packet (same goal/seeds) found in packets/;
#                           rehydration declined; original past-slice intact
#   failed_rehydration    — packet not found OR all selected_surfaces missing;
#                           drift/caution emit, no hot-path force


def _locate_packet(packets_dir: Path, packet_ref: str) -> Optional[Path]:
    """Resolve packet_id (full or prefix) to packet path."""
    if not packets_dir.exists():
        return None
    # Exact match first
    exact = packets_dir / f"{packet_ref}.json"
    if exact.exists():
        return exact
    # Prefix / substring match
    matches = [p for p in packets_dir.glob("*.json") if packet_ref in p.stem]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # Ambiguous — caller treats as failed_rehydration with reason
        return None
    return None


def _hash_surface(path: Path, max_bytes: int = 50 * 1024 * 1024) -> Optional[str]:
    """sha256 of file content, capped. Returns None for non-files."""
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    return f"sha256:partial-over-{max_bytes}"
                h.update(chunk)
    except OSError:
        return None
    return f"sha256:{h.hexdigest()}"


def _detect_supersession(packets_dir: Path, packet: dict) -> Optional[str]:
    """Look for newer packet with same goal that's emitted post-original.

    Returns superseding packet_id if found, else None.
    """
    if not packets_dir.exists():
        return None
    original_id = packet.get("packet_id")
    original_tic = packet.get("current_tic")
    original_goal = (packet.get("intake") or {}).get("goal", "").strip()
    if not original_goal:
        return None
    for p in packets_dir.glob("*.json"):
        if p.stem == original_id:
            continue
        try:
            other = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        other_goal = (other.get("intake") or {}).get("goal", "").strip()
        other_tic = other.get("current_tic")
        if other_goal == original_goal and other_tic is not None and original_tic is not None:
            if other_tic > original_tic:
                return other.get("packet_id")
    return None


def rehydrate_main(argv: list[str]) -> int:
    """rtch.py rehydrate --packet <id> — Layer 1 → Layer 3 bridge."""
    parser = argparse.ArgumentParser(
        prog="rtch.py rehydrate",
        description="Rehydrate an RTCH packet from past-slice with diff outcomes",
    )
    parser.add_argument("--packet", required=True,
                        help="packet_id (full or unique prefix)")
    parser.add_argument("--zone-root", default=None,
                        help="federation zone root (default: discover)")
    parser.add_argument("--current-tic", type=int, default=None,
                        help="override current tic (default: discover)")
    parser.add_argument("--ttl-tics", type=int, default=30,
                        help="default TTL window (default 30 tics per binder Q.3)")
    args = parser.parse_args(argv)

    # Zone discovery
    if args.zone_root:
        zone_root = args.zone_root
    else:
        zone = orient_zone({"goal": "rehydrate", "seeds": [], "profile": "tactical",
                            "fanout": "bounded", "risk": "low",
                            "output_kind": "evidence_packet", "enough": "rehydrate_complete",
                            "known_target": None, "forbid": [], "neighbor": []})
        zone_root = zone["zone_root"]

    packets_dir = Path(zone_root) / "audit-logs" / "rtch" / "packets"

    # Locate packet
    packet_path = _locate_packet(packets_dir, args.packet)
    if packet_path is None:
        outcome = {
            "rehydrate_outcome": "failed_rehydration",
            "reason": "packet_not_found_or_ambiguous",
            "packet_ref": args.packet,
            "current_claim_force": "none",
            "past_slice_preserved": True,  # we did not touch any file
            "rule": "TTL governs Layer 3 only; original packet remains in past-slice",
        }
        print(json.dumps(outcome, indent=2))
        return 0  # informational, not an error

    # Load packet (read-only)
    try:
        packet = json.loads(packet_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        outcome = {
            "rehydrate_outcome": "failed_rehydration",
            "reason": f"packet_unreadable: {e}",
            "packet_path": str(packet_path),
            "past_slice_preserved": True,
        }
        print(json.dumps(outcome, indent=2))
        return 0

    packet_id = packet.get("packet_id")
    birth_tic = packet.get("current_tic") or packet.get("emission_tic") or 0
    current_tic = args.current_tic if args.current_tic is not None else _current_tic({"zone_root": zone_root})

    # TTL state
    ttl = packet.get("ttl_tics", args.ttl_tics)
    expires_at = birth_tic + ttl
    expired = current_tic > expires_at

    # Supersession check
    superseded_by = _detect_supersession(packets_dir, packet)
    if superseded_by:
        outcome = {
            "rehydrate_outcome": "superseded",
            "packet_id": packet_id,
            "superseded_by": superseded_by,
            "birth_tic": birth_tic,
            "current_tic": current_tic,
            "past_slice_preserved": True,
            "rule": "Original packet remains as past-slice verbatim; rehydration declines in favor of newer packet",
            "next_action": f"rehydrate --packet {superseded_by} (or accept supersession)",
        }
        print(json.dumps(outcome, indent=2))
        return 0

    # Re-probe selected_surfaces
    selected = packet.get("selected_surfaces") or []
    surface_results = []
    refreshed_count = 0
    drift_count = 0
    missing_count = 0
    chunks = packet.get("chunks") or []
    chunk_by_path = {}
    for ch in chunks:
        sp = ch.get("source_path") or ch.get("path")
        if sp:
            chunk_by_path.setdefault(sp, []).append(ch)

    for surface in selected:
        # selected_surfaces entries can be string paths or richer dicts
        if isinstance(surface, dict):
            surface_path = surface.get("path") or surface.get("source_path")
        else:
            surface_path = surface
        if not surface_path:
            continue
        full = Path(surface_path)
        if not full.is_absolute():
            full = Path(zone_root) / surface_path
        if not full.exists():
            surface_results.append({"path": surface_path, "status": "missing"})
            missing_count += 1
            continue
        # Drift check: compare current sha256 against archived chunk sha if present
        current_hash = _hash_surface(full)
        archived_hashes = []
        for ch in chunk_by_path.get(surface_path, []):
            for k in ("sha256", "content_sha256", "hash"):
                if ch.get(k):
                    archived_hashes.append(ch[k])
        if archived_hashes and current_hash and current_hash not in archived_hashes:
            surface_results.append({"path": surface_path, "status": "drift",
                                    "current_hash": current_hash,
                                    "archived_hashes": archived_hashes})
            drift_count += 1
        else:
            # No archive hash to compare OR matches archive
            note = "verified" if archived_hashes else "present_no_archive_hash"
            surface_results.append({"path": surface_path, "status": "present", "note": note,
                                    "current_hash": current_hash})
            if archived_hashes:
                refreshed_count += 1

    # Determine outcome
    total = len(selected)
    if total == 0:
        rehydrate_outcome = "failed_rehydration"
        reason = "packet_has_no_selected_surfaces"
    elif missing_count == total:
        rehydrate_outcome = "failed_rehydration"
        reason = "all_surfaces_missing"
    elif drift_count > 0:
        rehydrate_outcome = "drift_detected"
        reason = f"{drift_count}/{total}_surfaces_drifted"
    else:
        rehydrate_outcome = "refreshed"
        reason = f"{refreshed_count}/{total}_surfaces_verified" if refreshed_count else f"{total}/{total}_surfaces_present"

    # Hot-path force allocation
    if rehydrate_outcome == "refreshed":
        current_claim_force = "restored_with_caveat" if expired else "active"
    elif rehydrate_outcome == "drift_detected":
        current_claim_force = "caution_only"
    else:
        current_claim_force = "none"

    outcome_record = {
        "rehydrate_outcome": rehydrate_outcome,
        "reason": reason,
        "packet_id": packet_id,
        "packet_path": str(packet_path.relative_to(zone_root)) if str(packet_path).startswith(zone_root) else str(packet_path),
        "birth_tic": birth_tic,
        "current_tic": current_tic,
        "expires_at_tic": expires_at,
        "ttl_window_status": "expired" if expired else "active",
        "current_claim_force": current_claim_force,
        "surface_summary": {
            "total": total,
            "refreshed": refreshed_count,
            "drift": drift_count,
            "missing": missing_count,
        },
        "surface_results": surface_results,
        "past_slice_preserved": True,
        "rule": "Failed/drifted rehydration emits caution, not truth. Layer 1 packet untouched.",
    }
    print(json.dumps(outcome_record, indent=2))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    raw = argv if argv is not None else sys.argv[1:]
    # Subcommand dispatch (additive — preserves legacy single-mode invocation)
    if raw and raw[0] == "rehydrate":
        return rehydrate_main(raw[1:])

    p = argparse.ArgumentParser(description="RTCH — runtime tactical context hydration")
    p.add_argument("--goal")
    p.add_argument("--profile", choices=sorted(VALID_TARGET_PROFILES))
    p.add_argument("--fanout", choices=sorted(VALID_FANOUT_LEVELS))
    p.add_argument("--risk", choices=sorted(VALID_MUTATION_RISK))
    p.add_argument("--output-kind", dest="output_kind", choices=sorted(VALID_OUTPUT_KINDS))
    p.add_argument("--enough", help="enough_evidence_definition")
    p.add_argument("--seed", action="append", help="explicit seed term (repeatable)")
    p.add_argument("--known-target", dest="known_target")
    p.add_argument("--forbid", action="append", help="forbidden assumption (repeatable)")
    p.add_argument("--neighbor", action="append", help="known neighbor surface (repeatable)")
    p.add_argument("--intake", help="path to intake JSON file")
    p.add_argument("--validate-example", choices=["10.1", "10.2", "10.3", "10.4", "10.5"])
    p.add_argument("--persist", action="store_true", help="write packet to audit-logs/rtch/packets/")
    p.add_argument("--handoff-to-consolidate", action="store_true", dest="handoff")
    p.add_argument("--json", action="store_true", help="emit packet JSON to stdout (default)")

    args = p.parse_args(raw)

    intake = parse_intake(args)
    zone = orient_zone(intake)
    scout = shape_scout(intake, zone)
    basket = build_basket(intake, zone, scout)
    plan = build_probe_plan(intake, zone, basket)
    executed, chunks = execute_probes_and_hydrate(intake, zone, plan)
    current_tic = _current_tic(zone)
    packet = build_packet(intake, zone, scout, basket, plan, executed, chunks, current_tic)

    if args.handoff:
        packet["packaging_handoff"] = handoff_to_consolidate(packet, zone)

    if args.persist:
        out_path = persist_packet(packet, zone)
        packet["persisted_at"] = out_path

    print(json.dumps(packet, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
