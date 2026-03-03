"""Tests for Chapter 1: Append-Only Event Store."""
import json
import os
import tempfile

import pytest

from src.event_store import append_event, read_current_state, read_full_history


@pytest.fixture
def store_path():
    """Create a temporary JSONL file for testing."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def empty_store(store_path):
    """An empty store file."""
    # Truncate the file
    open(store_path, "w").close()
    return store_path


class TestAppendEvent:
    def test_append_single_event(self, empty_store):
        event = {"id": "evt_001", "kind": "signal", "volume": 10}
        append_event(empty_store, event)

        with open(empty_store) as f:
            lines = f.readlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["id"] == "evt_001"

    def test_append_preserves_existing(self, empty_store):
        append_event(empty_store, {"id": "evt_001", "volume": 10})
        append_event(empty_store, {"id": "evt_002", "volume": 20})

        with open(empty_store) as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_append_same_id_creates_new_line(self, empty_store):
        append_event(empty_store, {"id": "evt_001", "status": "active"})
        append_event(empty_store, {"id": "evt_001", "status": "resolved"})

        with open(empty_store) as f:
            lines = f.readlines()
        assert len(lines) == 2  # Both lines preserved
        assert json.loads(lines[0])["status"] == "active"
        assert json.loads(lines[1])["status"] == "resolved"

    def test_append_requires_id(self, empty_store):
        with pytest.raises(ValueError, match="id"):
            append_event(empty_store, {"kind": "signal", "volume": 10})

    def test_append_creates_file_if_missing(self, tmp_path):
        path = str(tmp_path / "new_store.jsonl")
        append_event(path, {"id": "evt_001", "data": "test"})
        assert os.path.exists(path)

    def test_append_mode_is_atomic(self, empty_store):
        """Append mode ensures no data loss on concurrent writes."""
        for i in range(100):
            append_event(empty_store, {"id": f"evt_{i:03d}", "seq": i})

        with open(empty_store) as f:
            lines = f.readlines()
        assert len(lines) == 100


class TestReadCurrentState:
    def test_latest_entry_wins(self, empty_store):
        append_event(empty_store, {"id": "evt_001", "status": "active", "v": 1})
        append_event(empty_store, {"id": "evt_001", "status": "resolved", "v": 2})

        state = read_current_state(empty_store)
        assert state["evt_001"]["status"] == "resolved"
        assert state["evt_001"]["v"] == 2

    def test_multiple_ids(self, empty_store):
        append_event(empty_store, {"id": "a", "value": 1})
        append_event(empty_store, {"id": "b", "value": 2})
        append_event(empty_store, {"id": "a", "value": 3})

        state = read_current_state(empty_store)
        assert len(state) == 2
        assert state["a"]["value"] == 3
        assert state["b"]["value"] == 2

    def test_empty_file(self, empty_store):
        state = read_current_state(empty_store)
        assert state == {}

    def test_missing_file(self, tmp_path):
        state = read_current_state(str(tmp_path / "nonexistent.jsonl"))
        assert state == {}

    def test_skips_malformed_lines(self, empty_store):
        append_event(empty_store, {"id": "good", "data": "ok"})
        with open(empty_store, "a") as f:
            f.write("this is not json\n")
        append_event(empty_store, {"id": "also_good", "data": "fine"})

        state = read_current_state(empty_store)
        assert len(state) == 2
        assert "good" in state
        assert "also_good" in state


class TestReadFullHistory:
    def test_returns_all_lines(self, empty_store):
        append_event(empty_store, {"id": "a", "v": 1})
        append_event(empty_store, {"id": "a", "v": 2})
        append_event(empty_store, {"id": "b", "v": 1})

        history = read_full_history(empty_store)
        assert len(history) == 3
        assert history[0]["v"] == 1
        assert history[1]["v"] == 2

    def test_preserves_order(self, empty_store):
        for i in range(10):
            append_event(empty_store, {"id": f"evt_{i}", "seq": i})

        history = read_full_history(empty_store)
        seqs = [e["seq"] for e in history]
        assert seqs == list(range(10))

    def test_empty_file(self, empty_store):
        assert read_full_history(empty_store) == []

    def test_missing_file(self, tmp_path):
        assert read_full_history(str(tmp_path / "nope.jsonl")) == []

    def test_skips_malformed_lines(self, empty_store):
        append_event(empty_store, {"id": "ok", "v": 1})
        with open(empty_store, "a") as f:
            f.write("broken\n")
        append_event(empty_store, {"id": "ok", "v": 2})

        history = read_full_history(empty_store)
        assert len(history) == 2
