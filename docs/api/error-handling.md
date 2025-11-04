# Error Handling

Comprehensive guide to error codes, handling patterns, and troubleshooting for the FINOS MCP Server.

## Error Response Format

All errors follow a consistent JSON structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description",
    "details": {
      "field": "specific_field",
      "value": "invalid_value",
      "additional_context": "context_information"
    },
    "timestamp": "2024-01-15T16:30:00Z",
    "request_id": "correlation_id_for_tracking"
  }
}
```

## Error Categories

### 1. Validation Errors (4xx Series)

#### VALIDATION_ERROR
**Code**: `VALIDATION_ERROR`
**HTTP Status**: 400
**Description**: Input parameters fail schema validation

**Common Causes**:
- Missing required parameters
- Invalid parameter types
- Values outside allowed ranges
- Malformed input data

**Example**:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid framework_id parameter",
    "details": {
      "field": "framework_id",
      "value": "invalid_framework",
      "allowed_values": ["nist_ai_rmf", "eu_ai_act", "owasp_llm", "gdpr", "ccpa", "iso_27001", "soc_2"],
      "validation_rule": "Must be one of the supported framework identifiers"
    }
  }
}
```

**Resolution**:
- Check parameter names and types
- Verify values against documentation
- Use `list_frameworks` to see valid framework IDs

#### MALFORMED_QUERY
**Code**: `MALFORMED_QUERY`
**HTTP Status**: 400
**Description**: Search query contains invalid syntax

**Example**:
```json
{
  "error": {
    "code": "MALFORMED_QUERY",
    "message": "Search query contains invalid characters",
    "details": {
      "query": "risk && <script>",
      "invalid_patterns": ["<script>", "&&"],
      "suggestion": "Use standard search terms without special characters"
    }
  }
}
```

#### PARAMETER_RANGE_ERROR
**Code**: `PARAMETER_RANGE_ERROR`
**HTTP Status**: 400
**Description**: Parameter value outside acceptable range

**Example**:
```json
{
  "error": {
    "code": "PARAMETER_RANGE_ERROR",
    "message": "Limit parameter exceeds maximum allowed value",
    "details": {
      "parameter": "limit",
      "value": 500,
      "min_value": 1,
      "max_value": 100,
      "default_value": 20
    }
  }
}
```

### 2. Authentication & Authorization Errors (4xx Series)

#### RATE_LIMITED
**Code**: `RATE_LIMITED`
**HTTP Status**: 429
**Description**: Request rate limit exceeded

**Example**:
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Tool call rate limit exceeded",
    "details": {
      "limit_type": "tool_calls",
      "limit": 50,
      "window_seconds": 60,
      "current_count": 51,
      "retry_after": 45,
      "reset_time": "2024-01-15T16:31:00Z"
    }
  }
}
```

**Resolution**:
- Wait for the retry_after period
- Implement exponential backoff
- Consider caching responses to reduce calls

#### UNAUTHORIZED_ACCESS
**Code**: `UNAUTHORIZED_ACCESS`
**HTTP Status**: 403
**Description**: Access to resource denied

**Example**:
```json
{
  "error": {
    "code": "UNAUTHORIZED_ACCESS",
    "message": "Access to administrative operations requires elevated permissions",
    "details": {
      "required_permission": "admin",
      "current_permission": "read_only",
      "operation": "administrative_operation"
    }
  }
}
```

### 3. Resource Errors (4xx Series)

#### NOT_FOUND
**Code**: `NOT_FOUND`
**HTTP Status**: 404
**Description**: Requested resource does not exist

**Example**:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Framework not found",
    "details": {
      "resource_type": "framework",
      "resource_id": "nonexistent_framework",
      "available_frameworks": ["nist_ai_rmf", "eu_ai_act", "owasp_llm"],
      "suggestion": "Use list_frameworks to see available options"
    }
  }
}
```

#### RESOURCE_UNAVAILABLE
**Code**: `RESOURCE_UNAVAILABLE`
**HTTP Status**: 503
**Description**: Resource temporarily unavailable

**Example**:
```json
{
  "error": {
    "code": "RESOURCE_UNAVAILABLE",
    "message": "GDPR framework data temporarily unavailable",
    "details": {
      "framework": "gdpr",
      "reason": "external_api_timeout",
      "retry_after": 30,
      "estimated_recovery": "2024-01-15T16:35:00Z",
      "fallback_available": true
    }
  }
}
```

