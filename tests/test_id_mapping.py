#!/usr/bin/env python3
"""Test ID mapping between search results and get operations.

This test verifies that IDs returned from search can be used directly
with get_risk() and get_mitigation() operations.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finos_mcp.fastmcp_server import (
    get_mitigation,
    get_risk,
    list_mitigations,
    list_risks,
    search_mitigations,
    search_risks,
)


async def test_risk_id_mapping():
    """Test that risk IDs from search work with get_risk()."""
    print("\n" + "=" * 80)
    print("Testing Risk ID Mapping (Search → Get)")
    print("=" * 80)

    # Step 1: List all risks to see actual IDs
    print("\n1. Listing all risks...")
    risks_list = await list_risks()
    print(f"   Found {len(risks_list.documents)} risks")
    print(f"   Source: {risks_list.source}")

    if risks_list.documents:
        first_risk = risks_list.documents[0]
        print("\n   First risk from list:")
        print(f"   - ID: {first_risk.id}")
        print(f"   - Name: {first_risk.name}")

        # Step 2: Try to get the risk using the ID from list
        print(f"\n2. Trying get_risk('{first_risk.id}')...")
        risk_content = await get_risk(first_risk.id)
        print(f"   - Title: {risk_content.title}")
        print(f"   - Content length: {len(risk_content.content)}")

        if "Failed to load" in risk_content.content or "Error" in risk_content.title:
            print(f"   ✗ FAILED: {risk_content.content[:100]}")
        else:
            print("   ✓ SUCCESS: Content loaded")

    # Step 3: Search for risks
    print("\n3. Searching for 'injection'...")
    search_results = await search_risks("injection", limit=3)
    print(f"   Found {search_results.total_found} results")

    if search_results.results:
        first_result = search_results.results[0]
        print("\n   First search result:")
        print(f"   - Framework ID: {first_result.framework_id}")
        print(f"   - Section: {first_result.section}")

        # Step 4: Extract ID and try to get the risk
        # Search returns "risk-{id}" format, so we need to strip "risk-"
        risk_id_from_search = first_result.framework_id.replace("risk-", "")
        print(f"\n4. Extracted ID: '{risk_id_from_search}'")
        print(f"   Trying get_risk('{risk_id_from_search}')...")

        risk_content = await get_risk(risk_id_from_search)
        print(f"   - Title: {risk_content.title}")
        print(f"   - Content length: {len(risk_content.content)}")

        if "Failed to load" in risk_content.content or "Error" in risk_content.title:
            print(f"   ✗ FAILED: {risk_content.content[:200]}")
            return False
        else:
            print("   ✓ SUCCESS: Content loaded correctly")
            return True

    return False


async def test_mitigation_id_mapping():
    """Test that mitigation IDs from search work with get_mitigation()."""
    print("\n" + "=" * 80)
    print("Testing Mitigation ID Mapping (Search → Get)")
    print("=" * 80)

    # Step 1: List all mitigations to see actual IDs
    print("\n1. Listing all mitigations...")
    mitigations_list = await list_mitigations()
    print(f"   Found {len(mitigations_list.documents)} mitigations")
    print(f"   Source: {mitigations_list.source}")

    if mitigations_list.documents:
        first_mit = mitigations_list.documents[0]
        print("\n   First mitigation from list:")
        print(f"   - ID: {first_mit.id}")
        print(f"   - Name: {first_mit.name}")

        # Step 2: Try to get the mitigation using the ID from list
        print(f"\n2. Trying get_mitigation('{first_mit.id}')...")
        mit_content = await get_mitigation(first_mit.id)
        print(f"   - Title: {mit_content.title}")
        print(f"   - Content length: {len(mit_content.content)}")

        if "Failed to load" in mit_content.content or "Error" in mit_content.title:
            print(f"   ✗ FAILED: {mit_content.content[:100]}")
        else:
            print("   ✓ SUCCESS: Content loaded")

    # Step 3: Search for mitigations
    print("\n3. Searching for 'data'...")
    search_results = await search_mitigations("data", limit=3)
    print(f"   Found {search_results.total_found} results")

    if search_results.results:
        first_result = search_results.results[0]
        print("\n   First search result:")
        print(f"   - Framework ID: {first_result.framework_id}")
        print(f"   - Section: {first_result.section}")

        # Step 4: Extract ID and try to get the mitigation
        # Search returns "mitigation-{id}" format, so we need to strip "mitigation-"
        mit_id_from_search = first_result.framework_id.replace("mitigation-", "")
        print(f"\n4. Extracted ID: '{mit_id_from_search}'")
        print(f"   Trying get_mitigation('{mit_id_from_search}')...")

        mit_content = await get_mitigation(mit_id_from_search)
        print(f"   - Title: {mit_content.title}")
        print(f"   - Content length: {len(mit_content.content)}")

        if "Failed to load" in mit_content.content or "Error" in mit_content.title:
            print(f"   ✗ FAILED: {mit_content.content[:200]}")
            return False
        else:
            print("   ✓ SUCCESS: Content loaded correctly")
            return True

    return False


async def main():
    """Run all ID mapping tests."""
    print("\n" + "=" * 80)
    print("ID MAPPING VERIFICATION TEST")
    print("Testing that search results can be used with get operations")
    print("=" * 80)

    risk_success = await test_risk_id_mapping()
    mitigation_success = await test_mitigation_id_mapping()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Risk ID mapping: {'✓ PASS' if risk_success else '✗ FAIL'}")
    print(f"Mitigation ID mapping: {'✓ PASS' if mitigation_success else '✗ FAIL'}")
    print("=" * 80 + "\n")

    return 0 if (risk_success and mitigation_success) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
