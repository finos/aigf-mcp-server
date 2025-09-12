# FINOS AI Governance MCP Server - Developer Guide

Complete guide for developers who want to contribute to or extend the FINOS AI Governance MCP Server.

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Development Setup](#development-setup)
- [Code Structure](#code-structure)
- [Testing](#testing)
- [Contributing](#contributing)

## 🎯 Project Overview

The FINOS AI Governance MCP Server is a Model Context Protocol (MCP) server that provides programmatic access to AI governance content from the [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework).

### Key Capabilities
- **Content Access**: 17 AI governance mitigations and 17 risk assessments
- **Search Functionality**: Intelligent search across all governance content
- **MCP Compliance**: Full support for MCP 2024-11-05 specification
- **Enterprise Features**: Health monitoring, caching, error handling

### Technology Stack
- **Python 3.9-3.13**: Core implementation language
- **MCP Protocol**: Model Context Protocol for AI tool integration
- **AsyncIO**: Asynchronous programming for performance
- **Pydantic**: Data validation and settings management
- **httpx**: Modern HTTP client with async support

## 🏗️ Architecture

### Core Components

```
src/finos_mcp/
├── __init__.py          # Package initialization and version
├── server.py            # MCP server implementation
├── config.py            # Configuration management
├── tools.py             # MCP tool implementations
├── content/             # Content management modules
│   ├── service.py       # Content service orchestrator
│   ├── parser.py        # Frontmatter and markdown parsing
│   └── cache.py         # Intelligent caching system
├── http_client.py       # HTTP client with resilience features
├── logging.py           # Structured logging implementation
└── health.py            # Health monitoring and metrics
```

### Design Principles

1. **Modularity**: Clear separation of concerns with dedicated modules
2. **Resilience**: Circuit breakers, retry logic, graceful degradation
3. **Performance**: Intelligent caching and async operations
4. **Observability**: Comprehensive logging and health monitoring
5. **Security**: Input validation, rate limiting, secure defaults

### Data Flow

1. **Client Request** → MCP Protocol Handler
2. **Tool Validation** → Input sanitization and validation
3. **Content Service** → Orchestrates content retrieval
4. **HTTP Client** → Fetches from GitHub API (with caching)
5. **Content Parser** → Processes markdown and frontmatter
6. **Response Formation** → Formats response according to MCP spec

## 🛠️ Development Setup

### Prerequisites
- Python 3.9 or higher
- Git with SSH key configured
- Virtual environment tools

### Quick Setup
```bash
# Clone the repository
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server

# Run automated setup
./scripts/dev-setup.sh
```

### Manual Setup
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
pip install -r config/dependencies/requirements.lock

# Install pre-commit hooks
pre-commit install --config config/ci/pre-commit-config.yaml

# Verify installation
finos-mcp --help
```

## 📁 Code Structure

### Server Implementation (`server.py`)
- **MCP Protocol Handler**: Implements MCP specification
- **Tool Registry**: Manages available MCP tools
- **Error Handling**: Comprehensive error boundaries
- **Logging Integration**: Structured logging throughout

### Content Management (`content/`)
- **Service Layer**: High-level content operations
- **Parser Module**: Markdown and YAML frontmatter parsing
- **Cache System**: TTL-based caching with LRU eviction

### Configuration (`config.py`)
- **Pydantic Models**: Type-safe configuration
- **Environment Variables**: Flexible configuration sources
- **Validation**: Comprehensive setting validation

### Tools (`tools.py`)
- **Search Operations**: Intelligent content search
- **Content Retrieval**: Direct document access
- **Listing Operations**: Content discovery
- **Input Validation**: Secure parameter handling

## 🧪 Testing

### Test Structure
```
tests/
├── unit/                # Unit tests for individual modules
├── integration/         # Integration tests with external systems
├── conftest.py          # Shared test fixtures
└── golden/              # Golden file baselines
```

### Running Tests
```bash
# Unit tests
python -m pytest tests/unit/ -v

# Integration tests
python -m pytest tests/integration/ -v

# Full test suite with coverage
python -m pytest --cov=src/finos_mcp --cov-report=html

# Quality validation
./scripts/quality-check.sh
```

### Test Categories

**Unit Tests**: Individual module testing with mocking
- Configuration validation
- Content parsing logic
- Cache behavior
- HTTP client resilience

**Integration Tests**: End-to-end functionality
- MCP protocol compliance
- GitHub API integration
- Content service orchestration
- Error handling scenarios

**Stability Tests**: Production readiness validation
- Console script functionality
- Package installation
- Configuration loading
- Basic server operations

## 📝 Contributing

### Development Workflow

Please see our [Contributing Guide](CONTRIBUTING.md) for the complete development workflow including:
- Environment setup
- Branch management
- Testing requirements
- Pull request process

External contributors should follow the fork-based workflow outlined in the contributing guide.

### Code Standards

**Code Quality Requirements:**
- Ruff linting and formatting compliance
- MyPy type checking with comprehensive type annotations
- Test coverage meeting project requirements
- Security scanning compliance

**Architecture Guidelines:**
- Async/await for I/O operations
- Type hints for all public interfaces
- Comprehensive error handling
- Structured logging with context

### Type Checking Best Practices

The project uses MyPy for static type checking. Contributors should ensure proper type annotations.

**Common Type Annotation Patterns:**

1. **Function Signatures**: Always annotate parameters and return types
   ```python
   # ✅ Good
   def process_data(items: list[str]) -> dict[str, int]:
       return {"count": len(items)}

   # ❌ Bad - missing type annotations
   def process_data(items):
       return {"count": len(items)}
   ```

2. **Async Functions**: Include Awaitable and Callable imports
   ```python
   from collections.abc import Awaitable, Callable

   async def execute_with_retry(
       self, func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
   ) -> Any:
   ```

3. **Union Types**: Use modern Python 3.10+ syntax
   ```python
   # ✅ Good (Python 3.10+)
   cache: dict[str, Any] | None = None

   # ✅ Acceptable (older Python)
   from typing import Optional, Union
   cache: Optional[Dict[str, Any]] = None
   ```

4. **Exception Handling**: Use type assertions after isinstance checks
   ```python
   result = await asyncio.gather(task1, task2, return_exceptions=True)
   if isinstance(result[0], Exception):
       logger.error("Task failed: %s", result[0])
       return None

   # MyPy now knows result[0] is not an Exception
   assert isinstance(result[0], list)  # Help MyPy understand the type
   ```

5. **Singleton Patterns**: Use proper instance attribute declarations
   ```python
   class CacheManager:
       _instance: Optional["CacheManager"] = None

       def __init__(self) -> None:
           if not hasattr(self, '_initialized'):
               self._cache: dict[str, Any] | None = None
               self._timestamp: float | None = None
               self._initialized = True
   ```

**Common MyPy Errors and Solutions:**

- `[no-untyped-def]`: Add return type annotations (`-> None` if no return)
- `[arg-type]`: Check argument types match function signature
- `[has-type]`: Add proper type annotations to instance attributes
- `[unreachable]`: Fix logical conditions that MyPy can't analyze
- `[misc]`: Various issues - read the specific error message

**Testing Type Annotations:**
```bash
# Test type checking in development
./scripts/quality-check.sh

# Or just MyPy
python -m mypy src/finos_mcp

# MyPy with extra strict options
python -m mypy src/finos_mcp --strict --warn-unreachable
```

**Security Requirements:**
- Input validation for all external data
- Secure handling of credentials
- Rate limiting and resource protection
- Regular dependency updates

### Adding New Features

**New MCP Tools:**
1. Add tool function to `tools.py`
2. Include comprehensive input validation
3. Add error handling and logging
4. Write unit and integration tests
5. Update API documentation

**New Content Sources:**
1. Extend content service in `content/service.py`
2. Add parsing logic if needed
3. Update caching strategy
4. Add configuration options
5. Comprehensive testing

### Performance Considerations

- **Async Operations**: Use async/await for I/O
- **Caching Strategy**: Leverage TTL cache effectively
- **Resource Management**: Proper connection pooling
- **Error Boundaries**: Graceful degradation patterns

## 🔧 Development Tools

### Available Scripts
- `./scripts/dev-setup.sh` - Development environment setup
- `./scripts/quality-check.sh` - Code quality validation
- `./scripts/clean.sh` - Environment cleanup

### Configuration Files
- `config/ci/pre-commit-config.yaml` - Pre-commit hooks
- `config/security/bandit.yml` - Security scanning config
- `config/dependencies/requirements.lock` - Pinned dependencies

### IDE Integration
- MyPy configuration in `mypy.ini`
- Pytest configuration in `pytest.ini`
- Ruff settings in `pyproject.toml`

## 🎯 Coding Principles

### Core Design Patterns

**Problem Solved**: Previous development was slowed by over-engineered validation and complex tests.

#### 1. KISS Principle (Keep It Simple, Stupid)
```python
# ✅ Good: Simple, explicit checks
def is_dangerous_input(text: str) -> bool:
    return any(danger in text.lower() for danger in ["<script>", "javascript:", "eval("])

# ❌ Bad: Complex regex that breaks legitimate text
dangerous_patterns = [r"<script", r"javascript:", ...]  # Matches "security" wrongly
```

#### 2. Dependency Injection for Testability
```python
# ✅ Good: Injectable dependencies
def handle_call_tool(name: str, args: dict, validator=None) -> Any:
    if validator is None:
        validator = get_default_validator()
    return validator.validate(name, args)

# ❌ Bad: Hardcoded dependencies (untestable)
def handle_call_tool(name: str, args: dict) -> Any:
    validate_tool_arguments(name, args)  # Cannot be mocked
```

#### 3. Configuration-Driven Validation
```python
# Environment-based validation modes
ValidationMode.DISABLED   # Tests: no validation
ValidationMode.PERMISSIVE # Dev: relaxed validation
ValidationMode.STRICT     # Prod: full validation
```

### Testing Principles

#### 1. Simple, Focused Tests
```python
# ✅ Good: One concern per test
def test_package_import():
    import finos_mcp
    assert hasattr(finos_mcp, "get_version")

# ❌ Bad: Complex fixtures testing multiple concerns
def test_complex_scenario(complex_fixture, another_fixture):
    # 20 lines of setup and multiple assertions...
```

#### 2. Auto-Configuration for Tests
```python
# Automatic test environment setup (see tests/conftest.py)
@pytest.fixture(autouse=True)
def setup_test_environment():
    os.environ["FINOS_MCP_VALIDATION_MODE"] = "disabled"
```

### Environment Variables
- `FINOS_MCP_VALIDATION_MODE`: `strict|permissive|disabled`
- `FINOS_MCP_DEBUG_MODE`: `true|false`
- `PYTEST_CURRENT_TEST`: Auto-detected (disables validation)

### Development Workflow
```bash
# 1. Set development mode (relaxed validation)
export FINOS_MCP_VALIDATION_MODE=permissive

# 2. Tests automatically use disabled mode
pytest

# 3. Pre-commit ensures code quality
pre-commit run --all-files
```

---

> **Ready to contribute?** Check out our [Contributing Guide](CONTRIBUTING.md) for detailed guidelines and the [API Reference](api-reference.md) for technical specifications.
