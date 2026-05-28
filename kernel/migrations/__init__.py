"""Data migration system for the kernel.

Provides versioned migrations to evolve state files as the schema changes.
"""

from kernel.migrations.runner import get_current_version, run_pending_migrations

__all__ = ["get_current_version", "run_pending_migrations"]
