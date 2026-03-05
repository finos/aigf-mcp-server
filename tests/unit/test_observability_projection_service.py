"""Unit tests for observability projection service."""

import pytest

from finos_mcp.application.services import (
    CompatEventService,
    ObservabilityProjectionService,
)
from finos_mcp.compat import OpenEMCPPhase, default_risk_context


@pytest.mark.unit
class TestObservabilityProjectionService:
    def test_build_health_observability_shape(self):
        event_service = CompatEventService(max_events=8)
        projector = ObservabilityProjectionService(event_service)

        payload = projector.build_health_observability(
            phase=OpenEMCPPhase.CONTEXT_STATE_MANAGEMENT,
            correlation_id="corr-health",
            service_status="healthy",
            risk_context=default_risk_context(),
        )

        assert payload["openemcp"]["phase"] == "context_state_management"
        assert payload["openemcp"]["validation_status"] in {
            "approved",
            "rejected",
            "modified",
        }
        assert payload["risk_context"]["risk_tier"] in {
            "low",
            "medium",
            "high",
            "critical",
        }

    def test_build_cache_observability_shape(self):
        event_service = CompatEventService(max_events=8)
        projector = ObservabilityProjectionService(event_service)

        payload = projector.build_cache_observability(
            phase=OpenEMCPPhase.EXECUTION_RESILIENCE,
            correlation_id="corr-cache",
            cache_hit_rate=0.3,
            risk_context=default_risk_context(),
        )

        assert payload["openemcp"]["phase"] == "execution_resilience"
        assert payload["openemcp"]["validation_status"] in {
            "approved",
            "rejected",
            "modified",
        }
