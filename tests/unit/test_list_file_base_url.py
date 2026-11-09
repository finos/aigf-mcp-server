"""The discovery list file belongs to the ``base_url`` it was written for.

The list file recorded file names, SHAs and an expiry time, and nothing
about which repository it listed. After ``FINOS_MCP_BASE_URL`` changed,
a file that had not expired was served as it was: the list tools named the
previous repository's documents for up to an hour, while document bodies were
fetched from the new one. For a mirror host, which has no listing API, the
server said at startup that discovery uses the static lists and then served
the previous repository's listing instead.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from finos_mcp.content.discovery import (
    DiscoveryResult,
    GitHubDiscoveryService,
    GitHubFileInfo,
)
from finos_mcp.content.list_file import ListFile
from finos_mcp.security.repo_target import resolve_repo_target

pytestmark = pytest.mark.unit

_UPSTREAM = "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs"
_FORK = "https://raw.githubusercontent.com/someone/fork/main/docs"
_MIRROR = "https://mirror.example.com/docs"

_LISTED_NAME = "ri-777_only-in-the-previous-repository.md"
_LISTED = {
    "type": "file",
    "name": _LISTED_NAME,
    "path": f"docs/_risks/{_LISTED_NAME}",
    "sha": "abc123",
    "size": 10,
    "download_url": f"{_UPSTREAM}/_risks/{_LISTED_NAME}",
}


class RecordingClient:
    """HTTPClient stand-in whose risk directory holds ``_LISTED``, and only it.

    Built ``failing``, every request is answered 500.
    """

    def __init__(self, *, failing: bool = False) -> None:
        self.calls: list[str] = []
        self.failing = failing

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append(url)
        # Suspend once, as the real client does on the network, so the three
        # listings are in flight together and a refusal of one stops no other.
        await asyncio.sleep(0)
        if self.failing:
            body: Any = {"message": "Server Error"}
        else:
            # Each directory holds one name: listed empty, it would be a
            # failed listing (#317).
            body = (
                [_LISTED]
                if "/_risks?" in url
                else [
                    {"type": "file", "name": "mi-1_elsewhere.md"},
                    {"type": "file", "name": "elsewhere.yml"},
                ]
            )
        return httpx.Response(
            status_code=500 if self.failing else 200,
            content=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            request=httpx.Request("GET", url),
        )


async def _awaitable(value: Any) -> Any:
    return value


def _service(base_url: str, directory: Path) -> GitHubDiscoveryService:
    service = GitHubDiscoveryService()
    service.repo_target = resolve_repo_target(base_url)
    service.list_file = ListFile(
        directory, service.repo_target, service.cache_duration_seconds
    )
    return service


def _list_file_path(directory: Path) -> Path:
    path = _service(_UPSTREAM, directory).list_file.path
    assert path is not None
    return path


def _write_list_file(directory: Path, *, expired: bool) -> None:
    """Write the list file the way a server configured for upstream writes it.

    ``expired`` moves the written expiry an hour into the past.
    """
    entry = GitHubFileInfo(filename=_LISTED_NAME)
    service = _service(_UPSTREAM, directory)
    service.list_file.write(
        DiscoveryResult(
            mitigation_files=[],
            risk_files=[entry],
            framework_files=[],
            source="github_api",
        )
    )
    if expired:
        path = service.list_file.path
        assert path is not None
        data = json.loads(path.read_text(encoding="utf-8"))
        data["cache_expires"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        path.write_text(json.dumps(data), encoding="utf-8")


def _use(monkeypatch: pytest.MonkeyPatch, client: RecordingClient) -> None:
    monkeypatch.setattr(
        "finos_mcp.content.discovery.get_http_client",
        lambda *a, **k: _awaitable(client),
    )


def _risk_names(result: DiscoveryResult) -> list[str]:
    return [f.filename for f in result.risk_files]


@pytest.mark.parametrize("expired", [False, True], ids=["fresh", "expired"])
async def test_the_same_base_url_reads_its_own_list_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, expired: bool
) -> None:
    """Positive control: tying the file to a base_url must not disable it.

    A fresh file is served as it is. An expired one is served when GitHub
    cannot be asked (#260), which is the case where reading it matters.
    """
    _write_list_file(tmp_path, expired=expired)
    client = RecordingClient(failing=expired)
    _use(monkeypatch, client)

    result = await _service(_UPSTREAM, tmp_path).discover_content()

    assert result.source == ("expired_cache" if expired else "cache")
    assert _risk_names(result) == [_LISTED_NAME]
    # A fresh file needs no request; an expired one is listed again, once.
    assert len(client.calls) == (3 if expired else 0)


@pytest.mark.parametrize("expired", [False, True], ids=["fresh", "expired"])
async def test_a_fork_does_not_read_the_list_file_of_the_previous_base_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, expired: bool
) -> None:
    _write_list_file(tmp_path, expired=expired)
    # The fork answers with the same entry, so only the source and the URLs
    # asked tell a listing of the fork from the previous repository's file.
    client = RecordingClient()
    _use(monkeypatch, client)

    result = await _service(_FORK, tmp_path).discover_content()

    assert result.source == "github_api", (
        "the listing must come from the configured repository, not from a file "
        "written for another one"
    )
    assert len(client.calls) == 3, "one listing of the three directories"
    assert all("/repos/someone/fork/" in url for url in client.calls)


@pytest.mark.parametrize("expired", [False, True], ids=["fresh", "expired"])
async def test_a_mirror_does_not_read_the_list_file_of_the_previous_base_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, expired: bool
) -> None:
    _write_list_file(tmp_path, expired=expired)
    client = RecordingClient()
    _use(monkeypatch, client)

    result = await _service(_MIRROR, tmp_path).discover_content()

    assert result.source == "static_fallback"
    assert _LISTED_NAME not in _risk_names(result)
    assert client.calls == []


def _remove_base_url(directory: Path) -> Path:
    """Make the list file the one a server before #249 wrote; return its path."""
    list_file = _list_file_path(directory)
    data = json.loads(list_file.read_text(encoding="utf-8"))
    del data["base_url"]
    list_file.write_text(json.dumps(data), encoding="utf-8")
    return list_file


@pytest.mark.parametrize("expired", [False, True], ids=["fresh", "expired"])
async def test_a_list_file_written_before_the_base_url_was_recorded_is_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, expired: bool
) -> None:
    """An upgrade must not throw away the listing the server already has.

    Every list file written before #249 names no base_url. Ignoring them made
    the first start after the upgrade list the repository again, and a server
    with a spent rate limit served the static catalog instead (#261).
    """
    _write_list_file(tmp_path, expired=expired)
    _remove_base_url(tmp_path)
    client = RecordingClient(failing=expired)
    _use(monkeypatch, client)

    result = await _service(_UPSTREAM, tmp_path).discover_content()

    assert result.source == ("expired_cache" if expired else "cache")
    assert _risk_names(result) == [_LISTED_NAME]
    assert len(client.calls) == (3 if expired else 0)


@pytest.mark.parametrize("expired", [False, True], ids=["fresh", "expired"])
async def test_a_mirror_does_not_read_a_list_file_that_names_no_base_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, expired: bool
) -> None:
    """A mirror never writes a list file, so one found there lists GitHub."""
    _write_list_file(tmp_path, expired=expired)
    _remove_base_url(tmp_path)
    client = RecordingClient()
    _use(monkeypatch, client)

    result = await _service(_MIRROR, tmp_path).discover_content()

    assert result.source == "static_fallback"
    assert _LISTED_NAME not in _risk_names(result)
    assert client.calls == []


async def test_a_list_file_that_is_not_a_mapping_is_not_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Reading a file with no base_url must not read a file with no keys at all."""
    _list_file_path(tmp_path).write_text("[]", encoding="utf-8")
    client = RecordingClient()
    _use(monkeypatch, client)

    result = await _service(_UPSTREAM, tmp_path).discover_content()

    assert result.source == "github_api"
    assert len(client.calls) == 3
