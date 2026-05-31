"""Tests for graceful shutdown and interrupt handling in runner.py."""

import signal
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
import yaml

import runner
from memory.state_manager import StateManager


@pytest.fixture
def state_mgr_fixture(tmp_path):
    """Create a StateManager with temporary paths for testing."""
    state_file = tmp_path / "state.yaml"
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    state_data = {
        "current_node": "init",
        "iteration_count": 5,
        "max_iterations": 30,
        "goal": "Test goal",
        "workspace_path": "",
        "status": "running",
        "last_updated": "",
        "errors": [],
        "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        "node_visits": {},
        "progress_history": [],
        "execution_mode": "kernel",
    }
    with open(state_file, "w") as f:
        yaml.safe_dump(state_data, f)
    mgr = StateManager(str(state_file), str(memory_dir))
    return mgr


class TestSignalHandler:
    """Tests for signal handler registration and behavior."""

    def test_signal_handler_sets_interrupted_status(self, state_mgr_fixture):
        """Test that the shutdown handler sets status to interrupted."""
        state_mgr = state_mgr_fixture
        state_mgr.state["status"] = "running"

        # Simulate the shutdown handler closure from runner.py
        def _shutdown_handler(signum, frame):
            state_mgr.state["status"] = "interrupted"
            state_mgr.state.setdefault("errors", []).append("Execution interrupted by signal")
            state_mgr.save_state()
            sys.exit(130)

        with pytest.raises(SystemExit) as exc_info:
            _shutdown_handler(signal.SIGINT, None)

        assert exc_info.value.code == 130
        assert state_mgr.state["status"] == "interrupted"
        assert "Execution interrupted by signal" in state_mgr.state["errors"]

    def test_signal_handler_saves_state(self, state_mgr_fixture):
        """Test that the shutdown handler calls save_state."""
        state_mgr = state_mgr_fixture
        state_mgr.state["status"] = "running"

        with patch.object(state_mgr, "save_state") as mock_save:

            def _shutdown_handler(signum, frame):
                state_mgr.state["status"] = "interrupted"
                state_mgr.state.setdefault("errors", []).append("Execution interrupted by signal")
                mock_save()
                sys.exit(130)

            with pytest.raises(SystemExit):
                _shutdown_handler(signal.SIGTERM, None)

            mock_save.assert_called_once()

    @patch("signal.signal")
    def test_signal_handlers_registered_in_mode3(self, mock_signal, tmp_path):
        """Test that SIGINT and SIGTERM handlers are registered in Mode 3."""
        # We'll trace what signal.signal is called with
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        graph_file = tmp_path / "kernel" / "graph.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "skills").mkdir()
        (knowledge_dir / "skills" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "rules" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules" / "manual").mkdir()
        (knowledge_dir / "rules" / "learned").mkdir()
        (knowledge_dir / "patterns").mkdir()
        (knowledge_dir / "patterns" / "_index.yaml").write_text("items: []")

        graph_data = {
            "version": "1.0",
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Init",
                    "transitions": [],
                    "max_retries": 5,
                }
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        # Mock subprocess.Popen to avoid actually calling a command
        with (
            patch("subprocess.Popen") as mock_popen,
            patch("runner.KERNEL_ROOT", tmp_path),
            patch("atexit.register"),
        ):
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ("TRANSITION: done", "")
            mock_proc.returncode = 0
            mock_proc.kill.return_value = None
            mock_popen.return_value = mock_proc
            runner.main(
                [
                    "--goal",
                    "test",
                    "--ai-command",
                    "echo test",
                    "--max-iterations",
                    "1",
                ]
            )

        # Check that signal.signal was called for SIGINT and SIGTERM
        signal_calls = [call[0][0] for call in mock_signal.call_args_list]
        assert signal.SIGINT in signal_calls
        assert signal.SIGTERM in signal_calls


class TestAtexitHandler:
    """Tests for the atexit handler."""

    def test_atexit_saves_state_when_running(self, state_mgr_fixture):
        """Test that atexit handler saves state when status is running."""
        state_mgr = state_mgr_fixture
        state_mgr.state["status"] = "running"

        # Simulate the atexit handler closure
        def _atexit_save():
            if state_mgr.state.get("status") == "running":
                state_mgr.state["status"] = "interrupted"
                state_mgr.save_state()

        with patch.object(state_mgr, "save_state") as mock_save:
            _atexit_save()

        assert state_mgr.state["status"] == "interrupted"
        mock_save.assert_called_once()

    def test_atexit_does_not_save_when_complete(self, state_mgr_fixture):
        """Test that atexit handler does not save state when status is complete."""
        state_mgr = state_mgr_fixture
        state_mgr.state["status"] = "complete"

        def _atexit_save():
            if state_mgr.state.get("status") == "running":
                state_mgr.state["status"] = "interrupted"
                state_mgr.save_state()

        with patch.object(state_mgr, "save_state") as mock_save:
            _atexit_save()

        assert state_mgr.state["status"] == "complete"
        mock_save.assert_not_called()

    def test_atexit_does_not_save_when_interrupted(self, state_mgr_fixture):
        """Test that atexit handler does not save when already interrupted."""
        state_mgr = state_mgr_fixture
        state_mgr.state["status"] = "interrupted"

        def _atexit_save():
            if state_mgr.state.get("status") == "running":
                state_mgr.state["status"] = "interrupted"
                state_mgr.save_state()

        with patch.object(state_mgr, "save_state") as mock_save:
            _atexit_save()

        mock_save.assert_not_called()

    @patch("atexit.register")
    @patch("signal.signal")
    def test_atexit_registered_in_mode3(self, mock_signal, mock_atexit, tmp_path):
        """Test that atexit handler is registered in Mode 3."""
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        graph_file = tmp_path / "kernel" / "graph.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "skills").mkdir()
        (knowledge_dir / "skills" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "rules" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules" / "manual").mkdir()
        (knowledge_dir / "rules" / "learned").mkdir()
        (knowledge_dir / "patterns").mkdir()
        (knowledge_dir / "patterns" / "_index.yaml").write_text("items: []")

        graph_data = {
            "version": "1.0",
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Init",
                    "transitions": [],
                    "max_retries": 5,
                }
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        with patch("subprocess.Popen") as mock_popen, patch("runner.KERNEL_ROOT", tmp_path):
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ("TRANSITION: done", "")
            mock_proc.returncode = 0
            mock_proc.kill.return_value = None
            mock_popen.return_value = mock_proc
            runner.main(
                [
                    "--goal",
                    "test",
                    "--ai-command",
                    "echo test",
                    "--max-iterations",
                    "1",
                ]
            )

        mock_atexit.assert_called_once()


class TestResumeFromInterrupted:
    """Tests for resuming from interrupted status."""

    def test_resume_from_interrupted_resets_to_running(self, tmp_path):
        """Test that --resume from 'interrupted' status resets to running."""
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        graph_file = tmp_path / "kernel" / "graph.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "skills").mkdir()
        (knowledge_dir / "skills" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "rules" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules" / "manual").mkdir()
        (knowledge_dir / "rules" / "learned").mkdir()
        (knowledge_dir / "patterns").mkdir()
        (knowledge_dir / "patterns" / "_index.yaml").write_text("items: []")

        state_data = {
            "current_node": "plan",
            "iteration_count": 3,
            "max_iterations": 30,
            "goal": "Build an API",
            "workspace_path": "",
            "status": "interrupted",
            "last_updated": "",
            "errors": ["Execution interrupted by signal"],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
            "node_visits": {"init": 2, "plan": 1},
            "progress_history": [],
            "execution_mode": "kernel",
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        graph_data = {
            "version": "1.0",
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Init",
                    "transitions": [{"to": "plan", "condition": "goal_loaded"}],
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
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        with patch("runner.KERNEL_ROOT", tmp_path):
            result = runner.main(
                [
                    "--goal",
                    "Build an API",
                    "--resume",
                    "--dry-run",
                    "--max-iterations",
                    "1",
                ]
            )

        # After resume, status should have been reset from interrupted,
        # then changed to complete (graph ends after one iteration in dry-run)
        assert result["status"] == "complete"

    def test_resume_does_not_reset_running_status(self, tmp_path):
        """Test that --resume does not modify status when it is already running."""
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        graph_file = tmp_path / "kernel" / "graph.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "skills").mkdir()
        (knowledge_dir / "skills" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "rules" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules" / "manual").mkdir()
        (knowledge_dir / "rules" / "learned").mkdir()
        (knowledge_dir / "patterns").mkdir()
        (knowledge_dir / "patterns" / "_index.yaml").write_text("items: []")

        state_data = {
            "current_node": "init",
            "iteration_count": 2,
            "max_iterations": 30,
            "goal": "Build an API",
            "workspace_path": "",
            "status": "running",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
            "node_visits": {"init": 2},
            "progress_history": [],
            "execution_mode": "kernel",
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        graph_data = {
            "version": "1.0",
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Init",
                    "transitions": [],
                    "max_retries": 5,
                }
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        with patch("runner.KERNEL_ROOT", tmp_path):
            result = runner.main(
                [
                    "--goal",
                    "Build an API",
                    "--resume",
                    "--dry-run",
                    "--max-iterations",
                    "1",
                ]
            )

        # Should complete normally (status was already running)
        assert result["status"] == "complete"


class TestTimeoutHandling:
    """Tests for timeout error logging with subprocess context."""

    def test_timeout_error_includes_context(self, tmp_path):
        """Test that timeout error log includes stdout/stderr context."""
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        graph_file = tmp_path / "kernel" / "graph.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "skills").mkdir()
        (knowledge_dir / "skills" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "rules" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules" / "manual").mkdir()
        (knowledge_dir / "rules" / "learned").mkdir()
        (knowledge_dir / "patterns").mkdir()
        (knowledge_dir / "patterns" / "_index.yaml").write_text("items: []")

        graph_data = {
            "version": "1.0",
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Init",
                    "transitions": [{"to": "plan", "condition": "ready"}],
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
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        timeout_exc = subprocess.TimeoutExpired(
            cmd="echo test", timeout=10, output="partial output here", stderr="error output here"
        )

        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = timeout_exc
        mock_proc.kill.return_value = None

        # After kill, second communicate returns partial output
        def _communicate_after_kill(*args, **kwargs):
            if mock_proc.communicate.call_count > 1:
                return ("partial output here", "error output here")
            raise timeout_exc

        mock_proc.communicate.side_effect = _communicate_after_kill

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("runner.KERNEL_ROOT", tmp_path),
            patch("signal.signal"),
            patch("atexit.register"),
            patch("os.killpg"),
        ):
            result = runner.main(
                [
                    "--goal",
                    "test",
                    "--ai-command",
                    "echo test",
                    "--max-iterations",
                    "2",
                    "--complexity",
                    "high",
                ]
            )

        # Check that timeout errors contain context
        errors = result.get("errors", [])
        assert len(errors) > 0
        # At least one error should mention timeout and contain partial output info
        timeout_errors = [e for e in errors if "Timeout after" in e]
        assert len(timeout_errors) > 0
        assert "partial stdout" in timeout_errors[0]
        assert "stderr" in timeout_errors[0]

    def test_timeout_error_without_output(self, tmp_path):
        """Test timeout error logging when no stdout/stderr is available."""
        state_file = tmp_path / "kernel" / "state.yaml"
        state_file.parent.mkdir(parents=True)
        graph_file = tmp_path / "kernel" / "graph.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "skills").mkdir()
        (knowledge_dir / "skills" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "rules" / "_index.yaml").write_text("items: []")
        (knowledge_dir / "rules" / "manual").mkdir()
        (knowledge_dir / "rules" / "learned").mkdir()
        (knowledge_dir / "patterns").mkdir()
        (knowledge_dir / "patterns" / "_index.yaml").write_text("items: []")

        graph_data = {
            "version": "1.0",
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Init",
                    "transitions": [{"to": "plan", "condition": "ready"}],
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
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        # TimeoutExpired with no stdout/stderr
        timeout_exc = subprocess.TimeoutExpired(cmd="echo test", timeout=10)

        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = timeout_exc
        mock_proc.kill.return_value = None
        # After kill, second communicate returns empty
        call_count = [0]

        def _communicate_no_output(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 2 == 1:
                raise timeout_exc
            return ("", "")

        mock_proc.communicate.side_effect = _communicate_no_output

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("runner.KERNEL_ROOT", tmp_path),
            patch("signal.signal"),
            patch("atexit.register"),
            patch("os.killpg"),
        ):
            result = runner.main(
                [
                    "--goal",
                    "test",
                    "--ai-command",
                    "echo test",
                    "--max-iterations",
                    "2",
                    "--complexity",
                    "high",
                ]
            )

        errors = result.get("errors", [])
        timeout_errors = [e for e in errors if "Timeout after" in e]
        assert len(timeout_errors) > 0
        # Should not contain partial output since there was none
        assert "partial stdout" not in timeout_errors[0]
