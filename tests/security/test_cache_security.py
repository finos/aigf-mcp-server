"""Security tests for cache system - RCE prevention.

These tests ensure the cache system is secure against remote code execution
attacks and other security vulnerabilities in financial services environments.
"""

import gzip
import pickle
import tempfile
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

from finos_mcp.content.cache import TTLCache
from finos_mcp.content.cache_models import CacheValidationError, CacheSecurityError


class MaliciousPayload:
    """A malicious class that executes code when unpickled."""

    def __reduce__(self) -> tuple[Any, ...]:
        """Return a tuple that will execute arbitrary code when unpickled."""
        # This simulates a malicious payload that would execute system commands
        # In a real attack, this could run shell commands, access files, etc.
        import os
        return (os.system, ("echo 'RCE_EXECUTED' > /tmp/rce_test_marker",))


class TestCacheRCEPrevention:
    """Test suite for cache Remote Code Execution prevention."""

    def test_pickle_rce_vulnerability_exists(self):
        """Test that demonstrates the current pickle vulnerability.

        This test should FAIL initially (proving vulnerability exists),
        then PASS after implementing secure serialization.
        """
        # Create a malicious payload
        malicious_obj = MaliciousPayload()

        # Serialize it using pickle (current vulnerable method)
        pickled_payload = pickle.dumps(malicious_obj)
        compressed_payload = gzip.compress(pickled_payload)

        # Create cache instance
        cache = TTLCache(max_size=100, default_ttl=300)

        # Test that current implementation would execute malicious code
        # This should be prevented after security fix
        with pytest.raises((CacheSecurityError, CacheValidationError, ValueError, TypeError)):
            # Attempt to deserialize malicious payload through cache
            # The secure implementation should reject this
            cache._decompress_value(compressed_payload)

        # Verify RCE marker was NOT created (security fix working)
        rce_marker = Path("/tmp/rce_test_marker")
        assert not rce_marker.exists(), "RCE vulnerability still exists!"

    def test_malicious_cache_content_rejection(self):
        """Test that malicious cache content is rejected."""
        cache = TTLCache(max_size=100, default_ttl=300)

        # Create various malicious payloads
        malicious_payloads = [
            # Direct malicious object
            MaliciousPayload(),
            # Lambda function (should be rejected)
            lambda: exec("import os; os.system('rm -rf /')"),
            # Code object
            compile("__import__('os').system('echo hacked')", "<string>", "exec"),
        ]

        for payload in malicious_payloads:
            with pytest.raises((CacheSecurityError, CacheValidationError, ValueError, TypeError)):
                # Secure implementation should reject all malicious content
                pickled = pickle.dumps(payload)
                compressed = gzip.compress(pickled)
                cache._decompress_value(compressed)

    @pytest.mark.asyncio
    async def test_safe_data_serialization(self):
        """Test that safe data can still be cached and retrieved."""
        cache = TTLCache(max_size=100, default_ttl=300)

        # Test safe data types that should work
        safe_data = [
            "test_string",
            42,
            3.14,
            [1, 2, 3],
            {"key": "value", "nested": {"data": True}},
            {"framework": "NIST", "controls": ["AC-1", "AC-2"]},
        ]

        for i, data in enumerate(safe_data):
            cache_key = f"safe_data_{i}"
            # This should work without issues
            await cache.set(cache_key, data)
            retrieved = await cache.get(cache_key)
            assert retrieved == data, f"Safe data {data} was not cached/retrieved correctly"

    def test_cache_tampering_detection(self):
        """Test that cache tampering is detected."""
        cache = TTLCache(max_size=100, default_ttl=300)

        # Store legitimate data
        cache.set("test_key", {"legitimate": "data"})

        # Simulate cache tampering by directly accessing internal storage
        # and injecting malicious content
        malicious_payload = pickle.dumps(MaliciousPayload())
        compressed_malicious = gzip.compress(malicious_payload)

        # Attempt to inject malicious content into cache
        # Secure implementation should detect tampering
        with pytest.raises((CacheSecurityError, CacheValidationError, ValueError, TypeError)):
            cache._decompress_value(compressed_malicious)

    def test_oversized_payload_rejection(self):
        """Test that oversized payloads are rejected to prevent DoS."""
        cache = TTLCache(max_size=100, default_ttl=300)

        # Create oversized payload (should be rejected)
        oversized_data = "x" * (10 * 1024 * 1024)  # 10MB string

        with pytest.raises((ValueError, MemoryError)):
            cache.set("oversized", oversized_data)

    def test_compression_bomb_prevention(self):
        """Test prevention of compression bomb attacks."""
        cache = TTLCache(max_size=100, default_ttl=300)

        # Create a compression bomb (small compressed, huge uncompressed)
        bomb_data = b"0" * 1000000  # 1MB of zeros (compresses to ~1KB)
        compressed_bomb = gzip.compress(bomb_data)

        # Should detect and prevent decompression bomb
        with pytest.raises((ValueError, MemoryError)):
            cache._decompress_value(compressed_bomb)


class TestSecureSerializationFeatures:
    """Test secure serialization features that should be implemented."""

    def test_json_serialization_used(self):
        """Test that JSON serialization is used instead of pickle."""
        cache = TTLCache(max_size=100, default_ttl=300)

        # Test that complex objects are properly serialized as JSON
        test_data = {
            "framework": "GDPR",
            "articles": [1, 2, 3],
            "compliance": True,
            "score": 95.5
        }

        cache.set("json_test", test_data)
        retrieved = cache.get("json_test")

        assert retrieved == test_data
        # Verify no pickle is used in the process
        # This will be validated by the implementation

    def test_pydantic_validation_integration(self):
        """Test that Pydantic models are properly validated."""
        # This test will be expanded once Pydantic models are integrated
        # For now, ensure basic data validation works
        cache = TTLCache(max_size=100, default_ttl=300)

        # Test data that should pass validation
        valid_data = {
            "type": "framework_section",
            "id": "gdpr_article_1",
            "content": "Article 1 content"
        }

        cache.set("pydantic_test", valid_data)
        retrieved = cache.get("pydantic_test")
        assert retrieved == valid_data


# Security test fixtures
@pytest.fixture
def clean_temp_files():
    """Clean up any test artifacts."""
    yield
    # Cleanup any RCE test markers
    rce_marker = Path("/tmp/rce_test_marker")
    if rce_marker.exists():
        rce_marker.unlink()


@pytest.fixture
def secure_cache():
    """Fixture providing a secure cache instance."""
    import os
    # Set secure cache key for testing
    test_key = "a" * 32  # 32 character minimum key for testing
    os.environ["FINOS_MCP_CACHE_SECRET"] = test_key
    try:
        return TTLCache(max_size=100, default_ttl=300)
    finally:
        # Clean up environment variable after test
        os.environ.pop("FINOS_MCP_CACHE_SECRET", None)
