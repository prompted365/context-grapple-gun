#!/usr/bin/env python3
"""Tests for review-promote-writeback.py — the emit-side writeback (inline status
flip + auto-memory breadcrumb stamp). Closes the no-coverage gap (bk-emitter-review-wiring).

The module name is hyphenated, so it loads via importlib spec_from_file_location.
Every case isolates against a TemporaryDirectory through the script's search-dir /
am-dir test hooks — nothing touches the real auto-memory dir.

Run:  python3 -m unittest test_review_promote_writeback   (from cgg-runtime/scripts/)
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "review_promote_writeback", os.path.join(_HERE, "review-promote-writeback.py")
)
rpw = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rpw)


def _candidate(cpr_id, status="pending"):
    return (
        "# Topic\n\nsome prose\n\n"
        "<!-- --agnostic-candidate\n"
        f"  id: {cpr_id}\n"
        f"  status: {status}\n"
        '  lesson: "a durable lesson"\n'
        '  source: "handoff"\n'
        "-->\n\ntrailing prose\n"
    )


class TestBarePath(unittest.TestCase):
    def test_strips_anchor_linerange_scopehint_compound(self):
        self.assertEqual(rpw._bare_path("feedback_x.md#some-anchor"), "feedback_x.md")
        self.assertEqual(rpw._bare_path("feedback_x.md:12-40"), "feedback_x.md")
        self.assertEqual(rpw._bare_path("feedback_x.md (scope hint here)"), "feedback_x.md")
        # compound "A + B" -> first member
        self.assertEqual(
            rpw._bare_path("feedback_x.md#a + ledger.md#b"), "feedback_x.md"
        )


class TestFlipInlineStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_flip_pending_inserts_promoted_fields(self):
        f = self.dir / "MEMORY.md"
        f.write_text(_candidate("cpr_demo_tic500"), encoding="utf-8")
        actions = rpw.flip_inline_status(
            "cpr_demo_tic500", "promoted", 510, "feedback_demo.md",
            search_dir=self.dir,
        )
        self.assertEqual(sum(a["action"] == "flip" for a in actions), 1)
        text = f.read_text(encoding="utf-8")
        self.assertIn("status: promoted", text)
        self.assertNotIn("status: pending", text)
        self.assertIn("promoted_to:", text)
        self.assertIn("promoted_tic: 510", text)

    def test_terminal_status_not_reflipped(self):
        f = self.dir / "MEMORY.md"
        f.write_text(_candidate("cpr_demo_tic500", status="promoted_spec"), encoding="utf-8")
        actions = rpw.flip_inline_status(
            "cpr_demo_tic500", "promoted", 510, "feedback_demo.md",
            search_dir=self.dir,
        )
        self.assertTrue(any(a["action"] == "noop" for a in actions))
        self.assertIn("status: promoted_spec", f.read_text(encoding="utf-8"))


class TestStampBreadcrumb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_stamp_then_idempotent_noop(self):
        target = self.dir / "feedback_demo.md"
        target.write_text("# feedback\n\nbody\n", encoding="utf-8")
        first = rpw.stamp_breadcrumb(
            "cpr_demo_tic500", "feedback_demo.md", 500, 510, "MEMORY.md",
            am_dir=self.dir,
        )
        self.assertEqual(first["action"], "stamp")
        content = target.read_text(encoding="utf-8")
        self.assertIn("promoted from cpr_demo_tic500", content)
        # second run is a no-op (breadcrumb already present)
        second = rpw.stamp_breadcrumb(
            "cpr_demo_tic500", "feedback_demo.md", 500, 510, "MEMORY.md",
            am_dir=self.dir,
        )
        self.assertEqual(second["action"], "noop")
        self.assertEqual(content.count("promoted from cpr_demo_tic500"), 1)

    def test_ledger_target_is_skipped(self):
        # a ledger / CLAUDE.md target is owned by the ledger-inscription step
        res = rpw.stamp_breadcrumb(
            "cpr_demo_tic500",
            "audit-logs/governance/constitution-ledger/ledger.md#some-anchor",
            500, 510, "MEMORY.md", am_dir=self.dir,
        )
        self.assertEqual(res["action"], "skip")
        self.assertIn("non-auto-memory", res["reason"])


class TestWritebackEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_full_writeback_flips_and_stamps(self):
        (self.dir / "MEMORY.md").write_text(_candidate("cpr_demo_tic500"), encoding="utf-8")
        (self.dir / "feedback_demo.md").write_text("# feedback\n\nbody\n", encoding="utf-8")
        report = rpw.writeback(
            "cpr_demo_tic500", "feedback_demo.md", 510,
            status="promoted", search_dir=self.dir,
        )
        self.assertEqual(report["summary"]["inline_blocks_flipped"], 1)
        self.assertEqual(report["summary"]["breadcrumb_action"], "stamp")
        self.assertEqual(report["birth_tic"], 500)  # parsed from the id's tic suffix

    def test_dry_run_writes_nothing(self):
        mem = self.dir / "MEMORY.md"
        mem.write_text(_candidate("cpr_demo_tic500"), encoding="utf-8")
        before = mem.read_text(encoding="utf-8")
        rpw.writeback(
            "cpr_demo_tic500", "feedback_demo.md", 510,
            status="promoted", dry_run=True, search_dir=self.dir,
        )
        self.assertEqual(mem.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
