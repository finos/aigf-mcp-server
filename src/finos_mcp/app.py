#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The server object, and the wiring that must exist before any tool is registered.

Copyright 2025 FINOS

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import ipaddress
import time
from typing import cast

from fastmcp import FastMCP
from fastmcp.server.auth import JWTVerifier, RemoteAuthProvider
from fastmcp.server.dependencies import get_access_token, get_http_request
from mcp.shared.auth import ProtectedResourceMetadata
from pydantic import AnyHttpUrl, TypeAdapter

from . import __version__
from .config import Settings, validate_settings_on_startup
from .logging import get_logger
from .security.dos_middleware import DoSProtectionMiddleware
from .security.jwt_verifier import FinosJWTVerifier
from .security.prompt_safety import (
    SERVER_TRUST_INSTRUCTIONS,
)
from .security.request_validator import dos_protector, request_size_validator
from .security.tool_call_log import ToolCallLogMiddleware

# Initialize configuration and logging
settings = validate_settings_on_startup()

logger = get_logger("fastmcp_server")

# stdio serves exactly one client per process, so a fixed key is the honest
# identity there. Kept at its original value so stdio buckets are unchanged.
_STDIO_CLIENT_ID = "mcp_client"


def _is_trusted_proxy(address: str) -> bool:
    """Check whether an address falls inside a configured trusted-proxy network."""
    networks = settings.dos_trusted_proxy_networks
    if not networks:
        return False
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in networks)


def _client_ip() -> str | None:
    """Resolve the calling client's address, or None when not serving over HTTP."""
    try:
        request = get_http_request()
    except RuntimeError:
        return None  # stdio: no HTTP request in flight

    peer = request.client.host if request.client else None
    if peer is None or not _is_trusted_proxy(peer):
        # X-Forwarded-For is caller-controlled. Reading it from anyone but a
        # known proxy would let a client pick its own rate-limit bucket by
        # rotating the header, which is worse than sharing one bucket.
        return peer

    # The header is an append log: every hop adds the address it saw, so the
    # rightmost entries are the ones our own infrastructure wrote. Walk right to
    # left past the hops we trust; the first untrusted entry is the real client.
    forwarded = request.headers.get("x-forwarded-for", "")
    chain = [entry.strip() for entry in forwarded.split(",") if entry.strip()]
    for entry in reversed(chain):
        try:
            ipaddress.ip_address(entry)
        except ValueError:
            return peer  # malformed chain: distrust the whole header
        if not _is_trusted_proxy(entry):
            return entry
    return peer  # header absent, or every hop was one of ours


def _resolve_dos_client_id() -> str:
    """Identify the caller for rate limiting, most trustworthy identity first."""
    try:
        token = get_access_token()
    except Exception:  # pragma: no cover - defensive, no auth context active
        token = None
    if token is not None:
        # An attested subject survives NAT, proxies and IP rotation, and cannot
        # be forged the way a source address or a header can. The verifier
        # refuses a token without `sub` (#320), so `sub` is the only identity
        # read here (#408).
        identity = (token.claims or {}).get("sub")
        if identity:
            return f"jwt:{identity}"

    address = _client_ip()
    if address:
        return f"ip:{address}"
    return _STDIO_CLIENT_ID


# The metadata document's own URL rules: its model keeps a URL with no path
# free of the slash pydantic otherwise appends, so its settings are read from
# the model and not repeated here (#273).
_DOCUMENT_URL = TypeAdapter(AnyHttpUrl, config=ProtectedResourceMetadata.model_config)


def _published_issuer(issuer: str) -> str:
    """The form in which the metadata document names `issuer` (#266).

    The document is built by pydantic, which lowercases the scheme and host,
    drops a default port, resolves dot segments, percent-encodes the path and
    writes a host that is not ASCII as punycode. Measured on the document for
    thirteen spellings.
    """
    return str(_DOCUMENT_URL.validate_python(issuer))


