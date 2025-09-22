# Getting Started with Framework Tools

This guide will get you up and running with the FINOS AI Governance Framework tools in just a few minutes.

## Prerequisites

Before you begin, ensure you have:
- Access to an MCP-compatible client (Claude, VS Code, Cursor)
- The FINOS MCP Server installed and running
- Basic understanding of AI governance concepts

## Your First 5 Minutes

### Step 1: Check System Status (30 seconds)

Start by verifying the system is working properly:

**Tool**: `get_service_health`
**Arguments**: None required

**What you'll see**:
```json
{
  "overall_status": "healthy",
  "uptime_seconds": 3456789,
  "services": {
    "framework_service": {"status": "healthy"},
    "content_service": {"status": "healthy"}
  }
}
```

**✅ Success indicator**: `overall_status: "healthy"`
**❌ If unhealthy**: Wait a few minutes and try again, or check the troubleshooting guide

### Step 2: Explore Available Frameworks (1 minute)

See what governance frameworks are available:

**Tool**: `list_frameworks`
**Arguments**:
```json
{
  "include_stats": true
}
```

**What you'll see**:
```json
{
  "total_frameworks": 7,
  "active_frameworks": 4,
  "frameworks": [
    {
      "id": "nist_ai_rmf",
      "name": "NIST AI Risk Management Framework",
      "status": "active",
      "reference_count": 30
    },
    {
      "id": "eu_ai_act",
      "name": "EU Artificial Intelligence Act",
      "status": "active",
      "reference_count": 42
    }
  ]
}
```

**Key insights**:
- **Active frameworks**: Live data, automatically updated
- **Reference count**: Number of requirements/controls available
- **Status**: Whether the framework is currently available

### Step 3: Your First Search (2 minutes)

Try searching across all frameworks for a common governance topic:

**Tool**: `search_frameworks`
**Arguments**:
```json
{
  "query": "risk management",
  "limit": 5
}
```

**What you'll see**:
```json
{
  "query": "risk management",
  "total_results": 15,
  "results": [
    {
      "framework": "nist_ai_rmf",
      "reference_id": "ai-rmf-1.1",
      "title": "Establish AI Risk Management Culture",
      "relevance_score": 0.92,
      "severity": "high"
    }
  ]
}
```

**Understanding the results**:
- **relevance_score**: How well the content matches your query (0.0-1.0)
- **severity**: Importance level (critical, high, medium, low)
- **framework**: Which standard the requirement comes from

### Step 4: Dive Deeper into a Framework (1 minute)

Get detailed information about a specific framework:

**Tool**: `get_framework_details`
**Arguments**:
```json
{
  "framework_id": "nist_ai_rmf",
  "include_references": false
}
```

**What you'll see**:
```json
{
  "framework": {
    "id": "nist_ai_rmf",
    "name": "NIST AI Risk Management Framework",
    "version": "1.0",
    "total_references": 30,
    "compliance_metrics": {
      "compliance_rate": 85.7
    }
  }
}
```

### Step 5: Quick Compliance Check (30 seconds)

Get an overview of your compliance status:

**Tool**: `get_compliance_analysis`
**Arguments**:
```json
{
  "include_gaps": true
}
```

**What you'll see**:
```json
{
  "analysis_summary": {
    "overall_compliance_rate": 78.5,
    "critical_gaps": 5
  },
  "framework_compliance": [
    {
      "framework": "nist_ai_rmf",
      "compliance_rate": 85.7,
      "status": "good"
    }
  ]
}
```

## Understanding Framework Types

### Active Frameworks 🟢
These frameworks have live data from official sources:

- **NIST AI RMF**: Updated from NIST's official publications
- **EU AI Act**: Current regulatory text and guidance
- **OWASP LLM Top 10**: Latest security vulnerability information
- **GDPR**: Official regulation text and interpretations

**Benefits**: Always current, authoritative sources
**Note**: May occasionally be unavailable if source APIs are down

### Modeled Frameworks 🟡
These frameworks use internal data models:

- **CCPA**: California Consumer Privacy Act
- **ISO 27001**: Information Security Management
- **SOC 2**: Service Organization Controls

**Benefits**: Always available, consistent structure
**Note**: Updated manually, may lag behind official changes

