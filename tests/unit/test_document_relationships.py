"""Declared relationships survive retrieval, normalization and MCP serialization."""

import asyncio
import json
from collections.abc import Mapping
from typing import Any

import pytest
from fastmcp import Client

from finos_mcp import models
from finos_mcp.documents import format as doc_format
from finos_mcp.documents import tools as doc_tools
from finos_mcp.fastmcp_server import mcp

pytestmark = pytest.mark.unit


def test_specialized_models_keep_relationships_out_of_sibling_responses() -> None:
    entry = models.MitigationInfo(
        id="1_control", name="Control", filename="mi-1_control.md", mitigates=["1_risk"]
    )
    listing = models.MitigationList(
        documents=[entry], total_count=1, document_type="mitigation", source="cache"
    )
    assert listing.model_dump()["documents"][0]["mitigates"] == ["1_risk"]
    body: dict[str, Any] = {
        "document_id": "1_doc",
        "title": "T",
        "content": "Body",
        "sections": [],
    }
    risk = models.RiskContent(
        **body, related_risks=["2_risk"], mitigated_by=["1_control"]
    )
    mitigation = models.MitigationContent(
        **body, mitigates=["1_risk"], related_mitigations=["2_control"]
    )
    assert risk.model_dump()["mitigated_by"] == ["1_control"]
    assert mitigation.model_dump()["related_mitigations"] == ["2_control"]
    assert set(models.DocumentContent.model_fields) == set(body)
    assert "mitigates" not in models.DocumentInfo.model_fields
    assert "mitigates" not in risk.model_dump()
    assert "related_risks" not in mitigation.model_dump()


def test_relationship_defaults_are_independent_empty_arrays() -> None:
    first = models.MitigationInfo(id="1", name="A", filename="mi-1_a.md")
    second = models.MitigationInfo(id="2", name="B", filename="mi-2_b.md")
    assert first.mitigates == second.mitigates == []
    assert first.mitigates is not second.mitigates
    for model in (models.RiskContent, models.MitigationContent):
        result = model(document_id="1", title="T", content="Body", sections=[])
        assert all(
            value == []
            for key, value in result.model_dump().items()
            if key not in {"document_id", "title", "content", "sections"}
        )


async def test_listing_retains_metadata_even_when_title_extraction_fails(
    monkeypatch,
) -> None:
    metadata = {"mitigates": ["ri-1"]}

    class Service:
        async def get_document(
            self, _kind: str, filename: str
        ) -> dict[str, Any] | None:
            if filename == "unread.md":
                return None
            return {"metadata": metadata if filename == "broken.md" else {}}

    async def service() -> Service:
        return Service()

    async def extract(doc: Mapping[str, Any]) -> tuple[str | None, str | None]:
        if doc["metadata"]:
            raise RuntimeError("title extraction failed")
        return "Title", None

    monkeypatch.setattr(doc_format, "get_service", service)
    results = await doc_format._resolve_titles(
        "mitigation", ["broken.md", "empty.md", "unread.md"], extract, lambda name: name
    )
    assert results[0].metadata == metadata
    assert results[0].load_error is None
    assert results[1].metadata == {}
    assert results[2].metadata is None
    assert metadata == {"mitigates": ["ri-1"]}


async def test_listing_retains_throttling_and_marks_skipped_metadata(
    monkeypatch,
) -> None:
    from finos_mcp.exceptions import GitHubRateLimitError

    calls = []
    throttle = GitHubRateLimitError("throttled", retry_after=23)

    class Service:
        async def get_document(self, _kind: str, filename: str) -> None:
            calls.append(filename)
            raise throttle

    async def service() -> Service:
        return Service()

    monkeypatch.setattr(doc_format, "get_service", service)
    results = await doc_format._resolve_document_names(
        "mitigation", ["first.md", "later.md"]
    )
    assert calls == ["first.md"]
    assert [entry.metadata for entry in results] == [None, None]
    assert results[0].load_error is throttle
    assert results[1].load_error is None


