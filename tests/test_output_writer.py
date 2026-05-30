"""Tests for kernel/output_writer - code extraction from AI output."""

import os
from pathlib import Path

import pytest

from kernel.output_writer import extract_and_write_files


class TestExtractAndWriteFiles:
    """Tests for the extract_and_write_files function."""

    def test_empty_output_returns_empty(self, tmp_path: Path) -> None:
        """Empty AI output should return no files."""
        result = extract_and_write_files("", str(tmp_path))
        assert result == []

    def test_empty_workspace_returns_empty(self) -> None:
        """Empty workspace path should return no files."""
        result = extract_and_write_files("some output", "")
        assert result == []

    def test_no_code_blocks_returns_empty(self, tmp_path: Path) -> None:
        """Output without code blocks should return no files."""
        output = "Here is my plan:\n- Step 1\n- Step 2\nDone!"
        result = extract_and_write_files(output, str(tmp_path))
        assert result == []

    def test_extract_with_inline_filename_comment(self, tmp_path: Path) -> None:
        """Extract file when first line has # filename: comment."""
        output = (
            "Here is the code:\n"
            "```python\n"
            "# filename: src/main.py\n"
            "def hello():\n"
            '    return "hello"\n'
            "```\n"
        )
        result = extract_and_write_files(output, str(tmp_path))
        assert len(result) == 1
        written_path = Path(result[0])
        assert written_path.name == "main.py"
        content = written_path.read_text(encoding="utf-8")
        assert "def hello():" in content
        # The filename comment line should be removed
        assert "# filename:" not in content

    def test_extract_with_bold_filename(self, tmp_path: Path) -> None:
        """Extract file when preceded by **filename** pattern."""
        output = (
            "**src/app.py:**\n"
            "```python\n"
            "import os\n"
            "\n"
            "print('hello')\n"
            "```\n"
        )
        result = extract_and_write_files(output, str(tmp_path))
        assert len(result) == 1
        written_path = Path(result[0])
        assert written_path.name == "app.py"
        content = written_path.read_text(encoding="utf-8")
        assert "import os" in content
        assert "print('hello')" in content

    def test_extract_with_backtick_filename(self, tmp_path: Path) -> None:
        """Extract file when preceded by `filename` pattern."""
        output = (
            "Create `utils/helpers.py`:\n"
            "```python\n"
            "def add(a, b):\n"
            "    return a + b\n"
            "```\n"
        )
        result = extract_and_write_files(output, str(tmp_path))
        assert len(result) == 1
        written_path = Path(result[0])
        assert written_path.name == "helpers.py"
        content = written_path.read_text(encoding="utf-8")
        assert "def add(a, b):" in content

    def test_extract_multiple_files(self, tmp_path: Path) -> None:
        """Extract multiple files from a single AI output."""
        output = (
            "**src/main.py:**\n"
            "```python\n"
            "from utils import helper\n"
            "print(helper.greet())\n"
            "```\n"
            "\n"
            "**src/utils/helper.py:**\n"
            "```python\n"
            "def greet():\n"
            '    return "hi"\n'
            "```\n"
        )
        result = extract_and_write_files(output, str(tmp_path))
        assert len(result) == 2
        names = [Path(f).name for f in result]
        assert "main.py" in names
        assert "helper.py" in names

    def test_creates_subdirectories(self, tmp_path: Path) -> None:
        """Nested directories are created automatically."""
        output = (
            "**deep/nested/dir/file.py:**\n"
            "```python\n"
            "x = 1\n"
            "```\n"
        )
        result = extract_and_write_files(output, str(tmp_path))
        assert len(result) == 1
        assert (tmp_path / "deep" / "nested" / "dir" / "file.py").exists()

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        """Files with .. in path should be skipped."""
        output = (
            "**../../etc/passwd:**\n"
            "```\n"
            "malicious content\n"
            "```\n"
        )
        result = extract_and_write_files(output, str(tmp_path))
        assert result == []

    def test_strips_workspace_prefix(self, tmp_path: Path) -> None:
        """workspace/project-name/ prefix is stripped from paths."""
        output = (
            "**workspace/my-project/src/main.py:**\n"
            "```python\n"
            "print('hello')\n"
            "```\n"
        )
        result = extract_and_write_files(output, str(tmp_path))
        assert len(result) == 1
        written_path = Path(result[0])
        assert written_path.name == "main.py"
        assert "src" in str(written_path)

    def test_code_block_without_filename_skipped(self, tmp_path: Path) -> None:
        """Code blocks without identifiable filename are skipped."""
        output = (
            "Here is an example:\n"
            "```\n"
            "some random snippet\n"
            "```\n"
        )
        result = extract_and_write_files(output, str(tmp_path))
        assert result == []

    def test_heading_filename_pattern(self, tmp_path: Path) -> None:
        """Extract file when preceded by markdown heading with filename."""
        output = (
            "### config.yaml\n"
            "```yaml\n"
            "debug: true\n"
            "port: 8080\n"
            "```\n"
        )
        result = extract_and_write_files(output, str(tmp_path))
        assert len(result) == 1
        written_path = Path(result[0])
        assert written_path.name == "config.yaml"
        content = written_path.read_text(encoding="utf-8")
        assert "debug: true" in content
