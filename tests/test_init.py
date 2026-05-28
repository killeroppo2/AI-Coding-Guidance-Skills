"""Tests for kernel/init.py - runtime file initialization."""

from pathlib import Path

import yaml

from kernel.init import init_runtime_files


class TestInitRuntimeFiles:
    """Tests for the init_runtime_files function."""

    def test_creates_all_expected_files(self, tmp_path: Path) -> None:
        """Test that init_runtime_files creates all expected files."""
        init_runtime_files(tmp_path)

        expected_files = [
            tmp_path / "kernel" / "state.yaml",
            tmp_path / "memory" / "current_goal.md",
            tmp_path / "memory" / "plan.md",
            tmp_path / "memory" / "progress.yaml",
            tmp_path / "memory" / "assessment.yaml",
            tmp_path / "memory" / "tasks.yaml",
            tmp_path / "memory" / "decisions.jsonl",
            tmp_path / "memory" / "reflections.jsonl",
            tmp_path / "kernel" / "evolution" / "history.jsonl",
        ]

        for f in expected_files:
            assert f.exists(), f"Expected file not created: {f}"

    def test_idempotent_no_overwrite(self, tmp_path: Path, capsys) -> None:
        """Test that running init twice is idempotent and does not overwrite."""
        init_runtime_files(tmp_path)

        # Write custom content to state.yaml
        state_path = tmp_path / "kernel" / "state.yaml"
        state_path.write_text("custom: content\n", encoding="utf-8")

        # Run init again
        init_runtime_files(tmp_path)

        # Verify the file was NOT overwritten
        assert state_path.read_text(encoding="utf-8") == "custom: content\n"

        # Verify output shows skip messages
        captured = capsys.readouterr()
        assert "[skip]" in captured.out
        assert "already exists" in captured.out

    def test_state_yaml_default_structure(self, tmp_path: Path) -> None:
        """Test that created state.yaml has the correct default structure."""
        init_runtime_files(tmp_path)

        state_path = tmp_path / "kernel" / "state.yaml"
        state = yaml.safe_load(state_path.read_text(encoding="utf-8"))

        assert state["current_node"] == "init"
        assert state["iteration_count"] == 0
        assert state["status"] == "idle"
        assert state["goal"] == ""
        assert state["errors"] == []
        assert state["node_visits"] == {}

    def test_tasks_yaml_content(self, tmp_path: Path) -> None:
        """Test that tasks.yaml has correct default content."""
        init_runtime_files(tmp_path)

        tasks_path = tmp_path / "memory" / "tasks.yaml"
        content = tasks_path.read_text(encoding="utf-8")
        assert content == "tasks: []\n"

    def test_empty_files_are_empty(self, tmp_path: Path) -> None:
        """Test that files intended to be empty are actually empty."""
        init_runtime_files(tmp_path)

        empty_files = [
            tmp_path / "memory" / "current_goal.md",
            tmp_path / "memory" / "plan.md",
            tmp_path / "memory" / "decisions.jsonl",
            tmp_path / "memory" / "reflections.jsonl",
            tmp_path / "kernel" / "evolution" / "history.jsonl",
        ]

        for f in empty_files:
            assert f.read_text(encoding="utf-8") == "", f"Expected empty: {f}"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that parent directories are created automatically."""
        # Ensure directories don't exist yet
        assert not (tmp_path / "kernel").exists()
        assert not (tmp_path / "memory").exists()

        init_runtime_files(tmp_path)

        assert (tmp_path / "kernel").is_dir()
        assert (tmp_path / "memory").is_dir()
        assert (tmp_path / "kernel" / "evolution").is_dir()

    def test_output_summary(self, tmp_path: Path, capsys) -> None:
        """Test that initialization prints a summary with counts."""
        init_runtime_files(tmp_path)

        captured = capsys.readouterr()
        assert "Initialization complete." in captured.out
        assert "Created 9 file(s)" in captured.out
        assert "skipped 0 file(s)" in captured.out

    def test_partial_existing_files(self, tmp_path: Path, capsys) -> None:
        """Test init with some files already existing."""
        # Pre-create some files
        (tmp_path / "kernel").mkdir(parents=True)
        (tmp_path / "kernel" / "state.yaml").write_text("existing\n", encoding="utf-8")
        (tmp_path / "memory").mkdir(parents=True)
        (tmp_path / "memory" / "plan.md").write_text("existing plan\n", encoding="utf-8")

        init_runtime_files(tmp_path)

        captured = capsys.readouterr()
        assert "Created 7 file(s)" in captured.out
        assert "skipped 2 file(s)" in captured.out
