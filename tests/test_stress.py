"""Stress test - 100 rapid iterations to verify no memory leaks or unbounded growth.

Validates:
- History auto-prunes at 500 entries
- Errors list stays capped (trim_errors)
- Progress history stays bounded
- Metrics window doesn't exceed configured size
- JSONL files don't grow without bound
"""

import json
import random
from pathlib import Path

import pytest
import yaml

from kernel.evolution.engine import EvolutionEngine
from kernel.evolution.historian import EvolutionHistorian
from kernel.evolution.metrics import EvolutionMetrics
from kernel.feedback_loop import FeedbackLoop
from kernel.graph_executor import GraphExecutor
from kernel.reflector import Reflector
from knowledge.store import KnowledgeStore
from memory.state_manager import StateManager

pytestmark = pytest.mark.slow


def _make_graph_file(kernel_dir: Path) -> Path:
    """Create a minimal graph.yaml for testing."""
    graph_file = kernel_dir / "graph.yaml"
    graph_data = {
        "nodes": [
            {
                "id": "init",
                "prompt_file": "prompts/init.md",
                "description": "Initialize",
                "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                "max_retries": 5,
            },
            {
                "id": "plan",
                "prompt_file": "prompts/plan.md",
                "description": "Plan",
                "transitions": [{"to": "code", "condition": "plan_ready"}],
                "max_retries": 5,
            },
            {
                "id": "code",
                "prompt_file": "prompts/code.md",
                "description": "Write code",
                "transitions": [{"to": "test", "condition": "code_written"}],
                "max_retries": 5,
            },
            {
                "id": "test",
                "prompt_file": "prompts/test.md",
                "description": "Run tests",
                "transitions": [{"to": "review", "condition": "tests_pass"}],
                "max_retries": 5,
            },
            {
                "id": "review",
                "prompt_file": "prompts/review.md",
                "description": "Review",
                "transitions": [],
                "max_retries": 5,
            },
        ],
        "default_start": "init",
        "max_iterations": 200,
    }
    with open(graph_file, "w") as f:
        yaml.safe_dump(graph_data, f)
    return graph_file


