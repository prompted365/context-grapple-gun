#!/usr/bin/env python3
"""Patch E fixture tests — tiered cpr-extract schema widening (tic 188).

Validates the tier classification + extraction contract:
  Tier 1 — canonical (status=pending + lesson + source)
  Tier 2 — title+evidence (status pending OR absent + title + evidence)
  Tier 3 — lesson-only (status=pending + lesson, no source, no title+evidence)

Hard constraints:
  - no-status + lesson-only is NOT extractable
  - missing fields are not permission to invent source, scope, or evidence
  - terminal duplicates skipped
  - explicit ids preserved through any tier

Run as a script: python3 test_cpr_extract_patch_e.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Load cpr-extract.py with hyphenated filename via importlib
SCRIPT_DIR = Path(__file__).parent.parent / "cgg-runtime" / "scripts"
EXTRACT_PATH = SCRIPT_DIR / "cpr-extract.py"

# Add scripts dir to sys.path for zone_root + lib imports
sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location("cpr_extract", str(EXTRACT_PATH))
cpr_extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cpr_extract)


def _make_zone(tmpdir):
    """Set up a minimal CGG-zoned project tree under tmpdir."""
    p = Path(tmpdir)
    (p / "audit-logs" / "cprs").mkdir(parents=True, exist_ok=True)
    (p / "audit-logs" / "tics").mkdir(parents=True, exist_ok=True)
    # .ticzone marker file (resolve_zone_root looks for this or audit-logs/)
    (p / ".ticzone").write_text("rung: site\nname: test_zone\n")
    return p


def _write_memory(p, blocks_text):
    """Write a MEMORY.md-equivalent file with the given block text."""
    mem_path = p / "MEMORY.md"
    mem_path.write_text(blocks_text)
    return mem_path


class PatchETierClassification(unittest.TestCase):
    """Direct unit tests for _classify_tier without filesystem."""

    def test_tier1_canonical(self):
        block = {"status": "pending", "lesson": "L", "source": "S"}
        self.assertEqual(cpr_extract._classify_tier(block, "pending"), "tier1")

    def test_tier1_with_explicit_id(self):
        block = {"status": "pending", "lesson": "L", "source": "S", "id": "CogPR-X"}
        self.assertEqual(cpr_extract._classify_tier(block, "pending"), "tier1")

    def test_tier2_pending_with_title_evidence_no_lesson(self):
        block = {"status": "pending", "title": "T", "evidence": "E"}
        self.assertEqual(cpr_extract._classify_tier(block, "pending"), "tier2")

    def test_tier2_no_status_with_title_evidence(self):
        block = {"title": "T", "evidence": "E"}
        self.assertEqual(cpr_extract._classify_tier(block, ""), "tier2")

    def test_tier2_pending_with_title_evidence_and_lesson_no_source(self):
        # Title+evidence wins when source missing (else this is tier3)
        block = {"status": "pending", "title": "T", "evidence": "E", "lesson": "L"}
        self.assertEqual(cpr_extract._classify_tier(block, "pending"), "tier2")

    def test_tier3_lesson_only(self):
        block = {"status": "pending", "lesson": "L"}
        self.assertEqual(cpr_extract._classify_tier(block, "pending"), "tier3")

    def test_skip_no_status_lesson_only(self):
        # CRITICAL: no-status + lesson-only must NOT be extractable
        block = {"lesson": "L"}
        self.assertEqual(cpr_extract._classify_tier(block, ""), "skip_no_status")

    def test_skip_status_not_pending(self):
        block = {"status": "promoted", "lesson": "L", "source": "S"}
        self.assertEqual(cpr_extract._classify_tier(block, "promoted"), "skip_status")

    def test_skip_pending_no_extractable_shape(self):
        block = {"status": "pending"}
        self.assertEqual(cpr_extract._classify_tier(block, "pending"), "skip_schema_incomplete")


class PatchEFullExtraction(unittest.TestCase):
    """End-to-end fixture tests via extract_cprs()."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="patch_e_test_")
        self.zone = _make_zone(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _extract(self, dry_run=False):
        return cpr_extract.extract_cprs(str(self.zone), dry_run=dry_run)

    def test_tier1_source_lesson_canonical(self):
        block = """<!-- --agnostic-candidate
status: pending
band: COGNITIVE
source: "test-source-tier1"
lesson: "Tier 1 canonical lesson body."
-->
"""
        _write_memory(self.zone, block)
        entries, counters = self._extract(dry_run=True)
        self.assertEqual(counters["blocks_found"], 1)
        self.assertEqual(counters["blocks_extracted"], 1)
        self.assertEqual(counters["extracted_canonical"], 1)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["status"], "extracted")
        self.assertEqual(e["tier"], "tier1")
        self.assertEqual(e["lesson"], "Tier 1 canonical lesson body.")
        self.assertEqual(e["source"], "test-source-tier1")
        self.assertNotIn("pending_class", e)
        self.assertNotIn("no_evidence_reason", e)

    def test_tier1_explicit_id_preserved(self):
        block = """<!-- --agnostic-candidate
id: CogPR-EXPLICIT-188
status: pending
band: COGNITIVE
source: "test-source-explicit"
lesson: "Tier 1 with explicit id."
-->
"""
        _write_memory(self.zone, block)
        entries, counters = self._extract(dry_run=True)
        self.assertEqual(counters["explicit_id_preserved"], 1)
        self.assertEqual(entries[0]["id"], "CogPR-EXPLICIT-188")
        self.assertEqual(entries[0]["id_origin"], "explicit")

    def test_tier2_title_evidence_no_lesson(self):
        block = """<!-- --agnostic-candidate
status: pending
band: COGNITIVE
title: "Tier 2 candidate title"
evidence: "Tier 2 candidate evidence body."
-->
"""
        _write_memory(self.zone, block)
        entries, counters = self._extract(dry_run=True)
        self.assertEqual(counters["extracted_title_evidence"], 1)
        e = entries[0]
        self.assertEqual(e["tier"], "tier2")
        self.assertEqual(e["status"], "enrichment_needed")
        self.assertEqual(e["pending_class"], "evidence_scoped")
        self.assertEqual(e["title"], "Tier 2 candidate title")
        self.assertEqual(e["evidence"], "Tier 2 candidate evidence body.")
        # lesson := title when missing
        self.assertEqual(e["lesson"], "Tier 2 candidate title")
        # source := block locator when missing (no source in block)
        self.assertIn("MEMORY.md:", e["source"])
        self.assertEqual(e["confidence_tier"], "tentative")

    def test_tier3_lesson_only_pending(self):
        block = """<!-- --agnostic-candidate
status: pending
band: COGNITIVE
lesson: "Tier 3 lesson-only body, no source given."
-->
"""
        _write_memory(self.zone, block)
        entries, counters = self._extract(dry_run=True)
        self.assertEqual(counters["extracted_lesson_only"], 1)
        e = entries[0]
        self.assertEqual(e["tier"], "tier3")
        self.assertEqual(e["status"], "enrichment_needed")
        self.assertEqual(e["pending_class"], "schema_incomplete")
        self.assertEqual(e["no_evidence_reason"], "lesson_only_candidate_requires_enrichment")
        self.assertIn("MEMORY.md:", e["source"])
        self.assertEqual(e["confidence_tier"], "tentative")
        # Tier 3 must NOT infer recommended_scopes
        self.assertEqual(e["recommended_scopes"], [])

    def test_no_status_lesson_only_skipped(self):
        """CRITICAL: lesson-only without explicit status must NOT extract."""
        block = """<!-- --agnostic-candidate
band: COGNITIVE
lesson: "Lesson with no status — must be skipped."
-->
"""
        _write_memory(self.zone, block)
        entries, counters = self._extract(dry_run=True)
        self.assertEqual(counters["blocks_found"], 1)
        self.assertEqual(counters["blocks_extracted"], 0)
        self.assertEqual(counters["skipped_no_status"], 1)
        self.assertEqual(len(entries), 0)

    def test_terminal_duplicate_skipped(self):
        """Block with explicit id matching a terminal queue row must skip."""
        # Pre-populate queue with a terminal row for id CogPR-TERMINAL-T1
        queue_path = self.zone / "audit-logs" / "cprs" / "queue.jsonl"
        queue_path.write_text(
            json.dumps({"id": "CogPR-TERMINAL-T1", "status": "promoted", "dedup_hash": "deadbeef00000000"}) + "\n"
        )
        block = """<!-- --agnostic-candidate
id: CogPR-TERMINAL-T1
status: pending
band: COGNITIVE
source: "test-source-different-from-original"
lesson: "Re-extraction attempt for already-terminal id."
-->
"""
        _write_memory(self.zone, block)
        entries, counters = self._extract(dry_run=True)
        self.assertEqual(counters["blocks_found"], 1)
        self.assertEqual(counters["blocks_extracted"], 0)
        self.assertEqual(counters["terminal_duplicate_skipped"], 1)

    def test_no_fabricated_evidence(self):
        """Tier 3 must not fabricate evidence/title fields, and source != external invention."""
        block = """<!-- --agnostic-candidate
status: pending
band: COGNITIVE
lesson: "Lesson-only with no source, no title, no evidence."
-->
"""
        _write_memory(self.zone, block)
        entries, counters = self._extract(dry_run=True)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        # Source must be block locator, not invented string
        self.assertIn("MEMORY.md:", e["source"])
        self.assertNotIn("title", e)  # no title field for tier3
        self.assertNotIn("evidence", e)  # no evidence field for tier3
        # recommended_scopes must remain empty (never inferred)
        self.assertEqual(e["recommended_scopes"], [])
        # rationale must remain whatever was in block (empty here)
        self.assertEqual(e["rationale"], "")

    def test_status_not_pending_skipped(self):
        block = """<!-- --agnostic-candidate
status: promoted
band: COGNITIVE
source: "test-source"
lesson: "Already promoted lesson."
-->
"""
        _write_memory(self.zone, block)
        entries, counters = self._extract(dry_run=True)
        self.assertEqual(counters["skipped_status_not_pending"], 1)
        self.assertEqual(len(entries), 0)

    def test_pending_no_extractable_shape_skipped(self):
        block = """<!-- --agnostic-candidate
status: pending
band: COGNITIVE
-->
"""
        _write_memory(self.zone, block)
        entries, counters = self._extract(dry_run=True)
        self.assertEqual(counters["skipped_schema_incomplete"], 1)
        self.assertEqual(len(entries), 0)

    def test_dedup_hash_skip(self):
        """Same source:lesson hash must not extract twice."""
        block = """<!-- --agnostic-candidate
status: pending
band: COGNITIVE
source: "test-source-dup"
lesson: "Dedup target lesson."
-->
"""
        _write_memory(self.zone, block + block)  # write twice
        entries, counters = self._extract(dry_run=True)
        self.assertEqual(counters["blocks_found"], 2)
        self.assertEqual(counters["blocks_extracted"], 1)
        self.assertEqual(counters["skipped_dedup_hash_match"], 1)


