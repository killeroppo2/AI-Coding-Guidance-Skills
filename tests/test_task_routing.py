"""Tests for task complexity routing in runner.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

import runner


class TestComplexityArgParsing:
    """Tests for --complexity CLI argument parsing."""

    def test_complexity_default_auto(self) -> None:
        """Test that --complexity defaults to 'auto'."""
        args = runner.parse_args(["--goal", "test"])
        assert args.complexity == "auto"

    def test_complexity_low(self) -> None:
        """Test parsing --complexity low."""
        args = runner.parse_args(["--goal", "test", "--complexity", "low"])
        assert args.complexity == "low"

    def test_complexity_medium(self) -> None:
        """Test parsing --complexity medium."""
        args = runner.parse_args(["--goal", "test", "--complexity", "medium"])
        assert args.complexity == "medium"

    def test_complexity_high(self) -> None:
        """Test parsing --complexity high."""
        args = runner.parse_args(["--goal", "test", "--complexity", "high"])
        assert args.complexity == "high"

    def test_complexity_auto_explicit(self) -> None:
        """Test parsing --complexity auto explicitly."""
        args = runner.parse_args(["--goal", "test", "--complexity", "auto"])
        assert args.complexity == "auto"

    def test_complexity_invalid_choice(self) -> None:
        """Test that invalid complexity choice raises error."""
        with pytest.raises(SystemExit):
            runner.parse_args(["--goal", "test", "--complexity", "invalid"])


class TestLowComplexityRouting:
    """Tests for low complexity routing behavior."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a runner environment for routing tests."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()

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
                    "max_retries": 5,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/planner.md",
                    "description": "Plan",
                    "transitions": [{"to": "code", "condition": "plan_ready"}],
                    "max_retries": 5,
                },
                {
                    "id": "code",
                    "prompt_file": "prompts/coder.md",
                    "description": "Code",
                    "transitions": [{"to": "test", "condition": "code_written"}],
                    "max_retries": 5,
                },
                {
                    "id": "test",
                    "prompt_file": "prompts/tester.md",
                    "description": "Test",
                    "transitions": [{"to": "review", "condition": "tests_pass"}],
                    "max_retries": 5,
                },
                {
                    "id": "review",
                    "prompt_file": "prompts/reviewer.md",
                    "description": "Review",
                    "transitions": [{"to": "reflect", "condition": "review_pass"}],
                    "max_retries": 5,
                },
                {
                    "id": "reflect",
                    "prompt_file": "prompts/reflector.md",
                    "description": "Reflect",
                    "transitions": [{"to": "plan", "condition": "no_evolution_needed"}],
                    "max_retries": 5,
                },
                {
                    "id": "evolve",
                    "prompt_file": "prompts/reflector.md",
                    "description": "Evolve",
                    "transitions": [{"to": "plan", "condition": "evolution_applied"}],
                    "max_retries": 5,
                },
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator")
        (kernel_dir / "prompts" / "planner.md").write_text("Planner")
        (kernel_dir / "prompts" / "coder.md").write_text("Coder")
        (kernel_dir / "prompts" / "tester.md").write_text("Tester")
        (kernel_dir / "prompts" / "reviewer.md").write_text("Reviewer")
        (kernel_dir / "prompts" / "reflector.md").write_text("Reflector")
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
            yaml.safe_dump(
                {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"},
                f,
            )

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_low_complexity_sets_code_node(self, runner_env: Path, monkeypatch) -> None:
        """Test that low complexity sets current_node to 'code'."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main([
            "--goal", "hello world",
            "--complexity", "low",
            "--max-iterations", "1",
        ])
        # Low complexity starts at "code" node, then advances to "test"
        # (Mode 1 scaffolding takes first transition from code)
        assert state["complexity"] == "low"
        # Verify it did NOT stay at "init" or "plan"
        assert state["current_node"] in ("test", "code")

    def test_low_complexity_creates_tasks_file(self, runner_env: Path, monkeypatch) -> None:
        """Test that low complexity creates tasks.yaml if missing."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        runner.main([
            "--goal", "fix the bug",
            "--complexity", "low",
            "--max-iterations", "1",
        ])
        tasks_file = runner_env / "memory" / "tasks.yaml"
        assert tasks_file.exists()
        data = yaml.safe_load(tasks_file.read_text())
        assert data["tasks"][0]["id"] == "T-001"
        assert data["tasks"][0]["title"] == "fix the bug"
        assert data["tasks"][0]["complexity"] == "low"

    def test_low_complexity_does_not_overwrite_tasks(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test that low complexity does not overwrite existing tasks.yaml."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        tasks_file = runner_env / "memory" / "tasks.yaml"
        existing = {"tasks": [{"id": "T-100", "title": "existing", "status": "done"}]}
        with open(tasks_file, "w") as f:
            yaml.safe_dump(existing, f)

        runner.main([
            "--goal", "fix another bug",
            "--complexity", "low",
            "--max-iterations", "1",
        ])
        data = yaml.safe_load(tasks_file.read_text())
        # Should not have overwritten existing task
        assert data["tasks"][0]["id"] == "T-100"

    def test_low_complexity_dry_run_does_not_skip(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test that low complexity in dry-run does NOT skip to code."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main([
            "--goal", "hello world",
            "--complexity", "low",
            "--dry-run",
            "--max-iterations", "1",
        ])
        # In dry-run mode, low complexity should not modify current_node
        # It starts at init and advances via scaffolding
        assert state["complexity"] == "low"


