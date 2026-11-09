# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""A document body comes from the content host, and from nowhere else (#312).

``get_document`` used to fall back to the GitHub Contents API whenever the raw
fetch returned nothing, which covered a 404, a rejected body, a timeout and an
open breaker alike, sending the token when set. Every such miss spent one of
the 60 requests an hour discovery depends on, and while the fetch breaker was
open every call went straight to the API. The fallback is gone: a document is
fetched from the host ``FINOS_MCP_BASE_URL`` names, once, and a throttle there
is still reported as one.

Every test runs the real ``ContentService`` over the real ``HTTPClient`` with
its transport stubbed to record the host of every request.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from finos_mcp.content.fetch import HTTPClient
from finos_mcp.content.service import ContentService
from finos_mcp.exceptions import GitHubRateLimitError

pytestmark = pytest.mark.unit

RISK = "ri-1_first.md"


class _Hosts:
    """Answers the content host as told; records every host asked."""

    def __init__(
        self, answer: Callable[[httpx.Request], httpx.Response] | BaseException
    ) -> None:
        self.answer = answer
        self.hosts: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.hosts.append(request.url.host)
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer(request)


Made = tuple[ContentService, _Hosts]


@pytest.fixture
async def service(fast_retries: None) -> AsyncIterator[Callable[[Any], Made]]:
    clients: list[HTTPClient] = []

    def _make(answer: Any) -> Made:
        hosts = _Hosts(answer)
        client = HTTPClient()
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(hosts))
        instance = ContentService(http_client=client)

        async def _nothing(*_: Any, **__: Any) -> None:
            return None

        instance._cache_get_with_boundary = _nothing  # type: ignore[method-assign]
        instance._cache_set_with_boundary = _nothing  # type: ignore[method-assign,assignment]
        clients.append(client)
        return instance, hosts

    yield _make
    for client in clients:
        await client.close()


def _status(code: int, **headers: str) -> Callable[[httpx.Request], httpx.Response]:
    return lambda request: httpx.Response(
        code, request=request, headers=headers, text="x"
    )


async def test_a_missing_document_costs_no_api_request(
    service: Callable[[Any], Made],
) -> None:
    instance, hosts = service(_status(404))

    assert await instance.get_document("risk", RISK) is None

    assert hosts.hosts == ["raw.githubusercontent.com"], hosts.hosts


async def test_an_unreachable_content_host_costs_no_api_request(
    service: Callable[[Any], Made],
) -> None:
    instance, hosts = service(httpx.ConnectError("connection refused"))

    assert await instance.get_document("risk", RISK) is None

    assert set(hosts.hosts) == {"raw.githubusercontent.com"}, hosts.hosts


async def test_a_throttled_content_host_is_reported_with_its_delay(
    service: Callable[[Any], Made],
) -> None:
    instance, hosts = service(_status(429, **{"Retry-After": "90"}))

    with pytest.raises(GitHubRateLimitError, match="90 seconds"):
        await instance.get_document("risk", RISK)

    assert hosts.hosts == ["raw.githubusercontent.com"], hosts.hosts
