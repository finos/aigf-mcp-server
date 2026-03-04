"""Unit tests for compatibility event service."""

import pytest

from finos_mcp.application.services import CompatEventService
from finos_mcp.compat import OpenEMCPPhase


@pytest.mark.unit
class TestCompatEventService:
    def test_records_and_counts_events(self):
        service = CompatEventService(max_events=2)

        service.record_event(
            phase=OpenEMCPPhase.CONTEXT_STATE_MANAGEMENT,
            payload={"event": "start"},
            correlation_id="corr-1",
        )
        assert service.buffered_count() == 1

        service.record_event(
            phase=OpenEMCPPhase.EXECUTION_RESILIENCE,
            payload={"event": "success"},
            correlation_id="corr-2",
        )
        assert service.buffered_count() == 2

        service.record_event(
            phase=OpenEMCPPhase.EXECUTION_RESILIENCE,
            payload={"event": "overflow"},
            correlation_id="corr-3",
        )
        assert service.buffered_count() == 2

    def test_snapshot_returns_json_safe_dicts(self):
        service = CompatEventService(max_events=2)
        service.record_event(
            phase=OpenEMCPPhase.VALIDATION_COMPLIANCE,
            payload={"validation_status": "approved"},
            correlation_id="corr-snap",
            metadata={"source": "test"},
        )

        snapshot = service.snapshot()
        assert len(snapshot) == 1
        assert snapshot[0]["phase"] == "validation_compliance"
        assert snapshot[0]["metadata"]["source"] == "test"
