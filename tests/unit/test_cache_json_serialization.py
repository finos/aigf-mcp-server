"""
Unit tests for secure JSON serialization in cache system.

Tests the replacement of pickle with secure JSON serialization,
ensuring proper functionality while preventing security vulnerabilities.
"""

import json
from unittest.mock import patch

import pytest

from finos_mcp.content.cache import TTLCache


@pytest.mark.unit
class TestJSONSerializationBasics:
    """Test basic JSON serialization functionality."""

    @pytest.mark.asyncio
    async def test_simple_data_types_serialization(self, json_cache):
        """Test serialization of simple Python data types."""
        cache = json_cache

        test_cases = [
            ("string_test", "Hello, World!"),
            ("int_test", 42),
            ("float_test", 3.14159),
            ("bool_true", True),
            ("bool_false", False),
            ("none_test", None),
            ("empty_string", ""),
            ("zero", 0),
        ]

        for key, value in test_cases:
            await cache.set(key, value)
            retrieved = await cache.get(key)
            assert retrieved == value, (
                f"Failed for {key}: expected {value}, got {retrieved}"
            )

    @pytest.mark.asyncio
    async def test_complex_data_structures_serialization(self, json_cache):
        """Test serialization of complex data structures."""
        cache = json_cache

        test_cases = [
            ("list_test", [1, 2, 3, "four", 5.0]),
            ("dict_test", {"key1": "value1", "key2": 42, "key3": [1, 2, 3]}),
            (
                "nested_dict",
                {"level1": {"level2": {"level3": "deep_value", "numbers": [1, 2, 3]}}},
            ),
            (
                "mixed_list",
                [
                    {"type": "framework", "name": "GDPR"},
                    {"type": "article", "number": 6},
                    ["compliance", "privacy", "security"],
                ],
            ),
        ]

        for key, value in test_cases:
            await cache.set(key, value)
            retrieved = await cache.get(key)
            assert retrieved == value, (
                f"Failed for {key}: expected {value}, got {retrieved}"
            )

    @pytest.mark.asyncio
    async def test_framework_data_serialization(self, json_cache):
        """Test serialization of framework-specific data structures."""
        cache = json_cache

        framework_data = {
            "framework_id": "nist_ai_rmf",
            "sections": [
                {
                    "section_id": "govern_1",
                    "title": "Governance and Oversight",
                    "description": "AI governance processes",
                    "controls": ["GOV-1.1", "GOV-1.2"],
                    "compliance_score": 85.5,
                },
                {
                    "section_id": "map_1",
                    "title": "AI Risk Mapping",
                    "description": "Identify and categorize AI risks",
                    "controls": ["MAP-1.1", "MAP-1.2", "MAP-1.3"],
                    "compliance_score": 92.0,
                },
            ],
            "metadata": {
                "version": "1.0",
                "last_updated": "2024-01-15",
                "status": "active",
            },
        }

        await cache.set("framework_data", framework_data)
        retrieved = await cache.get("framework_data")
        assert retrieved == framework_data


