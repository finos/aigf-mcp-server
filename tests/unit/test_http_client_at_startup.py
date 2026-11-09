"""A server that cannot build its HTTP client does not start.

The client was built on first use. ``httpx`` reads the proxy environment
variables when a client is constructed, so a proxy setting it cannot use (a
SOCKS proxy without the ``socksio`` package, a proxy URL with an unsupported
scheme) raised there, inside the first tool call. The server had started by
then: health reported 4 of 4 services healthy, the list tools served the
static catalog with no descriptions, and every document call answered "could
not be loaded. Retry later." though no retry could succeed (#250).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from finos_mcp import fastmcp_main

pytestmark = pytest.mark.unit

_PROXY_VARIABLES = ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")

#: httpx refuses this scheme when the client is constructed, whichever
#: optional packages are installed.
_UNUSABLE_PROXY = "ftp://proxy.invalid:1"


async def test_the_server_is_not_started_when_the_client_cannot_be_built(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    cause = ImportError("Using SOCKS proxy, but the 'socksio' package is not installed")
    monkeypatch.setattr(fastmcp_main, "get_http_client", AsyncMock(side_effect=cause))
    serve = AsyncMock()
    monkeypatch.setattr(fastmcp_main, "_serve", serve)

    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit) as stopped:
        await fastmcp_main.main_async()

    assert stopped.value.code == 1
    serve.assert_not_called()
    reported = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("socksio" in message for message in reported), (
        f"the cause must be in the log a deployer reads; logged: {reported}"
    )


def _run_stdio_server(tmp_path: Path, **proxy: str) -> subprocess.CompletedProcess[str]:
    """Start the stdio server with stdin already at end of file."""
    env = {
        name: value
        for name, value in os.environ.items()
        if name.upper() not in _PROXY_VARIABLES
    }
    env.update(proxy)
    env["FINOS_MCP_DISCOVERY_CACHE_DIR"] = str(tmp_path)
    return subprocess.run(
        [sys.executable, "-m", "finos_mcp.fastmcp_main"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        cwd=tmp_path,
        check=False,
    )


def test_a_proxy_setting_httpx_cannot_use_stops_the_process(tmp_path: Path) -> None:
    result = _run_stdio_server(tmp_path, HTTPS_PROXY=_UNUSABLE_PROXY)

    assert result.returncode == 1, result.stderr[-2000:]
    assert "HTTP client" in result.stderr
    assert "ftp" in result.stderr, (
        "the message must carry httpx's own reason, which names the scheme"
    )


def test_without_the_proxy_setting_the_same_process_starts(tmp_path: Path) -> None:
    """Positive control: the exit above is caused by the proxy setting.

    A stdio server whose stdin is at end of file starts, finds nothing to
    read and exits 0.
    """
    result = _run_stdio_server(tmp_path)

    assert result.returncode == 0, result.stderr[-2000:]
    assert "Starting FINOS AI Governance MCP Server" in result.stderr
