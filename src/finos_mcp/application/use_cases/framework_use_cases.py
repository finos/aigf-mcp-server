"""Application use-cases for framework operations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

DEFAULT_FRAMEWORK_NAME_MAP: dict[str, str] = {
    "nist-ai-600-1": "NIST AI 600-1 Framework",
    "eu-ai-act": "EU AI Act 2024",
    "gdpr": "General Data Protection Regulation (GDPR)",
    "owasp-llm": "OWASP LLM Top 10",
    "iso-23053": "ISO/IEC 23053 Framework",
}


def format_framework_name(framework_id: str) -> str:
    """Format framework ID into a readable name."""
    return DEFAULT_FRAMEWORK_NAME_MAP.get(
        framework_id, framework_id.replace("-", " ").title()
    )


async def execute_list_frameworks(
    *,
    repository: Any,
    static_framework_files: list[str],
    logger: Any,
) -> dict[str, Any]:
    """List frameworks using repository discovery with static fallback."""
    try:
        framework_files = await repository.discover_framework_file_infos()
        filenames = [file_info.filename for file_info in framework_files]
    except Exception as exc:
        logger.error("Failed to list frameworks via discovery: %s", exc)
        filenames = list(static_framework_files)

    frameworks: list[dict[str, Any]] = []
    for filename in filenames:
        framework_id = filename.replace(".yml", "").replace(".yaml", "")
        framework_name = format_framework_name(framework_id)
        frameworks.append(
            {
                "id": framework_id,
                "name": framework_name,
                "description": f"Framework definition: {framework_name}",
                "title": framework_name,
            }
        )

    return {"frameworks": frameworks, "total_count": len(frameworks)}


async def execute_get_framework(
    *,
    framework_id: str,
    repository: Any,
    static_framework_files: list[str],
    format_yaml_content: Callable[[str, str], str],
    validate_resource_size: Callable[[str], None],
    safe_external_error: Callable[[Exception, str], str],
    logger: Any,
) -> dict[str, Any]:
    """Get framework content with size-safe formatting and fallback behavior."""
    try:
        framework_filenames = await repository.discover_framework_filenames()
    except Exception as discovery_error:
        logger.warning(
            "Framework discovery failed, using static fallback list: %s",
            discovery_error,
        )
        framework_filenames = list(static_framework_files)

    target_filename = None
    for filename in framework_filenames:
        file_id = filename.replace(".yml", "").replace(".yaml", "")
        if file_id == framework_id:
            target_filename = filename
            break

    if not target_filename:
        return {
            "framework_id": framework_id,
            "content": f"Framework '{framework_id}' was not found in the repository.",
            "sections": 0,
        }

    doc = await repository.get_framework_document(target_filename)
    if not doc:
        return {
            "framework_id": framework_id,
            "content": f"Failed to load content for framework '{framework_id}'.",
            "sections": 0,
        }

    content = doc.get("content", "")
    if content.strip():
        formatted_content = format_yaml_content(content, framework_id)
        try:
            validate_resource_size(formatted_content)
        except ValueError as size_error:
            logger.warning(
                "Framework payload exceeded size limit for %s: %s",
                framework_id,
                size_error,
            )
            formatted_content = safe_external_error(
                size_error,
                "Framework content exceeded allowed size limits. Please narrow your query.",
            )
        sections = len(
            [
                line
                for line in content.split("\n")
                if line.strip() and not line.startswith(" ") and ":" in line
            ]
        )
    else:
        formatted_content = (
            f"Framework {framework_id} content is empty or not accessible."
        )
        sections = 0

    return {
        "framework_id": framework_id,
        "content": formatted_content,
        "sections": sections,
    }


async def execute_search_frameworks(
    *,
    query: str,
    limit: int,
    list_frameworks_fn: Callable[[], Awaitable[Any]],
    search_single_framework_fn: Callable[[Any, str], Awaitable[list[Any]]],
    logger: Any,
) -> dict[str, Any]:
    """Search frameworks in parallel using provided search callbacks."""
    frameworks_list = await list_frameworks_fn()

    total_frameworks = len(frameworks_list.frameworks)
    logger.info(
        "Starting search across %d frameworks for query: %r",
        total_frameworks,
        query,
    )

    search_tasks = [
        search_single_framework_fn(framework, query)
        for framework in frameworks_list.frameworks
    ]

    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

    logger.info("Completed parallel search across %d frameworks", total_frameworks)

    results = []
    for result in search_results:
        if isinstance(result, list):
            results.extend(result)
        elif isinstance(result, Exception):
            logger.warning("Search task failed: %s", result)

    limited_results = results[:limit]
    return {"query": query, "results": limited_results, "total_found": len(results)}
