#!/bin/bash
# Development Testing Script
# Quick testing script for development workflow

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

# Test configuration
RUN_UNIT_TESTS=true
RUN_INTEGRATION_TESTS=true
RUN_IMPORT_TEST=true
RUN_BASIC_VALIDATION=true
QUICK_MODE=false
COVERAGE_REPORT=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            RUN_INTEGRATION_TESTS=false
            RUN_BASIC_VALIDATION=false
            shift
            ;;
        --unit-only)
            RUN_UNIT_TESTS=true
            RUN_INTEGRATION_TESTS=false
            RUN_BASIC_VALIDATION=false
            shift
            ;;
        --integration-only)
            RUN_UNIT_TESTS=false
            RUN_INTEGRATION_TESTS=true
            RUN_BASIC_VALIDATION=false
            shift
            ;;
        --coverage)
            COVERAGE_REPORT=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Quick development testing script for iterative development."
            echo ""
            echo "Options:"
            echo "  --quick              Run only fast tests (unit tests + import check)"
            echo "  --unit-only          Run only unit tests"
            echo "  --integration-only   Run only integration tests"
            echo "  --coverage           Generate coverage report"
            echo "  --help, -h          Show this help message"
            echo ""
            echo "Default: Run all tests (unit, integration, import, basic validation)"
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

# Run a test and update exit code
run_test() {
    local test_name="$1"
    local command="$2"
    local success_msg="$3"
    local error_msg="$4"
    
    log_info "Running $test_name..."
    
    if eval "$command" > /tmp/dev_test_output 2>&1; then
        log_success "$success_msg"
        return 0
    else
        log_error "$error_msg"
        echo "Command output:"
        cat /tmp/dev_test_output
        echo
        EXIT_CODE=1
        return 1
    fi
}

# Initialize testing environment
init_testing() {
    log_section "🧪 FINOS AI Governance MCP Server - Development Testing"
    
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
    
    # Check for pytest
    if ! command_exists pytest; then
        log_error "pytest is not installed. Run 'pip install pytest' or scripts/dev-setup.sh"
        exit 1
    fi
    
    # Show test configuration
    echo
    echo "🎯 Test configuration:"
    echo "  Unit tests: $([ "$RUN_UNIT_TESTS" == true ] && echo "Yes" || echo "No")"
    echo "  Integration tests: $([ "$RUN_INTEGRATION_TESTS" == true ] && echo "Yes" || echo "No")"
    echo "  Import test: $([ "$RUN_IMPORT_TEST" == true ] && echo "Yes" || echo "No")"
    echo "  Basic validation: $([ "$RUN_BASIC_VALIDATION" == true ] && echo "Yes" || echo "No")"
    echo "  Coverage report: $([ "$COVERAGE_REPORT" == true ] && echo "Yes" || echo "No")"
    echo "  Quick mode: $([ "$QUICK_MODE" == true ] && echo "Yes" || echo "No")"
}

# Test package import
test_package_import() {
    if [[ "$RUN_IMPORT_TEST" != true ]]; then
        return 0
    fi
    
    log_section "📦 Package Import Test"
    
    run_test "Package import" \
        "python -c 'import finos_mcp; print(\"Package version:\", finos_mcp.__version__)'" \
        "Package imports successfully" \
        "Package import failed"
}

# Run unit tests
run_unit_tests() {
    if [[ "$RUN_UNIT_TESTS" != true ]]; then
        return 0
    fi
    
    log_section "🔬 Unit Tests"
    
    local pytest_cmd="pytest tests/unit/ -v"
    
    if [[ "$COVERAGE_REPORT" == true ]]; then
        pytest_cmd="$pytest_cmd --cov=finos_mcp --cov-report=term-missing"
    fi
    
    if [[ "$QUICK_MODE" == true ]]; then
        pytest_cmd="$pytest_cmd -x"  # Stop on first failure
    fi
    
    run_test "Unit tests" \
        "$pytest_cmd" \
        "Unit tests passed" \
        "Unit tests failed"
}

# Run integration tests
run_integration_tests() {
    if [[ "$RUN_INTEGRATION_TESTS" != true ]]; then
        return 0
    fi
    
    log_section "🔗 Integration Tests"
    
    local pytest_cmd="pytest tests/integration/ -v"
    
    if [[ "$QUICK_MODE" == true ]]; then
        pytest_cmd="$pytest_cmd -x"  # Stop on first failure
    fi
    
    # Check if simple test exists and run it first
    if [[ -f "tests/integration/simple_test.py" ]]; then
        run_test "Simple integration test" \
            "python tests/integration/simple_test.py" \
            "Simple integration test passed" \
            "Simple integration test failed"
    fi
    
    run_test "Integration tests" \
        "$pytest_cmd" \
        "Integration tests passed" \
        "Integration tests failed"
}

