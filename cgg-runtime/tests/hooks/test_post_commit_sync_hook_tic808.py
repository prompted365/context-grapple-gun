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

TIC-818 EXTENSION — the ruled increment of /review 809 (Q3) on finding F-808-2:
  audit-logs/governance/receipts/2026-09-20-tic809-f808-2-merge-and-root-commits-never-sync-own-increment-ruling.md
    (2661 bytes, 15 lines, sha256 head-16 961ed5a01922eda2) — Architect-ratified,
    recommended option verbatim "Own increment, after goal 25 (Recommended)".
A merge-aware and root-aware "touched the runtime" predicate, ruled TOGETHER as ONE
predicate: the union of the per-parent diffs for a merge, the root form for a first
commit; an ordinary one-parent commit must decide exactly as it does today.

DOES-NOT-SATISFY RIDER (tic 818, travels verbatim): this increment does NOT change which paths count as runtime surfaces, does NOT widen the hook's 300-second freshness window, does NOT add a live witness for the committed-versus-working-tree arm (still fixture-only), and does NOT make the federation-repo arm reachable (F-808-4 stands).

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


# ===========================================================================
# TIC-818 ARMS — the merge-aware and root-aware predicate (ruled /review 809 on F-808-2).
#
# DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT change which paths count as runtime surfaces, does NOT widen the hook's 300-second freshness window, does NOT add a live witness for the committed-versus-working-tree arm (still fixture-only), and does NOT make the federation-repo arm reachable (F-808-4 stands).
# ===========================================================================
import re as _re

RIDER_818 = "this increment does NOT change which paths count as runtime surfaces, does NOT widen the hook's 300-second freshness window, does NOT add a live witness for the committed-versus-working-tree arm (still fixture-only), and does NOT make the federation-repo arm reachable (F-808-4 stands)."


def _plain_predicate(fx, repo: Path, sha: str) -> list:
    """The tic-808 predicate form, verbatim — the baseline an ordinary commit must still
    decide identically under."""
    r = fx.git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", sha)
    return [x for x in r.stdout.splitlines() if x.strip()]


def predicate_output(fx, repo: Path, sha: str) -> list:
    """Run the predicate OF THE HOOK UNDER TEST: the flags are READ OUT of the hook's own
    CHANGED_FILES assignment, never retyped here, so an arm can say what the predicate SAW
    rather than only that the hook was silent. A silent zero and a looked-and-found-nothing
    zero are different strengths of zero, and the ruled proof duty needs the second."""
    line = None
    for ln in hook_under_test().read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if s.startswith("CHANGED_FILES=") and "diff-tree" in s:
            line = s
            break
    assert line is not None, "no CHANGED_FILES diff-tree assignment in the hook under test"
    mm = _re.search(r'diff-tree\s+(.*?)\s+"\$COMMIT_SHA"', line)
    assert mm, "could not read the predicate flags out of: %s" % line
    flags = mm.group(1).split()
    r = fx.git(repo, "diff-tree", *flags, sha)
    return [x for x in r.stdout.splitlines() if x.strip()]


def _first_parent_names(fx, repo: Path, sha: str) -> list:
    r = fx.git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", sha + "^1", sha)
    return [x for x in r.stdout.splitlines() if x.strip()]


def _runtime(names) -> list:
    return [n for n in names if n.startswith("cgg-runtime/")]


def _merge_authored_by_commit(fx, repo: Path, side: str, message: str) -> str:
    """A MERGE commit whose reflog action is `commit (merge)` — the authoring path a
    resolved conflicted merge takes, and one of the two shapes that reach the ruled
    predicate at all (see test_a_clean_merge_is_declined_by_the_landed_commit_gate)."""
    fx.git(repo, "merge", "--no-commit", "--no-ff", side)
    fx.git(repo, _VERB, "-q", "-m", message)
    return fx.git(repo, "rev-parse", "HEAD").stdout.strip()


def _is_merge(fx, repo: Path, sha: str) -> bool:
    return len(fx.git(repo, "rev-list", "--parents", "-n1", sha).stdout.split()) == 3


