"""Tests for the TaskManager class."""

from pathlib import Path

import pytest
import yaml

from kernel.task_manager import TaskManager
from memory.state_manager import StateManager


class TestTaskManagerInit:
    """Tests for TaskManager initialization."""

    def test_instantiation(self, tmp_path: Path) -> None:
        """Test that TaskManager can be instantiated."""
        tm = TaskManager(str(tmp_path))
        assert tm.memory_dir == tmp_path
        assert tm.tasks_path == tmp_path / "tasks.yaml"

    def test_importable(self) -> None:
        """Test that kernel.task_manager can be imported."""
        from kernel import task_manager

        assert task_manager is not None


class TestLoadTasks:
    """Tests for loading tasks."""

    def test_load_tasks_empty_when_no_file(self, tmp_path: Path) -> None:
        """Test that load_tasks returns empty list when file does not exist."""
        tm = TaskManager(str(tmp_path))
        assert tm.load_tasks() == []

    def test_load_tasks_empty_when_file_empty(self, tmp_path: Path) -> None:
        """Test that load_tasks returns empty list when file is empty."""
        tasks_file = tmp_path / "tasks.yaml"
        tasks_file.write_text("")
        tm = TaskManager(str(tmp_path))
        assert tm.load_tasks() == []

    def test_load_tasks_returns_tasks(self, tmp_path: Path) -> None:
        """Test that load_tasks returns tasks from file."""
        tasks_file = tmp_path / "tasks.yaml"
        data = {
            "tasks": [
                {"id": "T-001", "title": "First", "status": "pending"},
            ]
        }
        with open(tasks_file, "w") as f:
            yaml.safe_dump(data, f)
        tm = TaskManager(str(tmp_path))
        result = tm.load_tasks()
        assert len(result) == 1
        assert result[0]["id"] == "T-001"


class TestSaveTasks:
    """Tests for saving tasks."""

    def test_save_tasks_creates_file(self, tmp_path: Path) -> None:
        """Test that save_tasks creates the tasks.yaml file."""
        tm = TaskManager(str(tmp_path))
        tasks = [{"id": "T-001", "title": "First", "status": "pending"}]
        tm.save_tasks(tasks)
        assert (tmp_path / "tasks.yaml").exists()

    def test_save_and_reload(self, tmp_path: Path) -> None:
        """Test that saved tasks can be reloaded correctly."""
        tm = TaskManager(str(tmp_path))
        tasks = [
            {
                "id": "T-001",
                "title": "Task One",
                "description": "Do something",
                "status": "pending",
                "acceptance_criteria": ["It works"],
                "dependencies": [],
                "complexity": "low",
            },
            {
                "id": "T-002",
                "title": "Task Two",
                "description": "Do more",
                "status": "done",
                "acceptance_criteria": ["It also works"],
                "dependencies": ["T-001"],
                "complexity": "medium",
            },
        ]
        tm.save_tasks(tasks)
        reloaded = tm.load_tasks()
        assert len(reloaded) == 2
        assert reloaded[0]["title"] == "Task One"
        assert reloaded[1]["dependencies"] == ["T-001"]

    def test_save_tasks_creates_directory(self, tmp_path: Path) -> None:
        """Test that save_tasks creates parent directory if missing."""
        nested = tmp_path / "deep" / "nested"
        tm = TaskManager(str(nested))
        tm.save_tasks([{"id": "T-001", "status": "pending"}])
        assert (nested / "tasks.yaml").exists()


