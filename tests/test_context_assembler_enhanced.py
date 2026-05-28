"""Tests for enhanced ContextAssembler: progress, decisions, workspace, plan, token budgeting."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import yaml
import pytest

from kernel.context_assembler import ContextAssembler


class TestLoadProgress:
    """Tests for _load_progress method."""

    def test_load_progress_existing_file(self, tmp_path: Path) -> None:
        """Test that progress.yaml is read and formatted correctly."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        progress_data = {
            "iteration": 5,
            "tasks_done": 3,
            "tasks_total": 10,
            "status": "running",
        }
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump(progress_data, f)

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_progress()
        assert result == "Iteration: 5, Tasks: 3/10 done, Status: running"

    def test_load_progress_missing_file(self, tmp_path: Path) -> None:
        """Test that missing progress.yaml returns empty string."""
        assembler = ContextAssembler(tmp_path)
        result = assembler._load_progress()
        assert result == ""

    def test_load_progress_empty_file(self, tmp_path: Path) -> None:
        """Test that empty progress.yaml returns empty string."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "progress.yaml").write_text("")

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_progress()
        assert result == ""

    def test_load_progress_invalid_yaml(self, tmp_path: Path) -> None:
        """Test that invalid YAML returns empty string."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "progress.yaml").write_text(": : invalid: [")

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_progress()
        assert result == ""


class TestLoadRecentDecisions:
    """Tests for _load_recent_decisions method."""

    def test_load_recent_decisions_returns_last_5(self, tmp_path: Path) -> None:
        """Test that with 10 entries, only last 5 are returned."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        entries = []
        for i in range(10):
            entries.append(json.dumps({
                "timestamp": f"2025-01-{i+1:02d}T00:00:00",
                "type": f"type_{i}",
                "summary": f"Decision {i}",
            }))
        (memory_dir / "decisions.jsonl").write_text("\n".join(entries) + "\n")

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_recent_decisions()

        # Should only have last 5
        assert "Decision 5" in result
        assert "Decision 9" in result
        assert "Decision 4" not in result
        lines = [l for l in result.strip().split("\n") if l.startswith("- ")]
        assert len(lines) == 5

    def test_load_recent_decisions_empty_file(self, tmp_path: Path) -> None:
        """Test that empty decisions.jsonl returns empty string."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "decisions.jsonl").write_text("")

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_recent_decisions()
        assert result == ""

    def test_load_recent_decisions_missing_file(self, tmp_path: Path) -> None:
        """Test that missing decisions.jsonl returns empty string."""
        assembler = ContextAssembler(tmp_path)
        result = assembler._load_recent_decisions()
        assert result == ""

    def test_load_recent_decisions_formats_correctly(self, tmp_path: Path) -> None:
        """Test that decisions are formatted as expected."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        entry = json.dumps({
            "timestamp": "2025-01-15T10:30:00",
            "type": "architecture",
            "summary": "Chose microservices",
        })
        (memory_dir / "decisions.jsonl").write_text(entry + "\n")

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_recent_decisions()
        assert result == "- [2025-01-15T10:30:00] architecture: Chose microservices"


class TestLoadWorkspaceManifest:
    """Tests for _load_workspace_manifest method."""

    def test_load_workspace_manifest_with_files(self, tmp_path: Path) -> None:
        """Test that files in workspace are listed (capped at max_entries)."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "file1.py").write_text("content")
        (workspace / "file2.py").write_text("content")
        sub = workspace / "subdir"
        sub.mkdir()
        (sub / "file3.py").write_text("content")

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_workspace_manifest(str(workspace))
        assert "file1.py" in result
        assert "file2.py" in result
        assert "subdir/" in result or "subdir" in result
        assert "file3.py" in result

    def test_load_workspace_manifest_caps_at_max_entries(self, tmp_path: Path) -> None:
        """Test that output is truncated at max_entries."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        for i in range(150):
            (workspace / f"file_{i:03d}.txt").write_text("x")

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_workspace_manifest(str(workspace), max_entries=100)
        assert "truncated at 100 entries" in result

    def test_load_workspace_manifest_nonexistent_path(self, tmp_path: Path) -> None:
        """Test that non-existent path returns empty string."""
        assembler = ContextAssembler(tmp_path)
        result = assembler._load_workspace_manifest("/nonexistent/path")
        assert result == ""

    def test_load_workspace_manifest_empty_string(self, tmp_path: Path) -> None:
        """Test that empty workspace_path returns empty string."""
        assembler = ContextAssembler(tmp_path)
        result = assembler._load_workspace_manifest("")
        assert result == ""


class TestLoadPlan:
    """Tests for _load_plan method."""

    def test_load_plan_existing_file(self, tmp_path: Path) -> None:
        """Test that plan.md content is returned."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "plan.md").write_text("# Plan\n\n1. Do thing A\n2. Do thing B\n")

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_plan()
        assert "# Plan" in result
        assert "Do thing A" in result

    def test_load_plan_missing_file(self, tmp_path: Path) -> None:
        """Test that missing plan.md returns empty string."""
        assembler = ContextAssembler(tmp_path)
        result = assembler._load_plan()
        assert result == ""

    def test_load_plan_empty_file(self, tmp_path: Path) -> None:
        """Test that empty plan.md returns empty string."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "plan.md").write_text("   \n  ")

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_plan()
        assert result == ""


def _make_assembler_env(tmp_path: Path) -> Path:
    """Create a minimal environment for context assembly tests."""
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    (kernel_dir / "BOOT.md").write_text("Boot content.")
    (kernel_dir / "philosophy").mkdir()
    (kernel_dir / "philosophy" / "dao.md").write_text("Dao.")
    (kernel_dir / "philosophy" / "strategy.md").write_text("Strategy.")
    (kernel_dir / "prompts").mkdir()
    (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator prompt.")

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
                "prompt_file": "prompts/orchestrator.md",
                "description": "Plan",
                "transitions": [{"to": "code", "condition": "plan_ready"}],
                "max_retries": 1,
            },
            {
                "id": "code",
                "prompt_file": "prompts/orchestrator.md",
                "description": "Code",
                "transitions": [{"to": "reflect", "condition": "code_written"}],
                "max_retries": 1,
            },
            {
                "id": "reflect",
                "prompt_file": "prompts/orchestrator.md",
                "description": "Reflect",
                "transitions": [{"to": "plan", "condition": "no_evolution_needed"}],
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
    (memory_dir / "decisions.jsonl").touch()
    (memory_dir / "reflections.jsonl").touch()
    (memory_dir / "plan.md").touch()

    # Create tasks.yaml so _load_current_task doesn't fail
    (memory_dir / "tasks.yaml").write_text(yaml.safe_dump([]))

    return tmp_path


class TestAssembleIncludesNewSections:
    """Tests that assemble() includes new sections when data exists."""

    def test_assemble_includes_progress(self, tmp_path: Path) -> None:
        """Test that assemble output includes progress section."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        memory_dir = env / "memory"
        progress_data = {"iteration": 3, "tasks_done": 2, "tasks_total": 5, "status": "active"}
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump(progress_data, f)

        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "init", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_current_node(state)
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== PROGRESS ===" in result
        assert "Iteration: 3, Tasks: 2/5 done, Status: active" in result

    def test_assemble_includes_plan(self, tmp_path: Path) -> None:
        """Test that assemble output includes plan section."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        (env / "memory" / "plan.md").write_text("# My Plan\nStep 1")

        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "plan", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_node("plan")
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== PLAN ===" in result
        assert "# My Plan" in result

    def test_assemble_includes_workspace_manifest(self, tmp_path: Path) -> None:
        """Test that assemble output includes workspace manifest."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "main.py").write_text("print('hello')")

        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "code", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "workspace_path": str(workspace),
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_node("code")
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== WORKSPACE MANIFEST ===" in result
        assert "main.py" in result

    def test_assemble_includes_recent_decisions(self, tmp_path: Path) -> None:
        """Test that assemble output includes recent decisions."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        entry = json.dumps({
            "timestamp": "2025-01-15T10:00:00",
            "type": "design",
            "summary": "Use REST API",
        })
        (env / "memory" / "decisions.jsonl").write_text(entry + "\n")

        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "reflect", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_node("reflect")
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== RECENT DECISIONS ===" in result
        assert "Use REST API" in result

    def test_assemble_new_sections_between_task_and_node_prompt(self, tmp_path: Path) -> None:
        """Test that new sections appear between CURRENT TASK and NODE PROMPT."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        progress_data = {"iteration": 1, "tasks_done": 0, "tasks_total": 1, "status": "active"}
        with open(env / "memory" / "progress.yaml", "w") as f:
            yaml.safe_dump(progress_data, f)

        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "init", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_current_node(state)
        result = assembler.assemble(state, node, graph, knowledge)

        # Progress should appear before NODE PROMPT
        progress_pos = result.find("=== PROGRESS ===")
        node_prompt_pos = result.find("=== NODE PROMPT")
        assert progress_pos < node_prompt_pos


class TestTokenBudgeting:
    """Tests for token budgeting in assemble()."""

    def test_token_budget_drops_decisions_first(self, tmp_path: Path) -> None:
        """Test that decisions section is dropped first when over budget."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)

        # Create substantial content for trimmable sections
        progress_data = {"iteration": 1, "tasks_done": 0, "tasks_total": 1, "status": "active"}
        with open(env / "memory" / "progress.yaml", "w") as f:
            yaml.safe_dump(progress_data, f)

        (env / "memory" / "plan.md").write_text("A" * 1000)

        # Create large decisions to push over budget
        entries = []
        for i in range(5):
            entries.append(json.dumps({
                "timestamp": f"2025-01-{i+1:02d}T00:00:00",
                "type": "big_decision",
                "summary": "X" * 200,
            }))
        (env / "memory" / "decisions.jsonl").write_text("\n".join(entries) + "\n")

        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "init", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        # Use node without id for backward compat (all sections included)
        node = {"prompt_file": "prompts/orchestrator.md", "description": "Test"}

        class _MockGraph:
            def get_prompt_for_node(self, node_id):
                return "prompts/orchestrator.md"

        mock_graph = _MockGraph()

        # First assemble with large budget to get full size
        full_result = assembler.assemble(state, node, mock_graph, knowledge, token_budget=100000)
        assert "=== RECENT DECISIONS ===" in full_result

        # Now use a tight budget that forces decisions to be dropped
        # Calculate a budget just under the full size
        full_tokens = len(full_result) // 4
        # Set budget to full_tokens minus enough to force decisions removal
        tight_budget = full_tokens - 50

        result = assembler.assemble(state, node, mock_graph, knowledge, token_budget=tight_budget)
        # Decisions should be dropped first
        assert "=== RECENT DECISIONS ===" not in result
        # But progress and plan should still be there
        assert "=== PROGRESS ===" in result
        assert "=== PLAN ===" in result

    def test_token_budget_extreme_only_core_remains(self, tmp_path: Path) -> None:
        """Test that with extremely small budget, only core sections remain."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)

        # Create content for all trimmable sections
        progress_data = {"iteration": 5, "tasks_done": 3, "tasks_total": 10, "status": "running"}
        with open(env / "memory" / "progress.yaml", "w") as f:
            yaml.safe_dump(progress_data, f)

        (env / "memory" / "plan.md").write_text("B" * 2000)

        entries = []
        for i in range(5):
            entries.append(json.dumps({
                "timestamp": f"2025-01-{i+1:02d}T00:00:00",
                "type": "decision",
                "summary": "Y" * 100,
            }))
        (env / "memory" / "decisions.jsonl").write_text("\n".join(entries) + "\n")

        # Create workspace files
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        for i in range(50):
            (workspace / f"file_{i}.py").write_text("x")

        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "init", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "workspace_path": str(workspace),
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_current_node(state)

        # Use a tiny budget that forces removal of all trimmable sections
        result = assembler.assemble(state, node, graph, knowledge, token_budget=1)

        # All trimmable sections should be removed
        assert "=== RECENT DECISIONS ===" not in result
        assert "=== WORKSPACE MANIFEST ===" not in result
        assert "=== PLAN ===" not in result
        assert "=== PROGRESS ===" not in result

        # Core sections should remain
        assert "=== BOOT SEQUENCE ===" in result
        assert "=== CURRENT STATE ===" in result
        assert "=== NODE PROMPT" in result

    def test_token_budget_no_trimming_when_within_budget(self, tmp_path: Path) -> None:
        """Test that no sections are trimmed when within budget."""
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        env = _make_assembler_env(tmp_path)
        progress_data = {"iteration": 1, "tasks_done": 0, "tasks_total": 1, "status": "active"}
        with open(env / "memory" / "progress.yaml", "w") as f:
            yaml.safe_dump(progress_data, f)

        (env / "memory" / "plan.md").write_text("Simple plan")

        entry = json.dumps({
            "timestamp": "2025-01-01T00:00:00",
            "type": "test",
            "summary": "Test decision",
        })
        (env / "memory" / "decisions.jsonl").write_text(entry + "\n")

        assembler = ContextAssembler(env)
        graph = GraphExecutor(str(env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(env / "knowledge"))
        state = {
            "current_node": "init", "goal": "test", "iteration_count": 0,
            "max_iterations": 30, "status": "running", "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        # Use node without id for backward compat (all sections included)
        node = {"prompt_file": "prompts/orchestrator.md", "description": "Test"}

        class _MockGraph:
            def get_prompt_for_node(self, node_id):
                return "prompts/orchestrator.md"

        mock_graph = _MockGraph()

        # Large budget should keep everything
        result = assembler.assemble(state, node, mock_graph, knowledge, token_budget=100000)
        assert "=== PROGRESS ===" in result
        assert "=== PLAN ===" in result
        assert "=== RECENT DECISIONS ===" in result
