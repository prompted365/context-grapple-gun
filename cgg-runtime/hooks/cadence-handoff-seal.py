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

PAYLOAD MODE (tic 804, /review-803 Deliverable 2 — LANDED INERT):
  One switch, cgg-runtime/config/handoff-payload-mode.json, single key
  `handoff_payload_mode` valued "body" | "pointer", landed as "body".
  ABSENT / UNREADABLE / MALFORMED MEANS "body" — this hook fails to the OLD
  path and says so on stderr. In "body" mode this hook's behaviour and every
  byte it journals are UNCHANGED: no mode key is written, so no historical or
  future body-mode row changes shape. In "pointer" mode plan_hash binds the
  DURABLE HOME's content hash — carried in the payload and RE-COMPUTED from the
  file; a carried hash that does not match the file is a REFUSAL, fail-closed
  and loud — payload_chars is recorded separately from plan_chars, and a pointer
  whose durable home is MISSING is REFUSED with a typed reason. The first
  pointer-mode row is the series EPOCH MARKER (forward-only, never backfilled).

**Does-not-satisfy rider (travels verbatim):** this increment does NOT remove or replace the local harness patch, does NOT rule which promoter is the seal seam's ordinary path (the tic-801 born, /review 804), does NOT cure the injected-plan-prompt dispatch gap (the tic-802 born, /review 805), and does NOT make any claim that the approval surface's budget is fixed across future harness versions — the born measured five versions and the pointer is chosen precisely so that the question stops mattering.

This seat's addition (ent_harpoon_build_citizen, tic 804 — MINE, not the
ruling's): this increment lands the pointer path INERT. No live boundary has
been carried on it. A fixture rollback is not a live rollback. The new path may
not become the default until the drill has passed.
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


# ---------------------------------------------------------------------------
# PAYLOAD MODE — the one switch (tic 804, D2 landed INERT).
# Every reader FAILS TO BODY (the old path) on absent / unreadable / malformed.
# ---------------------------------------------------------------------------

PAYLOAD_MODE_BODY = "body"
PAYLOAD_MODE_POINTER = "pointer"
PAYLOAD_MODE_KEY = "handoff_payload_mode"
PAYLOAD_MODE_CONFIG_ENV = "CGG_HANDOFF_PAYLOAD_MODE_CONFIG"


def payload_mode_config_candidates():
    """Config loci, in precedence order. The env override is the FIXTURE SEAM —
    it is how a drill flips the switch inside a tempfile zone without ever
    touching the real one. It is not a configuration framework: one key, one
    file, three places to find it."""
    out = []
    env = os.environ.get(PAYLOAD_MODE_CONFIG_ENV)
    if env:
        out.append(Path(env))
    out.append(HOOK_DIR.parent / "config" / "handoff-payload-mode.json")
    out.append(Path.home() / ".claude" / "cgg-runtime" / "config" / "handoff-payload-mode.json")
    return out


def resolve_payload_mode() -> tuple:
    """Return (mode, reason). Absent/unreadable/malformed -> ("body", reason) + stderr."""
    for p in payload_mode_config_candidates():
        try:
            if not p.is_file():
                continue
        except OSError:
            continue
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            sys.stderr.write(
                f"[cadence-handoff-seal] payload-mode switch at {p} is UNREADABLE/MALFORMED "
                f"({exc.__class__.__name__}); failing to '{PAYLOAD_MODE_BODY}' — the OLD path.\n")
            return PAYLOAD_MODE_BODY, f"malformed:{p}"
        if not isinstance(obj, dict):
            sys.stderr.write(
                f"[cadence-handoff-seal] payload-mode switch at {p} is not a JSON object; "
                f"failing to '{PAYLOAD_MODE_BODY}' — the OLD path.\n")
            return PAYLOAD_MODE_BODY, f"malformed_not_object:{p}"
        val = obj.get(PAYLOAD_MODE_KEY)
        if val == PAYLOAD_MODE_POINTER:
            return PAYLOAD_MODE_POINTER, f"configured:{p}"
        if val == PAYLOAD_MODE_BODY:
            return PAYLOAD_MODE_BODY, f"configured:{p}"
        sys.stderr.write(
            f"[cadence-handoff-seal] payload-mode switch at {p} carries an unrecognized "
            f"{PAYLOAD_MODE_KEY}={val!r}; failing to '{PAYLOAD_MODE_BODY}' — the OLD path.\n")
        return PAYLOAD_MODE_BODY, f"unrecognized_value:{val!r}"
    sys.stderr.write(
        f"[cadence-handoff-seal] payload-mode switch ABSENT; meaning '{PAYLOAD_MODE_BODY}' "
        f"— the OLD path.\n")
    return PAYLOAD_MODE_BODY, "absent"


