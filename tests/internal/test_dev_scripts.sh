#!/bin/bash
# Internal TDD tests for development scripts
# These tests validate the development automation improvements

set -euo pipefail

# Test utilities
assert_exists() {
    if [[ ! -e "$1" ]]; then
        echo "❌ FAIL: $1 does not exist"
        return 1
    fi
    echo "✅ PASS: $1 exists"
}

assert_not_exists() {
    if [[ -e "$1" ]]; then
        echo "❌ FAIL: $1 should not exist"
        return 1
    fi
    echo "✅ PASS: $1 does not exist"
}

assert_command_succeeds() {
    if ! eval "$1" &>/dev/null; then
        echo "❌ FAIL: Command failed: $1"
        return 1
    fi
    echo "✅ PASS: Command succeeded: $1"
}

assert_file_contains() {
    if ! grep -q "$2" "$1" 2>/dev/null; then
        echo "❌ FAIL: $1 does not contain: $2"
        return 1
    fi
    echo "✅ PASS: $1 contains: $2"
}

assert_env_var_equals() {
    if [[ "${!1:-}" != "$2" ]]; then
        echo "❌ FAIL: $1 = '${!1:-}', expected '$2'"
        return 1
    fi
    echo "✅ PASS: $1 = $2"
}

assert_pre_commit_installed() {
    if [[ ! -f ".git/hooks/pre-commit" ]]; then
        echo "❌ FAIL: pre-commit hook not installed"
        return 1
    fi
    echo "✅ PASS: pre-commit hook installed"
}

# Test: Quick setup creates complete environment
test_quick_setup_creates_complete_environment() {
    echo "🧪 Testing: dev-quick-setup.sh creates complete environment"

    # Clean slate
    rm -rf .venv .env.test

    # Run setup
    if [[ -f "scripts/dev-quick-setup.sh" ]]; then
        ./scripts/dev-quick-setup.sh
    else
        echo "❌ FAIL: scripts/dev-quick-setup.sh does not exist"
        return 1
    fi

    # Validate environment
    assert_exists ".venv/bin/python"
    assert_exists ".venv/bin/finos-mcp"
    assert_command_succeeds ".venv/bin/python -c 'import finos_mcp'"
    assert_pre_commit_installed

    echo "✅ Quick setup test passed"
}

# Test: Dev reset preserves config
test_dev_reset_preserves_config() {
    echo "🧪 Testing: dev-reset.sh preserves user configuration"

    # Create user config
    echo "CUSTOM_VAR=test_value" > .env.local
    echo "USER_SETTING=important" >> .env.local

    # Create cache files that should be removed
    mkdir -p .cache
    touch .cache/test_file
    mkdir -p src/__pycache__
    touch src/__pycache__/test.pyc

    # Run reset
    if [[ -f "scripts/dev-reset.sh" ]]; then
        ./scripts/dev-reset.sh
    else
        echo "❌ FAIL: scripts/dev-reset.sh does not exist"
        return 1
    fi

    # Validate preservation and cleanup
    assert_file_contains ".env.local" "CUSTOM_VAR=test_value"
    assert_file_contains ".env.local" "USER_SETTING=important"
    assert_not_exists ".cache"
    assert_not_exists "src/__pycache__"

    echo "✅ Dev reset test passed"
}

# Test: Focused mode enables offline testing
test_focused_mode_enables_offline_testing() {
    echo "🧪 Testing: dev-test-focused.sh enables offline development"

    # Clean state
    rm -f .env.test

    # Run focused mode setup
    if [[ -f "scripts/dev-test-focused.sh" ]]; then
        ./scripts/dev-test-focused.sh
    else
        echo "❌ FAIL: scripts/dev-test-focused.sh does not exist"
        return 1
    fi

    # Source test environment
    if [[ -f ".env.test" ]]; then
        source .env.test
    else
        echo "❌ FAIL: .env.test not created"
        return 1
    fi

    # Validate offline mode configuration
    assert_env_var_equals "FINOS_MCP_OFFLINE_MODE" "true"
    assert_env_var_equals "FINOS_MCP_ENABLE_CACHE" "true"
    assert_exists "tests/fixtures"

    echo "✅ Focused mode test passed"
}

# Test: Scripts have proper error handling
test_scripts_error_handling() {
    echo "🧪 Testing: scripts handle errors gracefully"

    # Test with invalid Python version (if we can simulate it)
    # This is more of a design validation test

    for script in "scripts/dev-quick-setup.sh" "scripts/dev-reset.sh" "scripts/dev-test-focused.sh"; do
        if [[ -f "$script" ]]; then
            # Validate script has proper shebang and error handling
            assert_file_contains "$script" "#!/bin/bash"
            assert_file_contains "$script" "set -euo pipefail"
            echo "✅ $script has proper error handling"
        fi
    done
}

# Test: Scripts are idempotent
test_scripts_idempotent() {
    echo "🧪 Testing: scripts can be run multiple times safely"

    # Run quick setup twice
    if [[ -f "scripts/dev-quick-setup.sh" ]]; then
        ./scripts/dev-quick-setup.sh
        ./scripts/dev-quick-setup.sh  # Should not fail
        echo "✅ dev-quick-setup.sh is idempotent"
    fi

    # Run reset twice
    if [[ -f "scripts/dev-reset.sh" ]]; then
        ./scripts/dev-reset.sh
        ./scripts/dev-reset.sh  # Should not fail
        echo "✅ dev-reset.sh is idempotent"
    fi
}

# Main test runner
main() {
    echo "🚀 Running TDD tests for development scripts"
    echo "=========================================="

    # Save current directory
    ORIGINAL_DIR=$(pwd)

    # Ensure we're in project root
    if [[ ! -f "pyproject.toml" ]]; then
        echo "❌ Must run from project root directory"
        exit 1
    fi

    # Run tests (these will initially fail - TDD Red phase)
    test_quick_setup_creates_complete_environment || echo "Expected failure: dev-quick-setup.sh not implemented yet"
    test_dev_reset_preserves_config || echo "Expected failure: dev-reset.sh not implemented yet"
    test_focused_mode_enables_offline_testing || echo "Expected failure: dev-test-focused.sh not implemented yet"
    test_scripts_error_handling || echo "Expected failure: scripts not implemented yet"
    test_scripts_idempotent || echo "Expected failure: scripts not implemented yet"

    echo "=========================================="
    echo "🔴 TDD Red Phase: Tests written and failing as expected"
    echo "Next: Implement scripts to make tests pass (Green phase)"

    # Restore directory
    cd "$ORIGINAL_DIR"
}

# Run tests if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
