# Integration Guide

Comprehensive guide for developers integrating with the FINOS AI Governance Framework MCP Server.

## Overview

The FINOS MCP Server provides 11 MCP tools for accessing AI governance framework data through the Model Context Protocol (MCP). This guide covers integration patterns, best practices, and code examples.

## Quick Start Integration

### 1. Basic Setup

**Prerequisites**:
- Python 3.10+
- MCP-compatible client (Claude Desktop, VS Code, Cursor)
- Network access for framework data loading

**Installation**:
```bash
git clone https://github.com/<OWNER>/<REPO>.git
cd aigf-mcp-server
pip install -e .
```

**Configuration**:
```bash
# Test the installation
finos-mcp --help

# Verify server connectivity via MCP client
```

### 2. First API Call

Start with a simple framework listing:

```python
# Example: List available frameworks
{
  "tool": "list_frameworks",
  "arguments": {}
}
```

**Expected Response**:
```json
{
  "total_count": 7,
  "frameworks": [
    {
      "id": "nist-ai-600-1",
      "name": "NIST AI Risk Management Framework",
      "description": "NIST's framework for managing AI risks"
    }
  ]
}
```

## Available Tools (11 Total)

### Framework Access Tools (5)

**1. list_frameworks** - List all supported AI governance frameworks
```python
# Usage
mcp_client.call_tool("list_frameworks", {})

# Returns: Available frameworks with IDs, names, descriptions
```

**2. get_framework** - Get complete content of a specific framework
```python
# Usage
mcp_client.call_tool("get_framework", {
    "framework": "nist-ai-600-1"
})

# Returns: Complete framework content with sections
```

**3. search_frameworks** - Search for text within framework documents
```python
# Usage
mcp_client.call_tool("search_frameworks", {
    "query": "risk management",
    "limit": 5
})

# Returns: Search results with matching content snippets
```

**4. list_risks** - List all available risk documents
```python
# Usage
mcp_client.call_tool("list_risks", {})

# Returns: Risk documents from FINOS repository
```

**5. get_risk** - Get complete content of specific risk documents
```python
# Usage
mcp_client.call_tool("get_risk", {
    "risk_id": "10_prompt-injection"
})

# Returns: Complete risk document content
```

### Risk & Mitigation Tools (4)

**6. search_risks** - Search within risk documentation
```python
# Usage
mcp_client.call_tool("search_risks", {
    "query": "injection",
    "limit": 5
})

# Returns: Matching risk content snippets
```

**7. list_mitigations** - List all available mitigation documents
```python
# Usage
mcp_client.call_tool("list_mitigations", {})

# Returns: Mitigation documents from FINOS repository
```

**8. get_mitigation** - Get complete content of mitigation documents
```python
# Usage
mcp_client.call_tool("get_mitigation", {
    "mitigation_id": "1_ai-data-leakage-prevention-and-detection"
})

# Returns: Complete mitigation document content
```

**9. search_mitigations** - Search within mitigation documentation
```python
# Usage
mcp_client.call_tool("search_mitigations", {
    "query": "encryption",
    "limit": 5
})

# Returns: Matching mitigation content snippets
```

### System Monitoring Tools (2)

**10. get_service_health** - Get service health status and metrics
```python
# Usage
mcp_client.call_tool("get_service_health", {})

# Returns: Health status, uptime, service component status
```

**11. get_cache_stats** - Get cache performance statistics
```python
# Usage
mcp_client.call_tool("get_cache_stats", {})

# Returns: Cache hit rate, memory usage, performance metrics
```

## Integration Patterns

### 1. Framework Research System

**Use Case**: Search and retrieve governance framework content

**Implementation Example**:
```python
class FrameworkResearcher:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def research_topic(self, topic):
        """Research a topic across all frameworks"""

        # Search across frameworks
        results = await self.mcp_client.call_tool(
            "search_frameworks",
            {
                "query": topic,
                "limit": 10
            }
        )

        return {
            "search_results": results,
            "summary": self._generate_summary(results)
        }

    async def get_framework_details(self, framework_id):
        """Get complete framework content"""

        return await self.mcp_client.call_tool(
            "get_framework",
            {"framework": framework_id}
        )
```

### 2. Risk Assessment Platform

**Use Case**: AI governance risk assessment and analysis

**Implementation Example**:
```python
class RiskAssessment:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def comprehensive_risk_assessment(self):
        """Perform comprehensive AI risk assessment"""

        # Get all risks
        risks = await self.mcp_client.call_tool("list_risks", {})

        risk_assessment = {}

        for risk in risks["documents"]:
            # Get detailed risk content
            risk_details = await self.mcp_client.call_tool(
                "get_risk",
                {"risk_id": risk["id"]}
            )

            risk_assessment[risk["id"]] = {
                "title": risk_details["title"],
                "content": risk_details["content"],
                "severity_analysis": self._analyze_severity(risk_details)
            }

        return risk_assessment

    async def search_specific_risks(self, keyword):
        """Search for specific types of risks"""

        return await self.mcp_client.call_tool(
            "search_risks",
            {
                "query": keyword,
                "limit": 5
            }
        )
```

### 3. Mitigation Planning System

**Use Case**: Develop mitigation strategies for identified risks

