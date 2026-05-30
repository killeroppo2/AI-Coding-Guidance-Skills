"""Logging configuration for the kernel package.

Provides structured logging with optional JSON format, environment-based
configuration, and verbose mode support.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Formats log records as JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            A JSON-encoded string representing the log record.
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return a logger for the kernel package.

    Reads LOG_LEVEL from environment (default "WARNING") and LOG_FORMAT
    (if "json", uses JSON formatter). When verbose is True, overrides
    level to DEBUG. When verbose is False, uses WARNING to suppress
    routine INFO messages from normal users.

    Args:
        verbose: If True, set log level to DEBUG regardless of LOG_LEVEL env var.

    Returns:
        A configured logger instance for the kernel package.
    """
    log_level_str = os.environ.get("LOG_LEVEL", "").upper()
    log_format = os.environ.get("LOG_FORMAT", "text").lower()

    # Map string to logging level
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    if verbose:
        log_level = logging.DEBUG
    elif log_level_str and log_level_str in level_map:
        log_level = level_map[log_level_str]
    else:
        # Default: WARNING for normal users (suppress INFO noise)
        log_level = logging.WARNING

    # Get the kernel logger
    logger = logging.getLogger("kernel")
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicate output on repeated calls
    logger.handlers.clear()

    # Console handler writing to stderr
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(log_level)

    if log_format == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        # Use message-only format to preserve existing output patterns
        formatter = logging.Formatter("%(message)s")

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate output
    logger.propagate = False

    return logger


def get_user_logger() -> logging.Logger:
    """Return a logger for critical user-facing messages.

    This logger is always set to INFO level regardless of the verbose
    setting, ensuring important messages are always visible to the user.

    Returns:
        A logger named 'kernel.user' at INFO level.
    """
    logger = logging.getLogger("kernel.user")
    logger.setLevel(logging.INFO)

    # Clear existing handlers to avoid accumulation on repeated calls
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.propagate = False
    return logger
