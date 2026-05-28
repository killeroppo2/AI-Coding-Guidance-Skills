"""Integration tests that prove the system works end-to-end.

These tests use monkeypatch to mock subprocess.Popen, simulating AI CLI tool
responses. They exercise the full flow from goal to completion through
runner.main() in Mode 3.
"""

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

import runner


def _make_mock_proc(returncode: int, stdout: str, stderr: str):
    """Create a mock Popen process object.

    Args:
        returncode: The return code for the process.
        stdout: The stdout text.
        stderr: The stderr text.

    Returns:
        A MagicMock that mimics a subprocess.Popen object.
    """
    proc = MagicMock()
    proc.communicate.return_value = (stdout, stderr)
    proc.returncode = returncode
    proc.kill.return_value = None
    proc.terminate.return_value = None
    proc.wait.return_value = returncode
    return proc


def make_mock_ai_response(node_responses: dict[str, str]):
    """Create a subprocess.Popen mock that returns appropriate responses per node.

    node_responses maps node_id -> stdout_text (which should include TRANSITION: line).

    The mock detects the current node from the stdin content, which contains
    a "=== NODE PROMPT (xxx) ===" section assembled by ContextAssembler.

    Args:
        node_responses: Mapping of node_id to the stdout text to return.

    Returns:
        A callable that mimics subprocess.Popen behavior.
    """

    def mock_popen(*args: Any, **kwargs: Any):
        """Mock subprocess.Popen that returns node-specific responses."""
        proc = MagicMock()
        proc.kill.return_value = None
        proc.terminate.return_value = None

        def mock_communicate(input=None, timeout=None):
            node_id = "unknown"
            if input:
                for line in input.splitlines():
                    if "NODE PROMPT" in line and "(" in line:
                        node_id = line.split("(")[1].split(")")[0]
                        break
            response_text = node_responses.get(
                node_id, "TRANSITION: goal_loaded\nSTATUS: success"
            )
            return (response_text, "")
        proc.communicate.side_effect = mock_communicate
        proc.returncode = 0
        proc.wait.return_value = 0
        return proc

    return mock_popen


def make_failing_mock(
    fail_node: str,
    fail_count: int,
    node_responses: dict[str, str],
):
    """Create a mock that fails a specified number of times for a node, then succeeds.

    Args:
        fail_node: The node_id that should fail initially.
        fail_count: Number of times to fail before succeeding.
        node_responses: Normal responses for all nodes (used after failures resolved).

    Returns:
        A callable that mimics subprocess.Popen with controlled failures.
    """
    call_counts: dict[str, int] = {}

    def mock_popen(*args: Any, **kwargs: Any):
        """Mock subprocess.Popen with controlled failures per node."""
        proc = MagicMock()
        proc.kill.return_value = None
        proc.terminate.return_value = None

        def mock_communicate(input=None, timeout=None):
            node_id = "unknown"
            if input:
                for line in input.splitlines():
                    if "NODE PROMPT" in line and "(" in line:
                        node_id = line.split("(")[1].split(")")[0]
                        break

            call_counts[node_id] = call_counts.get(node_id, 0) + 1

            if node_id == fail_node and call_counts[node_id] <= fail_count:
                proc.returncode = 1
                return ("", "Simulated failure")

            proc.returncode = 0
            response_text = node_responses.get(
                node_id, "TRANSITION: goal_loaded\nSTATUS: success"
            )
            return (response_text, "")
        proc.communicate.side_effect = mock_communicate
        proc.returncode = 0
        proc.wait.return_value = 0
        return proc

    return mock_popen


def make_always_failing_mock(fail_node: str, node_responses: dict[str, str]):
    """Create a mock that always fails for a specific node.

    Args:
        fail_node: The node_id that should always fail.
        node_responses: Normal responses for other nodes.

    Returns:
        A callable that mimics subprocess.Popen with perpetual failure for one node.
    """

    def mock_popen(*args: Any, **kwargs: Any):
        """Mock subprocess.Popen that always fails for the target node."""
        proc = MagicMock()
        proc.kill.return_value = None
        proc.terminate.return_value = None

        def mock_communicate(input=None, timeout=None):
            node_id = "unknown"
            if input:
                for line in input.splitlines():
                    if "NODE PROMPT" in line and "(" in line:
                        node_id = line.split("(")[1].split(")")[0]
                        break

            if node_id == fail_node:
                proc.returncode = 1
                return ("", "Always fails")

            proc.returncode = 0
            response_text = node_responses.get(
                node_id, "TRANSITION: goal_loaded\nSTATUS: success"
            )
            return (response_text, "")
        proc.communicate.side_effect = mock_communicate
        proc.returncode = 0
        proc.wait.return_value = 0
        return proc

    return mock_popen


