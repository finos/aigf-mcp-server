# 🔌 MCP Client Integration Guide

Comprehensive guide for integrating this independent MCP server project with popular development environments and AI assistants. This community-driven, enterprise-grade server provides access to FINOS AI governance content with multi-tenant architecture, plugin systems, and advanced performance optimizations.

---

## 📋 Supported Clients

<div align="center">

| Client | Status | Configuration | Difficulty | Enterprise Features |
|--------|--------|---------------|------------|-------------------|
| ![Claude Desktop](https://img.shields.io/badge/Claude%20Desktop-FF6B35?style=flat-square&logo=anthropic&logoColor=white) | ✅ **Native Support** | JSON Config | ⭐ Easy | Multi-tenant ready |
| ![Claude Code](https://img.shields.io/badge/Claude%20Code-4A90E2?style=flat-square&logo=visualstudiocode&logoColor=white) | ✅ **Full Support** | JSON Config | ⭐ Easy | Plugin compatible |
| ![Cursor](https://img.shields.io/badge/Cursor-000000?style=flat-square&logo=cursor&logoColor=white) | ✅ **MCP Support** | Settings UI | ⭐⭐ Medium | Streamable HTTP |
| ![Windsurf](https://img.shields.io/badge/Windsurf-0084FF?style=flat-square&logo=codestream&logoColor=white) | ✅ **Compatible** | Extension Config | ⭐⭐ Medium | OAuth 2.1 ready |
| ![VS Code](https://img.shields.io/badge/VS%20Code-007ACC?style=flat-square&logo=visualstudiocode&logoColor=white) | ✅ **Native MCP Support** | JSON Config | ⭐⭐ Medium | Continue.dev support |
| ![Continue.dev](https://img.shields.io/badge/Continue.dev-000000?style=flat-square&logo=github&logoColor=white) | ✅ **MCP Ready** | VS Code Extension | ⭐⭐ Medium | Tool Output Schemas |
| ![Zed](https://img.shields.io/badge/Zed-0F0F0F?style=flat-square&logo=zed&logoColor=white) | ✅ **Growing Support** | Settings Config | ⭐⭐ Medium | Modern protocol |
| ![JetBrains](https://img.shields.io/badge/JetBrains-000000?style=flat-square&logo=jetbrains&logoColor=white) | ⚠️ **Plugin Required** | Plugin Config | ⭐⭐⭐ Hard | Enterprise auth |

</div>

---

## 🚀 Quick Setup

### Prerequisites

Ensure you have the MCP server installed with enterprise features:

> **📦 Development Status**: This package is currently in development and not yet published to PyPI. Use the source installation method below for full enterprise capabilities.

```bash
# Install from source with enterprise features
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .

# Quick development setup (70% faster)
./scripts/dev-quick-setup.sh

# Verify installation with enterprise features
python -c "import finos_mcp; print('✅ Enterprise Edition Ready!')"
finos-mcp --version
```

### 🎯 VS Code Quick Start (Enterprise)

**Most Popular Setup**: VS Code with GitHub Copilot + Enterprise Features

1. **Create MCP config** at `~/.vscode/mcp.json`:
   ```json
   {
     "servers": {
       "finos-ai-governance": {
         "command": "/path/to/your/.venv/bin/python",
         "args": ["-m", "finos_mcp.server", "stdio"],
         "env": {
           "FINOS_MCP_MULTI_TENANT": "true",
           "FINOS_MCP_PLUGINS_ENABLED": "true",
           "FINOS_MCP_FAST_MODE": "true",
           "FINOS_MCP_LIVE_RELOAD": "true"
         }
       }
     }
   }
   ```

2. **Enterprise Configuration Options**:
   ```bash
   # Multi-tenant setup
   FINOS_MCP_MULTI_TENANT=true
   FINOS_MCP_DEFAULT_TENANT_LIMITS={"max_resources": 100, "max_tools": 50}
   
   # Performance optimizations
   FINOS_MCP_CACHE_TTL=3600
   FINOS_MCP_REQUEST_COALESCING=true
   FINOS_MCP_BACKGROUND_TASKS=true
   ```

3. **Find your Python path**:
   ```bash
   # With virtual environment activated
   which python  # Use this path in config above
   ```

4. **Reload VS Code** → Open chat → Ask about AI governance with enterprise features!

💡 **Detailed enterprise VS Code instructions** [below](#5-vs-code-with-github-copilot-enterprise)

---

## 🏢 Enterprise Features Overview

Before diving into client-specific configurations, here are the enterprise capabilities available:

<table>
<tr>
<td width="50%">

### Multi-Tenant Architecture
- **🔒 Resource Isolation** - Complete tenant separation
- **📊 Usage Limits** - Configurable resource quotas
- **🎯 Context Switching** - Seamless tenant operations
- **🛡️ Security** - Tenant-level access controls

### Plugin System
- **🔌 Extensible Hooks** - before_request, after_request, etc.
- **📦 Plugin Management** - Enable/disable, lifecycle
- **⚡ Error Resilience** - Plugin failures don't break core
- **🎛️ Configuration** - Per-plugin settings

</td>
<td width="50%">

### Performance & Scale
- **🚀 Request Coalescing** - 70% faster identical requests
- **💾 Smart Caching** - TTL + LRU with warming
- **⚙️ Background Tasks** - Non-blocking operations
- **📈 Metrics** - Real-time performance monitoring

### Developer Experience
- **🔄 Live Reload** - Real-time code updates
- **🧪 Interactive Testing** - CLI-based test runner
- **🏗️ Code Generation** - Auto-generate MCP tools
- **✅ Quality Gates** - Automated code quality

</td>
</tr>
</table>

---

## 📱 Client-Specific Guides

### 1. Claude Desktop (Enterprise)

![Claude Desktop Badge](https://img.shields.io/badge/Claude%20Desktop-Enterprise%20Ready-success?style=for-the-badge&logo=anthropic)

**Perfect for**: General AI conversations with multi-tenant governance access

#### Enterprise Configuration

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
        "FINOS_MCP_GITHUB_TOKEN": "ghp_your_token_here",
        
        "FINOS_MCP_MULTI_TENANT": "true",
        "FINOS_MCP_DEFAULT_TENANT": "enterprise_user",
        "FINOS_MCP_TENANT_LIMITS": "{\"max_resources\": 100, \"max_tools\": 50}",
        
        "FINOS_MCP_PLUGINS_ENABLED": "true",
        "FINOS_MCP_PLUGIN_PATH": "/path/to/plugins",
        
        "FINOS_MCP_PERFORMANCE_MODE": "optimized",
        "FINOS_MCP_REQUEST_COALESCING": "true",
        "FINOS_MCP_BACKGROUND_TASKS": "true"
      }
    }
  }
}
```

#### Multi-Tenant Usage Examples

```
@finos-ai-governance What mitigations are available for tenant "finance_team"?
@finos-ai-governance List all governance resources for tenant "dev_team"
@finos-ai-governance Switch to tenant context "compliance_team" and search risks
```

---

### 2. Claude Code (Enterprise)

![Claude Code Badge](https://img.shields.io/badge/Claude%20Code-Developer%20Enterprise-blue?style=for-the-badge&logo=visualstudiocode)

**Perfect for**: Code review with governance, development workflows, plugin development

#### Enterprise Configuration Methods

**Method 1: Command Line with Enterprise Features**

```bash
# Add MCP server with enterprise configuration
claude mcp add finos-ai-governance \
  --env FINOS_MCP_LOG_LEVEL=INFO \
  --env FINOS_MCP_ENABLE_CACHE=true \
  --env FINOS_MCP_GITHUB_TOKEN=ghp_your_token_here \
  --env FINOS_MCP_MULTI_TENANT=true \
  --env FINOS_MCP_PLUGINS_ENABLED=true \
  --env FINOS_MCP_FAST_MODE=true \
  --env FINOS_MCP_LIVE_RELOAD=true \
  -- python -m finos_mcp.server stdio

# List configured servers with enterprise features
claude mcp list --show-enterprise

# Get detailed server configuration
claude mcp get finos-ai-governance --verbose
```

**Method 2: Enterprise Manual Configuration**

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
        "FINOS_MCP_GITHUB_TOKEN": "ghp_your_token_here",
        
        "FINOS_MCP_MULTI_TENANT": "true",
        "FINOS_MCP_DEFAULT_TENANT_LIMITS": "{\"max_resources\": 100, \"max_tools\": 50}",
        
        "FINOS_MCP_PLUGINS_ENABLED": "true",
        "FINOS_MCP_PLUGIN_DISCOVERY": "auto",
        
        "FINOS_MCP_PERFORMANCE_OPTIMIZATIONS": "true",
        "FINOS_MCP_REQUEST_COALESCING": "true",
        "FINOS_MCP_SMART_CACHING": "true",
        "FINOS_MCP_BACKGROUND_PROCESSING": "true",
        
        "FINOS_MCP_DEVELOPER_MODE": "true",
        "FINOS_MCP_LIVE_RELOAD": "true",
        "FINOS_MCP_INTERACTIVE_TESTING": "true"
      }
    }
  }
}
```

#### Enterprise Development Workflow

```bash
# Start with fast development mode
./scripts/dev-quick-setup.sh

# Launch live reload server
python -m finos_mcp.internal.developer_productivity_tools &

# Interactive testing while developing
python -c "from finos_mcp.internal.developer_productivity_tools import InteractiveTestingCLI; InteractiveTestingCLI().run()"
```

---

### 3. Cursor (Enterprise)

![Cursor Badge](https://img.shields.io/badge/Cursor-Enterprise%20AI-black?style=for-the-badge&logo=cursor)

**Perfect for**: AI-first development with streamable HTTP and modern protocol features

#### Enterprise Configuration with Latest MCP Features

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
        "FINOS_MCP_GITHUB_TOKEN": "ghp_your_token_here",
        
        "FINOS_MCP_PROTOCOL_VERSION": "latest",
        "FINOS_MCP_STREAMABLE_HTTP": "true",
        "FINOS_MCP_TOOL_OUTPUT_SCHEMAS": "true",
        "FINOS_MCP_OAUTH2_ENABLED": "true",
        
        "FINOS_MCP_MULTI_TENANT": "true",
        "FINOS_MCP_PLUGIN_ARCHITECTURE": "true",
        
        "FINOS_MCP_PERFORMANCE_PROFILE": "high_throughput",
        "FINOS_MCP_REQUEST_COALESCING": "true",
        "FINOS_MCP_SMART_CACHING": "advanced"
      },
      "capabilities": {
        "streamableHttp": true,
        "toolOutputSchemas": true,
        "multiTenant": true,
        "pluginSystem": true
      }
    }
  }
}
```

#### Modern Protocol Features

```bash
# Test streamable HTTP support
curl -X POST http://localhost:8080/mcp/stream \
  -H "Content-Type: application/json" \
  -d '{"method": "search_mitigations", "params": {"query": "data privacy"}}'

# OAuth 2.1 authentication setup
export FINOS_MCP_OAUTH_CLIENT_ID="your_client_id"
export FINOS_MCP_OAUTH_REDIRECT_URI="http://localhost:8080/oauth/callback"
```

---

### 4. Windsurf (Enterprise Collaboration)

![Windsurf Badge](https://img.shields.io/badge/Windsurf-Team%20Enterprise-0084FF?style=for-the-badge&logo=codestream)

**Perfect for**: Team development, collaborative governance reviews, multi-tenant workflows

#### Team Enterprise Configuration

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
        "FINOS_MCP_GITHUB_TOKEN": "ghp_team_token_here",
        
        "FINOS_MCP_MULTI_TENANT": "true",
        "FINOS_MCP_TEAM_MODE": "collaborative",
        "FINOS_MCP_TENANT_ISOLATION": "strict",
        
        "FINOS_MCP_COLLABORATION_FEATURES": "true",
        "FINOS_MCP_AUDIT_LOGGING": "true",
        "FINOS_MCP_ROLE_BASED_ACCESS": "true",
        
        "FINOS_MCP_ENTERPRISE_SECURITY": "enabled",
        "FINOS_MCP_TEAM_ANALYTICS": "true"
      }
    }
  },
  "teamConfiguration": {
    "tenants": {
      "frontend_team": {"max_resources": 50},
      "backend_team": {"max_resources": 100},
      "compliance_team": {"max_resources": 200, "admin": true}
    }
  }
}
```

---

### 5. VS Code with GitHub Copilot (Enterprise)

![VS Code Badge](https://img.shields.io/badge/VS%20Code-Enterprise%20Native-007ACC?style=for-the-badge&logo=visualstudiocode)

**Perfect for**: Enterprise development with full MCP support, multi-tenant workflows, plugin development

#### Enterprise Prerequisites

- VS Code 1.95+ with GitHub Copilot extension
- Python 3.10+ installed
- FINOS MCP Enterprise Server installed
- Multi-tenant configuration ready

#### Enterprise Configuration Locations

Choose based on your enterprise setup:

**Team/Organization-wide**: `~/.vscode/mcp.json` (macOS/Linux) or `%USERPROFILE%\.vscode\mcp.json` (Windows)
**Project-specific**: `<your-project>/.vscode/mcp.json`
**Enterprise template**: `/shared/enterprise-configs/mcp/enterprise-template.json`

#### Enterprise Virtual Environment Setup

**Option 1: Enterprise Shared Installation**
```bash
# Install in shared enterprise location
git clone https://github.com/hugo-calderon/finos-mcp-server.git /opt/finos-mcp
cd /opt/finos-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Create enterprise configuration template
sudo mkdir -p /shared/enterprise-configs/mcp
sudo cp config/enterprise-template.json /shared/enterprise-configs/mcp/
```

**Option 2: Developer Workspace with Enterprise Features**
```bash
# Create project with enterprise features
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server

# Quick enterprise setup
./scripts/dev-quick-setup.sh

# Activate environment with enterprise features
source .venv/bin/activate

# Get path for configuration
which python  # Use this path in enterprise config
```

#### Enterprise Configuration Template

```json
{
  "servers": {
    "finos-ai-governance": {
      "command": "/opt/finos-mcp/.venv/bin/python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO",
        "FINOS_MCP_ENABLE_CACHE": "true",
        "FINOS_MCP_HTTP_TIMEOUT": "30",
        "FINOS_MCP_GITHUB_TOKEN": "${ENTERPRISE_GITHUB_TOKEN}",
        
        "FINOS_MCP_MULTI_TENANT": "true",
        "FINOS_MCP_DEFAULT_TENANT": "${USER_TENANT}",
        "FINOS_MCP_TENANT_LIMITS": "{\"max_resources\": 100, \"max_tools\": 50}",
        "FINOS_MCP_TENANT_ISOLATION": "strict",
        
        "FINOS_MCP_PLUGINS_ENABLED": "true",
        "FINOS_MCP_PLUGIN_PATH": "/opt/finos-mcp/plugins",
        "FINOS_MCP_PLUGIN_DISCOVERY": "enterprise",
        
        "FINOS_MCP_PERFORMANCE_MODE": "enterprise",
        "FINOS_MCP_REQUEST_COALESCING": "true",
        "FINOS_MCP_SMART_CACHING": "advanced",
        "FINOS_MCP_BACKGROUND_PROCESSING": "true",
        "FINOS_MCP_CONCURRENT_REQUESTS": "100",
        
        "FINOS_MCP_ENTERPRISE_FEATURES": "all",
        "FINOS_MCP_AUDIT_LOGGING": "true",
        "FINOS_MCP_METRICS_COLLECTION": "true",
        "FINOS_MCP_SECURITY_ENHANCED": "true",
        
        "FINOS_MCP_DEVELOPER_PRODUCTIVITY": "true",
        "FINOS_MCP_LIVE_RELOAD": "true",
        "FINOS_MCP_INTERACTIVE_TESTING": "true",
        "FINOS_MCP_CODE_GENERATION": "true"
      }
    }
  },
  "enterpriseConfig": {
    "tenantMapping": {
      "defaultTenant": "user_${USER}",
      "teamTenants": ["frontend", "backend", "compliance", "security"],
      "adminTenants": ["compliance", "security"]
    },
    "pluginPolicy": {
      "allowedPlugins": ["audit", "security", "performance"],
      "requiredPlugins": ["audit"]
    }
  }
}
```

#### Enterprise Development Workflow

```bash
# 🚀 Fast enterprise development setup
./scripts/dev-quick-setup.sh

# ⚡ Fast test mode with enterprise features
./scripts/dev-test-focused.sh

# 🔄 Live reload server with multi-tenant support
python -m finos_mcp.internal.developer_tools

# 🧪 Interactive testing with tenant switching
python -c "
from finos_mcp.internal.developer_productivity_tools import InteractiveTestingCLI
cli = InteractiveTestingCLI(enterprise_mode=True)
cli.run_interactive_session()
"

# 🏗️ Generate enterprise MCP tools
python -m finos_mcp.internal.code_quality_automation --generate-enterprise-tools

# ✅ Run quality gates with enterprise standards
./scripts/quality-check.sh --fix
```

#### Enterprise Usage Examples

```bash
# Multi-tenant operations
"@workspace What governance mitigations are available for tenant 'frontend_team'?"
"@workspace Switch to tenant 'compliance_team' and list all risks"
"@workspace Create a governance report for tenant 'backend_team'"

# Plugin-enhanced operations
"@workspace Use the audit plugin to analyze this code for governance compliance"
"@workspace Generate security documentation using the security plugin"

# Performance-optimized queries
"@workspace Search for data privacy mitigations (use request coalescing)"
"@workspace Batch analyze these files for AI governance risks"
```

---

### 6. Continue.dev (Enterprise)

![Continue Badge](https://img.shields.io/badge/Continue.dev-Enterprise%20Extension-black?style=for-the-badge&logo=github)

**Perfect for**: Enterprise AI-powered code completion with governance integration

#### Enterprise Prerequisites

- VS Code with Continue extension installed
- Enterprise MCP server with plugin support
- Multi-tenant configuration

#### Enterprise Configuration

**Location**: Create `.continue/mcpServers/` folder in your workspace

Create `finos-ai-governance-enterprise.yaml`:

```yaml
name: FINOS AI Governance Enterprise
mcpServer:
  version: 1.0.0
  schema: enterprise_v1
  enterpriseFeatures:
    multiTenant: true
    plugins: true
    performance: optimized

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
      FINOS_MCP_GITHUB_TOKEN: "ghp_enterprise_token"
      
      FINOS_MCP_MULTI_TENANT: "true"
      FINOS_MCP_DEFAULT_TENANT: "${CONTINUE_USER_TENANT}"
      FINOS_MCP_TENANT_CONTEXT_SWITCHING: "true"
      
      FINOS_MCP_PLUGINS_ENABLED: "true"
      FINOS_MCP_PLUGIN_PATH: "/path/to/plugins"
      
      FINOS_MCP_PERFORMANCE_ENTERPRISE: "true"
      FINOS_MCP_REQUEST_COALESCING: "true"
      FINOS_MCP_SMART_CACHING: "advanced"
    
    enterpriseConfig:
      tenantIsolation: strict
      auditLogging: true
      performanceMetrics: true
      securityEnhanced: true
```

---

### 7. Enterprise Integrations

#### JetBrains IDEs (Enterprise)

![JetBrains Badge](https://img.shields.io/badge/JetBrains-Enterprise%20Professional-black?style=for-the-badge&logo=jetbrains)

**Perfect for**: Large-scale enterprise Java, Python, JavaScript development

```json
{
  "mcp.enterprise.servers": {
    "finos-ai-governance": {
      "command": "python",
      "args": ["-m", "finos_mcp.server", "stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO",
        "FINOS_MCP_ENTERPRISE_MODE": "true",
        "FINOS_MCP_MULTI_TENANT": "true",
        "FINOS_MCP_ENTERPRISE_AUTH": "jetbrains_sso",
        "FINOS_MCP_TEAM_INTEGRATION": "true"
      },
      "enterpriseFeatures": {
        "singleSignOn": true,
        "teamWorkspaces": true,
        "auditTrails": true,
        "complianceReporting": true
      }
    }
  }
}
```

---

## ⚙️ Advanced Enterprise Configuration

### Multi-Tenant Environment Variables

```bash
# Multi-Tenant Configuration
FINOS_MCP_MULTI_TENANT=true                    # Enable multi-tenancy
FINOS_MCP_DEFAULT_TENANT="default_user"        # Default tenant ID
FINOS_MCP_TENANT_ISOLATION="strict"            # Isolation level: loose|strict
FINOS_MCP_MAX_TENANTS=100                      # Maximum number of tenants
FINOS_MCP_TENANT_LIMITS='{"max_resources": 100, "max_tools": 50}'

# Tenant-specific settings
FINOS_MCP_TENANT_CONFIG_PATH="/etc/finos-mcp/tenants"
FINOS_MCP_TENANT_CONTEXT_SWITCHING=true
FINOS_MCP_TENANT_RESOURCE_MONITORING=true
```

### Plugin System Configuration

```bash
# Plugin System
FINOS_MCP_PLUGINS_ENABLED=true                 # Enable plugin system
FINOS_MCP_PLUGIN_PATH="/opt/finos-mcp/plugins" # Plugin directory
FINOS_MCP_PLUGIN_DISCOVERY="auto"              # auto|manual|enterprise
FINOS_MCP_PLUGIN_SECURITY="sandbox"            # sandbox|restricted|open
FINOS_MCP_MAX_PLUGINS=50                       # Maximum loaded plugins

# Plugin development
FINOS_MCP_PLUGIN_DEV_MODE=true
FINOS_MCP_PLUGIN_HOT_RELOAD=true
FINOS_MCP_PLUGIN_DEBUG_LOGGING=true
```

### Performance Optimization (Enterprise)

```bash
# Performance & Scalability
FINOS_MCP_PERFORMANCE_MODE="enterprise"        # basic|optimized|enterprise
FINOS_MCP_REQUEST_COALESCING=true              # Batch identical requests
FINOS_MCP_SMART_CACHING="advanced"             # basic|advanced|intelligent
FINOS_MCP_BACKGROUND_PROCESSING=true           # Non-blocking operations
FINOS_MCP_CONCURRENT_REQUESTS=100              # Max concurrent requests
FINOS_MCP_CONNECTION_POOLING=true              # HTTP connection pooling

# Cache configuration
FINOS_MCP_CACHE_TTL_SECONDS=7200               # 2-hour cache lifetime
FINOS_MCP_CACHE_MAX_SIZE=5000                  # Maximum cache entries
FINOS_MCP_CACHE_WARMING=true                   # Proactive cache warming
FINOS_MCP_CACHE_COMPRESSION=true               # Compress cached data
```

### Developer Productivity Features

```bash
# Developer Experience
FINOS_MCP_DEVELOPER_MODE=true                  # Enhanced developer features
FINOS_MCP_LIVE_RELOAD=true                     # Real-time code updates
FINOS_MCP_INTERACTIVE_TESTING=true             # CLI test runner
FINOS_MCP_CODE_GENERATION=true                 # Auto-generate tools
FINOS_MCP_FAST_TEST_MODE=true                  # 70% faster tests

# Quality assurance
FINOS_MCP_AUTO_QUALITY_CHECKS=true             # Automated quality gates
FINOS_MCP_PRE_COMMIT_HOOKS=true                # Pre-commit validation
FINOS_MCP_CODE_FORMATTING=true                 # Auto-formatting
FINOS_MCP_TYPE_CHECKING="strict"               # Type safety level
```

### Enterprise Security & Compliance

```bash
# Security & Compliance
FINOS_MCP_ENTERPRISE_SECURITY=true             # Enhanced security features
FINOS_MCP_AUDIT_LOGGING=true                   # Detailed audit logs
FINOS_MCP_COMPLIANCE_REPORTING=true            # Generate compliance reports
FINOS_MCP_ENCRYPTION_AT_REST=true              # Encrypt stored data
FINOS_MCP_SECURE_COMMUNICATIONS=true           # TLS for all communications

# Access control
FINOS_MCP_RBAC_ENABLED=true                    # Role-based access control
FINOS_MCP_SSO_INTEGRATION=true                 # Single sign-on support
FINOS_MCP_SESSION_TIMEOUT=3600                 # Session timeout (seconds)
FINOS_MCP_API_RATE_LIMITING=true               # Rate limit protection
```

### GitHub Enterprise Integration

```bash
# GitHub Enterprise
FINOS_MCP_GITHUB_ENTERPRISE_URL="https://github.your-company.com/api/v3"
FINOS_MCP_GITHUB_ENTERPRISE_TOKEN="ghp_enterprise_token"
FINOS_MCP_GITHUB_ORG_REPOS_ONLY=true           # Only org repositories
FINOS_MCP_GITHUB_COMPLIANCE_SCANNING=true      # Scan for compliance
```

---

## 🔧 Enterprise Troubleshooting

### Multi-Tenant Issues

```bash
# Verify multi-tenant setup
python -c "
from finos_mcp.internal.advanced_mcp_capabilities import TenantManager
tm = TenantManager()
print('Multi-tenant support: OK')
"

# Test tenant isolation
python -m finos_mcp.server stdio --test-tenant-isolation

# List active tenants
python -c "
import os
os.environ['FINOS_MCP_MULTI_TENANT'] = 'true'
# Test tenant management
"
```

### Plugin System Diagnostics

```bash
# List loaded plugins
python -m finos_mcp.server stdio --list-plugins

# Test plugin system
python -c "
from finos_mcp.internal.advanced_mcp_capabilities import PluginManager
pm = PluginManager()
print('Plugin system: OK')
"

# Plugin development testing
python -m finos_mcp.internal.developer_productivity_tools --test-plugins
```

### Performance Diagnostics

```bash
# Performance metrics
python -m finos_mcp.server stdio --performance-report

# Test request coalescing
curl -X POST localhost:8080/test/coalescing \
  -H "Content-Type: application/json" \
  -d '{"concurrent_requests": 10, "identical": true}'

# Cache performance
python -c "
from finos_mcp.internal.performance_optimizations import SmartCache
cache = SmartCache()
print('Cache system: OK')
print('Stats:', cache.get_stats())
"
```

---

## 📊 Enterprise Usage Examples

### Multi-Tenant Operations

```bash
# Tenant-specific searches
"Search for mitigations in tenant 'frontend_team' related to data privacy"
"List all governance resources available to tenant 'compliance_team'"
"Generate a governance report for tenant 'backend_team'"

# Cross-tenant analysis (admin only)
"Compare governance maturity across all tenants"
"Aggregate risk assessments from all development teams"
```

### Plugin-Enhanced Workflows

```bash
# Using audit plugin
"Use the audit plugin to analyze this codebase for governance compliance"
"Generate audit trail for all governance queries this month"

# Performance plugins
"Optimize this governance query using the performance plugin"
"Cache warm all frequently used mitigations using background tasks"

# Security plugins
"Scan this AI model for governance risks using security plugin"
"Validate data privacy compliance using the privacy plugin"
```

### Enterprise Governance Analysis

```bash
# Advanced analysis
"Perform enterprise-wide governance gap analysis"
"Generate compliance dashboard for executive reporting"
"Analyze governance coverage across all product lines"

# Team collaboration
"Share governance findings with compliance team tenant"
"Create cross-functional governance improvement plan"
"Track governance metrics across development lifecycle"
```

---

## 🎯 Enterprise Client Recommendations

| Enterprise Use Case | Recommended Client | Enterprise Features |
|---------------------|-------------------|-------------------|
| **Multi-Team Development** | VS Code + Copilot | Native MCP, multi-tenant, plugin support |
| **Executive Dashboards** | Claude Desktop | Easy setup, enterprise reporting |
| **Compliance Workflows** | Windsurf | Team collaboration, audit trails |
| **AI-First Development** | Cursor | Modern protocol, streamable HTTP |
| **Large-Scale Java/Python** | JetBrains IDEs | Enterprise SSO, team workspaces |
| **Code Quality Gates** | Continue.dev | Integration with CI/CD, automated checks |
| **High-Performance Dev** | Zed | Fast execution, enterprise plugins |
| **Governance Training** | Claude Code | Interactive learning, guided workflows |

---

## 📞 Enterprise Support

Need help with enterprise integration? Check these resources:

<table>
<tr>
<td width="50%">

### Community & Open Source
- 📖 [MCP Protocol Documentation](https://modelcontextprotocol.io)
- 🐛 [Report Issues](https://github.com/hugo-calderon/finos-mcp-server/issues)
- 💬 [Discussion Forum](https://github.com/hugo-calderon/finos-mcp-server/discussions)
- 📚 [Documentation Hub](docs/README.md)

</td>
<td width="50%">

### Enterprise Support
- 🏢 [Enterprise Documentation](enterprise/README.md)
- 🔌 [Plugin Development Guide](enterprise/plugin-development.md)
- 📊 [Performance Tuning](enterprise/performance-tuning.md)
- 🛡️ [Security & Compliance](enterprise/security-compliance.md)
- 📧 [Project Support](mailto:hugocalderon@example.com)

</td>
</tr>
</table>

### Enterprise Onboarding

**Step 1**: [Enterprise Architecture Review](enterprise/README.md)
**Step 2**: [Multi-tenant Planning](enterprise/multi-tenant-setup.md)
**Step 3**: [Plugin Strategy](enterprise/plugin-development.md)
**Step 4**: [Performance Optimization](enterprise/performance-tuning.md)
**Step 5**: [Security Implementation](enterprise/security-compliance.md)

---

**Independent Project** | **Enterprise Features** | **350+ Tests** | **85%+ Coverage** | **Multi-tenant Ready** | **Plugin Ecosystem**