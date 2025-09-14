"""
Tests for performance optimization patterns.
Request coalescing, background tasks, and smart caching for MCP server.
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from finos_mcp.internal.performance_optimizations import (
    BackgroundTaskManager,
    CacheEntry,
    RequestCoalescer,
    SmartCache,
)


class TestRequestCoalescer:
    """Test request coalescing functionality."""

    @pytest.mark.asyncio
    async def test_coalescer_creation(self):
        """Test creating request coalescer."""
        coalescer = RequestCoalescer()
        assert coalescer is not None
        assert coalescer.max_batch_size == 10  # Default batch size

    @pytest.mark.asyncio
    async def test_single_request_handling(self):
        """Test handling single request."""
        coalescer = RequestCoalescer()
        handler = AsyncMock(return_value="result")

        result = await coalescer.coalesce("test_key", {"query": "test"}, handler)

        assert result == "result"
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_request_coalescing(self):
        """Test coalescing duplicate requests."""
        coalescer = RequestCoalescer()
        handler = AsyncMock(return_value="shared_result")

        # Start multiple identical requests concurrently
        tasks = [
            coalescer.coalesce("same_key", {"query": "test"}, handler),
            coalescer.coalesce("same_key", {"query": "test"}, handler),
            coalescer.coalesce("same_key", {"query": "test"}, handler)
        ]

        results = await asyncio.gather(*tasks)

        # All should get same result
        assert all(r == "shared_result" for r in results)
        # Handler should only be called once
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_keys_no_coalescing(self):
        """Test that different keys don't get coalesced."""
        coalescer = RequestCoalescer()
        handler = AsyncMock(side_effect=lambda req: f"result_for_{req['query']}")

        tasks = [
            coalescer.coalesce("key1", {"query": "test1"}, handler),
            coalescer.coalesce("key2", {"query": "test2"}, handler),
            coalescer.coalesce("key3", {"query": "test3"}, handler)
        ]

        results = await asyncio.gather(*tasks)

        assert results[0] == "result_for_test1"
        assert results[1] == "result_for_test2"
        assert results[2] == "result_for_test3"
        assert handler.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch processing when enabled."""
        coalescer = RequestCoalescer(max_batch_size=3, batch_timeout=0.1)
        handler = AsyncMock(return_value=["result1", "result2", "result3"])

        tasks = [
            coalescer.coalesce_batch("search", {"query": "test1"}, handler),
            coalescer.coalesce_batch("search", {"query": "test2"}, handler),
            coalescer.coalesce_batch("search", {"query": "test3"}, handler)
        ]

        results = await asyncio.gather(*tasks)

        assert results == ["result1", "result2", "result3"]
        # Batch handler called once with all requests
        handler.assert_called_once_with([
            {"query": "test1"},
            {"query": "test2"},
            {"query": "test3"}
        ])

    @pytest.mark.asyncio
    async def test_partial_batch_timeout(self):
        """Test partial batch processing with timeout."""
        coalescer = RequestCoalescer(max_batch_size=5, batch_timeout=0.05)
        handler = AsyncMock(return_value=["result1", "result2"])

        # Start batch with only 2 items
        start_time = time.time()
        tasks = [
            coalescer.coalesce_batch("search", {"query": "test1"}, handler),
            coalescer.coalesce_batch("search", {"query": "test2"}, handler)
        ]

        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        assert results == ["result1", "result2"]
        assert elapsed >= 0.05  # Should wait for timeout
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_in_coalescing(self):
        """Test error handling in request coalescing."""
        coalescer = RequestCoalescer()
        handler = AsyncMock(side_effect=ValueError("Test error"))

        with pytest.raises(ValueError, match="Test error"):
            await coalescer.coalesce("error_key", {"query": "test"}, handler)

        # Subsequent requests should also get the error
        with pytest.raises(ValueError, match="Test error"):
            await coalescer.coalesce("error_key", {"query": "test"}, handler)

    def test_key_generation(self):
        """Test request key generation."""
        coalescer = RequestCoalescer()

        key1 = coalescer._generate_key("search", {"query": "test", "limit": 10})
        key2 = coalescer._generate_key("search", {"limit": 10, "query": "test"})
        key3 = coalescer._generate_key("search", {"query": "different"})

        assert key1 == key2  # Same content, different order
        assert key1 != key3  # Different content


class TestSmartCache:
    """Test smart caching functionality."""

    def test_cache_creation(self):
        """Test creating smart cache."""
        cache = SmartCache(max_size=100, default_ttl=300)
        assert cache.max_size == 100
        assert cache.default_ttl == 300
        assert len(cache._cache) == 0

    def test_basic_get_set(self):
        """Test basic cache get/set operations."""
        cache = SmartCache()

        # Cache miss
        assert cache.get("key1") is None

        # Set value
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_ttl_expiration(self):
        """Test TTL-based cache expiration."""
        cache = SmartCache(default_ttl=0.1)

        cache.set("expiring_key", "value")
        assert cache.get("expiring_key") == "value"

        # Wait for expiration
        time.sleep(0.15)
        assert cache.get("expiring_key") is None

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = SmartCache(max_size=3)

        # Fill cache to capacity
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key1 to make it recently used
        cache.get("key1")

        # Add new item, should evict key2 (least recently used)
        cache.set("key4", "value4")

        assert cache.get("key1") == "value1"  # Still there
        assert cache.get("key2") is None      # Evicted
        assert cache.get("key3") == "value3"  # Still there
        assert cache.get("key4") == "value4"  # New item

    def test_custom_ttl(self):
        """Test custom TTL for individual entries."""
        cache = SmartCache(default_ttl=10)

        # Set with custom short TTL
        cache.set("short_key", "value", ttl=0.1)
        # Set with default TTL
        cache.set("long_key", "value")

        assert cache.get("short_key") == "value"
        assert cache.get("long_key") == "value"

        # Wait for short TTL expiration
        time.sleep(0.15)

        assert cache.get("short_key") is None   # Expired
        assert cache.get("long_key") == "value" # Still valid

    def test_cache_warming(self):
        """Test cache warming functionality."""
        cache = SmartCache()
        warmer = AsyncMock(return_value="warmed_value")

        # Warm cache
        asyncio.run(cache.warm("warm_key", warmer))

        # Should be in cache now
        assert cache.get("warm_key") == "warmed_value"
        warmer.assert_called_once_with("warm_key")

    def test_stats_tracking(self):
        """Test cache statistics tracking."""
        cache = SmartCache()

        # Initially empty stats
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0

        # Generate some hits and misses
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2/3

    def test_clear_cache(self):
        """Test cache clearing."""
        cache = SmartCache()

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert len(cache._cache) == 2

        cache.clear()
        assert len(cache._cache) == 0
        assert cache.get("key1") is None

    def test_cache_entry_structure(self):
        """Test cache entry data structure."""
        entry = CacheEntry(value="test", expires_at=time.time() + 100)

        assert entry.value == "test"
        assert entry.expires_at > time.time()
        assert not entry.is_expired()

        # Test expired entry
        expired_entry = CacheEntry(value="expired", expires_at=time.time() - 1)
        assert expired_entry.is_expired()


class TestBackgroundTaskManager:
    """Test background task management."""

    def test_manager_creation(self):
        """Test creating background task manager."""
        manager = BackgroundTaskManager(max_concurrent_tasks=5)
        assert manager.max_concurrent_tasks == 5
        assert len(manager._tasks) == 0

    @pytest.mark.asyncio
    async def test_submit_background_task(self):
        """Test submitting background tasks."""
        manager = BackgroundTaskManager()
        results = []

        async def background_work(data):
            results.append(f"processed_{data}")
            return f"result_{data}"

        # Submit task
        task_id = await manager.submit_task("test_task", background_work, "data1")
        assert task_id is not None

        # Wait a bit for task to complete
        await asyncio.sleep(0.01)

        assert "processed_data1" in results

    @pytest.mark.asyncio
    async def test_task_result_retrieval(self):
        """Test retrieving task results."""
        manager = BackgroundTaskManager()

        async def simple_task(x):
            return x * 2

        task_id = await manager.submit_task("multiply", simple_task, 5)

        # Wait for completion
        await asyncio.sleep(0.01)

        result = await manager.get_task_result(task_id)
        assert result == 10

    @pytest.mark.asyncio
    async def test_task_status_tracking(self):
        """Test task status tracking."""
        manager = BackgroundTaskManager()

        async def slow_task():
            await asyncio.sleep(0.05)
            return "done"

        task_id = await manager.submit_task("slow_work", slow_task)

        # Should be running
        status = manager.get_task_status(task_id)
        assert status in ["pending", "running"]

        # Wait for completion
        await asyncio.sleep(0.1)

        status = manager.get_task_status(task_id)
        assert status == "completed"

    @pytest.mark.asyncio
    async def test_concurrent_task_limit(self):
        """Test concurrent task limiting."""
        manager = BackgroundTaskManager(max_concurrent_tasks=2)
        running_tasks = []

        async def blocking_task(task_id):
            running_tasks.append(task_id)
            await asyncio.sleep(0.1)
            running_tasks.remove(task_id)
            return f"completed_{task_id}"

        # Submit 3 tasks (limit is 2)
        task_ids = []
        for i in range(3):
            task_id = await manager.submit_task(f"task_{i}", blocking_task, i)
            task_ids.append(task_id)

        # Check that at most 2 are running concurrently
        await asyncio.sleep(0.02)
        assert len(running_tasks) <= 2

        # Wait for all to complete
        await asyncio.sleep(0.2)
        assert len(running_tasks) == 0

    @pytest.mark.asyncio
    async def test_task_error_handling(self):
        """Test error handling in background tasks."""
        manager = BackgroundTaskManager()

        async def failing_task():
            raise ValueError("Task failed")

        task_id = await manager.submit_task("fail_task", failing_task)

        # Wait for task to fail
        await asyncio.sleep(0.01)

        status = manager.get_task_status(task_id)
        assert status == "failed"

        # Should be able to get error details
        with pytest.raises(ValueError, match="Task failed"):
            await manager.get_task_result(task_id)

    @pytest.mark.asyncio
    async def test_task_cleanup(self):
        """Test automatic task cleanup."""
        manager = BackgroundTaskManager(task_cleanup_interval=0.05)

        async def quick_task():
            return "done"

        task_id = await manager.submit_task("cleanup_test", quick_task)

        # Task should be in manager
        assert task_id in manager._tasks

        # Wait for cleanup
        await asyncio.sleep(0.1)

        # Task should be cleaned up
        assert task_id not in manager._tasks

    def test_task_priority(self):
        """Test task priority handling."""
        manager = BackgroundTaskManager()

        # Higher priority tasks should be processed first
        high_priority = manager._create_task_info("high", priority=1)
        low_priority = manager._create_task_info("low", priority=3)

        assert high_priority.priority < low_priority.priority
        assert high_priority < low_priority  # For priority queue


class TestIntegration:
    """Test integration between optimization components."""

    @pytest.mark.asyncio
    async def test_cache_with_coalescing(self):
        """Test smart cache integrated with request coalescing."""
        cache = SmartCache(default_ttl=1.0)
        coalescer = RequestCoalescer()

        async def cached_handler(request):
            key = f"search_{request['query']}"

            # Check cache first
            cached = cache.get(key)
            if cached:
                return cached

            # Expensive operation
            result = f"result_for_{request['query']}"
            cache.set(key, result)
            return result

        # First request - cache miss
        result1 = await coalescer.coalesce("test1", {"query": "python"}, cached_handler)
        assert result1 == "result_for_python"

        # Second identical request - should use cache
        result2 = await coalescer.coalesce("test2", {"query": "python"}, cached_handler)
        assert result2 == "result_for_python"

        # Cache stats should show hit
        stats = cache.get_stats()
        assert stats["hits"] >= 1

    @pytest.mark.asyncio
    async def test_background_tasks_with_caching(self):
        """Test background tasks updating cache."""
        cache = SmartCache()
        manager = BackgroundTaskManager()

        async def cache_warming_task(key, value):
            # Simulate expensive computation
            await asyncio.sleep(0.01)
            cache.set(key, f"warmed_{value}")
            return f"warmed_{value}"

        # Submit cache warming task
        await manager.submit_task(
            "warm_cache",
            cache_warming_task,
            "search_results",
            "expensive_data"
        )

        # Wait for task completion
        await asyncio.sleep(0.02)

        # Cache should be warmed
        assert cache.get("search_results") == "warmed_expensive_data"

    @pytest.mark.asyncio
    async def test_full_optimization_pipeline(self):
        """Test complete optimization pipeline."""
        cache = SmartCache(max_size=100, default_ttl=5.0)
        coalescer = RequestCoalescer(max_batch_size=3)
        manager = BackgroundTaskManager()

        call_count = 0

        async def expensive_search(requests):
            nonlocal call_count
            call_count += 1

            # Simulate expensive batch operation
            await asyncio.sleep(0.01)
            results = []

            for req in requests:
                result = f"search_result_for_{req['query']}"
                # Cache individual results
                cache.set(f"search_{req['query']}", result)
                results.append(result)

                # Submit background analytics task
                await manager.submit_task(
                    "analytics",
                    lambda q=req['query']: asyncio.sleep(0.001)  # Mock analytics
                )

            return results

        # Submit multiple search requests
        tasks = []
        for i in range(5):
            task = coalescer.coalesce_batch(
                "search",
                {"query": f"test{i % 3}"},  # Some duplicates
                expensive_search
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Should have results
        assert len(results) == 5

        # Expensive operation called less than 5 times due to coalescing/caching
        assert call_count <= 3

        # Cache should have entries
        cache_stats = cache.get_stats()
        assert cache_stats["entries"] > 0

        # Background tasks should be submitted
        await asyncio.sleep(0.05)  # Let background tasks complete

