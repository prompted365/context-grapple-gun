#!/usr/bin/env python3
"""civil-audit.py — the per-script envelope-pattern classification primitive.

WHAT THIS IS
------------
The classification PRIMITIVE that `cgg-runtime/agents/civil-engineer.md`
(§ Envelope-Pattern Compliance Audit) deferred at tic 273 under a PROMOTE-SPEC
verdict-shape: "the per-script classification primitive will be inscribed in
its own tranche." This is that tranche.

It classifies every script in a DECLARED scan scope as exactly one of:

  envelope_aware_via:<mechanism>   writes governance state AND satisfies >=1 of
                                   the ratified six-mechanism OR-gate
  bypass                           writes governance state, satisfies NONE
  not_a_governance_writer          no write call site resolves to a declared
                                   capability-surface emission target
  indeterminate                    has a real write call site whose target does
                                   NOT statically resolve, on a script that
                                   names a capability surface. NEVER silently
                                   cleared, never silently counted — declared
                                   negative space pending hand adjudication.
  excluded_test_fixture            test_*.py

WHAT CHANGED AND WHY (the tic-741 refinement)
---------------------------------------------
The six-mechanism OR-gate is RATIFIED (/review 710) and is reproduced here
UNCHANGED. Only the `writes_governance_state` predicate is refined.

The predicate civil ran BY HAND at tic 690 was a whole-file string
co-occurrence: "a capability-surface path string appears somewhere in the file"
AND "a write-shaped token appears somewhere in the file". Civil measured a 30%
sampled false-positive rate against its own 5% falsification threshold and,
correctly, WITHHELD the bypass classification for six consecutive passes
(690..740) rather than emit counts from a known-broken predicate.

The refined predicate is CALL-SITE-LOCAL and TARGET-RESOLVED: a script writes
governance state IFF it contains a write CALL SITE whose target path expression
resolves to a declared CAPABILITY-SURFACE emission target. A mention is not a
write; a write to a report lane is not a capability emission.

MEASURED CAUSE, NOT ASSUMED CAUSE. The tic-690 report attributed its false
positives to "read-only auditors that merely READ those paths". The tic-741
probe falsified that: all three scripts tic 690 named as false positives
contain REAL write call sites. What makes them false positives is the TARGET
CLASS, not the absence of a write. An "is there a write at all" AST check --
the direction the tic-700 diagnostic pointed at -- would NOT have cleared any
of the three. Every arm below therefore resolves the target, and every
non-capability target class names the FP class it answers.

FALSIFICATION GATE (carried here, not delegated)
------------------------------------------------
The spec's gate -- ">5% false-positive rate OR any false negative -> the
heuristic still requires refinement ... Surface the falsification finding to
Mogul; do not silently widen" -- is EXECUTED by this script against the labeled
control set inscribed below. If FP > 5% or FN > 0 the report carries
`predicate_falsified: true` and names the offending scripts. This script never
widens a mechanism, never edits the agent spec, and never suppresses a
disagreement.

WRITES
------
Read-only over the corpus. Writes ONLY its own report artifact (default
audit-logs/governance/harpoon-office/probe-reports/) or stdout with --stdout.

USAGE
-----
  python3 civil-audit.py                       classify, write report
  python3 civil-audit.py --stdout              classify, print, write nothing
  python3 civil-audit.py --legacy-compare      also run the tic-690 v0 predicate
  python3 civil-audit.py --scope scripts/lib   narrow the declared scan scope
  python3 civil-audit.py --explain foo.py      per-call-site evidence for one script
  python3 civil-audit.py --fail-on-falsified   exit 2 when the gate trips

Provenance: bk-civil-envelope-citation-and-falsification-gate-recurrence,
wave-11B build increment at tic 741, dispatched by ent_homeskillet.
"""

from __future__ import annotations

import argparse
import ast
import datetime as _dt
import json
import sys
from pathlib import Path

# ===========================================================================
# CONTENT LAYER — declared registries.
# Engine-content separation (federation KI: "Engine-content separation is
# mandatory for federation-grade gate primitives"): the classifier below is the
# ENGINE; every list in this block is CONTENT and may be amended at a gate
# without touching the engine.
# ===========================================================================

# --- The ratified six-mechanism OR-gate (civil-engineer.md, /review 710) ----
# This half is RATIFIED. This increment did not touch it. Mechanism 6
# ("constructs an envelope-shaped record") is structural rather than
# token-greppable and is detected by the provenance field-set probe below.
SIX_MECHANISM_TOKENS = {
    # 1. imports inbox_envelope OR routes through the inbox-envelope.py CLI
    "inbox_envelope": ("inbox_envelope", "inbox-envelope.py"),
    # 2. a dedup-at-write primitive from lib.atomic_append (either sibling)
    "dedup_append": ("dedup_signal_append", "dedup_queue_append"),
    # 3. imports atomic_write_json
    "atomic_write_json": ("atomic_write_json",),
    # 4. declares envelope_type literally
    "envelope_type": ("envelope_type",),
    # 5. cites envelopes.yaml (or an envelope-spec file)
    "envelopes_yaml": ("envelopes.yaml",),
}
MECHANISM_6_FIELDS = ("envelope_id", "schema_version", "written_at", "source")
MECHANISM_6_MIN_FIELDS = 3

# --- CAPABILITY-SURFACE EMISSION TARGETS -----------------------------------
# The spec names them: "signal manifold, mailbox, egress, vendor-state, or
# other capability-surface emission". A write whose target resolves INTO one of
# these makes writes_governance_state == yes. Nothing else does.
#
# The CogPR queue is included because /review 710 ratified `dedup_queue_append`
# as envelope mechanism 2 — a queue-side envelope boundary is only meaningful
# if queue writes are inside the audited population.
CAPABILITY_SURFACES = {
    "audit-logs/signals/": "signal_manifold",
    "audit-logs/agent-mailboxes/": "mailbox",
    "audit-logs/services/": "egress_router",
    "audit-logs/routing/": "egress_router",
    "audit-logs/cprs/queue.jsonl": "cogpr_queue",
    "audit-logs/cprs/queue-": "cogpr_queue",
    "audit-logs/media-router/vendors": "vendor_state",
    "audit-logs/external/": "vendor_state",
}

# --- NON-CAPABILITY TARGET CLASSES -----------------------------------------
# Each entry names the FALSE-POSITIVE CLASS it answers. These classes are the
# MEASURED causes from the tic-741 probe, not invented categories.
#
# FP-CLASS-A  report/receipt lane      — a script writing its own audit report
#                                        is a READER of the surfaces it names.
#                                        (queue-drift-audit.py, tic-690 named FP)
# FP-CLASS-B  telemetry / CPG plane    — already carved out in prose by the
#                                        ratified spec; made executable here.
# FP-CLASS-C  doctrine/source surface  — in-place markdown inscription is a
#                                        /review-gated governance write, not an
#                                        envelope emission.
#                                        (review-promote-writeback.py, tic-690 named FP)
# FP-CLASS-D  out-of-federation        — a write landing outside the canonical
#                                        zone cannot be a federation capability
#                                        emission by construction.
#                                        (ripple-assessor.py, tic-690 named FP)
# FP-CLASS-E  test / scratch target    — tmp_path, tempfile, fixture zones.
# FP-CLASS-F  local process state      — lockfiles, hook-seen markers, caches:
#                                        single-process bookkeeping, never an
#                                        inter-entity emission.
NON_CAPABILITY_SURFACES = [
    ("CLAUDE.md", "doctrine_source_surface", "FP-CLASS-C"),
    ("ledger.md", "doctrine_source_surface", "FP-CLASS-C"),
    ("MEMORY.md", "doctrine_source_surface", "FP-CLASS-C"),
    ("SYSTEM_MAP.md", "doctrine_source_surface", "FP-CLASS-C"),
    ("borns-", "doctrine_source_surface", "FP-CLASS-C"),
    ("cgg-runtime/agents/", "doctrine_source_surface", "FP-CLASS-C"),
    ("cgg-runtime/config/", "doctrine_source_surface", "FP-CLASS-C"),
    ("autonomous_kernel/", "doctrine_source_surface", "FP-CLASS-C"),
    ("audit-logs/governance/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/mogul/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/reports/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/reviews/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/review-dockets/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/conformations/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/boot-injections/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/evaluations/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/rollback-drills/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/provenance/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/plans/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/tics/", "report_receipt_lane", "FP-CLASS-A"),
    ("audit-logs/cpg/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/economy/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/harmony/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/contagion/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/biome/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/patterns/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/rtch/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/arenas/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/braid/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/visitor-economy/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/visitors/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/trust/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/posture/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/rebru/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/slices/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/memory-mining/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/consolidations/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/corrections/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/complement/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/cockpit/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/sentinel/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/swarms/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/swarm-rails/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/ladder-auditor/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/shadow-cadence/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/compute/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/cbux/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/heritage/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/bridge/", "telemetry_cpg", "FP-CLASS-B"),
    ("audit-logs/f2/", "telemetry_cpg", "FP-CLASS-B"),
    ("~/.claude", "out_of_federation", "FP-CLASS-D"),
    (".claude/", "out_of_federation", "FP-CLASS-D"),
    ("/tmp/", "out_of_federation", "FP-CLASS-D"),
]

