"""Validation helpers for the kernel runner."""

import os
import re


def _sanitize_project_name(goal: str) -> str:
    """Derive a sanitized project name from a goal string.

    Strips null bytes and control characters, lowercases the goal,
    replaces spaces with hyphens, removes special characters, and
    truncates to 50 characters.

    Args:
        goal: The goal string to sanitize.

    Returns:
        A filesystem-safe project name.
    """
    # Strip null bytes and control characters (U+0000-U+001F, U+007F-U+009F)
    name = "".join(c for c in goal if c >= " " and c not in ("\x7f",) and ord(c) > 0x1F)
    # Also strip Unicode direction override and other format characters
    name = "".join(
        c
        for c in name
        if not (0x200B <= ord(c) <= 0x200F or 0x202A <= ord(c) <= 0x202E or ord(c) == 0xFEFF)
    )
    name = name.lower().replace(" ", "-")
    # Keep CJK characters (Chinese/Japanese/Korean) for readable workspace names
    name = re.sub(r"[^a-z0-9\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af-]", "", name)
    name = name.lstrip("-.")
    name = name[:50]
    if not name:
        return "project"
    return name


def _validate_workspace_paths(files_written: list[str], workspace_path: str) -> list[str]:
    """Validate that all file paths are within the workspace boundary.

    Args:
        files_written: List of file paths reported by the AI.
        workspace_path: The expected workspace root path.

    Returns:
        List of violation strings for paths outside the workspace.
    """
    violations: list[str] = []
    if not workspace_path:
        return violations
    # Normalize workspace path to ensure consistent comparison
    normalized_workspace = os.path.normpath(os.path.abspath(workspace_path))
    for file_path in files_written:
        normalized_file = os.path.normpath(os.path.abspath(file_path))
        if (
            not normalized_file.startswith(normalized_workspace + os.sep)
            and normalized_file != normalized_workspace
        ):
            violations.append(f"Path '{file_path}' is outside workspace '{workspace_path}'")
    return violations
