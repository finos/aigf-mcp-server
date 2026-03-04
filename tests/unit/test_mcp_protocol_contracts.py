"""Protocol contract assertions to catch MCP-facing regressions."""

from __future__ import annotations

import inspect

import pytest

from finos_mcp.fastmcp_server import (
    get_cache_stats,
    get_service_health,
    list_frameworks,
    list_mitigations,
    list_risks,
    mcp,
)


async def _invoke(tool_obj, *args, **kwargs):
    """Invoke decorated tools across function and FunctionTool representations."""
    if hasattr(tool_obj, "fn"):
        result = tool_obj.fn(*args, **kwargs)
    else:
        result = tool_obj(*args, **kwargs)

    if inspect.isawaitable(result):
        return await result
    return result


@pytest.mark.unit
class TestMCPProtocolContracts:
    """Contract checks for MCP tool descriptors and required response fields."""

    @pytest.mark.asyncio
    async def test_mcp_surface_counts(self):
        """Server should expose the expected number of MCP primitives."""
        tools = await mcp.get_tools()
        resources = await mcp.get_resource_templates()
        prompts = await mcp.get_prompts()

        assert len(tools) == 11
        assert len(resources) == 3
        assert len(prompts) == 3

    @pytest.mark.asyncio
    async def test_search_tool_parameter_contract(self):
        """Search tools should preserve public query/limit schema bounds."""
        tools = await mcp.get_tools()
        for tool_name in ("search_frameworks", "search_risks", "search_mitigations"):
            params = tools[tool_name].parameters
            assert params["type"] == "object"
            assert params["required"] == ["query"]
            assert params["properties"]["limit"]["minimum"] == 1
            assert params["properties"]["limit"]["maximum"] == 20
            assert params["properties"]["limit"]["default"] == 5

    @pytest.mark.asyncio
    async def test_monitoring_required_fields_remain_stable(self):
        """Health/cache responses must keep required backward-compatible fields."""
        health = await _invoke(get_service_health)
        cache = await _invoke(get_cache_stats)

        health_payload = health.model_dump()
        cache_payload = cache.model_dump()

        for key in (
            "status",
            "version",
            "uptime_seconds",
            "healthy_services",
            "total_services",
        ):
            assert key in health_payload

        for key in ("total_requests", "cache_hits", "cache_misses", "hit_rate"):
            assert key in cache_payload

    @pytest.mark.asyncio
    async def test_list_tools_keep_required_fields(self):
        """List responses must preserve required fields with additive extensions only."""
        frameworks = await _invoke(list_frameworks)
        risks = await _invoke(list_risks)
        mitigations = await _invoke(list_mitigations)

        assert frameworks.total_count >= 0
        assert isinstance(frameworks.frameworks, list)
        assert frameworks.source in ("github_api", "unavailable", None)

        assert risks.total_count >= 0
        assert isinstance(risks.documents, list)
        assert risks.source in ("github_api", "unavailable")

        assert mitigations.total_count >= 0
        assert isinstance(mitigations.documents, list)
        assert mitigations.source in ("github_api", "unavailable")
