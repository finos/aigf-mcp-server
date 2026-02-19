#!/usr/bin/env python3
"""Optional live HTTP auth integration test for FastMCP boundary security.

Run with:
    FINOS_RUN_AUTH_HTTP_TEST=1 ./venv/bin/pytest -q tests/integration/test_auth_http_transport.py
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
from authlib.jose import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FINOS_RUN_AUTH_HTTP_TEST") != "1",
        reason="Set FINOS_RUN_AUTH_HTTP_TEST=1 to run live auth HTTP tests",
    ),
]


def _is_port_open(host: str, port: int) -> bool:
    """Return True when TCP endpoint is accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _wait_for_port(host: str, port: int, timeout_seconds: float = 15.0) -> None:
    """Wait until the server is listening on host:port."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _is_port_open(host, port):
            return
        time.sleep(0.2)
    raise TimeoutError(
        f"Server did not start on {host}:{port} within {timeout_seconds}s"
    )


def _generate_rsa_keys() -> tuple[str, bytes]:
    """Generate temporary RSA keypair for JWT signing and verification."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return public_pem.decode("utf-8"), private_pem


def _issue_token(
    private_pem: bytes,
    issuer: str,
    audience: str,
    scope: str,
    ttl_seconds: int = 1800,
) -> str:
    """Issue RS256 token for auth test cases."""
    now = int(time.time())
    claims = {
        "sub": "integration-test-client",
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + ttl_seconds,
        "scope": scope,
    }
    token = jwt.encode({"alg": "RS256", "typ": "JWT"}, claims, private_pem)
    return token.decode("utf-8")


async def _invoke_health(url: str, headers: dict[str, str] | None = None) -> dict:
    """Initialize MCP session and call get_service_health over HTTP."""
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result: CallToolResult = await session.call_tool("get_service_health", {})
            assert result.content, "Expected tool response content"
            first = result.content[0]
            assert isinstance(first, TextContent), "Expected text tool result content"
            payload = json.loads(first.text)
            assert isinstance(payload, dict)
            return payload


@pytest.mark.asyncio
async def test_http_auth_enforcement_with_scope_validation() -> None:
    """Validate unauthorized, forbidden, and authorized HTTP auth flows."""
    host = "127.0.0.1"
    port = int(os.getenv("FINOS_AUTH_HTTP_TEST_PORT", "18081"))
    url = f"http://{host}:{port}/mcp"
    issuer = "https://auth.integration.local"
    audience = "finos-mcp-server"
    required_scope = "governance:read"

    public_key_pem, private_key_pem = _generate_rsa_keys()
    log_path = Path(tempfile.gettempdir()) / f"finos_mcp_auth_http_{port}.log"

    env = os.environ.copy()
    env.update(
        {
            "FINOS_MCP_MCP_TRANSPORT": "http",
            "FINOS_MCP_MCP_HOST": host,
            "FINOS_MCP_MCP_PORT": str(port),
            "FINOS_MCP_MCP_AUTH_ENABLED": "true",
            "FINOS_MCP_MCP_AUTH_PUBLIC_KEY": public_key_pem,
            "FINOS_MCP_MCP_AUTH_ISSUER": issuer,
            "FINOS_MCP_MCP_AUTH_AUDIENCE": audience,
            "FINOS_MCP_MCP_AUTH_REQUIRED_SCOPES": required_scope,
        }
    )

    process = subprocess.Popen(
        [sys.executable, "-m", "finos_mcp.fastmcp_main"],
        env=env,
        stdout=log_path.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )

    try:
        _wait_for_port(host, port, timeout_seconds=20.0)

        # No token should fail.
        with pytest.raises(Exception):
            await _invoke_health(url)

        # Token missing required scope should fail.
        insufficient_scope_token = _issue_token(
            private_key_pem, issuer, audience, scope="governance:write"
        )
        with pytest.raises(Exception):
            await _invoke_health(
                url,
                headers={"Authorization": f"Bearer {insufficient_scope_token}"},
            )

        # Fully valid token should pass.
        valid_token = _issue_token(
            private_key_pem, issuer, audience, scope="governance:read governance:write"
        )
        payload = await _invoke_health(
            url,
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert payload["status"] in {"healthy", "degraded", "failing", "critical"}
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