# Run basic validation
run_basic_validation() {
    if [[ "$RUN_BASIC_VALIDATION" != true ]]; then
        return 0
    fi
    
    log_section "✅ Basic Validation"
    
    # Test console script
    run_test "Console script availability" \
        "finos-mcp --help" \
        "Console script works" \
        "Console script failed"
    
    # Test configuration loading
    run_test "Configuration validation" \
        "python -c 'from finos_mcp.config import get_settings; get_settings(); print(\"Config OK\")'" \
        "Configuration loads successfully" \
        "Configuration loading failed"
    
    # Test basic server functionality (if available)
    if [[ -f "$PROJECT_ROOT/tests/run_stability_validation.py" ]]; then
        log_info "Running smoke test from stability validation..."
        if python "$PROJECT_ROOT/tests/run_stability_validation.py" --smoke > /tmp/smoke_test 2>&1; then
            log_success "Smoke test passed"
        else
            log_warning "Smoke test failed - check stability validation"
            if [[ $(wc -l < /tmp/smoke_test) -lt 50 ]]; then
                cat /tmp/smoke_test
            fi
        fi
    fi
}

# Generate coverage report if requested
generate_coverage_report() {
    if [[ "$COVERAGE_REPORT" != true ]]; then
        return 0
    fi
    
    log_section "📊 Coverage Report"
    
    if command_exists coverage; then
        log_info "Generating HTML coverage report..."
        coverage html --directory=htmlcov
        log_success "Coverage report generated at htmlcov/index.html"
        
        # Show coverage summary
        if coverage report > /tmp/coverage_summary 2>&1; then
            echo
            echo "Coverage Summary:"
            tail -n 5 /tmp/coverage_summary
        fi
    else
        log_warning "Coverage tool not available. Install with: pip install coverage"
    fi
}

# Show development workflow suggestions
show_development_tips() {
    log_section "💡 Development Workflow Tips"
    
    echo "🚀 Quick development iteration:"
    echo "  1. Make your changes"
    echo "  2. Run: ./scripts/dev-test.sh --quick"
    echo "  3. Fix any issues"
    echo "  4. Run full tests: ./scripts/dev-test.sh"
    echo "  5. Quality check: ./scripts/quality-check.sh"
    echo
    echo "🔧 Useful commands:"
    echo "  • Quick tests: ./scripts/dev-test.sh --quick"
    echo "  • Unit tests only: ./scripts/dev-test.sh --unit-only"
    echo "  • With coverage: ./scripts/dev-test.sh --coverage"
    echo "  • Quality check: ./scripts/quality-check.sh"
    echo "  • Clean environment: ./scripts/clean.sh"
    echo
    echo "📁 Test organization:"
    echo "  • Unit tests: tests/unit/"
    echo "  • Integration tests: tests/integration/"
    echo "  • Stability tests: tests/run_stability_validation.py"
}

# Print test summary
print_test_summary() {
    echo
    log_section "📋 Development Test Summary"
    
    local duration="$SECONDS"
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    if [[ $EXIT_CODE -eq 0 ]]; then
        echo -e "${GREEN}🎉 ALL DEVELOPMENT TESTS PASSED!${NC}"
        echo
        echo "✅ Tests completed successfully in ${minutes}m ${seconds}s"
        echo
        echo "Test results:"
        echo "  • Package import: $([ "$RUN_IMPORT_TEST" == true ] && echo "✅ Passed" || echo "⏭️  Skipped")"
        echo "  • Unit tests: $([ "$RUN_UNIT_TESTS" == true ] && echo "✅ Passed" || echo "⏭️  Skipped")"
        echo "  • Integration tests: $([ "$RUN_INTEGRATION_TESTS" == true ] && echo "✅ Passed" || echo "⏭️  Skipped")"
        echo "  • Basic validation: $([ "$RUN_BASIC_VALIDATION" == true ] && echo "✅ Passed" || echo "⏭️  Skipped")"
        echo
        echo -e "${GREEN}🚀 Ready for development! Your changes are working correctly.${NC}"
        
        # Show next steps based on what was run
        if [[ "$QUICK_MODE" == true ]]; then
            echo
            echo "💡 Quick test completed. Consider running full test suite:"
            echo "   ./scripts/dev-test.sh"
        fi
    else
        echo -e "${RED}❌ DEVELOPMENT TESTS FAILED${NC}"
        echo
        echo "Some tests did not pass. Please review the output above"
        echo "and fix the issues before proceeding."
        echo
        echo "🔧 Debugging tips:"
        echo "  • Check individual test output for specific failures"
        echo "  • Run tests in isolation: pytest tests/unit/test_specific.py -v"
        echo "  • Use debugger: pytest --pdb"
        echo "  • Check logs and error messages carefully"
    fi
    
    show_development_tips
}

# Clean up temporary files
cleanup() {
    rm -f /tmp/dev_test_output /tmp/smoke_test /tmp/coverage_summary
}

# Main execution
main() {
    # Record start time
    local start_time=$SECONDS
    
    # Set up cleanup on exit
    trap cleanup EXIT
    
    init_testing
    
    # Run all requested tests
    test_package_import
    run_unit_tests
    run_integration_tests
    run_basic_validation
    generate_coverage_report
    
    # Calculate duration
    SECONDS=$start_time
    print_test_summary
    
    exit $EXIT_CODE
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi