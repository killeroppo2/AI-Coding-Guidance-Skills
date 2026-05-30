"""State management for the kernel execution lifecycle.

This module handles reading, updating, and persisting the kernel's state
including current node, iteration count, goals, and error tracking.
"""

import copy
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from kernel.atomic_write import atomic_write
from kernel.file_lock import FileLock

logger = logging.getLogger(__name__)

DEFAULT_STATE = {
    "current_node": "init",
    "iteration_count": 0,
    "max_iterations": 30,
    "goal": "",
    "workspace_path": "",
    "status": "idle",
    "last_updated": "",
    "errors": [],
    "context": {
        "skills_loaded": [],
        "current_task": "",
        "phase": "startup",
    },
    "node_visits": {},
    "progress_history": [],
    "execution_mode": "kernel",
}


class StateManager:
    """Manages kernel execution state via filesystem persistence.

    State is stored in YAML files and updated after each node execution.
    All state is file-based to support stateless AI agent execution.
    """

    def __init__(self, state_path: str, memory_dir: str) -> None:
        """Initialize the state manager.

        Args:
            state_path: Path to the state.yaml file.
            memory_dir: Path to the memory/ directory.
        """
        self.state_path = Path(state_path)
        self.memory_dir = Path(memory_dir)
        self.state: dict[str, Any] = self.load_state()

    def load_state(self) -> dict[str, Any]:
        """Load state.yaml, create default if missing.

        Returns:
            Dict containing the current state.
        """
        if not self.state_path.exists():
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            state = copy.deepcopy(DEFAULT_STATE)
            state["last_updated"] = datetime.now(timezone.utc).isoformat()
            with open(self.state_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(state, f, default_flow_style=False, allow_unicode=True)
            return state
        with open(self.state_path, "r", encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f) or {}
            except yaml.YAMLError:
                logger.warning(f"Corrupted state file {self.state_path}, resetting to defaults")
                data = copy.deepcopy(DEFAULT_STATE)
        # Merge with defaults for any missing keys
        for key, value in DEFAULT_STATE.items():
            if key not in data:
                data[key] = copy.deepcopy(value)
        self.state = data
        return data

    def save_state(self) -> None:
        """Write current state to state.yaml using atomic write."""
        self.state["last_updated"] = datetime.now(timezone.utc).isoformat()
        yaml_content = yaml.safe_dump(self.state, default_flow_style=False, allow_unicode=True)
        atomic_write(self.state_path, yaml_content)

    def _get_lock_path(self) -> Path:
        """Return the lock file path for state.yaml.

        Returns:
            Path with .lock suffix appended to state_path.
        """
        return self.state_path.with_suffix(".yaml.lock")

    def check_runner_lock(self) -> tuple[bool, str]:
        """Check if a runner lock exists and is not stale.

        Returns:
            Tuple of (is_locked, message). If locked and fresh, returns
            (True, "Runner already active since {timestamp}").
            If not locked or stale, returns (False, "").
        """
        runner_lock_path = self.memory_dir / "runner.lock"
        if not runner_lock_path.exists():
            return (False, "")
        if FileLock.is_stale(runner_lock_path, max_age_seconds=600):
            return (False, "")
        try:
            with open(runner_lock_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            timestamp = data.get("timestamp", "unknown")
            return (True, f"Runner already active since {timestamp}")
        except (json.JSONDecodeError, OSError):
            return (False, "")

    def acquire_runner_lock(self) -> None:
        """Create runner.lock in the memory directory."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        runner_lock_path = self.memory_dir / "runner.lock"
        lock_info = {
            "pid": os.getpid(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "host": os.uname().nodename,
        }
        with open(runner_lock_path, "w", encoding="utf-8") as f:
            json.dump(lock_info, f)

    def release_runner_lock(self) -> None:
        """Remove runner.lock from the memory directory."""
        runner_lock_path = self.memory_dir / "runner.lock"
        try:
            os.unlink(str(runner_lock_path))
        except FileNotFoundError:
            pass

    def get_state(self) -> dict[str, Any]:
        """Return current state dict.

        Returns:
            The current state dictionary.
        """
        return self.state

    def set_current_node(self, node_id: str) -> None:
        """Update current node.

        Args:
            node_id: The new current node ID.
        """
        self.state["current_node"] = node_id

    def increment_iteration(self) -> None:
        """Increment iteration_count and update last_updated timestamp."""
        self.state["iteration_count"] = self.state.get("iteration_count", 0) + 1
        self.state["last_updated"] = datetime.now(timezone.utc).isoformat()

    def record_decision(self, decision: dict) -> None:
        """Append JSON line to decisions.jsonl with advisory locking.

        Args:
            decision: Decision dict to record.
        """
        decision.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.memory_dir / "decisions.jsonl"
        lock_path = filepath.with_suffix(".jsonl.lock")
        # Clean up stale lock before acquiring (process likely crashed)
        if FileLock.is_stale(lock_path, max_age_seconds=30):
            FileLock.force_release(lock_path)
        with FileLock(lock_path, timeout=5.0):
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(decision) + "\n")

    def record_reflection(self, reflection: dict) -> None:
        """Append JSON line to reflections.jsonl with advisory locking.

        Args:
            reflection: Reflection dict to record.
        """
        reflection.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.memory_dir / "reflections.jsonl"
        lock_path = filepath.with_suffix(".jsonl.lock")
        # Clean up stale lock before acquiring (process likely crashed)
        if FileLock.is_stale(lock_path, max_age_seconds=30):
            FileLock.force_release(lock_path)
        with FileLock(lock_path, timeout=5.0):
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(reflection) + "\n")

    def update_progress(self, tasks_total: int, tasks_done: int) -> None:
        """Update progress.yaml using atomic write.

        Args:
            tasks_total: Total number of tasks.
            tasks_done: Number of completed tasks.
        """
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        progress_path = self.memory_dir / "progress.yaml"
        progress = {
            "iteration": self.state.get("iteration_count", 0),
            "tasks_total": tasks_total,
            "tasks_done": tasks_done,
            "status": (
                "complete" if tasks_done >= tasks_total and tasks_total > 0 else "in_progress"
            ),
        }
        yaml_content = yaml.safe_dump(progress, default_flow_style=False, allow_unicode=True)
        atomic_write(progress_path, yaml_content)

    def set_goal(self, goal: str) -> None:
        """Set goal in state and write to current_goal.md using atomic write.

        Args:
            goal: The goal string.
        """
        self.state["goal"] = goal
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        goal_path = self.memory_dir / "current_goal.md"
        atomic_write(goal_path, f"# Current Goal\n\n{goal}\n")

    def set_workspace(self, project_name: str) -> None:
        """Set workspace_path in state and create the workspace directory.

        Args:
            project_name: Sanitized project name for the workspace subdirectory.
        """
        workspace_rel = f"./workspace/{project_name}/"
        self.state["workspace_path"] = workspace_rel
        # Derive workspace directory relative to the project root
        # state_path is kernel/state.yaml, so parent.parent is the project root
        project_root = self.state_path.parent.parent
        workspace_dir = project_root / "workspace" / project_name
        workspace_dir.mkdir(parents=True, exist_ok=True)

    def get_execution_mode(self) -> str:
        """Return the current execution mode.

        Returns:
            The execution mode string ('kernel' or 'ralph').
        """
        mode: str = self.state.get("execution_mode", "kernel")
        return mode

    def set_execution_mode(self, mode: str) -> None:
        """Set the execution mode.

        Args:
            mode: The execution mode to set ('kernel' or 'ralph').

        Raises:
            ValueError: If mode is not 'kernel' or 'ralph'.
        """
        if mode not in ("kernel", "ralph"):
            raise ValueError(f"Invalid execution_mode '{mode}': must be 'kernel' or 'ralph'")
        self.state["execution_mode"] = mode

    def get_workspace(self) -> Path:
        """Return the workspace Path resolved from the project root.

        Returns:
            Path to the workspace directory.
        """
        workspace_rel: str = self.state.get("workspace_path", "")
        project_root = self.state_path.parent.parent
        if not workspace_rel:
            return project_root / "workspace"
        # Strip leading ./ if present
        clean = workspace_rel.lstrip("./")
        return project_root / clean

    def is_complete(self) -> bool:
        """Check if execution is complete.

        Returns:
            True if status is 'complete' or tasks_done >= tasks_total (and tasks_total > 0).
        """
        if self.state.get("status") == "complete":
            return True
        # Check progress
        progress_path = self.memory_dir / "progress.yaml"
        if progress_path.exists():
            with open(progress_path, "r", encoding="utf-8") as f:
                progress = yaml.safe_load(f) or {}
            tasks_total = progress.get("tasks_total", 0)
            tasks_done = progress.get("tasks_done", 0)
            if tasks_total > 0 and tasks_done >= tasks_total:
                return True
        return False

    def reset(self) -> None:
        """Reset state to defaults."""
        self.state = copy.deepcopy(DEFAULT_STATE)
        self.state["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.save_state()

    def track_node_visit(self, node_id: str) -> int:
        """Increment and return the visit count for a node.

        Args:
            node_id: The node being visited.

        Returns:
            The new visit count for this node.
        """
        if "node_visits" not in self.state:
            self.state["node_visits"] = {}
        self.state["node_visits"][node_id] = self.state["node_visits"].get(node_id, 0) + 1
        count: int = self.state["node_visits"][node_id]
        return count

    def trim_node_visits(self, max_nodes: int = 100) -> None:
        """Trim node_visits to prevent unbounded growth.

        Keeps only the max_nodes most-visited nodes. In practice, this is
        rarely needed since nodes are bounded by graph size, but protects
        against pathological cases.

        Args:
            max_nodes: Maximum number of node entries to retain.
        """
        visits = self.state.get("node_visits", {})
        if len(visits) > max_nodes:
            sorted_nodes = sorted(visits.items(), key=lambda x: x[1], reverse=True)
            self.state["node_visits"] = dict(sorted_nodes[:max_nodes])

    def check_stuck(self, max_retries_map: dict) -> tuple[bool, str | None, int]:
        """Check if any node has exceeded its max_retries.

        Args:
            max_retries_map: Dict of {node_id: max_retries_allowed}

        Returns:
            Tuple of (is_stuck, stuck_node_id_or_None, visit_count)
        """
        node_visits = self.state.get("node_visits", {})
        for node_id, visits in node_visits.items():
            max_allowed = max_retries_map.get(node_id, float("inf"))
            if visits > max_allowed:
                return (True, node_id, visits)
        return (False, None, 0)

    def get_tasks_path(self) -> Path:
        """Return the path to tasks.yaml in the memory directory.

        Returns:
            Path to memory/tasks.yaml.
        """
        return self.memory_dir / "tasks.yaml"

    def trim_errors(self, max_kept: int = 20) -> None:
        """Keep only the last max_kept errors, archive older ones to error_history.jsonl.

        Args:
            max_kept: Maximum number of errors to retain in state (default 20).
        """
        errors = self.state.get("errors", [])
        if len(errors) > max_kept:
            archived = errors[:-max_kept] if max_kept > 0 else errors
            self.state["errors"] = errors[-max_kept:] if max_kept > 0 else []
            # Append archived errors to error_history.jsonl
            history_path = self.memory_dir / "error_history.jsonl"
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            with open(history_path, "a", encoding="utf-8") as f:
                for error in archived:
                    entry = json.dumps(
                        {
                            "error": error,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    f.write(entry + "\n")

    def clear_errors(self) -> None:
        """Move all errors to error_history.jsonl and reset errors list."""
        self.trim_errors(max_kept=0)

    def check_convergence(self, lookback: int = 5) -> tuple[bool, int]:
        """Check if progress has stalled (tasks_done unchanged over lookback iterations).

        Looks at the progress_history list in state. If the last `lookback` entries
        all have the same tasks_done value and iteration_count > lookback, progress
        is considered stalled.

        Args:
            lookback: Number of iterations without progress to consider stalled.

        Returns:
            Tuple of (is_stalled, stale_iterations_count).
        """
        history = self.state.get("progress_history", [])
        if len(history) < lookback:
            return (False, 0)
        recent = history[-lookback:]
        # All recent entries have same tasks_done value
        if all(entry == recent[0] for entry in recent):
            iteration_count = self.state.get("iteration_count", 0)
            if iteration_count > lookback:
                return (True, lookback)
        return (False, 0)
