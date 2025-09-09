"""Content management package for FINOS MCP Server.

This package provides modular content handling including:
- HTTP client with retries and circuit breaker
- Document parsing and validation
- Caching layer with TTL and eviction
- Service orchestration
"""

__all__ = ["HTTPClient", "fetch"]

from .fetch import HTTPClient

__version__ = "0.1.0-dev"
