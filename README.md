# 🤖 AI Governance MCP Server

<!-- Core Project Badges -->
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![MCP Protocol](https://img.shields.io/badge/MCP-1.0+-green)
![Status](https://img.shields.io/badge/status-alpha-orange)

<!-- Quality & CI Badges -->
![GitHub Actions](https://img.shields.io/github/actions/workflow/status/hugo-calderon/finos-mcp-server/security-analysis.yml?branch=main&label=CI)
![Security](https://img.shields.io/badge/security-passing-brightgreen)
![Tests](https://img.shields.io/badge/tests-486%20passing-brightgreen)
![MyPy](https://img.shields.io/badge/mypy-passing-blue)

<!-- Tools & Features -->
![MCP Tools](https://img.shields.io/badge/MCP%20tools-10-blue)
![FINOS Content](https://img.shields.io/badge/FINOS%20content-17%20mitigations%20%7C%2017%20risks-blue)
![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen)

**Simple access to AI governance content for your development tools.**

This independent project provides AI governance mitigations and risk assessments through the Model Context Protocol (MCP), making them available in Claude, VS Code, Cursor, and other supported tools.

---

## 🚀 Quick Start

```bash
# Clone and install
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
pip install -e .

# Test
finos-mcp --help
```

**→ [Full Setup Guide](docs/README.md)** - Connect to Claude, VS Code, Cursor, etc.

---

## 🛠️ What You Get

**10 tools** providing access to:
- **17 AI Governance Mitigations** (mi-1 through mi-17)
- **17 AI Risk Assessments** (ri-1, ri-2, ri-3, ri-5-ri-16, ri-19, ri-23)

### Available Tools
| Tool | Purpose | Example Usage |
|------|---------|---------------|
| `search_mitigations` | Find governance strategies | "data privacy protection" |
| `search_risks` | Find AI risks | "prompt injection attacks" |
| `get_mitigation_details` | Get specific mitigation | Get mi-1 (data leakage prevention) |
| `get_risk_details` | Get specific risk | Get ri-2 (prompt injection) |
| `list_all_mitigations` | Browse all mitigations | See what's available |
| `list_all_risks` | Browse all risks | See what's available |
| `get_service_health` | Check server status | Is it working? |
| `get_service_metrics` | Performance stats | How fast? |
| `get_cache_stats` | Cache statistics | Memory usage |
| `reset_service_health` | Reset counters | Clear errors |

---

## 💡 Example Workflows

**Protecting user data:**
```
1. "Search for data privacy mitigations"
2. "Show me mitigation mi-1"
3. "What are data leakage risks?"
```

**Preventing prompt injection:**
```
1. "Find prompt injection risks"
2. "Show me risk ri-2"
3. "Search for input validation mitigations"
```

---

## 📖 Documentation

- **[Setup Guide](docs/README.md)** - Connect to your editor (5 minutes)
- **[GitHub Repository](https://github.com/hugo-calderon/finos-mcp-server)** - Source code

---

## 🔍 Content Source

Content from the [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework), used under CC BY 4.0 license.

This is an **independent project** - not officially affiliated with FINOS.

---

## 🆘 Need Help?

- 🐛 [Report Issues](https://github.com/hugo-calderon/finos-mcp-server/issues)
- 💬 [Ask Questions](https://github.com/hugo-calderon/finos-mcp-server/discussions)
- 📖 [Full Documentation](docs/README.md)

---

## License

[![Software License](https://img.shields.io/badge/software-Apache%202.0-blue.svg)](LICENSE)
[![Content License](https://img.shields.io/badge/content-CC%20BY%204.0-green.svg)](FINOS-LICENSE.md)

- **Software**: Apache 2.0 License
- **FINOS Content**: CC BY 4.0 License