def _catalog(monkeypatch, documents, source="github_api"):
    """A recording content service and discovery snapshot; no network or cache."""
    from finos_mcp.content.discovery import (
        DiscoveryResult,
        DiscoveryServiceManager,
        GitHubFileInfo,
    )

    calls = []
    discovery = DiscoveryResult(
        risk_files=[
            GitHubFileInfo(filename=name)
            for name in documents
            if name.startswith("ri-")
        ],
        mitigation_files=[
            GitHubFileInfo(filename=name)
            for name in documents
            if name.startswith("mi-")
        ],
        framework_files=[],
        source=source,
    )

    class Discovery:
        async def discover_content(self):
            return discovery

    class Service:
        async def get_document(self, kind, filename):
            calls.append((kind, filename))
            value = documents[filename]
            if isinstance(value, BaseException):
                raise value
            return value

    async def service():
        return Service()

    async def discover(_self):
        return Discovery()

    monkeypatch.setattr(doc_tools, "get_service", service)
    monkeypatch.setattr(doc_format, "get_service", service)
    monkeypatch.setattr(DiscoveryServiceManager, "get_discovery_service", discover)
    return calls


def _document(metadata=None):
    return {
        "content": "## Purpose\n\nDeclared control.\n",
        "metadata": {} if metadata is None else metadata,
    }


async def test_mitigation_tools_publish_canonical_links_without_extra_listing_fetches(
    monkeypatch,
):
    documents = {
        "ri-1_risk.md": _document(),
        "ri-10_other.md": _document(),
        "mi-1_control.md": _document(
            {
                "mitigates": [" RI-1 ", "1", "ri-10", "ri-999"],
                "related_mitigations": ["CT-2", "mi-2_other", "mi-999"],
            }
        ),
        "mi-2_other.md": _document(),
    }
    calls = _catalog(monkeypatch, documents)
    listing = await doc_tools.list_mitigations()
    assert listing.model_dump()["documents"][0]["mitigates"] == ["1_risk", "10_other"]
    assert listing.documents[1].mitigates == []
    assert calls == [
        ("mitigation", name) for name in documents if name.startswith("mi-")
    ]
    calls.clear()
    result = await doc_tools.get_mitigation("ct-1")
    assert result.document_id == "1_control"
    assert result.mitigates == ["1_risk", "10_other"]
    assert result.related_mitigations == ["2_other"]
    assert calls == [("mitigation", "mi-1_control.md")]
    assert documents["mi-1_control.md"]["metadata"]["mitigates"] == [
        " RI-1 ",
        "1",
        "ri-10",
        "ri-999",
    ]


async def test_mid_listing_failure_preserves_entries_and_successful_links(monkeypatch):
    documents = {
        "ri-1_risk.md": _document(),
        "mi-1_control.md": _document({"mitigates": ["ri-1"]}),
        "mi-2_unread.md": None,
        "mi-3_skipped.md": _document({"mitigates": ["ri-1"]}),
    }
    _catalog(monkeypatch, documents)
    listing = await doc_tools.list_mitigations()
    assert listing.total_count == 3
    assert [entry.id for entry in listing.documents] == [
        "1_control",
        "2_unread",
        "3_skipped",
    ]
    assert [entry.mitigates for entry in listing.documents] == [["1_risk"], [], []]
    assert listing.source == "github_api"


@pytest.mark.parametrize(
    "metadata",
    [{}, {"mitigates": None}, {"mitigates": "ri-1"}, {"_parsing_error": "bad YAML"}],
)
async def test_forward_fields_without_usable_metadata_are_empty(monkeypatch, metadata):
    _catalog(monkeypatch, {"mi-1_control.md": _document(metadata)})
    result = await doc_tools.get_mitigation("mi-1")
    assert result.mitigates == result.related_mitigations == []


