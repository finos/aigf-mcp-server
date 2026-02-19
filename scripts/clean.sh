#!/bin/bash
# Clean Development Environment Script
# Removes development artifacts, cache files, and build outputs

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Flags
CLEAN_CACHE=true
CLEAN_LOGS=true
CLEAN_BUILD=true
CLEAN_TESTS=true
CLEAN_VENV=false
DRY_RUN=false
VERBOSE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            CLEAN_CACHE=true
            CLEAN_LOGS=true
            CLEAN_BUILD=true
            CLEAN_TESTS=true
            CLEAN_VENV=true
            shift
            ;;
        --cache-only)
            CLEAN_CACHE=true
            CLEAN_LOGS=false
            CLEAN_BUILD=false
            CLEAN_TESTS=false
            CLEAN_VENV=false
            shift
            ;;
        --venv)
            CLEAN_VENV=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Clean development environment by removing temporary files and artifacts."
            echo ""
            echo "Options:"
            echo "  --all              Clean everything including virtual environment"
            echo "  --cache-only       Clean only cache files"
            echo "  --venv             Also remove virtual environment"
            echo "  --dry-run          Show what would be removed without actually doing it"
            echo "  --verbose, -v      Show detailed output"
            echo "  --help, -h         Show this help message"
            echo ""
            echo "By default, cleans cache, logs, build artifacts, and test outputs"
            echo "(but preserves virtual environment)."
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
    echo -e "${GREEN}[✅]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠️]${NC} $1"
}

log_error() {
    echo -e "${RED}[❌]${NC} $1"
}

log_section() {
    echo
    echo -e "${CYAN}$1${NC}"
    if [[ "$VERBOSE" == true ]]; then
        echo "$(printf '=%.0s' $(seq 1 ${#1}))"
    fi
}

