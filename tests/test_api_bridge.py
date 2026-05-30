"""Tests for scripts/api_bridge.py."""

import os
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.api_bridge import call_anthropic, call_openai, get_config, run_bridge


class TestGetConfig:
    """Tests for get_config function."""

    def test_default_provider_is_anthropic(self) -> None:
        """Default provider is anthropic."""
        with patch.dict(os.environ, {}, clear=True):
            config = get_config()
        assert config["provider"] == "anthropic"

    def test_openai_provider(self) -> None:
        """AI_PROVIDER=openai selects openai."""
        with patch.dict(os.environ, {"AI_PROVIDER": "openai"}, clear=True):
            config = get_config()
        assert config["provider"] == "openai"
        assert config["model"] == "gpt-4"

    def test_custom_model(self) -> None:
        """AI_MODEL env var overrides default model."""
        with patch.dict(
            os.environ, {"AI_MODEL": "custom-model"}, clear=True
        ):
            config = get_config()
        assert config["model"] == "custom-model"

    def test_custom_max_tokens(self) -> None:
        """AI_MAX_TOKENS env var is respected."""
        with patch.dict(os.environ, {"AI_MAX_TOKENS": "8192"}, clear=True):
            config = get_config()
        assert config["max_tokens"] == 8192

    def test_default_max_tokens(self) -> None:
        """Default max_tokens is 4096."""
        with patch.dict(os.environ, {}, clear=True):
            config = get_config()
        assert config["max_tokens"] == 4096

    def test_anthropic_api_key(self) -> None:
        """ANTHROPIC_API_KEY is read for anthropic provider."""
        with patch.dict(
            os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True
        ):
            config = get_config()
        assert config["api_key"] == "test-key"

    def test_openai_api_key(self) -> None:
        """OPENAI_API_KEY is read for openai provider."""
        with patch.dict(
            os.environ,
            {"AI_PROVIDER": "openai", "OPENAI_API_KEY": "oai-key"},
            clear=True,
        ):
            config = get_config()
        assert config["api_key"] == "oai-key"


class TestCallAnthropic:
    """Tests for call_anthropic function."""

    def test_missing_package(self) -> None:
        """Returns error tuple when anthropic package not installed."""
        config = {"api_key": "key", "model": "m", "max_tokens": 100}
        with patch.dict(sys.modules, {"anthropic": None}):
            result, is_error = call_anthropic("hello", config)
        assert "anthropic" in result
        assert is_error is True

    def test_missing_api_key(self) -> None:
        """Returns error tuple when API key is empty."""
        mock_anthropic = MagicMock()
        config = {"api_key": "", "model": "m", "max_tokens": 100}
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            result, is_error = call_anthropic("hello", config)
        assert "ANTHROPIC_API_KEY" in result
        assert is_error is True

    def test_successful_call(self) -> None:
        """Returns response text on success."""
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="AI response")]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.Anthropic.return_value = mock_client

        config = {"api_key": "test-key", "model": "claude", "max_tokens": 100}
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            result, is_error = call_anthropic("hello", config)
        assert result == "AI response"
        assert is_error is False


class TestCallOpenai:
    """Tests for call_openai function."""

    def test_missing_package(self) -> None:
        """Returns error tuple when openai package not installed."""
        config = {"api_key": "key", "model": "m", "max_tokens": 100}
        with patch.dict(sys.modules, {"openai": None}):
            result, is_error = call_openai("hello", config)
        assert "openai" in result
        assert is_error is True

    def test_missing_api_key(self) -> None:
        """Returns error tuple when API key is empty."""
        mock_openai = MagicMock()
        config = {"api_key": "", "model": "m", "max_tokens": 100}
        with patch.dict(sys.modules, {"openai": mock_openai}):
            result, is_error = call_openai("hello", config)
        assert "OPENAI_API_KEY" in result
        assert is_error is True

    def test_successful_call(self) -> None:
        """Returns response text on success."""
        mock_openai = MagicMock()
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "OpenAI response"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        config = {"api_key": "test-key", "model": "gpt-4", "max_tokens": 100}
        with patch.dict(sys.modules, {"openai": mock_openai}):
            result, is_error = call_openai("hello", config)
        assert result == "OpenAI response"
        assert is_error is False


class TestRunBridge:
    """Tests for run_bridge function."""

    def test_empty_stdin_exits(self) -> None:
        """Exits with error on empty stdin."""
        import pytest

        with patch("sys.stdin", StringIO("")):
            with pytest.raises(SystemExit) as exc_info:
                run_bridge()
            assert exc_info.value.code == 1

    def test_calls_anthropic_by_default(self) -> None:
        """Calls anthropic by default."""
        with (
            patch("sys.stdin", StringIO("test prompt")),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=True),
            patch(
                "scripts.api_bridge.call_anthropic",
                return_value=("response", False),
            ) as mock_call,
            patch("builtins.print") as mock_print,
        ):
            run_bridge()
            mock_call.assert_called_once()
            printed = mock_print.call_args[0][0]
            assert "response" in printed
            assert "STATUS: success" in printed
            assert "TRANSITION:" in printed

    def test_calls_openai_when_configured(self) -> None:
        """Calls openai when AI_PROVIDER is openai."""
        with (
            patch("sys.stdin", StringIO("test prompt")),
            patch.dict(
                os.environ,
                {"AI_PROVIDER": "openai", "OPENAI_API_KEY": "key"},
                clear=True,
            ),
            patch(
                "scripts.api_bridge.call_openai",
                return_value=("oai response", False),
            ) as mock_call,
            patch("builtins.print") as mock_print,
        ):
            run_bridge()
            mock_call.assert_called_once()
            printed = mock_print.call_args[0][0]
            assert "oai response" in printed
            assert "STATUS: success" in printed
            assert "TRANSITION:" in printed

    def test_error_exits_nonzero(self) -> None:
        """Exits with code 2 when API returns an error."""
        import pytest

        with (
            patch("sys.stdin", StringIO("test prompt")),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=True),
            patch(
                "scripts.api_bridge.call_anthropic",
                return_value=("错误: 请安装 anthropic 包", True),
            ),
        ):
            with pytest.raises(SystemExit) as exc_info:
                run_bridge()
            assert exc_info.value.code == 2

    def test_error_prints_to_stderr(self, capsys) -> None:
        """Error messages are printed to stderr, not stdout."""
        import pytest

        with (
            patch("sys.stdin", StringIO("test prompt")),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=True),
            patch(
                "scripts.api_bridge.call_anthropic",
                return_value=("错误: 请设置 ANTHROPIC_API_KEY 环境变量", True),
            ),
        ):
            with pytest.raises(SystemExit):
                run_bridge()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "ANTHROPIC_API_KEY" in captured.err
