#!/usr/bin/env python3
"""
border-stack.py — 7-Layer Border Stack Enforcement

Every request entering the compute mount passes through all seven layers
sequentially. Every return passes through layers 5-7. No layer may be
skipped. Fail-closed: if any layer cannot determine validity, reject.

Implements:
  - border-stack-spec.md (7-layer admission control)
  - envelopes.yaml (schema validation)
  - entity-ontology.md (identity resolution)
  - cache-governance-spec.md (trust-tier gating)
  - citizenization-policy.md (artifact classification)

Usage (CLI):
    python3 border-stack.py --enforce '<envelope_json>' --direction inbound
    python3 border-stack.py --enforce '<envelope_json>' --direction outbound
    python3 border-stack.py --audit <request_id>

Usage (module):
    from border_stack import enforce, audit_request

Exit codes: 0=pass, 1=rejected, 2=IO error.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from zone_root import resolve_zone_root, audit_logs_path, load_ticzone
    from lib.atomic_append import atomic_append_jsonl
except ImportError:
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


# ---------------------------------------------------------------------------
# Envelope type catalog (from envelopes.yaml)
# ---------------------------------------------------------------------------

# Required fields per envelope type (subset relevant to border stack)
ENVELOPE_SCHEMAS = {
    "compute.request": {
        "required": ["requester_id", "route_class", "payload_schema", "priority"],
        "provenance_required": True,
    },
    "compute.receipt": {
        "required": ["request_id", "provider_id", "result_schema",
                      "cost_metric", "duration_ms"],
        "provenance_required": True,
    },
    "route.plan": {
        "required": ["request_id", "route_candidates", "selection_rationale"],
        "provenance_required": False,
    },
    "route.challenge": {
        "required": ["route_plan_id", "challenger_id", "challenge_basis"],
        "provenance_required": False,
    },
    "contamination.notice": {
        "required": ["source_id", "affected_entries", "severity",
                      "detection_method"],
        "provenance_required": False,
    },
    "capacity.watch": {
        "required": ["provider_id", "utilization", "queue_depth", "error_rate"],
        "provenance_required": False,
    },
    "billing.observation": {
        "required": ["provider_id", "period", "invocation_count",
                      "total_cost", "budget_binding"],
        "provenance_required": False,
    },
    "egress.notification": {
        "required": ["request_id", "requester_id", "target_provider",
                      "target_region", "data_classification",
                      "acknowledgment_required"],
        "provenance_required": True,
    },
    "egress.acknowledgment": {
        "required": ["notification_id", "request_id", "requester_id",
                      "acknowledged", "acknowledgment_mode"],
        "provenance_required": True,
    },
}

# Egress posture to permitted transport channels
EGRESS_CHANNELS = {
    "SEALED": {"local_only"},
    "SCOPED": {"local_only", "private_router", "signed_callback"},
    "OPEN": {"local_only", "private_router", "signed_callback", "public_review"},
}

# Trust tier hierarchy (highest to lowest)
TRUST_TIERS = ["sovereign", "constitutional", "municipal_utility"]

# Standing hierarchy (lowest to highest)
STANDING_ORDER = ["guest", "tourist", "student", "resident", "citizen"]

# Minimum standing for operations
OPERATION_STANDING = {
    "inference.local": "student",
    "inference.remote": "student",
    "cache.read": "guest",
    "cache.write": "student",
    "cache.purge": "citizen",
    "execution.route": "student",
    "execution.challenge": "student",
}

# Artifact classification heuristics
GOVERNANCE_SIGNIFICANT_TYPES = {
    "contamination.notice", "route.challenge",
}
AUDIT_ONLY_TYPES = {
    "compute.receipt", "billing.observation", "capacity.watch",
    "egress.notification", "egress.acknowledgment",
}
TRANSIENT_TYPES = {
    "route.plan",  # route candidates before execution
}

# Trust-tier write gating for cache
CACHE_WRITE_PERMISSIONS = {
    "sovereign": {"sovereign", "constitutional", "municipal_utility"},
    "constitutional": {"constitutional"},
    "municipal_utility": {"municipal_utility"},
}


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _audit_root(zone_root=None):
    zr = zone_root or resolve_zone_root()
    return audit_logs_path(zr, load_ticzone(zr))


def _border_log(zone_root=None):
    ar = _audit_root(zone_root)
    return os.path.join(ar, "services", "border-stack", "enforcement.jsonl")


def _signals_path(zone_root=None):
    ar = _audit_root(zone_root)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(ar, "signals", f"{today}.jsonl")


def _deterministic_id(*parts):
    payload = json.dumps(list(parts), sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


# ---------------------------------------------------------------------------
# Signal emission
# ---------------------------------------------------------------------------

def _emit_signal(signal_id, kind, description, volume=40, zone_root=None):
    signal = {
        "signal_id": signal_id,
        "kind": kind,
        "source": "border-stack",
        "description": description,
        "volume": volume,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_append_jsonl(_signals_path(zone_root), signal)
    return signal


# ---------------------------------------------------------------------------
# Layer implementations
# ---------------------------------------------------------------------------

class LayerResult:
    """Result from a single layer check."""
    __slots__ = ("layer", "layer_name", "passed", "detail", "signals")

    def __init__(self, layer, layer_name, passed, detail, signals=None):
        self.layer = layer
        self.layer_name = layer_name
        self.passed = passed
        self.detail = detail
        self.signals = signals or []

    def to_dict(self):
        d = {
            "layer": self.layer,
            "layer_name": self.layer_name,
            "result": "PASS" if self.passed else "REJECT",
            "detail": self.detail,
        }
        if self.signals:
            d["signals"] = self.signals
        return d


def _layer_1_transport(envelope, direction, context):
    """Layer 1: Transport Border.

    Checks channel authorization and egress policy enforcement.
    """
    channel = envelope.get("transport_channel", "local_only")
    egress_policy = envelope.get("egress_policy", "SCOPED")

    # Determine which channels are permitted
    permitted = EGRESS_CHANNELS.get(egress_policy, set())

    if channel not in permitted:
        sig_id = _deterministic_id(
            "ALERT_transport_unauthorized_channel",
            envelope.get("request_id", "unknown"),
            channel)
        return LayerResult(
            1, "transport", False,
            f"Channel '{channel}' not permitted for egress policy '{egress_policy}'",
            signals=[{
                "signal_id": sig_id,
                "kind": "ALERT",
                "description": (
                    f"Unauthorized channel '{channel}' for "
                    f"egress_policy={egress_policy}"),
            }],
        )

    # SEALED providers: only local_only channel
    provider_id = envelope.get("provider_id", "")
    if provider_id and "mlx_local" in str(provider_id):
        if channel != "local_only":
            return LayerResult(
                1, "transport", False,
                f"SEALED provider {provider_id} cannot use channel '{channel}'",
                signals=[{
                    "signal_id": _deterministic_id(
                        "ALERT_sealed_egress_violation", provider_id, channel),
                    "kind": "ALERT",
                    "description": f"SEALED provider attempted non-local channel",
                }],
            )

    return LayerResult(
        1, "transport", True,
        f"Channel '{channel}' permitted for policy '{egress_policy}'")


def _layer_2_envelope(envelope, direction, context):
    """Layer 2: Envelope Border.

    Schema validation against envelopes.yaml types.
    """
    envelope_type = envelope.get("envelope_type")

    if not envelope_type:
        return LayerResult(
            2, "envelope", False,
            "Missing envelope_type field",
            signals=[{
                "signal_id": _deterministic_id(
                    "ALERT_envelope_schema_violation", "missing_type"),
                "kind": "ALERT",
                "description": "Envelope missing envelope_type field",
            }],
        )

    schema = ENVELOPE_SCHEMAS.get(envelope_type)
    if schema is None:
        return LayerResult(
            2, "envelope", False,
            f"Unregistered envelope type: {envelope_type}",
            signals=[{
                "signal_id": _deterministic_id(
                    "ALERT_envelope_schema_violation",
                    "unregistered", envelope_type),
                "kind": "ALERT",
                "description": f"Unregistered envelope type: {envelope_type}",
            }],
        )

    # Check required fields
    missing = [f for f in schema["required"] if f not in envelope]
    if missing:
        return LayerResult(
            2, "envelope", False,
            f"Missing required fields for {envelope_type}: {missing}",
            signals=[{
                "signal_id": _deterministic_id(
                    "ALERT_envelope_schema_violation",
                    envelope_type, str(missing)),
                "kind": "ALERT",
                "description": (
                    f"Schema violation on {envelope_type}: "
                    f"missing {missing}"),
            }],
        )

    # Check provenance if required
    if schema.get("provenance_required"):
        has_provenance = any(
            k in envelope for k in ("requester_id", "provider_id", "timestamp"))
        if not has_provenance:
            return LayerResult(
                2, "envelope", False,
                f"Provenance required for {envelope_type} but not found")

    return LayerResult(
        2, "envelope", True,
        f"Schema valid for {envelope_type}")


def _layer_3_identity(envelope, direction, context):
    """Layer 3: Identity Border.

    Requester resolution and standing/role/jurisdiction check.
    """
    requester_id = envelope.get("requester_id")

    if not requester_id:
        # Some envelope types don't have requester_id (e.g., compute.receipt)
        if direction == "outbound":
            return LayerResult(
                3, "identity", True,
                "Outbound: identity check deferred to provider_id")
        return LayerResult(
            3, "identity", False,
            "Missing requester_id",
            signals=[{
                "signal_id": _deterministic_id(
                    "ALERT_identity_missing", "no_requester_id"),
                "kind": "ALERT",
                "description": "Envelope missing requester_id for inbound request",
            }],
        )

    # Resolve standing via standing-engine if available
    standing = context.get("requester_standing", "unknown")
    try:
        # Attempt import of standing engine for live resolution
        from standing_engine import _get_entity_standing
        resolved = _get_entity_standing(requester_id)
        if resolved:
            standing = resolved
            context["requester_standing"] = standing
    except (ImportError, Exception):
        pass

    if standing == "unknown":
        # Fail closed: unknown standing = reject
        return LayerResult(
            3, "identity", False,
            f"Cannot resolve standing for entity {requester_id}. Fail-closed.",
            signals=[{
                "signal_id": _deterministic_id(
                    "ALERT_identity_insufficient_standing",
                    requester_id, "unknown"),
                "kind": "ALERT",
                "description": (
                    f"Entity {requester_id} standing unknown — rejected"),
            }],
        )

    # Check operation standing requirements
    route_class = envelope.get("route_class", "")
    capability = envelope.get("capability", route_class)
    min_standing = OPERATION_STANDING.get(capability, "student")
    min_idx = STANDING_ORDER.index(min_standing) if min_standing in STANDING_ORDER else 2
    cur_idx = STANDING_ORDER.index(standing) if standing in STANDING_ORDER else -1

    if cur_idx < min_idx:
        return LayerResult(
            3, "identity", False,
            f"Entity {requester_id} standing '{standing}' insufficient "
            f"for '{capability}' (requires '{min_standing}')",
            signals=[{
                "signal_id": _deterministic_id(
                    "ALERT_identity_insufficient_standing",
                    requester_id, capability),
                "kind": "ALERT",
                "description": (
                    f"Insufficient standing: {standing} < {min_standing} "
                    f"for {capability}"),
            }],
        )

    return LayerResult(
        3, "identity", True,
        f"Entity {requester_id} standing '{standing}' sufficient for '{capability}'")


def _layer_4_cache(envelope, direction, context):
    """Layer 4: Cache Border.

    Cache read/write authorization based on trust tier.
    """
    # Only applies to cache operations
    route_class = envelope.get("route_class", "")
    capability = envelope.get("capability", route_class)
    if not capability.startswith("cache."):
        return LayerResult(
            4, "cache", True,
            "Non-cache operation: Layer 4 passthrough")

    # Determine requester trust tier
    trust_tier = context.get("requester_trust_tier", "municipal_utility")

    if capability == "cache.write":
        # Check write authorization
        target_tier = envelope.get("cache_target_tier", "municipal_utility")
        permitted_tiers = CACHE_WRITE_PERMISSIONS.get(trust_tier, set())

        if target_tier not in permitted_tiers:
            return LayerResult(
                4, "cache", False,
                f"Trust tier '{trust_tier}' cannot write to "
                f"cache tier '{target_tier}'",
                signals=[{
                    "signal_id": _deterministic_id(
                        "ALERT_cache_trust_tier_violation",
                        trust_tier, target_tier),
                    "kind": "ALERT",
                    "description": (
                        f"Cache trust violation: {trust_tier} write to "
                        f"{target_tier}"),
                }],
            )

    if capability == "cache.read":
        # Check contamination status
        entry_status = envelope.get("cache_entry_status", "active")
        if entry_status == "quarantined":
            # Only crisis steward can read quarantined entries
            requester_role = context.get("requester_role", "")
            if requester_role != "crisis_steward":
                return LayerResult(
                    4, "cache", False,
                    "Read of quarantined entry denied (not crisis steward)",
                    signals=[{
                        "signal_id": _deterministic_id(
                            "ALERT_cache_contamination_read",
                            envelope.get("request_id", "unknown")),
                        "kind": "ALERT",
                        "description": "Attempted read of quarantined cache entry",
                    }],
                )

    return LayerResult(
        4, "cache", True,
        f"Cache operation '{capability}' authorized for trust tier '{trust_tier}'")


def _layer_5_callback(envelope, direction, context):
    """Layer 5: Callback Border.

    Return route validation for async operations.
    Only applies on outbound/return path.
    """
    if direction == "inbound":
        return LayerResult(
            5, "callback", True,
            "Inbound: callback layer not applicable")

    callback_mode = envelope.get("callback_mode", "null")

    if callback_mode == "null":
        # Synchronous — no callback needed
        return LayerResult(
            5, "callback", True,
            "Synchronous operation: no callback validation needed")

    if callback_mode == "signed_callback":
        # Verify signature presence (actual crypto verification would
        # require the signing key — this validates the structure)
        callback_signature = envelope.get("callback_signature")
        if not callback_signature:
            return LayerResult(
                5, "callback", False,
                "Signed callback missing signature",
                signals=[{
                    "signal_id": _deterministic_id(
                        "ALERT_callback_signature_invalid",
                        envelope.get("request_id", "unknown")),
                    "kind": "ALERT",
                    "description": "Callback response missing required signature",
                }],
            )

        # Verify callback target is registered
        callback_target = envelope.get("callback_target")
        if not callback_target:
            return LayerResult(
                5, "callback", False,
                "Signed callback missing target endpoint",
                signals=[{
                    "signal_id": _deterministic_id(
                        "ALERT_callback_endpoint_unregistered",
                        envelope.get("request_id", "unknown")),
                    "kind": "ALERT",
                    "description": "Callback to unregistered endpoint",
                }],
            )

    if callback_mode == "poll":
        # Verify correlation
        request_id = envelope.get("request_id")
        if not request_id:
            return LayerResult(
                5, "callback", False,
                "Polled response missing request_id for correlation")

    return LayerResult(
        5, "callback", True,
        f"Callback mode '{callback_mode}' validated")


def _layer_6_artifact_class(envelope, direction, context):
    """Layer 6: Artifact-Class Border.

    Classifies every output into artifact classes per citizenization-policy.md.
    This layer classifies — it does not block.
    """
    if direction == "inbound":
        return LayerResult(
            6, "artifact_class", True,
            "Inbound: artifact classification not applicable")

    envelope_type = envelope.get("envelope_type", "")

    if envelope_type in GOVERNANCE_SIGNIFICANT_TYPES:
        artifact_class = "governance_significant"
        rationale = f"{envelope_type} classified as governance-significant"
    elif envelope_type in AUDIT_ONLY_TYPES:
        artifact_class = "audit_only"
        rationale = f"{envelope_type} classified as audit-only"
    elif envelope_type in TRANSIENT_TYPES:
        artifact_class = "transient"
        rationale = f"{envelope_type} classified as transient"
    else:
        # Check content heuristics for unknown types
        content = json.dumps(envelope, sort_keys=True)
        governance_keywords = [
            "contamination", "violation", "escalat", "challenge",
            "finding", "proposal", "warrant",
        ]
        if any(kw in content.lower() for kw in governance_keywords):
            artifact_class = "governance_significant"
            rationale = "Content heuristic: governance keywords detected"
        else:
            artifact_class = "audit_only"
            rationale = "Default classification: audit-only"

    context["artifact_class"] = artifact_class
    context["artifact_class_rationale"] = rationale

    # If ambiguous, emit WATCH
    signals = []
    if artifact_class == "governance_significant" and "heuristic" in rationale:
        signals.append({
            "signal_id": _deterministic_id(
                "WATCH_artifact_classification_ambiguous",
                envelope.get("request_id", "unknown"),
                envelope_type),
            "kind": "WATCH",
            "description": (
                f"Artifact classification for {envelope_type} based on "
                f"heuristic — may need manual review"),
        })

    return LayerResult(
        6, "artifact_class", True,  # Layer 6 never blocks
        f"Classified as {artifact_class}: {rationale}",
        signals=signals)


def _layer_7_citizenization(envelope, direction, context):
    """Layer 7: Citizenization Border.

    Routes governance-significant artifacts into citizen candidate pipeline.
    """
    if direction == "inbound":
        return LayerResult(
            7, "citizenization", True,
            "Inbound: citizenization not applicable")

    artifact_class = context.get("artifact_class", "audit_only")

    if artifact_class != "governance_significant":
        return LayerResult(
            7, "citizenization", True,
            f"Artifact class '{artifact_class}': citizenization not triggered")

    # Verify lineage chain
    request_id = envelope.get("request_id")
    if not request_id:
        return LayerResult(
            7, "citizenization", False,
            "Governance-significant artifact missing request_id lineage",
            signals=[{
                "signal_id": _deterministic_id(
                    "ALERT_citizenization_lineage_incomplete",
                    envelope.get("envelope_type", "unknown")),
                "kind": "ALERT",
                "description": (
                    "Governance-significant artifact entered pipeline "
                    "without complete lineage"),
            }],
        )

    # Verify owner assignment
    owner = (
        envelope.get("requester_id")
        or envelope.get("provider_id")
        or envelope.get("challenger_id")
    )
    if not owner:
        return LayerResult(
            7, "citizenization", False,
            "Governance-significant artifact missing owner assignment")

    # Classify citizen type
    envelope_type = envelope.get("envelope_type", "")
    citizen_class_map = {
        "contamination.notice": "signal",
        "route.challenge": "finding",
        "capacity.watch": "watch",
    }
    citizen_class = citizen_class_map.get(envelope_type, "finding")

    context["citizen_class"] = citizen_class
    context["citizen_owner"] = owner

    return LayerResult(
        7, "citizenization", True,
        f"Routed to citizen pipeline: class={citizen_class}, owner={owner}")


# ---------------------------------------------------------------------------
# Main enforcement function
# ---------------------------------------------------------------------------

# Layer dispatch tables
INBOUND_LAYERS = [
    _layer_1_transport,
    _layer_2_envelope,
    _layer_3_identity,
    _layer_4_cache,
]

OUTBOUND_LAYERS = [
    _layer_5_callback,
    _layer_6_artifact_class,
    _layer_7_citizenization,
]


def enforce(envelope, direction="inbound", context=None, zone_root=None):
    """Enforce the border stack on an envelope.

    Args:
        envelope: The envelope dict to check.
        direction: "inbound" or "outbound".
        context: Optional dict with pre-resolved context
            (requester_standing, requester_trust_tier, requester_role, etc.)
        zone_root: Optional zone root path override.

    Returns dict:
        {
            "passed": bool,
            "direction": str,
            "layers": [LayerResult.to_dict(), ...],
            "signals_emitted": [...],
            "timestamp": ISO-8601,
            "envelope_type": str,
        }
    """
    if context is None:
        context = {}

    now = datetime.now(timezone.utc)

    if direction == "inbound":
        layers = INBOUND_LAYERS
    elif direction == "outbound":
        layers = OUTBOUND_LAYERS
    else:
        return {
            "passed": False,
            "direction": direction,
            "layers": [],
            "signals_emitted": [],
            "error": f"Invalid direction: {direction}",
            "timestamp": now.isoformat(),
        }

    results = []
    all_signals = []
    passed = True

    for layer_fn in layers:
        result = layer_fn(envelope, direction, context)
        results.append(result.to_dict())

        # Collect signals
        for sig in result.signals:
            all_signals.append(sig)
            _emit_signal(
                sig["signal_id"], sig["kind"], sig["description"],
                zone_root=zone_root)

        # Fail-closed: if any layer rejects, stop
        if not result.passed:
            passed = False
            break

    enforcement_record = {
        "passed": passed,
        "direction": direction,
        "envelope_type": envelope.get("envelope_type", "unknown"),
        "request_id": envelope.get("request_id"),
        "layers": results,
        "signals_emitted": all_signals,
        "context_snapshot": {
            k: v for k, v in context.items()
            if k in ("artifact_class", "citizen_class", "requester_standing")
        },
        "timestamp": now.isoformat(),
    }

    # Persist to audit log
    atomic_append_jsonl(_border_log(zone_root), enforcement_record)

    return enforcement_record


# ---------------------------------------------------------------------------
# Full request traversal (inbound + execute + outbound)
# ---------------------------------------------------------------------------

def enforce_full_traversal(request_envelope, response_envelope=None,
                           context=None, zone_root=None):
    """Enforce inbound stack on request, then outbound stack on response.

    Returns dict with both traversal results.
    """
    ctx = context or {}

    # Inbound traversal (L1-L4)
    inbound_result = enforce(request_envelope, "inbound", ctx, zone_root)

    if not inbound_result["passed"]:
        return {
            "inbound": inbound_result,
            "outbound": None,
            "overall": "rejected_inbound",
        }

    if response_envelope is None:
        return {
            "inbound": inbound_result,
            "outbound": None,
            "overall": "inbound_passed_awaiting_response",
        }

    # Outbound traversal (L5-L7)
    outbound_result = enforce(response_envelope, "outbound", ctx, zone_root)

    overall = "passed" if outbound_result["passed"] else "rejected_outbound"

    return {
        "inbound": inbound_result,
        "outbound": outbound_result,
        "overall": overall,
    }


# ---------------------------------------------------------------------------
# Audit query
# ---------------------------------------------------------------------------

def audit_request(request_id, zone_root=None):
    """Retrieve all border stack enforcement records for a request_id.

    Returns list of enforcement records.
    """
    log_path = _border_log(zone_root)
    if not os.path.isfile(log_path):
        return []

    records = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("request_id") == request_id:
                    records.append(rec)
            except json.JSONDecodeError:
                continue

    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Border Stack — 7-layer admission control")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--enforce", metavar="JSON",
                       help="Enforce border stack on an envelope (JSON string)")
    group.add_argument("--audit", metavar="REQUEST_ID",
                       help="Retrieve audit records for a request_id")
    parser.add_argument("--direction", choices=["inbound", "outbound"],
                        default="inbound",
                        help="Enforcement direction (default: inbound)")
    parser.add_argument("--context", metavar="JSON",
                        help="Optional context JSON (standing, trust tier, etc.)")

    args = parser.parse_args()

    try:
        if args.enforce:
            envelope = json.loads(args.enforce)
            ctx = {}
            if args.context:
                ctx = json.loads(args.context)
            result = enforce(envelope, args.direction, ctx)
            print(json.dumps(result, indent=2))
            sys.exit(0 if result["passed"] else 1)

        elif args.audit:
            records = audit_request(args.audit)
            print(json.dumps(records, indent=2))

    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"IO error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
