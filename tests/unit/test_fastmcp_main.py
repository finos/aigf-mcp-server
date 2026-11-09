"""
Unit tests for the FastMCP server entry point.

Covers how the networked transport is handed to uvicorn, which decides what the
rate limiter is able to see about the caller.
"""

import asyncio
import contextlib
import signal
import threading
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finos_mcp import fastmcp_main


@pytest.mark.unit
class TestNetworkTransportProxyHeaders:
    """uvicorn must not pre-empt our own X-Forwarded-For handling (AIGF-F1, #21).

    uvicorn ships ProxyHeadersMiddleware enabled with trusted_hosts="127.0.0.1",
    which rewrites scope["client"] from X-Forwarded-For before any application
    code runs. Left on, it silently overrides FINOS_MCP_DOS_TRUSTED_PROXIES: with
    that setting unset we promise the header is ignored, yet any caller arriving
    over loopback - the documented reverse-proxy topology - could still pick its
    own rate-limit bucket by rotating the header.
    """

    @staticmethod
    async def _run_and_capture(transport):
        """Run the entry point against a stubbed server and return run() kwargs."""
        fake_mcp = MagicMock()
        fake_mcp.run_async = AsyncMock()
        with (
            patch.object(fastmcp_main, "mcp", fake_mcp),
            patch("finos_mcp.fastmcp_main.settings.mcp_transport", transport),
            patch.object(fastmcp_main, "_install_signal_handlers"),
            patch.object(fastmcp_main, "cleanup_resources", AsyncMock()),
        ):
            await fastmcp_main.main_async()
        return fake_mcp.run_async.call_args.kwargs

    @pytest.mark.asyncio
    @pytest.mark.parametrize("transport", ["http", "streamable-http", "sse"])
    async def test_proxy_headers_disabled_for_network_transports(self, transport):
        """Every networked transport hands uvicorn proxy handling turned off."""
        kwargs = await self._run_and_capture(transport)

        uvicorn_config = kwargs.get("uvicorn_config")
        assert uvicorn_config is not None, (
            "networked transport must pass an explicit uvicorn_config; without it "
            "uvicorn trusts X-Forwarded-For from loopback callers"
        )
        assert uvicorn_config["proxy_headers"] is False
        assert uvicorn_config["forwarded_allow_ips"] == []

    @pytest.mark.asyncio
    async def test_stdio_is_unchanged(self):
        """stdio has no HTTP layer, so it takes no uvicorn configuration."""
        kwargs = await self._run_and_capture("stdio")

        assert kwargs == {"transport": "stdio", "show_banner": False}


@pytest.mark.unit
class TestOnlyANetworkedServerIsGivenTheGracePeriod:
    """A signalled stdio server is cancelled at once (#199).

    The grace period exists for uvicorn, which stops itself. Stdio has nothing
    that would use it, so waiting only delays the exit. The process-level
    signal tests allow fifteen seconds and cannot tell the two apart.
    """

    @staticmethod
    async def _signal_a_running_server(transport: str, **replaced: Any) -> None:
        """Run the entry point to its end with a signal already received."""

        async def serve_until_cancelled(**_kwargs: object) -> None:
            await asyncio.Event().wait()

        fake_mcp = MagicMock()
        fake_mcp.run_async = serve_until_cancelled
        with (
            patch.object(fastmcp_main, "mcp", fake_mcp),
            patch("finos_mcp.fastmcp_main.settings.mcp_transport", transport),
            patch.object(
                fastmcp_main,
                "_install_signal_handlers",
                side_effect=lambda _loop, stop: stop.received.set(),
            ),
            patch.object(fastmcp_main, "cleanup_resources", AsyncMock()),
            patch.multiple(fastmcp_main, **replaced),
            # A server that outlived its cancellation would end this process.
            patch.object(
                fastmcp_main, "_exit_past_the_blocked_stdin_reader"
            ) as hard_exit,
        ):
            try:
                await asyncio.wait_for(fastmcp_main.main_async(), timeout=10)
            except TimeoutError:
                pytest.fail("the entry point had not returned 10s after the signal")
        hard_exit.assert_not_called()

    @pytest.mark.asyncio
    async def test_stdio_is_cancelled_without_waiting(self):
        """With a sixty-second grace period, stdio still returns inside ten."""
        await self._signal_a_running_server(
            "stdio", _NETWORK_SHUTDOWN_GRACE_SECONDS=60.0
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("transport", ["http", "streamable-http", "sse"])
    async def test_a_networked_server_is_given_time_to_stop_itself(self, transport):
        server_had_stopped: list[bool] = []

        async def grace_period(server: asyncio.Task[None], *_others: object) -> None:
            server_had_stopped.append(server.done())

        await self._signal_a_running_server(transport, _let_uvicorn_stop=grace_period)

        assert server_had_stopped == [False], (
            "the grace period must run once, before the server task is cancelled"
        )


@pytest.fixture
def restored_stop_handlers():
    """Put back whatever handled SIGINT and SIGTERM before the test."""
    originals = {
        signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)
    }
    yield
    for signum, handler in originals.items():
        signal.signal(signum, handler)


