"""FINOS MCP Tools Package

This package contains modular tool implementations for the FINOS AI Governance
Framework MCP Server. Tools are organized by functionality:

- search.py: Search operations for mitigations and risks
- details.py: Detailed document retrieval operations
- listing.py: List operations for all available documents
- system.py: System health and metrics operations

Each module provides both tool definitions and handler implementations with
proper input validation using Pydantic models.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from mcp.types import TextContent, Tool

from .details import DETAILS_TOOLS, handle_details_tools
from .listing import LISTING_TOOLS, handle_listing_tools
from .search import SEARCH_TOOLS, handle_search_tools
from .system import SYSTEM_TOOLS, handle_system_tools

# All available tools consolidated
ALL_TOOLS: list[Tool] = [
    *SEARCH_TOOLS,
    *DETAILS_TOOLS,
    *LISTING_TOOLS,
    *SYSTEM_TOOLS,
]

# Tool name to handler mapping
TOOL_HANDLERS: dict[
    str, Callable[[str, dict[str, Any]], Awaitable[list[TextContent]]]
] = {
    # Search tools
    "search_mitigations": handle_search_tools,
    "search_risks": handle_search_tools,
    # Details tools
    "get_mitigation_details": handle_details_tools,
    "get_risk_details": handle_details_tools,
    # Listing tools
    "list_all_mitigations": handle_listing_tools,
    "list_all_risks": handle_listing_tools,
    # System tools
    "get_cache_stats": handle_system_tools,
    "get_service_health": handle_system_tools,
    "get_service_metrics": handle_system_tools,
    "reset_service_health": handle_system_tools,
}


def get_all_tools() -> list[Tool]:
    """Get all available MCP tools."""
    return ALL_TOOLS


async def handle_tool_call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route tool calls to appropriate handlers.

    Args:
        name: Tool name to execute
        arguments: Tool arguments

    Returns:
        Tool execution result

    Raises:
        ValueError: If tool name is unknown

    """
    if name not in TOOL_HANDLERS:
        raise ValueError(f"Unknown tool: {name}")

    handler = TOOL_HANDLERS[name]
    return await handler(name, arguments)


__all__ = [
    "ALL_TOOLS",
    "TOOL_HANDLERS",
    "get_all_tools",
    "handle_tool_call",
]
