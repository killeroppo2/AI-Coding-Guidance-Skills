"""Tests for kernel/providers/ package."""

import asyncio
import subprocess
from unittest.mock import patch

import pytest

from kernel.providers import AIProvider, ProviderResponse, create_provider
from kernel.providers.base import AIProvider as BaseAIProvider
from kernel.providers.cli_provider import CLIProvider
from kernel.providers.factory import create_provider as factory_create_provider


class TestProviderResponse:
    """Tests for the ProviderResponse dataclass."""

    def test_create_response(self) -> None:
        """ProviderResponse can be instantiated with required fields."""
        resp = ProviderResponse(text="hello", transition="next", raw_output="hello")
        assert resp.text == "hello"
        assert resp.transition == "next"
        assert resp.raw_output == "hello"

    def test_none_transition(self) -> None:
        """ProviderResponse allows None transition."""
        resp = ProviderResponse(text="hi", transition=None, raw_output="hi")
        assert resp.transition is None


class TestAIProviderBase:
    """Tests for the AIProvider abstract base class."""

    def test_cannot_instantiate_abstract(self) -> None:
        """AIProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AIProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_generate(self) -> None:
        """A subclass without generate() cannot be instantiated."""

        class IncompleteProvider(AIProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]


class TestCLIProvider:
    """Tests for the CLIProvider."""

    def test_init_stores_command(self) -> None:
        """CLIProvider stores the ai_command."""
        provider = CLIProvider(ai_command="echo test")
        assert provider.ai_command == "echo test"

    def test_is_ai_provider(self) -> None:
        """CLIProvider is an instance of AIProvider."""
        provider = CLIProvider(ai_command="echo test")
        assert isinstance(provider, AIProvider)

    def test_generate_success(self) -> None:
        """CLIProvider.generate returns response from subprocess."""
        provider = CLIProvider(ai_command="cat")
        result = asyncio.run(provider.generate("hello world\n", timeout=10))
        assert "hello world" in result.text
        assert result.raw_output == result.text

    def test_generate_nonzero_exit(self) -> None:
        """CLIProvider.generate raises CalledProcessError on non-zero exit."""
        provider = CLIProvider(ai_command="false")
        with pytest.raises(subprocess.CalledProcessError):
            asyncio.run(provider.generate("", timeout=10))

    def test_generate_timeout(self) -> None:
        """CLIProvider.generate raises TimeoutError on timeout."""
        provider = CLIProvider(ai_command="sleep 60")
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(provider.generate("", timeout=1))

    def test_generate_file_not_found(self) -> None:
        """CLIProvider.generate raises error for missing command."""
        provider = CLIProvider(ai_command="nonexistent_command_xyz123")
        with pytest.raises((FileNotFoundError, OSError)):
            asyncio.run(provider.generate("", timeout=5))


class TestFactory:
    """Tests for the create_provider factory."""

    def test_create_cli_provider(self) -> None:
        """Factory creates CLIProvider for 'cli' type."""
        provider = create_provider("cli", ai_command="echo test")
        assert isinstance(provider, CLIProvider)
        assert provider.ai_command == "echo test"

    def test_unknown_provider_raises(self) -> None:
        """Factory raises ValueError for unknown provider type."""
        with pytest.raises(ValueError, match="Unknown provider type"):
            create_provider("invalid_provider")

    def test_openai_without_package_raises_import_error(self) -> None:
        """Factory raises ImportError when openai package is missing."""
        from kernel.providers.openai_provider import OpenAIProvider

        # openai is already None in this environment (not installed)
        with pytest.raises((ImportError, ValueError)):
            OpenAIProvider(api_key="test-key")

    def test_anthropic_without_package_raises_import_error(self) -> None:
        """Factory raises ImportError when anthropic package is missing."""
        from kernel.providers.anthropic_provider import AnthropicProvider

        # anthropic is already None in this environment (not installed)
        with pytest.raises((ImportError, ValueError)):
            AnthropicProvider(api_key="test-key")


class TestFactoryProviderCreation:
    """Tests for factory creating openai and anthropic providers."""

    def test_factory_openai_import_error(self) -> None:
        """Factory for 'openai' raises ImportError when package missing."""
        with pytest.raises((ImportError, ValueError)):
            factory_create_provider("openai", api_key="test-key")

    def test_factory_anthropic_import_error(self) -> None:
        """Factory for 'anthropic' raises ImportError when package missing."""
        with pytest.raises((ImportError, ValueError)):
            factory_create_provider("anthropic", api_key="test-key")

    def test_factory_openai_with_mock(self) -> None:
        """Factory for 'openai' creates OpenAIProvider when package available."""
        import kernel.providers.openai_provider as oai_mod

        mock_openai = type("MockOpenAI", (), {"AsyncOpenAI": lambda *a, **kw: None})()
        with patch.object(oai_mod, "openai", mock_openai):
            provider = factory_create_provider("openai", api_key="test-key")
            assert provider.model == "gpt-4o"

    def test_factory_anthropic_with_mock(self) -> None:
        """Factory for 'anthropic' creates AnthropicProvider when package available."""
        import kernel.providers.anthropic_provider as ant_mod

        mock_anthropic = type(
            "MockAnthropic", (), {"AsyncAnthropic": lambda *a, **kw: None}
        )()
        with patch.object(ant_mod, "anthropic", mock_anthropic):
            provider = factory_create_provider("anthropic", api_key="test-key")
            assert provider.model == "claude-sonnet-4-20250514"


class TestOpenAIProviderValidation:
    """Tests for OpenAI provider API key validation."""

    def test_no_api_key_raises_value_error(self) -> None:
        """OpenAIProvider raises ValueError when no API key is available."""
        import kernel.providers.openai_provider as oai_mod

        # Mock the openai module so ImportError check passes
        mock_openai = type("MockOpenAI", (), {"AsyncOpenAI": lambda *a, **kw: None})()
        with patch.object(oai_mod, "openai", mock_openai):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(ValueError, match="API key is required"):
                    oai_mod.OpenAIProvider(api_key=None)


class TestAnthropicProviderValidation:
    """Tests for Anthropic provider API key validation."""

    def test_no_api_key_raises_value_error(self) -> None:
        """AnthropicProvider raises ValueError when no API key is available."""
        import kernel.providers.anthropic_provider as ant_mod

        # Mock the anthropic module so ImportError check passes
        mock_anthropic = type(
            "MockAnthropic", (), {"AsyncAnthropic": lambda *a, **kw: None}
        )()
        with patch.object(ant_mod, "anthropic", mock_anthropic):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(ValueError, match="API key is required"):
                    ant_mod.AnthropicProvider(api_key=None)


class TestPackageExports:
    """Tests for the providers package __init__.py exports."""

    def test_exports_ai_provider(self) -> None:
        """Package exports AIProvider."""
        from kernel.providers import AIProvider

        assert AIProvider is BaseAIProvider

    def test_exports_provider_response(self) -> None:
        """Package exports ProviderResponse."""
        from kernel.providers import ProviderResponse

        assert ProviderResponse is not None

    def test_exports_create_provider(self) -> None:
        """Package exports create_provider."""
        from kernel.providers import create_provider

        assert create_provider is factory_create_provider
