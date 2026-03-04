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
  "total_count": 3,
  "source": "github_api",
  "message": null,
  "frameworks": [
    {
      "id": "nist-ai-600-1",
      "name": "NIST AI Risk Management Framework",
      "description": "Framework definition: NIST AI Risk Management Framework",
      "title": "NIST AI Risk Management Framework"
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
- `source` (string | null): Discovery source (`github_api` or `unavailable`)
- `message` (string | null): Discovery status detail for degraded scenarios
- `frameworks` (array): List of framework objects
  - `id` (string): Framework identifier for use with get_framework
  - `name` (string): Human-readable framework name
  - `description` (string): Brief description of the framework
  - `title` (string | null): Display-friendly framework title

---

### 2. get_framework Response

Gets complete content of a specific framework.

**Response Schema**:
```json
{
  "framework_id": "nist-ai-600-1",
  "sections": 12,
  "content": "# NIST AI Risk Management Framework\n\n## Introduction\n\nThe NIST AI RMF provides guidance for managing AI risks..."
}
```

**Field Descriptions**:
- `framework_id` (string): The framework identifier
- `sections` (integer): Estimated count of top-level framework sections
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
  "message": null,
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
- `message` (string | null): Optional message when discovery is unavailable
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
  "total_count": 3,
  "source": "github_api",
  "message": null,
  "documents": [
    {
      "id": "1_information-leaked-to-hosted-model",
      "name": "Information Leaked to Hosted Model (RI-1)",
      "filename": "ri-1_information-leaked-to-hosted-model.md",
      "description": "AI governance risk: Information Leaked to Hosted Model (RI-1)",
      "last_modified": "2026-03-04T15:20:10+00:00",
      "title": "Information Leaked to Hosted Model (RI-1)"
    },
    {
      "id": "9_data-poisoning",
      "name": "Data Poisoning (RI-9)",
      "filename": "ri-9_data-poisoning.md",
      "description": "AI governance risk: Data Poisoning (RI-9)",
      "last_modified": "2026-03-04T15:20:10+00:00",
      "title": "Data Poisoning (RI-9)"
    },
    {
      "id": "10_prompt-injection",
      "name": "Prompt Injection (RI-10)",
      "filename": "ri-10_prompt-injection.md",
      "description": "AI governance risk: Prompt Injection (RI-10)",
      "last_modified": "2026-03-04T15:20:10+00:00",
      "title": "Prompt Injection (RI-10)"
    }
  ]
}
```

**Field Descriptions**:
- `total_count` (integer): Total number of risk documents available in current discovery run
- `source` (string): Data source (`github_api` or `unavailable`)
- `message` (string | null): Discovery status detail when degraded
- `documents` (array): List of risk document objects
  - `id` (string): Risk identifier for use with get_risk
  - `name` (string): Human-readable risk name
  - `filename` (string): Canonical markdown filename in source repository
  - `description` (string | null): Short document description
  - `last_modified` (string | null): Last modified timestamp (ISO-8601)
  - `title` (string | null): Display-friendly title

---

### 5. get_risk Response

Gets complete content of a specific risk document.

**Response Schema**:
```json
{
  "document_id": "10_prompt-injection",
  "title": "Prompt Injection (RI-10)",
  "sections": [
    "Description",
    "Attack Vectors",
    "Impact Assessment",
    "Mitigation Strategies"
  ],
  "content": "# Prompt Injection\n\n## Description\n\nPrompt injection attacks occur when..."
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
  "message": null,
  "results": [
    {
      "framework_id": "risk-10_prompt-injection",
      "section": "Prompt Injection",
      "content": "...prompt injection attacks allow malicious users to manipulate..."
    },
    {
      "framework_id": "risk-9_data-poisoning",
      "section": "Data Poisoning (RI-9)",
      "content": "...training data poisoning can compromise model behavior..."
    }
  ]
}
```

**Field Descriptions**:
- `query` (string): The search query executed
- `total_found` (integer): Total number of matching results
- `message` (string | null): Optional message when discovery is unavailable
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
  "total_count": 3,
  "source": "github_api",
  "message": null,
  "documents": [
    {
      "id": "1_ai-data-leakage-prevention-and-detection",
      "name": "AI Data Leakage Prevention and Detection (MI-1)",
      "filename": "mi-1_ai-data-leakage-prevention-and-detection.md",
      "description": "AI governance mitigation: AI Data Leakage Prevention and Detection (MI-1)",
      "last_modified": "2026-03-04T15:20:10+00:00",
      "title": "AI Data Leakage Prevention and Detection (MI-1)"
    },
    {
      "id": "12_role-based-access-control-for-ai-data",
      "name": "Role-based Access Control for AI Data (MI-12)",
      "filename": "mi-12_role-based-access-control-for-ai-data.md",
      "description": "AI governance mitigation: Role-based Access Control for AI Data (MI-12)",
      "last_modified": "2026-03-04T15:20:10+00:00",
      "title": "Role-based Access Control for AI Data (MI-12)"
    },
    {
      "id": "10_ai-model-version-pinning",
      "name": "AI Model Version Pinning (MI-10)",
      "filename": "mi-10_ai-model-version-pinning.md",
      "description": "AI governance mitigation: AI Model Version Pinning (MI-10)",
      "last_modified": "2026-03-04T15:20:10+00:00",
      "title": "AI Model Version Pinning (MI-10)"
    }
  ]
}
```

**Field Descriptions**:
- `total_count` (integer): Total number of mitigation documents available in current discovery run
- `source` (string): Data source (`github_api` or `unavailable`)
- `message` (string | null): Discovery status detail when degraded
- `documents` (array): List of mitigation document objects
  - `id` (string): Mitigation identifier for use with get_mitigation
  - `name` (string): Human-readable mitigation name
  - `filename` (string): Canonical markdown filename in source repository
  - `description` (string | null): Short document description
  - `last_modified` (string | null): Last modified timestamp (ISO-8601)
  - `title` (string | null): Display-friendly title

---

### 8. get_mitigation Response

Gets complete content of a specific mitigation document.

**Response Schema**:
```json
{
  "document_id": "1_ai-data-leakage-prevention-and-detection",
  "title": "AI Data Leakage Prevention and Detection (MI-1)",
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
  "message": null,
  "results": [
    {
      "framework_id": "mitigation-1_ai-data-leakage-prevention-and-detection",
      "section": "AI Data Leakage Prevention and Detection (MI-1)",
      "content": "...implement strong encryption algorithms for data at rest..."
    },
    {
      "framework_id": "mitigation-14_encryption-of-ai-data-at-rest",
      "section": "Encryption of AI Data at Rest (MI-14)",
      "content": "...implement strong encryption controls for AI data at rest..."
    }
  ]
}
```

**Field Descriptions**:
- `query` (string): The search query executed
- `total_found` (integer): Total number of matching results
- `message` (string | null): Optional message when discovery is unavailable
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
  "healthy_services": 4,
  "total_services": 4,
  "observability": {
    "openemcp": {
      "phase": "context_state_management",
      "correlation_id": "66a5506f-6f58-4dd1-af9e-269745b30271",
      "validation_status": "approved",
      "compatibility_enabled": true,
      "compat_events_buffered": 12
    },
    "risk_context": {
      "phase_assessed": "context_state_management",
      "risk_tier": "low",
      "risk_score": 0.2,
      "signals": {
        "boundary_open_count": 0,
        "circuit_breaker_trips": 0,
        "cache_hit_rate": 0.98,
        "failed_requests": 0,
        "total_requests": 100
      }
    }
  }
}
```

**Field Descriptions**:
- `status` (string): Overall health status ("healthy", "degraded", "unhealthy")
- `version` (string): MCP server version
- `uptime_seconds` (number): Server uptime in seconds
- `healthy_services` (integer): Number of healthy service components
- `total_services` (integer): Total number of service components
- `observability` (object | null): Internal OpenEMCP compatibility projection
  - `openemcp.phase` (string): Compatibility phase for this tool call
  - `openemcp.correlation_id` (string): Correlation ID for tracing
  - `openemcp.validation_status` (string): Canonical status enum (`approved`, `rejected`, `modified`)
  - `openemcp.compatibility_enabled` (boolean): Compatibility layer status
  - `openemcp.compat_events_buffered` (integer): Current in-memory event buffer count
  - `risk_context` (object): Derived risk posture from runtime signals

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
  "healthy_services": 4,
  "total_services": 4
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
  "hit_rate": 0.9504,
  "sets": 1500,
  "deletes": 120,
  "expires": 35,
  "evictions": 4,
  "clears": 1,
  "current_size": 320,
  "max_size": 1000,
  "memory_usage_bytes": 2621440,
  "observability": {
    "openemcp": {
      "phase": "execution_resilience",
      "correlation_id": "8b9e888d-b563-49b8-94d2-6a75f6d6c614",
      "validation_status": "approved",
      "compatibility_enabled": true,
      "compat_events_buffered": 18
    },
    "risk_context": {
      "phase_assessed": "execution_resilience",
      "risk_tier": "low",
      "risk_score": 0.18,
      "signals": {
        "cache_hit_rate": 0.9504,
        "failed_requests": 518,
        "total_requests": 10450
      }
    }
  }
}
```

