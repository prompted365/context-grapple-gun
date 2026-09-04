#!/usr/bin/env python3
"""remote-parity-readback.py — the REMOTE-PARITY READBACK close predicate (H3).

RULED: /review 769 (in-tic Architect-ratified question set) signed the HORIZON
QUIVER build set H1-H4 staged-lock; the Architect ruled "Dispatch H2 || H3 || H4
at 770". This module is H3. Staged decomposition:
audit-logs/governance/harpoon-office/staging/horizon-quiver-admission-and-dag-tic768.md
section 3 row H3 — "Remote-parity readback typed as a close predicate: formalize
the lived pushed-current + deploy-gate-GREEN-on-exact-sha reads into one typed
instrument (release-horizon set rider)" — with the section 2 row 15 rider
("Proof-qualified releases; per-horizon fault localization"). Gate evidence:
audit-logs/governance/harpoon-office/cable-receipts/H1-proof-horizon-ladder-tic769.json.

WHAT THIS FORMALIZES (two reads this federation has LIVED but never typed):
    1. PUSHED-CURRENT PER EXACT SHA — "is the remote serving the exact sha this
       tree is at?" Lived every close as an eyeballed comparison.
    2. DEPLOY-GATE GREEN PER EXACT headSha OF EACH PUSH SINCE THE LAST GREEN READ
       — lived as a per-close re-read of the CI verdict, with the SET of owed
       shas held in the seat's head between tics.
Both are READS ADDRESSED TO A REMOTE. This instrument performs them, types each
observation against the ruled proof-horizon ladder, and answers ONE predicate:
is a close claim typed at horizon C lawful for this target?

THE PREDICATE (why this is a close instrument and not a status page):
    lawful(target) == claim_within_horizon(claim_horizon, attained_horizon(target))
The seat declares the horizon it intends to CLAIM at close; this instrument
measures the horizon each declared target has ACTUALLY ATTAINED and reports the
over-claim. It reports; it does not refuse a receipt (that is H2, unbuilt).

EMISSION IS NOT RETRIEVAL — the reason `pushed` is never claimed here. The ruled
ladder types `pushed` (rank 1) as "the local emission to a remote returns
success", whose does_not_entail is "that the remote will serve those bytes to a
reader — a push is EMISSION, and emission is not retrieval." This instrument
NEVER observes an emission: it never watches a push return. Every arm it runs is
a RETRIEVAL addressed to the remote, so the highest rung it can attain for any
target is `remote_readback`, and it attains that rung DIRECTLY without ever
asserting rank 1. A target whose remote does not serve its exact sha does not
get `pushed` as a consolation rung from this instrument — it gets
`source_admitted` and a named fault.

ENGINE-CONTENT SEPARATION (inherited from H1, not re-implemented). This module
carries NO horizon ordering of its own — not a constant, not a fallback, not a
default on read failure. Every rank comes from scripts/lib/proof_horizon.py
reading contracts/proof-horizon-ladder-v1.json at call time. Every horizon NAME
this module emits is resolved through `horizon_rank` at startup, so a horizon
renamed or removed at /review makes this instrument REFUSE (typed) rather than
silently mean something else. A missing or malformed ladder is a READER FAILURE,
never a green.

READ-ONLY. This instrument writes NOTHING. It runs `git rev-parse`, `git
ls-remote`, `git rev-list`, `git cat-file -e` and `gh run list` — all reads. It
has no write surface, no state file, and no memory between runs: the
release-horizon set is derived per invocation from a declared or measured anchor.

DOES NOT SATISFY (this increment's rider, carried into every artifact it lands):
"H3 does NOT satisfy H2 (receipt-intake refusal) or H4 (detached-reproduction
twin). This instrument READS and REPORTS: it refuses no receipt at any intake
boundary, and it reproduces nothing on a detached machine. A GREEN gate verdict
read here is a remote_readback observation OF A VERDICT — it is NOT a
detached_reproduced observation performed by this instrument, and naming which
CI workflow constitutes a detached reproduction is H4's ruled job, not this
one's. NOTHING IS WIRED: no automatic caller invokes this instrument as of this
increment."

THE RELEASE-HORIZON SET, AND THE TWO ANCHORS IT CAN BE CUT FROM (do not conflate
them — they are DIFFERENT QUANTITIES that share a name):
    declared_anchor        (--since-sha S) — "each push since the LAST GREEN
        READ", where S is the sha at the caller's last green read. This is the
        quantity the ruling names. The caller supplies it because a read event
        is the caller's history, not the remote's.
    newest_green_verdict   (default) — "each push since the NEWEST GREEN VERDICT
        the remote reports". A different quantity: it is VACUOUS BY CONSTRUCTION
        whenever the newest green verdict is already on HEAD, because the set it
        cuts is then empty. Reported with `vacuous_antecedent: true` and PASS
        labelled non-discriminating — an arm that could not have failed is
        labelled, never counted as evidence.

EXIT CODES (precedence READER(2) > OVER_CLAIM(1) > PENDING(3) > LAWFUL(0) — a
pending verdict never masks an over-claim, and a reader failure never reads as
green):
    0 LAWFUL         every declared target's claim is within its attained horizon
    1 OVER_CLAIM     at least one target claims above what it attained (or a
                     claim is UNSUPPORTED because the target attained nothing)
    2 READER_FAILURE the instrument could not read (ladder unavailable, off-ladder
                     horizon, gh missing, repo unresolvable, gate-history window
                     insufficient, set bound exceeded) — LOUD, never a green
    3 PENDING        a member sha's run is queued/in_progress — no verdict yet

USAGE:
    python3 remote-parity-readback.py                       # table, exit = verdict
    python3 remote-parity-readback.py --json                # receipt object
    python3 remote-parity-readback.py --claim-horizon remote_readback
    python3 remote-parity-readback.py --since-sha <sha>     # the RULED anchor
    python3 remote-parity-readback.py --only cgg
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

INSTRUMENT = "remote-parity-readback"

EXIT_LAWFUL, EXIT_OVER_CLAIM, EXIT_READER, EXIT_PENDING = 0, 1, 2, 3

_PRECEDENCE = {EXIT_LAWFUL: 0, EXIT_PENDING: 1, EXIT_OVER_CLAIM: 2, EXIT_READER: 3}

DOES_NOT_SATISFY = (
    "H3 does NOT satisfy H2 (receipt-intake refusal) or H4 "
    "(detached-reproduction twin). This instrument READS and REPORTS: it "
    "refuses no receipt at any intake boundary, and it reproduces nothing on a "
    "detached machine. A GREEN gate verdict read here is a remote_readback "
    "observation OF A VERDICT — it is NOT a detached_reproduced observation "
    "performed by this instrument, and naming which CI workflow constitutes a "
    "detached reproduction is H4's ruled job, not this one's. NOTHING IS "
    "WIRED: no automatic caller invokes this instrument as of this increment.")

GOVERNING = (
    "audit-logs/governance/harpoon-office/staging/"
    "horizon-quiver-admission-and-dag-tic768.md section 3 row H3 (+ section 2 "
    "row 15 rider); horizon vocabulary and order from "
    "contracts/proof-horizon-ladder-v1.json via scripts/lib/proof_horizon.py")

# The horizon NAMES this instrument emits. These are NAMES ONLY — no order is
# implied here and none is stored. Every one is resolved through the ladder file
# at startup (see `resolve_horizon_vocabulary`); an off-ladder name is a typed
# READER FAILURE that routes the value to /review, never a local default.
HORIZON_LOCAL_SUBJECT = "source_admitted"
HORIZON_REMOTE_READBACK = "remote_readback"
EMITTED_HORIZONS = (HORIZON_LOCAL_SUBJECT, HORIZON_REMOTE_READBACK)

# The horizon this instrument DELIBERATELY NEVER EMITS, and why. Named so a
# reader can see the abstention rather than infer it from absence.
NEVER_EMITTED = {
    "pushed": ("this instrument observes RETRIEVAL, never EMISSION — it never "
               "watches a push return success, so it cannot occupy rank 1 on "
               "any target's behalf"),
    "detached_reproduced": ("typing a CI workflow as a detached reproduction is "
                            "H4's ruled job; a verdict READ is not a "
                            "reproduction PERFORMED"),
    "installed_verified": "install parity is runtime-sync's read, not this one's",
    "deployed": ("a CI conclusion is not a delivery surface serving the subject "
                 "under its own contract"),
    "outcome_observed": "no effect is measured here",
}


class ReaderFailure(Exception):
    """Every condition under which this instrument cannot READ exits through
    here with a typed `code`. A reader failure is LOUD and is never a green."""

    def __init__(self, message: str, code: str, detail=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = detail or {}


# ---------------------------------------------------------------------------
# H1's engine — loaded by path, fail-closed. No fallback ordering exists here.
# ---------------------------------------------------------------------------

def _scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def load_proof_horizon(module_path=None):
    """Import H1's comparator. FAIL-CLOSED: if the engine cannot be imported,
    this instrument REFUSES — it does not fall back to a local ordering, because
    a close predicate that keeps typing horizons without its ruled vocabulary has
    silently become the author of that vocabulary."""
    path = Path(module_path) if module_path else _scripts_dir() / "lib" / "proof_horizon.py"
    if not path.is_file():
        raise ReaderFailure(
            f"H1's proof-horizon engine is missing at {path}. FAIL-CLOSED: no "
            f"local horizon ordering is substituted. Governing artifact: {GOVERNING}",
            code="proof_horizon_engine_missing", detail={"path": str(path)})
    try:
        spec = importlib.util.spec_from_file_location("_h3_proof_horizon", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ReaderFailure(
            f"H1's proof-horizon engine at {path} could not be imported ({exc}). "
            f"FAIL-CLOSED: no local horizon ordering is substituted.",
            code="proof_horizon_engine_unimportable",
            detail={"path": str(path), "error": str(exc)}) from exc
    return module


def resolve_horizon_vocabulary(ph, ladder_path=None, extra_names=()):
    """Resolve EVERY horizon name this instrument uses against the ruled ladder.

    This is where engine-content separation is enforced at THIS instrument's
    boundary: the ranks are read from the contract file, and a name the ladder
    does not carry is a typed READER FAILURE that routes to /review. A ladder
    that is missing, unparseable, or schema-invalid is likewise a reader failure
    carrying H1's own refusal code — never a green, never a default order.
    """
    names = tuple(EMITTED_HORIZONS) + tuple(n for n in extra_names if n)
    ranks = {}
    try:
        ladder = ph.load_ladder(path=ladder_path)
    except Exception as exc:
        raise ReaderFailure(
            f"the ruled proof-horizon ladder could not be loaded ({exc}). "
            f"FAIL-CLOSED: this instrument types no horizon without it.",
            code=getattr(exc, "code", "ladder_unavailable"),
            detail={"error": str(exc)}) from exc
    for name in names:
        try:
            ranks[name] = ph.horizon_rank(name, path=ladder_path)
        except Exception as exc:
            raise ReaderFailure(
                f"horizon {name!r} is not on the ruled ladder ({exc}). MINTING "
                f"AUTHORITY: /review — this instrument does not coin a horizon "
                f"at its call site.",
                code=getattr(exc, "code", "off_ladder_horizon"),
                detail={"horizon": name, "error": str(exc)}) from exc
    return {"ranks": ranks, "order": list(ladder["order"]),
            "ladder_path": str(ladder["path"])}


# ---------------------------------------------------------------------------
# Command runners — the ONLY I/O seams. Tests substitute these.
# ---------------------------------------------------------------------------

def run_git(args, cwd, timeout=30):
    try:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                              text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise ReaderFailure("git binary not found", code="git_missing") from exc
    except subprocess.TimeoutExpired as exc:
        raise ReaderFailure(f"git {' '.join(args)} timed out",
                            code="git_timeout") from exc


def run_gh(args, cwd, gh_bin=None, timeout=90):
    gh = gh_bin or os.environ.get("GH_BIN") or "gh"
    if shutil.which(gh) is None and not Path(gh).is_file():
        raise ReaderFailure(
            f"gh binary not found ({gh}) — the gate is UNREAD, not green",
            code="gh_missing", detail={"gh": gh})
    try:
        return subprocess.run([gh, *args], cwd=str(cwd), capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ReaderFailure(f"gh {' '.join(args)} timed out",
                            code="gh_timeout") from exc


# ---------------------------------------------------------------------------
# The declared RELEASE-HORIZON SET of targets
# ---------------------------------------------------------------------------

def resolve_zone_root(explicit=None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("ZONE_ROOT")
    if env:
        return Path(env).resolve()
    here = _scripts_dir()
    for d in (here, *here.parents):
        if (d / ".ticzone").exists() or (d / ".federation-root").exists():
            return d.resolve()
    cwd = Path.cwd().resolve()
    for d in (cwd, *cwd.parents):
        if (d / ".ticzone").exists() or (d / ".federation-root").exists():
            return d.resolve()
    raise ReaderFailure(
        "no zone root could be resolved (no .ticzone / .federation-root marker "
        "found walking up from this script or from cwd); pass --zone-root",
        code="zone_root_unresolved")


def default_targets(zone_root: Path):
    """The DECLARED release-horizon set.

    HONEST LIMIT, stated at the declaration site: this set is declared by THIS
    INSTRUMENT, not ruled at /review. Unlike the horizon ladder — whose values
    are content amendable by a data edit under a verdict — extending this set is
    an edit to this file. Whether the release-horizon SET should itself become
    ruled content is handed up as an owed motion by this increment's receipt.

    `gate` is a DECLARATION, never an inference: `expected` means the target is
    expected to carry a push-triggered CI surface and its ABSENCE is a reader
    failure; `declared_absent` means the target carries no CI gate by design and
    the gate arm is NOT PERFORMED (declared negative space — never a silent
    pass, never green-by-absence).
    """
    return [
        {"name": "canonical", "repo_root": str(zone_root), "remote": "origin",
         "ref": "refs/heads/main", "gate": "declared_absent",
         "gate_basis": "the canonical federation repo carries no .github/workflows; "
                       "its close proof is canonical-side instruments, not CI"},
        {"name": "cgg",
         "repo_root": str(zone_root / "canonical_developer" / "context-grapple-gun"),
         "remote": "origin", "ref": "refs/heads/main", "gate": "expected",
         "gate_basis": "the CGG repo carries .github/workflows and its "
                       "push-to-main workflows are the lived deploy gate"},
    ]


def parse_target_spec(spec: str):
    out = {}
    for part in spec.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise ReaderFailure(f"malformed --target field {part!r} (expected key=value)",
                                code="target_spec_malformed")
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    if "name" not in out or "root" not in out:
        raise ReaderFailure(f"--target {spec!r} needs at least name= and root=",
                            code="target_spec_incomplete")
    gate = out.get("gate", "declared_absent")
    if gate not in ("expected", "declared_absent"):
        raise ReaderFailure(
            f"--target {out['name']!r} declares gate={gate!r}; declare "
            f"'expected' or 'declared_absent' — a gate is never inferred",
            code="target_gate_undeclared")
    return {"name": out["name"], "repo_root": out["root"],
            "remote": out.get("remote", "origin"),
            "ref": out.get("ref", "refs/heads/main"), "gate": gate,
            "gate_basis": out.get("basis", "declared on the command line")}


# ---------------------------------------------------------------------------
# ARM 1 — the local subject (source_admitted)
# ---------------------------------------------------------------------------

def arm_local_subject(target, git=run_git):
    """Read the target's own subject back from its tree. Authoring is not
    observation; this arm is the read-back."""
    arm = {"arm": "local_subject", "horizon": HORIZON_LOCAL_SUBJECT,
           "performed": True, "passed": False, "vacuous_antecedent": False,
           "evidence": {}, "faults": []}
    root = Path(target["repo_root"])
    if not (root / ".git").exists():
        arm["faults"].append({
            "code": "not_a_git_repo", "target": target["name"],
            "repo_root": str(root),
            "message": f"target {target['name']!r}: {root} carries no .git — no subject to read"})
        arm["reader_failure"] = True
        return arm
    r = git(["rev-parse", "HEAD"], root)
    if r.returncode != 0 or not r.stdout.strip():
        arm["faults"].append({
            "code": "head_unreadable", "target": target["name"],
            "repo_root": str(root),
            "message": f"target {target['name']!r}: git rev-parse HEAD failed "
                       f"({(r.stderr or '').strip()[:200]})"})
        arm["reader_failure"] = True
        return arm
    head = r.stdout.strip()
    arm["evidence"]["head_sha"] = head
    b = git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    branch = b.stdout.strip() if b.returncode == 0 else None
    arm["evidence"]["branch"] = branch
    declared_branch = target["ref"].rsplit("/", 1)[-1]
    arm["evidence"]["declared_branch"] = declared_branch
    if branch and branch != declared_branch:
        # The sole-writer lane is the declared ref. Measuring remote parity from
        # a different resident branch reads a reference that is not the lane the
        # parity claim is about.
        arm["faults"].append({
            "code": "branch_off_declared_ref", "target": target["name"],
            "repo_root": str(root), "observed_branch": branch,
            "declared_ref": target["ref"],
            "message": f"target {target['name']!r}: resident branch {branch!r} is "
                       f"not the declared ref {target['ref']!r} — parity measured "
                       f"here would not be parity of the declared lane"})
        return arm
    arm["passed"] = True
    return arm


# ---------------------------------------------------------------------------
# ARM 2 — ref parity: does the REMOTE serve the exact sha? (remote_readback)
# ---------------------------------------------------------------------------

def arm_ref_parity(target, head_sha, git=run_git):
    arm = {"arm": "ref_parity", "horizon": HORIZON_REMOTE_READBACK,
           "performed": True, "passed": False, "vacuous_antecedent": False,
           "evidence": {}, "faults": []}
    root = Path(target["repo_root"])
    u = git(["remote", "get-url", target["remote"]], root)
    remote_url = u.stdout.strip() if u.returncode == 0 else None
    arm["evidence"]["remote"] = target["remote"]
    arm["evidence"]["remote_url"] = remote_url
    arm["evidence"]["ref"] = target["ref"]
    arm["evidence"]["expected_sha"] = head_sha
    if remote_url is None:
        arm["faults"].append({
            "code": "remote_undefined", "target": target["name"],
            "remote": target["remote"],
            "message": f"target {target['name']!r}: remote {target['remote']!r} is not defined"})
        arm["reader_failure"] = True
        return arm
    r = git(["ls-remote", target["remote"], target["ref"]], root, timeout=60)
    if r.returncode != 0:
        arm["faults"].append({
            "code": "ls_remote_failed", "target": target["name"],
            "remote": target["remote"], "remote_url": remote_url,
            "ref": target["ref"],
            "message": f"target {target['name']!r}: git ls-remote {target['remote']} "
                       f"{target['ref']} failed ({(r.stderr or '').strip()[:200]}) — "
                       f"the remote is UNREAD, not parity-clean"})
        arm["reader_failure"] = True
        return arm
    served = None
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == target["ref"]:
            served = parts[0]
            break
    arm["evidence"]["served_sha"] = served
    if served is None:
        arm["faults"].append({
            "code": "ref_absent_on_remote", "target": target["name"],
            "remote": target["remote"], "remote_url": remote_url,
            "ref": target["ref"], "expected_sha": head_sha,
            "message": f"target {target['name']!r}: remote {remote_url} serves no "
                       f"{target['ref']} — the declared subject is not retrievable"})
        return arm
    if served != head_sha:
        arm["faults"].append({
            "code": "remote_serves_different_sha", "target": target["name"],
            "remote": target["remote"], "remote_url": remote_url,
            "ref": target["ref"], "expected_sha": head_sha, "served_sha": served,
            "message": f"target {target['name']!r}: remote {remote_url} serves "
                       f"{served[:12]} at {target['ref']} but this tree is at "
                       f"{head_sha[:12]} — NOT pushed-current; emission is not retrieval"})
        return arm
    arm["passed"] = True
    return arm


# ---------------------------------------------------------------------------
# ARM 3 — the gate over the RELEASE-HORIZON SET (remote_readback)
# ---------------------------------------------------------------------------

_GH_FIELDS = "databaseId,conclusion,status,headSha,createdAt,event"


def read_workflow_runs(target, workflow, limit, gh=run_gh, gh_bin=None):
    root = Path(target["repo_root"])
    r = gh(["run", "list", "--workflow", workflow, "--limit", str(limit),
            "--json", _GH_FIELDS], root, gh_bin=gh_bin)
    if r.returncode != 0:
        raise ReaderFailure(
            f"target {target['name']!r}: gh run list --workflow {workflow} failed "
            f"({(r.stderr or r.stdout or '').strip()[:200]}) — the gate is UNREAD, "
            f"not green",
            code="gh_run_list_failed",
            detail={"target": target["name"], "workflow": workflow})
    try:
        return json.loads(r.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise ReaderFailure(
            f"target {target['name']!r}: gh returned non-JSON for {workflow} ({exc})",
            code="gh_non_json",
            detail={"target": target["name"], "workflow": workflow}) from exc


def _conclusion_of(run):
    """A run that has not completed has NO conclusion — it is PENDING. Never
    read an in-flight run as red and never as green (the tic-748 scar)."""
    if run.get("status") != "completed":
        return "PENDING"
    return run.get("conclusion") or "UNKNOWN"


def release_horizon_set(target, head_sha, anchor_sha, max_set, git=run_git):
    """The exact shas owed a verdict: each push on the declared ref after the
    anchor, up to and including HEAD.

    FAIL-CLOSED at both edges: an anchor the local repo does not carry is a
    reader failure (the set cannot be derived and is NEVER guessed), and a set
    larger than the declared bound is a reader failure (NEVER silently
    truncated — a truncated set turns unread shas into implicit greens).
    """
    root = Path(target["repo_root"])
    probe = git(["cat-file", "-e", f"{anchor_sha}^{{commit}}"], root)
    if probe.returncode != 0:
        raise ReaderFailure(
            f"target {target['name']!r}: anchor sha {anchor_sha[:12]} is not a "
            f"commit this repo carries — the release-horizon set cannot be "
            f"derived and is not guessed",
            code="anchor_sha_unknown_locally",
            detail={"target": target["name"], "anchor_sha": anchor_sha})
    r = git(["rev-list", "--first-parent", f"{anchor_sha}..{head_sha}"], root)
    if r.returncode != 0:
        raise ReaderFailure(
            f"target {target['name']!r}: git rev-list {anchor_sha[:12]}..{head_sha[:12]} "
            f"failed ({(r.stderr or '').strip()[:200]})",
            code="rev_list_failed", detail={"target": target["name"]})
    members = [s for s in (r.stdout or "").split() if s]
    if len(members) > max_set:
        raise ReaderFailure(
            f"target {target['name']!r}: the release-horizon set holds "
            f"{len(members)} shas, above the declared bound {max_set} — refusing "
            f"to truncate, because a truncated set turns unread shas into "
            f"implicit greens. Raise --max-set deliberately or move the anchor.",
            code="release_horizon_set_exceeds_bound",
            detail={"target": target["name"], "size": len(members), "bound": max_set})
    return members


def arm_gate_set(target, head_sha, args, deploy_mod, gh=run_gh, git=run_git):
    """Read the deploy gate for EVERY sha in the release-horizon set, per
    push-triggered workflow. This is the arm the section 2 row 15 rider governs:
    every fault names WHICH remote, WHICH sha, and WHICH workflow."""
    arm = {"arm": "gate_set", "horizon": HORIZON_REMOTE_READBACK,
           "performed": True, "passed": False, "vacuous_antecedent": False,
           "evidence": {}, "faults": [], "pending": False}
    root = Path(target["repo_root"])
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        raise ReaderFailure(
            f"target {target['name']!r} declares gate=expected but carries no "
            f"{wf_dir} — a declared gate that is absent is a reader failure, "
            f"never a green",
            code="declared_gate_surface_absent",
            detail={"target": target["name"], "path": str(wf_dir)})
    workflows = deploy_mod.list_workflows(root)
    if not workflows:
        raise ReaderFailure(
            f"target {target['name']!r}: {wf_dir} carries no *.yml — nothing to read",
            code="declared_gate_surface_empty", detail={"target": target["name"]})

    considered, excluded = [], []
    for wf in workflows:
        trig = deploy_mod.push_main_triggered(root, wf)
        if trig is False:
            excluded.append({"workflow": wf, "reason": "not_push_triggered",
                             "basis": "the workflow does not run on push-to-main "
                                      "(PR / dispatch / build-branch trigger) — "
                                      "its verdict is not owed on a push"})
            continue
        if trig is None:
            # Unparseable trigger: NOT silently excluded. An unclassifiable
            # workflow is read as if it were owed, because excluding it would be
            # a green granted by a parse failure.
            considered.append({"workflow": wf, "trigger": "unparseable_included"})
            continue
        considered.append({"workflow": wf, "trigger": "push_main"})
    arm["evidence"]["workflows_considered"] = considered
    arm["evidence"]["workflows_excluded"] = excluded

    if not considered:
        raise ReaderFailure(
            f"target {target['name']!r} declares gate=expected but NO workflow on "
            f"its gate surface runs on push-to-main — there is no gate to read",
            code="declared_gate_has_no_push_workflow",
            detail={"target": target["name"],
                    "excluded": [e["workflow"] for e in excluded]})

    per_workflow = []
    any_member = False
    for entry in considered:
        wf = entry["workflow"]
        runs = read_workflow_runs(target, wf, args.gh_limit, gh=gh, gh_bin=args.gh_bin)
        window_saturated = len(runs) >= args.gh_limit
        by_sha = {}
        for run in runs:
            by_sha.setdefault(run.get("headSha"), []).append(run)

        if args.since_sha:
            anchor, anchor_kind = args.since_sha, "declared_anchor"
        else:
            green = [r for r in runs if _conclusion_of(r) == "success"]
            if not green:
                arm["faults"].append({
                    "code": "no_green_verdict_in_window", "target": target["name"],
                    "workflow": wf, "window": args.gh_limit,
                    "message": f"target {target['name']!r} workflow {wf}: no success "
                               f"verdict in the newest {args.gh_limit} runs — the "
                               f"anchor cannot be measured and absence is not green"})
                per_workflow.append({"workflow": wf, "anchor": None,
                                     "anchor_kind": "newest_green_verdict",
                                     "members": None, "passed": False})
                continue
            anchor, anchor_kind = green[0].get("headSha"), "newest_green_verdict"

        try:
            members = release_horizon_set(target, head_sha, anchor, args.max_set, git=git)
        except ReaderFailure:
            raise
        wf_row = {"workflow": wf, "anchor": anchor, "anchor_kind": anchor_kind,
                  "members": members, "member_count": len(members),
                  "vacuous_antecedent": len(members) == 0, "passed": True,
                  "window_saturated": window_saturated}
        if members:
            any_member = True
        for sha in members:
            sha_runs = by_sha.get(sha) or []
            if not sha_runs:
                code = ("gate_window_insufficient" if window_saturated
                        else "no_run_for_sha")
                if window_saturated:
                    raise ReaderFailure(
                        f"target {target['name']!r} workflow {wf}: sha {sha[:12]} has "
                        f"no run inside the newest {args.gh_limit} fetched runs AND "
                        f"the window is saturated — absence-of-run cannot be "
                        f"distinguished from absence-of-fetch. Raise --gh-limit.",
                        code=code,
                        detail={"target": target["name"], "workflow": wf, "sha": sha,
                                "window": args.gh_limit})
                wf_row["passed"] = False
                arm["faults"].append({
                    "code": code, "target": target["name"], "workflow": wf,
                    "sha": sha, "remote": target["remote"],
                    "message": f"target {target['name']!r} workflow {wf}: push {sha[:12]} "
                               f"carries NO run — a push with no verdict is not green"})
                continue
            newest = sha_runs[0]
            concl = _conclusion_of(newest)
            if concl == "PENDING":
                wf_row["passed"] = False
                arm["pending"] = True
                arm["faults"].append({
                    "code": "gate_pending_for_sha", "target": target["name"],
                    "workflow": wf, "sha": sha, "run_id": newest.get("databaseId"),
                    "status": newest.get("status"),
                    "message": f"target {target['name']!r} workflow {wf}: run "
                               f"{newest.get('databaseId')} on {sha[:12]} is "
                               f"{newest.get('status')} — no verdict yet; re-read before close"})
                continue
            if concl != "success":
                wf_row["passed"] = False
                arm["faults"].append({
                    "code": "gate_red_for_sha", "target": target["name"],
                    "workflow": wf, "sha": sha, "conclusion": concl,
                    "run_id": newest.get("databaseId"),
                    "created_at": newest.get("createdAt"),
                    "message": f"target {target['name']!r} workflow {wf}: run "
                               f"{newest.get('databaseId')} on {sha[:12]} concluded "
                               f"{concl} — the gate is RED on that exact sha"})
        per_workflow.append(wf_row)

    arm["evidence"]["per_workflow"] = per_workflow
    arm["vacuous_antecedent"] = (not any_member) and all(
        row.get("passed") for row in per_workflow)
    arm["passed"] = all(row.get("passed") for row in per_workflow) and not arm["faults"]
    if arm["vacuous_antecedent"]:
        arm["vacuity_note"] = (
            "EVALUATED-BUT-NON-DISCRIMINATING: the release-horizon set is EMPTY "
            "for every considered workflow, so this arm could not have failed. "
            "Its PASS is not evidence that the gate is green on anything — it is "
            "evidence that nothing was owed a verdict under the anchor used. "
            "Cut a non-vacuous set with --since-sha to make this arm able to fail.")
    return arm


# ---------------------------------------------------------------------------
# Attained horizon + the close predicate
# ---------------------------------------------------------------------------

def attained_horizon(arms, vocab):
    """The highest-ranked horizon whose performed arms ALL passed, walking the
    ladder in the FILE's order, stopping at the first rung with a failed arm.

    Returns None when NO rung was attained. None is ABSENCE, never rank 0 — the
    ruled contract states that a claim with no horizon asserted is not rank 0 and
    must not be silently defaulted to any rung; the same discipline applies to a
    measurement that attained nothing.

    THE RUNG PREDICATE IS CONJUNCTIVE, AND THE DEMOTION IS NOT A DIAGNOSIS. When
    two arms sit at the same rung on DIFFERENT SUBJECTS (ref_parity reads the
    ref->sha mapping; gate_set reads the verdicts keyed to each sha), a rung is
    attained only if BOTH passed. So a target whose remote genuinely serves its
    exact sha, but whose gate is RED on one member sha, is reported as attaining
    `source_admitted` — NOT because the remote failed to serve the sha, but
    because this instrument will not let a close claim at that rung stand while
    one of its own arms there is red. The reported rung is a floor, never a
    diagnosis: read `faults` for WHAT failed. Every fault names the remote, the
    sha, and the workflow (the section 2 row 15 rider).
    """
    by_horizon = {}
    for arm in arms:
        if arm.get("performed"):
            by_horizon.setdefault(arm["horizon"], []).append(arm)
    attained = None
    for name in vocab["order"]:
        rung = by_horizon.get(name)
        if not rung:
            continue  # skipping a rung is lawful; it simply is not attained here
        if all(a.get("passed") for a in rung):
            attained = name
        else:
            break
    return attained


def evaluate_target(target, args, ph, vocab, deploy_mod, gh=run_gh, git=run_git):
    row = {"target": target["name"], "repo_root": target["repo_root"],
           "remote": target["remote"], "ref": target["ref"],
           "gate": target["gate"], "gate_basis": target.get("gate_basis"),
           "arms": [], "attained_horizon": None, "claim_horizon": args.claim_horizon,
           "claim_lawful": None, "verdict": None, "faults": [],
           "not_performed": []}

    a1 = arm_local_subject(target, git=git)
    row["arms"].append(a1)
    if a1.get("reader_failure"):
        row["faults"].extend(a1["faults"])
        row["verdict"] = "READER_FAILURE"
        return row, EXIT_READER
    head = a1["evidence"].get("head_sha")
    row["head_sha"] = head

    if a1["passed"]:
        a2 = arm_ref_parity(target, head, git=git)
        row["arms"].append(a2)
        if a2.get("reader_failure"):
            row["faults"].extend(a2["faults"])
            row["verdict"] = "READER_FAILURE"
            return row, EXIT_READER
    else:
        row["not_performed"].append({
            "arm": "ref_parity",
            "reason": "the local subject arm did not pass — there is no verified "
                      "subject to address the remote with"})

    if target["gate"] == "expected":
        if all(a.get("passed") for a in row["arms"]):
            a3 = arm_gate_set(target, head, args, deploy_mod, gh=gh, git=git)
            row["arms"].append(a3)
        else:
            row["not_performed"].append({
                "arm": "gate_set",
                "reason": "an earlier arm failed — the gate is not read against an "
                          "unverified subject"})
    else:
        row["not_performed"].append({
            "arm": "gate_set",
            "reason": f"gate declared_absent for this target: {target.get('gate_basis')}. "
                      f"DECLARED NEGATIVE SPACE — not performed, and NOT a pass."})

    for arm in row["arms"]:
        row["faults"].extend(arm.get("faults", []))

    row["attained_horizon"] = attained_horizon(row["arms"], vocab)
    row["attained_rank"] = (vocab["ranks"].get(row["attained_horizon"])
                            if row["attained_horizon"] else None)
    row["vacuous_arms"] = [a["arm"] for a in row["arms"] if a.get("vacuous_antecedent")]

    if row["attained_horizon"] is None:
        row["claim_lawful"] = False
        row["claim_verdict_note"] = (
            f"UNSUPPORTED: this target attained NO horizon. Absence asserts "
            f"nothing and is NOT rank 0 — the claim {args.claim_horizon!r} rests "
            f"on no performed observation.")
        row["verdict"] = "OVER_CLAIM"
        code = EXIT_OVER_CLAIM
    else:
        try:
            lawful = ph.claim_within_horizon(args.claim_horizon,
                                             row["attained_horizon"],
                                             path=args.ladder_path)
        except Exception as exc:
            raise ReaderFailure(
                f"target {target['name']!r}: the close predicate could not be "
                f"evaluated ({exc})",
                code=getattr(exc, "code", "off_ladder_horizon"),
                detail={"target": target["name"]}) from exc
        row["claim_lawful"] = lawful
        if lawful:
            row["verdict"] = "LAWFUL"
            code = EXIT_LAWFUL
        else:
            row["claim_verdict_note"] = (
                f"OVER-CLAIM: claim {args.claim_horizon!r} (rank "
                f"{vocab['ranks'].get(args.claim_horizon)}) is above the attained "
                f"horizon {row['attained_horizon']!r} (rank {row['attained_rank']}) "
                f"— the observation stopped earlier than the claim.")
            row["verdict"] = "OVER_CLAIM"
            code = EXIT_OVER_CLAIM

    if any(a.get("pending") for a in row["arms"]) and code == EXIT_LAWFUL:
        row["verdict"] = "PENDING"
        code = EXIT_PENDING
    elif any(a.get("pending") for a in row["arms"]) and code != EXIT_LAWFUL:
        row["pending_present"] = True
    return row, code


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(
        description="Remote-parity readback typed as a close predicate (H3).")
    ap.add_argument("--zone-root", default=None)
    ap.add_argument("--target", action="append", default=None,
                    help="name=..,root=..[,remote=..][,ref=..][,gate=expected|declared_absent]")
    ap.add_argument("--only", default=None, help="evaluate one declared target by name")
    ap.add_argument("--claim-horizon", default=HORIZON_REMOTE_READBACK,
                    help="the horizon the caller intends to CLAIM at close")
    ap.add_argument("--since-sha", default=None,
                    help="the RULED anchor: the sha at the caller's last GREEN READ")
    ap.add_argument("--gh-limit", type=int, default=60)
    ap.add_argument("--max-set", type=int, default=50)
    ap.add_argument("--gh-bin", default=None)
    ap.add_argument("--ladder-path", default=None)
    ap.add_argument("--engine-path", default=None)
    ap.add_argument("--json", action="store_true")
    return ap


def main(argv=None, gh=run_gh, git=run_git):
    args = build_parser().parse_args(argv)
    receipt = {
        "instrument": INSTRUMENT,
        "read_at_utc": datetime.now(timezone.utc).isoformat(),
        "governing": GOVERNING,
        "does_not_satisfy": DOES_NOT_SATISFY,
        "read_only": True,
        "wired": False,
        "claim_horizon": args.claim_horizon,
        "anchor_kind": "declared_anchor" if args.since_sha else "newest_green_verdict",
        "anchor_sha": args.since_sha,
        "horizons_never_emitted": NEVER_EMITTED,
        "ladder_path": None, "ladder_order": None,
        "targets": [], "faults": [], "verdict": None, "exit_code": None,
    }
    try:
        ph = load_proof_horizon(args.engine_path)
        vocab = resolve_horizon_vocabulary(ph, ladder_path=args.ladder_path,
                                           extra_names=(args.claim_horizon,))
        receipt["ladder_path"] = vocab["ladder_path"]
        receipt["ladder_order"] = vocab["order"]
        receipt["claim_horizon_rank"] = vocab["ranks"].get(args.claim_horizon)

        deploy_mod = None
        zone = resolve_zone_root(args.zone_root)
        receipt["zone_root"] = str(zone)
        if args.target:
            targets = [parse_target_spec(t) for t in args.target]
        else:
            targets = default_targets(zone)
            receipt["target_set_origin"] = (
                "DECLARED BY THIS INSTRUMENT, not ruled at /review — extending it "
                "is an edit to this file (handed up as an owed motion)")
        if args.only:
            targets = [t for t in targets if t["name"] == args.only]
            if not targets:
                raise ReaderFailure(f"--only {args.only!r} matches no declared target",
                                    code="target_not_declared")
        if any(t["gate"] == "expected" for t in targets):
            deploy_mod = _load_deploy_gate_module()

        code = EXIT_LAWFUL
        for target in targets:
            row, tcode = evaluate_target(target, args, ph, vocab, deploy_mod,
                                         gh=gh, git=git)
            receipt["targets"].append(row)
            receipt["faults"].extend(row["faults"])
            if _PRECEDENCE[tcode] > _PRECEDENCE[code]:
                code = tcode
    except ReaderFailure as rf:
        receipt["faults"].append({"code": rf.code, "message": rf.message,
                                  **(rf.detail or {})})
        receipt["verdict"], receipt["exit_code"] = "READER_FAILURE", EXIT_READER
        _emit(receipt, args.json)
        return EXIT_READER

    receipt["verdict"] = {EXIT_LAWFUL: "LAWFUL", EXIT_OVER_CLAIM: "OVER_CLAIM",
                          EXIT_READER: "READER_FAILURE",
                          EXIT_PENDING: "PENDING"}[code]
    receipt["exit_code"] = code
    _emit(receipt, args.json)
    return code


def _load_deploy_gate_module():
    path = _scripts_dir() / "deploy-gate-read.py"
    if not path.is_file():
        raise ReaderFailure(
            f"the lived deploy-gate reader is missing at {path} — this "
            f"instrument formalizes that read and does not reimplement its "
            f"workflow-trigger classification",
            code="deploy_gate_reader_missing", detail={"path": str(path)})
    spec = importlib.util.spec_from_file_location("_h3_deploy_gate_read", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ReaderFailure(
            f"the lived deploy-gate reader at {path} could not be imported ({exc})",
            code="deploy_gate_reader_unimportable", detail={"path": str(path)}) from exc
    return module


def _emit(receipt, as_json):
    if as_json:
        print(json.dumps(receipt, indent=2))
        return
    print(f"{INSTRUMENT} · claim={receipt['claim_horizon']} · "
          f"anchor={receipt['anchor_kind']}"
          f"{(' ' + receipt['anchor_sha'][:12]) if receipt.get('anchor_sha') else ''} · "
          f"{receipt['read_at_utc']}")
    if receipt.get("ladder_path"):
        print(f"  ladder: {receipt['ladder_path']}")
        print(f"  order:  {' < '.join(receipt['ladder_order'] or [])}")
    for row in receipt.get("targets", []):
        print(f"  {row['target']:<12} attained={str(row.get('attained_horizon')):<18} "
              f"claim_lawful={str(row.get('claim_lawful')):<6} {row.get('verdict')}")
        for arm in row.get("arms", []):
            mark = "PASS" if arm.get("passed") else "FAIL"
            vac = "  (VACUOUS — could not have failed)" if arm.get("vacuous_antecedent") else ""
            print(f"      · {arm['arm']:<14} @{arm['horizon']:<18} {mark}{vac}")
        for np in row.get("not_performed", []):
            print(f"      · {np['arm']:<14} NOT PERFORMED — {np['reason']}")
        if row.get("claim_verdict_note"):
            print(f"      ! {row['claim_verdict_note']}")
    for f in receipt.get("faults", []):
        print(f"  ! [{f.get('code')}] {f.get('message')}")
    print(f"VERDICT: {receipt['verdict']} (exit {receipt['exit_code']})")


if __name__ == "__main__":
    sys.exit(main())
