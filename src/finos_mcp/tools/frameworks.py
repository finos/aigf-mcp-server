"""
Framework Navigation Tools

MCP tools for navigating and searching governance framework data.
Provides comprehensive framework search, analysis, and compliance mapping capabilities.
"""

import logging
import re
from typing import Any

from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field, field_validator

from ..frameworks.data_loader import FrameworkDataLoader
from ..frameworks.mappings import get_framework_correlations
from ..frameworks.mappings.cross_reference import CrossFrameworkMapper, MappingStrength
from ..frameworks.models import (
    ComplianceStatus,
    ExportFilter,
    ExportFormat,
    ExportRequest,
    FrameworkQuery,
    FrameworkSearchResult,
    FrameworkType,
    SeverityLevel,
)
from ..frameworks.query_engine import FrameworkQueryEngine

logger = logging.getLogger(__name__)

# Global framework components (initialized on first use)
_framework_loader: FrameworkDataLoader | None = None
_query_engine: FrameworkQueryEngine | None = None
_cross_mapper: CrossFrameworkMapper | None = None
_correlations_service = None


async def _ensure_framework_components():
    """Ensure framework components are initialized."""
    global _framework_loader, _query_engine, _cross_mapper, _correlations_service

    if _framework_loader is None:
        logger.info("Initializing framework data loader...")
        _framework_loader = FrameworkDataLoader()

    if _query_engine is None:
        logger.info("Loading frameworks and initializing query engine...")
        frameworks = await _framework_loader.load_all_frameworks()
        _query_engine = FrameworkQueryEngine(frameworks)
        logger.info(f"Framework system ready: {len(frameworks)} frameworks loaded")

    if _cross_mapper is None:
        logger.info("Initializing cross-framework mapper...")
        _cross_mapper = CrossFrameworkMapper()

    if _correlations_service is None:
        logger.info("Initializing framework correlations service...")
        _correlations_service = get_framework_correlations()


def _ensure_query_engine() -> FrameworkQueryEngine:
    """Ensure query engine is initialized and return it."""
    if _query_engine is None:
        raise RuntimeError("Framework query engine not initialized")
    return _query_engine


def _ensure_cross_mapper() -> CrossFrameworkMapper:
    """Ensure cross-framework mapper is initialized and return it."""
    if _cross_mapper is None:
        raise RuntimeError("Cross-framework mapper not initialized")
    return _cross_mapper


def _ensure_correlations_service():
    """Ensure correlations service is initialized and return it."""
    if _correlations_service is None:
        raise RuntimeError("Correlations service not initialized")
    return _correlations_service


# Security Validation Utilities

def sanitize_search_query(query: str) -> str:
    """Sanitize search query to prevent injection attacks."""
    # Remove potentially dangerous patterns
    query = re.sub(r'[;\'"<>{}$`|&]', '', query)  # Remove injection chars
    query = re.sub(r'(drop|delete|insert|update|select|union|exec|script)', '', query, flags=re.IGNORECASE)
    query = re.sub(r'--.*$', '', query)  # Remove SQL comments
    query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)  # Remove block comments
    return query.strip()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks."""
    if not filename:
        return filename

    # Remove path traversal patterns
    filename = re.sub(r'\.\.', '', filename)
    filename = re.sub(r'[/\\:*?"<>|]', '', filename)
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)  # Control chars

    # Remove dangerous patterns
    filename = re.sub(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])', '', filename, flags=re.IGNORECASE)

    return filename.strip()


def validate_csv_delimiter(delimiter: str) -> bool:
    """Validate CSV delimiter for security."""
    # Only allow safe single-character delimiters
    safe_delimiters = {',', ';', '\t', '|'}
    return len(delimiter) == 1 and delimiter in safe_delimiters


def validate_text_content(text: str) -> str:
    """Validate and sanitize general text content."""
    if not text:
        return text

    # Check for dangerous patterns
    dangerous_patterns = [
        r'[;\'"<>{}$`]',  # Injection characters
        r'(script|javascript|vbscript)',  # Script tags
        r'(drop|delete|insert|update|union|exec)\s',  # SQL keywords
        r'(\$\{|\#\{|\{\{)',  # Template injection
        r'(\|\s*(rm|cat|ls|ps|kill|curl|wget))',  # Command injection
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            raise ValueError("Invalid characters detected in input")

    return text


# Pydantic Models for Tool Input Validation


class SearchFrameworksInput(BaseModel):
    """Input parameters for framework search."""

    query: str = Field(
        ..., description="Search query text", min_length=1, max_length=200
    )
    frameworks: list[FrameworkType] = Field(
        default_factory=list,
        description="Specific frameworks to search (empty = all frameworks)",
    )
    sections: list[str] = Field(
        default_factory=list, description="Framework sections to filter by"
    )
    severity: list[SeverityLevel] = Field(
        default_factory=list, description="Severity levels to filter by"
    )
    compliance_status: list[ComplianceStatus] = Field(
        default_factory=list, description="Compliance status to filter by"
    )
    tags: list[str] = Field(default_factory=list, description="Tags to filter by")
    exact_match: bool = Field(
        default=False, description="Perform exact phrase matching"
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of results")

    @field_validator('query')
    @classmethod
    def validate_query_content(cls, v: str) -> str:
        """Validate search query for security."""
        return validate_text_content(v)

    @field_validator('sections')
    @classmethod
    def validate_sections(cls, v: list[str]) -> list[str]:
        """Validate sections list for security."""
        return [validate_text_content(section) for section in v]

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate tags list for security."""
        return [validate_text_content(tag) for tag in v]


class ListFrameworksInput(BaseModel):
    """Input parameters for listing frameworks."""

    include_stats: bool = Field(
        default=True, description="Include framework statistics"
    )
    active_only: bool = Field(default=True, description="Only list active frameworks")


