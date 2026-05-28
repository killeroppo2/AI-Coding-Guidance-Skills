"""Tests for kernel/session_tracker.py."""

import json
import time
from pathlib import Path

import pytest

from kernel.session_tracker import SessionTracker


@pytest.fixture
def memory_dir(tmp_path):
    """Create a temporary memory directory."""
    mem = tmp_path / "memory"
    mem.mkdir()
    return str(mem)


class TestSessionTracker:
    """Tests for SessionTracker."""

    def test_track_event_creates_file(self, memory_dir):
        """track_event should create the JSONL file and write an event."""
        tracker = SessionTracker(memory_dir)
        tracker.track_event("test_event", {"key": "value"})

        events_path = Path(memory_dir) / "session_events.jsonl"
        assert events_path.exists()
        content = events_path.read_text(encoding="utf-8").strip()
        event = json.loads(content)
        assert event["type"] == "test_event"
        assert event["data"] == {"key": "value"}
        assert "timestamp" in event

    def test_track_event_appends(self, memory_dir):
        """Multiple track_event calls should append to the same file."""
        tracker = SessionTracker(memory_dir)
        tracker.track_event("first", {"n": 1})
        tracker.track_event("second", {"n": 2})

        events_path = Path(memory_dir) / "session_events.jsonl"
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["type"] == "first"
        assert json.loads(lines[1])["type"] == "second"

    def test_track_event_no_data(self, memory_dir):
        """track_event with no data should store empty dict."""
        tracker = SessionTracker(memory_dir)
        tracker.track_event("empty_event")

        events = tracker.get_recent_events(1)
        assert events[0]["data"] == {}

    def test_track_event_creates_memory_dir(self, tmp_path):
        """track_event should create the memory directory if it does not exist."""
        mem = str(tmp_path / "nonexistent" / "memory")
        tracker = SessionTracker(mem)
        tracker.track_event("test", {"x": 1})
        assert Path(mem).exists()

    def test_get_recent_events_returns_correct_count(self, memory_dir):
        """get_recent_events should return the last n events."""
        tracker = SessionTracker(memory_dir)
        for i in range(10):
            tracker.track_event("event", {"i": i})

        events = tracker.get_recent_events(3)
        assert len(events) == 3
        assert events[0]["data"]["i"] == 7
        assert events[1]["data"]["i"] == 8
        assert events[2]["data"]["i"] == 9

    def test_get_recent_events_empty_file(self, memory_dir):
        """get_recent_events on nonexistent file should return empty list."""
        tracker = SessionTracker(memory_dir)
        assert tracker.get_recent_events() == []

    def test_get_recent_events_handles_invalid_json(self, memory_dir):
        """get_recent_events should skip lines with invalid JSON."""
        events_path = Path(memory_dir) / "session_events.jsonl"
        events_path.write_text(
            'invalid json line\n{"type": "valid", "timestamp": 1.0, "data": {}}\n',
            encoding="utf-8",
        )
        tracker = SessionTracker(memory_dir)
        events = tracker.get_recent_events(10)
        assert len(events) == 1
        assert events[0]["type"] == "valid"

    def test_build_resume_snapshot_no_data(self, memory_dir):
        """build_resume_snapshot with no events returns no_session_data."""
        tracker = SessionTracker(memory_dir)
        snapshot = tracker.build_resume_snapshot()
        assert snapshot["status"] == "no_session_data"
        assert snapshot["events_count"] == 0

    def test_build_resume_snapshot_with_events(self, memory_dir):
        """build_resume_snapshot extracts node transitions and iteration count."""
        tracker = SessionTracker(memory_dir)
        tracker.track_event("node_enter", {"node": "init"})
        tracker.track_event("iteration_complete", {"node": "init"})
        tracker.track_event("node_enter", {"node": "plan"})
        tracker.track_event("error", {"message": "something failed"})
        tracker.track_event("iteration_complete", {"node": "plan"})

        snapshot = tracker.build_resume_snapshot()
        assert snapshot["status"] == "has_session_data"
        assert snapshot["events_count"] == 5
        assert snapshot["last_node"] == "plan"
        assert snapshot["iteration_count"] == 2
        assert snapshot["node_path"] == ["init", "plan"]
        assert snapshot["recent_errors"] == ["something failed"]

    def test_build_resume_snapshot_limits_node_path(self, memory_dir):
        """build_resume_snapshot limits node_path to last 10 transitions."""
        tracker = SessionTracker(memory_dir)
        for i in range(15):
            tracker.track_event("node_enter", {"node": f"node_{i}"})

        snapshot = tracker.build_resume_snapshot()
        assert len(snapshot["node_path"]) == 10
        assert snapshot["node_path"][0] == "node_5"
        assert snapshot["node_path"][-1] == "node_14"

    def test_build_resume_snapshot_limits_errors(self, memory_dir):
        """build_resume_snapshot limits recent_errors to last 5."""
        tracker = SessionTracker(memory_dir)
        for i in range(8):
            tracker.track_event("error", {"message": f"error_{i}"})

        snapshot = tracker.build_resume_snapshot()
        assert len(snapshot["recent_errors"]) == 5
        assert snapshot["recent_errors"][0] == "error_3"

    def test_get_event_count(self, memory_dir):
        """get_event_count returns total number of events."""
        tracker = SessionTracker(memory_dir)
        assert tracker.get_event_count() == 0

        tracker.track_event("a")
        tracker.track_event("b")
        tracker.track_event("c")
        assert tracker.get_event_count() == 3

    def test_pruning(self, memory_dir):
        """Events beyond max_events should be pruned."""
        tracker = SessionTracker(memory_dir, max_events=5)
        for i in range(10):
            tracker.track_event("event", {"i": i})

        events_path = Path(memory_dir) / "session_events.jsonl"
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 5
        # Should keep the last 5 events
        first_event = json.loads(lines[0])
        assert first_event["data"]["i"] == 5

    def test_timestamp_increases(self, memory_dir):
        """Each event should have a monotonically non-decreasing timestamp."""
        tracker = SessionTracker(memory_dir)
        tracker.track_event("first")
        tracker.track_event("second")

        events = tracker.get_recent_events(2)
        assert events[1]["timestamp"] >= events[0]["timestamp"]
