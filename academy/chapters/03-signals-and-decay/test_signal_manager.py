"""Tests for Chapter 3: Signal Lifecycle Manager."""
import json
import os
import tempfile

import pytest

from src.signal_manager import (
    create_signal,
    get_active_signals,
    resolve_signal,
    tick_signals,
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


def write_signal(path, signal):
    with open(path, "a") as f:
        f.write(json.dumps(signal) + "\n")


class TestCreateSignal:
    def test_emergency_siren_at_defaults(self):
        sig = create_signal("sig_001", "BEACON", "PRIMITIVE")
        assert sig["id"] == "sig_001"
        assert sig["kind"] == "BEACON"
        assert sig["band"] == "PRIMITIVE"
        assert sig["status"] == "active"
        assert sig["volume"] == 10
        assert sig["ttl_hours"] == 24.0
        assert sig["escalation_threshold"] == 80
        assert sig["tick_count"] == 0
        assert sig["escalated"] is False

    def test_keeper_radio_with_custom_settings(self):
        sig = create_signal(
            "sig_002", "TENSION", "COGNITIVE",
            volume=50, ttl_hours=48.0, escalation_threshold=100,
        )
        assert sig["volume"] == 50
        assert sig["ttl_hours"] == 48.0
        assert sig["escalation_threshold"] == 100

    def test_invalid_signal_type_rejected(self):
        with pytest.raises(ValueError, match="Invalid kind"):
            create_signal("sig_003", "INVALID", "PRIMITIVE")

    def test_employee_of_month_auto_muted(self):
        with pytest.raises(ValueError, match="PRESTIGE"):
            create_signal("sig_004", "BEACON", "PRESTIGE")

    def test_signal_timestamped_at_creation(self):
        sig = create_signal("sig_005", "LESSON", "COGNITIVE")
        assert "created_at" in sig


class TestTickSignals:
    def test_mabels_bleat_gets_louder_each_tick(self, empty_store):
        sig = create_signal("sig_001", "BEACON", "PRIMITIVE", volume=10, volume_rate=5)
        write_signal(empty_store, sig)

        tick_signals(empty_store, elapsed_hours=1.0)

        active = get_active_signals(empty_store)
        assert len(active) == 1
        assert active[0]["volume"] == 15  # 10 + 5

    def test_signal_fades_toward_expiry(self, empty_store):
        sig = create_signal("sig_001", "BEACON", "PRIMITIVE", ttl_hours=10.0)
        write_signal(empty_store, sig)

        tick_signals(empty_store, elapsed_hours=3.0)

        active = get_active_signals(empty_store)
        assert active[0]["ttl_hours"] == 7.0

    def test_tick_counter_tracks_signal_age(self, empty_store):
        sig = create_signal("sig_001", "BEACON", "PRIMITIVE")
        write_signal(empty_store, sig)

        tick_signals(empty_store, elapsed_hours=1.0)
        tick_signals(empty_store, elapsed_hours=1.0)

        active = get_active_signals(empty_store)
        assert active[0]["tick_count"] == 2

    def test_pa_announcement_expires_on_schedule(self, empty_store):
        sig = create_signal("sig_001", "BEACON", "PRIMITIVE", ttl_hours=2.0)
        write_signal(empty_store, sig)

        result = tick_signals(empty_store, elapsed_hours=3.0)

        assert result["expired"] == 1
        assert result["total_active"] == 0
        assert get_active_signals(empty_store) == []

    def test_tension_crosses_threshold_escalates(self, empty_store):
        sig = create_signal(
            "sig_001", "TENSION", "COGNITIVE",
            volume=70, volume_rate=15, escalation_threshold=80,
        )
        write_signal(empty_store, sig)

        result = tick_signals(empty_store, elapsed_hours=1.0)

        assert result["escalated"] == 1
        active = get_active_signals(empty_store)
        assert active[0]["escalated"] is True
        assert active[0]["volume"] == 85  # 70 + 15

    def test_expired_signal_stays_silent(self, empty_store):
        sig = create_signal("sig_001", "BEACON", "PRIMITIVE", ttl_hours=1.0)
        write_signal(empty_store, sig)

        tick_signals(empty_store, elapsed_hours=2.0)  # Expires it
        result = tick_signals(empty_store, elapsed_hours=1.0)  # Should not tick

        assert result["ticked"] == 0

    def test_siren_and_radio_tick_together(self, empty_store):
        write_signal(empty_store, create_signal("sig_001", "BEACON", "PRIMITIVE", volume=10))
        write_signal(empty_store, create_signal("sig_002", "TENSION", "COGNITIVE", volume=20))

        result = tick_signals(empty_store, elapsed_hours=1.0)

        assert result["ticked"] == 2
        assert result["total_active"] == 2

    def test_tick_returns_zoo_status_report(self, empty_store):
        result = tick_signals(empty_store, elapsed_hours=1.0)
        assert "ticked" in result
        assert "expired" in result
        assert "escalated" in result
        assert "total_active" in result

    def test_empty_zoo_ticks_harmlessly(self, tmp_path):
        result = tick_signals(str(tmp_path / "nope.jsonl"), elapsed_hours=1.0)
        assert result["ticked"] == 0


class TestGetActiveSignals:
    def test_active_siren_heard_expired_silent(self, empty_store):
        write_signal(empty_store, create_signal("sig_001", "BEACON", "PRIMITIVE"))
        expired = create_signal("sig_002", "BEACON", "PRIMITIVE")
        expired["status"] = "expired"
        write_signal(empty_store, expired)

        active = get_active_signals(empty_store)
        assert len(active) == 1
        assert active[0]["id"] == "sig_001"

    def test_latest_signal_state_is_truth(self, empty_store):
        sig = create_signal("sig_001", "BEACON", "PRIMITIVE", volume=10)
        write_signal(empty_store, sig)
        sig["volume"] = 99
        write_signal(empty_store, sig)

        active = get_active_signals(empty_store)
        assert len(active) == 1
        assert active[0]["volume"] == 99

    def test_quiet_zoo_no_active_signals(self, empty_store):
        assert get_active_signals(empty_store) == []

    def test_no_log_no_signals(self, tmp_path):
        assert get_active_signals(str(tmp_path / "nope.jsonl")) == []


class TestResolveSignal:
    def test_petting_zoo_staff_handles_mabel(self, empty_store):
        write_signal(empty_store, create_signal("sig_001", "BEACON", "PRIMITIVE"))

        result = resolve_signal(empty_store, "sig_001")

        assert result is True
        assert get_active_signals(empty_store) == []

    def test_cant_handle_nonexistent_signal(self, empty_store):
        assert resolve_signal(empty_store, "nonexistent") is False

    def test_cant_resolve_expired_announcement(self, empty_store):
        sig = create_signal("sig_001", "BEACON", "PRIMITIVE")
        sig["status"] = "expired"
        write_signal(empty_store, sig)

        assert resolve_signal(empty_store, "sig_001") is False

    def test_no_log_nothing_to_resolve(self, tmp_path):
        assert resolve_signal(str(tmp_path / "nope.jsonl"), "sig_001") is False
