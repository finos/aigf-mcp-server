"""Where an assembled server comes from, asserted so the wrong route stays closed.

``finos_mcp.app`` binds ``mcp``. It does not register anything on it. The
tools, three resources and three prompts arrive only as the *import side effect*
of the domain modules, and the single place that performs those imports is
``finos_mcp.fastmcp_server``. Measured on the commit that introduced this file::

    import finos_mcp.app             -> app.mcp publishes  0 tools
    import finos_mcp.fastmcp_server  ->     mcp publishes 11 tools

They are the same object, mutated in place, which is exactly what makes the
mistake invisible: ``from finos_mcp.app import mcp`` imports cleanly, type-checks,
runs, and serves a client zero tools. There is no exception and no log line. This
is the same failure that #139 shipped once already, when a range-based extraction
dropped every ``@mcp.tool`` decorator and left all 204 definitions importable --
see ``tests/unit/test_published_surface.py``, which caught it by asking the running
server what it publishes.

That test asks *what the assembled server contains*. This file asks the question
one step earlier: *who is allowed to obtain one, and from where*. A new module that
takes the obvious-looking route would not fail ``test_published_surface.py`` at all
-- that test imports the assembler, so the surface it measures is correct no matter
how many other modules hold a half-registered handle.

**The residual, stated rather than implied.** These are static scans of import
syntax, so they close a route, not the policy. ``importlib.import_module("finos_mcp"
+ ".app").mcp`` defeats them, as does any other dynamic construction of the name.
They are aimed at the mistake that actually happens -- someone reads ``app.py``,
sees ``mcp`` defined there, and imports it from its defining module -- not at
someone working around a guard.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

import finos_mcp
from finos_mcp import app as app_module
from finos_mcp import fastmcp_server

#: The module that assembles the server: it performs the registration imports, so
#: it is the one module for which ``from .app import mcp`` denotes the finished
#: object rather than an empty one.
ASSEMBLER = "finos_mcp.fastmcp_server"

#: Modules that register something on ``mcp`` and therefore must reach it before
#: assembly is complete. Each one decorates the object with ``@mcp.tool``,
#: ``@mcp.resource`` or ``@mcp.prompt``, or adds HTTP routes to it with
#: ``custom_route`` (``http_health``). Adding a module here is how a new domain
#: joins the server; doing so without also importing it from the assembler is what
#: ``test_every_registrar_named_here_is_actually_imported`` below catches.
REGISTRARS = frozenset(
    {
        "finos_mcp.documents.tools",
        "finos_mcp.health_tools",
        "finos_mcp.http_health",
        "finos_mcp.prompts",
        "finos_mcp.resources",
        "finos_mcp.search.tools",
    }
)

#: The only name the assembler exists to hand out. Every other name it used to
#: re-export now comes from the module that owns it (#87).
ASSEMBLER_EXPORTS = ["mcp"]

_APP_MODULE = "finos_mcp.app"

#: This file itself, exempted from the ``mcp``-from-``app`` guard. Asserting that
#: the assembler hands out the same object ``app.py`` binds requires naming
#: ``app_module.mcp``, which is the very spelling that guard forbids. The exemption
#: is one file wide and deliberate: reaching an unassembled server is what this
#: file is *about*.
_PREMISE_TEST = "test_server_assembly.py"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_ROOT = _REPO_ROOT / "src" / "finos_mcp"
_TESTS_ROOT = _REPO_ROOT / "tests"


def _module_name(path: Path) -> str:
    """Return the dotted module name a source file is imported as."""
    relative = path.relative_to(_REPO_ROOT / "src").with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _package_of(path: Path) -> str:
    """Return the package a relative import inside this file resolves against."""
    if not path.is_relative_to(_SOURCE_ROOT):
        return ""  # tests are not a package; they cannot use relative imports
    module = _module_name(path)
    return module if path.name == "__init__.py" else module.rpartition(".")[0]


def _resolve(node: ast.ImportFrom, package: str) -> str:
    """Resolve an ``ImportFrom`` to an absolute module name."""
    if not node.level:
        return node.module or ""
    base = package.split(".")
    # level 1 is the containing package itself; each further level strips one more.
    trimmed = base[: len(base) - (node.level - 1)] if node.level > 1 else base
    return ".".join([*trimmed, node.module] if node.module else trimmed)


def _python_files() -> list[Path]:
    """Every source and test file the guards scan, sorted for stable reporting."""
    found = [
        path
        for root in (_SOURCE_ROOT, _TESTS_ROOT)
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    assert found, f"no Python files found under {_SOURCE_ROOT} or {_TESTS_ROOT}"
    return sorted(found)


def _reach_sites(path: Path, target: str, wanted: set[str] | None) -> list[str]:
    """Return every place in one file that reaches a name defined in ``target``.

    ``wanted`` selects which names to report; ``None`` reports every name. Three
    spellings are matched, because a guard that knows only one of them is a guard
    against one spelling:

    * ``from finos_mcp.app import mcp`` -- relative or absolute,
    * ``from finos_mcp import app as x`` then ``x.mcp``,
    * ``import finos_mcp.app as x`` then ``x.mcp``.

    Aliases are collected in a first pass over the whole tree before attributes are
    matched in a second, because ``ast.walk`` is breadth-first: a binding nested
    deeper than its use would not yet be known when that use is visited.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = _package_of(path)
    parent, _, leaf = target.rpartition(".")
    aliases: set[str] = set()
    sites: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            resolved = _resolve(node, package)
            if resolved == target:
                sites.extend(
                    f"{path.name}:{node.lineno}: from {leaf} import {alias.name}"
                    for alias in node.names
                    if wanted is None or alias.name in wanted
                )
            elif resolved == parent:
                aliases.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == leaf
                )
        elif isinstance(node, ast.Import):
            aliases.update(
                alias.asname
                for alias in node.names
                if alias.name == target and alias.asname
            )

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and (wanted is None or node.attr in wanted)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
        ):
            sites.append(f"{path.name}:{node.lineno}: {node.value.id}.{node.attr}")

    return sites


