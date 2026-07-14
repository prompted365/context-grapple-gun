#!/usr/bin/env python3
"""cadence-handoff-seal.py — PreToolUse:ExitPlanMode + PostToolUse:ExitPlanMode
                            + SessionStart reconciler (--reconcile-at-start)

HANDOFF SEAL (tic 633 plan-lifecycle split; tic 634 recovery-seam repair —
both Architect-directed).

The complement to cadence-interstitial-enter.py: the REAL plan exists only at
ExitPlanMode, so the handoff seal — plan hash, plan file path, activation mode
— is captured HERE, never at EnterPlanMode (where the former
cadence-plan-submit.py hashed synthesized text before the plan existed).

Lifecycle:
  PreToolUse:ExitPlanMode  → STAGE the seal (plan captured, hashed, activation
                             mode resolved; staged pre-approval at
                             audit-logs/hooks/handoff-seal-staged.json).
                             Plan capture is IDENTITY-VALIDATED at a live
                             boundary (t634 item 4): the captured text must be
                             THIS boundary's handoff (cgg-handoff entry_tic
                             match) or the capture is refused typed — never
                             seal a stale prior plan.
  PostToolUse:ExitPlanMode → MARK APPROVED (the tool returning means the user
                             acted on the plan): promote the staged seal to
                             audit-logs/hooks/handoff-seal-current.json +
                             append audit-logs/hooks/handoff-seals.jsonl
  SessionStart (session-restore.sh → this script --reconcile-at-start)
                           → RECONCILES + CONSUMES exactly once. PostToolUse
                             is NOT the sole promotion seam (t634 item 1):
                             when approval/background adoption skipped
                             PostToolUse, a staged seal is RECOVERED at
                             activation — promoted only with matching
                             emission_id + entry_tic against the live marker
                             AND plan-file approval evidence (t634 item 2),
                             never on an arbitrary SessionStart. Consumption
                             stamps consumed_at; the interstitial marker flips
                             active ONLY when its own boundary's seal is
                             consumed (t634 item 3 — a generic resume or
                             background SessionStart never clears it); the
                             pause-after-boot gate arms when activation.mode
                             == pause_after_boot.

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
import re
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


ZONE_ROOT = None
HOOK_STATE_DIR = None
STAGED_FILE = None
CURRENT_FILE = None
SEALS_LOG = None
PAUSE_NEXT_FILE = None
PAUSE_ACTIVE_FILE = None
INTERSTITIAL_MARKER = None


def bind_zone(zone_root):
    """Bind all governance paths to a verified zone root (or None)."""
    global ZONE_ROOT, HOOK_STATE_DIR, STAGED_FILE, CURRENT_FILE, SEALS_LOG
    global PAUSE_NEXT_FILE, PAUSE_ACTIVE_FILE, INTERSTITIAL_MARKER
    ZONE_ROOT = zone_root
    HOOK_STATE_DIR = (zone_root / "audit-logs" / "hooks") if zone_root else None
    STAGED_FILE = (HOOK_STATE_DIR / "handoff-seal-staged.json") if HOOK_STATE_DIR else None
    CURRENT_FILE = (HOOK_STATE_DIR / "handoff-seal-current.json") if HOOK_STATE_DIR else None
    SEALS_LOG = (HOOK_STATE_DIR / "handoff-seals.jsonl") if HOOK_STATE_DIR else None
    PAUSE_NEXT_FILE = (HOOK_STATE_DIR / "cadence-pause-next.json") if HOOK_STATE_DIR else None
    PAUSE_ACTIVE_FILE = (HOOK_STATE_DIR / "pause-after-boot-active.json") if HOOK_STATE_DIR else None
    INTERSTITIAL_MARKER = (zone_root / "audit-logs" / "tics" / ".interstitial-marker.json") if zone_root else None


bind_zone(resolve_zone_root(HOOK_DIR))


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


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_json(path) -> dict:
    if path is None or not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_boundary() -> dict:
    """Read the live interstitial marker (written by cadence-ops at emission)."""
    return _load_json(INTERSTITIAL_MARKER)


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


# ---------------------------------------------------------------------------
# Plan identity (t634 item 4) — the sealed plan must be THIS boundary's
# handoff, judged by the cgg-handoff block CONTENT, never by file name/path
# (the harness reuses the active plan file; a stale name can carry the right
# plan and vice versa — the tic-634 production incident proved both misreads).
# ---------------------------------------------------------------------------

HANDOFF_BLOCK_RE = re.compile(r"<!--\s*cgg-handoff(.*?)-->", re.DOTALL)


def parse_handoff_block(text: str) -> dict:
    """Parse the cgg-handoff comment block fields out of plan text."""
    m = HANDOFF_BLOCK_RE.search(text or "")
    if not m:
        return {}
    body = m.group(1)
    out = {}
    for key in ("handoff_id", "project_dir"):
        km = re.search(rf'{key}:\s*"?([^"\n]+?)"?\s*$', body, re.MULTILINE)
        if km:
            out[key] = km.group(1).strip()
    for key in ("work_tic", "entry_tic"):
        km = re.search(rf"{key}:\s*(\d+)", body)
        if km:
            out[key] = int(km.group(1))
    return out


def validate_plan_identity(plan_text: str, boundary: dict) -> dict:
    """Judge whether plan_text is the live boundary's handoff. Content-keyed."""
    entry_tic = boundary.get("entry_tic")
    if not plan_text:
        return {"status": "no_plan"}
    if entry_tic is None:
        return {"status": "no_live_boundary"}
    block = parse_handoff_block(plan_text)
    if not block:
        return {"status": "no_handoff_block", "expected_entry_tic": entry_tic}
    if block.get("entry_tic") != entry_tic:
        return {
            "status": "stale_prior_plan",
            "expected_entry_tic": entry_tic,
            "found_entry_tic": block.get("entry_tic"),
            "found_handoff_id": block.get("handoff_id"),
        }
    return {
        "status": "verified",
        "entry_tic": entry_tic,
        "work_tic": block.get("work_tic"),
        "handoff_id": block.get("handoff_id"),
    }


