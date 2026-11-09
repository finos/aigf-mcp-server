#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Tools that report on the server itself rather than on framework content.

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
"""

import time

from . import __version__
from .app import _SERVER_START_TIME, mcp
from .content.cache import get_cache
from .logging import get_logger
from .models import CacheStats, ServiceHealth
from .service import get_service

logger = get_logger("health_tools")


@mcp.tool()
async def get_service_health() -> ServiceHealth:
    """Get real service health status by querying each subsystem.

    Returns:
        Structured health information with actual subsystem counts.
    """

    # Query actual subsystem diagnostics instead of hardcoding values.
    total_services = 4  # fetch, cache, parser, config
    healthy_services = 0
    overall_status = "healthy"

    try:
        service = await get_service()
        diagnostics = await service.get_service_diagnostics()

        # Count healthy error boundaries (circuit breakers that are closed)
        boundaries = diagnostics.get("error_boundaries", {})
        healthy_boundaries = sum(
            1 for b in boundaries.values() if b.get("status") == "closed"
        )
        # The one breaker covers fetch; the cache is healthy when its statistics
        # can be read (it has no breaker since #302: nothing in it can fail)
        healthy_services += healthy_boundaries
        # A cache turned off is not a failed one: the service then reports no
        # statistics at all, which read as a broken cache until #405.
        cache_statistics = diagnostics.get("cache_statistics", {})
        cache_enabled = diagnostics.get("configuration", {}).get("cache_enabled", True)
        if not cache_enabled or (cache_statistics and "error" not in cache_statistics):
            healthy_services += 1

        # Parser subsystem is healthy if parser stats are accessible
        if "parser_statistics" in diagnostics:
            healthy_services += 1

        # Config subsystem is always healthy if we reached this point
        healthy_services += 1

        if healthy_services < total_services:
            overall_status = "degraded"

    except Exception as e:
        logger.warning("Failed to collect subsystem diagnostics: %s", e)
        # Cannot determine real status; report degraded rather than lying
        overall_status = "degraded"
        healthy_services = 0

    return ServiceHealth(
        status=overall_status,
        uptime_seconds=time.monotonic() - _SERVER_START_TIME,
        version=__version__,
        healthy_services=healthy_services,
        total_services=total_services,
    )


@mcp.tool()
async def get_cache_stats() -> CacheStats:
    """Get cache statistics.

    Returns:
        Structured cache performance information.
    """
    try:
        cache = await get_cache()
        stats = await cache.get_stats()
        total_requests = stats.hits + stats.misses
        hit_rate = (stats.hits / total_requests) if total_requests > 0 else 0.0
        return CacheStats(
            total_requests=total_requests,
            cache_hits=stats.hits,
            cache_misses=stats.misses,
            hit_rate=hit_rate,
        )
    except Exception as e:
        logger.warning("Failed to get real cache stats, returning safe defaults: %s", e)
        return CacheStats(total_requests=0, cache_hits=0, cache_misses=0, hit_rate=0.0)
