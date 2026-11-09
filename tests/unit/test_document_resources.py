"""``resources/list`` names every document, not only the three templates (#338).

The server published three resource templates and no resource, so a client
that discovers content through ``resources/list`` (Claude Code's resource
lister, the Inspector's Resources tab) saw nothing; only a client that already
knew a document id could build a URI. Each document the list tools name is
now a resource too, named by its filename stem (#384), and reads through the same
handler as the template. The list reads the discovery listing and no document
(#347, #348).
"""

from __future__ import annotations

import importlib
import logging

import pytest
from fastmcp import Client
from test_listing_descriptions import (  # type: ignore[import-not-found]
    _CATALOG,
    _GET_SERVICE_BINDERS,
    _stub_catalog,
)

from finos_mcp.fastmcp_server import mcp

_EXPECTED_URIS = {
    "finos://risks/10_prompt-injection",
    "finos://risks/9_data-poisoning",
    "finos://mitigations/10_ai-model-version-pinning",
    "finos://frameworks/eu-ai-act",
    "finos://frameworks/sr11-7",
}


@pytest.mark.unit
async def test_every_listed_document_is_a_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_catalog(monkeypatch, _CATALOG)

    async with Client(mcp) as client:
        listed = await client.list_resources()

    by_uri = {str(resource.uri): resource for resource in listed}
    assert set(by_uri) == _EXPECTED_URIS
    # Named by the filename stem: the list reads no document (#348), and
    # title-casing the filename gave "Ri 10_Prompt Injection" (#384).
    assert by_uri["finos://risks/10_prompt-injection"].name == (
        "ri-10_prompt-injection"
    )
    assert by_uri["finos://mitigations/10_ai-model-version-pinning"].name == (
        "mi-10_ai-model-version-pinning"
    )
    assert by_uri["finos://frameworks/eu-ai-act"].name == "EU AI Act"
    assert {resource.mime_type for resource in listed} == {"text/markdown"}


@pytest.mark.unit
async def test_a_listed_resource_has_its_templates_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each listed resource was described by ``functools.partial``'s docstring.

    fastmcp takes a missing description from the reader's ``__doc__``, and the
    reader is a ``functools.partial``, so every listed document read
    "partial(func, *args, **keywords) - new function with partial
    application..." (#383).
    """
    _stub_catalog(monkeypatch, _CATALOG)

    async with Client(mcp) as client:
        listed = await client.list_resources()
        templates = await client.list_resource_templates()

    by_kind = {
        template.uri_template.split("/")[2]: template.description
        for template in templates
    }
    assert len(by_kind) == 3
    for resource in listed:
        kind = str(resource.uri).split("/")[2]
        assert resource.description == by_kind[kind], resource.uri


@pytest.mark.unit
async def test_the_list_reads_no_document(monkeypatch: pytest.MonkeyPatch) -> None:
    """A connect costs the discovery listing, not one fetch per document.

    The list tools read every document to name it, about 60 fetches on a cold
    cache, and they ran on every ``resources/list`` (#348). Running three
    listings also lost every kind when one failed (#347).
    """
    _stub_catalog(monkeypatch, _CATALOG)
    # Counted, not refused: the list tools name a document they cannot read
    # from its filename, so a refused read would list every URI either way.
    reads: list[str] = []

    class _CountingService:
        async def get_document(
            self, _doc_type: str, filename: str
        ) -> dict[str, object] | None:
            reads.append(filename)
            document: dict[str, object] | None = _CATALOG[filename]
            return document

    async def _get_service() -> _CountingService:
        return _CountingService()

    for dotted in _GET_SERVICE_BINDERS:
        monkeypatch.setattr(
            importlib.import_module(dotted), "get_service", _get_service
        )

    async with Client(mcp) as client:
        listed = await client.list_resources()

    assert {str(resource.uri) for resource in listed} == _EXPECTED_URIS
    assert reads == []


@pytest.mark.unit
async def test_a_listed_resource_reads_as_the_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_catalog(monkeypatch, _CATALOG)
    document = _CATALOG["ri-10_prompt-injection.md"]
    assert document is not None

    async with Client(mcp) as client:
        read = await client.read_resource("finos://risks/10_prompt-injection")

    assert len(read) == 1
    assert getattr(read[0], "text", None) == document["content"]


@pytest.mark.unit
async def test_a_listing_that_fails_leaves_the_templates_and_says_so(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed listing is not a failed connection: the list is empty, logged."""
    from finos_mcp.content.discovery import DiscoveryServiceManager

    async def _broken(_self: object) -> object:
        raise RuntimeError("listing broke")

    monkeypatch.setattr(
        DiscoveryServiceManager, "get_discovery_service", _broken, raising=True
    )

    with caplog.at_level(logging.WARNING, logger="finos-ai-governance-mcp.resources"):
        async with Client(mcp) as client:
            listed = await client.list_resources()
            templates = await client.list_resource_templates()

    assert listed == []
    assert len(templates) == 3
    assert any("resources/list" in record.getMessage() for record in caplog.records)


@pytest.mark.unit
async def test_connecting_and_reading_cost_no_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The listing runs for ``resources/list`` only.

    Two fastmcp defaults would run it elsewhere: the lookup behind a read
    filters the provider's whole listing for the URI, and the startup check
    for task-enabled components lists everything to find them. A listing
    parses every framework's YAML, and at startup it fetches every document
    before the first request is served.
    """
    from finos_mcp import resources

    _stub_catalog(monkeypatch, _CATALOG)
    listings = 0
    real = resources.DocumentResources._list_resources

    async def _counted(self: resources.DocumentResources) -> object:
        nonlocal listings
        listings += 1
        return await real(self)

    monkeypatch.setattr(resources.DocumentResources, "_list_resources", _counted)

    async with Client(mcp) as client:
        await client.read_resource("finos://risks/10_prompt-injection")

    assert listings == 0


@pytest.mark.unit
async def test_a_listed_resource_names_a_truthful_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reader each listed resource carries is the template's handler.

    fastmcp serves a read through the template, so nothing on the wire runs
    this reader; it is still the resource's own statement of what it holds,
    and a client library may call it. Read directly, it is the document.
    """
    _stub_catalog(monkeypatch, _CATALOG)
    document = _CATALOG["ri-10_prompt-injection.md"]
    assert document is not None
    listed = {str(r.uri): r for r in await mcp.list_resources()}

    read = await listed["finos://risks/10_prompt-injection"].read()

    assert read == document["content"]
