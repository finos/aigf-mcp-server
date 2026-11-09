# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""A document that exists and cannot be served is an error on every surface (#216).

#193 made an unknown id an error. The other failure branches of ``get_risk``,
``get_mitigation`` and ``get_framework`` still returned an ordinary result
(``isError: false``): a record titled "Error loading risk <id>" or
"Risk <id> content unavailable", with a sentence written by this server in the
field a caller reads as the document. The ``finos://`` resources served that
sentence as a ``text/markdown`` body, and the framework search had to read
titles to tell such a record from a document.

Four branches, decided on 2026-10-08 to raise in every one:

- the fetch returns nothing;
- the tool body raises something unexpected;
- the body is over the size limit;
- the body is empty.

Every test goes through a client session against the assembled server, as
``test_unknown_identifier.py`` does and for the same reason: the defect is in
what a client receives.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable

import pytest
from fastmcp import Client
from mcp.shared.exceptions import MCPError
from mcp.types import INTERNAL_ERROR

from finos_mcp.content.discovery import (
    DiscoveryResult,
    DiscoveryServiceManager,
    GitHubFileInfo,
)
from finos_mcp.exceptions import GitHubRateLimitError, SearchFailedError
from finos_mcp.fastmcp_server import mcp
from finos_mcp.search import engine, ranking
from finos_mcp.security.request_validator import request_size_validator

#: Modules that look ``get_service`` up in their own namespace.
_GET_SERVICE_BINDERS = (
    "finos_mcp.documents.tools",
    "finos_mcp.documents.format",
    "finos_mcp.health_tools",
)

#: Text only the stubbed backend holds. A client must never be shown it: an
#: unexpected exception's own words are not written for a client.
BACKEND_DETAIL = "backend-detail-3f9a17"

#: What a document's own title would be, had it been served.
REAL_TITLE = "Sentinel Title Only The Document Has"


def _file(filename: str) -> GitHubFileInfo:
    return GitHubFileInfo(filename=filename)


class _Discovery:
    async def discover_content(self) -> DiscoveryResult:
        return DiscoveryResult(
            mitigation_files=[_file("mi-4_ai-firewall.md")],
            risk_files=[_file("ri-10_prompt-injection.md")],
            framework_files=[_file("eu-ai-act.yml"), _file("nist-ai-rmf.yml")],
            source="github_api",
        )


def _fetch_returns_nothing(_doc_type: str, _filename: str) -> None:
    return None


def _fetch_raises(_doc_type: str, _filename: str) -> None:
    raise RuntimeError(f"connection reset by {BACKEND_DETAIL}")


def _body_is_oversized(doc_type: str, _filename: str) -> dict[str, object]:
    limit = request_size_validator.max_resource_size
    if doc_type == "framework":
        # One long scalar, so the rendered document is over the limit too.
        return {"content": f"title: {REAL_TITLE}\ndescription: {'x' * (limit + 1)}\n"}
    return {"content": "x" * (limit + 1), "metadata": {"title": REAL_TITLE}}


def _body_is_empty(_doc_type: str, _filename: str) -> dict[str, object]:
    return {"content": "   \n", "metadata": {"title": REAL_TITLE}}


#: A phrase one of the two readable frameworks below says.
READABLE_PHRASE = "transparency obligations"


def _body_is_readable(_doc_type: str, filename: str) -> dict[str, object]:
    if filename == "nist-ai-rmf.yml":
        return {
            "content": f"title: NIST AI RMF\ndescription: Covers {READABLE_PHRASE}.\n"
        }
    return {"content": "title: EU AI Act\ndescription: Says something else.\n"}


#: branch, how the backend behaves, and what the message must say happened.
BRANCHES = [
    pytest.param(
        _fetch_returns_nothing, "could not be loaded", id="fetch-returns-nothing"
    ),
    pytest.param(_fetch_raises, "could not be loaded", id="unexpected-exception"),
    pytest.param(_body_is_oversized, "too large", id="oversized"),
    pytest.param(_body_is_empty, "no content", id="empty"),
]

#: tool, its parameter, an id the stubbed discovery lists, its resource URI.
SURFACES = [
    ("get_risk", "risk_id", "10_prompt-injection", "finos://risks/10_prompt-injection"),
    (
        "get_mitigation",
        "mitigation_id",
        "4_ai-firewall",
        "finos://mitigations/4_ai-firewall",
    ),
    ("get_framework", "framework_id", "eu-ai-act", "finos://frameworks/eu-ai-act"),
]


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
@pytest.mark.parametrize(("get_document", "says"), BRANCHES)
@pytest.mark.parametrize(("tool", "parameter", "doc_id", "_uri"), SURFACES)
async def test_a_get_tool_reports_an_unservable_document_as_an_error(
    backend: Callable[..., None],
    get_document: Callable[..., object],
    says: str,
    tool: str,
    parameter: str,
    doc_id: str,
    _uri: str,
) -> None:
    backend(get_document)

    async with Client(mcp) as client:
        result = await client.call_tool(tool, {parameter: doc_id}, raise_on_error=False)

    assert result.is_error, f"{tool} answered an unservable document as a success"
    assert result.structured_content is None, (
        f"{tool} sent a document record alongside the error"
    )
    message = result.content[0].text
    # Names the document and what happened to it, so a caller can tell
    # "retry" from "this document cannot be served".
    assert f"'{doc_id}'" in message
    assert says in message
    assert BACKEND_DETAIL not in message
    assert REAL_TITLE not in message


