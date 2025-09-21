"""
Framework Data Models

Unified Pydantic models for governance framework data structures.
Supports 7+ governance frameworks with consistent schema.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, validator


class FrameworkType(str, Enum):
    """Supported governance framework types."""

    NIST_AI_RMF = "nist-ai-rmf-1.0"
    EU_AI_ACT = "eu-ai-act"
    OWASP_LLM = "owasp-llm-top-10"
    ISO_27001 = "iso-27001"
    GDPR = "gdpr"
    CCPA = "ccpa"
    SOC2 = "soc2"


class SeverityLevel(str, Enum):
    """Risk/requirement severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "informational"


class ComplianceStatus(str, Enum):
    """Compliance implementation status."""

    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"
    UNDER_REVIEW = "under_review"


class FrameworkReference(BaseModel):
    """Individual framework reference/control/requirement."""

    id: str = Field(..., description="Unique framework reference identifier")
    framework_type: FrameworkType = Field(..., description="Source framework type")
    section: str = Field(..., description="Framework section/category")
    title: str = Field(..., description="Reference title")
    description: str = Field(..., description="Detailed description")
    severity: SeverityLevel = Field(default=SeverityLevel.MEDIUM)

    # External links
    official_url: HttpUrl | None = Field(None, description="Official framework URL")
    documentation_url: HttpUrl | None = Field(
        None, description="Additional documentation"
    )

    # Framework-specific metadata
    control_id: str | None = Field(None, description="Control/requirement ID")
    category: str | None = Field(None, description="Framework category")
    subcategory: str | None = Field(None, description="Framework subcategory")

    # Compliance tracking
    compliance_status: ComplianceStatus = Field(default=ComplianceStatus.UNDER_REVIEW)
    implementation_notes: str | None = Field(None, description="Implementation details")

    # Relationships
    related_references: list[str] = Field(
        default_factory=list, description="Related reference IDs"
    )
    tags: list[str] = Field(default_factory=list, description="Classification tags")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("id")
    def validate_id_format(cls, v):
        """Validate reference ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("Reference ID must be a non-empty string")
        return v.strip()

    @validator("tags")
    def validate_tags(cls, v):
        """Validate and normalize tags."""
        return [tag.strip().lower() for tag in v if tag.strip()]


class FrameworkSection(BaseModel):
    """Framework section/category grouping."""

    framework_type: FrameworkType
    section_id: str = Field(..., description="Section identifier")
    title: str = Field(..., description="Section title")
    description: str | None = Field(None, description="Section description")

    # Hierarchy
    parent_section: str | None = Field(None, description="Parent section ID")
    subsections: list[str] = Field(
        default_factory=list, description="Child section IDs"
    )

    # References in this section
    references: list[str] = Field(
        default_factory=list, description="Reference IDs in section"
    )
    reference_count: int = Field(default=0, description="Number of references")

    # Section metadata
    order: int = Field(default=0, description="Display order")
    is_active: bool = Field(default=True, description="Section is active")


class ComplianceMapping(BaseModel):
    """Cross-framework compliance mapping."""

    mapping_id: str = Field(..., description="Unique mapping identifier")
    source_reference: str = Field(..., description="Source reference ID")
    target_reference: str = Field(..., description="Target reference ID")

    # Mapping metadata
    mapping_type: str = Field(
        ..., description="Type of mapping (equivalent, related, etc.)"
    )
    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Mapping confidence"
    )
    justification: str | None = Field(None, description="Mapping justification")

    # Validation
    validated_by: str | None = Field(None, description="Validator identifier")
    validation_date: datetime | None = Field(None, description="Validation timestamp")
    is_validated: bool = Field(default=False, description="Mapping is validated")


class GovernanceFramework(BaseModel):
    """Complete governance framework definition."""

    framework_type: FrameworkType
    name: str = Field(..., description="Framework name")
    version: str = Field(..., description="Framework version")
    description: str = Field(..., description="Framework description")

    # Framework metadata
    publisher: str = Field(..., description="Framework publisher/organization")
    publication_date: datetime | None = Field(None, description="Publication date")
    effective_date: datetime | None = Field(None, description="Effective date")

    # Structure
    sections: list[FrameworkSection] = Field(default_factory=list)
    references: list[FrameworkReference] = Field(default_factory=list)

    # Framework URLs
    official_url: HttpUrl | None = Field(None, description="Official framework URL")
    documentation_url: HttpUrl | None = Field(None, description="Documentation URL")

    # Statistics
    total_references: int = Field(default=0, description="Total reference count")
    active_references: int = Field(default=0, description="Active reference count")

    # Status
    is_active: bool = Field(default=True, description="Framework is active")
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def get_reference_by_id(self, reference_id: str) -> FrameworkReference | None:
        """Get reference by ID."""
        return next((ref for ref in self.references if ref.id == reference_id), None)

    def get_section_by_id(self, section_id: str) -> FrameworkSection | None:
        """Get section by ID."""
        return next(
            (sec for sec in self.sections if sec.section_id == section_id), None
        )

    def get_references_by_section(self, section_id: str) -> list[FrameworkReference]:
        """Get all references in a section."""
        section = self.get_section_by_id(section_id)
        if not section:
            return []
        return [
            self.get_reference_by_id(ref_id)
            for ref_id in section.references
            if self.get_reference_by_id(ref_id)
        ]


class FrameworkQuery(BaseModel):
    """Framework search/query parameters."""

    # Query parameters
    query_text: str | None = Field(None, description="Text search query")
    framework_types: list[FrameworkType] = Field(
        default_factory=list, description="Target frameworks"
    )

    # Filters
    sections: list[str] = Field(default_factory=list, description="Section filters")
    severity_levels: list[SeverityLevel] = Field(
        default_factory=list, description="Severity filters"
    )
    compliance_status: list[ComplianceStatus] = Field(
        default_factory=list, description="Compliance filters"
    )
    tags: list[str] = Field(default_factory=list, description="Tag filters")

    # Search options
    include_related: bool = Field(
        default=False, description="Include related references"
    )
    exact_match: bool = Field(default=False, description="Exact text match")
    case_sensitive: bool = Field(default=False, description="Case sensitive search")

    # Pagination
    limit: int = Field(default=50, ge=1, le=200, description="Result limit")
    offset: int = Field(default=0, ge=0, description="Result offset")

    # Sorting
    sort_by: str = Field(default="relevance", description="Sort field")
    sort_order: str = Field(
        default="desc", pattern="^(asc|desc)$", description="Sort order"
    )


class FrameworkSearchResult(BaseModel):
    """Framework search result."""

    # Result metadata
    query: FrameworkQuery = Field(..., description="Original query")
    total_results: int = Field(..., description="Total matching results")
    returned_results: int = Field(..., description="Results in this response")

    # Results
    references: list[FrameworkReference] = Field(
        default_factory=list, description="Matching references"
    )
    sections: list[FrameworkSection] = Field(
        default_factory=list, description="Matching sections"
    )

    # Search metadata
    search_time_ms: float = Field(..., description="Search execution time")
    cache_hit: bool = Field(default=False, description="Result was cached")

    # Pagination
    has_more: bool = Field(default=False, description="More results available")
    next_offset: int | None = Field(None, description="Next page offset")

    # Cross-framework analysis
    framework_coverage: dict[FrameworkType, int] = Field(
        default_factory=dict, description="Results per framework"
    )
    compliance_summary: dict[ComplianceStatus, int] = Field(
        default_factory=dict, description="Compliance distribution"
    )
    severity_distribution: dict[SeverityLevel, int] = Field(
        default_factory=dict, description="Severity distribution"
    )


class FrameworkAnalytics(BaseModel):
    """Framework analytics and metrics."""

    # Overall statistics
    total_frameworks: int = Field(default=0)
    total_references: int = Field(default=0)
    total_sections: int = Field(default=0)
    total_mappings: int = Field(default=0)

    # Framework breakdown
    framework_stats: dict[FrameworkType, dict[str, Any]] = Field(default_factory=dict)

    # Compliance metrics
    compliance_coverage: dict[ComplianceStatus, int] = Field(default_factory=dict)
    compliance_percentage: float = Field(default=0.0, ge=0.0, le=100.0)

    # Search analytics
    search_volume: int = Field(default=0, description="Total searches performed")
    cache_hit_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Cache hit rate"
    )
    average_search_time: float = Field(
        default=0.0, description="Average search time in ms"
    )

    # Performance metrics
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    data_freshness: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Data freshness score"
    )


class ExportFormat(str, Enum):
    """Supported export formats for framework data."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


