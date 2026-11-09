# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""HTTP client with timeout, retry logic, and circuit breaker for FINOS MCP Server.

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

This module provides a robust HTTP client that handles:
- Exponential backoff with jitter for retries
- Circuit breaker pattern for API failure protection
- Comprehensive timeout configuration (connect, read, total)
- Connection pooling for performance
- Structured logging integration
"""

import asyncio
import logging
import time
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .. import __version__
from ..config import Settings, get_settings
from ..error_boundary import CircuitBreaker
from ..exceptions import CircuitBreakerError, HTTPClientError
from ..logging import get_logger, log_http_request
from ..loop_binding import must_rebind
from ..security.content_filter import (
    content_security_validator,
    is_allowed_fetch_target,
)
from ..security.repo_target import why_not_a_fetch_target

# Module-level logger for code that has no HTTPClient instance to borrow one
# from -- HTTPClientManager in particular. Mirrors cache.py, so these records
# stay inside the project's structured logging rather than arriving from a bare
# logging.getLogger() that is not a child of the app logger. Named for the
# manager rather than "http_client", which HTTPClient's own per-instance logger
# already uses, so a discarded-client record is told apart from a request log.
logger = get_logger("http_client_manager")

# Content hosts this server is allowed to reach. The host from the configured
# base_url is added at runtime so GitHub Enterprise and mirror deployments work
# without widening the default.
_DEFAULT_FETCH_HOSTS = frozenset({"raw.githubusercontent.com", "api.github.com"})

#: Headers that described the wire form of a body ``_whole`` has decoded.
_WIRE_FRAMING_HEADERS = frozenset(
    {b"content-encoding", b"content-length", b"transfer-encoding"}
)


class HTTPClient:
    """HTTP client with retry logic, a per-host circuit breaker and one connection pool.

    Features:
    - Exponential backoff with jitter
    - Circuit breaker protection
    - Comprehensive timeout handling
    - Structured logging integration
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize HTTP client."""
        self.settings = settings or get_settings()
        self.logger = get_logger("http_client")

        # Hosts this client may fetch from (SSRF allowlist)
        base_host = urlparse(self.settings.base_url).hostname
        self._allowed_fetch_hosts = _DEFAULT_FETCH_HOSTS | (
            {base_host} if base_host else set()
        )

        # Circuit breakers per host
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

        timeout_config = httpx.Timeout(
            connect=min(10.0, self.settings.http_timeout / 3),
            read=self.settings.http_timeout,
            write=10.0,
            pool=5.0,
        )

        # The one client, for the life of this object. A pool that resized
        # itself rebuilt this on the first request and closed the client in
        # use under requests in flight (#306); the readiness probe and the
        # "redirects are not followed" control both read this object.
        self._client = httpx.AsyncClient(
            timeout=timeout_config,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=30.0,
            ),
            # Redirects are NOT followed, so a redirect chain cannot be used to
            # reach internal infrastructure. Callers surface an unfollowed 3xx as
            # an error rather than treating the empty body as content.
            follow_redirects=False,
            headers={"User-Agent": f"finos-mcp/{__version__}"},
        )

    def circuit_breaker(self, url: str) -> CircuitBreaker:
        """The breaker for ``url``'s host, made on first ask.

        The one breaker a document fetch passes (#307): fed once per call,
        whatever the call's attempts, and read by ``/readyz`` through
        ``is_refusing`` and by ``get_service_health`` through the content
        service. Five failed calls in a row open it for 60 seconds.
        """
        parsed = urlparse(url)
        host_key = f"{parsed.scheme}://{parsed.netloc}"

        if host_key not in self._circuit_breakers:
            self._circuit_breakers[host_key] = CircuitBreaker()

        return self._circuit_breakers[host_key]

    def is_refusing(self, url: str) -> bool:
        """Whether a request to ``url``'s host would be refused now, changing nothing."""
        return self.circuit_breaker(url).is_refusing()

    @staticmethod
    def _says_the_host_is_failing(status: int) -> bool:
        """Whether an answer is evidence against the host, for the breaker.

        A 429 or a 5xx is the host saying it will not serve. Any other answer
        is the host serving, however unusable the document: a 404, a 403, a
        redirect. Those are the document's failure, and five of them for one
        document must not refuse every other document and turn ``/readyz`` to
        503 (#284). No answer at all is counted by the caller.
        """
        return status == 429 or status >= 500

    def _refuse_unsafe_target(self, url: str) -> None:
        """Raise ``ValueError`` for a URL this client must not request.

        SSRF protection, applied before every HTTP call so that manipulated URLs
        (e.g. from a compromised upstream response) cannot reach internal
        infrastructure. Two layers, checked in this order so that an attempt on
        an internal address is logged as such rather than as an allowlist miss:
          1. reject non-globally-routable addresses
          2. reject any host outside the content-host allowlist
        """
        reason = why_not_a_fetch_target(url)
        if reason:
            self.logger.warning("Blocked fetch target %s: %s", url, reason)
            raise ValueError(f"Blocked unsafe URL: {url}: {reason}")

        if not is_allowed_fetch_target(url, self._allowed_fetch_hosts):
            raise ValueError(
                f"Blocked fetch to non-allowlisted host: {urlparse(url).hostname}"
            )

    async def probe_status(self, url: str) -> int:
        """Send one GET and return the status code, as an observer.

        For the readiness watch, which asks whether the host answers and must
        not change how document fetches behave. So this is one attempt with no
        retry, and it neither consults nor feeds the host's circuit breaker:
        routed through ``get``, two unanswered probes opened that breaker and
        the server refused document fetches for the next minute, including on
        a deployment where nothing reads the readiness answer. The URL checks
        are the ones every request gets.

        Raises:
            ValueError: If the URL is one this client must not request
            httpx.RequestError: If no response arrives

        """
        self._refuse_unsafe_target(url)
        response = await self._client.send(
            self._client.build_request("GET", url), stream=True
        )
        # The status is all the probe uses; the body is not read (#291).
        await response.aclose()
        return response.status_code

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """One call: refused by the host's breaker, or made and counted once.

        The breaker is outside the retried request, so a call that got no
        answer in three attempts is one failure, not three: five failed calls
        open it, as the deployment guide says. What counts as a failure is no
        answer (``httpx.RequestError`` after the retries) or an answer of 429
        or 5xx; any other answer closes it. A URL this client refuses raises
        ``ValueError`` from the request itself and counts for nothing.

        The whole call, attempts and body included, ends when
        ``FINOS_MCP_HTTP_TIMEOUT`` says (#291): the per-phase timeouts alone
        let a host that sends one byte every 29 seconds hold a fetch for ever.
        A call cut off that way is no answer. The body is read as it arrives
        and refused past the size limit, so the answer returned here is whole
        and bounded.
        """
        circuit_breaker = self.circuit_breaker(url)
        if not circuit_breaker.can_execute():
            raise CircuitBreakerError(
                service_name=urlparse(url).netloc,
                failure_count=circuit_breaker.failure_count,
                retry_after=int(circuit_breaker.recovery_timeout),
            )
        try:
            async with asyncio.timeout(self.settings.http_timeout):
                response = await self._make_request(method, url, **kwargs)
                if self._says_the_host_is_failing(response.status_code):
                    circuit_breaker.on_failure(f"{response.status_code} from {url}")
                else:
                    circuit_breaker.on_success()
                return await self._whole(response)
        except (httpx.RequestError, TimeoutError) as e:
            circuit_breaker.on_failure(e)
            raise

    @staticmethod
    async def _whole(response: httpx.Response) -> httpx.Response:
        """Read a streamed answer within the size limit and return it whole.

        A ``Content-Length`` above the limit is refused before a body byte is
        read; otherwise the body is counted as it arrives, after the transfer
        decoding, so a small gzip body that decodes past the limit is refused
        too, within one chunk of the limit. The answer comes back as a new
        ``Response`` holding the decoded body, without the framing headers
        that described the wire form, so callers read ``.text``, ``.json()``
        and the headers as they always did.
        """
        limit = content_security_validator.max_content_size
        url = str(response.request.url)
        declared = response.headers.get("content-length", "")
        chunks: list[bytes] = []
        try:
            if declared.isdigit() and int(declared) > limit:
                raise HTTPClientError(
                    url=url,
                    status_code=response.status_code,
                    details=f"Content-Length {declared} exceeds the limit of {limit} bytes",
                )
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > limit:
                    raise HTTPClientError(
                        url=url,
                        status_code=response.status_code,
                        details=f"the body exceeds the limit of {limit} bytes",
                    )
                chunks.append(chunk)
        finally:
            await response.aclose()
        return httpx.Response(
            response.status_code,
            headers=[
                (name, value)
                for name, value in response.headers.raw
                if name.lower() not in _WIRE_FRAMING_HEADERS
            ],
            content=b"".join(chunks),
            request=response.request,
            extensions=response.extensions,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(multiplier=0.5, max=10.0, jitter=2.0),
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)
        ),
        reraise=True,
        before_sleep=before_sleep_log(get_logger("http_client"), logging.WARNING),
        after=after_log(get_logger("http_client"), logging.INFO),
    )
    async def _make_request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """Make one HTTP request, repeated up to twice when it gets no answer.

        The URL checks sit here, where the request is sent, so no route
        around the breaker reaches the network unchecked.
        """
        self._refuse_unsafe_target(url)
        start_time = time.time()

        try:
            # Streamed: the body is read, counted and bounded by ``_whole``.
            response = await self._client.send(
                self._client.build_request(method, url, **kwargs), stream=True
            )
        except httpx.RequestError as e:
            log_http_request(
                self.logger,
                method=method.upper(),
                url=url,
                status_code=None,
                response_time=time.time() - start_time,
                extra_data={"error": str(e), "error_type": type(e).__name__},
            )
            raise

        log_http_request(
            self.logger,
            method=method.upper(),
            url=url,
            status_code=response.status_code,
            response_time=time.time() - start_time,
            extra_data={"content_length": response.headers.get("content-length")},
        )
        return response

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make GET request with retry and circuit breaker.

        Args:
            url: Request URL
            params: Query parameters
            headers: Additional headers
            **kwargs: Additional httpx parameters

        Returns:
            HTTP response

        Raises:
            CircuitBreakerError: If circuit breaker is open
            httpx.RequestError: If request fails after retries

        """
        return await self._request("GET", url, params=params, headers=headers, **kwargs)

    @staticmethod
    def _check_response(response: httpx.Response) -> None:
        """Raise if the response is an unfollowed redirect or an error status.

        Redirects are not followed (see client construction), and
        raise_for_status() ignores 3xx, so without this an unfollowed redirect
        would be returned to callers as empty content.
        """
        if response.is_redirect:
            raise ValueError(
                f"Unfollowed redirect from {response.request.url} to "
                f"{response.headers.get('location', '<missing Location>')}"
            )
        response.raise_for_status()

    async def fetch_text(self, url: str, **kwargs: Any) -> str:
        """Fetch text content from URL.

        Args:
            url: URL to fetch
            **kwargs: Additional request parameters

        Returns:
            Text content

        Raises:
            ValueError: If the response is an unfollowed redirect
            httpx.HTTPStatusError: If response indicates error
            CircuitBreakerError: If circuit breaker is open

        """
        response = await self.get(url, **kwargs)
        self._check_response(response)
        return response.text

    async def close(self) -> None:
        """Close the connection pool."""
        await self._client.aclose()


class HTTPClientManager:
    """Singleton manager for the global HTTP client instance."""

    _instance: Optional["HTTPClientManager"] = None
    _http_client: HTTPClient | None = None
    _loop: asyncio.AbstractEventLoop | None = None

    def __new__(cls) -> "HTTPClientManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    #: What dropping the client costs. ``close_http_client()`` names the same
    #: loss on its own discard path; this is the acquisition-side wording.
    _DISCARD_COST = (
        "HTTPClient.close() does not run, so its connection pool is not closed."
    )

    async def get_http_client(self) -> HTTPClient:
        """Get shared HTTP client instance.

        The loop-change test is ``must_rebind()`` rather than an inline
        condition, so the abandoned client is recorded rather than dropped in
        silence.

        This is the third member of the family and the one #116 does not name.
        It carries the branch inline rather than in an ``_ensure_loop_context()``
        helper, which is why it stayed outside both the PR #111 diff -- that fixed
        this class's *closer* -- and #116's text. Probed: after a loop change,
        the caller gets a different client and ``aclose()`` never ran on the
        first one.

        The client is built from the process settings; a ``settings`` argument
        used to be accepted and ignored after the first call (#313).

        Returns:
            Shared HTTP client instance

        """
        current_loop = asyncio.get_running_loop()
        if must_rebind(
            bound_loop=self._loop,
            current_loop=current_loop,
            resource=self._http_client,
            resource_name="HTTP client",
            cost=self._DISCARD_COST,
            logger=logger,
        ):
            self._http_client = None
            self._loop = current_loop

        if self._http_client is None:
            self._http_client = HTTPClient()

        return self._http_client

    async def close_http_client(self) -> None:
        """Close the global HTTP client, unless another loop created it.

        A client is closed only on the loop that built it: its transports
        belong to that loop, and closing them from another raises. From any
        other loop the reference is dropped instead, which is what frees the
        socket (measured with ``lsof``: the connection is released when the
        client object is collected), and the log line says the pool was not
        closed.

        The reference is cleared before ``aclose()`` is awaited, not in a
        ``finally`` after it. ``aclose()`` marks the client closed before it
        awaits the transport, so a transport failure would otherwise leave a
        dead client on this manager for the next caller (#102); and while
        the await was suspended, a caller racing the teardown was handed the
        client being closed (#115, the cache's shape, probed here too). A
        failure still propagates: ``cleanup_resources()`` reports what failed.
        """
        if self._http_client is None:
            return

        if self._loop is not asyncio.get_running_loop():
            logger.info(
                "Discarding HTTP client without closing it: created on a "
                "different event loop, whose transports cannot be closed from "
                "here. Its connection pool is not closed."
            )
            self._http_client = None
            self._loop = None
            return

        dying = self._http_client
        self._http_client = None
        self._loop = None
        await dying.close()


# Global HTTP client manager instance
_http_client_manager = HTTPClientManager()


async def get_http_client() -> HTTPClient:
    """Get shared HTTP client instance."""
    return await _http_client_manager.get_http_client()


def running_http_client() -> HTTPClient | None:
    """Return the shared HTTP client if one has been built, else None.

    For a caller that reads the client's state and must not be the reason it
    exists: ``/readyz`` asks whether the content host's breaker is refusing.
    """
    return _http_client_manager._http_client


async def close_http_client() -> None:
    """Close and cleanup global HTTP client."""
    await _http_client_manager.close_http_client()
