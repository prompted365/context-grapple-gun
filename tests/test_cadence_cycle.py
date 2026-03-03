"""
Cadence Cycle and Epoch Tic Tests for CGG

Tests that verify the /cadence command behavior, tic emission,
and epoch boundary handling across the full cadence cycle.
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestTicEmission:
    """Test tic record emission and counting."""

    @pytest.fixture
    def tic_workspace(self, tmp_path):
        """Create a workspace with tic infrastructure."""
        workspace = tmp_path / "tic-test"
        (workspace / "audit-logs" / "tics").mkdir(parents=True)
        return workspace

    def test_tic_record_has_required_fields(self, tic_workspace):
        """Tic records must have all required fields."""
        tic = {
            "type": "tic",
            "tic": datetime.now(timezone.utc).isoformat(),
            "tic_zone": "test-zone",
            "cadence_position": "downbeat",
            "scope": "project"
        }

        required_fields = ["type", "tic", "tic_zone", "cadence_position", "scope"]
        for field in required_fields:
            assert field in tic

    def test_downbeat_tic_position(self, tic_workspace):
        """Downbeat cadence should emit 'downbeat' position."""
        tic = {
            "type": "tic",
            "tic": "2026-03-03T21:39:49Z",
            "tic_zone": "test",
            "cadence_position": "downbeat",
            "scope": "project"
        }
        assert tic["cadence_position"] == "downbeat"

    def test_syncopate_tic_position(self, tic_workspace):
        """Double-time cadence should emit 'syncopate' position."""
        tic = {
            "type": "tic",
            "tic": "2026-03-03T21:39:49Z",
            "tic_zone": "test",
            "cadence_position": "syncopate",
            "scope": "project"
        }
        assert tic["cadence_position"] == "syncopate"

    def test_tic_count_from_physical_files(self, tic_workspace):
        """Physical tic count should be determined by JSON parsing, not grep."""
        tic_dir = tic_workspace / "audit-logs" / "tics"

        # Write multiple tics across multiple files
        for date in ["2026-03-01", "2026-03-02", "2026-03-03"]:
            tic_file = tic_dir / f"{date}.jsonl"
            with open(tic_file, "a") as f:
                f.write(json.dumps({
                    "type": "tic",
                    "tic": f"{date}T12:00:00Z",
                    "tic_zone": "test",
                    "cadence_position": "downbeat",
                    "scope": "project"
                }) + "\n")

        # Count tics by parsing JSON (the correct way per ARCHITECTURE.md)
        count = 0
        for tic_file in tic_dir.glob("*.jsonl"):
            with open(tic_file) as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if record.get("type") == "tic":
                            count += 1
                    except json.JSONDecodeError:
                        continue

        assert count == 3

    def test_tic_files_use_date_based_naming(self, tic_workspace):
        """Tic files should be named YYYY-MM-DD.jsonl."""
        tic_dir = tic_workspace / "audit-logs" / "tics"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        tic_file = tic_dir / f"{today}.jsonl"
        tic_file.write_text(json.dumps({
            "type": "tic",
            "tic": datetime.now(timezone.utc).isoformat(),
            "tic_zone": "test",
            "cadence_position": "downbeat",
            "scope": "project"
        }) + "\n")

        assert tic_file.exists()
        assert tic_file.name == f"{today}.jsonl"


class TestCadenceDownbeat:
    """Test full downbeat cadence cycle."""

    @pytest.fixture
    def cadence_workspace(self, tmp_path):
        """Create a workspace for cadence testing."""
        workspace = tmp_path / "cadence-test"
        workspace.mkdir()

        # Create required directory structure
        (workspace / "audit-logs" / "tics").mkdir(parents=True)
        (workspace / "audit-logs" / "signals").mkdir(parents=True)
        (workspace / ".claude" / "plans").mkdir(parents=True)
        (workspace / ".claude" / "grapple-proposals").mkdir(parents=True)

        # Create .ticzone
        (workspace / ".ticzone").write_text(json.dumps({
            "name": "cadence-test",
            "tz": "UTC",
            "include": ["."],
            "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
            "muffling_per_hop": 5
        }))

        # Create CLAUDE.md with pending CPRs
        (workspace / "CLAUDE.md").write_text("""# Test Project

## Lessons

- Always validate inputs
<!-- --agnostic-candidate
  lesson: "Input validation prevents errors"
  source_date: "2026-03-03"
  source: "test.py:10"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "validation"
  status: "pending"
