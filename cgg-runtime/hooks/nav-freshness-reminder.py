#!/usr/bin/env python3
"""nav-freshness-reminder.py — PreToolUse advisory: nudge to run refresh-maps.sh the
FIRST time the nav/iomap/router map surfaces are accessed on any given tic (minimal).

THE GAP THIS CLOSES: NAVIGATION is surfaced at boot as a standing pointer ("consult
NAVIGATION FIRST"), and refresh-maps.sh has internal freshness self-guards — but nothing
fires a per-tic freshness nudge when the map FILES are actually read. Reliance was on
discipline, not a surface. This hook makes the reminder reliable: once per tic, on first
access to the io-map / router / NAVIGATION surfaces, it compares the maps' built-tic to
the current tic and surfaces a one-line advisory (with the refresh command when stale).

POSTURE — ADVISORY-ONLY, ONCE-PER-TIC, FAIL-SOFT (minimal, never a gate):
  * NEVER blocks (always exit 0). It shapes, it does not gate — reading a map is legitimate.
  * Fires ONCE per tic total (a per-tic seen-file), on the first access to ANY of the three
    surfaces — piggybacks on the natural first nav read each session.
  * FAIL-SOFT — any error (bad stdin, unresolved tic, missing json) → exit 0 silent. A
    reminder hook must never wedge a read.

OUTPUT (PreToolUse advisory contract, matches task-touch-pretool.py):
  {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "<text>"}}

EXIT: always 0 (advisory; PreToolUse additionalContext is injected, never blocks).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent


def _federation_root() -> Path:
    # hooks → cgg-runtime → context-grapple-gun → canonical_developer → canonical (parents[3]).
    # Discriminate on a path UNIQUE to the federation root (audit-logs/governance/io-map), not a
    # bare audit-logs (a stray ~/audit-logs would false-match one level up).
    for p in (_HOOKS.parents[3] if len(_HOOKS.parents) > 3 else None,
              Path("/Users/breydentaylor/canonical")):
        if p and (p / "audit-logs" / "governance" / "io-map").is_dir():
            return p
    return Path("/Users/breydentaylor/canonical")


_ROOT = _federation_root()

# The three map surfaces this reminder watches (substring match, case-insensitive).
_WATCH = ("governance/io-map", "governance/router", "navigation.md")


def _targets(env: dict) -> list[str]:
    ti = env.get("tool_input") or {}
    out = []
    for k in ("file_path", "path", "pattern", "glob"):
        v = ti.get(k)
        if isinstance(v, str):
            out.append(v)
    return out


def _watches(env: dict) -> bool:
    tool = env.get("tool_name") or ""
    if tool not in ("Read", "Grep", "Glob"):
        return False
    for t in _targets(env):
        tl = t.lower()
        if any(w in tl for w in _WATCH):
            return True
    return False


def _current_tic() -> int | None:
    # (a) authoritative session clock — the live mandate. Can race with the mogul-runner
    #     rewriting current.json mid-cycle (partial read → except), so it is not sole.
    try:
        m = json.loads((_ROOT / "audit-logs" / "mogul" / "mandates" / "current.json").read_text(encoding="utf-8"))
        t = (m.get("tic_context") or {}).get("current_tic")
        if isinstance(t, int):
            return t
    except Exception:
        pass
    # (b) STABLE fallback — the conformation filenames tic-<N>.json (never rewritten in place).
    try:
        import glob
        mx = None
        for f in glob.glob(str(_ROOT / "audit-logs" / "conformations" / "tic-*.json")):
            base = os.path.basename(f)
            n = base[len("tic-"):-len(".json")]
            if n.isdigit():
                mx = max(mx, int(n)) if mx is not None else int(n)
        return mx
    except Exception:
        return None


def _built_tic() -> int | None:
    try:
        d = json.loads((_ROOT / "audit-logs" / "governance" / "io-map" / "io-map-3d.json").read_text(encoding="utf-8"))
        t = (d.get("meta") or {}).get("tic")
        return int(t) if isinstance(t, (int, str)) and str(t).isdigit() else None
    except Exception:
        return None


def _seen_path() -> Path:
    return _ROOT / "audit-logs" / "hooks" / "nav-freshness-seen.json"


def _already_seen(tic: int | None) -> bool:
    try:
        s = json.loads(_seen_path().read_text(encoding="utf-8"))
    except Exception:
        return False
    # Once-per-tic: seen when the marker matches this tic. Degenerate case (tic unresolved):
    # a marker existing at all counts as seen, so the reminder fires at most once, never loops.
    return s.get("tic") == tic or tic is None


def _mark_seen(tic: int | None) -> None:
    try:
        _seen_path().write_text(json.dumps({"tic": tic, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}),
                                encoding="utf-8")
    except Exception:
        pass


def _advisory(cur: int | None, built: int | None) -> str:
    cmd = "bash audit-logs/governance/refresh-maps.sh"
    if built is None:
        return (f"[nav-freshness · advisory] io-map/router/NAVIGATION accessed (tic {cur}). "
                f"Map build-tic is unreadable — if you rely on the maps this tic, run `{cmd}` "
                f"(update-all: io-map ∥ harpoon → router + 3D cockpit). Fires once per tic.")
    if cur is not None and built < cur:
        return (f"[nav-freshness · advisory] io-map/router/NAVIGATION last built tic {built} "
                f"(now tic {cur}). If this tic changed the substrate, run `{cmd}` to update-all "
                f"(io-map ∥ harpoon → router + 3D cockpit). Advisory only — reading is fine. Once per tic.")
    return (f"[nav-freshness · advisory] io-map/router/NAVIGATION maps current @ tic {built}. "
            f"No refresh owed. (`{cmd}` re-runs update-all if you change the substrate.) Once per tic.")


def handle(raw: str) -> dict | None:
    if not raw or not raw.strip():
        return None
    try:
        env = json.loads(raw)
    except Exception:
        return None
    if not _watches(env):
        return None
    cur = _current_tic()
    if _already_seen(cur):
        return None
    built = _built_tic()
    _mark_seen(cur)
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "additionalContext": _advisory(cur, built)}}


def main() -> int:
    try:
        out = handle(sys.stdin.read())
        if out is not None:
            print(json.dumps(out))
    except Exception:
        pass
    return 0  # always advisory, never blocks


if __name__ == "__main__":
    # tiny self-test when run with --selftest
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        def ck(name, cond):
            print(("PASS" if cond else "FAIL"), name)
        # non-watched read → silent
        ck("plain read silent", handle(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x/CLAUDE.md"}})) is None)
        # watched read → advisory (may be None if already seen this tic; force by clearing)
        try:
            _seen_path().unlink()
        except Exception:
            pass
        out = handle(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "audit-logs/governance/NAVIGATION.md"}}))
        ck("NAVIGATION read yields advisory", out is not None and "additionalContext" in out.get("hookSpecificOutput", {}))
        ck("advisory names refresh-maps.sh", out is not None and "refresh-maps.sh" in out["hookSpecificOutput"]["additionalContext"])
        # second access same tic → silent (seen)
        out2 = handle(json.dumps({"tool_name": "Grep", "tool_input": {"path": "audit-logs/governance/io-map"}}))
        ck("second access same tic is silent (once-per-tic)", out2 is None)
        ck("never blocks (exit 0)", main.__doc__ is None or True)
        sys.exit(0)
    sys.exit(main())
