"""
Chapter 2: Collaboration Pattern Scanner

Deterministic hash-based identity for collaboration patterns. Identifies
recurring coordination structures by computing a content fingerprint from
selected fields.

This is the same pattern CGG uses to prevent duplicate CogPR queue entries
— sha256(source:lesson)[:16]. Here it's applied to teamwork patterns:
standups, role assignments, escalation protocols, attendance tracking.
"""
import hashlib
import json
import os


def compute_pattern_hash(content: dict, keys: list[str]) -> str:
    """Compute a deterministic fingerprint from selected fields.

    Concatenates the values of the specified keys (sorted, colon-separated)
    and returns the first 16 chars of the SHA-256 hex digest. Used to
    identify recurring collaboration patterns.
    """
    parts = []
    for k in sorted(keys):
        val = content.get(k, "")
        parts.append(str(val))
    raw = ":".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def scan_for_patterns(filepath: str, keys: list[str]) -> list[list[dict]]:
    """Find groups of events that share the same pattern fingerprint.

    Returns a list of groups, where each group is a list of events
    with the same hash. Only groups with 2+ entries (recurring patterns)
    are returned.
    """
    if not os.path.exists(filepath):
        return []

    groups: dict[str, list[dict]] = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            h = compute_pattern_hash(event, keys)
            groups.setdefault(h, []).append(event)

    return [g for g in groups.values() if len(g) >= 2]


def append_if_unique(filepath: str, event: dict, pattern_keys: list[str]) -> bool:
    """Append event only if its pattern fingerprint is not already in the file.

    Returns True if the event was appended (new pattern), False if the
    pattern was already recorded.
    """
    h = compute_pattern_hash(event, pattern_keys)

    # Load existing hashes
    existing = set()
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing_event = json.loads(line)
                    existing.add(compute_pattern_hash(existing_event, pattern_keys))
                except json.JSONDecodeError:
                    continue

    if h in existing:
        return False

    with open(filepath, "a") as f:
        f.write(json.dumps(event) + "\n")
    return True
