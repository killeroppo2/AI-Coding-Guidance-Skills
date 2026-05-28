"""Tests for kernel/reporter.py - human-readable progress reporting."""

from pathlib import Path

import pytest
import yaml

import runner
from kernel.reporter import Reporter


class TestReportIteration:
    """Tests for Reporter.report_iteration()."""

    def test_report_iteration_success(self) -> None:
        """Test reporting a successful iteration."""
        reporter = Reporter()
        state = {"iteration_count": 3, "max_iterations": 30}
        node = {"id": "code", "description": "Write code"}
        result = reporter.report_iteration(state, node, "success")
        assert result == "[3/30] code: success"

    def test_report_iteration_failed(self) -> None:
        """Test reporting a failed iteration."""
        reporter = Reporter()
        state = {"iteration_count": 7, "max_iterations": 30}
        node = {"id": "test", "description": "Run tests"}
        result = reporter.report_iteration(state, node, "failed")
        assert result == "[7/30] test: failed"

    def test_report_iteration_format(self) -> None:
        """Test that report_iteration produces a single line with key info."""
        reporter = Reporter()
        state = {"iteration_count": 1, "max_iterations": 10}
        node = {"id": "plan", "description": "Plan tasks"}
        result = reporter.report_iteration(state, node, "success")
        # Should be one line
        assert "\n" not in result
        # Should contain iteration info
        assert "1/10" in result
        # Should contain node id
        assert "plan" in result
        # Should contain result
        assert "success" in result

    def test_report_iteration_defaults(self) -> None:
        """Test report_iteration with missing state keys uses defaults."""
        reporter = Reporter()
        state = {}
        node = {"id": "init"}
        result = reporter.report_iteration(state, node, "success")
        assert result == "[0/30] init: success"


class TestReportCompletion:
    """Tests for Reporter.report_completion()."""

    def test_report_completion_all_done(self) -> None:
        """Test completion report when all tasks are done."""
        reporter = Reporter()
        state = {
            "goal": "Build a REST API",
            "status": "complete",
            "iteration_count": 10,
            "max_iterations": 30,
            "errors": [],
        }
        tasks = [
            {"id": "T-001", "status": "done"},
            {"id": "T-002", "status": "done"},
            {"id": "T-003", "status": "done"},
        ]
        result = reporter.report_completion(state, tasks)
        assert "Build a REST API" in result
        assert "complete" in result
        assert "10/30" in result
        assert "3/3 complete" in result
        assert "Errors encountered: 0" in result
        assert "Last error" not in result

    def test_report_completion_with_errors(self) -> None:
        """Test completion report when there are errors."""
        reporter = Reporter()
        state = {
            "goal": "Fix bugs",
            "status": "stuck",
            "iteration_count": 15,
            "max_iterations": 30,
            "errors": ["timeout on code", "contract violation on test"],
        }
        tasks = [
            {"id": "T-001", "status": "done"},
            {"id": "T-002", "status": "in_progress"},
        ]
        result = reporter.report_completion(state, tasks)
        assert "Fix bugs" in result
        assert "stuck" in result
        assert "15/30" in result
        assert "1/2 complete" in result
        assert "Errors encountered: 2" in result
        assert "Last error: contract violation on test" in result

    def test_report_completion_no_tasks(self) -> None:
        """Test completion report with empty task list."""
        reporter = Reporter()
        state = {
            "goal": "Explore",
            "status": "complete",
            "iteration_count": 5,
            "max_iterations": 30,
            "errors": [],
        }
        tasks = []
        result = reporter.report_completion(state, tasks)
        assert "Explore" in result
        assert "0/0 complete" in result

    def test_report_completion_multiline(self) -> None:
        """Test that completion report is multi-line."""
        reporter = Reporter()
        state = {
            "goal": "test",
            "status": "complete",
            "iteration_count": 1,
            "max_iterations": 30,
            "errors": [],
        }
        result = reporter.report_completion(state, [])
        assert "\n" in result
        assert "=== Execution Summary ===" in result


