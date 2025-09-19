"""
Framework Navigation Tools

MCP tools for navigating and searching governance framework data.
Provides comprehensive framework search, analysis, and compliance mapping capabilities.
"""

import logging
from typing import Any

from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

from ..frameworks.data_loader import FrameworkDataLoader
from ..frameworks.models import (
    ComplianceStatus,
    FrameworkQuery,
    FrameworkSearchResult,
    FrameworkType,
    SeverityLevel,
)
from ..frameworks.query_engine import FrameworkQueryEngine

logger = logging.getLogger(__name__)

# Global framework components (initialized on first use)
_framework_loader: FrameworkDataLoader = None
_query_engine: FrameworkQueryEngine = None


async def _ensure_framework_components():
    """Ensure framework components are initialized."""
    global _framework_loader, _query_engine

    if _framework_loader is None:
        logger.info("Initializing framework data loader...")
        _framework_loader = FrameworkDataLoader()

    if _query_engine is None:
        logger.info("Loading frameworks and initializing query engine...")
        frameworks = await _framework_loader.load_all_frameworks()
        _query_engine = FrameworkQueryEngine(frameworks)
        logger.info(f"Framework system ready: {len(frameworks)} frameworks loaded")


# Pydantic Models for Tool Input Validation

class SearchFrameworksInput(BaseModel):
    """Input parameters for framework search."""

    query: str = Field(..., description="Search query text", min_length=1, max_length=500)
    frameworks: list[FrameworkType] = Field(
        default_factory=list,
        description="Specific frameworks to search (empty = all frameworks)"
    )
    sections: list[str] = Field(
        default_factory=list,
        description="Framework sections to filter by"
    )
    severity: list[SeverityLevel] = Field(
        default_factory=list,
        description="Severity levels to filter by"
    )
    compliance_status: list[ComplianceStatus] = Field(
        default_factory=list,
        description="Compliance status to filter by"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags to filter by"
    )
    exact_match: bool = Field(
        default=False,
        description="Perform exact phrase matching"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results"
    )


class ListFrameworksInput(BaseModel):
    """Input parameters for listing frameworks."""

    include_stats: bool = Field(
        default=True,
        description="Include framework statistics"
    )
    active_only: bool = Field(
        default=True,
        description="Only list active frameworks"
    )


class GetFrameworkDetailsInput(BaseModel):
    """Input parameters for getting framework details."""

    framework_type: FrameworkType = Field(
        ...,
        description="Framework type to get details for"
    )
    include_references: bool = Field(
        default=True,
        description="Include reference details"
    )
    include_sections: bool = Field(
        default=True,
        description="Include section details"
    )


class GetComplianceAnalysisInput(BaseModel):
    """Input parameters for compliance analysis."""

    frameworks: list[FrameworkType] = Field(
        default_factory=list,
        description="Frameworks to analyze (empty = all frameworks)"
    )
    include_mappings: bool = Field(
        default=False,
        description="Include cross-framework mappings"
    )


class SearchFrameworkReferencesInput(BaseModel):
    """Input parameters for searching specific framework references."""

    query: str = Field(..., description="Search query", min_length=1)
    framework_type: FrameworkType = Field(
        ...,
        description="Specific framework to search"
    )
    section: str = Field(
        default="",
        description="Specific section to search within"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum results"
    )


# Tool Definitions

SEARCH_FRAMEWORKS_TOOL = Tool(
    name="search_frameworks",
    description="Search across all governance frameworks for specific requirements, controls, or topics. Supports filtering by framework type, severity, compliance status, and more.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query text",
                "minLength": 1,
                "maxLength": 500
            },
            "frameworks": {
                "type": "array",
                "items": {"type": "string", "enum": [ft.value for ft in FrameworkType]},
                "description": "Specific frameworks to search (leave empty for all)"
            },
            "sections": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Framework sections to filter by"
            },
            "severity": {
                "type": "array",
                "items": {"type": "string", "enum": [sl.value for sl in SeverityLevel]},
                "description": "Severity levels to filter by"
            },
            "compliance_status": {
                "type": "array",
                "items": {"type": "string", "enum": [cs.value for cs in ComplianceStatus]},
                "description": "Compliance status to filter by"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags to filter by"
            },
            "exact_match": {
                "type": "boolean",
                "description": "Perform exact phrase matching",
                "default": False
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum number of results",
                "default": 10
            }
        },
        "required": ["query"]
    }
)