def _report_key(path: Path) -> str:
    """Name a file the way the assertion messages should show it."""
    if path.is_relative_to(_SOURCE_ROOT):
        return _module_name(path)
    return str(path.relative_to(_REPO_ROOT))


def test_app_alone_registers_nothing_on_the_server() -> None:
    """The premise every other guard here rests on, measured rather than assumed.

    If this ever fails because ``app.py`` grew its own registrations, the guards
    below are protecting a hazard that no longer exists and should be deleted
    rather than kept passing.
    """
    assert fastmcp_server.mcp is app_module.mcp, (
        "the assembler must hand out the same object app.py binds; if it builds a "
        "second server the two surfaces can diverge silently"
    )
    source = (_SOURCE_ROOT / "app.py").read_text(encoding="utf-8")
    for decorator in ("@mcp.tool", "@mcp.resource", "@mcp.prompt"):
        assert decorator not in source, (
            f"app.py now registers {decorator} directly, so importing it no longer "
            "yields an empty server -- re-examine whether this file's guards apply"
        )


def test_only_the_registrars_take_mcp_from_its_defining_module() -> None:
    """No module may hold a half-registered server by importing ``mcp`` from ``app``.

    The registrars must, because they run before assembly finishes. Everyone else
    -- production code, entry points and tests alike -- has to go through the
    assembler, which is the only import that guarantees the tools are on it.
    """
    offenders: dict[str, list[str]] = {}
    for path in _python_files():
        if path.name == _PREMISE_TEST:
            continue
        sites = _mcp_from_app_sites(path)
        module = _report_key(path)
        if sites and module not in REGISTRARS and module != ASSEMBLER:
            offenders[module] = sites

    assert not offenders, (
        "these modules take `mcp` from finos_mcp.app, which publishes zero tools "
        f"until the assembler's imports run -- import it from {ASSEMBLER} "
        f"instead: {offenders}"
    )


def _mcp_from_app_sites(path: Path) -> list[str]:
    """Return every place in one file that takes ``mcp`` from ``finos_mcp.app``."""
    return _reach_sites(path, _APP_MODULE, {"mcp"})


def test_every_registrar_named_here_is_actually_imported() -> None:
    """A registrar the assembler does not import contributes nothing to the server.

    Without this, ``REGISTRARS`` is a list that grants permission and asserts
    nothing: a module could be added to it, take ``mcp`` from ``app``, register its
    tools on the shared object, and never be imported -- publishing nothing while
    passing the guard above.
    """
    assembler = _SOURCE_ROOT / "fastmcp_server.py"
    tree = ast.parse(
        assembler.read_text(encoding="utf-8"), filename="fastmcp_server.py"
    )
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            resolved = _resolve(node, "finos_mcp")
            imported.add(resolved)
            imported.update(f"{resolved}.{alias.name}" for alias in node.names)

    missing = sorted(module for module in REGISTRARS if module not in imported)
    assert not missing, (
        f"{missing} register tools on the shared server but {ASSEMBLER} never "
        "imports them, so nothing they define is published"
    )


