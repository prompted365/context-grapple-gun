#!/usr/bin/env python3
"""Tests for the /review 781 review-close-check cure — THE READ-INSTANT face.

Q2 (cpr_mogul_review_close_check_c509ebc8101d, PROMOTE + same-pass cure,
Architect-ratified recommended-option-verbatim): a multi-block artifact whose
blocks are measured at DIFFERENT INSTANTS of one run must publish a per-block
read-instant INTO the artifact — else a consumer with no call site reads the
blocks as simultaneous and finds a FALSE contradiction between fields each true
at its own write-time (lived at tic 778: prior_same_tic_observation.
earlier_preserved_same_tic_artifacts [] beside a superseded_receipt naming
exactly such a file — the list was computed BEFORE that run's own
preservation). queue_state_tuple modeled the cure first (read_at + a
by-construction blind-spot sentence); this cure extends the pattern to every
own-read block and moves the ordering clause from the function docstring INTO
the artifact (_SAME_TIC_OBS_NOTE, append-only).

THE CONSUMER HALF, adapted in the same change set: read-instants are
occurrence-class BY TYPE under the /review-775 MEASUREMENT-vs-OCCURRENCE
discriminator, so normalize_report_for_content_compare strips `read_at` keys
RECURSIVELY — otherwise every re-run's fresh instants would flip skip->replace
and the act of re-observing would manufacture its own supersession evidence
(the exact t772/t775 failure class). Test 4 is the NC: reverting the recursive
strip breaks it by construction. Test 5 pins the skip-branch parity.

FENCE HONORED: the same_tic block's PATH-CITATION composition (artifact /
selector naming the live tic-keyed path) is NOT touched — THE MUTABLE-ADDRESS
face (cpr_mogul_review_close_check_55eb70c0a49b) adjudicates at ITS docket
(783), not here.
"""
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest
from datetime import datetime

_HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "review_close_check_read_instant", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rcc)

_ORDERING_CLAUSE_MARK = "READ-INSTANT (/review 781"
_NOT_SIMULTANEOUS_MARK = "NOT simultaneous"


def _assert_iso_instant(testcase, value, where):
    testcase.assertIsInstance(value, str, f"{where}: read_at must be a string")
    # fromisoformat raises on a non-instant — the assertion IS the parse.
    datetime.fromisoformat(value)


def _walk_keys(node, key):
    """Yield every path at which `key` occurs anywhere in a nested structure."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield k
            yield from _walk_keys(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_keys(v, key)


class SameTicBlockReadInstant(unittest.TestCase):
    """The lived contradiction site: the same-tic prior-observation block."""

    def test_first_fire_block_carries_read_instant_and_ordering_clause(self):
        with tempfile.TemporaryDirectory() as td:
            prior, block = rcc._read_same_tic_prior_observation(
                td, "tic-9999-check.json")
        self.assertIsNone(prior)
        self.assertFalse(block["present"])
        self.assertEqual(block["reason_absent"], "no_same_tic_prior_observation")
        _assert_iso_instant(self, block["read_at"], "same_tic first fire")
        self.assertIn(_ORDERING_CLAUSE_MARK, block["note"])
        self.assertIn(_NOT_SIMULTANEOUS_MARK, block["note"])

    def test_present_fire_block_carries_read_instant_and_ordering_clause(self):
        with tempfile.TemporaryDirectory() as td:
            live = os.path.join(td, "tic-9999-check.json")
            with open(live, "w", encoding="utf-8") as f:
                json.dump({"generated_at": "2026-09-08T00:00:00+00:00"}, f)
            prior, block = rcc._read_same_tic_prior_observation(
                td, "tic-9999-check.json")
        self.assertIsInstance(prior, dict)
        self.assertTrue(block["present"])
        self.assertEqual(block["selector"], "same_tic_live_artifact_pre_overwrite")
        _assert_iso_instant(self, block["read_at"], "same_tic present fire")
        self.assertIn(_ORDERING_CLAUSE_MARK, block["note"])


class OwnReadBlocksCarryTheirInstants(unittest.TestCase):
    """Every block that performs its OWN read publishes its own instant."""

    def test_each_own_read_block_carries_read_at(self):
        with tempfile.TemporaryDirectory() as td:
            fname = "tic-9999-check.json"
            blocks = {
                "inscribed_index_delta": rcc.compute_unit_deltas(
                    td, fname, 9999, 5, 5),
                "verdict_counts_delta": rcc.compute_verdict_count_deltas(
                    td, fname, 9999,
                    {"promoted": 1, "deferred": 0, "skipped": 0}),
                "sibling_pair_attribution": rcc.compute_sibling_pair_attribution(
                    td, fname, 9999, []),
                "cross_counter_attribution": rcc.compute_cross_counter_attribution(
                    td, fname, 9999, set(), [], {}),
                "genuine_zero_streak": rcc.compute_genuine_zero_streak(
                    os.path.join(td, "log.jsonl"), 9999, 0),
            }
        for name, block in blocks.items():
            with self.subTest(block=name):
                self.assertIn("read_at", block,
                              f"{name} must publish its own read-instant")
                _assert_iso_instant(self, block["read_at"], name)


class NormalizerStripsReadInstants(unittest.TestCase):
    """The consumer half — the skip-vs-replace predicate never sees instants."""

    def _report(self, stamp):
        """A report-shaped dict with read_at at several depths."""
        return {
            "check_type": "review_close_check",
            "queue_state_tuple": {"read_at": stamp, "sha256_16": "abc",
                                  "raw_rows": 1},
            "inscribed_index_delta": {
                "read_at": stamp,
                "delta_tokens": 2,
                "prior_same_tic_observation": {
                    "read_at": stamp, "present": False,
                },
                "attribution": {"read_at": stamp,
                                "attribution_unresolved": True},
            },
            "verdict_counts_delta": {"read_at": stamp,
                                     "delta": {"promoted": 1}},
            "findings": [{"type": "x", "evidence": {"read_at": stamp}}],
            "genuine_zero_streak": {
                "read_at": stamp,
                "unit": "distinct_check_bearing_tics",
                "row_count_within_streak": 3,
                "same_tic_reobservation_tics": {},
                "span": [1, 3],
            },
        }

    def test_normalized_view_contains_no_read_instants_anywhere(self):
        # THE NC (P3): reverting the recursive strip in
        # normalize_report_for_content_compare breaks exactly this test —
        # the normalized view would still carry nested read_at keys.
        norm = rcc.normalize_report_for_content_compare(
            self._report("2026-09-08T01:02:03+00:00"))
        self.assertEqual(list(_walk_keys(norm, "read_at")), [],
                         "no read_at key may survive into the comparison view")
        # Information-bearing siblings survive the strip untouched.
        self.assertEqual(norm["queue_state_tuple"]["sha256_16"], "abc")
        self.assertEqual(norm["inscribed_index_delta"]["delta_tokens"], 2)
        self.assertEqual(norm["genuine_zero_streak"]["span"], [1, 3])

    def test_reports_differing_only_in_read_instants_compare_equal(self):
        # P4 (skip-branch parity): a re-run whose only movement is its own
        # read-instants is the SAME content — the skip branch must still fire,
        # so re-observing cannot manufacture supersession evidence.
        a = rcc.normalize_report_for_content_compare(
            self._report("2026-09-08T01:02:03+00:00"))
        b = rcc.normalize_report_for_content_compare(
            self._report("2026-09-08T09:59:59+00:00"))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