# Checked BEFORE the capability list: a lockfile beside a capability surface is
# process bookkeeping, and a tempfile is a fixture — neither is an emission.
PRE_CAPABILITY_SURFACES = [
    ("<TMP>", "test_scratch", "FP-CLASS-E"),
    (".lock", "local_process_state", "FP-CLASS-F"),
    ("__pycache__", "local_process_state", "FP-CLASS-F"),
    (".ticzone", "local_process_state", "FP-CLASS-F"),
    ("audit-logs/hooks/", "local_process_state", "FP-CLASS-F"),
]

# --- Write verbs the AST engine recognizes ---------------------------------
WRITE_METHODS = {"write_text", "write_bytes", "writelines"}

# lib write helpers: every one takes the target path as first positional arg.
# Two of them carry SURFACE SEMANTICS in the name itself — the /review-710
# ratified sibling pair — so they bind a capability surface even when the target
# expression is a parameter that does not resolve. This arm is FN-safety.
WRITE_HELPERS = {
    "atomic_append_jsonl": None,
    "atomic_write_json": None,
    # lib.atomic_write helper pair — REGISTERED /review 769 (F-768-W6-1: the
    # wave-6 helper was invisible to this audit until named here; six migrated
    # call sites now inside the audited population). Path-first-positional,
    # no surface semantics in the name.
    "atomic_write_bytes": None,
    "atomic_write_text": None,
    "dedup_signal_append": "signal_manifold",
    "dedup_queue_append": "cogpr_queue",
}

# CLI surfaces that write governance state when shelled out to.
#
# THIS IS A CALL-SITE ARM, NOT A MENTION ARM. An earlier cut of this primitive
# matched these tokens anywhere in the file text and thereby REPRODUCED the very
# v0 defect this increment exists to cure: mandate-write.py mentions
# "cadence-ops.py" three times in COMMENTS and was flagged a governance writer;
# this file mentions all three in its own registry and flagged ITSELF. The arm
# now requires a subprocess CALL whose folded argument list contains the CLI.
SUBPROCESS_WRITER_TOKENS = ("inbox-envelope.py", "cadence-ops.py", "trigger-router.py")
SUBPROCESS_CALLS = {"run", "Popen", "check_call", "check_output", "call", "system"}

# --- AUDIT-ROOT ALIASES (declared convention, measured not assumed) --------
# The corpus resolves the audit tree at RUNTIME and passes it down by name, so
# the literal "audit-logs/" never appears at the write call site: e.g.
# trigger-router.py:402 `os.path.join(audit_root, "services")` and
# inbox-envelope.py:180 `os.path.join(audit_root, "agent-mailboxes", entity_id)`.
# Without this binding both scripts — the egress router and the canonical
# mailbox writer — classify as NON-writers, which is the worst possible false
# negative this audit can produce (measured at tic 741: removing the mention
# shortcut exposed exactly these two).
#
# The alias is grounded, not guessed: `zone_root.audit_logs_path()` returns
# `os.path.join(zone_root, ticzone.get("audit_logs_path", "audit-logs"))`, and
# the alias names below are the corpus's own convention for its return value
# (measured across the declared scan scope at tic 741: audit_root x29,
# audit_dir x16, AUDIT_ROOT x13, audit_logs_dir x1).
#
# NON-DEFAULT-CONFIG LIMIT: a zone whose .ticzone overrides `audit_logs_path`
# to a non-default value is NOT modelled here; the alias resolves to the
# default lane. Declared, not hidden.
ROOT_ALIASES = ("audit_root", "audit_logs_root", "audit_dir", "audit_logs_dir",
                "AUDIT_ROOT", "AUDIT_LOGS", "AUDIT_LOGS_DIR")
ROOT_ALIAS_FUNCS = ("audit_logs_path",)
_AUDIT_ROOT_TOKEN = "<ROOT>/audit-logs"

# --- The tic-690 legacy predicate, kept for the --legacy-compare delta ------
# RECONSTRUCTED from the tic-690 report's own description ("a capability-surface
# path string plus any write-shaped token"). The tic-690 run was by hand and was
# never committed, so this is CALIBRATED (it flags all three scripts tic 690
# named as false positives), NOT byte-recovered.
V0_SURFACE_TOKENS = (
    "audit-logs/signals", "audit-logs/agent-mailboxes", "audit-logs/cprs",
    "audit-logs/services", "audit-logs/routing", "audit-logs/mogul",
    "signals", "signal-manifold", "inbox", "mailbox", "egress", "vendor",
    "queue.jsonl", "active-manifest",
)
V0_WRITE_TOKENS = (
    "open(", "write_text", "write_bytes", "writelines",
    "json.dump", "os.replace", "shutil.move", "shutil.copy",
)

