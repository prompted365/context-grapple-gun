"""Tests for Chapter 2: Collaboration Pattern Scanner.

These tests demonstrate how recurring collaboration patterns can be identified,
fingerprinted, and tracked -- the same dedup mechanics from Chapter 1, now
applied to patterns of teamwork and coordination.
"""
import json
import os
import tempfile

import pytest

from src.dedup_scanner import append_if_unique, compute_dedup_hash, scan_for_duplicates


@pytest.fixture
def store_path():
    """Create a temporary JSONL file for testing."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def empty_store(store_path):
    open(store_path, "w").close()
    return store_path


class TestComputePatternHash:
    """Pattern fingerprinting: how we identify recurring collaboration patterns."""

    def test_same_pattern_always_same_fingerprint(self):
        """Weekly standup pattern should hash identically regardless of metadata."""
        event = {"pattern_type": "weekly_standup", "group": "team_a"}
        h1 = compute_dedup_hash(event, ["pattern_type", "group"])
        h2 = compute_dedup_hash(event, ["pattern_type", "group"])
        assert h1 == h2

    def test_fingerprint_is_16_chars(self):
        """Pattern hashes are consistent 16-character fingerprints."""
        event = {"a": "hello", "b": "world"}
        h = compute_dedup_hash(event, ["a", "b"])
        assert len(h) == 16

    def test_different_pattern_different_fingerprint(self):
        """Weekly standup vs daily standup are distinct patterns."""
        e1 = {"pattern_type": "weekly_standup", "group": "team_a"}
        e2 = {"pattern_type": "daily_standup", "group": "team_a"}
        h1 = compute_dedup_hash(e1, ["pattern_type", "group"])
        h2 = compute_dedup_hash(e2, ["pattern_type", "group"])
        assert h1 != h2

    def test_field_order_doesnt_affect_hash(self):
        """Pattern identity is content-based, not order-based."""
        event = {"group": "team_a", "pattern_type": "escalation"}
        h1 = compute_dedup_hash(event, ["pattern_type", "group"])
        h2 = compute_dedup_hash(event, ["group", "pattern_type"])
        assert h1 == h2  # Keys are sorted internally

    def test_missing_fields_dont_crash(self):
        """Partial pattern records still fingerprint cleanly."""
        event = {"pattern_type": "role_assignment"}
        h = compute_dedup_hash(event, ["pattern_type", "missing_field"])
        assert len(h) == 16  # Doesn't crash

    def test_same_pattern_different_teams_same_hash(self):
        """The pattern itself is the identity, team is context."""
        e1 = {"pattern_type": "early_escalation", "context": "team_a"}
        e2 = {"pattern_type": "early_escalation", "context": "team_b"}
        h1 = compute_dedup_hash(e1, ["pattern_type"])
        h2 = compute_dedup_hash(e2, ["pattern_type"])
        assert h1 == h2  # Only pattern_type matters for this hash


class TestScanForRecurringPatterns:
    """Pattern recurrence: when the same collaboration pattern appears multiple times."""

    def test_two_unique_patterns_no_recurrence(self, empty_store):
        """Distinct patterns don't cluster."""
        with open(empty_store, "a") as f:
            f.write(json.dumps({"pattern_type": "standup", "week": 1}) + "\n")
            f.write(json.dumps({"pattern_type": "escalation", "week": 1}) + "\n")

        groups = scan_for_duplicates(empty_store, ["pattern_type"])
        assert groups == []

    def test_catches_repeated_attendance_issue(self, empty_store):
        """Same attendance problem recurring is flagged."""
        with open(empty_store, "a") as f:
            f.write(json.dumps({"pattern_type": "missed_checkin", "member": "henry"}) + "\n")
            f.write(json.dumps({"pattern_type": "role_conflict", "members": ["a", "b"]}) + "\n")
            f.write(json.dumps({"pattern_type": "missed_checkin", "member": "henry"}) + "\n")

        groups = scan_for_duplicates(empty_store, ["pattern_type", "member"])
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_multiple_recurring_issues_grouped_separately(self, empty_store):
        """Each recurring pattern gets its own cluster."""
        with open(empty_store, "a") as f:
            # Attendance issue recurs 3 times
            for _ in range(3):
                f.write(json.dumps({"pattern_type": "missed_checkin", "member": "henry"}) + "\n")
            # Ownership gap recurs 2 times
            for _ in range(2):
                f.write(json.dumps({"pattern_type": "ownership_gap", "area": "database"}) + "\n")
            # One-off escalation (not recurring)
            f.write(json.dumps({"pattern_type": "escalation", "reason": "emergency"}) + "\n")

        groups = scan_for_duplicates(empty_store, ["pattern_type", "member", "area"])
        assert len(groups) == 2

    def test_no_file_no_patterns(self, tmp_path):
        """Missing log returns empty, not error."""
        groups = scan_for_duplicates(str(tmp_path / "nope.jsonl"), ["pattern_type"])
        assert groups == []

    def test_bad_lines_skipped_patterns_still_found(self, empty_store):
        """Malformed entries don't break pattern detection."""
        with open(empty_store, "a") as f:
            f.write(json.dumps({"pattern_type": "standup", "week": 1}) + "\n")
            f.write("corrupted line\n")
            f.write(json.dumps({"pattern_type": "standup", "week": 2}) + "\n")

        groups = scan_for_duplicates(empty_store, ["pattern_type"])
        assert len(groups) == 1


class TestAppendPromotablePattern:
    """Pattern promotion: collaboration patterns become governance candidates."""

    def test_first_pattern_recorded(self, empty_store):
        """New collaboration pattern is captured."""
        result = append_if_unique(
            empty_store,
            {"pattern_type": "weekly_standup", "description": "consistent rhythm"},
            ["pattern_type"],
        )
        assert result is True
        with open(empty_store) as f:
            assert len(f.readlines()) == 1

    def test_duplicate_pattern_not_re_recorded(self, empty_store):
        """Same pattern appearing twice doesn't double-count."""
        event = {"pattern_type": "weekly_standup", "description": "same pattern"}
        append_if_unique(empty_store, event, ["pattern_type"])
        result = append_if_unique(empty_store, event, ["pattern_type"])
        assert result is False
        with open(empty_store) as f:
            assert len(f.readlines()) == 1

    def test_evolved_pattern_is_distinct(self, empty_store):
        """Pattern refinement creates new entry."""
        append_if_unique(
            empty_store,
            {"pattern_type": "standup", "frequency": "weekly"},
            ["pattern_type", "frequency"],
        )
        result = append_if_unique(
            empty_store,
            {"pattern_type": "standup", "frequency": "daily"},
            ["pattern_type", "frequency"],
        )
        assert result is True
        with open(empty_store) as f:
            assert len(f.readlines()) == 2

    def test_new_log_created_on_first_pattern(self, tmp_path):
        """Pattern capture creates log file if needed."""
        path = str(tmp_path / "patterns.jsonl")
        result = append_if_unique(
            path,
            {"pattern_type": "escalation", "threshold": "48h"},
            ["pattern_type"],
        )
        assert result is True
        assert os.path.exists(path)
