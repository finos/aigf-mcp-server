# Integration Guide

Comprehensive guide for developers integrating with the FINOS AI Governance Framework MCP Server.

## Overview

The FINOS MCP Server provides a robust, well-documented API for accessing governance framework data through the Model Context Protocol (MCP). This guide covers integration patterns, best practices, and code examples for various use cases.

## Quick Start Integration

### 1. Basic Setup

**Prerequisites**:
- Python 3.10+
- MCP-compatible client (Claude, VS Code, Cursor)
- Network access for framework data loading

**Installation**:
```bash
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
pip install -e .
```

**Configuration**:
```bash
# Test the installation
finos-mcp --help

# Verify server functionality
finos-mcp --test-connection
```

### 2. First API Call

Start with a simple framework listing:

```python
# Example: List available frameworks
{
  "tool": "list_frameworks",
  "arguments": {
    "include_stats": true
  }
}
```

**Expected Response**:
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
    }
  ]
}
```

## Integration Patterns

### 1. Compliance Monitoring System

**Use Case**: Automated compliance monitoring and reporting

**Architecture**:
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Your System   │───▶│   FINOS MCP      │───▶│   Framework     │
│                 │    │   Server         │    │   Data Sources  │
│ - Compliance    │    │                  │    │                 │
│   Dashboard     │    │ - Query Engine   │    │ - NIST API      │
│ - Risk Reports  │    │ - Data Mapping   │    │ - EU AI Act     │
│ - Audit Trails  │    │ - Export Tools   │    │ - OWASP LLM     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

**Implementation Example**:
```python
class ComplianceMonitor:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def assess_compliance(self, frameworks=None):
        """Get comprehensive compliance assessment"""
        response = await self.mcp_client.call_tool(
            "get_compliance_analysis",
            {
                "frameworks": frameworks or ["nist_ai_rmf", "eu_ai_act"],
                "include_gaps": True
            }
        )
        return self._process_compliance_data(response)

    async def generate_compliance_report(self, format="json"):
        """Generate detailed compliance report"""
        return await self.mcp_client.call_tool(
            "export_framework_data",
            {
                "framework_id": "nist_ai_rmf",
                "format": format,
                "include_metadata": True
            }
        )
```

### 2. Research and Analysis Platform

**Use Case**: Governance framework research and cross-framework analysis

**Key Tools**:
- `search_frameworks` - Multi-framework content search
- `get_framework_correlations` - Framework relationship analysis
- `find_compliance_gaps` - Gap analysis
- `get_related_controls` - Control mapping

**Implementation Example**:
```python
class FrameworkResearcher:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def research_topic(self, topic, frameworks=None):
        """Research a topic across frameworks"""
        results = await self.mcp_client.call_tool(
            "search_frameworks",
            {
                "query": topic,
                "frameworks": frameworks,
                "limit": 50
            }
        )

        # Analyze correlations between results
        correlations = await self._analyze_correlations(results)

        return {
            "search_results": results,
            "correlations": correlations,
            "summary": self._generate_summary(results)
        }

    async def map_frameworks(self, source_framework, target_frameworks):
        """Map controls between frameworks"""
        mapping_results = []

        for target in target_frameworks:
            correlation = await self.mcp_client.call_tool(
                "get_framework_correlations",
                {
                    "framework_a": source_framework,
                    "framework_b": target,
                    "include_mappings": True
                }
            )
            mapping_results.append(correlation)

        return mapping_results
```

### 3. Compliance Documentation Generator

**Use Case**: Automated generation of compliance documentation

**Implementation Example**:
```python
class DocumentationGenerator:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def generate_framework_guide(self, framework_id):
        """Generate comprehensive framework guide"""

        # Get framework details
        details = await self.mcp_client.call_tool(
            "get_framework_details",
            {
                "framework_id": framework_id,
                "include_references": True
            }
        )

        # Export full framework data
        data = await self.mcp_client.call_tool(
            "export_framework_data",
            {
                "framework_id": framework_id,
                "format": "markdown",
                "include_metadata": True
            }
        )

        return self._format_documentation(details, data)

    async def generate_compliance_matrix(self, frameworks):
        """Generate cross-framework compliance matrix"""
        matrix = {}

        for framework in frameworks:
            compliance = await self.mcp_client.call_tool(
                "get_compliance_analysis",
                {"frameworks": [framework]}
            )
            matrix[framework] = compliance

        return self._format_matrix(matrix)
