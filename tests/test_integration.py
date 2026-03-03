"""
Full CGG Workflow Integration Tests

End-to-end tests that simulate a complete CGG session,
including onboarding, cadence cycles, and signal management.
"""
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Import academy solutions for integration testing
import sys
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "academy" / "src"))

from event_store import append_event, read_current_state, read_full_history
from dedup_scanner import compute_dedup_hash, scan_for_duplicates, append_if_unique
from signal_manager import create_signal, tick_signals, get_active_signals, resolve_signal
from review_queue import queue_proposal, get_pending, record_verdict, get_review_history
from completion import check_chapter_status, generate_certificate_svg, generate_badge_svg


class TestFullCGGWorkflow:
    """Test a complete CGG workflow from setup to cadence."""

    @pytest.fixture
    def cgg_project(self, tmp_path):
        """Create a fully configured CGG project."""
        project = tmp_path / "cgg-project"
        project.mkdir()

        # Create directory structure
        (project / "audit-logs" / "tics").mkdir(parents=True)
        (project / "audit-logs" / "signals").mkdir(parents=True)
        (project / ".claude" / "plans").mkdir(parents=True)
        (project / ".claude" / "grapple-proposals").mkdir(parents=True)

        # Create .ticzone
        (project / ".ticzone").write_text(json.dumps({
            "name": "integration-test",
            "tz": "UTC",
            "include": ["."],
            "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
            "muffling_per_hop": 5
        }, indent=2))

        # Create .ticignore
        (project / ".ticignore").write_text("""
__pycache__/
*.pyc
.git/
.venv/
node_modules/
""")

        # Create CLAUDE.md
        (project / "CLAUDE.md").write_text("""# Integration Test Project

## Project Rules
- Test CGG governance primitives
- Validate cadence cycle

## Session Learning Protocol v3

### Band Budget Hierarchy
| Band | Propagation | Use for |
|------|-------------|---------|
| PRIMITIVE | Always audible | Safety, survival, data integrity |
| COGNITIVE | Standard working level | Lessons, insights, process improvement |
| SOCIAL | Suppressed | Collaboration signals (use sparingly) |
| PRESTIGE | Blocked | NEVER emit — governance filter |
""")

        # Create MEMORY.md
        (project / "MEMORY.md").write_text("# Operational Memory\n\n")

        return project

    def test_project_setup_complete(self, cgg_project):
        """Verify project has all required CGG files."""
        required_files = [
            ".ticzone",
            ".ticignore",
            "CLAUDE.md",
            "MEMORY.md",
        ]
        required_dirs = [
            "audit-logs/tics",
            "audit-logs/signals",
            ".claude/plans",
            ".claude/grapple-proposals",
        ]

        for f in required_files:
            assert (cgg_project / f).exists(), f"Missing {f}"

        for d in required_dirs:
            assert (cgg_project / d).is_dir(), f"Missing directory {d}"

    def test_signal_lifecycle(self, cgg_project):
        """Test complete signal lifecycle: create -> tick -> resolve."""
        signal_file = cgg_project / "audit-logs" / "signals" / "test.jsonl"

        # 1. Create a signal
        sig = create_signal(
            "sig_test_001",
            "BEACON",
            "PRIMITIVE",
            volume=10,
            ttl_hours=24.0,
            escalation_threshold=80
        )
        with open(signal_file, "a") as f:
            f.write(json.dumps(sig) + "\n")

        # 2. Verify it's active
        active = get_active_signals(str(signal_file))
        assert len(active) == 1
        assert active[0]["id"] == "sig_test_001"
        assert active[0]["status"] == "active"

        # 3. Tick the signal
        result = tick_signals(str(signal_file), elapsed_hours=1.0)
        assert result["ticked"] == 1

        # 4. Check volume increased
        active = get_active_signals(str(signal_file))
        assert active[0]["volume"] == 15  # 10 + 5 (default rate)

        # 5. Resolve the signal
        resolved = resolve_signal(str(signal_file), "sig_test_001")
        assert resolved is True

        # 6. Verify it's no longer active
        active = get_active_signals(str(signal_file))
        assert len(active) == 0

    def test_cpr_lifecycle(self, cgg_project):
        """Test complete CPR lifecycle: queue -> review -> verdict."""
        queue_file = cgg_project / "audit-logs" / "cpr-queue.jsonl"

        # 1. Queue a proposal
        queue_proposal(str(queue_file), {
            "id": "cpr_test_001",
            "lesson": "Always validate inputs before processing",
            "source": "test.py:42",
            "band": "COGNITIVE",
            "subsystem": "validation",
        })

        # 2. Verify it's pending
        pending = get_pending(str(queue_file))
        assert len(pending) == 1
        assert pending[0]["lesson"] == "Always validate inputs before processing"

        # 3. Record a verdict
        result = record_verdict(str(queue_file), "cpr_test_001", "approved", "Good lesson!")
        assert result is True

        # 4. Verify it's no longer pending
        pending = get_pending(str(queue_file))
        assert len(pending) == 0

        # 5. Verify it's in history
        history = get_review_history(str(queue_file))
        assert len(history) == 1
        assert history[0]["status"] == "approved"

    def test_tic_emission_and_counting(self, cgg_project):
        """Test tic emission and physical counting."""
        tic_dir = cgg_project / "audit-logs" / "tics"

        # Emit tics across multiple days
        dates = ["2026-03-01", "2026-03-02", "2026-03-03"]
        for i, date in enumerate(dates):
            tic_file = tic_dir / f"{date}.jsonl"
            tic = {
                "type": "tic",
                "tic": f"{date}T12:00:00Z",
                "tic_zone": "integration-test",
                "cadence_position": "downbeat",
                "scope": "project"
            }
            with open(tic_file, "a") as f:
                f.write(json.dumps(tic) + "\n")

        # Count physical tics (the canonical way per ARCHITECTURE.md)
        physical_count = 0
        for tic_file in tic_dir.glob("*.jsonl"):
            with open(tic_file) as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if record.get("type") == "tic":
                            physical_count += 1
                    except json.JSONDecodeError:
                        continue

        assert physical_count == 3

    def test_full_cadence_cycle(self, cgg_project):
        """Test a complete cadence cycle with all phases."""
        tic_dir = cgg_project / "audit-logs" / "tics"
        signal_dir = cgg_project / "audit-logs" / "signals"
        plans_dir = cgg_project / ".claude" / "plans"

        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")

        # Phase 1: Create some session work
        signal_file = signal_dir / f"{today}.jsonl"
        sig = create_signal("sig_session_001", "TENSION", "COGNITIVE", volume=40)
        with open(signal_file, "a") as f:
            f.write(json.dumps(sig) + "\n")

        # Add a CPR to CLAUDE.md
        claude_md = cgg_project / "CLAUDE.md"
        claude_md.write_text(claude_md.read_text() + """

## Session Lessons

- Discovered that signal ordering matters for consistency

<!-- --agnostic-candidate
  lesson: "Signal ordering must be preserved for causality"
  source_date: "{}"
  source: "test.py:100"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "signals"
  status: "pending"
-->
""".format(today))

        # Phase 2: Execute cadence (simulate)
        # Step 0.5: Emit tic
        tic_file = tic_dir / f"{today}.jsonl"
        tic = {
            "type": "tic",
            "tic": now.isoformat(),
            "tic_zone": "integration-test",
            "cadence_position": "downbeat",
            "scope": "project"
        }
        with open(tic_file, "a") as f:
            f.write(json.dumps(tic) + "\n")

        # Step 1: Signal tick
        tick_signals(str(signal_file), elapsed_hours=1.0)

        # Step 4: Write handoff plan
        handoff_id = f"{now.isoformat()}-integration-test"
        plan_content = f"""# [{now.strftime("%Y-%m-%dT%H:%M")}] integration-test

<!-- cgg-handoff
  handoff_id: "{handoff_id}"
  project_dir: "{cgg_project}"
  trigger_version: 1
  generated_at: "{now.isoformat()}"
-->

## Status: Active

## Working State
- Tested signal lifecycle
- Added CPR for signal ordering

## Session Learning & ROI
- Signal ordering matters for causality

## Next Actions
1. Review pending CPR
2. Continue integration testing

## Carried Signals
- sig_session_001 (TENSION, COGNITIVE, volume=45)

<!-- cgg-evaluate
  pending_cprs_expected: 1
  handoff_id: "{handoff_id}"
-->
"""
        plan_file = plans_dir / f"plan-{now.strftime('%Y%m%d-%H%M%S')}.md"
        plan_file.write_text(plan_content)

        # Verify cadence completed
        assert tic_file.exists()
        assert plan_file.exists()

        # Verify tic was written
        tic_lines = tic_file.read_text().strip().split("\n")
        assert len(tic_lines) >= 1
        last_tic = json.loads(tic_lines[-1])
        assert last_tic["cadence_position"] == "downbeat"

        # Verify plan has required sections
        plan_content = plan_file.read_text()
        assert "cgg-handoff" in plan_content
        assert "cgg-evaluate" in plan_content


