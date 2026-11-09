"""What the tool functions return when invoked directly.

These call the decorated tools as plain callables -- since FastMCP 3.x, decorators
return the original function -- so they measure ``documents/tools.py`` and
``health_tools.py`` without a protocol round trip. The same calls made *through*
the assembled server live in ``tests/integration/test_fastmcp_integration.py``;
#143 deleted ``test_assembled_server_calls.py``, which used to hold a weaker
copy of them.

Moved here whole from ``test_fastmcp_server.py`` in #141. See
``test_structured_output_models.py`` for why ``TestErrorHandling`` appears in two
files under one name.
"""

import inspect

import pytest

from finos_mcp.documents.tools import (
    get_framework,
    list_frameworks,
    list_mitigations,
    list_risks,
)
from finos_mcp.exceptions import UnknownDocumentError
from finos_mcp.health_tools import get_cache_stats, get_service_health
from finos_mcp.models import (
    CacheStats,
    DocumentList,
    Framework,
    FrameworkContent,
    FrameworkList,
    ServiceHealth,
)


async def _invoke_direct_tool(tool_obj, *args, **kwargs):
    """Invoke a decorated tool directly.

    Since FastMCP 3.x, decorators return the original function, so the decorated symbol
    is the callable.
    """
    result = tool_obj(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


@pytest.mark.unit
class TestFastMCPTools:
    """Test FastMCP tool functions with structured output."""

    @pytest.mark.asyncio
    async def test_list_frameworks(self):
        """Test list_frameworks tool returns structured FrameworkList."""
        result = await _invoke_direct_tool(list_frameworks)

        assert isinstance(result, FrameworkList)
        assert result.total_count > 0
        assert len(result.frameworks) == result.total_count

        # Check first framework structure
        framework = result.frameworks[0]
        assert isinstance(framework, Framework)
        assert framework.id
        assert framework.name

    @pytest.mark.asyncio
    async def test_get_framework_valid_framework(self):
        """Test get_framework with valid framework ID."""
        # "nist-ai-rmf" stood here and is not a framework: this passed on the
        # "not found" record until #193 made an unknown id an error.
        result = await _invoke_direct_tool(get_framework, "nist-ai-600-1")

        assert isinstance(result, FrameworkContent)
        assert result.framework_id == "nist-ai-600-1"
        assert result.content.startswith("# ")
        assert result.entry_count > 0

    @pytest.mark.asyncio
    async def test_get_framework_invalid_framework(self):
        """Test get_framework with invalid framework ID."""
        with pytest.raises(UnknownDocumentError, match="'invalid-framework'"):
            await _invoke_direct_tool(get_framework, "invalid-framework")

    @pytest.mark.asyncio
    async def test_list_risks(self):
        """Test list_risks tool returns structured DocumentList."""
        result = await _invoke_direct_tool(list_risks)

        assert isinstance(result, DocumentList)
        assert result.document_type == "risk"
        assert result.total_count > 0
        assert len(result.documents) == result.total_count

        # Check document structure
        doc = result.documents[0]
        assert hasattr(doc, "id") and doc.id
        assert hasattr(doc, "name") and doc.name

    @pytest.mark.asyncio
    async def test_list_mitigations(self):
        """Test list_mitigations tool returns structured DocumentList."""
        result = await _invoke_direct_tool(list_mitigations)

        assert isinstance(result, DocumentList)
        assert result.document_type == "mitigation"
        assert result.total_count > 0
        assert len(result.documents) == result.total_count

    @pytest.mark.asyncio
    async def test_get_service_health(self):
        """Test get_service_health tool returns structured ServiceHealth."""
        result = await _invoke_direct_tool(get_service_health)

        assert isinstance(result, ServiceHealth)
        assert result.status == "healthy"
        assert result.uptime_seconds > 0
        assert result.version
        assert result.healthy_services > 0
        assert result.total_services > 0

    @pytest.mark.asyncio
    async def test_get_cache_stats(self):
        """Test get_cache_stats tool returns structured CacheStats."""
        result = await _invoke_direct_tool(get_cache_stats)

        assert isinstance(result, CacheStats)
        assert result.total_requests >= 0
        assert result.cache_hits >= 0
        assert result.cache_misses >= 0
        assert 0 <= result.hit_rate <= 1
