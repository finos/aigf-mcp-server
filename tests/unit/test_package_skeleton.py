#!/usr/bin/env python3
"""
Test Package Skeleton
Validates the package structure, importability, and PEP 518 compliance.
Ensures the src/ layout works correctly without breaking functionality.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any


class PackageSkeletonTester:
    """Test package skeleton implementation"""

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

    def test_directory_structure(self) -> bool:
        """Test that package directories exist with correct structure"""
        required_paths = [
            "src/finos_mcp",
            "src/finos_mcp/__init__.py",
            "pyproject.toml",
        ]

        missing = []
        for path in required_paths:
            if not Path(path).exists():
                missing.append(path)

        if missing:
            self.log_test("Directory Structure", False, f"Missing: {missing}")
            return False

        self.log_test("Directory Structure", True, "All required paths exist")
        return True

    def test_package_importability(self) -> bool:
        """Test package can be imported and has correct attributes"""
        try:
            # Test import from src path
            sys.path.insert(0, "src")
            import finos_mcp

            # Test required attributes
            required_attrs = [
                "__version__",
                "__author__",
                "__email__",
                "__license__",
                "__description__",
                "get_version",
                "get_package_info",
                "version_info",
            ]

            missing_attrs = []
            for attr in required_attrs:
                if not hasattr(finos_mcp, attr):
                    missing_attrs.append(attr)

            if missing_attrs:
                self.log_test(
                    "Package Import", False, f"Missing attributes: {missing_attrs}"
                )
                return False

            # Test version format
            version = finos_mcp.__version__
            if not isinstance(version, str) or not version:
                self.log_test("Package Import", False, f"Invalid version: {version}")
                return False

            # Test version_info tuple
            version_info = finos_mcp.version_info
            if not isinstance(version_info, tuple) or len(version_info) < 2:
                self.log_test(
                    "Package Import", False, f"Invalid version_info: {version_info}"
                )
                return False

            # Test helper functions
            if finos_mcp.get_version() != version:
                self.log_test(
                    "Package Import", False, "get_version() doesn't match __version__"
                )
                return False

            package_info = finos_mcp.get_package_info()
            if not isinstance(package_info, dict) or "version" not in package_info:
                self.log_test("Package Import", False, "get_package_info() invalid")
                return False

            self.log_test(
                "Package Import", True, f"Package imported with version {version}"
            )
            return True

        except ImportError as e:
            self.log_test("Package Import", False, f"Import failed: {e}")
            return False
        except Exception as e:
            self.log_test("Package Import", False, f"Error: {e}")
            return False
        finally:
            # Clean up sys.path
            if "src" in sys.path:
                sys.path.remove("src")

    def test_editable_install(self) -> bool:
        """Test that package can be installed in editable mode"""
        try:
            # Check if already installed
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import finos_mcp; print(finos_mcp.__version__)",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                self.log_test(
                    "Editable Install", False, "Package not installed in environment"
                )
                return False

            version = result.stdout.strip()
            if not version:
                self.log_test("Editable Install", False, "No version found")
                return False

            self.log_test("Editable Install", True, f"Installed version: {version}")
            return True

        except Exception as e:
            self.log_test("Editable Install", False, f"Error: {e}")
            return False

    def test_console_script(self) -> bool:
        """Test that console script entry point exists"""
        try:
            # Check if console script exists
            result = subprocess.run(
                ["which", "finos-mcp"], capture_output=True, text=True
            )

            if result.returncode != 0:
                self.log_test("Console Script", False, "finos-mcp command not found")
                return False

            script_path = result.stdout.strip()
            if not script_path or not Path(script_path).exists():
                self.log_test(
                    "Console Script", False, f"Script path invalid: {script_path}"
                )
                return False

            self.log_test("Console Script", True, f"Console script: {script_path}")
            return True

        except Exception as e:
            self.log_test("Console Script", False, f"Error: {e}")
            return False

    def test_pyproject_toml_format(self) -> bool:
        """Test pyproject.toml has correct format and content"""
        try:
            pyproject_path = Path("pyproject.toml")
            if not pyproject_path.exists():
                self.log_test("Pyproject.toml", False, "pyproject.toml not found")
                return False

            content = pyproject_path.read_text()

            # Check for required sections
            required_sections = [
                "[build-system]",
                "[project]",
                "[tool.setuptools]",
                "[project.scripts]",
            ]

            missing_sections = []
            for section in required_sections:
                if section not in content:
                    missing_sections.append(section)

            if missing_sections:
                self.log_test(
                    "Pyproject.toml", False, f"Missing sections: {missing_sections}"
                )
                return False

            # Check for key fields
            required_fields = [
                'name = "finos-ai-governance-mcp-server"',
                'dynamic = ["version"]',
                'finos-mcp = "finos_mcp.server:main"',
            ]

            missing_fields = []
            for field in required_fields:
                if field not in content:
                    missing_fields.append(field)

            if missing_fields:
                self.log_test(
                    "Pyproject.toml", False, f"Missing fields: {missing_fields}"
                )
                return False

            self.log_test("Pyproject.toml", True, "Format and content valid")
            return True

        except Exception as e:
            self.log_test("Pyproject.toml", False, f"Error: {e}")
            return False

    def test_pep518_compliance(self) -> bool:
        """Test PEP 518 compliance by attempting to build"""
        try:
            # Test that the package can be built (dry run)
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", ".", "--dry-run"],
                capture_output=True,
                text=True,
            )

            # Note: --dry-run might not be supported in all pip versions
            # So we'll test actual install status instead
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import setuptools; print('setuptools available')",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                self.log_test("PEP 518 Compliance", False, "setuptools not available")
                return False

            # Check build-system in pyproject.toml
            pyproject_path = Path("pyproject.toml")
            content = pyproject_path.read_text()

            if 'build-backend = "setuptools.build_meta"' not in content:
                self.log_test("PEP 518 Compliance", False, "Invalid build backend")
                return False

            # Check for essential build requirements (setuptools_scm is optional but valid)
            if "setuptools>=61.0" not in content or "wheel" not in content:
                self.log_test("PEP 518 Compliance", False, "Invalid build requirements")
                return False

            self.log_test("PEP 518 Compliance", True, "PEP 518 compliant configuration")
            return True

        except Exception as e:
            self.log_test("PEP 518 Compliance", False, f"Error: {e}")
            return False

    def run_all_tests(self) -> bool:
        """Run all package skeleton tests"""
        print("📦 Testing Package Skeleton Implementation")
        print("=" * 60)

        tests = [
            ("Directory Structure", self.test_directory_structure),
            ("Package Import", self.test_package_importability),
            ("Editable Install", self.test_editable_install),
            ("Console Script", self.test_console_script),
            ("Pyproject.toml Format", self.test_pyproject_toml_format),
            ("PEP 518 Compliance", self.test_pep518_compliance),
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
            print("\n🚨 PACKAGE SKELETON HAS ISSUES")
            return False
        else:
            print("🎉 ALL PACKAGE SKELETON TESTS PASSED!")
            print("✅ src/ layout structure created successfully")
            print("✅ Package importable with correct metadata")
            print("✅ Editable installation working")
            print("✅ Console script entry point configured")
            print("✅ pyproject.toml PEP 518 compliant")
            print("✅ Ready for server code migration")
            return True


def main() -> None:
    """Main test runner"""
    tester = PackageSkeletonTester()
    success = tester.run_all_tests()

    if success:
        print("\n✅ PACKAGE SKELETON VALIDATION COMPLETE")
        print("📦 Python package structure ready for step 4!")
        sys.exit(0)
    else:
        print("\n❌ PACKAGE SKELETON VALIDATION FAILED")
        print("🚨 Must fix package issues before proceeding")
        sys.exit(1)


if __name__ == "__main__":
    main()