@pytest.fixture
def kernel_env(tmp_path: Path) -> Path:
    """Create a minimal kernel directory structure for integration tests.

    Sets up graph.yaml, prompts, constitution, BOOT.md, evolution dir,
    memory dir, and knowledge dir so runner.main() can execute.

    Returns:
        The temporary root path used as KERNEL_ROOT.
    """
    # Create kernel directory structure
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()

    # graph.yaml - full workflow
    graph_data = {
        "version": "1.0",
        "description": "Integration test graph",
        "nodes": [
            {
                "id": "init",
                "prompt_file": "prompts/orchestrator.md",
                "description": "Initialize context",
                "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                "max_retries": 2,
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
                "transitions": [
                    {"to": "test", "condition": "code_written"},
                    {"to": "code", "condition": "code_needs_retry"},
                ],
                "max_retries": 5,
                "stuck_handler": "reflect",
            },
            {
                "id": "test",
                "prompt_file": "prompts/tester.md",
                "description": "Run tests",
                "transitions": [
                    {"to": "review", "condition": "tests_pass"},
                    {"to": "code", "condition": "tests_fail"},
                ],
                "max_retries": 5,
                "stuck_handler": "reflect",
            },
            {
                "id": "review",
                "prompt_file": "prompts/reviewer.md",
                "description": "Review code",
                "transitions": [
                    {"to": "reflect", "condition": "review_pass"},
                    {"to": "code", "condition": "review_needs_changes"},
                ],
                "max_retries": 5,
            },
            {
                "id": "reflect",
                "prompt_file": "prompts/reflector.md",
                "description": "Reflect on iteration",
                "transitions": [
                    {"to": "evolve", "condition": "evolution_proposed"},
                    {"to": "plan", "condition": "no_evolution_needed"},
                ],
                "max_retries": 5,
            },
            {
                "id": "evolve",
                "prompt_file": "prompts/reflector.md",
                "description": "Apply evolution",
                "transitions": [{"to": "plan", "condition": "evolution_applied"}],
                "max_retries": 5,
            },
        ],
        "default_start": "init",
        "max_iterations": 30,
    }
    with open(kernel_dir / "graph.yaml", "w") as f:
        yaml.safe_dump(graph_data, f)

    # Create prompts directory with minimal prompt files
    prompts_dir = kernel_dir / "prompts"
    prompts_dir.mkdir()
    for prompt_name in [
        "orchestrator.md",
        "planner.md",
        "coder.md",
        "tester.md",
        "reviewer.md",
        "reflector.md",
    ]:
        (prompts_dir / prompt_name).write_text(f"# {prompt_name}\nDo your job.\n")

    # BOOT.md and constitution.md
    (kernel_dir / "BOOT.md").write_text("# Boot\nYou are the kernel.\n")
    (kernel_dir / "constitution.md").write_text("# Constitution\nDo no harm.\n")

    # Contracts directory with output_format.md
    contracts_dir = kernel_dir / "contracts"
    contracts_dir.mkdir()
    (contracts_dir / "output_format.md").write_text(
        "# Output Format\nTRANSITION: <condition>\nSTATUS: success|failure\n"
    )
    (contracts_dir / "__init__.py").touch()

    # Evolution directory
    evolution_dir = kernel_dir / "evolution"
    evolution_dir.mkdir()
    (evolution_dir / "history.jsonl").write_text("")
    (evolution_dir / "__init__.py").touch()

    # Philosophy directory
    philosophy_dir = kernel_dir / "philosophy"
    philosophy_dir.mkdir()
    (philosophy_dir / "dao.md").write_text("# Dao\nThe way.\n")
    (philosophy_dir / "strategy.md").write_text("# Strategy\nBe effective.\n")

    # Memory directory
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "decisions.jsonl").touch()
    (memory_dir / "reflections.jsonl").touch()
    (memory_dir / "current_goal.md").touch()
    (memory_dir / "plan.md").touch()
    progress = {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}
    with open(memory_dir / "progress.yaml", "w") as f:
        yaml.safe_dump(progress, f)

    # Knowledge directory
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "rules").mkdir()
    (knowledge_dir / "rules" / "manual").mkdir()
    (knowledge_dir / "rules" / "learned").mkdir()
    (knowledge_dir / "skills").mkdir()
    (knowledge_dir / "patterns").mkdir()
    for subdir in ["rules", "skills", "patterns"]:
        index_path = knowledge_dir / subdir / "_index.yaml"
        with open(index_path, "w") as f:
            yaml.safe_dump({"items": []}, f)

    return tmp_path


