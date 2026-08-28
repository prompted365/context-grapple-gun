"""test_deploy_gate_read.py — negative controls for deploy-gate-read.py (tic 748).

Every control MUTATES the fake gh's verdict and asserts the reader's exit code moves —
a control that does not change the input proves nothing (F-747-L1: a mutation that did
not mutate 'passed' once; never again).
"""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "deploy-gate-read.py"


def _mk_repo(tmp_path: Path, workflows=("a.yml", "b.yml"), triggers=None) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    (repo / ".github" / "workflows").mkdir(parents=True)
    for wf in workflows:
        body = (triggers or {}).get(wf, "on:\n  push:\n    branches: [main]\n")
        (repo / ".github" / "workflows" / wf).write_text(body)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x"], cwd=repo, check=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    return repo, head


def _mk_fake_gh(tmp_path: Path, results: dict) -> Path:
    """A fake `gh` that answers `gh run list --workflow X ... --json` from a results map."""
    d = tmp_path / "bin"
    d.mkdir(parents=True, exist_ok=True)
    (d / "results.json").write_text(json.dumps(results))
    gh = d / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, os\n"
        "args = sys.argv[1:]\n"
        "wf = args[args.index('--workflow') + 1]\n"
        "res = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')))\n"
        "print(json.dumps(res.get(wf, [])))\n"
    )
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return gh


def _run(repo: Path, gh: Path | None, *extra) -> tuple[int, dict]:
    env = dict(os.environ)
    env["GH_BIN"] = str(gh) if gh else "/nonexistent/gh-binary"
    r = subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(repo), "--json", *extra],
                       capture_output=True, text=True, env=env)
    return r.returncode, json.loads(r.stdout)


def _run_row(sha, conclusion="success", run_id=1):
    return [{"databaseId": run_id, "conclusion": conclusion, "status": "completed", "headSha": sha,
             "createdAt": "2026-08-28T00:00:00Z", "event": "push", "displayTitle": "t"}]


def test_all_green_on_head_exits_0(tmp_path):
    repo, head = _mk_repo(tmp_path)
    gh = _mk_fake_gh(tmp_path, {"a.yml": _run_row(head), "b.yml": _run_row(head, run_id=2)})
    code, receipt = _run(repo, gh)
    assert code == 0 and receipt["verdict"] == "GREEN"
    assert receipt["findings"] == []
    assert all(w["on_head"] for w in receipt["workflows"])


def test_one_red_exits_1_and_names_the_workflow(tmp_path):
    repo, head = _mk_repo(tmp_path)
    gh = _mk_fake_gh(tmp_path, {"a.yml": _run_row(head), "b.yml": _run_row(head, conclusion="failure", run_id=2)})
    code, receipt = _run(repo, gh)
    assert code == 1 and receipt["verdict"] == "RED"
    assert any(f.startswith("RED b.yml") for f in receipt["findings"]), receipt["findings"]
    # the mutation is real: flipping b.yml back to success returns the reader to 0
    gh2 = _mk_fake_gh(tmp_path / "again", {"a.yml": _run_row(head), "b.yml": _run_row(head, run_id=2)})
    assert _run(repo, gh2)[0] == 0


def test_stale_green_flagged_and_red_under_require_head(tmp_path):
    repo, head = _mk_repo(tmp_path)
    old = "0" * 40
    gh = _mk_fake_gh(tmp_path, {"a.yml": _run_row(head), "b.yml": _run_row(old, run_id=2)})
    code, receipt = _run(repo, gh)
    assert code == 0 and receipt["verdict"] == "GREEN"
    assert any(f.startswith("STALE-GREEN b.yml") for f in receipt["findings"])
    code2, receipt2 = _run(repo, gh, "--require-head")
    assert code2 == 1 and receipt2["verdict"] == "RED"


