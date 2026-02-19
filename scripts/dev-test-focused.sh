#!/bin/bash
# Development Test-Focused Mode
# Sets up environment for fast, offline testing and development

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

# Create test environment configuration
create_test_env() {
    log_info "Creating test environment configuration..."

    cat > .env.test << EOF
# Test-focused development environment
# This configuration optimizes for fast, offline testing

# Offline Mode - Disable external network calls
FINOS_MCP_OFFLINE_MODE=true

# Cache Configuration - Use in-memory for speed
FINOS_MCP_ENABLE_CACHE=true
FINOS_MCP_CACHE_MAX_SIZE=100
FINOS_MCP_CACHE_TTL_SECONDS=60

# Logging - Reduce noise during testing
FINOS_MCP_LOG_LEVEL=WARNING
FINOS_MCP_DEBUG_MODE=false

# Network - Faster timeouts for testing
FINOS_MCP_HTTP_TIMEOUT=5

# Validation - Disable for testing speed
FINOS_MCP_VALIDATION_MODE=disabled

# GitHub - Use mock responses
FINOS_MCP_GITHUB_TOKEN=mock_token_for_testing

# Test Mode Indicators
FINOS_MCP_TEST_MODE=true
FINOS_MCP_FAST_MODE=true
EOF

    log_success "Created .env.test"
}

# Create test fixtures directory structure
create_test_fixtures() {
    log_info "Setting up test fixtures..."

    # Create fixtures directory
    mkdir -p tests/fixtures
    mkdir -p tests/fixtures/responses
    mkdir -p tests/fixtures/documents
    mkdir -p tests/fixtures/mock_data

    # Create mock HTTP responses
    cat > tests/fixtures/responses/mitigation_sample.json << 'EOF'
{
    "filename": "sample-mitigation.md",
    "type": "mitigation",
    "metadata": {
        "title": "Sample AI Risk Mitigation",
        "category": "data-protection",
        "risk_level": "medium"
    },
    "content": "# Sample Mitigation\n\nThis is a sample mitigation for testing purposes.\n\n## Implementation\n\n- Step 1: Configure data validation\n- Step 2: Implement monitoring\n- Step 3: Set up alerts",
    "full_text": "---\ntitle: Sample AI Risk Mitigation\ncategory: data-protection\nrisk_level: medium\n---\n\n# Sample Mitigation\n\nThis is a sample mitigation for testing purposes.\n\n## Implementation\n\n- Step 1: Configure data validation\n- Step 2: Implement monitoring\n- Step 3: Set up alerts"
}
EOF

    cat > tests/fixtures/responses/risk_sample.json << 'EOF'
{
    "filename": "sample-risk.md",
    "type": "risk",
    "metadata": {
        "title": "Sample AI Risk",
        "category": "model-security",
        "severity": "high"
    },
    "content": "# Sample Risk\n\nThis is a sample risk for testing purposes.\n\n## Description\n\nThis risk represents potential security vulnerabilities in AI model deployment.\n\n## Impact\n\n- Data exposure\n- Model manipulation\n- Service disruption",
    "full_text": "---\ntitle: Sample AI Risk\ncategory: model-security\nseverity: high\n---\n\n# Sample Risk\n\nThis is a sample risk for testing purposes.\n\n## Description\n\nThis risk represents potential security vulnerabilities in AI model deployment.\n\n## Impact\n\n- Data exposure\n- Model manipulation\n- Service disruption"
}
EOF

    # Create mock file lists
    cat > tests/fixtures/mock_data/mitigation_files.json << 'EOF'
[
    "sample-mitigation.md",
    "data-protection-guide.md",
    "model-security-checklist.md",
    "privacy-framework.md",
    "audit-requirements.md"
]
EOF

    cat > tests/fixtures/mock_data/risk_files.json << 'EOF'
[
    "sample-risk.md",
    "adversarial-attacks.md",
    "data-poisoning.md",
    "prompt-injection.md",
    "model-extraction.md"
]
EOF

    # Create search response fixtures
    cat > tests/fixtures/responses/search_results.json << 'EOF'
{
    "results": [
        {
            "filename": "sample-mitigation.md",
            "type": "mitigation",
            "title": "Sample AI Risk Mitigation",
            "snippet": "This is a sample mitigation for testing purposes...",
            "relevance_score": 0.95
        },
        {
            "filename": "sample-risk.md",
            "type": "risk",
            "title": "Sample AI Risk",
            "snippet": "This risk represents potential security vulnerabilities...",
            "relevance_score": 0.87
        }
    ],
    "total_count": 2,
    "query": "sample",
    "execution_time_ms": 1.2
}
EOF

    log_success "Test fixtures created"
}

