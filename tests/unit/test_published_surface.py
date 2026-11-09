"""The published MCP surface is a contract, and this file is where it is written down.

Issue #87 wants ``fastmcp_server.py`` decomposed, and its own sequencing rule
says not to start before a test asserts the surface is unchanged: moving eleven
tools between modules without one is how a tool quietly disappears, or quietly
changes the name of a parameter that an LLM caller has already learned.

The only invariant that existed before this file pinned the *count*
(``test_tool_description_truth.py``), and its docstring was explicit that it is
a vacuity floor for the description checks rather than a surface contract. A
count of eleven survives renaming ``get_risk`` to ``fetch_risk``, dropping
``risk_id`` for ``id``, or trading a prompt for a tool. Since the exact set is
pinned here, that count assertion has been reduced to the anti-vacuity floor it
always claimed to be, so this file is now the single source of truth for the
tool inventory rather than a rival to it.

**What this file does not catch, stated so it is not mistaken for more.** These
are structural assertions: names, and which parameters are *required*. A
constraint that is loosened rather than removed passes -- drop ``min_length=1``
from ``framework_id`` and every assertion here still holds. Catching that needs
the JSON-Schema keywords compared per parameter, which was considered and not
taken: the reach it adds is smaller than the cost of a test that has to be
regenerated rather than read. If a decomposition ever moves the ``Annotated[...,
Field(...)]`` declarations between modules, that gap is where a regression would
travel.

The expected values are written as literals rather than derived from the server,
because a test that computes its expectation the way the code does cannot
disagree with the code. They are the surface as it stands on the commit that
introduced this file, which is exactly what #87 says must not change.
"""

from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from finos_mcp.fastmcp_server import mcp

#: Every tool the server publishes, and the parameters each one *requires*.
#: Requiring a new one, renaming one, or dropping a tool is a breaking change.
#: Optional parameters are not listed here -- adding one is compatible -- but
#: they are pinned separately in PUBLISHED_TOOL_PARAMETERS below, because
#: *renaming or removing* an optional parameter breaks callers just as surely.
PUBLISHED_TOOLS: dict[str, set[str]] = {
    "get_cache_stats": set(),
    "get_framework": {"framework_id"},
    "get_mitigation": {"mitigation_id"},
    "get_risk": {"risk_id"},
    "get_service_health": set(),
    "list_frameworks": set(),
    "list_mitigations": set(),
    "list_risks": set(),
    "search_frameworks": {"query"},
}

#: Every parameter each tool accepts, required or not. This is the half
#: PUBLISHED_TOOLS deliberately omits. ``search_frameworks`` publishes an
#: optional ``limit``; renaming it to ``max_results`` or dropping it during
#: #87's decomposition breaks every caller that passes it, while every
#: assertion keyed on ``required`` alone still passes.
#:
#: Only the key *set* is pinned, not the schema bodies -- deliberately. Pinning
#: the bodies would make this a generated file that has to be regenerated
#: rather than read, which is the cost the module docstring explains is not
#: worth paying.
PUBLISHED_TOOL_PARAMETERS: dict[str, set[str]] = {
    "get_cache_stats": set(),
    "get_framework": {"framework_id"},
    "get_mitigation": {"mitigation_id"},
    "get_risk": {"risk_id"},
    "get_service_health": set(),
    "list_frameworks": set(),
    "list_mitigations": set(),
    "list_risks": set(),
    "search_frameworks": {"limit", "query"},
}

#: Every prompt, and the arguments each one *requires*. Pinned for the same
#: reason as the tools: all three prompts take two required arguments, so
#: renaming one, or adding a third, is a breaking change that a names-only
#: assertion waves through.
#:
#: Note ``analyze_framework_compliance`` takes ``framework``, not
#: ``framework_id``. That is the very inconsistency the tool side was fixed for
#: -- an LLM that has learned ``framework_id`` from ``get_framework`` will get
#: the prompt call wrong. It is recorded here as the surface that ships today,
#: not endorsed; changing it is a published-surface change and belongs in its
#: own issue rather than inside a refactor that promises to change nothing.
PUBLISHED_PROMPTS: dict[str, set[str]] = {
    "analyze_framework_compliance": {"framework", "use_case"},
    "mitigation_strategy_prompt": {"risk_type", "system_description"},
    "risk_assessment_analysis": {"context", "risk_category"},
}

#: The URI forms. Every plain resource (one per document since #338) is an
#: instance of one of these; a fourth scheme would be a surface change.
PUBLISHED_RESOURCE_TEMPLATES = {
    "finos://frameworks/{framework_id}",
    "finos://mitigations/{mitigation_id}",
    "finos://risks/{risk_id}",
}


@pytest.mark.unit
async def test_the_published_tool_names_are_unchanged() -> None:
    """A rename is a breaking change for every caller that learned the old name."""
    published = {tool.name for tool in await mcp.list_tools()}

    assert published == set(PUBLISHED_TOOLS), (
        f"the published tool set changed. Added: "
        f"{sorted(published - set(PUBLISHED_TOOLS))}. Removed: "
        f"{sorted(set(PUBLISHED_TOOLS) - published)}. If this is deliberate, "
        "update PUBLISHED_TOOLS in the same commit and say why in the message"
    )


