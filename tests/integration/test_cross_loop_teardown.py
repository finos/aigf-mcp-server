"""Teardown of the shared HTTP client from a loop that did not create it.

The defect these cover: until #181 the server ran FastMCP with
``asyncio.to_thread(mcp.run, ...)`` (``fastmcp_main.py``), so FastMCP built and
used its own event loop -- call it L2 -- inside a worker thread. The shared
``HTTPClient`` and its connection pool were created there. When ``mcp.run()``
returned, L2 was closed; ``cleanup_resources()`` then ran on the *main* loop
(L1) and called ``close_http_client()``, which awaited ``aclose()`` against
transports bound to a loop that no longer existed::

    RuntimeError: Event loop is closed

The server no longer does that. It serves and cleans up on the one loop
``asyncio.run(main_async())`` creates, so none of the states below arises on
its own path. The handling these tests cover was kept on purpose (#196): the
cache, the HTTP client and the content service are process-wide singletons,
and a test suite or an embedding program that reaches them from more than one
loop still arrives in every one of these branches. The helpers here build
those states directly, with a second loop in a thread.

Why this needs a real socket. ``aclose()`` only touches the event loop if the
pool actually holds a connection, so an idle client tears down across a dead
loop without complaint -- the first attempt at reproducing this raised nothing
for exactly that reason. The connection also has to survive the request, which
means the server must speak HTTP/1.1: under HTTP/1.0 the server hangs up, the
pool empties, and the bug disappears again. A mock client cannot express any of
this, which is why the mocked branch tests live in
``tests/unit/test_http_client_manager.py`` and the reproduction lives here.

Requests are issued through ``HTTPClient._client`` rather than the public fetch
path on purpose: ``why_not_a_fetch_target`` requires HTTPS and refuses
loopback, so no public call can reach a 127.0.0.1 test server. The bug is
in teardown, not in how the connection was opened, so driving httpx directly
reproduces it faithfully.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from collections.abc import Callable, Coroutine, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, TypeVar

import pytest

from finos_mcp.content import cache as cache_module
from finos_mcp.content import fetch as fetch_module
from finos_mcp.content import service as service_module
from finos_mcp.content.cache import get_cache
from finos_mcp.content.fetch import close_http_client, get_http_client
from finos_mcp.service import get_service

T = TypeVar("T")


class _KeepAliveServer:
    """A loopback server that holds the connection open after responding.

    ``protocol_version = "HTTP/1.1"`` is the load-bearing line: it is what leaves
    a live connection in httpx's pool once the request completes, and the pooled
    connection is the precondition for the RuntimeError this module reproduces.
    Threaded so a parked keep-alive connection cannot block ``shutdown()``.
    """

    def __init__(self) -> None:
        body = b"ok"

        class _Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                """Silence the default stderr access log."""

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self) -> _KeepAliveServer:
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)

    @property
    def url(self) -> str:
        host, port = self._httpd.server_address[0], self._httpd.server_address[1]
        assert isinstance(host, str)
        return f"http://{host}:{port}/"


def _pooled_connections(client: object) -> int:
    """Number of connections httpx is currently holding for this client."""
    return len(client._client._transport._pool.connections)  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _restore_global_manager() -> Iterator[None]:
    """Keep these tests from leaking client state into the rest of the session.

    They deliberately drive the process-wide singleton, because that is the
    object ``cleanup_resources()`` reaches at shutdown.
    """
    manager = fetch_module._http_client_manager
    saved_client, saved_loop = manager._http_client, manager._loop
    manager._http_client, manager._loop = None, None
    try:
        yield
    finally:
        manager._http_client, manager._loop = saved_client, saved_loop


#: Longest the injected worker below stays parked. Its only job is to outlive a
#: 50ms join, so this is a failure bound rather than a wait: reaching it means
#: the seam under test never gave up, and the test says so instead of hanging.
_PARK_LIMIT_SECONDS = 5.0

#: How long a caller waits for a worker thread before giving up on it. A module
#: constant rather than a literal at the join, so the give-up path can be
#: exercised in milliseconds instead of in ten seconds.
_WORKER_JOIN_TIMEOUT_SECONDS = 10.0


def _run_in_a_dying_loop(build: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Run ``build()`` on a loop created and destroyed inside a worker thread.

    Mirrors what ``asyncio.to_thread(mcp.run, ...)`` did until #181: the loop
    lives and dies in the thread, leaving whatever the coroutine registered on
    a module-level singleton bound to a loop that no longer runs.

    ``asyncio.run()`` rather than a bare ``loop.close()`` because it is what
    FastMCP's ``run()`` reached (via ``anyio.run()``), and it is how a caller
    with a second loop normally ends one. The difference is observable:
    ``asyncio.run()`` cancels a pending background task as part of tearing the
    loop down, while a bare ``loop.close()`` leaves it pending. Reproducing the
    ordinary path matters more here than reproducing the worse one.

    ``daemon=True`` is load-bearing and cannot be observed by this suite
    passing. The join bounds the *test*; without the flag it does not bound the
    *thread*, so a worker that stalls outlives its own test failure and blocks
    interpreter exit -- a CI timeout with no failing test attached to it, which
    is the least diagnosable shape available. ``test_ci_config_drift.py`` pins
    the flag statically, since no passing run can.

    Both ways of not delivering a result are reported as themselves. Callers
    check a precondition immediately after this returns, so a discarded
    exception or an expired join would otherwise surface as "the harness
    produced the wrong state" and name the cache or the keep-alive server as
    the suspect while the real traceback went to stderr from a dead thread.

    **Residual on the give-up path.** Raising does not stop the worker; Python
    cannot. ``daemon=True`` keeps it from blocking interpreter exit, but a
    worker part-way through ``get_http_client()`` still holds a reference to
    the process-wide manager, and the raise unwinds past the fixture that
    restores that singleton -- so the thread can overwrite it afterwards and
    misattribute a *later* test. That is not new (returning a default leaked
    the same thread), and it is bounded by this seam being test-only, but the
    message says so rather than promising containment it cannot deliver.
    """
    result: list[T] = []
    error: list[BaseException] = []

    def worker() -> None:
        async def run() -> None:
            result.append(await build())

        try:
            asyncio.run(run())
        # Broad on purpose: anything the worker raises, including a
        # KeyboardInterrupt or a CancelledError, is re-raised below in the
        # joining thread rather than lost to a thread nobody is watching.
        except BaseException as exc:
            error.append(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=_WORKER_JOIN_TIMEOUT_SECONDS)

    # Liveness first. Reading `error` first leaves a window where the join has
    # expired, `error` is read empty, the worker then raises and exits, and
    # `is_alive()` is false by the time it is asked -- so both branches miss and
    # `result[0]` raises a bare IndexError, losing the traceback entirely. That
    # is the undiagnosable shape this seam exists to remove, and a 50ms join on
    # a loaded runner is exactly where it would land.
    if thread.is_alive():
        raise AssertionError(
            f"the worker thread did not finish within "
            f"{_WORKER_JOIN_TIMEOUT_SECONDS}s, so there is no result to check; "
            "the fault is here rather than in this caller's next precondition. "
            "The thread is still running as this raises and nothing can stop "
            "it, so if it was part-way through populating a singleton it may "
            "still write to one after the restoring fixture has run -- a later "
            "test failing oddly is a consequence of this, not a separate fault"
        )
    # The thread has returned, so both lists are final now.
    if error:
        raise error[0]
    if not result:
        raise AssertionError(
            "the worker returned without producing a result or an exception, "
            "which should be impossible; treat this as a fault in this seam"
        )
    return result[0]


