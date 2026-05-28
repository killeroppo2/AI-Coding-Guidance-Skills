"""Tests for P0: Lightweight Retry in runner.py Mode 3."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

import runner


class TestLightweightRetry:
    """Tests for the lightweight retry mechanism in Mode 3."""

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
                    "transitions": [
                        {"to": "plan", "condition": "goal_loaded"},
                    ],
                    "max_retries": 5,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/planner.md",
                    "description": "Plan tasks",
                    "transitions": [
                        {"to": "code", "condition": "plan_ready"},
                        {"to": "plan", "condition": "plan_needs_revision"},
                    ],
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
        (kernel_dir / "philosophy" / "strategy.md").write_text(
            "# Strategy\nStrategy content."
        )

        # contracts dir with output_format.md
        (kernel_dir / "contracts").mkdir()
        (kernel_dir / "contracts" / "output_format.md").write_text(
            "# Output Format\nSTATUS: success|failure\nTRANSITION: <condition>"
        )

        # evolution dir
        (kernel_dir / "evolution").mkdir()
        (kernel_dir / "evolution" / "history.jsonl").touch()

        # memory dir
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

        # knowledge dir
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_lightweight_prompt_built_correctly(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test that the lightweight prompt contains correct node_id and transitions."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        call_count = [0]
        prompts_received = []

        def mock_popen(*args, **kwargs):
            call_count[0] += 1
            mock_proc = MagicMock()
            if call_count[0] == 1:
                # First call: missing TRANSITION and STATUS
                mock_proc.communicate.return_value = (
                    "Some output without format lines",
                    "",
                )
            else:
                # Second call (lightweight retry): provide valid output
                mock_proc.communicate.return_value = (
                    "STATUS: success\nTRANSITION: goal_loaded",
                    "",
                )
            mock_proc.returncode = 0
            # Capture stdin input
            original_communicate = mock_proc.communicate

            def capture_communicate(*a, **kw):
                if "input" in kw:
                    prompts_received.append(kw["input"])
                elif a:
                    prompts_received.append(a[0] if a[0] else "")
                return original_communicate(*a, **kw)

            mock_proc.communicate = capture_communicate
            return mock_proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            state = runner.main([
                "--goal", "test lightweight",
                "--ai-command", "echo hello",
                "--max-iterations", "2",
                "--complexity", "high",
            ])

        # Should have 2 calls
        assert call_count[0] == 2
        # Second prompt should be lightweight
        assert len(prompts_received) == 2
        lightweight_prompt = prompts_received[1]
        assert "missing required format lines" in lightweight_prompt
        assert "Current node: init" in lightweight_prompt
        assert "goal_loaded" in lightweight_prompt
        # Should advance to plan after successful retry
        assert state["current_node"] == "plan"

    def test_format_violation_triggers_lightweight_retry(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test that after a format violation, the next iteration uses lightweight prompt."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        call_count = [0]
        prompts_received = []

        def mock_popen(*args, **kwargs):
            call_count[0] += 1
            mock_proc = MagicMock()
            if call_count[0] == 1:
                # First call: missing STATUS line
                mock_proc.communicate.return_value = (
                    "TRANSITION: goal_loaded\nSome other stuff",
                    "",
                )
            else:
                # Second call: correct output
                mock_proc.communicate.return_value = (
                    "STATUS: success\nTRANSITION: goal_loaded",
                    "",
                )
            mock_proc.returncode = 0

            original_communicate = mock_proc.communicate

            def capture_communicate(*a, **kw):
                if "input" in kw:
                    prompts_received.append(kw["input"])
                elif a:
                    prompts_received.append(a[0] if a[0] else "")
                return original_communicate(*a, **kw)

            mock_proc.communicate = capture_communicate
            return mock_proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            runner.main([
                "--goal", "test retry",
                "--ai-command", "echo hi",
                "--max-iterations", "2",
                "--complexity", "high",
            ])

        assert call_count[0] == 2
        # First prompt should be full context (has BOOT SEQUENCE or similar)
        assert "=== " in prompts_received[0] or "BOOT" in prompts_received[0]
        # Second prompt should be lightweight
        assert "missing required format lines" in prompts_received[1]

    def test_lightweight_retry_fails_then_full_context(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test that if lightweight retry also fails, third attempt uses full context."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        call_count = [0]
        prompts_received = []

        def mock_popen(*args, **kwargs):
            call_count[0] += 1
            mock_proc = MagicMock()
            if call_count[0] == 1:
                # First call: missing TRANSITION and STATUS
                mock_proc.communicate.return_value = (
                    "Some output without format lines",
                    "",
                )
            elif call_count[0] == 2:
                # Second call (lightweight retry): also missing format
                mock_proc.communicate.return_value = (
                    "Still no format lines here",
                    "",
                )
            else:
                # Third call: full context, provides correct output
                mock_proc.communicate.return_value = (
                    "STATUS: success\nTRANSITION: goal_loaded",
                    "",
                )
            mock_proc.returncode = 0

            original_communicate = mock_proc.communicate

            def capture_communicate(*a, **kw):
                if "input" in kw:
                    prompts_received.append(kw["input"])
                elif a:
                    prompts_received.append(a[0] if a[0] else "")
                return original_communicate(*a, **kw)

            mock_proc.communicate = capture_communicate
            return mock_proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            state = runner.main([
                "--goal", "test fallback",
                "--ai-command", "echo hi",
                "--max-iterations", "3",
                "--complexity", "high",
            ])

        assert call_count[0] == 3
        # First: full context
        assert "=== " in prompts_received[0] or "BOOT" in prompts_received[0]
        # Second: lightweight
        assert "missing required format lines" in prompts_received[1]
        # Third: back to full context (retry_lightweight was cleared)
        assert "=== " in prompts_received[2] or "BOOT" in prompts_received[2]
        # Should advance after third attempt
        assert state["current_node"] == "plan"

    def test_lightweight_prompt_has_valid_transitions_for_plan_node(
        self, runner_env: Path, monkeypatch
    ) -> None:
        """Test that lightweight prompt shows correct transitions for the plan node."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        # Set initial state to plan node
        state_file = runner_env / "kernel" / "state.yaml"
        state_data = yaml.safe_load(state_file.read_text())
        state_data["current_node"] = "plan"
        with open(state_file, "w") as f:
            yaml.safe_dump(state_data, f)

        call_count = [0]
        prompts_received = []

        def mock_popen(*args, **kwargs):
            call_count[0] += 1
            mock_proc = MagicMock()
            if call_count[0] == 1:
                # Missing format
                mock_proc.communicate.return_value = (
                    "No format output",
                    "",
                )
            else:
                mock_proc.communicate.return_value = (
                    "STATUS: success\nTRANSITION: plan_ready",
                    "",
                )
            mock_proc.returncode = 0

            original_communicate = mock_proc.communicate

            def capture_communicate(*a, **kw):
                if "input" in kw:
                    prompts_received.append(kw["input"])
                elif a:
                    prompts_received.append(a[0] if a[0] else "")
                return original_communicate(*a, **kw)

            mock_proc.communicate = capture_communicate
            return mock_proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            runner.main([
                "--goal", "test plan node",
                "--ai-command", "echo hi",
                "--max-iterations", "2",
                "--resume",
                "--complexity", "high",
            ])

        # Lightweight prompt for plan node should show plan_ready, plan_needs_revision
        assert len(prompts_received) >= 2
        lightweight_prompt = prompts_received[1]
        assert "Current node: plan" in lightweight_prompt
        assert "plan_ready" in lightweight_prompt
        assert "plan_needs_revision" in lightweight_prompt