# ---------------------------------------------------------------------------
# THE DURABLE HOME (Candidate A, ruled by the D1 manifest) — audit-logs/handoffs/.
# Sited OUTSIDE both directories candidate_plan_dirs() globs, on purpose: siting
# it inside either makes two files carry the same cgg-handoff entry_tic and the
# mtime sort below goes nondeterministic (F-804-D1-4).
# ---------------------------------------------------------------------------

DURABLE_HOME_RELDIR = "audit-logs/handoffs"
_DURABLE_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def durable_home_filename(entry_tic, handoff_id) -> str:
    """PURE function (entry_tic, handoff_id) -> filename-safe key. No I/O.

    A handoff id carries colons ("2026-09-19T13:12:00Z-..."), so every character
    outside [A-Za-z0-9._-] sanitizes to '-'. Sanitization is lossy, so an 8-hex
    digest of the RAW id is appended: two ids that sanitize alike can never
    collide on one filename."""
    raw = "" if handoff_id is None else str(handoff_id)
    slug = _DURABLE_UNSAFE_RE.sub("-", raw).strip("-")[:80].strip("-") or "unnamed"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    tic = entry_tic if isinstance(entry_tic, int) else "na"
    return f"{tic}-{slug}-{digest}.md"


def durable_home_relpath(entry_tic, handoff_id) -> str:
    return f"{DURABLE_HOME_RELDIR}/{durable_home_filename(entry_tic, handoff_id)}"


def resolve_durable_home(rel_or_abs):
    """Resolve a durable-home reference to an EXISTING file, or (None, why)."""
    if not rel_or_abs:
        return None, "no_durable_home_in_pointer_block"
    p = Path(rel_or_abs)
    cands = [p] if p.is_absolute() else []
    if not p.is_absolute() and ZONE_ROOT is not None:
        cands.append(ZONE_ROOT / p)
    for c in cands:
        try:
            if c.is_file():
                return c, "resolved"
        except OSError:
            continue
    return None, f"not_found:{rel_or_abs}"


# ---------------------------------------------------------------------------
# THE POINTER PAYLOAD.
#
# B13 — THE SUCCESSOR SESSION — is the consumer with NO call site. It cannot be
# re-pointed by code or config; only the payload's own first words can oblige it.
# SUCCESSOR_IMPERATIVE is ONE CONTIGUOUS CONSTANT, quoted by the cadence skill and
# tested for verbatim survival into a composed payload. THIS CONSUMER IS SERVED BY
# PERSUASION, NOT BY MECHANISM.
# ---------------------------------------------------------------------------

SUCCESSOR_IMPERATIVE = (
    "STOP — THIS IS A POINTER, NOT THE PLAN.\n"
    "Before any other action, before answering, and before any tool call other than\n"
    "the one named here: open the durable home named below, read it IN FULL and\n"
    "GAPLESS, and verify its content hash equals the hash named below. THAT document\n"
    "is your plan and your charter; everything else in this payload is only the\n"
    "envelope that carries its address, and the summary below is NOT the plan.\n"
    "If the durable home cannot be opened, or its hash does not match, STOP and report\n"
    "a broken handoff pointer — do NOT proceed from the summary, and do NOT\n"
    "reconstruct the plan from memory."
)

POINTER_BLOCK_RE = re.compile(r"<!--\s*cgg-handoff-pointer(.*?)-->", re.DOTALL)
HANDOFF_BLOCK_FULL_RE = re.compile(r"<!--\s*cgg-handoff\b(?!-pointer).*?-->", re.DOTALL)
EVALUATE_BLOCK_FULL_RE = re.compile(r"<!--\s*cgg-evaluate\b.*?-->", re.DOTALL)
POINTER_SUMMARY_MAX_CHARS = 1200


