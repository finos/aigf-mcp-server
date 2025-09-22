"""
Unit tests for TTL cache functionality.

Tests comprehensive caching behavior including TTL expiration, LRU eviction,
thread safety, and monitoring capabilities.
"""

import asyncio
import time
from unittest.mock import patch

import pytest
import pytest_asyncio

from finos_mcp.content.cache import (
    CacheEntry,
    CacheStats,
    TTLCache,
    close_cache,
    get_cache,
)


@pytest_asyncio.fixture
async def cache():
    """Create a test cache instance."""
    import os
    # Set secure cache key for testing
    test_key = "test_cache_key_" + "a" * 17  # 32 character minimum key for testing
    os.environ["FINOS_MCP_CACHE_SECRET"] = test_key

    test_cache: TTLCache[str, str] = TTLCache(
        max_size=5,
        default_ttl=1.0,  # 1 second for fast testing
        cleanup_interval=0.1,  # Fast cleanup for testing
        enable_background_cleanup=False,  # Disable for controlled testing
    )
    try:
        yield test_cache
    finally:
        await test_cache.close()
        # Clean up environment variable after test
        os.environ.pop("FINOS_MCP_CACHE_SECRET", None)


@pytest_asyncio.fixture
async def cache_no_ttl():
    """Create a test cache without TTL."""
    import os
    # Set secure cache key for testing
    test_key = "test_cache_no_ttl_" + "a" * 15  # 32 character minimum key for testing
    os.environ["FINOS_MCP_CACHE_SECRET"] = test_key

    test_cache: TTLCache[str, str] = TTLCache(
        max_size=3, default_ttl=None, enable_background_cleanup=False
    )
    try:
        yield test_cache
    finally:
        await test_cache.close()
        # Clean up environment variable after test
        os.environ.pop("FINOS_MCP_CACHE_SECRET", None)


@pytest.mark.unit
class TestCacheEntry:
    """Test CacheEntry functionality."""

    def test_cache_entry_creation(self):
        """Test basic cache entry creation."""
        current_time = time.time()
        entry = CacheEntry(
            value="test_value",
            created_at=current_time,
            accessed_at=current_time,
            expires_at=current_time + 10,
        )

        assert entry.value == "test_value"
        assert entry.created_at == current_time
        assert entry.accessed_at == current_time
        assert entry.expires_at == current_time + 10
        assert entry.access_count == 0

    def test_cache_entry_expiration(self):
        """Test cache entry expiration logic."""
        current_time = time.time()

        # Non-expiring entry
        entry = CacheEntry("test", current_time, current_time, None)
        assert not entry.is_expired()
        assert not entry.is_expired(current_time + 100)

        # Expiring entry
        expires_at = current_time + 10
        entry = CacheEntry("test", current_time, current_time, expires_at)
        assert not entry.is_expired(current_time + 5)
        assert entry.is_expired(current_time + 15)

    def test_cache_entry_touch(self):
        """Test cache entry access tracking."""
        current_time = time.time()
        entry = CacheEntry("test", current_time, current_time, None)

        # Touch entry
        new_time = current_time + 5
        entry.touch(new_time)

        assert entry.accessed_at == new_time
        assert entry.access_count == 1

        # Touch again
        entry.touch(new_time + 5)
        assert entry.access_count == 2

    def test_cache_entry_time_methods(self):
        """Test cache entry time calculation methods."""
        current_time = time.time()
        expires_at = current_time + 100
        entry = CacheEntry("test", current_time, current_time, expires_at)

        # Test age calculation
        test_time = current_time + 50
        assert entry.age_seconds(test_time) == 50

        # Test time to expiry
        assert entry.time_to_expiry(test_time) == 50

        # Test expired entry
        assert entry.time_to_expiry(current_time + 150) == 0


@pytest.mark.unit
class TestCacheStats:
    """Test CacheStats functionality."""

    def test_cache_stats_creation(self):
        """Test cache stats creation and update."""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0

        # Update stats
        stats.hits = 10
        stats.misses = 5
        stats.update_hit_rate()

        assert stats.hit_rate == 2 / 3

    def test_cache_stats_to_dict(self):
        """Test cache stats dictionary conversion."""
        stats = CacheStats(hits=10, misses=5, sets=15)
        dict_stats = stats.to_dict()

        assert dict_stats["hits"] == 10
        assert dict_stats["misses"] == 5
        assert dict_stats["sets"] == 15
        assert "hit_rate" in dict_stats


