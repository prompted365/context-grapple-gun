"""
Lightweight Mandate Consumer Regression Tests

Verifies that cgg-gate.sh inline lightweight consumer:
  1. Transitions a lightweight-only mandate to status=consumed
  2. Captures lightweight_results audit field with per-cycle outputs
  3. Honors the race-guard (skips consumption if mandate is no longer pending)

Topology reference: CGG_RUNTIME_TOPOLOGY_AND_LIFECYCLE.md Section 5
"Lightweight mandate consumer (RESOLVED)" + Section 9.2 "Lifecycle fix
(RESOLVED)". Original fix at commit 92e84a4; race-guard at 354f8ab;
authoritative-source refinement at 2f74ea1 (tic 208).

These tests prevent regression: if anyone changes the inline consumer
logic such that the lightweight branch stops transitioning state,
these fixtures fail.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest


CGG_GATE_SCRIPT = (
    Path(__file__).parent.parent / "cgg-runtime" / "hooks" / "cgg-gate.sh"
)


def make_zone(tmp_path: Path) -> Path:
    """Create a minimal CGG zone with .ticzone + audit-logs structure."""
    zone = tmp_path / "zone"
    zone.mkdir()
    (zone / ".ticzone").write_text(json.dumps({"name": "test-zone"}))

    audit = zone / "audit-logs"
    (audit / "mogul" / "mandates").mkdir(parents=True)
    (audit / "cprs").mkdir(parents=True)
    (audit / "signals").mkdir(parents=True)

    return zone


def make_lightweight_mandate(zone: Path, cycles: list[str]) -> Path:
    """Write a synthetic lightweight-only mandate."""
    mandate = {
        "mandate_id": "test-lightweight-tic214",
        "status": "pending",
        "tic_context": 214,
        "cycle_request": {"run_now": cycles},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    mandate_path = zone / "audit-logs" / "mogul" / "mandates" / "current.json"
    mandate_path.write_text(json.dumps(mandate, indent=2))
    return mandate_path


def seed_queue(zone: Path, entries: list[dict]) -> None:
    """Seed a synthetic queue.jsonl for queue_refresh."""
    path = zone / "audit-logs" / "cprs" / "queue.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def seed_signals(zone: Path, entries: list[dict]) -> None:
    """Seed a synthetic active-manifest.jsonl for signal_scan."""
    path = zone / "audit-logs" / "signals" / "active-manifest.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def run_gate(zone: Path, fake_home: Path, stdin_payload: str = "{}") -> tuple[int, str, str]:
    """Run cgg-gate.sh against the synthetic zone, return (rc, stdout, stderr)."""
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(zone)
    env["HOME"] = str(fake_home)
    env["TMPDIR"] = str(fake_home / "tmp")
    (fake_home / "tmp").mkdir(parents=True, exist_ok=True)
    (fake_home / ".claude").mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        ["bash", str(CGG_GATE_SCRIPT)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(zone),
        timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestLightweightMandateConsumer:
    """End-to-end fixtures for cgg-gate.sh inline lightweight branch."""

    @pytest.fixture
    def zone_with_lightweight(self, tmp_path):
        zone = make_zone(tmp_path)
        seed_queue(zone, [
            {"id": "cpr_1", "status": "pending"},
            {"id": "cpr_2", "status": "extracted"},
            {"id": "cpr_3", "status": "promoted"},
        ])
        seed_signals(zone, [
            {"id": "sig_1", "status": "active"},
            {"id": "sig_2", "status": "acknowledged"},
            {"id": "sig_3", "status": "resolved"},
        ])
        make_lightweight_mandate(zone, ["queue_refresh", "signal_scan"])
        return zone

    def test_lightweight_only_mandate_transitions_to_consumed(self, tmp_path, zone_with_lightweight):
        """Lightweight-only mandate must reach status=consumed after gate fires."""
        fake_home = tmp_path / "home"
        rc, stdout, stderr = run_gate(zone_with_lightweight, fake_home)

        assert rc == 0, f"gate exited non-zero: {stderr}"

        mandate = json.loads(
            (zone_with_lightweight / "audit-logs" / "mogul" / "mandates" / "current.json").read_text()
        )
        assert mandate["status"] == "consumed", \
            f"mandate must transition to consumed, got status={mandate['status']!r}"

    def test_lightweight_results_audit_field_populated(self, tmp_path, zone_with_lightweight):
        """consumed mandate must carry lightweight_results with per-cycle outputs."""
        fake_home = tmp_path / "home"
        run_gate(zone_with_lightweight, fake_home)

        mandate = json.loads(
            (zone_with_lightweight / "audit-logs" / "mogul" / "mandates" / "current.json").read_text()
        )
        assert "lightweight_results" in mandate, \
            "consumed mandate must include lightweight_results audit field"
        results = mandate["lightweight_results"]
        assert "queue_refresh=" in results, "lightweight_results must include queue_refresh"
        assert "signal_scan=" in results, "lightweight_results must include signal_scan"

    def test_completed_at_timestamp_set(self, tmp_path, zone_with_lightweight):
        """consumed mandate must have completed_at ISO-8601 timestamp."""
        fake_home = tmp_path / "home"
        run_gate(zone_with_lightweight, fake_home)

        mandate = json.loads(
            (zone_with_lightweight / "audit-logs" / "mogul" / "mandates" / "current.json").read_text()
        )
        assert "completed_at" in mandate, "consumed mandate must record completed_at"
        # ISO-8601 parse roundtrip
        datetime.fromisoformat(mandate["completed_at"])

    def test_queue_refresh_uses_canonical_pending_status_set(self, tmp_path):
        """queue_refresh must count statuses in PENDING_STATUSES set, not invert-filter."""
        zone = make_zone(tmp_path)
        seed_signals(zone, [])
        seed_queue(zone, [
            {"id": "a", "status": "pending"},
            {"id": "b", "status": "enrichment_needed"},
            {"id": "c", "status": "enrichment_eligible"},
            {"id": "d", "status": "extracted"},
            {"id": "e", "status": "review_ready"},
            {"id": "f", "status": "promoted"},
            {"id": "g", "status": "deferred"},
            {"id": "h", "status": "superseded"},
        ])
        make_lightweight_mandate(zone, ["queue_refresh"])

        fake_home = tmp_path / "home"
        run_gate(zone, fake_home)

        mandate = json.loads(
            (zone / "audit-logs" / "mogul" / "mandates" / "current.json").read_text()
        )
        assert mandate["status"] == "consumed"
        # Five entries match PENDING_STATUSES; promoted/deferred/superseded excluded.
        assert "queue_refresh=5_pending" in mandate["lightweight_results"], \
            f"expected 5 pending (PENDING_STATUSES set), got {mandate['lightweight_results']!r}"

    def test_signal_scan_filters_active_acknowledged_working(self, tmp_path):
        """signal_scan must filter active-manifest by {active, acknowledged, working} only."""
        zone = make_zone(tmp_path)
        seed_queue(zone, [])
        seed_signals(zone, [
            {"id": "s1", "status": "active"},
            {"id": "s2", "status": "acknowledged"},
            {"id": "s3", "status": "working"},
            {"id": "s4", "status": "resolved"},
            {"id": "s5", "status": "dismissed"},
        ])
        make_lightweight_mandate(zone, ["signal_scan"])

        fake_home = tmp_path / "home"
        run_gate(zone, fake_home)

        mandate = json.loads(
            (zone / "audit-logs" / "mogul" / "mandates" / "current.json").read_text()
        )
        assert mandate["status"] == "consumed"
        # Three entries match {active, acknowledged, working}; resolved/dismissed excluded.
        assert "signal_scan=3_active" in mandate["lightweight_results"], \
            f"expected 3 active (status filter), got {mandate['lightweight_results']!r}"

    def test_race_guard_skips_consumption_when_already_running(self, tmp_path):
        """Race guard: if mandate transitioned to non-pending between read and consume, skip."""
        zone = make_zone(tmp_path)
        seed_queue(zone, [{"id": "a", "status": "pending"}])
        seed_signals(zone, [])

        # Mandate already running (mogul-runner picked it up first)
        mandate_path = zone / "audit-logs" / "mogul" / "mandates" / "current.json"
        mandate_path.write_text(json.dumps({
            "mandate_id": "test-race",
            "status": "running",
            "tic_context": 214,
            "cycle_request": {"run_now": ["queue_refresh"]},
        }, indent=2))

        fake_home = tmp_path / "home"
        rc, stdout, stderr = run_gate(zone, fake_home)
        assert rc == 0

        # Mandate should still be running — not overwritten
        mandate = json.loads(mandate_path.read_text())
        assert mandate["status"] == "running", \
            "race guard must not overwrite running mandate"
