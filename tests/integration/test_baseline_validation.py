#!/usr/bin/env python3
"""
Baseline Validation Test Suite
Establishes and validates the current functionality before any refactoring.
This test ensures we have a stable foundation to build upon.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Import the server components directly to test functionality
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from the modern server location
import finos_mcp.server as finos_server
from finos_mcp.content.cache import get_cache
from finos_mcp.content.parse import parse_frontmatter
from finos_mcp.content.service import get_content_service

# Import the file lists and content service
get_mitigation_files = finos_server.get_mitigation_files
get_risk_files = finos_server.get_risk_files


class BaselineValidator:
    """Comprehensive baseline validation for the MCP server"""

    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []
        self.golden_data: dict[str, Any] = {}

    def log_result(
        self, test_name: str, passed: bool, message: str = "", data: Any = None
    ) -> None:
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"    {message}")

        self.results.append(
            {
                "test": test_name,
                "passed": passed,
                "message": message,
                "data": data,
                "timestamp": time.time(),
            }
        )

        if not passed:
            print(f"⚠️  CRITICAL: {test_name} failed - {message}")

    async def validate_http_fetching(self) -> bool:
        """Validate HTTP content fetching works correctly"""
        print("\n🌐 Testing HTTP Content Fetching...")

        # Use modern content service to fetch document
        service = await get_content_service()
        doc_data = await service.get_document(
            "mitigation", "mi-1_ai-data-leakage-prevention-and-detection.md"
        )

        if doc_data is None:
            self.log_result("HTTP Fetch", False, "Failed to fetch test document")
            return False

        content = doc_data["full_text"]
        if len(content) < 1000:
            self.log_result(
                "HTTP Fetch", False, f"Content too short: {len(content)} chars"
            )
            return False

        if not content.startswith("---"):
            self.log_result(
                "HTTP Fetch", False, "Content doesn't start with frontmatter"
            )
            return False

        self.log_result(
            "HTTP Fetch", True, f"Successfully fetched {len(content)} characters"
        )
        self.golden_data["sample_content_length"] = len(content)
        return True

    def validate_frontmatter_parsing(self) -> bool:
        """Validate YAML frontmatter parsing works correctly"""
        print("\n📄 Testing Frontmatter Parsing...")

        # Test with valid frontmatter
        test_content = """---
