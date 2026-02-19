# FINOS AI Governance MCP Server

<!-- Core Project Badges -->
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![MCP Protocol](https://img.shields.io/badge/MCP-1.0+-green)
![Status](https://img.shields.io/badge/status-stable-brightgreen)

<!-- Quality & CI Badges -->
![GitHub Actions](https://img.shields.io/github/actions/workflow/status/<OWNER>/<REPO>/security-analysis.yml?branch=main&label=CI)
![Security](https://img.shields.io/badge/security-passing-brightgreen)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![MyPy](https://img.shields.io/badge/mypy-passing-blue)

<!-- Tools & Features -->
![MCP Tools](https://img.shields.io/badge/MCP%20tools-11-blue)
![Document Access](https://img.shields.io/badge/document%20access-direct-blue)
![Framework Support](https://img.shields.io/badge/frameworks-7%20supported-green)
![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen)

**AI governance framework document access through the Model Context Protocol.**

This project provides direct access to AI governance framework documents from FINOS repositories through MCP, making them available in Claude, VS Code, Cursor, and other supported tools.

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/finos/aigf-mcp-server.git
cd aigf-mcp-server

# Create and activate a virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -e .

# Required security setting (generate your own value; choose one)
export FINOS_MCP_CACHE_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
# OR
export FINOS_MCP_CACHE_SECRET=$(openssl rand -hex 32)

# Test
finos-mcp --help
mcp list tools
```

> **Note:** Using a virtual environment isolates project dependencies from your system Python, preventing conflicts and keeping your environment clean. This is the recommended approach for Python development.

**→ [Full Setup Guide](docs/README.md)** - Connect to Claude, VS Code, Cursor, etc.

---

## Available MCP Tools

### Framework Access Tools (5)
| Tool Name | Description | Use Case |
|-----------|-------------|----------|
| `list_frameworks` | List all available AI governance frameworks | Get overview of supported frameworks (NIST AI 600-1, EU AI Act, ISO 42001, etc.) |
| `get_framework` | Get complete content of a specific framework | Retrieve complete framework document content |
| `search_frameworks` | Search for text within framework documents | Find specific content within framework documents |
| `list_risks` | List all available risk documents | Get overview of AI governance risks |
| `get_risk` | Get complete content of specific risk documents | Retrieve detailed risk documentation |

### Risk & Mitigation Tools (4)
| Tool Name | Description | Use Case |
|-----------|-------------|----------|
| `search_risks` | Search within risk documentation | Find specific risks by keyword |
| `list_mitigations` | List all available mitigation documents | Get overview of available mitigations |
| `get_mitigation` | Get complete content of specific mitigation documents | Retrieve detailed mitigation strategies |
| `search_mitigations` | Search within mitigation documentation | Find specific mitigations by keyword |

### System Monitoring Tools (2)
| Tool Name | Description | Use Case |
|-----------|-------------|----------|
| `get_service_health` | Get basic service health status | Monitor system availability and status |
| `get_cache_stats` | Get cache performance statistics | Monitor cache performance and efficiency |

---

## Supported Content

### AI Governance Frameworks
| Framework | Description | Focus Area |
|-----------|-------------|------------|
| NIST AI 600-1 | NIST Artificial Intelligence Risk Management Framework | Comprehensive AI risk management |
| EU AI Act | European Union Artificial Intelligence Act | AI regulation and compliance in EU |
| ISO 42001 | AI Management Systems Standard | AI management and governance |
| FFIEC IT Booklets | Federal Financial Institutions Examination Council IT guidance | Financial services IT risk management |
| NIST SP 800-53 | Security and Privacy Controls for Information Systems | Cybersecurity controls and privacy |
| OWASP LLM Top 10 | Top 10 security vulnerabilities for LLM applications | AI/LLM security risks |
| OWASP ML Top 10 | Top 10 risks for machine learning systems | ML security and operational risks |

---

## Risk and Mitigation Categories

### Risk Categories
| Risk Type | Description | Example Risks |
|-----------|-------------|---------------|
| Security | Information security and cybersecurity risks | Data leakage, prompt injection, adversarial attacks |
| Operational | Business and operational risks | AI bias, model drift, hallucination |
| Privacy | Data privacy and protection risks | Data exposure, unauthorized access |
| Transparency | Explainability and accountability risks | Model opacity, decision traceability |

### Mitigation Categories
| Mitigation Type | Description | Example Controls |
|-----------------|-------------|------------------|
| Prevention | Proactive controls to prevent risks | Access controls, bias testing, data validation |
| Detection | Controls to detect and monitor risks | Performance monitoring, anomaly detection |
| Response | Controls to respond to identified risks | Incident response, model rollback procedures |

---

## Common Use Cases

### Framework Research
- **List Available Frameworks**: Use `list_frameworks` to see all supported governance frameworks
- **Get Framework Content**: Use `get_framework` to retrieve complete framework documents
- **Search Framework Content**: Use `search_frameworks` to find specific text within frameworks

### Risk Management
- **Browse Available Risks**: Use `list_risks` to see all documented AI governance risks
- **Get Risk Details**: Use `get_risk` to retrieve complete risk documentation
- **Search Risks**: Use `search_risks` to find specific risks by keyword

### Mitigation Planning
- **Browse Available Mitigations**: Use `list_mitigations` to see all documented mitigation strategies
- **Get Mitigation Details**: Use `get_mitigation` to retrieve complete mitigation documentation
- **Search Mitigations**: Use `search_mitigations` to find specific mitigations by keyword

### System Monitoring
- **Health Status**: Use `get_service_health` to monitor system availability
- **Performance Metrics**: Use `get_cache_stats` to monitor cache performance

---

## Architecture

### Components

- **FastMCP Server Framework** (`src/finos_mcp/fastmcp_server.py`): Modern FastMCP-based server with decorator tools
- **MCP Tools**: 11 tools organized in 3 categories (Framework Access, Risk & Mitigation, System Monitoring)
- **MCP Prompts**: 3 prompt templates for framework analysis and risk assessment
- **MCP Resources**: 3 resource types with finos:// URI scheme for structured access
- **Content Management** (`src/finos_mcp/content/`): Dynamic content loading and caching
- **Security Layer** (`src/finos_mcp/security/`): Request validation and protection
- **Runtime Guardrails** (`src/finos_mcp/fastmcp_server.py`): Middleware-based rate limiting, safe error responses, and payload size enforcement

### Design Principles

- **Document Access Only**: Direct access to governance framework documents
- **Framework Agnostic**: Works with any governance framework document structure
- **Modular Tool System**: Easy addition and removal of tools
- **Security First**: All requests validated and protected
- **Performance Optimized**: Intelligent caching and async operations

### Runtime Security Controls

- **Middleware Order**: Error handling -> timing -> logging -> rate limiting
- **Input Limits**: Tool, prompt, and resource parameters enforce max lengths and request-size checks
- **Output Limits**: Resource/document payloads are size-validated before returning to clients
- **Error Disclosure Control**: External errors are sanitized and correlation-tagged
- **Fallback Strategy**: Dynamic GitHub discovery with static fallback lists for risk/mitigation/framework catalogs
- **Boundary Authentication (Optional)**: JWT validation at MCP boundary with issuer/audience/scope enforcement

---

## Development

### Setup

```bash
# Install development dependencies
pip install -e ".[dev,security,test]"

# Run quality checks
./scripts/quality-check.sh

# Run tests
pytest
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run fast tests
pytest -c pytest.fast.ini

# Test MCP server
mcp list tools
```

### Adding New Tools

The FastMCP architecture makes adding tools simple:

1. Add decorated async function in `src/finos_mcp/fastmcp_server.py`
2. Use `@mcp.tool()` decorator with type hints and Pydantic return models
3. Add tests in `tests/unit/test_fastmcp_server.py`
4. Update tool documentation

---

## Configuration

Environment variables and configuration:
- Content loaded from GitHub repositories dynamically
- Cache configuration in `src/finos_mcp/content/cache.py`
- Security settings in `src/finos_mcp/security/`

### Required Security Configuration

`FINOS_MCP_CACHE_SECRET` is required at startup.

```bash
# Option 1 (Python)
export FINOS_MCP_CACHE_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
# Option 2 (OpenSSL)
export FINOS_MCP_CACHE_SECRET=$(openssl rand -hex 32)
```

Notes:
- Use a unique secret per environment.
- Do not commit real secrets to git.

### MCP Auth Configuration

Use JWT validation (FastMCP `JWTVerifier`) to protect the MCP boundary in production.

```bash
export FINOS_MCP_MCP_AUTH_ENABLED=true
export FINOS_MCP_MCP_AUTH_ISSUER=https://auth.example.com
export FINOS_MCP_MCP_AUTH_AUDIENCE=finos-mcp-server
export FINOS_MCP_MCP_AUTH_JWKS_URI=https://auth.example.com/.well-known/jwks.json
export FINOS_MCP_MCP_AUTH_REQUIRED_SCOPES=governance:read,governance:write
```

Notes:
- Set exactly one of `FINOS_MCP_MCP_AUTH_JWKS_URI` or `FINOS_MCP_MCP_AUTH_PUBLIC_KEY`.
- When auth is enabled, missing issuer/audience/verifier settings fail startup.
- Clients must send `Authorization: Bearer <JWT>`.

### MCP Transport Configuration

Transport and network binding are config-driven (no hardcoded host/port in runtime code):

```bash
# Local MCP client default
export FINOS_MCP_MCP_TRANSPORT=stdio

# HTTP exposure example
export FINOS_MCP_MCP_TRANSPORT=http
export FINOS_MCP_MCP_HOST=127.0.0.1
export FINOS_MCP_MCP_PORT=8000
```

### Live Transport Tests

```bash
# End-to-end stdio MCP test
FINOS_RUN_LIVE_MCP_TEST=1 ./venv/bin/pytest -q tests/integration/test_live_mcp_server.py

# End-to-end HTTP MCP test (starts server + probes /mcp)
./scripts/test-http-transport.sh

# End-to-end HTTP auth boundary test (unauthorized/forbidden/authorized)
./scripts/test-auth-http-transport.sh
```

### Advanced Configuration Reference

Use `.env.example` as the canonical source and override by environment in production.

| Variable | Default | Required | Purpose / Guidance |
|---|---|---|---|
| `FINOS_MCP_MCP_TRANSPORT` | `stdio` | No | Runtime transport. Use `stdio` for local clients; use `http` or `streamable-http` for network exposure. |
| `FINOS_MCP_MCP_HOST` | `127.0.0.1` | For non-stdio | Bind host for network transports. Keep loopback unless behind controlled ingress. |
| `FINOS_MCP_MCP_PORT` | `8000` | For non-stdio | Bind port for network transports. |
| `FINOS_MCP_MCP_AUTH_ENABLED` | `false` | No | Enables JWT boundary authentication. Set `true` for production. |
| `FINOS_MCP_MCP_AUTH_ISSUER` | _(none)_ | If auth enabled | Expected JWT `iss` claim. |
| `FINOS_MCP_MCP_AUTH_AUDIENCE` | _(none)_ | If auth enabled | Expected JWT `aud` claim. |
| `FINOS_MCP_MCP_AUTH_JWKS_URI` | _(none)_ | One of verifier pair | Recommended verifier source (supports key rotation). |
| `FINOS_MCP_MCP_AUTH_PUBLIC_KEY` | _(none)_ | One of verifier pair | Static PEM verifier source. Do not set with `JWKS_URI`. |
| `FINOS_MCP_MCP_AUTH_REQUIRED_SCOPES` | _(none)_ | No | Comma-separated required scopes for all requests. |
| `FINOS_MCP_HTTP_TIMEOUT` | `30` | No | Outbound request timeout in seconds. |
| `FINOS_MCP_ENABLE_CACHE` | `true` | No | In-memory content cache toggle. |
| `FINOS_MCP_CACHE_MAX_SIZE` | `1000` | No | Max entries in cache. Increase carefully with memory limits. |
| `FINOS_MCP_CACHE_TTL_SECONDS` | `3600` | No | Cache TTL in seconds. |
| `FINOS_MCP_GITHUB_TOKEN` | _(none)_ | Recommended | Raises GitHub API limits and stability for dynamic content sync. |
| `FINOS_MCP_LOG_LEVEL` | `INFO` | No | Runtime log verbosity. |
| `FINOS_MCP_DEBUG_MODE` | `false` | No | Enables verbose diagnostics; avoid in production unless troubleshooting. |

Production baseline:
- `FINOS_MCP_MCP_AUTH_ENABLED=true`
- `FINOS_MCP_MCP_TRANSPORT=http` (or `streamable-http`) behind TLS ingress
- `FINOS_MCP_MCP_HOST=127.0.0.1` when fronted by reverse proxy
- Configure `FINOS_MCP_MCP_AUTH_JWKS_URI`, `FINOS_MCP_MCP_AUTH_ISSUER`, `FINOS_MCP_MCP_AUTH_AUDIENCE`

### Go-Live Approval Gate

Run full automated release gates:

```bash
./scripts/go-live-gate.sh
```

Includes:
- tracked-folder hygiene checks
- clean working tree enforcement
- linting and type checks
- regression tests
- live stdio/HTTP/auth transport checks
- dependency vulnerability scan

---

## Content Sources

### Content Coverage
- **Framework Data**: Direct access to governance framework documents
- **Dynamic Loading**: Automatic content fetching from official sources
- **FINOS Content**: AI governance risks and mitigations from [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework), used under CC BY 4.0 license

### Performance Characteristics
- **Response Times**: Fast cached response times with intelligent caching
- **Reliability**: Circuit breaker protection and error boundary management
- **Scalability**: Memory-efficient design with configurable cache limits
- **Security**: Comprehensive DoS protection and request validation

---

## Documentation

### Getting Started
- **[Setup Guide](docs/README.md)** - Connect to your editor (5 minutes)
- **[User Guide](docs/user-guide/)** - Comprehensive usage guide for all tools

### API & Integration
- **[API Documentation](docs/api/)** - Complete API reference for all 11 MCP tools
- **[Framework Architecture](docs/api/framework-architecture.md)** - System design and patterns

### Support & Troubleshooting
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
- **[Tools Reference](docs/tools-reference.md)** - Complete guide to all 11 MCP tools
- **[GitHub Repository](https://github.com/finos/aigf-mcp-server)** - Source code and issues

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and add tests
4. Run quality checks: `./scripts/quality-check.sh`
5. Test with MCP CLI: `mcp list tools`
6. Submit a pull request

---

## Need Help

- [Report Issues](https://github.com/finos/aigf-mcp-server/issues)
- [Ask Questions](https://github.com/finos/aigf-mcp-server/discussions)
- [Full Documentation](docs/README.md)

---

## License

[![Software License](https://img.shields.io/badge/software-Apache%202.0-blue.svg)](LICENSE)
[![Content License](https://img.shields.io/badge/content-CC%20BY%204.0-green.svg)](FINOS-LICENSE.md)

- **Software**: Apache 2.0 License
- **FINOS Content**: CC BY 4.0 License

---
