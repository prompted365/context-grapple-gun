#!/usr/bin/env python3
"""tool-absence-claim-gate.py — PreToolUse physics gate for tool-absence claims (tic 548).

The CONSUMER half of bk-tool-absence-physics-gate. The receipt engine
(scripts/tool-probe-receipt.py) is the detector; this hook is the gate that
consumes it — they land together.

WHY (feedback_agent-tool-presence-probe, occurrences #1–#9): "tool absent" /
"NOT_REACHABLE" / "isn't spawnable" shipped 9 times from the wrong surface (a
ToolSearch deferred-list no-match, an inherited handoff claim) without a
same-session call attempt — including once into a PUBLISHED artifact (tic 516)
and once WITH the worldview discipline read-in-full at boot (tic 547). Prompt-layer
wiring has no enforcement power (three-layer law, Autonomous Agent Tool Economics
§5); enforcement moves here, to the execution boundary, BEFORE the claim is written.

POSTURE — NARROW + FAIL-CLOSED on the condition, FAIL-SOFT on the hook's own errors
(mirrors boot-read-gate.py):
  * NARROW — fires ONLY when written content (Edit new_string / Write content /
    Bash command text) matches a tool-absence CLAIM shape from the CONTENT lexicon
    (tool-absence-claim-lexicon.json — engine-content separation: claim shapes are
    content, this automaton is engine). Reads are untouched; innocent prose
    ("absence of evidence", "absent-minded") does not match claim shapes.
  * FAIL-CLOSED on the condition — a matched claim with NO qualifying same-tic
    probe receipt BLOCKS (exit 2). The cure is one honest act: attempt the call
    (or load the schema via fuzzy select), record the receipt, retry.
  * FAIL-SOFT on the hook's own errors — missing lexicon, unresolved tic, missing
    engine, any internal exception → exit 0 (ALLOW). A gate bug must never wedge
    the system; only a clean determination of an unreceipted claim blocks.
  * NEVER-GATED — the recorder invocation itself, and the gate's own engine/content
    files (writing ABOUT the gate in its own home is maintenance, not a claim).
  * SCOPE-HONEST limitation, declared: receipts are TIC-scoped (the federation time
    authority), not session-scoped — two sessions in one tic share receipts. The
    cured failure is claim-with-NO-attempt, not cross-session reuse.

EXIT CODES (PreToolUse contract): 0 = allow · 2 = BLOCK (stderr shown to the model).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent
_LEXICON = _HOOKS / "tool-absence-claim-lexicon.json"


def _resolve_engine() -> Path:
    """SOVEREIGN resolution (mirrors boot-read-gate): canonical siblings first,
    installed runtime second, absolute machine-local fallback last."""
    cands = [
        _HOOKS.parent / "scripts" / "tool-probe-receipt.py",
        Path.home() / ".claude" / "cgg-runtime" / "scripts" / "tool-probe-receipt.py",
        Path("/Users/breydentaylor/canonical/canonical_developer/context-grapple-gun"
             "/cgg-runtime/scripts/tool-probe-receipt.py"),
    ]
    for c in cands:
        if c.exists():
            return c
    return cands[0]


def _load_lexicon() -> dict | None:
    for cand in (_LEXICON,
                 Path.home() / ".claude" / "hooks" / "tool-absence-claim-lexicon.json"):
        try:
            return json.loads(cand.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


_NEVER_GATE_CMD = ("tool-probe-receipt.py",)


def _match_claim(text: str, lex: dict) -> tuple:
    """(matched: bool, pattern_id: str, excerpt: str, tool: str|None).
    tool is a KNOWN-tool token captured from the claim, else None (generic check)."""
    known = {t.lower() for t in lex.get("known_tools", [])}
    for p in lex.get("patterns", []):
        try:
            m = re.search(p["regex"], text, re.IGNORECASE)
        except re.error:
            continue
        if not m:
            continue
        tool = None
        try:
            tok = m.groupdict().get("tool")
            if tok and tok.lower() in known:
                tool = tok
        except Exception:
            pass
        lo = max(0, m.start() - 40)
        excerpt = text[lo:m.end() + 40].replace("\n", " ")
        return True, p.get("id", "?"), excerpt, tool
    return False, "", "", None


def _exempt_target(fp: str, lex: dict) -> bool:
    frags = lex.get("exempt_path_fragments", [])
    return any(f in (fp or "") for f in frags)


def decide(raw: str) -> tuple:
    """(block: bool, message: str). FAIL-SOFT: any internal error → (False, '')."""
    try:
        if not raw or not raw.strip():
            return False, ""
        evt = json.loads(raw)
        tool_name = evt.get("tool_name") or ""
        ti = evt.get("tool_input") or {}
        if tool_name in ("Edit", "Write", "NotebookEdit"):
            text = ti.get("new_string") or ti.get("content") or ""
            fp = ti.get("file_path") or ""
        elif tool_name == "Bash":
            text = ti.get("command") or ""
            fp = ""
            if any(n in text for n in _NEVER_GATE_CMD):
                return False, ""  # recording / checking the receipt is never gated
        else:
            return False, ""
        if not text:
            return False, ""
        lex = _load_lexicon()
        if not lex:
            return False, ""  # content missing → gate bug, not debt → OPEN
        if _exempt_target(fp, lex):
            return False, ""  # maintaining the gate's own engine/content files
        matched, pid, excerpt, claimed_tool = _match_claim(text, lex)
        if not matched:
            return False, ""
        engine = _resolve_engine()
        if not engine.exists():
            return False, ""  # engine absent → fail-soft OPEN
        cmd = ["python3", str(engine), "check"]
        if claimed_tool:
            cmd += ["--tool", claimed_tool]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return False, ""  # clean primary proof — receipt exists
        if r.returncode != 3:
            return False, ""  # engine error → fail-soft OPEN
        reason = ""
        try:
            reason = json.loads(r.stdout).get("reason", "")
        except Exception:
            pass
        tool_arg = claimed_tool or "<tool>"
        msg = (
            "tool_absence_claim_unreceipted\n\n"
            f"A tool-absence claim is about to be written (pattern: {pid}):\n"
            f"  …{excerpt}…\n"
            f"but no qualifying same-tic probe receipt exists. {reason}\n\n"
            "'Absent' is not a writable conclusion without a same-session call attempt\n"
            "(9 recurrences on record — feedback_agent-tool-presence-probe.md; a ToolSearch\n"
            "deferred-list no-match and an inherited handoff claim are NOT absence evidence).\n\n"
            "ATTEMPT THE CALL FIRST (or a fuzzy select: schema-load probe), then record what\n"
            "actually happened and retry the write:\n"
            f"  python3 {engine} record --tool {tool_arg} "
            "--surface call_attempt --result \"<what the attempt returned>\"\n"
            "If the claim text is stale/inherited, correct the text instead of receipting it."
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
        return 2
    return 0


def _self_test() -> int:
    failures = []
    lex = _load_lexicon()

    def check(name, cond):
        print(("PASS" if cond else "FAIL"), name)
        if not cond:
            failures.append(name)

    check("lexicon loads", bool(lex))
    if not lex:
        print("\n1 FAILED: lexicon loads")
        return 1

    def m(text):
        return _match_claim(text, lex)

    # claim shapes MATCH
    r = m("the Agent tool is absent this session")
    check("'Agent tool is absent' matches with tool=Agent", r[0] and r[3] == "Agent")
    r = m("Agent tool absent (probed not assumed)")
    check("tic-547 exact claim shape matches", r[0] and r[3] == "Agent")
    r = m("the cpr-stepper isn't spawnable this session")
    check("'isn't spawnable' matches", r[0])
    r = m("prior assessment said NOT_REACHABLE and was overturned")
    check("NOT_REACHABLE matches", r[0])
    r = m("Workflow was absent from this session")
    check("'absent from this session' matches with tool=Workflow", r[0] and r[3] == "Workflow")
    r = m("there is no such Agent tool here")
    check("'no such Agent tool' matches", r[0])
    r = m("the tool was not enabled")
    check("bare 'tool was not enabled' matches (generic, no tool token)", r[0])
    # non-tool token does not trigger tool-specific check
    r = m("a tool is absent")
    check("'a tool is absent' matches but captures NO known tool", r[0] and r[3] is None)
    # innocent prose does NOT match
    check("'absence of evidence' no match", not m("the absence of evidence is not evidence")[0])
    check("'absent-minded' no match", not m("an absent-minded reviewer")[0])
    check("'the tool succeeded' no match", not m("the tool succeeded cleanly")[0])
    check("'signal absent from manifest' no match (not a TOOL claim)",
          not m("that signal is absent from the manifest")[0])
    check("plain code no match", not m("git add -A && git commit")[0])
    # envelope-level decisions (fail-soft + never-gate + exemptions)
    check("empty stdin → allow", decide("") == (False, ""))
    check("malformed JSON → allow", decide("{not json") == (False, ""))
    check("Read never gated",
          decide(json.dumps({"tool_name": "Read",
                             "tool_input": {"file_path": "x.md"}})) == (False, ""))
    check("recorder Bash invocation never gated",
          decide(json.dumps({"tool_name": "Bash", "tool_input": {
              "command": "python3 tool-probe-receipt.py record --tool Agent "
                         "--surface call_attempt --result 'tool absent'"}})) == (False, ""))
    check("writing the lexicon itself never gated",
          decide(json.dumps({"tool_name": "Write", "tool_input": {
              "file_path": "/x/hooks/tool-absence-claim-lexicon.json",
              "content": "Agent tool is absent"}})) == (False, ""))
    check("innocent Write → allow",
          decide(json.dumps({"tool_name": "Write", "tool_input": {
              "file_path": "/tmp/x.md", "content": "hello world"}})) == (False, ""))

    print()
    if failures:
        print(f"{len(failures)} FAILED:", ", ".join(failures))
        return 1
    print("all tool-absence-claim-gate self-checks PASS")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    sys.exit(main())
