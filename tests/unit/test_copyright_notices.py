"""The maintained source files carry the ownership decision made in #80.

Read the Git index so new staged modules are covered and build-generated files
such as setuptools-scm's version module are outside this maintained-source
contract. Match the actual leading comments, never incidental text in a
docstring, a string literal or an imported licence.
"""

import ast
import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _tracked_python_files(root: Path) -> list[Path]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.split("\0")
    return [root / path for path in tracked if path]


def test_maintained_modules_carry_the_agreed_header(
    pytestconfig: pytest.Config,
) -> None:
    root = Path(str(pytestconfig.rootpath))
    modules = [
        path
        for path in _tracked_python_files(root)
        if path.is_relative_to(root / "src")
    ]
    assert len(modules) >= 1, "source header scan found no maintained Python modules"

    expected = [
        "# Copyright 2025 FINOS",
        "# SPDX-License-Identifier: Apache-2.0",
    ]
    offenders = {}
    for module in modules:
        lines = module.read_text(encoding="utf-8").splitlines()
        if lines and lines[0].startswith("#!"):
            lines = lines[1:]
        if lines[:2] != expected:
            offenders[str(module.relative_to(root))] = lines[:2]
    assert not offenders, f"source header mismatch (actual leading lines): {offenders}"


def test_existing_module_docstring_notices_agree_with_the_headers(
    pytestconfig: pytest.Config,
) -> None:
    """A correct new header must not conceal a contradictory old notice.

    Check module docstrings across tracked Python, including tests. String
    literals inside test functions are examples, not module ownership notices.
    This does not require notices on tests that never had one.
    """
    root = Path(str(pytestconfig.rootpath))
    offenders = {}
    for module in _tracked_python_files(root):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        docstring = ast.get_docstring(tree) or ""
        notices = re.findall(r"^Copyright \d{4}[^\n]*", docstring, re.MULTILINE)
        wrong = [line for line in notices if line != "Copyright 2025 FINOS"]
        if wrong:
            offenders[str(module.relative_to(root))] = wrong
    assert not offenders, (
        f"module docstring copyright disagrees with the ownership decision: {offenders}"
    )
