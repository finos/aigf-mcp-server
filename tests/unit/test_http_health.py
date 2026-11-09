"""Tests for the two health URLs a networked server answers without a token (#255).

The defect these cover: an HTTP server with auth on answered ``404`` on every
path but ``/mcp``, and ``401`` there. A load balancer could only check that the
port answered, so it could not tell a server that had lost the content host
from a working one.

``/healthz`` says the process is serving. ``/readyz`` says whether it can fetch
documents, from two facts the server holds: what its last timed request to the
content host found, and whether the document-fetch circuit breaker is refusing
calls. Neither URL has a body.

The status codes are read from HTTP responses of the app fastmcp builds for an
auth-enabled server, next to a ``401`` from the MCP path of the same app. That
``401`` is what shows the ``200`` beside it was served without a token to a
server that requires one.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any, Literal, cast
from unittest.mock import patch

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastmcp import FastMCP
from pydantic import ValidationError

from finos_mcp import fastmcp_main, fastmcp_server, http_health
from finos_mcp.app import _build_auth_provider
from finos_mcp.app import settings as server_settings
from finos_mcp.config import Settings
from finos_mcp.content import fetch
from finos_mcp.content import service as content_service
from finos_mcp.content.fetch import HTTPClient
from finos_mcp.error_boundary import CircuitBreaker
from finos_mcp.exceptions import CircuitBreakerError

#: The manager ``running_content_service`` reads. Named here and not obtained
#: from ``ContentServiceManager()``: other tests reset that class's singleton,
#: after which the constructor returns an object the accessor does not read.
_MANAGER = content_service._content_service_manager

HEALTH_LOGGER = "finos-ai-governance-mcp.http_health"

#: The path each transport refuses without a token, and how to ask for it.
_GUARDED = {
    "http": ("POST", "/mcp"),
    "streamable-http": ("POST", "/mcp"),
    "sse": ("GET", "/sse"),
}
NETWORKED = sorted(_GUARDED)


@pytest.fixture(scope="module")
def public_pem() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )


def _settings(public_pem: str, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "mcp_transport": "http",
        "mcp_auth_enabled": True,
        "mcp_auth_public_key": public_pem,
        "mcp_auth_issuer": "https://auth.http-health.test",
        "mcp_auth_audience": "finos-mcp-server",
    }
    values.update(overrides)
    return Settings(**values)


@asynccontextmanager
async def _client(
    app_settings: Settings, transport: str = "http"
) -> AsyncIterator[httpx.AsyncClient]:
    """Serve an auth-enabled FastMCP app that carries the health routes."""
    server = FastMCP("http-health-test", auth=_build_auth_provider(app_settings))
    http_health.register_health_routes(server)
    app = (
        server.http_app(transport="sse")
        if transport == "sse"
        else server.http_app(
            path="/mcp", transport=cast(Literal["http", "streamable-http"], transport)
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Start each test with no probe result and no content service."""
    monkeypatch.setattr(http_health._content_host, "reachable", None)
    monkeypatch.setattr(http_health, "running_http_client", lambda: None)
    yield


@asynccontextmanager
async def _client_with(
    monkeypatch: pytest.MonkeyPatch, breaker: CircuitBreaker | None = None
) -> AsyncIterator[HTTPClient]:
    """The running HTTP client, its content-host breaker tripped as told."""
    client = HTTPClient()
    if breaker is not None:
        _trip(client.circuit_breaker(server_settings.base_url), breaker)
    monkeypatch.setattr(http_health, "running_http_client", lambda: client)
    try:
        yield client
    finally:
        await client.close()


def _trip(target: CircuitBreaker, like: CircuitBreaker) -> None:
    target.state = like.state
    target.failure_count = like.failure_count
    target.last_failure_time = like.last_failure_time


def _open_breaker(seconds_since_failure: float) -> CircuitBreaker:
    """A breaker tripped the way five failed fetches trip it."""
    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
    for _ in range(5):
        breaker.on_failure(RuntimeError("fetch failed"))
    assert breaker.state == "open"
    breaker.last_failure_time = time.time() - seconds_since_failure
    return breaker


