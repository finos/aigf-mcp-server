#!/usr/bin/env python3
"""Integration tests for explicit discovery-unavailable behavior.

The server no longer serves static filename fallback catalogs when live discovery
fails. Instead it returns a deterministic unavailable status/message so callers
can handle degradation explicitly.
"""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from finos_mcp.content.discovery import (
    STATIC_FRAMEWORK_FILES,
    STATIC_MITIGATION_FILES,
    STATIC_RISK_FILES,
    DiscoveryServiceManager,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_returns_unavailable_when_live_fetch_fails(monkeypatch):
    """Discovery should return explicit unavailable result instead of static fallback."""
    discovery_manager = DiscoveryServiceManager()
    discovery_service = await discovery_manager.get_discovery_service()

    async def _none(*args, **kwargs):
        return None

    monkeypatch.setattr(discovery_service, "_load_from_cache", _none)
    monkeypatch.setattr(discovery_service, "_load_expired_cache", _none)
    monkeypatch.setattr(discovery_service, "_fetch_from_github", _none)

    result = await discovery_service.discover_content()

    assert result.source == "unavailable"
    assert result.message is not None
    assert result.mitigation_files == []
    assert result.risk_files == []
    assert result.framework_files == []


@pytest.mark.integration
def test_static_catalog_exports_are_empty_for_backward_compatibility():
    """Static list exports remain importable but are intentionally empty."""
    assert STATIC_MITIGATION_FILES == ()
    assert STATIC_RISK_FILES == ()
    assert STATIC_FRAMEWORK_FILES == ()