#: The one signature algorithm a token may carry. Written out rather than left
#: to fastmcp's default, which is the same, so that the README and the CALM
#: control describe a decision of this server (#318). A JWKS key of another
#: type is not used; the static key must be an RSA public key.
SIGNATURE_ALGORITHM = "RS256"


def _with_sign_in_discovery(
    verifier: JWTVerifier, app_settings: Settings
) -> JWTVerifier | RemoteAuthProvider:
    """Publish where to sign in, when the server has been told its public URL.

    A bare verifier checks tokens and tells a client nothing: the 401 carries no
    ``resource_metadata`` and no protected-resource metadata document is served
    (RFC 9728), so a client following the MCP authorization flow cannot find
    the authorization server. fastmcp serves both once the verifier is wrapped,
    and the wrapper delegates every token check to the verifier it was given.

    The document's ``resource`` is the public URL plus the MCP path, and a
    client rejects a document whose ``resource`` is not the URL it called. The
    bind address is not that URL behind a proxy, so nothing is derived from it:
    without the setting the server publishes nothing, and says so (#251).
    """
    if app_settings.mcp_transport == "stdio":
        return verifier  # no HTTP routes to serve a document from
    issuer = app_settings.mcp_auth_issuer
    if issuer is None:
        return verifier  # validate_startup() refuses auth without an issuer
    if not app_settings.mcp_auth_base_url:
        logger.info(
            "Sign-in discovery is not advertised because "
            "FINOS_MCP_MCP_AUTH_BASE_URL is not set. Tokens are still checked; "
            "a client must be given its token, or the authorization server, "
            "by other means."
        )
        return verifier
    logger.info(
        "Sign-in discovery advertised for %s (authorization server %s)",
        app_settings.mcp_auth_base_url,
        issuer,
    )
    published = _published_issuer(issuer)
    if published != issuer:
        logger.warning(
            "The authorization server is published as %s, not as the "
            "configured FINOS_MCP_MCP_AUTH_ISSUER %s. Tokens are still checked "
            "against the configured value. A client that compares the "
            "published address with the issuer the authorization server "
            "states may refuse to sign in; configure the issuer in the "
            "published form if the two should be the same.",
            published,
            issuer,
        )
    # The issuer is passed as the string the operator configured. Building an
    # ``AnyHttpUrl`` from it appends a slash to a URL with no path, and a client
    # compares the published value with the ``issuer`` the authorization server
    # states about itself. What the document does change is reported above
    # (`_published_issuer`).
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=cast("list[AnyHttpUrl]", [issuer]),
        base_url=app_settings.mcp_auth_base_url,
        resource_name=app_settings.server_name,
    )


