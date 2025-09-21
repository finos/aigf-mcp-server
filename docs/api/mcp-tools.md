# MCP Tools Reference

Complete reference documentation for all MCP tools provided by the FINOS AI Governance Framework server.

## Framework Navigation Tools

### search_frameworks

Search across all governance frameworks for specific requirements, controls, or topics.

**Name**: `search_frameworks`

**Description**: Cross-framework search with advanced filtering capabilities including framework type, severity, compliance status, and more.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search terms for finding relevant framework content"
    },
    "frameworks": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["nist_ai_rmf", "eu_ai_act", "owasp_llm", "gdpr", "ccpa", "iso_27001", "soc_2"]
      },
      "description": "Specific frameworks to search (optional, searches all if not specified)"
    },
    "severity": {
      "type": "string",
      "enum": ["low", "medium", "high", "critical"],
      "description": "Filter by severity level"
    },
    "compliance_status": {
      "type": "string",
      "enum": ["compliant", "non_compliant", "partially_compliant", "not_assessed"],
      "description": "Filter by compliance status"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100,
      "default": 20,
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
  "total_results": "integer",
  "frameworks_searched": ["array of strings"],
  "results": [
    {
      "framework": "string",
      "reference_id": "string",
      "title": "string",
      "content": "string",
      "relevance_score": "number",
      "severity": "string",
      "compliance_status": "string"
    }
  ]
}
```

**Example**:
```
Query: "risk management"
Response: 15 results across NIST AI RMF, EU AI Act covering risk assessment, mitigation strategies, and monitoring requirements.
```

---

### list_frameworks

List all available governance frameworks with metadata and statistics.

**Name**: `list_frameworks`

**Description**: Get comprehensive overview of supported frameworks including reference counts, last update times, and framework status.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "include_stats": {
      "type": "boolean",
      "default": true,
      "description": "Include detailed statistics for each framework"
    },
    "status_filter": {
      "type": "string",
      "enum": ["active", "modeled", "all"],
      "default": "all",
      "description": "Filter frameworks by their operational status"
    }
  }
}
```

**Response Format**:
```json
{
  "total_frameworks": "integer",
  "active_frameworks": "integer",
  "frameworks": [
    {
      "id": "string",
      "name": "string",
      "description": "string",
      "type": "string",
      "status": "active|modeled",
      "version": "string",
      "last_updated": "ISO date string",
      "reference_count": "integer",
      "compliance_coverage": "number (percentage)"
    }
  ]
}
```

---

### get_framework_details

Get detailed information about a specific governance framework.

**Name**: `get_framework_details`

**Description**: Retrieve comprehensive framework information including structure, references, and compliance data.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "framework_id": {
      "type": "string",
      "enum": ["nist_ai_rmf", "eu_ai_act", "owasp_llm", "gdpr", "ccpa", "iso_27001", "soc_2"],
      "description": "Framework identifier"
    },
    "include_references": {
      "type": "boolean",
      "default": false,
      "description": "Include full list of framework references"
    }
  },
  "required": ["framework_id"]
}
```

**Response Format**:
```json
{
  "framework": {
    "id": "string",
    "name": "string",
    "description": "string",
    "version": "string",
    "status": "string",
    "categories": ["array of strings"],
    "total_references": "integer",
    "compliance_metrics": {
      "total_controls": "integer",
      "assessed_controls": "integer",
      "compliance_rate": "number"
    }
  },
  "references": [
    {
      "id": "string",
      "title": "string",
      "category": "string",
      "severity": "string",
      "content_preview": "string"
    }
  ]
}
```

---

### get_compliance_analysis

Get comprehensive compliance analysis across frameworks.

**Name**: `get_compliance_analysis`

**Description**: Analyze compliance coverage statistics and identify compliance gaps across multiple frameworks.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "frameworks": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Frameworks to analyze (optional, analyzes all if not specified)"
    },
    "include_gaps": {
      "type": "boolean",
      "default": true,
      "description": "Include detailed gap analysis"
    }
  }
}
```

**Response Format**:
```json
{
  "analysis_summary": {
    "frameworks_analyzed": "integer",
    "total_requirements": "integer",
    "overall_compliance_rate": "number"
  },
  "framework_compliance": [
    {
      "framework": "string",
      "compliance_rate": "number",
      "compliant_controls": "integer",
      "total_controls": "integer",
      "gaps": ["array of gap descriptions"]
    }
  ],
  "cross_framework_gaps": ["array of compliance gaps"],
  "recommendations": ["array of recommendations"]
}
```

