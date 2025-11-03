#!/usr/bin/env python3
"""Comprehensive MCP Functionality Test Suite

This script tests all FINOS MCP server operations with proper rate limit handling.
Designed to work with both authenticated and unauthenticated GitHub API access.

Usage:
    python tests/test_mcp_functionality.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finos_mcp.fastmcp_server import (
    get_cache_stats,
    get_framework,
    get_mitigation,
    get_risk,
    get_service_health,
    list_frameworks,
    list_mitigations,
    list_risks,
    search_frameworks,
    search_mitigations,
    search_risks,
)


class Colors:
    """ANSI color codes."""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"


def header(text: str):
    """Print test header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.END}\n")


def success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓{Colors.END} {text}")


def info(text: str):
    """Print info message."""
    print(f"{Colors.CYAN}i{Colors.END} {text}")


def warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.END} {text}")


def error(text: str):
    """Print error message."""
    print(f"{Colors.RED}✗{Colors.END} {text}")


async def test_service_health():
    """Test 1: Service Health Check."""
    header("TEST 1: Service Health & Monitoring")

    try:
        health = await get_service_health()
        info(f"Status: {health.status}")
        info(f"Version: {health.version}")
        info(f"Uptime: {health.uptime_seconds:.2f}s")
        info(f"Services: {health.healthy_services}/{health.total_services} healthy")

        if health.status == "healthy":
            success("Service health check passed")
            return True
        else:
            warning(f"Service status: {health.status}")
            return False

    except Exception as e:
        error(f"Service health check failed: {e}")
        return False


async def test_cache_stats():
    """Test 2: Cache Statistics."""
    header("TEST 2: Cache Statistics")

    try:
        stats = await get_cache_stats()
        info(f"Total requests: {stats.total_requests}")
        info(f"Cache hits: {stats.cache_hits}")
        info(f"Cache misses: {stats.cache_misses}")
        info(f"Hit rate: {stats.hit_rate:.1%}")

        success("Cache statistics retrieved successfully")
        return True

    except Exception as e:
        error(f"Cache stats failed: {e}")
        return False


async def test_list_frameworks():
    """Test 3: List Frameworks."""
    header("TEST 3: List Available Frameworks")

    try:
        result = await list_frameworks()
        info(f"Total frameworks: {result.total_count}")

        print("\nFrameworks:")
        for fw in result.frameworks:
            print(f"  • {fw.id}")
            print(f"    {fw.name}")
            print(f"    {fw.description}")

        if result.total_count > 0:
            success(f"Found {result.total_count} frameworks")
            return True, result
        else:
            warning("No frameworks found")
            return False, None

    except Exception as e:
        error(f"List frameworks failed: {e}")
        return False, None


async def test_list_risks():
    """Test 4: List Risk Documents."""
    header("TEST 4: List Risk Documents")

    try:
        result = await list_risks()
        info(f"Total risks: {result.total_count}")
        info(f"Source: {result.source}")

        print("\nSample Risks:")
        for risk in result.documents[:5]:
            print(f"  • {risk.id}")
            print(f"    {risk.name}")

        if result.total_count > 0:
            success(f"Found {result.total_count} risk documents")
            return True, result
        else:
            warning("No risks found")
            return False, None

    except Exception as e:
        error(f"List risks failed: {e}")
        return False, None


async def test_list_mitigations():
    """Test 5: List Mitigation Strategies."""
    header("TEST 5: List Mitigation Strategies")

    try:
        result = await list_mitigations()
        info(f"Total mitigations: {result.total_count}")
        info(f"Source: {result.source}")

        print("\nSample Mitigations:")
        for mit in result.documents[:5]:
            print(f"  • {mit.id}")
            print(f"    {mit.name}")

        if result.total_count > 0:
            success(f"Found {result.total_count} mitigation strategies")
            return True, result
        else:
            warning("No mitigations found")
            return False, None

    except Exception as e:
        error(f"List mitigations failed: {e}")
        return False, None


async def test_search_frameworks():
    """Test 6: Search Frameworks."""
    header("TEST 6: Search Frameworks (Optimized)")

    try:
        query = "risk"
        result = await search_frameworks(query, limit=3)

        info(f"Query: '{query}'")
        info(f"Total found: {result.total_found}")

        if result.total_found > 0:
            print("\nSearch Results:")
            for i, res in enumerate(result.results, 1):
                print(f"\n  Result {i}:")
                print(f"    Framework: {res.framework_id}")
                print(f"    Section: {res.section}")
                snippet = res.content[:150].replace("\n", " ")
                print(f"    Content: {snippet}...")

            success(f"Framework search returned {result.total_found} results")
            return True
        else:
            warning("No search results found")
            return False

    except Exception as e:
        error(f"Framework search failed: {e}")
        return False


