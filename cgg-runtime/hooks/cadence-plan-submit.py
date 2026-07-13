#!/usr/bin/env python3
"""cadence-plan-submit.py — COMPATIBILITY SHIM (tic 633 plan-lifecycle split)

This hook was the PreToolUse:EnterPlanMode "plan submit" capture — a misnomer:
it fired BEFORE the plan existed and hashed synthesized text. The Architect-
directed t632 correction split it into two honestly-named halves:

  cadence-interstitial-enter.py  (PreToolUse:EnterPlanMode — boundary entry;
                                  tdelta/git-cycle/ReBru; NO plan claims)
  cadence-handoff-seal.py        (Pre+PostToolUse:ExitPlanMode — the REAL plan
                                  + planFilePath, hash, activation mode, seal)

This file is preserved as a forwarding shim so any registration surface still
riding the old path (other machines, stale settings, older installs) keeps
working identically: it delegates to cadence-interstitial-enter.py, passing
stdin through untouched, and stamps the legacy-path fire into the event log
via the delegate's own logging. Delete only after canonical + installed +
settings registration parity is verified everywhere (t632 directive §4).
"""

import os
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent


def main():
    payload_raw = sys.stdin.read()

    # Prefer the sibling in the same directory (source and installed layouts
    # both keep the pair co-located); fall back to the installed copy.
    candidates = [
        HOOK_DIR / "cadence-interstitial-enter.py",
        Path.home() / ".claude" / "hooks" / "cadence-interstitial-enter.py",
    ]
    delegate = next((c for c in candidates if c.is_file()), None)
    if delegate is None:
        sys.stderr.write(
            "[cadence-plan-submit shim] delegate cadence-interstitial-enter.py "
            "not found — legacy path fires as no-op (never blocks plan mode).\n"
        )
        return 0

    try:
        proc = subprocess.run(
            ["python3", str(delegate)],
            input=payload_raw, text=True, capture_output=True, timeout=90,
        )
        if proc.stdout:
            sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        # A hook shim must never block plan mode on delegate failure; the
        # delegate itself is fail-soft, so forward its exit only when clean.
        return 0
    except (subprocess.TimeoutExpired, OSError) as err:
        sys.stderr.write(f"[cadence-plan-submit shim] delegate error: {err} — not blocking.\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
