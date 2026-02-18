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

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    ListToolsResult,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FINOS_RUN_LIVE_MCP_TEST") != "1",
        reason="Set FINOS_RUN_LIVE_MCP_TEST=1 to run live MCP subprocess tests",
    ),
]


def _extract_tool_payload(result: CallToolResult) -> dict:
    """Extract JSON payload from a tool result text content entry."""
    assert result.content, "Tool result content should not be empty"
    text = result.content[0].text
    assert isinstance(text, str), "Tool response text must be a string"
    parsed = json.loads(text)
    assert isinstance(parsed, dict), "Tool response payload must be a JSON object"
    return parsed


@pytest.mark.asyncio
async def test_live_tools_and_content_flow() -> None:
    """Validate live end-to-end behavior for all tools, resources, and prompts."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "finos_mcp.fastmcp_main"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as live_session:
            await live_session.initialize()

            tools_result: ListToolsResult = await live_session.list_tools()
            tool_names = {tool.name for tool in tools_result.tools}

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

            list_frameworks_result: CallToolResult = await live_session.call_tool(
                "list_frameworks", {}
            )
            frameworks = _extract_tool_payload(list_frameworks_result)
            assert frameworks["total_count"] > 0
            framework_id = frameworks["frameworks"][0]["id"]

            get_framework_result: CallToolResult = await live_session.call_tool(
                "get_framework", {"framework": framework_id}
            )
            framework = _extract_tool_payload(get_framework_result)
            assert framework["framework_id"] == framework_id
            assert isinstance(framework["content"], str)
            assert len(framework["content"]) > 0

            search_frameworks_result: CallToolResult = await live_session.call_tool(
                "search_frameworks", {"query": "risk management", "limit": 3}
            )
            search_frameworks_payload = _extract_tool_payload(search_frameworks_result)
            assert search_frameworks_payload["query"] == "risk management"
            assert isinstance(search_frameworks_payload["results"], list)

            list_risks_result: CallToolResult = await live_session.call_tool(
                "list_risks", {}
            )
            risks = _extract_tool_payload(list_risks_result)
            assert risks["document_type"] == "risk"
            assert risks["total_count"] > 0
            first_risk_id = risks["documents"][0]["id"]

            get_risk_result: CallToolResult = await live_session.call_tool(
                "get_risk", {"risk_id": first_risk_id}
            )
            risk = _extract_tool_payload(get_risk_result)
            assert risk["document_id"] == first_risk_id
            assert isinstance(risk["content"], str)
            assert len(risk["content"]) > 0

            search_risks_result: CallToolResult = await live_session.call_tool(
                "search_risks", {"query": "model risk", "limit": 3}
            )
            search_risks_payload = _extract_tool_payload(search_risks_result)
            assert search_risks_payload["query"] == "model risk"
            assert isinstance(search_risks_payload["results"], list)

            list_mitigations_result: CallToolResult = await live_session.call_tool(
                "list_mitigations", {}
            )
            mitigations = _extract_tool_payload(list_mitigations_result)
            assert mitigations["document_type"] == "mitigation"
            assert mitigations["total_count"] > 0
            first_mitigation_id = mitigations["documents"][0]["id"]

            get_mitigation_result: CallToolResult = await live_session.call_tool(
                "get_mitigation", {"mitigation_id": first_mitigation_id}
            )
            mitigation = _extract_tool_payload(get_mitigation_result)
            assert mitigation["document_id"] == first_mitigation_id
            assert isinstance(mitigation["content"], str)
            assert len(mitigation["content"]) > 0

            search_mitigation_result: CallToolResult = await live_session.call_tool(
                "search_mitigations", {"query": "data", "limit": 3}
            )
            search_mitigation_payload = _extract_tool_payload(search_mitigation_result)
            assert search_mitigation_payload["query"] == "data"
            assert isinstance(search_mitigation_payload["results"], list)

            health_result: CallToolResult = await live_session.call_tool(
                "get_service_health", {}
            )
            health = _extract_tool_payload(health_result)
            assert health["status"] in {"healthy", "degraded", "failing", "critical"}

            cache_result: CallToolResult = await live_session.call_tool(
                "get_cache_stats", {}
            )
            cache = _extract_tool_payload(cache_result)
            assert "hit_rate" in cache

            framework_resource_result = await live_session.read_resource(
                f"finos://frameworks/{framework_id}"
            )
            assert framework_resource_result is not None
            assert framework_resource_result.contents

            risk_resource_result = await live_session.read_resource(
                f"finos://risks/{first_risk_id}"
            )
            assert risk_resource_result is not None
            assert risk_resource_result.contents

            mitigation_resource_result = await live_session.read_resource(
                f"finos://mitigations/{first_mitigation_id}"
            )
            assert mitigation_resource_result is not None
            assert mitigation_resource_result.contents

            prompts_result: ListPromptsResult = await live_session.list_prompts()
            prompt_names = {prompt.name for prompt in prompts_result.prompts}
            assert {
                "analyze_framework_compliance",
                "risk_assessment_analysis",
                "mitigation_strategy_prompt",
            }.issubset(prompt_names)

            compliance_prompt: GetPromptResult = await live_session.get_prompt(
                "analyze_framework_compliance",
                {
                    "framework": framework_id,
                    "use_case": "US retail bank assistant for onboarding and fraud triage",
                },
            )
            assert compliance_prompt.messages

            risk_prompt: GetPromptResult = await live_session.get_prompt(
                "risk_assessment_analysis",
                {
                    "risk_category": "model risk",
                    "context": "US bank assistant handling customer support and KYC workflows",
                },
            )
            assert risk_prompt.messages

            mitigation_prompt: GetPromptResult = await live_session.get_prompt(
                "mitigation_strategy_prompt",
                {
                    "risk_type": "prompt injection",
                    "system_description": "Financial assistant with transaction advisory capabilities",
                },
            )
            assert mitigation_prompt.messages
