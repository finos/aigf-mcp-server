# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""A throttled get tool answers with one sentence that never names discovery
(#334).

The sentence interpolated the inner exception, whose text already carried the
"GitHub content discovery failed:" prefix the discovery errors write for the
log, and the tool wrapped the result in a second error that added the prefix
again. Measured, the client text opened by naming discovery for a document
fetch and ran "60 seconds This is" together. The sentence is now built from
the retry time the error carries, and raised as the error whose message is
that sentence verbatim.
"""

from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.shared.exceptions import MCPError

from finos_mcp.content.discovery import DiscoveryServiceManager
from finos_mcp.content.github_api import GitHubFileInfo
from finos_mcp.content.list_file import DiscoveryResult
from finos_mcp.content.service import ContentService
from finos_mcp.exceptions import GitHubRateLimitError
from finos_mcp.fastmcp_server import mcp

pytestmark = pytest.mark.unit

RETRY_AFTER = 60
#: The service's own words, prefix included, as a tool receives them.
INNER = f"GitHub is rate limiting content requests; retry in {RETRY_AFTER} seconds"

SURFACES = [
    pytest.param("get_framework", "framework_id", "eu-ai-act", id="framework"),
    pytest.param("get_risk", "risk_id", "10_prompt-injection", id="risk"),
    pytest.param("get_mitigation", "mitigation_id", "4_ai-firewall", id="mitigation"),
]


class _Discovery:
    async def discover_content(self) -> DiscoveryResult:
        return DiscoveryResult(
            mitigation_files=[GitHubFileInfo(filename="mi-4_ai-firewall.md")],
            risk_files=[GitHubFileInfo(filename="ri-10_prompt-injection.md")],
            framework_files=[GitHubFileInfo(filename="eu-ai-act.yml")],
            source="github_api",
        )


@pytest.fixture
def throttled_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _discovery(_self: object) -> _Discovery:
        return _Discovery()

    async def _throttled(_self: object, *_args: object, **_kwargs: object) -> None:
        raise GitHubRateLimitError(INNER, retry_after=RETRY_AFTER)

    monkeypatch.setattr(DiscoveryServiceManager, "get_discovery_service", _discovery)
    monkeypatch.setattr(ContentService, "get_document", _throttled)


def _reads_as_one_sentence(text: str, doc_id: str) -> None:
    assert text.count("discovery failed") == 0, text
    assert f"'{doc_id}'" in text
    assert f"The limit resets in {RETRY_AFTER} seconds. This is a temporary" in text
    assert INNER not in text, "the inner error's words reached the client"


@pytest.mark.parametrize(("tool", "parameter", "doc_id"), SURFACES)
async def test_a_throttled_get_tool_answers_with_one_sentence(
    throttled_backend: None, tool: str, parameter: str, doc_id: str
) -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError) as refusal:
            await client.call_tool(tool, {parameter: doc_id})
    _reads_as_one_sentence(str(refusal.value), doc_id)


async def test_a_throttled_resource_read_answers_with_the_same_sentence(
    throttled_backend: None,
) -> None:
    async with Client(mcp) as client:
        with pytest.raises(MCPError) as refusal:
            await client.read_resource("finos://risks/10_prompt-injection")
    _reads_as_one_sentence(str(refusal.value), "10_prompt-injection")


async def test_a_throttle_without_a_retry_time_still_reads_as_one_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _discovery(_self: object) -> _Discovery:
        return _Discovery()

    async def _throttled(_self: object, *_args: object, **_kwargs: object) -> None:
        raise GitHubRateLimitError("Resets in 60 seconds.")

    monkeypatch.setattr(DiscoveryServiceManager, "get_discovery_service", _discovery)
    monkeypatch.setattr(ContentService, "get_document", _throttled)

    async with Client(mcp) as client:
        with pytest.raises(ToolError) as refusal:
            await client.call_tool("get_risk", {"risk_id": "10_prompt-injection"})
    text = str(refusal.value)
    assert text.count("discovery failed") == 0, text
    assert "GitHub did not say when the limit resets. This is a temporary" in text
