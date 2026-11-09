# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The rate-limiting section describes one budget per caller (#335).

``docs/api/mcp-tools.md`` said tool calls and search operations had 600 a
minute each. ``DoSProtectionMiddleware.on_request`` counts every MCP request
the server receives, the handshake included, against one budget per caller;
a search is a tool call. The section now says so, and this test holds it:
no kind of request may reappear with an allowance of its own, and the
number stated is the setting's default.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from finos_mcp.config import Settings

DOC = Path(__file__).resolve().parents[2] / "docs" / "api" / "mcp-tools.md"


def _rate_limiting_section() -> str:
    text = DOC.read_text(encoding="utf-8")
    match = re.search(r"^## Rate Limiting\n(.*?)(?=^## )", text, re.S | re.M)
    assert match, "docs/api/mcp-tools.md has no '## Rate Limiting' section"
    return match.group(1)


@pytest.mark.unit
def test_no_kind_of_request_has_an_allowance_of_its_own() -> None:
    section = _rate_limiting_section()
    assert "Search operations" not in section, section
    assert "one budget per caller" in section.lower(), section
    assert "every mcp request" in section.lower(), section
    # One line states the per-minute number, and it names the setting.
    per_minute = [line for line in section.splitlines() if "a minute" in line]
    assert len(per_minute) == 1, per_minute
    assert "FINOS_MCP_DOS_MAX_REQUESTS_PER_MINUTE" in per_minute[0]


@pytest.mark.unit
def test_the_numbers_stated_are_the_defaults() -> None:
    section = _rate_limiting_section()
    fields = Settings.model_fields
    assert f"{fields['dos_max_requests_per_minute'].default} a minute" in section
    assert f"{fields['dos_max_concurrent_requests'].default} per caller" in section
