"""Search tools for FINOS MCP Server.

Provides search functionality for mitigations and risks with keyword matching
and filtering capabilities.
"""

import asyncio
import json
import time
from typing import Any, Optional

import httpx
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

from ..content.discovery import discover_content
from ..content.service import get_content_service
from ..logging import get_logger


# Simple validation functions
class ValidationError(ValueError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def validate_search_request(query: str, exact_match: bool = False) -> str:
    """Simple search request validation."""
    if not query or not isinstance(query, str):
        raise ValidationError("Invalid search query")
    return query.strip()


logger = get_logger("search_tools")

# File lists (would be updated as repository grows)
MITIGATION_FILES = [
    "mi-1_ai-data-leakage-prevention-and-detection.md",
    "mi-2_data-filtering-from-external-knowledge-bases.md",
    "mi-3_user-app-model-firewalling-filtering.md",
    "mi-4_ai-system-observability.md",
    "mi-5_system-acceptance-testing.md",
    "mi-6_data-quality-classification-sensitivity.md",
    "mi-7_legal-and-contractual-frameworks-for-ai-systems.md",
    "mi-8_quality-of-service-qos-and-ddos-prevention-for-ai-systems.md",
    "mi-9_ai-system-alerting-and-denial-of-wallet-dow-spend-monitoring.md",
    "mi-10_ai-model-version-pinning.md",
    "mi-11_human-feedback-loop-for-ai-systems.md",
    "mi-12_role-based-access-control-for-ai-data.md",
    "mi-13_providing-citations-and-source-traceability-for-ai-generated-information.md",
    "mi-14_encryption-of-ai-data-at-rest.md",
    "mi-15_using-large-language-models-for-automated-evaluation-llm-as-a-judge-.md",
    "mi-16_preserving-source-data-access-controls-in-ai-systems.md",
    "mi-17_ai-firewall-implementation-and-management.md",
]

RISK_FILES = [
    "ri-1_information-leaked-to-hosted-model.md",
    "ri-2_information-leaked-to-vector-store.md",
    "ri-4_hallucination-and-inaccurate-outputs.md",
    "ri-5_foundation-model-versioning.md",
    "ri-6_non-deterministic-behaviour.md",
    "ri-7_availability-of-foundational-model.md",
    "ri-8_tampering-with-the-foundational-model.md",
    "ri-9_data-poisoning.md",
    "ri-10_prompt-injection.md",
    "ri-14_inadequate-system-alignment.md",
    "ri-16_bias-and-discrimination.md",
    "ri-17_lack-of-explainability.md",
    "ri-18_model-overreach-expanded-use.md",
    "ri-19_data-quality-and-drift.md",
    "ri-20_reputational-risk.md",
    "ri-22_regulatory-compliance-and-oversight.md",
    "ri-23_intellectual-property-ip-and-copyright.md",
]


class DiscoveryCacheManager:
    """Manager for the discovery cache."""

    _instance: Optional["DiscoveryCacheManager"] = None

    def __new__(cls) -> "DiscoveryCacheManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the cache manager if not already initialized."""
        if not hasattr(self, "_discovery_cache"):
            self._discovery_cache: tuple[list[str], list[str], str] | None = None
            self._discovery_cache_timestamp: float | None = None

    async def get_file_lists(self) -> tuple[list[str], list[str], str]:
        """Get current file lists using dynamic discovery with caching."""
        # Cache for 5 minutes to avoid repeated API calls during the same session
        current_time = time.time()
        if (
            self._discovery_cache is not None
            and self._discovery_cache_timestamp is not None
            and current_time - self._discovery_cache_timestamp < 300
        ):  # 5 minutes
            return self._discovery_cache

        try:
            # Discover content dynamically
            discovery_result = await discover_content()

            mitigation_files = [f.filename for f in discovery_result.mitigation_files]
            risk_files = [f.filename for f in discovery_result.risk_files]

            self._discovery_cache = (
                mitigation_files,
                risk_files,
                discovery_result.source,
            )
            self._discovery_cache_timestamp = current_time

            logger.info(
                "File lists updated via dynamic discovery",
                extra={
                    "source": discovery_result.source,
                    "mitigation_count": len(mitigation_files),
                    "risk_count": len(risk_files),
                    "cache_expires": (
                        discovery_result.cache_expires.isoformat()
                        if discovery_result.cache_expires
                        else None
                    ),
                },
            )

            return self._discovery_cache

        except (
            httpx.HTTPError,
            httpx.TimeoutException,
            asyncio.TimeoutError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
        ) as e:
            logger.warning(
                "Failed to discover content, using static fallback",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            # Fallback to static lists if discovery fails completely
            return (MITIGATION_FILES, RISK_FILES, "static_fallback")


# Global discovery cache manager instance
_discovery_cache_manager = DiscoveryCacheManager()


async def get_file_lists() -> tuple[list[str], list[str], str]:
    """Get current file lists using dynamic discovery with caching."""
    return await _discovery_cache_manager.get_file_lists()


async def get_mitigation_files() -> list[str]:
    """Get current list of mitigation files."""
    mitigation_files, _, _ = await get_file_lists()
    return mitigation_files


async def get_risk_files() -> list[str]:
    """Get current list of risk files."""
    _, risk_files, _ = await get_file_lists()
    return risk_files


class SearchMitigationsRequest(BaseModel):
    """Request model for searching mitigations."""

    query: str = Field(
        ..., description="Search term or keyword to find relevant mitigations"
    )
    exact_match: bool = Field(
        default=False, description="Whether to use exact matching"
    )


class SearchRisksRequest(BaseModel):
    """Request model for searching risks."""

    query: str = Field(..., description="Search term or keyword to find relevant risks")
    exact_match: bool = Field(
        default=False, description="Whether to use exact matching"
    )


# Tool definitions
SEARCH_TOOLS: list[Tool] = [
    Tool(
        name="search_mitigations",
        description="Search through AI governance mitigations by keyword or topic",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term or keyword to find relevant mitigations",
                },
                "exact_match": {
                    "type": "boolean",
                    "description": "Whether to use exact matching (default: false)",
                    "default": False,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="search_risks",
        description="Search through AI governance risks by keyword or topic",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term or keyword to find relevant risks",
                },
                "exact_match": {
                    "type": "boolean",
                    "description": "Whether to use exact matching (default: false)",
                    "default": False,
                },
            },
            "required": ["query"],
        },
    ),
]


