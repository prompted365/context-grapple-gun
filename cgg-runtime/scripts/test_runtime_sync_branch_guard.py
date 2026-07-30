#!/usr/bin/env python3
"""Tests for the branch-residence guard in runtime-sync.py
(bk branch-residence sync guard, tic 675 — implementation from the t673 born
borns-tic673-branch-residence-regresses-installed-runtime).

The contract under guard: install-parity syncs mirror the RESIDENT BRANCH's
working tree, and the drift check compares installed bytes against that SAME
working tree — so a checkout to any non-main branch silently regresses
installed runtime semantics while drift reads 0 (reader and writer share one
reference). The cure at the write boundary: cmd_sync / cmd_auto_sync REFUSE
when the plugin repo's resident branch is not the sole-writer lane (main),
unless an explicit --allow-non-main override is armed — and every outcome
leaves durable residue in cgg-sync-log.jsonl (refusal rows on refusal;
reference_branch + non_main_override stamped on every successful sync row).

Both arms per documented conditional (selftest-fixture discipline):
refuse-on-branch AND sync-on-main AND override-with-lineage.

Run:  python3 -m unittest test_runtime_sync_branch_guard
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_spec = importlib.util.spec_from_file_location(
    "runtime_sync", os.path.join(_HERE, "runtime-sync.py"))
runtime_sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runtime_sync)


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, "-c", "user.email=t@t", "-c", "user.name=t",
         *args],
        capture_output=True, text=True, timeout=15)


def _make_repo(tmpdir, branch="main"):
    """Init a git repo with one commit on the given branch."""
    repo = os.path.join(tmpdir, "plugin")
    os.makedirs(repo, exist_ok=True)
    _git(repo, "init", "-b", branch)
    with open(os.path.join(repo, "surface.py"), "w") as f:
        f.write("MAIN_CONTENT = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init", "--no-gpg-sign")
    return repo


class TestGetCurrentBranch(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rsbg-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_main_residence_reads_main(self):
        repo = _make_repo(self.tmp)
        self.assertEqual(runtime_sync.get_current_branch(repo), "main")

    def test_branch_residence_reads_branch_name(self):
        repo = _make_repo(self.tmp)
        _git(repo, "checkout", "-b", "fix/distribution-release-lane")
        self.assertEqual(runtime_sync.get_current_branch(repo),
                         "fix/distribution-release-lane")

    def test_detached_head_reads_HEAD(self):
        repo = _make_repo(self.tmp)
        _git(repo, "checkout", "--detach")
        self.assertEqual(runtime_sync.get_current_branch(repo), "HEAD")

    def test_non_repo_reads_none(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        self.assertIsNone(runtime_sync.get_current_branch(plain))


class TestBranchResidenceGuard(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rsbg-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_sole_writer_lane_allowed(self):
        repo = _make_repo(self.tmp)
        g = runtime_sync.branch_residence_guard(repo)
        self.assertTrue(g["allowed"])
        self.assertEqual(g["branch"], "main")
        self.assertEqual(g["reason"], "sole_writer_lane")
        self.assertFalse(g["override"])

    def test_non_main_residence_refused(self):
        repo = _make_repo(self.tmp)
        _git(repo, "checkout", "-b", "feature/x")
        g = runtime_sync.branch_residence_guard(repo)
        self.assertFalse(g["allowed"])
        self.assertEqual(g["branch"], "feature/x")
        self.assertEqual(g["reason"], "non_main_residence")

    def test_detached_head_refused(self):
        # Detached HEAD is not the sole-writer lane either — same window.
        repo = _make_repo(self.tmp)
        _git(repo, "checkout", "--detach")
        g = runtime_sync.branch_residence_guard(repo)
        self.assertFalse(g["allowed"])
        self.assertEqual(g["branch"], "HEAD")

    def test_override_allows_with_lineage(self):
        repo = _make_repo(self.tmp)
        _git(repo, "checkout", "-b", "feature/x")
        g = runtime_sync.branch_residence_guard(repo, allow_non_main=True)
        self.assertTrue(g["allowed"])
        self.assertTrue(g["override"])
        self.assertEqual(g["reason"], "non_main_override")

    def test_no_git_reference_allowed(self):
        # No git repo → no checkout hazard exists; structural allow, named.
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        g = runtime_sync.branch_residence_guard(plain)
        self.assertTrue(g["allowed"])
        self.assertIsNone(g["branch"])
        self.assertEqual(g["reason"], "no_git_reference")


class TestWriteBoundaryPhysics(unittest.TestCase):
    """The guard fires at the write boundary — cmd_auto_sync / cmd_sync —
    before any copy side effect, and leaves durable sync-log residue."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rsbg-")
        self.zone = os.path.join(self.tmp, "zone")
        os.makedirs(os.path.join(self.zone, "audit-logs", "services"))
        self.repo = _make_repo(self.tmp)
        self.installed_dir = os.path.join(self.tmp, "installed")
        os.makedirs(self.installed_dir)
        self.surface = {
            "name": "script:surface",
            "canonical": os.path.join(self.repo, "surface.py"),
            "installed": os.path.join(self.installed_dir, "surface.py"),
            "type": "SCRIPT_CODE",
            "category": "scripts",
        }

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _log_rows(self):
        path = os.path.join(self.zone, "audit-logs", "services",
                            "cgg-sync-log.jsonl")
        if not os.path.isfile(path):
            return []
        with open(path) as f:
            return [json.loads(l) for l in f if l.strip()]

    def test_auto_sync_refuses_on_branch_no_copy_with_residue(self):
        _git(self.repo, "checkout", "-b", "feature/x")
        runtime_sync.cmd_auto_sync([self.surface], self.zone, self.repo)
        self.assertFalse(
            os.path.isfile(self.surface["installed"]),
            "guard must refuse BEFORE the copy side effect")
        rows = self._log_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "sync_refused_branch_residence")
        self.assertEqual(rows[0]["branch"], "feature/x")
        self.assertEqual(rows[0]["sole_writer_branch"], "main")

    def test_auto_sync_on_main_copies_and_stamps_reference(self):
        runtime_sync.cmd_auto_sync([self.surface], self.zone, self.repo)
        self.assertTrue(os.path.isfile(self.surface["installed"]))
        rows = self._log_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "sync")
        self.assertEqual(rows[0]["reference_branch"], "main")
        self.assertFalse(rows[0]["non_main_override"])

    def test_auto_sync_override_copies_with_override_lineage(self):
        _git(self.repo, "checkout", "-b", "feature/x")
        runtime_sync.cmd_auto_sync([self.surface], self.zone, self.repo,
                                   allow_non_main=True)
        self.assertTrue(os.path.isfile(self.surface["installed"]))
        rows = self._log_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "sync")
        self.assertEqual(rows[0]["reference_branch"], "feature/x")
        self.assertTrue(rows[0]["non_main_override"])

    def test_cmd_sync_refuses_on_branch(self):
        _git(self.repo, "checkout", "-b", "feature/x")
        result = runtime_sync.cmd_sync([self.surface], self.zone, self.repo)
        self.assertEqual(result, "refused_branch_residence")
        self.assertFalse(os.path.isfile(self.surface["installed"]))


if __name__ == "__main__":
    unittest.main()
