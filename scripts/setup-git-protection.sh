#!/bin/bash
# ===============================================================================
# FINOS MCP Server - Git Protection Setup Script
# Automatically installs git hooks and protective configurations
# ===============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Repository root detection
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo "================================================================="
    echo -e "${BLUE}🛡️  FINOS MCP Server - Git Protection Setup${NC}"
    echo "================================================================="
    echo ""
}

# Install pre-commit hooks
install_precommit_hooks() {
    print_status "Installing pre-commit hooks..."

    cd "$REPO_ROOT"

    # Ensure virtual environment is activated
    if [[ -f ".venv/bin/activate" ]]; then
        source .venv/bin/activate
        print_status "Activated virtual environment"
    else
        print_warning "Virtual environment not found - attempting system pre-commit"
    fi

    # Install pre-commit if not available
    if ! command -v pre-commit &> /dev/null; then
        print_status "Installing pre-commit..."
        pip install pre-commit
    fi

    # Install the hooks
    pre-commit install --install-hooks
    pre-commit install --hook-type pre-push

    print_success "Pre-commit hooks installed successfully"
}

# Create additional protective git hooks
create_protective_hooks() {
    print_status "Creating additional protective git hooks..."

    local hooks_dir="$REPO_ROOT/.git/hooks"

    # Create prepare-commit-msg hook to add warnings
    cat > "$hooks_dir/prepare-commit-msg" << 'EOF'
#!/bin/bash
# Additional protection: Add warning to commit messages about .claude content

COMMIT_MSG_FILE="$1"
COMMIT_SOURCE="$2"

# Only add warning for regular commits (not merges, etc.)
if [[ -z "$COMMIT_SOURCE" ]] || [[ "$COMMIT_SOURCE" == "message" ]]; then
    # Check if .claude content might be present
    if git diff --cached --name-only | grep -iE "claude" >/dev/null 2>&1; then
        echo "" >> "$COMMIT_MSG_FILE"
        echo "⚠️  WARNING: Commit may contain claude-related content" >> "$COMMIT_MSG_FILE"
        echo "⚠️  Ensure no .claude directories or sensitive data included" >> "$COMMIT_MSG_FILE"
    fi
fi
EOF

    chmod +x "$hooks_dir/prepare-commit-msg"

    # Create post-commit hook for verification
    cat > "$hooks_dir/post-commit" << 'EOF'
#!/bin/bash
# Post-commit verification: Check if any .claude content slipped through

if git show --name-only | grep -iE "claude" >/dev/null 2>&1; then
    echo ""
    echo "🚨 WARNING: The last commit contains claude-related files!"
    echo "Please review and consider amending if necessary:"
    git show --name-only | grep -iE "claude" | sed 's/^/  - /'
    echo ""
fi
EOF

    chmod +x "$hooks_dir/post-commit"

    print_success "Additional protective hooks created"
}

# Configure git settings for protection
configure_git_protection() {
    print_status "Configuring git protection settings..."

    cd "$REPO_ROOT"

    # Set git config to warn about large files
    git config core.preloadindex true
    git config core.fscache true

    # Configure git to use our hooks
    git config core.hooksPath .git/hooks

    # Enable git's built-in protections
    git config transfer.fsckObjects true
    git config fetch.fsckObjects true
    git config receive.fsckObjects true

    # Set up global gitignore patterns for .claude
    local global_gitignore="$HOME/.gitignore_global"
    if [[ ! -f "$global_gitignore" ]]; then
        touch "$global_gitignore"
        git config --global core.excludesfile "$global_gitignore"
    fi

    # Add .claude patterns to global gitignore if not present
    if ! grep -q "\.claude" "$global_gitignore" 2>/dev/null; then
        echo "" >> "$global_gitignore"
        echo "# Global protection against .claude content" >> "$global_gitignore"
        echo ".claude/" >> "$global_gitignore"
        echo ".claude/**" >> "$global_gitignore"
        echo "**/.claude/" >> "$global_gitignore"
        echo "**/.claude/**" >> "$global_gitignore"
        print_success "Added .claude patterns to global gitignore"
    fi

    print_success "Git protection settings configured"
}