### 4. Server Errors (5xx Series)

#### INTERNAL_ERROR
**Code**: `INTERNAL_ERROR`
**HTTP Status**: 500
**Description**: Unexpected server-side error

**Example**:
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred while processing the request",
    "details": {
      "error_type": "framework_loader_exception",
      "correlation_id": "req_123456789",
      "support_info": "Include this correlation ID when contacting support"
    }
  }
}
```

#### SERVICE_UNAVAILABLE
**Code**: `SERVICE_UNAVAILABLE`
**HTTP Status**: 503
**Description**: Service temporarily unavailable

**Example**:
```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Framework service is temporarily unavailable",
    "details": {
      "service": "framework_query_engine",
      "status": "degraded",
      "retry_after": 60,
      "maintenance_window": false,
      "alternative_tools": ["search_mitigations", "search_risks"]
    }
  }
}
```

#### TIMEOUT_ERROR
**Code**: `TIMEOUT_ERROR`
**HTTP Status**: 504
**Description**: Operation timed out

**Example**:
```json
{
  "error": {
    "code": "TIMEOUT_ERROR",
    "message": "Framework search operation timed out",
    "details": {
      "operation": "cross_framework_search",
      "timeout_seconds": 30,
      "elapsed_seconds": 31,
      "suggestion": "Try narrowing your search query or using fewer frameworks"
    }
  }
}
```

## Framework-Specific Errors

### Framework Loading Errors

#### FRAMEWORK_LOAD_FAILED
**Code**: `FRAMEWORK_LOAD_FAILED`
**HTTP Status**: 503

**Example**:
```json
{
  "error": {
    "code": "FRAMEWORK_LOAD_FAILED",
    "message": "Failed to load EU AI Act framework data",
    "details": {
      "framework": "eu_ai_act",
      "load_stage": "content_parsing",
      "error_reason": "invalid_json_structure",
      "last_successful_load": "2024-01-14T10:00:00Z",
      "cached_data_available": true
    }
  }
}
```

#### FRAMEWORK_VERSION_MISMATCH
**Code**: `FRAMEWORK_VERSION_MISMATCH`
**HTTP Status**: 409

**Example**:
```json
{
  "error": {
    "code": "FRAMEWORK_VERSION_MISMATCH",
    "message": "Framework version conflict detected",
    "details": {
      "framework": "nist_ai_rmf",
      "expected_version": "1.0",
      "loaded_version": "1.1",
      "action_required": "framework_reload"
    }
  }
}
```

### Search Engine Errors

#### SEARCH_INDEX_UNAVAILABLE
**Code**: `SEARCH_INDEX_UNAVAILABLE`
**HTTP Status**: 503

**Example**:
```json
{
  "error": {
    "code": "SEARCH_INDEX_UNAVAILABLE",
    "message": "Search index is being rebuilt",
    "details": {
      "index_type": "framework_content",
      "rebuild_progress": 0.65,
      "estimated_completion": "2024-01-15T16:45:00Z",
      "alternative": "Use framework-specific search tools"
    }
  }
}
```

### Export Errors

#### EXPORT_SIZE_EXCEEDED
**Code**: `EXPORT_SIZE_EXCEEDED`
**HTTP Status**: 413

**Example**:
```json
{
  "error": {
    "code": "EXPORT_SIZE_EXCEEDED",
    "message": "Export data size exceeds maximum limit",
    "details": {
      "requested_size_mb": 75,
      "max_size_mb": 50,
      "suggestion": "Use filters to reduce export size",
      "available_filters": ["severity", "category", "compliance_status"]
    }
  }
}
```

## Error Handling Patterns

### 1. Graceful Degradation

When primary services fail, the system attempts graceful degradation:

```json
{
  "warning": {
    "code": "DEGRADED_SERVICE",
    "message": "Using cached data due to service unavailability",
    "details": {
      "primary_service": "unavailable",
      "fallback_mode": "cached_data",
      "data_age_hours": 6,
      "cache_freshness": "acceptable"
    }
  },
  "results": [
    // Cached results with warning
  ]
}
```

### 2. Partial Failure Handling

For multi-framework operations, partial failures are reported:

```json
{
  "partial_success": true,
  "successful_frameworks": ["nist_ai_rmf", "owasp_llm"],
  "failed_frameworks": [
    {
      "framework": "eu_ai_act",
      "error": "FRAMEWORK_UNAVAILABLE",
      "message": "EU AI Act data temporarily unavailable"
    }
  ],
  "results": [
    // Results from successful frameworks
  ]
}
```

### 3. Circuit Breaker Pattern

When external services are unreliable:

```json
{
  "error": {
    "code": "CIRCUIT_BREAKER_OPEN",
    "message": "External service circuit breaker is open",
    "details": {
      "service": "official_framework_api",
      "failure_count": 5,
      "circuit_open_until": "2024-01-15T17:00:00Z",
      "fallback_strategy": "use_local_cache"
    }
  }
}
```

## Client Error Handling Recommendations

### 1. Retry Logic

Implement exponential backoff for retryable errors:

```python
def should_retry(error_code):
    retryable_codes = [
        "RATE_LIMITED",
        "SERVICE_UNAVAILABLE",
        "TIMEOUT_ERROR",
        "FRAMEWORK_UNAVAILABLE"
    ]
    return error_code in retryable_codes

