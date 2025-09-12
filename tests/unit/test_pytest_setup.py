"""
Basic pytest validation tests.

Simple tests to verify core functionality works.
"""

import asyncio

import pytest


@pytest.mark.unit
class TestBasicFunctionality:
    """Test basic functionality."""

    def test_pytest_working(self) -> None:
        """Basic test to verify pytest is functioning."""
        assert True

    def test_package_import(self) -> None:
        """Test package can be imported."""
        import finos_mcp

        # Test basic import
        assert hasattr(finos_mcp, "get_version")
        assert hasattr(finos_mcp, "get_package_info")

        # Test version
        version = finos_mcp.get_version()
        assert isinstance(version, str)
        assert len(version) > 0

    @pytest.mark.asyncio
    async def test_async_support(self) -> None:
        """Test that async tests work."""
        await asyncio.sleep(0.01)
        assert True

    def test_mcp_request_factory(self, mcp_request_factory) -> None:
        """Test MCP request factory fixture."""
        request = mcp_request_factory("test_method", {"param": "value"})
        assert request["jsonrpc"] == "2.0"
        assert request["method"] == "test_method"
        assert request["params"] == {"param": "value"}
        assert "id" in request