LIST_FRAMEWORKS_TOOL = Tool(
    name="list_frameworks",
    description="List all available governance frameworks with their metadata and statistics.",
    inputSchema={
        "type": "object",
        "properties": {
            "include_stats": {
                "type": "boolean",
                "description": "Include framework statistics",
                "default": True
            },
            "active_only": {
                "type": "boolean",
                "description": "Only list active frameworks",
                "default": True
            }
        }
    }
)

GET_FRAMEWORK_DETAILS_TOOL = Tool(
    name="get_framework_details",
    description="Get detailed information about a specific governance framework including its structure, references, and compliance data.",
    inputSchema={
        "type": "object",
        "properties": {
            "framework_type": {
                "type": "string",
                "enum": [ft.value for ft in FrameworkType],
                "description": "Framework type to get details for"
            },
            "include_references": {
                "type": "boolean",
                "description": "Include reference details",
                "default": True
            },
            "include_sections": {
                "type": "boolean",
                "description": "Include section details",
                "default": True
            }
        },
        "required": ["framework_type"]
    }
)

GET_COMPLIANCE_ANALYSIS_TOOL = Tool(
    name="get_compliance_analysis",
    description="Get comprehensive compliance analysis across frameworks including coverage statistics and compliance gaps.",
    inputSchema={
        "type": "object",
        "properties": {
            "frameworks": {
                "type": "array",
                "items": {"type": "string", "enum": [ft.value for ft in FrameworkType]},
                "description": "Frameworks to analyze (leave empty for all)"
            },
            "include_mappings": {
                "type": "boolean",
                "description": "Include cross-framework mappings",
                "default": False
            }
        }
    }
)

SEARCH_FRAMEWORK_REFERENCES_TOOL = Tool(
    name="search_framework_references",
    description="Search for specific references within a particular governance framework. Useful for finding detailed requirements or controls.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
                "minLength": 1
            },
            "framework_type": {
                "type": "string",
                "enum": [ft.value for ft in FrameworkType],
                "description": "Specific framework to search"
            },
            "section": {
                "type": "string",
                "description": "Specific section to search within",
                "default": ""
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Maximum results",
                "default": 20
            }
        },
        "required": ["query", "framework_type"]
    }
)

# Framework Tools Collection
FRAMEWORK_TOOLS = [
    SEARCH_FRAMEWORKS_TOOL,
    LIST_FRAMEWORKS_TOOL,
    GET_FRAMEWORK_DETAILS_TOOL,
    GET_COMPLIANCE_ANALYSIS_TOOL,
    SEARCH_FRAMEWORK_REFERENCES_TOOL,
]


# Tool Handler Functions

