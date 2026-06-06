#!/usr/bin/env python3
"""cadence-plan-submit.py — PreToolUse:EnterPlanMode hook

Fires when cadence submits a plan. Three responsibilities:
1. Persist the plan event into project memory
2. Trigger tmux delta dump against the correct session
3. Dedup: skip if same plan_hash was already processed

invariant: do not rely on shell aliases inside hooks — call the real binary
"""

import fcntl
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

HOOK_DIR = Path(__file__).resolve().parent


def resolve_zone_root(start: Path):
    """Fail-closed zone-root resolution.

    Walk up from the hook dir for the .ticzone marker; then cwd; then
    CLAUDE_PROJECT_DIR (only if it actually carries .ticzone). Return None if no
    verified root is found — the caller MUST fail-soft (skip audit writes) rather
    than write to a guessed or hardcoded root. Mirrors
    subagent-citizen-boot.resolve_zone_root. Removes the prior hardcoded
    /Users/breydentaylor/canonical fallback (fail-OPEN to wrong root).
    """
    for p in [start, *start.parents]:
        if (p / ".ticzone").is_file():
            return p
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        if (p / ".ticzone").is_file():
            return p
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir and (Path(env_dir) / ".ticzone").is_file():
        return Path(env_dir)
    return None


ZONE_ROOT = resolve_zone_root(HOOK_DIR)  # may be None -> main() fail-softs

# Machine-local auto-memory dir (outside the repo; no marker resolves it).
MEMORY_DIR = Path("/Users/breydentaylor/.claude/projects/-Users-breydentaylor-canonical/memory")
CADENCE_MEMORY = MEMORY_DIR / "project_cadence-hook-log.md"

# Audit-state paths derive from the verified zone root; None until resolved so a
# missing root cannot silently write under a guessed path.
HOOK_STATE_DIR = (ZONE_ROOT / "audit-logs" / "hooks") if ZONE_ROOT else None
SEEN_FILE = (HOOK_STATE_DIR / "cadence-plan-hook-seen.json") if HOOK_STATE_DIR else None
EVENT_LOG = (HOOK_STATE_DIR / "cadence-plan-submit.jsonl") if HOOK_STATE_DIR else None

TMUX_DELTA_BIN = Path("/Users/breydentaylor/.local/bin/tmux-delta-dump")


# ---------------------------------------------------------------------------
# Atomic write hygiene (mirrors scripts/lib/atomic_append.py; inlined so the
# hook stays self-contained across source/installed fire layouts — no import
# path dependency at fire time). Federation KI: JSONL Atomic Writes (PRIMITIVE).
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, data: dict) -> None:
    """Atomic JSON state write: tempfile + fsync + os.replace (atomic rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _atomic_append_jsonl(path: Path, obj: dict) -> None:
    """Atomic JSONL append: exclusive flock + fsync, one record per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj) + "\n"
    lockfile = str(path) + ".lock"
    with open(lockfile, "w") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


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
    _atomic_write_json(SEEN_FILE, data)


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

    try:
        result = subprocess.run(
            [str(TMUX_DELTA_BIN), session],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "dump_path": "", "stdout": "", "stderr": "tmux-delta-dump timed out"}

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

def log_event(plan_hash: str, delta_result: dict, agent_id: str = "", agent_type: str = "",
              session_id: str = "", dedup_mode: str = ""):
    """Log a hook-fire event to EVENT_LOG via atomic JSONL append.

    agent_id / agent_type captured from Claude Code 2.1.69+ hook payload to
    distinguish orchestrator-fired vs subagent-fired hook events. Empty when
    fired by orchestrator or older harness. session_id + dedup_mode record the
    idempotency identity used. Federation KI: bounded-delegation default masking
    — preserve agent identity in audit trail; JSONL Atomic Writes (PRIMITIVE).
    """
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "type": "hook_event",
        "hook": "cadence_plan_submit",
        "timestamp": ts,
        "plan_hash": plan_hash,
        "tdelta_rc": delta_result.get("returncode"),
        "tdelta_path": delta_result.get("dump_path", ""),
        "agent_id": agent_id,
        "agent_type": agent_type,
        "session_id": session_id,
        "dedup_mode": dedup_mode,
    }
    _atomic_append_jsonl(EVENT_LOG, event)


# ---------------------------------------------------------------------------
# Git cycle check — versioning-is-mandatory enforcement
# ---------------------------------------------------------------------------

