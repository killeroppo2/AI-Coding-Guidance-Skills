"""CLI-based AI provider using async subprocess execution."""

import asyncio
import shlex
import subprocess

from kernel.mode3_executor import _parse_transition
from kernel.providers.base import AIProvider, ProviderResponse


class CLIProvider(AIProvider):
    """AI provider that wraps a CLI command via subprocess.

    This preserves the existing Mode 3 subprocess behavior as a provider,
    using asyncio subprocess to avoid blocking the event loop.
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
            asyncio.TimeoutError: If the command times out.
            FileNotFoundError: If the command is not found.
            subprocess.CalledProcessError: If the command exits with non-zero status.
        """
        proc = await asyncio.create_subprocess_exec(
            *shlex.split(self.ai_command),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise

        stdout = stdout_bytes.decode() if stdout_bytes else ""
        stderr = stderr_bytes.decode() if stderr_bytes else ""

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, self.ai_command, stdout, stderr
            )

        transition = _parse_transition(stdout)
        return ProviderResponse(text=stdout, transition=transition, raw_output=stdout)
