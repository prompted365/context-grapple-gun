#!/usr/bin/env python3
"""Tests for the LAYOUT-CHURN discriminator on the sibling-pair attribution
(the minimum cure for cpr_mogul_review_close_check_3823e2916dd9, b758 → /review 761 —
minted by the close-fire citizen on the instrument's own tic-758 close artifact).

The contract under guard: the matched-comment identity is
`relative_path#occurrence_index#sha256_12_of_comment_segment` — it carries a
POSITION. Inserting a comment mid-file re-identifies every later comment in that
file, so the positional set difference reports layout churn as membership
movement (tic 758: 237 new / 234 removed where the true movement was +3/−0; the
headline scalar survived because insertion preserves count parity among the
churned members). The cure intersects the two sides of the difference on the
identity's CONTENT-BEARING component BEFORE any member-level claim, publishes the
churn count, re-derives the enumeration over the content component, and
reconciles the attribution block's unit declaration with membership_sets'.

Arms (all mandatory):
  (a) a mid-file insertion: positional new/removed are large and equal-ish, the
      scalar delta_by_membership == +1, layout_churn.members == the number of
      shifted comments, content_new == [the inserted comment], content_removed == [];
  (b) a true removal + a true addition with no shift: churn 0, content lists ==
      positional lists (content-projected), scalars agree;
  (c) the block's `unit` equals MATCHED_COMMENT_ID_UNIT (the same-run EMITTER tell
      reconciled) and the positional lists are still published beside a note;
  (d) byte-identical segments in one file collapse in the content component and the
      collapse is COUNTED (content_collapse), never hidden.

Run: python3 -m pytest -q cgg-runtime/scripts/test_review_close_check_layout_churn_tic758.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("rcc_mod", HERE / "review-close-check.py")
rcc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rcc)


def _prior(report_dir: Path, tic: int, ids: list[str]):
    art = {"membership_sets": {"matched_comment_ids": ids, "matched_comment_id_unit": rcc.MATCHED_COMMENT_ID_UNIT}}
    (report_dir / f"tic-{tic}-check.json").write_text(json.dumps(art), encoding="utf-8")


def _ids(path: str, shas: list[str]) -> list[str]:
    return [f"{path}#{i}#{s}" for i, s in enumerate(shas)]


def _run(prior_ids, current_ids):
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _prior(d, 757, prior_ids)
        return rcc.compute_sibling_pair_attribution(str(d), "tic-758-check.json", 758, current_ids)


def test_a_mid_file_insertion_is_churn_not_movement():
    shas = [f"{i:012x}" for i in range(1, 8)]          # 7 comments, distinct content
    prior = _ids("ledger.md", shas)
    inserted = "aaaaaaaaaaaa"
    current = _ids("ledger.md", shas[:3] + [inserted] + shas[3:])  # insert after the third → 4 shift
    b = _run(prior, current)
    assert b["attribution_unresolved"] is False
    assert b["delta_by_membership"] == 1
    assert len(b["new_matched_comments"]) == 5 and len(b["removed_matched_comments"]) == 4   # positional
    assert b["layout_churn"]["members"] == 4
    assert b["content_new_matched_comments"] == [f"ledger.md#{inserted}"]
    assert b["content_removed_matched_comments"] == []
    assert b["delta_by_content_membership"] == 1


def test_b_true_movement_without_shift_has_zero_churn():
    prior = _ids("a.md", ["111111111111", "222222222222"]) + _ids("b.md", ["333333333333"])
    current = _ids("a.md", ["111111111111", "222222222222"]) + _ids("b.md", ["444444444444"])  # b.md#0 replaced
    b = _run(prior, current)
    assert b["layout_churn"]["members"] == 0
    assert b["content_new_matched_comments"] == ["b.md#444444444444"]
    assert b["content_removed_matched_comments"] == ["b.md#333333333333"]
    assert b["delta_by_membership"] == b["delta_by_content_membership"] == 0


def test_c_unit_reconciled_and_positional_lists_kept():
    prior = _ids("x.md", ["111111111111"])
    current = _ids("x.md", ["111111111111", "222222222222"])
    b = _run(prior, current)
    assert b["unit"] == rcc.MATCHED_COMMENT_ID_UNIT
    assert "occurrence_index" in b["unit"]
    assert b["new_matched_comments"] == ["x.md#1#222222222222"]
    assert "positional_difference_note" in b


def test_d_identical_segments_collapse_is_counted():
    prior = _ids("y.md", ["111111111111"])
    # two byte-identical new segments in one file: positional ids differ, content component collapses
    current = _ids("y.md", ["111111111111", "222222222222", "222222222222"])
    b = _run(prior, current)
    assert len(b["new_matched_comments"]) == 2
    assert b["content_new_matched_comments"] == ["y.md#222222222222"]
    assert b["layout_churn"]["content_collapse"] == 1
    assert b["delta_by_membership"] == 2 and b["delta_by_content_membership"] == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
