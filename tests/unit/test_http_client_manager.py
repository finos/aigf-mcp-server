"""
Unit tests for HTTPClientManager loop-context guard and cleanup_resources() isolation.

Validates the fix for RuntimeError: Event loop is closed that occurred when
fastmcp_main.cleanup_resources() ran on the main event loop (L1) after
mcp.run() had created and closed its own loop (L2) in a worker thread.

Two invariants are tested:

1. HTTPClientManager.close_http_client() discards the client reference
   (without calling aclose()) when the client was created in a different
   or already-closed event loop.

2. cleanup_resources() closes every resource independently, so that a
   failure on one resource does not prevent the others from being cleaned up.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finos_mcp.content.fetch import HTTPClientManager


# ---------------------------------------------------------------------------
# HTTPClientManager.close_http_client() – loop-context guard
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHTTPClientManagerCloseGuard:
    """Verify the event-loop guard in HTTPClientManager.close_http_client()."""

    async def test_close_when_no_client_is_noop(self):
        """Returns cleanly when no client is held (_http_client is None)."""
        manager = HTTPClientManager.__new__(HTTPClientManager)
        manager._http_client = None
        manager._loop = None

        # Must not raise
        await manager.close_http_client()

        assert manager._http_client is None

    async def test_close_on_same_loop_calls_client_close(self):
        """Calls close() when the stored loop matches the current loop."""
        manager = HTTPClientManager.__new__(HTTPClientManager)

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        manager._http_client = mock_client
        manager._loop = asyncio.get_running_loop()  # same loop as caller

        await manager.close_http_client()

        mock_client.close.assert_awaited_once()
        assert manager._http_client is None
        assert manager._loop is None

    async def test_close_on_closed_loop_skips_aclose(self):
        """Discards client without calling close() when stored loop is closed.

        This reproduces the exact scenario from the bug report: mcp.run()
        creates loop L2 in a worker thread, resources are created there,
        L2 is closed when the thread exits, then cleanup runs on L1 and
        must not attempt aclose() against L2's transports.
        """
        manager = HTTPClientManager.__new__(HTTPClientManager)

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        manager._http_client = mock_client

        # Simulate L2: a separate loop that has already been closed
        old_loop = asyncio.new_event_loop()
        old_loop.close()
        manager._loop = old_loop

        # Must not raise RuntimeError: Event loop is closed
        await manager.close_http_client()

        # aclose() must NOT have been attempted against the closed loop
        mock_client.close.assert_not_awaited()

        # Reference must be released
        assert manager._http_client is None
        assert manager._loop is None

    async def test_close_on_different_live_loop_skips_aclose(self):
        """Discards client without calling close() when loop identity differs.

        Guards against a live-but-foreign loop (different asyncio.run() call)
        even if that loop is not yet closed.
        """
        manager = HTTPClientManager.__new__(HTTPClientManager)

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        manager._http_client = mock_client

        # Use a different loop object — identity check (is not) should trigger
        foreign_loop = MagicMock(spec=asyncio.AbstractEventLoop)
        foreign_loop.is_closed.return_value = False  # live, but different identity
        manager._loop = foreign_loop

        await manager.close_http_client()

        mock_client.close.assert_not_awaited()
        assert manager._http_client is None
        assert manager._loop is None

    async def test_close_when_loop_is_none_calls_client_close(self):
        """Calls close() when _loop is None (no loop tracked yet — safe path).

        If _loop is None the guard condition is False, so we attempt the normal
        close.  This is the conservative-but-safe fallback.
        """
        manager = HTTPClientManager.__new__(HTTPClientManager)

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        manager._http_client = mock_client
        manager._loop = None  # no loop recorded

        await manager.close_http_client()

        mock_client.close.assert_awaited_once()
        assert manager._http_client is None


# ---------------------------------------------------------------------------
# cleanup_resources() – per-resource error isolation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCleanupResourcesIsolation:
    """Verify that cleanup_resources() closes every resource independently."""

    async def test_all_close_successfully(self):
        """All three close calls are made when none raise."""
        from finos_mcp.fastmcp_main import cleanup_resources

        close_calls: list[str] = []

        async def ok_content():
            close_calls.append("content_service")

        async def ok_http():
            close_calls.append("http_client")

        async def ok_cache():
            close_calls.append("cache")

        with (
            patch("finos_mcp.fastmcp_main.close_content_service", ok_content),
            patch("finos_mcp.fastmcp_main.close_http_client", ok_http),
            patch("finos_mcp.fastmcp_main.close_cache", ok_cache),
        ):
            await cleanup_resources()

        assert close_calls == ["content_service", "http_client", "cache"]

    async def test_first_failure_does_not_skip_remaining(self):
        """When content_service close raises, http_client and cache are still closed."""
        from finos_mcp.fastmcp_main import cleanup_resources

        close_calls: list[str] = []

        async def failing_content():
            raise RuntimeError("Event loop is closed")

        async def ok_http():
            close_calls.append("http_client")

        async def ok_cache():
            close_calls.append("cache")

        with (
            patch("finos_mcp.fastmcp_main.close_content_service", failing_content),
            patch("finos_mcp.fastmcp_main.close_http_client", ok_http),
            patch("finos_mcp.fastmcp_main.close_cache", ok_cache),
        ):
            # Must not re-raise
            await cleanup_resources()

        assert close_calls == ["http_client", "cache"]

    async def test_middle_failure_does_not_skip_last(self):
        """When http_client close raises, cache is still closed."""
        from finos_mcp.fastmcp_main import cleanup_resources

        close_calls: list[str] = []

        async def ok_content():
            close_calls.append("content_service")

        async def failing_http():
            raise RuntimeError("Event loop is closed")

        async def ok_cache():
            close_calls.append("cache")

        with (
            patch("finos_mcp.fastmcp_main.close_content_service", ok_content),
            patch("finos_mcp.fastmcp_main.close_http_client", failing_http),
            patch("finos_mcp.fastmcp_main.close_cache", ok_cache),
        ):
            await cleanup_resources()

        assert close_calls == ["content_service", "cache"]

    async def test_all_failures_still_completes_without_raising(self):
        """cleanup_resources() completes without raising even if all three fail."""
        from finos_mcp.fastmcp_main import cleanup_resources

        async def failing():
            raise RuntimeError("Event loop is closed")

        with (
            patch("finos_mcp.fastmcp_main.close_content_service", failing),
            patch("finos_mcp.fastmcp_main.close_http_client", failing),
            patch("finos_mcp.fastmcp_main.close_cache", failing),
        ):
            # Must not propagate any exception
            await cleanup_resources()

    async def test_non_runtime_error_also_isolated(self):
        """Non-RuntimeError exceptions are also caught per-resource."""
        from finos_mcp.fastmcp_main import cleanup_resources

        close_calls: list[str] = []

        async def failing_content():
            raise ValueError("unexpected internal error")

        async def ok_http():
            close_calls.append("http_client")

        async def ok_cache():
            close_calls.append("cache")

        with (
            patch("finos_mcp.fastmcp_main.close_content_service", failing_content),
            patch("finos_mcp.fastmcp_main.close_http_client", ok_http),
            patch("finos_mcp.fastmcp_main.close_cache", ok_cache),
        ):
            await cleanup_resources()

        assert close_calls == ["http_client", "cache"]