class RootFixture(Fixture):
    """A fixture whose repo of record has NO commits at all, so the arm's own commit IS the
    repository's ROOT commit.

    The base Fixture deliberately opens every repo with an empty genesis commit
    (Fixture._init_repo) precisely so that no fixture commit is ever a root commit — that
    instrument choice is what kept F-808-2's root half invisible at tic 808, and it bit the
    808 seat's own prediction bank (recorded there as M-808-1). This subclass removes the
    shield for the arms that must see the blindness."""

    def __init__(self, root: Path):
        self.root = root
        self.home = root / "home"
        self.zone = root / "zone"
        self.cgg = root / "cgg"
        self.other = root / "other"
        self.tmp = root / "tmp"
        self.gitconf = root / "gitconfig-empty"

        self.tmp.mkdir(parents=True)
        self.gitconf.write_text("", encoding="utf-8")

        (self.zone / "audit-logs" / "services").mkdir(parents=True)
        (self.zone / "audit-logs" / "signals").mkdir(parents=True)
        (self.zone / ".ticzone").write_text(
            json.dumps({"name": "fixture-synchook-818-root", "tz": "UTC", "include": ["."],
                        "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"]}), encoding="utf-8")

        (self.home / ".claude" / "hooks").mkdir(parents=True)
        (self.home / ".claude" / "cgg-runtime").mkdir(parents=True)
        os.symlink(REAL_SCRIPTS, self.home / ".claude" / "cgg-runtime" / "scripts")
        shutil.copy2(REAL_MANIFEST, self.home / ".claude" / "cgg-runtime" / "sync-manifest.json")

        # THE REPO OF RECORD OPENS EMPTY — no genesis, so the next commit is the ROOT.
        self.cgg.mkdir(parents=True, exist_ok=True)
        self.git(self.cgg, "init", "-q", "-b", "main")
        self._init_repo(self.other)

        (self.cgg / "cgg-runtime" / "hooks").mkdir(parents=True)
        self.surface = self.cgg / "cgg-runtime" / "hooks" / "demo-hook.sh"
        self.surface2 = self.cgg / "cgg-runtime" / "hooks" / "demo-second.sh"
        self.nonruntime = self.cgg / "notes.txt"
        self.fx_manifest = self.cgg / "cgg-runtime" / "sync-manifest.json"
        self.surface.write_text("#!/usr/bin/env bash\necho ROOT-COMMITTED\n", encoding="utf-8")
        self.surface2.write_text("#!/usr/bin/env bash\necho SECOND-BASE\n", encoding="utf-8")
        self.nonruntime.write_text("base\n", encoding="utf-8")
        shutil.copy2(REAL_MANIFEST, self.fx_manifest)
        self.base_sha = None

        self.installed = self.home / ".claude" / "hooks" / "demo-hook.sh"
        self.installed2 = self.home / ".claude" / "hooks" / "demo-second.sh"
        self.installed_manifest = self.home / ".claude" / "cgg-runtime" / "sync-manifest.json"
        # deliberately NOT primed: nothing was ever installed from a repo with no commits.


@pytest.fixture()
def rootfx(tmp_path):
    return RootFixture(tmp_path)


# --- THE ROOT HALF ---------------------------------------------------------

def test_a_root_commit_that_adds_the_runtime_syncs(rootfx):
    """THE ROOT HALF OF THE RULED PREDICATE. A repository's FIRST commit, which adds the
    runtime. `diff-tree -r <root>` prints nothing (no parent to diff against), so before
    this cure the hook declined at the runtime-touch gate and the runtime was never
    installed for a fresh repo."""
    assert rootfx.git(rootfx.cgg, "rev-parse", "--verify", "HEAD").returncode != 0, (
        "this arm is void unless the repo of record starts with NO commits")
    sha = rootfx.commit(rootfx.cgg, "the repository's first commit, adding the runtime")
    parents = rootfx.git(rootfx.cgg, "rev-list", "--parents", "-n1", sha).stdout.split()
    assert len(parents) == 1, "this arm is void unless the commit is a ROOT commit: %r" % parents
    committed = sha16(rootfx.surface)

    before = rootfx.installed_shas()
    r = rootfx.run("%s -m 'the first commit'" % ADJACENT_PHRASE)
    after = rootfx.installed_shas()

    assert r.returncode == 0, r.stderr
    assert "via=reflog:commit (initial)" in r.stdout, (
        "the landed-commit gate did not admit the root commit: %r" % r.stdout)
    assert sha16(rootfx.installed) == committed, r.stdout
    assert str(rootfx.installed) in _moved(before, after), _moved(before, after)
    rows = rootfx.sync_rows()
    assert len(rows) == 1, rows
    assert rows[0]["commit_sha_full"] == sha, rows[0]


