#!/usr/bin/env python3
"""Optional live HTTP auth integration test for FastMCP boundary security.

Run with:
    FINOS_RUN_AUTH_HTTP_TEST=1 ./venv/bin/pytest -q tests/integration/test_auth_http_transport.py
"""

from __future__ import annotations

import datetime
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx2
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from joserfc import jwt
from joserfc.jwk import RSAKey
from mcp import MCPError
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
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
    kid: str | None = None,
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
    header = {"alg": "RS256", "typ": "JWT"}
    if kid:
        header["kid"] = kid
    return jwt.encode(header, claims, RSAKey.import_key(private_pem))


def _self_signed_localhost_cert(directory: Path) -> tuple[Path, Path]:
    """Write a self-signed certificate and key for ``localhost``.

    The JWKS endpoint has to speak real TLS for this test to mean anything. If
    it served plain HTTP, the unprotected run would fail the TLS handshake and
    record zero requests -- exactly what a successful SSRF block looks like --
    so the assertion would hold whether or not the guard was doing anything.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path = directory / "jwks-cert.pem"
    key_path = directory / "jwks-key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class _JwksServer:
    """Loopback HTTPS JWKS endpoint that records every request it receives.

    Stands in for an internal identity provider. The request log is what proves
    whether the server under test actually dialled the internal address, which a
    401 on its own does not tell you.
    """

    def __init__(
        self, jwks_document: dict[str, Any], cert_path: Path, key_path: Path
    ) -> None:
        payload = json.dumps(jwks_document).encode("utf-8")
        self.requests: list[str] = []
        server_self = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                server_self.requests.append(self.path)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args: object) -> None:
                """Silence the default stderr access log."""

        self._httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cert_path), str(key_path))
        self._httpd.socket = context.wrap_socket(self._httpd.socket, server_side=True)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self) -> _JwksServer:
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)

    @property
    def uri(self) -> str:
        """JWKS URI as an operator would configure it for an internal IdP.

        ``localhost`` is a name, not an IP literal, so this passes the DNS-free
        startup check and the server starts. It resolves to loopback, so the
        runtime SSRF guard is what refuses it -- which is the code path under
        test here.
        """
        return (
            f"https://localhost:{self._httpd.server_address[1]}/.well-known/jwks.json"
        )


def _jwks_document(public_key_pem: str, kid: str) -> dict[str, Any]:
    """Build a JWKS document for an RSA public key."""
    jwk = RSAKey.import_key(
        public_key_pem.encode("utf-8"),
        {"kid": kid, "use": "sig", "alg": "RS256"},
    )
    return {"keys": [jwk.as_dict()]}


async def _assert_health_rejected(
    url: str, headers: dict[str, str] | None, expected_status: int
) -> None:
    """Assert the health call is rejected with a specific HTTP status.

    Since mcp 2.x the client turns an HTTP error that carries no JSON-RPC body
    into a generic ``MCPError`` and drops the status, so the status is read off
    the wire instead, from the HTTP client's own responses. Asserting on that status rather than on "some
    exception happened" is what makes this a real check: a bare
    ``pytest.raises(Exception)`` is satisfied just as well by a connection
    refusal or a typo in the URL as by a rejected token, so it would pass
    against a server that never started.
    """
    statuses: list[int] = []
    with pytest.RaisesGroup(MCPError, flatten_subgroups=True):
        await _invoke_health(url, headers=headers, statuses=statuses)

    assert statuses == [expected_status], (
        f"Expected the request to be rejected with {expected_status}, got {statuses}"
    )


async def _invoke_health(
    url: str,
    headers: dict[str, str] | None = None,
    statuses: list[int] | None = None,
) -> dict[str, Any]:
    """Initialize MCP session and call get_service_health over HTTP.

    ``statuses``, when given, collects the HTTP status of every response.
    """

    async def record(response: httpx2.Response) -> None:
        if statuses is not None:
            statuses.append(response.status_code)

    async with httpx2.AsyncClient(
        headers=headers, event_hooks={"response": [record]}
    ) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (
            read,
            write,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result: CallToolResult = await session.call_tool(
                    "get_service_health", {}
                )
                assert result.content, "Expected tool response content"
                first = result.content[0]
                assert isinstance(first, TextContent), (
                    "Expected text tool result content"
                )
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
            # The URL a client uses to reach this server. Here it is the bind
            # address because the test connects directly, with no proxy.
            "FINOS_MCP_MCP_AUTH_BASE_URL": f"http://{host}:{port}",
            # An http base URL is refused without it (#323, #341).
            "FINOS_MCP_ALLOW_INSECURE_HTTP": "true",
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

        # No token should be rejected at the transport with 401.
        await _assert_health_rejected(url, None, expected_status=401)

        # That 401 must tell the client where to sign in (#251): it names a
        # metadata document, and the document names this server and the
        # authorization server. Followed the way a client follows it, by
        # fetching the URL the challenge gives.
        async with httpx2.AsyncClient() as http_client:
            challenged = await http_client.post(url, json={})
            assert challenged.status_code == 401
            named = re.search(
                r'resource_metadata="([^"]+)"', challenged.headers["www-authenticate"]
            )
            assert named is not None, challenged.headers["www-authenticate"]
            document = await http_client.get(named.group(1))
        assert document.status_code == 200
        metadata = document.json()
        assert metadata["resource"] == url
        assert metadata["authorization_servers"] == [issuer]
        assert metadata["scopes_supported"] == [required_scope]

        # A correctly signed token that lacks the required scope must also be
        # rejected. FastMCP's auth middleware reports this as invalid_token with
        # status 401 rather than the 403 that RFC 6750 suggests for
        # insufficient_scope, so both denials look identical from the client.
        # The valid-token call below is what proves this rejection is caused by
        # the scope claim: it is the only field that differs between the two
        # tokens, and it succeeds.
        insufficient_scope_token = _issue_token(
            private_key_pem, issuer, audience, scope="governance:write"
        )
        await _assert_health_rejected(
            url,
            {"Authorization": f"Bearer {insufficient_scope_token}"},
            expected_status=401,
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


def _server_env(**overrides: str) -> dict[str, str]:
    """Build a child-process environment for the server under test."""
    env = os.environ.copy()
    env.update(overrides)
    return env


def _stop(process: subprocess.Popen[bytes]) -> None:
    """Terminate the server subprocess, killing it if it will not exit."""
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.mark.asyncio
async def test_jwks_ssrf_protection_blocks_an_internal_endpoint_end_to_end() -> None:
    """Drive the JWKS verifier branch of a real server over HTTP.

    Two runs against the *same* HTTPS JWKS endpoint on loopback, with the same
    key and the same token. The only difference is
    ``FINOS_MCP_ALLOW_INSECURE_JWKS_URI``:

    * default -- the call must be refused and the JWKS endpoint must record zero
      requests, i.e. the server never dialled the internal address at all;
    * opt-out -- the identical endpoint must be fetched and the identical token
      accepted through a real MCP client.

    Holding the URI fixed is what gives the negative case teeth. An earlier
    version of this test served the JWKS over plain HTTP: the unprotected run
    then died in the TLS handshake and also recorded zero requests, so the
    assertion passed with the fix reverted. Serving real TLS -- trusted by the
    child process via ``SSL_CERT_FILE`` -- means a zero count can only come from
    the SSRF guard.

    The URI is ``https://localhost:<port>``: a name rather than an IP literal,
    so it passes the DNS-free startup check and the server starts, and is then
    refused at fetch time when the name resolves to loopback. This exercises the
    runtime guard, not the startup one.
    """
    host = "127.0.0.1"
    port = int(os.getenv("FINOS_AUTH_HTTP_TEST_PORT", "18082"))
    url = f"http://{host}:{port}/mcp"
    issuer = "https://auth.integration.local"
    audience = "finos-mcp-server"
    required_scope = "governance:read"
    kid = "integration-jwks-key"

    public_key_pem, private_key_pem = _generate_rsa_keys()
    token = _issue_token(
        private_key_pem, issuer, audience, scope=required_scope, kid=kid
    )
    log_path = Path(tempfile.gettempdir()) / f"finos_mcp_jwks_ssrf_{port}.log"

    with tempfile.TemporaryDirectory() as tls_dir:
        cert_path, key_path = _self_signed_localhost_cert(Path(tls_dir))
        jwks_document = _jwks_document(public_key_pem, kid)

        with _JwksServer(jwks_document, cert_path, key_path) as jwks:
            base_env = {
                "FINOS_MCP_MCP_TRANSPORT": "http",
                "FINOS_MCP_MCP_HOST": host,
                "FINOS_MCP_MCP_PORT": str(port),
                "FINOS_MCP_MCP_AUTH_ENABLED": "true",
                "FINOS_MCP_MCP_AUTH_ISSUER": issuer,
                "FINOS_MCP_MCP_AUTH_AUDIENCE": audience,
                "FINOS_MCP_MCP_AUTH_REQUIRED_SCOPES": required_scope,
                "FINOS_MCP_MCP_AUTH_JWKS_URI": jwks.uri,
                # Makes the child trust the endpoint's self-signed certificate,
                # so the unprotected run really can complete the fetch.
                "SSL_CERT_FILE": str(cert_path),
            }

            # --- Negative case: SSRF protection on (the default) -----------
            blocked = subprocess.Popen(
                [sys.executable, "-m", "finos_mcp.fastmcp_main"],
                env=_server_env(**base_env),
                stdout=log_path.open("w", encoding="utf-8"),
                stderr=subprocess.STDOUT,
            )
            try:
                _wait_for_port(host, port, timeout_seconds=20.0)
                await _assert_health_rejected(
                    url, {"Authorization": f"Bearer {token}"}, expected_status=401
                )
                assert jwks.requests == [], (
                    "The server contacted the loopback JWKS endpoint despite "
                    f"SSRF protection being enabled: {jwks.requests}"
                )
            finally:
                _stop(blocked)

            # --- Positive control: SSRF protection explicitly disabled -----
            permitted = subprocess.Popen(
                [sys.executable, "-m", "finos_mcp.fastmcp_main"],
                env=_server_env(**base_env, FINOS_MCP_ALLOW_INSECURE_JWKS_URI="true"),
                stdout=log_path.open("a", encoding="utf-8"),
                stderr=subprocess.STDOUT,
            )
            try:
                _wait_for_port(host, port, timeout_seconds=20.0)
                payload = await _invoke_health(
                    url, headers={"Authorization": f"Bearer {token}"}
                )
                assert payload["status"] in {
                    "healthy",
                    "degraded",
                    "failing",
                    "critical",
                }
                assert jwks.requests, (
                    "The opt-out run never fetched the JWKS, so the blocked run "
                    "above proves nothing about the SSRF guard"
                )
            finally:
                _stop(permitted)


@pytest.mark.asyncio
async def test_startup_refuses_a_jwks_uri_the_guard_can_never_fetch() -> None:
    """A statically unfetchable JWKS URI must stop the server, not 401 silently.

    fastmcp reports the SSRF block at DEBUG and returns an ordinary 401, so
    without this check an operator upgrading with a plain-HTTP JWKS URI would
    see every token rejected and nothing in the log explaining why.
    """
    host = "127.0.0.1"
    port = int(os.getenv("FINOS_AUTH_HTTP_TEST_PORT", "18083"))
    log_path = Path(tempfile.gettempdir()) / f"finos_mcp_jwks_startup_{port}.log"

    process = subprocess.Popen(
        [sys.executable, "-m", "finos_mcp.fastmcp_main"],
        env=_server_env(
            FINOS_MCP_MCP_TRANSPORT="http",
            FINOS_MCP_MCP_HOST=host,
            FINOS_MCP_MCP_PORT=str(port),
            FINOS_MCP_MCP_AUTH_ENABLED="true",
            FINOS_MCP_MCP_AUTH_ISSUER="https://auth.integration.local",
            FINOS_MCP_MCP_AUTH_AUDIENCE="finos-mcp-server",
            FINOS_MCP_MCP_AUTH_JWKS_URI="http://auth.integration.local/jwks.json",
        ),
        stdout=log_path.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    try:
        exit_code = process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        _stop(process)
        pytest.fail(
            "The server started with a JWKS URI that SSRF-safe fetching can "
            "never reach; it should have refused to start"
        )

    assert exit_code != 0, "Startup validation should have failed"
    log_text = log_path.read_text(encoding="utf-8")
    assert "FINOS_MCP_ALLOW_INSECURE_JWKS_URI" in log_text, log_text
    assert not _is_port_open(host, port), "The server should not be listening"
