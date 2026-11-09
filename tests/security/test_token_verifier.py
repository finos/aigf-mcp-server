# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""What the token verifier accepts and refuses, measured through the built app.

The verifier is fastmcp's ``JWTVerifier`` with this server's settings. These
tests pin the properties the CALM authentication control claims and the
documents state, each as a request to a FastMCP app guarded by the provider
``_build_auth_provider`` returns, because that is the surface a token
reaches.

- #318: only RS256 is accepted. The algorithm is passed explicitly rather
  than left to fastmcp's default, and ``alg: none`` and HS256-with-the-
  public-key both get 401.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import httpx
import pytest
from fastmcp import FastMCP
from fastmcp.server.auth import JWTVerifier
from joserfc import jwt
from joserfc.jwk import KeyParameters, RSAKey

from finos_mcp import http_health
from finos_mcp.app import _build_auth_provider
from finos_mcp.config import Settings

pytestmark = pytest.mark.unit

ISSUER = "https://issuer.token-verifier.test"
AUDIENCE = "finos-mcp-server"
SCOPE = "governance:read"
SUBJECT = "token-verifier-test-client"

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "token-verifier-test", "version": "0"},
    },
}
_MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _claims(**changes: Any) -> dict[str, Any]:
    """A token body that is valid in every respect; ``changes`` edit it.

    A key set to ``None`` is left out.
    """
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": SUBJECT,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 600,
        "scope": SCOPE,
    }
    claims.update(changes)
    return {key: value for key, value in claims.items() if value is not None}


def _rs256(private_pem: bytes, claims: dict[str, Any]) -> str:
    return jwt.encode(
        {"alg": "RS256", "typ": "JWT"}, claims, RSAKey.import_key(private_pem)
    )


