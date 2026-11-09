# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The shared test helpers do what the tests that use them rely on (#381)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import a_skip_is_a_failure, load_module

pytestmark = pytest.mark.unit


def test_a_skip_inside_is_turned_into_a_failure() -> None:
    """Not ``pytest.raises``: a skip escaping it would end this test as skipped."""
    try:
        with a_skip_is_a_failure():
            pytest.skip("the code under test gave up")
    except pytest.skip.Exception:
        pytest.fail("the skip passed through the helper")
    except pytest.fail.Exception as failed:
        assert "skipped where a defect" in str(failed)
    else:
        pytest.fail("the helper swallowed the skip")


def test_a_file_is_loaded_by_path(tmp_path: Path) -> None:
    script = tmp_path / "a-script.py"
    script.write_text("ANSWER = 42\n", encoding="utf-8")

    assert load_module(script, "a_script").ANSWER == 42
