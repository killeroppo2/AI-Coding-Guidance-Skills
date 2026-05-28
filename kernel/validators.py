"""Validation helpers for the kernel runner."""

import os
import re


def _sanitize_project_name(goal: str) -> str:
    """Derive a sanitized project name from a goal string.

    Lowercases the goal, replaces spaces with hyphens, removes special
    characters, and truncates to 50 characters.

    Args:
        goal: The goal string to sanitize.

    Returns:
        A filesystem-safe project name.
    """
    name = goal.lower().replace(" ", "-")
    name = re.sub(r"[^a-z0-9-]", "", name)
    return name[:50]


def _validate_workspace_paths(
    files_written: list[str], workspace_path: str
) -> list[str]:
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
        if not normalized_file.startswith(normalized_workspace + os.sep) and \
                normalized_file != normalized_workspace:
            violations.append(
                f"Path '{file_path}' is outside workspace '{workspace_path}'"
            )
    return violations
