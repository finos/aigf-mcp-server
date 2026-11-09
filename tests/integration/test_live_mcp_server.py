#!/usr/bin/env python3
"""Live MCP functional gate: the real stdio server, end to end.

This is the suite that must be green before anything merges into main, because
main is production. It spawns the actual server as a subprocess and drives it
over the MCP protocol, so it exercises the paths a client really takes.

Opt-in via FINOS_RUN_LIVE_MCP_TEST=1 because it spawns a subprocess and reaches
the network. The CI functional-gate job and the pre-push hook both set it, so
"opt-in" no longer means "never runs" -- for most of this file's life nothing
set the flag except scripts/go-live-gate.sh, and a hook set had never run in CI
at all.

Run with:
    FINOS_RUN_LIVE_MCP_TEST=1 ./venv/bin/pytest tests/integration/test_live_mcp_server.py -q

Assertions here are on **content identity**, not payload shape. That distinction
is the whole point of this file. The earlier versions of these checks read:

    assert frameworks["total_count"] > 0
    assert isinstance(framework["content"], str)
    assert isinstance(search_frameworks_payload["results"], list)

Three Jekyll taxonomy files satisfy the first. A Python dict repr dumped into
markdown satisfies the second. An **empty list** satisfies the third. All three
passed while the framework search returned nothing and the catalog could not say
where its data came from. Assert what the answer *is*, not what type it has.
"""

import json
import os
import sys
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    ListToolsResult,
    TextContent,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FINOS_RUN_LIVE_MCP_TEST") != "1",
        reason="Set FINOS_RUN_LIVE_MCP_TEST=1 to run live MCP subprocess tests",
    ),
]

# Governance frameworks the catalog must reach. Frozen rather than derived from
# whatever the catalog happens to return, which is what made the old
# `total_count > 0` check worthless: it agreed with any three files at all.
# These are named in list_frameworks' own description, so a caller is entitled
# to them.
REQUIRED_FRAMEWORK_IDS = frozenset(
    {"eu-ai-act", "nist-ai-600-1", "owasp-llm", "iso-42001"}
)

# Sources that prove live discovery ran. "cache" is a cached *live* listing
# (one-hour TTL), so it qualifies; "static_fallback" is shipped data and does
# not, because it looks identical whether discovery is healthy or misdirected.
# "expired_cache" does not either: it is a list file of any age, served because
# GitHub could not be asked (#264).
LIVE_SOURCES = frozenset({"github_api", "cache"})

# Fragments that only appear when a Python structure has been str()'d into
# markdown instead of formatted.
#: Fragments that only appear when a Python object has been str()'d into the
#: rendered body. The first three catch list-of-dict and dict-of-list shapes;
#: `['` and `{'` catch the commonest one, a plain sequence or mapping value,
#: which the original three missed entirely -- `- **listval**: ['one', 'two']`
#: matches none of them.
REPR_MARKERS = ("[{'", "': ['", "'}]", "['", "{'")


def _catalog_ids_in(prompt: GetPromptResult) -> list[str]:
    """The ids a catalog prompt lists, in the order it lists them."""
    lines = []
    for message in prompt.messages:
        assert isinstance(message.content, TextContent), "Prompt must be text"
        lines.append(message.content.text)
    text = "\n".join(lines)
    return [
        line.removeprefix("id: ")
        for line in text.splitlines()
        if line.startswith("id: ")
    ]


def _extract_tool_payload(result: CallToolResult) -> dict[str, Any]:
    """Extract JSON payload from a tool result text content entry."""
    assert result.content, "Tool result content should not be empty"
    content = result.content[0]
    assert isinstance(content, TextContent), "Tool response must be text content"
    text = content.text
    parsed = json.loads(text)
    assert isinstance(parsed, dict), "Tool response payload must be a JSON object"
    return parsed


#: What every listing description used to be, built from the entry's name.
GENERATED_DESCRIPTION_PREFIXES = (
    "Risk document:",
    "Mitigation strategy:",
    "Framework definition:",
)


def _quoted_from(description: str | None, content: str) -> bool:
    """Whether a listing description is text the document itself contains.

    Compared up to the first colon: a paragraph that introduces a list carries
    the items after it without their markers, which the document does not say
    in that form.
    """
    quoted = (description or "").removesuffix("...").split(":")[0]
    return bool(quoted) and quoted in " ".join(content.split())


