#!/usr/bin/env python3
"""cadence-interstitial-enter.py — PreToolUse:EnterPlanMode hook

INTERSTITIAL ENTRY (tic 633 plan-lifecycle split — Architect-directed repair).

This hook marks the entry into the interstitial between tic N (closed by the
/cadence emission that precedes plan mode) and tic N+1 (activated at the next
session's boot). It is the renamed, honest half of the former
cadence-plan-submit.py, which fired at EnterPlanMode but claimed to capture a
"plan submission" — hashing synthesized text BEFORE the plan existed. The plan
does not exist at EnterPlanMode; the handoff SEAL lives in
cadence-handoff-seal.py on ExitPlanMode.

Responsibilities (all boundary-context, no plan claims):
1. Record the boundary context — emission_id + work/entry tics read from the
   interstitial marker (audit-logs/tics/.interstitial-marker.json) written by
   cadence-ops.py at emission. Claims NO plan submission.
2. Trigger the tmux delta dump against the correct session (state capture at
   the boundary).
3. Git-cycle check — surface dirty repos before plan mode (versioning-is-
   mandatory enforcement, non-blocking).
4. ReBru cadence-block auto-emit (T3 Bite 3) — fail-soft substrate probe.
5. Event log + machine-local memory note.

Tic/tdelta/git-cycle/ReBru stay HERE (the boundary side) — they are NOT moved
into ExitPlanMode (per the t632 directive §4).

invariant: do not rely on shell aliases inside hooks — call the real binary
"""

