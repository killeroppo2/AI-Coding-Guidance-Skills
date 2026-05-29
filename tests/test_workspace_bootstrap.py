"""Tests for kernel/workspace_bootstrap.py - CLAUDE.md generation."""

from pathlib import Path

from kernel.workspace_bootstrap import _build_claude_md_content, generate_claude_md


class TestGenerateClaudeMd:
    """Tests for generate_claude_md function."""

    def test_creates_file(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md is created in workspace."""
        ws = str(tmp_path / "workspace" / "project") + "/"
        result = generate_claude_md(ws, "Build a REST API")
        assert result.exists()
        assert result.name == "CLAUDE.md"

    def test_contains_goal(self, tmp_path: Path) -> None:
        """Test that generated CLAUDE.md contains the goal."""
        ws = str(tmp_path / "workspace" / "project") + "/"
        result = generate_claude_md(ws, "Build a FastAPI REST API with JWT auth")
        content = result.read_text(encoding="utf-8")
        assert "Build a FastAPI REST API with JWT auth" in content

    def test_contains_workspace_path(self, tmp_path: Path) -> None:
        """Test that generated CLAUDE.md contains workspace path."""
        ws = str(tmp_path / "workspace" / "my-project") + "/"
        result = generate_claude_md(ws, "Test goal")
        content = result.read_text(encoding="utf-8")
        assert ws in content

    def test_contains_output_format(self, tmp_path: Path) -> None:
        """Test that generated CLAUDE.md contains output format rules."""
        ws = str(tmp_path / "workspace" / "project") + "/"
        result = generate_claude_md(ws, "Test goal")
        content = result.read_text(encoding="utf-8")
        assert "STATUS:" in content
        assert "TRANSITION:" in content
        assert "FILES_WRITTEN:" in content

    def test_contains_boundary_rule(self, tmp_path: Path) -> None:
        """Test that generated CLAUDE.md contains workspace boundary rule."""
        ws = str(tmp_path / "workspace" / "project") + "/"
        result = generate_claude_md(ws, "Test goal")
        content = result.read_text(encoding="utf-8")
        assert "NEVER write files outside" in content

    def test_idempotent(self, tmp_path: Path) -> None:
        """Test that calling twice does not overwrite existing CLAUDE.md."""
        ws = str(tmp_path / "workspace" / "project") + "/"
        first = generate_claude_md(ws, "First goal")
        first_content = first.read_text(encoding="utf-8")
        # Call again with different goal
        second = generate_claude_md(ws, "Different goal")
        second_content = second.read_text(encoding="utf-8")
        # Should be identical (first call content preserved)
        assert first_content == second_content
        assert "First goal" in second_content

    def test_with_tasks(self, tmp_path: Path) -> None:
        """Test that tasks are included when provided."""
        ws = str(tmp_path / "workspace" / "project") + "/"
        tasks = [
            {"id": "T-001", "title": "Setup project", "status": "done"},
            {"id": "T-002", "title": "Implement API", "status": "pending"},
        ]
        result = generate_claude_md(ws, "Build API", tasks)
        content = result.read_text(encoding="utf-8")
        assert "T-001" in content
        assert "Setup project" in content
        assert "T-002" in content
        assert "Implement API" in content

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test that parent directories are created if needed."""
        ws = str(tmp_path / "deep" / "nested" / "workspace") + "/"
        result = generate_claude_md(ws, "Test goal")
        assert result.exists()
        assert result.parent.exists()

    def test_no_tasks_section_when_none(self, tmp_path: Path) -> None:
        """Test that tasks section is omitted when no tasks provided."""
        ws = str(tmp_path / "workspace" / "project") + "/"
        result = generate_claude_md(ws, "Test goal")
        content = result.read_text(encoding="utf-8")
        assert "Current Tasks" not in content


class TestBuildClaudeMdContent:
    """Tests for _build_claude_md_content helper."""

    def test_has_title(self) -> None:
        """Test that content starts with CLAUDE.md title."""
        content = _build_claude_md_content("./workspace/test/", "goal")
        assert content.startswith("# CLAUDE.md")

    def test_has_workspace_section(self) -> None:
        """Test content has workspace section."""
        content = _build_claude_md_content("./workspace/test/", "goal")
        assert "## Workspace" in content

    def test_has_rules_section(self) -> None:
        """Test content has rules section."""
        content = _build_claude_md_content("./workspace/test/", "goal")
        assert "## Rules" in content

    def test_files_written_example_uses_workspace_path(self) -> None:
        """Test that FILES_WRITTEN example uses the workspace path."""
        content = _build_claude_md_content("./workspace/my-proj/", "goal")
        assert "./workspace/my-proj/" in content
        assert "FILES_WRITTEN:" in content