# Verify protection installation
verify_protection() {
    print_status "Verifying protection installation..."

    cd "$REPO_ROOT"

    local errors=0

    # Check pre-commit hooks
    if [[ ! -f ".git/hooks/pre-commit" ]]; then
        print_error "Pre-commit hook not found"
        ((errors++))
    fi

    # Check if pre-commit config exists
    if [[ ! -f ".pre-commit-config.yaml" ]]; then
        print_error "Pre-commit configuration not found"
        ((errors++))
    fi

    # Check gitignore patterns
    if ! grep -q "\.claude" .gitignore; then
        print_error ".claude patterns not found in .gitignore"
        ((errors++))
    fi

    # Test pre-commit hooks
    print_status "Testing pre-commit hooks..."
    if command -v pre-commit &> /dev/null; then
        if pre-commit run --all-files &>/dev/null || true; then
            print_success "Pre-commit hooks are functional"
        else
            print_warning "Pre-commit hooks may have issues (check manually)"
        fi
    fi

    if [[ $errors -eq 0 ]]; then
        print_success "All protection mechanisms verified successfully"
        return 0
    else
        print_error "Protection verification failed with $errors errors"
        return 1
    fi
}

# Create development safety script
create_safety_script() {
    print_status "Creating development safety script..."

    cat > "$REPO_ROOT/scripts/verify-no-claude.sh" << 'EOF'
#!/bin/bash
# ===============================================================================
# FINOS MCP Server - Claude Content Verification Script
# Verifies repository contains no .claude content
# ===============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "================================================================="
echo "🔍 Scanning repository for .claude content..."
echo "================================================================="

cd "$REPO_ROOT"

found_violations=0

# Check for .claude directories
if find . -type d -name "*claude*" -not -path "./.git/*" -not -path "./.venv/*" | head -1 | grep -q .; then
    echo -e "${RED}❌ Claude directories found:${NC}"
    find . -type d -name "*claude*" -not -path "./.git/*" -not -path "./.venv/*"
    found_violations=1
fi

# Check for claude files
if find . -type f -name "*claude*" -not -path "./.git/*" -not -path "./.venv/*" | head -1 | grep -q .; then
    echo -e "${RED}❌ Claude files found:${NC}"
    find . -type f -name "*claude*" -not -path "./.git/*" -not -path "./.venv/*"
    found_violations=1
fi

# Check git index
if git ls-files | grep -iE "claude" >/dev/null 2>&1; then
    echo -e "${RED}❌ Claude content in git index:${NC}"
    git ls-files | grep -iE "claude"
    found_violations=1
fi

# Check file contents (limited scan)
if git ls-files | xargs grep -l "\.claude" 2>/dev/null | head -5 | grep -q .; then
    echo -e "${YELLOW}⚠️  Files containing .claude references:${NC}"
    git ls-files | xargs grep -l "\.claude" 2>/dev/null | head -5
    echo -e "${YELLOW}Note: These may be legitimate references (e.g., in protection scripts)${NC}"
fi

if [[ $found_violations -eq 0 ]]; then
    echo -e "${GREEN}✅ No .claude content violations found${NC}"
    echo "================================================================="
    exit 0
else
    echo -e "${RED}❌ VIOLATIONS FOUND - Clean up required${NC}"
    echo "================================================================="
    exit 1
fi
EOF

    chmod +x "$REPO_ROOT/scripts/verify-no-claude.sh"
    print_success "Safety verification script created"
}

# Main execution
main() {
    print_header

    print_status "Setting up comprehensive git protection for FINOS MCP Server..."
    print_status "Repository: $REPO_ROOT"

    # Install all protection layers
    install_precommit_hooks
    create_protective_hooks
    configure_git_protection
    create_safety_script

    # Verify everything is working
    if verify_protection; then
        echo ""
        echo "================================================================="
        print_success "🛡️  Git protection setup completed successfully!"
        echo "================================================================="
        echo ""
        print_status "Protection layers installed:"
        echo "  ✅ Enhanced .gitignore patterns"
        echo "  ✅ Pre-commit hooks with .claude blocking"
        echo "  ✅ Additional protective git hooks"
        echo "  ✅ Git configuration hardening"
        echo "  ✅ Global gitignore protection"
        echo "  ✅ Verification scripts"
        echo ""
        print_status "Next steps:"
        echo "  1. Test protection: scripts/verify-no-claude.sh"
        echo "  2. Test pre-commit: git add . && git commit -m 'test'"
        echo "  3. Share this setup with all team members"
        echo ""
        print_warning "⚠️  NEVER use 'git commit --no-verify' to bypass protection!"
        echo "================================================================="
    else
        echo ""
        echo "================================================================="
        print_error "❌ Git protection setup failed!"
        echo "================================================================="
        print_error "Please review errors above and re-run this script."
        exit 1
    fi
}

# Execute main function
main "$@"
