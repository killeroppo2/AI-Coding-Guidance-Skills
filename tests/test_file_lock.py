"""Tests for file locking, atomic writes, and concurrency safety."""

import json
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from kernel.file_lock import FileLock
from kernel.atomic_write import atomic_write
from memory.state_manager import StateManager


class TestFileLockBasic:
    """Tests for FileLock acquire/release basic flow."""

    def test_acquire_release(self, tmp_path):
        """FileLock acquire and release creates/removes lock file."""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        assert lock.acquire()
        assert lock_path.exists()
        lock.release()
        assert not lock_path.exists()

    def test_acquire_fails_when_locked(self, tmp_path):
        """FileLock acquire fails (returns False) when already locked."""
        lock_path = tmp_path / "test.lock"
        lock1 = FileLock(lock_path)
        lock2 = FileLock(lock_path, timeout=0.5)
        assert lock1.acquire()
        assert not lock2.acquire(timeout=0.5)
        lock1.release()

    def test_lock_file_contains_json(self, tmp_path):
        """Lock file contains valid JSON with pid and timestamp."""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock.acquire()
        with open(lock_path) as f:
            data = json.load(f)
        assert "pid" in data
        assert "timestamp" in data
        assert "host" in data
        assert data["pid"] == os.getpid()
        lock.release()

    def test_release_without_acquire_is_noop(self, tmp_path):
        """Releasing without acquiring does not raise."""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock.release()  # Should not raise

    def test_is_locked(self, tmp_path):
        """is_locked returns True when lock file exists."""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        assert not lock.is_locked()
        lock.acquire()
        assert lock.is_locked()
        lock.release()
        assert not lock.is_locked()


class TestFileLockStale:
    """Tests for stale lock detection."""

    def test_is_stale_returns_true_for_old_locks(self, tmp_path):
        """is_stale returns True for locks older than max_age."""
        lock_path = tmp_path / "test.lock"
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=700)).isoformat()
        lock_data = {"pid": 12345, "timestamp": old_time, "host": "test"}
        with open(lock_path, "w") as f:
            json.dump(lock_data, f)
        assert FileLock.is_stale(lock_path, max_age_seconds=600)

    def test_is_stale_returns_false_for_fresh_locks(self, tmp_path):
        """is_stale returns False for locks newer than max_age."""
        lock_path = tmp_path / "test.lock"
        fresh_time = datetime.now(timezone.utc).isoformat()
        lock_data = {"pid": 12345, "timestamp": fresh_time, "host": "test"}
        with open(lock_path, "w") as f:
            json.dump(lock_data, f)
        assert not FileLock.is_stale(lock_path, max_age_seconds=600)

    def test_is_stale_returns_false_when_no_lock(self, tmp_path):
        """is_stale returns False when lock file does not exist."""
        lock_path = tmp_path / "nonexistent.lock"
        assert not FileLock.is_stale(lock_path)

    def test_is_stale_returns_true_for_invalid_json(self, tmp_path):
        """is_stale returns True for lock files with invalid JSON."""
        lock_path = tmp_path / "test.lock"
        with open(lock_path, "w") as f:
            f.write("not valid json")
        assert FileLock.is_stale(lock_path)

    def test_is_stale_returns_true_for_missing_timestamp(self, tmp_path):
        """is_stale returns True when timestamp field is empty."""
        lock_path = tmp_path / "test.lock"
        with open(lock_path, "w") as f:
            json.dump({"pid": 123, "timestamp": "", "host": "test"}, f)
        assert FileLock.is_stale(lock_path)


class TestFileLockForceRelease:
    """Tests for force_release."""

    def test_force_release_removes_lock(self, tmp_path):
        """force_release removes an existing lock file."""
        lock_path = tmp_path / "test.lock"
        lock_path.write_text("{}")
        assert FileLock.force_release(lock_path)
        assert not lock_path.exists()

    def test_force_release_returns_false_when_no_lock(self, tmp_path):
        """force_release returns False when lock file does not exist."""
        lock_path = tmp_path / "nonexistent.lock"
        assert not FileLock.force_release(lock_path)


class TestFileLockContextManager:
    """Tests for context manager support."""

    def test_context_manager_acquires_and_releases(self, tmp_path):
        """Context manager acquires on enter and releases on exit."""
        lock_path = tmp_path / "test.lock"
        with FileLock(lock_path) as lock:
            assert lock_path.exists()
            assert lock._acquired
        assert not lock_path.exists()

    def test_context_manager_raises_timeout_error(self, tmp_path):
        """Context manager raises TimeoutError when lock cannot be acquired."""
        lock_path = tmp_path / "test.lock"
        # Pre-create the lock file to block acquisition
        lock_path.write_text('{"pid": 1, "timestamp": "2025-01-01T00:00:00+00:00", "host": "x"}')
        with pytest.raises(TimeoutError, match="Could not acquire lock"):
            with FileLock(lock_path, timeout=0.3):
                pass


class TestFileLockConcurrency:
    """Tests for concurrent access with threading."""

    def test_concurrent_lock_acquisition(self, tmp_path):
        """Two threads trying to acquire same lock - only one succeeds at a time."""
        lock_path = tmp_path / "test.lock"
        results = []
        barrier = threading.Barrier(2, timeout=5)

        def worker(worker_id):
            barrier.wait()
            lock = FileLock(lock_path, timeout=2.0)
            acquired = lock.acquire(timeout=2.0)
            if acquired:
                results.append(f"acquired-{worker_id}")
                time.sleep(0.2)
                lock.release()
                results.append(f"released-{worker_id}")
            else:
                results.append(f"failed-{worker_id}")

        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # Both threads should eventually acquire (one waits for the other)
        acquired_count = sum(1 for r in results if r.startswith("acquired"))
        assert acquired_count == 2