def _segment(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


def _unsigned(claims: dict[str, Any]) -> str:
    """A token with ``alg: none`` and an empty signature, built by hand."""
    return (
        f"{_segment(_json({'alg': 'none', 'typ': 'JWT'}))}.{_segment(_json(claims))}."
    )


def _hs256_with_the_public_key(public_pem: str, claims: dict[str, Any]) -> str:
    """A token whose HMAC secret is the public key, which an attacker holds.

    Built by hand: joserfc refuses to sign HS256 with a PEM, an attacker's
    tooling does not.
    """
    signing_input = (
        f"{_segment(_json({'alg': 'HS256', 'typ': 'JWT'}))}.{_segment(_json(claims))}"
    )
    signature = hmac.new(
        public_pem.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    return f"{signing_input}.{_segment(signature)}"


def _settings(public_pem: str, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "mcp_transport": "http",
        "mcp_auth_enabled": True,
        "mcp_auth_public_key": public_pem,
        "mcp_auth_issuer": ISSUER,
        "mcp_auth_audience": AUDIENCE,
        "mcp_auth_required_scopes": SCOPE,
    }
    values.update(overrides)
    return Settings(**values)


@asynccontextmanager
async def _client(app_settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    """Serve a FastMCP app guarded by the provider built for ``app_settings``."""
    server = FastMCP("token-verifier-test", auth=_build_auth_provider(app_settings))
    app = server.http_app(path="/mcp")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client


async def _initialize(client: httpx.AsyncClient, token: str) -> httpx.Response:
    return await client.post(
        "/mcp",
        json=_INITIALIZE,
        headers={**_MCP_HEADERS, "Authorization": f"Bearer {token}"},
    )


class TestOnlyRS256IsAccepted:
    """#318. Pins, not fixes: fastmcp's default already behaved so, unstated."""

    def test_both_verifiers_are_built_for_rs256(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        _, public_pem = key_pair
        static = _build_auth_provider(_settings(public_pem))
        jwks = _build_auth_provider(
            _settings(
                public_pem,
                mcp_auth_public_key=None,
                mcp_auth_jwks_uri="https://auth.example.com/.well-known/jwks.json",
            )
        )
        assert isinstance(static, JWTVerifier) and isinstance(jwks, JWTVerifier)
        assert static.algorithm == "RS256"
        assert jwks.algorithm == "RS256"

    async def test_a_valid_rs256_token_is_accepted(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        """The control for the refusals below: this app does accept a token."""
        private_pem, public_pem = key_pair
        async with _client(_settings(public_pem)) as c:
            answer = await _initialize(c, _rs256(private_pem, _claims()))
        assert answer.status_code == 200, answer.text

    async def test_an_unsigned_token_is_refused(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        _, public_pem = key_pair
        async with _client(_settings(public_pem)) as c:
            answer = await _initialize(c, _unsigned(_claims()))
        assert answer.status_code == 401, "a token with alg none was accepted"

    async def test_a_token_signed_with_the_public_key_as_hmac_secret_is_refused(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        _, public_pem = key_pair
        async with _client(_settings(public_pem)) as c:
            answer = await _initialize(
                c, _hs256_with_the_public_key(public_pem, _claims())
            )
        assert answer.status_code == 401, (
            "an HS256 token keyed on the public key passed"
        )


class TestLifetimeClaims:
    """#286. Expiry is the only revocation this server has, so it is required."""

    async def test_a_token_without_exp_is_refused(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        private_pem, public_pem = key_pair
        async with _client(_settings(public_pem)) as c:
            answer = await _initialize(c, _rs256(private_pem, _claims(exp=None)))
        assert answer.status_code == 401, "a token that never expires was accepted"

    async def test_a_token_not_yet_valid_is_refused(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        private_pem, public_pem = key_pair
        ahead = int(time.time()) + 3600
        async with _client(_settings(public_pem)) as c:
            answer = await _initialize(c, _rs256(private_pem, _claims(nbf=ahead)))
        assert answer.status_code == 401, "a token with nbf an hour ahead was accepted"

    async def test_a_token_whose_nbf_has_passed_is_accepted(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        """The control: nbf is honoured, not refused by presence."""
        private_pem, public_pem = key_pair
        behind = int(time.time()) - 60
        async with _client(_settings(public_pem)) as c:
            answer = await _initialize(c, _rs256(private_pem, _claims(nbf=behind)))
        assert answer.status_code == 200, answer.text


class TestATokenNamesItsSubject:
    """#320. Rate limits and the call log key on the subject; one is required."""

    async def test_a_token_with_no_identity_claim_is_refused(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        """fastmcp would call this client ``unknown`` and accept it."""
        private_pem, public_pem = key_pair
        async with _client(_settings(public_pem)) as c:
            answer = await _initialize(c, _rs256(private_pem, _claims(sub=None)))
        assert answer.status_code == 401, "a token naming no subject was accepted"

    async def test_an_azp_without_sub_is_not_a_subject(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        """Decided: sub, not any of the three claims fastmcp accepts."""
        private_pem, public_pem = key_pair
        token = _rs256(private_pem, _claims(sub=None, azp="some-client-app"))
        async with _client(_settings(public_pem)) as c:
            answer = await _initialize(c, token)
        assert answer.status_code == 401, "a token with azp and no sub was accepted"


KEY_ID = "token-verifier-test-key"


class _JwksServer:
    """A loopback server for one JWKS that counts every request.

    ``failing`` makes it answer 500, the shape of a throttling provider.
    """

    def __init__(self, jwks_document: dict[str, Any]) -> None:
        payload = json.dumps(jwks_document).encode("utf-8")
        self.requests: list[str] = []
        self.failing = False
        server_self = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                server_self.requests.append(self.path)
                if server_self.failing:
                    self.send_response(500)
                    self.end_headers()
                    return
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
        host, port = self._httpd.server_address[0], self._httpd.server_address[1]
        assert isinstance(host, str)
        return f"http://{host}:{port}/.well-known/jwks.json"


@pytest.fixture
def jwks_server(key_pair: tuple[bytes, str]) -> Iterator[_JwksServer]:
    _, public_pem = key_pair
    parameters: KeyParameters = {"kid": KEY_ID, "use": "sig", "alg": "RS256"}
    jwk = RSAKey.import_key(public_pem, parameters)
    with _JwksServer({"keys": [jwk.as_dict()]}) as server:
        yield server


def _jwks_settings(jwks_uri: str) -> Settings:
    return Settings(
        mcp_transport="http",
        mcp_auth_enabled=True,
        mcp_auth_jwks_uri=jwks_uri,
        mcp_auth_issuer=ISSUER,
        mcp_auth_audience=AUDIENCE,
        mcp_auth_required_scopes=SCOPE,
        # The server is on loopback, which the SSRF guard refuses by design.
        allow_insecure_jwks_uri=True,
    )


def _rs256_with_kid(private_pem: bytes, kid: str) -> str:
    header = {"alg": "RS256", "typ": "JWT", "kid": kid}
    return jwt.encode(header, _claims(), RSAKey.import_key(private_pem))


@asynccontextmanager
async def _client_with_health(
    app_settings: Settings,
) -> AsyncIterator[httpx.AsyncClient]:
    """As ``_client``, with the two health URLs the real server registers."""
    server = FastMCP("token-verifier-test", auth=_build_auth_provider(app_settings))
    http_health.register_health_routes(server)
    app = server.http_app(path="/mcp")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client


class TestTheJwksIsNotFetchedPerRequest:
    """#285. Measured before: 20 unknown kids gave 20 fetches."""

    async def test_twenty_unknown_kids_cost_at_most_one_fetch(
        self, jwks_server: _JwksServer, key_pair: tuple[bytes, str]
    ) -> None:
        private_pem, _ = key_pair
        async with _client(_jwks_settings(jwks_server.jwks_uri)) as c:
            answers = [
                await _initialize(c, _rs256_with_kid(private_pem, f"unknown-{n}"))
                for n in range(20)
            ]
        assert {a.status_code for a in answers} == {401}
        assert len(jwks_server.requests) <= 1, (
            f"{len(jwks_server.requests)} JWKS fetches for 20 unknown key ids"
        )

    async def test_a_forged_header_on_a_health_url_costs_at_most_one_fetch(
        self, jwks_server: _JwksServer, key_pair: tuple[bytes, str]
    ) -> None:
        private_pem, _ = key_pair
        async with _client_with_health(_jwks_settings(jwks_server.jwks_uri)) as c:
            answers = [
                await c.get(
                    "/healthz",
                    headers={
                        "Authorization": f"Bearer {_rs256_with_kid(private_pem, f'x{n}')}"
                    },
                )
                for n in range(10)
            ]
        assert {a.status_code for a in answers} == {200}
        assert len(jwks_server.requests) <= 1, (
            f"{len(jwks_server.requests)} JWKS fetches for 10 health requests"
        )

    async def test_a_known_kid_is_served_from_the_fetched_set_meanwhile(
        self, jwks_server: _JwksServer, key_pair: tuple[bytes, str]
    ) -> None:
        """The control: the interval refuses unknown keys, not known ones."""
        private_pem, _ = key_pair
        async with _client(_jwks_settings(jwks_server.jwks_uri)) as c:
            first = await _initialize(c, _rs256_with_kid(private_pem, KEY_ID))
            unknown = await _initialize(c, _rs256_with_kid(private_pem, "unknown"))
            again = await _initialize(c, _rs256_with_kid(private_pem, KEY_ID))
        assert (first.status_code, unknown.status_code, again.status_code) == (
            200,
            401,
            200,
        ), (first.text, unknown.text, again.text)
        assert len(jwks_server.requests) == 1

    async def test_a_failing_provider_is_asked_once_per_interval(
        self, jwks_server: _JwksServer, key_pair: tuple[bytes, str]
    ) -> None:
        private_pem, _ = key_pair
        jwks_server.failing = True
        async with _client(_jwks_settings(jwks_server.jwks_uri)) as c:
            answers = [
                await _initialize(c, _rs256_with_kid(private_pem, KEY_ID))
                for _ in range(10)
            ]
        assert {a.status_code for a in answers} == {401}
        assert len(jwks_server.requests) == 1, (
            f"{len(jwks_server.requests)} attempts on a provider that answers 500"
        )
