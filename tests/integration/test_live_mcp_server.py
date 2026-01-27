#!/usr/bin/env python3
"""
Live MCP Server Test
Comprehensive test that starts the actual MCP server and validates all functionality.
This is the final validation before Step 2.
"""

import asyncio
import json
import sys
from collections.abc import Callable
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class LiveServerTester:
    """Test the live MCP server with real MCP protocol"""

    def __init__(self) -> None:
        self.test_results: list[dict[str, Any]] = []

    def log_test(self, test_name: str, success: bool, details: str = "") -> None:
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"    {details}")

        self.test_results.append(
            {"test": test_name, "success": success, "details": details}
        )

        if not success:
            print(f"🚨 CRITICAL FAILURE: {test_name}")

    async def test_server_initialization(self, session: ClientSession) -> bool:
        """Test MCP server initialization"""
        try:
            result = await session.initialize()

            if hasattr(result, "server_name") and result.server_name:
                self.log_test(
                    "Server Initialization", True, f"Server: {result.server_name}"
                )
                return True
            else:
                self.log_test(
                    "Server Initialization", False, "No server name in response"
                )
                return False

        except Exception as e:
            self.log_test("Server Initialization", False, f"Exception: {e!s}")
            return False

    async def test_list_resources(self, session: ClientSession) -> bool:
        """Test resource listing functionality"""
        try:
            resources = await session.list_resources()

            # Server uses dynamic resource templates (finos://frameworks/{id}, etc.)
            # which are not enumerable via resources/list - empty list is valid
            if resources is None:
                self.log_test("List Resources", False, "Resources returned None")
                return False

            # If we have resources, verify their structure
            if resources:
                mitigation_resources = [
                    r for r in resources if "mitigations" in str(r.uri)
                ]
                risk_resources = [r for r in resources if "risks" in str(r.uri)]
                self.log_test(
                    "List Resources",
                    True,
                    f"Found {len(resources)} resources ({len(mitigation_resources)} mitigations, {len(risk_resources)} risks)",
                )
            else:
                # Empty list is valid for servers using dynamic resource templates
                self.log_test(
                    "List Resources",
                    True,
                    "Resources list empty (server uses dynamic resource templates)",
                )
            return True

        except Exception as e:
            self.log_test("List Resources", False, f"Exception: {e!s}")
            return False

    async def test_read_resource(self, session: ClientSession) -> bool:
        """Test reading a specific resource"""
        try:
            # Try to read the first mitigation
            test_uri = (
                "finos://mitigations/mi-1_ai-data-leakage-prevention-and-detection.md"
            )
            content = await session.read_resource(test_uri)

            if not content:
                self.log_test("Read Resource", False, "No content returned")
                return False

            if len(content) < 1000:
                self.log_test(
                    "Read Resource",
                    False,
                    f"Content too short: {len(content)} characters",
                )
                return False

            if not content.startswith("---"):
                self.log_test(
                    "Read Resource", False, "Content doesn't start with frontmatter"
                )
                return False

            self.log_test(
                "Read Resource", True, f"Successfully read {len(content)} characters"
            )
            return True

        except Exception as e:
            self.log_test("Read Resource", False, f"Exception: {e!s}")
            return False

    async def test_list_tools(self, session: ClientSession) -> bool:
        """Test tool listing functionality"""
        try:
            tools = await session.list_tools()

            if not tools:
                self.log_test("List Tools", False, "No tools returned")
                return False

            # Should have exactly 11 tools
            expected_tools = [
                "list_frameworks",
                "get_framework",
                "search_frameworks",
                "list_risks",
                "get_risk",
                "search_risks",
                "list_mitigations",
                "get_mitigation",
                "search_mitigations",
                "get_service_health",
                "get_cache_stats",
            ]

            tool_names = [tool.name for tool in tools]

            missing_tools = []
            for expected in expected_tools:
                if expected not in tool_names:
                    missing_tools.append(expected)

            if missing_tools:
                self.log_test("List Tools", False, f"Missing tools: {missing_tools}")
                return False

            if len(tools) != 11:
                self.log_test(
                    "List Tools", False, f"Expected 11 tools, got {len(tools)}"
                )
                return False

            self.log_test("List Tools", True, "Found all 11 expected tools")
            return True

        except Exception as e:
            self.log_test("List Tools", False, f"Exception: {e!s}")
            return False

    async def test_search_tool(self, session: ClientSession) -> bool:
        """Test search functionality"""
        try:
            # Test search_mitigations with "data" query
            result = await session.call_tool("search_mitigations", {"query": "data"})

            if not result or not result[0].text:
                self.log_test("Search Tool", False, "No search results returned")
                return False

            # Parse JSON response
            search_results = json.loads(result[0].text)

            if not isinstance(search_results, list):
                self.log_test("Search Tool", False, "Search results not a list")
                return False

            # Should find multiple results for "data"
            if len(search_results) < 5:
                self.log_test(
                    "Search Tool",
                    False,
                    f"Expected multiple results for 'data', got {len(search_results)}",
                )
                return False

            # Check result structure
            first_result = search_results[0]
            required_fields = ["id", "title", "filename"]

            missing_fields = []
            for field in required_fields:
                if field not in first_result:
                    missing_fields.append(field)

            if missing_fields:
                self.log_test(
                    "Search Tool", False, f"Missing fields in results: {missing_fields}"
                )
                return False

            self.log_test(
                "Search Tool",
                True,
                f"Search returned {len(search_results)} valid results",
            )
            return True

        except Exception as e:
            self.log_test("Search Tool", False, f"Exception: {e!s}")
            return False

    async def test_details_tool(self, session: ClientSession) -> bool:
        """Test get details functionality"""
        try:
            # Test get_mitigation with mi-1
            result = await session.call_tool(
                "get_mitigation", {"mitigation_id": "mi-1"}
            )

            if not result or not result[0].text:
                self.log_test("Details Tool", False, "No details returned")
                return False

            # Parse JSON response
            details = json.loads(result[0].text)

            if not isinstance(details, dict):
                self.log_test("Details Tool", False, "Details not a dictionary")
                return False

            # Check required fields
            required_fields = ["id", "title", "content", "metadata"]
            missing_fields = []

            for field in required_fields:
                if field not in details:
                    missing_fields.append(field)

            if missing_fields:
                self.log_test(
                    "Details Tool", False, f"Missing fields: {missing_fields}"
                )
                return False

            # Check content length
            if len(details["content"]) < 1000:
                self.log_test(
                    "Details Tool",
                    False,
                    f"Content too short: {len(details['content'])} characters",
                )
                return False

            self.log_test(
                "Details Tool",
                True,
                f"Retrieved details for {details['id']}: {details['title']}",
            )
            return True

        except Exception as e:
            self.log_test("Details Tool", False, f"Exception: {e!s}")
            return False

    async def test_list_tool(self, session: ClientSession) -> bool:
        """Test list all functionality"""
        try:
            # Test list_mitigations
            result = await session.call_tool("list_mitigations", {})

            if not result or not result[0].text:
                self.log_test("List Tool", False, "No list results returned")
                return False

            # Parse JSON response
            mitigations = json.loads(result[0].text)

            if not isinstance(mitigations, list):
                self.log_test("List Tool", False, "Mitigations not a list")
                return False

            # Should have 17 mitigations
            if len(mitigations) != 17:
                self.log_test(
                    "List Tool",
                    False,
                    f"Expected 17 mitigations, got {len(mitigations)}",
                )
                return False

            # Check structure of first mitigation
            first_mitigation = mitigations[0]
            required_fields = ["id", "title"]

            missing_fields = []
            for field in required_fields:
                if field not in first_mitigation:
                    missing_fields.append(field)

            if missing_fields:
                self.log_test(
                    "List Tool",
                    False,
                    f"Missing fields in list items: {missing_fields}",
                )
                return False

            self.log_test(
                "List Tool", True, f"Listed {len(mitigations)} mitigations successfully"
            )
            return True

        except Exception as e:
            self.log_test("List Tool", False, f"Exception: {e!s}")
            return False

    async def run_comprehensive_test(self) -> bool:
        """Run all MCP server tests"""
        print("🚀 Starting Comprehensive Live MCP Server Test")
        print("=" * 60)

        server_params = StdioServerParameters(
            command=sys.executable, args=["finos-ai-governance-mcp-server.py"]
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    tests: list[tuple[str, Callable[[ClientSession], Any]]] = [
                        ("Server Initialization", self.test_server_initialization),
                        ("List Resources", self.test_list_resources),
                        ("Read Resource", self.test_read_resource),
                        ("List Tools", self.test_list_tools),
                        ("Search Tool", self.test_search_tool),
                        ("Details Tool", self.test_details_tool),
                        ("List Tool", self.test_list_tool),
                    ]

                    print("🔄 Running MCP Protocol Tests...")

                    for test_name, test_func in tests:
                        print(f"\n🧪 {test_name}...")
                        success = await test_func(session)

                        if not success:
                            print(f"💥 Test failed: {test_name}")
                            break

                        # Small delay between tests
                        await asyncio.sleep(0.1)

        except Exception as e:
            self.log_test("Server Connection", False, f"Failed to connect: {e!s}")
            return False

        print("=" * 60)

        # Summary
        passed = [r for r in self.test_results if r["success"]]
        failed = [r for r in self.test_results if not r["success"]]

        print(f"📊 Test Results: {len(passed)}/{len(self.test_results)} passed")

        if failed:
            print("❌ FAILED TESTS:")
            for test in failed:
                print(f"  - {test['test']}: {test['details']}")
            print("\n🚨 MCP SERVER HAS ISSUES - CANNOT PROCEED")
            return False
        else:
            print("🎉 ALL MCP SERVER TESTS PASSED!")
            print("✅ Server is fully functional and ready for production")
            return True


async def main() -> None:
    """Main test runner"""
    tester = LiveServerTester()
    success = await tester.run_comprehensive_test()

    if success:
        print("\n✅ LIVE SERVER TEST COMPLETE - SERVER IS ROCK SOLID")
        sys.exit(0)
    else:
        print("\n❌ LIVE SERVER TEST FAILED - MUST FIX BEFORE STEP 2")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
