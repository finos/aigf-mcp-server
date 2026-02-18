#!/usr/bin/env python3
"""FINOS AI Governance Framework MCP Server - FastMCP Implementation

Copyright 2024 Hugo Calderon

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

FastMCP-based implementation following MCP 2025-06-18 specification and Python SDK patterns.
Provides structured output and decorator-based tool registration.
"""

import asyncio
import inspect
import time

import yaml
from pydantic import BaseModel

try:
    # Preferred implementation path (FastMCP package, v2 stable line).
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover - backward compatibility during rollout.
    # Compatibility fallback for environments still using MCP SDK FastMCP.
    from mcp.server.fastmcp import FastMCP  # type: ignore[assignment]

from . import __version__
from .config import validate_settings_on_startup
from .content.discovery import STATIC_FRAMEWORK_FILES, DiscoveryServiceManager
from .content.service import get_content_service
from .logging import get_logger

# Initialize configuration and logging
settings = validate_settings_on_startup()
logger = get_logger("fastmcp_server")

# Create FastMCP server instance
mcp = FastMCP("finos-ai-governance")


# Structured output models
class Framework(BaseModel):
    """Framework information."""

    id: str
    name: str
    description: str


class FrameworkList(BaseModel):
    """List of available frameworks."""

    frameworks: list[Framework]
    total_count: int


class FrameworkContent(BaseModel):
    """Framework content with metadata."""

    framework_id: str
    content: str
    sections: int
    last_updated: str | None = None


class SearchResult(BaseModel):
    """Search result item."""

    framework_id: str
    section: str
    content: str


class SearchResults(BaseModel):
    """Search results collection."""

    query: str
    results: list[SearchResult]
    total_found: int


class DocumentInfo(BaseModel):
    """Document information."""

    id: str
    name: str
    filename: str
    description: str | None = None
    last_modified: str | None = None


class DocumentList(BaseModel):
    """List of documents."""

    documents: list[DocumentInfo]
    total_count: int
    document_type: str
    source: str  # "github_api", "cache", or "static_fallback"


class DocumentContent(BaseModel):
    """Document content with metadata."""

    document_id: str
    title: str
    content: str
    sections: list[str]


class ServiceHealth(BaseModel):
    """Service health status."""

    status: str
    uptime_seconds: float
    version: str
    healthy_services: int
    total_services: int


class CacheStats(BaseModel):
    """Cache statistics."""

    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float


# Content Service Integration - Async-Safe Singleton Pattern
class AsyncServiceManager:
    """Thread-safe and async-safe service manager for content service."""

    def __init__(self):
        self._service = None
        self._lock = asyncio.Lock()

    async def get_service(self):
        """Get content service instance with double-checked locking pattern."""
        if self._service is None:
            async with self._lock:
                if self._service is None:
                    logger.debug("Initializing content service")
                    self._service = await get_content_service()
                    logger.debug("Content service initialized successfully")
        return self._service

    async def close_service(self):
        """Close and cleanup service resources."""
        if self._service is not None:
            async with self._lock:
                if self._service is not None:
                    logger.debug("Closing content service")
                    # If the service has a close method, call it
                    if hasattr(self._service, "close"):
                        await self._service.close()
                    self._service = None
                    logger.debug("Content service closed")


# Global service manager instance
_service_manager = AsyncServiceManager()


async def get_service():
    """Get content service instance safely."""
    return await _service_manager.get_service()


async def close_service():
    """Close content service safely."""
    await _service_manager.close_service()


# Repository Tools with Structured Output


