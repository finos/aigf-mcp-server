"""Declared relationships survive retrieval, normalization and MCP serialization."""

from collections.abc import Mapping
from typing import Any

import pytest

from finos_mcp import models
from finos_mcp.documents import format as doc_format

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
