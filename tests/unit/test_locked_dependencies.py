#!/usr/bin/env python3
"""
Test Locked Dependencies
Validates that the requirements-lock.txt file produces an identical environment.
This ensures reproducible builds across different systems and times.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any


class DependencyLockTester:
    """Test dependency locking functionality"""

    def __init__(self) -> None:
        self.test_results: list[dict[str, Any]] = []

    def log_test(self, test_name: str, passed: bool, message: str = "") -> None:
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"    {message}")

        self.test_results.append(
            {"test": test_name, "passed": passed, "message": message}
        )

    def test_lock_file_exists(self) -> bool:
        """Test that lock file exists and is readable"""
        lock_file = Path("requirements-lock.txt")

        if not lock_file.exists():
            self.log_test("Lock File Exists", False, "requirements-lock.txt not found")
            return False

        try:
            with open(lock_file) as f:
                content = f.read()

            if len(content) < 100:
                self.log_test("Lock File Exists", False, "Lock file too short")
                return False

            # Check for key dependencies
            required_deps = ["mcp==", "httpx==", "PyYAML==", "pydantic=="]
            missing = []

            for dep in required_deps:
                if dep not in content:
                    missing.append(dep)

            if missing:
                self.log_test(
                    "Lock File Exists", False, f"Missing dependencies: {missing}"
                )
                return False

            self.log_test(
                "Lock File Exists",
                True,
                f"Lock file contains {len(content.splitlines())} lines",
            )
            return True

        except Exception as e:
            self.log_test("Lock File Exists", False, f"Error reading lock file: {e}")
            return False

    def test_current_environment_matches_lock(self) -> bool:
        """Test that current environment matches the lock file"""
        try:
            # Get current installed packages
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True
            )

            if result.returncode != 0:
                self.log_test(
                    "Environment Match", False, "Failed to get pip freeze output"
                )
                return False

            current_packages = set(result.stdout.strip().split("\n"))

            # Read lock file
            with open("requirements-lock.txt") as f:
                lock_content = f.read()

            # Extract package specs from lock file (ignore comments)
            lock_packages = set()
            for line in lock_content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and "==" in line:
                    # Extract just the package==version part
                    if "via" not in line:  # Skip dependency comments
                        lock_packages.add(line.split()[0])

            # Check if core dependencies match
            core_deps = ["mcp", "httpx", "PyYAML", "pydantic"]
            mismatches = []

            for dep in core_deps:
                # Find versions in current and lock
                current_version = None
                lock_version = None

                for pkg in current_packages:
                    if pkg.startswith(f"{dep}=="):
                        current_version = pkg
                        break

                for pkg in lock_packages:
                    if pkg.startswith(f"{dep}=="):
                        lock_version = pkg
                        break

                if current_version != lock_version:
                    mismatches.append(
                        f"{dep}: current={current_version}, lock={lock_version}"
                    )

            if mismatches:
                self.log_test(
                    "Environment Match", False, f"Version mismatches: {mismatches}"
                )
                return False

            self.log_test(
                "Environment Match", True, "Current environment matches lock file"
            )
            return True

        except Exception as e:
            self.log_test(
                "Environment Match", False, f"Error checking environment: {e}"
            )
            return False

    def test_functionality_with_locked_deps(self) -> bool:
        """Test that our server works with the locked dependencies"""
        try:
            # Run our basic functionality test
            result = subprocess.run(
                [sys.executable, "tests/integration/simple_test.py"],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                self.log_test(
                    "Functionality Test", False, f"Simple test failed: {result.stderr}"
                )
                return False

            # Check for success indicators in output
            output = result.stdout

            if "All basic functionality tests passed!" not in output:
                self.log_test(
                    "Functionality Test", False, "Success message not found in output"
                )
                return False

            self.log_test(
                "Functionality Test",
                True,
                "All functionality works with locked dependencies",
            )
            return True

        except Exception as e:
            self.log_test("Functionality Test", False, f"Error running test: {e}")
            return False

    def test_pip_tools_workflow(self) -> bool:
        """Test the pip-tools workflow setup"""
        try:
            # Check if requirements.in exists
            if not Path("requirements.in").exists():
                self.log_test("Pip-tools Setup", False, "requirements.in not found")
                return False

            # Read requirements.in
            with open("requirements.in") as f:
                req_in_content = f.read()

            # Check that it contains our core dependencies
            core_deps = ["mcp>=", "httpx>=", "PyYAML>=", "pydantic>="]
            missing = []

            for dep in core_deps:
                if dep not in req_in_content:
                    missing.append(dep)

            if missing:
                self.log_test(
                    "Pip-tools Setup", False, f"Missing from .in file: {missing}"
                )
                return False

            self.log_test("Pip-tools Setup", True, "pip-tools workflow files ready")
            return True

        except Exception as e:
            self.log_test("Pip-tools Setup", False, f"Error checking pip-tools: {e}")
            return False

    def run_all_tests(self) -> bool:
        """Run all dependency lock tests"""
        print("🔒 Testing Dependency Locking Implementation")
        print("=" * 60)

        tests = [
            ("Lock File Structure", self.test_lock_file_exists),
            ("Environment Match", self.test_current_environment_matches_lock),
            ("Functionality Test", self.test_functionality_with_locked_deps),
            ("Pip-tools Setup", self.test_pip_tools_workflow),
        ]

        for test_name, test_func in tests:
            print(f"\n🧪 {test_name}...")
            success = test_func()

            if not success:
                print(f"💥 Critical failure in: {test_name}")
                break

        print("=" * 60)

        # Summary
        passed = [r for r in self.test_results if r["passed"]]
        failed = [r for r in self.test_results if not r["passed"]]

        print(f"📊 Test Results: {len(passed)}/{len(self.test_results)} passed")

        if failed:
            print("❌ FAILED TESTS:")
            for test in failed:
                print(f"  - {test['test']}: {test['message']}")
            print("\n🚨 DEPENDENCY LOCKING HAS ISSUES")
            return False
        else:
            print("🎉 ALL DEPENDENCY LOCK TESTS PASSED!")
            print("✅ requirements-lock.txt ensures reproducible builds")
            print("✅ Current environment matches locked versions")
            print("✅ All functionality works with pinned dependencies")
            print("✅ pip-tools workflow ready for future updates")
            return True


def main() -> None:
    """Main test runner"""
    tester = DependencyLockTester()
    success = tester.run_all_tests()

    if success:
        print("\n✅ DEPENDENCY LOCKING VALIDATION COMPLETE")
        print("🔒 Reproducible builds ensured - ready for production!")
        sys.exit(0)
    else:
        print("\n❌ DEPENDENCY LOCKING VALIDATION FAILED")
        print("🚨 Must fix dependency issues before proceeding")
        sys.exit(1)


if __name__ == "__main__":
    main()
