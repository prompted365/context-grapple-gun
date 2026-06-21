#!/usr/bin/env python3
"""Tests for cpr-extract.py recency-bounded session_lessons scan (tic 483).

Borns authored at /cadence Step 2 land in the auto-memory directory as
session_lessons_tic_<N>[...].md carrying BLOCK-form <!-- --agnostic-candidate -->
markers. The boot counts them as inline CogPRs, but cpr-extract historically
scanned only MEMORY.md/CLAUDE.md — so those borns were unreachable (the tic-481
and tic-482 borns had to be rescued by hand via --plan-file). That violated the
promoted CGG invariant *Emitter Surface Declared Interface*.

select_session_lessons_files() makes the born home reachable, but RECENCY-BOUNDED
and SELF-ANCHORING: the window is measured from the NEWEST session_lessons file
present (the born frontier), NOT from an external tic counter (get_tic_count
over-counts raw tic events vs the authoritative conformation tic, which would
silently misalign the window and miss the current born). Forward borns are
scanned automatically; the historical backlog is NEVER swept as an extractor
side effect (it is a separate /review-gated decision). These cases test the pure
selection helper directly — nothing touches the real queue.

Run:  python3 -m unittest test_cpr_extract_session_lessons   (from cgg-runtime/scripts/)
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "cpr_extract", os.path.join(_HERE, "cpr-extract.py")
)
ce = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ce)


def _names(paths):
    return sorted(p.name for p in paths)


class SelectSessionLessonsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _touch(self, name):
        (self.dir / name).write_text("# stub\n", encoding="utf-8")

    def test_window_includes_frontier_and_recent(self):
        # max present = 483, window=3 → include tic >= 480
        for n in (479, 480, 481, 482, 483):
            self._touch(f"session_lessons_tic_{n}.md")
        got = ce.select_session_lessons_files(self.dir, window=3)
        self.assertEqual(
            _names(got),
            [f"session_lessons_tic_{n}.md" for n in (480, 481, 482, 483)],
        )

    def test_window_excludes_historical(self):
        # the historical backlog (tics far below the frontier) is never selected
        for n in (164, 223, 274, 398, 482):
            self._touch(f"session_lessons_tic_{n}.md")
        got = ce.select_session_lessons_files(self.dir, window=3)
        self.assertEqual(_names(got), ["session_lessons_tic_482.md"])

    def test_anchor_is_frontier_not_external_counter(self):
        # REGRESSION (tic 483): the newest born file MUST always be selected,
        # independent of any external tic count. get_tic_count over-counted
        # (487 vs authoritative 483) and an external-anchored window [484,487]
        # silently excluded the real current born (483). Frontier-anchoring fixes it.
        for n in (480, 481, 482, 483):
            self._touch(f"session_lessons_tic_{n}.md")
        got = ce.select_session_lessons_files(self.dir, window=3)
        self.assertIn("session_lessons_tic_483.md", _names(got))

    def test_window_boundary_exact(self):
        # tic == frontier-window is INCLUDED; tic == frontier-window-1 is EXCLUDED
        self._touch("session_lessons_tic_490.md")  # frontier
        self._touch("session_lessons_tic_487.md")  # 490-3 -> included
        self._touch("session_lessons_tic_486.md")  # 490-4 -> excluded
        got = ce.select_session_lessons_files(self.dir, window=3)
        self.assertEqual(
            _names(got),
            ["session_lessons_tic_487.md", "session_lessons_tic_490.md"],
        )

    def test_filename_variants_parse_tic(self):
        # suffixed / _v2 / descriptive variants must parse the leading tic number
        self._touch("session_lessons_tic_482_v2.md")            # frontier
        self._touch("session_lessons_tic_481_inline_cpr_pending.md")
        self._touch("session_lessons_tic_400_old_variant.md")  # excluded by window
        got = ce.select_session_lessons_files(self.dir, window=3)
        self.assertEqual(
            _names(got),
            ["session_lessons_tic_481_inline_cpr_pending.md",
             "session_lessons_tic_482_v2.md"],
        )

    def test_non_session_lessons_skipped(self):
        # only session_lessons_tic_* files are candidates — pointers/context are not
        self._touch("session_lessons_tic_482.md")
        self._touch("MEMORY.md")
        self._touch("project_some_topic.md")
        self._touch("reference_cpr_482_mention.md")
        got = ce.select_session_lessons_files(self.dir, window=3)
        self.assertEqual(_names(got), ["session_lessons_tic_482.md"])

    def test_negative_window_disables(self):
        # window < 0 selects nothing — legacy MEMORY.md/CLAUDE.md-only behavior
        self._touch("session_lessons_tic_482.md")
        self._touch("session_lessons_tic_483.md")
        self.assertEqual(ce.select_session_lessons_files(self.dir, window=-1), [])

    def test_huge_window_selects_all(self):
        # a window spanning the full tic range is the gated historical-sweep
        # escape hatch (never the default)
        for n in (164, 300, 482):
            self._touch(f"session_lessons_tic_{n}.md")
        got = ce.select_session_lessons_files(self.dir, window=9999)
        self.assertEqual(len(got), 3)

    def test_deterministic_ordering_by_tic_then_name(self):
        self._touch("session_lessons_tic_482_b.md")
        self._touch("session_lessons_tic_482_a.md")
        self._touch("session_lessons_tic_481.md")
        got = ce.select_session_lessons_files(self.dir, window=3)
        self.assertEqual(
            [p.name for p in got],
            ["session_lessons_tic_481.md",
             "session_lessons_tic_482_a.md",
             "session_lessons_tic_482_b.md"],
        )

    def test_empty_or_missing_dir_returns_empty(self):
        self.assertEqual(ce.select_session_lessons_files(self.dir, window=3), [])
        self.assertEqual(
            ce.select_session_lessons_files(self.dir / "nope", window=3), []
        )

    def test_default_window_constant(self):
        # the module default is forward-only and small (excludes the historical backlog)
        self.assertGreaterEqual(ce.SESSION_LESSONS_RECENCY_WINDOW, 1)
        self.assertLessEqual(ce.SESSION_LESSONS_RECENCY_WINDOW, 5)


if __name__ == "__main__":
    unittest.main()
