#!/usr/bin/env python3
"""Selftests for the tic-808 ruled increment — the post-commit sync hook stops installing
the working tree off a substring.

Rulings (the spec; this file executes THEM, not a paraphrase):
  audit-logs/governance/receipts/2026-09-19-tic804-post-commit-sync-hook-ruling.md
    (2092 bytes, 11 lines, sha256 head-16 828e9d80c5eab099) — /review 804 round 3,
    Architect-ratified, recommended option verbatim "Rule it; witness first, then build".
  audit-logs/governance/receipts/2026-09-19-tic807-sync-hook-live-witness-satisfies-witness-first-cure-released-ruling.md
    (2625 bytes, 14 lines, sha256 head-16 6b4e973ee5c12231) — /review 807 round 2,
    Architect-ratified, recommended option verbatim "Accept; release cure for 808".
  The witness both rest on:
    audit-logs/governance/sync-hook-witnesses/post-commit-sync-hook-live-witness-tic807.txt
    (3943 bytes, 24 lines, sha256 head-16 82a6a278c163676f).

THE RULED INCREMENT (four properties, one arm each below): the hook resolves WHICH repo the
commit landed in; syncs only when THAT commit touched the runtime; syncs from the COMMITTED
tree, never the working tree; and recognises the `-C` form — plus, per the 807 ruling, "a
fixture arm that reproduces the substring-only trigger as its negative control".

DOES-NOT-SATISFY RIDER (travels verbatim): this ruling does NOT identify the command text that carried the substring, does NOT audit past syncs for unverified installs, does NOT change what the sync manifest covers, and does NOT touch any other hook's commit matching.

THE HOOK UNDER TEST is located through ONE overridable seam — the environment variable
CGG_POST_COMMIT_SYNC_HOOK — defaulting to the source-tree location relative to THIS file.
The same test bytes therefore run against a scratch build now and against the landed hook
later, and against a deliberately-reverted variant for the revert controls.

INSTRUMENT UNIT: one INSTALLED file's sha16, read before and after the same hook run. Every
count below is published with its members (the dict of installed path -> sha16). Every arm is
a distinct pytest NODE ID; there is no subTest here, so no arm can report a passing parent
while a child fails.

THE REAL ZONE AND THE REAL HOME ARE NEVER TEST SUBJECTS. Every hook execution runs with
(i)   HOME pointed at a fixture HOME — runtime-sync.py resolves every install target through
      os.path.expanduser("~"), so this is what keeps the real ~/.claude untouched;
(ii)  CLAUDE_PROJECT_DIR and CLAUDE_PLUGIN_ROOT pinned to fixture paths, and a .ticzone in the
      fixture zone so the hook's walk terminates inside the fixture;
(iii) the process CWD OUTSIDE the canonical tree (the fixture root), so no resolver CWD
      fallback can reach the real zone — the failure that put a fixture row in the real seals
      journal at tic 804 (row 172, still false there);
(iv)  TMPDIR inside the fixture, so the hook's committed-tree snapshot is created and removed
      inside the fixture too;
(v)   GIT_CONFIG_GLOBAL / GIT_CONFIG_SYSTEM pointed at an empty file, so no user or machine
      git config (templates, hooks, aliases) can reach these fixture repos.
The sync log is written by runtime-sync.py through audit_logs_path(zone_root) — zone_root is
the --project-dir the hook passes — so the fixtures' sync rows land in the FIXTURE zone. The
arms assert that directly rather than prosing it.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

TESTS_HOOKS_DIR = Path(__file__).resolve().parent
CGG_RUNTIME = Path(__file__).resolve().parents[2]
SOURCE_HOOK = CGG_RUNTIME / "hooks" / "post-commit-sync.sh"
REAL_SCRIPTS = CGG_RUNTIME / "scripts"
REAL_MANIFEST = CGG_RUNTIME / "sync-manifest.json"

# THE ONE OVERRIDABLE SEAM.
HOOK_ENV_VAR = "CGG_POST_COMMIT_SYNC_HOOK"


def hook_under_test() -> Path:
    return Path(os.environ.get(HOOK_ENV_VAR) or SOURCE_HOOK)


RIDER = (
    "this ruling does NOT identify the command text that carried the substring, does NOT "
    "audit past syncs for unverified installs, does NOT change what the sync manifest "
    "covers, and does NOT touch any other hook's commit matching."
)

# The two-word phrase the defect matched on, assembled so this file never carries it as a
# contiguous literal: the live hook matches Bash command TEXT, and a test file is read by
# graders and greps long before it is run.
_VERB = "commit"
ADJACENT_PHRASE = "git" + " " + _VERB

STALE = 90000  # seconds: how far back a fixture back-dates a real-but-not-fresh commit


def sha16(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


class Fixture:
    """Two fixture repos, a fixture HOME, a fixture zone, a fixture TMPDIR."""

    def __init__(self, root: Path):
        self.root = root
        self.home = root / "home"
        self.zone = root / "zone"
        self.cgg = root / "cgg"        # the repo that owns the runtime
        self.other = root / "other"    # the OTHER repo
        self.tmp = root / "tmp"
        self.gitconf = root / "gitconfig-empty"

        self.tmp.mkdir(parents=True)
        self.gitconf.write_text("", encoding="utf-8")

        # ---- fixture zone: .ticzone + the audit-logs tree runtime-sync writes into ----
        (self.zone / "audit-logs" / "services").mkdir(parents=True)
        (self.zone / "audit-logs" / "signals").mkdir(parents=True)
        (self.zone / ".ticzone").write_text(
            json.dumps({"name": "fixture-synchook-808", "tz": "UTC", "include": ["."],
                        "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"]}),
            encoding="utf-8")

        # ---- fixture HOME: the install target AND the tool location ----
        # The tooling (runtime-sync.py and its imports) is reached through the hook's
        # global-install fallback, which keeps the fixture PLUGIN ROOT holding nothing but
        # the tracked runtime surfaces — so the discovered surface set is exactly the
        # fixture's own, in both the cured and uncured arms.
        (self.home / ".claude" / "hooks").mkdir(parents=True)
        (self.home / ".claude" / "cgg-runtime").mkdir(parents=True)
        os.symlink(REAL_SCRIPTS, self.home / ".claude" / "cgg-runtime" / "scripts")
        shutil.copy2(REAL_MANIFEST, self.home / ".claude" / "cgg-runtime" / "sync-manifest.json")

        # ---- the two fixture repos ----
        self._init_repo(self.cgg)
        self._init_repo(self.other)

        (self.cgg / "cgg-runtime" / "hooks").mkdir(parents=True)
        self.surface = self.cgg / "cgg-runtime" / "hooks" / "demo-hook.sh"
        self.surface2 = self.cgg / "cgg-runtime" / "hooks" / "demo-second.sh"
        self.nonruntime = self.cgg / "notes.txt"
        self.fx_manifest = self.cgg / "cgg-runtime" / "sync-manifest.json"

        self.surface.write_text("#!/usr/bin/env bash\necho BASE\n", encoding="utf-8")
        self.surface2.write_text("#!/usr/bin/env bash\necho SECOND-BASE\n", encoding="utf-8")
        self.nonruntime.write_text("base\n", encoding="utf-8")
        shutil.copy2(REAL_MANIFEST, self.fx_manifest)
        self.base_sha = self.commit(self.cgg, "fixture base", stale=True)

        (self.other / "notes.txt").write_text("base\n", encoding="utf-8")
        self.commit(self.other, "other base", stale=True)

        # installed targets (manifest: hooks -> .claude/hooks, type SCRIPT_CODE)
        self.installed = self.home / ".claude" / "hooks" / "demo-hook.sh"
        self.installed2 = self.home / ".claude" / "hooks" / "demo-second.sh"
        self.installed_manifest = self.home / ".claude" / "cgg-runtime" / "sync-manifest.json"

        self.prime_install()

    # -- repo helpers ---------------------------------------------------------
    def _git_env(self, stale: bool = False) -> dict:
        e = dict(os.environ)
        e.update({
            "GIT_CONFIG_GLOBAL": str(self.gitconf),
            "GIT_CONFIG_SYSTEM": str(self.gitconf),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "fixture",
            "GIT_AUTHOR_EMAIL": "fixture@fixture.invalid",
            "GIT_COMMITTER_NAME": "fixture",
            "GIT_COMMITTER_EMAIL": "fixture@fixture.invalid",
        })
        if stale:
            when = "%d +0000" % (int(time.time()) - STALE)
            e["GIT_AUTHOR_DATE"] = when
            e["GIT_COMMITTER_DATE"] = when
        return e

    def git(self, repo: Path, *args: str, stale: bool = False, cwd: Path | None = None):
        return subprocess.run(["git", "-C", str(repo), *args], cwd=str(cwd or self.root),
                              env=self._git_env(stale), capture_output=True, text=True,
                              timeout=60, check=False)

    def _init_repo(self, path: Path) -> None:
        """Every fixture repo opens with an EMPTY genesis commit, so no later fixture commit
        is ever a ROOT commit. This is an instrument requirement, not decoration:
        `git diff-tree --no-commit-id --name-only -r <root-commit>` prints NOTHING (a root
        commit has no parent to diff against), so a fixture whose base commit is the root
        commit would silently decline at the runtime-touch gate and its arm would pass for a
        reason it never meant to test. The blindness itself is a property of the hook, named
        as a finding, NOT cured here — the fixture merely stops hiding behind it."""
        path.mkdir(parents=True, exist_ok=True)
        self.git(path, "init", "-q", "-b", "main")
        self.git(path, _VERB, "-q", "--allow-empty", "-m", "genesis", stale=True)

    def commit(self, repo: Path, message: str, stale: bool = False,
               cwd: Path | None = None) -> str:
        """A REAL commit. Back-dated when stale=True, so the fixture can stage a commit that
        genuinely landed but does NOT belong to the tool call that just finished."""
        self.git(repo, "add", "-A", stale=stale, cwd=cwd)
        self.git(repo, _VERB, "-q", "-m", message, stale=stale, cwd=cwd)
        return self.git(repo, "rev-parse", "HEAD").stdout.strip()

    # -- install helpers ------------------------------------------------------
    def prime_install(self) -> None:
        """Baseline: installed == committed for every surface, so an arm's member set is the
        set of files THAT ARM moved, never the backlog of a never-installed tree."""
        shutil.copy2(self.surface, self.installed)
        shutil.copy2(self.surface2, self.installed2)

    def stage_uninstalled_stale_runtime_commit(self) -> str:
        """Leave a REAL, already-landed, NOT-fresh runtime commit whose bytes were never
        installed. Without this, a wrongly-fired sync would be a no-op (installed already
        equals committed) and every no-install arm would pass for the wrong reason — the
        arm would prove nothing. With it, ANY spurious sync moves a named member, whichever
        tree the sync reads from."""
        self.surface2.write_text("#!/usr/bin/env bash\necho SECOND-COMMITTED-STALE\n",
                                 encoding="utf-8")
        return self.commit(self.cgg, "a stale runtime commit, never installed", stale=True)

    def installed_shas(self) -> dict:
        return {
            str(self.installed): sha16(self.installed),
            str(self.installed2): sha16(self.installed2),
            str(self.installed_manifest): sha16(self.installed_manifest),
        }

    def sync_rows(self) -> list:
        log = self.zone / "audit-logs" / "services" / "cgg-sync-log.jsonl"
        if not log.is_file():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
                if line.strip()]

    # -- hook execution -------------------------------------------------------
    def env(self, debug: bool = True, window: str | None = None) -> dict:
        e = dict(os.environ)
        e.update({
            "HOME": str(self.home),
            "CLAUDE_PROJECT_DIR": str(self.zone),
            "CLAUDE_PLUGIN_ROOT": str(self.cgg),
            "TMPDIR": str(self.tmp),
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": str(self.gitconf),
            "GIT_CONFIG_SYSTEM": str(self.gitconf),
        })
        if debug:
            e["CGG_SYNC_HOOK_DEBUG"] = "1"
        else:
            e.pop("CGG_SYNC_HOOK_DEBUG", None)
        if window is not None:
            e["CGG_SYNC_COMMIT_WINDOW_SECONDS"] = window
        else:
            e.pop("CGG_SYNC_COMMIT_WINDOW_SECONDS", None)
        return e

    def payload(self, command: str) -> str:
        return json.dumps({
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "agent_id": "fixture-agent-808",
            "agent_type": "fixture-seat",
        })

    def run(self, command: str, hook: Path | None = None, debug: bool = True,
            window: str | None = None) -> subprocess.CompletedProcess:
        # CWD is the fixture ROOT — outside the canonical tree and outside BOTH fixture repos.
        return subprocess.run(
            ["bash", str(hook or hook_under_test())],
            input=self.payload(command), text=True, capture_output=True,
            cwd=str(self.root), env=self.env(debug=debug, window=window), timeout=180,
        )


@pytest.fixture()
def fx(tmp_path):
    return Fixture(tmp_path)


def _moved(before: dict, after: dict) -> dict:
    return {k: (before[k], after[k]) for k in before if before[k] != after[k]}


# ---------------------------------------------------------------------------
# THE NEGATIVE CONTROL THE 807 RULING NAMES — the substring-only trigger.
# ---------------------------------------------------------------------------

def test_substring_only_command_with_a_dirty_runtime_installs_nothing(fx):
    """THE ARM THE RULING NAMES. A command whose TEXT merely contains the two-word phrase,
    performing NO commit, against a repo whose last commit DID touch the runtime and a DIRTY
    runtime working tree. That is the tic-807 witness's shape, reproduced in a fixture.

    The cured hook must install nothing: no commit landed inside this tool call.
    """
    fx.stage_uninstalled_stale_runtime_commit()
    fx.surface.write_text("#!/usr/bin/env bash\necho UNCOMMITTED-DIRTY\n", encoding="utf-8")
    before = fx.installed_shas()
    r = fx.run("echo 'about to %s the tranche' # no commit is performed" % ADJACENT_PHRASE)
    after = fx.installed_shas()
    assert r.returncode == 0, r.stderr
    assert "[post-commit-sync:debug]" in r.stdout, (
        "positive control DARK — the hook did not run to its decision point")
    assert _moved(before, after) == {}, "a substring-only command installed bytes"
    assert fx.sync_rows() == [], "a substring-only command produced a sync row"


def test_substring_only_declines_for_the_reason_the_cure_names(fx):
    """Not merely silent: the hook must decline because no COMMIT landed, not because it
    crashed, not because it could not find a root. A silent zero is not a proof."""
    fx.surface.write_text("#!/usr/bin/env bash\necho UNCOMMITTED-DIRTY\n", encoding="utf-8")
    r = fx.run("echo %s" % ADJACENT_PHRASE)
    assert r.returncode == 0, r.stderr
    assert ("outside the" in r.stdout and "window" in r.stdout) or "no ref moved" in r.stdout, (
        "expected an explicit stale-commit decline; got: %r" % r.stdout)


# ---------------------------------------------------------------------------
# PROPERTY 1 — resolves WHICH repo the commit landed in.
# ---------------------------------------------------------------------------

def test_commit_in_the_other_repo_does_not_install_the_dirty_runtime(fx):
    """A real commit, in the OTHER repo, that does not touch the runtime — with the runtime
    working tree dirty. The old hook read the CGG repo's own HEAD whichever repo was
    committed to, so it synced. The cure must not."""
    fx.stage_uninstalled_stale_runtime_commit()
    fx.surface.write_text("#!/usr/bin/env bash\necho UNCOMMITTED-DIRTY\n", encoding="utf-8")
    (fx.other / "notes.txt").write_text("changed in the other repo\n", encoding="utf-8")
    fx.commit(fx.other, "a real commit, in the other repo")
    before = fx.installed_shas()
    r = fx.run("%s -m 'a real commit, in the other repo'" % ADJACENT_PHRASE)
    after = fx.installed_shas()
    assert r.returncode == 0, r.stderr
    assert "[post-commit-sync:debug]" in r.stdout, "positive control DARK"
    assert _moved(before, after) == {}, "a commit in the OTHER repo installed runtime bytes"
    assert fx.sync_rows() == []


# ---------------------------------------------------------------------------
# PROPERTY 2 — syncs only when THAT commit touched the runtime.
# ---------------------------------------------------------------------------

def test_commit_touching_only_non_runtime_paths_installs_nothing(fx):
    """A fresh, real commit in the repo of record that touches NOTHING under the runtime."""
    fx.stage_uninstalled_stale_runtime_commit()
    fx.nonruntime.write_text("changed, but not runtime\n", encoding="utf-8")
    fx.commit(fx.cgg, "non-runtime only")
    before = fx.installed_shas()
    r = fx.run("%s -m 'non-runtime only'" % ADJACENT_PHRASE)
    after = fx.installed_shas()
    assert r.returncode == 0, r.stderr
    assert "did not touch" in r.stdout, (
        "expected the explicit did-not-touch-the-runtime decline; got %r" % r.stdout)
    assert _moved(before, after) == {}
    assert fx.sync_rows() == []


# ---------------------------------------------------------------------------
# PROPERTY 3 — syncs from the COMMITTED tree, never the working tree.
# ---------------------------------------------------------------------------

def test_install_carries_committed_bytes_and_not_the_uncommitted_ones(fx):
    """The centre of the cure. A real runtime commit lands; MORE uncommitted edits are then
    on disk. The installed bytes must be the COMMITTED ones — both shas are named."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    sha = fx.commit(fx.cgg, "a real runtime commit")
    committed_sha16 = sha16(fx.surface)
    fx.surface.write_text("#!/usr/bin/env bash\necho UNCOMMITTED-AFTER\n", encoding="utf-8")
    uncommitted_sha16 = sha16(fx.surface)
    assert committed_sha16 != uncommitted_sha16

    before = fx.installed_shas()
    r = fx.run("%s -m 'a real runtime commit'" % ADJACENT_PHRASE)
    after = fx.installed_shas()

    assert r.returncode == 0, r.stderr
    assert sha16(fx.installed) == committed_sha16, (
        "installed bytes are not the committed bytes: installed=%s committed=%s uncommitted=%s"
        % (sha16(fx.installed), committed_sha16, uncommitted_sha16))
    assert sha16(fx.installed) != uncommitted_sha16
    assert set(_moved(before, after)) == {str(fx.installed)}, _moved(before, after)
    rows = fx.sync_rows()
    assert len(rows) == 1, rows
    assert rows[0]["commit_sha_full"] == sha
    assert [s["name"] for s in rows[0]["surfaces_synced"]] == ["hook:demo-hook"], rows[0]


