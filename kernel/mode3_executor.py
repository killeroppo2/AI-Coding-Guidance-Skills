"""Mode 3 subprocess execution logic for the kernel runner.

Contains AI output parsing utilities for Mode 3 (real AI execution).
"""

import subprocess

# Module-level reference to the active subprocess for signal handler cleanup
_active_subprocess = None  # type: subprocess.Popen | None


def _parse_transition(output: str) -> str | None:
    """Parse AI output for a TRANSITION line.

    Args:
        output: The AI subprocess stdout.

    Returns:
        The transition condition string, or None if not found.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("TRANSITION:"):
            return stripped[len("TRANSITION:"):].strip()
    return None
