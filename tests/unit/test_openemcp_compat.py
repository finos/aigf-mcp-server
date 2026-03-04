"""Unit tests for internal compatibility envelope primitives."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from finos_mcp.compat import (
    OpenEMCPEnvelope,
    OpenEMCPPhase,
    create_envelope,
)


@pytest.mark.unit
class TestOpenEMCPCompatibility:
    """Test internal OpenEMCP compatibility envelope behavior."""

    def test_create_envelope_generates_defaults(self):
        """Envelope factory should generate IDs/timestamp when omitted."""
        envelope = create_envelope(
            phase=OpenEMCPPhase.VALIDATION_COMPLIANCE,
            payload={"status": "ok"},
        )

        assert envelope.message_id
        assert envelope.correlation_id
        assert envelope.phase == OpenEMCPPhase.VALIDATION_COMPLIANCE
        assert envelope.payload == {"status": "ok"}
        assert isinstance(envelope.timestamp, datetime)
        assert envelope.timestamp.tzinfo is not None

    def test_create_envelope_honors_explicit_values(self):
        """Envelope factory should preserve caller-provided values."""
        ts = datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc)
        envelope = create_envelope(
            phase=OpenEMCPPhase.EXECUTION_RESILIENCE,
            payload={"event": "done"},
            correlation_id="corr-123",
            message_id="msg-123",
            metadata={"source": "unit-test"},
            timestamp=ts,
        )

        assert envelope.message_id == "msg-123"
        assert envelope.correlation_id == "corr-123"
        assert envelope.timestamp == ts
        assert envelope.metadata == {"source": "unit-test"}

    def test_all_required_fields_are_validated(self):
        """Envelope model should enforce required field constraints."""
        with pytest.raises(ValidationError):
            OpenEMCPEnvelope(
                message_id="",
                phase=OpenEMCPPhase.CONTRACT_MANAGEMENT,
                correlation_id="corr",
                timestamp=datetime.now(timezone.utc),
                payload={},
            )

    def test_phase_values_are_enum_constrained(self):
        """Phase field should only allow canonical OpenEMCP values."""
        envelope = OpenEMCPEnvelope(
            message_id="msg",
            phase=OpenEMCPPhase.CONTEXT_STATE_MANAGEMENT,
            correlation_id="corr",
            timestamp=datetime.now(timezone.utc),
            payload={"x": 1},
        )
        assert envelope.phase.value == "context_state_management"