# ===========================================================================
# LABELED CONTROL SET — the falsification gate's ground truth.
# Every label was established by READING the script's write call sites at the
# tic named in `verified_at_tic`. A label is evidence, not an assertion: `why`
# cites the resolved target and its line.
# ===========================================================================
CONTROL_SET = {
    # --- MUST NOT be classified as a governance-state writer (FP arm) --------
    # The three false positives civil NAMED at tic 690. Under v0 all three
    # flag; under the refined predicate all three must resolve to a
    # non-capability target class.
    "queue-drift-audit.py": {
        "expect": "not_a_governance_writer",
        "verified_at_tic": 741,
        "why": "sole write site L546 `out_file.write_text(...)`; out_file = OUT_DIR / f'{ts}{tic_part}.json' with OUT_DIR = <ROOT>/audit-logs/governance/queue-drift-audit (L87). Report lane. It READS audit-logs/cprs/queue.jsonl (L86) and never writes it.",
        "fp_class": "FP-CLASS-A",
        "source": "civil report 2026-08-09-tic-690.json finding 22 (named FP)",
    },
    "ripple-assessor.py": {
        "expect": "not_a_governance_writer",
        "verified_at_tic": 741,
        "why": "sole write site L784 `Path(output_path).write_text(proposals)`; output_path = args.output or os.path.expanduser('~/.claude/grapple-proposals/latest.md') (L745). Out of federation. Signals are READ from --signals-dir.",
        "fp_class": "FP-CLASS-D",
        "source": "civil report 2026-08-09-tic-690.json finding 22 (named FP)",
    },
    "review-promote-writeback.py": {
        "expect": "not_a_governance_writer",
        "verified_at_tic": 741,
        "why": "write sites L616/L675/L805 inscribe doctrine/source markdown in place (fpath = a CogPR source file, target = a doctrine surface, lpath = the constitution ledger). queue.jsonl appears only as a READ path (L222, L916).",
        "fp_class": "FP-CLASS-C",
        "source": "civil report 2026-08-09-tic-690.json finding 22 (named FP)",
    },
    # --- MUST stay envelope-aware (FN arm) -----------------------------------
    # The three formerly-false-negative scripts disposed at /review 710.
    "cogpr-ingest.py": {
        "expect": "envelope_aware",
        "verified_at_tic": 741,
        "why": "imports dedup_queue_append (L412, call site L413) — ratified mechanism 2 after the /review-710 widening.",
        "source": "/review 710 amendment provenance; civil 2026-08-26-tic-740.json finding 29",
    },
    "cpr-extract.py": {
        "expect": "envelope_aware",
        "verified_at_tic": 741,
        "why": "imports dedup_queue_append (L1194, call site L1198) — ratified mechanism 2.",
        "source": "/review 710 amendment provenance; civil 2026-08-26-tic-740.json finding 29",
    },
    "ladder-feedback-push.py": {
        "expect": "envelope_aware",
        "verified_at_tic": 741,
        "why": "routes through the inbox-envelope.py CLI by subprocess (path resolved L194, contract L197, docstring L22) — ratified mechanism 1.",
        "source": "/review 710 amendment provenance; civil 2026-08-26-tic-740.json finding 29",
    },
    # --- MUST be classified as governance-state writers (anti-over-narrowing) -
    # If the refinement stops seeing these, it has over-narrowed and the cure
    # would be worse than the disease.
    "inbox-envelope.py": {
        "expect": "envelope_aware",
        "verified_at_tic": 741,
        "why": "the canonical mailbox writer; writes audit-logs/agent-mailboxes/** directly.",
        "source": "tic-741 probe, hand-verified call sites",
    },
    "docks-signal-emitter.py": {
        "expect": "envelope_aware",
        "verified_at_tic": 741,
        "why": "emits to the signal manifold via dedup_signal_append (L168) and to the active manifest (L203).",
        "source": "tic-741 probe, hand-verified call sites",
    },
    "trigger-router.py": {
        "expect": "envelope_aware",
        "verified_at_tic": 741,
        "why": "routes triggers to entity inboxes; mailbox emission via the inbox-envelope surface.",
        "source": "tic-741 probe, hand-verified call sites",
    },
    "cadence-ops.py": {
        "expect": "envelope_aware",
        "verified_at_tic": 741,
        "why": "cadence obligation writer; routes through inbox_envelope and declares envelope_type.",
        "source": "civil report 2026-08-09-tic-690.json finding 22 (verified-correct citation)",
    },
    # --- MUST be classified bypass (true-positive regression guard) ----------
    # Hand-read at tic 741: each writes a resolvable capability-surface target
    # and contains ZERO of the six ratified mechanism tokens (grep count 0).
    # These are the first bypass findings this lane has ever ASSERTED — civil
    # withheld the classification for six passes rather than emit them from a
    # known-30%-FP predicate. They are labeled so a later refinement that
    # silently loses them trips this gate.
    "cpr-enrichment-scanner.py": {
        "expect": "bypass", "verified_at_tic": 741,
        "why": "L1091 `p.write_text('\\n'.join(new_lines) + '\\n')` rewrites the WHOLE of audit-logs/cprs/queue.jsonl under flock. 0/6 mechanism tokens.",
        "source": "tic-741 probe, hand-read call site",
    },
    "cpr-gate-advance.py": {
        "expect": "bypass", "verified_at_tic": 741,
        "why": "L168 `open(p, 'a')` appends a transition row to audit-logs/cprs/queue.jsonl behind its own write-side terminal-valve guard. 0/6 mechanism tokens.",
        "source": "tic-741 probe, hand-read call site",
    },
    "encounter-monitor.py": {
        "expect": "bypass", "verified_at_tic": 741,
        "why": "L213 `atomic_append_jsonl(signal_file, signal)` emits to the signal manifold. It builds a deterministic signal_id but carries no envelope_type / dedup primitive / provenance triple. 0/6 mechanism tokens.",
        "source": "tic-741 probe, hand-read call site",
    },
    "pattern_miner.py": {
        "expect": "bypass", "verified_at_tic": 741,
        "why": "L867 `atomic_append_jsonl(queue_path, env)` appends mined CogPR rows to audit-logs/cprs/queue.jsonl. Its own variable is named `envelopes`, but 0/6 ratified mechanism tokens are present.",
        "source": "tic-741 probe, hand-read call site",
    },
    "queue-lifecycle-writeback.py": {
        "expect": "bypass", "verified_at_tic": 741,
        "why": "L512 `open(queue_path, 'a')` under flock appends to audit-logs/cprs/queue.jsonl; the preferred path is the atomic-append.sh SHELL sibling, which is not one of the six ratified mechanisms. 0/6 mechanism tokens.",
        "source": "tic-741 probe, hand-read call site",
    },
    "runtime-sync.py": {
        "expect": "bypass", "verified_at_tic": 741,
        "why": "L600 `atomic_append_jsonl(str(log_file), entry)` writes audit-logs/services/cgg-sync-log.jsonl (egress/router lane). 0/6 mechanism tokens.",
        "source": "tic-741 probe, hand-read call site",
    },
    "trust-progression-cycle.py": {
        "expect": "bypass", "verified_at_tic": 741,
        "why": "L140 `atomic_append_jsonl(path, record)` with path = SIGNALS_DIR/<today>.jsonl emits to the signal manifold. 0/6 mechanism tokens.",
        "source": "tic-741 probe, hand-read call site",
    },
}

# ===========================================================================
# ENGINE LAYER
# ===========================================================================

_OPAQUE = "<OPAQUE>"
_TMP = "<TMP>"
# Candidate-set cap. Truncation MUST be deterministic: an earlier cut sliced an
# unsorted set, so PYTHONHASHSEED randomization made the SAME script classify
# differently run to run — ladder-feedback-push.py resolved its
# `subprocess.run(cmd)` writer CLI on one run and not the next. A governance
# instrument whose verdict depends on hash seed is not an instrument. `_cap`
# sorts path-shaped candidates first, then lexically, then slices.
_MAX_CANDIDATES = 24
_PASSTHROUGH_ATTRS = {"resolve", "absolute", "expanduser", "parents"}


def _empty():
    return set()


def _cap(values):
    """Deterministically bound a candidate set, path-shaped candidates first."""
    return set(sorted(values, key=lambda v: ("/" not in v, v))[:_MAX_CANDIDATES])



def _cross(a, b, joiner):
    out = set()
    for x in sorted(a):
        for y in sorted(b):
            out.add(joiner(x, y))
    return _cap(out)