def test_the_root_form_is_what_makes_the_root_half_work(rootfx):
    """The root half is `--root`, and `-m` alone does not supply it — measured on the same
    sha, so the two flags are proven to be one predicate rather than two spellings."""
    sha = rootfx.commit(rootfx.cgg, "the repository's first commit, adding the runtime")
    assert _plain_predicate(rootfx, rootfx.cgg, sha) == [], (
        "the tic-808 plain form must be BLIND on a root commit, or this arm is void")
    m_only = rootfx.git(rootfx.cgg, "diff-tree", "--no-commit-id", "--name-only", "-r", "-m", sha)
    assert [x for x in m_only.stdout.splitlines() if x.strip()] == [], (
        "-m alone must still be blind on a root commit")
    assert _runtime(predicate_output(rootfx, rootfx.cgg, sha)), (
        "the hook's own predicate must see the runtime in a root commit")


# --- THE MERGE HALF --------------------------------------------------------

def test_a_merge_that_brings_a_runtime_change_syncs(fx):
    """THE MERGE HALF OF THE RULED PREDICATE. `diff-tree -r <merge>` prints nothing (it
    needs a per-parent form), so before this cure a merge that brought runtime changes
    never installed them."""
    fx.git(fx.cgg, "checkout", "-q", "-b", "side")
    fx.surface.write_text("#!/usr/bin/env bash\necho MERGED-FROM-SIDE\n", encoding="utf-8")
    fx.commit(fx.cgg, "the side branch changes the runtime")
    fx.git(fx.cgg, "checkout", "-q", "main")
    sha = _merge_authored_by_commit(fx, fx.cgg, "side", "merge the side branch into main")
    assert _is_merge(fx, fx.cgg, sha), "this arm is void unless HEAD is a MERGE commit"
    committed = sha16(fx.surface)
    assert _plain_predicate(fx, fx.cgg, sha) == [], (
        "the tic-808 plain form must be BLIND on a merge, or this arm is void")

    before = fx.installed_shas()
    r = fx.run("%s -m 'merge the side branch into main'" % ADJACENT_PHRASE)
    after = fx.installed_shas()

    assert r.returncode == 0, r.stderr
    assert "via=reflog:commit (merge)" in r.stdout, r.stdout
    assert sha16(fx.installed) == committed, r.stdout
    assert set(_moved(before, after)) == {str(fx.installed)}, _moved(before, after)
    rows = fx.sync_rows()
    assert len(rows) == 1, rows
    assert rows[0]["commit_sha_full"] == sha, rows[0]


def test_a_merge_that_brings_no_runtime_change_stays_silent(fx):
    """THE RULED SILENCE. A merge whose side branch touched only non-runtime paths, forked
    from a mainline whose runtime was already current. It must install nothing — and it must
    be silent because the predicate LOOKED AND FOUND NO RUNTIME, not because it was blind.
    A stale, committed, never-installed runtime surface is staged BEFORE the fork so that any
    spurious sync would move a named member; without it the arm would pass for the wrong
    reason."""
    fx.stage_uninstalled_stale_runtime_commit()
    fx.git(fx.cgg, "checkout", "-q", "-b", "side")
    fx.nonruntime.write_text("the side branch touches only notes\n", encoding="utf-8")
    fx.commit(fx.cgg, "the side branch changes nothing under the runtime")
    fx.git(fx.cgg, "checkout", "-q", "main")
    sha = _merge_authored_by_commit(fx, fx.cgg, "side", "merge a non-runtime side branch")
    assert _is_merge(fx, fx.cgg, sha), "this arm is void unless HEAD is a MERGE commit"

    names = predicate_output(fx, fx.cgg, sha)
    assert names, (
        "the predicate is BLIND here, so silence would prove nothing: a merge that brings "
        "none must be silent because it LOOKED, not because it cannot see merges")
    assert _runtime(names) == [], names
    assert _runtime(_first_parent_names(fx, fx.cgg, sha)) == [], (
        "this arm is void unless the merge truly brings no runtime change to its first parent")

    before = fx.installed_shas()
    r = fx.run("%s -m 'merge a non-runtime side branch'" % ADJACENT_PHRASE)
    after = fx.installed_shas()

    assert r.returncode == 0, r.stderr
    assert "did not touch" in r.stdout, (
        "expected the explicit did-not-touch-the-runtime decline; got %r" % r.stdout)
    assert _moved(before, after) == {}, "a merge that brings no runtime change installed bytes"
    assert fx.sync_rows() == []


