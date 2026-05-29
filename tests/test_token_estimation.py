"""Tests for CJK-aware token estimation."""

from pathlib import Path

import pytest

from kernel.context_assembler import ContextAssembler
from knowledge.skill_composer import _estimate_tokens as skill_estimate_tokens


@pytest.fixture
def assembler(tmp_path: Path) -> ContextAssembler:
    """Create a ContextAssembler for testing."""
    return ContextAssembler(tmp_path)


class TestTokenEstimation:
    """Test CJK-aware token estimation."""

    def test_pure_ascii_estimation(self, assembler: ContextAssembler) -> None:
        """Pure ASCII text: estimate ~0.25 tokens per char."""
        text = "hello world"  # 11 chars -> 11 * 0.25 = 2.75 -> 2
        result = assembler._estimate_tokens(text)
        assert result == 2  # int(11 * 0.25) = 2

    def test_pure_cjk_estimation(self, assembler: ContextAssembler) -> None:
        """Pure CJK text: estimate ~1.5 tokens per char."""
        text = "\u4f60\u597d\u4e16\u754c\u6d4b\u8bd5\u6587\u672c\u4e2d\u6587"  # 10 CJK chars
        result = assembler._estimate_tokens(text)
        assert result == 15  # int(10 * 1.5) = 15

    def test_mixed_text_estimation(self, assembler: ContextAssembler) -> None:
        """Mixed text: CJK + ASCII."""
        text = "hello\u4f60\u597d"  # 5 ASCII + 2 CJK
        result = assembler._estimate_tokens(text)
        # int(2 * 1.5 + 5 * 0.25) = int(3 + 1.25) = int(4.25) = 4
        assert result == 4

    def test_cjk_higher_than_old_formula(self, assembler: ContextAssembler) -> None:
        """Chinese text should get HIGHER token estimate than old len//4."""
        text = "\u4f60\u597d\u4e16\u754c\u6d4b\u8bd5\u6587\u672c\u4e2d\u6587"  # 10 CJK chars
        old_estimate = len(text) // 4  # 10 // 4 = 2
        new_estimate = assembler._estimate_tokens(text)  # 15
        assert new_estimate > old_estimate

    def test_empty_string(self, assembler: ContextAssembler) -> None:
        """Empty string returns 0 tokens."""
        assert assembler._estimate_tokens("") == 0

    def test_single_ascii_char(self, assembler: ContextAssembler) -> None:
        """Single ASCII char returns 0 (int(0.25) = 0)."""
        assert assembler._estimate_tokens("a") == 0

    def test_four_ascii_chars(self, assembler: ContextAssembler) -> None:
        """Four ASCII chars returns 1 (int(4 * 0.25) = 1)."""
        assert assembler._estimate_tokens("abcd") == 1

    def test_skill_composer_estimate_tokens(self) -> None:
        """Test that skill_composer's estimate_tokens works the same."""
        text = "\u4f60\u597d\u4e16\u754c"  # 4 CJK
        result = skill_estimate_tokens(text)
        assert result == 6  # int(4 * 1.5) = 6

    def test_skill_composer_ascii(self) -> None:
        """Test skill_composer estimate with ASCII."""
        text = "hello world test"  # 16 chars
        result = skill_estimate_tokens(text)
        assert result == 4  # int(16 * 0.25) = 4
