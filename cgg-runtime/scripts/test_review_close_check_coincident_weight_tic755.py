#!/usr/bin/env python3
"""test_review_close_check_coincident_weight_tic755.py — the COINCIDENT-ARMS
weight coupling (/review 755 Q2, cpr_mogul_review_close_check_1b8378e77bd7
absorbed into the ATTRIBUTION clause; ruled consumer).

The lived defect (tic 752 close): promoted_delta 3 / token_delta 3 read
agree=true, non-vacuous, "evidence-bearing — two independent counters landed
on the same non-zero movement" — over sets intersecting in only 2 members.
Two catalogued divergence routes cancelled into a numeric coincidence the
magnitude-only weight scored as corroboration. The cure couples the weight
to the SAME attribution block the disclosure already prints: when the deltas
agree non-vacuously and magnitude_agreement_is_coincidence is True, the
weight reads coincident-arms instead of evidence-bearing. The agree flag
itself stays a magnitude claim by design (read the sets, not the flag).

Seven tests: coincidence→coincident-arms · no-coincidence→evidence-bearing ·
no-attribution default honest · vacuous arm unchanged · disagreement arm
unchanged · the lived 752 shape · agree-flag invariance.
"""

import importlib.util
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("rcc_t755", _HERE / "review-close-check.py")
rcc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rcc)


def _disc(promoted, tokens, attribution=None):
    return rcc.compute_cross_counter_disclosure(
        {"delta": {"promoted": promoted}}, {"delta_tokens": tokens}, attribution)


def _coincident_attribution(flag=True):
    return {
        "magnitude_agreement_is_coincidence": flag,
        "agree_by_membership": not flag,
        "new_index_tokens": ["a", "b", "c"],
        "new_promoted_ids": ["a", "b", "d"],
        "intersection_new_tokens_new_promoted": ["a", "b"],
    }


class CoincidentArmsWeight(unittest.TestCase):
    def test_equal_nonzero_with_coincidence_prints_coincident_arms(self):
        d = _disc(3, 3, _coincident_attribution(True))
        self.assertTrue(d["agree"])
        self.assertFalse(d["vacuous"])
        self.assertTrue(d["evidential_weight"].startswith("coincident-arms"))

    def test_equal_nonzero_without_coincidence_stays_evidence_bearing(self):
        d = _disc(2, 2, _coincident_attribution(False))
        self.assertTrue(d["evidential_weight"].startswith("evidence-bearing"))

    def test_no_attribution_supplied_stays_magnitude_honest(self):
        # two-argument form: no membership sets were supplied — the weight
        # cannot claim coincidence it never computed; the attribution field
        # carries the UNRESOLVED shape beside it.
        d = _disc(1, 1)
        self.assertTrue(d["evidential_weight"].startswith("evidence-bearing"))
        self.assertTrue(d["attribution"].get("attribution_unresolved"))

    def test_vacuous_arm_unchanged_even_with_coincidence_flag(self):
        d = _disc(0, 0, _coincident_attribution(True))
        self.assertTrue(d["vacuous"])
        self.assertTrue(d["evidential_weight"].startswith("none — both deltas are zero"))

    def test_disagreement_arm_unchanged(self):
        d = _disc(3, 2, _coincident_attribution(True))
        self.assertFalse(d["agree"])
        self.assertTrue(d["evidential_weight"].startswith("disagreement"))

    def test_lived_752_shape_names_attribution(self):
        # the tic-752 close reading: 3/3 over intersection 2 — the weight now
        # points the reader at the attribution instead of overclaiming.
        d = _disc(3, 3, _coincident_attribution(True))
        self.assertIn("see attribution", d["evidential_weight"])
        self.assertIn("an equal number is not a shared observation",
                      d["evidential_weight"])

    def test_agree_flag_itself_is_untouched_by_coupling(self):
        # the flag stays a MAGNITUDE claim (the clause's design: membership
        # verifies it beside, never rewrites it) — only the WEIGHT moves.
        d = _disc(3, 3, _coincident_attribution(True))
        self.assertTrue(d["agree"])
        d2 = _disc(3, 3, _coincident_attribution(False))
        self.assertTrue(d2["agree"])
        self.assertNotEqual(d["evidential_weight"], d2["evidential_weight"])


if __name__ == "__main__":
    unittest.main()
