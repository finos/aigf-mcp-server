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

# 🏢 **Enterprise Use Cases & Business Applications**

> *Transform AI governance from compliance burden to competitive advantage through automated, data-driven decision making*

---

## 📊 **Executive Summary**

| **Business Challenge** | **Traditional Approach** | **FINOS MCP Solution** | **Impact** |
|------------------------|--------------------------|------------------------|------------|
| Multi-framework compliance | Manual mapping, lengthy processes | Automated framework correlation | **Significant time reduction** |
| Risk assessment | Manual, inconsistent analysis | AI-powered, comprehensive discovery | **Faster threat identification** |
| Regulatory reporting | Custom builds per framework | Unified export engine | **Streamlined documentation** |
| Cross-border operations | Separate compliance programs | Integrated governance approach | **Operational efficiency gains** |

---

## 🎯 **Primary Use Case: Global Financial Services**

### **Enterprise Profile**
- **Industry**: Multinational financial institution
- **Challenge**: Deploy AI fraud detection across multiple jurisdictions
- **Regulatory Scope**: Multiple frameworks and hundreds of requirements
- **Goal**: Unified compliance approach across all markets

### **Implementation Journey**

<details>
<summary><strong>Strategic Assessment</strong></summary>

#### **Regulatory Landscape Discovery**
```bash
# Complete framework inventory
list_frameworks()
→ Identified all applicable frameworks across jurisdictions

# Detailed requirement analysis
get_framework_details(framework="eu-ai-act")
get_framework_details(framework="nist-ai-rmf-1.0")
get_framework_details(framework="gdpr")
→ Complete requirements mapped and categorized
```

#### **Cross-Framework Intelligence**
```bash
# Strategic overlap analysis
get_framework_correlations(framework1="eu-ai-act", framework2="nist-ai-rmf-1.0")
→ Discovered significant requirement overlap, enabling unified approach

# Gap identification
find_compliance_gaps(source_framework="gdpr", target_frameworks=["ccpa", "lgpd"])
→ Identified jurisdiction-specific requirements requiring localization
```

**Business Impact**: Dramatically reduced initial assessment time and eliminated redundant external consulting.

</details>

<details>
<summary><strong>Risk & Control Mapping</strong></summary>

#### **Comprehensive Risk Assessment**
```bash
# AI-specific threat landscape
search_risks(query="financial fraud detection")
→ Identified comprehensive AI-specific risks across operational, security, and regulatory categories

# Detailed impact analysis
get_risk_details(risk_id="ri-9")  # Data poisoning
get_risk_details(risk_id="ri-16") # Bias and discrimination
→ Quantified risk exposure and likelihood assessments
```

#### **Control Implementation Strategy**
```bash
# Targeted mitigation discovery
search_mitigations(query="bias detection financial services")
→ Found applicable controls with implementation guidance

# Control relationship mapping
get_related_controls(control_id="GDPR-25", frameworks=["ccpa", "nist-ai-rmf"])
→ Single control implementation satisfies multiple regulatory requirements
```

**Business Impact**: Achieved comprehensive risk coverage with significantly fewer controls than traditional approaches.

</details>

<details>
<summary><strong>Operational Excellence</strong></summary>

#### **Performance Monitoring**
```bash
# Real-time system health
get_service_health()
→ High uptime with automated alerting for compliance metrics

# Performance optimization
get_service_metrics()
get_cache_stats()
→ Substantial improvement in compliance query performance
```

#### **Continuous Compliance**
```bash
# Automated compliance assessment
get_compliance_analysis(frameworks=["eu-ai-act", "nist-ai-rmf", "gdpr"])
→ Real-time compliance scoring across all jurisdictions

# Advanced regulatory intelligence
advanced_search_frameworks(include_terms=["AI", "bias"], categories=["financial"])
→ Proactive identification of emerging requirements
```

**Business Impact**: Dramatically reduced ongoing compliance monitoring resource requirements.

</details>

<details>
<summary><strong>Stakeholder Enablement</strong></summary>

#### **Executive Reporting**
```bash
# Board-ready documentation
export_framework_data(framework="eu-ai-act", format="pdf", executive_summary=true)
→ Generated executive briefings with risk heatmaps

# Comprehensive documentation package
bulk_export_frameworks(frameworks=["all"], formats=["pdf", "json", "csv"])
→ Complete audit trail for regulatory submissions
```

#### **Operational Handover**
```bash
# Complete framework catalog
list_all_risks()
list_all_mitigations()
→ Transferred comprehensive risks and controls to operational teams
```

**Business Impact**: Achieved regulatory approval ahead of schedule, enabling accelerated market entry.

</details>

---

## 💼 **Tool-by-Tool Business Applications**

