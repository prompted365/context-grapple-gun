"""
cockpit_intent_emit.py — Python emitter for cockpit.intent envelope (T2b, tic 267).

Python-side equivalent of the TypeScript cockpitIntentEmitter at
canonical_developer/ak-control-room/src/adapters/cockpitIntentEmitter.ts (T2a, tic 260).

The TS emitter is browser-bound (it calls fetch('/api/governance/cockpit/intent')
against the vite dev server). Hooks fire from Claude Code's CLI context where
the vite server is not reachable; this helper writes the envelope directly to
the same JSONL the vite POST endpoint writes to, preserving byte-shape parity
with the TS emitter so downstream consumers (cockpitIntentAdapter, postureAdapter)
see one canonical write surface.

Used by:
  - cgg-runtime/hooks/cockpit-intent-posture-toggle.py (I-A: UserPromptSubmit)
  - cgg-runtime/scripts/cadence-ops.py (I-B: per-cadence-emit observe)
  - manual REST callers use the vite POST endpoint directly (I-D escape hatch)

Schema reference: ak_control_room/envelopes.yaml#cockpit.intent
Spec reference: audit-logs/governance/cockpit-intent-t2b-invocation-discipline-spec-tic264.md

SPEC_MIRROR: ak_control_room/envelopes.yaml#cockpit.intent
"""

import glob
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Allow importing siblings (atomic_append)
_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
import sys
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from atomic_append import atomic_append_jsonl  # noqa: E402

VALID_INTENT_CLASS = {"free", "observe", "interface_with", "flight", "bidirectional_mirror"}
VALID_REQUIRED_GATE = {"G0_auto_audit", "G1_notify", "G2_human_confirm", "G3_constitutional"}
VALID_POSTURE = {"ENG/META", "ENG/DIRECT", "OPS/META", "OPS/DIRECT"}
VALID_MODE = {"LITE", "FULL", "OFF"}


def _generate_intent_id() -> str:
    """Generate int_<8-char-hex> — mirrors TS emitter generateIntentId()."""
    return "int_" + secrets.token_hex(4)


def _resolve_current_tic(zone_root: str) -> int:
    """Resolve current tic by counting counted tic events. Mirrors cadence-ops.count_physical_tics.

    Falls back to -1 sentinel when tic surface is unreachable (matches TS emitter
    resolveCurrentTic shape). The -1 sentinel is the contract; downstream
    consumers may treat sentinel as an unresolved emission.
    """
    tic_dir = os.path.join(zone_root, "audit-logs", "tics")
    if not os.path.isdir(tic_dir):
        return -1
    total = 0
    for f in sorted(glob.glob(os.path.join(tic_dir, "*.jsonl"))):
        try:
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
        except OSError:
            return -1
    return total


def _validate_conditional_fields(envelope: dict) -> Optional[str]:
    """Validate envelopes.yaml when_included rules. Mirrors TS emitter validateConditionalFields.

    Returns None when valid; returns a human-readable error string otherwise.
    """
    cls = envelope.get("intent_class")
    has_target = bool(envelope.get("target_object_ref"))
    has_vector = bool(envelope.get("movement_vector"))
    has_mirror = bool(envelope.get("mirror_pair"))

    if cls in ("interface_with", "flight") and not has_target:
        return f"target_object_ref REQUIRED when intent_class is '{cls}' (envelopes.yaml when_included)"
    if cls == "flight" and not has_vector:
        return "movement_vector REQUIRED when intent_class is 'flight' (envelopes.yaml when_included)"
    if cls == "bidirectional_mirror" and not has_mirror:
        return "mirror_pair REQUIRED when intent_class is 'bidirectional_mirror' (envelopes.yaml when_included)"
    if cls in ("free", "observe") and has_target:
        return f"target_object_ref MUST be absent when intent_class is '{cls}' (envelopes.yaml when_included)"
    if cls != "flight" and has_vector:
        return "movement_vector MUST be absent when intent_class is not 'flight'"
    if cls != "bidirectional_mirror" and has_mirror:
        return "mirror_pair MUST be absent when intent_class is not 'bidirectional_mirror'"
    return None


def _validate_envelope(envelope: dict) -> Optional[str]:
    """Full schema validation. Returns None on valid; error string on invalid."""
    required = (
        "intent_class", "source_object_ref", "source_path",
        "required_gate", "posture", "mode", "operator_ref",
    )
    for f in required:
        if not envelope.get(f):
            return f"Missing required field: {f}"

    if envelope["intent_class"] not in VALID_INTENT_CLASS:
        return f"Invalid intent_class: {envelope['intent_class']} (valid: {sorted(VALID_INTENT_CLASS)})"
    if envelope["required_gate"] not in VALID_REQUIRED_GATE:
        return f"Invalid required_gate: {envelope['required_gate']}"
    if envelope["posture"] not in VALID_POSTURE:
        return f"Invalid posture: {envelope['posture']} (valid: {sorted(VALID_POSTURE)})"
    if envelope["mode"] not in VALID_MODE:
        return f"Invalid mode: {envelope['mode']} (valid: {sorted(VALID_MODE)})"

    return _validate_conditional_fields(envelope)


