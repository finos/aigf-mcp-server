# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Plain HTTP where tokens travel is refused or named at startup (#323).

``mcp_auth_base_url`` accepted scheme ``http``, so the published metadata
could tell clients to present bearer tokens to an unencrypted address; the
bind host check was "not empty", and ``0.0.0.0`` with auth on logged one
INFO line. The CALM node rests on "the platform terminates TLS"; the server
cannot know that, but it can see the two cases where it is visibly false or
unverified. The insecure-auth override gets an ERROR line each start; these
got nothing.

An ``http`` public URL now stops startup unless ``FINOS_MCP_ALLOW_INSECURE_HTTP``
is set; a bind host other than loopback with auth on is a WARNING, not a
refusal, because a container needs it.
"""

from __future__ import annotations

import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from finos_mcp import config
from finos_mcp.config import Settings, validate_settings_on_startup

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def public_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )


def _auth_on(public_pem: str, **values: object) -> Settings:
    base: dict[str, object] = {
        "mcp_transport": "http",
        "mcp_host": "127.0.0.1",
        "mcp_auth_enabled": True,
        "mcp_auth_public_key": public_pem,
        "mcp_auth_issuer": "https://issuer.plain-http.test",
        "mcp_auth_audience": "finos-mcp-server",
    }
    base.update(values)
    return Settings(**base)


class TestAnHttpPublicUrl:
    def test_is_refused_at_startup(self, public_pem: str) -> None:
        settings = _auth_on(public_pem, mcp_auth_base_url="http://mcp.example.com")
        with pytest.raises(ValueError, match="mcp_auth_base_url") as refused:
            settings.validate_startup()
        assert "FINOS_MCP_ALLOW_INSECURE_HTTP" in str(refused.value), (
            "the refusal does not say how a local setup may proceed"
        )

    def test_is_permitted_by_the_insecure_override(self, public_pem: str) -> None:
        _auth_on(
            public_pem,
            mcp_auth_base_url="http://mcp.example.com",
            allow_insecure_http=True,
        ).validate_startup()

    def test_https_is_the_control(self, public_pem: str) -> None:
        _auth_on(
            public_pem, mcp_auth_base_url="https://mcp.example.com"
        ).validate_startup()


def _warnings_naming_the_host(
    host: str,
    public_pem: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> list[str]:
    """Run the startup check bound to ``host``; return the WARNING lines naming it."""
    for name in [key for key in os.environ if key.startswith("FINOS_MCP_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FINOS_MCP_MCP_TRANSPORT", "http")
    monkeypatch.setenv("FINOS_MCP_MCP_HOST", host)
    monkeypatch.setenv("FINOS_MCP_MCP_AUTH_ENABLED", "true")
    monkeypatch.setenv("FINOS_MCP_MCP_AUTH_PUBLIC_KEY", public_pem)
    monkeypatch.setenv("FINOS_MCP_MCP_AUTH_ISSUER", "https://issuer.plain-http.test")
    monkeypatch.setenv("FINOS_MCP_MCP_AUTH_AUDIENCE", "finos-mcp-server")
    monkeypatch.setattr(config._settings_manager, "_settings", None)
    # Read from stderr, as a deployer does: setup_structured_logging clears
    # the logger's handlers, the one caplog attaches with them.
    capsys.readouterr()
    validate_settings_on_startup()
    return [
        line
        for line in capsys.readouterr().err.splitlines()
        if '"level":"WARNING"' in line and host in line
    ]


class TestANonLoopbackBindWithAuthOn:
    def test_is_warned_about(
        self,
        public_pem: str,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        all_interfaces = "0.0.0.0"  # noqa: S104 - the bind this test is about
        lines = _warnings_naming_the_host(
            all_interfaces, public_pem, monkeypatch, capsys
        )
        assert len(lines) == 1, lines
        assert "TLS" in lines[0]

    def test_loopback_is_not(
        self,
        public_pem: str,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert (
            _warnings_naming_the_host("127.0.0.1", public_pem, monkeypatch, capsys)
            == []
        )