def _build_client_in_a_dying_loop(url: str) -> int:
    """Populate the singleton HTTP client from a loop that dies before we return.

    Leaves the shared client on the module-level manager with its connection
    pool bound to a loop that no longer runs, and returns how many connections
    that pool ended up holding.
    """

    async def use_client() -> int:
        client = await get_http_client()
        await client._client.get(url)
        return _pooled_connections(client)

    return _run_in_a_dying_loop(use_client)


@pytest.mark.integration
async def test_close_http_client_survives_a_dead_creating_loop() -> None:
    """Teardown on L1 must not raise for a client whose pool belongs to L2."""
    with _KeepAliveServer() as server:
        pooled = _build_client_in_a_dying_loop(server.url)

        manager = fetch_module._http_client_manager
        # Without these the test would pass against a harness that never
        # produced the failing condition in the first place.
        assert pooled == 1, (
            "the worker loop left no connection in the pool, so this test cannot "
            "reproduce the cross-loop teardown failure"
        )
        assert manager._http_client is not None, "no client was left on the singleton"
        assert manager._loop is not None and manager._loop.is_closed(), (
            "the creating loop is still open; teardown would not be cross-loop"
        )
        assert manager._loop is not asyncio.get_running_loop()

        await close_http_client()

        assert manager._http_client is None
        assert manager._loop is None


