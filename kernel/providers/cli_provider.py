"""CLI-based AI provider using subprocess execution."""

import shlex
import subprocess

from kernel.mode3_executor import _parse_transition
from kernel.providers.base import AIProvider, ProviderResponse


class CLIProvider(AIProvider):
    """AI provider that wraps a CLI command via subprocess.

    This preserves the existing Mode 3 subprocess behavior as a provider.
    """

    def __init__(self, ai_command: str) -> None:
        """Initialize with an AI CLI command string.

        Args:
            ai_command: The shell command to invoke (e.g., 'claude --print').
        """
        self.ai_command = ai_command

    async def generate(self, prompt: str, timeout: int = 300) -> ProviderResponse:
        """Generate a response by piping prompt to the CLI command.

        Args:
            prompt: The prompt to send via stdin.
            timeout: Timeout in seconds.

        Returns:
            ProviderResponse with text, transition, and raw output.

        Raises:
            subprocess.TimeoutExpired: If the command times out.
            FileNotFoundError: If the command is not found.
        """
        proc = subprocess.Popen(
            shlex.split(self.ai_command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(input=prompt, timeout=timeout)

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, self.ai_command, stdout, stderr
            )

        transition = _parse_transition(stdout)
        return ProviderResponse(text=stdout, transition=transition, raw_output=stdout)
