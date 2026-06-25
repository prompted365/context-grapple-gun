#!/usr/bin/env python3
"""boot-read-gate.py — PreToolUse mutation gate for the boot-read invariant (tic 406).

The CONSUMER half of bk-boot-full-injection-read-invariant. The receipt sink
(scripts/boot-receipt.py, extended tic 406) is the detector; this hook is the gate that
consumes it — they land together (a receipt with no gate is the detector-without-a-sink
anti-pattern, the very refinement promoted at /review 406).

POSTURE — NARROW + FAIL-CLOSED (Architect, tic 406):
  * NARROW — gates ONLY the governance-mutation class (doctrine/ledger inscription,
    CLAUDE.md mutation, queue.jsonl promotion/terminal movement, mandate close/status
    mutation, backlog state movement, boot-injection mutation, active-manifest mutation)
    AND the review-INPUT class (tic 502, arm A): born candidates, counsel/review
    verification receipts, ripple proposals, enrichment consolidations, and proof-VERDICT
    edits recorded onto specs. Read/Grep/Glob, diagnostic Bash, plain draft/spec prep
    (no verdict marker), and WRITING THE BOOT RECEIPT ITSELF are never gated.
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
import re
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
# ── review-input perimeter (tic 502 · bk-boot-read-gate-review-input-perimeter · ARM A) ──
# LAW cgg-ledger#precondition-gate-perimeter-completeness: a precondition gate must COVER every
# surface that becomes counsel/review INPUT, OR explicitly DECLARE the exemption — a silent
# asymmetry is the defect. Arm A (Architect, tic 502): EXTEND coverage. The tic-500 evidence —
# the gate blocked `backlog.py --state` (a STATE surface) but let a born Write + a
# counsel-verification-receipt Edit land un-gated — is the asymmetry this closes. These Edit/Write
# file_path tails ARE review-input surfaces, authored as FINALIZED review input (not reversible
# draft prep), so review input cannot be authored under perception debt:
_REVIEW_INPUT_PATH_MARKERS = (
    "/borns-",                       # born CogPR candidates → cpr-extract → /review
    "grapple-proposals/",            # ripple-assessor proposal packet → /review docket
    "governance/enrichment/",        # CogPR enrichment consolidations → /review
    "_COUNSEL_VERIFICATION",         # counsel/review verification receipts (PACKET form)
    "counsel-verification",
    "-verification-receipt",
)
# DECLARED EXEMPTION (the perimeter's other half — the LAW is satisfied by cover-OR-declare):
#   * Plain spec / draft prep — a `*-spec-*.md` (or any governance/*.md) edited WITHOUT a verdict
#     marker — stays UN-gated: it is reversible authoring, and /review RE-READS it fresh at the
#     human gate, so the load-bearing read-attestation is at /review-TIME, not draft-WRITE-time.
#     HOLDING the tic-407 tension: do NOT collapse to "gate every spec edit" (that re-introduces
#     the over-block). The narrow review-INPUT case on a spec — RECORDING a proof/review VERDICT
#     onto it — IS gated, detected by a verdict marker in the WRITTEN CONTENT (below), not by path.
_VERDICT_CONTENT_MARKERS = (
    "review_verdict:", "review_verdict=",
    "verdict: PROMOTE", "verdict: PATH", "verdict: DEFER", "verdict: REJECT", "verdict: SKIP",
)
# Bash governed-state WRITE scripts — invoking these mutates governed state directly.
_DOCTRINE_WRITE_SCRIPTS = (
    "review-promote-writeback.py",
)
# Governed-state surface path fragments. A WRITE whose target is one of these is a
# mutation; a READ or git-VERSIONING that merely names one is NOT (tic-407 over-block fix).
# Includes the path-identifiable review-input surfaces (tic 502) so a redirect/tee/sed-i write
# to a born / proposal / enrichment file is gated symmetrically with the Edit/Write path.
_GOVERNED_SURFACES = (
    "/CLAUDE.md", "constitution-ledger/ledger.md", "cgg-ledger/ledger.md",
    "cprs/queue.jsonl", "mandates/current.json", "active-manifest.jsonl",
    "boot-injections/active.jsonl", "governance/backlog/backlog.jsonl",
    "/borns-", "grapple-proposals/", "governance/enrichment/",
)
# Things that LOOK mutating but are NOT gated — writing the receipt itself.
_NEVER_GATE_CMD = ("boot-receipt.py",)


def _writes_to_governed(cmd: str) -> bool:
    """True iff the Bash command performs an ACTUAL write to a governed surface — a
    > / >> redirect, tee, sed -i, or dd of= whose target is a governed path.

    This is the tic-407 narrowing (bk-boot-gate-bash-read-overblock). READS
    (cat / grep / head / tail / less / wc / diff / jq / awk) and git-VERSIONING
    (git add / commit / push / status / diff / log / show) that merely MENTION a
    governed surface are NOT mutations — versioning an already-mutated file RECORDS
    state (the mutation was gated at its Edit/Write source), and reading inspects it.
    Honest-scope limitation: an arbitrary-code write (e.g. a python heredoc opening a
    governed path in 'a'/'w' mode) is NOT detected here — the Bash classifier gates the
    enumerable write SIGNALS only; Edit/Write remains the strongly-gated primary path."""
    for surf in _GOVERNED_SURFACES:
        if surf not in cmd:
            continue
        s = re.escape(surf)
        if re.search(r">>?\s*[^|&;<>]*" + s, cmd):            # > / >> redirect into surface
            return True
        if re.search(r"\btee\b[^|&;]*" + s, cmd):             # tee writes the surface
            return True
        if re.search(r"\bsed\b[^|&;]*-i\b[^|&;]*" + s, cmd):  # sed -i in-place edit
            return True
        if re.search(r"\bdd\b[^|&;]*of=\S*" + s, cmd):        # dd of= the surface
            return True
    return False


def _is_doctrine_mutation(tool: str, file_path: str, command: str, content: str = "") -> bool:
    if tool in ("Edit", "Write", "NotebookEdit"):
        fp = file_path or ""
        # governed-STATE surfaces (always gated)
        if any(m in fp for m in _DOCTRINE_PATH_MARKERS):
            return True
        # review-INPUT surfaces (tic 502, arm A) — finalized review input, gated by path
        if any(m in fp for m in _REVIEW_INPUT_PATH_MARKERS):
            return True
        # a proof/review VERDICT recorded onto a spec / governance markdown — review input by
        # CONTENT, not path (so plain spec drafting stays un-gated: the declared exemption above)
        if fp.endswith(".md") and ("governance/" in fp or "-spec-" in fp or "_spec_" in fp):
            if any(v in (content or "") for v in _VERDICT_CONTENT_MARKERS):
                return True
        return False
    if tool == "Bash":
        cmd = command or ""
        if any(n in cmd for n in _NEVER_GATE_CMD):
            return False  # writing the boot receipt / override is explicitly allowed
        # backlog STATE movement only (touch --state); plain backlog reads/dag are fine
        if "backlog.py" in cmd and "--state" in cmd:
            return True
        # a known governed-state write-script invocation
        if any(w in cmd for w in _DOCTRINE_WRITE_SCRIPTS):
            return True
        # an ACTUAL write (redirect / tee / sed -i / dd) to a governed surface —
        # NOT a read, NOT git-versioning that merely names the surface
        if _writes_to_governed(cmd):
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
        # written content (for the review-input verdict-content check) — Edit=new_string, Write=content
        content = ti.get("new_string") or ti.get("content") or ""
        if not _is_doctrine_mutation(tool, fp, cmd, content):
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
            f"The boot packet was not receipted as fully read (surface-typed: prose gapless, "
            f"JSON/JSONL registries terminal-valve / latest-entry-per-id) for tic {tic} "
            f"[{entity}].\nGate reason: {reason}\n\n"
            "Emit a complete boot-read receipt, then retry (the gate blocks ONLY on "
            "required_unread_ranges — declared apophatic negative space is not debt):\n"
            f"  python3 {_BOOT_RECEIPT} emit --entity {entity} --tic {tic} \\\n"
            "    --understood ... --constraint ... --abstention ... --first-action ... \\\n"
            "    --full-boot-read --boot-read-mode full --chunking surface_typed\n"
            "  (a ranged/partial read also owes --apophatic-bound + --pertinence-rationale)\n"
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
    # review-input perimeter (tic 502, bk-boot-read-gate-review-input-perimeter, ARM A)
    check("Write a born IS review-input-gated",
          _is_doctrine_mutation("Write", "audit-logs/governance/borns-tic502-x.md", ""))
    check("Write grapple-proposals IS review-input-gated",
          _is_doctrine_mutation("Write", "/Users/x/.claude/grapple-proposals/latest.md", ""))
    check("Write enrichment consolidation IS review-input-gated",
          _is_doctrine_mutation("Write", "audit-logs/governance/enrichment/CogPR-9.consolidated.json", ""))
    check("Edit counsel-verification receipt IS review-input-gated",
          _is_doctrine_mutation("Edit", "audit-logs/governance/SOVEREIGN_PACKET_COUNSEL_VERIFICATION_TIC500.md", ""))
    check("Edit a spec WITHOUT a verdict marker is NOT gated (draft-prep exemption held — tic-407 tension)",
          not _is_doctrine_mutation("Edit", "audit-logs/governance/foo-spec-tic1.md", "", "draft prose about the strike mechanic"))
    check("Edit a spec WITH a verdict marker IS gated (proof-verdict review input, by content)",
          _is_doctrine_mutation("Edit", "audit-logs/governance/foo-spec-tic1.md", "", "STRIKE-3 result\nreview_verdict: PROMOTE"))
    check("Write a NON-governance .md is NOT gated even with a verdict-looking word (scoped to governance/spec)",
          not _is_doctrine_mutation("Write", "docs/readme.md", "", "verdict: PROMOTE"))
    check("Bash > into a born IS review-input-gated (redirect write)",
          _is_doctrine_mutation("Bash", "", "echo x > audit-logs/governance/borns-tic502-y.md"))
    check("Bash cat a born is NOT gated (read, tic-407 tension held)",
          not _is_doctrine_mutation("Bash", "", "cat audit-logs/governance/borns-tic502-y.md"))
    check("Bash backlog.py touch --state IS gated",
          _is_doctrine_mutation("Bash", "", "python3 backlog.py touch x --state done"))
    check("Bash backlog.py dag (read) is NOT gated",
          not _is_doctrine_mutation("Bash", "", "python3 backlog.py dag"))
    check("Bash boot-receipt.py emit is NEVER gated (writing the receipt itself)",
          not _is_doctrine_mutation("Bash", "", "python3 boot-receipt.py emit --entity ent_x --tic 1"))
    check("Bash ls is NOT gated",
          not _is_doctrine_mutation("Bash", "", "ls -la"))
    # tic-407 over-block fix (bk-boot-gate-bash-read-overblock): READS + git-VERSIONING
    # that merely NAME a governed surface are NOT mutations
    check("Bash cat ledger is NOT gated (read)",
          not _is_doctrine_mutation("Bash", "", "cat audit-logs/governance/constitution-ledger/ledger.md"))
    check("Bash grep queue.jsonl is NOT gated (read)",
          not _is_doctrine_mutation("Bash", "", "grep foo audit-logs/cprs/queue.jsonl"))
    check("Bash head cgg-ledger is NOT gated (read)",
          not _is_doctrine_mutation("Bash", "", "head -50 cgg-ledger/ledger.md"))
    check("Bash git add governed path is NOT gated (versioning)",
          not _is_doctrine_mutation("Bash", "", "git add audit-logs/governance/constitution-ledger/ledger.md"))
    check("Bash git commit naming governed path is NOT gated (versioning)",
          not _is_doctrine_mutation("Bash", "", "git commit -m x -- audit-logs/cprs/queue.jsonl"))
    check("Bash git diff/status of governed path is NOT gated (versioning)",
          not _is_doctrine_mutation("Bash", "", "git diff audit-logs/governance/constitution-ledger/ledger.md"))
    # actual WRITES to a governed surface ARE gated
    check("Bash >> into queue.jsonl IS gated (redirect write)",
          _is_doctrine_mutation("Bash", "", "echo '{}' >> audit-logs/cprs/queue.jsonl"))
    check("Bash > into ledger IS gated (redirect write)",
          _is_doctrine_mutation("Bash", "", "echo x > audit-logs/governance/constitution-ledger/ledger.md"))
    check("Bash tee into backlog.jsonl IS gated (write)",
          _is_doctrine_mutation("Bash", "", "echo x | tee audit-logs/governance/backlog/backlog.jsonl"))
    check("Bash sed -i on cgg-ledger IS gated (in-place write)",
          _is_doctrine_mutation("Bash", "", "sed -i 's/a/b/' cgg-ledger/ledger.md"))
    check("Bash review-promote-writeback.py IS gated (write script)",
          _is_doctrine_mutation("Bash", "", "python3 review-promote-writeback.py --apply"))
    check("Bash git commit with NO governed path is NOT gated",
          not _is_doctrine_mutation("Bash", "", "git commit -m 'tic407 backlog'"))
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
