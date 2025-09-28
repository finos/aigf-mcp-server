"""
Integration tests for FastMCP server.

Tests the complete FastMCP server functionality including MCP protocol compliance,
structured output, and real-world usage scenarios.
"""

import asyncio

import pytest

from finos_mcp.fastmcp_server import mcp


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
        tools = await mcp.list_tools()
        assert len(tools) >= 11  # Our expected total tools

        # Verify tool names
        tool_names = {tool.name for tool in tools}
        expected_tools = {
            "list_frameworks",
            "get_framework",
            "search_frameworks",
            "list_risks",
            "get_risk",
            "search_risks",
            "list_mitigations",
            "get_mitigation",
            "search_mitigations",
            "get_service_health",
            "get_cache_stats",
        }
        assert expected_tools.issubset(tool_names)

    @pytest.mark.asyncio
    async def test_structured_output_consistency(self):
        """Test that all tools return consistent structured output."""
        # Test list_frameworks
        result = await mcp.call_tool("list_frameworks", {})
        text_content, structured_data = result

        assert isinstance(structured_data, dict)
        assert "frameworks" in structured_data
        assert "total_count" in structured_data
        assert isinstance(structured_data["frameworks"], list)
        assert structured_data["total_count"] == len(structured_data["frameworks"])

        # Test get_service_health
        result = await mcp.call_tool("get_service_health", {})
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
        result = await mcp.call_tool(
            "get_framework", {"framework": "invalid-framework-id"}
        )
        text_content, structured_data = result

        assert isinstance(structured_data, dict)
        assert structured_data["framework_id"] == "invalid-framework-id"
        assert "not found" in structured_data["content"].lower()
        assert structured_data["sections"] == 0

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test that multiple concurrent tool calls work correctly."""
        # Create multiple concurrent calls
        tasks = [
            mcp.call_tool("list_frameworks", {}),
            mcp.call_tool("list_risks", {}),
            mcp.call_tool("list_mitigations", {}),
            mcp.call_tool("get_service_health", {}),
            mcp.call_tool("search_frameworks", {"query": "risk", "limit": 3}),
            mcp.call_tool("search_risks", {"query": "privacy", "limit": 3}),
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
@pytest.mark.skip(reason="CLI integration tests require external MCP CLI tool installation")
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
        result = await mcp.call_tool("list_frameworks", {})
        text_content, frameworks_data = result

        assert frameworks_data["total_count"] > 0
        first_framework = frameworks_data["frameworks"][0]
        framework_id = first_framework["id"]

        # Step 2: Get detailed framework content
        result = await mcp.call_tool("get_framework", {"framework": framework_id})
        text_content, content_data = result

        assert content_data["framework_id"] == framework_id
        assert content_data["content"]  # Should have content
        assert content_data["sections"] >= 0

    @pytest.mark.asyncio
    async def test_risk_and_mitigation_workflow(self):
        """Test risk and mitigation exploration workflow."""
        # Step 1: List risks
        result = await mcp.call_tool("list_risks", {})
        text_content, risks_data = result

        assert risks_data["document_type"] == "risk"
        assert risks_data["total_count"] > 0

        # Step 2: List mitigations
        result = await mcp.call_tool("list_mitigations", {})
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
        result = await mcp.call_tool("get_service_health", {})
        text_content, health_data = result

        assert health_data["status"] == "healthy"
        assert health_data["healthy_services"] == health_data["total_services"]

        # Check cache statistics
        result = await mcp.call_tool("get_cache_stats", {})
        text_content, cache_data = result

        assert cache_data["total_requests"] > 0
        assert 0 <= cache_data["hit_rate"] <= 1
        assert (
            cache_data["cache_hits"] + cache_data["cache_misses"]
            <= cache_data["total_requests"]
        )


@pytest.mark.integration
class TestPerformanceCharacteristics:
    """Test performance characteristics of FastMCP server."""

    @pytest.mark.asyncio
    async def test_response_times(self):
        """Test that tool responses are within acceptable time limits."""
        import time

        # Test list operations (should be fast)
        start_time = time.time()
        await mcp.call_tool("list_frameworks", {})
        list_time = time.time() - start_time

        assert list_time < 1.0, f"List frameworks took {list_time:.2f}s (expected < 1s)"

        # Test health check (should be very fast)
        start_time = time.time()
        await mcp.call_tool("get_service_health", {})
        health_time = time.time() - start_time

        assert health_time < 0.5, (
            f"Health check took {health_time:.2f}s (expected < 0.5s)"
        )

    @pytest.mark.asyncio
    async def test_memory_efficiency(self):
        """Test that repeated calls complete successfully (basic stability test)."""
        import gc

        # Perform many tool calls to test stability
        for _ in range(50):  # Reduced count for CI stability
            await mcp.call_tool("list_frameworks", {})
            await mcp.call_tool("get_service_health", {})

        # Force garbage collection
        gc.collect()

        # If we get here without crashes, memory management is working
        # This is a basic stability test rather than detailed memory monitoring
        assert True, "Repeated calls completed successfully"
