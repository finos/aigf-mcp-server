# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""``FINOS_MCP_DEBUG_MODE=true`` logs every line, redacted, as JSON (#299).

The debug branch of ``setup_structured_logging`` installed a plain formatter
naming ``%(correlation_id)s``, which ``CorrelationIdFilter`` set only inside
a document fetch. Measured: six of six startup records printed
``--- Logging error --- ... KeyError: 'correlation_id'`` with fifty lines of
stack each, and the configuration error text itself says to run with debug
mode for more details. The plain formatter also redacted nothing.

One formatter now serves both modes; the JSON formatter reads the
correlation id from the context variable itself.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

import pytest

from finos_mcp import config
from finos_mcp.logging import SecureJSONFormatter, setup_structured_logging

pytestmark = pytest.mark.unit


def test_importing_the_server_in_debug_mode_logs_without_error() -> None:
    env = {
        **os.environ,
        "FINOS_MCP_DEBUG_MODE": "true",
        "FINOS_MCP_MCP_TRANSPORT": "stdio",
    }
    env.pop(config.ENV_FILE_VARIABLE, None)
    completed = subprocess.run(
        [sys.executable, "-c", "import finos_mcp.fastmcp_server"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert "Logging error" not in completed.stderr, completed.stderr[-2000:]
    assert "correlation_id" not in completed.stderr or '"correlation_id"' in (
        completed.stderr
    ), "the format string names a field the record does not carry"
    # The lines that did come out are what debug mode promises: records.
    assert "Configuration loaded successfully" in completed.stderr


def test_debug_mode_installs_the_redacting_json_formatter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FINOS_MCP_DEBUG_MODE", "true")
    monkeypatch.delenv(config.ENV_FILE_VARIABLE, raising=False)
    monkeypatch.setattr(config._settings_manager, "_settings", None)

    logger = setup_structured_logging()

    assert config.get_settings().debug_mode is True, "debug mode was not on"
    handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
    assert handlers, "no stream handler installed"
    for handler in handlers:
        assert isinstance(handler.formatter, SecureJSONFormatter), (
            "debug mode formats without redaction"
        )
    record = logging.LogRecord(
        name=logger.name,
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="hello ghp_" + "a" * 40,
        args=(),
        exc_info=None,
    )  # pragma: allowlist secret
    line = handlers[0].formatter.format(record)  # type: ignore[union-attr]
    assert json.loads(line)["message"] == "hello [REDACTED_GITHUB_TOKEN]"
