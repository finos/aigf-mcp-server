# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0
"""A cache that is turned off is not a failed subsystem (#405).

With ``FINOS_MCP_ENABLE_CACHE=false`` the service reports no cache statistics,
and the health tool used to count that as an unhealthy cache: ``degraded 3/4``
from the first call, for as long as the cache stayed off.
"""

from __future__ import annotations

from typing import Any

import pytest

from finos_mcp import health_tools

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class _Service:
    def __init__(self, cache_enabled: bool, cache_statistics: dict[str, Any]) -> None:
        self._diagnostics = {
            "error_boundaries": {"fetch": {"status": "closed"}},
            "parser_statistics": {},
            "cache_statistics": cache_statistics,
            "configuration": {"cache_enabled": cache_enabled},
        }

    async def get_service_diagnostics(self) -> dict[str, Any]:
        return self._diagnostics


async def _health(
    monkeypatch: pytest.MonkeyPatch, service: _Service
) -> tuple[str, int]:
    async def get_service() -> _Service:
        return service

    monkeypatch.setattr(health_tools, "get_service", get_service)
    health = await health_tools.get_service_health()
    return health.status, health.healthy_services


async def test_a_cache_that_is_off_counts_as_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert await _health(monkeypatch, _Service(False, {})) == ("healthy", 4)


async def test_an_enabled_cache_without_statistics_still_degrades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The change must not hide a cache that is on and cannot be read."""
    assert await _health(monkeypatch, _Service(True, {})) == ("degraded", 3)
