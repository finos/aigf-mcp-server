# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""A base URL the fetch client would refuse is refused at startup (#298).

``validate_base_url`` accepted any ``http`` or ``https`` URL with a host, and
the client refuses ``http``, ``localhost`` and a non-public address literal
before every request, so ``http://mirror.example.com/docs`` or
``https://10.0.0.5/docs`` started a server on which every fetch failed with
a WARNING saying the host "does not answer". A query or a fragment started
too, and ``docs?sig=abc/index.md`` was requested.

The startup check is the client's own: ``why_not_a_fetch_target`` is what
``is_allowed_fetch_target`` consults before the allowlist, so the two cannot
drift apart. A mirror on a private address is not supported; the documents
say so.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from finos_mcp.config import Settings
from finos_mcp.content.fetch import HTTPClient
from finos_mcp.security.content_filter import is_allowed_fetch_target
from finos_mcp.security.repo_target import why_not_a_fetch_target

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("base_url", "reason"),
    [
        ("http://mirror.example.com/docs", "https"),
        ("https://10.0.0.5/docs", "public address"),
        ("https://localhost/docs", "localhost"),
        ("https://[fd00::1]/docs", "public address"),
        ("https://mirror.example.com/docs?sig=abc", "query"),
        ("https://mirror.example.com/docs#top", "fragment"),
        ("not-a-url", "https"),
    ],
)
def test_a_base_url_the_client_refuses_is_refused_at_startup(
    base_url: str, reason: str
) -> None:
    with pytest.raises(ValidationError) as refused:
        Settings(base_url=base_url)
    message = str(refused.value)
    assert "base_url" in message.lower(), message
    assert reason in message, f"the refusal does not say why: {message}"


@pytest.mark.parametrize(
    "base_url",
    [
        "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs",
        "https://raw.githubusercontent.com/a-fork/ai-governance-framework/v2/docs",
        "https://ghe.example.com/raw/org/repo/main/docs",
        "https://Mirror.Example.COM/Docs/",
        "https://93.184.216.34/docs",
        "https://mirror.example.com:8443/docs",
    ],
)
async def test_a_base_url_that_starts_is_one_the_client_requests(
    base_url: str,
) -> None:
    """Every URL startup accepts passes the check the client applies to each request."""
    settings = Settings(base_url=base_url)
    client = HTTPClient(settings=settings)
    try:
        client._refuse_unsafe_target(f"{settings.base_url}/_risks/ri-1_x.md")
    finally:
        await client.close()


def test_the_client_consults_the_same_check_before_its_allowlist() -> None:
    """An allowlisted host does not get past what ``why_not_a_fetch_target`` refuses."""
    url = "https://localhost/docs/index.md"
    assert why_not_a_fetch_target(url) is not None
    assert not is_allowed_fetch_target(url, frozenset({"localhost"}))
