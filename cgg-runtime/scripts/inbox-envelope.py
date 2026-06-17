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
  python3 inbox-envelope.py sweep [--entity ent_mogul] --current-tic 52   # reconcile drops + resurface due reminders
  python3 inbox-envelope.py search -q "cloudflare" [--entity ent_homeskillet] [--include-terminal]

Lane authority (tic 384 consolidation):
  This is the SINGLE, SOVEREIGN mailbox-authority lane. The filesystem is the
  source of truth; inbox-registry.json is a rebuildable cache. scan/sweep/search
  read the filesystem directly, so they see flat envelopes, directory envelopes
  (WAIT_<id>/envelope.json), AND bare files an actor hand-drops into a channel
  (e.g. the Architect from his phone). The former SQLite lane (scripts/
  inbox-query.py + inbox-index-builder.py) is DEPRECATED — its useful algorithms
  (resurface, bare-file synthesis, search) were ported here onto filesystem truth.
"""

import argparse
import hashlib
import json
import os
import re
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
            if fname.startswith("."):
                continue
            entry = os.path.join(channel_dir, fname)
            # Flat envelope: a <message_id>*.json file in the channel.
            if fname.endswith(".json") and message_id in fname and os.path.isfile(entry):
                fpath = entry
            # Directory envelope (WAIT_<id>/envelope.json) — a FIRST-CLASS form that
            # scan/sweep/search already read off the filesystem (lane header). The verb
            # resolver must honor the same contract (parity fix tic 468): descend and
            # match by the envelope's OWN message_id, NOT the dir name — the dir name may
            # differ (e.g. WAIT_gk_arrival_ack_penpal_359 vs message_id gk-arrival-ack-359,
            # underscores vs hyphens), so a name substring match would silently miss it.
            elif os.path.isdir(entry) and os.path.isfile(os.path.join(entry, "envelope.json")):
                fpath = os.path.join(entry, "envelope.json")
            else:
                continue
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
    # Persist the transition reason into the envelope BODY so the file carries its
    # own truthful terminal/transition reason (not only the event log + receipt).
    # Auditors reading the archived envelope must see WHY it closed without having
    # to cross-reference the event stream. Keyed by target state so the semantics
    # are explicit: nack_reason on NACK, defer_reason on DEFER, completion_note on
    # DONE. (Added tic 312 — the cadence obligation closure needs the body to
    # state "superseded", and a NACK with no recorded reason is an opaque close.)
    if reason:
        if to_state == "NACK":
            data["lifecycle"]["nack_reason"] = reason
        elif to_state == "DEFER":
            data["lifecycle"]["defer_reason"] = reason
        elif to_state == "DONE":
            data["lifecycle"]["completion_note"] = reason

    priority = data.get("routing", {}).get("priority", "normal")
    etype = data.get("content", {}).get("envelope_type")
    # source_tic lives under lifecycle for canonical envelopes, but directory/bare
    # envelopes carry it under provenance — fall back so dir-envelopes transition.
    tic = data["lifecycle"].get("source_tic") or data.get("provenance", {}).get("source_tic") or 0

    # Write new file / relocate. A directory envelope (WAIT_<id>/envelope.json with
    # co-located artifacts) is PRESERVED AS a directory through the transition: write the
    # mutated envelope back, then move the whole dir to the target channel with the new
    # state prefix (parity with the flat-file path, but keeps the README / EMIT_* artifacts).
    new_fname = envelope_filename(to_state, priority, etype, tic, message_id)
    new_path = envelope_filepath(inbox_path, to_state, new_fname)
    os.makedirs(os.path.dirname(new_path), exist_ok=True)

    src_dir = os.path.dirname(fpath)
    from_channel_dir = os.path.join(inbox_path, STATE_CHANNELS.get(from_state, ""))
    is_dir_envelope = (os.path.basename(fpath) == "envelope.json"
                       and os.path.abspath(src_dir) != os.path.abspath(from_channel_dir))
    if is_dir_envelope:
        Path(fpath).write_text(json.dumps(data, indent=2), encoding="utf-8")
        stem = re.sub(r"^(WAIT|ACTIVE|DONE|DEFER|NACK)_", "", os.path.basename(src_dir))
        new_dirname = f"{to_state}_{stem}"
        target_channel_dir = os.path.join(inbox_path, STATE_CHANNELS[to_state])
        os.makedirs(target_channel_dir, exist_ok=True)
        new_dir_path = os.path.join(target_channel_dir, new_dirname)
        if os.path.abspath(src_dir) != os.path.abspath(new_dir_path):
            os.rename(src_dir, new_dir_path)
        new_fname = new_dirname
    else:
        Path(new_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
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


# ─────────────────────────────────────────────
# Filesystem-truth reconciliation, manual-drop tolerance, reminder resurface
# (lane consolidation, tic 384)
#
# This is the SOVEREIGN, single mailbox-authority lane: the FILESYSTEM is the
# source of truth; the JSON registry is a rebuildable cache. The deprecated
# SQLite lane (scripts/inbox-query.py + inbox-index-builder.py) is retired —
# its binary index drifted to a stale snapshot and created a read/write
# split-brain. We HARVEST its useful algorithms (resurface, bare-file
# synthesis, prefix/subdir state inference, search) onto filesystem truth; we
# do NOT restore its index-as-authority model.
#
# These helpers let scan/sweep see EVERY envelope physically present:
#   • flat envelopes       WAIT_<priority>_<type>_t<tic>_<id>.json   (this lane's native write form)
#   • directory envelopes  WAIT_<id>/envelope.json (+ README/artifacts)  (the harvested deliver form; gk's shape)
#   • bare hand-dropped files an actor (e.g. the Architect, from his phone)
#     drops straight into a channel dir without going through `write` —
#     first-class inputs, not invisible.
# and resurface due deferred reminders (DEFER -> WAIT at reminder_tic), which
# the registry-only lane never did.
# ─────────────────────────────────────────────

_PREFIX_STATE = {"WAIT": "WAIT", "ACTIVE": "ACTIVE", "DONE": "DONE",
                 "DEFER": "DEFER", "NACK": "NACK"}
_CHANNEL_STATE = {"inbound": "WAIT", "processing": "ACTIVE",
                  "deferred": "DEFER", "archive": "DONE"}
_BARE_EXTS = (".md", ".txt", ".json")  # .json handled before this as structured
_NONTERMINAL_CHANNELS = ("inbound", "processing", "deferred")
_ALL_CHANNELS = ("inbound", "processing", "deferred", "archive")


def _entity_from_inbox(inbox_path: str) -> str:
    return os.path.basename(os.path.normpath(inbox_path))


def _infer_state(envelope: dict, name: str, channel: str) -> str:
    """Best-effort state: explicit lifecycle.state -> filename prefix -> channel dir.
    Tolerates directory/hand-dropped envelopes that lack lifecycle.state (e.g. gk,
    whose lifecycle has no `state` key)."""
    st = (envelope.get("lifecycle") or {}).get("state")
    if st in STATES:
        return st
    for pfx, s in _PREFIX_STATE.items():
        if name.startswith(pfx + "_") or name == pfx:
            return s
    return _CHANNEL_STATE.get(channel, "WAIT")


def _envelope_source_tic(env: dict):
    """source_tic lives in lifecycle (flat write form) OR provenance (deliver/
    directory form). Check both so directory envelopes classify correctly."""
    life = env.get("lifecycle") or {}
    prov = env.get("provenance") or {}
    t = life.get("source_tic")
    return prov.get("source_tic") if t is None else t


def _synthesize_drop_envelope(path: Path, channel: str, entity_id: str) -> dict:
    """Minimal envelope for a hand-dropped bare file (no envelope.json).
    Stable id from path hash so re-scans dedupe. (Architect drop-spot support —
    ported from the deprecated lane's synthesize_bare_file_envelope.)"""
    name = path.name
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        mtime = None
    h = hashlib.sha256(str(path).encode()).hexdigest()[:12]
    m = re.search(r"tic[ _-]?(\d+)", name, re.IGNORECASE)
    src_tic = int(m.group(1)) if m else None
    subject = name.rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
    return {
        "message_id": f"drop_{h}",
        "envelope_version": ENVELOPE_VERSION,
        "sender": {"entity_id": "ent_architect_dropspot"},
        "recipient": {"entity_id": entity_id},
        "routing": {"priority": "normal", "category": "directive",
                    "trust_level": "operator", "thread_id": None},
        "content": {"subject": subject, "envelope_type": None,
                    "body": None, "artifact_refs": [str(path)]},
        "lifecycle": {"state": _CHANNEL_STATE.get(channel, "WAIT"),
                      "source_tic": src_tic, "state_entered_at_tic": src_tic,
                      "created_at": mtime, "reminder_tic": None,
                      "defer_until_tic": None},
        "provenance": {"source_event": "manual_drop", "producer": "architect",
                       "manual_drop": True},
    }


def _iter_envelopes(inbox_path: str, channel: str, include_bare: bool = True):
    """Yield (message_id, envelope, name, kind) for every envelope physically
    present in a channel. kind in {flat, dir, bare}. Filesystem is truth.

    Robust by construction (tic 384): ANY file type or odd content is handled —
    a well-formed dict envelope (flat *.json or <dir>/envelope.json) parses as
    structured; ANYTHING ELSE (other extensions, a malformed or non-dict .json,
    a dropped folder with no envelope.json, a binary/image/PDF) surfaces as a
    bare `drop_` envelope. So a hand-drop is never invisible and NEVER crashes
    the scan — bare files are stat-only (content is not decoded)."""
    cdir = os.path.join(inbox_path, channel)
    if not os.path.isdir(cdir):
        return
    entity_id = _entity_from_inbox(inbox_path)
    for name in sorted(os.listdir(cdir)):
        if name.startswith(".") or name == "envelope.json":
            continue
        full = os.path.join(cdir, name)
        if os.path.isdir(full):
            cand = os.path.join(full, "envelope.json")
            if os.path.isfile(cand):
                env = None
                try:
                    env = json.loads(Path(cand).read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    env = None
                if isinstance(env, dict):
                    yield (env.get("message_id") or name), env, name, "dir"
                    continue
            # directory with no usable envelope.json -> opaque drop (visible, unparsed)
            if include_bare:
                env = _synthesize_drop_envelope(Path(full), channel, entity_id)
                yield env["message_id"], env, name, "bare"
            continue
        # regular file
        if name.endswith(".json"):
            env = None
            try:
                env = json.loads(Path(full).read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                env = None
            if isinstance(env, dict):
                yield (env.get("message_id") or name.rsplit(".json", 1)[0]), env, name, "flat"
                continue
            # malformed or non-dict JSON falls through to bare-drop handling below
        if include_bare:
            # any other extension (.md/.txt/.pdf/.png/.csv/binary/...) or a
            # non-envelope .json -> opaque drop. Synthesis is stat+filename only,
            # so unreadable/binary content cannot raise.
            env = _synthesize_drop_envelope(Path(full), channel, entity_id)
            yield env["message_id"], env, name, "bare"


def resurface_due_reminders(inbox_path: str, current_tic: int,
                            actor_id: str = "system:tic") -> dict:
    """DEFER -> WAIT for reminders whose due tic has arrived. Ported ALGORITHM
    from the deprecated SQLite lane's enforce-ttl. Loop-safe: pure lifecycle
    transition (mints NO signals), idempotent (once WAIT it leaves deferred/)."""
    resurfaced = []
    for mid, env, name, kind in list(_iter_envelopes(inbox_path, "deferred", include_bare=False)):
        if kind == "dir":
            continue  # directory envelopes aren't tic-keyed reminders
        life = env.get("lifecycle") or {}
        rt = life.get("reminder_tic")
        dut = life.get("defer_until_tic")
        due = (rt is not None and rt <= current_tic) or (dut is not None and dut <= current_tic)
        if not due:
            continue
        res = _transition(inbox_path, mid, "WAIT", actor_id, current_tic,
                          reason=f"Reminder due (reminder_tic={rt}, defer_until_tic={dut}, now={current_tic})")
        if res.get("status") == "ok":
            resurfaced.append(mid)
    return {"resurfaced": resurfaced, "resurfaced_count": len(resurfaced), "tic": current_tic}


def reconcile_registry(inbox_path: str, persist: bool = True) -> dict:
    """Rebuild registry messages{} from filesystem truth — adds any envelope
    physically present but missing from the registry (manual drops, directory
    envelopes). Filesystem is authoritative; registry is the cache."""
    registry = _load_registry(inbox_path)
    messages = registry.setdefault("messages", {})
    added, seen = [], set()
    for channel in _ALL_CHANNELS:
        for mid, env, name, kind in _iter_envelopes(inbox_path, channel):
            seen.add(mid)
            life = env.get("lifecycle") or {}
            src_tic = _envelope_source_tic(env)
            meta = {
                "state": _infer_state(env, name, channel),
                "filename": name,
                "subject": (env.get("content") or {}).get("subject", ""),
                "sender": (env.get("sender") or {}).get("entity_id", ""),
                "priority": (env.get("routing") or {}).get("priority", "normal"),
                "envelope_type": (env.get("content") or {}).get("envelope_type"),
                "source_tic": src_tic,
                "state_entered_at_tic": life.get("state_entered_at_tic", src_tic),
                "reminder_tic": life.get("reminder_tic"),
                "defer_until_tic": life.get("defer_until_tic"),
                "kind": kind,
            }
            if mid not in messages:
                added.append(mid)
            messages[mid] = {**messages.get(mid, {}), **meta}
    if persist:
        _save_registry(inbox_path, registry)
    return {"reconciled": len(seen), "added": added, "added_count": len(added)}


def search_inbox(inbox_path: str, query: str, include_terminal: bool = False) -> list:
    """Filesystem-native search over envelope content (sovereign: no binary
    index). Replaces the deprecated SQLite FTS5 lane."""
    q = (query or "").lower()
    out = []
    chans = _ALL_CHANNELS if include_terminal else _NONTERMINAL_CHANNELS
    for channel in chans:
        for mid, env, name, kind in _iter_envelopes(inbox_path, channel):
            try:
                blob = json.dumps(env, ensure_ascii=False).lower()
            except (TypeError, ValueError):
                blob = ""
            if q in blob:
                out.append({
                    "message_id": mid,
                    "channel": channel,
                    "state": _infer_state(env, name, channel),
                    "subject": (env.get("content") or {}).get("subject", ""),
                    "sender": (env.get("sender") or {}).get("entity_id", ""),
                    "source_tic": _envelope_source_tic(env),
                })
    return out


def scan_inbox(inbox_path: str) -> dict:
    """Full inbox scan — FILESYSTEM IS TRUTH (tic 384 consolidation).
    Walks channel dirs directly (flat + directory + bare-drop envelopes) so
    manually-dropped files and directory envelopes are visible, instead of
    trusting the registry cache (registry-only was the split-brain that hid
    hand-drops and the gk directory envelope)."""
    counts = {s: 0 for s in STATES}
    by_state = {s: [] for s in STATES}
    seen = set()
    for channel in _NONTERMINAL_CHANNELS:
        for mid, env, name, kind in _iter_envelopes(inbox_path, channel):
            if mid in seen:
                continue
            seen.add(mid)
            state = _infer_state(env, name, channel)
            counts[state] = counts.get(state, 0) + 1
            if state in TERMINAL_STATES:
                continue
            life = env.get("lifecycle") or {}
            by_state[state].append({
                "message_id": mid,
                "subject": (env.get("content") or {}).get("subject", ""),
                "sender": (env.get("sender") or {}).get("entity_id", ""),
                "priority": (env.get("routing") or {}).get("priority", "normal"),
                "envelope_type": (env.get("content") or {}).get("envelope_type"),
                "source_tic": _envelope_source_tic(env),
                "state_entered_at_tic": life.get("state_entered_at_tic"),
                "reminder_tic": life.get("reminder_tic"),
                "kind": kind,
            })

    pord = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    for msgs in by_state.values():
        msgs.sort(key=lambda m: (pord.get(m["priority"], 2), m.get("source_tic") or 0))

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
    """Detect items stale beyond threshold. Returns signal-ready dicts.
    Filesystem-truth (tic 384): walks channel dirs so hand-dropped + directory
    envelopes are subject to attention-debt too, not only registry-tracked ones."""
    if thresholds is None:
        thresholds = {"WAIT": 3, "ACTIVE": 3}
    stale = []
    seen = set()
    for channel in _NONTERMINAL_CHANNELS:
        for msg_id, env, name, kind in _iter_envelopes(inbox_path, channel):
            if msg_id in seen:
                continue
            seen.add(msg_id)
            # Envelope-only attention-debt (tic 404). Bare hand-drops / staging
            # files (kind="bare": swarm rails, context dumps, dropped media) are
            # NOT obligations — they carry no lifecycle contract to progress.
            # Counting them flooded the debt aggregate with ~149 phantom WAIT
            # entries (tic 404 inbox sweep: 156 inbound -> 7 real envelopes).
            # They remain VISIBLE in scan_inbox (a genuine Architect phone-drop is
            # never invisible), but they do not drive the daily attention-debt nag.
            # Only real envelopes (flat *.json / <dir>/envelope.json) accrue debt.
            # cf. ledger#obligation-lifecycle-must-be-bounded-at-both-ends — emission
            # GRANULARITY (and here, emission SUBJECT) was the leak, not the debt.
            if kind == "bare":
                continue
            state = _infer_state(env, name, channel)
            if state in TERMINAL_STATES:
                continue
            life = env.get("lifecycle") or {}
            entered = life.get("state_entered_at_tic")
            if entered is None:
                entered = _envelope_source_tic(env)
            if entered is None:
                continue
            age = current_tic - entered
            threshold = thresholds.get(state)
            if threshold and age > threshold:
                vol_map = {"WAIT": 30, "ACTIVE": 50, "DEFER": 35}
                stale.append({
                    "message_id": msg_id, "state": state,
                    "tics_in_state": age, "stale_since_tic": entered,
                    "subject": (env.get("content") or {}).get("subject", ""),
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

    AGGREGATE PER ENTITY (tic 403): ONE attention-debt signal per entity, not one
    per stale message. The debt stays visible (anti-silencing — a stale WAIT must
    not go silent; cf. ledger#obligation-lifecycle-must-be-bounded-at-both-ends),
    but as a SINGLE rollup ray carrying the full stale-message list in its payload,
    instead of N separate manifold rays. Granular per-message emission (pre-tic-403)
    flooded the manifold with up to 159 active rays for one backlog — emission
    GRANULARITY was the leak, never the debt itself. The signal id is deterministic
    and condition-stable on the ENTITY (the condition is "entity X carries inbox
    attention-debt"), so dedup-at-write collapses naturally and the daily re-surface
    is one ray per entity, not one per message.
    Dedup: skips emission if the entity's aggregate signal already exists in today's file.
    Returns list of emitted signal dicts (0 or 1 per call).

    Wire-cut gate (Wire-Cut Scoping by Capability Class): honors the `signals`
    capability scope. If ~/.claude/.wire-cut-signals or ~/.claude/.wire-cut-all
    is armed, emission is suppressed (returns []). This makes the granular
    `signals` scope real for the Python emitter — previously only hook-level
    cuts (.wire-cut-all/-hooks/-session/-gate) could stop the attention-debt
    emitter, leaving .wire-cut-signals dead. (Defense-in-depth against the
    inbox attention-debt signal-loop class.)
    """
    if not stale_items:
        return []

    # ── Wire-cut signal-emission guard (capability scope: signals) ──
    _wire_dir = os.path.join(os.path.expanduser("~"), ".claude")
    if os.path.isfile(os.path.join(_wire_dir, ".wire-cut-all")) or \
       os.path.isfile(os.path.join(_wire_dir, ".wire-cut-signals")):
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

    # Aggregate: one rollup signal per entity. The condition is "entity X carries
    # inbox attention-debt", so the id is keyed on the entity, not each message.
    count = len(stale_items)
    oldest = max(stale_items, key=lambda it: it.get("tics_in_state", 0))
    state_breakdown: dict = {}
    for it in stale_items:
        state_breakdown[it["state"]] = state_breakdown.get(it["state"], 0) + 1

    signal_id = f"sig_inbox_attention_debt_{entity_id}"
    emitted = []
    # Skip if the entity's aggregate already emitted today (one rollup/entity/day).
    if signal_id in existing_ids:
        return emitted

    # Volume scales with debt magnitude (more stale messages = louder), floored at
    # the worst item's tier and capped so a large backlog cannot dominate the manifold.
    base_vol = oldest.get("volume", 30)
    vol = min(90, base_vol + min(count - 1, 15) * 4)

    signal = {
        "id": signal_id,
        "type": "signal",
        "status": "active",
        "band": "COGNITIVE",
        "volume": vol,
        "source": "inbox_attention_debt",
        "target_entity": entity_id,
        "tic": current_tic,
        "payload": {
            "inbox_entity": entity_id,
            "stale_count": count,
            "states": state_breakdown,
            "oldest_message_id": oldest.get("message_id"),
            "oldest_state": oldest.get("state"),
            "oldest_tics_in_state": oldest.get("tics_in_state"),
            "oldest_stale_since_tic": oldest.get("stale_since_tic"),
            # Full list in payload so the debt is auditable per-message without N rays;
            # capped to keep the record bounded, with a truncation flag for the rest.
            "message_ids": [it.get("message_id") for it in stale_items[:50]],
            "message_ids_truncated": count > 50,
            "signal_kind": "TENSION",
        },
        "reason": (f"{count} message(s) stale in inbox "
                   f"(oldest {oldest.get('tics_in_state')} tics in {oldest.get('state')})"),
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


def cmd_sweep(args):
    """Reconcile filesystem -> registry (pick up hand-drops + directory
    envelopes) AND resurface due deferred reminders. The authoritative
    missed-fire catch; wired into SessionStart boot + /cadence. Replaces the
    deprecated SQLite lane's enforce-ttl."""
    zr, ar, _, _ = _resolve(args)
    if args.entity:
        targets = [args.entity]
    else:
        mbx = os.path.join(ar, "agent-mailboxes")
        targets = ([d for d in sorted(os.listdir(mbx))
                    if d.startswith("ent_") and os.path.isdir(os.path.join(mbx, d))]
                   if os.path.isdir(mbx) else [])
    out = {"status": "ok", "tic": args.current_tic, "entities": {}}
    for ent in targets:
        ibox = inbox_root(ar, ent)
        rec = reconcile_registry(ibox, persist=True)
        res = (resurface_due_reminders(ibox, args.current_tic)
               if args.current_tic is not None
               else {"resurfaced": [], "resurfaced_count": 0})
        out["entities"][ent] = {"reconciled": rec, "resurfaced": res}
    print(json.dumps(out, indent=2))


def cmd_search(args):
    """Filesystem-native content search (replaces the deprecated SQLite FTS5)."""
    zr, ar, _, _ = _resolve(args)
    if args.entity:
        matches = search_inbox(inbox_root(ar, args.entity), args.query, args.include_terminal)
    else:
        matches = []
        mbx = os.path.join(ar, "agent-mailboxes")
        if os.path.isdir(mbx):
            for d in sorted(os.listdir(mbx)):
                if d.startswith("ent_") and os.path.isdir(os.path.join(mbx, d)):
                    for r in search_inbox(inbox_root(ar, d), args.query, args.include_terminal):
                        r["entity"] = d
                        matches.append(r)
    print(json.dumps({"query": args.query, "matches": matches, "count": len(matches)}, indent=2))


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

    # sweep — reconcile filesystem->registry + resurface due reminders
    sw = sub.add_parser("sweep",
                        help="Reconcile hand-drops/dir envelopes + resurface due deferred reminders")
    sw.add_argument("--entity", default=None, help="Single entity; omit for all ent_*")
    sw.add_argument("--current-tic", type=int, default=None,
                    help="Required to resurface due reminders; omit for reconcile-only")
    sw.set_defaults(func=cmd_sweep)

    # search — filesystem-native content search (replaces SQLite FTS5)
    se = sub.add_parser("search", help="Filesystem-native content search")
    se.add_argument("--query", "-q", required=True)
    se.add_argument("--entity", default=None, help="Single entity; omit for all ent_*")
    se.add_argument("--include-terminal", action="store_true", default=False,
                    help="Also search archived/terminal envelopes")
    se.set_defaults(func=cmd_search)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