def _apply_plan_capture(seal: dict, plan_text: str, plan_file_path: str, boundary_bound: bool, boundary: dict) -> None:
    """Stamp plan capture onto a seal, FAIL-CLOSED at a live boundary.

    At a live boundary a plan that is not this boundary's handoff is refused
    typed (plan_captured=false + plan_capture_refusal forensics) — the
    activation field stays load-bearing regardless. Off-boundary captures are
    recorded as-is (audit honesty, nothing consumes them).
    """
    identity = validate_plan_identity(plan_text, boundary) if boundary_bound \
        else ({"status": "not_boundary_bound"} if plan_text else {"status": "no_plan"})
    seal["plan_identity"] = identity
    seal["plan_file_path"] = plan_file_path or None
    if boundary_bound and identity["status"] != "verified":
        seal["plan_captured"] = False
        seal["plan_hash"] = None
        seal["plan_chars"] = 0
        if plan_text:
            seal["plan_capture_refusal"] = {
                "reason": identity["status"],
                "refused_plan_hash": _sha16(plan_text),
                "refused_plan_chars": len(plan_text),
                **{k: v for k, v in identity.items() if k != "status"},
            }
        return
    seal["plan_captured"] = bool(plan_text)
    seal["plan_hash"] = _sha16(plan_text) if plan_text else None
    seal["plan_chars"] = len(plan_text)


# ---------------------------------------------------------------------------
# Approval evidence (t634 item 2) — a plan file on disk whose cgg-handoff
# block names THIS boundary's entry_tic. Plan approval auto-saves the plan;
# its presence with the matching block is the durable adoption evidence the
# recovery seam requires. Searched by CONTENT, capped for hook-latency safety.
# ---------------------------------------------------------------------------

def candidate_plan_dirs():
    dirs = [Path.home() / ".claude" / "plans"]
    if ZONE_ROOT is not None:
        project_key = str(ZONE_ROOT).replace("/", "-")
        dirs.append(Path.home() / ".claude" / "projects" / project_key)
    return [d for d in dirs if d.is_dir()]


def find_boundary_plan_file(entry_tic):
    """Locate the approved plan file for a boundary by cgg-handoff entry_tic."""
    if entry_tic is None:
        return None
    for d in candidate_plan_dirs():
        try:
            files = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:40]
        except OSError:
            continue
        for f in files:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if len(text) > 1_048_576:
                continue
            block = parse_handoff_block(text)
            if block.get("entry_tic") != entry_tic:
                continue
            pd = block.get("project_dir")
            if pd and ZONE_ROOT is not None and Path(pd) != ZONE_ROOT:
                continue
            return {"path": f, "text": text, "block": block}
    return None