def find_git_cycle() -> str:
    """Locate git-cycle.sh by walking up from ZONE_ROOT."""
    candidates = [
        ZONE_ROOT / "scripts" / "git-cycle.sh",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return str(c)
    return ""


def run_git_cycle() -> dict:
    """Run git-cycle.sh --check. Non-blocking — surfaces alerts via stdout."""
    script = find_git_cycle()
    if not script:
        return {"returncode": -1, "output": ""}

    try:
        result = subprocess.run(
            ["bash", script, "--check"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {"returncode": -1, "output": ""}

    # If repos need attention, emit to stdout so the hook output is visible
    if result.returncode != 0 and result.stdout.strip():
        print(f"[git-cycle] {result.stdout.strip()}")

    return {
        "returncode": result.returncode,
        "output": result.stdout.strip(),
    }


def run_rebru_emit() -> dict:
    """Fire rebru-cadence-emit (T3 Bite 3) at /cadence downbeat.

    Non-blocking, fail-soft: if the emitter is missing or errors, the hook
    proceeds without emitting a ReBru block. The cadence handoff is the
    load-bearing artifact; the ReBru block is supplementary v0 probe data.

    Bite 3 hook integration per T4a spec §13.
    """
    # The script lives at zone-root + canonical_developer/context-grapple-gun/
    # cgg-runtime/scripts/, OR at installed ~/.claude/cgg-runtime/scripts/.
    candidates = [
        ZONE_ROOT / "canonical_developer" / "context-grapple-gun" / "cgg-runtime" / "scripts" / "rebru-cadence-emit.py",
        Path.home() / ".claude" / "cgg-runtime" / "scripts" / "rebru-cadence-emit.py",
    ]
    script_path = next((c for c in candidates if c.exists()), None)
    if script_path is None:
        return {"returncode": -1, "output": "rebru-cadence-emit.py not found"}

    try:
        result = subprocess.run(
            ["python3", str(script_path), "--zone", str(ZONE_ROOT), "--quiet"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"returncode": -1, "output": str(e)}

    return {
        "returncode": result.returncode,
        "output": result.stdout.strip() or result.stderr.strip(),
    }


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

    # Fail-CLOSED on the write target, fail-SOFT on the gate: if the zone root is
    # not verified (.ticzone not found by source-walk / cwd / env), refuse to
    # write audit state under a guessed path, but never block EnterPlanMode.
    if ZONE_ROOT is None:
        sys.stderr.write(
            "[cadence-plan-submit] zone root unresolved (.ticzone not found); "
            "skipping audit writes, not blocking plan.\n"
        )
        return 0

    # Extract agent identity (Claude Code 2.1.69+). Empty for orchestrator-fired
    # or older harness — preserved as schema field for downstream provenance.
    agent_id = payload.get("agent_id") or ""
    agent_type = payload.get("agent_type") or ""
    session_id = payload.get("session_id") or ""

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

    # Identity-keyed idempotency.
    #   preferred key = session_id:entity:plan_hash
    #     - duplicate exact plan in the same session/entity  -> dedups
    #     - a revised plan in the same session (new hash)    -> recaptures
    #     - the same plan in a different session             -> recaptures
    #   legacy-safe fallback when the payload carries no session identity: do NOT
    #   pretend identity exists — key under a marked _legacy bucket on
    #   entity:plan_hash, and record dedup_mode so the audit trail is honest.
    entity = agent_id or "orchestrator"
    plan_hash = hashlib.sha256(plan_text.encode("utf-8")).hexdigest()[:16]
    if session_id:
        dedup_key = f"{session_id}:{entity}:{plan_hash}"
        dedup_mode = "identity_keyed"
    else:
        dedup_key = f"_legacy:{entity}:{plan_hash}"
        dedup_mode = "legacy_no_session"

    seen = load_seen()
    seen_keys = seen.get("seen_keys", {})
    if dedup_key in seen_keys:
        # Exact (session, entity, plan) already processed — skip, do not block.
        return 0

    # Determine tmux session — ZONE_ROOT is verified at this point.
    project_dir = str(ZONE_ROOT)
    tmux_session = resolve_tmux_session(project_dir)

    # Fire tmux delta dump
    delta_result = run_tdelta(tmux_session)

    # Git cycle check — surface dirty repos before plan mode
    # Non-blocking: emits to stdout (shown to user) but never blocks the plan.
    git_cycle_result = run_git_cycle()

    # ReBru cadence-block auto-emit (T3 Bite 3) — non-blocking, fail-soft.
    # Captures current substrate state as a v0 probe block at the /cadence
    # downbeat boundary. The block is supplementary; the cadence handoff is
    # the load-bearing artifact. Errors are logged but do not block.
    _ = run_rebru_emit()

    # Persist to memory — machine-local + best-effort; never block the plan.
    try:
        append_memory(plan_text, plan_hash, delta_result.get("dump_path", ""))
    except OSError:
        pass

    # Log event (atomic JSONL append) with identity + dedup provenance.
    log_event(plan_hash, delta_result, agent_id=agent_id, agent_type=agent_type,
              session_id=session_id, dedup_mode=dedup_mode)

    # Update dedup state. Dedup is session-scoped by design (different sessions
    # intentionally recapture), so bound growth by retaining only current-session
    # keys; the legacy bucket is capped to its 50 most-recent entries.
    seen_keys[dedup_key] = datetime.now(timezone.utc).isoformat()
    if session_id:
        seen_keys = {k: v for k, v in seen_keys.items() if k.startswith(f"{session_id}:")}
    else:
        legacy_items = sorted(seen_keys.items(), key=lambda kv: kv[1])
        seen_keys = dict(legacy_items[-50:])
    seen["seen_keys"] = seen_keys
    seen["last_plan_hash"] = plan_hash          # retained for back-compat/observability
    seen["last_session_id"] = session_id
    seen["last_entity"] = entity
    seen["last_dedup_mode"] = dedup_mode
    seen["last_timestamp"] = datetime.now(timezone.utc).isoformat()
    save_seen(seen)

    if delta_result["returncode"] == 0:
        return 0

    # Partial success: memory updated, tdelta failed — don't block the plan
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
