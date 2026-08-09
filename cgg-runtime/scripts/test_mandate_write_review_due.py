#!/usr/bin/env python3
"""test_mandate_write_review_due.py — queue-truth review_due derivation fixtures.

Fix-site: bk-cadence-ops-review-due-formula-off-by-one (filed tic 690, HIGH —
fourth consecutive off-by-one t687/688/689/690). The old formula stamped
review_due_tic = tic + 1 unconditionally while the queue maturity law
(birth_tic + maturity_tics, default 3) matures rows AT entry. The stamp was the
defect, never the docket: the bench lane derived the docket correctly all four
times. review_due_tic is a PROJECTION — derivation is fail-soft (any read
failure falls back to tic + 1) so the mandate write can never block on it.

Arms cover: matures-at-entry (the observed defect), no-pending default,
past-maturity clamp, future maturity, terminal/birthless/latest-per-id row
exclusion, missing-queue fail-soft, maturity_tics override, and the
build_mandate passthrough.
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "mandate_write", _HERE / "mandate-write.py"
)
mw = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mw)


def _zone_with_queue(rows):
    """Create a tmp zone root carrying audit-logs/cprs/queue.jsonl with rows."""
    zone = Path(tempfile.mkdtemp(prefix="mw-review-due-"))
    qdir = zone / "audit-logs" / "cprs"
    qdir.mkdir(parents=True)
    with open(qdir / "queue.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return zone


class ReviewDueDerivation(unittest.TestCase):
    def test_row_matures_at_entry_stamps_entry_not_entry_plus_one(self):
        """THE observed defect: d80f-shape row (birth 687, tic 690) is due AT 690."""
        zone = _zone_with_queue([
            {"id": "a", "status": "extracted", "birth_tic": 687},
            {"id": "b", "status": "extracted", "birth_tic": 688},
        ])
        markers = mw.compute_due_markers(690, zone_root_path=str(zone))
        self.assertEqual(markers["review_due_tic"], 690)

    def test_no_pending_rows_falls_back_to_default_projection(self):
        zone = _zone_with_queue([])
        markers = mw.compute_due_markers(690, zone_root_path=str(zone))
        self.assertEqual(markers["review_due_tic"], 691)

    def test_past_maturity_clamps_to_current_tic_never_the_past(self):
        zone = _zone_with_queue([
            {"id": "a", "status": "tic_gated", "birth_tic": 685},
        ])
        markers = mw.compute_due_markers(690, zone_root_path=str(zone))
        self.assertEqual(markers["review_due_tic"], 690)

    def test_future_maturity_stamps_the_maturity_tic(self):
        zone = _zone_with_queue([
            {"id": "b", "status": "extracted", "birth_tic": 688},
        ])
        markers = mw.compute_due_markers(690, zone_root_path=str(zone))
        self.assertEqual(markers["review_due_tic"], 691)

    def test_terminal_rows_do_not_contribute_a_clock(self):
        zone = _zone_with_queue([
            {"id": "a", "status": "promoted", "birth_tic": 687},
            {"id": "b", "status": "absorbed", "birth_tic": 686},
        ])
        markers = mw.compute_due_markers(690, zone_root_path=str(zone))
        self.assertEqual(markers["review_due_tic"], 691)

    def test_latest_per_id_wins_terminal_row_supersedes_earlier_pending(self):
        """Append-only discipline: a later promoted row retires the earlier
        extracted row for the same id — the retired row must not keep a clock."""
        zone = _zone_with_queue([
            {"id": "a", "status": "extracted", "birth_tic": 687},
            {"id": "a", "status": "promoted", "birth_tic": 687},
        ])
        markers = mw.compute_due_markers(690, zone_root_path=str(zone))
        self.assertEqual(markers["review_due_tic"], 691)

    def test_birthless_pending_rows_carry_no_maturity_clock(self):
        """C3-shape row: enrichment_eligible with birth_tic null is
        evidence-gated, not clock-gated — alone it yields the default."""
        zone = _zone_with_queue([
            {"id": "c3", "status": "enrichment_eligible", "birth_tic": None},
        ])
        markers = mw.compute_due_markers(690, zone_root_path=str(zone))
        self.assertEqual(markers["review_due_tic"], 691)

    def test_missing_queue_file_fails_soft_to_default(self):
        zone = Path(tempfile.mkdtemp(prefix="mw-review-due-empty-"))
        markers = mw.compute_due_markers(690, zone_root_path=str(zone))
        self.assertEqual(markers["review_due_tic"], 691)

    def test_no_zone_root_keeps_legacy_default(self):
        markers = mw.compute_due_markers(690)
        self.assertEqual(markers["review_due_tic"], 691)

    def test_maturity_tics_override_is_honored(self):
        zone = _zone_with_queue([
            {"id": "a", "status": "extracted", "birth_tic": 687, "maturity_tics": 5},
        ])
        markers = mw.compute_due_markers(690, zone_root_path=str(zone))
        self.assertEqual(markers["review_due_tic"], 692)

    def test_malformed_queue_line_is_skipped_not_fatal(self):
        zone = _zone_with_queue([
            {"id": "a", "status": "extracted", "birth_tic": 687},
        ])
        with open(zone / "audit-logs" / "cprs" / "queue.jsonl", "a") as f:
            f.write("{not json\n")
        markers = mw.compute_due_markers(690, zone_root_path=str(zone))
        self.assertEqual(markers["review_due_tic"], 690)

    def test_build_mandate_passes_zone_root_through_to_the_stamp(self):
        zone = _zone_with_queue([
            {"id": "a", "status": "extracted", "birth_tic": 687},
        ])
        mandate = mw.build_mandate(
            trigger_kind="cadence",
            trigger_source="test",
            tic=690,
            cycles=["queue_refresh"],
            merged_from=[],
            supersedes=[],
            conformation_ref=None,
            runtime_verified=False,
            zone_root_path=str(zone),
        )
        self.assertEqual(mandate["tic_context"]["review_due_tic"], 690)

    def test_other_due_markers_unchanged(self):
        zone = _zone_with_queue([])
        markers = mw.compute_due_markers(690, zone_root_path=str(zone))
        self.assertEqual(markers["memory_mining_due_tic"], 693)
        self.assertEqual(markers["ladder_audit_due_tic"], 695)
        self.assertEqual(markers["deep_audit_due_tic"], 696)
        self.assertEqual(markers["civil_check_due_tic"], 700)


if __name__ == "__main__":
    unittest.main(verbosity=2)
