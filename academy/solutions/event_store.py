"""
Chapter 1: Append-Only Event Store

JSONL-backed event store with latest-entry-per-ID-wins semantics.
This is the same pattern CGG uses for its signal store at audit-logs/signals/*.jsonl.
"""
import json
import os


def append_event(filepath: str, event: dict) -> None:
    """Append a JSON event to the JSONL file. Event must have an 'id' field."""
    if "id" not in event:
        raise ValueError("Event must have an 'id' field")

    with open(filepath, "a") as f:
        f.write(json.dumps(event) + "\n")


def read_current_state(filepath: str) -> dict[str, dict]:
    """Read all events, return dict of id -> latest event."""
    if not os.path.exists(filepath):
        return {}

    state = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if "id" in event:
                    state[event["id"]] = event
            except json.JSONDecodeError:
                continue
    return state


def read_full_history(filepath: str) -> list[dict]:
    """Read all events in order. No dedup."""
    if not os.path.exists(filepath):
        return []

    history = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                history.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return history
