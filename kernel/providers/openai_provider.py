"""OpenAI-based AI provider."""

import os

try:
    import openai
except ImportError:
    openai = None  # type: ignore[assignment]

from kernel.mode3_executor import _parse_transition
from kernel.providers.base import AIProvider, ProviderResponse


class OpenAIProvider(AIProvider):
    """AI provider using the OpenAI API."""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None) -> None:
        """Initialize the OpenAI provider.

        Args:
            model: The model name to use (default: gpt-4o).
            api_key: Optional API key. Falls back to OPENAI_API_KEY env var.

        Raises:
            ImportError: If the openai package is not installed.
        """
        if openai is None:
            raise ImportError(
                "The 'openai' package is required for OpenAIProvider. "
                "Install it with: pip install 'ai-coding-guidance-skills[openai]'"
            )
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = openai.AsyncOpenAI(api_key=self.api_key)

    async def generate(self, prompt: str, timeout: int = 300) -> ProviderResponse:
        """Generate a response using the OpenAI API.

        Args:
            prompt: The prompt to send.
            timeout: Timeout in seconds.

        Returns:
            ProviderResponse with text, transition, and raw output.
        """
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
        text = response.choices[0].message.content or ""
        transition = _parse_transition(text)
        return ProviderResponse(text=text, transition=transition, raw_output=text)
