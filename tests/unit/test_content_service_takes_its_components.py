# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""``ContentService`` takes its HTTP client and cache, or asks for them each time (#313).

Its constructor took no arguments; it obtained both from the singletons on
first use and memoised them, which needed 55 lines of loop-change detection
(#123) to drop the copies the managers had already replaced, and left tests
reaching past the interface to install fakes. Now the constructor accepts an
``http_client`` and a ``cache``; when either is absent the service asks the
manager on each use and holds no copy, so the managers' rebinding is the only
rebinding there is.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from finos_mcp.content import fetch
from finos_mcp.content.cache import TTLCache, close_cache, get_cache
from finos_mcp.content.fetch import HTTPClient, close_http_client, get_http_client
from finos_mcp.content.service import ContentService

pytestmark = pytest.mark.unit


class _Client:
    closed = False

    async def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
async def _no_shared_singletons() -> Any:
    await close_http_client()
    await close_cache()
    yield
    await close_http_client()
    await close_cache()


async def test_given_components_are_the_ones_used_and_the_managers_build_none() -> None:
    client: Any = _Client()
    cache: TTLCache[str, Any] = TTLCache(max_size=2, default_ttl=10)
    service = ContentService(http_client=client, cache=cache)

    assert await service._get_http_client() is client
    assert await service._get_cache() is cache
    assert fetch.running_http_client() is None, "the manager built a client anyway"


async def test_closing_a_service_leaves_given_components_to_their_owner() -> None:
    client: Any = _Client()
    service = ContentService(http_client=client, cache=TTLCache(max_size=2))

    await service.close()

    assert client.closed is False


async def test_without_given_components_the_service_holds_no_copy() -> None:
    """After the manager replaces its client, the service uses the new one."""
    service = ContentService()
    first = await service._get_http_client()
    assert first is await get_http_client()

    await close_http_client()
    second = await service._get_http_client()

    assert isinstance(second, HTTPClient)
    assert second is not first, "the service kept a copy the manager had closed"
    assert second is await get_http_client()
    assert await service._get_cache() is await get_cache()


async def test_closing_a_service_without_given_components_closes_the_shared_ones() -> (
    None
):
    service = ContentService()
    client = await service._get_http_client()
    await service._get_cache()

    await service.close()

    assert client._client.is_closed
    assert fetch.running_http_client() is None


def test_the_shared_client_is_asked_for_without_arguments() -> None:
    """``get_http_client(settings)`` ignored its argument after the first call."""
    assert list(inspect.signature(get_http_client).parameters) == []
    assert list(
        inspect.signature(fetch.HTTPClientManager.get_http_client).parameters
    ) == ["self"]


def test_the_service_keeps_no_loop_of_its_own() -> None:
    service = ContentService()

    assert not hasattr(service, "_loop")
    assert not hasattr(service, "_rebind_if_the_loop_changed")
