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
| ![VS Code](https://img.shields.io/badge/VS%20Code-007ACC?style=flat-square&logo=visualstudiocode&logoColor=white) | ✅ **Native MCP Support** | JSON Config | ⭐⭐ Medium |
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

### 🎯 VS Code Quick Start

**Most Popular Setup**: VS Code with GitHub Copilot

1. **Create MCP config** at `~/.vscode/mcp.json`:
   ```json
   {
     "servers": {
       "finos-ai-governance": {
         "command": "/path/to/your/.venv/bin/python",
         "args": ["-m", "finos_mcp.server", "stdio"]
       }
     }
   }
   ```

2. **Find your Python path**:
   ```bash
   # With virtual environment activated
   which python  # Use this path in config above
   ```

3. **Reload VS Code** → Open chat → Ask about AI governance!

💡 **Detailed VS Code instructions** [below](#5-vs-code-with-github-copilot)

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

#### Configuration Methods

**Method 1: Command Line (Recommended)**

```bash
# Add MCP server using Claude Code CLI
claude mcp add finos-ai-governance \
  --env FINOS_MCP_LOG_LEVEL=INFO \
  --env FINOS_MCP_ENABLE_CACHE=true \
  --env FINOS_MCP_GITHUB_TOKEN=ghp_your_token_here \
  -- python -m finos_mcp.server stdio

# List configured servers
claude mcp list

# Get server details
claude mcp get finos-ai-governance
```

**Method 2: Manual Configuration**

**File Location**: `~/.config/claude-code/mcp_servers.json`

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO",
        "FINOS_MCP_DEBUG_MODE": "false",
        "FINOS_MCP_ENABLE_CACHE": "true",
        "FINOS_MCP_GITHUB_TOKEN": "ghp_your_token_here"
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

**Locations**:
- **Project-specific**: `.cursor/mcp.json` in your project directory
- **Global**: `~/.cursor/mcp.json` (macOS/Linux) or `%USERPROFILE%\.cursor\mcp.json` (Windows)

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO",
        "FINOS_MCP_ENABLE_CACHE": "true",
        "FINOS_MCP_GITHUB_TOKEN": "ghp_your_token_here"
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

### 5. VS Code with GitHub Copilot

![VS Code Badge](https://img.shields.io/badge/VS%20Code-Native%20MCP%20Support-007ACC?style=for-the-badge&logo=visualstudiocode)

**Perfect for**: AI-powered development with integrated governance tools via GitHub Copilot

#### Prerequisites

- VS Code 1.95+ with GitHub Copilot extension
- Python 3.9+ installed
- FINOS MCP Server installed

#### Configuration Locations

Choose one based on your needs:

**User-wide configuration**: `~/.vscode/mcp.json` (macOS/Linux) or `%USERPROFILE%\.vscode\mcp.json` (Windows)
**Workspace-specific**: `<your-project>/.vscode/mcp.json`

#### Virtual Environment Support

**Option 1: Global Installation**
```bash
# Install globally (easiest setup)
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
pip install -e .

# Verify global installation
python -c "import finos_mcp; print('✅ FINOS MCP Server Ready!')"
```

Configuration for global installation:
```json
{
  "servers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"]
    }
  }
}
```

**Option 2: Virtual Environment (Recommended for Development)**
```bash
# Create project with virtual environment
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows

# Install MCP server
pip install -e .

# Get the full path to the virtual environment's Python
which python  # macOS/Linux: /path/to/project/.venv/bin/python
# where python  # Windows: C:\path\to\project\.venv\Scripts\python.exe
```

Configuration for virtual environment:
```json
{
  "servers": {
    "finos-ai-governance": {
      "command": "/full/path/to/your/project/.venv/bin/python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO",
        "FINOS_MCP_ENABLE_CACHE": "true",
        "FINOS_MCP_HTTP_TIMEOUT": "30",
        "FINOS_MCP_GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  },
  "inputs": [
    {
      "type": "promptString",
      "id": "github-token",
      "description": "Enter your GitHub token for higher rate limits (optional)"
    }
  ]
}
```

#### Step-by-Step Setup

1. **Install FINOS MCP Server**

   Choose your installation method:

   **For Global Use:**
   ```bash
   git clone https://github.com/hugo-calderon/finos-mcp-server.git
   cd finos-mcp-server
   pip install -e .
   ```

   **For Development/Isolated Use:**
   ```bash
   git clone https://github.com/hugo-calderon/finos-mcp-server.git
   cd finos-mcp-server
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -e .
   ```

2. **Create MCP Configuration**

   Create `mcp.json` in your chosen location with the appropriate configuration above.

   **Important**: Replace `/full/path/to/your/project/.venv/bin/python` with your actual virtual environment path.

3. **Find Your Virtual Environment Path**
   ```bash
   # While your virtual environment is activated
   which python    # macOS/Linux
   where python    # Windows
   ```

4. **Reload VS Code**
   - Press `Ctrl/Cmd + Shift + P`
   - Run "Developer: Reload Window"
   - Or restart VS Code completely

5. **Test Integration**
   - Open VS Code chat (`Ctrl/Cmd + Alt + I`)
   - Type: `@workspace What AI governance mitigations are available?`
   - You should see the MCP server tools become available

#### Troubleshooting

**🚨 Common Issues:**

1. **Server Not Starting:**
   ```bash
   # Verify Python path is correct
   ls -la /path/to/.venv/bin/python

   # Test server manually
   /path/to/.venv/bin/python -m finos_mcp.server stdio
   ```

2. **"Command not found" errors:**
   - Ensure you're using absolute paths in `mcp.json`
   - Check VS Code Output panel → "MCP Servers" for detailed error messages

3. **Virtual environment not found:**
   ```bash
   # Find your current Python path
   which python
   # Copy the full path to your mcp.json config
   ```

4. **Missing dependencies:**
   ```bash
   # Reinstall with all dependencies
   cd finos-mcp-server
   source .venv/bin/activate
   pip install -e .
   ```

5. **Permission Issues:**
   ```bash
   # On macOS/Linux
   chmod +x /path/to/.venv/bin/python

   # On Windows: Run VS Code as Administrator if needed
   ```

6. **Rate Limiting:**
   - Add your GitHub token to avoid API rate limits
   - Get token at: https://github.com/settings/tokens (needs `public_repo` scope)
   - Add to your `mcp.json` env variables

**🔍 Debugging Steps:**
1. Check VS Code Output panel → "MCP Servers"
2. Verify server works standalone: `.venv/bin/python -m finos_mcp.server stdio`
3. Test configuration with a simple example first
4. Restart VS Code completely after config changes

#### Usage in VS Code

Once configured, you can:

1. **In Chat**: `@workspace What are the AI governance risks related to data privacy?`
2. **In Agent Mode**: Ask Copilot to help implement governance controls
3. **Tool Discovery**: All FINOS governance tools become available automatically

---

### 6. Continue.dev

![Continue Badge](https://img.shields.io/badge/Continue.dev-Popular%20Extension-black?style=for-the-badge&logo=github)

**Perfect for**: AI-powered code completion and chat in VS Code

#### Prerequisites

- VS Code with Continue extension installed
- MCP can only be used in **agent mode**

#### Configuration

**Location**: Create `.continue/mcpServers/` folder in your workspace

Create a file called `finos-ai-governance.yaml`:

```yaml
name: FINOS AI Governance
mcpServer:
  version: 0.0.1
  schema: v1

mcpServers:
  - name: finos-ai-governance
    command: python
    args:
      - "-m"
      - "finos_mcp.server"
      - "stdio"
    env:
      FINOS_MCP_LOG_LEVEL: INFO
      FINOS_MCP_ENABLE_CACHE: "true"
      FINOS_MCP_GITHUB_TOKEN: "ghp_your_token_here"
```

**Alternative JSON Configuration** (in Continue config file):

```json
{
  "mcpServers": [
    {
      "name": "finos-ai-governance",
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO",
        "FINOS_MCP_ENABLE_CACHE": "true"
      }
    }
  ]
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

3. **Configure MCP Server**
   - Create `.continue/mcpServers/` folder in your workspace
   - Add the YAML configuration file above
   - Or use `Ctrl/Cmd + Shift + P` → "Continue: Edit Config" for JSON method

4. **Switch to Agent Mode**
   - MCP servers only work in Continue's agent mode
   - Use the agent chat interface to access FINOS governance tools

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
| **Development Workflows** | VS Code + Copilot | Native MCP support, comprehensive tooling |
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
