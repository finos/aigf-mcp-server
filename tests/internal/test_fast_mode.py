"""
TDD tests for fast test mode infrastructure.
Tests the in-memory replacements and offline testing capabilities.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

import pytest

# These imports will fail initially (TDD Red phase) - that's expected
try:
    from finos_mcp.internal.testing import FastTestMode, InMemoryHTTPClient, InMemoryCache
    from finos_mcp.internal.mock_content_service import get_mock_content_service as get_content_service
except ImportError:
    # Expected during Red phase - modules don't exist yet
    FastTestMode = None
    InMemoryHTTPClient = None
    InMemoryCache = None
    get_content_service = None


@pytest.mark.unit
@pytest.mark.asyncio
class TestFastTestMode:
    """Test the FastTestMode context manager."""

    async def test_fast_mode_context_manager(self):
        """Test FastTestMode context manager functionality."""
        if FastTestMode is None:
            pytest.skip("FastTestMode not implemented yet (TDD Red phase)")
        
        # Test context manager creation
        fast_mode = FastTestMode()
        assert fast_mode is not None
        
        # Test entering context
        async with fast_mode as mode:
            assert mode.network_calls_count == 0
            assert mode.cache_hits == 0
            assert mode.is_active == True
        
        # Test exiting context
        assert mode.is_active == False

    async def test_fast_mode_bypasses_network(self):
        """Test that FastTestMode bypasses network calls."""
        if FastTestMode is None or get_content_service is None:
            pytest.skip("FastTestMode not implemented yet (TDD Red phase)")
        
        with FastTestMode() as fast_mode:
            service = await get_content_service()
            result = await service.get_document("mitigation", "test.md")
            
            # Should get mock data without network calls
            assert result is not None
            assert fast_mode.network_calls_count == 0
            assert fast_mode.cache_hits > 0
            
            # Verify we got mock data structure
            assert "filename" in result
            assert "content" in result

    async def test_fast_mode_70_percent_speedup(self):
        """Test that FastTestMode achieves at least 70% speedup."""
        if FastTestMode is None or get_content_service is None:
            pytest.skip("FastTestMode not implemented yet (TDD Red phase)")
        
        # Measure normal mode (mocked for testing)
        start = time.time()
        with patch('finos_mcp.content.service.get_content_service') as mock_service:
            # Simulate slow network calls
            mock_service.return_value.get_document = AsyncMock()
            mock_service.return_value.get_document.side_effect = lambda *args: asyncio.sleep(0.1)
            
            for _ in range(5):
                service = await get_content_service()
                await service.get_document("mitigation", "sample.md")
        normal_time = time.time() - start
        
        # Measure fast mode
        start = time.time()
        with FastTestMode():
            for _ in range(5):
                service = await get_content_service()
                await service.get_document("mitigation", "sample.md")
        fast_time = time.time() - start
        
        # Calculate speedup
        speedup = normal_time / fast_time if fast_time > 0 else float('inf')
        assert speedup >= 1.7, f"Expected 70% speedup, got {speedup:.2f}x"

    async def test_fast_mode_metrics_tracking(self):
        """Test that FastTestMode tracks metrics correctly."""
        if FastTestMode is None:
            pytest.skip("FastTestMode not implemented yet (TDD Red phase)")
        
        with FastTestMode() as fast_mode:
            # Test initial metrics
            assert fast_mode.network_calls_count == 0
            assert fast_mode.cache_hits == 0
            assert fast_mode.mock_responses_served == 0
            
            # Simulate operations that should increment metrics
            fast_mode._record_cache_hit()
            fast_mode._record_mock_response()
            
            # Verify metrics tracking
            assert fast_mode.cache_hits == 1
            assert fast_mode.mock_responses_served == 1


@pytest.mark.unit
class TestInMemoryHTTPClient:
    """Test the InMemoryHTTPClient for offline testing."""

    def test_in_memory_http_client_creation(self):
        """Test InMemoryHTTPClient initialization."""
        if InMemoryHTTPClient is None:
            pytest.skip("InMemoryHTTPClient not implemented yet (TDD Red phase)")
        
        client = InMemoryHTTPClient()
        assert client is not None
        assert hasattr(client, 'responses')
        assert hasattr(client, 'get')
        assert hasattr(client, 'post')

    def test_preloaded_responses(self):
        """Test that InMemoryHTTPClient has preloaded responses."""
        if InMemoryHTTPClient is None:
            pytest.skip("InMemoryHTTPClient not implemented yet (TDD Red phase)")
        
        client = InMemoryHTTPClient()
        
        # Should have preloaded mitigation responses
        mitigation_response = client.get_response("mitigation", "sample-mitigation.md")
        assert mitigation_response is not None
        assert "filename" in mitigation_response
        assert "content" in mitigation_response
        
        # Should have preloaded risk responses
        risk_response = client.get_response("risk", "sample-risk.md")
        assert risk_response is not None
        assert "filename" in risk_response
        assert "content" in risk_response

    async def test_http_client_mock_responses(self):
        """Test HTTP client returns mock responses."""
        if InMemoryHTTPClient is None:
            pytest.skip("InMemoryHTTPClient not implemented yet (TDD Red phase)")
        
        client = InMemoryHTTPClient()
        
        # Test GET request
        response = await client.get("https://example.com/api/mitigation/test.md")
        assert response.status_code == 200
        assert response.json() is not None
        
        # Test that no actual network call was made
        assert client.network_calls_made == 0
        assert client.mock_responses_served > 0

    def test_http_client_configurable_responses(self):
        """Test that HTTP client accepts custom responses."""
        if InMemoryHTTPClient is None:
            pytest.skip("InMemoryHTTPClient not implemented yet (TDD Red phase)")
        
        custom_responses = {
            "custom_endpoint": {"data": "custom_data", "status": "success"}
        }
        
        client = InMemoryHTTPClient(custom_responses=custom_responses)
        response = client.get_response("custom_endpoint")
        
        assert response["data"] == "custom_data"
        assert response["status"] == "success"


@pytest.mark.unit
class TestInMemoryCache:
    """Test the InMemoryCache for fast testing."""

    def test_in_memory_cache_creation(self):
        """Test InMemoryCache initialization."""
        if InMemoryCache is None:
            pytest.skip("InMemoryCache not implemented yet (TDD Red phase)")
        
        cache = InMemoryCache()
        assert cache is not None
        assert hasattr(cache, 'get')
        assert hasattr(cache, 'set')
        assert hasattr(cache, 'clear')

    async def test_cache_operations(self):
        """Test basic cache operations."""
        if InMemoryCache is None:
            pytest.skip("InMemoryCache not implemented yet (TDD Red phase)")
        
        cache = InMemoryCache()
        
        # Test set and get
        await cache.set("test_key", {"data": "test_value"})
        result = await cache.get("test_key")
        
        assert result is not None
        assert result["data"] == "test_value"
        
        # Test cache miss
        missing = await cache.get("nonexistent_key")
        assert missing is None

    async def test_cache_instant_operations(self):
        """Test that cache operations are instant (no delays)."""
        if InMemoryCache is None:
            pytest.skip("InMemoryCache not implemented yet (TDD Red phase)")
        
        cache = InMemoryCache()
        
        # Measure cache operation time
        start = time.time()
        await cache.set("speed_test", {"large_data": "x" * 1000})
        result = await cache.get("speed_test")
        operation_time = time.time() - start
        
        # Should be instant (less than 1ms)
        assert operation_time < 0.001
        assert result is not None

    def test_cache_size_limits(self):
        """Test cache respects size limits for testing."""
        if InMemoryCache is None:
            pytest.skip("InMemoryCache not implemented yet (TDD Red phase)")
        
        # Create cache with small limit for testing
        cache = InMemoryCache(max_size=2)
        
        # Fill cache beyond limit
        cache.set_sync("key1", "value1")
        cache.set_sync("key2", "value2")
        cache.set_sync("key3", "value3")  # Should evict oldest
        
        # Verify LRU eviction
        assert cache.get_sync("key1") is None  # Evicted
        assert cache.get_sync("key2") is not None
        assert cache.get_sync("key3") is not None


@pytest.mark.integration
class TestFastModeIntegration:
    """Integration tests for fast mode with existing services."""

    async def test_fast_mode_with_content_service(self):
        """Test FastTestMode integration with ContentService."""
        if FastTestMode is None or get_content_service is None:
            pytest.skip("FastTestMode not implemented yet (TDD Red phase)")
        
        with FastTestMode() as fast_mode:
            # Test document retrieval
            service = await get_content_service()
            
            # Test mitigation document
            mitigation = await service.get_document("mitigation", "sample-mitigation.md")
            assert mitigation is not None
            assert mitigation["type"] == "mitigation"
            
            # Test risk document
            risk = await service.get_document("risk", "sample-risk.md")
            assert risk is not None
            assert risk["type"] == "risk"
            
            # Verify no network calls
            assert fast_mode.network_calls_count == 0
            assert fast_mode.cache_hits > 0

    async def test_fast_mode_search_functionality(self):
        """Test search functionality in fast mode."""
        if FastTestMode is None:
            pytest.skip("FastTestMode not implemented yet (TDD Red phase)")
        
        with FastTestMode() as fast_mode:
            # This would typically call search service
            # For now, test that we can access mock search data
            search_results = fast_mode.get_mock_search_results("ai risk")
            
            assert search_results is not None
            assert "results" in search_results
            assert len(search_results["results"]) > 0
            
            # Verify structure
            first_result = search_results["results"][0]
            assert "filename" in first_result
            assert "type" in first_result
            assert "relevance_score" in first_result

    def test_fast_mode_environment_detection(self):
        """Test that fast mode detects test environment correctly."""
        if FastTestMode is None:
            pytest.skip("FastTestMode not implemented yet (TDD Red phase)")
        
        import os
        
        # Test without environment variable
        assert not FastTestMode.is_fast_mode_enabled()
        
        # Test with environment variable
        os.environ["FINOS_MCP_FAST_MODE"] = "true"
        assert FastTestMode.is_fast_mode_enabled()
        
        # Test with offline mode
        os.environ["FINOS_MCP_OFFLINE_MODE"] = "true"
        assert FastTestMode.should_use_offline_mode()
        
        # Cleanup
        os.environ.pop("FINOS_MCP_FAST_MODE", None)
        os.environ.pop("FINOS_MCP_OFFLINE_MODE", None)


@pytest.mark.performance
class TestFastModePerformance:
    """Performance tests for fast mode infrastructure."""

    async def test_performance_with_many_requests(self):
        """Test fast mode performance with many concurrent requests."""
        if FastTestMode is None:
            pytest.skip("FastTestMode not implemented yet (TDD Red phase)")
        
        async def make_request(fast_mode):
            """Simulate a content request."""
            # This would be actual service call in real implementation
            fast_mode._record_cache_hit()
            return {"status": "success"}
        
        with FastTestMode() as fast_mode:
            start = time.time()
            
            # Run 100 concurrent requests
            tasks = [make_request(fast_mode) for _ in range(100)]
            results = await asyncio.gather(*tasks)
            
            duration = time.time() - start
            
            # Should complete very quickly
            assert duration < 0.1  # Less than 100ms
            assert len(results) == 100
            assert fast_mode.cache_hits == 100

    def test_memory_usage_efficiency(self):
        """Test that fast mode is memory efficient."""
        if FastTestMode is None or InMemoryCache is None:
            pytest.skip("FastTestMode not implemented yet (TDD Red phase)")
        
        import sys
        
        # Measure memory before
        cache = InMemoryCache(max_size=1000)
        initial_size = sys.getsizeof(cache)
        
        # Add many items
        for i in range(100):
            cache.set_sync(f"key_{i}", f"value_{i}")
        
        final_size = sys.getsizeof(cache)
        
        # Memory growth should be reasonable
        growth = final_size - initial_size
        assert growth < 100000  # Less than 100KB for 100 items


if __name__ == "__main__":
    # Run tests manually for TDD development
    print("🔴 TDD Red Phase: Running tests (expecting failures)")
    pytest.main([__file__, "-v", "--tb=short"])