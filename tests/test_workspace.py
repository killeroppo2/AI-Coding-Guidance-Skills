"""Tests for workspace isolation feature."""

from pathlib import Path

import pytest
import yaml

import runner
from memory.state_manager import StateManager


class TestWorkspaceStateManager:
    """Tests for workspace methods on StateManager."""

    def test_workspace_path_in_default_state(self, tmp_path: Path) -> None:
        """Test that workspace_path exists in DEFAULT_STATE with empty default."""
        from memory.state_manager import DEFAULT_STATE

        assert "workspace_path" in DEFAULT_STATE
        assert DEFAULT_STATE["workspace_path"] == ""

    def test_set_workspace_sets_path(self, tmp_path: Path) -> None:
        """Test that set_workspace sets workspace_path in state."""
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "workspace_path": "",
            "status": "idle",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        mgr = StateManager(str(state_file), str(memory_dir))
        mgr.set_workspace("my-project")
        assert mgr.state["workspace_path"] == "./workspace/my-project/"

    def test_set_workspace_creates_directory(self, tmp_path: Path) -> None:
        """Test that set_workspace creates the workspace directory."""
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "workspace_path": "",
            "status": "idle",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        mgr = StateManager(str(state_file), str(memory_dir))
        mgr.set_workspace("test-proj")

        workspace_dir = tmp_path / "workspace" / "test-proj"
        assert workspace_dir.exists()
        assert workspace_dir.is_dir()

    def test_get_workspace_returns_valid_path(self, tmp_path: Path) -> None:
        """Test that get_workspace returns the correct workspace Path."""
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "workspace_path": "./workspace/my-project/",
            "status": "idle",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        mgr = StateManager(str(state_file), str(memory_dir))
        result = mgr.get_workspace()
        assert result == tmp_path / "workspace" / "my-project"

    def test_get_workspace_empty_path(self, tmp_path: Path) -> None:
        """Test get_workspace with empty workspace_path returns default."""
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "workspace_path": "",
            "status": "idle",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        mgr = StateManager(str(state_file), str(memory_dir))
        result = mgr.get_workspace()
        assert result == tmp_path / "workspace"

    def test_workspace_path_loaded_from_existing_state(self, tmp_path: Path) -> None:
        """Test that workspace_path is preserved when loading existing state."""
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "build api",
            "workspace_path": "./workspace/build-api/",
            "status": "running",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        mgr = StateManager(str(state_file), str(memory_dir))
        assert mgr.state["workspace_path"] == "./workspace/build-api/"

    def test_workspace_path_defaults_when_missing_from_file(self, tmp_path: Path) -> None:
        """Test that workspace_path gets default when missing from state file."""
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        # State without workspace_path
        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "status": "idle",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        mgr = StateManager(str(state_file), str(memory_dir))
        assert mgr.state["workspace_path"] == ""


class TestSanitizeProjectName:
    """Tests for the _sanitize_project_name helper."""

    def test_basic_sanitization(self) -> None:
        """Test basic goal sanitization."""
        assert runner._sanitize_project_name("Build a REST API") == "build-a-rest-api"

    def test_special_characters_removed(self) -> None:
        """Test that special characters are removed."""
        assert runner._sanitize_project_name("Hello, World!") == "hello-world"

    def test_truncation_to_50_chars(self) -> None:
        """Test that result is truncated to 50 characters."""
        long_goal = "a" * 100
        result = runner._sanitize_project_name(long_goal)
        assert len(result) == 50

    def test_empty_goal(self) -> None:
        """Test sanitization of empty string."""
        assert runner._sanitize_project_name("") == "project"

    def test_all_special_chars(self) -> None:
        """Test goal that is only special characters."""
        assert runner._sanitize_project_name("!@#$%^&*()") == "project"

    def test_numbers_preserved(self) -> None:
        """Test that numbers are preserved."""
        assert runner._sanitize_project_name("version 2 api") == "version-2-api"

    def test_multiple_spaces(self) -> None:
        """Test multiple consecutive spaces become multiple hyphens."""
        result = runner._sanitize_project_name("hello   world")
        assert result == "hello---world"

    def test_mixed_case_lowered(self) -> None:
        """Test that mixed case is lowered."""
        assert runner._sanitize_project_name("MyProject") == "myproject"

    def test_leading_dash_stripped(self) -> None:
        """Test that leading dashes are stripped from sanitized name."""
        result = runner._sanitize_project_name("...API")
        assert not result.startswith("-")
        assert result == "api"

    def test_leading_dots_stripped(self) -> None:
        """Test that leading dots are stripped from sanitized name."""
        result = runner._sanitize_project_name("...hello")
        assert result[0].isalnum()
        assert result == "hello"

    def test_all_dashes_returns_fallback(self) -> None:
        """Test that all-dash input returns fallback name."""
        assert runner._sanitize_project_name("---") == "project"

    def test_goal_starting_with_special_then_word(self) -> None:
        """Test goal starting with special characters followed by a word."""
        assert runner._sanitize_project_name("!!!Build") == "build"


