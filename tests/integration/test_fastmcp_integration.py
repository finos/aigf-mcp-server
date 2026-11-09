"""
Integration tests for FastMCP server.

Tests the complete FastMCP server functionality including MCP protocol compliance,
structured output, and real-world usage scenarios.
"""

import asyncio
import contextlib
import socket
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from finos_mcp.exceptions import UnknownDocumentError
from finos_mcp.fastmcp_server import mcp
from finos_mcp.service import get_service


@contextlib.contextmanager
def _recording_http_requests() -> Iterator[list[str]]:
    """Record every HTTP request any httpx client issues inside the block.

    ``HTTPClient._make_request`` is the single egress chokepoint in
    ``content/fetch.py`` and it reaches the network through
    ``self._client.request(...)``, so patching ``httpx.AsyncClient.request``
    counts every request the server makes, whichever client issues it.

    Yields the list of ``"<METHOD> <url>"`` strings, which is empty for a call
    that reached no network at all.
    """
    recorded: list[str] = []
    original = httpx.AsyncClient.request

    async def recording(
        self: httpx.AsyncClient, method: str, url: str, **kwargs: object
    ) -> httpx.Response:
        recorded.append(f"{method} {url}")
        return await original(self, method, url, **kwargs)  # type: ignore[arg-type]

    httpx.AsyncClient.request = recording  # type: ignore[method-assign,assignment]
    try:
        yield recorded
    finally:
        httpx.AsyncClient.request = original  # type: ignore[method-assign]


async def _list_tools():
    """List tools via the current FastMCP API."""
    return await mcp.list_tools()


async def _call_tool(name: str, arguments: dict[str, Any]):
    """Call tools via the current FastMCP API."""
    tool = await mcp.get_tool(name)
    assert tool is not None, f"tool {name!r} is not registered"
    result = await tool.run(arguments)
    return result.content, result.structured_content


async def _reset_service_health_state() -> None:
    """Zero the counters and close the content host's breaker (#326)."""
    service = await get_service()
    service.total_requests = 0
    service.successful_requests = 0
    service.failed_requests = 0
    service.circuit_breaker_trips = 0
    (await service.content_host_breaker()).on_success()


@pytest.fixture(autouse=True)
async def _isolated_service_health():
    """Reset service health counters/circuit state between tests for isolation."""
    await _reset_service_health_state()
    yield
    await _reset_service_health_state()


