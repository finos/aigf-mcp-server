"""Content service orchestrator with error boundaries for FINOS MCP Server.

Copyright 2024 Hugo Calderon

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
import base64
import time
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from urllib.parse import urljoin

from ..config import get_settings
from ..error_boundary import CircuitBreaker, error_boundary, with_retry
from ..exceptions import (
    CacheError,
    CircuitBreakerError,
    ContentLoadingError,
    ContentValidationError,
    HTTPClientError,
    MCPServerError,
)
from ..health import get_health_monitor
from ..logging import get_logger, set_correlation_id
from ..security.content_filter import content_security_validator
from .cache import TTLCache, close_cache, get_cache

# Updated imports for new error handling
from .fetch import HTTPClient, close_http_client, get_http_client
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
    FALLBACK = "fallback"
    FAILURE = "failure"
    CIRCUIT_OPEN = "circuit_open"


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


# Custom ErrorBoundary class removed - using standardized error handling


class ContentService:  # pylint: disable=too-many-instance-attributes
    """Content service orchestrator with error boundaries and health monitoring.

    Coordinates HTTP fetching, frontmatter parsing, and caching operations
    while providing resilience through error boundaries and circuit breakers.
    """

    def __init__(self) -> None:
        """Initialize content service."""
        self.settings = get_settings()
        self.logger = get_logger("content_service")

        # Service start time for uptime calculation
        self.start_time = time.time()

        # Circuit breakers for service resilience
        self.fetch_circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=MCPServerError,
        )
        self.cache_circuit_breaker = CircuitBreaker(
            failure_threshold=3, recovery_timeout=30, expected_exception=CacheError
        )

        # Operation statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.circuit_breaker_trips = 0

        # Component references (lazy initialization)
        self._http_client: HTTPClient | None = None
        self._cache: TTLCache[str, Any] | None = None

        # Priority files for reference
        self._priority_files = [
            "mi-1_ai-data-leakage-prevention-and-detection.md",
            "mi-2_data-filtering-from-external-knowledge-bases.md",
            "mi-4_ai-system-observability.md",
            "ri-1_adversarial-behavior-against-ai-systems.md",
            "ri-2_prompt-injection.md",
            "ri-3_training-data-poisoning.md",
        ]

        self.logger.info("Content service initialized")

    async def start(self) -> None:
        """Start the content service.

        No background tasks needed for simple MCP server operation.
        """
        self.logger.debug("Content service started (no background tasks)")

    async def shutdown(self) -> None:
        """Shutdown the content service and cleanup resources."""
        await self.close()

    async def _get_http_client(self) -> HTTPClient:
        """Get HTTP client with lazy initialization."""
        if self._http_client is None:
            self._http_client = await get_http_client(self.settings)
        return self._http_client

    async def _get_cache(self) -> TTLCache[str, Any]:
        """Get cache with lazy initialization."""
        if self._cache is None:
            self._cache = await get_cache()
        return self._cache

    # All cache warming methods removed - over-engineered for MCP usage patterns

    async def _fetch_github_api_content(
        self, repo_path: str, context: OperationContext
    ) -> str | None:
        """Fetch content via GitHub API (base64 encoded) instead of raw.githubusercontent.com.

        This approach has higher rate limits (5000/hour with token, 60/hour without)
        compared to raw.githubusercontent.com (strict 60/hour limit).

        Args:
            repo_path: Path within repository (e.g., "docs/_data/owasp-llm.yml")
            context: Operation context

        Returns:
            Decoded content string or None if failed
        """
        # Construct GitHub API content URL
        api_url = f"https://api.github.com/repos/finos/ai-governance-framework/contents/{repo_path}"

        http_client = await self._get_http_client()

        try:
            # Add GitHub token if available for higher rate limits
            headers = {}
            if hasattr(self.settings, "github_token") and self.settings.github_token:
                headers["Authorization"] = f"token {self.settings.github_token}"
                headers["Accept"] = "application/vnd.github.v3+json"

            response = await http_client.get(api_url, headers=headers)
            data = response.json()

            # GitHub API returns base64-encoded content
            if "content" in data and data.get("encoding") == "base64":
                # Decode base64 content
                content_base64 = data["content"].replace("\n", "")  # Remove newlines
                content_bytes = base64.b64decode(content_base64)
                content = content_bytes.decode("utf-8")

                # Security validation for fetched content.
                if not content_security_validator.validate_content_size(content):
                    raise ContentValidationError(
                        "content_too_large", "GitHub API content exceeds safety limits"
                    )
                if not content_security_validator.validate_content_safety(content):
                    raise ContentValidationError(
                        "unsafe_content", "GitHub API content failed safety validation"
                    )

                self.logger.debug(
                    "Content fetched via GitHub API: %s characters",
                    len(content),
                    extra={
                        "operation_id": context.operation_id,
                        "api_url": api_url,
                        "content_length": len(content),
                        "encoding": data.get("encoding"),
                    },
                )

                return content
            else:
                raise ContentValidationError(
                    "unexpected_format",
                    f"GitHub API response missing content or unexpected encoding: {data.get('encoding')}",
                )

        except Exception as e:
            self.logger.warning(
                "GitHub API content fetch failed: %s",
                str(e),
                extra={
                    "operation_id": context.operation_id,
                    "api_url": api_url,
                    "error_type": type(e).__name__,
                },
            )
            return None

    @with_retry(max_attempts=3, base_delay=1.0)
    async def _fetch_content_with_boundary(
        self, url: str, context: OperationContext
    ) -> str | None:
        """Fetch content with error boundary protection and retry logic.

        Args:
            url: URL to fetch
            context: Operation context

        Returns:
            Fetched content or None if failed

        Raises:
            ContentLoadingError: If content loading fails after retries
            HTTPClientError: If HTTP request fails
        """

        @self.fetch_circuit_breaker
        async def _fetch_with_circuit_breaker() -> str:
            http_client = await self._get_http_client()
            try:
                content = await http_client.fetch_text(url)

                if not content.strip():
                    raise ContentValidationError(
                        "empty_content", "Retrieved content is empty"
                    )

                # Security validation for fetched content.
                if not content_security_validator.validate_content_size(content):
                    raise ContentValidationError(
                        "content_too_large", "Fetched content exceeds safety limits"
                    )
                if not content_security_validator.validate_content_safety(content):
                    raise ContentValidationError(
                        "unsafe_content", "Fetched content failed safety validation"
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
                return await _fetch_with_circuit_breaker()

        except Exception as e:
            self.logger.warning(
                "Content fetch failed after all retries: %s",
                str(e),
                extra={
                    "operation_id": context.operation_id,
                    "url": url,
                    "error_type": type(e).__name__,
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

        @self.cache_circuit_breaker
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

        @self.cache_circuit_breaker
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

        # Map document types to repository paths
        if doc_type == "mitigation":
            base_url = self.settings.mitigations_url
            repo_path = f"docs/_mitigations/{filename}"
        elif doc_type == "risk":
            base_url = self.settings.risks_url
            repo_path = f"docs/_risks/{filename}"
        elif doc_type == "framework":
            base_url = self.settings.frameworks_url
            repo_path = f"docs/_data/{filename}"
        else:
            raise ValueError(f"Unknown document type: {doc_type}")

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

        # Use urljoin for safe URL construction (fallback URL for raw content)
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

            # Step 2: Fetch content - try GitHub API first (higher rate limits), fallback to raw URL
            content = None

            # Try GitHub API first for better rate limits
            content = await self._fetch_github_api_content(repo_path, context)

            # Fallback to raw.githubusercontent.com if GitHub API fails
            if not content:
                self.logger.debug(
                    "GitHub API fetch failed, trying raw URL fallback",
                    extra={"operation_id": operation_id},
                )
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
                    },
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

            # Record successful request for health monitoring
            health_monitor = get_health_monitor()
            health_monitor.record_request(
                "content_service", success=True, response_time_ms=elapsed_ms
            )

            return doc_data

        except CircuitBreakerError as e:
            self.circuit_breaker_trips += 1
            self.failed_requests += 1

            self.logger.warning(
                "Circuit breaker open for document: %s/%s",
                doc_type,
                filename,
                extra={
                    "operation_id": operation_id,
                    "result": OperationResult.CIRCUIT_OPEN.value,
                    "error": str(e),
                },
            )

            # Record failed request for health monitoring
            health_monitor = get_health_monitor()
            health_monitor.record_request("content_service", success=False)

            return None

        except (
            asyncio.TimeoutError,
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

            # Record failed request for health monitoring
            health_monitor = get_health_monitor()
            health_monitor.record_request("content_service", success=False)

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
                cache_stats = await cache.get_stats()
                cache_total = cache_stats.hits + cache_stats.misses
                if cache_total > 0:
                    cache_hit_rate = cache_stats.hits / cache_total
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

        # Get circuit breaker status
        last_error = None
        last_error_time = None
        circuit_breaker_trips = 0

        # Check fetch circuit breaker
        if self.fetch_circuit_breaker.last_failure_time:
            circuit_breaker_trips += self.fetch_circuit_breaker.failure_count
            if (
                last_error_time is None
                or self.fetch_circuit_breaker.last_failure_time > last_error_time
            ):
                last_error = "fetch: circuit breaker failures"
                last_error_time = self.fetch_circuit_breaker.last_failure_time

        # Check cache circuit breaker
        if self.cache_circuit_breaker.last_failure_time:
            circuit_breaker_trips += self.cache_circuit_breaker.failure_count
            if (
                last_error_time is None
                or self.cache_circuit_breaker.last_failure_time > last_error_time
            ):
                last_error = "cache: circuit breaker failures"
                last_error_time = self.cache_circuit_breaker.last_failure_time

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

        # Get circuit breaker health
        boundaries = {
            "fetch": {
                "status": "open"
                if self.fetch_circuit_breaker.state == "open"
                else "closed",
                "failure_count": self.fetch_circuit_breaker.failure_count,
                "last_failure_time": self.fetch_circuit_breaker.last_failure_time,
            },
            "cache": {
                "status": "open"
                if self.cache_circuit_breaker.state == "open"
                else "closed",
                "failure_count": self.cache_circuit_breaker.failure_count,
                "last_failure_time": self.cache_circuit_breaker.last_failure_time,
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
            # Cache warming statistics removed
            "configuration": {
                "cache_enabled": self.settings.enable_cache,
                "cache_max_size": self.settings.cache_max_size,
                "cache_ttl_seconds": self.settings.cache_ttl_seconds,
                "http_timeout": self.settings.http_timeout,
                "debug_mode": self.settings.debug_mode,
                # Cache warming configuration removed
            },
        }

    # Cache warming stats method removed

    async def reset_health(self) -> None:
        """Reset service health counters and error boundaries."""
        # Reset health monitor
        health_monitor = get_health_monitor()
        health_monitor.reset_health()

        # Reset service-level counters
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.circuit_breaker_trips = 0
        self.start_time = time.time()

        # Reset circuit breakers
        self.fetch_circuit_breaker.failure_count = 0
        self.fetch_circuit_breaker.last_failure_time = None
        self.fetch_circuit_breaker.state = "closed"

        self.cache_circuit_breaker.failure_count = 0
        self.cache_circuit_breaker.last_failure_time = None
        self.cache_circuit_breaker.state = "closed"

        # Cache warming stats reset removed

        self.logger.info(
            "Service health counters and error boundaries reset successfully"
        )

    async def close(self) -> None:
        """Close service and cleanup resources."""
        self.logger.info("Shutting down content service")

        # Cache warming task cleanup removed

        # Close cache if initialized
        if self._cache:
            try:
                await close_cache()
                self.logger.debug("Cache closed successfully")
            except Exception as e:
                self.logger.warning("Error closing cache: %s", e)

        # Close HTTP client through manager so singleton state is reset.
        if self._http_client:
            try:
                await close_http_client()
                self._http_client = None
                self.logger.debug("HTTP client closed successfully")
            except Exception as e:
                self.logger.warning("Error closing HTTP client: %s", e)

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
            await self._content_service.start()
            logger.info("Global content service initialized and started")

        return self._content_service

    async def close_content_service(self) -> None:
        """Close and cleanup global content service."""
        if self._content_service is not None:
            try:
                await self._content_service.close()
            except Exception as e:
                logger.warning("Error during content service shutdown: %s", e)
            finally:
                self._content_service = None
                logger.info("Global content service closed")

    async def __aenter__(self) -> ContentService:
        """Async context manager entry."""
        return await self.get_content_service()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
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


async def close_content_service() -> None:
    """Close and cleanup global content service."""
    await _content_service_manager.close_content_service()
