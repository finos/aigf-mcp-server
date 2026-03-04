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
from typing import Annotated, Any
from uuid import uuid4

import yaml
from fastmcp import FastMCP
from fastmcp.server.auth import JWTVerifier
from pydantic import BaseModel, Field

from . import __version__
from .api.prompts import register_prompts
from .api.resources import register_resources
from .api.tools import (
    get_document_payload,
    get_framework_payload,
    list_documents_payload,
    list_frameworks_payload,
    search_documents_payload,
    search_frameworks_payload,
)
from .application.services import (
    CompatEventService,
    ObservabilityProjectionService,
    PromptCompositionService,
    best_match_index,
    clean_search_snippet,
)
from .application.use_cases import (
    execute_get_document,
    execute_get_framework,
    execute_list_documents,
    execute_list_frameworks,
    execute_search_documents,
    execute_search_frameworks,
    format_framework_name,
)
from .compat import (
    OpenEMCPPhase,
    build_risk_context_from_signals,
    normalize_validation_status,
)
from .config import Settings, validate_settings_on_startup
from .content.cache import get_cache
from .content.discovery import (
    DiscoveryServiceManager,
)
from .content.service import get_content_service
from .infrastructure.repositories import FrameworkRepository, RiskMitigationRepository
from .logging import get_logger
from .security.error_handler import secure_error_handler
from .security.request_validator import dos_protector, request_size_validator

# Initialize configuration and logging
settings = validate_settings_on_startup()
logger = get_logger("fastmcp_server")

# Configure global DoS protection from validated settings.
dos_protector.max_requests_per_minute = settings.dos_max_requests_per_minute
dos_protector.max_concurrent_requests = settings.dos_max_concurrent_requests
dos_protector.request_timeout = settings.dos_request_timeout_seconds

# Fixed client ID for stdio transport (single-client model).
# HTTP transports share this limit; extend to per-IP tracking when MCP exposes
# request context in tool handlers.
_DOS_CLIENT_ID = "mcp_client"


async def _apply_dos_protection() -> None:
    """Enforce rate and concurrency limits. Raises ValueError on violation."""
    await dos_protector.periodic_cleanup()
    if not await dos_protector.check_rate_limit(_DOS_CLIENT_ID):
        raise ValueError("Rate limit exceeded. Please slow down and try again later.")


def _build_auth_provider(app_settings: Settings) -> JWTVerifier | None:
    """Build the MCP auth provider from validated application settings."""
    if not app_settings.mcp_auth_enabled:
        logger.warning(
            "MCP auth is DISABLED. The server will accept requests from any client "
            "without authentication. Set FINOS_MCP_MCP_AUTH_ENABLED=true and configure "
            "FINOS_MCP_MCP_AUTH_JWKS_URI (or MCP_AUTH_PUBLIC_KEY) for production deployments."
        )
        return None

    if app_settings.mcp_auth_jwks_uri:
        logger.info("MCP auth enabled using JWKS verifier")
        return JWTVerifier(
            jwks_uri=app_settings.mcp_auth_jwks_uri,
            issuer=app_settings.mcp_auth_issuer,
            audience=app_settings.mcp_auth_audience,
            required_scopes=app_settings.mcp_auth_scopes_list or None,
        )
    else:
        logger.info("MCP auth enabled using static public key verifier")
        return JWTVerifier(
            public_key=app_settings.mcp_auth_public_key,
            issuer=app_settings.mcp_auth_issuer,
            audience=app_settings.mcp_auth_audience,
            required_scopes=app_settings.mcp_auth_scopes_list or None,
        )


# Create FastMCP server instance
mcp = FastMCP(settings.server_name, auth=_build_auth_provider(settings))
_SERVER_START_TIME = time.monotonic()
_compat_event_service = CompatEventService(max_events=256)
_observability_projection_service = ObservabilityProjectionService(
    _compat_event_service
)
_prompt_composition_service = PromptCompositionService()


