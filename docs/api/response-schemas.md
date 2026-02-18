# Response Schemas

Detailed schemas and examples for all 11 MCP tool responses in the FINOS AI Governance Framework server.

## Common Response Elements

### Base Response Structure

All successful tool responses follow the MCP protocol structure with Pydantic models:

```json
{
  "content": [
    {
      "type": "text",
      "text": "Response content in JSON or formatted text"
    }
  ]
}
```

### Error Response Structure

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": "object (optional)"
  }
}
```

## Framework Access Tools (5 tools)

### 1. list_frameworks Response

Lists all available AI governance frameworks.

**Response Schema**:
```json
{
  "total_count": 5,
  "frameworks": [
    {
      "id": "nist-ai-600-1",
      "name": "NIST AI Risk Management Framework",
      "description": "US federal AI governance framework"
    },
    {
      "id": "eu-ai-act",
      "name": "EU AI Act 2024",
      "description": "European Union AI regulation"
    },
    {
      "id": "gdpr",
      "name": "GDPR",
      "description": "General Data Protection Regulation"
    },
    {
      "id": "owasp-llm",
      "name": "OWASP LLM Top 10",
      "description": "AI security best practices"
    },
    {
      "id": "iso-23053",
      "name": "ISO/IEC 23053",
      "description": "International AI standards"
    }
  ]
}
```

**Field Descriptions**:
- `total_count` (integer): Total number of frameworks available
- `frameworks` (array): List of framework objects
  - `id` (string): Framework identifier for use with get_framework
  - `name` (string): Human-readable framework name
  - `description` (string): Brief description of the framework

---

### 2. get_framework Response

Gets complete content of a specific framework.

**Response Schema**:
```json
{
  "framework_id": "nist-ai-600-1",
  "sections": [
    "Introduction",
    "Core Principles",
    "Implementation Guidance",
    "References"
  ],
  "content": "# NIST AI Risk Management Framework\n\n## Introduction\n\nThe NIST AI RMF provides guidance for managing AI risks..."
}
```

**Field Descriptions**:
- `framework_id` (string): The framework identifier
- `sections` (array of strings): List of section titles in the framework
- `content` (string): Complete framework content in markdown format

**Example**:
```python
# Request
mcp_client.call_tool("get_framework", {"framework": "nist-ai-600-1"})

# Response includes full framework content with all sections
```

---

### 3. search_frameworks Response

Searches for text within framework documents.

**Response Schema**:
```json
{
  "query": "risk management",
  "total_found": 15,
  "results": [
    {
      "framework_id": "nist-ai-600-1",
      "section": "Core Principles",
      "content": "...establishing a comprehensive risk management framework for AI systems..."
    },
    {
      "framework_id": "eu-ai-act",
      "section": "Risk Assessment",
      "content": "...AI systems shall implement risk management procedures..."
    }
  ]
}
```

**Field Descriptions**:
- `query` (string): The search query that was executed
- `total_found` (integer): Total number of matching results
- `results` (array): List of search result objects
  - `framework_id` (string): Framework where match was found
  - `section` (string): Section title containing the match
  - `content` (string): Content snippet with matching text

**Example**:
```python
# Request
mcp_client.call_tool("search_frameworks", {
    "query": "data protection",
    "limit": 5
})

