"""Tests for error recovery: pre-execution tracking, error pruning, retry strategies."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

import runner
from memory.state_manager import StateManager


@pytest.fixture
def runner_env(tmp_path: Path) -> Path:
    """Set up a complete runner environment for error recovery tests."""
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
        "node_visits": {},
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
                "description": "Plan tasks",
                "transitions": [{"to": "code", "condition": "plan_ready"}],
                "max_retries": 5,
            },
            {
                "id": "code",
                "prompt_file": "prompts/coder.md",
                "description": "Write code",
                "transitions": [],
                "max_retries": 5,
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
    (kernel_dir / "prompts" / "coder.md").write_text("Coder prompt")
    (kernel_dir / "BOOT.md").write_text("# Boot\nBoot content.")
    (kernel_dir / "philosophy").mkdir()
    (kernel_dir / "philosophy" / "dao.md").write_text("# Dao\nDao content.")
    (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy\nStrategy content.")

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "decisions.jsonl").touch()
    (memory_dir / "reflections.jsonl").touch()
    (memory_dir / "current_goal.md").touch()
    with open(memory_dir / "progress.yaml", "w") as f:
        yaml.safe_dump({"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}, f)

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    for sub in ["rules", "skills", "patterns"]:
        (knowledge_dir / sub).mkdir()
        with open(knowledge_dir / sub / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

    return tmp_path


class TestTrackVisitBeforeExecution:
    """Tests that node visits are tracked BEFORE execution so failures count."""

    def test_track_visit_before_execution(self, runner_env: Path, monkeypatch) -> None:
        """Verify node visits increment even when subprocess fails."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "Error occurred")
        mock_proc.returncode = 1
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main([
                "--goal", "test tracking",
                "--ai-command", "echo hi",
                "--max-iterations", "3",
                "--complexity", "high",
            ])

        # Node "init" should have been visited 3 times despite all failures
        assert state["node_visits"].get("init", 0) == 3

    def test_stuck_detection_on_failures(self, runner_env: Path, monkeypatch) -> None:
        """Mock subprocess to always fail, verify stuck triggers."""
        # Set max_retries to 2 for init node
        graph_file = runner_env / "kernel" / "graph.yaml"
        graph_data = yaml.safe_load(graph_file.read_text())
        for node in graph_data["nodes"]:
            if node["id"] == "init":
                node["max_retries"] = 2
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "Always failing")
        mock_proc.returncode = 1
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main([
                "--goal", "test stuck on failure",
                "--ai-command", "echo hi",
                "--max-iterations", "10",
            ])

        # Should become stuck because init exceeded max_retries=2
        assert state["status"] == "stuck"
        assert any("exceeded max_retries" in e for e in state.get("errors", []))


class TestTrimErrors:
    """Tests for trim_errors() and clear_errors() methods."""

    def test_trim_errors_keeps_last_n(self, tmp_path: Path) -> None:
        """Add 15 errors, trim to 10, verify 10 remain and 5 archived."""
        state_file = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "status": "idle",
            "last_updated": "",
            "errors": [f"error_{i}" for i in range(15)],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
            "node_visits": {},
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        mgr = StateManager(str(state_file), str(memory_dir))
        mgr.trim_errors(max_kept=10)

        assert len(mgr.state["errors"]) == 10
        # Should keep the last 10 (error_5 through error_14)
        assert mgr.state["errors"][0] == "error_5"
        assert mgr.state["errors"][-1] == "error_14"

    def test_trim_errors_archives_to_history(self, tmp_path: Path) -> None:
        """Verify error_history.jsonl gets the old errors."""
        state_file = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "status": "idle",
            "last_updated": "",
            "errors": [f"error_{i}" for i in range(15)],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
            "node_visits": {},
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        mgr = StateManager(str(state_file), str(memory_dir))
        mgr.trim_errors(max_kept=10)

        history_path = memory_dir / "error_history.jsonl"
        assert history_path.exists()

        lines = history_path.read_text().strip().split("\n")
        assert len(lines) == 5
        # First archived error should be error_0
        first_entry = json.loads(lines[0])
        assert first_entry["error"] == "error_0"
        assert "timestamp" in first_entry

    def test_trim_errors_no_op_when_under_limit(self, tmp_path: Path) -> None:
        """Verify trim_errors does nothing when errors count is at or below max."""
        state_file = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "status": "idle",
            "last_updated": "",
            "errors": ["error_0", "error_1", "error_2"],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
            "node_visits": {},
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        mgr = StateManager(str(state_file), str(memory_dir))
        mgr.trim_errors(max_kept=10)

        assert len(mgr.state["errors"]) == 3
        history_path = memory_dir / "error_history.jsonl"
        assert not history_path.exists()

    def test_clear_errors_removes_all(self, tmp_path: Path) -> None:
        """Verify all errors moved to history."""
        state_file = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "status": "idle",
            "last_updated": "",
            "errors": ["err_a", "err_b", "err_c"],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
            "node_visits": {},
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        mgr = StateManager(str(state_file), str(memory_dir))
        mgr.clear_errors()

        assert mgr.state["errors"] == []
        history_path = memory_dir / "error_history.jsonl"
        assert history_path.exists()
        lines = history_path.read_text().strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            entry = json.loads(line)
            assert "error" in entry
            assert "timestamp" in entry


