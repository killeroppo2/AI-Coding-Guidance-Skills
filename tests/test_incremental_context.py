"""Tests for incremental context assembly in ContextAssembler."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from kernel.context_assembler import ContextAssembler


class TestAssembleIncremental:
    """Tests for assemble_incremental method."""

    @pytest.fixture
    def assembler_env(self, tmp_path: Path) -> tuple[ContextAssembler, MagicMock, MagicMock]:
        """Set up a ContextAssembler with mock graph and knowledge."""
        kernel_dir = tmp_path
        (kernel_dir / "kernel").mkdir()
        (kernel_dir / "kernel" / "prompts").mkdir()
        (kernel_dir / "kernel" / "prompts" / "coder.md").write_text("Code node prompt")
        (kernel_dir / "kernel" / "contracts").mkdir()
        (kernel_dir / "kernel" / "contracts" / "output_format.md").write_text(
            "Output format: STATUS and TRANSITION required."
        )
        (kernel_dir / "kernel" / "BOOT.md").write_text(
            "# Boot Sequence\n\n" + "Boot content paragraph. " * 50
        )
        (kernel_dir / "kernel" / "philosophy").mkdir()
        (kernel_dir / "kernel" / "philosophy" / "dao.md").write_text("# Dao\nPhilosophy.")
        (kernel_dir / "kernel" / "philosophy" / "strategy.md").write_text("# Strategy")

        memory_dir = kernel_dir / "memory"
        memory_dir.mkdir()
        (memory_dir / "decisions.jsonl").touch()
        (memory_dir / "reflections.jsonl").touch()
        (memory_dir / "current_goal.md").touch()
        (memory_dir / "plan.md").touch()
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump(
                {"iteration": 1, "tasks_total": 5, "tasks_done": 2, "status": "running"},
                f,
            )
        tasks_data = {
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Build login",
                    "status": "in_progress",
                    "description": "Build login page",
                    "complexity": "medium",
                },
            ]
        }
        with open(memory_dir / "tasks.yaml", "w") as f:
            yaml.safe_dump(tasks_data, f)

        # Create kernel/evolution dir for history
        (kernel_dir / "kernel" / "evolution").mkdir()
        (kernel_dir / "kernel" / "evolution" / "history.jsonl").touch()

        assembler = ContextAssembler(kernel_dir)

        graph_executor = MagicMock()
        graph_executor.get_prompt_for_node.return_value = "prompts/coder.md"

        knowledge_store = MagicMock()
        knowledge_store.list_skills.return_value = []

        return assembler, graph_executor, knowledge_store

    def test_incremental_returns_empty_on_first_call(self, assembler_env: tuple) -> None:
        """Test assemble_incremental returns empty on first call (no prior success)."""
        assembler, graph, knowledge = assembler_env
        state = {"goal": "test", "current_node": "code", "iteration_count": 1}
        node = {"id": "code"}

        result = assembler.assemble_incremental(state, node, graph, knowledge)
        assert result == ""

    def test_incremental_returns_content_after_mark_success(self, assembler_env: tuple) -> None:
        """Test assemble_incremental returns non-empty after mark_iteration_success."""
        assembler, graph, knowledge = assembler_env
        state = {
            "goal": "test",
            "current_node": "code",
            "iteration_count": 2,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {},
        }
        node = {"id": "code"}

        # First call to set last_node_id
        assembler.assemble_incremental(state, node, graph, knowledge)
        # Mark success
        assembler.mark_iteration_success("code")
        # Second call should return incremental content
        result = assembler.assemble_incremental(state, node, graph, knowledge)
        assert result != ""

    def test_incremental_returns_empty_when_node_changes(self, assembler_env: tuple) -> None:
        """Test assemble_incremental returns empty when node changes."""
        assembler, graph, knowledge = assembler_env
        state = {
            "goal": "test",
            "current_node": "code",
            "iteration_count": 2,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {},
        }

        # Mark success for "code"
        assembler.mark_iteration_success("code")
        # Now call with a different node
        node = {"id": "test"}
        graph.get_prompt_for_node.return_value = "prompts/tester.md"
        result = assembler.assemble_incremental(state, node, graph, knowledge)
        assert result == ""

    def test_incremental_contains_required_sections(self, assembler_env: tuple) -> None:
        """Test incremental output includes the required sections."""
        assembler, graph, knowledge = assembler_env
        state = {
            "goal": "test goal",
            "current_node": "code",
            "iteration_count": 2,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {},
        }
        node = {"id": "code"}

        assembler.assemble_incremental(state, node, graph, knowledge)
        assembler.mark_iteration_success("code")
        result = assembler.assemble_incremental(state, node, graph, knowledge)

        assert "=== INCREMENTAL UPDATE ===" in result
        assert "=== CURRENT STATE ===" in result
        assert "=== NODE PROMPT (code) ===" in result
        assert "=== OUTPUT FORMAT CONTRACT ===" in result

    def test_incremental_does_not_contain_full_sections(self, assembler_env: tuple) -> None:
        """Test incremental output does NOT include boot, philosophy, or evolution."""
        assembler, graph, knowledge = assembler_env
        state = {
            "goal": "test goal",
            "current_node": "code",
            "iteration_count": 2,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {},
        }
        node = {"id": "code"}

        assembler.assemble_incremental(state, node, graph, knowledge)
        assembler.mark_iteration_success("code")
        result = assembler.assemble_incremental(state, node, graph, knowledge)

        assert "=== BOOT SEQUENCE ===" not in result
        assert "=== PHILOSOPHY" not in result
        assert "=== EVOLUTION HISTORY ===" not in result

    def test_incremental_smaller_than_full(self, assembler_env: tuple) -> None:
        """Test incremental output is smaller than full assemble output."""
        assembler, graph, knowledge = assembler_env
        state = {
            "goal": "test goal",
            "current_node": "init",
            "iteration_count": 2,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {"skills_loaded": []},
        }
        node = {"id": "init"}

        # Get full context (init node includes BOOT.md, constitution, etc.)
        graph.get_prompt_for_node.return_value = "prompts/coder.md"
        full_context = assembler.assemble(state, node, graph, knowledge)

        # Get incremental context
        assembler.mark_iteration_success("init")
        incremental_context = assembler.assemble_incremental(state, node, graph, knowledge)

        assert len(incremental_context) > 0
        assert len(incremental_context) < len(full_context)

    def test_incremental_includes_current_task(self, assembler_env: tuple) -> None:
        """Test incremental output includes current task info."""
        assembler, graph, knowledge = assembler_env
        state = {
            "goal": "test goal",
            "current_node": "code",
            "iteration_count": 2,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {},
        }
        node = {"id": "code"}

        assembler.assemble_incremental(state, node, graph, knowledge)
        assembler.mark_iteration_success("code")
        result = assembler.assemble_incremental(state, node, graph, knowledge)

        assert "=== CURRENT TASK ===" in result
        assert "Build login" in result


class TestMarkIterationSuccess:
    """Tests for mark_iteration_success method."""

    def test_mark_sets_node_id(self) -> None:
        """Test mark_iteration_success sets the last node ID."""
        assembler = ContextAssembler(Path("/tmp/fake"))
        assembler.mark_iteration_success("code")
        assert assembler._last_node_id == "code"

    def test_mark_sets_successful_flag(self) -> None:
        """Test mark_iteration_success sets the success flag."""
        assembler = ContextAssembler(Path("/tmp/fake"))
        assembler.mark_iteration_success("code")
        assert assembler._last_successful is True

    def test_mark_increments_counter(self) -> None:
        """Test mark_iteration_success increments the counter."""
        assembler = ContextAssembler(Path("/tmp/fake"))
        assert assembler._last_iteration_count == 0
        assembler.mark_iteration_success("code")
        assert assembler._last_iteration_count == 1
        assembler.mark_iteration_success("code")
        assert assembler._last_iteration_count == 2

    def test_mark_with_different_nodes(self) -> None:
        """Test mark_iteration_success with different node IDs."""
        assembler = ContextAssembler(Path("/tmp/fake"))
        assembler.mark_iteration_success("code")
        assert assembler._last_node_id == "code"
        assembler.mark_iteration_success("test")
        assert assembler._last_node_id == "test"
        assert assembler._last_successful is True


class TestMarkIterationFailure:
    """Tests for mark_iteration_failure method."""

    def test_failure_resets_successful_flag(self) -> None:
        """Test mark_iteration_failure resets _last_successful to False."""
        assembler = ContextAssembler(Path("/tmp/fake"))
        assembler.mark_iteration_success("code")
        assert assembler._last_successful is True
        assembler.mark_iteration_failure()
        assert assembler._last_successful is False

    def test_failure_preserves_node_id(self) -> None:
        """Test mark_iteration_failure does not change _last_node_id."""
        assembler = ContextAssembler(Path("/tmp/fake"))
        assembler.mark_iteration_success("code")
        assembler.mark_iteration_failure()
        assert assembler._last_node_id == "code"

    def test_failure_after_success_forces_full_context(self, assembler_env: tuple) -> None:
        """Test that after mark_iteration_failure, assemble_incremental returns empty."""
        assembler, graph, knowledge = assembler_env
        state = {
            "goal": "test",
            "current_node": "code",
            "iteration_count": 2,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {},
        }
        node = {"id": "code"}

        # First call to set last_node_id
        assembler.assemble_incremental(state, node, graph, knowledge)
        # Mark success
        assembler.mark_iteration_success("code")
        # Verify incremental works
        result = assembler.assemble_incremental(state, node, graph, knowledge)
        assert result != ""

        # Now mark failure
        assembler.mark_iteration_failure()
        # Next assemble_incremental should return empty (full context needed)
        result = assembler.assemble_incremental(state, node, graph, knowledge)
        assert result == ""

    @pytest.fixture
    def assembler_env(self, tmp_path: Path) -> tuple[ContextAssembler, MagicMock, MagicMock]:
        """Set up a ContextAssembler with mock graph and knowledge."""
        kernel_dir = tmp_path
        (kernel_dir / "kernel").mkdir()
        (kernel_dir / "kernel" / "prompts").mkdir()
        (kernel_dir / "kernel" / "prompts" / "coder.md").write_text("Code node prompt")
        (kernel_dir / "kernel" / "contracts").mkdir()
        (kernel_dir / "kernel" / "contracts" / "output_format.md").write_text(
            "Output format: STATUS and TRANSITION required."
        )
        (kernel_dir / "kernel" / "BOOT.md").write_text(
            "# Boot Sequence\n\n" + "Boot content paragraph. " * 50
        )
        (kernel_dir / "kernel" / "philosophy").mkdir()
        (kernel_dir / "kernel" / "philosophy" / "dao.md").write_text("# Dao\nPhilosophy.")
        (kernel_dir / "kernel" / "philosophy" / "strategy.md").write_text("# Strategy")

        memory_dir = kernel_dir / "memory"
        memory_dir.mkdir()
        (memory_dir / "decisions.jsonl").touch()
        (memory_dir / "reflections.jsonl").touch()
        (memory_dir / "current_goal.md").touch()
        (memory_dir / "plan.md").touch()
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump(
                {"iteration": 1, "tasks_total": 5, "tasks_done": 2, "status": "running"},
                f,
            )
        tasks_data = {
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Build login",
                    "status": "in_progress",
                    "description": "Build login page",
                    "complexity": "medium",
                },
            ]
        }
        with open(memory_dir / "tasks.yaml", "w") as f:
            yaml.safe_dump(tasks_data, f)

        (kernel_dir / "kernel" / "evolution").mkdir()
        (kernel_dir / "kernel" / "evolution" / "history.jsonl").touch()

        assembler = ContextAssembler(kernel_dir)

        graph_executor = MagicMock()
        graph_executor.get_prompt_for_node.return_value = "prompts/coder.md"

        knowledge_store = MagicMock()
        knowledge_store.list_skills.return_value = []

        return assembler, graph_executor, knowledge_store