def parse_pointer_block(text: str) -> dict:
    """Parse the cgg-handoff-pointer block out of a payload."""
    m = POINTER_BLOCK_RE.search(text or "")
    if not m:
        return {}
    body = m.group(1)
    out = {}
    for key in ("payload_mode", "durable_home", "handoff_id", "content_sha16"):
        km = re.search(rf'{key}:\s*"?([^"\n]+?)"?\s*$', body, re.MULTILINE)
        if km:
            out[key] = km.group(1).strip()
    for key in ("entry_tic", "body_chars"):
        km = re.search(rf"{key}:\s*(\d+)", body)
        if km:
            out[key] = int(km.group(1))
    return out


def bounded_summary(body_text: str, limit: int = POINTER_SUMMARY_MAX_CHARS) -> str:
    """A BOUNDED extract of the body with the machine blocks stripped."""
    stripped = EVALUATE_BLOCK_FULL_RE.sub("", HANDOFF_BLOCK_FULL_RE.sub("", body_text or ""))
    lines = [ln for ln in stripped.splitlines() if ln.strip()]
    out, total = [], 0
    for ln in lines:
        if total + len(ln) + 1 > limit:
            out.append(f"... [bounded summary truncated at {limit} chars — "
                       f"the FULL plan is at the durable home above]")
            break
        out.append(ln)
        total += len(ln) + 1
    return "\n".join(out)


def compose_pointer_payload(body_text, entry_tic, handoff_id, durable_rel, content_hash) -> str:
    """Compose the payload handed to the approval surface: the imperative FIRST,
    the durable-home path, the handoff id, the content hash, a BOUNDED summary,
    and BOTH machine blocks VERBATIM (every marker-referencer is untouched)."""
    hb = HANDOFF_BLOCK_FULL_RE.search(body_text or "")
    eb = EVALUATE_BLOCK_FULL_RE.search(body_text or "")
    parts = [
        SUCCESSOR_IMPERATIVE,
        "",
        "<!-- cgg-handoff-pointer",
        f'  payload_mode: "{PAYLOAD_MODE_POINTER}"',
        f'  durable_home: "{durable_rel}"',
        f'  handoff_id: "{handoff_id}"',
        f"  entry_tic: {entry_tic}",
        f'  content_sha16: "{content_hash}"',
        f"  body_chars: {len(body_text or '')}",
        "-->",
        "",
        "## Bounded summary — NOT the plan. The plan is the durable home named above.",
        "",
        bounded_summary(body_text),
        "",
    ]
    if hb:
        parts += [hb.group(0), ""]
    if eb:
        parts += [eb.group(0), ""]
    return "\n".join(parts)


def write_durable_home(zone_root, body_text, entry_tic, handoff_id):
    """Write the body to its durable home and PROVE it landed (read back + re-hash).

    Returns (abs_path, rel_path, content_hash) or raises. The caller falls back to
    BODY mode on any failure: a pointer is never submitted to a home that does not
    hold its body."""
    rel = durable_home_relpath(entry_tic, handoff_id)
    dest = Path(zone_root) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(body_text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dest)
    readback = dest.read_text(encoding="utf-8")
    content_hash = _sha16(readback)
    if readback != body_text:
        raise OSError(f"durable-home readback differs from body at {dest}")
    return dest, rel, content_hash


def _is_first_pointer_row() -> bool:
    """True when no pointer-mode row exists in this journal yet."""
    try:
        if SEALS_LOG is None or not SEALS_LOG.is_file():
            return True
        with SEALS_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "payload_mode" not in line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("payload_mode") == PAYLOAD_MODE_POINTER:
                    return False
    except OSError:
        return False
    return True


