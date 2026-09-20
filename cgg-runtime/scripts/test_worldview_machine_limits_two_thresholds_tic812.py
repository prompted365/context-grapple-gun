#!/usr/bin/env python3
"""Fixtures for BOTH internal-disk thresholds in the MACHINE LIMITS sentence.

RULED /review 804 round 2, Ruling D (Architect, recommended option verbatim "Render both,
named, no verdict word"); KEPT /review 811 round 1 Q3. Ruling receipt
audit-logs/governance/receipts/2026-09-19-tic804-machine-limits-two-thresholds-ruling.md.
Built at tic 812 by the harpoon-build seat. Answers F-803-BL-2 (MEDIUM), raised by the
tic-803 build's own cable receipt.

WHAT WAS WRONG: the sentence conflated TWO different internal-disk thresholds under one
word. "NO model pull is safe" was a verdict about CONVERSION-OUTPUT headroom, not about a
model PULL. The two differ by more than 2x and select opposite reads at the same free-space
figure, so at 15 GiB free the frozen sentence and the frozen figure disagreed with each
other. The block now prints BOTH thresholds, NAMED, each with its OWN basis citation and its
OWN fits / does-not-fit read against ONE live free-space reading. "safe" is retired.

DOES-NOT-SATISFY RIDER (attached by the ruling; reproduced verbatim because a file full of
disk-threshold assertions is exactly what a reader could mistake for the withheld thing):

  "this increment does NOT rule or build the crisis sentinel's disk-headroom arm, does NOT
  build the cold_unavailable helper, does NOT rule Increment 2 of the T7 canonical-cold
  region, and does NOT attribute disk movement to any cause."

Nothing here observes disk on a schedule, emits a signal, writes state, or names a cause for
any disk movement. It renders a sentence at boot and proves that sentence fails soft.

Arms (every documented conditional, both sides - cgg-ledger#selftest-fixtures-must-exercise-
documented-conditional-paths):
  1. both thresholds named   - each with its own basis citation, in one sentence
  2. the four regions        - above both / between the two / inside the range / below both
  3. "safe" is gone          - searched in the rendered OUTPUT of every arm, not the source
  4. inherited fail-soft     - read failure, T7 unmounted, sysctl failure, render exception
  5. one read, two compares  - both thresholds consume the SAME reading; no second read
  6. the range is honest     - three outcomes, and the boundary values on both sides
  7. rider verbatim          - asserted by EQUALITY against the ruling's wording
  8. basis quotes are real   - each quoted fragment is a verbatim substring of the evidence
                               file (skipped, declared, when the evidence is unreachable)
  9. block integrity         - both thresholds survive into the full STANDING SUBSTRATE block

Run:  python3 -m pytest -q -p no:cacheprovider \
        test_worldview_machine_limits_two_thresholds_tic812.py
"""

import importlib.util
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

_spec = importlib.util.spec_from_file_location("office_worldview_tic812",
                                               HERE / "office-worldview.py")
ow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ow)

# The rider exactly as the /review 804 ruling attached it. Asserted by equality, never by
# substring - a rider that only reads correctly to a human is not a verbatim carry.
RIDER = ("this increment does NOT rule or build the crisis sentinel's disk-headroom arm, "
         "does NOT build the cold_unavailable helper, does NOT rule Increment 2 of the T7 "
         "canonical-cold region, and does NOT attribute disk movement to any cause.")

# The retired verdict word, in every casing the sentence could reintroduce it.
RETIRED = ("NO model pull is safe", "is safe", "is not safe", "unsafe", " safe")

NOWSTAMP = datetime(2026, 9, 20, 22, 0, tzinfo=timezone.utc)

LOW = ow.CONVERSION_OUTPUT_THRESHOLD_GIB_LOW      # 14
HIGH = ow.CONVERSION_OUTPUT_THRESHOLD_GIB_HIGH    # 18.5
PULL = ow.MODEL_PULL_THRESHOLD_GIB                # 8.1


