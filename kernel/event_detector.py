"""External event detection for user modifications.

Detects files modified by the user (not by the kernel) to prevent
evolution from overwriting user edits and to incorporate external feedback.
"""

import os
from datetime import datetime, timezone
from pathlib import Path


class EventDetector:
    """Detects external changes to kernel-managed files."""

    def __init__(self, kernel_root: Path) -> None:
        """Initialize the event detector.

        Args:
            kernel_root: Path to the project root directory.
        """
        self.kernel_root = kernel_root
        # Directories to scan and their event types
        self._scan_config = {
            "kernel/prompts": "prompt_modified",
            "knowledge/rules": "new_rule_added",
            "memory": "note_left",
        }

    def detect_external_changes(self, last_updated: str) -> list[dict]:
        """Detect files modified after the given timestamp.

        Scans configured directories for files whose modification time
        is newer than last_updated.

        Args:
            last_updated: ISO format timestamp of last kernel state save.

        Returns:
            List of event dicts with keys: type, path, modified_at.
            Empty list if no external changes detected.
        """
        if not last_updated:
            return []

        try:
            ref_time = datetime.fromisoformat(last_updated)
        except (ValueError, TypeError):
            return []

        events = []
        for rel_dir, event_type in self._scan_config.items():
            scan_dir = self.kernel_root / rel_dir
            if not scan_dir.exists():
                continue
            for filepath in scan_dir.rglob("*"):
                if not filepath.is_file():
                    continue
                # Skip internal files like _index.yaml, __pycache__
                if filepath.name.startswith("_") or "__pycache__" in str(filepath):
                    continue
                try:
                    mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc)
                except OSError:
                    continue
                if mtime > ref_time:
                    # Determine specific event type
                    actual_type = event_type
                    if event_type == "note_left" and filepath.name == "tasks.yaml":
                        actual_type = "manual_task_added"
                    events.append({
                        "type": actual_type,
                        "path": str(filepath.relative_to(self.kernel_root)),
                        "modified_at": mtime.isoformat(),
                    })
        return events

    def get_user_owned_files(self, state: dict) -> list[str]:
        """Get list of user-owned files from state.

        Args:
            state: The state dict (from StateManager).

        Returns:
            List of file paths that the user owns.
        """
        return state.get("user_owned_files", [])

    def mark_user_owned(self, state: dict, file_path: str) -> None:
        """Mark a file as user-owned in state.

        Args:
            state: The state dict to modify.
            file_path: Path to mark as user-owned.
        """
        owned = state.setdefault("user_owned_files", [])
        if file_path not in owned:
            owned.append(file_path)

    def is_user_owned(self, state: dict, file_path: str) -> bool:
        """Check if a file is user-owned.

        Args:
            state: The state dict.
            file_path: Path to check.

        Returns:
            True if the file is in user_owned_files list.
        """
        return file_path in state.get("user_owned_files", [])
