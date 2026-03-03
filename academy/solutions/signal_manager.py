"""
Chapter 3: Signal Lifecycle Manager

Signals with volume accrual, TTL-based expiry, and escalation thresholds.
Each tick advances the clock: volume accrues on active signals, TTL counts
down, and signals that cross their escalation threshold get flagged.

This is the same pattern CGG uses in /siren tick — signals accumulate
pressure until they either resolve or escalate into warrants.
"""
import json
import os
from datetime import datetime, timezone


def create_signal(
    signal_id: str,
    kind: str,
    band: str,
    volume: int = 10,
    ttl_hours: float = 24.0,
    escalation_threshold: int = 80,
    volume_rate: int = 5,
) -> dict:
    """Create a new signal dict with required lifecycle fields."""
    if kind not in ("BEACON", "LESSON", "OPPORTUNITY", "TENSION"):
        raise ValueError(f"Invalid kind: {kind}. Must be BEACON, LESSON, OPPORTUNITY, or TENSION")
    if band not in ("PRIMITIVE", "COGNITIVE", "SOCIAL"):
        raise ValueError(f"Invalid band: {band}. PRESTIGE is governance-blocked.")

    return {
        "id": signal_id,
        "type": "signal",
        "kind": kind,
        "band": band,
        "volume": volume,
        "volume_rate": volume_rate,
        "ttl_hours": ttl_hours,
        "escalation_threshold": escalation_threshold,
        "status": "active",
        "tick_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "escalated": False,
    }


def tick_signals(filepath: str, elapsed_hours: float = 1.0) -> dict:
    """Advance all signals by elapsed_hours.

    For each active signal:
    - Decrease ttl_hours by elapsed_hours
    - Increase volume by volume_rate
    - Increment tick_count
    - If ttl_hours <= 0, set status to 'expired'
    - If volume >= escalation_threshold, set escalated to True

    Returns a summary: {ticked, expired, escalated, total_active}.
    Writes updated state back to the file (append-only: latest-per-ID wins).
    """
    if not os.path.exists(filepath):
        return {"ticked": 0, "expired": 0, "escalated": 0, "total_active": 0}

    # Read current state (latest per ID)
    signals = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if event.get("type") == "signal" and "id" in event:
                    signals[event["id"]] = event
            except json.JSONDecodeError:
                continue

    ticked = 0
    expired = 0
    escalated = 0
    updates = []

    for sig_id, sig in signals.items():
        if sig.get("status") != "active":
            continue

        sig["ttl_hours"] = sig.get("ttl_hours", 0) - elapsed_hours
        sig["volume"] = sig.get("volume", 0) + sig.get("volume_rate", 0)
        sig["tick_count"] = sig.get("tick_count", 0) + 1
        ticked += 1

        if sig["ttl_hours"] <= 0:
            sig["status"] = "expired"
            expired += 1
        elif sig["volume"] >= sig.get("escalation_threshold", 100):
            sig["escalated"] = True
            escalated += 1

        updates.append(sig)

    # Append updated signals (latest-per-ID-wins)
    if updates:
        with open(filepath, "a") as f:
            for sig in updates:
                f.write(json.dumps(sig) + "\n")

    total_active = sum(
        1 for s in signals.values() if s.get("status") == "active"
    )

    return {
        "ticked": ticked,
        "expired": expired,
        "escalated": escalated,
        "total_active": total_active,
    }


def get_active_signals(filepath: str) -> list[dict]:
    """Return all signals with status 'active' (latest version per ID)."""
    if not os.path.exists(filepath):
        return []

    signals = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if event.get("type") == "signal" and "id" in event:
                    signals[event["id"]] = event
            except json.JSONDecodeError:
                continue

    return [s for s in signals.values() if s.get("status") == "active"]


def resolve_signal(filepath: str, signal_id: str) -> bool:
    """Mark a signal as resolved. Returns True if found and updated."""
    if not os.path.exists(filepath):
        return False

    signals = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if event.get("type") == "signal" and "id" in event:
                    signals[event["id"]] = event
            except json.JSONDecodeError:
                continue

    if signal_id not in signals:
        return False

    sig = signals[signal_id]
    if sig.get("status") != "active":
        return False

    sig["status"] = "resolved"
    with open(filepath, "a") as f:
        f.write(json.dumps(sig) + "\n")
    return True