def _reading(internal_free=85.5, internal_cap=91, internal_ok=True, internal_err=None,
             t7_free=1494.5, t7_cap=60, t7_mounted=True, t7_ok=True, t7_err=None,
             wired_ok=True, wired_value=0, wired_err=None):
    """A synthetic reading so each region is deterministic - the live machine is never
    touched to move a figure (the ruling's own instruction: inject the reading)."""
    return {
        "read_at": NOWSTAMP.strftime("%Y-%m-%dT%H:%MZ"),
        "internal": {"path": ow.INTERNAL_DATA_VOLUME, "mounted": True, "ok": internal_ok,
                     "free_gib": internal_free, "capacity_pct": internal_cap,
                     "error": internal_err},
        "t7": {"path": ow.T7_MOUNT, "mounted": t7_mounted, "ok": t7_ok,
               "free_gib": t7_free, "capacity_pct": t7_cap, "error": t7_err},
        "wired_limit_mb": {"ok": wired_ok, "value": wired_value, "error": wired_err},
        "model_pull_threshold_gib": ow.MODEL_PULL_THRESHOLD_GIB,
        "model_pull_threshold_basis": ow.MODEL_PULL_THRESHOLD_BASIS,
        "conversion_output_threshold_gib_low": LOW,
        "conversion_output_threshold_gib_high": HIGH,
        "conversion_output_threshold_basis": ow.CONVERSION_OUTPUT_THRESHOLD_BASIS,
    }


# Every region the sentence can be in, as (label, free_gib) - used by the "safe"-is-gone
# sweep so it searches the OUTPUT of EVERY arm rather than one happy path.
REGIONS = [
    ("above both", 85.5),
    ("between the two (pull fits, conversion does not)", 10.0),
    ("inside the conversion range", 15.0),
    ("below both", 5.0),
    ("exactly at the pull threshold", PULL),
    ("exactly at the range bottom", LOW),
    ("exactly at the range top", HIGH),
]


class BothThresholdsRenderNamed(unittest.TestCase):
    """Arm 1 - BOTH thresholds render, NAMED, each with its own basis citation."""

    def test_both_thresholds_are_named_in_one_sentence(self):
        s = ow.render_machine_limits(_reading())
        self.assertIn("8.1 GiB model-pull threshold", s)
        self.assertIn("14–18.5 GiB conversion-output threshold", s)

    def test_each_threshold_carries_its_own_basis_citation(self):
        s = ow.render_machine_limits(_reading())
        self.assertIn("threshold basis:", s)
        self.assertIn("conversion threshold basis:", s)
        # the pull basis names its evidence
        self.assertIn("an 8.1 GiB re-acquisition", s)
        # the conversion basis names ITS evidence, both anchors
        self.assertIn("hardware.disk.BINDING_CONSTRAINT", s)
        self.assertIn("affordability.ranking_summary.FITS_WITH_CONVERSION", s)
        self.assertEqual(s.count("lane-A-affordability.json"), 2,
                         "each threshold must cite the evidence file for ITSELF")

    def test_neither_threshold_is_rendered_without_the_other(self):
        for _label, free in REGIONS:
            s = ow.render_machine_limits(_reading(internal_free=free))
            self.assertIn("model-pull threshold", s)
            self.assertIn("conversion-output threshold", s)


class TheFourRegions(unittest.TestCase):
    """Arm 2 - the four regions, by INJECTED readings. The real disk is never moved."""

    def test_above_both_thresholds(self):
        s = ow.render_machine_limits(_reading(internal_free=85.5, internal_cap=91))
        self.assertIn("above the 8.1 GiB model-pull threshold, so the largest named pending "
                      "pull FITS", s)
        self.assertIn("ABOVE the top of the range, so a conversion output anywhere in the "
                      "range FITS", s)

    def test_between_the_two_pull_fits_conversion_does_not(self):
        s = ow.render_machine_limits(_reading(internal_free=10.0, internal_cap=98))
        self.assertIn("above the 8.1 GiB model-pull threshold", s)
        self.assertIn("BELOW the bottom of the range, so a conversion output anywhere in "
                      "the range DOES NOT FIT", s)

    def test_inside_the_conversion_range(self):
        s = ow.render_machine_limits(_reading(internal_free=15.0, internal_cap=99))
        self.assertIn("above the 8.1 GiB model-pull threshold", s)
        self.assertIn("INSIDE the range, so an output at the 14 GiB bottom FITS and one at "
                      "the 18.5 GiB top DOES NOT FIT", s)

    def test_below_both_thresholds(self):
        s = ow.render_machine_limits(_reading(internal_free=5.0, internal_cap=99))
        self.assertIn("BELOW the 8.1 GiB model-pull threshold: the largest named pending "
                      "pull DOES NOT FIT", s)
        self.assertIn("BELOW the bottom of the range", s)

    def test_the_t748_figure_now_reads_as_two_different_things(self):
        """The whole point of F-803-BL-2: at the historical 15 GiB reading the PULL fits and
        the CONVERSION output does not. One number, two honest and OPPOSITE reads - which is
        why one word could never carry both."""
        s = ow.render_machine_limits(_reading(internal_free=15.0, internal_cap=99))
        self.assertIn("pull FITS", s)
        self.assertIn("18.5 GiB top DOES NOT FIT", s)


