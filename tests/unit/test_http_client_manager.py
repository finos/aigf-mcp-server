"""Branch coverage for the HTTPClientManager teardown guard and cleanup isolation.

These are the mocked companions to
``tests/integration/test_cross_loop_teardown.py``. That file reproduces the real
``RuntimeError: Event loop is closed`` against a live socket, which is the only
way to prove the bug exists; this file enumerates the branches around it, which
a real socket makes awkward to reach one at a time.

Neither file is sufficient alone. Mocks here can show that ``close()`` is not
awaited on a foreign loop, but never that awaiting it would have raised -- an
``AsyncMock`` is happy to be awaited from any loop. That gap is why the port of
these tests came with a socket-backed reproduction rather than on its own.

Isolation matters more than usual here. ``HTTPClientManager.__new__`` is
overridden to return ``cls._instance``, so ``HTTPClientManager()`` -- and even
``HTTPClientManager.__new__(HTTPClientManager)`` -- hands back the process-wide
singleton rather than a fresh object. Tests written that way silently mutate the
manager that every other test in the session shares. ``object.__new__`` is used
instead, and the autouse fixture below fails the test that forgets.
"""

import asyncio
import logging
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finos_mcp import fastmcp_main
from finos_mcp.content import fetch as fetch_module
from finos_mcp.content.fetch import HTTPClientManager


@pytest.fixture(autouse=True)
def _global_manager_is_untouched() -> Iterator[None]:
    """Fail any test in this file that reaches the process-wide singleton.

    Sentinels rather than a before/after comparison, because a test that writes
    to the singleton and then calls close_http_client() erases its own evidence:
    the close resets both attributes to None, so a snapshot taken before and
    after would match while the singleton was in fact driven throughout. Marking
    the state with values no production path produces detects the write itself.

    Restores before asserting, so a test that does reach the global is reported
    here rather than corrupting whatever runs next.
    """
    manager = fetch_module._http_client_manager
    saved = (manager._http_client, manager._loop)
    # Typed Any: the sentinels are deliberately neither a client nor a loop.
    client_sentinel: Any = object()
    loop_sentinel: Any = object()
    manager._http_client, manager._loop = client_sentinel, loop_sentinel
    try:
        yield
        touched = (manager._http_client, manager._loop) != (
            client_sentinel,
            loop_sentinel,
        )
    finally:
        manager._http_client, manager._loop = saved
    assert not touched, (
        "this test wrote to the global _http_client_manager; build the manager "
        "with object.__new__(HTTPClientManager), which HTTPClientManager() and "
        "HTTPClientManager.__new__(HTTPClientManager) both fail to do"
    )


def _isolated_manager(client: Any, loop: Any) -> HTTPClientManager:
    """A manager that is genuinely not the singleton, holding the given state."""
    manager = object.__new__(HTTPClientManager)
    manager._http_client = client
    manager._loop = loop
    assert manager is not fetch_module._http_client_manager
    return manager


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.close = AsyncMock()
    return client


def _recording_closers(
    failing: dict[str, Exception] | None = None,
) -> tuple[list[str], dict[str, AsyncMock]]:
    """Closers that record every attempt, whether or not they then raise.

    Recording before raising is what makes "all three failed" distinguishable
    from "we stopped after the first" -- the exact confusion the single
    try/except produced.
    """
    failing = failing or {}
    attempted: list[str] = []

    def make(name: str) -> AsyncMock:
        async def close() -> None:
            attempted.append(name)
            if name in failing:
                raise failing[name]

        return AsyncMock(side_effect=close)

    closers = {name: make(name) for name in ("content service", "HTTP client", "cache")}
    return attempted, closers


async def _run_cleanup(closers: dict[str, AsyncMock]) -> None:
    """Drive cleanup_resources() with the given closers in place."""
    with (
        patch.object(fastmcp_main, "close_content_service", closers["content service"]),
        patch.object(fastmcp_main, "close_http_client", closers["HTTP client"]),
        patch.object(fastmcp_main, "close_cache", closers["cache"]),
    ):
        await fastmcp_main.cleanup_resources()


