# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The insecure-HTTP override is logged once, and only when auth is off (#332).

The startup summary in ``config`` wrote "INSECURE: serving ... with
authentication disabled" whenever ``FINOS_MCP_ALLOW_INSECURE_HTTP`` was set,
without reading ``mcp_auth_enabled``: measured with auth on, the ERROR line
was written and a verifier was built. With auth off, ``_build_auth_provider``
wrote the same fact a second time. The line now comes from the one place that
knows whether auth is on.

Both sites are driven the way a start drives them: the summary through
``validate_settings_on_startup`` on the environment, the provider through
``_build_auth_provider`` on the settings it built. The lines are read from
stderr, where the JSON handler writes them: ``validate_settings_on_startup``
rebuilds the application logger's handlers, which drops a caplog handler
attached before it, so a caplog capture here is empty and proves nothing. A
control line the summary always writes guards against an empty capture.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from finos_mcp.app import _build_auth_provider
from finos_mcp.config import _settings_manager, validate_settings_on_startup

pytestmark = pytest.mark.unit

SETTING = "FINOS_MCP_ALLOW_INSECURE_HTTP"
CONTROL = "MCP transport: http"


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


@pytest.fixture
def fresh_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No settings built yet, and no FINOS_MCP_ variable but the test's own."""
    for key in list(os.environ):
        if key.startswith("FINOS_MCP_"):
            monkeypatch.delenv(key)
    held = _settings_manager._settings
    _settings_manager._settings = None
    yield
    _settings_manager._settings = held


def _start(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    **environment: str,
) -> list[dict[str, Any]]:
    """Start as the server does and return every JSON log line written."""
    monkeypatch.setenv("FINOS_MCP_MCP_TRANSPORT", "http")
    monkeypatch.setenv("FINOS_MCP_MCP_HOST", "127.0.0.1")
    monkeypatch.setenv(SETTING, "true")
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    settings = validate_settings_on_startup()
    _build_auth_provider(settings)
    lines = [
        json.loads(line)
        for line in capsys.readouterr().err.splitlines()
        if line.startswith("{")
    ]
    assert any(CONTROL in line["message"] for line in lines), (
        f"the startup summary was not captured: {lines}"
    )
    return lines


def test_with_auth_on_the_override_is_not_announced_as_auth_off(
    fresh_settings: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    public_pem: str,
) -> None:
    lines = _start(
        monkeypatch,
        capsys,
        FINOS_MCP_MCP_AUTH_ENABLED="true",
        FINOS_MCP_MCP_AUTH_PUBLIC_KEY=public_pem,
        FINOS_MCP_MCP_AUTH_ISSUER="https://issuer.insecure-http.test",
        FINOS_MCP_MCP_AUTH_AUDIENCE="finos-mcp-server",
    )
    messages = [line["message"] for line in lines]
    assert not any("authentication disabled" in m for m in messages), messages
    assert not any("auth is DISABLED" in m for m in messages), messages
    assert not [
        line
        for line in lines
        if line["level"] == "ERROR" and SETTING in line["message"]
    ], messages


def test_with_auth_off_exactly_one_error_names_the_setting(
    fresh_settings: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = _start(monkeypatch, capsys)
    errors = [
        line["message"]
        for line in lines
        if line["level"] == "ERROR" and SETTING in line["message"]
    ]
    assert len(errors) == 1, errors
    assert "auth is DISABLED" in errors[0]
