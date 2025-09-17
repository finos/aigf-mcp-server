"""
Golden file testing system for regression detection.
Provides comprehensive golden file management, comparison, and regression analysis.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .mock_content_service import get_mock_content_service


@dataclass
class GoldenFileConfig:
    """Configuration for golden file operations."""

    golden_dir: Path = Path("tests/golden")
    update_mode: bool = False
    strict_comparison: bool = True
    ignore_fields: list[str] = field(
        default_factory=lambda: ["timestamp", "operation_id"]
    )
    hash_algorithm: str = "sha256"
    similarity_threshold: float = 0.95


@dataclass
class ComparisonResult:
    """Result of golden file comparison."""

    is_match: bool
    similarity_score: float
    differences: list[dict[str, Any]]
    summary: str
    details: dict[str, Any] | None = None


@dataclass
class TestResult:
    """Result of a golden file test."""

    test_name: str
    passed: bool
    comparison_result: ComparisonResult | None
    execution_time_ms: float = 0.0
    error: str | None = None


@dataclass
class RegressionReport:
    """Comprehensive regression analysis report."""

    total_tests: int
    passed_tests: int
    failed_tests: int
    regressions: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    summary: str
    generated_at: float = field(default_factory=time.time)


class GoldenFileManager:
    """Manages golden file storage and retrieval."""

    def __init__(self, config: GoldenFileConfig | None = None):
        """Initialize golden file manager.

        Args:
            config: Configuration for golden file operations
        """
        self.config = config or GoldenFileConfig()
        self.config.golden_dir.mkdir(parents=True, exist_ok=True)

    def save_golden_file(self, test_name: str, data: dict[str, Any]) -> bool:
        """Save golden file data.

        Args:
            test_name: Name of the test case
            data: Data to save as golden reference

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            golden_file = self.config.golden_dir / f"{test_name}.golden.json"

            golden_data = {
                "test_name": test_name,
                "data": data,
                "created_at": time.time(),
                "checksum": self._calculate_checksum(data),
            }

            with open(golden_file, "w", encoding="utf-8") as f:
                json.dump(golden_data, f, indent=2, sort_keys=True)

            return True

        except (OSError, TypeError, ValueError):
            return False

    def load_golden_file(self, test_name: str) -> dict[str, Any] | None:
        """Load golden file data.

        Args:
            test_name: Name of the test case

        Returns:
            Golden file data or None if not found
        """
        golden_file = self.config.golden_dir / f"{test_name}.golden.json"

        if not self._file_exists(golden_file):
            return None

        return self._load_json_file(golden_file)

    def list_golden_files(self) -> list[str]:
        """List all available golden files.

        Returns:
            List of test names with golden files
        """
        golden_files = list(self.config.golden_dir.glob("*.golden.json"))
        return [f.stem.replace(".golden", "") for f in golden_files]

    def _file_exists(self, file_path: Path) -> bool:
        """Check if file exists."""
        return file_path.exists() and file_path.is_file()

    def _load_json_file(self, file_path: Path) -> dict[str, Any] | None:
        """Load JSON file safely."""
        try:
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def _calculate_checksum(self, data: dict[str, Any]) -> str:
        """Calculate checksum for data."""
        # Create deterministic JSON string for hashing
        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))

        if self.config.hash_algorithm == "sha256":
            return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
        elif self.config.hash_algorithm == "md5":
            return hashlib.md5(json_str.encode("utf-8")).hexdigest()
        else:
            return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