---

### search_framework_references

Search for specific references within a particular governance framework.

**Name**: `search_framework_references`

**Description**: Deep search within a single framework for detailed requirements or controls.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "framework_id": {
      "type": "string",
      "enum": ["nist_ai_rmf", "eu_ai_act", "owasp_llm", "gdpr", "ccpa", "iso_27001", "soc_2"],
      "description": "Framework to search within"
    },
    "query": {
      "type": "string",
      "description": "Search terms for finding specific references"
    },
    "category": {
      "type": "string",
      "description": "Filter by reference category (optional)"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 50,
      "default": 10
    }
  },
  "required": ["framework_id", "query"]
}
```

**Response Format**:
```json
{
  "framework": "string",
  "query": "string",
  "total_results": "integer",
  "results": [
    {
      "reference_id": "string",
      "title": "string",
      "category": "string",
      "content": "string",
      "relevance_score": "number",
      "related_controls": ["array of control IDs"]
    }
  ]
}
```

---

## Cross-Framework Navigation Tools

### get_related_controls

Find related controls across different governance frameworks.

**Name**: `get_related_controls`

**Description**: Cross-framework compliance mapping to find equivalent controls across different frameworks.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "control_id": {
      "type": "string",
      "description": "Control or reference ID to find relationships for"
    },
    "source_framework": {
      "type": "string",
      "description": "Framework containing the source control"
    },
    "target_frameworks": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Frameworks to search for related controls (optional)"
    }
  },
  "required": ["control_id"]
}
```

**Response Format**:
```json
{
  "source_control": {
    "id": "string",
    "framework": "string",
    "title": "string",
    "description": "string"
  },
  "related_controls": [
    {
      "control_id": "string",
      "framework": "string",
      "title": "string",
      "relationship_strength": "strong|moderate|weak",
      "relationship_type": "equivalent|related|complementary"
    }
  ],
  "mapping_confidence": "number"
}
```

---

### get_framework_correlations

Analyze correlations between governance frameworks.

**Name**: `get_framework_correlations`

**Description**: Identify thematic overlaps and relationship strength between different frameworks.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "framework_a": {
      "type": "string",
      "description": "First framework for correlation analysis"
    },
    "framework_b": {
      "type": "string",
      "description": "Second framework for correlation analysis"
    },
    "include_mappings": {
      "type": "boolean",
      "default": false,
      "description": "Include detailed control mappings"
    }
  },
  "required": ["framework_a", "framework_b"]
}
```

**Response Format**:
```json
{
  "correlation_analysis": {
    "framework_a": "string",
    "framework_b": "string",
    "correlation_score": "number",
    "thematic_overlaps": ["array of overlap areas"],
    "mapping_coverage": "number"
  },
  "detailed_mappings": [
    {
      "control_a": "string",
      "control_b": "string",
      "mapping_strength": "string",
      "confidence": "number"
    }
  ]
}
```

---

### find_compliance_gaps

Identify potential compliance gaps when mapping between frameworks.

**Name**: `find_compliance_gaps`

**Description**: Gap analysis for multi-framework compliance planning and risk assessment.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "source_framework": {
      "type": "string",
      "description": "Primary framework for compliance"
    },
    "target_frameworks": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Additional frameworks to check for gaps"
    },
    "severity_threshold": {
      "type": "string",
      "enum": ["low", "medium", "high", "critical"],
      "default": "medium",
      "description": "Minimum severity level for gap reporting"
    }
  },
  "required": ["source_framework", "target_frameworks"]
}
```

**Response Format**:
```json
{
  "gap_analysis": {
    "source_framework": "string",
    "target_frameworks": ["array of strings"],
    "total_gaps": "integer",
    "critical_gaps": "integer"
  },
  "gaps": [
    {
      "gap_type": "missing_control|insufficient_coverage|conflicting_requirement",
      "severity": "string",
      "description": "string",
      "affected_frameworks": ["array of strings"],
      "recommendations": ["array of recommendations"]
    }
  ]
}
```

---

## Advanced Framework Tools

### advanced_search_frameworks

Perform advanced search with enhanced filtering capabilities.

**Name**: `advanced_search_frameworks`