class TestAddTask:
    """Tests for adding tasks."""

    def test_add_task_with_id(self, tmp_path: Path) -> None:
        """Test adding a task with an explicit id."""
        tm = TaskManager(str(tmp_path))
        tm.add_task({"id": "T-001", "title": "Manual ID", "status": "pending"})
        tasks = tm.load_tasks()
        assert len(tasks) == 1
        assert tasks[0]["id"] == "T-001"

    def test_add_task_auto_generates_id(self, tmp_path: Path) -> None:
        """Test that add_task auto-generates an id when missing."""
        tm = TaskManager(str(tmp_path))
        tm.add_task({"title": "No ID", "status": "pending"})
        tasks = tm.load_tasks()
        assert tasks[0]["id"] == "T-001"

    def test_add_task_auto_id_increments(self, tmp_path: Path) -> None:
        """Test that auto-generated ids increment correctly."""
        tm = TaskManager(str(tmp_path))
        tm.add_task({"id": "T-001", "title": "First", "status": "pending"})
        tm.add_task({"title": "Second", "status": "pending"})
        tasks = tm.load_tasks()
        assert tasks[1]["id"] == "T-002"

    def test_add_task_auto_id_with_gap(self, tmp_path: Path) -> None:
        """Test auto-id generation with gaps in existing ids."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "status": "done"},
                {"id": "T-005", "status": "pending"},
            ]
        )
        tm.add_task({"title": "After gap", "status": "pending"})
        tasks = tm.load_tasks()
        assert tasks[2]["id"] == "T-006"

    def test_add_task_empty_id_auto_generates(self, tmp_path: Path) -> None:
        """Test that empty string id triggers auto-generation."""
        tm = TaskManager(str(tmp_path))
        tm.add_task({"id": "", "title": "Empty ID", "status": "pending"})
        tasks = tm.load_tasks()
        assert tasks[0]["id"] == "T-001"


class TestGetNextTask:
    """Tests for get_next_task dependency resolution."""

    def test_get_next_task_simple(self, tmp_path: Path) -> None:
        """Test getting the next pending task with no dependencies."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "title": "First", "status": "pending", "dependencies": []},
                {"id": "T-002", "title": "Second", "status": "pending", "dependencies": []},
            ]
        )
        result = tm.get_next_task()
        assert result is not None
        assert result["id"] == "T-001"

    def test_get_next_task_skips_done(self, tmp_path: Path) -> None:
        """Test that done tasks are skipped."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "title": "First", "status": "done", "dependencies": []},
                {"id": "T-002", "title": "Second", "status": "pending", "dependencies": []},
            ]
        )
        result = tm.get_next_task()
        assert result is not None
        assert result["id"] == "T-002"

    def test_get_next_task_respects_dependencies(self, tmp_path: Path) -> None:
        """Test that tasks with unmet dependencies are skipped."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "title": "First", "status": "pending", "dependencies": []},
                {"id": "T-002", "title": "Second", "status": "pending", "dependencies": ["T-001"]},
            ]
        )
        result = tm.get_next_task()
        assert result is not None
        assert result["id"] == "T-001"

    def test_get_next_task_deps_met(self, tmp_path: Path) -> None:
        """Test that tasks with all deps done are returned."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "title": "First", "status": "done", "dependencies": []},
                {"id": "T-002", "title": "Second", "status": "pending", "dependencies": ["T-001"]},
            ]
        )
        result = tm.get_next_task()
        assert result is not None
        assert result["id"] == "T-002"

    def test_get_next_task_all_blocked(self, tmp_path: Path) -> None:
        """Test returns None when no task is eligible."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "title": "First", "status": "pending", "dependencies": ["T-002"]},
                {"id": "T-002", "title": "Second", "status": "pending", "dependencies": ["T-001"]},
            ]
        )
        result = tm.get_next_task()
        assert result is None

    def test_get_next_task_empty_list(self, tmp_path: Path) -> None:
        """Test returns None when no tasks exist."""
        tm = TaskManager(str(tmp_path))
        result = tm.get_next_task()
        assert result is None

    def test_get_next_task_all_done(self, tmp_path: Path) -> None:
        """Test returns None when all tasks are done."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "title": "First", "status": "done", "dependencies": []},
            ]
        )
        result = tm.get_next_task()
        assert result is None

    def test_get_next_task_skips_in_progress(self, tmp_path: Path) -> None:
        """Test that in_progress tasks are not returned as next."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "title": "First", "status": "in_progress", "dependencies": []},
                {"id": "T-002", "title": "Second", "status": "pending", "dependencies": []},
            ]
        )
        result = tm.get_next_task()
        assert result is not None
        assert result["id"] == "T-002"


class TestMarkStatus:
    """Tests for status transition methods."""

    def test_mark_in_progress(self, tmp_path: Path) -> None:
        """Test marking a task as in_progress."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "title": "First", "status": "pending", "dependencies": []},
            ]
        )
        tm.mark_in_progress("T-001")
        task = tm.get_task("T-001")
        assert task["status"] == "in_progress"

    def test_mark_done(self, tmp_path: Path) -> None:
        """Test marking a task as done."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "title": "First", "status": "in_progress", "dependencies": []},
            ]
        )
        tm.mark_done("T-001")
        task = tm.get_task("T-001")
        assert task["status"] == "done"

    def test_mark_blocked(self, tmp_path: Path) -> None:
        """Test marking a task as blocked with reason."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "title": "First", "status": "pending", "dependencies": []},
            ]
        )
        tm.mark_blocked("T-001", "Missing API key")
        task = tm.get_task("T-001")
        assert task["status"] == "blocked"
        assert task["blocked_reason"] == "Missing API key"

    def test_mark_in_progress_not_found(self, tmp_path: Path) -> None:
        """Test mark_in_progress raises KeyError for missing task."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks([])
        with pytest.raises(KeyError, match="Task not found: T-999"):
            tm.mark_in_progress("T-999")

    def test_mark_done_not_found(self, tmp_path: Path) -> None:
        """Test mark_done raises KeyError for missing task."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks([])
        with pytest.raises(KeyError, match="Task not found: T-999"):
            tm.mark_done("T-999")

    def test_mark_blocked_not_found(self, tmp_path: Path) -> None:
        """Test mark_blocked raises KeyError for missing task."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks([])
        with pytest.raises(KeyError, match="Task not found: T-999"):
            tm.mark_blocked("T-999", "reason")


