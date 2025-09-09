"""Listing tools for FINOS MCP Server.

Provides comprehensive listing of all available mitigations and risks with metadata.
"""

import json
from typing import Any

from mcp.types import TextContent, Tool
from pydantic import BaseModel

from ..content.service import get_content_service
from ..logging import get_logger
from .search import get_mitigation_files, get_risk_files

logger = get_logger("listing_tools")


class ListAllMitigationsRequest(BaseModel):
    """Request model for listing all mitigations (no parameters)."""


class ListAllRisksRequest(BaseModel):
    """Request model for listing all risks (no parameters)."""


# Tool definitions
LISTING_TOOLS: list[Tool] = [
    Tool(
        name="list_all_mitigations",
        description="List all available AI governance mitigations with their metadata",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="list_all_risks",
        description="List all available AI governance risks with their metadata",
        inputSchema={"type": "object", "properties": {}},
    ),
]


async def _list_documents(doc_type: str, file_list: list[str]) -> list[dict[str, Any]]:
    """List all documents of a specific type with metadata.

    Args:
        doc_type: Type of document ('mitigation' or 'risk')
        file_list: List of filenames to process

    Returns:
        List of document summaries with metadata

    """
    results = []
    service = await get_content_service()

    for filename in file_list:
        doc_data = await service.get_document(doc_type, filename)
        if doc_data:
            result = {
                "filename": filename,
                "title": doc_data["metadata"].get("title", ""),
                "sequence": doc_data["metadata"].get("sequence", ""),
                "type": doc_data["metadata"].get("type", ""),
                "status": doc_data["metadata"].get("doc-status", ""),
            }

            # Add type-specific fields
            if doc_type == "mitigation":
                result["mitigates"] = doc_data["metadata"].get("mitigates", [])
            elif doc_type == "risk":
                result["related_risks"] = doc_data["metadata"].get("related_risks", [])

            results.append(result)
        else:
            logger.warning("Failed to fetch %s: %s", doc_type, filename)

    # Sort by sequence number for consistent ordering
    results.sort(key=lambda x: x.get("sequence", 0))

    logger.info(
        "Listed all %ss: %s items",
        doc_type,
        len(results),
        extra={
            "doc_type": doc_type,
            "total_files": len(file_list),
            "successful_fetches": len(results),
        },
    )

    return results


async def handle_listing_tools(
    name: str, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle listing tool calls.

    Args:
        name: Tool name
        arguments: Tool arguments (usually empty for listing operations)

    Returns:
        Document listings as TextContent

    """
    logger.debug(
        "Handling listing tool: %s",
        name,
        extra={"tool_name": name, "arguments": arguments},
    )

    if name == "list_all_mitigations":
        # Validate input using Pydantic (no parameters expected)
        ListAllMitigationsRequest(**arguments)  # Validate input
        mitigation_files = await get_mitigation_files()
        results = await _list_documents("mitigation", mitigation_files)
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    if name == "list_all_risks":
        # Validate input using Pydantic (no parameters expected)
        ListAllRisksRequest(**arguments)  # Validate input
        risk_files = await get_risk_files()
        results = await _list_documents("risk", risk_files)
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    raise ValueError(f"Unknown listing tool: {name}")