async def _search_documents(
    doc_type: str, file_list: list[str], query: str, exact_match: bool = False
) -> list[dict[str, Any]]:
    """Search through documents for matching content.

    Args:
        doc_type: Type of document ('mitigation' or 'risk')
        file_list: List of filenames to search
        query: Search query
        exact_match: Whether to use exact matching

    Returns:
        List of matching document summaries

    """
    query_lower = query.lower()
    results = []

    service = await get_content_service()

    for filename in file_list:
        doc_data = await service.get_document(doc_type, filename)
        if not doc_data:
            logger.warning("Failed to fetch %s: %s", doc_type, filename)
            continue

        # Search in title, content, and metadata
        searchable_text = (
            doc_data["metadata"].get("title", "")
            + " "
            + doc_data["content"]
            + " "
            + str(doc_data["metadata"])
        ).lower()

        # Check if query matches
        is_match = False
        if exact_match:
            is_match = query_lower in searchable_text
        else:
            # Split query into terms and check if any term matches
            query_terms = query_lower.split()
            is_match = any(term in searchable_text for term in query_terms)

        if is_match:
            result = {
                "filename": filename,
                "title": doc_data["metadata"].get("title", ""),
                "sequence": doc_data["metadata"].get("sequence", ""),
                "type": doc_data["metadata"].get("type", ""),
            }

            # Add type-specific fields
            if doc_type == "mitigation":
                result["mitigates"] = doc_data["metadata"].get("mitigates", [])
            elif doc_type == "risk":
                result["related_risks"] = doc_data["metadata"].get("related_risks", [])

            results.append(result)

    logger.info(
        "Search completed: %s %ss found",
        len(results),
        doc_type,
        extra={
            "search_query": query,
            "exact_match": exact_match,
            "doc_type": doc_type,
            "results_count": len(results),
        },
    )

    return results


async def handle_search_tools(
    name: str, arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle search tool calls.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        Search results as TextContent

    """
    logger.debug(
        "Handling search tool: %s",
        name,
        extra={"tool_name": name, "arguments": arguments},
    )

    if name == "search_mitigations":
        try:
            # Validate input using Pydantic first
            request = SearchMitigationsRequest(**arguments)

            # Additional security validation
            validate_search_request(request.query, request.exact_match)

            logger.info(
                "Processing mitigation search request",
                extra={
                    "query": request.query,
                    "exact_match": request.exact_match,
                },
            )

            mitigation_files = await get_mitigation_files()
            results = await _search_documents(
                "mitigation",
                mitigation_files,
                request.query,
                request.exact_match,
            )
            return [TextContent(type="text", text=json.dumps(results, indent=2))]

        except ValidationError as e:
            logger.warning("Search validation failed: %s", e.message)
            error_response = {
                "error": "Invalid search request",
                "message": e.message,
                "suggestions": _get_search_suggestions(),
            }
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

    elif name == "search_risks":
        try:
            # Validate input using Pydantic first
            risk_request = SearchRisksRequest(**arguments)

            # Additional security validation
            validate_search_request(risk_request.query, risk_request.exact_match)

            logger.info(
                "Processing risk search request",
                extra={
                    "query": risk_request.query,
                    "exact_match": risk_request.exact_match,
                },
            )

            risk_files = await get_risk_files()
            results = await _search_documents(
                "risk", risk_files, risk_request.query, risk_request.exact_match
            )
            return [TextContent(type="text", text=json.dumps(results, indent=2))]

        except ValidationError as e:
            logger.warning("Search validation failed: %s", e.message)
            error_response = {
                "error": "Invalid search request",
                "message": e.message,
                "suggestions": _get_search_suggestions(),
            }
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

    else:
        raise ValueError(f"Unknown search tool: {name}")


def _get_search_suggestions() -> list[str]:
    """Get helpful search suggestions for users."""
    return [
        "Try shorter, more specific search terms",
        "Use single words or simple phrases",
        "Example queries: 'data leakage', 'ai governance', 'prompt injection'",
        "Search terms should be 1-500 characters long",
        "Avoid special characters and script tags",
    ]
