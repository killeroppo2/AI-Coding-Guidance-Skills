"""Tests for the GraphExecutor class."""

from pathlib import Path

import pytest
import yaml

from kernel.graph_executor import GraphExecutor


class TestGraphExecutorInit:
    """Tests for GraphExecutor initialization and loading."""

    def test_load_graph(self, tmp_graph: Path) -> None:
        """Test that GraphExecutor loads a valid graph."""
        ge = GraphExecutor(str(tmp_graph))
        assert ge.graph is not None
        assert "nodes" in ge.graph
        assert len(ge.graph["nodes"]) == 3

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that loading a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            GraphExecutor(str(tmp_path / "nonexistent.yaml"))

    def test_load_invalid_graph(self, tmp_path: Path) -> None:
        """Test that loading an invalid graph raises ValueError."""
        invalid_file = tmp_path / "invalid.yaml"
        with open(invalid_file, "w") as f:
            yaml.safe_dump({"not_nodes": "invalid"}, f)
        with pytest.raises(ValueError, match="must contain a 'nodes' list"):
            GraphExecutor(str(invalid_file))

    def test_load_real_graph(self, kernel_root: Path) -> None:
        """Test loading the actual graph.yaml from the project."""
        ge = GraphExecutor(str(kernel_root / "kernel" / "graph.yaml"))
        assert len(ge.graph["nodes"]) >= 7


class TestGetNode:
    """Tests for get_node and get_current_node methods."""

    def test_get_node_existing(self, tmp_graph: Path) -> None:
        """Test getting an existing node by ID."""
        ge = GraphExecutor(str(tmp_graph))
        node = ge.get_node("init")
        assert node["id"] == "init"
        assert node["prompt_file"] == "prompts/orchestrator.md"

    def test_get_node_nonexistent(self, tmp_graph: Path) -> None:
        """Test that getting a nonexistent node raises KeyError."""
        ge = GraphExecutor(str(tmp_graph))
        with pytest.raises(KeyError, match="Node not found"):
            ge.get_node("nonexistent")

    def test_get_current_node_with_state(self, tmp_graph: Path) -> None:
        """Test getting current node based on state dict."""
        ge = GraphExecutor(str(tmp_graph))
        state = {"current_node": "plan"}
        node = ge.get_current_node(state)
        assert node["id"] == "plan"

    def test_get_current_node_no_state(self, tmp_graph: Path) -> None:
        """Test getting current node with None state uses default_start."""
        ge = GraphExecutor(str(tmp_graph))
        node = ge.get_current_node(None)
        assert node["id"] == "init"

    def test_get_current_node_empty_state(self, tmp_graph: Path) -> None:
        """Test getting current node with empty state uses default_start."""
        ge = GraphExecutor(str(tmp_graph))
        node = ge.get_current_node({})
        assert node["id"] == "init"


class TestGetPromptForNode:
    """Tests for get_prompt_for_node."""

    def test_get_prompt_path(self, tmp_graph: Path) -> None:
        """Test getting the prompt file path for a node."""
        ge = GraphExecutor(str(tmp_graph))
        path = ge.get_prompt_for_node("init")
        assert path == "prompts/orchestrator.md"

    def test_get_prompt_for_plan(self, tmp_graph: Path) -> None:
        """Test getting prompt path for plan node."""
        ge = GraphExecutor(str(tmp_graph))
        path = ge.get_prompt_for_node("plan")
        assert path == "prompts/planner.md"


class TestAdvance:
    """Tests for the advance method."""

    def test_advance_with_valid_condition(self, tmp_graph: Path) -> None:
        """Test advancing with a matching condition."""
        ge = GraphExecutor(str(tmp_graph))
        next_id = ge.advance("init", "goal_loaded")
        assert next_id == "plan"

    def test_advance_with_invalid_condition(self, tmp_graph: Path) -> None:
        """Test advancing with a non-matching condition raises ValueError."""
        ge = GraphExecutor(str(tmp_graph))
        with pytest.raises(ValueError, match="No transition"):
            ge.advance("init", "invalid_condition")

    def test_advance_multiple_transitions(self, tmp_graph: Path) -> None:
        """Test advancing with multiple possible transitions."""
        ge = GraphExecutor(str(tmp_graph))
        assert ge.advance("plan", "plan_ready") == "code"
        assert ge.advance("plan", "plan_needs_revision") == "plan"