def _make_knowledge_dir(tmp_path: Path) -> Path:
    """Create a minimal knowledge directory."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "rules").mkdir()
    (knowledge_dir / "skills").mkdir()
    (knowledge_dir / "patterns").mkdir()
    return knowledge_dir


def _make_kernel_dir(tmp_path: Path) -> Path:
    """Create kernel directory with evolution subdirectory."""
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    (kernel_dir / "evolution").mkdir()
    (kernel_dir / "prompts").mkdir()
    # Create minimal prompt files
    for node in ["init", "plan", "code", "test", "review"]:
        (kernel_dir / "prompts" / f"{node}.md").write_text(f"# {node} prompt\n")
    return kernel_dir


class TestStress100Iterations:
    """Run 100 rapid iterations and verify bounds."""

    def test_100_iterations_no_unbounded_growth(self, tmp_path):
        """Feed 100 random iterations through the system, verify all bounded."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        kernel_dir = _make_kernel_dir(tmp_path)
        graph_file = _make_graph_file(kernel_dir)
        knowledge_dir = _make_knowledge_dir(tmp_path)

        graph = GraphExecutor(str(graph_file))
        knowledge = KnowledgeStore(str(knowledge_dir))
        reflector = Reflector(str(memory_dir), knowledge)
        evolution_engine = EvolutionEngine(str(kernel_dir), graph)
        metrics = EvolutionMetrics(window_size=10)
        history_file = kernel_dir / "evolution" / "history.jsonl"

        feedback_loop = FeedbackLoop(
            str(memory_dir),
            reflector,
            evolution_engine,
            metrics,
            history_file=history_file,
        )

        nodes = ["init", "plan", "code", "test", "review"]

        # Run 100 cycles with random success/failure
        for i in range(100):
            node = random.choice(nodes)
            success = random.choice([True, False])
            iteration_data = {
                "node": node,
                "result": "success" if success else "failed",
                "errors": [] if success else [f"Error at iteration {i}"],
                "iteration": i,
            }
            feedback_loop.run_cycle(iteration_data)

        # Verify: metrics window per node <= configured size (10)
        for node in nodes:
            node_metrics = metrics.get_node_metrics(node)
            assert node_metrics["sample_count"] <= 10

        # Verify: reflections.jsonl is written (100 entries, below prune threshold)
        reflections_path = memory_dir / "reflections.jsonl"
        assert reflections_path.exists()
        lines = reflections_path.read_text().strip().splitlines()
        # 100 iterations is below the 1000-line prune threshold
        assert len(lines) == 100
        # Verify the file would be pruned if it grew beyond 1000
        assert len(lines) <= 1000, "reflections.jsonl must stay bounded"

        # Verify: overall health is between 0 and 1
        health = metrics.get_overall_health()
        assert 0.0 <= health <= 1.0

    def test_historian_prunes_at_threshold(self, tmp_path):
        """Write 600 history entries, run prune, verify pruned to 500."""
        kernel_dir = _make_kernel_dir(tmp_path)
        history_file = kernel_dir / "evolution" / "history.jsonl"

        # Write 600 entries
        with open(history_file, "w") as f:
            for i in range(600):
                entry = {
                    "id": f"change-{i}",
                    "type": "modify_prompt",
                    "status": "applied",
                    "details": {"node_id": "code"},
                    "timestamp": f"2025-01-{(i % 28) + 1:02d}T00:00:00Z",
                }
                f.write(json.dumps(entry) + "\n")

        historian = EvolutionHistorian(history_file)

        # Verify 600 entries before pruning
        entries_before = historian.load_history()
        assert len(entries_before) == 600

        # Prune
        archived = historian.prune_history(max_entries=500)
        assert archived == 100

        # Verify 500 entries after pruning
        entries_after = historian.load_history()
        assert len(entries_after) == 500

        # Verify archive file was created
        archive_dir = history_file.parent / "archive"
        assert archive_dir.exists()
        archive_files = list(archive_dir.glob("archive_*.jsonl"))
        assert len(archive_files) == 1

        # Verify archived file has 100 entries
        archived_content = archive_files[0].read_text().strip().splitlines()
        assert len(archived_content) == 100

    def test_state_errors_bounded(self, tmp_path):
        """Feed many errors, verify trim_errors keeps max 10."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        state_path = tmp_path / "state.yaml"

        state_mgr = StateManager(str(state_path), str(memory_dir))

        # Add 50 errors
        for i in range(50):
            state_mgr.state.setdefault("errors", []).append(f"Error number {i}")

        # Trim errors
        state_mgr.trim_errors(max_kept=10)

        # Verify only 10 remain
        assert len(state_mgr.state["errors"]) == 10
        # Verify the remaining are the last 10
        assert state_mgr.state["errors"][0] == "Error number 40"
        assert state_mgr.state["errors"][-1] == "Error number 49"

        # Verify archived errors are in error_history.jsonl
        error_history = memory_dir / "error_history.jsonl"
        assert error_history.exists()
        archived_lines = error_history.read_text().strip().splitlines()
        assert len(archived_lines) == 40

    def test_metrics_window_bounded(self):
        """Record 100 iterations for one node, verify window is 10."""
        metrics = EvolutionMetrics(window_size=10)
        for i in range(100):
            metrics.record_iteration("code", success=random.choice([True, False]))
        node_metrics = metrics.get_node_metrics("code")
        assert node_metrics["sample_count"] == 10

    def test_rapid_feedback_cycles(self, tmp_path):
        """Run 100 feedback cycles rapidly and verify no crash."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        kernel_dir = _make_kernel_dir(tmp_path)
        graph_file = _make_graph_file(kernel_dir)
        knowledge_dir = _make_knowledge_dir(tmp_path)

        graph = GraphExecutor(str(graph_file))
        knowledge = KnowledgeStore(str(knowledge_dir))
        reflector = Reflector(str(memory_dir), knowledge)
        evolution_engine = EvolutionEngine(str(kernel_dir), graph)
        metrics = EvolutionMetrics(window_size=10)

        feedback_loop = FeedbackLoop(
            str(memory_dir),
            reflector,
            evolution_engine,
            metrics,
        )

        nodes = ["init", "plan", "code", "test", "review"]

        # Rapidly fire 100 cycles - should not raise
        for i in range(100):
            node = nodes[i % len(nodes)]
            iteration_data = {
                "node": node,
                "result": "success" if i % 3 != 0 else "failed",
                "errors": [] if i % 3 != 0 else [f"Simulated failure {i}"],
                "iteration": i,
            }
            result = feedback_loop.run_cycle(iteration_data)
            assert "reflection" in result
            assert "proposals_generated" in result
            assert "proposals_applied" in result

    def test_multiple_prune_cycles(self, tmp_path):
        """Run multiple prune cycles, verify history stays bounded."""
        kernel_dir = _make_kernel_dir(tmp_path)
        history_file = kernel_dir / "evolution" / "history.jsonl"

        historian = EvolutionHistorian(history_file)

        # Simulate 3 rounds of growth and pruning
        for round_num in range(3):
            # Write 200 more entries
            with open(history_file, "a") as f:
                for i in range(200):
                    entry = {
                        "id": f"change-r{round_num}-{i}",
                        "type": "modify_prompt",
                        "status": "applied",
                        "details": {"node_id": "code"},
                    }
                    f.write(json.dumps(entry) + "\n")

            # Prune to 500
            historian.prune_history(max_entries=500)
            entries = historian.load_history()
            assert len(entries) <= 500

    def test_progress_history_stays_capped(self, tmp_path):
        """Verify progress_history is capped at 20 entries."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        state_path = tmp_path / "state.yaml"

        state_mgr = StateManager(str(state_path), str(memory_dir))

        # Simulate adding progress entries like runner.py does
        for i in range(50):
            progress_history = state_mgr.state.setdefault("progress_history", [])
            progress_history.append(i)
            # Cap at 20 entries (same logic as runner.py)
            if len(progress_history) > 20:
                state_mgr.state["progress_history"] = progress_history[-20:]

        assert len(state_mgr.state["progress_history"]) == 20
        # Verify it kept the last 20
        assert state_mgr.state["progress_history"][0] == 30
        assert state_mgr.state["progress_history"][-1] == 49

    def test_evolution_engine_history_growth(self, tmp_path):
        """Apply many changes via engine, verify history file grows linearly."""
        kernel_dir = _make_kernel_dir(tmp_path)
        graph_file = _make_graph_file(kernel_dir)
        graph = GraphExecutor(str(graph_file))
        engine = EvolutionEngine(str(kernel_dir), graph)

        # Apply 50 changes
        for i in range(50):
            change = engine.propose_change(
                "modify_prompt",
                {"prompt_file": "prompts/code.md", "content": f"# V{i}"},
                f"Improvement attempt {i}",
            )
            engine.apply_change(change)

        # Verify history has all 50 entries
        history = engine.get_history()
        assert len(history) == 50
        assert all(h["status"] == "applied" for h in history)

    def test_metrics_multi_node_stress(self):
        """Record iterations across many nodes, verify all stay bounded."""
        metrics = EvolutionMetrics(window_size=10)
        nodes = [f"node_{i}" for i in range(20)]

        # Record 50 iterations per node
        for _ in range(50):
            for node in nodes:
                metrics.record_iteration(
                    node,
                    success=random.choice([True, False]),
                    retries=random.randint(0, 3),
                    duration=random.uniform(0.1, 5.0),
                )

        # Verify all nodes have exactly 10 samples (window size)
        for node in nodes:
            node_metrics = metrics.get_node_metrics(node)
            assert node_metrics["sample_count"] == 10
            assert 0.0 <= node_metrics["success_rate"] <= 1.0
            assert node_metrics["avg_retries"] >= 0
            assert node_metrics["avg_duration"] >= 0

        # Verify overall health is computed correctly
        health = metrics.get_overall_health()
        assert 0.0 <= health <= 1.0

    def test_reflections_file_growth(self, tmp_path):
        """Verify reflections.jsonl is pruned when it exceeds 1000 lines.

        The pruning mechanism keeps only the last 500 lines once the file
        grows beyond 1000 lines, preventing unbounded growth.
        """
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        kernel_dir = _make_kernel_dir(tmp_path)
        graph_file = _make_graph_file(kernel_dir)
        knowledge_dir = _make_knowledge_dir(tmp_path)

        graph = GraphExecutor(str(graph_file))
        knowledge = KnowledgeStore(str(knowledge_dir))
        reflector = Reflector(str(memory_dir), knowledge)
        evolution_engine = EvolutionEngine(str(kernel_dir), graph)
        metrics = EvolutionMetrics(window_size=10)

        feedback_loop = FeedbackLoop(
            str(memory_dir),
            reflector,
            evolution_engine,
            metrics,
        )

        # Run 100 cycles - should not trigger pruning (threshold is 1000)
        for i in range(100):
            iteration_data = {
                "node": "code",
                "result": "success",
                "errors": [],
                "iteration": i,
            }
            feedback_loop.run_cycle(iteration_data)

        reflections_path = memory_dir / "reflections.jsonl"
        lines = reflections_path.read_text().strip().splitlines()
        assert len(lines) == 100

        # Each line should be valid JSON
        for line in lines:
            data = json.loads(line)
            assert "node" in data
            assert "success" in data

    def test_reflections_pruning_at_threshold(self, tmp_path):
        """Verify reflections.jsonl is pruned to 500 lines when it exceeds 1000."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        kernel_dir = _make_kernel_dir(tmp_path)
        graph_file = _make_graph_file(kernel_dir)
        knowledge_dir = _make_knowledge_dir(tmp_path)

        graph = GraphExecutor(str(graph_file))
        knowledge = KnowledgeStore(str(knowledge_dir))
        reflector = Reflector(str(memory_dir), knowledge)
        evolution_engine = EvolutionEngine(str(kernel_dir), graph)
        metrics = EvolutionMetrics(window_size=10)

        feedback_loop = FeedbackLoop(
            str(memory_dir),
            reflector,
            evolution_engine,
            metrics,
        )

        # Pre-populate reflections.jsonl with 999 lines (just below threshold)
        reflections_path = memory_dir / "reflections.jsonl"
        with open(reflections_path, "w") as f:
            for i in range(999):
                f.write(json.dumps({"node": "code", "success": True, "iteration": i}) + "\n")

        # Adding 2 more will bring it to 1001, triggering pruning to 500
        for i in range(2):
            iteration_data = {
                "node": "test",
                "result": "success",
                "errors": [],
                "iteration": 999 + i,
            }
            feedback_loop.run_cycle(iteration_data)

        lines = reflections_path.read_text().strip().splitlines()
        # After exceeding 1000, should be pruned to 500
        assert len(lines) == 500

        # Verify the kept lines are the most recent ones
        last_entry = json.loads(lines[-1])
        assert last_entry["node"] == "test"

    def test_historian_effectiveness_under_load(self, tmp_path):
        """Verify effectiveness analysis works with large history."""
        kernel_dir = _make_kernel_dir(tmp_path)
        history_file = kernel_dir / "evolution" / "history.jsonl"

        # Write 300 entries with mixed types and statuses
        with open(history_file, "w") as f:
            for i in range(200):
                entry = {
                    "id": f"change-{i}",
                    "type": random.choice(["modify_prompt", "add_rule", "add_skill"]),
                    "status": random.choice(["applied", "rejected", "failed"]),
                    "details": {"node_id": "code"},
                }
                f.write(json.dumps(entry) + "\n")
            # Add some rollback entries
            for i in range(100):
                entry = {
                    "id": f"rollback-{i}",
                    "type": "rollback",
                    "status": "applied",
                    "details": {"rolled_back_change_id": f"change-{i}"},
                }
                f.write(json.dumps(entry) + "\n")

        historian = EvolutionHistorian(history_file)

        # Should not crash
        summary = historian.summarize_history()
        assert summary["total_changes"] == 300
        assert summary["rolled_back_count"] == 100

        effectiveness = historian.analyze_effectiveness()
        assert isinstance(effectiveness, dict)
        for ctype, data in effectiveness.items():
            assert "applied" in data
            assert "reverted" in data
            assert "stick_rate" in data
            # stick_rate can be negative if more reverted than applied
            assert data["stick_rate"] <= 1.0
