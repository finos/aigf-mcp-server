#!/usr/bin/env python3
"""Debug ID matching in get_risk and get_mitigation."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finos_mcp.content.discovery import DiscoveryServiceManager


async def debug_risk_matching():
    """Debug why risk ID matching fails."""
    print("\n" + "=" * 80)
    print("DEBUG: Risk ID Matching")
    print("=" * 80)

    # Get discovery service
    discovery_manager = DiscoveryServiceManager()
    discovery_service = await discovery_manager.get_discovery_service()
    discovery_result = await discovery_service.discover_content()

    print(f"\nSource: {discovery_result.source}")
    print(f"Total risk files: {len(discovery_result.risk_files)}")

    # Test ID: 1_adversarial-behavior-against-ai-systems (from list_risks)
    test_risk_id = "1_adversarial-behavior-against-ai-systems"
    print(f"\nLooking for risk ID: '{test_risk_id}'")

    print("\nAll risk files:")
    for i, file_info in enumerate(discovery_result.risk_files[:5], 1):
        file_id = file_info.filename.replace(".md", "").replace("ri-", "")
        matches = "✓ MATCH" if file_id == test_risk_id else ""
        print(f"  {i}. Filename: {file_info.filename}")
        print(f"     Extracted ID: '{file_id}' {matches}")

    # Now try searching
    target_file = None
    for file_info in discovery_result.risk_files:
        file_id = file_info.filename.replace(".md", "").replace("ri-", "")
        if file_id == test_risk_id:
            target_file = file_info
            break

    if target_file:
        print(f"\n✓ Found matching file: {target_file.filename}")
    else:
        print(f"\n✗ No matching file found for ID: '{test_risk_id}'")
        print("\nAll extracted IDs:")
        for file_info in discovery_result.risk_files:
            file_id = file_info.filename.replace(".md", "").replace("ri-", "")
            print(f"  - '{file_id}'")


async def debug_mitigation_matching():
    """Debug why mitigation ID matching works."""
    print("\n" + "=" * 80)
    print("DEBUG: Mitigation ID Matching")
    print("=" * 80)

    # Get discovery service
    discovery_manager = DiscoveryServiceManager()
    discovery_service = await discovery_manager.get_discovery_service()
    discovery_result = await discovery_service.discover_content()

    print(f"\nSource: {discovery_result.source}")
    print(f"Total mitigation files: {len(discovery_result.mitigation_files)}")

    # Test ID: 1_ai-data-leakage-prevention-and-detection (from list_mitigations)
    test_mit_id = "1_ai-data-leakage-prevention-and-detection"
    print(f"\nLooking for mitigation ID: '{test_mit_id}'")

    print("\nAll mitigation files:")
    for i, file_info in enumerate(discovery_result.mitigation_files[:5], 1):
        file_id = file_info.filename.replace(".md", "").replace("mi-", "")
        matches = "✓ MATCH" if file_id == test_mit_id else ""
        print(f"  {i}. Filename: {file_info.filename}")
        print(f"     Extracted ID: '{file_id}' {matches}")

    # Now try searching
    target_file = None
    for file_info in discovery_result.mitigation_files:
        file_id = file_info.filename.replace(".md", "").replace("mi-", "")
        if file_id == test_mit_id:
            target_file = file_info
            break

    if target_file:
        print(f"\n✓ Found matching file: {target_file.filename}")
    else:
        print(f"\n✗ No matching file found for ID: '{test_mit_id}'")
        print("\nAll extracted IDs:")
        for file_info in discovery_result.mitigation_files:
            file_id = file_info.filename.replace(".md", "").replace("mi-", "")
            print(f"  - '{file_id}'")


async def main():
    """Run debug tests."""
    await debug_risk_matching()
    await debug_mitigation_matching()


if __name__ == "__main__":
    asyncio.run(main())
