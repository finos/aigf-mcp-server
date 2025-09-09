"""
Pytest setup validation tests.

Basic tests to verify pytest configuration and fixtures are working correctly.
"""

import asyncio
from typing import Any

import pytest


@pytest.mark.unit
class TestPytestSetup:
    """Test that pytest setup is working correctly."""

    def test_pytest_working(self) -> None:
        """Basic test to verify pytest is functioning."""
        assert True, "Pytest basic functionality working"

    def test_package_import(self, package_info: dict[str, Any]) -> None:
        """Test package import using fixture."""
        assert package_info["importable"], (
            f"Package should be importable: {package_info.get('import_error', '')}"
        )
        # Verify version is properly set (should not be "unknown")
        assert package_info["version"] != "unknown", (
            f"Version should not be 'unknown', got {package_info['version']}"
        )
        # Check for valid version format (semantic versioning)
        assert "." in package_info["version"], (
            f"Version should contain dots for proper semantic versioning, got {package_info['version']}"
        )

    def test_package_functions(self) -> None:
        """Test package utility functions."""
        import finos_mcp

        # Test get_version function
        version = finos_mcp.get_version()
        assert version != "unknown", f"Version should not be 'unknown', got {version}"
        assert "." in version, (
            f"Version should contain dots for proper semantic versioning, got {version}"
        )

        # Test get_package_info function
        info = finos_mcp.get_package_info()
        assert info["name"] == "finos_mcp"
        assert info["version"] != "unknown", (
            f"Version should not be 'unknown', got {info['version']}"
        )
        assert "." in info["version"], (
            f"Version should contain dots for proper semantic versioning, got {info['version']}"
        )
        assert "author" in info
        assert "email" in info
        assert "license" in info

    def test_temp_dir_fixture(self, temp_dir: Any) -> None:
        """Test temporary directory fixture."""
        assert temp_dir.exists(), "Temporary directory should exist"
        assert temp_dir.is_dir(), "Should be a directory"

        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        assert test_file.exists(), "Should be able to create files in temp dir"

    @pytest.mark.asyncio
    async def test_async_support(self) -> None:
        """Test that async tests work."""
        await asyncio.sleep(0.1)
        assert True, "Async test support working"

    def test_fixtures_available(
        self, mcp_request_factory: Any, sample_mcp_requests: Any
    ) -> None:
        """Test that MCP fixtures are available."""
        # Test request factory
        request = mcp_request_factory("test_method", {"param": "value"})
        assert request["jsonrpc"] == "2.0"
        assert request["method"] == "test_method"
        assert request["params"] == {"param": "value"}
        assert "id" in request

        # Test sample requests
        assert "initialize" in sample_mcp_requests
        assert "list_tools" in sample_mcp_requests
        assert sample_mcp_requests["initialize"]["method"] == "initialize"


@pytest.mark.integration
@pytest.mark.console
class TestConsoleFunctionality:
    """Test console script functionality using pytest fixtures."""

    def test_console_script_exists(self, console_script_runner: Any) -> None:
        """Test that console script exists and is runnable."""
        result = console_script_runner(["which", "finos-mcp"], timeout=5.0)
        assert result.returncode == 0, f"Console script not found: {result.stderr}"
        assert "finos-mcp" in result.stdout, (
            "Console script path should contain finos-mcp"
        )

    def test_console_script_startup(self, console_script_runner: Any) -> None:
        """Test that console script starts without immediate errors."""
        result = console_script_runner(["finos-mcp"], timeout=2.0, input_data="")

        # Should timeout (not crash immediately)
        assert result.returncode == -1 or result.returncode == 0, (
            "Console script should start successfully or timeout"
        )

        # Should not have coroutine errors
        assert "coroutine" not in result.stderr.lower(), (
            f"Should not have coroutine errors: {result.stderr}"
        )
        assert "never awaited" not in result.stderr.lower(), (
            f"Should not have async errors: {result.stderr}"
        )


@pytest.mark.unit
class TestErrorScenarios:
    """Test error handling scenarios using pytest fixtures."""

    def test_error_scenarios_fixture(self, error_scenarios: Any) -> None:
        """Test that error scenarios fixture provides expected data."""
        assert "invalid_json" in error_scenarios
        assert "missing_jsonrpc" in error_scenarios
        assert "invalid_method" in error_scenarios
        assert "malformed_params" in error_scenarios

        # Verify structure
        invalid_method = error_scenarios["invalid_method"]
        assert invalid_method["jsonrpc"] == "2.0"
        assert invalid_method["method"] == "nonexistent_method"
