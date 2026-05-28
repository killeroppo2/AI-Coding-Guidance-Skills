"""Security policy enforcement for workspace operations.

Inspired by context-mode's security.ts, this module provides
deny/allow rule evaluation for filesystem and command operations.
"""

import os
import re
from pathlib import Path
from typing import Literal

PermissionDecision = Literal["allow", "deny"]


class SecurityPolicy:
    """Evaluates workspace operations against security rules.

    Default policy:
    - ALLOW: file operations within the workspace path
    - DENY: path traversal, writes outside workspace, dangerous commands
    """

    # Dangerous command patterns (shell injection vectors)
    DANGEROUS_PATTERNS: list[str] = [
        r"rm\s+(-[rfR]+\s+)?/",  # rm -rf /
        r";\s*rm\s",  # ; rm
        r"\|\s*rm\s",  # | rm
        r">\s*/etc/",  # redirect to /etc
        r"chmod\s+777",  # overly permissive chmod
        r"curl.*\|\s*(ba)?sh",  # curl pipe to shell
        r"wget.*\|\s*(ba)?sh",  # wget pipe to shell
        r"eval\s*\(",  # eval() in commands
    ]

    def __init__(self, workspace_root: str | None = None) -> None:
        """Initialize with optional workspace root path."""
        self._workspace_root = Path(workspace_root).resolve() if workspace_root else None
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_PATTERNS]

    def check_path(self, path: str) -> PermissionDecision:
        """Check if a file path is allowed.

        Args:
            path: The file path to check.

        Returns:
            'allow' if the path is within workspace, 'deny' otherwise.
        """
        if not path:
            return "deny"

        # Reject null bytes
        if "\x00" in path:
            return "deny"

        # Reject Unicode path traversal (fullwidth dots and slashes)
        # Fullwidth period: \uff0e, fullwidth solidus: \uff0f, fullwidth reverse solidus: \uff3c
        if "\uff0e" in path or "\uff0f" in path or "\uff3c" in path:
            return "deny"

        # Reject path traversal attempts
        if ".." in path.split(os.sep) or ".." in path.split("/"):
            return "deny"

        # If no workspace root set, allow all paths
        if self._workspace_root is None:
            return "allow"

        # Resolve and check containment
        try:
            resolved = Path(path).resolve()
            # Check if the resolved path is within the workspace
            resolved.relative_to(self._workspace_root)
            return "allow"
        except (ValueError, OSError):
            return "deny"

    def check_command(self, command: str) -> PermissionDecision:
        """Check if a shell command is safe.

        Args:
            command: The shell command string to check.

        Returns:
            'allow' if the command appears safe, 'deny' if it matches
            dangerous patterns.
        """
        if not command:
            return "allow"

        for pattern in self._compiled_patterns:
            if pattern.search(command):
                return "deny"

        return "allow"

    def check_operation(self, op_type: str, target: str) -> PermissionDecision:
        """Unified check for any operation type.

        Args:
            op_type: One of 'file_write', 'file_read', 'command', 'path'
            target: The path or command string to check.

        Returns:
            'allow' or 'deny'.
        """
        if op_type in ("file_write", "file_read", "path"):
            return self.check_path(target)
        elif op_type == "command":
            return self.check_command(target)
        return "allow"