async def test_forward_links_filter_invalid_and_ambiguous_references(
    monkeypatch, caplog
):
    _catalog(
        monkeypatch,
        {
            "ri-1_first.md": _document(),
            "ri-1_second.md": _document(),
            "mi-1_control.md": _document(
                {"mitigates": ["ri-1", "1_first", 1, "", {}, "ri-999"]}
            ),
        },
    )
    result = await doc_tools.get_mitigation("1")
    assert result.mitigates == ["1_first"]
    assert "mitigates" in caplog.text


async def test_static_discovery_does_not_hide_readable_relationships(monkeypatch):
    _catalog(
        monkeypatch,
        {
            "ri-1_risk.md": _document(),
            "mi-1_control.md": _document({"mitigates": ["ri-1"]}),
        },
        source="static_fallback",
    )
    listing = await doc_tools.list_mitigations()
    assert listing.source == "static_fallback"
    assert listing.documents[0].mitigates == ["1_risk"]


async def test_risk_returns_related_and_inverse_links_in_catalog_order(monkeypatch):
    documents = {
        "ri-1_risk.md": _document({"related_risks": ["RI-10", "10_other", "ri-999"]}),
        "ri-10_other.md": _document(),
        "mi-2_control.md": _document({"mitigates": ["ri-1", "1", "ri-999"]}),
        "mi-1_other.md": _document({"mitigates": ["ri-10"]}),
        "mi-3_control.md": _document({"mitigates": ["1_risk"]}),
        "mi-4_empty.md": _document(),
    }
    calls = _catalog(monkeypatch, documents)
    result = await doc_tools.get_risk("RI-1")
    assert result.document_id == "1_risk"
    assert result.related_risks == ["10_other"]
    assert result.mitigated_by == ["2_control", "3_control"]
    assert calls == [
        ("risk", "ri-1_risk.md"),
        *[("mitigation", name) for name in documents if name.startswith("mi-")],
    ]
    listing = await doc_tools.list_risks()
    assert "mitigates" not in listing.documents[0].model_dump()


@pytest.mark.parametrize(
    "bad_document",
    [
        None,
        RuntimeError("private backend detail"),
        _document({"_parsing_error": "private parser detail"}),
        _document([]),
        _document({"mitigates": "ri-1"}),
        _document({"mitigates": ["ri-1", 1]}),
        _document({"mitigates": [""]}),
    ],
)
async def test_reverse_lookup_refuses_partial_or_malformed_metadata(
    monkeypatch, bad_document
):
    from finos_mcp.exceptions import ToolExecutionError

    _catalog(
        monkeypatch,
        {
            "ri-1_risk.md": _document(),
            "mi-1_good.md": _document({"mitigates": ["ri-1"]}),
            "mi-2_bad.md": bad_document,
            "mi-3_later.md": _document({"mitigates": ["ri-1"]}),
        },
    )
    with pytest.raises(ToolExecutionError, match="relationships") as failure:
        await doc_tools.get_risk("1")
    assert "private" not in str(failure.value)


@pytest.mark.parametrize("metadata", [{}, {"mitigates": None}, {"mitigates": []}])
async def test_reverse_lookup_accepts_declared_absence(monkeypatch, metadata):
    _catalog(
        monkeypatch, {"ri-1_risk.md": _document(), "mi-1_empty.md": _document(metadata)}
    )
    result = await doc_tools.get_risk("1")
    assert result.mitigated_by == result.related_risks == []


async def test_reverse_lookup_preserves_throttle_retry_information(monkeypatch):
    from finos_mcp.exceptions import DocumentThrottledError, GitHubRateLimitError

    _catalog(
        monkeypatch,
        {
            "ri-1_risk.md": _document(),
            "mi-1_bad.md": _document({"mitigates": "invalid"}),
            "mi-2_throttled.md": GitHubRateLimitError(
                "private backend detail", retry_after=23
            ),
        },
    )
    with pytest.raises(DocumentThrottledError) as failure:
        await doc_tools.get_risk("1")
    assert failure.value.retry_after == 23
    assert "private" not in str(failure.value)


