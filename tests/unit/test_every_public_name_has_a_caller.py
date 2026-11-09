# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Every public name in the security and error modules is reached by
production code (#325).

About 250 lines under ``security/``, ``error_boundary.py`` and
``exceptions.py`` were reached only by their tests: a header builder with a
Content Security Policy for a server that serves no page, a content-type
check no fetch consulted, five exception types nothing raised. A name with
tests and no caller reads as a control that exists, so the review counted it
as one, and it was not.

A public top-level function or class in those modules, and a public method
of a class defined there, must be named by another module under ``src``.
Three shapes count as a caller without a name in another module, each
stated here so the rule cannot be widened quietly:

- a class another class in the same module subclasses (a base);
- a class a module-level assignment instantiates, when that instance is
  named by another module (``content_security_validator``);
- a method of a class whose base comes from another package (a hook the
  base's owner calls, such as ``on_call_tool``), or a method the same class
  calls on ``self``.

A package ``__init__`` is not a caller: a re-export reaches nothing.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "src" / "finos_mcp"
CHECKED = sorted(
    [p for p in (ROOT / "security").glob("*.py") if p.name != "__init__.py"]
    + [ROOT / "error_boundary.py", ROOT / "exceptions.py"]
)


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _names_used(tree: ast.AST) -> set[str]:
    """Every identifier a module reads: a plain name or an attribute."""
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
    return used


def _self_calls(cls: ast.ClassDef) -> set[str]:
    return {
        node.attr
        for node in ast.walk(cls)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }


def _module_instances(tree: ast.Module) -> dict[str, str]:
    """``instance_name -> ClassName`` for each ``x = ClassName(...)`` at top level."""
    found: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
        ):
            found[node.targets[0].id] = node.value.func.id
    return found


def _base_names(cls: ast.ClassDef) -> set[str]:
    return {
        base.id if isinstance(base, ast.Name) else base.attr
        for base in cls.bases
        if isinstance(base, ast.Name | ast.Attribute)
    }


def _unreached(path: Path, used_elsewhere: set[str]) -> list[str]:
    tree = _parsed(path)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    defined_here = {n.name for n in classes}
    subclassed = {b for c in classes for b in _base_names(c)}
    instances = _module_instances(tree)
    instance_used = {cls for name, cls in instances.items() if name in used_elsewhere}

    missing: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if node.name.startswith("_"):
            continue
        if node.name in used_elsewhere:
            pass
        elif isinstance(node, ast.ClassDef) and (
            node.name in subclassed or node.name in instance_used
        ):
            pass
        else:
            missing.append(f"{path.name}: {node.name}")
        if not isinstance(node, ast.ClassDef):
            continue
        if _base_names(node) - defined_here:
            continue  # a hook class: the base's owner calls its methods
        self_calls = _self_calls(node)
        for method in node.body:
            if not isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if method.name.startswith("_"):
                continue
            if method.name in used_elsewhere or method.name in self_calls:
                continue
            missing.append(f"{path.name}: {node.name}.{method.name}")
    return missing


@pytest.mark.unit
def test_every_public_name_in_the_security_and_error_modules_has_a_caller() -> None:
    modules = {p: _parsed(p) for p in ROOT.rglob("*.py") if p.name != "__init__.py"}
    unreached: list[str] = []
    for path in CHECKED:
        used_elsewhere: set[str] = set()
        for other, tree in modules.items():
            if other != path:
                used_elsewhere |= _names_used(tree)
        unreached.extend(_unreached(path, used_elsewhere))
    assert not unreached, (
        "public names no production module reaches (delete them with their "
        "tests, or give them the caller their docstring claims):\n  "
        + "\n  ".join(unreached)
    )
