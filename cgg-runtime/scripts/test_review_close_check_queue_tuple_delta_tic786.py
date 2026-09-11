"""THE PARTIAL-DELTA face (/review 786,
cpr_mogul_review_close_check_6dfe67fd3573, ratified same-pass cure).

Lived shape (t783): queue_state_tuple moved raw_rows 3106->3111 / unique_ids
1330->1333 against the prior artifact with no delta, no selector, and no
declaration — BESIDE a member-exact two-id attribution in the same artifact.
A consumer diffing two artifacts cannot tell NOT-COMPARABLE from
NOT-YET-BUILT; both readings are simultaneously available from the artifact
alone.

Cure: compute_queue_state_tuple_delta — per-key deltas {raw_rows, unique_ids,
promoted, bytes} under the shared tic-keyed selector, cross-tic baseline arm +
same-tic prior arm each carrying the per-arm producer-identity declaration
(/review 785), and an explicit declared-absent membership entry (the
pair_coverage declared-not-fabricated shape extended from published pairs to a
lone point-value counter). Honest nulls, no fabricated zeros.

Run:  python3 -m unittest test_review_close_check_queue_tuple_delta_tic786
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent / "review-close-check.py"
_spec = importlib.util.spec_from_file_location("rcc_qtd_t786", _SCRIPT)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["rcc_qtd_t786"] = rcc
_spec.loader.exec_module(rcc)

_CUR_ID = {"writer_path": "review-close-check.py",
           "writer_sha256_16": "cccccccccccccccc"}

_TUPLE = {"raw_rows": 3121, "unique_ids": 1338, "promoted": 845,
          "bytes": 8502568, "sha256_16": "3e83fcf70afa5aeb"}


def _write_artifact(d, filename, body):
    p = os.path.join(d, filename)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(body, fh)
    return p


class TestFirstBaselineAbsent(unittest.TestCase):
    """No prior artifact: nulls + delta_baseline_absent, never fabricated
    zeros — and the membership entry is declared absent on every path."""

    def test_no_prior_artifact_yields_declared_nulls(self):
        with tempfile.TemporaryDirectory() as d:
            block = rcc.compute_queue_state_tuple_delta(
                d, "tic-786-check.json", 786, dict(_TUPLE),
                current_identity=dict(_CUR_ID))
        self.assertTrue(block["delta_baseline_absent"])
        self.assertEqual(block["baseline"]["reason_absent"],
                         "no_prior_pass_artifact")
        self.assertTrue(all(v is None for v in block["delta"].values()))
        self.assertEqual(block["current"]["raw_rows"], 3121)
        self.assertEqual(block["current_sha256_16"], "3e83fcf70afa5aeb")


class TestCrossTicBaselineDelta(unittest.TestCase):
    """The cross-tic branch: per-key deltas exact against the prior PASS
    artifact under the shared tic-keyed selector, baseline sha carried."""

    def test_delta_exact_with_selector_and_sha(self):
        prior_tuple = {"raw_rows": 3120, "unique_ids": 1337, "promoted": 845,
                       "bytes": 8496599, "sha256_16": "771e5afafdea730e"}
        with tempfile.TemporaryDirectory() as d:
            _write_artifact(d, "tic-785-check.json",
                            {"queue_state_tuple": prior_tuple})
            block = rcc.compute_queue_state_tuple_delta(
                d, "tic-786-check.json", 786, dict(_TUPLE),
                current_identity=dict(_CUR_ID))
        self.assertFalse(block["delta_baseline_absent"])
        self.assertEqual(block["baseline"]["selector"],
                         "tic_keyed_prior_tic_785")
        self.assertEqual(block["baseline"]["artifact"], "tic-785-check.json")
        self.assertEqual(block["baseline"]["sha256_16"], "771e5afafdea730e")
        self.assertEqual(block["delta"],
                         {"raw_rows": 1, "unique_ids": 1, "promoted": 0,
                          "bytes": 5969})


class TestPriorPredatesFields(unittest.TestCase):
    """Older-schema baseline: reason disclosed, deltas stay None."""

    def test_prior_without_tuple_declares_reason(self):
        with tempfile.TemporaryDirectory() as d:
            _write_artifact(d, "tic-785-check.json",
                            {"verdict_counts": {"promoted": 845}})
            block = rcc.compute_queue_state_tuple_delta(
                d, "tic-786-check.json", 786, dict(_TUPLE),
                current_identity=dict(_CUR_ID))
        self.assertTrue(block["delta_baseline_absent"])
        self.assertEqual(block["baseline"]["reason_absent"],
                         "prior_artifact_predates_these_fields")
        self.assertTrue(all(v is None for v in block["delta"].values()))


class TestPerArmProducerIdentity(unittest.TestCase):
    """THE PER-ARM BASELINE-STABILITY face (/review 785) rides this block's
    cross-tic arm: the arm's stamped identity is declared beside the current
    writer's — a declaration, never a verification."""

    def test_cross_tic_arm_changed_true(self):
        prior_tuple = {"raw_rows": 3120, "unique_ids": 1337, "promoted": 845,
                       "bytes": 8496599, "sha256_16": "771e5afafdea730e"}
        with tempfile.TemporaryDirectory() as d:
            _write_artifact(d, "tic-785-check.json", {
                "queue_state_tuple": prior_tuple,
                "producer_identity": {"writer_path": "review-close-check.py",
                                      "writer_sha256_16": "aaaaaaaaaaaaaaaa"}})
            block = rcc.compute_queue_state_tuple_delta(
                d, "tic-786-check.json", 786, dict(_TUPLE),
                current_identity=dict(_CUR_ID))
        arm = block["baseline"]["producer_identity"]
        self.assertEqual(arm["arm_writer_sha256_16"], "aaaaaaaaaaaaaaaa")
        self.assertEqual(arm["current_writer_sha256_16"], "cccccccccccccccc")
        self.assertTrue(arm["arm_producer_identity_changed"])