class GetFrameworkDetailsInput(BaseModel):
    """Input parameters for getting framework details."""

    framework_type: FrameworkType = Field(
        ..., description="Framework type to get details for"
    )
    include_references: bool = Field(
        default=True, description="Include reference details"
    )
    include_sections: bool = Field(default=True, description="Include section details")


class GetComplianceAnalysisInput(BaseModel):
    """Input parameters for compliance analysis."""

    frameworks: list[FrameworkType] = Field(
        default_factory=list,
        description="Frameworks to analyze (empty = all frameworks)",
    )
    include_mappings: bool = Field(
        default=False, description="Include cross-framework mappings"
    )


class SearchFrameworkReferencesInput(BaseModel):
    """Input parameters for searching specific framework references."""

    query: str = Field(..., description="Search query", min_length=1)
    framework_type: FrameworkType = Field(
        ..., description="Specific framework to search"
    )
    section: str = Field(default="", description="Specific section to search within")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")


class GetRelatedControlsInput(BaseModel):
    """Input parameters for finding related controls across frameworks."""

    framework_type: FrameworkType = Field(..., description="Source framework type")
    control_id: str = Field(..., description="Source control ID", min_length=1)
    min_strength: str = Field(
        default="weak",
        description="Minimum mapping strength (exact, strong, partial, weak)",
    )


class GetFrameworkCorrelationsInput(BaseModel):
    """Input parameters for framework correlation analysis."""

    framework1: FrameworkType = Field(..., description="Primary framework")
    framework2: FrameworkType | None = Field(
        default=None, description="Secondary framework (optional for all correlations)"
    )
    min_strength: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum correlation strength"
    )


class FindComplianceGapsInput(BaseModel):
    """Input parameters for compliance gap analysis."""

    source_framework: FrameworkType = Field(
        ..., description="Source framework to analyze from"
    )
    target_frameworks: list[FrameworkType] = Field(
        ..., description="Target frameworks to map to", min_length=1
    )
    min_coverage: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum coverage threshold"
    )


class AdvancedSearchInput(BaseModel):
    """Input parameters for advanced framework search with enhanced filtering."""

    # Framework selection
    frameworks: list[FrameworkType] = Field(
        default_factory=list, description="Frameworks to search (empty = all)"
    )

    # Text search
    search_terms: list[str] = Field(
        default_factory=list, description="Terms that must be present"
    )
    exclude_terms: list[str] = Field(
        default_factory=list, description="Terms to exclude from results"
    )

    # Content filters
    categories: list[str] = Field(
        default_factory=list, description="Categories to filter by"
    )
    sections: list[str] = Field(
        default_factory=list, description="Sections to filter by"
    )
    tags: list[str] = Field(default_factory=list, description="Tags to filter by")

    # Status filters
    severity_levels: list[SeverityLevel] = Field(
        default_factory=list, description="Severity levels to include"
    )
    compliance_status: list[ComplianceStatus] = Field(
        default_factory=list, description="Compliance status to include"
    )

    # Date filters
    updated_after: str = Field(
        default="", description="Include items updated after this date (ISO format)"
    )
    updated_before: str = Field(
        default="", description="Include items updated before this date (ISO format)"
    )

    # Result limits
    limit: int = Field(
        default=100, ge=1, le=500, description="Maximum results to return"
    )


class ExportFrameworkDataInput(BaseModel):
    """Input parameters for framework data export."""

    # Export format
    format: ExportFormat = Field(..., description="Export format")

    # Basic filters (simplified for tool interface)
    frameworks: list[FrameworkType] = Field(
        default_factory=list, description="Frameworks to include (empty = all)"
    )
    categories: list[str] = Field(
        default_factory=list, description="Categories to filter by"
    )
    sections: list[str] = Field(
        default_factory=list, description="Sections to filter by"
    )
    severity_levels: list[SeverityLevel] = Field(
        default_factory=list, description="Severity levels to include"
    )
    compliance_status: list[ComplianceStatus] = Field(
        default_factory=list, description="Compliance status to include"
    )

    # Export options
    filename: str = Field(default="", description="Custom filename for export")
    include_descriptions: bool = Field(
        default=True, description="Include full descriptions"
    )
    include_urls: bool = Field(default=True, description="Include URLs")
    include_metadata: bool = Field(default=True, description="Include metadata fields")

    # Format-specific options
    csv_delimiter: str = Field(default=",", description="CSV field delimiter")
    include_summary: bool = Field(
        default=True, description="Include summary statistics"
    )

    @field_validator('filename')
    @classmethod
    def validate_filename_security(cls, v: str) -> str:
        """Validate filename for security."""
        if not v:
            return v

        # Check for path traversal patterns
        dangerous_patterns = ['..', '/', '\\', ':', '*', '?', '<', '>', '|', '&', ';', '`', '$']
        for pattern in dangerous_patterns:
            if pattern in v:
                raise ValueError("Invalid filename: contains dangerous characters")

        # Additional validation
        sanitized = sanitize_filename(v)
        if len(sanitized) > 100:  # Reasonable filename length limit
            raise ValueError("Filename too long (max 100 characters)")

        return sanitized

    @field_validator('csv_delimiter')
    @classmethod
    def validate_csv_delimiter_security(cls, v: str) -> str:
        """Validate CSV delimiter for security."""
        if not validate_csv_delimiter(v):
            raise ValueError("Invalid CSV delimiter: only safe single characters allowed")
        return v

    @field_validator('categories')
    @classmethod
    def validate_categories(cls, v: list[str]) -> list[str]:
        """Validate categories list for security."""
        return [validate_text_content(category) for category in v]

    @field_validator('sections')
    @classmethod
    def validate_sections_export(cls, v: list[str]) -> list[str]:
        """Validate sections list for security."""
        return [validate_text_content(section) for section in v]


