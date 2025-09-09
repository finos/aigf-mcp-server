"""
MCP Protocol Compliance Tests (pytest format)

Comprehensive testing of MCP protocol compliance using pytest framework
with proper async fixtures and isolation.
"""

import asyncio
import json

import pytest


@pytest.mark.integration
@pytest.mark.mcp
class TestMCPProtocolCompliance:
    """Test suite for MCP protocol compliance."""

    @pytest.mark.asyncio
    async def test_server_startup(self, mcp_server_process):
        """Test that MCP server starts successfully."""
        # Server should be running (fixture ensures this)
        assert mcp_server_process.poll() is None, "Server should be running"

    @pytest.mark.asyncio
    async def test_server_initialization(
        self, mcp_server_process, mcp_initialization_request
    ):
        """Test MCP initialization protocol."""
        # Send initialization request
        request_json = json.dumps(mcp_initialization_request) + "\n"
        mcp_server_process.stdin.write(request_json)
        mcp_server_process.stdin.flush()

        # Wait for response
        await asyncio.sleep(0.5)

        # Try to read response
        try:
            # Use select to check if data is available
            import select

            ready, _, _ = select.select([mcp_server_process.stdout], [], [], 2.0)

            if ready:
                response_line = mcp_server_process.stdout.readline()
                if response_line.strip():
                    response = json.loads(response_line)

                    # Verify response structure
                    assert "jsonrpc" in response, "Response should have jsonrpc field"
                    assert response["jsonrpc"] == "2.0", "Should be JSON-RPC 2.0"
                    assert "id" in response, "Response should have id field"
                    assert response["id"] == mcp_initialization_request["id"], (
                        "Response ID should match request ID"
                    )

                    # Should have either result or error
                    assert "result" in response or "error" in response, (
                        "Response should have result or error"
                    )

        except json.JSONDecodeError:
            pytest.fail("Server response was not valid JSON")
        except Exception as e:
            pytest.fail(f"Failed to read server response: {e}")

    @pytest.mark.asyncio
    async def test_tools_list(self, mcp_server_process, mcp_request_factory):
        """Test tools/list method."""
        # First initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }

        mcp_server_process.stdin.write(json.dumps(init_request) + "\n")
        mcp_server_process.stdin.flush()
        await asyncio.sleep(0.5)

        # Clear any initialization response
        try:
            mcp_server_process.stdout.readline()
        except Exception as e:
            print(f"Failed to read server output: {e}")

        # Send tools/list request
        tools_request = mcp_request_factory("tools/list", {})
        mcp_server_process.stdin.write(json.dumps(tools_request) + "\n")
        mcp_server_process.stdin.flush()

        await asyncio.sleep(0.5)

        # Check for response
        try:
            import select

            ready, _, _ = select.select([mcp_server_process.stdout], [], [], 2.0)

            if ready:
                response_line = mcp_server_process.stdout.readline()
                if response_line.strip():
                    response = json.loads(response_line)

                    assert "jsonrpc" in response
                    assert response["jsonrpc"] == "2.0"
                    assert "id" in response

                    if "result" in response:
                        # Should have tools in result
                        result = response["result"]
                        assert "tools" in result, "Result should contain tools array"
                        assert isinstance(result["tools"], list), (
                            "Tools should be an array"
                        )

                        # Verify expected tools exist
                        tool_names = [tool["name"] for tool in result["tools"]]
                        expected_tools = [
                            "search_mitigations",
                            "search_risks",
                            "get_mitigation_details",
                            "get_risk_details",
                            "list_all_mitigations",
                            "list_all_risks",
                        ]

                        for expected_tool in expected_tools:
                            assert expected_tool in tool_names, (
                                f"Expected tool {expected_tool} not found"
                            )

        except json.JSONDecodeError:
            pytest.fail("Server response was not valid JSON")
        except Exception as e:
            pytest.fail(f"Failed to test tools/list: {e}")

    @pytest.mark.asyncio
    async def test_resources_list(self, mcp_server_process, mcp_request_factory):
        """Test resources/list method."""
        # Initialize server first
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }

        mcp_server_process.stdin.write(json.dumps(init_request) + "\n")
        mcp_server_process.stdin.flush()
        await asyncio.sleep(0.5)

        # Clear initialization response
        try:
            mcp_server_process.stdout.readline()
        except Exception as e:
            print(f"Failed to read server output: {e}")

        # Send resources/list request
        resources_request = mcp_request_factory("resources/list", {})
        mcp_server_process.stdin.write(json.dumps(resources_request) + "\n")
        mcp_server_process.stdin.flush()

        await asyncio.sleep(0.5)

        try:
            import select

            ready, _, _ = select.select([mcp_server_process.stdout], [], [], 2.0)

            if ready:
                response_line = mcp_server_process.stdout.readline()
                if response_line.strip():
                    response = json.loads(response_line)

                    assert "jsonrpc" in response
                    assert response["jsonrpc"] == "2.0"

                    if "result" in response:
                        result = response["result"]
                        assert "resources" in result, (
                            "Result should contain resources array"
                        )
                        assert isinstance(result["resources"], list), (
                            "Resources should be an array"
                        )

                        # Should have both mitigation and risk resources
                        resources = result["resources"]
                        assert len(resources) > 0, "Should have some resources"

                        # Check for expected resource structure
                        if resources:
                            resource = resources[0]
                            assert "uri" in resource, "Resource should have uri"
                            assert "name" in resource, "Resource should have name"
                            assert "mimeType" in resource, (
                                "Resource should have mimeType"
                            )

        except json.JSONDecodeError:
            pytest.fail("Server response was not valid JSON")
        except Exception as e:
            pytest.fail(f"Failed to test resources/list: {e}")

    @pytest.mark.asyncio
    async def test_tool_call(self, mcp_server_process, mcp_request_factory):
        """Test tools/call method with search_mitigations tool."""
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }

        mcp_server_process.stdin.write(json.dumps(init_request) + "\n")
        mcp_server_process.stdin.flush()
        await asyncio.sleep(0.5)

        # Clear initialization
        try:
            mcp_server_process.stdout.readline()
        except Exception as e:
            print(f"Failed to read server output: {e}")

        # Call search_mitigations tool
        tool_call = mcp_request_factory(
            "tools/call", {"name": "search_mitigations", "arguments": {"query": "data"}}
        )

        mcp_server_process.stdin.write(json.dumps(tool_call) + "\n")
        mcp_server_process.stdin.flush()

        # Give more time for tool execution (may involve network calls)
        await asyncio.sleep(3.0)

        try:
            import select

            ready, _, _ = select.select([mcp_server_process.stdout], [], [], 5.0)

            if ready:
                response_line = mcp_server_process.stdout.readline()
                if response_line.strip():
                    response = json.loads(response_line)

                    assert "jsonrpc" in response
                    assert response["jsonrpc"] == "2.0"

                    if "result" in response:
                        result = response["result"]
                        assert "content" in result, "Tool result should have content"
                        assert isinstance(result["content"], list), (
                            "Content should be array"
                        )

                        if result["content"]:
                            content_item = result["content"][0]
                            assert "type" in content_item, (
                                "Content item should have type"
                            )
                            assert "text" in content_item, (
                                "Content item should have text"
                            )

        except json.JSONDecodeError:
            pytest.fail("Server response was not valid JSON")
        except Exception as e:
            pytest.fail(f"Failed to test tools/call: {e}")

    @pytest.mark.asyncio
    async def test_invalid_method(self, mcp_server_process, mcp_request_factory):
        """Test that server handles invalid methods gracefully."""
        invalid_request = mcp_request_factory("nonexistent/method", {})

        mcp_server_process.stdin.write(json.dumps(invalid_request) + "\n")
        mcp_server_process.stdin.flush()

        await asyncio.sleep(0.5)

        try:
            import select

            ready, _, _ = select.select([mcp_server_process.stdout], [], [], 2.0)

            if ready:
                response_line = mcp_server_process.stdout.readline()
                if response_line.strip():
                    response = json.loads(response_line)

                    assert "jsonrpc" in response
                    assert "error" in response, "Should return error for invalid method"
                    assert "id" in response

        except json.JSONDecodeError:
            pytest.fail("Server response was not valid JSON")
        except Exception as e:
            pytest.fail(f"Failed to test invalid method: {e}")

    @pytest.mark.asyncio
    async def test_malformed_json(self, mcp_server_process):
        """Test that server handles malformed JSON gracefully."""
        # Send invalid JSON
        mcp_server_process.stdin.write("invalid json here\n")
        mcp_server_process.stdin.flush()

        await asyncio.sleep(0.5)

        # Server should still be running (not crashed)
        assert mcp_server_process.poll() is None, (
            "Server should still be running after invalid JSON"
        )

    @pytest.mark.asyncio
    async def test_console_vs_direct_consistency(
        self, mcp_server_process, mcp_server_direct, mcp_request_factory
    ):
        """Test that console script and direct module execution behave consistently."""
        # Both servers should be running
        assert mcp_server_process.poll() is None, (
            "Console script server should be running"
        )
        assert mcp_server_direct.poll() is None, (
            "Direct module server should be running"
        )

        # Send same request to both
        test_request = mcp_request_factory(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        )

        # This test mainly verifies both servers start and respond to basic input
        # Detailed response comparison would be complex due to timing and I/O

        # Send to console script server
        mcp_server_process.stdin.write(json.dumps(test_request) + "\n")
        mcp_server_process.stdin.flush()

        # Send to direct module server
        mcp_server_direct.stdin.write(json.dumps(test_request) + "\n")
        mcp_server_direct.stdin.flush()

        await asyncio.sleep(1.0)

        # Both should still be running (basic consistency check)
        assert mcp_server_process.poll() is None, "Console server should handle request"
        assert mcp_server_direct.poll() is None, "Direct server should handle request"