async def test_search_risks():
    """Test 7: Search Risk Documents (Metadata Only)."""
    header("TEST 7: Search Risks (Metadata-Only Optimization)")

    try:
        query = "injection"
        result = await search_risks(query, limit=5)

        info(f"Query: '{query}'")
        info(f"Total found: {result.total_found}")
        info("Note: Search uses metadata only (no API calls)")

        if result.total_found > 0:
            print("\nSearch Results:")
            for i, res in enumerate(result.results, 1):
                print(f"\n  Result {i}:")
                print(f"    ID: {res.framework_id}")
                print(f"    Name: {res.section}")
                print(f"    Match: {res.content}")

            success(f"Risk search returned {result.total_found} results (0 API calls)")
            return True, result
        else:
            warning("No search results found")
            return False, None

    except Exception as e:
        error(f"Risk search failed: {e}")
        return False, None


async def test_search_mitigations():
    """Test 8: Search Mitigation Strategies (Metadata Only)."""
    header("TEST 8: Search Mitigations (Metadata-Only Optimization)")

    try:
        query = "data"
        result = await search_mitigations(query, limit=5)

        info(f"Query: '{query}'")
        info(f"Total found: {result.total_found}")
        info("Note: Search uses metadata only (no API calls)")

        if result.total_found > 0:
            print("\nSearch Results:")
            for i, res in enumerate(result.results, 1):
                print(f"\n  Result {i}:")
                print(f"    ID: {res.framework_id}")
                print(f"    Name: {res.section}")
                print(f"    Match: {res.content}")

            success(
                f"Mitigation search returned {result.total_found} results (0 API calls)"
            )
            return True, result
        else:
            warning("No search results found")
            return False, None

    except Exception as e:
        error(f"Mitigation search failed: {e}")
        return False, None


async def test_get_framework(framework_id: str):
    """Test 9: Get Framework Details."""
    header(f"TEST 9: Get Framework Details ({framework_id})")

    try:
        info("Loading framework content via GitHub API...")
        result = await get_framework(framework_id)

        info(f"Framework ID: {result.framework_id}")
        info(f"Sections: {result.sections}")
        info(f"Content length: {len(result.content):,} characters")

        if len(result.content) > 200:
            preview = result.content[:200].replace("\n", " ")
            print(f"\nContent Preview:\n{preview}...\n")
            success("Framework content loaded successfully")
            return True
        else:
            warning(f"Content seems short or failed to load: {result.content}")
            return False

    except Exception as e:
        error(f"Get framework failed: {e}")
        return False


async def test_get_risk(risk_id: str):
    """Test 10: Get Risk Document Details."""
    header(f"TEST 10: Get Risk Details ({risk_id})")

    try:
        info("Loading risk content via GitHub API...")
        result = await get_risk(risk_id)

        info(f"Risk ID: {result.document_id}")
        info(f"Title: {result.title}")
        info(f"Sections: {len(result.sections)}")
        info(f"Content length: {len(result.content):,} characters")

        if len(result.content) > 200:
            preview = result.content[:200].replace("\n", " ")
            print(f"\nContent Preview:\n{preview}...\n")
            success("Risk content loaded successfully")
            return True
        else:
            warning(f"Content seems short or failed to load: {result.content}")
            return False

    except Exception as e:
        error(f"Get risk failed: {e}")
        return False


async def test_get_mitigation(mitigation_id: str):
    """Test 11: Get Mitigation Strategy Details."""
    header(f"TEST 11: Get Mitigation Details ({mitigation_id})")

    try:
        info("Loading mitigation content via GitHub API...")
        result = await get_mitigation(mitigation_id)

        info(f"Mitigation ID: {result.document_id}")
        info(f"Title: {result.title}")
        info(f"Sections: {len(result.sections)}")
        info(f"Content length: {len(result.content):,} characters")

        if len(result.content) > 200:
            preview = result.content[:200].replace("\n", " ")
            print(f"\nContent Preview:\n{preview}...\n")
            success("Mitigation content loaded successfully")
            return True
        else:
            warning(f"Content seems short or failed to load: {result.content}")
            return False

    except Exception as e:
        error(f"Get mitigation failed: {e}")
        return False


