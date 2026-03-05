"""Repository adapters for risk and mitigation discovery/content access."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class RiskMitigationRepository:
    """Adapter for risk and mitigation discovery/content retrieval."""

    def __init__(
        self,
        *,
        discovery_manager: Any,
        get_service: Callable[[], Awaitable[Any]],
    ) -> None:
        self._discovery_manager = discovery_manager
        self._get_service = get_service

    @staticmethod
    def _assert_available(discovery_result: Any) -> None:
        source = getattr(discovery_result, "source", "github_api")
        if source == "unavailable":
            message = getattr(
                discovery_result,
                "message",
                "Risk and mitigation discovery is currently unavailable.",
            )
            raise RuntimeError(message)

    async def _discover(self) -> Any:
        discovery_service = await self._discovery_manager.get_discovery_service()
        result = await discovery_service.discover_content()
        self._assert_available(result)
        return result

    async def discover_risk_file_infos(self) -> list[Any]:
        result = await self._discover()
        return result.risk_files

    async def discover_mitigation_file_infos(self) -> list[Any]:
        result = await self._discover()
        return result.mitigation_files

    async def discover_risk_filenames(self) -> list[str]:
        infos = await self.discover_risk_file_infos()
        return [x.filename for x in infos]

    async def discover_mitigation_filenames(self) -> list[str]:
        infos = await self.discover_mitigation_file_infos()
        return [x.filename for x in infos]

    async def get_document(self, doc_type: str, filename: str) -> dict[str, Any] | None:
        service = await self._get_service()
        doc = await service.get_document(doc_type, filename)
        if isinstance(doc, dict):
            return doc
        return None