# Returns up to 5 matching results across all frameworks
```

---

### 4. list_risks Response

Lists all available risk documents.

**Response Schema**:
```json
{
  "total_count": 23,
  "source": "github_api",
  "documents": [
    {
      "id": "1_information-leaked-to-hosted-model",
      "name": "Ri 1 Information Leaked To Hosted Model"
    },
    {
      "id": "9_data-poisoning",
      "name": "Ri 9 Data Poisoning"
    },
    {
      "id": "10_prompt-injection",
      "name": "Prompt Injection"
    }
  ]
}
```

**Field Descriptions**:
- `total_count` (integer): Total number of risk documents available
- `source` (string): Data source ("github_api" or "static_fallback")
- `documents` (array): List of risk document objects
  - `id` (string): Risk identifier for use with get_risk
  - `name` (string): Human-readable risk name

---

### 5. get_risk Response

Gets complete content of a specific risk document.

**Response Schema**:
```json
{
  "document_id": "10_prompt-injection",
  "title": "Ri 10 Prompt Injection",
  "sections": [
    "Description",
    "Attack Vectors",
    "Impact Assessment",
    "Mitigation Strategies"
  ],
  "content": "# Model Inversion Attacks\n\n## Description\n\nModel inversion attacks occur when..."
}
```

**Field Descriptions**:
- `document_id` (string): The risk document identifier
- `title` (string): Risk document title
- `sections` (array of strings): List of section titles
- `content` (string): Complete risk document content in markdown format

---

## Risk & Mitigation Tools (4 tools)

### 6. search_risks Response

Searches within risk documentation.

**Response Schema**:
```json
{
  "query": "injection",
  "total_found": 3,
  "results": [
    {
      "framework_id": "risk-10_prompt-injection",
      "section": "Prompt Injection",
      "content": "...prompt injection attacks allow malicious users to manipulate..."
    },
    {
      "framework_id": "risk-9_data-poisoning",
      "section": "Ri 9 Data Poisoning",
      "content": "...training data poisoning can compromise model behavior..."
    }
  ]
}
```

**Field Descriptions**:
- `query` (string): The search query executed
- `total_found` (integer): Total number of matching results
- `results` (array): List of search result objects
  - `framework_id` (string): Prefixed risk ID where match was found (`risk-{id}`)
  - `section` (string): Risk name/title
  - `content` (string): Content snippet with matching text

---

### 7. list_mitigations Response

Lists all available mitigation documents.

**Response Schema**:
```json
{
  "total_count": 23,
  "source": "github_api",
  "documents": [
    {
      "id": "1_ai-data-leakage-prevention-and-detection",
      "name": "Mi 1 Ai Data Leakage Prevention And Detection"
    },
    {
      "id": "12_role-based-access-control-for-ai-data",
      "name": "Mi 12 Role Based Access Control For Ai Data"
    },
    {
      "id": "10_ai-model-version-pinning",
      "name": "AI Model Version Pinning"
    }
  ]
}
```

**Field Descriptions**:
- `total_count` (integer): Total number of mitigation documents available
- `source` (string): Data source ("github_api" or "static_fallback")
- `documents` (array): List of mitigation document objects
  - `id` (string): Mitigation identifier for use with get_mitigation
  - `name` (string): Human-readable mitigation name

---

### 8. get_mitigation Response

Gets complete content of a specific mitigation document.

**Response Schema**:
```json
{
  "document_id": "1_ai-data-leakage-prevention-and-detection",
  "title": "Mi 1 Ai Data Leakage Prevention And Detection",
  "sections": [
    "Overview",
    "Implementation Steps",
    "Best Practices",
    "Tools and Technologies"
  ],
  "content": "# Data Encryption\n\n## Overview\n\nData encryption is a fundamental mitigation..."
}
```

**Field Descriptions**:
- `document_id` (string): The mitigation document identifier
- `title` (string): Mitigation document title
- `sections` (array of strings): List of section titles
- `content` (string): Complete mitigation document content in markdown format

---

### 9. search_mitigations Response

Searches within mitigation documentation.

**Response Schema**:
```json
{
  "query": "encryption",
  "total_found": 5,
  "results": [
    {
      "framework_id": "mitigation-1_ai-data-leakage-prevention-and-detection",
      "section": "Mi 1 Ai Data Leakage Prevention And Detection",
      "content": "...implement strong encryption algorithms for data at rest..."
    },
    {
      "framework_id": "mitigation-14_encryption-of-ai-data-at-rest",
      "section": "Mi 14 Encryption Of Ai Data At Rest",
      "content": "...implement strong encryption controls for AI data at rest..."
    }
  ]
}
```

**Field Descriptions**:
- `query` (string): The search query executed
- `total_found` (integer): Total number of matching results
- `results` (array): List of search result objects
  - `framework_id` (string): Prefixed mitigation ID where match was found (`mitigation-{id}`)
  - `section` (string): Mitigation name/title
  - `content` (string): Content snippet with matching text

---

## System Monitoring Tools (2 tools)

### 10. get_service_health Response

Gets service health status and metrics.

**Response Schema**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 345678,
  "healthy_services": 5,
  "total_services": 5
}
```

**Field Descriptions**:
- `status` (string): Overall health status ("healthy", "degraded", "unhealthy")
- `version` (string): MCP server version
- `uptime_seconds` (number): Server uptime in seconds
- `healthy_services` (integer): Number of healthy service components
- `total_services` (integer): Total number of service components

**Status Values**:
- `healthy`: All services operational
- `degraded`: Some services have issues but core functionality works
- `unhealthy`: Critical services are down

**Example**:
```python
# Request
mcp_client.call_tool("get_service_health", {})

# Response
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "healthy_services": 5,
  "total_services": 5
}
```

---

### 11. get_cache_stats Response

Gets cache performance statistics.

**Response Schema**:
```json
{
  "total_requests": 10450,
  "cache_hits": 9932,
  "cache_misses": 518,
  "hit_rate": 0.9504
}
```

