# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Configuration settings for FINOS MCP Server.

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

This module provides Pydantic-based configuration management with environment variable
support and validation. Settings are loaded from environment variables and, when
FINOS_MCP_ENV_FILE names one, a dotenv file.
"""

import functools
import ipaddress
import logging
import os
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from pydantic import (
    AnyHttpUrl,
    Field,
    SecretStr,
    TypeAdapter,
    ValidationError,
    field_validator,
)
from pydantic.types import PositiveInt
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    PydanticBaseSettingsSource,
)

from .security.repo_target import (
    RepoTarget,
    resolve_repo_target,
    why_not_a_fetch_target,
)

_HTTP_URL = TypeAdapter(AnyHttpUrl)

#: Names the dotenv file the server reads. Unset, no file is read: on stdio the
#: working directory is the client's, so a ``.env`` there is not the operator's
#: (#283). Read from the environment, not a setting, because it decides where
#: the settings come from.
ENV_FILE_VARIABLE = "FINOS_MCP_ENV_FILE"

#: The prefixes GitHub gives its tokens. Not a check on the setting (#289):
#: GitHub adds formats, and a wrong token is answered with 401. Kept for log
#: redaction (#290).
GITHUB_TOKEN_PREFIXES = ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "ghv_", "github_pat_")


def _why_not_an_http_url(value: str) -> str | None:
    """Return why `value` is not an HTTP or HTTPS URL with a host, or None.

    Pydantic builds the metadata document from the issuer and fastmcp builds
    its resource URL from the base URL, so what pydantic refuses is refused
    here, with its reason: a port out of range, a space in the host, a
    malformed bracketed host (#265, #276, #277, #319). It accepts
    ``https:auth.example.com``, which names no host as written.
    """
    try:
        _HTTP_URL.validate_python(value)
    except ValidationError as error:
        return str(error.errors()[0]["msg"])
    try:
        hostname = urlparse(value).hostname
    except ValueError:  # pragma: no cover - no accepted value is known to raise
        hostname = None
    if not hostname:
        return "it is not an HTTP or HTTPS URL with a host"
    return None


def _is_loopback(host: str) -> bool:
    """Whether a bind host reaches only this machine."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _public_key_cannot_verify(pem: str) -> str | None:
    """Return why `pem` cannot verify an RS256 token, or None.

    fastmcp imports the key at the first token and reports a failure at
    DEBUG, so a key that cannot be used looks in production exactly like
    every token being invalid, and a private key is accepted and used (#287).
    Loaded here, at startup, with the reason.
    """
    if "PRIVATE KEY" in pem:
        return "it is a private key; give the public key"
    try:
        key = load_pem_public_key(pem.encode("utf-8"))
    except (ValueError, TypeError, UnsupportedAlgorithm) as error:
        return f"it does not load as a PEM public key ({error})"
    if not isinstance(key, RSAPublicKey):
        return "it is not an RSA public key, and tokens are RS256"
    return None


def _jwks_uri_blocked_by_ssrf_guard(uri: str) -> str | None:
    """Return why an SSRF-safe JWKS fetch can never reach this URI, or None.

    fastmcp reports an SSRF block at DEBUG and turns it into an ordinary 401, so
    a JWKS URI the guard will always refuse looks in production exactly like
    every token being invalid. This lifts the statically decidable half of that
    into a startup failure.

    Only what can be judged without a lookup is checked: the scheme, and a host
    written as an IP literal. A hostname that resolves to a private address is
    deliberately not detected -- resolving names during configuration validation
    would make startup depend on DNS, and the answer could differ by the time
    the fetch happens anyway.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "https":
        return (
            f"scheme {parsed.scheme!r} is refused: SSRF-safe JWKS fetching "
            "requires HTTPS"
        )

    hostname = parsed.hostname
    if not hostname:
        return "the URI has no host"

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        # A name, not a literal. Nothing further is decidable without DNS.
        return None

    if not address.is_global or address.is_multicast:
        return (
            f"address {hostname} is not publicly routable, and SSRF-safe JWKS "
            "fetching refuses loopback, link-local, private and reserved ranges"
        )
    return None


class _PrefixedNamesOnly(PydanticBaseSettingsSource):
    """The env file's values, without the names that lack the prefix (#283, #368).

    The file may be shared with other programs, so a name such as
    ``DATABASE_URL`` is skipped, where it stopped startup as an unknown
    setting. An unknown name that carries the prefix still stops startup: it
    is meant for this server and is mistyped. The shell environment's unknown
    names were never read, so a mistyped one there is not reported.
    """

    def __init__(self, settings_cls: type[BaseSettings], file: DotEnvSettingsSource):
        super().__init__(settings_cls)
        self._file = file

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        # Unused: __call__ is overridden, as in pydantic-settings' own sources.
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        prefix = self._file.env_prefix.lower()
        names = set(self._file.env_vars)
        unprefixed = {n for n in names if not n.startswith(prefix)}
        # A name present both ways is the prefixed one's to report.
        unprefixed -= {n[len(prefix) :] for n in names if n.startswith(prefix)}
        return {
            key: value for key, value in self._file().items() if key not in unprefixed
        }


class Settings(BaseSettings):
    """Application settings with environment variable support.

    All settings can be overridden via environment variables with FINOS_MCP_ prefix.
    Example: FINOS_MCP_LOG_LEVEL=DEBUG

    A dotenv file is read only when ``FINOS_MCP_ENV_FILE`` names it, and a
    variable set in the environment wins over the same variable in the file.
    """

    def __init__(self, **values: Any) -> None:
        # An explicit _env_file (tests, tooling) is honoured as given. Otherwise
        # the file is the one the operator named, or none: never the working
        # directory's, which on stdio belongs to the client (#283). A named
        # file that is not there is refused rather than skipped, so a wrong
        # path cannot start the server on defaults in silence.
        if "_env_file" not in values:
            named = os.environ.get(ENV_FILE_VARIABLE)
            if named is not None and not Path(named).is_file():
                raise ValueError(
                    f"{ENV_FILE_VARIABLE} names {named!r}, which is not a file"
                )
            values["_env_file"] = named
        super().__init__(**values)

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # Network Configuration
    http_timeout: PositiveInt = Field(
        default=30,
        ge=5,
        le=300,
        description=(
            "Seconds one outbound request may take in all: connecting, the "
            "attempts repeated when it gets no answer, and the body (5-300)"
        ),
    )

    # Repository Configuration
    base_url: str = Field(
        default="https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs",
        description=(
            "Base URL for the FINOS AI Governance Framework repository. This is the "
            "single source of truth for the content target: repository owner, name, "
            "ref and path prefix are all derived from it (see security.repo_target)."
        ),
    )

    # Cache Configuration
    enable_cache: bool = Field(
        default=True,
        description="Enable in-memory caching of fetched documents",
    )

    cache_max_size: PositiveInt = Field(
        default=1000,
        ge=10,
        le=50000,
        description="Maximum number of documents to cache in memory (10-50000 range)",
    )

    cache_ttl_seconds: PositiveInt = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Default time-to-live for cached documents in seconds (1min-24hrs)",
    )

    # Removed cache_cleanup_interval - automatic cleanup is sufficient

    # Development Configuration
    debug_mode: bool = Field(
        default=False,
        description="Enable debug mode with additional logging and error details",
    )

    # Server Configuration
    server_name: str = Field(
        default="finos-ai-governance",
        description="MCP server name identifier",
    )

    mcp_transport: Literal["stdio", "http", "streamable-http", "sse"] = Field(
        default="stdio",
        description="MCP server transport mode",
    )
    mcp_host: str = Field(
        default="127.0.0.1",
        description="Host binding for HTTP/SSE transports",
    )
    mcp_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port binding for HTTP/SSE transports (1-65535)",
    )

    # MCP Authentication Configuration
    mcp_auth_enabled: bool = Field(
        default=False,
        description="Enable JWT authentication at the MCP server boundary",
    )
    mcp_auth_jwks_uri: str | None = Field(
        default=None,
        description="JWKS endpoint for JWT signature validation",
    )
    mcp_auth_public_key: SecretStr | None = Field(
        default=None,
        description="PEM-encoded public key for JWT validation (use instead of JWKS URI)",
    )
    mcp_auth_issuer: str | None = Field(
        default=None,
        description="Expected JWT issuer claim (iss)",
    )
    mcp_auth_audience: str | None = Field(
        default=None,
        description="Expected JWT audience claim (aud)",
    )
    mcp_auth_required_scopes: str | None = Field(
        default=None,
        description="Comma-separated required OAuth scopes (e.g. governance:read,governance:write)",
    )
    mcp_auth_base_url: str | None = Field(
        default=None,
        description=(
            "Public URL clients use to reach this server (e.g. "
            "https://mcp.example.com). When set on a networked transport with "
            "auth enabled, the server publishes OAuth protected-resource "
            "metadata (RFC 9728) so a client can discover where to sign in."
        ),
    )
    allow_insecure_http: bool = Field(
        default=False,
        description=(
            "Permit networked transports to start without authentication. "
            "Local development only - never set this where anything else can "
            "reach the port."
        ),
    )
    allow_insecure_jwks_uri: bool = Field(
        default=False,
        description=(
            "Fetch the JWKS URI without SSRF protection: permits plain HTTP and "
            "loopback, link-local and private addresses. Needed only when the "
            "identity provider is an internal service. It also re-permits "
            "cleartext retrieval of the keys that decide which tokens are trusted."
        ),
    )

    # GitHub API Configuration
    github_token: SecretStr | None = Field(
        default=None,
        description="GitHub personal access token for API access (optional, increases rate limits)",
    )

    # Discovery cache directory. The default is the user's cache directory,
    # never the working directory (#293).
    discovery_cache_dir: str | None = Field(
        default=None,
        description=(
            "Absolute path for the GitHub discovery cache directory. "
            "Defaults to finos-mcp/discovery under XDG_CACHE_HOME, or "
            "~/.cache, when unset. A directory that cannot be used is not "
            "replaced: the listing is kept in memory."
        ),
    )

    # DoS Protection Configuration
    dos_max_requests_per_minute: PositiveInt = Field(
        default=600,
        ge=10,
        le=2000,
        description="Maximum requests per client per minute enforced by DoS protection",
    )
    dos_max_concurrent_requests: PositiveInt = Field(
        default=10,
        ge=1,
        le=200,
        description="Maximum concurrent requests per client enforced by DoS protection",
    )
    readiness_probe_interval_seconds: PositiveInt = Field(
        default=30,
        ge=5,
        le=3600,
        description=(
            "Seconds between the requests a networked server sends to the "
            "content host to decide what GET /readyz answers"
        ),
    )
    dos_trusted_proxies: str | None = Field(
        default=None,
        description=(
            "Comma-separated CIDRs of trusted reverse proxies (e.g. 127.0.0.1/32). "
            "When set and the peer address matches one of them, X-Forwarded-For is "
            "used to key rate limits. Unset means the header is ignored and the "
            "direct peer address is used."
        ),
    )

    model_config = {
        # No file by default; __init__ passes the one ENV_FILE_VARIABLE names.
        "env_file": None,
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "env_prefix": "FINOS_MCP_",
    }

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """The named file is read for its ``FINOS_MCP_`` names only (#368)."""
        if not isinstance(dotenv_settings, DotEnvSettingsSource):
            raise TypeError(f"unexpected dotenv source {dotenv_settings!r}")
        return (
            init_settings,
            env_settings,
            _PrefixedNamesOnly(settings_cls, dotenv_settings),
            file_secret_settings,
        )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is supported by Python logging."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()

    @field_validator("github_token", mode="before")
    @classmethod
    def validate_github_token(cls, v: object) -> object:
        """Blank means not set; whitespace and one pair of quotes are removed.

        No check of the token's form: a validator's ValueError is reported by
        pydantic with the input value, which put a refused token on stderr in
        full, and GitHub answers a wrong token with 401 anyway (#289). A pair
        of matching quotes around it is removed, not refused: a shell or a
        dotenv file keeps quotes that are nested or escaped, and the token
        was sent with them, refused with a 401 that did not say why (#369).
        """
        if isinstance(v, SecretStr):
            v = v.get_secret_value()
        if v is None or not isinstance(v, str):
            return None
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1].strip()
        return v or None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Refuse a base URL the content client would refuse on every fetch.

        The client requests ``https`` only, never ``localhost`` or a
        non-public address literal, so a base URL outside that started a
        server on which every document fetch failed as "the host does not
        answer" (#298). The check is the client's own. A query or a fragment
        is refused as well: document paths are appended to this URL.
        """
        reason = why_not_a_fetch_target(v)
        if reason is None:
            parsed = urlparse(v)
            if parsed.query:
                reason = "it carries a query, and document paths are appended to it"
            elif parsed.fragment:
                reason = "it carries a fragment, and document paths are appended to it"
        if reason:
            raise ValueError(f"Base URL {v!r} is refused: {reason}")
        return v.rstrip("/")

    @field_validator("mcp_auth_jwks_uri")
    @classmethod
    def validate_mcp_auth_jwks_uri(cls, v: str | None) -> str | None:
        """Validate optional JWKS URL when provided."""
        if v is None or v.strip() == "":
            return None
        parsed = urlparse(v.strip())
        if not parsed.scheme or parsed.scheme not in ["http", "https"]:
            raise ValueError("MCP auth JWKS URI must be a valid HTTP or HTTPS URL")
        if not parsed.netloc:
            raise ValueError("MCP auth JWKS URI must include a domain")
        return v.strip().rstrip("/")

    @field_validator("mcp_auth_issuer", "mcp_auth_audience")
    @classmethod
    def strip_mcp_auth_claim(cls, v: str | None) -> str | None:
        """Remove surrounding whitespace; a blank value means not set.

        A token's claim is compared against the setting as held, so a trailing
        newline from a secrets file failed every token (#281).
        """
        if v is None or v.strip() == "":
            return None
        return v.strip()

    @field_validator("mcp_auth_public_key", mode="before")
    @classmethod
    def read_public_key_newlines(cls, v: object) -> object:
        """Blank means not set; a literal ``\\n`` is a line break.

        A one-line PEM with ``\\n`` written out is what ``.env.example`` shows
        and what a shell export of such a line produces, and a PEM cannot
        legitimately contain the two characters (#287).
        """
        if isinstance(v, SecretStr):
            v = v.get_secret_value()
        if v is None or not isinstance(v, str) or v.strip() == "":
            return None
        return v.strip().replace("\\n", "\n")

    @field_validator("mcp_auth_base_url")
    @classmethod
    def validate_mcp_auth_base_url(cls, v: str | None) -> str | None:
        """Validate the optional public URL of this server.

        Checked as the issuer is: fastmcp builds an ``AnyHttpUrl`` from it at
        import, so a value pydantic refuses must be refused here, by name,
        rather than exit the server with a traceback (#319).
        """
        if v is None or v.strip() == "":
            return None
        value = v.strip()
        reason = _why_not_an_http_url(value)
        if reason:
            raise ValueError(f"MCP auth base URL {value!r} is refused: {reason}")
        return value.rstrip("/")

    @field_validator("mcp_auth_required_scopes")
    @classmethod
    def validate_mcp_auth_required_scopes(cls, v: str | None) -> str | None:
        """Normalize optional comma-separated scope list."""
        if v is None:
            return None
        normalized = ",".join(scope.strip() for scope in v.split(",") if scope.strip())
        return normalized or None

    @field_validator("mcp_host")
    @classmethod
    def validate_mcp_host(cls, v: str) -> str:
        """Validate optional MCP host setting."""
        host = v.strip()
        if not host:
            raise ValueError("MCP host cannot be empty")
        return host

    @property
    def repo_target(self) -> RepoTarget:
        """Repository coordinates derived from base_url.

        Every outbound content target - GitHub API URLs, discovery listings and
        raw downloads - is built from this one value, so the API and raw paths
        cannot point at different repositories.

        Raises:
            ValueError: If base_url cannot address a repository. validate_startup
                surfaces this as a configuration error.
        """
        return resolve_repo_target(self.base_url)

    @property
    def mcp_auth_scopes_list(self) -> list[str]:
        """Return auth required scopes as a normalized list."""
        if not self.mcp_auth_required_scopes:
            return []
        return [
            scope.strip()
            for scope in self.mcp_auth_required_scopes.split(",")
            if scope.strip()
        ]

    @property
    def dos_trusted_proxy_entries(self) -> list[str]:
        """Return the configured trusted-proxy CIDRs as raw, stripped strings."""
        if not self.dos_trusted_proxies:
            return []
        return [
            entry.strip()
            for entry in self.dos_trusted_proxies.split(",")
            if entry.strip()
        ]

    @functools.cached_property
    def dos_trusted_proxy_networks(
        self,
    ) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        """Return trusted-proxy CIDRs as parsed networks.

        Parsed once and cached because this is consulted on every tool call.
        Unparseable entries are skipped here rather than raising; validate_startup
        rejects them outright, so a running server never holds a partly-parsed
        allowlist without having said so at startup.
        """
        networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for entry in self.dos_trusted_proxy_entries:
            try:
                networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                continue
        return networks

    @property
    def _log_format(self) -> str:
        """Log record format string for the current mode."""
        return (
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            if self.debug_mode
            else "%(name)s - %(levelname)s - %(message)s"
        )

    def configure_logging(self) -> None:
        """Configure Python logging based on settings."""
        # Pass arguments explicitly. basicConfig is an overloaded stub, and
        # splatting a heterogeneous dict into it does not type-check; the
        # suppression that needed broke whenever mypy changed which error
        # code it reported.
        logging.basicConfig(
            level=self.log_level,
            format=self._log_format,
            datefmt="%Y-%m-%d %H:%M:%S" if self.debug_mode else None,
        )

        if self.debug_mode:
            # Enable debug logging for httpx in debug mode
            logging.getLogger("httpx").setLevel(logging.DEBUG)

    def validate_startup(self) -> None:
        """Validate configuration at startup.

        Raises:
            ValueError: If configuration is invalid for startup.

        """
        errors = []

        # Bounds on one field (a port range, a cache size, a timeout floor)
        # are declared on the field and enforced by pydantic before this
        # runs; checks that repeated them here could not fail (#325). What
        # follows is what pydantic cannot state: a relation between fields.

        # base_url is the only repository setting, so it has to be resolvable
        # into owner/repo/ref here rather than failing on the first fetch.
        try:
            _ = self.repo_target
        except ValueError as e:
            errors.append(f"Invalid base_url: {e}")

        if self.mcp_transport != "stdio":
            # Fail closed: a networked transport without authentication serves
            # every tool and prompt to anyone who can reach the port. stdio is
            # exempt because it has no network boundary to authenticate.
            if not self.mcp_auth_enabled and not self.allow_insecure_http:
                errors.append(
                    f"mcp_transport={self.mcp_transport} exposes a network endpoint, "
                    "so FINOS_MCP_MCP_AUTH_ENABLED=true is required. "
                    "For local development only, set "
                    "FINOS_MCP_ALLOW_INSECURE_HTTP=true to override."
                )
            # The published metadata tells clients where to present bearer
            # tokens. A plain-http address there sends them unencrypted (#323).
            if (
                self.mcp_auth_base_url
                and urlparse(self.mcp_auth_base_url).scheme == "http"
                and not self.allow_insecure_http
            ):
                errors.append(
                    f"mcp_auth_base_url {self.mcp_auth_base_url} is plain http: "
                    "clients would be told to present bearer tokens to an "
                    "unencrypted address. Use https, or for local development "
                    "only set FINOS_MCP_ALLOW_INSECURE_HTTP=true."
                )

        if self.mcp_auth_enabled:
            if not self.mcp_auth_issuer:
                errors.append("mcp_auth_issuer is required when mcp_auth_enabled=true")
            if not self.mcp_auth_audience:
                errors.append(
                    "mcp_auth_audience is required when mcp_auth_enabled=true"
                )
            if not self.mcp_auth_jwks_uri and not self.mcp_auth_public_key:
                errors.append(
                    "Either mcp_auth_jwks_uri or mcp_auth_public_key is required when mcp_auth_enabled=true"
                )
            if self.mcp_auth_jwks_uri and self.mcp_auth_public_key:
                errors.append(
                    "Configure only one of mcp_auth_jwks_uri or mcp_auth_public_key (not both)"
                )
            if self.mcp_auth_public_key:
                reason = _public_key_cannot_verify(
                    self.mcp_auth_public_key.get_secret_value()
                )
                if reason:
                    errors.append(
                        f"mcp_auth_public_key cannot verify tokens: {reason}. "
                        "Every token would be rejected at runtime."
                    )
            if self.mcp_auth_jwks_uri and not self.allow_insecure_jwks_uri:
                reason = _jwks_uri_blocked_by_ssrf_guard(self.mcp_auth_jwks_uri)
                if reason:
                    errors.append(
                        f"mcp_auth_jwks_uri {self.mcp_auth_jwks_uri} can never be "
                        f"fetched: {reason}. Every token would be rejected at "
                        "runtime. Use a public HTTPS JWKS endpoint, or set "
                        "FINOS_MCP_ALLOW_INSECURE_JWKS_URI=true if the identity "
                        "provider really is an internal service."
                    )
            # The published document names the issuer as the authorization
            # server, and a client goes to that address to sign in. An ``iss``
            # claim may be any string; an authorization server must be a URL
            # with a host. Without one the document cannot be built, or names
            # an address other than the one configured (#259).
            if (
                self.mcp_auth_base_url
                and self.mcp_auth_issuer
                and self.mcp_transport != "stdio"
            ):
                reason = _why_not_an_http_url(self.mcp_auth_issuer)
                if reason:
                    errors.append(
                        f"mcp_auth_issuer {self.mcp_auth_issuer} cannot be "
                        f"published as the authorization server: {reason}. "
                        "Unset FINOS_MCP_MCP_AUTH_BASE_URL to run without "
                        "sign-in discovery."
                    )

        # A trusted-proxy entry is permission to believe an X-Forwarded-For header,
        # which decides whose rate-limit bucket a request lands in. Both failure
        # modes below would let a caller choose their own bucket, so reject at
        # startup rather than degrade silently.
        for entry in self.dos_trusted_proxy_entries:
            try:
                network = ipaddress.ip_network(entry, strict=False)
            except ValueError:
                errors.append(
                    f"dos_trusted_proxies entry {entry!r} is not a valid CIDR or IP address"
                )
                continue
            if network.prefixlen == 0:
                errors.append(
                    f"dos_trusted_proxies entry {entry!r} matches every address, which "
                    "would trust X-Forwarded-For from any caller. List the specific "
                    "proxy ranges, or unset FINOS_MCP_DOS_TRUSTED_PROXIES to ignore "
                    "the header entirely."
                )

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(
                f"  - {err}" for err in errors
            )
            raise ValueError(error_msg)


class SettingsManager:
    """Singleton manager for the global settings instance."""

    _instance: Optional["SettingsManager"] = None
    _settings: Settings | None = None

    def __new__(cls) -> "SettingsManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_settings(self, reload: bool = False) -> Settings:
        """Get application settings singleton.

        Args:
            reload: If True, reload settings from environment/files.

        Returns:
            Settings instance.

        Raises:
            ValueError: If settings are invalid.

        """
        if self._settings is None or reload:
            try:
                self._settings = Settings()
                self._settings.validate_startup()
                self._settings.configure_logging()
            except (ValueError, TypeError, OSError, ImportError) as e:
                raise ValueError(f"Failed to load configuration: {e}") from e
            # Said once logging is configured, so it is seen. A deployer who
            # relied on the working directory's .env before #283 would
            # otherwise start on defaults with nothing to say why.
            if ENV_FILE_VARIABLE not in os.environ and Path(".env").is_file():
                logging.getLogger("finos-ai-governance-mcp").warning(
                    "A .env file is in the working directory and is not read; "
                    "set %s to the file the server should read",
                    ENV_FILE_VARIABLE,
                )

        return self._settings


# Global settings manager instance
_settings_manager = SettingsManager()


def get_settings(reload: bool = False) -> Settings:
    """Get application settings singleton.

    Args:
        reload: If True, reload settings from environment/files.

    Returns:
        Settings instance.

    Raises:
        ValueError: If settings are invalid.

    """
    return _settings_manager.get_settings(reload)


def validate_settings_on_startup() -> Settings:
    """Validate and configure settings during application startup.

    This function should be called early in the application lifecycle
    to ensure configuration is valid and logging is properly configured.

    Returns:
        Validated Settings instance.

    Raises:
        SystemExit: If configuration is critically invalid.

    """
    try:
        # The one place the settings are built on a start (#300): nothing
        # reads them at import, so there is nothing to reload.
        app_settings = get_settings()
        # Imported here, not at the top: finos_mcp.logging imports this module
        # for the settings, and the level can only be applied once they exist.
        from .logging import setup_structured_logging

        logger = setup_structured_logging()
        logger.info("Configuration loaded successfully")
        logger.debug("Base URL: %s", app_settings.base_url)
        # State the resolved coordinates plainly: base_url is the only place a
        # fork, branch or mirror is selected, and a ref containing a slash is
        # ambiguous in a raw URL. Logging what was resolved makes a wrong guess
        # visible instead of silent.
        target = app_settings.repo_target
        if target.github_api_available:
            logger.info(
                "Content repository: %s/%s at ref %s (path prefix %r)",
                target.owner,
                target.repo,
                target.ref,
                target.path_prefix,
            )
        else:
            logger.warning(
                "Content base_url host %s is not raw.githubusercontent.com, so the "
                "GitHub API is unavailable for it: documents are fetched over raw "
                "URLs only and discovery uses the static fallback lists.",
                urlparse(target.raw_base_url).hostname,
            )
        logger.debug("HTTP timeout: %ss", app_settings.http_timeout)
        logger.debug("Cache enabled: %s", app_settings.enable_cache)
        logger.info("MCP transport: %s", app_settings.mcp_transport)
        if app_settings.mcp_transport != "stdio":
            logger.info(
                "MCP bind address: %s:%s", app_settings.mcp_host, app_settings.mcp_port
            )
            # An unauthenticated networked transport is logged as an ERROR by
            # app._build_auth_provider, the one place that knows whether auth
            # is on; a line here read the override alone and wrote
            # "authentication disabled" while auth was on (#332).
            # Which identity the rate limiter keys on is not obvious from the
            # config alone, so state the resolved answer where an operator will
            # see it. DEBUG logs the key chosen per request for verification.
            logger.info(
                "DoS rate-limit keying: %s; trusted proxies: %s",
                "JWT subject, falling back to client address"
                if app_settings.mcp_auth_enabled
                else "client address",
                app_settings.dos_trusted_proxy_entries
                or "none (X-Forwarded-For ignored)",
            )
        logger.info("MCP auth enabled: %s", app_settings.mcp_auth_enabled)
        if (
            app_settings.mcp_auth_enabled
            and app_settings.mcp_transport != "stdio"
            and not _is_loopback(app_settings.mcp_host)
        ):
            # Not refused: a container needs the bind. Said once, at WARNING,
            # because the server cannot see what is in front of the port (#323).
            logger.warning(
                "MCP auth is on and the server binds %s, not loopback: bearer "
                "tokens reach this port over plain HTTP unless the platform "
                "terminates TLS in front of it",
                app_settings.mcp_host,
            )
        if app_settings.mcp_auth_enabled:
            logger.info(
                "MCP auth issuer configured: %s", bool(app_settings.mcp_auth_issuer)
            )
            logger.info(
                "MCP auth audience configured: %s", bool(app_settings.mcp_auth_audience)
            )
            logger.info(
                "MCP auth required scopes: %s", app_settings.mcp_auth_scopes_list
            )

        # Security status logging
        if app_settings.github_token:
            logger.info("GitHub token configured - enhanced rate limits active")
            logger.debug("Rate limiting: Enhanced mode (5000 requests/hour)")
        else:
            logger.warning(
                "No GitHub token configured - limited to 60 requests/hour. "
                "Consider adding FINOS_MCP_GITHUB_TOKEN for better reliability"
            )
        logger.debug("Debug mode: %s", app_settings.debug_mode)

        return app_settings

    except ValueError as e:
        # Print to stderr since logging might not be configured yet
        print(f"❌ Configuration Error: {e}", file=__import__("sys").stderr)
        print(
            "\n💡 Check your environment variables, or the file "
            f"{ENV_FILE_VARIABLE} names.",
            file=__import__("sys").stderr,
        )
        raise SystemExit(1) from e
    except (RuntimeError, ImportError, OSError, MemoryError) as e:
        print(f"❌ Unexpected configuration error: {e}", file=__import__("sys").stderr)
        raise SystemExit(1) from e