class ExportFilter(BaseModel):
    """Advanced filtering criteria for framework exports."""

    # Framework selection
    framework_types: list[FrameworkType] = Field(
        default_factory=list, description="Frameworks to include in export"
    )

    # Content filters
    sections: list[str] = Field(
        default_factory=list, description="Specific sections to include"
    )
    categories: list[str] = Field(
        default_factory=list, description="Categories to filter by"
    )
    tags: list[str] = Field(default_factory=list, description="Tags to filter by")

    # Status filters
    severity_levels: list[SeverityLevel] = Field(
        default_factory=list, description="Severity levels to include"
    )
    compliance_status: list[ComplianceStatus] = Field(
        default_factory=list, description="Compliance status to include"
    )

    # Text search
    search_terms: list[str] = Field(
        default_factory=list, description="Terms to search for in content"
    )
    exclude_terms: list[str] = Field(
        default_factory=list, description="Terms to exclude from results"
    )

    # Date filters
    updated_after: datetime | None = Field(
        None, description="Include items updated after this date"
    )
    updated_before: datetime | None = Field(
        None, description="Include items updated before this date"
    )

    # Content options
    include_descriptions: bool = Field(
        default=True, description="Include full descriptions in export"
    )
    include_urls: bool = Field(default=True, description="Include URLs in export")
    include_metadata: bool = Field(default=True, description="Include metadata fields")