class TestReportStuck:
    """Tests for Reporter.report_stuck()."""

    def test_report_stuck_code_node(self) -> None:
        """Test stuck report for a 'code' node with correct suggestion."""
        reporter = Reporter()
        state = {"current_node": "code", "iteration_count": 10}
        errors = ["timeout", "contract violation", "AI error"]
        result = reporter.report_stuck(state, "code", errors)
        assert "STUCK: Node 'code' is not making progress" in result
        assert "Check if the task is too complex. Try splitting it." in result
        assert "timeout" in result
        assert "contract violation" in result
        assert "AI error" in result

    def test_report_stuck_test_node(self) -> None:
        """Test stuck report for a 'test' node with correct suggestion."""
        reporter = Reporter()
        state = {"current_node": "test", "iteration_count": 5}
        errors = ["tests failed", "assertion error"]
        result = reporter.report_stuck(state, "test", errors)
        assert "STUCK: Node 'test' is not making progress" in result
        assert "Tests keep failing. Review test expectations." in result

    def test_report_stuck_other_node(self) -> None:
        """Test stuck report for an unknown node with generic suggestion."""
        reporter = Reporter()
        state = {"current_node": "plan", "iteration_count": 8}
        errors = ["plan revision needed"]
        result = reporter.report_stuck(state, "plan", errors)
        assert "STUCK: Node 'plan' is not making progress" in result
        assert "Consider using --retry-strategy skip to advance past this node." in result

    def test_report_stuck_no_errors(self) -> None:
        """Test stuck report with no error messages."""
        reporter = Reporter()
        state = {}
        result = reporter.report_stuck(state, "init", [])
        assert "STUCK: Node 'init' is not making progress" in result
        assert "(none recorded)" in result

    def test_report_stuck_trims_to_last_3(self) -> None:
        """Test that stuck report only shows last 3 errors."""
        reporter = Reporter()
        state = {}
        errors = ["err1", "err2", "err3", "err4", "err5"]
        result = reporter.report_stuck(state, "code", errors)
        # Should only include last 3
        assert "err3" in result
        assert "err4" in result
        assert "err5" in result
        assert "err1" not in result
        assert "err2" not in result


class TestFormatStatus:
    """Tests for Reporter.format_status()."""

    def test_format_status_idle(self) -> None:
        """Test status format for idle state."""
        reporter = Reporter()
        state = {
            "goal": "(no goal set)",
            "status": "idle",
            "iteration_count": 0,
            "max_iterations": 30,
            "current_node": "init",
            "execution_mode": "kernel",
            "errors": [],
        }
        result = reporter.format_status(state, [])
        assert "=== Kernel Status ===" in result
        assert "Status: idle" in result
        assert "Progress: iteration 0/30" in result
        assert "Current node: init" in result
        assert "Execution mode: kernel" in result
        assert "Tasks: 0/0 complete" in result
        assert "Errors: 0" in result

    def test_format_status_running(self) -> None:
        """Test status format for running state with progress."""
        reporter = Reporter()
        state = {
            "goal": "Build API",
            "status": "running",
            "iteration_count": 5,
            "max_iterations": 30,
            "current_node": "code",
            "execution_mode": "kernel",
            "errors": ["minor warning"],
        }
        tasks = [
            {"id": "T-001", "status": "done"},
            {"id": "T-002", "status": "in_progress"},
            {"id": "T-003", "status": "pending"},
        ]
        result = reporter.format_status(state, tasks)
        assert "Goal: Build API" in result
        assert "Status: running" in result
        assert "Progress: iteration 5/30" in result
        assert "Current node: code" in result
        assert "Tasks: 1/3 complete" in result
        assert "Errors: 1 (minor warning)" in result

    def test_format_status_complete(self) -> None:
        """Test status format for completed state."""
        reporter = Reporter()
        state = {
            "goal": "Done goal",
            "status": "complete",
            "iteration_count": 20,
            "max_iterations": 30,
            "current_node": "code",
            "execution_mode": "ralph",
            "errors": [],
        }
        tasks = [
            {"id": "T-001", "status": "done"},
            {"id": "T-002", "status": "done"},
        ]
        result = reporter.format_status(state, tasks)
        assert "Status: complete" in result
        assert "Tasks: 2/2 complete" in result
        assert "Execution mode: ralph" in result

    def test_format_status_no_tasks(self) -> None:
        """Test status format with no tasks."""
        reporter = Reporter()
        state = {
            "goal": "Simple goal",
            "status": "running",
            "iteration_count": 2,
            "max_iterations": 10,
            "current_node": "plan",
            "execution_mode": "kernel",
            "errors": [],
        }
        result = reporter.format_status(state, [])
        assert "Tasks: 0/0 complete" in result

    def test_format_status_long_error_truncated(self) -> None:
        """Test that long error messages are truncated in status."""
        reporter = Reporter()
        long_error = "x" * 100
        state = {
            "goal": "test",
            "status": "error",
            "iteration_count": 1,
            "max_iterations": 30,
            "current_node": "init",
            "execution_mode": "kernel",
            "errors": [long_error],
        }
        result = reporter.format_status(state, [])
        assert "..." in result
        # The preview should be truncated
        assert long_error not in result