@pytest.mark.parametrize("count", [0, 100, 101, 205])
async def test_reverse_lookup_reads_the_complete_catalog_beyond_the_title_ceiling(
    monkeypatch, count
):
    monkeypatch.setattr(doc_format, "_TITLE_FETCH_MAX_DOCUMENTS", 1)
    documents = {
        "ri-1_risk.md": _document(),
        **{
            f"mi-{number}_control.md": _document({"mitigates": ["ri-1"]})
            for number in range(1, count + 1)
        },
    }
    calls = _catalog(monkeypatch, documents)
    async with Client(mcp) as client:
        result = await client.call_tool("get_risk", {"risk_id": "1"})
    assert result.structured_content is not None
    assert result.structured_content["mitigated_by"] == [
        f"{number}_control" for number in range(1, count + 1)
    ]
    assert calls == [
        ("risk" if name.startswith("ri-") else "mitigation", name) for name in documents
    ]


@pytest.mark.parametrize("failure_kind", ["unread", "malformed", "throttled"])
async def test_reverse_lookup_still_rejects_unreadable_links_beyond_document_100(
    monkeypatch, failure_kind
):
    from finos_mcp.exceptions import (
        DocumentThrottledError,
        GitHubRateLimitError,
        ToolExecutionError,
    )

    bad_document = {
        "unread": None,
        "malformed": _document({"mitigates": "invalid"}),
        "throttled": GitHubRateLimitError("private throttle", retry_after=23),
    }[failure_kind]
    calls = _catalog(
        monkeypatch,
        {
            "ri-1_risk.md": _document(),
            **{f"mi-{number}_control.md": _document() for number in range(1, 101)},
            "mi-101_bad.md": bad_document,
        },
    )
    expected = (
        DocumentThrottledError if failure_kind == "throttled" else ToolExecutionError
    )
    with pytest.raises(expected) as failure:
        await doc_tools.get_risk("1")
    if failure_kind == "throttled":
        assert isinstance(failure.value, DocumentThrottledError)
        assert failure.value.retry_after == 23
    assert calls[-1] == ("mitigation", "mi-101_bad.md")


async def test_reverse_lookup_reads_only_metadata_with_bounded_concurrency(monkeypatch):
    documents = {
        "ri-1_risk.md": _document(),
        **{
            f"mi-{number}_control.md": _document({"mitigates": ["ri-1"]})
            for number in range(1, 24)
        },
    }
    calls = _catalog(monkeypatch, documents)
    active = 0
    peak = 0

    class Service:
        async def get_document(self, kind, filename):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0)
                calls.append((kind, filename))
                return documents[filename]
            finally:
                active -= 1

    async def service():
        return Service()

    async def no_title_resolution(*_args, **_kwargs):
        pytest.fail("reverse lookup must not resolve titles or descriptions")

    monkeypatch.setattr(doc_tools, "get_service", service)
    monkeypatch.setattr(doc_tools, "_resolve_document_names", no_title_resolution)
    result = await doc_tools.get_risk("1")
    assert len(result.mitigated_by) == 23
    assert 1 < peak <= 4
    assert active == 0
    assert len(calls) == len(documents)


@pytest.mark.parametrize("throttled", [True, False])
async def test_reverse_lookup_stops_after_a_failed_batch_and_preserves_throttling(
    monkeypatch, throttled
):
    from finos_mcp.exceptions import (
        DocumentThrottledError,
        GitHubRateLimitError,
        ToolExecutionError,
    )

    documents = {
        "ri-1_risk.md": _document(),
        **{f"mi-{number}_control.md": _document() for number in range(1, 10)},
        "mi-2_control.md": RuntimeError("private backend detail"),
        "mi-3_control.md": GitHubRateLimitError("private throttle", retry_after=23)
        if throttled
        else _document(),
    }
    calls = _catalog(monkeypatch, documents)
    expected = DocumentThrottledError if throttled else ToolExecutionError
    with pytest.raises(expected) as failure:
        await doc_tools.get_risk("1")
    if throttled:
        assert isinstance(failure.value, DocumentThrottledError)
        assert failure.value.retry_after == 23
    assert "private" not in str(failure.value)
    assert calls == [
        ("risk", "ri-1_risk.md"),
        *[("mitigation", f"mi-{number}_control.md") for number in range(1, 6)],
    ]


