#!/usr/bin/env python3
"""Deprecated helper retained for compatibility.

Static fallback catalogs were removed. Discovery now returns explicit
`unavailable` status/messages when upstream repository access fails.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finos_mcp.content.discovery import DiscoveryServiceManager


async def main() -> int:
    print("Static fallback catalogs are deprecated and no longer maintained.")
    print("Checking live discovery status instead...\n")

    manager = DiscoveryServiceManager()
    service = await manager.get_discovery_service()
    result = await service.discover_content()

    print(f"source: {result.source}")
    if result.message:
        print(f"message: {result.message}")

    print(f"frameworks: {len(result.framework_files)}")
    print(f"risks: {len(result.risk_files)}")
    print(f"mitigations: {len(result.mitigation_files)}")

    return 0 if result.source in {"github_api", "cache"} else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
