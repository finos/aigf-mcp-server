# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Log redaction covers every GitHub token form, exceptions and third parties (#290).

The redaction pattern matched ``gh[prs]_`` and ``gho_``; the settings accept
seven prefixes. Measured: ``ghp_`` was redacted, ``github_pat_`` and ``ghu_``
were logged whole, and a ``ghp_`` value inside an exception logged with
``exc_info=True`` appeared whole in ``exception.message`` and the traceback.
Third-party records reached the root handler with no redaction at all.

No line in ``src`` logs the token today; this is a defence that did not hold.
The pattern is now built from ``GITHUB_TOKEN_PREFIXES``, the exception
message and traceback pass through the redactor, and the root handler gets
the same formatter (decided on 2026-10-13: one formatter everywhere).
"""

from __future__ import annotations

import json
import logging
import sys

import pytest

from finos_mcp.config import GITHUB_TOKEN_PREFIXES
from finos_mcp.logging import SecureJSONFormatter, setup_structured_logging

pytestmark = pytest.mark.unit


def _token(prefix: str) -> str:
    # Fine-grained tokens carry an underscore inside; the body is long enough
    # for every form GitHub issues.
    return f"{prefix}Ab12{'x' * 20}_{'y' * 40}"  # pragma: allowlist secret


def _record(msg: str, exc_info: object = None) -> logging.LogRecord:
    return logging.LogRecord(
        name="redaction-test",
        level=logging.ERROR,
        pathname="test.py",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=exc_info,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize("prefix", GITHUB_TOKEN_PREFIXES)
def test_a_token_in_the_message_is_redacted(prefix: str) -> None:
    token = _token(prefix)
    line = SecureJSONFormatter().format(_record(f"request failed for {token}"))
    assert token not in line, f"a {prefix} token is logged whole"
    assert "[REDACTED_GITHUB_TOKEN]" in json.loads(line)["message"]


@pytest.mark.parametrize("prefix", GITHUB_TOKEN_PREFIXES)
def test_a_token_inside_an_exception_is_redacted(prefix: str) -> None:
    token = _token(prefix)
    try:
        raise ValueError(f"bad credentials: {token}")
    except ValueError:
        line = SecureJSONFormatter().format(_record("failed", sys.exc_info()))
    assert token not in line, f"a {prefix} token inside an exception is logged whole"
    exception = json.loads(line)["exception"]
    assert "[REDACTED_GITHUB_TOKEN]" in exception["message"]
    assert "[REDACTED_GITHUB_TOKEN]" in exception["traceback"]


def test_a_tokens_short_tail_is_not_a_match() -> None:
    """The control: the pattern is a token, not any text after a prefix."""
    line = SecureJSONFormatter().format(_record("ghp_ is a prefix GitHub uses"))
    assert "ghp_ is a prefix" in json.loads(line)["message"]


def test_a_third_party_record_passes_the_same_redaction() -> None:
    """Records of other libraries reach the root handler; it redacts too."""
    setup_structured_logging()
    root = logging.getLogger()
    assert root.handlers, "the root logger has no handler to format with"
    token = _token("ghp_")
    for handler in root.handlers:
        assert isinstance(handler.formatter, SecureJSONFormatter), (
            f"root handler {handler!r} formats without redaction"
        )
        line = handler.formatter.format(
            logging.LogRecord(
                name="httpx",
                level=logging.INFO,
                pathname="x.py",
                lineno=1,
                msg=f"GET https://api.github.com with {token}",
                args=(),
                exc_info=None,
            )
        )
        assert token not in line
