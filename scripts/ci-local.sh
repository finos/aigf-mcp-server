#!/usr/bin/env bash

# Local CI Simulation Script
# Runs the exact same sequence as GitHub Actions CI
# This prevents local vs CI discrepancies

set -e  # Exit on any failure

echo "🚀 Running LOCAL CI SIMULATION"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Linting (exact match to CI)
echo -e "${BLUE}🔍 STEP 1: Ruff Linting${NC}"
echo "Running: ruff check . --output-format=github"
.venv/bin/ruff check . --output-format=github
echo -e "${GREEN}✅ Linting passed${NC}"
echo

# Step 2: Formatting (exact match to CI)
echo -e "${BLUE}🎨 STEP 2: Ruff Formatting${NC}"
echo "Running: ruff format --check ."
.venv/bin/ruff format --check .
echo -e "${GREEN}✅ Formatting passed${NC}"
echo

# Step 3: Type Checking (exact match to CI)
echo -e "${BLUE}🔬 STEP 3: MyPy Type Checking${NC}"
echo "Running: mypy src/ --show-error-codes"
.venv/bin/mypy src/ --show-error-codes
echo -e "${GREEN}✅ Type checking passed${NC}"
echo

# Step 4: Security Scan (exact match to CI)
echo -e "${BLUE}🔒 STEP 4: Bandit Security Scan${NC}"
echo "Running: bandit -r src/ -f txt"
.venv/bin/bandit -r src/ -f txt
echo -e "${GREEN}✅ Security scan passed${NC}"
echo

# Step 5: Tests with Coverage (exact match to CI)
echo -e "${BLUE}🧪 STEP 5: Tests with Coverage${NC}"
echo "Running: pytest --cov=finos_mcp --cov-report=term-missing --cov-report=xml --cov-fail-under=70 -v"
.venv/bin/pytest --cov=finos_mcp --cov-report=term-missing --cov-report=xml --cov-fail-under=70 -v
echo -e "${GREEN}✅ Tests with coverage passed${NC}"
echo

# Step 6: Stability Validation (from test matrix)
echo -e "${BLUE}🛡️  STEP 6: Stability Validation${NC}"
echo "Running: python tests/run_stability_validation.py"
.venv/bin/python tests/run_stability_validation.py
echo -e "${GREEN}✅ Stability validation passed${NC}"
echo

echo "================================"
echo -e "${GREEN}🎉 ALL CI STEPS PASSED LOCALLY!${NC}"
echo -e "${GREEN}✅ Your code should now pass GitHub Actions CI${NC}"
echo "================================"
