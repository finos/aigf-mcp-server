"""The server has one version, and every surface that states it agrees (#194).

Three places tell someone outside the process which build is running: the
``initialize`` result, ``get_service_health`` and the ``User-Agent`` on outgoing
requests. ``initialize`` and the ``User-Agent`` read a ``server_version``
setting while ``get_service_health`` read the package, so setting
``FINOS_MCP_SERVER_VERSION`` made the server contradict itself, and
``.env.example`` set it to a version that was never built. The version is a
fact about the build, so the setting is gone.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import fastmcp
import pytest

import finos_mcp

_PROBE = """
import asyncio, json
from fastmcp import Client
from finos_mcp.content.fetch import HTTPClient
from finos_mcp.fastmcp_server import mcp

async def main():
    async with Client(mcp) as client:
        health = await client.call_tool("get_service_health", {})
        print(json.dumps({
            "initialize": client.server_info.version,
            "get_service_health": health.structured_content["version"],
            "user_agent": HTTPClient()._client.headers["User-Agent"],
        }))

asyncio.run(main())
"""


def _stated_versions(extra_env: dict[str, str]) -> dict[str, str]:
    """What a fresh server process states on each of its three surfaces."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        env={**os.environ, **extra_env},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    stated: dict[str, str] = json.loads(result.stdout.strip().splitlines()[-1])
    return stated


@pytest.mark.parametrize(
    "extra_env",
    [{}, {"FINOS_MCP_SERVER_VERSION": "9.9.9-override"}],
    ids=["default", "override-attempted"],
)
def test_every_surface_states_the_build_version(extra_env: dict[str, str]) -> None:
    build = finos_mcp.__version__
    assert build not in {"unknown", fastmcp.__version__}, (
        "precondition: the build version is distinguishable from the fallback "
        "and from fastmcp's, which is what initialize reports when left unset"
    )

    assert _stated_versions(extra_env) == {
        "initialize": build,
        "get_service_health": build,
        "user_agent": f"finos-mcp/{build}",
    }
