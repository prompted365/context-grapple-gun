#!/usr/bin/env python3
"""Fixtures for the two /review-775 review-close-check cures, ruled in one
Architect-ratified round (recommended verbatim, 4/4):

  A. MEASUREMENT-vs-OCCURRENCE content normalization (a5391802154e — ray on
     constitution-ledger#terminal-state-change-requires-receipt-and-no-signal-
     goes-dark): the skip-vs-replace change-discriminator compares fields
     carrying information FROM the measurement, never fields recording its
     OCCURRENCE. Lived t772: a content-empty supersession whose only deltas
     were genuine_zero_streak.row_count_within_streak 130->131,
     same_tic_reobservation_tics gaining '772', and queue_state_tuple.read_at.

  B. INDEX-CONSEQUENCE sub-typing of index_loss (3007b217a33d): a loud residue
     counter's non-zero is typed by its INDEX CONSEQUENCE —
     index_loss_comment_only (every token already in the index via another
     admitted comment; the witness COMMENT was shed, the ID was never missing)
     vs index_loss_id_absent (at least one token absent; a real hole). Lived
     t772: the consumer-carry note at cgg-ledger/ledger.md was typed a loss
     the index did not suffer.

Every documented conditional gets BOTH arms
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths).
SCOPE HONESTY: fixture-green over synthetic surfaces; the live fire is the
next review_close_check cycle.

Run:  python3 -m unittest test_review_close_check_content_norm_and_index_consequence_tic775
"""

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "review_close_check_775", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check_775"] = rcc
_spec.loader.exec_module(rcc)


# ---------------------------------------------------------------------------
# A. MEASUREMENT-vs-OCCURRENCE normalization (a5391802154e)
# ---------------------------------------------------------------------------

def _report(streak_rows=130, reobs=None, read_at="T0", genuine=0, sha="abc"):
    """A minimal report in the live artifact's shape — the t772 lived fields."""
    return {
        "generated_at": read_at,
        "summary": {"genuine_count": genuine, "known_count": 16},
        "verdict_counts": {"promoted": 818, "absorbed": 0, "skipped": 126},
        "genuine_zero_streak": {
            "unit": "distinct_check_bearing_tics",
            "distinct_check_bearing_tics": 87,
            "row_count_within_streak": streak_rows,
            "span": [681, 772],
            "gap_tics_no_check_row": [],
            "same_tic_reobservation_tics": dict(reobs or {}),
            "broken_at_tic": None,
        },
        "queue_state_tuple": {
            "read_at": read_at, "sha256_16": sha, "raw_rows": 3060,
            "unique_ids": 1313, "promoted": 818,
        },
    }


class TestContentNormalization(unittest.TestCase):

    def test_the_t772_lived_shape_now_compares_equal(self):
        """NC-GREEN: the exact t772 delta set (streak row count +1, a same-tic
        re-observation entry, a fresh read_at) normalizes EQUAL — the re-run
        skips instead of minting a content-empty supersession. Reverting the
        cure (comparing raw dicts minus the two volatile keys) breaks this."""
        first = _report(streak_rows=130, reobs={}, read_at="T0")
        rerun = _report(streak_rows=131, reobs={"772": 2}, read_at="T1")
        self.assertNotEqual(  # RED reproduced inline: the old comparison fired
            {k: v for k, v in first.items() if k not in ("generated_at", "superseded_receipt")},
            {k: v for k, v in rerun.items() if k not in ("generated_at", "superseded_receipt")})
        self.assertEqual(
            rcc.normalize_report_for_content_compare(first),
            rcc.normalize_report_for_content_compare(rerun),
            "occurrence-recording fields must not manufacture a content change")

    def test_information_bearing_streak_fields_still_compare(self):
        """CONTROL (the other arm): a streak whose SPAN moved is a REAL content
        change — the normalization must not swallow measurement information."""
        first = _report()
        moved = _report()
        moved["genuine_zero_streak"]["span"] = [681, 773]
        moved["genuine_zero_streak"]["distinct_check_bearing_tics"] = 88
        self.assertNotEqual(
            rcc.normalize_report_for_content_compare(first),
            rcc.normalize_report_for_content_compare(moved))

    def test_queue_measurement_fields_still_compare(self):
        """CONTROL: a changed queue sha (the queue actually moved between the
        two observations) is measurement information and drives replace."""
        first = _report(sha="abc")
        moved = _report(sha="def")
        self.assertNotEqual(
            rcc.normalize_report_for_content_compare(first),
            rcc.normalize_report_for_content_compare(moved))

    def test_volatile_keys_still_excluded(self):
        """The pre-775 exclusions (generated_at, superseded_receipt) survive."""
        first = _report()
        rerun = _report()
        rerun["superseded_receipt"] = {"anything": True}
        self.assertEqual(
            rcc.normalize_report_for_content_compare(first),
            rcc.normalize_report_for_content_compare(rerun))


