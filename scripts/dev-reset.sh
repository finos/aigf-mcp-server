#!/bin/bash
# Development Environment Reset
# Cleans development artifacts while preserving user configuration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the project root
check_project_root() {
    if [[ ! -f "pyproject.toml" ]]; then
        log_error "Must run from project root directory (where pyproject.toml is located)"
        exit 1
    fi
    log_info "Running from project root: $(pwd)"
}

# Clean Python cache files
clean_python_cache() {
    log_info "Cleaning Python cache files..."

    # Remove __pycache__ directories
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

    # Remove .pyc files
    find . -name "*.pyc" -delete 2>/dev/null || true

    # Remove .pyo files
    find . -name "*.pyo" -delete 2>/dev/null || true

    # Remove .pyd files (Windows)
    find . -name "*.pyd" -delete 2>/dev/null || true

    log_success "Python cache cleaned"
}

# Clean application cache
clean_app_cache() {
    log_info "Cleaning application cache..."

    # Remove .cache directory
    if [[ -d ".cache" ]]; then
        rm -rf .cache
        log_success "Application cache directory removed"
    else
        log_info "No application cache directory found"
    fi

    # Remove temporary files
    find . -name "*.tmp" -delete 2>/dev/null || true
    find . -name "*.temp" -delete 2>/dev/null || true

    log_success "Application cache cleaned"
}

# Clean logs
clean_logs() {
    log_info "Cleaning log files..."

    # Remove log files
    find . -name "*.log" -delete 2>/dev/null || true
    find . -name "*.log.*" -delete 2>/dev/null || true

    # Remove logs directory if it exists
    if [[ -d "logs" ]]; then
        rm -rf logs
        log_success "Logs directory removed"
    fi

    log_success "Log files cleaned"
}

# Clean build artifacts
clean_build_artifacts() {
    log_info "Cleaning build artifacts..."

    # Remove build directories
    rm -rf build/ 2>/dev/null || true
    rm -rf dist/ 2>/dev/null || true
    rm -rf *.egg-info/ 2>/dev/null || true

    # Remove coverage files
    rm -f .coverage 2>/dev/null || true
    rm -rf htmlcov/ 2>/dev/null || true
    rm -rf coverage-reports/ 2>/dev/null || true

    # Remove pytest cache
    rm -rf .pytest_cache/ 2>/dev/null || true

    # Remove mypy cache
    rm -rf .mypy_cache/ 2>/dev/null || true

    # Remove ruff cache
    rm -rf .ruff_cache/ 2>/dev/null || true

    log_success "Build artifacts cleaned"
}

# Clean security reports (but preserve structure)
clean_security_reports() {
    log_info "Cleaning security reports..."

    if [[ -d "security-reports" ]]; then
        # Clean old reports but keep directory structure
        find security-reports -name "*.json" -mtime +7 -delete 2>/dev/null || true
        find security-reports -name "*.txt" -mtime +7 -delete 2>/dev/null || true
        find security-reports -name "*.xml" -mtime +7 -delete 2>/dev/null || true
        log_success "Old security reports cleaned (>7 days)"
    fi
}

# Preserve user configuration files
preserve_user_config() {
    log_info "User configuration files preserved:"

    # List preserved files
    local preserved_files=(
        ".env"
        ".env.local"
        ".env.development"
        ".env.production"
        "config/local.yml"
        ".vscode/settings.json"
        ".idea/"
    )

    for file in "${preserved_files[@]}"; do
        if [[ -e "$file" ]]; then
            log_info "  ✅ $file"
        fi
    done
}

# Reset git hooks (optional)
reset_git_hooks() {
    if [[ "$1" == "--reset-hooks" ]]; then
        log_info "Resetting git hooks..."

        if [[ -d ".git/hooks" ]]; then
            # Backup existing hooks
            if [[ -f ".git/hooks/pre-commit" ]]; then
                cp .git/hooks/pre-commit .git/hooks/pre-commit.backup 2>/dev/null || true
            fi

            # Remove pre-commit hooks
            rm -f .git/hooks/pre-commit
            rm -f .git/hooks/commit-msg
            rm -f .git/hooks/pre-push

            log_warning "Git hooks removed (backed up as .backup)"
            log_info "Run './scripts/dev-quick-setup.sh' to reinstall hooks"
        fi
    fi
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --reset-hooks    Also reset git hooks (will need to run dev-quick-setup.sh)"
    echo "  --dry-run        Show what would be cleaned without actually doing it"
    echo "  --help           Show this help message"
    echo ""
    echo "Preserved files:"
    echo "  .env, .env.local, .env.*"
    echo "  config/local.yml"
    echo "  .vscode/, .idea/"
    echo "  .venv/ (virtual environment)"
}

# Dry run mode
dry_run() {
    log_info "DRY RUN - showing what would be cleaned:"
    echo ""

    echo "Would clean:"
    echo "  - Python cache files (__pycache__, *.pyc, *.pyo)"
    echo "  - Application cache (.cache/)"
    echo "  - Log files (*.log)"
    echo "  - Build artifacts (build/, dist/, *.egg-info/)"
    echo "  - Test artifacts (.pytest_cache/, .coverage, htmlcov/)"
    echo "  - Type checker cache (.mypy_cache/)"
    echo "  - Linter cache (.ruff_cache/)"
    echo "  - Old security reports (>7 days)"
    echo ""

    echo "Would preserve:"
    echo "  - Virtual environment (.venv/)"
    echo "  - User configuration (.env*, config/local.yml)"
    echo "  - Editor settings (.vscode/, .idea/)"
    echo "  - Git repository (.git/)"
    echo ""

    log_info "Run without --dry-run to perform actual cleanup"
}

# Main reset function
main() {
    echo "🧹 FINOS MCP Server - Development Environment Reset"
    echo "================================================="

    # Parse arguments
    local reset_hooks=false
    local dry_run_mode=false

    for arg in "$@"; do
        case $arg in
            --reset-hooks)
                reset_hooks=true
                ;;
            --dry-run)
                dry_run_mode=true
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown argument: $arg"
                show_usage
                exit 1
                ;;
        esac
    done

    check_project_root

    if [[ "$dry_run_mode" == true ]]; then
        dry_run
        exit 0
    fi

    # Perform cleanup
    clean_python_cache
    clean_app_cache
    clean_logs
    clean_build_artifacts
    clean_security_reports

    if [[ "$reset_hooks" == true ]]; then
        reset_git_hooks "--reset-hooks"
    fi

    preserve_user_config

    echo "================================================="
    log_success "Development environment reset complete! 🧹"
    echo ""
    echo "Cleaned:"
    echo "  ✅ Python cache files"
    echo "  ✅ Application cache"
    echo "  ✅ Log files"
    echo "  ✅ Build artifacts"
    echo "  ✅ Test artifacts"
    echo ""
    echo "Your development environment is now clean and ready!"
    echo "Run './scripts/dev-quick-setup.sh' if you need to reinstall dependencies."
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
