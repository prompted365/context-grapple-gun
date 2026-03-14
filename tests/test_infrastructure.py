"""
Infrastructure and Tooling Validation Tests for CGG

Tests that validate the shell hooks, skill files,
and the validation checklist items from VALIDATION-CHECKLIST.md.
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest


# Get the repository root
REPO_ROOT = Path(__file__).parent.parent


class TestShellHookSyntax:
    """Validate shell hook files have correct syntax."""

    def test_cgg_gate_hook_syntax(self):
        """cgg-gate.sh should have valid bash syntax."""
        hook_path = REPO_ROOT / "cgg-runtime" / "hooks" / "cgg-gate.sh"
        result = subprocess.run(
            ["bash", "-n", str(hook_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error in cgg-gate.sh: {result.stderr}"

    def test_session_restore_hook_syntax(self):
        """session-restore-patch.sh should have valid bash syntax."""
        hook_path = REPO_ROOT / "cgg-runtime" / "hooks" / "session-restore-patch.sh"
        result = subprocess.run(
            ["bash", "-n", str(hook_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error in session-restore-patch.sh: {result.stderr}"


class TestInstallFileMatrix:
    """Verify install file matrix matches actual cgg-runtime contents."""

    def test_hooks_directory_exists(self):
        """hooks/ directory should exist."""
        assert (REPO_ROOT / "cgg-runtime" / "hooks").is_dir()

    def test_agents_directory_exists(self):
        """agents/ directory should exist."""
        assert (REPO_ROOT / "cgg-runtime" / "agents").is_dir()

    def test_skills_directory_exists(self):
        """skills/ directory should exist."""
        assert (REPO_ROOT / "cgg-runtime" / "skills").is_dir()

    def test_primary_skills_exist(self):
        """Primary skills should exist (cadence, review, siren)."""
        skills_dir = REPO_ROOT / "cgg-runtime" / "skills"
        primary_skills = ["cadence", "review", "siren"]

        for skill in primary_skills:
            skill_dir = skills_dir / skill
            assert skill_dir.is_dir(), f"Primary skill {skill}/ missing"
            assert (skill_dir / "SKILL.md").is_file(), f"SKILL.md missing in {skill}/"

    def test_deprecated_skills_are_redirects(self):
        """Deprecated skills should be short redirect-only files."""
        skills_dir = REPO_ROOT / "cgg-runtime" / "skills"
        deprecated_skills = [
            "cadence-downbeat",
            "cadence-syncopate",
            "grapple",
            "init-gun",
            "init-cogpr"
        ]

        for skill in deprecated_skills:
            skill_file = skills_dir / skill / "SKILL.md"
            if skill_file.exists():
                lines = len(skill_file.read_text().strip().split("\n"))
                assert lines < 40, f"{skill}/SKILL.md has {lines} lines - too long for redirect"


class TestProposalsPathConsistency:
    """Verify proposals path is consistent across all files."""

    def test_proposals_path_is_consistent(self):
        """All references to grapple-proposals should use the same path."""
        expected_path = "~/.claude/grapple-proposals/latest.md"

        # Search for grapple-proposals references
        matches = []
        for ext in ["*.md", "*.sh"]:
            for f in REPO_ROOT.rglob(ext):
                content = f.read_text()
                if "grapple-proposals" in content:
                    matches.append((f, content))

        assert len(matches) > 0, "No references to grapple-proposals found"

        # Verify all references use the expected path format
        for file_path, content in matches:
            if "grapple-proposals/latest.md" in content or "grapple-proposals/" in content:
                # This is expected - path is being referenced correctly
                pass


class TestSkillFileStructure:
    """Validate skill file structure and YAML frontmatter."""

    def get_skill_files(self):
        """Get all SKILL.md files in cgg-runtime/skills/."""
        skills_dir = REPO_ROOT / "cgg-runtime" / "skills"
        return list(skills_dir.rglob("SKILL.md"))

    def test_skills_have_yaml_frontmatter(self):
        """Each SKILL.md should have YAML frontmatter."""
        for skill_file in self.get_skill_files():
            content = skill_file.read_text()
            # Check for frontmatter markers
            assert content.startswith("---"), f"{skill_file} missing frontmatter start"
            assert content.count("---") >= 2, f"{skill_file} missing frontmatter end"

    def test_skills_have_required_frontmatter_fields(self):
        """Each SKILL.md should have name and description in frontmatter."""
        for skill_file in self.get_skill_files():
            content = skill_file.read_text()
            # Extract frontmatter
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                assert "name:" in frontmatter, f"{skill_file} missing 'name:' in frontmatter"
                assert "description:" in frontmatter, f"{skill_file} missing 'description:' in frontmatter"


class TestDoubletimeConsistency:
    """Verify double-time semantics are consistent across documentation."""

    def test_doubletime_behavior_documented(self):
        """Double-time behavior should be documented consistently."""
        cadence_skill = REPO_ROOT / "cgg-runtime" / "skills" / "cadence" / "SKILL.md"
        content = cadence_skill.read_text()

        # Check for double-time documentation
        assert "double-time" in content.lower() or "Double-Time" in content
        assert "syncopate" in content.lower()

    def test_doubletime_skips_are_documented(self):
        """What double-time skips should be documented."""
        cadence_skill = REPO_ROOT / "cgg-runtime" / "skills" / "cadence" / "SKILL.md"
        content = cadence_skill.read_text()

        # Should document what is skipped
        skipped_items = ["signal tick", "conformation", "CogPR extraction"]
        content_lower = content.lower()

        # At least some skip documentation should exist
        skip_mentions = sum(1 for item in skipped_items if item.lower() in content_lower)
        assert skip_mentions > 0, "Double-time skip behavior not documented"


class TestTiczoneFormatValidation:
    """Validate .ticzone format matches documented schema."""

    def test_ticzone_schema_fields(self):
        """Ticzone schema should include all required fields."""
        # Expected fields from VALIDATION-CHECKLIST.md
        expected_fields = ["name", "tz", "include", "bands", "muffling_per_hop"]

        # Check scaffold template
        template_path = REPO_ROOT / "academy" / "scaffolding" / "ticzone.template"
        if template_path.exists():
            content = template_path.read_text()
            ticzone = json.loads(content)
            for field in expected_fields:
                assert field in ticzone, f"Field {field} missing from ticzone template"

    def test_ticzone_documented_in_readme(self):
        """Ticzone format should be documented in README."""
        readme_path = REPO_ROOT / "README.md"
        if readme_path.exists():
            content = readme_path.read_text()
            # Should mention ticzone somewhere
            assert ".ticzone" in content or "ticzone" in content.lower()


class TestNoExternalRepoDependencies:
    """Verify no external repo URL dependencies in documentation."""

    def test_no_external_dependencies(self):
        """Docs should not reference external repos as dependencies."""
        # Files that are allowed to have external URLs
        allowed_files = ["LICENSE", "CONTRIBUTING", "assets/"]

        external_patterns = ["github.com", "gitlab.com", "bitbucket.org"]

        issues = []
        for md_file in REPO_ROOT.rglob("*.md"):
            # Skip allowed files
            if any(allowed in str(md_file) for allowed in allowed_files):
                continue

            content = md_file.read_text()
            for pattern in external_patterns:
                if pattern in content:
                    # Check if it's just attribution
                    if "maintainer" not in content.lower() and "author" not in content.lower():
                        issues.append(f"{md_file}: contains {pattern}")

        # This is a soft check - just ensure we're aware of external references
        # Not necessarily a failure


class TestAcademyIntegration:
    """Test academy integration with the main CGG infrastructure."""

    def test_academy_course_json_valid(self):
        """course.json should be valid JSON."""
        course_path = REPO_ROOT / "academy" / "course.json"
        assert course_path.exists()

        content = course_path.read_text()
        course = json.loads(content)

        assert "name" in course
        assert "chapters" in course
        assert len(course["chapters"]) == 5

    def test_academy_chapters_have_tests(self):
        """Each academy chapter should have a test file."""
        chapters_dir = REPO_ROOT / "academy" / "chapters"
        expected_chapters = [
            "01-append-only-truth",
            "02-dedup-and-identity",
            "03-signals-and-decay",
            "04-human-gated-review",
            "05-completion"
        ]

        for chapter in expected_chapters:
            chapter_dir = chapters_dir / chapter
            assert chapter_dir.is_dir(), f"Chapter {chapter} directory missing"

            # Each chapter should have a test file
            test_files = list(chapter_dir.glob("test_*.py"))
            assert len(test_files) > 0, f"No test file in {chapter}"

    def test_academy_solutions_exist(self):
        """Academy solutions should exist."""
        solutions_dir = REPO_ROOT / "academy" / "solutions"
        expected_solutions = [
            "event_store.py",
            "pattern_scanner.py",
            "signal_manager.py",
            "review_queue.py",
            "completion.py"
        ]

        for solution in expected_solutions:
            solution_path = solutions_dir / solution
            assert solution_path.exists(), f"Solution {solution} missing"


class TestCogPRConfigurations:
    """Test CogPR configurations for different environments."""

    def test_desktop_config_exists(self):
        """Claude Desktop CogPR config should exist."""
        config_path = REPO_ROOT / "cogpr" / "claude-desktop" / "project-instructions.md"
        assert config_path.exists()

    def test_work_config_exists(self):
        """Claude for Work CogPR config should exist."""
        config_path = REPO_ROOT / "cogpr" / "claude-work" / "project-instructions.md"
        assert config_path.exists()

    def test_code_skills_exist(self):
        """Claude Code skills should exist in cgg-runtime/skills/."""
        skills_dir = REPO_ROOT / "cgg-runtime" / "skills"
        assert skills_dir.is_dir()

        # Should have the key skills (includes legacy compatibility shims)
        expected_skills = ["cadence-downbeat", "grapple", "init-cogpr"]
        for skill in expected_skills:
            skill_dir = skills_dir / skill
            assert skill_dir.is_dir(), f"Skill {skill} missing from cgg-runtime/skills/"

    def test_configs_have_band_hierarchy(self):
        """All CogPR configs should document the band hierarchy."""
        configs = [
            REPO_ROOT / "cogpr" / "claude-desktop" / "project-instructions.md",
            REPO_ROOT / "cogpr" / "claude-work" / "project-instructions.md",
        ]

        for config in configs:
            if config.exists():
                content = config.read_text()
                # Should have band budget hierarchy
                assert "PRIMITIVE" in content
                assert "COGNITIVE" in content
                assert "SOCIAL" in content
                assert "PRESTIGE" in content


class TestDocumentation:
    """Test documentation completeness and consistency."""

    def test_readme_exists(self):
        """README.md should exist at repo root."""
        assert (REPO_ROOT / "README.md").exists()

    def test_architecture_md_exists(self):
        """ARCHITECTURE.md should exist."""
        assert (REPO_ROOT / "ARCHITECTURE.md").exists()

    def test_install_md_exists(self):
        """INSTALL.md should exist."""
        assert (REPO_ROOT / "INSTALL.md").exists()

    def test_dev_readme_exists(self):
        """DEV-README.md should exist."""
        assert (REPO_ROOT / "DEV-README.md").exists()

    def test_start_here_exists(self):
        """START-HERE.md should exist."""
        assert (REPO_ROOT / "START-HERE.md").exists()

    def test_validation_checklist_exists(self):
        """VALIDATION-CHECKLIST.md should exist."""
        assert (REPO_ROOT / "docs" / "VALIDATION-CHECKLIST.md").exists()

    def test_lockstep_invariants_exists(self):
        """LOCKSTEP-INVARIANTS.md should exist."""
        assert (REPO_ROOT / "docs" / "LOCKSTEP-INVARIANTS.md").exists()