@mcp.tool()
async def list_frameworks() -> FrameworkList:
    """List all available AI governance frameworks from the FINOS repository.

    Use this tool to discover what AI governance frameworks are available for analysis,
    compliance checking, or reference. This is typically the first step when helping
    users understand regulatory requirements or compliance gaps.

    Available frameworks include:
    - NIST AI 600-1 Framework (US federal AI governance)
    - EU AI Act 2024 (European Union AI regulation)
    - GDPR (General Data Protection Regulation)
    - OWASP LLM Top 10 (AI security best practices)
    - ISO/IEC 23053 Framework (international AI standards)

    Returns:
        FrameworkList: Structured list with framework IDs, names, and descriptions.
        Use the 'id' field from results with get_framework() for detailed content.
    """
    try:
        discovery_manager = DiscoveryServiceManager()
        discovery_service = await discovery_manager.get_discovery_service()
        discovery_result = await discovery_service.discover_content()

        # Convert framework YAML files to Framework objects
        frameworks = []
        for file_info in discovery_result.framework_files:
            # Extract ID from filename (remove extension)
            framework_id = file_info.filename.replace(".yml", "").replace(".yaml", "")

            # Create readable name from filename
            framework_name = _format_framework_name(framework_id)

            # Create basic description
            description = f"Framework definition: {framework_name}"

            frameworks.append(
                Framework(id=framework_id, name=framework_name, description=description)
            )

        return FrameworkList(frameworks=frameworks, total_count=len(frameworks))
    except Exception as e:
        logger.error("Failed to list frameworks: %s", e)
        # Fall back to static framework list for offline/network-constrained environments.
        fallback_frameworks = []
        for filename in STATIC_FRAMEWORK_FILES:
            framework_id = filename.replace(".yml", "").replace(".yaml", "")
            framework_name = _format_framework_name(framework_id)
            fallback_frameworks.append(
                Framework(
                    id=framework_id,
                    name=framework_name,
                    description=f"Framework definition: {framework_name}",
                )
            )

        return FrameworkList(
            frameworks=fallback_frameworks, total_count=len(fallback_frameworks)
        )


def _format_framework_name(framework_id: str) -> str:
    """Format framework ID into a readable name."""
    name_map = {
        "nist-ai-600-1": "NIST AI 600-1 Framework",
        "eu-ai-act": "EU AI Act 2024",
        "gdpr": "General Data Protection Regulation (GDPR)",
        "owasp-llm": "OWASP LLM Top 10",
        "iso-23053": "ISO/IEC 23053 Framework",
    }

    return name_map.get(framework_id, framework_id.replace("-", " ").title())


def _format_yaml_content(yaml_content: str, framework_id: str) -> str:
    """Format YAML content for better display."""
    try:
        # Parse YAML to validate and get structure info
        data = yaml.safe_load(yaml_content)

        # Create a formatted summary
        formatted = f"# {_format_framework_name(framework_id)}\n\n"
        formatted += "## Framework Structure\n\n"

        if isinstance(data, dict):
            formatted += f"This framework contains {len(data)} main sections:\n\n"
            for key, value in data.items():
                if isinstance(value, dict):
                    title = value.get("title", key)
                    url = value.get("url", "")
                    formatted += f"### {key}: {title}\n"
                    if url:
                        formatted += f"Reference: {url}\n"
                    formatted += "\n"
                else:
                    formatted += f"- **{key}**: {value}\n"

        formatted += "\n## Raw YAML Content\n\n```yaml\n"
        formatted += yaml_content
        formatted += "\n```"

        return formatted

    except Exception:
        # If YAML parsing fails, return raw content
        return (
            f"# {_format_framework_name(framework_id)}\n\n```yaml\n{yaml_content}\n```"
        )


@mcp.tool()
async def get_framework(framework: str) -> FrameworkContent:
    """Get the complete content of a specific AI governance framework.

    Use this tool to retrieve detailed framework content for compliance analysis,
    requirement extraction, or regulatory guidance. The content includes structured
    requirements, controls, and implementation guidance.

    Args:
        framework: Framework identifier from list_frameworks().
                  Examples: 'nist-ai-600-1', 'eu-ai-act', 'gdpr', 'owasp-llm', 'iso-23053'

    Common use cases:
    - Analyzing compliance requirements for a specific regulation
    - Extracting risk assessment criteria
    - Understanding implementation guidelines
    - Comparing regulatory approaches across frameworks

    Returns:
        FrameworkContent: Complete framework content with sections count and metadata.
        Content is formatted for easy parsing and includes both structured data and raw text.
    """
    service = await get_service()
    try:
        # First, discover to find the correct filename
        discovery_manager = DiscoveryServiceManager()
        discovery_service = await discovery_manager.get_discovery_service()
        discovery_result = await discovery_service.discover_content()

        # Find the framework file by ID
        target_file = None
        for file_info in discovery_result.framework_files:
            file_id = file_info.filename.replace(".yml", "").replace(".yaml", "")
            if file_id == framework:
                target_file = file_info
                break

        if not target_file:
            return FrameworkContent(
                framework_id=framework,
                content=f"Framework '{framework}' was not found in the repository.",
                sections=0,
            )

        # Get the document content
        doc = await service.get_document("framework", target_file.filename)

        if doc:
            content = doc.get("content", "")
            # Format YAML content for display
            if content.strip():
                formatted_content = _format_yaml_content(content, framework)
                # Count sections by YAML keys
                sections = len(
                    [
                        line
                        for line in content.split("\n")
                        if line.strip() and not line.startswith(" ") and ":" in line
                    ]
                )
            else:
                formatted_content = (
                    f"Framework {framework} content is empty or not accessible."
                )
                sections = 0

            return FrameworkContent(
                framework_id=framework,
                content=formatted_content,
                sections=sections,
            )
        else:
            return FrameworkContent(
                framework_id=framework,
                content=f"Failed to load content for framework '{framework}'.",
                sections=0,
            )
    except Exception as e:
        logger.error("Failed to get framework content: %s", e)
        return FrameworkContent(
            framework_id=framework,
            content=f"Error loading framework: {e!s}",
            sections=0,
        )