@pytest.mark.unit
class TestCloseHTTPClientLoopGuard:
    """close_http_client() closes only what the running loop itself created."""

    async def test_no_client_is_a_noop(self) -> None:
        """Nothing to close, and nothing to raise about."""
        manager = _isolated_manager(client=None, loop=None)

        await manager.close_http_client()

        assert manager._http_client is None

    async def test_client_from_this_loop_is_really_closed(self) -> None:
        """The ordinary path: same loop, so the transport can be torn down."""
        client = _mock_client()
        manager = _isolated_manager(client, asyncio.get_running_loop())

        await manager.close_http_client()

        client.close.assert_awaited_once()
        assert manager._http_client is None
        assert manager._loop is None

    async def test_a_close_that_raises_still_drops_the_client(self) -> None:
        """The reference must go whether or not the close succeeded.

        ``httpx.AsyncClient.aclose()`` sets ``_state = CLOSED`` before it awaits
        the transport, so a transport failure leaves a client httpx already
        considers closed. Keeping it means the next ``get_http_client()`` on this
        loop passes the identity check, finds ``_http_client`` set, and hands the
        dead client back.

        The round trip is the assertion that matters -- checking only that the
        fields are ``None`` would pass against a version that never had the bug.
        The socket-backed companion is in
        ``tests/integration/test_teardown_failure.py``; what this adds is that
        the raise propagates, which a ``finally`` preserves and an ``except``
        would not.
        """
        client = _mock_client()
        client.close = AsyncMock(side_effect=RuntimeError("transport is broken"))
        manager = _isolated_manager(client, asyncio.get_running_loop())

        with pytest.raises(RuntimeError, match="transport is broken"):
            await manager.close_http_client()

        assert manager._http_client is None
        # A state assertion, not a behavioural one, and worth being exact about.
        # Dropping ``self._loop = None`` from the finally does fail this test and
        # two others -- but only because they read the field directly. Nothing
        # behaves differently: with ``_http_client`` cleared, get_http_client()
        # rebuilds whether the recorded loop matches the running one, differs
        # from it, or is closed. Measured, after predicting the opposite.
        assert manager._loop is None

        replacement = await manager.get_http_client()
        try:
            assert replacement is not client, (
                "the manager handed back the client whose close had failed"
            )
        finally:
            await replacement.close()

    async def test_client_from_a_closed_loop_is_discarded(self) -> None:
        """The reported bug: FastMCP's loop was gone by the time cleanup ran.

        Awaiting close() here is what raised ``RuntimeError: Event loop is
        closed`` in production. The mock cannot reproduce that raise, so what is
        asserted is the decision -- close() must not be attempted at all.
        """
        client = _mock_client()
        dead_loop = asyncio.new_event_loop()
        dead_loop.close()
        manager = _isolated_manager(client, dead_loop)

        await manager.close_http_client()

        client.close.assert_not_awaited()
        assert manager._http_client is None
        assert manager._loop is None

    async def test_client_from_a_different_live_loop_is_discarded(self) -> None:
        """Liveness is not the test; provenance is.

        A foreign loop that happens to still be open is just as unable to have
        its transports closed from here, so the identity check must reject it
        without consulting is_closed().
        """
        client = _mock_client()
        foreign_loop = asyncio.new_event_loop()
        try:
            assert not foreign_loop.is_closed()
            manager = _isolated_manager(client, foreign_loop)

            await manager.close_http_client()
        finally:
            foreign_loop.close()

        client.close.assert_not_awaited()
        assert manager._http_client is None
        assert manager._loop is None

    async def test_client_of_unrecorded_provenance_is_discarded(self) -> None:
        """_loop is None means unknown, which is not the same as safe.

        The commit this was ported from closed the client here, calling it "the
        conservative-but-safe fallback". It is neither: a client whose creating
        loop was never recorded is exactly the client whose transports we cannot
        reason about, and calling aclose() on one is the operation that raises.
        Reproduced before inverting it -- with a real pooled connection and
        _loop cleared, the lenient branch raises RuntimeError.
        """
        client = _mock_client()
        manager = _isolated_manager(client, loop=None)

        await manager.close_http_client()

        client.close.assert_not_awaited()
        assert manager._http_client is None