def _epoch_annotated(row: dict) -> dict:
    """Stamp the SERIES EPOCH MARKER on the first pointer-mode row. FORWARD-ONLY:
    historical body-mode rows are never backfilled. In BODY mode this returns the
    row untouched and reads nothing — body-mode rows keep their exact shape."""
    if row.get("payload_mode") != PAYLOAD_MODE_POINTER:
        return row
    if not _is_first_pointer_row():
        return row
    out = dict(row)
    out["payload_mode_epoch"] = {
        "series": "handoff_seal.plan_hash+plan_chars",
        "epoch": PAYLOAD_MODE_POINTER,
        "first_pointer_row": True,
        "note": ("FIRST pointer-mode row in this journal. From here plan_hash binds the "
                 "DURABLE HOME's content and plan_chars measures the durable body; "
                 "payload_chars carries the approval payload's size. Forward-only — "
                 "historical body-mode rows are NEVER backfilled and a longitudinal "
                 "read of plan_chars must break the series at this row."),
        "stamped_at": datetime.now(timezone.utc).isoformat(),
    }
    return out


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
    # Fallback: derive tic numbers from the handoff_id when the explicit block
    # fields are absent. The SKILL handoff template historically named only
    # handoff_id/project_dir/trigger_version/generated_at, so an author could
    # omit entry_tic and the seal would refuse to bind — leaving the interstitial
    # marker stuck (tic-636 stuck-marker incident). handoff_id encodes both tics:
    # "...-tic{work}-close-for-tic{entry}-entry".
    if out.get("handoff_id") and ("entry_tic" not in out or "work_tic" not in out):
        hm = re.search(r"tic(\d+)-close-for-tic(\d+)-entry", out["handoff_id"])
        if hm:
            out.setdefault("work_tic", int(hm.group(1)))
            out.setdefault("entry_tic", int(hm.group(2)))
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
    mode, mode_reason = resolve_payload_mode()
    if mode == PAYLOAD_MODE_POINTER:
        _apply_pointer_capture(seal, plan_text, mode_reason)
        return
    # BODY MODE — byte-identical to the pre-tic-804 path. No mode key is written,
    # so no historical or future body-mode row changes shape.
    seal["plan_captured"] = bool(plan_text)
    seal["plan_hash"] = _sha16(plan_text) if plan_text else None
    seal["plan_chars"] = len(plan_text)


def _apply_pointer_capture(seal: dict, payload_text: str, mode_reason: str) -> None:
    """POINTER MODE capture. plan_hash binds the DURABLE HOME's content, RE-COMPUTED
    from the file; a carried hash that does not match the file is a REFUSAL,
    fail-closed and loud. A pointer whose durable home is MISSING is REFUSED with a
    typed reason — the pre-approval write's failure story."""
    ptr = parse_pointer_block(payload_text)
    seal["payload_chars"] = len(payload_text or "")
    if not ptr:
        # The switch says pointer but the payload carries no pointer block: it IS a
        # body payload. Bind body semantics and say so — never silently mislabel.
        seal["payload_mode"] = PAYLOAD_MODE_BODY
        seal["payload_mode_degraded"] = "no_pointer_block_in_payload_bound_as_body"
        seal["plan_captured"] = bool(payload_text)
        seal["plan_hash"] = _sha16(payload_text) if payload_text else None
        seal["plan_chars"] = len(payload_text or "")
        sys.stderr.write("[cadence-handoff-seal] payload-mode is 'pointer' but the payload "
                         "carries no cgg-handoff-pointer block; bound as BODY.\n")
        return
    seal["payload_mode"] = PAYLOAD_MODE_POINTER
    seal["payload_mode_source"] = mode_reason
    seal["durable_home"] = ptr.get("durable_home")
    resolved, why = resolve_durable_home(ptr.get("durable_home"))
    if resolved is None:
        seal["plan_captured"] = False
        seal["plan_hash"] = None
        seal["plan_chars"] = 0
        seal["plan_capture_refusal"] = {
            "reason": "pointer_durable_home_missing",
            "durable_home": ptr.get("durable_home"),
            "resolution": why,
            "carried_content_sha16": ptr.get("content_sha16"),
        }
        sys.stderr.write(f"[cadence-handoff-seal] REFUSED: pointer payload names a durable home "
                         f"that does not exist ({ptr.get('durable_home')!r}); {why}. A pointer is "
                         f"never sealed against a home that does not hold its body.\n")
        return
    try:
        body = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        seal["plan_captured"] = False
        seal["plan_hash"] = None
        seal["plan_chars"] = 0
        seal["plan_capture_refusal"] = {
            "reason": "pointer_durable_home_unreadable",
            "durable_home": str(resolved),
            "error": exc.__class__.__name__,
        }
        sys.stderr.write(f"[cadence-handoff-seal] REFUSED: durable home {resolved} unreadable "
                         f"({exc.__class__.__name__}).\n")
        return
    recomputed = _sha16(body)
    carried = ptr.get("content_sha16")
    if carried and carried != recomputed:
        seal["plan_captured"] = False
        seal["plan_hash"] = None
        seal["plan_chars"] = 0
        seal["plan_capture_refusal"] = {
            "reason": "pointer_content_hash_mismatch",
            "durable_home": str(resolved),
            "carried_content_sha16": carried,
            "recomputed_content_sha16": recomputed,
        }
        sys.stderr.write(f"[cadence-handoff-seal] REFUSED: pointer carries content_sha16 {carried} "
                         f"but {resolved} hashes to {recomputed}. Fail-closed.\n")
        return
    seal["plan_captured"] = True
    seal["plan_hash"] = recomputed
    seal["plan_chars"] = len(body)
    seal["durable_home_resolved"] = str(resolved)


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
    _atomic_append_jsonl(SEALS_LOG, _epoch_annotated({"journal_event": "approved", **sealed}))
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