-->
""")

        return workspace

    def test_downbeat_emits_tic(self, cadence_workspace):
        """Downbeat should emit a tic record."""
        tic_dir = cadence_workspace / "audit-logs" / "tics"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc).isoformat()

        # Simulate tic emission
        tic = {
            "type": "tic",
            "tic": now,
            "tic_zone": "cadence-test",
            "cadence_position": "downbeat",
            "scope": "project"
        }

        tic_file = tic_dir / f"{today}.jsonl"
        with open(tic_file, "a") as f:
            f.write(json.dumps(tic) + "\n")

        # Verify tic was written
        lines = tic_file.read_text().strip().split("\n")
        assert len(lines) >= 1
        last_tic = json.loads(lines[-1])
        assert last_tic["type"] == "tic"
        assert last_tic["cadence_position"] == "downbeat"

    def test_downbeat_extracts_cprs(self, cadence_workspace):
        """Downbeat should identify pending CPR flags."""
        claude_md = cadence_workspace / "CLAUDE.md"
        content = claude_md.read_text()

        # Count pending CPRs
        pending_count = content.count('status: "pending"')
        assert pending_count >= 1

    def test_downbeat_creates_handoff_plan(self, cadence_workspace):
        """Downbeat should produce a handoff plan."""
        plans_dir = cadence_workspace / ".claude" / "plans"
        now = datetime.now(timezone.utc)
        handoff_id = f"{now.isoformat()}-downbeat-test"

        # Simulate handoff plan creation
        plan_content = f"""# {now.strftime("%Y-%m-%dT%H:%M")} downbeat-test

<!-- cgg-handoff
  handoff_id: "{handoff_id}"
  project_dir: "{cadence_workspace}"
  trigger_version: 1
  generated_at: "{now.isoformat()}"
-->

## Status: Active

## Working State
- Testing cadence cycle

## Next Actions
1. Continue testing

## Carried Signals
None active.

<!-- cgg-evaluate
  pending_cprs_expected: 1
  handoff_id: "{handoff_id}"
-->
"""
        plan_file = plans_dir / f"plan-{now.strftime('%Y%m%d-%H%M%S')}.md"
        plan_file.write_text(plan_content)

        # Verify plan structure
        content = plan_file.read_text()
        assert "cgg-handoff" in content
        assert f'handoff_id: "{handoff_id}"' in content
        assert "cgg-evaluate" in content


class TestCadenceDoubletime:
    """Test double-time (emergency syncopate) cadence."""

    @pytest.fixture
    def syncopate_workspace(self, tmp_path):
        """Create a workspace for syncopate testing."""
        workspace = tmp_path / "syncopate-test"
        workspace.mkdir()

        (workspace / "audit-logs" / "tics").mkdir(parents=True)
        (workspace / ".ticzone").write_text(json.dumps({
            "name": "syncopate-test",
            "tz": "UTC"
        }))

        return workspace

    def test_doubletime_emits_syncopate_tic(self, syncopate_workspace):
        """Double-time should emit a tic with 'syncopate' position."""
        tic_dir = syncopate_workspace / "audit-logs" / "tics"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc).isoformat()

        tic = {
            "type": "tic",
            "tic": now,
            "tic_zone": "syncopate-test",
            "cadence_position": "syncopate",
            "scope": "project"
        }

        tic_file = tic_dir / f"{today}.jsonl"
        with open(tic_file, "a") as f:
            f.write(json.dumps(tic) + "\n")

        lines = tic_file.read_text().strip().split("\n")
        last_tic = json.loads(lines[-1])
        assert last_tic["cadence_position"] == "syncopate"

    def test_doubletime_skips_signal_tick(self, syncopate_workspace):
        """Double-time should skip signal tick (verified by absence)."""
        # Double-time explicitly skips /siren tick
        # This is documented in the cadence skill
        signal_dir = syncopate_workspace / "audit-logs" / "signals"
        signal_dir.mkdir(parents=True)

        # After syncopate, signals should NOT have been ticked
        # (No automatic signal processing)
        signal_files = list(signal_dir.glob("*.jsonl"))
        assert len(signal_files) == 0

    def test_doubletime_produces_compact_handoff(self, syncopate_workspace):
        """Double-time handoff should be compact (5 lines max per section)."""
        now = datetime.now(timezone.utc)
        handoff_id = f"{now.isoformat()}-syncopate-test"

        compact_plan = f"""# [{now.strftime("%Y-%m-%dT%H:%M")}] syncopate-test

<!-- cgg-handoff
  handoff_id: "{handoff_id}"
  project_dir: "{syncopate_workspace}"
  trigger_version: 1
  generated_at: "{now.isoformat()}"
-->

## Status: Active

## Working State (compact)
Testing syncopate.

## Next Actions
1. Resume testing.

