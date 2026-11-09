# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Structured logging for FINOS MCP Server.

Copyright 2025 FINOS

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

This module provides JSON structured logging with security features including:
- PII/secret redaction for GitHub tokens, URLs with authentication
- Request correlation IDs for distributed tracing
- Configurable log levels via environment variables
- Structured output for observability tools
"""

import contextvars
import json
import logging
import re
import time
import uuid
from typing import Any, ClassVar, Optional

from .config import GITHUB_TOKEN_PREFIXES, get_settings

# Context variable for request correlation ID
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


class SecureJSONFormatter(logging.Formatter):
    """JSON formatter with PII/secret redaction capabilities.

    Automatically redacts, in the message, the exception and the extra fields:
    - GitHub tokens (every prefix in ``config.GITHUB_TOKEN_PREFIXES``, #290)
    - URLs with authentication (user:pass@host)
    - Authorization headers
    - API keys and secrets
    """

    # Patterns for sensitive data redaction
    REDACTION_PATTERNS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        # GitHub tokens, one pattern for every prefix the settings know. A
        # token body is 36 characters or more in every form GitHub issues.
        (
            re.compile(
                "(?:"
                + "|".join(re.escape(prefix) for prefix in GITHUB_TOKEN_PREFIXES)
                + r")[A-Za-z0-9_]{36,255}",
                re.IGNORECASE,
            ),
            "[REDACTED_GITHUB_TOKEN]",
        ),
        # URLs with authentication
        (
            re.compile(r"(https?://)[^@\s]+:[^@\s]+@([^/\s]+)", re.IGNORECASE),
            r"\1[REDACTED_AUTH]@\2",
        ),
        # Authorization headers
        (
            re.compile(
                r'authorization[\'\"]\s*:\s*[\'\"](Bearer\s+)?[^\'"]+[\'"]',
                re.IGNORECASE,
            ),
            'authorization": "[REDACTED_BEARER_TOKEN]"',
        ),
        # Generic API keys and secrets
        (
            re.compile(
                r'([\'\"](api[_-]?key|secret|token|password)[\'\"]\s*:\s*[\'\"])[^\'"]*([\'"])',
                re.IGNORECASE,
            ),
            r"\1[REDACTED]\3",
        ),
        # Environment variables containing secrets
        (
            re.compile(
                r"((?:API_KEY|SECRET|TOKEN|PASSWORD)\s*=\s*)[^\s]+", re.IGNORECASE
            ),
            r"\1[REDACTED]",
        ),
    ]

    def __init__(
        self, include_timestamp: bool = True, include_correlation_id: bool = True
    ):
        """Initialize the JSON formatter.

        Args:
            include_timestamp: Include timestamp in log output
            include_correlation_id: Include request correlation ID

        """
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_correlation_id = include_correlation_id

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with redaction."""
        # Base log data
        log_data: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": self._redact_sensitive_data(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add timestamp if requested
        if self.include_timestamp:
            log_data["timestamp"] = self._format_timestamp(record.created)

        # Add correlation ID if available and requested
        if self.include_correlation_id:
            correlation_id = request_id_var.get()
            if correlation_id:
                log_data["correlation_id"] = correlation_id

        # Add exception information if present
        if record.exc_info:
            # An exception's words are whatever raised it put there, a
            # credential included, so they pass the same redaction (#290).
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": self._redact_sensitive_data(str(record.exc_info[1]))
                if record.exc_info[1]
                else None,
                "traceback": self._redact_sensitive_data(
                    self.formatException(record.exc_info)
                ),
            }

        # Add extra fields from log record
        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key
            not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "message",
            }
        }

        if extra_fields:
            # Redact sensitive data in extra fields
            for key, value in extra_fields.items():
                if isinstance(value, str):
                    extra_fields[key] = self._redact_sensitive_data(value)
                elif isinstance(value, dict):
                    extra_fields[key] = self._redact_dict_values(value)

            log_data["extra"] = extra_fields

        return json.dumps(log_data, ensure_ascii=False, separators=(",", ":"))

    def _format_timestamp(self, created: float) -> str:
        """Format timestamp in ISO 8601 format."""
        return (
            time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(created))
            + f".{int((created % 1) * 1000):03d}Z"
        )

    def _redact_sensitive_data(self, text: str) -> str:
        """Apply redaction patterns to text."""
        result = text
        for pattern, replacement in self.REDACTION_PATTERNS:
            result = pattern.sub(replacement, result)

        return result

    def _redact_dict_values(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact sensitive data in dictionary values."""
        result: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self._redact_sensitive_data(value)
            elif isinstance(value, dict):
                result[key] = self._redact_dict_values(value)
            elif isinstance(value, list):
                result[key] = [
                    self._redact_sensitive_data(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result


def generate_correlation_id() -> str:
    """Generate a new correlation ID for request tracing."""
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: str | None = None) -> str:
    """Set correlation ID for current context.

    Args:
        correlation_id: Specific ID to use, or None to generate new one

    Returns:
        The correlation ID that was set

    """
    if correlation_id is None:
        correlation_id = generate_correlation_id()

    request_id_var.set(correlation_id)
    return correlation_id


def _bare_app_logger(logger_name: str = "finos-ai-governance-mcp") -> logging.Logger:
    """The application logger before the settings are read.

    Modules take their loggers at import, before ``validate_settings_on_startup``
    has built the settings, so this reads none: it formats and redacts as the
    configured logger does, and leaves the level to the root default until
    ``setup_structured_logging`` sets it (#300).
    """
    logger = logging.getLogger(logger_name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            SecureJSONFormatter(include_timestamp=True, include_correlation_id=True)
        )
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def setup_structured_logging(
    logger_name: str = "finos-ai-governance-mcp",
) -> logging.Logger:
    """Setup structured JSON logging for the application.

    Reads the settings, so it is called once, by
    ``validate_settings_on_startup``, after they are built; ``get_logger``
    does not call it (#300).

    One formatter in both modes. The debug mode used to install a plain
    formatter naming ``%(correlation_id)s``, a field only a document fetch
    set, so every other record became a "Logging error" with a stack, and
    nothing was redacted (#299).

    Args:
        logger_name: Name of the logger to configure

    Returns:
        Configured logger instance

    """
    settings = get_settings()

    # Get or create logger
    logger = logging.getLogger(logger_name)

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Set log level from settings
    log_level = getattr(logging, settings.log_level.upper())  # pylint: disable=no-member
    logger.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    formatter = SecureJSONFormatter(include_timestamp=True, include_correlation_id=True)
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    # Records of other libraries (httpx, fastmcp, uvicorn) reach the root
    # handler. It formats with the same redaction, so a credential in a
    # third-party message is not logged whole either (#290).
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for handler in root.handlers:
        handler.setFormatter(formatter)

    return logger


def log_http_request(
    logger: logging.Logger,
    method: str,
    url: str,
    *,
    status_code: int | None = None,
    response_time: float | None = None,
    extra_data: dict[str, Any] | None = None,
) -> None:
    """Log HTTP request with structured data and redaction.

    Args:
        logger: Logger instance to use
        method: HTTP method (GET, POST, etc.)
        url: Request URL (will be redacted if contains auth)
        status_code: HTTP response status code
        response_time: Request duration in seconds
        extra_data: Additional data to include in log

    """
    log_data: dict[str, Any] = {
        "event_type": "http_request",
        "http_method": method,
        "http_url": url,  # Will be redacted by formatter
    }

    if status_code is not None:
        log_data["http_status"] = status_code

    if response_time is not None:
        log_data["response_time_ms"] = round(response_time * 1000, 2)

    if extra_data:
        log_data.update(extra_data)

    # Log level based on status code
    if status_code and status_code >= 400:
        log_level = logging.WARNING if status_code < 500 else logging.ERROR
    else:
        log_level = logging.INFO

    logger.log(log_level, f"HTTP {method} {url}", extra=log_data)


def create_child_logger(
    parent_logger: logging.Logger, child_name: str
) -> logging.Logger:
    """Create a child logger that inherits parent's configuration.

    Args:
        parent_logger: Parent logger to inherit from
        child_name: Name for the child logger

    Returns:
        Child logger instance

    """
    child_logger_name = f"{parent_logger.name}.{child_name}"
    # No level of its own: the child follows the parent, whose level is set
    # once by validate_settings_on_startup(). An explicit copy of the parent's
    # level at creation froze whatever it was at import time (#300).
    return logging.getLogger(child_logger_name)


class LoggerManager:
    """Singleton manager for the global application logger."""

    _instance: Optional["LoggerManager"] = None
    _app_logger: logging.Logger | None = None

    def __new__(cls) -> "LoggerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_logger(self, name: str | None = None) -> logging.Logger:
        """Get configured application logger.

        Args:
            name: Optional logger name, defaults to main app logger

        Returns:
            Configured logger instance

        """
        if self._app_logger is None:
            self._app_logger = _bare_app_logger()

        if name:
            return create_child_logger(self._app_logger, name)

        return self._app_logger


# Global logger manager instance
_logger_manager = LoggerManager()


def get_logger(name: str | None = None) -> logging.Logger:
    """Get configured application logger.

    Args:
        name: Optional logger name, defaults to main app logger

    Returns:
        Configured logger instance

    """
    return _logger_manager.get_logger(name)