@pytest.mark.unit
class TestTTLCache:
    """Test TTL Cache functionality."""

    @pytest.mark.asyncio
    async def test_basic_get_set(self, cache):
        """Test basic cache get/set operations."""
        # Test set and get
        await cache.set("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"

        # Test non-existent key
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache):
        """Test TTL expiration behavior."""
        # Set with short TTL
        await cache.set("key1", "value1", ttl=0.1)

        # Should be available immediately
        result = await cache.get("key1")
        assert result == "value1"

        # Wait for expiration
        await asyncio.sleep(0.2)

        # Should be expired
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_ttl(self, cache_no_ttl):
        """Test cache without TTL."""
        await cache_no_ttl.set("key1", "value1")

        # Should still be available after default TTL
        await asyncio.sleep(0.1)
        result = await cache_no_ttl.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_lru_eviction(self, cache_no_ttl):
        """Test LRU eviction when cache is full."""
        # Fill cache to capacity (3 items)
        await cache_no_ttl.set("key1", "value1")
        await cache_no_ttl.set("key2", "value2")
        await cache_no_ttl.set("key3", "value3")

        # Verify all are present
        assert await cache_no_ttl.get("key1") == "value1"
        assert await cache_no_ttl.get("key2") == "value2"
        assert await cache_no_ttl.get("key3") == "value3"

        # Add one more item, should evict key1 (least recently used)
        await cache_no_ttl.set("key4", "value4")

        # key1 should be evicted
        assert await cache_no_ttl.get("key1") is None
        assert await cache_no_ttl.get("key2") == "value2"
        assert await cache_no_ttl.get("key3") == "value3"
        assert await cache_no_ttl.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_lru_access_order(self, cache_no_ttl):
        """Test that access updates LRU order."""
        # Fill cache
        await cache_no_ttl.set("key1", "value1")
        await cache_no_ttl.set("key2", "value2")
        await cache_no_ttl.set("key3", "value3")

        # Access key1 to make it most recently used
        await cache_no_ttl.get("key1")

        # Add new item, should evict key2 now (least recently used)
        await cache_no_ttl.set("key4", "value4")

        assert await cache_no_ttl.get("key1") == "value1"  # Should still be there
        assert await cache_no_ttl.get("key2") is None  # Should be evicted
        assert await cache_no_ttl.get("key3") == "value3"
        assert await cache_no_ttl.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_update_existing_key(self, cache):
        """Test updating existing cache key."""
        await cache.set("key1", "value1")
        await cache.set("key1", "value2")  # Update

        result = await cache.get("key1")
        assert result == "value2"

        # Should still be only one item
        assert await cache.size() == 1

    @pytest.mark.asyncio
    async def test_delete_operations(self, cache):
        """Test cache delete operations."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        # Delete existing key
        deleted = await cache.delete("key1")
        assert deleted is True
        assert await cache.get("key1") is None

        # Delete non-existent key
        deleted = await cache.delete("nonexistent")
        assert deleted is False

        # Other key should still exist
        assert await cache.get("key2") == "value2"

    @pytest.mark.asyncio
    async def test_exists_operation(self, cache):
        """Test cache exists operation."""
        await cache.set("key1", "value1", ttl=0.1)

        assert await cache.exists("key1") is True
        assert await cache.exists("nonexistent") is False

        # Wait for expiration
        await asyncio.sleep(0.2)
        assert await cache.exists("key1") is False

    @pytest.mark.asyncio
    async def test_clear_operation(self, cache):
        """Test cache clear operation."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        assert await cache.size() == 2

        await cache.clear()

        assert await cache.size() == 0
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache):
        """Test manual cleanup of expired entries."""
        # Add items with different TTLs
        await cache.set("key1", "value1", ttl=0.1)
        await cache.set("key2", "value2", ttl=1.0)
        await cache.set("key3", "value3", ttl=0.1)

        # Wait for some to expire
        await asyncio.sleep(0.2)

        # Manual cleanup
        expired_count = await cache.cleanup_expired()

        # Should have removed 2 expired entries
        assert expired_count == 2
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"  # Should still exist
        assert await cache.get("key3") is None

    @pytest.mark.asyncio
    async def test_cache_statistics(self, cache):
        """Test cache statistics tracking."""
        # Generate some cache activity
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        # Generate hits and misses
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("nonexistent")  # Miss

        await cache.delete("key2")
        await cache.clear()

        stats = await cache.get_stats()

        assert stats.hits == 2
        assert stats.misses >= 1
        assert stats.sets >= 2
        assert stats.deletes >= 1
        assert stats.clears >= 1
        assert stats.current_size == 0

    @pytest.mark.asyncio
    async def test_entry_info(self, cache):
        """Test detailed entry information."""
        await cache.set("key1", "value1", ttl=10.0)

        info = await cache.get_entry_info("key1")

        assert info is not None
        assert info["key"] == "key1"
        assert "created_at" in info
        assert "accessed_at" in info
        assert "expires_at" in info
        assert info["access_count"] == 1
        assert info["age_seconds"] >= 0
        assert info["time_to_expiry"] <= 10.0
        assert not info["is_expired"]

        # Non-existent key
        info = await cache.get_entry_info("nonexistent")
        assert info is None

    @pytest.mark.asyncio
    async def test_size_estimation(self, cache):
        """Test cache size estimation."""
        # Test with different data types
        await cache.set("string", "hello world")
        await cache.set("number", 42)
        await cache.set("list", [1, 2, 3])
        await cache.set("dict", {"key": "value"})

        stats = await cache.get_stats()
        assert stats.memory_usage_bytes > 0

    @pytest.mark.asyncio
    async def test_background_cleanup_disabled(self, cache):
        """Test cache with background cleanup disabled."""
        # This cache has background cleanup disabled
        assert cache._cleanup_task is None

    @pytest.mark.asyncio
    async def test_background_cleanup_enabled(self):
        """Test cache with background cleanup enabled."""
        import os
        # Set secure cache key for testing
        test_key = "test_background_cleanup_" + "a" * 10  # 32 character minimum key for testing
        original_key = os.environ.get("FINOS_MCP_CACHE_SECRET")
        os.environ["FINOS_MCP_CACHE_SECRET"] = test_key

        try:
            cache: TTLCache[str, str] = TTLCache(
                max_size=5,
                default_ttl=0.1,
                cleanup_interval=0.05,
                enable_background_cleanup=True,
            )
        except:
            # Restore environment and re-raise
            if original_key:
                os.environ["FINOS_MCP_CACHE_SECRET"] = original_key
            else:
                os.environ.pop("FINOS_MCP_CACHE_SECRET", None)
            raise

        # Add expiring items
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        # Should have cleanup task running
        assert cache._cleanup_task is not None
        assert not cache._cleanup_task.done()

        # Wait for expiration and cleanup
        await asyncio.sleep(0.2)

        # Items should be cleaned up automatically
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

        await cache.close()


