# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""``HTTPClient`` holds one ``httpx.AsyncClient`` for its whole life (#306).

The dynamic connection pool rebuilt the inner client on the first request
(its last adjustment started at 0.0, so the first request was always due;
one active request of twenty was under the low-utilisation threshold, so the
pool shrank) and closed the client in use under requests in flight. Measured:
after one fetch the inner client was a new object and the old one closed;
idle fetches 31 s apart shrank the limit 20, 16, 12, 9, 7, 5. The readiness
probe went through the same client with no retry, and the "redirects are not
followed" control rested on the rebuilt client's constructor, which no test
read.
"""

from __future__ import annotations

import ast
import inspect
import time
from typing import Any

import httpx
import pytest

from finos_mcp.content import fetch
from finos_mcp.content.fetch import HTTPClient

pytestmark = pytest.mark.unit

URL = (
    "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs/index.md"
)


class TestOneInnerClient:
    """Two requests far enough apart to be due for a resize use one client."""

    @pytest.mark.asyncio
    async def test_requests_31_seconds_apart_see_the_same_inner_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def answer(
            self: httpx.AsyncClient, request: httpx.Request, **_: Any
        ) -> httpx.Response:
            return httpx.Response(200, request=request, text="x")

        monkeypatch.setattr(httpx.AsyncClient, "send", answer)
        now = time.time()
        clock = [now]
        monkeypatch.setattr("finos_mcp.content.fetch.time.time", lambda: clock[0])

        client = HTTPClient()
        inner = client._client
        try:
            await client.get(URL)
            clock[0] = now + 31.0
            await client.get(URL)
            assert client._client is inner
            assert inner.is_closed is False
            assert inner.follow_redirects is False
        finally:
            await client.close()


class TestOneConstructorCall:
    """The redirect control reads one constructor, so there must be one."""

    def test_fetch_builds_one_httpx_async_client(self) -> None:
        tree = ast.parse(inspect.getsource(fetch))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "AsyncClient"
        ]
        assert len(calls) == 1, [call.lineno for call in calls]
