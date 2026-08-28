#!/usr/bin/env python3
"""deploy-gate-read.py — read every CGG GitHub workflow's LAST conclusion, from inside the CGG repo.

WHY (bk-cgg-deploy-gate-close-instrument-reader; tic 747 lineup head, built tic 748):
    The Distribution-contract workflow was RED on 83 consecutive pushes (2026-08-05 5e22c08
    -> 2026-08-28 ce35387) while runtime-sync read 0 drift every tic. runtime-sync measures
    the INSTALLED copy against canonical; it never reads the PUBLISHED package's gate. A CI
    verdict written on GitHub and read by no instrument the seat runs is a mounted bear
    (constitution-ledger#can-it-eat-dataflow-liveness-predicate, Case 2 of
    #structural-transform-implies-closed-consumer-set-obligation). The Architect found it,
    not the seat. This is the reader — the seat's close instruments now read the gate.

CONTRACT (a READ instrument — it never writes):
    - runs `gh run list` with cwd = the CGG repo root. `gh` resolves the repository from the
      working directory (the tic-747 lesson: run from canonical and it reads the wrong repo).
    - enumerates .github/workflows/*.yml|*.yaml — the consumer set is the workflow directory,
      never a hardcoded list (a workflow added later is read the next close, not discovered
      by-failure).
    - per workflow: the last run's conclusion / status / headSha / createdAt / databaseId.
    - compares each last run's headSha to the repo HEAD: a green on an OLD sha is not a verdict
      on the current publish — flagged `stale` (and RED under --require-head).
    - exit codes: 0 = every workflow read is success-or-no-runs (no-runs is flagged, never
      silent); 1 = at least one workflow's last conclusion is not success (or stale under
      --require-head); 2 = the reader itself could not read (gh missing / not authenticated /
      no workflow dir / not a git repo) — a reader failure is LOUD, never a green.

USAGE:
    python3 deploy-gate-read.py                    # table on stdout, exit code = verdict
    python3 deploy-gate-read.py --json             # receipt object for the close block
    python3 deploy-gate-read.py --require-head     # a last run not on HEAD counts as RED
    python3 deploy-gate-read.py --repo-root PATH   # explicit CGG repo root
    (env CGG_REPO_ROOT and GH_BIN are honored; GH_BIN defaults to `gh` on PATH)

REPO ROOT RESOLUTION (first hit wins; fail-closed at exit 2 if none carries .github/workflows):
    --repo-root -> $CGG_REPO_ROOT -> script-relative (scripts/ -> cgg-runtime/ -> repo)
    -> <zone_root>/canonical_developer/context-grapple-gun (the installed copy's fallback)
"""
from __future__ import annotations

import argparse
import json
import re
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FIELDS = "databaseId,conclusion,status,headSha,createdAt,event,displayTitle"
EXIT_GREEN, EXIT_RED, EXIT_READER = 0, 1, 2


def _candidate_roots(explicit: str | None) -> list[Path]:
    out: list[Path] = []
    if explicit:
        out.append(Path(explicit))
    env = os.environ.get("CGG_REPO_ROOT")
    if env:
        out.append(Path(env))
    here = Path(__file__).resolve()
    out.append(here.parents[2] if len(here.parents) > 2 else here.parent)
    try:
        sys.path.insert(0, str(here.parent))
        from zone_root import find_zone_root  # type: ignore
        zr = find_zone_root()
        if zr:
            out.append(Path(zr) / "canonical_developer" / "context-grapple-gun")
    except Exception:
        pass
    return out


def resolve_repo_root(explicit: str | None) -> Path | None:
    for c in _candidate_roots(explicit):
        if (c / ".github" / "workflows").is_dir():
            return c.resolve()
    return None


def list_workflows(root: Path) -> list[str]:
    wd = root / ".github" / "workflows"
    return sorted(p.name for p in wd.iterdir() if p.suffix in (".yml", ".yaml") and p.is_file())


