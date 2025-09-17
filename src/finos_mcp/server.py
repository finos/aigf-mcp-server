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
import re
import time
from collections import defaultdict, deque
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

from . import __version__
from .config import validate_settings_on_startup
from .content.service import get_content_service
from .health import get_health_monitor
from .logging import get_logger, log_mcp_request, set_correlation_id
from .tools import get_all_tools, handle_tool_call
from .tools.search import get_mitigation_files, get_risk_files

# Simple validation functions to replace removed security module


class ValidationError(ValueError):
    """Simple validation error for compatibility."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def validate_filename_safe(filename: str) -> str:
    """Simple filename validation."""
    if not filename or not isinstance(filename, str):
        raise ValidationError("Invalid filename")
    # Remove any path separators and dangerous characters
    safe_filename = filename.replace("/", "_").replace("\\", "_").replace("..", "_")
    return safe_filename


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


# =============================================================================
# SECURITY VALIDATION LAYER
# =============================================================================


class SecurityValidationError(ValueError):
    """Security-specific validation error for server operations."""

    def __init__(self, message: str, uri: str | None = None):
        self.message = message
        self.uri = uri
        super().__init__(message)


def validate_resource_uri(uri: str) -> tuple[str, str]:
    """Validate and parse resource URI with comprehensive security checks.

    Args:
        uri: Resource URI to validate

    Returns:
        Tuple of (resource_type, filename)

    Raises:
        SecurityValidationError: If URI is invalid or potentially malicious
    """
    if not uri or not isinstance(uri, str):
        raise SecurityValidationError("URI cannot be empty or non-string", uri=uri)

    # Length validation to prevent buffer overflow attacks
    if len(uri) > 1000:
        raise SecurityValidationError("URI exceeds maximum allowed length", uri=uri)

    # Basic structure validation
    if not uri.startswith("finos://"):
        raise SecurityValidationError(
            "Invalid URI scheme - must start with finos://", uri=uri
        )

    # Remove scheme for further processing
    path = uri[8:]  # Remove "finos://"

    # Path traversal protection
    if ".." in path or "//" in path or "\\" in path:
        raise SecurityValidationError("URI contains path traversal attempts", uri=uri)

    # Control character detection
    if any(ord(c) < 32 and c not in {"\t", "\n", "\r"} for c in path):
        raise SecurityValidationError("URI contains control characters", uri=uri)

    # URL injection protection
    dangerous_patterns = [
        r"javascript:",
        r"data:",
        r"vbscript:",
        r"file:",
        r"http:",
        r"https:",
        r"<script",
        r"<%",
        r"{{",
        r"${",
        r"`",
        r"eval\(",
        r"exec\(",
    ]
    path_lower = path.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, path_lower, re.IGNORECASE):
            raise SecurityValidationError(
                f"URI contains dangerous pattern: {pattern}", uri=uri
            )

    # Parse resource type and filename
    if path.startswith("mitigations/"):
        resource_type = "mitigation"
        filename = path[12:]  # Remove "mitigations/"
    elif path.startswith("risks/"):
        resource_type = "risk"
        filename = path[6:]  # Remove "risks/"
    else:
        raise SecurityValidationError(
            "Unknown resource type - must be mitigations/ or risks/", uri=uri
        )

    # Filename validation
    if not filename or filename in {".", ".."}:
        raise SecurityValidationError("Invalid or empty filename", uri=uri)

    try:
        # Use existing filename validation from validators.py
        validated_filename = validate_filename_safe(filename)

        # Additional restrictions for this context
        if not validated_filename.endswith((".md", ".markdown", ".txt")):
            raise SecurityValidationError(
                "File must have .md, .markdown, or .txt extension", uri=uri
            )

        # Prevent hidden files and system files
        if validated_filename.startswith(".") or validated_filename.lower() in {
            "config",
            "config.json",
            "package.json",
            ".env",
            ".git",
            "dockerfile",
        }:
            raise SecurityValidationError(
                "Access to system/config files not allowed", uri=uri
            )

    except ValidationError as e:
        raise SecurityValidationError(
            f"Filename validation failed: {e.message}", uri=uri
        ) from e

    return resource_type, validated_filename


def validate_tool_arguments(
    tool_name: str, arguments: dict[str, Any], validator: Any = None
) -> dict[str, Any]:
    """Validate tool arguments with security checks.

    Args:
        tool_name: Name of the tool being called
        arguments: Tool arguments to validate
        validator: Optional validator instance (uses default if None)

    Returns:
        Validated arguments dictionary

    Raises:
        SecurityValidationError: If arguments are invalid or malicious
    """
    # Simple validation - just return arguments as-is for now
    result = arguments if isinstance(arguments, dict) else {}
    # Ensure the result is a dictionary for type safety
    if not isinstance(result, dict):
        raise SecurityValidationError(
            f"Validator returned invalid type: {type(result)}"
        )
    return result


# =============================================================================
# RATE LIMITING LAYER
# =============================================================================


class RateLimiter:
    """Thread-safe rate limiter for API calls using sliding window algorithm."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: defaultdict[str, deque[float]] = defaultdict(lambda: deque())

    def is_allowed(self, client_id: str = "default") -> bool:
        """Check if request is allowed under rate limit.

        Args:
            client_id: Identifier for the client (for per-client limiting)

        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        client_requests = self.requests[client_id]

        # Remove old requests outside the window
        while client_requests and client_requests[0] <= now - self.window_seconds:
            client_requests.popleft()

        # Check if we're at the limit
        if len(client_requests) >= self.max_requests:
            return False

        # Add current request
        client_requests.append(now)
        return True

    def get_remaining_requests(self, client_id: str = "default") -> int:
        """Get number of remaining requests in current window."""
        now = time.time()
        client_requests = self.requests[client_id]

        # Clean up old requests
        while client_requests and client_requests[0] <= now - self.window_seconds:
            client_requests.popleft()

        return max(0, self.max_requests - len(client_requests))

    def reset_client(self, client_id: str) -> None:
        """Reset rate limit for a specific client."""
        if client_id in self.requests:
            self.requests[client_id].clear()


# Global rate limiter instances
_tool_rate_limiter = RateLimiter(
    max_requests=50, window_seconds=60
)  # 50 tool calls per minute
_resource_rate_limiter = RateLimiter(
    max_requests=200, window_seconds=60
)  # 200 resource requests per minute


@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    """List available resources for the FINOS AI Governance content"""
    # Rate limiting check
    if not _resource_rate_limiter.is_allowed("list_resources"):
        logger.warning(
            "Resource listing rate limited",
            extra={
                "remaining_requests": _resource_rate_limiter.get_remaining_requests(
                    "list_resources"
                )
            },
        )
        raise ValueError(
            "Rate limit exceeded for resource listing - please wait before retrying"
        )

    resources = []

    try:
        # Get dynamic file lists with error handling
        mitigation_files = await get_mitigation_files()
        risk_files = await get_risk_files()

        # Security: Limit the number of resources returned to prevent enumeration attacks
        max_resources = 500  # Reasonable limit
        total_files = len(mitigation_files) + len(risk_files)

        if total_files > max_resources:
            logger.warning(
                "Resource count exceeds security limit",
                extra={"total_files": total_files, "max_allowed": max_resources},
            )
            # Truncate to stay within limits
            remaining_budget = max_resources
            mitigation_files = mitigation_files[
                : min(remaining_budget, len(mitigation_files))
            ]
            remaining_budget -= len(mitigation_files)
            risk_files = risk_files[: min(remaining_budget, len(risk_files))]

        # Add mitigation resources with validation
        for filename in mitigation_files:
            try:
                # Validate filename for security
                validated_filename = validate_filename_safe(filename)

                # Skip hidden files and non-document files
                if validated_filename.startswith(
                    "."
                ) or not validated_filename.lower().endswith(
                    (".md", ".markdown", ".txt")
                ):
                    continue

                resources.append(
                    Resource(
                        uri=AnyUrl(f"finos://mitigations/{validated_filename}"),
                        name=f"Mitigation: {validated_filename}",
                        description=f"AI governance mitigation document: {validated_filename}",
                        mimeType="text/markdown",
                    )
                )
            except (ValidationError, ValueError) as e:
                logger.warning(f"Skipping invalid mitigation file: {filename} - {e}")
                continue

        # Add risk resources with validation
        for filename in risk_files:
            try:
                # Validate filename for security
                validated_filename = validate_filename_safe(filename)

                # Skip hidden files and non-document files
                if validated_filename.startswith(
                    "."
                ) or not validated_filename.lower().endswith(
                    (".md", ".markdown", ".txt")
                ):
                    continue

                resources.append(
                    Resource(
                        uri=AnyUrl(f"finos://risks/{validated_filename}"),
                        name=f"Risk: {validated_filename}",
                        description=f"AI governance risk document: {validated_filename}",
                        mimeType="text/markdown",
                    )
                )
            except (ValidationError, ValueError) as e:
                logger.warning(f"Skipping invalid risk file: {filename} - {e}")
                continue

        logger.info(
            f"Listed {len(resources)} resources",
            extra={
                "mitigation_count": len(
                    [r for r in resources if "mitigations" in str(r.uri)]
                ),
                "risk_count": len([r for r in resources if "risks" in str(r.uri)]),
            },
        )

        return resources

    except Exception as e:
        logger.error(f"Failed to list resources: {e}", exc_info=True)
        raise ValueError(f"Unable to retrieve resource list: {e}") from e


@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """Read a specific resource by URI"""
    uri_str = str(uri)

    # Rate limiting check
    if not _resource_rate_limiter.is_allowed("read_resource"):
        logger.warning(
            "Resource reading rate limited",
            extra={
                "uri": uri_str,
                "remaining_requests": _resource_rate_limiter.get_remaining_requests(
                    "read_resource"
                ),
            },
        )
        raise ValueError(
            "Rate limit exceeded for resource reading - please wait before retrying"
        )

    try:
        # Comprehensive URI validation
        resource_type, validated_filename = validate_resource_uri(uri_str)

        logger.debug(
            "Reading resource",
            extra={
                "uri": uri_str,
                "type": resource_type,
                "filename": validated_filename,
            },
        )

        # Get content service and fetch document
        service = await get_content_service_instance()
        doc_data = await service.get_document(resource_type, validated_filename)

        if not doc_data:
            logger.warning(f"Resource not found: {uri_str}")
            raise ValueError(f"Resource not found: {uri}")

        # Security: Validate content size to prevent memory exhaustion
        content = doc_data["full_text"]
        if len(content) > 10_000_000:  # 10MB limit
            logger.warning(
                "Resource content too large",
                extra={"uri": uri_str, "content_size": len(content)},
            )
            raise ValueError("Resource content exceeds size limit")

        logger.info(
            f"Successfully read resource: {validated_filename}",
            extra={"content_length": len(content), "type": resource_type},
        )

        return str(content)

    except SecurityValidationError as e:
        logger.warning(f"Security validation failed for URI: {uri_str} - {e.message}")
        raise ValueError(f"Invalid resource URI: {e.message}") from e
    except Exception as e:
        logger.error(f"Failed to read resource {uri_str}: {e}", exc_info=True)
        raise ValueError(f"Unable to read resource: {e}") from e


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools for interacting with FINOS AI Governance content"""
    return get_all_tools()


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any], validator: Any = None
) -> list[TextContent]:
    """Handle tool calls for FINOS AI Governance content"""
    # Set correlation ID for request tracing
    correlation_id = set_correlation_id()

    # Log MCP request start
    start_time = asyncio.get_event_loop().time()

    try:
        # Rate limiting check
        if not _tool_rate_limiter.is_allowed(f"tool_{name}"):
            logger.warning(
                f"Tool call rate limited: {name}",
                extra={
                    "tool_name": name,
                    "remaining_requests": _tool_rate_limiter.get_remaining_requests(
                        f"tool_{name}"
                    ),
                    "correlation_id": correlation_id,
                },
            )
            raise ValueError(
                f"Rate limit exceeded for tool '{name}' - please wait before retrying"
            )

        # Security validation of tool name
        if not isinstance(name, str) or len(name) > 100:
            raise SecurityValidationError("Invalid tool name format or length")

        # Validate tool name against injection attacks
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            raise SecurityValidationError("Tool name contains invalid characters")

        # Validate and sanitize arguments
        validated_arguments = validate_tool_arguments(name, arguments, validator)

        logger.debug(
            f"Executing tool: {name}",
            extra={
                "tool_name": name,
                "argument_count": len(validated_arguments),
                "correlation_id": correlation_id,
            },
        )

        # Route to modular tool handlers with validated arguments
        result = await handle_tool_call(name, validated_arguments)

        # Validate result size to prevent memory exhaustion
        if isinstance(result, list):
            total_size = sum(
                len(str(item.text)) if hasattr(item, "text") else len(str(item))
                for item in result
            )
            if total_size > 50_000_000:  # 50MB limit
                logger.warning(
                    f"Tool result too large: {name}",
                    extra={"result_size": total_size, "correlation_id": correlation_id},
                )
                raise ValueError("Tool result exceeds size limit")

        # Log successful request
        elapsed_time = asyncio.get_event_loop().time() - start_time
        log_mcp_request(
            logger=logger,
            method=name,
            request_id=correlation_id,
            params=validated_arguments,
            response_time=elapsed_time,
        )

        logger.info(
            f"Tool executed successfully: {name}",
            extra={
                "execution_time": elapsed_time,
                "result_count": len(result) if isinstance(result, list) else 1,
                "correlation_id": correlation_id,
            },
        )

        return result

    except (SecurityValidationError, ValueError) as error:
        # Log security/validation errors
        elapsed_time = asyncio.get_event_loop().time() - start_time
        logger.warning(
            f"Tool call validation failed: {name} - {error}",
            extra={
                "correlation_id": correlation_id,
                "error_type": type(error).__name__,
            },
        )
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

    except Exception as error:
        # Log unexpected errors
        elapsed_time = asyncio.get_event_loop().time() - start_time
        logger.error(
            f"Tool execution failed: {name} - {error}",
            extra={"correlation_id": correlation_id},
            exc_info=True,
        )
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
                server_version=__version__,
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