@pytest.mark.unit
@pytest.mark.parametrize(("get_document", "says"), BRANCHES)
@pytest.mark.parametrize(("_tool", "_parameter", "doc_id", "uri"), SURFACES)
async def test_a_resource_read_for_an_unservable_document_fails(
    backend: Callable[..., None],
    get_document: Callable[..., object],
    says: str,
    _tool: str,
    _parameter: str,
    doc_id: str,
    uri: str,
) -> None:
    """The body of a resource is the document, so there is nowhere to say "no"."""
    backend(get_document)

    async with Client(mcp) as client:
        with pytest.raises(MCPError) as refusal:
            await client.read_resource(uri)

    # Not INVALID_PARAMS, which is what an id no document has gets (#193):
    # this request was right and the server could not answer it.
    assert refusal.value.error.code == INTERNAL_ERROR
    message = str(refusal.value)
    assert f"'{doc_id}'" in message
    assert says in message
    assert BACKEND_DETAIL not in message
    # The sentence this server wrote for a client, not one put through the
    # sanitiser meant for exceptions nobody planned for.
    assert "Request ID" not in message


@pytest.mark.unit
@pytest.mark.parametrize(("_tool", "_parameter", "doc_id", "uri"), SURFACES)
async def test_a_resource_read_during_a_github_throttle_fails_with_the_explanation(
    backend: Callable[..., None], _tool: str, _parameter: str, doc_id: str, uri: str
) -> None:
    """The tools already raised for a throttle; the resources served it as a body."""

    def _throttled(_doc_type: str, _filename: str) -> None:
        raise GitHubRateLimitError("Resets in 60 seconds.")

    backend(_throttled)

    async with Client(mcp) as client:
        with pytest.raises(MCPError) as refusal:
            await client.read_resource(uri)

    assert refusal.value.error.code == INTERNAL_ERROR
    message = str(refusal.value)
    assert f"'{doc_id}'" in message
    assert "temporary throttle" in message
    assert "Request ID" not in message


