"""
Chapter 4: Human-Gated Review Queue

A review system that queues proposals for human judgment and records
verdicts (approve/reject/edit) with timestamps and notes.

This is the same pattern CGG uses in /review — lessons accumulate as
CogPR proposals, but nothing gets promoted to broader scope without
explicit human approval. The human approves laws, not tactics.
"""
import json
import os
from datetime import datetime, timezone


def queue_proposal(filepath: str, proposal: dict) -> None:
    """Add a proposal to the review queue.

    Proposal must have an 'id' and a 'lesson' field.
    Status is set to 'pending' automatically.
    """
    if "id" not in proposal:
        raise ValueError("Proposal must have an 'id' field")
    if "lesson" not in proposal:
        raise ValueError("Proposal must have a 'lesson' field")

    entry = {
        **proposal,
        "type": "proposal",
        "status": "pending",
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(filepath, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_pending(filepath: str) -> list[dict]:
    """Return all proposals with status 'pending' (latest version per ID)."""
    if not os.path.exists(filepath):
        return []

    proposals = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("type") == "proposal" and "id" in entry:
                    proposals[entry["id"]] = entry
            except json.JSONDecodeError:
                continue

    return [p for p in proposals.values() if p.get("status") == "pending"]


def record_verdict(
    filepath: str,
    proposal_id: str,
    verdict: str,
    notes: str = "",
) -> bool:
    """Record a human verdict on a proposal.

    Valid verdicts: 'approved', 'rejected', 'edit_requested'.
    Returns True if the proposal was found and verdict recorded.
    """
    valid_verdicts = ("approved", "rejected", "edit_requested")
    if verdict not in valid_verdicts:
        raise ValueError(
            f"Invalid verdict: {verdict}. Must be one of {valid_verdicts}"
        )

    if not os.path.exists(filepath):
        return False

    # Find the proposal (latest version)
    proposals = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("type") == "proposal" and "id" in entry:
                    proposals[entry["id"]] = entry
            except json.JSONDecodeError:
                continue

    if proposal_id not in proposals:
        return False

    proposal = proposals[proposal_id]
    if proposal.get("status") != "pending":
        return False

    # Update the proposal with the verdict
    proposal["status"] = verdict
    proposal["verdict_at"] = datetime.now(timezone.utc).isoformat()
    proposal["verdict_notes"] = notes

    # Append the updated version (latest-per-ID wins)
    with open(filepath, "a") as f:
        f.write(json.dumps(proposal) + "\n")
    return True


def get_review_history(filepath: str) -> list[dict]:
    """Return all proposals that have received a verdict (latest per ID).

    Includes approved, rejected, and edit_requested — everything
    except 'pending'. Ordered by verdict_at.
    """
    if not os.path.exists(filepath):
        return []

    proposals = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("type") == "proposal" and "id" in entry:
                    proposals[entry["id"]] = entry
            except json.JSONDecodeError:
                continue

    reviewed = [
        p for p in proposals.values() if p.get("status") != "pending"
    ]
    reviewed.sort(key=lambda p: p.get("verdict_at", ""))
    return reviewed
