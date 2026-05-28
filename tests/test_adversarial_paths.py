"""Tests for adversarial path inputs and rollback correctness.

Verifies that the evolution engine rejects path variants that attempt to
bypass immutability protections, and that rollback of remove_node correctly
restores the deleted node.
"""

from pathlib import Path

import pytest
import yaml

from kernel.evolution.engine import EvolutionEngine, IMMUTABLE_FILES
from kernel.graph_executor import GraphExecutor


@pytest.fixture
def evolution_env(tmp_path: Path):
    """Set up a temporary kernel directory for adversarial testing."""
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    (kernel_dir / "evolution").mkdir()
    (kernel_dir / "prompts").mkdir()

    # Create BOOT.md and constitution.md so resolve() works on real files
    (kernel_dir / "BOOT.md").write_text("# BOOT")
    (kernel_dir / "constitution.md").write_text("# Constitution")

    # Create runner.py at the project root (parent of kernel/)
    (tmp_path / "runner.py").write_text("# runner")

    graph_file = kernel_dir / "graph.yaml"
    graph_data = {
        "version": "1.0",
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
                "transitions": [{"to": "code", "condition": "plan_ready"}],
                "max_retries": 2,
            },
            {
                "id": "code",
                "prompt_file": "prompts/coder.md",
                "description": "Code",
                "transitions": [],
                "max_retries": 3,
            },
            {
                "id": "isolated",
                "prompt_file": "prompts/coder.md",
                "description": "Isolated node for removal tests",
                "transitions": [],
                "max_retries": 1,
            },
        ],
        "default_start": "init",
        "max_iterations": 30,
    }
    with open(graph_file, "w") as f:
        yaml.safe_dump(graph_data, f)

    # Create prompt files
    (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator prompt")
    (kernel_dir / "prompts" / "planner.md").write_text("Planner prompt")
    (kernel_dir / "prompts" / "coder.md").write_text("Coder prompt")

    graph_executor = GraphExecutor(str(graph_file))
    engine = EvolutionEngine(str(kernel_dir), graph_executor)
    return engine, kernel_dir, graph_executor


class TestPathNormalizationBypass:
    """Tests that path variants like ./kernel/BOOT.md are correctly rejected."""

    def test_reject_dot_slash_boot_md(self, evolution_env) -> None:
        """./kernel/BOOT.md should be rejected as a protected file."""
        engine, _, _ = evolution_env
        change = {
            "type": "modify_prompt",
            "details": {"target_file": "./kernel/BOOT.md"},
        }
        valid, reason = engine.validate_change(change)
        assert valid is False
        assert "protected file" in reason.lower() or "Cannot modify" in reason

    def test_reject_double_slash_boot_md(self, evolution_env) -> None:
        """kernel//BOOT.md should be rejected as a protected file."""
        engine, _, _ = evolution_env
        change = {
            "type": "modify_prompt",
            "details": {"target_file": "kernel//BOOT.md"},
        }
        valid, reason = engine.validate_change(change)
        assert valid is False
        assert "protected file" in reason.lower() or "Cannot modify" in reason

    def test_reject_dot_in_constitution_path(self, evolution_env) -> None:
        """kernel/./constitution.md should be rejected as a protected file."""
        engine, _, _ = evolution_env
        change = {
            "type": "modify_prompt",
            "details": {"path": "kernel/./constitution.md"},
        }
        valid, reason = engine.validate_change(change)
        assert valid is False
        assert "protected file" in reason.lower() or "Cannot modify" in reason

    def test_reject_dot_slash_runner(self, evolution_env) -> None:
        """./runner.py should be rejected as a protected file."""
        engine, _, _ = evolution_env
        change = {
            "type": "modify_prompt",
            "details": {"file": "./runner.py"},
        }
        valid, reason = engine.validate_change(change)
        assert valid is False
        assert "protected file" in reason.lower() or "Cannot modify" in reason

    def test_reject_complex_path_variant(self, evolution_env) -> None:
        """kernel/prompts/../BOOT.md should normalize to kernel/BOOT.md and be rejected."""
        engine, _, _ = evolution_env
        change = {
            "type": "modify_prompt",
            "details": {"target_file": "kernel/prompts/../BOOT.md"},
        }
        valid, reason = engine.validate_change(change)
        assert valid is False
        assert "protected file" in reason.lower() or "Cannot modify" in reason

    def test_accept_non_protected_path(self, evolution_env) -> None:
        """kernel/prompts/planner.md should still be accepted."""
        engine, _, _ = evolution_env
        change = {
            "type": "modify_prompt",
            "details": {"prompt_file": "prompts/planner.md", "content": "new content"},
        }
        valid, reason = engine.validate_change(change)
        assert valid is True


class TestPathTraversalInModifyPrompt:
    """Tests that modify_prompt rejects path traversal escaping kernel dir."""

    def test_reject_traversal_to_constitution(self, evolution_env) -> None:
        """../constitution.md as prompt_file should be rejected (escapes kernel/prompts)."""
        engine, _, _ = evolution_env
        change = {
            "type": "modify_prompt",
            "details": {"prompt_file": "../constitution.md", "content": "hacked"},
        }
        valid, reason = engine.validate_change(change)
        assert valid is False
        assert "protected file" in reason.lower() or "traversal" in reason.lower() or "Cannot modify" in reason

    def test_reject_traversal_escaping_kernel(self, evolution_env) -> None:
        """../../etc/passwd style paths should be rejected (escapes kernel dir)."""
        engine, _, _ = evolution_env
        change = {
            "type": "modify_prompt",
            "details": {"prompt_file": "../../etc/passwd", "content": "bad"},
        }
        valid, reason = engine.validate_change(change)
        assert valid is False
        assert "traversal" in reason.lower()

    def test_reject_absolute_path_prompt_file(self, evolution_env) -> None:
        """Even if resolved path is outside kernel_dir, detect traversal."""
        engine, _, _ = evolution_env
        change = {
            "type": "modify_prompt",
            "details": {"prompt_file": "../runner.py", "content": "hacked"},
        }
        valid, reason = engine.validate_change(change)
        assert valid is False

    def test_accept_nested_prompt_file(self, evolution_env) -> None:
        """prompts/sub/new.md should be accepted (stays inside kernel dir)."""
        engine, _, _ = evolution_env
        change = {
            "type": "modify_prompt",
            "details": {"prompt_file": "prompts/sub/new.md", "content": "valid"},
        }
        valid, reason = engine.validate_change(change)
        assert valid is True


class TestRollbackRemoveNode:
    """Tests that rollback of remove_node correctly restores the node."""

    def test_rollback_remove_node_restores_node(self, evolution_env) -> None:
        """After remove_node, rollback should restore the node definition."""
        engine, _, graph_executor = evolution_env

        # Verify isolated node exists before removal
        node = graph_executor.get_node("isolated")
        assert node["id"] == "isolated"
        assert node["description"] == "Isolated node for removal tests"

        # Remove the node
        change = engine.propose_change(
            "remove_node", {"node_id": "isolated"}, "Remove isolated node"
        )
        result = engine.apply_change(change)
        assert result is True

        # Verify node is gone
        with pytest.raises(KeyError):
            graph_executor.get_node("isolated")

        # Verify node_backup was saved in the change
        history = engine.get_history()
        applied_change = next(r for r in history if r["id"] == change["id"])
        assert "node_backup" in applied_change["details"]
        assert applied_change["details"]["node_backup"]["id"] == "isolated"

        # Rollback
        rollback_result = engine.rollback(change["id"])
        assert rollback_result is True

        # Verify node is restored
        restored = graph_executor.get_node("isolated")
        assert restored["id"] == "isolated"
        assert restored["description"] == "Isolated node for removal tests"

    def test_rollback_modify_prompt_restores_original(self, evolution_env) -> None:
        """After modify_prompt, rollback should restore original content."""
        engine, kernel_dir, _ = evolution_env

        original_content = "Planner prompt"
        prompt_path = kernel_dir / "prompts" / "planner.md"
        assert prompt_path.read_text() == original_content

        # Modify the prompt
        change = engine.propose_change(
            "modify_prompt",
            {"prompt_file": "prompts/planner.md", "content": "Modified content"},
            "Update planner",
        )
        result = engine.apply_change(change)
        assert result is True
        assert prompt_path.read_text() == "Modified content"

        # Verify original_content was saved
        history = engine.get_history()
        applied_change = next(r for r in history if r["id"] == change["id"])
        assert applied_change["details"]["original_content"] == original_content

        # Rollback
        rollback_result = engine.rollback(change["id"])
        assert rollback_result is True
        assert prompt_path.read_text() == original_content