class TestGetTask:
    """Tests for getting a task by ID."""

    def test_get_task_found(self, tmp_path: Path) -> None:
        """Test getting an existing task."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "title": "First", "status": "pending"},
                {"id": "T-002", "title": "Second", "status": "done"},
            ]
        )
        task = tm.get_task("T-002")
        assert task["title"] == "Second"
        assert task["status"] == "done"

    def test_get_task_not_found(self, tmp_path: Path) -> None:
        """Test that get_task raises KeyError for missing task."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks([{"id": "T-001", "status": "pending"}])
        with pytest.raises(KeyError, match="Task not found: T-999"):
            tm.get_task("T-999")

    def test_get_task_empty_list(self, tmp_path: Path) -> None:
        """Test that get_task raises KeyError when no tasks exist."""
        tm = TaskManager(str(tmp_path))
        with pytest.raises(KeyError):
            tm.get_task("T-001")


class TestGetProgress:
    """Tests for progress tracking."""

    def test_get_progress_empty(self, tmp_path: Path) -> None:
        """Test progress with no tasks."""
        tm = TaskManager(str(tmp_path))
        total, done = tm.get_progress()
        assert total == 0
        assert done == 0

    def test_get_progress_all_pending(self, tmp_path: Path) -> None:
        """Test progress with all tasks pending."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "status": "pending"},
                {"id": "T-002", "status": "pending"},
                {"id": "T-003", "status": "pending"},
            ]
        )
        total, done = tm.get_progress()
        assert total == 3
        assert done == 0

    def test_get_progress_some_done(self, tmp_path: Path) -> None:
        """Test progress with mix of statuses."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "status": "done"},
                {"id": "T-002", "status": "in_progress"},
                {"id": "T-003", "status": "pending"},
                {"id": "T-004", "status": "done"},
            ]
        )
        total, done = tm.get_progress()
        assert total == 4
        assert done == 2

    def test_get_progress_all_done(self, tmp_path: Path) -> None:
        """Test progress when all tasks are done."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "status": "done"},
                {"id": "T-002", "status": "done"},
            ]
        )
        total, done = tm.get_progress()
        assert total == 2
        assert done == 2


class TestValidateDependencies:
    """Tests for dependency validation."""

    def test_validate_no_issues(self, tmp_path: Path) -> None:
        """Test validation with valid dependencies."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "status": "pending", "dependencies": []},
                {"id": "T-002", "status": "pending", "dependencies": ["T-001"]},
                {"id": "T-003", "status": "pending", "dependencies": ["T-001", "T-002"]},
            ]
        )
        issues = tm.validate_dependencies()
        assert issues == []

    def test_validate_missing_dependency(self, tmp_path: Path) -> None:
        """Test validation catches missing dependency references."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "status": "pending", "dependencies": ["T-999"]},
            ]
        )
        issues = tm.validate_dependencies()
        assert len(issues) == 1
        assert "non-existent task T-999" in issues[0]

    def test_validate_circular_dependency(self, tmp_path: Path) -> None:
        """Test validation catches circular dependencies."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "status": "pending", "dependencies": ["T-002"]},
                {"id": "T-002", "status": "pending", "dependencies": ["T-001"]},
            ]
        )
        issues = tm.validate_dependencies()
        assert len(issues) >= 1
        assert any("Circular dependency" in issue for issue in issues)

    def test_validate_self_dependency(self, tmp_path: Path) -> None:
        """Test validation catches self-referencing dependency."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "status": "pending", "dependencies": ["T-001"]},
            ]
        )
        issues = tm.validate_dependencies()
        assert len(issues) >= 1
        assert any("Circular dependency" in issue for issue in issues)

    def test_validate_empty_tasks(self, tmp_path: Path) -> None:
        """Test validation with no tasks returns no issues."""
        tm = TaskManager(str(tmp_path))
        issues = tm.validate_dependencies()
        assert issues == []

    def test_validate_three_node_cycle(self, tmp_path: Path) -> None:
        """Test validation catches a three-node cycle."""
        tm = TaskManager(str(tmp_path))
        tm.save_tasks(
            [
                {"id": "T-001", "status": "pending", "dependencies": ["T-003"]},
                {"id": "T-002", "status": "pending", "dependencies": ["T-001"]},
                {"id": "T-003", "status": "pending", "dependencies": ["T-002"]},
            ]
        )
        issues = tm.validate_dependencies()
        assert len(issues) >= 1
        assert any("Circular dependency" in issue for issue in issues)


class TestStateManagerIntegration:
    """Tests for integration between StateManager and TaskManager."""

    def test_get_tasks_path(self, tmp_state: Path, tmp_memory: Path) -> None:
        """Test that StateManager.get_tasks_path returns correct path."""
        sm = StateManager(str(tmp_state), str(tmp_memory))
        expected = tmp_memory / "tasks.yaml"
        assert sm.get_tasks_path() == expected

    def test_task_manager_uses_state_manager_path(self, tmp_state: Path, tmp_memory: Path) -> None:
        """Test that TaskManager works with StateManager's tasks path."""
        sm = StateManager(str(tmp_state), str(tmp_memory))
        tm = TaskManager(str(sm.memory_dir))
        tm.add_task(
            {
                "title": "Integration test",
                "status": "pending",
                "dependencies": [],
            }
        )
        assert sm.get_tasks_path().exists()
        tasks = tm.load_tasks()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Integration test"
