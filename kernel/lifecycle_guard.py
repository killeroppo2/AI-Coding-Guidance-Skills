"""Lifecycle guard for orphan process detection.

Inspired by context-mode's lifecycle.ts, this module detects when the
parent process has died and triggers graceful shutdown to prevent
orphaned kernel processes.
"""

import os
import sys
import threading
from typing import Callable


class LifecycleGuard:
    """Monitors parent process liveness and triggers shutdown on orphan detection.

    Uses os.getppid() polling to detect when the parent process dies.
    On Linux/macOS, ppid changes to 1 (init) when parent dies.
    On Windows, ppid may not change reliably, so polling is more frequent.
    """

    DEFAULT_CHECK_INTERVAL = 30.0  # seconds
    SHUTDOWN_TIMEOUT = 5.0  # seconds to wait for on_shutdown callback

    def __init__(
        self,
        on_shutdown: Callable[[], None],
        check_interval: float | None = None,
        shutdown_timeout: float | None = None,
    ) -> None:
        """Initialize the lifecycle guard.

        Args:
            on_shutdown: Callback invoked when orphan state is detected.
            check_interval: Seconds between parent-liveness checks.
            shutdown_timeout: Max seconds to wait for on_shutdown callback.
        """
        self._on_shutdown = on_shutdown
        self._check_interval = check_interval or self.DEFAULT_CHECK_INTERVAL
        self._shutdown_timeout = shutdown_timeout or self.SHUTDOWN_TIMEOUT
        self._initial_ppid: int | None = None
        self._running = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the background liveness monitor.

        This method is idempotent - calling it multiple times will not
        create multiple monitor threads.
        """
        with self._lock:
            # Idempotent: if already running, do nothing
            if self._running and self._thread is not None and self._thread.is_alive():
                return

            try:
                self._initial_ppid = os.getppid()
            except (OSError, AttributeError):
                # os.getppid() not available on this platform
                return

            if self._initial_ppid <= 1:
                # Already orphaned or running as init child
                return

            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="lifecycle-guard",
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop the background monitor."""
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def is_parent_alive(self) -> bool:
        """Check if the parent process is still alive."""
        if self._initial_ppid is None:
            return True  # Can't check, assume alive
        try:
            current_ppid = os.getppid()
            # On Linux/macOS, ppid becomes 1 when parent dies
            if current_ppid != self._initial_ppid:
                return False
            # On some systems, also check if the process exists
            if sys.platform != "win32" and self._initial_ppid > 1:
                try:
                    os.kill(self._initial_ppid, 0)
                except ProcessLookupError:
                    return False
                except PermissionError:
                    pass  # Process exists but we can't signal it
            return True
        except (OSError, AttributeError):
            return True  # Can't check, assume alive

    def _monitor_loop(self) -> None:
        """Background loop that checks parent liveness."""
        while self._running:
            # Use event wait instead of time.sleep to allow quick stop
            self._stop_event.wait(timeout=self._check_interval)
            if not self._running:
                break
            if not self.is_parent_alive():
                self._running = False
                try:
                    # Run callback with a timeout to prevent blocking forever
                    cb_thread = threading.Thread(
                        target=self._run_shutdown_callback,
                        daemon=True,
                        name="lifecycle-shutdown-cb",
                    )
                    cb_thread.start()
                    cb_thread.join(timeout=self._shutdown_timeout)
                except Exception:
                    pass
                break

    def _run_shutdown_callback(self) -> None:
        """Execute the shutdown callback, swallowing any exceptions."""
        try:
            self._on_shutdown()
        except Exception:
            pass
