"""Tests that validate all example scenarios run successfully."""

import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"


class TestExamples:
    """Validate example scenarios execute correctly in dry-run mode."""

    def test_todo_app_example(self):
        """Todo app example runs successfully."""
        result = subprocess.run(
            [
                sys.executable,
                "runner.py",
                "--goal",
                "Build a Python Flask todo app with REST API and SQLite",
                "--dry-run",
                "--max-iterations",
                "10",
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "[DRY RUN]" in result.stdout

    def test_cli_tool_example(self):
        """CLI tool example runs successfully."""
        result = subprocess.run(
            [
                sys.executable,
                "runner.py",
                "--goal",
                "Build a CLI file organizer that sorts files by extension",
                "--dry-run",
                "--max-iterations",
                "10",
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "[DRY RUN]" in result.stdout

    def test_api_service_example(self):
        """API service example runs successfully."""
        result = subprocess.run(
            [
                sys.executable,
                "runner.py",
                "--goal",
                "Build a FastAPI microservice with JWT authentication",
                "--dry-run",
                "--max-iterations",
                "10",
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "[DRY RUN]" in result.stdout

    def test_validate_all_script_exists(self):
        """validate_all.sh exists and is executable."""
        script = EXAMPLES_DIR / "validate_all.sh"
        assert script.exists()
        # Check it's executable (has execute permission)
        import os

        assert os.access(script, os.X_OK)

    def test_todo_app_goal_exists(self):
        """Todo app goal.md exists with correct content."""
        goal_file = EXAMPLES_DIR / "todo_app" / "goal.md"
        assert goal_file.exists()
        content = goal_file.read_text()
        assert "Flask" in content
        assert "SQLite" in content
        assert "CRUD" in content

    def test_cli_tool_goal_exists(self):
        """CLI tool goal.md exists with correct content."""
        goal_file = EXAMPLES_DIR / "cli_tool" / "goal.md"
        assert goal_file.exists()
        content = goal_file.read_text()
        assert "extension" in content
        assert "Dry-run" in content

    def test_api_service_goal_exists(self):
        """API service goal.md exists with correct content."""
        goal_file = EXAMPLES_DIR / "api_service" / "goal.md"
        assert goal_file.exists()
        content = goal_file.read_text()
        assert "JWT" in content
        assert "authentication" in content

    def test_all_run_scripts_exist(self):
        """All example directories have run.sh scripts."""
        expected_dirs = ["todo_app", "cli_tool", "api_service"]
        for dirname in expected_dirs:
            run_script = EXAMPLES_DIR / dirname / "run.sh"
            assert run_script.exists(), f"Missing run.sh in {dirname}"

    def test_all_run_scripts_executable(self):
        """All run.sh scripts are executable."""
        import os

        for run_script in EXAMPLES_DIR.glob("*/run.sh"):
            assert os.access(run_script, os.X_OK), f"{run_script} is not executable"

    def test_docs_architecture_exists(self):
        """Architecture documentation exists and has substantive content."""
        doc = PROJECT_ROOT / "docs" / "architecture.md"
        assert doc.exists()
        content = doc.read_text()
        # Should be substantive (500+ words)
        word_count = len(content.split())
        assert word_count >= 500, f"Architecture doc only has {word_count} words"
        assert "GraphExecutor" in content
        assert "StateManager" in content

    def test_docs_api_reference_exists(self):
        """API reference documentation exists and covers endpoints."""
        doc = PROJECT_ROOT / "docs" / "api-reference.md"
        assert doc.exists()
        content = doc.read_text()
        assert "/api/state" in content
        assert "/api/metrics" in content
        assert "/api/goal" in content
        assert "WebSocket" in content

    def test_docs_evolution_guide_exists(self):
        """Evolution guide documentation exists and has substantive content."""
        doc = PROJECT_ROOT / "docs" / "evolution-guide.md"
        assert doc.exists()
        content = doc.read_text()
        word_count = len(content.split())
        assert word_count >= 500, f"Evolution guide only has {word_count} words"
        assert "Reflector" in content
        assert "revert_if_worse" in content
        assert "SkillAccumulator" in content
