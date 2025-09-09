"""System tools for FINOS MCP Server.

Provides health monitoring, metrics, and administrative operations for the server.
"""

import json
from typing import Any

from mcp.types import TextContent, Tool
from pydantic import BaseModel

from ..content.service import get_content_service
from ..logging import get_logger

logger = get_logger("system_tools")


class GetCacheStatsRequest(BaseModel):
    """Request model for getting cache statistics."""


class GetServiceHealthRequest(BaseModel):
    """Request model for getting service health."""


class GetServiceMetricsRequest(BaseModel):
    """Request model for getting service metrics."""


class ResetServiceHealthRequest(BaseModel):
    """Request model for resetting service health."""


# Tool definitions
SYSTEM_TOOLS: list[Tool] = [
    Tool(
        name="get_cache_stats",
        description="Get cache performance statistics and metrics",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_service_health",
        description="Get comprehensive service health status and diagnostics",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_service_metrics",
        description="Get detailed service performance metrics and statistics",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="reset_service_health",
        description="Reset service health counters and error boundaries",
        inputSchema={"type": "object", "properties": {}},
    ),
]


async def handle_system_tools(
    name: str, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle system tool calls.

    Args:
        name: Tool name
        arguments: Tool arguments (usually empty for system operations)

    Returns:
        System information as TextContent

    """
    logger.debug(
        "Handling system tool: %s",
        name,
        extra={"tool_name": name, "arguments": arguments},
    )

    service = await get_content_service()

    if name == "get_cache_stats":
        # Validate input using Pydantic (no parameters expected)
        GetCacheStatsRequest(**arguments)  # Validate input

        # Get cache statistics from service
        cache_stats = await service.get_service_diagnostics()
        cache_info = cache_stats.get("cache_statistics", {})

        logger.info(
            "Retrieved cache statistics",
            extra={
                "cache_hits": cache_info.get("hits", 0),
                "cache_misses": cache_info.get("misses", 0),
            },
        )

        return [TextContent(type="text", text=json.dumps(cache_info, indent=2))]

    if name == "get_service_health":
        # Validate input using Pydantic (no parameters expected)
        GetServiceHealthRequest(**arguments)  # Validate input

        # Get comprehensive health status
        health_status = await service.get_health_status()
        health_data = health_status.to_dict()

        logger.info(
            "Retrieved service health status",
            extra={
                "service_status": health_data.get("status", "unknown"),
                "success_rate": health_data.get("success_rate", 0),
                "total_requests": health_data.get("total_requests", 0),
            },
        )

        return [TextContent(type="text", text=json.dumps(health_data, indent=2))]

    if name == "get_service_metrics":
        # Validate input using Pydantic (no parameters expected)
        GetServiceMetricsRequest(**arguments)  # Validate input

        # Get detailed service diagnostics
        diagnostics = await service.get_service_diagnostics()

        logger.info(
            "Retrieved service metrics",
            extra={
                "total_requests": diagnostics.get("service_health", {}).get(
                    "total_requests", 0
                ),
                "cache_hit_rate": diagnostics.get("service_health", {}).get(
                    "cache_hit_rate", 0
                ),
            },
        )

        return [TextContent(type="text", text=json.dumps(diagnostics, indent=2))]

    if name == "reset_service_health":
        # Validate input using Pydantic (no parameters expected)
        ResetServiceHealthRequest(**arguments)  # Validate input

        # Reset health counters and error boundaries
        await service.reset_health()

        result = {
            "status": "success",
            "message": "Service health counters and error boundaries have been reset",
            "timestamp": service.start_time,
        }

        logger.info(
            "Service health reset completed successfully",
            extra={
                "operation": "reset_service_health",
                "timestamp": service.start_time,
            },
        )

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        raise ValueError(f"Unknown system tool: {name}")
