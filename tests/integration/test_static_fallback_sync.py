#!/usr/bin/env python3
"""Integration test to verify static fallback lists match GitHub API.

This test ensures the static fallback lists in discovery.py stay synchronized
with the actual GitHub repository content, preventing ID mapping mismatches.

Run this test:
- Locally before commits that change discovery.py
- In CI to catch repository changes
- Periodically (weekly) to detect upstream changes
"""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from finos_mcp.content.discovery import (
    DiscoveryServiceManager,
    STATIC_FRAMEWORK_FILES,
    STATIC_MITIGATION_FILES,
    STATIC_RISK_FILES,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_static_fallback_matches_github_api():
    """Verify static fallback lists match current GitHub repository content.

    This test prevents the bug where outdated static fallback lists cause
    ID mapping mismatches between list/search and get operations.
    """
    # Get actual files from GitHub API
    discovery_manager = DiscoveryServiceManager()
    discovery_service = await discovery_manager.get_discovery_service()
    discovery_result = await discovery_service.discover_content()

    # Skip if GitHub API unavailable (network issues, rate limit)
    if discovery_result.source != "github_api":
        pytest.skip(
            f"GitHub API unavailable (using {discovery_result.source}), "
            "cannot verify static fallback sync"
        )

    # Extract actual filenames from GitHub API
    actual_mitigations = sorted([f.filename for f in discovery_result.mitigation_files])
    actual_risks = sorted([f.filename for f in discovery_result.risk_files])
    actual_frameworks = sorted([f.filename for f in discovery_result.framework_files])

    # Compare with static fallback lists
    static_mitigations = sorted(STATIC_MITIGATION_FILES)
    static_risks = sorted(STATIC_RISK_FILES)
    static_frameworks = sorted(STATIC_FRAMEWORK_FILES)

    # Detailed reporting for each mismatch
    mismatches = []

    # Check mitigations
    if actual_mitigations != static_mitigations:
        missing = set(actual_mitigations) - set(static_mitigations)
        extra = set(static_mitigations) - set(actual_mitigations)
        mismatches.append(
            f"\nMitigation files mismatch:\n"
            f"  GitHub API count: {len(actual_mitigations)}\n"
            f"  Static fallback count: {len(static_mitigations)}\n"
            f"  Missing from static: {missing or 'none'}\n"
            f"  Extra in static: {extra or 'none'}"
        )

    # Check risks
    if actual_risks != static_risks:
        missing = set(actual_risks) - set(static_risks)
        extra = set(static_risks) - set(actual_risks)
        mismatches.append(
            f"\nRisk files mismatch:\n"
            f"  GitHub API count: {len(actual_risks)}\n"
            f"  Static fallback count: {len(static_risks)}\n"
            f"  Missing from static: {missing or 'none'}\n"
            f"  Extra in static: {extra or 'none'}"
        )

    # Check frameworks
    if actual_frameworks != static_frameworks:
        missing = set(actual_frameworks) - set(static_frameworks)
        extra = set(static_frameworks) - set(actual_frameworks)
        mismatches.append(
            f"\nFramework files mismatch:\n"
            f"  GitHub API count: {len(actual_frameworks)}\n"
            f"  Static fallback count: {len(static_frameworks)}\n"
            f"  Missing from static: {missing or 'none'}\n"
            f"  Extra in static: {extra or 'none'}"
        )

    # Fail test if any mismatches found
    if mismatches:
        error_msg = (
            "\n" + "=" * 80 + "\n"
            "STATIC FALLBACK OUT OF SYNC WITH GITHUB API\n"
            + "=" * 80
            + "".join(mismatches)
            + "\n\n"
            + "To fix this issue:\n"
            + "  1. Run: python scripts/update-static-fallback.py\n"
            + "  2. Review the generated code\n"
            + "  3. Update src/finos_mcp/content/discovery.py\n"
            + "  4. Commit the changes\n"
            + "=" * 80
        )
        pytest.fail(error_msg)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fallback_and_api_produce_same_ids():
    """Verify static fallback and GitHub API produce identical document IDs.

    This ensures that whether the system uses static fallback or GitHub API,
    the document IDs returned by list operations match the filenames expected
    by get operations.
    """
    discovery_manager = DiscoveryServiceManager()
    discovery_service = await discovery_manager.get_discovery_service()

    # Force both discovery methods
    api_result = await discovery_service._fetch_from_github()
    fallback_result = discovery_service._create_static_fallback()

    # Skip if GitHub API unavailable
    if not api_result:
        pytest.skip("GitHub API unavailable, cannot compare with static fallback")

    # Extract IDs from both methods
    def extract_ids(files):
        return sorted([f.filename.replace(".md", "").replace(".yml", "") for f in files])

    api_mitigation_ids = extract_ids(api_result.mitigation_files)
    fallback_mitigation_ids = extract_ids(fallback_result.mitigation_files)

    api_risk_ids = extract_ids(api_result.risk_files)
    fallback_risk_ids = extract_ids(fallback_result.risk_files)

    api_framework_ids = extract_ids(api_result.framework_files)
    fallback_framework_ids = extract_ids(fallback_result.framework_files)

    # Compare ID sets
    mismatches = []

    if api_mitigation_ids != fallback_mitigation_ids:
        mismatches.append(
            f"Mitigation IDs differ:\n"
            f"  API: {set(api_mitigation_ids) - set(fallback_mitigation_ids)}\n"
            f"  Fallback: {set(fallback_mitigation_ids) - set(api_mitigation_ids)}"
        )

    if api_risk_ids != fallback_risk_ids:
        mismatches.append(
            f"Risk IDs differ:\n"
            f"  API: {set(api_risk_ids) - set(fallback_risk_ids)}\n"
            f"  Fallback: {set(fallback_risk_ids) - set(api_risk_ids)}"
        )

    if api_framework_ids != fallback_framework_ids:
        mismatches.append(
            f"Framework IDs differ:\n"
            f"  API: {set(api_framework_ids) - set(fallback_framework_ids)}\n"
            f"  Fallback: {set(fallback_framework_ids) - set(api_framework_ids)}"
        )

    if mismatches:
        pytest.fail(
            "Static fallback produces different IDs than GitHub API:\n"
            + "\n".join(mismatches)
            + "\n\nRun: python scripts/update-static-fallback.py"
        )


if __name__ == "__main__":
    # Allow running this test directly
    import asyncio

    print("Running static fallback synchronization tests...\n")

    async def run_tests():
        try:
            await test_static_fallback_matches_github_api()
            print("✓ Static fallback matches GitHub API")
        except Exception as e:
            print(f"✗ Static fallback test failed:\n{e}")
            return 1

        try:
            await test_fallback_and_api_produce_same_ids()
            print("✓ Fallback and API produce same IDs")
        except Exception as e:
            print(f"✗ ID comparison test failed:\n{e}")
            return 1

        return 0

    exit_code = asyncio.run(run_tests())
    sys.exit(exit_code)
