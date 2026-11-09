"""A stop signal must end the server process, on every transport.

The defect these cover: ``fastmcp_main`` ran FastMCP in a worker thread. uvicorn
only installs its SIGTERM/SIGINT handlers on the main thread, and the server's
own handler set an ``asyncio.Event`` that nothing awaited, so the process logged
"initiating graceful shutdown" and kept serving. A ``docker stop`` waited out its
grace period and sent SIGKILL. Stdio looked clean only because a client that
goes away closes stdin; with stdin held open the signal was ignored there too.

Only a real process can show this. Signal delivery, uvicorn's handler
installation and the blocked stdin read are all properties of the process, so
each case starts ``python -m finos_mcp.fastmcp_main`` and signals it.
"""

from __future__ import annotations

import json
import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        sys.platform == "win32", reason="POSIX signals; Windows has no SIGTERM"
    ),
]

#: How long a signalled server may take to exit. fastmcp gives uvicorn a
#: two-second graceful-shutdown timeout, so a working server is well inside
#: this and a server that ignores the signal never is.
_EXIT_TIMEOUT_SECONDS = 15.0

_CLEANUP_DONE = "Resource cleanup completed successfully"

_STOP_SIGNALS = [signal.SIGTERM, signal.SIGINT]


def _server_env(**overrides: str) -> dict[str, str]:
    env = os.environ.copy()
    # A server that will not stop is sent SIGABRT, and with this set the
    # interpreter writes every thread's stack to stderr on its way out.
    env["PYTHONFAULTHANDLER"] = "1"
    env.update(overrides)
    return env


