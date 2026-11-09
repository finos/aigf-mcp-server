# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""What ``src`` imports is what ``[project.dependencies]`` declares (#321).

``config.py`` imported ``pydantic_settings`` and ``http_health.py`` imported
``starlette``, and neither distribution was declared: both arrived through
``fastmcp`` and ``mcp``, which may drop them in any release. ``pathvalidate``,
``bleach`` and ``python-slugify`` were declared under "security-focused
validation libraries" and imported nowhere, each a dependency tree of
advisories for nothing.

Import names are mapped to distributions by the installed metadata, not by a
hand-written table, so ``yaml`` is ``PyYAML`` because the environment says
so. One shape needs a rule: ``fastmcp`` is a distribution with no modules
whose one unconditional requirement, ``fastmcp-slim``, provides the
``fastmcp`` package. A declared distribution that provides no module counts
as providing what its unconditional requirements provide. A distribution
that does provide modules does not: ``mcp`` requiring ``starlette`` is not a
declaration of ``starlette``.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from importlib.metadata import (
    PackageNotFoundError,
    distribution,
    packages_distributions,
)
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "finos_mcp"

_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _normalised(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_name(requirement: str) -> str:
    match = _REQUIREMENT_NAME.match(requirement)
    assert match, requirement
    return _normalised(match.group(1))


def _imported_top_level_names() -> set[str]:
    """Every absolute import's first segment under ``src``, stdlib excluded."""
    names: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names - set(sys.stdlib_module_names) - {"finos_mcp"}


def _declared() -> set[str]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return {_requirement_name(r) for r in pyproject["project"]["dependencies"]}


def _providers() -> dict[str, set[str]]:
    """``{import name: distributions that install it}``, normalised."""
    return {
        name: {_normalised(d) for d in dists}
        for name, dists in packages_distributions().items()
    }


def _unconditional_requirements(dist: str) -> set[str]:
    try:
        requirements = distribution(dist).metadata.get_all("Requires-Dist") or []
    except PackageNotFoundError:
        return set()
    return {
        _requirement_name(r)
        for r in requirements
        if "extra ==" not in r.split(";", 1)[-1]
    }


def _provided_by(declared: str, providers: dict[str, set[str]]) -> set[str]:
    """The distributions a declared name stands for: itself, or what it wraps."""
    provides_a_module = any(declared in dists for dists in providers.values())
    if provides_a_module:
        return {declared}
    return {declared} | _unconditional_requirements(declared)


def test_every_third_party_import_is_a_declared_dependency() -> None:
    providers = _providers()
    declared = set().union(*(_provided_by(d, providers) for d in _declared()))
    not_installed = sorted(n for n in _imported_top_level_names() if n not in providers)
    assert not not_installed, (
        f"imported but not installed, so not mappable to a distribution: {not_installed}"
    )
    undeclared = sorted(
        f"{name} ({', '.join(sorted(providers[name]))})"
        for name in _imported_top_level_names()
        if not providers[name] & declared
    )
    assert not undeclared, (
        f"imported under src but not in [project.dependencies]: {undeclared}"
    )


def test_every_declared_dependency_is_imported() -> None:
    providers = _providers()
    used = set().union(
        *(providers.get(name, set()) for name in _imported_top_level_names())
    )
    unused = sorted(d for d in _declared() if not _provided_by(d, providers) & used)
    assert not unused, (
        f"in [project.dependencies] but imported nowhere under src: {unused}"
    )


def test_the_scanner_reads_a_function_local_import() -> None:
    """The deferred import config.py keeps (#300) is relative; an absolute one would count."""
    tree = ast.parse("def f():\n    import bleach\n    from .x import y\n")
    found = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert found == {"bleach"}