#: The logger ``fetch.py`` writes the discard line to. Spelled out rather than
#: read off the module, so a rename has to be noticed here too; the application
#: logger sets ``propagate = False``, so caplog reaches these records only via
#: the handler pytest attaches to non-propagating loggers.
HTTP_MANAGER_LOGGER = "finos-ai-governance-mcp.http_client_manager"


@pytest.mark.integration
async def test_a_discarded_http_client_says_it_was_not_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The discard is silent unless this line is emitted, and it is not nothing.

    Skipping the close means ``HTTPClient.close()`` never runs, so the
    connection pool is left to the collector. Someone reading a shutdown log
    needs to be told the client was dropped deliberately rather than conclude
    the server died before it got there. Asserted at INFO, because DEBUG would
    put the explanation below the level anybody runs at.
    """
    with _KeepAliveServer() as server:
        assert _build_client_in_a_dying_loop(server.url) == 1, (
            "no pooled connection, so this is not the discard path"
        )

        with caplog.at_level(logging.INFO, logger=HTTP_MANAGER_LOGGER):
            await close_http_client()

        discards = [
            r for r in caplog.records if "Discarding HTTP client" in r.getMessage()
        ]
        assert len(discards) == 1, (
            f"expected one discard line, got {[r.getMessage() for r in caplog.records]}"
        )
        assert discards[0].levelno == logging.INFO
        assert discards[0].name == HTTP_MANAGER_LOGGER
        assert "Its connection pool is not closed" in discards[0].getMessage(), (
            "the line must say what the skipped close cost, not just that it "
            "was skipped"
        )


@pytest.mark.integration
async def test_close_http_client_on_its_own_loop_really_closes_it() -> None:
    """Paired positive control: a same-loop teardown still performs the close.

    Without this, the guard could pass the test above by never closing anything
    at all, and the suite would report success for a client that is now leaked
    on every shutdown rather than only on the cross-loop one.
    """
    with _KeepAliveServer() as server:
        client = await get_http_client()
        await client._client.get(server.url)

        assert _pooled_connections(client) == 1
        assert not client._client.is_closed

        await close_http_client()

        assert client._client.is_closed, "same-loop teardown skipped the real close"
        assert _pooled_connections(client) == 0
        assert fetch_module._http_client_manager._http_client is None


#: The logger ``cache.py`` writes its discard line to.
CACHE_MANAGER_LOGGER = "finos-ai-governance-mcp.cache"


@pytest.fixture
def _restore_global_cache_manager() -> Iterator[None]:
    """Same singleton problem as the HTTP client, same remedy.

    ``close_cache()`` reaches the process-wide ``CacheManager``; a cache left
    behind by one test would be what the next one reads. (The cache is no
    longer loop-bound, #305, so the tests of its discard branch are gone.)
    """
    manager = cache_module._cache_manager
    saved = manager._cache
    manager._cache = None
    try:
        yield
    finally:
        manager._cache = saved


class _InjectedWorkerFailure(Exception):
    """Distinctive enough that nothing else in the suite can raise it."""


@pytest.mark.integration
def test_a_dying_loop_worker_reraises_its_own_exception() -> None:
    """A harness fault must arrive as itself, not as a wrong precondition.

    Both callers of this seam check a precondition immediately afterwards --
    "the worker never built a cache", "the worker loop left no connection in the
    pool" -- so a swallowed exception is reported as the harness having produced
    the wrong state, naming the cache or the keep-alive server as the suspect.
    The traceback meanwhile goes to stderr from a thread nobody is watching.

    Asserted by identity rather than by type: re-raising the captured object is
    the behaviour under test, and a type-only check would also be satisfied by
    some unrelated failure of the same class.
    """
    boom = _InjectedWorkerFailure("the worker's own failure")

    async def explode() -> object:
        raise boom

    with pytest.raises(_InjectedWorkerFailure) as caught:
        _run_in_a_dying_loop(explode)

    assert caught.value is boom, (
        "the exception that reached the test is not the one the worker raised"
    )


@pytest.mark.integration
def test_a_dying_loop_worker_that_hangs_names_the_hang(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other route to a wrong precondition: the join expires.

    Re-raising covers a worker that fails; it does nothing for one that never
    finishes, where no exception exists to capture and the caller would again
    read the empty result as "the harness produced the wrong state". The daemon
    flag makes that survivable at interpreter exit; only this makes it legible.

    The worker parks on an ``Event`` this test always sets, and the release is
    confirmed by waiting for the coroutine's own ``unparked`` signal. That is
    all it confirms: the signal fires inside the coroutine, before
    ``asyncio.run()`` tears the loop down and before the thread returns, and the
    thread handle belongs to the seam, so this test cannot join it and does not
    claim to. What it rules out is the worker still spinning in its poll loop
    after the test ends. The waits are guarded on ``parked``, so a seam that
    never ran the coroutine at all fails on its own assertion rather than in
    cleanup.
    """
    monkeypatch.setattr(sys.modules[__name__], "_WORKER_JOIN_TIMEOUT_SECONDS", 0.05)
    parked, released, unparked = threading.Event(), threading.Event(), threading.Event()

    async def hang() -> object:
        parked.set()
        try:
            # Bounded, so that a seam which lost its give-up path fails this
            # test in seconds instead of hanging the session forever. Replacing
            # the timed join with join(None) does exactly that, and an
            # unbounded park would answer that mutation with the undiagnosable
            # failure shape this whole change exists to prevent.
            loop = asyncio.get_running_loop()
            deadline = loop.time() + _PARK_LIMIT_SECONDS
            while not released.is_set() and loop.time() < deadline:
                await asyncio.sleep(0.01)
        finally:
            unparked.set()
        return "never observed"

    try:
        with pytest.raises(AssertionError) as caught:
            _run_in_a_dying_loop(hang)

        message = str(caught.value)
        assert parked.wait(timeout=5), "the worker never reached the parked state"
        assert "did not finish" in message, (
            f"the failure must name the hang rather than the missing result; "
            f"got {message!r}"
        )
    finally:
        released.set()
        if parked.is_set():
            assert unparked.wait(timeout=5), "the parked worker thread never unparked"


# ---------------------------------------------------------------------------
# Acquisition side: the same discard, taken by the getter rather than the closer
# ---------------------------------------------------------------------------
#
# Everything above drives a *closer* across a loop boundary. The three tests
# below drive a *getter*: `get_cache()`, `get_service()` and
# `get_http_client()` each react to a loop change by dropping the resource they
# are holding and rebuilding on the new loop. That branch skipped the same close
# the closers skip, and -- unlike them, after PR #113 -- said nothing at all.
#
# Why these belong beside the teardown tests rather than in their own file: the
# defect is the same silence on the same singletons, and reproducing it needs
# the same `_run_in_a_dying_loop()` harness and the same reasoning about which
# loop owns what.

#: The content service's logger. It wrote a discard line of its own while the
#: service memoised its components (#124); since #313 it memoises neither and
#: the only discard records are the two managers', so this logger is watched
#: here as a negative control.
SERVICE_LOGGER = "finos-ai-governance-mcp.content_service"


@pytest.fixture
def _restore_global_service_manager() -> Iterator[None]:
    """Reset the content-service singleton, and put it back after.

    One singleton, where this used to reset two. ``AsyncServiceManager`` held a
    second reference to the same instance and only ``ContentServiceManager``
    was on the shutdown path; #114 collapsed the pair, so ``get_service()`` is
    now a re-export of ``get_content_service()`` and there is one place to
    reset. The name is kept because these tests drive ``get_service()``, which
    is still the surface the tool bodies call.
    """
    content_manager = service_module._content_service_manager
    saved_content = content_manager._content_service
    content_manager._content_service = None
    try:
        yield
    finally:
        content_manager._content_service = saved_content


@pytest.mark.integration
async def test_an_http_client_dropped_by_a_loop_change_says_what_was_lost(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The third site, which #116 does not name and PR #111 did not reach.

    ``HTTPClientManager.get_http_client()`` carries the branch inline rather
    than in an ``_ensure_loop_context()`` helper, which is why it stayed outside
    both diffs. It is the same discard and the same silence.

    No keep-alive server here, unlike ``test_close_http_client_survives_a_dead
    _creating_loop``. That one needs a pooled connection because it *awaits*
    ``aclose()`` against the dead loop; this one only drops a reference, so the
    socket would add nothing the assertions could read.
    """
    client = _run_in_a_dying_loop(get_http_client)
    manager = fetch_module._http_client_manager
    assert manager._http_client is client, "no client was left on the singleton"
    assert manager._loop is not None and manager._loop.is_closed(), (
        "the creating loop is still open; this would not be a cross-loop rebind"
    )

    with caplog.at_level(logging.INFO, logger=HTTP_MANAGER_LOGGER):
        rebuilt = await get_http_client()

    discards = [r for r in caplog.records if "Discarding HTTP client" in r.getMessage()]
    assert len(discards) == 1, (
        f"expected one discard line, got {[r.getMessage() for r in caplog.records]}"
    )
    assert discards[0].levelno == logging.INFO
    assert discards[0].name == HTTP_MANAGER_LOGGER
    message = discards[0].getMessage()
    assert "now closed" in message, (
        f"the line must report the provenance it observed; got {message!r}"
    )
    assert "HTTPClient.close()" in message, (
        f"the line must say what the skipped close cost; got {message!r}"
    )
    assert rebuilt is not client, "the rebind did not replace the abandoned client"


@pytest.mark.integration
@pytest.mark.usefixtures(
    "_restore_global_cache_manager", "_restore_global_service_manager"
)
async def test_a_first_access_does_not_claim_a_discard(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The trap that makes a naive fix worse than the silence it replaces.

    All three getters take the rebind branch on the **first ever access**: a
    fresh manager has ``_loop is None``, which is the first clause of the
    condition. Measured on an unfixed manager, tracing the branch::

        loop A: 5 accesses on a fresh manager     -> resets: [('reset', 'EMPTY')]
        loop B: 5 accesses after the loop changed -> resets: [('reset', 'had_cache')]

    So a line placed in the branch rather than on the resource would announce a
    discard on every cold start, in production, having discarded nothing --
    and that firing is reachable where the real discard is not. Whatever the
    record is keyed on, it must be the resource, never the branch.

    This is the negative control for every site at once, which is deliberate:
    the trap is a property of the shared condition, so a fix that got it right
    at one site and wrong at another would still fail here.

    Two managers rather than three since #114 deleted ``AsyncServiceManager``;
    the service's own copy of the branch went with its memoised components in
    #313. It is still driven below through ``_get_http_client()``, which now
    asks the manager, so a first access through the service is one more route
    to the same branch.
    """
    for manager in (
        cache_module._cache_manager,
        fetch_module._http_client_manager,
    ):
        assert getattr(manager, "_loop", None) is None, (
            f"{type(manager).__name__} is already bound, so this test would not "
            "exercise a first access"
        )

    # Every one of these loggers has an ancestor with ``propagate = False``,
    # so caplog's root handler never sees their records and a bare
    # ``at_level(DEBUG)`` captures nothing at all. Naming the child is what
    # makes pytest attach its handler to that logger directly. The first
    # version of this test did not, and it passed against a deliberately
    # broken helper that logged a discard on every first access -- a negative
    # control that captures nothing is indistinguishable from one that passes.
    with (
        caplog.at_level(logging.DEBUG, logger=CACHE_MANAGER_LOGGER),
        caplog.at_level(logging.DEBUG, logger=SERVICE_LOGGER),
        caplog.at_level(logging.DEBUG, logger=HTTP_MANAGER_LOGGER),
    ):
        # Canaries, before the calls under test: prove each of the three
        # loggers actually reaches caplog, so the "no discard line" assertion
        # below is evidence of silence rather than of a dead capture path.
        for logger_name in (
            CACHE_MANAGER_LOGGER,
            SERVICE_LOGGER,
            HTTP_MANAGER_LOGGER,
        ):
            logging.getLogger(logger_name).debug("canary %s", logger_name)

        await get_cache()
        service = await get_service()
        await service._get_http_client()
        await get_http_client()

    captured = [r.name for r in caplog.records if "canary" in r.getMessage()]
    assert set(captured) == {
        CACHE_MANAGER_LOGGER,
        SERVICE_LOGGER,
        HTTP_MANAGER_LOGGER,
    }, f"capture is not live for every logger under test; got {captured}"

    discards = [r for r in caplog.records if "Discarding" in r.getMessage()]
    assert discards == [], (
        "a first access has nothing to discard, so it must not claim one; got "
        f"{[r.getMessage() for r in discards]}"
    )


@pytest.mark.integration
@pytest.mark.usefixtures(
    "_restore_global_cache_manager", "_restore_global_service_manager"
)
async def test_a_second_access_on_the_same_loop_keeps_the_resource(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Paired positive control for the rebind test, and it is not redundant.

    ``must_rebind()`` returning ``True`` unconditionally satisfies every
    assertion in the three discard tests above -- they only ever call a getter
    once, so a helper that rebuilt on *every* access would look identical to
    one that rebuilt on a loop change. Measured: that mutation survived the
    whole file until this test existed.

    What it would cost in production is the point. Rebuilding on every access
    means a fresh ``TTLCache`` per call -- so nothing is ever a cache hit -- and
    a fresh ``HTTPClient`` per call, so the connection pool is discarded
    between requests while the abandoned ones log a discard apiece.
    """
    with (
        caplog.at_level(logging.DEBUG, logger=CACHE_MANAGER_LOGGER),
        caplog.at_level(logging.DEBUG, logger=SERVICE_LOGGER),
        caplog.at_level(logging.DEBUG, logger=HTTP_MANAGER_LOGGER),
    ):
        first = (await get_cache(), await get_service(), await get_http_client())
        second = (await get_cache(), await get_service(), await get_http_client())

    for name, one, two in zip(
        ("cache", "service", "HTTP client"), first, second, strict=True
    ):
        assert one is two, (
            f"the {name} was rebuilt on a second access from the same loop, so "
            "the loop-change test is not testing the loop"
        )

    discards = [r for r in caplog.records if "Discarding" in r.getMessage()]
    assert discards == [], (
        f"nothing changed loops, so nothing may be discarded; got "
        f"{[r.getMessage() for r in discards]}"
    )