class TestAtomicWrite:
    """Tests for atomic_write function."""

    def test_atomic_write_creates_file(self, tmp_path):
        """atomic_write creates a file with correct content."""
        target = tmp_path / "output.txt"
        atomic_write(target, "hello world")
        assert target.read_text() == "hello world"

    def test_atomic_write_creates_parent_directories(self, tmp_path):
        """atomic_write creates parent directories if they do not exist."""
        target = tmp_path / "sub" / "dir" / "output.txt"
        atomic_write(target, "nested content")
        assert target.read_text() == "nested content"

    def test_atomic_write_temp_file_cleanup_on_failure(self, tmp_path):
        """atomic_write cleans up temp file when write fails."""
        target = tmp_path / "output.txt"
        with patch("kernel.atomic_write.os.rename", side_effect=OSError("rename failed")):
            with pytest.raises(OSError, match="rename failed"):
                atomic_write(target, "content")
        # No temp files should remain
        remaining = list(tmp_path.glob("*.tmp"))
        assert len(remaining) == 0

    def test_atomic_write_overwrites_existing(self, tmp_path):
        """atomic_write overwrites existing file content."""
        target = tmp_path / "output.txt"
        target.write_text("old content")
        atomic_write(target, "new content")
        assert target.read_text() == "new content"


class TestStateManagerAtomicWrite:
    """Tests for StateManager using atomic writes."""

    def test_save_state_uses_atomic_write(self, tmp_path):
        """StateManager.save_state writes state file correctly."""
        state_path = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        sm = StateManager(str(state_path), str(memory_dir))
        sm.state["goal"] = "test goal"
        sm.save_state()
        assert state_path.exists()
        with open(state_path) as f:
            data = yaml.safe_load(f)
        assert data["goal"] == "test goal"
        assert "last_updated" in data


class TestStateManagerAdvisoryLocks:
    """Tests for advisory locking on JSONL operations."""

    def test_record_decision_with_lock(self, tmp_path):
        """record_decision writes decision and no lock file remains."""
        state_path = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        sm = StateManager(str(state_path), str(memory_dir))
        sm.record_decision({"action": "test_decision"})
        filepath = memory_dir / "decisions.jsonl"
        assert filepath.exists()
        lines = filepath.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["action"] == "test_decision"
        assert "timestamp" in data
        # Lock file should not remain
        lock_path = filepath.with_suffix(".jsonl.lock")
        assert not lock_path.exists()

    def test_record_reflection_with_lock(self, tmp_path):
        """record_reflection writes reflection and no lock file remains."""
        state_path = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        sm = StateManager(str(state_path), str(memory_dir))
        sm.record_reflection({"insight": "test_reflection"})
        filepath = memory_dir / "reflections.jsonl"
        assert filepath.exists()
        lines = filepath.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["insight"] == "test_reflection"
        # Lock file should not remain
        lock_path = filepath.with_suffix(".jsonl.lock")
        assert not lock_path.exists()


class TestStateManagerRunnerLock:
    """Tests for runner lock management."""

    def test_check_runner_lock_no_lock(self, tmp_path):
        """check_runner_lock returns (False, '') when no lock exists."""
        state_path = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        sm = StateManager(str(state_path), str(memory_dir))
        locked, msg = sm.check_runner_lock()
        assert not locked
        assert msg == ""

    def test_acquire_and_check_runner_lock(self, tmp_path):
        """acquire_runner_lock creates lock, check_runner_lock detects it."""
        state_path = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        sm = StateManager(str(state_path), str(memory_dir))
        sm.acquire_runner_lock()
        locked, msg = sm.check_runner_lock()
        assert locked
        assert "Runner already active since" in msg

    def test_release_runner_lock(self, tmp_path):
        """release_runner_lock removes the lock file."""
        state_path = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        sm = StateManager(str(state_path), str(memory_dir))
        sm.acquire_runner_lock()
        sm.release_runner_lock()
        locked, msg = sm.check_runner_lock()
        assert not locked
        assert msg == ""

    def test_check_runner_lock_stale(self, tmp_path):
        """check_runner_lock returns (False, '') for stale locks."""
        state_path = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        sm = StateManager(str(state_path), str(memory_dir))
        # Create a stale lock (older than 600s)
        runner_lock_path = memory_dir / "runner.lock"
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=700)).isoformat()
        with open(runner_lock_path, "w") as f:
            json.dump({"pid": 9999, "timestamp": old_time, "host": "test"}, f)
        locked, msg = sm.check_runner_lock()
        assert not locked
        assert msg == ""

    def test_release_runner_lock_no_lock(self, tmp_path):
        """release_runner_lock does not raise when no lock exists."""
        state_path = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        sm = StateManager(str(state_path), str(memory_dir))
        sm.release_runner_lock()  # Should not raise

    def test_get_lock_path(self, tmp_path):
        """_get_lock_path returns state path with .yaml.lock suffix."""
        state_path = tmp_path / "state.yaml"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        sm = StateManager(str(state_path), str(memory_dir))
        lock_path = sm._get_lock_path()
        assert lock_path == tmp_path / "state.yaml.lock"
