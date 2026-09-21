#!/usr/bin/env python3
"""test_queue_writer_class_closure_tic812.py — THE CLASS-CLOSING CENSUS TEST.

RULED /review 804 round 2 (Ruling A', Architect-ratified on the recommended
option verbatim: "Adopt x3 + a class-closing test"), item 3; KEPT at /review 811
round 1 Q3. Ruling receipt:
  audit-logs/governance/receipts/2026-09-19-tic804-queue-writer-class-closure-ruling.md

WHAT THIS TEST IS FOR — the ruling's own words: "fails whenever any file under
the censused trees opens the real queue for append without the helper, so an
EIGHTH writer is found by structure and not by the next seat's grep."

THE HISTORY THAT EARNED IT. /review 801 keyed the projection recompile on the
writer. /review 803 put the body in ONE shared helper and wired five writers,
and its rider called the projection "writer-fresh for five of six writers". Both
denominators were ASSERTED, never censused: the tic-803 build seat then found a
SEVENTH live appender (arena-pressure-ingest.py, F-803-C3 HIGH) and an EIGHTH
and NINTH (correction_reconciler.py, queue_event_writer.py, F-803-C4). Two
consecutive rulings each named a writer count that the next build seat had to
correct. A count in prose rots; a test does not.

DOES-NOT-SATISFY RIDER (travels verbatim, on ONE unbroken line so a byte-exact grep resolves it): this increment does NOT add a reader-side staleness detector, does NOT prove two writers racing leave a whole projection, does NOT cure the ImportError double-append hazard (F-803-C6), and does NOT make the projection authoritative over the queue — queue.jsonl latest-per-id remains the only authority.

═══════════════════════════════════════════════════════════════════════════════
THE CENSUS CONTRACT — trees, detection, and drops, ALL STATED
═══════════════════════════════════════════════════════════════════════════════

TREES CENSUSED (exactly two; both are required and neither may silently vanish):
  1. CGG_TREE  — the CGG runtime tree that owns this file. Resolved as
     Path(__file__).parent.parent (scripts/ -> cgg-runtime/). A CODE lookup:
     it travels with the installation.
  2. DATA_TREE — the federation's audit-logs data tree, where the queue and its
     out-of-cgg-runtime writers live. Resolved by walking UP from the CGG tree
     for a `.ticzone`, then through zone_root.audit_logs_path (the existing
     resolver — a second zone reader minted here would be the exact
     counter-disagreement shape `Disagreement-as-evidence` names).

  Either tree may be overridden for test isolation by an environment variable
  (CENSUS_CGG_TREE_ENV / CENSUS_DATA_TREE_ENV below). AN OVERRIDE THAT IS SET
  BUT EMPTY IS REFUSED, LOUDLY — an empty override silently degrades to the
  DEFAULT, which for this census means walking the REAL trees while the caller
  believes it is sandboxed. That exact shape wrote live state at tic 811.

  AN UNRESOLVABLE OR UNREADABLE TREE IS A FAILURE WITH A MESSAGE, NEVER A SKIP.
  A census that cannot read its tree finds nothing, and "found nothing" is
  indistinguishable from "the class is closed" — which is the one lie this test
  exists to prevent. KNOWN CONSEQUENCE, disclosed rather than skipped around:
  the installed tree (~/.claude/cgg-runtime/) carries no `.ticzone` in its
  ancestry, so running this file FROM THE INSTALLED COPY fails on DATA_TREE
  resolution. That is correct behaviour — the census genuinely cannot be
  performed there — and the message names both lawful cures.

DETECTION (AST, never text): a file is a REAL-QUEUE APPENDER when it contains a
write call
    atomic_append_jsonl(<t>, ...) · dedup_queue_append(<t>, ...) ·
    open(<t>, 'a'|'w') · <t>.write_text(...) ·
    a subprocess argv carrying lib/atomic-append.sh
whose TARGET <t> resolves to the real queue by ONE of three rules:
  R1 LITERAL — <t> carries the constant `queue.jsonl` TOGETHER WITH `cprs`
     (or a single constant containing `cprs/queue.jsonl`). The `cprs` half is
     the discriminator that correctly excludes scripts/standing-engine.py,
     which appends to `biome/university-queue.jsonl` — a different queue.
  R2 ALIAS — <t> is a file-local name assigned from an R1 expression, or from
     such a name wrapped in PATH PLUMBING ONLY (Path/str/os.path/…, and no
     added string constant). This resolves `p = Path(queue_path)` at
     cpr-gate-advance.py, whose write target is the bare name `p`. The
     plumbing-only restriction is load-bearing: a naive "assigned from
     anything queue-ish" rule takes the transitive closure of the module and
     marks nearly every local as a queue alias (measured on the first run of
     this census: six false positives, including report writers).
  R3 CALLER-PARAMETERISED — <t> references the dest of an argparse option
     whose flag names a queue. queue_event_writer.py names no queue path
     anywhere: `--queue` is required=True and its caller (review-execute)
     passes THE REAL QUEUE. A literal-only census is blind to exactly that
     writer, which is why the tic-803 census found it only by hand.
  R4 PARAMETER, ONE HOP, SCOPED PER FUNCTION — a call that hands an R1/R2/R3
     expression to a local function binds THAT function's parameter. This is
     what resolves audit-logs/cprs/correction_reconciler.py. The binding is
     per-function, never a file-wide pool: measured on this census's first
     run, a file-wide pool misread a READ-ONLY index builder
     (corpus-harvest/tools/ubiquity_ledger_joiner.py) as a writer because one
     function reads the queue through a `queue_path` parameter while an
     unrelated function writes a derived index.

HONEST LIMIT, DECLARED: R1-R3 are static. A writer that receives the queue as a
bare function parameter from a caller this file cannot see, with no argparse
contract and no literal anywhere, is NOT detectable here. That residue is
declared negative space, not a claim of completeness.

WHY AST AND NOT grep: civil-audit.py's CONTROL_SET stores prose that QUOTES
other scripts' call sites (`"L512 open(queue_path, 'a') under flock..."`), and
cpr-enrichment-scanner.py's comments quote the mechanism they replaced. A text
census scores those as writers. The AST sees a dict of strings and a comment,
which is what they are. Conversely a text census keyed on the literal path misses
queue_event_writer.py, whose --queue is argparse required=True (caller-supplied,
and IS the real queue in its /review usage).

ADOPTION: a censused appender satisfies the class when it CALLS
`recompile_effective_state(...)` (an AST call, not a mention). The three routes
into that name are all lawful and all detected identically — the in-tree
`from lib.effective_state_recompile import ...`, the same import behind a
sys.path insert, and correction_reconciler.py's source-tree-then-installed-tree
resolver shim, which deliberately keeps the helper's name and its
(ok, detail) contract so there is ONE calling convention.

DROPS (stated rules, applied before the allow-list — a drop is a CLASS, an
allow-list entry is a NAMED FILE):
  D1  non-.py files, and any path with a `__pycache__` component.
  D2  TEST files — `test_*.py`, `*_test.py`, or any path under a `tests/`
      directory. They write FIXTURE queues in temp dirs; the class this test
      closes is production writers of the REAL queue. (This very file is
      dropped by D2, which is why it may quote every mechanism above.)
  D3  files that parse but contain no queue-shaped write call at all — the
      overwhelming majority, never enumerated.

ALLOW-LIST: named files that ARE real-queue writers and are nonetheless lawful
without the shared helper, EACH WITH A REASON (never a silent skip). A stale
allow-list entry — one naming a file that no longer exists — FAILS, so the
allow-list cannot rot into a blanket amnesty.

THE VACUOUS-PASS GUARD (test_census_is_not_vacuous): a detector that silently
went blind would make the main assertion pass by finding nothing. The census is
therefore also asserted to still SEE a known-member set. If a refactor moves
those files, this test fails and demands a human decision — that is the point.
"""
from __future__ import annotations