@pytest.mark.unit
class TestCleanupResourcesIsolation:
    """One failing close must not strand the resources that follow it."""

    async def test_every_resource_is_closed_in_order(self) -> None:
        """The happy path, and the control for the failure cases below."""
        attempted, closers = _recording_closers()

        await _run_cleanup(closers)

        assert attempted == ["content service", "HTTP client", "cache"]

    async def test_a_first_failure_does_not_strand_the_rest(self) -> None:
        """A raise in the first closer must not strand the two behind it.

        ``close_content_service()`` is what actually runs first, and it *can*
        raise: ``ContentService.close()`` attempts both of its closes and then
        raises once if either failed, and ``close_content_service()`` lets that
        through. So this is not a hypothetical branch -- it is the failure a real
        shutdown has. An earlier revision of this docstring said the opposite,
        which was true of the code it was written against and was left behind by
        the commit that removed the swallow.

        The closer is still patched rather than driven through a real
        ``ContentService``, because what this test is about is the *isolation* --
        that positions 2 and 3 still run. The production composition is exercised
        in ``tests/unit/test_content_service.py``.
        """
        attempted, closers = _recording_closers(
            {"content service": RuntimeError("Event loop is closed")}
        )

        await _run_cleanup(closers)

        assert attempted == ["content service", "HTTP client", "cache"]

    async def test_a_middle_failure_does_not_strand_the_last(self) -> None:
        """Cache must still be closed when the HTTP client's close raises."""
        attempted, closers = _recording_closers(
            {"HTTP client": RuntimeError("Event loop is closed")}
        )

        await _run_cleanup(closers)

        assert attempted == ["content service", "HTTP client", "cache"]

    async def test_all_three_are_attempted_even_when_all_three_fail(self) -> None:
        """Completing without raising is not enough; each close must be tried.

        Asserted on the recorded attempts rather than on "no exception escaped",
        which a body that closed nothing at all would satisfy just as well.
        """
        boom = RuntimeError("Event loop is closed")
        attempted, closers = _recording_closers(
            {"content service": boom, "HTTP client": boom, "cache": boom}
        )

        await _run_cleanup(closers)

        assert attempted == ["content service", "HTTP client", "cache"]

    async def test_isolation_is_not_limited_to_runtime_errors(self) -> None:
        """A bug in one closer is still just one closer's problem."""
        attempted, closers = _recording_closers(
            {"content service": ValueError("unexpected internal error")}
        )

        await _run_cleanup(closers)

        assert attempted == ["content service", "HTTP client", "cache"]


#: The logger ``fastmcp_main`` actually writes to. ``get_logger("fastmcp_main")``
#: returns a child of the application logger, and that parent sets
#: ``propagate = False``, so these records never reach the root logger. caplog
#: sees them only because pytest attaches its handler to non-propagating loggers
#: as well. Spelled out rather than read off ``fastmcp_main.logger.name``: an
#: assertion derived from the code under test cannot disagree with it, and this
#: is the name an operator greps for.
CLEANUP_LOGGER = "finos-ai-governance-mcp.fastmcp_main"