```

## Advanced Integration Patterns

### 1. Event-Driven Compliance Monitoring

**Architecture**: React to changes in framework data or compliance status

```python
class EventDrivenMonitor:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.subscribers = []

    async def monitor_compliance_changes(self):
        """Monitor for compliance status changes"""
        while True:
            current_status = await self._get_compliance_snapshot()

            if self._has_changed(current_status):
                await self._notify_subscribers(current_status)

            await asyncio.sleep(300)  # Check every 5 minutes

    async def _get_compliance_snapshot(self):
        """Get current compliance snapshot"""
        return await self.mcp_client.call_tool(
            "get_compliance_analysis",
            {"include_gaps": True}
        )
```

### 2. Multi-Framework Risk Assessment

**Use Case**: Comprehensive risk assessment across multiple frameworks

```python
class RiskAssessment:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def comprehensive_risk_assessment(self):
        """Perform comprehensive multi-framework risk assessment"""

        # Get all frameworks
        frameworks = await self.mcp_client.call_tool("list_frameworks")

        risk_assessment = {}

        for framework in frameworks["frameworks"]:
            if framework["status"] == "active":
                # Search for risk-related content
                risks = await self.mcp_client.call_tool(
                    "search_framework_references",
                    {
                        "framework_id": framework["id"],
                        "query": "risk OR threat OR vulnerability",
                        "limit": 20
                    }
                )

                # Analyze gaps
                gaps = await self.mcp_client.call_tool(
                    "find_compliance_gaps",
                    {
                        "source_framework": framework["id"],
                        "target_frameworks": [f["id"] for f in frameworks["frameworks"] if f["id"] != framework["id"]]
                    }
                )

                risk_assessment[framework["id"]] = {
                    "risks": risks,
                    "gaps": gaps,
                    "severity_analysis": self._analyze_severity(risks)
                }

        return risk_assessment
```

### 3. Intelligent Framework Recommendation

**Use Case**: Recommend relevant frameworks based on requirements

```python
class FrameworkRecommender:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def recommend_frameworks(self, requirements):
        """Recommend frameworks based on requirements"""

        recommendations = []

        # Search across all frameworks
        for requirement in requirements:
            results = await self.mcp_client.call_tool(
                "search_frameworks",
                {
                    "query": requirement,
                    "limit": 10
                }
            )

            # Analyze results to build recommendations
            for result in results["results"]:
                framework_id = result["framework"]
                score = result["relevance_score"]

                # Update recommendation scores
                existing = next((r for r in recommendations if r["framework"] == framework_id), None)
                if existing:
                    existing["score"] += score
                    existing["matching_requirements"].append(requirement)
                else:
                    recommendations.append({
                        "framework": framework_id,
                        "score": score,
                        "matching_requirements": [requirement]
                    })

        # Sort by score and return top recommendations
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations[:5]
```

## Performance Optimization

### 1. Caching Strategy

**Client-Side Caching**:
```python
import asyncio
from functools import lru_cache
from datetime import datetime, timedelta

class CachingMCPClient:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.cache = {}
        self.cache_ttl = timedelta(minutes=30)

    async def call_tool_cached(self, tool_name, arguments, ttl=None):
        """Call tool with caching"""
        cache_key = self._generate_cache_key(tool_name, arguments)

        # Check cache
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if datetime.now() - entry["timestamp"] < (ttl or self.cache_ttl):
                return entry["data"]

        # Call API and cache result
        result = await self.mcp_client.call_tool(tool_name, arguments)
        self.cache[cache_key] = {
            "data": result,
            "timestamp": datetime.now()
        }

        return result
```

### 2. Parallel Processing

**Concurrent Framework Queries**:
```python
async def parallel_framework_analysis(self, frameworks, query):
    """Analyze multiple frameworks in parallel"""

    tasks = []
    for framework in frameworks:
        task = self.mcp_client.call_tool(
            "search_framework_references",
            {
                "framework_id": framework,
                "query": query
            }
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results and handle exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "framework": frameworks[i],
                "error": str(result)
            })
        else:
            processed_results.append({
                "framework": frameworks[i],
                "data": result
            })

    return processed_results