**Description**: Enhanced search with category filtering, term inclusion/exclusion, and date ranges.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Primary search terms"
    },
    "include_terms": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Terms that must be included"
    },
    "exclude_terms": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Terms to exclude from results"
    },
    "categories": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Filter by specific categories"
    },
    "date_range": {
      "type": "object",
      "properties": {
        "start": {"type": "string", "format": "date"},
        "end": {"type": "string", "format": "date"}
      }
    }
  },
  "required": ["query"]
}
```

---

### export_framework_data

Export framework data in multiple formats with filtering options.

**Name**: `export_framework_data`

**Description**: Generate reports and documentation in JSON, CSV, or Markdown format with comprehensive filtering.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "framework_id": {
      "type": "string",
      "description": "Framework to export"
    },
    "format": {
      "type": "string",
      "enum": ["json", "csv", "markdown"],
      "default": "json",
      "description": "Export format"
    },
    "filters": {
      "type": "object",
      "properties": {
        "categories": {"type": "array", "items": {"type": "string"}},
        "severity": {"type": "array", "items": {"type": "string"}},
        "compliance_status": {"type": "array", "items": {"type": "string"}}
      }
    },
    "include_metadata": {
      "type": "boolean",
      "default": true
    }
  },
  "required": ["framework_id"]
}
```

---

### bulk_export_frameworks

Perform bulk export of multiple framework datasets.

**Name**: `bulk_export_frameworks`

**Description**: Generate comprehensive compliance documentation packages with multiple configurations.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "exports": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "framework_id": {"type": "string"},
          "format": {"type": "string", "enum": ["json", "csv", "markdown"]},
          "filters": {"type": "object"}
        },
        "required": ["framework_id", "format"]
      }
    }
  },
  "required": ["exports"]
}
```

---

## FINOS Tools

### search_mitigations

Search through AI governance mitigations by keyword or topic.

**Name**: `search_mitigations`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search terms for finding mitigations"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 50,
      "default": 10
    }
  },
  "required": ["query"]
}
```

---

### search_risks

Search through AI governance risks by keyword or topic.

**Name**: `search_risks`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search terms for finding risks"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 50,
      "default": 10
    }
  },
  "required": ["query"]
}
```

---

### get_mitigation_details

Get detailed information about a specific mitigation.

**Name**: `get_mitigation_details`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "mitigation_id": {
      "type": "string",
      "description": "Mitigation identifier (e.g., 'mi-1', 'mi-2')"
    }
  },
  "required": ["mitigation_id"]
}
```

---

### get_risk_details

Get detailed information about a specific risk.

**Name**: `get_risk_details`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "risk_id": {
      "type": "string",
      "description": "Risk identifier (e.g., 'ri-1', 'ri-2')"
    }
  },
  "required": ["risk_id"]
}
```

---

### list_all_mitigations

List all available AI governance mitigations with metadata.

**Name**: `list_all_mitigations`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {}
}
```

---

### list_all_risks

List all available AI governance risks with metadata.

**Name**: `list_all_risks`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {}
}
```

---

## System Tools

### get_service_health

Get comprehensive service health status and diagnostics.

**Name**: `get_service_health`

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
  "status": "healthy|degraded|unhealthy",
  "uptime_seconds": "number",
  "services": {
    "content_service": {"status": "string", "last_check": "ISO date"},
    "framework_service": {"status": "string", "last_check": "ISO date"},
    "cache_service": {"status": "string", "last_check": "ISO date"}
  },
  "performance_metrics": {
    "avg_response_time_ms": "number",
    "requests_per_minute": "number",
    "error_rate": "number"
  }
}
```

---

### get_service_metrics

Get detailed service performance metrics and statistics.

**Name**: `get_service_metrics`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {}
}
```

---

### get_cache_stats

Get cache performance statistics and metrics.

**Name**: `get_cache_stats`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {}
}
```

---

### reset_service_health

Reset service health counters and error boundaries.

**Name**: `reset_service_health`

**Input Schema**:
```json
{
  "type": "object",
  "properties": {}
}
```

---

## Error Responses

All tools may return errors in the following format:

```json
{
  "error": "string",
  "error_code": "string",
  "details": "object (optional)"
}
```

Common error codes:
- `VALIDATION_ERROR` - Invalid input parameters
- `NOT_FOUND` - Requested resource not found
- `RATE_LIMITED` - Request rate limit exceeded
- `INTERNAL_ERROR` - Server-side error
- `FRAMEWORK_UNAVAILABLE` - Framework service unavailable

## Rate Limiting

- **Tool Calls**: 50 requests per minute per client
- **Resource Access**: 200 requests per minute per client
- **Content Size Limits**: 10MB per resource, 50MB per tool response

Rate limit headers are included in responses:
- `X-RateLimit-Remaining` - Requests remaining in current window
- `X-RateLimit-Reset` - Time when rate limit resets
