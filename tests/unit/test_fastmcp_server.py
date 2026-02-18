"""
Test suite for FastMCP server implementation.

Tests the modern FastMCP-based server with structured output and decorator-based tools.
"""

import inspect

import pytest
from pydantic import ValidationError

from finos_mcp.fastmcp_server import (
    CacheStats,
    DocumentList,
    Framework,
    FrameworkContent,
    FrameworkList,
    ServiceHealth,
    get_cache_stats,
    get_framework,
    get_service_health,
    list_frameworks,
    list_mitigations,
    list_risks,
    mcp,
)


async def _list_tools_compat():
    """List tools across MCP SDK FastMCP and standalone FastMCP."""
    if hasattr(mcp, "list_tools"):
        return await mcp.list_tools()
    tools = await mcp.get_tools()
    return list(tools.values())


async def _call_tool_compat(name: str, arguments: dict):
    """Call tools across MCP SDK FastMCP and standalone FastMCP."""
    if hasattr(mcp, "call_tool"):
        return await mcp.call_tool(name, arguments)
    tools = await mcp.get_tools()
    result = await tools[name].run(arguments)
    return result.content, result.structured_content


async def _invoke_direct_tool(tool_obj, *args, **kwargs):
    """Invoke decorated tools across function and FunctionTool representations."""
    if hasattr(tool_obj, "fn"):
        result = tool_obj.fn(*args, **kwargs)
    else:
        result = tool_obj(*args, **kwargs)

    if inspect.isawaitable(result):
        return await result
    return result


@pytest.mark.unit
class TestFastMCPServer:
    """Test FastMCP server instance and configuration."""

    def test_server_instance(self):
        """Test that FastMCP server is properly instantiated."""
        assert mcp is not None
        assert mcp.name == "finos-ai-governance"

    @pytest.mark.asyncio
    async def test_server_tools_registration(self):
        """Test that tools are properly registered with FastMCP."""
        tools = await _list_tools_compat()

        # Expected tools from our FastMCP server
        expected_tools = {
            "list_frameworks",
            "get_framework",
            "list_risks",
            "list_mitigations",
            "get_service_health",
            "get_cache_stats",
        }

        actual_tools = {tool.name for tool in tools}
        assert expected_tools.issubset(actual_tools)


@pytest.mark.unit
class TestStructuredOutputModels:
    """Test Pydantic models for structured output."""

    def test_framework_model(self):
        """Test Framework model validation."""
        framework = Framework(
            id="test-framework", name="Test Framework", description="A test framework"
        )
        assert framework.id == "test-framework"
        assert framework.name == "Test Framework"
        assert framework.description == "A test framework"

    def test_framework_list_model(self):
        """Test FrameworkList model validation."""
        frameworks = [
            Framework(id="fw1", name="Framework 1", description="Description 1"),
            Framework(id="fw2", name="Framework 2", description="Description 2"),
        ]

        framework_list = FrameworkList(frameworks=frameworks, total_count=2)
        assert len(framework_list.frameworks) == 2
        assert framework_list.total_count == 2
        assert framework_list.frameworks[0].id == "fw1"

    def test_framework_content_model(self):
        """Test FrameworkContent model validation."""
        content = FrameworkContent(
            framework_id="test-fw",
            content="Test content",
            sections=3,
            last_updated="2024-01-01",
        )
        assert content.framework_id == "test-fw"
        assert content.content == "Test content"
        assert content.sections == 3
        assert content.last_updated == "2024-01-01"

    def test_document_list_model(self):
        """Test DocumentList model validation."""
        docs = [
            {
                "id": "doc1",
                "name": "Document 1",
                "filename": "doc1.md",
                "description": "Desc 1",
            },
            {
                "id": "doc2",
                "name": "Document 2",
                "filename": "doc2.md",
                "description": "Desc 2",
            },
        ]

        doc_list = DocumentList(
            documents=docs, total_count=2, document_type="risk", source="test"
        )
        assert len(doc_list.documents) == 2
        assert doc_list.total_count == 2
        assert doc_list.document_type == "risk"

    def test_service_health_model(self):
        """Test ServiceHealth model validation."""
        health = ServiceHealth(
            status="healthy",
            uptime_seconds=123.45,
            version="1.0.0",
            healthy_services=4,
            total_services=4,
        )
        assert health.status == "healthy"
        assert health.uptime_seconds == 123.45
        assert health.version == "1.0.0"
        assert health.healthy_services == 4

    def test_cache_stats_model(self):
        """Test CacheStats model validation."""
        stats = CacheStats(
            total_requests=100, cache_hits=75, cache_misses=25, hit_rate=0.75
        )
        assert stats.total_requests == 100
        assert stats.cache_hits == 75
        assert stats.cache_misses == 25
        assert stats.hit_rate == 0.75