class BulkExportInput(BaseModel):
    """Input parameters for bulk export of multiple framework data sets."""

    # Export configurations
    exports: list[dict] = Field(
        ..., description="List of export configurations", min_length=1, max_length=10
    )

    # Global options
    compress_output: bool = Field(
        default=False, description="Compress exports into archive"
    )
    include_manifest: bool = Field(
        default=True, description="Include export manifest file"
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
                "maxLength": 500,
            },
            "frameworks": {
                "type": "array",
                "items": {"type": "string", "enum": [ft.value for ft in FrameworkType]},
                "description": "Specific frameworks to search (leave empty for all)",
            },
            "sections": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Framework sections to filter by",
            },
            "severity": {
                "type": "array",
                "items": {"type": "string", "enum": [sl.value for sl in SeverityLevel]},
                "description": "Severity levels to filter by",
            },
            "compliance_status": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [cs.value for cs in ComplianceStatus],
                },
                "description": "Compliance status to filter by",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags to filter by",
            },
            "exact_match": {
                "type": "boolean",
                "description": "Perform exact phrase matching",
                "default": False,
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum number of results",
                "default": 10,
            },
        },
        "required": ["query"],
    },
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
                "default": True,
            },
            "active_only": {
                "type": "boolean",
                "description": "Only list active frameworks",
                "default": True,
            },
        },
    },
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
                "description": "Framework type to get details for",
            },
            "include_references": {
                "type": "boolean",
                "description": "Include reference details",
                "default": True,
            },
            "include_sections": {
                "type": "boolean",
                "description": "Include section details",
                "default": True,
            },
        },
        "required": ["framework_type"],
    },
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
                "description": "Frameworks to analyze (leave empty for all)",
            },
            "include_mappings": {
                "type": "boolean",
                "description": "Include cross-framework mappings",
                "default": False,
            },
        },
    },
)

SEARCH_FRAMEWORK_REFERENCES_TOOL = Tool(
    name="search_framework_references",
    description="Search for specific references within a particular governance framework. Useful for finding detailed requirements or controls.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query", "minLength": 1},
            "framework_type": {
                "type": "string",
                "enum": [ft.value for ft in FrameworkType],
                "description": "Specific framework to search",
            },
            "section": {
                "type": "string",
                "description": "Specific section to search within",
                "default": "",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Maximum results",
                "default": 20,
            },
        },
        "required": ["query", "framework_type"],
    },
)

GET_RELATED_CONTROLS_TOOL = Tool(
    name="get_related_controls",
    description="Find related controls across different governance frameworks for a specific control. Useful for cross-framework compliance mapping.",
    inputSchema={
        "type": "object",
        "properties": {
            "framework_type": {
                "type": "string",
                "enum": [ft.value for ft in FrameworkType],
                "description": "Source framework type",
            },
            "control_id": {
                "type": "string",
                "description": "Source control ID",
                "minLength": 1,
            },
            "min_strength": {
                "type": "string",
                "enum": ["exact", "strong", "partial", "weak"],
                "description": "Minimum mapping strength",
                "default": "weak",
            },
        },
        "required": ["framework_type", "control_id"],
    },
)

GET_FRAMEWORK_CORRELATIONS_TOOL = Tool(
    name="get_framework_correlations",
    description="Analyze correlations between governance frameworks to identify thematic overlaps and relationship strength.",
    inputSchema={
        "type": "object",
        "properties": {
            "framework1": {
                "type": "string",
                "enum": [ft.value for ft in FrameworkType],
                "description": "Primary framework",
            },
            "framework2": {
                "type": "string",
                "enum": [ft.value for ft in FrameworkType],
                "description": "Secondary framework (optional)",
            },
            "min_strength": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Minimum correlation strength",
                "default": 0.5,
            },
        },
        "required": ["framework1"],
    },
)

FIND_COMPLIANCE_GAPS_TOOL = Tool(
    name="find_compliance_gaps",
    description="Identify potential compliance gaps when mapping from one framework to others. Useful for gap analysis and compliance planning.",
    inputSchema={
        "type": "object",
        "properties": {
            "source_framework": {
                "type": "string",
                "enum": [ft.value for ft in FrameworkType],
                "description": "Source framework to analyze from",
            },
            "target_frameworks": {
                "type": "array",
                "items": {"type": "string", "enum": [ft.value for ft in FrameworkType]},
                "description": "Target frameworks to map to",
                "minItems": 1,
            },
            "min_coverage": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Minimum coverage threshold",
                "default": 0.7,
            },
        },
        "required": ["source_framework", "target_frameworks"],
    },
)

ADVANCED_SEARCH_TOOL = Tool(
    name="advanced_search_frameworks",
    description="Perform advanced search across frameworks with enhanced filtering capabilities including category filtering, term inclusion/exclusion, and date ranges.",
    inputSchema={
        "type": "object",
        "properties": {
            "frameworks": {
                "type": "array",
                "items": {"type": "string", "enum": [ft.value for ft in FrameworkType]},
                "description": "Frameworks to search (leave empty for all)",
            },
            "search_terms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Terms that must be present in results",
            },
            "exclude_terms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Terms to exclude from results",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Categories to filter by",
            },
            "sections": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Sections to filter by",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags to filter by",
            },
            "severity_levels": {
                "type": "array",
                "items": {"type": "string", "enum": [sl.value for sl in SeverityLevel]},
                "description": "Severity levels to include",
            },
            "compliance_status": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [cs.value for cs in ComplianceStatus],
                },
                "description": "Compliance status to include",
            },
            "updated_after": {
                "type": "string",
                "description": "Include items updated after this date (ISO format)",
                "default": "",
            },
            "updated_before": {
                "type": "string",
                "description": "Include items updated before this date (ISO format)",
                "default": "",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "description": "Maximum results to return",
                "default": 100,
            },
        },
    },
)