@pytest.mark.unit
class TestCleanupResourcesReporting:
    """What the shutdown transcript says happened, which is all an operator has.

    Every filter here is scoped by ``r.name == CLEANUP_LOGGER`` as well as by
    level. ``caplog.records`` is not scoped to the ``with caplog.at_level(...)``
    block: it holds every record captured during the whole ``call`` phase, from
    every logger, and ``at_level`` lowers the shared handler to that level for
    all of them. An assertion that selects on level alone and then compares for
    exact equality is therefore order-dependent by construction -- and this suite
    runs under ``pytest-randomly``. See [[caplog-in-this-repo]].
    """

    async def test_the_summary_names_every_resource_that_failed(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A stranded resource at shutdown is a leaked socket or an unflushed cache.

        Logged at ERROR because that is the level alerting and ``grep ERROR``
        key on, and because it is the level this line had before the per-resource
        handlers were introduced.
        """
        boom = RuntimeError("Event loop is closed")
        _, closers = _recording_closers({"content service": boom, "cache": boom})

        with caplog.at_level(logging.ERROR, logger=CLEANUP_LOGGER):
            await _run_cleanup(closers)

        errors = [
            r
            for r in caplog.records
            if r.levelno == logging.ERROR and r.name == CLEANUP_LOGGER
        ]
        assert len(errors) == 1, f"expected one ERROR summary, got {errors}"
        message = errors[0].getMessage()
        assert "content service" in message and "cache" in message, (
            f"summary must name the resources that failed, got {message!r}"
        )
        assert "HTTP client" not in message, (
            f"summary must not name the resource that closed, got {message!r}"
        )

    async def test_a_clean_shutdown_says_so_and_raises_nothing_to_ERROR(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The other half of the branch, without which inverting it stays green.

        Asserting only the failure summary leaves ``if errors:`` swappable with
        its ``else:`` -- every isolation test passes either way, because none of
        them reads the output.
        """
        _, closers = _recording_closers()

        with caplog.at_level(logging.INFO, logger=CLEANUP_LOGGER):
            await _run_cleanup(closers)

        problems = [
            r
            for r in caplog.records
            if r.levelno >= logging.WARNING and r.name == CLEANUP_LOGGER
        ]
        assert problems == [], (
            f"a shutdown in which nothing failed must not report a problem, got "
            f"{[(r.levelname, r.getMessage()) for r in problems]}"
        )
        summaries = [
            r.getMessage()
            for r in caplog.records
            if r.levelno == logging.INFO
            and r.name == CLEANUP_LOGGER
            and "cleanup completed" in r.getMessage()
        ]
        assert summaries == ["Resource cleanup completed successfully"], (
            f"expected one success summary, got {summaries}"
        )

    async def test_the_per_resource_line_claims_only_that_the_call_returned(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """cleanup_resources() observes a return, never an outcome.

        Two of the three closers can legitimately *discard* their resource and
        return normally -- ``close_http_client()`` when the creating loop is dead,
        ``close_cache()`` likewise. A line reading "X closed" is then false, and
        false in the one transcript someone reads while hunting the leak. The
        integration companion shows the contradiction in situ; this pins the
        wording that removed it.
        """
        _, closers = _recording_closers()

        with caplog.at_level(logging.DEBUG, logger=CLEANUP_LOGGER):
            await _run_cleanup(closers)

        per_resource = [
            r.getMessage()
            for r in caplog.records
            if r.levelno == logging.DEBUG and r.name == CLEANUP_LOGGER
        ]
        assert per_resource == [
            "content service cleanup returned",
            "HTTP client cleanup returned",
            "cache cleanup returned",
        ], f"got {per_resource}"

    async def test_each_failure_is_reported_where_it_happened(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The summary names the resource; only this line says what went wrong.

        WARNING rather than ERROR because the loop carries on and the summary is
        what reports the damage -- but it has to exist. Deleting it left every
        other test in this file green, since the summary is built from ``errors``
        and not from the log.

        ``exc_info`` is asserted because the traceback is the whole diagnostic
        value: "Error closing cache: Event loop is closed" without one gives no
        indication of which await raised.
        """
        boom = RuntimeError("Event loop is closed")
        _, closers = _recording_closers({"HTTP client": boom})

        with caplog.at_level(logging.WARNING, logger=CLEANUP_LOGGER):
            await _run_cleanup(closers)

        warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and r.name == CLEANUP_LOGGER
        ]
        assert len(warnings) == 1, (
            f"expected one per-resource warning, got "
            f"{[(r.levelname, r.getMessage()) for r in caplog.records]}"
        )
        message = warnings[0].getMessage()
        assert "HTTP client" in message and "Event loop is closed" in message, message
        assert warnings[0].exc_info is not None, (
            "the failure must carry its traceback; the message alone does not "
            "say which await raised"
        )


@pytest.mark.unit
class TestCloseHTTPClientHandsOutNothingMidTeardown:
    """#115's window, in the sibling the issue does not mention.

    #115 is written about ``CacheManager``. ``HTTPClientManager`` has the same
    shape line for line -- ``try: await close()`` with the reference cleared in
    a ``finally``, and a getter that returns ``self._http_client`` without a
    lock whenever it is set -- so a caller racing the teardown is handed the
    client whose ``aclose()`` is already running, and the ``finally`` then
    drops the manager's reference to it.

    Probed before the fix, and the observable consequence differs from the
    cache's in a way worth recording rather than assuming: the client the racer
    receives reports ``is_closed: True`` and a request through it **still
    succeeded**. So this does not announce itself by raising. It is a caller
    holding a client the manager has released, in a state httpx considers
    closed, which is the #102 shape reached through a different door.

    Fixed here rather than filed, because fixing only the reported site is what
    #118 and #121 each cost a second round.
    """

    async def test_a_racing_caller_is_not_handed_the_client_being_closed(
        self,
    ) -> None:
        """Driven with events rather than sleeps, so it cannot pass by timing."""
        entered = asyncio.Event()
        release = asyncio.Event()

        dying = _mock_client()

        async def blocking_close() -> None:
            entered.set()
            await release.wait()

        dying.close = AsyncMock(side_effect=blocking_close)
        manager = _isolated_manager(dying, asyncio.get_running_loop())

        closing = asyncio.create_task(manager.close_http_client())
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
        except TimeoutError:  # pragma: no cover - see the cache counterpart
            closing.cancel()
            pytest.fail(
                "close_http_client() never reached HTTPClient.close(), so there "
                "was no teardown window to race and this test measured nothing"
            )

        # Inside the window: aclose() has begun and has not returned.
        racer = await manager.get_http_client()

        release.set()
        await closing

        assert racer is not dying, (
            "get_http_client() handed out the client whose close was already "
            "running, and the manager drops its reference on the way out, so "
            "nothing can ever close the one that caller holds"
        )
        assert manager._http_client is racer, (
            "close_http_client() cleared the manager after the racing caller "
            "had populated it, so the fresh client is unreachable in its turn"
        )
