"""Tests for kernel/logging_config.py."""

import json
import logging
import os
from unittest.mock import patch

from kernel.logging_config import JsonFormatter, setup_logging


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def test_returns_logger(self) -> None:
        """setup_logging returns a Logger instance."""
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)

    def test_logger_name_is_kernel(self) -> None:
        """Logger name should be 'kernel'."""
        logger = setup_logging()
        assert logger.name == "kernel"

    def test_default_level_is_info(self) -> None:
        """Default log level is INFO."""
        logger = setup_logging()
        assert logger.level == logging.INFO

    def test_verbose_sets_debug(self) -> None:
        """verbose=True overrides level to DEBUG."""
        logger = setup_logging(verbose=True)
        assert logger.level == logging.DEBUG

    @patch.dict(os.environ, {"LOG_LEVEL": "WARNING"})
    def test_log_level_env_var(self) -> None:
        """LOG_LEVEL env var controls the log level."""
        logger = setup_logging()
        assert logger.level == logging.WARNING

    @patch.dict(os.environ, {"LOG_LEVEL": "ERROR"})
    def test_verbose_overrides_env_var(self) -> None:
        """verbose=True overrides LOG_LEVEL env var."""
        logger = setup_logging(verbose=True)
        assert logger.level == logging.DEBUG

    def test_handler_writes_to_stderr(self) -> None:
        """Logger handler should write to stderr."""
        logger = setup_logging()
        assert len(logger.handlers) == 1
        import sys

        assert logger.handlers[0].stream is sys.stderr

    @patch.dict(os.environ, {"LOG_FORMAT": "json"})
    def test_json_format_uses_json_formatter(self) -> None:
        """LOG_FORMAT=json uses JsonFormatter."""
        logger = setup_logging()
        assert isinstance(logger.handlers[0].formatter, JsonFormatter)

    def test_text_format_is_default(self) -> None:
        """Default format is text (message-only)."""
        logger = setup_logging()
        formatter = logger.handlers[0].formatter
        assert not isinstance(formatter, JsonFormatter)

    def test_no_propagation(self) -> None:
        """Logger should not propagate to root."""
        logger = setup_logging()
        assert logger.propagate is False

    def test_repeated_calls_do_not_duplicate_handlers(self) -> None:
        """Calling setup_logging multiple times should not add multiple handlers."""
        setup_logging()
        setup_logging()
        logger = setup_logging()
        assert len(logger.handlers) == 1

    @patch.dict(os.environ, {"LOG_LEVEL": "INVALID"})
    def test_invalid_log_level_defaults_to_info(self) -> None:
        """Invalid LOG_LEVEL falls back to INFO."""
        logger = setup_logging()
        assert logger.level == logging.INFO


class TestJsonFormatter:
    """Tests for the JsonFormatter class."""

    def test_format_produces_valid_json(self) -> None:
        """JsonFormatter output is valid JSON."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello world",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "hello world"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert "timestamp" in parsed

    def test_format_includes_exception(self) -> None:
        """JsonFormatter includes exception info when present."""
        formatter = JsonFormatter()
        try:
            raise RuntimeError("test error")
        except RuntimeError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="an error",
            args=None,
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "RuntimeError" in parsed["exception"]