import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path

CENSUS_CGG_TREE_ENV = "QUEUE_WRITER_CENSUS_CGG_TREE"
CENSUS_DATA_TREE_ENV = "QUEUE_WRITER_CENSUS_DATA_TREE"

HELPER_ENTRY_POINT = "recompile_effective_state"

# NO ENTRY NEEDED, and deliberately absent (both were entries on this file's
# first draft and test_allow_list_has_no_stale_entries removed them by failing):
#   scripts/lib/atomic_append.py — the append PRIMITIVE. Its target is whatever
#     its caller hands it, with no literal and no argparse contract, so the
#     census never flags it and an allow-list entry would be dead amnesty.
#   cprs/queue_state_compile.py — the COMPILER that PRODUCES the projection. It
#     writes the projection, never the queue; likewise never flagged.
# An allow-list is for writers that ARE detected and ARE lawful. A file the
# detector does not flag needs no pardon.
# --- the allow-list: real-queue writers lawful WITHOUT the shared helper -----
# Keyed by path suffix (POSIX form). Every entry carries its REASON.
ALLOW_LIST = {
    "scripts/queue-lifecycle-writeback.py": (
        "Carries its own RATIFIED copy of the recompile contract and was named "
        "OUT of the /review 803 fence by that ruling itself — the 'sixth by its "
        "own code' in the 803 rider. It is the live /review verdict path; "
        "refactoring it onto the shared helper is a separate ruled decision, "
        "not this census's to force."
    ),
    # --- historical one-off repair scripts (run-once, already run) -----------
    "cprs/update-queue-tic167.py": (
        "HISTORICAL ONE-OFF (tic 167): a whole-file queue rewrite, run once as "
        "a repair. Retained as a forensic artifact; it is not a live lane."
    ),
    "governance/backfill-clipped-pattern-lessons-tic398.py": (
        "HISTORICAL ONE-OFF (tic 398): backfill of clipped pattern lessons, "
        "run once. Retained as a forensic artifact."
    ),
    "governance/enrichment-remediation-tic609/migrate-deferred-rows.py": (
        "HISTORICAL ONE-OFF (tic 609): deferred-row migration, run once. Named "
        "for completeness by the tic-803 census (F-803-C4)."
    ),
    "governance/queue-repairs-tic648/a1ext-repair.py": (
        "HISTORICAL ONE-OFF (tic 648): queue repair, run once. Named for "
        "completeness by the tic-803 census (F-803-C4)."
    ),
    # --- build-seat FIXTURE DRIVERS kept as hand-up evidence ------------------
    # Found by this census at tic 825, on the first full-suite run after the
    # tic-824 hand-ups were committed (it failed, loudly, as it should). Each
    # builds a FIXTURE zone under a scratch root and writes that zone's own
    # queue.jsonl; none is handed the live zone, and nothing invokes them.
    # Named one by one, never by a directory prefix: a prefix over build
    # hand-ups would pardon whatever a later seat leaves there.
    "governance/review-824-evidence/build-scanner-notice/drivers/behaviour_diff.py": (
        "BUILD EVIDENCE (tic 824, the scanner join-notice increment): writes a "
        "one-row FIXTURE queue under a scratch root to diff old and new scanner "
        "behaviour. Frozen hand-up evidence; not a live lane."
    ),
    "governance/review-824-evidence/build-scanner-notice/drivers/case_c_queue_writer.py": (
        "BUILD EVIDENCE (tic 824, same increment): writes a one-row FIXTURE "
        "queue under a scratch root for the append-path case. Frozen hand-up "
        "evidence; not a live lane."
    ),
    "governance/review-824-evidence/build-checker-trio/logs/preflight.py": (
        "BUILD EVIDENCE (tic 824, the close-checker trio): writes an EMPTY "
        "fixture queue.jsonl into a scratch preflight zone so the checker's path "
        "resolvers can be exercised. Frozen hand-up evidence; not a live lane."
    ),
}

