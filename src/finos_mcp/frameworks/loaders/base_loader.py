"""Base framework loader following existing ContentService patterns.

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

This module provides the base loader class that follows the existing ContentService
patterns for HTTP fetching, caching, and error handling.
"""

import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ...config import get_settings
from ...content.cache import TTLCache, get_cache
from ...content.fetch import CircuitBreakerError, HTTPClient, get_http_client
from ...logging import get_logger, set_correlation_id
from ..models import GovernanceFramework


class FrameworkLoaderError(Exception):
    """Base exception for framework loader errors."""


@dataclass
class LoaderContext:
    """Context for framework loading operations."""

    operation_id: str
    framework_name: str
    start_time: float
    correlation_id: str | None = None
    cache_enabled: bool = True
    ttl_override: float | None = None


class BaseFrameworkLoader(ABC):
    """Base class for framework loaders following ContentService patterns.

    This class follows the same patterns as ContentService for:
    - HTTP client usage with circuit breakers
    - TTL cache integration
    - Error boundary protection
    - Async/await patterns
    - Security validation
    """

    def __init__(self, framework_name: str) -> None:
        """Initialize base framework loader.

        Args:
            framework_name: Name of the framework (e.g., "iso42001", "ffiec")
        """
        self.framework_name = framework_name
        self.settings = get_settings()
        self.logger = get_logger(f"framework_loader_{framework_name}")

        # Lazy initialization following ContentService pattern
        self._http_client: HTTPClient | None = None
        self._cache: TTLCache[str, Any] | None = None

        # Framework-specific cache TTL (24 hours for frameworks, longer than content)
        self.cache_ttl = getattr(self.settings, f"{framework_name}_cache_ttl", 86400.0)

        self.logger.info(f"Framework loader initialized: {framework_name}")

    async def _get_http_client(self) -> HTTPClient:
        """Get HTTP client with lazy initialization following ContentService pattern."""
        if self._http_client is None:
            self._http_client = await get_http_client(self.settings)
        return self._http_client

    async def _get_cache(self) -> TTLCache[str, Any]:
        """Get cache with lazy initialization following ContentService pattern."""
        if self._cache is None:
            self._cache = await get_cache()
        return self._cache

    async def _fetch_content_with_circuit_breaker(
        self, url: str, context: LoaderContext
    ) -> str | None:
        """Fetch content with circuit breaker protection following ContentService pattern.

        Args:
            url: URL to fetch
            context: Loading context

        Returns:
            Fetched content or None if failed
        """
        try:
            http_client = await self._get_http_client()
            content = await http_client.fetch_text(url)

            self.logger.debug(
                "Framework content fetched successfully: %s characters",
                len(content),
                extra={
                    "operation_id": context.operation_id,
                    "framework": self.framework_name,
                    "url": url,
                    "content_length": len(content),
                },
            )

            return content

        except CircuitBreakerError as e:
            self.logger.warning(
                "Circuit breaker open for framework %s",
                self.framework_name,
                extra={
                    "operation_id": context.operation_id,
                    "framework": self.framework_name,
                    "error": str(e),
                },
            )
            return None

        except Exception as e:
            self.logger.debug(
                "Failed to fetch framework content: %s",
                str(e),
                extra={
                    "operation_id": context.operation_id,
                    "framework": self.framework_name,
                    "url": url,
                    "error_type": type(e).__name__,
                },
            )
            return None

    async def _cache_get_with_boundary(
        self, cache_key: str, context: LoaderContext
    ) -> dict[str, Any] | None:
        """Get from cache with error boundary protection following ContentService pattern.

        Args:
            cache_key: Cache key to retrieve
            context: Loading context

        Returns:
            Cached framework data or None if not found/error
        """
        if not context.cache_enabled or not self.settings.enable_cache:
            return None

        try:
            cache = await self._get_cache()
            cached_data = await cache.get(cache_key)

            if cached_data:
                self.logger.debug(
                    "Cache hit for framework: %s",
                    self.framework_name,
                    extra={
                        "operation_id": context.operation_id,
                        "framework": self.framework_name,
                        "cache_key": cache_key,
                    },
                )
            else:
                self.logger.debug(
                    "Cache miss for framework: %s",
                    self.framework_name,
                    extra={
                        "operation_id": context.operation_id,
                        "framework": self.framework_name,
                        "cache_key": cache_key,
                    },
                )

            return cached_data

        except Exception as e:
            self.logger.warning(
                "Cache error for framework %s: %s",
                self.framework_name,
                e,
                extra={
                    "operation_id": context.operation_id,
                    "framework": self.framework_name,
                    "cache_key": cache_key,
                    "error": str(e),
                },
            )
            return None

    async def _cache_set_with_boundary(
        self, cache_key: str, framework_data: dict[str, Any], context: LoaderContext
    ) -> bool:
        """Set cache with error boundary protection following ContentService pattern.

        Args:
            cache_key: Cache key
            framework_data: Framework data to cache
            context: Loading context

        Returns:
            True if cached successfully, False otherwise
        """
        if not context.cache_enabled or not self.settings.enable_cache:
            return False

        try:
            cache = await self._get_cache()
            ttl = context.ttl_override or self.cache_ttl
            await cache.set(cache_key, framework_data, ttl=ttl)

            self.logger.debug(
                "Framework data cached successfully: %s",
                self.framework_name,
                extra={
                    "operation_id": context.operation_id,
                    "framework": self.framework_name,
                    "cache_key": cache_key,
                    "ttl": ttl,
                },
            )

            return True

        except Exception as e:
            self.logger.warning(
                "Failed to cache framework data for %s: %s",
                self.framework_name,
                e,
                extra={
                    "operation_id": context.operation_id,
                    "framework": self.framework_name,
                    "cache_key": cache_key,
                    "error": str(e),
                },
            )
            return False

    async def load_framework(
        self,
        ttl_override: float | None = None,
        correlation_id: str | None = None,
    ) -> GovernanceFramework | None:
        """Load framework data with comprehensive error handling and caching.

        Args:
            ttl_override: Optional TTL override for caching
            correlation_id: Optional correlation ID for tracing

        Returns:
            Loaded framework data or None if failed
        """
        # Set up operation context following ContentService pattern
        operation_id = f"{self.framework_name}:load:{int(time.time())}"
        if correlation_id is None:
            correlation_id = set_correlation_id()

        context = LoaderContext(
            operation_id=operation_id,
            framework_name=self.framework_name,
            start_time=time.time(),
            correlation_id=correlation_id,
            ttl_override=ttl_override,
        )

        self.logger.info(
            "Framework loading started: %s",
            self.framework_name,
            extra={
                "operation_id": operation_id,
                "framework": self.framework_name,
                "correlation_id": correlation_id,
            },
        )

        try:
            # Step 1: Check cache first (following ContentService pattern)
            cache_key = f"framework:{self.framework_name}"
            cached_data = await self._cache_get_with_boundary(cache_key, context)

            if cached_data:
                self.logger.info(
                    "Framework served from cache: %s",
                    self.framework_name,
                    extra={
                        "operation_id": operation_id,
                        "framework": self.framework_name,
                        "result": "cache_hit",
                        "elapsed_ms": (time.time() - context.start_time) * 1000,
                    },
                )

                # Reconstruct GovernanceFramework from cached data
                return await self._deserialize_framework(cached_data, context)

            # Step 2: Load from source
            framework_data = await self._load_from_source(context)
            if not framework_data:
                self.logger.error(
                    "Failed to load framework from source: %s",
                    self.framework_name,
                    extra={
                        "operation_id": operation_id,
                        "framework": self.framework_name,
                        "result": "failure",
                    },
                )
                return None

            # Step 3: Cache the result
            await self._cache_set_with_boundary(cache_key, framework_data, context)

            elapsed = time.time() - context.start_time
            elapsed_ms = elapsed * 1000

            self.logger.info(
                "Framework loaded successfully: %s",
                self.framework_name,
                extra={
                    "operation_id": operation_id,
                    "framework": self.framework_name,
                    "result": "success",
                    "elapsed_ms": elapsed_ms,
                },
            )

            # Step 4: Deserialize to GovernanceFramework
            return await self._deserialize_framework(framework_data, context)

        except Exception as e:
            self.logger.error(
                "Unexpected error loading framework: %s",
                self.framework_name,
                extra={
                    "operation_id": operation_id,
                    "framework": self.framework_name,
                    "result": "failure",
                    "error_type": type(e).__name__,
                    "error": str(e)[:200] if str(e) else "Unknown error",
                    "debug_traceback": traceback.format_exc()
                    if self.settings.debug_mode
                    else None,
                },
            )
            return None

    @abstractmethod
    async def _load_from_source(self, context: LoaderContext) -> dict[str, Any] | None:
        """Load framework data from external source.

        This method must be implemented by subclasses to define how to fetch
        and parse framework data from their specific sources.

        Args:
            context: Loading context

        Returns:
            Raw framework data dictionary or None if failed
        """
        ...

    @abstractmethod
    async def _deserialize_framework(
        self, data: dict[str, Any], context: LoaderContext
    ) -> GovernanceFramework | None:
        """Deserialize raw data into GovernanceFramework model.

        This method must be implemented by subclasses to convert their
        raw data format into the standard GovernanceFramework model.

        Args:
            data: Raw framework data
            context: Loading context

        Returns:
            GovernanceFramework instance or None if failed
        """
        ...

    @abstractmethod
    def get_source_urls(self) -> list[str]:
        """Get list of source URLs for this framework.

        Returns:
            List of URLs where framework data can be found
        """
        ...

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on framework loader.

        Returns:
            Health check results
        """
        start_time = time.time()
        health_info = {
            "framework": self.framework_name,
            "healthy": True,
            "checks": {},
            "total_time_ms": 0.0,
        }

        try:
            # Check source URLs
            urls = self.get_source_urls()
            http_client = await self._get_http_client()

            for url in urls[:3]:  # Check first 3 URLs to avoid timeout
                try:
                    check_result = await http_client.health_check(url)
                    health_info["checks"][url] = check_result
                    if not check_result.get("healthy", False):
                        health_info["healthy"] = False
                except Exception as e:
                    health_info["checks"][url] = {
                        "healthy": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                    health_info["healthy"] = False

            # Check cache connectivity
            try:
                cache = await self._get_cache()
                cache_stats = await cache.get_stats()
                health_info["cache"] = {
                    "healthy": True,
                    "stats": cache_stats.to_dict(),
                }
            except Exception as e:
                health_info["cache"] = {
                    "healthy": False,
                    "error": str(e),
                }

        except Exception as e:
            health_info["healthy"] = False
            health_info["error"] = str(e)
            health_info["error_type"] = type(e).__name__

        finally:
            health_info["total_time_ms"] = (time.time() - start_time) * 1000

        return health_info

    async def close(self) -> None:
        """Close loader and cleanup resources following ContentService pattern."""
        self.logger.info(f"Shutting down framework loader: {self.framework_name}")

        # HTTP client is managed by global manager, no need to close here
        # Cache is also managed globally

        self.logger.info(f"Framework loader shutdown complete: {self.framework_name}")
