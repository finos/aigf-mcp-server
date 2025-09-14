# Contributing to Independent AI Governance MCP Server

Thank you for your interest in contributing to this independent AI Governance MCP Server project! This document provides guidelines for contributing to this community-driven initiative.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Security Guidelines](#security-guidelines)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

## 🤝 Code of Conduct

This project adheres to our [Contributor Code of Conduct](../governance/code-of-conduct.md). By participating, you are expected to uphold this code.

## 🛠️ Development Setup

### Prerequisites

- **Python 3.9-3.13** (we test against all versions)
- **Git** with commit signing configured
- **Virtual environment tools** (venv or similar)

### Initial Setup

1. **Fork and Clone**
   ```bash
   # Fork the repository on GitHub first, then:
   git clone https://github.com/YOUR_USERNAME/finos-mcp-server.git
   cd finos-mcp-server
   git remote add upstream https://github.com/hugo-calderon/finos-mcp-server.git
   ```

2. **Create Development Environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install Development Dependencies**
   ```bash
   pip install -e .
   ```

4. **Verify Setup**
   ```bash
   # Run tests to verify installation
   python -m pytest tests/ -v
   
   # Verify CLI works
   finos-mcp --help
   ```

### Development Configuration

Create a `.env` file for development:

```bash
# Development configuration
FINOS_MCP_LOG_LEVEL=DEBUG
FINOS_MCP_DEBUG_MODE=true
FINOS_MCP_ENABLE_CACHE=false
FINOS_MCP_HTTP_TIMEOUT=10
```

## 🔄 Development Workflow

### Branch Strategy

We use **feature branch workflow** with strict quality gates:

1. **Main Branch**: Production-ready code only
2. **Feature Branches**: `feature/description-of-change`
3. **Hotfix Branches**: `hotfix/critical-issue-fix`
4. **Development Branch**: `develop` (if applicable)

### Creating a Feature

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-description
   ```

2. **Make Your Changes**
   - Follow coding standards (see below)
   - Write comprehensive tests
   - Update documentation as needed

3. **Validate Changes**
   ```bash
   # Run tests
   python -m pytest tests/ -v
   
   # Check code quality
   ruff check .
   ruff format --check .
   mypy src/
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: your descriptive commit message"
   ```

### Commit Message Format

We use **Conventional Commits** for automated changelog generation:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Test additions or modifications
- `chore`: Build/CI changes

**Examples:**
```bash
feat(tools): add search result ranking algorithm

Implements TF-IDF based ranking for search results to improve
relevance scoring across mitigation and risk documents.

Closes #123
```

```bash
fix(cache): resolve memory leak in TTL cleanup

Fixed issue where expired cache entries weren't being properly
garbage collected, causing memory usage to grow over time.

Fixes #456
```

## 📏 Coding Standards

### Code Quality Requirements

**ALL code must pass these quality gates:**

1. **Ruff Linting**: `ruff check .` (zero issues)
2. **Ruff Formatting**: `ruff format --check .` (all files formatted)
3. **MyPy Type Checking**: `mypy src/ --strict` (zero errors)
4. **Security Scanning**: `bandit -r src/` (no high/medium issues)

### Code Style Guidelines

#### Python Code Standards

```python
"""
Module docstring with clear description.

This module handles XYZ functionality with proper error handling,
logging, and type annotations throughout.
"""

import asyncio
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

class ExampleClass:
    """Class with comprehensive docstring."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize with proper type hints."""
        self.config = config
        self._cache: Dict[str, Any] = {}

    async def process_data(
        self,
        input_data: List[str],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process input data with comprehensive error handling.

        Args:
            input_data: List of strings to process
            options: Optional configuration parameters

        Returns:
            Processed data dictionary

        Raises:
            ValueError: If input data is invalid
            RuntimeError: If processing fails
        """
        if not input_data:
            raise ValueError("Input data cannot be empty")

        try:
            # Processing logic here
            return {"processed": len(input_data)}
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise RuntimeError(f"Data processing error: {e}") from e
```

#### Type Annotation Requirements

- **100% type coverage** for all functions and methods
- Use modern typing syntax: `list[str]` instead of `List[str]`
- Proper return type annotations: `-> None`, `-> bool`, `-> Dict[str, Any]`
- Complex types documented with TypedDict or Pydantic models

#### Error Handling Standards

```python
# Good: Comprehensive error handling
async def fetch_document(url: str) -> Optional[str]:
    """Fetch document with proper error handling."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error {e.response.status_code} for {url}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Network error fetching {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
        raise RuntimeError(f"Document fetch failed: {e}") from e
```

#### Logging Standards

```python
import logging
from finos_mcp.logging import get_logger

logger = get_logger(__name__)

# Good: Structured logging with context
logger.info(
    "Document processed successfully",
    extra={
        "document_id": doc_id,
        "processing_time": elapsed_ms,
        "cache_hit": from_cache
    }
)

# Good: Error logging with details
logger.error(
    "Failed to process document",
    extra={
        "document_id": doc_id,
        "error_type": type(e).__name__,
        "error_message": str(e)
    },
    exc_info=True
)
```

## 🧪 Testing Requirements

### Test Coverage Requirements

- **Target 85%+ code coverage**
- Comprehensive coverage for new features
- All edge cases and error conditions tested

### Test Categories

#### Unit Tests (`tests/unit/`)

```python
import pytest
from unittest.mock import AsyncMock, patch

from finos_mcp.content.service import ContentService

@pytest.mark.asyncio
async def test_fetch_document_success():
    """Test successful document fetching."""
    service = ContentService()

    with patch.object(service._http_client, 'fetch_text') as mock_fetch:
        mock_fetch.return_value = "document content"

        result = await service.get_document("mitigation", "mi-1.md")

        assert result is not None
        assert "content" in result
        mock_fetch.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_document_network_error():
    """Test network error handling."""
    service = ContentService()

    with patch.object(service._http_client, 'fetch_text') as mock_fetch:
        mock_fetch.side_effect = httpx.RequestError("Network error")

        result = await service.get_document("mitigation", "mi-1.md")

        assert result is None
```

#### Integration Tests (`tests/integration/`)

```python
@pytest.mark.asyncio
async def test_mcp_protocol_compliance():
    """Test MCP protocol compliance end-to-end."""
    # Start server process
    process = await asyncio.create_subprocess_exec(
        "finos-mcp",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE
    )

    # Send MCP initialization
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"}
    }

    process.stdin.write(json.dumps(request).encode() + b'\n')
    await process.stdin.drain()

    # Validate response
    response_line = await process.stdout.readline()
    response = json.loads(response_line.decode())

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
```

### Test Data Management

- Mock external dependencies (GitHub API calls)
- Test fixtures in `tests/conftest.py`
- Parameterized tests for multiple scenarios

## 🛡️ Security Guidelines

### Security Requirements

**ALL contributions must meet security standards:**

1. **No secrets in code**: Use environment variables
2. **Input validation**: All user inputs validated with Pydantic
3. **Dependency scanning**: `pip-audit` must pass
4. **Static analysis**: `bandit` security scanning required
5. **Secret scanning**: `detect-secrets` and `gitleaks` compliance

### Security Best Practices

```python
# Good: Secure configuration handling
from pydantic import BaseModel, Field, validator

class Settings(BaseModel):
    api_key: str = Field(..., description="API key from environment")

    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError("API key must be at least 10 characters")
        return v

# Good: Safe HTTP client usage
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url, follow_redirects=False)
    response.raise_for_status()