def _build_auth_provider(
    app_settings: Settings,
) -> JWTVerifier | RemoteAuthProvider | None:
    """Build the MCP auth provider from validated application settings."""
    if not app_settings.mcp_auth_enabled:
        # validate_startup() rejects a networked transport with auth disabled, so
        # reaching here means either stdio (no network boundary to authenticate)
        # or an explicit FINOS_MCP_ALLOW_INSECURE_HTTP override.
        if app_settings.mcp_transport == "stdio":
            logger.info(
                "MCP auth is not configured. This is expected for the stdio "
                "transport, which has no network boundary to authenticate."
            )
        else:
            logger.error(
                "MCP auth is DISABLED on transport %s because "
                "FINOS_MCP_ALLOW_INSECURE_HTTP=true. Any client that can reach "
                "%s:%s may invoke every tool and prompt without a token. Set "
                "FINOS_MCP_MCP_AUTH_ENABLED=true and configure "
                "FINOS_MCP_MCP_AUTH_JWKS_URI (or MCP_AUTH_PUBLIC_KEY) before "
                "exposing this server.",
                app_settings.mcp_transport,
                app_settings.mcp_host,
                app_settings.mcp_port,
            )
        return None

    if app_settings.mcp_auth_jwks_uri:
        # The JWKS URI is operator config that this process fetches at the
        # first token verification and again for an unknown key id or an aged
        # set, at most once a minute (#285); the document it returns decides
        # which signatures are trusted. ssrf_safe routes that fetch through fastmcp's
        # SSRF guard (HTTPS only, public unicast destinations, DNS pinned), so
        # it defaults on. Opting out is for an internal IdP and nothing else.
        ssrf_safe = not app_settings.allow_insecure_jwks_uri
        if ssrf_safe:
            logger.info(
                "MCP auth enabled using JWKS verifier with SSRF protection "
                "(HTTPS-only, public addresses only)"
            )
        else:
            # fastmcp logs an SSRF block at DEBUG and surfaces it as an ordinary
            # 401, so a deployment that opted out has no other signal that its
            # key source is unprotected. Say it here, at startup, at ERROR.
            logger.error(
                "INSECURE: JWKS SSRF protection is DISABLED because "
                "FINOS_MCP_ALLOW_INSECURE_JWKS_URI=true. Signing keys are "
                "fetched from %s with no scheme or destination restriction, so "
                "this server can be pointed at loopback, link-local or private "
                "addresses, and over plain HTTP an on-path attacker can "
                "substitute the keys used to accept tokens. Unset this unless "
                "the identity provider is an internal service.",
                app_settings.mcp_auth_jwks_uri,
            )
        verifier = FinosJWTVerifier(
            jwks_uri=app_settings.mcp_auth_jwks_uri,
            issuer=app_settings.mcp_auth_issuer,
            audience=app_settings.mcp_auth_audience,
            required_scopes=app_settings.mcp_auth_scopes_list or None,
            algorithm=SIGNATURE_ALGORITHM,
            ssrf_safe=ssrf_safe,
        )
    else:
        logger.info("MCP auth enabled using static public key verifier")
        if app_settings.mcp_auth_public_key is None:  # validate_startup requires one
            raise ValueError("MCP auth is enabled with neither a JWKS URI nor a key")
        verifier = FinosJWTVerifier(
            public_key=app_settings.mcp_auth_public_key.get_secret_value(),
            issuer=app_settings.mcp_auth_issuer,
            audience=app_settings.mcp_auth_audience,
            required_scopes=app_settings.mcp_auth_scopes_list or None,
            algorithm=SIGNATURE_ALGORITHM,
        )
    return _with_sign_in_discovery(verifier, app_settings)


# Create FastMCP server instance
mcp = FastMCP(
    settings.server_name,
    # Without this fastmcp reports its own version as the server's. The build's
    # version is not a setting: get_service_health and the User-Agent state the
    # same one (#194).
    version=__version__,
    auth=_build_auth_provider(settings),
    # Delivered in the ``initialize`` result, so the trust boundary for tool
    # and resource payloads is stated once to every client. See #122 and the
    # comment on SERVER_TRUST_INSTRUCTIONS for why those paths are not
    # marked per payload.
    instructions=SERVER_TRUST_INSTRUCTIONS,
)

_SERVER_START_TIME = time.monotonic()

# Configure global DoS protection from validated settings.
dos_protector.max_requests_per_minute = settings.dos_max_requests_per_minute
dos_protector.max_concurrent_requests = settings.dos_max_concurrent_requests

# Registered first, so outside the DoS middleware: a call the limits refuse is
# logged too (#271).
mcp.add_middleware(ToolCallLogMiddleware(resolve_client_id=_resolve_dos_client_id))

# The rate and concurrency limits live in middleware, not in the tool bodies:
# a guard inside a tool is swallowed by the code it constrains (#23).
mcp.add_middleware(
    DoSProtectionMiddleware(
        protector=dos_protector,
        validator=request_size_validator,
        resolve_client_id=_resolve_dos_client_id,
    )
)
