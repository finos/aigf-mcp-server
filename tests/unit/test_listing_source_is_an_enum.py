# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The three list tools publish ``source`` as an enum of four values with no
default (#333).

``source`` was typed as any string with the four values in a comment, and
``FrameworkList`` defaulted it to ``github_api``: measured from ``tools/list``,
``{"default": "github_api", "type": "string"}``. A fifth value would ship
unnoticed, and a list built without a source claimed a live listing.
"""

from __future__ import annotations

import pytest
from fastmcp import Client

from finos_mcp.fastmcp_server import mcp

LIST_TOOLS = ("list_frameworks", "list_risks", "list_mitigations")
SOURCES = {"github_api", "cache", "expired_cache", "static_fallback"}


@pytest.mark.unit
async def test_each_list_tool_publishes_the_four_sources_and_no_default() -> None:
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    for name in LIST_TOOLS:
        schema = tools[name].output_schema
        assert schema is not None, f"{name} publishes no output schema"
        source = schema["properties"]["source"]
        assert set(source.get("enum", [])) == SOURCES, f"{name}: {source}"
        assert source.get("type") == "string", f"{name}: {source}"
        assert "default" not in source, f"{name}: {source}"
