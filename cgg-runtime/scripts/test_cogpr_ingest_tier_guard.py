#!/usr/bin/env python3
"""test_cogpr_ingest_tier_guard.py — birth-surface tier vocabulary guard fixtures.

Fix-site: /review 708 off-enum rulings 1-4 (the write-boundary physics guard,
ruling 4; census A1-707/A2-708: 45/320 latest-per-id rows carried off-enum
confidence_tier values under producer restraint alone — A6-707). The birth
surface's arm: an off-enum candidate value is STRIPPED TO ABSENT with a typed
`tier_refusal` marker on the row + a stderr TIER-REFUSAL notice — the lesson is
never dropped (a row-level reject at a background birth surface would be its
own coverage drop; guard 10's shape). Lawful enum members (incl. the ruling-3
admitted measured family) pass through untouched; a candidate asserting nothing
keeps the lawful `tentative` default. Content: contracts/confidence-tier-enum-v1.json.

SCOPE FENCE: historical rows are not retro-edited (rulings 1-3 route history
through the correction lane / leave-disclosed); this guards NEW births only.
"""

import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "cogpr_ingest", _HERE / "cogpr-ingest.py")
ingest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ingest)

REPORT = {"mandate_id": "tic-708-test", "actor": {"runtime": "test"}}
TOPO = {"birth_rung": "site", "birth_scope_path": "/tmp/x"}


def mint(candidate):
    err = io.StringIO()
    with redirect_stderr(err):
        entry = ingest.mint_entry(candidate, "test_cycle", REPORT, 708, TOPO)
    return entry, err.getvalue()


class TestTierGuardAtBirth(unittest.TestCase):
    def test_lawful_value_passes_untouched(self):
        entry, err = mint({"lesson": "L1", "confidence_tier": "reinforced"})
        self.assertEqual(entry["confidence_tier"], "reinforced")
        self.assertNotIn("tier_refusal", entry)
        self.assertNotIn("TIER-REFUSAL", err)

    def test_admitted_measured_family_passes(self):
        for value in ("measured", "measured_single_locus"):
            entry, _ = mint({"lesson": f"L-{value}", "confidence_tier": value})
            self.assertEqual(entry["confidence_tier"], value)
            self.assertNotIn("tier_refusal", entry)

    def test_missing_value_keeps_tentative_default(self):
        entry, err = mint({"lesson": "L2"})
        self.assertEqual(entry["confidence_tier"], "tentative")
        self.assertNotIn("tier_refusal", entry)
        self.assertNotIn("TIER-REFUSAL", err)

    def test_off_enum_stripped_to_absent_with_typed_marker(self):
        entry, err = mint({"lesson": "L3", "confidence_tier": "observed"})
        self.assertNotIn("confidence_tier", entry)
        self.assertEqual(entry["tier_refusal"]["value"], "observed")
        self.assertEqual(entry["tier_refusal"]["reason"], "non_tier_marker")
        self.assertEqual(entry["tier_refusal"]["ruling"], "review-708")
        self.assertIn("TIER-REFUSAL", err)

    def test_class_bleed_stripped_and_named(self):
        entry, err = mint({"lesson": "L4", "confidence_tier": "exact"})
        self.assertNotIn("confidence_tier", entry)
        self.assertEqual(entry["tier_refusal"]["reason"], "class_bleed")
        self.assertIn("TIER-REFUSAL", err)

    def test_novel_coinage_stripped_as_off_enum(self):
        entry, err = mint({"lesson": "L5", "confidence_tier": "extremely_sure"})
        self.assertNotIn("confidence_tier", entry)
        self.assertEqual(entry["tier_refusal"]["reason"], "off_enum")
        self.assertIn("TIER-REFUSAL", err)

    def test_lesson_never_dropped_by_tier_refusal(self):
        entry, _ = mint({"lesson": "the lesson survives", "confidence_tier": "high"})
        self.assertIsNotNone(entry)
        self.assertEqual(entry["lesson"], "the lesson survives")
        self.assertEqual(entry["status"], "extracted")


if __name__ == "__main__":
    unittest.main()
