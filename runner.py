"""Self-evolving AI development kernel runner.

This is the main entry point for the kernel. It delegates to kernel.orchestrator.
"""
from pathlib import Path
from typing import Any

import kernel.orchestrator as _orchestrator
from kernel.cli import parse_args
from kernel.mode3_executor import _parse_transition
from kernel.validators import _sanitize_project_name, _validate_workspace_paths

KERNEL_ROOT = Path(__file__).parent

__all__ = ["main", "parse_args", "KERNEL_ROOT",
           "_parse_transition", "_sanitize_project_name", "_validate_workspace_paths"]


def main(argv: list[str] | None = None) -> dict[str, Any]:
    """Main entry point. Delegates to kernel.orchestrator.main()."""
    _orchestrator.KERNEL_ROOT = KERNEL_ROOT
    return _orchestrator.main(argv)


if __name__ == "__main__":
    main()