async def test_reverse_lookup_stops_after_a_failed_serial_probe(monkeypatch):
    from finos_mcp.exceptions import ToolExecutionError

    calls = _catalog(
        monkeypatch,
        {
            "ri-1_risk.md": _document(),
            "mi-1_unread.md": None,
            "mi-2_later.md": _document(),
        },
    )
    with pytest.raises(ToolExecutionError, match="relationships"):
        await doc_tools.get_risk("1")
    assert calls == [("risk", "ri-1_risk.md"), ("mitigation", "mi-1_unread.md")]


async def test_large_reverse_lookups_reuse_the_existing_document_cache(monkeypatch):
    from finos_mcp.content.cache import TTLCache
    from finos_mcp.content.service import ContentService

    documents = {
        "ri-1_risk.md": _document(),
        **{
            f"mi-{number}_control.md": _document({"mitigates": ["ri-1"]})
            for number in range(1, 102)
        },
    }
    _catalog(monkeypatch, documents)
    cache = TTLCache[str, dict[str, Any]]()
    for filename, document in documents.items():
        kind = "risk" if filename.startswith("ri-") else "mitigation"
        await cache.set(f"{kind}:{filename}", document)
    cached_service = ContentService(cache=cache)

    async def service():
        return cached_service

    async def no_fetch(*_args, **_kwargs):
        pytest.fail("cached relationship reads must not fetch content")

    monkeypatch.setattr(doc_tools, "get_service", service)
    monkeypatch.setattr(cached_service, "_fetch_content_with_boundary", no_fetch)
    for _ in range(2):
        result = await doc_tools.get_risk("1")
        assert result.mitigated_by == [f"{number}_control" for number in range(1, 102)]
    assert cached_service.successful_requests == 204


async def test_cancelling_reverse_lookup_cancels_pending_document_reads(monkeypatch):
    documents = {
        "ri-1_risk.md": _document(),
        **{f"mi-{number}_control.md": _document() for number in range(1, 10)},
    }
    _catalog(monkeypatch, documents)
    ready = asyncio.Event()
    blocked = asyncio.Event()
    active = 0

    class Service:
        async def get_document(self, kind, filename):
            nonlocal active
            if kind == "risk" or filename == "mi-1_control.md":
                return documents[filename]
            active += 1
            try:
                if active == 4:
                    ready.set()
                await blocked.wait()
                return documents[filename]
            finally:
                active -= 1

    async def service():
        return Service()

    monkeypatch.setattr(doc_tools, "get_service", service)
    monkeypatch.setattr(doc_format, "get_service", service)
    lookup = asyncio.create_task(doc_tools.get_risk("1"))
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
    finally:
        lookup.cancel()
        with pytest.raises(asyncio.CancelledError):
            await lookup
    assert active == 0


async def test_a_cancelled_document_read_is_not_reported_as_a_tool_error(monkeypatch):
    calls = _catalog(
        monkeypatch,
        {
            "ri-1_risk.md": _document(),
            **{f"mi-{number}_control.md": _document() for number in range(1, 10)},
            "mi-2_control.md": asyncio.CancelledError(),
        },
    )
    with pytest.raises(asyncio.CancelledError):
        await doc_tools.get_risk("1")
    assert calls == [
        ("risk", "ri-1_risk.md"),
        *[("mitigation", f"mi-{number}_control.md") for number in range(1, 6)],
    ]


async def test_resource_reads_do_not_depend_on_other_documents(monkeypatch):
    from finos_mcp.resources import get_mitigation_resource, get_risk_resource

    documents = {
        "ri-1_risk.md": _document(),
        "mi-1_control.md": _document(),
        "mi-2_bad.md": None,
    }
    calls = _catalog(monkeypatch, documents)
    assert await get_risk_resource("1") == documents["ri-1_risk.md"]["content"]
    assert await get_mitigation_resource("1") == documents["mi-1_control.md"]["content"]
    assert calls == [("risk", "ri-1_risk.md"), ("mitigation", "mi-1_control.md")]


