# 🔧 FINOS AI Governance MCP Server - API Reference

Complete API reference for developers working with the FINOS AI Governance MCP Server.

## 📋 Table of Contents

- [MCP Protocol Compliance](#mcp-protocol-compliance)
- [Server Capabilities](#server-capabilities)
- [Tools API](#tools-api)
- [Resources API](#resources-api)
- [Configuration API](#configuration-api)
- [Error Handling](#error-handling)
- [Type Definitions](#type-definitions)

## 🔌 MCP Protocol Compliance

### Protocol Version
- **Supported MCP Version**: 2024-11-05
- **JSON-RPC Version**: 2.0

### Server Information
```json
{
  "name": "finos-ai-governance",
  "version": "0.1.0-dev",
  "protocolVersion": "2024-11-05"
}
```

### Capabilities
```json
{
  "capabilities": {
    "tools": {},
    "resources": {
      "subscribe": false,
      "listChanged": false
    }
  }
}
```

## 🛠️ Tools API

### search_mitigations

Search through AI governance mitigations by keyword or topic.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query for mitigations (e.g., 'data privacy', 'model security')"
    }
  },
  "required": ["query"]
}
```

**Response Format:**
```json
{
  "results": [
    {
      "id": "mi-1",
      "title": "AI Data Leakage Prevention and Detection",
      "doc_status": "draft",
      "type": "technical",
      "content_preview": "Purpose: This mitigation addresses...",
      "uri": "finos://mitigations/mi-1_ai-data-leakage-prevention-and-detection.md"
    }
  ],
  "total_found": 3,
  "search_query": "data privacy"
}
```

### search_risks

Search through AI risk assessments by keyword or topic.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query for risks (e.g., 'prompt injection', 'bias')"
    }
  },
  "required": ["query"]
}
```

**Response Format:**
```json
{
  "results": [
    {
      "id": "ri-10",
      "title": "LLM05: Prompt Injection and Jailbreaking",
      "doc_status": "draft",
      "content_preview": "Summary: Prompt injection attacks...",
      "uri": "finos://risks/ri-10_llm05-prompt-injection-and-jailbreaking.md"
    }
  ],
  "total_found": 2,
  "search_query": "prompt injection"
}
```

### get_mitigation_details

Retrieve complete details of a specific mitigation by ID.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "mitigation_id": {
      "type": "string",
      "description": "Mitigation ID (e.g., 'mi-1', 'mi-7')",
      "pattern": "^mi-[0-9]+$"
    }
  },
  "required": ["mitigation_id"]
}
```

**Response Format:**
```json
{
  "id": "mi-1",
  "title": "AI Data Leakage Prevention and Detection",
  "metadata": {
    "sequence": 1,
    "title": "AI Data Leakage Prevention and Detection",
    "doc_status": "draft",
    "type": "technical",
    "iso_42001_2023_mapping": ["6.1", "6.2"],
    "nist_ai_rmf_1_0_mapping": ["GOVERN-1", "MAP-2"]
  },
  "content": "# AI Data Leakage Prevention and Detection\n\n## Purpose\n...",
  "uri": "finos://mitigations/mi-1_ai-data-leakage-prevention-and-detection.md"
}
```

### get_risk_details

Retrieve complete details of a specific risk assessment by ID.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "risk_id": {
      "type": "string",
      "description": "Risk ID (e.g., 'ri-10', 'ri-3')",
      "pattern": "^ri-[0-9]+$"
    }
  },
  "required": ["risk_id"]
}
```

**Response Format:**
```json
{
  "id": "ri-10",
  "title": "LLM05: Prompt Injection and Jailbreaking",
  "metadata": {
    "sequence": 10,
    "title": "LLM05: Prompt Injection and Jailbreaking",
    "doc_status": "draft",
    "owasp_llm_top_10_2023": ["LLM01"],
    "nist_ai_rmf_1_0": ["GOVERN-1.1"],
    "eu_ai_act": ["Article 9"]
  },
  "content": "# LLM05: Prompt Injection and Jailbreaking\n\n## Summary\n...",
  "uri": "finos://risks/ri-10_llm05-prompt-injection-and-jailbreaking.md"
}
```

### list_all_mitigations

List all available mitigations with metadata.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": []
}
```

**Response Format:**
```json
{
  "mitigations": [
    {
      "id": "mi-1",
      "title": "AI Data Leakage Prevention and Detection",
      "doc_status": "draft",
      "type": "technical",
      "uri": "finos://mitigations/mi-1_ai-data-leakage-prevention-and-detection.md"
    }
  ],
  "total_count": 17
}
```

### list_all_risks

List all available risk assessments with metadata.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": []
}
```

**Response Format:**
```json
{
  "risks": [
    {
      "id": "ri-10",
      "title": "LLM05: Prompt Injection and Jailbreaking",
      "doc_status": "draft",
      "uri": "finos://risks/ri-10_llm05-prompt-injection-and-jailbreaking.md"
    }
  ],
  "total_count": 23
}
```

## 📄 Resources API

### Resource URIs

**Mitigation Resources:**
- Pattern: `finos://mitigations/{filename}`
- Example: `finos://mitigations/mi-1_ai-data-leakage-prevention-and-detection.md`

**Risk Assessment Resources:**
- Pattern: `finos://risks/{filename}`
- Example: `finos://risks/ri-10_llm05-prompt-injection-and-jailbreaking.md`

### Resource Response Format

```json
{
  "uri": "finos://mitigations/mi-1_ai-data-leakage-prevention-and-detection.md",
  "mimeType": "text/markdown",
  "text": "# AI Data Leakage Prevention and Detection\n\n## Metadata\n..."
}
```

## ⚙️ Configuration API

### Environment Variables

All configuration through environment variables with `FINOS_MCP_` prefix:

```typescript
interface Configuration {
  // Logging
  LOG_LEVEL: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
  DEBUG_MODE: boolean

  // Network
  HTTP_TIMEOUT: number  // seconds
  BASE_URL: string      // GitHub raw content URL

  // Caching
  ENABLE_CACHE: boolean
  CACHE_MAX_SIZE: number
  CACHE_TTL_SECONDS: number

  // GitHub API
  GITHUB_TOKEN?: string
  GITHUB_API_DELAY_SECONDS: number
  GITHUB_API_MAX_RETRIES: number
  GITHUB_API_BACKOFF_FACTOR: number
  GITHUB_API_RATE_LIMIT_BUFFER: number

  // Server
  SERVER_NAME: string
  SERVER_VERSION: string
}
```

### Configuration Validation

The server performs comprehensive validation:
- **Type checking**: Ensures proper data types
- **Range validation**: Numeric values within acceptable ranges
- **URL validation**: Repository URLs are accessible
- **Token validation**: GitHub tokens have proper format

## ❌ Error Handling

### Error Response Format

```json
{
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": {
      "error_type": "ContentFetchError",
      "details": "Failed to fetch document from GitHub",
      "context": {
        "url": "https://raw.githubusercontent.com/...",
        "status_code": 404
      }
    }
  }
}
```

### Common Error Types

#### ConfigurationError
```json
{
  "error_type": "ConfigurationError",
  "message": "Invalid configuration",
  "details": "Log level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
}
```

#### ContentFetchError
```json
{
  "error_type": "ContentFetchError",
  "message": "Failed to fetch content",
  "details": "Network timeout after 30 seconds",
  "context": {
    "url": "https://raw.githubusercontent.com/...",
    "timeout": 30
  }
}
```

#### DocumentNotFoundError
```json
{
  "error_type": "DocumentNotFoundError",
  "message": "Document not found",
  "details": "Mitigation 'mi-99' not found",
  "context": {
    "document_id": "mi-99",
    "document_type": "mitigation"
  }
}
```

#### RateLimitError
```json
{
  "error_type": "RateLimitError",
  "message": "GitHub API rate limit exceeded",
  "details": "Rate limit will reset at 2024-01-15T14:30:00Z",
  "context": {
    "reset_time": "2024-01-15T14:30:00Z",
    "remaining": 0
  }
}
```

## 📝 Type Definitions

### Document Types

```typescript
interface DocumentMetadata {
  sequence: number
  title: string
  doc_status: "draft" | "approved" | "deprecated"
  type?: "technical" | "process" | "governance"

  // Framework mappings (varies by document)
  iso_42001_2023_mapping?: string[]
  nist_ai_rmf_1_0_mapping?: string[]
  owasp_llm_top_10_2023?: string[]
  eu_ai_act?: string[]
}

interface MitigationDocument {
  id: string
  title: string
  metadata: DocumentMetadata
  content: string
  uri: string
}

interface RiskDocument {
  id: string
  title: string
  metadata: DocumentMetadata
  content: string
  uri: string
}
```

### Search Results

```typescript
interface SearchResult {
  id: string
  title: string
  doc_status: string
  type?: string
  content_preview: string
  uri: string
}

interface SearchResponse {
  results: SearchResult[]
  total_found: number
  search_query: string
}
```

### Server Health

```typescript
interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy"
  message: string
  uptime_seconds: number
  uptime_human: string
  services: {
    [serviceName: string]: {
      status: "healthy" | "degraded" | "unhealthy"
      success_rate: number
      avg_response_time: number
      total_requests: number
    }
  }
}
```

## 🧪 Testing API

### Integration Testing

```python
import asyncio
import json
from finos_mcp.server import main

async def test_search_api():
    """Test search mitigation API."""
    # Setup MCP client connection
    # Send search request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_mitigations",
            "arguments": {"query": "data privacy"}
        }
    }

    # Validate response structure
    response = await send_mcp_request(request)
    assert "result" in response
    assert "results" in response["result"]
```

### Load Testing

```bash
# Test with multiple concurrent requests
python tests/load/concurrent_requests.py --requests=100 --concurrency=10
```

## 🔒 Security Considerations

### API Security
- All external requests use HTTPS
- GitHub tokens require minimal permissions (public_repo only)
- Input validation prevents injection attacks
- Rate limiting prevents abuse

### Data Security
- No user data is stored or logged
- All content is public domain (FINOS framework)
- Secure configuration management
- Regular dependency updates

---

> **Next Steps:** Check out the [Development Guide](development-guide.md) for setting up your development environment and contribution guidelines.