# --- THE ORDINARY COMMIT MUST NOT MOVE -------------------------------------

def test_the_predicate_decides_an_ordinary_one_parent_commit_exactly_as_today(fx):
    """BOTH ARMS of the unchanged requirement. The hook's own predicate flags are read out of
    the hook under test and run against the same sha as the tic-808 plain form; the outputs
    must be identical for a runtime commit AND for a non-runtime commit."""
    fx.surface.write_text("#!/usr/bin/env bash\necho COMMITTED\n", encoding="utf-8")
    runtime_sha = fx.commit(fx.cgg, "an ordinary runtime commit")
    fx.nonruntime.write_text("changed, but not runtime\n", encoding="utf-8")
    nonruntime_sha = fx.commit(fx.cgg, "an ordinary non-runtime commit")

    for sha, label in ((runtime_sha, "runtime"), (nonruntime_sha, "non-runtime")):
        plain = _plain_predicate(fx, fx.cgg, sha)
        under_test = predicate_output(fx, fx.cgg, sha)
        assert under_test == plain, (
            "%s arm diverged from the tic-808 form: under_test=%r plain=%r"
            % (label, under_test, plain))
    assert _runtime(_plain_predicate(fx, fx.cgg, runtime_sha)), (
        "positive control DARK: the runtime arm's plain output must be non-empty")
    assert _runtime(_plain_predicate(fx, fx.cgg, nonruntime_sha)) == []


# --- REACHABILITY: measured, NOT cured (fenced out of this increment) ------

def test_a_clean_merge_is_declined_by_the_landed_commit_gate_not_by_the_predicate(fx):
    """FINDING F-818-1, asserted rather than prosed, and TRUE OF BOTH HOOKS.

    A clean `git merge` writes the reflog action `merge <branch>:`, which the landed-commit
    gate DECLINES BY NAME (the hook's own documented decline list) before the runtime
    predicate is ever reached. The tic-818 cure therefore does NOT make a clean merge sync.
    That gate is a DIFFERENT predicate and is fenced out of this increment — this arm exists
    so the limit is a measured, executing assertion instead of a sentence in a receipt."""
    fx.git(fx.cgg, "checkout", "-q", "-b", "side")
    fx.surface.write_text("#!/usr/bin/env bash\necho MERGED-FROM-SIDE\n", encoding="utf-8")
    fx.commit(fx.cgg, "the side branch changes the runtime")
    fx.git(fx.cgg, "checkout", "-q", "main")
    fx.git(fx.cgg, "merge", "-q", "--no-ff", "side", "-m", "a clean merge")
    sha = fx.git(fx.cgg, "rev-parse", "HEAD").stdout.strip()
    assert _is_merge(fx, fx.cgg, sha), "this arm is void unless HEAD is a MERGE commit"
    subject = fx.git(fx.cgg, "log", "-g", "-1", "--format=%gs").stdout.strip()
    assert subject.startswith("merge side:"), (
        "this arm is void unless a clean merge writes a `merge <branch>:` action: %r" % subject)

    before = fx.installed_shas()
    r = fx.run("git merge --no-ff side")
    after = fx.installed_shas()

    assert r.returncode == 0, r.stderr
    assert "was not a commit" in r.stdout, (
        "expected the landed-commit gate's by-name decline; got %r" % r.stdout)
    assert _moved(before, after) == {}
    assert fx.sync_rows() == []


