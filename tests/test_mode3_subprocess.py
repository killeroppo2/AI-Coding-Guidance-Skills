"""Tests for Mode 3 subprocess process group creation and timeout behavior."""

import os
import signal
import subprocess
from unittest.mock import MagicMock, patch

import pytest
import yaml

import runner


@pytest.fixture
def mode3_env(tmp_path):
    """Set up the environment for Mode 3 subprocess tests."""
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

    return tmp_path


class TestMode3ProcessGroup:
    """Tests for process group creation in Mode 3 subprocess execution."""

    def test_popen_uses_setpgrp(self, mode3_env):
        """Verify subprocess.Popen is called with preexec_fn=os.setpgrp."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("TRANSITION: done", "")
        mock_proc.returncode = 0
        mock_proc.kill.return_value = None

        with (
            patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch("runner.KERNEL_ROOT", mode3_env),
            patch("signal.signal"),
            patch("atexit.register"),
        ):
            runner.main(
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

        # Verify preexec_fn=os.setpgrp was passed to Popen
        assert mock_popen.called
        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs.get("preexec_fn") is os.setpgrp

    def test_timeout_uses_killpg(self, mode3_env):
        """Verify os.killpg is used to kill the process group on timeout."""
        timeout_exc = subprocess.TimeoutExpired(cmd="echo test", timeout=10)

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        call_count = [0]

        def _communicate_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise timeout_exc
            return ("", "")

        mock_proc.communicate.side_effect = _communicate_side_effect
        mock_proc.kill.return_value = None

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("runner.KERNEL_ROOT", mode3_env),
            patch("signal.signal"),
            patch("atexit.register"),
            patch("os.killpg") as mock_killpg,
        ):
            runner.main(
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

        # Verify os.killpg was called with the process pid and SIGKILL
        mock_killpg.assert_called_with(12345, signal.SIGKILL)

    def test_timeout_communicate_has_timeout(self, mode3_env):
        """Verify the second communicate() call after kill has a timeout."""
        timeout_exc = subprocess.TimeoutExpired(cmd="echo test", timeout=10)

        mock_proc = MagicMock()
        mock_proc.pid = 99999
        call_count = [0]

        def _communicate_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise timeout_exc
            return ("output", "error")

        mock_proc.communicate.side_effect = _communicate_side_effect
        mock_proc.kill.return_value = None

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("runner.KERNEL_ROOT", mode3_env),
            patch("signal.signal"),
            patch("atexit.register"),
            patch("os.killpg"),
        ):
            runner.main(
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

        # Second communicate call should have timeout parameter
        communicate_calls = mock_proc.communicate.call_args_list
        assert len(communicate_calls) >= 2
        second_call_kwargs = communicate_calls[1][1]
        assert "timeout" in second_call_kwargs
        assert second_call_kwargs["timeout"] == 5

    def test_killpg_fallback_on_process_lookup_error(self, mode3_env):
        """Verify proc.kill() is used as fallback when killpg raises ProcessLookupError."""
        timeout_exc = subprocess.TimeoutExpired(cmd="echo test", timeout=10)

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        call_count = [0]

        def _communicate_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise timeout_exc
            return ("", "")

        mock_proc.communicate.side_effect = _communicate_side_effect
        mock_proc.kill.return_value = None

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("runner.KERNEL_ROOT", mode3_env),
            patch("signal.signal"),
            patch("atexit.register"),
            patch("os.killpg", side_effect=ProcessLookupError),
        ):
            runner.main(
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

        # Fallback to proc.kill() should be called
        mock_proc.kill.assert_called()

    def test_second_communicate_timeout_handled_gracefully(self, mode3_env):
        """Verify that TimeoutExpired on second communicate is handled gracefully."""
        timeout_exc = subprocess.TimeoutExpired(cmd="echo test", timeout=10)
        second_timeout_exc = subprocess.TimeoutExpired(cmd="echo test", timeout=5)

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        call_count = [0]

        def _communicate_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise timeout_exc
            # Second communicate also times out
            raise second_timeout_exc

        mock_proc.communicate.side_effect = _communicate_side_effect
        mock_proc.kill.return_value = None

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("runner.KERNEL_ROOT", mode3_env),
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

        # Should still complete without crashing
        errors = result.get("errors", [])
        timeout_errors = [e for e in errors if "Timeout after" in e]
        assert len(timeout_errors) > 0
