# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The static-fallback update script must ask GitHub, not the disk cache.

``scripts/update-static-fallback.py`` used to call ``discover_content()``. Within
an hour of any server run that returns the listing cached on disk, labelled
``cache``, so the script printed "Using cache instead of github_api", exited 1
and wrote nothing while the API was reachable; ``test_static_fallback_sync.py``
skipped for the same reason and so reported no failure with the lists three
documents out of date (#207).

Both now read ``fetch_live_listing`` from the script. These tests hold it to the
two properties that matter, offline: a warm cache does not answer for GitHub,
and a refused request raises instead of being answered from somewhere else.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
from tenacity import retry, stop_after_attempt

from finos_mcp.config import get_settings
from finos_mcp.content.discovery import (
    GitHubDiscoveryService,
)
from finos_mcp.content.github_api import FRAMEWORKS, MITIGATIONS, RISKS
from finos_mcp.content.list_file import FILE_NAME
from finos_mcp.exceptions import GitHubDiscoveryError, GitHubRateLimitError
from tests.helpers import load_module

pytestmark = pytest.mark.unit

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "update-static-fallback.py"

_UPSTREAM = {
    MITIGATIONS.subdir: ["mi-2_second.md", "mi-1_first.md"],
    RISKS.subdir: ["ri-1_only.md"],
    FRAMEWORKS.subdir: ["new-framework.yml"],
}


def _load_script() -> ModuleType:
    return load_module(_SCRIPT, "update_static_fallback")


def _entry(name: str) -> dict[str, Any]:
    return {
        "type": "file",
        "name": name,
        "path": f"docs/{name}",
        "sha": "abc123",
        "size": 1,
        "download_url": f"https://raw.githubusercontent.com/x/y/main/{name}",
    }


class _GitHub:
    """HTTPClient stand-in that answers each directory by its URL."""

    def __init__(self, status: int = 200, error_body: Any = None) -> None:
        self._status = status
        self._error_body = error_body
        self.calls: list[str] = []

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append(url)
        request = httpx.Request("GET", url)
        if self._status != 200:
            return httpx.Response(self._status, json=self._error_body, request=request)
        directory = httpx.URL(url).path
        for subdir in _UPSTREAM:
            if directory.endswith(f"/{subdir}"):
                body = [_entry(name) for name in _UPSTREAM[subdir]]
                return httpx.Response(200, json=body, request=request)
        raise AssertionError(f"unexpected URL {url}")


def _use(monkeypatch: pytest.MonkeyPatch, script: ModuleType, client: _GitHub) -> None:
    async def _client(*args: Any, **kwargs: Any) -> _GitHub:
        return client

    monkeypatch.setattr(script, "get_http_client", _client)


async def test_a_warm_disk_cache_does_not_answer_for_github(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = tmp_path / "discovery"
    directory.mkdir()
    monkeypatch.setattr(get_settings(), "discovery_cache_dir", str(directory))
    stale = {
        "filename": "mi-0_cached-an-hour-ago.md",
        "path": "docs/_mitigations/mi-0_cached-an-hour-ago.md",
        "sha": "abc123",
        "size": 1,
        "download_url": "https://raw.githubusercontent.com/x/y/main/mi-0.md",
    }
    cache_file = directory / FILE_NAME
    cache_file.write_text(
        json.dumps(
            {
                "mitigation_files": [stale],
                "risk_files": [],
                "framework_files": [],
                "base_url": get_settings().repo_target.raw_base_url,
                "cache_expires": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    planted = cache_file.read_text(encoding="utf-8")

    # The precondition: this is the cache the service reads, and it is warm. If
    # the plant landed anywhere else the assertions below would pass against a
    # cold cache and prove nothing.
    served = await GitHubDiscoveryService().discover_content()
    assert served.source == "cache"
    assert [f.filename for f in served.mitigation_files] == [stale["filename"]]

    script = _load_script()
    client = _GitHub()
    _use(monkeypatch, script, client)

    listing = await script.fetch_live_listing()

    assert listing == {
        "mitigations": ["mi-1_first.md", "mi-2_second.md"],
        "risks": ["ri-1_only.md"],
        "frameworks": ["new-framework.yml"],
    }
    assert len(client.calls) == 3
    assert cache_file.read_text(encoding="utf-8") == planted, (
        "the script must leave the server's discovery cache as it found it"
    )


async def test_a_throttled_request_raises_instead_of_serving_the_static_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script()
    _use(
        monkeypatch,
        script,
        _GitHub(403, {"message": "API rate limit exceeded for 203.0.113.7."}),
    )

    with pytest.raises(GitHubRateLimitError, match="rate limit"):
        await script.fetch_live_listing()


async def test_a_missing_directory_is_not_reported_as_throttling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sync test skips on a rate limit and fails on anything else GitHub says.

    A 404 means upstream moved a directory, which is a finding; if it arrived as
    ``GitHubRateLimitError`` the sync test would skip it every week.
    """
    script = _load_script()
    _use(monkeypatch, script, _GitHub(404, {"message": "Not Found"}))

    with pytest.raises(GitHubDiscoveryError, match="404") as caught:
        await script.fetch_live_listing()

    assert not isinstance(caught.value, GitHubRateLimitError)


class _Unreachable:
    """Fails the way the real client does once its retries are spent."""

    @retry(stop=stop_after_attempt(1))
    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError(
            "All connection attempts failed", request=httpx.Request("GET", url)
        )


async def test_an_unreachable_api_raises_the_connection_error_not_the_retry_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measured against a dead proxy: the client raises ``tenacity.RetryError``.

    The sync test skips on a transport error. Handed the wrapper it failed
    instead, with ``RetryError[<Future ...>]`` as the whole explanation.
    """
    script = _load_script()

    async def _client(*args: Any, **kwargs: Any) -> _Unreachable:
        return _Unreachable()

    monkeypatch.setattr(script, "get_http_client", _client)

    with pytest.raises(httpx.ConnectError, match="All connection attempts failed"):
        await script.fetch_live_listing()