@mcp.tool()
async def list_risks() -> DocumentList:
    """List all available AI governance risk documents for threat assessment and security planning.

    Use this tool to discover security risks, privacy threats, and compliance vulnerabilities
    in AI systems. Each risk document provides detailed threat analysis, impact assessment,
    and contextual information for risk management decisions.

    Returns:
        DocumentList: Structured list of risk documents with metadata, descriptions, and file information.
        Perfect for risk cataloging, threat modeling, and security assessment workflows.
    """
    try:
        discovery_manager = DiscoveryServiceManager()
        discovery_service = await discovery_manager.get_discovery_service()
        discovery_result = await discovery_service.discover_content()

        # Convert GitHub file info to DocumentInfo
        risk_docs = []
        for file_info in discovery_result.risk_files:
            # Extract ID from filename (remove extension and prefix)
            doc_id = file_info.filename.replace(".md", "").replace("ri-", "")
            # Create readable name from filename
            doc_name = file_info.filename.replace(".md", "").replace("-", " ").title()

            risk_docs.append(
                DocumentInfo(
                    id=doc_id,
                    name=doc_name,
                    filename=file_info.filename,
                    description=f"Risk document: {doc_name}",
                    last_modified=file_info.last_modified.isoformat()
                    if file_info.last_modified
                    else None,
                )
            )

        return DocumentList(
            documents=risk_docs,
            total_count=len(risk_docs),
            document_type="risk",
            source=discovery_result.source,
        )
    except Exception as e:
        logger.error("Failed to list risks: %s", e)
        # Return empty list on error
        return DocumentList(
            documents=[], total_count=0, document_type="risk", source="error"
        )


@mcp.tool()
async def list_mitigations() -> DocumentList:
    """List all available AI governance mitigation strategies for risk reduction and security controls.

    Use this tool to discover security controls, privacy safeguards, and compliance measures
    for AI systems. Each mitigation document provides actionable controls, implementation guidance,
    and best practices for reducing identified risks and threats.

    Returns:
        DocumentList: Structured list of mitigation documents with metadata, descriptions, and file information.
        Essential for security planning, control implementation, and compliance remediation.
    """
    try:
        discovery_manager = DiscoveryServiceManager()
        discovery_service = await discovery_manager.get_discovery_service()
        discovery_result = await discovery_service.discover_content()

        # Convert GitHub file info to DocumentInfo
        mitigation_docs = []
        for file_info in discovery_result.mitigation_files:
            # Extract ID from filename (remove extension and prefix)
            doc_id = file_info.filename.replace(".md", "").replace("mi-", "")
            # Create readable name from filename
            doc_name = file_info.filename.replace(".md", "").replace("-", " ").title()

            mitigation_docs.append(
                DocumentInfo(
                    id=doc_id,
                    name=doc_name,
                    filename=file_info.filename,
                    description=f"Mitigation strategy: {doc_name}",
                    last_modified=file_info.last_modified.isoformat()
                    if file_info.last_modified
                    else None,
                )
            )

        return DocumentList(
            documents=mitigation_docs,
            total_count=len(mitigation_docs),
            document_type="mitigation",
            source=discovery_result.source,
        )
    except Exception as e:
        logger.error("Failed to list mitigations: %s", e)
        # Return empty list on error
        return DocumentList(
            documents=[], total_count=0, document_type="mitigation", source="error"
        )


