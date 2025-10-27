#!/usr/bin/env python3
"""Local MCP Server Testing Script

This script tests the FINOS MCP server locally by simulating MCP protocol
communication similar to how Claude Desktop would interact with it.

Usage:
    python tests/local_mcp_test.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finos_mcp.fastmcp_server import (
    list_frameworks,
    get_framework,
    search_frameworks,
    list_risks,
    get_risk,
    search_risks,
    list_mitigations,
    get_mitigation,
    search_mitigations,
    get_service_health,
    get_cache_stats,
)


class Colors:
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    """Print a colored header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓{Colors.ENDC} {text}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ{Colors.ENDC} {text}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}✗{Colors.ENDC} {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠{Colors.ENDC} {text}")


async def test_list_frameworks():
    """Test 1: list_frameworks tool."""
    print_header("TEST 1: list_frameworks()")

    try:
        result = await list_frameworks()

        print_info(f"Total frameworks: {result.total_count}")
        print_info(f"Frameworks found: {len(result.frameworks)}")

        for fw in result.frameworks:
            print(f"  • {fw.id}: {fw.name}")

        if result.total_count > 0:
            print_success("list_frameworks() working correctly")
            return True, result
        else:
            print_error("No frameworks found")
            return False, None

    except Exception as e:
        print_error(f"list_frameworks() failed: {e}")
        return False, None


async def test_get_framework(framework_id: str):
    """Test 2: get_framework tool."""
    print_header(f"TEST 2: get_framework('{framework_id}')")

    try:
        result = await get_framework(framework_id)

        print_info(f"Framework ID: {result.framework_id}")
        print_info(f"Sections: {result.sections}")
        print_info(f"Content length: {len(result.content)} characters")

        if len(result.content) > 200:
            preview = result.content[:200].replace("\n", " ")
            print_info(f"Preview: {preview}...")
            print_success(f"get_framework('{framework_id}') working correctly")
            return True, result
        else:
            print_warning(f"Content seems short: {result.content}")
            return False, None

    except Exception as e:
        print_error(f"get_framework('{framework_id}') failed: {e}")
        return False, None


async def test_search_frameworks(query: str):
    """Test 3: search_frameworks tool."""
    print_header(f"TEST 3: search_frameworks('{query}')")

    try:
        result = await search_frameworks(query, limit=5)

        print_info(f"Query: {result.query}")
        print_info(f"Total results: {result.total_found}")

        for i, res in enumerate(result.results[:3], 1):
            print(f"\n  Result {i}:")
            print(f"    Framework: {res.framework_id}")
            print(f"    Section: {res.section}")
            snippet = res.content[:100].replace("\n", " ")
            print(f"    Content: {snippet}...")

        if result.total_found > 0:
            print_success(f"search_frameworks('{query}') working correctly")
            return True, result
        else:
            print_warning("No search results found")
            return False, None

    except Exception as e:
        print_error(f"search_frameworks('{query}') failed: {e}")
        return False, None


async def test_list_risks():
    """Test 4: list_risks tool."""
    print_header("TEST 4: list_risks()")

    try:
        result = await list_risks()

        print_info(f"Total risks: {result.total_count}")
        print_info(f"Source: {result.source}")
        print_info(f"Risks found: {len(result.documents)}")

        for risk in result.documents[:5]:
            print(f"  • {risk.id}: {risk.name}")

        if result.total_count > 0:
            print_success("list_risks() working correctly")
            return True, result
        else:
            print_error("No risks found")
            return False, None

    except Exception as e:
        print_error(f"list_risks() failed: {e}")
        return False, None


async def test_get_risk(risk_id: str):
    """Test 5: get_risk tool."""
    print_header(f"TEST 5: get_risk('{risk_id}')")

    try:
        result = await get_risk(risk_id)

        print_info(f"Risk ID: {result.document_id}")
        print_info(f"Title: {result.title}")
        print_info(f"Sections: {len(result.sections)}")
        print_info(f"Content length: {len(result.content)} characters")

        if len(result.content) > 200:
            preview = result.content[:200].replace("\n", " ")
            print_info(f"Preview: {preview}...")
            print_success(f"get_risk('{risk_id}') working correctly")
            return True, result
        else:
            print_warning(f"Content seems short: {result.content}")
            return False, None

    except Exception as e:
        print_error(f"get_risk('{risk_id}') failed: {e}")
        return False, None


async def test_search_risks(query: str):
    """Test 6: search_risks tool."""
    print_header(f"TEST 6: search_risks('{query}')")

    try:
        result = await search_risks(query, limit=5)

        print_info(f"Query: {result.query}")
        print_info(f"Total results: {result.total_found}")

        for i, res in enumerate(result.results[:3], 1):
            print(f"\n  Result {i}:")
            # SearchResult uses framework_id not document_id
            print(f"    Framework: {res.framework_id}")
            print(f"    Section: {res.section}")
            snippet = res.content[:100].replace("\n", " ")
            print(f"    Content: {snippet}...")

        if result.total_found > 0:
            print_success(f"search_risks('{query}') working correctly")
            return True, result
        else:
            print_warning("No search results found")
            return False, None

    except Exception as e:
        print_error(f"search_risks('{query}') failed: {e}")
        return False, None


async def test_list_mitigations():
    """Test 7: list_mitigations tool."""
    print_header("TEST 7: list_mitigations()")

    try:
        result = await list_mitigations()

        print_info(f"Total mitigations: {result.total_count}")
        print_info(f"Source: {result.source}")
        print_info(f"Mitigations found: {len(result.documents)}")

        for mit in result.documents[:5]:
            print(f"  • {mit.id}: {mit.name}")

        if result.total_count > 0:
            print_success("list_mitigations() working correctly")
            return True, result
        else:
            print_error("No mitigations found")
            return False, None

    except Exception as e:
        print_error(f"list_mitigations() failed: {e}")
        return False, None


async def test_get_mitigation(mitigation_id: str):
    """Test 8: get_mitigation tool."""
    print_header(f"TEST 8: get_mitigation('{mitigation_id}')")

    try:
        result = await get_mitigation(mitigation_id)

        print_info(f"Mitigation ID: {result.document_id}")
        print_info(f"Title: {result.title}")
        print_info(f"Sections: {len(result.sections)}")
        print_info(f"Content length: {len(result.content)} characters")

        if len(result.content) > 200:
            preview = result.content[:200].replace("\n", " ")
            print_info(f"Preview: {preview}...")
            print_success(f"get_mitigation('{mitigation_id}') working correctly")
            return True, result
        else:
            print_warning(f"Content seems short: {result.content}")
            return False, None

    except Exception as e:
        print_error(f"get_mitigation('{mitigation_id}') failed: {e}")
        return False, None


async def test_search_mitigations(query: str):
    """Test 9: search_mitigations tool."""
    print_header(f"TEST 9: search_mitigations('{query}')")

    try:
        result = await search_mitigations(query, limit=5)

        print_info(f"Query: {result.query}")
        print_info(f"Total results: {result.total_found}")

        for i, res in enumerate(result.results[:3], 1):
            print(f"\n  Result {i}:")
            # SearchResult uses framework_id not document_id
            print(f"    Framework: {res.framework_id}")
            print(f"    Section: {res.section}")
            snippet = res.content[:100].replace("\n", " ")
            print(f"    Content: {snippet}...")

        if result.total_found > 0:
            print_success(f"search_mitigations('{query}') working correctly")
            return True, result
        else:
            print_warning("No search results found")
            return False, None

    except Exception as e:
        print_error(f"search_mitigations('{query}') failed: {e}")
        return False, None


async def test_service_health():
    """Test 10: get_service_health tool."""
    print_header("TEST 10: get_service_health()")

    try:
        result = await get_service_health()

        print_info(f"Status: {result.status}")
        print_info(f"Version: {result.version}")
        print_info(f"Uptime: {result.uptime_seconds:.2f} seconds")
        print_info(f"Healthy services: {result.healthy_services}/{result.total_services}")

        print_success("get_service_health() working correctly")
        return True, result

    except Exception as e:
        print_error(f"get_service_health() failed: {e}")
        return False, None


async def test_cache_stats():
    """Test 11: get_cache_stats tool."""
    print_header("TEST 11: get_cache_stats()")

    try:
        result = await get_cache_stats()

        print_info(f"Total requests: {result.total_requests}")
        print_info(f"Cache hits: {result.cache_hits}")
        print_info(f"Cache misses: {result.cache_misses}")
        print_info(f"Hit rate: {result.hit_rate:.2%}")

        print_success("get_cache_stats() working correctly")
        return True, result

    except Exception as e:
        print_error(f"get_cache_stats() failed: {e}")
        return False, None


async def run_all_tests():
    """Run all MCP server tests."""
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{'FINOS AI Governance MCP Server - Local Testing':^80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.ENDC}")

    results = {}

    # Test 1: List frameworks
    success, frameworks_data = await test_list_frameworks()
    results["list_frameworks"] = success

    # Test 2: Get framework (use first framework from list)
    if success and frameworks_data and frameworks_data.frameworks:
        framework_id = frameworks_data.frameworks[0].id
        success, _ = await test_get_framework(framework_id)
        results["get_framework"] = success
    else:
        results["get_framework"] = False

    # Test 3: Search frameworks
    success, _ = await test_search_frameworks("risk")
    results["search_frameworks"] = success

    # Test 4: List risks
    success, risks_data = await test_list_risks()
    results["list_risks"] = success

    # Test 5: Get risk (use first risk from list)
    if success and risks_data and risks_data.documents:
        risk_id = risks_data.documents[0].id
        success, _ = await test_get_risk(risk_id)
        results["get_risk"] = success
    else:
        results["get_risk"] = False

    # Test 6: Search risks
    success, _ = await test_search_risks("injection")
    results["search_risks"] = success

    # Test 7: List mitigations
    success, mitigations_data = await test_list_mitigations()
    results["list_mitigations"] = success

    # Test 8: Get mitigation (use first mitigation from list)
    if success and mitigations_data and mitigations_data.documents:
        mitigation_id = mitigations_data.documents[0].id
        success, _ = await test_get_mitigation(mitigation_id)
        results["get_mitigation"] = success
    else:
        results["get_mitigation"] = False

    # Test 9: Search mitigations
    success, _ = await test_search_mitigations("data")
    results["search_mitigations"] = success

    # Test 10: Service health
    success, _ = await test_service_health()
    results["get_service_health"] = success

    # Test 11: Cache stats
    success, _ = await test_cache_stats()
    results["get_cache_stats"] = success

    # Print summary
    print_header("TEST SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, success in results.items():
        if success:
            print_success(f"{test_name:30} PASSED")
        else:
            print_error(f"{test_name:30} FAILED")

    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.ENDC}")

    if passed == total:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ ALL TESTS PASSED!{Colors.ENDC}")
        print(f"{Colors.OKGREEN}The MCP server is working correctly.{Colors.ENDC}\n")
        return 0
    else:
        print(f"\n{Colors.FAIL}{Colors.BOLD}✗ SOME TESTS FAILED{Colors.ENDC}")
        print(f"{Colors.FAIL}Please review the errors above.{Colors.ENDC}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
