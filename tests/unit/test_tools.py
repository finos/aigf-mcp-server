"""
Unit tests for modular tools implementation.

Tests each tool module independently and validates input validation
using Pydantic models.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finos_mcp.tools import get_all_tools, handle_tool_call
from finos_mcp.tools.details import handle_details_tools
from finos_mcp.tools.listing import handle_listing_tools
from finos_mcp.tools.search import handle_search_tools
from finos_mcp.tools.system import handle_system_tools


@pytest.mark.unit
class TestToolsPackage:
    """Test the main tools package functionality."""

    def test_get_all_tools(self):
        """Test that all tools are properly loaded."""
        tools = get_all_tools()

        # Should have 15 tools total (10 original + 5 framework tools)
        assert len(tools) == 15

        # Check tool names
        tool_names = [tool.name for tool in tools]
        expected_tools = [
            "search_mitigations",
            "search_risks",
            "get_mitigation_details",
            "get_risk_details",
            "list_all_mitigations",
            "list_all_risks",
            "get_cache_stats",
            "get_service_health",
            "get_service_metrics",
            "reset_service_health",
            # Framework tools
            "search_frameworks",
            "list_frameworks",
            "get_framework_details",
            "get_compliance_analysis",
            "search_framework_references",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names

    @pytest.mark.asyncio
    async def test_handle_tool_call_unknown_tool(self):
        """Test handling of unknown tool calls."""
        with pytest.raises(ValueError, match="Unknown tool: nonexistent_tool"):
            await handle_tool_call("nonexistent_tool", {})


@pytest.mark.unit
class TestSearchTools:
    """Test search tools functionality."""

    @pytest.mark.asyncio
    async def test_search_mitigations_input_validation(self):
        """Test input validation for search mitigations."""
        # Mock the content service
        mock_service = AsyncMock()
        mock_service.get_document.return_value = {
            "metadata": {
                "title": "Test Mitigation",
                "sequence": 1,
                "type": "mitigation",
            },
            "content": "Test content with data leakage keywords",
            "full_text": "Full content",
        }

        with patch(
            "finos_mcp.tools.search.get_content_service", return_value=mock_service
        ):
            # Test valid input
            result = await handle_search_tools(
                "search_mitigations", {"query": "data leakage", "exact_match": False}
            )

            assert len(result) == 1
            assert result[0].type == "text"

            # Parse and validate result
            search_results = json.loads(result[0].text)
            assert isinstance(search_results, list)

    @pytest.mark.asyncio
    async def test_search_risks_input_validation(self):
        """Test input validation for search risks."""
        # Mock the content service
        mock_service = AsyncMock()
        mock_service.get_document.return_value = {
            "metadata": {"title": "Test Risk", "sequence": 1, "type": "risk"},
            "content": "Test content with prompt injection keywords",
            "full_text": "Full content",
        }

        with patch(
            "finos_mcp.tools.search.get_content_service", return_value=mock_service
        ):
            # Test valid input
            result = await handle_search_tools(
                "search_risks", {"query": "prompt injection"}
            )

            assert len(result) == 1
            assert result[0].type == "text"

    @pytest.mark.asyncio
    async def test_search_tools_pydantic_validation(self):
        """Test that Pydantic validation catches invalid inputs."""
        with pytest.raises((ValueError, TypeError)):  # Pydantic validation error
            await handle_search_tools(
                "search_mitigations",
                {
                    # Missing required "query" field
                    "exact_match": True
                },
            )


@pytest.mark.unit
class TestDetailsTools:
    """Test details tools functionality."""

    @pytest.mark.asyncio
    async def test_get_mitigation_details(self):
        """Test getting mitigation details."""
        # Mock the content service
        mock_service = AsyncMock()
        mock_service.get_document.return_value = {
            "full_text": "# MI-1 Test Mitigation\nThis is test content."
        }

        with patch(
            "finos_mcp.tools.details.get_content_service", return_value=mock_service
        ):
            result = await handle_details_tools(
                "get_mitigation_details", {"mitigation_id": "mi-1"}
            )

            assert len(result) == 1
            assert result[0].type == "text"
            assert "# MI-1 Test Mitigation" in result[0].text

    @pytest.mark.asyncio
    async def test_get_risk_details(self):
        """Test getting risk details."""
        # Mock the content service
        mock_service = AsyncMock()
        mock_service.get_document.return_value = {
            "full_text": "# RI-10 Prompt Injection\nThis is test content."
        }

        with patch(
            "finos_mcp.tools.details.get_content_service", return_value=mock_service
        ):
            result = await handle_details_tools(
                "get_risk_details", {"risk_id": "ri-10"}
            )

            assert len(result) == 1
            assert result[0].type == "text"
            assert "# RI-10 Prompt Injection" in result[0].text

    @pytest.mark.asyncio
    async def test_details_tools_file_not_found(self):
        """Test handling when document file is not found."""
        with patch("finos_mcp.tools.details.get_content_service"):
            result = await handle_details_tools(
                "get_mitigation_details", {"mitigation_id": "non-existent-id"}
            )

            assert len(result) == 1
            assert "not found" in result[0].text


@pytest.mark.unit
class TestListingTools:
    """Test listing tools functionality."""

    @pytest.mark.asyncio
    async def test_list_all_mitigations(self):
        """Test listing all mitigations."""
        # Mock the content service
        mock_service = AsyncMock()

        # Create a list of mock returns for different calls
        def mock_get_document(doc_type, filename):
            return {
                "metadata": {
                    "title": f"Test {doc_type.capitalize()}",
                    "sequence": 1,  # Use integer, not MagicMock
                    "type": doc_type,
                    "doc-status": "ACTIVE",
                    "mitigates": ["test-risk"] if doc_type == "mitigation" else [],
                }
            }

        mock_service.get_document.side_effect = mock_get_document

        with patch(
            "finos_mcp.tools.listing.get_content_service", return_value=mock_service
        ):
            result = await handle_listing_tools("list_all_mitigations", {})

            assert len(result) == 1
            assert result[0].type == "text"

            # Parse and validate result
            listing_results = json.loads(result[0].text)
            assert isinstance(listing_results, list)
            assert len(listing_results) > 0  # Should have mitigation entries

    @pytest.mark.asyncio
    async def test_list_all_risks(self):
        """Test listing all risks."""
        # Mock the content service
        mock_service = AsyncMock()

        # Create a list of mock returns for different calls
        def mock_get_document(doc_type, filename):
            return {
                "metadata": {
                    "title": f"Test {doc_type.capitalize()}",
                    "sequence": 10,  # Use integer, not MagicMock
                    "type": doc_type,
                    "doc-status": "ACTIVE",
                    "related_risks": [],
                }
            }

        mock_service.get_document.side_effect = mock_get_document

        with patch(
            "finos_mcp.tools.listing.get_content_service", return_value=mock_service
        ):
            result = await handle_listing_tools("list_all_risks", {})

            assert len(result) == 1
            assert result[0].type == "text"

            # Parse and validate result
            listing_results = json.loads(result[0].text)
            assert isinstance(listing_results, list)


@pytest.mark.unit
class TestSystemTools:
    """Test system tools functionality."""

    @pytest.mark.asyncio
    async def test_get_service_diagnostics_cache_stats(self):
        """Test getting cache statistics."""
        # Mock the content service
        mock_service = AsyncMock()
        mock_service.get_service_diagnostics.return_value = {
            "cache_statistics": {"hits": 100, "misses": 10, "hit_rate": 0.909}
        }

        with patch(
            "finos_mcp.tools.system.get_content_service", return_value=mock_service
        ):
            result = await handle_system_tools("get_cache_stats", {})

            assert len(result) == 1
            assert result[0].type == "text"

            # Parse and validate result
            cache_stats = json.loads(result[0].text)
            assert "hits" in cache_stats
            assert "misses" in cache_stats

    @pytest.mark.asyncio
    async def test_get_service_health(self):
        """Test getting service health."""
        # Mock the content service
        mock_service = AsyncMock()
        mock_health = MagicMock()
        mock_health.to_dict.return_value = {
            "status": "healthy",
            "success_rate": 0.95,
            "total_requests": 1000,
        }
        mock_service.get_health_status.return_value = mock_health

        with patch(
            "finos_mcp.tools.system.get_content_service", return_value=mock_service
        ):
            result = await handle_system_tools("get_service_health", {})

            assert len(result) == 1
            assert result[0].type == "text"

            # Parse and validate result
            health_status = json.loads(result[0].text)
            assert health_status["status"] == "healthy"
            assert health_status["success_rate"] == 0.95

    @pytest.mark.asyncio
    async def test_reset_service_health(self):
        """Test resetting service health."""
        # Mock the content service
        mock_service = AsyncMock()
        mock_service.start_time = 1234567890.0

        with patch(
            "finos_mcp.tools.system.get_content_service", return_value=mock_service
        ):
            result = await handle_system_tools("reset_service_health", {})

            assert len(result) == 1
            assert result[0].type == "text"

            # Parse and validate result
            reset_result = json.loads(result[0].text)
            assert reset_result["status"] == "success"
            assert "reset" in reset_result["message"]


@pytest.mark.unit
class TestInputValidation:
    """Test Pydantic input validation across all tools."""

    @pytest.mark.asyncio
    async def test_invalid_tool_arguments(self):
        """Test that invalid arguments are properly rejected."""
        # Test cases for different validation errors
        test_cases: list[tuple[str, dict]] = [
            # Search tools - missing required field
            ("search_mitigations", {}),  # Missing "query"
            ("search_risks", {}),  # Missing "query"
            # Details tools - missing required field
            ("get_mitigation_details", {}),  # Missing "mitigation_id"
            ("get_risk_details", {}),  # Missing "risk_id"
        ]

        for tool_name, invalid_args in test_cases:
            with pytest.raises(
                (ValueError, TypeError)
            ):  # Should raise validation error
                await handle_tool_call(tool_name, invalid_args)

    @pytest.mark.asyncio
    async def test_valid_empty_arguments(self):
        """Test tools that accept empty arguments."""
        # Mock the content service for tools that need it
        mock_service = AsyncMock()
        mock_service.get_service_diagnostics.return_value = {"cache_statistics": {}}
        mock_health = MagicMock()
        mock_health.to_dict.return_value = {"status": "healthy"}
        mock_service.get_health_status.return_value = mock_health
        mock_service.start_time = 1234567890.0

        # Mock document returns with proper data types
        def mock_get_document(doc_type, filename):
            return {
                "metadata": {
                    "title": f"Test {doc_type.capitalize()}",
                    "sequence": 1,  # Use integer, not MagicMock
                    "type": doc_type,
                    "doc-status": "ACTIVE",
                    "mitigates": [] if doc_type == "mitigation" else None,
                    "related_risks": [] if doc_type == "risk" else None,
                }
            }

        mock_service.get_document.side_effect = mock_get_document

        # Tools that should accept empty arguments
        empty_arg_tools = [
            "list_all_mitigations",
            "list_all_risks",
            "get_cache_stats",
            "get_service_health",
            "get_service_metrics",
            "reset_service_health",
        ]

        with (
            patch(
                "finos_mcp.tools.listing.get_content_service", return_value=mock_service
            ),
            patch(
                "finos_mcp.tools.system.get_content_service", return_value=mock_service
            ),
        ):
            for tool_name in empty_arg_tools:
                # These should not raise validation errors
                result = await handle_tool_call(tool_name, {})
                assert len(result) >= 1
                assert result[0].type == "text"
