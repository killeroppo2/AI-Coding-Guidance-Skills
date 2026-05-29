"""Factory for creating AI provider instances."""

from kernel.providers.base import AIProvider


def create_provider(provider_type: str, **kwargs) -> AIProvider:
    """Create an AI provider instance.

    Args:
        provider_type: One of 'cli', 'openai', 'anthropic', 'subprocess'.
        **kwargs: Provider-specific configuration.

    Returns:
        An AIProvider instance.

    Raises:
        ValueError: If provider_type is unknown.
    """
    if provider_type == "cli":
        from kernel.providers.cli_provider import CLIProvider

        return CLIProvider(**kwargs)
    elif provider_type == "openai":
        from kernel.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(**kwargs)
    elif provider_type == "anthropic":
        from kernel.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(**kwargs)
    elif provider_type == "subprocess":
        from kernel.providers.subprocess_provider import SubprocessProvider

        return SubprocessProvider(**kwargs)
    else:
        raise ValueError(
            f"Unknown provider type: {provider_type!r}. "
            "Must be one of: cli, openai, anthropic, subprocess"
        )