```

### Vulnerability Reporting

**Do not** report security vulnerabilities through public GitHub issues. Instead:

1. Create a [Security Advisory](https://github.com/hugo-calderon/finos-mcp-server/security/advisories) for responsible disclosure
2. Allow 90 days for response before public disclosure
3. Include reproduction steps and impact assessment

## 🚀 Pull Request Process

### Before Opening a PR

1. **Validate Quality**
   ```bash
   # Run tests
   python -m pytest tests/ -v --tb=short
   
   # Check code quality  
   ruff check .
   ruff format --check .
   mypy src/
   ```

3. **Update Documentation**
   - Update README.md if adding features
   - Add docstrings to all new functions
   - Update CHANGELOG.md (if exists)

### PR Template

When opening a PR, use this template:

```markdown
## Description
Brief description of changes and motivation.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update

## Testing
- [ ] All tests pass: `python -m pytest tests/ -v --tb=short`
- [ ] Code quality checks pass: `ruff check .`, `ruff format --check .`, `mypy src/`
- [ ] New tests added for new functionality
- [ ] Test coverage maintained

## Security
- [ ] No secrets or sensitive data included
- [ ] Input validation implemented for new endpoints
- [ ] Security scanning passes (bandit, pip-audit)

## Documentation
- [ ] README.md updated (if needed)
- [ ] Docstrings added to new functions
- [ ] Type annotations are comprehensive

## Checklist
- [ ] Code follows project coding standards
- [ ] Self-review completed
- [ ] Conventional commit format used
- [ ] Branch is up to date with main
```

### Review Process

1. **Automated Checks**: All CI/CD pipelines must pass
2. **Code Review**: At least one maintainer review required
3. **Security Review**: Security team review for sensitive changes
4. **Final Validation**: Maintainer runs stability validation

### Merge Requirements

**ALL must be satisfied before merge:**

- ✅ All CI/CD checks pass
- ✅ Code review approval from maintainer
- ✅ No merge conflicts with main branch
- ✅ All tests pass
- ✅ Code quality checks pass
- ✅ Security scanning: No critical/high issues
- ✅ Documentation updated appropriately

## 📦 Release Process

### Version Management

We follow **Semantic Versioning** (semver):

- **MAJOR** version: Breaking changes
- **MINOR** version: New features (backward compatible)
- **PATCH** version: Bug fixes (backward compatible)

### Release Workflow

1. **Pre-release Validation**
   ```bash
   # Run tests and quality checks
   python -m pytest tests/ -v --tb=short
   ruff check .
   ruff format --check .
   mypy src/
   ```

2. **Version Bump**
   ```bash
   # Update version in pyproject.toml
   # Update version in src/finos_mcp/__init__.py
   # Create commit
   git add .
   git commit -m "chore: bump version to X.Y.Z"
   ```

3. **Create Release**
   ```bash
   # Create and push version tag
   git tag vX.Y.Z
   git push origin main --tags
   ```
   - Automated workflows create GitHub release
   - SBOM and security attestations generated
   - PyPI publishing with manual approval

### Release Automation

GitHub Actions handle:

- ✅ **Build artifacts** (wheel and source distribution)
- ✅ **Release notes** from conventional commits
- ✅ **Basic security scanning**

For detailed release procedures, see [`release-process.md`](../operations/release-process.md).

## 🆘 Getting Help

### Community Support

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and help
- **Project Discussions**: Use GitHub Discussions for community support

### Maintainer Contact

For urgent issues or security concerns:
- **Security Issues**: Use GitHub Security Advisories
- **General Support**: GitHub Issues and Discussions  
- **Direct Contact**: [hugocalderon@example.com](mailto:hugocalderon@example.com)

## 🙏 Recognition

All contributors will be recognized in:
- GitHub contributors list
- Release notes acknowledgments
- Project community highlights

Thank you for contributing to this independent AI Governance MCP Server project! 🚀