# Suffixes whose ANY-match means 'a recovered copy of a historical one-off'.
# Kept as a prefix rule rather than N near-identical entries because the
# recovery tree mirrors the same file at two different recovered roots.
ALLOW_PREFIX = {
    "governance/tmp-recovery/": (
        "RECOVERED SCRATCH (tic 591 recovery tree): copies of one-off scripts "
        "restored from a temp-dir recovery. Forensic artifacts, never a live "
        "lane; they are not invoked by anything."
    ),
}

# The vacuous-pass guard's known members: files the census MUST still see as
# real-queue appenders. Not an exhaustive denominator — a floor.
# A civil-audit.py-shaped fixture: a registry of PROSE that QUOTES other
# scripts' call sites. A text census scores this as a writer; the AST sees a
# dict of strings, which is what it is.
_REGISTRY_PROSE_FIXTURE = '''CONTROL_SET = {
    "x.py": {"why": "L512 `open(queue_path, 'a')` under flock appends to audit-logs/cprs/queue.jsonl. 0/6 mechanism tokens."},
    "y.py": {"why": "L867 `atomic_append_jsonl(queue_path, env)` appends mined rows to audit-logs/cprs/queue.jsonl."},
}
'''

KNOWN_CENSUS_MEMBERS = (
    "scripts/arena-pressure-ingest.py",
    "scripts/cogpr-ingest.py",
    "scripts/cpr-extract.py",
    "scripts/cpr-gate-advance.py",
    "scripts/cpr-enrichment-scanner.py",
    "scripts/pattern_miner.py",
    "scripts/queue_event_writer.py",
    "scripts/queue-lifecycle-writeback.py",
    "cprs/correction_reconciler.py",
)


class CensusError(RuntimeError):
    """Raised for any condition that must FAIL the census, never skip it."""


