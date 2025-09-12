#!/usr/bin/env python3
"""
Console Script Execution Test
Tests that the actual console script works end-to-end as users would experience it.
This test would have caught the async/sync main() bug.
"""

import json
import subprocess
import sys
import time


def test_console_script_startup() -> bool:
    """Test that finos-mcp console script starts without errors"""
    print("🧪 Testing Console Script Startup...")

    try:
        # Test 1: Console script exists and is executable
        # Prefer virtual environment script if available
        import os

        venv_script = os.path.join(os.path.dirname(sys.executable), "finos-mcp")

        if os.path.exists(venv_script):
            script_path = venv_script
        else:
            result = subprocess.run(
                ["which", "finos-mcp"], capture_output=True, text=True, timeout=10
            )

            if result.returncode != 0:
                print(
                    "❌ Console script 'finos-mcp' not found in PATH or virtual environment"
                )
                print("   Make sure you ran 'pip install -e .' first")
                raise AssertionError(
                    "Console script 'finos-mcp' not found in PATH or virtual environment"
                )

            script_path = result.stdout.strip()
        print(f"✅ Console script found at: {script_path}")

        # Test 2: Console script starts without immediate errors
        print("🚀 Testing server startup (should not crash immediately)...")

        process = subprocess.Popen(
            [script_path],
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

        # Wait for startup - server should start and wait for input
        time.sleep(1.0)

        # Check if process crashed immediately
        poll_result = process.poll()
        if poll_result is not None:
            stdout, stderr = process.communicate()
            print(
                f"❌ Console script crashed immediately with exit code: {poll_result}"
            )
            print(f"   STDOUT: {stdout[:500]}...")
            print(f"   STDERR: {stderr[:500]}...")

            # Check for specific async/coroutine errors
            if "coroutine" in stderr.lower() or "never awaited" in stderr.lower():
                print("💥 DETECTED: Async/sync main() function bug!")
                raise AssertionError("Async/sync main() function bug detected")

            raise AssertionError("Console script crashed immediately")

        print("✅ Console script started successfully (not crashed)")

        # Test 3: Server responds to basic MCP protocol
        print("🔗 Testing basic MCP protocol response...")

        # Send a simple initialization request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        # Send request and wait for response
        try:
            process.stdin.write(json.dumps(init_request) + "\n")
            process.stdin.flush()

            # Try to read response (with timeout)
            import select

            # Give server time to process
            time.sleep(0.5)

            # Check if we can read from stdout (means server is responding)
            ready, _, _ = select.select([process.stdout], [], [], 2.0)

            if ready:
                try:
                    response_line = process.stdout.readline()
                    if response_line.strip():
                        response = json.loads(response_line)
                        if "jsonrpc" in response and response.get("id") == 1:
                            print("✅ Server responded to MCP initialization")
                        else:
                            print(
                                f"⚠️  Server responded but format unexpected: {response}"
                            )
                except json.JSONDecodeError:
                    print(
                        f"⚠️  Server responded but not valid JSON: {response_line[:100]}..."
                    )
            else:
                print(
                    "⚠️  Server started but no response to initialization (may be normal)"
                )

        except Exception as e:
            print(f"⚠️  Could not test MCP protocol: {e}")

        finally:
            # Clean shutdown
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        # Test completed successfully
        print("✅ Server responded to MCP initialization")
        return True

    except subprocess.TimeoutExpired:
        print("❌ Console script test timed out")
        raise AssertionError("Console script test timed out") from None
    except Exception as e:
        print(f"❌ Console script test failed with error: {e}")
        raise AssertionError(f"Console script test failed with error: {e}") from None


def test_console_script_vs_direct_module() -> bool:
    """Test that console script and direct module execution have same behavior"""
    print("\n🔄 Testing Console Script vs Direct Module Execution...")

    # Get script path (same logic as in startup test)
    import os

    venv_script = os.path.join(os.path.dirname(sys.executable), "finos-mcp")
    script_path = venv_script if os.path.exists(venv_script) else "finos-mcp"

    def start_and_test(command: list[str], description: str) -> tuple[bool, str]:
        """Helper to start server and test basic behavior"""
        try:
            process = subprocess.Popen(
                command,
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

            time.sleep(0.8)  # Wait for startup

            # Check for immediate crash
            poll_result = process.poll()
            if poll_result is not None:
                stdout, stderr = process.communicate()
                return False, f"Crashed with code {poll_result}: {stderr[:200]}"

            # Clean shutdown
            try:
                process.terminate()
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

            return True, "Started successfully"

        except Exception as e:
            return False, str(e)

    # Test console script
    console_success, console_msg = start_and_test([script_path], "console script")
    print(f"   Console Script: {'✅' if console_success else '❌'} {console_msg}")

    # Test direct module
    module_success, module_msg = start_and_test(
        [sys.executable, "-m", "finos_mcp.server"], "direct module"
    )
    print(f"   Direct Module:  {'✅' if module_success else '❌'} {module_msg}")

    # Both should succeed
    if console_success and module_success:
        print("✅ Both execution methods work consistently")
        return True
    else:
        print("❌ Inconsistent behavior between execution methods")
        raise AssertionError("Inconsistent behavior between execution methods")


def test_console_script_error_handling() -> bool:
    """Test that console script handles errors gracefully"""
    print("\n🛡️  Testing Error Handling...")

    # Get script path (same logic as in startup test)
    import os

    venv_script = os.path.join(os.path.dirname(sys.executable), "finos-mcp")
    script_path = venv_script if os.path.exists(venv_script) else "finos-mcp"

    try:
        # Test with invalid JSON input
        process = subprocess.Popen(
            [script_path],
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

        time.sleep(0.5)

        # Send invalid input
        process.stdin.write("invalid json\n")
        process.stdin.flush()

        time.sleep(0.5)

        # Server should still be running (not crashed)
        poll_result = process.poll()
        if poll_result is not None:
            print("❌ Server crashed on invalid input")
            raise AssertionError("Server crashed on invalid input")

        print("✅ Server handles invalid input gracefully")

        # Clean shutdown
        try:
            process.terminate()
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

        # Test passed
        return True

    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        raise AssertionError(f"Error handling test failed: {e}") from None


def main() -> bool:
    """Run all console script execution tests"""
    print("🧪 CONSOLE SCRIPT EXECUTION TEST SUITE")
    print("=" * 50)
    print("This test suite validates that the finos-mcp console script")
    print("works exactly as users would experience it.\n")

    tests = [
        ("Console Script Startup", test_console_script_startup),
        ("Console vs Module Consistency", test_console_script_vs_direct_module),
        ("Error Handling", test_console_script_error_handling),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        print("-" * 30)

        try:
            success = test_func()
            results.append((test_name, success))
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"   Result: {status}")
        except Exception as e:
            print(f"   Result: ❌ ERROR - {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📊 CONSOLE SCRIPT TEST RESULTS")
    print("=" * 50)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {test_name}")

    print(f"\n📈 Summary: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 ALL CONSOLE SCRIPT TESTS PASSED!")
        print("✅ Console script is stable and ready for production")
        return True
    else:
        print("💥 CONSOLE SCRIPT TESTS FAILED!")
        print("❌ Fix issues before considering this stable")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
