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


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        data = json.loads(sys.argv[2])
        atomic_append_jsonl(sys.argv[1], data)
    else:
        print(f"Usage: {sys.argv[0]} <target.jsonl> '<json>'")
        sys.exit(1)
