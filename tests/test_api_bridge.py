"""Tests for scripts/api_bridge.py error handling."""

import subprocess
import sys
from pathlib import Path

BRIDGE_PATH = Path(__file__).parent.parent / "scripts" / "api_bridge.py"


class TestApiBridgeErrors:
    """Test error handling in the API bridge script."""

    def test_empty_stdin_exits_with_error(self):
        """Empty stdin should produce error and exit code 1."""
        result = subprocess.run(
            [sys.executable, str(BRIDGE_PATH)],
            input="",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Empty prompt" in result.stderr

    def test_missing_anthropic_key_exits_with_error(self):
        """Missing ANTHROPIC_API_KEY should produce clear error."""
        env = {"AI_PROVIDER": "anthropic", "PATH": ""}
        result = subprocess.run(
            [sys.executable, str(BRIDGE_PATH)],
            input="test prompt",
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 1
        assert "ANTHROPIC_API_KEY" in result.stderr

    def test_missing_openai_key_exits_with_error(self):
        """Missing OPENAI_API_KEY should produce clear error."""
        env = {"AI_PROVIDER": "openai", "PATH": ""}
        result = subprocess.run(
            [sys.executable, str(BRIDGE_PATH)],
            input="test prompt",
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 1
        assert "OPENAI_API_KEY" in result.stderr

    def test_unknown_provider_exits_with_error(self):
        """Unknown provider should produce clear error."""
        env = {"AI_PROVIDER": "fake_provider", "PATH": ""}
        result = subprocess.run(
            [sys.executable, str(BRIDGE_PATH)],
            input="test prompt",
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 1
        assert "fake_provider" in result.stderr
