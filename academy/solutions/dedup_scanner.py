"""
Chapter 2: Content-Addressed Dedup Scanner

Deterministic hash-based identity for events. Prevents duplicate entries
by computing a dedup hash from selected content fields.

This is the same pattern CGG uses in scripts/cpr-extract.py to prevent
duplicate CPR queue entries — sha256(source:lesson)[:16].
"""
import hashlib
import json
import os


def compute_dedup_hash(content: dict, keys: list[str]) -> str:
    """Compute a deterministic dedup hash from selected fields.

    Concatenates the values of the specified keys (sorted, colon-separated)
    and returns the first 16 chars of the SHA-256 hex digest.
    """
    parts = []
    for k in sorted(keys):
        val = content.get(k, "")
        parts.append(str(val))
    raw = ":".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def scan_for_duplicates(filepath: str, keys: list[str]) -> list[list[dict]]:
    """Find groups of events that share the same dedup hash.

    Returns a list of groups, where each group is a list of events
    with the same hash. Only groups with 2+ entries are returned.
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
            h = compute_dedup_hash(event, keys)
            groups.setdefault(h, []).append(event)

    return [g for g in groups.values() if len(g) >= 2]


def append_if_unique(filepath: str, event: dict, dedup_keys: list[str]) -> bool:
    """Append event only if its dedup hash is not already in the file.

    Returns True if the event was appended, False if it was a duplicate.
    """
    h = compute_dedup_hash(event, dedup_keys)

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
                    existing.add(compute_dedup_hash(existing_event, dedup_keys))
                except json.JSONDecodeError:
                    continue

    if h in existing:
        return False

    with open(filepath, "a") as f:
        f.write(json.dumps(event) + "\n")
    return True
