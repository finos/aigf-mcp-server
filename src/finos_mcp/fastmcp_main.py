#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""FastMCP-based FINOS AI Governance Framework MCP Server Main Entry Point

Copyright 2025 FINOS

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Main entry point for the FastMCP-based server implementation.
Follows MCP 2025-06-18 specification with structured output and decorator-based tools.
"""

import asyncio
import contextlib
import logging
import os
import signal
import sys
from collections.abc import Callable
from types import FrameType

from .app import settings
from .content.cache import close_cache
from .content.fetch import close_http_client, get_http_client
from .content.service import close_content_service
from .fastmcp_server import mcp
from .http_health import watch_content_host
from .logging import get_logger

logger = get_logger("fastmcp_main")

#: Seconds a networked server gets to stop through uvicorn after a stop signal
#: before its task is cancelled instead.
_NETWORK_SHUTDOWN_GRACE_SECONDS = 5.0

#: How often the wait above looks at the server while the grace period runs.
_SHUTDOWN_POLL_SECONDS = 0.05

#: Seconds a cancelled server task gets to unwind before the process exits
#: without it.
_CANCEL_WAIT_SECONDS = 2.0

#: How often the loop wakes while it waits for a stop signal. uvicorn wakes a
#: networked server's loop at the same interval.
_SIGNAL_CHECK_SECONDS = 0.1


async def cleanup_resources() -> None:
    """Close every resource, each with its own handler, and report what failed.

    Three closers run in order: the content service, the HTTP client, the
    cache. What each one does depends on whether a tool call ran (#336):

    - After a tool call, ``close_content_service()`` reaches
      ``ContentService.close()``, which closes the shared cache and the shared
      HTTP client itself (a component given to the service is its owner's to
      close), so the two closers after it find nothing and return.
    - Before any tool call, no content service exists and the first closer
      returns at once. The HTTP client exists all the same: it is built at
      startup by ``_build_http_client_or_stop`` (#250), and
      ``close_http_client()`` is what closes it. The cache is built on first
      use, so the third closer finds nothing.

    Each close has its own handler, so one that raises cannot strand the rest;
    the names of the positions that failed are logged together at ERROR, the
    individual failures at WARNING. The per-resource DEBUG record says the
    call *returned*, not that the resource was closed: a closer may discard a
    resource created on another loop, and says so itself.

    ``except Exception`` does not swallow cancellation: ``CancelledError`` and
    ``SystemExit`` derive from ``BaseException``. A closer that never returns
    is ended from outside this function: ``main_async`` runs it through
    ``_clean_up_unless_signalled``, which ends the process at the next stop
    signal.
    """
    logger.info("Starting graceful resource cleanup...")

    resources = [
        (close_content_service, "content service"),
        (close_http_client, "HTTP client"),
        (close_cache, "cache"),
    ]

    errors: list[str] = []
    for close_resource, name in resources:
        try:
            await close_resource()
            logger.debug("%s cleanup returned", name)
        except Exception as e:  # pylint: disable=broad-exception-caught
            errors.append(name)
            logger.warning("Error closing %s: %s", name, e, exc_info=True)

    if errors:
        logger.error("Resource cleanup completed with errors in: %s", ", ".join(errors))
    else:
        logger.info("Resource cleanup completed successfully")


class _StopRequest:
    """A stop signal as the server's loop sees it."""

    def __init__(self) -> None:
        self.received = asyncio.Event()
        self.signum: int | None = None
        self.handler: Callable[[int, FrameType | None], None] | None = None


def _install_signal_handlers(
    loop: asyncio.AbstractEventLoop, stop: _StopRequest
) -> None:
    """Route SIGINT and SIGTERM to ``stop`` on the server's loop.

    ``signal.signal`` rather than ``loop.add_signal_handler`` because uvicorn
    replaces these handlers with ``signal.signal`` while it serves and puts back
    whatever that call returned. It then re-raises each signal it handled, so
    the handler it restores must be one that leaves the process running long
    enough to clean up. The default SIGTERM action would not.

    The handler itself only schedules work. It runs between two bytecodes of
    whatever the main thread was doing, so the log record and the event are
    both left to the loop.
    """

    def note_signal(signum: int) -> None:
        logger.info("Received signal %d, shutting down...", signum)
        stop.signum = signum
        stop.received.set()

    def signal_handler(signum: int, _frame: FrameType | None) -> None:
        # The handler outlives the loop by the length of interpreter shutdown.
        # A signal landing there has nothing left to stop.
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(note_signal, signum)

    stop.handler = signal_handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def _serve() -> None:
    """Run the configured transport until it stops.

    FastMCP asks pypi.org for a newer version of itself before it prints its
    banner, so the banner is off on every transport (#254).
    """
    if settings.mcp_transport == "stdio":
        await mcp.run_async(transport="stdio", show_banner=False)
        return

    # What GET /readyz answers depends on this task's last request to the
    # content host. It ends with the server, before cleanup closes the HTTP
    # client it uses.
    watch = asyncio.create_task(watch_content_host())
    try:
        await mcp.run_async(
            transport=settings.mcp_transport,
            show_banner=False,
            host=settings.mcp_host,
            port=settings.mcp_port,
            # uvicorn enables proxy_headers by default and trusts loopback,
            # so it would rewrite scope["client"] from X-Forwarded-For before
            # any of our code sees it. That silently overrides
            # FINOS_MCP_DOS_TRUSTED_PROXIES: with the setting unset we promise
            # the header is ignored, but every loopback caller could still
            # choose its own rate-limit bucket. Turn it off and let
            # _client_ip apply the configured allowlist as the only authority.
            uvicorn_config={"proxy_headers": False, "forwarded_allow_ips": []},
        )
    finally:
        # Until it is done, not once: a cancellation can be absorbed by
        # whatever the task was awaiting, and a watch left running would use
        # the HTTP client after cleanup had closed it.
        while not watch.done():
            watch.cancel()
            await asyncio.wait({watch}, timeout=_SHUTDOWN_POLL_SECONDS)


async def _build_http_client_or_stop() -> None:
    """Build the shared HTTP client now, and end the process if that fails.

    Every document is fetched through this client, and it used to be built by
    the first tool call. httpx reads the proxy environment variables when a
    client is constructed, so a setting it cannot use (a SOCKS proxy without
    the ``socksio`` package, an unsupported proxy scheme) raised there, after
    the server had started: health reported healthy, the list tools served the
    static catalog and each document call told the client to retry (#250).
    Such a server can serve no document, so it does not start.

    The client is bound to the running loop, which is the loop the server
    runs on, so the one built here is the one the tools use.
    """
    try:
        await get_http_client()
    except Exception as e:
        logger.error(
            "Cannot build the HTTP client, so no document could be fetched; "
            "not starting. Check the proxy environment variables "
            "(ALL_PROXY, HTTPS_PROXY, HTTP_PROXY). Cause: %s: %s",
            type(e).__name__,
            e,
        )
        raise SystemExit(1) from e


async def main_async() -> None:
    """Run the FastMCP server on this loop and stop it on SIGINT or SIGTERM.

    The server runs on the main thread's event loop. It used to run through
    ``asyncio.to_thread(mcp.run, ...)``, which gave FastMCP a second loop in a
    worker thread and made the process ignore stop signals: uvicorn installs
    its signal handlers only on the main thread, and nothing awaited the event
    this module's own handler set. A stdio server ignored them too unless its
    client closed stdin.

    How a signal ends each transport:

    - Networked transports are stopped by uvicorn. It takes over SIGINT and
      SIGTERM while it serves, shuts down gracefully, then re-raises the signal
      to the handler installed here. That late arrival finds the server already
      finished or finishing, which is why a signal is followed by a grace
      period rather than an immediate cancel.
    - Stdio has no handler of its own, so the task is cancelled at once. The
      cancellation cannot complete while the client holds stdin open; see
      ``_exit_past_the_blocked_stdin_reader``.

    Either way the handler runs only when the main thread next runs, and a
    signal sent to the process may be delivered to another thread: the kernel
    can pick the worker blocked reading stdin. An idle stdio server's main
    thread is asleep in the loop with nothing due to wake it, so such a signal
    was never acted on (#231). The wait for a stop signal therefore wakes at a
    steady interval. A wakeup descriptor (``signal.set_wakeup_fd``) would wake
    it at once, but there is one per process, which
    ``loop.add_signal_handler`` also sets and clears, and watching it takes
    ``loop.add_reader``, which Windows' default loop does not implement.

    A signal that lands before uvicorn has taken over reaches only this
    module's handler, and uvicorn would go on to start and serve. So the wait
    watches for uvicorn replacing the handler and, when it does, raises the
    signal again for uvicorn to act on. If the server has still not stopped
    when the grace period ends, its task is cancelled.

    Once cleanup has begun, a further signal ends the process without
    waiting for it; see ``_clean_up_unless_signalled``.

    The loop-bound singletons (cache, HTTP client, content service) are now
    created and closed on the same loop. Their rebind-on-loop-change handling
    stays: it is what keeps them usable from tests and embedders that call
    them from more than one loop.
    """
    logger.info("Starting FINOS AI Governance MCP Server (FastMCP)")
    logger.info("Configured transport: %s", settings.mcp_transport)

    loop = asyncio.get_running_loop()
    stop = _StopRequest()
    _install_signal_handlers(loop, stop)

    # After the handlers: building the client takes long enough for a stop
    # signal to arrive, and one that did would otherwise end the process
    # through the default handler, with a signal status instead of 0.
    await _build_http_client_or_stop()

    server = asyncio.create_task(_serve())
    try:
        await _wait_for_task_or_signal(server, stop)
        if not server.done():
            if settings.mcp_transport != "stdio":
                await _let_uvicorn_stop(server, stop, loop)
            if not server.done():
                server.cancel()
                await asyncio.wait({server}, timeout=_CANCEL_WAIT_SECONDS)
        if server.done():
            try:
                await server
            except asyncio.CancelledError:
                logger.info("Server stopped by signal")
            except Exception as e:
                logger.error("Server error: %s", e, exc_info=True)
                raise
    finally:
        if server.done() and not server.cancelled():
            # uvicorn reports a failed startup (a port already in use) with
            # sys.exit(3). asyncio lets a SystemExit out of the loop without
            # anyone awaiting the task, then logs the task's exception as
            # never retrieved. Reading it here keeps the exit code and drops
            # the second traceback.
            server.exception()
        # Always cleanup resources
        await _clean_up_unless_signalled(stop)

    if not server.done():
        _exit_past_the_blocked_stdin_reader()


async def _let_uvicorn_stop(
    server: asyncio.Task[None], stop: _StopRequest, loop: asyncio.AbstractEventLoop
) -> None:
    """Wait out the grace period, handing an early signal on to uvicorn.

    Returns when the server task is done or the grace period has run out.
    """
    deadline = loop.time() + _NETWORK_SHUTDOWN_GRACE_SECONDS
    forwarded = False
    while not server.done() and loop.time() < deadline:
        if (
            not forwarded
            and stop.signum is not None
            and signal.getsignal(stop.signum) is not stop.handler
        ):
            # uvicorn is listening now and never saw the signal we were sent.
            signal.raise_signal(stop.signum)
            forwarded = True
        await asyncio.wait({server}, timeout=_SHUTDOWN_POLL_SECONDS)


async def _wait_for_task_or_signal(
    task: asyncio.Task[None], stop: _StopRequest
) -> None:
    """Return when ``task`` is done or a stop signal has been received.

    The wait wakes at a steady interval because the signal may be delivered
    to a thread other than the main one; see ``main_async``.
    """
    signalled = asyncio.create_task(stop.received.wait())
    try:
        while not task.done() and not signalled.done():
            await asyncio.wait(
                {task, signalled},
                timeout=_SIGNAL_CHECK_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
    finally:
        signalled.cancel()


async def _clean_up_unless_signalled(stop: _StopRequest) -> None:
    """Run ``cleanup_resources()``, ending the process at a further stop signal.

    Cleanup was awaited with nothing watching for a signal, and the handler
    installed here raises no ``KeyboardInterrupt``. A closer that never
    returned, a stuck ``aclose()`` for one, therefore held the process until
    it was sent SIGKILL (#233). Now a stop signal that arrives while cleanup
    runs ends the process with exit code 1.

    Only a signal received after cleanup has begun counts, so the event is
    cleared first. That leaves out the signal that stopped the server and
    uvicorn's re-raise of it, which is raised from inside the server task as
    it returns. It also leaves out a second signal sent while the server was
    still stopping: one Ctrl-C can reach a process more than once, through
    its process group and through a parent that forwards it, and a cleanup
    that is about to finish should not be cut short by the echo. A server
    whose cleanup then hangs needs one more signal.

    Residuals. The signal is noticed by the loop, so a closer that blocks the
    loop itself, in a synchronous call, is still ended only by SIGKILL; the
    three closers await. And a networked server that has not unwound when
    cleanup begins still has uvicorn's handlers installed, so a signal goes
    to uvicorn and not to this wait.
    """
    stop.received.clear()
    cleanup = asyncio.create_task(cleanup_resources())
    try:
        await _wait_for_task_or_signal(cleanup, stop)
    except asyncio.CancelledError:
        # Cleanup used to be awaited directly, so cancelling the entry point
        # cancelled it and the caller resumed once it had unwound. As a task
        # it would carry on alone.
        cleanup.cancel()
        await asyncio.wait({cleanup})
        raise
    if not cleanup.done():
        _exit_with_cleanup_unfinished()
    await cleanup


def _flush_and_exit(exit_code: int) -> None:
    """End the process now, writing out what a normal exit would have.

    ``os._exit`` skips every flush a normal exit performs, so they are done
    here by hand.
    """
    logging.shutdown()
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(OSError, ValueError):
            stream.flush()
    os._exit(exit_code)


def _exit_with_cleanup_unfinished() -> None:
    """End the process when a stop signal arrives while cleanup is running.

    Returning would not end it: ``asyncio.run`` waits for every task it
    cancels, and a closer that did not return may not return when cancelled
    either. The exit code is 1 because the process is leaving with resources
    it did not release.
    """
    logger.error(
        "Stop signal received during cleanup; "
        "exiting without finishing resource cleanup"
    )
    _flush_and_exit(1)


def _exit_past_the_blocked_stdin_reader() -> None:
    """End the process when the cancelled stdio server cannot finish.

    The MCP stdio transport reads stdin with a blocking ``readline`` in an
    anyio worker thread, and anyio shields the awaiting task from cancellation
    until that call returns. With the client still holding stdin open it never
    returns, so the cancelled server task never completes. Returning normally
    would not help either: ``asyncio.run`` waits for every task it cancels, and
    interpreter shutdown joins the worker thread, which is not a daemon.

    Resources are already closed when this runs, so what a normal exit would
    still do is flush, and ``_flush_and_exit`` does that.

    The caller's test is that the cancelled task is still running, not that the
    transport is stdio, so a networked server that will not unwind ends here
    too. The log line says only what was observed.
    """
    logger.info("Server task did not finish after cancellation; exiting without it")
    _flush_and_exit(0)


def main() -> None:
    """Main entry point for the FastMCP server."""
    try:
        asyncio.run(main_async())
        logger.info("Server shutdown completed")
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Server error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
