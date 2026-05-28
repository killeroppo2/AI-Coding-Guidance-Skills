"""Tests for kernel/session_tracker.py."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from kernel.session_tracker import SessionTracker, _safe_serialize


@pytest.fixture
def memory_dir(tmp_path):
    """Create a temporary memory directory."""
    mem = tmp_path / "memory"
    mem.mkdir()
    return str(mem)


class TestSafeSerialize:
    """Tests for _safe_serialize helper."""

    def test_primitives_pass_through(self):
        """Primitive types pass through unchanged."""
        assert _safe_serialize("hello") == "hello"
        assert _safe_serialize(42) == 42
        assert _safe_serialize(3.14) == 3.14
        assert _safe_serialize(True) is True
        assert _safe_serialize(None) is None

    def test_path_converted_to_string(self):
        """Path objects are converted to strings."""
        result = _safe_serialize(Path("/tmp/test.py"))
        assert result == "/tmp/test.py"
        assert isinstance(result, str)

    def test_datetime_converted_to_string(self):
        """datetime objects are converted to string representation."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = _safe_serialize(dt)
        assert "2024" in result
        assert isinstance(result, str)

    def test_nested_dict_with_non_serializable(self):
        """Nested dicts with non-serializable values are handled."""
        data = {"path": Path("/tmp"), "nested": {"ts": datetime.now()}}
        result = _safe_serialize(data)
        assert isinstance(result, dict)
        assert result["path"] == "/tmp"
        assert isinstance(result["nested"]["ts"], str)

    def test_list_with_non_serializable(self):
        """Lists with non-serializable items are handled."""
        data = [Path("/a"), Path("/b"), 42]
        result = _safe_serialize(data)
        assert result == ["/a", "/b", 42]

    def test_set_converted_to_sorted_list(self):
        """Sets are converted to sorted lists."""
        data = {3, 1, 2}
        result = _safe_serialize(data)
        assert result == [1, 2, 3]

    def test_bytes_decoded(self):
        """Bytes are decoded to string."""
        result = _safe_serialize(b"hello bytes")
        assert result == "hello bytes"

    def test_tuple_converted_to_list(self):
        """Tuples are converted to lists."""
        result = _safe_serialize((1, "a", Path("/x")))
        assert result == [1, "a", "/x"]

    def test_custom_object_uses_str(self):
        """Custom objects fall back to str()."""

        class CustomObj:
            def __str__(self):
                return "custom_repr"

        result = _safe_serialize(CustomObj())
        assert result == "custom_repr"


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

    def test_track_event_with_path_objects(self, memory_dir):
        """track_event handles Path objects in data gracefully."""
        tracker = SessionTracker(memory_dir)
        tracker.track_event("file_op", {"path": Path("/tmp/test.py"), "backup": Path("./bak")})

        events = tracker.get_recent_events(1)
        assert events[0]["data"]["path"] == "/tmp/test.py"
        assert events[0]["data"]["backup"] == "bak"

    def test_track_event_with_datetime(self, memory_dir):
        """track_event handles datetime objects in data gracefully."""
        tracker = SessionTracker(memory_dir)
        dt = datetime(2024, 6, 15, 12, 0, 0)
        tracker.track_event("timed", {"started": dt})

        events = tracker.get_recent_events(1)
        assert "2024" in events[0]["data"]["started"]

    def test_track_event_with_nested_non_serializable(self, memory_dir):
        """track_event handles nested non-serializable objects."""
        tracker = SessionTracker(memory_dir)
        tracker.track_event(
            "complex",
            {
                "files": [Path("/a"), Path("/b")],
                "meta": {"created": datetime(2024, 1, 1)},
            },
        )

        events = tracker.get_recent_events(1)
        assert events[0]["data"]["files"] == ["/a", "/b"]
        assert "2024" in events[0]["data"]["meta"]["created"]

    def test_track_event_with_unicode(self, memory_dir):
        """track_event handles Unicode data correctly."""
        tracker = SessionTracker(memory_dir)
        tracker.track_event(
            "unicode_test",
            {
                "message": "Hello \u4e16\u754c",
                "emoji": "\U0001f680",
                "japanese": "\u3053\u3093\u306b\u3061\u306f",
            },
        )

        events = tracker.get_recent_events(1)
        assert events[0]["data"]["message"] == "Hello \u4e16\u754c"
        assert events[0]["data"]["emoji"] == "\U0001f680"
        assert events[0]["data"]["japanese"] == "\u3053\u3093\u306b\u3061\u306f"

    def test_track_event_with_none_values(self, memory_dir):
        """track_event handles None values in data dict."""
        tracker = SessionTracker(memory_dir)
        tracker.track_event("nullable", {"result": None, "count": 0})

        events = tracker.get_recent_events(1)
        assert events[0]["data"]["result"] is None
        assert events[0]["data"]["count"] == 0

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

    def test_get_recent_events_handles_corrupted_file(self, memory_dir):
        """get_recent_events handles file with partial/corrupted JSON lines."""
        events_path = Path(memory_dir) / "session_events.jsonl"
        # Simulate corruption: truncated line, empty line, partial JSON
        content = (
            '{"type": "good1", "timestamp": 1.0, "data": {}}\n'
            '{"type": "trun\n'
            "\n"
            '{"unclosed": true\n'
            '{"type": "good2", "timestamp": 2.0, "data": {"x": 1}}\n'
        )
        events_path.write_text(content, encoding="utf-8")
        tracker = SessionTracker(memory_dir)
        events = tracker.get_recent_events(10)
        assert len(events) == 2
        assert events[0]["type"] == "good1"
        assert events[1]["type"] == "good2"

    def test_get_recent_events_handles_empty_lines(self, memory_dir):
        """get_recent_events handles file with empty lines gracefully."""
        events_path = Path(memory_dir) / "session_events.jsonl"
        events_path.write_text(
            '\n\n{"type": "valid", "timestamp": 1.0, "data": {}}\n\n',
            encoding="utf-8",
        )
        tracker = SessionTracker(memory_dir)
        events = tracker.get_recent_events(10)
        assert len(events) == 1

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

        # With 10% buffer (threshold=5), pruning occurs at 6 events
        # After 10 writes, final prune keeps last 5
        events_path = Path(memory_dir) / "session_events.jsonl"
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) <= 5 + 1  # at most max_events + buffer remainder
        # Most recent events are kept
        last_event = json.loads(lines[-1])
        assert last_event["data"]["i"] == 9

    def test_pruning_with_buffer(self, memory_dir):
        """Pruning uses a 10% buffer to avoid constant rewriting.

        With max_events=10, threshold is 11. So writing 11 events does NOT
        trigger a prune, but writing 12 does (prune back to 10).
        """
        tracker = SessionTracker(memory_dir, max_events=10)
        # Write exactly 11 events (threshold is int(10*1.1) = 11)
        for i in range(11):
            tracker.track_event("event", {"i": i})

        events_path = Path(memory_dir) / "session_events.jsonl"
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        # 11 events written, threshold=11, so > 11 is needed to prune
        assert len(lines) == 11

        # Write one more (12 total > 11 threshold triggers prune to 10)
        tracker.track_event("event", {"i": 11})
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 10
        # Verify the oldest are gone, newest kept
        first = json.loads(lines[0])
        last = json.loads(lines[-1])
        assert first["data"]["i"] == 2
        assert last["data"]["i"] == 11

    def test_pruning_exact_boundary(self, memory_dir):
        """Write exactly max_events=10, write 15, verify bounded near max_events."""
        tracker = SessionTracker(memory_dir, max_events=10)
        for i in range(15):
            tracker.track_event("event", {"i": i})

        events_path = Path(memory_dir) / "session_events.jsonl"
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        # With 10% buffer (threshold=11), final file may have up to threshold lines
        assert len(lines) <= tracker._prune_threshold
        assert len(lines) >= 10
        # Most recent event is always preserved
        last_event = json.loads(lines[-1])
        assert last_event["data"]["i"] == 14

    def test_resume_flow_integration(self, memory_dir):
        """Simulate the resume flow: write events, build snapshot, verify."""
        tracker = SessionTracker(memory_dir)
        # Simulate a session: start, init node, plan node, error, complete
        tracker.track_event("session_start", {"goal": "build calculator", "mode": "mode3"})
        tracker.track_event("node_enter", {"node": "init"})
        tracker.track_event("iteration_complete", {"node": "init", "next_node": "plan"})
        tracker.track_event("node_enter", {"node": "plan"})
        tracker.track_event("error", {"message": "AI timeout on plan node"})
        tracker.track_event("node_enter", {"node": "plan"})
        tracker.track_event("iteration_complete", {"node": "plan", "next_node": "code"})
        tracker.track_event("node_enter", {"node": "code"})

        # Build resume snapshot
        snapshot = tracker.build_resume_snapshot()

        # Verify snapshot contains useful resume info
        assert snapshot["status"] == "has_session_data"
        assert snapshot["events_count"] == 8
        assert snapshot["last_node"] == "code"
        assert snapshot["iteration_count"] == 2
        assert "init" in snapshot["node_path"]
        assert "plan" in snapshot["node_path"]
        assert "code" in snapshot["node_path"]
        assert snapshot["recent_errors"] == ["AI timeout on plan node"]

    def test_build_resume_snapshot_missing_file(self, tmp_path):
        """build_resume_snapshot handles non-existent session_events.jsonl."""
        mem = str(tmp_path / "empty_memory")
        # Don't create the directory - tracker should handle gracefully
        tracker = SessionTracker(mem)
        snapshot = tracker.build_resume_snapshot()
        assert snapshot["status"] == "no_session_data"
        assert snapshot["events_count"] == 0


