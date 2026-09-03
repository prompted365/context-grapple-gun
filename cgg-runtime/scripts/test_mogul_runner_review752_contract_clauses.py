#!/usr/bin/env python3
"""Regression fence for the two /review 752 contract clauses in mogul-runner.sh — the
runner's inline cycle contract text is an AGENT-CONSUMER surface with no call site, so the
text IS the consumer (the /review 743 Q2 precedent). Both clauses were ratified as
refinement rays and their first consumer is this text:

  * C2 · cpr_mogul_queue_refresh_04fdfd8962fe → the COINCIDENT-ARMS face of guard 19
    (ledger.md#presence-observation-fallacy-guard): the queue_refresh instruction must
    demand `shapes_disagreed_on_rows` (a SET, 'empty' when empty, never omitted) beside the
    per-shape count, and must state the mint-time cohort (48 of 265, births 126-467).
    The t752 stepper's A7-752 measured this instrument untouched by the tic-751 checker
    cure — the ray's cure lives here, not on the checker.
  * C1 · cpr_mogul_harmony_invoke_6689bad2ad26 → the WINDOW-vs-POINT axis (THIRD ray on
    ledger.md#disagreement-as-evidence): the harmony_invoke instruction must order the
    read — cause and family BEFORE the salient fields — and forbid a fired watch standing
    as the tic's own event.

The arms are STATIC (parse the runner text) — executing the runner spawns a headless
agent against the live zone. Each clause is pinned to its cycle line so a clause that
drifts to a different cycle (or is deleted) fails loud.

Run:  python3 -m unittest test_mogul_runner_review752_contract_clauses
"""
import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_RUNNER = os.path.join(_HERE, "mogul-runner.sh")


def _cycle_line(cycle: str) -> str:
    text = open(_RUNNER, encoding="utf-8").read()
    lines = [ln for ln in text.splitlines() if re.match(rf"\s*-\s+{re.escape(cycle)}:", ln)]
    assert len(lines) == 1, f"expected exactly one '{cycle}:' instruction line, found {len(lines)}"
    return lines[0]


class QueueRefreshDisagreementSetClause(unittest.TestCase):
    def setUp(self):
        self.line = _cycle_line("queue_refresh")

    def test_demands_the_disagreement_set_key(self):
        self.assertIn("shapes_disagreed_on_rows", self.line)

    def test_set_is_never_omitted_and_empty_is_literal(self):
        self.assertIn("'empty'", self.line)
        self.assertIn("never omit the key", self.line)

    def test_coincident_arms_are_named_provenance_not_evidence(self):
        self.assertIn("PROVENANCE NOTE", self.line)
        self.assertIn("never evidence the second shape was exercised", self.line)

    def test_mint_time_cohort_is_stated_with_its_boundary(self):
        self.assertIn("48 of 265", self.line)
        self.assertIn("126-467", self.line)
        self.assertIn("post-467 mint site", self.line)

    def test_clause_cites_its_ray_and_row(self):
        self.assertIn("COINCIDENT-ARMS", self.line)
        self.assertIn("cpr_mogul_queue_refresh_04fdfd8962fe", self.line)

    def test_the_743_per_shape_count_survives_beside_it(self):
        # the new clause EXTENDS the per-shape disclosure; it must not replace it
        self.assertIn("disclose the count of rows resolved through EACH shape", self.line)


class HarmonyInvokeWindowVsPointClause(unittest.TestCase):
    def setUp(self):
        self.line = _cycle_line("harmony_invoke")

    def test_cause_and_family_are_read_before_the_salient_fields(self):
        i_cause = self.line.find("voice.fallback_reason")
        i_family = self.line.find("voice.fallback_families.current")
        i_before = self.line.find("BEFORE validators_passed")
        self.assertTrue(0 <= i_cause < i_before and 0 <= i_family < i_before,
                        "cause/family must be named ahead of the BEFORE clause")

    def test_a_fired_watch_never_stands_as_the_tics_own_event(self):
        self.assertIn("never let a fired watch stand as this tic's own event", self.line)

    def test_window_and_point_are_each_named_with_their_parts(self):
        self.assertIn("prior_refusal_tics", self.line)
        self.assertIn("denominator", self.line)
        self.assertIn("name its cause and family", self.line)

    def test_vacuous_validators_passed_is_named(self):
        self.assertIn("validators_passed=false is VACUOUS", self.line)

    def test_clause_cites_its_ray_and_row(self):
        self.assertIn("WINDOW-vs-POINT", self.line)
        self.assertIn("cpr_mogul_harmony_invoke_6689bad2ad26", self.line)

    def test_read_only_kernel_sentence_survives(self):
        self.assertIn("Read-only kernel; does not mutate governance state.", self.line)


if __name__ == "__main__":
    unittest.main()
