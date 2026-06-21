#!/usr/bin/env python3
"""Tests for review-promote-writeback.py — the emit-side writeback (inline status
flip + auto-memory breadcrumb stamp). Closes the no-coverage gap (bk-emitter-review-wiring).

The module name is hyphenated, so it loads via importlib spec_from_file_location.
Every case isolates against a TemporaryDirectory through the script's search-dir /
am-dir test hooks — nothing touches the real auto-memory dir.

Run:  python3 -m unittest test_review_promote_writeback   (from cgg-runtime/scripts/)
"""
import importlib.util
import json
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


def _candidate(cpr_id, status="pending", lesson="a durable lesson", source="handoff"):
    return (
        "# Topic\n\nsome prose\n\n"
        "<!-- --agnostic-candidate\n"
        f"  id: {cpr_id}\n"
        f"  status: {status}\n"
        f'  lesson: "{lesson}"\n'
        f'  source: "{source}"\n'
        "-->\n\ntrailing prose\n"
    )


def _candidate_no_id(status="pending", lesson="a durable lesson", source="handoff"):
    """An inline block with NO `id:` line — the realistic shape behind a hash-derived
    queue id (cpr-extract mints `cpr_<dedup_hash>` precisely when no explicit id is
    present). Resolvable ONLY by the content-identity bridge."""
    return (
        "# Topic\n\nsome prose\n\n"
        "<!-- --agnostic-candidate\n"
        f"  status: {status}\n"
        f'  lesson: "{lesson}"\n'
        f'  source: "{source}"\n'
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


class TestNonTerminalAdvance(unittest.TestCase):
    """The flip advances ANY non-terminal status, not just `pending` — the self-demo
    facet (cpr_self_operation_signal_discipline_tic350 sat at `enrichment_eligible`
    despite being promoted at /review 373; the old `!= pending` guard no-op'd it)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_enrichment_eligible_advances_to_promoted(self):
        f = self.dir / "MEMORY.md"
        f.write_text(_candidate("cpr_demo_tic500", status="enrichment_eligible"),
                     encoding="utf-8")
        actions = rpw.flip_inline_status(
            "cpr_demo_tic500", "promoted", 510, "feedback_demo.md", search_dir=self.dir)
        self.assertEqual(sum(a["action"] == "flip" for a in actions), 1)
        text = f.read_text(encoding="utf-8")
        self.assertIn("status: promoted", text)
        self.assertNotIn("status: enrichment_eligible", text)

    def test_each_non_terminal_state_advances(self):
        for st in ("pending", "extracted", "enrichment_needed",
                   "enrichment_eligible", "promotable"):
            with self.subTest(state=st):
                d = Path(self.tmp.name) / st
                d.mkdir()
                (d / "MEMORY.md").write_text(
                    _candidate("cpr_demo_tic500", status=st), encoding="utf-8")
                actions = rpw.flip_inline_status(
                    "cpr_demo_tic500", "promoted", 510, "feedback_demo.md", search_dir=d)
                self.assertEqual(sum(a["action"] == "flip" for a in actions), 1)


class TestResolvePromotionIdSet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_harvests_dedup_hash_and_alias_across_rows(self):
        q = self.dir / "queue.jsonl"
        h = rpw._compute_dedup_hash("handoff", "a durable lesson")
        rows = [
            {"id": "cpr_x_tic1", "dedup_hash": h, "status": "extracted",
             "memory_md_aliases": [{"alias_id": "CogPR-99"}],
             "extracted_from_inline": "cpr_old_form_tic1"},
            {"id": "cpr_x_tic1", "status": "promoted", "review_tic": 5},
            {"id": "cpr_other", "dedup_hash": "deadbeefdeadbeef"},  # ignored
        ]
        q.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        id_set, dedup = rpw.resolve_promotion_id_set("cpr_x_tic1", queue_path=q)
        self.assertEqual(dedup, h)
        self.assertIn("cpr_x_tic1", id_set)
        self.assertIn(f"cpr_{h}", id_set)
        self.assertIn("CogPR-99", id_set)
        self.assertIn("cpr_old_form_tic1", id_set)
        self.assertNotIn("deadbeefdeadbeef", id_set)

    def test_hash_form_id_yields_dedup_even_without_queue(self):
        # a `cpr_<16hex>` id carries its own dedup_hash; resolution works queue-absent
        id_set, dedup = rpw.resolve_promotion_id_set(
            "cpr_b3b60803db923870", queue_path=self.dir / "absent.jsonl")
        self.assertEqual(dedup, "b3b60803db923870")
        self.assertEqual(id_set, {"cpr_b3b60803db923870"})


class TestIdFormDivergence(unittest.TestCase):
    """The headline fix: queue carries a hash-id while the born inline block declares a
    DIFFERENT (long-form) id or NO id. The single-key match silently no-op'd; the id-set
    + content-identity bridge resolves it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.am = self.dir / "memory"
        self.am.mkdir()
        self.addCleanup(self.tmp.cleanup)

    def _queue(self, hash_id, dedup_hash):
        q = self.dir / "queue.jsonl"
        q.write_text(
            json.dumps({"id": hash_id, "dedup_hash": dedup_hash,
                        "status": "promoted", "review_tic": 481}) + "\n",
            encoding="utf-8")
        return q

    def test_hash_queue_id_vs_longform_block_id_bridged(self):
        # inline block declares the long-form id; queue carries the hash-id
        (self.am / "MEMORY.md").write_text(
            _candidate("cpr_primary_tool_x_tic475"), encoding="utf-8")
        (self.am / "feedback_x.md").write_text("# fb\n\nbody\n", encoding="utf-8")
        h = rpw._compute_dedup_hash("handoff", "a durable lesson")
        q = self._queue(f"cpr_{h}", h)
        report = rpw.writeback(
            f"cpr_{h}", "feedback_x.md", 481,
            status="promoted", search_dir=self.am, queue_path=q)
        self.assertEqual(report["summary"]["inline_blocks_flipped"], 1)
        self.assertTrue(report["summary"]["id_divergence_bridged"])
        self.assertEqual(report["resolution"]["matched_by_content_hash"], 1)
        self.assertTrue(report["summary"]["post_assert_flipped_eq_expected"])
        text = (self.am / "MEMORY.md").read_text(encoding="utf-8")
        self.assertIn("status: promoted", text)
        self.assertNotIn("status: pending", text)

    def test_idless_block_bridged_by_content_hash(self):
        (self.am / "MEMORY.md").write_text(_candidate_no_id(), encoding="utf-8")
        h = rpw._compute_dedup_hash("handoff", "a durable lesson")
        q = self._queue(f"cpr_{h}", h)
        report = rpw.writeback(
            f"cpr_{h}", "ledger.md#anchor", 481,  # ledger target → breadcrumb skip
            status="promoted", search_dir=self.am, queue_path=q)
        self.assertEqual(report["summary"]["inline_blocks_flipped"], 1)
        self.assertEqual(report["resolution"]["matched_by_content_hash"], 1)

    def test_no_match_reports_zero_not_crash(self):
        # a genuinely-absent inline block: 0 flips, post-assert holds, no crash
        (self.am / "MEMORY.md").write_text(
            _candidate("cpr_unrelated_tic1"), encoding="utf-8")
        q = self._queue("cpr_aaaaaaaaaaaaaaaa", "aaaaaaaaaaaaaaaa")
        report = rpw.writeback(
            "cpr_aaaaaaaaaaaaaaaa", "feedback_x.md", 481,
            status="promoted", search_dir=self.am, queue_path=q)
        self.assertEqual(report["summary"]["inline_blocks_flipped"], 0)
        self.assertEqual(report["resolution"]["blocks_matched"], 0)
        self.assertTrue(report["summary"]["post_assert_flipped_eq_expected"])


if __name__ == "__main__":
    unittest.main()
