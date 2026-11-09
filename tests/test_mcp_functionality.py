"""Contract tests for every MCP tool, called in process.

This file used to be 535 lines that could not fail: 32 ``return True``/
``return False`` statements, 11 bare ``except Exception`` handlers, and **zero**
assertions. A pytest function that returns a value instead of asserting passes,
so "comprehensive MCP functionality" reported success no matter what the server
did -- which is how a framework search that answered nothing, and a catalog that
could not report its own provenance, both reached main.

Scope is deliberately the *contract* each tool must satisfy whether discovery
reached GitHub or fell back to the static catalog: identifiers are usable, counts
agree with payloads, provenance is declared. End-to-end behaviour over a real
stdio session belongs to tests/integration/test_live_mcp_server.py, which is the
functional gate.

Nothing here swallows exceptions. A tool that raises must fail the test rather
than be reported as a handled condition.
"""

from __future__ import annotations

from typing import Any

import pytest

from finos_mcp.exceptions import UnknownDocumentError
from finos_mcp.fastmcp_server import mcp

pytestmark = pytest.mark.integration

# Every value a catalog may legitimately report. "unavailable" is absent on
# purpose: it means discovery failed *and* nothing served the request, which is a
# defect rather than a degraded mode.
VALID_SOURCES = {"github_api", "cache", "expired_cache", "static_fallback"}

CATALOG_TOOLS = (
    ("list_risks", "documents"),
    ("list_mitigations", "documents"),
    ("list_frameworks", "frameworks"),
)

SEARCH_TOOLS = ("search_frameworks",)


async def call(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a registered tool and return its structured payload."""
    tool = await mcp.get_tool(name)
    assert tool is not None, f"tool {name!r} is not registered"
    result = await tool.run(arguments or {})
    payload = result.structured_content
    assert isinstance(payload, dict), (
        f"{name} returned {type(payload).__name__}, not a structured payload"
    )
    return payload


@pytest.mark.parametrize(("tool_name", "collection_key"), CATALOG_TOOLS)
async def test_catalog_declares_its_provenance(
    tool_name: str, collection_key: str
) -> None:
    """Every catalog must say where its answer came from.

    FrameworkList carried no `source` field at all, so list_frameworks answered
    None while the risk and mitigation catalogs reported theirs. A caller could
    not tell a live catalog from the shipped static one.
    """
    payload = await call(tool_name)

    assert payload.get("source") in VALID_SOURCES, (
        f"{tool_name} reported source={payload.get('source')!r}; expected one of "
        f"{sorted(VALID_SOURCES)}. None means the field is missing entirely; "
        "'unavailable' means nothing served the request."
    )


@pytest.mark.parametrize(("tool_name", "collection_key"), CATALOG_TOOLS)
async def test_catalog_entries_are_usable_and_counted(
    tool_name: str, collection_key: str
) -> None:
    """Identifiers must be present and unique, and total_count must be honest."""
    payload = await call(tool_name)
    entries = payload[collection_key]

    assert entries, (
        f"{tool_name} returned an empty {collection_key} list; the static "
        "fallback should serve a catalog even with no network"
    )
    assert payload["total_count"] == len(entries), (
        f"{tool_name} claims total_count={payload['total_count']} but returned "
        f"{len(entries)} entries"
    )

    ids = [entry["id"] for entry in entries]
    assert all(ids), f"{tool_name} returned an entry with an empty id: {ids}"
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f"{tool_name} returned duplicate ids: {duplicates}"
    assert all(entry.get("name") for entry in entries), (
        f"{tool_name} returned an entry with no display name"
    )


@pytest.mark.parametrize("tool_name", SEARCH_TOOLS)
async def test_search_echoes_the_query_and_counts_its_results(tool_name: str) -> None:
    """A search must report the query it ran and a count matching its results.

    Asserting the count against the payload rather than `isinstance(results,
    list)` -- an empty list satisfies that, which is the assertion that let
    search_frameworks answer nothing without anyone noticing.
    """
    payload = await call(tool_name, {"query": "risk", "limit": 3})

    assert payload["query"] == "risk"
    results = payload["results"]
    assert len(results) <= 3, f"{tool_name} returned {len(results)} results for limit=3"
    assert payload["total_found"] >= len(results), (
        f"{tool_name} reports total_found={payload['total_found']} but returned "
        f"{len(results)} results"
    )


async def test_framework_search_returns_distinct_frameworks() -> None:
    """`limit` counts frameworks, not matches inside one framework.

    A per-framework cap of three used to let one document fill the answer:
    limit=5 returned five results spanning two frameworks.
    """
    payload = await call("search_frameworks", {"query": "risk", "limit": 5})
    ids = [result["document_id"] for result in payload["results"]]

    assert len(set(ids)) == len(ids), (
        f"search_frameworks returned the same framework more than once: {ids}. "
        "limit must mean distinct frameworks."
    )


async def test_service_health_reports_every_subsystem() -> None:
    payload = await call("get_service_health")

    assert payload["status"] in {"healthy", "degraded", "unhealthy"}
    assert payload["total_services"] > 0, "the health check counted no subsystems"
    assert payload["healthy_services"] <= payload["total_services"]


async def test_cache_stats_are_internally_consistent() -> None:
    """The four counters CacheStats declares must agree with each other.

    Only those four: main's model is total_requests / cache_hits / cache_misses /
    hit_rate. An earlier draft of this test asserted `current_size <= max_size`,
    fields that exist on another branch's richer model, and failed with KeyError.
    """
    payload = await call("get_cache_stats")

    assert (
        payload["total_requests"] == payload["cache_hits"] + payload["cache_misses"]
    ), (
        f"cache stats do not add up: {payload['cache_hits']} hits + "
        f"{payload['cache_misses']} misses != {payload['total_requests']} requests"
    )
    assert 0.0 <= payload["hit_rate"] <= 1.0, (
        f"hit_rate={payload['hit_rate']} is outside 0..1"
    )
    if payload["total_requests"]:
        expected = payload["cache_hits"] / payload["total_requests"]
        assert abs(payload["hit_rate"] - expected) < 1e-9, (
            f"hit_rate={payload['hit_rate']} does not match "
            f"{payload['cache_hits']}/{payload['total_requests']}"
        )


async def test_unknown_identifier_is_an_error_that_names_the_id() -> None:
    """A bad id is an error of its own kind, not a crash and not a document.

    The old file wrapped this in `except Exception: return False`, so a crash and
    a clean "not found" were indistinguishable. Then it came back as a record
    saying "not found", which a caller reads as the document (#193).
    """
    with pytest.raises(UnknownDocumentError) as refusal:
        await call("get_risk", {"risk_id": "definitely-not-a-real-risk"})

    assert "'definitely-not-a-real-risk'" in str(refusal.value)
    assert "list_risks" in str(refusal.value)