def test_the_snapshot_is_removed_after_the_run(fx):
    """The committed tree is materialised into TMPDIR and must not be left behind."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    fx.commit(fx.cgg, "a real runtime commit")
    fx.run("%s -m 'a real runtime commit'" % ADJACENT_PHRASE)
    leftovers = [p.name for p in fx.tmp.iterdir() if p.name.startswith("cgg-sync-committed-")]
    assert leftovers == [], "snapshot residue left in TMPDIR: %s" % leftovers


# ---------------------------------------------------------------------------
# PROPERTY 4 — recognises the `-C` form.
# ---------------------------------------------------------------------------

def test_dash_C_form_from_a_cwd_outside_both_repos_is_recognised(fx):
    """The spelling the old substring test could not see — `git -C <path> commit` carries no
    adjacent two-word phrase at all. The commit is made from a CWD outside BOTH repos, and
    the payload carries that exact command text."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED-VIA-DASH-C\n", encoding="utf-8")
    sha = fx.commit(fx.cgg, "landed through the -C form", cwd=fx.root)
    committed_sha16 = sha16(fx.surface)
    command = "git -C %s %s -m 'landed through the -C form'" % (fx.cgg, _VERB)
    assert ADJACENT_PHRASE not in command, "this arm is void unless the text lacks the phrase"

    before = fx.installed_shas()
    r = fx.run(command)
    after = fx.installed_shas()

    assert r.returncode == 0, r.stderr
    assert sha16(fx.installed) == committed_sha16
    assert set(_moved(before, after)) == {str(fx.installed)}, _moved(before, after)
    assert len(fx.sync_rows()) == 1