class TestLiveness:
    """``/healthz`` answers while the process serves, whatever else is true."""

    @pytest.mark.parametrize("transport", NETWORKED)
    async def test_answers_200_without_a_token_on_a_server_that_requires_one(
        self, public_pem: str, transport: str
    ) -> None:
        method, guarded_path = _GUARDED[transport]
        async with _client(_settings(public_pem), transport) as c:
            guarded = await c.request(method, guarded_path, json={})
            health = await c.get("/healthz")

        assert guarded.status_code == 401
        assert health.status_code == 200
        assert health.content == b""
        assert health.headers["cache-control"] == "no-store"

    async def test_answers_200_with_sign_in_discovery_on(self, public_pem: str) -> None:
        """The provider that publishes metadata guards the same paths."""
        app_settings = _settings(
            public_pem, mcp_auth_base_url="https://mcp.http-health.test"
        )
        async with _client(app_settings) as c:
            guarded = await c.post("/mcp", json={})
            health = await c.get("/healthz")
            ready = await c.get("/readyz")

        assert guarded.status_code == 401
        assert health.status_code == 200
        assert ready.status_code == 503

    async def test_answers_200_while_the_server_is_not_ready(
        self, public_pem: str
    ) -> None:
        http_health._content_host.reachable = False
        async with _client(_settings(public_pem)) as c:
            ready = await c.get("/readyz")
            health = await c.get("/healthz")

        assert ready.status_code == 503
        assert health.status_code == 200

    async def test_a_head_request_is_answered_too(self, public_pem: str) -> None:
        async with _client(_settings(public_pem)) as c:
            health = await c.head("/healthz")

        assert health.status_code == 200


