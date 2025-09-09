"""Detail tools for FINOS MCP Server.

Provides detailed document retrieval for specific mitigations and risks by ID.
"""

from typing import Any

from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

from ..content.service import get_content_service
from ..logging import get_logger
from ..security.validators import ValidationError, validate_document_id
from .search import get_mitigation_files, get_risk_files

logger = get_logger("details_tools")


class GetMitigationDetailsRequest(BaseModel):
    """Request model for getting mitigation details."""

    mitigation_id: str = Field(
        ..., description="Mitigation ID (e.g., 'mi-1', 'mi-10') or filename"
    )


class GetRiskDetailsRequest(BaseModel):
    """Request model for getting risk details."""

    risk_id: str = Field(..., description="Risk ID (e.g., 'ri-1', 'ri-10') or filename")


# Tool definitions
DETAILS_TOOLS: list[Tool] = [
    Tool(
        name="get_mitigation_details",
        description="Get detailed information about a specific mitigation",
        inputSchema={
            "type": "object",
            "properties": {
                "mitigation_id": {
                    "type": "string",
                    "description": "Mitigation ID (e.g., 'mi-1', 'mi-10') or filename",
                }
            },
            "required": ["mitigation_id"],
        },
    ),
    Tool(
        name="get_risk_details",
        description="Get detailed information about a specific risk",
        inputSchema={
            "type": "object",
            "properties": {
                "risk_id": {
                    "type": "string",
                    "description": "Risk ID (e.g., 'ri-1', 'ri-10') or filename",
                }
            },
            "required": ["risk_id"],
        },
    ),
]


def _find_file_by_id(file_list: list[str], doc_id: str) -> str | None:
    """Find filename by document ID.

    Args:
        file_list: List of available filenames
        doc_id: Document ID or filename to search for

    Returns:
        Matching filename or None if not found

    """
    # If it's already a filename, return as-is if it exists
    if doc_id.endswith(".md"):
        return doc_id if doc_id in file_list else None

    # Search for file starting with the ID
    for filename in file_list:
        if filename.startswith(doc_id + "_") or filename.startswith(doc_id + "."):
            return filename

    return None


async def _get_document_details(
    doc_type: str, doc_id: str, file_list: list[str]
) -> str:
    """Get detailed document content by ID.

    Args:
        doc_type: Type of document ('mitigation' or 'risk')
        doc_id: Document ID to retrieve
        file_list: List of available files

    Returns:
        Full document text or error message

    """
    filename = _find_file_by_id(file_list, doc_id)

    if not filename:
        error_msg = f"{doc_type.capitalize()} {doc_id} not found"
        logger.warning(error_msg, extra={"doc_type": doc_type, "doc_id": doc_id})
        return error_msg

    service = await get_content_service()
    doc_data = await service.get_document(doc_type, filename)

    if not doc_data:
        error_msg = f"Failed to fetch {doc_type} {doc_id}"
        logger.error(
            error_msg,
            extra={
                "doc_type": doc_type,
                "doc_id": doc_id,
                "document_filename": filename,
            },
        )
        return error_msg

    logger.info(
        "Retrieved %s details: %s",
        doc_type,
        doc_id,
        extra={
            "doc_type": doc_type,
            "doc_id": doc_id,
            "document_filename": filename,
            "content_length": len(doc_data["full_text"]),
        },
    )

    return doc_data["full_text"]


async def handle_details_tools(
    name: str, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle detail tool calls.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        Document details as TextContent

    """
    logger.debug(
        "Handling details tool: %s",
        name,
        extra={"tool_name": name, "arguments": arguments},
    )

    if name == "get_mitigation_details":
        try:
            # Validate input using Pydantic
            request = GetMitigationDetailsRequest(**arguments)

            # Additional security validation
            validated_id = validate_document_id(request.mitigation_id)

            logger.info(
                "Processing mitigation details request",
                extra={"mitigation_id": validated_id},
            )

            mitigation_files = await get_mitigation_files()
            content = await _get_document_details(
                "mitigation", validated_id, mitigation_files
            )
            return [TextContent(type="text", text=content)]

        except ValidationError as e:
            logger.warning("Document ID validation failed: %s", e.message)
            error_message = (
                f"Invalid mitigation ID: {e.message}\n\n"
                "Valid formats: mi-1, mi-10, or full filenames like mi-1_description.md"
            )
            return [TextContent(type="text", text=error_message)]

    elif name == "get_risk_details":
        try:
            # Validate input using Pydantic
            risk_request = GetRiskDetailsRequest(**arguments)

            # Additional security validation
            validated_id = validate_document_id(risk_request.risk_id)

            logger.info(
                "Processing risk details request", extra={"risk_id": validated_id}
            )

            risk_files = await get_risk_files()
            content = await _get_document_details("risk", validated_id, risk_files)
            return [TextContent(type="text", text=content)]

        except ValidationError as e:
            logger.warning("Document ID validation failed: %s", e.message)
            error_message = (
                f"Invalid risk ID: {e.message}\n\n"
                "Valid formats: ri-1, ri-5, or full filenames like ri-1_description.md"
            )
            return [TextContent(type="text", text=error_message)]

    else:
        raise ValueError(f"Unknown details tool: {name}")
