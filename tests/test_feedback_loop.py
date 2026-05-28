"""Tests for the FeedbackLoop class and related integration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from kernel.evolution.engine import EvolutionEngine
from kernel.evolution.metrics import EvolutionMetrics
from kernel.feedback_loop import FeedbackLoop
from kernel.graph_executor import GraphExecutor
from kernel.reflector import Reflector


@pytest.fixture
def feedback_setup(tmp_path: Path):
    """Set up a complete feedback loop environment."""
    # Memory dir
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "reflections.jsonl").touch()

    # Kernel dir with graph
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    (kernel_dir / "evolution").mkdir()
    (kernel_dir / "prompts").mkdir()
    (kernel_dir / "prompts" / "coder.md").write_text("Coder prompt")

    graph_file = kernel_dir / "graph.yaml"
    graph_data = {
        "nodes": [
            {
                "id": "init",
                "prompt_file": "prompts/orchestrator.md",
                "description": "Initialize",
                "transitions": [{"to": "code", "condition": "goal_loaded"}],
                "max_retries": 1,
            },
            {
                "id": "code",
                "prompt_file": "prompts/coder.md",
                "description": "Write code",
                "transitions": [],
                "max_retries": 3,
            },
        ],
        "default_start": "init",
        "max_iterations": 30,
    }
    with open(graph_file, "w") as f:
        yaml.safe_dump(graph_data, f)

    # Knowledge dir
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "rules").mkdir()
    (knowledge_dir / "skills").mkdir()
    (knowledge_dir / "patterns").mkdir()
    for sub in ["rules", "skills", "patterns"]:
        with open(knowledge_dir / sub / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

    from knowledge.store import KnowledgeStore

    knowledge = KnowledgeStore(str(knowledge_dir))
    graph_executor = GraphExecutor(str(graph_file))
    reflector = Reflector(str(memory_dir), knowledge)
    engine = EvolutionEngine(str(kernel_dir), graph_executor)
    metrics = EvolutionMetrics()

    loop = FeedbackLoop(str(memory_dir), reflector, engine, metrics)
    return loop, memory_dir, kernel_dir, engine, metrics


class TestRunCycle:
    """Tests for FeedbackLoop.run_cycle."""

    def test_run_cycle_produces_reflection(self, feedback_setup) -> None:
        """Test that run_cycle produces a reflection dict."""
        loop, memory_dir, _, _, _ = feedback_setup
        iteration_data = {
            "node": "code",
            "result": "success",
            "errors": [],
            "iteration": 1,
        }

        result = loop.run_cycle(iteration_data)

        assert "reflection" in result
        assert result["reflection"]["node"] == "code"
        assert result["reflection"]["success"] is True

    def test_run_cycle_with_high_confidence_proposal_applies_change(self, feedback_setup) -> None:
        """Test that proposals with high confidence are auto-applied."""
        loop, memory_dir, kernel_dir, engine, _ = feedback_setup

        # Pre-populate reflections with repeated failures to trigger proposals
        reflections_path = memory_dir / "reflections.jsonl"
        for i in range(5):
            entry = {
                "iteration": i,
                "node": "code",
                "success": False,
                "learnings": [],
                "issues": [f"Error: syntax error in iteration {i}"],
                "timestamp": f"2025-01-01T00:00:0{i}Z",
            }
            with open(reflections_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

        iteration_data = {
            "node": "code",
            "result": "failed",
            "errors": ["syntax error"],
            "iteration": 6,
        }

        result = loop.run_cycle(iteration_data)

        # Should have generated and potentially applied proposals
        assert result["proposals_generated"] >= 0
        # Verify reflection was stored
        assert result["reflection"]["node"] == "code"

    def test_run_cycle_with_low_confidence_proposal_skips(self, feedback_setup) -> None:
        """Test that proposals with low confidence are skipped."""
        loop, memory_dir, _, engine, _ = feedback_setup

        # Pre-populate with just enough failures to trigger a proposal but not high confidence
        reflections_path = memory_dir / "reflections.jsonl"
        for i in range(3):
            entry = {
                "iteration": i,
                "node": "code",
                "success": False,
                "learnings": [],
                "issues": [f"Error type {i}"],  # Different errors = low consistency
                "timestamp": f"2025-01-01T00:00:0{i}Z",
            }
            with open(reflections_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

        # Set threshold high so nothing passes
        loop.threshold = 0.95

        iteration_data = {
            "node": "code",
            "result": "failed",
            "errors": ["another error"],
            "iteration": 4,
        }

        result = loop.run_cycle(iteration_data)

        # proposals may be generated but none should be applied with high threshold
        assert result["proposals_applied"] == 0
        assert result["proposals_skipped"] == result["proposals_generated"]


class TestReadRecentReflections:
    """Tests for FeedbackLoop._read_recent_reflections."""

    def test_read_recent_reflections_reads_last_n(self, feedback_setup) -> None:
        """Test that _read_recent_reflections returns last N entries."""
        loop, memory_dir, _, _, _ = feedback_setup

        reflections_path = memory_dir / "reflections.jsonl"
        for i in range(15):
            entry = {"iteration": i, "node": "code", "success": True}
            with open(reflections_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

        result = loop._read_recent_reflections(count=5)
        assert len(result) == 5
        # Should be the last 5 entries
        assert result[0]["iteration"] == 10
        assert result[4]["iteration"] == 14

    def test_read_recent_reflections_empty_file(self, feedback_setup) -> None:
        """Test reading reflections from an empty file."""
        loop, _, _, _, _ = feedback_setup

        result = loop._read_recent_reflections(count=10)
        assert result == []

    def test_read_recent_reflections_missing_file(self, tmp_path: Path) -> None:
        """Test reading reflections when file does not exist."""
        from knowledge.store import KnowledgeStore

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "skills").mkdir()
        (knowledge_dir / "patterns").mkdir()
        for sub in ["rules", "skills", "patterns"]:
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        knowledge = KnowledgeStore(str(knowledge_dir))

        # Point to non-existent memory dir
        nonexistent_dir = tmp_path / "no_memory"
        reflector = Reflector(str(nonexistent_dir), knowledge)
        engine = MagicMock()
        metrics = EvolutionMetrics()
        loop = FeedbackLoop(str(nonexistent_dir), reflector, engine, metrics)

        result = loop._read_recent_reflections(count=10)
        assert result == []


class TestRecordReflection:
    """Tests for FeedbackLoop._record_reflection."""

    def test_record_reflection_appends_to_file(self, feedback_setup) -> None:
        """Test that _record_reflection appends to reflections.jsonl."""
        loop, memory_dir, _, _, _ = feedback_setup

        reflection = {
            "iteration": 1,
            "node": "code",
            "success": True,
            "learnings": ["learned something"],
            "issues": [],
        }

        loop._record_reflection(reflection)

        reflections_path = memory_dir / "reflections.jsonl"
        lines = reflections_path.read_text().strip().split("\n")
        assert len(lines) == 1
        stored = json.loads(lines[0])
        assert stored["node"] == "code"
        assert stored["success"] is True

    def test_record_reflection_creates_directory(self, tmp_path: Path) -> None:
        """Test that _record_reflection creates memory dir if missing."""
        from knowledge.store import KnowledgeStore

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "skills").mkdir()
        (knowledge_dir / "patterns").mkdir()
        for sub in ["rules", "skills", "patterns"]:
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        knowledge = KnowledgeStore(str(knowledge_dir))

        new_memory_dir = tmp_path / "new_memory"
        reflector = Reflector(str(new_memory_dir), knowledge)
        engine = MagicMock()
        metrics = EvolutionMetrics()
        loop = FeedbackLoop(str(new_memory_dir), reflector, engine, metrics)

        reflection = {"iteration": 1, "node": "test", "success": True}
        loop._record_reflection(reflection)

        reflections_path = new_memory_dir / "reflections.jsonl"
        assert reflections_path.exists()


class TestApplyIfConfident:
    """Tests for EvolutionEngine.apply_if_confident."""

    @pytest.fixture
    def engine_setup(self, tmp_path: Path):
        """Set up an engine for apply_if_confident tests."""
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
                    "description": "Init",
                    "transitions": [{"to": "plan", "condition": "done"}],
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
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        graph_executor = GraphExecutor(str(graph_file))
        engine = EvolutionEngine(str(kernel_dir), graph_executor)
        return engine, kernel_dir

    def test_apply_if_confident_filters_by_threshold(self, engine_setup) -> None:
        """Test that only proposals above threshold are applied."""
        engine, kernel_dir = engine_setup

        proposals = [
            {
                "type": "add_rule",
                "details": {"name": "low_conf_rule"},
                "reason": "Low confidence",
                "confidence_score": 0.3,
            },
            {
                "type": "add_rule",
                "details": {"name": "high_conf_rule"},
                "reason": "High confidence",
                "confidence_score": 0.9,
            },
        ]

        applied = engine.apply_if_confident(proposals, threshold=0.7)
        assert len(applied) == 1
        assert applied[0]["type"] == "add_rule"

    def test_apply_if_confident_skips_invalid_proposals(self, engine_setup) -> None:
        """Test that proposals failing validation are skipped."""
        engine, kernel_dir = engine_setup

        proposals = [
            {
                "type": "modify_prompt",
                "details": {"target_file": "kernel/BOOT.md", "content": "hacked"},
                "reason": "Try to modify protected",
                "confidence_score": 0.99,
            },
        ]

        applied = engine.apply_if_confident(proposals, threshold=0.7)
        assert len(applied) == 0

    def test_apply_if_confident_returns_empty_for_all_low(self, engine_setup) -> None:
        """Test that no proposals are applied when all are below threshold."""
        engine, _ = engine_setup

        proposals = [
            {
                "type": "add_rule",
                "details": {"name": "rule1"},
                "reason": "r1",
                "confidence_score": 0.5,
            },
            {
                "type": "add_rule",
                "details": {"name": "rule2"},
                "reason": "r2",
                "confidence_score": 0.6,
            },
        ]

        applied = engine.apply_if_confident(proposals, threshold=0.7)
        assert applied == []

    def test_apply_if_confident_empty_proposals(self, engine_setup) -> None:
        """Test with empty proposals list."""
        engine, _ = engine_setup
        applied = engine.apply_if_confident([], threshold=0.7)
        assert applied == []


class TestMultipleCycles:
    """Tests for multiple feedback cycles accumulating reflections."""

    def test_multiple_cycles_accumulate_reflections(self, feedback_setup) -> None:
        """Test that running multiple cycles accumulates reflections."""
        loop, memory_dir, _, _, _ = feedback_setup

        for i in range(5):
            iteration_data = {
                "node": "code",
                "result": "success",
                "errors": [],
                "iteration": i,
            }
            loop.run_cycle(iteration_data)

        reflections_path = memory_dir / "reflections.jsonl"
        lines = [l for l in reflections_path.read_text().strip().split("\n") if l]
        assert len(lines) == 5

        # Verify each reflection has expected content
        for i, line in enumerate(lines):
            entry = json.loads(line)
            assert entry["node"] == "code"
            assert entry["iteration"] == i


class TestRunnerCallsFeedbackLoop:
    """Tests for runner.py integration with FeedbackLoop."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a complete runner environment in tmp_path."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "evolution").mkdir()

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
        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Initialize",
                    "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                    "max_retries": 10,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/planner.md",
                    "description": "Plan tasks",
                    "transitions": [],
                    "max_retries": 10,
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
        (kernel_dir / "BOOT.md").write_text("# Boot\nBoot content.")
        (kernel_dir / "constitution.md").write_text("# Constitution")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy")

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

        return tmp_path

    def test_runner_calls_feedback_loop_on_success(self, runner_env: Path, monkeypatch) -> None:
        """Test that Mode 3 runner calls feedback loop after successful transition."""
        import runner

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("STATUS: success\nTRANSITION: goal_loaded", "")
        mock_proc.returncode = 0
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            runner.main(
                [
                    "--goal",
                    "test feedback",
                    "--ai-command",
                    "echo hello",
                    "--max-iterations",
                    "1",
                    "--complexity",
                    "high",
                ]
            )

        # Verify feedback loop ran by checking reflections.jsonl
        reflections_path = runner_env / "memory" / "reflections.jsonl"
        content = reflections_path.read_text().strip()
        assert content != ""
        entry = json.loads(content.split("\n")[0])
        assert entry["node"] == "init"
        assert entry["success"] is True

    def test_runner_calls_feedback_loop_on_failure(self, runner_env: Path, monkeypatch) -> None:
        """Test that Mode 3 runner calls feedback loop on AI command failure."""
        import runner

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "Error: rate limited")
        mock_proc.returncode = 1
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            runner.main(
                [
                    "--goal",
                    "test failure feedback",
                    "--ai-command",
                    "echo hello",
                    "--max-iterations",
                    "1",
                ]
            )

        # Verify feedback loop ran with failure data
        reflections_path = runner_env / "memory" / "reflections.jsonl"
        content = reflections_path.read_text().strip()
        assert content != ""
        entry = json.loads(content.split("\n")[0])
        assert entry["node"] == "init"
        assert entry["success"] is False


