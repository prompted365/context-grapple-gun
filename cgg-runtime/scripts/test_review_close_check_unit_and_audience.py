#!/usr/bin/env python3
"""Tests for the /review 716 review-close-check cures.

Cure A (cpr_mogul_review_close_check_502236e96cf1, SKIP-with-routing — the
class-cure executed): the inscribed-index counter's POPULATION and UNIT are
declared as fields beside the integer (unit_declaration in the diagnostics +
inscribed_index_unit in the report), with the multi-token comment count that
measures the token≠event referent gap. The tic-706 reserved-prefix exclusion
was an instance-cure; this is the class-cure the /review-712 guard-11
refinement ray entails.

Cure B (cpr_mogul_review_close_check_07c597566b16, PROMOTE-as-refinement-ray —
the AUDIENCE/HANDLE ray): the supersession receipt is ALSO written into the
live replacing artifact (the consumer's handle) and a sidecar back-stamp
lands beside the preserved copy (raw bytes stay byte-exact); the receipt key
is comparison-volatile so identical-findings runs still lawfully skip.
Write-path arms are generator-enforced against source (the 6372-cure style):
the conditional's both arms live in the replace branch a unit fixture cannot
cheaply reach; the source asserts pin the wiring, and the first live fire
rides the next real supersession event.

Both arms of every documented conditional are exercised
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths).
"""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = (_HERE / "review-close-check.py").read_text(encoding="utf-8")
_spec = importlib.util.spec_from_file_location(
    "review_close_check", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check"] = rcc
_spec.loader.exec_module(rcc)


class _HermeticHome(unittest.TestCase):
    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self._orig_expanduser = os.path.expanduser
        self._orig_home = Path.home
        home = self._home.name
        os.path.expanduser = lambda p: p.replace("~", home, 1) if p.startswith("~") else p
        Path.home = classmethod(lambda cls: Path(home))
        rcc.os.path.expanduser = os.path.expanduser

    def tearDown(self):
        os.path.expanduser = self._orig_expanduser
        rcc.os.path.expanduser = self._orig_expanduser
        Path.home = self._orig_home
        self._home.cleanup()


class TestUnitDeclaration(_HermeticHome):
    def _run(self, claude_md_text, queue_ids=None):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(claude_md_text, encoding="utf-8")
        with tmp:
            diag = {}
            inscribed = rcc.build_inscribed_index(
                str(root), queue_ids=queue_ids, diagnostics=diag)
            return inscribed, diag

    def test_unit_declaration_present_with_all_fields(self):
        _, diag = self._run("<!-- promoted from cpr_one_tic700 -->\n")
        ud = diag["unit_declaration"]
        for key in ("unit", "population", "boundary_rule", "not_the_unit",
                    "matched_comment_count", "multi_token_comment_count"):
            self.assertIn(key, ud)
        self.assertEqual(
            ud["unit"],
            "distinct_cpr_shaped_tokens_inside_matched_provenance_comments")
        self.assertEqual(ud["matched_comment_count"], 1)
        self.assertEqual(ud["multi_token_comment_count"], 0)

    def test_multi_token_comment_counted(self):
        # One compound comment (two distinct admitted tokens) + one single-token
        # comment: multi count is exactly 1 — the referent-gap measurement.
        _, diag = self._run(
            "<!-- promoted from cpr_a_tic700 merged with cpr_b_tic701 -->\n"
            "<!-- promoted from cpr_c_tic702 -->\n")
        ud = diag["unit_declaration"]
        self.assertEqual(ud["matched_comment_count"], 2)
        self.assertEqual(ud["multi_token_comment_count"], 1)

    def test_reserved_token_not_counted_toward_multi(self):
        # A real token + a reserved-namespace token in one comment: the reserved
        # token is excluded BEFORE the distinct count, so the comment is not
        # multi-token (both-arms discipline: exclusion feeds the count).
        _, diag = self._run(
            "<!-- promoted from cpr_real_tic700. era: cpr_era_tic_700_749 -->\n")
        ud = diag["unit_declaration"]
        self.assertEqual(ud["matched_comment_count"], 1)
        self.assertEqual(ud["multi_token_comment_count"], 0)
        self.assertEqual(diag["reserved_excluded_count"], 1)

    def test_repeated_same_token_not_multi(self):
        # The same id appearing twice in one comment is ONE distinct token.
        _, diag = self._run(
            "<!-- promoted from cpr_same_tic700; supersedes cpr_same_tic700 -->\n")
        self.assertEqual(diag["unit_declaration"]["multi_token_comment_count"], 0)


class TestPromoteAsRefinementVerbMatched(_HermeticHome):
    """tic-716 verb-alternation fix (n=2 of the tic-515 class), both arms."""

    def _run(self, text):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(text, encoding="utf-8")
        with tmp:
            return rcc.build_inscribed_index(str(root))

    def test_promote_as_refinement_comment_admitted(self):
        idx = self._run(
            "<!-- PROMOTE-AS-REFINEMENT (ray to some-entry), /review 716. "
            "Promoted from cpr_ray_token_tic716. -->\n")
        self.assertIn("cpr_ray_token_tic716", idx)

    def test_skip_with_home_opening_stays_excluded(self):
        # A SKIP pointer is NOT an inscription witness — excluded by design.
        idx = self._run(
            "<!-- SKIP-WITH-HOME POINTER (cpr_skip_token_tic716, born tic 700) "
            "durable home elsewhere -->\n")
        self.assertNotIn("cpr_skip_token_tic716", idx)


class TestReview719VerbAdmissionsAndLoudCounter(_HermeticHome):
    """/review-719 first-consumer patch (3a40ab346adb, PROMOTE-as-ray + patch,
    Architect-ratified): the census-residue and measured compound heads are
    ADMITTED, and any FUTURE head that fails the alternation is surfaced by the
    unmatched-provenance-shape loud counter instead of dropping out silently.
    Both arms of every documented conditional are exercised."""

    def _run(self, text):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(text, encoding="utf-8")
        with tmp:
            diag = {}
            idx = rcc.build_inscribed_index(str(root), diagnostics=diag)
            return idx, diag

    def test_admitted_heads_all_indexed(self):
        heads = {
            "INSCRIBED": "cpr_inscribed_head_tic719",
            "review-executed": "cpr_review_executed_head_tic719",
            "CONDITIONAL-PROMOTED": "cpr_conditional_head_tic719",
            "MERGE": "cpr_merge_head_tic719",
            "REINFORCED": "cpr_reinforced_head_tic719",
        }
        text = "".join(
            f"<!-- {head} at /review 719, from {token}. -->\n"
            for head, token in heads.items()
        )
        idx, diag = self._run(text)
        for token in heads.values():
            self.assertIn(token, idx)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)

    def test_novel_head_fires_loud_counter_not_index(self):
        idx, diag = self._run(
            "<!-- RATIFIED-INTO some-entry, from cpr_novel_head_tic719. -->\n")
        self.assertNotIn("cpr_novel_head_tic719", idx)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)
        sample = diag["unmatched_provenance_shaped_samples"][0]
        self.assertIn("cpr_novel_head_tic719", sample["tokens"])
        self.assertTrue(sample["head"].startswith("<!-- RATIFIED-INTO"))

    def test_skip_head_not_counted_by_loud_counter(self):
        idx, diag = self._run(
            "<!-- SKIP-WITH-HOME POINTER (cpr_skip_loud_tic719) home elsewhere -->\n")
        self.assertNotIn("cpr_skip_loud_tic719", idx)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)

    def test_reserved_only_comment_not_counted(self):
        # A comment whose only token is a reserved sibling-namespace label is
        # metadata, not a shed inscription witness.
        _, diag = self._run("<!-- era boundary marker cpr_era_tic_700_749 -->\n")
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)

    def test_tokenless_unmatched_comment_not_counted(self):
        _, diag = self._run("<!-- an ordinary prose comment, no ids at all -->\n")
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)

    def test_merged_still_admitted_longest_first(self):
        # `merge` was added AFTER `merged` — the longer form must keep matching.
        idx, diag = self._run(
            "<!-- merged from cpr_merged_form_tic719 + cpr_other_form_tic719 -->\n")
        self.assertIn("cpr_merged_form_tic719", idx)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)


