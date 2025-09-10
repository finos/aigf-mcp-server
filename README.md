# 🛡️ FINOS AI Governance MCP Server

[![GitHub Actions](https://github.com/hugo-calderon/finos-mcp-server/workflows/CI/badge.svg)](https://github.com/hugo-calderon/finos-mcp-server/actions)
[![Coverage Status](https://img.shields.io/badge/coverage-80%2B%25-brightgreen)](https://github.com/hugo-calderon/finos-mcp-server/actions)
[![Type Checking](https://img.shields.io/badge/mypy-strict-blue)](https://github.com/hugo-calderon/finos-mcp-server/actions)
[![Security Scan](https://img.shields.io/badge/security-bandit%20%7C%20semgrep-green)](https://github.com/hugo-calderon/finos-mcp-server/actions)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![MCP Protocol](https://img.shields.io/badge/MCP-2024--11--05-orange)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

> **Professional Model Context Protocol (MCP) server providing intelligent access to AI governance frameworks**

Transform your AI governance workflow with enterprise-grade access to the [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework). Built for developers, compliance teams, and AI practitioners who need reliable, structured access to governance content.

---

## 📋 Table of Contents

- [🎯 What It Does](#-what-it-does)
- [⚡ Quick Start](#-quick-start)
- [🔌 Client Integration](#-client-integration)
- [✨ Features](#-features)
- [🛠️ Technology Stack](#️-technology-stack)
- [📚 Documentation](#-documentation)
- [🔧 Development](#-development)
- [📄 About](#-about)

---

## 🎯 What It Does

This enterprise-ready MCP server exposes comprehensive AI governance content through a modern, async protocol:

### 📊 **Governance Content Access**
- 🛡️ **17 AI Governance Mitigations** (mi-1 through mi-17)
- ⚠️ **23 AI Risk Assessments** (ri-1 through ri-23)
- 🔍 **Intelligent Search** across all governance documentation
- 📈 **Real-time Content Updates** from FINOS repository

### 🏗️ **Enterprise Features**
- ⚡ **Async Performance** with intelligent caching
- 🔒 **Security-First** design with rate limiting
- 📊 **Health Monitoring** and diagnostics
- 🔧 **Type-Safe** implementation with strict MyPy checking

## ⚡ Quick Start

### 🚀 **Installation** (< 2 minutes)

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

### 🔌 **Claude Code Integration**

Add to your Claude Code MCP settings:
```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "finos-mcp",
      "args": [],
      "description": "FINOS AI Governance Framework access"
    }
  }
}
```

### ⚡ **Instant Test**
```bash
# Quick verification
python -c "import finos_mcp; print('✅ Ready to use!')"
finos-mcp --version
```

## 🔌 Client Integration

Connect your FINOS AI Governance MCP Server to popular development environments and AI assistants:

> **📦 Installation Note**: This package is currently in development. Install from source using the [Quick Start](#-quick-start) instructions above.

<div align="center">

[![Claude Desktop](https://img.shields.io/badge/Claude%20Desktop-FF6B35?style=for-the-badge&logo=anthropic&logoColor=white)](#claude-desktop)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-4A90E2?style=for-the-badge&logo=visualstudiocode&logoColor=white)](#claude-code)
[![Cursor](https://img.shields.io/badge/Cursor-000000?style=for-the-badge&logo=cursor&logoColor=white)](#cursor)
[![Continue.dev](https://img.shields.io/badge/Continue.dev-000000?style=for-the-badge&logo=github&logoColor=white)](#continuedev)
[![Zed](https://img.shields.io/badge/Zed-0F0F0F?style=for-the-badge&logo=zed&logoColor=white)](#zed-editor)
[![VS Code](https://img.shields.io/badge/VS%20Code-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)](#vs-code)

</div>

### Claude Desktop

The most straightforward integration for Anthropic's desktop application.

**Configuration File**: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%/Claude/claude_desktop_config.json` (Windows)

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO",
        "FINOS_MCP_ENABLE_CACHE": "true",
        "FINOS_MCP_HTTP_TIMEOUT": "30",
        "FINOS_MCP_CACHE_TTL_SECONDS": "3600"
      }
    }
  }
}
```

**Steps**:
1. Install the MCP server: Clone and install from source (see [Quick Start](#-quick-start))
2. Add the configuration above to your Claude Desktop config file
3. Restart Claude Desktop completely
4. Start using AI governance tools in your conversations

### Claude Code

Perfect for development workflows in VS Code.

**Configuration File**: `~/.config/claude-code/mcp_servers.json`

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO",
        "FINOS_MCP_DEBUG_MODE": "false"
      }
    }
  }
}
```

**Steps**:
1. Install Claude Code extension in VS Code
2. Install MCP server: Clone and install from source (see [Quick Start](#-quick-start))
3. Create configuration file as shown above
4. Restart VS Code and activate Claude Code

### Cursor

AI-powered coding with governance integration.

**Configuration**: Via Cursor's MCP settings or configuration file

```json
{
  "mcp": {
    "servers": {
      "finos-ai-governance": {
        "command": "python",
        "args": ["-m", "finos_mcp.server", "stdio"],
        "env": {
          "FINOS_MCP_LOG_LEVEL": "INFO"
        }
      }
    }
  }
}
```

**Steps**:
1. Install MCP server: Clone and install from source (see [Quick Start](#-quick-start))
2. Open Cursor settings → Extensions → MCP
3. Add server configuration
4. Restart Cursor

### Continue.dev

Popular VS Code extension for AI-powered development.

**Configuration File**: VS Code settings or Continue config

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Steps**:
1. Install Continue.dev extension in VS Code
2. Install MCP server: Clone and install from source (see [Quick Start](#-quick-start))
3. Configure through Continue settings
4. Add MCP server configuration

### Zed Editor

Modern, high-performance editor with growing AI ecosystem.

**Configuration**: Through Zed's extension system

```json
{
  "mcp": {
    "servers": {
      "finos-ai-governance": {
        "command": "python",
        "args": ["-m", "finos_mcp.server", "stdio"],
        "env": {
          "FINOS_MCP_LOG_LEVEL": "INFO"
        }
      }
    }
  }
}
```

**Steps**:
1. Install MCP server: Clone and install from source (see [Quick Start](#-quick-start))
2. Open Zed settings
3. Add MCP configuration
4. Restart Zed

### Windsurf

AI-assisted development environment.

**Configuration File**: Platform-specific MCP configuration

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO",
        "FINOS_MCP_ENABLE_CACHE": "true"
      }
    }
  }
}
```

**Steps**:
1. Install MCP server: Clone and install from source (see [Quick Start](#-quick-start))
2. Configure through Windsurf's MCP integration settings
3. Add server as shown in configuration
4. Restart Windsurf

### VS Code

Using MCP through compatible extensions.

**Prerequisites**: Install an MCP-compatible extension (like Claude Code or similar)

```json
{
  "mcp.servers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Steps**:
1. Install MCP-compatible extension
2. Install MCP server: Clone and install from source (see [Quick Start](#-quick-start))
3. Configure through extension settings
4. Restart VS Code

### 🏢 **Enterprise & Specialized Integrations**

#### JetBrains IDEs (IntelliJ, PyCharm, WebStorm)
![JetBrains](https://img.shields.io/badge/JetBrains-000000?style=flat-square&logo=jetbrains&logoColor=white)

**Status**: Via MCP-compatible plugins
**Use Case**: Professional Java, Python, JavaScript development

```json
{
  "mcp.servers": {
    "finos-ai-governance": {
      "command": "python", 
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

#### Replit Agent
![Replit](https://img.shields.io/badge/Replit-667881?style=flat-square&logo=replit&logoColor=white)

**Status**: Beta MCP support
**Use Case**: Cloud development, education, prototyping

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_ENABLE_CACHE": "true"
      }
    }
  }
}
```

#### GitHub Copilot Enterprise
![GitHub Copilot](https://img.shields.io/badge/GitHub%20Copilot-000000?style=flat-square&logo=github&logoColor=white)

**Status**: Custom integration via GitHub Apps
**Use Case**: Enterprise development workflows

```yaml
# .github/copilot-extensions.yml
mcp_servers:
  - name: finos-ai-governance
    command: python -m finos_mcp.server stdio
    description: AI governance framework access
```

### 🛠️ **Advanced Configuration**

#### Environment Variables

Customize your MCP server behavior:

```bash
# Logging
FINOS_MCP_LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
FINOS_MCP_DEBUG_MODE=false        # Enable debug mode

# Performance  
FINOS_MCP_ENABLE_CACHE=true       # Enable content caching
FINOS_MCP_CACHE_TTL_SECONDS=3600  # Cache TTL (1 hour)
FINOS_MCP_HTTP_TIMEOUT=30         # HTTP timeout seconds

# GitHub API (recommended)
FINOS_MCP_GITHUB_TOKEN=ghp_...    # Personal access token for higher rate limits
```

#### Troubleshooting

**Common Issues**:

1. **Server not appearing in client**
   - Verify Python installation and module accessibility
   - Check configuration file syntax
   - Restart client application completely

2. **Connection errors**
   - Ensure `finos_mcp` module is installed: `python -c "import finos_mcp"`
   - Test server directly: `python -m finos_mcp.server stdio --help`
   - Check environment variables and paths

3. **Rate limiting issues**
   - Add `FINOS_MCP_GITHUB_TOKEN` for higher GitHub API limits
   - Enable caching: `FINOS_MCP_ENABLE_CACHE=true`

**Verification Commands**:

```bash
# Test installation
python -c "import finos_mcp; print('✅ Module installed')"

# Test server startup
python -m finos_mcp.server stdio --help

# Test MCP protocol
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "clientInfo": {"name": "test", "version": "1.0"}}}' | python -m finos_mcp.server stdio
```

### 📖 **Need More Help?**

For comprehensive setup instructions, troubleshooting, and advanced configuration options, see our [**🔌 Complete Integration Guide**](docs/integration-guide.md).

## ✨ Features

<table>
<tr>
<td width="50%">

### 🔍 **Search & Discovery**
- 🎯 **Intelligent Search** - Natural language queries
- 🏷️ **Tag-based Filtering** - Precise content targeting
- 📊 **Fuzzy Matching** - Find relevant content easily
- ⚡ **Real-time Results** - Sub-second response times

</td>
<td width="50%">

### 📚 **Content Management**
- 📖 **Direct Access** - Get content by ID (mi-1, ri-10)
- 📋 **Bulk Listing** - All mitigations and risks
- 🔄 **Auto-sync** - Latest FINOS framework updates
- 📈 **Usage Analytics** - Track content access patterns

</td>
</tr>
</table>

### 🛠️ **Available MCP Tools**

| Tool | Description | Example |
|------|-------------|---------|
| `search_mitigations` | 🛡️ Find mitigation strategies | `"data leakage"` |
| `search_risks` | ⚠️ Discover AI risks | `"prompt injection"` |
| `get_mitigation_details` | 📖 Get specific mitigation | `"mi-1"` |
| `get_risk_details` | 📊 Get specific risk | `"ri-10"` |
| `list_all_mitigations` | 📋 List all mitigations | All 17 mitigations |
| `list_all_risks` | 📊 List all risks | All 23 risks |

### 💡 **Usage Examples**
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

## 🛠️ Technology Stack

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![AsyncIO](https://img.shields.io/badge/AsyncIO-FF6B6B?style=for-the-badge&logo=python&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![httpx](https://img.shields.io/badge/httpx-2E8B57?style=for-the-badge&logo=python&logoColor=white)
![MyPy](https://img.shields.io/badge/MyPy-3776AB?style=for-the-badge&logo=python&logoColor=white)

</div>

### 🏗️ **Architecture Highlights**
- **🔄 Async-First Design**: Built on Python asyncio for high performance
- **🛡️ Type Safety**: Strict MyPy checking with comprehensive annotations
- **🔧 Modern HTTP**: httpx client with connection pooling and resilience
- **⚡ Smart Caching**: TTL-based caching with LRU eviction
- **📊 Health Monitoring**: Built-in diagnostics and metrics

### ⚙️ **Configuration**

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

## 🔧 Development

<table>
<tr>
<td width="50%">

### 🧪 **Quality Assurance**
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

### 📊 **Project Health**
- ✅ **237 Tests Passing** (80%+ coverage)
- 🔒 **Security Scanned** (Bandit + Semgrep)
- 🎯 **Type Safe** (Strict MyPy)
- 🚀 **CI/CD Pipeline** (GitHub Actions)

</td>
</tr>
</table>

### 🛠️ **Development Quick Start**
```bash
# Setup development environment
./scripts/dev-setup.sh

# Run tests
python -m pytest tests/unit/ -v

# Quality validation
./scripts/quality-check.sh
```

## 📚 Documentation

<div align="center">

| 📖 **Guide** | 🎯 **Audience** | 📄 **Description** |
|-------------|------------------|-------------------|
| [📚 Complete Docs](docs/README.md) | Everyone | Master navigation hub |
| [🔌 Integration Guide](docs/integration-guide.md) | Users | Client setup & configuration |
| [👥 User Guide](docs/user/README.md) | End Users | Installation & usage |
| [🛠️ Developer Guide](docs/developer/README.md) | Contributors | Development & contributing |
| [🚀 Operations Guide](docs/operations/README.md) | DevOps Teams | Production deployment |

</div>

## 📄 About

<div align="center">

**🎯 Mission**: *Making AI governance knowledge accessible to everyone through simple, modern tools*

</div>

This initiative bridges the gap between comprehensive AI governance frameworks and practical implementation. By connecting the wealth of knowledge in the [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework) with modern development workflows, we're making it easier for teams to build responsible AI systems.

**Content Attribution**: AI governance content is sourced from the FINOS AI Governance Framework by FINOS and contributors, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

### 🌟 **Why We Built This**
- **📚 Knowledge Sharing**: Transform complex governance documents into accessible, searchable tools
- **🔗 Bridge Building**: Connect governance frameworks with day-to-day development practices
- **⚡ Simplicity First**: Make AI governance guidance available right where developers work
- **🤝 Community Impact**: Enable teams worldwide to build more responsible AI systems

---

<div align="center">

### 📜 **License**

[![Software License](https://img.shields.io/badge/software-Apache%202.0-blue.svg)](LICENSE)
[![Content License](https://img.shields.io/badge/content-CC%20BY%204.0-green.svg)](FINOS-LICENSE.md)

**Dual License Structure:**
- **Software Code**: Apache 2.0 License ([LICENSE](LICENSE))
- **FINOS Content**: CC BY 4.0 License ([FINOS-LICENSE.md](FINOS-LICENSE.md))

This project provides software under Apache 2.0 that accesses AI governance content from the [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework), which is licensed under Creative Commons Attribution 4.0 International License.

---

**⭐ Star this project** | **🍴 Fork & Contribute** | **📢 Share with your team**

Made with ❤️ for the AI governance community

</div>