def push_main_triggered(root: Path, workflow: str) -> bool | None:
    """Does this workflow run on `push` to main? None = could not parse. A stale-green on a
    PR-only / dispatch-only / build-branch workflow is BY CONSTRUCTION, not a missed verdict —
    the reader classifies the trigger so STALE-GREEN reds only what should have run on HEAD."""
    try:
        text = (root / ".github" / "workflows" / workflow).read_text()
    except Exception:
        return None
    try:
        import yaml  # type: ignore
        doc = yaml.safe_load(text) or {}
        on = doc.get("on", doc.get(True, {}))  # PyYAML parses bare `on:` as the boolean True
        if isinstance(on, str):
            return on == "push"
        if isinstance(on, list):
            return "push" in on
        if isinstance(on, dict) and "push" in on:
            push = on.get("push") or {}
            branches = push.get("branches") if isinstance(push, dict) else None
            if not branches:
                return True
            return any(b in ("main", "master", "*", "**") for b in branches)
        return False
    except Exception:
        m = re.search(r"^on:\s*\n((?:[ \t]+.*\n|\n)+)", text, re.M)
        block = m.group(1) if m else text
        if not re.search(r"^\s+push\s*:", block, re.M):
            return False
        pm = re.search(r"^\s+push\s*:\s*\n((?:[ \t]+.*\n)+)", block, re.M)
        pb = pm.group(1) if pm else ""
        if "branches" not in pb:
            return True
        return bool(re.search(r"\bmain\b|\bmaster\b", pb))


def git_head(root: Path) -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


