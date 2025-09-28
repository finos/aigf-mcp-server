"""
Enhanced error reporting and context management for the FINOS MCP server.

Provides structured error reporting with detailed context, performance metrics,
and actionable recovery guidance for operations teams.
"""

import asyncio
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from .exceptions import MCPServerError
from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class ErrorContext:
    """Comprehensive error context information."""

    operation: str
    request_id: str | None = None
    user_id: str | None = None
    component: str | None = None
    endpoint: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    performance_metrics: dict[str, float] = field(default_factory=dict)
    correlation_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert error context to dictionary for logging."""
        return {
            "operation": self.operation,
            "request_id": self.request_id,
            "user_id": self.user_id,
            "component": self.component,
            "endpoint": self.endpoint,
            "parameters": self.parameters,
            "environment": self.environment,
            "performance_metrics": self.performance_metrics,
            "correlation_data": self.correlation_data,
        }


@dataclass
class ErrorReport:
    """Structured error report with comprehensive information."""

    error: Exception
    context: ErrorContext
    timestamp: float
    stack_trace: str
    error_id: str
    severity: str = "error"
    recoverable: bool = True
    recovery_suggestions: list[str] = field(default_factory=list)
    related_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert error report to dictionary for logging and analysis."""
        error_data = {
            "error_id": self.error_id,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "recoverable": self.recoverable,
            "error_type": type(self.error).__name__,
            "error_message": str(self.error),
            "stack_trace": self.stack_trace,
            "context": self.context.to_dict(),
            "recovery_suggestions": self.recovery_suggestions,
            "related_errors": self.related_errors,
        }

        # Add structured exception data if available
        if isinstance(self.error, MCPServerError):
            error_data.update(self.error.to_dict())

        return error_data


