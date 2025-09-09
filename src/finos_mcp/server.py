#!/usr/bin/env python3
"""FINOS AI Governance Framework MCP Server

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

A Model Context Protocol server that provides access to AI governance content from
the FINOS AI Governance Framework repository, specifically exposing risks and mitigations.

This is the refactored modular version with tools split into separate modules.
"""

import asyncio
from typing import Any, Optional

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    ResourcesCapability,
    ServerCapabilities,
    TextContent,
    Tool,
    ToolsCapability,
)
from pydantic import AnyUrl

from .config import validate_settings_on_startup
from .content.service import get_content_service
from .health import get_health_monitor
from .logging import get_logger, log_mcp_request, set_correlation_id
from .tools import get_all_tools, handle_tool_call
from .tools.search import get_mitigation_files, get_risk_files

# Export public symbols
__all__ = ["get_mitigation_files", "get_risk_files", "main", "main_async", "server"]

# Initialize configuration and structured logging
settings = validate_settings_on_startup()
logger = get_logger()

server = Server("finos-ai-governance-mcp")


class ContentServiceInstanceManager:
    """Manager for the content service instance."""

    _instance: Optional["ContentServiceInstanceManager"] = None
    _content_service = None

    def __new__(cls) -> "ContentServiceInstanceManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_content_service_instance(self) -> Any:
        """Get the content service instance, initializing if needed"""
        if self._content_service is None:
            self._content_service = await get_content_service()
        return self._content_service


# Content service instance manager
_content_service_instance_manager = ContentServiceInstanceManager()


async def get_content_service_instance() -> Any:
    """Get the content service instance, initializing if needed"""
    return await _content_service_instance_manager.get_content_service_instance()


@server.list_resources()  # type: ignore[no-untyped-call]
async def handle_list_resources() -> list[Resource]:
    """List available resources for the FINOS AI Governance content"""
    resources = []

    # Get dynamic file lists
    mitigation_files = await get_mitigation_files()
    risk_files = await get_risk_files()

    # Add mitigation resources
    for filename in mitigation_files:
        resources.append(
            Resource(
                uri=AnyUrl(f"finos://mitigations/{filename}"),
                name=f"Mitigation: {filename}",
                description=f"AI governance mitigation document: {filename}",
                mimeType="text/markdown",
            )
        )

    # Add risk resources
    for filename in risk_files:
        resources.append(
            Resource(
                uri=AnyUrl(f"finos://risks/{filename}"),
                name=f"Risk: {filename}",
                description=f"AI governance risk document: {filename}",
                mimeType="text/markdown",
            )
        )

    return resources


@server.read_resource()  # type: ignore[no-untyped-call]
async def handle_read_resource(uri: AnyUrl) -> str:
    """Read a specific resource by URI"""
    uri_str = str(uri)

    # Route to appropriate document type
    if uri_str.startswith("finos://mitigations/"):
        filename = uri_str.replace("finos://mitigations/", "")
        service = await get_content_service_instance()
        doc_data = await service.get_document("mitigation", filename)
    elif uri_str.startswith("finos://risks/"):
        filename = uri_str.replace("finos://risks/", "")
        service = await get_content_service_instance()
        doc_data = await service.get_document("risk", filename)
    else:
        raise ValueError(f"Unknown resource URI: {uri}")

    if not doc_data:
        raise ValueError(f"Resource not found: {uri}")

    return doc_data["full_text"]


@server.list_tools()  # type: ignore[no-untyped-call]
async def handle_list_tools() -> list[Tool]:
    """List available tools for interacting with FINOS AI Governance content"""
    return get_all_tools()


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls for FINOS AI Governance content"""
    # Set correlation ID for request tracing
    correlation_id = set_correlation_id()

    # Log MCP request start
    start_time = asyncio.get_event_loop().time()

    try:
        # Route to modular tool handlers
        result = await handle_tool_call(name, arguments)

        # Log successful request
        elapsed_time = asyncio.get_event_loop().time() - start_time
        log_mcp_request(
            logger=logger,
            method=name,
            request_id=correlation_id,
            params=arguments,
            response_time=elapsed_time,
        )

        return result

    except Exception as error:
        # Log failed request
        elapsed_time = asyncio.get_event_loop().time() - start_time
        log_mcp_request(
            logger=logger,
            method=name,
            request_id=correlation_id,
            params=arguments,
            error=str(error),
            response_time=elapsed_time,
        )

        # Re-raise the error for MCP error handling
        raise


async def log_health_status() -> None:
    """Log current health status for monitoring."""
    health_monitor = get_health_monitor()
    health_summary = health_monitor.get_health_summary()

    # Log condensed health status
    overall = health_monitor.get_overall_health()
    logger.info(
        "Health Status: %s - %s",
        overall.status.value,
        overall.message,
        extra={
            "health_status": overall.status.value,
            "uptime_seconds": health_summary["uptime_seconds"],
            "total_services": health_summary["summary"]["total_services"],
            "healthy_services": health_summary["summary"]["healthy_services"],
            "degraded_services": health_summary["summary"]["degraded_services"],
            "unhealthy_services": health_summary["summary"]["unhealthy_services"],
        },
    )

    # Debug-level detailed status
    logger.debug("Detailed health summary", extra={"health_details": health_summary})


async def main_async() -> None:
    """Async main entry point for the server"""
    # Log initial health status
    await log_health_status()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="finos-ai-governance-mcp",
                server_version="1.0.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(listChanged=False),
                    resources=ResourcesCapability(subscribe=False, listChanged=False),
                ),
            ),
        )


def main() -> None:
    """Synchronous entry point for console script"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
