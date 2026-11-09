"""Tests that an authenticated HTTP server tells a client where to sign in (#251).

The defect these cover: with auth enabled the server answered an unauthenticated
request with ``WWW-Authenticate: Bearer scope="..."`` and nothing else, and
served no protected-resource metadata document (RFC 9728). A client following
the MCP authorization flow had nothing to discover, so it worked only with a
token configured by hand.

Every assertion here is made on an HTTP response from the app fastmcp builds
for the provider ``_build_auth_provider`` returns. Reading the provider's type
back would pass against a provider that is wrapped and publishes nothing, so
the type is asserted only for stdio, where there is no HTTP surface to ask.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastmcp import FastMCP
from joserfc import jwt
from joserfc.jwk import RSAKey
from pydantic import ValidationError

from finos_mcp.app import _build_auth_provider, _published_issuer
from finos_mcp.config import Settings
from finos_mcp.security.jwt_verifier import FinosJWTVerifier

ISSUER = "https://auth.resource-metadata.test"
AUDIENCE = "finos-mcp-server"
SCOPE = "governance:read"
PUBLIC_URL = "https://mcp.resource-metadata.test"
METADATA_PATH = "/.well-known/oauth-protected-resource/mcp"
APP_LOGGER = "finos-ai-governance-mcp.fastmcp_server"

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "resource-metadata-test", "version": "1"},
    },
}
_MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def _token(private_pem: bytes, scope: str) -> str:
    now = int(time.time())
    claims = {
        "sub": "resource-metadata-test-client",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 600,
        "scope": scope,
    }
    return jwt.encode(
        {"alg": "RS256", "typ": "JWT"}, claims, RSAKey.import_key(private_pem)
    )


def _settings(public_pem: str, **overrides: object) -> Settings:
    """Build auth-enabled HTTP settings; ``overrides`` replace single fields."""
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
    server = FastMCP("resource-metadata-test", auth=_build_auth_provider(app_settings))
    app = server.http_app(path="/mcp")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client


class TestSignInDiscovery:
    """What an unauthenticated client is told, with and without the public URL."""

    async def test_challenge_names_a_document_that_describes_this_server(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        _, public_pem = key_pair
        async with _client(_settings(public_pem, mcp_auth_base_url=PUBLIC_URL)) as c:
            rejected = await c.post("/mcp", json=_INITIALIZE, headers=_MCP_HEADERS)
            document = await c.get(METADATA_PATH)

        assert rejected.status_code == 401
        challenge = rejected.headers["www-authenticate"]
        named = re.search(r'resource_metadata="([^"]+)"', challenge)
        assert named is not None, f"challenge names no metadata URL: {challenge}"
        assert named.group(1) == PUBLIC_URL + METADATA_PATH

        assert document.status_code == 200
        body = document.json()
        assert body["resource"] == PUBLIC_URL + "/mcp"
        # Exactly the configured issuer: a client compares this string with the
        # ``issuer`` the authorization server states about itself, and a
        # trailing slash added on the way makes a strict client reject it.
        assert body["authorization_servers"] == [ISSUER]
        assert body["scopes_supported"] == [SCOPE]

    async def test_the_issuer_path_is_published_as_written(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        """What fastmcp changes in the issuer on the way to the document (#259).

        The scheme and host are lowercased and a default port is dropped; the
        path, where issuers differ in case, is kept.
        """
        _, public_pem = key_pair
        written = "HTTPS://Auth.Example.com:443/Realms/Main"
        app_settings = _settings(
            public_pem, mcp_auth_base_url=PUBLIC_URL, mcp_auth_issuer=written
        )
        async with _client(app_settings) as c:
            body = (await c.get(METADATA_PATH)).json()
        assert body["authorization_servers"] == ["https://auth.example.com/Realms/Main"]

    @pytest.mark.parametrize(
        ("written", "published"),
        [
            ("https://auth.example.com", "https://auth.example.com"),
            ("https://auth.example.com/", "https://auth.example.com/"),
            ("https://auth.example.com:8443/r/", "https://auth.example.com:8443/r/"),
            (
                "https://auth.example.com/Realm?x=1",
                "https://auth.example.com/Realm?x=1",
            ),
            ("https://Auth.example.com", "https://auth.example.com"),
            ("https://auth.example.com:443", "https://auth.example.com"),
            ("http://auth.example.com:80", "http://auth.example.com"),
            ("https://auth.example.com/a b", "https://auth.example.com/a%20b"),
            ("https://bücher.example/r", "https://xn--bcher-kva.example/r"),
            # A dot segment is resolved, and the slash it leaves is published;
            # no slash is added before a query or fragment with no path (#273).
            ("https://auth.example.com/a/.", "https://auth.example.com/a/"),
            ("https://auth.example.com/a/..", "https://auth.example.com/"),
            ("https://auth.example.com?x=1", "https://auth.example.com?x=1"),
            ("https://auth.example.com#f", "https://auth.example.com#f"),
        ],
    )
    async def test_an_issuer_published_in_another_form_is_reported(
        self,
        key_pair: tuple[bytes, str],
        caplog: pytest.LogCaptureFixture,
        written: str,
        published: str,
    ) -> None:
        """The operator is told when clients will see another issuer (#266).

        Tokens are checked against the configured string, so the two forms
        differ in silence until a client compares them and refuses to sign in.
        """
        _, public_pem = key_pair
        app_settings = _settings(
            public_pem, mcp_auth_base_url=PUBLIC_URL, mcp_auth_issuer=written
        )
        with caplog.at_level(logging.INFO, logger=APP_LOGGER):
            async with _client(app_settings) as c:
                body = (await c.get(METADATA_PATH)).json()
        warned = [
            r.getMessage()
            for r in caplog.records
            if r.name == APP_LOGGER and r.levelno == logging.WARNING
        ]

        assert body["authorization_servers"] == [published]
        assert _published_issuer(written) == published
        if written == published:
            assert warned == []
        else:
            assert len(warned) == 1, warned
            assert published in warned[0] and written in warned[0]

    async def test_nothing_is_advertised_without_the_public_url(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        """The server does not guess its public URL from the bind address.

        Paired with the test above: the same settings less one field, the same
        two requests. That test is what shows these requests can find a
        document when one is served.
        """
        _, public_pem = key_pair
        async with _client(_settings(public_pem)) as c:
            rejected = await c.post("/mcp", json=_INITIALIZE, headers=_MCP_HEADERS)
            document = await c.get(METADATA_PATH)

        assert rejected.status_code == 401
        assert "resource_metadata" not in rejected.headers["www-authenticate"]
        assert document.status_code == 404

    def test_stdio_keeps_the_bare_verifier(self, key_pair: tuple[bytes, str]) -> None:
        """stdio has no HTTP routes, so there is nowhere to serve a document."""
        _, public_pem = key_pair
        provider = _build_auth_provider(
            _settings(public_pem, mcp_transport="stdio", mcp_auth_base_url=PUBLIC_URL)
        )
        assert type(provider) is FinosJWTVerifier


class TestTokensAreCheckedTheSameWithDiscoveryOn:
    """Publishing the document must not change which tokens are accepted."""

    async def test_valid_token_is_accepted_and_wrong_scope_is_rejected(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        private_pem, public_pem = key_pair
        accepted_token = _token(private_pem, SCOPE)
        wrong_scope_token = _token(private_pem, "governance:write")

        async with _client(_settings(public_pem, mcp_auth_base_url=PUBLIC_URL)) as c:
            accepted = await c.post(
                "/mcp",
                json=_INITIALIZE,
                headers={**_MCP_HEADERS, "Authorization": f"Bearer {accepted_token}"},
            )
            wrong_scope = await c.post(
                "/mcp",
                json=_INITIALIZE,
                headers={
                    **_MCP_HEADERS,
                    "Authorization": f"Bearer {wrong_scope_token}",
                },
            )

        # The two tokens differ only in the scope claim, so the 200 is what
        # shows the rejection below is caused by the scope and nothing else.
        assert accepted.status_code == 200, accepted.text
        assert "resource-metadata-test" in accepted.text
        assert wrong_scope.status_code == 401
        assert 'error="invalid_token"' in wrong_scope.headers["www-authenticate"]


class TestStartupSaysWhenDiscoveryIsOff:
    """An operator who has not set the URL is told what clients will not get."""

    def test_missing_public_url_is_logged_for_http(
        self, key_pair: tuple[bytes, str], caplog: pytest.LogCaptureFixture
    ) -> None:
        _, public_pem = key_pair
        with caplog.at_level(logging.INFO, logger=APP_LOGGER):
            _build_auth_provider(_settings(public_pem))
        lines = [r.getMessage() for r in caplog.records if r.name == APP_LOGGER]
        assert any("FINOS_MCP_MCP_AUTH_BASE_URL" in line for line in lines), lines

    def test_no_such_line_when_the_public_url_is_set(
        self, key_pair: tuple[bytes, str], caplog: pytest.LogCaptureFixture
    ) -> None:
        _, public_pem = key_pair
        with caplog.at_level(logging.INFO, logger=APP_LOGGER):
            logging.getLogger(APP_LOGGER).info("canary")
            _build_auth_provider(_settings(public_pem, mcp_auth_base_url=PUBLIC_URL))
        lines = [r.getMessage() for r in caplog.records if r.name == APP_LOGGER]
        assert "canary" in lines
        assert not any("is not set" in line for line in lines), lines


class TestPublicUrlSetting:
    """What the setting accepts."""

    def test_an_issuer_that_is_not_a_url_stops_startup(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        """The issuer is published as the place to sign in, so it must be one."""
        _, public_pem = key_pair
        plain = {"mcp_auth_issuer": "internal-issuer"}
        with pytest.raises(ValueError, match="cannot be published"):
            _settings(
                public_pem, mcp_auth_base_url=PUBLIC_URL, **plain
            ).validate_startup()
        # Without the public URL nothing is published and the same issuer starts.
        _settings(public_pem, **plain).validate_startup()

    @pytest.mark.parametrize(
        "issuer",
        [
            "https://",
            "https://?realm=a",
            "https:auth.example.com",
            "https://:8443",
            "https://[auth",
        ],
    )
    def test_an_issuer_with_no_host_stops_startup(
        self, key_pair: tuple[bytes, str], issuer: str
    ) -> None:
        """An HTTPS scheme is not an address a client can go to (#259).

        The first two passed startup and stopped the server later, with a
        pydantic error raised while the metadata document was built. The third
        was published as ``https://auth.example.com``, which is not the
        ``iss`` the tokens carry.
        """
        _, public_pem = key_pair
        named = {"mcp_auth_issuer": issuer}
        with pytest.raises(ValueError, match="cannot be published"):
            _settings(
                public_pem, mcp_auth_base_url=PUBLIC_URL, **named
            ).validate_startup()
        _settings(public_pem, **named).validate_startup()

    @pytest.mark.parametrize(
        "issuer",
        [
            "https://auth.example.com:99999",
            "https://auth.example.com:abc",
            "https:// auth.example.com",
            "https://auth example.com/x",
            "https://%20",
        ],
    )
    def test_an_issuer_pydantic_cannot_read_stops_startup(
        self, key_pair: tuple[bytes, str], issuer: str
    ) -> None:
        """A scheme and a host are not all the metadata document needs (#265).

        Each of these passed startup and stopped the server later, with a
        pydantic error raised while the document was built.
        """
        _, public_pem = key_pair
        named = {"mcp_auth_issuer": issuer}
        with pytest.raises(ValueError, match="cannot be published"):
            _settings(
                public_pem, mcp_auth_base_url=PUBLIC_URL, **named
            ).validate_startup()
        _settings(public_pem, **named).validate_startup()

    def test_the_refusal_states_what_is_wrong_with_the_issuer(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        """A URL with a host was refused as "not a URL with a host" (#276)."""
        _, public_pem = key_pair

        def refusal(issuer: str) -> str:
            app_settings = _settings(
                public_pem,
                mcp_auth_base_url=PUBLIC_URL,
                mcp_auth_issuer=issuer,
            )
            with pytest.raises(ValueError, match="cannot be published") as raised:
                app_settings.validate_startup()
            return str(raised.value)

        bad_port = refusal("https://auth.example.com:99999")
        assert "invalid port number" in bad_port
        assert "with a host" not in bad_port
        assert "with a host" in refusal("https:auth.example.com")
        # A malformed host is a host: urlparse raises on it, and that was read
        # as no host at all (#277).
        for malformed in ("https://[::1", "https://[zz]/"):
            assert "invalid IPv6 address" in refusal(malformed)
            assert "with a host" not in refusal(malformed)

    def test_trailing_slash_is_removed_and_a_path_is_kept(self) -> None:
        assert (
            Settings(mcp_auth_base_url="https://mcp.example.com/").mcp_auth_base_url
            == "https://mcp.example.com"
        )
        assert (
            Settings(mcp_auth_base_url="https://example.com/gov/").mcp_auth_base_url
            == "https://example.com/gov"
        )

    def test_blank_means_not_set(self) -> None:
        assert Settings(mcp_auth_base_url="  ").mcp_auth_base_url is None

    def test_whitespace_around_the_issuer_and_audience_is_removed(
        self, key_pair: tuple[bytes, str]
    ) -> None:
        """A trailing newline started the server and failed every token (#281).

        Tokens are compared against the setting as held, and the startup check
        passed because urlparse and pydantic both strip the value.
        """
        _, public_pem = key_pair
        held = Settings(
            mcp_auth_issuer=f" {ISSUER}\n", mcp_auth_audience=f"{AUDIENCE}\n"
        )
        assert held.mcp_auth_issuer == ISSUER
        assert held.mcp_auth_audience == AUDIENCE

        blank = _settings(public_pem, mcp_auth_issuer="  ")
        assert blank.mcp_auth_issuer is None
        with pytest.raises(ValueError, match="mcp_auth_issuer is required"):
            blank.validate_startup()

    @pytest.mark.parametrize(
        "value", ["ftp://mcp.example.com", "mcp.example.com", "https://"]
    )
    def test_a_value_that_is_not_an_http_url_is_rejected(self, value: str) -> None:
        with pytest.raises(ValidationError, match="MCP auth base URL"):
            Settings(mcp_auth_base_url=value)


class TestTheBaseUrlIsCheckedAsTheIssuerIs:
    """#319: a base URL pydantic refuses stops startup naming the setting.

    ``validate_mcp_auth_base_url`` used ``urlparse`` alone, so a port out of
    range or a space in the host passed ``validate_startup`` and fastmcp's
    ``AnyHttpUrl`` then failed at import with a traceback naming no setting.
    This is what #265 fixed for the issuer, applied to the setting next to it.
    """

    @pytest.mark.parametrize(
        "value", ["https://mcp.example.com:99999", "https://mcp example.com"]
    )
    def test_a_base_url_pydantic_refuses_is_refused_by_name(self, value: str) -> None:
        with pytest.raises(ValidationError, match="base URL") as refused:
            Settings(mcp_auth_base_url=value)
        assert "mcp_auth_base_url" in str(refused.value)

    def test_a_base_url_with_a_path_and_a_port_is_kept(self) -> None:
        assert (
            Settings(
                mcp_auth_base_url="https://mcp.example.com:8443/mcp/"
            ).mcp_auth_base_url
            == "https://mcp.example.com:8443/mcp"
        )
