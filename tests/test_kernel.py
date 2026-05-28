"""Tests for the kernel package structure and configuration files."""

from pathlib import Path

import pytest
import yaml

from kernel.bootstrap import BootstrapGenerator
from kernel.context_assembler import ContextAssembler
from kernel.graph_executor import GraphExecutor
from knowledge.store import KnowledgeStore


class TestKernelStructure:
    """Tests for kernel directory structure."""

    def test_kernel_package_importable(self) -> None:
        """Test that kernel package can be imported."""
        import kernel

        assert kernel is not None

    def test_evolution_package_importable(self) -> None:
        """Test that kernel.evolution package can be imported."""
        from kernel.evolution import engine

        assert engine is not None

    def test_evolution_engine_class_exists(self) -> None:
        """Test that EvolutionEngine class exists."""
        from kernel.evolution.engine import EvolutionEngine

        assert EvolutionEngine is not None

    def test_graph_executor_importable(self) -> None:
        """Test that kernel.graph_executor can be imported."""
        from kernel.graph_executor import GraphExecutor

        assert GraphExecutor is not None

    def test_reflector_importable(self) -> None:
        """Test that kernel.reflector can be imported."""
        from kernel.reflector import Reflector

        assert Reflector is not None

    def test_immutable_files_defined(self) -> None:
        """Test that IMMUTABLE_FILES is defined correctly."""
        from kernel.evolution.engine import IMMUTABLE_FILES

        assert "kernel/BOOT.md" in IMMUTABLE_FILES
        assert "kernel/constitution.md" in IMMUTABLE_FILES
        assert "runner.py" in IMMUTABLE_FILES


class TestGraphYaml:
    """Tests for graph.yaml validity."""

    def test_graph_has_nodes(self, graph_yaml: Path) -> None:
        """Test that graph.yaml has a nodes list."""
        data = yaml.safe_load(graph_yaml.read_text())
        assert "nodes" in data
        assert isinstance(data["nodes"], list)
        assert len(data["nodes"]) > 0

    def test_graph_nodes_have_required_fields(self, graph_yaml: Path) -> None:
        """Test that all nodes have required fields."""
        data = yaml.safe_load(graph_yaml.read_text())
        for node in data["nodes"]:
            assert "id" in node, f"Node missing 'id': {node}"
            assert "prompt_file" in node, f"Node {node['id']} missing 'prompt_file'"
            assert "description" in node, f"Node {node['id']} missing 'description'"
            assert "transitions" in node, f"Node {node['id']} missing 'transitions'"
            assert "max_retries" in node, f"Node {node['id']} missing 'max_retries'"

    def test_graph_transitions_reference_valid_nodes(self, graph_yaml: Path) -> None:
        """Test that all transitions reference existing node IDs."""
        data = yaml.safe_load(graph_yaml.read_text())
        node_ids = {node["id"] for node in data["nodes"]}
        for node in data["nodes"]:
            for transition in node["transitions"]:
                assert transition["to"] in node_ids, (
                    f"Node '{node['id']}' has transition to unknown node '{transition['to']}'"
                )

    def test_graph_has_default_start(self, graph_yaml: Path) -> None:
        """Test that graph.yaml has a default_start field."""
        data = yaml.safe_load(graph_yaml.read_text())
        assert "default_start" in data
        node_ids = {node["id"] for node in data["nodes"]}
        assert data["default_start"] in node_ids

    def test_graph_has_max_iterations(self, graph_yaml: Path) -> None:
        """Test that graph.yaml has a max_iterations field."""
        data = yaml.safe_load(graph_yaml.read_text())
        assert "max_iterations" in data
        assert isinstance(data["max_iterations"], int)

    def test_graph_prompt_files_exist(self, kernel_root: Path, graph_yaml: Path) -> None:
        """Test that all prompt files referenced in graph.yaml exist."""
        data = yaml.safe_load(graph_yaml.read_text())
        for node in data["nodes"]:
            prompt_path = kernel_root / "kernel" / node["prompt_file"]
            assert prompt_path.exists(), f"Prompt file missing: {node['prompt_file']}"