class GoldenFileComparator:
    """Compares actual data with golden file references."""

    def __init__(self, ignore_fields: list[str] | None = None, strict: bool = True):
        """Initialize comparator.

        Args:
            ignore_fields: Fields to ignore during comparison
            strict: Whether to use strict comparison
        """
        self.ignore_fields = set(ignore_fields or ["timestamp", "operation_id"])
        self.strict = strict

    def compare(
        self, golden_data: dict[str, Any], actual_data: dict[str, Any]
    ) -> ComparisonResult:
        """Compare golden data with actual data.

        Args:
            golden_data: Expected data from golden file
            actual_data: Actual data from test execution

        Returns:
            Comparison result with details
        """
        # Remove ignored fields for comparison
        golden_filtered = self._filter_ignored_fields(golden_data)
        actual_filtered = self._filter_ignored_fields(actual_data)

        differences = []
        self._compare_recursive(golden_filtered, actual_filtered, "", differences)

        is_match = len(differences) == 0
        similarity_score = self._calculate_similarity(golden_filtered, actual_filtered)

        summary = "Exact match" if is_match else f"Found {len(differences)} differences"

        return ComparisonResult(
            is_match=is_match,
            similarity_score=similarity_score,
            differences=differences,
            summary=summary,
            details={
                "golden_keys": set(golden_filtered.keys())
                if isinstance(golden_filtered, dict)
                else None,
                "actual_keys": set(actual_filtered.keys())
                if isinstance(actual_filtered, dict)
                else None,
            },
        )

    def deep_compare(
        self, obj1: Any, obj2: Any, path: str = ""
    ) -> list[dict[str, Any]]:
        """Perform deep comparison of nested objects.

        Args:
            obj1: First object to compare
            obj2: Second object to compare
            path: Current path in object hierarchy

        Returns:
            List of differences found
        """
        differences = []
        self._compare_recursive(obj1, obj2, path, differences)
        return differences

    def generate_diff(
        self, golden_data: dict[str, Any], actual_data: dict[str, Any]
    ) -> str:
        """Generate human-readable diff.

        Args:
            golden_data: Expected data
            actual_data: Actual data

        Returns:
            Formatted diff string
        """
        differences = self.deep_compare(golden_data, actual_data)

        if not differences:
            return "No differences found"

        diff_lines = ["Golden file comparison differences:", ""]

        for diff in differences:
            diff_lines.append(f"Path: {diff['path']}")
            diff_lines.append(f"  Expected: {diff['expected']}")
            diff_lines.append(f"  Actual:   {diff['actual']}")
            diff_lines.append("")

        return "\n".join(diff_lines)

    def _filter_ignored_fields(self, data: Any) -> Any:
        """Remove ignored fields from data."""
        if isinstance(data, dict):
            return {
                k: self._filter_ignored_fields(v)
                for k, v in data.items()
                if k not in self.ignore_fields
            }
        elif isinstance(data, list):
            return [self._filter_ignored_fields(item) for item in data]
        else:
            return data

    def _compare_recursive(
        self, obj1: Any, obj2: Any, path: str, differences: list[dict[str, Any]]
    ) -> None:
        """Recursively compare objects and collect differences."""
        if type(obj1) != type(obj2):
            differences.append(
                {
                    "path": path or "root",
                    "type": "type_mismatch",
                    "expected": str(type(obj1).__name__),
                    "actual": str(type(obj2).__name__),
                }
            )
            return

        if isinstance(obj1, dict):
            all_keys = set(obj1.keys()) | set(obj2.keys())
            for key in all_keys:
                key_path = f"{path}.{key}" if path else key

                if key not in obj1:
                    differences.append(
                        {
                            "path": key_path,
                            "type": "missing_expected",
                            "expected": None,
                            "actual": obj2[key],
                        }
                    )
                elif key not in obj2:
                    differences.append(
                        {
                            "path": key_path,
                            "type": "missing_actual",
                            "expected": obj1[key],
                            "actual": None,
                        }
                    )
                else:
                    self._compare_recursive(obj1[key], obj2[key], key_path, differences)

        elif isinstance(obj1, list):
            if len(obj1) != len(obj2):
                differences.append(
                    {
                        "path": path or "root",
                        "type": "length_mismatch",
                        "expected": len(obj1),
                        "actual": len(obj2),
                    }
                )

            for i in range(min(len(obj1), len(obj2))):
                item_path = f"{path}[{i}]" if path else f"[{i}]"
                self._compare_recursive(obj1[i], obj2[i], item_path, differences)

        else:
            if obj1 != obj2:
                differences.append(
                    {
                        "path": path or "root",
                        "type": "value_mismatch",
                        "expected": obj1,
                        "actual": obj2,
                    }
                )

    def _calculate_similarity(self, obj1: Any, obj2: Any) -> float:
        """Calculate similarity score between objects."""
        if obj1 == obj2:
            return 1.0

        if isinstance(obj1, dict) and isinstance(obj2, dict):
            all_keys = set(obj1.keys()) | set(obj2.keys())
            if not all_keys:
                return 1.0

            matching_keys = sum(
                1
                for key in all_keys
                if key in obj1 and key in obj2 and obj1[key] == obj2[key]
            )
            return matching_keys / len(all_keys)

        elif isinstance(obj1, list) and isinstance(obj2, list):
            if not obj1 and not obj2:
                return 1.0
            if not obj1 or not obj2:
                return 0.0

            max_len = max(len(obj1), len(obj2))
            matching_items = sum(
                1 for i in range(min(len(obj1), len(obj2))) if obj1[i] == obj2[i]
            )
            return matching_items / max_len

        else:
            return 1.0 if obj1 == obj2 else 0.0


