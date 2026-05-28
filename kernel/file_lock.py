"""File-based locking for concurrency safety."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


class FileLock:
    """Simple file-based lock using atomic file creation.

    Uses os.open with O_CREAT|O_EXCL for atomic lock acquisition.
    Lock file contains JSON with pid and timestamp.
    """

    def __init__(self, lock_path: str | Path, timeout: float = 10.0):
        self.lock_path = Path(lock_path)
        self._default_timeout = timeout
        self._acquired = False

    def acquire(self, timeout: float = 10.0, poll_interval: float = 0.1) -> bool:
        """Attempt to acquire the lock within timeout.

        Creates lock file atomically with O_CREAT|O_EXCL.
        Lock file contains: {"pid": <pid>, "timestamp": <iso>, "host": <hostname>}

        Returns True if acquired, False if timeout.
        """
        deadline = time.monotonic() + timeout
        while True:
            try:
                fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                lock_info = {
                    "pid": os.getpid(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "host": os.uname().nodename,
                }
                with os.fdopen(fd, "w") as f:
                    json.dump(lock_info, f)
                self._acquired = True
                return True
            except FileExistsError:
                if time.monotonic() >= deadline:
                    return False
                time.sleep(poll_interval)

    def release(self) -> None:
        """Release the lock by removing the lock file."""
        if self._acquired:
            try:
                os.unlink(str(self.lock_path))
            except FileNotFoundError:
                pass
            self._acquired = False

    def is_locked(self) -> bool:
        """Check if lock file exists."""
        return self.lock_path.exists()

    @classmethod
    def is_stale(cls, lock_path: str | Path, max_age_seconds: float = 600) -> bool:
        """Check if an existing lock is stale (older than max_age_seconds).

        Reads the timestamp from lock file JSON.
        Returns True if lock exists and is older than max_age.
        Returns False if lock doesn't exist or is fresh.
        """
        lock_path = Path(lock_path)
        if not lock_path.exists():
            return False
        try:
            with open(lock_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            timestamp_str = data.get("timestamp", "")
            if not timestamp_str:
                return True
            lock_time = datetime.fromisoformat(timestamp_str)
            age = (datetime.now(timezone.utc) - lock_time).total_seconds()
            return age > max_age_seconds
        except (json.JSONDecodeError, ValueError, OSError):
            return True

    @classmethod
    def force_release(cls, lock_path: str | Path) -> bool:
        """Force-remove a lock file regardless of ownership.

        Returns True if lock was removed, False if it didn't exist.
        """
        lock_path = Path(lock_path)
        try:
            os.unlink(str(lock_path))
            return True
        except FileNotFoundError:
            return False

    def __enter__(self):
        if not self.acquire(timeout=self._default_timeout):
            raise TimeoutError(f"Could not acquire lock: {self.lock_path}")
        return self

    def __exit__(self, *args):
        self.release()
