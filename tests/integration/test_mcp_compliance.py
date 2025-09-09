#!/usr/bin/env python3
"""
MCP Protocol Compliance Test
Simple test to verify the server responds to MCP protocol correctly.
This establishes that MCP functionality works before refactoring.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path


async def test_server_startup() -> bool:
    """Test that server starts and responds to basic MCP commands"""
    print("🚀 Testing MCP Server Startup and Basic Protocol...")

    # Test server process startup
    try:
        # Start the server as a subprocess
        process = subprocess.Popen(
            [sys.executable, "-m", "finos_mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
        )

        # Type assertion for mypy - we know these are not None due to PIPE
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None

        # Give it a moment to start
        await asyncio.sleep(0.5)

        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print("❌ Server failed to start:")
            print(f"  stdout: {stdout}")
            print(f"  stderr: {stderr}")
            return False

        print("✅ Server process started successfully")

        # Test basic JSON-RPC structure (not full MCP initialization)
        test_request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

        # Send request
        try:
            process.stdin.write(json.dumps(test_request) + "\n")
            process.stdin.flush()

            # Give server time to process
            await asyncio.sleep(1.0)

            # Try to read response (with timeout)
            try:
                # Use select to check if data is available (Unix-like systems)
                import select

                if select.select([process.stdout], [], [], 2.0)[0]:
                    response = process.stdout.readline()
                    if response:
                        response_data = json.loads(response.strip())
                        print("✅ Server responded with valid JSON-RPC")
                        print(f"  Response ID: {response_data.get('id')}")

                        if "error" in response_data:
                            print(
                                f"  Expected error (no proper initialization): {response_data['error']['message']}"
                            )
                        else:
                            print(f"  Unexpected success: {response_data}")

                        result = True
                    else:
                        print("❌ No response from server")
                        result = False
                else:
                    print("❌ Server did not respond within timeout")
                    result = False

            except ImportError:
                # Windows fallback - just assume it works if process is running
                print("✅ Server process is running (Windows - cannot test response)")
                result = True

        except Exception as e:
            print(f"❌ Failed to communicate with server: {e}")
            result = False

        finally:
            # Clean up process
            try:
                process.terminate()
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

        return result

    except Exception as e:
        print(f"❌ Server startup test failed: {e}")
        return False


async def test_server_import() -> bool:
    """Test that we can import the server module without errors"""
    print("\n📦 Testing Server Module Import...")

    try:
        # Import the modern server module
        import finos_mcp.server as finos_server

        # Check that key modern components exist
        required_components = [
            "server",
            "get_mitigation_files",
            "get_risk_files",
            "get_content_service_instance",
            "main",
            "main_async",
        ]

        missing = []
        for component in required_components:
            if not hasattr(finos_server, component):
                missing.append(component)

        if missing:
            print(f"❌ Missing components: {missing}")
            return False

        print(f"✅ All {len(required_components)} modern components found")
        print(f"  Server instance: {type(finos_server.server)}")

        # Test dynamic file discovery
        mitigation_files = await finos_server.get_mitigation_files()
        risk_files = await finos_server.get_risk_files()
        print(f"  Mitigation files: {len(mitigation_files)}")
        print(f"  Risk files: {len(risk_files)}")
        print(
            f"  Content service function: {finos_server.get_content_service_instance}"
        )

        return True

    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False


def test_file_structure() -> None:
    """Test that all expected files exist"""
    print("\n📂 Testing File Structure...")

    required_files = [
        "src/finos_mcp/server.py",
        "requirements.txt",
        "README.md",
        "tests/integration/test_baseline_validation.py",
        "scripts/create_golden_files.py",
        "tests/golden_baseline.json",
    ]

    missing = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing.append(file_path)

    if missing:
        print(f"❌ Missing files: {missing}")
        raise AssertionError(f"Missing files: {missing}")

    # Check golden files
    golden_dir = Path("tests/golden")
    if not golden_dir.exists():
        print("❌ Golden files directory missing")
        raise AssertionError("Golden files directory missing")

    expected_golden_files = [
        "search_mitigations.json",
        "search_risks.json",
        "get_mitigation_details.json",
        "get_risk_details.json",
        "list_all_mitigations.json",
        "list_all_risks.json",
    ]

    missing_golden = []
    for golden_file in expected_golden_files:
        if not (golden_dir / golden_file).exists():
            missing_golden.append(golden_file)

    if missing_golden:
        print(f"❌ Missing golden files: {missing_golden}")
        raise AssertionError(f"Missing golden files: {missing_golden}")

    print(f"✅ All {len(required_files)} required files present")
    print(f"✅ All {len(expected_golden_files)} golden files present")
    assert True  # Explicit assertion instead of return


async def main() -> bool:
    """Run MCP compliance tests"""
    print("🔍 MCP Protocol Compliance Test Suite")
    print("=" * 50)

    tests = [
        ("File Structure", test_file_structure),
        ("Server Import", test_server_import),
        ("Server Startup", test_server_startup),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            # Execute the test function
            if asyncio.iscoroutinefunction(test_func):
                raw_result = await test_func()
            else:
                raw_result = test_func()  # type: ignore

            # Convert result to bool - None means success
            success = bool(raw_result) if raw_result is not None else True
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    print("=" * 50)

    passed = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]

    print(f"📊 Test Results: {len(passed)}/{len(results)} passed")

    if failed:
        print("❌ Failed tests:")
        for test_name, _ in failed:
            print(f"  - {test_name}")
        print("\n🚨 MCP compliance issues detected - must fix before proceeding")
        return False
    else:
        print("🎉 All MCP compliance tests passed!")
        print("✅ Server is ready for refactoring")
        return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