async def handle_framework_tools(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle framework tool calls.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        Tool response content
    """
    try:
        await _ensure_framework_components()

        if name == "search_frameworks":
            return await _handle_search_frameworks(arguments)
        elif name == "list_frameworks":
            return await _handle_list_frameworks(arguments)
        elif name == "get_framework_details":
            return await _handle_get_framework_details(arguments)
        elif name == "get_compliance_analysis":
            return await _handle_get_compliance_analysis(arguments)
        elif name == "search_framework_references":
            return await _handle_search_framework_references(arguments)
        else:
            raise ValueError(f"Unknown framework tool: {name}")

    except Exception as e:
        logger.error(f"Framework tool error ({name}): {e}")
        return [TextContent(
            type="text",
            text=f"Framework tool error: {e!s}"
        )]


async def _handle_search_frameworks(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle framework search requests."""
    # Validate input
    input_data = SearchFrameworksInput(**arguments)

    # Build framework query
    query = FrameworkQuery(
        query_text=input_data.query,
        framework_types=input_data.frameworks,
        sections=input_data.sections,
        severity_levels=input_data.severity,
        compliance_status=input_data.compliance_status,
        tags=input_data.tags,
        exact_match=input_data.exact_match,
        limit=input_data.limit,
    )

    # Execute search
    result = await _query_engine.search(query)

    # Format response
    response_text = _format_search_result(result)

    return [TextContent(type="text", text=response_text)]


async def _handle_list_frameworks(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle list frameworks requests."""
    input_data = ListFrameworksInput(**arguments)

    frameworks = _query_engine.frameworks
    response_lines = ["# Available Governance Frameworks\n"]

    for framework_type, framework in frameworks.items():
        if not input_data.active_only or framework.is_active:
            response_lines.append(f"## {framework.name} ({framework_type.value})")
            response_lines.append(f"**Version:** {framework.version}")
            response_lines.append(f"**Publisher:** {framework.publisher}")

            if input_data.include_stats:
                response_lines.append(f"**References:** {framework.total_references}")
                response_lines.append(f"**Sections:** {len(framework.sections)}")
                response_lines.append(f"**Active References:** {framework.active_references}")

            if framework.description:
                response_lines.append(f"**Description:** {framework.description}")

            if framework.official_url:
                response_lines.append(f"**Official URL:** {framework.official_url}")

            response_lines.append("")

    return [TextContent(type="text", text="\n".join(response_lines))]


async def _handle_get_framework_details(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle framework details requests."""
    input_data = GetFrameworkDetailsInput(**arguments)

    framework = _query_engine.frameworks.get(input_data.framework_type)
    if not framework:
        return [TextContent(
            type="text",
            text=f"Framework not found: {input_data.framework_type}"
        )]

    response_lines = [f"# {framework.name} Details\n"]

    # Framework metadata
    response_lines.extend([
        f"**Type:** {framework.framework_type.value}",
        f"**Version:** {framework.version}",
        f"**Publisher:** {framework.publisher}",
        f"**Total References:** {framework.total_references}",
        f"**Active References:** {framework.active_references}",
        f"**Last Updated:** {framework.last_updated.strftime('%Y-%m-%d %H:%M:%S')}",
        ""
    ])

    if framework.description:
        response_lines.extend([f"**Description:** {framework.description}", ""])

    # Sections
    if input_data.include_sections and framework.sections:
        response_lines.append("## Framework Sections")
        for section in sorted(framework.sections, key=lambda s: s.order):
            response_lines.append(f"- **{section.title}** ({section.section_id})")
            if section.description:
                response_lines.append(f"  - {section.description}")
            response_lines.append(f"  - References: {section.reference_count}")
        response_lines.append("")

    # Sample references
    if input_data.include_references and framework.references:
        response_lines.append("## Sample References")
        sample_refs = framework.references[:5]  # Show first 5 references
        for ref in sample_refs:
            response_lines.extend([
                f"### {ref.title} ({ref.id})",
                f"**Section:** {ref.section}",
                f"**Severity:** {ref.severity.value}",
                f"**Compliance Status:** {ref.compliance_status.value}",
            ])
            if ref.description:
                response_lines.append(f"**Description:** {ref.description}")
            if ref.official_url:
                response_lines.append(f"**URL:** {ref.official_url}")
            response_lines.append("")

        if len(framework.references) > 5:
            response_lines.append(f"*... and {len(framework.references) - 5} more references*")

    return [TextContent(type="text", text="\n".join(response_lines))]


async def _handle_get_compliance_analysis(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle compliance analysis requests."""
    input_data = GetComplianceAnalysisInput(**arguments)

    analytics = await _query_engine.get_analytics()

    response_lines = ["# Compliance Analysis Report\n"]

    # Overall statistics
    response_lines.extend([
        f"**Total Frameworks:** {analytics.total_frameworks}",
        f"**Total References:** {analytics.total_references}",
        f"**Overall Compliance:** {analytics.compliance_percentage:.1f}%",
        ""
    ])

    # Framework-specific analysis
    target_frameworks = input_data.frameworks if input_data.frameworks else list(_query_engine.frameworks.keys())

    response_lines.append("## Framework Breakdown")
    for framework_type in target_frameworks:
        if framework_type in analytics.framework_stats:
            stats = analytics.framework_stats[framework_type]
            framework = _query_engine.frameworks[framework_type]

            response_lines.extend([
                f"### {framework.name}",
                f"- **References:** {stats['references']}",
                f"- **Active References:** {stats['active_references']}",
                f"- **Sections:** {stats['sections']}",
                ""
            ])

    # Compliance status distribution
    if analytics.compliance_coverage:
        response_lines.append("## Compliance Status Distribution")
        for status, count in analytics.compliance_coverage.items():
            percentage = (count / analytics.total_references) * 100
            response_lines.append(f"- **{status.value.title()}:** {count} ({percentage:.1f}%)")
        response_lines.append("")

    # Compliance gaps and recommendations
    non_compliant = analytics.compliance_coverage.get(ComplianceStatus.NON_COMPLIANT, 0)
    under_review = analytics.compliance_coverage.get(ComplianceStatus.UNDER_REVIEW, 0)

    if non_compliant > 0 or under_review > 0:
        response_lines.append("## Compliance Gaps")
        if non_compliant > 0:
            response_lines.append(f"- **{non_compliant} non-compliant references** require immediate attention")
        if under_review > 0:
            response_lines.append(f"- **{under_review} references under review** need compliance assessment")
        response_lines.append("")

    return [TextContent(type="text", text="\n".join(response_lines))]


async def _handle_search_framework_references(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle framework reference search requests."""
    input_data = SearchFrameworkReferencesInput(**arguments)

    # Build targeted query
    query = FrameworkQuery(
        query_text=input_data.query,
        framework_types=[input_data.framework_type],
        sections=[input_data.section] if input_data.section else [],
        limit=input_data.limit,
    )

    # Execute search
    result = await _query_engine.search(query)

    # Format response focusing on references
    framework = _query_engine.frameworks[input_data.framework_type]
    response_lines = [f"# {framework.name} Reference Search Results\n"]

    if result.total_results == 0:
        response_lines.append("No matching references found.")
    else:
        response_lines.append(f"Found {result.total_results} matching references:\n")

        for ref in result.references:
            response_lines.extend([
                f"## {ref.title} ({ref.id})",
                f"**Section:** {ref.section}",
                f"**Severity:** {ref.severity.value}",
                f"**Status:** {ref.compliance_status.value}",
            ])

            if ref.description:
                response_lines.append(f"**Description:** {ref.description}")

            if ref.official_url:
                response_lines.append(f"**URL:** {ref.official_url}")

            if ref.tags:
                response_lines.append(f"**Tags:** {', '.join(ref.tags)}")

            response_lines.append("")

        if result.has_more:
            response_lines.append(f"*Showing {result.returned_results} of {result.total_results} results*")

    return [TextContent(type="text", text="\n".join(response_lines))]


def _format_search_result(result: FrameworkSearchResult) -> str:
    """Format search result for display.

    Args:
        result: Search result to format

    Returns:
        Formatted result text
    """
    lines = ["# Framework Search Results\n"]

    # Search summary
    lines.append(f"**Query:** {result.query.query_text}")
    lines.append(f"**Results:** {result.total_results} found in {result.search_time_ms:.1f}ms")

    if result.cache_hit:
        lines.append("*(cached result)*")

    lines.append("")

    # Framework coverage
    if result.framework_coverage:
        lines.append("**Framework Coverage:**")
        for framework_type, count in result.framework_coverage.items():
            framework_name = _query_engine.frameworks[framework_type].name
            lines.append(f"- {framework_name}: {count} results")
        lines.append("")

    # Results
    if result.total_results == 0:
        lines.append("No matching results found.")
    else:
        # Show references
        if result.references:
            lines.append("## Matching References")
            for ref in result.references:
                framework_name = _query_engine.frameworks[ref.framework_type].name
                lines.extend([
                    f"### {ref.title}",
                    f"**Framework:** {framework_name}",
                    f"**Section:** {ref.section}",
                    f"**Severity:** {ref.severity.value}",
                    f"**Status:** {ref.compliance_status.value}",
                ])

                if ref.description:
                    lines.append(f"**Description:** {ref.description[:200]}...")

                if ref.official_url:
                    lines.append(f"**URL:** {ref.official_url}")

                lines.append("")

        # Show sections
        if result.sections:
            lines.append("## Matching Sections")
            for section in result.sections:
                framework_name = _query_engine.frameworks.get(section.framework_type, {}).name or "Unknown"
                lines.extend([
                    f"### {section.title}",
                    f"**Framework:** {framework_name}",
                    f"**References:** {section.reference_count}",
                ])

                if section.description:
                    lines.append(f"**Description:** {section.description}")

                lines.append("")

        # Pagination info
        if result.has_more:
            lines.append(f"*Showing {result.returned_results} of {result.total_results} results*")

    return "\n".join(lines)