def test_a_command_text_that_never_mentions_git_at_all_is_still_recognised(fx):
    """The cure reads the REPO, not the text: a commit made by a wrapper script whose command
    text mentions neither word must sync exactly the same."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED-BY-WRAPPER\n", encoding="utf-8")
    fx.commit(fx.cgg, "landed through a wrapper")
    committed_sha16 = sha16(fx.surface)
    command = "./release.sh --tranche 12"
    assert "git" not in command and _VERB not in command

    before = fx.installed_shas()
    r = fx.run(command)
    after = fx.installed_shas()
    assert r.returncode == 0, r.stderr
    assert sha16(fx.installed) == committed_sha16
    assert set(_moved(before, after)) == {str(fx.installed)}


# ---------------------------------------------------------------------------
# THE COUPLED HALF — the branch-residence guard must not go dark behind the cure.
# ---------------------------------------------------------------------------

def test_non_main_residence_is_still_refused_and_leaves_its_residue(fx):
    """runtime-sync.py refuses an install-parity sync from a non-sole-writer branch
    (borns-tic673) by reading the resident branch OF THE PLUGIN ROOT IT IS GIVEN. The cure
    hands it a materialised snapshot, so the snapshot must carry the repo's HEAD identity or
    the guard silently passes. Nothing may install, and the refusal must leave its row."""
    fx.git(fx.cgg, "checkout", "-q", "-b", "side-lane")
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED-ON-SIDE\n", encoding="utf-8")
    fx.commit(fx.cgg, "a runtime commit on a side branch")
    before = fx.installed_shas()
    r = fx.run("%s -m 'a runtime commit on a side branch'" % ADJACENT_PHRASE)
    after = fx.installed_shas()

    assert r.returncode == 0, r.stderr
    assert "REFUSED" in r.stdout, "the branch-residence guard did not fire: %r" % r.stdout
    assert _moved(before, after) == {}, "a non-main residence installed bytes"
    rows = fx.sync_rows()
    assert len(rows) == 1, rows
    assert rows[0]["event"] == "sync_refused_branch_residence", rows[0]
    assert rows[0]["branch"] == "side-lane", rows[0]


def test_sole_writer_residence_is_stamped_on_the_sync_row(fx):
    """The other arm of the same guard: on the sole-writer lane the row carries the real
    branch, not a null — which is what the snapshot's mirrored identity is for."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    fx.commit(fx.cgg, "a real runtime commit")
    fx.run("%s -m 'a real runtime commit'" % ADJACENT_PHRASE)
    rows = fx.sync_rows()
    assert len(rows) == 1, rows
    assert rows[0]["reference_branch"] == "main", rows[0]
    assert rows[0]["non_main_override"] is False, rows[0]


