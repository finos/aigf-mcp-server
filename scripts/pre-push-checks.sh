#!/bin/bash
# Pre-push CI checks script
# Run this before pushing to catch issues early

set -e

echo "🚀 Running pre-push CI checks..."
echo "=================================="

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Not in a git repository"
    exit 1
fi

# Check if virtual environment exists
if [[ ! -d ".venv" ]]; then
    echo "❌ Virtual environment not found. Run: python -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

echo "📋 1. Running Ruff linter..."
echo "----------------------------"
if ! .venv/bin/ruff check src/ tests/ scripts/ --quiet; then
    echo "❌ Ruff linting failed"
    echo "💡 Run: .venv/bin/ruff check src/ tests/ scripts/ --fix"
    exit 1
fi
echo "✅ Ruff linting passed"

echo ""
echo "🔧 2. Running Ruff formatter..."
echo "------------------------------"
if ! .venv/bin/ruff format --check src/ tests/ scripts/; then
    echo "❌ Code formatting issues found"
    echo "💡 Run: .venv/bin/ruff format src/ tests/ scripts/"
    exit 1
fi
echo "✅ Code formatting passed"

echo ""
echo "🏃 3. Running critical tests..."
echo "------------------------------"
if ! .venv/bin/python -m pytest tests/unit/test_tools.py -v --tb=short --disable-warnings; then
    echo "❌ Critical tests failed"
    exit 1
fi
echo "✅ Critical tests passed"

echo ""
echo "🔍 4. Running MyPy on main tools..."
echo "----------------------------------"
if ! .venv/bin/mypy src/finos_mcp/tools/ --ignore-missing-imports --no-strict-optional; then
    echo "⚠️  MyPy found type issues in main tools"
    echo "💡 Fix critical type errors before pushing"
    # Don't fail for now, just warn
fi

echo ""
echo "🛡️  5. Running security checks..."
echo "--------------------------------"
if ! .venv/bin/bandit -r src/ -f json -o /tmp/bandit-report.json --quiet; then
    echo "❌ Security issues found"
    echo "💡 Check bandit report for details"
    exit 1
fi
echo "✅ Security checks passed"

echo ""
echo "🎉 All critical pre-push checks passed!"
echo "Ready to commit and push safely."
echo ""
echo "💡 To run full CI simulation: ./scripts/ci-exact-simulation.sh"
