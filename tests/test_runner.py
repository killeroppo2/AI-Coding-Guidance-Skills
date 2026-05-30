"""Tests for runner.py - the kernel entry point."""

from pathlib import Path

import pytest
import yaml

import runner


class TestRunnerImport:
    """Tests for runner module import and structure."""

    def test_runner_importable(self) -> None:
        """Test that runner module can be imported."""
        assert runner is not None

    def test_runner_has_main(self) -> None:
        """Test that runner has a main function."""
        assert hasattr(runner, "main")
        assert callable(runner.main)

    def test_runner_has_parse_args(self) -> None:
        """Test that runner has parse_args function."""
        assert hasattr(runner, "parse_args")


class TestParseArgs:
    """Tests for the parse_args function."""

    def test_required_goal(self) -> None:
        """Test that --goal defaults to None when not provided."""
        args = runner.parse_args([])
        assert args.goal is None

    def test_goal_argument(self) -> None:
        """Test parsing the --goal argument."""
        args = runner.parse_args(["--goal", "Build an API"])
        assert args.goal == "Build an API"

    def test_max_iterations_default(self) -> None:
        """Test that --max-iterations defaults to 30."""
        args = runner.parse_args(["--goal", "test"])
        assert args.max_iterations == 30

    def test_max_iterations_custom(self) -> None:
        """Test parsing custom --max-iterations."""
        args = runner.parse_args(["--goal", "test", "--max-iterations", "10"])
        assert args.max_iterations == 10

    def test_dry_run_flag(self) -> None:
        """Test parsing the --dry-run flag."""
        args = runner.parse_args(["--goal", "test", "--dry-run"])
        assert args.dry_run is True

    def test_no_dry_run_default(self) -> None:
        """Test that --dry-run defaults to False."""
        args = runner.parse_args(["--goal", "test"])
        assert args.dry_run is False

    def test_check_flag(self) -> None:
        """Test parsing the --check flag."""
        args = runner.parse_args(["--check"])
        assert args.check is True
        assert args.goal is None

    def test_check_flag_default(self) -> None:
        """Test that --check defaults to False."""
        args = runner.parse_args(["--goal", "test"])
        assert args.check is False