class SafeIsRetired(unittest.TestCase):
    """Arm 3 - "safe" is gone from every arm of the RENDERED OUTPUT (not the source)."""

    def test_no_arm_of_the_rendered_output_carries_the_retired_word(self):
        for label, free in REGIONS:
            s = ow.render_machine_limits(_reading(internal_free=free))
            for word in RETIRED:
                self.assertNotIn(word, s, f"region [{label}] reintroduced {word!r}")

    def test_the_failure_arms_do_not_carry_it_either(self):
        arms = [
            ow.render_machine_limits(_reading(internal_ok=False, internal_free=None,
                                              internal_cap=None, internal_err="OSError")),
            ow.render_machine_limits(_reading(t7_mounted=False, t7_ok=False, t7_free=None,
                                              t7_cap=None, t7_err="not mounted")),
            ow.render_machine_limits(_reading(wired_ok=False, wired_value=None,
                                              wired_err="FileNotFoundError")),
            ow.render_machine_limits({}),
        ]
        for i, s in enumerate(arms):
            for word in RETIRED:
                self.assertNotIn(word, s, f"failure arm {i} reintroduced {word!r}")

    def test_the_full_block_render_carries_no_arm_with_it(self):
        block = ow.render_standing_substrate(812)
        self.assertNotIn("NO model pull is safe", block)
        self.assertNotIn("model pull is safe", block)


class InheritedFailSoft(unittest.TestCase):
    """Arm 4 - the parent increment's properties SURVIVE: fail-soft never fail-stale, no
    remembered number, no exception out of the block, and the conversion line under a failed
    read says `unmeasured` rather than a fits read it cannot support."""

    def test_internal_read_failure_leaves_both_thresholds_unevaluated(self):
        s = ow.render_machine_limits(_reading(internal_ok=False, internal_free=None,
                                              internal_cap=None, internal_err="OSError"))
        self.assertIn("internal disk unmeasured (OSError)", s)
        self.assertIn("CANNOT be evaluated", s)
        self.assertIn("14–18.5 GiB conversion-output threshold: unmeasured", s)
        self.assertIn("no fits read is possible", s)

    def test_a_failed_read_never_renders_a_conversion_fits_read(self):
        s = ow.render_machine_limits(_reading(internal_ok=False, internal_free=None,
                                              internal_cap=None, internal_err="OSError"))
        for forbidden in ("ABOVE the top of the range", "INSIDE the range",
                          "BELOW the bottom of the range"):
            self.assertNotIn(forbidden, s,
                             "an unmeasured volume may not carry a fits read of any kind")

    def test_t7_unmounted_still_renders_both_thresholds(self):
        s = ow.render_machine_limits(_reading(t7_mounted=False, t7_ok=False, t7_free=None,
                                              t7_cap=None, t7_err="not mounted"))
        self.assertIn("T7 not mounted (a membrane when present)", s)
        self.assertIn("model-pull threshold", s)
        self.assertIn("conversion-output threshold", s)

    def test_sysctl_failure_still_renders_both_thresholds(self):
        s = ow.render_machine_limits(_reading(wired_ok=False, wired_value=None,
                                              wired_err="FileNotFoundError"))
        self.assertIn("iogpu.wired_limit_mb=unmeasured", s)
        self.assertIn("model-pull threshold", s)
        self.assertIn("conversion-output threshold", s)

    def test_a_render_exception_still_returns_a_sentence(self):
        s = ow.render_machine_limits({})
        self.assertIn("MACHINE LIMITS", s)
        self.assertIn("unmeasured", s)
        self.assertIn("no remembered figure is substituted", s)

    def test_no_remembered_figure_appears_in_any_failure_arm(self):
        for s in (ow.render_machine_limits(_reading(internal_ok=False, internal_free=None,
                                                    internal_cap=None, internal_err="E")),
                  ow.render_machine_limits({})):
            for stale in ("13–15 GiB", "13-15 GiB", "407 GiB", "(t748): internal"):
                self.assertNotIn(stale, s)

    def test_a_partial_reading_still_renders_both_thresholds(self):
        """Fail-soft direction: a reading that predates the second threshold must not lose a
        threshold - it falls back to the module constants rather than rendering one of two."""
        partial = _reading()
        for k in ("conversion_output_threshold_gib_low",
                  "conversion_output_threshold_gib_high",
                  "conversion_output_threshold_basis"):
            partial.pop(k)
        s = ow.render_machine_limits(partial)
        self.assertIn("14–18.5 GiB conversion-output threshold", s)
        self.assertIn("conversion threshold basis:", s)


