#!/bin/bash
# 🎯 EXACT CI SIMULATION SCRIPT
# This script runs the IDENTICAL commands that GitHub Actions CI runs
# to prevent local/CI validation mismatches
# UPDATED: Fixed CI workflow discrepancies (Ruff & Pylint error handling)
#
# ⚠️  IMPORTANT: This script simulates CI but cannot guarantee 100% parity because:
# - Tool versions may differ (GitHub Actions may use newer versions)
# - Different Python/OS environments may have different behaviors
# - Always verify critical changes pass actual GitHub CI before merging
#
# 💡 To minimize differences:
# - Keep tool versions in pyproject.toml up to date
# - Run this script before every commit
# - Monitor GitHub Actions for version updates

set -uo pipefail  # Exit on undefined variables or pipe failures, but not regular errors

# Initialize exit code tracking
OVERALL_EXIT_CODE=0
FAILED_PHASES=()

# Function to handle errors but continue execution
handle_phase_error() {
    local phase_name="$1"
    local exit_code="$2"
    echo "❌ PHASE FAILED: $phase_name (exit code: $exit_code)"
    FAILED_PHASES+=("$phase_name")
    if [ $OVERALL_EXIT_CODE -eq 0 ]; then
        OVERALL_EXIT_CODE=$exit_code
    fi
}

# Function to run command with error handling
run_phase() {
    local phase_name="$1"
    shift
    echo "🔄 Running: $*"
    set +e  # Temporarily disable exit on error
    "$@"
    local exit_code=$?
    set -e  # Re-enable exit on error

    if [ $exit_code -eq 0 ]; then
        echo "✅ $phase_name passed"
        return 0
    else
        handle_phase_error "$phase_name" $exit_code
        return $exit_code
    fi
}

echo "🔍 EXACT CI SIMULATION - FINOS MCP Server"
echo "=========================================="
echo "📍 Location: $(pwd)"

# Ensure we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "src/finos_mcp" ]; then
    echo "❌ ERROR: Must run from project root directory"
    echo "Expected: /Users/hugocalderon/SRC/IA-FINOS"
    exit 1
fi

