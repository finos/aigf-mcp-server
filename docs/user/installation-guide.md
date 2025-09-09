# 🚀 FINOS AI Governance MCP Server - Installation Guide

Complete installation guide for users wanting to get started with the FINOS AI Governance MCP Server.

## 📋 Table of Contents

- [System Requirements](#system-requirements)
- [Installation Methods](#installation-methods)
- [Configuration](#configuration)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

## 💻 System Requirements

### Minimum Requirements
- **Python**: 3.9, 3.10, 3.11, 3.12, or 3.13
- **Operating System**: Windows, macOS, Linux
- **Memory**: 100MB RAM minimum
- **Storage**: 50MB disk space
- **Network**: Internet connection for document fetching

### Recommended Requirements
- **Python**: 3.11+ for optimal performance
- **Memory**: 256MB RAM for caching
- **Network**: Stable broadband connection
- **GitHub Token**: Personal access token for enhanced reliability

## 🛠️ Installation Methods

### Method 1: PyPI Installation (Recommended)
```bash
# Install from PyPI
pip install finos-ai-governance-mcp-server

# Verify installation
finos-mcp --version
```

### Method 2: Development Installation
```bash
# Clone repository
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .
```

### Method 3: Docker Installation
```bash
# Pull and run Docker container
# Docker images not available for this personal project
# Use local installation method above
```

## ⚙️ Configuration

### Basic Configuration
Create a `.env` file in your working directory:

```bash
# Basic settings
FINOS_MCP_LOG_LEVEL=INFO
FINOS_MCP_HTTP_TIMEOUT=30
FINOS_MCP_ENABLE_CACHE=true
```

### Advanced Configuration
```bash
# Performance tuning
FINOS_MCP_CACHE_MAX_SIZE=1000
FINOS_MCP_CACHE_TTL_SECONDS=3600

# GitHub API (optional but recommended)
FINOS_MCP_GITHUB_TOKEN=your_token_here

# Custom repository (advanced users)
FINOS_MCP_BASE_URL=https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs
```

### GitHub Token Setup (Recommended)

**Why use a GitHub token?**
- Increases rate limit from 60 to 5000 requests/hour
- More reliable service during peak usage
- Dedicated rate limits prevent service interruption

**Setup Steps:**
1. Visit [GitHub Settings → Personal Access Tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select **only** "public_repo" scope
4. Set 90-day expiration for security
5. Add to your `.env` file: `FINOS_MCP_GITHUB_TOKEN=your_token_here`

## ✅ Verification

### Quick Test
```bash
# Test basic functionality
finos-mcp --help

# Test server import
python -c "import finos_mcp; print('Import successful!')"
```

### Full Validation
```bash
# Clone repository for tests (development installation)
python tests/integration/simple_test.py

# Expected output: "Server functionality validated successfully!"
```

### Claude Code Integration Test
Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "finos-mcp",
      "args": []
    }
  }
}
```

## 🛡️ Security Best Practices

### Token Security
- ✅ Use minimal permissions (public_repo only)
- ✅ Set 90-day expiration
- ✅ Monitor usage in GitHub settings
- ✅ Never commit tokens to version control
- ✅ Rotate regularly

### Environment Security
- ✅ Use virtual environments
- ✅ Keep .env files secure
- ✅ Update dependencies regularly
- ✅ Monitor logs for security warnings

## 🔍 Troubleshooting

### Common Issues

**❌ "Command 'finos-mcp' not found"**
```bash
# Solution: Ensure virtual environment is activated
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Verify PATH includes virtual environment
which finos-mcp  # Should show path in .venv
```

**❌ "ModuleNotFoundError: No module named 'finos_mcp'"**
```bash
# Solution: Reinstall package
pip uninstall finos-ai-governance-mcp-server
pip install finos-ai-governance-mcp-server
```

**❌ "Configuration Error: GitHub token format invalid"**
```bash
# Solution: Check token format
# Classic tokens: ghp_* (40 characters) # pragma: allowlist secret
# Fine-grained: github_pat_* (50+ characters) # pragma: allowlist secret
```

**❌ "HTTPTimeout: Request timed out"**
```bash
# Solution: Increase timeout
export FINOS_MCP_HTTP_TIMEOUT=60
```

**❌ "Rate limit exceeded"**
```bash
# Solution: Add GitHub token or wait
export FINOS_MCP_GITHUB_TOKEN=your_token_here
# Without token: 60 requests/hour
# With token: 5000 requests/hour
```

### Getting Help

If you encounter issues:

1. **Check logs**: Run with `FINOS_MCP_LOG_LEVEL=DEBUG` for detailed information
2. **GitHub Issues**: [Report bugs and issues](https://github.com/hugo-calderon/finos-mcp-server/issues)
3. **GitHub Discussions**: [Ask questions and get help](https://github.com/hugo-calderon/finos-mcp-server/discussions)

## 🎯 Next Steps

### For End Users
1. **[Usage Guide](usage-guide.md)** - Learn how to use the MCP server effectively

### For Developers
1. **[Developer Documentation](../developer/README.md)** - Development setup and contribution guidelines
2. **[API Reference](../developer/api-reference.md)** - Complete API documentation

### For Operations Teams
1. **[Production Deployment](../operations/production-deployment.md)** - Deploy in production environments
2. **[Security Guide](../operations/security.md)** - Security hardening and compliance

---

> **Need Support?** Visit our [comprehensive documentation hub](../README.md) for guides tailored to your specific use case.