# ═══════════════════════════════════════════════════════════════════════════
# TREE RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════

def _override(var):
    """Read an override. SET-BUT-EMPTY is refused; unset returns None."""
    if var not in os.environ:
        return None
    raw = os.environ[var]
    if not raw.strip():
        raise CensusError(
            f"{var} is SET BUT EMPTY. An empty override is not a no-op: it "
            f"falls back to the DEFAULT tree, so a caller who believes it is "
            f"sandboxed would census (and a sibling program would write) the "
            f"REAL zone. Pass an explicit non-empty path or unset the variable."
        )
    p = Path(raw).expanduser()
    if not p.is_dir():
        raise CensusError(f"{var}={raw!r} is not a readable directory.")
    return p.resolve()


def resolve_cgg_tree():
    ov = _override(CENSUS_CGG_TREE_ENV)
    if ov is not None:
        return ov
    tree = Path(__file__).resolve().parent.parent
    if not tree.is_dir():
        raise CensusError(f"CGG tree {tree} is not a readable directory.")
    return tree


def resolve_data_tree(cgg_tree):
    ov = _override(CENSUS_DATA_TREE_ENV)
    if ov is not None:
        return ov
    here = cgg_tree.resolve()
    for cand in (here, *here.parents):
        if (cand / ".ticzone").is_file():
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from zone_root import audit_logs_path, load_ticzone  # noqa: E402
            data = Path(audit_logs_path(str(cand), load_ticzone(str(cand))))
            if not data.is_dir():
                raise CensusError(
                    f"zone {cand} resolves its data tree to {data}, which is "
                    f"not a readable directory."
                )
            return data.resolve()
    raise CensusError(
        f"DATA TREE UNRESOLVABLE: no `.ticzone` found walking up from {here}. "
        f"This census REFUSES to skip — a census that reads no tree finds no "
        f"writers, and 'found nothing' is indistinguishable from 'the class is "
        f"closed'. Two lawful cures: (1) run this test from the source "
        f"checkout, whose zone root carries `.ticzone`; or (2) set "
        f"{CENSUS_DATA_TREE_ENV} to an explicit, non-empty audit-logs path. "
        f"NOTE: the installed tree (~/.claude/cgg-runtime/) has no `.ticzone` "
        f"in its ancestry by design, so this failure is EXPECTED there."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AST DETECTION
# ═══════════════════════════════════════════════════════════════════════════

SAFE_WRAPPERS = frozenset({
    "Path", "PosixPath", "str", "os", "path", "fspath", "resolve",
    "expanduser", "absolute", "join", "abspath", "parent", "parents",
})


def _consts(node):
    """Every string constant inside an expression."""
    return {n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _significant_names(node, dests):
    """Names in an expression, SKIPPING the base of `<ns>.<queue_dest>`.

    `Path(args.queue)` must read as plumbing around the queue dest, not as a
    reference to some unrelated name `args`.
    """
    skip = set()
    for n in ast.walk(node):
        if (isinstance(n, ast.Attribute) and n.attr in dests
                and isinstance(n.value, ast.Name)):
            skip.add(id(n.value))
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and id(n) not in skip:
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def _literal_real_queue(node):
    """R1 — the expression LITERALLY names the CPR queue.

    Requires the `cprs` segment beside `queue.jsonl`. That is the discriminator
    that correctly EXCLUDES scripts/standing-engine.py, which appends to
    `biome/university-queue.jsonl` — a different queue, and the same exclusion
    the tic-803 census made by hand.
    """
    consts = _consts(node)
    if any("cprs/queue.jsonl" in c for c in consts):
        return True
    return "queue.jsonl" in consts and "cprs" in consts


def _pure_wrapper_of(node, known, dests):
    """R2 — the expression is `known` wrapped in PATH PLUMBING ONLY.

    Resolves `p = Path(queue_path)` (cpr-gate-advance.py) and
    `queue_path = Path(args.queue)` (a1ext-repair.py) WITHOUT the runaway
    transitive closure a naive rule produces: `rows = load_latest(queue_path)`
    introduces `load_latest`, which is not plumbing, so `rows` is NOT an alias.
    Any added string constant also disqualifies — a new path segment means a
    DIFFERENT path, which is how a report writer stops being a queue writer.
    """
    names = _significant_names(node, dests)
    if not (names & (known | dests)):
        return False
    if _consts(node):
        return False
    return not (names - known - dests - SAFE_WRAPPERS)


def _argparse_queue_dests(tree):
    """R3 — dest names of argparse options whose FLAG names a queue.

    queue_event_writer.py names no queue path anywhere: `--queue` is
    `required=True` and the target is supplied by its caller (review-execute),
    which passes THE REAL QUEUE. A literal-only census is blind to exactly that
    writer — which is how the tic-803 census found it only by hand. Detecting
    the argparse contract rather than hardcoding a filename means the NEXT
    caller-parameterised writer is caught too.
    """
    dests = set()
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "add_argument"):
            continue
        flags = [a.value for a in n.args
                 if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if not any("queue" in f.lower() for f in flags):
            continue
        dest = None
        for kw in n.keywords:
            if kw.arg == "dest" and isinstance(kw.value, ast.Constant):
                dest = kw.value.value
        if dest is None:
            long = [f for f in flags if f.startswith("--")]
            if not long:
                continue
            dest = long[0].lstrip("-").replace("-", "_")
        dests.add(dest)
    return dests


def _shell_append_aliases(tree):
    """Names bound to the lib/atomic-append.sh shell primitive."""
    aliases = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            targets, value = n.targets, n.value
        elif isinstance(n, ast.AnnAssign) and n.value is not None:
            targets, value = [n.target], n.value
        else:
            continue
        if any(c.endswith("atomic-append.sh") for c in _consts(value)):
            for t in targets:
                if isinstance(t, ast.Name):
                    aliases.add(t.id)
    return aliases


def _grow_aliases(scope, seed, dests):
    """Fixpoint over assignments in `scope`, starting from `seed`."""
    aliases = set(seed)
    for _ in range(4):
        before = len(aliases)
        for n in ast.walk(scope):
            if isinstance(n, ast.Assign):
                targets, value = n.targets, n.value
            elif isinstance(n, ast.AnnAssign) and n.value is not None:
                targets, value = [n.target], n.value
            else:
                continue
            if not (_literal_real_queue(value) or _pure_wrapper_of(value, aliases, dests)):
                continue
            for t in targets:
                if isinstance(t, ast.Name):
                    aliases.add(t.id)
        if len(aliases) == before:
            break
    return aliases


def _is_queue_target(node, aliases, dests):
    if _literal_real_queue(node):
        return True
    names = _significant_names(node, dests)
    return bool(names & aliases) or bool(names & dests)


def _param_bindings(tree, module_aliases, dests):
    """R4 — ONE-HOP parameter propagation, SCOPED PER FUNCTION.

    `append_rows(args.queue, rows)` binds the real queue to that function's
    parameter `queue_path`, and the write inside it targets the PARAMETER.
    Without this hop audit-logs/cprs/correction_reconciler.py is invisible: its
    `DEFAULT_QUEUE = SCRIPT_DIR / 'queue.jsonl'` carries no `cprs` constant (the
    script already LIVES in cprs/), so R1 cannot fire, and the write target is a
    parameter, so R3 cannot either.

    THE BINDING IS PER-FUNCTION, not a file-wide pool. Measured on this census's
    first run: a file-wide pool marked audit-logs/corpus-harvest/tools/
    ubiquity_ledger_joiner.py a writer because it READS the queue through one
    function's `queue_path` parameter while an UNRELATED function writes a
    derived index. Scoping the binding to the function whose call actually
    carried the queue removes that whole false-positive class.

    Returns {function_name: {param names bound to the real queue}}.
    """
    funcs = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs[n.name] = ([a.arg for a in n.args.args]
                             + [a.arg for a in n.args.kwonlyargs])
    bound = {}
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)):
            continue
        params = funcs.get(n.func.id)
        if not params:
            continue
        for idx, arg in enumerate(n.args):
            if idx < len(params) and _is_queue_target(arg, module_aliases, dests):
                bound.setdefault(n.func.id, set()).add(params[idx])
        for kw in n.keywords:
            if kw.arg in params and _is_queue_target(kw.value, module_aliases, dests):
                bound.setdefault(n.func.id, set()).add(kw.arg)
    return bound


