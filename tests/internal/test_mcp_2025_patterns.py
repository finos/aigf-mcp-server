"""
Tests for MCP 2025 patterns implementation.
Ensures backward compatibility with stdio while adding new capabilities.
"""

from unittest.mock import patch

import pytest

from finos_mcp.internal.mcp_2025_patterns import (
    MCP2025Server,
    OAuth21Handler,
    ProtocolNegotiator,
    StreamableHTTPTransport,
    ToolOutputSchema,
)


class TestProtocolNegotiator:
    """Test protocol negotiation between stdio and streamable HTTP."""

    def test_stdio_default(self):
        """Test that stdio remains the default protocol."""
        negotiator = ProtocolNegotiator()
        protocol = negotiator.negotiate_protocol({})

        assert protocol == "stdio"
        assert negotiator.supports_stdio is True

    def test_streamable_http_negotiation(self):
        """Test negotiating streamable HTTP when supported."""
        negotiator = ProtocolNegotiator()
        protocol = negotiator.negotiate_protocol(
            {"capabilities": {"transport": {"streamable_http": True}}}
        )

        # Should still default to stdio for compatibility
        assert protocol in ["stdio", "streamable_http"]
        assert negotiator.supports_streamable_http is True

    def test_both_protocols_supported(self):
        """Test that both protocols can be supported simultaneously."""
        negotiator = ProtocolNegotiator()

        assert negotiator.supports_stdio is True
        assert negotiator.can_support_streamable_http() is True


class TestStreamableHTTPTransport:
    """Test streamable HTTP transport implementation."""

    def test_transport_creation(self):
        """Test creating streamable HTTP transport."""
        transport = StreamableHTTPTransport(host="localhost", port=8080)

        assert transport.host == "localhost"
        assert transport.port == 8080
        assert transport.is_streaming is True

    @pytest.mark.asyncio
    async def test_backwards_compatibility_with_stdio(self):
        """Test that streamable HTTP can fallback to stdio behavior."""
        transport = StreamableHTTPTransport()

        # Should be able to handle traditional request/response
        request = {"method": "tools/list", "params": {}}
        response = await transport.handle_request(request, fallback_stdio=True)

        assert "result" in response or "error" in response

    @pytest.mark.asyncio
    async def test_streaming_response(self):
        """Test streaming response capability."""
        transport = StreamableHTTPTransport()

        async def mock_stream_handler():
            yield {"type": "progress", "progress": 0.5}
            yield {"type": "data", "content": "streaming data"}
            yield {"type": "complete", "result": "done"}

        transport.set_stream_handler(mock_stream_handler)

        stream = transport.create_stream()
        results = []
        async for chunk in stream:
            results.append(chunk)

        assert len(results) == 3
        assert results[0]["type"] == "progress"
        assert results[2]["type"] == "complete"

    def test_http_compatibility(self):
        """Test HTTP protocol compatibility."""
        transport = StreamableHTTPTransport()

        # Should accept standard HTTP methods
        assert transport.supports_method("GET") is True
        assert transport.supports_method("POST") is True
        assert transport.supports_header("content-type") is True


class TestToolOutputSchema:
    """Test tool output schema validation."""

    def test_basic_schema_validation(self):
        """Test basic schema validation."""
        schema = ToolOutputSchema(
            {
                "type": "object",
                "properties": {
                    "result": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["result"],
            }
        )

        # Valid output
        valid_output = {"result": "success", "confidence": 0.95}
        assert schema.validate(valid_output) is True

        # Invalid output
        invalid_output = {"confidence": 0.95}  # missing required 'result'
        assert schema.validate(invalid_output) is False

    def test_backward_compatibility_with_existing_tools(self):
        """Test that existing tools without schemas still work."""
        schema = ToolOutputSchema(None)  # No schema provided

        # Should accept any output when no schema is defined
        any_output = {"whatever": "format", "legacy": True}
        assert schema.validate(any_output) is True

    def test_enhanced_schema_features(self):
        """Test MCP 2025 enhanced schema features."""
        schema = ToolOutputSchema(
            {
                "type": "object",
                "properties": {
                    "data": {"type": "string"},
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "timestamp": {"type": "string", "format": "date-time"},
                        },
                    },
                },
                "additionalProperties": False,
            }
        )

        valid_output = {
            "data": "some content",
            "metadata": {"source": "test", "timestamp": "2025-01-01T00:00:00Z"},
        }

        assert schema.validate(valid_output) is True
        assert schema.extract_metadata(valid_output)["source"] == "test"

    def test_streaming_output_schema(self):
        """Test schema validation for streaming outputs."""
        stream_schema = ToolOutputSchema(
            {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["progress", "data", "complete"],
                    },
                    "content": {"type": "string"},
                    "progress": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["type"],
            }
        )

        progress_chunk = {"type": "progress", "progress": 0.3}
        data_chunk = {"type": "data", "content": "streaming content"}
        complete_chunk = {"type": "complete", "content": "final result"}

        assert stream_schema.validate(progress_chunk) is True
        assert stream_schema.validate(data_chunk) is True
        assert stream_schema.validate(complete_chunk) is True