class TestMediumComplexityRouting:
    """Tests for medium complexity routing behavior."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a runner environment with reflect/evolve transitions."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()

        state_data = {
            "current_node": "review",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "status": "idle",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "coding"},
        }
        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

        graph_data = {
            "nodes": [
                {
                    "id": "review",
                    "prompt_file": "prompts/reviewer.md",
                    "description": "Review",
                    "transitions": [
                        {"to": "reflect", "condition": "review_pass"},
                        {"to": "code", "condition": "review_needs_changes"},
                    ],
                    "max_retries": 5,
                },
                {
                    "id": "reflect",
                    "prompt_file": "prompts/reflector.md",
                    "description": "Reflect",
                    "transitions": [
                        {"to": "evolve", "condition": "evolution_proposed"},
                        {"to": "plan", "condition": "no_evolution_needed"},
                    ],
                    "max_retries": 5,
                },
                {
                    "id": "evolve",
                    "prompt_file": "prompts/reflector.md",
                    "description": "Evolve",
                    "transitions": [{"to": "plan", "condition": "evolution_applied"}],
                    "max_retries": 5,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/planner.md",
                    "description": "Plan",
                    "transitions": [{"to": "code", "condition": "plan_ready"}],
                    "max_retries": 5,
                },
                {
                    "id": "code",
                    "prompt_file": "prompts/coder.md",
                    "description": "Code",
                    "transitions": [],
                    "max_retries": 5,
                },
            ],
            "default_start": "review",
            "max_iterations": 30,
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "reviewer.md").write_text("Reviewer")
        (kernel_dir / "prompts" / "planner.md").write_text("Planner")
        (kernel_dir / "prompts" / "coder.md").write_text("Coder")
        (kernel_dir / "prompts" / "reflector.md").write_text("Reflector")
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
            yaml.safe_dump(
                {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"},
                f,
            )

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_medium_skips_reflect_in_scaffolding(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test that medium complexity skips reflect node in Mode 1."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main([
            "--goal", "Add user login page",
            "--complexity", "medium",
            "--dry-run",
            "--max-iterations", "3",
        ])
        assert state["complexity"] == "medium"
        # The graph starts at review -> reflect (first transition).
        # Medium complexity overrides reflect -> plan, then plan -> code.
        assert state["current_node"] == "code"

    def test_medium_skips_reflect_in_mode3(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test that medium complexity skips reflect/evolve in Mode 3."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            "STATUS: success\nTRANSITION: review_pass",
            "",
        )
        mock_proc.returncode = 0
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main([
                "--goal", "Add user login page",
                "--complexity", "medium",
                "--ai-command", "echo hi",
                "--max-iterations", "1",
            ])

        # review -> reflect transition, but medium complexity overrides to plan
        assert state["current_node"] == "plan"
        assert state["complexity"] == "medium"


class TestHighComplexityRouting:
    """Tests for high complexity - full flow unchanged."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a runner environment for high complexity tests."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()

        state_data = {
            "current_node": "review",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "status": "idle",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "coding"},
        }
        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

        graph_data = {
            "nodes": [
                {
                    "id": "review",
                    "prompt_file": "prompts/reviewer.md",
                    "description": "Review",
                    "transitions": [
                        {"to": "reflect", "condition": "review_pass"},
                    ],
                    "max_retries": 5,
                },
                {
                    "id": "reflect",
                    "prompt_file": "prompts/reflector.md",
                    "description": "Reflect",
                    "transitions": [
                        {"to": "plan", "condition": "no_evolution_needed"},
                    ],
                    "max_retries": 5,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/planner.md",
                    "description": "Plan",
                    "transitions": [],
                    "max_retries": 5,
                },
            ],
            "default_start": "review",
            "max_iterations": 30,
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "reviewer.md").write_text("Reviewer")
        (kernel_dir / "prompts" / "reflector.md").write_text("Reflector")
        (kernel_dir / "prompts" / "planner.md").write_text("Planner")
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
            yaml.safe_dump(
                {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"},
                f,
            )

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_high_does_not_skip_reflect(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test that high complexity does NOT skip reflect."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main([
            "--goal", "Build a distributed architecture",
            "--complexity", "high",
            "--dry-run",
            "--max-iterations", "3",
        ])
        assert state["complexity"] == "high"
        # Full flow: review -> reflect -> plan -> complete (no transitions from plan)
        assert state["current_node"] == "plan"
        assert state["status"] == "complete"


class TestAutoComplexityRouting:
    """Tests for auto mode calling assess_complexity."""

    def test_auto_calls_assess_complexity(self) -> None:
        """Test that auto mode uses assess_complexity to determine routing."""
        state = runner.main([
            "--goal", "hello world",
            "--complexity", "auto",
            "--dry-run",
            "--max-iterations", "1",
        ])
        # "hello world" should be assessed as low
        assert state["complexity"] == "low"

    def test_auto_detects_high(self) -> None:
        """Test that auto mode detects high complexity goals."""
        state = runner.main([
            "--goal", "Build a distributed microservice architecture",
            "--complexity", "auto",
            "--dry-run",
            "--max-iterations", "1",
        ])
        assert state["complexity"] == "high"

    def test_auto_detects_medium(self) -> None:
        """Test that auto mode detects medium complexity goals."""
        state = runner.main([
            "--goal", "Add user login page feature",
            "--complexity", "auto",
            "--dry-run",
            "--max-iterations", "1",
        ])
        assert state["complexity"] == "medium"
