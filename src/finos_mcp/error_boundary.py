"""
Error boundary utilities for graceful error handling and recovery.

Provides decorators and context managers for implementing error boundaries
throughout the MCP server. Includes circuit breaker patterns, retry logic,
and structured error reporting.
"""

import asyncio
import functools
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from .exceptions import (
    CircuitBreakerError,
    ContentLoadingError,
    HTTPClientError,
    MCPServerError,
    ServiceUnavailableError,
    ToolExecutionError,
)
from .logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[Exception] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "closed"  # closed, open, half-open

    def __call__(
        self, func: Callable[..., Awaitable[T]]
    ) -> Callable[..., Awaitable[T]]:
        """Decorator for applying circuit breaker to async functions."""

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if self.state == "open":
                if self._should_attempt_reset():
                    self.state = "half-open"
                    logger.info(f"Circuit breaker half-open for {func.__name__}")
                else:
                    raise CircuitBreakerError(
                        service_name=func.__name__,
                        failure_count=self.failure_count,
                        retry_after=self.recovery_timeout,
                    )

            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result

            except self.expected_exception as e:
                self._on_failure(e)
                raise

        return wrapper

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self) -> None:
        """Handle successful operation."""
        if self.state == "half-open":
            self.state = "closed"
            self.failure_count = 0
            logger.info("Circuit breaker closed after successful recovery")

    def _on_failure(self, exception: Exception) -> None:
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.error(
                f"Circuit breaker opened after {self.failure_count} failures",
                extra={"exception": str(exception)},
            )


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (
        ContentLoadingError,
        HTTPClientError,
        ServiceUnavailableError,
    ),
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for adding retry logic with exponential backoff."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)

                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts",
                            extra={"exception": str(e), "attempt": attempt + 1},
                        )
                        break

                    delay = min(base_delay * (exponential_base**attempt), max_delay)
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_attempts}), retrying in {delay}s",
                        extra={"exception": str(e), "delay": delay},
                    )

                    await asyncio.sleep(delay)

                except Exception as e:
                    # Non-retryable exception
                    logger.error(
                        f"Function {func.__name__} failed with non-retryable exception",
                        extra={"exception": str(e)},
                    )
                    raise

            # Re-raise the last exception if all retries failed
            if last_exception:
                raise last_exception

            # This should never happen, but just in case
            raise RuntimeError(f"Function {func.__name__} failed unexpectedly")

        return wrapper

    return decorator


@asynccontextmanager
async def error_boundary(
    operation_name: str,
    fallback_value: T | None = None,
    suppress_exceptions: bool = False,
    context: dict[str, Any] | None = None,
):
    """Context manager for implementing error boundaries.

    Args:
        operation_name: Name of the operation for logging
        fallback_value: Value to return if an exception occurs and suppress_exceptions is True
        suppress_exceptions: If True, exceptions are logged but not re-raised
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

        if not suppress_exceptions:
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

        if not suppress_exceptions:
            # Wrap in structured exception
            raise ToolExecutionError(
                tool_name=operation_name,
                reason=f"{type(e).__name__}: {e!s}",
                context=context,
            ) from e


def safe_async_operation(
    operation_name: str,
    fallback_value: T | None = None,
    log_errors: bool = True,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T | None]]]:
    """Decorator for making async operations safe with optional fallback values."""

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T | None]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T | None:
            try:
                return await func(*args, **kwargs)

            except MCPServerError as e:
                if log_errors:
                    logger.error(
                        f"Safe operation {operation_name} failed with MCP error",
                        extra={"error_details": e.to_dict()},
                    )
                return fallback_value

            except Exception as e:
                if log_errors:
                    logger.error(
                        f"Safe operation {operation_name} failed with unexpected error",
                        extra={
                            "exception_type": type(e).__name__,
                            "exception_message": str(e),
                        },
                        exc_info=True,
                    )
                return fallback_value

        return wrapper

    return decorator


class ErrorRecoveryContext:
    """Context for tracking error recovery attempts and patterns."""

    def __init__(self) -> None:
        self.recovery_attempts: dict[str, int] = {}
        self.last_errors: dict[str, float] = {}

    def should_attempt_recovery(
        self, operation: str, max_attempts: int = 3, cooldown: int = 300
    ) -> bool:
        """Check if recovery should be attempted for an operation."""
        current_time = time.time()

        # Check if we're in cooldown period
        if operation in self.last_errors:
            if current_time - self.last_errors[operation] < cooldown:
                return False

        # Check attempt count
        attempts = self.recovery_attempts.get(operation, 0)
        return attempts < max_attempts

    def record_recovery_attempt(self, operation: str, success: bool) -> None:
        """Record a recovery attempt."""
        current_time = time.time()

        if success:
            # Reset counters on success
            self.recovery_attempts.pop(operation, None)
            self.last_errors.pop(operation, None)
        else:
            # Increment attempt counter and update timestamp
            self.recovery_attempts[operation] = (
                self.recovery_attempts.get(operation, 0) + 1
            )
            self.last_errors[operation] = current_time


# Global error recovery context
_error_recovery_context = ErrorRecoveryContext()


def get_error_recovery_context() -> ErrorRecoveryContext:
    """Get the global error recovery context."""
    return _error_recovery_context
