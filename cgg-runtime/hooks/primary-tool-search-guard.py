#!/usr/bin/env python3
"""primary-tool-search-guard.py — PreToolUse guard on ToolSearch (tic 557).

THE FOOTGUN (feedback_agent-tool-presence-probe, occurrences #1-#9): an agent
runs `ToolSearch select:Agent` (or any primary-tool name), gets "No matching
deferred tools found", and mis-reads the empty result as "the tool is gone".
But ToolSearch searches the DEFERRED registry ONLY; a PRIMARY (top-level) tool
is never in it, so a no-match for a primary tool is EXPECTED — it means "already
available", not "unreachable". The tool-absence-claim-gate catches this LATER,
at the WRITE boundary (when the false conclusion is inscribed). This guard fires
EARLIER — at the ToolSearch call itself — so the false signal never forms:
detect the primary-tool name in the query and inject its lite-spec + roster
BEFORE the empty result can be misread.

  * INPUT  — a JSON envelope on stdin: {tool_name, tool_input:{query, ...}, ...}
  * OUTPUT — the ONLY model-visible channel at exit 0 is structured JSON:
               {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                       "additionalContext": "<advisory text>"}}
             Plain stdout at exit 0 is DISCARDED.

DISCIPLINE (why this guard is structurally safe):
  * SHAPES, NEVER GATES — exit is ALWAYS 0. The search still runs; the advisory
    rides alongside. Only exit 2 would block, and this guard never reaches it.
  * SILENT ON NO-MATCH — when the query names no primary tool (the common case:
    a real deferred-tool search like `select:mcp__...` or `notebook jupyter`),
    it emits NOTHING and exits 0.
  * FAIL-SOFT — any error (bad stdin, missing/broken registry) → exit 0, no
    output. A delivery seam must never break the thing it orients.
  * ENGINE-CONTENT SEPARATION — this file is the ENGINE; tool names + lite-specs
    live in the sibling primary-tools-registry.json (content), which self-locates
    from __file__ (tic-365 self-locating-artifact discipline).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_REGISTRY = Path(__file__).resolve().parent / "primary-tools-registry.json"
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _load_registry() -> dict | None:
    try:
        return json.loads(_REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return None


def _candidate_names(query: str) -> list[str]:
    """Extract candidate tool tokens from a ToolSearch query.

    Handles the two query forms in the ToolSearch contract:
      * `select:A,B,C` — exact tool-name selection (the highest-signal form,
        and the one the footgun hits: `select:Agent`).
      * keyword / `+require term` — free tokens; we match whole-word tokens.
    Returns the token list (order-preserving, de-duplicated, case as written).
    """
    if not query:
        return []
    q = query.strip()
    seen: dict[str, None] = {}
    # select: form — everything after the first "select:" up to whitespace is a
    # comma list; also tokenize the rest of the query for keyword matches.
    m = re.match(r"\s*select:\s*(.+)$", q, re.IGNORECASE | re.DOTALL)
    if m:
        for part in m.group(1).split(","):
            tok = part.strip()
            # a select entry may be a bare name or contain further whitespace;
            # take the leading identifier token of each comma part.
            im = _TOKEN_RE.match(tok)
            if im:
                seen.setdefault(im.group(0), None)
    for tok in _TOKEN_RE.findall(q):
        if tok.lower() == "select":
            continue
        seen.setdefault(tok, None)
    return list(seen)


def _match(query: str, registry: dict) -> list[dict]:
    """Return matched primary-tool entries (canonical, alias-resolved, deduped)."""
    tools = registry.get("primary_tools") or {}
    # case-insensitive lookup: name/alias -> canonical entry name
    lut: dict[str, str] = {}
    for name, entry in tools.items():
        lut[name.lower()] = name
        for al in entry.get("aliases", []):
            lut[al.lower()] = name
    hits: list[dict] = []
    seen_canonical: set[str] = set()
    for tok in _candidate_names(query):
        canonical = lut.get(tok.lower())
        if not canonical or canonical in seen_canonical:
            continue
        seen_canonical.add(canonical)
        entry = dict(tools[canonical])
        entry["_name"] = canonical
        entry["_matched_as"] = tok
        hits.append(entry)
    return hits


def build_advisory(hits: list[dict], registry: dict) -> str | None:
    if not hits:
        return None
    classes = registry.get("classes") or {}
    lines = [
        "[primary-tool-search guard - advisory, shapes never gates] "
        "ToolSearch searches the DEFERRED registry ONLY. Your query names "
        "PRIMARY (top-level) tool(s) that are not deferred, so a no-match here "
        "is EXPECTED and is not evidence they are unreachable - invoke them "
        "directly. Matched:",
    ]
    for h in hits:
        cls = h.get("class", "")
        note = ""
        if cls == "usually_primary_session_variable":
            note = " (usually primary; if ToolSearch DID return it this session, use it from there)"
        lines.append(
            f"  - {h['_name']} [{cls}]{note}: {h.get('lite_spec','')}"
        )
        if h.get("invoke"):
            lines.append(f"      invoke: {h['invoke']}")
    # Full reliably-primary roster so the agent sees what is on the table.
    roster = [
        n for n, e in (registry.get("primary_tools") or {}).items()
        if e.get("class") == "reliably_primary" and "alias_of" not in e
    ]
    if roster:
        lines.append("  Reliably-primary roster (invoke directly, never via ToolSearch): "
                     + ", ".join(roster))
    lines.append("  Ref: feedback_agent-tool-presence-probe (#1-#9) - a ToolSearch "
                 "deferred-list no-match is not presence evidence either way.")
    return "\n".join(lines)


def handle(raw: str) -> dict | None:
    """Pure core: PreToolUse envelope text -> hookSpecificOutput dict (or None
    for silence). Fail-soft — any failure returns None."""
    if not raw or not raw.strip():
        return None
    try:
        evt = json.loads(raw)
    except Exception:
        return None
    if evt.get("tool_name") != "ToolSearch":
        return None
    query = (evt.get("tool_input") or {}).get("query") or ""
    registry = _load_registry()
    if not registry:
        return None
    hits = _match(query, registry)
    ctx = build_advisory(hits, registry)
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

    # 1. select:Agent -> advisory naming Agent
    out = handle(json.dumps({"tool_name": "ToolSearch",
                             "tool_input": {"query": "select:Agent", "max_results": 3}}))
    check("select:Agent yields hookSpecificOutput", out is not None and "hookSpecificOutput" in out)
    check("advisory names Agent",
          out is not None and "Agent" in out["hookSpecificOutput"]["additionalContext"])
    check("advisory NEVER carries permissionDecision (shapes, not gates)",
          out is not None and "permissionDecision" not in out["hookSpecificOutput"])

    # 2. alias: select:Task -> resolves to Agent
    out = handle(json.dumps({"tool_name": "ToolSearch",
                             "tool_input": {"query": "select:Task"}}))
    check("select:Task resolves to Agent",
          out is not None and "Agent" in out["hookSpecificOutput"]["additionalContext"])

    # 3. multi-select with a real deferred tool + a primary one
    out = handle(json.dumps({"tool_name": "ToolSearch",
                             "tool_input": {"query": "select:Read,mcp__foo__bar"}}))
    check("select:Read,mcp__foo__bar fires (Read is primary)",
          out is not None and "Read" in out["hookSpecificOutput"]["additionalContext"])

    # 4. keyword query naming a primary tool
    out = handle(json.dumps({"tool_name": "ToolSearch",
                             "tool_input": {"query": "spawn an agent subagent"}}))
    check("keyword 'agent' fires", out is not None
          and "Agent" in out["hookSpecificOutput"]["additionalContext"])

    # 5. genuine deferred-tool search -> SILENCE
    out = handle(json.dumps({"tool_name": "ToolSearch",
                             "tool_input": {"query": "select:mcp__claude-in-chrome__navigate"}}))
    check("pure deferred-tool select is silent", out is None)
    out = handle(json.dumps({"tool_name": "ToolSearch",
                             "tool_input": {"query": "notebook jupyter"}}))
    check("keyword 'notebook jupyter' is silent (NotebookEdit only matches on the word 'notebook'?)",
          out is None or "NotebookEdit" in out["hookSpecificOutput"]["additionalContext"])

    # 6. wrong tool_name -> silence
    check("non-ToolSearch envelope is silent",
          handle(json.dumps({"tool_name": "Bash", "tool_input": {"command": "select:Agent"}})) is None)

    # 7. fail-soft
    check("empty stdin is silent", handle("") is None)
    check("malformed JSON is silent", handle("{not json") is None)
    check("missing tool_name is silent",
          handle(json.dumps({"tool_input": {"query": "select:Agent"}})) is None)

    print()
    if failures:
        print(f"{len(failures)} FAILED:", ", ".join(failures))
        return 1
    print("all primary-tool-search-guard self-checks PASS")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    sys.exit(main())
