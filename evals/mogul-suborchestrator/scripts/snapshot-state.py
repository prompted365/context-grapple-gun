#!/usr/bin/env python3
"""Capture post-run governance state for eval comparison.

Reads a workspace after Mogul execution and produces a structured JSON
snapshot of all governance state changes: mandate status, CPR queue diffs,
signal state, written artifacts.

Usage:
    python3 snapshot-state.py --workspace-dir files/workspace-queue-refresh --output snapshot.json
    python3 snapshot-state.py --help

Exit codes:
    0 - Success
    1 - Invalid arguments
    2 - Workspace not found
    3 - Snapshot write failed
"""
import argparse
import glob
import hashlib
import json
import os
import sys
from datetime import datetime, timezone


def read_json(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def file_hash(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def snapshot_mandate(workspace: str) -> dict:
    mandate_path = os.path.join(workspace, "audit-logs/mogul/mandates/current.json")
    mandate = read_json(mandate_path)
    if not mandate:
        return {"exists": False, "status": None, "mandate_id": None}
    return {
        "exists": True,
        "status": mandate.get("status"),
        "mandate_id": mandate.get("mandate_id"),
        "started_at": mandate.get("started_at"),
        "completed_at": mandate.get("completed_at"),
        "error": mandate.get("error"),
        "cycles_requested": mandate.get("cycle_request", {}).get("run_now", []),
    }


def snapshot_cpr_queue(workspace: str) -> dict:
    queue_path = os.path.join(workspace, "audit-logs/cprs/queue.jsonl")
    entries = read_jsonl(queue_path)

    # Latest entry per ID wins (append-only semantics)
    latest: dict[str, dict] = {}
    for entry in entries:
        cpr_id = entry.get("id", "")
        latest[cpr_id] = entry

    status_counts: dict[str, int] = {}
    cprs = []
    for cpr_id, entry in latest.items():
        status = entry.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        cprs.append({
            "id": cpr_id,
            "status": status,
            "lesson_prefix": entry.get("lesson", "")[:80],
            "has_enrichment": bool(entry.get("enrichment")),
            "enrichment_count": len(entry.get("enrichment", [])),
        })

    return {
        "total_entries": len(entries),
        "unique_cprs": len(latest),
        "status_counts": status_counts,
        "cprs": cprs,
    }


def snapshot_signals(workspace: str) -> dict:
    signal_dir = os.path.join(workspace, "audit-logs/signals")
    if not os.path.isdir(signal_dir):
        return {"files": [], "total_entries": 0, "active_count": 0}

    all_signals = []
    for fname in sorted(os.listdir(signal_dir)):
        if fname.endswith(".jsonl"):
            entries = read_jsonl(os.path.join(signal_dir, fname))
            all_signals.extend(entries)

    # Latest per ID
    latest: dict[str, dict] = {}
    for sig in all_signals:
        sig_id = sig.get("id", "")
        latest[sig_id] = sig

    active = [s for s in latest.values() if s.get("status") == "active"]

    return {
        "total_entries": len(all_signals),
        "unique_signals": len(latest),
        "active_count": len(active),
        "active_ids": [s.get("id", "") for s in active],
    }


def snapshot_tics(workspace: str) -> dict:
    tic_dir = os.path.join(workspace, "audit-logs/tics")
    if not os.path.isdir(tic_dir):
        return {"total_entries": 0}

    total = 0
    for fname in sorted(os.listdir(tic_dir)):
        if fname.endswith(".jsonl"):
            entries = read_jsonl(os.path.join(tic_dir, fname))
            total += len(entries)

    return {"total_entries": total}


def snapshot_artifacts(workspace: str) -> dict:
    """Find all governance artifacts written during the eval run."""
    artifact_dirs = [
        "audit-logs/mogul/reports",
        "audit-logs/mogul/transcripts",
        "audit-logs/conformations",
        "audit-logs/enrichment",
        "audit-logs/bench-packets",
    ]

    found = []
    for rel_dir in artifact_dirs:
        full_dir = os.path.join(workspace, rel_dir)
        if os.path.isdir(full_dir):
            for fname in os.listdir(full_dir):
                fpath = os.path.join(full_dir, fname)
                if os.path.isfile(fpath):
                    found.append({
                        "path": os.path.join(rel_dir, fname),
                        "size_bytes": os.path.getsize(fpath),
                        "hash": file_hash(fpath),
                    })

    # Also check for any new .json or .jsonl files created outside standard dirs
    for pattern in ["**/*.json", "**/*.jsonl"]:
        for fpath in glob.glob(os.path.join(workspace, pattern), recursive=True):
            rel = os.path.relpath(fpath, workspace)
            if rel not in [a["path"] for a in found]:
                # Skip known seed files
                if any(
                    rel.startswith(p)
                    for p in [
                        "audit-logs/cprs/",
                        "audit-logs/signals/",
                        "audit-logs/tics/",
                        "audit-logs/mogul/mandates/",
                        ".ticzone",
                    ]
                ):
                    continue
                found.append({
                    "path": rel,
                    "size_bytes": os.path.getsize(fpath),
                    "hash": file_hash(fpath),
                })

    return {"count": len(found), "artifacts": found}


def snapshot_claude_md(workspace: str) -> dict:
    """Check if any CLAUDE.md files exist or were modified."""
    claude_files = []
    for pattern in ["**/CLAUDE.md"]:
        for fpath in glob.glob(os.path.join(workspace, pattern), recursive=True):
            rel = os.path.relpath(fpath, workspace)
            claude_files.append({
                "path": rel,
                "hash": file_hash(fpath),
                "size_bytes": os.path.getsize(fpath),
            })
    return {"count": len(claude_files), "files": claude_files}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot post-run governance state for eval grading."
    )
    parser.add_argument(
        "--workspace-dir",
        required=True,
        help="Path to the eval workspace to snapshot",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output path for snapshot JSON (default: stdout)",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.workspace_dir):
        print(
            json.dumps({"error": f"Workspace not found: {args.workspace_dir}"}),
            file=sys.stderr,
        )
        return 2

    snapshot = {
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "workspace": os.path.abspath(args.workspace_dir),
        "mandate": snapshot_mandate(args.workspace_dir),
        "cpr_queue": snapshot_cpr_queue(args.workspace_dir),
        "signals": snapshot_signals(args.workspace_dir),
        "tics": snapshot_tics(args.workspace_dir),
        "artifacts": snapshot_artifacts(args.workspace_dir),
        "claude_md": snapshot_claude_md(args.workspace_dir),
    }

    output_json = json.dumps(snapshot, indent=2)
    if args.output == "-":
        print(output_json)
    else:
        try:
            os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
            with open(args.output, "w") as f:
                f.write(output_json + "\n")
        except OSError as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