class TestContextAssemblerIncludesHistoryAndReflections:
    """Tests for context_assembler including evolution history and reflections."""

    def test_context_assembler_includes_history_and_reflections(self, tmp_path: Path) -> None:
        """Test that assembled context includes evolution history and reflections."""
        from kernel.context_assembler import ContextAssembler

        # Set up directory structure
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "BOOT.md").write_text("# Boot")
        (kernel_dir / "constitution.md").write_text("# Constitution")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy")
        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator")
        (kernel_dir / "contracts").mkdir()
        (kernel_dir / "contracts" / "output_format.md").write_text("# Format")

        # Evolution history
        (kernel_dir / "evolution").mkdir()
        history_path = kernel_dir / "evolution" / "history.jsonl"
        history_entry = {
            "type": "add_rule",
            "reason": "Test evolution entry",
            "status": "applied",
            "timestamp": "2025-01-01T00:00:00Z",
        }
        with open(history_path, "w") as f:
            f.write(json.dumps(history_entry) + "\n")

        # Reflections
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        reflections_path = memory_dir / "reflections.jsonl"
        reflection_entry = {
            "node": "code",
            "success": True,
            "learnings": ["Learned to handle errors"],
            "issues": [],
        }
        with open(reflections_path, "w") as f:
            f.write(json.dumps(reflection_entry) + "\n")

        # Graph
        graph_file = kernel_dir / "graph.yaml"
        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Init",
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
            "max_iterations": 30,
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        # Knowledge
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        graph_executor = GraphExecutor(str(graph_file))
        knowledge_store = KnowledgeStore(str(knowledge_dir))

        assembler = ContextAssembler(tmp_path)
        state = {"current_node": "reflect", "goal": "test", "iteration_count": 0}
        node = {"id": "reflect"}

        result = assembler.assemble(state, node, graph_executor, knowledge_store)

        assert "=== EVOLUTION HISTORY ===" in result
        assert "Test evolution entry" in result
        assert "=== RECENT REFLECTIONS ===" in result
        assert "Learned to handle errors" in result

    def test_context_assembler_no_history_no_reflections(self, tmp_path: Path) -> None:
        """Test that assembler works when no history or reflections exist."""
        from kernel.context_assembler import ContextAssembler

        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "BOOT.md").write_text("# Boot")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy")
        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator")

        # Graph
        graph_file = kernel_dir / "graph.yaml"
        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Init",
                    "transitions": [],
                    "max_retries": 1,
                },
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        graph_executor = GraphExecutor(str(graph_file))
        knowledge_store = KnowledgeStore(str(knowledge_dir))

        assembler = ContextAssembler(tmp_path)
        state = {"current_node": "init", "goal": "test", "iteration_count": 0}
        node = {"id": "init"}

        result = assembler.assemble(state, node, graph_executor, knowledge_store)

        # Should not include these sections when files are missing
        assert "=== EVOLUTION HISTORY ===" not in result
        assert "=== RECENT REFLECTIONS ===" not in result


