"""
atomic_append.py — JSONL-safe atomic append using fcntl file locking.

Usage:
    from lib.atomic_append import atomic_append_jsonl
    atomic_append_jsonl("/path/to/file.jsonl", {"key": "value"})
"""

import fcntl
import json
import os
import tempfile


def atomic_append_jsonl(target: str, data: dict) -> None:
    """Atomically append a JSON line to a JSONL file with exclusive locking."""
    os.makedirs(os.path.dirname(target), exist_ok=True)
    line = json.dumps(data, separators=(",", ":")) + "\n"
    lockfile = target + ".lock"

    with open(lockfile, "w") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            with open(target, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def atomic_write_json(target: str, data: dict) -> None:
    """Atomically write a JSON file (temp + rename)."""
    os.makedirs(os.path.dirname(target), exist_ok=True)
    fd, tmppath = tempfile.mkstemp(
        dir=os.path.dirname(target), suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmppath, target)
    except Exception:
        os.unlink(tmppath)
        raise


def dedup_signal_append(target: str, signal: dict, manifest_path: str = None) -> bool:
    """Append a signal only if its ID doesn't already exist in the target file
    or the active manifest. Returns True if written, False if deduplicated.

    Signal ID is read from 'signal_id' or 'id' field.
    """
    sig_id = signal.get("signal_id", signal.get("id", ""))
    if not sig_id:
        # No ID — can't dedup, just append
        atomic_append_jsonl(target, signal)
        return True

    os.makedirs(os.path.dirname(target), exist_ok=True)
    lockfile = target + ".lock"

    with open(lockfile, "w") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            # Check target file for existing ID
            existing_ids = set()
            if os.path.isfile(target):
                with open(target, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            eid = d.get("signal_id", d.get("id", ""))
                            if eid:
                                existing_ids.add(eid)
                        except (json.JSONDecodeError, ValueError):
                            pass

            # Check active manifest if provided and different from target
            if manifest_path and manifest_path != target and os.path.isfile(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            eid = d.get("signal_id", d.get("id", ""))
                            if eid:
                                existing_ids.add(eid)
                        except (json.JSONDecodeError, ValueError):
                            pass

            if sig_id in existing_ids:
                return False

            # Write signal
            sline = json.dumps(signal, separators=(",", ":")) + "\n"
            with open(target, "a", encoding="utf-8") as f:
                f.write(sline)
                f.flush()
                os.fsync(f.fileno())
            return True
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def dedup_queue_append(target: str, entry: dict) -> bool:
    """Append a CPR queue entry only if its id doesn't already exist in the
    target file. Returns True if written, False if deduplicated.

    Implements Dedup-at-Write doctrine (CogPR-117) for the CPR queue: dedup
    enforcement happens at the write boundary, keyed on canonical record
    identity (entry id). Mirrors dedup_signal_append for queue.jsonl.

    The function reads the target under exclusive lock, scans existing ids,
    and only writes if the new entry's id is absent. This catches duplication
    at the physics layer regardless of why the caller is attempting to write
    the same id again (race, loop bug, missed upstream check).

    For terminal-state preservation, callers should verify the existing entry
    is not already terminal BEFORE invoking this function — once an id is
    written, this function will never overwrite. The Terminal-State Valve
    pattern (CogPR-188) is the read-side complement.
    """
    eid = entry.get("id", "")
    if not eid:
        # No ID — fall back to plain append; caller is responsible
        atomic_append_jsonl(target, entry)
        return True

    os.makedirs(os.path.dirname(target), exist_ok=True)
    lockfile = target + ".lock"

    with open(lockfile, "w") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            existing_ids = set()
            if os.path.isfile(target):
                with open(target, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            existing = d.get("id", "")
                            if existing:
                                existing_ids.add(existing)
                        except (json.JSONDecodeError, ValueError):
                            pass

            if eid in existing_ids:
                return False

            line = json.dumps(entry, separators=(",", ":")) + "\n"
            with open(target, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
            return True
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        data = json.loads(sys.argv[2])
        atomic_append_jsonl(sys.argv[1], data)
    else:
        print(f"Usage: {sys.argv[0]} <target.jsonl> '<json>'")
        sys.exit(1)