class BlockScalarParsing(unittest.TestCase):
    """Direct parse_cpr_block tests for YAML block-scalar handling (tic 484).

    Bug: parse_cpr_block handled only the exact literal `|` and had no folded
    `>` branch, so `lesson: >` stored the bare ">" indicator and discarded the
    body. Fix: detect block-scalar headers generally, fold `>` (newlines→spaces,
    blank lines→newline), preserve `|` (newlines verbatim).
    """

    def test_folded_joins_lines_with_space(self):
        block = (
            "status: pending\n"
            "lesson: >\n"
            "  First folded line\n"
            "  second folded line\n"
        )
        out = cpr_extract.parse_cpr_block(block)
        self.assertEqual(out["lesson"], "First folded line second folded line")
        self.assertNotEqual(out["lesson"], ">")

    def test_folded_blank_line_is_paragraph_break(self):
        block = (
            "lesson: >\n"
            "  Para one line one\n"
            "  para one line two\n"
            "\n"
            "  Para two\n"
        )
        out = cpr_extract.parse_cpr_block(block)
        self.assertEqual(
            out["lesson"],
            "Para one line one para one line two\nPara two",
        )

    def test_folded_with_chomping_indicator(self):
        # `>-` is a valid folded header (strip chomping) — must still fold
        block = "lesson: >-\n  alpha\n  beta\n"
        out = cpr_extract.parse_cpr_block(block)
        self.assertEqual(out["lesson"], "alpha beta")

    def test_literal_preserves_newlines_regression(self):
        # tic 207 behavior must be preserved by the tic 484 generalization
        block = "lesson: |\n  line A\n  line B\n"
        out = cpr_extract.parse_cpr_block(block)
        self.assertEqual(out["lesson"], "line A\nline B")

    def test_plain_scalar_with_gt_is_not_block_scalar(self):
        # a value that merely CONTAINS `>` (`x > y`) is a plain scalar, not a header
        block = "threshold: x > y\nstatus: pending\n"
        out = cpr_extract.parse_cpr_block(block)
        self.assertEqual(out["threshold"], "x > y")
        self.assertEqual(out["status"], "pending")

    def test_folded_header_with_no_body_is_empty(self):
        # `>` followed immediately by a dedented key collects no body → empty
        # (routes to skip_schema_incomplete downstream, not to the verifier)
        block = "lesson: >\nstatus: pending\n"
        out = cpr_extract.parse_cpr_block(block)
        self.assertEqual(out["lesson"], "")
        self.assertEqual(out["status"], "pending")


