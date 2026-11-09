#!/bin/bash
# Development Environment Setup Script
# Sets up complete development environment for FINOS AI Governance MCP Server

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="${PROJECT_ROOT}/venv"

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

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verify system requirements
check_requirements() {
    log_info "Checking system requirements..."

    # Check Python
    if ! command_exists python3; then
        log_error "Python 3 is not installed. Please install Python 3.11+ first (requires-python in pyproject.toml)."
        exit 1
    fi

    # Check Python version
    PYTHON_ACTUAL_VERSION=$(python3 --version | cut -d ' ' -f 2)
    log_info "Found Python $PYTHON_ACTUAL_VERSION"

    # Check git
    if ! command_exists git; then
        log_error "Git is not installed. Please install git first."
        exit 1
    fi

    log_success "System requirements satisfied"
}

# Create and activate virtual environment
setup_virtual_environment() {
    log_info "Setting up virtual environment..."

    if [[ -d "$VENV_PATH" ]]; then
        log_warning "Virtual environment already exists at $VENV_PATH"
        read -p "Remove existing environment? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_PATH"
            log_info "Removed existing virtual environment"
        else
            log_info "Using existing virtual environment"
            return 0
        fi
    fi

    # Create virtual environment
    python3 -m venv "$VENV_PATH"
    log_success "Virtual environment created at $VENV_PATH"

    # Activate virtual environment
    # shellcheck source=/dev/null
    source "$VENV_PATH/bin/activate"

    # Upgrade pip
    pip install --upgrade pip
    log_success "Virtual environment activated and pip upgraded"
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."

    # Ensure virtual environment is activated
    if [[ "$VIRTUAL_ENV" != "$VENV_PATH" ]]; then
        # shellcheck source=/dev/null
        source "$VENV_PATH/bin/activate"
    fi

    # Install the package in development mode with the extras CI installs.
    # No requirements file is kept beside pyproject.toml (#167).
    pip install -e "${PROJECT_ROOT}[security,dev]"

    log_success "Dependencies installed successfully"
}

# Setup pre-commit hooks
setup_pre_commit() {
    log_info "Setting up pre-commit hooks..."

    # There is exactly one hook configuration. This script used to install
    # config/ci/pre-commit-config.yaml while dev-quick-setup.sh installed the
    # root file, so two developers ran two different, silently diverging gates.
    if [[ ! -f "$PROJECT_ROOT/.pre-commit-config.yaml" ]]; then
        log_error "Pre-commit configuration not found at .pre-commit-config.yaml"
        return 1
    fi

    # pre-commit comes from the dev extra install_dependencies just installed,
    # so there is one declared version and no second install here.
    pre-commit install

    # Run hooks once to verify setup
    log_info "Running initial pre-commit check..."
    if pre-commit run --all-files; then
        log_success "Pre-commit hooks installed and working"
    else
        log_warning "Pre-commit hooks installed but some checks failed - this is normal for initial setup"
    fi
}

# Create development configuration
setup_dev_config() {
    log_info "Setting up development configuration..."

    # .env is the one file the server reads, and .env.example lists every
    # setting it has. No second list of settings is kept in this script.
    local env_file="$PROJECT_ROOT/.env"

    if [[ -f "$env_file" ]]; then
        log_info "Configuration already exists at $env_file"
        return 0
    fi

    cp "$PROJECT_ROOT/.env.example" "$env_file"

    log_success "Configuration created at $env_file from .env.example"
    log_info "Edit $env_file to add your GitHub token for better rate limits"
}

# Run validation tests
run_validation() {
    log_info "Running validation tests..."

    # Test basic import
    if python -c "import finos_mcp; print('✅ Package import successful')"; then
        log_success "Package import validation passed"
    else
        log_error "Package import validation failed"
        return 1
    fi

    # Test console script
    if command_exists finos-mcp; then
        log_success "Console script 'finos-mcp' available"
    else
        log_error "Console script 'finos-mcp' not found"
        return 1
    fi

    log_success "Development environment validation completed"
}

# Print setup summary
print_summary() {
    echo
    echo "==============================================="
    echo -e "${GREEN}🎉 Development Environment Setup Complete!${NC}"
    echo "==============================================="
    echo
    echo "📁 Project structure:"
    echo "   Virtual Environment: $VENV_PATH"
    echo "   Configuration: $PROJECT_ROOT/.env (read only when FINOS_MCP_ENV_FILE names it)"
    echo "   Scripts: $PROJECT_ROOT/scripts/"
    echo
    echo "🚀 Next steps:"
    echo "   1. Activate virtual environment:"
    echo "      source venv/bin/activate"
    echo
    echo "   2. Edit development configuration:"
    echo "      nano .env"
    echo "      # Add your GitHub token for better rate limits"
    echo
    echo "   3. Test the MCP server:"
    echo "      FINOS_MCP_ENV_FILE=$PROJECT_ROOT/.env venv/bin/finos-mcp"
    echo
    echo "   4. Run comprehensive tests:"
    echo "      pytest"
    echo
    echo "   5. Start development with:"
    echo "      scripts/dev-test.sh"
    echo
    echo "📚 Documentation available at:"
    echo "   docs/README.md - Setup guide"
    echo "   docs/api/mcp-tools.md - Complete tool reference"
    echo
    echo "🛠️ Development commands:"
    echo "   scripts/dev-test.sh      - Run development tests"
    echo "   scripts/quality-check.sh - Run quality validation"
    echo "   scripts/clean.sh         - Clean development artifacts"
}

# Main execution
main() {
    echo "==============================================="
    echo -e "${BLUE}🚀 FINOS AI Governance MCP Server${NC}"
    echo -e "${BLUE}   Development Environment Setup${NC}"
    echo "==============================================="
    echo

    cd "$PROJECT_ROOT"

    check_requirements
    setup_virtual_environment
    install_dependencies
    setup_pre_commit
    setup_dev_config
    run_validation
    print_summary
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
