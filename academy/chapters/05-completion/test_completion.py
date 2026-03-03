"""Tests for Chapter 5: Gamified Completion Layer."""
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from src.completion import (
    check_chapter_status,
    generate_badge_svg,
    generate_certificate_svg,
    get_share_metadata,
    record_completion,
)


# --- Fixtures ---


@pytest.fixture
def store_path():
    """Create a temporary JSONL file for testing."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def project_root(tmp_path):
    """Create a mock project root with chapter directories and test files."""
    chapters_dir = tmp_path / "chapters"
    for chapter in [
        "01-append-only-truth",
        "02-dedup-and-identity",
        "03-signals-and-decay",
        "04-human-gated-review",
    ]:
        chapter_dir = chapters_dir / chapter
        chapter_dir.mkdir(parents=True)
        (chapter_dir / f"test_{chapter.split('-', 1)[0]}.py").write_text(
            "# placeholder test"
        )
    return str(tmp_path)


@pytest.fixture
def all_passed_chapters():
    return {
        "Append-Only Truth": True,
        "Dedup & Identity": True,
        "Signals & Decay": True,
        "Human-Gated Review": True,
    }


@pytest.fixture
def partial_chapters():
    return {
        "Append-Only Truth": True,
        "Dedup & Identity": True,
        "Signals & Decay": False,
        "Human-Gated Review": False,
    }


# --- check_chapter_status ---


class TestCheckChapterStatus:
    @patch("src.completion.subprocess.run")
    def test_all_chapters_pass_ready_to_graduate(self, mock_run, project_root):
        """All chapters pass when pytest returns 0."""
        mock_run.return_value = MagicMock(returncode=0)

        result = check_chapter_status(project_root)

        assert isinstance(result, dict)
        assert len(result) == 4
        assert all(v is True for v in result.values())

    @patch("src.completion.subprocess.run")
    def test_some_chapters_fail_not_ready_yet(self, mock_run, project_root):
        """Chapters with non-zero exit code are marked False."""
        def side_effect(cmd, **kwargs):
            test_path = cmd[3]  # ["python", "-m", "pytest", <path>, ...]
            if "01-append-only-truth" in test_path:
                return MagicMock(returncode=0)
            return MagicMock(returncode=1)

        mock_run.side_effect = side_effect

        result = check_chapter_status(project_root)

        assert result["Append-Only Truth"] is True
        assert result["Dedup & Identity"] is False
        assert result["Signals & Decay"] is False
        assert result["Human-Gated Review"] is False

    @patch("src.completion.subprocess.run")
    def test_no_chapters_pass_fresh_start(self, mock_run, project_root):
        """All chapters fail when pytest returns non-zero."""
        mock_run.return_value = MagicMock(returncode=1)

        result = check_chapter_status(project_root)

        assert all(v is False for v in result.values())

    @patch("src.completion.subprocess.run")
    def test_slow_tests_count_as_failure(self, mock_run, project_root):
        """Timeout is treated as failure."""
        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="pytest", timeout=30)

        result = check_chapter_status(project_root)

        assert all(v is False for v in result.values())

    @patch("src.completion.subprocess.run")
    def test_checks_all_four_governance_chapters(self, mock_run, project_root):
        """Result always contains all four chapter labels."""
        mock_run.return_value = MagicMock(returncode=0)

        result = check_chapter_status(project_root)

        assert "Append-Only Truth" in result
        assert "Dedup & Identity" in result
        assert "Signals & Decay" in result
        assert "Human-Gated Review" in result

    def test_fresh_workspace_no_chapters_yet(self, tmp_path):
        """Missing chapter directories are marked False."""
        # No chapters dir at all
        result = check_chapter_status(str(tmp_path))

        assert all(v is False for v in result.values())

    @patch("src.completion.subprocess.run")
    def test_chapter_dir_without_tests_fails(self, mock_run, tmp_path):
        """Chapter directory without test files is marked False."""
        chapters_dir = tmp_path / "chapters"
        (chapters_dir / "01-append-only-truth").mkdir(parents=True)
        # No test file inside

        result = check_chapter_status(str(tmp_path))

        assert result["Append-Only Truth"] is False
        # subprocess.run should not be called for dir without tests
        for call_args in mock_run.call_args_list:
            assert "01-append-only-truth" not in str(call_args)


# --- generate_certificate_svg ---


class TestGenerateCertificateSvg:
    def test_certificate_is_valid_svg(self, all_passed_chapters):
        svg = generate_certificate_svg("Alice", "2026-03-03", all_passed_chapters)

        assert svg.strip().startswith("<svg")
        assert svg.strip().endswith("</svg>")

    def test_certificate_bears_students_name(self, all_passed_chapters):
        svg = generate_certificate_svg("Alice", "2026-03-03", all_passed_chapters)

        assert "Alice" in svg

    def test_certificate_shows_completion_date(self, all_passed_chapters):
        svg = generate_certificate_svg("Alice", "2026-03-03", all_passed_chapters)

        assert "2026-03-03" in svg

    def test_certificate_lists_chapter_names(self, all_passed_chapters):
        svg = generate_certificate_svg("Alice", "2026-03-03", all_passed_chapters)

        assert "Append-Only Truth" in svg
        assert "Dedup &amp; Identity" in svg
        assert "Signals &amp; Decay" in svg
        assert "Human-Gated Review" in svg

    def test_full_rotation_earns_grappler_title(self, all_passed_chapters):
        svg = generate_certificate_svg("Alice", "2026-03-03", all_passed_chapters)

        assert "GRAPPLER" in svg

    def test_partial_shows_in_progress(self, partial_chapters):
        svg = generate_certificate_svg("Alice", "2026-03-03", partial_chapters)

        assert "IN PROGRESS" in svg

    def test_xss_in_name_safely_escaped(self, all_passed_chapters):
        svg = generate_certificate_svg(
            "Alice <script>alert('xss')</script>",
            "2026-03-03",
            all_passed_chapters,
        )

        assert "<script>" not in svg
        assert "&lt;script&gt;" in svg

    def test_certificate_is_800x520(self, all_passed_chapters):
        svg = generate_certificate_svg("Alice", "2026-03-03", all_passed_chapters)

        assert 'width="800"' in svg
        assert 'height="520"' in svg


# --- generate_badge_svg ---


class TestGenerateBadgeSvg:
    def test_badge_is_valid_svg(self):
        svg = generate_badge_svg("Alice")

        assert svg.strip().startswith("<svg")
        assert svg.strip().endswith("</svg>")

    def test_badge_shows_students_name(self):
        svg = generate_badge_svg("Alice")

        assert "Alice" in svg

    def test_badge_shows_grappler_title(self):
        svg = generate_badge_svg("Alice")

        assert "GRAPPLER" in svg

    def test_badge_more_compact_than_certificate(self):
        badge = generate_badge_svg("Alice")
        cert = generate_certificate_svg(
            "Alice",
            "2026-03-03",
            {"Ch1": True, "Ch2": True, "Ch3": True, "Ch4": True},
        )

        assert len(badge) < len(cert)

    def test_badge_is_200x200(self):
        """Badge has smaller declared dimensions than certificate."""
        badge = generate_badge_svg("Alice")

        assert 'width="200"' in badge
        assert 'height="200"' in badge

    def test_badge_escapes_special_chars(self):
        svg = generate_badge_svg("O'Malley & Friends")

        assert "O&apos;Malley &amp; Friends" in svg


# --- record_completion ---


class TestRecordCompletion:
    def test_completion_recorded_to_audit_log(self, store_path, all_passed_chapters):
        record_completion(store_path, "Alice", all_passed_chapters)

        with open(store_path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["student_name"] == "Alice"

    def test_completion_id_includes_student_name(self, store_path, all_passed_chapters):
        record = record_completion(store_path, "Alice", all_passed_chapters)

        assert "id" in record
        assert "Alice" in record["id"]

    def test_completion_has_timestamp(self, store_path, all_passed_chapters):
        record = record_completion(store_path, "Alice", all_passed_chapters)

        assert "completed_at" in record

    def test_completion_tracks_all_chapters(self, store_path, all_passed_chapters):
        record = record_completion(store_path, "Alice", all_passed_chapters)

        assert "chapters" in record
        assert record["chapters"] == all_passed_chapters

    def test_partial_completion_counts_correctly(self, store_path, partial_chapters):
        record = record_completion(store_path, "Alice", partial_chapters)

        assert record["completed_count"] == 2
        assert record["total_count"] == 4
        assert record["all_passed"] is False

    def test_all_passed_flag_set_on_full_rotation(self, store_path, all_passed_chapters):
        record = record_completion(store_path, "Alice", all_passed_chapters)

        assert record["all_passed"] is True

    def test_multiple_students_complete_independently(self, store_path, all_passed_chapters):
        """Multiple completions append, never overwrite."""
        record_completion(store_path, "Alice", all_passed_chapters)
        record_completion(store_path, "Bob", all_passed_chapters)

        with open(store_path) as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_creates_audit_dir_if_needed(self, tmp_path):
        """Creates parent directories if they do not exist."""
        path = str(tmp_path / "sub" / "dir" / "completions.jsonl")
        chapters = {"Ch1": True}

        record_completion(path, "Alice", chapters)

        assert os.path.exists(path)

    def test_returns_completion_record(self, store_path, all_passed_chapters):
        record = record_completion(store_path, "Alice", all_passed_chapters)

        assert isinstance(record, dict)
        assert record["type"] == "completion"


# --- get_share_metadata ---


class TestGetShareMetadata:
    def test_share_card_has_title_desc_alt(self):
        meta = get_share_metadata("Alice", 4, 4)

        assert "title" in meta
        assert "description" in meta
        assert "image_alt" in meta

    def test_completed_student_gets_celebration(self):
        meta = get_share_metadata("Alice", 4, 4)

        assert "Alice" in meta["title"]
        assert "completed" in meta["title"]

    def test_grappler_in_completion_description(self):
        meta = get_share_metadata("Alice", 4, 4)

        assert "Grappler" in meta["description"]
        assert "4" in meta["description"]

    def test_in_progress_student_keeps_working(self):
        meta = get_share_metadata("Alice", 2, 4)

        assert "Alice" in meta["title"]
        assert "working" in meta["title"]

    def test_partial_progress_shows_count(self):
        meta = get_share_metadata("Alice", 2, 4)

        assert "2" in meta["description"]
        assert "4" in meta["description"]

    def test_alt_text_includes_student_name(self):
        meta = get_share_metadata("Alice", 4, 4)

        assert "Alice" in meta["image_alt"]

    def test_zero_chapters_still_works(self):
        meta = get_share_metadata("Alice", 0, 4)

        assert "0" in meta["description"]
        assert "working" in meta["title"]