# ---------------------------------------------------------------------------
# Actor discrimination (tic-799 born -> /review 802 Q5, the THIRD BOOT KIND face
# of cgg-ledger#boot-seam-duality-primary-sessionstart-citizens-subagentstart).
#
# A mogul-runner `claude -p` child is a TOP-LEVEL session: it boots through
# SessionStart -- the PRIMARY's seam, not SubagentStart -- carrying an EMPTY
# payload agent_id, so it satisfies every predicate the primary would and
# consumed the primary's seal (measured at the entry-tic-800 boundary:
# consumed_by orchestrator_session_start at 04:40:53Z, 44 s after the headless
# child logged Status -> running at 04:40:09Z). The runner exports its
# obligation identity into that child's environment before spawning it, so a
# discriminator was present at this seam and unread.
#
# Only an empty agent_id with NO obligation environment is the primary. The
# obligation ids are a LABEL source and are never trusted as authority; it is
# their ABSENCE that makes the primary the primary.
#
# Lock line: whoever boots first is not thereby the primary; the seal asks who.
# ---------------------------------------------------------------------------

OBLIGATION_MANDATE_ENV = "CGG_OBLIGATION_MANDATE_ID"
OBLIGATION_TIC_ENV = "CGG_OBLIGATION_TIC"


def derive_actor(agent_id: str) -> dict:
    """Derive the reconcile actor; only the primary may consume a seal.

    Three boot kinds reach this seam:
      subagent         -- non-empty payload agent_id (a subagent context)
      headless_citizen -- empty agent_id + the runner's obligation environment
      primary          -- empty agent_id AND no obligation environment
    """
    mandate_id = (os.environ.get(OBLIGATION_MANDATE_ENV) or "").strip()
    obligation_tic = (os.environ.get(OBLIGATION_TIC_ENV) or "").strip()
    agent_id = (agent_id or "").strip()

    if agent_id:
        # A subagent context reaching this seam is non-primary whether or not it
        # also carries an obligation environment; both discriminators recorded.
        return {
            "actor": "subagent:" + agent_id,
            "actor_class": "subagent",
            "is_primary": False,
            "agent_id": agent_id,
            "obligation_mandate_id": mandate_id or None,
            "obligation_tic": obligation_tic or None,
        }
    if mandate_id:
        return {
            "actor": "headless_citizen:" + mandate_id,
            "actor_class": "headless_citizen",
            "is_primary": False,
            "agent_id": "",
            "obligation_mandate_id": mandate_id,
            "obligation_tic": obligation_tic or None,
        }
    return {
        "actor": "orchestrator_session_start",
        "actor_class": "primary",
        "is_primary": True,
        "agent_id": "",
        "obligation_mandate_id": None,
        "obligation_tic": obligation_tic or None,
    }


