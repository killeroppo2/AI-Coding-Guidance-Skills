"""Tests for P1: Context Tiering in kernel/context_assembler.py."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import yaml
import pytest

from kernel.context_assembler import ContextAssembler


def _make_assembler_env(tmp_path: Path) -> Path:
    """Create a comprehensive environment for context assembly tiering tests."""
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    (kernel_dir / "BOOT.md").write_text("Boot content.")
    (kernel_dir / "constitution.md").write_text("Constitution content.")
    (kernel_dir / "philosophy").mkdir()
    (kernel_dir / "philosophy" / "dao.md").write_text("Dao content.")
    (kernel_dir / "philosophy" / "strategy.md").write_text("Strategy content.")
    (kernel_dir / "prompts").mkdir()
    (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator prompt.")
    (kernel_dir / "prompts" / "coder.md").write_text("Coder prompt.")
    (kernel_dir / "prompts" / "reflector.md").write_text("Reflector prompt.")
    (kernel_dir / "prompts" / "planner.md").write_text("Planner prompt.")
    (kernel_dir / "prompts" / "tester.md").write_text("Tester prompt.")
    (kernel_dir / "prompts" / "reviewer.md").write_text("Reviewer prompt.")

    # contracts
    (kernel_dir / "contracts").mkdir()
    (kernel_dir / "contracts" / "output_format.md").write_text(
        "Output format contract content."
    )

    # evolution history
    (kernel_dir / "evolution").mkdir()
    history_entries = [
        json.dumps({"status": "applied", "type": "refactor", "reason": "improve", "timestamp": "2025-01-01T00:00:00"}),
    ]
    (kernel_dir / "evolution" / "history.jsonl").write_text("\n".join(history_entries) + "\n")

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
                "transitions": [{"to": "code", "condition": "plan_ready"}],
                "max_retries": 1,
            },
            {
                "id": "code",
                "prompt_file": "prompts/coder.md",
                "description": "Code",
                "transitions": [{"to": "test", "condition": "code_written"}],
                "max_retries": 1,
            },
            {
                "id": "test",
                "prompt_file": "prompts/tester.md",
                "description": "Test",
                "transitions": [{"to": "review", "condition": "tests_pass"}],
                "max_retries": 1,
            },
            {
                "id": "review",
                "prompt_file": "prompts/reviewer.md",
                "description": "Review",
                "transitions": [{"to": "reflect", "condition": "review_pass"}],
                "max_retries": 1,
            },
            {
                "id": "reflect",
                "prompt_file": "prompts/reflector.md",
                "description": "Reflect",
                "transitions": [{"to": "evolve", "condition": "evolution_proposed"}],
                "max_retries": 1,
            },
            {
                "id": "evolve",
                "prompt_file": "prompts/reflector.md",
                "description": "Evolve",
                "transitions": [{"to": "plan", "condition": "evolution_applied"}],
                "max_retries": 1,
            },
        ],
        "default_start": "init",
    }
    with open(kernel_dir / "graph.yaml", "w") as f:
        yaml.safe_dump(graph_data, f)

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    for sub in ["rules", "skills", "patterns"]:
        (knowledge_dir / sub).mkdir()
        with open(knowledge_dir / sub / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()

    # decisions
    decisions_entries = [
        json.dumps({"timestamp": "2025-01-01T00:00:00", "type": "arch", "summary": "Decision A"}),
    ]
    (memory_dir / "decisions.jsonl").write_text("\n".join(decisions_entries) + "\n")

    # reflections
    reflections_entries = [
        json.dumps({"node": "code", "success": True, "learnings": ["L1"], "issues": []}),
    ]
    (memory_dir / "reflections.jsonl").write_text("\n".join(reflections_entries) + "\n")

    (memory_dir / "current_goal.md").touch()
    (memory_dir / "plan.md").write_text("Plan content here.")

    # tasks.yaml so _load_current_task doesn't fail
    tasks_data = {"tasks": [{"id": "t1", "title": "Task 1", "status": "in_progress", "description": "Do thing"}]}
    with open(memory_dir / "tasks.yaml", "w") as f:
        yaml.safe_dump(tasks_data, f)

    with open(memory_dir / "progress.yaml", "w") as f:
        yaml.safe_dump(
            {"iteration": 1, "tasks_total": 1, "tasks_done": 0, "status": "running"},
            f,
        )

    return tmp_path


class TestShouldInclude:
    """Tests for the _should_include helper method."""

    def test_node_id_none_always_includes(self, tmp_path: Path) -> None:
        """Test that node_id=None always returns True (backward compat)."""
        assembler = ContextAssembler(tmp_path)
        tier_rules = {"boot": ["init"], "dao": ["reflect"]}
        assert assembler._should_include("boot", None, tier_rules) is True
        assert assembler._should_include("dao", None, tier_rules) is True

    def test_none_rule_means_all_nodes(self, tmp_path: Path) -> None:
        """Test that a None value in tier_rules means all nodes."""
        assembler = ContextAssembler(tmp_path)
        tier_rules = {"output_format": None, "node_prompt": None}
        assert assembler._should_include("output_format", "code", tier_rules) is True
        assert assembler._should_include("node_prompt", "reflect", tier_rules) is True
        assert assembler._should_include("output_format", "init", tier_rules) is True

    def test_node_in_allowed_list(self, tmp_path: Path) -> None:
        """Test that a node in the allowed list returns True."""
        assembler = ContextAssembler(tmp_path)
        tier_rules = {"boot": ["init"], "dao": ["reflect", "evolve"]}
        assert assembler._should_include("boot", "init", tier_rules) is True
        assert assembler._should_include("dao", "reflect", tier_rules) is True
        assert assembler._should_include("dao", "evolve", tier_rules) is True

    def test_node_not_in_allowed_list(self, tmp_path: Path) -> None:
        """Test that a node not in the allowed list returns False."""
        assembler = ContextAssembler(tmp_path)
        tier_rules = {"boot": ["init"], "dao": ["reflect", "evolve"]}
        assert assembler._should_include("boot", "code", tier_rules) is False
        assert assembler._should_include("dao", "code", tier_rules) is False
        assert assembler._should_include("dao", "init", tier_rules) is False

    def test_unknown_section_key_returns_true(self, tmp_path: Path) -> None:
        """Test that a section key not in tier_rules returns True (default include)."""
        assembler = ContextAssembler(tmp_path)
        tier_rules = {"boot": ["init"]}
        # "unknown_section" is not in tier_rules, so .get returns None -> include
        assert assembler._should_include("unknown_section", "code", tier_rules) is True


class TestContextTieringInit:
    """Tests for tiering when node_id is 'init'."""

    def test_init_includes_boot_and_constitution(self, tmp_path: Path) -> None:
        """Test that init node includes BOOT.md and constitution."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "init", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_node("init")
        result = assembler.assemble(state, node, graph, knowledge)

        assert "=== BOOT SEQUENCE ===" in result
        assert "Boot content." in result
        assert "=== CONSTITUTION (IMMUTABLE) ===" in result
        assert "Constitution content." in result

    def test_init_excludes_dao_evolution_reflections(self, tmp_path: Path) -> None:
        """Test that init node does NOT include dao, evolution_history, or recent_reflections."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "init", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_node("init")
        result = assembler.assemble(state, node, graph, knowledge)

        assert "=== PHILOSOPHY: DAO ===" not in result
        assert "=== EVOLUTION HISTORY ===" not in result
        assert "=== RECENT REFLECTIONS ===" not in result


class TestContextTieringCode:
    """Tests for tiering when node_id is 'code'."""

    def test_code_excludes_boot_constitution_dao_strategy_decisions_evolution_reflections(
        self, tmp_path: Path
    ) -> None:
        """Test that code node does NOT include boot, constitution, dao, strategy, decisions, evolution_history, reflections."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "code", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "coding"},
        }
        node = graph.get_node("code")
        result = assembler.assemble(state, node, graph, knowledge)

        assert "=== BOOT SEQUENCE ===" not in result
        assert "=== CONSTITUTION (IMMUTABLE) ===" not in result
        assert "=== PHILOSOPHY: DAO ===" not in result
        assert "=== PHILOSOPHY: STRATEGY ===" not in result
        assert "=== RECENT DECISIONS ===" not in result
        assert "=== EVOLUTION HISTORY ===" not in result
        assert "=== RECENT REFLECTIONS ===" not in result

    def test_code_includes_current_task_workspace_plan_output_format_node_prompt_state(
        self, tmp_path: Path
    ) -> None:
        """Test that code node includes current_task, workspace_manifest, plan, output_format, node_prompt, state_summary."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        # Create workspace for manifest
        workspace = env / "workspace"
        workspace.mkdir()
        (workspace / "main.py").write_text("print('hello')")

        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "code", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "workspace_path": str(workspace),
            "context": {"skills_loaded": [], "current_task": "", "phase": "coding"},
        }
        node = graph.get_node("code")
        result = assembler.assemble(state, node, graph, knowledge)

        assert "=== CURRENT TASK ===" in result
        assert "=== WORKSPACE MANIFEST ===" in result
        assert "=== PLAN ===" in result
        assert "=== OUTPUT FORMAT CONTRACT ===" in result
        assert "=== NODE PROMPT (code) ===" in result
        assert "=== CURRENT STATE ===" in result


class TestContextTieringReflect:
    """Tests for tiering when node_id is 'reflect'."""

    def test_reflect_includes_dao_decisions_reflections_evolution_strategy(
        self, tmp_path: Path
    ) -> None:
        """Test that reflect node includes dao, decisions, recent_reflections, evolution_history, strategy."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "reflect", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "reflecting"},
        }
        node = graph.get_node("reflect")
        result = assembler.assemble(state, node, graph, knowledge)

        assert "=== PHILOSOPHY: DAO ===" in result
        assert "=== RECENT DECISIONS ===" in result
        assert "=== RECENT REFLECTIONS ===" in result
        assert "=== EVOLUTION HISTORY ===" in result
        assert "=== PHILOSOPHY: STRATEGY ===" in result

    def test_reflect_excludes_boot_constitution_current_task_workspace(
        self, tmp_path: Path
    ) -> None:
        """Test that reflect node does NOT include boot, constitution, current_task, workspace_manifest."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "reflect", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "workspace_path": str(env / "workspace"),
            "context": {"skills_loaded": [], "current_task": "", "phase": "reflecting"},
        }
        node = graph.get_node("reflect")
        result = assembler.assemble(state, node, graph, knowledge)

        assert "=== BOOT SEQUENCE ===" not in result
        assert "=== CONSTITUTION (IMMUTABLE) ===" not in result
        assert "=== CURRENT TASK ===" not in result
        assert "=== WORKSPACE MANIFEST ===" not in result


class TestContextTieringBackwardCompat:
    """Tests for backward compatibility when node has no id or id is None."""

    def test_node_without_id_includes_all_sections(self, tmp_path: Path) -> None:
        """Test that a node with id=None includes all sections (backward compat)."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "init", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        # Create a node dict without 'id' key
        node = {"prompt_file": "prompts/orchestrator.md", "description": "Test"}

        # Mock get_prompt_for_node to handle missing id
        class MockGraphExecutor:
            def get_prompt_for_node(self, node_id):
                return "prompts/orchestrator.md"

        mock_graph = MockGraphExecutor()
        result = assembler.assemble(state, node, mock_graph, knowledge)

        # All sections should be included when node_id is None
        assert "=== BOOT SEQUENCE ===" in result
        assert "=== CONSTITUTION (IMMUTABLE) ===" in result
        assert "=== PHILOSOPHY: DAO ===" in result
        assert "=== PHILOSOPHY: STRATEGY ===" in result
        assert "=== EVOLUTION HISTORY ===" in result
        assert "=== RECENT REFLECTIONS ===" in result
        assert "=== RECENT DECISIONS ===" in result
        assert "=== CURRENT TASK ===" in result