@pytest.mark.unit
class TestFastMCPTools:
    """Test FastMCP tool functions with structured output."""

    @pytest.mark.asyncio
    async def test_list_frameworks(self):
        """Test list_frameworks tool returns structured FrameworkList."""
        result = await _invoke_direct_tool(list_frameworks)

        assert isinstance(result, FrameworkList)
        assert result.total_count > 0
        assert len(result.frameworks) == result.total_count

        # Check first framework structure
        framework = result.frameworks[0]
        assert isinstance(framework, Framework)
        assert framework.id
        assert framework.name
        assert framework.description

    @pytest.mark.asyncio
    async def test_get_framework_valid_framework(self):
        """Test get_framework with valid framework ID."""
        result = await _invoke_direct_tool(get_framework, "nist-ai-rmf")

        assert isinstance(result, FrameworkContent)
        assert result.framework_id == "nist-ai-rmf"
        assert result.content
        assert result.sections >= 0

    @pytest.mark.asyncio
    async def test_get_framework_invalid_framework(self):
        """Test get_framework with invalid framework ID."""
        result = await _invoke_direct_tool(get_framework, "invalid-framework")

        assert isinstance(result, FrameworkContent)
        assert result.framework_id == "invalid-framework"
        assert "not found" in result.content.lower()
        assert result.sections == 0

    @pytest.mark.asyncio
    async def test_list_risks(self):
        """Test list_risks tool returns structured DocumentList."""
        result = await _invoke_direct_tool(list_risks)

        assert isinstance(result, DocumentList)
        assert result.document_type == "risk"
        assert result.total_count > 0
        assert len(result.documents) == result.total_count

        # Check document structure
        doc = result.documents[0]
        assert hasattr(doc, "id") and doc.id
        assert hasattr(doc, "name") and doc.name
        assert hasattr(doc, "description") and doc.description

    @pytest.mark.asyncio
    async def test_list_mitigations(self):
        """Test list_mitigations tool returns structured DocumentList."""
        result = await _invoke_direct_tool(list_mitigations)

        assert isinstance(result, DocumentList)
        assert result.document_type == "mitigation"
        assert result.total_count > 0
        assert len(result.documents) == result.total_count

    @pytest.mark.asyncio
    async def test_get_service_health(self):
        """Test get_service_health tool returns structured ServiceHealth."""
        result = await _invoke_direct_tool(get_service_health)

        assert isinstance(result, ServiceHealth)
        assert result.status == "healthy"
        assert result.uptime_seconds > 0
        assert result.version
        assert result.healthy_services > 0
        assert result.total_services > 0

    @pytest.mark.asyncio
    async def test_get_cache_stats(self):
        """Test get_cache_stats tool returns structured CacheStats."""
        result = await _invoke_direct_tool(get_cache_stats)

        assert isinstance(result, CacheStats)
        assert result.total_requests > 0
        assert result.cache_hits >= 0
        assert result.cache_misses >= 0
        assert 0 <= result.hit_rate <= 1


@pytest.mark.unit
class TestFastMCPIntegration:
    """Test FastMCP server integration and tool calls."""

    @pytest.mark.asyncio
    async def test_mcp_call_tool_list_frameworks(self):
        """Test calling list_frameworks through FastMCP server."""
        result = await _call_tool_compat("list_frameworks", {})

        # FastMCP returns tuple: (TextContent, structured_data)
        text_content, structured_data = result

        # Verify structured data
        assert isinstance(structured_data, dict)
        assert "frameworks" in structured_data
        assert "total_count" in structured_data
        assert structured_data["total_count"] > 0

    @pytest.mark.asyncio
    async def test_mcp_call_tool_get_service_health(self):
        """Test calling get_service_health through FastMCP server."""
        result = await _call_tool_compat("get_service_health", {})

        text_content, structured_data = result

        assert isinstance(structured_data, dict)
        assert structured_data["status"] == "healthy"
        assert "version" in structured_data
        assert "uptime_seconds" in structured_data

    @pytest.mark.asyncio
    async def test_mcp_call_tool_with_parameters(self):
        """Test calling tool with parameters through FastMCP server."""
        result = await _call_tool_compat("get_framework", {"framework": "gdpr"})

        text_content, structured_data = result

        assert isinstance(structured_data, dict)
        assert structured_data["framework_id"] == "gdpr"
        assert "content" in structured_data
        assert "sections" in structured_data

    @pytest.mark.asyncio
    async def test_mcp_invalid_tool_call(self):
        """Test calling non-existent tool raises appropriate error."""
        with pytest.raises(Exception):  # FastMCP will raise an exception
            await _call_tool_compat("nonexistent_tool", {})


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling in FastMCP tools."""

    @pytest.mark.asyncio
    async def test_framework_content_error_handling(self):
        """Test that framework content errors are handled gracefully."""
        result = await _invoke_direct_tool(get_framework, "nonexistent-framework")

        assert isinstance(result, FrameworkContent)
        assert "not found" in result.content.lower()
        assert result.sections == 0

    def test_pydantic_validation_errors(self):
        """Test that Pydantic models validate input correctly."""
        # Test missing required fields
        with pytest.raises(ValidationError):
            Framework()  # Missing required fields

        # Test invalid data types
        with pytest.raises(ValidationError):
            CacheStats(
                total_requests="invalid",  # Should be int
                cache_hits=75,
                cache_misses=25,
                hit_rate=0.75,
            )
