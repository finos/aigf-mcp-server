#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The two URLs a networked server answers without a token.

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

A load balancer or an orchestrator holds no token and speaks no MCP, so the
``get_service_health`` tool is out of its reach. Without these routes it could
only check that the port answered (#255).

``GET /healthz`` answers 200 while the process serves HTTP.

``GET /readyz`` answers 200 when the server can fetch documents as far as it
can tell without doing work for the caller, and 503 otherwise. It reads two
facts:

- what the last request of ``watch_content_host`` found. That task asks the
  content host for one small file at a fixed interval, so a server that
  receives no calls still notices that the host has gone. Until its first
  request has finished the answer is 503.
- whether the HTTP client's circuit breaker for the content host is refusing
  calls. That one is driven by real document fetches, so it also covers a host
  that answers 429 or 5xx to documents, which the request above may not see.

Neither route has a body, and neither handler starts a request, builds a
service or takes a lock: what a caller can learn is one bit. fastmcp serves
custom routes without requiring a token and outside the MCP middleware, so the
rate limit that applies to tool calls does not apply here. It does verify a
``Bearer`` header that a request carries, on these paths as on a path that
answers 404, which with a JWKS verifier can fetch the key set.
"""

import asyncio

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import Response

from .app import mcp, settings
from .content.fetch import get_http_client, running_http_client
from .logging import get_logger

logger = get_logger("http_health")

#: Seconds one request to the content host may take before it counts as
#: unanswered. Not ``FINOS_MCP_HTTP_TIMEOUT``: that bounds a whole document
#: fetch, 30 seconds by default, and an unanswered probe is repeated once, so
#: ``/readyz`` answered 200 for about a minute after the host had stopped
#: answering (#262).
_PROBE_DEADLINE_SECONDS = 5.0

#: The file the probe asks for, under the base URL. The Jekyll landing page of
#: the framework's ``docs`` directory, 1.3 kB.
_PROBE_FILE = "index.md"

#: Seconds before a request that got no answer is repeated, when the last one
#: before it was answered. One lost request would otherwise make ``/readyz``
#: answer 503 for a whole interval: a checker that acts only on several failed
#: checks in a row would see them all, from a single request.
_RECHECK_SECONDS = 2.0

#: A proxy between the checker and this server must not answer for it.
_HEADERS = {"Cache-Control": "no-store"}


class _ContentHost:
    """What the last request to the content host found."""

    def __init__(self) -> None:
        #: None until the first request has finished.
        self.reachable: bool | None = None


_content_host = _ContentHost()


async def _content_host_answers() -> bool:
    """Ask the content host for one file once; report whether it answered.

    A 429 or a 5xx is the host saying it will not serve; any other status is
    the host being there. That includes 404: if the file is renamed upstream,
    or a mirror does not carry it, reading 404 as a failure would take every
    instance out of rotation at once. No answer at all, a URL the client
    refuses to fetch and a client that cannot be built all count as not
    answering.

    The request is one attempt outside the client's retries and circuit
    breaker (``HTTPClient.probe_status``), so a probe cannot make a document
    fetch be refused.
    """
    try:
        client = await get_http_client()
        # Not ``asyncio.wait_for``: on Python 3.11 it returns the result and
        # drops a cancellation that arrives in the same loop step.
        async with asyncio.timeout(_PROBE_DEADLINE_SECONDS):
            status = await client.probe_status(f"{settings.base_url}/{_PROBE_FILE}")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.debug("Content host request failed: %s: %s", type(e).__name__, e)
        return False
    return status != 429 and status < 500


def _note(reachable: bool) -> None:
    """Record a probe result, logging it only when it differs from the last."""
    if reachable is not _content_host.reachable:
        if reachable:
            logger.info(
                "Content host %s answers; GET /readyz no longer answers 503 "
                "on its account",
                settings.base_url,
            )
        else:
            logger.warning(
                "Content host %s does not answer; GET /readyz answers 503 "
                "until it does",
                settings.base_url,
            )
    _content_host.reachable = reachable


async def _probe() -> bool:
    """Run one probe; one that raises is a failed one.

    A watch that ended would leave its last answer standing for as long as the
    process lived.
    """
    try:
        return await _content_host_answers()
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Content host probe raised: %s", e, exc_info=True)
        return False


async def watch_content_host() -> None:
    """Keep the last probe result current until cancelled.

    Run by the entry point beside a networked server. A request that gets no
    answer while the host was answering is repeated once before it is
    believed; see ``_RECHECK_SECONDS``.
    """
    while True:
        reachable = await _probe()
        if not reachable and _content_host.reachable:
            await asyncio.sleep(_RECHECK_SECONDS)
            reachable = await _probe()
        _note(reachable)
        await asyncio.sleep(settings.readiness_probe_interval_seconds)


def _fetch_breaker_refuses() -> bool:
    """True while the HTTP client would refuse a fetch from the content host.

    Read through ``is_refusing`` and not ``state``: the breaker leaves ``open``
    only when a call arrives after its window, and an instance a load balancer
    has taken out of rotation receives none.
    """
    client = running_http_client()
    return client is not None and client.is_refusing(settings.base_url)


async def healthz(_request: Request) -> Response:
    """Answer 200: the process is serving HTTP."""
    return Response(status_code=200, headers=_HEADERS)


async def readyz(_request: Request) -> Response:
    """Answer 200 if documents can be fetched as far as the server knows."""
    ready = _content_host.reachable is True and not _fetch_breaker_refuses()
    return Response(status_code=200 if ready else 503, headers=_HEADERS)


def register_health_routes(server: FastMCP) -> None:
    """Add both routes to ``server``'s HTTP app. Stdio serves no HTTP."""
    server.custom_route("/healthz", methods=["GET"], include_in_schema=False)(healthz)
    server.custom_route("/readyz", methods=["GET"], include_in_schema=False)(readyz)


register_health_routes(mcp)