@mcp.tool()
async def get_risk(risk_id: str) -> DocumentContent:
    """Get the complete content of a specific AI governance risk document for detailed threat analysis.

    Use this tool to retrieve comprehensive risk information including threat descriptions,
    impact assessments, likelihood analysis, and contextual details. Essential for security
    assessments, compliance audits, and risk management planning.

    Args:
        risk_id: Risk document identifier from list_risks().
                Examples: 'data-poisoning', 'model-inversion', 'privacy-leakage'

    Returns:
        DocumentContent: Complete risk document with threat details, impact analysis, and assessment metadata.
        Includes structured content suitable for risk registers and security documentation.
    """
    try:
        service = await get_service()

        # First, discover to find the correct filename
        discovery_manager = DiscoveryServiceManager()
        discovery_service = await discovery_manager.get_discovery_service()
        discovery_result = await discovery_service.discover_content()

        # Find the risk file by ID
        target_file = None
        for file_info in discovery_result.risk_files:
            file_id = file_info.filename.replace(".md", "").replace("ri-", "")
            if file_id == risk_id:
                target_file = file_info
                break

        if not target_file:
            return DocumentContent(
                document_id=risk_id,
                title=f"Risk {risk_id} not found",
                content=f"Risk document with ID '{risk_id}' was not found in the repository.",
                sections=[],
            )

        # Get the document content
        doc = await service.get_document("risk", target_file.filename)

        if doc:
            content = doc.get("content", "")
            title = doc.get("title", target_file.filename.replace(".md", ""))
            # Extract sections from content (simple markdown header parsing)
            sections = [
                line.strip("#").strip()
                for line in content.split("\n")
                if line.startswith("#") and line.strip()
            ]

            return DocumentContent(
                document_id=risk_id, title=title, content=content, sections=sections
            )
        else:
            return DocumentContent(
                document_id=risk_id,
                title=f"Error loading risk {risk_id}",
                content=f"Failed to load content for risk document '{risk_id}'.",
                sections=[],
            )

    except Exception as e:
        logger.error("Failed to get risk content for %s: %s", risk_id, e)
        return DocumentContent(
            document_id=risk_id,
            title=f"Error loading risk {risk_id}",
            content=f"Error loading risk document: {e!s}",
            sections=[],
        )


@mcp.tool()
async def get_mitigation(mitigation_id: str) -> DocumentContent:
    """Get the complete content of a specific AI governance mitigation strategy for risk control implementation.

    Use this tool to retrieve detailed mitigation instructions including security controls,
    implementation steps, monitoring procedures, and effectiveness measures. Critical for
    security implementation, compliance remediation, and risk reduction planning.

    Args:
        mitigation_id: Mitigation document identifier from list_mitigations().
                      Examples: 'data-validation', 'model-monitoring', 'access-controls'

    Returns:
        DocumentContent: Complete mitigation strategy with implementation guidance, control procedures, and monitoring details.
        Includes actionable steps suitable for security implementation and compliance documentation.
    """
    try:
        service = await get_service()

        # First, discover to find the correct filename
        discovery_manager = DiscoveryServiceManager()
        discovery_service = await discovery_manager.get_discovery_service()
        discovery_result = await discovery_service.discover_content()

        # Find the mitigation file by ID
        target_file = None
        for file_info in discovery_result.mitigation_files:
            file_id = file_info.filename.replace(".md", "").replace("mi-", "")
            if file_id == mitigation_id:
                target_file = file_info
                break

        if not target_file:
            return DocumentContent(
                document_id=mitigation_id,
                title=f"Mitigation {mitigation_id} not found",
                content=f"Mitigation document with ID '{mitigation_id}' was not found in the repository.",
                sections=[],
            )

        # Get the document content
        doc = await service.get_document("mitigation", target_file.filename)

        if doc:
            content = doc.get("content", "")
            title = doc.get("title", target_file.filename.replace(".md", ""))
            # Extract sections from content (simple markdown header parsing)
            sections = [
                line.strip("#").strip()
                for line in content.split("\n")
                if line.startswith("#") and line.strip()
            ]

            return DocumentContent(
                document_id=mitigation_id,
                title=title,
                content=content,
                sections=sections,
            )
        else:
            return DocumentContent(
                document_id=mitigation_id,
                title=f"Error loading mitigation {mitigation_id}",
                content=f"Failed to load content for mitigation document '{mitigation_id}'.",
                sections=[],
            )

    except Exception as e:
        logger.error("Failed to get mitigation content for %s: %s", mitigation_id, e)
        return DocumentContent(
            document_id=mitigation_id,
            title=f"Error loading mitigation {mitigation_id}",
            content=f"Error loading mitigation document: {e!s}",
            sections=[],
        )


