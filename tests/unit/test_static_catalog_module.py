# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The static catalog is a module the update script writes and the server imports (#330).

``scripts/update-static-fallback.py`` wrote a git-ignored side file nobody
imported, and the guide said to copy its three lists into ``discovery.py`` by
hand, under a comment that called them auto-generated. Names went into Python
source unescaped, so one holding a quote would have broken the module.

The script now renders ``src/finos_mcp/content/static_catalog.py`` whole, and
``discovery`` imports the lists from there. These tests hold the generator to
three properties: the module it renders imports and holds the listing it was
given; a name outside the shape the corpus has is refused before it reaches
the source; and the shipped module is exactly what the generator renders from
its own lists, so a hand edit, or a generator whose output ruff would reformat,
fails here.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import ModuleType

import pytest

from finos_mcp.content import static_catalog
from finos_mcp.content.discovery import GitHubDiscoveryService
from tests.helpers import load_module

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "update-static-fallback.py"
_MODULE = _ROOT / "src" / "finos_mcp" / "content" / "static_catalog.py"


def _script() -> ModuleType:
    return load_module(_SCRIPT, "update_static_fallback")


def test_the_module_the_script_renders_imports_and_holds_the_listing(
    tmp_path: Path,
) -> None:
    listing = {
        "mitigations": ["mi-2_second.md", "mi-1_first.md"],
        "risks": ["ri-7_only.md"],
        "frameworks": ["z-last.yml", "a-first.yml"],
    }

    written = tmp_path / "static_catalog.py"
    written.write_text(_script().render_module(listing, "2026-10-13"), encoding="utf-8")
    module = load_module(written, "rendered_static_catalog")

    assert module.STATIC_MITIGATION_FILES == ["mi-1_first.md", "mi-2_second.md"]
    assert module.STATIC_RISK_FILES == ["ri-7_only.md"]
    assert module.STATIC_FRAMEWORK_FILES == ["a-first.yml", "z-last.yml"]
    assert module.LISTED_ON == "2026-10-13"


@pytest.mark.parametrize(
    ("directory", "name"),
    [
        ("mitigations", 'mi-1_a".md'),
        ("risks", "ri-1_a'.md"),
        ("frameworks", 'a".yml'),
        ("mitigations", "ri-1_a-risk-listed-as-a-mitigation.md"),
        ("risks", "ri-1_Capitals.md"),
        ("frameworks", "eu-ai-act.yaml"),
        ("frameworks", "sub/dir.yml"),
        ("risks", "ri-1_a.md\n"),
        ("mitigations", ""),
    ],
)
def test_a_name_outside_the_shape_the_corpus_has_is_refused(
    directory: str, name: str
) -> None:
    listing: dict[str, list[str]] = {"mitigations": [], "risks": [], "frameworks": []}
    listing[directory] = [name]

    with pytest.raises(ValueError, match=re.escape(repr(name))):
        _script().render_module(listing, "2026-10-13")


def test_a_date_that_is_not_a_date_is_refused() -> None:
    listing: dict[str, list[str]] = {"mitigations": [], "risks": [], "frameworks": []}

    with pytest.raises(ValueError, match="2026-10-13"):
        _script().render_module(listing, 'today"; import os')


def test_the_shipped_module_is_what_the_script_renders_from_its_own_lists() -> None:
    """A hand edit, or a generator ruff would reformat, fails here.

    This is also the positive control for the name rule: every name the
    server ships passes it, or the script could never regenerate the module.
    """
    rendered = _script().render_module(
        {
            "mitigations": list(static_catalog.STATIC_MITIGATION_FILES),
            "risks": list(static_catalog.STATIC_RISK_FILES),
            "frameworks": list(static_catalog.STATIC_FRAMEWORK_FILES),
        },
        static_catalog.LISTED_ON,
    )

    assert rendered == _MODULE.read_text(encoding="utf-8")


def test_discovery_serves_the_module_the_script_writes() -> None:
    """``discovery`` holds no lists of its own any more."""
    served = GitHubDiscoveryService()._create_static_fallback()

    assert served.source == "static_fallback"
    assert [f.filename for f in served.mitigation_files] == list(
        static_catalog.STATIC_MITIGATION_FILES
    )
    assert [f.filename for f in served.risk_files] == list(
        static_catalog.STATIC_RISK_FILES
    )
    assert [f.filename for f in served.framework_files] == list(
        static_catalog.STATIC_FRAMEWORK_FILES
    )