async def test_inverse_results_follow_current_metadata_without_an_extra_cache(
    monkeypatch,
):
    documents = {
        "ri-1_risk.md": _document(),
        "mi-1_control.md": _document({"mitigates": ["ri-1"]}),
    }
    _catalog(monkeypatch, documents)
    assert (await doc_tools.get_risk("1")).mitigated_by == ["1_control"]
    _catalog(monkeypatch, {**documents, "mi-1_control.md": _document()})
    assert (await doc_tools.get_risk("1")).mitigated_by == []


async def test_mcp_serializes_relationships_in_structured_and_text_results(monkeypatch):
    _catalog(
        monkeypatch,
        {
            "ri-1_risk.md": _document({"related_risks": ["ri-10"]}),
            "ri-10_other.md": _document(),
            "mi-1_control.md": _document(
                {"mitigates": ["ri-1"], "related_mitigations": ["ct-2"]}
            ),
            "mi-2_other.md": _document(),
        },
    )
    async with Client(mcp) as client:
        assert len(await client.list_tools()) == 9
        listing = await client.call_tool("list_mitigations", {})
        mitigation = await client.call_tool("get_mitigation", {"mitigation_id": "ct-1"})
        risk = await client.call_tool("get_risk", {"risk_id": "ri-1"})
        for result in (listing, mitigation, risk):
            assert not result.is_error
            assert result.structured_content == json.loads(result.content[0].text)
        assert listing.structured_content is not None
        assert mitigation.structured_content is not None
        assert risk.structured_content is not None
        assert listing.structured_content["documents"][0]["mitigates"] == ["1_risk"]
        assert mitigation.structured_content["mitigates"] == ["1_risk"]
        assert mitigation.structured_content["related_mitigations"] == ["2_other"]
        assert risk.structured_content["related_risks"] == ["10_other"]
        assert risk.structured_content["mitigated_by"] == ["1_control"]


async def test_mcp_refuses_incomplete_inverse_but_still_serves_the_resource(
    monkeypatch,
):
    documents = {
        "ri-1_risk.md": _document(),
        "mi-1_unread.md": RuntimeError("private backend detail"),
    }
    calls = _catalog(monkeypatch, documents)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_risk", {"risk_id": "1"}, raise_on_error=False
        )
        assert result.is_error
        assert result.structured_content is None
        assert "relationships" in result.content[0].text
        assert "private" not in result.content[0].text
        resource = await client.read_resource("finos://risks/1")
        assert resource[0].text == documents["ri-1_risk.md"]["content"]
        assert calls == [
            ("risk", "ri-1_risk.md"),
            ("mitigation", "mi-1_unread.md"),
            ("risk", "ri-1_risk.md"),
        ]


async def test_published_schemas_limit_relationship_fields_to_their_tools():
    schemas = {}
    for tool in await mcp.list_tools():
        assert tool.output_schema is not None
        schemas[tool.name] = tool.output_schema
    listing_properties = schemas["list_mitigations"]["properties"]
    entry_properties = listing_properties["documents"]["items"]["properties"]
    assert entry_properties["mitigates"]["items"] == {"type": "string"}
    assert entry_properties["mitigates"]["type"] == "array"
    risk_properties = schemas["get_risk"]["properties"]
    mitigation_properties = schemas["get_mitigation"]["properties"]
    assert {"related_risks", "mitigated_by"} <= set(risk_properties)
    assert {"mitigates", "related_mitigations"} <= set(mitigation_properties)
    assert "mitigates" not in risk_properties
    assert "related_risks" not in mitigation_properties
    risk_entry = schemas["list_risks"]["properties"]["documents"]["items"]["properties"]
    assert "mitigates" not in risk_entry
