# AI Governance MCP Server

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Model Context Protocol (MCP) server providing access to the [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework). This independent project makes AI governance content accessible through development tools.

---

## 📋 Table of Contents

- [What It Does](#what-it-does)
- [Installation](#installation)
- [Client Integration](#client-integration)
- [Available Tools](#available-tools)
- [Documentation](#documentation)
- [Development](#development)
- [About](#about)

## What It Does

This MCP server provides access to AI governance content:

- **17 AI Governance Mitigations** (mi-1 through mi-17)
- **17 AI Risk Assessments** (ri-1, ri-2, ri-3, ri-5 through ri-16, ri-19, ri-23)
- **Search functionality** across governance documentation
- **Content retrieval** from FINOS repository

## Installation

```bash
# Clone repository
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install
pip install -e .

# Verify
finos-mcp --help
```


## Client Integration

This MCP server works with AI assistants and code editors that support the MCP protocol.

### Supported Clients

| Client | Status | Configuration |
|--------|--------|---------------|
| Claude Desktop | ✅ Supported | JSON Config |
| Claude Code | ✅ Supported | JSON Config |
| Cursor | ✅ Supported | Settings UI |
| Continue.dev | ✅ Supported | VS Code Extension |

**[Integration Guide →](docs/integration-guide.md)** - Setup instructions for supported clients

## Available Tools

| Tool | Description |
|------|-------------|
| `search_mitigations` | Find mitigation strategies |
| `search_risks` | Discover AI risks |
| `get_mitigation_details` | Get specific mitigation |
| `get_risk_details` | Get specific risk |
| `list_all_mitigations` | List all mitigations |
| `list_all_risks` | List all risks |
| `get_service_health` | Get service health status |
| `get_service_metrics` | Get service metrics |
| `get_cache_stats` | Get cache statistics |
| `reset_service_health` | Reset service health counters |

### Usage Example

```python
# Search for mitigations
search_result = await search_mitigations("data privacy")

# Get specific mitigation details
mitigation = await get_mitigation_details("mi-1")

# Check service health
health_status = await get_service_health()
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Complete Docs](docs/README.md) | Documentation hub |
| [Integration Guide](docs/integration-guide.md) | Client setup |
| [User Guide](docs/user/README.md) | Installation & usage |
| [Developer Guide](docs/developer/README.md) | Development |
| [Operations Guide](docs/operations/README.md) | Deployment |

## Development

For development work, install with development dependencies:

```bash
# Install with development tools
pip install -e ".[dev,security,test]"

# Run tests
python -m pytest tests/

# Type checking
python -m mypy src/

# Code formatting
python -m ruff check
python -m ruff format
```

## About

This independent project provides MCP server access to the [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework). It makes AI governance content accessible through development tools.

**Content Attribution**: AI governance content is sourced from the FINOS AI Governance Framework, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## License

[![Software License](https://img.shields.io/badge/software-Apache%202.0-blue.svg)](LICENSE)
[![Content License](https://img.shields.io/badge/content-CC%20BY%204.0-green.svg)](FINOS-LICENSE.md)

- **Software**: Apache 2.0 License - see [LICENSE](LICENSE)
- **FINOS Content**: CC BY 4.0 License - see [FINOS-LICENSE.md](FINOS-LICENSE.md)