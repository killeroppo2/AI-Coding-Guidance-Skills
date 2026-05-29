"""Execution strategy modules for the kernel runner.

This package contains the extracted execution logic:
- protocol: Shared utilities for node transitions, stuck detection, progress tracking
- autonomous: Mode 3 AI subprocess execution loop
- dry_run: Mode 1 scaffolding/dry-run execution loop
"""

from kernel.execution.autonomous import AutonomousExecutor
from kernel.execution.dry_run import DryRunExecutor

__all__ = ["AutonomousExecutor", "DryRunExecutor"]