class TestOAuth21Handler:
    """Test OAuth 2.1 authentication handler."""

    def test_oauth_handler_creation(self):
        """Test creating OAuth 2.1 handler."""
        handler = OAuth21Handler(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
        )

        assert handler.client_id == "test_client"
        assert handler.supports_pkce is True  # OAuth 2.1 requires PKCE

    def test_backwards_compatibility_with_existing_auth(self):
        """Test that existing authentication methods still work."""
        handler = OAuth21Handler(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
        )

        # Should still support basic auth for compatibility
        assert handler.supports_legacy_auth() is True

    @pytest.mark.asyncio
    async def test_pkce_flow(self):
        """Test PKCE (Proof Key for Code Exchange) flow."""
        handler = OAuth21Handler(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
        )

        # Generate PKCE challenge
        challenge = handler.generate_pkce_challenge()

        assert "code_challenge" in challenge
        assert "code_challenge_method" in challenge
        assert challenge["code_challenge_method"] == "S256"

    @pytest.mark.asyncio
    async def test_token_refresh(self):
        """Test automatic token refresh."""
        handler = OAuth21Handler(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
        )

        # Mock expired token
        handler.access_token = "expired_token"
        handler.refresh_token = "valid_refresh_token"
        handler.token_expires_at = 1640995200  # Past timestamp

        with patch.object(handler, "_refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new_token",
                "expires_in": 3600,
            }

            token = await handler.get_valid_token()
            assert token == "new_token"
            mock_refresh.assert_called_once()


class TestMCP2025Server:
    """Test MCP 2025 server with backward compatibility."""

    @pytest.mark.asyncio
    async def test_dual_protocol_support(self):
        """Test server supporting both stdio and streamable HTTP."""
        server = MCP2025Server()

        # Should support stdio (existing protocol)
        assert server.supports_stdio() is True

        # Should support streamable HTTP (new protocol)
        assert server.supports_streamable_http() is True

    @pytest.mark.asyncio
    async def test_stdio_request_handling(self):
        """Test that existing stdio requests still work."""
        server = MCP2025Server()

        # Traditional stdio request
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

        response = await server.handle_stdio_request(request)

        assert "jsonrpc" in response
        assert response["id"] == 1
        assert "result" in response or "error" in response

    @pytest.mark.asyncio
    async def test_streamable_http_request_handling(self):
        """Test new streamable HTTP request handling."""
        server = MCP2025Server()

        # Streamable HTTP request
        request = {
            "method": "tools/call",
            "params": {"name": "search_documents", "arguments": {"query": "test"}},
            "stream": True,
        }

        response = await server.handle_streamable_request(request)

        # Should return a stream or regular response
        assert response is not None

    @pytest.mark.asyncio
    async def test_protocol_auto_detection(self):
        """Test automatic protocol detection."""
        server = MCP2025Server()

        # stdio-style request
        stdio_request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

        protocol = server.detect_protocol(stdio_request)
        assert protocol == "stdio"

        # HTTP-style request
        http_request = {
            "method": "GET",
            "path": "/tools",
            "headers": {"accept": "application/json"},
        }

        protocol = server.detect_protocol(http_request)
        assert protocol == "http"

    @pytest.mark.asyncio
    async def test_enhanced_tool_capabilities(self):
        """Test enhanced tool capabilities with output schemas."""
        server = MCP2025Server()

        # Tool with output schema
        tool_config = {
            "name": "enhanced_search",
            "description": "Enhanced search with structured output",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "results": {"type": "array"},
                    "metadata": {"type": "object"},
                },
            },
        }

        server.register_enhanced_tool(tool_config)
        tools = server.list_tools()

        enhanced_tool = next(t for t in tools if t["name"] == "enhanced_search")
        assert "output_schema" in enhanced_tool

    def test_configuration_compatibility(self):
        """Test that existing configurations still work."""
        # Existing stdio configuration
        stdio_config = {"transport": "stdio", "tools": ["search", "details"]}

        server = MCP2025Server(config=stdio_config)
        assert server.transport_type == "stdio"

        # New configuration with multiple transports
        multi_config = {
            "transports": {
                "stdio": {"enabled": True},
                "streamable_http": {"enabled": True, "port": 8080},
            },
            "tools": ["search", "details"],
        }

        server2 = MCP2025Server(config=multi_config)
        assert server2.supports_stdio() is True
        assert server2.supports_streamable_http() is True


class TestIntegration:
    """Test integration between all MCP 2025 patterns."""

    @pytest.mark.asyncio
    async def test_end_to_end_streamable_with_oauth(self):
        """Test complete flow with streamable HTTP and OAuth 2.1."""
        # Setup OAuth handler
        oauth_handler = OAuth21Handler(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
        )

        # Setup server with streamable transport
        server = MCP2025Server()
        server.set_auth_handler(oauth_handler)

        # Setup transport
        transport = StreamableHTTPTransport()
        server.add_transport("streamable_http", transport)

        # Should maintain existing functionality
        assert server.supports_stdio() is True

        # Should add new capabilities
        assert server.has_auth_handler() is True

    @pytest.mark.asyncio
    async def test_graceful_fallback_to_stdio(self):
        """Test graceful fallback to stdio when new features unavailable."""
        server = MCP2025Server()

        # Client that only supports stdio
        client_capabilities = {"transport": "stdio"}

        negotiated = server.negotiate_capabilities(client_capabilities)

        # Should fallback to stdio
        assert negotiated["transport"] == "stdio"
        assert "streamable_http" not in negotiated

        # But server should still work
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

        response = await server.handle_request(request)
        assert response["id"] == 1
