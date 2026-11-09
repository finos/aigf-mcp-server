# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""
Error boundary utilities for graceful error handling and recovery.

A circuit breaker, which the HTTP client keeps per host, and a context manager
that logs an operation's failure and raises it as an ``MCPServerError``. The
retry decorator, the fallback decorator and the recovery context that used to
live here had no caller that reached them (#307), nor had the breaker's
decorator form (#376).
"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from .exceptions import MCPServerError, ToolExecutionError
from .logging import get_logger

logger = get_logger(__name__)


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60,
    ):
        """
        Args:
            failure_threshold: Failures in a row that open the breaker.
            recovery_timeout: Seconds the breaker stays open.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "closed"  # closed, open, half-open

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def can_execute(self) -> bool:
        """Check whether operation execution is currently allowed."""
        if self.state == "closed":
            return True
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
                return True
            return False
        # half-open
        return True

    def is_refusing(self) -> bool:
        """Report whether a call made now would be refused, changing nothing.

        ``can_execute`` answers the same question but moves an open breaker to
        half-open once its window has passed, and ``get_service_diagnostics``
        reports any state but ``open`` as closed. This is for a caller that
        only wants to know.
        """
        return self.state == "open" and not self._should_attempt_reset()

    def on_success(self) -> None:
        """Record a call that succeeded."""
        was_half_open = self.state == "half-open"
        # Reset on any success to avoid stale failure accumulation.
        self.state = "closed"
        self.failure_count = 0
        self.last_failure_time = None
        if was_half_open:
            logger.info("Circuit breaker closed after successful recovery")

    def on_failure(self, reason: object) -> None:
        """Record a call that failed. ``reason`` is what the record says."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.error(
                f"Circuit breaker opened after {self.failure_count} failures",
                extra={"exception": str(reason)},
            )


@asynccontextmanager
async def error_boundary(
    operation_name: str,
    context: dict[str, Any] | None = None,
) -> AsyncIterator[None]:
    """Log an operation's failure, then raise it as an ``MCPServerError``.

    An ``MCPServerError`` is re-raised as it is; any other exception is
    raised as a ``ToolExecutionError`` that names it, chained to it.

    Args:
        operation_name: Name of the operation for logging
        context: Additional context for error logging
    """
    try:
        yield

    except MCPServerError as e:
        # Structured MCP errors are already properly formatted
        logger.error(
            f"Operation {operation_name} failed with MCP error",
            extra={"error_details": e.to_dict(), "context": context},
        )
        raise

    except Exception as e:
        # Convert unstructured exceptions to structured ones
        logger.error(
            f"Operation {operation_name} failed with unexpected error",
            extra={
                "exception_type": type(e).__name__,
                "exception_message": str(e),
                "context": context,
            },
            exc_info=True,
        )
        raise ToolExecutionError(
            tool_name=operation_name,
            reason=f"{type(e).__name__}: {e!s}",
            context=context,
        ) from e