class Folder:
    """Statically folds a path expression to a SET of candidate strings.

    Returns a set (not a single string) so that `A or B`, `X if c else Y`, and
    a parameter bound at several call sites all fold without the engine having
    to pick a winner. Anything unfoldable yields the empty set and is reported
    as UNRESOLVED — never silently treated as safe.
    """

    def __init__(self, env: dict, argparse_defaults: dict, func_returns: dict | None = None):
        self.env = env
        self.argparse_defaults = argparse_defaults
        # fn name -> folded return value(s). Lets `target = resolve_x(...)` resolve
        # through a module-local resolver function instead of reporting unresolved.
        self.func_returns = func_returns or {}

    def fold(self, node, depth=0) -> set:
        if node is None or depth > 20:
            return _empty()
        if isinstance(node, ast.Constant):
            return {node.value} if isinstance(node.value, str) else _empty()
        if isinstance(node, ast.Name):
            if node.id == "__file__":
                return {_OPAQUE}
            bound = self.env.get(node.id)
            if bound:
                return set(bound)
            # declared audit-root alias — only when the name is otherwise
            # unbound, so a real assignment always wins.
            if node.id in ROOT_ALIASES:
                return {_AUDIT_ROOT_TOKEN}
            return _empty()
        if isinstance(node, ast.BoolOp):
            out = set()
            for v in node.values:
                out |= self.fold(v, depth + 1)
            return _cap(out)
        if isinstance(node, ast.IfExp):
            return _cap(self.fold(node.body, depth + 1) | self.fold(node.orelse, depth + 1))
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            # container -> its ELEMENT candidate set (over-approximation; the
            # path-shape filter at the binding site keeps non-path members out).
            out = set()
            for e in node.elts:
                out |= self.fold(e, depth + 1)
            return _cap(out)
        if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
            # `(f, "x") for f in DIR.glob(...)` -> the element's candidates.
            # The comprehension's own generator target is bound by _fold_scope,
            # which walks ast.comprehension nodes.
            return self.fold(node.elt, depth + 1)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
            left = self.fold(node.left, depth + 1)
            right = self.fold(node.right, depth + 1)
            if not left or not right:
                return _empty()
            if isinstance(node.op, ast.Div):
                return _cross(left, right, lambda a, b: a.rstrip("/") + "/" + b.lstrip("/"))
            return _cross(left, right, lambda a, b: a + b)
        if isinstance(node, ast.JoinedStr):
            acc = {""}
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    piece = {v.value}
                elif isinstance(v, ast.FormattedValue):
                    piece = self.fold(v.value, depth + 1) or {"*"}
                else:
                    piece = {"*"}
                acc = _cross(acc, piece, lambda a, b: a + b)
                if not acc:
                    return _empty()
            return acc
        if isinstance(node, ast.Attribute):
            # argparse namespace: args.out -> the declared default
            if isinstance(node.value, ast.Name) and node.value.id in ("args", "opts", "ns"):
                return set(self.argparse_defaults.get(node.attr, ()))
            base = self.fold(node.value, depth + 1)
            if not base:
                return _empty()
            if node.attr == "parent":
                return {b if b == _OPAQUE else b.rstrip("/").rsplit("/", 1)[0] for b in base}
            if node.attr in _PASSTHROUGH_ATTRS:
                return base
            return _empty()
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Attribute) and node.value.attr == "parents":
                return {_OPAQUE}
            return _empty()
        if isinstance(node, ast.Call):
            f = node.func
            fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
            if fname in ("Path", "str", "PosixPath", "fspath"):
                # Path() with no args is cwd; Path.home() is the user home.
                if not node.args:
                    if isinstance(f, ast.Attribute) and f.attr == "home":
                        return {"~"}
                    return _empty()
                return self.fold(node.args[0], depth + 1)
            if fname == "home":
                return {"~"}
            if fname in ("abspath", "realpath", "normpath"):
                return self.fold(node.args[0], depth + 1) if node.args else _empty()
            if fname == "dirname":
                base = self.fold(node.args[0], depth + 1) if node.args else _empty()
                return {b if b == _OPAQUE else b.rstrip("/").rsplit("/", 1)[0] for b in base}
            if fname in ("resolve", "absolute") and isinstance(f, ast.Attribute):
                return self.fold(f.value, depth + 1)
            if fname == "expanduser":
                if node.args:
                    return self.fold(node.args[0], depth + 1)
                return self.fold(f.value, depth + 1) if isinstance(f, ast.Attribute) else _empty()
            if fname == "join":
                parts = [self.fold(a, depth + 1) for a in node.args]
                if any(not p for p in parts):
                    return _empty()
                acc = parts[0]
                for p in parts[1:]:
                    acc = _cross(acc, p, lambda a, b: a.rstrip("/") + "/" + b.lstrip("/"))
                return acc
            if fname in ("mkdtemp", "mkstemp", "NamedTemporaryFile", "TemporaryDirectory", "gettempdir"):
                return {_TMP}
            # sequence passthrough: sorted(X) / list(X) / reversed(X) / tuple(X)
            if fname in ("sorted", "list", "reversed", "tuple", "set", "iter"):
                return self.fold(node.args[0], depth + 1) if node.args else _empty()
            # directory scan: base.glob(pat) / base.rglob(pat) / base.iterdir()
            if fname in ("glob", "rglob", "iterdir") and isinstance(f, ast.Attribute):
                base = self.fold(f.value, depth + 1)
                if not base:
                    return _empty()
                pats = self.fold(node.args[0], depth + 1) if node.args else {"*"}
                if not pats:
                    pats = {"*"}
                return _cross(base, pats, lambda a, b: a.rstrip("/") + "/" + b.lstrip("/"))
            if fname == "format" and isinstance(f, ast.Attribute):
                base = self.fold(f.value, depth + 1)
                return {b.split("{")[0] + "*" for b in base} if base else _empty()
            if fname in ROOT_ALIAS_FUNCS:
                return {_AUDIT_ROOT_TOKEN}
            # return-value binding for a module-local function
            if fname in self.func_returns:
                return set(self.func_returns[fname])
            return _empty()
        return _empty()


def _argparse_defaults(tree, folder_seed):
    """Map an argparse dest -> the folded default(s) of its add_argument call."""
    out = {}
    folder = Folder(folder_seed, {})
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            continue
        dest = None
        for kw in node.keywords or []:
            if kw.arg == "dest" and isinstance(kw.value, ast.Constant):
                dest = kw.value.value
        if dest is None:
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.startswith("--"):
                    dest = a.value[2:].replace("-", "_")
        if dest is None:
            continue
        for kw in node.keywords or []:
            if kw.arg == "default":
                vals = folder.fold(kw.value)
                if vals:
                    out.setdefault(dest, set()).update(vals)
    return out


def _assign_targets(node):
    if isinstance(node, ast.Assign):
        return node.targets
    if isinstance(node, ast.AnnAssign):
        return [node.target]
    return []


