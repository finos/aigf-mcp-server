"""The framework's count and the documents' section titles have different names (#339).

``get_framework`` published ``sections`` as an integer, the number of entries
the framework lists, while ``get_risk`` and ``get_mitigation`` publish
``sections`` as the list of the document's section titles. One field name
with two types across sibling tools: a client that handles one shape
mishandles the other, and a real client called it inconsistent. The count is
``entry_count`` now, and ``sections`` is a list wherever it appears.
"""

from __future__ import annotations

from typing import cast

import pytest
from fastmcp import Client

from finos_mcp.fastmcp_server import mcp


async def _output_properties(tool_name: str) -> dict[str, dict[str, object]]:
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    schema = tools[tool_name].output_schema
    assert schema is not None, f"{tool_name} publishes no output schema"
    return cast("dict[str, dict[str, object]]", schema["properties"])


@pytest.mark.unit
async def test_the_framework_count_is_entry_count_and_not_sections() -> None:
    properties = await _output_properties("get_framework")

    assert properties["entry_count"]["type"] == "integer"
    assert "sections" not in properties


@pytest.mark.unit
@pytest.mark.parametrize("tool_name", ["get_risk", "get_mitigation"])
async def test_sections_is_a_list_wherever_it_is_published(tool_name: str) -> None:
    properties = await _output_properties(tool_name)

    assert properties["sections"]["type"] == "array"
    assert "entry_count" not in properties