# ---------------------------------------------------------------------------
# DOCUMENTED CONDITIONALS — both arms of each.
# ---------------------------------------------------------------------------

def test_reflog_present_path_names_the_reflog(fx):
    """Arm A of the landed-commit probe: the reflog is the record of WHICH action moved HEAD."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    fx.commit(fx.cgg, "a real runtime commit")
    r = fx.run("%s -m x" % ADJACENT_PHRASE)
    assert "via=reflog:commit" in r.stdout, r.stdout


def test_reflog_absent_falls_back_to_the_committer_date(fx):
    """Arm B: a repo with reflogs disabled has no record of WHICH action moved HEAD. The
    documented fallback is the committer date — a commit that is fresh still syncs, rather
    than silently never syncing (which would be a new silent-miss class)."""
    fx.git(fx.cgg, "config", "core.logAllRefUpdates", "false")
    logs = fx.cgg / ".git" / "logs"
    if logs.exists():
        shutil.rmtree(logs)
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED-NO-REFLOG\n", encoding="utf-8")
    fx.commit(fx.cgg, "a real runtime commit, no reflog")
    committed_sha16 = sha16(fx.surface)
    assert not (fx.cgg / ".git" / "logs" / "HEAD").exists()

    before = fx.installed_shas()
    r = fx.run("%s -m x" % ADJACENT_PHRASE)
    after = fx.installed_shas()
    assert "via=committer-date(no-reflog)" in r.stdout, r.stdout
    assert sha16(fx.installed) == committed_sha16
    assert set(_moved(before, after)) == {str(fx.installed)}


def test_a_ref_move_that_is_not_a_commit_is_declined_by_name(fx):
    """A checkout moves HEAD and refreshes the reflog inside the window. It is not a commit,
    and the decline must say which action it saw."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    fx.commit(fx.cgg, "a real runtime commit")
    fx.git(fx.cgg, "checkout", "-q", "-b", "elsewhere")
    fx.git(fx.cgg, "checkout", "-q", "main")
    before = fx.installed_shas()
    r = fx.run("git checkout main")
    after = fx.installed_shas()
    assert "was not a commit" in r.stdout, r.stdout
    assert _moved(before, after) == {}


