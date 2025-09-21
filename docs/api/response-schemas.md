# Response Schemas

Detailed schemas and examples for all MCP tool responses in the FINOS AI Governance Framework server.

## Common Response Elements

### Base Response Structure

All successful tool responses follow the MCP protocol structure:

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

## Framework Tool Responses

### search_frameworks Response

```json
{
  "query": "risk management",
  "total_results": 15,
  "frameworks_searched": ["nist_ai_rmf", "eu_ai_act", "owasp_llm"],
  "search_metadata": {
    "execution_time_ms": 245,
    "cache_hit": true,
    "relevance_threshold": 0.5
  },
  "results": [
    {
      "framework": "nist_ai_rmf",
      "reference_id": "ai-rmf-1.1",
      "title": "Risk Management Framework",
      "content": "Establish and implement a comprehensive AI risk management framework...",
      "relevance_score": 0.92,
      "severity": "high",
      "compliance_status": "compliant",
      "category": "governance",
      "highlights": [
        "Risk management framework implementation",
        "AI system risk assessment procedures"
      ],
      "related_controls": ["ai-rmf-1.2", "ai-rmf-2.1"]
    }
  ]
}
```

### list_frameworks Response

```json
{
  "total_frameworks": 7,
  "active_frameworks": 4,
  "modeled_frameworks": 3,
  "last_updated": "2024-01-15T10:30:00Z",
  "frameworks": [
    {
      "id": "nist_ai_rmf",
      "name": "NIST AI Risk Management Framework",
      "description": "NIST's framework for managing AI risks",
      "type": "active",
      "status": "production",
      "version": "1.0",
      "last_updated": "2024-01-15T08:00:00Z",
      "reference_count": 30,
      "compliance_coverage": 85.5,
      "categories": ["governance", "risk_management", "trustworthy_ai"],
      "source": "official_api",
      "health_status": "healthy"
    },
    {
      "id": "eu_ai_act",
      "name": "EU Artificial Intelligence Act",
      "description": "European Union's comprehensive AI regulation",
      "type": "active",
      "status": "production",
      "version": "2024.1",
      "last_updated": "2024-01-14T15:30:00Z",
      "reference_count": 42,
      "compliance_coverage": 92.1,
      "categories": ["regulation", "compliance", "risk_assessment"],
      "source": "official_api",
      "health_status": "healthy"
    }
  ]
}
```

### get_framework_details Response

```json
{
  "framework": {
    "id": "nist_ai_rmf",
    "name": "NIST AI Risk Management Framework",
    "description": "Comprehensive framework for managing AI risks in organizational contexts",
    "version": "1.0",
    "status": "active",
    "type": "governance_framework",
    "publisher": "National Institute of Standards and Technology",
    "publication_date": "2023-01-26",
    "last_updated": "2024-01-15T08:00:00Z",
    "categories": ["governance", "risk_management", "trustworthy_ai"],
    "scope": "Applies to all AI systems and applications",
    "jurisdiction": "United States (Global applicability)",
    "total_references": 30,
    "compliance_metrics": {
      "total_controls": 30,
      "assessed_controls": 28,
      "compliant_controls": 24,
      "compliance_rate": 85.7,
      "last_assessment": "2024-01-10T12:00:00Z"
    },
    "statistics": {
      "high_severity_controls": 8,
      "medium_severity_controls": 15,
      "low_severity_controls": 7,
      "average_implementation_effort": "medium"
    }
  },
  "references": [
    {
      "id": "ai-rmf-1.1",
      "title": "Establish AI Risk Management Culture",
      "category": "governance",
      "severity": "high",
      "compliance_status": "compliant",
      "content_preview": "Organizations shall establish and maintain a culture of AI risk management...",
      "implementation_guidance": "Develop organizational policies and procedures...",
      "related_controls": ["ai-rmf-1.2", "ai-rmf-2.1"],
      "tags": ["culture", "governance", "risk_management"]
    }
  ]
}
```

### get_compliance_analysis Response

