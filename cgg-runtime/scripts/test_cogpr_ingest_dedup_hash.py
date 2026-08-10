#!/usr/bin/env python3
"""test_cogpr_ingest_dedup_hash.py — capture-time dedup_hash stamp fixtures.

Fix-site: bk-cogpr-ingest-dedup-hash-unstamped (filed from the cpr-stepper
A1-688 pass, struck tic 692). 25 of 36 cogpr-ingest rows corpus-wide carried
NO dedup_hash — vs cpr-extract at 171/171 stamped — so on this lane hash-dedup
was not blind to the t687 stub shape, it was ABSENT entirely. The cure stamps
the cpr-extract lane's exact colon-form formula, sha256("{source}:{lesson}")
[:16], at capture. SCOPE FENCE (per the filing): capture-defect half only —
the stub-ABSORB question is the /review lane's; historical unstamped rows are
not retro-edited.
"""

import hashlib
import importlib.util
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("cogpr_ingest", _HERE / "cogpr-ingest.py")
ci = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ci)

TOPO = {"birth_rung": "site", "birth_scope_path": "/tmp/zone"}
REPORT = {"mandate_id": "tic-692-test", "actor": {"runtime": "claude_code"}}


def _mint(lesson, cycle="pattern_mining"):
    return ci.mint_entry({"lesson": lesson}, cycle, REPORT, 692, TOPO)


class DedupHashStamp(unittest.TestCase):
    def test_minted_entry_carries_colon_form_dedup_hash(self):
        """THE defect: pre-fix the field was absent entirely on this lane."""
        e = _mint("A lesson about queues.")
        self.assertIn("dedup_hash", e)
        want = hashlib.sha256(
            "mogul:pattern_mining:A lesson about queues.".encode()
        ).hexdigest()[:16]
        self.assertEqual(e["dedup_hash"], want)

    def test_formula_parity_with_cpr_extract_lane(self):
        """Same formula shape as cpr-extract: sha256(source:lesson)[:16],
        where source is the row's own source field."""
        e = _mint("Another lesson.", cycle="queue_refresh")
        want = hashlib.sha256(f"{e['source']}:{e['lesson']}".encode()).hexdigest()[:16]
        self.assertEqual(e["dedup_hash"], want)
        self.assertEqual(len(e["dedup_hash"]), 16)

    def test_deterministic_same_candidate_same_hash_and_id(self):
        a = _mint("Stable lesson.")
        b = _mint("Stable lesson.")
        self.assertEqual(a["dedup_hash"], b["dedup_hash"])
        self.assertEqual(a["id"], b["id"])

    def test_distinct_cycles_yield_distinct_hashes(self):
        a = _mint("Same lesson.", cycle="pattern_mining")
        b = _mint("Same lesson.", cycle="deep_audit")
        self.assertNotEqual(a["dedup_hash"], b["dedup_hash"])

    def test_lesson_less_candidate_still_returns_none(self):
        self.assertIsNone(ci.mint_entry({"lesson": "  "}, "c", REPORT, 692, TOPO))

    def test_id_derivation_unchanged_by_the_stamp(self):
        """The 12-char cycle-keyed id formula is untouched — the stamp is
        additive, never a re-key of identity."""
        e = _mint("Id stability lesson.")
        digest = hashlib.sha256(
            "pattern_mining:Id stability lesson.".encode()
        ).hexdigest()[:12]
        self.assertEqual(e["id"], f"cpr_mogul_pattern_mining_{digest}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
