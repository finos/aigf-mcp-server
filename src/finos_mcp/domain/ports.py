"""Domain ports (interfaces) for layered architecture boundaries."""

from __future__ import annotations

from typing import Any, Protocol


class FrameworkRepositoryPort(Protocol):
    """Access to framework catalog/content operations."""

    async def list_frameworks(self) -> dict[str, Any]:
        """Return serialized framework catalog payload."""

    async def get_framework(self, framework_id: str) -> dict[str, Any]:
        """Return serialized framework content payload."""

    async def search_frameworks(self, query: str, limit: int) -> dict[str, Any]:
        """Return serialized framework search payload."""


class RiskRepositoryPort(Protocol):
    """Access to risk catalog/content operations."""

    async def list_risks(self) -> dict[str, Any]:
        """Return serialized risk catalog payload."""

    async def get_risk(self, risk_id: str) -> dict[str, Any]:
        """Return serialized risk content payload."""

    async def search_risks(self, query: str, limit: int) -> dict[str, Any]:
        """Return serialized risk search payload."""


class MitigationRepositoryPort(Protocol):
    """Access to mitigation catalog/content operations."""

    async def list_mitigations(self) -> dict[str, Any]:
        """Return serialized mitigation catalog payload."""

    async def get_mitigation(self, mitigation_id: str) -> dict[str, Any]:
        """Return serialized mitigation content payload."""

    async def search_mitigations(self, query: str, limit: int) -> dict[str, Any]:
        """Return serialized mitigation search payload."""


class CachePort(Protocol):
    """Minimal cache operations required by application services."""

    async def get_stats(self) -> Any:
        """Return cache statistics snapshot."""


class ObservabilityPort(Protocol):
    """Compatibility/observability event sink abstraction."""

    def record_event(self, *, phase: str, payload: dict[str, Any]) -> None:
        """Record an observability event."""