class TestReadiness:
    """``/readyz`` is 200 only when both facts say documents can be fetched."""

    async def _ready(self, public_pem: str, transport: str = "http") -> httpx.Response:
        async with _client(_settings(public_pem), transport) as c:
            return await c.get("/readyz")

    async def test_503_until_the_content_host_has_been_asked(
        self, public_pem: str
    ) -> None:
        response = await self._ready(public_pem)

        assert response.status_code == 503
        assert response.content == b""
        assert response.headers["cache-control"] == "no-store"

    @pytest.mark.parametrize("transport", NETWORKED)
    async def test_200_once_the_content_host_has_answered(
        self, public_pem: str, transport: str
    ) -> None:
        http_health._content_host.reachable = True

        response = await self._ready(public_pem, transport)

        assert response.status_code == 200
        assert response.content == b""

    async def test_503_after_the_content_host_stopped_answering(
        self, public_pem: str
    ) -> None:
        http_health._content_host.reachable = False

        assert (await self._ready(public_pem)).status_code == 503

    async def test_503_while_the_fetch_breaker_refuses_calls(
        self, public_pem: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        http_health._content_host.reachable = True
        async with _client_with(monkeypatch, _open_breaker(seconds_since_failure=1)):
            assert (await self._ready(public_pem)).status_code == 503

    async def test_503_once_connect_errors_have_opened_the_breaker(
        self, public_pem: str, monkeypatch: pytest.MonkeyPatch, fast_retries: None
    ) -> None:
        """The breaker ``/readyz`` reads is the one document fetches open (#307).

        Fetches used to pass two breakers and ``/readyz`` read the second;
        the deployment guide documented the case where it read the closed one.
        """
        http_health._content_host.reachable = True

        async def refuse(request: httpx.Request, **_: Any) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        async with _client_with(monkeypatch) as client:
            monkeypatch.setattr(client._client, "send", refuse)
            for _ in range(5):
                with pytest.raises(httpx.ConnectError):
                    await client.fetch_text(f"{server_settings.base_url}/x.md")

            assert (await self._ready(public_pem)).status_code == 503

    async def test_200_again_once_the_breaker_would_let_a_call_through(
        self, public_pem: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An instance taken out of rotation gets no call that could close it.

        The breaker leaves ``open`` only when a call arrives after its window.
        A readiness answer that followed ``state`` alone would stay 503 for
        ever behind a load balancer that had stopped sending calls.
        """
        http_health._content_host.reachable = True
        async with _client_with(
            monkeypatch, _open_breaker(seconds_since_failure=61)
        ) as client:
            response = await self._ready(public_pem)

            assert response.status_code == 200
            # Asking left the breaker as it was.
            assert client.circuit_breaker(server_settings.base_url).state == "open"

    async def test_200_with_a_closed_breaker(
        self, public_pem: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        http_health._content_host.reachable = True
        async with _client_with(monkeypatch):
            assert (await self._ready(public_pem)).status_code == 200

    async def test_the_breaker_read_belongs_to_the_running_client(
        self, public_pem: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The tests above stand in for the accessor; this one does not."""
        monkeypatch.undo()
        monkeypatch.setattr(http_health._content_host, "reachable", True)
        client = await fetch.get_http_client()
        _trip(
            client.circuit_breaker(server_settings.base_url),
            _open_breaker(seconds_since_failure=1),
        )
        try:
            assert fetch.running_http_client() is client
            assert (await self._ready(public_pem)).status_code == 503
        finally:
            await fetch.close_http_client()

    async def test_asking_builds_no_content_service_and_sends_no_request(
        self, public_pem: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The handlers read; they start nothing on the caller's behalf."""
        monkeypatch.undo()  # the real accessor, not the fixture's stand-in
        monkeypatch.setattr(http_health._content_host, "reachable", True)
        monkeypatch.setattr(_MANAGER, "_content_service", None)
        await fetch.close_http_client()
        assert fetch.running_http_client() is None
        asked: list[str] = []

        async def no_client() -> None:
            # Recorded, not raised: the probe turns any exception into False.
            asked.append("client")
            raise RuntimeError("no client in this test")

        monkeypatch.setattr(http_health, "get_http_client", no_client)

        async with _client(_settings(public_pem)) as c:
            ready = await c.get("/readyz")
            health = await c.get("/healthz")
            await asyncio.sleep(0.01)  # anything scheduled would have run

        assert (ready.status_code, health.status_code) == (200, 200)
        assert asked == []
        assert _MANAGER._content_service is None
        assert fetch.running_http_client() is None


class _FakeClient:
    """Stands in for the shared HTTP client; records what it was asked for."""

    def __init__(self, outcome: int | BaseException | None) -> None:
        self.outcome = outcome
        self.urls: list[str] = []
        self.asked = asyncio.Event()

    async def probe_status(self, url: str) -> int:
        self.urls.append(url)
        self.asked.set()
        if self.outcome is None:
            await asyncio.Event().wait()  # never answers
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        assert self.outcome is not None
        return self.outcome


def _use(monkeypatch: pytest.MonkeyPatch, client: _FakeClient) -> None:
    async def get_client() -> _FakeClient:
        return client

    monkeypatch.setattr(http_health, "get_http_client", get_client)


class TestOneProbe:
    """What one request to the content host is taken to mean."""

    @pytest.mark.parametrize(
        ("outcome", "expected"),
        [
            (200, True),
            # The file was renamed upstream, or a mirror does not carry it:
            # the host is there, which is all this asks.
            (404, True),
            (400, True),
            (302, True),
            (499, True),
            (429, False),
            (500, False),
            (502, False),
            (503, False),
            (504, False),
            (httpx.ConnectError("no route"), False),
            (httpx.ReadTimeout("slow"), False),
            (ValueError("Blocked unsafe URL"), False),
        ],
    )
    async def test_outcome(
        self,
        monkeypatch: pytest.MonkeyPatch,
        outcome: int | BaseException,
        expected: bool,
    ) -> None:
        client = _FakeClient(outcome)
        _use(monkeypatch, client)

        assert await http_health._content_host_answers() is expected
        assert client.urls == [f"{server_settings.base_url}/index.md"]

    async def test_a_request_that_never_answers_counts_as_no_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _use(monkeypatch, _FakeClient(None))
        monkeypatch.setattr(http_health, "_PROBE_DEADLINE_SECONDS", 0.05)

        answered = await asyncio.wait_for(
            http_health._content_host_answers(), timeout=5
        )

        assert answered is False

    def test_the_deadline_is_shorter_than_a_document_fetch_may_take(self) -> None:
        """A silent host is noticed in seconds, whatever the HTTP timeout is.

        The deadline was ``FINOS_MCP_HTTP_TIMEOUT``, 30 seconds by default, and
        an unanswered request is repeated once: about a minute of 200 from
        ``/readyz`` with a host that had stopped answering (#262).

        The setting's default is read from the class: ``Settings()`` reads the
        shell, where ``FINOS_MCP_HTTP_TIMEOUT=5`` is a valid value (#267).
        """
        assert http_health._PROBE_DEADLINE_SECONDS == 5.0
        assert (
            http_health._PROBE_DEADLINE_SECONDS
            < Settings.model_fields["http_timeout"].default
        )

    async def test_a_client_that_cannot_be_built_counts_as_no_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def no_client() -> None:
            raise RuntimeError("cannot build")

        monkeypatch.setattr(http_health, "get_http_client", no_client)

        assert await http_health._content_host_answers() is False

    async def test_cancellation_is_not_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The watch is stopped by cancelling it, mid-request if need be.

        The cancel lands once the request is in flight (#373): before it,
        the task is cancelled whatever the probe does with the error.
        """
        client = _FakeClient(None)
        _use(monkeypatch, client)
        probe = asyncio.create_task(http_health._content_host_answers())
        await asyncio.wait_for(client.asked.wait(), timeout=5)

        probe.cancel()
        done, _ = await asyncio.wait({probe}, timeout=5)

        assert done and probe.cancelled()


class TestProbeRequest:
    """The probe's request observes the host; it does not act on fetches.

    Routed through ``HTTPClient.get``, two unanswered probes opened the host's
    circuit breaker, and the server then refused document fetches for a minute
    after the host was back, on deployments that never read ``/readyz`` too.
    """

    URL = "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs/index.md"

    @asynccontextmanager
    async def _http_client(self, handler: Any) -> AsyncIterator[HTTPClient]:
        client = HTTPClient()
        await client._client.aclose()
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            yield client
        finally:
            await client.close()

    async def test_returns_the_status_the_host_answered(self) -> None:
        async with self._http_client(lambda _request: httpx.Response(404)) as client:
            assert await client.probe_status(self.URL) == 404

    async def test_unanswered_probes_do_not_make_a_fetch_be_refused(self) -> None:
        calls: list[str] = []
        host_is_up = False

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if not host_is_up:
                raise httpx.ConnectError("no route", request=request)
            return httpx.Response(200, text="document")

        async with self._http_client(handler) as client:
            for _ in range(6):  # one more than opens the breaker
                with pytest.raises(httpx.ConnectError):
                    await client.probe_status(self.URL)
            # One request per probe: no retry.
            assert len(calls) == 6

            host_is_up = True
            fetched = await client.fetch_text(self.URL)

        assert fetched == "document"
        # The fetch was answered by the handler above, not by the network.
        assert len(calls) == 7

    async def test_a_redirect_is_reported_and_not_followed(self) -> None:
        """The URL checks cover the URL asked for, not one a host points to."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(
                302, headers={"location": "https://169.254.169.254/latest"}
            )

        async with self._http_client(handler) as client:
            # The test's own client must have the setting the real one has.
            client._client.follow_redirects = HTTPClient()._client.follow_redirects
            assert await client.probe_status(self.URL) == 302

        assert calls == [self.URL]

    async def test_an_open_breaker_does_not_stop_the_probe(self) -> None:
        """The two facts ``/readyz`` reads stay independent of each other."""
        async with self._http_client(lambda _request: httpx.Response(200)) as client:
            breaker = client.circuit_breaker(self.URL)
            for _ in range(5):
                breaker.on_failure(RuntimeError("fetch failed"))
            # The same client, in the same state, refuses a fetch.
            with pytest.raises(CircuitBreakerError):
                await client.get(self.URL)

            assert await client.probe_status(self.URL) == 200
            # And observing left the breaker as it was.
            assert breaker.state == "open"

    @pytest.mark.parametrize(
        ("url", "reason"),
        [
            ("https://169.254.169.254/latest/meta-data", "Blocked unsafe URL"),
            ("https://example.com/index.md", "non-allowlisted host"),
        ],
    )
    async def test_a_url_the_client_must_not_request_is_not_requested(
        self, url: str, reason: str
    ) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(200)

        async with self._http_client(handler) as client:
            # The handler answers, so only the check can be what stops this.
            assert await client.probe_status(self.URL) == 200
            with pytest.raises(ValueError, match=reason):
                await client.probe_status(url)

        assert calls == [self.URL]


class TestWatch:
    """The background task that keeps the last probe result current."""

    async def _run_watch(
        self, monkeypatch: pytest.MonkeyPatch, answers: list[bool | BaseException]
    ) -> tuple[list[bool | None], list[float]]:
        """Run the watch over ``answers``, one per probe.

        Returns the recorded state at each sleep, and the sleeps.
        """
        remaining = list(answers)
        seen: list[bool | None] = []
        sleeps: list[float] = []

        async def probe() -> bool:
            answer = remaining.pop(0)
            if isinstance(answer, BaseException):
                raise answer
            return answer

        async def sleep(seconds: float) -> None:
            sleeps.append(seconds)
            seen.append(http_health._content_host.reachable)
            if not remaining:
                raise asyncio.CancelledError

        monkeypatch.setattr(http_health, "_content_host_answers", probe)
        monkeypatch.setattr("finos_mcp.http_health.asyncio.sleep", sleep)

        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(http_health.watch_content_host(), timeout=5)

        assert remaining == []
        return seen, sleeps

    INTERVAL = server_settings.readiness_probe_interval_seconds
    RECHECK = http_health._RECHECK_SECONDS

    async def test_each_round_replaces_the_last_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen, sleeps = await self._run_watch(monkeypatch, [True, False, False, True])

        # At the recheck the state is still the one before it.
        assert seen == [True, True, False, True]
        assert sleeps == [self.INTERVAL, self.RECHECK, self.INTERVAL, self.INTERVAL]

    async def test_one_unanswered_request_does_not_change_a_ready_server(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A single lost request would otherwise cost a whole interval of 503."""
        with caplog.at_level(logging.INFO, logger=HEALTH_LOGGER):
            seen, sleeps = await self._run_watch(monkeypatch, [True, False, True])

        assert seen == [True, True, True]
        assert sleeps == [self.INTERVAL, self.RECHECK, self.INTERVAL]
        assert [r.levelno for r in caplog.records if r.name == HEALTH_LOGGER] == [
            logging.INFO
        ]

    @pytest.mark.parametrize("before", [None, False])
    async def test_a_server_that_is_not_ready_is_not_rechecked(
        self, monkeypatch: pytest.MonkeyPatch, before: bool | None
    ) -> None:
        http_health._content_host.reachable = before

        seen, sleeps = await self._run_watch(monkeypatch, [False, False])

        assert seen == [False, False]
        assert sleeps == [self.INTERVAL, self.INTERVAL]

    async def test_a_probe_that_raises_is_a_failed_probe_and_the_watch_goes_on(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A watch that died would leave its last answer standing for ever."""
        failure = RuntimeError("unexpected")
        seen, _ = await self._run_watch(monkeypatch, [True, failure, failure, True])

        assert seen == [True, True, False, True]

    async def test_a_change_is_logged_once_and_a_repeat_is_not(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger=HEALTH_LOGGER):
            await self._run_watch(monkeypatch, [True, True, False, False, False, True])

        records = [
            (r.levelno, r.getMessage())
            for r in caplog.records
            if r.name == HEALTH_LOGGER
        ]
        assert [level for level, _ in records] == [
            logging.INFO,
            logging.WARNING,
            logging.INFO,
        ]
        assert "503" in records[1][1]
        assert server_settings.base_url in records[1][1]

    async def test_cancelling_the_watch_during_a_probe_ends_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        in_flight = asyncio.Event()

        async def probe() -> bool:
            in_flight.set()
            await asyncio.Event().wait()
            return True

        monkeypatch.setattr(http_health, "_content_host_answers", probe)
        watch = asyncio.create_task(http_health.watch_content_host())
        await asyncio.wait_for(in_flight.wait(), timeout=5)

        watch.cancel()
        done, _ = await asyncio.wait({watch}, timeout=5)

        assert done and watch.cancelled()


class TestWiring:
    """The routes and the watch reach the server that is actually run."""

    async def test_the_assembled_server_serves_both_urls(self) -> None:
        app = fastmcp_server.mcp.http_app(path="/mcp")
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as c:
                health = await c.get("/healthz")
                ready = await c.get("/readyz")
                unknown = await c.get("/livez")

        assert health.status_code == 200
        assert ready.status_code == 503
        assert unknown.status_code == 404

    @staticmethod
    def _stub_watch(
        started: asyncio.Event, stopped: asyncio.Event, swallow_first_cancel: bool
    ) -> Any:
        """A watch that takes several loop steps to unwind, as a real one does.

        It can also ignore one cancellation, which ``asyncio.wait_for`` did on
        Python 3.11 when the awaited call finished in the same step.
        """

        async def watch() -> None:
            started.set()
            try:
                if swallow_first_cancel:
                    with contextlib.suppress(asyncio.CancelledError):
                        await asyncio.Event().wait()
                await asyncio.Event().wait()
            finally:
                for _ in range(5):
                    await asyncio.sleep(0)
                stopped.set()

        return watch

    @pytest.mark.parametrize(
        ("transport", "watched"),
        [*((name, True) for name in NETWORKED), ("stdio", False)],
    )
    @pytest.mark.parametrize("swallow_first_cancel", [False, True])
    async def test_the_watch_runs_while_a_networked_server_serves(
        self,
        monkeypatch: pytest.MonkeyPatch,
        transport: str,
        watched: bool,
        swallow_first_cancel: bool,
    ) -> None:
        started = asyncio.Event()
        stopped = asyncio.Event()
        observed: list[bool] = []

        async def run_async(**_kwargs: object) -> None:
            await asyncio.sleep(0.01)  # let a started watch reach its first await
            observed.append(started.is_set() and not stopped.is_set())

        monkeypatch.setattr(
            fastmcp_main,
            "watch_content_host",
            self._stub_watch(started, stopped, swallow_first_cancel),
        )
        with (
            patch("finos_mcp.fastmcp_main.settings.mcp_transport", transport),
            patch("finos_mcp.fastmcp_main.mcp.run_async", run_async),
        ):
            await asyncio.wait_for(fastmcp_main._serve(), timeout=5)

        assert observed == [watched]
        # Nothing is left running once the server has returned.
        assert stopped.is_set() is watched

    async def test_the_watch_is_stopped_when_the_server_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def run_async(**_kwargs: object) -> None:
            await asyncio.sleep(0.01)
            raise SystemExit(3)  # what uvicorn raises for a port in use

        monkeypatch.setattr(
            fastmcp_main,
            "watch_content_host",
            self._stub_watch(started, stopped, False),
        )
        # asyncio.timeout, not wait_for: on 3.11 wait_for runs _serve in a task
        # of its own, and a SystemExit raised in a task leaves the event loop
        # instead of reaching pytest.raises here (#393). Production awaits
        # run_async in the caller's task, as this does.
        with (
            patch("finos_mcp.fastmcp_main.settings.mcp_transport", "http"),
            patch("finos_mcp.fastmcp_main.mcp.run_async", run_async),
            pytest.raises(SystemExit),
        ):
            async with asyncio.timeout(5):
                await fastmcp_main._serve()

        assert started.is_set() and stopped.is_set()


class TestBreakerReading:
    """``is_refusing`` reports what ``can_execute`` would do, and changes nothing."""

    def test_a_closed_breaker_is_not_refusing(self) -> None:
        assert CircuitBreaker().is_refusing() is False

    def test_an_open_breaker_refuses_inside_its_window_only(self) -> None:
        inside = _open_breaker(seconds_since_failure=59)
        outside = _open_breaker(seconds_since_failure=61)

        assert inside.is_refusing() is True
        assert outside.is_refusing() is False
        # The same two breakers, asked the question that does change state.
        assert inside.can_execute() is False
        assert outside.can_execute() is True

    def test_a_half_open_breaker_is_not_refusing(self) -> None:
        breaker = _open_breaker(seconds_since_failure=61)
        assert breaker.can_execute() is True
        assert breaker.state == "half-open"

        assert breaker.is_refusing() is False


class TestIntervalSetting:
    def test_default_is_thirty_seconds(self) -> None:
        assert Settings().readiness_probe_interval_seconds == 30

    @pytest.mark.parametrize("value", [4, 3601])
    def test_out_of_range_is_refused(self, value: int) -> None:
        with pytest.raises(ValidationError, match="readiness_probe_interval_seconds"):
            Settings(readiness_probe_interval_seconds=value)

    @pytest.mark.parametrize("value", [5, 3600])
    def test_bounds_are_accepted(self, value: int) -> None:
        assert (
            Settings(
                readiness_probe_interval_seconds=value
            ).readiness_probe_interval_seconds
            == value
        )
