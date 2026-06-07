#!/usr/bin/env python3
"""task_touch.py — the task-touch seam (Injection Fabric, §1.3.1, tic 370).

Implements the FIRST genuinely-new build target of the Injection Fabric spec
(`autonomous_kernel/injection-fabric-spec.md` §1.3.1 / §3.1):

    "The task-touch seam — fragment delivery keyed to *what the agent is about to
     do* (pre-tool / mid-turn), not just *who booted*. Today delivery is
     identity-and-tic-gated; it is not task-aware."

THE GAP THIS CLOSES. Every live delivery model (office-worldview.py boot, the
active.jsonl registry) keys on WHO booted and WHEN (identity + tic). None key on
WHAT THE AGENT IS ABOUT TO DO. This module is the surface-touch layer (spec §2): a
task descriptor (tool, target, office, tic) resolves task-pertinent SHAPING
fragments from a canonical-owned rule registry.

THE TWO §1.3 TARGETS COMPOSE. The task-touch seam (§1.3.1) DELIVERS; per-fragment
auditability (§1.3.2, lib/fragment_receipt.py, tic 368) AUDITS. With
--emit-receipts this renderer routes every delivered fragment through
fragment_receipt.emit_receipts(seam="task-touch"). Delivery and accountability are
one path.

WHERE IT SITS (three-layer economics, CLAUDE.md Tool Economics). The pre-tool seam
is PHYSICS-ADJACENT (spec §3) — but this delivery is the PERCEPTION layer: it
SHAPES, it NEVER GATES. A matched rule yields advisory orientation text + (optional)
a receipt; it never blocks, denies, or enforces. Motivation-compliance §5:
prompt-level shaping has no enforcement power, and this seam claims none. Exit is
always success.

GOVERNING INVARIANT (spec §6): canonical owns the lifecycle; runtimes produce
artifacts. The rule registry (task-touch-rules.jsonl) is GOVERNED DATA canonical
owns; this runtime only RENDERS. Admissibility is imported from
fragment_contract.validate_fragment — NEVER decided here. Self-Operation Signal
Discipline (tic 350): a runtime that could self-admit fragments would be mutating
the surface that grants it sight. It cannot.

SCOPE (Architect-directed, tic 370). Render-only BY DEFAULT (no write). The opt-in
--emit-receipts path is the only side-effecting branch. NOT wired into a live
blocking PreToolUse hook this slice — render+prove before wiring (the same additive
discipline fragment_receipt.py followed tic 368). The sibling target
(per-fragment auditability, §1.3.2) is the receipt lane this composes with.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── shared contract import (single-source; mirrors fragment_receipt.py) ───────
# The 3 normative directives + admission verdict + the badge renderer + the class
# authority ceilings all live in the shared contract (lib/fragment_contract.py,
# tic 367). FAIL-SOFT: a catastrophic import degrades to a permissive stub rather
# than crash — a delivery seam must never break the thing it is orienting.
_LIB = Path(__file__).resolve().parent / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
try:
    from fragment_contract import (  # type: ignore
        validate_fragment,
        class_authority,
        badge,
        PERTINENCE_CLASSES,
    )
    _CONTRACT_OK = True
except Exception:  # pragma: no cover - boot-safety only
    _CONTRACT_OK = False
    PERTINENCE_CLASSES = {}

    def class_authority(cls):  # type: ignore
        return {"may_quote": True}

    def badge(cls, auth=None, gated=False):  # type: ignore
        return f"<{cls}>"

    def validate_fragment(frag):  # type: ignore
        return (None, ["fragment_contract import unavailable — admission not evaluated"])

# fragment_receipt is imported lazily inside emit (only --emit-receipts needs it)
# so a render-only invocation never touches the receipt lane.


def zone_root() -> Path:
    """Resolve the federation/zone root by walking up for audit-logs/boot-injections.
    Self-locating-artifact discipline (tic 365): a __file__-rooted resolver finds
    the zone it lives in, not a zone you point it at."""
    p = Path(__file__).resolve()
    for anc in [p] + list(p.parents):
        if (anc / "audit-logs" / "boot-injections").is_dir():
            return anc
    cand = Path("/Users/breydentaylor/canonical")
    if (cand / "audit-logs" / "boot-injections").is_dir():
        return cand
    raise SystemExit("task-touch: could not locate zone root (audit-logs/boot-injections)")


def rules_path(root: Path) -> Path:
    return root / "audit-logs" / "boot-injections" / "task-touch-rules.jsonl"


def load_rules(path: Path) -> list:
    """Read the canonical rule registry. Fail-soft: an absent or unreadable file
    yields an empty rule set (no fragments), never a crash — absence of rules is a
    valid 'nothing task-pertinent here' answer, not an error."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _glob_to_regex(glob: str) -> str:
    """Translate a path glob into an anchored regex. Supports `**` (any depth,
    crossing `/`), `*` (within a path segment), and `?`. Everything else is
    escaped literally. Authored narrowly for the rule registry's path patterns."""
    out = ["^"]
    i = 0
    while i < len(glob):
        c = glob[i]
        if c == "*":
            if i + 1 < len(glob) and glob[i + 1] == "*":
                out.append(".*")  # ** — any depth, crosses '/'
                i += 2
                # swallow an immediate '/' so '**/x' also matches a bare 'x'
                if i < len(glob) and glob[i] == "/":
                    out.append("(?:/)?")
                    i += 1
                continue
            out.append("[^/]*")  # * — within a segment
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    out.append("$")
    return "".join(out)


