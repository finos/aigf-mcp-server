"""Unit tests for risk/mitigation repository adapter."""

import pytest

from finos_mcp.infrastructure.repositories import RiskMitigationRepository


class _DiscoveryService:
    async def discover_content(self):
        class _Result:
            def __init__(self):
                self.risk_files = [
                    type("F", (), {"filename": "ri-risk-a.md"})(),
                    type("F", (), {"filename": "ri-risk-b.md"})(),
                ]
                self.mitigation_files = [
                    type("F", (), {"filename": "mi-mit-a.md"})(),
                ]

        return _Result()


class _DiscoveryManager:
    async def get_discovery_service(self):
        return _DiscoveryService()


class _ContentService:
    async def get_document(self, doc_type: str, filename: str):
        if doc_type == "risk" and filename == "ri-risk-a.md":
            return {"content": "risk"}
        return None


async def _get_service():
    return _ContentService()


@pytest.mark.unit
class TestRiskMitigationRepository:
    @pytest.mark.asyncio
    async def test_discover_risk_filenames(self):
        repo = RiskMitigationRepository(
            discovery_manager=_DiscoveryManager(),
            get_service=_get_service,
        )
        filenames = await repo.discover_risk_filenames()
        assert filenames == ["ri-risk-a.md", "ri-risk-b.md"]

    @pytest.mark.asyncio
    async def test_discover_mitigation_filenames(self):
        repo = RiskMitigationRepository(
            discovery_manager=_DiscoveryManager(),
            get_service=_get_service,
        )
        filenames = await repo.discover_mitigation_filenames()
        assert filenames == ["mi-mit-a.md"]

    @pytest.mark.asyncio
    async def test_get_document_dict(self):
        repo = RiskMitigationRepository(
            discovery_manager=_DiscoveryManager(),
            get_service=_get_service,
        )
        doc = await repo.get_document("risk", "ri-risk-a.md")
        assert doc == {"content": "risk"}

    @pytest.mark.asyncio
    async def test_get_document_none(self):
        repo = RiskMitigationRepository(
            discovery_manager=_DiscoveryManager(),
            get_service=_get_service,
        )
        doc = await repo.get_document("risk", "missing.md")
        assert doc is None
