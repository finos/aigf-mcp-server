# 🔌 MCP Client Integration Guide

Comprehensive guide for integrating the FINOS AI Governance MCP Server with popular development environments and AI assistants.

---

## 📋 Supported Clients

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

---

## 🚀 Quick Setup

### Prerequisites

Ensure you have the MCP server installed:

> **📦 Development Status**: This package is currently in development and not yet published to PyPI. Use the source installation method below.

```bash
# Install from source
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .

# Verify installation
python -c "import finos_mcp; print('✅ Ready!')"
```

---

## 📱 Client-Specific Guides

### 1. Claude Desktop

![Claude Desktop Badge](https://img.shields.io/badge/Claude%20Desktop-Recommended-success?style=for-the-badge&logo=anthropic)

**Perfect for**: General AI conversations, research, content analysis

#### Configuration

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

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
        "FINOS_MCP_CACHE_TTL_SECONDS": "3600",
        "FINOS_MCP_GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

#### Setup Steps

1. **Install MCP Server**
   ```bash
   git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
   ```

2. **Create/Edit Configuration**
   - Open the config file location for your platform
   - Add the JSON configuration above
   - Optionally add your GitHub token for higher rate limits

3. **Restart Claude Desktop**
   - Completely quit Claude Desktop
   - Relaunch the application
   - Verify "finos-ai-governance" appears in available tools

4. **Test Integration**
   ```
   Can you search for AI governance mitigations related to data privacy?
   ```

---

### 2. Claude Code

![Claude Code Badge](https://img.shields.io/badge/Claude%20Code-Developer%20Focused-blue?style=for-the-badge&logo=visualstudiocode)

**Perfect for**: Code review with governance, development workflows

#### Configuration

**All Platforms**: `~/.config/claude-code/mcp_servers.json`

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO",
        "FINOS_MCP_DEBUG_MODE": "false",
        "FINOS_MCP_ENABLE_CACHE": "true"
      }
    }
  }
}
```

#### Setup Steps

1. **Install Claude Code Extension**
   - Open VS Code
   - Install "Claude Code" from the marketplace
   - Sign in to your Anthropic account

2. **Install MCP Server**
   ```bash
   git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
   ```

3. **Create Configuration Directory**
   ```bash
   mkdir -p ~/.config/claude-code
   ```

4. **Add Configuration File**
   - Create `mcp_servers.json` with the configuration above

5. **Restart VS Code**
   - Close VS Code completely
   - Relaunch and activate Claude Code
   - MCP server should be available

---

### 3. Cursor

![Cursor Badge](https://img.shields.io/badge/Cursor-AI%20First-black?style=for-the-badge&logo=cursor)

**Perfect for**: AI-assisted development, code generation with governance

#### Configuration Method 1: Settings UI

1. **Install MCP Server**
   ```bash
   git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
   ```

2. **Open Cursor Settings**
   - Press `Cmd/Ctrl + ,` to open settings
   - Search for "MCP" or navigate to Extensions → MCP

3. **Add Server Configuration**
   - Click "Add Server"
   - **Name**: `finos-ai-governance`
   - **Command**: `python`
   - **Args**: `-m finos_mcp.server stdio`
   - **Environment Variables**:
     - `FINOS_MCP_LOG_LEVEL=INFO`
     - `FINOS_MCP_ENABLE_CACHE=true`

#### Configuration Method 2: JSON Config

**Location**: Cursor's settings directory (varies by platform)

```json
{
  "mcp": {
    "servers": {
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
}
```

---

### 4. Windsurf

![Windsurf Badge](https://img.shields.io/badge/Windsurf-Collaborative-0084FF?style=for-the-badge&logo=codestream)

**Perfect for**: Team development, collaborative governance reviews

#### Configuration

Windsurf supports MCP through its extension system or built-in configuration:

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO",
        "FINOS_MCP_ENABLE_CACHE": "true",
        "FINOS_MCP_HTTP_TIMEOUT": "30"
      }
    }
  }
}
```

#### Setup Steps

1. **Install MCP Server**
   ```bash
   git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
   ```

2. **Configure via Windsurf Settings**
   - Open Windsurf preferences
   - Navigate to MCP integration settings
   - Add server configuration as shown above

3. **Alternative: Configuration File**
   - Check Windsurf documentation for config file location
   - Add JSON configuration to appropriate file

---

### 5. VS Code

![VS Code Badge](https://img.shields.io/badge/VS%20Code-Extension%20Required-007ACC?style=for-the-badge&logo=visualstudiocode)

**Perfect for**: Development with MCP-compatible extensions

#### Prerequisites

VS Code doesn't have native MCP support. You need an MCP-compatible extension:

- **Claude Code** (recommended)
- **Continue** (with MCP support)
- **Codeium** (with MCP integration)
- Other MCP-compatible extensions

#### Configuration Example

Depends on the extension, but typically:

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

#### Setup Steps

1. **Install MCP-Compatible Extension**
   - Choose from supported extensions above
   - Install from VS Code marketplace

2. **Install MCP Server**
   ```bash
   git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
   ```

3. **Configure Through Extension**
   - Follow extension-specific configuration instructions
   - Add server configuration via extension settings

---

### 6. Continue.dev

![Continue Badge](https://img.shields.io/badge/Continue.dev-Popular%20Extension-black?style=for-the-badge&logo=github)

**Perfect for**: AI-powered code completion and chat in VS Code

#### Configuration

**Location**: VS Code settings or Continue config directory

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

#### Setup Steps

1. **Install Continue Extension**
   - Open VS Code marketplace
   - Search for "Continue" and install

2. **Install MCP Server**
   ```bash
   git clone https://github.com/hugo-calderon/finos-mcp-server.git
   cd finos-mcp-server
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -e .
   ```

3. **Configure Continue**
   - Press `Ctrl/Cmd + Shift + P`
   - Search "Continue: Edit Config"
   - Add MCP server configuration

4. **Test Integration**
   - Open Continue chat
   - Ask: "What AI governance mitigations are available?"

---

### 7. Zed Editor

![Zed Badge](https://img.shields.io/badge/Zed-Modern%20Performance-0F0F0F?style=for-the-badge&logo=zed)

**Perfect for**: High-performance development with modern AI features

#### Configuration

**Location**: Zed settings or extensions directory

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

#### Setup Steps

1. **Install MCP Server**
   ```bash
   git clone https://github.com/hugo-calderon/finos-mcp-server.git
   cd finos-mcp-server
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -e .
   ```

2. **Open Zed Settings**
   - Press `Cmd/Ctrl + ,`
   - Navigate to Extensions or MCP section

3. **Add MCP Configuration**
   - Add server configuration as shown above
   - Save settings

4. **Restart Zed**
   - Close and reopen Zed
   - MCP server should be available

---

### 8. Enterprise Integrations

#### JetBrains IDEs (IntelliJ, PyCharm, WebStorm)

![JetBrains Badge](https://img.shields.io/badge/JetBrains-Professional%20Development-black?style=for-the-badge&logo=jetbrains)

**Perfect for**: Enterprise Java, Python, JavaScript development

**Status**: Requires MCP-compatible plugin

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

**Setup**:
1. Install MCP-compatible plugin from JetBrains marketplace
2. Install FINOS MCP server from source
3. Configure through IDE settings
4. Add server configuration

#### Replit Agent

![Replit Badge](https://img.shields.io/badge/Replit-Cloud%20Development-667881?style=for-the-badge&logo=replit)

**Perfect for**: Educational environments, cloud prototyping

**Status**: Beta MCP support

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_ENABLE_CACHE": "true",
        "FINOS_MCP_HTTP_TIMEOUT": "45"
      }
    }
  }
}
```

**Setup**:
1. Access Replit's MCP settings (beta feature)
2. Add server configuration
3. Test in Replit development environment

---

## ⚙️ Advanced Configuration

### Environment Variables

Customize server behavior across all clients:

```bash
# Essential Settings
FINOS_MCP_LOG_LEVEL=INFO              # Logging level
FINOS_MCP_DEBUG_MODE=false            # Debug mode
FINOS_MCP_ENABLE_CACHE=true           # Enable caching

# Performance Tuning
FINOS_MCP_CACHE_TTL_SECONDS=3600      # Cache lifetime (1 hour)
FINOS_MCP_HTTP_TIMEOUT=30             # HTTP timeout
FINOS_MCP_CACHE_MAX_SIZE=1000         # Maximum cache entries

# GitHub API (Strongly Recommended)
FINOS_MCP_GITHUB_TOKEN=ghp_xxxxxxxxxxxx  # Your GitHub PAT

# Repository Configuration
FINOS_MCP_BASE_URL=https://api.github.com/repos/finos/ai-governance-framework
FINOS_MCP_MITIGATIONS_URL=https://raw.githubusercontent.com/finos/ai-governance-framework/main/mitigations
FINOS_MCP_RISKS_URL=https://raw.githubusercontent.com/finos/ai-governance-framework/main/risks
```

### GitHub Token Setup

To avoid rate limiting, create a GitHub Personal Access Token:

1. **Go to GitHub Settings**
   - Visit: https://github.com/settings/tokens
   - Click "Generate new token (classic)"

2. **Configure Token**
   - **Name**: "FINOS MCP Server"
   - **Scopes**: `public_repo` (read access to public repositories)
   - **Expiration**: Choose appropriate duration

3. **Add to Configuration**
   ```json
   "env": {
     "FINOS_MCP_GITHUB_TOKEN": "ghp_your_token_here"
   }
   ```

### Performance Optimization

```json
{
  "env": {
    "FINOS_MCP_ENABLE_CACHE": "true",
    "FINOS_MCP_CACHE_TTL_SECONDS": "7200",
    "FINOS_MCP_HTTP_TIMEOUT": "45",
    "FINOS_MCP_CACHE_MAX_SIZE": "2000"
  }
}
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Server Not Appearing

**Symptoms**: MCP server doesn't show up in client

**Solutions**:
```bash
# Verify installation
python -c "import finos_mcp; print('✅ Installed')"

# Test server startup
python -m finos_mcp.server stdio --help

# Check configuration syntax
python -m json.tool your_config_file.json
```

#### 2. Connection Errors

**Symptoms**: Server appears but fails to connect

**Solutions**:
```bash
# Test MCP protocol directly
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "clientInfo": {"name": "test", "version": "1.0"}}}' | python -m finos_mcp.server stdio
```

#### 3. Rate Limiting

**Symptoms**: GitHub API rate limit errors

**Solutions**:
- Add `FINOS_MCP_GITHUB_TOKEN` environment variable
- Enable caching: `FINOS_MCP_ENABLE_CACHE=true`
- Increase cache TTL: `FINOS_MCP_CACHE_TTL_SECONDS=7200`

#### 4. Performance Issues

**Symptoms**: Slow response times

**Solutions**:
- Enable caching
- Increase cache size
- Add GitHub token
- Adjust HTTP timeout

### Diagnostic Commands

```bash
# Installation verification
python -c "import finos_mcp; print(f'Version: {finos_mcp.__version__}')"

# Server health check
python -m finos_mcp.server stdio --version

# Protocol test
echo '{"jsonrpc": "2.0", "id": 1, "method": "ping"}' | python -m finos_mcp.server stdio

# Environment check
python -c "
import os
print('Environment Variables:')
for key in sorted(os.environ.keys()):
    if 'FINOS_MCP' in key:
        print(f'  {key}={os.environ[key]}')
"
```

---

## 📚 Usage Examples

Once integrated, you can use these commands in any compatible client:

### Search Operations
```
Find mitigations for data privacy in AI systems
Search for risks related to prompt injection attacks
List all available AI governance mitigations
```

### Detailed Information
```
Get details about mitigation mi-1
Show me risk ri-10 information
What are the implementation steps for mi-4?
```

### Governance Analysis
```
Analyze this code for AI governance risks
What mitigations apply to LLM training data?
Review this AI system design for compliance gaps
```

---

## 🎯 Client Recommendations

| Use Case | Recommended Client | Why |
|----------|-------------------|-----|
| **General AI Assistance** | Claude Desktop | Best user experience, native integration |
| **Development Workflows** | Claude Code | Seamless VS Code integration, code-aware |
| **AI-First Development** | Cursor | Built for AI-assisted coding |
| **Code Completion Focus** | Continue.dev | Popular VS Code extension, 1M+ users |
| **High-Performance Editing** | Zed | Modern, fast editor with growing AI ecosystem |
| **Enterprise Java/Python** | JetBrains IDEs | Professional development, enterprise features |
| **Cloud Development** | Replit Agent | Educational, prototyping, collaborative coding |
| **Team Collaboration** | Windsurf | Collaborative features, governance reviews |
| **Extension Flexibility** | VS Code + Extension | Most customizable, ecosystem benefits |

---

## 📞 Support

Need help with integration? Check these resources:

- 📖 [MCP Protocol Documentation](https://modelcontextprotocol.io)
- 🐛 [Report Issues](https://github.com/hugo-calderon/finos-mcp-server/issues)
- 💬 [Discussion Forum](https://github.com/hugo-calderon/finos-mcp-server/discussions)
- 📧 [Email Support](mailto:hugocalderon@example.com)

---

*Last updated: September 2024*