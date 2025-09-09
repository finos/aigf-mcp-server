#!/bin/bash
# MANDATORY Pre-commit Hook: API Consistency Validation
# Purpose: Prevent tests from calling non-existent methods

set -e

echo "🔍 Validating API Consistency..."

FAILED=false
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Check 1: Look for calls to removed/deprecated methods
echo "Checking for calls to removed methods..."
REMOVED_METHODS_FOUND=$(grep -r -n "reset_statistics\|_get_cache_stats" "${PROJECT_ROOT}/tests/" 2>/dev/null | grep -v "test_method_exists" || true)

if [ -n "$REMOVED_METHODS_FOUND" ]; then
    echo "❌ CRITICAL: Found calls to removed methods:"
    echo "$REMOVED_METHODS_FOUND"
    echo ""
    echo "These methods have been removed:"
    echo "- reset_statistics() → Use reset_health() instead"
    echo "- _get_cache_stats() → Use get_service_diagnostics() instead"
    FAILED=true
fi

# Check 2: Look for missing await on async methods
echo "Checking for missing await on async methods..."
MISSING_AWAIT=$(grep -r -n "service\.get_health_status()\|service\.get_service_diagnostics()\|service\.reset_health()" "${PROJECT_ROOT}/tests/" 2>/dev/null | grep -v "await" | grep -v "assert" || true)

if [ -n "$MISSING_AWAIT" ]; then
    echo "❌ CRITICAL: Found missing await for async methods:"
    echo "$MISSING_AWAIT"
    echo ""
    echo "These methods are async and require await:"
    echo "- await service.get_health_status()"
    echo "- await service.get_service_diagnostics()"
    echo "- await service.reset_health()"
    FAILED=true
fi

# Check 3: Ensure API contract validation tests exist
echo "Checking for API contract validation tests..."
API_CONTRACT_TESTS=$(find "${PROJECT_ROOT}/tests/unit" -name "*.py" -exec grep -l "api_contract_validation\|API.*CONTRACT" {} \; 2>/dev/null || true)

if [ -z "$API_CONTRACT_TESTS" ]; then
    echo "⚠️  WARNING: No API contract validation tests found"
    echo "Consider adding API contract validation to test classes"
fi

# Check 4: Validate test file structure
echo "Checking test file structure..."
TEST_FILES_WITHOUT_ASYNC=$(find "${PROJECT_ROOT}/tests/unit" -name "*.py" -exec grep -L "@pytest.mark.asyncio" {} \; 2>/dev/null | grep -v "__" || true)

if [ -n "$TEST_FILES_WITHOUT_ASYNC" ]; then
    echo "ℹ️  INFO: Test files without async markers found:"
    echo "$TEST_FILES_WITHOUT_ASYNC"
fi

# Final result
if [ "$FAILED" = true ]; then
    echo ""
    echo "❌ API CONSISTENCY VALIDATION FAILED"
    echo "Fix API mismatches before committing!"
    echo ""
    echo "Common fixes:"
    echo "1. Replace reset_statistics() with reset_health()"
    echo "2. Replace _get_cache_stats() with get_service_diagnostics()"
    echo "3. Add 'await' before async method calls"
    echo "4. Add @pytest.mark.asyncio to async test methods"
    exit 1
fi

echo "✅ API Consistency Validated Successfully"
echo ""