def _write_sites_in(scope, aliases, dests, shell_aliases):
    """Every write call inside `scope` whose TARGET is the real queue."""
    sites = []
    for n in ast.walk(scope):
        if not isinstance(n, ast.Call):
            continue
        fname = None
        if isinstance(n.func, ast.Name):
            fname = n.func.id
        elif isinstance(n.func, ast.Attribute):
            fname = n.func.attr

        if fname in ("atomic_append_jsonl", "dedup_queue_append") and n.args:
            if _is_queue_target(n.args[0], aliases, dests):
                sites.append((fname, n.lineno))
        elif fname == "open" and n.args:
            mode = ""
            if len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                mode = str(n.args[1].value)
            for kw in n.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if mode[:1] in ("a", "w") and _is_queue_target(n.args[0], aliases, dests):
                sites.append((f"open({mode!r})", n.lineno))
        elif fname == "write_text" and isinstance(n.func, ast.Attribute):
            if _is_queue_target(n.func.value, aliases, dests):
                sites.append(("write_text", n.lineno))
        else:
            uses_primitive = bool(_significant_names(n, dests) & shell_aliases) or any(
                c.endswith("atomic-append.sh") for c in _consts(n))
            if uses_primitive and any(
                    _is_queue_target(a, aliases, dests) for a in ast.walk(n)
                    if isinstance(a, (ast.Name, ast.Call, ast.Attribute, ast.BinOp))):
                sites.append(("atomic-append.sh", n.lineno))
    return sites