class TestSameTicPriorObservation(unittest.TestCase):
    """The SAME-TIC RE-OBSERVATION face applied on arrival: a two-fire tic's
    close fire decomposes its movement against the entry fire, with the
    same-tic arm carrying its own identity declaration."""

    def test_same_tic_decomposition_and_arm(self):
        entry_tuple = {"raw_rows": 3121, "unique_ids": 1338, "promoted": 845,
                       "bytes": 8502568, "sha256_16": "3e83fcf70afa5aeb"}
        close_tuple = {"raw_rows": 3123, "unique_ids": 1338, "promoted": 847,
                       "bytes": 8510000, "sha256_16": "dddddddddddddddd"}
        with tempfile.TemporaryDirectory() as d:
            _write_artifact(d, "tic-786-check.json", {
                "queue_state_tuple": entry_tuple,
                "producer_identity": {"writer_path": "review-close-check.py",
                                      "writer_sha256_16": "aaaaaaaaaaaaaaaa"}})
            block = rcc.compute_queue_state_tuple_delta(
                d, "tic-786-check.json", 786, dict(close_tuple),
                current_identity=dict(_CUR_ID))
        st = block["prior_same_tic_observation"]
        self.assertTrue(st["present"])
        self.assertFalse(st["decomposition_absent"])
        self.assertEqual(st["prior_values"]["raw_rows"], 3121)
        self.assertEqual(st["delta_since_prior_same_tic"],
                         {"raw_rows": 2, "unique_ids": 0, "promoted": 2,
                          "bytes": 7432})
        self.assertTrue(st["producer_identity"]["arm_producer_identity_changed"])


class TestMembershipDeclaredAbsent(unittest.TestCase):
    """The born's cure shape: membership is DECLARED absent, never silently
    omitted — on every path, baseline present or not."""

    def test_membership_declared_absent_on_every_path(self):
        with tempfile.TemporaryDirectory() as d:
            bare = rcc.compute_queue_state_tuple_delta(
                d, "tic-786-check.json", 786, dict(_TUPLE))
            _write_artifact(d, "tic-785-check.json",
                            {"queue_state_tuple": dict(_TUPLE)})
            with_base = rcc.compute_queue_state_tuple_delta(
                d, "tic-786-check.json", 786, dict(_TUPLE))
        for block in (bare, with_base):
            self.assertTrue(block["membership"]["declared_absent"])
            self.assertIn("membership_sets", block["membership"]["reason"])


class TestCurrentUnmeasured(unittest.TestCase):
    """A current tuple missing its ints declares current_pass_tuple_unmeasured
    — honest nulls, never fabricated zeros."""

    def test_unmeasured_current_declares_reason(self):
        with tempfile.TemporaryDirectory() as d:
            block = rcc.compute_queue_state_tuple_delta(
                d, "tic-786-check.json", 786,
                {"sha256_16": "3e83fcf70afa5aeb"},
                current_identity=dict(_CUR_ID))
        self.assertTrue(block["delta_baseline_absent"])
        self.assertEqual(block["baseline"]["reason_absent"],
                         "current_pass_tuple_unmeasured")
        self.assertTrue(all(v is None for v in block["delta"].values()))


if __name__ == "__main__":
    unittest.main()