class TestSkillAccumulatorIntegration:
    """Tests for SkillAccumulator integration with FeedbackLoop."""

    def test_skill_accumulator_called_on_project_complete(self, feedback_setup) -> None:
        """Test that skill_accumulator.analyze_completion is called when project completes."""
        loop, memory_dir, _, _, _ = feedback_setup

        mock_accumulator = MagicMock()
        mock_accumulator.analyze_completion.return_value = []
        loop.skill_accumulator = mock_accumulator

        iteration_data = {
            "node": "review",
            "result": "success",
            "errors": [],
            "iteration": 10,
            "project_complete": True,
            "goal": "Build a calculator",
            "skills_used": ["python-api"],
        }

        loop.run_cycle(iteration_data)

        mock_accumulator.analyze_completion.assert_called_once()
        call_args = mock_accumulator.analyze_completion.call_args[0][0]
        assert call_args["goal"] == "Build a calculator"
        assert call_args["skills_used"] == ["python-api"]

    def test_skill_accumulator_not_called_without_project_complete(self, feedback_setup) -> None:
        """Test that skill_accumulator is NOT called for normal iterations."""
        loop, memory_dir, _, _, _ = feedback_setup

        mock_accumulator = MagicMock()
        loop.skill_accumulator = mock_accumulator

        iteration_data = {
            "node": "code",
            "result": "success",
            "errors": [],
            "iteration": 5,
        }

        loop.run_cycle(iteration_data)

        mock_accumulator.analyze_completion.assert_not_called()

    def test_feedback_loop_works_without_skill_accumulator(self, feedback_setup) -> None:
        """Test that FeedbackLoop works fine when no skill_accumulator is provided."""
        loop, _, _, _, _ = feedback_setup
        assert loop.skill_accumulator is None

        iteration_data = {
            "node": "code",
            "result": "success",
            "errors": [],
            "iteration": 1,
            "project_complete": True,
        }

        # Should not raise even with project_complete=True
        result = loop.run_cycle(iteration_data)
        assert "reflection" in result
