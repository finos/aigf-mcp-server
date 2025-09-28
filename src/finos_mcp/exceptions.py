"""
Standardized exception types for the FINOS MCP server.

This module provides a hierarchy of specific exceptions to replace broad
exception handling throughout the codebase. Each exception type includes
proper context, error codes, and recovery guidance.
"""

from typing import Any


class MCPServerError(Exception):
    """Base exception for all MCP server errors.

    Provides structured error information with context and recovery guidance.
    """

    def __init__(
        self,
        message: str,
        error_code: str,
        context: dict[str, Any] | None = None,
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.recoverable = recoverable

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging and reporting."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
            "recoverable": self.recoverable,
        }


class ContentError(MCPServerError):
    """Base class for content-related errors."""

    pass


class ContentNotFoundError(ContentError):
    """Content could not be found."""

    def __init__(self, resource_id: str, resource_type: str = "content"):
        super().__init__(
            message=f"{resource_type.title()} not found: {resource_id}",
            error_code="CONTENT_NOT_FOUND",
            context={"resource_id": resource_id, "resource_type": resource_type},
            recoverable=False,
        )


class ContentLoadingError(ContentError):
    """Content loading failed due to external service issues."""

    def __init__(self, source: str, details: str, retry_after: int | None = None):
        super().__init__(
            message=f"Failed to load content from {source}: {details}",
            error_code="CONTENT_LOADING_FAILED",
            context={
                "source": source,
                "details": details,
                "retry_after": retry_after,
            },
            recoverable=True,
        )


class ContentValidationError(ContentError):
    """Content failed validation checks."""

    def __init__(
        self, validation_type: str, details: str, content_id: str | None = None
    ):
        super().__init__(
            message=f"Content validation failed ({validation_type}): {details}",
            error_code="CONTENT_VALIDATION_FAILED",
            context={
                "validation_type": validation_type,
                "details": details,
                "content_id": content_id,
            },
            recoverable=False,
        )


class SecurityError(MCPServerError):
    """Base class for security-related errors."""

    def __init__(
        self, message: str, error_code: str, context: dict[str, Any] | None = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            context=context,
            recoverable=False,  # Security errors are generally not recoverable
        )


class ContentSecurityError(SecurityError):
    """Content failed security validation."""

    def __init__(self, reason: str, content_type: str = "content"):
        super().__init__(
            message=f"Content security validation failed: {reason}",
            error_code="CONTENT_SECURITY_VIOLATION",
            context={"reason": reason, "content_type": content_type},
        )


class RequestTooLargeError(SecurityError):
    """Request exceeds size limits."""

    def __init__(self, actual_size: int, max_size: int, request_type: str = "request"):
        super().__init__(
            message=f"{request_type.title()} size {actual_size} exceeds limit {max_size}",
            error_code="REQUEST_TOO_LARGE",
            context={
                "actual_size": actual_size,
                "max_size": max_size,
                "request_type": request_type,
            },
        )


class RateLimitExceededError(SecurityError):
    """Client exceeded rate limits."""

    def __init__(
        self, client_id: str, limit_type: str, current_value: int, max_value: int
    ):
        super().__init__(
            message=f"Rate limit exceeded for {client_id}: {limit_type} {current_value}/{max_value}",
            error_code="RATE_LIMIT_EXCEEDED",
            context={
                "client_id": client_id,
                "limit_type": limit_type,
                "current_value": current_value,
                "max_value": max_value,
            },
        )


class ServiceError(MCPServerError):
    """Base class for service-related errors."""

    pass


class ServiceUnavailableError(ServiceError):
    """External service is unavailable."""

    def __init__(self, service_name: str, reason: str, retry_after: int | None = None):
        super().__init__(
            message=f"Service {service_name} is unavailable: {reason}",
            error_code="SERVICE_UNAVAILABLE",
            context={
                "service_name": service_name,
                "reason": reason,
                "retry_after": retry_after,
            },
            recoverable=True,
        )


class CacheError(ServiceError):
    """Cache operation failed."""

    def __init__(self, operation: str, details: str):
        super().__init__(
            message=f"Cache {operation} failed: {details}",
            error_code="CACHE_OPERATION_FAILED",
            context={"operation": operation, "details": details},
            recoverable=True,
        )


class HTTPClientError(ServiceError):
    """HTTP client operation failed."""

    def __init__(self, url: str, status_code: int | None = None, details: str = ""):
        super().__init__(
            message=f"HTTP request to {url} failed"
            + (f" ({status_code})" if status_code else "")
            + (f": {details}" if details else ""),
            error_code="HTTP_REQUEST_FAILED",
            context={
                "url": url,
                "status_code": status_code,
                "details": details,
            },
            recoverable=True,
        )


class ConfigurationError(MCPServerError):
    """Configuration is invalid or missing."""

    def __init__(self, config_key: str, reason: str):
        super().__init__(
            message=f"Configuration error for {config_key}: {reason}",
            error_code="CONFIGURATION_ERROR",
            context={"config_key": config_key, "reason": reason},
            recoverable=False,
        )


class ToolExecutionError(MCPServerError):
    """MCP tool execution failed."""

    def __init__(
        self, tool_name: str, reason: str, context: dict[str, Any] | None = None
    ):
        super().__init__(
            message=f"Tool {tool_name} execution failed: {reason}",
            error_code="TOOL_EXECUTION_FAILED",
            context={"tool_name": tool_name, "reason": reason, **(context or {})},
            recoverable=True,
        )


class CircuitBreakerError(ServiceError):
    """Circuit breaker is open, preventing operation."""

    def __init__(self, service_name: str, failure_count: int, retry_after: int):
        super().__init__(
            message=f"Circuit breaker open for {service_name} after {failure_count} failures",
            error_code="CIRCUIT_BREAKER_OPEN",
            context={
                "service_name": service_name,
                "failure_count": failure_count,
                "retry_after": retry_after,
            },
            recoverable=True,
        )
