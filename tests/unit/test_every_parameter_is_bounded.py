# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Every tool, resource template and prompt parameter has a bound, and the
bound refuses an argument before the function runs (#322).

A 100 kB parameter size check opened every tool, resource and prompt body.
No argument could reach it: the widest ``Field`` bound is 4000 characters,
and fastmcp refuses a longer value before it calls the function. The check
and the error sanitiser behind it are gone. What protects is the bound each
parameter declares, so this test reads that bound off the published schema
(tools) or the function's own annotations (resource templates, prompts) and
sends one more than it allows through a real client.

A tool or resource argument is refused by pydantic, whose message names the
bound. A prompt argument is refused by fastmcp's argument conversion, whose
message names the argument; for prompts the at-bound value is sent too, with
the body replaced by a sentinel, so the bound is pinned on both sides.
"""

from __future__ import annotations

import typing
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp.prompts.function_prompt import FunctionPrompt
from fastmcp.resources.template import FunctionResourceTemplate
from mcp.shared.exceptions import MCPError
from pydantic import TypeAdapter

from finos_mcp import prompts as prompts_module
from finos_mcp.fastmcp_server import mcp

BODY_RAN = "the body ran: BODY_RAN_SENTINEL"


def _bound(owner: str, name: str, schema: dict[str, Any]) -> tuple[str, int]:
    """The kind and the upper bound a parameter's JSON schema declares."""
    if schema.get("type") == "string":
        assert "maxLength" in schema, f"{owner} {name!r} has no maxLength"
        return "string", int(schema["maxLength"])
    if schema.get("type") == "integer":
        assert "maximum" in schema, f"{owner} {name!r} has no maximum"
        return "integer", int(schema["maximum"])
    pytest.fail(f"{owner} {name!r} is a {schema.get('type')!r}; add a bound rule")


def _over(kind: str, bound: int) -> Any:
    return "x" * (bound + 1) if kind == "string" else bound + 1


def _at(kind: str, bound: int, schema: dict[str, Any]) -> Any:
    if kind == "string":
        return "x" * bound
    return int(schema.get("minimum", bound))


def _refused_text(kind: str, bound: int) -> str:
    """What pydantic says for one over the bound."""
    if kind == "string":
        return f"String should have at most {bound} characters"
    return f"Input should be less than or equal to {bound}"


def _annotation_schemas(fn: Any) -> dict[str, dict[str, Any]]:
    hints = typing.get_type_hints(fn, include_extras=True)
    return {
        name: TypeAdapter(hint).json_schema()
        for name, hint in hints.items()
        if name != "return"
    }


async def _tool_parameters() -> list[tuple[str, str, dict[str, Any], dict[str, Any]]]:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    found = []
    for tool in tools:
        properties = (tool.input_schema or {}).get("properties", {})
        for name, schema in properties.items():
            found.append((tool.name, name, schema, properties))
    return found


@pytest.mark.unit
async def test_a_tool_argument_over_its_bound_is_refused_before_the_tool_runs() -> None:
    parameters = await _tool_parameters()
    assert parameters, "no tool takes a parameter; the surface changed"
    async with Client(mcp) as client:
        for tool, name, schema, siblings in parameters:
            kind, bound = _bound(tool, name, schema)
            arguments = {
                other: _at(*_bound(tool, other, s), s)
                for other, s in siblings.items()
                if other != name
            }
            arguments[name] = _over(kind, bound)
            with pytest.raises(ToolError) as refusal:
                await client.call_tool(tool, arguments)
            message = str(refusal.value)
            assert name in message and _refused_text(kind, bound) in message, (
                f"{tool} {name!r}: {message!r}"
            )


@pytest.mark.unit
async def test_a_resource_id_over_its_bound_is_refused_before_the_read() -> None:
    templates = await mcp.list_resource_templates()
    assert templates, "no resource template; the surface changed"
    async with Client(mcp) as client:
        for template in templates:
            assert isinstance(template, FunctionResourceTemplate), template
            for name, schema in _annotation_schemas(template.fn).items():
                kind, bound = _bound(template.uri_template, name, schema)
                uri = template.uri_template.replace(f"{{{name}}}", _over(kind, bound))
                with pytest.raises(MCPError) as refusal:
                    await client.read_resource(uri)
                message = str(refusal.value)
                assert name in message and _refused_text(kind, bound) in message, (
                    f"{template.uri_template} {name!r}: {message!r}"
                )


@pytest.mark.unit
async def test_a_prompt_argument_over_its_bound_is_refused_and_one_at_it_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _body_ran(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError(BODY_RAN)

    for tool in ("get_framework", "list_risks", "list_mitigations"):
        monkeypatch.setattr(prompts_module, tool, _body_ran)

    async with Client(mcp) as client:
        prompts = await client.list_prompts()
        assert prompts, "no prompt; the surface changed"
        for listed in prompts:
            prompt = await mcp.get_prompt(listed.name)
            assert isinstance(prompt, FunctionPrompt), prompt
            schemas = _annotation_schemas(prompt.fn)
            for name, schema in schemas.items():
                kind, bound = _bound(listed.name, name, schema)
                at_bound = {
                    other: _at(*_bound(listed.name, other, s), s)
                    for other, s in schemas.items()
                }
                with pytest.raises(MCPError) as reached:
                    await client.get_prompt(listed.name, at_bound)
                assert BODY_RAN in str(reached.value), (
                    f"{listed.name} {name!r} at its bound did not reach the body: "
                    f"{reached.value!r}"
                )
                over = dict(at_bound, **{name: _over(kind, bound)})
                with pytest.raises(MCPError) as refusal:
                    await client.get_prompt(listed.name, over)
                message = str(refusal.value)
                assert BODY_RAN not in message, f"{listed.name} {name!r}: {message!r}"
                assert f"Could not convert argument '{name}'" in message, (
                    f"{listed.name} {name!r}: {message!r}"
                )
