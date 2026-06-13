#!/usr/bin/env python3
"""boot-read-gate.py — PreToolUse mutation gate for the boot-read invariant (tic 406).

The CONSUMER half of bk-boot-full-injection-read-invariant. The receipt sink
(scripts/boot-receipt.py, extended tic 406) is the detector; this hook is the gate that
consumes it — they land together (a receipt with no gate is the detector-without-a-sink
anti-pattern, the very refinement promoted at /review 406).

POSTURE — NARROW + FAIL-CLOSED (Architect, tic 406):
  * NARROW — gates ONLY the governance-mutation class (doctrine/ledger inscription,
    CLAUDE.md mutation, queue.jsonl promotion/terminal movement, mandate close/status
    mutation, backlog state movement, boot-injection mutation, active-manifest mutation).
    Read/Grep/Glob, diagnostic Bash, draft/spec prep, and WRITING THE BOOT RECEIPT ITSELF
    are never gated.
  * FAIL-CLOSED on the CONDITION — a missing / false / preview_only / incomplete boot-read
    receipt for the current tic BLOCKS a governed mutation (PreToolUse exit 2). Perception
    debt cannot authorize governance mutation. The audited, non-silent escape is an
    OVERRIDE receipt (boot-receipt.py override).
  * FAIL-SOFT on the HOOK'S OWN errors — a bad envelope, an unresolved tic, a missing
    receipt SCRIPT, any internal exception → exit 0 (ALLOW). A gate bug must never wedge
    the system; only a clean determination of perception-debt blocks. (Distinguishes
    "the gate broke" [open] from "the gate fired" [closed].)

EXIT CODES (PreToolUse contract, probed via task-touch-pretool.py):
  0 = allow (silent, or advisory additionalContext)
  2 = BLOCK (stderr message shown to the model)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent


def _resolve_boot_receipt() -> Path:
    """SOVEREIGN resolution — the gate must find its engine from ANY layout, not just
    the canonical sibling tree. Canonical: hooks/ and scripts/ are siblings under
    cgg-runtime/. INSTALLED: hooks land in ~/.claude/hooks/ but scripts in
    ~/.claude/cgg-runtime/scripts/ (NOT siblings) — so a naive sibling resolve is
    toothless-from-install (fails to find the engine → fail-soft allow). Fallback chain
    mirrors the runtime resolve_script() discipline. The DECISION ENGINE (boot-receipt.py
    gate-check) is harness-agnostic; this adapter is the only Claude-Code-hook-shaped
    piece, so any other hook system (git hook, CI gate, another harness) reuses the same
    engine via its own thin adapter."""
    cands = [
        _HOOKS.parent / "scripts" / "boot-receipt.py",                       # canonical siblings
        Path.home() / ".claude" / "cgg-runtime" / "scripts" / "boot-receipt.py",  # installed runtime
        Path("/Users/breydentaylor/canonical/canonical_developer/context-grapple-gun"
             "/cgg-runtime/scripts/boot-receipt.py"),                        # absolute fallback
    ]
    for c in cands:
        if c.exists():
            return c
    return cands[0]


_BOOT_RECEIPT = _resolve_boot_receipt()

# ── doctrine-mutation classification (NARROW) ────────────────────────────────────
# Edit/Write file_path tails that ARE governed-state surfaces.
_DOCTRINE_PATH_MARKERS = (
    "/CLAUDE.md", "constitution-ledger/ledger.md", "cgg-ledger/ledger.md",
    "cprs/queue.jsonl", "mogul/mandates/current.json",
    "boot-injections/active.jsonl", "signals/active-manifest.jsonl",
    "governance/backlog/backlog.jsonl",
)
# Bash command substrings that perform a governed mutation.
_DOCTRINE_CMD_MARKERS = (
    "review-promote-writeback.py", "constitution-ledger/ledger.md", "cgg-ledger/ledger.md",
    "cprs/queue.jsonl", "mandates/current.json", "active-manifest.jsonl",
    "boot-injections/active.jsonl",
)
# Things that LOOK mutating but are NOT gated — writing the receipt itself + reads.
_NEVER_GATE_CMD = ("boot-receipt.py",)


def _is_doctrine_mutation(tool: str, file_path: str, command: str) -> bool:
    if tool in ("Edit", "Write", "NotebookEdit"):
        fp = file_path or ""
        return any(m in fp for m in _DOCTRINE_PATH_MARKERS)
    if tool == "Bash":
        cmd = command or ""
        if any(n in cmd for n in _NEVER_GATE_CMD):
            return False  # writing the boot receipt / override is explicitly allowed
        # backlog STATE movement only (touch --state); plain backlog reads are fine
        if "backlog.py" in cmd and "--state" in cmd:
            return True
        # a git commit/append that touches a governed surface
        if any(m in cmd for m in _DOCTRINE_CMD_MARKERS):
            return True
    return False


def _current_tic() -> int | None:
    """Cheap, fail-soft: read tic_context.current_tic from the live mandate."""
    for cand in (
        _HOOKS.parent.parent.parent / "audit-logs" / "mogul" / "mandates" / "current.json",
        Path("/Users/breydentaylor/canonical/audit-logs/mogul/mandates/current.json"),
    ):
        try:
            m = json.loads(cand.read_text(encoding="utf-8"))
            t = (m.get("tic_context") or {}).get("current_tic")
            if isinstance(t, int):
                return t
        except Exception:
            continue
    return None


def _entity(evt: dict) -> str:
    aid = evt.get("agent_id") or ""
    return aid if aid.startswith("ent_") else "ent_homeskillet"


def decide(raw: str) -> tuple:
    """(block: bool, message: str). FAIL-SOFT: any internal error → (False, '') = allow."""
    try:
        if not raw or not raw.strip():
            return False, ""
        evt = json.loads(raw)
        tool = evt.get("tool_name") or ""
        ti = evt.get("tool_input") or {}
        fp = ti.get("file_path") or ""
        cmd = ti.get("command") or ""
        if not _is_doctrine_mutation(tool, fp, cmd):
            return False, ""  # NARROW — not a governed mutation, never gate
        tic = _current_tic()
        if tic is None:
            return False, ""  # can't resolve tic → fail-soft OPEN (gate bug, not debt)
        entity = _entity(evt)
        target = fp or cmd
        if not _BOOT_RECEIPT.exists():
            return False, ""  # receipt script absent → fail-soft OPEN
        r = subprocess.run(
            ["python3", str(_BOOT_RECEIPT), "gate-check",
             "--entity", entity, "--tic", str(tic), "--path", target],
            capture_output=True, text=True, timeout=10)
        # exit 0 = allow, 3 = block; anything else = gate error → fail-soft OPEN
        if r.returncode == 0:
            return False, ""
        if r.returncode != 3:
            return False, ""
        reason = ""
        try:
            reason = json.loads(r.stdout).get("reason", "")
        except Exception:
            pass
        msg = (
            "Perception debt cannot authorize governance mutation.\n\n"
            f"The boot packet was not receipted as fully read (sequential, gapless) for tic {tic} "
            f"[{entity}].\nGate reason: {reason}\n\n"
            "Emit a complete boot-read receipt, then retry:\n"
            f"  python3 {_BOOT_RECEIPT} emit --entity {entity} --tic {tic} \\\n"
            "    --understood ... --constraint ... --abstention ... --first-action ... \\\n"
            "    --full-boot-read --boot-read-mode full --chunking gapless\n"
            "Or, if a full read is genuinely impossible, record an AUDITED override (non-silent):\n"
            f"  python3 {_BOOT_RECEIPT} override --actor {entity} --tic {tic} "
            "--reason \"...\" --touched-path \"<path>\"\n"
            "Read-only inspection (Read/Grep/Glob, diagnostic Bash) remains allowed."
        )
        return True, msg
    except Exception:
        return False, ""  # FAIL-SOFT: never wedge on a gate bug


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0
    block, msg = decide(raw)
    if block:
        sys.stderr.write(msg + "\n")
        return 2  # PreToolUse BLOCK
    return 0


def _self_test() -> int:
    failures = []

    def check(name, cond):
        print(("PASS" if cond else "FAIL"), name)
        if not cond:
            failures.append(name)

    # classification (no receipt lookup needed)
    check("Edit ledger.md is doctrine-mutation",
          _is_doctrine_mutation("Edit", "audit-logs/governance/constitution-ledger/ledger.md", ""))
    check("Edit CLAUDE.md is doctrine-mutation",
          _is_doctrine_mutation("Edit", "canonical/CLAUDE.md", ""))
    check("Edit a source file is NOT doctrine-mutation",
          not _is_doctrine_mutation("Edit", "src/main.rs", ""))
    check("Read is never a mutation (no Edit/Write/Bash)",
          not _is_doctrine_mutation("Read", "audit-logs/governance/constitution-ledger/ledger.md", ""))
    check("Bash backlog.py touch --state IS gated",
          _is_doctrine_mutation("Bash", "", "python3 backlog.py touch x --state done"))
    check("Bash backlog.py dag (read) is NOT gated",
          not _is_doctrine_mutation("Bash", "", "python3 backlog.py dag"))
    check("Bash boot-receipt.py emit is NEVER gated (writing the receipt itself)",
          not _is_doctrine_mutation("Bash", "", "python3 boot-receipt.py emit --entity ent_x --tic 1"))
    check("Bash ls is NOT gated",
          not _is_doctrine_mutation("Bash", "", "ls -la"))
    # fail-soft envelopes → allow
    check("empty stdin → allow", decide("") == (False, ""))
    check("malformed JSON → allow", decide("{not json") == (False, ""))
    check("source-file Edit envelope → allow",
          decide(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "src/x.rs"}})) == (False, ""))

    print()
    if failures:
        print(f"{len(failures)} FAILED:", ", ".join(failures))
        return 1
    print("all boot-read-gate self-checks PASS")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    sys.exit(main())