**Field Descriptions**:
- `total_requests` (integer): Total number of cache requests processed
- `cache_hits` (integer): Number of successful cache hits
- `cache_misses` (integer): Number of cache misses (data not in cache)
- `hit_rate` (number): Cache hit rate as decimal (0.0 to 1.0)

**Performance Metrics**:
- Hit rate > 0.90: Excellent cache performance
- Hit rate 0.75-0.90: Good cache performance
- Hit rate < 0.75: Consider reviewing cache strategy

**Example**:
```python
# Request
mcp_client.call_tool("get_cache_stats", {})

# Response
{
  "total_requests": 1000,
  "cache_hits": 950,
  "cache_misses": 50,
  "hit_rate": 0.95  # 95% hit rate
}
```

---

## Error Response Examples

### Validation Error

Returned when input parameters are invalid.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {
      "field": "framework",
      "value": "invalid_framework",
      "expected": "Valid framework ID from list_frameworks"
    }
  }
}
```

**Common Validation Errors**:
- Invalid framework in get_framework
- Invalid risk_id in get_risk
- Invalid mitigation_id in get_mitigation
- Invalid limit parameter (must be 1-20)

---

### Resource Not Found

Returned when requested resource doesn't exist.

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Requested resource not found",
    "details": {
      "resource_type": "framework",
      "resource_id": "nonexistent_framework",
      "suggestion": "Use list_frameworks to see available frameworks"
    }
  }
}
```

**Common Not Found Scenarios**:
- Framework ID doesn't exist
- Risk ID doesn't exist
- Mitigation ID doesn't exist

---

### Service Unavailable

Returned when service is temporarily unavailable.

```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Content service temporarily unavailable",
    "details": {
      "service": "github_content_loader",
      "retry_after": 30,
      "fallback_available": true
    }
  }
}
```

**Recovery Actions**:
- Wait and retry after specified seconds
- System may fall back to static content
- Check get_service_health for status

---

## Response Patterns

### Pagination

Search tools support limit parameter for result pagination:

```python
# Get first 5 results
search_frameworks("query", limit=5)

# Get next 5 results (requires offset parameter in future versions)
search_frameworks("query", limit=5, offset=5)
```

**Current Limitations**:
- Offset parameter not yet implemented
- Maximum limit: 50 results per query
- Default limit: 5 results

### Content Format

All content is returned in markdown format for easy rendering:

```python
# Framework content example
{
  "content": "# Framework Title\n\n## Section 1\n\nContent here..."
}
```

**Markdown Features Used**:
- Headers (# ## ###)
- Lists (ordered and unordered)
- Code blocks
- Links
- Emphasis (bold/italic)

### Caching Behavior

The server implements intelligent caching:

- Framework content: Cached for 1 hour
- Risk/mitigation lists: Cached for 30 minutes
- Search results: Cached for 15 minutes
- Health status: Not cached (live data)

**Cache Control**:
- Client cannot control cache directly
- Use get_cache_stats to monitor cache performance
- Cache automatically invalidated on server restart

---

## Response Size Limits

| Tool | Typical Size | Maximum Size |
|------|-------------|--------------|
| list_frameworks | 2KB | 10KB |
| get_framework | 50-500KB | 5MB |
| search_frameworks | 5-50KB | 500KB |
| list_risks | 2KB | 10KB |
| get_risk | 10-100KB | 1MB |
| search_risks | 5-50KB | 500KB |
| list_mitigations | 2KB | 10KB |
| get_mitigation | 10-100KB | 1MB |
| search_mitigations | 5-50KB | 500KB |
| get_service_health | 1KB | 5KB |
| get_cache_stats | 500B | 2KB |

**Note**: Large responses are automatically formatted for optimal display in MCP clients.

---

## Response Performance

### Expected Response Times

| Tool Category | Cached | Uncached (GitHub API) |
|---------------|--------|----------------------|
| List operations | <10ms | 100-500ms |
| Get operations | <50ms | 500-2000ms |
| Search operations | 10-100ms | 200-1000ms |
| System operations | <5ms | N/A (not cached) |

**Optimization Tips**:
- Use list operations before get operations
- Implement client-side caching for frequently accessed content
- Monitor cache performance with get_cache_stats
- Batch related queries when possible

---

## Tool Response Consistency

All 11 tools follow consistent response patterns:

1. **Structured Output**: Pydantic models ensure type safety
2. **Error Handling**: Consistent error format across all tools
3. **Content Format**: Markdown for all document content
4. **Metadata**: Consistent field naming and types

This consistency makes integration easier and more predictable across all MCP clients.
