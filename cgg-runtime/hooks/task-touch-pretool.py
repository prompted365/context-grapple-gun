#!/usr/bin/env python3
"""task-touch-pretool.py — PreToolUse adapter for the task-touch seam (Injection
Fabric §1.3.1, tic 371).

Wires `task_touch.resolve()` into a LIVE PreToolUse hook in SHAPES-never-gates
form. The CLI `task_touch.py` (tic 370) renders to stdout/JSON for a human or a
`--format json` consumer; a PreToolUse hook needs a different shape entirely:

  * INPUT  — a JSON envelope on stdin: {tool_name, tool_input:{file_path|command}, …}
  * OUTPUT — the ONLY model-visible channel at exit 0 is structured JSON:
               {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                       "additionalContext": "<advisory text>"}}
             Plain stdout at exit 0 is DISCARDED (probed authoritatively, tic 371).

DISCIPLINE (why this adapter is structurally safe):
  * SHAPES, NEVER GATES — exit is ALWAYS 0. Only exit 2 blocks a PreToolUse call;
    this adapter cannot reach exit 2. No `permissionDecision` is ever emitted.
  * SILENT ON NO-MATCH — when no task-touch rule matches (the ~99% case: Edit a
    source file, Bash `ls`), the adapter emits NOTHING and exits 0. No noise on
    every tool call.
  * FAIL-SOFT — any error (bad stdin, import failure, resolve crash) → exit 0,
    no output. A delivery seam must never break the thing it orients (mirrors
    task_touch.py's fail-soft contract import + fragment_receipt.py discipline).
  * RENDER-ONLY — no receipts written. A per-tool-call hook must not side-effect
    on every Edit/Write/Bash; receipt emission stays in the explicit CLI
    `--emit-receipts` lane. Self-Operation Signal Discipline (tic 350): a hook
    that wrote on the motion surface it fires from would be mutating the surface
    that grants it motion.

ZONE / RULE SOURCE: `task_touch.resolve()` self-locates the zone from its own
`__file__` (tic-365 self-locating-artifact discipline), so the rule registry is
ALWAYS canonical's `audit-logs/boot-injections/task-touch-rules.jsonl`, regardless
of cwd or which project the edited file lives in. (Cross-zone note: a `**/CLAUDE.md`
rule therefore fires its advisory for a CLAUDE.md edit in ANY project — advisory
only, never blocking; scope-narrowing to the canonical zone is a future option,
recorded in the activation-readiness docket.)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# adapter lives in cgg-runtime/hooks/ ; task_touch lives in cgg-runtime/scripts/
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def build_advisory(resolution: dict) -> str | None:
    """Render matched fragments into a single additionalContext string. Returns
    None when nothing matched (caller stays silent)."""
    matched = resolution.get("matched") or []
    if not matched:
        return None
    lines = ["[task-touch · advisory — shapes, never gates] you are about to: "
             f"{resolution.get('tool')} → {resolution.get('target')}"]
    for m in matched:
        frag = m.get("fragment", {})
        lines.append(f"  {m.get('badge', '')} {frag.get('text', '')}".rstrip())
    return "\n".join(lines)


def handle(raw: str) -> dict | None:
    """Pure core: PreToolUse envelope text → hookSpecificOutput dict (or None for
    silence). Fail-soft — any failure returns None."""
    if not raw or not raw.strip():
        return None
    try:
        evt = json.loads(raw)
    except Exception:
        return None
    tool = evt.get("tool_name")
    if not tool:
        return None
    ti = evt.get("tool_input") or {}
    target = ti.get("file_path") or ti.get("command") or ""
    try:
        from task_touch import resolve  # type: ignore
        resolution = resolve(tool, target)
    except Exception:
        return None
    ctx = build_advisory(resolution)
    if ctx is None:
        return None
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "additionalContext": ctx}}


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0  # fail-soft
    out = handle(raw)
    if out is not None:
        print(json.dumps(out))
    return 0  # SHAPES, never gates — exit is always 0 (only exit 2 blocks)


def _self_test() -> int:
    failures = []

    def check(name, cond):
        print(("PASS" if cond else "FAIL"), name)
        if not cond:
            failures.append(name)

    # 1. doctrine-surface edit → advisory emitted, additionalContext present
    edit_claude = json.dumps({"tool_name": "Edit",
                              "tool_input": {"file_path": "canonical/CLAUDE.md"}})
    out = handle(edit_claude)
    check("Edit CLAUDE.md yields hookSpecificOutput", out is not None
          and "hookSpecificOutput" in out)
    check("advisory carries additionalContext text",
          out is not None
          and bool(out["hookSpecificOutput"].get("additionalContext")))
    check("advisory NEVER carries permissionDecision (shapes, not gates)",
          out is not None
          and "permissionDecision" not in out["hookSpecificOutput"])

    # 2. source-file edit → SILENCE (no rule matches)
    edit_src = json.dumps({"tool_name": "Edit",
                           "tool_input": {"file_path": "src/main.rs"}})
    check("Edit src/main.rs is silent (no match)", handle(edit_src) is None)

    # 3. git push Bash → advisory (command_contains rule)
    bash_push = json.dumps({"tool_name": "Bash",
                            "tool_input": {"command": "cd repo && git push origin main"}})
    check("Bash 'git push' yields advisory", handle(bash_push) is not None)

    # 4. benign Bash → silence
    bash_ls = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    check("Bash 'ls' is silent", handle(bash_ls) is None)

    # 5. fail-soft: empty / malformed / missing tool_name → silence, never raise
    check("empty stdin is silent", handle("") is None)
    check("malformed JSON is silent", handle("{not json") is None)
    check("missing tool_name is silent",
          handle(json.dumps({"tool_input": {"file_path": "x/CLAUDE.md"}})) is None)

    print()
    if failures:
        print(f"{len(failures)} FAILED:", ", ".join(failures))
        return 1
    print("all task-touch-pretool self-checks PASS")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    sys.exit(main())