class ModuleAnalysis:
    """Interprocedural, single-module path analysis.

    Fixpoint over three environments:
      module constants -> function locals -> parameter bindings from call sites.

    Function parameters are the dominant unresolved shape in this corpus (a
    writer takes `queue_file` / `signal_file` / `out_path` and the caller
    supplies the literal), so a purely intra-procedural resolver reports
    `unresolved` for most real writers — which would silently become false
    negatives. Binding parameters from their in-module call sites is what makes
    the refined predicate honest rather than merely narrower.
    """

    ROUNDS = 4

    def __init__(self, tree):
        self.tree = tree
        self.funcs = {}
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs.setdefault(n.name, n)
        self.param_bindings = {}          # (fn, param) -> set[str]
        self.func_returns = {}            # fn -> set[str] folded return value(s)
        self.module_env = {}
        self.local_env = {}               # fn name -> dict
        self.argparse_defaults = {}
        self._run()

    # -- environment construction -------------------------------------------
    def _fold_scope(self, scope, base_env):
        env = dict(base_env)
        folder = Folder(env, self.argparse_defaults, self.func_returns)
        # 3 inner rounds: the deepest real chain in this corpus is
        # module-const -> .glob() -> generator-expression element -> list
        # accumulation -> tuple-unpack loop target, which needs three passes to
        # reach a fixpoint. Bounded, not unbounded: the resolver is declaredly
        # flow-INSENSITIVE (one binding per name), so more rounds buy nothing.
        for _ in range(3):
            for node in ast.walk(scope):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    val = folder.fold(node.value if isinstance(node, ast.Assign) else node.value)
                    if val:
                        for t in _assign_targets(node):
                            if isinstance(t, ast.Name):
                                env[t.id] = val
                elif isinstance(node, ast.withitem):
                    ce, ov = node.context_expr, node.optional_vars
                    if (isinstance(ce, ast.Call) and isinstance(ce.func, ast.Name)
                            and ce.func.id == "open" and isinstance(ov, ast.Name) and ce.args):
                        val = folder.fold(ce.args[0])
                        if val:
                            env[ov.id] = val
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and node.func.attr in ("append", "extend") \
                        and isinstance(node.func.value, ast.Name) and node.args:
                    # container accumulation: `scan_files.append(x)` /
                    # `.extend(genexp)` -> the container's ELEMENT candidates.
                    # Without it, `for f in scan_files` after a build-up loop
                    # reports unresolved and a real lane-walking writer would
                    # become a silent false negative.
                    val = folder.fold(node.args[0])
                    if val:
                        name = node.func.value.id
                        env[name] = _cap(set(env.get(name, set())) | val)
                elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                    # loop-iterator binding: `for f in DIR.glob("*.md")` binds f.
                    # Directory-scan iteration is the corpus's second-most-common
                    # target shape after function parameters; without it a writer
                    # that walks a lane reports `unresolved` and would become a
                    # silent false negative.
                    tgt = node.target
                    it = node.iter
                    if isinstance(tgt, ast.Name):
                        val = folder.fold(it)
                        if val:
                            env[tgt.id] = val
                    elif isinstance(tgt, (ast.Tuple, ast.List)):
                        # tuple unpacking (`for fpath, surface in scan_files`).
                        # Over-approximation: every unpacked name gets the
                        # container's candidates, FILTERED TO PATH-SHAPED ones
                        # (must contain "/"), so a co-packed label string like
                        # "auto_memory" can never masquerade as a write target.
                        val = {v for v in folder.fold(it) if "/" in v}
                        if val:
                            for el in tgt.elts:
                                if isinstance(el, ast.Name):
                                    env[el.id] = val
            folder.env = env
        return env

    def _module_scope_nodes(self):
        return [n for n in self.tree.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]

    def _run(self):
        # round 0: module constants (no function bodies)
        shell = ast.Module(body=self._module_scope_nodes(), type_ignores=[])
        self.module_env = self._fold_scope(shell, {})
        self.argparse_defaults = _argparse_defaults(self.tree, self.module_env)

        for _ in range(self.ROUNDS):
            changed = False
            # (a) function locals, seeded with module env + current param bindings
            for name, fn in self.funcs.items():
                base = dict(self.module_env)
                for p in fn.args.args + fn.args.kwonlyargs:
                    b = self.param_bindings.get((name, p.arg))
                    if b:
                        base[p.arg] = b
                # parameter defaults
                folder = Folder(self.module_env, self.argparse_defaults, self.func_returns)
                defaults = fn.args.defaults or []
                pos = fn.args.args[len(fn.args.args) - len(defaults):] if defaults else []
                for p, d in zip(pos, defaults):
                    dv = folder.fold(d)
                    if dv:
                        base.setdefault(p.arg, set()).update(dv) if isinstance(base.get(p.arg), set) else base.update({p.arg: dv})
                new_env = self._fold_scope(fn, base)
                if self.local_env.get(name) != new_env:
                    self.local_env[name] = new_env
                    changed = True
            # (a2) fold each function's return value(s) so a caller writing to
            # `target = resolve_x(...)` resolves through the module-local
            # resolver instead of reporting unresolved.
            for name, fn in self.funcs.items():
                folder = Folder(self.local_env.get(name, self.module_env),
                                self.argparse_defaults, self.func_returns)
                vals = set()
                for n in ast.walk(fn):
                    if isinstance(n, ast.Return) and n.value is not None:
                        vals |= folder.fold(n.value)
                vals = _cap(vals)
                if vals and self.func_returns.get(name) != vals:
                    self.func_returns[name] = vals
                    changed = True
            # (b) bind parameters from call sites
            for caller, env in list(self.local_env.items()) + [("<module>", self.module_env)]:
                scope = self.funcs[caller] if caller in self.funcs else shell
                folder = Folder(env, self.argparse_defaults, self.func_returns)
                for node in ast.walk(scope):
                    if not isinstance(node, ast.Call):
                        continue
                    f = node.func
                    callee = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
                    if callee not in self.funcs:
                        continue
                    fn = self.funcs[callee]
                    params = [a.arg for a in fn.args.args]
                    for i, arg in enumerate(node.args):
                        if i >= len(params):
                            break
                        vals = folder.fold(arg)
                        if vals:
                            key = (callee, params[i])
                            before = set(self.param_bindings.get(key, ()))
                            after = _cap(before | vals)
                            if after != before:
                                self.param_bindings[key] = after
                                changed = True
                    for kw in node.keywords or []:
                        if kw.arg in params:
                            vals = folder.fold(kw.value)
                            if vals:
                                key = (callee, kw.arg)
                                before = set(self.param_bindings.get(key, ()))
                                after = _cap(before | vals)
                                if after != before:
                                    self.param_bindings[key] = after
                                    changed = True
            if not changed:
                break

    # -- write-site collection ----------------------------------------------
    def _scope_of(self, node_id, owner):
        return owner.get(node_id, "<module>")

    def write_sites(self):
        owner = {}
        for name, fn in self.funcs.items():
            for n in ast.walk(fn):
                if isinstance(n, ast.Call):
                    owner[id(n)] = name
        sites = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
            if fname is None:
                continue
            scope = owner.get(id(node), "<module>")
            env = self.local_env.get(scope, self.module_env)
            folder = Folder(env, self.argparse_defaults, self.func_returns)

            verb = target_node = None
            helper_surface = None
            if fname == "open":
                mode = None
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                for kw in node.keywords or []:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
                if mode and any(m in mode for m in ("w", "a", "x", "+")):
                    verb, target_node = f"open(mode={mode!r})", (node.args[0] if node.args else None)
            elif fname in WRITE_METHODS and isinstance(f, ast.Attribute):
                verb, target_node = f".{fname}()", f.value
            elif fname in WRITE_HELPERS:
                verb = f"{fname}()"
                target_node = node.args[0] if node.args else None
                helper_surface = WRITE_HELPERS[fname]
            elif (fname == "replace" and isinstance(f, ast.Attribute)
                  and isinstance(f.value, ast.Name) and f.value.id == "os"):
                verb, target_node = "os.replace()", (node.args[1] if len(node.args) > 1 else None)
            elif (fname in ("move", "copy", "copy2", "copyfile") and isinstance(f, ast.Attribute)
                  and isinstance(f.value, ast.Name) and f.value.id == "shutil"):
                verb, target_node = f"shutil.{fname}()", (node.args[1] if len(node.args) > 1 else None)
            elif (fname == "dump" and isinstance(f, ast.Attribute)
                  and isinstance(f.value, ast.Name) and f.value.id == "json" and len(node.args) > 1):
                verb, target_node = "json.dump()", node.args[1]
            if verb is None:
                continue
            cands = sorted(folder.fold(target_node)) if target_node is not None else []
            try:
                expr = ast.unparse(target_node) if target_node is not None else None
            except Exception:
                expr = "<unparseable>"
            sites.append({
                "line": getattr(node, "lineno", -1),
                "scope": scope,
                "verb": verb,
                "target_expr": expr,
                "target_resolved": cands,
                "helper_surface_semantics": helper_surface,
            })
        seen, out = set(), []
        for s in sorted(sites, key=lambda x: (x["line"], x["verb"])):
            key = (s["line"], s["verb"], s["target_expr"])
            if key in seen:
                continue
            seen.add(key)
            out.append(s)
        return out

    def subprocess_writer_sites(self):
        """Real subprocess CALL SITES whose folded arguments name a writer CLI.

        The predicate arm this feeds is call-site-local by construction: a
        comment or a registry constant mentioning `cadence-ops.py` is NOT a
        write, and an earlier cut of this primitive got that wrong.
        """
        owner = {}
        for name, fn in self.funcs.items():
            for n in ast.walk(fn):
                if isinstance(n, ast.Call):
                    owner[id(n)] = name
        out = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
            if fname not in SUBPROCESS_CALLS:
                continue
            env = self.local_env.get(owner.get(id(node), "<module>"), self.module_env)
            folder = Folder(env, self.argparse_defaults, self.func_returns)
            cands = set()
            for a in node.args:
                cands |= folder.fold(a)
                if isinstance(a, (ast.List, ast.Tuple)):
                    for e in a.elts:
                        cands |= folder.fold(e)
            hit = sorted({t for t in SUBPROCESS_WRITER_TOKENS
                          if any(t in c for c in cands)})
            if hit:
                out.append({"line": getattr(node, "lineno", -1),
                            "verb": f"subprocess.{fname}()",
                            "writer_cli": hit,
                            "resolved_args": sorted(c for c in cands if any(t in c for t in hit))})
        return out

    def all_resolved_symbols(self):
        vals = set()
        for env in [self.module_env] + list(self.local_env.values()):
            for v in env.values():
                vals |= set(v)
        for v in self.param_bindings.values():
            vals |= set(v)
        return vals


