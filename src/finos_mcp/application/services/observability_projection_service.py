"""Shared observability projection helpers for MCP tool outputs."""

from __future__ import annotations

from typing import Any

from finos_mcp.application.services.compat_event_service import CompatEventService
from finos_mcp.compat import (
    OpenEMCPPhase,
    OpenEMCPRiskContext,
    normalize_validation_status,
)


class ObservabilityProjectionService:
    """Build additive observability payloads for tool responses."""

    def __init__(self, event_service: CompatEventService) -> None:
        self._event_service = event_service

    def build_health_observability(
        self,
        *,
        phase: OpenEMCPPhase,
        correlation_id: str,
        service_status: str,
        risk_context: OpenEMCPRiskContext,
    ) -> dict[str, Any]:
        """Build health tool observability payload."""
        canonical_status = normalize_validation_status(
            "approved" if service_status == "healthy" else "modified"
        )
        return {
            "openemcp": {
                "phase": phase.value,
                "correlation_id": correlation_id,
                "validation_status": canonical_status.value,
                "compatibility_enabled": True,
                "compat_events_buffered": self._event_service.buffered_count(),
            },
            "risk_context": risk_context.model_dump(mode="json"),
        }

    def build_cache_observability(
        self,
        *,
        phase: OpenEMCPPhase,
        correlation_id: str,
        cache_hit_rate: float,
        risk_context: OpenEMCPRiskContext,
    ) -> dict[str, Any]:
        """Build cache tool observability payload."""
        canonical_status = normalize_validation_status(
            "approved" if cache_hit_rate >= 0.5 else "modified"
        )
        return {
            "openemcp": {
                "phase": phase.value,
                "correlation_id": correlation_id,
                "validation_status": canonical_status.value,
                "compatibility_enabled": True,
                "compat_events_buffered": self._event_service.buffered_count(),
            },
            "risk_context": risk_context.model_dump(mode="json"),
        }
