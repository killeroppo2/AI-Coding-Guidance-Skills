"""Tests targeting specific uncovered code paths to improve coverage.

These tests address the coverage gaps identified in:
- kernel/evolution/engine.py (lines 158, 228-240, 254-255)
- kernel/graph_executor.py (lines 144, 161, 171-172, 176)
- knowledge/skill_composer.py (line 97)
- knowledge/store.py (lines 48, 50, 245, 271-274)
- memory/state_manager.py (line 67)
- runner.py (lines 96, 100-103, 119, 132-136, 153)
"""

from pathlib import Path

import pytest
import yaml

import runner
from kernel.evolution.engine import EvolutionEngine
from kernel.graph_executor import GraphExecutor
from knowledge.skill_composer import SkillComposer
from knowledge.store import KnowledgeStore
from memory.state_manager import StateManager

# ============================================================
# GraphExecutor coverage gaps
# ============================================================


class TestGraphExecutorValidationGaps:
    """Tests for validate_graph uncovered branches."""

    def test_default_start_not_in_nodes(self, tmp_path: Path) -> None:
        """Test validate_graph when default_start references a missing node (line 144)."""
        graph_file = tmp_path / "graph.yaml"
        data = {
            "nodes": [
                {
                    "id": "only_node",
                    "prompt_file": "p.md",
                    "description": "Only node",
                    "transitions": [],
                    "max_retries": 1,
                }
            ],
            "default_start": "missing_start",
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(data, f)
        ge = GraphExecutor(str(graph_file))
        valid, issues = ge.validate_graph()
        assert valid is False
        assert any("missing_start" in issue and "not found" in issue for issue in issues)

    def test_orphan_node_detection(self, tmp_path: Path) -> None:
        """Test validate_graph detects orphan nodes unreachable from start (line 176)."""
        graph_file = tmp_path / "graph.yaml"
        data = {
            "nodes": [
                {
                    "id": "start",
                    "prompt_file": "p.md",
                    "description": "Start",
                    "transitions": [],
                    "max_retries": 1,
                },
                {
                    "id": "orphan",
                    "prompt_file": "p.md",
                    "description": "Orphan - no path from start",
                    "transitions": [],
                    "max_retries": 1,
                },
            ],
            "default_start": "start",
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(data, f)
        ge = GraphExecutor(str(graph_file))
        valid, issues = ge.validate_graph()
        assert valid is False
        assert any("orphan" in issue and "unreachable" in issue for issue in issues)

    def test_validate_with_transition_to_nonexistent_in_queue(self, tmp_path: Path) -> None:
        """Test validate_graph handles transitions pointing to non-existent nodes in BFS.

        When a transition points to a non-existent node, the BFS adds it to the queue.
        When processing it, `current not in node_ids` triggers continue.
        """
        graph_file = tmp_path / "graph.yaml"
        data = {
            "nodes": [
                {
                    "id": "start",
                    "prompt_file": "p.md",
                    "description": "Start",
                    "transitions": [{"to": "ghost_node", "condition": "go"}],
                    "max_retries": 1,
                },
            ],
            "default_start": "start",
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(data, f)
        ge = GraphExecutor(str(graph_file))
        valid, issues = ge.validate_graph()
        assert valid is False
        # The ghost_node transition is invalid
        assert any("ghost_node" in issue for issue in issues)

    def test_validate_graph_with_cycle_hits_reachable_check(self, tmp_path: Path) -> None:
        """Test validate_graph BFS handles cycles by skipping already-reachable nodes (line 161).

        When multiple transitions lead to the same node, it enters the queue twice.
        The second time it's popped, it's already in `reachable` so `continue` is hit.
        """
        graph_file = tmp_path / "graph.yaml"
        data = {
            "nodes": [
                {
                    "id": "a",
                    "prompt_file": "p.md",
                    "description": "Node A",
                    "transitions": [
                        {"to": "b", "condition": "go_b"},
                        {"to": "c", "condition": "go_c"},
                    ],
                    "max_retries": 1,
                },
                {
                    "id": "b",
                    "prompt_file": "p.md",
                    "description": "Node B",
                    "transitions": [{"to": "c", "condition": "go_c"}],
                    "max_retries": 1,
                },
                {
                    "id": "c",
                    "prompt_file": "p.md",
                    "description": "Node C",
                    "transitions": [{"to": "a", "condition": "back"}],
                    "max_retries": 1,
                },
            ],
            "default_start": "a",
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(data, f)
        ge = GraphExecutor(str(graph_file))
        valid, issues = ge.validate_graph()
        # Graph is valid - all nodes reachable, all transitions valid
        assert valid is True
        # May have a loop warning but no hard errors
        hard_errors = [i for i in issues if not i.startswith("Warning:")]
        assert hard_errors == []


# ============================================================
# Evolution Engine coverage gaps
# ============================================================


class TestEvolutionRollbackGaps:
    """Tests for rollback uncovered branches."""

    @pytest.fixture
    def evo_setup(self, tmp_path: Path):
        """Set up evolution engine for rollback tests."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "evolution").mkdir()
        (kernel_dir / "prompts").mkdir()

        graph_file = kernel_dir / "graph.yaml"
        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Initialize",
                    "transitions": [{"to": "plan", "condition": "go"}],
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
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        (kernel_dir / "prompts" / "orchestrator.md").write_text("Original orchestrator")
        (kernel_dir / "prompts" / "planner.md").write_text("Original planner")

        graph_executor = GraphExecutor(str(graph_file))
        engine = EvolutionEngine(str(kernel_dir), graph_executor)
        return engine, kernel_dir, graph_executor

    def test_rollback_remove_node(self, evo_setup) -> None:
        """Test rolling back a remove_node change re-adds the node (lines 228-232)."""
        engine, kernel_dir, graph_executor = evo_setup

        # Add an isolated node, then remove it via engine
        graph_executor.add_node({"id": "temp_node", "description": "Temporary"})
        graph_executor.save_graph()

        change = engine.propose_change(
            "remove_node",
            {
                "node_id": "temp_node",
                "node_backup": {"id": "temp_node", "description": "Temporary"},
            },
            "Remove temp",
        )
        result = engine.apply_change(change)
        assert result is True

        # Node should be gone
        with pytest.raises(KeyError):
            graph_executor.get_node("temp_node")

        # Rollback should re-add it
        rollback_result = engine.rollback(change["id"])
        assert rollback_result is True
        node = graph_executor.get_node("temp_node")
        assert node["id"] == "temp_node"

    def test_rollback_modify_prompt(self, evo_setup) -> None:
        """Test rolling back a modify_prompt restores original content (lines 234-240)."""
        engine, kernel_dir, _ = evo_setup

        original_content = "Original planner"
        change = engine.propose_change(
            "modify_prompt",
            {
                "prompt_file": "prompts/planner.md",
                "content": "Modified planner content",
                "original_content": original_content,
            },
            "Modify planner",
        )
        result = engine.apply_change(change)
        assert result is True

        # Verify modification
        prompt_path = kernel_dir / "prompts" / "planner.md"
        assert prompt_path.read_text() == "Modified planner content"

        # Rollback
        rollback_result = engine.rollback(change["id"])
        assert rollback_result is True
        assert prompt_path.read_text() == original_content

    def test_rollback_exception_returns_false(self, evo_setup) -> None:
        """Test that rollback returns False when an exception occurs (lines 254-255)."""
        engine, kernel_dir, graph_executor = evo_setup

        # Apply an add_node change
        change = engine.propose_change(
            "add_node",
            {"node": {"id": "will_fail", "description": "test"}},
            "Add node to rollback",
        )
        engine.apply_change(change)

        # Now manually remove the node so rollback will fail with KeyError
        graph_executor.graph["nodes"] = [
            n for n in graph_executor.graph["nodes"] if n["id"] != "will_fail"
        ]
        graph_executor.save_graph()

        # Rollback should fail because node is already gone (remove_node will raise KeyError)
        result = engine.rollback(change["id"])
        assert result is False


class TestEvolutionReorderPartialOrder:
    """Test reorder when not all nodes are in the order list (line 158)."""

    @pytest.fixture
    def evo_setup(self, tmp_path: Path):
        """Set up evolution engine for reorder tests."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "evolution").mkdir()

        graph_file = kernel_dir / "graph.yaml"
        graph_data = {
            "nodes": [
                {
                    "id": "a",
                    "prompt_file": "",
                    "description": "A",
                    "transitions": [],
                    "max_retries": 1,
                },
                {
                    "id": "b",
                    "prompt_file": "",
                    "description": "B",
                    "transitions": [],
                    "max_retries": 1,
                },
                {
                    "id": "c",
                    "prompt_file": "",
                    "description": "C",
                    "transitions": [],
                    "max_retries": 1,
                },
            ],
            "default_start": "a",
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        graph_executor = GraphExecutor(str(graph_file))
        engine = EvolutionEngine(str(kernel_dir), graph_executor)
        return engine, kernel_dir, graph_executor

    def test_reorder_partial_list_appends_missing(self, evo_setup) -> None:
        """Test that reorder with partial order appends unlisted nodes at end (line 158)."""
        engine, _, graph_executor = evo_setup

        # Only reorder "c" and "a", leaving "b" out
        change = engine.propose_change(
            "reorder",
            {"order": ["c", "a"]},
            "Partial reorder",
        )
        result = engine.apply_change(change)
        assert result is True

        node_ids = [n["id"] for n in graph_executor.graph["nodes"]]
        # "c" and "a" come first (in that order), then "b" is appended
        assert node_ids == ["c", "a", "b"]


# ============================================================
# KnowledgeStore coverage gaps
# ============================================================


class TestKnowledgeStoreIndexGaps:
    """Tests for _load_index uncovered branches."""

    def test_load_index_no_items_key(self, tmp_path: Path) -> None:
        """Test _load_index when YAML exists but has no 'items' key (line 48)."""
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        rules_dir = knowledge_dir / "rules"
        rules_dir.mkdir()
        # Write index without 'items' key
        index_path = rules_dir / "_index.yaml"
        with open(index_path, "w") as f:
            yaml.safe_dump({"version": "1.0", "description": "Rules"}, f)

        ks = KnowledgeStore(str(knowledge_dir))
        # _load_index should add "items" key
        index = ks._load_index(rules_dir)
        assert "items" in index
        assert index["items"] == []

    def test_load_index_file_not_exists(self, tmp_path: Path) -> None:
        """Test _load_index when index file does not exist (line 50)."""
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        nonexistent_dir = knowledge_dir / "empty_category"
        nonexistent_dir.mkdir()
        # No _index.yaml exists

        ks = KnowledgeStore(str(knowledge_dir))
        index = ks._load_index(nonexistent_dir)
        assert index == {"items": []}


class TestKnowledgeStoreRebuildSkills:
    """Tests for rebuild_index('skills') uncovered branches."""

    def test_rebuild_skills_index(self, tmp_path: Path) -> None:
        """Test rebuild_index for skills scans directories with SKILL.md (lines 245, 271-274)."""
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()

        # Skills directory is now a sibling of knowledge/
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create skill directories with SKILL.md
        skill1_dir = skills_dir / "my-skill"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text("# My Skill\nDoes things.")

        skill2_dir = skills_dir / "another-skill"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text("# Another Skill\nDoes other things.")

        # Create a dir without SKILL.md (should be ignored)
        no_skill_dir = skills_dir / "not-a-skill"
        no_skill_dir.mkdir()
        (no_skill_dir / "README.md").write_text("Not a skill")

        # Write empty initial index
        with open(skills_dir / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

        # Also create rules and patterns dirs to satisfy KnowledgeStore
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "patterns").mkdir()

        ks = KnowledgeStore(str(knowledge_dir))
        ks.rebuild_index("skills")

        # Verify index was rebuilt
        skills = ks.list_skills()
        skill_names = [s["name"] for s in skills]
        assert "my-skill" in skill_names
        assert "another-skill" in skill_names
        assert "not-a-skill" not in skill_names


# ============================================================
# SkillComposer coverage gaps
# ============================================================


class TestSkillComposerAltPath:
    """Tests for get_skill_content alt_path branch (line 97)."""

    def test_get_skill_content_from_repo_root(self, tmp_path: Path) -> None:
        """Test that get_skill_content finds SKILL.md at repo root level (line 97)."""
        # Set up knowledge dir
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "patterns").mkdir()

        # Skills directory is a sibling of knowledge/
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        with open(skills_dir / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

        # The skill path points to a directory at repo root level (parent of knowledge_dir)
        # Skill NOT in skills_dir, but at tmp_path / "grill-me" / SKILL.md
        skill_at_root = tmp_path / "grill-me"
        skill_at_root.mkdir()
        (skill_at_root / "SKILL.md").write_text("# Grill Me\nInterview prep skill.")

        ks = KnowledgeStore(str(knowledge_dir))
        ks.add_skill("grill-me", "Interview prep", path="grill-me")

        sc = SkillComposer(ks)
        content = sc.get_skill_content("grill-me")
        assert "Grill Me" in content
        assert "Interview prep skill" in content


# ============================================================
# StateManager coverage gaps
# ============================================================


class TestStateManagerLoadGaps:
    """Tests for load_state uncovered branches."""

    def test_load_state_merges_missing_keys(self, tmp_path: Path) -> None:
        """Test that load_state merges defaults for missing keys (line 67)."""
        state_file = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        # Write a minimal state file missing some default keys
        partial_state = {
            "current_node": "plan",
            "iteration_count": 5,
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(partial_state, f)

        sm = StateManager(str(state_file), str(memory_dir))
        state = sm.get_state()

        # Should have the keys from the file
        assert state["current_node"] == "plan"
        assert state["iteration_count"] == 5
        # Should have merged in defaults for missing keys
        assert state["max_iterations"] == 30
        assert state["goal"] == ""
        assert state["status"] == "idle"
        assert state["errors"] == []
        assert "context" in state


# ============================================================
# Runner coverage gaps
# ============================================================


class TestRunnerGaps:
    """Tests for runner.py uncovered code paths."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a complete runner environment in tmp_path."""
        # state.yaml
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
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

        # graph.yaml with a terminal node (no transitions)
        graph_file = tmp_path / "kernel" / "graph.yaml"
        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Initialize",
                    "transitions": [{"to": "terminal", "condition": "goal_loaded"}],
                    "max_retries": 1,
                },
                {
                    "id": "terminal",
                    "prompt_file": "prompts/terminal.md",
                    "description": "Terminal node with no transitions",
                    "transitions": [],
                    "max_retries": 1,
                },
            ],
            "default_start": "init",
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        # Prompt files
        prompts_dir = tmp_path / "kernel" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "orchestrator.md").write_text("Orchestrator prompt content")
        # terminal.md intentionally NOT created to test the "not found" branch

        # Memory dir
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "decisions.jsonl").touch()
        (memory_dir / "reflections.jsonl").touch()
        (memory_dir / "current_goal.md").touch()
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump(
                {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}, f
            )

        # Knowledge dir
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_runner_is_complete_breaks_loop(self, runner_env: Path, monkeypatch) -> None:
        """Test that runner breaks when is_complete() returns True (line 96)."""
        # Set progress to complete so is_complete() triggers on first check
        progress_path = runner_env / "memory" / "progress.yaml"
        with open(progress_path, "w") as f:
            yaml.safe_dump(
                {"iteration": 0, "tasks_total": 5, "tasks_done": 5, "status": "complete"}, f
            )

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main(["--goal", "test", "--max-iterations", "10"])
        # Should have completed without iterating
        assert state["status"] == "complete"
        assert state["iteration_count"] == 0

    def test_runner_key_error_on_current_node(self, runner_env: Path, monkeypatch) -> None:
        """Test runner handles KeyError when current node is invalid (lines 100-103)."""
        # Set state to reference a non-existent node
        state_file = runner_env / "kernel" / "state.yaml"
        state_data = {
            "current_node": "nonexistent_node",
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

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main(["--goal", "test", "--max-iterations", "5", "--complexity", "high"])
        assert state["status"] == "error"
        assert len(state["errors"]) > 0
        assert "nonexistent_node" in state["errors"][0]

    def test_runner_prompt_not_found_dry_run(self, runner_env: Path, monkeypatch, capsys) -> None:
        """Test dry-run shows [not found] when prompt file is missing (line 119)."""
        # Ensure terminal.md does NOT exist (it shouldn't from fixture)
        # But the first iteration uses init -> orchestrator.md which exists
        # So we need to make init's prompt file missing
        prompt_path = runner_env / "kernel" / "prompts" / "orchestrator.md"
        prompt_path.unlink()

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        runner.main(["--goal", "test", "--max-iterations", "1", "--dry-run"])
        captured = capsys.readouterr()
        assert "[未找到]" in captured.out

    def test_runner_no_transitions_completes(self, runner_env: Path, monkeypatch) -> None:
        """Test runner completes when reaching a node with no transitions (lines 132-136)."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main(["--goal", "test", "--max-iterations", "10", "--complexity", "high"])
        # After init -> terminal (which has no transitions), it should complete
        assert state["status"] == "complete"

    def test_runner_no_transitions_dry_run(self, runner_env: Path, monkeypatch, capsys) -> None:
        """Test dry-run shows END when reaching node with no transitions (lines 133-135)."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        runner.main(["--goal", "test", "--max-iterations", "10", "--dry-run"])
        captured = capsys.readouterr()
        assert "结束" in captured.out

    def test_runner_max_iterations_completes(self, tmp_path: Path, monkeypatch) -> None:
        """Test runner marks complete when max iterations loop ends (covers the running->complete transition)."""
        # Set up a cycling graph
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
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

        # Graph that cycles: init -> init (always loops)
        graph_file = tmp_path / "kernel" / "graph.yaml"
        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Initialize",
                    "transitions": [{"to": "init", "condition": "loop"}],
                    "max_retries": 10,
                },
            ],
            "default_start": "init",
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        prompts_dir = tmp_path / "kernel" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "orchestrator.md").write_text("prompt")

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "decisions.jsonl").touch()
        (memory_dir / "reflections.jsonl").touch()
        (memory_dir / "current_goal.md").touch()
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump(
                {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}, f
            )

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        monkeypatch.setattr(runner, "KERNEL_ROOT", tmp_path)
        state = runner.main(
            ["--goal", "test loop", "--max-iterations", "3", "--complexity", "high"]
        )
        assert state["iteration_count"] == 3
        assert state["status"] == "complete"
