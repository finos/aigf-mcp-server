#!/usr/bin/env python3
"""Integration test to verify static fallback lists match GitHub API.

This test ensures the static catalog (``static_catalog.py``) stays synchronized
with the actual GitHub repository content, preventing ID mapping mismatches.

Run this test:
- Locally before commits that change static_catalog.py
- In CI to catch repository changes
- Periodically (weekly) to detect upstream changes
"""

import os
import sys
from pathlib import Path

import httpx
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from finos_mcp.content.static_catalog import (
    STATIC_FRAMEWORK_FILES,
    STATIC_MITIGATION_FILES,
    STATIC_RISK_FILES,
)
from finos_mcp.exceptions import CircuitBreakerError, GitHubRateLimitError
from tests.helpers import load_module

_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "update-static-fallback.py"

#: Set by the weekly workflow (#297): an API that cannot be asked is then a
#: failure, not a skip. Two skips exit 0, and the step reported "synchronized"
#: having compared nothing.
NO_SKIP_VARIABLE = "FINOS_STATIC_SYNC_NO_SKIP"

# The only outcomes that mean "the API could not be asked". Anything else --
# a 404 because upstream moved a directory, a response that is not a listing --
# is a finding and must fail, not skip.
_UNREACHABLE = (
    httpx.TransportError,
    TimeoutError,
    OSError,
    GitHubRateLimitError,
    CircuitBreakerError,
)


def _load_update_script():
    """Import ``scripts/update-static-fallback.py`` by path.

    The test reads the listing through the script's own function, so the check
    and the remedy its failure message names cannot disagree about what GitHub
    holds. ``scripts/`` is not a package and the filename has hyphens, so it
    cannot be imported by name.
    """
    return load_module(_SCRIPT, "update_static_fallback")


async def _live_listing() -> dict[str, list[str]]:
    """The filenames GitHub lists now, whatever the discovery disk cache holds.

    Skips only when the API cannot be reached or has throttled this address,
    and not even then under ``NO_SKIP_VARIABLE``. A warm cache used to skip
    this module, so a local run reported no failure with the lists three
    documents out of date (#207).
    """
    try:
        listing: dict[str, list[str]] = await _load_update_script().fetch_live_listing()
        return listing
    except _UNREACHABLE as exc:
        reason = f"GitHub API unreachable ({type(exc).__name__}: {exc})"
        if os.environ.get(NO_SKIP_VARIABLE, "").strip():
            pytest.fail(
                f"{reason}; {NO_SKIP_VARIABLE} is set, so this run had to compare "
                "the listing and could not"
            )
        pytest.skip(f"{reason}, cannot verify static fallback sync")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_static_fallback_matches_github_api():
    """Verify static fallback lists match current GitHub repository content.

    This test prevents the bug where outdated static fallback lists cause
    ID mapping mismatches between list/search and get operations.
    """
    listing = await _live_listing()
    actual_mitigations = listing["mitigations"]
    actual_risks = listing["risks"]
    actual_frameworks = listing["frameworks"]

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
            + "  2. Review the diff of src/finos_mcp/content/static_catalog.py\n"
            + "  3. Commit it\n"
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
    listing = await _live_listing()

    def extract_ids(filenames):
        return sorted(
            [name.replace(".md", "").replace(".yml", "") for name in filenames]
        )

    api_mitigation_ids = extract_ids(listing["mitigations"])
    fallback_mitigation_ids = extract_ids(STATIC_MITIGATION_FILES)

    api_risk_ids = extract_ids(listing["risks"])
    fallback_risk_ids = extract_ids(STATIC_RISK_FILES)

    api_framework_ids = extract_ids(listing["frameworks"])
    fallback_framework_ids = extract_ids(STATIC_FRAMEWORK_FILES)

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
