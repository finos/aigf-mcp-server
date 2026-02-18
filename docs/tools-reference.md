# 🛠️ Tools Reference

Quick reference for all 11 available MCP tools organized in 3 categories.

## Framework Access Tools (5)

### `list_frameworks`
**Purpose**: List all supported AI governance frameworks
**Usage**: `list_frameworks()`
**Returns**: Structured list of available frameworks with descriptions

**Supported Frameworks**:
- NIST AI 600-1 (Artificial Intelligence Risk Management Framework)
- EU AI Act (European Union Artificial Intelligence Act)
- ISO 42001 (AI Management Systems Standard)
- FFIEC IT Booklets (Federal Financial Institutions Examination Council IT guidance)
- NIST SP 800-53 (Security and Privacy Controls for Information Systems)
- OWASP LLM Top 10 (Top 10 security vulnerabilities for LLM applications)
- OWASP ML Top 10 (Top 10 risks for machine learning systems)

### `get_framework`
**Purpose**: Get complete content of a specific framework
**Usage**: `get_framework("nist-ai-600-1")`
**Parameters**: framework (string) - Framework ID from list_frameworks
**Returns**: Framework content with metadata and section count

**Example Usage**:
```
get_framework("eu-ai-act")
get_framework("iso-42001")
get_framework("owasp-llm")
```

### `search_frameworks`
**Purpose**: Search for text within framework documents
**Usage**: `search_frameworks("bias", 5)`
**Parameters**:
- query (string) - Search term to find in framework content
- limit (int, optional) - Maximum number of results (default: 5)
**Returns**: Search results with matching content snippets

### `list_risks`
**Purpose**: List available risk documents
**Usage**: `list_risks()`
**Returns**: Structured list of risk documents from GitHub repository

### `get_risk`
**Purpose**: Get complete content of a specific risk document
**Usage**: `get_risk("10_prompt-injection")`
**Parameters**: risk_id (string) - Risk ID from list_risks
**Returns**: Full risk document content with metadata and sections

## Risk & Mitigation Tools (4)

### `search_risks`
**Purpose**: Search within risk documentation
**Usage**: `search_risks("privacy", 3)`
**Parameters**:
- query (string) - Search term to find in risk content
- limit (int, optional) - Maximum number of results (default: 5)
**Returns**: Search results with matching risk content snippets

### `list_mitigations`
**Purpose**: List available mitigation documents
**Usage**: `list_mitigations()`
**Returns**: Structured list of mitigation documents from GitHub repository

### `get_mitigation`
**Purpose**: Get complete content of a specific mitigation document
**Usage**: `get_mitigation("1_ai-data-leakage-prevention-and-detection")`
**Parameters**: mitigation_id (string) - Mitigation ID from list_mitigations
**Returns**: Full mitigation document content with metadata and sections

### `search_mitigations`
**Purpose**: Search within mitigation documentation
**Usage**: `search_mitigations("encryption", 3)`
**Parameters**:
- query (string) - Search term to find in mitigation content
- limit (int, optional) - Maximum number of results (default: 5)
**Returns**: Search results with matching mitigation content snippets

## System Monitoring Tools

### `get_service_health`
**Purpose**: Get current service health status
**Usage**: `get_service_health()`
**Returns**: Health metrics including uptime, version, and service status

**Health Metrics**:
- Service status (healthy/degraded)
- Uptime in seconds
- Server version
- Service component health

### `get_cache_stats`
**Purpose**: Get cache performance statistics
**Usage**: `get_cache_stats()`
**Returns**: Cache performance metrics and hit rates

**Cache Metrics**:
- Total requests processed
- Cache hits and misses
- Hit rate percentage
- Performance statistics

---

## MCP Prompts (3)

### `analyze_framework_compliance`
**Purpose**: Analyze compliance requirements across AI governance frameworks
**Usage**: Available as MCP prompt template for compliance analysis
**Parameters**: Framework selection and compliance requirements
**Returns**: Structured compliance gap analysis and recommendations

### `risk_assessment_analysis`
**Purpose**: Conduct comprehensive AI risk assessment using FINOS methodology
**Usage**: Available as MCP prompt template for risk evaluation
**Parameters**: AI system description and risk categories
**Returns**: Risk assessment matrix with severity ratings and mitigation priorities

### `mitigation_strategy_prompt`
**Purpose**: Develop comprehensive mitigation strategies for identified AI risks
**Usage**: Available as MCP prompt template for mitigation planning
**Parameters**: Risk profile and organizational context
**Returns**: Tailored mitigation strategy with implementation roadmap

---

## MCP Resources (3)

### `finos://frameworks/{id}`
**Purpose**: URI-based access to framework content
**Usage**: Direct resource access via MCP resource protocol
**Examples**:
- `finos://frameworks/nist-ai-600-1`
- `finos://frameworks/eu-ai-act`
- `finos://frameworks/iso-42001`

### `finos://risks/{id}`
**Purpose**: URI-based access to risk documents
**Usage**: Direct resource access via MCP resource protocol
**Examples**:
- `finos://risks/10_prompt-injection`
- `finos://risks/9_data-poisoning`

### `finos://mitigations/{id}`
**Purpose**: URI-based access to mitigation documents
**Usage**: Direct resource access via MCP resource protocol
**Examples**:
- `finos://mitigations/1_ai-data-leakage-prevention-and-detection`
- `finos://mitigations/10_ai-model-version-pinning`

---

## Tool Output Format

All tools return structured Pydantic models with type safety and validation. This follows the MCP 2025-06-18 specification for consistent tool integration and structured output.

## Error Handling

All tools include comprehensive error handling:
- Invalid framework IDs return structured error responses
- Network issues are handled gracefully
- Service degradation is reported in health metrics

---

For implementation examples and integration guides, see the [User Guide](user-guide/).