class TestMain:
    """Tests for the main function."""

    def test_main_no_goal_exits(self) -> None:
        """Test that main exits with code 2 when no --goal is provided."""
        with pytest.raises(SystemExit) as exc_info:
            runner.main([])
        assert exc_info.value.code == 2

    def test_main_check_flag(self) -> None:
        """Test that --check runs setup checks and exits."""
        with pytest.raises(SystemExit) as exc_info:
            runner.main(["--check"])
        # Exit code 0 means all checks passed, 1 means some failed
        assert exc_info.value.code in (0, 1)

    def test_main_dry_run(self) -> None:
        """Test main function with dry-run."""
        state = runner.main(["--goal", "test goal", "--dry-run"])
        assert state["goal"] == "test goal"
        assert state["status"] == "complete"

    def test_main_dry_run_max_iterations(self) -> None:
        """Test main function respects max iterations in dry-run."""
        state = runner.main(["--goal", "test", "--max-iterations", "3", "--dry-run"])
        assert state["iteration_count"] <= 3

    def test_main_dry_run_does_not_modify_state(self, state_yaml: Path) -> None:
        """Test that dry run does not modify state.yaml."""
        original_content = state_yaml.read_text()
        runner.main(["--goal", "test goal", "--max-iterations", "2", "--dry-run"])
        assert state_yaml.read_text() == original_content

    def test_main_produces_output(self, capsys) -> None:
        """Test that dry run produces output."""
        runner.main(["--goal", "test goal", "--max-iterations", "1", "--dry-run"])
        captured = capsys.readouterr()
        assert "[预演]" in captured.out
        assert "test goal" in captured.out

    def test_main_shows_node_info(self, capsys) -> None:
        """Test that dry run shows node information."""
        runner.main(["--goal", "test", "--max-iterations", "2", "--dry-run"])
        captured = capsys.readouterr()
        assert "init" in captured.out
        assert "提示词长度" in captured.out

    def test_main_non_dry_run(self, tmp_path: Path, monkeypatch) -> None:
        """Test main function without dry-run modifies state."""
        import shutil

        import yaml

        # Set up temp kernel structure
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

        # Copy graph.yaml
        kernel_root = Path(__file__).parent.parent
        shutil.copy(kernel_root / "kernel" / "graph.yaml", tmp_path / "kernel" / "graph.yaml")

        # Copy prompts
        prompts_dir = tmp_path / "kernel" / "prompts"
        shutil.copytree(kernel_root / "kernel" / "prompts", prompts_dir)

        # Create memory dir
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "decisions.jsonl").touch()
        (memory_dir / "reflections.jsonl").touch()
        (memory_dir / "current_goal.md").touch()
        progress = {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump(progress, f)

        # Create knowledge dir
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        monkeypatch.setattr(runner, "KERNEL_ROOT", tmp_path)
        state = runner.main(["--goal", "integration test", "--max-iterations", "2"])
        assert state["goal"] == "integration test"
        assert state["iteration_count"] > 0
        # Verify state was saved
        saved = yaml.safe_load(state_file.read_text())
        assert saved["goal"] == "integration test"


class TestParseArgsExtended:
    """Tests for new CLI arguments (--ai-command, --timeout, --resume, --generate-prompt)."""

    def test_ai_command_argument(self) -> None:
        """Test parsing --ai-command argument."""
        args = runner.parse_args(["--goal", "test", "--ai-command", "claude --print"])
        assert args.ai_command == "claude --print"

    def test_ai_command_default_none(self) -> None:
        """Test that --ai-command defaults to None."""
        args = runner.parse_args(["--goal", "test"])
        assert args.ai_command is None

    def test_timeout_argument(self) -> None:
        """Test parsing --timeout argument."""
        args = runner.parse_args(["--goal", "test", "--timeout", "60"])
        assert args.timeout == 60

    def test_timeout_default(self) -> None:
        """Test that --timeout defaults to 300."""
        args = runner.parse_args(["--goal", "test"])
        assert args.timeout == 300

    def test_resume_flag(self) -> None:
        """Test parsing --resume flag."""
        args = runner.parse_args(["--goal", "test", "--resume"])
        assert args.resume is True

    def test_resume_default(self) -> None:
        """Test that --resume defaults to False."""
        args = runner.parse_args(["--goal", "test"])
        assert args.resume is False

    def test_generate_prompt_flag(self) -> None:
        """Test parsing --generate-prompt flag."""
        args = runner.parse_args(["--goal", "test", "--generate-prompt"])
        assert args.generate_prompt is True

    def test_generate_prompt_default(self) -> None:
        """Test that --generate-prompt defaults to False."""
        args = runner.parse_args(["--goal", "test"])
        assert args.generate_prompt is False

    def test_all_new_args_together(self) -> None:
        """Test parsing all new arguments together."""
        args = runner.parse_args(
            [
                "--goal",
                "test",
                "--ai-command",
                "claude --print",
                "--timeout",
                "120",
                "--resume",
                "--generate-prompt",
            ]
        )
        assert args.ai_command == "claude --print"
        assert args.timeout == 120
        assert args.resume is True
        assert args.generate_prompt is True


class TestMode3:
    """Tests for Mode 3 (real AI execution via subprocess)."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a complete runner environment in tmp_path."""
        # kernel dir
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
                    "max_retries": 1,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/planner.md",
                    "description": "Plan tasks",
                    "transitions": [
                        {"to": "code", "condition": "plan_ready"},
                        {"to": "plan", "condition": "plan_needs_revision"},
                    ],
                    "max_retries": 2,
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
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator prompt")
        (kernel_dir / "prompts" / "planner.md").write_text("Planner prompt")
        (kernel_dir / "prompts" / "coder.md").write_text("Coder prompt")

        (kernel_dir / "BOOT.md").write_text("# Boot\nBoot content.")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao\nDao content.")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy\nStrategy content.")

        # memory dir
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "decisions.jsonl").touch()
        (memory_dir / "reflections.jsonl").touch()
        (memory_dir / "current_goal.md").touch()
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump(
                {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}, f
            )

        # knowledge dir
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_mode3_advances_with_transition(self, runner_env: Path, monkeypatch) -> None:
        """Test Mode 3 advances node based on TRANSITION line in AI output."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            "Some output\nSTATUS: success\nTRANSITION: goal_loaded\nMore output",
            "",
        )
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            state = runner.main(
                [
                    "--goal",
                    "test mode3",
                    "--ai-command",
                    "echo hello",
                    "--max-iterations",
                    "1",
                    "--complexity",
                    "high",
                ]
            )

        mock_popen.assert_called_once()
        # After init with TRANSITION: goal_loaded, should advance to "plan"
        assert state["current_node"] == "plan"

    def test_mode3_fallback_first_transition(self, runner_env: Path, monkeypatch) -> None:
        """Test Mode 3 stays on same node when no TRANSITION line found (contract violation)."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            "Some output without transition info\nSTATUS: success",
            "",
        )
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main(
                [
                    "--goal",
                    "test fallback",
                    "--ai-command",
                    "echo hi",
                    "--max-iterations",
                    "1",
                    "--complexity",
                    "high",
                ]
            )

        # Contract validation fails (missing TRANSITION), stays on same node
        assert state["current_node"] == "init"

    def test_mode3_unmatched_transition_falls_back(self, runner_env: Path, monkeypatch) -> None:
        """Test Mode 3 stays on node when transition condition is invalid (contract violation)."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            "STATUS: success\nTRANSITION: nonexistent_condition",
            "",
        )
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main(
                [
                    "--goal",
                    "test unmatched",
                    "--ai-command",
                    "echo hi",
                    "--max-iterations",
                    "1",
                    "--complexity",
                    "high",
                ]
            )

        # Contract validation fails (invalid transition for init), stays on same node
        assert state["current_node"] == "init"

    def test_mode3_timeout_handling(self, runner_env: Path, monkeypatch) -> None:
        """Test Mode 3 handles subprocess timeout correctly."""
        import subprocess as sp
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        call_count = [0]
        timeout_exc = sp.TimeoutExpired("echo", 5)

        def _communicate_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 2 == 1:
                raise timeout_exc
            return ("", "")

        mock_proc.communicate.side_effect = _communicate_side_effect
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main(
                [
                    "--goal",
                    "test timeout",
                    "--ai-command",
                    "echo hi",
                    "--timeout",
                    "5",
                    "--max-iterations",
                    "2",
                    "--complexity",
                    "high",
                ]
            )

        # Should stay on same node and record error
        assert state["current_node"] == "init"
        assert any("Timeout" in e for e in state.get("errors", []))

    def test_mode3_command_not_found(self, runner_env: Path, monkeypatch, capsys) -> None:
        """Test Mode 3 handles missing AI command gracefully."""
        from unittest.mock import patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        with patch("subprocess.Popen", side_effect=FileNotFoundError()):
            state = runner.main(
                [
                    "--goal",
                    "test cmd not found",
                    "--ai-command",
                    "nonexistent_command --flag",
                    "--max-iterations",
                    "3",
                ]
            )

        assert state["status"] == "error"
        assert any(
            "not found" in e.lower() or "Command not found" in e for e in state.get("errors", [])
        )
        captured = capsys.readouterr()
        assert "nonexistent_command" in captured.err

    def test_mode3_completes_at_terminal_node(self, runner_env: Path, monkeypatch) -> None:
        """Test Mode 3 completes when reaching a node with no transitions."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        call_count = [0]

        def mock_popen(*args, **kwargs):
            call_count[0] += 1
            proc = MagicMock()
            proc.kill.return_value = None
            if call_count[0] == 1:
                proc.communicate.return_value = ("STATUS: success\nTRANSITION: goal_loaded", "")
                proc.returncode = 0
            elif call_count[0] == 2:
                proc.communicate.return_value = ("STATUS: success\nTRANSITION: plan_ready", "")
                proc.returncode = 0
            else:
                proc.communicate.return_value = ("STATUS: success\nTRANSITION: done", "")
                proc.returncode = 0
            return proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            state = runner.main(
                [
                    "--goal",
                    "test terminal",
                    "--ai-command",
                    "echo hi",
                    "--max-iterations",
                    "10",
                ]
            )

        # Should reach "code" node which has no transitions -> complete
        assert state["status"] == "complete"
        assert state["current_node"] == "code"

    def test_mode3_subprocess_receives_context(self, runner_env: Path, monkeypatch) -> None:
        """Test that subprocess receives assembled context as stdin."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        captured_input = []

        def mock_popen(*args, **kwargs):
            proc = MagicMock()
            proc.kill.return_value = None

            def mock_communicate(input=None, timeout=None):
                captured_input.append(input or "")
                return ("STATUS: success\nTRANSITION: goal_loaded", "")

            proc.communicate.side_effect = mock_communicate
            proc.returncode = 0
            return proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            runner.main(
                [
                    "--goal",
                    "context test",
                    "--ai-command",
                    "claude --print",
                    "--max-iterations",
                    "1",
                    "--complexity",
                    "high",
                ]
            )

        assert len(captured_input) == 1
        assert "=== BOOT SEQUENCE ===" in captured_input[0]
        assert "=== CURRENT STATE ===" in captured_input[0]
        assert "=== NODE PROMPT (init) ===" in captured_input[0]

    def test_mode3_no_ai_command_falls_back_to_scaffolding(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test that no --ai-command and no --dry-run falls back to Mode 1 scaffolding."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main(["--goal", "test fallback mode", "--max-iterations", "1"])
        # Should still advance state (Mode 1 scaffolding behavior)
        assert state["iteration_count"] > 0


class TestGeneratePrompt:
    """Tests for --generate-prompt flag."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a complete runner environment in tmp_path."""
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
            "max_iterations": 30,
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator prompt text.")
        (kernel_dir / "BOOT.md").write_text("# Boot\nBoot sequence content.")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao\nSimplicity.")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy\nPlan.")

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

    def test_generate_prompt_outputs_context(self, runner_env: Path, monkeypatch, capsys) -> None:
        """Test --generate-prompt outputs assembled context to stdout."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        runner.main(["--goal", "test prompt", "--generate-prompt"])
        captured = capsys.readouterr()
        assert "=== BOOT SEQUENCE ===" in captured.out
        assert "=== CURRENT STATE ===" in captured.out
        assert "=== CURRENT ROLE PROMPT ===" in captured.out
        assert "=== PHILOSOPHY: DAO ===" in captured.out
        assert "=== PHILOSOPHY: STRATEGY ===" in captured.out

    def test_generate_prompt_exits_without_running_loop(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test --generate-prompt does not run the main loop."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main(["--goal", "test prompt", "--generate-prompt"])
        # Iteration count should not have advanced
        assert state["iteration_count"] == 0

    def test_generate_prompt_with_invalid_node(self, runner_env: Path, monkeypatch, capsys) -> None:
        """Test --generate-prompt with invalid current node still produces output."""
        # Set state to reference a non-existent node
        state_file = runner_env / "kernel" / "state.yaml"
        state_data = {
            "current_node": "nonexistent",
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
        runner.main(["--goal", "test", "--generate-prompt"])
        captured = capsys.readouterr()
        # BootstrapGenerator gracefully skips missing node prompt
        assert "=== BOOT SEQUENCE ===" in captured.out
        assert "=== CURRENT STATE ===" in captured.out
        # No role prompt section since node doesn't exist
        assert "=== CURRENT ROLE PROMPT ===" not in captured.out


class TestResume:
    """Tests for --resume flag."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a runner environment with existing goal in state."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()

        state_data = {
            "current_node": "plan",
            "iteration_count": 3,
            "max_iterations": 30,
            "goal": "existing goal from previous run",
            "status": "running",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "coding"},
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
                    "max_retries": 1,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/planner.md",
                    "description": "Plan",
                    "transitions": [{"to": "code", "condition": "plan_ready"}],
                    "max_retries": 2,
                },
                {
                    "id": "code",
                    "prompt_file": "prompts/coder.md",
                    "description": "Code",
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
        (kernel_dir / "prompts" / "planner.md").write_text("Planner")
        (kernel_dir / "prompts" / "coder.md").write_text("Coder")
        (kernel_dir / "BOOT.md").write_text("# Boot")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy")

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "decisions.jsonl").touch()
        (memory_dir / "reflections.jsonl").touch()
        (memory_dir / "current_goal.md").write_text(
            "# Current Goal\n\nexisting goal from previous run\n"
        )
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump(
                {"iteration": 3, "tasks_total": 0, "tasks_done": 0, "status": "in_progress"}, f
            )

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_resume_preserves_existing_goal(self, runner_env: Path, monkeypatch) -> None:
        """Test --resume does not overwrite existing goal."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main(
            [
                "--goal",
                "new goal that should be ignored",
                "--resume",
                "--dry-run",
                "--max-iterations",
                "1",
            ]
        )
        assert state["goal"] == "existing goal from previous run"

    def test_no_resume_overwrites_goal(self, runner_env: Path, monkeypatch) -> None:
        """Test without --resume, goal is overwritten."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main(
            [
                "--goal",
                "new goal",
                "--dry-run",
                "--max-iterations",
                "1",
            ]
        )
        assert state["goal"] == "new goal"


