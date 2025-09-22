"""
Security tests for request size limiting and DoS protection.

Tests to ensure the server can handle resource-intensive requests without
allowing denial of service attacks through oversized requests.
"""

import pytest
from unittest.mock import patch, MagicMock
import asyncio

from src.finos_mcp.security.request_validator import RequestSizeValidator


class TestRequestSizeLimits:
    """Test request size validation and DoS protection."""

    @pytest.fixture
    def request_validator(self):
        """Create RequestSizeValidator instance for testing."""
        return RequestSizeValidator(
            max_tool_result_size=5_000_000,  # 5MB
            max_resource_size=1_000_000,     # 1MB
            max_request_params_size=100_000  # 100KB
        )

    def test_validates_tool_result_size_limits(self, request_validator):
        """Test that tool results exceeding size limits are rejected."""
        # Simulate a 6MB result (exceeds 5MB limit)
        large_result = "x" * 6_000_000

        with pytest.raises(ValueError, match="Tool result exceeds size limit"):
            request_validator.validate_tool_result_size([large_result])

    def test_validates_resource_size_limits(self, request_validator):
        """Test that resources exceeding size limits are rejected."""
        # Simulate a 2MB resource (exceeds 1MB limit)
        large_resource = "x" * 2_000_000

        with pytest.raises(ValueError, match="Resource content exceeds size limit"):
            request_validator.validate_resource_size(large_resource)

    def test_validates_request_parameters_size(self, request_validator):
        """Test that request parameters exceeding size limits are rejected."""
        # Simulate 200KB parameters (exceeds 100KB limit)
        large_params = {"data": "x" * 200_000}

        with pytest.raises(ValueError, match="Request parameters exceed size limit"):
            request_validator.validate_request_params_size(large_params)

    def test_allows_normal_sized_requests(self, request_validator):
        """Test that normal-sized requests are allowed through."""
        # Normal sizes that should pass
        normal_result = ["small result"]
        normal_resource = "small resource content"
        normal_params = {"query": "normal query"}

        # These should not raise exceptions
        request_validator.validate_tool_result_size(normal_result)
        request_validator.validate_resource_size(normal_resource)
        request_validator.validate_request_params_size(normal_params)

    def test_calculates_content_size_accurately(self, request_validator):
        """Test that content size calculation is accurate for various data types."""
        # Test with list of strings
        result_list = ["abc", "def", "ghi"]
        size = request_validator._calculate_content_size(result_list)
        assert size == 9  # 3 + 3 + 3

        # Test with nested structures
        nested_data = {"key": ["value1", "value2"]}
        size = request_validator._calculate_content_size(nested_data)
        assert size > 0

    def test_handles_edge_cases(self, request_validator):
        """Test handling of edge cases in size validation."""
        # Empty content
        request_validator.validate_tool_result_size([])
        request_validator.validate_resource_size("")
        request_validator.validate_request_params_size({})

        # None values
        request_validator.validate_resource_size(None)


class TestDoSProtection:
    """Test denial of service protection mechanisms."""

    @pytest.fixture
    def dos_protector(self):
        """Create DoS protection instance."""
        from src.finos_mcp.security.request_validator import DoSProtector
        return DoSProtector(
            max_requests_per_minute=60,
            max_concurrent_requests=10,
            request_timeout_seconds=30
        )

    def test_prevents_request_flooding(self, dos_protector):
        """Test that rapid request flooding is prevented."""
        client_id = "test_client"

        # Simulate 61 requests in quick succession (exceeds 60/minute limit)
        for i in range(61):
            if i < 60:
                # First 60 should be allowed
                assert dos_protector.check_rate_limit(client_id) is True
            else:
                # 61st request should be blocked
                assert dos_protector.check_rate_limit(client_id) is False

    def test_prevents_concurrent_request_overload(self, dos_protector):
        """Test that too many concurrent requests are prevented."""
        client_id = "test_client"

        # Start 10 concurrent requests (at the limit)
        for i in range(10):
            dos_protector.start_request(client_id)

        # 11th concurrent request should be blocked
        with pytest.raises(ValueError, match="Too many concurrent requests"):
            dos_protector.start_request(client_id)

    def test_releases_concurrent_slots_when_requests_complete(self, dos_protector):
        """Test that concurrent request slots are released when requests complete."""
        client_id = "test_client"

        # Start and complete requests
        for i in range(5):
            request_id = dos_protector.start_request(client_id)
            dos_protector.complete_request(client_id, request_id)

        # Should still be able to start new requests
        request_id = dos_protector.start_request(client_id)
        assert request_id is not None

    async def test_request_timeout_protection(self, dos_protector):
        """Test that long-running requests are timed out."""
        client_id = "test_client"

        # Start a request that will timeout
        request_id = dos_protector.start_request(client_id)
        start_time = dos_protector._get_current_time()

        # Mock timeout scenario
        with patch.object(dos_protector, '_get_current_time') as mock_time:
            # Simulate 31 seconds have passed (exceeds 30s timeout)
            mock_time.return_value = start_time + 31

            # Check if request is considered timed out
            assert dos_protector._is_request_timed_out(client_id, request_id) is True

    def test_different_clients_have_separate_limits(self, dos_protector):
        """Test that different clients have separate rate limiting."""
        client1 = "client_1"
        client2 = "client_2"

        # Each client should be able to make their full quota
        for i in range(60):
            assert dos_protector.check_rate_limit(client1) is True
            assert dos_protector.check_rate_limit(client2) is True


class TestResourceExhaustion:
    """Test protection against resource exhaustion attacks."""

    def test_prevents_memory_exhaustion_through_large_requests(self):
        """Test that extremely large requests don't exhaust server memory."""
        validator = RequestSizeValidator(
            max_tool_result_size=1_000_000,  # 1MB limit
            max_resource_size=500_000,       # 500KB limit
            max_request_params_size=50_000   # 50KB limit
        )

        # Simulate an attack with extremely large data
        attack_data = "x" * 10_000_000  # 10MB attack payload

        # All of these should be rejected before consuming excessive memory
        with pytest.raises(ValueError):
            validator.validate_tool_result_size([attack_data])

        with pytest.raises(ValueError):
            validator.validate_resource_size(attack_data)

        with pytest.raises(ValueError):
            validator.validate_request_params_size({"attack": attack_data})

    def test_handles_deeply_nested_data_structures(self):
        """Test that deeply nested data doesn't cause stack overflow."""
        validator = RequestSizeValidator()

        # Create deeply nested structure
        nested = {}
        current = nested
        for i in range(1000):  # 1000 levels deep
            current["next"] = {}
            current = current["next"]
        current["data"] = "deep_data"

        # Should handle gracefully without stack overflow
        size = validator._calculate_content_size(nested)
        assert size > 0

    def test_concurrent_request_memory_limits(self):
        """Test that concurrent requests don't exceed memory limits."""
        validator = RequestSizeValidator(max_concurrent_memory_mb=50)  # 50MB total limit

        # Simulate multiple concurrent requests each using memory
        request_sizes = [10_000_000] * 6  # 6 requests of 10MB each (60MB total)

        with pytest.raises(ValueError, match="Total concurrent memory usage exceeds limit"):
            validator.validate_concurrent_memory_usage(request_sizes)