**Implementation Example**:
```python
class MitigationPlanner:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def get_mitigation_strategies(self, risk_keywords):
        """Get relevant mitigation strategies for risks"""

        strategies = []

        for keyword in risk_keywords:
            # Search for relevant mitigations
            results = await self.mcp_client.call_tool(
                "search_mitigations",
                {
                    "query": keyword,
                    "limit": 3
                }
            )

            strategies.extend(results["results"])

        return self._deduplicate_strategies(strategies)

    async def get_detailed_mitigation(self, mitigation_id):
        """Get detailed mitigation implementation guide"""

        return await self.mcp_client.call_tool(
            "get_mitigation",
            {"mitigation_id": mitigation_id}
        )
```

### 4. System Monitoring

**Use Case**: Monitor MCP server health and performance

**Implementation Example**:
```python
class SystemMonitor:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def check_system_health(self):
        """Check MCP server health status"""

        health = await self.mcp_client.call_tool("get_service_health", {})
        cache_stats = await self.mcp_client.call_tool("get_cache_stats", {})

        return {
            "health": health,
            "cache_performance": cache_stats,
            "status": self._evaluate_status(health, cache_stats)
        }
```

## Performance Optimization

### 1. Caching Strategy

**Client-Side Caching**:
```python
from datetime import datetime, timedelta

class CachingMCPClient:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.cache = {}
        self.cache_ttl = timedelta(minutes=30)

    async def call_tool_cached(self, tool_name, arguments, ttl=None):
        """Call tool with client-side caching"""
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

    def _generate_cache_key(self, tool_name, arguments):
        """Generate cache key from tool call"""
        import json
        args_str = json.dumps(arguments, sort_keys=True)
        return f"{tool_name}:{args_str}"
```

### 2. Parallel Processing

**Concurrent Framework Queries**:
```python
import asyncio

async def parallel_framework_search(mcp_client, queries):
    """Search multiple queries in parallel"""

    tasks = []
    for query in queries:
        task = mcp_client.call_tool(
            "search_frameworks",
            {"query": query, "limit": 5}
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results and handle exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "query": queries[i],
                "error": str(result)
            })
        else:
            processed_results.append({
                "query": queries[i],
                "data": result
            })

    return processed_results
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

            except Exception as e:
                self.logger.error(f"Error calling {tool_name}: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        return None
```

### 2. Graceful Degradation

```python
class GracefulFrameworkClient:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def get_framework_with_fallback(self, framework_id):
        """Get framework data with fallback strategies"""

        try:
            # Try primary method
            return await self.mcp_client.call_tool(
                "get_framework",
                {"framework": framework_id}
            )

        except Exception:
            # Fallback to framework list
            try:
                frameworks = await self.mcp_client.call_tool("list_frameworks", {})
                for fw in frameworks["frameworks"]:
                    if fw["id"] == framework_id:
                        return {
                            "framework_id": framework_id,
                            "name": fw["name"],
                            "description": fw["description"],
                            "content": "Detailed content unavailable"
                        }
            except Exception:
                pass

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
    async def test_framework_search(self, mock_mcp_client):
        # Mock response
        mock_mcp_client.call_tool.return_value = {
            "query": "risk",
            "total_found": 5,
            "results": []
        }

        researcher = FrameworkResearcher(mock_mcp_client)
        result = await researcher.research_topic("risk")

        assert "search_results" in result
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

        assert result["total_found"] > 0
        assert len(result["results"]) <= 5
```

## Production Deployment

### 1. Connection Management

```python
class ProductionMCPClient:
    def __init__(self, config):
        self.config = config

    async def __aenter__(self):
        # Initialize connection
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Clean up resources
        pass
```

### 2. Monitoring and Metrics

```python
import time

class MonitoredMCPClient:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def call_tool(self, tool_name, arguments):
        start_time = time.time()

        try:
            result = await self.mcp_client.call_tool(tool_name, arguments)
            duration = time.time() - start_time
            self._log_success(tool_name, duration)
            return result

        except Exception as e:
            duration = time.time() - start_time
            self._log_error(tool_name, duration, e)
            raise

    def _log_success(self, tool_name, duration):
        print(f"Tool {tool_name} succeeded in {duration:.2f}s")

    def _log_error(self, tool_name, duration, error):
        print(f"Tool {tool_name} failed after {duration:.2f}s: {error}")
```

## Best Practices

1. **Use Appropriate Tools**: Choose the right tool for your use case (list vs search vs get)
2. **Implement Caching**: Cache frequently accessed framework content client-side
3. **Handle Errors Gracefully**: Implement retry logic and fallback strategies
4. **Monitor Performance**: Track tool call performance and cache hit rates
5. **Test Thoroughly**: Write unit and integration tests for your integration
6. **Follow MCP Protocol**: Adhere to MCP 2025-06-18 specification

## Common Use Cases

### Research Workflow
1. `list_frameworks()` - See available frameworks
2. `search_frameworks("topic")` - Find relevant content
3. `get_framework("id")` - Get complete framework

### Risk Assessment Workflow
1. `list_risks()` - Browse all risks
2. `search_risks("keyword")` - Find specific risks
3. `get_risk("id")` - Get detailed risk information

### Mitigation Planning Workflow
1. `list_mitigations()` - Browse all mitigations
2. `search_mitigations("keyword")` - Find relevant mitigations
3. `get_mitigation("id")` - Get detailed mitigation strategies

### System Monitoring Workflow
1. `get_service_health()` - Check system status
2. `get_cache_stats()` - Monitor cache performance

This comprehensive integration guide provides the foundation for building robust applications that leverage the FINOS MCP Server's 11 governance framework tools.
