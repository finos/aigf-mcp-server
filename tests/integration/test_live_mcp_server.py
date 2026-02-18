#!/usr/bin/env python3
"""Optional live MCP integration tests against the real stdio server.

These tests are intentionally opt-in because they spawn a subprocess and
exercise the live MCP protocol end-to-end.

Run with:
    FINOS_RUN_LIVE_MCP_TEST=1 ./venv/bin/pytest tests/integration/test_live_mcp_server.py -q
"""

import json
import os
import sys
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FINOS_RUN_LIVE_MCP_TEST") != "1",
        reason="Set FINOS_RUN_LIVE_MCP_TEST=1 to run live MCP subprocess tests",
    ),
]


async def _extract_structured_tool_result(result: Any) -> dict[str, Any]:
    """Extract structured payload from MCP SDK responses across versions."""
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        return result[1]

    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured

    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured

    content = getattr(result, "content", None)
    if isinstance(content, list):
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed

    raise AssertionError("Unable to extract structured tool response")


@pytest.fixture
async def live_session() -> ClientSession:
    """Create a live stdio MCP session against the server module."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "finos_mcp.fastmcp_main"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@pytest.mark.asyncio
async def test_live_tools_and_content_flow(live_session: ClientSession) -> None:
    """Validate a real end-to-end flow with current tool/resource contracts."""
    tools = await live_session.list_tools()
    tool_names = {tool.name for tool in tools}

    expected = {
        "list_frameworks",
        "get_framework",
        "search_frameworks",
        "list_risks",
        "get_risk",
        "search_risks",
        "list_mitigations",
        "get_mitigation",
        "search_mitigations",
        "get_service_health",
        "get_cache_stats",
    }
    assert expected.issubset(tool_names)

    list_mitigations_result = await live_session.call_tool("list_mitigations", {})
    mitigations = await _extract_structured_tool_result(list_mitigations_result)

    assert mitigations["document_type"] == "mitigation"
    assert mitigations["total_count"] > 0
    first_mitigation_id = mitigations["documents"][0]["id"]

    get_mitigation_result = await live_session.call_tool(
        "get_mitigation", {"mitigation_id": first_mitigation_id}
    )
    mitigation = await _extract_structured_tool_result(get_mitigation_result)

    assert mitigation["document_id"] == first_mitigation_id
    assert isinstance(mitigation["content"], str)
    assert len(mitigation["content"]) > 100

    # Resource IDs match tool IDs (e.g., "1_ai-data-...", not "mi-1").
    resource_uri = f"finos://mitigations/{first_mitigation_id}"
    resource_result = await live_session.read_resource(resource_uri)
    assert resource_result is not None

    search_result = await live_session.call_tool(
        "search_mitigations", {"query": "data", "limit": 3}
    )
    search_payload = await _extract_structured_tool_result(search_result)
    assert search_payload["query"] == "data"
    assert isinstance(search_payload["results"], list)