# ---------------------------------------------------------------------------
# B. INDEX-CONSEQUENCE sub-typing (3007b217a33d)
# ---------------------------------------------------------------------------

# An ADMITTED head-anchored inscription witness donating its token to the index.
ADMITTED = ("<!-- PROMOTE-AS-REFINEMENT promoted from "
            "cpr_mogul_review_close_check_1d0125de5ee3 at /review 771 -->")
# The t772 lived shed shape: a consumer-carry note whose head verb sits outside
# the inscription alternation (remedy_class vocabulary_gap) carrying the SAME token.
SHED_SAME_TOKEN = ("<!-- consumer-carry note from "
                   "cpr_mogul_review_close_check_1d0125de5ee3 (/review 772) -->")
# A shed comment whose token nothing ever admits.
SHED_ABSENT = ("<!-- consumer-carry note from "
               "cpr_mogul_review_close_check_feedbeef0000 (/review 772) -->")


class HermeticIndexCase(unittest.TestCase):
    """HOME sandboxed so real surfaces never leak into fixture counts
    (cgg-ledger#self-locating-artifact-test-isolation)."""

    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self._orig_expanduser = os.path.expanduser
        self._orig_home = Path.home
        home = self._home.name
        os.path.expanduser = (
            lambda p: p.replace("~", home, 1) if p.startswith("~") else p)
        Path.home = classmethod(lambda cls: Path(home))
        rcc.os.path.expanduser = os.path.expanduser

    def tearDown(self):
        os.path.expanduser = self._orig_expanduser
        rcc.os.path.expanduser = self._orig_expanduser
        Path.home = self._orig_home
        self._home.cleanup()

    def index(self, body):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(body, encoding="utf-8")
        diag = {}
        with redirect_stderr(io.StringIO()):
            inscribed = rcc.build_inscribed_index(
                str(root), queue_ids=None, diagnostics=diag)
        return inscribed, diag


class TestIndexConsequenceSubtype(HermeticIndexCase):

    def test_comment_only_when_token_admitted_elsewhere(self):
        """The t772 lived member: the shed comment's token IS in the index via
        another admitted comment — comment_only, ZERO index consequence."""
        inscribed, diag = self.index(ADMITTED + "\n\n" + SHED_SAME_TOKEN + "\n")
        self.assertIn("cpr_mogul_review_close_check_1d0125de5ee3", inscribed)
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["counts"]["index_loss"], 1)
        self.assertEqual(split["index_loss_subtype_counts"],
                         {"index_loss_comment_only": 1,
                          "index_loss_id_absent": 0})
        sample = split["samples_by_disposition"]["index_loss"][0]
        self.assertEqual(sample["index_consequence"], "index_loss_comment_only")

    def test_id_absent_when_no_admitting_comment_exists(self):
        """The other arm: nothing admits the token — a real hole, the
        population the /review-719 counter was minted for."""
        inscribed, diag = self.index(SHED_ABSENT + "\n")
        self.assertEqual(inscribed, set())
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["index_loss_subtype_counts"],
                         {"index_loss_comment_only": 0,
                          "index_loss_id_absent": 1})
        sample = split["samples_by_disposition"]["index_loss"][0]
        self.assertEqual(sample["index_consequence"], "index_loss_id_absent")

    def test_order_independence_shed_before_admitting(self):
        """The sub-typing runs POST-WALK against the complete index: a shed
        comment appearing BEFORE the comment that admits its token still types
        comment_only (mid-walk membership would have mis-typed it)."""
        inscribed, diag = self.index(SHED_SAME_TOKEN + "\n\n" + ADMITTED + "\n")
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["index_loss_subtype_counts"],
                         {"index_loss_comment_only": 1,
                          "index_loss_id_absent": 0})

    def test_partial_presence_types_id_absent(self):
        """A shed comment carrying one admitted token AND one absent token is
        id_absent — a missing token IS a hole (the ruling's partial clause)."""
        shed_two = ("<!-- consumer-carry note from "
                    "cpr_mogul_review_close_check_1d0125de5ee3 and "
                    "cpr_mogul_review_close_check_feedbeef0000 (/review 772) -->")
        inscribed, diag = self.index(ADMITTED + "\n\n" + shed_two + "\n")
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["index_loss_subtype_counts"],
                         {"index_loss_comment_only": 0,
                          "index_loss_id_absent": 1})

    def test_headline_counter_stays_loud_in_both_subtypes(self):
        """The ruling changes what the number MEANS, never whether it sounds:
        both subtypes remain in the loud headline count."""
        inscribed, diag = self.index(
            ADMITTED + "\n\n" + SHED_SAME_TOKEN + "\n\n" + SHED_ABSENT + "\n")
        split = diag["unmatched_disposition_split"]
        self.assertEqual(split["counts"]["index_loss"], 2)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 2)
        self.assertEqual(split["index_loss_subtype_counts"],
                         {"index_loss_comment_only": 1,
                          "index_loss_id_absent": 1})


if __name__ == "__main__":
    unittest.main()