@pytest.mark.integration
class TestFastMCPProtocolCompliance:
    """Test FastMCP server protocol compliance and real-world integration."""

    @pytest.mark.asyncio
    async def test_server_startup_and_shutdown(self):
        """Test that FastMCP server can start and shutdown cleanly."""
        # Test server instance is available
        assert mcp is not None
        assert mcp.name == "finos-ai-governance"

        # Test tools are properly registered
        tools = await _list_tools()
        assert len(tools) >= 9  # Our expected total tools

        # Verify tool names
        tool_names = {tool.name for tool in tools}
        expected_tools = {
            "list_frameworks",
            "get_framework",
            "search_frameworks",
            "list_risks",
            "get_risk",
            "list_mitigations",
            "get_mitigation",
            "get_service_health",
            "get_cache_stats",
        }
        assert expected_tools.issubset(tool_names)

    @pytest.mark.asyncio
    async def test_structured_output_consistency(self):
        """Test that all tools return consistent structured output."""
        # Test list_frameworks
        result = await _call_tool("list_frameworks", {})
        text_content, structured_data = result

        assert isinstance(structured_data, dict)
        assert "frameworks" in structured_data
        assert "total_count" in structured_data
        assert isinstance(structured_data["frameworks"], list)
        assert structured_data["total_count"] == len(structured_data["frameworks"])

        # Test get_service_health
        result = await _call_tool("get_service_health", {})
        text_content, structured_data = result

        assert isinstance(structured_data, dict)
        required_health_fields = {
            "status",
            "uptime_seconds",
            "version",
            "healthy_services",
            "total_services",
        }
        assert required_health_fields.issubset(structured_data.keys())

    @pytest.mark.asyncio
    async def test_error_handling_consistency(self):
        """Test that errors are handled consistently across all tools."""
        # Test invalid framework request
        # An unknown id is an error, not a record that says "not found" (#193).
        with pytest.raises(UnknownDocumentError, match="'invalid-framework-id'"):
            await _call_tool("get_framework", {"framework_id": "invalid-framework-id"})

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test that multiple concurrent tool calls work correctly."""
        # Create multiple concurrent calls
        tasks = [
            _call_tool("list_frameworks", {}),
            _call_tool("list_risks", {}),
            _call_tool("list_mitigations", {}),
            _call_tool("get_service_health", {}),
            _call_tool("search_frameworks", {"query": "risk", "limit": 3}),
            _call_tool("get_cache_stats", {}),
        ]

        # Execute concurrently
        results = await asyncio.gather(*tasks)

        # Verify all calls succeeded
        assert len(results) == 6
        for result in results:
            text_content, structured_data = result
            assert isinstance(structured_data, dict)
            assert structured_data  # Not empty


@pytest.mark.integration
@pytest.mark.skip(
    reason="CLI integration tests require external MCP CLI tool installation"
)
class TestMCPCLIIntegration:
    """Test FastMCP server integration with MCP CLI tools (requires manual setup)."""

    def test_mcp_cli_tool_execution(self):
        """Test that MCP CLI can execute tools successfully."""
        pytest.skip("Requires external MCP CLI tool and proper installation")

    def test_mcp_cli_health_check(self):
        """Test health check via MCP CLI."""
        pytest.skip("Requires external MCP CLI tool and proper installation")


@pytest.mark.integration
class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    @pytest.mark.asyncio
    async def test_framework_workflow(self):
        """Test complete framework exploration workflow."""
        # Step 1: List available frameworks
        result = await _call_tool("list_frameworks", {})
        text_content, frameworks_data = result

        assert frameworks_data["total_count"] > 0
        first_framework = frameworks_data["frameworks"][0]
        framework_id = first_framework["id"]

        # Step 2: Get detailed framework content
        result = await _call_tool("get_framework", {"framework_id": framework_id})
        text_content, content_data = result

        assert content_data["framework_id"] == framework_id
        assert content_data["content"]  # Should have content
        assert content_data["entry_count"] > 0, "the first framework has no entries"

    @pytest.mark.asyncio
    async def test_risk_and_mitigation_workflow(self):
        """Test risk and mitigation exploration workflow."""
        # Step 1: List risks
        result = await _call_tool("list_risks", {})
        text_content, risks_data = result

        assert risks_data["document_type"] == "risk"
        assert risks_data["total_count"] > 0

        # Step 2: List mitigations
        result = await _call_tool("list_mitigations", {})
        text_content, mitigations_data = result

        assert mitigations_data["document_type"] == "mitigation"
        assert mitigations_data["total_count"] > 0

        # Both should have similar structure
        assert len(risks_data["documents"]) == risks_data["total_count"]
        assert len(mitigations_data["documents"]) == mitigations_data["total_count"]

    @pytest.mark.asyncio
    async def test_system_monitoring_workflow(self):
        """Test system monitoring and observability."""
        # Check service health
        result = await _call_tool("get_service_health", {})
        text_content, health_data = result

        assert health_data["status"] == "healthy"
        assert health_data["healthy_services"] == health_data["total_services"]

        # Check cache statistics
        result = await _call_tool("get_cache_stats", {})
        text_content, cache_data = result

        assert cache_data["total_requests"] >= 0
        assert 0 <= cache_data["hit_rate"] <= 1
        assert (
            cache_data["cache_hits"] + cache_data["cache_misses"]
            <= cache_data["total_requests"]
        )


@pytest.mark.integration
class TestResourceUsage:
    """What the server spends answering a call, measured in requests not seconds.

    These assertions replace a pair that read ``list_time < 1.0`` and
    ``health_time < 0.5`` around live calls to ``api.github.com`` and
    ``raw.githubusercontent.com``. A budget on a round trip measures GitHub and
    the runner, not this code. ``main`` went red on 1.09s, 1.03s and 1.02s over
    three consecutive pushes to unchanged source, and PR #131's single commit
    (31e448bf) failed on Python 3.11 in one workflow while passing on 3.11 in
    another, then went green on both when the identical commit was re-run.
    Every number a wall clock produces here belongs to somebody else.

    A request count does not. The number of HTTP requests a tool issues is
    decided entirely by this repository's caching and fan-out, it is the same on
    a fast runner and a slow one, and it is the quantity that actually matters:
    the GitHub API allows 60 unauthenticated requests an hour, which is what a
    listing that forgets to cache spends in silence.
    """

    @pytest.mark.asyncio
    async def test_repeat_listing_is_served_without_touching_the_network(self):
        """A second list_frameworks must issue no HTTP request at all.

        ``list_frameworks`` names each entry from the document itself, so a cold
        call reads every framework file: measured at 16 requests -- three
        contents-API listings plus one document each for 13 frameworks. Warm,
        it must issue zero. A listing that re-reads its corpus on every call
        spends the whole hourly API budget in a handful of calls.

        The content assertions below are load-bearing, not decoration. If the
        listing were broken and returned nothing, it would reach no network
        either, and a bare "the second call issued zero requests" would pass on
        a server that answers nothing at all.
        """
        try:
            socket.getaddrinfo("api.github.com", 443)
        except OSError:
            pytest.skip("DNS unavailable; the first call needs to populate the cache")

        # First call: warms the cache. Its own count depends on what earlier
        # tests already fetched, so nothing is asserted about it.
        _, first_payload = await _call_tool("list_frameworks", {})

        # The precondition, checked rather than assumed. On the static-fallback
        # path nothing was fetched, so there is nothing cached and no caching to
        # measure -- and every later assertion here would be reporting a GitHub
        # outage as a defect in this repository, which is the mistake #132 is
        # about. An expired list file is the same case: GitHub could not be
        # asked, and the next call asks again (#278).
        if first_payload["source"] in ("static_fallback", "expired_cache"):
            pytest.skip(
                f"listing came from {first_payload['source']}, so no fetch was cached"
            )

        frameworks = first_payload["frameworks"]
        assert frameworks, "list_frameworks returned no frameworks to serve from cache"
        # Case-insensitive: the #118 defect handed the raw filename to
        # _format_framework_name, which published "Eu Ai Act.Yml" -- a name that
        # a case-sensitive check for ".yml" would have let through.
        by_filename = [f["name"] for f in frameworks if ".yml" in f["name"].lower()]
        assert not by_filename, (
            f"frameworks are named by filename, so the listing never read them: "
            f"{by_filename}"
        )

        with _recording_http_requests() as requests:
            _, second_payload = await _call_tool("list_frameworks", {})

        assert second_payload["frameworks"] == frameworks, (
            "the repeat listing answered differently from the first"
        )
        assert requests == [], (
            f"a repeat listing issued {len(requests)} HTTP requests instead of "
            f"being served from cache: {requests}"
        )

    @pytest.mark.asyncio
    async def test_health_check_never_reaches_the_network(self):
        """get_service_health reports on subsystems already in this process.

        It reads error-boundary and parser diagnostics that live in memory, so
        it must reach no network -- which is also why this test, unlike the one
        above, needs no DNS and runs everywhere. A health check that fetches is
        a health check that fails when the thing it is reporting on fails.
        """
        with _recording_http_requests() as requests:
            _, payload = await _call_tool("get_service_health", {})

        assert requests == [], (
            f"the health check issued {len(requests)} HTTP requests: {requests}"
        )
        assert payload["status"] in {"healthy", "degraded"}, (
            f"health check reported an unrecognised status: {payload['status']!r}"
        )
        assert payload["total_services"] > 0, (
            "health check reported on no subsystems at all"
        )

    @pytest.mark.asyncio
    async def test_memory_efficiency(self):
        """Test that repeated calls complete successfully (basic stability test)."""
        import gc

        # Perform many tool calls to test stability
        for _ in range(50):  # Reduced count for CI stability
            await _call_tool("list_frameworks", {})
            await _call_tool("get_service_health", {})

        # Force garbage collection
        gc.collect()

        # If we get here without crashes, memory management is working
        # This is a basic stability test rather than detailed memory monitoring
        assert True, "Repeated calls completed successfully"
