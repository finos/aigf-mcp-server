# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""A fetched document body is served as written (#282).

Both fetch routes ran eight browser-XSS regexes over every body and refused
the document when one matched. Three of them matched ordinary prose: a
``javascript:`` label, a ``data:...base64`` fragment and, with no word
boundary, any ``<word>on<word> = "<text>"`` such as ``config = "x"``. The
last was quadratic on a long run of word characters: measured 1 s at 20 kB,
4 s at 40 kB and 16 s at 80 kB, on the event loop. The refusal was an
``MCPServerError``, so five reads of one such document opened the service's
fetch breaker of the time and ``/readyz`` answered 503 for every document.
(A served document counts for nothing on the one breaker left by #307, so
that case needs no test of its own here.)

The consumer is a model reading Markdown, not a browser; the trust boundary
is stated in ``SERVER_TRUST_INSTRUCTIONS``, and #122 declined "a guard
damaging real content in order to defend it". Censused on 2026-10-13 at
``finos/ai-governance-framework`` ``a149dd1``: of 72 files, the only two a
pattern matched were site pages this server never serves.

Every test here runs the real ``ContentService`` fetch routes over a stubbed
HTTP client, because the refusal lived inside those routes.
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from fastmcp import Client

from finos_mcp.content.discovery import (
    DiscoveryResult,
    DiscoveryServiceManager,
    GitHubFileInfo,
)
from finos_mcp.content.service import ContentService
from finos_mcp.fastmcp_server import mcp

#: Modules that look ``get_service`` up in their own namespace.
_GET_SERVICE_BINDERS = (
    "finos_mcp.documents.tools",
    "finos_mcp.documents.format",
    "finos_mcp.health_tools",
)

RISK_FILE = "ri-10_prompt-injection.md"

#: Prose that the removed patterns refused, with what refused it.
PROSE = [
    pytest.param('Set config = "x" before the first run.', id="assignment"),
    pytest.param("JavaScript: both must pin the version.", id="label"),
    pytest.param("<script>alert(1)</script> appears in the example.", id="script"),
]


def _document(body: str) -> str:
    return f"---\ntitle: Prompt Injection\n---\n\n## Summary\n\n{body}\n"


class _HTTPClient:
    """Serves one body."""

    def __init__(self, text: str) -> None:
        self.text = text

    async def fetch_text(self, url: str, **_: Any) -> str:
        return self.text


@pytest.fixture
async def service() -> AsyncIterator[Callable[[str], ContentService]]:
    """A real ``ContentService`` whose HTTP client serves a given body.

    The cache is bypassed so every ``get_document`` runs a fetch route.
    """
    services: list[ContentService] = []

    def _make(text: str) -> ContentService:
        client: Any = _HTTPClient(text)
        instance = ContentService(http_client=client)

        async def _miss(*_: Any, **__: Any) -> None:
            return None

        async def _no_store(*_: Any, **__: Any) -> bool:
            return False

        instance._cache_get_with_boundary = _miss  # type: ignore[method-assign]
        instance._cache_set_with_boundary = _no_store  # type: ignore[method-assign]
        services.append(instance)
        return instance

    yield _make
    for instance in services:
        await instance.close()


@pytest.fixture
def served(
    monkeypatch: pytest.MonkeyPatch,
    service: Callable[[str], ContentService],
) -> Callable[[str], None]:
    """Install a body behind ``get_risk``: one listed risk, served raw."""

    def _file(filename: str) -> GitHubFileInfo:
        return GitHubFileInfo(filename=filename)

    class _Discovery:
        async def discover_content(self) -> DiscoveryResult:
            return DiscoveryResult(
                mitigation_files=[],
                risk_files=[_file(RISK_FILE)],
                framework_files=[],
                source="github_api",
            )

    async def _discovery(_self: object) -> _Discovery:
        return _Discovery()

    monkeypatch.setattr(
        DiscoveryServiceManager, "get_discovery_service", _discovery, raising=True
    )

    def _install(body: str) -> None:
        instance = service(_document(body))

        async def _get_service() -> ContentService:
            return instance

        for dotted in _GET_SERVICE_BINDERS:
            monkeypatch.setattr(
                importlib.import_module(dotted), "get_service", _get_service
            )

    return _install


@pytest.mark.unit
@pytest.mark.parametrize("body", PROSE)
async def test_get_risk_serves_prose_the_patterns_refused(
    served: Callable[[str], None], body: str
) -> None:
    served(body)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_risk", {"risk_id": "10_prompt-injection"}, raise_on_error=False
        )

    assert not result.is_error, result.content[0].text
    assert result.structured_content is not None
    assert body in result.structured_content["content"], (
        "the body was served but not as written"
    )


@pytest.mark.unit
async def test_the_fetch_route_serves_an_assignment_in_prose(
    service: Callable[[str], ContentService],
) -> None:
    body = 'Set config = "x" before the first run.'
    instance = service(_document(body))

    document = await instance.get_document("risk", RISK_FILE)

    assert document is not None, "the document was refused"
    assert body in document["content"]