```

### 3. Batch Operations

**Bulk Export Processing**:
```python
async def bulk_export_optimized(self, export_configs):
    """Optimized bulk export processing"""

    # Group exports by framework to minimize server load
    exports_by_framework = {}
    for config in export_configs:
        framework = config["framework_id"]
        if framework not in exports_by_framework:
            exports_by_framework[framework] = []
        exports_by_framework[framework].append(config)

    results = []

    # Process each framework's exports together
    for framework, configs in exports_by_framework.items():
        batch_result = await self.mcp_client.call_tool(
            "bulk_export_frameworks",
            {"exports": configs}
        )
        results.append(batch_result)

    return results
```

## Error Handling Best Practices

### 1. Robust Error Handling

```python
import logging
from typing import Optional, Dict, Any

class RobustMCPClient:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.logger = logging.getLogger(__name__)

    async def safe_call_tool(self, tool_name: str, arguments: Dict[str, Any],
                           max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """Safe tool call with retry logic"""

        for attempt in range(max_retries):
            try:
                return await self.mcp_client.call_tool(tool_name, arguments)

            except RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = e.retry_after if hasattr(e, 'retry_after') else 2 ** attempt
                    self.logger.warning(f"Rate limited, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                raise

            except ServiceUnavailableError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Service unavailable, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                raise

            except Exception as e:
                self.logger.error(f"Unexpected error calling {tool_name}: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1)
```

### 2. Graceful Degradation

```python
class GracefulFrameworkClient:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def get_framework_data_with_fallback(self, framework_id):
        """Get framework data with fallback strategies"""

        try:
            # Try primary method
            return await self.mcp_client.call_tool(
                "get_framework_details",
                {"framework_id": framework_id, "include_references": True}
            )

        except FrameworkUnavailableError:
            # Fallback to basic details
            try:
                return await self.mcp_client.call_tool(
                    "get_framework_details",
                    {"framework_id": framework_id, "include_references": False}
                )
            except Exception:
                # Final fallback to framework list
                frameworks = await self.mcp_client.call_tool("list_frameworks")
                for fw in frameworks["frameworks"]:
                    if fw["id"] == framework_id:
                        return {"framework": fw, "references": []}

                raise FrameworkNotFoundError(f"Framework {framework_id} not available")
```

## Testing Integration

### 1. Unit Testing

```python
import pytest
from unittest.mock import AsyncMock

class TestFrameworkIntegration:
    @pytest.fixture
    def mock_mcp_client(self):
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_compliance_analysis(self, mock_mcp_client):
        # Mock response
        mock_mcp_client.call_tool.return_value = {
            "analysis_summary": {
                "overall_compliance_rate": 85.5
            }
        }

        monitor = ComplianceMonitor(mock_mcp_client)
        result = await monitor.assess_compliance()

        assert result["compliance_rate"] == 85.5
        mock_mcp_client.call_tool.assert_called_once()
```

### 2. Integration Testing

```python
class TestLiveIntegration:
    @pytest.mark.integration
    async def test_framework_search(self):
        client = MCPClient()  # Real client

        result = await client.call_tool(
            "search_frameworks",
            {"query": "risk management", "limit": 5}
        )

        assert result["total_results"] > 0
        assert len(result["results"]) <= 5
        assert all("relevance_score" in r for r in result["results"])
```

## Production Deployment

### 1. Connection Management

```python
class ProductionMCPClient:
    def __init__(self, config):
        self.config = config
        self.connection_pool = ConnectionPool(
            max_connections=config.max_connections,
            timeout=config.timeout
        )

    async def __aenter__(self):
        await self.connection_pool.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connection_pool.close()
```

### 2. Monitoring and Metrics

```python
import time
import metrics

class MonitoredMCPClient:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.metrics = metrics.get_client()

    async def call_tool(self, tool_name, arguments):
        start_time = time.time()

        try:
            result = await self.mcp_client.call_tool(tool_name, arguments)
            self.metrics.increment(f"mcp.tool.{tool_name}.success")
            return result

        except Exception as e:
            self.metrics.increment(f"mcp.tool.{tool_name}.error")
            self.metrics.increment(f"mcp.error.{type(e).__name__}")
            raise

        finally:
            duration = time.time() - start_time
            self.metrics.timing(f"mcp.tool.{tool_name}.duration", duration)
```

This comprehensive integration guide provides the foundation for building robust applications that leverage the FINOS MCP Server's governance framework capabilities.