EXPORT_FRAMEWORK_DATA_TOOL = Tool(
    name="export_framework_data",
    description="Export framework data in JSON, CSV, or Markdown format with comprehensive filtering options. Perfect for compliance teams to generate reports and documentation.",
    inputSchema={
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "enum": [ef.value for ef in ExportFormat],
                "description": "Export format (json, csv, markdown)",
            },
            "frameworks": {
                "type": "array",
                "items": {"type": "string", "enum": [ft.value for ft in FrameworkType]},
                "description": "Frameworks to include (leave empty for all)",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Categories to filter by",
            },
            "sections": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Sections to filter by",
            },
            "severity_levels": {
                "type": "array",
                "items": {"type": "string", "enum": [sl.value for sl in SeverityLevel]},
                "description": "Severity levels to include",
            },
            "compliance_status": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [cs.value for cs in ComplianceStatus],
                },
                "description": "Compliance status to include",
            },
            "filename": {
                "type": "string",
                "description": "Custom filename for export",
                "default": "",
            },
            "include_descriptions": {
                "type": "boolean",
                "description": "Include full descriptions",
                "default": True,
            },
            "include_urls": {
                "type": "boolean",
                "description": "Include URLs",
                "default": True,
            },
            "include_metadata": {
                "type": "boolean",
                "description": "Include metadata fields",
                "default": True,
            },
            "csv_delimiter": {
                "type": "string",
                "description": "CSV field delimiter",
                "default": ",",
            },
            "include_summary": {
                "type": "boolean",
                "description": "Include summary statistics",
                "default": True,
            },
        },
        "required": ["format"],
    },
)

BULK_EXPORT_TOOL = Tool(
    name="bulk_export_frameworks",
    description="Perform bulk export of multiple framework datasets with different configurations. Useful for generating comprehensive compliance documentation packages.",
    inputSchema={
        "type": "object",
        "properties": {
            "exports": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Export name"},
                        "format": {
                            "type": "string",
                            "enum": [ef.value for ef in ExportFormat],
                        },
                        "frameworks": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [ft.value for ft in FrameworkType],
                            },
                        },
                        "include_summary": {"type": "boolean", "default": True},
                    },
                    "required": ["name", "format"],
                },
                "description": "List of export configurations",
                "minItems": 1,
                "maxItems": 10,
            },
            "compress_output": {
                "type": "boolean",
                "description": "Compress exports into archive",
                "default": False,
            },
            "include_manifest": {
                "type": "boolean",
                "description": "Include export manifest file",
                "default": True,
            },
        },
        "required": ["exports"],
    },
)

# Framework Tools Collection
FRAMEWORK_TOOLS = [
    SEARCH_FRAMEWORKS_TOOL,
    LIST_FRAMEWORKS_TOOL,
    GET_FRAMEWORK_DETAILS_TOOL,
    GET_COMPLIANCE_ANALYSIS_TOOL,
    SEARCH_FRAMEWORK_REFERENCES_TOOL,
    GET_RELATED_CONTROLS_TOOL,
    GET_FRAMEWORK_CORRELATIONS_TOOL,
    FIND_COMPLIANCE_GAPS_TOOL,
    ADVANCED_SEARCH_TOOL,
    EXPORT_FRAMEWORK_DATA_TOOL,
    BULK_EXPORT_TOOL,
]


# Tool Handler Functions


async def handle_framework_tools(
    name: str, arguments: dict[str, Any]
) -> list[TextContent]:
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
        elif name == "get_related_controls":
            return await _handle_get_related_controls(arguments)
        elif name == "get_framework_correlations":
            return await _handle_get_framework_correlations(arguments)
        elif name == "find_compliance_gaps":
            return await _handle_find_compliance_gaps(arguments)
        elif name == "advanced_search_frameworks":
            return await _handle_advanced_search_frameworks(arguments)
        elif name == "export_framework_data":
            return await _handle_export_framework_data(arguments)
        elif name == "bulk_export_frameworks":
            return await _handle_bulk_export_frameworks(arguments)
        else:
            raise ValueError(f"Unknown framework tool: {name}")

    except Exception as e:
        logger.error(f"Framework tool error ({name}): {e}")
        return [TextContent(type="text", text=f"Framework tool error: {e!s}")]


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
    try:
        query_engine = _ensure_query_engine()
        result = await query_engine.search(query)
    except RuntimeError as e:
        return [TextContent(type="text", text=str(e))]

    # Format response
    response_text = _format_search_result(result)

    return [TextContent(type="text", text=response_text)]


