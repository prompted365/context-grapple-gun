#!/usr/bin/env python3
"""
harpoon-orchestrator.py — Harpoon Routing Brain

Receives compute.request envelopes and produces route.plan proposals.
Selects execution lane (local sovereign vs. remote burst) based on
egress policy, local capacity, and trust constraints.

Implements:
  - harpoon-orchestrator-spec.md (routing decision tree, route plans, challenges)
  - border-stack-spec.md (all routes traverse the 7-layer stack)
  - local-sovereign-lane-spec.md (primary execution path)
  - municipal-remote-compute-spec.md (burst capacity)

Usage (CLI):
    python3 harpoon-orchestrator.py --route '<compute.request JSON>'
    python3 harpoon-orchestrator.py --status
    python3 harpoon-orchestrator.py --challenge '<route.challenge JSON>'

Usage (module):
    from harpoon_orchestrator import (
        route_request,
        get_status,
        challenge_route,
        load_providers,
        load_services,
    )

Exit codes: 0=success, 1=validation error, 2=IO error, 3=routing error.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow importing from same directory
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from zone_root import resolve_zone_root, audit_logs_path, load_ticzone
    from lib.atomic_append import atomic_append_jsonl, atomic_write_json
except ImportError:
    # Minimal fallbacks for standalone testing
    def resolve_zone_root(start_dir=None):
        return os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    def audit_logs_path(zone_root, ticzone_config=None):
        return os.path.join(zone_root, "audit-logs")

    def load_ticzone(zone_root):
        return {}

    def atomic_append_jsonl(target, data):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, separators=(",", ":")) + "\n")

    def atomic_write_json(target, data):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")


# ---------------------------------------------------------------------------
# PROVISIONAL CONFIG — all thresholds lack calibration evidence
# ---------------------------------------------------------------------------
CONFIG = {
    # Local queue depth threshold before considering remote (PROVISIONAL)
    "local_queue_depth_threshold": 10,

    # Hard ceiling for priority requests in local queue (PROVISIONAL)
    "local_priority_ceiling": 50,

    # Routing latency warning threshold in ms (PROVISIONAL)
    "routing_latency_warn_ms": 500,

    # Challenge rate threshold per tic (PROVISIONAL)
    "challenge_rate_threshold": 3,

    # Challenge window duration — "1_tic" for routine, "immediate" for governance
    "challenge_window_routine": "1_tic",
    "challenge_window_governance": "immediate",

    # Valid egress policies
    "valid_egress_policies": {"SEALED", "SCOPED", "OPEN"},

    # Valid priority classes
    "valid_priorities": {"standard", "governance"},

    # Route plan audit log (relative to audit-logs root)
    "route_plan_log": "services/harpoon-orchestrator/route-plans.jsonl",

    # Challenge audit log (relative to audit-logs root)
    "challenge_log": "services/harpoon-orchestrator/challenges.jsonl",

    # Provider status file (relative to audit-logs root)
    "provider_status_file": "services/harpoon-orchestrator/provider-status.json",

    # Local queue state file (relative to audit-logs root)
    "local_queue_file": "services/harpoon-orchestrator/local-queue.json",
}

# Egress posture to permitted channels (from border-stack-spec.md Layer 1)
EGRESS_CHANNEL_MAP = {
    "SEALED": {"local_only"},
    "SCOPED": {"local_only", "private_router", "signed_callback"},
    "OPEN": {"local_only", "private_router", "signed_callback", "public_review"},
}

# Trust level hierarchy (highest to lowest)
TRUST_ORDER = ["sovereign", "constitutional", "municipal_utility"]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _audit_root(zone_root=None):
    """Resolve the audit-logs root."""
    zr = zone_root or resolve_zone_root()
    return audit_logs_path(zr, load_ticzone(zr))


def _route_plan_log(zone_root=None):
    ar = _audit_root(zone_root)
    return os.path.join(ar, CONFIG["route_plan_log"])


def _challenge_log(zone_root=None):
    ar = _audit_root(zone_root)
    return os.path.join(ar, CONFIG["challenge_log"])


def _provider_status_path(zone_root=None):
    ar = _audit_root(zone_root)
    return os.path.join(ar, CONFIG["provider_status_file"])


def _local_queue_path(zone_root=None):
    ar = _audit_root(zone_root)
    return os.path.join(ar, CONFIG["local_queue_file"])


def _federation_root():
    """Walk up from zone root to find the federation root (has ak_control_room/)."""
    zr = resolve_zone_root()
    d = zr
    while d != os.path.dirname(d):
        if os.path.isdir(os.path.join(d, "ak_control_room")):
            return d
        d = os.path.dirname(d)
    return zr


# ---------------------------------------------------------------------------
# YAML loading (pure stdlib — parse subset needed)
# ---------------------------------------------------------------------------

def _simple_yaml_load(path):
    """Minimal YAML-like loader for providers.yaml/services.yaml.

    Handles the flat key-value structure used in ak_control_room configs.
    Returns raw text content for structured parsing, or empty dict on failure.
    For full fidelity, this loads as JSON-from-comments approach.
    We parse what we need: provider entries and their key fields.
    """
    if not os.path.isfile(path):
        return {}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    # If PyYAML available, use it
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        pass
    # Minimal fallback: extract provider/service blocks as flat dicts
    # This is intentionally limited — for production, PyYAML should be available
    return {"_raw": text}


def load_providers(federation_root=None):
    """Load providers.yaml and extract Mount Binder v2 providers.

    Returns dict of {provider_id: provider_info}.
    """
    fr = federation_root or _federation_root()
    path = os.path.join(fr, "ak_control_room", "providers.yaml")
    data = _simple_yaml_load(path)
    if not data or "_raw" in data:
        # Fallback: return known providers from spec
        return _fallback_providers()
    providers = data.get("providers", {})
    result = {}
    for pid, pinfo in providers.items():
        if isinstance(pinfo, dict) and pinfo.get("egress_posture"):
            result[pid] = pinfo
    return result


def _fallback_providers():
    """Hardcoded fallback provider info from spec when YAML parsing unavailable."""
    return {
        "mlx_local": {
            "description": "Local sovereign inference",
            "egress_posture": "SEALED",
            "trust_level": "sovereign",
            "provider_kind": "local_inference",
        },
        "hosted_ai": {
            "description": "Municipal remote compute",
            "egress_posture": "SCOPED",
            "trust_level": "municipal_utility",
            "provider_kind": "remote_inference",
        },
        "harpoon_exec": {
            "description": "Constitutional execution substrate",
            "egress_posture": "SCOPED",
            "trust_level": "constitutional",
            "provider_kind": "execution_substrate",
        },
    }


def load_services(federation_root=None):
    """Load services.yaml mount_services section.

    Returns dict of {service_id: service_info}.
    """
    fr = federation_root or _federation_root()
    path = os.path.join(fr, "ak_control_room", "services.yaml")
    data = _simple_yaml_load(path)
    if not data or "_raw" in data:
        return _fallback_services()
    return data.get("mount_services", {})


def _fallback_services():
    """Hardcoded fallback service info from spec."""
    return {
        "svc_mlx_inference": {
            "provider_family": "mlx_local",
            "route_class": "local",
            "egress_policy": "SEALED",
        },
        "svc_hostedai_inference": {
            "provider_family": "hosted_ai",
            "route_class": "remote",
            "egress_policy": "SCOPED",
        },
        "svc_harpoon_orchestrator": {
            "provider_family": "harpoon_exec",
            "route_class": "composite",
            "egress_policy": "SCOPED",
        },
        "svc_harpoon_cache_steward": {
            "provider_family": "harpoon_exec",
            "route_class": "local",
            "egress_policy": "SEALED",
        },
    }


# ---------------------------------------------------------------------------
# Provider status management
# ---------------------------------------------------------------------------

def _load_provider_status(zone_root=None):
    """Load provider status (active/suspended/unavailable)."""
    path = _provider_status_path(zone_root)
    if not os.path.isfile(path):
        return {
            "mlx_local": {"status": "active", "last_checked": None},
            "hosted_ai": {"status": "active", "last_checked": None},
        }
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "mlx_local": {"status": "active", "last_checked": None},
            "hosted_ai": {"status": "active", "last_checked": None},
        }


def _save_provider_status(status, zone_root=None):
    """Persist provider status."""
    path = _provider_status_path(zone_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_json(path, status)


# ---------------------------------------------------------------------------
# Local queue state
# ---------------------------------------------------------------------------

def _load_local_queue(zone_root=None):
    """Load local queue state."""
    path = _local_queue_path(zone_root)
    if not os.path.isfile(path):
        return {"depth": 0, "pending_requests": [], "last_updated": None}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"depth": 0, "pending_requests": [], "last_updated": None}


def _save_local_queue(queue_state, zone_root=None):
    """Persist local queue state."""
    path = _local_queue_path(zone_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_json(path, queue_state)


# ---------------------------------------------------------------------------
# Deterministic ID generation
# ---------------------------------------------------------------------------

def _deterministic_id(*parts):
    """Generate a deterministic SHA-256 hash from ordered parts."""
    payload = json.dumps(list(parts), sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


# ---------------------------------------------------------------------------
# Envelope validation
# ---------------------------------------------------------------------------

def validate_compute_request(envelope):
    """Validate a compute.request envelope.

    Returns (valid: bool, errors: list[str]).
    Required fields per envelopes.yaml: requester_id, route_class,
    payload_schema, priority.
    """
    errors = []

    if not isinstance(envelope, dict):
        return False, ["Envelope must be a JSON object"]

    # Required fields
    for field in ("requester_id", "route_class", "payload_schema", "priority"):
        if field not in envelope:
            errors.append(f"Missing required field: {field}")

    # Egress policy validation
    egress_policy = envelope.get("egress_policy", "SCOPED")
    if egress_policy not in CONFIG["valid_egress_policies"]:
        errors.append(f"Invalid egress_policy: {egress_policy}")

    # Priority validation
    priority = envelope.get("priority", "standard")
    if priority not in CONFIG["valid_priorities"]:
        errors.append(f"Invalid priority: {priority}")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Signal emission
# ---------------------------------------------------------------------------

def _emit_signal(signal_id, kind, description, volume=40, zone_root=None):
    """Emit a signal to the daily signals log."""
    ar = _audit_root(zone_root)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    signals_path = os.path.join(ar, "signals", f"{today}.jsonl")

    signal = {
        "signal_id": signal_id,
        "kind": kind,
        "source": "harpoon-orchestrator",
        "description": description,
        "volume": volume,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_append_jsonl(signals_path, signal)
    return signal


# ---------------------------------------------------------------------------
# Routing decision tree
# ---------------------------------------------------------------------------

def _check_local_capacity(zone_root=None):
    """Check if local sovereign lane has capacity.

    Returns (has_capacity: bool, queue_depth: int).
    """
    queue = _load_local_queue(zone_root)
    depth = queue.get("depth", 0)
    return depth < CONFIG["local_queue_depth_threshold"], depth


def _check_remote_policy(egress_policy, provider_status):
    """Check if remote burst lane is permitted and available.

    Returns (permitted: bool, reason: str).
    """
    if egress_policy == "SEALED":
        return False, "SEALED policy: remote never permitted"

    hosted_ai_status = provider_status.get("hosted_ai", {})
    if hosted_ai_status.get("status") == "suspended":
        return False, "HostedAI provider suspended"
    if hosted_ai_status.get("status") == "unavailable":
        return False, "HostedAI provider unavailable"

    return True, "Remote burst permitted"


def route_request(envelope, zone_root=None):
    """Execute the routing decision tree for a compute.request.

    Returns a route.plan envelope (dict).
    Raises ValueError on validation failure.
    """
    start_time = datetime.now(timezone.utc)

    # Validate envelope
    valid, errors = validate_compute_request(envelope)
    if not valid:
        raise ValueError(f"Invalid compute.request: {'; '.join(errors)}")

    request_id = envelope.get("request_id", _deterministic_id(
        envelope["requester_id"],
        json.dumps(envelope.get("payload_schema", {}), sort_keys=True),
        start_time.isoformat(),
    ))

    egress_policy = envelope.get("egress_policy", "SCOPED")
    priority = envelope.get("priority", "standard")

    provider_status = _load_provider_status(zone_root)
    local_has_capacity, queue_depth = _check_local_capacity(zone_root)

    # --- Decision tree ---
    decision = None
    target_service = None
    egress_will_occur = False
    rationale = {
        "egress_policy": egress_policy,
        "local_capacity_available": local_has_capacity,
        "queue_depth_at_decision": queue_depth,
        "priority_class": priority,
    }

    if egress_policy == "SEALED":
        # SEALED: local only, always
        if local_has_capacity:
            decision = "local"
            target_service = "svc_mlx_inference"
        else:
            decision = "queued"
            target_service = "svc_mlx_inference"
            rationale["queued_reason"] = "local_backpressure_sealed"
        rationale["remote_policy_permits"] = False

    elif egress_policy == "SCOPED":
        rationale["remote_policy_permits"] = False  # default, may change
        if local_has_capacity:
            # SCOPED + local has capacity: route local
            decision = "local"
            target_service = "svc_mlx_inference"
        else:
            # SCOPED + local overloaded: check remote
            remote_ok, remote_reason = _check_remote_policy(
                egress_policy, provider_status)
            rationale["remote_policy_permits"] = remote_ok
            rationale["remote_policy_reason"] = remote_reason
            if remote_ok:
                decision = "remote"
                target_service = "svc_hostedai_inference"
                egress_will_occur = True
            else:
                decision = "queued"
                target_service = "svc_mlx_inference"
                rationale["queued_reason"] = "local_overloaded_remote_unavailable"
                # Emit capacity watch
                _emit_signal(
                    signal_id=_deterministic_id(
                        "capacity_watch", "scoped_queue", request_id),
                    kind="WATCH",
                    description=(
                        f"SCOPED request queued: local overloaded "
                        f"(depth={queue_depth}), remote unavailable "
                        f"({remote_reason})"),
                    volume=35,
                    zone_root=zone_root,
                )

    elif egress_policy == "OPEN":
        # OPEN: best available lane
        if local_has_capacity:
            decision = "local"
            target_service = "svc_mlx_inference"
            rationale["remote_policy_permits"] = True
        else:
            remote_ok, remote_reason = _check_remote_policy(
                egress_policy, provider_status)
            rationale["remote_policy_permits"] = remote_ok
            if remote_ok:
                decision = "remote"
                target_service = "svc_hostedai_inference"
                egress_will_occur = True
            else:
                decision = "queued"
                target_service = "svc_mlx_inference"
                rationale["queued_reason"] = "all_lanes_exhausted"
                # Emit high-severity capacity watch
                _emit_signal(
                    signal_id=_deterministic_id(
                        "capacity_watch", "all_exhausted", request_id),
                    kind="WATCH",
                    description=(
                        f"All lanes exhausted for OPEN request. "
                        f"Local depth={queue_depth}, remote: {remote_reason}"),
                    volume=45,
                    zone_root=zone_root,
                )

    # Build route.plan envelope
    now = datetime.now(timezone.utc)
    plan_id = _deterministic_id(request_id, now.isoformat())

    route_plan = {
        "envelope_type": "route.plan",
        "plan_id": plan_id,
        "request_id": request_id,
        "egress_policy": egress_policy,
        "decision": decision,
        "rationale": rationale,
        "target_service": target_service,
        "egress_will_occur": egress_will_occur,
        "challengeable": True,
        "challenge_window": (
            CONFIG["challenge_window_governance"]
            if priority == "governance"
            else CONFIG["challenge_window_routine"]
        ),
        "status": "pending",
        "timestamp": now.isoformat(),
    }

    # If routing to remote, generate egress.notification obligation
    if egress_will_occur:
        notification_id = _deterministic_id(
            "egress_notification", plan_id, request_id)
        route_plan["egress_notification"] = {
            "envelope_type": "egress.notification",
            "notification_id": notification_id,
            "request_id": request_id,
            "requester_id": envelope["requester_id"],
            "target_provider": target_service,
            "target_region": envelope.get("route_preference", "nearest"),
            "data_classification": envelope.get("data_classification", "inference"),
            "acknowledgment_required": True,
            "auto_acknowledge_policy": envelope.get("auto_acknowledge_policy"),
            "status": "pending_acknowledgment",
        }

    # If queued, add to local queue
    if decision == "queued":
        queue = _load_local_queue(zone_root)
        queue["depth"] = queue.get("depth", 0) + 1
        queue["pending_requests"].append({
            "request_id": request_id,
            "plan_id": plan_id,
            "priority": priority,
            "queued_at": now.isoformat(),
        })
        queue["last_updated"] = now.isoformat()
        _save_local_queue(queue, zone_root)

    # Generate compute receipt stub for local routes
    # (MLX integration point — replace mock with real inference)
    if decision == "local":
        receipt_id = _deterministic_id(
            request_id, target_service, now.isoformat())
        route_plan["compute_receipt_stub"] = {
            "envelope_type": "compute.receipt",
            "receipt_id": receipt_id,
            "request_id": request_id,
            "provider_id": target_service,
            "route_class": "local",
            "egress_occurred": False,
            # --- MLX INTEGRATION POINT ---
            # Replace this stub with actual MLX inference call.
            # The stub returns a mock receipt. When MLX runtime is wired,
            # this becomes: mlx_result = mlx_inference(envelope["payload_schema"])
            "model_id": "mlx_stub_pending_integration",
            "duration_ms": 0,
            "cost_metric": {"type": "local_compute", "value": 0, "unit": "none"},
            "result_hash": None,
            "timestamp": now.isoformat(),
            "_integration_note": "MLX inference stub — wire to real runtime",
        }

    # Persist route plan to audit log
    atomic_append_jsonl(_route_plan_log(zone_root), route_plan)

    return route_plan


# ---------------------------------------------------------------------------
# Route challenge
# ---------------------------------------------------------------------------

def challenge_route(challenge_envelope, zone_root=None):
    """Process a route.challenge against a pending route.plan.

    Returns verdict dict: {verdict, plan_id, rationale, timestamp}.
    Raises ValueError on validation failure.
    """
    if not isinstance(challenge_envelope, dict):
        raise ValueError("Challenge must be a JSON object")

    required = ("route_plan_id", "challenger_id", "challenge_basis")
    for field in required:
        if field not in challenge_envelope:
            raise ValueError(f"Missing required field: {field}")

    plan_id = challenge_envelope["route_plan_id"]
    challenger_id = challenge_envelope["challenger_id"]
    challenge_basis = challenge_envelope["challenge_basis"]
    now = datetime.now(timezone.utc)

    challenge_id = _deterministic_id(
        plan_id, challenger_id,
        challenge_envelope.get("challenge_type", "general"))

    # Load existing route plans to find the challenged plan
    log_path = _route_plan_log(zone_root)
    challenged_plan = None
    if os.path.isfile(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    plan = json.loads(line)
                    if plan.get("plan_id") == plan_id:
                        challenged_plan = plan
                except json.JSONDecodeError:
                    continue

    if challenged_plan is None:
        raise ValueError(f"Route plan not found: {plan_id}")

    if challenged_plan.get("status") == "executed":
        raise ValueError(f"Route plan already executed: {plan_id}")

    # Build challenge record
    challenge_record = {
        "envelope_type": "route.challenge",
        "challenge_id": challenge_id,
        "plan_id": plan_id,
        "challenger_id": challenger_id,
        "challenge_type": challenge_envelope.get("challenge_type", "general"),
        "challenge_basis": challenge_basis,
        "evidence": challenge_envelope.get("evidence"),
        "expected_outcome": challenge_envelope.get("expected_outcome"),
        "challenged_plan_decision": challenged_plan.get("decision"),
        "challenged_plan_target": challenged_plan.get("target_service"),
        # Verdict: AFFIRM by default for now.
        # Full adversarial review is a governance action that requires
        # entity standing verification and review process.
        # This records the challenge and flags the plan.
        "verdict": "PAUSED",
        "verdict_rationale": (
            "Challenge recorded. Route plan paused pending adversarial review. "
            "Execution does not proceed until verdict is issued."
        ),
        "timestamp": now.isoformat(),
    }

    # Persist challenge
    atomic_append_jsonl(_challenge_log(zone_root), challenge_record)

    return challenge_record


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def get_status(zone_root=None):
    """Return current orchestrator status.

    Includes: provider status, local queue state, recent route plan summary.
    """
    provider_status = _load_provider_status(zone_root)
    queue = _load_local_queue(zone_root)
    providers = load_providers()
    services = load_services()

    # Count recent route plans
    log_path = _route_plan_log(zone_root)
    plan_counts = {"local": 0, "remote": 0, "queued": 0}
    total_plans = 0
    if os.path.isfile(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    plan = json.loads(line)
                    decision = plan.get("decision", "unknown")
                    plan_counts[decision] = plan_counts.get(decision, 0) + 1
                    total_plans += 1
                except json.JSONDecodeError:
                    continue

    return {
        "orchestrator": "harpoon",
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "providers": {
            pid: {
                "registered": pid in providers,
                "egress_posture": providers.get(pid, {}).get("egress_posture"),
                "trust_level": providers.get(pid, {}).get("trust_level"),
                "runtime_status": provider_status.get(pid, {}).get("status", "unknown"),
            }
            for pid in ("mlx_local", "hosted_ai", "harpoon_exec")
        },
        "local_queue": {
            "depth": queue.get("depth", 0),
            "threshold": CONFIG["local_queue_depth_threshold"],
            "at_capacity": queue.get("depth", 0) >= CONFIG["local_queue_depth_threshold"],
        },
        "route_plan_summary": {
            "total": total_plans,
            "by_decision": plan_counts,
        },
        "services_registered": list(services.keys()),
    }


# ---------------------------------------------------------------------------
# Provider management (suspension, re-admission)
# ---------------------------------------------------------------------------

def suspend_provider(provider_id, reason, zone_root=None):
    """Suspend a provider. In-flight work should be rerouted."""
    status = _load_provider_status(zone_root)
    now = datetime.now(timezone.utc).isoformat()

    status[provider_id] = {
        "status": "suspended",
        "suspended_at": now,
        "suspension_reason": reason,
        "last_checked": now,
    }
    _save_provider_status(status, zone_root)

    _emit_signal(
        signal_id=_deterministic_id("provider_suspended", provider_id, reason),
        kind="WATCH",
        description=f"Provider {provider_id} suspended: {reason}",
        volume=40,
        zone_root=zone_root,
    )

    return status[provider_id]


def reinstate_provider(provider_id, zone_root=None):
    """Reinstate a previously suspended provider."""
    status = _load_provider_status(zone_root)
    now = datetime.now(timezone.utc).isoformat()

    status[provider_id] = {
        "status": "active",
        "reinstated_at": now,
        "last_checked": now,
    }
    _save_provider_status(status, zone_root)
    return status[provider_id]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Harpoon Orchestrator — routing brain for compute mount")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--route", metavar="JSON",
                       help="Route a compute.request envelope (JSON string)")
    group.add_argument("--status", action="store_true",
                       help="Show orchestrator status")
    group.add_argument("--challenge", metavar="JSON",
                       help="Issue a route.challenge (JSON string)")
    group.add_argument("--suspend", metavar="PROVIDER_ID",
                       help="Suspend a provider")
    group.add_argument("--reinstate", metavar="PROVIDER_ID",
                       help="Reinstate a suspended provider")
    parser.add_argument("--reason", help="Reason for suspension")

    args = parser.parse_args()

    try:
        if args.route:
            envelope = json.loads(args.route)
            result = route_request(envelope)
            print(json.dumps(result, indent=2))

        elif args.status:
            result = get_status()
            print(json.dumps(result, indent=2))

        elif args.challenge:
            envelope = json.loads(args.challenge)
            result = challenge_route(envelope)
            print(json.dumps(result, indent=2))

        elif args.suspend:
            reason = args.reason or "CLI suspension"
            result = suspend_provider(args.suspend, reason)
            print(json.dumps(result, indent=2))

        elif args.reinstate:
            result = reinstate_provider(args.reinstate)
            print(json.dumps(result, indent=2))

    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"IO error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
