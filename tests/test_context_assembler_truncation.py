"""Tests for ContextAssembler skill truncation and context size estimation."""

import logging
import logging.handlers
from pathlib import Path
from unittest.mock import MagicMock, patch

from kernel.context_assembler import ContextAssembler


class TestTruncateSkillContent:
    """Tests for _truncate_skill_content method."""

    def test_truncates_oversized_content_with_marker(self, tmp_path: Path) -> None:
        """Content exceeding max_chars is hard-truncated at line boundary with marker."""
        assembler = ContextAssembler(tmp_path)
        content = "A" * 500
        result = assembler._truncate_skill_content(content, 100)
        # No newlines in content, so it falls back to hard cut at max_chars
        assert len(result.split("\n...[TRUNCATED]")[0]) == 100
        assert result.endswith("\n...[TRUNCATED]")

    def test_summary_mode_keeps_intro_and_first_section(self, tmp_path: Path) -> None:
        """Content with ## headings gets truncated to intro+first section."""
        assembler = ContextAssembler(tmp_path)
        content = (
            "# Skill Title\n"
            "\n"
            "Introduction paragraph.\n"
            "\n"
            "## First Section\n"
            "\n"
            "First section content.\n"
            "\n"
            "## Second Section\n"
            "\n"
            "Second section content that is very long.\n"
        )
        # Set max_chars large enough for intro+first section but less than total
        result = assembler._truncate_skill_content(content, len(content) - 10)
        assert "# Skill Title" in result
        assert "## First Section" in result
        assert "## Second Section" not in result
        assert "[TRUNCATED - see individual skill files for full content]" in result

    def test_content_under_limit_passes_through_unchanged(self, tmp_path: Path) -> None:
        """Content under max_chars is returned unchanged."""
        assembler = ContextAssembler(tmp_path)
        content = "Short content"
        result = assembler._truncate_skill_content(content, 1000)
        assert result == content

    def test_summary_mode_falls_back_to_hard_truncate(self, tmp_path: Path) -> None:
        """If summary is still too long, falls back to hard truncate at line boundary."""
        assembler = ContextAssembler(tmp_path)
        # Create content where the intro+first section is still too long
        content = (
            "# Title\n"
            "\n" + "A" * 500 + "\n"
            "\n"
            "## First Section\n"
            "\n" + "B" * 500 + "\n"
            "\n"
            "## Second Section\n"
            "\n"
            "End content.\n"
        )
        result = assembler._truncate_skill_content(content, 50)
        assert result.endswith("\n...[TRUNCATED]")
        # The content before the marker should be cut at the last newline before 50 chars
        before_marker = result.split("\n...[TRUNCATED]")[0]
        assert len(before_marker) <= 50
        # Should cut at line boundary (last newline before max_chars)
        assert before_marker.endswith("\n") or "\n" not in content[:50]

    def test_no_headings_hard_truncates(self, tmp_path: Path) -> None:
        """Content without ## headings gets hard-truncated at line boundary."""
        assembler = ContextAssembler(tmp_path)
        content = "No headings here, just plain text. " * 100
        result = assembler._truncate_skill_content(content, 200)
        assert result.endswith("\n...[TRUNCATED]")
        before_marker = result.split("\n...[TRUNCATED]")[0]
        # No newlines in content, so falls back to hard cut at max_chars
        assert len(before_marker) == 200

    def test_single_heading_hard_truncates(self, tmp_path: Path) -> None:
        """Content with only one ## heading gets hard-truncated."""
        assembler = ContextAssembler(tmp_path)
        content = "# Title\n\n## Only Section\n\n" + "X" * 500 + "\n"
        result = assembler._truncate_skill_content(content, 50)
        assert result.endswith("\n...[TRUNCATED]")


