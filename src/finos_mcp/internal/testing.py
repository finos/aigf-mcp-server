"""
Fast test mode infrastructure for offline testing.
Provides in-memory replacements for HTTP clients and caches.
"""

import os
from typing import Any, Optional

# Global fast mode context
_fast_mode_context: Optional["FastTestMode"] = None


class InMemoryCache:
    """In-memory cache for instant operations."""

    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, Any] = {}
        self._max_size = max_size
        self._access_order = []

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if key in self._cache:
            self._update_access_order(key)
            return self._cache[key]
        return None

    def get_sync(self, key: str) -> Any | None:
        """Synchronous get for testing."""
        if key in self._cache:
            self._update_access_order(key)
            return self._cache[key]
        return None

    async def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        self.set_sync(key, value)

    def set_sync(self, key: str, value: Any) -> None:
        """Synchronous set for testing."""
        if len(self._cache) >= self._max_size and key not in self._cache:
            # LRU eviction
            oldest_key = self._access_order[0]
            del self._cache[oldest_key]
            self._access_order.remove(oldest_key)

        self._cache[key] = value
        self._update_access_order(key)

    async def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._access_order.clear()

    def _update_access_order(self, key: str) -> None:
        """Update access order for LRU."""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)


class MockResponse:
    """Mock HTTP response."""

    def __init__(self, data: dict[str, Any], status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        """Return JSON data."""
        return self._data


class InMemoryHTTPClient:
    """In-memory HTTP client for offline testing."""

    def __init__(self, custom_responses: dict[str, Any] | None = None):
        self.responses = self._load_default_responses()
        if custom_responses:
            self.responses.update(custom_responses)

        self.network_calls_made = 0
        self.mock_responses_served = 0

    def _load_default_responses(self) -> dict[str, Any]:
        """Load default mock responses."""
        return {
            "mitigation": {
                "sample-mitigation.md": {
                    "filename": "sample-mitigation.md",
                    "type": "mitigation",
                    "content": "# Sample Mitigation\n\nThis is a mock mitigation for testing.",
                    "metadata": {"title": "Sample Mitigation", "category": "security"},
                }
            },
            "risk": {
                "sample-risk.md": {
                    "filename": "sample-risk.md",
                    "type": "risk",
                    "content": "# Sample Risk\n\nThis is a mock risk for testing.",
                    "metadata": {"title": "Sample Risk", "category": "model-security"},
                }
            },
        }

    def get_response(
        self, response_type: str, filename: str | None = None
    ) -> dict[str, Any] | None:
        """Get mock response by type and filename."""
        if response_type in self.responses:
            if (
                filename
                and isinstance(self.responses[response_type], dict)
                and filename in self.responses[response_type]
            ):
                return self.responses[response_type][filename]
            elif not filename:
                # Return first response for type or the direct response if not nested
                type_response = self.responses[response_type]
                if isinstance(type_response, dict) and all(
                    isinstance(v, dict) for v in type_response.values()
                ):
                    # Nested structure (type -> filename -> data)
                    return next(iter(type_response.values())) if type_response else None
                else:
                    # Direct response (type -> data)
                    return type_response
        return None

    async def get(self, url: str) -> MockResponse:
        """Mock GET request."""
        self.mock_responses_served += 1

        # Extract type and filename from URL
        if "mitigation" in url:
            data = self.get_response("mitigation", "sample-mitigation.md")
        elif "risk" in url:
            data = self.get_response("risk", "sample-risk.md")
        else:
            data = {"status": "success", "data": "mock_response"}

        return MockResponse(data or {})

    async def post(self, url: str, **kwargs) -> MockResponse:
        """Mock POST request."""
        self.mock_responses_served += 1
        return MockResponse({"status": "success", "method": "POST"})


class FastTestMode:
    """Context manager for fast test mode."""

    def __init__(self):
        self.network_calls_count = 0
        self.cache_hits = 0
        self.mock_responses_served = 0
        self.is_active = False
        self._cache = InMemoryCache()
        self._http_client = InMemoryHTTPClient()

    async def __aenter__(self):
        """Enter async context."""
        self.is_active = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        self.is_active = False

    def __enter__(self):
        """Enter context."""
        self.is_active = True
        # Patch content service to use fast mode
        self._patch_content_service()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        self.is_active = False
        self._unpatch_content_service()

    def _patch_content_service(self):
        """Patch content service for fast mode."""
        global _fast_mode_context
        _fast_mode_context = self

    def _unpatch_content_service(self):
        """Restore original content service."""
        global _fast_mode_context
        _fast_mode_context = None

    def _record_cache_hit(self):
        """Record cache hit for metrics."""
        self.cache_hits += 1

    def _record_mock_response(self):
        """Record mock response for metrics."""
        self.mock_responses_served += 1

    def get_mock_search_results(self, query: str) -> dict[str, Any]:
        """Get mock search results."""
        self._record_mock_response()
        return {
            "results": [
                {
                    "filename": "sample-mitigation.md",
                    "type": "mitigation",
                    "relevance_score": 0.95,
                    "title": "Sample Mitigation",
                },
                {
                    "filename": "sample-risk.md",
                    "type": "risk",
                    "relevance_score": 0.87,
                    "title": "Sample Risk",
                },
            ],
            "total_count": 2,
            "query": query,
        }

    @staticmethod
    def is_fast_mode_enabled() -> bool:
        """Check if fast mode is enabled via environment."""
        return os.getenv("FINOS_MCP_FAST_MODE", "false").lower() == "true"

    @staticmethod
    def should_use_offline_mode() -> bool:
        """Check if offline mode should be used."""
        return os.getenv("FINOS_MCP_OFFLINE_MODE", "false").lower() == "true"