@pytest.mark.unit
async def test_a_name_outside_the_published_set_is_rejected() -> None:
    """An unregistered name is refused at the MCP boundary.

    The set equality above measures the *listing*. Dispatch is a separate path,
    so it says nothing about what a caller gets for a twelfth name. This asserts
    that direction.

    Two details are load-bearing. It goes through a real in-memory ``Client``
    rather than ``mcp.get_tool(...)``, so the rejection comes from the server
    rather than from a harness failing to resolve the name; and it matches on
    the message, because the original spelling of this test paired
    ``pytest.raises(Exception)`` with a harness-side lookup and passed without
    the request ever reaching the server.

    **The residual, measured rather than assumed.** This closes the route for a
    name registered *nowhere*. It does not close the gap between the two paths,
    and that gap is real: a ``Middleware.on_list_tools`` hook that filters the
    listing leaves dispatch untouched, and a tool hidden that way answers a
    ``call_tool`` normally while the assertion above still passes. Measured on
    fastmcp 3.4.7 with a two-tool probe server -- the listing reported one name,
    and calling the hidden one returned its result. Nothing here filters the
    listing today (``DoSProtectionMiddleware`` hooks only ``on_request`` and
    ``on_call_tool``), so this is the shape to watch for rather than a live
    defect; a listing filter added later needs its own assertion, because
    neither this test nor the one above would notice.

    Moved here from ``test_assembled_server_calls.py`` in #143, which deleted
    that file. Every other test in it asserted strictly less than an existing
    assertion elsewhere; this one had no counterpart anywhere, and it belongs
    beside the contract it is the converse of.
    """
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="Unknown tool"):
            await client.call_tool("nonexistent_tool", {})


@pytest.mark.unit
async def test_every_tool_requires_the_same_parameters_it_always_did() -> None:
    """Renaming a required parameter breaks callers as surely as renaming a tool.

    ``get_framework`` took ``framework`` while its siblings took ``*_id``, so
    ``get_framework(framework_id=...)`` returned isError -- an LLM infers the
    sibling pattern and fails the call. That was fixed; nothing stopped it
    regressing until this assertion.
    """
    actual = {
        tool.name: set((tool.parameters or {}).get("required") or [])
        for tool in await mcp.list_tools()
    }

    differences = {
        name: {"expected": sorted(expected), "actual": sorted(actual.get(name, set()))}
        for name, expected in PUBLISHED_TOOLS.items()
        if actual.get(name, set()) != expected
    }
    assert not differences, (
        f"required parameters changed for {sorted(differences)}: {differences}"
    )


@pytest.mark.unit
async def test_every_tool_accepts_the_same_parameters_it_always_did() -> None:
    """Optional parameters are part of the surface too.

    The assertion above pins only ``required``, so renaming ``limit`` to
    ``max_results`` on ``search_frameworks`` -- or dropping it -- passes it
    untouched while breaking every caller that passes the argument.
    """
    actual = {
        tool.name: set((tool.parameters or {}).get("properties") or {})
        for tool in await mcp.list_tools()
    }

    differences = {
        name: {"expected": sorted(expected), "actual": sorted(actual.get(name, set()))}
        for name, expected in PUBLISHED_TOOL_PARAMETERS.items()
        if actual.get(name, set()) != expected
    }
    assert not differences, (
        f"the accepted parameter set changed for {sorted(differences)}: {differences}"
    )


@pytest.mark.unit
async def test_the_published_prompts_are_unchanged() -> None:
    """Prompts are part of the surface; a decomposition can drop one silently."""
    published = {prompt.name for prompt in await mcp.list_prompts()}

    assert published == set(PUBLISHED_PROMPTS), (
        f"the published prompt set changed. Added: "
        f"{sorted(published - set(PUBLISHED_PROMPTS))}. Removed: "
        f"{sorted(set(PUBLISHED_PROMPTS) - published)}"
    )


@pytest.mark.unit
async def test_every_prompt_requires_the_same_arguments_it_always_did() -> None:
    """The prompt-side twin of the tool assertion above.

    Prompts declare their arguments as a list of objects rather than a JSON
    Schema, so this reads ``argument.required`` instead of a ``required`` array.
    """
    actual = {
        prompt.name: {arg.name for arg in (prompt.arguments or []) if arg.required}
        for prompt in await mcp.list_prompts()
    }

    differences = {
        name: {"expected": sorted(expected), "actual": sorted(actual.get(name, set()))}
        for name, expected in PUBLISHED_PROMPTS.items()
        if actual.get(name, set()) != expected
    }
    assert not differences, (
        f"required prompt arguments changed for {sorted(differences)}: {differences}"
    )


@pytest.mark.unit
async def test_the_published_resource_templates_are_unchanged() -> None:
    """Templates carry the URI scheme callers construct links against."""
    published = {
        str(template.uri_template) for template in await mcp.list_resource_templates()
    }

    assert published == PUBLISHED_RESOURCE_TEMPLATES, (
        f"the published resource-template set changed. Added: "
        f"{sorted(published - PUBLISHED_RESOURCE_TEMPLATES)}. Removed: "
        f"{sorted(PUBLISHED_RESOURCE_TEMPLATES - published)}"
    )


@pytest.mark.unit
async def test_every_plain_resource_is_an_instance_of_a_published_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The documents are listed as resources (#338) under the three forms above.

    The catalog is stubbed so the listing reads no network; the set of
    documents is the listing tests' concern, the URI forms are this file's.
    """
    from test_listing_descriptions import _CATALOG, _stub_catalog  # type: ignore[import-not-found]

    _stub_catalog(monkeypatch, _CATALOG)
    prefixes = tuple(
        template.split("{", 1)[0] for template in PUBLISHED_RESOURCE_TEMPLATES
    )

    listed = [str(resource.uri) for resource in await mcp.list_resources()]

    assert listed, "no document is published as a resource"
    assert all(uri.startswith(prefixes) for uri in listed), listed