def analyse(tree):
    """Full per-file analysis. Returns sorted [(kind, lineno)] write sites."""
    dests = _argparse_queue_dests(tree)
    shell_aliases = _shell_append_aliases(tree)
    module_aliases = _grow_aliases(tree, set(), dests)
    bound = _param_bindings(tree, module_aliases, dests)

    sites = []
    func_nodes = [n for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for fn in func_nodes:
        fn_aliases = _grow_aliases(fn, module_aliases | bound.get(fn.name, set()), dests)
        sites.extend(_write_sites_in(fn, fn_aliases, dests, shell_aliases))

    # Module-level statements (everything not inside a function body).
    module_only = ast.Module(
        body=[b for b in tree.body
              if not isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))],
        type_ignores=[])
    sites.extend(_write_sites_in(module_only, module_aliases, dests, shell_aliases))
    return sorted(set(sites), key=lambda s: (s[1], s[0]))


def _calls_helper(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) else None)
            if name == HELPER_ENTRY_POINT:
                return True
    return False


def _dropped_by_rule(rel_posix):
    parts = rel_posix.split("/")
    if "__pycache__" in parts:
        return "D1:bytecode"
    name = parts[-1]
    if name.startswith("test_") or name.endswith("_test.py") or "tests" in parts[:-1]:
        return "D2:test-file"
    return None


def _allow_reason(path_posix):
    for suffix, reason in ALLOW_LIST.items():
        if path_posix.endswith(suffix):
            return reason
    for prefix, reason in ALLOW_PREFIX.items():
        if prefix in path_posix:
            return reason
    return None


def census(trees):
    """Walk the trees. Returns a report dict. Raises CensusError, never skips."""
    report = {"trees": {k: str(v) for k, v in trees.items()},
              "files_walked": 0, "files_parsed": 0,
              "appenders": [], "unadopted": [], "allowed": [],
              "parse_failures": []}
    for label, root in trees.items():
        if not root.is_dir():
            raise CensusError(f"censused tree {label} at {root} is unreadable.")
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in sorted(filenames):
                if not fn.endswith(".py"):
                    continue
                p = Path(dirpath) / fn
                report["files_walked"] += 1
                rel = p.relative_to(root).as_posix()
                if _dropped_by_rule(rel):
                    continue
                try:
                    src = p.read_text(encoding="utf-8")
                except OSError as exc:
                    raise CensusError(
                        f"UNREADABLE FILE inside censused tree {label}: {p} "
                        f"({exc}). The census refuses to under-count silently."
                    ) from exc
                try:
                    tree = ast.parse(src, filename=str(p))
                except SyntaxError as exc:
                    report["parse_failures"].append({"path": str(p), "error": str(exc)})
                    continue
                report["files_parsed"] += 1
                sites = analyse(tree)
                if not sites:
                    continue
                entry = {"path": str(p), "rel": rel, "tree": label,
                         "sites": sites, "adopted": _calls_helper(tree)}
                report["appenders"].append(entry)
                reason = _allow_reason(p.as_posix())
                if reason:
                    entry["allow_reason"] = reason
                    report["allowed"].append(entry)
                elif not entry["adopted"]:
                    report["unadopted"].append(entry)
    return report


def resolve_trees():
    cgg = resolve_cgg_tree()
    return {"cgg_runtime": cgg, "audit_logs_data": resolve_data_tree(cgg)}