def _record_compat_event(
    *,
    phase: OpenEMCPPhase,
    payload: dict[str, object],
    correlation_id: str,
    metadata: dict[str, object] | None = None,
) -> None:
    """Record an internal OpenEMCP compatibility envelope."""
    _compat_event_service.record_event(
        phase=phase,
        payload=payload,
        correlation_id=correlation_id,
        metadata=metadata,
    )


def _tool_annotations(*, title: str, open_world: bool) -> dict[str, bool | str]:
    """Return MCP tool behavior hints aligned with MCP annotation guidance."""
    return {
        "title": title,
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": open_world,
    }


def _resource_annotations(*, priority: float = 0.8) -> dict[str, object]:
    """Return MCP resource annotations for audience targeting and ranking."""
    return {
        "audience": ["assistant"],
        "priority": priority,
    }


# Structured output models
class Framework(BaseModel):
    """Framework information."""

    id: str
    name: str
    description: str
    title: str | None = None


class FrameworkList(BaseModel):
    """List of available frameworks."""

    frameworks: list[Framework]
    total_count: int
    source: str | None = None
    message: str | None = None


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
    message: str | None = None


class DocumentInfo(BaseModel):
    """Document information."""

    id: str
    name: str
    filename: str
    description: str | None = None
    last_modified: str | None = None
    title: str | None = None


class DocumentList(BaseModel):
    """List of documents."""

    documents: list[DocumentInfo]
    total_count: int
    document_type: str
    source: str  # "github_api", "cache", or "unavailable"
    message: str | None = None


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
    observability: dict[str, object] | None = None


class CacheStats(BaseModel):
    """Cache statistics."""

    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    sets: int | None = None
    deletes: int | None = None
    expires: int | None = None
    evictions: int | None = None
    clears: int | None = None
    current_size: int | None = None
    max_size: int | None = None
    memory_usage_bytes: int | None = None
    observability: dict[str, object] | None = None


def _safe_external_error(error: Exception, fallback_message: str) -> str:
    """Return a sanitized error message safe for tool/resource responses."""
    try:
        return secure_error_handler.create_safe_error_response(str(error))
    except Exception:
        return fallback_message


def _validate_request_params(**params: object) -> None:
    """Validate request parameter size limits for DoS protection."""
    request_size_validator.validate_request_params_size(dict(params))


def _safe_resource_content(content: str, resource_id: str) -> str:
    """Validate resource output size and return safe response on violations."""
    try:
        request_size_validator.validate_resource_size(content)
        return content
    except ValueError as e:
        logger.warning(
            "Resource payload exceeded size limit for %s: %s", resource_id, e
        )
        return _safe_external_error(
            e,
            "Resource payload exceeded allowed size limits. Please narrow your query.",
        )


def _safe_document_content(
    content: str, document_id: str, fallback_message: str
) -> tuple[str, list[str]]:
    """Validate large document payloads and return a safe fallback on overflow."""
    try:
        request_size_validator.validate_resource_size(content)
        sections = [
            line.strip("#").strip()
            for line in content.split("\n")
            if line.startswith("#")
        ]
        return content, sections
    except ValueError as e:
        logger.warning("Document payload too large for %s: %s", document_id, e)
        return _safe_external_error(e, fallback_message), []


# Content Service Integration - Async-Safe Singleton Pattern
class AsyncServiceManager:
    """Thread-safe and async-safe service manager for content service."""

    def __init__(self):
        self._service = None
        self._lock: asyncio.Lock | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def _ensure_loop_context(self) -> asyncio.Lock:
        """Ensure service lock/resources are bound to the active event loop."""
        current_loop = asyncio.get_running_loop()
        if (
            self._loop is None
            or self._loop.is_closed()
            or self._loop is not current_loop
        ):
            self._service = None
            self._loop = current_loop
            self._lock = asyncio.Lock()
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get_service(self):
        """Get content service instance with double-checked locking pattern."""
        lock = await self._ensure_loop_context()
        if self._service is None:
            async with lock:
                if self._service is None:
                    logger.debug("Initializing content service")
                    self._service = await get_content_service()
                    logger.debug("Content service initialized successfully")
        return self._service

    async def close_service(self):
        """Close and cleanup service resources."""
        lock = await self._ensure_loop_context()
        if self._service is not None:
            async with lock:
                if self._service is not None:
                    logger.debug("Closing content service")
                    # If the service has a close method, call it
                    if hasattr(self._service, "close"):
                        await self._service.close()
                    self._service = None
                    logger.debug("Content service closed")


