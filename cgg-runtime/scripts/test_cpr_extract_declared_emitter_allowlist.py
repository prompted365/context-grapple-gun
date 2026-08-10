#!/usr/bin/env python3
"""Tests for the declared-emitter allow-list at the cpr-extract intake mouth
(bk-cpr-extract-declared-emitter-allowlist, tic 696 — filed from the tic-695
membrane-fence sibling survey, site 2).

The defect under cure: find_governance_files' CLAUDE.md/MEMORY.md leg is an
unbounded rglob behind the .ticignore DENY-list while the borns and --plan-file
legs are already allow-lists. Emitter status was being INFERRED from a basename:
any file merely NAMED CLAUDE.md/MEMORY.md inside the audit-logs DATA tree —
whose mailbox membrane accumulates inbound dumps, extracted archives, and
consolidate copies — became a governance intake surface by name alone. Live
material at filing: 4 files / 29 extractable blocks in the ent_breyden mailbox;
at strike time the rglob was ingesting 2 mailbox CLAUDE.md files from the
ent_homeskillet mailbox (harpoonables inbound + harpoonTargets queue). Blast
radius 0 to date only by terminal-valve luck; no-source blocks would mint NEW
dedup hashes (hash valve blind).

The cure, both halves DECLARED not inferred (Emitter Surface Declared
Interface):
  A. rglob-leg allow-list — the doctrine-tree scan may not enter the audit-logs
     data tree; that tree's only declared emitter (the borns home) is its own
     allow-listed leg. NOT a ported deny-fence: the boundary is the declared
     doctrine-tree/data-tree split, resolved from .ticzone config, not a path
     blacklist.
  B. --plan-file membrane arming — a plan file resolving into the zone's
     agent-mailboxes membrane tree is typed-rejected AT INTAKE, before any
     side effect (membrane paths are FIELD evidence, never emitter surfaces;
     rescue material routes by copying into a declared emitter under /review,
     never by pointing the extractor at the membrane).

Contract teeth, each with a fixture arm (selftest-fixture discipline):
  1. mailbox membrane CLAUDE.md    -> NOT in the gov set (RED pre-fix)
  2. data-tree non-mailbox MEMORY.md -> NOT in the gov set (RED pre-fix)
  3. doctrine-tree files           -> still found (regression guard)
  4. borns leg                     -> unaffected (its own allow-list)
  5. membrane --plan-file          -> typed reject, exit 2, NO queue write
                                      (RED pre-fix — it would extract)
  6. non-membrane --plan-file      -> accepted, extracts (regression guard)
  7. custom audit_logs_path        -> boundary follows .ticzone config, not the
                                      literal "audit-logs" name (engine-content
                                      separation)

Fixtures are root-pinned to a temp zone (Self-Locating Artifact Test
Isolation); extract_cprs takes an explicit project_dir so no arm can touch the
real zone.

Run:  python3 -m unittest test_cpr_extract_declared_emitter_allowlist
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "cpr-extract.py")

_spec = importlib.util.spec_from_file_location("cpr_extract", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


CANDIDATE_BLOCK = """<!-- --agnostic-candidate
id: {cid}
status: pending
lesson: {lesson}
source: {source}
-->
"""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class DeclaredEmitterAllowlistTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="cpr-allowlist-test-")
        self.zone = Path(self._tmp.name)
        # Doctrine-tree surfaces (declared emitters)
        _write(self.zone / "CLAUDE.md", "# root doctrine\n")
        _write(self.zone / "domain_a" / "CLAUDE.md", "# domain doctrine\n")
        _write(self.zone / "MEMORY.md", "# project memory\n")
        # Data-tree surfaces named like emitters (NOT declared)
        self.mailbox_claude = _write(
            self.zone / "audit-logs" / "agent-mailboxes" / "ent_test"
            / "inbound" / "dump" / "CLAUDE.md",
            "# inbound dump masquerading by basename\n"
            + CANDIDATE_BLOCK.format(
                cid="cpr_membrane_should_never_extract_tic1",
                lesson="membrane lesson", source="membrane source"),
        )
        self.lane_memory = _write(
            self.zone / "audit-logs" / "some-lane" / "MEMORY.md",
            "# data-lane file named MEMORY.md\n",
        )
        # Borns home (its own allow-listed leg — must keep working)
        self.born = _write(
            self.zone / "audit-logs" / "governance" / "borns-tic12-test-born.md",
            "# born detail doc\n",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _gov_files(self, zone=None):
        zone = str(zone or self.zone)
        excludes = _mod.load_ticignore(zone)
        return _mod.find_governance_files(zone, excludes)

    # -- Arm 1: mailbox membrane file excluded ------------------------------
    def test_rglob_excludes_mailbox_membrane_file(self):
        files = self._gov_files()
        self.assertNotIn(self.mailbox_claude, files,
                         "mailbox membrane CLAUDE.md reached the governance "
                         "scan set — emitter status inferred from basename")

    # -- Arm 2: data-tree non-mailbox file excluded -------------------------
    def test_rglob_excludes_data_tree_nonmailbox_file(self):
        files = self._gov_files()
        self.assertNotIn(self.lane_memory, files,
                         "data-tree MEMORY.md reached the governance scan set")

    # -- Arm 3: doctrine-tree files still found (regression guard) ----------
    def test_rglob_keeps_doctrine_tree_files(self):
        files = self._gov_files()
        self.assertIn(self.zone / "CLAUDE.md", files)
        self.assertIn(self.zone / "domain_a" / "CLAUDE.md", files)
        self.assertIn(self.zone / "MEMORY.md", files)

    # -- Arm 4: borns leg unaffected ----------------------------------------
    def test_borns_leg_unaffected(self):
        files = self._gov_files()
        self.assertIn(self.born, files,
                      "borns home is the data tree's declared emitter leg and "
                      "must survive the allow-list")

    # -- Arm 5: membrane --plan-file typed-rejected before side effects -----
    def test_plan_file_membrane_path_rejected_typed_before_side_effects(self):
        queue = self.zone / "audit-logs" / "cprs" / "queue.jsonl"
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                _mod.extract_cprs(
                    str(self.zone), dry_run=False,
                    plan_file=str(self.mailbox_claude),
                )
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("plan_file_membrane_path_rejected", err.getvalue(),
                      "reject must be TYPED, naming its reason code")
        self.assertFalse(queue.exists(),
                         "membrane reject must fire before any queue write")

    # -- Arm 6: non-membrane --plan-file accepted (regression guard) --------
    def test_plan_file_outside_membrane_accepted(self):
        plan = _write(
            self.zone / "plans" / "active-plan.md",
            CANDIDATE_BLOCK.format(
                cid="cpr_plan_file_ok_tic1",
                lesson="plan lesson", source="plan source"),
        )
        entries, counters = _mod.extract_cprs(
            str(self.zone), dry_run=False, plan_file=str(plan),
        )
        ids = [e["id"] for e in entries]
        self.assertIn("cpr_plan_file_ok_tic1", ids)
        queue = self.zone / "audit-logs" / "cprs" / "queue.jsonl"
        self.assertTrue(queue.exists())

    # -- Arm 7: boundary follows .ticzone config, not the literal name ------
    def test_custom_audit_logs_path_respected(self):
        with tempfile.TemporaryDirectory(prefix="cpr-allowlist-custom-") as td:
            zone = Path(td)
            _write(zone / ".ticzone",
                   json.dumps({"audit_logs_path": "governance-data"}))
            _write(zone / "CLAUDE.md", "# root doctrine\n")
            custom_membrane = _write(
                zone / "governance-data" / "agent-mailboxes" / "ent_x"
                / "inbound" / "CLAUDE.md",
                "# membrane under custom data tree\n",
            )
            # A directory literally named audit-logs is NOT the data tree here
            literal_dir_file = _write(
                zone / "audit-logs" / "CLAUDE.md",
                "# doctrine-tree file under a literally-named dir\n",
            )
            files = self._gov_files(zone)
            self.assertNotIn(custom_membrane, files,
                             "configured data tree must be excluded")
            self.assertIn(literal_dir_file, files,
                          "the boundary is the CONFIGURED data tree, not the "
                          "literal 'audit-logs' basename")


if __name__ == "__main__":
    unittest.main()
