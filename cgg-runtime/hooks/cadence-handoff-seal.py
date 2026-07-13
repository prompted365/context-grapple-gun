#!/usr/bin/env python3
"""cadence-handoff-seal.py — PreToolUse:ExitPlanMode + PostToolUse:ExitPlanMode

HANDOFF SEAL (tic 633 plan-lifecycle split — Architect-directed repair).

The complement to cadence-interstitial-enter.py: the REAL plan exists only at
ExitPlanMode, so the handoff seal — plan hash, plan file path, activation mode
— is captured HERE, never at EnterPlanMode (where the former
cadence-plan-submit.py hashed synthesized text before the plan existed).

Lifecycle:
  PreToolUse:ExitPlanMode  → STAGE the seal (plan captured, hashed, activation
                             mode resolved; staged pre-approval at
                             audit-logs/hooks/handoff-seal-staged.json)
  PostToolUse:ExitPlanMode → MARK APPROVED (the tool returning means the user
                             acted on the plan): promote the staged seal to
                             audit-logs/hooks/handoff-seal-current.json +
                             append audit-logs/hooks/handoff-seals.jsonl
  SessionStart (session-restore.sh) → RECONCILES + CONSUMES exactly once
                             (stamps consumed_at; flips the interstitial
                             marker active; arms the pause-after-boot gate
                             when activation.mode == pause_after_boot)

Activation field (t632 directive §5):
  activation: {emission_id, entry_tic, mode}
  mode = "continuous" (DEFAULT — today's behavior, unchanged) |
         "pause_after_boot" (STRICTLY OPT-IN, one-boundary override armed via
         `/cadence pause-next` → audit-logs/hooks/cadence-pause-next.json;
         consumed HERE at seal time — no saved/global preference exists)

Boundary-bound discrimination: a seal is boundary-bound only when the
interstitial marker is live (state=interstitial). An ExitPlanMode with no live
boundary (ordinary mid-tic plan mode) is still logged to the seals history for
audit honesty, but does NOT write handoff-seal-current.json — there is nothing
for the next boot to consume.

Tic/tdelta/git-cycle/ReBru live in the interstitial-entry hook — NOT here
(t632 directive §4: do not move them into ExitPlanMode).
"""

import fcntl
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent


def resolve_zone_root(start: Path):
    """Fail-closed zone-root resolution (same discipline as the sibling hooks)."""
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


ZONE_ROOT = resolve_zone_root(HOOK_DIR)

HOOK_STATE_DIR = (ZONE_ROOT / "audit-logs" / "hooks") if ZONE_ROOT else None
STAGED_FILE = (HOOK_STATE_DIR / "handoff-seal-staged.json") if HOOK_STATE_DIR else None
CURRENT_FILE = (HOOK_STATE_DIR / "handoff-seal-current.json") if HOOK_STATE_DIR else None
SEALS_LOG = (HOOK_STATE_DIR / "handoff-seals.jsonl") if HOOK_STATE_DIR else None
PAUSE_NEXT_FILE = (HOOK_STATE_DIR / "cadence-pause-next.json") if HOOK_STATE_DIR else None
INTERSTITIAL_MARKER = (ZONE_ROOT / "audit-logs" / "tics" / ".interstitial-marker.json") if ZONE_ROOT else None


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