```json
{
  "analysis_summary": {
    "frameworks_analyzed": 4,
    "total_requirements": 125,
    "assessed_requirements": 115,
    "overall_compliance_rate": 78.5,
    "critical_gaps": 5,
    "analysis_date": "2024-01-15T14:30:00Z"
  },
  "framework_compliance": [
    {
      "framework": "nist_ai_rmf",
      "framework_name": "NIST AI Risk Management Framework",
      "compliance_rate": 85.7,
      "compliant_controls": 24,
      "non_compliant_controls": 4,
      "partially_compliant_controls": 2,
      "total_controls": 30,
      "status": "good",
      "gaps": [
        {
          "control_id": "ai-rmf-3.2",
          "title": "Continuous Monitoring",
          "gap_type": "implementation",
          "severity": "medium",
          "description": "Automated monitoring system not fully implemented"
        }
      ],
      "strengths": [
        "Strong governance framework",
        "Comprehensive risk assessment procedures"
      ]
    }
  ],
  "cross_framework_gaps": [
    {
      "gap_type": "coverage",
      "description": "GDPR data protection requirements not fully covered by NIST framework",
      "affected_frameworks": ["nist_ai_rmf", "gdpr"],
      "severity": "high",
      "recommendation": "Implement additional data protection controls"
    }
  ],
  "recommendations": [
    {
      "priority": "high",
      "category": "implementation",
      "description": "Implement automated compliance monitoring",
      "affected_frameworks": ["nist_ai_rmf", "eu_ai_act"],
      "estimated_effort": "medium"
    }
  ]
}
```

### get_related_controls Response

```json
{
  "source_control": {
    "id": "ai-rmf-1.1",
    "framework": "nist_ai_rmf",
    "title": "Establish AI Risk Management Culture",
    "description": "Organizations shall establish and maintain a culture of AI risk management",
    "category": "governance",
    "severity": "high"
  },
  "related_controls": [
    {
      "control_id": "art-5",
      "framework": "eu_ai_act",
      "framework_name": "EU AI Act",
      "title": "General-Purpose AI Systems",
      "relationship_strength": "strong",
      "relationship_type": "equivalent",
      "confidence_score": 0.87,
      "similarity_factors": [
        "Governance requirements",
        "Risk management culture",
        "Organizational responsibility"
      ]
    },
    {
      "control_id": "llm-gov-01",
      "framework": "owasp_llm",
      "framework_name": "OWASP LLM Top 10",
      "title": "LLM01: Prompt Injection",
      "relationship_strength": "moderate",
      "relationship_type": "related",
      "confidence_score": 0.65,
      "similarity_factors": [
        "Risk awareness",
        "Security governance"
      ]
    }
  ],
  "mapping_confidence": 0.78,
  "total_related_controls": 2,
  "mapping_metadata": {
    "algorithm_version": "1.2",
    "last_updated": "2024-01-15T10:00:00Z"
  }
}
```

### export_framework_data Response

```json
{
  "export_metadata": {
    "framework_id": "nist_ai_rmf",
    "format": "json",
    "export_date": "2024-01-15T15:45:00Z",
    "total_records": 30,
    "file_size_bytes": 245760,
    "filters_applied": {
      "categories": ["governance", "risk_management"],
      "severity": ["high", "medium"]
    }
  },
  "data": {
    "framework_info": {
      "id": "nist_ai_rmf",
      "name": "NIST AI Risk Management Framework",
      "version": "1.0",
      "export_timestamp": "2024-01-15T15:45:00Z"
    },
    "references": [
      {
        "id": "ai-rmf-1.1",
        "title": "Establish AI Risk Management Culture",
        "content": "Full content text...",
        "category": "governance",
        "severity": "high",
        "compliance_status": "compliant",
        "metadata": {
          "created_date": "2023-01-26",
          "last_reviewed": "2024-01-10",
          "tags": ["culture", "governance"]
        }
      }
    ]
  }
}
```

## FINOS Tool Responses

### search_mitigations Response

```json
{
  "query": "data privacy",
  "total_results": 5,
  "results": [
    {
      "mitigation_id": "mi-1",
      "title": "Data Leakage Prevention",
      "description": "Implement comprehensive data leakage prevention measures",
      "category": "data_protection",
      "relevance_score": 0.95,
      "tags": ["data_privacy", "leakage_prevention", "security"]
    }
  ],
  "search_metadata": {
    "execution_time_ms": 45,
    "source": "finos_content"
  }
}
```

### get_mitigation_details Response

```json
{
  "mitigation": {
    "id": "mi-1",
    "title": "Data Leakage Prevention",
    "description": "Comprehensive data leakage prevention strategy",
    "category": "data_protection",
    "severity": "high",
    "implementation_complexity": "medium",
    "content": {
      "overview": "Full mitigation content...",
      "implementation_steps": [
        "Step 1: Assess current data flows",
        "Step 2: Implement monitoring"
      ],
      "best_practices": ["Practice 1", "Practice 2"],
      "tools_required": ["DLP software", "Monitoring tools"]
    },
    "related_risks": ["ri-1", "ri-3"],
    "metadata": {
      "created_date": "2023-06-15",
      "last_updated": "2024-01-10",
      "source": "finos_ai_governance"
    }
  }
}
```

