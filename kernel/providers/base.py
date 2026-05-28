"""Base class and types for AI providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProviderResponse:
    """Response from an AI provider."""

    text: str
    transition: str | None
    raw_output: str


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def generate(self, prompt: str, timeout: int = 300) -> ProviderResponse:
        """Generate a response from the AI provider.

        Args:
            prompt: The prompt to send to the AI.
            timeout: Timeout in seconds.

        Returns:
            ProviderResponse with text, transition, and raw output.
        """
        ...
