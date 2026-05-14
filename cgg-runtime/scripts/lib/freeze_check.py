#!/usr/bin/env python3
"""Freeze runtime gate for constitutional dehydration Pass 4.

Reads audit-logs/governance/constitution-ledger/freeze-state.json on each call
(mutation-fresh; no caching). When freeze is active on a surface in scope, raises
FreezeViolation. Callers must invoke check_freeze(target_path, zone_root) before
writing to any constitutional surface.

Spec: audit-logs/governance/constitution-ledger/freeze-runtime-gate-spec-tic266.md
Authority: Architect-only activation/deactivation (default Pass 4 open/close gates).
"""
import json
import os
from pathlib import Path
from typing import Optional


class FreezeViolation(Exception):
    """Raised when a write is attempted on a frozen surface during active freeze."""
    pass


# Path relative to zone_root
FREEZE_STATE_REL = Path("audit-logs/governance/constitution-ledger/freeze-state.json")
FREEZE_EVENTS_REL = Path("audit-logs/governance/constitution-ledger/freeze-events.jsonl")


def _find_zone_root(start: Optional[Path] = None) -> Path:
    """Walk upward from start to find a .federation-root marker (zone root)."""
    if start is None:
        start = Path.cwd()
    start = start.resolve()
    for ancestor in [start] + list(start.parents):
        if (ancestor / ".federation-root").exists():
            return ancestor
    # Fallback: use start
    return start


def check_freeze(target_path: str, zone_root: Optional[Path] = None) -> None:
    """Raise FreezeViolation if target_path is in active freeze surface_scope.

    Args:
        target_path: path to the file about to be written (absolute or relative).
        zone_root: federation root path; auto-detected if None.

    Returns:
        None if freeze is inactive, no state file exists, or target is out of scope.

    Raises:
        FreezeViolation: when freeze is active AND target is in surface_scope.

    Reads state file on every call (no caching — state is mutation-fresh).
    The check is cheap (single file read + dict lookup) and idempotent.
    """
    if zone_root is None:
        zone_root = _find_zone_root()
    zone_root = Path(zone_root).resolve()

    state_file = zone_root / FREEZE_STATE_REL
    if not state_file.exists():
        # No freeze state inscribed → no-op (pre-spec state, or post-deactivation cleanup)
        return

    try:
        state = json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        # Corrupted or unreadable state — fail-open to avoid blocking legitimate writes.
        # The Atomic-Commit Discipline KI applies: state mutations are atomic; corruption
        # implies operator intervention required. Returning None here is the safer default
        # than raising on every write.
        return

    if state.get("status") != "active":
        return

    surface_scope = state.get("surface_scope", [])
    if not surface_scope:
        return

    # Normalize target_path to a path relative to zone_root for surface_scope comparison
    target = Path(target_path)
    if not target.is_absolute():
        target = (zone_root / target).resolve()
    else:
        target = target.resolve()
    try:
        rel_target = str(target.relative_to(zone_root))
    except ValueError:
        # Target is outside zone_root — out of federation scope; don't enforce.
        return

    if rel_target in surface_scope:
        raise FreezeViolation(
            f"Constitutional freeze active on {rel_target}. "
            f"activated_at_tic={state.get('activated_at_tic')} "
            f"by={state.get('activated_by')}. "
            f"Spec: {state.get('spec_anchor')}. "
            f"Audit trail: {state.get('audit_trail_anchor')}. "
            f"To proceed, Architect must deactivate via append to freeze-events.jsonl "
            f"with event_type='deactivate' and flip freeze-state.json status to 'inactive'."
        )


def get_freeze_state(zone_root: Optional[Path] = None) -> dict:
    """Return current freeze state dict, or {'status': 'inactive'} if no state file."""
    if zone_root is None:
        zone_root = _find_zone_root()
    state_file = Path(zone_root).resolve() / FREEZE_STATE_REL
    if not state_file.exists():
        return {"status": "inactive", "surface_scope": [], "spec_anchor": None}
    try:
        return json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {"status": "inactive", "surface_scope": [], "spec_anchor": None, "error": "unreadable_state"}


if __name__ == "__main__":
    # CLI usage: python3 freeze_check.py <target_path>
    # Exit 0 if no violation; exit 1 if FreezeViolation raised; prints reason.
    import sys
    if len(sys.argv) < 2:
        print("Usage: freeze_check.py <target_path>")
        sys.exit(2)
    try:
        check_freeze(sys.argv[1])
    except FreezeViolation as exc:
        print(f"FREEZE_VIOLATION: {exc}")
        sys.exit(1)
    print(f"freeze_check OK: {sys.argv[1]} is not blocked")
    sys.exit(0)
