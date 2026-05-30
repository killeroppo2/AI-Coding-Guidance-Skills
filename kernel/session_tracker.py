"""Session event tracking for iteration-level observability.

Inspired by context-mode's SessionDB, this module provides lightweight
event tracking for the kernel's execution loop, enabling resume context
and session analytics.
"""

import json
import time
from pathlib import Path
from typing import Any


def _safe_serialize(obj: Any) -> Any:
    """Convert non-serializable objects to string representations.

    Args:
        obj: Any object to make JSON-safe.

    Returns:
        A JSON-serializable version of the object.
    """
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(item) for item in obj]
    if isinstance(obj, (set, frozenset)):
        return [_safe_serialize(item) for item in sorted(obj, key=str)]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    # Fallback: convert to string
    try:
        return str(obj)
    except Exception:
        return "<unserializable>"


class SessionTracker:
    """Tracks session events to memory/session_events.jsonl.

    Events are appended in JSONL format for easy streaming reads.
    Provides resume snapshot generation and event querying.
    """

    def __init__(self, memory_dir: str, max_events: int = 1000, flush_interval: int = 10) -> None:
        """Initialize the session tracker.

        Args:
            memory_dir: Path to the memory directory.
            max_events: Maximum events to retain in the log file.
            flush_interval: Number of events to buffer before flushing to disk.
        """
        self.memory_dir = Path(memory_dir)
        self.events_path = self.memory_dir / "session_events.jsonl"
        self.max_events = max_events
        self._prune_threshold = int(max_events * 1.1)
        self._flush_interval = flush_interval
        self._buffer: list[dict] = []

    def track_event(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Append an event to the session log.

        Handles non-serializable objects by converting them to string
        representations. This ensures tracking never crashes even with
        unexpected data types (Path objects, datetime, custom classes).

        Control characters in event_type are stripped. Data is serialized
        safely regardless of size or nesting depth.

        Args:
            event_type: Type of event (e.g. node_enter, iteration_complete).
            data: Optional dict of event-specific data.
        """
        # Strip control characters from event type for safety
        clean_type = "".join(ch for ch in event_type if ch >= " " or ch in "\t\n")
        if not clean_type:
            clean_type = "unknown"
        safe_data = _safe_serialize(data) if data else {}
        event = {
            "timestamp": time.time(),
            "type": clean_type,
            "data": safe_data,
        }
        self._buffer.append(event)
        if len(self._buffer) >= self._flush_interval:
            self.flush()

    def flush(self) -> None:
        """Write buffered events to disk.

        Best-effort: swallows IO errors to avoid crashing the kernel.
        """
        if not self._buffer:
            return
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.events_path, "a", encoding="utf-8") as f:
                for event in self._buffer:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._buffer.clear()
            self._prune_if_needed()
        except (OSError, ValueError):
            pass  # Best-effort flush

    def get_recent_events(self, n: int = 20) -> list[dict[str, Any]]:
        """Return the last n events.

        Args:
            n: Number of recent events to return.

        Returns:
            List of event dicts, most recent last.
        """
        if not self.events_path.exists():
            return []
        lines = self.events_path.read_text(encoding="utf-8").strip().splitlines()
        events = []
        for line in lines[-n:]:
            try:
                events.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue
        return events

    def build_resume_snapshot(self) -> dict[str, Any]:
        """Build a concise resume context from session events.

        Returns:
            A dict summarizing session state for resume purposes.
        """
        events = self.get_recent_events(50)
        if not events:
            return {"status": "no_session_data", "events_count": 0}

        node_transitions: list[str] = []
        last_node: str | None = None
        iteration_count = 0
        errors: list[str] = []

        for ev in events:
            if ev.get("type") == "node_enter":
                node = ev.get("data", {}).get("node", "unknown")
                node_transitions.append(node)
                last_node = node
            elif ev.get("type") == "iteration_complete":
                iteration_count += 1
            elif ev.get("type") == "error":
                errors.append(ev.get("data", {}).get("message", "unknown error"))

        return {
            "status": "has_session_data",
            "events_count": len(events),
            "last_node": last_node,
            "iteration_count": iteration_count,
            "node_path": node_transitions[-10:],
            "recent_errors": errors[-5:],
        }

    def get_event_count(self) -> int:
        """Return total number of events in the log.

        Returns:
            Integer count of events.
        """
        if not self.events_path.exists():
            return 0
        return sum(1 for _ in open(self.events_path, encoding="utf-8"))

    def _prune_if_needed(self) -> None:
        """Keep only the last max_events entries.

        Uses a 10% buffer threshold to avoid re-reading the file on every
        single write. Only prunes when count exceeds max_events * 1.1.
        """
        if not self.events_path.exists():
            return
        lines = self.events_path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) > self._prune_threshold:
            pruned = lines[-self.max_events :]
            self.events_path.write_text("\n".join(pruned) + "\n", encoding="utf-8")
