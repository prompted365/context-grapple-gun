"""Tests for Chapter 4: Human-Gated Review Queue."""
import json
import os
import tempfile

import pytest

from src.review_queue import (
    get_pending,
    get_review_history,
    queue_proposal,
    record_verdict,
)


@pytest.fixture
def store_path():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def empty_store(store_path):
    open(store_path, "w").close()
    return store_path


class TestQueueProposal:
    def test_engineer_submits_bridge_repair(self, empty_store):
        queue_proposal(empty_store, {
            "id": "cpr_001",
            "lesson": "Always validate inputs",
            "source": "src/app.py:42",
        })

        with open(empty_store) as f:
            lines = f.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["id"] == "cpr_001"
        assert entry["status"] == "pending"
        assert "queued_at" in entry

    def test_proposal_needs_an_id(self, empty_store):
        with pytest.raises(ValueError, match="id"):
            queue_proposal(empty_store, {"lesson": "something"})

    def test_proposal_needs_a_lesson(self, empty_store):
        with pytest.raises(ValueError, match="lesson"):
            queue_proposal(empty_store, {"id": "cpr_001"})

    def test_proposal_metadata_preserved(self, empty_store):
        queue_proposal(empty_store, {
            "id": "cpr_001",
            "lesson": "test",
            "band": "COGNITIVE",
            "subsystem": "auth",
        })

        with open(empty_store) as f:
            entry = json.loads(f.readline())
        assert entry["band"] == "COGNITIVE"
        assert entry["subsystem"] == "auth"

    def test_five_proposals_arrive_week_one(self, empty_store):
        for i in range(5):
            queue_proposal(empty_store, {
                "id": f"cpr_{i:03d}",
                "lesson": f"Lesson {i}",
            })

        with open(empty_store) as f:
            assert len(f.readlines()) == 5


class TestGetPending:
    def test_unreviewed_proposals_in_inbox(self, empty_store):
        queue_proposal(empty_store, {
            "id": "cpr_001",
            "lesson": "pending lesson",
        })

        pending = get_pending(empty_store)
        assert len(pending) == 1
        assert pending[0]["lesson"] == "pending lesson"

    def test_approved_proposal_leaves_the_pile(self, empty_store):
        queue_proposal(empty_store, {"id": "cpr_001", "lesson": "will be approved"})
        queue_proposal(empty_store, {"id": "cpr_002", "lesson": "still pending"})
        record_verdict(empty_store, "cpr_001", "approved")

        pending = get_pending(empty_store)
        assert len(pending) == 1
        assert pending[0]["id"] == "cpr_002"

    def test_resubmission_replaces_original(self, empty_store):
        queue_proposal(empty_store, {"id": "cpr_001", "lesson": "v1"})
        queue_proposal(empty_store, {"id": "cpr_001", "lesson": "v2"})

        pending = get_pending(empty_store)
        assert len(pending) == 1
        assert pending[0]["lesson"] == "v2"

    def test_empty_inbox_monday_morning(self, empty_store):
        assert get_pending(empty_store) == []

    def test_no_inbox_no_pending(self, tmp_path):
        assert get_pending(str(tmp_path / "nope.jsonl")) == []


class TestRecordVerdict:
    def test_inspector_approves_good_formula(self, empty_store):
        queue_proposal(empty_store, {"id": "cpr_001", "lesson": "test"})
        result = record_verdict(empty_store, "cpr_001", "approved", "LGTM")

        assert result is True
        pending = get_pending(empty_store)
        assert len(pending) == 0

    def test_inspector_rejects_bad_concrete_ratio(self, empty_store):
        queue_proposal(empty_store, {"id": "cpr_001", "lesson": "test"})
        result = record_verdict(empty_store, "cpr_001", "rejected", "Too narrow")

        assert result is True

    def test_inspector_requests_wind_loading_fix(self, empty_store):
        queue_proposal(empty_store, {"id": "cpr_001", "lesson": "test"})
        result = record_verdict(empty_store, "cpr_001", "edit_requested", "Needs examples")

        assert result is True

    def test_maybe_is_not_a_valid_verdict(self, empty_store):
        queue_proposal(empty_store, {"id": "cpr_001", "lesson": "test"})
        with pytest.raises(ValueError, match="Invalid verdict"):
            record_verdict(empty_store, "cpr_001", "maybe")

    def test_cant_review_nonexistent_proposal(self, empty_store):
        result = record_verdict(empty_store, "nonexistent", "approved")
        assert result is False

    def test_one_verdict_per_proposal_no_retrial(self, empty_store):
        queue_proposal(empty_store, {"id": "cpr_001", "lesson": "test"})
        record_verdict(empty_store, "cpr_001", "approved")
        result = record_verdict(empty_store, "cpr_001", "rejected")

        assert result is False  # Already reviewed

    def test_verdict_carries_annotation_and_time(self, empty_store):
        queue_proposal(empty_store, {"id": "cpr_001", "lesson": "test"})
        record_verdict(empty_store, "cpr_001", "approved", "good stuff")

        history = get_review_history(empty_store)
        assert "verdict_at" in history[0]
        assert history[0]["verdict_notes"] == "good stuff"

    def test_no_inbox_no_verdict(self, tmp_path):
        result = record_verdict(str(tmp_path / "nope.jsonl"), "x", "approved")
        assert result is False


class TestGetReviewHistory:
    def test_history_shows_reviewed_not_pending(self, empty_store):
        queue_proposal(empty_store, {"id": "cpr_001", "lesson": "approved"})
        queue_proposal(empty_store, {"id": "cpr_002", "lesson": "still pending"})
        record_verdict(empty_store, "cpr_001", "approved")

        history = get_review_history(empty_store)
        assert len(history) == 1
        assert history[0]["id"] == "cpr_001"

    def test_approved_rejected_edit_all_in_history(self, empty_store):
        queue_proposal(empty_store, {"id": "cpr_001", "lesson": "a"})
        queue_proposal(empty_store, {"id": "cpr_002", "lesson": "b"})
        queue_proposal(empty_store, {"id": "cpr_003", "lesson": "c"})
        record_verdict(empty_store, "cpr_001", "approved")
        record_verdict(empty_store, "cpr_002", "rejected")
        record_verdict(empty_store, "cpr_003", "edit_requested")

        history = get_review_history(empty_store)
        assert len(history) == 3
        statuses = {h["status"] for h in history}
        assert statuses == {"approved", "rejected", "edit_requested"}

    def test_review_history_in_chronological_order(self, empty_store):
        for i in range(3):
            queue_proposal(empty_store, {"id": f"cpr_{i}", "lesson": f"l{i}"})
        # Verdict in reverse order
        record_verdict(empty_store, "cpr_2", "approved")
        record_verdict(empty_store, "cpr_1", "approved")
        record_verdict(empty_store, "cpr_0", "approved")

        history = get_review_history(empty_store)
        times = [h["verdict_at"] for h in history]
        assert times == sorted(times)

    def test_empty_inbox_no_history(self, empty_store):
        assert get_review_history(empty_store) == []

    def test_no_inbox_no_history(self, tmp_path):
        assert get_review_history(str(tmp_path / "nope.jsonl")) == []