# Global service manager instance
_service_manager = AsyncServiceManager()

# Module-level DiscoveryServiceManager singleton.
# Tool handlers previously called DiscoveryServiceManager() on every
# invocation, constructing a new Python wrapper object each time even though
# the underlying singleton state is held in class variables.  A module-level
# instance avoids the unnecessary allocation on every call.
_discovery_manager = DiscoveryServiceManager()


async def get_service():
    """Get content service instance safely."""
    return await _service_manager.get_service()


async def close_service():
    """Close content service safely."""
    await _service_manager.close_service()


_framework_repository = FrameworkRepository(
    discovery_manager=_discovery_manager,
    get_service=lambda: get_service(),
)
_risk_mitigation_repository = RiskMitigationRepository(
    discovery_manager=_discovery_manager,
    get_service=lambda: get_service(),
)


# Repository Tools with Structured Output


@mcp.tool(
    annotations=_tool_annotations(
        title="List Governance Frameworks",
        open_world=True,
    )
)
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
    payload = await list_frameworks_payload(
        apply_dos=_apply_dos_protection,
        execute_list_frameworks_fn=execute_list_frameworks,
        repository=_framework_repository,
        logger=logger,
    )
    frameworks = [Framework(**item) for item in payload["frameworks"]]
    return FrameworkList(
        frameworks=frameworks,
        total_count=payload["total_count"],
        source=payload.get("source"),
        message=payload.get("message"),
    )


def _format_framework_name(framework_id: str) -> str:
    """Format framework ID into a readable name."""
    return format_framework_name(framework_id)


# Acronyms that should be fully uppercased when they appear as words in a name.
_KNOWN_ACRONYMS: frozenset[str] = frozenset(
    {"ai", "mcp", "llm", "qos", "ddos", "dow", "rbac", "ip"}
)

# Common English function words that stay lowercase in title case (except when first).
_LOWERCASE_WORDS: frozenset[str] = frozenset(
    {"and", "or", "the", "a", "an", "of", "for", "in", "to", "with", "as"}
)


def _format_document_name(filename: str, prefix: str) -> str:
    """Format a document filename into a clean human-readable name.

    Examples:
        "ri-9_data-poisoning.md",  "ri-" -> "Data Poisoning (RI-9)"
        "mi-20_mcp-server-security-governance.md", "mi-" -> "MCP Server Security Governance (MI-20)"
    """
    stem = filename.removesuffix(".md")
    if stem.startswith(prefix):
        stem = stem[len(prefix) :]

    # Split number from slug on the first underscore.
    parts = stem.split("_", 1)
    if len(parts) == 2 and parts[0].isdigit():
        number, slug = parts
    else:
        number, slug = "", stem

    # Clean slug: strip trailing punctuation artifacts, replace hyphens with spaces.
    raw_words = slug.rstrip("- ").replace("-", " ").split()
    words = []
    for i, word in enumerate(raw_words):
        lower = word.lower()
        if lower in _KNOWN_ACRONYMS:
            words.append(word.upper())
        elif i > 0 and lower in _LOWERCASE_WORDS:
            words.append(lower)
        else:
            words.append(word.capitalize())

    clean_name = " ".join(words)
    label = prefix.rstrip("-").upper()
    return f"{clean_name} ({label}-{number})" if number else clean_name


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


@mcp.tool(
    annotations=_tool_annotations(
        title="Get Framework Content",
        open_world=True,
    )
)
async def get_framework(
    framework: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            description="Framework identifier from list_frameworks() (e.g. nist-ai-600-1).",
        ),
    ],
) -> FrameworkContent:
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
    payload = await get_framework_payload(
        framework_id=framework,
        apply_dos=_apply_dos_protection,
        validate_request_params=_validate_request_params,
        execute_get_framework_fn=execute_get_framework,
        repository=_framework_repository,
        format_yaml_content=_format_yaml_content,
        validate_resource_size=request_size_validator.validate_resource_size,
        safe_external_error=_safe_external_error,
        logger=logger,
    )
    return FrameworkContent(**payload)