def classify_target(resolved: str):
    """Map one resolved target path to (surface_class, detail, fp_class)."""
    norm = resolved.replace("\\", "/")
    for token, cls, fp in PRE_CAPABILITY_SURFACES:
        if token in norm:
            return (cls, token, fp)
    for prefix, kind in CAPABILITY_SURFACES.items():
        if prefix in norm:
            return ("capability_emission", kind, None)
    for token, cls, fp in NON_CAPABILITY_SURFACES:
        if token in norm:
            return (cls, token, fp)
    if "audit-logs/" in norm:
        lane = norm.split("audit-logs/", 1)[1].split("/")[0]
        return ("undeclared_audit_lane", lane, None)
    if norm.startswith("/") or norm.startswith("~"):
        return ("out_of_federation", norm, "FP-CLASS-D")
    return ("unresolved", None, None)


def classify_site(site):
    """Classify one write site over its candidate targets. Capability wins.

    Returns (surface_class, detail, fp_class, matched_target). `matched_target`
    is the SPECIFIC candidate that produced the class — never candidate[0] —
    so the reported evidence line cites the path that actually classified. The
    first cut of this primitive printed candidate[0] beside a class derived
    from a different candidate, which is an evidence-attribution defect of
    exactly the kind the audit exists to catch.
    """
    classes = []
    for cand in site["target_resolved"]:
        cls, detail, fp = classify_target(cand)
        classes.append((cls, detail, fp, cand))
    # helper semantics: dedup_signal_append / dedup_queue_append name the
    # surface in the function name itself (ratified mechanism-2 sibling pair).
    if site.get("helper_surface_semantics"):
        classes.append(("capability_emission", site["helper_surface_semantics"], None,
                        f"<helper semantics: {site['verb']}>"))
    if not classes:
        return ("unresolved", None, None, None)
    for c in classes:
        if c[0] == "capability_emission":
            return c
    non_unresolved = [c for c in classes if c[0] != "unresolved"]
    return non_unresolved[0] if non_unresolved else ("unresolved", None, None, None)


def mechanisms_present(text: str):
    hits = []
    for name, toks in SIX_MECHANISM_TOKENS.items():
        for t in toks:
            if t in text:
                hits.append({"mechanism": name, "token": t})
                break
    n6 = sum(1 for fld in MECHANISM_6_FIELDS if fld in text)
    if n6 >= MECHANISM_6_MIN_FIELDS:
        hits.append({"mechanism": "envelope_shaped_record",
                     "token": f"{n6}/{len(MECHANISM_6_FIELDS)} provenance fields"})
    return hits


def v0_legacy_flag(text: str):
    surf = [t for t in V0_SURFACE_TOKENS if t in text]
    wr = [t for t in V0_WRITE_TOKENS if t in text]
    return bool(surf) and bool(wr), surf, wr


def subprocess_writer_tokens(text: str):
    return [t for t in SUBPROCESS_WRITER_TOKENS if t in text]


def classify_script(path: Path, rel: str):
    text = path.read_text(encoding="utf-8", errors="replace")
    row = {
        "script": rel,
        "class": "test_fixture" if Path(rel).name.startswith("test_") else "production",
    }
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        row.update({"classification": "parse_error", "error": str(exc),
                    "writes_governance_state": "indeterminate", "predicate_arm": "parse_error"})
        return row

    ma = ModuleAnalysis(tree)
    sites = ma.write_sites()
    for s in sites:
        cls, detail, fp, matched = classify_site(s)
        s["surface_class"] = cls
        s["surface_detail"] = detail
        s["fp_class_answered"] = fp
        s["matched_target"] = matched

    # A script that vendors an ImportError fallback shim for a lib write helper
    # (`def atomic_append_jsonl(target, data): open(target, "a")`) has a write
    # site INSIDE the shim whose target binds to the union of every caller. The
    # classification is right, but citing the shim's internal open() as the
    # audit trail is weak evidence — the spec's contract is a per-script
    # citation a reader can check. Mark shim-internal sites and rank them last.
    for s2 in sites:
        s2["via_local_helper_shim"] = s2.get("scope") in WRITE_HELPERS
    cap_sites = sorted(
        [s for s in sites if s["surface_class"] == "capability_emission"],
        key=lambda x: (x["via_local_helper_shim"], x["line"]),
    )
    unresolved = [s for s in sites if s["surface_class"] == "unresolved"]
    subproc = ma.subprocess_writer_sites()
    mentions_only = [t for t in subprocess_writer_tokens(text)
                     if not any(t in s2["writer_cli"] for s2 in subproc)]
    mechs = mechanisms_present(text)
    symbols = ma.all_resolved_symbols()
    names_cap = any(any(p in v for p in CAPABILITY_SURFACES) for v in symbols) or any(
        t in text for t in ("audit-logs/signals", "audit-logs/agent-mailboxes", "queue.jsonl"))

    row["write_sites"] = sites
    row["write_sites_total"] = len(sites)
    row["capability_write_sites"] = cap_sites
    row["unresolved_write_sites"] = len(unresolved)
    row["target_surface_classes"] = sorted({s["surface_class"] for s in sites})
    row["fp_classes_answered"] = sorted({s["fp_class_answered"] for s in sites if s["fp_class_answered"]})
    row["mechanisms"] = mechs
    row["names_capability_surface"] = names_cap
    row["subprocess_writer_call_sites"] = subproc
    # DIAGNOSTIC ONLY — never a predicate input. Recorded so a reader can see
    # the mention/call-site gap that the v0 predicate could not see.
    row["subprocess_writer_tokens_mentioned_not_called"] = mentions_only

    # ---- ARM 1 — resolved capability call site -----------------------------
    # A write CALL SITE whose target RESOLVES into a declared capability
    # surface. Answers FP classes A/B/C/D/E/F at once: a mention is not a
    # write, and a write to a report / telemetry / doctrine / out-of-zone /
    # tmp / lockfile target is not a capability emission.
    if cap_sites:
        row["writes_governance_state"] = "yes"
        row["predicate_arm"] = "arm1_resolved_capability_call_site"
    # ---- ARM 2 — subprocess to a validated writer CLI ----------------------
    # Shelling out to inbox-envelope.py / cadence-ops.py / trigger-router.py IS
    # a governance write; the call site is a subprocess, not an open(). Answers
    # the FALSE-NEGATIVE the /review-710 amendment named on
    # ladder-feedback-push.py, which has NO local write verb at all.
    elif subproc:
        row["writes_governance_state"] = "yes"
        row["predicate_arm"] = "arm2_subprocess_to_validated_writer_cli"
    # ---- ARM 3 — indeterminate, never silently cleared ---------------------
    # A real write verb with an unresolvable target on a script that names a
    # capability surface. Not a positive and not a negative: DECLARED NEGATIVE
    # SPACE for hand adjudication. Answers the honesty gap that let v0's 30%
    # look tolerable — v0 had no way to say "I do not know".
    elif unresolved and names_cap:
        row["writes_governance_state"] = "indeterminate"
        row["predicate_arm"] = "arm3_unresolved_target_on_capability_naming_script"
    else:
        row["writes_governance_state"] = "no"
        row["predicate_arm"] = "arm0_no_resolved_capability_write"

    if row["class"] == "test_fixture":
        row["classification"] = "excluded_test_fixture"
    elif row["writes_governance_state"] == "yes":
        if mechs:
            row["classification"] = "envelope_aware_via:" + mechs[0]["mechanism"]
            row["envelope_aware_via"] = [m["mechanism"] for m in mechs]
        else:
            row["classification"] = "bypass"
            row["all_six_mechanisms_absent"] = True
    elif row["writes_governance_state"] == "indeterminate":
        row["classification"] = "indeterminate"
    else:
        row["classification"] = "not_a_governance_writer"

    v0f, v0s, v0w = v0_legacy_flag(text)
    row["v0_legacy_flagged"] = v0f
    row["v0_legacy_surface_tokens"] = v0s[:8]
    row["v0_legacy_write_tokens"] = v0w
    return row


