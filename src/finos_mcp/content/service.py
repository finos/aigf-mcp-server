# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Content service orchestrator with error boundaries for FINOS MCP Server.

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

CONTENT ATTRIBUTION:
This module accesses AI governance content from the FINOS AI Governance Framework
(https://github.com/finos/ai-governance-framework) by FINOS and contributors,
licensed under Creative Commons Attribution 4.0 International License
(https://creativecommons.org/licenses/by/4.0/).

This module provides a unified service layer that coordinates HTTP client,
frontmatter parser, and caching operations with comprehensive error handling
and circuit breaker patterns to ensure system resilience.
"""

import asyncio
import time
import traceback
from dataclasses import dataclass
from enum import Enum
from types import TracebackType
from typing import Any, Optional
from urllib.parse import urljoin

from ..config import get_settings
from ..error_boundary import CircuitBreaker, error_boundary
from ..exceptions import (
    CacheError,
    ContentLoadingError,
    ContentValidationError,
    GitHubRateLimitError,
    HTTPClientError,
)
from ..logging import get_logger, set_correlation_id
from .cache import TTLCache, close_cache, get_cache
from .fetch import HTTPClient, close_http_client, get_http_client
from .github_api import DIRECTORIES, retry_after_if_rate_limited
from .parse import get_parser_stats, parse_frontmatter

logger = get_logger("content_service")


class ServiceStatus(Enum):
    """Service health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    CRITICAL = "critical"


class OperationResult(Enum):
    """Operation result types."""

    SUCCESS = "success"
    CACHE_HIT = "cache_hit"
    FAILURE = "failure"


@dataclass  # pylint: disable=too-many-instance-attributes
class ServiceHealth:
    """Service health information."""

    status: ServiceStatus
    uptime_seconds: float
    success_rate: float
    last_error: str | None
    last_error_time: float | None
    total_requests: int
    successful_requests: int
    failed_requests: int
    circuit_breaker_trips: int
    cache_hit_rate: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "uptime_seconds": self.uptime_seconds,
            "success_rate": round(self.success_rate, 3),
            "last_error": self.last_error,
            "last_error_time": self.last_error_time,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "circuit_breaker_trips": self.circuit_breaker_trips,
            "cache_hit_rate": round(self.cache_hit_rate, 3),
        }


@dataclass  # pylint: disable=too-many-instance-attributes
class OperationContext:
    """Context for service operations."""

    operation_id: str
    doc_type: str
    filename: str
    url: str
    start_time: float
    correlation_id: str | None = None
    cache_enabled: bool = True
    ttl_override: float | None = None

    # Seconds the content host asked us to wait, when the fetch was throttled.
    # Recorded so get_document can tell the caller "GitHub is throttling us,
    # retry in N seconds" apart from "this document does not exist", which
    # used to be the identical string "Failed to load content for X".
    #
    # This lives on the per-request context, not on the service, because
    # documents are fetched concurrently: service-level state would report one
    # request's failure against another's result.
    retry_after: int | None = None


def _rate_limit_retry_after(exc: BaseException) -> int | None:
    """Walk an exception chain for a throttled HTTP response.

    The raw route's 429 surfaces as an httpx.HTTPStatusError raised deep in
    the fetch stack and is re-wrapped as ContentLoadingError on the way out,
    so the status is only reachable through __cause__/__context__. The rule
    that reads the answer is github_api's, the same one the API route uses.
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        response = getattr(current, "response", None)
        if response is not None:
            delay = retry_after_if_rate_limited(
                getattr(response, "status_code", None),
                getattr(response, "headers", None),
            )
            if delay is not None:
                return delay
        current = current.__cause__ or current.__context__
    return None


class ContentService:  # pylint: disable=too-many-instance-attributes
    """Content service orchestrator with error boundaries and health monitoring.

    Coordinates HTTP fetching, frontmatter parsing, and caching operations.
    The one circuit breaker a fetch passes is the HTTP client's, per host
    (#307); this class reads it for its health reports.
    """

    def __init__(
        self,
        http_client: HTTPClient | None = None,
        cache: TTLCache[str, Any] | None = None,
    ) -> None:
        """Initialize content service.

        Args:
            http_client: The client to fetch with. None means the shared one,
                asked of its manager on each use and never copied here (#313):
                the managers rebind across loops, and a copy did not.
            cache: The cache to serve from, likewise.
        """
        self.settings = get_settings()
        self.logger = get_logger("content_service")

        # Service start time for uptime calculation
        self.start_time = time.time()

        # Operation statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.circuit_breaker_trips = 0

        self._http_client = http_client
        self._cache = cache

        self.logger.info("Content service initialized")

    async def _get_http_client(self) -> HTTPClient:
        """The client given to the constructor, else the shared one, asked now."""
        return self._http_client or await get_http_client()

    async def _get_cache(self) -> TTLCache[str, Any]:
        """The cache given to the constructor, else the shared one, asked now."""
        return self._cache or await get_cache()

    async def content_host_breaker(self) -> CircuitBreaker:
        """The HTTP client's breaker for the host documents come from."""
        http_client = await self._get_http_client()
        return http_client.circuit_breaker(self.settings.base_url)

    async def _fetch_content_with_boundary(
        self, url: str, context: OperationContext
    ) -> str | None:
        """Fetch a document's text, or None when it could not be had.

        The HTTP client retries a request that got no answer and keeps the
        breaker for the host; a failure of either kind, a refusal and an
        unusable body all end here as None, with the reason logged and a
        throttle recorded on ``context``.
        """

        async def _fetch() -> str:
            http_client = await self._get_http_client()
            try:
                content = await http_client.fetch_text(url)

                # Bounded, not scanned: the HTTP client refuses a body past
                # the size limit as it arrives (#291), and the consumer is a
                # model reading Markdown with the trust boundary stated in
                # SERVER_TRUST_INSTRUCTIONS (#122, #282).
                if not content.strip():
                    raise ContentValidationError(
                        "empty_content", "Retrieved content is empty"
                    )

                self.logger.debug(
                    "Content fetched successfully: %s characters",
                    len(content),
                    extra={
                        "operation_id": context.operation_id,
                        "url": url,
                        "content_length": len(content),
                    },
                )

                return content

            except Exception as e:
                # Convert generic exceptions to structured ones
                if isinstance(
                    e, ContentValidationError | HTTPClientError | ContentLoadingError
                ):
                    raise
                else:
                    raise ContentLoadingError(
                        source=url, details=f"{type(e).__name__}: {e!s}", retry_after=60
                    ) from e

        try:
            async with error_boundary(
                operation_name=f"fetch_content_{context.doc_type}",
                context={"url": url, "operation_id": context.operation_id},
            ):
                return await _fetch()

        except Exception as e:
            context.retry_after = _rate_limit_retry_after(e)
            self.logger.warning(
                "Content fetch failed: %s",
                str(e),
                extra={
                    "operation_id": context.operation_id,
                    "url": url,
                    "error_type": type(e).__name__,
                    "retry_after": context.retry_after,
                },
            )
            return None

    async def _parse_content_with_boundary(
        self, content: str, context: OperationContext
    ) -> tuple[dict[str, Any], str]:
        """Parse content with error boundary protection.

        Args:
            content: Raw content to parse
            context: Operation context

        Returns:
            Tuple of (frontmatter, body)

        Raises:
            ContentValidationError: If content parsing fails
        """
        try:
            async with error_boundary(
                operation_name=f"parse_content_{context.doc_type}",
                context={"operation_id": context.operation_id},
            ):
                # Use asyncio.to_thread for true async parsing (25-35% concurrency improvement)
                frontmatter, body = await asyncio.to_thread(parse_frontmatter, content)

                if not isinstance(frontmatter, dict):
                    raise ContentValidationError(
                        "invalid_frontmatter",
                        "Frontmatter parsing did not return a dictionary",
                    )

                self.logger.debug(
                    "Content parsed successfully: %s frontmatter fields",
                    len(frontmatter),
                    extra={
                        "operation_id": context.operation_id,
                        "frontmatter_fields": len(frontmatter),
                        "body_length": len(body),
                    },
                )

                return frontmatter, body

        except Exception as e:
            if isinstance(e, ContentValidationError):
                raise
            else:
                raise ContentValidationError(
                    "parse_error", f"Failed to parse content: {type(e).__name__}: {e!s}"
                ) from e

    async def _cache_get_with_boundary(
        self, cache_key: str, context: OperationContext
    ) -> dict[str, Any] | None:
        """Get from cache with error boundary protection.

        Args:
            cache_key: Cache key to retrieve
            context: Operation context

        Returns:
            Cached document data or None if not found/error

        Raises:
            CacheError: If cache operation fails
        """
        if not context.cache_enabled or not self.settings.enable_cache:
            return None

        async def _get_from_cache() -> dict[str, Any] | None:
            try:
                cache = await self._get_cache()
                cached_data = await cache.get(cache_key)

                if cached_data:
                    self.logger.debug(
                        "Cache hit for key: %s",
                        cache_key,
                        extra={
                            "operation_id": context.operation_id,
                            "cache_key": cache_key,
                        },
                    )
                else:
                    self.logger.debug(
                        "Cache miss for key: %s",
                        cache_key,
                        extra={
                            "operation_id": context.operation_id,
                            "cache_key": cache_key,
                        },
                    )

                return cached_data

            except Exception as e:
                raise CacheError(
                    "get", f"Failed to retrieve from cache: {type(e).__name__}: {e!s}"
                ) from e

        try:
            async with error_boundary(
                operation_name=f"cache_get_{context.doc_type}",
                context={"cache_key": cache_key, "operation_id": context.operation_id},
            ):
                return await _get_from_cache()

        except Exception as e:
            self.logger.warning(
                "Cache get operation failed: %s",
                str(e),
                extra={
                    "operation_id": context.operation_id,
                    "cache_key": cache_key,
                    "error_type": type(e).__name__,
                },
            )
            return None

    async def _cache_set_with_boundary(
        self, cache_key: str, doc_data: dict[str, Any], context: OperationContext
    ) -> bool:
        """Set cache with error boundary protection.

        Args:
            cache_key: Cache key
            doc_data: Document data to cache
            context: Operation context

        Returns:
            True if cached successfully, False otherwise

        """
        if not context.cache_enabled or not self.settings.enable_cache:
            return False

        async def _set_to_cache() -> bool:
            try:
                cache = await self._get_cache()
                ttl = context.ttl_override or self.settings.cache_ttl_seconds
                await cache.set(cache_key, doc_data, ttl=ttl)

                self.logger.debug(
                    "Content cached successfully: %s",
                    cache_key,
                    extra={
                        "operation_id": context.operation_id,
                        "cache_key": cache_key,
                        "ttl": ttl,
                    },
                )

                return True

            except Exception as e:
                raise CacheError(
                    "set", f"Failed to store in cache: {type(e).__name__}: {e!s}"
                ) from e

        try:
            async with error_boundary(
                operation_name=f"cache_set_{context.doc_type}",
                context={"cache_key": cache_key, "operation_id": context.operation_id},
            ):
                return await _set_to_cache()

        except Exception as e:
            self.logger.warning(
                "Cache set operation failed: %s",
                str(e),
                extra={
                    "operation_id": context.operation_id,
                    "cache_key": cache_key,
                    "error": str(e),
                },
            )
            return False

    async def get_document(
        self,
        doc_type: str,
        filename: str,
        ttl_override: float | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Get document with comprehensive error handling and caching.

        Args:
            doc_type: Type of document ('mitigation', 'risk', or 'framework')
            filename: Document filename
            ttl_override: Optional TTL override for caching
            correlation_id: Optional correlation ID for tracing

        Returns:
            Parsed document data or None if failed

        """
        # Set up operation context
        operation_id = f"{doc_type}:{filename}:{int(time.time())}"
        if correlation_id is None:
            correlation_id = set_correlation_id()

        directory = DIRECTORIES.get(doc_type)
        if directory is None:
            raise ValueError(f"Unknown document type: {doc_type}")
        base_url = f"{self.settings.base_url}/{directory.subdir}"

        # Secure URL construction to prevent path injection
        # Validate filename contains no path traversal attempts
        if ".." in filename or "/" in filename or "\\" in filename:
            self.failed_requests += 1
            self.logger.error(
                "Invalid filename with path traversal attempt: %s",
                filename,
                extra={
                    "operation_id": operation_id,
                    "security_violation": "path_traversal_attempt",
                    "document_filename": filename,
                },
            )
            return None

        # Use urljoin for safe URL construction
        url = urljoin(base_url.rstrip("/") + "/", filename)

        context = OperationContext(
            operation_id=operation_id,
            doc_type=doc_type,
            filename=filename,
            url=url,
            correlation_id=correlation_id,
            start_time=time.time(),
            ttl_override=ttl_override,
        )

        self.total_requests += 1

        self.logger.info(
            "Document request started: %s/%s",
            doc_type,
            filename,
            extra={
                "operation_id": operation_id,
                "doc_type": doc_type,
                "document_filename": filename,
                "url": url,
                "correlation_id": correlation_id,
            },
        )

        try:
            # Step 1: Check cache first
            cache_key = f"{doc_type}:{filename}"
            cached_data = await self._cache_get_with_boundary(cache_key, context)

            if cached_data:
                self.successful_requests += 1

                self.logger.info(
                    "Document served from cache: %s/%s",
                    doc_type,
                    filename,
                    extra={
                        "operation_id": operation_id,
                        "result": OperationResult.CACHE_HIT.value,
                        "elapsed_ms": (time.time() - context.start_time) * 1000,
                    },
                )

                return cached_data

            # Step 2: Fetch the document from the content host, the host
            # base_url names. That is the one place a body comes from (#312):
            # the Contents API used to be tried after any raw failure, a 404
            # and an open breaker included, and each try spent one of the 60
            # requests an hour discovery depends on. raw.githubusercontent.com
            # is not counted against that budget at all.
            content = await self._fetch_content_with_boundary(url, context)

            if not content:
                self.failed_requests += 1

                self.logger.error(
                    "Failed to fetch document content: %s/%s",
                    doc_type,
                    filename,
                    extra={
                        "operation_id": operation_id,
                        "result": OperationResult.FAILURE.value,
                        # Avoid logging full URL to prevent information disclosure
                        "doc_type": doc_type,
                        "document_filename": filename,
                        "retry_after": context.retry_after,
                    },
                )

                # Throttled. Returning None here would reach the caller as
                # "Failed to load content for X" -- indistinguishable from a
                # document that does not exist, which is what an LLM then
                # reports to the user. Raise instead, so the tools can say what
                # actually happened and when to retry.
                if context.retry_after is not None:
                    raise GitHubRateLimitError(
                        f"GitHub is rate limiting content requests; retry in "
                        f"{context.retry_after} seconds",
                        retry_after=context.retry_after,
                    )

                return None

            # Step 3: Parse content
            frontmatter, body = await self._parse_content_with_boundary(
                content, context
            )

            # Step 4: Create document data
            doc_data = {
                "filename": filename,
                "type": doc_type,
                "url": url,
                "metadata": frontmatter,
                "content": body,
                "full_text": content,
                "retrieved_at": time.time(),
                "operation_id": operation_id,
            }

            # Step 5: Cache the result
            await self._cache_set_with_boundary(cache_key, doc_data, context)

            self.successful_requests += 1

            elapsed = time.time() - context.start_time
            elapsed_ms = elapsed * 1000

            self.logger.info(
                "Document processed successfully: %s/%s",
                doc_type,
                filename,
                extra={
                    "operation_id": operation_id,
                    "result": OperationResult.SUCCESS.value,
                    "elapsed_ms": elapsed_ms,
                    "frontmatter_fields": len(frontmatter),
                    "content_length": len(content),
                },
            )

            return doc_data

        except ContentValidationError:
            # A parse failure is raised on to the caller, as before, but
            # counted: it escaped this method without touching failed_requests
            # (#366).
            self.failed_requests += 1
            raise
        except (
            TimeoutError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
        ) as e:
            self.failed_requests += 1

            self.logger.error(
                "Unexpected error processing document: %s/%s",
                doc_type,
                filename,
                extra={
                    "operation_id": operation_id,
                    "result": OperationResult.FAILURE.value,
                    "error_type": type(e).__name__,
                    # Sanitize error message to avoid information disclosure
                    "error": str(e)[:200] if str(e) else "Unknown error",
                    # Include traceback only in debug mode to avoid information leakage
                    "debug_traceback": traceback.format_exc()
                    if self.settings.debug_mode
                    else None,
                },
            )

            return None

    async def get_health_status(self) -> ServiceHealth:
        """Get comprehensive service health status.

        Returns:
            ServiceHealth with detailed health information

        """
        uptime = time.time() - self.start_time
        total_requests = self.total_requests or 1  # Avoid division by zero
        success_rate = self.successful_requests / total_requests

        # Get cache statistics
        cache_hit_rate = 0.0
        try:
            if self.settings.enable_cache:
                cache = await self._get_cache()
                cache_hit_rate = (await cache.get_stats()).hit_rate
        except (RuntimeError, ValueError, KeyError, AttributeError) as e:
            self.logger.warning("Failed to get cache stats for health check: %s", e)

        # Determine overall service status
        if (
            success_rate >= 0.95 and self.circuit_breaker_trips == 0
        ) or success_rate >= 0.8:
            status = ServiceStatus.HEALTHY
        elif success_rate >= 0.6:
            status = ServiceStatus.DEGRADED
        elif success_rate >= 0.4:
            status = ServiceStatus.FAILING
        else:
            status = ServiceStatus.CRITICAL

        # The content host's breaker: its count of failures in a row, and when
        # the last one was.
        last_error = None
        last_error_time = None
        circuit_breaker_trips = 0

        breaker = await self.content_host_breaker()
        if breaker.last_failure_time:
            circuit_breaker_trips = breaker.failure_count
            last_error = "fetch: circuit breaker failures"
            last_error_time = breaker.last_failure_time

        self.circuit_breaker_trips = circuit_breaker_trips

        return ServiceHealth(
            status=status,
            uptime_seconds=uptime,
            success_rate=success_rate,
            last_error=last_error,
            last_error_time=last_error_time,
            total_requests=self.total_requests,
            successful_requests=self.successful_requests,
            failed_requests=self.failed_requests,
            circuit_breaker_trips=self.circuit_breaker_trips,
            cache_hit_rate=cache_hit_rate,
        )

    async def get_service_diagnostics(self) -> dict[str, Any]:
        """Get comprehensive service diagnostics.

        Returns:
            Detailed diagnostic information for troubleshooting

        """
        health = await self.get_health_status()

        # The content host's breaker, as the health tool reads it
        breaker = await self.content_host_breaker()
        boundaries = {
            "fetch": {
                "status": "open" if breaker.state == "open" else "closed",
                "failure_count": breaker.failure_count,
                "last_failure_time": breaker.last_failure_time,
            },
        }

        # Get parser stats
        parser_stats = get_parser_stats()

        # Get cache stats if available
        cache_stats = {}
        try:
            if self.settings.enable_cache:
                cache = await self._get_cache()
                cache_stats = (await cache.get_stats()).to_dict()
        except (RuntimeError, ValueError, KeyError, AttributeError) as e:
            cache_stats = {"error": str(e)}

        return {
            "service_health": health.to_dict(),
            "error_boundaries": boundaries,
            "parser_statistics": parser_stats,
            "cache_statistics": cache_stats,
            "configuration": {
                "cache_enabled": self.settings.enable_cache,
                "cache_max_size": self.settings.cache_max_size,
                "cache_ttl_seconds": self.settings.cache_ttl_seconds,
                "http_timeout": self.settings.http_timeout,
                "debug_mode": self.settings.debug_mode,
            },
        }

    async def close(self) -> None:
        """Close the shared cache and HTTP client; given ones stay their owner's.

        This is where the cache and the HTTP client are actually closed on the
        server's own path. ``cleanup_resources()`` reaches
        ``close_content_service()`` first, so by the time it gets to its own
        ``close_http_client()`` and ``close_cache()`` calls, both singletons are
        already ``None`` and those two positions do nothing. A component the
        constructor was given is not closed here: whoever built it closes it.

        These records say the close *returned*, not that anything was closed.
        Both closers discard their resource and return normally when the loop
        that created it is dead -- each says so at INFO -- so "Cache closed
        successfully" landed one line under "Discarding cache without closing
        it", in the DEBUG transcript someone turns on precisely when hunting a
        resource that outlived the process.

        Each close keeps its own ``except Exception`` handler, so a failing cache
        cannot strand the HTTP client behind it -- for values of "failing" that
        derive from ``Exception``. A ``KeyboardInterrupt`` or ``CancelledError``
        raised inside the cache close propagates immediately and the HTTP client
        close is not attempted, leaving its pooled sockets open and no record
        that it was skipped. That is deliberate rather than overlooked, and it is
        the same choice ``cleanup_resources()`` makes one layer up for the same
        reason: a shutdown that is being interrupted is not one to keep grinding
        through. What the handlers must not do is end there: this
        method used to log both failures at WARNING and then return normally,
        which made them invisible to everything above. ``close_content_service()``
        saw a clean return, ``cleanup_resources()`` appended nothing to its
        ``errors`` list, and a shutdown in which two resources failed to close
        ended:

            WARNING content_service  Error closing cache: Event loop is closed
            WARNING content_service  Error closing HTTP client: Event loop is closed
            INFO    content_service  Content service shutdown complete
            INFO    content_service  Global content service closed
            INFO    fastmcp_main     Resource cleanup completed successfully

        -- measured, on the production composition. Three consecutive
        clean-close claims after two failures, and no ERROR record anywhere,
        which is the exact condition #100 exists to remove. So the failures are
        reported where they happen and then raised together, once every close
        has been attempted. The success line runs only when there is nothing to
        raise.
        """
        self.logger.info("Shutting down content service")

        failed: list[str] = []
        first_error: Exception | None = None

        if self._cache is None:
            try:
                await close_cache()
                self.logger.debug("Cache close returned")
            except Exception as e:
                failed.append("cache")
                first_error = first_error or e
                self.logger.warning("Error closing cache: %s", e, exc_info=True)

        if self._http_client is None:
            try:
                await close_http_client()
                self.logger.debug("HTTP client close returned")
            except Exception as e:
                failed.append("HTTP client")
                first_error = first_error or e
                self.logger.warning("Error closing HTTP client: %s", e, exc_info=True)

        if failed:
            raise RuntimeError(
                f"content service shutdown failed to close: {', '.join(failed)}"
            ) from first_error

        self.logger.info("Content service shutdown complete")


class ContentServiceManager:
    """Singleton manager for the global content service instance."""

    _instance: Optional["ContentServiceManager"] = None
    _content_service: ContentService | None = None

    def __new__(cls) -> "ContentServiceManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_content_service(self) -> ContentService:
        """Get global content service instance.

        Returns:
            Global ContentService instance

        """
        if self._content_service is None:
            self._content_service = ContentService()
            logger.info("Global content service initialized")

        return self._content_service

    async def close_content_service(self) -> None:
        """Close and cleanup global content service.

        There is deliberately no ``except`` here. One existed to stop a failing
        content service from stranding the resources closed after it -- but
        ``cleanup_resources()`` gives every closer its own handler now, so
        position 1 raising no longer reaches positions 2 and 3. What the
        ``except`` still did was hide the failure: nothing propagated, nothing
        was appended to ``errors``, and the shutdown was signed off as
        successful while two resources had failed to close. Reporting it at
        ERROR from here did not help either -- ``ContentService.close()`` caught
        both of its own awaits, so it could not raise and this handler could not
        run.

        Letting it propagate puts the report where #100 asked for it: the
        individual failures at WARNING where they happen, and the summary that
        names them at ERROR, from the one function that can see every position.

        ``finally`` clears the reference on both paths. The success line runs
        only on the path that succeeded -- in the ``finally`` it announced a
        clean close directly beneath the warning saying the close had failed.

        Removing the ``except`` changes one thing beyond shutdown, and it is not
        reasoned about above: ``ContentServiceManager.__aexit__`` awaits this
        function, so ``async with ContentServiceManager()`` can now raise from
        the exit. If the body raised too, the shutdown error is what reaches the
        caller and the body's exception is demoted to ``__context__``. No call
        site in ``src/`` uses the context-manager form. Left as is deliberately:
        giving ``__aexit__`` swallow-and-log semantics is a decision about that
        context manager, and making it here would restore, one layer out, the
        exact silence this function was changed to remove.
        """
        if self._content_service is not None:
            try:
                await self._content_service.close()
                logger.info("Global content service closed")
            finally:
                self._content_service = None

    async def __aenter__(self) -> ContentService:
        """Async context manager entry."""
        return await self.get_content_service()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit with cleanup."""
        await self.close_content_service()


# Global content service manager instance
_content_service_manager = ContentServiceManager()


async def get_content_service() -> ContentService:
    """Get global content service instance.

    Returns:
        Global ContentService instance

    """
    return await _content_service_manager.get_content_service()


def running_content_service() -> ContentService | None:
    """Return the global content service if one has been built, else None.

    For a caller that reads the service's state and must not be the reason it
    exists: ``get_content_service()`` builds and starts one.
    """
    return _content_service_manager._content_service


async def close_content_service() -> None:
    """Close and cleanup global content service."""
    await _content_service_manager.close_content_service()