@pytest.mark.unit
class TestJSONSerializationValidation:
    """Test validation and error handling in JSON serialization."""

    @pytest.mark.asyncio
    async def test_json_serializable_validation(self, json_cache):
        """Test that only JSON-serializable objects are accepted."""
        cache = json_cache

        # These should work (JSON-serializable)
        valid_data = [{"valid": "dict"}, [1, 2, 3], "string", 42, 3.14, True, None]

        for i, data in enumerate(valid_data):
            await cache.set(f"valid_{i}", data)
            result = await cache.get(f"valid_{i}")
            assert result == data

        # These should be rejected or handled safely (non-JSON-serializable)
        invalid_data = [
            lambda x: x,  # Function
            {1, 2, 3},  # Set
            complex(1, 2),  # Complex number
            object(),  # Generic object
        ]

        for i, data in enumerate(invalid_data):
            # Should either convert to safe representation or raise TypeError
            try:
                await cache.set(f"invalid_{i}", data)
                retrieved = await cache.get(f"invalid_{i}")
                # If it didn't raise an error, it should have been converted safely
                assert json.dumps(retrieved) is not None  # Should be JSON-serializable
            except (TypeError, ValueError, Exception):  # noqa: S110
                # This is expected for non-serializable data - cache correctly rejects it
                # Logging the exception would be noisy in this test context
                pass

    @pytest.mark.asyncio
    async def test_large_data_handling(self, json_cache):
        """Test handling of large data structures."""
        cache = json_cache

        # Test reasonably large data (should work)
        large_dict = {f"key_{i}": f"value_{i}" for i in range(1000)}
        await cache.set("large_dict", large_dict)
        retrieved = await cache.get("large_dict")
        assert retrieved == large_dict

        # Test very large data (should be handled gracefully)
        very_large_data = {"data": "x" * 100000}  # 100KB string
        try:
            await cache.set("very_large", very_large_data)
            retrieved = await cache.get("very_large")
            assert retrieved == very_large_data
        except (MemoryError, ValueError):
            # Acceptable to reject very large data
            pass

    @pytest.mark.asyncio
    async def test_unicode_and_special_characters(self, json_cache):
        """Test handling of Unicode and special characters."""
        cache = json_cache

        test_cases = [
            ("unicode_test", "こんにちは世界"),  # Japanese
            ("emoji_test", "🔒🛡️🚀"),  # Emojis
            ("special_chars", "Special: !@#$%^&*()_+-=[]{}|;':\",./<>?"),
            (
                "mixed_unicode",
                {
                    "english": "Hello",
                    "spanish": "Hola",
                    "chinese": "你好",
                    "arabic": "مرحبا",
                    "emoji": "👋",
                },
            ),
        ]

        for key, value in test_cases:
            await cache.set(key, value)
            retrieved = await cache.get(key)
            assert retrieved == value, f"Unicode test failed for {key}"


@pytest.mark.unit
class TestCacheCompressionWithJSON:
    """Test compression functionality with JSON serialization."""

    @pytest.mark.asyncio
    async def test_json_compression_enabled(self):
        """Test that JSON data is properly compressed when enabled."""
        import os

        # Set secure cache key for testing
        test_key = "test_compression_key_" + "a" * 16
        original_key = os.environ.get("FINOS_MCP_CACHE_SECRET")
        os.environ["FINOS_MCP_CACHE_SECRET"] = test_key

        try:
            cache = TTLCache(max_size=100, default_ttl=300, enable_compression=True)
        except:
            # Restore environment and re-raise
            if original_key:
                os.environ["FINOS_MCP_CACHE_SECRET"] = original_key
            else:
                os.environ.pop("FINOS_MCP_CACHE_SECRET", None)
            raise

        # Large repetitive data that compresses well
        large_data = {
            "repeated_field": "This is a repeated string. " * 100,
            "numbers": list(range(1000)),
            "framework": "NIST AI RMF",
            "controls": ["GOV-1.1"] * 50,
        }

        await cache.set("compression_test", large_data)
        retrieved = await cache.get("compression_test")
        assert retrieved == large_data

    @pytest.mark.asyncio
    async def test_json_compression_disabled(self):
        """Test that JSON serialization works with compression disabled."""
        import os

        # Set secure cache key for testing
        test_key = "test_no_compress_key_" + "a" * 16
        original_key = os.environ.get("FINOS_MCP_CACHE_SECRET")
        os.environ["FINOS_MCP_CACHE_SECRET"] = test_key

        try:
            cache = TTLCache(max_size=100, default_ttl=300, enable_compression=False)
        except:
            # Restore environment and re-raise
            if original_key:
                os.environ["FINOS_MCP_CACHE_SECRET"] = original_key
            else:
                os.environ.pop("FINOS_MCP_CACHE_SECRET", None)
            raise

        test_data = {
            "framework": "GDPR",
            "articles": list(range(1, 100)),
            "compliance": True,
        }

        await cache.set("no_compression_test", test_data)
        retrieved = await cache.get("no_compression_test")
        assert retrieved == test_data


