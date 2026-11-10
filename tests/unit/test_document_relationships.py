"""Declared relationships survive retrieval, normalization and MCP serialization."""

from collections.abc import Mapping
from typing import Any

import pytest

from finos_mcp import models
from finos_mcp.documents import format as doc_format
from finos_mcp.documents import tools as doc_tools
from finos_mcp.service import _discovery_manager

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
    from finos_mcp.content.discovery import DiscoveryResult, GitHubFileInfo

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
            if isinstance(value, Exception):
                raise value
            return value

    async def service():
        return Service()

    async def discover():
        return Discovery()

    monkeypatch.setattr(doc_tools, "get_service", service)
    monkeypatch.setattr(doc_format, "get_service", service)
    monkeypatch.setattr(_discovery_manager, "get_discovery_service", discover)
    return calls


def _document(metadata=None):
    return {"content": "## Purpose\n\nDeclared control.\n", "metadata": metadata or {}}


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