def run_gate(rows):
    """Execute the spec's falsification gate against the labeled control set.

    TWO READINGS, BOTH PUBLISHED — neither is allowed to hide the other.

      ASSERTED  a labeled negative the classifier ASSERTS is a governance-state
                writer (bypass / envelope_aware). This is the harm the tic-690
                gate was written against: the damage there was "28 bypass
                candidates" — scripts NAMED as writers that were not.
      STRICT    the same, PLUS labeled negatives the classifier declines to
                assert on (`indeterminate`). Declining is not asserting, but a
                predicate that declines is also not doing its job, so the
                stricter number is published BESIDE the gate number rather than
                dissolved into it.

    `predicate_falsified` fires on the ASSERTED rate (the spec's own harm model)
    OR any false negative. The STRICT rate is reported so no reader has to take
    the gate's framing on trust, and every indeterminate-on-a-labeled-negative
    is named rather than counted.
    """
    by_name = {Path(r["script"]).name: r for r in rows}
    asserted_fps, declined, fns, missing = [], [], [], []
    for name, label in CONTROL_SET.items():
        r = by_name.get(name)
        if r is None:
            missing.append(name)
            continue
        actual = str(r["classification"])
        exp = label["expect"]
        if exp == "not_a_governance_writer":
            if actual == "not_a_governance_writer":
                continue
            row = {"script": name, "expected": exp, "actual": actual,
                   "label_why": label["why"], "fp_class": label.get("fp_class")}
            (declined if actual == "indeterminate" else asserted_fps).append(row)
        elif exp == "envelope_aware":
            if not actual.startswith("envelope_aware_via:"):
                fns.append({"script": name, "expected": exp, "actual": actual,
                            "label_why": label["why"]})
        elif exp == "bypass":
            if actual != "bypass":
                fns.append({"script": name, "expected": exp, "actual": actual,
                            "label_why": label["why"],
                            "note": "a labeled TRUE bypass the classifier no longer "
                                    "asserts is a false negative — a real bypass "
                                    "counted compliant"})
    labeled = len(CONTROL_SET) - len(missing)
    negatives = sum(1 for lb in CONTROL_SET.values()
                    if lb["expect"] == "not_a_governance_writer")
    fp_rate = (len(asserted_fps) / labeled) if labeled else None
    strict_rate = ((len(asserted_fps) + len(declined)) / labeled) if labeled else None
    prod = [r for r in rows if r["class"] == "production"]
    flagged = [r for r in prod if r.get("writes_governance_state") == "yes"]
    indet = [r["script"] for r in prod if r.get("writes_governance_state") == "indeterminate"]
    unlabeled_flagged = [r["script"] for r in flagged if Path(r["script"]).name not in CONTROL_SET]
    return {
        "gate_text": (">5% false-positive rate OR any false negative -> the heuristic still "
                      "requires refinement (possibly toward full per-script tactical-hydration "
                      "classification as the canonical method). Surface the falsification finding "
                      "to Mogul; do not silently widen. (civil-engineer.md, Falsification gate)"),
        "control_set_size": len(CONTROL_SET),
        "control_set_resolved": labeled,
        "control_set_labeled_negatives": negatives,
        "control_set_missing_from_scope": missing,
        "false_positives_asserted": asserted_fps,
        "false_positive_count": len(asserted_fps),
        "false_positive_rate": fp_rate,
        "false_positive_rate_pct": round(fp_rate * 100, 2) if fp_rate is not None else None,
        "declined_to_assert_on_labeled_negative": declined,
        "declined_count": len(declined),
        "false_positive_rate_strict_pct": round(strict_rate * 100, 2) if strict_rate is not None else None,
        "threshold_pct": 5.0,
        "false_negatives": fns,
        "false_negative_count": len(fns),
        "predicate_falsified": bool(fns) or (fp_rate is not None and fp_rate > 0.05),
        "flagged_production_scripts": len(flagged),
        "flagged_but_unlabeled": unlabeled_flagged,
        "indeterminate_scripts": indet,
        "measurement_scope_disclosure": (
            "The FP/FN rates are indexed to the LABELED CONTROL SET only — they are NOT a "
            "corpus-wide false-positive rate, and no corpus-wide FP rate is claimed anywhere in "
            "this report. Scripts flagged as governance-state writers that carry no hand-verified "
            "label are listed in flagged_but_unlabeled and are never counted as clean. "
            "`indeterminate` rows are declared negative space: counted in neither the numerator "
            "nor the denominator of any classification claim, and enumerated in "
            "indeterminate_scripts so the aperture is auditable rather than implied."
        ),
    }


def enumerate_scope(root: Path, scope_args):
    scopes = scope_args or ["scripts", "scripts/lib"]
    files, declared = [], []
    for s in scopes:
        d = root / s
        declared.append(str(s))
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.py")):
            if "__pycache__" in str(p):
                continue
            files.append(p)
    seen, out = set(), []
    for p in files:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return out, declared


def find_runtime_root(start: Path):
    p = start.resolve()
    for cand in [p] + list(p.parents):
        if (cand / "scripts").is_dir() and (cand / "agents").is_dir():
            return cand
    return p


