"""Atomic file writing using write-to-temp-then-rename pattern."""

import os
import tempfile
from pathlib import Path


def atomic_write(path: str | Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to file atomically.

    Writes to a temporary file in the same directory, then uses os.rename()
    which is atomic on POSIX systems.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to temp file in same directory (same filesystem for atomic rename)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.rename(tmp_path, str(path))
    except BaseException:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