# Remove files/directories with dry-run support
remove_item() {
    local item="$1"
    local description="$2"

    if [[ -e "$item" ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            log_warning "Would remove: $item ($description)"
        else
            rm -rf "$item"
            log_success "Removed: $item ($description)"
        fi
        return 0
    else
        if [[ "$VERBOSE" == true ]]; then
            log_info "Not found: $item"
        fi
        return 1
    fi
}

# Remove files matching pattern with dry-run support
remove_pattern() {
    local pattern="$1"
    local description="$2"
    local count=0

    # Use find with -print0 and read to handle filenames with spaces
    while IFS= read -r -d '' file; do
        if [[ "$DRY_RUN" == true ]]; then
            log_warning "Would remove: $file ($description)"
        else
            rm -rf "$file"
            if [[ "$VERBOSE" == true ]]; then
                log_success "Removed: $file"
            fi
        fi
        ((count++))
    done < <(find "$PROJECT_ROOT" -name "$pattern" -print0 2>/dev/null || true)

    if [[ $count -gt 0 ]]; then
        if [[ "$DRY_RUN" == false ]]; then
            log_success "Removed $count items matching '$pattern' ($description)"
        fi
    elif [[ "$VERBOSE" == true ]]; then
        log_info "No items found matching '$pattern'"
    fi
}

# Clean Python cache files
clean_python_cache() {
    if [[ "$CLEAN_CACHE" != true ]]; then
        return 0
    fi

    log_section "🗑️  Cleaning Python Cache Files"

    # Python cache directories
    remove_pattern "__pycache__" "Python cache directories"

    # Compiled Python files
    remove_pattern "*.pyc" "Python compiled files"
    remove_pattern "*.pyo" "Python optimized files"

    # Python cache files
    remove_pattern "*.pyd" "Python extension modules"

    # Jupyter notebook checkpoints
    remove_pattern ".ipynb_checkpoints" "Jupyter notebook checkpoints"
}

# Clean build artifacts
clean_build_artifacts() {
    if [[ "$CLEAN_BUILD" != true ]]; then
        return 0
    fi

    log_section "🔨 Cleaning Build Artifacts"

    # Python build directories
    remove_item "$PROJECT_ROOT/build" "Build directory"
    remove_item "$PROJECT_ROOT/dist" "Distribution directory"
    remove_item "$PROJECT_ROOT/*.egg-info" "Egg info directories"

    # Wheel build cache
    remove_item "$PROJECT_ROOT/.eggs" "Eggs directory"

    # setuptools build
    remove_pattern "*.egg-info" "Egg info directories"

    # Coverage files
    remove_item "$PROJECT_ROOT/.coverage" "Coverage data file"
    remove_item "$PROJECT_ROOT/htmlcov" "HTML coverage report"
    remove_pattern ".coverage.*" "Coverage data files"
}

# Clean test artifacts
clean_test_artifacts() {
    if [[ "$CLEAN_TESTS" != true ]]; then
        return 0
    fi

    log_section "🧪 Cleaning Test Artifacts"

    # Pytest cache
    remove_item "$PROJECT_ROOT/.pytest_cache" "Pytest cache directory"

    # Test reports
    remove_item "$PROJECT_ROOT/test-reports" "Test reports directory"
    remove_item "$PROJECT_ROOT/junit.xml" "JUnit test report"

    # MyPy cache
    remove_item "$PROJECT_ROOT/.mypy_cache" "MyPy cache directory"

    # Ruff cache
    remove_item "$PROJECT_ROOT/.ruff_cache" "Ruff cache directory"

    # Temporary test files
    remove_pattern "*_test_*.tmp" "Temporary test files"
    remove_pattern "test_*.log" "Test log files"
}

# Clean log files
clean_logs() {
    if [[ "$CLEAN_LOGS" != true ]]; then
        return 0
    fi

    log_section "📋 Cleaning Log Files"

    # Application logs
    remove_pattern "*.log" "Log files"
    remove_item "$PROJECT_ROOT/logs" "Logs directory"

    # Development artifacts
    remove_pattern "audit_*.json" "Audit report files"
    remove_pattern "debug_*.txt" "Debug files"

    # Temporary files
    remove_pattern "*.tmp" "Temporary files"
    remove_pattern ".DS_Store" "macOS metadata files"
    remove_pattern "Thumbs.db" "Windows thumbnail files"
}

# Clean IDE and editor files
clean_ide_files() {
    log_section "📝 Cleaning IDE and Editor Files"

    # VS Code
    remove_item "$PROJECT_ROOT/.vscode/settings.json.bak" "VS Code settings backup"

    # PyCharm
    remove_item "$PROJECT_ROOT/.idea" "PyCharm IDE files"

    # Vim/Neovim
    remove_pattern "*.swp" "Vim swap files"
    remove_pattern "*.swo" "Vim swap files"
    remove_pattern "*~" "Editor backup files"

    # Emacs
    remove_pattern "#*#" "Emacs temporary files"
    remove_pattern ".#*" "Emacs lock files"
}

# Clean virtual environment
clean_virtual_environment() {
    if [[ "$CLEAN_VENV" != true ]]; then
        return 0
    fi

    log_section "🐍 Cleaning Virtual Environment"

    if remove_item "$PROJECT_ROOT/.venv" "Virtual environment"; then
        log_warning "Virtual environment removed. Run scripts/dev-setup.sh to recreate it."
    fi
}

# Show disk space saved
show_cleanup_summary() {
    log_section "📊 Cleanup Summary"

    if [[ "$DRY_RUN" == true ]]; then
        echo -e "${YELLOW}🔍 DRY RUN COMPLETED${NC}"
        echo "No files were actually removed. Use without --dry-run to perform cleanup."
    else
        echo -e "${GREEN}🎉 CLEANUP COMPLETED${NC}"
        echo "Development environment has been cleaned."
    fi

    echo
    echo "Cleanup operations performed:"
    echo "  • Python cache files: $([ "$CLEAN_CACHE" == true ] && echo "✅" || echo "⏭️ ")"
    echo "  • Build artifacts: $([ "$CLEAN_BUILD" == true ] && echo "✅" || echo "⏭️ ")"
    echo "  • Test artifacts: $([ "$CLEAN_TESTS" == true ] && echo "✅" || echo "⏭️ ")"
    echo "  • Log files: $([ "$CLEAN_LOGS" == true ] && echo "✅" || echo "⏭️ ")"
    echo "  • Virtual environment: $([ "$CLEAN_VENV" == true ] && echo "✅" || echo "⏭️ ")"

    if [[ "$CLEAN_VENV" == true && "$DRY_RUN" == false ]]; then
        echo
        echo "🔄 To restore development environment:"
        echo "   ./scripts/dev-setup.sh"
    fi

    echo
    echo "💡 Next steps:"
    echo "   • Run tests: python -m pytest"
    echo "   • Quality check: ./scripts/quality-check.sh"
    echo "   • Setup dev env: ./scripts/dev-setup.sh"
}

# Main execution
main() {
    echo "==============================================="
    echo -e "${BLUE}🧹 FINOS AI Governance MCP Server${NC}"
    echo -e "${BLUE}   Development Environment Cleanup${NC}"
    echo "==============================================="

    if [[ "$DRY_RUN" == true ]]; then
        log_warning "DRY RUN MODE - No files will be actually removed"
    fi

    cd "$PROJECT_ROOT"

    # Show what will be cleaned
    echo
    echo "🎯 Cleanup configuration:"
    echo "  Cache files: $([ "$CLEAN_CACHE" == true ] && echo "Yes" || echo "No")"
    echo "  Build artifacts: $([ "$CLEAN_BUILD" == true ] && echo "Yes" || echo "No")"
    echo "  Test artifacts: $([ "$CLEAN_TESTS" == true ] && echo "Yes" || echo "No")"
    echo "  Log files: $([ "$CLEAN_LOGS" == true ] && echo "Yes" || echo "No")"
    echo "  Virtual environment: $([ "$CLEAN_VENV" == true ] && echo "Yes" || echo "No")"
    echo "  Verbose output: $([ "$VERBOSE" == true ] && echo "Yes" || echo "No")"

    # Confirm before cleaning virtual environment
    if [[ "$CLEAN_VENV" == true && "$DRY_RUN" == false ]]; then
        echo
        log_warning "This will remove the virtual environment (.venv/)"
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Cleanup cancelled."
            exit 0
        fi
    fi

    # Run cleanup operations
    clean_python_cache
    clean_build_artifacts
    clean_test_artifacts
    clean_logs
    clean_ide_files
    clean_virtual_environment

    show_cleanup_summary
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
