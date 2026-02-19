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
from .fastmcp_server import mcp, settings
from .logging import get_logger

logger = get_logger("fastmcp_main")

# Global shutdown event for coordinating graceful shutdown
_shutdown_event: asyncio.Event | None = None


async def cleanup_resources() -> None:
    """Clean up all resources before shutdown.

    Each resource is closed independently so that a failure in one does not
    prevent the others from being cleaned up.
    """
    logger.info("Starting graceful resource cleanup...")

    _resources = [
        (close_content_service, "content service"),
        (close_http_client, "HTTP client"),
        (close_cache, "cache"),
    ]

    errors: list[str] = []
    for close_fn, name in _resources:
        try:
            await close_fn()
            logger.debug("%s closed", name)
        except Exception as e:
            errors.append(name)
            logger.warning("Error closing %s: %s", name, e, exc_info=True)

    if errors:
        logger.warning(
            "Resource cleanup completed with errors in: %s", ", ".join(errors)
        )
    else:
        logger.info("Resource cleanup completed successfully")


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

    EVENT LOOP ARCHITECTURE NOTE (A-02):
    FastMCP's mcp.run() is a synchronous blocking call that internally starts
    its own event loop.  It is wrapped in asyncio.to_thread() so that it runs
    in a ThreadPoolExecutor thread, keeping the main asyncio event loop free to
    handle shutdown signals and cleanup coroutines.

    Consequence: two event loops are active concurrently — FastMCP's loop
    (in the worker thread) and the main loop (on the main thread).  asyncio
    primitives (Lock, Event, Queue) created in one loop cannot be awaited from
    the other without a RuntimeError.  All shared async resources (cache,
    HTTP client, content service) are initialised lazily on first use inside
    FastMCP's tool handlers (which run in FastMCP's thread loop), and the
    cleanup coroutines in cleanup_resources() run on the *main* loop.

    This is safe as long as:
    (a) Cleanup is invoked *after* mcp.run() returns (i.e. after FastMCP's
        loop has stopped), so no shared objects are being awaited concurrently.
    (b) AsyncServiceManager._ensure_loop_context() detects loop changes and
        resets singletons when a new loop is observed, preventing stale
        cross-loop object references.

    Validate this architecture under load and graceful-shutdown scenarios
    before enabling HTTP transport in production.
    """
    global _shutdown_event

    logger.info("Starting FINOS AI Governance MCP Server (FastMCP)")
    logger.info("Configured transport: %s", settings.mcp_transport)

    # Set up signal handlers
    setup_signal_handlers()

    try:
        if settings.mcp_transport == "stdio":
            await asyncio.to_thread(mcp.run, transport="stdio")
        else:
            await asyncio.to_thread(
                mcp.run,
                transport=settings.mcp_transport,
                host=settings.mcp_host,
                port=settings.mcp_port,
            )

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