@pytest.mark.unit
class TestGlobalCacheAPI:
    """Test global cache API functions."""

    @pytest.mark.asyncio
    async def test_global_cache_access(self):
        """Test global cache access."""
        # Clean up any existing global cache
        await close_cache()

        # Get global cache
        cache1 = await get_cache()
        cache2 = await get_cache()

        # Should be the same instance
        assert cache1 is cache2

        # Test basic functionality
        await cache1.set("test", "value")
        result = await cache2.get("test")
        assert result == "value"

        # Cleanup
        await close_cache()

    @pytest.mark.asyncio
    async def test_cache_configuration_from_settings(self):
        """Test cache configuration from application settings."""
        with patch("finos_mcp.content.cache.get_settings") as mock_settings:
            mock_settings.return_value.cache_max_size = 100
            mock_settings.return_value.cache_ttl_seconds = 1800

            # Clean up any existing global cache
            await close_cache()

            cache = await get_cache()

            assert cache.max_size == 100
            assert cache.default_ttl == 1800

            await close_cache()


@pytest.mark.unit
class TestCachePerformance:
    """Test cache performance characteristics."""

    @pytest.mark.asyncio
    async def test_concurrent_access(self, cache_no_ttl):
        """Test concurrent cache access."""

        async def set_items(start: int, end: int) -> None:
            for i in range(start, end):
                await cache_no_ttl.set(f"key{i}", f"value{i}")

        async def get_items(start: int, end: int) -> list:
            results = []
            for i in range(start, end):
                result = await cache_no_ttl.get(f"key{i}")
                results.append(result)
            return results

        # Concurrent operations
        await asyncio.gather(
            set_items(0, 2),
            set_items(2, 3),  # Note: cache max_size is 3
            get_items(0, 2),
        )

        # Cache should handle concurrent access gracefully
        assert await cache_no_ttl.size() <= 3

    @pytest.mark.asyncio
    async def test_large_values(self, cache):
        """Test cache with large values."""
        # Create large string (1MB)
        large_value = "x" * (1024 * 1024)

        await cache.set("large", large_value)
        result = await cache.get("large")

        assert result == large_value

        # Check memory usage is tracked (compression will reduce size significantly)
        stats = await cache.get_stats()
        assert stats.memory_usage_bytes > 0  # Just verify memory usage is tracked
        # With gzip compression, 1MB of repeated 'x' compresses to ~1KB
        assert stats.memory_usage_bytes < 10000  # Verify compression is working
