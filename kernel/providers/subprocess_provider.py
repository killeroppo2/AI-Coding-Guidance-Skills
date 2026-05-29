"""Subprocess-based AI provider for Mode 3 execution."""

import shlex
import subprocess

from kernel.mode3_executor import _parse_transition
from kernel.providers.base import AIProvider, ProviderResponse

# Module-level reference to the active subprocess for signal handler cleanup
_active_subprocess: subprocess.Popen | None = None


class SubprocessProvider(AIProvider):
    """AI provider that executes commands via subprocess.

    Wraps the subprocess.Popen logic currently inline in orchestrator.py
    behind the standard AIProvider interface.
    """

    def __init__(self, command: str, timeout: int = 300) -> None:
        """Initialize the subprocess provider.

        Args:
            command: Shell command string to execute (will be shlex.split).
            timeout: Default timeout in seconds for subprocess execution.
        """
        self.command = command
        self.timeout = timeout

    async def generate(self, prompt: str, timeout: int = 300) -> ProviderResponse:
        """Generate a response by piping prompt to subprocess.

        Args:
            prompt: The prompt to send to the subprocess via stdin.
            timeout: Timeout in seconds (overrides default).

        Returns:
            ProviderResponse with text, parsed transition, and raw output.

        Raises:
            FileNotFoundError: If the command is not found.
            TimeoutError: If the subprocess times out.
            RuntimeError: If the subprocess returns a non-zero exit code.
        """
        global _active_subprocess
        effective_timeout = timeout or self.timeout

        proc = subprocess.Popen(
            shlex.split(self.command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _active_subprocess = proc
        try:
            try:
                stdout, stderr = proc.communicate(
                    input=prompt, timeout=effective_timeout
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                _active_subprocess = None
                raise TimeoutError(
                    f"Subprocess timed out after {effective_timeout}s"
                )
        finally:
            _active_subprocess = None

        if proc.returncode != 0:
            raise RuntimeError(
                f"AI command exited with code {proc.returncode}: {stderr.strip()}"
            )

        transition = _parse_transition(stdout)
        return ProviderResponse(
            text=stdout,
            transition=transition,
            raw_output=stdout,
        )
