"""Internal OpenEMCP compatibility models and helpers.

This module provides additive, internal-only primitives used to normalize
events and telemetry to OpenEMCP-like structures without changing MCP tool
contracts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class OpenEMCPPhase(str, Enum):
    """Canonical OpenEMCP phase identifiers."""

    CONTRACT_MANAGEMENT = "contract_management"
    PLANNING_NEGOTIATION = "planning_negotiation"
    VALIDATION_COMPLIANCE = "validation_compliance"
    EXECUTION_RESILIENCE = "execution_resilience"
    CONTEXT_STATE_MANAGEMENT = "context_state_management"
    COMMUNICATION_DELIVERY = "communication_delivery"


class OpenEMCPEnvelope(BaseModel):
    """Internal compatibility envelope for phase events."""

    message_id: str = Field(min_length=1)
    phase: OpenEMCPPhase
    correlation_id: str = Field(min_length=1)
    timestamp: datetime
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


def create_envelope(
    *,
    phase: OpenEMCPPhase,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    message_id: str | None = None,
    timestamp: datetime | None = None,
) -> OpenEMCPEnvelope:
    """Create an OpenEMCP-compatible internal envelope with safe defaults."""
    return OpenEMCPEnvelope(
        message_id=message_id or str(uuid4()),
        phase=phase,
        correlation_id=correlation_id or str(uuid4()),
        timestamp=timestamp or datetime.now(timezone.utc),
        payload=payload,
        metadata=metadata or {},
    )