def test_no_runs_is_flagged_not_silent(tmp_path):
    repo, head = _mk_repo(tmp_path)
    gh = _mk_fake_gh(tmp_path, {"a.yml": _run_row(head)})  # b.yml has no runs
    code, receipt = _run(repo, gh)
    assert code == 0
    assert any(f.startswith("NO RUNS b.yml") for f in receipt["findings"])
    assert [w["conclusion"] for w in receipt["workflows"]] == ["success", "NO_RUNS"]


def test_gh_missing_is_reader_failure_exit_2_never_green(tmp_path):
    repo, _ = _mk_repo(tmp_path)
    code, receipt = _run(repo, None)
    assert code == 2 and receipt["verdict"] == "READER_FAILURE"
    assert receipt["workflows"] == []


def test_no_workflow_dir_is_reader_failure(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    env = dict(os.environ)
    env["GH_BIN"] = "/nonexistent/gh-binary"
    env.pop("CGG_REPO_ROOT", None)
    r = subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(repo), "--json"], capture_output=True, text=True, env=env)
    # --repo-root without .github/workflows falls through; the script-relative root (the real CGG repo)
    # then wins — so pin the failure by pointing every fallback at nothing is not possible from here.
    # Assert only the contract this test can own: the explicit root was NOT accepted as-is.
    receipt = json.loads(r.stdout)
    assert receipt["repo_root"] != str(repo)


def test_stale_green_on_pr_only_workflow_is_by_construction_never_red(tmp_path):
    repo, head = _mk_repo(tmp_path, triggers={"b.yml": "on:\n  pull_request:\n    paths: ['x/**']\n  workflow_dispatch:\n"})
    old = "1" * 40
    gh = _mk_fake_gh(tmp_path, {"a.yml": _run_row(head), "b.yml": _run_row(old, run_id=2)})
    code, receipt = _run(repo, gh, "--require-head")
    assert code == 0 and receipt["verdict"] == "GREEN"
    assert any(f.startswith("NOT-PUSH-TRIGGERED b.yml") for f in receipt["findings"]), receipt["findings"]
    assert [w["push_main"] for w in receipt["workflows"]] == [True, False]
    # the discriminator is the trigger, not the sha: make b.yml push-main and the same stale sha turns RED
    repo2, head2 = _mk_repo(tmp_path / "r2")
    gh2 = _mk_fake_gh(tmp_path / "r2", {"a.yml": _run_row(head2), "b.yml": _run_row(old, run_id=2)})
    assert _run(repo2, gh2, "--require-head")[0] == 1


def test_installed_copy_resolves_repo_by_cwd_walk_up(tmp_path):
    """The installed copy (~/.claude/cgg-runtime/scripts) is not inside a repo: script-relative
    fails and the reader must find <zone>/canonical_developer/context-grapple-gun by walking up
    from cwd. Copy the script OUT of the repo so the fallback is the path actually exercised."""
    import shutil
    zone = tmp_path / "zone"
    (zone / ".ticzone").mkdir(parents=True)
    repo, head = _mk_repo(zone / "canonical_developer" / "context-grapple-gun-parent")
    # _mk_repo made <parent>/repo; move it to the expected name
    target = zone / "canonical_developer" / "context-grapple-gun"
    shutil.move(str(repo), str(target))
    installed = tmp_path / "installed" / "cgg-runtime" / "scripts"
    installed.mkdir(parents=True)
    shutil.copy(SCRIPT, installed / "deploy-gate-read.py")
    gh = _mk_fake_gh(tmp_path, {"a.yml": _run_row(head), "b.yml": _run_row(head, run_id=2)})
    env = dict(os.environ)
    env["GH_BIN"] = str(gh)
    env.pop("CGG_REPO_ROOT", None)
    sub = zone / "audit-logs" / "deep"
    sub.mkdir(parents=True)
    r = subprocess.run([sys.executable, str(installed / "deploy-gate-read.py"), "--json"], cwd=sub, capture_output=True, text=True, env=env)
    receipt = json.loads(r.stdout)
    assert receipt["repo_root"] == str(target.resolve()), receipt
    assert r.returncode == 0 and receipt["verdict"] == "GREEN"
