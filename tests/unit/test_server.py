"""
Test suite for server.py - MCP server functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import Resource, TextContent, Tool
from pydantic import AnyUrl

from finos_mcp.server import (
    ContentServiceInstanceManager,
    get_content_service_instance,
    handle_call_tool,
    handle_list_resources,
    handle_list_tools,
    handle_read_resource,
    log_health_status,
)


@pytest.mark.unit
class TestContentServiceInstanceManager:
    """Test ContentServiceInstanceManager functionality."""

    def test_singleton_pattern(self):
        """Test that ContentServiceInstanceManager is a singleton."""
        manager1 = ContentServiceInstanceManager()
        manager2 = ContentServiceInstanceManager()
        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_get_content_service_instance(self):
        """Test getting content service instance."""
        manager = ContentServiceInstanceManager()

        with patch("finos_mcp.server.get_content_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_get_service.return_value = mock_service

            service = await manager.get_content_service_instance()
            assert service == mock_service
            mock_get_service.assert_called_once()


@pytest.mark.unit
class TestServerFunctions:
    """Test server handler functions."""

    @pytest.mark.asyncio
    async def test_get_content_service_instance_function(self):
        """Test the standalone get_content_service_instance function."""
        with patch(
            "finos_mcp.server._content_service_instance_manager.get_content_service_instance"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_get_service.return_value = mock_service

            service = await get_content_service_instance()
            assert service == mock_service

    @pytest.mark.asyncio
    async def test_handle_list_resources(self):
        """Test listing resources handler."""
        with (
            patch("finos_mcp.server.get_mitigation_files") as mock_get_mitigations,
            patch("finos_mcp.server.get_risk_files") as mock_get_risks,
        ):
            mock_get_mitigations.return_value = ["mit1.md", "mit2.md"]
            mock_get_risks.return_value = ["risk1.md", "risk2.md"]

            resources = await handle_list_resources()

            assert len(resources) == 4
            assert all(isinstance(r, Resource) for r in resources)

            # Verify resource structure
            resource_uris = [str(r.uri) for r in resources]
            assert "finos://mitigations/mit1.md" in resource_uris
            assert "finos://risks/risk1.md" in resource_uris

    @pytest.mark.asyncio
    async def test_handle_read_resource_mitigation(self):
        """Test reading a mitigation resource."""
        with patch("finos_mcp.server.get_content_service_instance") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_document.return_value = {
                "filename": "test.md",
                "metadata": {"title": "Test Mitigation"},
                "content": "Test content",
                "full_text": "Full text content",
            }
            mock_get_service.return_value = mock_service

            uri = AnyUrl("finos://mitigations/test.md")
            content = await handle_read_resource(uri)

            assert content == "Full text content"
            mock_service.get_document.assert_called_once_with("mitigation", "test.md")

    @pytest.mark.asyncio
    async def test_handle_read_resource_risk(self):
        """Test reading a risk resource."""
        with patch("finos_mcp.server.get_content_service_instance") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_document.return_value = {
                "filename": "risk.md",
                "metadata": {"title": "Test Risk"},
                "content": "Risk content",
                "full_text": "Full risk text",
            }
            mock_get_service.return_value = mock_service

            uri = AnyUrl("finos://risks/risk.md")
            content = await handle_read_resource(uri)

            assert content == "Full risk text"
            mock_service.get_document.assert_called_once_with("risk", "risk.md")

    @pytest.mark.asyncio
    async def test_handle_list_tools(self):
        """Test listing available tools."""
        tools = await handle_list_tools()

        assert len(tools) >= 4  # At least the main tools
        assert all(isinstance(tool, Tool) for tool in tools)

        tool_names = [tool.name for tool in tools]
        assert "search_mitigations" in tool_names
        assert "search_risks" in tool_names
        assert "list_all_mitigations" in tool_names
        assert "list_all_risks" in tool_names

    @pytest.mark.asyncio
    async def test_handle_call_tool_search_mitigations(self):
        """Test calling the search_mitigations tool."""
        from finos_mcp.security.config import ValidationConfig, ValidationMode

        # Create disabled validator for testing
        test_validator = ValidationConfig(ValidationMode.DISABLED)

        with patch("finos_mcp.server.handle_tool_call") as mock_handler:
            mock_handler.return_value = [TextContent(type="text", text="Search result")]

            result = await handle_call_tool(
                "search_mitigations", {"query": "privacy"}, test_validator
            )

            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            assert result[0].text == "Search result"
            mock_handler.assert_called_once_with(
                "search_mitigations", {"query": "privacy"}
            )

    @pytest.mark.asyncio
    async def test_handle_call_tool_invalid_tool(self):
        """Test calling an invalid tool name."""
        with pytest.raises(ValueError, match="Unknown tool"):
            await handle_call_tool("invalid_tool", {})

    @pytest.mark.asyncio
    async def test_log_health_status(self):
        """Test health status logging."""
        with (
            patch("finos_mcp.server.get_health_monitor") as mock_get_monitor,
            patch("finos_mcp.server.logger") as mock_logger,
        ):
            mock_monitor = MagicMock()
            mock_overall_health = MagicMock()
            mock_overall_health.status.value = "healthy"
            mock_overall_health.message = "All systems operational"
            mock_monitor.get_overall_health.return_value = mock_overall_health
            mock_monitor.get_health_summary.return_value = {
                "uptime_seconds": 100.0,
                "summary": {
                    "total_services": 3,
                    "healthy_services": 3,
                    "degraded_services": 0,
                    "unhealthy_services": 0,
                },
            }
            mock_get_monitor.return_value = mock_monitor

            await log_health_status()

            # Verify health monitor was called
            mock_get_monitor.assert_called_once()
            mock_monitor.get_health_summary.assert_called_once()
            mock_monitor.get_overall_health.assert_called_once()

            # Verify logging occurred
            mock_logger.info.assert_called()
