#!/usr/bin/env python3
"""Tests for the escalation-attention READER in signal_active.py
(bk-age-unknown-escalation-reader, tic 674 — the mouth for the t671 canary).

The contract under guard: manifest-prune (producer) re-heats an unowned silent
carried/dimmed ray and stamps `re_escalation_reminder` — "a reminder marker the
docket can key on" — and renders unknown age as `age_unknown` in
`_v2_projection_inputs`. Until this reader landed, NO consumer keyed on either:
the re-heat effect entered the active set via volume/heat, but the marker
itself was written-never-read (the t673 canary-docket class), and the t671
in-item escalation-eligibility decision had no reader-side expression.

The mouth is two halves:
  - signal_active.py (single-owner predicate module) exports the reader
    predicates: is_reescalated_ray / is_age_unknown_ray /
    escalation_attention_rays;
  - cadence-ops write_conformation consumes them every downbeat (sparse
    per-signal markers + an escalation_attention count) — the demanding
    consumer that makes the marker eat.

Both arms per documented conditional (selftest-fixture discipline).

Run:  python3 -m unittest test_signal_active_escalation_reader
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lib.signal_active import (  # noqa: E402
    is_active_ray,
    is_reescalated_ray,
    is_age_unknown_ray,
    escalation_attention_rays,
)


class TestIsReescalatedRay(unittest.TestCase):
    """Keys on the producer's re_escalation_reminder marker — both arms."""

    def test_marker_true_reads_reescalated(self):
        rec = {"signal_id": "s1", "status": "acknowledged",
               "structural_status": "carried", "volume": 20.0, "heat": 0.24,
               "re_escalation_reminder": True}
        self.assertTrue(is_reescalated_ray(rec))

    def test_marker_absent_or_false_reads_normal(self):
        self.assertFalse(is_reescalated_ray(
            {"signal_id": "s2", "status": "active", "volume": 35}))
        self.assertFalse(is_reescalated_ray(
            {"signal_id": "s3", "status": "acknowledged",
             "re_escalation_reminder": False}))

    def test_prior_provenance_without_reminder_is_not_reescalated(self):
        # A ray that re-escalated in a PAST cycle carries re_escalated_at_tic
        # provenance but no live reminder — the docket keys on the reminder.
        rec = {"signal_id": "s4", "status": "acknowledged",
               "structural_status": "carried", "heat": 0.24,
               "re_escalated_at_tic": 660, "re_escalation_count": 1}
        self.assertFalse(is_reescalated_ray(rec))


class TestIsAgeUnknownRay(unittest.TestCase):
    """age_unknown: projected marker preferred; un-projected records derive it
    (absence of every reinforcement source == unknown, never fresh)."""

    def test_projected_marker_true(self):
        rec = {"signal_id": "s5", "status": "active",
               "_v2_projection_inputs": {"age_unknown": True,
                                         "raw_age_tics": None}}
        self.assertTrue(is_age_unknown_ray(rec))

    def test_projected_marker_false(self):
        rec = {"signal_id": "s6", "status": "active",
               "_v2_projection_inputs": {"age_unknown": False,
                                         "raw_age_tics": 3}}
        self.assertFalse(is_age_unknown_ray(rec))

    def test_unprojected_with_no_source_is_unknown(self):
        self.assertTrue(is_age_unknown_ray(
            {"signal_id": "s7", "status": "active", "volume": 35}))

    def test_unprojected_with_any_source_is_known(self):
        self.assertFalse(is_age_unknown_ray(
            {"signal_id": "s8", "status": "active", "source_tic": 660}))
        self.assertFalse(is_age_unknown_ray(
            {"signal_id": "s9", "status": "active",
             "added_to_manifest_tic": 661}))
        self.assertFalse(is_age_unknown_ray(
            {"signal_id": "s10", "status": "active",
             "volume_history": [{"tic": 662}]}))


class TestEscalationAttentionRays(unittest.TestCase):
    """The docket filter: ACTIVE rays carrying the live reminder marker —
    re-heated by anti-silencing, unowned, needing a DECISION not decay."""

    def _reescalated(self, sid):
        return {"signal_id": sid, "status": "acknowledged",
                "structural_status": "carried", "volume": 20.0, "heat": 0.24,
                "re_escalation_reminder": True}

    def test_filters_to_active_reminder_rays_only(self):
        rays = [
            self._reescalated("attn1"),
            {"signal_id": "plain_active", "status": "active", "volume": 35},
            {"signal_id": "cooled_carry", "status": "acknowledged",
             "structural_status": "carried", "heat": 0.0},
            {"signal_id": "resolved_reminder", "status": "resolved",
             "structural_status": "resolved", "heat": 0.0,
             "re_escalation_reminder": True},  # terminal wins — not attention
        ]
        attn = escalation_attention_rays(rays)
        self.assertEqual([r["signal_id"] for r in attn], ["attn1"])

    def test_empty_when_no_reminders(self):
        rays = [{"signal_id": "plain", "status": "active", "volume": 30}]
        self.assertEqual(escalation_attention_rays(rays), [])

    def test_reescalated_ray_is_active(self):
        # Coherence with the single-owner predicate: a re-heated ray
        # (REESC_VOLUME=20 → heat ~0.24) is active — the docket subset of
        # the active set, never a parallel state machine.
        self.assertTrue(is_active_ray(self._reescalated("attn2")))


if __name__ == "__main__":
    unittest.main()