## Common Use Cases

### 🎯 For Compliance Teams

**Goal**: Assess organizational compliance across multiple frameworks

**Recommended workflow**:
1. `list_frameworks` - See what's available
2. `get_compliance_analysis` - Get overall status
3. `find_compliance_gaps` - Identify priority areas
4. `export_framework_data` - Generate reports

### 🔍 For Risk Managers

**Goal**: Find and analyze risk-related requirements

**Recommended workflow**:
1. `search_frameworks` with "risk" or "threat"
2. `search_framework_references` for specific frameworks
3. `get_related_controls` - Map controls across frameworks
4. `export_framework_data` - Create risk documentation

### 📋 For Auditors

**Goal**: Compare compliance across different standards

**Recommended workflow**:
1. `get_framework_correlations` - Understand relationships
2. `find_compliance_gaps` - Identify missing controls
3. `get_compliance_analysis` - Generate metrics
4. `bulk_export_frameworks` - Create comprehensive reports

## Quick Reference Commands

### Essential Tools for Everyone
```bash
# Check if system is working
get_service_health

# See available frameworks
list_frameworks

# Search across all frameworks
search_frameworks {"query": "your topic"}

# Get framework details
get_framework_details {"framework_id": "nist_ai_rmf"}
```

### For Compliance Analysis
```bash
# Overall compliance status
get_compliance_analysis

# Find gaps between frameworks
find_compliance_gaps {"source_framework": "nist_ai_rmf", "target_frameworks": ["eu_ai_act"]}

# Export compliance report
export_framework_data {"framework_id": "nist_ai_rmf", "format": "csv"}
```

### For Cross-Framework Work
```bash
# Find related controls
get_related_controls {"control_id": "ai-rmf-1.1"}

# Analyze framework relationships
get_framework_correlations {"framework_a": "nist_ai_rmf", "framework_b": "eu_ai_act"}
```

## Tips for Success

### 🎯 Search Effectively
- **Be specific**: "data protection" vs "privacy"
- **Try variations**: "risk assessment" and "risk evaluation"
- **Use quotes**: "prompt injection" for exact phrases
- **Check all frameworks**: Different frameworks use different terminology

### 📊 Understand Results
- **Relevance scores**: 0.8+ are highly relevant, 0.5+ are worth reviewing
- **Severity levels**: Focus on "critical" and "high" first
- **Framework context**: Same concept may have different names in different frameworks

### 🔄 Build Your Workflow
- **Start broad**: Use multi-framework search first
- **Narrow down**: Use framework-specific searches for details
- **Map relationships**: Use correlation tools to understand connections
- **Document findings**: Export results for future reference

### ⚡ Performance Tips
- **Use limits**: Set reasonable limits (10-20) for initial searches
- **Cache results**: Same searches return cached results quickly
- **Check health**: If responses are slow, check service health

## What's Next?

Now that you're familiar with the basics:

1. **Deep dive into search**: Read the [Framework Search Guide](framework-search.md)
2. **Learn compliance analysis**: See [Compliance Analysis](compliance-analysis.md)
3. **Explore cross-framework features**: Check [Cross-Framework Navigation](cross-framework-navigation.md)
4. **Generate reports**: Learn about [Export and Reporting](export-reporting.md)

## Common First-Time Questions

### Q: How do I know which framework to start with?
**A**: Start with `list_frameworks` to see what's available, then use `search_frameworks` with your main compliance topic to see which frameworks have relevant content.

### Q: What if a framework shows as "unavailable"?
**A**: Active frameworks occasionally go offline. Check `get_service_health` and try again in a few minutes. You can still access cached data.

### Q: How current is the framework data?
**A**: Active frameworks are updated regularly from official sources. Check the `last_updated` field in framework details for specific timestamps.

### Q: Can I search for specific regulation numbers or control IDs?
**A**: Yes! Use `search_framework_references` with the specific framework and search for the exact ID or number.

### Q: How do I export results for my team?
**A**: Use `export_framework_data` with format "csv" for spreadsheets, "json" for data analysis, or "markdown" for documentation.

You're now ready to start using the framework tools effectively! Choose your next guide based on your primary use case.