# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The risk and mitigation tools are one body each, not one written twice
(#314).

``get_risk`` and ``get_mitigation`` differed in the prefix, the type word,
the listing tool's name and nothing else, and so did ``list_risks`` and
``list_mitigations``; the nine facts a client relies on per get tool lived
in three places, so #193 and #216 were each fixed three times. The
published tools keep their names and docstrings and hand everything to
``_get_document`` or ``_list_documents`` with a ``_Kind``. This test reads
the bodies: a tool whose body is anything but a docstring and that one
``return`` has grown a second copy.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from finos_mcp.documents import tools

PAIRS = {
    "get_risk": "_get_document",
    "get_mitigation": "_get_document",
    "list_risks": "_list_documents",
    "list_mitigations": "_list_documents",
}


def _body_without_docstring(name: str) -> list[ast.stmt]:
    source = inspect.getsource(getattr(tools, name))
    function = ast.parse(source).body[0]
    assert isinstance(function, ast.AsyncFunctionDef)
    body = function.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return body


@pytest.mark.unit
@pytest.mark.parametrize(("tool", "shared"), sorted(PAIRS.items()))
def test_the_tool_is_one_return_of_the_shared_body(tool: str, shared: str) -> None:
    body = _body_without_docstring(tool)
    assert len(body) == 1, f"{tool} has {len(body)} statements past its docstring"
    statement = body[0]
    assert isinstance(statement, ast.Return), f"{tool}: {ast.dump(statement)[:80]}"
    value = statement.value
    assert isinstance(value, ast.Await)
    call = value.value
    assert isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    assert call.func.id == shared, f"{tool} returns {call.func.id}, not {shared}"


@pytest.mark.unit
def test_each_document_error_is_raised_from_the_shared_body_only() -> None:
    """A client-facing error sentence for these documents has one call site."""
    source = inspect.getsource(tools)
    module = ast.parse(source)
    raisers: dict[str, set[str]] = {}
    for function in module.body:
        if not isinstance(function, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Raise)
                and isinstance(node.exc, ast.Call)
                and isinstance(node.exc.func, ast.Name)
                and node.exc.func.id
                in {"UnknownDocumentError", "DocumentUnavailableError"}
            ):
                raisers.setdefault(node.exc.func.id, set()).add(function.name)
    # get_framework keeps its own body for the YAML parse and formatter.
    for error, functions in raisers.items():
        assert functions <= {"_get_document", "get_framework"}, (
            f"{error} is raised from {sorted(functions)}"
        )
    assert "_get_document" in raisers["UnknownDocumentError"]
    assert "_get_document" in raisers["DocumentUnavailableError"]