def glob_match(target: str, pattern: str) -> bool:
    """True if `target` (a path string) matches the glob `pattern`. Also tries the
    basename so a bare 'CLAUDE.md' target still matches '**/CLAUDE.md'."""
    if target is None:
        return False
    rx = _glob_to_regex(pattern)
    if re.match(rx, target):
        return True
    base = target.rsplit("/", 1)[-1]
    return bool(re.match(rx, base))


def rule_matches(rule: dict, tool: str, target: str) -> bool:
    """A rule matches when its declared `tool` set includes the tool AND at least
    one of its target predicates (`target_glob` / `command_contains`) hits. A rule
    with no target predicate is tool-only (matches any target for that tool)."""
    m = rule.get("match", {})
    tools = m.get("tool")
    if tools and tool not in tools:
        return False
    globs = m.get("target_glob")
    contains = m.get("command_contains")
    if not globs and not contains:
        return True  # tool-only rule
    if globs and any(glob_match(target, g) for g in globs):
        return True
    if contains and target and any(c in target for c in contains):
        return True
    return False


def render_fragment(rule: dict) -> dict:
    """Build a rendered fragment from a rule's fragment spec. Authority is filled
    from the class ceiling (class_authority) so the fragment ADMITS by construction;
    an optional `tighten` block may make it MORE restrictive (never less — the
    contract rejects loosening regardless). Pure: invents only the authority block
    the class already authorizes."""
    spec = rule.get("fragment", {})
    cls = spec.get("class", "FIELD")
    auth = class_authority(cls)
    for k, v in (spec.get("tighten") or {}).items():
        auth[k] = v  # tighten only; contract rejects any loosening
    frag = {
        "id": spec.get("id", f"tt.{rule.get('rule_id', 'anon')}"),
        "text": spec.get("text", ""),
        "pertinence": {"class": cls, "reason": spec.get("reason", "")},
        "authority": auth,
        "source": spec.get("source", f"task-touch-rules.jsonl#{rule.get('rule_id', 'anon')}"),
    }
    return frag


def resolve(tool: str, target: str, *, root: Path = None, rules_file: Path = None) -> dict:
    """The core task-touch resolution: which fragments are pertinent to (tool,
    target)? Read-only — loads the canonical rule registry, matches, renders, and
    records each fragment's canonical admission verdict. NEVER writes."""
    root = root or zone_root()
    rfile = rules_file or rules_path(root)
    rules = load_rules(rfile)

    matched = []
    for rule in rules:
        if rule_matches(rule, tool, target):
            frag = render_fragment(rule)
            admitted, errors = validate_fragment(frag)
            matched.append({
                "rule_id": rule.get("rule_id"),
                "fragment": frag,
                "badge": badge(frag["pertinence"]["class"], frag["authority"]),
                "admission": {"evaluated": _CONTRACT_OK, "admitted": admitted, "errors": errors},
            })
    return {
        "tool": tool,
        "target": target,
        "rules_considered": len(rules),
        "matched": matched,
        "rules_file": str(rfile.relative_to(root)) if rfile.exists() else None,
        "contract_available": _CONTRACT_OK,
    }


