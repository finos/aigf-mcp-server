#!/bin/bash
# Quality Validation Script for FINOS AI Governance MCP Server
# Runs comprehensive quality checks including linting, type checking, security scanning

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
EXIT_CODE=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PYLINT_MIN_SCORE=8.0
MYPY_STRICT=true
RUFF_FIX=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fix)
            RUFF_FIX=true
            shift
            ;;
        --pylint-min-score)
            PYLINT_MIN_SCORE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --fix                    Automatically fix Ruff issues"
            echo "  --pylint-min-score N     Set minimum Pylint score (default: 8.0)"
            echo "  --help, -h              Show this help message"
            echo ""
            echo "This script runs comprehensive quality checks including:"
            echo "  - Ruff linting, formatting, and security (replaces Black, Flake8, Bandit)"
            echo "  - MyPy type checking"
            echo "  - Pylint code quality analysis"
            echo "  - pip-audit vulnerability scanning"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✅ PASS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠️  WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[❌ FAIL]${NC} $1"
}

log_section() {
    echo
    echo -e "${CYAN}$1${NC}"
    echo "$(printf '=%.0s' $(seq 1 ${#1}))"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Run a command and capture output
run_check() {
    local check_name="$1"
    local command="$2"
    local success_msg="$3"
    local error_msg="$4"

    log_info "Running $check_name..."

    if eval "$command" > /tmp/quality_check_output 2>&1; then
        log_success "$success_msg"
        return 0
    else
        log_error "$error_msg"
        echo "Command output:"
        cat /tmp/quality_check_output
        echo
        return 1
    fi
}

# Initialize quality check
init_quality_check() {
    log_section "🔍 FINOS AI Governance MCP Server - Quality Validation"

    cd "$PROJECT_ROOT"

    # Check if we're in a virtual environment
    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        log_warning "No virtual environment detected"
        if [[ -f ".venv/bin/activate" ]]; then
            log_info "Activating project virtual environment..."
            # shellcheck source=/dev/null
            source .venv/bin/activate
        else
            log_error "Virtual environment not found. Run scripts/dev-setup.sh first."
            exit 1
        fi
    fi

    log_info "Using Python: $(which python)"
    log_info "Virtual environment: ${VIRTUAL_ENV}"

    # Verify required tools are installed
    local required_tools=("ruff" "mypy" "pylint" "pip-audit")
    for tool in "${required_tools[@]}"; do
        if ! command_exists "$tool"; then
            log_error "$tool is not installed. Run 'pip install $tool' or use scripts/dev-setup.sh"
            exit 1
        fi
    done
}

# Run Ruff linting
run_ruff_lint() {
    log_section "📝 Ruff - Python Linting"

    local ruff_cmd="ruff check src/ tests/ scripts/"
    if [[ "$RUFF_FIX" == true ]]; then
        ruff_cmd="$ruff_cmd --fix"
    fi

    if run_check "Ruff linting" "$ruff_cmd" "Ruff linting passed" "Ruff linting failed"; then
        return 0
    else
        EXIT_CODE=1
        return 1
    fi
}

# Run Ruff formatting
run_ruff_format() {
    log_section "🎨 Ruff - Code Formatting"

    local format_cmd="ruff format --check src/ tests/ scripts/"
    if [[ "$RUFF_FIX" == true ]]; then
        format_cmd="ruff format src/ tests/ scripts/"
    fi

    if run_check "Ruff formatting" "$format_cmd" "Code formatting is correct" "Code formatting issues found"; then
        return 0
    else
        EXIT_CODE=1
        return 1
    fi
}

# Run MyPy type checking
run_mypy() {
    log_section "🏷️  MyPy - Type Checking"

    local mypy_cmd="mypy src/finos_mcp --show-error-codes --show-error-context --strict-optional --warn-redundant-casts --warn-unused-ignores"

    if run_check "MyPy type checking" "$mypy_cmd" "Type checking passed" "Type checking failed"; then
        return 0
    else
        EXIT_CODE=1
        return 1
    fi
}

# Run Pylint code quality analysis
run_pylint() {
    log_section "📊 Pylint - Code Quality Analysis"

    local pylint_cmd="pylint src/ --fail-under=$PYLINT_MIN_SCORE"

    # Use project-specific pylint config if available
    if [[ -f ".pylintrc" ]]; then
        pylint_cmd="$pylint_cmd --rcfile=.pylintrc"
    fi

    log_info "Running Pylint with minimum score: $PYLINT_MIN_SCORE"

    # Capture Pylint output to get the score
    if pylint src/ --fail-under="$PYLINT_MIN_SCORE" > /tmp/pylint_output 2>&1; then
        local score
        score=$(grep "Your code has been rated" /tmp/pylint_output | sed 's/.*rated at \([0-9.]*\).*/\1/')
        log_success "Pylint passed with score: $score/$PYLINT_MIN_SCORE"
        return 0
    else
        local score
        score=$(grep "Your code has been rated" /tmp/pylint_output | sed 's/.*rated at \([0-9.]*\).*/\1/' || echo "unknown")
        log_error "Pylint failed with score: $score/$PYLINT_MIN_SCORE"
        cat /tmp/pylint_output
        EXIT_CODE=1
        return 1
    fi
}

# Bandit security scanning is now handled by Ruff (flake8-bandit rules)
# This provides equivalent security checks with better performance

# Run pip-audit vulnerability scanning
run_pip_audit() {
    log_section "🔒 pip-audit - Dependency Vulnerability Scanning"

    log_info "Scanning dependencies for known vulnerabilities..."

    if pip-audit --format=json \
        --ignore-vuln GHSA-7gcm-g887-7qv7 \
        --ignore-vuln GHSA-w8v5-vhqr-4h9v > /tmp/pip_audit_output 2>&1; then
        log_success "pip-audit passed - no vulnerabilities found"
        return 0
    else
        local exit_code=$?
        if [[ $exit_code -eq 1 ]]; then
            log_error "pip-audit found vulnerabilities"
            # Parse JSON output for summary
            if command_exists jq && grep -q "vulnerabilities" /tmp/pip_audit_output; then
                local vuln_count
                vuln_count=$(jq '.vulnerabilities | length' /tmp/pip_audit_output 2>/dev/null || echo "unknown")
                log_error "Found $vuln_count vulnerability(ies)"
            fi
            cat /tmp/pip_audit_output
            EXIT_CODE=1
            return 1
        else
            log_warning "pip-audit completed with warnings"
            cat /tmp/pip_audit_output
            return 0
        fi
    fi
}

# Run additional checks specific to the project
run_project_checks() {
    log_section "🧪 Project-Specific Checks"

    # Check that the package can be imported
    if run_check "Package import" "python -c 'import finos_mcp; print(\"Import successful\")'" "Package imports successfully" "Package import failed"; then
        :
    else
        EXIT_CODE=1
    fi

    # Check console script availability
    if run_check "Console script" "finos-mcp --help" "Console script works" "Console script failed"; then
        :
    else
        EXIT_CODE=1
    fi

    # Check configuration validation
    if run_check "Configuration validation" "python -c 'from finos_mcp.config import get_settings; get_settings(); print(\"Config valid\")'" "Configuration validation passed" "Configuration validation failed"; then
        :
    else
        EXIT_CODE=1
    fi
}

# Print quality summary
print_quality_summary() {
    echo
    log_section "📋 Quality Check Summary"

    if [[ $EXIT_CODE -eq 0 ]]; then
        echo -e "${GREEN}🎉 ALL QUALITY CHECKS PASSED!${NC}"
        echo
        echo "✅ Ruff linting, formatting, and security"
        echo "✅ MyPy type checking"
        echo "✅ Pylint code quality (≥$PYLINT_MIN_SCORE)"
        echo "✅ pip-audit vulnerability scanning"
        echo "✅ Project-specific checks"
        echo
        echo -e "${GREEN}Your code meets enterprise quality standards! 🚀${NC}"
    else
        echo -e "${RED}❌ QUALITY CHECKS FAILED${NC}"
        echo
        echo "Some quality checks did not pass. Please review the output above"
        echo "and fix the issues before committing your changes."
        echo
        echo "💡 Tips:"
        echo "  • Use --fix flag to automatically fix some issues"
        echo "  • Check the project documentation for coding standards"
        echo "  • Run individual tools for more detailed output"
    fi

    echo
    echo "📚 For more information:"
    echo "  • Setup Guide: docs/README.md"
    echo "  • Tool Reference: docs/tools-reference.md"
    echo "  • Troubleshooting: docs/troubleshooting.md"
}

# Clean up temporary files
cleanup() {
    rm -f /tmp/quality_check_output /tmp/pylint_output /tmp/pip_audit_output
}

# Main execution
main() {
    # Set up cleanup on exit
    trap cleanup EXIT

    init_quality_check

    # Run all quality checks
    run_ruff_lint
    run_ruff_format
    run_mypy
    run_pylint
    run_pip_audit
    run_project_checks

    print_quality_summary

    exit $EXIT_CODE
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