def handle_reconcile_at_start(agent_id: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    actor = derive_actor(agent_id)
    consumer = actor["actor"]
    msg_parts = []

    marker = read_boundary()
    marker_em = marker.get("emission_id")

    current = _load_json(CURRENT_FILE)
    staged = _load_json(STAGED_FILE)

    # ----------------------------------------------------------------------
    # REFUSAL BRANCH (tic-799 born, ruled /review 802 Q5). A non-primary actor
    # RECORDS its sighting and consumes NOTHING: the staged/current seal is left
    # BYTE-IDENTICAL for the primary, and the interstitial marker is NOT
    # activated -- marker activation below is driven solely by consumed_seal,
    # which stays None on this path, so refusal leaves the primary's boundary
    # unarmed rather than half-armed. With no seal pending, a non-primary boot
    # writes NOTHING AT ALL: a citizen boot must not drop a noise row into the
    # journal on every spawn. consumed_by on a real consumption now names an
    # actor a non-primary could not have produced.
    #
    # DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT rule or
    # cure which promoter is the seam's ordinary path (the PostToolUse promoter
    # versus the SessionStart recovery seam), does NOT touch the PostToolUse
    # promoter, and does NOT retire the recovery_promoted label; a sibling born
    # adjudicates that at its own round. It also does NOT prove the installed
    # hook carries the cure -- that is the seat's sync-and-verify motion after
    # the commit.
    # ----------------------------------------------------------------------
    if not actor["is_primary"]:
        pending = None
        if current and current.get("consumed_at") is None:
            pending = current
        elif staged and (not current or current.get("consumed_at") is not None):
            pending = staged
        if pending is not None:
            pend_act = pending.get("activation") or {}
            _atomic_append_jsonl(SEALS_LOG, {
                "journal_event": "consume_refused",
                "reason": "non_primary_actor",
                "actor": actor["actor"],
                "actor_class": actor["actor_class"],
                "agent_id": actor["agent_id"],
                "obligation_mandate_id": actor["obligation_mandate_id"],
                "obligation_tic": actor["obligation_tic"],
                "seal_emission_id": pend_act.get("emission_id"),
                "seal_entry_tic": pend_act.get("entry_tic"),
                "seal_stage": pending.get("stage"),
                "marker_emission_id": marker_em,
                "at": now,
            })
        print("")
        return 0

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
                recovered_hash, rec_pointer, rec_refusal = _recover_binding(plan_text)
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
                if rec_refusal is not None:
                    # POINTER MODE: the recovered plan file is a pointer whose durable
                    # home is missing / unreadable / hash-divergent. REFUSE, typed.
                    _atomic_append_jsonl(SEALS_LOG, {
                        "journal_event": "recovery_refused",
                        "staged_emission_id": st_em,
                        "staged_entry_tic": st_entry,
                        "plan_file": str(evidence["path"]),
                        "payload_mode": PAYLOAD_MODE_POINTER,
                        "at": now,
                        **rec_refusal,
                    })
                    msg_parts.append(
                        f"[SEAL RECOVERY REFUSED] The staged handoff seal for {st_em} was NOT "
                        f"promoted: the approved payload is a POINTER and its durable home did "
                        f"not verify ({rec_refusal.get('reason')}). The boundary REMAINS "
                        f"INTERSTITIAL and the pause was NOT armed."
                    )
                elif staged_hash_state == "mismatch":
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
                    if rec_pointer is not None:
                        # POINTER MODE: plan_chars measures the DURABLE BODY; the
                        # approval payload's size is recorded separately.
                        sealed["payload_mode"] = PAYLOAD_MODE_POINTER
                        sealed["payload_chars"] = len(plan_text)
                        sealed["plan_chars"] = rec_pointer.get("body_chars", len(plan_text))
                        sealed["durable_home"] = rec_pointer.get("durable_home")
                        sealed["durable_home_resolved"] = rec_pointer.get("durable_home_resolved")
                    sealed["plan_identity"] = {
                        "status": "verified_at_recovery",
                        "entry_tic": st_entry,
                        "work_tic": evidence["block"].get("work_tic"),
                        "handoff_id": evidence["block"].get("handoff_id"),
                    }
                    sealed["consumed_at"] = now
                    sealed["consumed_by"] = consumer
                    _atomic_write_json(CURRENT_FILE, sealed)
                    _atomic_append_jsonl(SEALS_LOG,
                                         _epoch_annotated({"journal_event": "recovery_promoted", **sealed}))
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


def _recover_binding(plan_text: str) -> tuple:
    """Resolve the hash the recovery seam binds, MODE-SYMMETRICALLY.

    Returns (recovered_hash, pointer_info_or_None, refusal_or_None).
    BODY mode — and ANY payload carrying no pointer block — returns
    _sha16(plan_text): byte-identical to the pre-tic-804 seam. POINTER mode binds
    the DURABLE HOME's content hash, RE-COMPUTED from the file, so the recovery
    seam and the staged capture resolve the SAME binding deterministically."""
    mode, _reason = resolve_payload_mode()
    if mode != PAYLOAD_MODE_POINTER:
        return _sha16(plan_text), None, None
    ptr = parse_pointer_block(plan_text)
    if not ptr:
        return _sha16(plan_text), None, None
    resolved, why = resolve_durable_home(ptr.get("durable_home"))
    if resolved is None:
        return None, ptr, {"reason": "pointer_durable_home_missing",
                           "durable_home": ptr.get("durable_home"), "resolution": why}
    try:
        body = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, ptr, {"reason": "pointer_durable_home_unreadable",
                           "durable_home": str(resolved), "error": exc.__class__.__name__}
    recomputed = _sha16(body)
    carried = ptr.get("content_sha16")
    if carried and carried != recomputed:
        return None, ptr, {"reason": "pointer_content_hash_mismatch",
                           "durable_home": str(resolved),
                           "carried_content_sha16": carried,
                           "recomputed_content_sha16": recomputed}
    return recomputed, {**ptr, "durable_home_resolved": str(resolved),
                        "body_chars": len(body)}, None


def _argval(argv, flag, default=None):
    try:
        return argv[argv.index(flag) + 1]
    except (ValueError, IndexError):
        return default


def handle_stage_pointer_payload(argv) -> int:
    """--stage-pointer-payload: body on stdin -> durable home written, payload on stdout.

    THE PRE-APPROVAL WRITE. If the durable-home write fails for ANY reason this
    falls back to BODY for this boundary and says so on stderr: a pointer is never
    submitted to a home that does not hold its body."""
    body = sys.stdin.read()
    entry_tic = _argval(argv, "--entry-tic")
    handoff_id = _argval(argv, "--handoff-id") or ""
    zone = _argval(argv, "--zone-root") or (str(ZONE_ROOT) if ZONE_ROOT else "")
    try:
        entry_tic = int(entry_tic)
    except (TypeError, ValueError):
        block = parse_handoff_block(body)
        entry_tic = block.get("entry_tic")
        handoff_id = handoff_id or block.get("handoff_id", "")
    mode, mode_reason = resolve_payload_mode()
    if mode != PAYLOAD_MODE_POINTER:
        sys.stdout.write(body)
        sys.stderr.write(json.dumps({"payload_mode": PAYLOAD_MODE_BODY, "source": mode_reason,
                                     "durable_home": None, "fallback": False}) + "\n")
        return 0
    try:
        if not zone:
            raise OSError("zone root unresolved")
        dest, rel, content_hash = write_durable_home(zone, body, entry_tic, handoff_id)
    except OSError as exc:
        sys.stdout.write(body)
        sys.stderr.write(json.dumps({
            "payload_mode": PAYLOAD_MODE_BODY, "fallback": True,
            "fallback_reason": f"durable_home_write_failed:{exc.__class__.__name__}",
            "detail": str(exc),
        }) + "\n")
        sys.stderr.write("[cadence-handoff-seal] durable-home write FAILED; this boundary "
                         "falls back to BODY mode. A pointer is never submitted to a home "
                         "that does not hold its body.\n")
        return 0
    payload = compose_pointer_payload(body, entry_tic, handoff_id, rel, content_hash)
    sys.stdout.write(payload)
    sys.stderr.write(json.dumps({
        "payload_mode": PAYLOAD_MODE_POINTER, "source": mode_reason, "fallback": False,
        "durable_home": rel, "durable_home_abs": str(dest),
        "content_sha16": content_hash, "body_chars": len(body),
        "payload_chars": len(payload),
    }) + "\n")
    return 0


def main():
    argv = sys.argv[1:]

    if "--payload-mode" in argv:
        mode, reason = resolve_payload_mode()
        print(json.dumps({PAYLOAD_MODE_KEY: mode, "source": reason}))
        return 0

    if "--durable-home-path" in argv:
        raw_tic = _argval(argv, "--entry-tic")
        try:
            tic = int(raw_tic)
        except (TypeError, ValueError):
            tic = raw_tic
        print(durable_home_relpath(tic, _argval(argv, "--handoff-id") or ""))
        return 0

    if "--stage-pointer-payload" in argv:
        if "--zone-root" in argv:
            try:
                zr = Path(_argval(argv, "--zone-root"))
                if (zr / ".ticzone").is_file():
                    bind_zone(zr)
            except (TypeError, OSError):
                pass
        return handle_stage_pointer_payload(argv)

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