def _assert_nothing_generated(entries: list[dict[str, Any]]) -> None:
    """No entry describes itself with its own name, or carries a dead field."""
    assert entries, "an empty listing proves nothing about its entries"
    for entry in entries:
        description = entry["description"]
        assert description is None or (
            not description.startswith(GENERATED_DESCRIPTION_PREFIXES)
            and description != entry["name"]
        ), (
            f"{entry['id']!r} is described as {description!r}: the name again, "
            "not what the document says (#191)"
        )
        assert "last_modified" not in entry, (
            f"{entry['id']!r} publishes last_modified, which nothing populates"
        )


@pytest.mark.asyncio
async def test_live_tools_and_content_flow() -> None:
    """Validate live end-to-end behavior for all tools, resources, and prompts."""
    env = os.environ.copy()

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "finos_mcp.fastmcp_main"],
        env=env,
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
                "list_mitigations",
                "get_mitigation",
                "get_service_health",
                "get_cache_stats",
            }
            # Equal, not a subset: a tool that was removed must stay removed
            # (search_risks and search_mitigations, #208).
            assert tool_names == expected

            list_frameworks_result: CallToolResult = await live_session.call_tool(
                "list_frameworks", {}
            )
            frameworks = _extract_tool_payload(list_frameworks_result)
            assert frameworks["total_count"] > 0

            catalog_ids = {entry["id"] for entry in frameworks["frameworks"]}
            missing = REQUIRED_FRAMEWORK_IDS - catalog_ids
            assert not missing, (
                f"list_frameworks is missing {sorted(missing)}. Present: "
                f"{sorted(catalog_ids)}. These are the frameworks the tool's own "
                "description promises, so their absence means the catalog is "
                "pointed at something other than the reference directory."
            )
            # Require a source derived from live discovery. "cache" counts:
            # discovery caches its listing for an hour by design, so demanding
            # "github_api" would leave the gate passing only in the first minute
            # of each hour -- an earlier version of this assertion did exactly
            # that and turned every run red on `source='cache'`.
            #
            # "static_fallback" does not count, and that is the point. A negative
            # control showed that with FRAMEWORKS.subdir pointed at `_data` (site
            # taxonomy) instead of `_data/references`, a failed discovery falls
            # back to STATIC_FRAMEWORK_FILES, which ships the 13 correct
            # filenames -- so the frozen-id assertion above passed while the
            # catalog was misconfigured. Good resilience, useless as evidence.
            assert frameworks["source"] in LIVE_SOURCES, (
                f"list_frameworks served source={frameworks['source']!r}, so the "
                "catalog did not come from live discovery and this run has "
                "verified nothing about it. 'static_fallback' or 'expired_cache' "
                "usually means the unauthenticated GitHub rate limit (60 "
                "requests/hour per IP) is spent rather than a code defect: "
                "retry, or set FINOS_MCP_GITHUB_TOKEN. The gate fails rather "
                "than passing on fallback data, because the fallback ships the "
                "correct filenames even when discovery is pointed at the wrong "
                "directory, and an expired list file can be of any age."
            )

            framework_id = "eu-ai-act"
            get_framework_result: CallToolResult = await live_session.call_tool(
                "get_framework", {"framework_id": framework_id}
            )
            framework = _extract_tool_payload(get_framework_result)
            assert framework["framework_id"] == framework_id
            # Structural, not a pinned literal: the name map also says "EU AI
            # Act", so an equality here would couple the gate to upstream free
            # text without discriminating between the document and the fallback.
            # Discrimination lives in the unit tests, not here -- see the
            # block below for why no live comparison can provide it.
            assert framework["title"] and "not found" not in framework["title"].lower()
            assert framework_id not in framework["title"], (
                f"get_framework published its own id as the title: "
                f"{framework['title']!r}"
            )

            # Every framework: the catalog, the fetched title, and the
            # document's own YAML must all agree.
            #
            # **What this can and cannot catch, stated so it is not mistaken for
            # more.** It cannot detect the YAML-title path regressing to the
            # name map, because this PR aligned that map to the corpus -- the
            # two sources now produce identical strings, so no live comparison
            # can tell them apart. An earlier version of this block claimed to
            # be that discriminator and was measured *surviving* a mutation that
            # replaced the whole YAML lookup with None. The discriminator is
            # tests/unit/test_document_titles.py, which stubs a sentinel title
            # only a document could supply.
            #
            # What this does catch, and what nothing offline can: the map
            # drifting from what FINOS publishes. list_frameworks answers from
            # the map while get_framework answers from the document, so the
            # moment upstream retitles anything, these disagree.
            checked = 0
            for entry in frameworks["frameworks"]:
                fid = entry["id"]
                payload = _extract_tool_payload(
                    await live_session.call_tool("get_framework", {"framework_id": fid})
                )
                assert entry["name"] == payload["title"], (
                    f"list_frameworks calls {fid!r} {entry['name']!r} while "
                    f"get_framework calls it {payload['title']!r}. The "
                    "hardcoded name map has drifted from what FINOS publishes, "
                    "so a client that lists then fetches sees two names for one "
                    "document (see #121)"
                )
                # The catalog is what a model chooses from, so an entry must
                # say what the file says about itself (#191). Null is allowed
                # per entry -- the name above matches the map even when the
                # listing could not read the document -- and bounded below.
                assert entry["description"] is None or _quoted_from(
                    entry["description"], payload["content"]
                ), (
                    f"list_frameworks describes {fid!r} as "
                    f"{entry['description']!r}, which the framework file does "
                    "not say"
                )
                assert "last_updated" not in payload, (
                    f"get_framework({fid!r}) publishes last_updated, which "
                    "nothing populates"
                )
                leaked = [m for m in REPR_MARKERS if m in payload["content"]]
                assert not leaked, (
                    f"{fid} rendered Python repr fragments {leaked}, so a "
                    "structure is being str()'d rather than formatted"
                )
                # The body is the framework written out as a document (#192):
                # headed by its title, each entry a list item under its id,
                # and `entry_count` the number of them. It used to be a list of
                # the file's top-level keys, a heading made from the key
                # `entries`, and the raw YAML in a fence, with the count (then `sections`) at 3
                # or 4 for every framework.
                body = payload["content"].split("\n")
                assert body[0] == f"# {payload['title']}", (
                    f"get_framework({fid!r}) is titled {payload['title']!r} "
                    f"above a body headed {body[0]!r}"
                )
                listed = [line for line in body if line.startswith("- **")]
                assert payload["entry_count"] == len(listed) >= 10, (
                    f"get_framework({fid!r}) reports {payload['entry_count']} "
                    f"entries and lists {len(listed)} entries; every "
                    "framework in the corpus has at least ten"
                )
                generated = [
                    line
                    for line in body
                    if line.startswith(("```", "### ", "## Framework", "## Raw"))
                    or line.lower().lstrip("# ").startswith("entries")
                ]
                assert not generated, (
                    f"get_framework({fid!r}) wrote lines the framework does "
                    f"not say: {generated[:3]}"
                )
                checked += 1
            assert checked >= 10, (
                f"only {checked} frameworks were listed; the corpus ships 13, "
                "so these checks have gone largely vacuous"
            )

            # A literal find (#208): every framework that says the phrase, in
            # the order list_frameworks gives them, each with a count.
            catalog_order = [entry["id"] for entry in frameworks["frameworks"]]
            search_frameworks_result: CallToolResult = await live_session.call_tool(
                "search_frameworks", {"query": "risk management", "limit": 20}
            )
            search_frameworks_payload = _extract_tool_payload(search_frameworks_result)
            assert search_frameworks_payload["query"] == "risk management"
            framework_hits = search_frameworks_payload["results"]
            found_ids = [hit["document_id"] for hit in framework_hits]
            counts = [hit["occurrences"] for hit in framework_hits]
            assert len(found_ids) >= 3 and counts != sorted(counts, reverse=True), (
                "precondition: 'risk management' no longer tells catalog order "
                f"from an ordering by count ({dict(zip(found_ids, counts, strict=True))}); "
                "pick a phrase several frameworks say an uneven number of times"
            )
            assert found_ids == [fid for fid in catalog_order if fid in found_ids], (
                f"search_frameworks did not answer in catalog order: {found_ids}"
            )
            assert search_frameworks_payload["total_found"] == len(found_ids)
            for hit in framework_hits:
                quoted = " ".join(hit["content"].lower().replace("-", " ").split())
                assert "risk management" in quoted, (
                    f"{hit['document_id']}: the passage does not say the phrase: "
                    f"{hit['content']!r}"
                )

            # The words apart are not the phrase. Each is in the corpus; in
            # this order they are not, and the old matcher answered with every
            # framework holding either one.
            for word in ("obligations", "high-risk"):
                word_result: CallToolResult = await live_session.call_tool(
                    "search_frameworks", {"query": word, "limit": 1}
                )
                assert _extract_tool_payload(word_result)["total_found"] > 0, (
                    f"precondition: no framework says {word!r} any more"
                )
            apart_result: CallToolResult = await live_session.call_tool(
                "search_frameworks", {"query": "obligations high-risk", "limit": 3}
            )
            apart = _extract_tool_payload(apart_result)
            assert (apart["results"], apart["total_found"]) == ([], 0), (
                "search_frameworks matched 'obligations high-risk' on its words "
                f"apart: {[hit['document_id'] for hit in apart['results']]}"
            )

            # `limit` must mean distinct frameworks: a per-framework cap of three
            # used to let one document fill the caller's whole budget.
            spread_result: CallToolResult = await live_session.call_tool(
                "search_frameworks", {"query": "risk", "limit": 5}
            )
            spread_hits = _extract_tool_payload(spread_result)["results"]
            hit_ids = [hit["document_id"] for hit in spread_hits]
            assert len(set(hit_ids)) == len(hit_ids), (
                f"search_frameworks returned the same framework more than once: "
                f"{hit_ids}. limit counts frameworks, not matches within one."
            )
            assert set(hit_ids) <= catalog_ids, (
                "search_frameworks reported ids absent from list_frameworks: "
                f"{sorted(set(hit_ids) - catalog_ids)}"
            )

            list_risks_result: CallToolResult = await live_session.call_tool(
                "list_risks", {}
            )
            risks = _extract_tool_payload(list_risks_result)
            assert risks["document_type"] == "risk"
            assert risks["total_count"] > 0
            first_risk_id = risks["documents"][0]["id"]
            first_risk_filename = risks["documents"][0]["filename"]
            assert not first_risk_id.startswith(("ri-", "mi-")), (
                f"list_risks published {first_risk_id!r}, which keeps the "
                "filename prefix the get_* tools omit"
            )

            get_risk_result: CallToolResult = await live_session.call_tool(
                "get_risk", {"risk_id": first_risk_id}
            )
            risk = _extract_tool_payload(get_risk_result)
            assert risk["document_id"] == first_risk_id
            assert risks["source"] in LIVE_SOURCES, (
                f"list_risks served source={risks['source']!r}, so the listing "
                "did not come from live discovery (#280). See the frameworks "
                "assertion above for the usual cause."
            )
            # A real document, not merely a string. "Error loading ..." and
            # "... not found" are both strings of non-zero length, which is all
            # the previous two assertions required.
            assert len(risk["content"]) > 500, (
                f"{first_risk_id} returned {len(risk['content'])} characters; "
                f"title={risk['title']!r}"
            )
            assert "not found" not in risk["title"].lower(), (
                f"the id {first_risk_id!r} came from list_risks but get_risk "
                f"reports it does not exist: {risk['title']!r}"
            )
            # The assertion above is what let #118 ship: a filename passes it.
            # Every risk is presented to the caller under this title, so assert
            # what it *is*, not merely what it is not.
            assert not risk["title"].startswith(("ri-", "mi-")), (
                f"get_risk published the filename as the title: "
                f"{risk['title']!r}. The document declares a real title in its "
                "frontmatter and it is being discarded"
            )
            # A listing and a fetch must agree on what a document is called.
            #
            # Tolerant of exactly one documented outcome: the listing's name is
            # best-effort, so a transient fetch failure during title resolution
            # legitimately yields the derived name. A strict equality here would
            # turn an upstream blip into a blocked push, since the pre-push hook
            # runs this suite. It still catches the real defect -- the framework
            # bug published the name map's value, which is neither the title nor
            # the derived name.
            listed_name = risks["documents"][0]["name"]
            derived = first_risk_filename.replace(".md", "").replace("-", " ").title()
            assert listed_name in (risk["title"], derived), (
                f"list_risks calls it {listed_name!r} while get_risk calls it "
                f"{risk['title']!r}, and it is not the documented fallback "
                f"{derived!r} either; a client sees one name browsing and "
                "another opening"
            )
            # Same tolerance: a listing that read the document describes it in
            # the document's words (#191); one that fell back describes nothing.
            if listed_name == risk["title"]:
                assert _quoted_from(
                    risks["documents"][0]["description"], risk["content"]
                ), (
                    f"list_risks describes {first_risk_id!r} as "
                    f"{risks['documents'][0]['description']!r}, which is not "
                    "the opening of the document get_risk returns"
                )
            for listing in (frameworks["frameworks"], risks["documents"]):
                _assert_nothing_generated(listing)
            assert any(f["description"] for f in frameworks["frameworks"]), (
                "list_frameworks described none of its entries; every framework "
                "file declares a description, so none was read"
            )

            # Deliberately *not* pinning "Prompt Injection" here.
            #
            # This suite is the pre-push functional-gate, and branch protection
            # is unavailable, so it is the real enforcement point -- a pinned
            # piece of upstream free text means a FINOS retitle turns every
            # developer's push red against correct server code, with no code
            # change able to make it green. The block 150 lines above declines
            # to pin "EU AI Act" for exactly that reason; pinning a risk title
            # here contradicted it.
            #
            # Nothing is lost: the discrimination lives in
            # tests/unit/test_document_titles.py, which stubs a title only a
            # document could supply and is mutation-verified. What remains here
            # is the structural property, which is what a live run can add.
            pinned: CallToolResult = await live_session.call_tool(
                "get_risk", {"risk_id": "10_prompt-injection"}
            )
            pinned_risk = _extract_tool_payload(pinned)
            assert not pinned_risk["title"].startswith(("ri-", "mi-")), (
                f"get_risk published the filename as the title: "
                f"{pinned_risk['title']!r}"
            )
            assert pinned_risk["title"] != "10_prompt-injection", (
                "get_risk published its own id as the title"
            )
            assert " " in pinned_risk["title"] and pinned_risk["title"][:1].isupper(), (
                f"the title does not read like a declared name: "
                f"{pinned_risk['title']!r}"
            )

            list_mitigations_result: CallToolResult = await live_session.call_tool(
                "list_mitigations", {}
            )
            mitigations = _extract_tool_payload(list_mitigations_result)
            assert mitigations["document_type"] == "mitigation"
            assert mitigations["total_count"] > 0
            _assert_nothing_generated(mitigations["documents"])
            first_mitigation_id = mitigations["documents"][0]["id"]
            # Asserted *before* the id is spent on a get_mitigation call, to
            # match the risk branch above. Under a non-uniform fault -- where
            # list_mitigations keeps the prefix but get_mitigation does not --
            # calling first would return the "not found" document, and the
            # failure would surface as a document_id mismatch further down
            # rather than as the message below explaining the actual cause.
            #
            # The round trip is no substitute, because it is self-consistent
            # under a *uniform* fault: both sites derive ids the same way, so a
            # wrong prefix at both still round-trips. Measured -- mutating every
            # "mi-" derivation to "ri-" left this whole suite and all 452 unit
            # tests green. The published form is what breaks, so the published
            # form is what must be asserted.
            assert not first_mitigation_id.startswith(("mi-", "ri-")), (
                f"list_mitigations published {first_mitigation_id!r}, which "
                "keeps the filename prefix the get_* tools and every documented "
                "example omit"
            )

            get_mitigation_result: CallToolResult = await live_session.call_tool(
                "get_mitigation", {"mitigation_id": first_mitigation_id}
            )
            mitigation = _extract_tool_payload(get_mitigation_result)
            assert mitigation["document_id"] == first_mitigation_id
            # As for the first risk: described in its own words when the
            # listing read it, by nothing when it fell back.
            first_mitigation = mitigations["documents"][0]
            if first_mitigation["name"] == mitigation["title"]:
                assert _quoted_from(
                    first_mitigation["description"], mitigation["content"]
                ), (
                    f"list_mitigations describes {first_mitigation_id!r} as "
                    f"{first_mitigation['description']!r}, which is not the "
                    "opening of the document get_mitigation returns"
                )
            assert isinstance(mitigation["content"], str)
            assert len(mitigation["content"]) > 0

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
            # The whole catalog, for the model to choose from (#208): every id
            # list_risks reported, so each can be handed to get_risk.
            assert _catalog_ids_in(risk_prompt) == [
                document["id"] for document in risks["documents"]
            ], "risk_assessment_analysis does not embed the catalog list_risks reports"

            mitigation_prompt: GetPromptResult = await live_session.get_prompt(
                "mitigation_strategy_prompt",
                {
                    "risk_type": "prompt injection",
                    "system_description": "Financial assistant with transaction advisory capabilities",
                },
            )
            assert mitigation_prompt.messages
            assert _catalog_ids_in(mitigation_prompt) == [
                document["id"] for document in mitigations["documents"]
            ], (
                "mitigation_strategy_prompt does not embed the catalog "
                "list_mitigations reports"
            )