class TestOnboardingWorkflow:
    """Test the onboarding/academy workflow."""

    @pytest.fixture
    def academy_workspace(self, tmp_path):
        """Create a simulated academy workspace."""
        workspace = tmp_path / "academy-test"
        workspace.mkdir()

        # Copy academy structure
        academy_src = REPO_ROOT / "academy"

        # Create src/ with solutions
        src_dir = workspace / "src"
        src_dir.mkdir()
        for solution in (academy_src / "solutions").glob("*.py"):
            shutil.copy(solution, src_dir / solution.name)

        # Create chapters/ with tests
        chapters_src = academy_src / "chapters"
        chapters_dst = workspace / "chapters"
        if chapters_src.exists():
            shutil.copytree(chapters_src, chapters_dst)

        return workspace

    def test_academy_tests_pass(self, academy_workspace):
        """All academy tests should pass."""
        # Run pytest on the academy workspace
        import subprocess

        result = subprocess.run(
            ["python", "-m", "pytest", str(academy_workspace / "chapters"), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=str(academy_workspace),
            timeout=120
        )

        # All tests should pass (exit code 0)
        assert result.returncode == 0, f"Academy tests failed:\n{result.stdout}\n{result.stderr}"

    def test_certificate_generation(self, academy_workspace):
        """Certificate should be generated for completed courses."""
        chapters = {
            "Append-Only Truth": True,
            "Dedup & Identity": True,
            "Signals & Decay": True,
            "Human-Gated Review": True,
        }

        svg = generate_certificate_svg("TestStudent", "2026-03-03", chapters)

        assert svg.startswith("<svg")
        assert "TestStudent" in svg
        assert "2026-03-03" in svg
        assert "GRAPPLER" in svg

    def test_badge_generation(self):
        """Badge should be generated for completed students."""
        svg = generate_badge_svg("TestStudent")

        assert svg.startswith("<svg")
        assert "TestStudent" in svg
        assert "GRAPPLER" in svg


class TestDashModeWorkflow:
    """Test dash mode (compact/rapid) workflow patterns."""

    @pytest.fixture
    def dash_workspace(self, tmp_path):
        """Create a workspace for dash mode testing."""
        workspace = tmp_path / "dash-test"
        workspace.mkdir()

        (workspace / "audit-logs" / "tics").mkdir(parents=True)
        (workspace / ".ticzone").write_text(json.dumps({
            "name": "dash-test",
            "tz": "UTC"
        }))

        return workspace

    def test_dash_mode_rapid_tic_emission(self, dash_workspace):
        """Dash mode should support rapid tic emission."""
        tic_dir = dash_workspace / "audit-logs" / "tics"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tic_file = tic_dir / f"{today}.jsonl"

        # Emit multiple tics rapidly (simulating dash mode)
        for i in range(5):
            tic = {
                "type": "tic",
                "tic": f"2026-03-03T12:{i:02d}:00Z",
                "tic_zone": "dash-test",
                "cadence_position": "syncopate",
                "scope": "project"
            }
            with open(tic_file, "a") as f:
                f.write(json.dumps(tic) + "\n")

        # Verify all tics were recorded
        lines = tic_file.read_text().strip().split("\n")
        assert len(lines) == 5

        # All should be syncopate (dash mode)
        for line in lines:
            tic = json.loads(line)
            assert tic["cadence_position"] == "syncopate"

    def test_dash_mode_minimal_handoff(self, dash_workspace):
        """Dash mode handoff should be minimal (5 lines max per section)."""
        now = datetime.now(timezone.utc)

        # Minimal handoff format
        handoff = f"""# [{now.strftime("%Y-%m-%dT%H:%M")}] syncopate-test

<!-- cgg-handoff
  handoff_id: "test-id"
  generated_at: "{now.isoformat()}"
-->

## Status: Active

## Working State (compact)
Dash mode testing.

## Next Actions
1. Continue.

## Carried Signals
See /siren status.
"""
        # Count lines per section
        sections = handoff.split("## ")[1:]  # Skip header
        for section in sections:
            lines = [l for l in section.strip().split("\n") if l.strip() and not l.startswith("##")]
            assert len(lines) <= 5, f"Section too long: {len(lines)} lines"


class TestErrorRecovery:
    """Test error recovery and edge cases."""

    def test_corrupted_jsonl_recovery(self, tmp_path):
        """System should recover from corrupted JSONL files."""
        store = tmp_path / "store.jsonl"

        # Write valid data
        append_event(str(store), {"id": "good1", "data": "ok"})

        # Inject corruption
        with open(store, "a") as f:
            f.write("this is not valid json\n")
            f.write("{incomplete json\n")

        # Write more valid data
        append_event(str(store), {"id": "good2", "data": "also ok"})

        # Read should recover gracefully
        state = read_current_state(str(store))
        assert "good1" in state
        assert "good2" in state

    def test_missing_file_handling(self, tmp_path):
        """System should handle missing files gracefully."""
        nonexistent = tmp_path / "does_not_exist.jsonl"

        # These should return empty results, not crash
        state = read_current_state(str(nonexistent))
        assert state == {}

        history = read_full_history(str(nonexistent))
        assert history == []

        active = get_active_signals(str(nonexistent))
        assert active == []

    def test_concurrent_write_safety(self, tmp_path):
        """Append-only stores should be safe for concurrent writes."""
        store = tmp_path / "concurrent.jsonl"

        # Simulate concurrent writes (rapid sequential as proxy)
        for i in range(100):
            append_event(str(store), {"id": f"event_{i:03d}", "seq": i})

        # All events should be preserved
        history = read_full_history(str(store))
        assert len(history) == 100