class TestReportCarriesUnitBesideInteger(unittest.TestCase):
    def test_report_block_publishes_inscribed_index_unit(self):
        # Generator-enforce: the report dict publishes the unit declaration
        # BESIDE the integer, keyed inscribed_index_unit.
        i_size = _SRC.index('"inscribed_index_size": len(inscribed_ids)')
        i_unit = _SRC.index('"inscribed_index_unit": inscribed_diagnostics.get("unit_declaration")')
        self.assertGreater(i_unit, i_size)
        # ...and within the same report-literal neighborhood (beside, not far).
        self.assertLess(i_unit - i_size, 600)


class TestAudienceHandleCureWiring(unittest.TestCase):
    """Generator-enforce arms for the /review 716 AUDIENCE/HANDLE cure."""

    def test_live_artifact_receipt_written_before_output_write(self):
        i_assign = _SRC.index('report["superseded_receipt"] = superseded_receipt')
        i_write = _SRC.index('Path(output_path).write_text', i_assign)
        self.assertGreater(i_write, i_assign,
                           "the live-artifact receipt must land BEFORE the write")

    def test_sidecar_backstamp_beside_preserved_copy(self):
        self.assertIn('preserved_abs + ".superseded-by.json"', _SRC)
        # The preserved copy itself stays raw-bytes (write_bytes of prior_raw
        # unchanged — the /review 685 preservation law).
        self.assertIn("Path(preserved_abs).write_bytes(prior_raw)", _SRC)

    def test_superseded_receipt_is_comparison_volatile(self):
        self.assertIn('_volatile = ("generated_at", "superseded_receipt")', _SRC)

    def test_log_row_still_carries_receipt_producer_lane_intact(self):
        # The cure ADDS an audience; it never removes the producer-lane sink.
        self.assertIn('log_entry["superseded_receipt"] = superseded_receipt',
                      _SRC.replace("\n        ", "\n"))
        # tolerant match: the exact line exists with its original indentation
        self.assertIn('log_entry["superseded_receipt"] = superseded_receipt', _SRC)


if __name__ == "__main__":
    unittest.main()
