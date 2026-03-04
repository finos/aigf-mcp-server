"""Shared compatibility event service for OpenEMCP-style internal telemetry."""

from __future__ import annotations

from collections import deque
from typing import Any

from finos_mcp.compat import OpenEMCPPhase, create_envelope


class CompatEventService:
    """In-memory compatibility event sink."""

    def __init__(self, *, max_events: int = 256) -> None:
        self._events: deque = deque(maxlen=max_events)

    def record_event(
        self,
        *,
        phase: OpenEMCPPhase,
        payload: dict[str, object],
        correlation_id: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Record a compatibility envelope."""
        envelope = create_envelope(
            phase=phase,
            payload=payload,
            correlation_id=correlation_id,
            metadata=metadata or {},
        )
        self._events.append(envelope)

    def buffered_count(self) -> int:
        """Return number of currently buffered events."""
        return len(self._events)

    def snapshot(self) -> list[dict[str, Any]]:
        """Return a JSON-safe snapshot of buffered events."""
        return [event.model_dump(mode="json") for event in self._events]