class GoldenTestRunner:
    """Runs golden file tests and manages test execution."""

    def __init__(
        self, config: GoldenFileConfig | None = None, update_mode: bool = False
    ):
        """Initialize test runner.

        Args:
            config: Configuration for golden file operations
            update_mode: Whether to update golden files instead of comparing
        """
        self.config = config or GoldenFileConfig()
        self.config.update_mode = update_mode or self.config.update_mode
        self.manager = GoldenFileManager(self.config)
        self.comparator = GoldenFileComparator(
            ignore_fields=self.config.ignore_fields,
            strict=self.config.strict_comparison,
        )

    async def run_golden_test(self, test_name: str) -> TestResult | None:
        """Run a single golden file test.

        Args:
            test_name: Name of the test to run

        Returns:
            Test result or None if test couldn't be executed
        """
        start_time = time.time()

        try:
            # Update mode: generate/update golden file without comparison
            if self.config.update_mode:
                # For update mode, we need some test input - create a default one
                default_test_data = {
                    "input": {"doc_type": "mitigation", "filename": f"{test_name}.md"},
                    "test_name": test_name,
                }
                actual_data = await self._execute_test_case(default_test_data)
                if actual_data is None:
                    return TestResult(
                        test_name=test_name,
                        passed=False,
                        comparison_result=None,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        error="Failed to generate data for golden file",
                    )

                success = self._save_golden_file(
                    test_name,
                    {
                        "input": default_test_data["input"],
                        "expected_output": actual_data,
                    },
                )
                return TestResult(
                    test_name=test_name,
                    passed=success,
                    comparison_result=None,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            # Compare mode: load golden file and compare
            golden_data = self._load_golden_file(test_name)
            if not golden_data:
                return TestResult(
                    test_name=test_name,
                    passed=False,
                    comparison_result=None,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    error="Golden file not found",
                )

            # Execute test and get actual data
            actual_data = await self._execute_test_case(golden_data)
            if actual_data is None:
                return TestResult(
                    test_name=test_name,
                    passed=False,
                    comparison_result=None,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    error="Test execution failed",
                )

            # Compare with golden data
            expected_data = golden_data.get("data") or golden_data.get(
                "expected_output"
            )
            if expected_data is None:
                return TestResult(
                    test_name=test_name,
                    passed=False,
                    comparison_result=None,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    error="No expected data found in golden file",
                )

            comparison = self.comparator.compare(expected_data, actual_data)

            return TestResult(
                test_name=test_name,
                passed=comparison.is_match,
                comparison_result=comparison,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return TestResult(
                test_name=test_name,
                passed=False,
                comparison_result=None,
                execution_time_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    async def generate_golden_files(
        self, test_cases: list[dict[str, Any]]
    ) -> list[bool]:
        """Generate golden files for multiple test cases.

        Args:
            test_cases: List of test case definitions

        Returns:
            List of success status for each test case
        """
        results = []

        for test_case in test_cases:
            success = await self._generate_single_golden_file(test_case)
            results.append(success)

        return results

    async def validate_all_golden_files(self) -> list[TestResult | dict[str, Any]]:
        """Validate all available golden files.

        Returns:
            List of validation results
        """
        golden_files = self._discover_golden_files()
        results = []

        for test_name in golden_files:
            result = await self.run_golden_test(test_name)
            if result:
                results.append(result)
            else:
                # Fallback dict format for compatibility
                results.append(
                    {
                        "test_name": test_name,
                        "passed": False,
                        "error": "Test execution failed",
                    }
                )

        return results

    def _load_golden_file(self, test_name: str) -> dict[str, Any] | None:
        """Load golden file data."""
        return self.manager.load_golden_file(test_name)

    def _save_golden_file(self, test_name: str, data: dict[str, Any]) -> bool:
        """Save golden file data."""
        return self.manager.save_golden_file(test_name, data)

    async def _execute_test_case(
        self, golden_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Execute test case and return actual data."""
        try:
            # Extract test case info from golden data
            if "input" in golden_data:
                input_data = golden_data["input"]
                doc_type = input_data.get("doc_type")
                filename = input_data.get("filename")

                if doc_type and filename:
                    # Execute using mock content service
                    content_service = await get_mock_content_service()
                    result = await content_service.get_document(doc_type, filename)
                    return result

            return None

        except Exception:
            return None

    async def _generate_single_golden_file(self, test_case: dict[str, Any]) -> bool:
        """Generate single golden file from test case definition."""
        try:
            test_name = test_case.get("name")
            doc_type = test_case.get("doc_type")
            filename = test_case.get("filename")

            if not all([test_name, doc_type, filename]):
                return False

            # Execute test to get data
            content_service = await get_mock_content_service()
            data = await content_service.get_document(doc_type, filename)

            if data is None:
                return False

            # Create golden file with input context
            golden_content = {
                "input": {"doc_type": doc_type, "filename": filename},
                "expected_output": data,
            }

            return self.manager.save_golden_file(test_name, golden_content)

        except Exception:
            return False

    def _discover_golden_files(self) -> list[str]:
        """Discover available golden files."""
        return self.manager.list_golden_files()


class RegressionDetector:
    """Detects regressions in golden file test results."""

    def __init__(self, similarity_threshold: float = 0.95):
        """Initialize regression detector.

        Args:
            similarity_threshold: Minimum similarity score to consider acceptable
        """
        self.similarity_threshold = similarity_threshold

    def detect_regressions(
        self, test_results: list[TestResult | dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect regressions in test results.

        Args:
            test_results: List of test results to analyze

        Returns:
            List of detected regressions
        """
        regressions = []

        for result in test_results:
            # Handle both TestResult objects and dicts
            if isinstance(result, TestResult):
                test_name = result.test_name
                passed = result.passed
                similarity = (
                    result.comparison_result.similarity_score
                    if result.comparison_result
                    else 0.0
                )
            else:
                test_name = result.get("test_name", "unknown")
                passed = result.get("passed", False)
                similarity = result.get("similarity", 0.0)

            # Detect various types of regressions
            if not passed:
                regressions.append(
                    {
                        "test_name": test_name,
                        "type": "test_failure",
                        "severity": "high",
                        "passed": passed,
                        "similarity": similarity,
                        "description": "Test failed completely",
                    }
                )
            elif similarity < self.similarity_threshold:
                regressions.append(
                    {
                        "test_name": test_name,
                        "type": "similarity_degradation",
                        "severity": "medium",
                        "passed": passed,
                        "similarity": similarity,
                        "description": f"Similarity below threshold ({similarity:.3f} < {self.similarity_threshold})",
                    }
                )

        return regressions

    def analyze_changes(
        self, previous_results: dict[str, Any], current_results: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyze changes between two sets of results.

        Args:
            previous_results: Previous test results
            current_results: Current test results

        Returns:
            Dictionary of detected changes
        """
        changes = {}

        # Check for changed tests
        for test_name in current_results:
            if test_name in previous_results:
                prev = previous_results[test_name]
                curr = current_results[test_name]

                # Check for checksum changes
                prev_checksum = prev.get("checksum")
                curr_checksum = curr.get("checksum")

                if prev_checksum and curr_checksum and prev_checksum != curr_checksum:
                    changes[test_name] = {
                        "type": "content_change",
                        "previous_checksum": prev_checksum,
                        "current_checksum": curr_checksum,
                    }

                # Check for status changes
                prev_passed = prev.get("passed", False)
                curr_passed = curr.get("passed", False)

                if prev_passed != curr_passed:
                    changes[test_name] = changes.get(test_name, {})
                    changes[test_name].update(
                        {
                            "status_change": True,
                            "previous_passed": prev_passed,
                            "current_passed": curr_passed,
                        }
                    )

        return changes

    def generate_report(
        self, test_results: list[TestResult | dict[str, Any]]
    ) -> RegressionReport:
        """Generate comprehensive regression report.

        Args:
            test_results: Test results to analyze

        Returns:
            Detailed regression report
        """
        total_tests = len(test_results)
        passed_tests = sum(
            1
            for r in test_results
            if (r.passed if isinstance(r, TestResult) else r.get("passed", False))
        )
        failed_tests = total_tests - passed_tests

        regressions = self.detect_regressions(test_results)

        # Generate warnings for tests with lower similarity
        warnings = []
        for result in test_results:
            if isinstance(result, TestResult):
                similarity = (
                    result.comparison_result.similarity_score
                    if result.comparison_result
                    else 1.0
                )
                test_name = result.test_name
            else:
                similarity = result.get("similarity", 1.0)
                test_name = result.get("test_name", "unknown")

            if 0.8 <= similarity < self.similarity_threshold:
                warnings.append(
                    {
                        "test_name": test_name,
                        "similarity": similarity,
                        "message": "Similarity approaching threshold",
                    }
                )

        # Generate summary
        if failed_tests == 0 and len(regressions) == 0:
            summary = f"All {total_tests} tests passed with no regressions detected"
        else:
            summary = (
                f"{failed_tests} failed tests, {len(regressions)} regressions detected"
            )

        return RegressionReport(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            regressions=regressions,
            warnings=warnings,
            summary=summary,
        )
