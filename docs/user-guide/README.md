# User Guide

Welcome to the FINOS AI Governance MCP Server user guide.

## Available Guides

- **[Getting Started](getting-started.md)** - Quick start guide for using the 11 MCP tools

## Tool Categories

The server provides 11 MCP tools organized in 3 categories:

### Framework Access Tools (5)
- `list_frameworks` - List all available AI governance frameworks
- `get_framework` - Get complete content of a specific framework
- `search_frameworks` - Search for text within framework documents
- `list_risks` - List all available risk documents
- `get_risk` - Get complete content of specific risk documents

### Risk & Mitigation Tools (4)
- `search_risks` - Search within risk documentation
- `list_mitigations` - List all available mitigation documents
- `get_mitigation` - Get complete content of mitigation documents
- `search_mitigations` - Search within mitigation documentation

### System Monitoring Tools (2)
- `get_service_health` - Get service health status and metrics
- `get_cache_stats` - Get cache performance statistics

## Quick Examples

### List Available Frameworks
```
Use: list_frameworks()
Returns: 7 governance frameworks (NIST AI 600-1, EU AI Act, ISO 42001, etc.)
```

### Search Across Frameworks
```
Use: search_frameworks("risk management", 5)
Returns: 5 results matching "risk management" from all frameworks
```

### Get Framework Content
```
Use: get_framework("eu-ai-act")
Returns: Complete EU AI Act document content
```

### List Risks
```
Use: list_risks()
Returns: 17 AI governance risk documents from FINOS repository
```

### Search Risks
```
Use: search_risks("injection", 5)
Returns: Risks related to injection attacks
```

## Common Workflows

### Researching AI Governance
1. List available frameworks: `list_frameworks()`
2. Search for specific topics: `search_frameworks("data protection")`
3. Get full framework content: `get_framework("nist-ai-600-1")`

### Risk Assessment
1. List all risks: `list_risks()`
2. Search for specific risks: `search_risks("model bias")`
3. Get risk details: `get_risk("10_prompt-injection")`

### Mitigation Planning
1. List all mitigations: `list_mitigations()`
2. Search for mitigations: `search_mitigations("encryption")`
3. Get mitigation details: `get_mitigation("1_ai-data-leakage-prevention-and-detection")`

## Supported Frameworks

| Framework | Description |
|-----------|-------------|
| **NIST AI 600-1** | Artificial Intelligence Risk Management Framework |
| **EU AI Act** | European Union Artificial Intelligence Act |
| **ISO 42001** | AI Management Systems Standard |
| **FFIEC IT Booklets** | Federal Financial Institutions Examination Council IT guidance |
| **NIST SP 800-53** | Security and Privacy Controls for Information Systems |
| **OWASP LLM Top 10** | Top 10 security vulnerabilities for LLM applications |
| **OWASP ML Top 10** | Top 10 risks for machine learning systems |

## For More Information

- **[API Documentation](../api/README.md)** - Complete API reference for all 11 tools
- **[Tools Reference](../tools-reference.md)** - Detailed tool documentation
- **[Troubleshooting](../troubleshooting.md)** - Common issues and solutions
