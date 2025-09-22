# 🔍 Governance Framework Reference System

<!-- Core Project Badges -->
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![MCP Protocol](https://img.shields.io/badge/MCP-1.0+-green)
![Status](https://img.shields.io/badge/status-alpha-orange)

<!-- Quality & CI Badges -->
![GitHub Actions](https://img.shields.io/github/actions/workflow/status/hugo-calderon/finos-mcp-server/security-analysis.yml?branch=main&label=CI)
![Security](https://img.shields.io/badge/security-passing-brightgreen)
![Tests](https://img.shields.io/badge/tests-493%20passing-brightgreen)
![MyPy](https://img.shields.io/badge/mypy-passing-blue)

<!-- Tools & Features -->
![MCP Tools](https://img.shields.io/badge/MCP%20tools-21-blue)
![Governance Content](https://img.shields.io/badge/governance%20content-220%2B%20references-blue)
![Framework Support](https://img.shields.io/badge/frameworks-7%20supported-green)
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

## 🛠️ Complete Tools Reference

### Framework Management
| Tool Name | Description | Key Parameters | Use Case |
|-----------|-------------|----------------|----------|
| `search_frameworks` | Search across all governance frameworks for requirements/controls | `query`, `frameworks`, `severity`, `compliance_status`, `tags`, `sections`, `limit` | Find specific requirements across NIST, EU AI Act, OWASP, ISO 27001, GDPR, etc. |
| `list_frameworks` | List all available governance frameworks with statistics | `active_only`, `include_stats` | Get overview of supported frameworks (NIST AI RMF, EU AI Act, OWASP LLM Top 10, etc.) |
| `get_framework_details` | Get detailed information about a specific framework | `framework_type`, `include_references`, `include_sections` | Deep dive into framework structure, requirements, and compliance data |
| `search_framework_references` | Search for specific references within a particular framework | `framework_type`, `query`, `section`, `limit` | Find detailed requirements or controls within specific frameworks |

### Cross-Framework Analysis
| Tool Name | Description | Key Parameters | Use Case |
|-----------|-------------|----------------|----------|
| `get_related_controls` | Find related controls across different frameworks | `framework_type`, `control_id`, `min_strength` | Map controls between frameworks for compliance alignment |
| `get_framework_correlations` | Analyze correlations between frameworks | `framework1`, `framework2`, `min_strength` | Identify thematic overlaps and relationship strength between standards |
| `find_compliance_gaps` | Identify compliance gaps when mapping between frameworks | `source_framework`, `target_frameworks`, `min_coverage` | Gap analysis for compliance planning across multiple standards |

### Compliance Analysis
| Tool Name | Description | Key Parameters | Use Case |
|-----------|-------------|----------------|----------|
| `get_compliance_analysis` | Get comprehensive compliance analysis across frameworks | `frameworks`, `include_mappings` | Overall compliance coverage statistics and gap identification |
| `advanced_search_frameworks` | Enhanced search with advanced filtering capabilities | `search_terms`, `exclude_terms`, `categories`, `severity_levels`, `compliance_status`, `frameworks`, `sections`, `tags`, `updated_after`, `updated_before`, `limit` | Complex queries with multiple filters for targeted compliance research |

### Risk Management
| Tool Name | Description | Key Parameters | Use Case |
|-----------|-------------|----------------|----------|
| `search_risks` | Search through AI governance risks by keyword or topic | `query`, `exact_match` | Find specific risks related to keywords like "data leakage", "bias", "security" |
| `get_risk_details` | Get comprehensive details about a specific risk | `risk_id` | Deep dive into risk details, mitigation strategies, and regulatory mappings |
| `list_all_risks` | List all available AI governance risks with metadata | None | Overview of all 17 identified AI risks with status and relationships |

### Mitigation Controls
| Tool Name | Description | Key Parameters | Use Case |
|-----------|-------------|----------------|----------|
| `search_mitigations` | Search through AI governance mitigations by keyword | `query`, `exact_match` | Find controls for specific risk areas like "encryption", "monitoring", "access control" |
| `get_mitigation_details` | Get detailed information about a specific mitigation | `mitigation_id` | Complete implementation guidance, principles, and regulatory references |
| `list_all_mitigations` | List all available mitigations with their metadata | None | Overview of all 17 mitigation controls with types and risk coverage |

### Data Export & Reporting
| Tool Name | Description | Key Parameters | Use Case |
|-----------|-------------|----------------|----------|
| `export_framework_data` | Export framework data in multiple formats | `format` (json/csv/markdown), `frameworks`, `categories`, `compliance_status`, `severity_levels`, `sections`, `filename`, `include_descriptions`, `include_metadata`, `include_summary`, `include_urls` | Generate compliance reports and documentation |
| `bulk_export_frameworks` | Export multiple framework datasets with different configurations | `exports`, `compress_output`, `include_manifest` | Comprehensive compliance documentation packages |

### System Monitoring
| Tool Name | Description | Key Parameters | Use Case |
|-----------|-------------|----------------|----------|
| `get_service_health` | Get comprehensive service health status and diagnostics | None | Monitor system availability, success rates, and error tracking |
| `get_service_metrics` | Get detailed service performance metrics and statistics | None | Performance analysis and system optimization insights |
| `get_cache_stats` | Get cache performance statistics and metrics | None | Cache hit rates and performance optimization data |
| `reset_service_health` | Reset service health counters and error boundaries | None | System maintenance and health counter reset |

---

## 📋 Supported Governance Frameworks

| Framework | Code | Description | Focus Area |
|-----------|------|-------------|------------|
| NIST AI RMF 1.0 | `nist-ai-rmf-1.0` | NIST Artificial Intelligence Risk Management Framework | Comprehensive AI risk management |
| EU AI Act | `eu-ai-act` | European Union Artificial Intelligence Act | AI regulation and compliance in EU |
| OWASP LLM Top 10 | `owasp-llm-top-10` | Top 10 security vulnerabilities for LLM applications | AI/LLM security risks |
| ISO 27001 | `iso-27001` | Information Security Management System standard | Information security management |
| GDPR | `gdpr` | General Data Protection Regulation | Data privacy and protection |
| CCPA | `ccpa` | California Consumer Privacy Act | Consumer data privacy |
| SOC 2 | `soc2` | Service Organization Control 2 | Service provider security controls |

---

## 🎯 Risk Categories & Types

### Risk Categories
| Risk Type | Code | Description | Example Risks |
|-----------|------|-------------|---------------|
| Security (SEC) | `SEC` | Information security and cybersecurity risks | Data leakage, prompt injection, tampering |
| Operational (OP) | `OP` | Business and operational risks | Hallucination, bias, model drift |
| Regulatory/Compliance (RC) | `RC` | Legal and regulatory compliance risks | Regulatory oversight, IP/copyright issues |

### Mitigation Types
| Mitigation Type | Code | Description | Example Controls |
|-----------------|------|-------------|------------------|
| Prevention (PREV) | `PREV` | Proactive controls to prevent risks | Access controls, firewalls, data classification |
| Detection (DET) | `DET` | Controls to detect and monitor risks | Observability, alerting, human feedback loops |

---

## 💡 Common Use Cases & Tool Combinations

| Use Case | Recommended Tool Sequence | Purpose |
|----------|---------------------------|---------|
| **Risk Assessment** | `list_all_risks` → `search_risks` → `get_risk_details` | Comprehensive risk identification and analysis |
| **Control Implementation** | `search_mitigations` → `get_mitigation_details` → `get_related_controls` | Find and implement appropriate controls |
| **Compliance Mapping** | `list_frameworks` → `search_frameworks` → `find_compliance_gaps` | Map requirements across multiple standards |
| **Framework Analysis** | `get_framework_details` → `get_framework_correlations` → `get_compliance_analysis` | Deep framework comparison and analysis |
| **Documentation Generation** | `advanced_search_frameworks` → `export_framework_data` → `bulk_export_frameworks` | Create comprehensive compliance documentation |
| **System Monitoring** | `get_service_health` → `get_service_metrics` → `get_cache_stats` | Monitor and optimize system performance |

---

## 🔄 Example Workflows

### Framework Governance Research
```
1. "List all supported governance frameworks"
   → Use: list_frameworks(include_stats=true)

2. "Search frameworks for 'risk management'"
   → Use: search_frameworks(query="risk management", limit=10)

3. "Get compliance analysis for my requirements"
   → Use: get_compliance_analysis(frameworks=["nist-ai-rmf-1.0", "eu-ai-act"])
```

### Cross-Framework Compliance Mapping
```
1. "Search framework references for 'data protection'"
   → Use: search_framework_references(framework_type="gdpr", query="data protection")

2. "Get framework details for GDPR"
   → Use: get_framework_details(framework_type="gdpr", include_references=true)

3. "Find related controls for ai-rmf-1.1"
   → Use: get_related_controls(framework_type="nist-ai-rmf-1.0", control_id="ai-rmf-1.1")

4. "Analyze correlations between NIST and EU AI Act"
   → Use: get_framework_correlations(framework1="nist-ai-rmf-1.0", framework2="eu-ai-act")

5. "Find compliance gaps when mapping to multiple frameworks"
   → Use: find_compliance_gaps(source_framework="nist-ai-rmf-1.0", target_frameworks=["eu-ai-act", "gdpr"])
```

### Comprehensive Risk & Mitigation Analysis
```
1. "Search for data privacy mitigations"
   → Use: search_mitigations(query="data privacy", exact_match=false)

2. "Show me mitigation mi-1 details"
   → Use: get_mitigation_details(mitigation_id="mi-1")

3. "Find prompt injection risks"
   → Use: search_risks(query="prompt injection", exact_match=true)

4. "Get comprehensive risk details"
   → Use: get_risk_details(risk_id="ri-2")
```

### Documentation & Reporting
```
1. "Advanced search across multiple frameworks"
   → Use: advanced_search_frameworks(search_terms=["security", "privacy"], frameworks=["gdpr", "nist-ai-rmf-1.0"])

2. "Export framework data for compliance report"
   → Use: export_framework_data(format="markdown", frameworks=["eu-ai-act"], include_descriptions=true)

3. "Generate comprehensive documentation package"
   → Use: bulk_export_frameworks(exports=[{format:"json"}, {format:"csv"}], compress_output=true)
```

---

## 🔍 Content Sources & Performance

### Content Coverage
- **Framework Data**: Multi-framework governance references including NIST AI RMF, EU AI Act, OWASP LLM Top 10, GDPR (220+ references)
- **Dynamic Loading**: Automatic content fetching from official sources with ContentService integration
- **FINOS Content**: AI governance mitigations and risks from [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework), used under CC BY 4.0 license
- **Cross-Framework Mapping**: Intelligent correlation and gap analysis between standards

### Performance Characteristics
- **Response Times**: Sub-0.1ms cached response times with intelligent caching
- **Reliability**: Circuit breaker protection and error boundary management
- **Scalability**: Memory-efficient design with configurable cache limits
- **Security**: Comprehensive DoS protection and request validation

---

## 📖 Documentation

### Getting Started
- **[Setup Guide](docs/README.md)** - Connect to your editor (5 minutes)
- **[User Guide](docs/user-guide/)** - Comprehensive usage guide for all tools
- **[Framework Search Guide](docs/user-guide/framework-search.md)** - Master framework content discovery

### API & Integration
- **[API Documentation](docs/api/)** - Complete API reference for all 21 MCP tools
- **[Framework Architecture](docs/api/framework-architecture.md)** - System design and patterns
- **[Integration Guide](docs/api/integration-guide.md)** - Developer integration patterns
- **[Response Schemas](docs/api/response-schemas.md)** - Detailed response formats

### Support & Troubleshooting
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
- **[Tools Reference](docs/tools-reference.md)** - Complete guide to all 21 MCP tools
- **[GitHub Repository](https://github.com/hugo-calderon/finos-mcp-server)** - Source code and issues

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

---

*This is an **independent project** - not officially affiliated with FINOS or other framework organizations.*