def test_debug_is_off_by_default_and_on_when_armed(fx):
    """Both arms of the trace conditional. Default OFF means the hook stays silent on the
    common path; armed ON is what makes a live run's resolved roots auditable."""
    fx.surface.write_text("#!/usr/bin/env bash\necho UNCOMMITTED-DIRTY\n", encoding="utf-8")
    quiet = fx.run("echo %s" % ADJACENT_PHRASE, debug=False)
    loud = fx.run("echo %s" % ADJACENT_PHRASE, debug=True)
    assert quiet.stdout == "", "the hook is not silent by default: %r" % quiet.stdout
    assert "[post-commit-sync:debug]" in loud.stdout


def test_window_override_both_arms(fx):
    """Both arms of the freshness window: a back-dated real runtime commit is OUTSIDE the
    default window (no install), and INSIDE a window widened past its age (installs)."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED-STALE\n", encoding="utf-8")
    fx.commit(fx.cgg, "a stale runtime commit", stale=True)
    committed_sha16 = sha16(fx.surface)

    before = fx.installed_shas()
    narrow = fx.run("%s -m x" % ADJACENT_PHRASE)
    assert _moved(before, fx.installed_shas()) == {}, "a stale commit installed under the default window"
    assert "outside the" in narrow.stdout or "no ref moved" in narrow.stdout

    wide = fx.run("%s -m x" % ADJACENT_PHRASE, window=str(STALE * 2))
    assert wide.returncode == 0, wide.stderr
    assert sha16(fx.installed) == committed_sha16
    assert set(_moved(before, fx.installed_shas())) == {str(fx.installed)}


# ---------------------------------------------------------------------------
# THE MANIFEST COPY — same class, same file: it must also come from the commit.
# ---------------------------------------------------------------------------

def test_manifest_copy_takes_the_committed_manifest_not_the_working_one(fx):
    """The hook copies sync-manifest.json to the installed location when the commit changed
    it. That copy is an install of runtime bytes like any other, so it must come from the
    COMMITTED tree — a working-tree manifest is exactly the class this cure keeps out."""
    committed = json.loads(REAL_MANIFEST.read_text(encoding="utf-8"))
    committed["_fixture_marker"] = "COMMITTED-MANIFEST"
    fx.fx_manifest.write_text(json.dumps(committed, indent=2), encoding="utf-8")
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    fx.commit(fx.cgg, "manifest + runtime change")
    committed_manifest_sha = sha16(fx.fx_manifest)

    dirty = dict(committed)
    dirty["_fixture_marker"] = "UNCOMMITTED-MANIFEST"
    fx.fx_manifest.write_text(json.dumps(dirty, indent=2), encoding="utf-8")
    assert sha16(fx.fx_manifest) != committed_manifest_sha

    r = fx.run("%s -m 'manifest + runtime change'" % ADJACENT_PHRASE)
    assert "sync-manifest.json CHANGED in this commit" in r.stdout, r.stdout
    assert sha16(fx.installed_manifest) == committed_manifest_sha, (
        "the installed manifest is not the committed manifest")
    body = json.loads(fx.installed_manifest.read_text(encoding="utf-8"))
    assert body["_fixture_marker"] == "COMMITTED-MANIFEST"


# ---------------------------------------------------------------------------
# ISOLATION AND SHAPE — asserted, not prosed.
# ---------------------------------------------------------------------------

def test_every_resolved_root_is_a_fixture_path(fx):
    """The per-run proof the dispatch requires: ZONE_ROOT, CGG_ROOT, SCRIPT_DIR, HOME, the
    install root and the snapshot must ALL resolve inside the fixture."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    fx.commit(fx.cgg, "a real runtime commit")
    r = fx.run("%s -m x" % ADJACENT_PHRASE)
    trace = [ln for ln in r.stdout.splitlines() if ln.startswith("[post-commit-sync:debug]")]
    assert trace, r.stdout
    blob = "\n".join(trace)
    for key in ("ZONE_ROOT=", "CGG_ROOT=", "SCRIPT_DIR=", "SNAPSHOT_ROOT=", "HOME=",
                "INSTALL_ROOT="):
        assert key in blob, "trace does not name %s: %s" % (key, blob)
    for line in trace:
        for token in line.split():
            key, sep, value = token.partition("=")
            if not sep or not value.startswith("/"):
                continue
            assert value.startswith(str(fx.root)), (
                "a resolved path escaped the fixture: %s (fixture root %s)" % (token, fx.root))