class TestRetryStrategies:
    """Tests for --retry-strategy flag behavior."""

    def test_retry_strategy_continue(self, runner_env: Path, monkeypatch) -> None:
        """Default behavior: stays on same node after failure."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "Error")
        mock_proc.returncode = 1
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main([
                "--goal", "test continue",
                "--ai-command", "echo hi",
                "--max-iterations", "2",
                "--retry-strategy", "continue",
                "--complexity", "high",
            ])

        # Should stay on init
        assert state["current_node"] == "init"

    def test_retry_strategy_skip(self, runner_env: Path, monkeypatch) -> None:
        """Skip strategy forces advancement on failure."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "Error")
        mock_proc.returncode = 1
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main([
                "--goal", "test skip",
                "--ai-command", "echo hi",
                "--max-iterations", "1",
                "--retry-strategy", "skip",
                "--complexity", "high",
            ])

        # Should advance to "plan" (first available transition from init)
        assert state["current_node"] == "plan"

    def test_retry_strategy_backoff(self, runner_env: Path, monkeypatch) -> None:
        """Backoff strategy applies exponential delay."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "Error")
        mock_proc.returncode = 1
        mock_proc.kill.return_value = None

        sleep_calls = []

        def mock_sleep(seconds):
            sleep_calls.append(seconds)

        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("time.sleep", side_effect=mock_sleep):
                runner.main([
                    "--goal", "test backoff",
                    "--ai-command", "echo hi",
                    "--max-iterations", "3",
                    "--retry-strategy", "backoff",
                ])

        # Should have called time.sleep with exponential backoff
        # Visit 1: 2^(1-1)=1, Visit 2: 2^(2-1)=2, Visit 3: 2^(3-1)=4
        assert len(sleep_calls) == 3
        assert sleep_calls[0] == 1
        assert sleep_calls[1] == 2
        assert sleep_calls[2] == 4

    def test_retry_strategy_backoff_capped_at_60(self, runner_env: Path, monkeypatch) -> None:
        """Backoff delay is capped at 60 seconds."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        # Set max_retries high so we don't get stuck early
        graph_file = runner_env / "kernel" / "graph.yaml"
        graph_data = yaml.safe_load(graph_file.read_text())
        for node in graph_data["nodes"]:
            if node["id"] == "init":
                node["max_retries"] = 100
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "Error")
        mock_proc.returncode = 1
        mock_proc.kill.return_value = None

        sleep_calls = []

        def mock_sleep(seconds):
            sleep_calls.append(seconds)

        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("time.sleep", side_effect=mock_sleep):
                runner.main([
                    "--goal", "test backoff cap",
                    "--ai-command", "echo hi",
                    "--max-iterations", "8",
                    "--retry-strategy", "backoff",
                    "--complexity", "high",
                ])

        # Visit 7: 2^(7-1)=64 -> capped to 60
        assert all(s <= 60 for s in sleep_calls)
        # At visit 7, 2^6=64 should be capped to 60
        assert 60 in sleep_calls

    def test_retry_strategy_parse_args(self) -> None:
        """Test that --retry-strategy is properly parsed."""
        args = runner.parse_args(["--goal", "test", "--retry-strategy", "skip"])
        assert args.retry_strategy == "skip"

        args = runner.parse_args(["--goal", "test", "--retry-strategy", "backoff"])
        assert args.retry_strategy == "backoff"

        args = runner.parse_args(["--goal", "test"])
        assert args.retry_strategy == "continue"

    def test_retry_strategy_invalid_choice(self) -> None:
        """Test that invalid retry strategy raises error."""
        with pytest.raises(SystemExit):
            runner.parse_args(["--goal", "test", "--retry-strategy", "invalid"])


class TestErrorsTrimmedEachIteration:
    """Tests that trim_errors is called during the execution loop."""

    def test_errors_trimmed_each_iteration(self, runner_env: Path, monkeypatch) -> None:
        """Verify trim_errors is called in the loop by checking errors stay bounded."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        # Set max_retries high to avoid stuck
        graph_file = runner_env / "kernel" / "graph.yaml"
        graph_data = yaml.safe_load(graph_file.read_text())
        for node in graph_data["nodes"]:
            node["max_retries"] = 50
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error"

        with patch("subprocess.run", return_value=mock_result):
            state = runner.main([
                "--goal", "test trim in loop",
                "--ai-command", "echo hi",
                "--max-iterations", "15",
            ])

        # With 15 failures adding errors, trim_errors(20) should keep at most 20
        assert len(state.get("errors", [])) <= 20

    def test_errors_trimmed_on_success_path(self, runner_env: Path, monkeypatch) -> None:
        """Verify trim_errors is called after successful transitions too."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        # Pre-load state with many errors
        state_file = runner_env / "kernel" / "state.yaml"
        state_data = yaml.safe_load(state_file.read_text())
        state_data["errors"] = [f"pre_error_{i}" for i in range(15)]
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "STATUS: success\nTRANSITION: goal_loaded"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            state = runner.main([
                "--goal", "test trim on success",
                "--ai-command", "echo hi",
                "--max-iterations", "1",
            ])

        # After trimming, should have at most 20 errors
        assert len(state.get("errors", [])) <= 20