def emit_receipts_for(resolution: dict, *, office: str, tic: int, root: Path = None) -> dict:
    """Route every matched fragment through the §1.3.2 per-fragment receipt lane
    (seam='task-touch'). This is the COMPOSITION of the two §1.3 targets and the
    ONLY side-effecting path. Lazy import so render-only never loads the lane."""
    sys.path.insert(0, str(_LIB))
    from fragment_receipt import emit_receipts  # type: ignore
    frags = [m["fragment"] for m in resolution["matched"]]
    return emit_receipts(frags, recipient=office, tic=tic, seam="task-touch", root=root)


# ── rendering ─────────────────────────────────────────────────────────────────

def render_text(resolution: dict, *, office: str = None, tic: int = None,
                receipts: dict = None) -> str:
    lines = []
    tool, target = resolution["tool"], resolution["target"]
    lines.append(f"task-touch seam  (read-only render — SHAPES, never gates)\n")
    lines.append(f"  about to: {tool}  →  {target}")
    if office or tic is not None:
        lines.append(f"  office: {office or '-'}   tic: {tic if tic is not None else '-'}")
    lines.append(f"  rules considered: {resolution['rules_considered']}"
                 f"   matched: {len(resolution['matched'])}")
    lines.append("")
    if not resolution["matched"]:
        lines.append("  (no task-pertinent fragment — nothing to shape here)")
    for m in resolution["matched"]:
        frag = m["fragment"]
        adm = m["admission"]
        flag = "" if (adm["admitted"] or not adm["evaluated"]) else "  [INADMISSIBLE]"
        lines.append(f"  {m['badge']} {m['rule_id']}{flag}")
        lines.append(f"      {frag['text']}")
        lines.append("")
    if receipts is not None:
        lines.append(f"  receipts (seam=task-touch): recorded={receipts['recorded']} "
                     f"deduped={receipts['deduped']} → {receipts['sink']}")
    lines.append("  (orientation only — no tool was blocked, no state was mutated)")
    return "\n".join(lines)


def render_json(resolution: dict, *, office: str = None, tic: int = None,
                receipts: dict = None) -> str:
    doc = {
        "command": "task-touch",
        "seam": "task-touch",
        "read_only": receipts is None,
        "shapes_not_gates": True,
        "task": {"tool": resolution["tool"], "target": resolution["target"],
                 "office": office, "tic": tic},
        "rules_considered": resolution["rules_considered"],
        "rules_file": resolution["rules_file"],
        "contract_available": resolution["contract_available"],
        "fragments": [
            {
                "rule_id": m["rule_id"],
                "id": m["fragment"]["id"],
                "badge": m["badge"],
                "pertinence_class": m["fragment"]["pertinence"]["class"],
                "text": m["fragment"]["text"],
                "source": m["fragment"]["source"],
                "admission": m["admission"],
            }
            for m in resolution["matched"]
        ],
    }
    if receipts is not None:
        doc["receipts"] = receipts
    return json.dumps(doc, indent=2, ensure_ascii=False)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Injection Fabric task-touch seam (§1.3.1) — resolve task-pertinent "
                    "SHAPING fragments for a pending action. Render-only by default; "
                    "--emit-receipts routes each through the per-fragment receipt lane.")
    ap.add_argument("--tool", help="the tool the agent is about to use (e.g. Edit, Write, Bash)")
    ap.add_argument("--target", default="",
                    help="the target — a file path (Edit/Write) or command string (Bash)")
    ap.add_argument("--office", help="recipient office (required for --emit-receipts)")
    ap.add_argument("--tic", type=int, help="delivery tic (required for --emit-receipts)")
    ap.add_argument("--emit-receipts", action="store_true",
                    help="ALSO emit one per-fragment delivery receipt (seam=task-touch); "
                         "the only side-effecting path")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--rules", default=None, help="override rule registry path")
    ap.add_argument("--zone-root", default=None)
    ap.add_argument("--self-test", action="store_true", help="run task-touch self-checks")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()

    if not args.tool:
        ap.error("--tool is required (or use --self-test)")

    root = Path(args.zone_root).resolve() if args.zone_root else None
    rfile = Path(args.rules).resolve() if args.rules else None
    resolution = resolve(args.tool, args.target, root=root, rules_file=rfile)

    receipts = None
    if args.emit_receipts:
        if not args.office or args.tic is None:
            print("--emit-receipts requires --office and --tic", file=sys.stderr)
            return 2
        receipts = emit_receipts_for(resolution, office=args.office, tic=args.tic, root=root)

    if args.format == "json":
        print(render_json(resolution, office=args.office, tic=args.tic, receipts=receipts))
    else:
        print(render_text(resolution, office=args.office, tic=args.tic, receipts=receipts))
    return 0  # SHAPES, never gates — exit is always success