def test_sync_log_lands_in_the_fixture_zone_not_the_real_one(fx):
    """runtime-sync resolves its log through audit_logs_path(zone_root); zone_root is the
    --project-dir the hook passes. Proven by the row landing in the fixture."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    fx.commit(fx.cgg, "a real runtime commit")
    fx.run("%s -m x" % ADJACENT_PHRASE)
    log = fx.zone / "audit-logs" / "services" / "cgg-sync-log.jsonl"
    assert log.is_file(), "no fixture sync log was written"
    assert len(fx.sync_rows()) == 1


def test_agent_identity_is_still_threaded_into_the_sync_row(fx):
    """No regression on what the hook still owes: agent_id / agent_type from the payload
    reach the sync-log row."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    fx.commit(fx.cgg, "a real runtime commit")
    fx.run("%s -m x" % ADJACENT_PHRASE)
    rows = fx.sync_rows()
    assert len(rows) == 1, rows
    assert rows[0]["agent_id"] == "fixture-agent-808", rows[0]
    assert rows[0]["agent_type"] == "fixture-seat", rows[0]


def test_absent_agent_fields_resolve_to_empty_not_to_a_crash(fx):
    """The payload schema is externally versioned. Both fields absent must still sync."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    fx.commit(fx.cgg, "a real runtime commit")
    thin = json.dumps({"tool_input": {"command": "anything"}})
    r = subprocess.run(["bash", str(hook_under_test())], input=thin, text=True,
                       capture_output=True, cwd=str(fx.root), env=fx.env(), timeout=180)
    assert r.returncode == 0, r.stderr
    rows = fx.sync_rows()
    assert len(rows) == 1, rows
    assert rows[0]["agent_id"] == "" and rows[0]["agent_type"] == "", rows[0]


def test_wire_cutter_is_still_sourced_before_any_work(fx):
    """No regression: the emergency kill switch still runs, and still stops the hook."""
    wire = fx.home / ".claude" / "wire-cutter.sh"
    wire.write_text("wire_check() { echo 'WIRE CUT'; exit 0; }\n", encoding="utf-8")
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    fx.commit(fx.cgg, "a real runtime commit")
    before = fx.installed_shas()
    r = fx.run("%s -m x" % ADJACENT_PHRASE)
    assert "WIRE CUT" in r.stdout, r.stdout
    assert _moved(before, fx.installed_shas()) == {}


def test_the_hook_is_syntactically_valid(fx):
    r = subprocess.run(["bash", "-n", str(hook_under_test())], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_the_rider_travels_verbatim_on_one_contiguous_comment_line():
    """The does-not-satisfy rider of the LATER and WIDER ruling, reproduced verbatim as ONE
    contiguous unit on ONE comment line of the hook under test."""
    text = hook_under_test().read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if RIDER in ln]
    assert len(lines) == 1, "the rider must appear exactly once, contiguous: found %d" % len(lines)
    assert lines[0].lstrip().startswith("#"), "the rider must ride a comment line"


# ---------------------------------------------------------------------------
# THE FEDERATION-REPO ARM — the layout where CGG carries no .git of its own and the
# federation repo owns canonical_developer/context-grapple-gun/cgg-runtime/. It is the
# SAME class of defect as the CGG arm, so it is cured under the same four properties; a
# documented branch with no fixture is an unexercised conditional, so it gets one.
# ---------------------------------------------------------------------------

class FederationFixture(Fixture):
    """CGG has NO .git; the ZONE is the repo of record and the runtime lives under
    canonical_developer/context-grapple-gun/cgg-runtime/ inside it."""

    def __init__(self, root: Path):
        self.root = root
        self.home = root / "home"
        self.zone = root / "zone"
        self.tmp = root / "tmp"
        self.gitconf = root / "gitconfig-empty"
        self.cgg = self.zone / "canonical_developer" / "context-grapple-gun"
        self.other = root / "other"

        self.tmp.mkdir(parents=True)
        self.gitconf.write_text("", encoding="utf-8")

        (self.zone / "audit-logs" / "services").mkdir(parents=True)
        (self.zone / "audit-logs" / "signals").mkdir(parents=True)
        (self.zone / ".ticzone").write_text(
            json.dumps({"name": "fixture-synchook-808-federation", "tz": "UTC",
                        "include": ["."], "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"]}),
            encoding="utf-8")
        (self.zone / ".federation-root").write_text("", encoding="utf-8")

        (self.home / ".claude" / "hooks").mkdir(parents=True)
        (self.home / ".claude" / "cgg-runtime").mkdir(parents=True)
        os.symlink(REAL_SCRIPTS, self.home / ".claude" / "cgg-runtime" / "scripts")
        shutil.copy2(REAL_MANIFEST, self.home / ".claude" / "cgg-runtime" / "sync-manifest.json")

        self._init_repo(self.zone)   # the ZONE is the repo
        self._init_repo(self.other)

        (self.cgg / "cgg-runtime" / "hooks").mkdir(parents=True)
        self.surface = self.cgg / "cgg-runtime" / "hooks" / "demo-hook.sh"
        self.surface2 = self.cgg / "cgg-runtime" / "hooks" / "demo-second.sh"
        self.nonruntime = self.zone / "notes.txt"
        self.fx_manifest = self.cgg / "cgg-runtime" / "sync-manifest.json"
        self.surface.write_text("#!/usr/bin/env bash\necho BASE\n", encoding="utf-8")
        self.surface2.write_text("#!/usr/bin/env bash\necho SECOND-BASE\n", encoding="utf-8")
        self.nonruntime.write_text("base\n", encoding="utf-8")
        shutil.copy2(REAL_MANIFEST, self.fx_manifest)
        self.base_sha = self.commit(self.zone, "federation fixture base", stale=True)
        (self.other / "notes.txt").write_text("base\n", encoding="utf-8")
        self.commit(self.other, "other base", stale=True)

        self.installed = self.home / ".claude" / "hooks" / "demo-hook.sh"
        self.installed2 = self.home / ".claude" / "hooks" / "demo-second.sh"
        self.installed_manifest = self.home / ".claude" / "cgg-runtime" / "sync-manifest.json"
        self.prime_install()

    def stage_uninstalled_stale_runtime_commit(self) -> str:
        self.surface2.write_text("#!/usr/bin/env bash\necho SECOND-COMMITTED-STALE\n",
                                 encoding="utf-8")
        return self.commit(self.zone, "a stale runtime commit, never installed", stale=True)


@pytest.fixture()
def fedfx(tmp_path):
    return FederationFixture(tmp_path)


def test_federation_arm_installs_the_committed_bytes(fedfx):
    """A real runtime commit in the FEDERATION repo, with a dirtier working tree on top."""
    fedfx.surface.write_text("#!/usr/bin/env bash\necho FED-COMMITTED\n", encoding="utf-8")
    fedfx.commit(fedfx.zone, "a federation runtime commit")
    committed_sha16 = sha16(fedfx.surface)
    fedfx.surface.write_text("#!/usr/bin/env bash\necho FED-UNCOMMITTED\n", encoding="utf-8")

    before = fedfx.installed_shas()
    r = fedfx.run("%s -m 'a federation runtime commit'" % ADJACENT_PHRASE)
    after = fedfx.installed_shas()

    assert r.returncode == 0, r.stderr
    assert not (fedfx.cgg / ".git").exists(), "this arm is void if CGG has its own .git"
    assert sha16(fedfx.installed) == committed_sha16, r.stdout
    assert set(_moved(before, after)) == {str(fedfx.installed)}, _moved(before, after)


def test_federation_arm_declines_a_substring_only_command(fedfx):
    """The same negative control on the federation arm."""
    fedfx.stage_uninstalled_stale_runtime_commit()
    fedfx.surface.write_text("#!/usr/bin/env bash\necho FED-DIRTY\n", encoding="utf-8")
    before = fedfx.installed_shas()
    r = fedfx.run("echo %s" % ADJACENT_PHRASE)
    after = fedfx.installed_shas()
    assert r.returncode == 0, r.stderr
    assert _moved(before, after) == {}, "a substring-only command installed bytes"


def test_the_command_text_is_never_read_as_a_gate():
    """The structural half of property 4: the cure must not reintroduce a text gate. The
    hook may not extract tool_input.command at all."""
    text = hook_under_test().read_text(encoding="utf-8")
    assert "tool_input" not in text, (
        "the cured hook reads tool_input again — the defect is a text gate")