def read_boundary() -> dict:
    """Read the live interstitial marker (written by cadence-ops at emission)."""
    if INTERSTITIAL_MARKER is None or not INTERSTITIAL_MARKER.is_file():
        return {}
    try:
        m = json.loads(INTERSTITIAL_MARKER.read_text(encoding="utf-8"))
        return m if isinstance(m, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def resolve_activation_mode() -> tuple:
    """Resolve activation mode + consume the one-boundary pause-next override.

    Returns (mode, pause_next_record_or_None). Consumption (file removal)
    happens at STAGE time — the override is one-boundary by construction: it
    binds to the seal being staged now and can never leak to a later boundary.
    No saved/global preference exists or is consulted (t632 directive §5).
    """
    if PAUSE_NEXT_FILE is not None and PAUSE_NEXT_FILE.is_file():
        try:
            rec = json.loads(PAUSE_NEXT_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rec = {"unreadable": True}
        try:
            PAUSE_NEXT_FILE.unlink()
        except OSError:
            pass
        return "pause_after_boot", rec
    return "continuous", None


def extract_plan(payload: dict) -> tuple:
    """Extract (plan_text, plan_file_path) from a hook payload, defensively.

    Claude Code injects the real plan (and, on current harnesses, the plan
    file path) into the ExitPlanMode tool input / response. Key names have
    drifted across harness versions (Epistemic Volatility Notice), so probe
    the known candidates in both tool_input and tool_response.
    """
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    if not isinstance(tool_response, dict):
        tool_response = {}

    plan_text = ""
    for src in (tool_input, tool_response, payload):
        if not isinstance(src, dict):
            continue
        for key in ("plan", "planText", "plan_text"):
            v = src.get(key)
            if isinstance(v, str) and v.strip():
                plan_text = v
                break
        if plan_text:
            break

    plan_file_path = ""
    for src in (tool_input, tool_response, payload):
        if not isinstance(src, dict):
            continue
        for key in ("planFilePath", "plan_file_path", "planPath", "plan_path", "filePath"):
            v = src.get(key)
            if isinstance(v, str) and v.strip():
                plan_file_path = v
                break
        if plan_file_path:
            break

    return plan_text, plan_file_path


def handle_pre(payload: dict) -> int:
    """PreToolUse:ExitPlanMode — stage the seal (pre-approval)."""
    plan_text, plan_file_path = extract_plan(payload)
    boundary = read_boundary()
    boundary_bound = boundary.get("state") == "interstitial"
    mode, pause_rec = resolve_activation_mode()

    now = datetime.now(timezone.utc).isoformat()
    plan_hash = hashlib.sha256(plan_text.encode("utf-8")).hexdigest()[:16] if plan_text else None

    staged = {
        "type": "handoff_seal",
        "stage": "staged_pre_approval",
        "staged_at": now,
        "plan_hash": plan_hash,
        "plan_captured": bool(plan_text),
        "plan_chars": len(plan_text),
        "plan_file_path": plan_file_path or None,
        "boundary_bound": boundary_bound,
        "activation": {
            "emission_id": boundary.get("emission_id"),
            "entry_tic": boundary.get("entry_tic"),
            "mode": mode,
        },
        "pause_next_consumed": pause_rec,
        "session_id": payload.get("session_id") or "",
        "agent_id": payload.get("agent_id") or "",
    }
    _atomic_write_json(STAGED_FILE, staged)
    return 0


def handle_post(payload: dict) -> int:
    """PostToolUse:ExitPlanMode — mark approved, promote staged → current."""
    now = datetime.now(timezone.utc).isoformat()

    staged = {}
    if STAGED_FILE.is_file():
        try:
            staged = json.loads(STAGED_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            staged = {}

    # The response may carry the plan file path the Pre stage didn't have yet.
    plan_text, plan_file_path = extract_plan(payload)
    if plan_file_path and not staged.get("plan_file_path"):
        staged["plan_file_path"] = plan_file_path
    if plan_text and not staged.get("plan_hash"):
        staged["plan_hash"] = hashlib.sha256(plan_text.encode("utf-8")).hexdigest()[:16]
        staged["plan_captured"] = True
        staged["plan_chars"] = len(plan_text)

    sealed = dict(staged) if staged else {
        "type": "handoff_seal",
        "boundary_bound": False,
        "activation": {"emission_id": None, "entry_tic": None, "mode": "continuous"},
        "note": "post fired with no staged record — seal assembled from post payload only",
        "plan_hash": (hashlib.sha256(plan_text.encode("utf-8")).hexdigest()[:16]
                      if plan_text else None),
        "plan_file_path": plan_file_path or None,
    }
    sealed["stage"] = "approved"
    sealed["approved_at"] = now
    sealed["consumed_at"] = None
    sealed["consumed_by"] = None

    # History row always (audit honesty), current-pointer only when the seal is
    # bound to a live boundary — otherwise there is nothing to consume at boot.
    _atomic_append_jsonl(SEALS_LOG, sealed)
    if sealed.get("boundary_bound"):
        _atomic_write_json(CURRENT_FILE, sealed)

    # The staged record is one-shot.
    try:
        if STAGED_FILE.is_file():
            STAGED_FILE.unlink()
    except OSError:
        pass
    return 0


def main():
    try:
        payload_raw = sys.stdin.read()
        payload = json.loads(payload_raw) if payload_raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    if ZONE_ROOT is None:
        sys.stderr.write(
            "[cadence-handoff-seal] zone root unresolved (.ticzone not found); "
            "skipping seal writes, not blocking ExitPlanMode.\n"
        )
        return 0

    event = (payload.get("hook_event_name") or payload.get("hookEventName") or "").strip()
    if event == "PreToolUse":
        return handle_pre(payload)
    if event == "PostToolUse":
        return handle_post(payload)

    # Unknown/missing event name: infer from payload shape — a tool_response
    # present means post; otherwise treat as pre. Fail-soft either way.
    if payload.get("tool_response") is not None:
        return handle_post(payload)
    return handle_pre(payload)


if __name__ == "__main__":
    raise SystemExit(main())
