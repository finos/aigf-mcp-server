#!/usr/bin/env python3
"""Detailed trace of get_risk() to find the bug."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finos_mcp.content.discovery import DiscoveryServiceManager
from finos_mcp.content.service import get_content_service


async def trace_get_risk():
    """Trace through get_risk logic step by step."""
    print("\n" + "=" * 80)
    print("DETAILED TRACE: get_risk('1_adversarial-behavior-against-ai-systems')")
    print("=" * 80)

    risk_id = "1_adversarial-behavior-against-ai-systems"

    # Step 1: Discovery
    print("\nStep 1: Discovery")
    discovery_manager = DiscoveryServiceManager()
    discovery_service = await discovery_manager.get_discovery_service()
    discovery_result = await discovery_service.discover_content()

    print(f"  Source: {discovery_result.source}")
    print(f"  Total risk files: {len(discovery_result.risk_files)}")

    # Step 2: Find the risk file by ID
    print(f"\nStep 2: Finding file for risk_id='{risk_id}'")
    target_file = None
    for file_info in discovery_result.risk_files:
        file_id = file_info.filename.replace(".md", "").replace("ri-", "")
        print(f"  Checking: filename='{file_info.filename}' -> file_id='{file_id}'")
        if file_id == risk_id:
            target_file = file_info
            print("  ✓ MATCH FOUND!")
            break

    if not target_file:
        print("  ✗ NO MATCH FOUND")
        return

    print("\nTarget file found:")
    print(f"  filename: {target_file.filename}")
    print(f"  path: {target_file.path}")
    print(f"  download_url: {target_file.download_url}")

    # Step 3: Try to load the document
    print("\nStep 3: Loading document via ContentService")
    service = await get_content_service()

    doc = await service.get_document("risk", target_file.filename)

    if doc:
        print("  ✓ Document loaded successfully")
        print(f"  - Title: {doc.get('title', 'N/A')}")
        print(f"  - Content length: {len(doc.get('content', ''))} characters")
    else:
        print("  ✗ Document loading FAILED - returned None")


async def main():
    """Run detailed trace."""
    await trace_get_risk()


if __name__ == "__main__":
    asyncio.run(main())