**Field Descriptions**:
- `total_requests` (integer): Total number of cache requests processed
- `cache_hits` (integer): Number of successful cache hits
- `cache_misses` (integer): Number of cache misses (data not in cache)
- `hit_rate` (number): Cache hit rate as decimal (0.0 to 1.0)
- `sets`, `deletes`, `expires`, `evictions`, `clears` (integer | null): Cache operation counters
- `current_size`, `max_size` (integer | null): Current and configured cache capacity
- `memory_usage_bytes` (integer | null): Estimated memory usage
- `observability` (object | null): Internal OpenEMCP compatibility projection

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
  "hit_rate": 0.95,
  "sets": 120,
  "deletes": 5,
  "expires": 2,
  "evictions": 0,
  "clears": 0,
  "current_size": 80,
  "max_size": 1000,
  "memory_usage_bytes": 524288
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
      "retry_after": 30
    }
  }
}
```

**Recovery Actions**:
- Wait and retry after specified seconds
- Treat list/search responses with `source: "unavailable"` as retryable failures
- Check get_service_health for status

---

## Response Patterns

### Pagination

Search tools support limit parameter for result pagination:

```python
# Get first 5 results
search_frameworks("query", limit=5)

# Get next results by issuing another query with the same limit
search_frameworks("query", limit=5)
```

**Current Limitations**:
- Offset parameter is not supported
- Maximum limit: 20 results per query
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

The server uses in-memory caching for content/discovery paths.
Cache policy is configuration-driven and may vary by deployment.

**Cache Control**:
- Client cannot control cache directly
- Use get_cache_stats to monitor cache performance
- Cache automatically invalidated on server restart

---

## Response Size Limits

Runtime guardrails enforce payload limits:

- tool result payload validation: 5MB default
- resource/document payload validation: 1MB default
- request parameter payload validation: 100KB default

---

## Response Performance

Response latency depends on cache state, host capacity, and upstream API/network
conditions. Avoid assuming fixed latency budgets in clients.

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