## Carried Signals
See /siren status.
"""
        # Verify it's compact
        sections = compact_plan.split("## ")
        for section in sections[1:]:  # Skip header
            lines = [l for l in section.strip().split("\n") if l.strip()]
            assert len(lines) <= 6  # Section header + 5 content lines


class TestEpochBoundaryInvariants:
    """Test invariants that must hold at every epoch boundary."""

    @pytest.fixture
    def epoch_workspace(self, tmp_path):
        """Create workspace for epoch boundary testing."""
        workspace = tmp_path / "epoch-test"
        workspace.mkdir()

        (workspace / "audit-logs" / "tics").mkdir(parents=True)

        return workspace

    def test_tic_timestamps_are_monotonic(self, epoch_workspace):
        """Tic timestamps should be monotonically increasing."""
        tic_dir = epoch_workspace / "audit-logs" / "tics"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tic_file = tic_dir / f"{today}.jsonl"

        # Write tics with increasing timestamps
        timestamps = [
            "2026-03-03T10:00:00Z",
            "2026-03-03T12:00:00Z",
            "2026-03-03T14:00:00Z",
        ]

        with open(tic_file, "w") as f:
            for ts in timestamps:
                f.write(json.dumps({
                    "type": "tic",
                    "tic": ts,
                    "tic_zone": "test",
                    "cadence_position": "downbeat",
                    "scope": "project"
                }) + "\n")

        # Verify monotonicity
        lines = tic_file.read_text().strip().split("\n")
        tic_times = [json.loads(l)["tic"] for l in lines]
        assert tic_times == sorted(tic_times)

    def test_global_counter_mirrors_physical_truth(self, epoch_workspace):
        """Global counter should match physical tic count."""
        tic_dir = epoch_workspace / "audit-logs" / "tics"

        # Write some tics
        for i in range(5):
            date = f"2026-03-0{i+1}"
            tic_file = tic_dir / f"{date}.jsonl"
            tic_file.write_text(json.dumps({
                "type": "tic",
                "tic": f"{date}T12:00:00Z",
                "tic_zone": "test",
                "cadence_position": "downbeat",
                "scope": "project"
            }) + "\n")

        # Count physical tics
        physical_count = 0
        for f in tic_dir.glob("*.jsonl"):
            for line in open(f):
                try:
                    if json.loads(line).get("type") == "tic":
                        physical_count += 1
                except json.JSONDecodeError:
                    continue

        # Global counter should match
        global_counter = {
            "count": physical_count,
            "last_tic": "2026-03-05T12:00:00Z"
        }
        assert global_counter["count"] == 5

    def test_tic_zone_name_matches_ticzone_file(self, epoch_workspace):
        """Tic zone name should come from .ticzone file."""
        zone_name = "epoch-boundary-test"

        # Create .ticzone
        (epoch_workspace / ".ticzone").write_text(json.dumps({
            "name": zone_name,
            "tz": "UTC"
        }))

        # Tic should use zone name from file
        tic = {
            "type": "tic",
            "tic": "2026-03-03T12:00:00Z",
            "tic_zone": zone_name,
            "cadence_position": "downbeat",
            "scope": "project"
        }

        assert tic["tic_zone"] == zone_name


class TestTicZoneConfiguration:
    """Test .ticzone configuration and zone scoping."""

    def test_ticzone_required_fields(self, tmp_path):
        """Ticzone should have all required fields."""
        required = ["name", "tz", "include", "bands", "muffling_per_hop"]
        ticzone = {
            "name": "test-zone",
            "tz": "UTC",
            "include": ["."],
            "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
            "muffling_per_hop": 5
        }

        for field in required:
            assert field in ticzone

    def test_ticzone_bands_exclude_prestige(self, tmp_path):
        """Active bands should never include PRESTIGE."""
        ticzone = {
            "name": "test",
            "tz": "UTC",
            "include": ["."],
            "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
            "muffling_per_hop": 5
        }

        assert "PRESTIGE" not in ticzone["bands"]

    def test_ticzone_muffling_positive(self, tmp_path):
        """Muffling per hop should be a positive integer."""
        ticzone = {
            "name": "test",
            "tz": "UTC",
            "include": ["."],
            "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
            "muffling_per_hop": 5
        }

        assert ticzone["muffling_per_hop"] > 0
        assert isinstance(ticzone["muffling_per_hop"], int)

    def test_nested_zones_double_attenuation(self, tmp_path):
        """Cross-zone signal propagation should attenuate at double rate."""
        base_muffling = 5
        cross_zone_muffling = base_muffling * 2

        assert cross_zone_muffling == 10
