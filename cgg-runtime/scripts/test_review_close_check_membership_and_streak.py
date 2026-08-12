#!/usr/bin/env python3
"""Tests for the /review 709 review-close-check cures.

Cure 1 (cpr_mogul_review_close_check_f94b63ce931d): membership resolution at
BOTH _CPR_REF_RE consumer sites (A5-707 both-sites constraint) — reserved
sibling-prefix tokens excluded + reported; queue-unresolved id-shaped tokens
admitted-but-disclosed.

Cure 2 (cpr_mogul_review_close_check_ad00d4c652c8): the genuine-zero streak is
computed by the log-row writer, in exactly its declared unit
(distinct_check_bearing_tics), gaps + same-tic re-observations disclosed.
Both arms of every documented conditional are exercised
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths).
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "review_close_check", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check"] = rcc
_spec.loader.exec_module(rcc)


class TestReservedRefExclusion(unittest.TestCase):
    def setUp(self):
        # Hermetic: build_inscribed_index also sweeps ~/.claude/CLAUDE.md and the
        # auto-memory dir — point "home" into the sandbox so real surfaces never
        # leak into the fixture's counts.
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

    def _mkproject(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(
            "# root\n"
            "<!-- promoted from cpr_real_lesson_tic700 (queue-resident). "
            "era: cpr_era_tic_700_749 -->\n"
            "<!-- promoted from cpr_legacy_never_queued_tic12 -->\n",
            encoding="utf-8",
        )
        return tmp, root

    def test_reserved_token_excluded_and_reported(self):
        tmp, root = self._mkproject()
        with tmp:
            diag = {}
            inscribed = rcc.build_inscribed_index(
                str(root),
                queue_ids={"cpr_real_lesson_tic700"},
                diagnostics=diag,
            )
            # the era label never enters the counted set
            self.assertNotIn("cpr_era_tic_700_749", inscribed)
            # ...and is REPORTED, never silently dropped
            self.assertIn("cpr_era_tic_700_749", diag["reserved_tokens_excluded"])
            self.assertEqual(diag["reserved_excluded_count"], 1)
            # the genuine queue-resident id is admitted
            self.assertIn("cpr_real_lesson_tic700", inscribed)
            # the legacy id fails queue membership: admitted (no historical flip)
            # but DISCLOSED
            self.assertIn("cpr_legacy_never_queued_tic12", inscribed)
            self.assertEqual(diag["unresolved_against_queue_count"], 1)
            self.assertIn(
                "cpr_legacy_never_queued_tic12",
                diag["unresolved_against_queue_sample"],
            )

    def test_no_queue_ids_no_diagnostics_backcompat(self):
        # Both optional args omitted: original behavior minus reserved tokens.
        tmp, root = self._mkproject()
        with tmp:
            inscribed = rcc.build_inscribed_index(str(root))
            self.assertIn("cpr_real_lesson_tic700", inscribed)
            self.assertIn("cpr_legacy_never_queued_tic12", inscribed)
            self.assertNotIn("cpr_era_tic_700_749", inscribed)

    def test_receipt_surface_site_excludes_reserved(self):
        # A5-707 second call site: _receipt_surface_ids must apply the same rule.
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            root = Path(tmp.name)
            conf = root / "audit-logs" / "conformations"
            conf.mkdir(parents=True)
            (conf / "tic-1.json").write_text(
                json.dumps(
                    {
                        "note": "cites cpr_cited_in_receipt_tic5 and "
                        "era label cpr_era_tic_700_749"
                    }
                ),
                encoding="utf-8",
            )
            rcc._RECEIPT_INDEX_CACHE.clear()
            ids = rcc._receipt_surface_ids(str(root))
            self.assertIn("cpr_cited_in_receipt_tic5", ids)
            self.assertNotIn("cpr_era_tic_700_749", ids)
            rcc._RECEIPT_INDEX_CACHE.clear()

    def test_is_reserved_ref(self):
        self.assertTrue(rcc._is_reserved_ref("cpr_era_tic_700_749"))
        self.assertFalse(rcc._is_reserved_ref("cpr_era"))  # bare, no underscore-suffix namespace
        self.assertFalse(rcc._is_reserved_ref("cpr_real_lesson_tic700"))


class TestGenuineZeroStreak(unittest.TestCase):
    def _mklog(self, rows):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        for r in rows:
            tmp.write(json.dumps(r) + "\n")
        tmp.close()
        return tmp.name

    def test_streak_with_gap_reobservation_and_break(self):
        log = self._mklog(
            [
                {"tic": 699, "genuine_count": 2},  # breaking tic
                {"tic": 700, "genuine_count": 0},
                {"tic": 701, "genuine_count": 0},
                {"tic": 701, "genuine_count": 0},  # same-tic re-observation
                # 702 unobserved — a GAP, disclosed, not absorbed
                {"tic": 703, "genuine_count": 0},
            ]
        )
        try:
            s = rcc.compute_genuine_zero_streak(log, 704, 0)
            self.assertEqual(s["unit"], "distinct_check_bearing_tics")
            self.assertEqual(s["distinct_check_bearing_tics"], 4)  # 700,701,703,704
            self.assertEqual(s["row_count_within_streak"], 5)  # 701 counted twice as ROWS
            self.assertEqual(s["span"], [700, 704])
            self.assertEqual(s["gap_tics_no_check_row"], [702])
            self.assertEqual(s["same_tic_reobservation_tics"], {"701": 2})
            self.assertEqual(s["broken_at_tic"], 699)
        finally:
            os.unlink(log)

    def test_current_row_genuine_breaks_streak(self):
        # The other arm: a current genuine>0 row yields streak 0, breaking tic
        # disclosed as the current tic.
        log = self._mklog([{"tic": 700, "genuine_count": 0}])
        try:
            s = rcc.compute_genuine_zero_streak(log, 701, 3)
            self.assertEqual(s["distinct_check_bearing_tics"], 0)
            self.assertEqual(s["broken_at_tic"], 701)
        finally:
            os.unlink(log)

    def test_empty_log_first_observation(self):
        # No log yet: the current zero row is a streak of exactly one tic.
        missing = os.path.join(tempfile.gettempdir(), "no-such-rcc-log.jsonl")
        s = rcc.compute_genuine_zero_streak(missing, 705, 0)
        self.assertEqual(s["distinct_check_bearing_tics"], 1)
        self.assertEqual(s["span"], [705, 705])
        self.assertEqual(s["gap_tics_no_check_row"], [])
        self.assertIsNone(s["broken_at_tic"])

    def test_unbroken_history_no_breaking_tic(self):
        log = self._mklog(
            [{"tic": 700, "genuine_count": 0}, {"tic": 701, "genuine_count": 0}]
        )
        try:
            s = rcc.compute_genuine_zero_streak(log, 702, 0)
            self.assertEqual(s["distinct_check_bearing_tics"], 3)
            self.assertIsNone(s["broken_at_tic"])
        finally:
            os.unlink(log)

    def test_malformed_rows_skipped(self):
        log = self._mklog([{"tic": 700, "genuine_count": 0}])
        with open(log, "a", encoding="utf-8") as f:
            f.write("not-json\n")
            f.write(json.dumps({"no_tic": True}) + "\n")
        try:
            s = rcc.compute_genuine_zero_streak(log, 701, 0)
            self.assertEqual(s["distinct_check_bearing_tics"], 2)
        finally:
            os.unlink(log)


if __name__ == "__main__":
    unittest.main(verbosity=2)