### **System Operations Suite**
| Tool | Enterprise Application | Business Value |
|------|----------------------|----------------|
| `get_service_health()` | **24/7 Compliance SLA Monitoring**<br/>Real-time health checks for mission-critical compliance systems | Prevents regulatory penalty exposure |
| `get_service_metrics()` | **Performance Optimization**<br/>Monitors AI governance system performance during peak regulatory periods | Substantial improvement in compliance query speed |
| `get_cache_stats()` | **Infrastructure Efficiency**<br/>Optimizes compliance data retrieval for high-volume queries | Significant reduction in infrastructure overhead |
| `reset_service_health()` | **Incident Recovery**<br/>Clean baseline establishment after system maintenance | Dramatically reduces mean time to recovery |

### **Strategic Intelligence Suite**
| Tool | Enterprise Application | Business Value |
|------|----------------------|----------------|
| `list_frameworks()` | **Regulatory Landscape Mapping**<br/>Complete inventory of applicable frameworks across all jurisdictions | Eliminates external regulatory research dependencies |
| `get_framework_details()` | **Deep Compliance Analysis**<br/>Detailed requirement breakdown for legal and compliance teams | Accelerates legal review cycles |
| `search_frameworks()` | **Targeted Regulatory Research**<br/>Precision search across multiple frameworks for specific AI requirements | Reduces research time from weeks to hours |
| `search_framework_references()` | **Authoritative Citation Engine**<br/>Official regulatory citations for audit and legal documentation | Ensures regulatory defensibility |

### **Cross-Border Unification Suite**
| Tool | Enterprise Application | Business Value |
|------|----------------------|----------------|
| `get_related_controls()` | **Global Control Harmonization**<br/>Maps equivalent requirements across multiple regional regulations | Single implementation for multiple jurisdictions |
| `get_framework_correlations()` | **Strategic Overlap Analysis**<br/>Identifies substantial overlap between major frameworks for unified approach | Eliminates duplicate compliance programs |
| `find_compliance_gaps()` | **Expansion Risk Assessment**<br/>Quantifies additional work needed for new market entry | Enables accurate planning for international expansion |

### **Risk Intelligence Suite**
| Tool | Enterprise Application | Business Value |
|------|----------------------|----------------|
| `search_risks()` | **Threat Landscape Intelligence**<br/>AI-specific risk discovery across multiple risk categories | Proactive threat identification before incidents occur |
| `get_risk_details()` | **Executive Risk Briefings**<br/>Quantified risk assessments for C-level decision making | Data-driven risk investment prioritization |
| `list_all_risks()` | **Comprehensive Risk Registry**<br/>Complete AI governance risk catalog for enterprise risk management | Complete risk coverage for audit compliance |

### **Control Implementation Suite**
| Tool | Enterprise Application | Business Value |
|------|----------------------|----------------|
| `search_mitigations()` | **Control Discovery Engine**<br/>AI-specific security and compliance controls with implementation guidance | Optimal risk coverage with efficient control selection |
| `get_mitigation_details()` | **Implementation Playbooks**<br/>Step-by-step control deployment guides for technical teams | Accelerated control implementation cycles |
| `list_all_mitigations()` | **Enterprise Control Library**<br/>Comprehensive catalog of AI governance controls | Standardized security posture across business units |

### **Business Intelligence Suite**
| Tool | Enterprise Application | Business Value |
|------|----------------------|----------------|
| `get_compliance_analysis()` | **Real-time Compliance Scoring**<br/>Continuous compliance posture assessment across all frameworks | Executive dashboard with predictive compliance metrics |
| `advanced_search_frameworks()` | **Regulatory Intelligence**<br/>Advanced queries for emerging AI regulations and requirements | Extended regulatory change lead time |

### **Enterprise Documentation Suite**
| Tool | Enterprise Application | Business Value |
|------|----------------------|----------------|
| `export_framework_data()` | **Audit-Ready Documentation**<br/>Professional regulatory reports for external auditors and regulators | Zero documentation deficiencies in regulatory reviews |
| `bulk_export_frameworks()` | **Knowledge Management**<br/>Comprehensive compliance documentation for enterprise knowledge bases | Unified source of truth across organization |

---

## 📈 **Quantified Business Outcomes**

### **Operational Excellence**
- **Time to Compliance**: Substantial reduction in implementation timeline
- **Regulatory Query Speed**: Multiple-fold improvement in response times
- **Cross-framework Accuracy**: Near-perfect accuracy vs manual approaches
- **Audit Preparation**: Dramatic time reduction in audit readiness

### **Strategic Advantages**
- **Market Entry Speed**: Accelerated international expansion capabilities
- **Regulatory Risk**: Significant reduction in compliance violations
- **Competitive Advantage**: First-mover advantage in AI governance automation
- **Stakeholder Confidence**: High approval rate for AI initiatives

---

## 🚀 **Implementation Approach**

| **Phase** | **Key Activities** | **Business Milestone** |
|-----------|-------------------|------------------------|
| **Discovery** | Framework mapping, risk assessment | Complete regulatory landscape understanding |
| **Strategy** | Gap analysis, control design | Unified compliance strategy approved |
| **Implementation** | System deployment, team training | Operational AI governance platform |
| **Excellence** | Optimization, reporting, handover | Full regulatory readiness achieved |

---

*Transform your AI governance from reactive compliance to proactive competitive advantage with systematic, automated workflows.*

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
