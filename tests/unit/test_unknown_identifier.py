# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""An id that does not exist is an error on every surface (#193).

``get_risk("does-not-exist")`` used to return an ordinary result
(``isError: false``) titled "Risk does-not-exist not found", with a sentence
saying so in the field a caller reads as the document. A model can take a
successful tool result for an answer. The three ``finos://`` resources served
the same sentence as a ``text/markdown`` body, and
``analyze_framework_compliance`` embedded it as the framework to analyse.

Every test here goes through a client session against the assembled server,
because the defect was in what a client receives: called directly, the tool
returned a record whose title said "not found", which is what the earlier
tests asserted and why they passed.
"""

from __future__ import annotations

import pytest
from fastmcp import Client
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS

from finos_mcp.fastmcp_server import mcp

UNKNOWN = "does-not-exist"

#: tool, its parameter, and the listing tool that holds the valid ids.
GET_TOOLS = [
    ("get_risk", "risk_id", "list_risks"),
    ("get_mitigation", "mitigation_id", "list_mitigations"),
    ("get_framework", "framework_id", "list_frameworks"),
]


@pytest.mark.unit
@pytest.mark.parametrize(("tool", "parameter", "listing"), GET_TOOLS)
async def test_a_get_tool_reports_an_unknown_id_as_an_error(
    tool: str, parameter: str, listing: str
) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            tool, {parameter: UNKNOWN}, raise_on_error=False
        )

    assert result.is_error, f"{tool} answered an unknown id as a success"
    assert result.structured_content is None, (
        f"{tool} sent a document record alongside the error"
    )
    message = result.content[0].text
    # Names the id that failed and where the valid ones are, so the caller's
    # next step is in the message.
    assert f"'{UNKNOWN}'" in message
    assert listing in message


#: resource URI for an unknown id, and the listing tool that holds the valid ids.
RESOURCES = [
    (f"finos://risks/{UNKNOWN}", "list_risks"),
    (f"finos://mitigations/{UNKNOWN}", "list_mitigations"),
    (f"finos://frameworks/{UNKNOWN}", "list_frameworks"),
]


@pytest.mark.unit
@pytest.mark.parametrize(("uri", "listing"), RESOURCES)
async def test_a_resource_read_for_an_unknown_id_fails(uri: str, listing: str) -> None:
    """The body of a resource is the document, so there is nowhere to say "no"."""
    async with Client(mcp) as client:
        with pytest.raises(MCPError) as refusal:
            await client.read_resource(uri)

    # The code fastmcp gives a URI no template matches: to a client, an id no
    # document has is the same event.
    assert refusal.value.error.code == INVALID_PARAMS
    message = str(refusal.value)
    assert f"'{UNKNOWN}'" in message
    assert listing in message


@pytest.mark.unit
async def test_the_compliance_prompt_refuses_a_framework_that_does_not_exist() -> None:
    """It used to embed "Framework 'x' was not found" as the framework to analyse."""
    async with Client(mcp) as client:
        with pytest.raises(MCPError) as refusal:
            await client.get_prompt(
                "analyze_framework_compliance",
                {"framework": UNKNOWN, "use_case": "a customer service chatbot"},
            )

    # No code is pinned: fastmcp wraps whatever a prompt function raises as an
    # internal error (-32603), an MCPError included, and keeps only the message.
    message = str(refusal.value)
    assert f"'{UNKNOWN}'" in message
    assert "list_frameworks" in message
