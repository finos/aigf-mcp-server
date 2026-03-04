"""Architecture guard tests to prevent layering regressions."""

from __future__ import annotations

import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = PROJECT_ROOT / "src" / "finos_mcp" / "api"
FASTMCP_SERVER = PROJECT_ROOT / "src" / "finos_mcp" / "fastmcp_server.py"
SRC_ROOT = PROJECT_ROOT / "src" / "finos_mcp"


def _imports_for_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level > 0:
                # Relative import marker keeps checks simple and deterministic.
                imports.append("." * node.level + module)
            else:
                imports.append(module)
    return imports


def test_api_layers_do_not_import_infrastructure_or_content() -> None:
    """API modules should stay decoupled from direct infra/content imports."""
    api_files = sorted(
        p
        for p in API_ROOT.rglob("*.py")
        if "__pycache__" not in p.parts and p.name != "__init__.py"
    )

    banned_markers = ("finos_mcp.infrastructure", "finos_mcp.content")
    violations: list[str] = []

    for file_path in api_files:
        for imported in _imports_for_file(file_path):
            if any(marker in imported for marker in banned_markers):
                violations.append(f"{file_path}: {imported}")

    assert not violations, (
        "Direct infra/content imports found in api layer:\n" + "\n".join(violations)
    )


def test_fastmcp_server_has_no_inline_prompt_or_resource_handlers() -> None:
    """Prompt/resource registrations must remain in api registries, not inline."""
    content = FASTMCP_SERVER.read_text(encoding="utf-8")
    assert re.search(r"(?m)^@mcp\.prompt\(", content) is None
    assert re.search(r"(?m)^@mcp\.resource\(", content) is None


def test_runtime_layers_import_compat_not_openemcp_shims() -> None:
    """Internal runtime code should import compat directly, not openemcp shims."""
    target_files = sorted(
        p
        for p in SRC_ROOT.rglob("*.py")
        if "__pycache__" not in p.parts
        and "openemcp" not in p.parts
        and p.name != "__init__.py"
    )

    violations: list[str] = []
    for file_path in target_files:
        for imported in _imports_for_file(file_path):
            if "finos_mcp.openemcp" in imported or imported.startswith(".openemcp"):
                violations.append(f"{file_path}: {imported}")

    assert not violations, (
        "Runtime modules import openemcp shim modules directly:\n"
        + "\n".join(violations)
    )