class OneReadTwoComparisons(unittest.TestCase):
    """Arm 5 - ONE live free-space reading, two comparisons. Never two reads that can
    disagree with each other."""

    def test_render_takes_no_second_reading_when_handed_one(self):
        calls = []
        original = ow._read_volume
        try:
            ow._read_volume = lambda path: (calls.append(path), original(path))[1]
            ow.render_machine_limits(_reading())
        finally:
            ow._read_volume = original
        self.assertEqual(calls, [],
                         "a supplied reading must be the ONLY source of the free figure")

    def test_both_clauses_consume_the_same_internal_dict(self):
        seen = []
        original_conv = ow._conversion_clause
        original_pull = ow._internal_clause
        try:
            ow._conversion_clause = lambda internal, low, high: (
                seen.append(id(internal)), original_conv(internal, low, high))[1]
            ow._internal_clause = lambda internal, threshold: (
                seen.append(id(internal)), original_pull(internal, threshold))[1]
            ow.render_machine_limits(_reading())
        finally:
            ow._conversion_clause = original_conv
            ow._internal_clause = original_pull
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0], seen[1],
                         "both thresholds must read the SAME internal reading object")

    def test_the_live_reading_carries_both_thresholds(self):
        r = ow.read_machine_limits()
        for key in ("read_at", "internal", "t7", "wired_limit_mb",
                    "model_pull_threshold_gib", "model_pull_threshold_basis",
                    "conversion_output_threshold_gib_low",
                    "conversion_output_threshold_gib_high",
                    "conversion_output_threshold_basis"):
            self.assertIn(key, r)


class TheRangeIsHonest(unittest.TestCase):
    """Arm 6 - a range read has THREE outcomes and the boundaries fall on a declared side."""

    def test_exactly_at_the_bottom_is_inside_not_below(self):
        s = ow.render_machine_limits(_reading(internal_free=LOW))
        self.assertIn("INSIDE the range", s)
        self.assertNotIn("BELOW the bottom", s)

    def test_a_hair_under_the_bottom_is_below(self):
        s = ow.render_machine_limits(_reading(internal_free=LOW - 0.1))
        self.assertIn("BELOW the bottom of the range", s)

    def test_exactly_at_the_top_is_above_not_inside(self):
        s = ow.render_machine_limits(_reading(internal_free=HIGH))
        self.assertIn("ABOVE the top of the range", s)
        self.assertNotIn("INSIDE the range", s)

    def test_a_hair_under_the_top_is_inside(self):
        s = ow.render_machine_limits(_reading(internal_free=HIGH - 0.1))
        self.assertIn("INSIDE the range", s)

    def test_the_range_renders_without_false_precision(self):
        s = ow.render_machine_limits(_reading())
        self.assertIn("14–18.5 GiB", s)
        self.assertNotIn("14.0", s)

    def test_exactly_one_of_the_three_outcomes_renders_per_arm(self):
        outcomes = ("ABOVE the top of the range", "INSIDE the range",
                    "BELOW the bottom of the range")
        for label, free in REGIONS:
            s = ow.render_machine_limits(_reading(internal_free=free))
            hits = [o for o in outcomes if o in s]
            self.assertEqual(len(hits), 1,
                             f"region [{label}] rendered {len(hits)} range outcomes: {hits}")


