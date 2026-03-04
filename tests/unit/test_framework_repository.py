"""Unit tests for framework infrastructure repository adapter."""

import pytest

from finos_mcp.infrastructure.repositories import FrameworkRepository


class _DiscoveryService:
    async def discover_content(self):
        class _Result:
            def __init__(self):
                self.framework_files = [
                    type("F", (), {"filename": "eu-ai-act.yml"})(),
                    type("F", (), {"filename": "nist-ai-600-1.yml"})(),
                ]

        return _Result()


class _DiscoveryManager:
    async def get_discovery_service(self):
        return _DiscoveryService()


class _ContentService:
    async def get_document(self, doc_type: str, filename: str):
        if doc_type == "framework" and filename == "eu-ai-act.yml":
            return {"content": "demo"}
        return None


async def _get_service():
    return _ContentService()


@pytest.mark.unit
class TestFrameworkRepository:
    @pytest.mark.asyncio
    async def test_discover_framework_filenames(self):
        repo = FrameworkRepository(
            discovery_manager=_DiscoveryManager(),
            get_service=_get_service,
        )
        filenames = await repo.discover_framework_filenames()
        assert filenames == ["eu-ai-act.yml", "nist-ai-600-1.yml"]

    @pytest.mark.asyncio
    async def test_get_framework_document(self):
        repo = FrameworkRepository(
            discovery_manager=_DiscoveryManager(),
            get_service=_get_service,
        )
        doc = await repo.get_framework_document("eu-ai-act.yml")
        assert doc == {"content": "demo"}

    @pytest.mark.asyncio
    async def test_get_framework_document_none(self):
        repo = FrameworkRepository(
            discovery_manager=_DiscoveryManager(),
            get_service=_get_service,
        )
        doc = await repo.get_framework_document("missing.yml")
        assert doc is None