class TestStateYaml:
    """Tests for state.yaml validity."""

    def test_state_has_current_node(self, state_yaml: Path) -> None:
        """Test that state.yaml has current_node."""
        data = yaml.safe_load(state_yaml.read_text())
        assert "current_node" in data

    def test_state_has_iteration_count(self, state_yaml: Path) -> None:
        """Test that state.yaml has iteration_count."""
        data = yaml.safe_load(state_yaml.read_text())
        assert "iteration_count" in data
        assert isinstance(data["iteration_count"], int)

    def test_state_has_status(self, state_yaml: Path) -> None:
        """Test that state.yaml has status."""
        data = yaml.safe_load(state_yaml.read_text())
        assert "status" in data
        assert data["status"] in ("idle", "running", "paused", "complete", "error")

    def test_state_initial_values(self, state_yaml: Path) -> None:
        """Test that state.yaml has correct initial values."""
        data = yaml.safe_load(state_yaml.read_text())
        assert data["current_node"] == "init"
        assert data["iteration_count"] == 0
        assert data["status"] == "idle"


class TestKernelFiles:
    """Tests for kernel file existence."""

    def test_boot_md_exists(self, kernel_root: Path) -> None:
        """Test that BOOT.md exists."""
        assert (kernel_root / "kernel" / "BOOT.md").exists()

    def test_constitution_md_exists(self, kernel_root: Path) -> None:
        """Test that constitution.md exists."""
        assert (kernel_root / "kernel" / "constitution.md").exists()

    def test_dao_md_exists(self, kernel_root: Path) -> None:
        """Test that philosophy/dao.md exists."""
        assert (kernel_root / "kernel" / "philosophy" / "dao.md").exists()

    def test_strategy_md_exists(self, kernel_root: Path) -> None:
        """Test that philosophy/strategy.md exists."""
        assert (kernel_root / "kernel" / "philosophy" / "strategy.md").exists()

    def test_all_prompt_files_exist(self, kernel_root: Path) -> None:
        """Test that all prompt files exist."""
        prompts = [
            "orchestrator.md",
            "planner.md",
            "coder.md",
            "tester.md",
            "reviewer.md",
            "reflector.md",
        ]
        for prompt in prompts:
            path = kernel_root / "kernel" / "prompts" / prompt
            assert path.exists(), f"Missing prompt: {prompt}"


