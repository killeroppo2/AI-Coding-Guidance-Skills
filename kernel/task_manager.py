"""Task manager for structured task tracking.

This module provides the TaskManager class which manages task state
in memory/tasks.yaml, supporting dependency-aware task selection,
status transitions, and dependency validation.
"""

from pathlib import Path

import yaml

from kernel.atomic_write import atomic_write


class TaskManager:
    """Manages structured tasks in memory/tasks.yaml.

    Provides CRUD operations for tasks, dependency-aware task selection,
    and validation of the task dependency graph.
    """

    def __init__(self, memory_dir: str) -> None:
        """Initialize the task manager.

        Args:
            memory_dir: Path to the memory directory.
        """
        self.memory_dir = Path(memory_dir)
        self.tasks_path = self.memory_dir / "tasks.yaml"

    def load_tasks(self) -> list[dict]:
        """Load tasks from memory/tasks.yaml.

        Returns:
            List of task dicts, or empty list if file does not exist.
        """
        if not self.tasks_path.exists():
            return []
        with open(self.tasks_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        tasks: list[dict] = data.get("tasks", [])
        return tasks

    def save_tasks(self, tasks: list[dict]) -> None:
        """Write tasks to memory/tasks.yaml using atomic write.

        Args:
            tasks: List of task dicts to persist.
        """
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        yaml_content = yaml.safe_dump(
            {"tasks": tasks},
            default_flow_style=False,
            allow_unicode=True,
        )
        atomic_write(self.tasks_path, yaml_content)

    def add_task(self, task: dict) -> None:
        """Add a task, auto-generating an id if missing.

        Auto-generated IDs follow the pattern T-001, T-002, etc.

        Args:
            task: Task dict to add.
        """
        tasks = self.load_tasks()
        if "id" not in task or not task["id"]:
            task["id"] = self._generate_id(tasks)
        tasks.append(task)
        self.save_tasks(tasks)

    def get_next_task(self) -> dict | None:
        """Return the first pending task whose dependencies are all done.

        Tasks are evaluated in ID order. A task is eligible if its status
        is 'pending' and all tasks listed in its dependencies have status 'done'.

        Returns:
            The next eligible task dict, or None if no task is available.
        """
        tasks = self.load_tasks()
        status_map = {t["id"]: t.get("status", "pending") for t in tasks}

        # Sort by id to ensure deterministic ordering
        pending = [t for t in tasks if t.get("status") == "pending"]
        pending.sort(key=lambda t: t["id"])

        for task in pending:
            deps = task.get("dependencies", [])
            if all(status_map.get(dep) == "done" for dep in deps):
                return task
        return None

    def mark_in_progress(self, task_id: str) -> None:
        """Set a task's status to in_progress.

        Args:
            task_id: The task ID to update.

        Raises:
            KeyError: If task_id is not found.
        """
        tasks = self.load_tasks()
        for task in tasks:
            if task["id"] == task_id:
                task["status"] = "in_progress"
                self.save_tasks(tasks)
                return
        raise KeyError(f"Task not found: {task_id}")

    def mark_done(self, task_id: str) -> None:
        """Set a task's status to done.

        Args:
            task_id: The task ID to update.

        Raises:
            KeyError: If task_id is not found.
        """
        tasks = self.load_tasks()
        for task in tasks:
            if task["id"] == task_id:
                task["status"] = "done"
                self.save_tasks(tasks)
                return
        raise KeyError(f"Task not found: {task_id}")

    def mark_blocked(self, task_id: str, reason: str) -> None:
        """Set a task's status to blocked with a reason.

        Args:
            task_id: The task ID to update.
            reason: The reason for blocking.

        Raises:
            KeyError: If task_id is not found.
        """
        tasks = self.load_tasks()
        for task in tasks:
            if task["id"] == task_id:
                task["status"] = "blocked"
                task["blocked_reason"] = reason
                self.save_tasks(tasks)
                return
        raise KeyError(f"Task not found: {task_id}")

    def get_task(self, task_id: str) -> dict:
        """Get a task by its ID.

        Args:
            task_id: The task ID to look up.

        Returns:
            The task dict.

        Raises:
            KeyError: If task_id is not found.
        """
        tasks = self.load_tasks()
        for task in tasks:
            if task["id"] == task_id:
                return task
        raise KeyError(f"Task not found: {task_id}")

    def get_progress(self) -> tuple[int, int]:
        """Return progress as (tasks_total, tasks_done).

        Returns:
            Tuple of (total task count, number of tasks with status 'done').
        """
        tasks = self.load_tasks()
        total = len(tasks)
        done = sum(1 for t in tasks if t.get("status") == "done")
        return (total, done)

    def validate_dependencies(self) -> list[str]:
        """Check for cycles and missing dependencies.

        Uses DFS to detect cycles in the dependency graph and checks
        that all referenced dependency IDs exist.

        Returns:
            List of issue descriptions. Empty list means no issues.
        """
        tasks = self.load_tasks()
        task_ids = {t["id"] for t in tasks}
        issues: list[str] = []

        # Check for missing dependency references
        for task in tasks:
            for dep in task.get("dependencies", []):
                if dep not in task_ids:
                    issues.append(f"Task {task['id']} depends on non-existent task {dep}")

        # Check for cycles using DFS
        # Build adjacency list: task -> tasks it depends on
        graph: dict[str, list[str]] = {}
        for task in tasks:
            graph[task["id"]] = task.get("dependencies", [])

        visited: set[str] = set()
        in_stack: set[str] = set()

        def dfs(node: str) -> bool:
            """Return True if a cycle is detected from this node."""
            visited.add(node)
            in_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in task_ids:
                    continue  # already reported as missing
                if neighbor in in_stack:
                    issues.append(f"Circular dependency detected involving {node} and {neighbor}")
                    return True
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
            in_stack.discard(node)
            return False

        for task_id in task_ids:
            if task_id not in visited:
                dfs(task_id)

        return issues

    def _generate_id(self, tasks: list[dict]) -> str:
        """Generate the next sequential task ID.

        Finds the maximum existing ID number and increments by 1.

        Args:
            tasks: Current list of tasks.

        Returns:
            A new task ID string like T-001, T-002, etc.
        """
        max_num = 0
        for task in tasks:
            tid = task.get("id", "")
            if tid.startswith("T-"):
                try:
                    num = int(tid[2:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        return f"T-{max_num + 1:03d}"