# Activate virtual environment if not already active
if [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "🔄 Activating virtual environment..."
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    else
        echo "❌ ERROR: Virtual environment not found at .venv/bin/activate"
        echo "Run: python -m venv .venv && source .venv/bin/activate && pip install -e .[dev,security]"
        exit 1
    fi
fi

echo "🐍 Python: $(python --version)"
echo "📦 Virtual Environment: $VIRTUAL_ENV"
echo "⏰ Started: $(date)"
echo ""

# Install CI-specific dependencies that may not be in local environment
echo "📦 Installing CI-specific dependencies..."
pip install lxml > /dev/null 2>&1 || echo "⚠️  lxml installation failed - some CI reports may not work"

# Ensure all dev dependencies including type stubs are installed
echo "📦 Installing dev dependencies with type stubs..."
pip install -e .[security,dev] > /dev/null 2>&1 || echo "⚠️  Dev dependencies installation failed"

# Create the same directories as CI
echo "📁 Creating CI directories..."
mkdir -p security-reports
mkdir -p coverage-reports

# =============================================================================
# PHASE 1: BANDIT SECURITY SCANNER (EXACT CI COMMAND)
# =============================================================================
echo ""
echo "🛡️ PHASE 1: Bandit Security Scanner (EXACT CI COMMAND)"
echo "----------------------------------------------------"

echo "Running Bandit security scanner..."
python -m bandit -c config/security/bandit.yml -r src/ \
  --format json \
  --output security-reports/bandit-report.json \
  --severity-level low \
  --confidence-level medium

# Check if any HIGH or MEDIUM severity issues were found (EXACT CI LOGIC)
HIGH_ISSUES=$(jq '[.results[] | select(.issue_severity == "HIGH")] | length' security-reports/bandit-report.json)
MEDIUM_ISSUES=$(jq '[.results[] | select(.issue_severity == "MEDIUM")] | length' security-reports/bandit-report.json)

echo "Bandit found $HIGH_ISSUES high severity and $MEDIUM_ISSUES medium severity issues"

if [ "$HIGH_ISSUES" -gt 0 ]; then
  echo "❌ CRITICAL: Bandit found $HIGH_ISSUES high severity security issues"
  jq '.results[] | select(.issue_severity == "HIGH")' security-reports/bandit-report.json
  exit 1
fi

if [ "$MEDIUM_ISSUES" -gt 3 ]; then
  echo "❌ FAILURE: Bandit found $MEDIUM_ISSUES medium severity issues (threshold: 3)"
  exit 1
fi

echo "✅ Bandit security scan passed"

# =============================================================================
# PHASE 2: SEMGREP STATIC ANALYSIS (EXACT CI COMMAND)
# =============================================================================
echo ""
echo "🔍 PHASE 2: Semgrep Static Analysis (EXACT CI COMMAND)"
echo "-----------------------------------------------------"

echo "Running Semgrep static analysis..."
./scripts/semgrep-isolated.sh --config config/security/semgrep.yml src/ \
  --json \
  --output security-reports/semgrep-report.json \
  --metrics=off

# Check for ERROR level findings (EXACT CI LOGIC)
ERROR_ISSUES=$(jq '[.results[] | select(.extra.severity == "ERROR")] | length' security-reports/semgrep-report.json)
WARNING_ISSUES=$(jq '[.results[] | select(.extra.severity == "WARNING")] | length' security-reports/semgrep-report.json)

echo "Semgrep found $ERROR_ISSUES errors and $WARNING_ISSUES warnings"

if [ "$ERROR_ISSUES" -gt 0 ]; then
  echo "❌ CRITICAL: Semgrep found $ERROR_ISSUES critical security issues"
  jq '.results[] | select(.extra.severity == "ERROR")' security-reports/semgrep-report.json
  exit 1
fi

echo "✅ Semgrep security scan passed"

# =============================================================================
# PHASE 3: PYLINT CODE ANALYSIS (EXACT CI COMMAND)
# =============================================================================
echo ""
echo "📊 PHASE 3: Pylint Code Analysis (EXACT CI COMMAND)"
echo "--------------------------------------------------"

echo "Running Pylint code quality analysis..."
set +e  # Temporarily disable exit on error to capture Pylint exit code
python -m pylint src/ \
  --output-format=json \
  --reports=yes \
  --score=yes > security-reports/pylint-report.json
PYLINT_EXIT_CODE=$?
set -e  # Re-enable exit on error

if [ $PYLINT_EXIT_CODE -ne 0 ]; then
  echo "❌ CRITICAL: Pylint score below 8.5 threshold (exit code: $PYLINT_EXIT_CODE)"
  echo "📋 Detailed Pylint report:"
  cat security-reports/pylint-report.json | jq '.[] | select(.type == "fatal" or .type == "error") | {type, message, path, line}'
  exit 1
fi

echo "✅ Pylint code quality check passed"

# =============================================================================
# PHASE 4: RUFF LINTER (EXACT CI COMMAND)
# =============================================================================
echo ""
echo "🎨 PHASE 4: Ruff Linter (EXACT CI COMMAND)"
echo "-----------------------------------------"

echo "Running Ruff linter..."
set +e  # Temporarily disable exit on error to capture Ruff exit code
ruff check src/ tests/ scripts/ --output-format=json > security-reports/ruff-report.json
RUFF_EXIT_CODE=$?
set -e  # Re-enable exit on error

# Count the number of issues found (EXACT CI LOGIC)
RUFF_ISSUES=$(jq 'length' security-reports/ruff-report.json)
echo "Ruff found $RUFF_ISSUES linting issues"

# CRITICAL: Fail if Ruff found any issues (EXACT CI BEHAVIOR)
if [ $RUFF_EXIT_CODE -ne 0 ]; then
  echo "❌ CRITICAL: Ruff found $RUFF_ISSUES linting issues"
  echo "📋 Detailed Ruff issues:"
  jq '.' security-reports/ruff-report.json
  echo ""
  echo "💡 To fix these issues automatically, run:"
  echo "   ruff check src/ tests/ scripts/ --fix --unsafe-fixes"
  echo "   ruff format src/ tests/ scripts/"
  exit 1
fi

# Check formatting (EXACT CI COMMAND)
echo "Checking code formatting with Ruff..."
set +e
ruff format --check src/ tests/ scripts/
FORMAT_EXIT_CODE=$?
set -e

if [ $FORMAT_EXIT_CODE -ne 0 ]; then
  echo "❌ CRITICAL: Ruff format check failed"
  echo "💡 To fix formatting issues, run:"
  echo "   ruff format src/ tests/ scripts/"
  exit 1
fi

echo "✅ Ruff linting and formatting checks passed"

# =============================================================================
# PHASE 5: MYPY TYPE CHECKING (EXACT CI COMMAND) - THE CRITICAL ONE
# =============================================================================
echo ""
echo "🏷️ PHASE 5: MyPy Type Checking (EXACT CI COMMAND) - CRITICAL"
echo "------------------------------------------------------------"

echo "Running MyPy type checking..."
echo "COMMAND: python -m mypy src/finos_mcp --show-error-codes --show-error-context --txt-report security-reports/mypy-report --strict-optional --warn-redundant-casts --warn-unused-ignores"
echo ""

# THIS IS THE EXACT COMMAND THAT CI RUNS - THE ONE THAT WAS FAILING
python -m mypy src/finos_mcp \
  --show-error-codes \
  --show-error-context \
  --txt-report security-reports/mypy-report \
  --strict-optional \
  --warn-redundant-casts \
  --warn-unused-ignores

echo "✅ MyPy type checking passed - no type errors found"

# =============================================================================
# PHASE 6: ALL TESTS (EXACT CI COMMAND)
# =============================================================================
echo ""
echo "🧪 PHASE 6: All Tests (EXACT CI COMMAND)"
echo "---------------------------------------"

echo "Running all tests..."
if [ -d "tests" ]; then
  # Run tests with less verbose output to avoid truncation
  set +e  # Temporarily disable exit on error for this section
  python -m pytest tests/ \
    --cov=src/finos_mcp \
    --cov-report=json:coverage-reports/coverage.json \
    --cov-report=xml:coverage-reports/coverage.xml \
    --cov-report=html:coverage-reports/html \
    --junit-xml=coverage-reports/pytest.xml \
    --cov-fail-under=65 \
    --tb=short \
    --quiet

  # Show summary of test results
  PYTEST_EXIT_CODE=$?
  set -e  # Re-enable exit on error

  if [ $PYTEST_EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed successfully"

    # Extract key metrics from coverage report
    if [ -f "coverage-reports/coverage.json" ]; then
      COVERAGE=$(python -c "import json; data=json.load(open('coverage-reports/coverage.json')); print(f'{data[\"totals\"][\"percent_covered\"]:.1f}%')" 2>/dev/null || echo "unknown")
      echo "📊 Test Coverage: $COVERAGE"
    fi
  else
    echo "❌ Tests failed with exit code: $PYTEST_EXIT_CODE"
    handle_phase_error "All Tests" $PYTEST_EXIT_CODE
  fi
else
  echo "⚠️  No tests directory found - skipping tests"
fi

# =============================================================================
# PHASE 7: PIP-AUDIT DEPENDENCY SCANNER (EXACT CI COMMAND)
# =============================================================================
echo ""
echo "🔐 PHASE 7: pip-audit Dependency Scanner (EXACT CI COMMAND)"
echo "------------------------------------------------------------"

echo "Running pip-audit dependency vulnerability scanner..."
pip freeze > security-reports/requirements.txt

# Install pip-audit (Python Packaging Authority's official tool)
python -m pip install pip-audit

# Run pip-audit scan - fail on any known vulnerabilities
# Ignored vulnerabilities (no fix available):
# - GHSA-7gcm-g887-7qv7: protobuf DoS via JSON recursion (CVE-2026-0994)
# - GHSA-w8v5-vhqr-4h9v: diskcache vulnerability with no patched release available
pip-audit --format json --output security-reports/pip-audit-report.json \
  --ignore-vuln GHSA-7gcm-g887-7qv7 \
  --ignore-vuln GHSA-w8v5-vhqr-4h9v

# Check for vulnerabilities - handle both old and new pip-audit output formats (EXACT CI LOGIC)
VULNS=$(jq 'if type == "array" then map(select(.vulns? | length? > 0)) | length elif .dependencies then .dependencies | map(select(.vulns | length > 0)) | length else 0 end' security-reports/pip-audit-report.json)

if [ "$VULNS" -gt 0 ]; then
  echo "❌ CRITICAL: Found vulnerabilities in $VULNS dependencies"
  if jq -e '.dependencies' security-reports/pip-audit-report.json > /dev/null; then
    jq '.dependencies | map(select(.vulns | length > 0))' security-reports/pip-audit-report.json
  else
    jq 'map(select(.vulns? | length? > 0))' security-reports/pip-audit-report.json
  fi
  exit 1
fi

echo "✅ No known vulnerabilities found in dependencies"

# =============================================================================
# PHASE 8: INTEGRATION TESTS (EXACT CI COMMAND)
# =============================================================================
echo ""
echo "🔗 PHASE 8: Integration Tests (EXACT CI COMMAND)"
echo "-----------------------------------------------"

echo "Running integration tests..."
# Test that the MCP server can actually start and respond (EXACT CI CODE)
# Use python timeout implementation for cross-platform compatibility
python -c "
import asyncio
import sys
import signal
sys.path.insert(0, 'src')

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException('Integration test timed out after 30 seconds')

# Set timeout (Linux/macOS compatible)
try:
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)
except AttributeError:
    # Windows doesn't have SIGALRM, skip timeout
    pass

async def test_server_startup():
    try:
        from finos_mcp.fastmcp_main import main
        from finos_mcp.content.service import get_content_service
        print('✅ Server imports successful')

        # Test service initialization
        service = await get_content_service()
        print('✅ Content service initialization successful')

        print('✅ Integration tests passed')
    except Exception as e:
        print(f'❌ Integration test failed: {e}')
        sys.exit(1)
    finally:
        try:
            signal.alarm(0)  # Cancel timeout
        except AttributeError:
            pass

try:
    asyncio.run(test_server_startup())
except TimeoutException as e:
    print(f'❌ Integration test failed: {e}')
    sys.exit(1)
"

echo "✅ Integration tests completed successfully"

# =============================================================================
# FINAL VALIDATION SUMMARY
# =============================================================================
echo ""
echo "📋 CI SIMULATION SUMMARY"
echo "========================="

if [ $OVERALL_EXIT_CODE -eq 0 ]; then
    echo "🎉 EXACT CI SIMULATION COMPLETED SUCCESSFULLY"
    echo "📊 All phases passed:"
    echo "  ✅ Bandit Security Scanner"
    echo "  ✅ Semgrep Static Analysis"
    echo "  ✅ Pylint Code Quality"
    echo "  ✅ Ruff Linter & Formatter"
    echo "  ✅ MyPy Type Checking"
    echo "  ✅ All Tests (unit/integration)"
    echo "  ✅ pip-audit Dependency Scanner"
    echo "  ✅ Integration Tests (Server Startup)"
    echo ""
    echo "🚀 This code is ready for CI - all checks will pass"
else
    echo "❌ CI SIMULATION FAILED"
    echo "📊 Failed phases (${#FAILED_PHASES[@]} total):"
    for phase in "${FAILED_PHASES[@]}"; do
        echo "  ❌ $phase"
    done
    echo ""
    echo "🔧 Fix the above issues before pushing to CI"
fi

echo "⏰ Completed: $(date)"

# Cleanup (optional)
echo ""
echo "🧹 Generated reports in:"
echo "  📁 security-reports/"
echo "  📁 coverage-reports/"
echo ""

# Check for non-interactive mode via CI environment variable or command line
if [ "${CI:-false}" = "true" ] || [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
    # In CI environments, always clean up reports to keep runners clean
    rm -rf security-reports coverage-reports
    echo "✅ Reports cleaned up (CI mode)"
else
    # Interactive mode - ask user
    echo "Keep reports? (y/N): "
    read -r KEEP_REPORTS
    if [ "$KEEP_REPORTS" != "y" ] && [ "$KEEP_REPORTS" != "Y" ]; then
        rm -rf security-reports coverage-reports
        echo "✅ Reports cleaned up"
    else
        echo "📋 Reports preserved for review"
    fi
fi

# Exit with overall status
echo ""
if [ $OVERALL_EXIT_CODE -eq 0 ]; then
    echo "✅ CI simulation completed successfully"
else
    echo "❌ CI simulation failed with exit code: $OVERALL_EXIT_CODE"
fi

exit $OVERALL_EXIT_CODE
