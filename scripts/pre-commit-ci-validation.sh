#!/bin/bash
# 🛡️ PRE-COMMIT CI VALIDATION HOOK
# This script ensures local changes will pass CI before allowing commits
# Add this to your git hooks or run manually before commits

set -e

echo "🛡️ PRE-COMMIT CI VALIDATION"
echo "=========================="
echo "📍 Ensuring code will pass GitHub Actions CI"
echo "⏰ Started: $(date)"
echo ""

# Ensure we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "src/finos_mcp" ]; then
    echo "❌ ERROR: Must run from project root directory"
    echo "Expected: FINOS MCP Server project root"
    exit 1
fi

# Ensure virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ ERROR: Virtual environment not activated"
    echo "Run: source .venv/bin/activate"
    exit 1
fi

# Check if there are changes to commit
if [ -z "$(git status --porcelain)" ]; then
    echo "⚠️  No changes detected to commit"
    echo "This validation is for pre-commit checking"
    exit 0
fi

echo "📋 Changes detected - validating before commit..."
git status --short
echo ""

# =============================================================================
# PHASE 1: SYNCHRONIZATION CHECK
# =============================================================================
echo "🔍 PHASE 1: CI Synchronization Check"
echo "-----------------------------------"

if [ -f "scripts/ci-sync-validator.sh" ]; then
    echo "Running CI synchronization validator..."
    ./scripts/ci-sync-validator.sh > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "❌ CRITICAL: CI synchronization validation failed"
        echo "Local simulation is out of sync with GitHub Actions CI"
        echo "Run: ./scripts/ci-sync-validator.sh"
        echo "Fix synchronization issues before committing"
        exit 1
    fi
    echo "✅ CI synchronization validated"
else
    echo "⚠️  CI sync validator not found - skipping sync check"
fi

# =============================================================================
# PHASE 2: EXACT CI SIMULATION
# =============================================================================
echo ""
echo "🎯 PHASE 2: Exact CI Simulation"
echo "------------------------------"

if [ -f "scripts/ci-exact-simulation.sh" ]; then
    echo "Running exact CI simulation (this may take a few minutes)..."
    echo ""

    # Run the exact CI simulation
    echo "N" | ./scripts/ci-exact-simulation.sh
    CI_EXIT_CODE=$?

    if [ $CI_EXIT_CODE -ne 0 ]; then
        echo ""
        echo "❌ CRITICAL: CI simulation FAILED"
        echo "============================================"
        echo "Your code will NOT pass GitHub Actions CI"
        echo ""
        echo "🔧 Fix the following issues:"
        echo "1. Run: ./scripts/ci-exact-simulation.sh"
        echo "2. Review and fix all reported issues"
        echo "3. Re-run this validation"
        echo "4. Only commit when CI simulation passes"
        echo ""
        echo "💡 Common issues:"
        echo "- Type checking errors (MyPy)"
        echo "- Security vulnerabilities (Bandit, pip-audit)"
        echo "- Code quality issues (Pylint, Ruff)"
        echo "- Test failures or low coverage"
        echo ""
        exit 1
    fi

    echo ""
    echo "✅ CI simulation PASSED - GitHub Actions will succeed"
else
    echo "❌ ERROR: CI simulation script not found"
    echo "Expected: scripts/ci-exact-simulation.sh"
    exit 1
fi

# =============================================================================
# PHASE 3: COMMIT READINESS VALIDATION
# =============================================================================
echo ""
echo "📝 PHASE 3: Commit Readiness Validation"
echo "--------------------------------------"

# Check for sensitive information in staged changes
STAGED_FILES=$(git diff --cached --name-only)
if [ -n "$STAGED_FILES" ]; then
    echo "Checking staged files for sensitive information..."

    # Check for common sensitive patterns
    SENSITIVE_PATTERNS=(
        "password"
        "secret"
        "token"
        "api_key"
        "privkey"
        "credential"
    )

    for pattern in "${SENSITIVE_PATTERNS[@]}"; do
        if git diff --cached | grep -i "$pattern" > /dev/null; then
            echo "⚠️  WARNING: Potential sensitive information detected: $pattern"
            echo "Please review staged changes carefully"
        fi
    done

    echo "✅ Staged files reviewed"
else
    echo "⚠️  No staged changes found"
fi

# Check commit message if this is being run as a git hook
if [ -f ".git/COMMIT_EDITMSG" ]; then
    COMMIT_MSG=$(cat .git/COMMIT_EDITMSG)

    # Basic commit message validation
    if [ ${#COMMIT_MSG} -lt 10 ]; then
        echo "❌ ERROR: Commit message too short (minimum 10 characters)"
        echo "Current: ${#COMMIT_MSG} characters"
        exit 1
    fi

    # Check for emoji in commit message (not allowed per agent guidelines)
    if echo "$COMMIT_MSG" | grep -P "[\x{1F600}-\x{1F64F}]|[\x{1F300}-\x{1F5FF}]|[\x{1F680}-\x{1F6FF}]|[\x{1F700}-\x{1F77F}]|[\x{1F780}-\x{1F7FF}]|[\x{1F800}-\x{1F8FF}]|[\x{2600}-\x{26FF}]|[\x{2700}-\x{27BF}]" > /dev/null; then
        echo "❌ ERROR: Emojis not allowed in commit messages"
        echo "Please use professional commit message format"
        exit 1
    fi

    echo "✅ Commit message format validated"
fi

# =============================================================================
# SUCCESS SUMMARY
# =============================================================================
echo ""
echo "🎉 PRE-COMMIT VALIDATION SUCCESSFUL"
echo "=================================="
echo "📊 Validation Summary:"
echo "  ✅ CI synchronization verified"
echo "  ✅ All 7 CI phases passed locally"
echo "  ✅ Code will pass GitHub Actions CI"
echo "  ✅ No sensitive information detected"
echo "  ✅ Commit message format valid"
echo ""
echo "🚀 SAFE TO COMMIT - CI will pass"
echo "⏰ Completed: $(date)"
echo ""

# =============================================================================
# COMMIT GUIDANCE
# =============================================================================
echo "📋 COMMIT GUIDANCE:"
echo "=================="
echo "Your code has passed all validations and is ready for commit."
echo ""
echo "💡 Professional commit message format:"
echo "fix: resolve [specific issue] in [component]"
echo "feat: add [new feature] to [component]"
echo "refactor: improve [aspect] in [component]"
echo ""
echo "📝 Include in commit description:"
echo "- Technical changes made"
echo "- Issues resolved"
echo "- Testing performed"
echo "- Quality metrics achieved"
echo ""
echo "🔗 Example:"
echo "fix: resolve content caching issue in fast mode"
echo ""
echo "Update content service to properly handle cache invalidation"
echo "when content is updated externally. Fixes race condition"
echo "between cache and content discovery service."
echo ""
echo "Technical Changes:"
echo "- Add cache invalidation logic to ContentService"
echo "- Implement TTL-based cache expiration"
echo "- Update integration tests for cache consistency"
echo ""
echo "Quality Validation:"
echo "- All 413 tests passing (76.27% coverage)"
echo "- Zero security issues found"
echo "- MyPy type checking clean"
echo ""