#!/bin/bash
# 🎯 EXACT CI SIMULATION SCRIPT
# This script runs the IDENTICAL commands that GitHub Actions CI runs
# to prevent local/CI validation mismatches

set -e  # Exit on any error

echo "🔍 EXACT CI SIMULATION - FINOS MCP Server"
echo "=========================================="
echo "📍 Location: $(pwd)"
echo "🐍 Python: $(python --version)"
echo "⏰ Started: $(date)"
echo ""

# Ensure we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "src/finos_mcp" ]; then
    echo "❌ ERROR: Must run from project root directory"
    echo "Expected: /Users/hugocalderon/SRC/IA-FINOS"
    exit 1
fi

# Ensure virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ ERROR: Virtual environment not activated"
    echo "Run: source .venv/bin/activate"
    exit 1
fi

# Install CI-specific dependencies that may not be in local environment
echo "📦 Installing CI-specific dependencies..."
pip install lxml > /dev/null 2>&1 || echo "⚠️  lxml installation failed - some CI reports may not work"

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
semgrep --config config/security/semgrep.yml src/ \
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
python -m pylint src/ \
  --output-format=json \
  --reports=yes \
  --score=yes > security-reports/pylint-report.json

# Pylint will exit with non-zero code if score < fail-under (8.5) - EXACT CI LOGIC
PYLINT_EXIT_CODE=$?

if [ $PYLINT_EXIT_CODE -ne 0 ]; then
  echo "❌ CRITICAL: Pylint score below 8.5 threshold (exit code: $PYLINT_EXIT_CODE)"
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
ruff check src/ tests/ scripts/ --output-format=json > security-reports/ruff-report.json

# Count the number of issues found (EXACT CI LOGIC)
RUFF_ISSUES=$(jq 'length' security-reports/ruff-report.json)
echo "Ruff found $RUFF_ISSUES linting issues"

# Check formatting (EXACT CI COMMAND)
echo "Checking code formatting with Ruff..."
ruff format --check src/ tests/ scripts/

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
# PHASE 6: UNIT TESTS (EXACT CI COMMAND)
# =============================================================================
echo ""
echo "🧪 PHASE 6: Unit Tests (EXACT CI COMMAND)"
echo "----------------------------------------"

echo "Running unit tests..."
if [ -d "tests" ]; then
  python -m pytest tests/ \
    --cov=src/finos_mcp \
    --cov-report=json:coverage-reports/coverage.json \
    --cov-report=xml:coverage-reports/coverage.xml \
    --cov-report=html:coverage-reports/html \
    --junit-xml=coverage-reports/pytest.xml \
    --cov-fail-under=65 \
    -v
else
  echo "⚠️  No tests directory found - skipping tests"
fi

echo "✅ Unit tests passed"

# =============================================================================
# FINAL VALIDATION SUMMARY
# =============================================================================
echo ""
echo "🎉 EXACT CI SIMULATION COMPLETED SUCCESSFULLY"
echo "============================================="
echo "📊 All phases passed:"
echo "  ✅ Bandit Security Scanner"
echo "  ✅ Semgrep Static Analysis"
echo "  ✅ Pylint Code Quality"
echo "  ✅ Ruff Linter & Formatter"
echo "  ✅ MyPy Type Checking"
echo "  ✅ Unit Tests"
echo ""
echo "🚀 This code is ready for CI - all checks will pass"
echo "⏰ Completed: $(date)"

# Cleanup (optional)
echo ""
echo "🧹 Generated reports in:"
echo "  📁 security-reports/"
echo "  📁 coverage-reports/"
echo ""
echo "Keep reports? (y/N): "
read -r KEEP_REPORTS
if [ "$KEEP_REPORTS" != "y" ] && [ "$KEEP_REPORTS" != "Y" ]; then
    rm -rf security-reports coverage-reports
    echo "✅ Reports cleaned up"
else
    echo "📋 Reports preserved for review"
fi
