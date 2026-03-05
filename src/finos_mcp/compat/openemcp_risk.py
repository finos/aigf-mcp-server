"""Risk context primitives for internal OpenEMCP compatibility."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OpenEMCPRiskTier(str, Enum):
    """Canonical OpenEMCP risk tier values."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OpenEMCPRiskContext(BaseModel):
    """Internal risk context propagated with compatibility events."""

    phase_assessed: str = "validation_compliance"
    composite_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_tier: OpenEMCPRiskTier = OpenEMCPRiskTier.LOW
    dimension_scores: dict[str, float] = Field(
        default_factory=lambda: {
            "financial_risk": 0.0,
            "operational_risk": 0.0,
            "compliance_risk": 0.0,
            "security_risk": 0.0,
        }
    )
    dimension_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "financial_risk": 0.25,
            "operational_risk": 0.20,
            "compliance_risk": 0.30,
            "security_risk": 0.25,
        }
    )
    risk_flags: list[str] = Field(default_factory=list)
    risk_events: list[dict[str, Any]] = Field(default_factory=list)
    circuit_breaker_trips: int = Field(default=0, ge=0)
    assessment_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    assessed_by: str = "finos_mcp_internal"


def _tier_from_score(score: float) -> OpenEMCPRiskTier:
    if score >= 0.80:
        return OpenEMCPRiskTier.CRITICAL
    if score >= 0.60:
        return OpenEMCPRiskTier.HIGH
    if score >= 0.40:
        return OpenEMCPRiskTier.MEDIUM
    return OpenEMCPRiskTier.LOW


def default_risk_context() -> OpenEMCPRiskContext:
    """Return a safe default risk context."""
    return OpenEMCPRiskContext()


def build_risk_context_from_signals(
    *,
    phase_assessed: str,
    boundary_open_count: int = 0,
    circuit_breaker_trips: int = 0,
    cache_hit_rate: float | None = None,
    failed_requests: int = 0,
    total_requests: int = 0,
) -> OpenEMCPRiskContext:
    """Build risk context from existing service/cache signals."""
    safe_cache_hit_rate = (
        max(0.0, min(1.0, cache_hit_rate)) if cache_hit_rate is not None else 0.5
    )
    failure_ratio = (
        (failed_requests / total_requests)
        if total_requests > 0
        else (0.0 if failed_requests == 0 else 1.0)
    )
    failure_ratio = max(0.0, min(1.0, failure_ratio))

    operational_risk = min(
        1.0,
        (boundary_open_count * 0.20)
        + (min(circuit_breaker_trips, 5) * 0.10)
        + (failure_ratio * 0.40)
        + ((1.0 - safe_cache_hit_rate) * 0.15),
    )
    dimension_scores = {
        "financial_risk": 0.05,
        "operational_risk": round(operational_risk, 4),
        "compliance_risk": 0.05,
        "security_risk": 0.05,
    }

    weights = {
        "financial_risk": 0.25,
        "operational_risk": 0.20,
        "compliance_risk": 0.30,
        "security_risk": 0.25,
    }
    composite = sum(dimension_scores[k] * weights[k] for k in weights)
    composite = round(max(0.0, min(1.0, composite)), 4)

    risk_flags: list[str] = []
    if boundary_open_count > 0:
        risk_flags.append("error_boundary_open")
    if circuit_breaker_trips > 0:
        risk_flags.append("circuit_breaker_activity")
    if failure_ratio > 0.05:
        risk_flags.append("elevated_failure_ratio")

    return OpenEMCPRiskContext(
        phase_assessed=phase_assessed,
        composite_risk_score=composite,
        risk_tier=_tier_from_score(composite),
        dimension_scores=dimension_scores,
        dimension_weights=weights,
        risk_flags=risk_flags,
        circuit_breaker_trips=max(0, circuit_breaker_trips),
    )
