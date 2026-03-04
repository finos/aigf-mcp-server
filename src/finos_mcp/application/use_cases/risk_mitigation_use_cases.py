"""Application use-cases for risk and mitigation operations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


def _strip_doc_id(filename: str, prefix: str) -> str:
    return filename.removesuffix(".md").removeprefix(prefix)


async def execute_list_documents(
    *,
    document_type: str,
    prefix: str,
    static_files: list[str],
    discover_file_infos: Callable[[], Awaitable[list[Any]]],
    format_document_name: Callable[[str, str], str],
    logger: Any,
) -> dict[str, Any]:
    """List risk/mitigation documents with static fallback."""
    source = "github_api"
    try:
        file_infos = await discover_file_infos()
        filenames = [f.filename for f in file_infos]
        last_modified_map = {
            f.filename: (f.last_modified.isoformat() if f.last_modified else None)
            for f in file_infos
        }
    except Exception as exc:
        logger.error("Failed to list %s documents: %s", document_type, exc)
        filenames = list(static_files)
        last_modified_map = {}
        source = "static_fallback"

    documents = []
    for filename in filenames:
        doc_id = _strip_doc_id(filename, prefix)
        doc_name = format_document_name(filename, prefix)
        label = "risk" if document_type == "risk" else "mitigation"
        documents.append(
            {
                "id": doc_id,
                "name": doc_name,
                "filename": filename,
                "description": f"AI governance {label}: {doc_name}",
                "last_modified": last_modified_map.get(filename),
                "title": doc_name,
            }
        )

    return {
        "documents": documents,
        "total_count": len(documents),
        "document_type": document_type,
        "source": source,
    }


async def execute_get_document(
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
    logger: Any,
) -> dict[str, Any]:
    """Get risk/mitigation content with static fallback discovery."""
    try:
        filenames = await discover_filenames()
    except Exception as discovery_error:
        logger.warning(
            "%s discovery failed, using static fallback list: %s",
            doc_type.capitalize(),
            discovery_error,
        )
        filenames = list(static_files)

    target_filename = None
    for filename in filenames:
        file_id = filename.replace(".md", "").replace(prefix, "")
        if file_id == requested_id:
            target_filename = filename
            break

    if not target_filename:
        label = doc_type.capitalize()
        return {
            "document_id": requested_id,
            "title": f"{label} {requested_id} not found",
            "content": f"{label} document with ID '{requested_id}' was not found in the repository.",
            "sections": [],
        }

    doc = await get_document_by_filename(doc_type, target_filename)
    if not doc:
        return {
            "document_id": requested_id,
            "title": f"Error loading {doc_type} {requested_id}",
            "content": f"Failed to load content for {doc_type} document '{requested_id}'.",
            "sections": [],
        }

    content = doc.get("content", "")
    title = doc.get("title") or format_document_name(target_filename, prefix)
    fallback = (
        f"{doc_type.capitalize()} document exceeded allowed size limits. "
        "Please narrow your query."
    )

    try:
        content, sections = safe_document_content(
            content,
            f"{doc_type}:{requested_id}",
            fallback,
        )
    except Exception as exc:
        logger.warning("Error while sanitizing %s %s: %s", doc_type, requested_id, exc)
        return {
            "document_id": requested_id,
            "title": f"Error loading {doc_type} {requested_id}",
            "content": safe_external_error(
                exc, f"Error loading {doc_type} document. Please retry later."
            ),
            "sections": [],
        }

    return {
        "document_id": requested_id,
        "title": title,
        "content": content,
        "sections": sections,
    }


async def execute_search_documents(
    *,
    query: str,
    limit: int,
    list_documents_fn: Callable[[], Awaitable[Any]],
    search_single_document_fn: Callable[
        [Any, str], Awaitable[list[tuple[Any, bool, int]]]
    ],
    logger: Any,
    label: str,
) -> dict[str, Any]:
    """Search risk/mitigation docs in parallel with ranked exact-match priority."""
    docs_list = await list_documents_fn()
    total_documents = len(docs_list.documents)
    logger.info(
        "Starting search across %d %s documents for query: %r",
        total_documents,
        label,
        query,
    )

    search_tasks = [
        search_single_document_fn(document, query) for document in docs_list.documents
    ]
    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

    tagged: list[tuple[Any, bool, int]] = []
    for result in search_results:
        if isinstance(result, list):
            tagged.extend(result)
        elif isinstance(result, Exception):
            logger.warning("Search task failed: %s", result)

    tagged.sort(key=lambda x: (not x[1], x[2]))
    results = [r for r, _, __ in tagged]
    return {"query": query, "results": results[:limit], "total_found": len(results)}