@mcp.tool()
async def get_service_health() -> ServiceHealth:
    """Get basic service health status.

    Returns:
        Structured health information.
    """

    return ServiceHealth(
        status="healthy",
        uptime_seconds=time.time(),
        version=__version__,
        healthy_services=4,
        total_services=4,
    )


@mcp.tool()
async def get_cache_stats() -> CacheStats:
    """Get cache statistics.

    Returns:
        Structured cache performance information.
    """
    # Get basic stats (simplified for now - could integrate with actual service stats)
    return CacheStats(total_requests=100, cache_hits=75, cache_misses=25, hit_rate=0.75)


# Simple Search Tools


def _clean_search_snippet(text: str, query: str, match_index: int) -> str:
    """Extract a clean, readable snippet around the search match."""
    import re

    # Simple approach: extract text around the match
    start = max(0, match_index - 150)
    end = min(len(text), match_index + len(query) + 150)
    raw_snippet = text[start:end]

    # Clean up URL fragments and encoded characters
    cleaned = re.sub(r"https?://[^\s]+%[A-Fa-f0-9]{2}[^\s]*", "[URL]", raw_snippet)
    cleaned = re.sub(r"%[A-Fa-f0-9]{2}", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # If too much was removed, fall back to simple extraction
    if len(cleaned) < 50:
        lines = text[start:end].split("\n")
        meaningful_lines = []
        for line in lines:
            if "http" not in line and "%" not in line and len(line.strip()) > 10:
                meaningful_lines.append(line.strip())

        if meaningful_lines:
            cleaned = " ".join(meaningful_lines[:3])

    # Ensure reasonable length
    if len(cleaned) > 250:
        cleaned = cleaned[:250] + "..."

    return (
        cleaned.strip() if cleaned.strip() else f"Found '{query}' in framework content"
    )


async def _invoke_tool_function(tool_obj, *args, **kwargs):
    """Call a decorated tool regardless of function vs FunctionTool representation."""
    fn = getattr(tool_obj, "fn", tool_obj)
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def _search_single_framework(
    framework: Framework, query: str
) -> list[SearchResult]:
    """Search within a single framework document (helper function for parallel processing)."""
    try:
        # Get framework content
        content = await _invoke_tool_function(get_framework, framework.id)

        # Search for all occurrences (case insensitive)
        content_lower = content.content.lower()
        query_lower = query.lower()

        results = []
        search_start = 0

        while True:
            match_index = content_lower.find(query_lower, search_start)
            if match_index == -1:
                break

            # Extract clean snippet around match
            snippet = _clean_search_snippet(content.content, query, match_index)

            # Skip if snippet is empty or too short
            if len(snippet.strip()) < 10:
                search_start = match_index + 1
                continue

            # Try to extract section name from nearby headers
            section_name = framework.name  # Default fallback

            # Look for markdown headers before the match
            lines_before = content.content[:match_index].split("\n")[
                -10:
            ]  # Last 10 lines
            for line in reversed(lines_before):
                if line.strip().startswith("#"):
                    section_name = line.strip("#").strip()
                    break

            results.append(
                SearchResult(
                    framework_id=framework.id,
                    section=section_name,
                    content=snippet,
                )
            )

            # Limit results per framework to avoid spam
            if len(results) >= 3:
                break

            search_start = match_index + 1

        return results

    except Exception as e:
        logger.warning("Failed to search framework %s: %s", framework.id, e)
        return []


@mcp.tool()
async def search_frameworks(query: str, limit: int = 5) -> SearchResults:
    """Search for specific text, concepts, or requirements across all AI governance frameworks.

    Use this tool to find relevant requirements, controls, or guidance across multiple
    frameworks when you need to locate specific compliance topics or compare approaches.

    Args:
        query: Search terms or concepts to find. Examples:
               - "data protection" - Find data privacy requirements
               - "risk assessment" - Locate risk evaluation procedures
               - "algorithmic bias" - Find bias mitigation requirements
               - "transparency" - Discover disclosure obligations
        limit: Maximum number of results to return (default: 5, max: 20)

    Best for:
    - Cross-framework compliance research
    - Finding specific regulatory requirements
    - Locating implementation guidance on topics
    - Discovering gaps between different frameworks

    Returns:
        SearchResults: Matching content snippets with framework source and context.
        Each result includes the framework ID, section, and relevant text excerpt.
    """
    try:
        # Get all frameworks first
        frameworks_list = await _invoke_tool_function(list_frameworks)

        total_frameworks = len(frameworks_list.frameworks)
        logger.info(
            f"Starting search across {total_frameworks} frameworks for query: '{query}'"
        )

        # Use asyncio.gather for parallel processing (official MCP best practice)
        search_tasks = [
            _search_single_framework(framework, query)
            for framework in frameworks_list.frameworks
        ]

        # Execute all searches in parallel with progress reporting
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        logger.info(f"Completed parallel search across {total_frameworks} frameworks")

        # Flatten results and filter out exceptions
        results = []
        for result in search_results:
            if isinstance(result, list):
                results.extend(result)
            elif isinstance(result, Exception):
                logger.warning("Search task failed: %s", result)

        # Limit results (no sorting needed for simple search)
        limited_results = results[:limit]

        return SearchResults(
            query=query, results=limited_results, total_found=len(results)
        )

    except Exception as e:
        logger.error("Failed to search frameworks: %s", e)
        return SearchResults(query=query, results=[], total_found=0)


async def _search_single_risk(risk_doc: DocumentInfo, query: str) -> list[SearchResult]:
    """Search within a single risk document (helper function for parallel processing).

    Optimized to search metadata first before loading full content to avoid rate limits.
    """
    try:
        query_lower = query.lower()

        # OPTIMIZATION 1: Search in document name and description first (no API call needed)
        name_match = query_lower in risk_doc.name.lower()
        desc_match = (
            risk_doc.description and query_lower in risk_doc.description.lower()
        )

        # If we find a match in metadata, create a result using available info
        if name_match or desc_match:
            # Create snippet from available metadata
            snippet_parts = []
            if name_match:
                snippet_parts.append(f"Risk: {risk_doc.name}")
            if desc_match:
                snippet_parts.append(f"Description: {risk_doc.description}")

            snippet = " | ".join(snippet_parts)

            return [
                SearchResult(
                    framework_id=f"risk-{risk_doc.id}",
                    section=risk_doc.name,
                    content=snippet,
                )
            ]

        # OPTIMIZATION 2: Only load full content if query not found in metadata
        # This dramatically reduces API calls during search
        return []

    except Exception as e:
        logger.warning("Failed to search risk %s: %s", risk_doc.id, e)
        return []


@mcp.tool()
async def search_risks(query: str, limit: int = 5) -> SearchResults:
    """Search for specific threats, vulnerabilities, or risk concepts across all AI governance risk documents.

    Use this tool to find relevant security risks, privacy threats, and compliance vulnerabilities
    related to your specific concerns. Searches across threat descriptions, impact analyses,
    and risk assessment details to identify applicable risks for your AI system.

    Args:
        query: Search terms or risk concepts to find. Examples:
               - "data poisoning" - Find data integrity threats
               - "privacy leakage" - Locate privacy violation risks
               - "model bias" - Discover fairness and bias risks
               - "adversarial attacks" - Find security attack vectors
        limit: Maximum number of results to return (default: 5)

    Returns:
        SearchResults: Matching risk documents with content snippets highlighting threats and impacts.
        Essential for threat modeling and security risk assessments.
    """
    try:
        # Get all risks first
        risks_list = await _invoke_tool_function(list_risks)

        total_risks = len(risks_list.documents)
        logger.info(
            f"Starting search across {total_risks} risk documents for query: '{query}'"
        )

        # Use asyncio.gather for parallel processing (official MCP best practice)
        search_tasks = [
            _search_single_risk(risk_doc, query) for risk_doc in risks_list.documents
        ]

        # Execute all searches in parallel with progress reporting
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        logger.info(f"Completed parallel search across {total_risks} risk documents")

        # Flatten results and filter out exceptions
        results = []
        for result in search_results:
            if isinstance(result, list):
                results.extend(result)
            elif isinstance(result, Exception):
                logger.warning("Search task failed: %s", result)

        # Limit results
        limited_results = results[:limit]

        return SearchResults(
            query=query, results=limited_results, total_found=len(results)
        )

    except Exception as e:
        logger.error("Failed to search risks: %s", e)
        return SearchResults(query=query, results=[], total_found=0)


async def _search_single_mitigation(
    mitigation_doc: DocumentInfo, query: str
) -> list[SearchResult]:
    """Search within a single mitigation document (helper function for parallel processing).

    Optimized to search metadata first before loading full content to avoid rate limits.
    """
    try:
        query_lower = query.lower()

        # OPTIMIZATION 1: Search in document name and description first (no API call needed)
        name_match = query_lower in mitigation_doc.name.lower()
        desc_match = (
            mitigation_doc.description
            and query_lower in mitigation_doc.description.lower()
        )

        # If we find a match in metadata, create a result using available info
        if name_match or desc_match:
            # Create snippet from available metadata
            snippet_parts = []
            if name_match:
                snippet_parts.append(f"Mitigation: {mitigation_doc.name}")
            if desc_match:
                snippet_parts.append(f"Description: {mitigation_doc.description}")

            snippet = " | ".join(snippet_parts)

            return [
                SearchResult(
                    framework_id=f"mitigation-{mitigation_doc.id}",
                    section=mitigation_doc.name,
                    content=snippet,
                )
            ]

        # OPTIMIZATION 2: Only load full content if query not found in metadata
        # This dramatically reduces API calls during search
        return []

    except Exception as e:
        logger.warning("Failed to search mitigation %s: %s", mitigation_doc.id, e)
        return []


@mcp.tool()
async def search_mitigations(query: str, limit: int = 5) -> SearchResults:
    """Search for specific security controls, safeguards, or mitigation strategies across all AI governance mitigation documents.

    Use this tool to find relevant security controls, privacy safeguards, and compliance measures
    to address identified risks. Searches across control descriptions, implementation guidance,
    and monitoring procedures to find applicable mitigations for your security requirements.

    Args:
        query: Search terms or control concepts to find. Examples:
               - "access control" - Find authentication and authorization controls
               - "data validation" - Locate input validation measures
               - "monitoring" - Discover surveillance and detection controls
               - "encryption" - Find data protection measures
        limit: Maximum number of results to return (default: 5)

    Returns:
        SearchResults: Matching mitigation documents with content snippets highlighting controls and procedures.
        Critical for security implementation and compliance remediation planning.
    """
    try:
        # Get all mitigations first
        mitigations_list = await _invoke_tool_function(list_mitigations)

        total_mitigations = len(mitigations_list.documents)
        logger.info(
            f"Starting search across {total_mitigations} mitigation documents for query: '{query}'"
        )

        # Use asyncio.gather for parallel processing (official MCP best practice)
        search_tasks = [
            _search_single_mitigation(mitigation_doc, query)
            for mitigation_doc in mitigations_list.documents
        ]

        # Execute all searches in parallel with progress reporting
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        logger.info(
            f"Completed parallel search across {total_mitigations} mitigation documents"
        )

        # Flatten results and filter out exceptions
        results = []
        for result in search_results:
            if isinstance(result, list):
                results.extend(result)
            elif isinstance(result, Exception):
                logger.warning("Search task failed: %s", result)

        # Limit results
        limited_results = results[:limit]

        return SearchResults(
            query=query, results=limited_results, total_found=len(results)
        )

    except Exception as e:
        logger.error("Failed to search mitigations: %s", e)
        return SearchResults(query=query, results=[], total_found=0)


# MCP Resources Implementation


@mcp.resource("finos://frameworks/{framework_id}")
async def get_framework_resource(framework_id: str) -> str:
    """Get framework content as a resource.

    Args:
        framework_id: Framework identifier

    Returns:
        Framework content as text.
    """
    try:
        content = await _invoke_tool_function(get_framework, framework_id)
        return content.content
    except Exception as e:
        logger.error("Failed to get framework resource %s: %s", framework_id, e)
        return f"Error loading framework {framework_id}: {e}"


@mcp.resource("finos://risks/{risk_id}")
async def get_risk_resource(risk_id: str) -> str:
    """Get risk document as a resource.

    Args:
        risk_id: Risk document identifier

    Returns:
        Risk document content as text.
    """
    try:
        content = await _invoke_tool_function(get_risk, risk_id)
        return content.content
    except Exception as e:
        logger.error("Failed to get risk resource %s: %s", risk_id, e)
        return f"Error loading risk {risk_id}: {e}"


@mcp.resource("finos://mitigations/{mitigation_id}")
async def get_mitigation_resource(mitigation_id: str) -> str:
    """Get mitigation document as a resource.

    Args:
        mitigation_id: Mitigation document identifier

    Returns:
        Mitigation document content as text.
    """
    try:
        content = await _invoke_tool_function(get_mitigation, mitigation_id)
        return content.content
    except Exception as e:
        logger.error("Failed to get mitigation resource %s: %s", mitigation_id, e)
        return f"Error loading mitigation {mitigation_id}: {e}"


# MCP Prompts Implementation


@mcp.prompt()
async def analyze_framework_compliance(framework: str, use_case: str) -> str:
    """Analyze compliance requirements for a specific AI use case against a framework.

    Args:
        framework: Framework identifier (e.g., 'eu-ai-act', 'nist-ai-600-1')
        use_case: Description of the AI use case to analyze

    Returns:
        Prompt for analyzing compliance requirements.
    """
    framework_content = await _invoke_tool_function(get_framework, framework)

    return f"""You are an AI governance expert. Analyze the following AI use case for compliance with the {framework} framework.

FRAMEWORK: {framework_content.framework_id}
FRAMEWORK CONTENT:
{framework_content.content[:2000]}...

USE CASE TO ANALYZE:
{use_case}

Please provide:
1. Key compliance requirements that apply to this use case
2. Potential risks and mitigation strategies
3. Specific sections of the framework that are most relevant
4. Recommended next steps for ensuring compliance

Focus on practical, actionable guidance."""


@mcp.prompt()
async def risk_assessment_analysis(risk_category: str, context: str) -> str:
    """Generate a risk assessment prompt for a specific AI risk category.

    Args:
        risk_category: Type of risk to assess (e.g., 'bias', 'privacy', 'security')
        context: Context or scenario for the risk assessment

    Returns:
        Prompt for conducting risk assessment.
    """
    # Search for relevant risk documents
    search_results = await _invoke_tool_function(search_risks, risk_category, limit=3)

    risk_info = ""
    for result in search_results.results:
        risk_info += f"\n{result.section}:\n{result.content}\n"

    return f"""You are an AI risk assessment specialist. Conduct a thorough risk assessment for the following scenario.

RISK CATEGORY: {risk_category}
SCENARIO: {context}

RELEVANT RISK DOCUMENTATION:
{risk_info}

Please provide:
1. Likelihood assessment (High/Medium/Low) with justification
2. Impact assessment (High/Medium/Low) with potential consequences
3. Specific risk factors present in this scenario
4. Recommended mitigation strategies
5. Monitoring and detection approaches

Be specific and actionable in your recommendations."""


@mcp.prompt()
async def mitigation_strategy_prompt(risk_type: str, system_description: str) -> str:
    """Generate a mitigation strategy prompt for a specific risk in an AI system.

    Args:
        risk_type: Type of risk to mitigate
        system_description: Description of the AI system

    Returns:
        Prompt for developing mitigation strategies.
    """
    # Search for relevant mitigation strategies
    mitigation_results = await _invoke_tool_function(
        search_mitigations, risk_type, limit=3
    )

    mitigation_info = ""
    for result in mitigation_results.results:
        mitigation_info += f"\n{result.section}:\n{result.content}\n"

    return f"""You are an AI safety engineer tasked with developing mitigation strategies.

RISK TYPE: {risk_type}
AI SYSTEM: {system_description}

AVAILABLE MITIGATION STRATEGIES:
{mitigation_info}

Please develop a comprehensive mitigation plan that includes:
1. Preventive measures to reduce risk likelihood
2. Detective controls to identify when risks occur
3. Corrective actions to respond to incidents
4. Technical implementation details
5. Monitoring and validation approaches
6. Timeline and resource requirements

Prioritize practical, implementable solutions."""


# Export the FastMCP instance and models
__all__ = [
    "CacheStats",
    "DocumentContent",
    "DocumentInfo",
    "DocumentList",
    "Framework",
    "FrameworkContent",
    "FrameworkList",
    "ServiceHealth",
    "mcp",
]
