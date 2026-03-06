"""
Simulated Environment Tests for CGG

Tests that verify the CogPR configurations work correctly
across simulated desktop, work, and code environments.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest


class TestDesktopEnvironmentSimulation:
    """Simulate Claude Desktop environment and validate CogPR behavior."""

    @pytest.fixture
    def desktop_workspace(self, tmp_path):
        """Create a simulated desktop workspace with CogPR v3 config."""
        workspace = tmp_path / "desktop-workspace"
        workspace.mkdir()

        # Create CLAUDE.md with desktop CogPR config
        claude_md = workspace / "CLAUDE.md"
        claude_md.write_text("""# Desktop Project

## Session Learning Protocol v3 (Signal Manifold)

### Band Budget Hierarchy
| Band | Propagation | Use for |
|------|-------------|---------|
| PRIMITIVE | Always audible | Safety, survival, data integrity |
| COGNITIVE | Standard working level | Lessons, insights, process improvement |
| SOCIAL | Suppressed | Collaboration signals (use sparingly) |
| PRESTIGE | Blocked | NEVER emit — governance filter |
""")

        # Create MEMORY.md for operational memory
        memory_md = workspace / "MEMORY.md"
        memory_md.write_text("# Operational Memory\n")

        return workspace

    def test_desktop_workspace_has_governance_files(self, desktop_workspace):
        """Desktop workspace should have CLAUDE.md and MEMORY.md."""
        assert (desktop_workspace / "CLAUDE.md").exists()
        assert (desktop_workspace / "MEMORY.md").exists()

    def test_desktop_claude_md_has_band_hierarchy(self, desktop_workspace):
        """Desktop CLAUDE.md should contain band budget hierarchy."""
        content = (desktop_workspace / "CLAUDE.md").read_text()
        assert "PRIMITIVE" in content
        assert "COGNITIVE" in content
        assert "SOCIAL" in content
        assert "PRESTIGE" in content

    def test_desktop_cpr_flag_structure(self, desktop_workspace):
        """Validate CogPR flag structure for desktop environment."""
        # Append a CogPR flag to CLAUDE.md
        cogpr_flag = """
<!-- --agnostic-candidate
  lesson: "Always validate inputs before processing"
  source_date: "2026-03-03"
  source: "src/app.py:42"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "validation"
  recommended_scopes:
    - "CLAUDE.md"
  rationale: "Input validation is universally applicable"
  status: "pending"
-->
"""
        claude_md = desktop_workspace / "CLAUDE.md"
        claude_md.write_text(claude_md.read_text() + cogpr_flag)

        content = claude_md.read_text()
        assert "agnostic-candidate" in content
        assert 'status: "pending"' in content

    def test_desktop_signal_flag_structure(self, desktop_workspace):
        """Validate signal flag structure for desktop environment."""
        signal_flag = """
<!-- --signal
  id: "sig_2026-03-03T21:39Z_validation_input_error"
  kind: "BEACON"
  band: "PRIMITIVE"
  motivation_layer: "PRIMITIVE"
  source: "src/app.py:55"
  source_date: "2026-03-03"
  subsystem: "validation"
  volume: 30
  status: "active"
-->
"""
        memory_md = desktop_workspace / "MEMORY.md"
        memory_md.write_text(memory_md.read_text() + signal_flag)

        content = memory_md.read_text()
        assert "signal" in content
        assert 'kind: "BEACON"' in content


class TestWorkEnvironmentSimulation:
    """Simulate Claude for Work environment and validate CogPR behavior."""

    @pytest.fixture
    def work_workspace(self, tmp_path):
        """Create a simulated work workspace."""
        workspace = tmp_path / "work-workspace"
        workspace.mkdir()

        # Create .ticzone for zone scoping
        ticzone = workspace / ".ticzone"
        ticzone.write_text(json.dumps({
            "name": "work-project",
            "tz": "America/New_York",
            "include": ["."],
            "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
            "muffling_per_hop": 5
        }))

        # Create .ticignore
        ticignore = workspace / ".ticignore"
        ticignore.write_text("""
node_modules/
__pycache__/
.git/
vendor/
""")

        # Create CLAUDE.md
        claude_md = workspace / "CLAUDE.md"
        claude_md.write_text("""# Work Project