class TestSessionStatsOutput:
    """Tests for --session-stats CLI output format (Round 16)."""

    def test_session_stats_no_events(self, tmp_path, monkeypatch, capsys):
        """--session-stats with no events produces structured output."""
        from kernel import orchestrator

        # Set up minimal environment
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
        import yaml

        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        monkeypatch.setattr(orchestrator, "KERNEL_ROOT", tmp_path)
        orchestrator.main(["--session-stats"])

        captured = capsys.readouterr()
        assert "=== Session Statistics ===" in captured.out
        assert "Events: 0" in captured.out
        assert "Status: no_session_data" in captured.out
        assert "Last node: none" in captured.out
        assert "Recent path: no events" in captured.out
        assert "No session events recorded" in captured.out

    def test_session_stats_with_events(self, tmp_path, monkeypatch, capsys):
        """--session-stats with events produces structured output."""
        from kernel import orchestrator

        # Set up minimal environment
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_data = {
            "current_node": "plan",
            "iteration_count": 3,
            "max_iterations": 30,
            "goal": "test",
            "status": "running",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "running"},
        }
        import yaml

        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        # Write some events
        tracker = SessionTracker(str(memory_dir))
        tracker.track_event("node_enter", {"node": "init"})
        tracker.track_event("iteration_complete", {"node": "init", "next_node": "plan"})
        tracker.track_event("node_enter", {"node": "plan"})

        monkeypatch.setattr(orchestrator, "KERNEL_ROOT", tmp_path)
        orchestrator.main(["--session-stats"])

        captured = capsys.readouterr()
        assert "=== Session Statistics ===" in captured.out
        assert "Events: 3" in captured.out
        assert "Status: has_session_data" in captured.out
        assert "Last node: plan" in captured.out
        assert "Recent path: init -> plan" in captured.out

    def test_timestamp_increases(self, memory_dir):
        """Each event should have a monotonically non-decreasing timestamp."""
        tracker = SessionTracker(memory_dir)
        tracker.track_event("first")
        tracker.track_event("second")

        events = tracker.get_recent_events(2)
        assert events[1]["timestamp"] >= events[0]["timestamp"]
