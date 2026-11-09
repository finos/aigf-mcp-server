# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Helpers more than one test module needs (#381).

Imported as ``tests.helpers``: pytest puts the repository root on the path
(``pythonpath`` in pyproject.toml), and mypy names the test modules from it.
Fixtures live in ``tests/conftest.py``.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import pytest


def load_module(path: Path, name: str) -> ModuleType:
    """The Python file at ``path``, imported as ``name``.

    For files that cannot be imported by name: ``scripts/`` and the test
    directories are not packages, and some script names have hyphens.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"{path} must exist"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def a_skip_is_a_failure() -> Iterator[None]:
    """Fail where the code inside skips.

    A skip raised inside ``pytest.raises(SomeError)`` is not caught by it: it
    ends the test as skipped, so a test of "this is not skipped" would report
    the opposite of what it found without failing.
    """
    try:
        yield
    except pytest.skip.Exception as skipped:
        pytest.fail(f"skipped where a defect had to be reported: {skipped}")
