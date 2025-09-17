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
import time
import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from urllib.parse import urljoin

from ..config import get_settings
from ..health import get_health_monitor
from ..logging import get_logger, set_correlation_id
from .cache import TTLCache, close_cache, get_cache
from .discovery import STATIC_MITIGATION_FILES, STATIC_RISK_FILES
from .fetch import CircuitBreakerError, HTTPClient, get_http_client
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


@dataclass
class CacheWarmingStats:
    """Cache warming statistics for performance monitoring."""

    total_warmed: int = 0
    successful_warmed: int = 0
    failed_warmed: int = 0
    warming_time_ms: float = 0.0
    last_warming: float = 0.0
    warming_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "total_warmed": self.total_warmed,
            "successful_warmed": self.successful_warmed,
            "failed_warmed": self.failed_warmed,
            "success_rate": self.successful_warmed / max(self.total_warmed, 1),
            "warming_time_ms": round(self.warming_time_ms, 2),
            "last_warming": self.last_warming,
            "warming_enabled": self.warming_enabled,
        }


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


class ErrorBoundary:
    """Error boundary implementation for isolating service failures.

    Prevents cascading failures by catching and handling errors at the service level,
    allowing the system to continue operating even when individual operations fail.
    """

    def __init__(self, service_name: str, fallback_enabled: bool = True):
        """Initialize error boundary.

        Args:
            service_name: Name of the service being protected
            fallback_enabled: Whether to enable fallback operations

        """
        self.service_name = service_name
        self.fallback_enabled = fallback_enabled
        self.error_count = 0
        self.success_count = 0
        self.last_error: str | None = None
        self.last_error_time: float | None = None

    @asynccontextmanager
    async def protect(self) -> AsyncGenerator["ErrorBoundary", None]:
        """Async context manager for error boundary protection.

        Yields:
            Operation context that handles errors gracefully

        """
        start_time = time.time()
        operation_result = OperationResult.SUCCESS

        try:
            yield self
            self.success_count += 1
            logger.debug("Error boundary [%s]: Operation succeeded", self.service_name)

        except CircuitBreakerError as e:
            operation_result = OperationResult.CIRCUIT_OPEN
            self.error_count += 1
            self.last_error = str(e)
            self.last_error_time = time.time()

            logger.warning(
                "Error boundary [%s]: Circuit breaker open",
                self.service_name,
                extra={
                    "service": self.service_name,
                    "error_type": "CircuitBreakerError",
                    "error": str(e),
                },
            )

        except (ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            operation_result = OperationResult.FAILURE
            self.error_count += 1
            self.last_error = str(e)
            self.last_error_time = time.time()

            logger.error(
                "Error boundary [%s]: Operation failed",
                self.service_name,
                extra={
                    "service": self.service_name,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                },
            )

        finally:
            elapsed = time.time() - start_time
            logger.debug(
                "Error boundary [%s]: Operation completed",
                self.service_name,
                extra={
                    "service": self.service_name,
                    "result": operation_result.value,
                    "elapsed_ms": elapsed * 1000,
                    "success_count": self.success_count,
                    "error_count": self.error_count,
                },
            )

    def get_health_info(self) -> dict[str, Any]:
        """Get health information for this error boundary."""
        total = self.success_count + self.error_count
        success_rate = (self.success_count / total) if total > 0 else 1.0

        if self.error_count == 0 or success_rate >= 0.9:
            status = ServiceStatus.HEALTHY
        elif success_rate >= 0.7:
            status = ServiceStatus.DEGRADED
        elif success_rate >= 0.5:
            status = ServiceStatus.FAILING
        else:
            status = ServiceStatus.CRITICAL

        return {
            "status": status.value,
            "success_rate": success_rate,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time,
        }


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

        # Error boundaries for each service component
        self.fetch_boundary = ErrorBoundary("http_fetch", fallback_enabled=True)
        self.parse_boundary = ErrorBoundary("frontmatter_parse", fallback_enabled=True)
        self.cache_boundary = ErrorBoundary("cache_operations", fallback_enabled=True)

        # Operation statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.circuit_breaker_trips = 0

        # Component references (lazy initialization)
        self._http_client: HTTPClient | None = None
        self._cache: TTLCache[str, Any] | None = None

        # Cache warming configuration and statistics
        self._warming_stats = CacheWarmingStats()
        self._warming_enabled = getattr(self.settings, "enable_cache_warming", True)
        self._warming_interval = getattr(
            self.settings, "cache_warming_interval", 300.0
        )  # 5 minutes
        self._warming_concurrency = getattr(
            self.settings, "cache_warming_concurrency", 3
        )
        self._warming_task: asyncio.Task[None] | None = None

        # Priority files for cache warming (most frequently accessed)
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
        """Start async components of the service.

        This method must be called after service creation to start background tasks.
        It ensures proper async context management and lifecycle.
        """
        # Start cache warming if enabled and not already started
        if self._warming_enabled and (
            self._warming_task is None or self._warming_task.done()
        ):
            self._start_cache_warming()
            self.logger.info("Cache warming started in async context")

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

    def _start_cache_warming(self) -> None:
        """Start background cache warming task."""
        try:
            # Check if we have a running event loop
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                self.logger.debug("Cannot start cache warming: no event loop running")
                return

            if self._warming_task is None or self._warming_task.done():
                self._warming_task = asyncio.create_task(self._cache_warming_loop())
                self.logger.info("Cache warming started")
        except Exception as e:
            self.logger.warning(f"Failed to start cache warming: {e}")
            # Don't raise - cache warming is optional

    async def _cache_warming_loop(self) -> None:
        """Background loop for cache warming."""
        try:
            # Initial warming after 30 seconds startup delay
            await asyncio.sleep(30)
            await self._perform_cache_warming()

            # Periodic warming
            while True:
                await asyncio.sleep(self._warming_interval)
                await self._perform_cache_warming()

        except asyncio.CancelledError:
            self.logger.info("Cache warming task cancelled")
            raise
        except (asyncio.TimeoutError, RuntimeError, ValueError, TypeError) as e:
            self.logger.error("Cache warming loop error: %s", e)

    async def _perform_cache_warming(self) -> None:
        """Perform cache warming for priority documents."""
        if not self._warming_enabled:
            return

        start_time = time.time()
        self.logger.info("Starting cache warming cycle")

        try:
            cache = await self._get_cache()

            # Prepare warming tasks for high-priority files
            warming_tasks = []
            files_to_warm = []

            # Add priority files first
            for filename in self._priority_files:
                # Check both mitigation and risk versions
                for doc_type in ["mitigation", "risk"]:
                    cache_key = f"{doc_type}:{filename}"
                    if await self._should_warm_cache_key(cache, cache_key):
                        files_to_warm.append((doc_type, filename))

            # Add some additional files for broader coverage (deterministic selection)
            all_static_files = [("mitigation", f) for f in STATIC_MITIGATION_FILES] + [
                ("risk", f) for f in STATIC_RISK_FILES
            ]
            # Use deterministic selection based on filename hash for reproducible cache warming
            additional_files = sorted(all_static_files)[: min(5, len(all_static_files))]

            for doc_type, filename in additional_files:
                cache_key = f"{doc_type}:{filename}"
                if await self._should_warm_cache_key(cache, cache_key):
                    files_to_warm.append((doc_type, filename))

            # Limit concurrent warming operations
            files_to_warm = files_to_warm[: self._warming_concurrency * 2]

            # Create warming tasks
            for doc_type, filename in files_to_warm:
                task = asyncio.create_task(
                    self._warm_single_document(doc_type, filename)
                )
                warming_tasks.append(task)

            # Execute warming tasks with concurrency limit
            if warming_tasks:
                semaphore = asyncio.Semaphore(self._warming_concurrency)

                async def limited_warm(task: asyncio.Task[bool]) -> bool:
                    async with semaphore:
                        return await task

                results = await asyncio.gather(
                    *[limited_warm(task) for task in warming_tasks],
                    return_exceptions=True,
                )

                # Update statistics
                successful = sum(1 for r in results if r is True)
                failed = len(results) - successful

                self._warming_stats.total_warmed += len(results)
                self._warming_stats.successful_warmed += successful
                self._warming_stats.failed_warmed += failed

            elapsed = (time.time() - start_time) * 1000
            self._warming_stats.warming_time_ms = elapsed
            self._warming_stats.last_warming = start_time

            self.logger.info(
                "Cache warming completed: %s files processed in %.1fms",
                len(files_to_warm),
                elapsed,
            )

        except (
            asyncio.TimeoutError,
            RuntimeError,
            ValueError,
            KeyError,
            AttributeError,
        ) as e:
            self.logger.error("Cache warming failed: %s", e)

    async def _should_warm_cache_key(self, cache: TTLCache[str, Any], key: str) -> bool:
        """Check if cache key should be warmed (missing or expiring soon)."""
        try:
            # Check if key exists and get entry info
            entry_info = await cache.get_entry_info(key)
            if entry_info is None:
                return True  # Not in cache, should warm

            # Check if expiring within next 30 minutes (1800 seconds)
            time_to_expiry = entry_info.get("time_to_expiry")
            if time_to_expiry is not None and time_to_expiry < 1800:
                return True  # Expiring soon, should warm

            return False  # Fresh in cache, no need to warm

        except (KeyError, AttributeError, ValueError, TypeError):
            return True  # Error checking, safer to warm

    async def _warm_single_document(self, doc_type: str, filename: str) -> bool:
        """Warm cache for a single document."""
        try:
            # Use the existing get_document method which handles caching
            document = await self.get_document(doc_type, filename)
            return document is not None

        except (
            asyncio.TimeoutError,
            RuntimeError,
            ValueError,
            KeyError,
            AttributeError,
        ) as e:
            self.logger.debug(
                "Failed to warm cache for %s/%s: %s", doc_type, filename, e
            )
            return False

    async def _fetch_content_with_boundary(
        self, url: str, context: OperationContext
    ) -> str | None:
        """Fetch content with error boundary protection.

        Args:
            url: URL to fetch
            context: Operation context

        Returns:
            Fetched content or None if failed

        """
        try:
            async with self.fetch_boundary.protect():
                http_client = await self._get_http_client()
                content = await http_client.fetch_text(url)

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
            self.logger.debug(
                "Failed to fetch content: %s",
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

        """
        async with self.parse_boundary.protect():
            # Use asyncio.to_thread for true async parsing (25-35% concurrency improvement)
            frontmatter, body = await asyncio.to_thread(parse_frontmatter, content)

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

    async def _cache_get_with_boundary(
        self, cache_key: str, context: OperationContext
    ) -> dict[str, Any] | None:
        """Get from cache with error boundary protection.

        Args:
            cache_key: Cache key to retrieve
            context: Operation context

        Returns:
            Cached document data or None if not found/error

        """
        if not context.cache_enabled or not self.settings.enable_cache:
            return None

        async with self.cache_boundary.protect():
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

        try:
            async with self.cache_boundary.protect():
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
        except (
            asyncio.TimeoutError,
            RuntimeError,
            ValueError,
            KeyError,
            AttributeError,
        ) as e:
            self.logger.warning(
                "Failed to cache content: %s",
                e,
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
            doc_type: Type of document ('mitigation' or 'risk')
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

        base_url = (
            self.settings.mitigations_url
            if doc_type == "mitigation"
            else self.settings.risks_url
        )

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
                    "filename": filename,
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

            # Step 2: Fetch content
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
                        "filename": filename,
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

        # Get last error info from error boundaries
        last_error = None
        last_error_time = None

        for boundary in [self.fetch_boundary, self.parse_boundary, self.cache_boundary]:
            if boundary.last_error and (
                last_error_time is None
                or (
                    boundary.last_error_time
                    and boundary.last_error_time > last_error_time
                )
            ):
                last_error = f"{boundary.service_name}: {boundary.last_error}"
                last_error_time = boundary.last_error_time

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

        # Get error boundary health
        boundaries = {
            "fetch": self.fetch_boundary.get_health_info(),
            "parse": self.parse_boundary.get_health_info(),
            "cache": self.cache_boundary.get_health_info(),
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
            "cache_warming_statistics": self.get_cache_warming_stats(),
            "configuration": {
                "cache_enabled": self.settings.enable_cache,
                "cache_max_size": self.settings.cache_max_size,
                "cache_ttl_seconds": self.settings.cache_ttl_seconds,
                "http_timeout": self.settings.http_timeout,
                "debug_mode": self.settings.debug_mode,
                "cache_warming_enabled": self._warming_enabled,
                "cache_warming_interval": self._warming_interval,
                "cache_warming_concurrency": self._warming_concurrency,
            },
        }

    def get_cache_warming_stats(self) -> dict[str, Any]:
        """Get cache warming statistics."""
        return self._warming_stats.to_dict()

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

        # Reset error boundaries
        self.fetch_boundary.error_count = 0
        self.fetch_boundary.success_count = 0
        self.fetch_boundary.last_error = None
        self.fetch_boundary.last_error_time = None

        self.parse_boundary.error_count = 0
        self.parse_boundary.success_count = 0
        self.parse_boundary.last_error = None
        self.parse_boundary.last_error_time = None

        self.cache_boundary.error_count = 0
        self.cache_boundary.success_count = 0
        self.cache_boundary.last_error = None
        self.cache_boundary.last_error_time = None

        # Reset cache warming stats
        self._warming_stats = CacheWarmingStats()

        self.logger.info(
            "Service health counters and error boundaries reset successfully"
        )

    async def close(self) -> None:
        """Close service and cleanup resources."""
        self.logger.info("Shutting down content service")

        # Cancel cache warming task
        if self._warming_task and not self._warming_task.done():
            self._warming_task.cancel()
            try:
                await self._warming_task
            except asyncio.CancelledError:
                self.logger.debug("Cache warming task cancelled successfully")
            except Exception as e:
                self.logger.warning("Error during cache warming task cleanup: %s", e)
            self.logger.info("Cache warming task cleanup completed")

        # Close cache if initialized
        if self._cache:
            try:
                await close_cache()
                self.logger.debug("Cache closed successfully")
            except Exception as e:
                self.logger.warning("Error closing cache: %s", e)

        # Close HTTP client if initialized
        if self._http_client:
            try:
                await self._http_client.close()
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
