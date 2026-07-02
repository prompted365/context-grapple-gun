#!/usr/bin/env python3
"""tool-probe-receipt.py — probe-receipt engine for tool-availability claims (tic 548).

The DETECTOR half of bk-tool-absence-physics-gate. The gate
(hooks/tool-absence-claim-gate.py) is the consumer — they land together (a gate
with no receipt sink is teeth without evidence; a sink with no gate is the
detector-without-a-sink anti-pattern).

WHY (feedback_agent-tool-presence-probe, occurrences #1–#9): "tool absent" /
"NOT_REACHABLE" / "isn't spawnable" conclusions kept shipping from the WRONG
surface (a ToolSearch deferred-list no-match, an inherited handoff claim) without
a same-session call attempt. Prompt-layer wiring failed 9×; per the three-layer
law (Autonomous Agent Tool Economics §5) enforcement belongs at the execution
boundary. This engine records the honest probe; the gate refuses the claim
without it.

RECEIPT SEMANTICS:
  * a receipt attests "a probe was ATTEMPTED this tic on this surface" — it does
    NOT attest the tool is absent or present; the --result field carries what
    actually happened (e.g. "exists but is not enabled in this context").
  * surface ∈ {call_attempt, schema_load, roster_observed} — call_attempt is the
    strongest (the memory's own instruction: attempt the call); schema_load is a
    fuzzy-select ToolSearch that LOADED a schema (proves presence); roster_observed
    is an unprompted system-reminder enumeration.
  * tic-scoped: the tic is the federation time authority (timestamps are
    observability only). Honest limitation, declared: two sessions inside one tic
    share receipts — acceptable; the cured failure mode is claim-with-NO-attempt,
    not cross-session receipt reuse.

  - Append-only JSONL; POSIX O_APPEND writes under PIPE_BUF are atomic across procs.
  - flock(LOCK_EX) serializes appends (mirrors boot-receipt.py discipline).

EXIT CODES (check): 0 = receipt found · 3 = no qualifying receipt · 1 = usage error.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent


def _zone_root() -> Path:
    """Canonical zone resolution — sovereign chain (mirrors boot-read-gate resolve
    discipline): canonical-relative from the source tree, then the absolute
    machine-local fallback (this is a machine-local governance surface)."""
    cands = [
        _SCRIPTS.parents[3],  # scripts → cgg-runtime → context-grapple-gun → canonical_developer → canonical
        Path("/Users/breydentaylor/canonical"),
    ]
    for c in cands:
        if (c / "audit-logs").is_dir() and (c / "CLAUDE.md").exists():
            return c
    return cands[-1]


def _sink() -> Path:
    return _zone_root() / "audit-logs" / "hooks" / "tool-probe-receipts.jsonl"


def _current_tic() -> int | None:
    """Cheap, fail-soft: tic_context.current_tic from the live mandate (the same
    resolution boot-read-gate uses — one clock, not two)."""
    try:
        m = json.loads((_zone_root() / "audit-logs" / "mogul" / "mandates" / "current.json")
                       .read_text(encoding="utf-8"))
        t = (m.get("tic_context") or {}).get("current_tic")
        return t if isinstance(t, int) else None
    except Exception:
        return None


_SURFACES = ("call_attempt", "schema_load", "roster_observed")


def cmd_record(args: argparse.Namespace) -> int:
    tic = args.tic if args.tic is not None else _current_tic()
    if tic is None:
        print(json.dumps({"status": "error", "reason": "tic unresolvable; pass --tic"}))
        return 1
    if args.surface not in _SURFACES:
        print(json.dumps({"status": "error", "reason": f"surface must be one of {_SURFACES}"}))
        return 1
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tic": tic,
        "tool": args.tool,
        "surface": args.surface,
        "result": args.result,
        "actor": args.actor,
    }
    path = _sink()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(".lock")
    with open(lock, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644),
                           "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
    print(json.dumps({"status": "recorded", "tic": tic, "tool": args.tool,
                      "surface": args.surface, "sink": str(path)}))
    return 0


def _load_receipts(tic: int) -> list[dict]:
    path = _sink()
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("tic") == tic:
            out.append(r)
    return out


def cmd_check(args: argparse.Namespace) -> int:
    tic = args.tic if args.tic is not None else _current_tic()
    if tic is None:
        # fail-soft posture is the CALLER's (the gate allows on unresolvable tic);
        # the engine itself reports honestly.
        print(json.dumps({"status": "no_receipt", "reason": "tic unresolvable"}))
        return 3
    rs = _load_receipts(tic)
    if args.tool:
        hits = [r for r in rs if (r.get("tool") or "").lower() == args.tool.lower()]
        if hits:
            print(json.dumps({"status": "receipt_found", "tic": tic, "tool": args.tool,
                              "surfaces": sorted({r.get("surface") for r in hits})}))
            return 0
        reason = (f"receipts exist at tic {tic} but none for tool '{args.tool}'"
                  if rs else f"no probe receipts at tic {tic}")
        print(json.dumps({"status": "no_receipt", "tic": tic, "tool": args.tool, "reason": reason}))
        return 3
    if rs:
        print(json.dumps({"status": "receipt_found", "tic": tic,
                          "tools": sorted({r.get("tool") for r in rs})}))
        return 0
    print(json.dumps({"status": "no_receipt", "tic": tic, "reason": f"no probe receipts at tic {tic}"}))
    return 3


def _self_test() -> int:
    """Self-test against a THROWAWAY sink (root-pinned per Self-Locating Artifact
    Test Isolation — fixtures must not leak into the real zone)."""
    import tempfile
    global _sink  # noqa: PLW0603
    failures = []

    def check(name, cond):
        print(("PASS" if cond else "FAIL"), name)
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "receipts.jsonl"
        real_sink = _sink
        _sink = lambda: tmp  # noqa: E731
        try:
            ns = argparse.Namespace(tool="Agent", surface="call_attempt",
                                    result="exists but is not enabled", actor="ent_test", tic=999)
            check("record exits 0", cmd_record(ns) == 0)
            check("check same tool+tic → 0",
                  cmd_check(argparse.Namespace(tool="Agent", tic=999)) == 0)
            check("check tool case-insensitive → 0",
                  cmd_check(argparse.Namespace(tool="agent", tic=999)) == 0)
            check("check other tool same tic → 3",
                  cmd_check(argparse.Namespace(tool="Workflow", tic=999)) == 3)
            check("check any-tool same tic → 0",
                  cmd_check(argparse.Namespace(tool=None, tic=999)) == 0)
            check("check other tic → 3",
                  cmd_check(argparse.Namespace(tool="Agent", tic=1000)) == 3)
            check("bad surface rejected",
                  cmd_record(argparse.Namespace(tool="X", surface="vibes",
                                                result="r", actor="a", tic=999)) == 1)
        finally:
            _sink = real_sink
    print()
    if failures:
        print(f"{len(failures)} FAILED:", ", ".join(failures))
        return 1
    print("all tool-probe-receipt self-checks PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="record a probe receipt (an ATTEMPT, not a verdict)")
    r.add_argument("--tool", required=True)
    r.add_argument("--surface", required=True, choices=_SURFACES)
    r.add_argument("--result", required=True,
                   help="what actually happened (e.g. 'exists but is not enabled in this context')")
    r.add_argument("--actor", default="ent_homeskillet")
    r.add_argument("--tic", type=int, default=None)
    c = sub.add_parser("check", help="exit 0 if a qualifying same-tic receipt exists, else 3")
    c.add_argument("--tool", default=None)
    c.add_argument("--tic", type=int, default=None)
    args = ap.parse_args()
    return cmd_record(args) if args.cmd == "record" else cmd_check(args)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    sys.exit(main())
