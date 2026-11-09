"""Pydantic models for structured tool output (``models.py``).

Moved here whole from ``test_fastmcp_server.py`` in #141.

``TestErrorHandling`` arrives split: it held one model test and one tool test, so
its other half lives in ``test_tool_results.py``. The class name is preserved on
both halves deliberately -- #141 was executed as a pure move, and keeping the
name keeps every nodeid's ``Class::test`` tail identical to what it was before,
which is what made "nothing was silently dropped" a computation rather than a
reading.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from finos_mcp.models import (
    CacheStats,
    DocumentList,
    Framework,
    FrameworkContent,
    FrameworkList,
    ServiceHealth,
)


@pytest.mark.unit
class TestStructuredOutputModels:
    """Test Pydantic models for structured output."""

    def test_framework_model(self):
        """Test Framework model validation."""
        framework = Framework(
            id="test-framework", name="Test Framework", description="A test framework"
        )
        assert framework.id == "test-framework"
        assert framework.name == "Test Framework"
        assert framework.description == "A test framework"

    def test_framework_list_model(self):
        """Test FrameworkList model validation."""
        frameworks = [
            Framework(id="fw1", name="Framework 1", description="Description 1"),
            Framework(id="fw2", name="Framework 2", description="Description 2"),
        ]

        framework_list = FrameworkList(
            frameworks=frameworks, total_count=2, source="github_api"
        )
        assert len(framework_list.frameworks) == 2
        assert framework_list.total_count == 2
        assert framework_list.frameworks[0].id == "fw1"

    def test_framework_content_model(self):
        """Test FrameworkContent model validation."""
        content = FrameworkContent(
            framework_id="test-fw",
            title="Test Framework",
            content="Test content",
            entry_count=3,
        )
        assert content.framework_id == "test-fw"
        assert content.content == "Test content"
        assert content.entry_count == 3

    def test_document_list_model(self):
        """Test DocumentList model validation."""
        docs: list[Any] = [
            {
                "id": "doc1",
                "name": "Document 1",
                "filename": "doc1.md",
                "description": "Desc 1",
            },
            {
                "id": "doc2",
                "name": "Document 2",
                "filename": "doc2.md",
                "description": "Desc 2",
            },
        ]

        doc_list = DocumentList(
            documents=docs, total_count=2, document_type="risk", source="cache"
        )
        assert len(doc_list.documents) == 2
        assert doc_list.total_count == 2
        assert doc_list.document_type == "risk"

        # A fifth source value is refused, and a list has no source by
        # default (#333).
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DocumentList(
                documents=docs,
                total_count=2,
                document_type="risk",
                source="test",  # type: ignore[arg-type]
            )
        with pytest.raises(ValidationError):
            DocumentList(documents=docs, total_count=2, document_type="risk")  # type: ignore[call-arg]

    def test_service_health_model(self):
        """Test ServiceHealth model validation."""
        health = ServiceHealth(
            status="healthy",
            uptime_seconds=123.45,
            version="1.0.0",
            healthy_services=4,
            total_services=4,
        )
        assert health.status == "healthy"
        assert health.uptime_seconds == 123.45
        assert health.version == "1.0.0"
        assert health.healthy_services == 4

    def test_cache_stats_model(self):
        """Test CacheStats model validation."""
        stats = CacheStats(
            total_requests=100, cache_hits=75, cache_misses=25, hit_rate=0.75
        )
        assert stats.total_requests == 100
        assert stats.cache_hits == 75
        assert stats.cache_misses == 25
        assert stats.hit_rate == 0.75


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling in FastMCP tools."""

    def test_pydantic_validation_errors(self):
        """Test that Pydantic models validate input correctly."""
        # Test missing required fields
        with pytest.raises(ValidationError):
            Framework()  # type: ignore[call-arg]  # Missing required fields

        # Test invalid data types
        with pytest.raises(ValidationError):
            CacheStats(
                total_requests="invalid",  # type: ignore[arg-type]  # Should be int
                cache_hits=75,
                cache_misses=25,
                hit_rate=0.75,
            )
