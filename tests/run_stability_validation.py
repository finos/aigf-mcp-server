#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stability Validation Master Script

This script runs all critical tests to ensure system stability before
advancing to the next development step. This addresses the requirement
that any future modification must be tested before considering it stable.

Run this before every step transition to ensure no regressions.
"""

import subprocess
import sys
import time
from pathlib import Path
import os

# Ensure UTF-8 encoding for Windows compatibility
if os.name == 'nt':  # Windows
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def run_test_script(script_path: Path | str, description: str) -> bool:
    """Run a test script and return success status"""
    print(f"\n🧪 Running: {description}")
    print("=" * 60)

    try:
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=False,  # Show output in real time
            text=True,
            timeout=120,  # 2 minute timeout per test
        )

        duration = time.time() - start_time
        success = result.returncode == 0

        status = "✅ PASS" if success else "❌ FAIL"
        print(f"\n{status} {description} (took {duration:.1f}s)")

        return success

    except subprocess.TimeoutExpired:
        print(f"❌ TIMEOUT {description} (exceeded 2 minutes)")
        return False
    except Exception as e:
        print(f"❌ ERROR {description}: {e}")
        return False


def main() -> bool:
    """Run comprehensive stability validation"""
    print("🛡️  FINOS MCP SERVER - STABILITY VALIDATION SUITE")
    print("=" * 70)
    print("Ensuring system stability before advancing to next development step")
    print("This prevents regressions and ensures production readiness")
    print()

    # Define all critical tests that must pass
    tests = [
        # Core functionality tests
        (
            "tests/integration/test_baseline_validation.py",
            "Baseline Functionality Validation",
        ),
        ("tests/integration/test_mcp_compliance.py", "MCP Protocol Compliance"),
        # Console script and user experience tests
        (
            "tests/integration/test_console_script_execution.py",
            "Console Script Execution",
        ),
        ("tests/integration/test_server_working.py", "Server Working Verification"),
        # Package structure tests
        ("tests/unit/test_package_skeleton.py", "Package Structure Validation"),
        # Additional stability tests
        ("tests/unit/test_locked_dependencies.py", "Dependency Lock Validation"),
    ]

    print(f"🎯 Running {len(tests)} critical stability tests...\n")

    results = []
    failed_tests = []

    for script_path, description in tests:
        script_file = Path(script_path)

        if not script_file.exists():
            print(f"⚠️  SKIP {description} - Test file not found: {script_path}")
            results.append((description, False, "File not found"))
            failed_tests.append(description)
            continue

        success = run_test_script(script_file, description)
        results.append((description, success, "Passed" if success else "Failed"))

        if not success:
            failed_tests.append(description)

    # Summary Report
    print("\n" + "=" * 70)
    print("📊 STABILITY VALIDATION RESULTS")
    print("=" * 70)

    passed = len([r for r in results if r[1]])
    total = len(results)

    for description, success, status in results:
        icon = "✅" if success else "❌"
        print(f"  {icon} {description:<45} {status}")

    print("-" * 70)
    print(f"📈 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL STABILITY TESTS PASSED!")
        print("✅ System is STABLE and ready for next development step")
        print("✅ No regressions detected")
        print("✅ Production readiness confirmed")
        return True
    else:
        print("\n💥 STABILITY VALIDATION FAILED!")
        print(f"❌ {len(failed_tests)} test(s) failed:")
        for test in failed_tests:
            print(f"   - {test}")
        print("\n🛑 DO NOT ADVANCE TO NEXT STEP")
        print("🔧 Fix all failing tests before continuing")
        print("📋 Stability is a MUST and PRIORITY")
        return False


def quick_smoke_test() -> bool:
    """Quick smoke test for rapid validation during development"""
    print("💨 QUICK SMOKE TEST")
    print("=" * 30)

    # Just test the most critical path: console script execution
    success = run_test_script(
        Path("tests/integration/test_console_script_execution.py"),
        "Console Script Smoke Test",
    )

    if success:
        print("\n✅ Quick smoke test PASSED - basic functionality working")
    else:
        print("\n❌ Quick smoke test FAILED - immediate attention needed")

    return success


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--smoke":
        success = quick_smoke_test()
    else:
        success = main()

    sys.exit(0 if success else 1)
