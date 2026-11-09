"""Invariants over the tool metadata an MCP client actually receives.

A tool's published metadata is not documentation. FastMCP sends the ``description``
and the parameter JSON Schema in ``tools/list``, so this is the text an LLM reads when
deciding what to call and what to pass. A framework advertised there but absent from the
catalog produces real failed calls, not merely a confusing read.

Scope note, established by measurement rather than assumption: FastMCP publishes the
docstring summary and body but **strips the ``Args:`` section**, and takes parameter text
from the Pydantic ``Field(description=...)`` instead. Prose inside ``Args:`` therefore
never reaches a client, and asserting on it here would test something no caller can see.
These tests read only what ``mcp.list_tools()`` actually exposes.

No network call is made; claims are checked against the static catalogs shipped in the
package.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from typing import Any

import pytest

from finos_mcp.content.static_catalog import (
    STATIC_FRAMEWORK_FILES,
    STATIC_MITIGATION_FILES,
    STATIC_RISK_FILES,
)

_EXTENSIONS = (".yml", ".yaml", ".md")

# Identifier examples embedded in published parameter descriptions, e.g.
# "Framework identifier from list_frameworks() (e.g. nist-ai-600-1)."
_PARAM_EXAMPLE = re.compile(r"e\.g\.\s*([A-Za-z0-9][A-Za-z0-9._-]*)")

# A bullet in a "Available frameworks include:" list, up to the parenthetical gloss.
_BULLET = re.compile(r"^\s*[-*]\s*(?P<label>[^(\n]+)", re.MULTILINE)


def _catalog_ids(filenames: tuple[str, ...], prefixes: tuple[str, ...]) -> set[str]:
    """Identifiers a caller may legitimately pass, derived from the catalog."""
    ids: set[str] = set()
    for filename in filenames:
        stem = filename
        for extension in _EXTENSIONS:
            if stem.endswith(extension):
                stem = stem[: -len(extension)]
                break
        for prefix in prefixes:
            if stem.startswith(prefix):
                stem = stem[len(prefix) :]
        ids.add(stem)
    return ids


FRAMEWORK_IDS = _catalog_ids(tuple(STATIC_FRAMEWORK_FILES), ())
RISK_IDS = _catalog_ids(tuple(STATIC_RISK_FILES), ("ri-",))
MITIGATION_IDS = _catalog_ids(tuple(STATIC_MITIGATION_FILES), ("mi-",))
ALL_IDS = FRAMEWORK_IDS | RISK_IDS | MITIGATION_IDS


def _normalise(text: str) -> str:
    """Reduce a display label or id to comparable letters and digits."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _published_tools() -> list[Any]:
    from finos_mcp.fastmcp_server import mcp

    result = mcp.list_tools()
    if inspect.isawaitable(result):
        return list(asyncio.run(result))
    return list(result)


@pytest.fixture(scope="module")
def published() -> dict[str, object]:
    return {tool.name: tool for tool in _published_tools()}


def test_advertised_frameworks_exist_in_the_catalog(published: dict[str, Any]) -> None:
    """Frameworks named in a published description must be resolvable.

    The violation this was written for: list_frameworks advertised "GDPR (General Data
    Protection Regulation)" and "ISO/IEC 23053 Framework", neither of which is in the
    catalog, so a client asking for either gets nothing back.
    """
    description = getattr(published["list_frameworks"], "description", "") or ""
    labels = [match.group("label").strip() for match in _BULLET.finditer(description)]

    assert labels, (
        "list_frameworks publishes no framework bullets to verify; if the enumeration "
        "was removed, delete this test deliberately rather than letting it pass empty"
    )

    known = {_normalise(framework_id) for framework_id in FRAMEWORK_IDS}
    unresolvable = [
        label
        for label in labels
        if not any(
            _normalise(label) == identifier
            or _normalise(label).startswith(identifier)
            or identifier.startswith(_normalise(label))
            for identifier in known
        )
    ]

    assert not unresolvable, (
        f"list_frameworks advertises frameworks absent from the catalog: "
        f"{unresolvable}. Real framework ids: {sorted(FRAMEWORK_IDS)}"
    )


def test_parameter_examples_resolve(published: dict[str, Any]) -> None:
    """Any "e.g. <id>" in a published parameter description must be a real id."""
    offenders: list[str] = []
    checked = 0

    for name, tool in published.items():
        properties = (getattr(tool, "parameters", {}) or {}).get("properties") or {}
        for parameter, schema in properties.items():
            for example in _PARAM_EXAMPLE.findall(schema.get("description") or ""):
                checked += 1
                if example not in ALL_IDS:
                    offenders.append(f"{name}.{parameter} -> {example!r}")

    assert checked, "no parameter examples were found to check"
    assert not offenders, f"published parameter examples do not resolve: {offenders}"


def test_catalogs_are_populated() -> None:
    """Guard the guard.

    An empty catalog would make the checks above fail for the wrong reason, or pass
    vacuously if the claims were deleted too. Assert the fixtures carry real content.
    """
    assert len(FRAMEWORK_IDS) >= 10, f"framework catalog looks empty: {FRAMEWORK_IDS}"
    assert len(RISK_IDS) >= 10, f"risk catalog looks empty: {RISK_IDS}"
    assert len(MITIGATION_IDS) >= 10, (
        f"mitigation catalog looks empty: {MITIGATION_IDS}"
    )


def test_the_description_checks_inspected_something(published: dict[str, Any]) -> None:
    """A floor on what was inspected.

    Without this, a change that published zero tools would make every test above
    pass by inspecting nothing.

    Deliberately *not* a second copy of the tool count. This used to assert
    ``len(published) == 11``, which made it a rival source of truth to
    ``PUBLISHED_TOOLS`` in tests/unit/test_published_surface.py -- and that one
    pins the exact tool *set*, which subsumes any count. The duplication meant
    publishing a twelfth tool required editing two files, and whoever updated
    only the surface contract got a green new test plus a red assertion over
    here, in a file whose subject is description accuracy and not the tool
    inventory. This stays an anti-vacuity floor and nothing more.
    """
    assert published, (
        "no tools were published, so every description assertion above "
        "inspected nothing"
    )
