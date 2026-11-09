# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The HTTP client built at startup is closed by ``cleanup_resources`` when no
tool call ran (#336).

``cleanup_resources`` documented its HTTP-client position as one that finds
nothing to do, because the content service's own close reaches the client.
Since #250 the client is built at startup, before any content service exists,
so a server that served no tool call shuts down with a client only the second
closer can close. This test runs that shutdown and reads the client.
"""

from __future__ import annotations

import pytest

from finos_mcp import fastmcp_main
from finos_mcp.content import fetch
from finos_mcp.content import service as service_module

pytestmark = pytest.mark.unit


async def test_the_startup_client_is_closed_without_a_content_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No tool call ran: the first closer has nothing. The client manager
    # starts as a fresh process does.
    monkeypatch.setattr(
        service_module._content_service_manager, "_content_service", None
    )
    monkeypatch.setattr(fetch._http_client_manager, "_http_client", None)
    monkeypatch.setattr(fetch._http_client_manager, "_loop", None)

    await fastmcp_main._build_http_client_or_stop()
    client = fetch.running_http_client()
    assert client is not None, "startup built no client"
    pool = client._client
    assert not pool.is_closed

    await fastmcp_main.cleanup_resources()

    assert pool.is_closed, "the client built at startup outlived shutdown"
    assert fetch.running_http_client() is None
