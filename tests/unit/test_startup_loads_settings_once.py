# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Settings are built once, and a bad configuration is reported, not traced (#300).

``app.py`` imported the security modules before it called
``validate_settings_on_startup()``, and ``get_logger()`` at import called
``get_settings()``, so the first module that owned a logger built the
settings. Measured with ``FINOS_MCP_MCP_TRANSPORT=http`` and nothing else:
exit 1, a forty-line traceback through five modules, and the string
``Configuration Error`` zero times. On a good start the settings were built
twice (``get_settings()`` at import, ``reload=True`` at validation), on
stdio generating two cache secrets.

Decided on 2026-10-13: loggers stop reading settings at import.
``get_logger()`` hands out a logger that formats and redacts but carries no
level; ``validate_settings_on_startup()`` is the one place settings are
built, and it applies the level once.

Both tests run the real entry point in a subprocess, because the defect is
in the order modules are imported.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from finos_mcp import config

pytestmark = pytest.mark.unit


def _run(code: str, **env: str) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("FINOS_MCP_")
    }
    environment.update(env)
    return subprocess.run(
        [sys.executable, "-c", code],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_a_bad_configuration_is_reported_without_a_traceback() -> None:
    completed = _run(
        "import runpy; runpy.run_module('finos_mcp.fastmcp_main', run_name='__main__')",
        FINOS_MCP_MCP_TRANSPORT="http",
    )
    assert completed.returncode == 1, completed.stderr[-2000:]
    assert "Traceback" not in completed.stderr, completed.stderr[-3000:]
    assert "Configuration Error" in completed.stderr, completed.stderr[-2000:]
    # What is wrong with this configuration, named.
    assert "auth" in completed.stderr.lower()


def test_settings_are_built_once_on_a_good_start() -> None:
    code = """
import finos_mcp.config as config
built = []
original = config.Settings.__init__
def counted(self, **values):
    built.append(1)
    original(self, **values)
config.Settings.__init__ = counted
import finos_mcp.fastmcp_server
print(len(built))
"""
    completed = _run(code, FINOS_MCP_MCP_TRANSPORT="stdio")
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert completed.stdout.strip() == "1", (
        f"Settings was built {completed.stdout.strip()} times"
    )


def test_a_logger_taken_before_validation_formats_and_redacts() -> None:
    """The bare logger has no level of its own but is not a plain one."""
    code = """
import json, logging
from finos_mcp.logging import SecureJSONFormatter, get_logger
import finos_mcp.config as config
assert config._settings_manager._settings is None, "settings were built at import"
app = get_logger()
assert app.handlers and all(isinstance(h.formatter, SecureJSONFormatter) for h in app.handlers)
child = get_logger("probe")
assert child.level == logging.NOTSET, child.level
print("ok")
"""
    completed = _run(code)
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert completed.stdout.strip() == "ok"


def test_the_singleton_still_reloads_on_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``reload=True`` is for tests and stays; it just is not used at startup."""
    monkeypatch.setattr(config._settings_manager, "_settings", None)
    first = config.get_settings()
    assert config.get_settings() is first
    assert config.get_settings(reload=True) is not first
