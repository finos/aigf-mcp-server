"""Unit tests for risk/mitigation use-cases."""

import pytest

from finos_mcp.application.use_cases.risk_mitigation_use_cases import (
    execute_get_document,
    execute_list_documents,
    execute_search_documents,
)


class _FakeFileInfo:
    def __init__(self, filename: str, last_modified=None):
        self.filename = filename
        self.last_modified = last_modified


class _Logger:
    def error(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None


@pytest.mark.unit
class TestRiskMitigationUseCases:
    @pytest.mark.asyncio
    async def test_execute_list_documents_success(self):
        payload = await execute_list_documents(
            document_type="risk",
            prefix="ri-",
            discover_file_infos=lambda: _async_return(
                [_FakeFileInfo("ri-risk-a.md"), _FakeFileInfo("ri-risk-b.md")]
            ),
            format_document_name=lambda filename, prefix: filename.removeprefix(
                prefix
            ).removesuffix(".md"),
            logger=_Logger(),
        )

        assert payload["total_count"] == 2
        assert payload["source"] == "github_api"
        assert payload["documents"][0]["id"] == "risk-a"

    @pytest.mark.asyncio
    async def test_execute_list_documents_fallback(self):
        async def _raise_discovery():
            raise RuntimeError("boom")

        payload = await execute_list_documents(
            document_type="mitigation",
            prefix="mi-",
            discover_file_infos=_raise_discovery,
            format_document_name=lambda filename, prefix: filename.removeprefix(
                prefix
            ).removesuffix(".md"),
            logger=_Logger(),
        )

        assert payload["total_count"] == 0
        assert payload["source"] == "unavailable"
        assert payload["message"] is not None

    @pytest.mark.asyncio
    async def test_execute_get_document_found(self):
        payload = await execute_get_document(
            requested_id="risk-a",
            doc_type="risk",
            prefix="ri-",
            discover_filenames=lambda: _async_return(["ri-risk-a.md"]),
            get_document_by_filename=lambda doc_type, filename: _async_return(
                {"content": "# Header\nbody", "title": "Risk A"}
            ),
            format_document_name=lambda filename, prefix: "Formatted",
            safe_document_content=lambda content, doc_id, fallback: (
                content,
                ["Header"],
            ),
            safe_external_error=lambda e, m: m,
            logger=_Logger(),
        )

        assert payload["document_id"] == "risk-a"
        assert payload["title"] == "Risk A"
        assert payload["sections"] == ["Header"]

    @pytest.mark.asyncio
    async def test_execute_get_document_not_found(self):
        payload = await execute_get_document(
            requested_id="missing",
            doc_type="risk",
            prefix="ri-",
            discover_filenames=lambda: _async_return(["ri-risk-a.md"]),
            get_document_by_filename=lambda doc_type, filename: _async_return(None),
            format_document_name=lambda filename, prefix: "Formatted",
            safe_document_content=lambda content, doc_id, fallback: (content, []),
            safe_external_error=lambda e, m: m,
            logger=_Logger(),
        )

        assert payload["document_id"] == "missing"
        assert "not found" in payload["content"]

    @pytest.mark.asyncio
    async def test_execute_search_documents_ranks_exact_first(self):
        docs = type(
            "Docs",
            (),
            {
                "documents": [
                    type("D", (), {"id": "1"})(),
                    type("D", (), {"id": "2"})(),
                ]
            },
        )()

        async def _search_single(document, query):
            if document.id == "1":
                return [("partial", False, 1)]
            return [("exact", True, 50)]

        payload = await execute_search_documents(
            query="x",
            limit=10,
            list_documents_fn=lambda: _async_return(docs),
            search_single_document_fn=_search_single,
            logger=_Logger(),
            label="risk",
        )

        assert payload["total_found"] == 2
        assert payload["results"][0] == "exact"


async def _async_return(value):
    return value