async def _handle_list_frameworks(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle list frameworks requests."""
    input_data = ListFrameworksInput(**arguments)

    try:
        query_engine = _ensure_query_engine()
        frameworks = query_engine.frameworks
    except RuntimeError as e:
        return [TextContent(type="text", text=str(e))]
    response_lines = ["# Available Governance Frameworks\n"]

    for framework_type, framework in frameworks.items():
        if not input_data.active_only or framework.is_active:
            response_lines.append(f"## {framework.name} ({framework_type.value})")
            response_lines.append(f"**Version:** {framework.version}")
            response_lines.append(f"**Publisher:** {framework.publisher}")

            if input_data.include_stats:
                response_lines.append(f"**References:** {framework.total_references}")
                response_lines.append(f"**Sections:** {len(framework.sections)}")
                response_lines.append(
                    f"**Active References:** {framework.active_references}"
                )

            if framework.description:
                response_lines.append(f"**Description:** {framework.description}")

            if framework.official_url:
                response_lines.append(f"**Official URL:** {framework.official_url}")

            response_lines.append("")

    return [TextContent(type="text", text="\n".join(response_lines))]


async def _handle_get_framework_details(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle framework details requests."""
    input_data = GetFrameworkDetailsInput(**arguments)

    try:
        query_engine = _ensure_query_engine()
        framework = query_engine.frameworks.get(input_data.framework_type)
    except RuntimeError as e:
        return [TextContent(type="text", text=str(e))]
    if not framework:
        return [
            TextContent(
                type="text", text=f"Framework not found: {input_data.framework_type}"
            )
        ]

    response_lines = [f"# {framework.name} Details\n"]

    # Framework metadata
    response_lines.extend(
        [
            f"**Type:** {framework.framework_type.value}",
            f"**Version:** {framework.version}",
            f"**Publisher:** {framework.publisher}",
            f"**Total References:** {framework.total_references}",
            f"**Active References:** {framework.active_references}",
            f"**Last Updated:** {framework.last_updated.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
    )

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
            response_lines.extend(
                [
                    f"### {ref.title} ({ref.id})",
                    f"**Section:** {ref.section}",
                    f"**Severity:** {ref.severity.value}",
                    f"**Compliance Status:** {ref.compliance_status.value}",
                ]
            )
            if ref.description:
                response_lines.append(f"**Description:** {ref.description}")
            if ref.official_url:
                response_lines.append(f"**URL:** {ref.official_url}")
            response_lines.append("")

        if len(framework.references) > 5:
            response_lines.append(
                f"*... and {len(framework.references) - 5} more references*"
            )

    return [TextContent(type="text", text="\n".join(response_lines))]


async def _handle_get_compliance_analysis(
    arguments: dict[str, Any],
) -> list[TextContent]:
    """Handle compliance analysis requests."""
    input_data = GetComplianceAnalysisInput(**arguments)

    try:
        query_engine = _ensure_query_engine()
        analytics = await query_engine.get_analytics()
    except RuntimeError as e:
        return [TextContent(type="text", text=str(e))]

    response_lines = ["# Compliance Analysis Report\n"]

    # Overall statistics
    response_lines.extend(
        [
            f"**Total Frameworks:** {analytics.total_frameworks}",
            f"**Total References:** {analytics.total_references}",
            f"**Overall Compliance:** {analytics.compliance_percentage:.1f}%",
            "",
        ]
    )

    # Framework-specific analysis
    target_frameworks = (
        input_data.frameworks
        if input_data.frameworks
        else list(_ensure_query_engine().frameworks.keys())
    )

    response_lines.append("## Framework Breakdown")
    for framework_type in target_frameworks:
        if framework_type in analytics.framework_stats:
            stats = analytics.framework_stats[framework_type]
            framework = _ensure_query_engine().frameworks[framework_type]

            response_lines.extend(
                [
                    f"### {framework.name}",
                    f"- **References:** {stats['references']}",
                    f"- **Active References:** {stats['active_references']}",
                    f"- **Sections:** {stats['sections']}",
                    "",
                ]
            )

    # Compliance status distribution
    if analytics.compliance_coverage:
        response_lines.append("## Compliance Status Distribution")
        for status, count in analytics.compliance_coverage.items():
            percentage = (count / analytics.total_references) * 100
            response_lines.append(
                f"- **{status.value.title()}:** {count} ({percentage:.1f}%)"
            )
        response_lines.append("")

    # Compliance gaps and recommendations
    non_compliant = analytics.compliance_coverage.get(ComplianceStatus.NON_COMPLIANT, 0)
    under_review = analytics.compliance_coverage.get(ComplianceStatus.UNDER_REVIEW, 0)

    if non_compliant > 0 or under_review > 0:
        response_lines.append("## Compliance Gaps")
        if non_compliant > 0:
            response_lines.append(
                f"- **{non_compliant} non-compliant references** require immediate attention"
            )
        if under_review > 0:
            response_lines.append(
                f"- **{under_review} references under review** need compliance assessment"
            )
        response_lines.append("")

    return [TextContent(type="text", text="\n".join(response_lines))]


async def _handle_search_framework_references(
    arguments: dict[str, Any],
) -> list[TextContent]:
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
    result = await _ensure_query_engine().search(query)

    # Format response focusing on references
    framework = _ensure_query_engine().frameworks[input_data.framework_type]
    response_lines = [f"# {framework.name} Reference Search Results\n"]

    if result.total_results == 0:
        response_lines.append("No matching references found.")
    else:
        response_lines.append(f"Found {result.total_results} matching references:\n")

        for ref in result.references:
            response_lines.extend(
                [
                    f"## {ref.title} ({ref.id})",
                    f"**Section:** {ref.section}",
                    f"**Severity:** {ref.severity.value}",
                    f"**Status:** {ref.compliance_status.value}",
                ]
            )

            if ref.description:
                response_lines.append(f"**Description:** {ref.description}")

            if ref.official_url:
                response_lines.append(f"**URL:** {ref.official_url}")

            if ref.tags:
                response_lines.append(f"**Tags:** {', '.join(ref.tags)}")

            response_lines.append("")

        if result.has_more:
            response_lines.append(
                f"*Showing {result.returned_results} of {result.total_results} results*"
            )

    return [TextContent(type="text", text="\n".join(response_lines))]


async def _handle_get_related_controls(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle related controls requests."""
    input_data = GetRelatedControlsInput(**arguments)

    # Convert string to enum
    min_strength = MappingStrength(input_data.min_strength)

    # Get related controls
    related_controls = _ensure_cross_mapper().get_related_controls(
        input_data.framework_type, input_data.control_id, min_strength
    )

    response_lines = [f"# Related Controls for {input_data.control_id}\n"]

    if not related_controls:
        response_lines.append("No related controls found with the specified criteria.")
    else:
        response_lines.append(f"Found {len(related_controls)} related controls:\n")

        for mapping in related_controls:
            target_framework = _ensure_query_engine().frameworks.get(
                mapping.target_framework
            )
            framework_name = (
                target_framework.name
                if target_framework
                else mapping.target_framework.value
            )

            response_lines.extend(
                [
                    f"## {mapping.target_control_id}",
                    f"**Framework:** {framework_name}",
                    f"**Mapping Strength:** {mapping.mapping_strength.value.title()}",
                    f"**Description:** {mapping.description}",
                ]
            )

            if mapping.notes:
                response_lines.append(f"**Notes:** {mapping.notes}")

            response_lines.append("")

    return [TextContent(type="text", text="\n".join(response_lines))]


async def _handle_get_framework_correlations(
    arguments: dict[str, Any],
) -> list[TextContent]:
    """Handle framework correlations requests."""
    input_data = GetFrameworkCorrelationsInput(**arguments)

    if input_data.framework2:
        # Get correlations between two specific frameworks
        if _correlations_service is None:
            raise RuntimeError("Correlations service not initialized")
        correlations = _correlations_service.get_framework_correlations(
            input_data.framework1, input_data.framework2, input_data.min_strength
        )
        summary = _correlations_service.get_correlation_summary(
            input_data.framework1, input_data.framework2
        )

        response_lines = [
            f"# Correlations: {input_data.framework1.value} ↔ {input_data.framework2.value}\n"
        ]

        if summary["correlation_exists"]:
            response_lines.extend(
                [
                    f"**Total Correlations:** {summary['total_correlations']}",
                    f"**Average Strength:** {summary['average_strength']}",
                    f"**Correlation Types:** {', '.join(summary['correlation_types'])}",
                    f"**Strongest Correlation:** {summary['strongest_correlation']}",
                    "",
                ]
            )

            response_lines.append("## Detailed Correlations")
            for correlation in correlations:
                response_lines.extend(
                    [
                        f"### {correlation.topic}",
                        f"**Type:** {correlation.correlation_type.value.title()}",
                        f"**Strength:** {correlation.strength:.2f}",
                        f"**Description:** {correlation.description}",
                        f"**Related Controls:** {', '.join(correlation.related_controls)}",
                        "",
                    ]
                )
        else:
            response_lines.append(summary["summary"])
    else:
        # Get all correlations for the framework
        if _correlations_service is None:
            raise RuntimeError("Correlations service not initialized")
        related_frameworks = _correlations_service.get_related_frameworks(
            input_data.framework1, input_data.min_strength
        )

        response_lines = [f"# Framework Correlations: {input_data.framework1.value}\n"]

        if not related_frameworks:
            response_lines.append("No correlations found with the specified criteria.")
        else:
            response_lines.append(
                f"Found correlations with {len(related_frameworks)} frameworks:\n"
            )

            for framework_type, correlations in related_frameworks.items():
                target_framework = _ensure_query_engine().frameworks.get(framework_type)
                framework_name = (
                    target_framework.name if target_framework else framework_type.value
                )

                avg_strength = sum(c.strength for c in correlations) / len(correlations)

                response_lines.extend(
                    [
                        f"## {framework_name}",
                        f"**Correlations:** {len(correlations)}",
                        f"**Average Strength:** {avg_strength:.2f}",
                        f"**Topics:** {', '.join(c.topic for c in correlations)}",
                        "",
                    ]
                )

    return [TextContent(type="text", text="\n".join(response_lines))]


async def _handle_find_compliance_gaps(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle compliance gap analysis requests."""
    input_data = FindComplianceGapsInput(**arguments)

    # Perform gap analysis
    if _correlations_service is None:
        raise RuntimeError("Correlations service not initialized")
    gap_analysis = _correlations_service.find_compliance_gaps(
        input_data.source_framework,
        input_data.target_frameworks,
        input_data.min_coverage,
    )

    source_framework = _ensure_query_engine().frameworks.get(
        input_data.source_framework
    )
    source_name = (
        source_framework.name if source_framework else input_data.source_framework.value
    )

    response_lines = [f"# Compliance Gap Analysis: {source_name}\n"]

    response_lines.extend(
        [
            f"**Source Framework:** {source_name}",
            f"**Target Frameworks:** {len(input_data.target_frameworks)}",
            f"**Overall Coverage:** {gap_analysis['overall_coverage']:.1%}",
            f"**Coverage Threshold:** {input_data.min_coverage:.1%}",
            "",
        ]
    )

    # Coverage summary by framework
    response_lines.append("## Framework Coverage Summary")
    for framework_name, coverage_info in gap_analysis["coverage_summary"].items():
        target_framework = next(
            (
                f
                for f in _ensure_query_engine().frameworks.values()
                if f.framework_type.value == framework_name
            ),
            None,
        )
        display_name = target_framework.name if target_framework else framework_name

        response_lines.extend(
            [
                f"### {display_name}",
                f"- **Total Correlations:** {coverage_info['total_correlations']}",
                f"- **Strong Correlations:** {coverage_info['strong_correlations']}",
                f"- **Coverage Ratio:** {coverage_info['coverage_ratio']:.1%}",
                "",
            ]
        )

    # Potential gaps
    if gap_analysis["potential_gaps"]:
        response_lines.append("## Identified Gaps")

        # Group gaps by severity
        high_gaps = [
            g for g in gap_analysis["potential_gaps"] if g["gap_severity"] == "high"
        ]
        medium_gaps = [
            g for g in gap_analysis["potential_gaps"] if g["gap_severity"] == "medium"
        ]

        if high_gaps:
            response_lines.append("### High Severity Gaps")
            for gap in high_gaps:
                response_lines.extend(
                    [
                        f"**{gap['topic']}** ({gap['target_framework']})",
                        f"- Strength: {gap['strength']:.2f}",
                        f"- Description: {gap['description']}",
                        "",
                    ]
                )

        if medium_gaps:
            response_lines.append("### Medium Severity Gaps")
            for gap in medium_gaps:
                response_lines.extend(
                    [
                        f"**{gap['topic']}** ({gap['target_framework']})",
                        f"- Strength: {gap['strength']:.2f}",
                        f"- Description: {gap['description']}",
                        "",
                    ]
                )
    else:
        response_lines.append("## No Significant Gaps Identified")
        response_lines.append("All correlations meet the minimum coverage threshold.")

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
    lines.append(
        f"**Results:** {result.total_results} found in {result.search_time_ms:.1f}ms"
    )

    if result.cache_hit:
        lines.append("*(cached result)*")

    lines.append("")

    # Framework coverage
    if result.framework_coverage:
        lines.append("**Framework Coverage:**")
        for framework_type, count in result.framework_coverage.items():
            framework_name = _ensure_query_engine().frameworks[framework_type].name
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
                framework_name = (
                    _ensure_query_engine().frameworks[ref.framework_type].name
                )
                lines.extend(
                    [
                        f"### {ref.title}",
                        f"**Framework:** {framework_name}",
                        f"**Section:** {ref.section}",
                        f"**Severity:** {ref.severity.value}",
                        f"**Status:** {ref.compliance_status.value}",
                    ]
                )

                if ref.description:
                    lines.append(f"**Description:** {ref.description[:200]}...")

                if ref.official_url:
                    lines.append(f"**URL:** {ref.official_url}")

                lines.append("")

        # Show sections
        if result.sections:
            lines.append("## Matching Sections")
            for section in result.sections:
                framework = _ensure_query_engine().frameworks.get(
                    section.framework_type
                )
                framework_name = framework.name if framework else "Unknown"
                lines.extend(
                    [
                        f"### {section.title}",
                        f"**Framework:** {framework_name}",
                        f"**References:** {section.reference_count}",
                    ]
                )

                if section.description:
                    lines.append(f"**Description:** {section.description}")

                lines.append("")

        # Pagination info
        if result.has_more:
            lines.append(
                f"*Showing {result.returned_results} of {result.total_results} results*"
            )

    return "\n".join(lines)


async def _handle_advanced_search_frameworks(
    arguments: dict[str, Any],
) -> list[TextContent]:
    """Handle advanced framework search requests."""
    from datetime import datetime

    input_data = AdvancedSearchInput(**arguments)

    # Build export filter for advanced search
    export_filter = ExportFilter(
        framework_types=input_data.frameworks,
        sections=input_data.sections,
        categories=input_data.categories,
        tags=input_data.tags,
        severity_levels=input_data.severity_levels,
        compliance_status=input_data.compliance_status,
        search_terms=input_data.search_terms,
        exclude_terms=input_data.exclude_terms,
        updated_after=None,
        updated_before=None,
    )

    # Parse date filters if provided
    if input_data.updated_after:
        try:
            export_filter.updated_after = datetime.fromisoformat(
                input_data.updated_after.replace("Z", "+00:00")
            )
        except ValueError:
            pass

    if input_data.updated_before:
        try:
            export_filter.updated_before = datetime.fromisoformat(
                input_data.updated_before.replace("Z", "+00:00")
            )
        except ValueError:
            pass

    # Execute advanced search
    result = await _ensure_query_engine().advanced_search(export_filter)

    # Apply limit to results
    if input_data.limit < len(result.references) + len(result.sections):
        # Truncate results
        total_items = input_data.limit
        refs_to_take = min(len(result.references), total_items)
        secs_to_take = total_items - refs_to_take

        result.references = result.references[:refs_to_take]
        result.sections = result.sections[:secs_to_take]
        result.returned_results = len(result.references) + len(result.sections)
        result.has_more = True

    # Format response
    response_lines = ["# Advanced Framework Search Results\n"]

    # Search criteria summary
    response_lines.extend(
        [
            f"**Total Results:** {result.total_results}",
            f"**Returned Results:** {result.returned_results}",
            f"**Search Time:** {result.search_time_ms:.2f}ms",
            "",
        ]
    )

    # Applied filters summary
    filters_applied = []
    if input_data.frameworks:
        filters_applied.append(
            f"Frameworks: {', '.join([ft.value for ft in input_data.frameworks])}"
        )
    if input_data.search_terms:
        filters_applied.append(f"Include terms: {', '.join(input_data.search_terms)}")
    if input_data.exclude_terms:
        filters_applied.append(f"Exclude terms: {', '.join(input_data.exclude_terms)}")
    if input_data.categories:
        filters_applied.append(f"Categories: {', '.join(input_data.categories)}")
    if input_data.severity_levels:
        filters_applied.append(
            f"Severity: {', '.join([sl.value for sl in input_data.severity_levels])}"
        )

    if filters_applied:
        response_lines.extend(
            [
                "**Applied Filters:**",
                *[f"- {filter_desc}" for filter_desc in filters_applied],
                "",
            ]
        )

    # Framework coverage
    if result.framework_coverage:
        response_lines.append("**Framework Coverage:**")
        for framework_type, count in result.framework_coverage.items():
            framework_name = _ensure_query_engine().frameworks[framework_type].name
            response_lines.append(f"- {framework_name}: {count} results")
        response_lines.append("")

    # Results
    if result.total_results == 0:
        response_lines.append("No matching results found with the specified criteria.")
    else:
        # Show references
        if result.references:
            response_lines.append("## Matching References")
            for ref in result.references:
                framework_name = (
                    _ensure_query_engine().frameworks[ref.framework_type].name
                )
                response_lines.extend(
                    [
                        f"### {ref.title}",
                        f"**Framework:** {framework_name}",
                        f"**Section:** {ref.section}",
                        f"**Severity:** {ref.severity.value}",
                        f"**Status:** {ref.compliance_status.value}",
                    ]
                )

                if ref.description:
                    response_lines.append(
                        f"**Description:** {ref.description[:300]}..."
                    )

                if ref.tags:
                    response_lines.append(f"**Tags:** {', '.join(ref.tags)}")

                response_lines.append("")

        # Show sections
        if result.sections:
            response_lines.append("## Matching Sections")
            for section in result.sections:
                framework = _ensure_query_engine().frameworks.get(
                    section.framework_type
                )
                framework_name = framework.name if framework else "Unknown"
                response_lines.extend(
                    [
                        f"### {section.title}",
                        f"**Framework:** {framework_name}",
                        f"**References:** {section.reference_count}",
                    ]
                )

                if section.description:
                    response_lines.append(f"**Description:** {section.description}")

                response_lines.append("")

        # Pagination info
        if result.has_more:
            response_lines.append(
                f"*Showing {result.returned_results} of {result.total_results} results*"
            )

    return [TextContent(type="text", text="\n".join(response_lines))]


async def _handle_export_framework_data(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle framework data export requests."""
    input_data = ExportFrameworkDataInput(**arguments)

    # Build export filter
    export_filter = ExportFilter(
        framework_types=input_data.frameworks,
        categories=input_data.categories,
        sections=input_data.sections,
        severity_levels=input_data.severity_levels,
        compliance_status=input_data.compliance_status,
        updated_after=None,
        updated_before=None,
    )

    # Build export request
    export_request = ExportRequest(
        format=input_data.format,
        filters=export_filter,
        filename=input_data.filename or None,
        include_summary=input_data.include_summary,
        csv_delimiter=input_data.csv_delimiter,
    )

    # Execute export
    export_result = await _ensure_query_engine().export_data(export_request)

    # Format response
    response_lines = [
        f"# Framework Data Export ({input_data.format.value.upper()})\n",
        f"**Export ID:** {export_result.export_id}",
        f"**Format:** {export_result.request.format.value}",
        f"**Content Size:** {export_result.content_size:,} bytes",
        f"**Export Time:** {export_result.export_time_ms:.2f}ms",
        "",
        "**Items Exported:**",
        f"- Total Items: {export_result.total_items}",
        f"- Frameworks: {export_result.total_frameworks}",
        f"- References: {export_result.total_references}",
        f"- Sections: {export_result.total_sections}",
        "",
    ]

    # Validation status
    if export_result.is_valid:
        response_lines.append("**Validation:** ✅ Export content is valid")
    else:
        response_lines.extend(
            [
                "**Validation:** ❌ Export content has issues:",
                *[f"- {error}" for error in export_result.validation_errors],
            ]
        )
    response_lines.append("")

    # Content preview for smaller exports
    if export_result.content_size < 10000:  # Less than 10KB
        response_lines.extend(
            [
                "## Export Content",
                "",
                f"```{input_data.format.value}",
                export_result.content,
                "```",
            ]
        )
    else:
        # Show truncated content for larger exports
        preview_length = 2000
        truncated_content = export_result.content[:preview_length]
        if len(export_result.content) > preview_length:
            truncated_content += "\n... (content truncated)"

        response_lines.extend(
            [
                "## Export Content Preview",
                f"*(Showing first {preview_length} characters of {export_result.content_size:,} total)*",
                "",
                f"```{input_data.format.value}",
                truncated_content,
                "```",
            ]
        )

    return [TextContent(type="text", text="\n".join(response_lines))]


async def _handle_bulk_export_frameworks(
    arguments: dict[str, Any],
) -> list[TextContent]:
    """Handle bulk framework export requests."""
    input_data = BulkExportInput(**arguments)

    response_lines = [
        "# Bulk Framework Export\n",
        f"**Number of Exports:** {len(input_data.exports)}",
        f"**Compress Output:** {input_data.compress_output}",
        f"**Include Manifest:** {input_data.include_manifest}",
        "",
    ]

    export_results = []
    total_size = 0
    total_time = 0.0

    # Process each export
    for i, export_config in enumerate(input_data.exports, 1):
        try:
            response_lines.append(
                f"## Export {i}: {export_config.get('name', f'Export {i}')}"
            )

            # Build export request
            export_filter = ExportFilter(
                framework_types=[
                    FrameworkType(ft) for ft in export_config.get("frameworks", [])
                ],
                updated_after=None,
                updated_before=None,
            )

            export_request = ExportRequest(
                format=ExportFormat(export_config["format"]),
                filters=export_filter,
                filename=export_config.get("name", f"export_{i}"),
                include_summary=export_config.get("include_summary", True),
            )

            # Execute export
            export_result = await _ensure_query_engine().export_data(export_request)
            export_results.append(export_result)

            total_size += export_result.content_size
            total_time += export_result.export_time_ms

            response_lines.extend(
                [
                    f"**Format:** {export_result.request.format.value}",
                    f"**Size:** {export_result.content_size:,} bytes",
                    f"**Items:** {export_result.total_items}",
                    f"**Time:** {export_result.export_time_ms:.2f}ms",
                    f"**Status:** {'✅ Valid' if export_result.is_valid else '❌ Invalid'}",
                    "",
                ]
            )

        except Exception as e:
            response_lines.extend(
                [
                    f"**Status:** ❌ Failed - {e!s}",
                    "",
                ]
            )

    # Summary
    response_lines.extend(
        [
            "## Bulk Export Summary",
            "",
            f"**Total Exports:** {len(export_results)} of {len(input_data.exports)} successful",
            f"**Total Size:** {total_size:,} bytes",
            f"**Total Time:** {total_time:.2f}ms",
            f"**Average Size:** {total_size // len(export_results) if export_results else 0:,} bytes per export",
            "",
        ]
    )

    # Manifest information
    if input_data.include_manifest and export_results:
        response_lines.extend(
            [
                "## Export Manifest",
                "",
                "| Export | Format | Size (bytes) | Items | Status |",
                "|--------|--------|--------------|-------|--------|",
            ]
        )

        for result in export_results:
            name = result.request.filename or result.export_id[:8]
            status = "✅" if result.is_valid else "❌"
            response_lines.append(
                f"| {name} | {result.request.format.value} | {result.content_size:,} | {result.total_items} | {status} |"
            )

        response_lines.append("")

    # Content availability note
    if export_results:
        response_lines.extend(
            [
                "## Content Access",
                "",
                "The exported content has been generated and validated. In a production environment, ",
                "these exports would be available for download or further processing.",
                "",
                "**Export IDs for reference:**",
            ]
        )

        for result in export_results:
            name = result.request.filename or "Unnamed"
            response_lines.append(f"- {name}: `{result.export_id}`")

    return [TextContent(type="text", text="\n".join(response_lines))]
