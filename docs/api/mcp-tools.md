# MCP Tools Reference

Complete reference documentation for all 11 MCP tools provided by the FINOS AI Governance Framework server.

## Overview

The server provides 11 tools organized in 3 categories:
- **Framework Access Tools** (5 tools): List, retrieve, and search governance frameworks
- **Risk & Mitigation Tools** (4 tools): Access and search AI governance risks and mitigations
- **System Monitoring Tools** (2 tools): Service health and cache performance monitoring

### Tool Annotations (MCP Hints)

All tools publish MCP `annotations` metadata to improve planner behavior and client UX:
- `title`
- `readOnlyHint`
- `destructiveHint`
- `idempotentHint`
- `openWorldHint`

Current policy:
- Content/discovery/search tools: `readOnlyHint=true`, `destructiveHint=false`, `idempotentHint=true`, `openWorldHint=true`
- Internal telemetry tools (`get_service_health`, `get_cache_stats`): same hints, but `openWorldHint=false`

These hints are advisory metadata for planning/safety UX and do not replace hard security controls.

### Resource And Prompt Metadata

In addition to tool annotations:
- Resource templates publish explicit `title`/`description` plus `annotations` (`audience`, `priority`) for better client ranking and context targeting.
- Prompts publish explicit `title`/`description` metadata. (Prompt objects do not include MCP `annotations` fields in the current protocol type model.)

---

## Framework Access Tools

### list_frameworks

List all available AI governance frameworks.

**Name**: `list_frameworks`

**Description**: Returns a structured list of all supported AI governance frameworks with metadata including framework ID, name, and description.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {}
}
```

**Response Format**:
```json
{
  "total_count": "integer",
  "frameworks": [
    {
      "id": "string",
      "name": "string",
      "description": "string"
    }
  ]
}
```

**Example**:
```
list_frameworks()
→ Returns the currently available framework catalog from FINOS
```

---

### get_framework

Get complete content of a specific framework.

**Name**: `get_framework`

**Description**: Retrieves the complete content of a governance framework document including all sections and metadata.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "framework": {
      "type": "string",
      "description": "Framework identifier (e.g., 'nist-ai-600-1', 'eu-ai-act')"
    }
  },
  "required": ["framework"]
}
```

**Response Format**:
```json
{
  "framework_id": "string",
  "sections": "array of strings",
  "content": "string (full framework content)"
}
```

**Example**:
```
get_framework("eu-ai-act")
→ Returns complete EU AI Act content with all sections
```

---

### search_frameworks

Search for text within framework documents.

**Name**: `search_frameworks`

**Description**: Searches across all framework documents for specific text or keywords and returns matching content snippets.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query text"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 20,
      "default": 5,
      "description": "Maximum number of results to return"
    }
  },
  "required": ["query"]
}
```

**Response Format**:
```json
{
  "query": "string",
  "total_found": "integer",
  "results": [
    {
      "framework_id": "string",
      "section": "string",
      "content": "string (matching content snippet)"
    }
  ]
}
```

**Example**:
```
search_frameworks("risk management", 5)
→ Returns 5 results matching "risk management" across frameworks
```

---

### list_risks

List all available risk documents.

**Name**: `list_risks`

**Description**: Returns a structured list of all AI governance risk documents available in the system.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {}
}
```

**Response Format**:
```json
{
  "total_count": "integer",
  "source": "string (e.g., 'github_api' or 'static_fallback')",
  "documents": [
    {
      "id": "string",
      "name": "string"
    }
  ]
}
```

**Example**:
```
list_risks()
→ Returns risk documents from FINOS AI Governance Framework
```

---

### get_risk

Get complete content of a specific risk document.

**Name**: `get_risk`

**Description**: Retrieves the complete content of a specific AI governance risk document including all sections and details.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "risk_id": {
      "type": "string",
      "description": "Risk identifier (e.g., '10_prompt-injection', '1_information-leaked-to-hosted-model')"
    }
  },
  "required": ["risk_id"]
}
```

**Response Format**:
```json
{
  "document_id": "string",
  "title": "string",
  "sections": "array of strings",
  "content": "string (full risk document content)"
}
```

**Example**:
```
get_risk("10_prompt-injection")
→ Returns complete prompt injection risk documentation
```

---

## Risk & Mitigation Tools

### search_risks

Search within risk documentation.

**Name**: `search_risks`

**Description**: Searches across all risk documents for specific text or keywords and returns matching content snippets.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query text"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 20,
      "default": 5,
      "description": "Maximum number of results to return"
    }
  },
  "required": ["query"]
}
```