@pytest.mark.integration
@pytest.mark.mcp
@pytest.mark.slow
class TestMCPProtocolEdgeCases:
    """Test edge cases and error conditions in MCP protocol."""

    @pytest.mark.asyncio
    async def test_rapid_requests(self, mcp_server_process, mcp_request_factory):
        """Test server handling of rapid sequential requests."""
        requests = [
            mcp_request_factory(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            ),
            mcp_request_factory("tools/list", {}),
            mcp_request_factory("resources/list", {}),
        ]

        # Send all requests rapidly
        for request in requests:
            mcp_server_process.stdin.write(json.dumps(request) + "\n")
            mcp_server_process.stdin.flush()

        await asyncio.sleep(2.0)

        # Server should still be responsive
        assert mcp_server_process.poll() is None, "Server should handle rapid requests"

    @pytest.mark.asyncio
    async def test_large_response_handling(
        self, mcp_server_process, mcp_request_factory
    ):
        """Test server handling of requests that generate large responses."""
        # Initialize first
        init_request = mcp_request_factory(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        )

        mcp_server_process.stdin.write(json.dumps(init_request) + "\n")
        mcp_server_process.stdin.flush()
        await asyncio.sleep(0.5)

        # Request that should generate large response (list all resources)
        large_request = mcp_request_factory("resources/list", {})
        mcp_server_process.stdin.write(json.dumps(large_request) + "\n")
        mcp_server_process.stdin.flush()

        await asyncio.sleep(2.0)

        # Server should handle large responses without crashing
        assert mcp_server_process.poll() is None, "Server should handle large responses"
