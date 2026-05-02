#!/usr/bin/env python3
"""trigger-router.py — Single-lane trigger router for entity activation.

Reads trigger-manifest.yaml, accepts events from hooks/scripts/skills,
resolves target entities, applies routing policy, delivers via inbox-envelope.py.

Primitive:
  Trigger routing is mandatory.
  Entity activation routes through inbox delivery.
  Direct activation is exception-only.

Flow:
  event -> trigger-router -> routing_policy -> inbox-envelope.write_envelope

This is the router (execution). It calls the handler (delivery contract).
Hooks call this instead of writing mandates directly.

Usage:
  # Route a trigger from a source event
  python3 trigger-router.py route \\
      --trigger-type mogul.mandate \\
      --source-event SessionStart \\
      --producer session-restore.sh \\
      --source-tic 52 \\
      --subject "Mogul mandate — tic 52" \\
      --body '{"mandate_id":"tic-52-...","cycle_request":{"run_now":["queue_refresh"]}}'

  # Route with explicit target override (for dynamic resolution)
  python3 trigger-router.py route \\
      --trigger-type swarm.task_dispatch \\
      --target ent_civil_engineer \\
      --source-tic 52 \\
      --subject "Queue compaction" \\
      --body '{"task_id":"t1","swarm_id":"sw1"}'

  # Dry-run (validate and print what would be routed, no write)
  python3 trigger-router.py route --dry-run \\
      --trigger-type mogul.mandate --source-tic 52 --subject "Test"

  # List all trigger types from manifest
  python3 trigger-router.py list

  # Show routing policy for a trigger type
  python3 trigger-router.py show --trigger-type mogul.mandate
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, audit_logs_path, load_ticzone

# Import inbox-envelope as module (hyphenated filename)
import importlib.util
_ie_spec = importlib.util.spec_from_file_location(
    "inbox_envelope",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "inbox-envelope.py"),
)
inbox_envelope = importlib.util.module_from_spec(_ie_spec)
_ie_spec.loader.exec_module(inbox_envelope)


# ─────────────────────────────────────────────
# Manifest Loading (full parse)
# ─────────────────────────────────────────────

def load_manifest(zone_root: str) -> dict:
    """Load and parse trigger-manifest.yaml. Returns full manifest dict."""
    path = os.path.join(zone_root, "autonomous_kernel", "trigger-manifest.yaml")
    if not os.path.isfile(path):
        _die(f"Trigger manifest not found: {path}")
    try:
        import yaml
        return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except ImportError:
        # No PyYAML — use inline parser
        return _parse_manifest_full(path)


def _parse_manifest_full(path: str) -> dict:
    """Parse trigger-manifest.yaml without PyYAML.

    Extracts trigger type keys and their nested properties as flat dicts.
    Sufficient for routing decisions — not a full YAML parser.
    """
    text = Path(path).read_text(encoding="utf-8")
    triggers = {}
    current_trigger = None
    current_data = {}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Top-level trigger key (2-space indent, ends with :)
        if line.startswith("  ") and not line.startswith("    ") and ":" in stripped:
            # Save previous trigger
            if current_trigger:
                triggers[current_trigger] = current_data
            key = stripped.split(":")[0].strip()
            if key and not key.startswith("#") and key != "triggers":
                current_trigger = key
                current_data = {}
            else:
                current_trigger = None
                current_data = {}
            continue

        # Nested properties under a trigger
        if current_trigger and line.startswith("    "):
            # Extract key: value pairs at various depths
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                k = parts[0].strip().lstrip("- ")
                v = parts[1].strip().strip('"').strip("'")
                if k and v and not k.startswith("#"):
                    current_data[k] = v

    if current_trigger:
        triggers[current_trigger] = current_data

    # Extract routing defaults and direct exceptions sections
    routing_defaults = {}
    direct_exceptions = {}

    return {
        "version": 1,
        "triggers": triggers,
        "routing_defaults": routing_defaults,
        "direct_exceptions": direct_exceptions,
    }


def get_trigger_spec(manifest: dict, trigger_type: str) -> dict | None:
    """Get the full spec for a trigger type."""
    return manifest.get("triggers", {}).get(trigger_type)


# ─────────────────────────────────────────────
# Target Resolution
# ─────────────────────────────────────────────

def resolve_targets(trigger_spec: dict, explicit_target: str | None = None,
                    registry: dict | None = None) -> list[str]:
    """Resolve target entity IDs for a trigger.

    Priority:
      1. Explicit target override (for dynamic resolution / swarm dispatch)
      2. Static entities from manifest
      3. Empty list (caller must provide)
    """
    if explicit_target:
        return [explicit_target]

    targets = trigger_spec.get("targets", {})
    resolution = targets.get("resolution", "static")

    if resolution == "static":
        entities = targets.get("entities", [])
        if isinstance(entities, list):
            return [e for e in entities if e]
        return []

    elif resolution == "dynamic":
        # Dynamic resolution: entities list may be empty.
        # Caller must provide --target for dynamic triggers.
        entities = targets.get("entities", [])
        if isinstance(entities, list) and entities:
            return [e for e in entities if e]
        return []

    return []


def resolve_escalation_targets(trigger_spec: dict, condition: dict | None = None) -> list[str]:
    """Resolve escalation targets if escalation condition is met."""
    targets = trigger_spec.get("targets", {})
    esc_condition = targets.get("escalation_condition", "")
    esc_entities = targets.get("escalation_entities", [])

    if not esc_entities or not esc_condition:
        return []

    # Simple condition evaluation for known patterns
    if condition:
        # e.g., "signal.band == PRIMITIVE"
        if "PRIMITIVE" in esc_condition and condition.get("band") == "PRIMITIVE":
            return esc_entities

    return []


# ─────────────────────────────────────────────
# Routing Policy Application
# ─────────────────────────────────────────────

def extract_routing_policy(trigger_spec: dict) -> dict:
    """Extract routing policy from a trigger spec."""
    rp = trigger_spec.get("routing_policy", {})
    return {
        "priority": rp.get("priority", "normal"),
        "delivery_mode": rp.get("delivery_mode"),
        "idempotency_key_template": rp.get("idempotency_key", ""),
        "dedupe_policy": rp.get("dedupe_policy", "latest_wins"),
    }


def compute_idempotency_key(template: str, context: dict) -> str | None:
    """Compute idempotency key from template + context values.

    Templates use {field} placeholders:
      "mandate_{tic}_{session_id}" -> "mandate_52_abc123"
    """
    if not template:
        return None
    key = template
    for field, value in context.items():
        key = key.replace(f"{{{field}}}", str(value) if value else "none")
    # Replace any remaining unresolved placeholders
    import re
    key = re.sub(r"\{[^}]+\}", "none", key)
    return key


def extract_receipt_required(trigger_spec: dict) -> bool:
    """Whether this trigger requires receipt on delivery."""
    return trigger_spec.get("receipt_required", False)


# ─────────────────────────────────────────────
# Route (core)
# ─────────────────────────────────────────────

def route_trigger(
    zone_root: str,
    trigger_type: str,
    source_event: str | None,
    producer: str | None,
    source_tic: int,
    subject: str,
    body: any,
    explicit_target: str | None = None,
    session_id: str | None = None,
    sender_id: str | None = None,
    priority_override: str | None = None,
    expires_at_tic: int | None = None,
    escalation_condition: dict | None = None,
    dry_run: bool = False,
    agent_id: str = "",
    agent_type: str = "",
) -> dict:
    """Route a trigger through the manifest to inbox delivery.

    Returns result dict with delivery outcomes per target.
    """
    ticzone = load_ticzone(zone_root)
    audit_root = audit_logs_path(zone_root, ticzone)
    manifest = load_manifest(zone_root)
    registry = inbox_envelope.load_actor_registry(zone_root)

    # 1. Look up trigger type in manifest
    trigger_spec = get_trigger_spec(manifest, trigger_type)
    if trigger_spec is None:
        return {"status": "rejected",
                "reason": f"Unknown trigger type: {trigger_type}",
                "trigger_type": trigger_type}

    # 2. Resolve targets
    targets = resolve_targets(trigger_spec, explicit_target, registry)
    esc_targets = resolve_escalation_targets(trigger_spec, escalation_condition)
    all_targets = list(dict.fromkeys(targets + esc_targets))  # dedup preserving order

    if not all_targets:
        return {"status": "rejected",
                "reason": f"No targets resolved for {trigger_type}. "
                          "Dynamic triggers require --target.",
                "trigger_type": trigger_type}

    # 3. Extract routing policy
    policy = extract_routing_policy(trigger_spec)
    priority = priority_override or policy["priority"]
    dedupe = policy["dedupe_policy"]

    # 4. Compute idempotency key
    idem_context = {
        "tic": source_tic,
        "session_id": session_id or "none",
        "trigger_type": trigger_type,
    }
    # Extract additional context from body if dict
    if isinstance(body, dict):
        for k in ("mandate_id", "plan_id", "handoff_id", "signal_id",
                   "arena_id", "report_id", "swarm_id", "task_id",
                   "crossing_tic", "cadence_mode"):
            if k in body:
                idem_context[k] = body[k]
    idem_key = compute_idempotency_key(policy["idempotency_key_template"], idem_context)

    # 5. Determine sender
    if sender_id is None:
        # Infer from source_event
        se = trigger_spec.get("source_event", {})
        prod = se.get("producer", producer or "trigger-router")
        # Map common producers to entity IDs
        sender_map = {
            "session-restore.sh": "ent_homeskillet",
            "cgg-gate.sh": "ent_homeskillet",
            "/cadence skill (operator-invoked)": "ent_skill_cadence",
            "arena-pressure-ingest.py": "ent_mogul",
            "cadence-ops.py": "ent_skill_cadence",
        }
        sender_id = sender_map.get(prod, "ent_homeskillet")

    # 6. Dry run check
    if dry_run:
        return {
            "status": "dry_run",
            "trigger_type": trigger_type,
            "targets": all_targets,
            "priority": priority,
            "dedupe_policy": dedupe,
            "idempotency_key": idem_key,
            "sender": sender_id,
            "delivery_mode": policy["delivery_mode"],
            "receipt_required": extract_receipt_required(trigger_spec),
            "subject": subject,
        }

    # 7. Deliver to each target
    results = []
    for target_id in all_targets:
        # Verify standing
        ok, reason = inbox_envelope.verify_standing(registry, target_id)
        if not ok:
            results.append({"target": target_id, "status": "rejected", "reason": reason})
            continue

        ibox = inbox_envelope.inbox_root(audit_root, target_id)

        envelope = inbox_envelope.build_envelope(
            sender_id=sender_id,
            recipient_id=target_id,
            envelope_type=trigger_type,
            subject=subject,
            body=body,
            source_tic=source_tic,
            priority=priority,
            category="directive",
            delivery_mode=policy["delivery_mode"],
            source_event=source_event,
            producer=producer,
            zone_root=zone_root,
            session_id=session_id,
            idempotency_key=idem_key,
            expires_at_tic=expires_at_tic,
        )

        result = inbox_envelope.write_envelope(
            envelope, ibox,
            idempotency_key=idem_key,
            dedupe_policy=dedupe,
            manifest=manifest,
        )
        result["target"] = target_id
        results.append(result)

    # 8. Log routing decision (agent identity threaded from upstream hook
    # payload — federation KI: bounded-delegation default masking).
    _log_routing(audit_root, {
        "trigger_type": trigger_type,
        "source_event": source_event,
        "producer": producer,
        "source_tic": source_tic,
        "targets": all_targets,
        "priority": priority,
        "idempotency_key": idem_key,
        "dedupe_policy": dedupe,
        "results": [{"target": r["target"], "status": r["status"]} for r in results],
        "agent_id": agent_id or "",
        "agent_type": agent_type or "",
    })

    delivered = [r for r in results if r.get("status") == "delivered"]
    return {
        "status": "routed",
        "trigger_type": trigger_type,
        "targets_resolved": len(all_targets),
        "delivered": len(delivered),
        "results": results,
    }


def _log_routing(audit_root: str, entry: dict) -> None:
    """Append routing decision to trigger-router audit log."""
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    log_dir = os.path.join(audit_root, "services")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "trigger-router.jsonl")
    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(log_file, entry)
    except ImportError:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def cmd_route(args):
    zr = args.zone_root or resolve_zone_root()

    body = args.body
    if body:
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            pass
    if args.body_file:
        body = json.loads(Path(args.body_file).read_text(encoding="utf-8"))

    esc_condition = None
    if args.escalation_band:
        esc_condition = {"band": args.escalation_band}

    result = route_trigger(
        zone_root=zr,
        trigger_type=args.trigger_type,
        source_event=args.source_event,
        producer=args.producer,
        source_tic=args.source_tic,
        subject=args.subject or f"{args.trigger_type} — tic {args.source_tic}",
        body=body,
        explicit_target=args.target,
        session_id=args.session_id,
        sender_id=args.sender,
        priority_override=args.priority,
        expires_at_tic=args.expires_at_tic,
        escalation_condition=esc_condition,
        dry_run=args.dry_run,
        agent_id=getattr(args, 'agent_id', ''),
        agent_type=getattr(args, 'agent_type', ''),
    )
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] in ("routed", "dry_run") else 1)


def cmd_list(args):
    zr = args.zone_root or resolve_zone_root()
    manifest = load_manifest(zr)
    triggers = manifest.get("triggers", {})
    for name, spec in triggers.items():
        desc = spec.get("description", "") if isinstance(spec, dict) else ""
        print(f"  {name:30s} {desc}")


def cmd_show(args):
    zr = args.zone_root or resolve_zone_root()
    manifest = load_manifest(zr)
    spec = get_trigger_spec(manifest, args.trigger_type)
    if spec is None:
        print(f"Unknown trigger type: {args.trigger_type}")
        sys.exit(1)
    if isinstance(spec, dict):
        print(json.dumps(spec, indent=2, default=str))
    else:
        print(f"{args.trigger_type}: {spec}")


def _die(msg: str):
    print(json.dumps({"status": "error", "reason": msg}), file=sys.stderr)
    sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="Trigger router — single-lane entity activation")
    p.add_argument("--zone-root", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    # route
    r = sub.add_parser("route", help="Route a trigger to target inbox(es)")
    r.add_argument("--trigger-type", required=True, help="Type from trigger-manifest.yaml")
    r.add_argument("--source-event", default=None, help="Hook event name")
    r.add_argument("--producer", default=None, help="Script/hook that produced the event")
    r.add_argument("--source-tic", type=int, required=True)
    r.add_argument("--subject", default=None)
    r.add_argument("--body", default=None)
    r.add_argument("--body-file", default=None)
    r.add_argument("--target", default=None, help="Explicit target (overrides manifest)")
    r.add_argument("--sender", default=None, help="Sender entity_id (auto-resolved if omitted)")
    r.add_argument("--session-id", default=None)
    r.add_argument("--priority", default=None, help="Override manifest priority")
    r.add_argument("--expires-at-tic", type=int, default=None)
    r.add_argument("--escalation-band", default=None, help="Band for escalation check")
    r.add_argument("--agent-id", default="", help="Hook payload agent_id (Claude Code 2.1.69+); empty when orchestrator-fired")
    r.add_argument("--agent-type", default="", help="Hook payload agent_type (Claude Code 2.1.69+); empty when orchestrator-fired")
    r.add_argument("--dry-run", action="store_true", help="Validate without writing")
    r.set_defaults(func=cmd_route)

    # list
    l = sub.add_parser("list", help="List all trigger types")
    l.set_defaults(func=cmd_list)

    # show
    s = sub.add_parser("show", help="Show routing policy for a trigger type")
    s.add_argument("--trigger-type", required=True)
    s.set_defaults(func=cmd_show)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
