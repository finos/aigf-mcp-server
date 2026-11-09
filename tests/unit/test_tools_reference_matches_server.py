"""Guards that ``docs/api/mcp-tools.md`` describes the tools the server publishes.

That page is the one per-tool reference (#66). When there were three, their
hand-typed input schemas had lost ``maxLength``, ``minLength`` and
``additionalProperties``, two listing tools were missing ``document_type``,
``list_frameworks`` was missing ``source``, and the health tool documented a
status it never returns. Nothing compared any of it with the server.

So each tool's section is read back here: its **Input Schema** must be the
schema the server publishes, and its **Response Fields** must name the fields
of the output schema, no more and no fewer.

What this does not close: the sentence beside a field. A field that is listed
with a wrong explanation passes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from finos_mcp.fastmcp_server import mcp

pytestmark = pytest.mark.unit

_REFERENCE = Path(__file__).resolve().parents[2] / "docs" / "api" / "mcp-tools.md"

_TOOL_HEADING = re.compile(r"^### ([a-z_]+)\s*$", re.MULTILINE)
_NEXT_SECTION = re.compile(r"^#{1,3} ", re.MULTILINE)
_INPUT_SCHEMA = re.compile(
    r"^\*\*Input Schema\*\*:\n```json\n(.*?)^```", re.MULTILINE | re.DOTALL
)
_RESPONSE_FIELDS = re.compile(
    r"^\*\*Response Fields\*\*:\n(.*?)(?=^\*\*|\Z)", re.MULTILINE | re.DOTALL
)
_FIELD = re.compile(r"^\s*- `([a-z_]+)` \(", re.MULTILINE)


def _sections(text: str) -> dict[str, str]:
    """Each ``### tool`` section of the reference, by tool name."""
    sections = {}
    for heading in _TOOL_HEADING.finditer(text):
        following = _NEXT_SECTION.search(text, heading.end())
        sections[heading.group(1)] = text[
            heading.end() : following.start() if following else len(text)
        ]
    return sections


def _property_names(schema: dict[str, Any]) -> set[str]:
    """Every property an output schema names, nested objects included.

    The server publishes these schemas with nested models written out in
    place. Should one arrive as a ``$ref`` instead, its fields are not read
    and the comparison fails on them rather than passing.
    """
    names: set[str] = set()

    def visit(node: dict[str, Any]) -> None:
        for branch in node.get("anyOf", []):
            visit(branch)
        if "items" in node:
            visit(node["items"])
        for name, child in node.get("properties", {}).items():
            names.add(name)
            visit(child)

    visit(schema)
    return names


async def test_the_reference_has_one_section_per_published_tool() -> None:
    published = {tool.name for tool in await mcp.list_tools()}
    assert len(published) >= 5, f"the server listed only {len(published)} tools"

    documented = set(_sections(_REFERENCE.read_text(encoding="utf-8")))
    assert documented == published, (
        f"{_REFERENCE.name} and the server disagree about which tools exist.\n"
        f"  documented, not published: {sorted(documented - published)}\n"
        f"  published, not documented: {sorted(published - documented)}"
    )


async def test_each_input_schema_is_the_one_the_server_publishes() -> None:
    """A caller builds its arguments from this block, so it has to be exact."""
    sections = _sections(_REFERENCE.read_text(encoding="utf-8"))
    compared = 0
    wrong: list[str] = []
    for tool in await mcp.list_tools():
        shown = _INPUT_SCHEMA.search(sections.get(tool.name, ""))
        if shown is None:
            wrong.append(f"{tool.name}: no **Input Schema** block")
            continue
        compared += 1
        if json.loads(shown.group(1)) != tool.parameters:
            wrong.append(
                f"{tool.name}: the server publishes "
                f"{json.dumps(tool.parameters, sort_keys=True)}"
            )

    assert compared >= 5 or wrong, f"only {compared} input schemas were compared"
    assert not wrong, (
        f"{_REFERENCE.name} shows input schemas the server does not publish:\n  "
        + "\n  ".join(wrong)
    )


async def test_each_response_field_list_names_the_fields_the_server_returns() -> None:
    sections = _sections(_REFERENCE.read_text(encoding="utf-8"))
    fields_read = 0
    wrong: list[str] = []
    for tool in await mcp.list_tools():
        assert tool.output_schema, f"{tool.name} publishes no output schema"
        returned = _property_names(tool.output_schema)
        listed_block = _RESPONSE_FIELDS.search(sections.get(tool.name, ""))
        listed = set(_FIELD.findall(listed_block.group(1))) if listed_block else set()
        fields_read += len(listed)
        if listed != returned:
            wrong.append(
                f"{tool.name}: documented and not returned "
                f"{sorted(listed - returned)}, returned and not documented "
                f"{sorted(returned - listed)}"
            )

    assert fields_read >= 20 or wrong, f"only {fields_read} fields were read"
    assert not wrong, (
        f"{_REFERENCE.name} lists response fields the server does not return, "
        "or leaves out ones it does:\n  " + "\n  ".join(wrong)
    )
