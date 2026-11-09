# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The one fetch breaker opens on a failing host, not on a failing document.

Document fetches used to pass two breakers: ``HTTPClient``'s per host, fed per
retry attempt and counting only transport errors, and
``ContentService.fetch_circuit_breaker``, fed per call and the one ``/readyz``
read (#284, #307). The service breaker is gone; the client's per-host breaker
is the one, fed once per call, and it counts what says the host is failing:
no answer (a transport error or a timeout, after the retries), or an answer of
429 or 5xx. A 4xx or an unusable body is the host answering, and resets the
count as a served document would. Measured before #284: five calls for one 404
document opened the service breaker, a sixth call for a served document sent
no request, and ``/readyz`` answered 503.

Every test runs the real ``ContentService`` route over the real ``HTTPClient``
with its transport stubbed, and reads the breaker through ``is_refusing``, as
``/readyz`` does.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from finos_mcp.content.fetch import HTTPClient
from finos_mcp.content.service import ContentService
from finos_mcp.exceptions import GitHubRateLimitError

pytestmark = pytest.mark.unit

FIRST = "ri-1_first.md"
SECOND = "ri-2_second.md"
BODY = "---\ntitle: Second\n---\n\nServed.\n"


def _status(code: int) -> Callable[[httpx.Request], httpx.Response]:
    def _answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(code, request=request, text="x")

    return _answer


class _Transport:
    """Answers ``FIRST`` as told; serves ``SECOND``. Counts requests."""

    def __init__(self, first: Callable[..., httpx.Response] | BaseException) -> None:
        self.first = first
        self.requests: list[str] = []

    async def send(self, request: httpx.Request, **_: Any) -> httpx.Response:
        self.requests.append(str(request.url))
        if str(request.url).endswith(SECOND):
            return httpx.Response(200, request=request, text=BODY)
        if isinstance(self.first, BaseException):
            raise self.first
        return self.first(request)


Made = tuple[ContentService, HTTPClient, _Transport]


@pytest.fixture
async def service(
    monkeypatch: pytest.MonkeyPatch, fast_retries: None
) -> AsyncIterator[Callable[[Any], Made]]:
    services: list[ContentService] = []
    clients: list[HTTPClient] = []

    def _make(first: Any) -> Made:
        transport = _Transport(first)
        client = HTTPClient()
        monkeypatch.setattr(
            client._client,
            "send",
            transport.send,  # the stub, not the network
        )
        instance = ContentService(http_client=client)

        async def _nothing(*_: Any, **__: Any) -> None:
            return None

        async def _stored(*_: Any, **__: Any) -> bool:
            return True

        instance._cache_get_with_boundary = _nothing  # type: ignore[method-assign]
        instance._cache_set_with_boundary = _stored  # type: ignore[method-assign]
        services.append(instance)
        clients.append(client)
        return instance, client, transport

    yield _make
    for client in clients:
        await client.close()


def _refusing(instance: ContentService, client: HTTPClient) -> bool:
    return client.is_refusing(instance.settings.base_url)


ANSWERS = [
    pytest.param(_status(404), id="404"),
    pytest.param(_status(403), id="403"),
    pytest.param(
        lambda request: httpx.Response(
            301, request=request, headers={"location": "https://x.test/"}
        ),
        id="redirect",
    ),
]


@pytest.mark.parametrize("first", ANSWERS)
async def test_five_answers_for_one_document_do_not_open_the_breaker(
    service: Callable[[Any], Made], first: Any
) -> None:
    instance, client, transport = service(first)

    for _ in range(5):
        assert await instance.get_document("risk", FIRST) is None

    assert not _refusing(instance, client), (
        "five answers for one document made the server refuse every document"
    )
    document = await instance.get_document("risk", SECOND)
    assert document is not None
    assert transport.requests[-1].endswith(SECOND), (
        "the second document was not asked for"
    )


HOST_FAILURES = [
    pytest.param(httpx.ConnectError("connection refused"), id="connect"),
    pytest.param(httpx.ReadTimeout("read timed out"), id="timeout"),
    pytest.param(_status(503), id="503"),
    pytest.param(_status(429), id="429"),
]


@pytest.mark.parametrize("first", HOST_FAILURES)
async def test_five_host_failures_open_the_breaker(
    service: Callable[[Any], Made], first: Any
) -> None:
    instance, client, transport = service(first)

    for _ in range(5):
        # A 429 is reported to the caller as a rate limit (#248); the others
        # as no document.
        with contextlib.suppress(GitHubRateLimitError):
            assert await instance.get_document("risk", FIRST) is None

    assert _refusing(instance, client), (
        "five failures of the host left the breaker closed"
    )
    before = len(transport.requests)
    assert await instance.get_document("risk", SECOND) is None
    assert len(transport.requests) == before, "a refused fetch still sent a request"


async def test_a_call_counts_once_however_many_attempts_it_took(
    service: Callable[[Any], Made],
) -> None:
    """Four calls that got no answer are four failures, not twelve.

    The retry layer repeats a request that got no answer, three attempts in
    all. Fed per attempt, the breaker opened after two failed calls, where the
    deployment guide promises the fifth.
    """
    instance, client, transport = service(httpx.ConnectError("connection refused"))

    for _ in range(4):
        await instance.get_document("risk", FIRST)

    assert len(transport.requests) == 12, "each unanswered call retries twice"
    assert not _refusing(instance, client), "four unanswered calls opened the breaker"


async def test_a_server_error_is_not_retried(
    service: Callable[[Any], Made],
) -> None:
    """A 500 is an answer: one request, no retry, one failure counted."""
    instance, client, transport = service(_status(500))

    await instance.get_document("risk", FIRST)

    assert transport.requests == [f"{instance.settings.base_url}/_risks/{FIRST}"]
    assert client.circuit_breaker(instance.settings.base_url).failure_count == 1


async def test_an_answer_resets_the_count_of_host_failures(
    service: Callable[[Any], Made],
) -> None:
    """A 404 after four connect errors is the host back, as a 200 would be."""
    instance, client, transport = service(httpx.ConnectError("connection refused"))

    for _ in range(4):
        await instance.get_document("risk", FIRST)
    transport.first = _status(404)
    await instance.get_document("risk", FIRST)
    transport.first = httpx.ConnectError("connection refused")
    for _ in range(4):
        await instance.get_document("risk", FIRST)

    assert not _refusing(instance, client), (
        "an answer from the host did not reset the failure count"
    )
