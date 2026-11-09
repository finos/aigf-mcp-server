"""Teardown that raises, and what the managers keep hold of afterwards.

The defect, in two places: ``HTTPClientManager.close_http_client()`` and
``CacheManager.close_cache()`` both clear their state *after* the await that
does the closing::

    await self._http_client.close()
    self._http_client = None      # <- not reached when the close raises
    self._loop = None

State cleared after an await is state kept when the await raises, and what is
kept is a resource whose teardown has already begun. Measured, before the fix:

* ``httpx.AsyncClient.aclose()`` sets ``_state = CLOSED`` **before** awaiting the
  transport, so a transport failure leaves a client httpx already considers
  closed -- and the manager still holding it. The next ``get_http_client()`` on
  the same loop passes the loop-identity check, finds ``_http_client`` set, and
  hands the dead client back. Every request through it then raises
  ``Cannot send a request, as the client has been closed.``
* ``TTLCache.close()`` cancels the background cleanup task and awaits it
  *before* ``await self.clear()``, so a failing ``clear()`` leaves a cache with
  no cleanup task running -- and the manager still holding it.

Why the tests below are not built on ``cleanup_resources()``. The rule in this
repo is to reproduce the production composition, and following it here would
have produced a test that cannot fail. Measured on the full stack -- content
service, cache and HTTP client, driven through ``cleanup_resources()`` with the
transport raising -- the HTTP client defect **self-heals**: position 1 fails,
and position 2 calls ``close_http_client()`` a second time, where ``aclose()``
short-circuits on the already-CLOSED state, returns cleanly, and clears the
fields. The transcript shows "HTTP client closing" twice and the singleton empty
at the end. So the composition that reproduces this one is a single close
followed by a re-acquire, which is what the issue scopes it to: a
restart-in-place, a test reusing the singleton, or a shutdown that does not exit.

The cache is not symmetrical, and the difference is the reason both are here.
``TTLCache`` has no equivalent of httpx's CLOSED flag, so position 3 re-enters
``clear()``, raises again, and the manager keeps the dead cache. That one has a
consequence on the path the server takes today, which
``test_a_failing_cache_close_is_reported_once`` pins, and the httpx fact the
HTTP client's scoping rests on is pinned by
``test_httpx_does_not_reach_the_transport_a_second_time``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest

from finos_mcp import fastmcp_main
from finos_mcp.content import cache as cache_module
from finos_mcp.content import fetch as fetch_module
from finos_mcp.content import service as service_module
from finos_mcp.content.fetch import close_http_client, get_http_client
from finos_mcp.content.service import get_content_service

#: The logger ``cleanup_resources()`` writes its shutdown summary to. Spelled
#: out rather than read off the module, so a rename has to be noticed here too.
CLEANUP_LOGGER = "finos-ai-governance-mcp.fastmcp_main"


@pytest.fixture(autouse=True)
def _restore_singletons() -> Iterator[None]:
    """These tests drive the process-wide managers, because that is the bug.

    All three are emptied first and put back afterwards. Emptying matters as
    much as restoring: a manager carrying another test's client would make the
    round-trip assertion below compare against the wrong object.
    """
    http, cache, service = (
        fetch_module._http_client_manager,
        cache_module._cache_manager,
        service_module._content_service_manager,
    )
    saved = (
        (http._http_client, http._loop),
        cache._cache,
        service._content_service,
    )
    http._http_client, http._loop = None, None
    cache._cache = None
    service._content_service = None
    try:
        yield
    finally:
        (
            (http._http_client, http._loop),
            cache._cache,
            service._content_service,
        ) = saved


def _raising_transport(
    client: object, message: str
) -> contextlib.AbstractContextManager[object]:
    """Make the client's real transport fail its close, and nothing else.

    Patched at the transport rather than at ``HTTPClient.close()`` on purpose:
    the load-bearing fact is what ``aclose()`` does to the client's own state
    *before* it delegates, and a patch further out would skip exactly that.
    """
    return patch.object(
        client._client._transport,  # type: ignore[attr-defined]
        "aclose",
        AsyncMock(side_effect=RuntimeError(message)),
    )


@pytest.mark.integration
async def test_a_client_whose_close_raised_is_not_handed_out_again() -> None:
    """The round trip is the assertion that carries weight.

    Asserting only that the manager's fields are ``None`` would pass against a
    version that never had the bug. What has to be shown is that the *next*
    caller gets a different client -- because before the fix it got the same
    one, and that one is dead.
    """
    manager = fetch_module._http_client_manager
    client = await get_http_client()

    # Preconditions. Without them a green result cannot distinguish this from
    # the discard branch, which clears its state before returning anyway.
    assert manager._http_client is client
    assert manager._loop is asyncio.get_running_loop(), (
        "not the same-loop branch; this test would be exercising the discard"
    )

    with _raising_transport(client, "transport is broken"):
        with pytest.raises(RuntimeError, match="transport is broken"):
            await close_http_client()

    # The measured httpx behaviour that makes retention a trap rather than an
    # untidiness: the client is already closed by the time the transport fails.
    assert client._client.is_closed, (
        "httpx did not mark the client closed, so keeping it would be harmless "
        "and this test is no longer reproducing the reported defect"
    )

    replacement = await get_http_client()
    try:
        assert replacement is not client, (
            "the manager handed back the client whose close had already failed"
        )
    finally:
        await replacement.close()


@pytest.mark.integration
async def test_httpx_does_not_reach_the_transport_a_second_time() -> None:
    """Pins the httpx behaviour the issue's scoping rests on, not this fix.

    ``close_http_client()`` runs twice during a shutdown --
    ``ContentService.close()`` at position 1, ``cleanup_resources()`` at
    position 2 -- and before this fix the second call is what cleared the
    retained client: ``httpx.AsyncClient.aclose()`` returns immediately when
    ``_state`` is already CLOSED, so it succeeded where the first had failed.
    That is a fact about httpx rather than about this code, and it is the entire
    reason the defect is scoped as unreachable in the current shutdown path. If a
    future httpx stops short-circuiting, that scoping becomes wrong.

    Asserted against the transport, not against the manager. An earlier revision
    called ``close_http_client()`` a second time and asserted the manager's
    fields were ``None`` -- which this fix's own ``finally`` guarantees, so the
    second call returned at the ``if self._http_client is None`` guard without
    reaching ``aclose()`` at all. Measured: one ``HTTPClient.close`` call across
    both invocations. It would have stayed green through any httpx change, which
    makes it exactly the tripwire that cannot trip.

    This one can: with the client's state forced back to OPENED before the second
    close, ``await_count`` reaches 2 and the last assertion fires. Measured.
    """
    client = await get_http_client()
    transport_close = AsyncMock(side_effect=RuntimeError("transport is broken"))

    with patch.object(
        client._client._transport,
        "aclose",
        transport_close,
    ):
        with pytest.raises(RuntimeError, match="transport is broken"):
            await close_http_client()

        assert transport_close.await_count == 1, (
            "the transport was never reached, so this is not measuring the close "
            "it claims to"
        )
        assert client._client.is_closed, "httpx did not mark the client closed"

        # The same client again, directly: the manager no longer holds it. The
        # raise is suppressed rather than allowed to propagate: an httpx that
        # reached the transport would raise here and the failure would read
        # "transport is broken" instead of the diagnostic below, which is the
        # sentence that says what actually changed. The suppression hides
        # nothing -- the only RuntimeError available is the mock's, and
        # await_count is what measures whether it was reached.
        with contextlib.suppress(RuntimeError):
            await client.close()

        assert transport_close.await_count == 1, (
            "httpx reached the transport for an already-closed client, so a "
            "failing close is no longer recovered by the second call at "
            "position 2 -- and issue #102's scoping is now wrong"
        )


@pytest.mark.integration
async def test_a_failing_cache_close_is_reported_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The cache defect has a consequence on the path the server takes today.

    ``TTLCache`` has no equivalent of httpx's CLOSED flag, so the second
    ``close_cache()`` -- position 3 of ``cleanup_resources()``, after position 1
    already failed -- re-enters ``clear()`` and raises again. The summary then
    names the cache as a second failed resource for a single failure:

        ERROR  Resource cleanup completed with errors in: content service, cache

    Measured, before the fix. One failure, two names, and an operator reading
    that line concludes two resources were stranded.
    """
    service = await get_content_service()
    cache = await service._get_cache()
    await service._get_http_client()

    with (
        patch.object(
            cache, "clear", AsyncMock(side_effect=RuntimeError("clear failed"))
        ),
        caplog.at_level(logging.ERROR, logger=CLEANUP_LOGGER),
    ):
        await fastmcp_main.cleanup_resources()

    summaries = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.ERROR and r.name == CLEANUP_LOGGER
    ]
    assert len(summaries) == 1, f"expected one ERROR summary, got {summaries}"
    assert "content service" in summaries[0], summaries[0]
    assert "cache" not in summaries[0], (
        f"one failing close was reported as two stranded resources: {summaries[0]!r}"
    )