class TestGetAvailableTransitions:
    """Tests for get_available_transitions."""

    def test_single_transition(self, tmp_graph: Path) -> None:
        """Test node with single transition."""
        ge = GraphExecutor(str(tmp_graph))
        transitions = ge.get_available_transitions("init")
        assert len(transitions) == 1
        assert transitions[0]["to"] == "plan"

    def test_multiple_transitions(self, tmp_graph: Path) -> None:
        """Test node with multiple transitions."""
        ge = GraphExecutor(str(tmp_graph))
        transitions = ge.get_available_transitions("plan")
        assert len(transitions) == 2


class TestValidateGraph:
    """Tests for validate_graph."""

    def test_valid_graph(self, tmp_graph: Path) -> None:
        """Test that a valid graph passes validation."""
        ge = GraphExecutor(str(tmp_graph))
        valid, issues = ge.validate_graph()
        assert valid is True
        # The tmp_graph has a deterministic loop (init -> plan -> code -> init)
        # so there may be a loop warning, but no hard errors
        hard_errors = [i for i in issues if not i.startswith("Warning:")]
        assert hard_errors == []

    def test_invalid_transition_target(self, tmp_path: Path) -> None:
        """Test graph with transition to nonexistent node."""
        graph_file = tmp_path / "bad_graph.yaml"
        data = {
            "nodes": [
                {
                    "id": "start",
                    "prompt_file": "p.md",
                    "description": "Start",
                    "transitions": [{"to": "nonexistent", "condition": "x"}],
                    "max_retries": 1,
                }
            ],
            "default_start": "start",
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(data, f)
        ge = GraphExecutor(str(graph_file))
        valid, issues = ge.validate_graph()
        assert valid is False
        assert any("nonexistent" in issue for issue in issues)


class TestAddRemoveNode:
    """Tests for add_node and remove_node."""

    def test_add_node(self, tmp_graph: Path) -> None:
        """Test adding a new node."""
        ge = GraphExecutor(str(tmp_graph))
        ge.add_node({"id": "new_node", "prompt_file": "prompts/new.md", "description": "New"})
        node = ge.get_node("new_node")
        assert node["id"] == "new_node"

    def test_add_duplicate_node(self, tmp_graph: Path) -> None:
        """Test that adding a duplicate node raises ValueError."""
        ge = GraphExecutor(str(tmp_graph))
        with pytest.raises(ValueError, match="already exists"):
            ge.add_node({"id": "init"})

    def test_add_node_without_id(self, tmp_graph: Path) -> None:
        """Test that adding a node without id raises ValueError."""
        ge = GraphExecutor(str(tmp_graph))
        with pytest.raises(ValueError, match="must have an 'id' field"):
            ge.add_node({"prompt_file": "test.md"})

    def test_remove_node_no_references(self, tmp_graph: Path) -> None:
        """Test removing a node that nothing transitions to."""
        ge = GraphExecutor(str(tmp_graph))
        # Add a node with no incoming transitions
        ge.add_node({"id": "isolated", "description": "Isolated node"})
        ge.remove_node("isolated")
        with pytest.raises(KeyError):
            ge.get_node("isolated")

    def test_remove_node_with_references(self, tmp_graph: Path) -> None:
        """Test that removing a referenced node raises ValueError."""
        ge = GraphExecutor(str(tmp_graph))
        with pytest.raises(ValueError, match="Cannot remove"):
            ge.remove_node("plan")


class TestSaveGraph:
    """Tests for save_graph."""

    def test_save_and_reload(self, tmp_graph: Path) -> None:
        """Test that saving and reloading preserves the graph."""
        ge = GraphExecutor(str(tmp_graph))
        ge.add_node({"id": "saved_node", "description": "Test save"})
        ge.save_graph()

        # Reload
        ge2 = GraphExecutor(str(tmp_graph))
        node = ge2.get_node("saved_node")
        assert node["id"] == "saved_node"


class TestLoopDetection:
    """Tests for deterministic loop detection in validate_graph."""

    def test_validate_detects_trivial_loop(self, tmp_path: Path) -> None:
        """Test that a graph where first transitions form a cycle produces a warning."""
        graph_file = tmp_path / "loop_graph.yaml"
        data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/init.md",
                    "description": "Init",
                    "transitions": [{"to": "plan", "condition": "ready"}],
                    "max_retries": 1,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/plan.md",
                    "description": "Plan",
                    "transitions": [{"to": "code", "condition": "planned"}],
                    "max_retries": 1,
                },
                {
                    "id": "code",
                    "prompt_file": "prompts/code.md",
                    "description": "Code",
                    "transitions": [{"to": "plan", "condition": "needs_revision"}],
                    "max_retries": 1,
                },
            ],
            "default_start": "init",
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(data, f)
        ge = GraphExecutor(str(graph_file))
        valid, issues = ge.validate_graph()
        # Loop warning should not make graph invalid
        assert valid is True
        # Should have a warning about loop
        warnings = [i for i in issues if i.startswith("Warning:")]
        assert len(warnings) == 1
        assert "Deterministic loop" in warnings[0]
        assert "plan -> code -> plan" in warnings[0]

    def test_validate_no_false_positive_loop(self, tmp_path: Path) -> None:
        """Test that a graph where first transitions terminate does not warn."""
        graph_file = tmp_path / "noloop_graph.yaml"
        data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/init.md",
                    "description": "Init",
                    "transitions": [{"to": "plan", "condition": "ready"}],
                    "max_retries": 1,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/plan.md",
                    "description": "Plan",
                    "transitions": [{"to": "done", "condition": "complete"}],
                    "max_retries": 1,
                },
                {
                    "id": "done",
                    "prompt_file": "prompts/done.md",
                    "description": "Done",
                    "transitions": [],
                    "max_retries": 1,
                },
            ],
            "default_start": "init",
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(data, f)
        ge = GraphExecutor(str(graph_file))
        valid, issues = ge.validate_graph()
        assert valid is True
        warnings = [i for i in issues if i.startswith("Warning:")]
        assert len(warnings) == 0

    def test_validate_loop_warning_not_error(self, tmp_path: Path) -> None:
        """Test that loop detection is a warning, not a hard validity failure."""
        graph_file = tmp_path / "loop_valid.yaml"
        data = {
            "nodes": [
                {
                    "id": "a",
                    "prompt_file": "prompts/a.md",
                    "description": "Node A",
                    "transitions": [
                        {"to": "b", "condition": "go"},
                        {"to": "c", "condition": "skip"},
                    ],
                    "max_retries": 1,
                },
                {
                    "id": "b",
                    "prompt_file": "prompts/b.md",
                    "description": "Node B",
                    "transitions": [{"to": "a", "condition": "back"}],
                    "max_retries": 1,
                },
                {
                    "id": "c",
                    "prompt_file": "prompts/c.md",
                    "description": "Node C",
                    "transitions": [],
                    "max_retries": 1,
                },
            ],
            "default_start": "a",
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(data, f)
        ge = GraphExecutor(str(graph_file))
        valid, issues = ge.validate_graph()
        # Graph is valid even with a loop warning
        assert valid is True
        # There should be a loop warning (first transition of a goes to b, first of b goes to a)
        warnings = [i for i in issues if i.startswith("Warning:")]
        assert len(warnings) == 1
        assert "a -> b -> a" in warnings[0]
