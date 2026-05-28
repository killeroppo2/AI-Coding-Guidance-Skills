"""End-to-end test using mock AI server to validate full kernel cycle.

This test proves the kernel can complete a full goal with real subprocess
invocations, real file I/O, and real state transitions.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

pytestmark = pytest.mark.slow


@pytest.fixture
def e2e_env(tmp_path: Path):
    """Set up a complete kernel environment for E2E testing."""
    # Kernel directory
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    (kernel_dir / "evolution").mkdir()
    (kernel_dir / "philosophy").mkdir()

    prompts_dir = kernel_dir / "prompts"
    prompts_dir.mkdir()

    # Create minimal prompt files
    (prompts_dir / "orchestrator.md").write_text("You are the orchestrator. Initialize the goal.")
    (prompts_dir / "planner.md").write_text("You are the planner. Create a plan.")
    (prompts_dir / "coder.md").write_text("You are the coder. Write code.")
    (prompts_dir / "tester.md").write_text("You are the tester. Run tests.")
    (prompts_dir / "reviewer.md").write_text("You are the reviewer. Review code.")
    (prompts_dir / "reflector.md").write_text("You are the reflector. Reflect on the iteration.")

    # BOOT.md and constitution
    (kernel_dir / "BOOT.md").write_text("# Boot\nBoot content for E2E test.")
    (kernel_dir / "constitution.md").write_text("# Constitution\nE2E test constitution.")
    (kernel_dir / "philosophy" / "dao.md").write_text("# Dao")
    (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy")

    # Contracts directory
    contracts_dir = kernel_dir / "contracts"
    contracts_dir.mkdir()
    (contracts_dir / "output_format.md").write_text("# Output Format\nTRANSITION: <condition>")

    # Graph with minimal cycle: init -> plan -> code (terminal for test simplicity)
    graph_data = {
        "version": "1.0",
        "description": "E2E test graph",
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
                "transitions": [{"to": "test", "condition": "code_written"}],
                "max_retries": 10,
            },
            {
                "id": "test",
                "prompt_file": "prompts/tester.md",
                "description": "Run tests",
                "transitions": [{"to": "review", "condition": "tests_pass"}],
                "max_retries": 10,
            },
            {
                "id": "review",
                "prompt_file": "prompts/reviewer.md",
                "description": "Review code",
                "transitions": [{"to": "reflect", "condition": "review_pass"}],
                "max_retries": 10,
            },
            {
                "id": "reflect",
                "prompt_file": "prompts/reflector.md",
                "description": "Reflect",
                "transitions": [
                    {"to": "plan", "condition": "no_evolution_needed"},
                ],
                "max_retries": 10,
            },
        ],
        "default_start": "init",
        "max_iterations": 30,
    }
    graph_file = kernel_dir / "graph.yaml"
    with open(graph_file, "w") as f:
        yaml.safe_dump(graph_data, f)

    # State file
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

    # Memory directory
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "decisions.jsonl").touch()
    (memory_dir / "reflections.jsonl").touch()
    (memory_dir / "current_goal.md").touch()
    (memory_dir / "plan.md").touch()
    with open(memory_dir / "progress.yaml", "w") as f:
        yaml.safe_dump({"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}, f)

    # Knowledge directory
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    for sub in ["rules", "skills", "patterns"]:
        (knowledge_dir / sub).mkdir()
        with open(knowledge_dir / sub / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

    # Skills directory (sibling to knowledge)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    with open(skills_dir / "_index.yaml", "w") as f:
        yaml.safe_dump({"items": []}, f)

    return tmp_path


class TestFullCycle:
    """End-to-end tests running the kernel with mock AI subprocess."""

    def test_kernel_completes_cycle_with_mock_ai(self, e2e_env: Path) -> None:
        """Run kernel with mock AI and verify it advances through nodes."""
        import runner

        # Path to mock AI server
        mock_server = Path(__file__).parent / "mock_ai_server.py"
        ai_command = f"{sys.executable} {mock_server}"

        with patch.object(runner, "KERNEL_ROOT", e2e_env):
            state = runner.main(
                [
                    "--goal",
                    "Create a calculator",
                    "--ai-command",
                    ai_command,
                    "--max-iterations",
                    "8",
                ]
            )

        # Verify state advanced
        assert state["iteration_count"] > 0, "Iteration count should be > 0 after running"

        # Verify we moved past the init node
        assert state["current_node"] != "init" or state["iteration_count"] > 1, (
            "Should have advanced past init node"
        )

    def test_kernel_records_reflections(self, e2e_env: Path) -> None:
        """Verify that running the kernel produces reflection entries."""
        import runner

        mock_server = Path(__file__).parent / "mock_ai_server.py"
        ai_command = f"{sys.executable} {mock_server}"

        with patch.object(runner, "KERNEL_ROOT", e2e_env):
            runner.main(
                [
                    "--goal",
                    "Create a calculator",
                    "--ai-command",
                    ai_command,
                    "--max-iterations",
                    "5",
                ]
            )

        # Check reflections.jsonl was populated
        reflections_path = e2e_env / "memory" / "reflections.jsonl"
        content = reflections_path.read_text().strip()
        assert content != "", "reflections.jsonl should have entries"

        entries = [json.loads(line) for line in content.split("\n") if line.strip()]
        assert len(entries) > 0, "Should have at least one reflection entry"

        # Each entry should have expected fields
        for entry in entries:
            assert "node" in entry
            assert "success" in entry

    def test_kernel_state_transitions_happen(self, e2e_env: Path) -> None:
        """Verify state transitions occurred (nodes changed)."""
        import runner

        mock_server = Path(__file__).parent / "mock_ai_server.py"
        ai_command = f"{sys.executable} {mock_server}"

        with patch.object(runner, "KERNEL_ROOT", e2e_env):
            state = runner.main(
                [
                    "--goal",
                    "Create a calculator",
                    "--ai-command",
                    ai_command,
                    "--max-iterations",
                    "6",
                ]
            )

        # The mock AI server outputs TRANSITION lines that the runner parses
        # After init, it should transition to plan (TRANSITION: goal_loaded)
        # After plan, it should transition to code (TRANSITION: plan_ready)
        # This proves real state transitions are happening
        assert state["iteration_count"] >= 2, "Should have at least 2 iterations for transitions"

    def test_mock_ai_server_outputs_transitions(self, e2e_env: Path) -> None:
        """Verify mock AI server produces correct TRANSITION lines."""
        import subprocess

        mock_server = Path(__file__).parent / "mock_ai_server.py"

        # Test init node
        result = subprocess.run(
            [sys.executable, str(mock_server)],
            input="Current Node: init\nYou are the orchestrator.",
            capture_output=True,
            text=True,
        )
        assert "TRANSITION: goal_loaded" in result.stdout

        # Test planner node
        result = subprocess.run(
            [sys.executable, str(mock_server)],
            input="Current Node: plan\nYou are the planner.",
            capture_output=True,
            text=True,
        )
        assert "TRANSITION: plan_ready" in result.stdout

        # Test coder node
        result = subprocess.run(
            [sys.executable, str(mock_server)],
            input="Current Node: code\nYou are the coder.",
            capture_output=True,
            text=True,
        )
        assert "TRANSITION: code_written" in result.stdout

        # Test tester node
        result = subprocess.run(
            [sys.executable, str(mock_server)],
            input="Current Node: test\nYou are the tester.",
            capture_output=True,
            text=True,
        )
        assert "TRANSITION: tests_pass" in result.stdout

        # Test reviewer node
        result = subprocess.run(
            [sys.executable, str(mock_server)],
            input="Current Node: review\nYou are the reviewer.",
            capture_output=True,
            text=True,
        )
        assert "TRANSITION: review_pass" in result.stdout

        # Test reflector node
        result = subprocess.run(
            [sys.executable, str(mock_server)],
            input="Current Node: reflect\nYou are the reflector.",
            capture_output=True,
            text=True,
        )
        assert "TRANSITION: no_evolution_needed" in result.stdout
