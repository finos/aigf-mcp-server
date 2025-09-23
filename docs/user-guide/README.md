# Framework Tool Usage Guide

User-friendly guide for compliance teams, risk managers, and governance professionals using the FINOS AI Governance Framework tools.

## Quick Navigation

- **[Getting Started](getting-started.md)** - First steps and basic concepts
- **[Framework Search Guide](framework-search.md)** - Finding the right governance content
- **[Compliance Analysis](compliance-analysis.md)** - Assessing compliance across frameworks
- **[Cross-Framework Navigation](cross-framework-navigation.md)** - Mapping between different frameworks
- **[Export and Reporting](export-reporting.md)** - Generating compliance reports
- **[Common Workflows](common-workflows.md)** - Step-by-step compliance scenarios
- **[Troubleshooting](troubleshooting.md)** - Solving common issues

## Who Should Use This Guide

### Compliance Teams
- Assess organizational compliance across multiple frameworks
- Generate compliance reports and documentation
- Identify and address compliance gaps

### Risk Managers
- Search for risk-related requirements across frameworks
- Analyze cross-framework risk coverage
- Map risk controls between different standards

### Governance Professionals
- Research governance frameworks and their relationships
- Create comprehensive governance documentation
- Track framework updates and changes

### Auditors and Consultants
- Compare client compliance across different frameworks
- Generate audit reports and recommendations
- Identify missing controls and requirements

## Supported Frameworks

| Framework | Type | Best For | Key Use Cases |
|-----------|------|----------|---------------|
| **NIST AI RMF** | Active | AI Risk Management | Risk assessment, trustworthy AI, governance culture |
| **EU AI Act** | Active | AI Regulation | Legal compliance, high-risk AI systems, conformity assessment |
| **OWASP LLM Top 10** | Active | AI Security | LLM vulnerabilities, prompt injection, model security |
| **GDPR** | Active | Data Protection | Privacy compliance, data rights, processing rules |
| **CCPA** | Modeled | California Privacy | Consumer privacy rights, data disclosure |
| **ISO 27001** | Modeled | Information Security | Security management, risk controls |
| **SOC 2** | Modeled | Service Organization Controls | Security, availability, confidentiality |

## Framework Tool Categories

### 🔍 Search Tools
- **Multi-Framework Search**: Find content across all frameworks
- **Framework-Specific Search**: Deep dive into individual frameworks
- **Advanced Search**: Complex queries with filters and exclusions

### 📊 Analysis Tools
- **Compliance Analysis**: Assess compliance status and coverage
- **Gap Analysis**: Identify missing controls and requirements
- **Correlation Analysis**: Understand framework relationships

### 🗺️ Navigation Tools
- **Control Mapping**: Find equivalent controls across frameworks
- **Related Controls**: Discover connected requirements
- **Framework Correlations**: Analyze thematic overlaps

### 📋 Export Tools
- **Framework Export**: Generate comprehensive framework reports
- **Bulk Export**: Create multiple reports simultaneously
- **Custom Reports**: Filtered exports with specific criteria

## Quick Start Workflow

### 1. Explore Available Frameworks
```
Tool: list_frameworks
Purpose: See what frameworks are available and their status
```

### 2. Search for Your Topic
```
Tool: search_frameworks
Query: "risk management" or "data protection"
Purpose: Find relevant content across all frameworks
```

### 3. Get Framework Details
```
Tool: get_framework_details
Framework: nist_ai_rmf (or your chosen framework)
Purpose: Understand framework structure and requirements
```

### 4. Analyze Compliance
```
Tool: get_compliance_analysis
Purpose: Assess current compliance status and identify gaps
```

### 5. Export Results
```
Tool: export_framework_data
Format: markdown (for documentation) or csv (for analysis)
Purpose: Generate reports for stakeholders
```

## Key Concepts

### Framework Types
- **Active Frameworks**: Live data from official sources, automatically updated
- **Modeled Frameworks**: Internal representations, manually maintained

### Relevance Scoring
- **High (0.8-1.0)**: Directly relevant to your query
- **Medium (0.5-0.8)**: Related content worth reviewing
- **Low (0.2-0.5)**: Potentially relevant in specific contexts

### Compliance Status
- **Compliant**: Requirements fully met
- **Partially Compliant**: Some aspects implemented
- **Non-Compliant**: Requirements not met
- **Not Assessed**: Status unknown or not evaluated

### Severity Levels
- **Critical**: Essential requirements, high impact if missing
- **High**: Important requirements, significant impact
- **Medium**: Standard requirements, moderate impact
- **Low**: Recommended practices, minimal direct impact

## Success Tips

### 🎯 Effective Searching
- Use specific terms for targeted results
- Try different variations of your search terms
- Use framework-specific searches for detailed requirements
- Combine multiple searches for comprehensive coverage

### 📈 Compliance Management
- Start with broad compliance analysis
- Focus on high-severity gaps first
- Use cross-framework mapping to avoid duplication
- Regular reassessment to track progress

### 🔄 Cross-Framework Work
- Begin with your primary framework
- Map to secondary frameworks gradually
- Look for correlation patterns between frameworks
- Use gap analysis to identify unique requirements

### 📊 Reporting Best Practices
- Export in appropriate format for your audience
- Include metadata for context and traceability
- Filter results to focus on relevant content
- Use bulk export for comprehensive documentation

## Getting Help

### Built-in Help
- Use `get_service_health` to check system status
- Check framework availability with `list_frameworks`
- Review error messages for specific guidance

### Documentation
- Review the [API Reference](../api/mcp-tools.md) for technical details
- Check [Troubleshooting](troubleshooting.md) for common issues
- See [Common Workflows](common-workflows.md) for step-by-step guides

### Support Resources
- GitHub Issues for bug reports and feature requests
- Community discussions for usage questions
- Documentation feedback for guide improvements

## Next Steps

1. **New Users**: Start with [Getting Started](getting-started.md)
2. **Search Focus**: Read [Framework Search Guide](framework-search.md)
3. **Compliance Teams**: Go to [Compliance Analysis](compliance-analysis.md)
4. **Multi-Framework**: See [Cross-Framework Navigation](cross-framework-navigation.md)

This guide will help you maximize the value of the FINOS AI Governance Framework tools for your compliance and governance needs.