def test_a_merge_reaches_the_predicate_when_reflogs_are_disabled(fx):
    """The OTHER reachable path for the merge half, and the far arm of the hook's own
    documented reflog-present / reflog-absent conditional: with reflogs disabled the
    committer-date fallback is in force, the action gate is not consulted at all, and a clean
    merge does reach the ruled predicate."""
    fx.git(fx.cgg, "checkout", "-q", "-b", "side")
    fx.surface.write_text("#!/usr/bin/env bash\necho MERGED-NO-REFLOG\n", encoding="utf-8")
    fx.commit(fx.cgg, "the side branch changes the runtime")
    fx.git(fx.cgg, "checkout", "-q", "main")
    fx.git(fx.cgg, "config", "core.logAllRefUpdates", "false")
    fx.git(fx.cgg, "merge", "-q", "--no-ff", "side", "-m", "a clean merge, no reflog")
    sha = fx.git(fx.cgg, "rev-parse", "HEAD").stdout.strip()
    assert _is_merge(fx, fx.cgg, sha)
    logs = fx.cgg / ".git" / "logs"
    if logs.exists():
        shutil.rmtree(logs)
    assert not (fx.cgg / ".git" / "logs" / "HEAD").exists()
    committed = sha16(fx.surface)

    before = fx.installed_shas()
    r = fx.run("git merge --no-ff side")
    after = fx.installed_shas()

    assert r.returncode == 0, r.stderr
    assert "via=committer-date(no-reflog)" in r.stdout, r.stdout
    assert sha16(fx.installed) == committed, r.stdout
    assert set(_moved(before, after)) == {str(fx.installed)}, _moved(before, after)


# --- THE UNION'S MEASURED EDGE --------------------------------------------

def test_the_ruled_union_also_fires_when_only_the_mainline_advanced_the_runtime(fx):
    """FINDING F-818-2, asserted rather than prosed.

    The ruling names the UNION of the per-parent diffs. When the MAINLINE advanced the
    runtime after the fork point and the side branch brought no runtime change at all, the
    union still contains a runtime path — because relative to the SECOND parent, the
    mainline's own runtime advance IS a change. So the hook syncs on a merge that brought NO
    runtime change relative to the branch it landed on (its FIRST parent).

    This is left exactly as the ruling ruled it and handed up, not re-scoped: the union is
    what was ruled, the over-fire is an idempotent re-install of bytes the mainline's own
    commit should already have installed, and the alternative axis (--first-parent) would be
    a different predicate than the one ratified."""
    fx.git(fx.cgg, "checkout", "-q", "-b", "side")
    fx.nonruntime.write_text("the side branch touches only notes\n", encoding="utf-8")
    fx.commit(fx.cgg, "the side branch changes nothing under the runtime")
    fx.git(fx.cgg, "checkout", "-q", "main")
    fx.surface.write_text("#!/usr/bin/env bash\necho MAINLINE-ADVANCED\n", encoding="utf-8")
    fx.commit(fx.cgg, "the MAINLINE advances the runtime after the fork point")
    sha = _merge_authored_by_commit(fx, fx.cgg, "side", "merge the non-runtime side branch")
    assert _is_merge(fx, fx.cgg, sha)

    assert _runtime(_first_parent_names(fx, fx.cgg, sha)) == [], (
        "this arm is void unless the merge brings NO runtime change to its first parent")
    names = predicate_output(fx, fx.cgg, sha)
    assert _runtime(names), (
        "the ruled UNION is expected to contain a runtime path here: %r" % names)

    before = fx.installed_shas()
    r = fx.run("%s -m 'merge the non-runtime side branch'" % ADJACENT_PHRASE)
    after = fx.installed_shas()

    assert r.returncode == 0, r.stderr
    assert set(_moved(before, after)) == {str(fx.installed)}, (
        "the ruled union is expected to SYNC here — that is the finding, measured: %r"
        % _moved(before, after))


# --- THE RIDER -------------------------------------------------------------

def test_the_tic818_rider_travels_verbatim_on_one_contiguous_comment_line():
    """The tic-818 does-not-satisfy rider, reproduced verbatim as ONE contiguous unit on ONE
    comment line of the hook under test."""
    text = hook_under_test().read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if RIDER_818 in ln]
    assert len(lines) == 1, (
        "the tic-818 rider must appear exactly once, contiguous: found %d" % len(lines))
    assert lines[0].lstrip().startswith("#"), "the rider must ride a comment line"