def get_retry_delay(error_details, attempt):
    if error_details.get("retry_after"):
        return error_details["retry_after"]
    return min(300, 2 ** attempt)  # Exponential backoff, max 5 minutes
```

### 2. Error Recovery Strategies

**For RATE_LIMITED**:
- Respect `retry_after` values
- Implement client-side rate limiting
- Cache responses to reduce API calls

**For NOT_FOUND**:
- Validate input against latest documentation
- Use list operations to discover valid values
- Implement input validation on client side

**For SERVICE_UNAVAILABLE**:
- Implement graceful degradation
- Use alternative tools when available
- Show appropriate user messages

**For VALIDATION_ERROR**:
- Validate inputs before API calls
- Provide user-friendly error messages
- Suggest valid alternatives

### 3. Monitoring and Alerting

Track error patterns:
- Error rate by tool type
- Most common validation errors
- Service availability metrics
- Response time degradation

## Error Code Reference

| Code | HTTP Status | Category | Retryable | Description |
|------|-------------|----------|-----------|-------------|
| VALIDATION_ERROR | 400 | Client | No | Invalid input parameters |
| MALFORMED_QUERY | 400 | Client | No | Invalid search query syntax |
| PARAMETER_RANGE_ERROR | 400 | Client | No | Parameter outside valid range |
| UNAUTHORIZED_ACCESS | 403 | Client | No | Insufficient permissions |
| NOT_FOUND | 404 | Client | No | Resource not found |
| RATE_LIMITED | 429 | Client | Yes | Rate limit exceeded |
| INTERNAL_ERROR | 500 | Server | Yes | Unexpected server error |
| SERVICE_UNAVAILABLE | 503 | Server | Yes | Service temporarily down |
| TIMEOUT_ERROR | 504 | Server | Yes | Operation timed out |
| FRAMEWORK_LOAD_FAILED | 503 | Framework | Yes | Framework loading failed |
| FRAMEWORK_VERSION_MISMATCH | 409 | Framework | No | Version conflict |
| SEARCH_INDEX_UNAVAILABLE | 503 | Search | Yes | Search index rebuilding |
| EXPORT_SIZE_EXCEEDED | 413 | Export | No | Export too large |
| CIRCUIT_BREAKER_OPEN | 503 | Circuit | Yes | External service protection |

## Debugging Tips

### 1. Use Correlation IDs
Every request includes a correlation ID for tracking:
```bash
# Include correlation ID in support requests
X-Request-ID: req_123456789abcdef
```

### 2. Check Service Health
Use health endpoints to diagnose issues:
```bash
# Check overall system health
tool: get_service_health

# Check cache status
tool: get_cache_stats
```

### 3. Enable Debug Logging
Server-side logging provides detailed error context:
- Request parameters
- Framework loading status
- Cache hit/miss information
- External API call status

### 4. Validate Framework Availability
Check framework status before complex operations:
```bash
# Verify framework is available
tool: list_frameworks
```

This comprehensive error handling approach ensures robust operation and clear diagnostics for troubleshooting issues.
