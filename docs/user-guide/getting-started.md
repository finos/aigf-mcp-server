# Getting Started

Quick start guide for using the FINOS AI Governance MCP Server's 11 tools.

## Prerequisites

- Access to an MCP-compatible client (Claude Desktop, VS Code, Cursor)
- FINOS MCP Server installed and running
- Basic understanding of AI governance concepts

## Your First 5 Minutes

### Step 1: Check System Status

Verify the system is working:

```
Tool: get_service_health()
Returns: {status: "healthy", uptime_seconds: 3600, healthy_services: 5, total_services: 5}
```

### Step 2: Explore Available Frameworks

See what governance frameworks are available:

```
Tool: list_frameworks()
Returns: 5 frameworks (NIST AI 600-1, EU AI Act 2024, GDPR, OWASP LLM Top 10, ISO/IEC 23053)
```

### Step 3: Search Across Frameworks

Try your first search:

```
Tool: search_frameworks("risk management", 5)
Returns: 5 results matching "risk management" across all frameworks
```

### Step 4: Get Framework Content

Retrieve a complete framework:

```
Tool: get_framework("nist-ai-600-1")
Returns: Complete NIST AI RMF content with all sections
```

### Step 5: Explore Risks and Mitigations

Browse AI governance risks:

```
Tool: list_risks()
Returns: 17 risk documents from FINOS AI Governance Framework
```

Search for specific risks:

```
Tool: search_risks("injection", 5)
Returns: Risks related to injection attacks
```

Get risk details:

```
Tool: get_risk("10_prompt-injection")
Returns: Complete prompt injection risk documentation
```

## Common Use Cases

### Researching AI Governance
1. `list_frameworks()` - See all available frameworks
2. `search_frameworks("data protection")` - Find relevant content
3. `get_framework("eu-ai-act")` - Get full framework

### Risk Assessment
1. `list_risks()` - Browse all risks
2. `search_risks("model bias")` - Find specific risks
3. `get_risk("10_prompt-injection")` - Get risk details

### Mitigation Planning
1. `list_mitigations()` - Browse all mitigations
2. `search_mitigations("encryption")` - Find relevant mitigations
3. `get_mitigation("1_ai-data-leakage-prevention-and-detection")` - Get mitigation details

### System Monitoring
1. `get_service_health()` - Check system status
2. `get_cache_stats()` - Monitor performance

## Next Steps

- **[User Guide](README.md)** - Complete tool reference
- **[API Documentation](../api/README.md)** - Detailed API reference
- **[Troubleshooting](../troubleshooting.md)** - Common issues and solutions

## Tips for Success

- Start with broad searches, then narrow down
- Use `list_*` tools to browse available content
- Use `search_*` tools to find specific topics
- Use `get_*` tools to retrieve complete documents
- Check `get_service_health()` if you encounter issues