# ═══════════════════════════════════════════════════════════════════════════
# THE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class QueueWriterClassClosure(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # A resolution failure propagates as an ERROR (never a skip) — that is
        # the ruled behaviour for an unreadable/unresolvable tree.
        cls.trees = resolve_trees()
        cls.report = census(cls.trees)

    def test_no_unadopted_real_queue_appender(self):
        """THE CLASS-CLOSING ASSERTION."""
        if self.report["unadopted"]:
            lines = [
                "UNADOPTED REAL-QUEUE APPENDER(S) — the writer class is OPEN.",
                "",
                "Each file below writes a queue-shaped target but never calls",
                f"`{HELPER_ENTRY_POINT}(...)`, so a mutation through it leaves",
                "audit-logs/cprs/effective-state/ stale (RULED /review 801, 803,",
                "804). Cures, in order of preference:",
                "  (a) adopt the shared helper after the successful append, ",
                "      fail-soft — mirror scripts/cogpr-ingest.py;",
                "  (b) if the file lives outside cgg-runtime, mirror",
                "      audit-logs/cprs/correction_reconciler.py's resolver shim;",
                "  (c) if it is genuinely not a live writer, add it to ALLOW_LIST",
                "      in this file WITH A REASON — never a silent skip.",
                "",
            ]
            for e in self.report["unadopted"]:
                lines.append(f"  {e['tree']}:{e['rel']}")
                for kind, lineno in e["sites"]:
                    lines.append(f"      L{lineno}  {kind}")
            self.fail("\n".join(lines))

    def test_census_is_not_vacuous(self):
        """A blind detector would pass the assertion above by finding nothing."""
        seen = {e["path"].replace("\\", "/") for e in self.report["appenders"]}
        missing = [m for m in KNOWN_CENSUS_MEMBERS
                   if not any(s.endswith(m) for s in seen)]
        self.assertEqual(
            missing, [],
            "THE CENSUS WENT BLIND (or these files moved). The detector no "
            "longer sees known real-queue appenders, which would make "
            "test_no_unadopted_real_queue_appender pass VACUOUSLY. Missing: "
            f"{missing}. Trees censused: {self.report['trees']}. If the files "
            "genuinely moved, update KNOWN_CENSUS_MEMBERS in the same change "
            "that moved them.")

    def test_allow_list_has_no_stale_entries(self):
        """An allow-list that outlives its files rots into blanket amnesty."""
        allowed_rels = {e["path"].replace("\\", "/") for e in self.report["allowed"]}
        stale = [s for s in ALLOW_LIST
                 if not any(a.endswith(s) for a in allowed_rels)]
        self.assertEqual(
            stale, [],
            f"ALLOW_LIST names file(s) the census no longer sees as real-queue "
            f"appenders: {stale}. Either the file was deleted/moved (drop the "
            f"entry) or it stopped writing the queue (drop the entry) — an "
            f"allow-list entry with no live referent silently widens the "
            f"amnesty for any future file that lands on that path.")

    def test_every_allowance_states_a_reason(self):
        for e in self.report["allowed"]:
            self.assertTrue(
                e.get("allow_reason", "").strip(),
                f"{e['rel']} is allow-listed with no reason — the ruling "
                f"requires an explicit allow-list WITH REASONS, never a silent "
                f"skip.")

    def test_planted_eighth_writer_is_detected(self):
        """NEGATIVE CONTROL, in-test: a planted writer MUST trip the census."""
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "cgg" / "scripts"
            fake.mkdir(parents=True)
            (fake / "planted_eighth_writer.py").write_text(
                "import json\n"
                "from pathlib import Path\n"
                "def append(audit_logs, entry):\n"
                "    queue_file = str(Path(audit_logs) / 'cprs' / 'queue.jsonl')\n"
                "    with open(queue_file, 'a', encoding='utf-8') as f:\n"
                "        f.write(json.dumps(entry) + '\\n')\n",
                encoding="utf-8")
            data = Path(td) / "data"
            data.mkdir()
            rep = census({"cgg_runtime": Path(td) / "cgg", "audit_logs_data": data})
            rels = [e["rel"] for e in rep["unadopted"]]
            self.assertIn(
                "scripts/planted_eighth_writer.py", rels,
                "THE CENSUS FAILED TO DETECT A PLANTED WRITER — it cannot close "
                "the class it was built to close.")

    def test_planted_writer_passes_once_it_adopts(self):
        """The control's other arm: adopting the helper clears the finding."""
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "cgg" / "scripts"
            fake.mkdir(parents=True)
            (fake / "planted_eighth_writer.py").write_text(
                "import json\n"
                "from pathlib import Path\n"
                "from lib.effective_state_recompile import recompile_effective_state\n"
                "def append(audit_logs, entry):\n"
                "    queue_file = str(Path(audit_logs) / 'cprs' / 'queue.jsonl')\n"
                "    with open(queue_file, 'a', encoding='utf-8') as f:\n"
                "        f.write(json.dumps(entry) + '\\n')\n"
                "    recompile_effective_state(queue_file)\n",
                encoding="utf-8")
            data = Path(td) / "data"
            data.mkdir()
            rep = census({"cgg_runtime": Path(td) / "cgg", "audit_logs_data": data})
            self.assertEqual([e["rel"] for e in rep["unadopted"]], [])
            self.assertEqual(len(rep["appenders"]), 1)
            self.assertTrue(rep["appenders"][0]["adopted"])

    def test_a_mere_mention_of_the_helper_is_not_adoption(self):
        """Adoption is an AST CALL, not a comment or a string."""
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "cgg" / "scripts"
            fake.mkdir(parents=True)
            (fake / "pretender.py").write_text(
                "import json\n"
                "from pathlib import Path\n"
                "# we should call recompile_effective_state here one day\n"
                "NOTE = 'recompile_effective_state'\n"
                "def append(audit_logs, entry):\n"
                "    queue_file = str(Path(audit_logs) / 'cprs' / 'queue.jsonl')\n"
                "    with open(queue_file, 'a') as f:\n"
                "        f.write(json.dumps(entry) + '\\n')\n",
                encoding="utf-8")
            data = Path(td) / "data"
            data.mkdir()
            rep = census({"cgg_runtime": Path(td) / "cgg", "audit_logs_data": data})
            self.assertEqual([e["rel"] for e in rep["unadopted"]],
                             ["scripts/pretender.py"])

    def test_string_literals_quoting_a_call_site_are_not_writers(self):
        """civil-audit.py's CONTROL_SET prose must not score as a writer."""
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "cgg" / "scripts"
            fake.mkdir(parents=True)
            (fake / "registry_prose.py").write_text(
                _REGISTRY_PROSE_FIXTURE, encoding="utf-8")
            data = Path(td) / "data"
            data.mkdir()
            rep = census({"cgg_runtime": Path(td) / "cgg", "audit_logs_data": data})
            self.assertEqual(rep["appenders"], [],
                             "prose quoting a call site scored as a real writer")

    def test_empty_override_is_refused_not_silently_defaulted(self):
        """An empty override IS the default — it must be refused, loudly."""
        for var in (CENSUS_CGG_TREE_ENV, CENSUS_DATA_TREE_ENV):
            with self.subTest(var=var):
                prior = os.environ.get(var)
                os.environ[var] = ""
                try:
                    with self.assertRaises(CensusError) as ctx:
                        _override(var)
                    self.assertIn("SET BUT EMPTY", str(ctx.exception))
                finally:
                    if prior is None:
                        os.environ.pop(var, None)
                    else:
                        os.environ[var] = prior

    def test_unresolvable_data_tree_fails_it_does_not_skip(self):
        """A zone-less tree must ERROR with a message, never pytest.skip."""
        with tempfile.TemporaryDirectory() as td:
            zoneless = Path(td) / "cgg-runtime"
            (zoneless / "scripts").mkdir(parents=True)
            prior = os.environ.pop(CENSUS_DATA_TREE_ENV, None)
            try:
                with self.assertRaises(CensusError) as ctx:
                    resolve_data_tree(zoneless)
                msg = str(ctx.exception)
                self.assertIn("DATA TREE UNRESOLVABLE", msg)
                self.assertIn("REFUSES to skip", msg)
            finally:
                if prior is not None:
                    os.environ[CENSUS_DATA_TREE_ENV] = prior

    def test_parse_failures_are_reported_not_swallowed(self):
        self.assertEqual(
            self.report["parse_failures"], [],
            "file(s) under the censused trees do not parse; the census cannot "
            "see inside them and reports rather than swallowing: "
            f"{self.report['parse_failures']}")


def _main():
    """Standalone census report — the same walk the tests assert on."""
    import json
    trees = resolve_trees()
    rep = census(trees)
    print(json.dumps({
        "trees": rep["trees"],
        "files_walked": rep["files_walked"],
        "files_parsed": rep["files_parsed"],
        "appenders_total": len(rep["appenders"]),
        "adopted": sorted(e["rel"] for e in rep["appenders"]
                          if e["adopted"] and "allow_reason" not in e),
        "allow_listed": sorted(e["rel"] for e in rep["allowed"]),
        "unadopted": sorted(e["rel"] for e in rep["unadopted"]),
        "parse_failures": rep["parse_failures"],
        "allow_list_reasons": ALLOW_LIST,
        "allow_prefix_reasons": ALLOW_PREFIX,
    }, indent=2))
    return 1 if rep["unadopted"] else 0


if __name__ == "__main__":
    if "--census" in sys.argv:
        sys.exit(_main())
    unittest.main()
