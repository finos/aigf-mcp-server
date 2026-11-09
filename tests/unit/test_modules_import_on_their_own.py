# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""A module imports what it uses, and no package ``__init__`` imports for it
(#329).

``config.py`` carried the package's only function-local import of a pure
module, to dodge a cycle that existed because ``security/__init__.py``
re-exported fifteen names nothing imported: importing ``repo_target``
pulled in the DoS middleware and, through it, ``logging``, which imports
``config``. ``safety.py`` and ``documents/format.py`` took their logger
from ``app``, so importing 840 lines of formatting validated the
environment and built the server, and six modules logged under the name
``fastmcp_server``.

Three invariants, each the shape that was broken:

- the package ``__init__`` files import nothing (a re-export is an import
  edge every submodule pays for);
- ``config.py`` has one function-local import, ``setup_structured_logging``
  (#300, because ``logging`` imports ``config``); every other import is at
  module scope;
- no module imports a name called ``logger`` from another module, and
  importing the formatting module in a fresh interpreter does not build
  the server.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "src" / "finos_mcp"


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@pytest.mark.unit
def test_package_inits_import_nothing() -> None:
    offenders = []
    for init in sorted(ROOT.rglob("__init__.py")):
        if init.parent == ROOT:
            continue  # the top-level package reads its version, nothing else
        for node in ast.walk(_parsed(init)):
            if isinstance(node, ast.Import | ast.ImportFrom):
                offenders.append(f"{init.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, f"package __init__ files that import: {offenders}"


@pytest.mark.unit
def test_config_defers_only_the_logging_import() -> None:
    tree = _parsed(ROOT / "config.py")
    deferred: list[str] = []
    for scope in ast.walk(tree):
        if not isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for node in ast.walk(scope):
            if isinstance(node, ast.ImportFrom):
                deferred.extend(f"{node.module}.{a.name}" for a in node.names)
            elif isinstance(node, ast.Import):
                deferred.extend(a.name for a in node.names)
    assert deferred == ["logging.setup_structured_logging"], deferred


@pytest.mark.unit
def test_no_module_borrows_another_modules_logger() -> None:
    offenders = []
    for path in sorted(ROOT.rglob("*.py")):
        for node in ast.walk(_parsed(path)):
            if isinstance(node, ast.ImportFrom) and any(
                alias.name == "logger" for alias in node.names
            ):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, f"modules that import a logger: {offenders}"


@pytest.mark.unit
def test_importing_the_formatter_does_not_build_the_server() -> None:
    probe = (
        "import sys, finos_mcp.documents.format, finos_mcp.config;"
        "print(sorted(m for m in sys.modules if m.startswith('finos_mcp.')))"
    )
    run = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    loaded = run.stdout
    assert "'finos_mcp.app'" not in loaded, loaded
    assert "'finos_mcp.security.dos_middleware'" not in loaded, loaded