# ---------------------------------------------------------------------------
# Hook handlers
# ---------------------------------------------------------------------------

def handle_pre(payload: dict) -> int:
    """PreToolUse:ExitPlanMode — stage the seal (pre-approval)."""
    plan_text, plan_file_path = extract_plan(payload)
    boundary = read_boundary()
    boundary_bound = boundary.get("state") == "interstitial"
    mode, pause_rec = resolve_activation_mode()

    now = datetime.now(timezone.utc).isoformat()
    staged = {
        "type": "handoff_seal",
        "stage": "staged_pre_approval",
        "staged_at": now,
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
    _apply_plan_capture(staged, plan_text, plan_file_path, boundary_bound, boundary)
    _atomic_write_json(STAGED_FILE, staged)
    return 0


def handle_post(payload: dict) -> int:
    """PostToolUse:ExitPlanMode — mark approved, promote staged → current."""
    now = datetime.now(timezone.utc).isoformat()
    boundary = read_boundary()

    staged = _load_json(STAGED_FILE)

    # The response may carry the plan (or its file path) the Pre stage didn't
    # have yet — adopt it under the same identity fail-closed discipline.
    plan_text, plan_file_path = extract_plan(payload)
    if staged:
        if plan_file_path and not staged.get("plan_file_path"):
            staged["plan_file_path"] = plan_file_path
        if plan_text and not staged.get("plan_hash"):
            _apply_plan_capture(staged, plan_text, staged.get("plan_file_path") or plan_file_path,
                                bool(staged.get("boundary_bound")), boundary)

    sealed = dict(staged) if staged else {
        "type": "handoff_seal",
        "boundary_bound": False,
        "activation": {"emission_id": None, "entry_tic": None, "mode": "continuous"},
        "note": "post fired with no staged record — seal assembled from post payload only",
        "plan_hash": _sha16(plan_text) if plan_text else None,
        "plan_captured": bool(plan_text),
        "plan_chars": len(plan_text),
        "plan_file_path": plan_file_path or None,
    }
    sealed["stage"] = "approved"
    sealed["approved_at"] = now
    sealed["promoted_by"] = "posttooluse"
    sealed["consumed_at"] = None
    sealed["consumed_by"] = None

    # History row always (audit honesty); current-pointer only when the seal is
    # bound to a live boundary WITH a real activation identity — there must be
    # a specific boundary for the next boot to match against (t634 item 2).
    _atomic_append_jsonl(SEALS_LOG, {"journal_event": "approved", **sealed})
    if sealed.get("boundary_bound") and (sealed.get("activation") or {}).get("emission_id"):
        _atomic_write_json(CURRENT_FILE, sealed)

    # The staged record is one-shot.
    try:
        if STAGED_FILE.is_file():
            STAGED_FILE.unlink()
    except OSError:
        pass
    return 0


# ---------------------------------------------------------------------------
# SessionStart reconciler (t634 items 1-3) — invoked by session-restore.sh as
#   cadence-handoff-seal.py --reconcile-at-start --zone-root <root> [--agent-id X]
# Prints the boot-injection message (possibly empty). Fail-soft: never blocks.
# ---------------------------------------------------------------------------

def handle_reconcile_at_start(agent_id: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    consumer = agent_id or "orchestrator_session_start"
    msg_parts = []

    marker = read_boundary()
    marker_em = marker.get("emission_id")

    current = _load_json(CURRENT_FILE)
    staged = _load_json(STAGED_FILE)

    consumed_seal = None

    # 1) Normal path: a PostToolUse-promoted seal awaits consumption.
    if current and current.get("consumed_at") is None:
        cur_em = (current.get("activation") or {}).get("emission_id")
        if marker_em is not None and cur_em is not None and cur_em != marker_em:
            _atomic_append_jsonl(SEALS_LOG, {
                "journal_event": "consume_refused",
                "reason": "different_active_boundary",
                "seal_emission_id": cur_em,
                "marker_emission_id": marker_em,
                "at": now,
            })
        else:
            current["consumed_at"] = now
            current["consumed_by"] = consumer
            _atomic_write_json(CURRENT_FILE, current)
            _atomic_append_jsonl(SEALS_LOG, {
                "journal_event": "consumed",
                "emission_id": cur_em,
                "entry_tic": (current.get("activation") or {}).get("entry_tic"),
                "consumed_by": consumer,
                "at": now,
            })
            consumed_seal = current

    # 2) Recovery seam (t634 item 1): PostToolUse skipped (approval into a
    #    background session / harness path without a Post fire) left the seal
    #    staged. Promote it ONLY for the matching live boundary with plan-file
    #    approval evidence (t634 item 2) — never on an arbitrary SessionStart.
    #    Eligible when no UNCONSUMED current seal competes — a consumed
    #    prior-boundary seal in current must not starve the next recovery.
    elif staged and (not current or current.get("consumed_at") is not None):
        st_act = staged.get("activation") or {}
        st_em = st_act.get("emission_id")
        st_entry = st_act.get("entry_tic")
        if marker_em is None or st_em is None or st_em != marker_em \
                or st_entry != marker.get("entry_tic"):
            _atomic_append_jsonl(SEALS_LOG, {
                "journal_event": "recovery_refused",
                "reason": "different_boundary",
                "staged_emission_id": st_em,
                "staged_entry_tic": st_entry,
                "marker_emission_id": marker_em,
                "marker_entry_tic": marker.get("entry_tic"),
                "at": now,
            })
        else:
            evidence = find_boundary_plan_file(st_entry)
            if evidence is None:
                _atomic_append_jsonl(SEALS_LOG, {
                    "journal_event": "recovery_refused",
                    "reason": "no_approval_evidence",
                    "staged_emission_id": st_em,
                    "staged_entry_tic": st_entry,
                    "at": now,
                })
            else:
                plan_text = evidence["text"]
                recovered_hash = _sha16(plan_text)
                staged_hash = staged.get("plan_hash")
                # Recovery acceptance evidence (four-case truth table, tic 635):
                #   absent   (staged hash None)  + exact-boundary plan verified -> ACCEPT
                #   match    (staged hash == recovered)                         -> ACCEPT
                #   mismatch (staged hash present, != recovered)                -> REJECT (the staged
                #     approval hash and recovered boundary-plan hash differ; cause — drift / tamper /
                #     stale capture / other — remains UNADJUDICATED)
                #   no approval evidence (no plan file)                         -> REJECT (handled above)
                # ABSENCE IS NOT CONTRADICTION: an absent staged hash is the
                # independent-verification accept path; only a PRESENT-and-different
                # hash is a mismatch refusal.
                staged_hash_state = (
                    "absent" if staged_hash is None
                    else "match" if staged_hash == recovered_hash
                    else "mismatch"
                )
                if staged_hash_state == "mismatch":
                    _atomic_append_jsonl(SEALS_LOG, {
                        "journal_event": "recovery_refused",
                        "reason": "plan_hash_mismatch",
                        "staged_hash_state": "mismatch",
                        "staged_emission_id": st_em,
                        "staged_entry_tic": st_entry,
                        "staged_plan_hash": staged_hash,
                        "recovered_plan_hash": recovered_hash,
                        "plan_file": str(evidence["path"]),
                        "at": now,
                    })
                    msg_parts.append(
                        f"[SEAL RECOVERY REFUSED] The staged handoff seal for {st_em} was NOT promoted: "
                        f"the staged approval hash and recovered boundary-plan hash differ "
                        f"(plan_hash_mismatch — staged {staged_hash} != recovered {recovered_hash}, "
                        f"{evidence['path'].name}); the cause (drift / tamper / stale capture / other) "
                        f"is UNADJUDICATED. The boundary REMAINS INTERSTITIAL and the pause was NOT armed; "
                        f"re-approve the plan to re-stage this boundary."
                    )
                else:
                    sealed = dict(staged)
                    sealed["stage"] = "approved"
                    sealed["approved_at"] = None
                    sealed["promoted_by"] = "sessionstart_recovery"
                    sealed["promoted_at"] = now
                    sealed["approval_evidence"] = {
                        "source": "plan_file_cgg_handoff_block",
                        "plan_file": str(evidence["path"]),
                        "handoff_id": evidence["block"].get("handoff_id"),
                        "entry_tic": st_entry,
                        "plan_hash_computed_at_recovery": recovered_hash,
                        "staged_plan_hash": staged_hash,
                        # absent -> null (NOT false — absence is not contradiction);
                        # match  -> true
                        "hash_matches_staged": True if staged_hash_state == "match" else None,
                        "staged_hash_state": staged_hash_state,
                    }
                    sealed["plan_captured"] = True
                    sealed["plan_hash"] = recovered_hash
                    sealed["plan_chars"] = len(plan_text)
                    sealed["plan_file_path"] = str(evidence["path"])
                    sealed["plan_identity"] = {
                        "status": "verified_at_recovery",
                        "entry_tic": st_entry,
                        "work_tic": evidence["block"].get("work_tic"),
                        "handoff_id": evidence["block"].get("handoff_id"),
                    }
                    sealed["consumed_at"] = now
                    sealed["consumed_by"] = consumer
                    _atomic_write_json(CURRENT_FILE, sealed)
                    _atomic_append_jsonl(SEALS_LOG, {"journal_event": "recovery_promoted", **sealed})
                    try:
                        STAGED_FILE.unlink()
                    except OSError:
                        pass
                    consumed_seal = sealed
                    msg_parts.append(
                        f"[SEAL RECOVERED] The staged handoff seal for {st_em} was promoted+consumed "
                        f"at SessionStart (PostToolUse:ExitPlanMode not observed this boundary; "
                        f"staged_hash_state={staged_hash_state}); approval evidence: "
                        f"{evidence['path'].name} (cgg-handoff entry_tic {st_entry})."
                    )

    # 3) Pause arming + marker flip — driven ONLY by a seal consumed for the
    #    matching boundary. A generic resume/background SessionStart with no
    #    matching seal leaves the interstitial marker untouched (t634 item 3).
    if consumed_seal is not None:
        act = consumed_seal.get("activation") or {}
        if act.get("mode") == "pause_after_boot":
            _atomic_write_json(PAUSE_ACTIVE_FILE, {
                "armed_at": now,
                "emission_id": act.get("emission_id"),
                "entry_tic": act.get("entry_tic"),
                "source_seal_approved_at": consumed_seal.get("approved_at"),
                "source_seal_promoted_by": consumed_seal.get("promoted_by"),
            })
            msg_parts.append(
                "[ACTIVATION: pause_after_boot] The sealed handoff opted into a paused boot "
                "(one-boundary override). Hydration proceeds; the activation fabric will NOT "
                "consume the mandate, start the assessor, launch workflows, or delegate until "
                "a real explicit 'continue' opens the gate. Report: hydrated and paused."
            )
        if marker and marker.get("emission_id") == act.get("emission_id"):
            if marker.get("state") == "interstitial":
                marker["state"] = "active"
                marker["activated_at"] = now
                marker["activated_by"] = f"{consumer}+seal_consumption"
                _atomic_write_json(INTERSTITIAL_MARKER, marker)
            else:
                marker["activation_verified_at"] = now
                marker["activation_verified_by"] = f"{consumer}+seal_consumption"
                _atomic_write_json(INTERSTITIAL_MARKER, marker)

    print(" ".join(msg_parts))
    return 0


def main():
    argv = sys.argv[1:]

    if "--reconcile-at-start" in argv:
        # The SessionStart reconciler passes the resolved zone root explicitly
        # (the installed hook copy has no .ticzone above it; walk-up would
        # otherwise depend on cwd). Fail-closed: an override without .ticzone
        # is ignored and the import-time resolution stands.
        if "--zone-root" in argv:
            try:
                zr = Path(argv[argv.index("--zone-root") + 1])
                if (zr / ".ticzone").is_file():
                    bind_zone(zr)
            except (IndexError, OSError):
                pass
        agent_id = ""
        if "--agent-id" in argv:
            try:
                agent_id = argv[argv.index("--agent-id") + 1]
            except IndexError:
                agent_id = ""
        if ZONE_ROOT is None:
            sys.stderr.write(
                "[cadence-handoff-seal] zone root unresolved (.ticzone not found); "
                "skipping seal reconcile, not blocking boot.\n"
            )
            return 0
        return handle_reconcile_at_start(agent_id)

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
