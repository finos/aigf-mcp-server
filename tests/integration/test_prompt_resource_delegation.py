"""Contract tests for prompts and resources that delegate to tool functions.

The three prompts and three resources all reach their data by calling a registered
tool function. That delegation is the one part of this server with no always-on
coverage, and it is exactly what the FastMCP 2.x -> 3.x upgrade breaks: in 3.x a
`@mcp.tool()` decorator returns the original function rather than a component
object, so any indirection through a `.fn` attribute raises AttributeError.

Two failure shapes make this worth testing through a real client rather than by
calling the handlers directly:

  * A prompt surfaces the break as an MCPError, which is loud.
  * A resource did not, until #216. Every resource handler wrapped its body in
    `except Exception` and returned the error text as the resource body, so
    `read_resource` still succeeded with non-empty content. A test that asserted
    only that content came back passed against a completely broken resource.

So these tests assert on the *content* that came back, not on its truthiness, and
they drive the production `mcp` object over the MCP protocol rather than importing
the handlers and calling them.

Upstream lookups are stubbed, so the tests are hermetic and assert that the
delegated payload actually reached the caller.
"""

import pytest
from fastmcp import Client

from finos_mcp import prompts as _prompts
from finos_mcp import resources as _resources
from finos_mcp.fastmcp_server import mcp
from finos_mcp.models import (
    DocumentContent,
    DocumentInfo,
    DocumentList,
    FrameworkContent,
)

pytestmark = [pytest.mark.integration]

# Marker text that can only appear in a response if the delegated call actually
# returned this stub's payload. An error string cannot contain it.
SENTINEL = "DELEGATION-SENTINEL-8fd21c"


#: Which module binds each name. Since #87 split the server, a prompt calls
#: ``get_framework`` through :mod:`finos_mcp.prompts`'s own namespace, so
#: patching the aggregator would rebind a name that nothing reads.
_BINDINGS = {
    "get_framework": (_prompts, _resources),
    "get_risk": (_resources,),
    "get_mitigation": (_resources,),
    "list_risks": (_prompts,),
    "list_mitigations": (_prompts,),
}


def _patch_everywhere(monkeypatch, name, value, **kwargs) -> None:
    """Patch ``name`` in every module that binds it."""
    for module in _BINDINGS[name]:
        monkeypatch.setattr(module, name, value, **kwargs)


@pytest.fixture
def stub_upstream(monkeypatch):
    """Replace the delegated tool functions with hermetic stubs.

    The prompts and resources look these up as module globals at call time, so
    patching the module attribute intercepts the delegation on both the 2.x
    (`_call_registered_tool(fn, ...)`) and 3.x (direct `await fn(...)`) shapes.
    """

    async def fake_get_framework(framework_id, *_args, **_kwargs):
        return FrameworkContent(
            framework_id=framework_id,
            title=framework_id,
            content=f"{SENTINEL} framework body for {framework_id}",
            entry_count=1,
        )

    def _catalog(kind):
        async def fake_list(*_args, **_kwargs):
            return DocumentList(
                documents=[
                    DocumentInfo(
                        id=f"1_{kind}",
                        name=f"{kind} title",
                        filename=f"1_{kind}.md",
                        description=f"{SENTINEL} {kind} description",
                    )
                ],
                total_count=1,
                document_type=kind,
                source="github_api",
            )

        return fake_list

    async def fake_get_risk(risk_id, *_args, **_kwargs):
        return DocumentContent(
            document_id=risk_id,
            title=f"Risk {risk_id}",
            content=f"{SENTINEL} risk body for {risk_id}",
            sections=["s"],
        )

    async def fake_get_mitigation(mitigation_id, *_args, **_kwargs):
        return DocumentContent(
            document_id=mitigation_id,
            title=f"Mitigation {mitigation_id}",
            content=f"{SENTINEL} mitigation body for {mitigation_id}",
            sections=["s"],
        )

    _patch_everywhere(monkeypatch, "get_framework", fake_get_framework)
    _patch_everywhere(monkeypatch, "get_risk", fake_get_risk)
    _patch_everywhere(monkeypatch, "get_mitigation", fake_get_mitigation)
    _patch_everywhere(monkeypatch, "list_risks", _catalog("risk"))
    _patch_everywhere(monkeypatch, "list_mitigations", _catalog("mitigation"))


def _prompt_text(result) -> str:
    """Flatten a get_prompt result into the text a model would receive."""
    parts = []
    for message in result.messages:
        content = message.content
        text = getattr(content, "text", None)
        parts.append(text if text is not None else str(content))
    return "\n".join(parts)


class TestPromptsDelegateToTools:
    """Each prompt must embed the payload its delegated tool returned."""

    async def test_analyze_framework_compliance_embeds_framework_content(
        self, stub_upstream
    ):
        async with Client(mcp) as client:
            result = await client.get_prompt(
                "analyze_framework_compliance",
                {"framework": "eu-ai-act", "use_case": "credit scoring"},
            )

        text = _prompt_text(result)
        assert SENTINEL in text, "prompt did not embed the delegated tool's payload"
        assert "credit scoring" in text

    async def test_risk_assessment_analysis_embeds_the_catalog(self, stub_upstream):
        async with Client(mcp) as client:
            result = await client.get_prompt(
                "risk_assessment_analysis",
                {"risk_category": "bias", "context": "loan approval model"},
            )

        text = _prompt_text(result)
        assert f"{SENTINEL} risk description" in text, (
            "prompt did not embed the delegated listing"
        )
        assert "id: 1_risk" in text
        assert "loan approval model" in text

    async def test_mitigation_strategy_prompt_embeds_the_catalog(self, stub_upstream):
        async with Client(mcp) as client:
            result = await client.get_prompt(
                "mitigation_strategy_prompt",
                {"risk_type": "privacy", "system_description": "chat assistant"},
            )

        text = _prompt_text(result)
        assert f"{SENTINEL} mitigation description" in text, (
            "prompt did not embed the delegated listing"
        )
        assert "id: 1_mitigation" in text
        assert "chat assistant" in text

    async def test_all_three_prompts_are_registered(self):
        async with Client(mcp) as client:
            names = {prompt.name for prompt in await client.list_prompts()}

        assert {
            "analyze_framework_compliance",
            "risk_assessment_analysis",
            "mitigation_strategy_prompt",
        } <= names


class TestResourcesDelegateToTools:
    """Assert on the body, never on truthiness."""

    @pytest.mark.parametrize(
        ("uri", "expected_fragment"),
        [
            ("finos://frameworks/eu-ai-act", "framework body for eu-ai-act"),
            ("finos://risks/ri-1", "risk body for ri-1"),
            ("finos://mitigations/mi-1", "mitigation body for mi-1"),
        ],
    )
    async def test_resource_returns_delegated_content(
        self, stub_upstream, uri, expected_fragment
    ):
        async with Client(mcp) as client:
            contents = await client.read_resource(uri)

        body = contents[0].text

        # The regression this guards: a broken delegation used to return a
        # non-empty body, because the handler caught the error and returned its
        # text. Only a content assertion distinguished the two.
        assert "has no attribute" not in body, (
            f"resource returned an error body: {body}"
        )
        assert SENTINEL in body, "resource did not return the delegated payload"
        assert expected_fragment in body