@pytest.mark.unit
@pytest.mark.skipif(
    not hasattr(signal, "pthread_kill"), reason="needs a signal aimed at one thread"
)
@pytest.mark.usefixtures("restored_stop_handlers")
class TestASignalOnAnotherThreadIsStillActedOn:
    """The kernel may hand a signal to a thread other than the main one (#231).

    Python runs the handler only when the main thread next runs. With the
    server idle, nothing was due to wake it. The process-level case, with the
    signal on the thread reading stdin, is in
    ``tests/integration/test_signal_shutdown.py``; this one runs in-process.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
    async def test_an_idle_server_notices_it_unprompted(self, signum):
        loop = asyncio.get_running_loop()
        release = threading.Event()
        parked = threading.Thread(target=release.wait, daemon=True)
        parked.start()
        woken_from_outside = threading.Event()

        def send_to_the_parked_thread() -> None:
            assert parked.ident is not None
            signal.pthread_kill(parked.ident, signum)

        def wake_the_loop_from_outside() -> None:
            woken_from_outside.set()
            loop.call_soon_threadsafe(lambda: None)

        # A server that sleeps through the signal acts on it the moment
        # anything else wakes its loop, so the test supplies that wakeup, late,
        # and asks afterwards whether it was needed. The timeout on the entry
        # point below is a wakeup too, which is why it comes later still.
        last_resort = threading.Timer(30, wake_the_loop_from_outside)

        async def serve_until_cancelled(**_kwargs: object) -> None:
            # Sent from a third thread, a moment after this loop has gone
            # idle: sent from here, the main thread would notice it at once.
            threading.Timer(0.3, send_to_the_parked_thread).start()
            last_resort.start()
            await asyncio.Event().wait()

        fake_mcp = MagicMock()
        fake_mcp.run_async = serve_until_cancelled
        try:
            with (
                patch.object(fastmcp_main, "mcp", fake_mcp),
                patch("finos_mcp.fastmcp_main.settings.mcp_transport", "stdio"),
                patch.object(fastmcp_main, "cleanup_resources", AsyncMock()),
                patch.object(
                    fastmcp_main, "_exit_past_the_blocked_stdin_reader"
                ) as hard_exit,
                # The real handlers are installed, and this exit is real too.
                patch.object(fastmcp_main, "_exit_with_cleanup_unfinished"),
            ):
                try:
                    await asyncio.wait_for(fastmcp_main.main_async(), timeout=60)
                except TimeoutError:
                    pytest.fail("the entry point never acted on the signal at all")
        finally:
            last_resort.cancel()
            release.set()

        hard_exit.assert_not_called()
        assert not woken_from_outside.is_set(), (
            "the server slept through a signal delivered to another thread "
            "until something else woke its loop"
        )


class _ProcessExited(Exception):
    """Stands in for the process ending, which a test cannot let happen."""


@pytest.mark.unit
@pytest.mark.usefixtures("restored_stop_handlers")
class TestAStopSignalDuringCleanupEndsTheProcess:
    """Cleanup that does not return is ended by the next stop signal (#233).

    The process-level cases, with a real server on each transport, are in
    ``tests/integration/test_signal_shutdown.py``. These pin the two things
    those cannot force: that the signal which stopped the server is not taken
    for one sent during cleanup, and that a signal handed to another thread is
    noticed while cleanup is stuck.
    """

    @staticmethod
    async def _run_to_the_end(cleanup, hard_exit, *, signalled_before_cleanup):
        """Run the entry point with a server that has already stopped."""
        fake_mcp = MagicMock()
        fake_mcp.run_async = AsyncMock()
        installed = (
            patch.object(
                fastmcp_main,
                "_install_signal_handlers",
                side_effect=lambda _loop, stop: stop.received.set(),
            )
            if signalled_before_cleanup
            else contextlib.nullcontext()
        )
        with (
            patch.object(fastmcp_main, "mcp", fake_mcp),
            patch("finos_mcp.fastmcp_main.settings.mcp_transport", "stdio"),
            patch.object(fastmcp_main, "cleanup_resources", cleanup),
            patch.object(fastmcp_main, "_exit_with_cleanup_unfinished", hard_exit),
            installed,
        ):
            await asyncio.wait_for(fastmcp_main.main_async(), timeout=60)

    @pytest.mark.asyncio
    async def test_the_signal_that_stopped_the_server_does_not_end_cleanup(self):
        """One signal is a clean shutdown, however long cleanup takes."""
        finished: list[bool] = []

        async def slow_cleanup() -> None:
            # Several of the intervals at which a signal is looked for.
            await asyncio.sleep(0.5)
            finished.append(True)

        hard_exit = MagicMock(side_effect=_ProcessExited)

        await self._run_to_the_end(
            slow_cleanup, hard_exit, signalled_before_cleanup=True
        )

        hard_exit.assert_not_called()
        assert finished == [True], "the entry point returned before cleanup had"

    @pytest.mark.asyncio
    async def test_a_failure_in_cleanup_still_reaches_the_caller(self):
        async def failing_cleanup() -> None:
            raise RuntimeError("cleanup failed")

        with pytest.raises(RuntimeError, match="cleanup failed"):
            await self._run_to_the_end(
                failing_cleanup, MagicMock(), signalled_before_cleanup=True
            )

    @pytest.mark.asyncio
    async def test_cancelling_the_entry_point_cancels_cleanup(self):
        """Cleanup runs as a task; a cancelled caller resumes after it has unwound."""
        started = asyncio.Event()
        outcome: list[str] = []

        async def cleanup_that_waits() -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                # A closer that takes a moment to let go.
                await asyncio.sleep(0.05)
                outcome.append("unwound")
                raise

        entry_point = asyncio.create_task(
            self._run_to_the_end(
                cleanup_that_waits, MagicMock(), signalled_before_cleanup=True
            )
        )
        await asyncio.wait_for(started.wait(), timeout=10)
        entry_point.cancel()
        with pytest.raises(asyncio.CancelledError):
            await entry_point

        assert outcome == ["unwound"], (
            "the entry point returned before its cancelled cleanup had unwound"
        )

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not hasattr(signal, "pthread_kill"),
        reason="needs a signal aimed at one thread",
    )
    @pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
    async def test_a_signal_on_another_thread_ends_a_hung_cleanup(self, signum):
        """As in #231: nothing is due to wake a loop whose cleanup is stuck."""
        loop = asyncio.get_running_loop()
        release = threading.Event()
        parked = threading.Thread(target=release.wait, daemon=True)
        parked.start()
        woken_from_outside = threading.Event()
        cleanup_may_return = asyncio.Event()

        def send_to_the_parked_thread() -> None:
            assert parked.ident is not None
            signal.pthread_kill(parked.ident, signum)

        def wake_the_loop_from_outside() -> None:
            woken_from_outside.set()
            loop.call_soon_threadsafe(lambda: None)

        # The outside wakeup comes late, and the test asks afterwards whether
        # it was needed; see TestASignalOnAnotherThreadIsStillActedOn.
        last_resort = threading.Timer(30, wake_the_loop_from_outside)

        async def hung_cleanup() -> None:
            threading.Timer(0.3, send_to_the_parked_thread).start()
            last_resort.start()
            await cleanup_may_return.wait()

        hard_exit = MagicMock(side_effect=_ProcessExited)
        try:
            with pytest.raises(_ProcessExited):
                await self._run_to_the_end(
                    hung_cleanup, hard_exit, signalled_before_cleanup=False
                )
        except TimeoutError:
            pytest.fail("the entry point never acted on the signal at all")
        finally:
            last_resort.cancel()
            release.set()
            cleanup_may_return.set()
            await asyncio.sleep(0)

        hard_exit.assert_called_once_with()
        assert not woken_from_outside.is_set(), (
            "the server slept through a signal delivered to another thread "
            "until something else woke its loop"
        )


@pytest.mark.unit
@pytest.mark.usefixtures("restored_stop_handlers")
class TestEarlySignalIsHandedToUvicorn:
    """A signal that arrived before uvicorn listened is raised again for it (#179).

    uvicorn replaces the entry point's handlers with ``signal.signal`` when it
    starts serving. A signal received before that reached only the entry point,
    and uvicorn would start and serve as if nothing had been sent. These drive
    ``_let_uvicorn_stop`` with a stand-in for uvicorn's handler, because the
    window is a few milliseconds wide in a real process and a subprocess test
    cannot hit it on demand.
    """

    @staticmethod
    def _stop_request_already_signalled() -> tuple[
        fastmcp_main._StopRequest, list[int]
    ]:
        """A stop request as it looks after the entry point heard SIGTERM."""
        heard_by_entry_point: list[int] = []
        stop = fastmcp_main._StopRequest()
        stop.signum = signal.SIGTERM
        stop.handler = lambda signum, _frame: heard_by_entry_point.append(signum)
        signal.signal(signal.SIGTERM, stop.handler)
        return stop, heard_by_entry_point

    @pytest.mark.asyncio
    async def test_the_signal_is_raised_again_once_uvicorn_takes_the_handler(self):
        loop = asyncio.get_running_loop()
        stop, heard_by_entry_point = self._stop_request_already_signalled()
        uvicorn_heard = asyncio.Event()

        async def serve_until_signalled() -> None:
            # uvicorn takes the handler over a moment after the wait begins.
            await asyncio.sleep(0.1)
            signal.signal(signal.SIGTERM, lambda *_: uvicorn_heard.set())
            await uvicorn_heard.wait()

        server = asyncio.create_task(serve_until_signalled())
        with patch.object(fastmcp_main, "_NETWORK_SHUTDOWN_GRACE_SECONDS", 5.0):
            await asyncio.wait_for(
                fastmcp_main._let_uvicorn_stop(server, stop, loop), timeout=10
            )

        assert uvicorn_heard.is_set(), "uvicorn never received the early signal"
        assert server.done(), "the wait returned before the server had stopped"
        assert heard_by_entry_point == [], "the signal was raised at ourselves"

    @pytest.mark.asyncio
    async def test_nothing_is_raised_while_the_handler_is_still_ours(self):
        """uvicorn's own re-raise arrives with our handler restored: do not echo it."""
        loop = asyncio.get_running_loop()
        stop, heard_by_entry_point = self._stop_request_already_signalled()

        server = asyncio.create_task(asyncio.sleep(0.2))
        await asyncio.wait_for(
            fastmcp_main._let_uvicorn_stop(server, stop, loop), timeout=10
        )

        assert server.done()
        assert heard_by_entry_point == []

    @pytest.mark.asyncio
    async def test_the_wait_gives_up_when_the_grace_period_ends(self):
        """A server that never stops is handed back to the caller to cancel."""
        loop = asyncio.get_running_loop()
        stop, _ = self._stop_request_already_signalled()
        never = asyncio.Event()

        server = cast("asyncio.Task[None]", asyncio.create_task(never.wait()))
        try:
            with patch.object(fastmcp_main, "_NETWORK_SHUTDOWN_GRACE_SECONDS", 0.2):
                await asyncio.wait_for(
                    fastmcp_main._let_uvicorn_stop(server, stop, loop), timeout=10
                )
            assert not server.done()
        finally:
            server.cancel()