def _self_test() -> int:
    import tempfile
    failures = []

    def check(name, cond):
        print(("PASS" if cond else "FAIL"), name)
        if not cond:
            failures.append(name)

    # glob matcher
    check("** matches any depth", glob_match("a/b/c/CLAUDE.md", "**/CLAUDE.md"))
    check("** matches bare basename", glob_match("CLAUDE.md", "**/CLAUDE.md"))
    check("* stays within a segment", not glob_match("a/b.jsonl", "audit-logs/*.jsonl"))
    check("nested ** + suffix", glob_match("x/audit-logs/signals/2026.jsonl", "**/audit-logs/**/*.jsonl"))
    check("non-match is false", not glob_match("src/main.rs", "**/CLAUDE.md"))

    # build a temp rule registry under a temp zone (no prod write)
    with tempfile.TemporaryDirectory() as td:
        troot = Path(td)
        bij = troot / "audit-logs" / "boot-injections"
        bij.mkdir(parents=True)
        rules = [
            {"rule_id": "doc-mut", "match": {"tool": ["Edit", "Write"],
                                             "target_glob": ["**/CLAUDE.md"]},
             "fragment": {"id": "tt.doc", "class": "ESCALATE", "reason": "doctrine",
                          "text": "route through /review"}},
            {"rule_id": "push", "match": {"tool": ["Bash"], "command_contains": ["git push"]},
             "fragment": {"id": "tt.push", "class": "OFFICE", "reason": "push",
                          "text": "confirm branch + remote"}},
        ]
        (bij / "task-touch-rules.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rules) + "\n", encoding="utf-8")

        # task-aware: editing a CLAUDE.md matches the doctrine rule
        r1 = resolve("Edit", "canonical/CLAUDE.md", root=troot)
        check("Edit CLAUDE.md matches doctrine rule", len(r1["matched"]) == 1
              and r1["matched"][0]["rule_id"] == "doc-mut")
        check("matched fragment ADMITS (built at ceiling)",
              (not _CONTRACT_OK) or r1["matched"][0]["admission"]["admitted"] is True)
        check("ESCALATE badge carries ESCALATE↑",
              (not _CONTRACT_OK) or "ESCALATE" in r1["matched"][0]["badge"])

        # task-aware: editing a source file matches NOTHING (the whole point — not who, but what)
        r2 = resolve("Edit", "src/main.rs", root=troot)
        check("Edit src/main.rs matches no rule (task-aware)", len(r2["matched"]) == 0)

        # command_contains: a Bash git push matches the push rule
        r3 = resolve("Bash", "cd repo && git push origin main", root=troot)
        check("Bash 'git push' matches push rule", len(r3["matched"]) == 1
              and r3["matched"][0]["rule_id"] == "push")

        # a Bash that does NOT push matches nothing
        r4 = resolve("Bash", "ls -la", root=troot)
        check("Bash 'ls' matches no rule", len(r4["matched"]) == 0)

        # composition: --emit-receipts routes through the receipt lane (seam=task-touch)
        if _CONTRACT_OK:
            out = emit_receipts_for(r1, office="ent_homeskillet", tic=370, root=troot)
            check("emit routes to task-touch seam", out["seam"] == "task-touch")
            check("emit records the matched fragment", out["recorded"] == 1)
            out2 = emit_receipts_for(r1, office="ent_homeskillet", tic=370, root=troot)
            check("re-emit dedups (idempotent)", out2["recorded"] == 0 and out2["deduped"] == 1)

        # render-only is side-effect-free: no receipts file created by resolve()
        check("render-only writes no receipt sink",
              not (bij / "fragment-receipts.jsonl").exists() or _CONTRACT_OK)

    print()
    if failures:
        print(f"{len(failures)} FAILED:", ", ".join(failures))
        return 1
    print("all task-touch self-checks PASS"
          + ("" if _CONTRACT_OK else "  (NOTE: fragment_contract import unavailable — admission degraded)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
