"""Unit tests for governance API tool handlers."""

import pytest

from finos_mcp.api.tools import (
    get_document_payload,
    get_framework_payload,
    list_documents_payload,
    list_frameworks_payload,
    search_documents_payload,
    search_frameworks_payload,
)


class _Logger:
    def error(self, *args, **kwargs):
        return None


async def _noop() -> None:
    return None


def _validate(**kwargs):
    return None


@pytest.mark.unit
class TestGovernanceToolHandlers:
    @pytest.mark.asyncio
    async def test_list_frameworks_payload(self):
        payload = await list_frameworks_payload(
            apply_dos=_noop,
            execute_list_frameworks_fn=lambda **kwargs: _async_return(
                {
                    "frameworks": [{"id": "f", "name": "F", "description": "d"}],
                    "total_count": 1,
                }
            ),
            repository=object(),
            static_framework_files=[],
            logger=_Logger(),
        )
        assert payload["total_count"] == 1

    @pytest.mark.asyncio
    async def test_get_framework_payload_error_fallback(self):
        async def _raise(**kwargs):
            raise RuntimeError("boom")

        payload = await get_framework_payload(
            framework_id="x",
            apply_dos=_noop,
            validate_request_params=_validate,
            execute_get_framework_fn=_raise,
            repository=object(),
            static_framework_files=[],
            format_yaml_content=lambda c, f: c,
            validate_resource_size=lambda c: None,
            safe_external_error=lambda e, m: m,
            logger=_Logger(),
        )
        assert payload["framework_id"] == "x"
        assert payload["sections"] == 0

    @pytest.mark.asyncio
    async def test_list_documents_payload(self):
        payload = await list_documents_payload(
            document_type="risk",
            prefix="ri-",
            static_files=[],
            discover_file_infos=lambda: _async_return([]),
            format_document_name=lambda f, p: f,
            apply_dos=_noop,
            execute_list_documents_fn=lambda **kwargs: _async_return(
                {
                    "documents": [{"id": "a", "name": "A", "filename": "ri-a.md"}],
                    "total_count": 1,
                    "document_type": "risk",
                    "source": "github_api",
                }
            ),
            logger=_Logger(),
        )
        assert payload["document_type"] == "risk"

    @pytest.mark.asyncio
    async def test_get_document_payload_success(self):
        payload = await get_document_payload(
            requested_id="a",
            doc_type="risk",
            prefix="ri-",
            static_files=[],
            discover_filenames=lambda: _async_return(["ri-a.md"]),
            get_document_by_filename=lambda d, f: _async_return({"content": "ok"}),
            format_document_name=lambda f, p: f,
            safe_document_content=lambda c, i, fb: (c, []),
            safe_external_error=lambda e, m: m,
            apply_dos=_noop,
            validate_request_params=_validate,
            execute_get_document_fn=lambda **kwargs: _async_return(
                {"document_id": "a", "title": "A", "content": "ok", "sections": []}
            ),
            logger=_Logger(),
        )
        assert payload["document_id"] == "a"

    @pytest.mark.asyncio
    async def test_search_payloads(self):
        f_payload = await search_frameworks_payload(
            query="x",
            limit=5,
            apply_dos=_noop,
            validate_request_params=_validate,
            execute_search_frameworks_fn=lambda **kwargs: _async_return(
                {"query": "x", "results": [], "total_found": 0}
            ),
            list_frameworks_fn=lambda: _async_return(
                type("L", (), {"frameworks": []})()
            ),
            search_single_framework_fn=lambda d, q: _async_return([]),
            logger=_Logger(),
        )
        d_payload = await search_documents_payload(
            query="x",
            limit=5,
            label="risk",
            apply_dos=_noop,
            validate_request_params=_validate,
            execute_search_documents_fn=lambda **kwargs: _async_return(
                {"query": "x", "results": [], "total_found": 0}
            ),
            list_documents_fn=lambda: _async_return(type("L", (), {"documents": []})()),
            search_single_document_fn=lambda d, q: _async_return([]),
            logger=_Logger(),
        )
        assert f_payload["total_found"] == 0
        assert d_payload["total_found"] == 0


async def _async_return(value):
    return value