@mcp.tool(
    annotations=_tool_annotations(
        title="List Governance Risks",
        open_world=True,
    )
)
async def list_risks() -> DocumentList:
    """List all available AI governance risk documents for threat assessment and security planning.

    Use this tool to discover security risks, privacy threats, and compliance vulnerabilities
    in AI systems. Each risk document provides detailed threat analysis, impact assessment,
    and contextual information for risk management decisions.

    Returns:
        DocumentList: Structured list of risk documents with metadata, descriptions, and file information.
        Perfect for risk cataloging, threat modeling, and security assessment workflows.
    """
    payload = await list_documents_payload(
        document_type="risk",
        prefix="ri-",
        discover_file_infos=_risk_mitigation_repository.discover_risk_file_infos,
        format_document_name=_format_document_name,
        apply_dos=_apply_dos_protection,
        execute_list_documents_fn=execute_list_documents,
        logger=logger,
    )
    docs = [DocumentInfo(**item) for item in payload["documents"]]
    return DocumentList(
        documents=docs,
        total_count=payload["total_count"],
        document_type=payload["document_type"],
        source=payload["source"],
        message=payload.get("message"),
    )


@mcp.tool(
    annotations=_tool_annotations(
        title="List Governance Mitigations",
        open_world=True,
    )
)
async def list_mitigations() -> DocumentList:
    """List all available AI governance mitigation strategies for risk reduction and security controls.

    Use this tool to discover security controls, privacy safeguards, and compliance measures
    for AI systems. Each mitigation document provides actionable controls, implementation guidance,
    and best practices for reducing identified risks and threats.

    Returns:
        DocumentList: Structured list of mitigation documents with metadata, descriptions, and file information.
        Essential for security planning, control implementation, and compliance remediation.
    """
    payload = await list_documents_payload(
        document_type="mitigation",
        prefix="mi-",
        discover_file_infos=_risk_mitigation_repository.discover_mitigation_file_infos,
        format_document_name=_format_document_name,
        apply_dos=_apply_dos_protection,
        execute_list_documents_fn=execute_list_documents,
        logger=logger,
    )
    docs = [DocumentInfo(**item) for item in payload["documents"]]
    return DocumentList(
        documents=docs,
        total_count=payload["total_count"],
        document_type=payload["document_type"],
        source=payload["source"],
        message=payload.get("message"),
    )


@mcp.tool(
    annotations=_tool_annotations(
        title="Get Risk Content",
        open_world=True,
    )
)
async def get_risk(
    risk_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=256,
            description="Risk document identifier from list_risks().",
        ),
    ],
) -> DocumentContent:
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
    payload = await get_document_payload(
        requested_id=risk_id,
        doc_type="risk",
        prefix="ri-",
        discover_filenames=_risk_mitigation_repository.discover_risk_filenames,
        get_document_by_filename=_risk_mitigation_repository.get_document,
        format_document_name=_format_document_name,
        safe_document_content=_safe_document_content,
        safe_external_error=_safe_external_error,
        apply_dos=_apply_dos_protection,
        validate_request_params=_validate_request_params,
        execute_get_document_fn=execute_get_document,
        logger=logger,
    )
    return DocumentContent(**payload)


@mcp.tool(
    annotations=_tool_annotations(
        title="Get Mitigation Content",
        open_world=True,
    )
)
async def get_mitigation(
    mitigation_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=256,
            description="Mitigation document identifier from list_mitigations().",
        ),
    ],
) -> DocumentContent:
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
    payload = await get_document_payload(
        requested_id=mitigation_id,
        doc_type="mitigation",
        prefix="mi-",
        discover_filenames=_risk_mitigation_repository.discover_mitigation_filenames,
        get_document_by_filename=_risk_mitigation_repository.get_document,
        format_document_name=_format_document_name,
        safe_document_content=_safe_document_content,
        safe_external_error=_safe_external_error,
        apply_dos=_apply_dos_protection,
        validate_request_params=_validate_request_params,
        execute_get_document_fn=execute_get_document,
        logger=logger,
    )
    return DocumentContent(**payload)