import fcntl
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
    """Fail-closed zone-root resolution (mirrors cadence-plan-submit heritage).

    Walk up from the hook dir for the .ticzone marker; then cwd; then
    CLAUDE_PROJECT_DIR (only if it actually carries .ticzone). Return None if no
    verified root is found — the caller MUST fail-soft (skip audit writes)
    rather than write to a guessed or hardcoded root.
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

HOOK_STATE_DIR = (ZONE_ROOT / "audit-logs" / "hooks") if ZONE_ROOT else None
SEEN_FILE = (HOOK_STATE_DIR / "cadence-plan-hook-seen.json") if HOOK_STATE_DIR else None
EVENT_LOG = (HOOK_STATE_DIR / "cadence-plan-submit.jsonl") if HOOK_STATE_DIR else None
INTERSTITIAL_MARKER = (ZONE_ROOT / "audit-logs" / "tics" / ".interstitial-marker.json") if ZONE_ROOT else None

TMUX_DELTA_BIN = Path("/Users/breydentaylor/.local/bin/tmux-delta-dump")


# ---------------------------------------------------------------------------
# Atomic write hygiene (inlined; self-contained across fire layouts)
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _atomic_append_jsonl(path: Path, obj: dict) -> None:
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
# Boundary context — read, never write (cadence-ops owns the marker)
# ---------------------------------------------------------------------------

def read_boundary_context() -> dict:
    """Read the interstitial marker written by cadence-ops.py at emission.

    Returns {} when absent/unreadable — an EnterPlanMode with no fresh boundary
    (mid-tic ordinary plan mode) is a legitimate fire; the event row simply
    carries no boundary claim.
    """
    if INTERSTITIAL_MARKER is None or not INTERSTITIAL_MARKER.is_file():
        return {}
    try:
        marker = json.loads(INTERSTITIAL_MARKER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(marker, dict):
        return {}
    return {
        "emission_id": marker.get("emission_id"),
        "work_tic": marker.get("work_tic"),
        "entry_tic": marker.get("entry_tic"),
        "marker_state": marker.get("state"),
    }


# ---------------------------------------------------------------------------
# Dedup state (per-session single fire; keyed on session + boundary)
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

def append_memory(boundary: dict, dump_path: str = ""):
    ts = datetime.now(timezone.utc).isoformat()
    dump_note = f"  dump: {dump_path}" if dump_path else "  dump: (not captured)"
    em = boundary.get("emission_id") or "(no fresh boundary)"
    block = (
        f"\n### Cadence interstitial entered — {ts[:10]}\n"
        f"- timestamp: {ts}\n"
        f"- emission_id: {em}\n"
        f"- work_tic: {boundary.get('work_tic')}  entry_tic: {boundary.get('entry_tic')}\n"
        f"{dump_note}\n"
        f"- action: interstitial entry (no plan submission claimed — seal lands at ExitPlanMode)\n"
    )
    CADENCE_MEMORY.parent.mkdir(parents=True, exist_ok=True)
    if not CADENCE_MEMORY.exists():
        header = (
            "---\n"
            "name: Cadence Hook Log\n"
            "description: Auto-logged cadence boundary events with tmux delta dumps\n"
            "type: reference\n"
            "---\n\n"
            "## Cadence Boundary Events\n\n"
            "Automatically logged by the cadence plan-lifecycle hooks.\n"
        )
        CADENCE_MEMORY.write_text(header)
    with CADENCE_MEMORY.open("a", encoding="utf-8") as f:
        f.write(block)


# ---------------------------------------------------------------------------
# Tmux delta dump
# ---------------------------------------------------------------------------

def resolve_tmux_session(project_dir: str) -> str:
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
            capture_output=True, text=True, check=False, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "dump_path": "", "stdout": "", "stderr": "tmux-delta-dump timed out"}
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
# Git cycle check — versioning-is-mandatory enforcement
# ---------------------------------------------------------------------------

def run_git_cycle() -> dict:
    script = ZONE_ROOT / "scripts" / "git-cycle.sh"
    if not (script.exists() and script.is_file()):
        return {"returncode": -1, "output": ""}
    try:
        result = subprocess.run(
            ["bash", str(script), "--check"],
            capture_output=True, text=True, check=False, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {"returncode": -1, "output": ""}
    if result.returncode != 0 and result.stdout.strip():
        print(f"[git-cycle] {result.stdout.strip()}")
    return {"returncode": result.returncode, "output": result.stdout.strip()}


def run_rebru_emit() -> dict:
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
            capture_output=True, text=True, check=False, timeout=20,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"returncode": -1, "output": str(e)}
    return {"returncode": result.returncode,
            "output": result.stdout.strip() or result.stderr.strip()}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        payload_raw = sys.stdin.read()
        payload = json.loads(payload_raw) if payload_raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # Fail-CLOSED on the write target, fail-SOFT on the gate: never block
    # EnterPlanMode, never write under a guessed root.
    if ZONE_ROOT is None:
        sys.stderr.write(
            "[cadence-interstitial-enter] zone root unresolved (.ticzone not "
            "found); skipping audit writes, not blocking plan mode.\n"
        )
        return 0

    agent_id = payload.get("agent_id") or ""
    agent_type = payload.get("agent_type") or ""
    session_id = payload.get("session_id") or ""

    boundary = read_boundary_context()

    # Idempotency: one interstitial-entry capture per (session, boundary).
    # A fresh boundary keys on emission_id; a boundary-less EnterPlanMode
    # (ordinary mid-tic plan mode) keys on the session alone and is captured
    # at most once per session.
    entity = agent_id or "orchestrator"
    em = boundary.get("emission_id") or "_no_boundary"
    if session_id:
        dedup_key = f"{session_id}:{entity}:interstitial:{em}"
        dedup_mode = "identity_keyed"
    else:
        dedup_key = f"_legacy:{entity}:interstitial:{em}"
        dedup_mode = "legacy_no_session"

    seen = load_seen()
    seen_keys = seen.get("seen_keys", {})
    if dedup_key in seen_keys:
        return 0

    project_dir = str(ZONE_ROOT)
    tmux_session = resolve_tmux_session(project_dir)
    delta_result = run_tdelta(tmux_session)
    _ = run_git_cycle()
    _ = run_rebru_emit()

    try:
        append_memory(boundary, delta_result.get("dump_path", ""))
    except OSError:
        pass

    ts = datetime.now(timezone.utc).isoformat()
    _atomic_append_jsonl(EVENT_LOG, {
        "type": "hook_event",
        "hook": "cadence_interstitial_enter",
        "timestamp": ts,
        "emission_id": boundary.get("emission_id"),
        "work_tic": boundary.get("work_tic"),
        "entry_tic": boundary.get("entry_tic"),
        "marker_state": boundary.get("marker_state"),
        "plan_submission_claimed": False,
        "tdelta_rc": delta_result.get("returncode"),
        "tdelta_path": delta_result.get("dump_path", ""),
        "agent_id": agent_id,
        "agent_type": agent_type,
        "session_id": session_id,
        "dedup_mode": dedup_mode,
    })

    seen_keys[dedup_key] = ts
    if session_id:
        seen_keys = {k: v for k, v in seen_keys.items() if k.startswith(f"{session_id}:")}
    else:
        legacy_items = sorted(seen_keys.items(), key=lambda kv: kv[1])
        seen_keys = dict(legacy_items[-50:])
    seen["seen_keys"] = seen_keys
    seen["last_session_id"] = session_id
    seen["last_entity"] = entity
    seen["last_dedup_mode"] = dedup_mode
    seen["last_emission_id"] = boundary.get("emission_id")
    seen["last_timestamp"] = ts
    save_seen(seen)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