def _dedup_check(zone_root: str, tic: int, envelope: dict) -> bool:
    """Per-spec idempotency contract (T2b §Idempotency Contract).

    Within the same tic, identical (source_object_ref, source_path, intent_class,
    posture, mode) tuples collapse to a single emission. The first emission wins;
    subsequent identical tuples within the same tic are no-ops.

    Returns True if this emission is a duplicate (caller should skip); False if
    novel (caller should proceed). Updates the dedup window file on novel.
    """
    if tic < 0:
        # Sentinel tic — cannot dedup; allow emission to surface as unresolved
        return False

    dedup_dir = os.path.join(zone_root, "audit-logs", "cockpit", "intents")
    os.makedirs(dedup_dir, exist_ok=True)
    dedup_file = os.path.join(dedup_dir, f"dedup-window-{tic}.json")

    tuple_key = "|".join([
        envelope.get("source_object_ref", ""),
        envelope.get("source_path", ""),
        envelope.get("intent_class", ""),
        envelope.get("posture", ""),
        envelope.get("mode", ""),
    ])
    tuple_hash = hashlib.sha256(tuple_key.encode("utf-8")).hexdigest()[:16]

    seen = {}
    if os.path.exists(dedup_file):
        try:
            with open(dedup_file, "r", encoding="utf-8") as f:
                seen = json.load(f)
        except (OSError, json.JSONDecodeError):
            seen = {}

    if tuple_hash in seen:
        return True

    seen[tuple_hash] = {
        "tuple": tuple_key,
        "intent_id": envelope.get("intent_id"),
        "first_seen": datetime.now(timezone.utc).isoformat(),
    }
    # Atomic-ish write of the dedup window file
    tmp = dedup_file + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(seen, f, indent=2)
        os.replace(tmp, dedup_file)
    except OSError:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return False


def emit_intent(
    zone_root: str,
    intent_class: str,
    source_object_ref: str,
    source_path: str,
    required_gate: str,
    posture: str,
    mode: str,
    operator_ref: str = "ent_breyden",
    target_object_ref: Optional[str] = None,
    movement_vector: Optional[dict] = None,
    mirror_pair: Optional[dict] = None,
    actor: str = "cockpit_intent_emit",
    source_ref: Optional[str] = None,
) -> dict:
    """Emit a cockpit.intent envelope.

    Returns a result dict:
        {"emitted": True, "intent_id": "...", "envelope": {...}, "dedup_skipped": False}
        {"emitted": False, "reason": "...", "dedup_skipped": True}
        {"emitted": False, "reason": "...", "error": True}

    Per spec T2b §Error Handling: validation failures and dedup skips are
    surfaced explicitly; callers (hook surfaces) should log them visibly
    rather than silently swallowing.
    """
    intent_id = _generate_intent_id()
    tic = _resolve_current_tic(zone_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    envelope = {
        "intent_id": intent_id,
        "intent_class": intent_class,
        "source_object_ref": source_object_ref,
        "source_path": source_path,
        "required_gate": required_gate,
        "posture": posture,
        "mode": mode,
        "tic": tic,
        "operator_ref": operator_ref,
    }
    if target_object_ref:
        envelope["target_object_ref"] = target_object_ref
    if movement_vector:
        envelope["movement_vector"] = movement_vector
    if mirror_pair:
        envelope["mirror_pair"] = mirror_pair

    envelope["provenance_stamp"] = {
        "actor": actor,
        "tic": tic,
        "timestamp": timestamp,
        "source_ref": source_ref or "cockpit_intent_emit.emit_intent",
    }
    envelope["emitted_at"] = timestamp

    # Schema validation
    validation_error = _validate_envelope(envelope)
    if validation_error:
        return {
            "emitted": False,
            "error": True,
            "reason": f"cockpit.intent: {validation_error}",
        }

    # Idempotency contract (T2b §Idempotency)
    if _dedup_check(zone_root, tic, envelope):
        return {
            "emitted": False,
            "dedup_skipped": True,
            "reason": f"per-tic dedup hit (tic={tic})",
            "intent_id": intent_id,
        }

    # Atomic append to canonical surface
    today = timestamp[:10]
    target = os.path.join(zone_root, "audit-logs", "cockpit", "intents", f"{today}.jsonl")
    try:
        atomic_append_jsonl(target, envelope)
    except OSError as err:
        return {
            "emitted": False,
            "error": True,
            "reason": f"append failed: {err}",
            "intent_id": intent_id,
        }

    return {
        "emitted": True,
        "intent_id": intent_id,
        "envelope": envelope,
        "tic": tic,
        "path": target,
    }


def resolve_zone_root(start: Optional[str] = None) -> str:
    """Walk up from start (or cwd) looking for .ticzone. Mirrors zone_root.resolve_zone_root."""
    cur = Path(start or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
    while cur != cur.parent:
        if (cur / ".ticzone").exists():
            return str(cur)
        cur = cur.parent
    # Fall back to canonical default
    return os.environ.get("CLAUDE_PROJECT_DIR", "/Users/breydentaylor/canonical")