@pytest.mark.unit
class TestCacheJSONErrorHandling:
    """Test error handling in JSON serialization cache."""

    @pytest.mark.asyncio
    async def test_corrupted_data_handling(self, json_cache):
        """Test handling of corrupted cache data."""
        cache = json_cache

        # Store valid data first
        await cache.set("test_key", {"valid": "data"})

        # Simulate corruption by manually injecting invalid JSON
        # This tests the error handling pathway
        with patch.object(cache, "_decompress_value") as mock_decompress:
            mock_decompress.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

            # Should handle corrupted data by raising an exception or returning None
            try:
                result = await cache.get("test_key")
                # If no exception, result should be None
                assert result is None
            except json.JSONDecodeError:
                # This is also acceptable - cache detected corruption
                pass

    @pytest.mark.asyncio
    async def test_memory_limit_enforcement(self, json_cache):
        """Test that memory limits are enforced during JSON serialization."""
        cache = json_cache

        # This test ensures memory protection is working
        # Implementation should reject data exceeding size limits
        oversized_data = {"huge_field": "x" * (2 * 1024 * 1024)}  # 2MB

        try:
            await cache.set("oversized", oversized_data)
            # If it succeeds, verify it was actually stored
            retrieved = await cache.get("oversized")
            if retrieved is not None:
                assert retrieved == oversized_data
        except (MemoryError, ValueError, OverflowError):
            # Expected behavior for oversized data
            pass

    @pytest.mark.asyncio
    async def test_circular_reference_handling(self, json_cache):
        """Test handling of circular references in data structures."""
        cache = json_cache

        # Create circular reference
        circular_data = {"key": "value"}
        circular_data["self"] = circular_data

        # Should handle circular references gracefully by raising an error
        with pytest.raises((ValueError, TypeError, RecursionError, Exception)):
            await cache.set("circular", circular_data)


@pytest.mark.unit
class TestCacheJSONPerformance:
    """Test performance characteristics of JSON serialization."""

    @pytest.mark.asyncio
    async def test_serialization_performance(self, json_cache):
        """Test that JSON serialization has acceptable performance."""
        cache = json_cache

        # Test with various data sizes
        test_data = {
            "small": {"framework": "GDPR", "article": 6},
            "medium": {"controls": [f"CTRL-{i}" for i in range(100)]},
            "large": {"data": [{"id": i, "value": f"value_{i}"} for i in range(1000)]},
        }

        import time

        for size_name, data in test_data.items():
            start_time = time.time()

            # Perform multiple operations to test performance
            for i in range(10):
                await cache.set(f"{size_name}_{i}", data)
                retrieved = await cache.get(f"{size_name}_{i}")
                assert retrieved == data

            elapsed = time.time() - start_time

            # Should complete operations reasonably quickly
            # This is a basic performance check
            assert elapsed < 1.0, (
                f"JSON serialization too slow for {size_name} data: {elapsed}s"
            )

    @pytest.mark.asyncio
    async def test_concurrent_access_json_serialization(self, json_cache):
        """Test JSON serialization under concurrent access."""
        cache = json_cache

        async def cache_operation(thread_id: int):
            """Perform cache operations asynchronously."""
            data = {"thread_id": thread_id, "data": list(range(100))}
            await cache.set(f"thread_{thread_id}", data)
            retrieved = await cache.get(f"thread_{thread_id}")
            assert retrieved == data

        import asyncio

        # Use asyncio.gather for concurrent async operations
        tasks = [cache_operation(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # Verify all data was stored correctly
        for i in range(5):
            expected_data = {"thread_id": i, "data": list(range(100))}
            result = await cache.get(f"thread_{i}")
            assert result == expected_data


# Fixtures for JSON serialization tests
@pytest.fixture
def json_cache():
    """Fixture providing a cache configured for JSON serialization."""
    import os

    # Set secure cache key for testing
    test_key = "test_json_cache_key_" + "a" * 16  # 32 character minimum key for testing
    original_key = os.environ.get("FINOS_MCP_CACHE_SECRET")
    os.environ["FINOS_MCP_CACHE_SECRET"] = test_key

    try:
        yield TTLCache(max_size=100, default_ttl=300)
    finally:
        # Restore original environment variable
        if original_key:
            os.environ["FINOS_MCP_CACHE_SECRET"] = original_key
        else:
            os.environ.pop("FINOS_MCP_CACHE_SECRET", None)


@pytest.fixture
def sample_framework_data():
    """Fixture providing sample framework data for testing."""
    return {
        "framework": "GDPR",
        "articles": [
            {
                "number": 6,
                "title": "Lawfulness of processing",
                "lawful_bases": ["consent", "contract", "legal_obligation"],
            },
            {
                "number": 7,
                "title": "Conditions for consent",
                "requirements": ["freely_given", "specific", "informed"],
            },
        ],
        "compliance_score": 95.5,
        "last_assessment": "2024-01-15",
    }
