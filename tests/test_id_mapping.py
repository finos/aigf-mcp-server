"""Identifiers from list_* and search_frameworks must work with get_*.

The round-trip is what makes the toolset usable: a caller lists or searches, takes
an id from the answer, and asks for that document. If the two sides disagree about
what an id looks like, every workflow built on these tools breaks at step two --
and "list, choose, then fetch" is the workflow an assistant performs.

This file used to describe exactly that property in 167 lines of prints, with zero
assertions and six ``return True``/``return False`` statements. It even printed
``✗ FAILED: ...`` on a mismatch and then returned, which pytest treats as a pass.
While it sat there reporting success, the risk search that existed then was
returning ``risk-19_data-quality-and-drift`` and ``get_risk`` was answering
``Risk risk-19_data-quality-and-drift not found``.

Content bodies come from raw.githubusercontent.com, so the get_* half needs
network. It skips when a body cannot be fetched, rather than failing for the wrong
reason; the non-skippable end-to-end coverage is
tests/integration/test_live_mcp_server.py, the functional gate.

Since #216 a get_* tool raises when a body cannot be fetched, where it used to
return a record saying so, and this file went on reading the record: without
network every test here failed (#245). ``call`` now reads the exceptions. The
tests at the end of the file stub the backend and check each decision ``call``
and ``get_by_id`` make, so they run without network.
"""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from finos_mcp.content.discovery import (
    DiscoveryResult,
    DiscoveryServiceManager,
    GitHubFileInfo,
)
from finos_mcp.exceptions import (
    DocumentUnavailableError,
    GitHubRateLimitError,
    SearchFailedError,
    UnknownDocumentError,
)
from finos_mcp.fastmcp_server import mcp
from tests.helpers import a_skip_is_a_failure


