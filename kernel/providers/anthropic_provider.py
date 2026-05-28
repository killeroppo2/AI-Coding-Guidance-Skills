"""Anthropic-based AI provider."""

import os

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

from kernel.mode3_executor import _parse_transition
from kernel.providers.base import AIProvider, ProviderResponse


class AnthropicProvider(AIProvider):
    """AI provider using the Anthropic API."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None) -> None:
        """Initialize the Anthropic provider.

        Args:
            model: The model name to use (default: claude-sonnet-4-20250514).
            api_key: Optional API key. Falls back to ANTHROPIC_API_KEY env var.

        Raises:
            ImportError: If the anthropic package is not installed.
            ValueError: If no API key is provided and ANTHROPIC_API_KEY is not set.
        """
        if anthropic is None:
            raise ImportError(
                "The 'anthropic' package is required for AnthropicProvider. "
                "Install it with: pip install 'ai-coding-guidance-skills[anthropic]'"
            )
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key is required. Pass api_key= or set the "
                "ANTHROPIC_API_KEY environment variable."
            )
        self._client = anthropic.AsyncAnthropic(api_key=self.api_key)

    async def generate(self, prompt: str, timeout: int = 300) -> ProviderResponse:
        """Generate a response using the Anthropic API.

        Args:
            prompt: The prompt to send.
            timeout: Timeout in seconds.

        Returns:
            ProviderResponse with text, transition, and raw output.
        """
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
        text = response.content[0].text if response.content else ""
        transition = _parse_transition(text)
        return ProviderResponse(text=text, transition=transition, raw_output=text)
