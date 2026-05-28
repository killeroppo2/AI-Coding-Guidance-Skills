"""Tests for kernel/lifecycle_guard.py."""

import os
import threading
import time
from unittest.mock import MagicMock, patch

from kernel.lifecycle_guard import LifecycleGuard


class TestLifecycleGuardStartStop:
    """Tests for LifecycleGuard start/stop lifecycle."""

    def test_start_and_stop(self):
        """Guard starts and stops cleanly."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=60.0)
        guard.start()
        assert guard._running is True
        assert guard._thread is not None
        assert guard._thread.is_alive()
        guard.stop()
        assert guard._running is False
        assert guard._thread is None
        callback.assert_not_called()

    def test_stop_without_start(self):
        """Stop is safe to call without start."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback)
        guard.stop()  # Should not raise
        assert guard._running is False

    def test_stop_prevents_further_checks(self):
        """After stop, no more checks run."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=0.05)
        guard.start()
        guard.stop()
        time.sleep(0.15)
        callback.assert_not_called()

    def test_default_check_interval(self):
        """Default check interval is 30 seconds."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback)
        assert guard._check_interval == 30.0

    def test_custom_check_interval(self):
        """Custom check interval is respected."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=5.0)
        assert guard._check_interval == 5.0


class TestIsParentAlive:
    """Tests for LifecycleGuard.is_parent_alive."""

    def test_parent_alive_returns_true(self):
        """is_parent_alive returns True when parent exists."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback)
        guard._initial_ppid = os.getppid()
        assert guard.is_parent_alive() is True

    def test_parent_alive_when_initial_ppid_is_none(self):
        """is_parent_alive returns True when initial_ppid is None (can't check)."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback)
        guard._initial_ppid = None
        assert guard.is_parent_alive() is True

    @patch("kernel.lifecycle_guard.os.getppid")
    def test_orphan_detected_when_ppid_changes(self, mock_getppid):
        """is_parent_alive returns False when ppid changes."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback)
        guard._initial_ppid = 12345
        mock_getppid.return_value = 1  # Changed to init
        assert guard.is_parent_alive() is False

    @patch("kernel.lifecycle_guard.os.getppid")
    def test_orphan_detected_when_ppid_different(self, mock_getppid):
        """is_parent_alive returns False when ppid differs from initial."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback)
        guard._initial_ppid = 12345
        mock_getppid.return_value = 67890  # Different parent
        assert guard.is_parent_alive() is False


class TestOrphanDetection:
    """Tests for orphan detection triggering the callback."""

    @patch("kernel.lifecycle_guard.os.getppid")
    def test_orphan_triggers_callback(self, mock_getppid):
        """Orphan detection triggers the on_shutdown callback."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=0.05)

        # Start with a valid ppid
        mock_getppid.return_value = 9999
        guard._initial_ppid = 9999
        guard._running = True
        guard._stop_event.clear()
        guard._thread = threading.Thread(
            target=guard._monitor_loop, daemon=True, name="lifecycle-guard"
        )
        guard._thread.start()

        # Simulate parent death
        time.sleep(0.02)
        mock_getppid.return_value = 1  # Parent died, ppid became 1

        # Wait for the guard to detect it
        time.sleep(0.2)
        callback.assert_called_once()
        assert guard._running is False

    @patch("kernel.lifecycle_guard.os.getppid")
    def test_callback_exception_is_swallowed(self, mock_getppid):
        """Exceptions in on_shutdown callback are swallowed."""
        callback = MagicMock(side_effect=RuntimeError("shutdown error"))
        guard = LifecycleGuard(on_shutdown=callback, check_interval=0.05)

        mock_getppid.return_value = 9999
        guard._initial_ppid = 9999
        guard._running = True
        guard._stop_event.clear()
        guard._thread = threading.Thread(
            target=guard._monitor_loop, daemon=True, name="lifecycle-guard"
        )
        guard._thread.start()

        # Simulate parent death
        time.sleep(0.02)
        mock_getppid.return_value = 1

        # Wait for guard to detect and handle
        time.sleep(0.2)
        callback.assert_called_once()
        assert guard._running is False


