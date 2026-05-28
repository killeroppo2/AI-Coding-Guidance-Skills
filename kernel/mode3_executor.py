"""Mode 3 subprocess execution logic for the kernel runner.

Contains AI output parsing utilities for Mode 3 (real AI execution).
"""

import subprocess  # noqa: F401 - Popen type used for _active_subprocess annotation

# Module-level reference to the active subprocess for signal handler cleanup
_active_subprocess: subprocess.Popen | None = None


def _parse_transition(output: str) -> str | None:
    """Parse AI output for a TRANSITION line.

    Validates the transition value to reject path traversal or
    other suspicious patterns. Only alphanumeric, underscore, and
    hyphen characters are allowed in condition values.

    Args:
        output: The AI subprocess stdout.

    Returns:
        The transition condition string, or None if not found or invalid.
    """
    # Limit scan to first 1MB to prevent excessive processing on huge outputs
    scan_output = output[:1_048_576] if len(output) > 1_048_576 else output
    for line in scan_output.splitlines():
        stripped = line.strip()
        if stripped.startswith("TRANSITION:"):
            value = stripped[len("TRANSITION:") :].strip()
            # Reject values containing path separators or null bytes
            if any(c in value for c in ("/", "\\", "\x00", "..")):
                return None
            return value
    return None
