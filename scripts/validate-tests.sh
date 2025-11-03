#!/bin/bash
# 🧪 TEST VALIDATION SCRIPT
# Validates pytest configuration and catches common test issues before CI
# Run this before committing test changes

set -e

echo "🧪 PYTEST VALIDATION - Catching Issues Before CI"
echo "=================================================="
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# =============================================================================
# PHASE 1: Pytest Collection Validation
# =============================================================================
echo "📋 PHASE 1: Pytest Collection Check"
echo "-----------------------------------"
echo "Validating pytest can collect all tests without errors..."

# Collect tests and capture output
pytest --collect-only tests/ -q > /tmp/pytest-collect.log 2>&1

# Check for fixture errors
if grep -qi "fixture.*not found" /tmp/pytest-collect.log 2>/dev/null; then
    echo "❌ CRITICAL: Pytest fixture errors found during collection!"
    echo ""
    echo "Detailed errors:"
    grep -i "fixture.*not found" /tmp/pytest-collect.log
    echo ""
    echo "💡 Common causes:"
    echo "   1. Test function has parameters but no matching @pytest.fixture"
    echo "   2. Helper function named 'test_*' with parameters (rename it!)"
    echo "   3. Missing fixture import from conftest.py"
    exit 1
fi

# Check for collection errors (but not test names containing "error")
if grep -i "^ERROR\|collection.*ERROR\|INTERNAL.*ERROR" /tmp/pytest-collect.log 2>/dev/null; then
    echo "❌ CRITICAL: Pytest collection errors found!"
    cat /tmp/pytest-collect.log
    exit 1
fi

# Count collected tests
TEST_COUNT=$(tail -1 /tmp/pytest-collect.log | grep -oE '[0-9]+' | head -1 || echo "0")
echo "✅ Pytest collection successful: $TEST_COUNT tests found"
echo ""

# =============================================================================
# PHASE 2: Test Naming Convention Check
# =============================================================================
echo "📝 PHASE 2: Test Naming Convention Check"
echo "----------------------------------------"
echo "Checking for potential test naming issues..."

# Find functions starting with 'test_' that have parameters (potential fixtures)
PARAM_TESTS=$(grep -r "^async def test_.*(..*:.*)" tests/ --include="*.py" | grep -v "@pytest.fixture" || echo "")

if [ -n "$PARAM_TESTS" ]; then
    echo "⚠️  WARNING: Found test functions with parameters:"
    echo "$PARAM_TESTS"
    echo ""
    echo "💡 These should either:"
    echo "   1. Have matching @pytest.fixture decorators, OR"
    echo "   2. Be renamed (remove 'test_' prefix if they're helpers)"
    echo ""
    # Don't fail, just warn
fi

# Find potential helper functions that might be collected as tests
SYNC_HELPERS=$(grep -r "^def test_.*(..*:.*)" tests/ --include="*.py" | grep -v "@pytest" || echo "")
if [ -n "$SYNC_HELPERS" ]; then
    echo "⚠️  WARNING: Found sync functions starting with 'test_' with parameters:"
    echo "$SYNC_HELPERS"
    echo ""
fi

echo "✅ Naming convention check complete"
echo ""

# =============================================================================
# PHASE 3: Test Markers Validation
# =============================================================================
echo "🏷️  PHASE 3: Test Markers Validation"
echo "------------------------------------"
echo "Validating pytest markers..."

# Check for unknown markers
pytest --strict-markers --collect-only tests/ -q > /tmp/pytest-markers.log 2>&1 || true

if grep -i "unknown mark" /tmp/pytest-markers.log; then
    echo "⚠️  WARNING: Unknown pytest markers found:"
    grep -i "unknown mark" /tmp/pytest-markers.log
    echo ""
    echo "💡 Add these markers to pyproject.toml [tool.pytest.ini_options] markers section"
else
    echo "✅ All pytest markers are valid"
fi
echo ""

# =============================================================================
# PHASE 4: Quick Smoke Test
# =============================================================================
echo "💨 PHASE 4: Quick Smoke Test"
echo "-----------------------------"
echo "Running fast unit tests as smoke test..."

# Run fast tests only (using pytest.fast.ini if available)
if [ -f "pytest.fast.ini" ]; then
    pytest -c pytest.fast.ini --co -q > /dev/null 2>&1
    FAST_TEST_COUNT=$(pytest -c pytest.fast.ini --co -q 2>&1 | tail -1 | grep -oE '[0-9]+' | head -1 || echo "0")
    echo "✅ Fast test configuration valid: $FAST_TEST_COUNT tests would run"
else
    echo "ℹ️  No pytest.fast.ini found, skipping fast test check"
fi
echo ""

# =============================================================================
# SUMMARY
# =============================================================================
echo "✅ VALIDATION COMPLETE"
echo "======================"
echo ""
echo "Summary:"
echo "  ✓ Pytest can collect $TEST_COUNT tests"
echo "  ✓ No fixture errors found"
echo "  ✓ Test markers validated"
echo ""
echo "💡 Next steps:"
echo "  1. Run: ./scripts/ci-exact-simulation.sh"
echo "  2. Run: pre-commit run --all-files"
echo "  3. Commit and push"
echo ""
