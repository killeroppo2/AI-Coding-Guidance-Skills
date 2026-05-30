"""Tests for kernel/workspace_bootstrap.py."""

from pathlib import Path

from kernel.workspace_bootstrap import generate_claude_md


class TestGenerateClaudeMd:
    """Tests for generate_claude_md function."""

    def test_creates_file(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md is created in the workspace."""
        ws = str(tmp_path / "workspace")
        result = generate_claude_md(ws, "Build an API")
        assert Path(result).exists()
        assert result == str(Path(ws) / "CLAUDE.md")

    def test_contains_goal(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md contains the goal."""
        ws = str(tmp_path / "workspace")
        generate_claude_md(ws, "Build an API")
        content = (Path(ws) / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Build an API" in content

    def test_contains_workspace_path(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md contains the workspace path."""
        ws = str(tmp_path / "workspace")
        generate_claude_md(ws, "test goal")
        content = (Path(ws) / "CLAUDE.md").read_text(encoding="utf-8")
        assert ws in content

    def test_handles_tasks(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md includes tasks when provided."""
        ws = str(tmp_path / "workspace")
        tasks = [
            {"status": "done", "title": "Setup project"},
            {"status": "pending", "title": "Write tests"},
        ]
        generate_claude_md(ws, "test", tasks=tasks)
        content = (Path(ws) / "CLAUDE.md").read_text(encoding="utf-8")
        assert "[done] Setup project" in content
        assert "[pending] Write tests" in content
        assert "## 任务" in content

    def test_handles_none_tasks(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md works with tasks=None."""
        ws = str(tmp_path / "workspace")
        generate_claude_md(ws, "test", tasks=None)
        content = (Path(ws) / "CLAUDE.md").read_text(encoding="utf-8")
        assert "## 任务" not in content

    def test_handles_empty_tasks(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md works with empty tasks list."""
        ws = str(tmp_path / "workspace")
        generate_claude_md(ws, "test", tasks=[])
        content = (Path(ws) / "CLAUDE.md").read_text(encoding="utf-8")
        assert "## 任务" not in content

    def test_creates_directory_if_not_exists(self, tmp_path: Path) -> None:
        """Test that workspace directory is created if missing."""
        ws = str(tmp_path / "deep" / "nested" / "workspace")
        result = generate_claude_md(ws, "test")
        assert Path(result).exists()

    def test_returns_path_as_string(self, tmp_path: Path) -> None:
        """Test that return value is a string path."""
        ws = str(tmp_path / "workspace")
        result = generate_claude_md(ws, "test")
        assert isinstance(result, str)

    def test_contains_chinese_instructions(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md contains Chinese formatting rules."""
        ws = str(tmp_path / "workspace")
        generate_claude_md(ws, "test")
        content = (Path(ws) / "CLAUDE.md").read_text(encoding="utf-8")
        assert "项目规则" in content
        assert "输出格式" in content
        assert "规则" in content