**Response Format**:
```json
{
  "query": "string",
  "total_found": "integer",
  "results": [
    {
      "framework_id": "string (prefixed risk ID, e.g., 'risk-10_prompt-injection')",
      "section": "string (risk name)",
      "content": "string (matching content snippet)"
    }
  ]
}
```

**Example**:
```
search_risks("injection", 5)
→ Returns risks related to injection attacks
```

---

### list_mitigations

List all available mitigation documents.

**Name**: `list_mitigations`

**Description**: Returns a structured list of all AI governance mitigation strategy documents available in the system.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {}
}
```

**Response Format**:
```json
{
  "total_count": "integer",
  "source": "string (e.g., 'github_api' or 'static_fallback')",
  "documents": [
    {
      "id": "string",
      "name": "string"
    }
  ]
}
```

**Example**:
```
list_mitigations()
→ Returns mitigation documents from FINOS AI Governance Framework
```

---

### get_mitigation

Get complete content of a specific mitigation document.

**Name**: `get_mitigation`

**Description**: Retrieves the complete content of a specific AI governance mitigation strategy document including all sections and details.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "mitigation_id": {
      "type": "string",
      "description": "Mitigation identifier (e.g., '1_ai-data-leakage-prevention-and-detection', '10_ai-model-version-pinning')"
    }
  },
  "required": ["mitigation_id"]
}
```

**Response Format**:
```json
{
  "document_id": "string",
  "title": "string",
  "sections": "array of strings",
  "content": "string (full mitigation document content)"
}
```

**Example**:
```
get_mitigation("1_ai-data-leakage-prevention-and-detection")
→ Returns complete mitigation documentation
```

---

### search_mitigations

Search within mitigation documentation.

**Name**: `search_mitigations`

**Description**: Searches across all mitigation documents for specific text or keywords and returns matching content snippets.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query text"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 20,
      "default": 5,
      "description": "Maximum number of results to return"
    }
  },
  "required": ["query"]
}
```

**Response Format**:
```json
{
  "query": "string",
  "total_found": "integer",
  "results": [
    {
      "framework_id": "string (prefixed mitigation ID, e.g., 'mitigation-1_ai-data-leakage-prevention-and-detection')",
      "section": "string (mitigation name)",
      "content": "string (matching content snippet)"
    }
  ]
}
```

**Example**:
```
search_mitigations("encryption", 5)
→ Returns mitigations related to encryption
```

---

## System Monitoring Tools

### get_service_health

Get service health status and metrics.

**Name**: `get_service_health`

**Description**: Returns comprehensive health status of the MCP server including uptime, service status, and component health.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {}
}
```

**Response Format**:
```json
{
  "status": "string (healthy/degraded/unhealthy)",
  "version": "string",
  "uptime_seconds": "number",
  "healthy_services": "integer",
  "total_services": "integer"
}
```

**Example**:
```
get_service_health()
→ Returns: status=healthy, uptime=3600s, services=5/5
```

---

### get_cache_stats

Get cache performance statistics.

**Name**: `get_cache_stats`

**Description**: Returns cache performance metrics including hit rate, memory usage, and request statistics.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {}
}
```

**Response Format**:
```json
{
  "total_requests": "integer",
  "cache_hits": "integer",
  "cache_misses": "integer",
  "hit_rate": "number (0.0 to 1.0)"
}
```

**Example**:
```
get_cache_stats()
→ Returns: 1000 requests, 950 hits, 50 misses, 95% hit rate
```

---

## Error Handling

All tools return structured error responses when errors occur:

```json
{
  "error": "string (error type)",
  "message": "string (human-readable error message)",
  "details": "object (optional additional context)"
}
```

Common error types:
- `ValidationError`: Invalid input parameters
- `NotFoundError`: Requested resource not found
- `ServiceError`: Internal service error
- `RateLimitError`: Rate limit exceeded

## Rate Limiting

- **Tool calls**: 50 requests/minute per client
- **Content retrieval**: Unlimited (cached content)
- **Search operations**: 50 requests/minute per client

## Performance Characteristics

- **Cached content**: <0.1ms response time
- **GitHub API calls**: 500-2000ms (when cache miss)
- **Search operations**: 10-100ms depending on corpus size
- **List operations**: <10ms (metadata only)