class BlockScalarExtraction(unittest.TestCase):
    """End-to-end extraction tests for the block-scalar fold fix (tic 484)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="block_scalar_test_")
        self.zone = _make_zone(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _extract(self, dry_run=True):
        return cpr_extract.extract_cprs(str(self.zone), dry_run=dry_run)

    def test_folded_born_extracts_real_body_not_indicator(self):
        # REGRESSION (tic 484): the cpr_hop_receipt_chain_outcome_mapping_tic371
        # shape — a folded `lesson: >` born — must extract its real body, never
        # the bare ">" indicator.
        block = """<!-- --agnostic-candidate
id: cpr_repro_folded_tic371
status: pending
source: "session_lessons_tic_372.md"
lesson: >
  hop receipt chain outcome mapping —
  folded multi-line body that must NOT
  collapse to a bare indicator.
-->
"""
        _write_memory(self.zone, block)
        entries, counters = self._extract()
        self.assertEqual(counters["blocks_extracted"], 1)
        self.assertEqual(counters["skipped_block_scalar_bare_indicator"], 0)
        e = entries[0]
        self.assertEqual(e["id"], "cpr_repro_folded_tic371")
        self.assertEqual(e["tier"], "tier1")
        self.assertEqual(
            e["lesson"],
            "hop receipt chain outcome mapping — folded multi-line body "
            "that must NOT collapse to a bare indicator.",
        )
        self.assertNotEqual(e["lesson"], ">")

    def test_quoted_bare_indicator_lesson_is_verifier_skipped(self):
        # The quoted-indicator authoring path (`lesson: ">"`) bypasses the
        # block-scalar branch (quotes), so the verifier must catch it: refuse
        # the malformed content-empty row and count the skip.
        block = """<!-- --agnostic-candidate
id: cpr_malformed_quoted_indicator
status: pending
source: "src"
lesson: ">"
-->
"""
        _write_memory(self.zone, block)
        entries, counters = self._extract()
        self.assertEqual(counters["blocks_found"], 1)
        self.assertEqual(counters["blocks_extracted"], 0)
        self.assertEqual(counters["skipped_block_scalar_bare_indicator"], 1)
        self.assertEqual(len(entries), 0)


def main():
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