class ErrorReporter:
    """Enhanced error reporting system with context management."""

    def __init__(self) -> None:
        self.error_history: list[ErrorReport] = []
        self.context_stack: list[ErrorContext] = []
        self.correlation_id: str | None = None
        self._lock = asyncio.Lock()

    async def push_context(self, context: ErrorContext) -> None:
        """Push a new error context onto the stack."""
        async with self._lock:
            self.context_stack.append(context)

    async def pop_context(self) -> ErrorContext | None:
        """Pop the most recent error context from the stack."""
        async with self._lock:
            return self.context_stack.pop() if self.context_stack else None

    async def get_current_context(self) -> ErrorContext | None:
        """Get the current error context without removing it."""
        async with self._lock:
            return self.context_stack[-1] if self.context_stack else None

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set correlation ID for tracking related operations."""
        self.correlation_id = correlation_id

    async def report_error(
        self,
        error: Exception,
        context_override: ErrorContext | None = None,
        severity: str = "error",
        recovery_suggestions: list[str] | None = None,
    ) -> ErrorReport:
        """Report an error with comprehensive context."""
        import time
        import uuid

        current_context = context_override or await self.get_current_context()

        if current_context is None:
            current_context = ErrorContext(operation="unknown")

        # Add correlation information
        if self.correlation_id:
            current_context.correlation_data["correlation_id"] = self.correlation_id

        # Generate comprehensive error report
        error_report = ErrorReport(
            error=error,
            context=current_context,
            timestamp=time.time(),
            stack_trace=traceback.format_exc(),
            error_id=str(uuid.uuid4()),
            severity=severity,
            recoverable=getattr(error, "recoverable", True),
            recovery_suggestions=recovery_suggestions
            or self._generate_recovery_suggestions(error),
            related_errors=self._find_related_errors(error),
        )

        # Store in history (keep last 100 errors)
        async with self._lock:
            self.error_history.append(error_report)
            if len(self.error_history) > 100:
                self.error_history.pop(0)

        # Log structured error report
        await self._log_error_report(error_report)

        return error_report

    def _generate_recovery_suggestions(self, error: Exception) -> list[str]:
        """Generate actionable recovery suggestions based on error type."""
        suggestions = []

        if isinstance(error, MCPServerError):
            if error.error_code == "CONTENT_NOT_FOUND":
                suggestions.extend(
                    [
                        "Verify the resource identifier is correct",
                        "Check if the content source is accessible",
                        "Try refreshing the content cache",
                    ]
                )
            elif error.error_code == "CONTENT_LOADING_FAILED":
                suggestions.extend(
                    [
                        "Check network connectivity",
                        "Verify GitHub API rate limits",
                        "Try again after a short delay",
                        "Check if GitHub service is operational",
                    ]
                )
            elif error.error_code == "RATE_LIMIT_EXCEEDED":
                suggestions.extend(
                    [
                        "Reduce request frequency",
                        "Implement exponential backoff",
                        "Consider upgrading API limits",
                    ]
                )
            elif error.error_code == "CACHE_OPERATION_FAILED":
                suggestions.extend(
                    [
                        "Check available disk space",
                        "Verify cache directory permissions",
                        "Try clearing the cache",
                    ]
                )

        # Generic suggestions based on exception type
        if isinstance(error, (ConnectionError, TimeoutError)):
            suggestions.extend(
                [
                    "Check network connectivity",
                    "Verify service endpoints are accessible",
                    "Consider increasing timeout values",
                ]
            )
        elif isinstance(error, PermissionError):
            suggestions.extend(
                [
                    "Check file/directory permissions",
                    "Verify user has required access rights",
                    "Check security policies",
                ]
            )
        elif isinstance(error, MemoryError):
            suggestions.extend(
                [
                    "Reduce data processing batch size",
                    "Increase available memory",
                    "Check for memory leaks",
                ]
            )

        return suggestions or ["Contact support with error ID for assistance"]

    def _find_related_errors(self, error: Exception) -> list[str]:
        """Find related errors in recent history."""
        related = []
        error_type = type(error).__name__
        error_message_words = str(error).lower().split()

        for recent_error in self.error_history[-10:]:  # Check last 10 errors
            recent_type = type(recent_error.error).__name__
            recent_message_words = str(recent_error.error).lower().split()

            # Same error type
            if recent_type == error_type:
                related.append(recent_error.error_id)
            # Similar error message (common words)
            elif len(set(error_message_words) & set(recent_message_words)) >= 2:
                related.append(recent_error.error_id)

        return related

    async def _log_error_report(self, error_report: ErrorReport) -> None:
        """Log structured error report."""
        log_data = error_report.to_dict()

        if error_report.severity == "critical":
            logger.critical(
                f"Critical error in {error_report.context.operation}: {error_report.error}",
                extra={"error_report": log_data},
            )
        elif error_report.severity == "error":
            logger.error(
                f"Error in {error_report.context.operation}: {error_report.error}",
                extra={"error_report": log_data},
            )
        elif error_report.severity == "warning":
            logger.warning(
                f"Warning in {error_report.context.operation}: {error_report.error}",
                extra={"error_report": log_data},
            )

    async def get_error_summary(self, last_n: int = 10) -> dict[str, Any]:
        """Get summary of recent errors for monitoring."""
        async with self._lock:
            recent_errors = self.error_history[-last_n:]

        if not recent_errors:
            return {
                "total_errors": 0,
                "error_types": {},
                "most_common_operations": {},
                "recovery_success_rate": 0.0,
            }

        error_types: dict[str, int] = {}
        operations: dict[str, int] = {}
        recoverable_count = 0

        for error_report in recent_errors:
            # Count error types
            error_type = type(error_report.error).__name__
            error_types[error_type] = error_types.get(error_type, 0) + 1

            # Count operations
            operation = error_report.context.operation
            operations[operation] = operations.get(operation, 0) + 1

            # Count recoverable errors
            if error_report.recoverable:
                recoverable_count += 1

        return {
            "total_errors": len(recent_errors),
            "error_types": dict(
                sorted(error_types.items(), key=lambda x: x[1], reverse=True)
            ),
            "most_common_operations": dict(
                sorted(operations.items(), key=lambda x: x[1], reverse=True)
            ),
            "recovery_success_rate": recoverable_count / len(recent_errors)
            if recent_errors
            else 0.0,
            "recent_error_ids": [report.error_id for report in recent_errors],
        }


# Global error reporter instance
_error_reporter: ErrorReporter | None = None
_reporter_lock = asyncio.Lock()


async def get_error_reporter() -> ErrorReporter:
    """Get or create the global error reporter instance."""
    global _error_reporter

    if _error_reporter is None:
        async with _reporter_lock:
            if _error_reporter is None:
                _error_reporter = ErrorReporter()

    return _error_reporter


@asynccontextmanager
async def error_context(
    operation: str,
    component: str | None = None,
    request_id: str | None = None,
    **kwargs,
):
    """Context manager for enhanced error reporting."""
    reporter = await get_error_reporter()

    context = ErrorContext(
        operation=operation, component=component, request_id=request_id, **kwargs
    )

    await reporter.push_context(context)

    try:
        yield context
    except Exception as e:
        # Report the error with current context
        await reporter.report_error(e)
        raise
    finally:
        await reporter.pop_context()


async def report_error(
    error: Exception,
    operation: str | None = None,
    severity: str = "error",
    recovery_suggestions: list[str] | None = None,
    **context_kwargs,
) -> ErrorReport:
    """Report an error with optional context override."""
    reporter = await get_error_reporter()

    context_override = None
    if operation:
        context_override = ErrorContext(operation=operation, **context_kwargs)

    return await reporter.report_error(
        error=error,
        context_override=context_override,
        severity=severity,
        recovery_suggestions=recovery_suggestions,
    )


async def get_error_summary(last_n: int = 10) -> dict[str, Any]:
    """Get summary of recent errors for monitoring."""
    reporter = await get_error_reporter()
    return await reporter.get_error_summary(last_n)
