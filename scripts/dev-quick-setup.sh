#!/bin/bash
# Development Environment Quick Setup
# Automated setup for FINOS MCP Server development environment

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

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."

    # Check Python version
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        log_info "Python version: $PYTHON_VERSION"

        # Check if version is >= 3.10
        if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)'; then
            log_success "Python 3.10+ detected"
        else
            log_error "Python 3.10+ required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        log_error "Python 3 not found. Please install Python 3.10+"
        exit 1
    fi

    # Check git
    if command -v git &> /dev/null; then
        log_success "Git found: $(git --version)"
    else
        log_error "Git not found. Please install Git"
        exit 1
    fi
}

# Create virtual environment
setup_venv() {
    log_info "Setting up virtual environment..."

    if [[ -d ".venv" ]]; then
        log_warning "Virtual environment already exists, recreating..."
        rm -rf .venv
    fi

    python3 -m venv .venv
    log_success "Virtual environment created"

    # Activate virtual environment
    source .venv/bin/activate

    # Upgrade pip
    log_info "Upgrading pip..."
    python -m pip install --upgrade pip

    log_success "Virtual environment ready"
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."

    source .venv/bin/activate

    # Install in development mode with all extras
    log_info "Installing package in development mode..."
    pip install -e .[dev,security,test]

    # Verify installation
    if command -v finos-mcp &> /dev/null; then
        log_success "finos-mcp command available"
    else
        log_error "finos-mcp command not found after installation"
        exit 1
    fi

    log_success "Dependencies installed"
}

# Setup pre-commit hooks
setup_precommit() {
    log_info "Setting up pre-commit hooks..."

    source .venv/bin/activate

    # Install pre-commit hooks
    pre-commit install

    # Verify installation
    if [[ -f ".git/hooks/pre-commit" ]]; then
        log_success "Pre-commit hooks installed"
    else
        log_error "Pre-commit hooks installation failed"
        exit 1
    fi
}

# Create default environment configuration
setup_environment() {
    log_info "Setting up environment configuration..."

    # Create .env.example if it doesn't exist
    if [[ ! -f ".env.example" ]]; then
        cat > .env.example << EOF
# FINOS MCP Server Environment Configuration
# Copy to .env and customize as needed

# Logging Configuration
FINOS_MCP_LOG_LEVEL=INFO
FINOS_MCP_DEBUG_MODE=false

# Cache Configuration
FINOS_MCP_ENABLE_CACHE=true
FINOS_MCP_CACHE_MAX_SIZE=1000
FINOS_MCP_CACHE_TTL_SECONDS=3600

# Network Configuration
FINOS_MCP_HTTP_TIMEOUT=30

# GitHub Configuration (optional - improves rate limits)
# FINOS_MCP_GITHUB_TOKEN=your_token_here
EOF
        log_success "Created .env.example"
    fi

    # Create .env.local for local overrides (if it doesn't exist)
    if [[ ! -f ".env.local" ]]; then
        cat > .env.local << EOF
# Local development overrides
# This file is gitignored and safe for local configuration

# Enable debug mode for development
FINOS_MCP_LOG_LEVEL=DEBUG
FINOS_MCP_DEBUG_MODE=true
EOF
        log_success "Created .env.local for local development"
    else
        log_info ".env.local already exists, preserving existing configuration"
    fi
}

# Validate installation
validate_installation() {
    log_info "Validating installation..."

    source .venv/bin/activate

    # Test basic import
    if python -c "import finos_mcp; print('✅ Import successful')"; then
        log_success "Package import successful"
    else
        log_error "Package import failed"
        exit 1
    fi

    # Test console script
    if finos-mcp --help > /dev/null 2>&1; then
        log_success "Console script working"
    else
        log_error "Console script failed"
        exit 1
    fi

    # Test pre-commit
    if pre-commit --version > /dev/null 2>&1; then
        log_success "Pre-commit working"
    else
        log_error "Pre-commit failed"
        exit 1
    fi
}

# Main setup function
main() {
    echo "🚀 FINOS MCP Server - Development Environment Setup"
    echo "=================================================="

    check_project_root
    check_requirements
    setup_venv
    install_dependencies
    setup_precommit
    setup_environment
    validate_installation

    echo "=================================================="
    log_success "Development environment setup complete! 🎉"
    echo ""
    echo "Next steps:"
    echo "  1. Activate virtual environment: source .venv/bin/activate"
    echo "  2. Run tests: pytest tests/"
    echo "  3. Start development server: finos-mcp"
    echo ""
    echo "Development scripts:"
    echo "  ./scripts/dev-reset.sh      - Reset development environment"
    echo "  ./scripts/dev-test-focused.sh - Setup for fast testing"
    echo ""
    echo "Happy coding! 🚀"
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
