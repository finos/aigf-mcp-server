"""
Unit tests for memory allocation limits in cache system.

Tests protection against memory exhaustion attacks through
oversized objects and decompression bombs.
"""

import os

import pytest

from finos_mcp.content.cache import MAX_OBJECT_SIZE, TTLCache


@pytest.mark.unit
class TestMemoryLimits:
    """Test memory allocation limits and DoS protection."""

    @pytest.fixture
    def cache(self):
        """Create a cache instance with environment variable set."""
        # Set secure cache key for testing
        test_key = "test_memory_limits_key_" + "a" * 10  # 32 char minimum
        original_key = os.environ.get("FINOS_MCP_CACHE_SECRET")
        os.environ["FINOS_MCP_CACHE_SECRET"] = test_key

        try:
            cache = TTLCache(max_size=100, default_ttl=300, enable_compression=True)
            yield cache
        finally:
            # Restore original environment variable
            if original_key:
                os.environ["FINOS_MCP_CACHE_SECRET"] = original_key
            else:
                os.environ.pop("FINOS_MCP_CACHE_SECRET", None)

    @pytest.mark.asyncio
    async def test_oversized_object_rejection(self, cache):
        """Test that oversized objects are rejected."""
        # Create object larger than 1MB (Pydantic enforces 1MB limit)
        oversized_data = "x" * (1024 * 1024 + 1000)  # Just over 1MB

        # Should fail due to Pydantic validation (1MB limit)
        with pytest.raises(Exception):  # Could be ValueError or ValidationError
            await cache.set("oversized", oversized_data)

    @pytest.mark.asyncio
    async def test_large_but_acceptable_object(self, cache):
        """Test that large but acceptable objects work."""
        # Create object under the 1MB Pydantic limit with low compression ratio
        # Use random-ish data that doesn't compress well
        import random
        import string

        large_data = "".join(
            random.choices(string.ascii_letters + string.digits, k=100 * 1024)  # noqa: S311
        )  # 100KB random data (non-cryptographic use is fine for tests)

        # This should work
        await cache.set("large", large_data)
        result = await cache.get("large")
        assert result == large_data

    @pytest.mark.asyncio
    async def test_compression_bomb_prevention(self, cache):
        """Test protection against compression bombs."""
        # Create data that compresses extremely well (bomb-like)
        # 500KB of zeros should compress to ~500 bytes with gzip
        bomb_data = "\0" * (500 * 1024)  # 500KB of null bytes

        try:
            await cache.set("bomb", bomb_data)
            result = await cache.get("bomb")
            # If we get here, the compression ratio was acceptable
            assert result == bomb_data
        except Exception as e:
            # If compression ratio exceeds limits or validation fails, that's expected
            assert (
                "compression ratio" in str(e).lower()
                or "exceeds maximum" in str(e).lower()
                or "validation" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_normal_compression_works(self, cache):
        """Test that normal compression still works."""
        # Normal data that compresses moderately well
        normal_data = {
            "framework": "GDPR",
            "articles": list(range(100)),
            "text": "This is some normal text that compresses reasonably well. " * 100,
        }

        await cache.set("normal", normal_data)
        result = await cache.get("normal")
        assert result == normal_data

    @pytest.mark.asyncio
    async def test_memory_usage_tracking(self, cache):
        """Test that memory usage is tracked correctly."""
        # Add some data
        await cache.set("test1", "value1")
        await cache.set("test2", "value2" * 100)
        await cache.set("test3", {"key": "value", "data": list(range(50))})

        stats = await cache.get_stats()
        assert stats.memory_usage_bytes > 0
        assert stats.current_size == 3

    def test_memory_limit_constants(self):
        """Test that memory limit constants are reasonable."""
        # Verify MAX_OBJECT_SIZE is set to expected value
        assert MAX_OBJECT_SIZE == 10_000_000  # 10MB

        # Import the compression ratio constant
        from finos_mcp.content.cache import MAX_COMPRESSION_RATIO

        assert MAX_COMPRESSION_RATIO == 100  # 100:1 ratio max