class TestParseTransition:
    """Tests for the _parse_transition helper function."""

    def test_parse_transition_found(self) -> None:
        """Test parsing a TRANSITION line from output."""
        output = "Some AI output\nTRANSITION: plan_ready\nMore output"
        assert runner._parse_transition(output) == "plan_ready"

    def test_parse_transition_not_found(self) -> None:
        """Test parsing output with no TRANSITION line."""
        output = "Just regular output without transition info"
        assert runner._parse_transition(output) is None

    def test_parse_transition_with_whitespace(self) -> None:
        """Test parsing TRANSITION line with extra whitespace."""
        output = "  TRANSITION:  goal_loaded  \n"
        assert runner._parse_transition(output) == "goal_loaded"

    def test_parse_transition_first_match(self) -> None:
        """Test that first TRANSITION line is used if multiple exist."""
        output = "TRANSITION: first\nTRANSITION: second"
        assert runner._parse_transition(output) == "first"

    def test_parse_transition_empty_output(self) -> None:
        """Test parsing empty output."""
        assert runner._parse_transition("") is None


class TestStuckDetection:
    """Tests for stuck detection in the runner."""

    @pytest.fixture
    def stuck_env(self, tmp_path: Path) -> Path:
        """Set up an environment where a node will get stuck (cycling graph)."""
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

        # Graph where code cycles back to itself with max_retries=2
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
                    "transitions": [{"to": "code", "condition": "code_needs_retry"}],
                    "max_retries": 2,
                },
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator prompt")
        (kernel_dir / "prompts" / "coder.md").write_text("Coder prompt")
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
                {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}, f
            )

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    @pytest.fixture
    def stuck_handler_env(self, tmp_path: Path) -> Path:
        """Set up an environment with stuck_handler on the cycling node."""
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

        # Graph where code cycles back to itself with max_retries=2 and stuck_handler
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
                    "transitions": [{"to": "code", "condition": "code_needs_retry"}],
                    "max_retries": 2,
                    "stuck_handler": "reflect",
                },
                {
                    "id": "reflect",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Reflect on progress",
                    "transitions": [],
                    "max_retries": 1,
                },
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator prompt")
        (kernel_dir / "prompts" / "coder.md").write_text("Coder prompt")
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
                {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}, f
            )

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_runner_detects_stuck_and_stops(self, stuck_env: Path, monkeypatch) -> None:
        """Test runner stops with 'stuck' status when max_retries exceeded."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", stuck_env)
        state = runner.main(
            [
                "--goal",
                "test stuck detection",
                "--max-iterations",
                "20",
            ]
        )
        assert state["status"] == "stuck"
        assert any("exceeded max_retries" in e for e in state.get("errors", []))

    def test_runner_stuck_handler_redirect(self, stuck_handler_env: Path, monkeypatch) -> None:
        """Test runner redirects to stuck_handler node when max_retries exceeded."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", stuck_handler_env)
        state = runner.main(
            [
                "--goal",
                "test stuck handler",
                "--max-iterations",
                "20",
            ]
        )
        # Should redirect to reflect and then complete (reflect has no transitions)
        assert state["current_node"] == "reflect"
        assert state["status"] == "complete"

    def test_runner_stuck_in_dry_run(self, stuck_env: Path, monkeypatch, capsys) -> None:
        """Test dry-run prints stuck message when max_retries exceeded."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", stuck_env)
        state = runner.main(
            [
                "--goal",
                "test stuck dry run",
                "--max-iterations",
                "20",
                "--dry-run",
            ]
        )
        captured = capsys.readouterr()
        assert "已遍历所有节点" in captured.out
        assert state["status"] == "complete"


class TestReviewFixes:
    """Tests for review findings fixes: shlex, fallback warning, resume reset, returncode."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a complete runner environment in tmp_path."""
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
                    "max_retries": 10,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/planner.md",
                    "description": "Plan tasks",
                    "transitions": [{"to": "code", "condition": "plan_ready"}],
                    "max_retries": 10,
                },
                {
                    "id": "code",
                    "prompt_file": "prompts/coder.md",
                    "description": "Write code",
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
        (kernel_dir / "prompts" / "coder.md").write_text("Coder prompt")
        (kernel_dir / "BOOT.md").write_text("# Boot\nBoot content.")
        (kernel_dir / "constitution.md").write_text("# Constitution\nImmutable rules.")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao\nDao content.")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy\nStrategy content.")

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

    def test_shlex_parsing_with_quoted_args(self, runner_env: Path, monkeypatch) -> None:
        """Test that AI command with quoted arguments is split correctly using shlex."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        captured_args = []

        def mock_popen(cmd, **kwargs):
            captured_args.append(cmd)
            proc = MagicMock()
            proc.communicate.return_value = ("STATUS: success\nTRANSITION: goal_loaded", "")
            proc.returncode = 0
            proc.kill.return_value = None
            proc.terminate.return_value = None
            return proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            runner.main(
                [
                    "--goal",
                    "test shlex",
                    "--ai-command",
                    'claude --print --model "claude-3"',
                    "--max-iterations",
                    "1",
                ]
            )

        assert len(captured_args) == 1
        # shlex.split should produce: ['claude', '--print', '--model', 'claude-3']
        assert captured_args[0] == ["claude", "--print", "--model", "claude-3"]

    def test_fallback_produces_warning_no_transition(
        self, runner_env: Path, monkeypatch, capsys
    ) -> None:
        """Test that missing TRANSITION line triggers contract violation."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            "Some output without any transition info\nSTATUS: success",
            "",
        )
        mock_proc.returncode = 0
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main(
                [
                    "--goal",
                    "test fallback warning",
                    "--ai-command",
                    "echo hi",
                    "--max-iterations",
                    "1",
                ]
            )

        captured = capsys.readouterr()
        assert "[CONTRACT VIOLATION] Missing required TRANSITION line" in captured.err
        # Contract violation stays on same node and records error
        assert any("Contract violations" in str(e) for e in state.get("errors", []))

    def test_fallback_produces_warning_unmatched_condition(
        self, runner_env: Path, monkeypatch, capsys
    ) -> None:
        """Test that invalid transition condition triggers contract violation."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            "STATUS: success\nTRANSITION: nonexistent_condition",
            "",
        )
        mock_proc.returncode = 0
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            runner.main(
                [
                    "--goal",
                    "test unmatched warning",
                    "--ai-command",
                    "echo hi",
                    "--max-iterations",
                    "1",
                ]
            )

        captured = capsys.readouterr()
        assert "[CONTRACT VIOLATION]" in captured.err
        assert "nonexistent_condition" in captured.err

    def test_resume_resets_node_visits(self, runner_env: Path, monkeypatch) -> None:
        """Test that --resume resets node_visits to empty dict."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        # Set up state with stale node_visits
        state_file = runner_env / "kernel" / "state.yaml"
        state_data = {
            "current_node": "plan",
            "iteration_count": 5,
            "max_iterations": 30,
            "goal": "existing goal",
            "status": "running",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "coding"},
            "node_visits": {"init": 3, "plan": 4},
        }
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        state = runner.main(
            [
                "--goal",
                "resume goal",
                "--resume",
                "--dry-run",
                "--max-iterations",
                "1",
            ]
        )

        # node_visits should have been reset at the start of resume
        # Only new visits from this session should be counted
        # Since we ran 1 iteration starting from "plan", we should see
        # only 1 visit to whatever the next node was
        assert (
            "init" not in state.get("node_visits", {}) or state["node_visits"].get("init", 0) == 0
        )
        # Previous stale counts of 3 and 4 should not persist
        assert state.get("node_visits", {}).get("plan", 0) < 4

    def test_nonzero_returncode_handling(self, runner_env: Path, monkeypatch, capsys) -> None:
        """Test that non-zero returncode from AI command is handled as error."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("TRANSITION: goal_loaded", "Error: API rate limited")
        mock_proc.returncode = 1
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main(
                [
                    "--goal",
                    "test returncode",
                    "--ai-command",
                    "claude --print",
                    "--max-iterations",
                    "2",
                    "--complexity",
                    "high",
                ]
            )

        captured = capsys.readouterr()
        # Should log error to stderr
        assert "[ERROR] AI command exited with code 1" in captured.err
        assert "API rate limited" in captured.err
        # Should record error in state
        assert any("exited with code 1" in e for e in state.get("errors", []))
        # Should NOT have advanced the node (stdout should not be parsed)
        assert state["current_node"] == "init"

    def test_progress_history_populated_on_success(self, runner_env: Path, monkeypatch) -> None:
        """Test that progress_history is populated after successful Mode 3 iterations."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        # Create tasks.yaml with some tasks
        memory_dir = runner_env / "memory"
        tasks_data = {
            "tasks": [
                {"id": "T-001", "title": "Task 1", "status": "done", "dependencies": []},
                {"id": "T-002", "title": "Task 2", "status": "pending", "dependencies": []},
            ]
        }
        with open(memory_dir / "tasks.yaml", "w") as f:
            yaml.safe_dump(tasks_data, f)

        call_count = [0]

        def mock_popen(*args, **kwargs):
            call_count[0] += 1
            proc = MagicMock()
            proc.kill.return_value = None
            proc.terminate.return_value = None
            if call_count[0] == 1:
                proc.communicate.return_value = ("STATUS: success\nTRANSITION: goal_loaded", "")
                proc.returncode = 0
            elif call_count[0] == 2:
                proc.communicate.return_value = ("STATUS: success\nTRANSITION: plan_ready", "")
                proc.returncode = 0
            else:
                proc.communicate.return_value = ("STATUS: success\nTRANSITION: done", "")
                proc.returncode = 0
            return proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            state = runner.main(
                [
                    "--goal",
                    "test progress history",
                    "--ai-command",
                    "echo hi",
                    "--max-iterations",
                    "5",
                ]
            )

        # progress_history should contain entries (1 task done per iteration)
        assert "progress_history" in state
        assert len(state["progress_history"]) > 0
        assert all(isinstance(v, int) for v in state["progress_history"])

    def test_progress_history_capped_at_20(self, runner_env: Path, monkeypatch) -> None:
        """Test that progress_history is capped at 20 entries."""
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        # Create tasks.yaml with some tasks
        memory_dir = runner_env / "memory"
        tasks_data = {
            "tasks": [
                {"id": "T-001", "title": "Task 1", "status": "done", "dependencies": []},
                {"id": "T-002", "title": "Task 2", "status": "pending", "dependencies": []},
            ]
        }
        with open(memory_dir / "tasks.yaml", "w") as f:
            yaml.safe_dump(tasks_data, f)

        # Pre-seed progress_history with 19 entries
        state_file = runner_env / "kernel" / "state.yaml"
        state_data = yaml.safe_load(state_file.read_text())
        state_data["progress_history"] = list(range(19))
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        call_count = [0]

        def mock_popen(*args, **kwargs):
            call_count[0] += 1
            proc = MagicMock()
            proc.kill.return_value = None
            proc.terminate.return_value = None
            if call_count[0] == 1:
                proc.communicate.return_value = ("STATUS: success\nTRANSITION: goal_loaded", "")
                proc.returncode = 0
            elif call_count[0] == 2:
                proc.communicate.return_value = ("STATUS: success\nTRANSITION: plan_ready", "")
                proc.returncode = 0
            else:
                proc.communicate.return_value = ("STATUS: success\nTRANSITION: done", "")
                proc.returncode = 0
            return proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            state = runner.main(
                [
                    "--goal",
                    "test cap",
                    "--ai-command",
                    "echo hi",
                    "--max-iterations",
                    "5",
                ]
            )

        # progress_history should not exceed 20 entries
        assert len(state.get("progress_history", [])) <= 20

    def test_assessment_skipped_on_resume_with_existing_file(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test that capability assessment is skipped on --resume when assessment.yaml exists."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        # Create pre-existing assessment.yaml
        memory_dir = runner_env / "memory"
        existing_assessment = {
            "goal": "previous goal",
            "confidence": 0.8,
            "covered_skills": ["skill-a"],
            "skill_gaps": [],
            "suggestions": [],
            "timestamp": "2025-01-01T00:00:00+00:00",
        }
        with open(memory_dir / "assessment.yaml", "w") as f:
            yaml.safe_dump(existing_assessment, f)

        # Set up pre-existing state with a goal
        state_file = runner_env / "kernel" / "state.yaml"
        state_data = yaml.safe_load(state_file.read_text())
        state_data["goal"] = "previous goal"
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        runner.main(
            [
                "--goal",
                "previous goal",
                "--resume",
                "--max-iterations",
                "1",
            ]
        )

        # The existing assessment.yaml should NOT have been overwritten
        with open(memory_dir / "assessment.yaml") as f:
            saved = yaml.safe_load(f)
        assert saved["goal"] == "previous goal"
        assert saved["confidence"] == 0.8
        assert saved["timestamp"] == "2025-01-01T00:00:00+00:00"

    def test_assessment_runs_on_fresh_start(self, runner_env: Path, monkeypatch) -> None:
        """Test that capability assessment runs on fresh start (no --resume)."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        memory_dir = runner_env / "memory"
        # Ensure no assessment.yaml exists
        assessment_path = memory_dir / "assessment.yaml"
        if assessment_path.exists():
            assessment_path.unlink()

        runner.main(
            [
                "--goal",
                "test fresh assessment",
                "--max-iterations",
                "1",
            ]
        )

        # assessment.yaml should have been created
        assert assessment_path.exists()
        with open(assessment_path) as f:
            saved = yaml.safe_load(f)
        assert saved["goal"] == "test fresh assessment"


class TestNoGoalErrorMessage:
    """Tests for the no-goal error message including usage hint."""

    def test_no_goal_error_includes_usage_hint(self, capsys) -> None:
        """Test that running without --goal shows a usage hint."""
        with pytest.raises(SystemExit) as exc_info:
            runner.main([])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "usage:" in captured.err
        assert "--goal" in captured.err

    def test_empty_goal_error_includes_usage_hint(self, capsys) -> None:
        """Test that --goal '' shows the same usage hint."""
        with pytest.raises(SystemExit) as exc_info:
            runner.main(["--goal", ""])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "usage:" in captured.err
        assert "--goal" in captured.err


class TestMaxIterationsValidation:
    """Tests for --max-iterations input validation."""

    def test_negative_max_iterations_rejected(self, capsys) -> None:
        """Test that --max-iterations -1 produces an error."""
        with pytest.raises(SystemExit) as exc_info:
            runner.main(["--goal", "test", "--max-iterations", "-1"])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "positive integer" in captured.err

    def test_zero_max_iterations_rejected(self, capsys) -> None:
        """Test that --max-iterations 0 produces an error."""
        with pytest.raises(SystemExit) as exc_info:
            runner.main(["--goal", "test", "--max-iterations", "0"])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "positive integer" in captured.err

    def test_valid_max_iterations_accepted(self) -> None:
        """Test that --max-iterations 1 is accepted."""
        state = runner.main(["--goal", "test", "--max-iterations", "1", "--dry-run"])
        assert state["max_iterations"] == 1