def _wait_for_port(host: str, port: int, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex((host, port)) == 0:
                return
        time.sleep(0.2)
    raise TimeoutError(f"no server on {host}:{port} within {timeout_seconds}s")


def _free_port() -> int:
    """A port that was free a moment ago.

    Another process can take it between this release and the server's bind.
    The server then exits 3 with "address already in use" and the test fails
    on its exit code, so the race can fail a run but cannot pass one.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_exit(process: subprocess.Popen[Any], sent: str, log_path: Path) -> int:
    """Return the exit code of a signalled server, failing if it stays up.

    A server that stays up is aborted, not killed outright, so that its log
    ends with where each of its threads was (#231).
    """
    try:
        return process.wait(timeout=_EXIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.send_signal(signal.SIGABRT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        pytest.fail(
            f"the server was still running {_EXIT_TIMEOUT_SECONDS:.0f}s after "
            f"{sent}; it had to be killed. Its log:\n"
            + log_path.read_text(encoding="utf-8", errors="replace")
        )


def _signal_and_wait(
    process: subprocess.Popen[Any], signum: signal.Signals, log_path: Path
) -> int:
    """Send ``signum`` and return the exit code, killing a server that stays up."""
    process.send_signal(signum)
    return _wait_for_exit(process, signum.name, log_path)


def _start_http_server(
    log_path: Path, command: list[str] | None = None
) -> tuple[subprocess.Popen[bytes], str]:
    host, port = "127.0.0.1", _free_port()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command or [sys.executable, "-m", "finos_mcp.fastmcp_main"],
            env=_server_env(
                FINOS_MCP_MCP_TRANSPORT="http",
                FINOS_MCP_MCP_HOST=host,
                FINOS_MCP_MCP_PORT=str(port),
                FINOS_MCP_ALLOW_INSECURE_HTTP="true",
            ),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    try:
        _wait_for_port(host, port, timeout_seconds=20.0)
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise
    return process, f"http://{host}:{port}/mcp"


def _assert_clean_exit(exit_code: int, log_path: Path) -> None:
    log_text = log_path.read_text(encoding="utf-8")
    assert exit_code == 0, log_text
    assert _CLEANUP_DONE in log_text, log_text


@pytest.mark.parametrize("signum", _STOP_SIGNALS, ids=lambda s: s.name)
def test_http_server_exits_on_a_stop_signal(signum: signal.Signals) -> None:
    """An idle HTTP server stops, cleans up and exits 0."""
    log_path = Path(tempfile.mkdtemp()) / "http.log"
    process, _ = _start_http_server(log_path)

    exit_code = _signal_and_wait(process, signum, log_path)

    _assert_clean_exit(exit_code, log_path)


def test_http_server_stops_cleanly_on_a_signal_sent_during_startup() -> None:
    """A signal sent while the server is still starting ends it without a traceback.

    Until uvicorn takes the signal handlers over, only the entry point's own
    handler hears a signal; after that uvicorn does. The window between the
    two is milliseconds wide, so which side hears this signal varies from run
    to run. Either way the process must stop cleanly. The handover itself is
    pinned in ``tests/unit/test_fastmcp_main.py``, where it can be forced.
    """
    log_path = Path(tempfile.mkdtemp()) / "http-early.log"
    host, port = "127.0.0.1", _free_port()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "finos_mcp.fastmcp_main"],
            env=_server_env(
                FINOS_MCP_MCP_TRANSPORT="http",
                FINOS_MCP_MCP_HOST=host,
                FINOS_MCP_MCP_PORT=str(port),
                FINOS_MCP_ALLOW_INSECURE_HTTP="true",
            ),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    try:
        # The entry point logs this after installing its handlers and before
        # it starts the transport.
        deadline = time.monotonic() + 20
        while "Configured transport" not in log_path.read_text(encoding="utf-8"):
            assert time.monotonic() < deadline, "the server never reached startup"
            assert process.poll() is None, log_path.read_text(encoding="utf-8")
            time.sleep(0.01)
        at_signal = log_path.read_text(encoding="utf-8")
        exit_code = _signal_and_wait(process, signal.SIGTERM, log_path)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert "Uvicorn running" not in at_signal, (
        "precondition: the signal was sent before uvicorn was serving"
    )
    _assert_clean_exit(exit_code, log_path)
    log_text = log_path.read_text(encoding="utf-8")
    assert "Traceback" not in log_text, log_text
    assert "Application shutdown complete" in log_text, log_text


@pytest.mark.asyncio
async def test_http_server_exits_on_sigterm_with_a_session_open() -> None:
    """A connected client must not keep a signalled server alive.

    This is the container case: the orchestrator sends SIGTERM while clients
    are still attached. The session is opened and left open across the signal.
    """
    log_path = Path(tempfile.mkdtemp()) / "http-session.log"
    process, url = _start_http_server(log_path)

    try:
        async with streamable_http_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert tools.tools, "precondition: the session is live"

                process.send_signal(signal.SIGTERM)
                deadline = time.monotonic() + _EXIT_TIMEOUT_SECONDS
                while process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.1)
                still_running = process.poll() is None
    except BaseException:
        # The client may raise as its server goes away; the verdict below is
        # read from the process, not from how the client took the news.
        still_running = process.poll() is None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert not still_running, (
        f"the server was still running {_EXIT_TIMEOUT_SECONDS:.0f}s after "
        "SIGTERM with a client session open"
    )
    _assert_clean_exit(process.returncode, log_path)


def _start_initialized_stdio_server(
    log_path: Path, command: list[str]
) -> subprocess.Popen[str]:
    """Start a stdio server and return it once it has answered ``initialize``.

    A served request is the readiness check: the server is past startup and
    blocked reading stdin, which is the state a stop signal must end.
    """
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            env=_server_env(FINOS_MCP_MCP_TRANSPORT="stdio"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
        )
    assert process.stdin is not None and process.stdout is not None
    try:
        process.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "signal-test", "version": "0"},
                    },
                }
            )
            + "\n"
        )
        process.stdin.flush()
        # Bounded: a server that never answers must fail here, not hang the run.
        ready, _, _ = select.select([process.stdout], [], [], 30)
        assert ready, "the server did not answer initialize within 30s"
        reply = json.loads(process.stdout.readline())
        assert reply.get("id") == 1 and "result" in reply, reply
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise
    return process


@pytest.mark.parametrize("signum", _STOP_SIGNALS, ids=lambda s: s.name)
def test_stdio_server_exits_on_a_stop_signal_while_stdin_is_open(
    signum: signal.Signals,
) -> None:
    """A stdio server stops on a signal even though its client has not hung up.

    Stdin stays open for the whole test. Closing it would end the server by
    EOF and the signal would have nothing left to prove.
    """
    log_path = Path(tempfile.mkdtemp()) / "stdio.log"
    process = _start_initialized_stdio_server(
        log_path, [sys.executable, "-m", "finos_mcp.fastmcp_main"]
    )
    assert process.stdin is not None
    try:
        exit_code = _signal_and_wait(process, signum, log_path)
        assert not process.stdin.closed, "precondition: stdin was open throughout"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    _assert_clean_exit(exit_code, log_path)


@pytest.mark.parametrize("signum", _STOP_SIGNALS, ids=lambda s: s.name)
def test_stdio_server_exits_when_the_signal_lands_on_the_thread_reading_stdin(
    signum: signal.Signals, tmp_path: Path
) -> None:
    """A signal the kernel hands to another thread still stops the server (#231).

    A signal sent to a process is delivered to one of its threads, and it need
    not be the main one. Python runs the handler on the main thread only, the
    next time that thread runs, and an idle stdio server's main thread was
    asleep in the event loop with nothing due to wake it. The server then
    went on running as if nothing had been sent.

    Which thread receives a signal sent from outside is the kernel's choice,
    so this starts the server with a helper that sends it from inside, to the
    thread blocked reading stdin.
    """
    go, sent = tmp_path / "go", tmp_path / "sent"
    program = textwrap.dedent(
        f"""
        import os
        import signal
        import sys
        import threading
        import time

        def deliver():
            while not os.path.exists({str(go)!r}):
                time.sleep(0.01)
            # A worker inside a call has its own ``run`` as its innermost
            # Python frame; an idle one is further in, waiting on its queue.
            # Once the reply has been written, the only call still running
            # is the read of stdin.
            deadline = time.monotonic() + 5
            while True:
                frames = sys._current_frames()
                busy = [
                    thread
                    for thread in threading.enumerate()
                    if thread.name.startswith("AnyIO worker")
                    and thread.ident in frames
                    and frames[thread.ident].f_code.co_name == "run"
                ]
                if len(busy) == 1 or time.monotonic() > deadline:
                    break
                time.sleep(0.01)
            if len(busy) == 1:
                signal.pthread_kill(busy[0].ident, {int(signum)})
            with open({str(sent)!r}, "w") as report:
                report.write(str(len(busy)))

        threading.Thread(target=deliver, daemon=True).start()

        from finos_mcp.fastmcp_main import main

        main()
        """
    )
    log_path = tmp_path / "stdio.log"
    process = _start_initialized_stdio_server(log_path, [sys.executable, "-c", program])
    try:
        go.touch()
        deadline = time.monotonic() + 10
        while not (sent.exists() and sent.read_text(encoding="utf-8")):
            assert time.monotonic() < deadline, "the helper thread never reported"
            time.sleep(0.01)
        assert sent.read_text(encoding="utf-8") == "1", (
            "precondition: exactly one worker thread is inside a call, the one "
            f"reading stdin; found {sent.read_text(encoding='utf-8')}"
        )
        exit_code = _wait_for_exit(
            process, f"{signum.name} reached the thread reading stdin", log_path
        )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    _assert_clean_exit(exit_code, log_path)


_CLEANUP_IS_HUNG = "cleanup is hung"

#: The server with a first closer that never returns, which is what a stuck
#: ``aclose()`` looks like to the entry point.
_SERVER_WHOSE_CLEANUP_HANGS = textwrap.dedent(
    f"""
    import asyncio
    import sys

    from finos_mcp import fastmcp_main

    async def never_returns():
        print({_CLEANUP_IS_HUNG!r}, file=sys.stderr, flush=True)
        await asyncio.Event().wait()

    fastmcp_main.close_content_service = never_returns
    fastmcp_main.main()
    """
)


@pytest.mark.parametrize("transport", ["stdio", "http"])
@pytest.mark.parametrize("signum", _STOP_SIGNALS, ids=lambda s: s.name)
def test_a_second_stop_signal_ends_a_server_whose_cleanup_hangs(
    transport: str, signum: signal.Signals, tmp_path: Path
) -> None:
    """A stop signal sent while cleanup is stuck ends the process (#233).

    The first signal stops the server and starts cleanup. Cleanup used to be
    awaited with nothing watching for another signal, and the handler that
    replaced Python's own raises no ``KeyboardInterrupt``, so a server stuck
    there could only be ended with SIGKILL. It exits 1: it stopped, and it did
    not release what it held.
    """
    log_path = tmp_path / f"{transport}-hung-cleanup.log"
    command = [sys.executable, "-c", _SERVER_WHOSE_CLEANUP_HANGS]
    process: subprocess.Popen[Any]
    if transport == "stdio":
        process = _start_initialized_stdio_server(log_path, command)
    else:
        process, _ = _start_http_server(log_path, command)
    try:
        process.send_signal(signum)
        deadline = time.monotonic() + _EXIT_TIMEOUT_SECONDS
        while _CLEANUP_IS_HUNG not in log_path.read_text(encoding="utf-8"):
            assert time.monotonic() < deadline, (
                "cleanup never began: " + log_path.read_text(encoding="utf-8")
            )
            time.sleep(0.01)
        # Longer than the interval at which the server looks for a signal, so
        # a server that ended here on the first signal alone is caught below.
        time.sleep(0.5)
        assert process.poll() is None, (
            "precondition: the server is still running, held by its cleanup"
        )
        exit_code = _signal_and_wait(process, signum, log_path)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    log_text = log_path.read_text(encoding="utf-8")
    assert exit_code == 1, log_text
    assert "exiting without finishing resource cleanup" in log_text, log_text
    assert "Resource cleanup completed" not in log_text, log_text


@pytest.mark.parametrize(
    ("hard_exit", "expected_code"),
    [("_exit_past_the_blocked_stdin_reader", 0), ("_exit_with_cleanup_unfinished", 1)],
)
def test_each_hard_exit_writes_out_what_was_buffered(
    hard_exit: str, expected_code: int, tmp_path: Path
) -> None:
    """``os._exit`` skips every flush a normal exit performs, so they are done by hand.

    Both exits that leave through ``os._exit`` are checked: the one past a
    blocked stdin reader and the one at a stop signal during cleanup (#233).

    The signal tests above cannot see this: the server's own log lines reach
    their handlers' streams as they are written, so nothing is waiting in a
    buffer when the server exits. Here a log record is held in a buffering
    handler and stdout carries an unterminated line, which is what a
    deployment's own handler or a half-written message looks like. The record
    goes to a file, so that writing it out does not flush stdout.

    Residual: the stderr flush is not checked. The server's log handler writes
    to stderr and flushes it with every record, the function's own closing
    line included, so text left in stderr arrives whether or not the explicit
    flush runs.
    """
    held_log = tmp_path / "held.log"
    program = textwrap.dedent(
        """
        import logging
        import logging.handlers
        import sys

        from finos_mcp import fastmcp_main

        held = logging.handlers.MemoryHandler(
            capacity=1000, target=logging.FileHandler(sys.argv[1])
        )
        # Not propagated: the server's own handler would write it at once.
        logging.getLogger("held").propagate = False
        logging.getLogger("held").addHandler(held)
        logging.getLogger("held").warning("a held log record")
        sys.stdout.write("buffered on stdout")
        getattr(fastmcp_main, sys.argv[2])()
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", program, str(held_log), hard_exit],
        # Empty, so an inherited setting cannot leave stdout with no buffer.
        env=_server_env(PYTHONUNBUFFERED=""),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == expected_code, result.stdout + result.stderr
    assert "buffered on stdout" in result.stdout, "stdout was not flushed"
    assert "a held log record" in held_log.read_text(encoding="utf-8"), (
        "logging was not shut down"
    )


def test_a_failed_startup_exits_nonzero_and_reports_the_error_once() -> None:
    """A port already in use ends the process with uvicorn's exit code.

    uvicorn reports it with ``sys.exit(3)`` from inside the server task. The
    exit code must survive, cleanup must still run, and asyncio must not add a
    "Task exception was never retrieved" traceback to the one error line.
    """
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]

        result = subprocess.run(
            [sys.executable, "-m", "finos_mcp.fastmcp_main"],
            env=_server_env(
                FINOS_MCP_MCP_TRANSPORT="http",
                FINOS_MCP_MCP_HOST="127.0.0.1",
                FINOS_MCP_MCP_PORT=str(port),
                FINOS_MCP_ALLOW_INSECURE_HTTP="true",
            ),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    output = result.stdout + result.stderr
    assert result.returncode == 3, output
    assert "address already in use" in output.lower(), output
    assert _CLEANUP_DONE in output, output
    assert "never retrieved" not in output, output


def test_the_go_live_http_probe_script_passes() -> None:
    """``scripts/test-http-transport.sh`` runs to completion against this tree.

    ``scripts/go-live-gate.sh`` runs it as Gate 6 and nothing else did, so when
    the MCP client changed what ``streamable_http_client`` yields the script
    crashed for weeks without a failing check. Its ``cleanup`` then waited on a
    server that ignored SIGTERM, which is why the timeout here matters as much
    as the exit code.
    """
    repo_root = Path(__file__).resolve().parents[2]
    log_path = Path(tempfile.mkdtemp()) / "probe.log"

    result = subprocess.run(
        ["bash", str(repo_root / "scripts" / "test-http-transport.sh")],
        env=_server_env(
            PYTHON_BIN=sys.executable,
            FINOS_MCP_MCP_HOST="127.0.0.1",
            FINOS_MCP_MCP_PORT=str(_free_port()),
            LOG_FILE=str(log_path),
        ),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output + log_path.read_text(encoding="utf-8")
    assert "HTTP transport test completed successfully." in output, output