class ExportRequest(BaseModel):
    """Export request configuration."""

    format: ExportFormat = Field(..., description="Export format")
    filters: ExportFilter = Field(
        default_factory=ExportFilter, description="Export filters"
    )

    # Export options
    filename: str | None = Field(None, description="Custom filename for export")
    include_summary: bool = Field(
        default=True, description="Include summary statistics"
    )
    include_analytics: bool = Field(default=False, description="Include analytics data")

    # CSV specific options
    csv_delimiter: str = Field(default=",", description="CSV field delimiter")
    csv_include_headers: bool = Field(
        default=True, description="Include headers in CSV"
    )

    # Markdown specific options
    markdown_include_toc: bool = Field(
        default=True, description="Include table of contents in markdown"
    )
    markdown_include_links: bool = Field(
        default=True, description="Include clickable links in markdown"
    )


class ExportResult(BaseModel):
    """Export operation result."""

    # Export metadata
    export_id: str = Field(..., description="Unique export identifier")
    request: ExportRequest = Field(..., description="Original export request")

    # Results
    content: str = Field(..., description="Exported content")
    content_size: int = Field(..., description="Content size in bytes")

    # Statistics
    total_items: int = Field(default=0, description="Total items exported")
    total_frameworks: int = Field(default=0, description="Frameworks included")
    total_references: int = Field(default=0, description="References exported")
    total_sections: int = Field(default=0, description="Sections exported")

    # Export metadata
    export_time_ms: float = Field(..., description="Export execution time")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Content validation
    is_valid: bool = Field(default=True, description="Content passed validation")
    validation_errors: list[str] = Field(
        default_factory=list, description="Validation error messages"
    )