### list_all_mitigations Response

```json
{
  "total_mitigations": 25,
  "categories": [
    {"name": "data_protection", "count": 8},
    {"name": "model_security", "count": 7},
    {"name": "governance", "count": 10}
  ],
  "mitigations": [
    {
      "id": "mi-1",
      "title": "Data Leakage Prevention",
      "category": "data_protection",
      "severity": "high",
      "description_preview": "Implement comprehensive data leakage prevention measures..."
    }
  ]
}
```

## System Tool Responses

### get_service_health Response

```json
{
  "overall_status": "healthy",
  "uptime_seconds": 3456789,
  "uptime_human": "40 days, 1 hour, 33 minutes",
  "last_health_check": "2024-01-15T16:00:00Z",
  "services": {
    "content_service": {
      "status": "healthy",
      "last_check": "2024-01-15T16:00:00Z",
      "response_time_ms": 15,
      "error_count": 0
    },
    "framework_service": {
      "status": "healthy",
      "last_check": "2024-01-15T16:00:00Z",
      "response_time_ms": 25,
      "frameworks_loaded": 7
    },
    "cache_service": {
      "status": "healthy",
      "last_check": "2024-01-15T16:00:00Z",
      "hit_rate": 0.96,
      "memory_usage_mb": 245
    }
  },
  "performance_metrics": {
    "avg_response_time_ms": 120,
    "requests_per_minute": 45,
    "error_rate": 0.002,
    "memory_usage_mb": 445,
    "cpu_usage_percent": 12.5
  },
  "health_checks": [
    {
      "name": "database_connectivity",
      "status": "pass",
      "duration_ms": 5
    },
    {
      "name": "external_api_connectivity",
      "status": "pass",
      "duration_ms": 150
    }
  ]
}
```

### get_cache_stats Response

```json
{
  "cache_performance": {
    "total_requests": 10450,
    "cache_hits": 9932,
    "cache_misses": 518,
    "hit_rate": 0.9504,
    "avg_lookup_time_ms": 2.3
  },
  "memory_usage": {
    "total_allocated_mb": 245,
    "used_mb": 198,
    "available_mb": 47,
    "utilization_percent": 80.8
  },
  "cache_categories": {
    "framework_data": {
      "size_mb": 125,
      "items": 45,
      "hit_rate": 0.98
    },
    "query_results": {
      "size_mb": 73,
      "items": 234,
      "hit_rate": 0.92
    }
  },
  "eviction_stats": {
    "total_evictions": 15,
    "eviction_policy": "LRU",
    "last_eviction": "2024-01-15T14:30:00Z"
  }
}
```

## Error Response Examples

### Validation Error

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {
      "field": "framework_id",
      "value": "invalid_framework",
      "allowed_values": ["nist_ai_rmf", "eu_ai_act", "owasp_llm", "gdpr"]
    }
  }
}
```

### Rate Limit Error

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Request rate limit exceeded",
    "details": {
      "limit": 50,
      "window_seconds": 60,
      "retry_after": 45,
      "remaining_requests": 0
    }
  }
}
```

### Resource Not Found

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

### Service Unavailable

```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Framework service temporarily unavailable",
    "details": {
      "service": "framework_loader",
      "retry_after": 30,
      "estimated_recovery": "2024-01-15T16:30:00Z"
    }
  }
}
```

## Response Headers

### Standard Headers

All responses include these headers:
- `Content-Type: application/json`
- `X-Request-ID: <correlation_id>`
- `X-Response-Time: <milliseconds>`

### Rate Limiting Headers

- `X-RateLimit-Limit: 50`
- `X-RateLimit-Remaining: 45`
- `X-RateLimit-Reset: 1642262400`
- `X-RateLimit-Window: 60`

### Caching Headers

- `X-Cache-Status: hit|miss`
- `X-Cache-TTL: 3600`
- `X-Content-Source: cache|live`

## Response Size Limits

| Response Type | Maximum Size | Typical Size |
|---------------|--------------|--------------|
| Simple Query | 1MB | 50KB |
| Framework Details | 5MB | 500KB |
| Export Data | 50MB | 10MB |
| Health Status | 100KB | 10KB |
| Error Response | 10KB | 1KB |

Large responses are automatically paginated or streamed when possible.