def test_the_assembler_re_exports_nothing_but_the_assembled_server() -> None:
    """#87's shim is gone: the assembler hands out one name, not forty-three.

    It re-exported 43 names so that a decomposition of that size did not also have
    to rewrite every importer. That was scaffolding for the move, and it survived
    the move: keeping it would leave every helper reachable from two places, which
    is the coupling the decomposition was meant to remove.
    """
    assert fastmcp_server.__all__ == ASSEMBLER_EXPORTS, (
        "the assembler's job is to hand out the assembled server and nothing else; "
        "every other name belongs to the module that defines it"
    )


def test_nothing_borrows_a_helper_from_the_assembler() -> None:
    """Importers reach for the owning module, so no name has two homes.

    ``__all__`` alone would not catch this: ``from finos_mcp.fastmcp_server import
    _find_phrase`` keeps working while ``__all__`` says ``["mcp"]``, because
    ``__all__`` governs ``import *`` and nothing else. Neither would an import-only
    scan: ``import finos_mcp.fastmcp_server as server`` followed by
    ``server._resolve_titles`` was the majority spelling in this repository before
    #87 -- measured across the tree at ``07c8b1e``, 54 of the 95 borrowing sites in
    11 files, and 27 of the 37 in ``test_document_titles.py`` alone. An import-only
    guard would have reported the other 41 as the whole problem.

    Two further sites were invisible to both, because the name was built at runtime
    (``getattr(server, f"get_{doc_type}")``). They were found by ruff's F821 after
    the alias import was removed, not by this scan, and one of them was a patch of
    a binding no caller read -- so this guard is a floor, not a census.
    """
    offenders: dict[str, list[str]] = {}
    for path in _python_files():
        if path.name == _PREMISE_TEST:
            continue
        borrowed = [
            site
            for site in _reach_sites(path, ASSEMBLER, None)
            if not any(
                site.endswith(f" {name}") or site.endswith(f".{name}")
                for name in ASSEMBLER_EXPORTS
            )
        ]
        if borrowed:
            offenders[_report_key(path)] = borrowed

    assert not offenders, (
        f"these files reach for names via {ASSEMBLER} that it does not own -- take "
        f"each from the module that defines it: {offenders}"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from ..app import mcp", ["x.py:1: from app import mcp"]),
        ("from .app import mcp, logger", []),
        ("from finos_mcp.app import mcp", ["x.py:1: from app import mcp"]),
        ("from finos_mcp import app as a\na.mcp", ["x.py:2: a.mcp"]),
        ("from finos_mcp import app\napp.mcp", ["x.py:2: app.mcp"]),
        ("import finos_mcp.app as a\na.mcp", ["x.py:2: a.mcp"]),
        ("from ..app import logger", []),
        ("from finos_mcp import app as a\na.settings", []),
        ("from finos_mcp.fastmcp_server import mcp", []),
        ("def f():\n    from finos_mcp import app as a\na.mcp", ["x.py:3: a.mcp"]),
    ],
)
def test_the_scanner_matches_every_spelling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str, expected: list[str]
) -> None:
    """The detector is exercised directly, because the guards above cannot fail today.

    A guard whose offender set is empty on every real file is indistinguishable
    from a guard whose predicate never matches anything. These cases pin the
    spellings it must catch -- and the near misses it must not -- so a later
    simplification of the scan cannot quietly turn it into a no-op.

    The probe lives two packages deep, matching ``finos_mcp/documents/tools.py``,
    so ``level=2`` relative imports resolve the way the real ones do. That is why
    ``from .app import mcp, logger`` expects *no* match: one level up from
    ``finos_mcp.documents`` is ``finos_mcp.documents.app``, not ``finos_mcp.app``.
    The last case is the breadth-first trap -- the binding is nested inside a
    function, deeper in the tree than the use it must be known for.
    """
    module_dir = tmp_path / "src" / "finos_mcp" / "documents"
    module_dir.mkdir(parents=True)
    probe = module_dir / "x.py"
    probe.write_text(source, encoding="utf-8")
    this_module = sys.modules[__name__]
    monkeypatch.setattr(this_module, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(this_module, "_SOURCE_ROOT", tmp_path / "src" / "finos_mcp")

    assert _mcp_from_app_sites(probe) == expected


def test_the_package_exposes_no_second_route_to_an_empty_server() -> None:
    """``finos_mcp.mcp`` must not exist: it would be a third, unguarded spelling."""
    assert not hasattr(finos_mcp, "mcp"), (
        "the package root now binds `mcp`, which is a route the guards above do "
        "not scan for -- either remove it or extend the scan"
    )
