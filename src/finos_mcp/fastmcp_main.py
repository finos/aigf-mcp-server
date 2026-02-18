#!/usr/bin/env python3
"""FastMCP-based FINOS AI Governance Framework MCP Server Main Entry Point

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

Main entry point for the FastMCP-based server implementation.
Follows MCP 2025-06-18 specification with structured output and decorator-based tools.
"""

import asyncio
import signal
import sys

from .content.cache import close_cache
from .content.fetch import close_http_client
from .content.service import close_content_service
from .fastmcp_server import mcp
from .logging import get_logger

logger = get_logger("fastmcp_main")

# Global shutdown event for coordinating graceful shutdown
_shutdown_event: asyncio.Event | None = None


async def cleanup_resources() -> None:
    """Clean up all resources before shutdown."""
    logger.info("Starting graceful resource cleanup...")

    try:
        # Close all resources in order
        await close_content_service()
        logger.debug("Content service closed")

        await close_http_client()
        logger.debug("HTTP client closed")

        await close_cache()
        logger.debug("Cache closed")

        logger.info("Resource cleanup completed successfully")

    except Exception as e:
        logger.error("Error during resource cleanup: %s", e, exc_info=True)


def setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""
    global _shutdown_event

    if _shutdown_event is None:
        _shutdown_event = asyncio.Event()

    def signal_handler(signum: int, frame) -> None:
        logger.info("Received signal %d, initiating graceful shutdown...", signum)
        if _shutdown_event:
            _shutdown_event.set()

    # Handle SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main_async() -> None:
    """Run the FastMCP server with stdio transport and graceful shutdown.

    This follows the modern MCP pattern for server setup with proper resource management.
    """
    global _shutdown_event

    logger.info("Starting FINOS AI Governance MCP Server (FastMCP)")

    # Set up signal handlers
    setup_signal_handlers()

    try:
        # Prefer async stdio runner when available (MCP SDK FastMCP and some FastMCP versions).
        if hasattr(mcp, "run_stdio_async"):
            await mcp.run_stdio_async()
        else:
            # Fallback for FastMCP variants that expose only blocking run().
            await asyncio.to_thread(mcp.run)

    except KeyboardInterrupt:
        logger.info("Shutdown signal received")

    except Exception as e:
        logger.error("Server error: %s", e, exc_info=True)
        raise

    finally:
        # Always cleanup resources
        await cleanup_resources()


def main() -> None:
    """Main entry point for the FastMCP server."""
    try:
        asyncio.run(main_async())
        logger.info("Server shutdown completed")
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Server error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