title: Test Document
sequence: 1
status: active
---
# Test Content
This is test markdown content."""

        metadata, body = parse_frontmatter(test_content)

        # metadata is always a dict based on function signature

        if metadata.get("title") != "Test Document":
            self.log_result(
                "Frontmatter Parse", False, f"Wrong title: {metadata.get('title')}"
            )
            return False

        if metadata.get("sequence") != 1:
            self.log_result(
                "Frontmatter Parse",
                False,
                f"Wrong sequence: {metadata.get('sequence')}",
            )
            return False

        if not body.startswith("# Test Content"):
            self.log_result(
                "Frontmatter Parse", False, f"Wrong body start: {body[:20]}"
            )
            return False

        self.log_result(
            "Frontmatter Parse", True, f"Parsed {len(metadata)} metadata fields"
        )
        return True

    async def validate_document_processing(self) -> bool:
        """Validate complete document processing pipeline"""
        print("\n📋 Testing Document Processing...")

        # Test mitigation document using modern content service
        service = await get_content_service()
        doc = await service.get_document(
            "mitigation", "mi-1_ai-data-leakage-prevention-and-detection.md"
        )

        if doc is None:
            self.log_result(
                "Document Processing", False, "Failed to get mitigation document"
            )
            return False

        required_fields = [
            "filename",
            "type",
            "url",
            "metadata",
            "content",
            "full_text",
        ]
        for field in required_fields:
            if field not in doc:
                self.log_result("Document Processing", False, f"Missing field: {field}")
                return False

        if doc["type"] != "mitigation":
            self.log_result("Document Processing", False, f"Wrong type: {doc['type']}")
            return False

        if not isinstance(doc["metadata"], dict) or len(doc["metadata"]) == 0:
            self.log_result("Document Processing", False, "Invalid metadata")
            return False

        self.log_result(
            "Document Processing",
            True,
            f"Processed document with {len(doc['metadata'])} metadata fields",
        )
        self.golden_data["mitigation_metadata_fields"] = list(doc["metadata"].keys())
        return True

    async def validate_caching_system(self) -> bool:
        """Validate the caching system works correctly"""
        print("\n💾 Testing Caching System...")

        # Get modern cache system
        cache = await get_cache()

        # Test cache operations
        test_key = "test_key"
        test_value = {"data": "test_data", "timestamp": time.time()}

        # Test cache set/get
        await cache.set(test_key, test_value, ttl=300)
        cached_value = await cache.get(test_key)

        if cached_value is None:
            self.log_result(
                "Cache Operations", False, "Failed to retrieve cached value"
            )
            return False

        if cached_value != test_value:
            self.log_result(
                "Cache Operations", False, "Cached value doesn't match original"
            )
            return False

        # Test cache miss
        missing_value = await cache.get("non_existent_key")
        if missing_value is not None:
            self.log_result(
                "Cache Operations", False, "Cache returned value for non-existent key"
            )
            return False

        # Test cache stats
        stats = await cache.get_stats()
        if not hasattr(stats, "hits") or not hasattr(stats, "misses"):
            self.log_result(
                "Cache Statistics", False, "Cache stats don't have required attributes"
            )
            return False

        self.log_result(
            "Cache Operations", True, "Cache set/get/miss operations work correctly"
        )
        return True

    async def validate_file_lists(self) -> bool:
        """Validate the dynamic file lists are correct"""
        print("\n📂 Testing File Lists...")

        try:
            mitigation_files = await get_mitigation_files()
            risk_files = await get_risk_files()
        except Exception as e:
            self.log_result("File Lists", False, f"Failed to get file lists: {e}")
            return False

        if len(mitigation_files) == 0:
            self.log_result("File Lists", False, "No mitigation files found")
            return False

        if len(risk_files) == 0:
            self.log_result("File Lists", False, "No risk files found")
            return False

        # Check file naming convention
        for filename in mitigation_files:
            if not filename.startswith("mi-") or not filename.endswith(".md"):
                self.log_result(
                    "File Lists", False, f"Invalid mitigation filename: {filename}"
                )
                return False

        for filename in risk_files:
            if not filename.startswith("ri-") or not filename.endswith(".md"):
                self.log_result(
                    "File Lists", False, f"Invalid risk filename: {filename}"
                )
                return False

        self.log_result(
            "File Lists",
            True,
            f"Found {len(mitigation_files)} mitigations, {len(risk_files)} risks",
        )
        self.golden_data["mitigation_count"] = len(mitigation_files)
        self.golden_data["risk_count"] = len(risk_files)
        return True

    async def validate_network_resilience(self) -> bool:
        """Test network error handling"""
        print("\n🌐 Testing Network Error Handling...")

        # Test with invalid document (should handle gracefully through content service)
        service = await get_content_service()

        # Test with non-existent file - should return None gracefully
        invalid_doc = await service.get_document("mitigation", "non-existent-file.md")

        if invalid_doc is not None:
            self.log_result(
                "Network Error Handling", False, "Non-existent file should return None"
            )
            return False

        # Test service health after error
        health_status = await service.get_health_status()
        if health_status.status.value == "critical":
            self.log_result(
                "Network Error Handling",
                False,
                "Service became critical after single error",
            )
            return False

        self.log_result(
            "Network Error Handling", True, "Network errors handled gracefully"
        )
        return True

    async def run_all_validations(self) -> bool:
        """Run all baseline validation tests"""
        print("🚀 Starting Baseline Validation Suite...")
        print("=" * 60)

        validation_tests = [
            self.validate_file_lists,
            self.validate_frontmatter_parsing,
            self.validate_caching_system,
            self.validate_http_fetching,
            self.validate_document_processing,
            self.validate_network_resilience,
        ]

        all_passed = True

        for test in validation_tests:
            try:
                if asyncio.iscoroutinefunction(test):
                    result = await test()
                else:
                    result = test()

                if not result:
                    all_passed = False

            except Exception as e:
                self.log_result(f"{test.__name__}", False, f"Exception: {e!s}")
                all_passed = False

        print("=" * 60)

        if all_passed:
            print("🎉 ALL BASELINE VALIDATIONS PASSED!")
            print(f"✅ {len([r for r in self.results if r['passed']])} tests passed")
            self.save_golden_data()
            return True
        else:
            failed_count = len([r for r in self.results if not r["passed"]])
            print(f"❌ VALIDATION FAILED: {failed_count} tests failed")
            print(
                "🚨 CRITICAL: Cannot proceed with refactoring until all baseline tests pass"
            )
            return False

    def save_golden_data(self) -> None:
        """Save golden data for regression testing"""
        golden_file = Path("tests/golden_baseline.json")
        golden_file.parent.mkdir(exist_ok=True)

        with open(golden_file, "w") as f:
            json.dump(self.golden_data, f, indent=2)

        print(f"📄 Golden baseline data saved to {golden_file}")


async def main() -> None:
    """Main validation runner"""
    validator = BaselineValidator()
    success = await validator.run_all_validations()

    if success:
        print("\n✅ BASELINE VALIDATION COMPLETE - READY FOR STEP 2")
        sys.exit(0)
    else:
        print("\n❌ BASELINE VALIDATION FAILED - MUST FIX BEFORE PROCEEDING")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