class TestContextAssembler:
    """Tests for the ContextAssembler class."""

    @pytest.fixture
    def assembler_env(self, tmp_path: Path) -> Path:
        """Set up a minimal kernel environment for context assembly."""
        # kernel dir
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "BOOT.md").write_text("# Boot content\nBoot instructions here.")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao\nSimplicity is key.")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy\nPlan first.")
        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator prompt text.")

        # graph.yaml
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
                    "description": "Plan tasks",
                    "transitions": [],
                    "max_retries": 1,
                },
                {
                    "id": "reflect",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Reflect",
                    "transitions": [],
                    "max_retries": 1,
                },
            ],
            "default_start": "init",
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        # knowledge dir
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_assemble_includes_boot(self, assembler_env: Path) -> None:
        """Test that assembled prompt includes BOOT.md content."""
        assembler = ContextAssembler(assembler_env)
        graph = GraphExecutor(str(assembler_env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(assembler_env / "knowledge"))
        state = {
            "current_node": "init",
            "goal": "test",
            "iteration_count": 0,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_current_node(state)
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== BOOT SEQUENCE ===" in result
        assert "Boot instructions here." in result

    def test_assemble_includes_state(self, assembler_env: Path) -> None:
        """Test that assembled prompt includes state summary."""
        assembler = ContextAssembler(assembler_env)
        graph = GraphExecutor(str(assembler_env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(assembler_env / "knowledge"))
        state = {
            "current_node": "init",
            "goal": "Build API",
            "iteration_count": 5,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "task1", "phase": "coding"},
        }
        node = graph.get_current_node(state)
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== CURRENT STATE ===" in result
        assert "Goal: Build API" in result
        assert "Iteration: 5" in result
        assert "Current Task: task1" in result
        assert "Phase: coding" in result

    def test_assemble_includes_node_prompt(self, assembler_env: Path) -> None:
        """Test that assembled prompt includes node prompt content."""
        assembler = ContextAssembler(assembler_env)
        graph = GraphExecutor(str(assembler_env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(assembler_env / "knowledge"))
        state = {
            "current_node": "init",
            "goal": "test",
            "iteration_count": 0,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_current_node(state)
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== NODE PROMPT (init) ===" in result
        assert "Orchestrator prompt text." in result

    def test_assemble_includes_philosophy(self, assembler_env: Path) -> None:
        """Test that assembled prompt includes philosophy files."""
        assembler = ContextAssembler(assembler_env)
        graph = GraphExecutor(str(assembler_env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(assembler_env / "knowledge"))
        state = {
            "current_node": "reflect",
            "goal": "test",
            "iteration_count": 0,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_node("reflect")
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== PHILOSOPHY: DAO ===" in result
        assert "Simplicity is key." in result
        assert "=== PHILOSOPHY: STRATEGY ===" in result
        assert "Plan first." in result

    def test_assemble_includes_skills(self, assembler_env: Path) -> None:
        """Test that assembled prompt includes loaded skills."""
        assembler = ContextAssembler(assembler_env)
        graph = GraphExecutor(str(assembler_env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(assembler_env / "knowledge"))
        knowledge.add_skill("test-skill", "A test skill for testing")
        state = {
            "current_node": "init",
            "goal": "test",
            "iteration_count": 0,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {"skills_loaded": ["test-skill"], "current_task": "", "phase": "startup"},
        }
        node = graph.get_current_node(state)
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== LOADED SKILLS ===" in result
        assert "test-skill: A test skill for testing" in result

    def test_assemble_skill_not_found(self, assembler_env: Path) -> None:
        """Test that assembled prompt handles missing skills gracefully."""
        assembler = ContextAssembler(assembler_env)
        graph = GraphExecutor(str(assembler_env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(assembler_env / "knowledge"))
        state = {
            "current_node": "init",
            "goal": "test",
            "iteration_count": 0,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {"skills_loaded": ["nonexistent"], "current_task": "", "phase": "startup"},
        }
        node = graph.get_current_node(state)
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== LOADED SKILLS ===" in result
        assert "nonexistent: (skill not found)" in result

    def test_assemble_missing_prompt_file(self, assembler_env: Path) -> None:
        """Test that assembled prompt handles missing prompt file gracefully."""
        assembler = ContextAssembler(assembler_env)
        graph = GraphExecutor(str(assembler_env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(assembler_env / "knowledge"))
        # Use "plan" node which has prompts/planner.md that doesn't exist
        state = {
            "current_node": "plan",
            "goal": "test",
            "iteration_count": 0,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_current_node(state)
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== NODE PROMPT (plan) ===" in result
        assert "(file not found: planner.md)" in result

    def test_assemble_with_errors_in_state(self, assembler_env: Path) -> None:
        """Test that assembled prompt shows errors in state."""
        assembler = ContextAssembler(assembler_env)
        graph = GraphExecutor(str(assembler_env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(assembler_env / "knowledge"))
        state = {
            "current_node": "init",
            "goal": "test",
            "iteration_count": 2,
            "max_iterations": 30,
            "status": "running",
            "errors": ["timeout on node plan"],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_current_node(state)
        result = assembler.assemble(state, node, graph, knowledge)
        assert "Errors:" in result
        assert "timeout on node plan" in result

    def test_assemble_no_skills_loaded(self, assembler_env: Path) -> None:
        """Test that assembled prompt omits skills section when none loaded."""
        assembler = ContextAssembler(assembler_env)
        graph = GraphExecutor(str(assembler_env / "kernel" / "graph.yaml"))
        knowledge = KnowledgeStore(str(assembler_env / "knowledge"))
        state = {
            "current_node": "init",
            "goal": "test",
            "iteration_count": 0,
            "max_iterations": 30,
            "status": "running",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        node = graph.get_current_node(state)
        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== LOADED SKILLS ===" not in result

    def test_context_assembler_importable(self) -> None:
        """Test that context_assembler module can be imported."""
        from kernel.context_assembler import ContextAssembler

        assert ContextAssembler is not None

    def test_load_current_task_malformed_yaml(self, tmp_path: Path) -> None:
        """Test that _load_current_task handles malformed tasks.yaml gracefully."""
        from kernel.context_assembler import ContextAssembler

        (tmp_path / "memory").mkdir(parents=True)
        (tmp_path / "memory" / "tasks.yaml").write_text("not: valid: yaml: {{", encoding="utf-8")

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_current_task()
        assert result == ""

    def test_load_current_task_missing_file(self, tmp_path: Path) -> None:
        """Test that _load_current_task handles missing tasks.yaml gracefully."""
        from kernel.context_assembler import ContextAssembler

        (tmp_path / "memory").mkdir(parents=True)
        # Do not create tasks.yaml

        assembler = ContextAssembler(tmp_path)
        result = assembler._load_current_task()
        assert result == ""


class TestBootstrapGenerator:
    """Tests for the BootstrapGenerator class."""

    @pytest.fixture
    def bootstrap_env(self, tmp_path: Path) -> Path:
        """Set up a minimal kernel environment for bootstrap generation."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "BOOT.md").write_text("# KERNEL BOOT SEQUENCE\nBoot content here.")
        (kernel_dir / "constitution.md").write_text("# Constitution\nImmutable safety rules.")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao\nSimplicity is the way.")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy\nAdapt and overcome.")
        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrate the workflow.")

        # state.yaml
        state_data = {
            "current_node": "init",
            "iteration_count": 3,
            "max_iterations": 30,
            "goal": "Build an API",
            "status": "running",
            "errors": [],
        }
        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

        # graph.yaml
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
                    "max_retries": 1,
                },
            ],
            "default_start": "init",
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        # knowledge dir
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_generate_includes_boot(self, bootstrap_env: Path) -> None:
        """Test that generate output contains boot sequence content."""
        gen = BootstrapGenerator(bootstrap_env)
        result = gen.generate()
        assert "=== BOOT SEQUENCE ===" in result
        assert "Boot content here." in result

    def test_generate_includes_constitution(self, bootstrap_env: Path) -> None:
        """Test that generate output contains constitution content."""
        gen = BootstrapGenerator(bootstrap_env)
        result = gen.generate()
        assert "=== CONSTITUTION (IMMUTABLE) ===" in result
        assert "Immutable safety rules." in result

    def test_generate_includes_state(self, bootstrap_env: Path) -> None:
        """Test that generate output contains state info."""
        gen = BootstrapGenerator(bootstrap_env)
        result = gen.generate()
        assert "=== CURRENT STATE ===" in result
        assert "Goal: Build an API" in result
        assert "Iteration: 3 / 30" in result

    def test_generate_includes_philosophy(self, bootstrap_env: Path) -> None:
        """Test that generate output contains dao and strategy content."""
        gen = BootstrapGenerator(bootstrap_env)
        result = gen.generate()
        assert "=== PHILOSOPHY: DAO ===" in result
        assert "Simplicity is the way." in result
        assert "=== PHILOSOPHY: STRATEGY ===" in result
        assert "Adapt and overcome." in result

    def test_generate_with_defaults(self, bootstrap_env: Path) -> None:
        """Test that generate works with no arguments (uses defaults)."""
        gen = BootstrapGenerator(bootstrap_env)
        result = gen.generate()
        # Should work without error and contain content from all sections
        assert "BOOT SEQUENCE" in result
        assert "CONSTITUTION" in result
        assert "CURRENT STATE" in result

    def test_format_state(self, bootstrap_env: Path) -> None:
        """Test that _format_state produces readable output."""
        gen = BootstrapGenerator(bootstrap_env)
        state = {
            "goal": "Test goal",
            "current_node": "plan",
            "status": "running",
            "iteration_count": 5,
            "max_iterations": 30,
            "errors": ["some error"],
        }
        result = gen._format_state(state)
        assert "Goal: Test goal" in result
        assert "Current Node: plan" in result
        assert "Status: running" in result
        assert "Iteration: 5 / 30" in result
        assert "Last Error: some error" in result

    def test_format_state_no_errors(self, bootstrap_env: Path) -> None:
        """Test that _format_state works without errors."""
        gen = BootstrapGenerator(bootstrap_env)
        state = {
            "goal": "My goal",
            "current_node": "init",
            "status": "idle",
            "iteration_count": 0,
            "max_iterations": 30,
            "errors": [],
        }
        result = gen._format_state(state)
        assert "Goal: My goal" in result
        assert "Last Error" not in result

    def test_generate_includes_role_prompt(self, bootstrap_env: Path) -> None:
        """Test that generate includes the current node's role prompt."""
        gen = BootstrapGenerator(bootstrap_env)
        result = gen.generate()
        assert "=== CURRENT ROLE PROMPT ===" in result
        assert "Orchestrate the workflow." in result
