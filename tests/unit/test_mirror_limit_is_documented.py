# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The documents state that a mirror is always listed from the built-in catalog (#316).

For a base_url on a host the GitHub API cannot address, ``discover_content``
goes straight to the static catalog, a listing of upstream ``main`` on the date
``static_catalog.LISTED_ON`` records, and never reads an expired list file. A
mirror whose corpus differs lists documents that fail on get and refuses ones
it holds, and the client sees ``static_fallback``, which the tools document
defined as "GitHub could not be reached". The deployment guide did not mention
mirrors at all.

The guard reads the three places a deployer or a client learns about sources:
the deployment guide, every ``source`` field description in the tools
reference, and the CALM flow for a listing GitHub cannot answer. Each must
name the condition and the consequence in one paragraph. What it does not
catch: a paragraph that names both and says something else about them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_DEPLOYMENT = _ROOT / "docs" / "deployment.md"
_TOOLS = _ROOT / "docs" / "api" / "mcp-tools.md"
_ARCHITECTURE = _ROOT / "calm" / "architecture.json"

_CONDITION = "GitHub API cannot address"
_CONSEQUENCE = "built-in catalog"
_SOURCE_FIELD = "`source` (string): Where the listing came from:"

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def _paragraphs(text: str) -> list[str]:
    return [p for p in _PARAGRAPH_BREAK.split(text) if p.strip()]


def _states_the_limit(paragraph: str) -> bool:
    return _CONDITION in paragraph and _CONSEQUENCE in paragraph


def test_the_deployment_guide_states_the_mirror_limit() -> None:
    stating = [
        p for p in _paragraphs(_DEPLOYMENT.read_text("utf-8")) if _states_the_limit(p)
    ]

    assert stating, (
        f"{_DEPLOYMENT.name} has no paragraph saying that a host the "
        f"{_CONDITION} is listed from the {_CONSEQUENCE}"
    )


def test_every_source_field_in_the_tools_reference_states_the_mirror_limit() -> None:
    fields = [p for p in _paragraphs(_TOOLS.read_text("utf-8")) if _SOURCE_FIELD in p]
    assert len(fields) >= 2, f"{_TOOLS.name} describes `source` {len(fields)} times"

    silent = [p for p in fields if not _states_the_limit(p)]
    assert not silent, (
        f"{len(silent)} `source` description(s) in {_TOOLS.name} do not say that a "
        f"host the {_CONDITION} is listed from the {_CONSEQUENCE}:\n"
        + "\n---\n".join(silent)
    )


def test_the_calm_flow_names_the_mirror_case() -> None:
    architecture = json.loads(_ARCHITECTURE.read_text("utf-8"))
    flows = {f["unique-id"]: f for f in architecture["flows"]}
    steps = flows["list-when-github-cannot-be-asked"]["transitions"]
    fallback = [
        s
        for s in steps
        if s["relationship-unique-id"] == "server-falls-back-to-static-catalog"
    ]
    assert len(fallback) == 1, [s["relationship-unique-id"] for s in steps]

    description = fallback[0]["description"]
    assert _CONDITION in description and "static catalog" in description, description


def test_the_scanner_needs_both_halves_in_one_paragraph() -> None:
    """The guards above pass over an empty selection only if this can fail."""
    assert not _states_the_limit(f"A host the {_CONDITION} is refused.")
    assert not _states_the_limit(f"The {_CONSEQUENCE} is served when GitHub is down.")
    assert not any(
        _states_the_limit(p)
        for p in _paragraphs(f"A host the {_CONDITION}.\n\nThe {_CONSEQUENCE}.")
    )
    assert _states_the_limit(
        f"A host the {_CONDITION} is listed from the {_CONSEQUENCE}."
    )