class TestRunnerStatusFlag:
    """Tests for --status flag in runner.py."""

    @pytest.fixture
    def status_env(self, tmp_path: Path) -> Path:
        """Set up a runner environment for --status testing."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()

        state_data = {
            "current_node": "code",
            "iteration_count": 5,
            "max_iterations": 30,
            "goal": "Build a web app",
            "status": "running",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "coding"},
            "node_visits": {},
            "progress_history": [],
            "execution_mode": "kernel",
            "workspace_path": "",
        }
        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

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
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator")
        (kernel_dir / "prompts" / "coder.md").write_text("Coder")
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
            yaml.safe_dump({"iteration": 5, "tasks_total": 2, "tasks_done": 1, "status": "in_progress"}, f)

        # Create tasks.yaml
        tasks_data = {
            "tasks": [
                {"id": "T-001", "description": "Setup", "status": "done"},
                {"id": "T-002", "description": "Implement", "status": "in_progress"},
            ]
        }
        with open(memory_dir / "tasks.yaml", "w") as f:
            yaml.safe_dump(tasks_data, f)

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_status_flag_no_goal_required(self) -> None:
        """Test that --status does not require --goal."""
        args = runner.parse_args(["--status"])
        assert args.status is True
        assert args.goal is None

    def test_status_prints_and_returns(self, status_env: Path, monkeypatch, capsys) -> None:
        """Test --status prints status and returns without running."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", status_env)
        state = runner.main(["--status"])
        captured = capsys.readouterr()
        assert "=== Kernel Status ===" in captured.out
        assert "Build a web app" in captured.out
        assert "running" in captured.out
        assert "code" in captured.out
        # Should return a state dict
        assert state["goal"] == "Build a web app"
        assert state["iteration_count"] == 5

    def test_status_shows_tasks(self, status_env: Path, monkeypatch, capsys) -> None:
        """Test --status shows task progress."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", status_env)
        runner.main(["--status"])
        captured = capsys.readouterr()
        assert "1/2 complete" in captured.out

    def test_status_no_tasks_file(self, status_env: Path, monkeypatch, capsys) -> None:
        """Test --status works when tasks.yaml does not exist."""
        # Remove tasks.yaml
        tasks_file = status_env / "memory" / "tasks.yaml"
        tasks_file.unlink()

        monkeypatch.setattr(runner, "KERNEL_ROOT", status_env)
        runner.main(["--status"])
        captured = capsys.readouterr()
        assert "0/0 complete" in captured.out


class TestRunnerVerboseFlag:
    """Tests for --verbose flag in runner.py parse_args."""

    def test_verbose_flag(self) -> None:
        """Test parsing the --verbose flag."""
        args = runner.parse_args(["--goal", "test", "--verbose"])
        assert args.verbose is True

    def test_verbose_default(self) -> None:
        """Test that --verbose defaults to False."""
        args = runner.parse_args(["--goal", "test"])
        assert args.verbose is False
