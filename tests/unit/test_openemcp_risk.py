"""Unit tests for compatibility risk context primitives."""

import pytest
from pydantic import ValidationError

from finos_mcp.compat import (
    OpenEMCPRiskContext,
    OpenEMCPRiskTier,
    build_risk_context_from_signals,
    default_risk_context,
)


@pytest.mark.unit
class TestOpenEMCPRiskContext:
    """Validate risk context defaults, validation, and signal mapping."""

    def test_default_risk_context_is_safe(self):
        risk = default_risk_context()
        assert risk.risk_tier == OpenEMCPRiskTier.LOW
        assert risk.composite_risk_score == 0.0
        assert risk.circuit_breaker_trips == 0

    def test_risk_context_enforces_score_bounds(self):
        with pytest.raises(ValidationError):
            OpenEMCPRiskContext(composite_risk_score=1.2)

    def test_build_from_signals_produces_canonical_tier(self):
        risk = build_risk_context_from_signals(
            phase_assessed="execution_resilience",
            boundary_open_count=2,
            circuit_breaker_trips=3,
            cache_hit_rate=0.20,
            failed_requests=20,
            total_requests=100,
        )

        assert risk.phase_assessed == "execution_resilience"
        assert 0.0 <= risk.composite_risk_score <= 1.0
        assert risk.risk_tier in (
            OpenEMCPRiskTier.LOW,
            OpenEMCPRiskTier.MEDIUM,
            OpenEMCPRiskTier.HIGH,
            OpenEMCPRiskTier.CRITICAL,
        )
        assert "operational_risk" in risk.dimension_scores
        assert risk.circuit_breaker_trips == 3
        assert isinstance(risk.risk_flags, list)