def build_report(root: Path, scope_args, legacy_compare: bool):
    files, declared = enumerate_scope(root, scope_args)
    rows = [classify_script(p, str(p.relative_to(root))) for p in files]
    prod = [r for r in rows if r["class"] == "production"]
    tests = [r for r in rows if r["class"] == "test_fixture"]

    def count(pred, seq=prod):
        return sum(1 for r in seq if pred(r))

    gate = run_gate(rows)
    summary = {
        "scripts_scanned": len(rows),
        "production": len(prod),
        "excluded_test_fixtures": len(tests),
        "writes_governance_state_yes": count(lambda r: r.get("writes_governance_state") == "yes"),
        "writes_governance_state_no": count(lambda r: r.get("writes_governance_state") == "no"),
        "writes_governance_state_indeterminate": count(
            lambda r: r.get("writes_governance_state") == "indeterminate"),
        "envelope_aware": count(lambda r: str(r["classification"]).startswith("envelope_aware_via:")),
        "bypass": count(lambda r: r["classification"] == "bypass"),
        "parse_errors": count(lambda r: r["classification"] == "parse_error", rows),
        "by_predicate_arm": {},
        "by_target_surface_class": {},
    }
    for r in prod:
        arm = r.get("predicate_arm", "n/a")
        summary["by_predicate_arm"][arm] = summary["by_predicate_arm"].get(arm, 0) + 1
        for c in r.get("target_surface_classes", []):
            summary["by_target_surface_class"][c] = summary["by_target_surface_class"].get(c, 0) + 1

    report = {
        "artifact": "civil-audit",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime_root": str(root),
        "declared_scan_scope": declared,
        "scope_exclusions_declared": [
            "__pycache__ / .pytest_cache (build residue)",
            "non-.py surfaces (shell / TypeScript / Rust are out of this primitive's declared scope)",
            "scripts/media-router/** (nested vendor tree; outside the tic-690 and tic-700 scopes too)",
        ],
        "predicate_version": "v1-tic741-call-site-target-resolved",
        "or_gate_status": "RATIFIED /review 710 — reproduced unchanged by this primitive",
        "summary": summary,
        "falsification_gate": gate,
        "scripts": rows,
    }

    if legacy_compare:
        v0_flagged = [r["script"] for r in prod if r["v0_legacy_flagged"]]
        v1_flagged = [r["script"] for r in prod if r.get("writes_governance_state") == "yes"]
        cleared = sorted(set(v0_flagged) - set(v1_flagged))
        added = sorted(set(v1_flagged) - set(v0_flagged))
        cause_hist, fp_hist = {}, {}
        for name in cleared:
            r = next(x for x in prod if x["script"] == name)
            for cls in r.get("target_surface_classes", []) or ["no_write_site"]:
                cause_hist[cls] = cause_hist.get(cls, 0) + 1
            for fp in r.get("fp_classes_answered", []):
                fp_hist[fp] = fp_hist.get(fp, 0) + 1
        report["legacy_comparison"] = {
            "v0_predicate": ("RECONSTRUCTED from civil report 2026-08-09-tic-690.json finding 22 "
                             "(\"a capability-surface path string plus any write-shaped token\"). "
                             "The tic-690 run was by hand and never committed; this reconstruction "
                             "is CALIBRATED (it flags all three scripts tic 690 named as false "
                             "positives), NOT byte-recovered."),
            "v0_flagged_production": len(v0_flagged),
            "v1_flagged_production": len(v1_flagged),
            "cleared_by_refinement": cleared,
            "cleared_count": len(cleared),
            "newly_flagged_by_refinement": added,
            "cleared_target_class_histogram": cause_hist,
            "cleared_fp_class_histogram": fp_hist,
        }
    return report


def render_text(report):
    s = report["summary"]
    g = report["falsification_gate"]
    L = []
    L.append(f"civil-audit {report['predicate_version']} @ {report['generated_at']}")
    L.append(f"scope: {report['declared_scan_scope']}  root: {report['runtime_root']}")
    L.append(f"scanned {s['scripts_scanned']} ({s['production']} production, "
             f"{s['excluded_test_fixtures']} test fixtures excluded)")
    L.append(f"writes_governance_state: yes={s['writes_governance_state_yes']} "
             f"no={s['writes_governance_state_no']} "
             f"indeterminate={s['writes_governance_state_indeterminate']}")
    L.append(f"classification: envelope_aware={s['envelope_aware']} bypass={s['bypass']}")
    L.append("")
    L.append("FALSIFICATION GATE:")
    L.append(f"  control set {g['control_set_resolved']}/{g['control_set_size']} resolved")
    L.append(f"  false positives ASSERTED: {g['false_positive_count']} "
             f"({g['false_positive_rate_pct']}% vs {g['threshold_pct']}% threshold)")
    L.append(f"  declined-to-assert on a labeled negative: {g['declined_count']} "
             f"(STRICT reading: {g['false_positive_rate_strict_pct']}%)")
    L.append(f"  false negatives: {g['false_negative_count']}")
    L.append(f"  predicate_falsified: {g['predicate_falsified']}")
    for fp in g["false_positives_asserted"]:
        L.append(f"    FP {fp['script']}: expected {fp['expected']}, got {fp['actual']}")
    for d in g["declined_to_assert_on_labeled_negative"]:
        L.append(f"    DECLINED {d['script']}: expected {d['expected']}, got {d['actual']}")
    for fn in g["false_negatives"]:
        L.append(f"    FN {fn['script']}: expected {fn['expected']}, got {fn['actual']}")
    if g["flagged_but_unlabeled"]:
        L.append(f"  flagged-but-unlabeled ({len(g['flagged_but_unlabeled'])}): "
                 f"{', '.join(g['flagged_but_unlabeled'])}")
    L.append("")
    L.append("PER-SCRIPT (production writers — aggregate-only reporting is forbidden by the spec):")
    for r in sorted(report["scripts"], key=lambda x: (x.get("writes_governance_state") != "yes",
                                                     x.get("writes_governance_state") != "indeterminate",
                                                     x["script"])):
        if r["class"] != "production" or r.get("writes_governance_state") == "no":
            continue
        ev = ""
        if r.get("capability_write_sites"):
            w = r["capability_write_sites"][0]
            ev = (f"  [{w['surface_detail']} @ L{w['line']} {w['verb']} "
                  f"-> {w.get('matched_target')}]")
        elif r.get("subprocess_writer_call_sites"):
            w = r["subprocess_writer_call_sites"][0]
            ev = f"  [{','.join(w['writer_cli'])} @ L{w['line']} {w['verb']}]"
        elif r.get("writes_governance_state") == "indeterminate":
            ev = f"  [{r['unresolved_write_sites']} unresolved write site(s)]"
        L.append(f"  {r['script']:<44} {r['classification']}{ev}")
    if "legacy_comparison" in report:
        lc = report["legacy_comparison"]
        L.append("")
        L.append(f"LEGACY DELTA: v0 flagged {lc['v0_flagged_production']}, "
                 f"v1 flags {lc['v1_flagged_production']}, cleared {lc['cleared_count']}")
        L.append(f"  cleared target classes: {lc['cleared_target_class_histogram']}")
        L.append(f"  cleared FP classes:     {lc['cleared_fp_class_histogram']}")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="civil-audit — per-script envelope-pattern classifier")
    ap.add_argument("--root", default=None, help="cgg-runtime root (default: resolved from this file)")
    ap.add_argument("--scope", action="append", default=None,
                    help="declared scan scope, repeatable (default: scripts, scripts/lib)")
    ap.add_argument("--out", default=None, help="report path (default: probe-reports lane)")
    ap.add_argument("--stdout", action="store_true", help="print the report, write nothing")
    ap.add_argument("--json", action="store_true", help="emit JSON rather than the text render")
    ap.add_argument("--legacy-compare", action="store_true",
                    help="also run the reconstructed tic-690 v0 predicate and report the delta")
    ap.add_argument("--explain", default=None, help="print every write call site for one script")
    ap.add_argument("--fail-on-falsified", action="store_true",
                    help="exit 2 when the falsification gate trips")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else find_runtime_root(Path(__file__).parent)

    if args.explain:
        files, _ = enumerate_scope(root, args.scope)
        target = next((p for p in files if p.name == args.explain or str(p).endswith(args.explain)), None)
        if target is None:
            print(f"not in declared scope: {args.explain}", file=sys.stderr)
            return 1
        print(json.dumps(classify_script(target, str(target.relative_to(root))), indent=2))
        return 0

    report = build_report(root, args.scope, args.legacy_compare)
    payload = json.dumps(report, indent=2) if args.json else render_text(report)

    if args.stdout:
        print(payload)
    else:
        if args.out:
            out = Path(args.out)
        else:
            fed = root.parents[2] if len(root.parents) >= 3 else root
            out = (fed / "audit-logs" / "governance" / "harpoon-office" / "probe-reports"
                   / "civil-audit-latest.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(render_text(report))
        print(f"\nreport written: {out}")

    if args.fail_on_falsified and report["falsification_gate"]["predicate_falsified"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
