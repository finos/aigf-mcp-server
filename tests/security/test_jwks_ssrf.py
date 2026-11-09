"""Tests for SSRF hardening of the JWKS fetch on the MCP auth path.

The defect these cover: ``_build_auth_provider`` handed the operator-supplied
``FINOS_MCP_MCP_AUTH_JWKS_URI`` to ``JWTVerifier`` with fastmcp's default
``ssrf_safe=False``, so every token verification fetched that URI with an
unrestricted ``httpx`` client. A mistyped or attacker-influenced JWKS URI could
therefore reach loopback, link-local (cloud metadata) and private addresses --
and the document it returns is what decides which signatures the server trusts.

Two things make these tests worth more than a config assertion:

* The fetch is lazy. ``JWTVerifier`` stores ``ssrf_safe`` at construction and
  only acts on it inside ``_fetch_jwks``, at the first token verification. A
  test that only reads back the constructed attribute would pass against a
  build where the flag reaches the object but changes nothing.
* The block is silent. fastmcp logs the ``SSRFError`` at DEBUG, re-raises it as
  a generic ``ValueError`` and ``load_access_token`` turns that into ``None``,
  i.e. an ordinary 401. Asserting "the token was rejected" is satisfied just as
  well by a malformed token, an unreachable port or a typo in the URI.

So the assertion that carries the weight here is the *request count* on a real
loopback JWKS server: SSRF-safe mode must leave it at zero, having never dialled
the internal address at all. The opt-out case is the paired positive control --
same server, same key, same token, one setting different, and it must reach the
server and mint a valid ``AccessToken``. Without it a zero-hit count would also
be produced by a broken harness that never worked in either mode.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastmcp.server.auth import JWTVerifier
from joserfc import jwt
from joserfc.jwk import RSAKey

from finos_mcp.app import _build_auth_provider
from finos_mcp.config import Settings

ISSUER = "https://issuer.jwks-ssrf.test"
AUDIENCE = "finos-mcp-server"
SUBJECT = "jwks-ssrf-test-client"
SCOPE = "governance:read"
KEY_ID = "jwks-ssrf-test-key"

# A JWKS URI on a routable public host. Used where the test needs a URI that the
# SSRF guard has no static reason to reject; nothing is ever fetched from it.
PUBLIC_JWKS_URI = "https://auth.example.com/.well-known/jwks.json"


class _JwksServer:
    """A loopback HTTP server that serves one JWKS and counts every request.

    The count is the measurement these tests are built on, so it is recorded
    before anything else in the handler: a request that arrives and then fails
    still proves the process dialled the internal address.
    """

    def __init__(self, jwks_document: dict[str, Any]) -> None:
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
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self) -> _JwksServer:
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)

    @property
    def jwks_uri(self) -> str:
        """Loopback JWKS URI, the shape an internal IdP endpoint would have."""
        host, port = self._httpd.server_address[0], self._httpd.server_address[1]
        assert isinstance(host, str)
        return f"http://{host}:{port}/.well-known/jwks.json"


@pytest.fixture(scope="module")
def signing_key() -> tuple[bytes, dict[str, Any]]:
    """Return an RSA private key and the JWKS document for its public half."""
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
    jwk = RSAKey.import_key(public_pem, {"kid": KEY_ID, "use": "sig", "alg": "RS256"})
    return private_pem, {"keys": [jwk.as_dict()]}


@pytest.fixture(scope="module")
def signed_token(signing_key: tuple[bytes, dict[str, Any]]) -> str:
    """Return a token that is valid in every respect except key availability."""
    private_pem, _ = signing_key
    now = int(time.time())
    claims = {
        "sub": SUBJECT,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 600,
        "scope": SCOPE,
    }
    return jwt.encode(
        {"alg": "RS256", "typ": "JWT", "kid": KEY_ID},
        claims,
        RSAKey.import_key(private_pem),
    )


@pytest.fixture
def jwks_server(signing_key: tuple[bytes, dict[str, Any]]) -> Iterator[_JwksServer]:
    """Run the loopback JWKS server for the duration of one test."""
    _, jwks_document = signing_key
    with _JwksServer(jwks_document) as server:
        yield server


def _auth_settings(jwks_uri: str, *, allow_insecure: bool) -> Settings:
    """Build auth-enabled settings for the JWKS verifier branch."""
    return Settings(
        mcp_auth_enabled=True,
        mcp_auth_jwks_uri=jwks_uri,
        mcp_auth_issuer=ISSUER,
        mcp_auth_audience=AUDIENCE,
        mcp_auth_required_scopes=SCOPE,
        allow_insecure_jwks_uri=allow_insecure,
    )


class TestJwksFetchReachesTheNetworkOnlyWhenPermitted:
    """The setting must change what the process does, not just what it stores."""

    async def test_internal_jwks_endpoint_is_never_contacted_by_default(
        self, jwks_server: _JwksServer, signed_token: str
    ) -> None:
        """A loopback JWKS URI must not be fetched under the secure default.

        The token is rejected, but that alone proves nothing -- an unreachable
        port rejects tokens too. The request count is the real assertion: the
        server is up and would have answered, and it was never asked.
        """
        verifier = _build_auth_provider(
            _auth_settings(jwks_server.jwks_uri, allow_insecure=False)
        )
        assert isinstance(verifier, JWTVerifier)

        access_token = await verifier.load_access_token(signed_token)

        assert jwks_server.requests == [], (
            "SSRF-safe mode still contacted the loopback JWKS endpoint: "
            f"{jwks_server.requests}"
        )
        assert access_token is None, (
            "A token whose signing key could not be fetched must not be accepted"
        )

    async def test_opting_out_restores_the_fetch_and_accepts_the_token(
        self, jwks_server: _JwksServer, signed_token: str
    ) -> None:
        """Positive control for the test above.

        Everything is identical except ``allow_insecure_jwks_uri``. This case
        must fetch the JWKS and mint a real ``AccessToken``, which is what rules
        out a zero-hit result caused by a broken server, an unusable JWKS
        document or a malformed token rather than by the SSRF guard.
        """
        verifier = _build_auth_provider(
            _auth_settings(jwks_server.jwks_uri, allow_insecure=True)
        )
        assert isinstance(verifier, JWTVerifier)

        access_token = await verifier.load_access_token(signed_token)

        assert len(jwks_server.requests) == 1, (
            f"The opt-out must fetch the JWKS exactly once, got {jwks_server.requests}"
        )
        assert access_token is not None, (
            "The opt-out path must accept a token signed by the served JWKS key"
        )
        assert access_token.client_id == SUBJECT
        assert SCOPE in access_token.scopes


class TestJwksVerifierConfiguration:
    """The constructed verifier must carry the setting it was built from."""

    def test_jwks_verifier_is_ssrf_safe_by_default(self) -> None:
        """Secure default: no environment change should be needed to get it."""
        verifier = _build_auth_provider(
            _auth_settings(PUBLIC_JWKS_URI, allow_insecure=False)
        )
        assert isinstance(verifier, JWTVerifier)
        assert verifier.jwks_uri == PUBLIC_JWKS_URI
        assert verifier.ssrf_safe is True

    def test_opt_out_disables_ssrf_protection_on_the_verifier(self) -> None:
        """The escape hatch must actually reach the constructed verifier."""
        verifier = _build_auth_provider(
            _auth_settings(PUBLIC_JWKS_URI, allow_insecure=True)
        )
        assert isinstance(verifier, JWTVerifier)
        assert verifier.ssrf_safe is False

    def test_opt_out_logs_an_error_naming_the_uri(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Running without SSRF protection must be visible at default log level.

        The block itself is only logged by fastmcp at DEBUG, so this startup
        message is the operator's one chance to notice the configuration.
        """
        with caplog.at_level("ERROR", logger="finos_mcp.fastmcp_server"):
            _build_auth_provider(_auth_settings(PUBLIC_JWKS_URI, allow_insecure=True))

        messages = [record.getMessage() for record in caplog.records]
        assert any(
            PUBLIC_JWKS_URI in message
            and "FINOS_MCP_ALLOW_INSECURE_JWKS_URI" in message
            for message in messages
        ), f"Expected an error naming the URI and the setting, got {messages}"

    def test_static_public_key_branch_is_unaffected(self) -> None:
        """The public-key verifier does not fetch anything and must not change."""
        public_pem = (
            rsa.generate_private_key(public_exponent=65537, key_size=2048)
            .public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        settings = Settings(
            mcp_auth_enabled=True,
            mcp_auth_public_key=public_pem,
            mcp_auth_issuer=ISSUER,
            mcp_auth_audience=AUDIENCE,
        )
        verifier = _build_auth_provider(settings)
        assert isinstance(verifier, JWTVerifier)
        assert verifier.jwks_uri is None


class TestStartupRejectsUnfetchableJwksUri:
    """A JWKS URI the guard can never fetch must fail loudly at startup.

    Without this the misconfiguration surfaces as every token being rejected
    with a bare 401 and a DEBUG-only log line, which is close to undiagnosable
    in a deployment running at INFO.
    """

    @pytest.mark.parametrize(
        ("jwks_uri", "expected_reason"),
        [
            ("http://auth.example.com/.well-known/jwks.json", "HTTPS"),
            ("https://10.0.0.5/.well-known/jwks.json", "not publicly routable"),
            ("https://127.0.0.1:8443/.well-known/jwks.json", "not publicly routable"),
            ("https://[::1]/.well-known/jwks.json", "not publicly routable"),
            ("https://169.254.169.254/latest/jwks.json", "not publicly routable"),
        ],
    )
    def test_unfetchable_uri_fails_startup_and_names_the_escape_hatch(
        self, jwks_uri: str, expected_reason: str
    ) -> None:
        """Reject at startup, and say which setting would permit it."""
        settings = _auth_settings(jwks_uri, allow_insecure=False)

        with pytest.raises(ValueError) as failure:
            settings.validate_startup()

        message = str(failure.value)
        assert expected_reason in message, message
        assert jwks_uri in message, message
        assert "FINOS_MCP_ALLOW_INSECURE_JWKS_URI" in message, message

    @pytest.mark.parametrize(
        "jwks_uri",
        [
            "http://auth.example.com/.well-known/jwks.json",
            "https://10.0.0.5/.well-known/jwks.json",
        ],
    )
    def test_opt_out_permits_the_same_uri(self, jwks_uri: str) -> None:
        """The escape hatch must clear the startup check it triggered."""
        _auth_settings(jwks_uri, allow_insecure=True).validate_startup()

    def test_public_https_jwks_uri_is_accepted(self) -> None:
        """Negative control: the guard must not reject a normal IdP endpoint.

        Without this, a check that rejected every JWKS URI would pass the cases
        above for entirely the wrong reason.
        """
        _auth_settings(PUBLIC_JWKS_URI, allow_insecure=False).validate_startup()

    def test_hostname_jwks_uri_is_accepted_even_though_it_may_resolve_privately(
        self,
    ) -> None:
        """The startup check is deliberately DNS-free.

        A hostname that only resolves inside the network cannot be judged here
        without a lookup, so it is allowed through and fails at fetch time. This
        test pins that boundary so the check is not later "improved" into
        something that resolves names during configuration validation.
        """
        _auth_settings(
            "https://keycloak.internal.example/.well-known/jwks.json",
            allow_insecure=False,
        ).validate_startup()