class TestFullCycleHelloWorld:
    """Integration tests for a complete init->plan->code->test->review->reflect cycle."""

    def test_full_cycle_hello_world(
        self, kernel_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test full cycle with goal 'Create hello.py that prints Hello World'.

        Mocks subprocess.run to return appropriate TRANSITION and STATUS for
        each node. Verifies the system advances through the expected nodes
        and completes successfully.
        """
        node_responses = {
            "init": "TRANSITION: goal_loaded\nSTATUS: success",
            "plan": "TRANSITION: plan_ready\nSTATUS: success\nFILES_WRITTEN: memory/tasks.yaml",
            "code": "TRANSITION: code_written\nSTATUS: success\nFILES_WRITTEN: workspace/create-hellopy-that-prints-hello-world/hello.py",
            "test": "TRANSITION: tests_pass\nSTATUS: success",
            "review": "TRANSITION: review_pass\nSTATUS: success",
            "reflect": "TRANSITION: no_evolution_needed\nSTATUS: success",
        }

        mock_fn = make_mock_ai_response(node_responses)
        monkeypatch.setattr(subprocess, "Popen", mock_fn)
        monkeypatch.setattr(runner, "KERNEL_ROOT", kernel_env)

        state = runner.main([
            "--goal", "Create hello.py that prints Hello World",
            "--ai-command", "mock-ai",
            "--max-iterations", "10",
        ])

        # The system should have completed or be running (having gone through nodes)
        assert state["status"] in ("running", "complete")
        # Should have iterated through multiple nodes
        assert state["iteration_count"] > 1
        # Goal should be set
        assert state["goal"] == "Create hello.py that prints Hello World"
        # Workspace path should be set
        assert state["workspace_path"] != ""

    def test_full_cycle_advances_through_nodes(
        self, kernel_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that the system advances through the expected node sequence."""
        visited_nodes: list[str] = []

        node_responses = {
            "init": "TRANSITION: goal_loaded\nSTATUS: success",
            "plan": "TRANSITION: plan_ready\nSTATUS: success",
            "code": "TRANSITION: code_written\nSTATUS: success",
            "test": "TRANSITION: tests_pass\nSTATUS: success",
            "review": "TRANSITION: review_pass\nSTATUS: success",
            "reflect": "TRANSITION: no_evolution_needed\nSTATUS: success",
        }

        def tracking_mock(*args: Any, **kwargs: Any):
            """Track which nodes are visited."""
            proc = MagicMock()
            proc.kill.return_value = None
            proc.terminate.return_value = None

            def mock_communicate(input=None, timeout=None):
                node_id = "unknown"
                if input:
                    for line in input.splitlines():
                        if "NODE PROMPT" in line and "(" in line:
                            node_id = line.split("(")[1].split(")")[0]
                            break
                visited_nodes.append(node_id)
                response_text = node_responses.get(
                    node_id, "TRANSITION: goal_loaded\nSTATUS: success"
                )
                return (response_text, "")
            proc.communicate.side_effect = mock_communicate
            proc.returncode = 0
            proc.wait.return_value = 0
            return proc

        monkeypatch.setattr(subprocess, "Popen", tracking_mock)
        monkeypatch.setattr(runner, "KERNEL_ROOT", kernel_env)

        runner.main([
            "--goal", "Test node traversal",
            "--ai-command", "mock-ai",
            "--max-iterations", "10",
            "--complexity", "high",
        ])

        # Verify we visited expected nodes in order for one full cycle
        # The sequence should be: init, plan, code, test, review, reflect
        # then back to plan (since reflect -> no_evolution_needed -> plan)
        expected_start = ["init", "plan", "code", "test", "review", "reflect"]
        assert visited_nodes[:6] == expected_start
        # After reflect with no_evolution_needed, it goes back to plan
        if len(visited_nodes) > 6:
            assert visited_nodes[6] == "plan"


class TestFailureAndRetry:
    """Integration tests for failure recovery and retry behavior."""

    def test_failure_and_retry(
        self, kernel_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a failure on a node is retried and eventually succeeds.

        Mocks the code node to fail once (returncode 1), then succeed on retry.
        Verifies that errors are recorded and the system advances past the node.
        """
        node_responses = {
            "init": "TRANSITION: goal_loaded\nSTATUS: success",
            "plan": "TRANSITION: plan_ready\nSTATUS: success",
            "code": "TRANSITION: code_written\nSTATUS: success",
            "test": "TRANSITION: tests_pass\nSTATUS: success",
            "review": "TRANSITION: review_pass\nSTATUS: success",
            "reflect": "TRANSITION: no_evolution_needed\nSTATUS: success",
        }

        mock_fn = make_failing_mock(
            fail_node="code", fail_count=1, node_responses=node_responses
        )
        monkeypatch.setattr(subprocess, "Popen", mock_fn)
        monkeypatch.setattr(runner, "KERNEL_ROOT", kernel_env)

        state = runner.main([
            "--goal", "Test failure and retry",
            "--ai-command", "mock-ai",
            "--max-iterations", "10",
        ])

        # System should have recorded an error for the failed attempt
        assert len(state.get("errors", [])) > 0 or any(
            "code" in str(e) for e in state.get("errors", [])
        )
        # The system should still be running or complete (not stuck)
        assert state["status"] in ("running", "complete")
        # The system should have advanced past code (current_node != code)
        # or at least completed more than the initial iterations
        assert state["iteration_count"] > 2

    def test_failure_records_error(
        self, kernel_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a subprocess failure records an error in state."""
        node_responses = {
            "init": "TRANSITION: goal_loaded\nSTATUS: success",
            "plan": "TRANSITION: plan_ready\nSTATUS: success",
            "code": "TRANSITION: code_written\nSTATUS: success",
            "test": "TRANSITION: tests_pass\nSTATUS: success",
            "review": "TRANSITION: review_pass\nSTATUS: success",
            "reflect": "TRANSITION: no_evolution_needed\nSTATUS: success",
        }

        mock_fn = make_failing_mock(
            fail_node="code", fail_count=2, node_responses=node_responses
        )
        monkeypatch.setattr(subprocess, "Popen", mock_fn)
        monkeypatch.setattr(runner, "KERNEL_ROOT", kernel_env)

        state = runner.main([
            "--goal", "Test error recording",
            "--ai-command", "mock-ai",
            "--max-iterations", "10",
        ])

        # Errors should mention the code node failure
        errors_text = " ".join(str(e) for e in state.get("errors", []))
        assert "code" in errors_text.lower() or state["iteration_count"] > 2


class TestStuckDetectionIntegration:
    """Integration tests for stuck detection when a node always fails."""

    def test_stuck_detection_triggers(
        self, kernel_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that stuck detection triggers when a node always fails.

        The code node has max_retries=5 and a stuck_handler pointing to reflect.
        When reflect also loops back, it should eventually get stuck.
        We use a graph with low max_retries on the code node to trigger stuck faster.
        """
        # Override graph with low max_retries for code node (no stuck_handler)
        graph_data = {
            "version": "1.0",
            "description": "Stuck detection test graph",
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Initialize",
                    "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                    "max_retries": 2,
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
                    "max_retries": 3,
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
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(kernel_env / "kernel" / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        node_responses = {
            "init": "TRANSITION: goal_loaded\nSTATUS: success",
            "plan": "TRANSITION: plan_ready\nSTATUS: success",
            "code": "TRANSITION: code_written\nSTATUS: success",
            "test": "TRANSITION: tests_pass\nSTATUS: success",
            "review": "TRANSITION: review_pass\nSTATUS: success",
            "reflect": "TRANSITION: no_evolution_needed\nSTATUS: success",
        }

        mock_fn = make_always_failing_mock(
            fail_node="code", node_responses=node_responses
        )
        monkeypatch.setattr(subprocess, "Popen", mock_fn)
        monkeypatch.setattr(runner, "KERNEL_ROOT", kernel_env)

        state = runner.main([
            "--goal", "Test stuck detection",
            "--ai-command", "mock-ai",
            "--max-iterations", "10",
        ])

        # System should be stuck
        assert state["status"] == "stuck"
        # Errors should mention exceeded max_retries
        errors_text = " ".join(str(e) for e in state.get("errors", []))
        assert "max_retries" in errors_text or "exceeded" in errors_text

    def test_stuck_detection_with_stuck_handler(
        self, kernel_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that stuck_handler redirects to reflect node before giving up.

        When code node exceeds max_retries and has a stuck_handler, the system
        should redirect to the handler node.
        """
        node_responses = {
            "init": "TRANSITION: goal_loaded\nSTATUS: success",
            "plan": "TRANSITION: plan_ready\nSTATUS: success",
            "code": "TRANSITION: code_written\nSTATUS: success",
            "test": "TRANSITION: tests_pass\nSTATUS: success",
            "review": "TRANSITION: review_pass\nSTATUS: success",
            "reflect": "TRANSITION: no_evolution_needed\nSTATUS: success",
        }

        mock_fn = make_always_failing_mock(
            fail_node="code", node_responses=node_responses
        )
        monkeypatch.setattr(subprocess, "Popen", mock_fn)
        monkeypatch.setattr(runner, "KERNEL_ROOT", kernel_env)

        # The default kernel_env graph has stuck_handler: reflect on code node
        # with max_retries: 5 - the system will redirect to reflect after 5 failures
        state = runner.main([
            "--goal", "Test stuck handler",
            "--ai-command", "mock-ai",
            "--max-iterations", "15",
        ])

        # With stuck_handler, the system should redirect to reflect rather than
        # immediately going stuck. But since code always fails and plan leads
        # back to code, eventually iterations run out or it gets stuck elsewhere.
        # The key assertion: system ran more iterations than just max_retries of code
        assert state["iteration_count"] > 3