@mcp.tool(
    annotations=_tool_annotations(
        title="Service Health",
        open_world=False,
    )
)
async def get_service_health() -> ServiceHealth:
    """Get real service health status by querying each subsystem.

    Returns:
        Structured health information with actual subsystem counts.
    """
    await _apply_dos_protection()

    # Query actual subsystem diagnostics instead of hardcoding values.
    total_services = 4  # fetch, cache, parser, config
    healthy_services = 0
    overall_status = "healthy"
    correlation_id = str(uuid4())
    phase = OpenEMCPPhase.CONTEXT_STATE_MANAGEMENT
    boundaries: dict[str, dict[str, object]] = {}
    failure_count = 0
    total_requests = 0
    cache_hit_rate: float | None = None

    _record_compat_event(
        phase=phase,
        correlation_id=correlation_id,
        payload={"event": "start", "tool": "get_service_health"},
        metadata={"source": "tool"},
    )

    try:
        service = await get_service()
        diagnostics = await service.get_service_diagnostics()

        # Count healthy error boundaries (circuit breakers that are closed)
        boundaries = diagnostics.get("error_boundaries", {})
        healthy_boundaries = sum(
            1 for b in boundaries.values() if b.get("status") == "closed"
        )
        # Circuit breakers cover fetch + cache (2 of 4 subsystems)
        healthy_services += healthy_boundaries

        # Parser subsystem is healthy if parser stats are accessible
        if "parser_statistics" in diagnostics:
            healthy_services += 1

        # Config subsystem is always healthy if we reached this point
        healthy_services += 1

        service_health = diagnostics.get("service_health", {})
        failure_count = int(service_health.get("failed_requests", 0))
        total_requests = int(service_health.get("total_requests", 0))
        cache_hit_rate = service_health.get("cache_hit_rate")

        if healthy_services < total_services:
            overall_status = "degraded"

    except Exception as e:
        logger.warning("Failed to collect subsystem diagnostics: %s", e)
        # Cannot determine real status; report degraded rather than lying
        overall_status = "degraded"
        healthy_services = 0

    boundary_open_count = sum(
        1 for b in boundaries.values() if b.get("status") != "closed"
    )
    risk_context = build_risk_context_from_signals(
        phase_assessed=phase.value,
        boundary_open_count=boundary_open_count,
        circuit_breaker_trips=boundary_open_count,
        cache_hit_rate=cache_hit_rate,
        failed_requests=failure_count,
        total_requests=total_requests,
    )
    canonical_status = normalize_validation_status(
        "approved" if overall_status == "healthy" else "modified"
    )

    _record_compat_event(
        phase=phase,
        correlation_id=correlation_id,
        payload={
            "event": "success",
            "tool": "get_service_health",
            "status": overall_status,
            "validation_status": canonical_status.value,
            "risk_tier": risk_context.risk_tier.value,
        },
        metadata={"source": "tool"},
    )

    observability = _observability_projection_service.build_health_observability(
        phase=phase,
        correlation_id=correlation_id,
        service_status=overall_status,
        risk_context=risk_context,
    )

    return ServiceHealth(
        status=overall_status,
        uptime_seconds=time.monotonic() - _SERVER_START_TIME,
        version=__version__,
        healthy_services=healthy_services,
        total_services=total_services,
        observability=observability,
    )


