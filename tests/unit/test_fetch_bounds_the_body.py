# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""A response body is bounded as it arrives, and a fetch has one deadline (#291).

The client downloaded and decompressed a response whole and the 10 MB check
ran on the decoded string afterwards, so a host answering for the content
host could make the server hold gigabytes of decompressed gzip. Its timeout
was per phase, so a host sending one byte every 29 seconds never timed out,
and a document fetch had no deadline across its three attempts. The
readiness probe read the body it did not need.

Now the body is read in chunks and counted after decoding, a request is
refused past the limit, a ``Content-Length`` above it is refused before the
body, the probe reads no body, and ``FINOS_MCP_HTTP_TIMEOUT`` bounds the
whole of one call, attempts and body included.

Every test runs the real ``HTTPClient`` over a mock transport.
"""

from __future__ import annotations

import asyncio
import gzip
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from finos_mcp.content.fetch import HTTPClient
from finos_mcp.exceptions import HTTPClientError
from finos_mcp.security.content_filter import content_security_validator

pytestmark = pytest.mark.unit

URL = "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs/x.md"
LIMIT = content_security_validator.max_content_size
CHUNK = 1024 * 1024


class _Stream(httpx.AsyncByteStream):
    """Yields ``chunks`` and records how much of it was asked for."""

    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.yielded = 0
        self.iterated = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        self.iterated = True
        for chunk in self.chunks:
            self.yielded += len(chunk)
            yield chunk

    async def aclose(self) -> None:
        return None


@pytest.fixture
async def client() -> AsyncIterator[Callable[[Callable[..., Any]], HTTPClient]]:
    """A real ``HTTPClient`` whose transport is ``handler``."""
    clients: list[HTTPClient] = []

    def _make(handler: Callable[..., Any]) -> HTTPClient:
        made = HTTPClient()
        made._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        clients.append(made)
        return made

    yield _make
    for made in clients:
        await made.close()


class TestBoundedBody:
    async def test_a_body_past_the_limit_is_refused_within_one_chunk(
        self, client: Callable[..., HTTPClient]
    ) -> None:
        stream = _Stream([b"x" * CHUNK] * 11)
        made = client(lambda request: httpx.Response(200, stream=stream))

        with pytest.raises(HTTPClientError, match="exceeds"):
            await made.fetch_text(URL)

        assert LIMIT < stream.yielded <= LIMIT + CHUNK, stream.yielded

    async def test_a_content_length_past_the_limit_is_refused_before_the_body(
        self, client: Callable[..., HTTPClient]
    ) -> None:
        stream = _Stream([b"x" * CHUNK] * 11)
        made = client(
            lambda request: httpx.Response(
                200, headers={"content-length": str(LIMIT + 1)}, stream=stream
            )
        )

        with pytest.raises(HTTPClientError, match="exceeds"):
            await made.fetch_text(URL)

        assert not stream.iterated, "the body was read although its length was known"

    async def test_the_limit_counts_decoded_bytes(
        self, client: Callable[..., HTTPClient]
    ) -> None:
        """A small gzip body that decodes past the limit is refused."""
        compressed = gzip.compress(b"0" * (LIMIT + 1))
        assert len(compressed) < LIMIT // 100
        made = client(
            lambda request: httpx.Response(
                200, headers={"content-encoding": "gzip"}, content=compressed
            )
        )

        with pytest.raises(HTTPClientError, match="exceeds"):
            await made.fetch_text(URL)

    async def test_a_gzip_body_within_the_limit_is_decoded(
        self, client: Callable[..., HTTPClient]
    ) -> None:
        made = client(
            lambda request: httpx.Response(
                200,
                headers={
                    "content-encoding": "gzip",
                    "content-type": "text/plain; charset=utf-8",
                },
                content=gzip.compress("# Título\n".encode()),
            )
        )

        assert await made.fetch_text(URL) == "# Título\n"

    async def test_a_json_answer_keeps_its_body_and_headers(
        self, client: Callable[..., HTTPClient]
    ) -> None:
        """The listing path reads ``get()``'s answer as before."""
        made = client(
            lambda request: httpx.Response(
                200,
                headers={"x-ratelimit-remaining": "41"},
                content=json.dumps([{"name": "a.md"}]).encode(),
            )
        )

        response = await made.get(URL)

        assert response.status_code == 200
        assert response.json() == [{"name": "a.md"}]
        assert response.headers["x-ratelimit-remaining"] == "41"

    async def test_an_error_status_is_still_raised_as_such(
        self, client: Callable[..., HTTPClient]
    ) -> None:
        made = client(lambda request: httpx.Response(404, text="gone"))

        with pytest.raises(httpx.HTTPStatusError):
            await made.fetch_text(URL)


class TestProbeReadsNoBody:
    async def test_probe_status_returns_the_status_without_the_body(
        self, client: Callable[..., HTTPClient]
    ) -> None:
        stream = _Stream([b"x" * CHUNK] * 11)
        made = client(lambda request: httpx.Response(200, stream=stream))

        assert await made.probe_status(URL) == 200
        assert not stream.iterated, "the probe read a body it does not use"


class TestOneDeadline:
    async def test_a_call_ends_at_the_timeout_and_counts_against_the_host(
        self, client: Callable[..., HTTPClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The whole call, attempts included, ends when the setting says.

        Without the deadline the handler answers 200 after its sleep, so
        ``raises`` alone tells the two apart; no clock is read.
        """

        async def slow(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(5)
            return httpx.Response(200, text="late")

        made = client(slow)
        monkeypatch.setattr(made.settings, "http_timeout", 0.3)

        with pytest.raises(TimeoutError):
            await made.fetch_text(URL)

        assert made.circuit_breaker(URL).failure_count == 1

    async def test_the_deadline_covers_the_body(
        self, client: Callable[..., HTTPClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A host that answers at once and then trickles the body is cut off."""

        class _Trickle(httpx.AsyncByteStream):
            async def __aiter__(self) -> AsyncIterator[bytes]:
                yield b"first"
                await asyncio.sleep(5)
                yield b"never"

            async def aclose(self) -> None:
                return None

        made = client(lambda request: httpx.Response(200, stream=_Trickle()))
        monkeypatch.setattr(made.settings, "http_timeout", 0.3)

        with pytest.raises(TimeoutError):
            await made.fetch_text(URL)
