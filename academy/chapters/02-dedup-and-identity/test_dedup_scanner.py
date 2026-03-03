"""Tests for Chapter 2: Content-Addressed Dedup Scanner."""
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


class TestComputeDedupHash:
    def test_deterministic(self):
        event = {"source": "file.py:10", "lesson": "always check None"}
        h1 = compute_dedup_hash(event, ["source", "lesson"])
        h2 = compute_dedup_hash(event, ["source", "lesson"])
        assert h1 == h2

    def test_length_is_16(self):
        event = {"a": "hello", "b": "world"}
        h = compute_dedup_hash(event, ["a", "b"])
        assert len(h) == 16

    def test_different_content_different_hash(self):
        e1 = {"source": "file.py:10", "lesson": "check None"}
        e2 = {"source": "file.py:10", "lesson": "check empty"}
        h1 = compute_dedup_hash(e1, ["source", "lesson"])
        h2 = compute_dedup_hash(e2, ["source", "lesson"])
        assert h1 != h2

    def test_key_order_does_not_matter(self):
        event = {"b": "world", "a": "hello"}
        h1 = compute_dedup_hash(event, ["a", "b"])
        h2 = compute_dedup_hash(event, ["b", "a"])
        assert h1 == h2  # Keys are sorted internally

    def test_missing_keys_use_empty_string(self):
        event = {"a": "hello"}
        h = compute_dedup_hash(event, ["a", "missing"])
        assert len(h) == 16  # Doesn't crash

    def test_same_values_same_hash(self):
        e1 = {"source": "x", "lesson": "y", "extra": "ignored"}
        e2 = {"source": "x", "lesson": "y", "different": "also ignored"}
        h1 = compute_dedup_hash(e1, ["source", "lesson"])
        h2 = compute_dedup_hash(e2, ["source", "lesson"])
        assert h1 == h2  # Only dedup keys matter


class TestScanForDuplicates:
    def test_no_duplicates(self, empty_store):
        with open(empty_store, "a") as f:
            f.write(json.dumps({"source": "a.py:1", "lesson": "one"}) + "\n")
            f.write(json.dumps({"source": "b.py:2", "lesson": "two"}) + "\n")

        groups = scan_for_duplicates(empty_store, ["source", "lesson"])
        assert groups == []

    def test_finds_duplicates(self, empty_store):
        with open(empty_store, "a") as f:
            f.write(json.dumps({"source": "a.py:1", "lesson": "same"}) + "\n")
            f.write(json.dumps({"source": "b.py:2", "lesson": "different"}) + "\n")
            f.write(json.dumps({"source": "a.py:1", "lesson": "same"}) + "\n")

        groups = scan_for_duplicates(empty_store, ["source", "lesson"])
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_multiple_duplicate_groups(self, empty_store):
        with open(empty_store, "a") as f:
            for _ in range(3):
                f.write(json.dumps({"source": "a", "lesson": "x"}) + "\n")
            for _ in range(2):
                f.write(json.dumps({"source": "b", "lesson": "y"}) + "\n")
            f.write(json.dumps({"source": "c", "lesson": "z"}) + "\n")  # unique

        groups = scan_for_duplicates(empty_store, ["source", "lesson"])
        assert len(groups) == 2

    def test_missing_file(self, tmp_path):
        groups = scan_for_duplicates(str(tmp_path / "nope.jsonl"), ["a"])
        assert groups == []

    def test_skips_malformed_lines(self, empty_store):
        with open(empty_store, "a") as f:
            f.write(json.dumps({"source": "a", "lesson": "x"}) + "\n")
            f.write("not json\n")
            f.write(json.dumps({"source": "a", "lesson": "x"}) + "\n")

        groups = scan_for_duplicates(empty_store, ["source", "lesson"])
        assert len(groups) == 1


class TestAppendIfUnique:
    def test_appends_new_event(self, empty_store):
        result = append_if_unique(
            empty_store,
            {"source": "a.py:1", "lesson": "new thing"},
            ["source", "lesson"],
        )
        assert result is True
        with open(empty_store) as f:
            assert len(f.readlines()) == 1

    def test_rejects_duplicate(self, empty_store):
        event = {"source": "a.py:1", "lesson": "same thing"}
        append_if_unique(empty_store, event, ["source", "lesson"])
        result = append_if_unique(empty_store, event, ["source", "lesson"])
        assert result is False
        with open(empty_store) as f:
            assert len(f.readlines()) == 1  # Still just one line

    def test_allows_different_content(self, empty_store):
        append_if_unique(
            empty_store,
            {"source": "a.py:1", "lesson": "first"},
            ["source", "lesson"],
        )
        result = append_if_unique(
            empty_store,
            {"source": "a.py:1", "lesson": "second"},
            ["source", "lesson"],
        )
        assert result is True
        with open(empty_store) as f:
            assert len(f.readlines()) == 2

    def test_creates_file_if_missing(self, tmp_path):
        path = str(tmp_path / "new.jsonl")
        result = append_if_unique(
            path,
            {"source": "a", "lesson": "b"},
            ["source", "lesson"],
        )
        assert result is True
        assert os.path.exists(path)