@mcp.tool(
    annotations=_tool_annotations(
        title="Cache Statistics",
        open_world=False,
    )
)
async def get_cache_stats() -> CacheStats:
    """Get cache statistics.

    Returns:
        Structured cache performance information.
    """
    correlation_id = str(uuid4())
    phase = OpenEMCPPhase.EXECUTION_RESILIENCE
    _record_compat_event(
        phase=phase,
        correlation_id=correlation_id,
        payload={"event": "start", "tool": "get_cache_stats"},
        metadata={"source": "tool"},
    )

    try:
        await _apply_dos_protection()
        cache = await get_cache()
        stats = await cache.get_stats()
        total_requests = stats.hits + stats.misses
        hit_rate = (stats.hits / total_requests) if total_requests > 0 else 0.0
        risk_context = build_risk_context_from_signals(
            phase_assessed=phase.value,
            cache_hit_rate=hit_rate,
            failed_requests=stats.misses,
            total_requests=total_requests,
        )
        canonical_status = normalize_validation_status(
            "approved" if hit_rate >= 0.5 else "modified"
        )
        _record_compat_event(
            phase=phase,
            correlation_id=correlation_id,
            payload={
                "event": "success",
                "tool": "get_cache_stats",
                "validation_status": canonical_status.value,
                "hit_rate": round(hit_rate, 4),
                "risk_tier": risk_context.risk_tier.value,
            },
            metadata={"source": "tool"},
        )
        observability = _observability_projection_service.build_cache_observability(
            phase=phase,
            correlation_id=correlation_id,
            cache_hit_rate=hit_rate,
            risk_context=risk_context,
        )
        return CacheStats(
            total_requests=total_requests,
            cache_hits=stats.hits,
            cache_misses=stats.misses,
            hit_rate=hit_rate,
            sets=stats.sets,
            deletes=stats.deletes,
            expires=stats.expires,
            evictions=stats.evictions,
            clears=stats.clears,
            current_size=stats.current_size,
            max_size=stats.max_size,
            memory_usage_bytes=stats.memory_usage_bytes,
            observability=observability,
        )
    except Exception as e:
        logger.warning("Failed to get real cache stats, returning safe defaults: %s", e)
        canonical_status = normalize_validation_status("modified")
        _record_compat_event(
            phase=phase,
            correlation_id=correlation_id,
            payload={
                "event": "error",
                "tool": "get_cache_stats",
                "validation_status": canonical_status.value,
                "error_type": type(e).__name__,
            },
            metadata={"source": "tool"},
        )
        risk_context = build_risk_context_from_signals(
            phase_assessed=phase.value,
            cache_hit_rate=0.0,
            failed_requests=1,
            total_requests=1,
        )
        observability = _observability_projection_service.build_cache_observability(
            phase=phase,
            correlation_id=correlation_id,
            cache_hit_rate=0.0,
            risk_context=risk_context,
        )
        return CacheStats(
            total_requests=0,
            cache_hits=0,
            cache_misses=0,
            hit_rate=0.0,
            observability=observability,
        )


# Simple Search Tools


async def _call_registered_tool(tool_obj, *args, **kwargs):
    """Invoke a registered FastMCP FunctionTool via its wrapped function.

    SECURITY NOTE — intentional auth bypass:
    This helper calls tool_obj.fn() directly, which bypasses the FastMCP JWT
    auth middleware layer.  This is by design: callers of this function are
    @mcp.prompt() handlers that have already been authenticated at the MCP
    boundary.  Prompt handlers are permitted to internally delegate to tool
    functions without re-authenticating, because the initial auth context
    covers the full scope of the prompt execution.  Any new callers of this
    helper must also be authenticated entry points; do not call it from
    unauthenticated code paths.
    """
    result = tool_obj.fn(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def _search_single_framework(
    framework: Framework, query: str
) -> list[SearchResult]:
    """Search within a single framework document (helper function for parallel processing)."""
    try:
        # Get framework content
        content = await _call_registered_tool(get_framework, framework.id)

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
            snippet = clean_search_snippet(content.content, query, match_index)

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


@mcp.tool(
    annotations=_tool_annotations(
        title="Search Frameworks",
        open_world=True,
    )
)
async def search_frameworks(
    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=512,
            description="Search terms or concepts to find across frameworks.",
        ),
    ],
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=20,
            description="Maximum number of results to return (1-20).",
        ),
    ] = 5,
) -> SearchResults:
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
    payload = await search_frameworks_payload(
        query=query,
        limit=limit,
        apply_dos=_apply_dos_protection,
        validate_request_params=_validate_request_params,
        execute_search_frameworks_fn=execute_search_frameworks,
        list_frameworks_fn=lambda: _call_registered_tool(list_frameworks),
        search_single_framework_fn=_search_single_framework,
        logger=logger,
    )
    return SearchResults(**payload)