@pytest.mark.unit
async def test_a_resource_does_not_pass_on_an_exception_nobody_planned_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whatever reaches a resource that the tool did not turn into its own error."""
    from finos_mcp import resources

    async def _broken(_risk_id: str) -> None:
        raise RuntimeError("cannot read /srv/finos/content/cache.py at line 3")

    monkeypatch.setattr(resources, "get_risk", _broken, raising=True)

    async with Client(mcp) as client:
        with pytest.raises(MCPError) as refusal:
            await client.read_resource("finos://risks/10_prompt-injection")

    assert refusal.value.error.code == INTERNAL_ERROR
    assert "/srv/finos" not in str(refusal.value)


@pytest.mark.unit
@pytest.mark.parametrize(("get_document", "says"), BRANCHES)
async def test_the_compliance_prompt_refuses_a_framework_it_could_not_read(
    backend: Callable[..., None], get_document: Callable[..., object], says: str
) -> None:
    """It used to embed "Failed to load content ..." as the framework to analyse."""
    backend(get_document)

    async with Client(mcp) as client:
        with pytest.raises(MCPError) as refusal:
            await client.get_prompt(
                "analyze_framework_compliance",
                {"framework": "eu-ai-act", "use_case": "a customer service chatbot"},
            )

    message = str(refusal.value)
    assert "'eu-ai-act'" in message
    assert says in message
    assert BACKEND_DETAIL not in message


@pytest.mark.unit
@pytest.mark.parametrize(("get_document", "_says"), BRANCHES)
async def test_a_search_skips_a_framework_it_could_not_read(
    backend: Callable[..., None], get_document: Callable[..., object], _says: str
) -> None:
    """One unreadable framework does not cost the search the others.

    Decided with #216: skipped and logged, as before. What changed is how the
    search knows: ``get_framework`` raises, where the search used to read the
    title of a record to find out it was not a document.
    """
    phrase = "transparency obligations"

    def _one_good_one_bad(doc_type: str, filename: str) -> object:
        if filename == "nist-ai-rmf.yml":
            return {"content": f"title: NIST AI RMF\ndescription: Covers {phrase}.\n"}
        return get_document(doc_type, filename)

    backend(_one_good_one_bad)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_frameworks", {"query": phrase}, raise_on_error=False
        )

    assert not result.is_error, result.content[0].text
    found = [hit["document_id"] for hit in result.structured_content["results"]]
    assert found == ["nist-ai-rmf"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "words",
    [
        "could not be loaded",
        "too large",
        "no content",
        "Error loading framework",
        "content unavailable",
    ],
)
async def test_a_search_cannot_match_words_this_server_would_use_for_a_failure(
    backend: Callable[..., None], words: str
) -> None:
    """A failure used to arrive as a body, so its own sentence was searchable.

    One framework is readable, so the search runs: with none it is an error
    (#224), and an error would pass this for the wrong reason.
    """

    def _one_good_one_bad(_doc_type: str, filename: str) -> object:
        if filename == "nist-ai-rmf.yml":
            return {"content": "title: NIST AI RMF\ndescription: Says none of it.\n"}
        return None

    backend(_one_good_one_bad)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_frameworks", {"query": words}, raise_on_error=False
        )

    assert not result.is_error, result.content[0].text
    assert result.structured_content == {
        "query": words,
        "results": [],
        "total_found": 0,
    }


# A search that did not run is an error, not "0 results" (#224).
#
# ``search_frameworks`` ended in a catch-all that answered any unexpected
# exception with an empty, successful result, and a search in which every
# framework was skipped answered the same. A client reads ``total_found: 0`` as
# "no framework says this". Decided on 2026-10-08: both are tool
# errors, and the per-framework skip covers an unservable document only.


@pytest.mark.unit
@pytest.mark.parametrize(("get_document", "_says"), BRANCHES)
async def test_a_search_that_could_read_no_framework_is_an_error(
    backend: Callable[..., None], get_document: Callable[..., object], _says: str
) -> None:
    """Every framework skipped means nothing was searched."""
    backend(get_document)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_frameworks", {"query": "risk"}, raise_on_error=False
        )

    assert result.is_error, result.structured_content
    assert result.structured_content is None
    text = result.content[0].text
    assert text == (
        f"Error calling tool 'search_frameworks': {SearchFailedError.NOTHING_READ}"
    )
    assert BACKEND_DETAIL not in text


@pytest.mark.unit
async def test_a_search_whose_listing_fails_is_an_error(
    backend: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reproduction in #224: the listing the search starts from raises."""
    backend(_body_is_readable)

    async def _listing_raises() -> None:
        raise RuntimeError(f"listing broke: {BACKEND_DETAIL}")

    monkeypatch.setattr(
        "finos_mcp.search.tools.list_frameworks", _listing_raises, raising=True
    )

    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_frameworks", {"query": READABLE_PHRASE}, raise_on_error=False
        )

    assert result.is_error, result.structured_content
    assert result.structured_content is None
    text = result.content[0].text
    assert text == (
        f"Error calling tool 'search_frameworks': {SearchFailedError.UNEXPECTED}"
    )
    assert BACKEND_DETAIL not in text


@pytest.mark.unit
async def test_a_search_does_not_skip_a_framework_its_own_matching_broke_on(
    backend: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A skip is for a document that cannot be served, not for a bug here.

    Both frameworks are readable and one says the phrase. The matcher raises
    on the other, which used to be logged and skipped: the answer was one
    result, with nothing to say a framework had gone unsearched.
    """
    backend(_body_is_readable)
    real_find_phrase = ranking._find_phrase

    def _breaks_on_one(query: str, text: str) -> object:
        if "EU AI Act" in text:
            raise RuntimeError(f"matcher broke: {BACKEND_DETAIL}")
        return real_find_phrase(query, text)

    monkeypatch.setattr(engine, "_find_phrase", _breaks_on_one, raising=True)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_frameworks", {"query": READABLE_PHRASE}, raise_on_error=False
        )

    assert result.is_error, result.structured_content
    text = result.content[0].text
    assert text == (
        f"Error calling tool 'search_frameworks': {SearchFailedError.UNEXPECTED}"
    )
    assert BACKEND_DETAIL not in text


@pytest.mark.unit
async def test_a_search_that_read_every_framework_and_found_nothing_is_not_an_error(
    backend: Callable[..., None],
) -> None:
    """The answer the errors above must not be mistaken for."""
    backend(_body_is_readable)

    async with Client(mcp) as client:
        said = await client.call_tool(
            "search_frameworks", {"query": READABLE_PHRASE}, raise_on_error=False
        )
        unsaid = await client.call_tool(
            "search_frameworks", {"query": "zeppelin"}, raise_on_error=False
        )

    assert not said.is_error, said.content[0].text
    assert [hit["document_id"] for hit in said.structured_content["results"]] == [
        "nist-ai-rmf"
    ]
    assert not unsaid.is_error, unsaid.content[0].text
    assert unsaid.structured_content == {
        "query": "zeppelin",
        "results": [],
        "total_found": 0,
    }
