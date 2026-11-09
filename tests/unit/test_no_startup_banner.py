"""The server starts without the FastMCP banner and the request behind it.

Before FastMCP prints its banner it asks ``pypi.org`` for a newer version of
itself. A deployed server therefore contacted a host no document of this
project names, started about two seconds later when that host did not answer,
and printed an advert for a hosting service on standard error (#254).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from finos_mcp import fastmcp_main

pytestmark = pytest.mark.unit

#: Either of these in the environment removes the request by itself, so a test
#: that inherits one passes whatever the server does.
_FASTMCP_SWITCHES = ("FASTMCP_SHOW_SERVER_BANNER", "FASTMCP_CHECK_FOR_UPDATES")
_PROXY_VARIABLES = ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")


@pytest.mark.parametrize("transport", ["stdio", "http"])
async def test_each_transport_is_run_without_the_banner(
    monkeypatch: pytest.MonkeyPatch, transport: str
) -> None:
    run_async = AsyncMock()
    monkeypatch.setattr("finos_mcp.fastmcp_main.mcp.run_async", run_async)
    monkeypatch.setattr("finos_mcp.fastmcp_main.settings.mcp_transport", transport)

    await fastmcp_main._serve()

    assert run_async.await_args is not None
    assert run_async.await_args.kwargs["transport"] == transport
    assert run_async.await_args.kwargs.get("show_banner") is False


def test_an_idle_stdio_server_connects_to_nothing(tmp_path: Path) -> None:
    """A proxy that only listens sees no connection from a start.

    The FastMCP data directory is empty, so no earlier answer stands in for
    the request.
    """
    env = {
        name: value
        for name, value in os.environ.items()
        if name.upper() not in _PROXY_VARIABLES + _FASTMCP_SWITCHES
    }
    with socket.socket() as proxy:
        proxy.bind(("127.0.0.1", 0))
        proxy.listen()
        env["HTTPS_PROXY"] = f"http://127.0.0.1:{proxy.getsockname()[1]}"
        env["FASTMCP_HOME"] = str(tmp_path / "fastmcp")
        env["FINOS_MCP_DISCOVERY_CACHE_DIR"] = str(tmp_path)

        result = subprocess.run(
            [sys.executable, "-m", "finos_mcp.fastmcp_main"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            cwd=tmp_path,
            check=False,
        )

        proxy.settimeout(0)
        try:
            connection, _ = proxy.accept()
        except BlockingIOError:
            asked = None
        else:
            with connection:
                connection.settimeout(1)
                asked = connection.recv(200).decode(errors="replace")

    assert result.returncode == 0, result.stderr[-2000:]
    assert "Starting FINOS AI Governance MCP Server" in result.stderr
    assert asked is None, f"the server connected out at startup: {asked!r}"
    assert "gofastmcp.com" not in result.stderr, "the banner was printed"
