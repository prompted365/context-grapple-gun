#!/usr/bin/env python3
"""cadence-plan-submit.py — PreToolUse:EnterPlanMode hook

Fires when cadence submits a plan. Three responsibilities:
1. Persist the plan event into project memory
2. Trigger tmux delta dump against the correct session
3. Dedup: skip if same plan_hash was already processed

invariant: do not rely on shell aliases inside hooks — call the real binary
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ZONE_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", "/Users/breydentaylor/canonical"))
MEMORY_DIR = Path("/Users/breydentaylor/.claude/projects/-Users-breydentaylor-canonical/memory")
CADENCE_MEMORY = MEMORY_DIR / "project_cadence-hook-log.md"

HOOK_STATE_DIR = ZONE_ROOT / "audit-logs" / "hooks"
SEEN_FILE = HOOK_STATE_DIR / "cadence-plan-hook-seen.json"
EVENT_LOG = HOOK_STATE_DIR / "cadence-plan-submit.jsonl"

TMUX_DELTA_BIN = Path("/Users/breydentaylor/.local/bin/tmux-delta-dump")


# ---------------------------------------------------------------------------
# Dedup state
# ---------------------------------------------------------------------------

def load_seen():
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_seen(data):
    HOOK_STATE_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Memory persistence
# ---------------------------------------------------------------------------

def append_memory(plan_text: str, plan_hash: str, dump_path: str = ""):
    ts = datetime.now(timezone.utc).isoformat()
    dump_note = f"  dump: {dump_path}" if dump_path else "  dump: (not captured)"
    block = (
        f"\n### Cadence plan submitted — {ts[:10]}\n"
        f"- timestamp: {ts}\n"
        f"- plan_hash: {plan_hash}\n"
        f"{dump_note}\n"
        f"- action: auto-triggered tmux delta dump on plan submit\n"
    )
    CADENCE_MEMORY.parent.mkdir(parents=True, exist_ok=True)

    # Create the file with frontmatter if it doesn't exist
    if not CADENCE_MEMORY.exists():
        header = (
            "---\n"
            "name: Cadence Hook Log\n"
            "description: Auto-logged cadence plan submissions with tmux delta dumps\n"
            "type: reference\n"
            "---\n\n"
            "## Cadence Plan Submit Events\n\n"
            "Automatically logged by `cadence-plan-submit.py` hook on PreToolUse:EnterPlanMode.\n"
        )
        CADENCE_MEMORY.write_text(header)

    with CADENCE_MEMORY.open("a", encoding="utf-8") as f:
        f.write(block)


# ---------------------------------------------------------------------------
# Tmux delta dump
# ---------------------------------------------------------------------------

def resolve_tmux_session(project_dir: str) -> str:
    """Determine which tmux session to dump based on project directory."""
    if "operationTorque" in project_dir or "ot-" in project_dir:
        return "torquebox"
    if "canonical" in project_dir:
        return "canon"
    return "canon"


def run_tdelta(session: str) -> dict:
    if not TMUX_DELTA_BIN.exists():
        return {"returncode": 127, "stdout": "", "stderr": "tmux-delta-dump not found"}

    result = subprocess.run(
        [str(TMUX_DELTA_BIN), session],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    # Extract dump path from stdout (first line with a path)
    dump_path = ""
    for line in result.stdout.splitlines():
        if line.startswith("run_dir=") or line.startswith("full_file="):
            dump_path = line.split("=", 1)[1]
            break

    return {
        "returncode": result.returncode,
        "dump_path": dump_path,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-1000:],
    }


# ---------------------------------------------------------------------------
# Event logging
# ---------------------------------------------------------------------------

def log_event(plan_hash: str, delta_result: dict):
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "type": "hook_event",
        "hook": "cadence_plan_submit",
        "timestamp": ts,
        "plan_hash": plan_hash,
        "tdelta_rc": delta_result.get("returncode"),
        "tdelta_path": delta_result.get("dump_path", ""),
    }
    HOOK_STATE_DIR.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Read hook payload from stdin (PreToolUse provides tool input as JSON)
    try:
        payload_raw = sys.stdin.read()
        payload = json.loads(payload_raw) if payload_raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # Extract plan text from the EnterPlanMode tool input
    tool_input = payload.get("tool_input", payload)
    plan_text = ""
    if isinstance(tool_input, dict):
        plan_text = tool_input.get("plan", tool_input.get("description", ""))
    elif isinstance(tool_input, str):
        plan_text = tool_input

    if not plan_text:
        # Still fire tdelta even without plan text — the session boundary matters
        plan_text = f"(plan text not captured — hook fired at {datetime.now(timezone.utc).isoformat()})"

    # Dedup check
    plan_hash = hashlib.sha256(plan_text.encode("utf-8")).hexdigest()[:16]
    seen = load_seen()

    if seen.get("last_plan_hash") == plan_hash:
        # Skip duplicate but don't error
        return 0

    # Determine tmux session
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", str(ZONE_ROOT))
    tmux_session = resolve_tmux_session(project_dir)

    # Fire tmux delta dump
    delta_result = run_tdelta(tmux_session)

    # Persist to memory
    append_memory(plan_text, plan_hash, delta_result.get("dump_path", ""))

    # Log event
    log_event(plan_hash, delta_result)

    # Update dedup state
    seen["last_plan_hash"] = plan_hash
    seen["last_timestamp"] = datetime.now(timezone.utc).isoformat()
    save_seen(seen)

    if delta_result["returncode"] == 0:
        return 0

    # Partial success: memory updated, tdelta failed — don't block the plan
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