async def _search_single_document(
    *,
    document: DocumentInfo,
    query: str,
    get_document_fn: Any,
    framework_prefix: str,
    log_label: str,
) -> list[tuple[SearchResult, bool, int]]:
    """Search within a single risk/mitigation document."""
    try:
        doc = await _call_registered_tool(get_document_fn, document.id)
        content = doc.content
        match_index, is_exact = best_match_index(content, query)
        if match_index == -1:
            return []

        section = document.name
        for line in reversed(content[:match_index].splitlines()[-10:]):
            if line.strip().startswith("#"):
                section = line.strip("#").strip()
                break

        snippet = clean_search_snippet(content, query, match_index)
        return [
            (
                SearchResult(
                    framework_id=f"{framework_prefix}-{document.id}",
                    section=section,
                    content=snippet,
                ),
                is_exact,
                match_index,
            )
        ]
    except Exception as e:
        logger.warning("Failed to search %s %s: %s", log_label, document.id, e)
        return []


async def _search_single_risk(
    risk_doc: DocumentInfo, query: str
) -> list[tuple[SearchResult, bool, int]]:
    """Search wrapper for risk documents."""
    return await _search_single_document(
        document=risk_doc,
        query=query,
        get_document_fn=get_risk,
        framework_prefix="risk",
        log_label="risk",
    )


@mcp.tool(
    annotations=_tool_annotations(
        title="Search Risks",
        open_world=True,
    )
)
async def search_risks(
    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=512,
            description="Search terms or risk concepts to find.",
        ),
    ],
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=20,
            description="Maximum number of results to return (1-20).",
        ),
    ] = 5,
) -> SearchResults:
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
    payload = await search_documents_payload(
        query=query,
        limit=limit,
        label="risk",
        apply_dos=_apply_dos_protection,
        validate_request_params=_validate_request_params,
        execute_search_documents_fn=execute_search_documents,
        list_documents_fn=lambda: _call_registered_tool(list_risks),
        search_single_document_fn=_search_single_risk,
        logger=logger,
    )
    return SearchResults(**payload)


async def _search_single_mitigation(
    mitigation_doc: DocumentInfo, query: str
) -> list[tuple[SearchResult, bool, int]]:
    """Search wrapper for mitigation documents."""
    return await _search_single_document(
        document=mitigation_doc,
        query=query,
        get_document_fn=get_mitigation,
        framework_prefix="mitigation",
        log_label="mitigation",
    )


@mcp.tool(
    annotations=_tool_annotations(
        title="Search Mitigations",
        open_world=True,
    )
)
async def search_mitigations(
    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=512,
            description="Search terms or control concepts to find.",
        ),
    ],
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=20,
            description="Maximum number of results to return (1-20).",
        ),
    ] = 5,
) -> SearchResults:
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
    payload = await search_documents_payload(
        query=query,
        limit=limit,
        label="mitigation",
        apply_dos=_apply_dos_protection,
        validate_request_params=_validate_request_params,
        execute_search_documents_fn=execute_search_documents,
        list_documents_fn=lambda: _call_registered_tool(list_mitigations),
        search_single_document_fn=_search_single_mitigation,
        logger=logger,
    )
    return SearchResults(**payload)


# MCP Resources and Prompts registration (delegated modules)
register_resources(
    mcp=mcp,
    resource_annotations=_resource_annotations,
    validate_request_params=_validate_request_params,
    call_registered_tool=_call_registered_tool,
    safe_resource_content=_safe_resource_content,
    safe_external_error=_safe_external_error,
    get_framework_tool=get_framework,
    get_risk_tool=get_risk,
    get_mitigation_tool=get_mitigation,
    logger=logger,
)

register_prompts(
    mcp=mcp,
    validate_request_params=_validate_request_params,
    call_registered_tool=_call_registered_tool,
    prompt_service=_prompt_composition_service,
    get_framework_tool=get_framework,
    get_risk_tool=get_risk,
    get_mitigation_tool=get_mitigation,
    search_risks_tool=search_risks,
    search_mitigations_tool=search_mitigations,
    logger=logger,
)


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