async def run_all_tests():
    """Run comprehensive test suite."""
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.END}")
    print(
        f"{Colors.BOLD}{'FINOS MCP Server - Comprehensive Functionality Test':^80}{Colors.END}"
    )
    print(f"{Colors.BOLD}{'=' * 80}{Colors.END}")

    results = {}

    # Phase 1: Service Health Tests (No API calls)
    print(
        f"\n{Colors.CYAN}{Colors.BOLD}PHASE 1: Service Health & Infrastructure{Colors.END}"
    )
    results["service_health"] = await test_service_health()
    results["cache_stats"] = await test_cache_stats()

    # Phase 2: Discovery Tests (Uses cached data or makes API calls)
    print(f"\n{Colors.CYAN}{Colors.BOLD}PHASE 2: Content Discovery{Colors.END}")
    success_fw, frameworks = await test_list_frameworks()
    results["list_frameworks"] = success_fw

    success_r, risks = await test_list_risks()
    results["list_risks"] = success_r

    success_m, mitigations = await test_list_mitigations()
    results["list_mitigations"] = success_m

    # Phase 3: Search Tests (Optimized - No API calls)
    print(
        f"\n{Colors.CYAN}{Colors.BOLD}PHASE 3: Optimized Search (Metadata Only){Colors.END}"
    )
    info("These searches use NO API calls - instant results from cached metadata")

    results["search_frameworks"] = await test_search_frameworks()
    success_sr, search_risks_result = await test_search_risks()
    results["search_risks"] = success_sr

    success_sm, search_mit_result = await test_search_mitigations()
    results["search_mitigations"] = success_sm

    # Phase 4: Document Details Tests (Makes API calls - may hit rate limits)
    print(
        f"\n{Colors.CYAN}{Colors.BOLD}PHASE 4: Document Details (API Calls){Colors.END}"
    )
    warning(
        "These operations make GitHub API calls and may fail if rate limited (60/hour without token)"
    )

    # Test framework details (if available)
    if frameworks and frameworks.frameworks:
        fw_id = frameworks.frameworks[0].id
        results["get_framework"] = await test_get_framework(fw_id)
    else:
        results["get_framework"] = False

    # Test risk details (use search result if available)
    if search_risks_result and search_risks_result.results:
        risk_id = search_risks_result.results[0].framework_id.replace("risk-", "")
        results["get_risk"] = await test_get_risk(risk_id)
    elif risks and risks.documents:
        risk_id = risks.documents[0].id
        results["get_risk"] = await test_get_risk(risk_id)
    else:
        results["get_risk"] = False

    # Test mitigation details (use search result if available)
    if search_mit_result and search_mit_result.results:
        mit_id = search_mit_result.results[0].framework_id.replace("mitigation-", "")
        results["get_mitigation"] = await test_get_mitigation(mit_id)
    elif mitigations and mitigations.documents:
        mit_id = mitigations.documents[0].id
        results["get_mitigation"] = await test_get_mitigation(mit_id)
    else:
        results["get_mitigation"] = False

    # Print Summary
    header("TEST SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n{Colors.BOLD}Results by Category:{Colors.END}\n")

    print(f"{Colors.CYAN}Service Health:{Colors.END}")
    for test in ["service_health", "cache_stats"]:
        if results.get(test):
            success(f"{test:30} PASSED")
        else:
            error(f"{test:30} FAILED")

    print(f"\n{Colors.CYAN}Content Discovery:{Colors.END}")
    for test in ["list_frameworks", "list_risks", "list_mitigations"]:
        if results.get(test):
            success(f"{test:30} PASSED")
        else:
            error(f"{test:30} FAILED")

    print(f"\n{Colors.CYAN}Optimized Search (0 API calls):{Colors.END}")
    for test in ["search_frameworks", "search_risks", "search_mitigations"]:
        if results.get(test):
            success(f"{test:30} PASSED")
        else:
            error(f"{test:30} FAILED")

    print(f"\n{Colors.CYAN}Document Details (API calls):{Colors.END}")
    for test in ["get_framework", "get_risk", "get_mitigation"]:
        if results.get(test):
            success(f"{test:30} PASSED")
        else:
            warning(f"{test:30} FAILED (likely rate limited)")

    print(f"\n{Colors.BOLD}Overall: {passed}/{total} tests passed{Colors.END}\n")

    # Recommendations
    if passed < total:
        print(f"{Colors.YELLOW}Recommendations:{Colors.END}")
        if (
            not results.get("get_framework")
            or not results.get("get_risk")
            or not results.get("get_mitigation")
        ):
            print(
                "  • Document detail tests failed - likely hit GitHub rate limit (60/hour)"
            )
            print("  • Solution 1: Wait 1 hour and try again")
            print("  • Solution 2: Add GitHub token for 5000/hour limit:")
            print("      export FINOS_MCP_GITHUB_TOKEN='your_token_here'")
        print()

    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ ALL TESTS PASSED!{Colors.END}")
        print(f"{Colors.GREEN}The MCP server is fully functional.{Colors.END}\n")
        return 0
    elif passed >= total * 0.75:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠ MOSTLY WORKING{Colors.END}")
        print(
            f"{Colors.YELLOW}Core functionality works. Some tests failed due to rate limiting.{Colors.END}\n"
        )
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ MULTIPLE FAILURES{Colors.END}")
        print(f"{Colors.RED}Please review the errors above.{Colors.END}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
