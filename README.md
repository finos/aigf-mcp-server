# 🛡️ FINOS AI Governance MCP Server

[![GitHub Actions](https://github.com/hugo-calderon/finos-mcp-server/workflows/CI/badge.svg)](https://github.com/hugo-calderon/finos-mcp-server/actions)
[![Coverage Status](https://img.shields.io/badge/coverage-80%2B%25-brightgreen)](https://github.com/hugo-calderon/finos-mcp-server/actions)
[![Type Checking](https://img.shields.io/badge/mypy-strict-blue)](https://github.com/hugo-calderon/finos-mcp-server/actions)
[![Security Scan](https://img.shields.io/badge/security-bandit%20%7C%20semgrep-green)](https://github.com/hugo-calderon/finos-mcp-server/actions)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![MCP Protocol](https://img.shields.io/badge/MCP-2024--11--05-orange)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

> **Professional Model Context Protocol (MCP) server providing intelligent access to AI governance frameworks**

Transform your AI governance workflow with enterprise-grade access to the [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework). Built for developers, compliance teams, and AI practitioners who need reliable, structured access to governance content.

---

## 📋 Table of Contents

- [What It Does](#what-it-does)
- [Quick Start](#quick-start)
- [Client Integration](#client-integration)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Documentation](#documentation)
- [🔧 Development](#development)
- [About](#about)

---

## What It Does

This enterprise-ready MCP server exposes comprehensive AI governance content through a modern, async protocol:

### Governance Content Access
- 🛡️ **17 AI Governance Mitigations** (mi-1 through mi-17)
- ⚠️ **23 AI Risk Assessments** (ri-1 through ri-23)
- 🔍 **Intelligent Search** across all governance documentation
- 📈 **Real-time Content Updates** from FINOS repository

### Enterprise Features
- ⚡ **Async Performance** with intelligent caching
- 🔒 **Security-First** design with rate limiting
- 📊 **Health Monitoring** and diagnostics
- 🔧 **Type-Safe** implementation with strict MyPy checking

## Quick Start

### Installation (< 2 minutes)

```bash
# 1️⃣ Clone and setup
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server

# 2️⃣ Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3️⃣ Install in development mode
pip install -e .

# 4️⃣ Verify installation
finos-mcp --help
```

## 🔌 Client Integration

Ready to integrate with your favorite development environment? The FINOS AI Governance MCP Server supports all major AI assistants and code editors.

### 📋 Supported Clients

<div align="center">

| Client | Status | Configuration | Difficulty |
|--------|--------|---------------|------------|
| ![Claude Desktop](https://img.shields.io/badge/Claude%20Desktop-FF6B35?style=flat-square&logo=anthropic&logoColor=white) | ✅ **Native Support** | JSON Config | ⭐ Easy |
| ![Claude Code](https://img.shields.io/badge/Claude%20Code-4A90E2?style=flat-square&logo=visualstudiocode&logoColor=white) | ✅ **Full Support** | JSON Config | ⭐ Easy |
| ![Cursor](https://img.shields.io/badge/Cursor-000000?style=flat-square&logo=cursor&logoColor=white) | ✅ **MCP Support** | Settings UI | ⭐⭐ Medium |
| ![Windsurf](https://img.shields.io/badge/Windsurf-0084FF?style=flat-square&logo=codestream&logoColor=white) | ✅ **Compatible** | Extension Config | ⭐⭐ Medium |
| ![VS Code](https://img.shields.io/badge/VS%20Code-007ACC?style=flat-square&logo=visualstudiocode&logoColor=white) | ⚠️ **Via Extensions** | Extension Required | ⭐⭐⭐ Hard |
| ![Continue.dev](https://img.shields.io/badge/Continue.dev-000000?style=flat-square&logo=github&logoColor=white) | ✅ **MCP Ready** | VS Code Extension | ⭐⭐ Medium |
| ![Zed](https://img.shields.io/badge/Zed-0F0F0F?style=flat-square&logo=zed&logoColor=white) | ✅ **Growing Support** | Settings Config | ⭐⭐ Medium |
| ![JetBrains](https://img.shields.io/badge/JetBrains-000000?style=flat-square&logo=jetbrains&logoColor=white) | ⚠️ **Plugin Required** | Plugin Config | ⭐⭐⭐ Hard |
| ![Replit](https://img.shields.io/badge/Replit-667881?style=flat-square&logo=replit&logoColor=white) | 🧪 **Beta Support** | Cloud Config | ⭐⭐ Medium |

</div>

### 📖 **[Complete Integration Guide →](docs/integration-guide.md)**

Get step-by-step setup instructions for:
- **9 Supported Clients** with detailed configuration
- **Troubleshooting Guide** for common issues  
- **Advanced Configuration** for enterprise deployments
- **Performance Tuning** and optimization tips

> **📦 Development Status**: This package is currently in development. Install from source using the [Quick Start](#quick-start) instructions above.

## Features

<table>
<tr>
<td width="50%">

### Search & Discovery
- **Intelligent Search** - Natural language queries
- 🏷️ **Tag-based Filtering** - Precise content targeting
- 📊 **Fuzzy Matching** - Find relevant content easily
- ⚡ **Real-time Results** - Sub-second response times

</td>
<td width="50%">

### Content Management
- 📖 **Direct Access** - Get content by ID (mi-1, ri-10)
- 📋 **Bulk Listing** - All mitigations and risks
- 🔄 **Auto-sync** - Latest FINOS framework updates
- 📈 **Usage Analytics** - Track content access patterns

</td>
</tr>
</table>

### Available MCP Tools

| Tool | Description | Example |
|------|-------------|---------|
| `search_mitigations` | 🛡️ Find mitigation strategies | `"data leakage"` |
| `search_risks` | ⚠️ Discover AI risks | `"prompt injection"` |
| `get_mitigation_details` | 📖 Get specific mitigation | `"mi-1"` |
| `get_risk_details` | 📊 Get specific risk | `"ri-10"` |
| `list_all_mitigations` | 📋 List all mitigations | All 17 mitigations |
| `list_all_risks` | 📊 List all risks | All 23 risks |

### Usage Examples
```python
# 🔍 Search for specific governance topics
search_mitigations(query="data leakage prevention")
search_risks(query="model bias and fairness")

# 📖 Get detailed information
get_mitigation_details(mitigation_id="mi-1")  # Data governance
get_risk_details(risk_id="ri-10")            # Prompt injection

# 📋 Explore all available content
list_all_mitigations()  # Browse complete catalog
list_all_risks()        # Full risk assessment library
```

## Technology Stack

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![AsyncIO](https://img.shields.io/badge/AsyncIO-FF6B6B?style=for-the-badge&logo=python&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![httpx](https://img.shields.io/badge/httpx-2E8B57?style=for-the-badge&logo=python&logoColor=white)
![MyPy](https://img.shields.io/badge/MyPy-3776AB?style=for-the-badge&logo=python&logoColor=white)

</div>

### Architecture Highlights
- **🔄 Async-First Design**: Built on Python asyncio for high performance
- **🛡️ Type Safety**: Strict MyPy checking with comprehensive annotations
- **🔧 Modern HTTP**: httpx client with connection pooling and resilience
- **⚡ Smart Caching**: TTL-based caching with LRU eviction
- **📊 Health Monitoring**: Built-in diagnostics and metrics

### Configuration

Create a `.env` file for customization:

```bash
# 🚀 Performance tuning
FINOS_MCP_LOG_LEVEL=INFO
FINOS_MCP_HTTP_TIMEOUT=30
FINOS_MCP_CACHE_TTL=3600

# 🔒 Optional: GitHub token for enhanced rate limits
# Without token: 60 requests/hour | With token: 5000 requests/hour
FINOS_MCP_GITHUB_TOKEN=ghp_your_token_here

# 🏗️ Advanced settings
FINOS_MCP_MAX_RETRIES=3
FINOS_MCP_ENABLE_CACHE=true
```

<details>
<summary>📖 <b>Advanced Configuration Options</b></summary>

For comprehensive configuration options including security settings, monitoring, and enterprise features, see our [Configuration Guide](docs/user/installation-guide.md).

</details>

## Development

<table>
<tr>
<td width="50%">

### Quality Assurance
```bash
# Quick verification
python -c "import finos_mcp; print('✅ Ready!')"
finos-mcp --help

# Full test suite (237 tests)
pytest --cov=finos_mcp

# Quality checks
./scripts/quality-check.sh
```

</td>
<td width="50%">

### Project Health
- ✅ **237 Tests Passing** (80%+ coverage)
- 🔒 **Security Scanned** (Bandit + Semgrep)
- **Type Safe** (Strict MyPy)
- 🚀 **CI/CD Pipeline** (GitHub Actions)

</td>
</tr>
</table>

### Development Quick Start
```bash
# Setup development environment
./scripts/dev-setup.sh

# Run tests
python -m pytest tests/unit/ -v

# Quality validation
./scripts/quality-check.sh
```

## Documentation

<div align="center">

| **Guide** | **Audience** | **Description** |
|-------------|------------------|-------------------|
| [📚 Complete Docs](docs/README.md) | Everyone | Master navigation hub |
| [🔌 Integration Guide](docs/integration-guide.md) | Users | Client setup & configuration |
| [👥 User Guide](docs/user/README.md) | End Users | Installation & usage |
| [🛠️ Developer Guide](docs/developer/README.md) | Contributors | Development & contributing |
| [🚀 Operations Guide](docs/operations/README.md) | DevOps Teams | Production deployment |

</div>

## About

<div align="center">

**Mission**: *Making AI governance knowledge accessible to everyone through simple, modern tools*

</div>

This initiative bridges the gap between comprehensive AI governance frameworks and practical implementation. By connecting the wealth of knowledge in the [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework) with modern development workflows, we're making it easier for teams to build responsible AI systems.

**Content Attribution**: AI governance content is sourced from the FINOS AI Governance Framework by FINOS and contributors, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

### Why We Built This
- **📚 Knowledge Sharing**: Transform complex governance documents into accessible, searchable tools
- **🔗 Bridge Building**: Connect governance frameworks with day-to-day development practices
- **⚡ Simplicity First**: Make AI governance guidance available right where developers work
- **🤝 Community Impact**: Enable teams worldwide to build more responsible AI systems

---

<div align="center">

### License

[![Software License](https://img.shields.io/badge/software-Apache%202.0-blue.svg)](LICENSE)
[![Content License](https://img.shields.io/badge/content-CC%20BY%204.0-green.svg)](FINOS-LICENSE.md)

**Dual License Structure:**
- **Software Code**: Apache 2.0 License - see [LICENSE](LICENSE)
- **FINOS Content**: CC BY 4.0 License - see [FINOS-LICENSE.md](FINOS-LICENSE.md)

This project provides software under Apache 2.0 that accesses AI governance content from the [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework), which is licensed under Creative Commons Attribution 4.0 International License.

---

**Star this project** | **Fork & Contribute** | **Share with your team**

Made with ❤️ for the AI governance community

</div>
