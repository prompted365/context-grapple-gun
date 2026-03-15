#!/usr/bin/env python3
"""inbox-envelope.py — Envelope handler for the agent inbox capability surface.

Contract-enforcing, atomic, idempotent, mailbox-state aware.
Not the router — the delivery contract.

Responsibilities:
  validate, normalize, dedupe, write atomically, initialize lifecycle fields,
  emit receipt skeleton when required.

Does NOT: routing decisions, manifest interpretation beyond schema lookup,
hook rewiring.

Phase 5 additions: attention-debt signal emission (detect_stale -> emit_attention_debt_signals),
stale-check CLI command (scans all entity inboxes), scan_all_inboxes helper.

Filename shape:
  WAIT_<priority>_<trigger-type>_t<tic>_<short-id>.json
  ACTIVE_<priority>_<trigger-type>_t<tic>_<short-id>.json
  DONE_<priority>_<trigger-type>_t<tic>_<short-id>.json
  DEFER_<priority>_<trigger-type>_t<tic>_<short-id>.json
  NACK_<priority>_<trigger-type>_t<tic>_<short-id>.json

Usage:
  python3 inbox-envelope.py write --recipient ent_mogul --type mogul.mandate \\
      --sender ent_homeskillet --subject "Mandate tic 52" --source-tic 52 \\
      --body '{"mandate_id":"..."}' --source-event SessionStart \\
      --producer session-restore.sh

  python3 inbox-envelope.py claim --entity ent_mogul --message-id ab12cd34
  python3 inbox-envelope.py complete --entity ent_mogul --message-id ab12cd34
  python3 inbox-envelope.py defer --entity ent_mogul --message-id ab12cd34 --until-tic 53
  python3 inbox-envelope.py nack --entity ent_mogul --message-id ab12cd34 --reason "..."
  python3 inbox-envelope.py scan --entity ent_mogul [--format json|injection] [--current-tic 52]
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, audit_logs_path, load_ticzone

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

ENVELOPE_VERSION = "1.0"

VALID_PRIORITIES = ("low", "normal", "high", "urgent")
VALID_CATEGORIES = ("work_item", "directive", "report", "query", "delivery_receipt")
VALID_TRUST_LEVELS = ("operator", "self_generated", "federated", "external", "unknown")

# Minimal legal state machine (council-scoped)
#   WAIT -> ACTIVE -> DONE
#   WAIT -> DEFER
#   WAIT -> NACK
#   ACTIVE -> DONE
#   ACTIVE -> DEFER
STATES = ("WAIT", "ACTIVE", "DONE", "DEFER", "NACK")
TERMINAL_STATES = ("DONE", "NACK")
STATE_TRANSITIONS = {
    "WAIT":   {"ACTIVE", "DEFER", "NACK"},
    "ACTIVE": {"DONE", "DEFER"},
    "DEFER":  {"WAIT"},            # resurface
}

# Channel directories
STATE_CHANNELS = {
    "WAIT":   "inbound",
    "ACTIVE": "processing",
    "DONE":   "archive",
    "DEFER":  "deferred",
    "NACK":   "archive",
}

DEDUPE_POLICIES = ("latest_wins", "first_wins", "reject_duplicate")
MINIMUM_INBOX_STANDING = {"citizen", "resident", "registered_artifact", "recognized_body"}


# ─────────────────────────────────────────────
# Trigger Manifest Loader
# ─────────────────────────────────────────────

def load_trigger_manifest(zone_root: str) -> dict:
    """Load trigger-manifest.yaml, return triggers dict. Empty on failure."""
    manifest_path = os.path.join(zone_root, "autonomous_kernel", "trigger-manifest.yaml")
    if not os.path.isfile(manifest_path):
        return {}
    try:
        import yaml
        return yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8"))
    except ImportError:
        # Fallback: basic YAML key extraction without PyYAML
        return _parse_manifest_keys(manifest_path)
    except Exception:
        return {}


def _parse_manifest_keys(path: str) -> dict:
    """Minimal manifest parser — extracts trigger type keys without PyYAML."""
    text = Path(path).read_text(encoding="utf-8")
    triggers = {}
    in_triggers = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "triggers:":
            in_triggers = True
            continue
        if in_triggers and not line.startswith(" ") and not line.startswith("#") and stripped:
            in_triggers = False
            continue
        if in_triggers and line.startswith("  ") and not line.startswith("    ") and ":" in stripped:
            key = stripped.split(":")[0].strip()
            if key and not key.startswith("#"):
                triggers[key] = True
    return {"triggers": triggers}


def validate_envelope_type(manifest: dict, envelope_type: str | None) -> tuple[bool, str]:
    """Check envelope_type exists in trigger-manifest.yaml."""
    if envelope_type is None:
        return True, "ok (no type specified)"
    triggers = manifest.get("triggers", {})
    if envelope_type in triggers:
        return True, "ok"
    return False, f"Unknown envelope_type '{envelope_type}' — not in trigger-manifest.yaml"


# ─────────────────────────────────────────────
# Actor Registry
# ─────────────────────────────────────────────

def load_actor_registry(zone_root: str) -> dict:
    """Load actor-registry.json keyed by entity_id."""
    path = os.path.join(zone_root, "autonomous_kernel", "actor-registry.json")
    if not os.path.isfile(path):
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return {a["entity_id"]: a for a in data.get("actors", [])}
    except (json.JSONDecodeError, OSError, KeyError):
        return {}


def verify_standing(registry: dict, entity_id: str) -> tuple[bool, str]:
    """Verify entity has standing for inbox receipt."""
    actor = registry.get(entity_id)
    if actor is None:
        return False, f"Entity {entity_id} not in actor-registry"
    if actor.get("standing", "") not in MINIMUM_INBOX_STANDING:
        return False, f"Entity {entity_id} standing '{actor.get('standing')}' insufficient"
    if actor.get("status") != "active":
        return False, f"Entity {entity_id} not active"
    return True, "ok"


# ─────────────────────────────────────────────
# Inbox Paths
# ─────────────────────────────────────────────

def inbox_root(audit_root: str, entity_id: str) -> str:
    return os.path.join(audit_root, "agent-mailboxes", entity_id)


def ensure_inbox(inbox_path: str) -> None:
    for d in ("inbound", "processing", "archive", "deferred", "indexes"):
        os.makedirs(os.path.join(inbox_path, d), exist_ok=True)


def envelope_filename(state: str, priority: str, envelope_type: str,
                      tic: int, short_id: str) -> str:
    """Deterministic, sortable filename.
    Example: WAIT_normal_mogul.mandate_t51_ab12cd34.json
    """
    safe_type = (envelope_type or "generic").replace("/", "-")
    return f"{state}_{priority}_{safe_type}_t{tic}_{short_id}.json"


def envelope_filepath(inbox_path: str, state: str, filename: str) -> str:
    channel = STATE_CHANNELS[state]
    return os.path.join(inbox_path, channel, filename)


def find_envelope_file(inbox_path: str, message_id: str) -> tuple[str | None, str | None, dict | None]:
    """Find an envelope by message_id across all channels.
    Returns (filepath, current_state, envelope_data) or (None, None, None).
    """
    for state, channel in STATE_CHANNELS.items():
        channel_dir = os.path.join(inbox_path, channel)
        if not os.path.isdir(channel_dir):
            continue
        for fname in os.listdir(channel_dir):
            if not fname.endswith(".json") or fname.startswith("."):
                continue
            if message_id in fname:
                fpath = os.path.join(channel_dir, fname)
                try:
                    data = json.loads(Path(fpath).read_text(encoding="utf-8"))
                    if data.get("message_id") == message_id:
                        return fpath, state, data
                except (json.JSONDecodeError, OSError):
                    continue
    return None, None, None


# ─────────────────────────────────────────────
# Idempotency
# ─────────────────────────────────────────────

def _registry_path(inbox_path: str) -> str:
    return os.path.join(inbox_path, "indexes", "inbox-registry.json")


def _load_registry(inbox_path: str) -> dict:
    path = _registry_path(inbox_path)
    default = {"messages": {}, "idempotency_index": {}}
    if not os.path.isfile(path):
        return default
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data.setdefault("messages", {})
        data.setdefault("idempotency_index", {})
        return data
    except (json.JSONDecodeError, OSError):
        return default


def _save_registry(inbox_path: str, registry: dict) -> None:
    path = _registry_path(inbox_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        from lib.atomic_append import atomic_write_json
        atomic_write_json(path, registry)
    except ImportError:
        Path(path).write_text(json.dumps(registry, indent=2), encoding="utf-8")


def check_idempotency(inbox_path: str, key: str, policy: str) -> tuple[str, str | None]:
    """Returns (action, existing_id). action: deliver|supersede|skip|reject."""
    if not key:
        return "deliver", None
    registry = _load_registry(inbox_path)
    existing = registry.get("idempotency_index", {}).get(key)
    if existing is None:
        return "deliver", None
    eid = existing.get("message_id")
    state = existing.get("state", "WAIT")
    if state in TERMINAL_STATES:
        return "deliver", None
    if policy == "latest_wins":
        return "supersede", eid
    elif policy == "first_wins":
        return "skip", eid
    elif policy == "reject_duplicate":
        return "reject", eid
    return "deliver", None


# ─────────────────────────────────────────────
# Envelope Build
# ─────────────────────────────────────────────

def build_envelope(
    sender_id: str,
    recipient_id: str,
    envelope_type: str | None,
    subject: str,
    body: any,
    source_tic: int,
    priority: str = "normal",
    category: str = "directive",
    trust_level: str = "self_generated",
    delivery_mode: str | None = None,
    source_event: str | None = None,
    producer: str | None = None,
    zone_root: str | None = None,
    session_id: str | None = None,
    idempotency_key: str | None = None,
    expires_at_tic: int | None = None,
    defer_until_tic: int | None = None,
    reminder_tic: int | None = None,
    reply_to: str | None = None,
    thread_id: str | None = None,
) -> dict:
    """Build a complete InboxEnvelope with lifecycle.state."""
    short_id = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()

    return {
        "message_id": short_id,
        "envelope_version": ENVELOPE_VERSION,
        "idempotency_key": idempotency_key,
        "sender": {
            "entity_id": sender_id,
        },
        "recipient": {
            "entity_id": recipient_id,
        },
        "routing": {
            "priority": priority,
            "category": category,
            "delivery_mode": delivery_mode,
            "trust_level": trust_level,
            "reply_to": reply_to,
            "thread_id": thread_id,
            "forward_chain": [],
        },
        "content": {
            "subject": subject,
            "envelope_type": envelope_type,
            "body": body,
            "artifact_refs": [],
        },
        "lifecycle": {
            "state": "WAIT",
            "source_tic": source_tic,
            "state_entered_at_tic": source_tic,
            "created_at": now,
            "expires_at_tic": expires_at_tic,
            "defer_until_tic": defer_until_tic,
            "reminder_tic": reminder_tic,
        },
        "provenance": {
            "source_event": source_event,
            "producer": producer,
            "zone_root": zone_root,
            "session_id": session_id,
        },
    }


def validate_envelope(envelope: dict) -> tuple[bool, str]:
    """Validate required fields."""
    for field in ("message_id", "sender", "recipient", "routing", "content", "lifecycle", "provenance"):
        if field not in envelope:
            return False, f"Missing: {field}"
    if not envelope.get("sender", {}).get("entity_id"):
        return False, "Missing sender.entity_id"
    if not envelope.get("recipient", {}).get("entity_id"):
        return False, "Missing recipient.entity_id"
    if envelope.get("lifecycle", {}).get("source_tic") is None:
        return False, "Missing lifecycle.source_tic"
    p = envelope.get("routing", {}).get("priority", "")
    if p not in VALID_PRIORITIES:
        return False, f"Invalid priority: {p}"
    return True, "ok"


# ─────────────────────────────────────────────
# Write (atomic)
# ─────────────────────────────────────────────

def write_envelope(
    envelope: dict,
    inbox_path: str,
    idempotency_key: str | None = None,
    dedupe_policy: str = "latest_wins",
    manifest: dict | None = None,
) -> dict:
    """Validate, dedupe, write atomically. Returns result dict."""
    # 1. Validate envelope
    valid, reason = validate_envelope(envelope)
    if not valid:
        return {"status": "rejected", "reason": reason}

    # 2. Validate envelope_type against manifest
    if manifest:
        et = envelope.get("content", {}).get("envelope_type")
        valid, reason = validate_envelope_type(manifest, et)
        if not valid:
            return {"status": "rejected", "reason": reason}

    # 3. Ensure inbox structure
    ensure_inbox(inbox_path)

    msg_id = envelope["message_id"]
    priority = envelope["routing"]["priority"]
    etype = envelope.get("content", {}).get("envelope_type")
    tic = envelope["lifecycle"]["source_tic"]

    # 4. Idempotency check
    if idempotency_key:
        envelope["idempotency_key"] = idempotency_key
        action, existing_id = check_idempotency(inbox_path, idempotency_key, dedupe_policy)
        if action == "skip":
            return {"status": "skipped", "reason": f"first_wins: {existing_id}",
                    "existing_message_id": existing_id}
        elif action == "reject":
            return {"status": "rejected", "reason": f"duplicate rejected: {existing_id}",
                    "existing_message_id": existing_id}
        elif action == "supersede" and existing_id:
            _nack_existing(inbox_path, existing_id, f"Superseded by {msg_id}")

    # 5. Atomic write
    fname = envelope_filename("WAIT", priority, etype, tic, msg_id)
    fpath = envelope_filepath(inbox_path, "WAIT", fname)
    try:
        from lib.atomic_append import atomic_write_json
        atomic_write_json(fpath, envelope)
    except ImportError:
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        Path(fpath).write_text(json.dumps(envelope, indent=2), encoding="utf-8")

    # 6. Update registry
    registry = _load_registry(inbox_path)
    registry["messages"][msg_id] = {
        "state": "WAIT",
        "filename": fname,
        "subject": envelope["content"]["subject"],
        "sender": envelope["sender"]["entity_id"],
        "priority": priority,
        "envelope_type": etype,
        "source_tic": tic,
        "state_entered_at_tic": tic,
    }
    if idempotency_key:
        registry["idempotency_index"][idempotency_key] = {
            "message_id": msg_id, "state": "WAIT",
        }
    _save_registry(inbox_path, registry)

    # 7. Log event
    _log_event(inbox_path, {
        "message_id": msg_id,
        "from_state": None,
        "to_state": "WAIT",
        "actor": envelope["sender"]["entity_id"],
        "tic": tic,
        "reason": f"Delivered: {envelope['content']['subject']}",
    })

    return {"status": "delivered", "message_id": msg_id, "filename": fname,
            "path": fpath}


def _nack_existing(inbox_path: str, msg_id: str, reason: str) -> None:
    """NACK an existing message (superseded by dedupe)."""
    fpath, state, data = find_envelope_file(inbox_path, msg_id)
    if not fpath or not data:
        return
    tic = data.get("lifecycle", {}).get("source_tic", 0)
    priority = data.get("routing", {}).get("priority", "normal")
    etype = data.get("content", {}).get("envelope_type")

    # Move to archive as NACK
    data["lifecycle"]["state"] = "NACK"
    nack_fname = envelope_filename("NACK", priority, etype, tic, msg_id)
    nack_path = envelope_filepath(inbox_path, "NACK", nack_fname)
    os.makedirs(os.path.dirname(nack_path), exist_ok=True)
    Path(nack_path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Remove old file
    if os.path.isfile(fpath):
        os.remove(fpath)

    # Update registry
    registry = _load_registry(inbox_path)
    if msg_id in registry["messages"]:
        registry["messages"][msg_id]["state"] = "NACK"
        registry["messages"][msg_id]["filename"] = nack_fname
    _save_registry(inbox_path, registry)

    # Receipt
    _log_receipt(inbox_path, _build_receipt(msg_id, "NACK", reason))
    _log_event(inbox_path, {
        "message_id": msg_id, "from_state": state, "to_state": "NACK",
        "actor": "system", "tic": tic, "reason": reason,
    })


# ─────────────────────────────────────────────
# State Transitions: claim, complete, defer, nack
# ─────────────────────────────────────────────

def _transition(inbox_path: str, message_id: str, to_state: str,
                actor_id: str, current_tic: int, reason: str | None = None,
                result_ref: str | None = None, reminder_tic: int | None = None) -> dict:
    """Core state transition engine."""
    if to_state not in STATES:
        return {"status": "error", "reason": f"Invalid state: {to_state}"}

    fpath, from_state, data = find_envelope_file(inbox_path, message_id)
    if not fpath or not data:
        return {"status": "error", "reason": f"Message {message_id} not found"}

    valid_targets = STATE_TRANSITIONS.get(from_state, set())
    if to_state not in valid_targets:
        return {"status": "error",
                "reason": f"Invalid: {from_state} -> {to_state} (valid: {valid_targets})"}

    # Update envelope
    data["lifecycle"]["state"] = to_state
    data["lifecycle"]["state_entered_at_tic"] = current_tic
    if to_state == "DEFER" and reminder_tic:
        data["lifecycle"]["reminder_tic"] = reminder_tic

    priority = data.get("routing", {}).get("priority", "normal")
    etype = data.get("content", {}).get("envelope_type")
    tic = data["lifecycle"]["source_tic"]

    # Write new file
    new_fname = envelope_filename(to_state, priority, etype, tic, message_id)
    new_path = envelope_filepath(inbox_path, to_state, new_fname)
    os.makedirs(os.path.dirname(new_path), exist_ok=True)
    Path(new_path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Remove old
    if os.path.isfile(fpath) and fpath != new_path:
        os.remove(fpath)

    # Update registry
    registry = _load_registry(inbox_path)
    if message_id in registry["messages"]:
        registry["messages"][message_id]["state"] = to_state
        registry["messages"][message_id]["filename"] = new_fname
        registry["messages"][message_id]["state_entered_at_tic"] = current_tic
    for idx_entry in registry.get("idempotency_index", {}).values():
        if idx_entry.get("message_id") == message_id:
            idx_entry["state"] = to_state
    _save_registry(inbox_path, registry)

    # Log event
    _log_event(inbox_path, {
        "message_id": message_id, "from_state": from_state, "to_state": to_state,
        "actor": actor_id, "tic": current_tic,
        "reason": reason, "result_ref": result_ref,
    })

    # Receipt on terminal
    receipt = None
    if to_state in TERMINAL_STATES:
        rtype = "ACK" if to_state == "DONE" else "NACK"
        receipt = _build_receipt(message_id, rtype, reason, result_ref, current_tic)
        _log_receipt(inbox_path, receipt)

    return {"status": "ok", "from": from_state, "to": to_state,
            "message_id": message_id, "filename": new_fname, "receipt": receipt}


def claim_envelope(inbox_path: str, message_id: str, actor_id: str, current_tic: int) -> dict:
    return _transition(inbox_path, message_id, "ACTIVE", actor_id, current_tic, "Claimed")

def complete_envelope(inbox_path: str, message_id: str, actor_id: str,
                      current_tic: int, result_ref: str | None = None) -> dict:
    return _transition(inbox_path, message_id, "DONE", actor_id, current_tic,
                       "Completed", result_ref=result_ref)

def defer_envelope(inbox_path: str, message_id: str, actor_id: str,
                   current_tic: int, reason: str | None = None,
                   until_tic: int | None = None) -> dict:
    return _transition(inbox_path, message_id, "DEFER", actor_id, current_tic,
                       reason or "Deferred", reminder_tic=until_tic)

def nack_envelope(inbox_path: str, message_id: str, actor_id: str,
                  current_tic: int, reason: str = "Rejected") -> dict:
    return _transition(inbox_path, message_id, "NACK", actor_id, current_tic, reason)


# ─────────────────────────────────────────────
# Inbox Scan
# ─────────────────────────────────────────────

def read_inbox(inbox_path: str, channel: str = "inbound") -> list:
    """Read all envelopes in a channel. Returns list of envelope dicts."""
    channel_dir = os.path.join(inbox_path, channel)
    if not os.path.isdir(channel_dir):
        return []
    envelopes = []
    for fname in sorted(os.listdir(channel_dir)):
        if not fname.endswith(".json") or fname.startswith("."):
            continue
        try:
            data = json.loads(Path(os.path.join(channel_dir, fname)).read_text(encoding="utf-8"))
            data["_filename"] = fname
            envelopes.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return envelopes


def scan_inbox(inbox_path: str) -> dict:
    """Full inbox scan. Returns counts + messages by state."""
    registry = _load_registry(inbox_path)
    counts = {s: 0 for s in STATES}
    by_state = {s: [] for s in STATES}

    for msg_id, entry in registry.get("messages", {}).items():
        state = entry.get("state", "WAIT")
        counts[state] = counts.get(state, 0) + 1
        if state not in TERMINAL_STATES:
            by_state[state].append({
                "message_id": msg_id,
                "subject": entry.get("subject", ""),
                "sender": entry.get("sender", ""),
                "priority": entry.get("priority", "normal"),
                "envelope_type": entry.get("envelope_type"),
                "source_tic": entry.get("source_tic"),
                "state_entered_at_tic": entry.get("state_entered_at_tic"),
            })

    # Sort: urgent first, then by tic
    pord = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    for msgs in by_state.values():
        msgs.sort(key=lambda m: (pord.get(m["priority"], 2), m.get("source_tic", 0)))

    return {"counts": counts, "messages": by_state}


def format_injection(entity_id: str, scan_result: dict, stale: list | None = None) -> str:
    """Format for Layer 2 prompt injection."""
    c = scan_result["counts"]
    msgs = scan_result["messages"]
    waiting = c.get("WAIT", 0)
    active = c.get("ACTIVE", 0)
    deferred = c.get("DEFER", 0)

    if waiting == 0 and active == 0 and deferred == 0 and not stale:
        return f"[INBOX: {entity_id}] Empty."

    lines = [f"[INBOX: {entity_id}] {waiting} new, {active} active, {deferred} deferred."]

    for msg in msgs.get("WAIT", []):
        p = msg["priority"]
        if p in ("high", "urgent"):
            lines.append(f"  - [{p.upper()}] {msg['subject']} (from: {msg['sender']}, tic {msg.get('source_tic', '?')})")

    for msg in msgs.get("ACTIVE", []):
        lines.append(f"  - [ACTIVE] {msg['subject']} (tic {msg.get('state_entered_at_tic', '?')})")

    if stale:
        for item in stale:
            lines.append(f"  - [ATTENTION] {item.get('subject','')} — stale {item.get('tics_in_state',0)} tics in {item.get('state','?')}")

    return "\n".join(lines)


def detect_stale(inbox_path: str, current_tic: int,
                 thresholds: dict | None = None) -> list:
    """Detect items stale beyond threshold. Returns signal-ready dicts."""
    if thresholds is None:
        thresholds = {"WAIT": 3, "ACTIVE": 3}
    registry = _load_registry(inbox_path)
    stale = []
    for msg_id, entry in registry.get("messages", {}).items():
        state = entry.get("state", "WAIT")
        if state in TERMINAL_STATES:
            continue
        entered = entry.get("state_entered_at_tic")
        if entered is None:
            continue
        age = current_tic - entered
        threshold = thresholds.get(state)
        if threshold and age > threshold:
            vol_map = {"WAIT": 30, "ACTIVE": 50, "DEFER": 35}
            stale.append({
                "message_id": msg_id, "state": state,
                "tics_in_state": age, "stale_since_tic": entered,
                "subject": entry.get("subject", ""),
                "signal_kind": "TENSION", "signal_band": "COGNITIVE",
                "volume": vol_map.get(state, 40),
                "reason": f"Stale in {state} for {age} tics (threshold: {threshold})",
            })
    return stale


# ─────────────────────────────────────────────
# Attention-Debt Signal Emission (Phase 5)
# ─────────────────────────────────────────────

def emit_attention_debt_signals(zone_root: str, entity_id: str,
                                stale_items: list, current_tic: int) -> list:
    """Emit attention-debt signals to audit-logs/signals/ for stale inbox items.

    Each stale item becomes one signal entry in YYYY-MM-DD.jsonl.
    Idempotent: signal IDs are deterministic (entity + message_id + state).
    Dedup: skips emission if a signal with the same ID already exists in today's file.
    Returns list of emitted signal dicts.
    """
    if not stale_items:
        return []

    tz = load_ticzone(zone_root)
    signal_dir = os.path.join(audit_logs_path(zone_root, tz), "signals")
    os.makedirs(signal_dir, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    signal_file = os.path.join(signal_dir, f"{today}.jsonl")
    now = datetime.now(timezone.utc).isoformat()

    # Build set of signal IDs already emitted today to prevent duplicates
    existing_ids: set = set()
    if os.path.isfile(signal_file):
        try:
            with open(signal_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        existing_ids.add(json.loads(line).get("id", ""))
                    except (json.JSONDecodeError, KeyError):
                        pass
        except OSError:
            pass

    emitted = []
    for item in stale_items:
        msg_id = item["message_id"]
        state = item["state"]
        signal_id = f"sig_inbox_{entity_id}_{msg_id}_{state.lower()}"

        # Skip if already emitted today
        if signal_id in existing_ids:
            continue

        signal = {
            "id": signal_id,
            "type": "signal",
            "status": "active",
            "band": item.get("signal_band", "COGNITIVE"),
            "volume": item.get("volume", 40),
            "source": "inbox_attention_debt",
            "target_entity": entity_id,
            "tic": current_tic,
            "payload": {
                "inbox_entity": entity_id,
                "message_id": msg_id,
                "current_state": state,
                "stale_since_tic": item.get("stale_since_tic"),
                "tics_in_state": item.get("tics_in_state"),
                "subject": item.get("subject", ""),
                "signal_kind": item.get("signal_kind", "TENSION"),
            },
            "reason": item.get("reason", ""),
            "created_at": now,
        }
        try:
            from lib.atomic_append import atomic_append_jsonl
            atomic_append_jsonl(signal_file, signal)
        except ImportError:
            with open(signal_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(signal, separators=(",", ":")) + "\n")
        existing_ids.add(signal_id)
        emitted.append(signal)

    return emitted


def scan_all_inboxes(audit_root: str, current_tic: int,
                     thresholds: dict | None = None) -> dict:
    """Scan all entity inboxes for stale items. Returns {entity_id: [stale_items]}."""
    mailbox_dir = os.path.join(audit_root, "agent-mailboxes")
    if not os.path.isdir(mailbox_dir):
        return {}
    results = {}
    for entity_dir in sorted(os.listdir(mailbox_dir)):
        if not entity_dir.startswith("ent_"):
            continue
        ibox = os.path.join(mailbox_dir, entity_dir)
        if not os.path.isdir(ibox):
            continue
        stale = detect_stale(ibox, current_tic, thresholds)
        if stale:
            results[entity_dir] = stale
    return results


# ─────────────────────────────────────────────
# Receipts & Events
# ─────────────────────────────────────────────

def _build_receipt(message_id: str, receipt_type: str, notes: str | None = None,
                   result_ref: str | None = None, completed_at_tic: int | None = None) -> dict:
    return {
        "receipt_id": uuid.uuid4().hex[:8],
        "message_id": message_id,
        "receipt_type": receipt_type,
        "result_ref": result_ref,
        "completed_at_tic": completed_at_tic,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }


def _log_event(inbox_path: str, event: dict) -> None:
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    path = os.path.join(inbox_path, "indexes", "events.jsonl")
    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(path, event)
    except ImportError:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")


def _log_receipt(inbox_path: str, receipt: dict) -> None:
    path = os.path.join(inbox_path, "indexes", "receipts.jsonl")
    try:
        from lib.atomic_append import atomic_append_jsonl
        atomic_append_jsonl(path, receipt)
    except ImportError:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(receipt, separators=(",", ":")) + "\n")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def _resolve(args) -> tuple[str, str, dict, dict]:
    """Common resolution: zone_root, audit_root, registry, manifest."""
    zr = args.zone_root or resolve_zone_root()
    tz = load_ticzone(zr)
    ar = audit_logs_path(zr, tz)
    reg = load_actor_registry(zr)
    man = load_trigger_manifest(zr)
    return zr, ar, reg, man


def cmd_write(args):
    zr, ar, reg, man = _resolve(args)

    # Verify recipient
    ok, reason = verify_standing(reg, args.recipient)
    if not ok:
        print(json.dumps({"status": "rejected", "reason": reason}))
        sys.exit(1)

    body = args.body
    if body:
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            pass
    if args.body_file:
        body = json.loads(Path(args.body_file).read_text(encoding="utf-8"))

    ibox = inbox_root(ar, args.recipient)
    envelope = build_envelope(
        sender_id=args.sender,
        recipient_id=args.recipient,
        envelope_type=args.type,
        subject=args.subject,
        body=body,
        source_tic=args.source_tic,
        priority=args.priority or "normal",
        category=args.category or "directive",
        delivery_mode=args.delivery_mode,
        source_event=args.source_event,
        producer=args.producer,
        zone_root=zr,
        session_id=args.session_id,
        idempotency_key=args.idempotency_key,
        expires_at_tic=args.expires_at_tic,
        reminder_tic=args.reminder_tic,
    )
    result = write_envelope(envelope, ibox,
                            idempotency_key=args.idempotency_key,
                            dedupe_policy=args.dedupe_policy or "latest_wins",
                            manifest=man)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "delivered" else 1)


def cmd_claim(args):
    zr, ar, _, _ = _resolve(args)
    ibox = inbox_root(ar, args.entity)
    result = claim_envelope(ibox, args.message_id, args.actor or args.entity, args.current_tic)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "ok" else 1)


def cmd_complete(args):
    zr, ar, _, _ = _resolve(args)
    ibox = inbox_root(ar, args.entity)
    result = complete_envelope(ibox, args.message_id, args.actor or args.entity,
                               args.current_tic, args.result_ref)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "ok" else 1)


def cmd_defer(args):
    zr, ar, _, _ = _resolve(args)
    ibox = inbox_root(ar, args.entity)
    result = defer_envelope(ibox, args.message_id, args.actor or args.entity,
                            args.current_tic, args.reason, args.until_tic)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "ok" else 1)


def cmd_nack(args):
    zr, ar, _, _ = _resolve(args)
    ibox = inbox_root(ar, args.entity)
    result = nack_envelope(ibox, args.message_id, args.actor or args.entity,
                           args.current_tic, args.reason or "Rejected")
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "ok" else 1)


def cmd_scan(args):
    zr, ar, _, _ = _resolve(args)
    ibox = inbox_root(ar, args.entity)
    result = scan_inbox(ibox)
    if args.format == "injection":
        stale = detect_stale(ibox, args.current_tic) if args.current_tic else []
        print(format_injection(args.entity, result, stale))
    else:
        print(json.dumps(result, indent=2))


def cmd_stale_check(args):
    """Scan all entity inboxes for stale items and emit attention-debt signals."""
    zr, ar, _, _ = _resolve(args)
    if not args.current_tic:
        print(json.dumps({"status": "error", "reason": "--current-tic required"}))
        sys.exit(1)

    all_stale = scan_all_inboxes(ar, args.current_tic)
    total_emitted = 0

    if args.emit_signals:
        for entity_id, items in all_stale.items():
            emitted = emit_attention_debt_signals(zr, entity_id, items, args.current_tic)
            total_emitted += len(emitted)

    # Summary
    summary = {
        "status": "ok",
        "tic": args.current_tic,
        "entities_checked": len(all_stale) if all_stale else 0,
        "total_stale": sum(len(v) for v in all_stale.values()),
        "signals_emitted": total_emitted,
        "details": {eid: [{"message_id": s["message_id"], "state": s["state"],
                           "tics_in_state": s["tics_in_state"], "subject": s["subject"]}
                          for s in items]
                    for eid, items in all_stale.items()},
    }
    print(json.dumps(summary, indent=2))


def main():
    p = argparse.ArgumentParser(description="Inbox envelope handler")
    p.add_argument("--zone-root", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    # write
    w = sub.add_parser("write")
    w.add_argument("--sender", required=True)
    w.add_argument("--recipient", required=True)
    w.add_argument("--type", default=None, help="Trigger type from manifest")
    w.add_argument("--subject", required=True)
    w.add_argument("--body", default=None)
    w.add_argument("--body-file", default=None)
    w.add_argument("--source-tic", type=int, required=True)
    w.add_argument("--priority", default="normal")
    w.add_argument("--category", default="directive")
    w.add_argument("--delivery-mode", default=None)
    w.add_argument("--source-event", default=None)
    w.add_argument("--producer", default=None)
    w.add_argument("--session-id", default=None)
    w.add_argument("--idempotency-key", default=None)
    w.add_argument("--dedupe-policy", default="latest_wins")
    w.add_argument("--expires-at-tic", type=int, default=None)
    w.add_argument("--reminder-tic", type=int, default=None)
    w.set_defaults(func=cmd_write)

    # claim
    c = sub.add_parser("claim")
    c.add_argument("--entity", required=True)
    c.add_argument("--message-id", required=True)
    c.add_argument("--actor", default=None)
    c.add_argument("--current-tic", type=int, required=True)
    c.set_defaults(func=cmd_claim)

    # complete
    d = sub.add_parser("complete")
    d.add_argument("--entity", required=True)
    d.add_argument("--message-id", required=True)
    d.add_argument("--actor", default=None)
    d.add_argument("--current-tic", type=int, required=True)
    d.add_argument("--result-ref", default=None)
    d.set_defaults(func=cmd_complete)

    # defer
    e = sub.add_parser("defer")
    e.add_argument("--entity", required=True)
    e.add_argument("--message-id", required=True)
    e.add_argument("--actor", default=None)
    e.add_argument("--current-tic", type=int, required=True)
    e.add_argument("--reason", default=None)
    e.add_argument("--until-tic", type=int, default=None)
    e.set_defaults(func=cmd_defer)

    # nack
    f = sub.add_parser("nack")
    f.add_argument("--entity", required=True)
    f.add_argument("--message-id", required=True)
    f.add_argument("--actor", default=None)
    f.add_argument("--current-tic", type=int, required=True)
    f.add_argument("--reason", default=None)
    f.set_defaults(func=cmd_nack)

    # scan
    g = sub.add_parser("scan")
    g.add_argument("--entity", required=True)
    g.add_argument("--format", default="json", choices=["json", "injection"])
    g.add_argument("--current-tic", type=int, default=None)
    g.set_defaults(func=cmd_scan)

    # stale-check
    h = sub.add_parser("stale-check")
    h.add_argument("--current-tic", type=int, required=True)
    h.add_argument("--emit-signals", action="store_true", default=False,
                   help="Emit attention-debt signals for stale items")
    h.set_defaults(func=cmd_stale_check)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
