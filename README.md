# 🔍 Governance Framework Reference System

<!-- Core Project Badges -->
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![MCP Protocol](https://img.shields.io/badge/MCP-1.0+-green)
![Status](https://img.shields.io/badge/status-alpha-orange)

<!-- Quality & CI Badges -->
![GitHub Actions](https://img.shields.io/github/actions/workflow/status/hugo-calderon/finos-mcp-server/security-analysis.yml?branch=main&label=CI)
![Security](https://img.shields.io/badge/security-passing-brightgreen)
![Tests](https://img.shields.io/badge/tests-438%20passing-brightgreen)
![MyPy](https://img.shields.io/badge/mypy-passing-blue)

<!-- Tools & Features -->
![MCP Tools](https://img.shields.io/badge/MCP%20tools-21-blue)
![Governance Content](https://img.shields.io/badge/governance%20content-200%2B%20references-blue)
![Framework Support](https://img.shields.io/badge/frameworks-4%20active%20%7C%207%20supported-green)
![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen)

**Comprehensive governance framework reference system for your development tools.**

This independent project provides access to governance frameworks, compliance analysis, and risk assessments through the Model Context Protocol (MCP), making them available in Claude, VS Code, Cursor, and other supported tools.

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

**21 tools** providing access to:
- **220+ Governance References** across multiple frameworks
- **AI Risk Assessments & Mitigations** (34 items total)
- **Framework Integration** with NIST AI RMF, EU AI Act, OWASP LLM Top 10, GDPR
- **Dynamic Content Loading** from official sources with intelligent caching
- **Cross-Framework Navigation** with control mapping and correlation analysis
- **Compliance Gap Analysis** for multi-framework compliance planning

### Available Tools
| Tool | Purpose | Example Usage |
|------|---------|---------------|
| **Framework Tools** | | |
| `search_frameworks` | Cross-framework search | "risk management" |
| `list_frameworks` | Available frameworks | See supported frameworks |
| `get_framework_details` | Framework information | Get NIST AI RMF details |
| `get_compliance_analysis` | Compliance metrics | Framework coverage analysis |
| `search_framework_references` | Framework-specific search | "injection" in OWASP |
| **Cross-Framework Navigation** | | |
| `get_related_controls` | Find equivalent controls | Map NIST control to EU AI Act |
| `get_framework_correlations` | Analyze framework relationships | NIST ↔ EU AI Act correlations |
| `find_compliance_gaps` | Identify compliance gaps | Gap analysis for multiple frameworks |
| **Advanced Search & Export** | | |
| `advanced_search_frameworks` | Advanced multi-criteria search | Complex filtering across frameworks |
| `export_framework_data` | Export framework data | JSON/CSV/Markdown export |
| `bulk_export_frameworks` | Bulk export operations | Multiple framework datasets |
| **FINOS Content Tools** | | |
| `search_mitigations` | Find governance strategies | "data privacy protection" |
| `search_risks` | Find AI risks | "prompt injection attacks" |
| `get_mitigation_details` | Get specific mitigation | Get mi-1 (data leakage prevention) |
| `get_risk_details` | Get specific risk | Get ri-2 (prompt injection) |
| `list_all_mitigations` | Browse all mitigations | See what's available |
| `list_all_risks` | Browse all risks | See what's available |
| **System Tools** | | |
| `get_service_health` | Check server status | Is it working? |
| `get_service_metrics` | Performance stats | How fast? |
| `get_cache_stats` | Cache statistics | Memory usage |
| `reset_service_health` | Reset counters | Clear errors |

---

## 💡 Example Workflows

**Framework Governance Research:**
```
1. "List all supported governance frameworks"
2. "Search frameworks for 'risk management'"
3. "Get compliance analysis for my requirements"
```

**Cross-Framework Compliance:**
```
1. "Search framework references for 'data protection'"
2. "Get framework details for GDPR"
3. "Find related controls for ai-rmf-1.1"
4. "Analyze correlations between NIST and EU AI Act"
5. "Find compliance gaps when mapping to multiple frameworks"
```

**FINOS Content:**
```
1. "Search for data privacy mitigations"
2. "Show me mitigation mi-1"
3. "Find prompt injection risks"
```

---

## 📖 Documentation

### Getting Started
- **[Setup Guide](docs/README.md)** - Connect to your editor (5 minutes)
- **[User Guide](docs/user-guide/)** - Comprehensive usage guide for all tools
- **[Framework Search Guide](docs/user-guide/framework-search.md)** - Master framework content discovery

### API & Integration
- **[API Documentation](docs/api/)** - Complete API reference for all 18 MCP tools
- **[Framework Architecture](docs/api/framework-architecture.md)** - System design and patterns
- **[Integration Guide](docs/api/integration-guide.md)** - Developer integration patterns
- **[Response Schemas](docs/api/response-schemas.md)** - Detailed response formats

### Support & Troubleshooting
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
- **[Tools Reference](docs/tools-reference.md)** - Complete guide to all 21 MCP tools
- **[GitHub Repository](https://github.com/hugo-calderon/finos-mcp-server)** - Source code and issues

---

## 🔍 Content Sources

- **Framework Data**: Multi-framework governance references including NIST AI RMF, EU AI Act, OWASP LLM Top 10, GDPR (9 sections, 18 references)
- **Dynamic Loading**: Automatic content fetching from official sources with ContentService integration
- **FINOS Content**: AI governance mitigations and risks from [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework), used under CC BY 4.0 license
- **Performance**: Sub-0.1ms cached response times with intelligent caching and circuit breaker protection

This is an **independent project** - not officially affiliated with FINOS or other framework organizations.

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