class TestEstimateTotalContextSize:
    """Tests for _estimate_total_context_size method."""

    def test_returns_correct_total(self, tmp_path: Path) -> None:
        """Returns sum of all section lengths."""
        assembler = ContextAssembler(tmp_path)
        sections = ["abc", "defgh", "ij"]
        result = assembler._estimate_total_context_size(sections)
        assert result == 10

    def test_returns_zero_for_empty(self, tmp_path: Path) -> None:
        """Returns 0 for empty list."""
        assembler = ContextAssembler(tmp_path)
        result = assembler._estimate_total_context_size([])
        assert result == 0

    def test_warning_emitted_when_over_100k(self, tmp_path: Path) -> None:
        """Warning is emitted via logger when context exceeds 100K chars."""
        assembler = ContextAssembler(tmp_path)
        sections = ["X" * 100001]
        logger = logging.getLogger("kernel.context_assembler")
        # Remove stale handlers that may reference closed streams
        stale_handlers = list(logger.handlers)
        for h in stale_handlers:
            logger.removeHandler(h)
        # Add a fresh handler to capture the warning
        handler = logging.handlers.MemoryHandler(capacity=100)
        handler.setLevel(logging.WARNING)
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        original_propagate = logger.propagate
        logger.propagate = True
        try:
            assembler._estimate_total_context_size(sections)
        finally:
            logger.removeHandler(handler)
            logger.propagate = original_propagate
            for h in stale_handlers:
                logger.addHandler(h)
        # Check the records captured by the handler
        records = handler.buffer
        assert len(records) == 1
        msg = records[0].getMessage()
        assert "[警告]" in msg
        assert "100001 字符" in msg
        assert "超出推荐限制" in msg

    def test_no_warning_when_under_100k(self, tmp_path: Path) -> None:
        """No warning when context is under 100K chars."""
        assembler = ContextAssembler(tmp_path)
        sections = ["X" * 50000]
        logger = logging.getLogger("kernel.context_assembler")
        stale_handlers = list(logger.handlers)
        for h in stale_handlers:
            logger.removeHandler(h)
        handler = logging.handlers.MemoryHandler(capacity=100)
        handler.setLevel(logging.WARNING)
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        original_propagate = logger.propagate
        logger.propagate = False
        try:
            assembler._estimate_total_context_size(sections)
        finally:
            logger.removeHandler(handler)
            logger.propagate = original_propagate
            for h in stale_handlers:
                logger.addHandler(h)
        assert len(handler.buffer) == 0

    def test_warning_at_boundary(self, tmp_path: Path) -> None:
        """No warning at exactly 100000 chars (only > triggers)."""
        assembler = ContextAssembler(tmp_path)
        sections = ["X" * 100000]
        logger = logging.getLogger("kernel.context_assembler")
        stale_handlers = list(logger.handlers)
        for h in stale_handlers:
            logger.removeHandler(h)
        handler = logging.handlers.MemoryHandler(capacity=100)
        handler.setLevel(logging.WARNING)
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        original_propagate = logger.propagate
        logger.propagate = False
        try:
            assembler._estimate_total_context_size(sections)
        finally:
            logger.removeHandler(handler)
            logger.propagate = original_propagate
            for h in stale_handlers:
                logger.addHandler(h)
        assert len(handler.buffer) == 0


class TestLoadSkillsRespectsTruncation:
    """Tests for _load_skills respecting max_skill_content_chars total limit."""

    def test_load_skills_truncates_when_over_limit(self, tmp_path: Path) -> None:
        """Skills content exceeding total limit is truncated."""
        assembler = ContextAssembler(tmp_path, max_skill_content_chars=50)

        mock_store = MagicMock()
        large_content = "A" * 200

        with patch("knowledge.skill_composer.SkillComposer") as MockComposer:
            mock_instance = MockComposer.return_value
            mock_instance.compose.return_value = large_content
            result = assembler._load_skills(["skill1", "skill2"], mock_store)

        # max_total = 50 * 2 = 100, content is 200 -> should be truncated
        assert "[TRUNCATED]" in result
        assert len(result) < 200

    def test_load_skills_no_truncation_when_under_limit(self, tmp_path: Path) -> None:
        """Skills content under the limit passes through unchanged."""
        assembler = ContextAssembler(tmp_path, max_skill_content_chars=500)

        mock_store = MagicMock()
        small_content = "Short skill content"

        with patch("knowledge.skill_composer.SkillComposer") as MockComposer:
            mock_instance = MockComposer.return_value
            mock_instance.compose.return_value = small_content
            result = assembler._load_skills(["skill1"], mock_store)

        assert result == small_content

    def test_load_skills_fallback_also_truncated(self, tmp_path: Path) -> None:
        """Even fallback descriptions are truncated if over limit."""
        assembler = ContextAssembler(tmp_path, max_skill_content_chars=10)

        mock_store = MagicMock()
        mock_store.get_skill.return_value = {"description": "A" * 100}

        with patch("knowledge.skill_composer.SkillComposer") as MockComposer:
            mock_instance = MockComposer.return_value
            mock_instance.compose.side_effect = ValueError("fail")
            result = assembler._load_skills(["skill1"], mock_store)

        # max_total = 10 * 1 = 10, fallback content is long -> truncated
        assert "[TRUNCATED]" in result
