"""Tests for kernel/event_detector.py and user-owned file protection."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kernel.event_detector import EventDetector
from kernel.evolution.engine import EvolutionEngine


@pytest.fixture
def event_root(tmp_path: Path) -> Path:
    """Create a temporary project root with scan directories."""
    (tmp_path / "kernel" / "prompts").mkdir(parents=True)
    (tmp_path / "knowledge" / "rules").mkdir(parents=True)
    (tmp_path / "memory").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def detector(event_root: Path) -> EventDetector:
    """Create an EventDetector instance."""
    return EventDetector(event_root)


class TestDetectExternalChanges:
    """Tests for detect_external_changes method."""

    def test_finds_files_modified_after_last_updated(self, event_root, detector):
        """Files modified after last_updated are detected."""
        # Set reference time in the past
        ref_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        last_updated = ref_time.isoformat()

        # Create a file and set its mtime to after ref_time
        prompt_file = event_root / "kernel" / "prompts" / "test.md"
        prompt_file.write_text("content")
        future_time = (ref_time + timedelta(hours=1)).timestamp()
        os.utime(prompt_file, (future_time, future_time))

        events = detector.detect_external_changes(last_updated)
        assert len(events) == 1
        assert events[0]["type"] == "prompt_modified"
        assert events[0]["path"] == "kernel/prompts/test.md"

    def test_returns_empty_list_when_nothing_changed(self, event_root, detector):
        """No events when all files are older than last_updated."""
        # Create a file and set mtime in the past
        prompt_file = event_root / "kernel" / "prompts" / "old.md"
        prompt_file.write_text("old content")
        past_time = datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp()
        os.utime(prompt_file, (past_time, past_time))

        # Reference time is after the file's mtime
        ref_time = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        events = detector.detect_external_changes(ref_time.isoformat())
        assert events == []

    def test_categorizes_prompt_modified(self, event_root, detector):
        """Files in kernel/prompts/ produce prompt_modified events."""
        ref_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        prompt_file = event_root / "kernel" / "prompts" / "system.md"
        prompt_file.write_text("modified prompt")
        future_time = (ref_time + timedelta(hours=1)).timestamp()
        os.utime(prompt_file, (future_time, future_time))

        events = detector.detect_external_changes(ref_time.isoformat())
        assert len(events) == 1
        assert events[0]["type"] == "prompt_modified"

    def test_categorizes_new_rule_added(self, event_root, detector):
        """Files in knowledge/rules/ produce new_rule_added events."""
        ref_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        rule_file = event_root / "knowledge" / "rules" / "new_rule.yaml"
        rule_file.write_text("rule: test")
        future_time = (ref_time + timedelta(hours=1)).timestamp()
        os.utime(rule_file, (future_time, future_time))

        events = detector.detect_external_changes(ref_time.isoformat())
        assert len(events) == 1
        assert events[0]["type"] == "new_rule_added"

    def test_categorizes_note_left(self, event_root, detector):
        """Files in memory/ produce note_left events."""
        ref_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        note_file = event_root / "memory" / "notes.md"
        note_file.write_text("user note")
        future_time = (ref_time + timedelta(hours=1)).timestamp()
        os.utime(note_file, (future_time, future_time))

        events = detector.detect_external_changes(ref_time.isoformat())
        assert len(events) == 1
        assert events[0]["type"] == "note_left"

    def test_categorizes_manual_task_added(self, event_root, detector):
        """memory/tasks.yaml produces manual_task_added event."""
        ref_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        task_file = event_root / "memory" / "tasks.yaml"
        task_file.write_text("- task: do something")
        future_time = (ref_time + timedelta(hours=1)).timestamp()
        os.utime(task_file, (future_time, future_time))

        events = detector.detect_external_changes(ref_time.isoformat())
        assert len(events) == 1
        assert events[0]["type"] == "manual_task_added"

    def test_handles_empty_last_updated(self, detector):
        """Returns empty list when last_updated is empty string."""
        events = detector.detect_external_changes("")
        assert events == []

    def test_handles_none_last_updated(self, detector):
        """Returns empty list when last_updated is None."""
        events = detector.detect_external_changes(None)
        assert events == []

    def test_handles_invalid_last_updated(self, detector):
        """Returns empty list when last_updated is not a valid ISO timestamp."""
        events = detector.detect_external_changes("not-a-date")
        assert events == []

    def test_skips_files_starting_with_underscore(self, event_root, detector):
        """Files starting with _ are skipped (like _index.yaml)."""
        ref_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        index_file = event_root / "knowledge" / "rules" / "_index.yaml"
        index_file.write_text("items: []")
        future_time = (ref_time + timedelta(hours=1)).timestamp()
        os.utime(index_file, (future_time, future_time))

        events = detector.detect_external_changes(ref_time.isoformat())
        assert events == []

    def test_skips_nonexistent_directories(self, tmp_path):
        """Gracefully handles missing scan directories."""
        # Create detector with empty root (no subdirs)
        detector = EventDetector(tmp_path)
        ref_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        events = detector.detect_external_changes(ref_time.isoformat())
        assert events == []


class TestGetUserOwnedFiles:
    """Tests for get_user_owned_files method."""

    def test_returns_empty_list_when_not_in_state(self, detector):
        """Returns empty list when state has no user_owned_files key."""
        state = {"current_node": "init"}
        assert detector.get_user_owned_files(state) == []

    def test_returns_list_when_present(self, detector):
        """Returns the user_owned_files list from state."""
        state = {"user_owned_files": ["kernel/prompts/custom.md", "memory/notes.md"]}
        result = detector.get_user_owned_files(state)
        assert result == ["kernel/prompts/custom.md", "memory/notes.md"]


class TestMarkUserOwned:
    """Tests for mark_user_owned method."""

    def test_adds_file_to_state(self, detector):
        """Adds a file path to user_owned_files in state."""
        state = {}
        detector.mark_user_owned(state, "kernel/prompts/custom.md")
        assert "kernel/prompts/custom.md" in state["user_owned_files"]

    def test_does_not_add_duplicates(self, detector):
        """Does not add the same file path twice."""
        state = {"user_owned_files": ["kernel/prompts/custom.md"]}
        detector.mark_user_owned(state, "kernel/prompts/custom.md")
        assert state["user_owned_files"].count("kernel/prompts/custom.md") == 1

    def test_adds_to_existing_list(self, detector):
        """Appends to existing user_owned_files list."""
        state = {"user_owned_files": ["file1.md"]}
        detector.mark_user_owned(state, "file2.md")
        assert state["user_owned_files"] == ["file1.md", "file2.md"]


class TestIsUserOwned:
    """Tests for is_user_owned method."""

    def test_returns_true_for_owned_files(self, detector):
        """Returns True when file is in user_owned_files."""
        state = {"user_owned_files": ["kernel/prompts/my.md"]}
        assert detector.is_user_owned(state, "kernel/prompts/my.md") is True

    def test_returns_false_for_unowned_files(self, detector):
        """Returns False when file is not in user_owned_files."""
        state = {"user_owned_files": ["kernel/prompts/my.md"]}
        assert detector.is_user_owned(state, "kernel/prompts/other.md") is False

    def test_returns_false_when_no_user_owned_files(self, detector):
        """Returns False when state has no user_owned_files key."""
        state = {}
        assert detector.is_user_owned(state, "anything.md") is False


class TestEvolutionEngineUserOwned:
    """Tests for user-owned file protection in EvolutionEngine."""

    @pytest.fixture
    def engine(self, tmp_path: Path) -> EvolutionEngine:
        """Create an EvolutionEngine for testing."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        graph_executor = MagicMock()
        return EvolutionEngine(str(kernel_dir), graph_executor)

    def test_rejects_changes_to_user_owned_files(self, engine):
        """validate_change rejects changes targeting user-owned files."""
        state = {"user_owned_files": ["kernel/prompts/custom.md"]}
        change = {
            "type": "modify_prompt",
            "details": {"prompt_file": "kernel/prompts/custom.md", "content": "new"},
        }
        valid, reason = engine.validate_change(change, state=state)
        assert valid is False
        assert "user-owned" in reason

    def test_rejects_via_target_file_field(self, engine):
        """Rejects when target_file matches a user-owned file."""
        state = {"user_owned_files": ["knowledge/rules/my_rule.yaml"]}
        change = {
            "type": "add_rule",
            "details": {"target_file": "knowledge/rules/my_rule.yaml"},
        }
        valid, reason = engine.validate_change(change, state=state)
        assert valid is False
        assert "user-owned" in reason

    def test_rejects_via_path_field(self, engine):
        """Rejects when path field matches a user-owned file."""
        state = {"user_owned_files": ["memory/notes.md"]}
        change = {
            "type": "add_rule",
            "details": {"path": "memory/notes.md"},
        }
        valid, reason = engine.validate_change(change, state=state)
        assert valid is False
        assert "user-owned" in reason

    def test_allows_changes_to_non_user_owned_files(self, engine):
        """validate_change allows changes to files not in user_owned_files."""
        state = {"user_owned_files": ["kernel/prompts/custom.md"]}
        change = {
            "type": "modify_prompt",
            "details": {"prompt_file": "kernel/prompts/other.md", "content": "new"},
        }
        valid, reason = engine.validate_change(change, state=state)
        assert valid is True

    def test_works_without_state_parameter(self, engine):
        """validate_change still works without state (backward compat)."""
        change = {
            "type": "modify_prompt",
            "details": {"prompt_file": "prompts/test.md", "content": "content"},
        }
        valid, reason = engine.validate_change(change)
        assert valid is True
        assert reason == "Change is valid"

    def test_works_with_state_none(self, engine):
        """validate_change works when state is explicitly None."""
        change = {
            "type": "add_node",
            "details": {"node": {"id": "new_node"}},
        }
        valid, reason = engine.validate_change(change, state=None)
        assert valid is True

    def test_works_with_state_without_user_owned_files(self, engine):
        """validate_change works when state has no user_owned_files key."""
        state = {"current_node": "init"}
        change = {
            "type": "modify_prompt",
            "details": {"prompt_file": "prompts/test.md", "content": "x"},
        }
        valid, reason = engine.validate_change(change, state=state)
        assert valid is True
