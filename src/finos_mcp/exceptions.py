# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""
Standardized exception types for the FINOS MCP server.

This module provides a hierarchy of specific exceptions to replace broad
exception handling throughout the codebase. Each exception type includes
proper context, error codes, and recovery guidance.
"""

from collections.abc import Sequence
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


class UnknownDocumentError(ContentNotFoundError):
    """No document of this kind has the id the caller asked for.

    Raised by ``get_risk``, ``get_mitigation`` and ``get_framework`` rather
    than returned as a record: a "not found" sentence in a successful result
    arrives in the field a caller reads as the document (#193). The message is
    what the client is shown, so it names the listing tool that holds the
    valid ids.

    A short id two documents share names no one document either (#349);
    ``candidates`` holds their full ids, and the message names them.
    """

    def __init__(
        self,
        resource_id: str,
        resource_type: str,
        listing_tool: str,
        candidates: Sequence[str] = (),
    ):
        super().__init__(resource_id, resource_type)
        if candidates:
            self.message = (
                f"The id '{resource_id}' names more than one {resource_type}: "
                f"{', '.join(candidates)}. Ask for one by its full id."
            )
        else:
            self.message = (
                f"No {resource_type} has the id '{resource_id}'. "
                f"Call {listing_tool} for the valid ids."
            )
        self.args = (self.message,)
        self.context["listing_tool"] = listing_tool


class DocumentUnavailableError(ContentError):
    """A document that exists could not be served.

    Raised by ``get_risk``, ``get_mitigation`` and ``get_framework`` rather
    than returned as a record, for the reason ``UnknownDocumentError`` is: a
    sentence saying so in a successful result arrives in the field a caller
    reads as the document (#216). The message is what the client is shown. It
    names the document and one of the three things that can have happened,
    and nothing of the exception underneath.
    """

    #: The fetch returned nothing, or failed in a way nobody planned for.
    NOT_LOADED = "could not be loaded. Retry later."
    #: The document was fetched and is over the size this server returns.
    TOO_LARGE = "is too large for this server to return."
    #: The document was fetched and has no body.
    EMPTY = "has no content."

    def __init__(self, resource_id: str, resource_type: str, reason: str):
        super().__init__(
            message=f"The {resource_type} '{resource_id}' {reason}",
            error_code="DOCUMENT_UNAVAILABLE",
            context={"resource_id": resource_id, "resource_type": resource_type},
            recoverable=reason == self.NOT_LOADED,
        )


class SearchFailedError(MCPServerError):
    """``search_frameworks`` has no answer to give.

    Raised rather than returned as an empty result: ``total_found: 0`` says
    that no framework has the phrase, and a caller reports that as a fact
    (#224). The message is what the client is shown, and is one of the two
    sentences below. Nothing of the exception underneath is in it.
    """

    #: Every framework was skipped as unservable, so none was searched.
    NOTHING_READ = "No framework could be read, so nothing was searched. Retry later."
    #: The search stopped on something nobody planned for.
    UNEXPECTED = "The search failed before it finished. Retry later."

    def __init__(self, reason: str):
        super().__init__(message=reason, error_code="SEARCH_FAILED", recoverable=True)


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


class ServiceError(MCPServerError):
    """Base class for service-related errors."""

    pass


class GitHubDiscoveryError(ServiceError):
    """A GitHub content-discovery request did not return a directory listing.

    Raised instead of letting the response body be parsed as one. GitHub answers
    an error with a JSON object, and iterating that object walks its keys, so the
    previous behaviour was `TypeError: string indices must be integers, not
    'str'` -- an error that named neither the status code nor the real cause.
    """

    def __init__(
        self,
        reason: str,
        status_code: int | None = None,
        error_code: str = "GITHUB_DISCOVERY_FAILED",
        retry_after: int | None = None,
    ):
        super().__init__(
            message=f"GitHub content discovery failed: {reason}",
            error_code=error_code,
            context={
                "reason": reason,
                "status_code": status_code,
                "retry_after": retry_after,
            },
            recoverable=True,
        )
        #: Seconds before the API is asked again, when the answer or the
        #: backoff that refused this request says (#310).
        self.retry_after = retry_after


class GitHubRateLimitError(GitHubDiscoveryError):
    """The GitHub API rate limit is exhausted.

    Distinct from RateLimitExceededError, which is this server throttling its own
    callers. This one is us being throttled by GitHub, and it is the expected
    outcome of running unauthenticated: 60 requests/hour per IP. Carries its own
    error code so a caller can tell "retry in an hour" apart from "the request
    was wrong".
    """

    def __init__(self, reason: str, retry_after: int | None = None):
        super().__init__(
            reason=reason,
            status_code=403,
            error_code="GITHUB_RATE_LIMIT_EXHAUSTED",
            retry_after=retry_after,
        )


class DocumentThrottledError(GitHubRateLimitError):
    """A GitHub throttle, in the one sentence a client reads (#334).

    The discovery errors prefix their message with "GitHub content discovery
    failed:" for the log. The get tools build one sentence for a client from
    the throttle's retry time and raise it as this, whose message is that
    sentence verbatim: nothing names discovery, and nothing is wrapped twice.
    """

    def __init__(self, sentence: str, retry_after: int | None):
        super().__init__(sentence, retry_after=retry_after)
        self.message = sentence
        self.args = (sentence,)


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