# Create fast test configuration
create_pytest_config() {
    log_info "Creating fast test configuration..."

    # Create pytest configuration for fast tests
    cat > pytest.fast.ini << 'EOF'
[tool:pytest]
minversion = 6.0
addopts =
    --strict-markers
    --strict-config
    --disable-warnings
    -ra
    --tb=short
    --maxfail=5
    -x
testpaths = tests/unit
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
markers =
    unit: Fast unit tests
    integration: Slower integration tests (skipped in fast mode)
    slow: Very slow tests (skipped in fast mode)
    network: Tests requiring network (skipped in offline mode)
EOF

    log_success "Fast test configuration created"
}

# Create test runner script
create_test_runner() {
    log_info "Creating fast test runner..."

    cat > scripts/test-fast.sh << 'EOF'
#!/bin/bash
# Fast test runner for development
set -euo pipefail

# Load test environment
if [[ -f ".env.test" ]]; then
    source .env.test
fi

# Run only fast unit tests
echo "🚀 Running fast tests (offline mode)..."
python -m pytest \
    -c pytest.fast.ini \
    --disable-warnings \
    -q \
    -x \
    --tb=short \
    -m "not slow and not integration and not network" \
    tests/unit/

echo "✅ Fast tests completed"
EOF

    chmod +x scripts/test-fast.sh
    log_success "Fast test runner created"
}

# Setup offline development mode
setup_offline_mode() {
    log_info "Configuring offline development mode..."

    # Create offline configuration helper
    cat > tests/internal/offline_config.py << 'EOF'
"""
Offline development mode configuration.
Provides utilities for running tests without external dependencies.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List

class OfflineConfig:
    """Configuration for offline development mode."""

    def __init__(self):
        self.fixtures_dir = Path("tests/fixtures")
        self.responses_dir = self.fixtures_dir / "responses"
        self.mock_data_dir = self.fixtures_dir / "mock_data"

    def is_offline_mode(self) -> bool:
        """Check if offline mode is enabled."""
        return os.getenv("FINOS_MCP_OFFLINE_MODE", "false").lower() == "true"

    def get_mock_response(self, response_type: str) -> Dict[str, Any]:
        """Get mock response data for testing."""
        response_file = self.responses_dir / f"{response_type}.json"
        if response_file.exists():
            with open(response_file) as f:
                return json.load(f)
        return {}

    def get_mock_file_list(self, list_type: str) -> List[str]:
        """Get mock file list for testing."""
        list_file = self.mock_data_dir / f"{list_type}_files.json"
        if list_file.exists():
            with open(list_file) as f:
                return json.load(f)
        return []

# Global instance
offline_config = OfflineConfig()
EOF

    log_success "Offline mode configuration created"
}

# Verify test environment
verify_test_environment() {
    log_info "Verifying test environment..."

    # Check that all required files exist
    required_files=(
        ".env.test"
        "tests/fixtures/responses/mitigation_sample.json"
        "tests/fixtures/responses/risk_sample.json"
        "tests/fixtures/mock_data/mitigation_files.json"
        "tests/fixtures/mock_data/risk_files.json"
        "pytest.fast.ini"
        "scripts/test-fast.sh"
        "tests/internal/offline_config.py"
    )

    for file in "${required_files[@]}"; do
        if [[ -f "$file" ]]; then
            log_success "✅ $file"
        else
            log_error "❌ $file missing"
            exit 1
        fi
    done

    # Test offline configuration
    if source .env.test && [[ "$FINOS_MCP_OFFLINE_MODE" == "true" ]]; then
        log_success "Offline mode configuration valid"
    else
        log_error "Offline mode configuration invalid"
        exit 1
    fi
}

# Show usage instructions
show_usage() {
    echo ""
    echo "🎯 Test-focused development mode is now active!"
    echo ""
    echo "Quick commands:"
    echo "  source .env.test           # Load test environment"
    echo "  ./scripts/test-fast.sh     # Run fast tests only"
    echo "  pytest -m 'not slow'      # Run non-slow tests"
    echo "  pytest tests/unit -q -x   # Quick unit tests"
    echo ""
    echo "Environment features:"
    echo "  ✅ Offline mode (no external network calls)"
    echo "  ✅ Fast in-memory caching"
    echo "  ✅ Reduced logging noise"
    echo "  ✅ Mock responses for testing"
    echo "  ✅ Optimized timeouts"
    echo ""
    echo "To return to normal development:"
    echo "  unset FINOS_MCP_OFFLINE_MODE"
    echo "  source .env.local  # or restart shell"
}

# Main function
main() {
    echo "🎯 FINOS MCP Server - Test-Focused Development Mode"
    echo "================================================="

    check_project_root
    create_test_env
    create_test_fixtures
    create_pytest_config
    create_test_runner
    setup_offline_mode
    verify_test_environment

    echo "================================================="
    log_success "Test-focused development mode setup complete! 🎯"

    show_usage
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
