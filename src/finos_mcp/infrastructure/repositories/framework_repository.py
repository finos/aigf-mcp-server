"""Framework repository adapter backed by discovery and content services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class FrameworkRepository:
    """Adapter for framework discovery and document retrieval."""

    def __init__(
        self,
        *,
        discovery_manager: Any,
        get_service: Callable[[], Awaitable[Any]],
    ) -> None:
        self._discovery_manager = discovery_manager
        self._get_service = get_service

    async def discover_framework_file_infos(self) -> list[Any]:
        """Return discovered framework file info objects."""
        discovery_service = await self._discovery_manager.get_discovery_service()
        discovery_result = await discovery_service.discover_content()
        return discovery_result.framework_files

    async def discover_framework_filenames(self) -> list[str]:
        """Return discovered framework filenames."""
        file_infos = await self.discover_framework_file_infos()
        return [file_info.filename for file_info in file_infos]

    async def get_framework_document(self, filename: str) -> dict[str, Any] | None:
        """Fetch a framework document by filename."""
        service = await self._get_service()
        doc = await service.get_document("framework", filename)
        if isinstance(doc, dict):
            return doc
        return None