class RiderTravelsVerbatim(unittest.TestCase):
    """Arm 7 - the rider is a contiguous value, matched by EQUALITY (F-803-BL-1's cure)."""

    def test_rider_is_carried_verbatim_as_one_contiguous_value(self):
        self.assertEqual(ow.DOES_NOT_SATISFY_RIDER_TIC812, RIDER)

    def test_the_parent_increments_rider_is_untouched(self):
        self.assertEqual(
            ow.DOES_NOT_SATISFY_RIDER_TIC803,
            "this increment does NOT add the sentinel's disk arm, does NOT build the "
            "`cold_unavailable` reader helper, and does NOT rule or start canonical-cold "
            "Increment 2; disk headroom stays unobserved by the sentinel until that arm is "
            "ruled and built.")

    def test_the_rendered_sentence_attributes_no_cause(self):
        """The rider's last clause, enforced: the sentence renders figures and reads, and
        never names a cause for any disk movement."""
        for _label, free in REGIONS:
            s = ow.render_machine_limits(_reading(internal_free=free))
            for cause_word in ("because", "caused by", "due to", "clone", "another process"):
                self.assertNotIn(cause_word, s)


class BasisQuotesAreReal(unittest.TestCase):
    """Arm 8 - each quoted fragment in a basis string is a VERBATIM substring of the evidence
    file. A basis citation that does not appear in its evidence is a fabricated citation."""

    def _evidence(self):
        env = os.environ.get("MACHINE_LIMITS_EVIDENCE", "").strip()
        rel = Path("audit-logs/governance/hoist-preparation-tic748/lane-A-affordability.json")
        if env:
            p = Path(env)
            if p.is_file():
                return p
        for parent in [HERE, *HERE.parents]:
            cand = parent / rel
            if cand.is_file():
                return cand
        return None

    def test_conversion_basis_quotes_appear_verbatim_in_the_evidence(self):
        p = self._evidence()
        if p is None:
            self.skipTest("lane-A evidence file unreachable from this tree (declared skip)")
        blob = json.dumps(json.load(p.open()))
        for quote in ("ANY conversion output larger than ~14 GiB has nowhere to land "
                      "internally",
                      "~18.5 GiB conversion output with NOWHERE INTERNAL TO LAND IT"):
            self.assertIn(quote, blob, "a basis quote must exist in its evidence file")

    def test_the_two_anchors_are_the_numbers_the_code_carries(self):
        p = self._evidence()
        if p is None:
            self.skipTest("lane-A evidence file unreachable from this tree (declared skip)")
        doc = json.load(p.open())
        self.assertIn("~14 GiB", doc["hardware"]["disk"]["BINDING_CONSTRAINT"])
        self.assertEqual(LOW, 14.0)
        rows = doc["affordability"]["ranking"]
        sized = [r for r in rows if r.get("disk_needed_gib") == HIGH]
        self.assertTrue(sized, "the range top must be a figure the evidence actually states")


class BlockIntegrity(unittest.TestCase):
    """Arm 9 - both thresholds survive into the full block, and nothing else moved."""

    def test_both_thresholds_reach_the_standing_substrate_block(self):
        block = ow.render_standing_substrate(812)
        self.assertNotIn(ow.MACHINE_LIMITS_PLACEHOLDER, block)
        self.assertIn("MACHINE LIMITS (read live at", block)
        self.assertIn("model-pull threshold", block)
        self.assertIn("conversion-output threshold", block)

    def test_the_rest_of_the_block_is_untouched(self):
        block = ow.render_standing_substrate(812)
        for verbatim in (
            "THIRTEEN entries, not three",
            "organization-engine-lora (20G",
            "the law of this block is unchanged",
            "THE GAP IS THE JOIN, NOT ABSENCE",
            "THE PINKY — THE ECONOMICS OF A GOVERNED SUBSTRATE",
        ):
            self.assertIn(verbatim, block,
                          "the model inventory and the law of the block are OUT of fence")


if __name__ == "__main__":
    unittest.main(verbosity=2)