class TestHandlesMissingGetppid:
    """Tests for graceful handling when os.getppid is unavailable."""

    @patch("kernel.lifecycle_guard.os.getppid", side_effect=AttributeError)
    def test_start_with_no_getppid(self, mock_getppid):
        """Guard handles missing os.getppid gracefully on start."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=0.05)
        guard.start()
        # Should not start the thread when getppid raises
        assert guard._thread is None
        assert guard._running is False
        callback.assert_not_called()

    @patch("kernel.lifecycle_guard.os.getppid", side_effect=OSError("no ppid"))
    def test_start_with_os_error(self, mock_getppid):
        """Guard handles OSError from os.getppid gracefully."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=0.05)
        guard.start()
        assert guard._thread is None
        assert guard._running is False

    def test_start_skipped_when_ppid_is_1(self):
        """Guard does not start monitoring if already under init."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=0.05)
        with patch("kernel.lifecycle_guard.os.getppid", return_value=1):
            guard.start()
        assert guard._thread is None
        assert guard._running is False

    @patch("kernel.lifecycle_guard.os.getppid", side_effect=OSError("container"))
    def test_is_parent_alive_with_os_error(self, mock_getppid):
        """is_parent_alive returns True when os.getppid raises OSError."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback)
        guard._initial_ppid = 1234
        # Should not crash, returns True (assume alive)
        assert guard.is_parent_alive() is True

    def test_stop_cleans_up_thread_completely(self):
        """After stop(), the thread reference is None and thread is dead."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=60.0)
        guard.start()
        assert guard._thread is not None
        thread_ref = guard._thread
        guard.stop()
        assert guard._thread is None
        assert not thread_ref.is_alive()

    def test_stop_is_idempotent(self):
        """Calling stop() multiple times does not raise."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=60.0)
        guard.start()
        guard.stop()
        guard.stop()  # Second stop should be safe
        guard.stop()  # Third stop should be safe
        assert guard._running is False

    @patch("kernel.lifecycle_guard.os.getppid")
    def test_callback_exception_does_not_crash_thread(self, mock_getppid):
        """on_shutdown exceptions are swallowed, thread exits cleanly."""
        callback = MagicMock(side_effect=Exception("boom"))
        guard = LifecycleGuard(on_shutdown=callback, check_interval=0.05)

        mock_getppid.return_value = 9999
        guard._initial_ppid = 9999
        guard._running = True
        guard._stop_event.clear()
        guard._thread = threading.Thread(
            target=guard._monitor_loop, daemon=True, name="lifecycle-guard"
        )
        guard._thread.start()

        # Simulate parent death
        time.sleep(0.02)
        mock_getppid.return_value = 1

        # Wait for guard to detect and handle
        time.sleep(0.2)
        callback.assert_called_once()
        assert guard._running is False
        # Thread should have exited
        assert not guard._thread.is_alive()

    def test_no_zombie_thread_after_stop(self):
        """After stop(), no lingering threads remain from the guard."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=0.05)
        guard.start()
        time.sleep(0.05)
        guard.stop()
        # Verify no lifecycle-guard threads are alive
        for t in threading.enumerate():
            assert t.name != "lifecycle-guard" or not t.is_alive()


class TestLifecycleGuardAdversarial:
    """Adversarial tests for LifecycleGuard (Round 19)."""

    def test_start_is_idempotent(self):
        """Calling start() multiple times does not create multiple threads."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=60.0)
        guard.start()
        first_thread = guard._thread
        assert first_thread is not None
        assert first_thread.is_alive()

        # Call start again - should be idempotent
        guard.start()
        assert guard._thread is first_thread  # Same thread, not a new one

        # A third call should still be the same
        guard.start()
        assert guard._thread is first_thread

        guard.stop()
        callback.assert_not_called()

    def test_start_idempotent_no_extra_threads(self):
        """Multiple start() calls should not spawn extra threads."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=60.0)

        guard.start()
        guard.start()
        guard.start()

        # Count lifecycle-guard threads
        guard_threads = [t for t in threading.enumerate() if t.name == "lifecycle-guard"]
        assert len(guard_threads) == 1

        guard.stop()

    @patch("kernel.lifecycle_guard.os.getppid")
    def test_blocking_callback_has_timeout(self, mock_getppid):
        """on_shutdown callback that blocks forever is bounded by timeout."""
        block_event = threading.Event()

        def blocking_callback():
            block_event.wait(timeout=30)  # Block for a long time

        guard = LifecycleGuard(
            on_shutdown=blocking_callback,
            check_interval=0.05,
            shutdown_timeout=0.2,
        )

        mock_getppid.return_value = 9999
        guard._initial_ppid = 9999
        guard._running = True
        guard._stop_event.clear()
        guard._thread = threading.Thread(
            target=guard._monitor_loop, daemon=True, name="lifecycle-guard"
        )
        guard._thread.start()

        # Simulate parent death
        time.sleep(0.02)
        mock_getppid.return_value = 1

        # Wait enough for detection + timeout
        time.sleep(0.5)

        # Guard should have detected orphan and exited the loop
        # even though the callback is still blocking
        assert guard._running is False

        # Clean up the blocking callback
        block_event.set()

    def test_start_after_stop_restarts(self):
        """After stop(), calling start() again should restart monitoring."""
        callback = MagicMock()
        guard = LifecycleGuard(on_shutdown=callback, check_interval=60.0)

        guard.start()
        assert guard._running is True
        first_thread = guard._thread
        guard.stop()
        assert guard._running is False

        # Restart
        guard.start()
        assert guard._running is True
        assert guard._thread is not first_thread  # New thread
        assert guard._thread.is_alive()

        guard.stop()
