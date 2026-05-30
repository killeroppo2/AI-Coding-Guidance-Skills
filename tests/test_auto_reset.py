"""Tests for auto-reset logic in kernel/orchestrator.py."""

from pathlib import Path

import yaml

import runner


class TestAutoReset:
    """Tests for automatic state reset when a new goal is provided."""

    def _make_env(self, tmp_path: Path, state_data: dict) -> Path:
        """Create a minimal runner environment with the given state."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
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
            yaml.safe_dump(
                {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"},
                f,
            )

        # Create stale files to verify cleanup
        (memory_dir / "tasks.yaml").write_text("tasks: [{id: T-001, status: done}]")
        (memory_dir / "assessment.yaml").write_text("confidence: 0.9")

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        with open(skills_dir / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": [], "core_items": [], "community_items": []}, f)

        return tmp_path

    def test_auto_reset_on_complete_status_with_new_goal(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """State resets when status=complete and new goal is given."""
        state_data = {
            "current_node": "code",
            "iteration_count": 10,
            "max_iterations": 30,
            "goal": "Old goal",
            "status": "complete",
            "last_updated": "",
            "errors": ["old error"],
            "context": {"skills_loaded": [], "current_task": "", "phase": "done"},
            "node_visits": {},
            "progress_history": [],
            "execution_mode": "kernel",
            "workspace_path": "",
        }
        env_path = self._make_env(tmp_path, state_data)
        monkeypatch.setattr(runner, "KERNEL_ROOT", env_path)

        # Use max-iterations=1 to terminate quickly (no dry-run so reset fires)
        state = runner.main(["--goal", "New goal", "--max-iterations", "1"])
        assert state["goal"] == "New goal"
        # The reset cleared old errors (they would carry over otherwise)
        assert "old error" not in state.get("errors", [])
        # iteration_count reflects only iterations from this run (not old 10)
        assert state["iteration_count"] <= 1

    def test_auto_reset_on_stuck_status(self, tmp_path: Path, monkeypatch) -> None:
        """State resets when status=stuck and new goal is given."""
        state_data = {
            "current_node": "code",
            "iteration_count": 5,
            "max_iterations": 30,
            "goal": "Stuck goal",
            "status": "stuck",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "coding"},
            "node_visits": {},
            "progress_history": [],
            "execution_mode": "kernel",
            "workspace_path": "",
        }
        env_path = self._make_env(tmp_path, state_data)
        monkeypatch.setattr(runner, "KERNEL_ROOT", env_path)

        state = runner.main(["--goal", "New goal", "--max-iterations", "1"])
        assert state["goal"] == "New goal"

    def test_auto_reset_on_different_goal(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """State resets when goal differs from stored goal."""
        state_data = {
            "current_node": "code",
            "iteration_count": 3,
            "max_iterations": 30,
            "goal": "Build an API",
            "status": "running",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "coding"},
            "node_visits": {},
            "progress_history": [],
            "execution_mode": "kernel",
            "workspace_path": "",
        }
        env_path = self._make_env(tmp_path, state_data)
        monkeypatch.setattr(runner, "KERNEL_ROOT", env_path)

        state = runner.main(
            ["--goal", "Completely different goal", "--max-iterations", "1"]
        )
        assert state["goal"] == "Completely different goal"

    def test_no_reset_on_resume(self, tmp_path: Path, monkeypatch) -> None:
        """State does not reset when --resume is used."""
        state_data = {
            "current_node": "code",
            "iteration_count": 5,
            "max_iterations": 30,
            "goal": "My goal",
            "status": "complete",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "done"},
            "node_visits": {},
            "progress_history": [],
            "execution_mode": "kernel",
            "workspace_path": "",
        }
        env_path = self._make_env(tmp_path, state_data)
        monkeypatch.setattr(runner, "KERNEL_ROOT", env_path)

        state = runner.main(["--goal", "My goal", "--resume", "--dry-run"])
        # With resume, the goal is preserved, no reset
        assert state["goal"] == "My goal"
