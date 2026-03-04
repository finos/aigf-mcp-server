"""API-layer handler helpers for governance catalog tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


async def list_frameworks_payload(
    *,
    apply_dos: Callable[[], Awaitable[None]],
    execute_list_frameworks_fn: Callable[..., Awaitable[dict[str, Any]]],
    repository: Any,
    static_framework_files: list[str],
    logger: Any,
) -> dict[str, Any]:
    """Build payload for list_frameworks tool."""
    await apply_dos()
    return await execute_list_frameworks_fn(
        repository=repository,
        static_framework_files=static_framework_files,
        logger=logger,
    )


async def get_framework_payload(
    *,
    framework_id: str,
    apply_dos: Callable[[], Awaitable[None]],
    validate_request_params: Callable[..., None],
    execute_get_framework_fn: Callable[..., Awaitable[dict[str, Any]]],
    repository: Any,
    static_framework_files: list[str],
    format_yaml_content: Callable[[str, str], str],
    validate_resource_size: Callable[[str], None],
    safe_external_error: Callable[[Exception, str], str],
    logger: Any,
) -> dict[str, Any]:
    """Build payload for get_framework tool."""
    try:
        await apply_dos()
        validate_request_params(framework=framework_id)
        return await execute_get_framework_fn(
            framework_id=framework_id,
            repository=repository,
            static_framework_files=static_framework_files,
            format_yaml_content=format_yaml_content,
            validate_resource_size=validate_resource_size,
            safe_external_error=safe_external_error,
            logger=logger,
        )
    except Exception as exc:
        logger.error("Failed to get framework content: %s", exc)
        return {
            "framework_id": framework_id,
            "content": safe_external_error(
                exc, "Error loading framework. Please retry later."
            ),
            "sections": 0,
        }


async def search_frameworks_payload(
    *,
    query: str,
    limit: int,
    apply_dos: Callable[[], Awaitable[None]],
    validate_request_params: Callable[..., None],
    execute_search_frameworks_fn: Callable[..., Awaitable[dict[str, Any]]],
    list_frameworks_fn: Callable[[], Awaitable[Any]],
    search_single_framework_fn: Callable[[Any, str], Awaitable[list[Any]]],
    logger: Any,
) -> dict[str, Any]:
    """Build payload for search_frameworks tool."""
    try:
        await apply_dos()
        validate_request_params(query=query, limit=limit)
        return await execute_search_frameworks_fn(
            query=query,
            limit=limit,
            list_frameworks_fn=list_frameworks_fn,
            search_single_framework_fn=search_single_framework_fn,
            logger=logger,
        )
    except Exception as exc:
        logger.error("Failed to search frameworks: %s", exc)
        return {"query": query, "results": [], "total_found": 0}


async def list_documents_payload(
    *,
    document_type: str,
    prefix: str,
    static_files: list[str],
    discover_file_infos: Callable[[], Awaitable[list[Any]]],
    format_document_name: Callable[[str, str], str],
    apply_dos: Callable[[], Awaitable[None]],
    execute_list_documents_fn: Callable[..., Awaitable[dict[str, Any]]],
    logger: Any,
) -> dict[str, Any]:
    """Build payload for list_risks/list_mitigations tools."""
    await apply_dos()
    return await execute_list_documents_fn(
        document_type=document_type,
        prefix=prefix,
        static_files=static_files,
        discover_file_infos=discover_file_infos,
        format_document_name=format_document_name,
        logger=logger,
    )


async def get_document_payload(
    *,
    requested_id: str,
    doc_type: str,
    prefix: str,
    static_files: list[str],
    discover_filenames: Callable[[], Awaitable[list[str]]],
    get_document_by_filename: Callable[[str, str], Awaitable[dict[str, Any] | None]],
    format_document_name: Callable[[str, str], str],
    safe_document_content: Callable[[str, str, str], tuple[str, list[str]]],
    safe_external_error: Callable[[Exception, str], str],
    apply_dos: Callable[[], Awaitable[None]],
    validate_request_params: Callable[..., None],
    execute_get_document_fn: Callable[..., Awaitable[dict[str, Any]]],
    logger: Any,
) -> dict[str, Any]:
    """Build payload for get_risk/get_mitigation tools."""
    try:
        await apply_dos()
        validate_request_params(**{f"{doc_type}_id": requested_id})
        return await execute_get_document_fn(
            requested_id=requested_id,
            doc_type=doc_type,
            prefix=prefix,
            static_files=static_files,
            discover_filenames=discover_filenames,
            get_document_by_filename=get_document_by_filename,
            format_document_name=format_document_name,
            safe_document_content=safe_document_content,
            safe_external_error=safe_external_error,
            logger=logger,
        )
    except Exception as exc:
        logger.error("Failed to get %s content for %s: %s", doc_type, requested_id, exc)
        return {
            "document_id": requested_id,
            "title": f"Error loading {doc_type} {requested_id}",
            "content": safe_external_error(
                exc, f"Error loading {doc_type} document. Please retry later."
            ),
            "sections": [],
        }


async def search_documents_payload(
    *,
    query: str,
    limit: int,
    label: str,
    apply_dos: Callable[[], Awaitable[None]],
    validate_request_params: Callable[..., None],
    execute_search_documents_fn: Callable[..., Awaitable[dict[str, Any]]],
    list_documents_fn: Callable[[], Awaitable[Any]],
    search_single_document_fn: Callable[
        [Any, str], Awaitable[list[tuple[Any, bool, int]]]
    ],
    logger: Any,
) -> dict[str, Any]:
    """Build payload for search_risks/search_mitigations tools."""
    try:
        await apply_dos()
        validate_request_params(query=query, limit=limit)
        return await execute_search_documents_fn(
            query=query,
            limit=limit,
            list_documents_fn=list_documents_fn,
            search_single_document_fn=search_single_document_fn,
            logger=logger,
            label=label,
        )
    except Exception as exc:
        logger.error("Failed to search %ss: %s", label, exc)
        return {"query": query, "results": [], "total_found": 0}