def read_last_run(gh: str, root: Path, workflow: str) -> dict:
    """One `gh run list --workflow <file> --limit 1 --json ...` with cwd=root."""
    row: dict = {"workflow": workflow, "read": False, "conclusion": None, "status": None,
                 "head_sha": None, "created_at": None, "run_id": None, "event": None, "error": None}
    try:
        r = subprocess.run([gh, "run", "list", "--workflow", workflow, "--limit", "1", "--json", FIELDS],
                           cwd=root, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        row["error"] = f"gh binary not found: {gh}"
        return row
    except subprocess.TimeoutExpired:
        row["error"] = "gh run list timed out (60s)"
        return row
    if r.returncode != 0:
        row["error"] = (r.stderr or r.stdout).strip()[:300] or f"gh exit {r.returncode}"
        return row
    try:
        runs = json.loads(r.stdout or "[]")
    except json.JSONDecodeError as e:
        row["error"] = f"gh returned non-JSON: {e}"
        return row
    row["read"] = True
    if not runs:
        row["conclusion"] = "NO_RUNS"
        return row
    run = runs[0]
    row.update({"conclusion": run.get("conclusion") or run.get("status"), "status": run.get("status"),
                "head_sha": run.get("headSha"), "created_at": run.get("createdAt"),
                "run_id": run.get("databaseId"), "event": run.get("event"),
                "title": (run.get("displayTitle") or "")[:80]})
    return row


def classify(rows: list[dict], head: str | None, require_head: bool) -> tuple[int, list[str]]:
    findings: list[str] = []
    code = EXIT_GREEN
    for row in rows:
        wf = row["workflow"]
        if not row["read"]:
            findings.append(f"READER FAILURE {wf}: {row['error']}")
            code = max(code, EXIT_READER)
            continue
        row["on_head"] = (head is not None and row["head_sha"] is not None and row["head_sha"] == head)
        row["stale"] = bool(head and row["head_sha"] and not row["on_head"])
        if row["conclusion"] == "NO_RUNS":
            findings.append(f"NO RUNS {wf}: the workflow has never produced a verdict (flagged, not green)")
            continue
        if row["conclusion"] != "success":
            findings.append(f"RED {wf}: last conclusion={row['conclusion']} run={row['run_id']} sha={(row['head_sha'] or '')[:7]} at {row['created_at']}")
            code = max(code, EXIT_RED)
            continue
        if row["stale"]:
            if row.get("push_main") is False:
                findings.append(f"NOT-PUSH-TRIGGERED {wf}: last success on {(row['head_sha'] or '')[:7]} (HEAD {(head or '')[:7]}) is by construction — the workflow does not run on push-to-main (PR / dispatch / build-branch trigger)")
                continue
            msg = f"STALE-GREEN {wf}: last success is on {(row['head_sha'] or '')[:7]}, HEAD is {(head or '')[:7]} — the workflow runs on push-to-main and has no verdict on the current publish"
            findings.append(msg)
            if require_head:
                code = max(code, EXIT_RED)
    return code, findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read every CGG workflow's last conclusion from inside the CGG repo.")
    ap.add_argument("--repo-root", default=None)
    ap.add_argument("--json", action="store_true", help="emit a receipt object instead of a table")
    ap.add_argument("--require-head", action="store_true", help="a last run not on HEAD counts as RED")
    args = ap.parse_args(argv)

    gh = os.environ.get("GH_BIN") or "gh"
    receipt: dict = {"instrument": "deploy-gate-read", "read_at_utc": datetime.now(timezone.utc).isoformat(),
                     "repo_root": None, "head": None, "gh": gh, "workflows": [], "findings": [], "verdict": None, "exit_code": None}

    root = resolve_repo_root(args.repo_root)
    if root is None:
        receipt["findings"] = ["READER FAILURE: no candidate repo root carries .github/workflows (pass --repo-root or set CGG_REPO_ROOT)"]
        receipt["verdict"], receipt["exit_code"] = "READER_FAILURE", EXIT_READER
        _emit(receipt, args.json)
        return EXIT_READER
    receipt["repo_root"] = str(root)
    if shutil.which(gh) is None and not Path(gh).is_file():
        receipt["findings"] = [f"READER FAILURE: gh binary not found ({gh}) — the gate is unread, not green"]
        receipt["verdict"], receipt["exit_code"] = "READER_FAILURE", EXIT_READER
        _emit(receipt, args.json)
        return EXIT_READER

    head = git_head(root)
    receipt["head"] = head
    workflows = list_workflows(root)
    if not workflows:
        receipt["findings"] = ["READER FAILURE: .github/workflows carries no *.yml — nothing to read"]
        receipt["verdict"], receipt["exit_code"] = "READER_FAILURE", EXIT_READER
        _emit(receipt, args.json)
        return EXIT_READER

    rows = [read_last_run(gh, root, wf) for wf in workflows]
    for row in rows:
        row["push_main"] = push_main_triggered(root, row["workflow"])
    code, findings = classify(rows, head, args.require_head)
    receipt["workflows"] = rows
    receipt["findings"] = findings
    receipt["verdict"] = {EXIT_GREEN: "GREEN", EXIT_RED: "RED", EXIT_READER: "READER_FAILURE"}[code]
    receipt["exit_code"] = code
    _emit(receipt, args.json)
    return code


def _emit(receipt: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(receipt, indent=2))
        return
    print(f"deploy-gate-read · repo {receipt.get('repo_root')} · HEAD {(receipt.get('head') or '?')[:7]} · {receipt['read_at_utc']}")
    for row in receipt.get("workflows", []):
        flag = "" if row.get("read") else "  ← READER FAILURE"
        if row.get("read") and row.get("stale"):
            flag = "  ← stale (push-main workflow, no verdict on HEAD)" if row.get("push_main") is not False else "  · not push-triggered (by construction)"
        print(f"  {row['workflow']:<42} {str(row.get('conclusion')):<10} {str(row.get('head_sha') or '')[:7]:<8} {str(row.get('created_at') or ''):<22} {str(row.get('run_id') or ''):<12}{flag}")
    for f in receipt.get("findings", []):
        print(f"  ! {f}")
    print(f"VERDICT: {receipt['verdict']} (exit {receipt['exit_code']})")


if __name__ == "__main__":
    sys.exit(main())
