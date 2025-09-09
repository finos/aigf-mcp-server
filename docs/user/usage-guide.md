# 📖 FINOS AI Governance MCP Server - Usage Guide

Complete guide for using the FINOS AI Governance MCP Server to access AI governance content through the Model Context Protocol.

## 📋 Table of Contents

- [Overview](#overview)
- [Available Tools](#available-tools)
- [Search Operations](#search-operations)
- [Content Retrieval](#content-retrieval)
- [Usage Examples](#usage-examples)
- [Best Practices](#best-practices)

## 🔍 Overview

The FINOS AI Governance MCP Server provides access to comprehensive AI governance content including:
- **17 Mitigations** (mi-1 through mi-17): AI governance strategies and controls
- **17 Risk Assessments** (ri-1 through ri-23): AI risk evaluations and frameworks

All content is sourced from the official [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework).

## 🛠️ Available Tools

### Search Tools
- **`search_mitigations`** - Search through AI governance mitigations
- **`search_risks`** - Search through AI risk assessments

### Content Retrieval Tools
- **`get_mitigation_details`** - Get complete mitigation by ID (e.g., "mi-1")
- **`get_risk_details`** - Get complete risk assessment by ID (e.g., "ri-10")

### Listing Tools
- **`list_all_mitigations`** - List all available mitigations with metadata
- **`list_all_risks`** - List all available risks with metadata

## 🔍 Search Operations

### Searching Mitigations

**Basic search:**
```python
search_mitigations(query="data privacy")
```

**Common search topics:**
- Data protection: `"data leakage"`, `"privacy"`, `"confidentiality"`
- Model security: `"model security"`, `"adversarial"`, `"robustness"`
- Governance: `"compliance"`, `"audit"`, `"oversight"`
- Operations: `"monitoring"`, `"testing"`, `"validation"`

### Searching Risks

**Basic search:**
```python
search_risks(query="prompt injection")
```

**Common risk categories:**
- Input attacks: `"prompt injection"`, `"input manipulation"`
- Output issues: `"hallucination"`, `"bias"`, `"toxicity"`
- Data concerns: `"data poisoning"`, `"privacy leakage"`
- Model vulnerabilities: `"adversarial"`, `"extraction"`

## 📄 Content Retrieval

### Get Specific Mitigations

**Available mitigation IDs:** mi-1, mi-2, mi-3, mi-4, mi-5, mi-6, mi-7, mi-8, mi-9, mi-10, mi-11, mi-12, mi-13, mi-14, mi-15, mi-16, mi-17

```python
# Get data leakage prevention mitigation
get_mitigation_details(mitigation_id="mi-1")

# Get AI system testing mitigation
get_mitigation_details(mitigation_id="mi-7")
```

### Get Specific Risk Assessments

**Available risk IDs:** ri-1, ri-2, ri-3, ri-4, ri-5, ri-6, ri-7, ri-8, ri-9, ri-10, ri-11, ri-12, ri-13, ri-14, ri-15, ri-16, ri-17, ri-18, ri-19, ri-20, ri-21, ri-22, ri-23

```python
# Get prompt injection risk assessment
get_risk_details(risk_id="ri-10")

# Get data poisoning risk assessment
get_risk_details(risk_id="ri-3")
```

## 💡 Usage Examples

### Example 1: Finding Data Protection Guidance

**Scenario:** You need to implement data protection measures for your AI system.

```python
# Step 1: Search for data-related mitigations
search_mitigations(query="data protection")

# Step 2: Get specific mitigation details
get_mitigation_details(mitigation_id="mi-1")  # Data leakage prevention

# Step 3: Search for related risks
search_risks(query="data leakage")
```

### Example 2: Addressing Prompt Injection Concerns

**Scenario:** You're concerned about prompt injection attacks.

```python
# Step 1: Search for prompt injection risks
search_risks(query="prompt injection")

# Step 2: Get detailed risk assessment
get_risk_details(risk_id="ri-10")  # Prompt injection and jailbreaking

# Step 3: Find relevant mitigations
search_mitigations(query="input validation")
```

### Example 3: Comprehensive AI Governance Audit

**Scenario:** You need to conduct a comprehensive governance review.

```python
# Step 1: List all available content
list_all_mitigations()
list_all_risks()

# Step 2: Focus on high-priority areas
search_mitigations(query="governance")
search_risks(query="compliance")

# Step 3: Get specific frameworks
get_mitigation_details(mitigation_id="mi-2")  # AI governance framework
```

### Example 4: Model Security Assessment

**Scenario:** You want to assess and secure your AI model.

```python
# Step 1: Search for security-related content
search_mitigations(query="model security")
search_risks(query="adversarial")

# Step 2: Get comprehensive guidance
get_mitigation_details(mitigation_id="mi-3")  # Model security and robustness
get_risk_details(risk_id="ri-12")             # Adversarial attacks
```

## 📊 Understanding Content Structure

### Mitigation Documents Include:
- **Metadata**: Sequence, title, status, type, standards references
- **Purpose**: Overview and scope
- **Key Principles**: Fundamental strategies
- **Implementation Guidance**: Detailed action items
- **Importance and Benefits**: Justification and value

### Risk Assessment Documents Include:
- **Metadata**: Sequence, title, status, framework references
- **Summary**: Brief risk overview
- **Description**: Detailed explanation
- **Consequences**: Potential impacts
- **Key Risks**: Highlighted areas
- **Links**: Additional resources

## 🎯 Best Practices

### Search Strategy
1. **Start broad**: Use general terms like "security", "privacy", "governance"
2. **Refine specific**: Move to specific terms like "data leakage", "prompt injection"
3. **Cross-reference**: Search both mitigations and risks for complete coverage
4. **Use IDs**: When you know specific document IDs, use direct retrieval

### Content Usage
1. **Read metadata**: Understand document status and applicability
2. **Check references**: Note framework alignments (ISO 42001, NIST AI, OWASP)
3. **Implement systematically**: Follow implementation guidance step-by-step
4. **Monitor updates**: Content is regularly updated from FINOS framework

### Performance Optimization
1. **Cache effectively**: Related queries benefit from the built-in cache
2. **Batch operations**: Plan multiple queries to minimize network calls
3. **Use specific IDs**: Direct retrieval is faster than search when you know the ID

## 🔒 Data and Privacy

### Content Source
- All content is sourced from the public [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework)
- No proprietary or confidential information is stored or transmitted
- Content updates automatically reflect the latest FINOS framework updates

### Privacy Considerations
- No user queries or content access patterns are logged or stored
- All communications use standard MCP protocol security
- GitHub API access uses minimal permissions (public repository read-only)

## 📈 Monitoring Usage

### Performance Indicators
The server provides built-in health monitoring:
- **Response Times**: Typical queries complete in <1 second
- **Success Rates**: >95% success rate under normal conditions
- **Cache Performance**: High cache hit rates improve response times

### Health Status
- 🟢 **Healthy**: >80% success rate, <5s response time
- 🟡 **Degraded**: 50-80% success rate OR >5s response time
- 🔴 **Unhealthy**: <50% success rate

## 🆘 Getting Help

### Common Issues

**No results found:**
- Try broader search terms
- Check spelling and terminology
- Use `list_all_mitigations()` or `list_all_risks()` to see available content

**Slow responses:**
- Check network connectivity
- Consider GitHub token for better rate limits
- Review server configuration (timeout settings)

**Content seems outdated:**
- Server automatically fetches latest content from FINOS framework
- Clear cache by restarting server if needed

### Support Resources

1. **[Installation Guide](installation-guide.md)** - Setup and configuration help
2. **[Installation Reference](installation-guide.md)** - Configuration and setup options
3. **[GitHub Issues](https://github.com/hugo-calderon/finos-mcp-server/issues)** - Bug reports and feature requests

---

> **Ready to integrate?** Check the [Installation Guide](installation-guide.md) for Claude Code integration setup.