class TestWorkspaceRunner:
    """Tests for workspace initialization in runner.py."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a complete runner environment in tmp_path."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "workspace_path": "",
            "status": "idle",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Initialize",
                    "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                    "max_retries": 1,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/planner.md",
                    "description": "Plan",
                    "transitions": [],
                    "max_retries": 2,
                },
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator prompt")
        (kernel_dir / "prompts" / "planner.md").write_text("Planner prompt")
        (kernel_dir / "BOOT.md").write_text("# Boot")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy")

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "decisions.jsonl").touch()
        (memory_dir / "reflections.jsonl").touch()
        (memory_dir / "current_goal.md").touch()
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump({"iteration": 0, "tasks_total": 0, "tasks_done": 0}, f)

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_workspace_initialized_from_goal(self, runner_env: Path, monkeypatch) -> None:
        """Test workspace is initialized based on goal."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main(["--goal", "Build a REST API", "--max-iterations", "1"])
        assert state["workspace_path"] == "./workspace/build-a-rest-api/"
        workspace_dir = runner_env / "workspace" / "build-a-rest-api"
        assert workspace_dir.exists()

    def test_workspace_cli_override(self, runner_env: Path, monkeypatch) -> None:
        """Test --workspace flag overrides goal-derived name."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main(
            [
                "--goal",
                "Build a REST API",
                "--workspace",
                "custom-project",
                "--max-iterations",
                "1",
            ]
        )
        assert state["workspace_path"] == "./workspace/custom-project/"
        workspace_dir = runner_env / "workspace" / "custom-project"
        assert workspace_dir.exists()

    def test_workspace_dry_run_does_not_create_dir(self, runner_env: Path, monkeypatch) -> None:
        """Test that dry run sets workspace_path but does not create directory."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main(
            [
                "--goal",
                "Build a REST API",
                "--dry-run",
                "--max-iterations",
                "1",
            ]
        )
        assert state["workspace_path"] == "./workspace/build-a-rest-api/"
        workspace_dir = runner_env / "workspace" / "build-a-rest-api"
        assert not workspace_dir.exists()

    def test_workspace_parse_args_flag(self) -> None:
        """Test that --workspace argument is parsed correctly."""
        args = runner.parse_args(["--goal", "test", "--workspace", "my-ws"])
        assert args.workspace == "my-ws"

    def test_workspace_parse_args_default_none(self) -> None:
        """Test that --workspace defaults to None."""
        args = runner.parse_args(["--goal", "test"])
        assert args.workspace is None


class TestWorkspaceConstitution:
    """Tests that constitution and prompts reference workspace correctly."""

    def test_constitution_has_article_ix(self, kernel_root: Path) -> None:
        """Test that constitution.md has Article IX about workspace protection."""
        constitution = (kernel_root / "kernel" / "constitution.md").read_text()
        assert "Article IX" in constitution
        assert "Workspace Protection" in constitution
        assert "workspace" in constitution.lower()

    def test_boot_md_mentions_workspace(self, kernel_root: Path) -> None:
        """Test that BOOT.md mentions workspace boundaries."""
        boot = (kernel_root / "kernel" / "BOOT.md").read_text()
        assert "workspace" in boot.lower()
        assert "workspace_path" in boot

    def test_coder_prompt_forbids_writing_outside_workspace(self, kernel_root: Path) -> None:
        """Test coder.md explicitly forbids writing outside workspace."""
        coder = (kernel_root / "kernel" / "prompts" / "coder.md").read_text()
        assert "workspace" in coder.lower()
        assert "NEVER write to kernel/" in coder

    def test_orchestrator_prompt_mentions_workspace(self, kernel_root: Path) -> None:
        """Test orchestrator.md mentions workspace initialization."""
        orch = (kernel_root / "kernel" / "prompts" / "orchestrator.md").read_text()
        assert "workspace" in orch.lower()


class TestWorkspaceContextAssembler:
    """Tests for workspace_path in context assembler output."""

    def test_format_state_includes_workspace(self, tmp_path: Path) -> None:
        """Test that _format_state includes workspace_path when set."""
        from kernel.context_assembler import ContextAssembler

        assembler = ContextAssembler(tmp_path)
        state = {
            "goal": "test",
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "status": "running",
            "workspace_path": "./workspace/test-project/",
            "errors": [],
            "context": {"current_task": "", "phase": "startup"},
        }
        result = assembler._format_state(state)
        assert "Workspace: ./workspace/test-project/" in result

    def test_format_state_omits_empty_workspace(self, tmp_path: Path) -> None:
        """Test that _format_state omits workspace when empty."""
        from kernel.context_assembler import ContextAssembler

        assembler = ContextAssembler(tmp_path)
        state = {
            "goal": "test",
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "status": "running",
            "workspace_path": "",
            "errors": [],
            "context": {"current_task": "", "phase": "startup"},
        }
        result = assembler._format_state(state)
        assert "Workspace" not in result
