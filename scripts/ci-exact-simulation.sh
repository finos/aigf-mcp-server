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
    exit 1
fi

# One interpreter, resolved the way every other gate resolves it. This block
# used to `source .venv/bin/activate` or die -- but ci-local.sh defaults to
# venv/ and docs/development.md documents venv/, so the script whose entire purpose
# is CI parity demanded a virtualenv the documented setup never creates. Every
# phase below then invoked a bare `python`, which does not exist on macOS at
# all, so on the maintainer's own platform this script could not run a single
# gate (#56).
if ! PYTHON_BIN="$(./scripts/project-python.sh --print-interpreter)"; then
    exit 1
fi
export PYTHON_BIN

echo "🐍 Python: $("$PYTHON_BIN" --version) ($PYTHON_BIN)"
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
"$PYTHON_BIN" -m bandit -c config/security/bandit.yml -r src/ \
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
"$PYTHON_BIN" -m pylint src/ \
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
echo "COMMAND: mypy --show-error-codes --show-error-context --txt-report security-reports/mypy-report"
echo ""

# THIS IS THE EXACT COMMAND THAT CI RUNS - THE ONE THAT WAS FAILING
"$PYTHON_BIN" -m mypy \
  --show-error-codes \
  --show-error-context \
  --txt-report security-reports/mypy-report

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
  "$PYTHON_BIN" -m pytest \
    --cov=src/finos_mcp \
    --cov-report=json:coverage-reports/coverage.json \
    --cov-report=xml:coverage-reports/coverage.xml \
    --cov-report=html:coverage-reports/html \
    --junit-xml=coverage-reports/pytest.xml \
    --tb=short \
    --quiet

  # Show summary of test results
  PYTEST_EXIT_CODE=$?
  set -e  # Re-enable exit on error

  if [ $PYTEST_EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed successfully"

    # Coverage is read only by scripts/coverage-summary.sh. A call site that
    # can obtain the number can enforce a floor with it, which is how a second
    # floor of 75 came to sit alongside pyproject.toml's 82;
    # tests/unit/test_ci_config_drift.py forbids the read here.
    echo "📊 Test Coverage: $(./scripts/coverage-summary.sh coverage-reports/coverage.json)"
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

# Run pip-audit scan - fail on any known vulnerabilities.
# This block previously listed a subset of the flags it actually passed, while
# claiming to be the EXACT CI COMMAND. Both this script and the workflow now
# call the same wrapper, so there is no second copy left to fall out of date.
./scripts/pip-audit-scan.sh \
  --format json --output security-reports/pip-audit-report.json

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
"$PYTHON_BIN" -c "
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
# PHASE 9: PRE-COMMIT HOOKS (EXACT CI COMMAND)
# =============================================================================
echo ""
echo "🪝 PHASE 9: Pre-commit Hooks (EXACT CI COMMAND)"
echo "----------------------------------------------"

# Mirrors the `pre-commit` job in .github/workflows/security-analysis.yml.
# Nothing ran the hooks in CI before that job existed, which is how a semgrep
# hook that could not start and a detect-secrets hook that always failed both
# reached main. The hooks that matter most here are the ones with no phase
# above -- detect-secrets, end-of-file-fixer, check-yaml, check-toml and the
# Claude-content blockers -- every tool hook is repo: local + language: system
# and re-runs the same tools the earlier phases already used.
echo "Running pre-commit hooks..."
set +e  # Temporarily disable exit on error to capture the pre-commit exit code
"$PYTHON_BIN" -m pre_commit run --all-files
PRE_COMMIT_EXIT_CODE=$?
set -e  # Re-enable exit on error

if [ $PRE_COMMIT_EXIT_CODE -ne 0 ]; then
  handle_phase_error "Pre-commit Hooks" $PRE_COMMIT_EXIT_CODE
else
  echo "✅ Pre-commit hooks passed"
fi

# =============================================================================
# PHASE 10: FUNCTIONAL GATE (EXACT CI COMMAND)
# =============================================================================
echo ""
echo "🎯 PHASE 10: Functional Gate (EXACT CI COMMAND)"
echo "----------------------------------------------"

# Mirrors the functional-gate job in .github/workflows/security-analysis.yml.
echo "Running the live functional suite..."
set +e  # Temporarily disable exit on error to capture the exit code
FINOS_RUN_LIVE_MCP_TEST=1 FINOS_RUN_AUTH_HTTP_TEST=1 "$PYTHON_BIN" -m pytest -q tests/integration/test_live_mcp_server.py tests/integration/test_auth_http_transport.py
FUNCTIONAL_GATE_EXIT_CODE=$?
set -e  # Re-enable exit on error

if [ $FUNCTIONAL_GATE_EXIT_CODE -ne 0 ]; then
  handle_phase_error "Functional Gate" $FUNCTIONAL_GATE_EXIT_CODE
  echo "  If the failure names 'static_fallback' or 'expired_cache', the cause is the"
  echo "  unauthenticated GitHub rate limit rather than a code defect."
else
  echo "✅ Functional gate passed"
fi

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
    echo "  ✅ Pre-commit Hooks"
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