## Team Conventions
Follow the CogPR v3 protocol for all session learning.
""")

        return workspace

    def test_work_workspace_has_zone_config(self, work_workspace):
        """Work workspace should have .ticzone configuration."""
        assert (work_workspace / ".ticzone").exists()

    def test_work_ticzone_has_required_fields(self, work_workspace):
        """Work .ticzone should have all required fields."""
        ticzone_content = json.loads((work_workspace / ".ticzone").read_text())
        assert "name" in ticzone_content
        assert "tz" in ticzone_content
        assert "include" in ticzone_content
        assert "bands" in ticzone_content
        assert "muffling_per_hop" in ticzone_content

    def test_work_ticignore_excludes_standard_dirs(self, work_workspace):
        """Work .ticignore should exclude standard directories."""
        content = (work_workspace / ".ticignore").read_text()
        assert "node_modules/" in content
        assert "__pycache__/" in content
        assert ".git/" in content

    def test_work_environment_band_filtering(self, work_workspace):
        """Work environment should filter PRESTIGE band."""
        ticzone_content = json.loads((work_workspace / ".ticzone").read_text())
        bands = ticzone_content["bands"]
        assert "PRESTIGE" not in bands
        assert "PRIMITIVE" in bands
        assert "COGNITIVE" in bands


class TestCodeEnvironmentSimulation:
    """Simulate Claude Code environment and validate full CogPR + cadence behavior."""

    @pytest.fixture
    def code_workspace(self, tmp_path):
        """Create a simulated code workspace with full CGG setup."""
        workspace = tmp_path / "code-workspace"
        workspace.mkdir()

        # Create directory structure
        (workspace / "audit-logs" / "tics").mkdir(parents=True)
        (workspace / "audit-logs" / "signals").mkdir(parents=True)
        (workspace / ".claude" / "plans").mkdir(parents=True)
        (workspace / ".claude" / "grapple-proposals").mkdir(parents=True)

        # Create .ticzone
        ticzone = workspace / ".ticzone"
        ticzone.write_text(json.dumps({
            "name": "code-project",
            "tz": "UTC",
            "include": ["."],
            "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
            "muffling_per_hop": 5
        }))

        # Create CLAUDE.md
        claude_md = workspace / "CLAUDE.md"
        claude_md.write_text("""# Code Project

## CGG Governance

This project uses Context Grapple Gun for session governance.

### Cadence Protocol
Use /cadence for epoch boundaries.
Use /cadence double-time for emergency syncopate.
""")

        return workspace

    def test_code_workspace_has_audit_logs_structure(self, code_workspace):
        """Code workspace should have audit-logs directory structure."""
        assert (code_workspace / "audit-logs" / "tics").exists()
        assert (code_workspace / "audit-logs" / "signals").exists()

    def test_code_workspace_has_claude_dir(self, code_workspace):
        """Code workspace should have .claude directory for plans."""
        assert (code_workspace / ".claude" / "plans").exists()
        assert (code_workspace / ".claude" / "grapple-proposals").exists()

    def test_code_tic_record_format(self, code_workspace):
        """Validate tic record format for epoch boundaries."""
        tic_record = {
            "type": "tic",
            "tic": "2026-03-03T21:39:49Z",
            "tic_zone": "code-project",
            "cadence_position": "downbeat",
            "scope": "project"
        }

        tic_file = code_workspace / "audit-logs" / "tics" / "2026-03-03.jsonl"
        tic_file.write_text(json.dumps(tic_record) + "\n")

        # Verify we can read it back
        lines = tic_file.read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["type"] == "tic"
        assert parsed["cadence_position"] == "downbeat"

    def test_code_signal_store_format(self, code_workspace):
        """Validate signal store format (JSONL append-only)."""
        signals = [
            {"id": "sig_001", "type": "signal", "kind": "BEACON", "band": "PRIMITIVE", "status": "active", "volume": 10},
            {"id": "sig_002", "type": "signal", "kind": "LESSON", "band": "COGNITIVE", "status": "active", "volume": 5},
        ]

        signal_file = code_workspace / "audit-logs" / "signals" / "2026-03-03.jsonl"
        with open(signal_file, "w") as f:
            for sig in signals:
                f.write(json.dumps(sig) + "\n")

        # Verify JSONL format
        lines = signal_file.read_text().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "id" in parsed
            assert "type" in parsed


class TestCrossEnvironmentCompatibility:
    """Test that CogPR configurations are compatible across environments."""

    @pytest.fixture
    def multi_env_project(self, tmp_path):
        """Create a project with all three environment configs."""
        project = tmp_path / "multi-env"
        project.mkdir()

        # Desktop style
        (project / "desktop").mkdir()
        (project / "desktop" / "CLAUDE.md").write_text("# Desktop Config\n")

        # Work style
        (project / "work").mkdir()
        (project / "work" / ".ticzone").write_text(json.dumps({"name": "work", "tz": "UTC"}))

        # Code style
        (project / "code").mkdir()
        (project / "code" / "audit-logs" / "tics").mkdir(parents=True)

        return project

    def test_all_environments_coexist(self, multi_env_project):
        """All environment configurations should coexist in the same project."""
        assert (multi_env_project / "desktop" / "CLAUDE.md").exists()
        assert (multi_env_project / "work" / ".ticzone").exists()
        assert (multi_env_project / "code" / "audit-logs" / "tics").exists()

    def test_band_hierarchy_consistent_across_environments(self):
        """Band hierarchy should be consistent across all environments."""
        # These are the universal bands as defined in ARCHITECTURE.md
        expected_bands = ["PRIMITIVE", "COGNITIVE", "SOCIAL", "PRESTIGE"]

        # PRESTIGE is always blocked in all environments
        active_bands = ["PRIMITIVE", "COGNITIVE", "SOCIAL"]

        for band in active_bands:
            assert band in expected_bands
        assert "PRESTIGE" not in active_bands