async def call(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a tool, skipping when this environment cannot reach the documents.

    Three errors say that and nothing about identifiers: GitHub's request
    budget is spent, a body could not be loaded, and a search in which no
    framework could be read. Every other error is raised, a document that is
    empty or too large among them.

    A body that "could not be loaded" is also what a get_* tool raises for an
    exception nobody planned for, so a tool broken in that way skips here
    instead of failing. tests/unit/test_unservable_document.py and the
    functional gate are where that fails.
    """
    tool = await mcp.get_tool(name)
    assert tool is not None, f"tool {name!r} is not registered"
    try:
        result = await tool.run(arguments or {})
    except GitHubRateLimitError as error:
        pytest.skip(f"GitHub's request budget is spent: {error}")
    except DocumentUnavailableError as error:
        if not error.message.endswith(DocumentUnavailableError.NOT_LOADED):
            raise
        pytest.skip(f"cannot fetch document bodies here: {error}")
    except SearchFailedError as error:
        if error.message != SearchFailedError.NOTHING_READ:
            raise
        pytest.skip(f"cannot fetch document bodies here: {error}")
    payload = result.structured_content
    assert isinstance(payload, dict), (
        f"{name} returned {type(payload).__name__}, not a structured payload"
    )
    return payload


async def get_by_id(
    get_tool: str, id_argument: str, document_id: str, source_tool: str
) -> dict[str, Any]:
    """Fetch the document ``source_tool`` named, and assert a body came back.

    An id the get_* tool does not know is the defect this module exists to
    catch: the two tools disagree about what an id looks like.
    """
    try:
        payload = await call(get_tool, {id_argument: document_id})
    except UnknownDocumentError as error:
        pytest.fail(
            f"the id {document_id!r} came from {source_tool}, but {get_tool} "
            f"reports it does not exist -- the two disagree about identifier "
            f"format. {error}"
        )
    body = payload.get("content") or ""
    assert len(body) > 100, (
        f"{document_id!r} returned only {len(body)} characters of content"
    )
    return payload


@pytest.mark.integration
@pytest.mark.parametrize(
    ("list_tool", "collection_key", "get_tool", "id_argument"),
    [
        ("list_risks", "documents", "get_risk", "risk_id"),
        ("list_mitigations", "documents", "get_mitigation", "mitigation_id"),
        ("list_frameworks", "frameworks", "get_framework", "framework_id"),
    ],
)
async def test_ids_from_list_work_with_get(
    list_tool: str, collection_key: str, get_tool: str, id_argument: str
) -> None:
    """Every id a catalog returns must be accepted by its get_* tool."""
    listing = await call(list_tool)
    entries = listing[collection_key]
    assert entries, f"{list_tool} returned nothing to round-trip"

    document_id = entries[0]["id"]
    payload = await get_by_id(get_tool, id_argument, document_id, list_tool)

    echoed = payload.get("document_id") or payload.get("framework_id")
    assert echoed == document_id, (
        f"{get_tool} echoed {echoed!r} for the id {document_id!r} that "
        f"{list_tool} supplied"
    )


@pytest.mark.integration
async def test_ids_from_search_work_with_get() -> None:
    """An id straight out of search must be usable, with no string surgery.

    The risk and mitigation searches used to prefix the id with the document
    type, so this assertion failed with "not found" while the old print-based
    version of this file reported success.
    """
    search_tool, get_tool, id_argument = (
        "search_frameworks",
        "get_framework",
        "framework_id",
    )
    found = await call(search_tool, {"query": "data", "limit": 3})
    results = found["results"]
    if not results:
        pytest.skip(f"{search_tool} found nothing for 'data'; nothing to round-trip")

    document_id = results[0]["document_id"]
    await get_by_id(get_tool, id_argument, document_id, search_tool)


@pytest.mark.integration
async def test_search_reports_only_ids_the_catalog_knows() -> None:
    """Ids that search reports must exist in the catalog.

    Catches the two sides drifting apart in either direction: a search that
    synthesises ids, or a catalog that renames them, leaves every search result
    unusable. Stronger than the round-trip above, which only samples the top hit.
    """
    list_tool, search_tool = "list_frameworks", "search_frameworks"
    listing = await call(list_tool)
    catalog_ids = {entry["id"] for entry in listing["frameworks"]}
    assert catalog_ids, f"{list_tool} returned nothing to compare against"

    found = await call(search_tool, {"query": "data", "limit": 5})
    if not found["results"]:
        pytest.skip(f"{search_tool} found nothing for 'data'")

    reported = {result["document_id"] for result in found["results"]}
    unknown = reported - catalog_ids
    assert not unknown, (
        f"{search_tool} reported ids absent from {list_tool}: {sorted(unknown)}"
    )


# What the helpers above decide, measured against a stubbed backend.

#: Modules that look ``get_service`` up in their own namespace.
_GET_SERVICE_BINDERS = ("finos_mcp.documents.tools", "finos_mcp.documents.format")

ROUND_TRIPS = [
    ("list_risks", "documents", "get_risk", "risk_id"),
    ("list_mitigations", "documents", "get_mitigation", "mitigation_id"),
    ("list_frameworks", "frameworks", "get_framework", "framework_id"),
]


def _file(filename: str) -> GitHubFileInfo:
    return GitHubFileInfo(filename=filename)


class _Discovery:
    async def discover_content(self) -> DiscoveryResult:
        return DiscoveryResult(
            mitigation_files=[_file("mi-4_ai-firewall.md")],
            risk_files=[_file("ri-10_prompt-injection.md")],
            framework_files=[_file("eu-ai-act.yml")],
            source="github_api",
        )


def _fetch_returns_nothing(_doc_type: str, _filename: str) -> None:
    """What the content service answers when it has no route to GitHub."""
    return None


def _budget_is_spent(_doc_type: str, _filename: str) -> None:
    raise GitHubRateLimitError("0 of 60 requests left")


def _body_is_empty(_doc_type: str, _filename: str) -> dict[str, object]:
    return {"content": "   \n", "metadata": {"title": "A Title"}}


def _body_is_a_stub(_doc_type: str, _filename: str) -> dict[str, object]:
    """Served, and too short to be a document. Valid as Markdown and as YAML."""
    return {"content": "title: A Title\n", "metadata": {"title": "A Title"}}


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> Callable[[Callable[..., object]], None]:
    """Stub discovery to list one of each kind; install a ``get_document``."""

    async def _discovery(_self: object) -> _Discovery:
        return _Discovery()

    monkeypatch.setattr(
        DiscoveryServiceManager, "get_discovery_service", _discovery, raising=True
    )

    def _install(get_document: Callable[..., object]) -> None:
        class _Service:
            async def get_document(self, doc_type: str, filename: str) -> object:
                return get_document(doc_type, filename)

        async def _get_service() -> _Service:
            return _Service()

        for dotted in _GET_SERVICE_BINDERS:
            monkeypatch.setattr(
                importlib.import_module(dotted),
                "get_service",
                _get_service,
                raising=True,
            )

    return _install


@pytest.mark.unit
@pytest.mark.parametrize(
    ("get_document", "reason"),
    [
        pytest.param(
            _fetch_returns_nothing, "cannot fetch document bodies", id="no-route"
        ),
        pytest.param(_budget_is_spent, "request budget is spent", id="budget-spent"),
    ],
)
@pytest.mark.parametrize(
    ("list_tool", "collection_key", "get_tool", "id_argument"), ROUND_TRIPS
)
async def test_a_round_trip_skips_when_no_body_can_be_fetched(
    backend: Callable[..., None],
    get_document: Callable[..., object],
    reason: str,
    list_tool: str,
    collection_key: str,
    get_tool: str,
    id_argument: str,
) -> None:
    backend(get_document)

    with pytest.raises(pytest.skip.Exception, match=reason):
        await test_ids_from_list_work_with_get(
            list_tool, collection_key, get_tool, id_argument
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "search_test",
    [
        test_ids_from_search_work_with_get,
        test_search_reports_only_ids_the_catalog_knows,
    ],
)
async def test_a_search_test_skips_when_no_framework_can_be_read(
    backend: Callable[..., None], search_test: Callable[[], Awaitable[object]]
) -> None:
    backend(_fetch_returns_nothing)

    with pytest.raises(pytest.skip.Exception, match="cannot fetch document bodies"):
        await search_test()


@pytest.mark.unit
async def test_a_search_that_broke_is_not_skipped(
    backend: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only "nothing could be read" is this environment; the rest is a defect."""
    backend(_fetch_returns_nothing)

    async def _broken() -> None:
        raise RuntimeError("not a network failure")

    monkeypatch.setattr(
        importlib.import_module("finos_mcp.search.tools"), "list_frameworks", _broken
    )

    with pytest.raises(SearchFailedError, match="failed before it finished"):
        with a_skip_is_a_failure():
            await test_ids_from_search_work_with_get()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("list_tool", "collection_key", "get_tool", "id_argument"), ROUND_TRIPS
)
async def test_an_unservable_document_is_not_skipped(
    backend: Callable[..., None],
    list_tool: str,
    collection_key: str,
    get_tool: str,
    id_argument: str,
) -> None:
    """An empty document is reachable and wrong, which no retry will change."""
    backend(_body_is_empty)

    with pytest.raises(DocumentUnavailableError, match="has no content"):
        with a_skip_is_a_failure():
            await test_ids_from_list_work_with_get(
                list_tool, collection_key, get_tool, id_argument
            )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("list_tool", "_collection_key", "get_tool", "id_argument"), ROUND_TRIPS
)
async def test_an_id_the_get_tool_rejects_fails_the_round_trip(
    backend: Callable[..., None],
    list_tool: str,
    _collection_key: str,
    get_tool: str,
    id_argument: str,
) -> None:
    backend(_fetch_returns_nothing)

    # Anchored: the helper above repeats a skip's reason in its own message.
    with pytest.raises(pytest.fail.Exception, match=r"^the id 'an-id-no-document-has'"):
        with a_skip_is_a_failure():
            await get_by_id(get_tool, id_argument, "an-id-no-document-has", list_tool)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("list_tool", "collection_key", "get_tool", "id_argument"), ROUND_TRIPS
)
async def test_a_body_too_short_to_be_a_document_fails_the_round_trip(
    backend: Callable[..., None],
    list_tool: str,
    collection_key: str,
    get_tool: str,
    id_argument: str,
) -> None:
    backend(_body_is_a_stub)

    with pytest.raises(AssertionError, match="characters of content"):
        with a_skip_is_a_failure():
            await test_ids_from_list_work_with_get(
                list_tool, collection_key, get_tool, id_argument
            )
